# 语义去重中间结果简化变更说明

## 变更时间
2025-10-19

## 变更概述
简化了 `save_intermediate_results` 功能，使其只记录语义去重的核心信息，而不是所有的中间处理细节。

## 主要修改

### 1. 简化了数据结构

**之前**：复杂的嵌套结构，包含完整的候选列表、聚类详情、所有 LLM 调用记录等

**现在**：简洁的平面结构，只记录核心信息：

```json
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
```

### 2. 修改的函数

#### `_deduplicate_keyword_nodes` (第1154-1457行)
- 移除了 `candidates`、`clustering`、`llm_groups`、`final_merges` 等详细字段
- 只保留 `head`、`relation`、`dedup_records`
- 只在有实际合并操作时才保存记录

#### `_semantic_deduplicate_group` (第1513-1753行)
- 简化了边去重的中间结果记录
- 移除了所有候选项列表和聚类详情
- 只记录最终的合并操作

#### `triple_deduplicate_semantic` (第1770-1853行)
- 简化了最终保存的结果结构
- 移除了复杂的汇总统计信息

### 3. 输出文件

输出文件现在更加简洁：

- **关键词去重**：`{dataset}_keyword_dedup_{timestamp}.json`
- **边去重**：`{dataset}_edge_dedup_{timestamp}.json`

每个文件都是一个简单的数组，包含多个去重记录。

## 核心记录信息

每条去重记录包含：

1. **head**：进行去重的头实体或社区
2. **relation**：关系类型
3. **dedup_records**：去重操作列表
   - **merged_tails**：合并的所有 tail（第一个是代表性的）
   - **chunk_ids**：所有相关的 chunk ID（已排序）
   - **rationale**：LLM 的判断理由

## 优势

1. **文件更小**：去除了大量中间过程数据，文件大小显著减少
2. **更易读**：结构简单，一目了然
3. **易于分析**：可以快速查看每个去重决策
4. **保留关键信息**：所有必要的调试信息都保留了
   - 知道哪些实体被合并了（merged_tails）
   - 知道它们来自哪里（chunk_ids）
   - 知道为什么合并（rationale）

## 向后兼容性

此变更**不影**响图构建的核心逻辑，只是改变了中间结果的记录格式。

如果你之前依赖详细的中间结果进行分析，可能需要调整分析脚本。

## 使用方法

配置文件中启用：

```yaml
construction:
  semantic_dedup:
    enabled: true
    save_intermediate_results: true
    intermediate_results_path: "output/dedup_intermediate/"
```

## 相关文件

- `models/constructor/kt_gen.py`：主要修改文件
- `SIMPLIFIED_DEDUP_RESULTS.md`：详细的输出格式说明和示例
