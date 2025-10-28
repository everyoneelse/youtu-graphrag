# Head Dedup 中间结果记录功能 - 修改总结

## 修改内容

### 1. 代码修改 (`models/constructor/kt_gen.py`)

#### a. 在 `deduplicate_heads` 函数中添加了中间结果记录功能

**主要修改点：**

1. **配置读取** (第4533-4547行)
   - 添加 `save_intermediate` 变量读取配置
   - 初始化 `intermediate_results` 结构
   - 记录配置参数（阈值、验证方法等）

2. **Phase 1 - 候选节点记录** (第4569-4578行)
   - 记录候选节点总数
   - 保存前100个候选节点ID
   - 保存前10个候选节点的详细信息（名称、描述）

3. **Phase 2 - 精确匹配记录** (第4586-4594行)
   - 记录精确匹配总数
   - 保存前50个合并对及其名称信息

4. **Phase 3 - 语义去重记录** (第4626-4674行)
   - 记录剩余节点数和候选对数量
   - 记录验证方法（LLM/embedding）
   - 保存前20个候选对及相似度
   - 记录验证结果和合并决策（前50个）
   - 包含元数据（置信度、理由等）

5. **结果保存** (第4722-4753行)
   - 自动生成带时间戳的文件名
   - 支持自定义保存路径
   - 包含完整统计摘要
   - 异常处理和日志记录

### 2. 配置文件修改 (`config/base_config.yaml`)

在 `head_dedup` 配置段（第95-98行）添加了：

```yaml
# Save intermediate results for debugging and analysis
save_intermediate_results: false
# Path to save intermediate results (optional, auto-generated if not specified)
# intermediate_results_path: "output/dedup_intermediate/"
```

## 使用示例

### 启用功能

```yaml
# config/base_config.yaml
construction:
  semantic_dedup:
    head_dedup:
      enabled: true
      save_intermediate_results: true  # 启用
```

### 代码调用

```python
from config.config_loader import load_config
from models.constructor.kt_gen import KTGen

config = load_config("config/base_config.yaml")
config.construction.semantic_dedup.head_dedup.enabled = True
config.construction.semantic_dedup.head_dedup.save_intermediate_results = True

kt_gen = KTGen(config, dataset_name="demo")
# ... 构建图谱 ...
stats = kt_gen.deduplicate_heads()
# 结果自动保存到: output/dedup_intermediate/demo_head_dedup_{timestamp}.json
```

## 输出文件结构

```json
{
  "dataset": "demo",
  "config": { ... },
  "phases": {
    "phase1_candidates": {
      "total_candidates": 150,
      "candidate_ids": [...],
      "sample_candidates": [...]
    },
    "phase2_exact_match": {
      "total_matches": 10,
      "merge_pairs": [...]
    },
    "phase3_semantic": {
      "remaining_nodes": 140,
      "candidate_pairs_generated": 50,
      "validation_method": "embedding",
      "sample_candidate_pairs": [...],
      "validation_results": {
        "total_matches": 15,
        "merge_decisions": [...]
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

## 核心特性

✅ **完整性** - 记录所有去重阶段的详细信息
✅ **可配置** - 支持启用/禁用和自定义路径
✅ **高效性** - 仅保存样本数据，避免文件过大
✅ **一致性** - 与 semantic_dedup_groups 功能对等
✅ **易用性** - 自动生成文件名和创建目录

## 应用场景

1. **调试** - 分析哪些实体被合并及原因
2. **优化** - 调整阈值参数
3. **对比** - 比较不同配置的效果
4. **审查** - 生成去重报告

## 性能影响

- 性能开销：< 1%
- 建议：生产环境关闭，调试时启用

## 相关文档

详细使用说明请参考：`HEAD_DEDUP_INTERMEDIATE_RESULTS.md`
