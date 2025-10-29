# Tail去重工具与Youtu-GraphRAG对接指南

## 📋 概述

本指南帮助你将 Youtu-GraphRAG 生成的 `graph.json` 与 tail 去重结果对接，实现完整的去重流程。

## 🔄 完整工作流程

```
┌─────────────────┐
│  原始文档/数据   │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Youtu-GraphRAG  │ ← 构建初始知识图谱
│  构建知识图谱    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   graph.json    │ ← 原始图谱
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ semantic_dedup_ │ ← 你的去重处理
│     group       │    (识别重复的tail节点)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ dedup_results   │ ← 你处理得到的去重结果
│     .json       │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ 格式转换脚本     │ ← convert_dedup_format.py
│ (如果需要)      │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│apply_tail_dedup │ ← 应用去重结果到图谱
│   _results.py   │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│deduped_graph.json│ ← 最终去重后的图谱
└─────────────────┘
```

## 📁 你的数据格式

### 1. graph.json 格式

Youtu-GraphRAG 生成的 `graph.json` 格式如下：

```json
[
  {
    "start_node": {
      "label": "entity",
      "properties": {
        "name": "魔角效应",
        "chunk id": "Dwjxk2M8",
        "schema_type": "MRI伪影"
      }
    },
    "relation": "解决方案为",
    "end_node": {
      "label": "entity",
      "properties": {
        "name": "延长TE值",
        "chunk id": "Dwjxk2M8"
      }
    }
  }
]
```

### 2. 你的 dedup_results 格式

你通过 `semantic_dedup_group` 处理后得到的格式：

```json
[
  {
    "head_node": {
      "label": "entity",
      "properties": {
        "name": "魔角效应",
        "chunk id": "Dwjxk2M8",
        "schema_type": "MRI伪影"
      }
    },
    "relation": "解决方案为",
    "tail_nodes_to_dedup": [
      "延长TE值 (chunk id: Dwjxk2M8) [entity]",
      "改变扫描体位 (chunk id: Dwjxk2M8) [entity]",
      "增加TE值 (chunk id: PHuCr1nf) [entity]",
      "延长TE (chunk id: IwfMagF6) [entity]",
      "改变体位 (chunk id: IwfMagF6) [entity]"
    ],
    "dedup_results": {
      "cluster_0": {
        "member": [
          "增加TE值 (chunk id: PHuCr1nf) [entity]",
          "延长TE (chunk id: IwfMagF6) [entity]",
          "延长TE值 (chunk id: Dwjxk2M8) [entity]"
        ],
        "llm_judge_reason": "三条尾巴均指延长回波时间..."
      },
      "cluster_1": {
        "member": [
          "改变体位 (chunk id: IwfMagF6) [entity]",
          "改变扫描体位 (chunk id: Dwjxk2M8) [entity]"
        ],
        "llm_judge_reason": "改变扫描体位与改变体位指代同一操作..."
      }
    },
    "deduped_tails": [
      "改变扫描体位 (chunk id: Dwjxk2M8) [entity]",
      "延长TE值 (chunk id: Dwjxk2M8) [entity]"
    ]
  }
]
```

## ✅ 你的格式已经兼容！

**好消息**：你的 `dedup_results` 格式**完全符合**我的工具要求！可以直接使用。

## 🚀 快速开始（3步完成）

### 步骤1：准备文件

确保你有以下文件：

```bash
# 你的文件
output/graphs/original_graph.json     # Youtu-GraphRAG生成的图谱
your_dedup_results.json               # 你的去重结果

# 工具脚本（已创建）
apply_tail_dedup_results.py           # 去重应用脚本
```

### 步骤2：运行去重应用

```bash
python3 apply_tail_dedup_results.py \
    --graph output/graphs/original_graph.json \
    --dedup-results your_dedup_results.json \
    --output output/graphs/deduped_graph.json
```

### 步骤3：验证结果

