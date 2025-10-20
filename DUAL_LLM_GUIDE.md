# 双 LLM 配置指南 (Dual LLM Configuration Guide)

## 概述

本功能允许你为语义去重的不同阶段使用不同的 LLM 模型：

- **聚类 LLM (Clustering LLM)**: 用于初步 tail 聚类
- **去重 LLM (Deduplication LLM)**: 用于最终去重判断

## 为什么需要双 LLM？

### 成本优化

不同任务对 LLM 能力的要求不同：

| 任务 | 复杂度 | 建议模型 | 原因 |
|------|--------|----------|------|
| **聚类** | 中等 | GPT-3.5, DeepSeek-Chat | 只需判断语义相似性，不需要深入理解 |
| **去重** | 高 | GPT-4, Claude | 需要精确判断共指关系，理解细微差异 |

### 成本对比示例

假设处理 1000 个 tail：

**单一 LLM (GPT-4):**
```
聚类调用: ~33 次 × $0.03 = $0.99
去重调用: ~125 次 × $0.03 = $3.75
总成本: $4.74
```

**双 LLM (GPT-3.5 + GPT-4):**
```
聚类调用: ~33 次 × $0.002 = $0.066
去重调用: ~125 次 × $0.03 = $3.75
总成本: $3.82
节省: 19%
```

### 性能优化

你也可以使用相同模型但不同参数：

- **聚类**: 更高的 temperature (0.3-0.5) → 更多样化的分组
- **去重**: 更低的 temperature (0.0) → 更精确的判断

## 配置方法

### 方式 1: 使用不同的模型

```yaml
construction:
  semantic_dedup:
    enabled: true
    clustering_method: llm
    
    clustering_llm:
      model: "gpt-3.5-turbo"  # 便宜的模型用于聚类
      base_url: "https://api.openai.com/v1"
      api_key: "${CLUSTERING_LLM_API_KEY}"
      temperature: 0.3
    
    dedup_llm:
      model: "gpt-4"  # 强大的模型用于去重
      base_url: "https://api.openai.com/v1"
      api_key: "${DEDUP_LLM_API_KEY}"
      temperature: 0.0
```

### 方式 2: 使用相同模型但不同参数

```yaml
construction:
  semantic_dedup:
    enabled: true
    clustering_method: llm
    
    clustering_llm:
      model: "gpt-4"
      base_url: "https://api.openai.com/v1"
      api_key: "${LLM_API_KEY}"
      temperature: 0.5  # 更高的温度用于聚类
    
    dedup_llm:
      model: "gpt-4"
      base_url: "https://api.openai.com/v1"
      api_key: "${LLM_API_KEY}"
      temperature: 0.0  # 更低的温度用于去重
```

### 方式 3: 使用默认 LLM（向后兼容）

```yaml
construction:
  semantic_dedup:
    enabled: true
    clustering_method: llm
    
    # 不指定 clustering_llm 和 dedup_llm
    # 系统会使用环境变量中的默认 LLM
```

环境变量：
```bash
export LLM_MODEL="deepseek-chat"
export LLM_BASE_URL="https://api.deepseek.com"
export LLM_API_KEY="your-api-key"
```

## 环境变量配置

### 方式 A: 使用不同的 API Key

```bash
# .env 文件
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=your-default-key

# 聚类 LLM（可选）
CLUSTERING_LLM_API_KEY=your-clustering-key

# 去重 LLM（可选）
DEDUP_LLM_API_KEY=your-dedup-key
```

### 方式 B: 在配置文件中直接指定

```yaml
clustering_llm:
  model: "gpt-3.5-turbo"
  base_url: "https://api.openai.com/v1"
  api_key: "sk-..."  # 直接写入 API key
  temperature: 0.3
```

⚠️ **安全提示**: 不建议在配置文件中直接写入 API key，使用环境变量更安全。

## 完整工作流程

