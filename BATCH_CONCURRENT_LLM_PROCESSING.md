# 批量并发LLM处理优化说明

## 概述

本次修改将LLM调用的并发粒度从**单个head-relation级别**提升到**全局批量级别**，实现了：

1. **全局收集**: 收集所有head-relation组合的prompts
2. **批量并发处理**: 统一并发处理所有clustering prompts，然后统一并发处理所有semantic dedup prompts
3. **后处理**: 根据所有LLM结果构建最终的去重图

这种架构能够最大化并发效率，显著减少总处理时间。

## 架构设计

### 原有架构（顺序处理）

```
for each (head, relation) group:
    ├── LLM clustering (if enabled)
    │   ├── batch 1
    │   ├── batch 2
    │   └── ...
    ├── for each cluster:
    │   ├── LLM semantic dedup batch 1
    │   ├── LLM semantic dedup batch 2
    │   └── ...
    └── build edges
```

**问题**: 所有LLM调用串行执行，即使不同head-relation组之间没有依赖关系。

### 新架构（批量并发处理）

```
PHASE 1: 准备所有dedup groups
├── 遍历所有 (head, relation) 组合
├── 对每组进行exact dedup
└── 准备需要semantic dedup的组的元数据

PHASE 2: 批量clustering
├── 收集所有clustering prompts（来自所有groups）
├── 统一并发处理所有clustering prompts
└── 解析结果并更新所有groups

PHASE 3: 批量semantic dedup
├── 基于clustering结果收集所有semantic dedup prompts
├── 统一并发处理所有semantic dedup prompts
└── 解析结果并更新所有groups

PHASE 4: 构建最终图
└── 根据所有groups的结果构建deduplicated edges
```

**优势**: 
- 所有同类型的LLM调用并发执行
- 最大化API throughput
- 总时间 ≈ max(单个调用时间) 而非 Σ(所有调用时间)

## 核心修改

### 1. 新增辅助方法

#### `_prepare_dedup_group(head_id, relation, edges, config)`
**功能**: 为一个head-relation组准备所有需要的元数据

**返回**: 包含以下字段的dict
```python
{
    'head_id': str,
    'head_text': str,
    'relation': str,
    'edges': list,
    'entries': list,  # 每个edge的详细信息
    'head_context_lines': list,
    'candidate_descriptions': list,
    'config_params': dict,
    'initial_clusters': None,  # 由clustering填充
    'llm_clustering_details': None,  # 由LLM clustering填充
    'semantic_results': {},  # 由semantic dedup填充
}
```

#### `_collect_clustering_prompts(group_data)`
**功能**: 收集一个group的所有clustering prompts

**返回**: prompt列表
```python
[
    {
        'type': 'clustering',
        'prompt': str,
        'metadata': {
            'batch_start': int,
            'batch_end': int,
            'batch_offset': int,
            'descriptions': list,
            'group_idx': int,  # 添加后标识来自哪个group
        }
    },
    ...
]
```

#### `_parse_clustering_results(dedup_groups, clustering_results)`
**功能**: 解析所有clustering结果并更新dedup_groups

**处理逻辑**:
1. 按group_idx分组结果
2. 对每个group解析clustering结果
3. 更新group_data的initial_clusters和llm_clustering_details

#### `_apply_embedding_clustering(group_data)`
**功能**: 对一个group应用embedding-based clustering

#### `_collect_semantic_dedup_prompts(group_data)`
**功能**: 收集一个group的所有semantic dedup prompts

**返回**: prompt列表
```python
[
    {
        'type': 'semantic',
        'prompt': str,
        'metadata': {
            'cluster_idx': int,
            'batch_num': int,
            'batch_indices': list,
            'overflow_indices': list,
            'group_idx': int,  # 添加后标识来自哪个group
        }
    },
    ...
]
```

#### `_parse_semantic_dedup_results(dedup_groups, semantic_results)`
**功能**: 解析所有semantic dedup结果并更新dedup_groups

**处理逻辑**:
1. 按group_idx分组结果
2. 对每个group解析semantic dedup结果
3. 更新group_data的semantic_results

#### `_build_final_edges(group_data, save_intermediate)`
**功能**: 根据group_data中的所有结果构建最终的deduplicated edges

**返回**: `[(tail_id, edge_data), ...]`

### 2. 重构 `triple_deduplicate_semantic()`

将原来的循环处理改为4个阶段：

```python
def triple_deduplicate_semantic(self):
    # PHASE 1: 准备所有groups
    dedup_groups = []
    for (head, relation), edges in grouped_edges.items():
        exact_unique = self._deduplicate_exact(edges)
        if self._semantic_dedup_enabled() and len(exact_unique) > 1:
            group_data = self._prepare_dedup_group(head, relation, exact_unique, config)
            dedup_groups.append(group_data)
    
    # PHASE 2: 批量clustering
    if clustering_method == "llm":
        clustering_prompts = []
        for group_idx, group_data in enumerate(dedup_groups):
            prompts = self._collect_clustering_prompts(group_data)
            for prompt in prompts:
                prompt['metadata']['group_idx'] = group_idx
            clustering_prompts.extend(prompts)
        
        clustering_results = self._concurrent_llm_calls(clustering_prompts)
        self._parse_clustering_results(dedup_groups, clustering_results)
    else:
        for group_data in dedup_groups:
            self._apply_embedding_clustering(group_data)
    
    # PHASE 3: 批量semantic dedup
    semantic_prompts = []
    for group_idx, group_data in enumerate(dedup_groups):
        prompts = self._collect_semantic_dedup_prompts(group_data)
        for prompt in prompts:
            prompt['metadata']['group_idx'] = group_idx
        semantic_prompts.extend(prompts)
    
    semantic_results = self._concurrent_llm_calls(semantic_prompts)
    self._parse_semantic_dedup_results(dedup_groups, semantic_results)
    
    # PHASE 4: 构建最终图
    for group_data in dedup_groups:
        final_edges = self._build_final_edges(group_data, save_intermediate)
        for tail_id, edge_data in final_edges:
            new_graph.add_edge(head, tail_id, **edge_data)
```

