# Graph.json去重应用工具 - 完成总结

## 已完成的工作

我已经为你创建了完整的工具集，用于将offline dedup的结果应用到原始graph.json文件中，使用representative代替duplicate。

## 创建的文件

### 1. 主要脚本

#### `apply_dedup_results.py` (11KB)
核心Python脚本，用于应用去重结果到graph.json。

**主要功能**：
- 加载关键词去重结果（keyword dedup）
- 加载边去重结果（edge dedup）  
- 构建node mapping和edge mapping
- 将duplicate节点/边替换为representative
- 保存去重后的图

**命令行参数**：
```bash
--graph          # 必需：输入的graph.json路径
--keyword-dedup  # 可选：关键词去重结果文件
--edge-dedup     # 可选：边去重结果文件
--output         # 必需：输出文件路径
--remove-isolated # 可选：删除孤立节点
```

### 2. 文档

#### `APPLY_DEDUP_RESULTS_README.md` (9.5KB)
详细的使用文档，包含：
- 功能说明
- 参数详解
- 工作原理
- 输入文件格式要求
- 使用示例
- 故障排除
- 性能优化建议

#### `QUICK_START_APPLY_DEDUP.md` (7KB)
快速开始指南，包含：
- 最常用的使用场景
- 命令示例
- 常见问题解答
- 完整工作流程

### 3. 示例脚本

#### `example_apply_dedup.sh` (2.8KB, 可执行)
Shell脚本示例，自动查找去重结果文件并应用。

**使用方法**：
```bash
./example_apply_dedup.sh
```

#### `example_apply_dedup_usage.py` (7.9KB)
Python代码示例，展示5种不同的使用场景：
1. 基本用法（应用两种去重）
2. 仅应用关键词去重
3. 仅应用边去重
4. 检查映射关系
5. 批量处理多个图

**使用方法**：
```bash
python example_apply_dedup_usage.py 1  # 运行示例1
```

## 使用方法

### 方法1：命令行（推荐）

```bash
python apply_dedup_results.py \
    --graph output/graphs/demo_new.json \
    --keyword-dedup output/dedup_intermediate/demo_dedup_20251021_120000.json \
    --edge-dedup output/dedup_intermediate/demo_edge_dedup_20251021_120000.json \
    --output output/graphs/demo_deduped.json
```

### 方法2：Shell脚本

```bash
# 编辑脚本设置文件路径
vim example_apply_dedup.sh

# 运行
./example_apply_dedup.sh
```

### 方法3：Python代码

```python
from pathlib import Path
from apply_dedup_results import DedupResultsApplier
from utils import graph_processor

applier = DedupResultsApplier()
applier.graph = graph_processor.load_graph_from_json("output/graphs/demo_new.json")
applier.load_keyword_dedup_results(Path("path/to/keyword_dedup.json"))
applier.load_edge_dedup_results(Path("path/to/edge_dedup.json"))
applier.apply_dedup_to_graph()
graph_processor.save_graph_to_json(applier.graph, "output/graphs/demo_deduped.json")
```

## 工作流程

```
┌─────────────────────────────┐
│ 1. 原始 graph.json          │
│    (包含重复的节点和边)      │
└──────────┬──────────────────┘
           │
           ├──────────────────────────────┐
           │                              │
┌──────────▼──────────────┐  ┌───────────▼────────────┐
│ 2a. Keyword Dedup 结果  │  │ 2b. Edge Dedup 结果    │
│     *_dedup_*.json      │  │     *_edge_dedup_*.json│
│                         │  │                        │
│  communities:           │  │  triples:              │
│    final_merges:        │  │    final_merges:       │
│      representative     │  │      representative    │
│      duplicates         │  │      duplicates        │
└──────────┬──────────────┘  └───────────┬────────────┘
           │                              │
           └──────────┬───────────────────┘
                      │
           ┌──────────▼──────────────────┐
           │ 3. apply_dedup_results.py   │
           │                             │
           │  - 构建映射关系              │
           │  - 删除duplicate节点        │
           │  - 重定向边                 │
           │  - 删除duplicate边          │
           └──────────┬──────────────────┘
                      │
           ┌──────────▼──────────────────┐
           │ 4. 去重后的 graph.json      │
           │    (使用representative)     │
           │                             │
           │  节点数减少                 │
           │  边数减少                   │
           │  图结构简化                 │
           └─────────────────────────────┘
```

## 核心逻辑

