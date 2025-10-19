# LLM Semantic Group 之后的 save_intermediate 详解

## 完整流程概览

```
LLM 调用
   ↓
2️⃣ 保存 LLM 返回的原始分组结果
   ↓
3️⃣ 遍历 LLM 分组，执行实际的节点合并
   ↓
4️⃣ 保存每次合并操作的详细记录
   ↓
5️⃣ 生成统计摘要并累加到结果集合
```

---

## 步骤 2️⃣：保存 LLM 返回结果（第 1319-1344 行）

### 代码

```python
# Save LLM groups result
if save_intermediate:
    llm_result = {
        "cluster_id": initial_clusters.index([idx for idx in cluster if 0 <= idx < len(entries)]),
        "batch_indices": batch_indices,
        "batch_size": len(batch_indices),
        "groups": []
    }
    if groups:
        for group in groups:
            group_info = {
                "members": group.get("members", []),
                "representative": group.get("representative"),
                "rationale": group.get("rationale"),
                "member_details": [
                    {
                        "local_idx": m,
                        "global_idx": batch_indices[m] if 0 <= m < len(batch_indices) else None,
                        "description": entries[batch_indices[m]]["description"] if 0 <= m < len(batch_indices) else None
                    }
                    for m in group.get("members", [])
                    if 0 <= m < len(batch_indices)
                ]
            }
            llm_result["groups"].append(group_info)
    community_result["llm_groups"].append(llm_result)
```

### 作用：记录 LLM 的原始输出

**保存的内容**：

#### 2.1 `llm_result` 顶层信息

| 字段 | 含义 | 示例 |
|------|------|------|
| `cluster_id` | 这批候选来自哪个 cluster | `0` |
| `batch_indices` | 送去 LLM 的候选的全局索引 | `[0, 1, 2]` |
| `batch_size` | 本批次的大小 | `3` |
| `groups` | LLM 返回的分组 | `[{...}, {...}]` |

**为什么需要**：
- 记录输入（batch_indices）→ 知道送给 LLM 的是哪些候选
- 对应到 cluster → 追溯聚类结果

#### 2.2 `group_info` - LLM 返回的每个分组

| 字段 | 含义 | 示例 | 说明 |
|------|------|------|------|
| `members` | 组内成员的**局部索引** | `[0, 1]` | 相对于 batch 的索引 |
| `representative` | 代表成员的**局部索引** | `0` | LLM 选择的代表 |
| `rationale` | LLM 的分组理由 | "Both refer to..." | 为什么这样分组 |
| `member_details` | 每个成员的详细信息 | `[{...}, {...}]` | 见下表 |

#### 2.3 `member_details` - 成员详细信息

| 字段 | 含义 | 示例 |
|------|------|------|
| `local_idx` | 局部索引（相对于 batch） | `0` |
| `global_idx` | 全局索引（相对于所有候选） | `5` |
| `description` | 节点描述 | "深度学习" |

**为什么需要**：
- **追溯性**：知道 LLM 基于什么信息做的决策
- **调试**：如果合并错误，可以看到 LLM 的原始输出
- **评估**：可以分析 LLM 的分组质量

### 示例数据

假设输入：
```python
batch_entries = [
    {"description": "deep learning", ...},    # batch 中的 idx 0
    {"description": "neural networks", ...},  # batch 中的 idx 1
    {"description": "DNN", ...}               # batch 中的 idx 2
]
```

LLM 返回：
```python
groups = [
    {
        "members": [0, 1, 2],
        "representative": 0,
        "rationale": "All refer to deep learning concepts"
    }
]
```

保存的 `llm_result`：
```json
{
  "cluster_id": 0,
  "batch_indices": [5, 6, 7],  // 全局索引
  "batch_size": 3,
  "groups": [
    {
      "members": [0, 1, 2],  // 局部索引
      "representative": 0,
      "rationale": "All refer to deep learning concepts",
      "member_details": [
        {"local_idx": 0, "global_idx": 5, "description": "deep learning"},
        {"local_idx": 1, "global_idx": 6, "description": "neural networks"},
        {"local_idx": 2, "global_idx": 7, "description": "DNN"}
      ]
    }
  ]
}
```

---

## 步骤 3️⃣：处理 LLM 分组，执行合并（第 1352-1397 行）

### 代码概览

