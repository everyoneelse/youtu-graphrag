# 去重中间结果保存功能

## 功能说明

该功能用于保存语义去重过程中的所有中间结果，支持两种类型的去重：

### 1. 关键词节点去重 (Keyword Node Deduplication)
处理 `keyword_of` 关系的候选节点去重，保存：
- **聚类结果**：基于 Average Linkage 层次聚类的分组
- **LLM 分组结果**：每个 cluster 经过 LLM 处理后的 semantic groups
- **最终合并操作**：实际执行的节点合并记录

### 2. 三元组边去重 (Edge/Triple Deduplication)
处理普通三元组（head, relation, tail）的语义去重，保存：
- **聚类结果**：对相同 (head, relation) 的所有 tails 进行聚类
- **LLM 分组结果**：每个 cluster 的语义分组
- **最终合并操作**：重复边的合并记录

## 配置方法

在 `config/base_config.yaml` 中配置：

```yaml
construction:
  semantic_dedup:
    enabled: true
    embedding_threshold: 0.85
    max_batch_size: 8
    max_candidates: 50
    use_embeddings: true
    prompt_type: general
    
    # 启用中间结果保存
    save_intermediate_results: true
    
    # 可选：指定保存路径（不指定则自动生成）
    intermediate_results_path: "output/dedup_intermediate/"
```

## 输出文件格式

会生成两个独立的输出文件：

1. **关键词节点去重结果**：`{dataset_name}_dedup_{timestamp}.json`
   - 在 `_deduplicate_keyword_nodes` 函数结束时保存
   - 记录所有 community 的关键词去重过程

2. **边去重结果**：`{dataset_name}_edge_dedup_{timestamp}.json`
   - 在 `triple_deduplicate_semantic` 函数结束时保存
   - 记录所有 (head, relation) 对的边去重过程

### 文件结构

#### 关键词节点去重结果 (`*_dedup_*.json`)

```json
{
  "dataset": "hotpot",
  "dedup_type": "keyword_node_deduplication",  // 可选字段
  "config": {
    "threshold": 0.85,
    "max_batch_size": 8,
    "max_candidates": 50
  },
  "communities": [
    {
      "community_id": "entity_123",
      "community_name": "Machine Learning",
      "relation": "keyword_of",
      "total_candidates": 15,
      "head_contexts": ["context line 1", "context line 2"],
      
      "candidates": [
        {
          "index": 0,
          "node_id": "keyword_001",
          "description": "deep learning",
          "raw_name": "deep learning",
          "source_entity_id": "entity_456",
          "source_entity_name": "Neural Networks"
        }
      ],
      
      "clustering": {
        "method": "average_linkage",
        "threshold": 0.85,
        "clusters": [
          {
            "cluster_id": 0,
            "size": 3,
            "member_indices": [0, 1, 2],
            "members": [
              {
                "index": 0,
                "node_id": "keyword_001",
                "description": "deep learning"
              },
              {
                "index": 1,
                "node_id": "keyword_002",
                "description": "deep neural networks"
              },
              {
                "index": 2,
                "node_id": "keyword_003",
                "description": "DNN"
              }
            ]
          }
        ]
      },
      
      "llm_groups": [
        {
          "cluster_id": 0,
          "batch_indices": [0, 1, 2],
          "batch_size": 3,
          "groups": [
            {
              "members": [0, 1, 2],
              "representative": 0,
              "rationale": "All three refer to the same concept of deep neural networks",
              "member_details": [
                {
                  "local_idx": 0,
                  "global_idx": 0,
                  "description": "deep learning"
                }
              ]
            }
          ]
        }
      ],
      
      "final_merges": [
        {
          "representative": {
            "index": 0,
            "node_id": "keyword_001",
            "description": "deep learning"
          },
          "duplicates": [
            {
              "index": 1,
              "node_id": "keyword_002",
              "description": "deep neural networks"
            },
            {
              "index": 2,
              "node_id": "keyword_003",
              "description": "DNN"
            }
          ],
          "rationale": "All three refer to the same concept of deep neural networks"
        }
      ],
      
      "summary": {
        "total_candidates": 15,
        "total_clusters": 5,
        "single_item_clusters": 3,
        "multi_item_clusters": 2,
        "total_llm_calls": 2,
        "total_merges": 1,
        "items_merged": 2
      }
    }
  ],
  
  "summary": {
    "total_communities": 10,
    "total_candidates": 150,
    "total_clusters": 50,
    "total_llm_calls": 20,
    "total_merges": 15,
    "total_items_merged": 45
  }
}
```

#### 边去重结果 (`*_edge_dedup_*.json`)

