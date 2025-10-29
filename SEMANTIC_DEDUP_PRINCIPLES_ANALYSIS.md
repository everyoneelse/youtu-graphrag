# Semantic Dedup Prompt 优秀原则分析

## 1. 核心发现

Tail dedup prompt 有以下优秀设计，值得 head dedup 借鉴：

### ✅ **FUNDAMENTAL PRINCIPLE** - 基础原则清晰
```
COREFERENCE requires REFERENTIAL IDENTITY: 
Two expressions must denote the exact same referent.

- MERGE: 'Entity_A' and 'Entity_A_alias' → same referent
- DO NOT MERGE: 'Entity_X' and 'Entity_Y' → different referents
```

### ⚠️ **CRITICAL DISTINCTION** - 关键区分（非常重要！）
```
CRITICAL DISTINCTION - Relation Satisfaction vs Entity Identity:

⚠️ If multiple tails all satisfy relation R with head H, 
   this does NOT make them coreferent.

Each tail can be a DIFFERENT entity that happens to satisfy the SAME relation.

Formal logic: (H,R,X) ∧ (H,R,Y) ↛ X=Y
(relation satisfaction does not imply entity identity)
```

**这个原则对 head dedup 同样适用：**
- 两个 entity 有相似的关系模式，不代表它们是同一实体
- 例如：两个人都"工作于"某大学，不代表他们是同一个人

### ✅ **MERGE CONDITIONS** - 明确的合并条件

```
MERGE CONDITIONS - ALL must hold:

1. REFERENT TEST: Do the two tails refer to exactly the same entity?
   • Same entity, different names → MERGE
   • Different entities → KEEP SEPARATE

2. SUBSTITUTION TEST: Can you replace one with the other in ALL contexts?
   • If substitution changes meaning → KEEP SEPARATE
   • If substitution preserves meaning → MERGE

3. EQUIVALENCE CLASS: After merging, all members must denote the SAME entity.
   • Do NOT create groups containing multiple distinct entities
```

### ❌ **PROHIBITED MERGE REASONS** - 禁止理由列表（非常清晰！）

```
PROHIBITED MERGE REASONS (NOT valid reasons to merge):

✗ Shared relation: "Both satisfy R with H" → NOT sufficient
✗ Semantic similarity: "X and Y are similar/related" → similarity ≠ identity
✗ Same category: "Both are type T" → category membership ≠ identity
✗ Co-occurrence: "X and Y appear together" → proximity ≠ coreference
✗ Functional relationship: "X causes/affects Y" → relationship ≠ identity
✗ Shared properties: "X and Y have property P" → sharing ≠ identity
✗ Part of same set: "X, Y ∈ Set_S" → set membership ≠ identity
```

### 🔍 **MULTI-VALUED RELATIONS** - 多值关系说明

```
MULTI-VALUED RELATIONS:

Many relations map one head to MULTIPLE distinct tail entities.
Each tail is a separate instance.

Pattern: If H has relation R to {T1, T2, ..., Tn}, 
         each Ti is typically a DIFFERENT entity.

Only merge Ti and Tj if they are different names for the SAME entity,
not just because both satisfy R.
```

### 📋 **DECISION PROCEDURE** - 简洁的决策流程

```
DECISION PROCEDURE:

For each pair of tails (Ti, Tj):
  1. Ask: "Do Ti and Tj refer to the same entity?" 
     (not "Are they related?")
  2. Apply SUBSTITUTION TEST: Would swapping them change the information?
  3. If uncertain → KEEP SEPARATE (conservative principle)
```

### 🛡️ **CONSERVATIVE PRINCIPLE** - 清晰表述

```
CONSERVATIVE PRINCIPLE:

False splits (keeping coreferent entities separate) 
< 
False merges (merging distinct entities)

When in doubt, preserve distinctions.
```

## 2. 对比当前 Head Dedup Prompt 的不足

| 方面 | Tail Dedup (semantic_dedup) | Head Dedup (当前) | 需要改进 |
|-----|---------------------------|-----------------|---------|
| **CRITICAL DISTINCTION** | ✅ 明确警告关系满足≠实体同一 | ❌ 缺失 | **需要添加** |
| **MERGE CONDITIONS** | ✅ 3个明确的必须条件 | ⚠️ 分散在多处 | **需要集中** |
| **PROHIBITED MERGE REASONS** | ✅ 7个清晰的禁止理由 | ⚠️ 仅4个，不够醒目 | **需要扩展** |
| **DECISION PROCEDURE** | ✅ 3步简洁流程 | ⚠️ 5步较复杂 | **可简化** |
| **CONSERVATIVE PRINCIPLE** | ✅ 明确的不等式表达 | ✅ 已有 | 保持 |
| **MULTI-VALUED RELATIONS** | ✅ 专门说明 | ❌ 缺失 | **可考虑添加** |

## 3. 建议改进 Head Dedup Prompt

### 改进点 1: 添加 CRITICAL DISTINCTION

```
CRITICAL DISTINCTION - Similar Relations ≠ Same Entity:

⚠️ If two entities have similar graph relationships or appear in 
   similar contexts, this does NOT make them the same entity.

Two entities can have similar patterns but be DIFFERENT entities.

Example:
- Entity_1: "Professor Zhang", works_at → Tsinghua, age → 45
- Entity_2: "Professor Zhang", works_at → Peking University, age → 50
→ Similar patterns, but DIFFERENT people with the same name!

Formal: Similar(E1, E2) ↛ E1 = E2
(relation pattern similarity does not imply entity identity)
```

### 改进点 2: 重构 MERGE CONDITIONS

