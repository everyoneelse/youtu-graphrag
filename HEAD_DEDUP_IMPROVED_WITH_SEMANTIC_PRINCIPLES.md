# Head Dedup Prompt 改进：借鉴 Semantic Dedup 原则

## 修改日期
2025-10-29

## 改进背景

在完成"综合判断"改进后，进一步参考了 `semantic_dedup` (tail去重) 的优秀设计原则，对 head dedup prompt 进行了第二轮优化。

## Semantic Dedup 的优秀设计

Tail dedup prompt 有以下值得借鉴的特点：

### 1. ⚠️ **CRITICAL DISTINCTION** （关键警告）

```
⚠️ If multiple tails all satisfy relation R with head H, 
   this does NOT make them coreferent.

Formal logic: (H,R,X) ∧ (H,R,Y) ↛ X=Y
(relation satisfaction does not imply entity identity)
```

**启示**：仅仅因为两个实体有相似的关系模式，不代表它们是同一实体。

### 2. ✅ **MERGE CONDITIONS** （明确的合并条件）

将判断标准明确列为"ALL must hold"的4个条件：
1. REFERENT TEST
2. SUBSTITUTION TEST
3. NO CONTRADICTIONS
4. EQUIVALENCE CLASS

### 3. ❌ **PROHIBITED MERGE REASONS** （禁止理由清单）

用 ✗ 符号明确列出8个禁止合并的理由，非常醒目。

### 4. 📋 **简洁的 DECISION PROCEDURE**

只有4个步骤，清晰易懂。

### 5. 🛡️ **CONSERVATIVE PRINCIPLE 的清晰表达**

```
False splits < False merges
When in doubt, preserve distinctions.
```

用不等式清晰表达原则。

## 本次改进内容

### 改进 1: 添加 CRITICAL DISTINCTION ⚠️

```yaml
CRITICAL DISTINCTION - Similar Relations ≠ Same Entity:

⚠️  If two entities have similar graph relationships or appear in similar contexts, 
    this does NOT automatically make them the same entity.

Two entities can have similar patterns but be DIFFERENT entities.

Example:
- Entity_1: "张三", works_at → 清华大学, age → 45, position → 教授
- Entity_2: "张三", works_at → 北京大学, age → 22, position → 学生
→ Similar patterns (same name, both at universities), but DIFFERENT people!

Formal: SimilarPatterns(E1, E2) ↛ E1 = E2
(relation pattern similarity does not imply entity identity)
```

**重要性**：这个警告对于防止过度合并至关重要！

### 改进 2: 重构 MERGE CONDITIONS

从分散的规则整合为清晰的 4 个必须条件：

```yaml
MERGE CONDITIONS - ALL must hold:

1. REFERENT TEST: Do the two entities refer to exactly the same real-world object?
   Using BOTH source text AND graph relationships:
   • Same object, different names → MERGE
   • Different objects → KEEP SEPARATE

2. SUBSTITUTION TEST: Can you replace one with the other in ALL contexts?
   Using BOTH source text AND graph relationships:
   • If substitution changes meaning → KEEP SEPARATE
   • If substitution preserves meaning → MERGE

3. NO CONTRADICTIONS: The evidence must be consistent.
   • Any contradiction in source text OR graph → KEEP SEPARATE
   • Hierarchical relations (owns/contains) → KEEP SEPARATE
   • Conflicting attributes → KEEP SEPARATE

4. EQUIVALENCE CLASS: Both entities must denote the SAME single object.
   • Do NOT merge if they represent different instances/aspects
```

### 改进 3: 扩展 PROHIBITED MERGE REASONS

从 4 个扩展到 8 个，并用 ✗ 符号标记：

```yaml
PROHIBITED MERGE REASONS (NOT valid reasons to merge):

✗ Similar names: "John Smith" vs "John Smith Jr."
✗ Same category: "Both are universities"
✗ Similar relations: "Both have relation R"
✗ Related entities: "Apple Inc." vs "Apple Store"
✗ Co-occurrence: "Appear in same context/community"
✗ Shared properties: "Both have property P"
✗ Same community: "Both in community C"
✗ Partial match: "Some relations match"
```

### 改进 4: 简化 DECISION PROCEDURE

从 5 步简化为 4 步：

