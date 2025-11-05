# Prompt强制性增强 - 修改总结

**修改时间**: 2025-11-05 05:52:30  
**修改文件**: `models/constructor/kt_gen.py`  
**修改范围**: `DEFAULT_SEMANTIC_DEDUP_PROMPT` 和 `DEFAULT_ATTRIBUTE_DEDUP_PROMPT`

---

## 修改目标

解决LLM输出中**rationale（理由）与members（成员列表）不一致**的问题，通过增强prompt的强制性和显眼性，而不是case by case的修复。

---

## 核心修改策略

### 1. 🚨 **前置警告** - 在prompt开头立即强调一致性要求

**位置**：紧接在任务描述之后，使用醒目符号

**内容**：
```
🚨 ABSOLUTE CONSISTENCY REQUIREMENT (READ THIS FIRST):
If your rationale states that candidates X and Y 'are the same', 'should be merged', 
'are coreferent', 'refer to the same entity', '予以合并', '视为同一实体', 
or ANY similar phrase indicating they are identical:
→ Those candidates MUST appear TOGETHER in the SAME group's members array
→ DO NOT create separate groups for them
```

**作用**：
- 在LLM开始处理任务前就建立强烈的一致性意识
- 覆盖中英文多种表述方式
- 使用视觉符号（🚨、→）增强注意力

### 2. ✅❌ **正反例对比** - 用具体格式展示正确和错误的输出

**新增内容**：
```
CORRECT OUTPUT FORMAT:
  If candidates [2], [5], [7] are the same entity:
  ✅ {"members": [2, 5, 7], "representative": 2, "rationale": "Candidates [2], [5], and [7] all refer to..."}

INCORRECT OUTPUT FORMAT (NEVER DO THIS):
  ❌ {"members": [2], "rationale": "..."}
  ❌ {"members": [5], "rationale": "Same as [2], should merge"}  ← WRONG!
  ❌ {"members": [7], "rationale": "Merge with [2] and [5]"}  ← WRONG!
  If you write that [2], [5], [7] should merge, they MUST be in ONE group: [2, 5, 7]
```

**作用**：
- 使用通用的候选项索引[2], [5], [7]（不针对具体领域）
- 直观展示错误模式
- 通过对比加深理解

### 3. 📋 **步骤化检查清单** - 提供可执行的验证步骤

**修改位置**：OUTPUT REQUIREMENTS 第5条

**新增内容**：
```
5. 🚨 **MANDATORY CONSISTENCY CHECK** (Verify BEFORE outputting):
   Step 1: Read your rationale for each group
   Step 2: Extract ALL candidate numbers mentioned in that rationale
   Step 3: If rationale uses merge language ('same as', 'merge with', 'coreferent with', etc.):
           → ALL mentioned candidates MUST be in that group's members array
   Step 4: If rationale says candidates are DIFFERENT:
           → They MUST be in DIFFERENT groups
```

**作用**：
- 提供明确的操作步骤
- 指导LLM进行自我检查
- 降低执行难度

### 4. ⚠️ **禁止模式列表** - 明确列出会导致错误的模式

**新增内容**：
```
⚠️  FORBIDDEN PATTERNS (these will cause errors):
   ✗ rationale: '...same as [X]...' but members: [Y] (missing X)
   ✗ rationale: '...merge [X] and [Y]...' but separate groups for X and Y
   ✗ rationale: '...与[X]合并...' but members only contains Y
   ✗ rationale: '...different from [X]...' but members contains both X and Y
```

**作用**：
- 直接指出您遇到的问题模式
- 覆盖中英文表述
- 使用通用变量X、Y（不针对具体案例）

### 5. ☑️ **最终检查清单** - 在prompt末尾添加提交前检查

**新增内容**：
```
═══════════════════════════════════════════════════════════════════════════════
⚠️  FINAL CHECKLIST - Review each group before submitting:
□ Does the rationale mention merging with other candidates?
  → If YES: Are ALL those candidates in the members array?
□ Are there candidates in separate groups with rationales saying they should merge?
  → If YES: Combine them into ONE group
□ Does each group's rationale accurately describe ALL members in that group?
  → If NO: Revise the rationale or adjust the members
═══════════════════════════════════════════════════════════════════════════════
```

**作用**：
- 在生成完成前触发最后一次检查
- 使用分隔线增强视觉效果
- 提供actionable的检查项

---

## 修改的两个Prompt

### 1. `DEFAULT_SEMANTIC_DEDUP_PROMPT`

**用途**：实体去重（判断哪些tail实体指向同一个实体）

