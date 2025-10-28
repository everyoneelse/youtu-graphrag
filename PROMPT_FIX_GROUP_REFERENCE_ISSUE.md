# 实体去重Prompt改进：解决组引用混乱问题

## 问题描述

在实体去重的LLM输出中，rationale经常包含对其他组的引用，例如：

```
"rationale": "\"增加相位编码方向的矩阵\"即扩大相位编码步数，与组1/组2所指操作完全一致，信息无差异，可合并。"
```

这里的"组1/组2"引用存在以下问题：

1. **编号系统不清晰**：
   - 候选项使用从1开始的编号：`[1]`, `[2]`, `[3]`, ...
   - 但groups数组的索引是从0开始的
   - LLM提到"组1"时，不清楚是指groups[0]还是groups[1]

2. **可读性差**：
   - 用户需要来回对照才能理解"组1/组2"指的是什么
   - 跨组引用增加了理解成本

3. **维护困难**：
   - 如果组的顺序变化，引用就会失效
   - 不利于独立理解每个组的rationale

## 解决方案

在所有去重相关的prompt中添加**RATIONALE/DESCRIPTION WRITING GUIDELINES**，明确指导LLM：

### 核心原则

1. **独立描述**：每个rationale应独立解释为什么这些成员属于同一组
2. **使用候选项编号**：引用具体项时使用候选项编号（如`[1]`和`[2]`）
3. **禁止跨组引用**：避免使用"组1"、"与组2一致"等跨组引用
4. **聚焦身份描述**：描述该组实体的身份，而非与其他组的关系

## 修改的Prompt

### 1. DEFAULT_SEMANTIC_DEDUP_PROMPT（实体去重）

添加第6点：
```
6. **RATIONALE WRITING GUIDELINES**:
   - Each rationale should INDEPENDENTLY explain why its members are coreferent
   - Use candidate numbers (e.g., "[1] and [2]") to refer to specific items
   - DO NOT reference other groups (e.g., avoid "same as group 1" or "与组1一致")
   - If comparing with non-members, explain why they are DIFFERENT entities
   - Focus on describing the IDENTITY of this group's entity, not relationships to other groups
```

### 2. DEFAULT_ATTRIBUTE_DEDUP_PROMPT（属性值去重）

添加第6点：
```
6. **RATIONALE WRITING GUIDELINES**:
   - Each rationale should INDEPENDENTLY explain why its members are equivalent
   - Use candidate numbers (e.g., "[1] and [2]") to refer to specific items
   - DO NOT reference other groups (e.g., avoid "same as group 1" or "与组1一致")
   - If comparing with non-members, explain why they are DIFFERENT values
   - Focus on describing the VALUE of this group, not relationships to other groups
```

### 3. DEFAULT_LLM_CLUSTERING_PROMPT（聚类）

添加第5点：
```
5. **DESCRIPTION WRITING GUIDELINES**:
   - Each description should INDEPENDENTLY explain why its members are grouped together
   - Use candidate numbers (e.g., "[1] and [2]") to refer to specific items if needed
   - DO NOT reference other clusters (e.g., avoid "same as cluster 1" or "与簇1一致")
   - Focus on describing the COMMON SEMANTIC THEME of this cluster's members
```

## 预期效果

### 改进前的rationale示例：
```json
{
  "members": [4],
  "representative": 4,
  "rationale": "\"增加相位编码方向的矩阵\"即扩大相位编码步数，与组1/组2所指操作完全一致，信息无差异，可合并。"
}
```

**问题**：用户不清楚"组1/组2"是什么

### 改进后的rationale示例：
```json
{
  "members": [0, 1, 4],
  "representative": 0,
  "rationale": "候选项[1]\"增加相位编码步数\"、[2]\"增加相位编码方向的分辨率\"和[5]\"增加相位编码方向的矩阵\"都指向同一操作：在相位编码方向采集更多步级以提升空间分辨率。这三个表述是同一技术手段的不同表达方式，具有引用一致性。"
}
```

**改进**：
- 使用候选项编号`[1]`, `[2]`, `[5]`清晰指明具体项
- 独立描述该组的实体身份
- 不引用其他组

## 文件修改

- **文件**: `/workspace/models/constructor/kt_gen.py`
- **修改内容**:
  - `DEFAULT_SEMANTIC_DEDUP_PROMPT` (第70-87行)
  - `DEFAULT_ATTRIBUTE_DEDUP_PROMPT` (第146-162行)
  - `DEFAULT_LLM_CLUSTERING_PROMPT` (第364-378行)

## 测试验证

运行测试脚本验证所有prompt都包含新的指导原则：

```bash
cd /workspace
python3 test_prompt_guidelines.py
```

测试结果：✓ 所有prompt都包含完整的指导原则

## 遵循的设计原则

本次修改遵循了用户规则中的重要原则：

> "如果你被要求修改prompt，请注意修改时，不要case by case的修改，如果采用case by case的方式修改，那要修改到什么时候"

我们采用的是**通用原则性指导**：
- 不是针对"组1/组2"这个特定case打补丁
- 而是建立了通用的rationale编写规范
- 这些规范适用于所有类型的去重和聚类场景

## 后续建议

1. **监控LLM输出质量**：观察新prompt是否有效减少跨组引用
2. **调整validation逻辑**：可以在validation prompt中也强化这些原则
3. **用户反馈**：收集实际使用中的rationale质量反馈

## 版本信息

- **修改日期**: 2025-10-23
- **修改分支**: cursor/group-similar-artifact-solutions-fe0b
- **相关Issue**: 实体去重结果中组引用编号不清晰的问题