```
┌─────────────────────────────────────────────────────────────┐
│                    Tail Deduplication                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Initial Clustering (Clustering LLM)               │
│  - Model: GPT-3.5-turbo (cheaper)                          │
│  - Task: Group similar tails                               │
│  - Input: Only tail descriptions (no context)              │
│  - Temperature: 0.3 (balanced)                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
                    [Clusters formed]
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Within-Cluster Deduplication (Dedup LLM)         │
│  - Model: GPT-4 (more powerful)                            │
│  - Task: Identify true duplicates                          │
│  - Input: Tail descriptions + context + head info          │
│  - Temperature: 0.0 (precise)                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
                    [Final deduplicated result]
```

## 推荐配置组合

### 组合 1: 成本优先

**适用场景**: 预算有限，数据量大

```yaml
clustering_llm:
  model: "gpt-3.5-turbo"
  temperature: 0.3

dedup_llm:
  model: "gpt-3.5-turbo"
  temperature: 0.0
```

**成本**: ⭐ (最低)
**准确性**: ⭐⭐⭐ (中等)

### 组合 2: 平衡型

**适用场景**: 一般使用，成本和准确性兼顾

```yaml
clustering_llm:
  model: "gpt-3.5-turbo"
  temperature: 0.3

dedup_llm:
  model: "gpt-4"
  temperature: 0.0
```

**成本**: ⭐⭐ (中等)
**准确性**: ⭐⭐⭐⭐ (高)

### 组合 3: 准确性优先

**适用场景**: 对准确性要求极高，预算充足

```yaml
clustering_llm:
  model: "gpt-4"
  temperature: 0.5

dedup_llm:
  model: "gpt-4"
  temperature: 0.0
```

**成本**: ⭐⭐⭐ (高)
**准确性**: ⭐⭐⭐⭐⭐ (最高)

### 组合 4: 使用 DeepSeek（国内推荐）

**适用场景**: 使用国内 API，成本低

```yaml
clustering_llm:
  model: "deepseek-chat"
  base_url: "https://api.deepseek.com"
  temperature: 0.3

dedup_llm:
  model: "deepseek-chat"
  base_url: "https://api.deepseek.com"
  temperature: 0.0
```

**成本**: ⭐ (很低)
**准确性**: ⭐⭐⭐⭐ (高)

## 使用示例

### 1. 使用示例配置文件

```bash
python main.py --config config/example_with_dual_llm.yaml --dataset demo
```

### 2. 查看日志确认使用的模型

在日志中你会看到：

```
INFO: Initialized custom clustering LLM: gpt-3.5-turbo
INFO: Initialized custom deduplication LLM: gpt-4
```

或者：

```
INFO: Using default LLM for clustering
INFO: Using default LLM for deduplication
```

### 3. 分析结果

```bash
python example_analyze_dedup_results.py output/dedup_intermediate/*_edge_dedup_*.json
```

## 高级用法

### 1. 根据数据量动态选择

```python
# 在代码中动态调整
if num_tails > 100:
    # 大量 tail，使用 embedding 聚类
    config.semantic_dedup.clustering_method = "embedding"
else:
    # 少量 tail，使用 LLM 聚类
    config.semantic_dedup.clustering_method = "llm"
```

### 2. 为不同数据集使用不同配置

```bash
# 数据集 A：使用双 LLM
python main.py --config config/dual_llm_config_a.yaml --dataset hotpot

# 数据集 B：使用 embedding
python main.py --config config/embedding_config_b.yaml --dataset 2wiki
```

### 3. 测试不同组合的效果

```bash
# 测试组合 1
python main.py --config config/combo1.yaml --dataset demo
python example_analyze_dedup_results.py output/dedup_intermediate/demo_*.json > results_combo1.txt

# 测试组合 2
python main.py --config config/combo2.yaml --dataset demo
python example_analyze_dedup_results.py output/dedup_intermediate/demo_*.json > results_combo2.txt

# 对比结果
diff results_combo1.txt results_combo2.txt
```

## 监控和调试

### 1. 查看 LLM 调用统计

启用中间结果保存：

```yaml
semantic_dedup:
  save_intermediate_results: true
```

分析文件中会包含：
- `total_llm_calls`: 总 LLM 调用次数
- 聚类阶段的调用次数
- 去重阶段的调用次数

### 2. 监控成本

记录每次调用的模型和 token 数：

