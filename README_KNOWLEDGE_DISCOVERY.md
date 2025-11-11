# 知识发现模块 - Knowledge Discovery Module

## 概述

知识发现模块用于优化和重构知识图谱中的三元组，通过识别可连接的三元组并应用事件建模模式（Event Modeling Pattern）来提升知识表示的质量。

## 核心功能

### 1. 三元组连接检测

自动识别知识图谱中可以连接的三元组对，例如：
- **三元组1**: `['化学位移伪影', '解决方案为', '采用高带宽']`
- **三元组2**: `['高带宽', '影响', '信噪比']`

这两个三元组可以连接，因为第一个的尾实体"采用高带宽"与第二个的头实体"高带宽"相关。

### 2. 事件建模模式

将实体分解为三种类型：

#### 对象实体 (Object Entity)
- 代表核心概念或事物
- 示例：`带宽`、`序列`、`剂量`

#### 状态实体 (State Entity)
- 描述对象的状态或属性
- 模式：`高X`、`低X`、`快X`、`慢X`等
- 示例：`高带宽`、`低剂量`、`快速序列`

#### 动作实体 (Action Entity)
- 描述改变对象状态的动作
- 模式：`采用X`、`提高X`、`降低X`、`优化X`等
- 示例：`采用高带宽`、`提高信噪比`、`优化参数`

### 3. 知识图谱重构

基于事件建模模式，自动添加新的实体和关系：

**原始三元组**：
```
化学位移伪影 --解决方案为--> 采用高带宽
高带宽 --影响--> 信噪比
```

**重构后**：
```
化学位移伪影 --解决方案为--> 采用高带宽 (保留)
采用高带宽 --作用于--> 带宽 (新增)
带宽 --处于状态--> 高带宽 (新增)
高带宽 --影响--> 信噪比 (保留)
```

## 使用方法

### 快速开始

```python
from utils.knowledge_discovery import discover_and_reconstruct
from utils.graph_processor import load_graph_from_json

# 加载知识图谱
graph = load_graph_from_json('path/to/your/graph.json')

# 执行知识发现和重构
results = discover_and_reconstruct(
    graph=graph,
    output_dir='./output/knowledge_discovery'
)

# 查看结果
print(f"发现 {results['stats']['connectable_pairs_count']} 对可连接的三元组")
print(f"新增 {results['stats']['new_nodes']} 个节点")
print(f"新增 {results['stats']['new_edges']} 条边")
```

### 详细使用

```python
from utils.knowledge_discovery import KnowledgeDiscovery

# 初始化
kd = KnowledgeDiscovery()
kd.load_graph(graph)

# 1. 查找可连接的三元组
connectable_pairs = kd.find_connectable_triples()

# 2. 分析实体类型
for pair in connectable_pairs:
    entity = pair['overlap_entity']
    decomposition = kd.decompose_entity(entity)
    print(f"实体: {entity}")
    print(f"类型: {decomposition['type']}")
    print(f"对象: {decomposition['object']}")

# 3. 重构图谱
reconstructed_graph = kd.reconstruct_with_event_modeling(connectable_pairs)

# 4. 导出结果
kd.export_discovery_results(
    connectable_pairs,
    './output/discovery_results.json'
)
```

### 使用LLM增强分析（可选）

```python
from utils.call_llm_api import LLM
from config import get_config

# 初始化LLM客户端
config = get_config()
llm_client = LLM(config=config)

# 使用LLM进行智能分析
results = discover_and_reconstruct(
    graph=graph,
    llm_client=llm_client,
    output_dir='./output/knowledge_discovery_llm'
)
```

## 运行示例

项目提供了完整的示例程序：

```bash
python example_knowledge_discovery.py
```

示例包括：
1. 基本使用方法
2. 导出分析结果
3. 实体分解示例
4. 使用自定义图谱
5. LLM增强分析

## 输出文件

知识发现模块会生成以下文件：

### knowledge_discovery_results.json
```json
{
  "total_pairs": 3,
  "pairs": [
    {
      "triple1": ["化学位移伪影", "解决方案为", "采用高带宽"],
      "triple2": ["高带宽", "影响", "信噪比"],
      "overlap_entity": "高带宽",
      "decomposition": {
        "object": "带宽",
        "state": "高带宽",
        "action": null,
        "type": "state"
      }
    }
  ]
}
```

