# 通用DSPy训练数据格式

## 🎯 核心理念

**不局限于特定领域或特定case**

您说得对！训练数据应该是**通用的**，能够对应当前semantic dedup流程的任何场景：
- ✅ 任何 head entity（实体、概念、事件等）
- ✅ 任何 relation（has_attribute, located_in, author_of等）
- ✅ 任何 domain（医学、技术、地理、商业等）

---

## 📋 通用数据格式

### 最小化格式（必需字段）

```json
{
  "head_entity": "任意实体名称",
  "relation": "任意关系类型",
  "tail_descriptions": [
    "待去重的tail 1",
    "待去重的tail 2",
    "待去重的tail 3"
  ]
}
```

### 完整格式（带标注）

```json
{
  "head_entity": "实体名称",
  "relation": "关系类型",
  
  "tail_descriptions": [
    "tail 1",
    "tail 2", 
    "tail 3"
  ],
  
  "contexts": [
    ["tail 1的上下文1", "tail 1的上下文2"],
    ["tail 2的上下文1"],
    ["tail 3的上下文1", "tail 3的上下文2", "tail 3的上下文3"]
  ],
  
  "gold_clusters": [
    [1, 2],
    [3]
  ],
  
  "gold_groups": [
    {
      "members": [1, 2],
      "representative": 1,
      "rationale": "为什么tail 1和tail 2应该合并"
    },
    {
      "members": [3],
      "representative": 3,
      "rationale": "为什么tail 3应该独立"
    }
  ],
  
  "metadata": {
    "domain": "领域标签（可选）",
    "complexity": "简单/中等/困难（可选）",
    "source": "数据来源（可选）"
  }
}
```

### 字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `head_entity` | string | ✅ | 头实体的描述 |
| `relation` | string | ✅ | 关系类型 |
| `tail_descriptions` | List[str] | ✅ | 待去重的尾实体列表 |
| `contexts` | List[List[str]] | ❌ | 每个tail的上下文（可选但推荐） |
| `gold_clusters` | List[List[int]] | 🔶 | 聚类标注（用于训练clustering） |
| `gold_groups` | List[Dict] | 🔶 | 去重标注（用于训练dedup） |
| `metadata` | Dict | ❌ | 额外信息（可选） |

**注意**: `gold_clusters` 和 `gold_groups` 至少需要一个用于监督训练。

---

## 🌍 多领域示例

### 示例1: 技术领域 - 版本号

```json
{
  "head_entity": "Python",
  "relation": "has_version",
  "tail_descriptions": [
    "Python 3.9",
    "Python 3.9.0",
    "Python 3.10"
  ],
  "gold_groups": [
    {
      "members": [1, 2],
      "representative": 1,
      "rationale": "3.9.0 is the full version of 3.9"
    },
    {
      "members": [3],
      "representative": 3,
      "rationale": "Different minor version"
    }
  ]
}
```

### 示例2: 地理领域 - 城市别名

```json
{
  "head_entity": "中国",
  "relation": "has_city",
  "tail_descriptions": [
    "北京",
    "北京市",
    "Beijing",
    "上海"
  ],
  "gold_groups": [
    {
      "members": [1, 2, 3],
      "representative": 1,
      "rationale": "Same city - Beijing"
    },
    {
      "members": [4],
      "representative": 4,
      "rationale": "Different city"
    }
  ]
}
```

### 示例3: 医学领域 - 属性描述

```json
{
  "head_entity": "魔角效应",
  "relation": "has_attribute",
  "tail_descriptions": [
    "定义:在特定角度下MRI信号异常增高的现象",
    "定义:当关节软骨轴线与主磁场轴形成约55度角时信号增高",
    "关键角度: 55°"
  ],
  "gold_groups": [
    {
      "members": [1, 2],
      "representative": 2,
      "rationale": "定义1是定义2的简化版"
    },
    {
      "members": [3],
      "representative": 3,
      "rationale": "参数信息，独立"
    }
  ]
}
```

### 示例4: 商业领域 - 公司名称

