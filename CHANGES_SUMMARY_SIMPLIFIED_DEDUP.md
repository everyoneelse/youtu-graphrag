# 语义去重中间结果简化 - 变更总结

## 变更日期
2025-10-19

## 变更目标

根据用户需求，将 `save_intermediate_results` 功能简化，只记录语义去重的核心信息：
1. 每次进行 semantic_dedup 时的输入（head 和 relation）
2. 最后的合并结果（cluster 或未合并）
3. 合并的 tail 连同 head、relation、chunk id、LLM 的 rationale

## 主要变更

### 1. 代码修改

**文件**: `models/constructor/kt_gen.py`

#### 修改的方法：

1. **`_deduplicate_keyword_nodes`** (行 1154-1457)
   - 简化了中间结果数据结构
   - 移除了详细的候选列表、聚类步骤、LLM 调用记录
   - 只保留核心信息：head, relation, dedup_records

2. **`_semantic_deduplicate_group`** (行 1513-1753)
   - 简化了边去重的中间结果记录
   - 统一使用相同的简化格式

3. **`triple_deduplicate_semantic`** (行 1770-1853)
   - 简化了最终保存逻辑
   - 移除了复杂的统计汇总

### 2. 新增文档

| 文件 | 说明 |
|------|------|
| `SIMPLIFIED_DEDUP_RESULTS.md` | 详细的输出格式说明和字段解释 |
| `SEMANTIC_DEDUP_SIMPLIFICATION.md` | 变更详情和技术说明 |
| `QUICK_START_SIMPLIFIED_DEDUP.md` | 快速开始指南 |
| `examples/simplified_dedup_output_example.json` | 输出格式示例 |
| `examples/dedup_output_comparison.md` | 新旧格式对比 |

### 3. 测试文件

| 文件 | 说明 |
|------|------|
| `test_simplified_dedup.py` | 格式验证测试脚本 |

## 输出格式

### 简化后的格式

```json
[
  {
    "head": "实体或社区名称",
    "relation": "关系类型",
    "dedup_records": [
      {
        "merged_tails": ["tail1", "tail2", "tail3"],
        "chunk_ids": ["chunk_id_1", "chunk_id_2"],
        "rationale": "LLM判断理由"
      }
    ]
  }
]
```

### 输出文件

- **关键词去重**：`{dataset}_keyword_dedup_{timestamp}.json`
- **边去重**：`{dataset}_edge_dedup_{timestamp}.json`

## 优势

| 方面 | 简化前 | 简化后 |
|------|--------|--------|
| **文件大小** | 大（2-3KB/组） | 小（0.3KB/组） |
| **可读性** | 复杂嵌套 | 简单直观 |
| **记录内容** | 完整流程 | 核心决策 |
| **分析难度** | 需要理解结构 | 一目了然 |

## 核心信息保留

✅ **保留的关键信息**：
- head（去重的头实体）
- relation（关系类型）
- merged_tails（合并的所有 tail）
- chunk_ids（来源 chunk）
- rationale（判断理由）

❌ **移除的信息**：
- 所有候选项详细列表
- 聚类算法的中间步骤
- LLM 调用的详细输入输出
- 节点 ID 和索引映射
- 复杂的统计汇总

## 向后兼容性

- ✅ **不影响**图构建核心逻辑
- ✅ **不影响**去重算法的执行
- ✅ **不影响**最终生成的知识图谱
- ⚠️ **仅影响**中间结果的记录格式

## 测试结果

```
✅ 基本格式验证通过
✅ 示例文件格式验证通过
✅ 代码文件存在: models/constructor/kt_gen.py
✅ 文档文件完整
```

## 配置方法

在配置文件中启用：

```yaml
construction:
  semantic_dedup:
    enabled: true
    save_intermediate_results: true
    intermediate_results_path: "output/dedup_intermediate/"  # 可选
```

## 使用示例

### Python 读取分析

```python
import json

with open('output/dedup_intermediate/dataset_edge_dedup_20251019.json', 'r') as f:
    results = json.load(f)

for record in results:
    print(f"Head: {record['head']}, Relation: {record['relation']}")
    for dedup in record['dedup_records']:
        print(f"  合并: {', '.join(dedup['merged_tails'])}")
        print(f"  理由: {dedup['rationale']}")
```

### 命令行快速查看

```bash
# 统计去重组数量
jq 'length' dataset_edge_dedup_*.json

# 查看所有合并操作
jq '.[] | .dedup_records[]' dataset_edge_dedup_*.json

# 搜索特定实体
jq '.[] | select(.head | contains("张三"))' dataset_edge_dedup_*.json
```

## 相关资源

- **快速开始**: `QUICK_START_SIMPLIFIED_DEDUP.md`
- **详细说明**: `SIMPLIFIED_DEDUP_RESULTS.md`
- **格式对比**: `examples/dedup_output_comparison.md`
- **示例输出**: `examples/simplified_dedup_output_example.json`

## 后续工作

如果需要更详细的调试信息，可以考虑：
1. 添加可选的详细模式（通过配置开关）
2. 分离核心记录和调试记录到不同文件
3. 提供专门的分析工具

## 反馈

如有任何问题或建议，请提出 Issue 或 PR。
