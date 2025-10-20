# LLM-based Clustering for Tail Deduplication

## 概述

当共享相同 head 和 relation 的 tail 数量过多时，传统的 embedding 相似度聚类可能不够准确。本功能提供了使用 LLM 进行初步 tail 聚类的选项，可以更准确地理解语义相似性。

## 两种聚类方法对比

### 1. Embedding-based Clustering（默认）

**工作原理：**
- 使用 Sentence Transformer 将 tail 描述转换为向量
- 使用层次聚类（Average Linkage）根据余弦相似度分组
- 快速但可能对复杂语义理解不够准确

**优点：**
- ⚡ 速度快
- 💰 成本低（不需要额外 LLM 调用）
- 🔄 可扩展性好

**缺点：**
- ❌ 对复杂语义理解有限
- ❌ 可能产生不准确的聚类
- ❌ 依赖于 embedding 模型的质量

**适用场景：**
- tail 数量非常大（>100）
- 语义较为简单和直接
- 预算有限或需要快速处理

### 2. LLM-based Clustering（新功能）

**工作原理：**
- 将 tail 描述发送给 LLM
- LLM 根据语义相似性进行分组
- 只使用 tail 描述，不包含 context 信息
- 后续步骤仍使用 LLM 进行最终去重判断

**优点：**
- ✅ 准确理解复杂语义
- ✅ 能够识别上下位关系、同义关系等
- ✅ 聚类质量更高

**缺点：**
- 🐌 速度较慢（需要额外 LLM 调用）
- 💸 成本较高
- ⚠️ 大量 tail 时需要分批处理

**适用场景：**
- tail 数量适中（<100）
- 语义复杂，embedding 效果不佳
- 对准确性要求高
- 有足够的 LLM API 配额

## 配置方法

### 在配置文件中启用 LLM 聚类

```yaml
construction:
  semantic_dedup:
    enabled: true
    
    # 设置聚类方法为 "llm"
    clustering_method: llm
    
    # LLM 聚类批次大小（一次发送给 LLM 的最大 tail 数量）
    llm_clustering_batch_size: 30
    
    # 其他参数保持不变
    max_batch_size: 8
    max_candidates: 50
```

### 使用 embedding 聚类（默认）

```yaml
construction:
  semantic_dedup:
    enabled: true
    
    # 设置聚类方法为 "embedding" 或不设置（默认）
    clustering_method: embedding
    
    # Embedding 聚类阈值
    embedding_threshold: 0.85
```

## 工作流程

### Embedding 聚类流程

```
Tails (head, relation) 
  ↓
[1] Embedding + 层次聚类
  ↓
初步 Clusters
  ↓
[2] 对每个 Cluster 使用 LLM 进行去重
  ↓
最终去重结果
```

### LLM 聚类流程

```
Tails (head, relation)
  ↓
[1] LLM 语义聚类（只基于 tail 描述）
  ↓
初步 Clusters（质量更高）
  ↓
[2] 对每个 Cluster 使用 LLM 进行去重（带 context）
  ↓
最终去重结果
```

## LLM 聚类的 Prompt 设计

LLM 聚类使用专门设计的 prompt，强调：

1. **初步分组目标**：将可能指向同一实体的 tail 分到一组
2. **包容性原则**：宁可过度聚类，不要遗漏潜在的重复
3. **语义相似性**：基于语义而非字符串匹配
4. **清晰分离**：明显不同的实体保持分离

示例聚类决策：
- ✅ 聚在一起：['New York', 'NYC', 'New York City'] - 潜在共指
- ✅ 聚在一起：['United States', 'USA', 'US', 'America'] - 潜在共指
- ❌ 分开：['Paris', 'London', 'Berlin'] - 明显不同的城市
- ❌ 分开：['red', 'large', 'heavy'] - 不同的属性类型

## 性能考虑

### LLM 调用次数

假设有 N 个 tail 需要聚类：

**Embedding 方法：**
- 聚类阶段：0 次 LLM 调用
- 去重阶段：~N/8 次 LLM 调用（按 max_batch_size=8 计算）

**LLM 方法：**
- 聚类阶段：~N/30 次 LLM 调用（按 llm_clustering_batch_size=30 计算）
- 去重阶段：~N/8 次 LLM 调用

**总额外成本：** LLM 方法增加约 N/30 次调用

### 建议

1. **默认使用 embedding 聚类**，只在以下情况使用 LLM 聚类：
   - Embedding 聚类效果不理想
   - 数据集较小（<1000 个 tail）
   - 对准确性要求极高

2. **监控聚类质量**：
   - 使用 `save_intermediate_results: true` 保存中间结果
   - 使用 `example_analyze_dedup_results.py` 分析聚类效果
   - 关注 `single_item_clusters` 比例（过高说明聚类过于保守）

