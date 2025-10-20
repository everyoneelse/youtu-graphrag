# LLM 聚类中间结果保存格式

## 概述

当使用 `clustering_method: llm` 时，中间结果现在包含 LLM 给出的聚类理由和描述，方便分析和调试。

## 新增字段

### 在聚类信息中

每个 cluster 现在包含：

```json
{
  "clustering": {
    "method": "llm",  // 新增：聚类方法 ("llm" 或 "embedding")
    "threshold": 0.85,
    "clusters": [
      {
        "cluster_id": 0,
        "size": 3,
        "member_indices": [0, 1, 2],
        "members": [...],
        
        // ===== 新增字段 =====
        "llm_description": "Different name variations of New York City",
        "llm_rationale": "These are all referring to the same city - New York City. NYC is the common abbreviation, and 'New York' can refer to either the city or state but in this context refers to the city."
      }
    ]
  }
}
```

## 完整示例

### Edge Deduplication 结果

```json
{
  "dataset": "demo",
  "dedup_type": "edge_deduplication",
  "config": {
    "threshold": 0.85,
    "max_batch_size": 8,
    "max_candidates": 50
  },
  "triples": [
    {
      "head_id": "entity_123",
      "head_name": "United States",
      "relation": "has_city",
      "total_edges": 10,
      "candidates": [
        {
          "index": 0,
          "node_id": "entity_456",
          "description": "New York City"
        },
        {
          "index": 1,
          "node_id": "entity_457",
          "description": "NYC"
        },
        {
          "index": 2,
          "node_id": "entity_458",
          "description": "New York"
        }
      ],
      "clustering": {
        "method": "llm",  // 👈 新增：表示使用 LLM 聚类
        "threshold": 0.85,
        "clusters": [
          {
            "cluster_id": 0,
            "size": 3,
            "member_indices": [0, 1, 2],
            "members": [
              {
                "index": 0,
                "node_id": "entity_456",
                "description": "New York City"
              },
              {
                "index": 1,
                "node_id": "entity_457",
                "description": "NYC"
              },
              {
                "index": 2,
                "node_id": "entity_458",
                "description": "New York"
              }
            ],
            // 👇 新增：LLM 的聚类描述
            "llm_description": "Different name variations of New York City",
            // 👇 新增：LLM 的详细理由
            "llm_rationale": "These three expressions all refer to the same city. NYC is the common abbreviation for New York City. 'New York' in this context (with relation 'has_city') clearly refers to the city rather than the state."
          },
          {
            "cluster_id": 1,
            "size": 2,
            "member_indices": [3, 4],
            "members": [...],
            "llm_description": "Los Angeles and its abbreviation",
            "llm_rationale": "LA is the common abbreviation for Los Angeles."
          }
        ]
      },
      "llm_groups": [...],
      "final_merges": [...]
    }
  ]
}
```

### Keyword Node Deduplication 结果

```json
{
  "dataset": "demo",
  "dedup_type": "keyword_node_deduplication",
  "communities": [
    {
      "community_id": "comm_789",
      "community_name": "Cities in the United States",
      "relation": "keyword_of",
      "total_candidates": 8,
      "clustering": {
        "method": "llm",  // 👈 表示使用 LLM 聚类
        "threshold": 0.85,
        "clusters": [
          {
            "cluster_id": 0,
            "size": 3,
            "member_indices": [0, 1, 2],
            "members": [...],
            // 👇 LLM 聚类的描述和理由
            "llm_description": "Keywords referring to New York City",
            "llm_rationale": "All three keywords (NYC, New York City, New York) refer to the same city entity."
          }
        ]
      }
    }
  ]
}
```

## 字段说明

### clustering.method

- **类型**: string
- **可能值**: "llm" | "embedding" | "average_linkage"
- **说明**: 使用的聚类方法
  - `"llm"`: 使用 LLM 进行语义聚类
  - `"embedding"`: 使用 embedding 相似度聚类
  - `"average_linkage"`: 历史版本，等同于 embedding

### llm_description

- **类型**: string
- **说明**: LLM 对这个聚类的简短描述
- **示例**: 
  - "Different name variations of New York City"
  - "Los Angeles and its abbreviation"
  - "Clearly distinct cities with no semantic overlap"

### llm_rationale

- **类型**: string
- **说明**: LLM 给出的详细聚类理由
- **用途**: 
  - 帮助理解 LLM 的聚类决策
  - 调试聚类质量
  - 验证聚类是否合理

## 使用场景

### 1. 分析聚类质量

```python
import json

with open('output/dedup_intermediate/demo_edge_dedup_*.json', 'r') as f:
    data = json.load(f)

for triple in data['triples']:
    clustering = triple['clustering']
    
    if clustering['method'] == 'llm':
        print(f"\n=== {triple['head_name']} - {triple['relation']} ===")
        print(f"Clustering method: LLM")
        
        for cluster in clustering['clusters']:
            print(f"\nCluster {cluster['cluster_id']} ({cluster['size']} members):")
            print(f"  Description: {cluster.get('llm_description', 'N/A')}")
            print(f"  Rationale: {cluster.get('llm_rationale', 'N/A')}")
            
            # 检查聚类是否合理
            if cluster['size'] > 5:
                print(f"  ⚠️  Large cluster, may need review")
```