```json
{
  "head_entity": "科技行业",
  "relation": "has_company",
  "tail_descriptions": [
    "Apple Inc.",
    "Apple",
    "苹果公司",
    "Microsoft"
  ],
  "gold_groups": [
    {
      "members": [1, 2, 3],
      "representative": 1,
      "rationale": "Same company - different names"
    },
    {
      "members": [4],
      "representative": 4,
      "rationale": "Different company"
    }
  ]
}
```

---

## 🔄 从您的数据创建训练集

### 方法1: 从去重结果批量提取

如果您已经运行过semantic dedup，可以从结果中提取：

```bash
# 从intermediate results提取
python scripts/create_universal_training_data.py \
    --from-dedup-results output/dedup_intermediate \
    --sample-size 50 \
    --output data/my_training.json
```

这会：
1. 读取所有 `output/dedup_intermediate/*.json` 文件
2. 提取clustering和dedup结果
3. 转换为通用训练格式
4. 过滤低质量样本
5. 随机采样

### 方法2: 手工转换您的数据

您的原始数据：
```json
{
  "head_node": {"properties": {"name": "魔角效应"}},
  "relation": "has_attribute",
  "tail_nodes_to_dedup": ["tail1", "tail2", ...]
}
```

转换为训练格式：
```python
import json

def convert_my_data(original_data):
    """转换您的数据格式"""
    
    # 提取基本信息
    head_name = original_data['head_node']['properties']['name']
    relation = original_data['relation']
    tails = original_data['tail_nodes_to_dedup']
    
    # 清理tails（去掉metadata）
    clean_tails = []
    for tail in tails:
        # 去掉 (chunk id: xxx) 和 [attribute] 等标记
        clean = tail.split(" (chunk id:")[0]
        clean = clean.split(" [attribute]")[0]
        clean_tails.append(clean)
    
    # 创建训练样本
    training_sample = {
        "head_entity": head_name,
        "relation": relation,
        "tail_descriptions": clean_tails,
        
        # 需要添加标注！
        "gold_groups": [
            # TODO: 人工标注
        ]
    }
    
    return training_sample

# 批量转换
with open('your_data.json', 'r') as f:
    data = json.load(f)

training_data = [convert_my_data(item) for item in data]

# 保存
with open('training.json', 'w') as f:
    json.dump(training_data, f, indent=2, ensure_ascii=False)
```

### 方法3: 使用转换脚本

```bash
# 交互式标注
python scripts/convert_real_data_to_dspy.py \
    --input your_data.json \
    --interactive \
    --output training.json
```

---

## 📊 训练集质量要求

### 数量要求

| 目标 | 最少样本 | 推荐样本 | 理想样本 |
|------|---------|---------|---------|
| **概念验证** | 5-10 | 10-15 | 20+ |
| **生产使用** | 20-30 | 30-50 | 50-100 |
| **高精度** | 50+ | 100+ | 200+ |

### 质量要求

✅ **多样性**
- 覆盖不同的head entity类型
- 覆盖不同的relation类型
- 覆盖不同的复杂度（简单/中等/困难）

✅ **代表性**
- 包含真实场景的case
- 包含边界case
- 包含容易混淆的case

✅ **平衡性**
- 不要全是trivial case（全部合并或全部分开）
- 不要全是简单case
- 不要全是同一个领域

---

## 🎯 训练数据分布建议

### 按领域分布

```
医学: 30-40%  ← 您的主要领域
技术: 20-30%
地理: 10-20%
商业: 10-20%
其他: 10%
```

### 按复杂度分布

```
简单（2-5 tails, 明显的合并/分离）: 30%
中等（5-10 tails, 需要判断）: 50%
困难（10+ tails, 复杂场景）: 20%
```

### 按关系类型分布

```
has_attribute: 40%  ← 您的主要关系
其他关系: 60%
  - has_property
  - located_in
  - member_of
  - author_of
  - has_version
  等等
```

---

## 🔧 使用流程

### Step 1: 创建训练数据

