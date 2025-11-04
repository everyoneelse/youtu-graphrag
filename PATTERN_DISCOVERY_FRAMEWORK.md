# 知识图谱模式发现框架 🎯

## 为什么需要通用框架？

### ❌ 问题：Case-by-Case 的硬编码方案

之前的实现基于**文本模式匹配**：
```python
# 硬编码的状态模式
state_patterns = [r'高(.+)', r'低(.+)', r'快(.+)', r'慢(.+)']

# 硬编码的动作模式
action_patterns = [r'采用(.+)', r'提高(.+)', r'降低(.+)']
```

**局限性**：
- 🚫 只适用于特定案例（MR伪影示例）
- 🚫 无法处理其他领域的模式
- 🚫 依赖于实体的命名规范
- 🚫 不考虑图的结构特征
- 🚫 难以扩展和维护
- 🚫 无法从数据中学习新模式

### ✅ 解决方案：通用模式发现框架

基于**图结构分析**的专业框架：

```python
# 使用通用框架
from utils.kg_pattern_discovery import discover_and_optimize

results = discover_and_optimize(
    graph=your_graph,
    output_dir='./output',
    use_llm=False  # 可选LLM增强
)
```

**优势**：
- ✅ 基于图结构，不依赖文本
- ✅ 支持多种知识图谱设计模式
- ✅ 完全可配置和可扩展
- ✅ 可选的LLM驱动智能发现
- ✅ 专业和可持续
- ✅ 适用于任何领域

---

## 核心设计原则

### 1. 基于图结构，而非文本

**旧方法**：
```python
if re.match(r'高(.+)', entity_name):
    # 识别为状态实体
```

**新方法**：
```python
# 分析图的拓扑结构
if has_chain_structure(nodes):
    # 识别为链式模式
```

### 2. 支持多种设计模式

不仅仅是"事件模式"，还支持：
- **Chain Pattern** (链式模式) - A→B→C传递关系
- **Star Pattern** (星型模式) - 中心节点连接多个节点
- **Reification Pattern** (具体化模式) - 关系转实体
- **Hierarchy Pattern** (层次模式) - is-a, part-of关系
- **Temporal Pattern** (时间模式) - 带时间维度
- **Custom Patterns** (自定义模式) - 用户定义

### 3. 可配置的模式定义

使用YAML配置文件：
```yaml
patterns:
  chain_pattern:
    enabled: true
    params:
      min_chain_length: 2
      max_chain_length: 5
      confidence_threshold: 0.5
```

### 4. 基于LLM的语义理解

可选的智能分析：
```python
engine = PatternDiscoveryEngine(llm_client=llm)
pattern_matches = engine.discover_patterns(graph)
```

### 5. 从数据中学习模式

LLM可以发现新的、未预定义的模式。

---

## 支持的设计模式

### 🔗 1. Chain Pattern (链式模式)

**定义**：检测 A→B→C 的链式连接

**应用场景**：
- 因果链：原因 → 中间状态 → 结果
- 过程链：输入 → 处理 → 输出
- 传递关系：A影响B，B影响C

**示例**：
```
化学位移伪影 --解决方案为--> 采用高带宽 --设置为--> 高带宽 --影响--> 信噪比
```

**重构建议**：
- 添加快捷边（如果链很长）
- 识别关键中间节点

**配置**：
```yaml
chain_pattern:
  enabled: true
  params:
    min_chain_length: 2
    max_chain_length: 5
    add_shortcut_edges: true
```

---

### ⭐ 2. Star Pattern (星型模式)

**定义**：一个中心节点连接多个周边节点

**应用场景**：
- 实体属性聚合
- 概念关系网络
- 分类中心

**示例**：
```
                    对比度
                      ↑
        扫描时间 ← T1序列 → 空间分辨率
                      ↓
                   信噪比
```

**重构建议**：
- 合并相同关系为集合
- 分析周边节点之间的关系

**配置**：
```yaml
star_pattern:
  enabled: true
  params:
    min_neighbors: 3
    consolidate_collections: false
```

---

### 🔄 3. Reification Pattern (具体化模式)

**定义**：将关系转化为实体（当关系需要携带属性时）

**应用场景**：
- 带时间的关系
- 带条件的关系
- 需要量化的关系

**示例**：
```
原始: A --关系1--> B
      A --关系2--> B
      A --关系3--> B

具体化后:
      A --has_relation--> [关系实体] --points_to--> B
                            ↓
                      [属性1, 属性2, ...]
```

**配置**：
```yaml
reification_pattern:
  enabled: true
  params:
    min_edges_for_reification: 2
    auto_reify: false
```

---

### 🤖 4. LLM-Driven Pattern (LLM驱动模式)

