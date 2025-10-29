# 🚀 快速上手：对接你的去重结果

## ⚡ 重要更新

现在支持**全图去重**！不仅替换tail位置的节点，也替换head位置的节点。
无论待去重节点出现在三元组的哪个位置，都会被正确替换为代表节点。

详见：[`FULL_GRAPH_DEDUP_EXPLANATION.md`](FULL_GRAPH_DEDUP_EXPLANATION.md)

## 一分钟快速对接

你的数据格式**已经兼容**！只需3步：

### 步骤1：验证格式

```bash
python3 verify_dedup_results_format.py your_dedup_results.json
```

### 步骤2：应用去重

```bash
python3 apply_tail_dedup_results.py \
    --graph output/graphs/original.json \
    --dedup-results your_dedup_results.json \
    --output output/graphs/deduped.json
```

### 步骤3：查看结果

输出会显示详细统计，例如：
```
Deduplication Statistics:
  Total clusters processed: 10
  Edges updated: 25
  Graph size: 200 → 193 nodes
```

---

## 完整工作流（推荐）

使用一键式脚本完成所有步骤：

```bash
python3 complete_dedup_workflow.py \
    output/graphs/original.json \
    your_dedup_results.json \
    output/graphs/deduped.json
```

这个脚本会：
- ✅ 验证输入文件
- ✅ 分析原始图谱
- ✅ 分析去重结果
- ✅ 应用去重
- ✅ 打印详细报告
- ✅ 保存结果

---

## 你的数据格式

### ✅ 你有的：graph.json

Youtu-GraphRAG 输出格式：
```json
[
  {
    "start_node": {
      "label": "entity",
      "properties": {"name": "...", "chunk id": "..."}
    },
    "relation": "...",
    "end_node": {
      "label": "entity",
      "properties": {"name": "...", "chunk id": "..."}
    }
  }
]
```

### ✅ 你有的：dedup_results.json

你的去重结果格式（已兼容！）：
```json
[
  {
    "head_node": {...},
    "relation": "...",
    "dedup_results": {
      "cluster_0": {
        "member": [
          "node1 (chunk id: xxx) [entity]",
          "node2 (chunk id: yyy) [entity]",
          "representative (chunk id: zzz) [entity]"
        ]
      }
    }
  }
]
```

**关键点**：
- 最后一个member是代表节点
- 格式：`"name (chunk id: xxx) [label]"`

---

## 常见问题

### Q1: 我的格式对吗？

运行验证脚本：
```bash
python3 verify_dedup_results_format.py your_dedup_results.json
```

### Q2: 怎么知道去重成功了？

看统计输出：
- `Edges updated` > 0
- `Graph size` 减少
- 没有警告信息

### Q3: 如何检查具体的代表节点？

```python
import json
with open('your_dedup_results.json', 'r') as f:
    data = json.load(f)

for group in data:
    for cluster_name, cluster_data in group['dedup_results'].items():
        members = cluster_data['member']
        print(f"代表节点: {members[-1]}")  # 最后一个
```

### Q4: 去重结果不理想怎么办？

检查：
1. 代表节点是否在原图中存在
2. chunk id 是否匹配
3. 节点标识符格式是否正确

---

## 文件清单

| 文件 | 用途 | 必需 |
|------|------|------|
| `apply_tail_dedup_results.py` | 核心去重脚本 | ✅ |
| `verify_dedup_results_format.py` | 格式验证 | 推荐 |
| `complete_dedup_workflow.py` | 一键式工作流 | 推荐 |
| `test_apply_tail_dedup.py` | 测试脚本 | 可选 |
| `visualize_tail_dedup_process.py` | 可视化演示 | 可选 |

---

## 详细文档

- 📖 `INTEGRATION_GUIDE.md` - 完整对接指南
- 📖 `APPLY_TAIL_DEDUP_README.md` - 工具说明
- 📖 `TAIL_DEDUP_APPLICATION_GUIDE.md` - 详细用法
- 📖 `TAIL_DEDUP_DETAILED_EXPLANATION.md` - 技术细节

---

## 示例命令

### 基本用法
```bash
python3 apply_tail_dedup_results.py \
    --graph my_graph.json \
    --dedup-results my_dedup.json \
    --output deduped_graph.json
```

### 验证格式
```bash
python3 verify_dedup_results_format.py my_dedup.json
```

### 完整工作流
```bash
python3 complete_dedup_workflow.py \
    my_graph.json \
    my_dedup.json \
    deduped_graph.json
```

### 运行测试
```bash
python3 test_apply_tail_dedup.py
```

### 查看演示
```bash
python3 visualize_tail_dedup_process.py
```

---

## 预期结果示例

```
============================================================
Deduplication Statistics:
  Total clusters processed: 2
  Total members in clusters: 5
  Edges updated: 3
  Communities updated: 1
  Community members deduplicated: 2
  Keyword_filter_by relations updated: 0
  Isolated nodes removed: 3
  Graph size: 7 → 4 nodes (3 removed)
  Graph edges: 8 → 3 edges (5 removed)
============================================================
```

---

## 立即开始！

1. **验证你的格式**
   ```bash
   python3 verify_dedup_results_format.py your_dedup_results.json
   ```

2. **运行去重**
   ```bash
   python3 complete_dedup_workflow.py \
       output/graphs/original.json \
       your_dedup_results.json \
       output/graphs/deduped.json
   ```

3. **检查结果**
   - 查看输出统计
   - 对比原图和去重图
   - 在下游任务中使用去重图

---

## 需要帮助？

- 查看详细文档：`INTEGRATION_GUIDE.md`
- 运行测试验证：`python3 test_apply_tail_dedup.py`
- 查看可视化：`python3 visualize_tail_dedup_process.py`

**祝你使用愉快！** 🎉