### 2. 对比 LLM vs Embedding 聚类

```python
def compare_clustering_methods(file1, file2):
    """对比两种聚类方法的效果"""
    
    with open(file1) as f:
        data1 = json.load(f)
    with open(file2) as f:
        data2 = json.load(f)
    
    for t1, t2 in zip(data1['triples'], data2['triples']):
        c1 = t1['clustering']
        c2 = t2['clustering']
        
        print(f"\n=== {t1['head_name']} ===")
        print(f"Method 1 ({c1['method']}): {len(c1['clusters'])} clusters")
        print(f"Method 2 ({c2['method']}): {len(c2['clusters'])} clusters")
        
        if c1['method'] == 'llm':
            print("\nLLM Clustering Rationales:")
            for cluster in c1['clusters']:
                if cluster['size'] > 1:
                    print(f"  - {cluster.get('llm_description', 'N/A')}")
```

### 3. 提取聚类统计

```python
def analyze_llm_clustering(filepath):
    """分析 LLM 聚类结果"""
    
    with open(filepath) as f:
        data = json.load(f)
    
    llm_clusters = 0
    total_clusters = 0
    avg_cluster_size = []
    
    for triple in data.get('triples', []):
        clustering = triple['clustering']
        
        if clustering['method'] == 'llm':
            llm_clusters += len(clustering['clusters'])
            
            for cluster in clustering['clusters']:
                total_clusters += 1
                avg_cluster_size.append(cluster['size'])
    
    if avg_cluster_size:
        print(f"LLM Clustering Statistics:")
        print(f"  Total clusters: {total_clusters}")
        print(f"  Average cluster size: {sum(avg_cluster_size) / len(avg_cluster_size):.2f}")
        print(f"  Max cluster size: {max(avg_cluster_size)}")
        print(f"  Singleton clusters: {sum(1 for s in avg_cluster_size if s == 1)}")
```

## 向后兼容性

### Embedding 聚类结果

使用 embedding 聚类时，不会有 `llm_description` 和 `llm_rationale` 字段：

```json
{
  "clustering": {
    "method": "embedding",
    "threshold": 0.85,
    "clusters": [
      {
        "cluster_id": 0,
        "size": 3,
        "member_indices": [0, 1, 2],
        "members": [...]
        // 没有 llm_description 和 llm_rationale
      }
    ]
  }
}
```

### 检查代码

在分析代码中安全访问新字段：

```python
# 安全访问
llm_desc = cluster.get('llm_description', '')
llm_rationale = cluster.get('llm_rationale', '')

# 检查是否使用 LLM 聚类
if clustering.get('method') == 'llm':
    # 使用了 LLM 聚类
    print(f"LLM Description: {cluster.get('llm_description', 'N/A')}")
else:
    # 使用了 embedding 聚类
    print("No LLM rationale available (used embedding clustering)")
```

## 调试建议

### 1. 检查聚类质量

查看 LLM 的聚类理由，验证是否合理：

```bash
# 提取所有 LLM 聚类的描述
jq '.triples[].clustering.clusters[] | select(.llm_description != null) | {desc: .llm_description, size: .size}' output.json
```

### 2. 识别问题聚类

找出可能有问题的聚类（如过大或理由不充分）：

```python
def find_problematic_clusters(filepath, max_size=10):
    with open(filepath) as f:
        data = json.load(f)
    
    problems = []
    
    for triple in data.get('triples', []):
        for cluster in triple['clustering']['clusters']:
            # 检查过大的聚类
            if cluster['size'] > max_size:
                problems.append({
                    'type': 'large_cluster',
                    'size': cluster['size'],
                    'description': cluster.get('llm_description', 'N/A'),
                    'members': cluster['members']
                })
            
            # 检查缺少理由的聚类
            if cluster['size'] > 1 and not cluster.get('llm_rationale'):
                problems.append({
                    'type': 'missing_rationale',
                    'size': cluster['size'],
                    'members': cluster['members']
                })
    
    return problems
```

## 性能影响

### 存储空间

- **LLM 聚类**: 每个 cluster 增加约 50-200 字节（取决于描述长度）
- **Embedding 聚类**: 无额外开销

### 建议

如果不需要分析聚类详情，可以：

1. 不启用 `save_intermediate_results`
2. 或者在分析后删除中间结果文件

## 总结

新增的 LLM 聚类详情字段提供了：

✅ **透明性**: 可以看到 LLM 的聚类理由
✅ **可调试性**: 更容易发现聚类问题
✅ **可分析性**: 可以对比不同聚类方法的效果
✅ **向后兼容**: 不影响现有的 embedding 聚类

## 相关文件

- `models/constructor/kt_gen.py` - 实现代码
- `DEDUP_INTERMEDIATE_RESULTS.md` - 原有中间结果格式文档
- `LLM_CLUSTERING_README.md` - LLM 聚类功能文档

## 更新日期

2025-10-20
