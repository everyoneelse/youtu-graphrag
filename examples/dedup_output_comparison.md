# 语义去重输出格式对比

## 简化前的输出格式（旧版）

```json
{
  "dataset": "example_dataset",
  "config": {
    "threshold": 0.85,
    "max_batch_size": 8,
    "max_candidates": 50
  },
  "communities": [
    {
      "community_id": "comm_123",
      "community_name": "张三 (人物实体)",
      "relation": "works_at",
      "total_candidates": 5,
      "candidates": [
        {
          "index": 0,
          "node_id": "node_001",
          "description": "北京协和医院",
          "raw_name": "北京协和医院",
          "source_entity_id": "entity_123",
          "source_entity_name": "张三"
        },
        {
          "index": 1,
          "node_id": "node_002",
          "description": "协和医院",
          "raw_name": "协和医院",
          "source_entity_id": "entity_123",
          "source_entity_name": "张三"
        },
        {
          "index": 2,
          "node_id": "node_003",
          "description": "北京协和",
          "raw_name": "北京协和",
          "source_entity_id": "entity_123",
          "source_entity_name": "张三"
        },
        {
          "index": 3,
          "node_id": "node_004",
          "description": "第二医院",
          "raw_name": "第二医院",
          "source_entity_id": "entity_123",
          "source_entity_name": "张三"
        },
        {
          "index": 4,
          "node_id": "node_005",
          "description": "人民医院",
          "raw_name": "人民医院",
          "source_entity_id": "entity_123",
          "source_entity_name": "张三"
        }
      ],
      "head_contexts": [
        "- (abc123) 张三是一位经验丰富的医生，在北京协和医院工作多年...",
        "- (def456) 张三目前在协和医院担任主治医师..."
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
                "node_id": "node_001",
                "description": "北京协和医院"
              },
              {
                "index": 1,
                "node_id": "node_002",
                "description": "协和医院"
              },
              {
                "index": 2,
                "node_id": "node_003",
                "description": "北京协和"
              }
            ]
          },
          {
            "cluster_id": 1,
            "size": 1,
            "member_indices": [3],
            "members": [
              {
                "index": 3,
                "node_id": "node_004",
                "description": "第二医院"
              }
            ]
          },
          {
            "cluster_id": 2,
            "size": 1,
            "member_indices": [4],
            "members": [
              {
                "index": 4,
                "node_id": "node_005",
                "description": "人民医院"
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
              "rationale": "这三个实体都指向同一家医院",
              "member_details": [
                {
                  "local_idx": 0,
                  "global_idx": 0,
                  "description": "北京协和医院"
                },
                {
                  "local_idx": 1,
                  "global_idx": 1,
                  "description": "协和医院"
                },
                {
                  "local_idx": 2,
                  "global_idx": 2,
                  "description": "北京协和"
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
            "node_id": "node_001",
            "description": "北京协和医院"
          },
          "duplicates": [
            {
              "index": 1,
              "node_id": "node_002",
              "description": "协和医院"
            },
            {
              "index": 2,
              "node_id": "node_003",
              "description": "北京协和"
            }
          ],
          "rationale": "这三个实体都指向同一家医院"
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
  ],
  "summary": {
    "total_communities": 1,
    "total_candidates": 5,
    "total_clusters": 3,
    "total_llm_calls": 1,
    "total_merges": 1,
    "total_items_merged": 2
  }
}
```

**文件大小**：约 2-3KB（单个去重组）

---

## 简化后的输出格式（新版）

```json
[
  {
    "head": "张三 (人物实体)",
    "relation": "works_at",
    "dedup_records": [
      {
        "merged_tails": [
          "北京协和医院",
          "协和医院",
          "北京协和"
        ],
        "chunk_ids": ["abc123", "def456", "ghi789"],
        "rationale": "这三个实体都指向同一家医院（北京协和医院），只是在不同文本中的表述方式不同。"
      }
    ]
  }
]
```

**文件大小**：约 0.3KB（单个去重组）

---

## 对比总结

| 特性 | 旧版（详细） | 新版（简化） |
|------|------------|------------|
| **文件大小** | 大（包含所有中间步骤） | 小（只有核心信息） |
| **可读性** | 复杂嵌套结构 | 简单平面结构 |
| **信息量** | 完整的处理过程 | 关键的决策信息 |
| **调试价值** | 可追踪每个步骤 | 可追踪最终决策 |
| **分析难度** | 需要深入理解结构 | 一目了然 |
| **文件数量** | 多个嵌套对象 | 简单数组 |

## 保留的核心信息

无论是旧版还是新版，都保留了最重要的信息：

✅ **输入**：head 和 relation（知道对什么进行去重）
✅ **结果**：merged_tails（知道哪些被合并了）
✅ **来源**：chunk_ids（知道来自哪些文本）
✅ **理由**：rationale（知道为什么合并）

## 移除的信息

新版移除了以下中间过程信息：

❌ 所有候选项的完整列表
❌ 聚类的详细步骤和参数
❌ 每个 LLM 调用的详细输入输出
❌ 复杂的统计汇总信息
❌ 节点 ID 和索引映射

## 适用场景

### 使用新版（简化版）的场景：
- ✅ 日常使用和监控
- ✅ 快速检查去重效果
- ✅ 生成报告和文档
- ✅ 长期存储和归档

### 需要旧版（详细版）的场景：
- ⚠️ 深度调试去重算法
- ⚠️ 研究 LLM 决策过程
- ⚠️ 优化聚类参数
- ⚠️ 性能分析和优化

如果需要详细版本，可以在代码中恢复相关字段的记录。
