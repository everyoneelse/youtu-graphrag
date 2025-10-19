# 属性关系去重策略修复

## 问题描述

### 原始问题

在对 `has_attribute` 类型的关系进行语义去重时，LLM 会**过度合并**不同的属性值。

**错误案例**：
```
Head: 魔角效应 (MRI伪影)
Relation: has_attribute

候选属性：
[1] "角度依赖性、组织依赖性、TE依赖性" (三个特点的概括)
[2] "T2弛豫时间最多可延长两倍以上" (具体数值)

❌ 错误结果：LLM 将它们合并了
理由："都来自同一上下文，都是魔角效应的属性"
```

**为什么这是错误的**？
- [1] 和 [2] 是**完全不同的属性信息**
- [1] 是对依赖性特征的概括
- [2] 是对T2延长程度的具体描述
- 它们应该作为独立的属性保留

### 根本原因

原 prompt 的指令过于宽泛：
```
"Group tails that refer to the same real-world entity or express the same fact."
```

对于属性关系，这会导致：
- ✅ 同一实体 → 但不是同一属性！
- ✅ 都是事实 → 但是不同的事实！
- ❌ 错误地合并

## 解决方案

### 1. 添加属性专用的 Prompt

在 `config/base_config.yaml` 中添加了新的 `attribute` prompt 类型：

```yaml
semantic_dedup:
  general: |-
    # ... 原有的通用 prompt ...
  
  attribute: |-
    You are a knowledge graph curation assistant.
    Your task is to identify and merge ONLY duplicate or redundant attribute values.
    
    CRITICAL INSTRUCTIONS for attribute deduplication:
    1. ONLY merge if attribute values are truly identical or redundant:
       - Same attribute expressed differently
       - Complete redundancy
    
    2. NEVER merge if:
       - Attributes describe different properties
       - Attributes have different values or measurements
       - Attributes describe different aspects
       - Attributes come from the same context but convey different information
    
    3. When in doubt, keep them separate
```

### 2. 自动 Prompt 选择

修改了 `_build_semantic_dedup_prompt` 函数，自动根据 relation 类型选择 prompt：

```python
# Auto-detect prompt type based on relation
attribute_relations = {"has_attribute", "attribute", "property", "has_property", "characteristic"}
relation_lower = relation.lower() if relation else ""
if relation_lower in attribute_relations or "attribute" in relation_lower:
    prompt_type = "attribute"
    logger.debug(f"Auto-selected 'attribute' prompt type for relation: {relation}")
```

**触发条件**：
- 关系名为：`has_attribute`, `attribute`, `property`, `has_property`, `characteristic`
- 或关系名包含 `"attribute"` 字符串

### 3. 添加 Fallback Prompt

添加了 `DEFAULT_ATTRIBUTE_DEDUP_PROMPT` 常量，当配置文件中没有 `attribute` prompt 时使用。

## 使用方法

### 自动模式（推荐）

**什么都不需要做！**

系统会自动检测关系类型：
```python
# 自动使用 attribute prompt
_semantic_deduplicate_group(head_id, "has_attribute", edges)
_semantic_deduplicate_group(head_id, "property", edges)

# 自动使用 general prompt
_semantic_deduplicate_group(head_id, "related_to", edges)
_semantic_deduplicate_group(head_id, "keyword_of", edges)
```

### 手动指定（可选）

如果需要强制指定 prompt 类型，在配置中设置：

```yaml
construction:
  semantic_dedup:
    enabled: true
    prompt_type: "attribute"  # 强制使用 attribute prompt
```

## 效果对比

### 修复前 ❌

```json
{
  "groups": [
    {
      "members": [1, 2],
      "representative": 1,
      "rationale": "都来自同一上下文，都是魔角效应的属性"
    }
  ]
}
```
→ **错误**：不同的属性被合并了

### 修复后 ✅

```json
{
  "groups": [
    {
      "members": [1],
      "representative": 1,
      "rationale": "Unique attribute describing three types of dependencies"
    },
    {
      "members": [2],
      "representative": 2,
      "rationale": "Unique attribute describing T2 relaxation time extension"
    }
  ]
}
```
→ **正确**：不同属性保持独立

## 支持的 Relation 类型

### 自动使用 Attribute Prompt

以下关系会自动使用严格的属性去重策略：

| Relation | 说明 | 示例 |
|----------|------|------|
| `has_attribute` | 实体具有属性 | (魔角效应, has_attribute, "角度依赖性") |
| `attribute` | 属性关系 | (MRI, attribute, "分辨率高") |
| `property` | 属性/性质 | (扫描仪, property, "3T磁场强度") |
| `has_property` | 具有性质 | (T2WI, has_property, "高信号") |
| `characteristic` | 特征 | (伪影, characteristic, "条状") |
| 任何包含 "attribute" 的关系 | - | (实体, some_attribute_relation, 值) |

### 使用 General Prompt

其他关系使用宽松的通用去重策略：

