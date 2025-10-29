# Context Verification Mechanism for Head Deduplication

## 概述

本文档说明在head_dedup的LLM去重中新增的**Context验证机制**。该机制专门用于验证待去重实体的context信息，确保LLM在做共指决策时能够充分利用和验证上下文信息。

## 背景

在使用`use_hybrid_context`开关时，待去重的实体所在的context（包括图关系和源文本chunk）会被加入到prompt中。然而，之前的prompt缺少专门针对context的验证机制，可能导致：

1. **忽略context信息**: LLM可能不会充分分析提供的context
2. **错过矛盾信息**: context中的冲突信息可能被忽略，导致错误合并
3. **信息不足时过于激进**: 即使context信息不足，也可能做出合并决策
4. **缺乏系统化分析**: 没有强制要求LLM系统化地分析context

## 新增的Context验证机制

### 验证步骤（5个强制步骤）

#### Step A: Context Relevance Check (相关性检查)
验证提供的context信息是否真实描述这两个实体：
- ✓ 关系和文本是否真的与实体相关
- ✓ Context信息是否直接相关于比较的实体
- ✗ 如果context缺失、不相关或过于模糊 → 标注在rationale中并应用保守原则

#### Step B: Context Consistency Check (一致性检查) 🔴 关键
检查两个实体的context是否包含矛盾信息：
- **时间属性冲突**: 成立日期、时期、年龄
- **空间属性冲突**: 地点、地理信息
- **类型/类别冲突**: 人 vs 组织，公司 vs 产品
- **功能角色冲突**: 创始人 vs 员工，父公司 vs 子公司
- **数量属性冲突**: 不同的规模、人口、数量

**规则**: 如果存在**任何**关键矛盾 → 它们是不同实体，回答NO

#### Step C: Context Completeness Assessment (完整性评估)
评估提供的context是否足够做出可靠的共指决策：
- **高置信度**: 多个一致的关系，清晰的context
- **中置信度**: 一些关系，部分context
- **低置信度**: 最少的信息，不清晰的context

**规则**: 如果信息不足且不确定性高 → 应用保守原则（回答NO）

#### Step D: Relationship Pattern Analysis (关系模式分析)
比较两个实体的关系模式：
- 是否共享共同的关系类型？
- 共享的关系是否与"同一实体"假设一致？
- 关系目标是否对齐还是冲突？

**强共指证据**:
- 多个重叠关系且目标相同或等价
- 关系形成一致且连贯的模式
- 无冲突的关系信息

**反共指证据**:
- 关系暗示层级结构（所有者-被所有，父-子）
- 关系描述不同的范围或领域
- 关系目标相互矛盾

#### Step E: Source Text Validation (源文本验证)
当启用`hybrid_context`时验证源文本：
- 文本是否真的提到这些实体名称？
- 文本context是否支持或反驳共指假设？
- 实体在源文本中的使用方式是否相似或不同？

**强文本证据**:
- 实体在文本中可互换使用
- 文本明确陈述等价性（例如："也被称为"，"缩写为"）
- 跨文本的一致使用模式

### 决策流程

```
PHASE 1: CONTEXT VERIFICATION (执行步骤 A-E)
  → 验证context相关性、一致性、完整性
  → 分析关系模式和源文本
  → 记录发现的任何问题或顾虑

PHASE 2: COREFERENCE DETERMINATION (共指判断)
  → 检查名称是否为同一实体的变体
  → 验证关系模式是否一致
  → 查找矛盾 - 如有任何关键关系冲突 → 不同实体
  → 应用替换测试
  → 如果在context验证后仍不确定 → 回答NO

PHASE 3: REPRESENTATIVE SELECTION (代表选择)
  → 仅在确定共指后执行
  → 基于形式性、领域惯例、信息丰富度等选择
```

### 输出要求

rationale必须包含三部分：
1. **Context验证摘要** (步骤A-E的结果)
2. **共指决策推理**
3. **如果共指，代表选择推理**

## 示例

### 示例1: 应该合并（context支持）

```
Entity 1 (entity_100): "UN"
Relations: [founded→1945, member→United States, headquarters→New York]

Entity 2 (entity_150): "United Nations"
Relations: [established→1945, member→USA]
```

**输出**:
```json
{
  "is_coreferent": true,
  "preferred_representative": "entity_100",
  "rationale": "(Context Verification) Step A: Context相关，都描述国际组织。Step B: 一致 - 成立年份1945匹配，成员对齐。Step C: 信息充足，共5个关系。Step D: 强模式对齐。Step E: N/A。(Coreference) 'UN'是'United Nations'的标准缩写，所有关系一致，通过替换测试。(Representative) 选择entity_100 (UN)：(1)更多关系(3 vs 2)，(2)'UN'是国际关系语境中广泛认可的标准形式。"
}
```

