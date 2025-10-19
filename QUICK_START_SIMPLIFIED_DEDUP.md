# 简化语义去重快速开始指南

## 1. 启用简化去重记录

在配置文件中启用中间结果保存：

```yaml
# config/base_config.yaml 或你的配置文件
construction:
  semantic_dedup:
    enabled: true
    save_intermediate_results: true
    intermediate_results_path: "output/dedup_intermediate/"  # 可选
```

## 2. 运行知识图谱构建

正常运行你的图构建流程：

```bash
python main.py --config your_config.yaml
```

## 3. 查看输出结果

去重完成后，在输出目录会生成两个 JSON 文件：

```
output/dedup_intermediate/
├── {dataset}_keyword_dedup_{timestamp}.json   # 关键词去重结果
└── {dataset}_edge_dedup_{timestamp}.json      # 边去重结果
```

## 4. 输出格式示例

每个文件都是一个简单的数组：

```json
[
  {
    "head": "实体或社区名称",
    "relation": "关系类型",
    "dedup_records": [
      {
        "merged_tails": ["合并的tail1", "tail2", "tail3"],
        "chunk_ids": ["chunk_id_1", "chunk_id_2"],
        "rationale": "LLM判断这些应该合并的理由"
      }
    ]
  }
]
```

## 5. 快速分析

### 使用 Python 分析

```python
import json

# 读取结果
with open('output/dedup_intermediate/dataset_edge_dedup_20251019_123456.json', 'r') as f:
    results = json.load(f)

# 统计合并情况
for record in results:
    print(f"Head: {record['head']}")
    print(f"Relation: {record['relation']}")
    print(f"合并操作数: {len(record['dedup_records'])}")
    
    for dedup in record['dedup_records']:
        tails = dedup['merged_tails']
        print(f"  - 合并了 {len(tails)} 个tail: {', '.join(tails)}")
        print(f"    来自 {len(dedup['chunk_ids'])} 个chunk")
        print(f"    理由: {dedup['rationale'][:50]}...")
    print()
```

### 使用 jq 分析（命令行）

```bash
# 统计总共有多少个去重组
jq 'length' dataset_edge_dedup_*.json

# 查看所有 head 和 relation
jq '.[] | {head: .head, relation: .relation}' dataset_edge_dedup_*.json

# 统计总共合并了多少个 tail
jq '[.[] | .dedup_records | length] | add' dataset_edge_dedup_*.json

# 查看特定 relation 的去重情况
jq '.[] | select(.relation == "works_at")' dataset_edge_dedup_*.json
```

## 6. 常见问题

### Q: 为什么没有生成输出文件？
A: 检查以下几点：
- 确认 `save_intermediate_results: true` 已设置
- 确认有实际的去重操作发生（如果没有重复项，不会生成记录）
- 检查日志中是否有保存成功的提示

### Q: 如何找到某个实体的去重记录？
A: 使用 jq 或 Python 过滤：
```bash
jq '.[] | select(.head | contains("张三"))' dataset_edge_dedup_*.json
```

### Q: 文件太大怎么办？
A: 简化版已经大幅减小了文件大小。如果还是太大，可以：
- 调整 `max_candidates` 限制候选数量
- 提高 `embedding_threshold` 减少合并操作
- 分批处理数据

## 7. 相关文档

- **详细格式说明**：`SIMPLIFIED_DEDUP_RESULTS.md`
- **变更说明**：`SEMANTIC_DEDUP_SIMPLIFICATION.md`
- **格式对比**：`examples/dedup_output_comparison.md`
- **示例输出**：`examples/simplified_dedup_output_example.json`

## 8. 下一步

- 查看实际输出，了解去重效果
- 根据 rationale 评估 LLM 的判断是否合理
- 调整 `embedding_threshold` 优化去重效果
- 使用 chunk_ids 追溯到原始文本进行验证
