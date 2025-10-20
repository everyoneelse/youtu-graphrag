# LLM-based Clustering Feature - 更新日志

## 概述

本次更新为 semantic deduplication 添加了基于 LLM 的聚类功能，可以更准确地对共享相同 head 和 relation 的 tail 进行初步分组。

## 新增功能

### 1. LLM 聚类方法

**新增函数：** `_cluster_candidate_tails_with_llm()`

- **位置：** `models/constructor/kt_gen.py:827`
- **功能：** 使用 LLM 对 tail 进行语义聚类
- **特点：**
  - 只使用 tail 描述，不包含 context
  - 支持批次处理（大量 tail 时自动分批）
  - 失败时自动回退到安全模式

**新增辅助函数：** `_llm_cluster_batch()`

- **位置：** `models/constructor/kt_gen.py:858`
- **功能：** 处理单个批次的 LLM 聚类请求

### 2. 新增 Prompt 模板

**常量名：** `DEFAULT_LLM_CLUSTERING_PROMPT`

- **位置：** `models/constructor/kt_gen.py:145`
- **内容：** 专门设计的 LLM 聚类 prompt，强调：
  - 初步分组目标
  - 包容性原则（宁可过度聚类）
  - 基于语义相似性分组
  - 清晰分离明显不同的实体

### 3. 配置选项

**新增配置项（在 `SemanticDedupConfig` 中）：**

```python
clustering_method: str = "embedding"  # "embedding" or "llm"
llm_clustering_batch_size: int = 30
save_intermediate_results: bool = False
intermediate_results_path: str = ""
```

**配置文件更新：**

- `config/base_config.yaml`: 添加 `clustering_method` 和 `llm_clustering_batch_size`
- `config/config_loader.py`: 更新 `SemanticDedupConfig` 类

### 4. 代码修改

**修改的函数：** `_semantic_deduplicate_group()`

- **位置：** `models/constructor/kt_gen.py:1627`
- **改动：** 
  - 添加 `clustering_method` 配置检查
  - 根据配置选择使用 embedding 或 LLM 聚类
  - 添加调试日志

**修改的函数：** `_deduplicate_keyword_nodes()`

- **位置：** `models/constructor/kt_gen.py:1258`
- **改动：**
  - 添加 `clustering_method` 配置检查
  - 支持 LLM 聚类用于关键词去重

## 文件清单

### 修改的文件

1. **models/constructor/kt_gen.py**
   - 添加 `DEFAULT_LLM_CLUSTERING_PROMPT` 常量
   - 添加 `_cluster_candidate_tails_with_llm()` 方法
   - 添加 `_llm_cluster_batch()` 方法
   - 修改 `_semantic_deduplicate_group()` 支持 LLM 聚类
   - 修改 `_deduplicate_keyword_nodes()` 支持 LLM 聚类

2. **config/base_config.yaml**
   - 添加 `clustering_method: embedding`
   - 添加 `llm_clustering_batch_size: 30`
   - 添加注释说明

3. **config/config_loader.py**
   - 更新 `SemanticDedupConfig` 类
   - 添加新的配置字段

### 新增的文件

1. **config/example_with_llm_clustering.yaml**
   - LLM 聚类的完整配置示例
   - 包含详细注释

2. **LLM_CLUSTERING_README.md**
   - 完整的使用文档
   - 包含原理说明、配置方法、最佳实践等

3. **test_llm_clustering.py**
   - 测试脚本
   - 包含两个测试案例（导演、城市）

4. **LLM_CLUSTERING_CHANGELOG.md**
   - 本文件，记录所有改动

## 工作流程对比

### 原有流程（Embedding 聚类）

```
Tails → Embedding → 层次聚类 → 初步 Clusters → LLM 去重 → 结果
```

### 新流程（LLM 聚类）

```
Tails → LLM 语义聚类 → 初步 Clusters → LLM 去重 → 结果
```

### 关键差异

| 方面 | Embedding 聚类 | LLM 聚类 |
|------|---------------|----------|
| 速度 | 快 | 较慢 |
| 成本 | 低 | 较高 |
| 准确性 | 中等 | 高 |
| 适用规模 | 大规模 | 中小规模 |
| LLM 调用 | 0 次（聚类阶段） | ~N/30 次 |

## 使用方法

### 启用 LLM 聚类

在配置文件中设置：