```json
{
  "dataset": "hotpot",
  "dedup_type": "edge_deduplication",
  "config": {
    "threshold": 0.85,
    "max_batch_size": 8,
    "max_candidates": 50
  },
  "triples": [
    {
      "head_id": "entity_123",
      "head_name": "Machine Learning",
      "relation": "related_to",
      "total_edges": 5,
      "head_contexts": ["context..."],
      "candidates": [
        {
          "index": 0,
          "node_id": "entity_456",
          "description": "deep learning"
        }
      ],
      "clustering": {
        "method": "average_linkage",
        "threshold": 0.85,
        "clusters": [...]
      },
      "llm_groups": [...],
      "final_merges": [...],
      "summary": {
        "total_edges": 5,
        "total_clusters": 3,
        "single_item_clusters": 2,
        "multi_item_clusters": 1,
        "total_llm_calls": 1,
        "total_merges": 1,
        "edges_merged": 2,
        "final_edges": 3
      }
    }
  ],
  "summary": {
    "total_triples": 50,
    "total_edges": 250,
    "total_clusters": 150,
    "total_llm_calls": 30,
    "total_merges": 20,
    "total_edges_merged": 60,
    "final_total_edges": 190
  }
}
```

## 数据字段说明

### 关键词节点去重 - 顶层字段

| 字段 | 说明 |
|------|------|
| `dataset` | 数据集名称 |
| `config` | 去重配置参数 |
| `communities` | 每个 community 的处理结果 |
| `summary` | 全局统计摘要 |

### Community 字段

| 字段 | 说明 |
|------|------|
| `community_id` | Community 节点 ID |
| `community_name` | Community 节点描述 |
| `relation` | 关系类型（通常是 "keyword_of"） |
| `total_candidates` | 候选项总数 |
| `head_contexts` | Head entity 的上下文摘要 |
| `candidates` | 所有候选项的详细信息 |
| `clustering` | 聚类结果 |
| `llm_groups` | LLM 分组结果 |
| `final_merges` | 最终执行的合并操作 |
| `summary` | 该 community 的统计摘要 |

### Clustering 字段

| 字段 | 说明 |
|------|------|
| `method` | 聚类方法（average_linkage） |
| `threshold` | 相似度阈值 |
| `clusters` | 所有 cluster 的详细信息 |

### LLM Groups 字段

| 字段 | 说明 |
|------|------|
| `cluster_id` | 对应的 cluster ID |
| `batch_indices` | 当前批次的全局索引 |
| `batch_size` | 批次大小 |
| `groups` | LLM 返回的分组结果 |

### Final Merges 字段

| 字段 | 说明 |
|------|------|
| `representative` | 保留的代表节点 |
| `duplicates` | 被合并的重复节点 |
| `rationale` | 合并理由（来自 LLM） |

### 边去重 - 顶层字段

| 字段 | 说明 |
|------|------|
| `dataset` | 数据集名称 |
| `dedup_type` | 去重类型（"edge_deduplication"） |
| `config` | 去重配置参数 |
| `triples` | 每个 (head, relation) 对的处理结果 |
| `summary` | 全局统计摘要 |

### Triple 字段

| 字段 | 说明 |
|------|------|
| `head_id` | Head 实体 ID |
| `head_name` | Head 实体描述 |
| `relation` | 关系类型 |
| `total_edges` | 该三元组的 edge 总数 |
| `candidates` | 所有 tail 候选项 |
| `clustering` | 聚类结果 |
| `llm_groups` | LLM 分组结果 |
| `final_merges` | 最终执行的合并操作 |
| `summary` | 该三元组的统计摘要 |

## 使用场景

### 1. 调试和优化

分析中间结果可以帮助：
- 检查聚类算法是否正确分组
- 验证 LLM 的分组决策是否合理
- 发现需要调整的阈值参数

### 2. 质量评估

通过中间结果可以：
- 统计去重的召回率和精确率
- 分析误判案例
- 评估不同参数的效果

### 3. 数据分析

可以用于：
- 分析候选项的分布特征
- 研究语义相似度模式
- 生成去重报告

## 示例：分析聚类效果

### 分析关键词节点去重

```python
import json

# 读取关键词节点去重结果
with open('output/dedup_intermediate/hotpot_dedup_20251019_120000.json', 'r') as f:
    results = json.load(f)

# 统计分析
print(f"总共处理了 {results['summary']['total_communities']} 个 communities")
print(f"总候选项数: {results['summary']['total_candidates']}")
print(f"聚类后 clusters 数: {results['summary']['total_clusters']}")
print(f"LLM 调用次数: {results['summary']['total_llm_calls']}")
print(f"最终合并数: {results['summary']['total_merges']}")
print(f"去重项数: {results['summary']['total_items_merged']}")

# 分析单个 community
for comm in results['communities']:
    print(f"\nCommunity: {comm['community_name']}")
    print(f"  候选项: {comm['total_candidates']}")
    print(f"  聚类成: {len(comm['clustering']['clusters'])} 个 clusters")
    print(f"  最终合并: {len(comm['final_merges'])} 次")
    
    # 查看具体的合并操作
    for merge in comm['final_merges']:
        print(f"    保留: {merge['representative']['description']}")
        print(f"    合并: {[d['description'] for d in merge['duplicates']]}")
        print(f"    理由: {merge['rationale']}")
```