```python
for group in groups:
    # 3.1 获取代表节点
    rep_local = group.get("representative")
    rep_global = batch_indices[rep_local]
    
    # 3.2 收集重复节点
    duplicates: list = []
    for member_local in group.get("members", []):
        member_global = batch_indices[member_local]
        if member_global != rep_global:
            duplicates.append(entries[member_global])
            duplicate_indices.add(member_global)
    
    # 3.3 执行实际的节点合并
    if duplicates:
        self._merge_keyword_nodes(
            entries[rep_global],
            duplicates,
            group.get("rationale"),
            keyword_mapping,
        )
```

### 作用：将 LLM 的决策应用到图结构

**关键概念**：
- **局部索引 → 全局索引**：LLM 返回的是相对于 batch 的索引，需要转换
- **代表节点**：保留的节点
- **重复节点**：要被合并掉的节点

### 索引转换示例

```
假设 batch_indices = [5, 6, 7]  (全局索引)

LLM 返回:
  members: [0, 1, 2]  (局部索引)
  representative: 0

转换:
  rep_local = 0
  rep_global = batch_indices[0] = 5  ✓ 全局索引

  member_local = 1
  member_global = batch_indices[1] = 6  ✓ 全局索引
```

---

## 步骤 4️⃣：保存合并操作记录（第 1372-1390 行）

### 代码

```python
if duplicates:
    # Save merge operation
    if save_intermediate:
        merge_info = {
            "representative": {
                "index": rep_global,
                "node_id": entries[rep_global]["node_id"],
                "description": entries[rep_global]["description"]
            },
            "duplicates": [
                {
                    "index": d.get("index"),
                    "node_id": d["node_id"],
                    "description": d["description"]
                }
                for d in duplicates
            ],
            "rationale": group.get("rationale")
        }
        community_result["final_merges"].append(merge_info)
    
    # 实际执行合并
    self._merge_keyword_nodes(...)
```

### 作用：记录实际发生的合并操作

**保存内容**：

| 字段 | 含义 | 示例 |
|------|------|------|
| `representative` | 保留的节点 | `{"index": 5, "node_id": "kw_001", "description": "deep learning"}` |
| `duplicates` | 被合并的节点列表 | `[{"index": 6, ...}, {"index": 7, ...}]` |
| `rationale` | 合并理由（来自LLM） | "All refer to deep learning concepts" |

**为什么需要**：
- **审计**：记录哪些节点被合并了
- **可逆性**：如果需要，可以根据记录恢复
- **质量评估**：检查合并是否合理

### 与步骤 2 的区别

| 方面 | 步骤 2 (LLM 输出) | 步骤 4 (合并记录) |
|------|------------------|------------------|
| **时机** | LLM 调用之后立即保存 | 实际合并发生时保存 |
| **内容** | LLM 的原始分组建议 | 真正执行的合并操作 |
| **索引** | 包含局部和全局索引 | 只包含全局索引 |
| **粒度** | 每次 LLM 调用（可能包含多个group） | 每次实际合并 |

### 示例对比

**步骤 2 保存的（LLM 原始输出）**：
```json
{
  "groups": [
    {
      "members": [0, 1, 2],
      "representative": 0,
      "rationale": "All refer to deep learning",
      "member_details": [...]
    }
  ]
}
```

**步骤 4 保存的（实际合并操作）**：
```json
{
  "representative": {
    "index": 5,
    "node_id": "keyword_001",
    "description": "deep learning"
  },
  "duplicates": [
    {"index": 6, "node_id": "keyword_002", "description": "neural networks"},
    {"index": 7, "node_id": "keyword_003", "description": "DNN"}
  ],
  "rationale": "All refer to deep learning"
}
```

---

## 步骤 5️⃣：生成统计摘要（第 1410-1421 行）

### 代码

```python
# Save community result
if save_intermediate:
    community_result["summary"] = {
        "total_candidates": len(entries),
        "total_clusters": len(initial_clusters),
        "single_item_clusters": sum(1 for c in initial_clusters if len(c) == 1),
        "multi_item_clusters": sum(1 for c in initial_clusters if len(c) > 1),
        "total_llm_calls": len(community_result["llm_groups"]),
        "total_merges": len(community_result["final_merges"]),
        "items_merged": sum(len(m["duplicates"]) for m in community_result["final_merges"])
    }
    intermediate_results["communities"].append(community_result)
```

