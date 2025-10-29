# Tail Deduplication Results Application Tool

## 概述

这个工具用于将 `semantic_dedup_group` 处理后的tail去重结果应用到原始知识图谱中。它能够智能地替换聚类成员为代表节点，并处理图中的各种结构（三元组、社区、特殊关系等）。

## 文件说明

| 文件 | 说明 |
|------|------|
| `apply_tail_dedup_results.py` | 主脚本，应用tail去重结果到图谱 |
| `example_apply_tail_dedup.py` | 使用示例和演示 |
| `test_apply_tail_dedup.py` | 测试脚本，验证功能正确性 |
| `TAIL_DEDUP_APPLICATION_GUIDE.md` | 详细使用指南 |

## 快速开始

### 1. 准备去重结果

你的去重结果应该是一个JSON列表，格式如下：

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
    "tail_nodes_to_dedup": [...],
    "dedup_results": {
      "cluster_0": {
        "member": [
          "增加TE值 (chunk id: PHuCr1nf) [entity]",
          "延长TE (chunk id: IwfMagF6) [entity]",
          "延长TE值 (chunk id: Dwjxk2M8) [entity]"
        ],
        "llm_judge_reason": "..."
      }
    },
    "deduped_tails": [...]
  }
]
```

### 2. 运行去重应用

```bash
python3 apply_tail_dedup_results.py \
    --graph output/graphs/original.json \
    --dedup-results tail_dedup_results.json \
    --output output/graphs/deduped.json
```

### 3. 查看结果

脚本会输出详细的统计信息：

```
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
```

## 核心功能

### 1. 代表节点选择

**默认策略**：使用cluster的**最后一个成员**作为代表节点

```python
# 示例cluster
{
  "member": [
    "增加TE值 (chunk id: PHuCr1nf) [entity]",
    "延长TE (chunk id: IwfMagF6) [entity]",
    "延长TE值 (chunk id: Dwjxk2M8) [entity]"  # ← 这个是代表
  ]
}
```

所有成员都会被替换为 `"延长TE值 (chunk id: Dwjxk2M8) [entity]"`

### 2. 图结构处理

#### 三元组（Triples/Edges）
- 对每条边，如果tail节点在聚类中，替换为代表节点
- 自动去重，避免创建重复边

```python
# 原始：
魔角效应 --解决方案为--> 增加TE值
魔角效应 --解决方案为--> 延长TE
魔角效应 --解决方案为--> 延长TE值

# 去重后：
魔角效应 --解决方案为--> 延长TE值
```

#### 社区（Communities）
- 如果多个cluster成员都在同一个community中
- 全部替换为代表节点
- 自动去重community成员列表

```python
# 原始community成员：
[增加TE值, 延长TE, 延长TE值]

# 去重后：
[延长TE值]
```

#### 特殊关系（keyword_filter_by）
- 处理keyword过滤关系
- 与普通三元组类似的替换逻辑

### 3. 清理孤立节点

去重后自动清理：
- 没有入边和出边的节点
- 被替换后不再使用的节点

## 测试验证

运行测试脚本验证功能：

```bash
python3 test_apply_tail_dedup.py
```

测试包括：
- ✓ 节点数量减少
- ✓ 边数量减少
- ✓ 代表节点存在
- ✓ cluster成员被移除
- ✓ head节点的边正确
- ✓ community成员去重

## 技术细节

### 节点标识符解析

节点标识符格式：`"name (chunk id: xxx) [label]"`

```python
# 示例
"延长TE值 (chunk id: Dwjxk2M8) [entity]"
# 解析为：
# name: "延长TE值"
# chunk_id: "Dwjxk2M8"
# label: "entity"
```

### 映射构建

```python
# 从dedup_results构建映射
node_mapping = {
    "增加TE值 (chunk id: PHuCr1nf) [entity]": "延长TE值 (chunk id: Dwjxk2M8) [entity]",
    "延长TE (chunk id: IwfMagF6) [entity]": "延长TE值 (chunk id: Dwjxk2M8) [entity]",
    "延长TE值 (chunk id: Dwjxk2M8) [entity]": "延长TE值 (chunk id: Dwjxk2M8) [entity]",  # 代表映射到自己
}
```

### 边处理流程

```python
for each edge (u, v, relation):
    v_representative = get_representative(v)
    
    if v_representative != v:
        if not exists_edge(u, relation, v_representative):
            add_edge(u, relation, v_representative)
        remove_edge(u, relation, v)
