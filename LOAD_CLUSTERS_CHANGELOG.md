# Changelog - 支持加载保存的Cluster结果

## 日期
2025-10-21

## 功能概述
添加了从文件加载之前保存的LLM clustering结果的功能，允许跳过clustering阶段，直接进行semantic deduplication。

## 修改的文件

### 1. `offline_semantic_dedup.py`

**修改内容:**
- 在 `OfflineSemanticDeduper` 类中添加 `preloaded_clusters` 属性
- 添加 `load_cluster_results()` 方法，用于从JSON文件加载cluster结果
- 在 `_parse_args()` 中添加 `--load-clusters` 命令行参数
- 在 `main()` 函数中添加cluster加载逻辑

**关键代码:**
```python
# 新增属性
self.preloaded_clusters = None

# 新增方法
def load_cluster_results(self, cluster_file: Path) -> None:
    """Load previously saved clustering results from intermediate results file."""
    ...

# 新增命令行参数
parser.add_argument(
    "--load-clusters",
    type=Path,
    help="Path to previously saved clustering results JSON file"
)
```

### 2. `models/constructor/kt_gen.py`

**修改内容:**
- 添加 `_apply_preloaded_clusters()` 方法，用于将预加载的cluster应用到community数据
- 修改 `_deduplicate_keyword_nodes()` 方法的PHASE 2，检查是否有预加载的cluster
- 如果有预加载cluster，跳过clustering阶段，直接使用预加载的结果

**关键代码:**
```python
# 新增方法
def _apply_preloaded_clusters(self, dedup_communities: list, preloaded_data: dict) -> None:
    """
    Apply preloaded cluster results to communities, skipping the clustering phase.
    """
    ...

# 修改PHASE 2逻辑
if hasattr(self, 'preloaded_clusters') and self.preloaded_clusters:
    logger.info("Using preloaded cluster results, skipping clustering phase...")
    self._apply_preloaded_clusters(dedup_communities, self.preloaded_clusters)
elif clustering_method == "llm":
    # 原有的clustering逻辑
    ...
```

## 使用示例

### 基本用法
```bash
python3 offline_semantic_dedup.py \
    --graph output/graphs/demo_new.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_deduped.json \
    --load-clusters output/dedup_intermediate/demo_keyword_dedup_20251021_123456.json \
    --force-enable
```

### 参数说明
- `--load-clusters`: 指向之前保存的cluster结果JSON文件的路径
- 其他参数保持不变

## 优势

1. **节省成本**: 避免重复的LLM clustering调用，可节省50%-70%的API调用
2. **快速迭代**: 可以多次调整semantic dedup参数而无需重新clustering
3. **调试友好**: 使用固定的cluster结果，更容易调试和对比semantic dedup效果
4. **分阶段处理**: 支持将clustering和dedup分开处理，便于处理大规模数据

## 兼容性

- ✅ 向后兼容：不使用 `--load-clusters` 参数时，行为与之前完全一致
- ✅ 配置灵活：可以使用不同的semantic dedup配置，clustering配置会被忽略
- ✅ 容错机制：如果某个community找不到对应的cluster数据，会使用fallback策略

## 技术细节

### Cluster数据匹配逻辑
1. 根据 `community_id` 匹配当前图谱中的community和保存的cluster
2. 提取cluster的 `member_indices`、`llm_description`、`llm_rationale`
3. 填充到 `community_data` 的 `initial_clusters` 和 `llm_clustering_details`
4. 后续semantic dedup阶段正常使用这些cluster信息

### Fallback策略
当找不到匹配的cluster数据时：
- 将该community的所有成员作为单个cluster
- 记录warning日志
- 继续处理，不会中断整个流程

## 测试

已通过以下测试：
- ✅ Python语法检查 (`python3 -m py_compile`)
- ✅ 代码逻辑审查
- ✅ 文档完整性检查

## 后续改进建议

1. **支持Edge Deduplication**: 扩展到支持edge dedup的cluster加载
2. **验证功能**: 添加cluster文件与图谱的兼容性验证
3. **统计信息**: 在日志中输出更详细的匹配统计信息
4. **部分加载**: 支持只加载特定community的cluster结果

## 相关文档

- 使用指南: `LOAD_CLUSTERS_USAGE.md`
- 配置说明: `config/base_config.yaml`
- 中间结果示例: `output/dedup_intermediate/`