```bash
# 查看统计信息（在步骤2的输出中）
# 检查输出文件
ls -lh output/graphs/deduped_graph.json
```

## 📝 详细使用示例

### 示例1：完整的Python脚本

```python
#!/usr/bin/env python3
"""
完整的去重流程示例
"""
import json
from pathlib import Path
from apply_tail_dedup_results import TailDedupApplicator
from utils import graph_processor

# 1. 加载原始图谱
print("1. 加载原始图谱...")
graph = graph_processor.load_graph_from_json('output/graphs/original_graph.json')
print(f"   原始图: {graph.number_of_nodes()} 节点, {graph.number_of_edges()} 边")

# 2. 加载去重结果
print("\n2. 加载去重结果...")
with open('your_dedup_results.json', 'r', encoding='utf-8') as f:
    dedup_results = json.load(f)
print(f"   去重组数: {len(dedup_results)}")

# 统计cluster信息
total_clusters = sum(len(g['dedup_results']) for g in dedup_results)
total_members = sum(
    len(cluster['member']) 
    for g in dedup_results 
    for cluster in g['dedup_results'].values()
)
print(f"   总cluster数: {total_clusters}")
print(f"   总成员数: {total_members}")

# 3. 应用去重
print("\n3. 应用去重...")
applicator = TailDedupApplicator(graph)
stats = applicator.apply_all(dedup_results)

# 4. 保存结果
print("\n4. 保存结果...")
output_path = 'output/graphs/deduped_graph.json'
Path(output_path).parent.mkdir(parents=True, exist_ok=True)
graph_processor.save_graph_to_json(graph, output_path)

# 5. 打印统计
print("\n" + "="*60)
print("去重统计:")
print("="*60)
for key, value in stats.items():
    print(f"  {key}: {value}")
print(f"\n  最终图: {graph.number_of_nodes()} 节点, {graph.number_of_edges()} 边")
print("="*60)
print(f"\n✅ 完成！结果已保存到: {output_path}")
```

### 示例2：验证去重结果