```

## 注意事项

### 1. 代表节点必须存在

- 确保所有代表节点在原图中存在
- 脚本会警告找不到的代表节点
- 找不到时保持原节点不变

### 2. NetworkX MultiDiGraph

- 使用 `nx.MultiDiGraph` 允许多重边
- 同一对节点可以有多条不同relation的边
- 脚本会检查relation避免真正的重复

### 3. 节点标识符匹配

- 确保chunk id格式一致
- 确保label名称匹配（entity, keyword, community等）
- 确保name完全匹配（包括空格）

## 高级用法

### 自定义代表选择策略

修改 `TailDedupApplicator` 类：

```python
class CustomApplicator(TailDedupApplicator):
    def build_mapping_from_dedup_results(self, dedup_results):
        for group in dedup_results:
            for cluster_name, cluster_data in group['dedup_results'].items():
                members = cluster_data['member']
                
                # 使用第一个成员而不是最后一个
                representative = members[0]
                
                # 或使用自定义逻辑
                # representative = self._custom_selection(members)
                
                for member in members:
                    self.node_mapping[member] = representative
```

### 批量处理

```python
import glob
from pathlib import Path
from apply_tail_dedup_results import TailDedupApplicator
from utils import graph_processor
import json

# 加载去重结果
with open('dedup_results.json', 'r', encoding='utf-8') as f:
    dedup_results = json.load(f)

# 批量处理所有图
for graph_file in glob.glob('output/graphs/*.json'):
    print(f"Processing {graph_file}...")
    
    graph = graph_processor.load_graph_from_json(graph_file)
    applicator = TailDedupApplicator(graph)
    stats = applicator.apply_all(dedup_results)
    
    output_file = graph_file.replace('.json', '_deduped.json')
    graph_processor.save_graph_to_json(graph, output_file)
    
    print(f"  Updated {stats['edges_updated']} edges")
```

### 与离线去重集成

```bash
# 步骤1：运行semantic去重
python3 offline_semantic_dedup.py \
    --graph output/graphs/original.json \
    --chunks output/chunks/ \
    --output output/graphs/semantic_deduped.json

# 步骤2：应用tail去重（如果你有自定义的tail去重结果）
python3 apply_tail_dedup_results.py \
    --graph output/graphs/semantic_deduped.json \
    --dedup-results tail_dedup_results.json \
    --output output/graphs/fully_deduped.json
```

## 性能考虑

- **时间复杂度**：O(E)，其中E是边的数量
- **空间复杂度**：O(N + E)，其中N是节点数量
- **大图处理**：对于>100K节点的图，考虑分批处理
- **内存使用**：整个图会加载到内存中

## 问题排查

### 问题1：警告 "Representative node not found"

**原因**：代表节点在图中不存在

**解决**：
- 检查节点标识符格式
- 验证chunk id匹配
- 确认原图中有该节点

### 问题2：统计显示0更新

**原因**：节点标识符不匹配

**解决**：
- 检查dedup_results中的标识符格式
- 确认与图中节点的name、chunk id、label完全匹配

### 问题3：去重后仍有重复

**原因**：MultiDiGraph允许多重边

**解决**：
- 这是正常的（不同relation）
- 如需移除真正的重复，使用后处理脚本

## 示例场景

### 场景1：医学术语标准化

```
原始：
- 增加TE值 (不同来源)
- 延长TE (不同来源)
- 延长TE值 (标准术语)

去重后：
- 延长TE值 (统一使用标准术语)
```

### 场景2：社区成员整合

```
原始社区成员：
- [MR伪影A, MRI伪影B, MR伪影C]  # 都指同一类伪影

去重后：
- [MRI伪影B]  # 使用标准名称
```

## 输出解读

### 统计信息说明

```
Total clusters processed: 10           # 处理的聚类数量
Total members in clusters: 35          # 所有聚类的成员总数
Edges updated: 25                      # 更新的边数量
Communities updated: 5                 # 更新的社区数量
Community members deduplicated: 8      # 社区中去重的成员数
Keyword_filter_by relations updated: 2 # 更新的keyword关系数
Isolated nodes removed: 7              # 移除的孤立节点数
Graph size: 200 → 193 nodes           # 图的节点变化
Graph edges: 350 → 325 edges          # 图的边变化
```

## 贡献和反馈

如果遇到问题或有改进建议，请：
1. 查看测试脚本了解预期行为
2. 查看详细指南了解高级用法
3. 运行测试验证你的修改

## 总结

`apply_tail_dedup_results.py` 提供了一个强大的工具来应用tail去重结果到知识图谱：

- ✅ 自动替换cluster成员为代表节点
- ✅ 处理三元组、社区、特殊关系
- ✅ 智能去重，避免重复
- ✅ 清理孤立节点
- ✅ 详细的统计报告
- ✅ 完整的测试验证

使用这个工具可以有效地减少图谱冗余，提高知识表示的质量和一致性。