```yaml
DECISION PROCEDURE:

Use BOTH source text AND graph relationships together.

For Entity 1 and Entity 2:
  
  1. Ask: "Do they refer to the SAME real-world object?" 
     (not just "Are they similar?" or "Are they related?")
  
  2. Check for ANY contradictions:
     → In source text OR graph relationships
     → Hierarchical relationships → KEEP SEPARATE
     → Conflicting attributes → KEEP SEPARATE
  
  3. Apply SUBSTITUTION TEST in ALL contexts:
     → Can you swap them in source text?
     → Can you swap them in graph relationships?
  
  4. If uncertain → answer NO:
     → Limited evidence → KEEP SEPARATE
```

### 改进 5: 强化 CONSERVATIVE PRINCIPLE

```yaml
CONSERVATIVE PRINCIPLE:

False splits (keeping coreferent entities separate) 
< 
False merges (merging distinct entities)

When in doubt, preserve distinctions.
```

用数学不等式清晰表达。

### 改进 6: 增强示例说明

每个示例现在都包含：
1. **Analysis** 部分：展示如何应用 MERGE CONDITIONS
2. **明确标注** 每个条件是否通过（✓ or ✗）
3. **违反的条件或禁止理由**

示例 3（不应合并）：

```yaml
Analysis:
→ REFERENT TEST: Same name but likely different people ✗
→ CONTRADICTION CHECK: Multiple contradictions detected ✗
  - Age: 45 vs 22
  - Role: 教授 vs 学生
  - Institution: 清华大学 vs 北京大学
  - Relationship type: works_at vs studies_at
→ CRITICAL DISTINCTION: Similar patterns but DIFFERENT entities

→ is_coreferent: false
→ Rationale: "Despite identical names '张三', these are different people. 
   Multiple contradictions... This demonstrates CRITICAL DISTINCTION: 
   similar patterns does not equal identity..."
```

### 改进 7: 使用分隔线增强可读性

```yaml
═══════════════════════════════════════════════════════════

FUNDAMENTAL PRINCIPLE:
...

═══════════════════════════════════════════════════════════

CRITICAL DISTINCTION:
...

═══════════════════════════════════════════════════════════
```

## 对比：改进前后

| 方面 | 改进前 | 改进后 | 改进点 |
|-----|-------|-------|-------|
| **警告机制** | ❌ 无 | ✅ CRITICAL DISTINCTION | **新增关键警告** |
| **合并条件** | ⚠️ 分散在多处 | ✅ 4个明确条件（ALL must hold） | **结构化、清晰** |
| **禁止理由** | ⚠️ 4个，不醒目 | ✅ 8个，用✗标记 | **扩展、醒目** |
| **决策流程** | ⚠️ 5步较复杂 | ✅ 4步简洁 | **简化、易懂** |
| **保守原则** | ✅ 已有 | ✅ 不等式表达 | **更清晰** |
| **示例分析** | ⚠️ 只有rationale | ✅ 包含Analysis和标注 | **更教学化** |
| **可读性** | ⚠️ 一般 | ✅ 分隔线分区 | **增强** |

## 完整的 Prompt 结构

```
TASK: ...

Entity 1 (ID: ...) / Entity 2 (ID: ...)

═══════════════════════════════════════════════════════════
FUNDAMENTAL PRINCIPLE
═══════════════════════════════════════════════════════════
CRITICAL DISTINCTION ⚠️
═══════════════════════════════════════════════════════════
MERGE CONDITIONS (ALL must hold)
  1. REFERENT TEST
  2. SUBSTITUTION TEST
  3. NO CONTRADICTIONS
  4. EQUIVALENCE CLASS
═══════════════════════════════════════════════════════════
PROHIBITED MERGE REASONS (8个，用✗标记)
═══════════════════════════════════════════════════════════
DECISION PROCEDURE (4步)
═══════════════════════════════════════════════════════════
CONSERVATIVE PRINCIPLE
═══════════════════════════════════════════════════════════
REPRESENTATIVE SELECTION
═══════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════
EXAMPLES (3个，包含Analysis)
```

## 核心改进总结

### 1. **防止过度合并** 🛡️
- CRITICAL DISTINCTION 警告相似性≠同一性
- 8个明确的 PROHIBITED REASONS
- 示例强调 DIFFERENT entities with similar patterns

