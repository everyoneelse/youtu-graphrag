# Head Dedup: 应用Semantic Dedup判断逻辑

**日期**: 2025-10-29  
**任务**: 将semantic_dedup的判断逻辑直接应用到head_dedup，只修改开头部分以适配输入格式

---

## 📋 修改说明

### 修改策略
1. **保持判断逻辑不变**: 直接使用semantic_dedup的完整判断逻辑
2. **修改开头部分**: 适配head_dedup的输入格式（两个entity，包含图关系+chunk）
3. **调整输出格式**: 适配head_dedup的输出（is_coreferent, confidence, rationale）

---

## 🔄 从semantic_dedup复制的部分

### ✅ 完整保留的判断逻辑

#### 1. CRITICAL RULES (4条)
```
1. REFERENTIAL IDENTITY
   - MERGE: Same entity with different names → YES
   - DO NOT MERGE: Different entities → NO

2. SUBSTITUTION TEST
   - If substitution changes information → DO NOT MERGE
   - If substitution preserves meaning → MERGE

3. EQUIVALENCE CLASS
   - Both entities must represent ONE single entity
   - Do NOT merge entities that are multiple distinct entities

4. CONSERVATIVE PRINCIPLE
   - When uncertain → KEEP SEPARATE
   - False merge is worse than false split
```

#### 2. CRITICAL DISTINCTION
```
CRITICAL DISTINCTION - Relation Satisfaction vs Entity Identity:
⚠️  If two entities have similar relations or contexts, this does NOT make them coreferent.
Each entity can be a DIFFERENT entity that happens to have SIMILAR relations.
Example: 'Zhang San works_at Tsinghua University' and 'Zhang San works_at Computer Science Department'
→ Both satisfy 'works_at', but they are DIFFERENT entities (university vs department)
```

#### 3. PROHIBITED MERGE REASONS (7条)
```
✗ Shared relation: "Both have similar relations" → NOT sufficient
✗ Semantic similarity: "X and Y are similar/related" → similarity ≠ identity
✗ Same category: "Both are type T" → category membership ≠ entity identity
✗ Co-occurrence: "X and Y appear together" → contextual proximity ≠ coreference
✗ Functional relationship: "X causes/affects/contains Y" → relationship ≠ identity
✗ Shared properties: "X and Y have property P" → property sharing ≠ entity identity
✗ Part of same set: "X, Y ∈ Set_S" → set membership ≠ element identity
```

#### 4. DECISION PROCEDURE (6步)
```
1. Check if they are variations of the same entity (abbreviations, translations, aliases)
2. Compare their graph relations - do they describe the SAME entity?
3. Compare their source text contexts - do they describe the SAME entity?
4. Apply SUBSTITUTION TEST: Can they be swapped in all contexts?
5. Look for contradictions - if any key information conflicts, they are DIFFERENT
6. If uncertain → answer NO (conservative principle)
```

#### 5. CONSERVATIVE PRINCIPLE说明
```
False splits (keeping coreferent entities separate) < False merges (merging distinct entities)
When in doubt, preserve distinctions.
```

---

## 🎯 修改的部分

### 1. 开头部分（适配head_dedup）

**之前 (semantic_dedup)**:
```
You are an expert in knowledge graph entity deduplication.
All listed triples share the same head entity and relation.

Head entity: {head}
Relation: {relation}

Head contexts (source text):
{head_context}

Candidate tails:
{candidates}

TASK: Identify which tails are COREFERENT (refer to the exact same entity/concept).
```

**之后 (head_dedup)**:
```
You are an expert in knowledge graph entity deduplication.

TASK: Determine if the following two entities are COREFERENT (refer to the exact same entity/concept).

Entity 1: {entity_1}
Related knowledge about Entity 1 (graph relations and source text):
{context_1}

Entity 2: {entity_2}
Related knowledge about Entity 2 (graph relations and source text):
{context_2}
```

**关键差异**:
- ✅ 从"多个tails"变为"两个entities"
- ✅ 明确说明context包含"graph relations and source text"
- ✅ 去掉了relation相关的描述（head_dedup是全局去重）

### 2. 输出格式（适配head_dedup）

