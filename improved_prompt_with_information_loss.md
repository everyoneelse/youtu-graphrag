# 信息损失感知的Head Dedup Prompt改进方案

## 核心问题

当前Prompt的问题：
- 只判断"是否指向同一对象"
- 没有评估"合并是否损失信息"
- 没有区分"完全等价" vs "宽泛表达" vs "不同层次"

## 改进方案：三级判断框架

### Level 1: Referential Identity（指称判断）

```
Do the two entities refer to the SAME real-world object/concept?
```

### Level 2: Information Equivalence（信息等价判断）- 新增！

```
If they refer to the same object, are they INFORMATIONALLY EQUIVALENT?

Check for information asymmetry:

1. TERM SPECIFICITY:
   Q: Is one term more specific/precise than the other?
   Example:
   - "增加读出带宽" (specific: which bandwidth is clear)
   - "加大带宽" (vague: which bandwidth is unclear)
   
   If YES → Information asymmetry exists

2. CONTEXT DETAIL LEVEL:
   Q: Do they appear in contexts with different detail levels?
   Example:
   - Entity A: appears with mechanism explanation
   - Entity B: appears in simple solution listings
   
   If YES → Different knowledge granularity

3. SYMMETRIC SUBSTITUTION TEST:
   Q: Is substitution information-preserving in BOTH directions?
   
   Test A→B: "通过[增加读出带宽]解决伪影"
           → "通过[加大带宽]解决伪影"
           Loss? Precision lost ✗
   
   Test B→A: "解决方法：[加大带宽]"
           → "解决方法：[增加读出带宽]"
           Loss? No loss, adds precision ✓
   
   If ASYMMETRIC → Not fully equivalent

4. FORMALITY/REGISTER DIFFERENCE:
   Q: Do they serve different audiences or contexts?
   Example:
   - Entity A: technical documentation language
   - Entity B: colloquial or simplified language
   
   If YES → Audience-specific expressions

5. RELATIONSHIP PATTERN DIFFERENCE:
   Q: Do they have significantly different relationships in the graph?
   Example:
   - Entity A: rich technical relationships (parameters, mechanisms)
   - Entity B: simple solution relationships
   
   If YES → Structural information difference
```

### Level 3: Merge Decision（合并决策）

```
Based on information equivalence assessment:

┌─────────────────────────────────────────────────────────────┐
│ Scenario 1: FULL EQUIVALENCE (0-1 concerns)                │
│                                                             │
│ - Same referent ✓                                          │
│ - No information asymmetry                                  │
│ - Symmetric substitution                                    │
│ - No specificity/detail/audience difference                │
│                                                             │
│ → DECISION: TRUE MERGE (complete deduplication)            │
│ → OUTPUT: is_coreferent=true, merge_type="full_merge"     │
│                                                             │
│ Example:                                                    │
│   - "UN" vs "United Nations" (just abbreviation)           │
│   - "MRI扫描" vs "磁共振成像扫描" (同义词，无精确度差异)      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Scenario 2: PARTIAL EQUIVALENCE (2-3 concerns)             │
│                                                             │
│ - Same referent ✓                                          │
│ - BUT: Specificity OR detail-level OR audience difference  │
│ - Asymmetric substitution                                   │
│                                                             │
│ → DECISION: ESTABLISH ALIAS/BROADER RELATION               │
│ → OUTPUT: is_coreferent=true, merge_type="alias_relation" │
│                                                             │
│ Preserve BOTH entities, but link them:                     │
│   - Keep the more specific one as primary                  │
│   - Mark the vague one as "broader_term" or "colloquial_form" │
│   - Maintain information hierarchy                         │
│                                                             │
│ Example:                                                    │
│   - "增加读出带宽" (precise) vs "加大带宽" (vague)           │
│   - "化学位移伪影" (technical) vs "图像模糊" (colloquial)     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Scenario 3: DIFFERENT ENTITIES (4+ concerns OR different   │
│              referents)                                     │
│                                                             │
│ - Different referents, OR                                   │
│ - Same referent but significant information asymmetry       │
│                                                             │
│ → DECISION: KEEP SEPARATE                                  │
│ → OUTPUT: is_coreferent=false                              │
│                                                             │
│ Example:                                                    │
│   - "提高带宽(流动伪影)" vs "提高带宽(化学位移伪影)"          │
│   - "Apple Inc." vs "Apple Store"                          │
└─────────────────────────────────────────────────────────────┘
```