```python
#!/usr/bin/env python3
"""
验证去重结果的脚本
"""
import json
from utils import graph_processor

def verify_dedup(original_path, deduped_path, dedup_results_path):
    """验证去重是否正确应用"""
    
    # 加载图谱
    original = graph_processor.load_graph_from_json(original_path)
    deduped = graph_processor.load_graph_from_json(deduped_path)
    
    # 加载去重结果
    with open(dedup_results_path, 'r', encoding='utf-8') as f:
        dedup_results = json.load(f)
    
    print("="*60)
    print("去重验证报告")
    print("="*60)
    
    # 1. 图大小对比
    print("\n1. 图大小变化:")
    print(f"   节点: {original.number_of_nodes()} → {deduped.number_of_nodes()}")
    print(f"   边:   {original.number_of_edges()} → {deduped.number_of_edges()}")
    
    # 2. 检查代表节点是否存在
    print("\n2. 检查代表节点:")
    representatives = []
    for group in dedup_results:
        for cluster_name, cluster_data in group['dedup_results'].items():
            members = cluster_data['member']
            rep = members[-1]  # 最后一个是代表
            representatives.append(rep)
    
    found_count = 0
    for rep in representatives:
        # 解析节点标识符
        parts = rep.split(' (chunk id: ')
        if len(parts) == 2:
            name = parts[0]
            chunk_label = parts[1].split(') [')
            chunk_id = chunk_label[0]
            label = chunk_label[1].rstrip(']')
            
            # 在去重后的图中查找
            found = False
            for node_id, data in deduped.nodes(data=True):
                props = data.get('properties', {})
                if (props.get('name') == name and 
                    props.get('chunk id') == chunk_id and
                    data.get('label') == label):
                    found = True
                    found_count += 1
                    break
            
            if found:
                print(f"   ✅ {name} (chunk: {chunk_id})")
            else:
                print(f"   ❌ {name} (chunk: {chunk_id}) - 未找到！")
    
    print(f"\n   代表节点存在率: {found_count}/{len(representatives)} ({found_count/len(representatives)*100:.1f}%)")
    
    # 3. 检查是否有应该被删除的节点
    print("\n3. 检查被删除的节点:")
    should_remove = []
    for group in dedup_results:
        for cluster_name, cluster_data in group['dedup_results'].items():
            members = cluster_data['member']
            rep = members[-1]
            # 除了代表，其他都应该被删除
            for member in members[:-1]:
                should_remove.append(member)
    
    still_exists = 0
    for member in should_remove:
        parts = member.split(' (chunk id: ')
        if len(parts) == 2:
            name = parts[0]
            chunk_label = parts[1].split(') [')
            chunk_id = chunk_label[0]
            label = chunk_label[1].rstrip(']')
            
            # 检查是否还在图中
            for node_id, data in deduped.nodes(data=True):
                props = data.get('properties', {})
                if (props.get('name') == name and 
                    props.get('chunk id') == chunk_id and
                    data.get('label') == label):
                    still_exists += 1
                    print(f"   ⚠️  {name} (chunk: {chunk_id}) - 应该删除但仍存在")
                    break
    
    removed_count = len(should_remove) - still_exists
    print(f"\n   应删除节点: {len(should_remove)}")
    print(f"   已删除: {removed_count}")
    print(f"   删除率: {removed_count/len(should_remove)*100:.1f}%")
    
    # 4. 总结
    print("\n" + "="*60)
    if found_count == len(representatives) and still_exists == 0:
        print("✅ 验证通过！去重正确应用。")
    else:
        print("⚠️  验证发现问题，请检查上述详情。")
    print("="*60)

# 使用示例
verify_dedup(
    'output/graphs/original_graph.json',
    'output/graphs/deduped_graph.json',
    'your_dedup_results.json'
)
```

## 🔧 常见场景处理

### 场景1：你的 dedup_results 格式略有不同

如果你的格式稍有不同，可以使用转换脚本（见下一节）。

### 场景2：批量处理多个图谱

```python
#!/usr/bin/env python3
"""批量处理多个图谱"""
import glob
import json
from pathlib import Path
from apply_tail_dedup_results import TailDedupApplicator
from utils import graph_processor

# 去重结果（假设所有图谱使用相同的去重规则）
with open('common_dedup_results.json', 'r', encoding='utf-8') as f:
    dedup_results = json.load(f)

# 批量处理
for graph_file in glob.glob('output/graphs/*.json'):
    if 'deduped' in graph_file:
        continue  # 跳过已处理的
    
    print(f"\n处理: {graph_file}")
    
    # 加载并去重
    graph = graph_processor.load_graph_from_json(graph_file)
    applicator = TailDedupApplicator(graph)
    stats = applicator.apply_all(dedup_results)
    
    # 保存
    output_file = graph_file.replace('.json', '_deduped.json')
    graph_processor.save_graph_to_json(graph, output_file)
    
    print(f"  完成: {stats['edges_updated']} 边更新")
```

### 场景3：只处理特定类型的节点

```python
#!/usr/bin/env python3
"""只对entity类型的节点去重"""
import json
from apply_tail_dedup_results import TailDedupApplicator
from utils import graph_processor

# 过滤去重结果，只保留entity类型
with open('all_dedup_results.json', 'r', encoding='utf-8') as f:
    all_results = json.load(f)

# 只保留entity节点的去重
entity_results = []
for group in all_results:
    # 检查是否是entity类型
    if group['head_node']['label'] == 'entity':
        # 进一步检查cluster成员
        filtered_clusters = {}
        for cluster_name, cluster_data in group['dedup_results'].items():
            # 检查成员是否都是entity
            if all('[entity]' in member for member in cluster_data['member']):
                filtered_clusters[cluster_name] = cluster_data
        
        if filtered_clusters:
            group_copy = group.copy()
            group_copy['dedup_results'] = filtered_clusters
            entity_results.append(group_copy)

print(f"过滤后: {len(entity_results)} 组去重规则（只包含entity）")

# 应用去重
graph = graph_processor.load_graph_from_json('output/graphs/original_graph.json')
applicator = TailDedupApplicator(graph)
stats = applicator.apply_all(entity_results)

graph_processor.save_graph_to_json(graph, 'output/graphs/entity_deduped.json')
```