**定义**：使用LLM自动发现和理解模式

**优势**：
- 不需要预定义规则
- 理解语义而非仅结构
- 可以发现新的模式类型

**工作流程**：
1. 提取有趣的子图
2. 转换为自然语言描述
3. LLM分析模式
4. 提供重构建议

**配置**：
```yaml
llm_driven_pattern:
  enabled: true  # 需要LLM支持
  params:
    max_subgraphs: 20
    confidence_threshold: 0.7
```

---

## 使用方法

### 快速开始

```python
from utils.kg_pattern_discovery import discover_and_optimize

# 一行代码完成模式发现和优化！
results = discover_and_optimize(
    graph=your_graph,
    output_dir='./output/pattern_discovery',
    use_llm=False  # 或 True（需要LLM支持）
)

print(f"发现 {results['stats']['total_pattern_matches']} 个模式")
print(f"优化后: {results['stats']['optimized_nodes']} 个节点")
```

### 详细控制

```python
from utils.kg_pattern_discovery import PatternDiscoveryEngine

# 初始化引擎
engine = PatternDiscoveryEngine(llm_client=None)

# 发现模式
pattern_matches = engine.discover_patterns(graph)

# 查看结果
for pattern_name, matches in pattern_matches.items():
    print(f"{pattern_name}: {len(matches)} 个匹配")
    for match in matches:
        print(f"  置信度: {match.confidence:.2f}")
        print(f"  建议: {match.recommendation}")

# 应用转换
optimized_graph = engine.apply_transformations(graph, pattern_matches)
```

### 使用配置文件

```python
import yaml

# 加载配置
with open('config/pattern_discovery_config.yaml') as f:
    config = yaml.safe_load(f)

# 根据配置初始化
engine = PatternDiscoveryEngine()
if config['patterns']['chain_pattern']['enabled']:
    # 使用配置的参数
    pass
```

---

## 架构设计

### 类层次结构

```
KGPattern (抽象基类)
    ├── ChainPattern
    ├── StarPattern
    ├── ReificationPattern
    ├── LLMDrivenPatternDiscovery
    └── CustomPattern (用户扩展)

PatternDiscoveryEngine
    ├── 模式注册
    ├── 批量检测
    ├── 冲突解决
    └── 批量转换
```

### 扩展新模式

```python
from utils.kg_pattern_discovery import KGPattern, PatternMatch

class MyCustomPattern(KGPattern):
    def __init__(self):
        super().__init__("My Pattern", "描述")
    
    def detect(self, graph, **kwargs):
        # 实现检测逻辑
        matches = []
        # ... 分析图结构
        return matches
    
    def transform(self, graph, match):
        # 实现转换逻辑
        new_graph = graph.copy()
        # ... 修改图
        return new_graph

# 注册自定义模式
engine = PatternDiscoveryEngine()
engine.register_pattern(MyCustomPattern())
```

---

## 配置系统

### 配置文件结构

```yaml
global:
  use_llm: false
  output:
    save_report: true
    output_dir: "./output/pattern_discovery"

patterns:
  chain_pattern:
    enabled: true
    params: {...}
  
  star_pattern:
    enabled: true
    params: {...}

custom_patterns:
  - name: "Temporal Pattern"
    detection: {...}
    transformation: {...}

application_strategy:
  priority: ["Chain Pattern", "Star Pattern", ...]
  conflict_resolution: "highest_confidence"

performance:
  max_nodes: 10000
  parallel_processing: false
```

### 领域特定配置

```yaml
domain_specific:
  medical_imaging:
    enabled: true
    entity_types: ["伪影", "序列", "参数"]
    relation_types: ["解决方案为", "影响"]
    custom_patterns:
      - name: "Parameter-State-Action Pattern"
        trigger_relations: ["解决方案为"]
```

---

## 性能优化

### 大规模图谱处理

```yaml
performance:
  max_nodes: 10000  # 超过此数量会采样
  parallel_processing: true
  num_workers: 4
  use_cache: true
```

### 计算复杂度

| 模式 | 时间复杂度 | 空间复杂度 |
|------|-----------|-----------|
| Chain Pattern | O(n²) | O(n) |
| Star Pattern | O(n·d) | O(n) |
| Reification | O(e) | O(e) |
| LLM-Driven | O(n·k) | O(k) |

其中：
- n: 节点数
- e: 边数
- d: 平均度数
- k: 子图数量

---

## 与旧方法的对比

| 维度 | 硬编码方法 | 通用框架 |
|------|----------|---------|
| **适用性** | 特定案例 | 通用 |
| **可扩展性** | 低 | 高 |
| **依赖** | 文本模式 | 图结构 |
| **领域适应** | 需重写代码 | 修改配置 |
| **智能程度** | 规则匹配 | 可选LLM |
| **维护成本** | 高 | 低 |
| **可持续性** | 差 | 好 |

