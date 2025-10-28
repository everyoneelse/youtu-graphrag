# 快速开始：应用去重结果到Graph.json

## 概述

本指南帮助你快速使用 `apply_dedup_results.py` 工具，将已保存的semantic_dedup和keywords dedup结果应用到原始的graph.json文件中。

## 前提条件

1. 你已经通过offline dedup保存了去重结果文件：
   - 关键词去重结果：`*_dedup_*.json` (不包含"edge"字样)
   - 边去重结果：`*_edge_dedup_*.json`

2. 你有原始的graph.json文件

## 快速开始

### 方法1：使用命令行工具（推荐）

```bash
# 基本用法：应用两种去重
python apply_dedup_results.py \
    --graph output/graphs/demo_new.json \
    --keyword-dedup output/dedup_intermediate/demo_dedup_20251021_120000.json \
    --edge-dedup output/dedup_intermediate/demo_edge_dedup_20251021_120000.json \
    --output output/graphs/demo_deduped.json
```

### 方法2：使用Shell脚本

```bash
# 编辑脚本，设置正确的文件路径
vim example_apply_dedup.sh

# 运行脚本
./example_apply_dedup.sh
```

### 方法3：使用Python代码

```python
from pathlib import Path
from apply_dedup_results import DedupResultsApplier
from utils import graph_processor

# 初始化
applier = DedupResultsApplier()

# 加载原始图
applier.graph = graph_processor.load_graph_from_json("output/graphs/demo_new.json")

# 加载去重结果
applier.load_keyword_dedup_results(Path("output/dedup_intermediate/demo_dedup_*.json"))
applier.load_edge_dedup_results(Path("output/dedup_intermediate/demo_edge_dedup_*.json"))

# 应用去重
applier.apply_dedup_to_graph()

# 保存结果
graph_processor.save_graph_to_json(applier.graph, "output/graphs/demo_deduped.json")
```

## 常见使用场景

### 场景1：只应用关键词去重

```bash
python apply_dedup_results.py \
    --graph output/graphs/demo_new.json \
    --keyword-dedup output/dedup_intermediate/demo_dedup_*.json \
    --output output/graphs/demo_keyword_deduped.json
```

### 场景2：只应用边去重

```bash
python apply_dedup_results.py \
    --graph output/graphs/demo_new.json \
    --edge-dedup output/dedup_intermediate/demo_edge_dedup_*.json \
    --output output/graphs/demo_edge_deduped.json
```

### 场景3：去重后删除孤立节点

```bash
python apply_dedup_results.py \
    --graph output/graphs/demo_new.json \
    --keyword-dedup output/dedup_intermediate/demo_dedup_*.json \
    --edge-dedup output/dedup_intermediate/demo_edge_dedup_*.json \
    --output output/graphs/demo_deduped.json \
    --remove-isolated
```

## 查找去重结果文件

如果不知道去重结果文件的具体路径，可以使用以下命令查找：

```bash
# 查找关键词去重结果
find . -name "*_dedup_*.json" -not -name "*edge*" | sort -r

# 查找边去重结果
find . -name "*_edge_dedup_*.json" | sort -r
```

## 验证结果

应用去重后，你会看到类似以下的输出：

```
INFO: Original graph: 1000 nodes, 5000 edges
INFO: Loaded 50 keyword node mappings from 10 communities
INFO: Loaded 100 edge mappings from 30 triple groups
INFO: Removed 50 duplicate keyword nodes, redirected 150 edges
INFO: Removed 100 duplicate edges, added 80 redirected edges
INFO: Deduplication complete:
  Nodes: 1000 -> 950 (removed 50)
  Edges: 5000 -> 4930 (removed 70)
INFO: Deduplicated graph saved to output/graphs/demo_deduped.json
```

## 工作原理

脚本执行以下步骤：

1. **加载原始图**：读取graph.json文件
2. **构建映射**：
   - 节点映射：duplicate_node_id → representative_node_id
   - 边映射：(head, relation, duplicate_tail) → representative_tail
