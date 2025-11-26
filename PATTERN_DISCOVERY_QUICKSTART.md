# 模式发现框架 - 5分钟快速开始 ⚡

## 一句话总结

**从case-by-case的硬编码到通用的、可扩展的、专业的知识图谱模式发现框架。**

---

## 🆚 新旧对比

### ❌ 旧方法（v1）

```python
# 硬编码的文本模式
if re.match(r'高(.+)', entity_name):
    return 'state_entity'
```

**问题**：
- 只适用于特定案例
- 依赖实体命名
- 难以扩展

### ✅ 新方法（v2）

```python
# 基于图结构的通用框架
results = discover_and_optimize(graph)
```

**优势**：
- 适用于任何领域
- 基于图结构
- 完全可扩展

---

## 🚀 立即开始

### 1️⃣ 运行示例

```bash
python example_pattern_discovery.py
```

### 2️⃣ 查看输出

```bash
ls output/pattern_discovery/
  - pattern_report_configured.json  # 发现的模式
  - original_graph.json              # 原始图谱
  - optimized_graph.json             # 优化后的图谱
```

### 3️⃣ 在代码中使用

```python
from utils.kg_pattern_discovery import discover_and_optimize

# 加载你的图谱
graph = load_graph_from_json('your_graph.json')

# 一行代码完成模式发现和优化！
results = discover_and_optimize(
    graph=graph,
    output_dir='./output',
    use_llm=False  # 可选LLM增强
)

print(f"✅ 发现 {results['stats']['total_pattern_matches']} 个模式")
print(f"✅ 新增 {results['stats']['optimized_edges'] - results['stats']['original_edges']} 条边")
```

---

## 🎯 支持的模式

| 模式 | 说明 | 示例 |
|------|------|------|
| **Chain** | A→B→C链式连接 | 伪影→解决方案→参数→效果 |
| **Star** | 中心节点连接多个节点 | T1序列→{对比度,时间,分辨率} |
| **Reification** | 关系转实体 | A和B之间有多种关系 |
| **LLM-Driven** | LLM自动发现 | 任何未预定义的模式 |

---

## ⚙️ 配置文件

编辑 `config/pattern_discovery_config.yaml`：

```yaml
patterns:
  chain_pattern:
    enabled: true
    params:
      min_chain_length: 2
      max_chain_length: 5
  
  star_pattern:
    enabled: true
    params:
      min_neighbors: 3
  
  llm_driven_pattern:
    enabled: false  # 需要LLM支持
```

---

## 📊 示例输出

```
Chain Pattern: 2 个匹配
  链 #1: 化学位移伪影 → 采用高带宽 → 高带宽 → 信噪比
    置信度: 0.75
    建议: 添加快捷关系
  
  链 #2: 运动伪影 → 使用门控技术 → 门控技术 → 扫描时间
    置信度: 0.72
    建议: 标记关键节点

Star Pattern: 1 个匹配
  星型 #1: T1加权序列 连接 4个相关概念
    置信度: 0.80
    建议: 分析周边节点关联

Reification Pattern: 1 个匹配
  具体化 #1: 梯度回波序列 ↔ 自旋回波序列 (3条边)
    置信度: 0.70
    建议: 创建关系实体节点
```

---

## 🔧 扩展新模式

```python
from utils.kg_pattern_discovery import KGPattern

class MyCustomPattern(KGPattern):
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

# 注册并使用
engine = PatternDiscoveryEngine()
engine.register_pattern(MyCustomPattern())
```

---

## 📚 文档导航

- **快速开始**（本文档）：5分钟上手
- **框架文档**：`PATTERN_DISCOVERY_FRAMEWORK.md` - 完整介绍
- **配置文档**：`config/pattern_discovery_config.yaml` - 参数说明
- **示例程序**：`example_pattern_discovery.py` - 6个示例

---

## ❓ 常见问题

### Q: 需要LLM吗？
**A**: 不需要！LLM是可选的增强功能。

### Q: 如何处理特定领域？
**A**: 修改配置文件的 `domain_specific` 部分，无需改代码。

### Q: 性能如何？
**A**: 中小规模图谱（<10000节点）实时处理。

### Q: 与旧版兼容吗？
**A**: API基本兼容，建议新项目直接用v2。

---

## ✨ 核心优势

| 特性 | 旧版 | 新版 |
|------|------|------|
| **通用性** | ❌ | ✅ |
| **可配置** | ❌ | ✅ |
| **可扩展** | ❌ | ✅ |
| **专业性** | ⚠️ | ✅ |
| **可持续** | ❌ | ✅ |

---

## 🎉 立即体验

```bash
# 1. 运行示例
python example_pattern_discovery.py

# 2. 查看结果
cat output/pattern_discovery/pattern_report_configured.json

# 3. 在你的项目中使用
# 把你的图谱传给 discover_and_optimize() 即可！
```

---

**从case-by-case到通用框架，这才是专业和可持续的方案！** 🚀

查看完整文档：`PATTERN_DISCOVERY_FRAMEWORK.md`
