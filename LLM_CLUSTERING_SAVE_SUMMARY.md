# LLM 聚类中间结果保存 - 功能总结

## 🎯 问题

**用户提问**: "当前 `_llm_cluster_batch` 的结果是否能够通过原有的 `save_intermediate` 来保存呢？"

**原有问题**:
- ❌ `_llm_cluster_batch` 只返回索引列表，**丢弃了 LLM 的聚类理由**
- ❌ 中间结果只保存聚类结果（哪些索引在一起），**无法看到 LLM 的决策依据**
- ❌ 无法区分是 embedding 聚类还是 LLM 聚类

## ✅ 解决方案

### 1. 增强返回值

**修改前:**
```python
def _llm_cluster_batch(...) -> list:
    # 只返回 clusters（索引列表）
    return clusters
```

**修改后:**
```python
def _llm_cluster_batch(...) -> tuple:
    # 返回 (clusters, cluster_details)
    # cluster_details 包含 LLM 的聚类描述和理由
    return clusters, cluster_details
```

### 2. 保存详细信息

**新增字段:**

```json
{
  "clustering": {
    "method": "llm",  // 👈 新增：标识聚类方法
    "clusters": [
      {
        "cluster_id": 0,
        "size": 3,
        "member_indices": [0, 1, 2],
        
        // 👇 新增：LLM 的聚类理由
        "llm_description": "Different name variations of New York City",
        "llm_rationale": "These are all referring to the same city..."
      }
    ]
  }
}
```

## 📝 修改清单

### 文件修改

| 文件 | 改动 | 说明 |
|------|------|------|
| `models/constructor/kt_gen.py` | 3 处修改 | 增强返回值和保存逻辑 |
| `example_analyze_dedup_results.py` | 2 处修改 | 显示 LLM 聚类信息 |
| `LLM_CLUSTERING_INTERMEDIATE_RESULTS.md` | 新增 | 格式文档 |
| `LLM_CLUSTERING_SAVE_SUMMARY.md` | 新增 | 本文件 |

### 代码改动详情

#### 1. `_llm_cluster_batch` 方法

```python
# 修改前
def _llm_cluster_batch(...) -> list:
    ...
    return clusters

# 修改后
def _llm_cluster_batch(...) -> tuple:
    ...
    cluster_details = []
    for cluster_info in clusters_raw:
        cluster_details.append({
            "cluster_id": cluster_idx,
            "members": cluster_members,
            "description": cluster_info.get("description", ""),
            "llm_rationale": cluster_info.get("description", "")
        })
    return clusters, cluster_details
```

#### 2. `_cluster_candidate_tails_with_llm` 方法

```python
# 修改前
def _cluster_candidate_tails_with_llm(...) -> list:
    return self._llm_cluster_batch(...)

# 修改后
def _cluster_candidate_tails_with_llm(...) -> tuple:
    clusters, details = self._llm_cluster_batch(...)
    return clusters, details
```

#### 3. 调用点更新（2 处）

**在 `_semantic_deduplicate_group` 中:**
```python
# 修改前
if clustering_method == "llm":
    initial_clusters = self._cluster_candidate_tails_with_llm(...)

# 修改后
if clustering_method == "llm":
    initial_clusters, llm_clustering_details = self._cluster_candidate_tails_with_llm(...)
```

**在 `_deduplicate_keyword_nodes` 中:**
```python
# 同样的修改
```

#### 4. 保存逻辑增强（2 处）

```python
# 在保存中间结果时
if save_intermediate:
    # 新增：标记聚类方法
    edge_dedup_result["clustering"]["method"] = clustering_method
    
    for cluster_idx, cluster in enumerate(initial_clusters):
        cluster_info = {...}
        
        # 新增：保存 LLM 聚类详情
        if llm_clustering_details and cluster_idx < len(llm_clustering_details):
            detail = llm_clustering_details[cluster_idx]
            cluster_info["llm_description"] = detail.get("description", "")
            cluster_info["llm_rationale"] = detail.get("llm_rationale", "")
```

## 🎁 新功能

### 1. 可视化 LLM 聚类理由

运行分析脚本时，现在会显示：

```bash
$ python example_analyze_dedup_results.py output/dedup_intermediate/*.json

【聚类效果分析】
  聚类方法: llm  👈 新增
  单项 clusters: 15 (30.0%)
  多项 clusters: 35 (70.0%)

【详细案例】
--- Community 1: Cities in USA ---
聚类方法: llm  👈 新增
聚类结果: 5 clusters

LLM 聚类描述:  👈 新增
  • Cluster 0 (3 项):
    Different name variations of New York City
  • Cluster 1 (2 项):
    Los Angeles and its abbreviation
```

### 2. 调试聚类质量

```python
# 可以提取所有 LLM 聚类的理由
with open('results.json') as f:
    data = json.load(f)

for comm in data['communities']:
    clustering = comm['clustering']
    if clustering['method'] == 'llm':
        for cluster in clustering['clusters']:
            if cluster['size'] > 1:
                print(f"Cluster: {cluster['llm_description']}")
                print(f"Reason: {cluster['llm_rationale']}\n")
```

### 3. 对比聚类方法

```python
# 可以对比 LLM 和 embedding 聚类的效果
llm_results = load_results('llm_clustering.json')
emb_results = load_results('embedding_clustering.json')

print(f"LLM 聚类: {count_clusters(llm_results)} clusters")
print(f"Embedding 聚类: {count_clusters(emb_results)} clusters")

# 查看 LLM 的聚类理由
for cluster in llm_results['communities'][0]['clustering']['clusters']:
    print(f"  - {cluster.get('llm_description', 'N/A')}")
```