### 节点去重
```
对于每个 (duplicate_node, representative_node) 映射：
  1. 将 duplicate_node 的所有出边重定向到 representative_node
  2. 将 duplicate_node 的所有入边重定向到 representative_node  
  3. 删除 duplicate_node
```

### 边去重
```
对于每个 (head, relation, duplicate_tail) -> representative_tail 映射：
  1. 删除边 (head, relation, duplicate_tail)
  2. 如果不存在，创建边 (head, relation, representative_tail)
  3. 保留原始边的所有属性
```

## 输入文件要求

### 去重结果文件格式

你的去重结果文件应该包含 `final_merges` 字段：

**关键词去重结果**：
```json
{
  "dataset": "demo",
  "communities": [
    {
      "community_id": "...",
      "final_merges": [
        {
          "representative": {
            "node_id": "keyword_001",
            "description": "deep learning"
          },
          "duplicates": [
            {"node_id": "keyword_002", "description": "..."},
            {"node_id": "keyword_003", "description": "..."}
          ],
          "rationale": "..."
        }
      ]
    }
  ]
}
```

**边去重结果**：
```json
{
  "dataset": "demo",
  "triples": [
    {
      "head_id": "entity_123",
      "relation": "related_to",
      "final_merges": [
        {
          "representative": {
            "node_id": "entity_456",
            "description": "..."
          },
          "duplicates": [
            {"node_id": "entity_457", "description": "..."}
          ],
          "rationale": "..."
        }
      ]
    }
  ]
}
```

## 预期效果

运行后你会看到：

```
INFO: Loading graph from output/graphs/demo_new.json
INFO: Original graph: 1000 nodes, 5000 edges
INFO: Loading keyword dedup results from ...
INFO: Loaded 50 keyword node mappings from 10 communities
INFO: Loading edge dedup results from ...
INFO: Loaded 100 edge mappings from 30 triple groups
INFO: Applying deduplication results to graph...
INFO: Removed 50 duplicate keyword nodes, redirected 150 edges
INFO: Removed 100 duplicate edges, added 80 redirected edges
INFO: Final graph stats: 950 nodes, 4930 edges
INFO: Deduplication complete:
  Nodes: 1000 -> 950 (removed 50)
  Edges: 5000 -> 4930 (removed 70)
INFO: Deduplicated graph saved to output/graphs/demo_deduped.json
```

## 下一步操作

### 1. 准备去重结果文件

如果还没有去重结果文件，先运行：
```bash
python offline_semantic_dedup.py \
    --graph output/graphs/demo_new.json \
    --chunks output/chunks/demo.txt \
    --config config/base_config.yaml \
    --output temp.json
```

这会在配置的目录（默认`output/dedup_intermediate/`）生成去重结果文件。

### 2. 查找去重结果文件

```bash
# 查找关键词去重结果
find . -name "*_dedup_*.json" -not -name "*edge*"

# 查找边去重结果  
find . -name "*_edge_dedup_*.json"
```

### 3. 应用去重结果

```bash
python apply_dedup_results.py \
    --graph <你的graph.json路径> \
    --keyword-dedup <关键词去重结果路径> \
    --edge-dedup <边去重结果路径> \
    --output <输出路径>
```

### 4. 验证结果

```python
from utils import graph_processor

original = graph_processor.load_graph_from_json('output/graphs/demo_new.json')
deduped = graph_processor.load_graph_from_json('output/graphs/demo_deduped.json')

print(f'Original: {original.number_of_nodes()} nodes, {original.number_of_edges()} edges')
print(f'Deduped:  {deduped.number_of_nodes()} nodes, {deduped.number_of_edges()} edges')
```

## 注意事项

1. **环境要求**：需要Python 3.8+和networkx库
2. **文件匹配**：去重结果文件必须与graph.json对应
3. **备份数据**：建议先备份原始graph.json
4. **内存使用**：大型图（>100万边）可能需要较多内存
5. **幂等性**：不要对同一个图重复应用相同的去重结果

## 相关文件

- `APPLY_DEDUP_RESULTS_README.md` - 详细文档
- `QUICK_START_APPLY_DEDUP.md` - 快速开始
- `DEDUP_INTERMEDIATE_RESULTS.md` - 去重结果格式说明
- `offline_semantic_dedup.py` - 离线语义去重脚本

## 技术支持

如遇问题，请检查：

1. 去重结果文件格式是否正确
2. graph.json是否与去重结果对应
3. 是否有足够的内存
4. Python版本和依赖是否满足要求

---

**创建时间**: 2025-10-21  
**工具版本**: 1.0.0  
**状态**: ✅ 已完成并测试语法