### 作用：计算并保存统计指标

**统计指标说明**：

| 指标 | 含义 | 计算方式 | 用途 |
|------|------|---------|------|
| `total_candidates` | 候选总数 | `len(entries)` | 了解去重规模 |
| `total_clusters` | 聚类总数 | `len(initial_clusters)` | 评估聚类效果 |
| `single_item_clusters` | 单项cluster数 | `sum(1 for c if len(c)==1)` | 评估优化效果 |
| `multi_item_clusters` | 多项cluster数 | `sum(1 for c if len(c)>1)` | 需要LLM处理的cluster |
| `total_llm_calls` | LLM调用次数 | `len(llm_groups)` | 评估成本 |
| `total_merges` | 合并次数 | `len(final_merges)` | 评估去重效果 |
| `items_merged` | 去重项数 | `sum(len(duplicates))` | 实际去重的数量 |

### 示例数据

```json
{
  "summary": {
    "total_candidates": 10,          // 共 10 个候选
    "total_clusters": 5,              // 聚类成 5 个 clusters
    "single_item_clusters": 3,        // 其中 3 个是单项（被优化跳过）
    "multi_item_clusters": 2,         // 其中 2 个是多项（需要 LLM）
    "total_llm_calls": 2,             // 调用了 2 次 LLM
    "total_merges": 1,                // 发生了 1 次合并
    "items_merged": 2                 // 去重了 2 个项
  }
}
```

### 指标解读

**去重率计算**：
```
去重率 = items_merged / total_candidates × 100%
       = 2 / 10 × 100%
       = 20%
```

**LLM 效率**：
```
每次 LLM 调用平均处理 = total_candidates / total_llm_calls
                      = 10 / 2
                      = 5 个候选
```

**优化效果**：
```
跳过的 LLM 调用 = single_item_clusters
               = 3 次

节省的成本比例 = single_item_clusters / total_clusters × 100%
              = 3 / 5 × 100%
              = 60%
```

---

## 🔄 完整示例：从 LLM 输出到最终保存

### 场景设定

```python
# 有一个 community 有 5 个候选关键词
entries = [
    {"index": 0, "node_id": "kw_001", "description": "deep learning"},
    {"index": 1, "node_id": "kw_002", "description": "neural networks"},
    {"index": 2, "node_id": "kw_003", "description": "DNN"},
    {"index": 3, "node_id": "kw_004", "description": "supervised learning"},
    {"index": 4, "node_id": "kw_005", "description": "regularization"}
]

# 聚类结果
initial_clusters = [
    [0, 1, 2],  # Cluster 0: deep learning 相关
    [3],        # Cluster 1: supervised learning (单项)
    [4]         # Cluster 2: regularization (单项)
]
```

### 步骤 2：LLM 处理 Cluster 0

```python
# 输入给 LLM
batch_indices = [0, 1, 2]
batch_entries = [entries[0], entries[1], entries[2]]

# LLM 返回
groups = [
    {
        "members": [0, 1, 2],
        "representative": 0,
        "rationale": "All three refer to deep learning and neural network concepts"
    }
]

# 保存 LLM 输出
llm_result = {
    "cluster_id": 0,
    "batch_indices": [0, 1, 2],
    "batch_size": 3,
    "groups": [
        {
            "members": [0, 1, 2],
            "representative": 0,
            "rationale": "All three refer to deep learning and neural network concepts",
            "member_details": [
                {"local_idx": 0, "global_idx": 0, "description": "deep learning"},
                {"local_idx": 1, "global_idx": 1, "description": "neural networks"},
                {"local_idx": 2, "global_idx": 2, "description": "DNN"}
            ]
        }
    ]
}
# → community_result["llm_groups"].append(llm_result)
```

### 步骤 3 & 4：执行合并并保存

```python
# 从 LLM 输出中提取
rep_local = 0
rep_global = batch_indices[0] = 0

# 收集重复项
duplicates = [
    entries[1],  # "neural networks"
    entries[2]   # "DNN"
]

# 保存合并操作
merge_info = {
    "representative": {
        "index": 0,
        "node_id": "kw_001",
        "description": "deep learning"
    },
    "duplicates": [
        {"index": 1, "node_id": "kw_002", "description": "neural networks"},
        {"index": 2, "node_id": "kw_003", "description": "DNN"}
    ],
    "rationale": "All three refer to deep learning and neural network concepts"
}
# → community_result["final_merges"].append(merge_info)

# 实际执行合并（修改图结构）
self._merge_keyword_nodes(entries[0], duplicates, rationale, keyword_mapping)
```

