# 改进的Semantic Dedup Prompt设计

## 改进策略

### 1. Context优化 - 消除冗余
```
结构变更：
原来：
  - Head And Tail contexts: [列出所有chunks]
  - Candidate tails:
    - [1] Tail: XXX
        Contexts: [重复chunk内容]
    - [2] Tail: YYY
        Contexts: [重复chunk内容]

改为：
  - Shared contexts: [所有相关chunks，只出现一次]
  - Candidate tails:
    - [1] XXX (from chunk_id: ABC)
    - [2] YYY (from chunk_id: DEF)
```

### 2. 原则重组 - 突出关键点

**将最容易出错的原则放在最前面，用醒目格式：**

```
🚨 CRITICAL: FUNCTIONAL SIMILARITY ≠ ENTITY IDENTITY 🚨

WRONG REASONING (常见错误):
❌ "Both are methods to solve X" → MERGE
❌ "Both achieve the same goal" → MERGE  
❌ "Both belong to category Y" → MERGE
❌ "Both have property Z" → MERGE

CORRECT REASONING:
✓ "Both are different names for THE SAME method" → MERGE
✓ "Method_A = Method_A_alias" → MERGE

Example:
- "治疗感冒的方法" → {阿司匹林, 布洛芬, 对乙酰氨基酚}
  → All achieve same goal (reduce fever)
  → But they are THREE DIFFERENT drugs
  → DO NOT MERGE

- "New York" and "NYC" and "纽约"
  → Different names for ONE city
  → MERGE
```

### 3. 多值关系特别警告

```
⚠️ MULTI-VALUED RELATIONS - SPECIAL ATTENTION ⚠️

Relations that typically have MULTIPLE distinct values:
- "解决方案" / "solution" / "approach"
- "方法" / "method" / "technique"  
- "表现形式" / "manifestation" / "presentation"
- "类型" / "type" / "category"
- "包括" / "includes" / "comprises"
- "步骤" / "step" / "procedure"

For these relations:
- Default assumption: Each tail is a DIFFERENT entity
- Only merge if they are SYNONYMS (same name in different words)
- Do NOT merge based on functional similarity

Quick test: If I say "Use method A", can I randomly replace it with "Use method B"?
- If NO → They are different entities → DO NOT MERGE
- If YES without any information loss → They might be coreferent → Consider merging
```

### 4. 输出一致性检查步骤

**在输出要求前添加：**

```
BEFORE GENERATING OUTPUT - MANDATORY SELF-CHECK:

Step 1: Review your analysis for each pair
Step 2: For each group you want to create:
        - List the member indices you identified
        - Verify they refer to THE SAME entity (not just similar entities)
Step 3: Generate JSON with members array
Step 4: Write rationale that matches your members array
        - If rationale says "should be merged", they MUST be in same group
        - If rationale says "different entities", they MUST be in different groups
Step 5: Final check: Read your rationale, check your members array matches it

CRITICAL: Your rationale must EXPLAIN why the members in THIS group are coreferent.
Do NOT say "should merge with X" if X is not in this group's members.
```

### 5. 简化输出格式 - 使用编号引用

```
OUTPUT FORMAT REQUIREMENTS:

1. Use 1-based indexing consistently: [1], [2], [3], etc.
2. In your rationale, reference candidates by their numbers: "[1] and [2]"
3. Your members array should use the SAME numbers: "members": [1, 2]
4. Each rationale should be self-contained:
   - Describe what entity this group represents
   - Explain why members are different expressions of the same entity
   - If comparing with other candidates, explain why they are DIFFERENT

Example:
{
  "groups": [
    {
      "members": [1, 3],
      "representative": 1,
      "rationale": "[1] and [3] both refer to the same city - New York, just using different names (full name vs abbreviation). This is one geographic entity with two linguistic expressions."
    },
    {
      "members": [2],
      "representative": 2,
      "rationale": "[2] refers to Los Angeles, which is a different city from [1]/[3]. This is a distinct geographic entity."
    }
  ]
}
```

## 完整改进后的Prompt模板

