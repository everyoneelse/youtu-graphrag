# Context Usage Guidance for Head Deduplication

## 概述

本文档说明在head_dedup的LLM去重中新增的**Context使用指导**。该机制指导LLM如何使用context信息（关系和源文本）来做更准确的共指判断，而不是验证context本身。

## 背景

在使用`use_hybrid_context`开关时，待去重的实体所在的context（包括图关系和源文本chunk）会被加入到prompt中。然而，之前的prompt缺少专门针对context的验证机制，可能导致：

1. **忽略context信息**: LLM可能不会充分分析提供的context
2. **错过矛盾信息**: context中的冲突信息可能被忽略，导致错误合并
3. **信息不足时过于激进**: 即使context信息不足，也可能做出合并决策
4. **缺乏系统化分析**: 没有强制要求LLM系统化地分析context

## 新增的Context使用指导

Context包含两部分信息，在prompt中明确区分：
1. **Graph relationships**（图谱关系）：实体的结构化关系信息
2. **Source text**（源文本）：实体所在的原始chunk文本

这两种信息是帮助LLM做共指判断的**额外信息**，而不是需要验证的对象。指导原则如下：

### 4个使用原则

#### 1. **识别矛盾信息** (Identify contradictions)
如果contexts揭示了两个实体的矛盾信息 → 它们是不同实体，回答NO

示例：
- 年龄矛盾：45岁 vs 22岁
- 角色矛盾：教授 vs 学生
- 所属机构矛盾：清华大学 vs 北京大学

#### 2. **寻找支持证据** (Find supporting evidence)
如果contexts显示一致且互补的信息 → 支持共指假设

示例：
- 成立时间一致：founded→1945, established→1945
- 成员信息一致：member→United States, member→USA

#### 3. **评估信息充分性** (Assess information sufficiency)
如果context信息过于有限，无法做出可靠判断 → 应用保守原则，回答NO

示例：
- 仅有通用属性：age→30, gender→male
- 缺乏区分性信息

#### 4. **识别层级关系** (Recognize hierarchical relationships)
如果context显示一个实体拥有/包含/管理另一个实体 → 它们是不同实体，回答NO

示例：
- owned_by关系：Apple Store owned_by Apple Inc.
- 子公司关系：subsidiary_of

### 重要原则

**不要验证context本身** - 信任并使用context来做更好的共指决策

### 决策流程

```
PHASE 1: USE CONTEXT TO INFORM COREFERENCE DECISION (使用context辅助共指判断)
  → 使用提供的context识别矛盾或支持证据
  → 如果context揭示矛盾或层级关系 → 不同实体
  → 如果context信息不足 → 应用保守原则

PHASE 2: COREFERENCE DETERMINATION (共指判断)
  → 检查名称是否为同一实体的变体
  → 使用context验证关系模式是否一致
  → 查找context中的矛盾 - 如有任何关键信息冲突 → 不同实体
  → 应用替换测试
  → 如果不确定 → 回答NO

PHASE 3: REPRESENTATIVE SELECTION (代表选择)
  → 仅在确定共指后执行
  → 基于形式性、领域惯例、信息丰富度等选择
```

### 输出要求

rationale必须包含三部分：
1. **如何使用context** (怎样利用context信息做判断)
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
  "rationale": "(Context Usage) Contexts显示一致信息：成立年份1945匹配，成员对齐(United States/USA指同一国家)。未发现矛盾。Context支持这是同一实体的不同名称形式。(Coreference) 'UN'是'United Nations'的标准缩写，所有关系一致。(Representative) 选择entity_100 (UN)：(1)更多关系(3 vs 2)，(2)'UN'是广泛认可的标准形式。"
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
  "rationale": "(Context Usage) Contexts揭示关键矛盾：年龄不同(45 vs 22)，一个是清华大学教授，另一个是北京大学学生。这些矛盾表明它们是同名不同人。(Decision) 同名但context信息矛盾。应用保守原则。"
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
  "rationale": "(Context Usage) Contexts提供非常有限的信息：仅通用属性(年龄30、性别男)，很多人共享这些属性。无区分性信息来可靠判断是否同一人。(Decision) Context不足无法做出可靠决策。保守原则：回答NO避免错误合并。"
}
```

## 修改的文件

### 1. `/workspace/config/base_config.yaml`
- 在prompt中明确区分`{graph_context_1/2}`和`{chunk_context_1/2}`
- 添加了"Graph relationships:"和"Source text:"标签
- 更新了Context使用指导
- 更新了示例说明

### 2. `/workspace/config_llm_driven_representative_example.yaml`
- 同步修改prompt，区分graph relationships和source text
- 更新了Context使用指导

### 3. `/workspace/HEAD_DEDUP_LLM_REPRESENTATIVE_SELECTION.md`
- 更新prompt模板，区分两种context信息
- 更新文档说明

### 4. `/workspace/head_dedup_llm_driven_representative.py`
- 修改`_build_head_dedup_prompt_v2()`方法
- 分别传入`graph_context_1/2`和`chunk_context_1/2`
- 当`use_hybrid_context=False`时，chunk_context显示为"(Not available)"
- 更新`_get_embedded_prompt_template_v2()`函数签名

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

### Context的自动收集和区分

当使用`_build_head_dedup_prompt_v2()`方法时：
1. 自动收集图关系context (`_collect_node_context()`) → 填充到`{graph_context_1}`和`{graph_context_2}`
2. 如果`use_hybrid_context=True`，自动收集chunk text context (`_collect_chunk_context()`) → 填充到`{chunk_context_1}`和`{chunk_context_2}`
3. 如果`use_hybrid_context=False`，chunk_context显示为"(Not available)"
4. Prompt中明确区分"Graph relationships"和"Source text"，让LLM清楚知道信息来源

## 优势

1. **简洁清晰**: 不列举具体检查项，给LLM更多判断空间
2. **减少错误合并**: 强调识别矛盾信息和层级关系
3. **保守原则**: 在信息不足时明确要求保守决策
4. **正确定位**: Context是辅助信息，不是验证对象
5. **混合context利用**: 充分利用图关系和文本chunk的信息
6. **层级关系识别**: 专门识别所有权、父子等层级关系，避免错误合并

## 注意事项

1. **Token消耗**: Context会增加prompt长度，特别是在`use_hybrid_context=True`时
2. **保守倾向**: 机制设计偏向保守，可能减少一些真实的合并，但减少错误合并
3. **信任context**: 不要让LLM质疑context的相关性或质量，直接使用它来辅助判断

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
