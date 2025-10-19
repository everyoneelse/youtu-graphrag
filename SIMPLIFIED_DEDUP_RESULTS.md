# 简化的语义去重中间结果说明

## 概述

简化后的 `save_intermediate_results` 功能记录每次语义去重（semantic_dedup）操作的关键信息：

1. **输入信息**：head 和 relation
2. **合并结果**：合并的 tail 列表
3. **来源信息**：所在的 chunk id
4. **判断依据**：LLM 的 rationale

## 输出文件

根据去重类型，会生成两个 JSON 文件：

1. **关键词去重结果**：`{dataset}_keyword_dedup_{timestamp}.json`
2. **边去重结果**：`{dataset}_edge_dedup_{timestamp}.json`

## 输出格式

### 关键词去重结果

```json
[
  {
    "head": "社区名称或实体名称",
    "relation": "keyword_of",
    "dedup_records": [
      {
        "merged_tails": ["关键词1", "关键词2", "关键词3"],
        "chunk_ids": ["chunk_id_1", "chunk_id_2"],
        "rationale": "LLM判断这些关键词指向同一概念的理由"
      }
    ]
  }
]
```

### 边去重结果

```json
[
  {
    "head": "头实体名称",
    "relation": "关系类型",
    "dedup_records": [
      {
        "merged_tails": ["尾实体1描述", "尾实体2描述"],
        "chunk_ids": ["chunk_id_1", "chunk_id_2", "chunk_id_3"],
        "rationale": "LLM判断这些尾实体是重复的理由"
      }
    ]
  }
]
```

## 字段说明

- **head**：进行去重时的头实体或社区名称
- **relation**：关系类型（如 "keyword_of", "has_attribute", "located_in" 等）
- **dedup_records**：本次去重操作的记录列表
  - **merged_tails**：合并在一起的所有 tail（第一个是代表性的 tail）
  - **chunk_ids**：这些 tail 来自的所有 chunk ID（已排序去重）
  - **rationale**：LLM 判断这些 tail 应该合并的理由

## 示例

### 关键词去重示例

```json
[
  {
    "head": "张三 (人物)",
    "relation": "keyword_of",
    "dedup_records": [
      {
        "merged_tails": ["医生", "大夫", "医师"],
        "chunk_ids": ["abc123", "def456"],
        "rationale": "这些关键词都指向张三的职业，是同一概念的不同表达"
      },
      {
        "merged_tails": ["北京", "京城"],
        "chunk_ids": ["abc123", "ghi789"],
        "rationale": "这些关键词都指向相同的地理位置"
      }
    ]
  }
]
```

### 边去重示例

```json
[
  {
    "head": "张三",
    "relation": "works_at",
    "dedup_records": [
      {
        "merged_tails": [
          "北京协和医院",
          "协和医院",
          "北京协和"
        ],
        "chunk_ids": ["abc123", "def456", "ghi789"],
        "rationale": "这些实体都指向同一家医院，只是表述不同"
      }
    ]
  },
  {
    "head": "李四",
    "relation": "has_attribute",
    "dedup_records": [
      {
        "merged_tails": [
          "身高180cm",
          "身高180厘米"
        ],
        "chunk_ids": ["jkl012"],
        "rationale": "相同的身高属性，单位表达不同"
      }
    ]
  }
]
```

## 与之前版本的区别

**简化前**的输出包含大量详细信息：
- 所有候选项的完整列表
- 聚类的详细步骤
- 每个 LLM 调用的输入输出
- 复杂的嵌套结构和统计信息

**简化后**的输出仅保留核心信息：
- 每次去重操作的输入（head + relation）
- 最终合并的结果（merged_tails）
- 来源信息（chunk_ids）
- 判断依据（rationale）

这使得输出文件更小、更易读、更容易分析和调试。

## 配置

在配置文件中启用中间结果记录：

```yaml
construction:
  semantic_dedup:
    enabled: true
    save_intermediate_results: true
    intermediate_results_path: "output/dedup_intermediate/"  # 可选，默认为此路径
```
