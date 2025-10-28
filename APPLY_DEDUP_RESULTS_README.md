# 应用去重结果到Graph.json

## 概述

`apply_dedup_results.py` 脚本用于将离线语义去重（offline semantic deduplication）的结果应用到原始的 `graph.json` 文件中，使用 representative 节点/边代替 duplicate 节点/边。

## 功能

该脚本支持两种类型的去重结果：

1. **关键词节点去重** (Keyword Node Deduplication)
   - 读取 `*_dedup_*.json` 文件
   - 将重复的关键词节点合并到代表节点
   - 重定向所有相关的边

2. **三元组边去重** (Edge/Triple Deduplication)
   - 读取 `*_edge_dedup_*.json` 文件
   - 将重复的边（相同head和relation，但tail不同）合并
   - 使用representative tail替换duplicate tail

## 使用方法

### 基本用法

```bash
python apply_dedup_results.py \
    --graph output/graphs/demo_new.json \
    --keyword-dedup output/dedup_intermediate/demo_dedup_20251021_120000.json \
    --edge-dedup output/dedup_intermediate/demo_edge_dedup_20251021_120000.json \
    --output output/graphs/demo_deduped.json
```

### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `--graph` | ✓ | 输入的原始graph.json文件路径 |
| `--keyword-dedup` | ✗ | 关键词去重结果文件路径 |
| `--edge-dedup` | ✗ | 边去重结果文件路径 |
| `--output` | ✓ | 输出的去重后graph.json文件路径 |
| `--remove-isolated` | ✗ | 是否删除孤立节点（默认不删除） |

**注意**：`--keyword-dedup` 和 `--edge-dedup` 至少需要提供一个。

### 使用示例

#### 1. 仅应用关键词去重

```bash
python apply_dedup_results.py \
    --graph output/graphs/demo_new.json \
    --keyword-dedup output/dedup_intermediate/demo_dedup_20251021_120000.json \
    --output output/graphs/demo_keyword_deduped.json
```

#### 2. 仅应用边去重

```bash
python apply_dedup_results.py \
    --graph output/graphs/demo_new.json \
    --edge-dedup output/dedup_intermediate/demo_edge_dedup_20251021_120000.json \
    --output output/graphs/demo_edge_deduped.json
```

#### 3. 应用两种去重并删除孤立节点

```bash
python apply_dedup_results.py \
    --graph output/graphs/demo_new.json \
    --keyword-dedup output/dedup_intermediate/demo_dedup_20251021_120000.json \
    --edge-dedup output/dedup_intermediate/demo_edge_dedup_20251021_120000.json \
    --output output/graphs/demo_fully_deduped.json \
    --remove-isolated
```

## 工作原理

### 1. 加载去重结果

脚本从去重结果文件中提取 `final_merges` 信息：

**关键词去重**：
```json
{
  "representative": {
    "node_id": "keyword_001",
    "description": "deep learning"
  },
  "duplicates": [
    {"node_id": "keyword_002", "description": "deep neural networks"},
    {"node_id": "keyword_003", "description": "DNN"}
  ]
}
```

**边去重**：
```json
{
  "head_id": "entity_123",
  "relation": "related_to",
  "representative": {
    "node_id": "entity_456",
    "description": "deep learning"
  },
  "duplicates": [
    {"node_id": "entity_457", "description": "deep neural networks"}
  ]
}
```

### 2. 构建映射关系

- **节点映射**：`duplicate_node_id -> representative_node_id`
- **边映射**：`(head, relation, duplicate_tail) -> representative_tail`

### 3. 应用去重

#### 关键词节点去重流程：

1. 对于每个 duplicate 节点：
   - 将其所有出边重定向到 representative 节点
   - 将其所有入边重定向到 representative 节点
   - 删除 duplicate 节点

2. 避免创建重复边（检查是否已存在相同的边）

#### 边去重流程：

1. 对于每条 duplicate 边 `(head, relation, duplicate_tail)`:
   - 删除该边
   - 如果不存在 `(head, relation, representative_tail)` 边，则创建它
   - 保留原始边的所有属性

2. 合并边的属性（如 chunk_ids, weights 等）

### 4. 统计输出

脚本会输出详细的统计信息：

```
INFO: Original graph: 1000 nodes, 5000 edges
INFO: Loaded 50 keyword node mappings from 10 communities
INFO: Loaded 100 edge mappings from 30 triple groups
INFO: Removed 50 duplicate keyword nodes, redirected 150 edges
INFO: Removed 100 duplicate edges, added 80 redirected edges
INFO: Final graph stats: 950 nodes, 4930 edges
INFO: Deduplication complete:
  Nodes: 1000 -> 950 (removed 50)
  Edges: 5000 -> 4930 (removed 70)
```

## 输入文件格式要求

### 去重结果文件格式

去重结果文件应该是由 `offline_semantic_dedup.py` 生成的，包含以下结构：

**关键词去重结果** (`*_dedup_*.json`):
```json
{
  "dataset": "demo",
  "communities": [
    {
      "community_id": "...",
      "final_merges": [
        {
          "representative": {"node_id": "...", "description": "..."},
          "duplicates": [{"node_id": "...", "description": "..."}]
        }
      ]
    }
  ]
}
```

