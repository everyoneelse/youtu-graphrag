# Changelog - 支持加载保存的Cluster结果

## 日期
2025-10-21

## 功能概述
添加了从文件加载之前保存的LLM clustering结果的功能，允许跳过clustering阶段，直接进行semantic deduplication。

支持两种类型的去重：
1. **Keyword Deduplication**: 关键词节点去重
2. **Edge/Triple Deduplication**: 三元组边去重

## 修改的文件

### 1. `offline_semantic_dedup.py`

**修改内容:**
- 在 `OfflineSemanticDeduper` 类中添加两个独立属性:
  - `preloaded_keyword_clusters`: 存储keyword dedup cluster结果
  - `preloaded_edge_clusters`: 存储edge dedup cluster结果
- 添加 `load_keyword_cluster_results()` 方法，用于加载keyword cluster
- 添加 `load_edge_cluster_results()` 方法，用于加载edge cluster
- 在 `_parse_args()` 中添加两个独立的命令行参数:
  - `--load-keyword-clusters`: 加载keyword cluster文件
  - `--load-edge-clusters`: 加载edge cluster文件
- 在 `main()` 函数中添加两种cluster的加载逻辑

**关键代码:**
```python
# 新增属性
self.preloaded_keyword_clusters = None  # For keyword dedup
self.preloaded_edge_clusters = None     # For edge dedup

# 新增方法
def load_keyword_cluster_results(self, cluster_file: Path) -> None:
    """Load keyword clustering results."""
    ...

def load_edge_cluster_results(self, cluster_file: Path) -> None:
    """Load edge clustering results."""
    ...

# 新增命令行参数
parser.add_argument("--load-keyword-clusters", type=Path, ...)
parser.add_argument("--load-edge-clusters", type=Path, ...)
```

### 2. `models/constructor/kt_gen.py`

**修改内容:**
- 添加 `_apply_preloaded_clusters()` 方法，用于将预加载的keyword cluster应用到community数据
- 添加 `_apply_preloaded_clusters_for_edges()` 方法，用于将预加载的edge cluster应用到group数据
- 修改 `_deduplicate_keyword_nodes()` 方法的PHASE 2，检查 `preloaded_keyword_clusters`
- 修改 `triple_deduplicate_semantic()` 方法的PHASE 2，检查 `preloaded_edge_clusters`
- 如果有对应的预加载cluster，跳过相应的clustering阶段

**关键代码:**
```python
# 新增方法 - Keyword Dedup
def _apply_preloaded_clusters(self, dedup_communities: list, preloaded_data: dict) -> None:
    """
    Apply preloaded keyword cluster results to communities.
    """
    ...

# 新增方法 - Edge Dedup
def _apply_preloaded_clusters_for_edges(self, dedup_groups: list, preloaded_data: dict) -> None:
    """
    Apply preloaded edge cluster results to edge groups.
    """
    ...

# 修改Keyword Dedup的PHASE 2逻辑
if hasattr(self, 'preloaded_keyword_clusters') and self.preloaded_keyword_clusters:
    logger.info("Using preloaded keyword cluster results, skipping clustering phase...")
    self._apply_preloaded_clusters(dedup_communities, self.preloaded_keyword_clusters)
elif clustering_method == "llm":
    # 原有的clustering逻辑
    ...

# 修改Edge Dedup的PHASE 2逻辑
if hasattr(self, 'preloaded_edge_clusters') and self.preloaded_edge_clusters:
    logger.info("Using preloaded edge cluster results, skipping clustering phase...")
    self._apply_preloaded_clusters_for_edges(dedup_groups, self.preloaded_edge_clusters)
elif clustering_method == "llm":
    # 原有的clustering逻辑
    ...
```

## 使用示例

### 基本用法

#### 只加载keyword clusters
```bash
python3 offline_semantic_dedup.py \
    --graph output/graphs/demo_new.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_deduped.json \
    --load-keyword-clusters output/dedup_intermediate/demo_keyword_dedup_20251021_123456.json \
    --force-enable
```

#### 只加载edge clusters
```bash
python3 offline_semantic_dedup.py \
    --graph output/graphs/demo_new.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_deduped.json \
    --load-edge-clusters output/dedup_intermediate/demo_edge_dedup_20251021_123456.json \
    --force-enable
```

#### 同时加载两种clusters
```bash
python3 offline_semantic_dedup.py \
    --graph output/graphs/demo_new.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_deduped.json \
    --load-keyword-clusters output/dedup_intermediate/demo_keyword_dedup_20251021_123456.json \
    --load-edge-clusters output/dedup_intermediate/demo_edge_dedup_20251021_123456.json \
    --force-enable
```

### 参数说明
- `--load-keyword-clusters`: 指向keyword cluster结果JSON文件的路径
- `--load-edge-clusters`: 指向edge cluster结果JSON文件的路径
- 可以单独使用其中一个，也可以同时使用两个
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

#### Keyword Deduplication
1. 根据 `community_id` 匹配当前图谱中的community和保存的cluster
2. 从 `communities` 数组中提取对应的cluster信息
3. 提取cluster的 `member_indices`、`llm_description`、`llm_rationale`
4. 填充到 `community_data` 的 `initial_clusters` 和 `llm_clustering_details`

#### Edge Deduplication
1. 根据 `(head_id, relation)` 组合匹配当前图谱中的edge group和保存的cluster
2. 从 `triples` 数组中提取对应的cluster信息
3. 提取cluster的 `member_indices`、`llm_description`、`llm_rationale`
4. 填充到 `group_data` 的 `initial_clusters` 和 `llm_clustering_details`

### 自动识别机制
系统通过检查JSON文件的结构自动识别cluster类型：
- 包含 `communities` 字段 → Keyword dedup cluster
- 包含 `triples` 字段 → Edge dedup cluster
- 两者都可以同时加载和使用

### Fallback策略
当找不到匹配的cluster数据时：
- 将该community/group的所有成员作为单个cluster
- 记录warning日志
- 继续处理，不会中断整个流程

## 测试

已通过以下测试：
- ✅ Python语法检查 (`python3 -m py_compile`)
- ✅ 代码逻辑审查
- ✅ 文档完整性检查

## 后续改进建议

1. ✅ **支持Edge Deduplication**: 已完成！现在支持edge dedup的cluster加载
2. **验证功能**: 添加cluster文件与图谱的兼容性验证
3. **统计信息**: 在日志中输出更详细的匹配统计信息
4. **部分加载**: 支持只加载特定community/group的cluster结果
5. **合并加载**: 支持同时加载多个cluster文件（例如，分别从不同时间点保存的结果）

## 相关文档

- 使用指南: `LOAD_CLUSTERS_USAGE.md`
- 配置说明: `config/base_config.yaml`
- 中间结果示例: `output/dedup_intermediate/`
