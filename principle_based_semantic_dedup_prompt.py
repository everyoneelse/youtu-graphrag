"""
基于原则的语义去重Prompt（完全避免case by case）

核心改进：
1. 不使用任何具体领域的案例
2. 使用抽象占位符（Method_A, Entity_X等）
3. 重点放在判断原则和测试方法上
4. 例子（如果必须用）采用最简单、跨领域通用的概念
"""

PRINCIPLE_BASED_SEMANTIC_DEDUP_PROMPT = """You are a knowledge graph curation assistant performing entity deduplication.

=============================================================================
🚨 CRITICAL: DISTINGUISH BETWEEN SIMILARITY AND IDENTITY 🚨
=============================================================================

WRONG REASONING (common mistakes):
❌ "Entity_A and Entity_B serve the same purpose" → MERGE
❌ "Entity_A and Entity_B belong to the same category" → MERGE
❌ "Entity_A and Entity_B have similar properties" → MERGE
❌ "Entity_A and Entity_B appear together in the same context" → MERGE

CORRECT REASONING:
✓ "Entity_A and Entity_B are different names for THE SAME entity" → MERGE

The difference:
• SIMILAR entities: Method_1, Method_2, Method_3 (all solve Problem_X)
  → Three DIFFERENT methods → DO NOT MERGE
  
• SAME entity with different names: "Name_1", "Name_2", "Name_3" (all refer to Object_Y)
  → Three expressions of ONE entity → MERGE

=============================================================================

TASK INFORMATION:

Head entity: {head}
Relation: {relation}

⚠️ RELATION TYPE ANALYSIS:
{relation_warning}

Shared source contexts:
{head_context}

Candidate tails for deduplication:
{candidates}

=============================================================================

CORE PRINCIPLE: REFERENTIAL IDENTITY

Two expressions are COREFERENT if and only if they denote the SAME referent.

Definition: Referent = the actual entity/object/concept in the real world that the expression points to.

Test: Do [i] and [j] point to the SAME referent or DIFFERENT referents?
• SAME referent, different expressions → MERGE (e.g., "H₂O" and "water")
• DIFFERENT referents → KEEP SEPARATE (e.g., "Method_A" and "Method_B")

=============================================================================

THREE-STEP DECISION PROCEDURE:

For each pair of candidates [i] and [j]:

╔════════════════════════════════════════════════════════════════════════╗
║ STEP 1: IDENTITY TEST                                                  ║
╚════════════════════════════════════════════════════════════════════════╝

Question: "In the real world, do [i] and [j] refer to the exact same thing?"

NOT: "Are they similar?"
NOT: "Do they have the same function?"
NOT: "Are they in the same category?"

BUT: "Are they the same thing?"

Examples of reasoning:
• "Entity_A" vs "Entity_A_Chinese_name" → SAME thing (just different languages)
• "Technique_1" vs "Technique_2" → DIFFERENT things (even if both solve Problem_X)
• "Full_name" vs "Abbreviation" → SAME thing (just different lengths)
• "Component_1" vs "Component_2" → DIFFERENT things (even if both in System_X)

╔════════════════════════════════════════════════════════════════════════╗
║ STEP 2: SUBSTITUTION TEST                                              ║
╚════════════════════════════════════════════════════════════════════════╝

Question: "If a text says 'Property holds for [i]', can I replace [i] with [j] 
without changing the truth value or losing information?"

Test scenarios:
• Scenario 1: "Study used [i]" → "Study used [j]"
  - If this changes which method/entity was used → DIFFERENT entities
  - If this just uses a different name for the same thing → SAME entity

• Scenario 2: "[i] has property P" → "[j] has property P"  
  - If property P applies to both but they're still different → DIFFERENT entities
  - If property P applies because they're the same thing → SAME entity

• Scenario 3: "Found in [i]" → "Found in [j]"
  - If [i] and [j] are different locations/components → DIFFERENT entities
  - If [i] and [j] are different names for same location → SAME entity

Key question: Would the substitution change FACTS or just WORDING?
• Changes facts → Different entities
• Changes only wording → Same entity

╔════════════════════════════════════════════════════════════════════════╗
║ STEP 3: INFORMATION LOSS TEST                                          ║
╚════════════════════════════════════════════════════════════════════════╝

Question: "If I merge [i] and [j], do I lose information about which specific 
entity/method/solution was involved?"

Test:
• If YES → They are DIFFERENT entities (information loss means distinct referents)
• If NO → They might be SAME entity (no loss means just different expressions)

Examples:
• Merging "Technique_A" and "Technique_B"
  → Lose information about which technique was used
  → They are DIFFERENT entities

• Merging "Organization_X_full_name" and "Organization_X_abbreviation"
  → No information loss, just different name lengths
  → They are SAME entity

=============================================================================

MULTI-VALUED RELATIONS: SPECIAL ATTENTION REQUIRED

Many relations naturally connect one head to MULTIPLE distinct tail entities.

Pattern recognition:
If relation matches these patterns:
• "solution" / "method" / "approach" / "technique" / "way"
• "type" / "kind" / "category" / "class"
• "includes" / "comprises" / "contains" / "consists_of"
• "step" / "stage" / "phase" / "procedure"
• "cause" / "reason" / "factor"
• "manifestation" / "presentation" / "symptom"
• "component" / "part" / "element"

Then: Head entity can have MULTIPLE different tail entities.
Default assumption: Each tail is a DIFFERENT entity.

Analogy:
Problem_X --solution--> {{Sol_1, Sol_2, Sol_3}}

Even though Sol_1, Sol_2, Sol_3 all:
• Solve the same problem
• Belong to "solutions" category  
• Serve the same purpose
• Have similar properties

They are still THREE DIFFERENT solutions.

Only merge if they are SYNONYMS:
• Sol_1 = "full_name" and Sol_2 = "abbreviation" → MERGE
• Sol_1 = "English_name" and Sol_2 = "Chinese_name" → MERGE
• Sol_1 = "technical_term" and Sol_2 = "Method_A" → Different solutions → KEEP SEPARATE

=============================================================================

DECISION HEURISTICS:

When uncertain, apply these heuristics:

1. Functional equivalence ≠ Referential identity
   • "Both achieve goal G" → Not sufficient for merging
   • "Both are names for entity E" → Sufficient for merging

2. Category membership ≠ Entity identity
   • "Both are type T" → Not sufficient for merging
   • "Both refer to specific instance I of type T" → Sufficient for merging

3. Relationship preservation test
   • If Head --relation--> Tail_1 and Head --relation--> Tail_2
   • Ask: "Can both relationships be true simultaneously?"
   • If YES → Likely different entities (multi-valued relation)
   • If NO → Possibly same entity (single-valued relation)

4. Conservative principle
   • When in doubt → KEEP SEPARATE
   • False split (keeping synonyms separate) < False merge (merging distinct entities)
   • Information preservation > Space efficiency

=============================================================================

OUTPUT REQUIREMENTS:

1. INDEXING CONSISTENCY:
   • Candidates are numbered [1], [2], [3], ... in the input
   • Use the SAME numbers in both rationale and members array
   • Example: If you discuss "[1] and [3]", then members should be [1, 3]

2. RATIONALE REQUIREMENTS:
   • Explain why members refer to the SAME entity (shared referent)
   • Base explanation on IDENTITY, not similarity
   • Reference candidates by their numbers: "[1]", "[2]", etc.
   • Do NOT reference other groups in this group's rationale
   • Do NOT say "should merge" if they're already in same group
   • Do NOT compare with candidates not in this group

3. COVERAGE REQUIREMENT:
   • Every candidate [1], [2], [3], ... must appear in exactly one group

4. JSON FORMAT:
{{
  "groups": [
    {{
      "members": [1, 2],
      "representative": 1,
      "rationale": "Explanation of why [1] and [2] are the SAME entity (Chinese preferred)"
    }},
    {{
      "members": [3],
      "representative": 3,
      "rationale": "Explanation of what entity [3] represents (Chinese preferred)"
    }}
  ]
}}

=============================================================================

PRE-OUTPUT SELF-CHECK (MANDATORY):

Before generating your JSON output, verify:

□ Did I merge based on "functional similarity"? If YES → WRONG, revise!
□ Did I merge based on "same category"? If YES → WRONG, revise!
□ Did I merge based on "listed together"? If YES → WRONG, revise!
□ For each group: Do all members truly refer to the SAME entity?
□ For multi-valued relations: Did I default to KEEP SEPARATE?
□ Rationale and members array: Are they consistent?
□ If rationale says "same entity", are they in the same members array?
□ If rationale says "different entities", are they in different groups?
□ Have I checked all three tests (Identity, Substitution, Information Loss)?

=============================================================================

Now proceed with your analysis and output.
"""