**之前 (semantic_dedup)**:
```json
{
  "groups": [
    {"members": [1, 3], "representative": 3, "rationale": "..."}
  ]
}
```

**之后 (head_dedup)**:
```json
{
  "is_coreferent": true/false,
  "confidence": 0.0-1.0,
  "rationale": "Clear explanation based on REFERENTIAL IDENTITY"
}
```

---

## ✅ 测试结果

```
✓ Head dedup prompt formatting successful
✓ Formatted prompt length: 4194 characters
✓ All required sections from semantic_dedup present
✓ Adapted for head_dedup (two entities)
```

验证项:
- [x] CRITICAL RULES (4条)
- [x] CRITICAL DISTINCTION
- [x] PROHIBITED MERGE REASONS (7条)
- [x] DECISION PROCEDURE (6步)
- [x] CONSERVATIVE PRINCIPLE
- [x] 适配Entity 1和Entity 2格式
- [x] 说明包含graph relations和source text

---

## 🔍 Context信息对比

### semantic_dedup的context
```
Head contexts (source text):
- (chunk_1) Zhang San works at Tsinghua University...
- (chunk_3) He is a professor...

Candidate tails:
[1] Tail: Tsinghua University
    Contexts:
      - (chunk_1) Tsinghua University is in Beijing...
```
**只使用chunk文本**

### head_dedup的context
```
Entity 1: Beijing
Related knowledge about Entity 1 (graph relations and source text):
Graph relations:
  • capital_of → China
  • located_in → North China
Source text: "Beijing is the capital of China..."
```
**使用图关系 + 源文本** (根据use_hybrid_context配置)

---

## 📊 判断逻辑一致性

| 判断逻辑部分 | semantic_dedup | head_dedup | 状态 |
|------------|----------------|-----------|------|
| CRITICAL RULES | ✓ | ✓ | 完全一致 |
| CRITICAL DISTINCTION | ✓ | ✓ | 完全一致 |
| PROHIBITED MERGE REASONS | ✓ | ✓ | 完全一致 |
| DECISION PROCEDURE | ✓ | ✓ | 完全一致 |
| CONSERVATIVE PRINCIPLE | ✓ | ✓ | 完全一致 |

**结论**: 两个prompt使用**完全相同**的判断逻辑和原则！

---

## 🎯 设计优势

### 1. 统一的判断标准
- semantic_dedup和head_dedup使用完全相同的判断逻辑
- 减少不一致性，提高整体图谱质量

### 2. 经过验证的逻辑
- semantic_dedup的判断逻辑已经在生产环境中验证
- 直接应用到head_dedup可以利用已有的最佳实践

### 3. 更容易维护
- 判断逻辑只需要在一个地方更新
- semantic_dedup的改进可以直接同步到head_dedup

### 4. 清晰的职责划分
- **开头部分**: 描述输入格式（tailsVS entities, chunk VS graph+chunk）
- **判断逻辑**: 统一的去重原则（完全一致）
- **输出格式**: 适配不同的使用场景（groups VS is_coreferent）

---

## 📝 示例对比

### semantic_dedup示例
```
Input:
  Head: Zhang San
  Relation: works_at
  Candidate tails: [1] Tsinghua University, [2] 清华大学, [3] Tsinghua Univ

Output:
  {
    "groups": [
      {"members": [1, 2, 3], "representative": 1, "rationale": "All refer to same university"}
    ]
  }
```

### head_dedup示例
```
Input:
  Entity 1: Tsinghua University
  Entity 2: 清华大学

Output:
  {
    "is_coreferent": true,
    "confidence": 0.95,
    "rationale": "Same university with different names (English vs Chinese)"
  }
```

---

## 🚀 未来优化方向

### 短期
- ✅ 统一判断逻辑 (已完成)
- 📋 在真实数据上测试效果
- 📋 对比修改前后的去重质量

### 长期
- 🔬 考虑将判断逻辑提取为共享模板
- 🔬 根据实际效果微调PROHIBITED MERGE REASONS
- 🔬 收集badcase优化DECISION PROCEDURE

---

**修改完成时间**: 2025-10-29  
**文件修改**: `config/base_config.yaml` → `prompts.head_dedup.general`  
**状态**: ✅ 已测试通过  
**兼容性**: ✅ 与现有代码完全兼容