## 新的输出格式

```json
{
  "is_coreferent": true/false,
  "merge_type": "full_merge" | "alias_relation" | "keep_separate",
  "preferred_representative": "entity_XXX" | null,
  "information_asymmetry": {
    "specificity_difference": true/false,
    "detail_level_difference": true/false,
    "substitution_symmetric": true/false,
    "formality_difference": true/false,
    "relationship_difference": true/false
  },
  "rationale": "Unified analysis explaining referential identity, information equivalence assessment, and merge decision"
}
```

## 完整的Prompt模板

```
You are an expert in knowledge graph entity resolution with focus on INFORMATION PRESERVATION.

TASK: Determine if two entities refer to the same object AND whether they should be fully merged or kept as related variants.

Entity 1 (ID: {entity_1_id}): {entity_1_desc}
Graph relationships: {graph_context_1}
Source text: {chunk_context_1}

Entity 2 (ID: {entity_2_id}): {entity_2_desc}
Graph relationships: {graph_context_2}
Source text: {chunk_context_2}

═══════════════════════════════════════════════════════════

STEP 1: REFERENTIAL IDENTITY CHECK

Do these two entities refer to the EXACT SAME real-world object/concept?

Apply:
- REFERENT TEST: Same object?
- SUBSTITUTION TEST: Can replace in contexts?
- CONTRADICTION CHECK: Any conflicting evidence?

═══════════════════════════════════════════════════════════

STEP 2: INFORMATION EQUIVALENCE ASSESSMENT (Only if Step 1 = YES)

Even if they refer to the same object, assess INFORMATION ASYMMETRY:

1. SPECIFICITY: Is one more precise than the other?
   - Check if one term is unambiguous while other is vague
   - Example: "读出带宽" (clear) vs "带宽" (ambiguous)

2. DETAIL LEVEL: Different context granularity?
   - Check source texts: detailed explanation vs simple listing?
   - Check relationships: rich technical links vs simple links?

3. SUBSTITUTION SYMMETRY: Information-preserving in BOTH directions?
   - Test A→B: Any precision loss?
   - Test B→A: Any precision loss?
   - ONLY if both directions preserve info → fully equivalent

4. REGISTER/FORMALITY: Different audiences?
   - Technical vs colloquial language?
   - Academic vs practical contexts?

5. STRUCTURAL: Different relationship patterns?
   - One has mechanism explanations, other doesn't?
   - Different community memberships indicating different usage contexts?

Count concerns (1 = YES to any check above)

═══════════════════════════════════════════════════════════

STEP 3: MERGE DECISION

Based on assessment:

IF referentially different → 
   merge_type = "keep_separate"
   
IF same referent + 0-1 concerns → 
   merge_type = "full_merge"
   Choose more formal/complete as representative
   
IF same referent + 2-3 concerns →
   merge_type = "alias_relation"
   Choose more specific/formal as primary
   Explanation: Preserve both for information hierarchy
   
IF same referent + 4-5 concerns →
   merge_type = "keep_separate"
   Explanation: Too much information asymmetry, treat as related but distinct

═══════════════════════════════════════════════════════════

CRITICAL PRINCIPLES:

1. INFORMATION PRESERVATION over simplification
   - Don't merge if it loses precision, detail level, or audience-specific knowledge

2. CONSERVATIVE when uncertain
   - If in doubt about information loss → prefer "alias_relation" over "full_merge"

3. ASYMMETRIC SUBSTITUTION = NOT EQUIVALENT
   - If A→B loses info but B→A doesn't → they have different specificity levels

4. DIFFERENT DETAIL LEVELS = VALUABLE HIERARCHY
   - Detailed explanation vs simple listing = different knowledge granularities worth preserving

═══════════════════════════════════════════════════════════

OUTPUT FORMAT (strict JSON):

{
  "is_coreferent": true/false,
  "merge_type": "full_merge" | "alias_relation" | "keep_separate",
  "preferred_representative": "{entity_1_id}" or "{entity_2_id}" or null,
  "information_asymmetry": {
    "specificity_difference": true/false,
    "detail_level_difference": true/false,
    "substitution_symmetric": true/false,
    "formality_difference": true/false,
    "relationship_difference": true/false
  },
  "rationale": "Unified analysis covering: (1) Referential identity check with evidence, (2) Information asymmetry assessment with specific findings for each dimension, (3) Merge decision reasoning based on concern count and information preservation principle"
}

IMPORTANT:
- Set merge_type based on concern count
- If merge_type = "alias_relation", explain what information would be lost by full merge
- Prioritize information preservation over graph simplicity
```

