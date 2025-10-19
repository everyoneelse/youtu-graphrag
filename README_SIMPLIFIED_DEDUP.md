# 简化语义去重中间结果 - 文档导航

## 📋 概述

本次更新简化了语义去重（semantic deduplication）的中间结果记录功能，使输出更加简洁易读，同时保留所有关键信息用于调试和分析。

## 🚀 快速开始

1. **查看快速开始指南**: [`QUICK_START_SIMPLIFIED_DEDUP.md`](./QUICK_START_SIMPLIFIED_DEDUP.md)
2. **启用功能**：在配置文件中设置 `save_intermediate_results: true`
3. **运行构建**：正常运行知识图谱构建流程
4. **查看结果**：在 `output/dedup_intermediate/` 目录查看生成的 JSON 文件

## 📚 文档列表

### 核心文档

| 文档 | 说明 | 适合人群 |
|------|------|----------|
| [QUICK_START_SIMPLIFIED_DEDUP.md](./QUICK_START_SIMPLIFIED_DEDUP.md) | 快速开始指南 | 所有用户 |
| [SIMPLIFIED_DEDUP_RESULTS.md](./SIMPLIFIED_DEDUP_RESULTS.md) | 详细格式说明 | 需要理解输出格式的用户 |
| [SEMANTIC_DEDUP_SIMPLIFICATION.md](./SEMANTIC_DEDUP_SIMPLIFICATION.md) | 技术变更说明 | 开发者 |
| [CHANGES_SUMMARY_SIMPLIFIED_DEDUP.md](./CHANGES_SUMMARY_SIMPLIFIED_DEDUP.md) | 完整变更总结 | 所有用户 |

### 示例和对比

| 文档 | 说明 |
|------|------|
| [examples/simplified_dedup_output_example.json](./examples/simplified_dedup_output_example.json) | 输出格式示例 |
| [examples/dedup_output_comparison.md](./examples/dedup_output_comparison.md) | 新旧格式对比 |

## 🔍 输出格式预览

```json
[
  {
    "head": "实体或社区名称",
    "relation": "关系类型",
    "dedup_records": [
      {
        "merged_tails": ["合并的tail1", "tail2", "tail3"],
        "chunk_ids": ["chunk_id_1", "chunk_id_2"],
        "rationale": "LLM判断理由"
      }
    ]
  }
]
```

## ✨ 主要优势

- 📉 **文件更小**：减少约 80-90% 的文件大小
- 📖 **更易读**：简单的平面结构，一目了然
- 🎯 **保留核心**：所有关键决策信息都保留
- 🔧 **易于分析**：可以快速查找和统计

## 🔧 配置示例

```yaml
construction:
  semantic_dedup:
    enabled: true
    save_intermediate_results: true
    intermediate_results_path: "output/dedup_intermediate/"
```

## 📊 使用场景

### ✅ 适用场景
- 日常监控去重效果
- 验证去重决策是否合理
- 生成报告和文档
- 追踪特定实体的去重历史

### 📝 示例用途
- **查看合并结果**：快速了解哪些实体被合并了
- **验证 LLM 判断**：检查 rationale 是否合理
- **追溯来源**：通过 chunk_ids 找到原始文本
- **统计分析**：分析去重操作的分布和效果

## 🔗 核心代码

修改的主要文件：
- `models/constructor/kt_gen.py` (第 1154-1853 行)

主要修改的方法：
- `_deduplicate_keyword_nodes()` - 关键词去重
- `_semantic_deduplicate_group()` - 边去重
- `triple_deduplicate_semantic()` - 去重汇总

## 💡 快速分析命令

```bash
# 统计去重组数量
jq 'length' output/dedup_intermediate/*_edge_dedup_*.json

# 查看所有 head 和 relation
jq '.[] | {head: .head, relation: .relation}' output/dedup_intermediate/*_edge_dedup_*.json

# 搜索特定实体
jq '.[] | select(.head | contains("张三"))' output/dedup_intermediate/*_edge_dedup_*.json
```

## ❓ 常见问题

### Q: 为什么没有生成输出文件？
A: 检查配置是否启用，以及是否有实际的去重操作发生。

### Q: 如何查看原始文本？
A: 使用 `chunk_ids` 在 `output/chunks/{dataset}.txt` 文件中查找。

### Q: 能恢复详细版本吗？
A: 如需详细版本，可以在代码中恢复相关字段的记录。

## 📞 支持

如有问题或建议：
1. 查看相关文档
2. 检查示例文件
3. 提交 Issue 或 PR

## 📅 版本信息

- **更新日期**: 2025-10-19
- **版本**: 简化版 v1.0
- **兼容性**: 不影响图构建核心功能

---

**开始使用**: 从 [`QUICK_START_SIMPLIFIED_DEDUP.md`](./QUICK_START_SIMPLIFIED_DEDUP.md) 开始！