**边去重结果** (`*_edge_dedup_*.json`):
```json
{
  "dataset": "demo",
  "triples": [
    {
      "head_id": "...",
      "relation": "...",
      "final_merges": [
        {
          "representative": {"node_id": "...", "description": "..."},
          "duplicates": [{"node_id": "...", "description": "..."}]
        }
      ]
    }
  ]
}
```

## 注意事项

### 1. 数据一致性

- 确保去重结果文件与原始 graph.json 对应
- 去重结果中的节点ID必须存在于原始图中

### 2. 边的处理

- 脚本会保留所有边的属性（如 chunk_ids, weights）
- 如果多条边被合并到同一条边，后续可能需要手动合并属性

### 3. 孤立节点

- 默认情况下不删除孤立节点
- 使用 `--remove-isolated` 可以删除去重后产生的孤立节点

### 4. 性能考虑

- 对于大型图（>100万条边），处理可能需要几分钟
- 确保有足够的内存来加载整个图

## 与 offline_semantic_dedup.py 的区别

| 特性 | offline_semantic_dedup.py | apply_dedup_results.py |
|------|---------------------------|------------------------|
| 功能 | 执行语义去重并保存结果 | 应用已有的去重结果 |
| 需要LLM | 是 | 否 |
| 需要embeddings | 是 | 否 |
| 执行时间 | 长（需要调用LLM） | 短（只做图操作） |
| 适用场景 | 首次去重或调整参数 | 快速应用已有结果 |

## 工作流程推荐

### 场景1：首次去重

1. 使用 `offline_semantic_dedup.py` 执行去重并保存中间结果：
```bash
python offline_semantic_dedup.py \
    --graph output/graphs/demo_new.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_deduped.json \
    --config config/base_config.yaml \
    --save-intermediate-results
```

### 场景2：基于已有结果快速应用

1. 如果已有去重结果文件，直接应用：
```bash
python apply_dedup_results.py \
    --graph output/graphs/demo_new.json \
    --keyword-dedup output/dedup_intermediate/demo_dedup_*.json \
    --edge-dedup output/dedup_intermediate/demo_edge_dedup_*.json \
    --output output/graphs/demo_deduped.json
```

### 场景3：增量去重

1. 先应用之前的去重结果：
```bash
python apply_dedup_results.py \
    --graph output/graphs/demo_new.json \
    --keyword-dedup results/old_dedup.json \
    --output output/graphs/demo_partial_deduped.json
```

2. 在部分去重的基础上继续去重：
```bash
python offline_semantic_dedup.py \
    --graph output/graphs/demo_partial_deduped.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_fully_deduped.json
```

## 故障排除

### 问题1：找不到节点ID

**错误信息**：
```
WARNING: Node 'keyword_123' not found in graph, skipping...
```

**解决方法**：
- 检查去重结果文件是否与graph.json匹配
- 确认graph.json是用于生成去重结果的原始图

### 问题2：边数量增加

**原因**：
- 重定向边时可能创建新的边
- 这是正常的，因为将多个duplicate的边合并到representative

**验证**：
- 检查日志中的 "redirected edges" 数量
- 确认最终边数 = 原始边数 - 删除边数 + 新增边数

### 问题3：图结构改变

**原因**：
- 去重会改变图的拓扑结构
- representative节点会获得更多的连接

**验证**：
- 使用图分析工具检查去重前后的图统计
- 确认重要节点的连接没有丢失

## 扩展功能

### 自定义去重逻辑

可以继承 `DedupResultsApplier` 类并重写方法：

```python
class CustomApplier(DedupResultsApplier):
    def apply_dedup_to_graph(self):
        # 自定义去重逻辑
        super().apply_dedup_to_graph()
        # 额外的处理
        self._merge_edge_attributes()
    
    def _merge_edge_attributes(self):
        # 合并重复边的属性
        pass
```

### 批处理多个图

```bash
#!/bin/bash
for graph in output/graphs/*.json; do
    base=$(basename "$graph" .json)
    python apply_dedup_results.py \
        --graph "$graph" \
        --keyword-dedup "results/${base}_dedup.json" \
        --edge-dedup "results/${base}_edge_dedup.json" \
        --output "output/deduped/${base}_deduped.json"
done
```

## 日志说明

脚本会输出详细的日志信息：

- `INFO`: 主要流程和统计信息
- `DEBUG`: 每个映射的详细信息（需要设置日志级别）
- `WARNING`: 潜在问题（如节点未找到）

启用DEBUG日志：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 性能优化

对于大型图，可以考虑：

1. 使用批处理模式
2. 增加内存限制
3. 使用并行处理（未来版本）

## 相关文档

- [DEDUP_INTERMEDIATE_RESULTS.md](DEDUP_INTERMEDIATE_RESULTS.md) - 去重中间结果说明
- [offline_semantic_dedup.py](offline_semantic_dedup.py) - 离线语义去重脚本
- [utils/graph_processor.py](utils/graph_processor.py) - 图处理工具