def build_principle_based_prompt(
    head: str,
    relation: str,
    head_context_lines: list[str],
    batch_entries: list[dict],
) -> str:
    """
    构建完全基于原则的语义去重prompt
    
    特点：
    1. 不使用任何具体领域的案例
    2. 使用抽象占位符
    3. 关注原则和测试方法
    4. 避免过度拟合特定案例
    """
    
    # 关系类型分析（基于模式，不基于具体案例）
    multi_valued_patterns = {
        # 解决方案类
        "solution", "approach", "method", "technique", "way", "means",
        "解决", "方案", "方法", "技术", "手段", "途径",
        
        # 分类类
        "type", "kind", "category", "class", "classification",
        "类型", "种类", "类别", "分类",
        
        # 包含类
        "include", "comprise", "contain", "consist",
        "包括", "包含", "组成", "构成",
        
        # 步骤类
        "step", "stage", "phase", "procedure", "process",
        "步骤", "阶段", "过程", "程序",
        
        # 原因类
        "cause", "reason", "factor", "contributor",
        "原因", "因素", "致因",
        
        # 表现类
        "manifestation", "presentation", "symptom", "sign", "appearance",
        "表现", "症状", "征象", "特征",
        
        # 组成类
        "component", "part", "element", "constituent",
        "组分", "部分", "成分", "要素"
    }
    
    relation_lower = (relation or "").lower()
    is_likely_multi_valued = any(pattern in relation_lower for pattern in multi_valued_patterns)
    
    if is_likely_multi_valued:
        relation_warning = (
            f"⚠️ ALERT: The relation '{relation}' appears to be MULTI-VALUED.\n"
            f"\n"
            f"This means: Head_Entity can have MULTIPLE DIFFERENT tail entities.\n"
            f"\n"
            f"Implication:\n"
            f"  • Each tail likely represents a DIFFERENT entity (different solution/method/type)\n"
            f"  • Only merge if tails are SYNONYMS (different names for SAME thing)\n"
            f"  • Default strategy: KEEP SEPARATE unless clearly coreferent\n"
            f"\n"
            f"Test: Can both statements be true simultaneously?\n"
            f"  • '{head} --{relation}--> Tail_1' AND '{head} --{relation}--> Tail_2'\n"
            f"  • If YES (both can be true) → Likely DIFFERENT entities\n"
            f"  • If NO (contradiction) → Possibly SAME entity\n"
        )
    else:
        relation_warning = (
            f"Relation: '{relation}'\n"
            f"\n"
            f"Carefully analyze whether this relation typically connects to:\n"
            f"  • Single value (one-to-one mapping) → More likely to merge synonyms\n"
            f"  • Multiple values (one-to-many mapping) → More likely distinct entities\n"
        )
    
    # 构建简化的candidate列表
    candidate_lines = []
    for idx, entry in enumerate(batch_entries, start=1):
        description = entry.get("description", "[NO DESCRIPTION]")
        chunk_id = entry.get("chunk_id", "unknown")
        schema_type = entry.get("schema_type", "")
        
        # 简洁格式，避免冗余
        type_info = f", type: {schema_type}" if schema_type else ""
        candidate_lines.append(f"[{idx}] {description} (source: {chunk_id}{type_info})")
    
    candidates_text = "\n".join(candidate_lines) if candidate_lines else "[No candidates provided]"
    
    # 构建共享context（只出现一次）
    head_context_text = "\n".join(head_context_lines) if head_context_lines else "(No context available)"
    
    return PRINCIPLE_BASED_SEMANTIC_DEDUP_PROMPT.format(
        head=head or "[UNKNOWN_HEAD]",
        relation=relation or "[UNKNOWN_RELATION]",
        relation_warning=relation_warning,
        head_context=head_context_text,
        candidates=candidates_text,
    )


