# Head Dedup Prompt 改进：融合 Semantic Dedup 原则

## 修改日期
2025-10-29

## 问题描述

在使用 head_dedup 对知识图谱进行去重时，发现当前 prompt 过于依赖 chunk 内容，导致错误判断。

### 问题案例

**错误判断结果：**
```json
{
  "duplicate_name": "伪影",
  "canonical_name": "魔角伪影",
  "metadata": {
    "rationale": "（1）指称同一性：两条实体均描述'当肌腱、韧带等平行纤维结构与主磁场成约55°夹角时，MRI短TE序列出现信号增强、易被误诊为病理'的物理现象...",
    "confidence": 1.0
  }
}
```

**为什么这是错误的：**
- **"伪影"** 是一个**通用类别**（所有 MRI 伪影）
- **"魔角伪影"** 是一个**特定类型**（魔角效应产生的伪影）
- 它们处于**类别-实例关系**，不是同一实体

这类似于将 "动物" 和 "老虎" 判断为相同实体，显然是错误的。

## 根本原因

当前 head_dedup prompt 的问题：
1. ❌ 缺少 "类别-实例" 关系的明确警告
2. ❌ 没有强调 "相似上下文 ≠ 实体同一性"
3. ❌ PROHIBITED MERGE REASONS 不够全面
4. ❌ 过于依赖 chunk 内容的相似性

## 解决方案

参考 `semantic_dedup_group` 中使用的 `DEFAULT_SEMANTIC_DEDUP_PROMPT`，将其核心原则融入 head_dedup prompt。

### 关键改进点

#### 1. 添加 CRITICAL DISTINCTION 警告

```yaml
CRITICAL DISTINCTION - Similar Context/Relations ≠ Entity Identity:
⚠️  If two entities appear in similar contexts or have similar relations, this does NOT make them the same entity.
Each entity can be a DIFFERENT object that happens to appear in SIMILAR contexts.
Formal logic: Similar_Context(X, Y) ↛ X=Y  (contextual similarity does not imply entity identity)
```

#### 2. 强化 MERGE CONDITIONS

```yaml
MERGE CONDITIONS - ALL must hold:
1. REFERENT TEST: Do the two entities refer to exactly the same object in the real world?
   • Same entity, different names → MERGE (e.g., 'NYC' = 'New York City')
   • Different entities → KEEP SEPARATE (even if highly related)
   • Category vs Instance → KEEP SEPARATE (e.g., "动物" ≠ "老虎", "伪影" ≠ "魔角伪影")

2. SUBSTITUTION TEST: Can you replace one entity with the other in ALL contexts without changing truth value?
   • If substitution changes meaning/information → KEEP SEPARATE
   • If substitution preserves meaning → MERGE

3. EQUIVALENCE: After merging, both must denote the SAME single entity.
   • Do NOT merge entities representing different objects
   • Each pair = one entity with different linguistic expressions
```

#### 3. 扩展 PROHIBITED MERGE REASONS

新增了更多禁止合并的原因：

```yaml
PROHIBITED MERGE REASONS (these are NOT valid reasons to merge):
✗ Semantic similarity: "X and Y are similar/related" → similarity ≠ identity
✗ Same category: "Both are type T" → category membership ≠ entity identity
✗ Shared context: "X and Y appear in similar contexts" → contextual proximity ≠ identity
✗ Shared relations: "Both have similar relations" → relation similarity ≠ entity identity
✗ Functional relationship: "X causes/affects/contains Y" → relationship ≠ identity
✗ Shared properties: "X and Y have property P" → property sharing ≠ entity identity
✗ Category-Instance: "X is category, Y is instance of X" → hierarchical relationship ≠ identity
✗ Part-Whole: "X is part of Y" or "Y contains X" → compositional relationship ≠ identity
✗ General-Specific: "X is general term, Y is specific type" → specificity difference ≠ identity
```

#### 4. 新增 CATEGORY-INSTANCE WARNING 专项

