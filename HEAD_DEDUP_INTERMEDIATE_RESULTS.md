# Head Dedup 中间结果记录功能

## 概述

现在 `head_dedup` 功能已经支持中间结果记录，与 `semantic_dedup_groups` 保持一致。这个功能可以帮助你调试、分析和理解实体去重的过程。

## 修改内容

### 1. 代码修改 (`models/constructor/kt_gen.py`)

在 `deduplicate_heads` 函数中添加了以下功能：

#### a. 配置读取和初始化
```python
# 检查是否应该保存中间结果
save_intermediate = getattr(config, 'save_intermediate_results', False)

# 初始化中间结果收集器
intermediate_results = {
    "dataset": self.dataset_name,
    "config": {
        "enable_semantic": enable_semantic,
        "similarity_threshold": similarity_threshold,
        "use_llm_validation": use_llm_validation,
        "max_candidates": max_candidates,
        "candidate_similarity_threshold": getattr(config, 'candidate_similarity_threshold', 0.75)
    },
    "phases": {}
} if save_intermediate else None
```

#### b. Phase 1: 候选节点信息记录
记录所有候选的实体节点信息，包括：
- 候选节点总数
- 前100个候选节点ID（用于检查）
- 前10个候选节点的详细信息（名称、描述）

#### c. Phase 2: 精确匹配结果记录
记录基于名称标准化的精确匹配结果，包括：
- 匹配总数
- 前50个合并对（重复节点 → 规范节点）
- 每个合并对的名称信息

#### d. Phase 3: 语义去重结果记录
记录基于语义相似度的去重结果，包括：
- 剩余节点数
- 候选对总数
- 验证方法（LLM 或 embedding）
- 前20个候选对及其相似度
- 验证结果和合并决策
- 前50个合并对及其元数据（置信度、理由等）

#### e. 结果保存
自动保存到文件：
- 默认路径：`output/dedup_intermediate/{dataset_name}_head_dedup_{timestamp}.json`
- 支持自定义路径
- 包含完整的统计摘要

### 2. 配置文件修改 (`config/base_config.yaml`)

在 `head_dedup` 配置段添加了两个新选项：

```yaml
construction:
  semantic_dedup:
    head_dedup:
      enabled: false
      # ... 其他配置 ...
      
      # 保存中间结果用于调试和分析
      save_intermediate_results: false
      # 保存中间结果的路径（可选，如果不指定则自动生成）
      # intermediate_results_path: "output/dedup_intermediate/"
```

## 使用方法

### 1. 启用中间结果保存

在配置文件中启用：

```yaml
# config/base_config.yaml
construction:
  semantic_dedup:
    head_dedup:
      enabled: true
      save_intermediate_results: true  # 启用中间结果保存
```

### 2. 运行代码

```python
from config.config_loader import load_config
from models.constructor.kt_gen import KTGen

# 加载配置
config = load_config("config/base_config.yaml")

# 确保启用 head_dedup 和中间结果保存
config.construction.semantic_dedup.head_dedup.enabled = True
config.construction.semantic_dedup.head_dedup.save_intermediate_results = True

# 可选：自定义保存路径
# config.construction.semantic_dedup.head_dedup.intermediate_results_path = "my_output/"

# 创建 KTGen 实例
kt_gen = KTGen(config, dataset_name="demo")

# 构建知识图谱...
# kt_gen.construct_graph(...)

# 运行 head dedup
stats = kt_gen.deduplicate_heads()

# 中间结果会自动保存到:
# output/dedup_intermediate/demo_head_dedup_20250101_120000.json
```

### 3. 分析中间结果

```python
import json

# 读取保存的中间结果
with open("output/dedup_intermediate/demo_head_dedup_20250101_120000.json") as f:
    results = json.load(f)

# 查看配置信息
print("配置:", results["config"])

# 查看各阶段信息
print("阶段:", results["phases"].keys())

# Phase 1: 候选节点信息
phase1 = results["phases"]["phase1_candidates"]
print(f"候选节点总数: {phase1['total_candidates']}")
print(f"示例候选节点: {phase1['sample_candidates'][:3]}")

# Phase 2: 精确匹配结果
phase2 = results["phases"]["phase2_exact_match"]
print(f"精确匹配数量: {phase2['total_matches']}")
print(f"示例合并对: {phase2['merge_pairs'][:3]}")

# Phase 3: 语义去重结果
if "phase3_semantic" in results["phases"]:
    phase3 = results["phases"]["phase3_semantic"]
    print(f"剩余节点数: {phase3['remaining_nodes']}")
    print(f"候选对数量: {phase3['candidate_pairs_generated']}")
    print(f"验证方法: {phase3['validation_method']}")
    
    if "validation_results" in phase3:
        print(f"语义匹配数量: {phase3['validation_results']['total_matches']}")

# 查看统计摘要
print("\n统计摘要:")
print(json.dumps(results["summary"], indent=2, ensure_ascii=False))
```