### connectable_pairs_visualization.png
可视化图表，展示可连接的三元组对及其分解结果。

## 配置选项

### 自定义状态模式

```python
kd = KnowledgeDiscovery()

# 添加自定义状态模式
kd.state_patterns.extend([
    r'超高(.+)',
    r'极低(.+)',
    # 更多模式...
])
```

### 自定义动作模式

```python
# 添加自定义动作模式
kd.action_patterns.extend([
    r'启用(.+)',
    r'禁用(.+)',
    # 更多模式...
])
```

## 应用场景

### 1. MR伪影知识图谱优化
- 识别伪影、解决方案、参数之间的关系
- 明确参数的状态和调整动作

### 2. 医疗知识图谱构建
- 疾病、症状、治疗方案的关系建模
- 药物、剂量、效果的事件建模

### 3. 技术文档知识抽取
- 问题、解决方案、配置的关系链
- 参数、设置、影响的因果建模

## 技术原理

### 连接检测算法

1. **完全匹配**：尾实体 == 头实体
2. **包含关系**：尾实体包含头实体，或反之
3. **核心概念匹配**：提取核心概念后进行匹配

### 实体分解规则

1. **状态识别**：匹配状态修饰词模式（高、低、大、小等）
2. **动作识别**：匹配动作动词模式（采用、提高、降低等）
3. **对象提取**：去除状态修饰词和动作动词后的核心概念

### 重构策略

**对于状态实体**：
```
原始: [A] --关系--> [高X]
重构: [A] --关系--> [高X]
      [X] --处于状态--> [高X]
```

**对于动作实体**：
```
原始: [A] --关系--> [采用X]
重构: [A] --关系--> [采用X]
      [采用X] --作用于--> [X]
```

## API 参考

### KnowledgeDiscovery 类

#### `__init__(llm_client=None)`
初始化知识发现模块。

**参数**：
- `llm_client`: LLM客户端（可选），用于语义分析

#### `load_graph(graph)`
加载知识图谱。

**参数**：
- `graph`: NetworkX MultiDiGraph 对象

#### `find_connectable_triples()`
查找可连接的三元组对。

**返回**：可连接的三元组对列表

#### `decompose_entity(entity)`
将实体分解为对象、状态、动作。

**参数**：
- `entity`: 实体名称

**返回**：分解结果字典

#### `reconstruct_with_event_modeling(connectable_pairs)`
使用事件建模模式重构图谱。

**参数**：
- `connectable_pairs`: 可连接的三元组对列表

**返回**：重构后的知识图谱

#### `export_discovery_results(connectable_pairs, output_path)`
导出知识发现结果。

**参数**：
- `connectable_pairs`: 可连接的三元组对列表
- `output_path`: 输出文件路径

### discover_and_reconstruct 函数

便捷函数，一次性完成知识发现和重构。

```python
discover_and_reconstruct(
    graph,              # 知识图谱
    llm_client=None,    # LLM客户端（可选）
    output_dir=None     # 输出目录（可选）
)
```

**返回**：
```python
{
    'connectable_pairs': [...],      # 可连接的三元组对
    'reconstructed_graph': graph,    # 重构后的图谱
    'stats': {...}                   # 统计信息
}
```

## 性能考虑

- **时间复杂度**：O(n²)，其中n是三元组数量
- **空间复杂度**：O(n)
- **优化建议**：
  - 对于大规模图谱，可以先过滤特定关系类型
  - 使用并行处理加速连接检测
  - 启用缓存避免重复计算

## 常见问题

### Q: 如何处理多语言实体？
A: 可以扩展 `state_patterns` 和 `action_patterns` 以支持其他语言的模式。

### Q: LLM分析是必需的吗？
A: 不是，LLM分析是可选的增强功能，基本功能不依赖LLM。

### Q: 如何自定义连接检测逻辑？
A: 可以继承 `KnowledgeDiscovery` 类并重写 `_can_connect` 方法。

### Q: 重构会修改原始图谱吗？
A: 不会，`reconstruct_with_event_modeling` 返回新的图谱对象，原图谱不变。

## 版本历史

- **v1.0** (2025-11-04)
  - 初始版本
  - 实现三元组连接检测
  - 实现事件建模模式
  - 支持可视化和导出

## 许可证

本模块遵循项目主许可证。

## 贡献

欢迎提交Issue和Pull Request！

## 联系方式

如有问题，请通过项目Issue页面联系。
