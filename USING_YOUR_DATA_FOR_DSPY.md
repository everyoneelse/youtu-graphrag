# 使用您的真实数据训练DSPy

## 🎯 您的数据完全适合！

您提供的医学影像数据（MRI伪影）是**非常好的训练数据**，因为：

✅ **专业领域**: 医学术语，DSPy可以学习domain-specific的去重规则  
✅ **复杂场景**: 多个定义描述同一概念的不同方面  
✅ **真实挑战**: 需要专业知识判断哪些应该合并  

---

## 📊 您的数据示例分析

### 原始数据

```json
{
  "head_node": {
    "properties": {"name": "魔角效应", "schema_type": "MRI伪影"}
  },
  "relation": "has_attribute",
  "tail_nodes_to_dedup": [
    "定义:魔角效应伪影，在短TE序列上较为显著，常被误诊为损伤",
    "定义:在关节磁共振扫描过程中，当关节软骨的轴线与主磁场轴形成约55度角时，成像结果表现出更高的信号的现象",
    "定义:在特定角度下MRI信号异常增高的现象",
    "关键角度: 55°",
    "条件: 短TE序列",
    "效果: 局部异常增高的高信号",
    "定义:特殊走向的纤维组织出现虚假的相对高信号",
    "特点:角度依赖性、组织依赖性、TE依赖性",
    "T2弛豫时间延长:最多可延长两倍以上"
  ]
}
```

### 专业分析

**去重挑战**:
- 🔸 **4个定义** - 描述同一现象的不同方面
  - 定义1: 强调临床表现（误诊风险）
  - 定义2: 强调物理原理（55度角）
  - 定义3: 简化描述（定义2的简化版）✅ **应合并**
  - 定义4: 强调组织特性（纤维组织）

- 🔸 **其他属性** - 独立信息，不应合并
  - 角度、条件、效果、特点、T2时间 - 各自独立

**推荐的去重结果**:
```python
{
  "groups": [
    {
      "members": [2, 3],  # 定义2和定义3合并
      "representative": 2,
      "rationale": "定义3是定义2的简化版，表达相同内容"
    },
    {"members": [1], "representative": 1, "rationale": "强调临床表现"},
    {"members": [4], "representative": 4, "rationale": "角度参数"},
    {"members": [5], "representative": 5, "rationale": "条件"},
    {"members": [6], "representative": 6, "rationale": "效果"},
    {"members": [7], "representative": 7, "rationale": "强调组织特性"},
    {"members": [8], "representative": 8, "rationale": "依赖性特点"},
    {"members": [9], "representative": 9, "rationale": "T2时间"}
  ]
}
```

---

## 🚀 使用流程

### 方案1: 快速开始（使用示例数据）

```bash
# 1. 创建魔角效应的标准示例
python scripts/convert_real_data_to_dspy.py \
    --create-example \
    --output data/magic_angle_example.json

# 2. 查看生成的训练数据
cat data/magic_angle_example.json

# 3. 用这个示例训练DSPy
python scripts/train_dspy_modules.py \
    --train-data data/magic_angle_example.json \
    --train-all
```

### 方案2: 使用您的完整数据集

#### Step 1: 准备数据文件

将您的数据保存为JSON文件，例如 `data/my_mri_dedup_data.json`:

```json
[
  {
    "head_node": {
      "label": "entity",
      "properties": {
        "name": "魔角效应",
        "schema_type": "MRI伪影"
      }
    },
    "relation": "has_attribute",
    "tail_nodes_to_dedup": [
      "定义:魔角效应伪影...",
      "定义:在关节磁共振扫描...",
      ...
    ]
  },
  {
    "head_node": {...},
    "relation": "...",
    "tail_nodes_to_dedup": [...]
  }
  // ... 更多样本
]
```

#### Step 2: 人工标注（重要！）

有两种方式：

**方式A: 交互式标注**

```bash
python scripts/convert_real_data_to_dspy.py \
    --input data/my_mri_dedup_data.json \
    --output data/labeled_training_data.json \
    --interactive
```

脚本会引导您完成标注：
```
标注样本
================================================================================
Head: 魔角效应
Relation: has_attribute

Tails (9):
  [1] 定义:魔角效应伪影，在短TE序列上较为显著...
  [2] 定义:在关节磁共振扫描过程中...
  [3] 定义:在特定角度下MRI信号异常增高的现象
  [4] 关键角度: 55°
  ...

请标注去重结果:
输入应该合并的tail的索引，用逗号分隔。

输入一组 (或 'done'): 2,3
  为什么合并 [2, 3]? 定义3是定义2的简化版本

输入一组 (或 'done'): 1
  为什么合并 [1]? 强调临床表现，独立信息

输入一组 (或 'done'): done
```