```bash
# 方式A: 从去重结果提取
python scripts/create_universal_training_data.py \
    --from-dedup-results output/dedup_intermediate \
    --output data/training.json

# 方式B: 创建多样化示例
python scripts/create_universal_training_data.py \
    --create-diverse-examples \
    --output data/diverse_training.json

# 方式C: 转换您的数据
python scripts/convert_real_data_to_dspy.py \
    --input your_data.json \
    --interactive \
    --output data/your_training.json
```

### Step 2: 检查数据质量

```bash
# 查看统计信息
python scripts/create_universal_training_data.py \
    --from-dedup-results output/dedup_intermediate \
    --output data/training.json
# 会显示: 总样本数、领域分布、关系分布、复杂度分布
```

### Step 3: 训练DSPy模块

```bash
python scripts/train_dspy_modules.py \
    --train-data data/training.json \
    --train-all \
    --output-dir models/dspy_universal
```

### Step 4: 评估和迭代

```bash
# 在验证集上评估
python scripts/train_dspy_modules.py \
    --train-data data/training.json \
    --val-split 0.3 \
    --train-all

# 如果效果不理想:
# 1. 增加更多训练样本
# 2. 增加困难case
# 3. 平衡领域分布
```

---

## 💡 最佳实践

### 1. 从小规模开始

```bash
# 先用10个精心标注的样本
python scripts/train_dspy_modules.py \
    --train-data data/small_training.json \
    --train-all

# 评估效果，然后扩展到30-50个
```

### 2. 混合真实和多样化数据

```python
# 组合您的医学数据 + 多样化示例
medical_data = load_your_medical_data()
diverse_examples = create_diverse_examples()

combined = medical_data + diverse_examples
```

### 3. 迭代优化

```
Round 1: 10个样本 → 训练 → 评估
  ↓
Round 2: +20个困难case → 重新训练 → 评估
  ↓
Round 3: +20个边界case → 最终训练 → 部署
```

### 4. 保持领域焦点但不局限

```python
# 推荐组合:
training_set = [
    *your_medical_cases (60%),      # 您的核心领域
    *diverse_examples (40%)         # 增强泛化能力
]
```

---

## 🆚 对比：特定 vs 通用

| 维度 | 特定示例（之前） | 通用格式（现在） |
|------|---------------|---------------|
| **适用性** | 只适用于"魔角效应" | ✅ 适用于任何case |
| **可扩展性** | ❌ 难以扩展 | ✅ 易于批量生成 |
| **泛化能力** | ❌ 过拟合单一case | ✅ 更好的泛化 |
| **实用性** | ❌ 需要大量改动 | ✅ 直接使用 |

---

## 📚 相关工具

| 工具 | 用途 |
|------|------|
| `create_universal_training_data.py` | 创建通用训练数据 |
| `convert_real_data_to_dspy.py` | 转换您的特定格式数据 |
| `train_dspy_modules.py` | 训练DSPy模块 |

---

## ✅ 检查清单

使用通用格式前，确认：

- [ ] 数据包含多个不同的head entity
- [ ] 数据包含多个不同的relation类型
- [ ] 不局限于单一领域或单一case
- [ ] 包含简单、中等、困难的不同复杂度
- [ ] 每个样本都有清晰的标注（gold_groups）
- [ ] 样本数量至少10个（推荐30-50个）

---

## 🚀 快速开始

```bash
# 1. 创建多样化训练集
python scripts/create_universal_training_data.py \
    --create-diverse-examples \
    --output data/universal.json

# 2. 添加您的医学数据
python scripts/convert_real_data_to_dspy.py \
    --input your_medical_data.json \
    --interactive

# 3. 合并并训练
cat data/universal.json data/your_training.json > data/combined.json
python scripts/train_dspy_modules.py \
    --train-data data/combined.json \
    --train-all
```

---

**通用格式让DSPy学习更广泛的去重规则，而不是过拟合特定case！** 🎯

这样训练出的模型可以：
- ✅ 处理任何head entity
- ✅ 处理任何relation类型
- ✅ 在您的医学数据上表现更好
- ✅ 具有更好的泛化能力
