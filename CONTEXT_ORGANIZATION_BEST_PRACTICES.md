# Context组织的最佳实践

## 实验发现

**同一组候选实体**，仅改变context组织形式：

| Context组织方式 | 结果 | 准确性 |
|----------------|------|--------|
| 每个candidate独立的详细context | 6个独立组（过度分离） | ❌ 错误 |
| Shared context + 简洁候选列表 | 2个组（合理合并） | ✓ 正确 |

## 推荐方案：Shared Context模式

### ✅ 推荐的结构

```
=============================================================================
HEAD ENTITY: {head}
RELATION: {relation}

SHARED SOURCE CONTEXTS:
{所有相关的contexts，按chunk_id组织，只出现一次}

CANDIDATE TAILS FOR DEDUPLICATION:
[1] {description_1} (source: {chunk_id_1})
[2] {description_2} (source: {chunk_id_2})
[3] {description_3} (source: {chunk_id_3})
...
=============================================================================
```

### 优势

1. **减少Token消耗**：
   - 每个chunk只出现一次
   - 通常减少50-70%的context token

2. **提高判断准确性**：
   - LLM聚焦于candidate的核心语义
   - 不被不同的context描述分散注意力
   - 自动将候选项置于"同一背景"下比较

3. **更好的对比性**：
   - 所有candidates在同一信息基础上
   - 更容易识别同义表达
   - 减少过度分离

### 实施代码

```python
def build_dedup_prompt_with_shared_context(
    head: str,
    relation: str,
    batch_entries: list[dict],
    all_chunks: dict[str, str]
) -> str:
    """
    构建使用shared context的去重prompt
    """
    
    # 1. 收集所有相关的chunk_ids
    all_chunk_ids = set()
    for entry in batch_entries:
        chunk_id = entry.get("chunk_id")
        if chunk_id:
            all_chunk_ids.add(chunk_id)
    
    # 2. 构建shared context（只出现一次）
    shared_context_lines = []
    for chunk_id in sorted(all_chunk_ids):
        if chunk_id in all_chunks:
            chunk_text = all_chunks[chunk_id]
            # 可选：截断过长的chunk
            if len(chunk_text) > 500:
                chunk_text = chunk_text[:500] + "..."
            shared_context_lines.append(f"- ({chunk_id}) {chunk_text}")
    
    shared_contexts = "\n".join(shared_context_lines) if shared_context_lines else "(No context available)"
    
    # 3. 构建简洁的candidate列表（只有描述+chunk引用）
    candidate_lines = []
    for idx, entry in enumerate(batch_entries, start=1):
        description = entry.get("description", "[NO DESCRIPTION]")
        chunk_id = entry.get("chunk_id", "unknown")
        schema_type = entry.get("schema_type", "")
        
        type_info = f", type: {schema_type}" if schema_type else ""
        candidate_lines.append(
            f"[{idx}] {description} (source: {chunk_id}{type_info})"
        )
    
    candidates = "\n".join(candidate_lines)
    
    # 4. 填充prompt模板
    return PROMPT_TEMPLATE.format(
        head=head,
        relation=relation,
        shared_contexts=shared_contexts,
        candidates=candidates
    )
```

## ❌ 不推荐的结构

### 每个candidate独立context

```
CANDIDATE TAILS:
[1] Tail: {description_1}
    Contexts:
        - {context_1a}
        - {context_1b}
[2] Tail: {description_2}
    Contexts:
        - {context_2a}  [可能与1a重复]
        - {context_2b}  [可能与1b重复]
```

### 问题

1. **Context重复**：
   - 同一个chunk可能在多个candidates中重复
   - 浪费大量tokens

2. **导致过度分离**：
   - LLM看到"不同的contexts"
   - 错误推断"不同的实体"

3. **信息过载**：
   - 每个candidate都有大量文本
   - LLM难以聚焦于核心语义

## 对比实验数据

### 测试案例：化学位移定义去重

**候选项**：
1. 原子核共振频率差异
2. 水和脂肪质子频率差异
3. 不同组织氢质子频率不同
4. 导致脂肪和水频率差异（因果描述）
5. 不同化学环境频率差异
6. 共振频率因分子环境变化

