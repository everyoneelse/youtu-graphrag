"""
改进的语义去重Prompt
解决问题：
1. 一致性问题：rationale和members不匹配
2. 多值关系过度合并：功能相似被错误合并
3. Context冗余问题
"""

IMPROVED_SEMANTIC_DEDUP_PROMPT = """You are a knowledge graph curation assistant performing entity deduplication.

🚨 MOST COMMON ERROR TO AVOID 🚨

❌ WRONG: "X and Y both achieve the same goal" → MERGE
❌ WRONG: "X and Y are both methods/solutions/types for Z" → MERGE
❌ WRONG: "X and Y have similar functions" → MERGE

✓ CORRECT: "X and Y are different names for THE SAME entity" → MERGE

Example of WRONG reasoning:
- ECG门控、VCG门控、指脉门控 all use physiological signals for gating
- They achieve the same goal (reduce motion artifacts)
- ❌ WRONG: Merge them because they're similar
- ✓ CORRECT: Keep separate - they are THREE different techniques

Example of CORRECT reasoning:
- "New York City", "NYC", "纽约" - different names for ONE city → MERGE
- "阿司匹林" and "Aspirin" - same drug in Chinese/English → MERGE

=============================================================================

TASK INFORMATION:

Head entity: {head}
Relation: {relation}

⚠️ RELATION CHECK:
{relation_warning}

Shared source contexts:
{head_context}

Candidate tails for deduplication:
{candidates}

=============================================================================

CORE PRINCIPLE: REFERENTIAL IDENTITY

Two expressions are COREFERENT if and only if:
1. They refer to the exact same entity in the real world
2. They are interchangeable in all contexts without changing facts
3. The only difference is linguistic expression, not the referent

Tests to apply:

TEST 1 - SUBSTITUTION:
If text says "研究使用了X", can you replace X with Y without changing the fact?
- "使用了ECG门控" → "使用了指脉门控" = ❌ CHANGES FACT → Different entities
- "位于New York" → "位于NYC" = ✓ SAME FACT → Same entity

TEST 2 - INFORMATION LOSS:
Would merging X and Y lose information?
- Merging "ECG门控" and "VCG门控" → ❌ YES, loses which technique was used
- Merging "New York City" and "NYC" → ✓ NO, just different spellings

TEST 3 - MULTI-VALUED RELATION:
Does this relation typically have multiple different values?
- "解决方案" (solution) → Usually YES → Default: KEEP SEPARATE
- "别名" (alias) → Usually NO → More likely to merge

⚠️ SPECIAL WARNING FOR MULTI-VALUED RELATIONS:

If the relation is like:
- X --解决方案--> {{Y1, Y2, Y3}} (multiple solutions)
- X --方法--> {{Y1, Y2, Y3}} (multiple methods)
- X --类型--> {{Y1, Y2, Y3}} (multiple types)
- X --包括--> {{Y1, Y2, Y3}} (multiple parts)
- X --表现--> {{Y1, Y2, Y3}} (multiple manifestations)

Then Y1, Y2, Y3 are typically DIFFERENT entities, even if:
- They serve the same purpose
- They belong to the same category
- They are listed together
- They have similar properties

Only merge if they are SYNONYMS (different words for the same thing).

=============================================================================

DECISION PROCEDURE:

For each pair of candidates [i] and [j]:

Step 1: Ask "Are [i] and [j] the same entity or different entities?"
        NOT "Are they similar?" or "Do they serve the same purpose?"
        
Step 2: Apply SUBSTITUTION TEST
        Can I swap them in any sentence without changing truth value?
        
Step 3: Apply INFORMATION TEST
        Would merging lose information about which specific entity/method/solution?
        
Step 4: If uncertain → KEEP SEPARATE (conservative principle)

=============================================================================

OUTPUT REQUIREMENTS:

1. Use the SAME indexing in both rationale and members array
2. Candidates are numbered [1], [2], [3], etc. - use these numbers consistently
3. Before finalizing, CHECK:
   ✓ If rationale says "[X] and [Y] are the same", then X and Y are in same members array?
   ✓ If rationale says "[X] and [Y] are different", then they are in different groups?
   ✓ Does each rationale explain why its members are THE SAME entity?

4. Rationale writing rules:
   - Focus on explaining why members refer to the SAME entity
   - Use candidate numbers: "[1] and [2] both refer to..."
   - Do NOT say "should merge with [X]" if [X] is not in this group's members
   - Do NOT compare with other groups

5. Every candidate must appear in exactly one group

JSON Schema:
{{
  "groups": [
    {{
      "members": [1, 3],
      "representative": 1,
      "rationale": "为什么[1]和[3]指向同一个实体的中文解释"
    }}
  ]
}}

=============================================================================

SELF-CHECK BEFORE OUTPUT (必须检查):

□ 我是否基于"功能相似"做了合并？如果是，这是错误的！
□ 每个group的members是否真的指向同一个实体？
□ 我的rationale是否与members数组一致？
□ 如果rationale说"应该合并"，它们是否在同一个group？
□ 对于多值关系，我是否默认保持分离？

Now generate your output:
"""