### 2. **清晰的判断标准** ✅
- 4个 MERGE CONDITIONS（ALL must hold）
- 每个条件都有明确的通过/不通过标准
- 示例展示如何检查每个条件

### 3. **简洁的决策流程** 📋
- 从5步简化为4步
- 每步都综合使用源文本和图关系
- 保持"unified reasoning"的原则

### 4. **更好的教学性** 📚
- 示例包含 Analysis 部分
- 用 ✓ 和 ✗ 标注条件是否满足
- 明确指出违反了哪个条件或禁止理由

### 5. **增强可读性** 📖
- 使用分隔线区分各个部分
- 用 ⚠️ 和 ✗ 等符号增强视觉效果
- 结构化、模块化的设计

## 修改的文件

1. **`/workspace/config/base_config.yaml`**
   - `prompts.head_dedup.with_representative_selection`
   - 完全重构，应用所有改进

2. **`/workspace/head_dedup_llm_driven_representative.py`**
   - `_get_embedded_prompt_template_v2()`
   - 更新 fallback prompt 以保持一致

## 预期效果

### 1. **更严格的合并标准**
LLM 会更加谨慎，不会仅因为相似就合并。

### 2. **更清晰的推理**
Rationale 会明确说明：
- 检查了哪些条件
- 哪些条件通过/不通过
- 是否违反了禁止理由

### 3. **更少的错误合并**
通过 CRITICAL DISTINCTION 和 PROHIBITED REASONS，减少错误合并。

### 4. **更好的溯源性**
可以从 rationale 中清楚看到 LLM 的判断依据。

## 使用建议

### 1. 测试验证
```bash
python3 test_unified_reasoning_prompt.py
```

### 2. 实际运行
```python
from models.constructor.kt_gen import KnowledgeTreeGen

kt_gen = KnowledgeTreeGen(dataset_name, config)
stats = kt_gen.deduplicate_heads_with_llm_v2(
    enable_semantic=True,
    similarity_threshold=0.85
)
```

### 3. 检查输出质量
重点关注：
- Rationale 是否提到了 MERGE CONDITIONS
- 是否有违反 PROHIBITED REASONS 的情况
- 对于相似但不同的实体，是否正确识别

## 与 Semantic Dedup 的对齐

| 原则 | Semantic Dedup (Tail) | Head Dedup | 对齐程度 |
|-----|---------------------|-----------|---------|
| FUNDAMENTAL PRINCIPLE | ✅ | ✅ | 完全对齐 |
| CRITICAL DISTINCTION | ✅ | ✅ | **新增，完全对齐** |
| MERGE CONDITIONS | ✅ 3个 | ✅ 4个 | 对齐（扩展） |
| PROHIBITED REASONS | ✅ 7个 | ✅ 8个 | 对齐（扩展） |
| DECISION PROCEDURE | ✅ 3步 | ✅ 4步 | 对齐 |
| CONSERVATIVE PRINCIPLE | ✅ | ✅ | 完全对齐 |
| 统一推理（新增） | ❌ | ✅ | Head特有 |

## 总结

本次改进成功借鉴了 semantic_dedup 的优秀设计原则：

1. ✅ **添加了关键警告**（CRITICAL DISTINCTION）
2. ✅ **结构化了判断标准**（MERGE CONDITIONS）
3. ✅ **扩展了禁止理由**（PROHIBITED REASONS）
4. ✅ **简化了决策流程**（DECISION PROCEDURE）
5. ✅ **强化了保守原则**（CONSERVATIVE PRINCIPLE）
6. ✅ **增强了示例教学性**（Analysis + 标注）
7. ✅ **保持了统一推理**（之前的改进）

这些改进使 head dedup prompt 更加：
- **严格**：不会轻易合并
- **清晰**：判断标准明确
- **易懂**：结构化、模块化
- **教学化**：示例详细

---

**相关文档**：
- [SEMANTIC_DEDUP_PRINCIPLES_ANALYSIS.md](SEMANTIC_DEDUP_PRINCIPLES_ANALYSIS.md) - 详细分析
- [HEAD_DEDUP_PROMPT_UNIFIED_REASONING.md](HEAD_DEDUP_PROMPT_UNIFIED_REASONING.md) - 第一轮改进
- [PROMPT_MODIFICATION_SUMMARY.md](PROMPT_MODIFICATION_SUMMARY.md) - 总体总结

**最后更新**: 2025-10-29