**期望结果**：
- [1,2,3,5,6] 合并（都是定义，同义表达）
- [4] 独立（因果描述，不是定义）

### 结果对比

| Context组织 | LLM输出 | 准确性 | Token消耗 |
|------------|---------|--------|-----------|
| **独立context** | 6个独立组 | ❌ 过度分离 | ~2000 tokens |
| **Shared context** | 2个组（[1,2,3,5,6], [4]） | ✓ 正确 | ~1000 tokens |

**改进效果**：
- ✅ 准确性：从错误 → 正确
- ✅ Token：减少50%
- ✅ 一致性：更稳定

## 实施建议

### 立即行动

1. **修改`kt_gen.py`中的`_build_semantic_dedup_prompt`**：

```python
def _build_semantic_dedup_prompt(self, head_text, relation, head_context_lines, batch_entries):
    # 收集所有chunk_ids
    all_chunk_ids = set()
    for entry in batch_entries:
        for chunk_id in entry.get("chunk_ids", []):
            if chunk_id:
                all_chunk_ids.add(chunk_id)
    
    # Shared contexts（只出现一次）
    shared_context_lines = []
    for chunk_id in sorted(all_chunk_ids):
        if chunk_id in self.all_chunks:
            chunk_summary = self._summarize_chunk(chunk_id)  # 可选：摘要
            shared_context_lines.append(f"- ({chunk_id}) {chunk_summary}")
    
    # 简洁的candidate列表
    candidate_lines = []
    for idx, entry in enumerate(batch_entries, start=1):
        description = entry.get("description", "[NO DESCRIPTION]")
        chunk_id = entry.get("chunk_id", "unknown")
        candidate_lines.append(f"[{idx}] {description} (source: {chunk_id})")
    
    return PROMPT.format(
        head=head_text,
        relation=relation,
        shared_contexts="\n".join(shared_context_lines),
        candidates="\n".join(candidate_lines)
    )
```

2. **更新Prompt模板**：

确保prompt模板使用：
```
Shared source contexts:
{shared_contexts}

Candidate tails:
{candidates}
```

而不是：
```
Candidate tails:
[1] Tail: XXX
    Contexts: ...
```

### 验证步骤

1. 在化学位移案例上测试
2. 在门控扫描案例上测试
3. 比较准确率和token消耗
4. 确认改进效果

## 其他优化建议

### 1. Context去重

如果多个candidates来自同一个chunk，该chunk在shared contexts中只出现一次：

```python
# 去重chunk_ids
unique_chunks = {}
for entry in batch_entries:
    chunk_id = entry.get("chunk_id")
    if chunk_id and chunk_id not in unique_chunks:
        unique_chunks[chunk_id] = self.all_chunks.get(chunk_id, "")
```

### 2. Context优先级排序

按相关性排序chunks：

```python
# 按出现频率或重要性排序
chunk_frequency = Counter(entry.get("chunk_id") for entry in batch_entries)
sorted_chunks = sorted(
    unique_chunks.items(),
    key=lambda x: chunk_frequency.get(x[0], 0),
    reverse=True
)
```

### 3. Context长度控制

对过长的context进行摘要或截断：

```python
def truncate_context(text: str, max_length: int = 500) -> str:
    if len(text) <= max_length:
        return text
    # 截断并添加省略号
    return text[:max_length] + "... (truncated)"
```

## 总结

**核心原则**：
- ✅ Shared context模式
- ✅ Context只出现一次
- ✅ Candidate列表简洁明了
- ✅ 通过chunk_id引用关联

**预期效果**：
- ✅ 减少过度分离
- ✅ 提高合并准确性
- ✅ 节省50%+ tokens
- ✅ 结果更稳定一致

**关键洞察**：
Context组织方式不是技术细节，而是**影响LLM判断的关键因素**。
正确的组织方式能让LLM更准确地理解任务：比较candidates的核心语义，
而不是被不同的background descriptions分散注意力。