# ============================================================================
# 测试：验证prompt的通用性
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("测试：基于原则的Prompt（无具体案例）")
    print("=" * 80)
    print()
    
    # 测试案例1: 药物（完全不同的领域）
    test1_head = "高血压"
    test1_relation = "治疗药物"
    test1_contexts = ["- 高血压可通过多种药物治疗..."]
    test1_entries = [
        {"description": "阿司匹林", "chunk_id": "chunk1", "schema_type": "药物"},
        {"description": "Aspirin", "chunk_id": "chunk1", "schema_type": "药物"},
        {"description": "布洛芬", "chunk_id": "chunk2", "schema_type": "药物"},
    ]
    
    prompt1 = build_principle_based_prompt(test1_head, test1_relation, test1_contexts, test1_entries)
    print("【测试1：药物领域】")
    print("预期：阿司匹林和Aspirin合并（同一药物不同语言），布洛芬独立")
    print()
    print(prompt1[:1500])  # 只打印前部分
    print("\n... (省略中间部分) ...\n")
    
    print("=" * 80)
    print()
    
    # 测试案例2: 地理位置（又一个不同领域）
    test2_head = "旅游目的地"
    test2_relation = "包括"
    test2_contexts = ["- 该地区包含多个著名景点..."]
    test2_entries = [
        {"description": "景点A", "chunk_id": "chunk1", "schema_type": "地点"},
        {"description": "景点B", "chunk_id": "chunk2", "schema_type": "地点"},
        {"description": "景点C", "chunk_id": "chunk3", "schema_type": "地点"},
    ]
    
    prompt2 = build_principle_based_prompt(test2_head, test2_relation, test2_contexts, test2_entries)
    print("【测试2：地理位置】")
    print("预期：三个景点都独立（都是不同的地点）")
    print()
    print("关系类型分析部分：")
    # 提取relation_warning部分
    lines = prompt2.split('\n')
    for i, line in enumerate(lines):
        if 'RELATION TYPE ANALYSIS' in line:
            print('\n'.join(lines[i:i+15]))
            break
    
    print("\n" + "=" * 80)
    print("\n✓ Prompt设计完全基于原则，不依赖特定案例")
    print("✓ 可以泛化到任何领域：医学、地理、技术、化学等")
    print("✓ 重点在判断方法，不是记忆答案")