---

## 实际应用示例

### 医学影像领域

```python
# 自动检测：伪影 → 解决方案 → 参数 → 影响
results = discover_and_optimize(graph)

# 发现的模式：
# - 链式模式: 化学位移伪影 → 采用高带宽 → 高带宽 → 信噪比
# - 星型模式: T1序列连接多个参数
# - 具体化: 多个序列之间的比较关系
```

### 其他领域

该框架可以直接应用于：
- 临床诊疗知识图谱
- 技术文档知识抽取
- 工业过程知识建模
- 金融关系网络分析
- 社交网络分析
- ...

只需修改配置，无需修改代码！

---

## 运行示例

```bash
# 运行完整示例
python example_pattern_discovery.py

# 查看输出
ls output/pattern_discovery/
  - pattern_report_configured.json
  - original_graph.json
  - optimized_graph.json
```

---

## 最佳实践

### 1. 从基础模式开始

```yaml
patterns:
  chain_pattern:
    enabled: true
  star_pattern:
    enabled: true
  # 先不启用LLM
  llm_driven_pattern:
    enabled: false
```

### 2. 逐步调整参数

```yaml
chain_pattern:
  params:
    min_chain_length: 2  # 从小值开始
    confidence_threshold: 0.5  # 从低阈值开始
```

### 3. 使用配置文件管理

不要在代码中硬编码参数，使用配置文件。

### 4. 先分析再转换

```python
# 先只发现模式
pattern_matches = engine.discover_patterns(graph)

# 检查建议
for matches in pattern_matches.values():
    for match in matches:
        print(match.recommendation)

# 确认后再应用
optimized = engine.apply_transformations(graph, pattern_matches)
```

### 5. 保存中间结果

```python
# 保存原始图
save_graph_to_json(graph, 'original.json')

# 保存模式报告
engine.generate_report(pattern_matches, 'report.json')

# 保存优化图
save_graph_to_json(optimized, 'optimized.json')
```

---

## 常见问题

### Q: 是否需要LLM？

**A**: 不需要！基础功能完全不依赖LLM。LLM只是可选的增强功能。

### Q: 如何处理特定领域？

**A**: 通过配置文件的 `domain_specific` 部分定义领域特征，无需修改代码。

### Q: 如何添加新的模式？

**A**: 继承 `KGPattern` 基类，实现 `detect()` 和 `transform()` 方法，然后注册到引擎。

### Q: 性能如何？

**A**: 对于中小规模图谱（<10000节点）实时处理。大规模图谱可启用采样和并行处理。

### Q: 是否会破坏原始图？

**A**: 不会！所有操作都在副本上进行，原图保持不变。

---

## 技术亮点

### 1. 图算法集成
- 使用NetworkX的图算法
- 路径查找、中心性分析、社区发现

### 2. 置信度评分
- 多因素综合评分
- 基于结构特征和语义特征

### 3. 冲突解决
- 智能处理重叠匹配
- 可配置的优先级策略

### 4. 批量处理
- 高效的批量检测
- 并行处理支持

### 5. 可解释性
- 每个匹配都有详细的元数据
- 清晰的重构建议和理由

---

## 未来扩展

### 计划中的模式

- ✅ Chain Pattern
- ✅ Star Pattern
- ✅ Reification Pattern
- ✅ LLM-Driven Pattern
- 🔜 Hierarchy Pattern
- 🔜 Temporal Pattern
- 🔜 Causal Pattern
- 🔜 Constraint Pattern

### 计划中的功能

- 🔜 模式自动学习
- 🔜 图谱质量评估
- 🔜 交互式可视化
- 🔜 Web界面
- 🔜 更多领域配置

---

## 总结

这是一个**专业的、可持续的、非case-by-case的**解决方案：

✅ **通用性** - 适用于任何领域  
✅ **可扩展** - 轻松添加新模式  
✅ **可配置** - 无需修改代码  
✅ **智能化** - 可选LLM增强  
✅ **专业性** - 基于图论和设计模式  
✅ **可维护** - 清晰的架构和文档  

**从case-by-case到通用框架，这才是可持续的发展方向！**

---

## 文件清单

- `utils/kg_pattern_discovery.py` - 核心框架代码
- `config/pattern_discovery_config.yaml` - 配置文件
- `example_pattern_discovery.py` - 完整示例（6个示例）
- `PATTERN_DISCOVERY_FRAMEWORK.md` - 本文档

---

**立即开始**：

```bash
python example_pattern_discovery.py
```

享受通用框架带来的便利！🎉
