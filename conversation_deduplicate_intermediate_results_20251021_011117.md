# 对话记录：查看 _deduplicate_keyword_nodes 中间结果保存代码

**日期时间**: 2025-10-21 01:11:17  
**分支**: cursor/examine-intermediate-result-saving-code-0b37

## 用户提问

当前 _deduplicate_keyword_nodes中 保存中间结果的代码是什么样的

## 代码分析

在 `models/constructor/kt_gen.py` 文件的 `_deduplicate_keyword_nodes` 函数中，保存中间结果的代码包含以下几个主要部分：

### 1. 初始化中间结果收集器 (行 1532-1542)

```python
# Initialize intermediate results collector
save_intermediate = getattr(config, "save_intermediate_results", False)
intermediate_results = {
    "dataset": self.dataset_name,
    "config": {
        "threshold": threshold,
        "max_batch_size": max_batch_size,
        "max_candidates": max_candidates,
    },
    "communities": []
} if save_intermediate else None
```

**说明**: 根据配置决定是否启用中间结果保存，并初始化顶层结果字典，包含数据集名称、配置参数和社区列表。

### 2. 社区级别的结果收集器 (行 1549-1563)

```python
community_result = {
    "community_id": community_id,
    "community_name": None,
    "relation": "keyword_of",
    "total_candidates": len(keyword_ids),
    "candidates": [],
    "clustering": {
        "method": "average_linkage",
        "threshold": threshold,
        "clusters": []
    },
    "llm_groups": [],
    "final_merges": []
} if save_intermediate else None
```

**说明**: 为每个社区创建独立的结果收集器，记录该社区的所有去重过程信息。

### 3. 保存候选项信息 (行 1624-1635)

```python
if save_intermediate:
    community_result["community_name"] = head_text
    community_result["head_contexts"] = head_context_lines
    for entry in entries:
        community_result["candidates"].append({
            "index": entry["index"],
            "node_id": entry["node_id"],
            "description": entry["description"],
            "raw_name": entry["raw_name"],
            "source_entity_id": entry.get("source_entity_id"),
            "source_entity_name": entry.get("source_entity_name")
        })
```

**说明**: 保存社区的基本信息和所有候选关键词节点的详细信息。

### 4. 保存聚类结果 (行 1655-1681)

```python
if save_intermediate:
    # Add clustering method info
    community_result["clustering"]["method"] = clustering_method
    
    for cluster_idx, cluster in enumerate(initial_clusters):
        cluster_info = {
            "cluster_id": cluster_idx,
            "size": len(cluster),
            "member_indices": cluster,
            "members": [
                {
                    "index": idx,
                    "node_id": entries[idx]["node_id"],
                    "description": entries[idx]["description"]
                }
                for idx in cluster if 0 <= idx < len(entries)
            ]
        }
        
        # Add LLM clustering details if available
        if llm_clustering_details and cluster_idx < len(llm_clustering_details):
            detail = llm_clustering_details[cluster_idx]
            cluster_info["llm_description"] = detail.get("description", "")
            cluster_info["llm_rationale"] = detail.get("llm_rationale", "")
        
        community_result["clustering"]["clusters"].append(cluster_info)
```

**说明**: 保存初始聚类的结果，包括每个簇的成员和大小。如果使用 LLM 聚类，还会保存 LLM 的描述和理由。

### 5. 保存LLM分组结果 (行 1708-1733)

```python
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

**说明**: 保存 LLM 语义分组的结果，包括每个批次的分组信息、代表节点和理由。

### 6. 保存合并操作 (行 1762-1779)

```python
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
```

**说明**: 记录每次实际执行的节点合并操作，包括保留的代表节点、被合并的重复节点以及合并理由。

### 7. 保存社区汇总统计 (行 1800-1810)

```python
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

**说明**: 为每个社区生成统计摘要，包括候选数量、聚类数量、LLM 调用次数和合并次数等。

### 8. 写入文件 (行 1812-1846)

```python
if save_intermediate and intermediate_results:
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = getattr(config, "intermediate_results_path", None)
    
    if not output_path:
        output_path = f"output/dedup_intermediate/{self.dataset_name}_dedup_{timestamp}.json"
    else:
        # If path is a directory, add filename
        if output_path.endswith('/'):
            output_path = f"{output_path}{self.dataset_name}_dedup_{timestamp}.json"
    
    # Ensure directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Add summary statistics
    intermediate_results["summary"] = {
        "total_communities": len(intermediate_results["communities"]),
        "total_candidates": sum(c["total_candidates"] for c in intermediate_results["communities"]),
        "total_clusters": sum(len(c["clustering"]["clusters"]) for c in intermediate_results["communities"]),
        "total_llm_calls": sum(len(c["llm_groups"]) for c in intermediate_results["communities"]),
        "total_merges": sum(len(c["final_merges"]) for c in intermediate_results["communities"]),
        "total_items_merged": sum(c["summary"]["items_merged"] for c in intermediate_results["communities"])
    }
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(intermediate_results, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved deduplication intermediate results to: {output_path}")
        logger.info(f"Summary: {intermediate_results['summary']}")
    except Exception as e:
        logger.warning(f"Failed to save intermediate results: {e}")
```

**说明**: 
- 根据配置或默认路径生成输出文件路径（带时间戳）
- 创建必要的目录
- 添加全局汇总统计（所有社区的总计）
- 将完整的中间结果以 JSON 格式写入文件
- 记录保存结果的日志

## 设计特点

这个中间结果保存机制的设计具有以下特点：

1. **分层记录**: 从全局（所有社区）→ 社区级别 → 聚类 → LLM分组 → 合并操作，层层记录详细信息

2. **可配置性**: 通过 `save_intermediate_results` 配置项控制是否启用，避免不必要的性能开销

3. **完整追溯**: 记录了去重过程的每一个关键步骤，便于调试和分析算法效果

4. **统计摘要**: 在社区级别和全局级别都提供统计摘要，方便快速了解去重效果

5. **时间戳命名**: 输出文件带时间戳，避免覆盖，便于对比不同时间的结果

6. **异常处理**: 保存失败时只记录警告，不影响主流程执行

## 配置参数

要启用中间结果保存，需要在配置中设置：

```python
config.save_intermediate_results = True
config.intermediate_results_path = "output/dedup_intermediate/"  # 可选，不设置时使用默认路径
```

## 输出示例

生成的 JSON 文件结构：

```json
{
  "dataset": "dataset_name",
  "config": {
    "threshold": 0.85,
    "max_batch_size": 8,
    "max_candidates": 0
  },
  "communities": [
    {
      "community_id": "...",
      "community_name": "...",
      "candidates": [...],
      "clustering": {
        "method": "embedding",
        "clusters": [...]
      },
      "llm_groups": [...],
      "final_merges": [...],
      "summary": {...}
    }
  ],
  "summary": {
    "total_communities": 10,
    "total_candidates": 150,
    "total_merges": 45,
    ...
  }
}
```

---

**文件路径**: `models/constructor/kt_gen.py`  
**函数**: `_deduplicate_keyword_nodes` (行 1509-1847)
