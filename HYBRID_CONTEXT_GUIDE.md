# Hybrid Context Feature for Head Deduplication

## 概述

`use_hybrid_context` 功能现已完全实现！该功能允许在 head deduplication 过程中同时使用**图关系上下文**和**原始文本块（chunk）**来帮助 LLM 做出更准确的实体去重决策。

## 什么是 Context？

在 head_dedup 的 prompt 中，`context` 包含：

### 1. 图关系上下文（默认，始终启用）
- **出边关系**：该实体作为 head 的关系
  - 格式：`• relation → tail_entity_description`
  - 例如：`• founded_by → Steve Jobs [person]`

- **入边关系**：该实体作为 tail 的关系
  - 格式：`• head_entity_description → relation`
  - 例如：`• iPhone [product] → produced_by`

### 2. 文本块上下文（可选，通过 `use_hybrid_context` 启用）
- 实体所在的原始文本片段
- 格式：`Source text: "...chunk text..."`
- 提供实体出现的原始语境

## 配置方法

在配置文件中（如 `config/base_config.yaml`）：

```yaml
construction:
  semantic_dedup:
    head_dedup:
      enabled: true
      use_hybrid_context: false  # 设为 true 启用混合上下文
```

## 何时使用 Hybrid Context？

### ✅ 适合使用的场景

1. **实体关系稀疏**：如果实体在图中的关系很少，图上下文信息不足
2. **需要更多语境**：实体名称相似但需要原始文本来区分
3. **高精度要求**：对去重精度要求极高，愿意牺牲速度和成本
4. **复杂领域**：医学、法律等需要精确语境的领域

### ❌不适合使用的场景

1. **大规模数据**：chunk 文本会显著增加 token 消耗和成本
2. **图关系丰富**：如果实体已经有足够的关系上下文
3. **速度优先**：需要快速处理大量实体对
4. **简单场景**：实体名称差异明显，不需要额外上下文

## 性能影响

| 方面 | 仅图关系 | 混合上下文 |
|------|---------|----------|
| **速度** | 快 | 慢（~2-3x） |
| **Token消耗** | 低 | 高（~3-5x） |
| **精度** | 高 | 更高 |
| **成本** | 低 | 高 |

## 实现细节

### 核心函数

#### `_collect_chunk_context(node_id, max_length=500)`

从节点获取其所在的 chunk 文本：

```python
def _collect_chunk_context(self, node_id: str, max_length: int = 500) -> str:
    """
    Collect chunk text context for a node.
    
    Returns:
        Formatted chunk context string
    """
    # 1. 从节点属性获取 chunk_id
    chunk_id = node.properties.get("chunk id")
    
    # 2. 从 self.all_chunks 获取 chunk 文本
    chunk_text = self.all_chunks.get(chunk_id)
    
    # 3. 截断过长的文本（默认 500 字符）
    if len(chunk_text) > max_length:
        chunk_text = chunk_text[:max_length] + "..."
    
    return f'  Source text: "{chunk_text}"'
```

#### `_build_head_dedup_prompt_v2()` 的修改

```python
# 始终收集图关系上下文
context_1 = self._collect_node_context(node_id_1, max_relations=10)
context_2 = self._collect_node_context(node_id_2, max_relations=10)

# 如果启用混合上下文，添加 chunk 文本
if use_hybrid_context:
    chunk_context_1 = self._collect_chunk_context(node_id_1)
    chunk_context_2 = self._collect_chunk_context(node_id_2)
    
    # 合并图关系和 chunk 文本
    context_1 = f"{context_1}\n{chunk_context_1}"
    context_2 = f"{context_2}\n{chunk_context_2}"
```

### Prompt 示例

#### 不启用 hybrid context（默认）

```
Entity 1: Apple Inc. [organization]
Related knowledge about Entity 1:
  • founded_by → Steve Jobs [person]
  • produces → iPhone [product]
  • headquartered_in → Cupertino [location]

Entity 2: Apple Computer [organization]
Related knowledge about Entity 2:
  • founded_by → Steve Jobs [person]
  • founded_in → 1976 [date]
```

#### 启用 hybrid context

```
Entity 1: Apple Inc. [organization]
Related knowledge about Entity 1:
  • founded_by → Steve Jobs [person]
  • produces → iPhone [product]
  • headquartered_in → Cupertino [location]
  Source text: "Apple Inc. is a multinational technology company that designs, develops, and sells consumer electronics, computer software, and online services."

Entity 2: Apple Computer [organization]
Related knowledge about Entity 2:
  • founded_by → Steve Jobs [person]
  • founded_in → 1976 [date]
  Source text: "Apple Computer was founded on April 1, 1976, by Steve Jobs, Steve Wozniak, and Ronald Wayne to develop and sell personal computers."
```

可以看到，混合上下文提供了更丰富的信息，帮助 LLM 理解这两个实体实际上指代同一公司（只是名称演变）。

## 使用示例

```python
from models.constructor.kt_gen import KnowledgeTreeGen
from config import get_config

# 加载配置
config = get_config("your_dataset")

# 修改配置启用混合上下文
config.construction.semantic_dedup.head_dedup.use_hybrid_context = True

# 创建构建器
builder = KnowledgeTreeGen("experiment_name", config)

# 构建图
builder.build_from_corpus("path/to/corpus.json")

# 执行带混合上下文的 head 去重
stats = builder.deduplicate_heads_with_llm_v2(
    enable_semantic=True,
    similarity_threshold=0.85,
    max_candidates=1000
)

print(f"Merged {stats['total_merges']} entity pairs")
```

## 配置参数

```yaml
head_dedup:
  # 是否启用混合上下文
  use_hybrid_context: false  # true 或 false
  
  # 控制上下文中包含的关系数量
  max_relations_context: 10  # 默认 10
```

注意：`max_length` 参数（chunk 截断长度）目前硬编码为 500 字符，可以在代码中修改。

## 技术细节

### 数据流

1. **节点存储 chunk_id**：
   ```python
   node.properties = {
       "name": "entity_name",
       "chunk id": "chunk_12345"  # 或 "chunk_id"
   }
   ```

2. **KnowledgeTreeGen 存储 chunk 文本**：
   ```python
   self.all_chunks = {
       "chunk_12345": "actual chunk text...",
       ...
   }
   ```

3. **_collect_chunk_context 检索文本**：
   - 从节点属性获取 chunk_id
   - 从 self.all_chunks 字典获取文本
   - 截断并格式化

### 错误处理

函数会优雅地处理以下情况：
- 节点不存在：返回 `(Node not found in graph)`
- 无 chunk_id：返回 `(No chunk information)`
- chunk 未找到：返回 `(Chunk {chunk_id} not found)`

## 验证实现

运行验证脚本：

```bash
python3 verify_hybrid_context_implementation.py
```

应该看到所有检查都通过 ✓

## 性能建议

1. **小规模测试**：先在小数据集上测试效果和成本
2. **监控 token 使用**：启用后监控 LLM API 的 token 消耗
3. **对比实验**：对比启用前后的去重质量
4. **动态调整**：根据实际效果决定是否保持启用

## 总结

`use_hybrid_context` 功能提供了一种在精度和性能之间平衡的选项：

- **默认（false）**：快速、经济、适合大多数场景
- **启用（true）**：更高精度、更多成本、适合特定场景

根据你的具体需求选择合适的模式！
