# Head Dedup Prompt 修改对比

## 快速对比

| 方面 | 修改前 | 修改后 |
|-----|--------|--------|
| **核心原则** | 分散在 CRITICAL RULES 中 | ✅ 集中在 FUNDAMENTAL PRINCIPLE |
| **CRITICAL DISTINCTION** | ❌ 无 | ✅ 明确警告：相似上下文 ≠ 实体同一性 |
| **类别-实例关系** | ⚠️ 简单提及 | ✅ 专门的 CATEGORY-INSTANCE WARNING |
| **禁止合并理由** | 5 条 | ✅ 9 条（新增 4 条） |
| **DECISION PROCEDURE** | 5 步 | ✅ 5 步（第 2 步新增类别-实例检查） |
| **示例** | 3 个 | ✅ 4 个（新增用户案例） |
| **prompt 长度** | ~3500 字符 | ~5200 字符 |

## 关键改进内容

### 1. FUNDAMENTAL PRINCIPLE（新增）

**修改后：**
```
FUNDAMENTAL PRINCIPLE:
COREFERENCE requires REFERENTIAL IDENTITY: Two entities must denote the exact same referent.
- MERGE: 'Entity_A' and 'Entity_A_alias' → same referent (different names for one thing)
- DO NOT MERGE: 'Entity_X' and 'Entity_Y' → different referents (two distinct things)
```

### 2. CRITICAL DISTINCTION（新增）

**修改后：**
```
CRITICAL DISTINCTION - Similar Context/Relations ≠ Entity Identity:
⚠️  If two entities appear in similar contexts or have similar relations, 
this does NOT make them the same entity.
Each entity can be a DIFFERENT object that happens to appear in SIMILAR contexts.
Formal logic: Similar_Context(X, Y) ↛ X=Y
```

### 3. MERGE CONDITIONS（重构）

**修改前：**
```
1. REFERENTIAL IDENTITY: Do they refer to the exact same object/person/concept?
2. SUBSTITUTION TEST: Can you replace one with the other...
3. TYPE CONSISTENCY: Check entity types/categories
```

**修改后：**
```
MERGE CONDITIONS - ALL must hold:
1. REFERENT TEST: Do the two entities refer to exactly the same object in the real world?
   • Same entity, different names → MERGE (e.g., 'NYC' = 'New York City')
   • Different entities → KEEP SEPARATE (even if highly related)
   • Category vs Instance → KEEP SEPARATE (e.g., "动物" ≠ "老虎", "伪影" ≠ "魔角伪影")

2. SUBSTITUTION TEST: Can you replace one entity with the other in ALL contexts...
3. EQUIVALENCE: After merging, both must denote the SAME single entity.
```

### 4. PROHIBITED MERGE REASONS（扩展）

**修改前（5 条）：**
```
✗ Similar names
✗ Related entities
✗ Same category
✗ Shared relations
✗ Partial overlap
```

**修改后（9 条）：**
```
✗ Semantic similarity
✗ Same category
✗ Shared context
✗ Shared relations
✗ Functional relationship
✗ Shared properties
✗ Category-Instance        ← 新增
✗ Part-Whole               ← 新增
✗ General-Specific         ← 新增
```

### 5. CATEGORY-INSTANCE WARNING（新增）

**修改后：**
```
CATEGORY-INSTANCE WARNING:
If one entity is a GENERAL CATEGORY and the other is a SPECIFIC INSTANCE/TYPE, 
they are DIFFERENT entities.

Examples:
- "伪影" (general: all artifacts) vs "魔角伪影" (specific: magic angle artifact) → DIFFERENT
- "疾病" (category: disease) vs "感冒" (instance: common cold) → DIFFERENT  
- "动物" (category: animal) vs "老虎" (instance: tiger) → DIFFERENT
- "Vehicle" (category) vs "Car" (specific type) → DIFFERENT
```

### 6. DECISION PROCEDURE（增强）

**修改前：**
```
1. Check if names are variations of the same entity
2. Compare their relation patterns
3. Look for contradictions
4. Apply substitution test
5. If uncertain → answer NO
```

**修改后：**
```
1. Ask: "Do they refer to the same entity?" (not "Are they related?")
2. Check: Is one a category and the other an instance/type? → If YES, KEEP SEPARATE  ← 新增
3. Apply SUBSTITUTION TEST: Would swapping them change the information?
4. Check for contradictions in their relations/properties
5. If uncertain → answer NO (conservative principle)
```

### 7. EXAMPLES（新增用户案例）