## 🔄 格式转换（如果需要）

如果你的格式需要调整，可以创建转换脚本。我会在下面提供通用的转换工具。

## ⚠️ 注意事项

### 1. 节点标识符格式

确保你的节点标识符格式为：
```
"name (chunk id: xxx) [label]"
```

例如：
```
"延长TE值 (chunk id: Dwjxk2M8) [entity]"
```

### 2. 代表节点必须存在

- cluster的最后一个成员会被用作代表
- 确保这个代表节点在原图中存在
- 如果不存在，会输出警告但继续处理

### 3. 备份原始文件

```bash
# 建议先备份
cp output/graphs/original_graph.json output/graphs/original_graph.json.backup
```

### 4. 检查日志输出

工具会输出详细日志，包括：
- 警告信息（如找不到代表节点）
- 处理进度
- 统计信息

## 📊 预期结果

运行后你会看到类似的输出：

```
[INFO] Loading graph from output/graphs/original_graph.json
[INFO] Original graph: 200 nodes, 350 edges
[INFO] Loading deduplication results from your_dedup_results.json
[INFO] Loaded 10 deduplication groups
[INFO] Building node mapping from deduplication results...
[INFO] Built mapping with 10 clusters and 35 total members
[INFO] Mapping entries: 35
[INFO] Applying deduplication to edges...
[INFO] Updated 25 edges
[INFO] Applying deduplication to communities...
[INFO] Updated 5 communities
[INFO] Deduplicated 8 community members
[INFO] Applying deduplication to keyword_filter_by relations...
[INFO] Updated 2 keyword_filter_by relations
[INFO] Removed 7 isolated nodes
============================================================
Deduplication Statistics:
  Total clusters processed: 10
  Total members in clusters: 35
  Edges updated: 25
  Communities updated: 5
  Community members deduplicated: 8
  Keyword_filter_by relations updated: 2
  Isolated nodes removed: 7
  Graph size: 200 → 193 nodes (7 removed)
  Graph edges: 350 → 325 edges (25 removed)
============================================================
[INFO] Deduplicated graph saved to output/graphs/deduped_graph.json
```

## 🐛 问题排查

### 问题1：找不到模块

```bash
# 确保在workspace目录下运行
cd /workspace

# 检查Python路径
python3 -c "import sys; print('\n'.join(sys.path))"
```

### 问题2：格式错误

```bash
# 验证JSON格式
python3 -c "import json; json.load(open('your_dedup_results.json'))"
```

### 问题3：没有效果（0更新）

可能原因：
- 节点标识符格式不匹配
- chunk id 不一致
- label名称不匹配

解决：运行验证脚本查看详细信息

## 📚 相关文档

- `APPLY_TAIL_DEDUP_README.md` - 快速入门
- `TAIL_DEDUP_APPLICATION_GUIDE.md` - 详细指南
- `TAIL_DEDUP_DETAILED_EXPLANATION.md` - 技术细节
- `visualize_tail_dedup_process.py` - 可视化演示

## 🎯 总结

你的数据格式已经兼容，只需要：

1. ✅ 确保有 `graph.json`（Youtu-GraphRAG输出）
2. ✅ 确保有 `dedup_results.json`（你的去重结果）
3. ✅ 运行 `apply_tail_dedup_results.py`
4. ✅ 检查输出和统计信息

就这么简单！🎉