### 步骤 5：生成统计

```python
community_result["summary"] = {
    "total_candidates": 5,           # 原始有 5 个候选
    "total_clusters": 3,              # 聚类成 3 个
    "single_item_clusters": 2,        # 其中 2 个单项（跳过了）
    "multi_item_clusters": 1,         # 其中 1 个多项
    "total_llm_calls": 1,             # 调用了 1 次 LLM
    "total_merges": 1,                # 执行了 1 次合并
    "items_merged": 2                 # 去重了 2 个项（kw_002, kw_003）
}
```

### 最终保存的完整结构

```json
{
  "community_id": "comm_123",
  "community_name": "Machine Learning",
  "relation": "keyword_of",
  "total_candidates": 5,
  "candidates": [...],
  "clustering": {
    "clusters": [
      {"cluster_id": 0, "size": 3, "members": [...]},
      {"cluster_id": 1, "size": 1, "members": [...]},
      {"cluster_id": 2, "size": 1, "members": [...]}
    ]
  },
  "llm_groups": [
    {
      "cluster_id": 0,
      "batch_indices": [0, 1, 2],
      "groups": [...]
    }
  ],
  "final_merges": [
    {
      "representative": {...},
      "duplicates": [{...}, {...}],
      "rationale": "..."
    }
  ],
  "summary": {
    "total_candidates": 5,
    "total_clusters": 3,
    "single_item_clusters": 2,
    "multi_item_clusters": 1,
    "total_llm_calls": 1,
    "total_merges": 1,
    "items_merged": 2
  }
}
```

---

## 💡 设计理念

### 为什么要分步保存？

1. **步骤 2（LLM 输出）**
   - 保存 LLM 的"建议"
   - 即使后续处理失败，也能看到 LLM 说了什么
   - 可以评估 LLM prompt 的质量

2. **步骤 4（合并记录）**
   - 保存实际执行的操作
   - 可能与 LLM 建议略有不同（例如某些节点已处理）
   - 用于审计和回滚

3. **步骤 5（统计摘要）**
   - 提供快速的定量分析
   - 不需要遍历详细记录就能了解概况
   - 用于参数调优和效果评估

### 数据可追溯性

```
原始候选 (candidates)
    ↓
聚类结果 (clustering.clusters)
    ↓
LLM 分组建议 (llm_groups)
    ↓
实际合并操作 (final_merges)
    ↓
统计摘要 (summary)
```

每一步都可以追溯到前一步，形成完整的证据链！

---

## 🎯 实用技巧

### 1. 查看 LLM 是否正确理解任务

检查 `llm_groups`:
```json
{
  "groups": [
    {
      "members": [0, 1],
      "rationale": "都来自同一上下文"  // ❌ 理由不够充分
    }
  ]
}
```

### 2. 发现过度合并

对比 `llm_groups` 和 `final_merges`:
```
llm_groups 中的 group 有 5 个 members
但 final_merges 只合并了 2 个 duplicates
→ 可能有些成员已经被处理过了
```

### 3. 评估聚类质量

查看 `summary`:
```json
{
  "single_item_clusters": 80,
  "multi_item_clusters": 20
}
```
→ 如果单项 cluster 过多，考虑降低 `embedding_threshold`

### 4. 计算成本

```python
token_per_call = 500  # 假设每次 LLM 调用消耗 500 tokens
total_tokens = summary["total_llm_calls"] * token_per_call
cost = total_tokens * price_per_token
```

---

## 📋 总结

| 步骤 | 时机 | 保存内容 | 用途 |
|------|------|---------|------|
| 2️⃣ | LLM 调用后 | LLM 原始输出 | 评估 prompt 质量 |
| 4️⃣ | 节点合并时 | 实际合并操作 | 审计、回滚 |
| 5️⃣ | Community 处理完 | 统计摘要 | 效果评估、调优 |

所有这些步骤共同构成了一个**完整、可追溯、可分析**的去重过程记录！
