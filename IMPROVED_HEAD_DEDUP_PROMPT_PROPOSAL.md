# Head Dedup Prompt 改进建议

## 对比tail_dedup后的改进方向

### 借鉴点1: 更直白的表述

```yaml
当前表述 → 改进表述

"When uncertain about coreference → answer NO" 
→ "When in doubt, keep them separate"

"False merge is worse than false split"
→ "It's better to have duplicate entities than to incorrectly merge different ones"

"Apply CONSERVATIVE PRINCIPLE → answer NO"
→ "When contexts are insufficient or unclear, keep them separate"
```

### 借鉴点2: 简化Instructions结构

**当前结构**（过于详细）:
- CRITICAL RULES (4条)
- PROHIBITED MERGE REASONS (5个反例)
- CONTEXT USAGE GUIDANCE (4个原则)  
- DECISION PROCEDURE (3个PHASE, 每个有多个sub-steps)

**建议简化为**（参考tail_dedup）:
- TASK: 明确任务
- INSTRUCTIONS: 3-5条核心指导
- CONTEXT USAGE: 简化为2-3条
- OUTPUT FORMAT

### 借鉴点3: Context使用的表述

**当前**:
```
1. Identify contradictions: If the contexts reveal contradictory information...
2. Find supporting evidence: If the contexts show consistent and complementary information...
3. Assess information sufficiency: If context is too limited...
4. Recognize hierarchical relationships: If context shows one entity owns/contains/manages...
```

**建议简化**:
```
Use the provided context (graph relationships and source text) to compare the two entities:
1. If contexts describe different situations or contain contradictions → keep them separate
2. If contexts describe the same entity with consistent information → they are coreferent
3. When contexts are insufficient or unclear → keep them separate (conservative approach)
```

### 借鉴点4: 增加"Different situations"的概念

Tail dedup中的"contexts describe different situations"很有用：
- 同名但不同时间段 → different situations
- 同名但不同地点 → different situations  
- 同名但不同组织 → different situations

可以在head_dedup中明确这个概念。

## 改进后的Prompt草稿

```yaml
with_representative_selection: |-
  You are an expert in knowledge graph entity resolution.

  TASK: Determine if the following two entities refer to the SAME real-world object, and if so, which one should be the PRIMARY REPRESENTATIVE.

  Entity 1 (ID: {entity_1_id}): {entity_1_desc}
  Graph relationships:
  {graph_context_1}
  Source text:
  {chunk_context_1}

  Entity 2 (ID: {entity_2_id}): {entity_2_desc}
  Graph relationships:
  {graph_context_2}
  Source text:
  {chunk_context_2}

  CORE INSTRUCTIONS:

  1. **Referential Identity**: Do they refer to the exact same real-world object?
     - Same entity with different names → YES (e.g., "UN" = "United Nations")
     - Different but related entities → NO (e.g., "Apple Inc." ≠ "Apple Store")
     - Same name, different situations → NO (e.g., "张三 (professor at Tsinghua)" ≠ "张三 (student at Peking University)")

  2. **Use Context to Compare**:
     - If contexts describe the same entity with consistent information → they are coreferent
     - If contexts describe different situations or contain contradictions → keep them separate
     - If contexts are insufficient or unclear → keep them separate (conservative approach)

  3. **Common Mistakes to Avoid**:
     ✗ Merging entities just because they have similar names
     ✗ Merging entities just because they are in the same category
     ✗ Merging entities when they have a hierarchical relationship (owner-owned, parent-child)
     ✗ Merging entities when some relations match but key information conflicts

  4. **Conservative Principle**:
     When in doubt, keep them separate. It's better to have duplicate entities than to incorrectly merge different ones.

  5. **Representative Selection** (only if coreferent):
     Choose the entity with:
     - More complete and formal name
     - More graph relationships (richer information)
     - Standard/official naming (considering domain conventions)

  OUTPUT FORMAT (strict JSON):
  {{
    "is_coreferent": true/false,
    "preferred_representative": "{entity_1_id}" or "{entity_2_id}" or null,
    "rationale": "Explain: (1) How context informed your decision, (2) Why they are same/different, (3) If same, why you chose this representative"
  }}

  EXAMPLES:
  [精简示例，每个示例只保留关键信息]
```

## 主要改进

1. ✅ 删除冗余部分：合并CRITICAL RULES和PROHIBITED MERGE REASONS
2. ✅ 更直白的表述："When in doubt, keep them separate"
3. ✅ 引入"different situations"概念
4. ✅ 简化CONTEXT USAGE到2-3条核心指导
5. ✅ 删除复杂的PHASE结构，让LLM自然推理
6. ✅ 保留关键的反例说明，但更简洁

## 是否需要实施？

这个改进会让prompt:
- 更简洁（预计减少30-40%长度）
- 更易理解
- 保持所有核心功能

但也可能:
- 失去一些详细指导
- 需要测试效果是否保持

建议：可以创建一个simplified版本和当前详细版本并行测试。