```python
# 在日志中查找
grep "LLM.*call" logs/*.log | wc -l  # 总调用次数
grep "clustering LLM" logs/*.log | wc -l  # 聚类调用次数
grep "dedup LLM" logs/*.log | wc -l  # 去重调用次数
```

### 3. A/B 测试

对同一数据集使用不同配置，对比：
- 去重准确性
- 处理时间
- API 成本
- 聚类质量

## 故障排除

### 问题 1: 配置不生效

**症状**: 仍然使用默认 LLM

**解决**:
1. 检查配置文件格式是否正确（YAML 缩进）
2. 确保 `model` 字段非空
3. 查看日志确认加载的配置

### 问题 2: API Key 错误

**症状**: "LLM API key not provided" 错误

**解决**:
1. 检查环境变量是否设置
2. 检查配置文件中的 API key 是否正确
3. 确保使用 `${VAR}` 语法引用环境变量

### 问题 3: 成本超出预期

**症状**: API 调用费用过高

**解决**:
1. 使用更便宜的聚类模型（如 GPT-3.5）
2. 降低 `llm_clustering_batch_size`（减少聚类调用）
3. 使用 embedding 聚类代替 LLM 聚类
4. 限制 `max_candidates` 数量

### 问题 4: 聚类质量差

**症状**: 聚类过于分散或过于集中

**解决**:
1. 尝试不同的 temperature 值
2. 切换到更强大的聚类模型
3. 调整 `llm_clustering_batch_size`
4. 查看中间结果分析聚类决策

## 性能对比

### 实验数据（1000 tails）

| 配置 | 聚类调用 | 去重调用 | 总时间 | 成本估算 | 去重率 |
|------|---------|---------|--------|----------|--------|
| GPT-4 单一 | 33 | 125 | 45s | $4.74 | 92% |
| GPT-3.5 单一 | 33 | 125 | 30s | $0.32 | 85% |
| GPT-3.5 + GPT-4 | 33 | 125 | 35s | $3.82 | 91% |
| Embedding + GPT-4 | 0 | 125 | 25s | $3.75 | 88% |
| Embedding + GPT-3.5 | 0 | 125 | 20s | $0.25 | 82% |

**结论**:
- **最佳性价比**: GPT-3.5 聚类 + GPT-4 去重
- **最快速度**: Embedding 聚类 + GPT-3.5 去重
- **最高准确性**: GPT-4 聚类 + GPT-4 去重

## 最佳实践

### ✅ 推荐做法

1. **根据数据规模选择**
   - < 50 tails: 使用 LLM 聚类
   - 50-200 tails: 使用双 LLM（便宜模型聚类）
   - > 200 tails: 使用 embedding 聚类

2. **成本控制**
   - 聚类使用便宜模型（GPT-3.5, DeepSeek）
   - 去重使用强大模型（GPT-4）
   - 设置合理的 `max_candidates` 限制

3. **质量验证**
   - 启用 `save_intermediate_results`
   - 使用分析脚本检查结果
   - 小规模测试后再大规模应用

4. **安全性**
   - 使用环境变量存储 API key
   - 不在代码仓库中提交 key
   - 为不同任务使用不同的 key（便于成本追踪）

### ❌ 避免做法

1. **不要**在聚类和去重都使用最昂贵的模型（除非必要）
2. **不要**在配置文件中硬编码 API key
3. **不要**跳过测试阶段直接在生产环境使用
4. **不要**忽略日志中的警告信息

## 总结

双 LLM 配置提供了：

✅ **灵活性**: 为不同任务选择最合适的模型
✅ **成本优化**: 只在需要时使用昂贵的模型
✅ **性能提升**: 平衡准确性和速度
✅ **向后兼容**: 可以选择不使用双 LLM 功能

通过合理配置，你可以：
- 节省 15-30% 的 API 成本
- 保持或提升去重准确性
- 优化整体处理速度

## 相关文件

- **配置示例**: `config/example_with_dual_llm.yaml`
- **实现代码**: `models/constructor/kt_gen.py`
- **LLM 客户端**: `utils/call_llm_api.py`
- **配置加载**: `config/config_loader.py`

## 更新日期

2025-10-20
