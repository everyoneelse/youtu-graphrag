# Semantic Dedup Validation V2.0 - Changelog

## 📅 更新日期: 2025-10-23

## 🎯 核心改进：聚焦验证范围

### 问题
V1.0的验证prompt范围过于宽泛，会检测多种类型的不一致，包括：
- ✅ rationale的结论与分组结构不匹配（**这是我们要的**）
- ❌ rationale内容的准确性问题（**这不是我们要的**）

例如，V1.0会报告：
> "Group 2的rationale说有54.7°角度，但原文只说'特定角度'没有具体数值"

这是rationale内容准确性的问题，不是分组结构的不一致。

### 解决方案
V2.0明确限定验证范围，**只检查一个核心问题**：

> **rationale的结论（合并/独立）是否与实际分组结构（members数组）一致？**

## 📝 主要变更

### 1. 重写Prompt结构

**Before (V1.0):**
```
CORE TASK:
Check if each group's 'rationale' is LOGICALLY CONSISTENT with its 'members' array.

CONSISTENCY PRINCIPLE:
A group is CONSISTENT when:
  ✅ The rationale accurately describes WHY the members are grouped together
  ✅ If rationale says items are "coreferent/equivalent/same", they ARE in the same group
  ...
```

**After (V2.0):**
```
═══════════════════════════════════════════════════════════════════
🎯 YOUR ONLY JOB: Check rationale's CONCLUSION vs actual grouping
═══════════════════════════════════════════════════════════════════

CHECK THIS ONE THING:
Does the rationale's CONCLUSION (merge/keep separate) match the actual members array?

🚫 DO NOT CHECK (out of scope):
  ❌ Whether rationale accurately describes original candidate content
  ❌ Whether rationale mentions details not in original text
  ❌ Whether rationale's reasoning is sound or makes sense
  ❌ Content accuracy of the rationale

🎯 ONLY CHECK:
  ✅ Does "rationale conclusion" match "actual grouping structure"?
```

### 2. 明确排除项

新增了明确的"DO NOT CHECK"部分，告诉LLM哪些问题**不**应该报告：

```
🚫 DO NOT CHECK (out of scope):
  ❌ Whether rationale accurately describes original candidate content
  ❌ Whether rationale mentions details not in original text
  ❌ Whether rationale's reasoning is sound or makes sense
  ❌ Content accuracy of the rationale
```

### 3. 简化验证步骤

**Before (V1.0 - 5步):**
```
1. Read each group's rationale carefully
2. Check if the members array matches the rationale's claim
3. **ESPECIALLY**: If rationale mentions merging with other groups, verify those groups are actually merged
4. Use your understanding of semantics and coreference
5. Consider the INTENT behind the rationale
```

**After (V2.0 - 4步，更聚焦):**
```
For each group:
1. Read the rationale's CONCLUSION: Does it say merge or keep separate?
2. Check if rationale mentions other groups/items (e.g., "与组1", "same as group 0")
3. Look at the members array: Are those mentioned items actually included?
4. If mismatch → Report inconsistency

IGNORE:
- Content details in rationale
- Whether reasoning makes sense
- Original candidate text accuracy
```

### 4. 添加反面示例

新增了"What NOT to report"**原则性**示例，明确告诉LLM什么情况不应该报告：

```python
Example 3 (What NOT to report - General principle):
Scenario type: Rationale content inaccuracy but grouping structure is correct

Pattern:
- Rationale says items should be grouped together → Members ARE grouped together ✅
- BUT rationale's description/reasoning has factual errors ⚠️

Decision: DO NOT REPORT
Reason: Content accuracy is out of scope. We only check structural consistency.

Rule: If the grouping action (merge/separate) matches the rationale's conclusion,
      then it's CONSISTENT, regardless of whether the rationale's reasoning is accurate.

Examples of this pattern (all should NOT be reported):
- Rationale mentions details not in original candidates
- Rationale uses incorrect terminology or descriptions
- Rationale's reasoning logic is flawed
- Rationale makes factual mistakes
→ As long as grouping structure matches the conclusion, it's CONSISTENT.
```

**设计原则**：不列举具体案例（如"54.7°角度"），而是描述通用模式和原则。

### 5. 统一issue_type

**Before (V1.0):**
- 多种issue_type: `rationale_claims_coreference_but_separate`, `rationale_says_merge_but_not_merged`, 等

**After (V2.0):**
- 统一为: `rationale_conclusion_vs_grouping_mismatch`

## 📊 对比总结

| 方面 | V1.0 | V2.0 |
|------|------|------|
| **验证范围** | 广泛：rationale与members的各种一致性 | 聚焦：只检查结论与分组是否匹配 |
| **是否检查内容准确性** | ✅ 是（会报告细节不准确） | ❌ 否（只看分组结构） |
| **验证步骤** | 5步，较宽泛 | 4步，更聚焦 |
| **反面示例** | ❌ 无 | ✅ 有（Example 3） |
| **排除项说明** | ❌ 无 | ✅ 有（DO NOT CHECK） |
| **issue_type** | 多种 | 统一为一种 |

## ✅ 应该检测的问题（V2.0）

- ✅ rationale说"可合并"，但members没有合并
- ✅ rationale说"与组X相同"，但members不包含组X的items
- ✅ rationale说"保持独立"，但members包含了其他组的items
- ✅ 任何"rationale结论 vs 实际分组结构"的不一致

## ❌ 不应该检测的问题（V2.0）

