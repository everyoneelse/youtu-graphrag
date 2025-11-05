# DSPy Semantic Dedup 优化方案 - 文件索引

## 📁 项目结构

本方案包含以下文件，用于实现基于DSPy的semantic deduplication优化：

```
.
├── README_DSPY.md                              # 本文件 - 文件索引
├── DSPY_INTEGRATION_SUMMARY.md                 # 集成总结 - 快速了解方案
├── DSPY_QUICKSTART.md                          # 快速开始指南 - 5分钟上手
├── DSPY_PROMPT_OPTIMIZATION_ANALYSIS.md        # 详细技术分析 - 深入理解
│
├── example_dspy_demo.py                        # 演示脚本 - 快速体验DSPy
│
├── models/constructor/
│   └── dspy_semantic_dedup.py                  # 核心实现 - DSPy模块定义
│
└── scripts/
    ├── prepare_dspy_training_data.py           # 训练数据准备
    └── train_dspy_modules.py                   # 模块训练脚本
```

---

## 📖 文档导航

### 🚀 快速开始（推荐顺序）

#### 1️⃣ 首先阅读：集成总结
**文件**: `DSPY_INTEGRATION_SUMMARY.md`  
**时长**: 5分钟  
**内容**:
- ✅ 方案概览
- ✅ 核心优势（性能+成本）
- ✅ 预期收益
- ✅ 实施流程

👉 **适合**: 决策者、项目负责人、想快速了解方案的人

---

#### 2️⃣ 然后跟随：快速开始指南
**文件**: `DSPY_QUICKSTART.md`  
**时长**: 10-15分钟实操  
**内容**:
- 🔧 环境配置
- 💻 代码示例
- 🎯 一步步教程
- 🐛 故障排除
- 💡 最佳实践

👉 **适合**: 开发人员、想立即上手的人

---

#### 3️⃣ 体验演示：运行示例脚本
**文件**: `example_dspy_demo.py`  
**时长**: 5分钟  
**命令**:
```bash
export OPENAI_API_KEY=your_key
python example_dspy_demo.py
```

**演示内容**:
- 🔸 示例1: LLM-based Clustering
- 🔸 示例2: Semantic Deduplication
- 🔸 示例3: 优化过程演示
- 🔸 示例4: 成本对比分析

👉 **适合**: 想直观感受DSPy效果的人

---

#### 4️⃣ 深入理解：技术分析文档
**文件**: `DSPY_PROMPT_OPTIMIZATION_ANALYSIS.md`  
**时长**: 30-60分钟  
**内容**:
- 📊 当前实现分析
- 🔬 DSPy原理详解
- 💻 完整代码示例
- 🏗️ 架构设计
- 🔧 实施步骤

👉 **适合**: 架构师、想深入理解技术细节的人

---

## 🎯 根据角色选择阅读路径

### 👔 如果你是：项目负责人/决策者
**建议阅读顺序**:
1. `DSPY_INTEGRATION_SUMMARY.md` - 了解价值和收益
2. `DSPY_QUICKSTART.md` 的"预期收益"部分 - 看具体数据
3. 运行 `example_dspy_demo.py` - 看实际效果

**关注重点**: 性能提升、成本节省、实施难度

---

### 💻 如果你是：开发工程师
**建议阅读顺序**:
1. `DSPY_QUICKSTART.md` - 快速上手
2. 运行 `example_dspy_demo.py` - 体验功能
3. `DSPY_PROMPT_OPTIMIZATION_ANALYSIS.md` - 深入理解
4. 查看 `models/constructor/dspy_semantic_dedup.py` - 学习代码

**关注重点**: API使用、代码实现、调试技巧

---

### 🏗️ 如果你是：架构师/技术专家
**建议阅读顺序**:
1. `DSPY_INTEGRATION_SUMMARY.md` - 整体方案
2. `DSPY_PROMPT_OPTIMIZATION_ANALYSIS.md` - 技术细节
3. 审查 `models/constructor/dspy_semantic_dedup.py` - 评估实现
4. `DSPY_QUICKSTART.md` 的"高级使用"部分 - 定制方案

**关注重点**: 架构设计、可扩展性、性能优化

---

### 🎓 如果你是：研究人员/学生
**建议阅读顺序**:
1. `DSPY_PROMPT_OPTIMIZATION_ANALYSIS.md` - 完整技术文档
2. 运行 `example_dspy_demo.py` - 实践验证
3. 阅读 DSPy 论文和文档 - 理论基础
4. 修改代码实验 - 深度学习