**方式B: 直接编辑JSON添加标注**

在您的数据JSON中添加 `gold_groups` 字段：

```json
{
  "head_node": {...},
  "relation": "has_attribute",
  "tail_nodes_to_dedup": [...],
  "gold_groups": [
    {
      "members": [2, 3],
      "representative": 2,
      "rationale": "定义3是定义2的简化版"
    },
    {
      "members": [1],
      "representative": 1,
      "rationale": "强调临床表现"
    }
    // ... 更多groups
  ]
}
```

然后转换：
```bash
python scripts/convert_real_data_to_dspy.py \
    --input data/my_labeled_data.json \
    --output data/dspy_training.json
```

#### Step 3: 训练DSPy模块

```bash
python scripts/train_dspy_modules.py \
    --train-data data/dspy_training.json \
    --train-all \
    --teacher-model gpt-4 \
    --student-model gpt-3.5-turbo \
    --output-dir models/dspy_optimized_mri
```

#### Step 4: 评估和使用

```bash
# 测试优化后的模块
python example_dspy_demo.py

# 在生产环境使用
# 更新config.yaml中的模块路径
# dspy:
#   clustering_module_path: "models/dspy_optimized_mri/clustering_module.json"
#   dedup_module_path: "models/dspy_optimized_mri/dedup_module_general.json"
```

---

## 📝 标注指南

### 基本原则

#### ✅ 应该合并（Same Entity）

- ✓ **相同概念的不同表述**
  ```
  "定义:在特定角度下MRI信号异常增高的现象"
  "定义:当关节软骨轴线与主磁场轴形成约55度角时，成像结果表现出更高的信号"
  → 第一个是第二个的简化版，应合并
  ```

- ✓ **缩写和全称**
  ```
  "TE序列"
  "Time to Echo序列"
  → 应合并
  ```

- ✓ **不同语言/符号表示**
  ```
  "55度"
  "55°"
  "55 degrees"
  → 应合并
  ```

#### ❌ 不应合并（Different Entities）

- ✗ **不同属性类型**
  ```
  "定义:魔角效应是..."
  "关键角度: 55°"
  → 一个是定义，一个是参数，不应合并
  ```

- ✗ **不同侧重点的描述**
  ```
  "定义:伪影，常被误诊为损伤"  (强调临床表现)
  "定义:特殊走向的纤维组织出现虚假的相对高信号"  (强调组织特性)
  → 虽然都是定义，但强调不同方面，不应合并
  ```

- ✗ **互补信息**
  ```
  "条件: 短TE序列"
  "效果: 局部异常增高的高信号"
  → 是互补的信息，不是重复，不应合并
  ```

### 医学领域特殊考虑

对于您的MRI数据：

1. **定义的粒度**
   - 如果两个定义从不同角度解释同一现象 → **保持分开**
   - 如果一个是另一个的简化/泛化 → **可以合并**

2. **参数和测量**
   - 不同的测量参数（角度、时间、信号强度）→ **保持分开**
   - 相同参数的不同表示（55° vs 55度）→ **合并**

3. **因果关系**
   - 原因和结果 → **保持分开**
   - 条件和效果 → **保持分开**

---

## 💡 实战示例

### 示例1: 简单case（应合并）

```python
tails = [
    "定义:在特定角度下MRI信号异常增高",
    "定义:特定角度(约55°)下MRI信号增高的现象"
]

# 标注:
gold_groups = [
    {
        "members": [1, 2],
        "representative": 2,  # 选择更具体的那个
        "rationale": "表达相同概念，2更具体(包含角度信息)"
    }
]
```

### 示例2: 复杂case（部分合并）

```python
tails = [
    "定义:魔角效应伪影",
    "定义:MRI信号在55°角时异常增高",
    "定义:纤维组织的虚假高信号",
    "关键角度: 55°",
    "临床表现: 易误诊为损伤"
]

# 标注:
gold_groups = [
    {
        "members": [1, 2],
        "representative": 2,
        "rationale": "都是定义，2更具体"
    },
    {
        "members": [3],
        "representative": 3,
        "rationale": "强调组织特性，不同侧重"
    },
    {
        "members": [4],
        "representative": 4,
        "rationale": "参数信息，独立"
    },
    {
        "members": [5],
        "representative": 5,
        "rationale": "临床表现，独立"
    }
]
```

### 示例3: 属性去重（您的数据）