### 示例2: 不应合并（context揭示矛盾）

```
Entity 1 (entity_300): "张三"
Relations: [works_at→清华大学, age→45, position→教授]

Entity 2 (entity_350): "张三"
Relations: [studies_at→北京大学, age→22, status→学生]
```

**输出**:
```json
{
  "is_coreferent": false,
  "preferred_representative": null,
  "rationale": "(Context Verification) Step A: Contexts相关。Step B: 关键矛盾 - 年龄不同(45 vs 22)，角色冲突(教授 vs 学生)，不同机构。Step C: 充足信息显示冲突。Step D: 完全不同的模式。(Decision) Context验证揭示矛盾，它们是不同的同名人物。应用保守原则。"
}
```

### 示例3: 信息不足（应回答NO）

```
Entity 1 (entity_500): "李明"
Relations: [age→30]

Entity 2 (entity_550): "李明"
Relations: [gender→male]
```

**输出**:
```json
{
  "is_coreferent": false,
  "preferred_representative": null,
  "rationale": "(Context Verification) Step A: 最小context。Step B: 无矛盾但也无确认信息。Step C: 信息不足 - 仅2个通用属性，无法可靠确定身份。Step D: 无有意义的模式。(Decision) context不足无法做出可靠决策，应用保守原则避免错误合并。"
}
```

## 修改的文件

### 1. `/workspace/config/base_config.yaml`
- 在`prompts.head_dedup.with_representative_selection`中添加了完整的Context验证机制
- 更新了DECISION PROCEDURE，明确分为3个PHASE
- 更新了OUTPUT FORMAT的rationale要求
- 添加了5个包含context验证的示例

### 2. `/workspace/config_llm_driven_representative_example.yaml`
- 添加了完整的Context验证步骤（Steps A-E）
- 更新了DECISION PROCEDURE
- 更新了OUTPUT FORMAT的rationale要求

### 3. `/workspace/HEAD_DEDUP_LLM_REPRESENTATIVE_SELECTION.md`
- 重构了文档结构，添加了"CONTEXT VERIFICATION (MANDATORY)"部分
- 详细说明了5个验证步骤
- 添加了包含context验证的完整示例
- 明确了决策流程的3个阶段

## 使用方法

### 配置开启

在配置文件中启用hybrid context:

```yaml
construction:
  semantic_dedup:
    head_dedup:
      enabled: true
      use_hybrid_context: true  # 开启混合context
      max_relations_context: 10  # 最多包含的关系数
```

### 代码调用

```python
# 使用LLM驱动的代表选择 + Context验证
stats = builder.deduplicate_heads_with_llm_v2(
    enable_semantic=True,
    similarity_threshold=0.85
)
```

### Context验证的自动执行

当使用`_build_head_dedup_prompt_v2()`方法时：
1. 自动收集图关系context (`_collect_node_context()`)
2. 如果`use_hybrid_context=True`，自动添加chunk text context (`_collect_chunk_context()`)
3. 将完整context填充到prompt模板
4. LLM按照prompt中的强制步骤执行context验证

## 优势

1. **系统化验证**: 强制LLM系统化地检查context的各个方面
2. **减少错误合并**: 通过一致性检查捕获矛盾信息
3. **保守原则**: 在信息不足时明确要求保守决策
4. **可追溯性**: rationale中必须包含验证结果，便于审计
5. **混合context利用**: 充分利用图关系和文本chunk的信息
6. **层级关系识别**: 专门识别所有权、父子等层级关系，避免错误合并

## 注意事项

1. **Token消耗**: Context验证会增加prompt长度，特别是在`use_hybrid_context=True`时
2. **处理时间**: 更详细的验证可能略微增加LLM处理时间
3. **保守倾向**: 机制设计偏向保守，可能减少一些真实的合并，但减少错误合并
4. **Step E可选**: 源文本验证仅在`use_hybrid_context=True`时适用

## 验证状态

✅ 所有配置文件YAML语法验证通过
✅ Prompt模板已更新
✅ 文档已同步更新
✅ 示例已包含context验证演示

---

**更新日期**: 2025-10-29  
**版本**: v1.0  
**相关配置**: `use_hybrid_context`, `max_relations_context`  
**相关代码**: `head_dedup_llm_driven_representative.py`