| Relation | 说明 | 示例 |
|----------|------|------|
| `related_to` | 相关实体 | (深度学习, related_to, 神经网络) |
| `keyword_of` | 关键词 | (深度学习, keyword_of, 社区A) |
| `has_component` | 组成部分 | (MRI系统, has_component, 梯度线圈) |
| 其他 | - | - |

## Prompt 设计原则

### Attribute Prompt（严格）

**原则**：只有真正完全相同或冗余的属性才合并

**应该合并**：
- ✅ "颜色: 红色" ←→ "color: red" (相同属性，不同语言)
- ✅ "高度: 10cm" ←→ "高度: 10厘米" (相同属性，不同单位)
- ✅ "温度是37度" ←→ "37度" (完全冗余)

**不应该合并**：
- ❌ "角度依赖性" ←→ "T2延长两倍" (不同属性)
- ❌ "长度10cm" ←→ "宽度5cm" (不同属性，即使都是尺寸)
- ❌ "特点1: A" ←→ "特点2: B" (不同的特点)

### General Prompt（宽松）

**原则**：指向同一实体或表达同一事实的不同表述可以合并

**应该合并**：
- ✅ "deep learning" ←→ "深度学习" ←→ "DL" (同一概念)
- ✅ "neural network model" ←→ "神经网络" (同一实体)

## 配置示例

### 场景1：医疗知识图谱（有很多属性）

```yaml
construction:
  semantic_dedup:
    enabled: true
    embedding_threshold: 0.85
    # 不需要设置 prompt_type，系统会自动识别
```

### 场景2：强制所有关系使用严格模式

```yaml
construction:
  semantic_dedup:
    enabled: true
    embedding_threshold: 0.90  # 提高阈值
    prompt_type: "attribute"    # 强制使用严格模式
```

### 场景3：自定义 Attribute Prompt

```yaml
prompts:
  semantic_dedup:
    attribute: |-
      # 你的自定义 prompt
      # 可以根据具体领域调整指令
      ...
```

## 技术细节

### 修改的文件

1. **`models/constructor/kt_gen.py`**
   - 添加 `DEFAULT_ATTRIBUTE_DEDUP_PROMPT`
   - 修改 `_build_semantic_dedup_prompt` 函数
   - 添加自动 prompt 选择逻辑

2. **`config/base_config.yaml`**
   - 添加 `semantic_dedup.attribute` prompt 模板

### 代码变更摘要

```python
# 新增常量
DEFAULT_ATTRIBUTE_DEDUP_PROMPT = """..."""

# 修改函数
def _build_semantic_dedup_prompt(...):
    # Auto-detect prompt type based on relation
    if prompt_type == "general":
        attribute_relations = {...}
        if relation_lower in attribute_relations or "attribute" in relation_lower:
            prompt_type = "attribute"
    
    # Fallback to appropriate default
    try:
        return self.config.get_prompt_formatted("semantic_dedup", prompt_type, ...)
    except Exception:
        if prompt_type == "attribute":
            return DEFAULT_ATTRIBUTE_DEDUP_PROMPT.format(...)
        else:
            return DEFAULT_SEMANTIC_DEDUP_PROMPT.format(...)
```

## 验证方法

### 1. 查看日志

启用 debug 日志，查看 prompt 选择：

```python
logger.debug(f"Auto-selected 'attribute' prompt type for relation: {relation}")
```

### 2. 检查中间结果

启用中间结果保存：
```yaml
save_intermediate_results: true
```

查看生成的 JSON 文件中的 `llm_groups` 部分，检查：
- 不同属性是否被正确分离
- `rationale` 字段的解释是否合理

### 3. 统计去重率

对比修复前后的去重率：
- **修复前**：属性去重率可能过高（>30%）
- **修复后**：属性去重率应该较低（<10%），因为大部分属性都是独特的

## 最佳实践

1. **对于属性密集的知识图谱**
   - 让系统自动检测（推荐）
   - 或强制使用 `prompt_type: "attribute"`

2. **对于实体密集的知识图谱**
   - 使用默认的 `prompt_type: "general"`

3. **监控去重效果**
   - 启用 `save_intermediate_results: true`
   - 定期检查去重结果是否合理
   - 根据实际情况调整 `embedding_threshold`

4. **自定义领域知识**
   - 如果默认 prompt 效果不好
   - 可以在配置文件中自定义 `attribute` prompt
   - 添加领域特定的示例和指令

## 向后兼容性

- ✅ 不影响现有配置
- ✅ 默认行为：自动检测（对大部分场景更友好）
- ✅ 可以通过配置禁用自动检测
- ✅ 所有原有功能保持不变

## 总结

这次修复解决了属性去重中的**过度合并**问题，核心改进：

1. ✅ 添加了属性专用的严格去重 prompt
2. ✅ 实现了基于 relation 类型的自动 prompt 选择
3. ✅ 保持了向后兼容性
4. ✅ 提供了灵活的配置选项

**结果**：对于 `has_attribute` 等属性关系，只有真正相同的属性才会被合并，避免了信息损失！
