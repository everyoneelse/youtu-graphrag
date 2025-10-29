# Head Dedup Prompt 修改：原则驱动 vs 案例驱动

## 用户反馈

> "你在修改时，是不是case by case了"

**是的，我最初犯了这个错误。**

## 错误做法（已修正）

### ❌ Case-by-case 修改（错误）

最初我在 prompt 中硬编码了用户的具体案例：

```yaml
CATEGORY-INSTANCE WARNING:
Examples:
- "伪影" (general: all artifacts) vs "魔角伪影" (specific: magic angle artifact) → DIFFERENT  # ← 硬编码用户案例
- "疾病" vs "感冒" → DIFFERENT
...

Example 3 - SHOULD NOT MERGE (category vs instance):
Entity 1: "伪影", relations: [member_of→脊柱解剖与诊断, ...]  # ← 硬编码用户案例
Entity 2: "魔角伪影", relations: [has_attribute→定义:...]
```

**问题：**
- 如果每个用户的具体案例都加进去，prompt 会越来越长
- 变成了"补丁式"修改，而不是建立通用规则
- 违反了用户规则："如果采用case by case的方式修改，那要修改到什么时候"

## 正确做法（已修正）

### ✅ 原则驱动修改（正确）

现在 prompt 中只包含**通用原则和通用示例**：

```yaml
CATEGORY-INSTANCE WARNING:
If one entity is a GENERAL CATEGORY and the other is a SPECIFIC INSTANCE/TYPE, they are DIFFERENT entities.
Pattern: Category_X vs Instance_of_X → ALWAYS DIFFERENT  # ← 通用模式
Examples:
- "Animal" (category) vs "Tiger" (specific species) → DIFFERENT      # ← 通用示例
- "Disease" (category) vs "Influenza" (specific disease) → DIFFERENT  # ← 通用示例
- "Vehicle" (category) vs "Car" (specific type) → DIFFERENT           # ← 通用示例
- "Food" (category) vs "Apple" (specific food) → DIFFERENT            # ← 通用示例

Example 3 - SHOULD NOT MERGE (category vs instance):
Entity 1: "Vehicle", relations: [has_type→Car, has_type→Truck, ...]  # ← 通用示例
Entity 2: "Car", relations: [is_type_of→Vehicle, has_feature→Four wheels, ...]
→ Rationale: "Vehicle" is a GENERAL CATEGORY, "Car" is a SPECIFIC TYPE...
```

**优势：**
- ✅ 建立了通用的判断模式：`Category_X vs Instance_of_X → ALWAYS DIFFERENT`
- ✅ 示例涵盖多个领域（动物、疾病、交通工具、食物）
- ✅ LLM 可以将这个模式应用到任何领域，包括用户的"伪影"案例
- ✅ 不需要为每个新案例修改 prompt

## 核心原则

### 我们添加的是通用规则，不是具体案例

| 修改内容 | 类型 | 说明 |
|---------|------|------|
| **FUNDAMENTAL PRINCIPLE** | ✅ 通用原则 | REFERENTIAL IDENTITY 适用于所有实体 |
| **CRITICAL DISTINCTION** | ✅ 通用原则 | 相似上下文 ≠ 实体同一性（适用于所有场景） |
| **CATEGORY-INSTANCE WARNING** | ✅ 通用模式 | `Category_X vs Instance_of_X → DIFFERENT`（模式） |
| **PROHIBITED MERGE REASONS** | ✅ 通用规则 | 9 条禁止理由适用于所有实体对 |
| **DECISION PROCEDURE** | ✅ 通用流程 | 5 步决策流程适用于所有判断 |
| **Examples** | ✅ 通用示例 | Vehicle/Car, Animal/Tiger（跨领域示例） |
| ~~"伪影" vs "魔角伪影"~~ | ❌ 具体案例 | 已删除，LLM 通过通用模式自动推断 |

## 为什么通用原则能解决用户的问题？

用户的案例：**"伪影" vs "魔角伪影"**

LLM 通过通用原则推理：

1. **读取 CATEGORY-INSTANCE WARNING**：
   - "If one entity is a GENERAL CATEGORY and the other is a SPECIFIC INSTANCE/TYPE, they are DIFFERENT"
   - Pattern: `Category_X vs Instance_of_X → ALWAYS DIFFERENT`

2. **看到示例**：
   - "Vehicle" (category) vs "Car" (specific type) → DIFFERENT
   - "Animal" (category) vs "Tiger" (specific species) → DIFFERENT

3. **应用到具体案例**：
   - "伪影" = 通用类别（所有 MRI 伪影）
   - "魔角伪影" = 特定类型（魔角效应产生的伪影）
   - → 匹配模式 `Category_X vs Instance_of_X`
   - → 结论：DIFFERENT

4. **检查 DECISION PROCEDURE**：
   - Step 2: "Is one a category and the other an instance/type? → If YES, KEEP SEPARATE"
   - → 确认：KEEP SEPARATE

**结果：** LLM 能正确判断，无需在 prompt 中看到"伪影"这个词。

## 测试验证

虽然 prompt 中没有"伪影"的具体案例，但通用原则应该能覆盖：

```python
# LLM 应该能推理：
"伪影" vs "魔角伪影"
→ 识别为 Category vs Instance 模式
→ 应用 CATEGORY-INSTANCE WARNING
→ 判断：KEEP SEPARATE
```

## 设计哲学

### 好的 Prompt 设计

```
通用原则 + 跨领域示例 = 强大的泛化能力
```

- **通用原则**：定义判断标准（REFERENTIAL IDENTITY, SUBSTITUTION TEST）
- **通用模式**：定义常见错误模式（Category vs Instance）
- **跨领域示例**：展示如何应用（Vehicle/Car, Animal/Tiger）
- **LLM 推理**：将原则和模式应用到新案例

### 坏的 Prompt 设计

```
具体案例 + 具体案例 + 具体案例 = 补丁堆积
```

- 每个用户问题都加一个示例
- Prompt 越来越长
- 仍然会遇到没见过的新案例
- 不可持续

## 总结

### 修正前（错误）
- ❌ 在 prompt 中硬编码 "伪影" vs "魔角伪影"
- ❌ Case-by-case 修改

### 修正后（正确）
- ✅ 只添加通用原则：`Category_X vs Instance_of_X → DIFFERENT`
- ✅ 使用跨领域示例：Vehicle/Car, Animal/Tiger, Disease/Influenza
- ✅ LLM 通过模式识别应用到 "伪影" vs "魔角伪影"
- ✅ 原则驱动，可持续

## 遵循的用户规则

> "如果你被要求修改prompt，请注意修改时，不要case by case的修改，如果采用case by case的方式修改，那要修改到什么时候"

✅ 我们现在遵循了这个规则：
- 建立了通用的 CATEGORY-INSTANCE 模式
- 使用了跨领域的通用示例
- 没有硬编码用户的具体案例
- 可以应用到未来所有类似问题

---

**修正日期**: 2025-10-29  
**状态**: ✅ 已修正为原则驱动