## 实施建议

### 代码层面修改

```python
def _parse_coreference_response_v3(self, response: str) -> dict:
    """
    解析新的三级判断结果
    """
    parsed = json_repair.loads(response)
    
    return {
        "is_coreferent": parsed.get("is_coreferent", False),
        "merge_type": parsed.get("merge_type", "keep_separate"),
        "preferred_representative": parsed.get("preferred_representative"),
        "information_asymmetry": parsed.get("information_asymmetry", {}),
        "rationale": parsed.get("rationale", "")
    }

def _apply_merge_decisions_v3(self, merge_results):
    """
    根据merge_type分别处理
    """
    full_merges = {}
    alias_relations = {}
    
    for result in merge_results:
        merge_type = result["merge_type"]
        
        if merge_type == "full_merge":
            # 完全合并：删除duplicate，转移所有关系
            full_merges[result["duplicate"]] = result["canonical"]
            
        elif merge_type == "alias_relation":
            # 别名关系：保留两个实体，但建立链接
            alias_relations[result["duplicate"]] = {
                "primary": result["canonical"],
                "relation_type": "broader_term_of",  # 或 "less_specific_form_of"
                "asymmetry": result["information_asymmetry"]
            }
            # 不删除duplicate，只添加关系
            self.graph.add_edge(
                result["duplicate"],
                result["canonical"],
                label="less_specific_than",
                metadata=result["information_asymmetry"]
            )
    
    return full_merges, alias_relations
```

### 查询层面支持

```python
def query_with_alias_expansion(self, entity_name, include_aliases=True):
    """
    查询时可以选择是否包含别名
    """
    exact_match = self.find_entity(entity_name)
    
    if not include_aliases:
        return [exact_match]
    
    # 查找所有别名和精确形式
    aliases = self.graph.neighbors(
        exact_match, 
        edge_filter={"label": "less_specific_than"}
    )
    
    more_specific = self.graph.predecessors(
        exact_match,
        edge_filter={"label": "less_specific_than"}
    )
    
    return [exact_match] + list(aliases) + list(more_specific)
```

## 对entity_565 vs 666的重新评估

应用新框架：

```yaml
STEP 1: Referential Identity
  Result: ✓ YES (both refer to bandwidth adjustment)

STEP 2: Information Equivalence
  1. Specificity: ✗ 565 precise, 666 vague
  2. Detail level: ✗ 565 has mechanism, 666 is listing
  3. Substitution symmetric: ✗ Asymmetric
  4. Formality: ✗ Likely different audiences
  5. Structural: ? Need to check
  
  Concerns: 3-4 out of 5

STEP 3: Merge Decision
  Concerns = 3-4 → merge_type = "alias_relation"
  
  Output:
  {
    "is_coreferent": true,
    "merge_type": "alias_relation",  # NOT full_merge!
    "preferred_representative": "entity_565",
    "information_asymmetry": {
      "specificity_difference": true,
      "detail_level_difference": true,
      "substitution_symmetric": false,
      "formality_difference": true,
      "relationship_difference": "unknown"
    },
    "rationale": "两者指向同一技术操作，但存在显著的信息不对称：565是精确的技术术语'增加读出带宽'，出现在详细的机制解释中；666是模糊的表达'加大带宽'，出现在简单的解决方案列举中。替换测试显示非对称性：565→666会损失精确性，666→565不会损失但会增加精确性。建议保留两个实体并建立'666是565的宽泛表达'关系，以保留知识的层次性。"
  }
```

## 总结

你的质疑揭示了当前方法的根本问题：

**❌ 错误：同社区+同场景 = 应该合并**

**✓ 正确：指称相同 + 信息等价 + 无损失 = 应该合并**

新框架的核心：
1. 区分"指向同一对象" vs "完全等价"
2. 评估信息对称性
3. 根据信息损失程度选择：完全合并 vs 别名关系 vs 保持独立
4. 优先保留信息，而非追求简洁性
