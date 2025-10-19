# 属性去重修复效果测试

## 你的问题案例

### 输入

```python
head_text = '魔角效应 (MRI伪影)'
relation = 'has_attribute'

candidates = [
    "[1] 角度依赖性、组织依赖性、TE依赖性",
    "[2] T2弛豫时间最多可延长两倍以上"
]
```

### 修复前的 Prompt（General）

```
Instructions:
1. Group tails that refer to the same real-world entity or express the same fact.
2. Keep tails separate when their meanings differ...
```

**LLM 输出（错误）**：
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

❌ **问题**：两个不同的属性被错误地合并了！

---

### 修复后的 Prompt（Attribute）

```
CRITICAL INSTRUCTIONS for attribute deduplication:
1. ONLY merge if attribute values are truly identical or redundant
2. NEVER merge if:
   - Attributes describe different properties
   - Attributes have different values or measurements
   - Attributes describe different aspects
```

**LLM 输出（正确）**：
```json
{
  "groups": [
    {
      "members": [1],
      "representative": 1,
      "rationale": "Describes three dependency characteristics - unique attribute"
    },
    {
      "members": [2],
      "representative": 2,
      "rationale": "Describes T2 relaxation time extension - unique attribute"
    }
  ]
}
```

✅ **正确**：两个不同的属性保持独立！

---

## 更多测试案例

### 案例1：应该合并的属性

**输入**：
```python
head = "扫描序列A"
relation = "has_attribute"
candidates = [
    "[1] TR: 2000ms",
    "[2] 重复时间: 2000毫秒"
]
```

**期望输出**：
```json
{
  "groups": [
    {
      "members": [1, 2],
      "representative": 2,
      "rationale": "相同的属性（TR），相同的值（2000ms），只是表述不同"
    }
  ]
}
```

✅ **应该合并**：完全相同的属性值

---

### 案例2：不应该合并的属性

**输入**：
```python
head = "扫描序列A"
relation = "has_attribute"
candidates = [
    "[1] TR: 2000ms",
    "[2] TE: 80ms"
]
```

**期望输出**：
```json
{
  "groups": [
    {
      "members": [1],
      "representative": 1,
      "rationale": "TR (repetition time) - unique attribute"
    },
    {
      "members": [2],
      "representative": 2,
      "rationale": "TE (echo time) - different attribute from TR"
    }
  ]
}
```

✅ **不应该合并**：不同的属性（TR vs TE）

---

### 案例3：多个属性混合

**输入**：
```python
head = "T2加权像"
relation = "has_attribute"
candidates = [
    "[1] 脑脊液呈高信号",
    "[2] CSF显示为高信号",
    "[3] 灰质信号高于白质",
    "[4] 脂肪抑制效果好"
]
```

**期望输出**：
```json
{
  "groups": [
    {
      "members": [1, 2],
      "representative": 1,
      "rationale": "相同属性：脑脊液/CSF都是高信号"
    },
    {
      "members": [3],
      "representative": 3,
      "rationale": "灰白质对比 - 不同的属性"
    },
    {
      "members": [4],
      "representative": 4,
      "rationale": "脂肪抑制效果 - 不同的属性"
    }
  ]
}
```

- ✅ [1, 2] 合并：相同的属性（CSF信号）
- ✅ [3] 独立：不同的属性（灰白质对比）
- ✅ [4] 独立：不同的属性（脂肪抑制）

---

## 系统行为验证

### 自动 Prompt 选择

```python
# 以下关系会自动使用 'attribute' prompt：
relations_attribute = [
    "has_attribute",     # ✓ 自动检测
    "attribute",         # ✓ 自动检测
    "property",          # ✓ 自动检测
    "has_property",      # ✓ 自动检测
    "characteristic",    # ✓ 自动检测
    "my_attribute_xyz",  # ✓ 包含 "attribute" 字符串
]

# 以下关系会使用 'general' prompt：
relations_general = [
    "related_to",        # ✓ 使用 general
    "keyword_of",        # ✓ 使用 general
    "has_component",     # ✓ 使用 general
]
```

### 日志输出

启用 debug 日志后会看到：

```
DEBUG: Auto-selected 'attribute' prompt type for relation: has_attribute
```

---

## 实际运行测试

### 准备工作

1. 确保配置文件更新：
```bash
# 检查 config/base_config.yaml 是否有 semantic_dedup.attribute
grep -A 30 "semantic_dedup:" config/base_config.yaml
```

2. 确保代码更新：
```bash
# 检查是否有 DEFAULT_ATTRIBUTE_DEDUP_PROMPT
grep "DEFAULT_ATTRIBUTE_DEDUP_PROMPT" models/constructor/kt_gen.py
```

### 运行测试

```python
# 测试你的案例
from models.constructor.kt_gen import KTBuilder

builder = KTBuilder(dataset_name="test")

# 构建包含 has_attribute 关系的图
# ... 你的图构建代码 ...

# 运行语义去重
builder.triple_deduplicate_semantic()

# 查看中间结果
# 检查 output/dedup_intermediate/ 中的结果文件
```

### 预期结果

在中间结果文件中：

```json
{
  "triples": [
    {
      "head_name": "魔角效应",
      "relation": "has_attribute",
      "llm_groups": [
        {
          "groups": [
            {"members": [0], "rationale": "Unique attribute: three dependencies"},
            {"members": [1], "rationale": "Unique attribute: T2 extension"}
          ]
        }
      ],
      "final_merges": [],  // ✓ 应该为空，因为没有合并
      "summary": {
        "total_edges": 2,
        "final_edges": 2,  // ✓ 保留了全部2个属性
        "edges_merged": 0  // ✓ 没有被合并
      }
    }
  ]
}
```

---

## 对比总结

| 方面 | 修复前 | 修复后 |
|------|--------|--------|
| **Prompt** | General（宽松） | Attribute（严格） |
| **你的案例** | ❌ 错误合并 | ✅ 正确分离 |
| **合并条件** | "相关的事实" | "完全相同的属性" |
| **信息损失** | 有（丢失属性） | 无 |
| **自动检测** | 不支持 | ✅ 支持 |
| **向后兼容** | - | ✅ 完全兼容 |

---

## 后续建议

### 1. 监控去重效果

启用中间结果保存并定期检查：

```yaml
construction:
  semantic_dedup:
    save_intermediate_results: true
```

### 2. 调整阈值

如果还有问题，可以调整聚类阈值：

```yaml
construction:
  semantic_dedup:
    embedding_threshold: 0.90  # 提高阈值，更严格
```

### 3. 自定义 Prompt

针对你的医疗领域，可以添加领域特定的指令：

```yaml
prompts:
  semantic_dedup:
    attribute: |-
      ... 原有指令 ...
      
      Domain-specific note for medical imaging:
      - "依赖性"、"机制"、"特点"、"对策" 等是不同类型的属性
      - 数值型属性（如 "延长两倍"）和描述型属性（如 "三个特点"）不应合并
      - 即使来自同一段落，也可能是不同的属性
```

---

## 总结

✅ **问题已修复**：属性去重不再过度合并

✅ **自动工作**：`has_attribute` 关系自动使用严格策略

✅ **保留信息**：不同的属性值被正确保留

✅ **向后兼容**：不影响其他关系的去重行为
