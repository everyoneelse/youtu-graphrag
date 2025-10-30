# 对话记录：Head Deduplication LLM验证的关系图深度分析

**时间**: 2025-10-30 02:04:21  
**主题**: Head去重时LLM验证阶段的关系图深度  
**分支**: cursor/check-head-deduplication-llm-relationship-graph-depth-d008

---

## 用户问题

帮我看下在head_dedup时，llm进行验证的时候，所为每个实体准备的关系图的深度是什么？

---

## 回答概要

在 head_dedup 时，LLM 验证阶段为每个实体准备的关系图深度是 **1-hop（深度为1）**。

---

## 详细分析

### 核心函数：`_collect_node_context`

该函数负责收集实体节点的上下文信息，位于 `models/constructor/kt_gen.py`:

```python
def _collect_node_context(self, node_id: str, max_relations: int = 10) -> str:
    """Collect graph relations as context for a node."""
    config = self.config.construction.semantic_dedup.head_dedup if hasattr(
        self.config.construction.semantic_dedup, 'head_dedup'
    ) else None
    
    if config:
        max_relations = getattr(config, 'max_relations_context', 10)
    
    contexts = []
    
    # Outgoing edges
    out_edges = list(self.graph.out_edges(node_id, data=True))[:max_relations]
    for _, tail_id, data in out_edges:
        relation = data.get("relation", "related_to")
        tail_desc = self._describe_node(tail_id)
        contexts.append(f"  • {relation} → {tail_desc}")
    
    # Incoming edges
    in_edges = list(self.graph.in_edges(node_id, data=True))[:max_relations]
    for head_id, _, data in in_edges:
        relation = data.get("relation", "related_to")
        head_desc = self._describe_node(head_id)
        contexts.append(f"  • {head_desc} → {relation}")
    
    return "\n".join(contexts) if contexts else "  (No relations found)"
```

### 关键特征

#### 1. **关系图深度：1-hop**
- 只收集**直接连接**到目标实体的边
- 包括出边（outgoing edges）和入边（incoming edges）
- 不进行递归深度遍历

#### 2. **关系数量限制**
- 默认最多收集 **10 条关系**
- 可通过配置参数 `max_relations_context` 调整
- 超过限制时，取前 N 条关系

#### 3. **上下文格式**
- 出边格式：`• {relation} → {tail_entity_description}`
- 入边格式：`• {head_entity_description} → {relation}`

### 使用场景

该上下文信息在 LLM 验证时被使用，位于 `_build_head_dedup_prompt` 函数：

```python
def _build_head_dedup_prompt(self, node_id_1: str, node_id_2: str) -> str:
    """Build LLM prompt for head deduplication."""
    desc_1 = self._describe_node(node_id_1)
    desc_2 = self._describe_node(node_id_2)
    
    context_1 = self._collect_node_context(node_id_1)
    context_2 = self._collect_node_context(node_id_2)
    
    # Load prompt from config
    prompt_template = self.config.get_prompt_formatted(
        "head_dedup", 
        "general",
        entity_1=desc_1,
        context_1=context_1,
        entity_2=desc_2,
        context_2=context_2
    )
    return prompt_template
```

### 设计合理性

这种 1-hop 设计是合理的，原因包括：

1. **足够的区分性**：1-hop 邻居关系已经能提供足够的上下文信息来区分不同实体
2. **性能优化**：避免深度图遍历，提升处理速度
3. **成本控制**：限制上下文长度，降低 LLM 调用成本
4. **避免噪声**：过深的关系图可能引入不相关的噪声信息

---

## 配置参数

相关配置位于 `config.construction.semantic_dedup.head_dedup`:

- `max_relations_context`: 最多收集的关系数量（默认：10）
- `use_llm_validation`: 是否启用 LLM 验证（默认：False）
- `similarity_threshold`: 相似度阈值（默认：0.85）

---

## 相关文件

- `models/constructor/kt_gen.py` (行 5032-5057): `_collect_node_context` 函数
- `models/constructor/kt_gen.py` (行 5000-5030): `_build_head_dedup_prompt` 函数
- `models/constructor/kt_gen.py` (行 4946-4998): `_validate_candidates_with_llm` 函数

---

## 总结

Head去重时，LLM验证阶段为每个实体准备的关系图深度为 **1-hop**，默认收集最多 **10条** 直接相连的关系（包括入边和出边），这种设计在准确性、性能和成本之间取得了良好的平衡。
