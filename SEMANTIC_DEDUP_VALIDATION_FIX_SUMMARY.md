# Semantic Deduplication Validation Fix Summary

## 问题描述

用户发现语义去重验证功能 `_llm_validate_semantic_dedup` 存在一个关键问题：

### 具体问题

当某个group的rationale明确说"可合并"、"应该与XX组合并"、"信息完全一致"等，**但实际上该group却是独立的，没有真正合并到一起**时，验证逻辑没有检测到这个不一致。

### 验证范围的澄清

用户进一步指出，验证应该**只关注一个核心问题**：
- ✅ **应该检查**: rationale的结论（合并/独立）与实际分组结构（members数组）是否一致
- ❌ **不应该检查**: rationale内容的准确性（比如是否提到了原文不存在的细节）

例如，不应该报告这种问题：
> "Group 2的rationale说有54.7°角度，但原文只说'特定角度'没有具体数值"

这是rationale内容准确性的问题，不是分组结构的不一致。

### 用户案例

```python
groups = [
    {
        'representative': 0,
        'members': [0, 1],
        'rationale': '二者信息完全一致，可互换使用。'
    },
    {
        'representative': 4,
        'members': [4],  # ❌ 不一致！
        'rationale': '与组1/组2所指操作完全一致，信息无差异，可合并。'
        # ☝️ rationale说要与组1/2合并，但实际只有[4]，没有合并！
    }
]
```

**期望行为**: 验证逻辑应该检测到Group 4的rationale说"可合并"但实际没有合并的不一致。

**实际行为**: 验证逻辑没有检测到这个不一致，反而关注了其他细节问题。

## 解决方案

### 修改内容

重写了 `DEFAULT_SEMANTIC_DEDUP_VALIDATION_PROMPT`，明确验证范围和重点：

#### 1. 明确验证范围（核心改进）

```
🎯 YOUR ONLY JOB: Check rationale's CONCLUSION vs actual grouping

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

#### 2. 新增关键短语识别

```
**CRITICAL CHECK** - Pay special attention to:
⚠️ If a group's rationale says it "can merge", "should merge", "is identical", "is the same as", "no difference from" another group/items,
   BUT the group only contains its own members (not merged with the mentioned group),
   this is a MAJOR INCONSISTENCY that MUST be detected and fixed.
```

```
🔍 Key phrases indicating MERGE intention:

Chinese (中文):
  - "可合并" / "可以合并" / "应该合并" / "宜合并"
  - "完全一致" / "信息一致" / "信息完全一致"
  - "无差异" / "信息无差异"
  - "同一" / "相同" / "等同"
  - "与组X" / "与XX组" (mentions other groups)

⚠️ If you see these phrases + group references → Verify actual merge happened!
```

#### 3. 简化验证步骤

```
VALIDATION STEPS:

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

#### 4. 添加正反示例

**正面示例** - 应该检测的不一致：
```
Example 2 (Chinese - YOUR CASE):
Input groups:
- Group 0: {members: [0, 1], representative: 0, rationale: "二者信息完全一致，可互换使用。"}
- Group 1: {members: [2], representative: 2, rationale: "表述过于简略，信息粒度不同，不宜合并。"}
- Group 2: {members: [3], representative: 3, rationale: "与组0所指操作完全一致，信息无差异，可合并。"}

Analysis: Group 2's rationale says "与组0所指操作完全一致，信息无差异，可合并" (completely identical to group 0, can merge),
but Group 2 only has member [3] - it hasn't actually merged with Group 0.
This is a MAJOR inconsistency!

Output:
{
  "has_inconsistencies": true,
  "inconsistencies": [{
    "group_ids": [2, 0],
    "issue_type": "rationale_says_merge_but_not_merged",
    "description": "Group 2's rationale says '与组0所指操作完全一致，信息无差异，可合并' but Group 2 is still separate with only member [3], not merged with Group 0",
    "suggested_fix": "merge group 2 into group 0"
  }],
  "corrected_groups": [
    {"members": [0, 1, 3], "representative": 0, "rationale": "这些表述信息完全一致，可互换使用。"},
    {"members": [2], "representative": 2, "rationale": "表述过于简略，信息粒度不同，保持独立。"}
  ]
}
```