```python
tails = [
    "特点:角度依赖性、组织依赖性、TE依赖性",
    "特点:角度依赖、组织依赖、TE依赖",
    "特点:具有角度、组织和TE的依赖性"
]

# 标注:
gold_groups = [
    {
        "members": [1, 2, 3],
        "representative": 1,
        "rationale": "表达相同内容，只是措辞略有不同"
    }
]
```

---

## 📊 数据质量建议

### 理想的训练集

| 特征 | 推荐 | 最低要求 |
|------|------|---------|
| **样本数量** | 30-50个 | 10个 |
| **领域覆盖** | 多种MRI伪影类型 | 至少3-5种 |
| **复杂度** | 包含简单和复杂case | 混合 |
| **标注质量** | 专家审核 | 一致性检查 |

### 增强策略

如果样本不够，可以：

1. **从不同来源收集**
   - 不同的chunk组合
   - 不同的表述方式
   - 不同的专业子领域

2. **数据增强**
   - 同义词替换（保持医学准确性）
   - 改写描述
   - 添加噪声数据（故意的错误case）

3. **迭代标注**
   - 先标注10个样本
   - 训练初步模型
   - 用模型辅助标注更多样本

---

## 🎓 训练建议

### For 医学领域

```bash
# 使用更强的teacher model确保医学准确性
python scripts/train_dspy_modules.py \
    --train-data data/mri_training.json \
    --teacher-model gpt-4 \
    --student-model gpt-3.5-turbo \
    --output-dir models/dspy_mri \
    --val-split 0.2
```

### 评估指标

重点关注：
- **False Positive率** - 不应合并医学上不同的概念
- **Domain Accuracy** - 是否符合医学专业知识
- **Consistency** - 相似case的处理是否一致

### 迭代优化

```
Iteration 1: 用10个精心标注的样本训练
  ↓
评估: 在5个测试样本上验证
  ↓
Iteration 2: 根据错误case增加训练样本
  ↓
评估: 扩大测试集
  ↓
Iteration 3: 达到满意性能
```

---

## 🔧 配置建议

### For 医学数据

```yaml
# config/mri_dedup_config.yaml
construction:
  semantic_dedup:
    enabled: true
    use_dspy: true
    
    dspy:
      clustering_module_path: "models/dspy_mri/clustering_module.json"
      dedup_module_path: "models/dspy_mri/dedup_module_general.json"
      
      # 医学数据建议启用validation
      enable_validation: true
      validation_module_path: "models/dspy_mri/validation_module.json"
      
      # 保守策略：宁可不合并，也不要错误合并医学概念
      fallback_to_original: true
    
    # 使用较低的阈值（更保守）
    threshold: 0.90  # 默认0.88
    
    # 较小的batch size（医学描述通常较长）
    max_batch_size: 6
    
    clustering_llm:
      model: "gpt-3.5-turbo"
      temperature: 0.0  # 医学领域用0温度确保一致性
    
    dedup_llm:
      model: "gpt-3.5-turbo"  # DSPy优化后可以用cheaper model
      temperature: 0.0
```

---

## ✅ 检查清单

使用您的数据前，确认：

- [ ] 数据格式正确（包含head_node, relation, tail_nodes_to_dedup）
- [ ] 已完成人工标注（gold_groups）
- [ ] 至少有10个高质量标注样本
- [ ] 标注符合医学专业知识
- [ ] 包含简单和复杂的case
- [ ] 测试集和训练集分开（如果数据量足够）

---

## 📚 相关文档

- **数据转换脚本**: `scripts/convert_real_data_to_dspy.py`
- **训练脚本**: `scripts/train_dspy_modules.py`
- **DSPy快速开始**: `DSPY_QUICKSTART.md`
- **完整技术分析**: `DSPY_PROMPT_OPTIMIZATION_ANALYSIS.md`

---

## 🆘 常见问题

**Q: 我的数据没有标注怎么办？**  
A: 使用 `--interactive` 模式进行交互式标注，或者先创建示例数据学习流程。

**Q: 标注10个样本够吗？**  
A: 可以开始，但20-30个样本效果更好。可以先用10个训练，然后迭代增加。

**Q: 如何处理医学术语的准确性？**  
A: 
1. 使用GPT-4作为teacher model
2. 启用validation检查结果
3. 人工审核关键case
4. 温度设为0确保一致性

**Q: 我的数据格式不一样怎么办？**  
A: 修改 `convert_real_data_to_dspy.py` 中的解析逻辑，适配您的格式。

---

**您的数据非常有价值！开始训练吧！** 🚀

有任何问题，参考文档或运行示例脚本即可。