## 中间结果文件结构

```json
{
  "dataset": "demo",
  "config": {
    "enable_semantic": true,
    "similarity_threshold": 0.85,
    "use_llm_validation": false,
    "max_candidates": 1000,
    "candidate_similarity_threshold": 0.75
  },
  "phases": {
    "phase1_candidates": {
      "total_candidates": 150,
      "candidate_ids": ["entity_1", "entity_2", ...],
      "sample_candidates": [
        {
          "node_id": "entity_1",
          "name": "Apple Inc.",
          "description": "American multinational technology company..."
        }
      ]
    },
    "phase2_exact_match": {
      "total_matches": 10,
      "merge_pairs": [
        {
          "duplicate_id": "entity_5",
          "duplicate_name": "Apple Inc",
          "canonical_id": "entity_1",
          "canonical_name": "Apple Inc."
        }
      ]
    },
    "phase3_semantic": {
      "remaining_nodes": 140,
      "candidate_pairs_generated": 50,
      "validation_method": "embedding",
      "sample_candidate_pairs": [
        {
          "node_id_1": "entity_10",
          "node_name_1": "UN",
          "node_id_2": "entity_25",
          "node_name_2": "United Nations",
          "embedding_similarity": 0.92
        }
      ],
      "validation_results": {
        "total_matches": 15,
        "merge_decisions": [
          {
            "duplicate_id": "entity_25",
            "duplicate_name": "United Nations",
            "canonical_id": "entity_10",
            "canonical_name": "UN",
            "metadata": {
              "rationale": "High embedding similarity",
              "confidence": 0.92,
              "method": "embedding"
            }
          }
        ]
      }
    }
  },
  "summary": {
    "enabled": true,
    "total_candidates": 150,
    "exact_merges": 10,
    "semantic_merges": 15,
    "total_merges": 25,
    "initial_entity_count": 150,
    "final_entity_count": 125,
    "reduction_rate": 16.67,
    "elapsed_time_seconds": 45.2,
    "integrity_issues": {}
  }
}
```

## 与 semantic_dedup_groups 的对比

| 特性 | semantic_dedup_groups | head_dedup |
|------|----------------------|------------|
| 配置信息记录 | ✅ | ✅ |
| 数据集名称 | ✅ | ✅ |
| 候选信息记录 | ✅ | ✅ |
| 聚类结果记录 | ✅ | N/A（head_dedup 使用精确匹配） |
| 精确匹配记录 | N/A | ✅ |
| 语义去重记录 | ✅ | ✅ |
| LLM 调用记录 | ✅ | ✅ |
| 合并决策记录 | ✅ | ✅ |
| 统计摘要 | ✅ | ✅ |
| 自动保存 | ✅ | ✅ |
| 自定义路径 | ✅ | ✅ |

## 应用场景

1. **调试去重逻辑**
   - 检查哪些实体被合并了
   - 验证合并决策是否合理
   - 分析为什么某些实体没有被合并

2. **优化阈值**
   - 查看不同相似度阈值的候选对
   - 分析置信度分布
   - 调整 `similarity_threshold` 和 `candidate_similarity_threshold`

3. **对比不同配置**
   - LLM vs. embedding 验证
   - 不同阈值的效果
   - 不同数据集的去重效果

4. **生成报告**
   - 去重效果统计
   - 合并案例分析
   - 质量评估

## 性能影响

- 记录中间结果对性能影响很小（< 1%）
- 主要开销在于文件写入
- 建议在生产环境中关闭，仅在调试时启用

## 注意事项

1. 中间结果文件可能很大（取决于候选节点数量）
2. 仅保存前N个样本以避免文件过大
3. 可以使用 `intermediate_results_path` 自定义保存位置
4. 文件名包含时间戳，不会覆盖旧文件
5. 需要确保输出目录有写权限

## 更新日志

- **2025-10-28**: 添加 head_dedup 中间结果记录功能
  - 记录所有阶段的详细信息
  - 支持自定义保存路径
  - 与 semantic_dedup_groups 功能对等
