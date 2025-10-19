# 聚类描述格式修改说明

## 修改概述

修改了语义去重聚类时使用的节点描述格式，去除了 `chunk id` 和节点 `label` 信息，只保留核心语义内容，以提高聚类的准确性。

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

在 `_semantic_deduplicate_group` 方法中（第1634行），修改了生成 tail 节点描述的方式：

**修改前：**
```python
"description": self._describe_node(tail_id),
```

**修改后：**
```python
"description": self._describe_node_for_clustering(tail_id),
```

### 3. 修改关键词去重（Keyword Deduplication）

在 `_deduplicate_keyword_nodes` 方法中（第1325行），修改了生成 source entity 描述的方式：

**修改前：**
```python
source_entity_name = self._describe_node(source_entity_id)
```

**修改后：**
```python
source_entity_name = self._describe_node_for_clustering(source_entity_id)
```

## 效果对比

### 修改前的描述格式：
```
关键角度: 55° (chunk id: PHuCr1nf) [attribute]
产品型号 (schema_type: Product, chunk id: ABC123) [entity]
高温环境 (chunk id: XYZ789) [keyword]
```

### 修改后的描述格式（用于聚类）：
```
关键角度: 55°
产品型号 (schema_type: Product)
高温环境
```

## 优势

1. **更准确的语义聚类**：去除无关的技术元数据（chunk id 和 label），使模型能够专注于实际的语义内容
2. **更简洁的输入**：减少了向量编码器的输入长度，提高了处理效率
3. **更好的泛化能力**：不同 chunk 中的相同概念现在更容易被识别为语义相似

## 不影响的功能

- 原有的 `_describe_node` 方法保持不变，其他功能（如日志记录、结果展示等）仍然使用完整的描述格式
- 只有在语义聚类时才使用简化的描述格式
- chunk id 信息仍然被保留在节点的 properties 中，可以在需要时访问

## 测试验证

可以使用以下脚本验证修改效果：

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
print("完整描述:", builder._describe_node("test_node"))
# 输出: 关键角度 (value: 55°, chunk id: PHuCr1nf) [attribute]

print("聚类描述:", builder._describe_node_for_clustering("test_node"))
# 输出: 关键角度 (value: 55°)
```

## 相关文件

- `models/constructor/kt_gen.py` - 主要修改文件
- `offline_semantic_dedup.py` - 离线去重脚本（自动使用新方法）