- ❌ rationale提到的细节不在原文中
- ❌ rationale的推理逻辑不合理
- ❌ rationale对原文的理解不准确
- ❌ rationale的措辞不够精确

## 🎯 核心原则

> **只看分组结构，不看内容细节**
> 
> 只要rationale的**结论**（合并/独立）与实际的**分组结构**（members数组）一致，就算通过验证。
> 
> 至于rationale是否准确描述了原文，那是另一个问题，不在本验证的范围内。

## 📁 修改文件

- `models/constructor/kt_gen.py` - 重写了 `DEFAULT_SEMANTIC_DEDUP_VALIDATION_PROMPT`
- `config/base_config.yaml` - 更新了注释
- `SEMANTIC_DEDUP_VALIDATION_FIX_SUMMARY.md` - 更新了文档
- `DOCUMENTATION_INDEX.md` - 添加了V2文档链接

## 🔧 使用方法

无需更改配置，只要启用了验证即可：

```yaml
semantic_dedup:
  enable_semantic_dedup_validation: true
```

V2.0会自动使用新的验证逻辑。

## 🚀 效果

- ✅ **更精确**: 只报告真正的分组结构问题
- ✅ **更简洁**: 不会报告无关的内容准确性问题
- ✅ **更高效**: LLM可以更快地完成验证
- ✅ **更易理解**: 报告的问题都是核心的结构性问题

## 📌 向后兼容

完全向后兼容，无需修改代码或配置。只是让LLM更聚焦在核心问题上。

---

**版本**: V2.0 → V3.0  
**更新时间**: 2025-10-23  
**状态**: ✅ V3.0已完成，待测试

---

## 🚀 V3.0 (2025-10-23) - 极简重构

### 问题
V2.0虽然明确了验证范围，但在实际使用中发现：
- LLM仍然无法检测到用户真实案例中的"故归入一组"不一致
- Prompt太长（~150行），关键信息被淹没
- 过多装饰和重复内容，分散LLM注意力

### 用户真实案例（V2.0未能检测）

```python
{
  'members': [4],
  'rationale': '"边缘振荡伪影"...与"振铃伪影"视角相同，可视为同一别名，故归入一组。'
}
```

rationale明确说"**故归入一组**"，但members只有[4]，没有实际合并。

### V3.0解决方案

#### 1. 大幅简化prompt

| Metric | V2.0 | V3.0 | 改进 |
|--------|------|------|------|
| 行数 | ~150行 | ~80行 | -47% |
| 核心内容占比 | ~40% | ~80% | +100% |
| 装饰元素 | 多 | 少 | 更清晰 |

#### 2. 突出关键短语

**特别强化**：
```
⚠️ CRITICAL: "故归入一组" / "归入XX组" = says to MERGE
```

用户案例中的确切短语！

#### 3. 使用真实案例

**V2.0**: 虚构的通用示例  
**V3.0**: 用户实际遇到的"振铃伪影"案例

```
Input groups:
- Group 0: {members: [1], rationale: "振铃伪影，单独保留作为代表"}
- Group 1: {members: [4], rationale: "...故归入一组"}

Step 1: "故归入一组" = MERGE
Step 2: members: [4] only = SEPARATE  
Step 3: MERGE ≠ SEPARATE → ❌ INCONSISTENT
```

#### 4. 步骤式推理

**V2.0 (文字描述)**:
```
Analysis: Group 1's rationale says "故归入一组" but members are separate...
```

**V3.0 (步骤式)**:
```
Step 1: What does rationale conclude? → MERGE
Step 2: What do members show? → SEPARATE
Step 3: Match? → NO, INCONSISTENT
```

### V3.0主要变更

#### Removed ❌
- 冗长的CONTEXT部分（head/relation在此验证中不重要）
- 重复的原则说明
- 过多的装饰线（═══）
- 复杂的验证步骤描述

#### Added ✅
- "故归入一组"关键短语的突出标注
- 用户真实案例作为示例
- Step-by-step推理演示
- 更聚焦的关键词列表

#### Improved ⬆️
- Prompt长度：150行 → 80行
- 验证步骤：5步 → 3个问题
- 示例质量：通用 → 真实案例
- 可读性：中等 → 高

### 关键短语列表（V3.0）

**MERGE indicators（更聚焦）**:
```
- "归入一组" / "归为一组" / "故归入一组"  ← 核心！
- "可合并" / "应合并"
- "完全一致"
```

**SEPARATE indicators**:
```
- "单独保留" / "保持独立"
- "不宜合并"
```

### V3.0设计哲学

> **从"教育LLM"到"演示给LLM看"**

- V2.0: 详细解释原则，希望LLM理解
- V3.0: 直接展示真实案例，让LLM模仿

> **从"全面覆盖"到"聚焦重点"**

- V2.0: 列举所有可能情况
- V3.0: 聚焦最关键的pattern

> **从"复杂规则"到"简单问题"**

- V2.0: 5步验证流程
- V3.0: 3个问题（Q1/Q2/Q3）

### 期望效果

V3.0应该能够：
- ✅ 正确检测"故归入一组"类型的不一致
- ✅ 更快完成验证（prompt更短）
- ✅ 更容易维护和理解
- ✅ 减少误报和漏报

---

**版本历史**:
- V1.0: 初始版本，检测范围过广
- V2.0: 聚焦验证范围，但prompt过长
- V3.0: 极简重构，使用真实案例