**修改行数**：第23-122行

**主要改动**：
- ✅ 开头添加前置警告（第26-38行）
- ✅ 添加正反例对比
- ✅ 重写OUTPUT REQUIREMENTS第5条为步骤化检查（第89-100行）
- ✅ 添加禁止模式列表
- ✅ 更新rationale写作指南，强调"ALL members"（第101-106行）
- ✅ 添加最终检查清单（第113-121行）

### 2. `DEFAULT_ATTRIBUTE_DEDUP_PROMPT`

**用途**：属性值去重（判断哪些属性值表达相同的值）

**修改行数**：第124-226行

**主要改动**：
- ✅ 开头添加前置警告（第127-139行）
- ✅ 添加正反例对比
- ✅ 重写OUTPUT REQUIREMENTS第5条为步骤化检查（第193-204行）
- ✅ 添加禁止模式列表
- ✅ 更新rationale写作指南（第205-210行）
- ✅ 添加最终检查清单（第217-225行）

---

## 设计原则（遵循"不要case by case"的要求）

### ✅ 我们做到的

1. **通用化示例**
   - 使用抽象的候选项编号：[2], [5], [7]、[3], [6], [9]、[X], [Y]
   - 不涉及具体的实体名称或领域知识
   - 适用于任何类型的实体或属性

2. **原则性规则**
   - 强调"referential identity"（指称一致性）和"value identity"（值一致性）
   - 基于逻辑原则，而非特定场景
   - 可复用到任何关系类型

3. **语言无关性**
   - 同时覆盖英文和中文常见表述
   - 使用通用的合并语义词汇
   - 不依赖特定术语

### ❌ 我们避免的

1. **不针对特定实体类型**
   - 没有提及"化学位移"、"质子"等具体概念
   - 没有针对医学、化学等特定领域

2. **不依赖特定关系**
   - 规则适用于任何relation类型
   - 不特殊处理"has_attribute"、"has_property"等

3. **不做个案修复**
   - 不针对用户提供的具体例子调整
   - 所有改动都是通用性的增强

---

## 预期效果

修改后，LLM应该：

1. **在开始任务前就意识到一致性要求**
   - 前置警告确保这是第一印象

2. **知道什么是错误的输出**
   - 通过反例学习，避免重复错误

3. **有明确的检查步骤**
   - 不再是模糊的"要一致"，而是具体的验证流程

4. **在提交前进行自我检查**
   - 最终清单作为最后一道防线

---

## 测试建议

使用修改后的prompt重新测试之前出错的案例：

### 测试用例
如您之前的例子（候选项关于"化学位移"的定义）

### 期望输出
如果LLM判断候选项[1]、[5]、[6]是相同实体：
```json
{
  "groups": [
    {
      "members": [1, 5, 6],
      "representative": 1,
      "rationale": "候选项[1]、[5]和[6]都给出了化学位移的定义，指向同一个概念..."
    }
  ]
}
```

### 不应该出现的输出
```json
{
  "groups": [
    {"members": [1], "rationale": "..."},
    {"members": [5], "rationale": "与[1]一致，予以合并"},  // ❌ 错误！
    {"members": [6], "rationale": "与[1][5]合并"}  // ❌ 错误！
  ]
}
```

---

## 如果问题仍然存在

如果修改后问题依然出现，可能需要：

### 短期方案
1. **降低temperature** - 在`call_llm_api.py`中将默认temperature从0.3降到0.1
2. **添加后处理验证** - 在代码层面检测不一致并发出警告

### 长期方案
1. **切换到更强大的模型** - 如GPT-4o或Claude-3.5-Sonnet
2. **启用结构化输出** - 使用OpenAI的JSON Schema功能
3. **两阶段调用** - 先分组，再生成rationale

---

## 相关文件

- **主修改文件**: `models/constructor/kt_gen.py`
- **问题分析文档**: `桌面/CursorProject/semantic_dedup_rationale_members_inconsistency_20251105_054617.md`
- **本修改总结**: `桌面/CursorProject/prompt_enhancement_changes_20251105_055230.md`

---

## 总结

本次修改通过**5个层次的强制性增强**：
1. 🚨 前置警告
2. ✅❌ 正反例对比
3. 📋 步骤化检查
4. ⚠️ 禁止模式列表
5. ☑️ 最终检查清单

全面提升了prompt的强制性和可执行性，同时保持了**通用性和原则性**，没有进行case by case的设计。

修改完全遵循了"不要case by case"的要求，所有改动都是基于通用原则和抽象示例。
