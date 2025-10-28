# Prompt修复说明 - 捡了芝麻别丢西瓜

**问题发现**: 2025-10-28  
**修复状态**: ✅ 已修复  

---

## 😰 问题说明

用户发现了一个**严重问题**：

> "你的 with_representative_selection的prompt和head_dedup中的general的prompt相比，关键的进行等价判断/替换判断的内容都没啦？捡了芝麻丢了西瓜？"

**用户说得完全正确！** 我犯了一个严重错误。

---

## ❌ 原有错误的prompt

### 丢失的关键内容

我的 `with_representative_selection` prompt **丢失了**：

1. ❌ **TYPE CONSISTENCY** - 类型一致性检查
2. ❌ **PROHIBITED MERGE REASONS** - 禁止合并的原因（**最重要！**）
   ```
   ✗ Similar names但不同实体
   ✗ Related entities但不是同一个  
   ✗ Same category但不同实例
   ✗ Shared relations但需要全面匹配
   ✗ Partial overlap需要所有关键关系匹配
   ```
3. ❌ **DECISION PROCEDURE** - 详细的决策流程（**最重要！**）
   ```
   Step 1: 检查名称变体
   Step 2: 比较关系模式
   Step 3: 查找矛盾
   Step 4: 替换测试
   Step 5: 不确定时说NO
   ```
4. ❌ **详细的负面例子** - 应该拒绝合并的案例

### 问题严重性

**严重程度**: 🔴 极高

这些丢失的内容是**防止错误合并的关键规则**！

- **PROHIBITED MERGE REASONS**: 告诉LLM什么情况**不能**合并
- **DECISION PROCEDURE**: 给出明确的判断步骤
- **负面例子**: 展示应该拒绝的情况

**没有这些，LLM可能会错误地合并不该合并的实体！**

---

## ✅ 修复后的prompt

### 完整保留的内容

新的 `with_representative_selection` prompt **完整包含**：

#### 1. REFERENTIAL IDENTITY ✓
```
Do they refer to the exact same object/person/concept?
- Same entity with different names → YES
- Different but related entities → NO
```

#### 2. SUBSTITUTION TEST ✓
```
Can you replace one with the other in all contexts?
- If substitution changes information → NO
- If substitution preserves meaning → YES
```

#### 3. TYPE CONSISTENCY ✓ (修复：之前丢失)
```
Check entity types/categories
- Same name, different types → carefully verify with context
- Example: "Apple (company)" ≠ "Apple (fruit)"
```

#### 4. CONSERVATIVE PRINCIPLE ✓
```
- When uncertain about coreference → answer NO
- When uncertain about representative → choose MORE relationships
- False merge is worse than false split
```

#### 5. PROHIBITED MERGE REASONS ✓ (修复：之前丢失)
```
✗ Similar names: "John Smith" vs "John Smith Jr." → different
✗ Related entities: "Apple Inc." vs "Apple Store" → hierarchy
✗ Same category: Both cities → might be different cities
✗ Shared relations: Need comprehensive match
✗ Partial overlap: Need ALL key relations to match
```

#### 6. DECISION PROCEDURE ✓ (修复：之前丢失)
```
Step 1: Check name variations (abbreviations, translations)
Step 2: Compare relation patterns - consistent relationships?
Step 3: Look for contradictions - conflicts = DIFFERENT
Step 4: Apply substitution test - swappable in all contexts?
Step 5: If uncertain → answer NO
Step 6 (if coreferent): Choose PRIMARY REPRESENTATIVE based on:
  a) Formality and Completeness
  b) Domain Convention
  c) Information Richness
  d) Naming Quality
  e) Cultural Context
```

#### 7. EXAMPLES ✓ (修复：增强了)

新增了**4个详细例子**：

**Example 1** - 应该合并（缩写）:
- UN vs United Nations → 合并，选UN（更多关系）

**Example 2** - 不应该合并（相关但不同）:
- Apple Inc. vs Apple Store → **拒绝**（层级关系，不是等价）

**Example 3** - 不确定（保守拒绝）:
- 张三（45岁教授）vs 张三（22岁学生）→ **拒绝**（矛盾信息）

**Example 4** - 应该合并（正式名）:
- 北京 vs 北京市 → 合并，选北京市（官方名称）

---

## 📊 对比

### 原有general prompt (正确)

```yaml
- ✅ REFERENTIAL IDENTITY
- ✅ SUBSTITUTION TEST
- ✅ TYPE CONSISTENCY
- ✅ CONSERVATIVE PRINCIPLE
- ✅ PROHIBITED MERGE REASONS（关键！）
- ✅ DECISION PROCEDURE（关键！）
- ✅ 3个详细例子（正面+负面）
```

### 错误的with_representative_selection (v1)

```yaml
- ✅ REFERENTIAL IDENTITY
- ✅ SUBSTITUTION TEST
- ❌ TYPE CONSISTENCY（丢失）
- ✅ CONSERVATIVE PRINCIPLE
- ❌ PROHIBITED MERGE REASONS（丢失！关键内容）
- ❌ DECISION PROCEDURE（丢失！关键内容）
- ⚠️ 3个简化例子（缺少负面案例）
+ ✅ PRIMARY REPRESENTATIVE SELECTION（新增）
```

### 修复后的with_representative_selection (v2) ✅

```yaml
- ✅ REFERENTIAL IDENTITY
- ✅ SUBSTITUTION TEST
- ✅ TYPE CONSISTENCY（恢复）
- ✅ CONSERVATIVE PRINCIPLE
- ✅ PROHIBITED MERGE REASONS（恢复！）
- ✅ DECISION PROCEDURE（恢复！）
- ✅ 4个详细例子（包含负面案例）
+ ✅ PRIMARY REPRESENTATIVE SELECTION（新增）
```