**修改后新增：**
```
Example 3 - SHOULD NOT MERGE (category vs instance):
Entity 1: "伪影", relations: [member_of→脊柱解剖与诊断, 表现形式为→魔角效应]
Entity 2: "魔角伪影", relations: [has_attribute→定义:肌腱、韧带等...成55°夹角时信号增强, 
                                常见部位或组织为→肌腱]
→ is_coreferent: false, confidence: 0.90
→ Rationale: "伪影" is a GENERAL CATEGORY (all MRI artifacts), "魔角伪影" is a 
SPECIFIC TYPE (magic angle artifact). They are in a category-instance relationship, 
not identity. Cannot substitute one for the other without losing specificity.
```

## 原则对齐

### 与 semantic_dedup 的一致性

| 原则 | semantic_dedup (tail 去重) | head_dedup (修改后) |
|------|---------------------------|-------------------|
| **核心哲学** | REFERENTIAL IDENTITY | ✅ REFERENTIAL IDENTITY |
| **CRITICAL DISTINCTION** | Relation satisfaction ≠ identity | ✅ Similar context ≠ identity |
| **MERGE CONDITIONS** | 3 条（全部必须满足） | ✅ 3 条（全部必须满足） |
| **PROHIBITED REASONS** | 7 条 | ✅ 9 条 |
| **保守原则** | When in doubt, keep separate | ✅ When in doubt, keep separate |
| **SUBSTITUTION TEST** | ✅ | ✅ |
| **示例驱动** | ✅ | ✅ |

## 测试结果

运行 `test_head_dedup_category_instance.py`:

```
✅ Key Principles Check: 9/9 (100%)
✅ Prohibited Reasons Coverage: 9/9 (100%)
✅ Decision Procedure Check: 4/4 (100%)
✅ Examples Check: 4/4 (100%)

✅ ALL CHECKS PASSED!
```

## 预期效果示例

### 案例 1：用户提到的错误

**输入：**
```
Entity 1: "伪影"
- member_of → 脊柱解剖与诊断
- 表现形式为 → 魔角效应

Entity 2: "魔角伪影"
- has_attribute → 定义:肌腱、韧带等...
- 常见部位或组织为 → 肌腱
```

**修改前（错误）：**
```json
{
  "is_coreferent": true,
  "confidence": 1.0,
  "rationale": "两条实体均描述魔角效应相关现象，信息等价..."
}
```

**修改后（正确）：**
```json
{
  "is_coreferent": false,
  "confidence": 0.90,
  "rationale": "'伪影' is a GENERAL CATEGORY (all MRI artifacts), '魔角伪影' is a 
  SPECIFIC TYPE. Category-instance relationship detected. Substitution would change 
  information scope. Conservative principle: KEEP SEPARATE."
}
```

### 案例 2：其他类别-实例关系

**输入：**
```
Entity 1: "疾病"
Entity 2: "感冒"
```

**预期判断：**
```json
{
  "is_coreferent": false,
  "confidence": 0.90,
  "rationale": "'疾病' is a general category encompassing all diseases, '感冒' is a 
  specific instance (common cold). Category-instance relationship. KEEP SEPARATE."
}
```

### 案例 3：仍应合并的情况

**输入：**
```
Entity 1: "魔角伪影"
Entity 2: "魔角效应伪影"
```

**预期判断：**
```json
{
  "is_coreferent": true,
  "confidence": 0.95,
  "rationale": "Both refer to the same specific artifact type (magic angle artifact). 
  '魔角伪影' and '魔角效应伪影' are different linguistic expressions for the same entity. 
  Substitution test passes in both directions. MERGE."
}
```

## 使用方法

### 1. 立即生效

修改已保存在 `config/base_config.yaml`，下次运行 head deduplication 时自动使用新 prompt：

```bash
python offline_semantic_dedup.py \
    --graph output/graphs/demo.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_deduped.json
```

### 2. 删除旧缓存

如果之前保存了中间结果，需要删除：

```bash
rm output/intermediate_results/*.pkl
```

### 3. 监控效果

查看日志中的 rationale，确认：
- 类别-实例关系被正确识别
- 合并决策基于 referential identity 而非 chunk 相似性

## 总结

本次修改的核心：

1. ✅ **强化原则性指导**：明确 "相似性 ≠ 同一性"
2. ✅ **新增类别-实例警告**：专门处理这类常见错误
3. ✅ **扩展禁止理由**：从 5 条扩展到 9 条
4. ✅ **保持一致性**：与 semantic_dedup 使用相同的哲学
5. ✅ **原则驱动**：避免 case-by-case 修改，建立通用规则

这使得 head_dedup 不再过度依赖 chunk 内容的相似性，而是基于严格的 **referential identity** 原则进行判断。

---

**修改日期**: 2025-10-29  
**测试状态**: ✅ 全部通过  
**文档**: `HEAD_DEDUP_PROMPT_SEMANTIC_IMPROVEMENT.md`