```yaml
CATEGORY-INSTANCE WARNING:
If one entity is a GENERAL CATEGORY and the other is a SPECIFIC INSTANCE/TYPE, they are DIFFERENT entities.
Examples:
- "伪影" (general: all artifacts) vs "魔角伪影" (specific: magic angle artifact) → DIFFERENT
- "疾病" (category: disease) vs "感冒" (instance: common cold) → DIFFERENT  
- "动物" (category: animal) vs "老虎" (instance: tiger) → DIFFERENT
- "Vehicle" (category) vs "Car" (specific type) → DIFFERENT
```

#### 5. 更新 DECISION PROCEDURE

在决策流程中明确加入类别-实例检查：

```yaml
DECISION PROCEDURE:
For Entity 1 and Entity 2:
  1. Ask: "Do they refer to the same entity?" (not "Are they related?")
  2. Check: Is one a category and the other an instance/type? → If YES, KEEP SEPARATE
  3. Apply SUBSTITUTION TEST: Would swapping them change the information?
  4. Check for contradictions in their relations/properties
  5. If uncertain → answer NO (conservative principle)
```

#### 6. 新增针对性示例

添加了用户提到的具体案例作为示例：

```yaml
Example 3 - SHOULD NOT MERGE (category vs instance):
Entity 1: "伪影", relations: [member_of→脊柱解剖与诊断, 表现形式为→魔角效应]
Entity 2: "魔角伪影", relations: [has_attribute→定义:肌腱、韧带等...成55°夹角时信号增强, 常见部位或组织为→肌腱]
→ is_coreferent: false, confidence: 0.90
→ Rationale: "伪影" is a GENERAL CATEGORY (all MRI artifacts), "魔角伪影" is a SPECIFIC TYPE (magic angle artifact). They are in a category-instance relationship, not identity. Cannot substitute one for the other without losing specificity.
```

## 修改内容对比

| 方面 | 修改前 | 修改后 |
|-----|--------|--------|
| **CRITICAL DISTINCTION** | ❌ 无 | ✅ 明确警告：相似上下文 ≠ 实体同一性 |
| **类别-实例关系** | ⚠️ 仅在 "Same category" 中轻微提及 | ✅ 专门的 CATEGORY-INSTANCE WARNING 部分 |
| **PROHIBITED REASONS** | 5 条 | 9 条（新增 4 条） |
| **DECISION PROCEDURE** | 5 步 | 5 步（第 2 步新增类别-实例检查） |
| **示例** | 3 个 | 4 个（新增类别-实例示例） |
| **FUNDAMENTAL PRINCIPLE** | ⚠️ 在 CRITICAL RULES 中分散 | ✅ 集中在开头，明确定义 |

## 核心设计原则

### 1. 原则驱动，非案例驱动

遵循用户规则：
> "如果你被要求修改prompt，请注意修改时，不要case by case的修改"

我们采用的是**通用原则性指导**：
- ✅ 建立了通用的判断标准（REFERENTIAL IDENTITY）
- ✅ 明确了禁止合并的通用原因（9 条）
- ✅ 专门针对常见错误模式（类别-实例）建立警告机制

而不是：
- ❌ 针对 "伪影/魔角伪影" 这个特定案例打补丁
- ❌ 硬编码具体实体名称的判断规则

### 2. 保持与 semantic_dedup 一致的哲学

核心思想：
```
COREFERENCE requires REFERENTIAL IDENTITY
相似性（similarity）≠ 同一性（identity）
```

这个原则在两个 prompt 中现在都是核心：
- `semantic_dedup`: 用于 tail 去重（relation 对象去重）
- `head_dedup`: 用于 head 去重（实体去重）

### 3. 保守原则

```
False splits (keeping coreferent entities separate) < False merges (merging distinct entities)
When in doubt, KEEP SEPARATE.
```

宁可误拆（false split），不可误合（false merge）。

## 预期效果

使用新 prompt 后，对于用户提到的案例：