```python
IMPROVED_SEMANTIC_DEDUP_PROMPT = """You are a knowledge graph curation assistant performing entity deduplication.

🚨 CRITICAL: FUNCTIONAL SIMILARITY ≠ ENTITY IDENTITY 🚨

Common WRONG reasoning that you must AVOID:
❌ "Both are methods/solutions/approaches for X" → DO NOT MERGE
❌ "Both achieve the same goal/function" → DO NOT MERGE
❌ "Both belong to the same category" → DO NOT MERGE
❌ "Both can solve problem Y" → DO NOT MERGE

Correct reasoning:
✓ "Both are different names for THE SAME specific entity" → MERGE
✓ "'Entity_A' and 'Entity_A_alias' refer to the same thing" → MERGE

=======================================================================

HEAD ENTITY: {head}
RELATION: {relation}

⚠️ RELATION TYPE ANALYSIS:
{relation_analysis}

SHARED CONTEXTS:
{shared_contexts}

CANDIDATE TAILS:
{candidates}

=======================================================================

TASK: Identify which tails are COREFERENT (refer to the exact same entity).

DECISION PROCESS FOR EACH PAIR:

1. IDENTITY TEST: Do they refer to the same entity in the real world?
   - "阿司匹林" vs "布洛芬" → NO (two different drugs)
   - "New York" vs "NYC" → YES (same city, different names)

2. SUBSTITUTION TEST: Can I replace one with the other without changing facts?
   - "本研究使用ECG门控" → "本研究使用指脉门控" = Changes the fact! → NOT coreferent
   - "New York is large" → "NYC is large" = Same fact! → Coreferent

3. INFORMATION TEST: Do they convey different information?
   - If YES → NOT coreferent (they are complementary, keep separate)
   - If NO → Possibly coreferent (redundant, check if same entity)

=======================================================================

BEFORE GENERATING OUTPUT - SELF-CHECK:

□ Have I identified which tails refer to the SAME entity? (not just similar)
□ For each group, are all members truly SYNONYMOUS?
□ Have I avoided merging based on functional similarity?
□ Does my rationale match my members array?
□ If I say "should merge" in rationale, are they in the same members array?

=======================================================================

OUTPUT FORMAT:

{{
  "groups": [
    {{
      "members": [1, 2],
      "representative": 1,
      "rationale": "Explain why [1] and [2] refer to the SAME entity (use numbers [1], [2], etc. consistently)"
    }},
    {{
      "members": [3],
      "representative": 3,
      "rationale": "Explain what entity [3] represents and why it's DIFFERENT from others"
    }}
  ]
}}

Remember: 
- Every candidate [1], [2], [3], ... must appear in exactly one group
- Use same numbering in rationale and members array
- When in doubt, KEEP SEPARATE (better to split than incorrectly merge)
"""

# 关系类型分析模板
def get_relation_analysis(relation: str) -> str:
    multi_valued_keywords = {
        "解决方案", "solution", "method", "方法", "技术", "technique",
        "表现", "manifestation", "type", "类型", "包括", "include",
        "步骤", "step", "特征", "feature", "原因", "cause"
    }
    
    relation_lower = relation.lower() if relation else ""
    is_multi_valued = any(kw in relation_lower for kw in multi_valued_keywords)
    
    if is_multi_valued:
        return (
            f"⚠️ '{relation}' is likely a MULTI-VALUED relation.\n"
            "   → One head can have MULTIPLE different tail entities\n"
            "   → Each tail is typically a DIFFERENT entity/method/solution\n"
            "   → Only merge if tails are SYNONYMS (different names for same thing)\n"
            "   → Default: KEEP SEPARATE unless clearly coreferent"
        )
    else:
        return (
            f"The relation '{relation}' may have multiple values.\n"
            "   → Carefully check if tails are synonyms or distinct entities"
        )
```

## 实施建议

1. **短期改进（立即可做）：**
   - 在现有prompt开头添加"🚨 CRITICAL"警告
   - 添加自检步骤
   - 添加关系类型分析

2. **中期改进（需要代码修改）：**
   - 优化context结构，消除冗余
   - 自动检测关系类型并给出针对性提示

3. **长期改进（更大改动）：**
   - 实现两阶段输出：先输出分析，再输出JSON
   - 添加自动验证：检查rationale和members一致性
   - 对多值关系使用更保守的策略（默认不合并）