### 分析边去重

```python
import json

# 读取边去重结果
with open('output/dedup_intermediate/hotpot_edge_dedup_20251019_120000.json', 'r') as f:
    edge_results = json.load(f)

# 统计分析
print(f"总共处理了 {edge_results['summary']['total_triples']} 个三元组")
print(f"总 edges: {edge_results['summary']['total_edges']}")
print(f"聚类后 clusters: {edge_results['summary']['total_clusters']}")
print(f"LLM 调用次数: {edge_results['summary']['total_llm_calls']}")
print(f"最终合并数: {edge_results['summary']['total_merges']}")
print(f"去重 edges 数: {edge_results['summary']['total_edges_merged']}")
print(f"最终保留 edges: {edge_results['summary']['final_total_edges']}")

# 去重率
dedup_rate = edge_results['summary']['total_edges_merged'] / edge_results['summary']['total_edges'] * 100
print(f"边去重率: {dedup_rate:.2f}%")

# 查看具体的三元组去重
for triple in edge_results['triples'][:5]:
    print(f"\nTriple: ({triple['head_name']}, {triple['relation']}, ...)")
    print(f"  原始edges: {triple['total_edges']}")
    print(f"  最终edges: {triple['summary']['final_edges']}")
    print(f"  去重: {triple['summary']['edges_merged']} 个")
```

## 优化建议

根据中间结果可以进行以下优化：

### 1. 调整阈值

如果发现：
- **过多的单项 clusters**：降低 `embedding_threshold`
- **不该聚在一起的被聚类**：提高 `embedding_threshold`

### 2. 优化 LLM prompt

如果 LLM 分组结果不理想：
- 检查 `llm_groups` 中的 `rationale`
- 根据问题调整 prompt 模板

### 3. 调整批次大小

如果处理效率不高：
- 增加 `max_batch_size` 减少 LLM 调用次数
- 但要注意 LLM 的 context length 限制

## 性能影响

启用中间结果保存会：
- ✅ 增加少量内存占用（收集结果）
- ✅ 增加少量 I/O 开销（写入文件）
- ⚠️ 不影响去重逻辑和准确性
- ⚠️ 建议仅在需要分析时启用

## 注意事项

1. **文件大小**：大规模数据集可能产生较大的 JSON 文件
2. **敏感信息**：中间结果包含原始文本，注意数据隐私
3. **存储空间**：定期清理旧的中间结果文件
4. **性能**：生产环境建议关闭此功能

## 日志输出

启用后，日志中会看到：

```
INFO: Saved deduplication intermediate results to: output/dedup_intermediate/hotpot_dedup_20251019_120000.json
INFO: Summary: {'total_communities': 10, 'total_candidates': 150, ...}

INFO: Saved edge deduplication intermediate results to: output/dedup_intermediate/hotpot_edge_dedup_20251019_120000.json
INFO: Summary: {'total_triples': 50, 'total_edges': 250, ...}
```

## 输出文件结构

运行后会在指定目录（默认 `output/dedup_intermediate/`）生成两种类型的文件：

```
output/
└── dedup_intermediate/
    ├── hotpot_dedup_20251019_120000.json           # 关键词节点去重结果
    ├── hotpot_edge_dedup_20251019_120000.json      # 三元组边去重结果
    ├── hotpot_dedup_20251019_140000.json           # 第二次运行的关键词去重
    ├── hotpot_edge_dedup_20251019_140000.json      # 第二次运行的边去重
    └── ...
```

两种文件的区别：
- **`*_dedup_*.json`**: 关键词节点去重，记录 community 中候选关键词的聚类和合并
- **`*_edge_dedup_*.json`**: 三元组边去重，记录 (head, relation) 对的 tail 去重

## 完整工作流程

1. **配置启用**：在 `config/base_config.yaml` 中设置 `save_intermediate_results: true`
2. **运行构建**：正常运行知识图谱构建流程
3. **自动保存**：系统在去重阶段自动保存两个中间结果文件
4. **分析结果**：使用 `example_analyze_dedup_results.py` 或自定义脚本分析结果
5. **优化调整**：根据分析结果调整 threshold、batch_size 等参数
6. **迭代改进**：重新运行并对比不同参数的效果