**关注重点**: 算法原理、评估指标、实验设计

---

## 🛠️ 核心代码文件说明

### 1. `models/constructor/dspy_semantic_dedup.py`
**功能**: DSPy模块核心实现  
**大小**: ~450行代码  
**包含**:
- ✅ DSPy Signatures定义
  - `TailClustering` - 聚类任务
  - `CoreferenceResolution` - 共指消解任务
  - `AttributeEquivalence` - 属性等价任务
  
- ✅ DSPy Modules实现
  - `SemanticClusteringModule` - 聚类模块
  - `SemanticDedupModule` - 去重模块
  
- ✅ 评估指标
  - `clustering_metric` - 聚类F1 score
  - `dedup_metric` - 去重F1 score
  
- ✅ 优化器
  - `DSPySemanticDedupOptimizer` - 训练和优化wrapper

**使用示例**:
```python
from models.constructor.dspy_semantic_dedup import SemanticClusteringModule

clustering = SemanticClusteringModule()
clusters = clustering(
    head_entity="United States",
    relation="president", 
    tail_descriptions=["Obama", "Barack Obama", "Trump"]
)
```

---

### 2. `scripts/prepare_dspy_training_data.py`
**功能**: 准备DSPy训练数据  
**大小**: ~360行代码  
**包含**:
- ✅ 合成数据生成（8个高质量样本）
- ✅ 从JSON文件加载/保存
- ✅ 统计信息展示

**使用方法**:
```bash
# 生成合成训练数据
python scripts/prepare_dspy_training_data.py --output data/dspy_training.json --show-stats

# 从真实数据提取（需要实现）
python scripts/prepare_dspy_training_data.py --from-real-data output/dedup_intermediate/*.json
```

**训练样本场景**:
1. 人名别名 (George Lucas, G. Lucas, ...)
2. 城市名称 (NYC, New York City, ...)
3. 产品版本 (iPhone 13, iPhone 14)
4. 国家缩写 (USA, US, America)
5. 组织名称
6. 属性单位转换 (100°C = 212°F)
7. 书籍作品
8. 科学概念

---

### 3. `scripts/train_dspy_modules.py`
**功能**: 训练和优化DSPy模块  
**大小**: ~370行代码  
**包含**:
- ✅ Baseline评估
- ✅ 使用BootstrapFewShot优化
- ✅ 性能对比
- ✅ 模块保存

**使用方法**:
```bash
# 训练所有模块
python scripts/train_dspy_modules.py \
    --train-all \
    --use-synthetic \
    --teacher-model gpt-4 \
    --student-model gpt-3.5-turbo \
    --output-dir models/dspy_optimized \
    --api-key YOUR_KEY

# 只训练聚类模块
python scripts/train_dspy_modules.py --train-clustering --use-synthetic

# 使用自定义训练数据
python scripts/train_dspy_modules.py \
    --train-data data/my_training_data.json \
    --val-split 0.3
```

---

### 4. `example_dspy_demo.py`
**功能**: 快速演示DSPy功能  
**大小**: ~330行代码  
**包含**:
- ✅ 聚类演示
- ✅ 去重演示
- ✅ 优化过程演示
- ✅ 成本对比分析

**运行方法**:
```bash
export OPENAI_API_KEY=your_key
python example_dspy_demo.py
```

---

## 📊 快速参考表

| 需求 | 推荐文件 | 预计时间 |
|------|---------|---------|
| 快速了解方案 | `DSPY_INTEGRATION_SUMMARY.md` | 5分钟 |
| 立即上手使用 | `DSPY_QUICKSTART.md` | 15分钟 |
| 体验Demo | `example_dspy_demo.py` | 5分钟 |
| 深入技术细节 | `DSPY_PROMPT_OPTIMIZATION_ANALYSIS.md` | 60分钟 |
| 查看代码实现 | `dspy_semantic_dedup.py` | 30分钟 |
| 准备训练数据 | `prepare_dspy_training_data.py` | 10分钟 |
| 训练优化模块 | `train_dspy_modules.py` | 15分钟 |

---

## 🚀 立即开始

### 最快5分钟体验流程

```bash
# 1. 安装依赖
pip install dspy-ai

# 2. 设置API key
export OPENAI_API_KEY=your_key

# 3. 运行演示
python example_dspy_demo.py

# 4. 查看结果
# 你会看到聚类和去重的实际效果！
```