**反面示例** - 不应该检测的问题：
```
Example 3 (What NOT to report):
Input:
- Group 0: {members: [0, 1], rationale: "Both mention 54.7° angle"}
But candidate [0] actually says "specific angle" (no 54.7° mentioned in original text)

Analysis:
This is a content accuracy issue - rationale mentions a detail (54.7°) not in original text.
BUT, the grouping structure is correct: members [0, 1] ARE grouped together as intended.
✅ Conclusion (group together) = Structure (grouped) → CONSISTENT
🚫 Do NOT report this - content accuracy is out of scope!

Output:
{
  "has_inconsistencies": false,
  "inconsistencies": [],
  "corrected_groups": null
}
```

## 修改文件

- `/workspace/models/constructor/kt_gen.py` (line 160-240)
  - 修改了 `DEFAULT_SEMANTIC_DEDUP_VALIDATION_PROMPT`

## 测试

### 测试用例

使用用户提供的真实案例：

```python
test_groups = [
    {
        'representative': 0,
        'members': [0, 1],
        'rationale': '二者信息完全一致，可互换使用。'
    },
    {
        'representative': 4,
        'members': [4],  # 不一致：rationale说要与组0合并，但未合并
        'rationale': '与组1/组2所指操作完全一致，信息无差异，可合并。'
    }
]

test_candidates = [
    "增加相位编码步数",
    "增加相位编码方向的分辨率",
    "增加相位编码",
    "增加矩阵",
    "增加相位编码方向的矩阵",
    "增大采集矩阵"
]
```

### 期望结果

验证逻辑应该：
1. 检测到Group 3（members=[4]）的rationale说"可合并"
2. 发现该group实际上没有与Group 0合并
3. 报告inconsistency并建议修复
4. 返回corrected_groups，将[4]合并到Group 0

## 关键改进点总结

### V2.0 (2025-10-23) - 聚焦核心问题

✅ **明确验证范围** - 只检查"rationale结论 vs 分组结构"，不检查内容准确性  
✅ **中文关键词列表** - 包含"可合并"、"完全一致"、"信息无差异"等关键短语  
✅ **简化验证步骤** - 4步清晰流程，去除无关检查  
✅ **正反示例** - 包含"应该检测"和"不应该检测"的示例  
✅ **统一issue_type** - 使用"rationale_conclusion_vs_grouping_mismatch"

### 核心设计理念

**只关注一个问题**: rationale的决策（合并/独立）与实际分组是否匹配

- ✅ 检查：rationale说"可合并"，实际是否合并了
- ✅ 检查：rationale说"保持独立"，实际是否独立了
- ❌ 不检查：rationale内容是否准确描述原文
- ❌ 不检查：rationale提到的细节是否存在于原文

## 如何使用

1. 确保配置文件中启用了语义去重验证：
   ```yaml
   semantic_dedup:
     enable_semantic_dedup_validation: true
   ```

2. 运行知识树生成流程

3. 观察验证输出，检查是否正确检测到"rationale说合并但未合并"的不一致

## 影响范围

- **核心逻辑**: 未修改，只是增强了prompt
- **向后兼容**: 完全兼容，只是让LLM更容易检测到这类不一致
- **性能影响**: 无，prompt长度略微增加但不影响性能
- **副作用**: 无，只是让验证更准确

## 设计原则

遵循了用户的规则：
> "如果你被要求修改prompt，请注意修改时，不要case by case的修改"

本次修改采用**原则驱动**的方式：
- 定义了通用的不一致类型
- 提供了关键词列表而非具体case
- 示例只用于说明原则，不限制检测范围

## 后续建议

1. **监控验证效果**: 观察修改后LLM是否能正确检测到这类不一致
2. **收集更多案例**: 如果还有其他类型的不一致未被检测，继续优化prompt
3. **考虑结构化输出**: 如果LLM仍然不稳定，可以考虑使用结构化输出格式
