# 并发LLM处理优化说明

## 概述

本次修改优化了 `_semantic_deduplicate_group` 方法中的LLM调用策略，将原本顺序执行的LLM调用改为**先收集所有prompts，然后统一并发处理**的模式，从而显著提升处理效率。

## 修改内容

### 1. 新增方法：`_concurrent_llm_calls`

**位置**: `models/constructor/kt_gen.py` (第 1290 行之后)

**功能**: 并发处理多个LLM prompts

**方法签名**:
```python
def _concurrent_llm_calls(self, prompts_with_metadata: list) -> list:
    """
    Concurrently process multiple LLM prompts.
    
    Args:
        prompts_with_metadata: List of dicts with keys:
            - 'type': 'clustering' or 'semantic'
            - 'prompt': the prompt string
            - 'metadata': additional metadata for processing results
            
    Returns:
        List of dicts with keys:
            - 'type': same as input
            - 'response': raw LLM response
            - 'metadata': same as input
            - 'error': error message if failed (None if successful)
    """
```

**特点**:
- 使用 `ThreadPoolExecutor` 实现并发处理
- 支持 `clustering` 和 `semantic` 两种prompt类型
- 根据prompt类型自动选择对应的LLM客户端
- 错误处理：单个prompt失败不影响其他prompts
- 限制最大并发数为10，避免API限流

### 2. 重构方法：`_semantic_deduplicate_group`

**位置**: `models/constructor/kt_gen.py` (第 1960 行)

**主要变化**:

#### 原有流程（顺序处理）:
```
1. 执行 LLM clustering（如果启用）
2. 遍历每个cluster
   - 对每个batch调用 LLM semantic grouping
   - 处理结果
   - 构建最终edges
```

#### 新流程（并发处理）:
```
PHASE 1: 收集所有prompts
├── 1.1: 收集clustering prompts（如果启用LLM clustering）
│   └── 支持批次化处理
└── 1.2: 预准备semantic grouping prompts收集

PHASE 2A: 并发处理clustering prompts
├── 调用 _concurrent_llm_calls 并发执行
├── 解析clustering结果
└── 生成initial_clusters

PHASE 2B: 收集semantic grouping prompts
├── 基于clustering结果
├── 遍历每个cluster
└── 收集所有需要semantic grouping的batch prompts

PHASE 3: 并发处理所有semantic grouping prompts
├── 调用 _concurrent_llm_calls 并发执行
└── 解析semantic grouping结果

PHASE 4: 处理结果并构建final edges
├── 创建cluster_idx到semantic结果的映射
├── 遍历每个cluster
├── 应用semantic grouping结果
└── 构建最终的deduplicated edges
```

## 关键改进

### 1. 性能提升
- **原方案**: 所有LLM调用顺序执行，总时间 = Σ(每个调用时间)
- **新方案**: 同类型prompts并发执行，总时间 ≈ max(单个调用时间)
- **预期提升**: 在有多个clusters需要semantic grouping时，可获得 N倍加速（N为并发数）

### 2. 代码结构优化
- 清晰的分阶段处理流程
- 更好的关注点分离
- 易于理解和维护

### 3. 灵活性
- 支持embedding和LLM两种clustering方法
- 自动处理批次化
- 优雅的错误处理

## 兼容性

### 完全兼容原有功能:
- ✅ 保留所有原有参数和配置
- ✅ 保留intermediate results保存逻辑
- ✅ 保留single-item cluster优化
- ✅ 保留max_candidates限制
- ✅ 保留overflow处理逻辑
- ✅ 输出格式完全一致

### 向后兼容:
- ✅ 不需要修改配置文件
- ✅ 不需要修改调用代码
- ✅ 所有现有测试应该正常通过

## 使用示例

无需修改使用方式，函数签名和行为保持一致：

```python
# 使用方式完全相同
builder = KTBuilder("dataset_name", config=config)
deduped_edges = builder._semantic_deduplicate_group(
    head_id="some_entity",
    relation="some_relation",
    edges=edge_list
)
```

## 性能对比示例

假设有以下场景：
- 5个clusters需要semantic grouping
- 每个cluster需要2个batch
- 每个LLM调用耗时2秒

**原方案（顺序执行）**:
```
Clustering: 2s
Semantic grouping: 5 clusters × 2 batches × 2s = 20s
总计: 22s
```

**新方案（并发执行）**:
```
Clustering: 2s（单个或少量batches）
Semantic grouping: ~2s（所有batches并发）
总计: ~4s
```

**加速比**: ~5.5倍

## 技术细节

### 并发实现
- 使用 `concurrent.futures.ThreadPoolExecutor`
- 线程池大小：min(10, prompt数量)
- 线程安全：每个线程独立调用LLM API

### 错误处理
- 单个prompt失败不影响其他prompts
- 失败的prompt返回error信息
- Clustering失败使用fallback策略
- Semantic grouping失败视为无grouping

### 内存管理
- 所有prompts在内存中收集（通常数量不大）
- 结果逐个处理，避免大量内存占用

## 测试建议

1. **单元测试**:
   - 测试 `_concurrent_llm_calls` 方法
   - 验证错误处理逻辑
   - 验证并发正确性

2. **集成测试**:
   - 使用真实数据测试完整流程
   - 对比修改前后的输出一致性
   - 测量性能提升

3. **边界情况**:
   - 单个cluster
   - 大量小clusters
   - 少量大clusters
   - API调用失败场景

## 注意事项

1. **API限流**: 注意LLM服务商的并发限制，当前默认限制为10个并发
2. **成本**: 并发调用不会减少API调用次数，只是加快处理速度
3. **调试**: 并发执行时日志可能交错，需要通过metadata追踪

## 文件修改清单

- ✅ `models/constructor/kt_gen.py`
  - 新增 `_concurrent_llm_calls` 方法
  - 重构 `_semantic_deduplicate_group` 方法

## 版本信息

- 修改日期: 2025-10-20
- 修改分支: cursor/concurrent-llm-prompt-processing-and-grouping-3896
- 修改类型: 性能优化 + 代码重构
- 破坏性变更: 无
