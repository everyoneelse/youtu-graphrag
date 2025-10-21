# 加载已保存的Cluster结果进行Semantic Dedup

## 功能说明

该功能允许你跳过LLM clustering阶段，直接使用之前保存的cluster结果进行semantic deduplication。这在以下场景中特别有用：

1. **节省成本**: 避免重复调用LLM进行clustering
2. **调试优化**: 可以使用相同的cluster结果，多次调试semantic dedup参数
3. **分阶段处理**: 先完成clustering，再单独运行semantic dedup

## 使用方法

### 第一步：保存Cluster结果

首先，确保你的配置文件中启用了中间结果保存：

```yaml
construction:
  semantic_dedup:
    enabled: true
    clustering_method: llm  # 或 embedding
    save_intermediate_results: true
    # 可选：指定保存路径
    intermediate_results_path: "output/dedup_intermediate/"
```

运行知识图谱构建或离线去重时，会自动保存cluster结果到JSON文件中，例如：
- `output/dedup_intermediate/demo_keyword_dedup_20251021_123456.json`

### 第二步：使用保存的Cluster结果

使用 `offline_semantic_dedup.py` 脚本，添加 `--load-clusters` 参数：

```bash
python3 offline_semantic_dedup.py \
    --graph output/graphs/demo_new.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_deduped_v2.json \
    --load-clusters output/dedup_intermediate/demo_keyword_dedup_20251021_123456.json \
    --force-enable
```

### 参数说明

- `--graph`: 输入的知识图谱JSON文件
- `--chunks`: chunk文件或目录
- `--output`: 输出的去重后图谱文件
- `--load-clusters`: **新增参数** - 之前保存的cluster结果JSON文件路径
- `--force-enable`: 强制启用semantic dedup（即使配置中禁用）
- `--config`: （可选）自定义配置文件

## Cluster结果文件格式

保存的cluster结果文件包含以下结构：

```json
{
  "dataset": "demo",
  "config": {
    "threshold": 0.85,
    "max_batch_size": 8,
    "max_candidates": 50,
    "clustering_method": "llm"
  },
  "communities": [
    {
      "community_id": "community_xxx",
      "total_candidates": 10,
      "clustering": {
        "method": "llm",
        "clusters": [
          {
            "cluster_id": 0,
            "size": 3,
            "member_indices": [0, 2, 5],
            "llm_description": "关于时间相关的概念",
            "llm_rationale": "这些都描述时间相关的属性",
            "members": [
              {
                "index": 0,
                "node_id": "keyword_node_1",
                "description": "时间"
              }
            ]
          }
        ]
      }
    }
  ],
  "summary": {
    "total_communities": 5,
    "total_candidates": 50,
    "total_clusters": 15
  }
}
```

## 工作原理

1. **加载阶段**: 脚本读取之前保存的cluster结果JSON文件
2. **匹配阶段**: 根据community_id匹配当前图谱中的社区和保存的cluster信息
3. **跳过Clustering**: 直接使用加载的cluster结果，跳过LLM clustering调用
4. **Semantic Dedup**: 正常执行semantic deduplication阶段
5. **保存结果**: 输出去重后的知识图谱

## 注意事项

1. **图谱一致性**: 确保使用的图谱与保存cluster结果时的图谱一致或兼容
2. **Community匹配**: 如果某个community在cluster文件中找不到，会使用fallback策略（所有成员作为单个cluster）
3. **配置兼容**: semantic dedup的配置参数（如max_batch_size）可以与clustering时不同，允许独立调优

## 示例场景

### 场景1: 优化Semantic Dedup参数

```bash
# 第一次运行：完整的clustering + dedup
python3 offline_semantic_dedup.py \
    --graph output/graphs/demo.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_dedup_v1.json \
    --config config/my_config.yaml

# 保存的cluster结果: output/dedup_intermediate/demo_keyword_dedup_20251021_120000.json

# 第二次运行：调整dedup参数，使用已有cluster
# 修改配置文件中的 max_batch_size 或其他dedup参数
python3 offline_semantic_dedup.py \
    --graph output/graphs/demo.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_dedup_v2.json \
    --load-clusters output/dedup_intermediate/demo_keyword_dedup_20251021_120000.json \
    --config config/my_config_v2.yaml
```

### 场景2: 分阶段处理大规模数据

```bash
# 阶段1: 只运行到clustering（通过主流程，会自动保存）
python3 main.py --dataset large_dataset --mode construct

# 检查clustering结果，确认无误后
# 阶段2: 使用保存的cluster进行dedup
python3 offline_semantic_dedup.py \
    --graph output/graphs/large_dataset_new.json \
    --chunks output/chunks/large_dataset.txt \
    --output output/graphs/large_dataset_deduped.json \
    --load-clusters output/dedup_intermediate/large_dataset_keyword_dedup_xxx.json
```

## 技术细节

修改的主要文件：
- `offline_semantic_dedup.py`: 添加 `--load-clusters` 参数和加载逻辑
- `models/constructor/kt_gen.py`: 
  - 添加 `preloaded_clusters` 属性
  - 实现 `_apply_preloaded_clusters()` 方法
  - 修改 `_deduplicate_keyword_nodes()` 在PHASE 2中检查并使用预加载的cluster

## 常见问题

**Q: 如果cluster文件中的community在当前图谱中不存在会怎样？**  
A: 会跳过该community，并记录warning日志。

**Q: 可以使用不同配置文件吗？**  
A: 可以。clustering配置（如clustering_method, llm_clustering_batch_size）会被忽略，但semantic dedup配置（如max_batch_size）仍然生效。

**Q: 支持edge deduplication吗？**  
A: 当前版本主要支持keyword deduplication。Edge deduplication暂不支持加载预保存的cluster。

**Q: 性能提升如何？**  
A: 跳过clustering阶段可以节省50%-70%的LLM调用次数，具体取决于你的数据规模和clustering配置。
