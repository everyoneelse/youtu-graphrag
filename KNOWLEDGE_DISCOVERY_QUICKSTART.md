# 知识发现快速开始 ⚡

## 5分钟快速体验

### 1️⃣ 运行示例程序

```bash
python example_knowledge_discovery.py
```

这将运行所有示例，展示知识发现的完整功能。

### 2️⃣ 查看输出结果

```bash
# 查看分析结果（JSON格式）
cat output/knowledge_discovery/knowledge_discovery_results.json

# 查看可视化图表
# output/knowledge_discovery/connectable_pairs_visualization.png
```

### 3️⃣ 使用自己的图谱

```python
from utils.knowledge_discovery import discover_and_reconstruct
from utils.graph_processor import load_graph_from_json, save_graph_to_json

# 加载你的图谱
graph = load_graph_from_json('your_graph.json')

# 执行知识发现
results = discover_and_reconstruct(
    graph=graph,
    output_dir='./output/my_discovery'
)

# 保存重构后的图谱
save_graph_to_json(
    results['reconstructed_graph'],
    'your_reconstructed_graph.json'
)

print(f"✅ 发现 {results['stats']['connectable_pairs_count']} 对可连接的三元组")
print(f"✅ 新增 {results['stats']['new_nodes']} 个节点")
print(f"✅ 新增 {results['stats']['new_edges']} 条边")
```

---

## 核心功能一览

### 🔍 三元组连接检测

自动发现可以连接的三元组对：

```
三元组1: ['化学位移伪影', '解决方案为', '采用高带宽']
三元组2: ['高带宽', '影响', '信噪比']
         └─────┬─────┘
              连接点
```

### 🎯 事件建模模式

将实体分解为三种类型：

| 类型 | 说明 | 示例 |
|------|------|------|
| **对象实体** | 核心概念 | 带宽、序列、剂量 |
| **状态实体** | 对象的状态 | 高带宽、快速序列、低剂量 |
| **动作实体** | 改变状态的动作 | 采用高带宽、提高信噪比、优化参数 |

### 🔄 知识图谱重构

自动添加新的关系：

```
原始:
  化学位移伪影 --解决方案为--> 采用高带宽
  高带宽 --影响--> 信噪比

重构后:
  化学位移伪影 --解决方案为--> 采用高带宽 (保留)
  采用高带宽 --作用于--> 带宽 (新增)
  带宽 --处于状态--> 高带宽 (新增)
  高带宽 --影响--> 信噪比 (保留)
```

---

## 实体分解示例

```python
from utils.knowledge_discovery import KnowledgeDiscovery

kd = KnowledgeDiscovery()

# 测试各种实体
print(kd.decompose_entity('高带宽'))
# → {'object': '带宽', 'state': '高带宽', 'type': 'state'}

print(kd.decompose_entity('采用高带宽'))
# → {'object': '高带宽', 'action': '采用高带宽', 'type': 'action'}

print(kd.decompose_entity('带宽'))
# → {'object': '带宽', 'type': 'object'}
```

---

## 常用API速查

### 便捷函数（推荐）

```python
from utils.knowledge_discovery import discover_and_reconstruct

results = discover_and_reconstruct(
    graph=your_graph,
    llm_client=None,  # 可选：传入LLM客户端
    output_dir='./output'  # 可选：输出目录
)
```

### 详细控制

```python
from utils.knowledge_discovery import KnowledgeDiscovery

kd = KnowledgeDiscovery()
kd.load_graph(graph)

# 步骤1：查找可连接的三元组
pairs = kd.find_connectable_triples()

# 步骤2：分解实体
for pair in pairs:
    entity = pair['overlap_entity']
    decomposition = kd.decompose_entity(entity)

# 步骤3：重构图谱
new_graph = kd.reconstruct_with_event_modeling(pairs)

# 步骤4：导出结果
kd.export_discovery_results(pairs, 'results.json')
```

---

## 自定义配置

### 添加自定义状态模式

```python
kd = KnowledgeDiscovery()

# 添加领域特定的状态模式
kd.state_patterns.extend([
    r'超高(.+)',     # 超高分辨率
    r'极低(.+)',     # 极低剂量
    r'超快(.+)',     # 超快扫描
])
```

### 添加自定义动作模式

```python
# 添加领域特定的动作模式
kd.action_patterns.extend([
    r'启用(.+)',     # 启用抑制
    r'禁用(.+)',     # 禁用补偿
    r'激活(.+)',     # 激活保护
])
```

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `utils/knowledge_discovery.py` | 核心模块代码 |
| `example_knowledge_discovery.py` | 完整示例程序（5个示例） |
| `README_KNOWLEDGE_DISCOVERY.md` | 详细文档 |
| `KNOWLEDGE_DISCOVERY_QUICKSTART.md` | 本快速开始指南 |

---

## 输出文件

运行后会生成以下文件：

```
output/
├── knowledge_discovery/
│   ├── knowledge_discovery_results.json  # 分析结果
│   └── connectable_pairs_visualization.png  # 可视化图表
├── example_graph.json  # 示例图谱
└── reconstructed_graph.json  # 重构后的图谱
```

---

## 典型应用场景

### 🏥 医学影像知识图谱
```
伪影 → 解决方案 → 参数设置 → 图像质量
```

### 💊 医疗诊疗知识图谱
```
疾病 → 治疗方法 → 药物剂量 → 治疗效果
```

### 📚 技术文档知识抽取
```
问题 → 解决方案 → 配置参数 → 系统性能
```

### 🏭 工业过程知识建模
```
工艺步骤 → 参数控制 → 质量指标 → 产品质量
```

---

## 疑难解答

### Q: 为什么没有找到可连接的三元组？

**A**: 可能的原因：
1. 图谱中的实体命名不一致
2. 三元组之间确实没有连接关系
3. 需要自定义连接检测逻辑

**解决方法**：
```python
# 可以先查看所有实体
for node, data in graph.nodes(data=True):
    if data.get('label') == 'entity':
        print(data['properties']['name'])
```

### Q: 如何处理多语言实体？

**A**: 添加相应语言的模式：
```python
# 英文模式
kd.state_patterns.extend([
    r'high (.+)',
    r'low (.+)',
])

kd.action_patterns.extend([
    r'using (.+)',
    r'increase (.+)',
])
```

### Q: 重构会修改原始图谱吗？

**A**: 不会！`reconstruct_with_event_modeling()` 返回新的图谱对象，原图谱保持不变。

---

## 性能提示

### 对于大规模图谱（10000+ 三元组）

1. **过滤特定关系类型**：
```python
# 只处理特定关系
filtered_graph = filter_by_relations(graph, ['解决方案为', '影响'])
results = discover_and_reconstruct(filtered_graph)
```

2. **分批处理**：
```python
# 按社区分批处理
for community in communities:
    subgraph = extract_subgraph(graph, community)
    results = discover_and_reconstruct(subgraph)
```

---

## 下一步

✅ **完成基本使用** → 运行 `example_knowledge_discovery.py`  
✅ **处理自己的数据** → 使用 `discover_and_reconstruct()`  
✅ **深入了解** → 阅读 `README_KNOWLEDGE_DISCOVERY.md`  
✅ **集成到项目** → 在知识图谱构建流程中调用  

---

## 获取帮助

- 📖 详细文档：`README_KNOWLEDGE_DISCOVERY.md`
- 💻 示例代码：`example_knowledge_discovery.py`
- 🐛 问题反馈：项目 Issue 页面

---

**祝使用愉快！🎉**
