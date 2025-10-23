# Semantic Dedup Validation V3.0 - 设计笔记

## 📅 日期: 2025-10-23

## 🎯 核心问题

用户发现即使V2.0的prompt明确要求检测"rationale说合并但未合并"的不一致，LLM仍然没有检测到实际案例：

### 用户的真实案例

```python
输入groups:
[
  {
    'representative': 1,
    'members': [1],
    'rationale': '"振铃伪影"侧重描述同心条纹的"振铃"视觉特征，与Gibbs现象是同一机制的不同命名，语境中常互换，故单独保留并作为该别名组的代表。'
  },
  {
    'representative': 4,
    'members': [4],
    'rationale': '"边缘振荡伪影"强调边界振荡的物理过程，与"振铃伪影"视角相同，可视为同一别名，故归入一组。'
  }
]
```

**问题分析**：
- Group 1的rationale明确说：**"故归入一组"**（应该归入到"振铃伪影"所在的Group 0）
- 但实际members只有[4]，没有包含Group 0的[1]
- 这是明显的不一致，但LLM没有检测出来

**输出结果**：LLM返回的groups与输入完全一样，没有检测到任何不一致

## 🔍 根本原因

V2.0的prompt虽然内容正确，但存在以下问题：

1. **太长太复杂** - 150+行，关键信息被淹没
2. **视觉干扰** - 过多的装饰线和表情符号，分散注意力
3. **重复内容** - 同一概念用多种方式解释，反而让LLM困惑
4. **缺少具体案例** - 没有用类似"故归入一组"的真实案例作为示例

## ✅ V3.0解决方案

### 1. 大幅简化prompt

**Before (V2.0):** ~150行，包含大量解释和装饰

**After (V3.0):** ~80行，只保留核心内容

### 2. 突出关键短语

特别强调中文的**关键决策短语**：

```
⚠️ CRITICAL: "故归入一组" / "归入XX组" = says to MERGE
   → Check if members actually include the referenced group's items!
```

这是用户案例中出现的确切短语！

### 3. 使用真实案例作为示例

用用户实际遇到的"振铃伪影"案例作为Example，让LLM看到完全相同的pattern：

```python
Input groups:
- Group 0: {members: [1], rationale: "振铃伪影，单独保留作为代表"}
- Group 1: {members: [4], rationale: "边缘振荡伪影，与振铃伪影视角相同，故归入一组"}

Step 1: What does Group 1's rationale conclude?
  → "故归入一组" = should MERGE into Group 0

Step 2: What do Group 1's members show?
  → members: [4] only = SEPARATE (doesn't include Group 0's [1])

Step 3: Match?
  → NO! Conclusion=MERGE, Structure=SEPARATE
  → ❌ INCONSISTENT
```

### 4. 步骤式推理

用明确的Step 1/2/3展示推理过程，而不是一段文字描述：

```
Step 1: What does the rationale conclude?
Step 2: What do the members show?
Step 3: Do they match?
```

这让LLM更容易follow这个推理模式。

### 5. 去除冗余

删除了：
- 过多的装饰线（═══）
- 重复的说明
- 冗长的解释
- 无关的CONTEXT部分（head/relation在此验证中不重要）

## 📊 V2.0 vs V3.0 对比

| 方面 | V2.0 | V3.0 |
|------|------|------|
| **Prompt长度** | ~150行 | ~80行 (-47%) |
| **视觉复杂度** | 高（多种装饰） | 低（简洁线条） |
| **关键短语** | 列表形式 | 突出显示+解释 |
| **示例** | 通用案例 | 用户真实案例 |
| **推理展示** | 文字描述 | 步骤式（Step 1/2/3） |
| **重点** | 分散 | 聚焦"故归入一组" |

## 🎯 V3.0的核心设计原则

### 1. 极简主义
> "Less is more" - 去除一切不必要的内容

### 2. 具体化
> 用用户的真实案例，而不是虚构的示例

### 3. 可操作性
> 给出明确的3步推理流程，LLM只需follow

### 4. 关键词突出
> "故归入一组"这种关键短语必须醒目标注

## 🔑 关键改进点

### 特别强调的中文短语

```
MERGE conclusion indicators:
- "可合并", "应合并", "完全一致"
- "归入一组", "归为一组"  ← 新增
- "故归入一组"  ← 用户案例中的确切短语！
- "归入XX组"
- "视为同一"
```

### 验证流程简化

**Before:**
```
1. Read each group's rationale carefully
2. Check if the members array matches the rationale's claim
3. **ESPECIALLY**: If rationale mentions merging with other groups, verify those groups are actually merged
4. Use your understanding of semantics and coreference
5. Consider the INTENT behind the rationale
```

**After:**
```
For each group, ask:
  Q1: What does the rationale CONCLUDE? (merge OR separate)
  Q2: What do the members show? (merged OR separate)
  Q3: Do they match?
```

从5步简化到3个问题！

## 📝 关键短语全列表

### MERGE indicators（说要合并）
- 可合并 / 可以合并 / 应该合并 / 宜合并
- 完全一致 / 信息一致 / 信息完全一致
- 无差异 / 信息无差异
- 同一 / 相同 / 等同
- **归入一组** / **归为一组** / **故归入一组** ← 重点！
- **归入XX组** / **与XX归为一组**

### SEPARATE indicators（说要独立）
- 保持独立 / 单独保留
- 不宜合并 / 不应合并
- 保留为独立组

## 🚀 预期效果

V3.0应该能够：

1. ✅ 正确检测用户的"故归入一组"案例
2. ✅ 更快速地完成验证（prompt更短）
3. ✅ 减少误报（去除了内容准确性检查）
4. ✅ 更容易被人类理解和维护

## 🎯 测试要点

用用户的真实案例测试：

```python
groups = [
    {'members': [1], 'rationale': '...故单独保留...'},
    {'members': [4], 'rationale': '...故归入一组'}  # 应该检测到不一致！
]
```

期望输出：
```json
{
  "has_inconsistencies": true,
  "inconsistencies": [{
    "group_ids": [1, 0],
    "description": "Group 1 says '故归入一组' but is separate"
  }],
  "corrected_groups": [
    {"members": [1, 4], "representative": 1, "rationale": "..."}
  ]
}
```

## 💡 设计哲学

### 从"教育"到"演示"

**V2.0思路**：详细解释给LLM听，让它理解原则
- 结果：LLM被淹没在大量文字中

**V3.0思路**：直接展示给LLM看，让它模仿
- 用真实案例step by step演示
- 用它会遇到的确切短语作为关键词

### 从"全面"到"聚焦"

**V2.0思路**：列举所有可能的情况和短语
- 结果：太全面反而失去重点

**V3.0思路**：聚焦最重要的pattern
- "故归入一组" = 核心pattern
- 其他短语作为补充

## 📌 后续优化方向

如果V3.0仍然不能检测，考虑：

1. **进一步简化** - 可能还是太长
2. **Few-shot learning** - 提供2-3个真实案例
3. **结构化输出** - 使用JSON schema强制输出格式
4. **分步调用** - 先让LLM提取conclusion，再比对structure

---

**版本**: V3.0  
**更新时间**: 2025-10-23  
**状态**: ✅ 已完成，待测试  
**核心改进**: 极简设计 + 真实案例 + 关键短语突出