### 最快30分钟完整流程

```bash
# 1. 安装依赖
pip install dspy-ai

# 2. 设置API key
export OPENAI_API_KEY=your_key

# 3. 准备训练数据
python scripts/prepare_dspy_training_data.py --use-synthetic --show-stats

# 4. 训练模块（这一步需要10-15分钟）
python scripts/train_dspy_modules.py --train-all --use-synthetic

# 5. 查看结果
# 你会看到baseline vs optimized的性能对比
# 以及优化后的模块保存在 models/dspy_optimized/

# 6. (可选) 更新配置并运行去重
# 编辑 config/base_config.yaml，设置 use_dspy: true
# python main.py --config config/base_config.yaml --dataset demo
```

---

## ❓ 常见问题

### Q1: 我需要先了解DSPy吗？
**A**: 不需要！本方案已经封装好了DSPy的使用，你只需要：
- 阅读 `DSPY_QUICKSTART.md`
- 运行 `example_dspy_demo.py`
- 按照指南操作即可

### Q2: 必须使用OpenAI API吗？
**A**: 不是必须的。DSPy支持任何兼容OpenAI API格式的服务，包括：
- ✅ OpenAI官方
- ✅ Azure OpenAI
- ✅ 本地部署的模型（如deepseek、qwen等）
- ✅ 任何兼容的API服务

### Q3: 训练需要多少数据？
**A**: 
- **最少**: 5-10个高质量样本即可看到改进
- **推荐**: 20-50个样本用于生产环境
- **理想**: 50-100个样本达到最佳效果

### Q4: 训练成本是多少？
**A**: 使用合成数据（8个样本）训练：
- 时间: 10-15分钟
- 成本: 约$0.50-1.00 (使用GPT-4作为teacher)
- 后续使用: GPT-3.5-turbo成本降低90%

### Q5: 如果效果不好怎么办？
**A**: 方案设计了fallback机制：
1. 配置中设置 `fallback_to_original: true`
2. 如果DSPy模块加载失败或效果不佳
3. 系统自动回退到原始手工优化的prompt
4. 保证系统稳定性

### Q6: 可以只优化部分功能吗？
**A**: 可以！你可以选择：
- 只优化clustering: `--train-clustering`
- 只优化dedup: `--train-dedup`
- 针对特定relation优化
- 逐步推广到生产环境

---

## 📚 延伸阅读

### DSPy相关
- [DSPy GitHub](https://github.com/stanfordnlp/dspy)
- [DSPy Paper](https://arxiv.org/abs/2406.11695)
- [DSPy Documentation](https://dspy-docs.vercel.app/)

### 本项目相关
- [LLM_CLUSTERING_README.md](./LLM_CLUSTERING_README.md) - LLM clustering原理
- [DUAL_LLM_GUIDE.md](./DUAL_LLM_GUIDE.md) - 双LLM配置
- [DEDUP_INTERMEDIATE_RESULTS.md](./DEDUP_INTERMEDIATE_RESULTS.md) - 去重结果分析

### Semantic Dedup相关
- [Coreference Resolution](https://en.wikipedia.org/wiki/Coreference) - 共指消解
- [Entity Linking](https://en.wikipedia.org/wiki/Entity_linking) - 实体链接
- [Knowledge Graph Deduplication](https://arxiv.org/abs/2010.03656) - 知识图谱去重

---

## 🤝 支持和反馈

如果你在使用过程中遇到问题或有改进建议：

1. **查看文档**: 首先查看本README和相关文档
2. **运行Demo**: 运行 `example_dspy_demo.py` 确认环境正常
3. **检查配置**: 确认API key和配置文件正确
4. **查看日志**: 检查错误日志获取详细信息

---

## ✅ 下一步

选择适合你的路径：

**🎯 如果想快速了解**:
→ 阅读 `DSPY_INTEGRATION_SUMMARY.md` (5分钟)

**💻 如果想立即使用**:
→ 跟随 `DSPY_QUICKSTART.md` (15分钟)

**🔬 如果想深入研究**:
→ 阅读 `DSPY_PROMPT_OPTIMIZATION_ANALYSIS.md` (60分钟)

**🚀 如果想直接体验**:
→ 运行 `python example_dspy_demo.py` (5分钟)

---

**祝使用愉快！有任何问题随时咨询。** 🎉