```
MERGE CONDITIONS - ALL must hold:

1. REFERENT TEST: Do the two entities refer to exactly the same object?
   Using BOTH source text AND graph relationships:
   • Same object, different names → MERGE (e.g., "UN" = "United Nations")
   • Different objects → KEEP SEPARATE (even if highly related)

2. SUBSTITUTION TEST: Can you replace one with the other in ALL contexts?
   Using BOTH source text AND graph relationships:
   • If substitution changes meaning/information → KEEP SEPARATE
   • If substitution preserves meaning → MERGE

3. NO CONTRADICTIONS: The evidence must be consistent.
   • If ANY contradiction in source text OR graph → KEEP SEPARATE
   • Hierarchical relations (owns/contains) → KEEP SEPARATE
   • Conflicting attributes (different age/type) → KEEP SEPARATE

4. EQUIVALENCE CLASS: After merging, both entities denote the SAME object.
   • Do NOT merge if they represent different instances/aspects
```

### 改进点 3: 扩展 PROHIBITED MERGE REASONS

```
PROHIBITED MERGE REASONS (NOT valid reasons to merge):

✗ Similar names: "John Smith" vs "John Smith Jr." → different persons
✗ Same category: "Both are universities" → category ≠ identity
✗ Similar relations: "Both have relation R" → pattern ≠ identity
✗ Related entities: "Apple Inc." vs "Apple Store" → company ≠ subsidiary
✗ Co-occurrence: "Appear in same context" → proximity ≠ coreference
✗ Shared properties: "Both have property P" → sharing ≠ identity
✗ Same community: "Both in community C" → membership ≠ identity
✗ Partial match: "Some relations match" → partial ≠ complete identity
```

### 改进点 4: 简化 DECISION PROCEDURE

```
DECISION PROCEDURE (using source text + graph together):

For Entity 1 and Entity 2:
  1. Ask: "Do they refer to the same real-world object?" 
     (not just "Are they similar?")
  2. Check for ANY contradictions in source text OR graph
     → If contradictions found → KEEP SEPARATE
  3. Apply SUBSTITUTION TEST in ALL contexts
     → If substitution changes information → KEEP SEPARATE
  4. If uncertain → KEEP SEPARATE (conservative principle)
```

### 改进点 5: 添加 SIMILAR ENTITIES 说明

```
SIMILAR BUT DISTINCT ENTITIES:

Many entities may have similar characteristics but be DIFFERENT entities.

Pattern: If E1 and E2 have similar relations {R1, R2, ..., Rn},
         they might be different instances of the same type.

Examples:
- Multiple "张三" (different people with same name)
- Multiple "Apple Store" locations (different branches)
- Multiple "Professor" (different persons with same title)

Only merge if they are different names for the EXACT SAME entity,
not just because they have similar patterns.
```

## 4. 完整的改进后 Prompt 结构

```
TASK: Determine if two entities refer to the SAME real-world object...

Entity 1 (ID: {entity_1_id}): {entity_1_desc}
Graph relationships: {graph_context_1}
Source text: {chunk_context_1}

Entity 2 (ID: {entity_2_id}): {entity_2_desc}
Graph relationships: {graph_context_2}
Source text: {chunk_context_2}

═══════════════════════════════════════════════════════════

FUNDAMENTAL PRINCIPLE:
COREFERENCE requires REFERENTIAL IDENTITY: 
Two entities must denote the exact same real-world object.
- MERGE: Different names for ONE object
- DO NOT MERGE: Two DIFFERENT objects

═══════════════════════════════════════════════════════════

CRITICAL DISTINCTION - Similar Relations ≠ Same Entity:
⚠️ Similar graph patterns do NOT make entities coreferent!
[详细说明...]

═══════════════════════════════════════════════════════════

MERGE CONDITIONS - ALL must hold:
1. REFERENT TEST: [...]
2. SUBSTITUTION TEST: [...]
3. NO CONTRADICTIONS: [...]
4. EQUIVALENCE CLASS: [...]

═══════════════════════════════════════════════════════════

PROHIBITED MERGE REASONS:
✗ Similar names
✗ Same category
✗ Similar relations
✗ Related entities
✗ Co-occurrence
✗ Shared properties
✗ Same community
✗ Partial match

═══════════════════════════════════════════════════════════

DECISION PROCEDURE:
1. Ask: Same object?
2. Check: Any contradictions?
3. Test: Substitution preserves meaning?
4. If uncertain → KEEP SEPARATE

═══════════════════════════════════════════════════════════

CONSERVATIVE PRINCIPLE:
False splits < False merges
When in doubt, preserve distinctions.

═══════════════════════════════════════════════════════════

REPRESENTATIVE SELECTION (only if coreferent):
[选择标准...]

═══════════════════════════════════════════════════════════

OUTPUT FORMAT:
{
  "is_coreferent": true/false,
  "preferred_representative": "entity_X" or null,
  "rationale": "UNIFIED analysis..."
}
```

## 5. 关键改进点总结

1. **添加 CRITICAL DISTINCTION** ⚠️ - 警告相似性≠同一性
2. **明确 MERGE CONDITIONS** - 4个必须同时满足的条件
3. **扩展 PROHIBITED REASONS** - 8个清晰的禁止理由（用✗标记）
4. **简化 DECISION PROCEDURE** - 4步简洁流程
5. **添加 SIMILAR ENTITIES** - 说明相似但不同的实体模式
6. **保持 CONSERVATIVE PRINCIPLE** - 明确的不等式表达
7. **保持 UNIFIED REASONING** - 综合使用上下文和图关系

这些改进将使 prompt 更加清晰、严谨、易于遵循！
