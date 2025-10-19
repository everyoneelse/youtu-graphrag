# 聚类描述格式修改说明 (方案B)

## 修改概述

实现了**双描述策略**：
- **向量聚类**使用简化描述（去除 `chunk id` 和 `label`）
- **LLM prompt**保留完整描述（包含所有信息）

这样既提高了向量聚类的准确性，又让 LLM 能够看到完整的上下文信息。

## 修改内容

### 1. 新增方法：`_describe_node_for_clustering`

在 `models/constructor/kt_gen.py` 中添加了新方法（第741-768行）：

```python
def _describe_node_for_clustering(self, node_id: str) -> str:
    """Generate a simplified description for semantic clustering.
    
    This method excludes chunk_id and label information to focus on
    the semantic content of the node for better clustering results.
    """
    node_data = self.graph.nodes.get(node_id, {})
    properties = node_data.get("properties", {})

    if isinstance(properties, dict):
        name = properties.get("name") or properties.get("title")
        extras = []
        for key, value in properties.items():
            # Skip name, chunk_id, and empty values
            if key == "name" or key == "chunk id" or key == "chunk_id" or value in (None, ""):
                continue
            extras.append(f"{key}: {value}")

        extra_text = ", ".join(extras)
        if name and extra_text:
            return f"{name} ({extra_text})"
        if name:
            return name
        if extra_text:
            return extra_text

    # Fallback to node name only
    return properties.get("name") or properties.get("title") or node_id
```

### 2. 修改边去重（Triple Deduplication）

在 `_semantic_deduplicate_group` 方法中（第1622-1638行），现在同时生成两种描述：

**修改后：**
```python
entries.append(
    {
        "index": idx,
        "node_id": tail_id,
        "data": copy.deepcopy(data),
        "raw_data": copy.deepcopy(data),
        "description": self._describe_node(tail_id),  # Full for LLM
        "description_for_clustering": self._describe_node_for_clustering(tail_id),  # Simple for clustering
        "context_chunk_ids": chunk_ids,
        "context_summaries": self._summarize_contexts(chunk_ids),
    }
)
```

调用聚类时使用简化描述（第1654-1656行）：
```python
# Use simplified descriptions for vector-based clustering
candidate_descriptions = [entry["description_for_clustering"] for entry in entries]
initial_clusters = self._cluster_candidate_tails(candidate_descriptions, threshold)
```

### 3. 修改关键词去重（Keyword Deduplication）

在 `_deduplicate_keyword_nodes` 方法中（第1320-1346行），同时生成两种描述：

**修改后：**
```python
if source_entity_id and source_entity_id in self.graph:
    source_entity_name_full = self._describe_node(source_entity_id)  # Full for LLM
    source_entity_name_simple = self._describe_node_for_clustering(source_entity_id)  # Simple for clustering
    ...

# Full description for LLM prompt
description_full = raw_name
if source_entity_name_full and source_entity_name_full not in description_full:
    description_full = f"{raw_name} (from {source_entity_name_full})"

# Simplified description for vector clustering
description_simple = raw_name
if source_entity_name_simple and source_entity_name_simple not in description_simple:
    description_simple = f"{raw_name} (from {source_entity_name_simple})"

entries.append(
    {
        "node_id": kw_id,
        "description": description_full,  # Full for LLM
        "description_for_clustering": description_simple,  # Simple for clustering
        ...
    }
)
```

调用聚类时使用简化描述（第1395-1397行）：
```python
# Use simplified descriptions for vector-based clustering
candidate_descriptions = [entry["description_for_clustering"] for entry in entries]
initial_clusters = self._cluster_candidate_tails(candidate_descriptions, threshold)
```

## 效果对比

### 边去重示例：

**向量聚类看到的（简化）：**
```
关键角度: 55°
```

**LLM prompt 看到的（完整）：**
```
关键角度: 55° (chunk id: PHuCr1nf) [attribute]
```

### 关键词去重示例：

**向量聚类看到的（简化）：**
```
高温环境 (from 产品型号 (schema_type: Product))
```

**LLM prompt 看到的（完整）：**
```
高温环境 (from 产品型号 (schema_type: Product, chunk id: ABC123) [entity])
```

## 优势

1. **向量聚类更准确**：
   - 去除无关的技术元数据（chunk id 和 label）
   - 向量编码器能够专注于实际的语义内容
   - 不同 chunk 中的相同概念更容易被识别为语义相似

2. **LLM 判断更精准**：
   - 保留完整的上下文信息（chunk id 和 label）
   - LLM 可以利用这些元数据进行更准确的语义判断
   - 便于 LLM 理解节点的类型和来源

3. **两阶段协同优化**：
   - 第一阶段（向量聚类）：快速粗筛，基于纯语义相似度
   - 第二阶段（LLM 精排）：精细判断，利用完整上下文

## 实现细节

- 原有的 `_describe_node` 方法保持不变
- 新增 `_describe_node_for_clustering` 方法用于生成简化描述
- 每个 entry 同时包含 `description`（完整）和 `description_for_clustering`（简化）
- `_cluster_candidate_tails` 使用简化描述
- `_build_semantic_dedup_prompt` 使用完整描述
- chunk id 信息仍然被保留在节点的 properties 中

## 测试验证

创建测试节点并查看两种描述：

```python
from models.constructor.kt_gen import KTBuilder
from config import get_config

config = get_config()
builder = KTBuilder("test", mode="noagent")

# 创建测试节点
builder.graph.add_node(
    "test_node",
    label="attribute",
    properties={"name": "关键角度", "value": "55°", "chunk id": "PHuCr1nf"},
    level=1
)

# 比较两种描述方式
print("完整描述 (用于 LLM):", builder._describe_node("test_node"))
# 输出: 关键角度 (value: 55°, chunk id: PHuCr1nf) [attribute]

print("聚类描述 (用于向量):", builder._describe_node_for_clustering("test_node"))
# 输出: 关键角度 (value: 55°)
```

### 数据流验证

```
节点 → _describe_node() → 完整描述
                        ↓
                   _build_semantic_dedup_prompt() → LLM
                   
节点 → _describe_node_for_clustering() → 简化描述
                                      ↓
                                _cluster_candidate_tails() → 向量编码 → 聚类
```

## 相关文件

- `models/constructor/kt_gen.py` - 主要修改文件
- `offline_semantic_dedup.py` - 离线去重脚本（自动使用新方法）