```
Entity 1: "伪影" (chunk: 魔角效应：魔角效应伪影，在短TE序列上较为显著...)
Entity 2: "魔角伪影" (chunk: 魔角伪影主要影响肌腱、韧带等平行纤维结构...)
```

**预期判断：**
```json
{
  "is_coreferent": false,
  "confidence": 0.90,
  "rationale": "Entity 1 ('伪影') is a GENERAL CATEGORY encompassing all MRI artifacts, while Entity 2 ('魔角伪影') is a SPECIFIC TYPE referring only to magic angle artifacts. They are in a category-instance relationship, not entity identity. Substitution test fails: replacing '伪影' with '魔角伪影' would incorrectly narrow the scope, and vice versa would incorrectly broaden it. Conservative principle applied: KEEP SEPARATE."
}
```

## 修改文件

- ✅ `config/base_config.yaml` → `prompts.head_dedup.general`

## 测试建议

### 1. 验证类别-实例判断

测试案例：
```python
test_cases = [
    # 应该拒绝合并
    ("伪影", "魔角伪影"),         # 类别 vs 特定类型
    ("疾病", "感冒"),             # 类别 vs 实例
    ("动物", "老虎"),             # 类别 vs 实例
    ("Vehicle", "Car"),           # 类别 vs 类型
    
    # 应该合并
    ("UN", "United Nations"),     # 缩写 vs 全称
    ("NYC", "New York City"),     # 别名
    ("魔角伪影", "魔角效应伪影"),  # 同一实体的不同表达
]
```

### 2. 回归测试

确保原有的正确判断仍然有效：
- 缩写-全称：应该合并
- 不同但相关的实体：应该拒绝合并
- 不确定的情况：保守地拒绝合并

### 3. 实际数据测试

在实际知识图谱数据上运行 head deduplication：
```bash
python offline_semantic_dedup.py \
    --graph output/graphs/demo.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_deduped.json \
    --config config/base_config.yaml
```

查看日志和中间结果，确认：
- 类别-实例关系被正确识别
- 合并率是否合理（不应过高）
- rationale 的解释是否清晰

## 后续步骤

1. ✅ 修改 `config/base_config.yaml` 中的 prompt
2. ⏳ 在测试数据上验证新 prompt
3. ⏳ 观察实际使用中的效果
4. ⏳ 根据反馈进一步调整（如果需要）

## 相关文档

- `SEMANTIC_DEDUP_PRINCIPLES_ANALYSIS.md` - Semantic dedup 原则分析
- `HEAD_DEDUP_IMPROVED_WITH_SEMANTIC_PRINCIPLES.md` - 之前的改进
- `PROMPT_MODIFICATION_GUIDE.md` - Prompt 修改指南
- `HEAD_DEDUP_PROMPT_CUSTOMIZATION.md` - Prompt 自定义说明

## 注意事项

### ⚠️ 缓存失效

如果之前保存了 semantic results 的缓存（intermediate results），修改 prompt 后需要**重新生成**：

```bash
# 删除旧缓存
rm output/intermediate_results/*.pkl

# 重新运行去重
python offline_semantic_dedup.py --graph ... --chunks ... --output ...
```

### ⚠️ 配置文件版本

确保使用的是 `config/base_config.yaml` 而不是备份文件：
- ✅ `config/base_config.yaml` - 最新版本
- ❌ `config/base_config.yaml.backup` - 旧版本
- ❌ `config/base_config.yaml.backup2` - 旧版本

## 总结

本次改进的核心是：

1. **强化原则性指导**：明确 "相似性 ≠ 同一性"
2. **新增类别-实例警告**：专门处理这类常见错误
3. **扩展禁止理由**：从 5 条扩展到 9 条
4. **保持一致性**：与 semantic_dedup 使用相同的哲学

这使得 head_dedup 不再过度依赖 chunk 内容的相似性，而是基于严格的 **referential identity** 原则进行判断。

---

**最后更新**: 2025-10-29
**状态**: ✅ 已完成