3. **调整参数**：
   - `llm_clustering_batch_size`：增大可减少 LLM 调用次数，但单次处理更多 tail
   - `max_candidates`：限制每个 (head, relation) 对的最大 tail 数量

## 示例

### 场景：电影关系去重

假设有以下 tail 需要去重（head="Star Wars", relation="director"）：

```
1. George Lucas
2. G. Lucas
3. George Walton Lucas Jr.
4. J.J. Abrams
5. Jeffrey Jacob Abrams
6. Rian Johnson
```

**Embedding 聚类可能的结果：**
```
Cluster 1: [1, 2, 3]  ✅ 正确
Cluster 2: [4, 5]     ✅ 正确
Cluster 3: [6]        ✅ 正确
```

**LLM 聚类的结果（更准确）：**
```
Cluster 1: [1, 2, 3]  ✅ 识别为同一人的不同写法
  Rationale: "Different name variations of George Lucas"
  
Cluster 2: [4, 5]     ✅ 识别为同一人的全名和昵称
  Rationale: "J.J. Abrams and his full name Jeffrey Jacob Abrams"
  
Cluster 3: [6]        ✅ 单独的导演
  Rationale: "Distinct director, no variations in the list"
```

## 调试和分析

启用中间结果保存：

```yaml
construction:
  semantic_dedup:
    save_intermediate_results: true
    intermediate_results_path: "output/dedup_intermediate/"
```

查看聚类结果：

```bash
python example_analyze_dedup_results.py output/dedup_intermediate/demo_edge_dedup_20251020_120000.json
```

关注聚类指标：
- **总 clusters 数量**：应该合理反映实际的语义分组
- **单项 clusters 比例**：过高（>70%）说明聚类过于保守
- **多项 clusters 比例**：应该包含真正相似的 tail
- **LLM 调用浪费率**：后续去重阶段没有产生合并的 LLM 调用比例

## 最佳实践

1. **先试 embedding，再用 LLM**
   - 从 embedding 聚类开始
   - 分析结果，识别问题
   - 如有必要切换到 LLM 聚类

2. **混合使用**
   - 对简单数据集使用 embedding
   - 对复杂数据集使用 LLM
   - 可以为不同数据集配置不同的 config 文件

3. **成本优化**
   - 使用 `max_candidates` 限制处理的 tail 数量
   - 调大 `llm_clustering_batch_size` 减少调用次数
   - 监控 API 使用量

4. **质量验证**
   - 保存中间结果
   - 抽样检查聚类质量
   - 根据结果调整配置

## 技术细节

### LLM 聚类 Prompt

```python
DEFAULT_LLM_CLUSTERING_PROMPT = (
    "You are a knowledge graph curation assistant performing initial clustering of tail entities.\n"
    "All listed tail entities share the same head entity and relation.\n\n"
    "Head entity: {head}\n"
    "Relation: {relation}\n\n"
    "Candidate tails:\n"
    "{candidates}\n\n"
    "TASK: Group these tails into PRELIMINARY CLUSTERS based on semantic similarity.\n"
    ...
)
```

### 输出格式

```json
{
  "clusters": [
    {
      "members": [1, 3, 5],
      "description": "Brief explanation of why these tails are clustered together"
    },
    {
      "members": [2],
      "description": "This tail is semantically distinct from others"
    }
  ]
}
```

## 相关文件

- **实现代码**: `models/constructor/kt_gen.py`
  - `_cluster_candidate_tails_with_llm()`: LLM 聚类方法
  - `_llm_cluster_batch()`: 批次处理
  - `_semantic_deduplicate_group()`: 使用聚类结果

- **配置文件**: `config/base_config.yaml`
  - `semantic_dedup.clustering_method`
  - `semantic_dedup.llm_clustering_batch_size`

- **示例配置**: `config/example_with_llm_clustering.yaml`

## 常见问题

**Q: 什么时候应该使用 LLM 聚类？**
A: 当 embedding 聚类效果不佳，且数据量不太大（<100 tails per (head, relation)）时。

**Q: LLM 聚类会增加多少成本？**
A: 约增加 N/30 次 LLM 调用（N 为 tail 数量），具体取决于 `llm_clustering_batch_size`。

**Q: 可以只对部分数据使用 LLM 聚类吗？**
A: 可以，为不同数据集创建不同的配置文件，或在代码中动态调整配置。

**Q: LLM 聚类失败会怎样？**
A: 会自动回退到将所有 tail 放在一个 cluster 中，然后由后续的 LLM 去重步骤处理。

**Q: 可以自定义聚类 prompt 吗？**
A: 目前使用默认 prompt，未来版本可能支持通过配置文件自定义。

## 总结

LLM 聚类为 tail 去重提供了更准确的初步分组方法，特别适合：
- 语义复杂的场景
- 对准确性要求高的场景
- tail 数量适中的场景

通过配置 `clustering_method: llm`，你可以轻松启用这个功能，并通过中间结果分析验证改进效果。