3. **应用去重**：
   - 删除duplicate节点，将其边重定向到representative
   - 删除duplicate边，创建到representative的新边
4. **保存结果**：输出去重后的graph.json

## 常见问题

### Q1: 去重结果文件在哪里？

**A**: 去重结果文件通常保存在以下位置：
- 默认：`output/dedup_intermediate/`
- 自定义：查看你的配置文件中的 `intermediate_results_path`

### Q2: 如何知道去重效果？

**A**: 查看日志输出，关注：
- `Removed X duplicate keyword nodes`
- `Removed X duplicate edges`
- `Nodes: X -> Y (removed Z)`

### Q3: 去重后图的结构会改变吗？

**A**: 是的，这是预期行为：
- Duplicate节点被删除
- Representative节点会获得更多连接
- 图的拓扑结构会简化

### Q4: 可以多次应用去重吗？

**A**: 建议只应用一次。如果需要多次去重：
1. 第一次应用去重结果
2. 在去重后的图上重新运行`offline_semantic_dedup.py`
3. 应用新的去重结果

### Q5: 去重会丢失数据吗？

**A**: 不会丢失重要数据：
- Duplicate节点的边会重定向到representative
- 边的属性会保留（如chunk_ids）
- 但duplicate节点本身会被删除

## 完整工作流程示例

```bash
# 步骤1：运行离线语义去重（如果还没有去重结果）
python offline_semantic_dedup.py \
    --graph output/graphs/demo_new.json \
    --chunks output/chunks/demo.txt \
    --config config/base_config.yaml \
    --output output/graphs/temp_deduped.json

# 注意：上述命令会保存中间结果到 output/dedup_intermediate/

# 步骤2：查找生成的去重结果文件
find output/dedup_intermediate -name "*demo*" -type f

# 步骤3：应用去重结果到原始图
python apply_dedup_results.py \
    --graph output/graphs/demo_new.json \
    --keyword-dedup output/dedup_intermediate/demo_dedup_*.json \
    --edge-dedup output/dedup_intermediate/demo_edge_dedup_*.json \
    --output output/graphs/demo_final_deduped.json

# 步骤4：验证结果
python -c "
from utils import graph_processor
import networkx as nx

original = graph_processor.load_graph_from_json('output/graphs/demo_new.json')
deduped = graph_processor.load_graph_from_json('output/graphs/demo_final_deduped.json')

print(f'Original: {original.number_of_nodes()} nodes, {original.number_of_edges()} edges')
print(f'Deduped:  {deduped.number_of_nodes()} nodes, {deduped.number_of_edges()} edges')
print(f'Reduction: {original.number_of_nodes() - deduped.number_of_nodes()} nodes, {original.number_of_edges() - deduped.number_of_edges()} edges')
"
```

## 下一步

- 查看 [APPLY_DEDUP_RESULTS_README.md](APPLY_DEDUP_RESULTS_README.md) 了解详细文档
- 查看 [example_apply_dedup_usage.py](example_apply_dedup_usage.py) 了解更多代码示例
- 查看 [DEDUP_INTERMEDIATE_RESULTS.md](DEDUP_INTERMEDIATE_RESULTS.md) 了解去重结果格式

## 需要帮助？

如果遇到问题，检查：

1. **文件路径是否正确**
   ```bash
   ls -lh output/graphs/demo_new.json
   ls -lh output/dedup_intermediate/
   ```

2. **去重结果文件格式是否正确**
   ```bash
   python -c "import json; print(json.load(open('output/dedup_intermediate/demo_dedup_*.json'))['dataset'])"
   ```

3. **Python环境是否正确**
   ```bash
   python --version  # 应该是 Python 3.8+
   pip list | grep networkx
   ```

## 相关工具

- `offline_semantic_dedup.py` - 执行语义去重
- `utils/graph_processor.py` - 图处理工具
- `example_analyze_dedup_results.py` - 分析去重结果