def build_improved_prompt(
    head: str,
    relation: str,
    head_context_lines: list[str],
    batch_entries: list[dict],
) -> str:
    """
    构建改进版的语义去重prompt
    
    改进点：
    1. 消除context冗余 - 所有contexts只在开头列出一次
    2. 突出关键原则 - 功能相似≠实体同一
    3. 添加关系类型分析
    4. 强化输出一致性检查
    """
    
    # 1. 分析关系类型
    multi_valued_keywords = {
        "解决方案", "solution", "approach", "method", "方法", "技术", 
        "technique", "表现", "manifestation", "presentation", "类型", 
        "type", "category", "包括", "include", "comprise", "步骤", 
        "step", "procedure", "特征", "feature", "cause", "原因"
    }
    
    relation_lower = (relation or "").lower()
    is_likely_multi_valued = any(kw in relation_lower for kw in multi_valued_keywords)
    
    if is_likely_multi_valued:
        relation_warning = (
            f"⚠️ WARNING: '{relation}' appears to be a MULTI-VALUED relation.\n"
            f"   This means one head entity can have MULTIPLE DIFFERENT tail entities.\n"
            f"   → Each tail is likely a DIFFERENT solution/method/type\n"
            f"   → Only merge if tails are SYNONYMS (different names for the SAME thing)\n"
            f"   → Default strategy: KEEP SEPARATE unless clearly coreferent\n"
            f"   → Test: If I say 'use method A', can I randomly replace with 'use method B' without changing facts? If NO → different entities"
        )
    else:
        relation_warning = (
            f"The relation '{relation}' may support multiple distinct values.\n"
            f"Carefully verify whether tails are synonyms or distinct entities."
        )
    
    # 2. 构建candidates列表（简化，避免重复context）
    # 收集所有chunk IDs以便引用
    candidate_lines = []
    for idx, entry in enumerate(batch_entries, start=1):
        description = entry.get("description", "[NO DESCRIPTION]")
        chunk_id = entry.get("chunk_id", "unknown")
        schema_type = entry.get("schema_type", "")
        type_suffix = f", type: {schema_type}" if schema_type else ""
        
        candidate_lines.append(
            f"[{idx}] {description} (chunk: {chunk_id}{type_suffix})"
        )
    
    candidates_text = "\n".join(candidate_lines) if candidate_lines else "[No candidates]"
    
    # 3. 构建共享contexts（只列出一次，带chunk id标识）
    head_context_text = "\n".join(head_context_lines) if head_context_lines else "- (no context available)"
    
    # 4. 填充prompt
    return IMPROVED_SEMANTIC_DEDUP_PROMPT.format(
        head=head or "[UNKNOWN_HEAD]",
        relation=relation or "[UNKNOWN_RELATION]",
        relation_warning=relation_warning,
        head_context=head_context_text,
        candidates=candidates_text,
    )


# 使用示例
if __name__ == "__main__":
    # 测试案例1: 化学位移伪影
    test_head = "第一类化学位移伪影"
    test_relation = "表现形式为"
    test_contexts = [
        "- (p6Mx8KB1) 第一类化学位移伪影表现为皮下脂肪投影于器官，脂肪和水交界面的黑色暗带...",
        "- (NlU-Bk_n) 脂肪组织的信号会在频率编码方向上向梯度场较低的一侧偏移...",
        "- (VvffD1OO) 图像中位置发生移位的现象..."
    ]
    test_entries = [
        {"description": "皮下脂肪投影于器官", "chunk_id": "p6Mx8KB1", "schema_type": "表现"},
        {"description": "脂肪组织信号偏移", "chunk_id": "NlU-Bk_n", "schema_type": "机制"},
        {"description": "信号板块移动", "chunk_id": "VvffD1OO", "schema_type": "现象"},
    ]
    
    prompt1 = build_improved_prompt(test_head, test_relation, test_contexts, test_entries)
    print("=" * 80)
    print("测试案例1: 化学位移伪影")
    print("=" * 80)
    print(prompt1)
    
    # 测试案例2: 门控扫描
    test_head2 = "流动伪影"
    test_relation2 = "解决方案"
    test_contexts2 = [
        "- (JICjXeah) 门控技术通过同步生理信号来减少运动伪影..."
    ]
    test_entries2 = [
        {"description": "ECG门控扫描", "chunk_id": "JICjXeah", "schema_type": "技术"},
        {"description": "VCG门控扫描", "chunk_id": "JICjXeah", "schema_type": "技术"},
        {"description": "指脉式门控扫描", "chunk_id": "JICjXeah", "schema_type": "技术"},
    ]
    
    prompt2 = build_improved_prompt(test_head2, test_relation2, test_contexts2, test_entries2)
    print("\n\n")
    print("=" * 80)
    print("测试案例2: 门控扫描（多值关系）")
    print("=" * 80)
    print(prompt2)