```yaml
construction:
  semantic_dedup:
    enabled: true
    clustering_method: llm
    llm_clustering_batch_size: 30
```

### 使用 Embedding 聚类（默认）

```yaml
construction:
  semantic_dedup:
    enabled: true
    clustering_method: embedding
    embedding_threshold: 0.85
```

### 运行测试

```bash
python test_llm_clustering.py
```

## 技术细节

### LLM 聚类 API

```python
def _cluster_candidate_tails_with_llm(
    self, 
    head_text: str, 
    relation: str, 
    descriptions: list, 
    max_batch_size: int = 30
) -> list:
    """
    使用 LLM 对候选 tail 进行聚类
    
    Args:
        head_text: head 实体描述
        relation: 关系名称
        descriptions: tail 描述列表
        max_batch_size: 单次 LLM 调用的最大 tail 数量
    
    Returns:
        聚类结果，每个元素是一个索引列表
    """
```

### 批次处理逻辑

- 如果 tail 数量 ≤ `llm_clustering_batch_size`：一次处理全部
- 如果 tail 数量 > `llm_clustering_batch_size`：分批处理
- 每批结果自动合并

### 错误处理

- LLM 调用失败：回退到单一 cluster（由后续步骤处理）
- JSON 解析失败：回退到单一 cluster
- 网络超时：回退到单一 cluster

## 性能影响

### LLM 调用次数增加

假设有 N 个 tail：

- **Embedding 方法总调用：** ~N/8 次（仅去重阶段）
- **LLM 方法总调用：** ~N/30 + N/8 次（聚类 + 去重）

**额外调用：** ~N/30 次

### 建议的使用场景

✅ **适合使用 LLM 聚类：**
- tail 数量 < 100
- Embedding 效果不佳
- 对准确性要求高
- 有充足的 API 配额

❌ **不建议使用 LLM 聚类：**
- tail 数量 > 100
- 预算有限
- 需要快速处理
- Embedding 效果已经很好

## 向后兼容性

✅ **完全向后兼容**

- 默认值为 `clustering_method: embedding`
- 现有配置无需修改即可正常工作
- 新功能为可选增强

## 测试

### 测试用例

1. **导演名称聚类**
   - 测试人名变体识别
   - 测试全名与缩写

2. **城市名称聚类**
   - 测试城市名变体
   - 测试昵称识别

### 运行测试

```bash
# 运行测试脚本
python test_llm_clustering.py

# 使用 LLM 聚类配置运行完整流程
python main.py --config config/example_with_llm_clustering.yaml --dataset demo
```

## 监控和调试

### 启用中间结果保存

```yaml
construction:
  semantic_dedup:
    save_intermediate_results: true
    intermediate_results_path: "output/dedup_intermediate/"
```

### 分析结果

```bash
python example_analyze_dedup_results.py output/dedup_intermediate/demo_edge_dedup_*.json
```

### 关键指标

- **聚类数量：** 应该合理反映语义分组
- **单项 clusters 比例：** <30% 为佳
- **LLM 调用次数：** 监控 API 使用量

## 已知限制

1. **批次处理限制：**
   - 单批最多建议 30-50 个 tail
   - 过多会影响 LLM 输出质量

2. **成本考虑：**
   - 大规模数据集会显著增加成本
   - 建议先小规模测试

3. **时间开销：**
   - 处理时间增加 ~30%
   - 取决于 LLM API 延迟

## 未来改进方向

1. **混合策略：**
   - 先用 embedding 快速筛选
   - 仅对疑难案例使用 LLM

2. **自适应选择：**
   - 根据 tail 数量自动选择方法
   - 根据 embedding 置信度决定是否使用 LLM

3. **Prompt 优化：**
   - 支持自定义 prompt
   - 针对不同 relation 类型的专用 prompt

4. **缓存机制：**
   - 缓存 LLM 聚类结果
   - 相似输入直接复用结果

## 贡献者

- 实现：Cursor Agent
- 设计：基于用户需求分析
- 测试：待完善

## 参考资料

- [DEDUP_INTERMEDIATE_RESULTS.md](./DEDUP_INTERMEDIATE_RESULTS.md) - 中间结果格式文档
- [CLUSTERING_DESCRIPTION_CHANGE.md](./CLUSTERING_DESCRIPTION_CHANGE.md) - 聚类描述改进
- [example_analyze_dedup_results.py](./example_analyze_dedup_results.py) - 结果分析脚本

## 更新日期

2025-10-20