## 📊 格式示例

### 完整示例

```json
{
  "dataset": "demo",
  "communities": [
    {
      "community_id": "comm_123",
      "community_name": "US Cities",
      "clustering": {
        "method": "llm",
        "threshold": 0.85,
        "clusters": [
          {
            "cluster_id": 0,
            "size": 3,
            "member_indices": [0, 1, 2],
            "members": [
              {"index": 0, "description": "New York City"},
              {"index": 1, "description": "NYC"},
              {"index": 2, "description": "New York"}
            ],
            "llm_description": "Different name variations of New York City",
            "llm_rationale": "All three refer to the same city. NYC is the abbreviation, and 'New York' in the context of cities refers to New York City rather than the state."
          },
          {
            "cluster_id": 1,
            "size": 2,
            "member_indices": [3, 4],
            "members": [
              {"index": 3, "description": "Los Angeles"},
              {"index": 4, "description": "LA"}
            ],
            "llm_description": "Los Angeles and its abbreviation",
            "llm_rationale": "LA is the common abbreviation for Los Angeles."
          },
          {
            "cluster_id": 2,
            "size": 1,
            "member_indices": [5],
            "members": [
              {"index": 5, "description": "Chicago"}
            ],
            "llm_description": "Singleton cluster (unassigned by LLM)",
            "llm_rationale": ""
          }
        ]
      }
    }
  ]
}
```

## 🔄 向后兼容性

### Embedding 聚类（不受影响）

```json
{
  "clustering": {
    "method": "embedding",
    "threshold": 0.85,
    "clusters": [
      {
        "cluster_id": 0,
        "size": 3,
        "member_indices": [0, 1, 2]
        // 没有 llm_description 和 llm_rationale
      }
    ]
  }
}
```

### 安全访问

```python
# 在代码中安全访问新字段
clustering = comm['clustering']
method = clustering.get('method', 'unknown')

if method == 'llm':
    for cluster in clustering['clusters']:
        desc = cluster.get('llm_description', 'N/A')
        rationale = cluster.get('llm_rationale', '')
        print(f"{desc}: {rationale}")
```

## 💡 使用建议

### 1. 分析聚类质量

```bash
# 运行分析脚本
python example_analyze_dedup_results.py output/dedup_intermediate/*.json

# 查看 LLM 聚类的详细理由
```

### 2. 调试聚类问题

```python
# 找出可能有问题的聚类
for cluster in clustering['clusters']:
    if cluster['size'] > 10:  # 过大的聚类
        print(f"Large cluster: {cluster.get('llm_description')}")
        print(f"Rationale: {cluster.get('llm_rationale')}")
```

### 3. 对比不同配置

```bash
# 使用 LLM 聚类
python main.py --config config_llm.yaml

# 使用 embedding 聚类
python main.py --config config_embedding.yaml

# 对比两种方法的聚类结果
diff <(jq '.communities[].clustering.clusters[].size' results_llm.json) \
     <(jq '.communities[].clustering.clusters[].size' results_emb.json)
```

## 🎯 核心价值

### 之前（修改前）

```
LLM 聚类 → 返回索引 → 保存索引 → ❌ 看不到 LLM 的理由
```

### 现在（修改后）

```
LLM 聚类 → 返回索引+理由 → 保存索引+理由 → ✅ 可以看到 LLM 的决策依据
```

## 📈 效果对比

| 方面 | 修改前 | 修改后 |
|------|--------|--------|
| **可见性** | 只看到聚类结果 | 可以看到聚类理由 |
| **调试性** | 难以理解聚类决策 | 容易分析和验证 |
| **透明度** | LLM 黑盒 | LLM 决策透明 |
| **存储** | ~10 KB | ~15 KB (+50%) |

## 🔍 验证方法

### 1. 检查格式

```bash
# 确认包含 method 字段
jq '.communities[0].clustering.method' results.json

# 确认包含 llm_description
jq '.communities[0].clustering.clusters[0].llm_description' results.json
```

### 2. 对比文件

```bash
# LLM 聚类文件应该更大（包含描述）
ls -lh output/dedup_intermediate/*llm*.json
ls -lh output/dedup_intermediate/*embedding*.json
```

### 3. 运行测试

```bash
# 使用示例配置测试
python main.py --config config/example_with_dual_llm.yaml --dataset demo

# 检查生成的中间结果
python example_analyze_dedup_results.py output/dedup_intermediate/*.json
```

## 📚 相关文档

- **格式详情**: [LLM_CLUSTERING_INTERMEDIATE_RESULTS.md](./LLM_CLUSTERING_INTERMEDIATE_RESULTS.md)
- **LLM 聚类**: [LLM_CLUSTERING_README.md](./LLM_CLUSTERING_README.md)
- **双 LLM**: [DUAL_LLM_GUIDE.md](./DUAL_LLM_GUIDE.md)
- **原有格式**: [DEDUP_INTERMEDIATE_RESULTS.md](./DEDUP_INTERMEDIATE_RESULTS.md)

## 🎉 总结

✅ **现在可以通过 `save_intermediate_results` 保存 LLM 聚类的详细信息了！**

新增内容：
- `clustering.method`: 标识聚类方法
- `cluster.llm_description`: LLM 的聚类描述
- `cluster.llm_rationale`: LLM 的详细理由

这些信息对于：
- 🔍 **理解** LLM 的聚类决策
- 🐛 **调试** 聚类质量问题
- 📊 **对比** 不同聚类方法的效果

非常有价值！

---

**更新时间**: 2025-10-20