---

## 🎯 关键改进

### 1. 恢复PROHIBITED MERGE REASONS

**作用**: 明确告诉LLM**什么不能合并**

```
之前：只说应该合并什么
现在：明确说明不应该合并什么！

✗ Similar names: "John Smith" vs "John Smith Jr."
✗ Related entities: "Apple Inc." vs "Apple Store"
✗ Same category: Both are cities
✗ Shared relations: Similar ≠ Identical
✗ Partial overlap: Need ALL key relations
```

### 2. 恢复DECISION PROCEDURE

**作用**: 给出**明确的判断步骤**

```
之前：没有明确流程，LLM自己猜
现在：6步决策流程！

Step 1: 检查名称变体
Step 2: 比较关系模式
Step 3: 查找矛盾（关键！）
Step 4: 替换测试
Step 5: 不确定→NO
Step 6: 选择representative
```

### 3. 增强EXAMPLES

**作用**: 展示**负面案例**

```
之前：只有正面例子（应该合并的）
现在：包含负面例子！

Example 2: Apple Inc. vs Apple Store → 拒绝（相关但不同）
Example 3: 张三教授 vs 张三学生 → 拒绝（矛盾信息）
```

---

## 🔍 为什么这些很重要？

### PROHIBITED MERGE REASONS的重要性

**场景1**: 相关实体（容易误判）
```
没有这个规则：
  LLM可能认为 "Apple Inc." 和 "Apple Store" 很相似 → 错误合并 ✗

有了这个规则：
  明确指出 "Related entities" 不应该合并 → 正确拒绝 ✓
```

**场景2**: 同名不同实体
```
没有这个规则：
  LLM可能认为两个"张三"是同一人 → 错误合并 ✗

有了这个规则：
  明确指出 "Similar names" 需要关系一致 → 正确拒绝 ✓
```

### DECISION PROCEDURE的重要性

**给出明确流程**:
```
没有流程：
  LLM不知道先看什么后看什么 → 判断不稳定

有了流程：
  Step 1→2→3→4→5 系统化判断 → 结果稳定
```

**Step 3最关键**:
```
"Look for contradictions - if any key relations conflict, they are DIFFERENT"

这一步可以防止大量错误合并！
```

---

## 📝 修复验证

### 验证方法

```bash
# 检查PROHIBITED MERGE REASONS是否存在
grep "PROHIBITED MERGE REASONS" config/base_config.yaml

# 检查DECISION PROCEDURE是否存在
grep "DECISION PROCEDURE" config/base_config.yaml

# 检查TYPE CONSISTENCY是否存在
grep "TYPE CONSISTENCY" config/base_config.yaml

# 检查负面例子
grep "SHOULD NOT MERGE" config/base_config.yaml
```

### 预期输出

都应该找到相应内容！

```bash
✅ PROHIBITED MERGE REASONS found
✅ DECISION PROCEDURE found
✅ TYPE CONSISTENCY found
✅ SHOULD NOT MERGE examples found
```

---

## 🎓 教训

### "捡了芝麻丢了西瓜"

**芝麻**（新增）: PRIMARY REPRESENTATIVE SELECTION  
**西瓜**（丢失）: PROHIBITED MERGE REASONS + DECISION PROCEDURE

**正确做法**: 芝麻和西瓜**都要**！

### 正确的改进方式

```
❌ 错误：用新内容替换旧内容
✅ 正确：在旧内容基础上增加新内容

原有prompt (100分)
  ↓
添加新功能（150分）← 正确
  ✅ 保留原有100分
  ✅ 添加新的50分

替换内容（70分）← 错误
  ❌ 丢失原有30分
  ✅ 添加新的50分
  = 总分反而降低
```

---

## ✅ 修复确认

- [x] ✅ TYPE CONSISTENCY 已恢复
- [x] ✅ PROHIBITED MERGE REASONS 已恢复
- [x] ✅ DECISION PROCEDURE 已恢复
- [x] ✅ 负面例子已添加
- [x] ✅ PRIMARY REPRESENTATIVE SELECTION 保留
- [x] ✅ 4个详细例子（2正面 + 2负面）
- [x] ✅ 创建备份 base_config.yaml.backup2

---

## 🚀 使用修复后的prompt

配置文件已自动更新，无需手动修改。

```python
from models.constructor.kt_gen import KnowledgeTreeGen
from config import get_config

config = get_config()
builder = KnowledgeTreeGen("dataset", config)

# 自动使用修复后的prompt
stats = builder.deduplicate_heads_with_llm_v2()
```

修复后的prompt将会：
- ✅ 正确判断等价性（有完整规则）
- ✅ 正确拒绝不应合并的实体（有PROHIBITED MERGE REASONS）
- ✅ 系统化决策（有DECISION PROCEDURE）
- ✅ 智能选择representative（有PRIMARY REPRESENTATIVE SELECTION）

---

## 🙏 感谢

**感谢用户的敏锐观察！**

如果没有指出这个问题，会导致：
- ❌ LLM错误合并不该合并的实体
- ❌ 准确率大幅下降
- ❌ 产生大量错误数据

**你的反馈拯救了这个功能！** 🎉

---

**修复时间**: 2025-10-28  
**修复状态**: ✅ 完成  
**影响文件**: config/base_config.yaml  
**备份文件**: base_config.yaml.backup2