## 性能提升分析

### 场景示例

假设有以下场景：
- 10个(head, relation)组需要去重
- 每组平均5个clusters
- 每个cluster平均2个batches需要semantic dedup
- 每个LLM调用耗时2秒

#### 原架构（顺序）：
```
Clustering: 10 groups × 2s = 20s
Semantic dedup: 10 groups × 5 clusters × 2 batches × 2s = 200s
总计: 220s
```

#### 新架构（批量并发）：
```
Clustering: ~2-4s (10个并发，受限于并发数10)
Semantic dedup: ~20-40s (100个并发分批，每批10个)
总计: ~22-44s
```

**加速比**: **5-10倍**

### 并发数限制

当前实现中 `_concurrent_llm_calls` 限制最大并发数为10：

```python
max_workers = min(10, len(prompts_with_metadata))
```

这是为了：
1. 避免API限流
2. 控制资源消耗
3. 平衡性能和稳定性

可以根据实际API限制调整此参数。

## 兼容性

### ✅ 完全向后兼容
- 保留所有原有配置参数
- 保留intermediate results保存逻辑
- 输出格式完全一致
- 函数签名不变

### ✅ 功能保持
- Single-item cluster优化
- max_candidates限制
- Overflow处理
- 错误处理和fallback机制

## 使用方式

**无需任何修改**，使用方式与之前完全相同：

```python
builder = KTBuilder("dataset_name", config=config)
builder.triple_deduplicate_semantic()
```

## 日志输出

新架构增加了更详细的进度日志：

```
INFO: Prepared 10 groups for semantic deduplication
INFO: Collecting all clustering prompts...
INFO: Collected 15 clustering prompts, processing concurrently...
INFO: Parsing clustering results...
INFO: Using embedding-based clustering...
INFO: Collecting all semantic dedup prompts...
INFO: Collected 98 semantic dedup prompts, processing concurrently...
INFO: Parsing semantic dedup results...
INFO: Building final deduplicated graph...
INFO: Semantic deduplication completed
```

## 注意事项

### 1. 内存使用
- 所有prompts和结果会在内存中累积
- 对于超大图可能需要更多内存
- 通常不是问题（prompts数量一般在百到千级别）

### 2. API限流
- 并发调用可能触发API限流
- 可以通过调整 `_concurrent_llm_calls` 中的 `max_workers` 控制
- 建议根据API provider的限制调整

### 3. 成本
- 并发不会减少API调用次数
- 只是加快处理速度
- 总cost与原架构相同

### 4. 调试
- 并发执行时日志可能交错
- 使用metadata中的group_idx追踪
- save_intermediate可以帮助调试

## 文件修改清单

- ✅ `models/constructor/kt_gen.py`
  - 保留 `_concurrent_llm_calls` 方法
  - 废弃之前对 `_semantic_deduplicate_group` 的修改
  - 新增 `_prepare_dedup_group` 方法
  - 新增 `_collect_clustering_prompts` 方法
  - 新增 `_parse_clustering_results` 方法
  - 新增 `_apply_embedding_clustering` 方法
  - 新增 `_collect_semantic_dedup_prompts` 方法
  - 新增 `_parse_semantic_dedup_results` 方法
  - 新增 `_build_final_edges` 方法
  - 重构 `triple_deduplicate_semantic` 方法

## 测试建议

### 1. 功能测试
- 对比修改前后输出的一致性
- 验证edge数量和内容
- 检查metadata完整性

### 2. 性能测试
- 测量不同规模数据集的处理时间
- 对比串行vs并发的时间差异
- 监控内存使用

### 3. 边界测试
- 单个group
- 大量小groups
- 少量大groups
- API调用失败场景

### 4. 压力测试
- 超大规模数据集
- API限流场景
- 并发错误处理

## 未来优化方向

1. **动态并发数**: 根据API响应动态调整max_workers
2. **流式处理**: 边收集边处理，减少内存峰值
3. **断点续传**: 支持中断后从上次位置继续
4. **结果缓存**: 缓存LLM结果避免重复调用
5. **批次优化**: 智能分批，平衡batch size和并发数

## 版本信息

- 修改日期: 2025-10-20
- 修改分支: cursor/concurrent-llm-prompt-processing-and-grouping-3896
- 修改类型: 重大架构重构 + 性能优化
- 破坏性变更: 无
- 预期性能提升: 5-10倍（取决于数据规模和并发配置）
