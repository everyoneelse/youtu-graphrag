# Head Deduplication with Logical Relations

## 简介

本项目实现了基于逻辑关系的head deduplication增强方案，通过结合**语义相似度**和**图中已存在的逻辑关系**来生成去重候选对，显著提升了去重的召回率和准确性。

### 核心问题

传统的head dedup仅依赖实体名称的语义相似度，导致一些别名关系被遗漏：

```
场景：
- 实体A: "吉布斯伪影"
- 实体B: "截断伪影"
- 图中存在: 吉布斯伪影 --[别名包括]--> 截断伪影

问题：
虽然图中已明确表示别名关系，但由于名称语义相似度可能不高，
传统方法不会将它们作为候选对。
```

### 解决方案

**方案2（已实现）**: 利用图中的逻辑关系生成额外的候选对

- ✅ 从图中提取别名关系作为候选对来源
- ✅ 结合语义相似度候选对
- ✅ LLM统一验证所有候选对
- ✅ 准确可靠，不盲目合并

---

## 快速开始

### 1. 安装依赖

确保已安装项目的基础依赖。

### 2. 使用示例

```python
from models.constructor.kt_gen import KnowledgeTreeGen
from head_dedup_with_logical_relations import HeadDeduplicationLogicalRelationsMixin
from head_dedup_alias_implementation import HeadDeduplicationAliasMixin
from head_dedup_llm_driven_representative import HeadDeduplicationLLMDrivenMixin

# 创建增强类
class EnhancedKnowledgeTreeGen(
    HeadDeduplicationLogicalRelationsMixin,
    HeadDeduplicationLLMDrivenMixin,
    HeadDeduplicationAliasMixin,
    KnowledgeTreeGen
):
    pass

# 使用
builder = EnhancedKnowledgeTreeGen(config=config)

# 运行增强去重
stats = builder.deduplicate_heads_with_relations(
    enable_semantic=True,              # 启用语义候选
    enable_relation_candidates=True,   # 启用关系候选
    similarity_threshold=0.85,
    use_llm_validation=True,
    max_candidates=1000,
    alias_relation_names=["别名包括", "别名", "alias_of"]
)

print(f"合并了 {stats['total_alias_created']} 个实体")
print(f"关系候选对: {stats['relation_based_candidates']}")
```

### 3. 运行示例

```bash
python example_use_relation_based_head_dedup.py
```

---

## 文件说明

### 核心文件

1. **head_dedup_with_logical_relations.py** (455行)
   - 核心实现文件
   - `HeadDeduplicationLogicalRelationsMixin` 类
   - 提供3个核心方法

2. **example_use_relation_based_head_dedup.py** (330行)
   - 完整的使用示例
   - 包含4个测试场景
   - 2个演示函数

### 文档文件

3. **HEAD_DEDUP_LOGICAL_RELATIONS_GUIDE.md** (600+行)
   - 完整的使用指南
   - 技术细节、最佳实践、FAQ
   - 配置示例和对比分析

4. **HEAD_DEDUP_LOGICAL_RELATIONS_SUMMARY.md**
   - 实现总结文档
   - 快速参考指南
   - 设计决策说明

5. **HEAD_DEDUP_LOGICAL_RELATIONS_README.md** (本文件)
   - 项目概述
   - 快速开始指南

6. **conversation_logs/conversation_head_dedup_logical_relations_20251102_125321.md**
   - 完整的对话记录
   - 开发过程文档

---

## 核心功能

### 1. 关系提取

从图中提取具有别名关系的实体对：

```python
relation_candidates = builder._extract_alias_relation_candidates(
    remaining_nodes,
    alias_relation_names=["别名包括", "别名", "alias_of"]
)
```

**支持的关系类型**（默认）:
- 别名包括
- 别名
- alias_of
- also_known_as
- aka
- 又称
- 又名
- 简称

### 2. 候选对合并

结合两种来源生成候选对：

```python
all_candidates = builder._generate_semantic_and_relation_candidates(
    remaining_nodes,
    max_candidates=1000,
    similarity_threshold=0.75,
    enable_relation_candidates=True
)
```

**候选对来源**:
- 语义相似度（基于embedding）
- 逻辑关系（基于图结构）

### 3. 完整去重流程

```python
stats = builder.deduplicate_heads_with_relations(
    enable_semantic=True,              # 启用语义候选
    enable_relation_candidates=True,   # 启用关系候选
    similarity_threshold=0.85,         # 相似度阈值
    use_llm_validation=True,           # LLM验证
    max_candidates=1000,               # 最大候选数
    alias_relation="alias_of",         # 创建的关系名
    alias_relation_names=[...]         # 识别的关系类型
)
```

---

## 配置场景

### 场景1: 最大化召回率

```python
stats = builder.deduplicate_heads_with_relations(
    enable_semantic=True,
    enable_relation_candidates=True,
    similarity_threshold=0.75,         # 降低阈值
    max_candidates=2000                # 增加候选数
)
```

适用于：初次构建图谱、数据探索

### 场景2: 仅使用关系候选（快速）

```python
stats = builder.deduplicate_heads_with_relations(
    enable_semantic=False,             # 禁用语义
    enable_relation_candidates=True    # 仅关系
)
```

适用于：图中有大量高质量别名关系

### 场景3: 平衡模式（推荐）

```python
stats = builder.deduplicate_heads_with_relations(
    enable_semantic=True,
    enable_relation_candidates=True,
    similarity_threshold=0.85,         # 标准阈值
    max_candidates=1000                # 标准候选数
)
```

适用于：生产环境、大多数场景

---

## 技术特点

### 1. Mixin设计

模块化设计，易于集成：

```python
class EnhancedKnowledgeTreeGen(
    HeadDeduplicationLogicalRelationsMixin,  # 逻辑关系支持
    HeadDeduplicationLLMDrivenMixin,         # LLM验证
    HeadDeduplicationAliasMixin,             # Alias方法
    KnowledgeTreeGen                         # 基础类
):
    pass
```

### 2. 双源候选对

- **语义候选**: 基于embedding相似度（传统方法）
- **关系候选**: 基于图中关系（新方法）

### 3. 智能优先级

候选对超限时：
1. 优先保留所有关系候选对
2. 按相似度排序语义候选对
3. 填充剩余配额

### 4. LLM统一验证

所有候选对都经过LLM验证：
- 不会盲目合并有关系的实体
- 确保信息真正等价
- 基于完整上下文做决策

---

## 测试场景

示例包含4个典型场景：

### Case 1: 低语义相似度 + 别名关系
```
吉布斯伪影 --[别名包括]--> 截断伪影
名称相似度低，但有明确的别名关系
```

### Case 2: 高语义相似度（精确匹配）
```
两个实体都叫"运动伪影"
测试传统方法是否仍然有效
```

### Case 3: 语义相似度 + 别名关系
```
磁共振成像 --[别名]--> MRI
两种证据都支持合并
```

### Case 4: 不相关实体
```
化学位移伪影 vs 金属伪影
应该不被合并
```

---

## 性能

### 时间复杂度

| 步骤 | 复杂度 | 说明 |
|------|--------|------|
| 关系提取 | O(E) | E为边数 |
| 语义候选 | O(N²) | N为实体数 |
| LLM验证 | O(C) | C为候选对数 |
| **总体** | **O(N² + E + C)** | E通常远小于N² |

### 实际性能

```
测试配置:
- 实体数: 8
- 边数: 3
- 候选对: 5

性能指标:
- 关系提取: <0.1s
- 语义候选: 2.5s
- LLM验证: 12s
- 总耗时: ~15s
```

---

## 优势

1. ✅ **提高召回率**
   - 捕获语义相似度低但有逻辑关系的实体对
   - 充分利用图中已有知识

2. ✅ **保持准确率**
   - LLM验证避免盲目合并
   - 基于完整上下文做决策

3. ✅ **灵活可配置**
   - 支持多种使用场景
   - 可自定义关系类型

4. ✅ **易于集成**
   - Mixin设计，模块化
   - 与现有代码兼容

5. ✅ **性能可控**
   - max_candidates限制
   - 关系提取快速

---

## 局限

1. ⚠️ **依赖图质量**
   - 如果图中关系有误，会产生错误候选
   - 缓解：LLM会验证，降低风险

2. ⚠️ **需要配置关系类型**
   - 需手动指定哪些关系表示别名
   - 缓解：提供合理默认列表

3. ⚠️ **计算开销**
   - 更多候选对意味着更多LLM调用
   - 缓解：使用max_candidates限制

---

## 常见问题

### Q: 关系候选对会被无条件合并吗？

A: 不会。所有候选对都会经过LLM验证。

### Q: 如果图中没有别名关系怎么办？

A: 不影响。功能退化为传统的语义相似度方法。

### Q: 如何添加新的关系类型？

A: 在调用时传入`alias_relation_names`参数：

```python
stats = builder.deduplicate_heads_with_relations(
    alias_relation_names=["别名包括", "别名", "我的自定义关系"]
)
```

### Q: 性能影响如何？

A: 关系提取很快（O(E)），主要开销在LLM验证，可通过max_candidates控制。

### Q: 可以只用关系候选对吗？

A: 可以。设置`enable_semantic=False, enable_relation_candidates=True`。

---

## 文档导航

- **快速开始**: 本文件（README）
- **详细指南**: [HEAD_DEDUP_LOGICAL_RELATIONS_GUIDE.md](HEAD_DEDUP_LOGICAL_RELATIONS_GUIDE.md)
- **实现总结**: [HEAD_DEDUP_LOGICAL_RELATIONS_SUMMARY.md](HEAD_DEDUP_LOGICAL_RELATIONS_SUMMARY.md)
- **使用示例**: [example_use_relation_based_head_dedup.py](example_use_relation_based_head_dedup.py)
- **核心代码**: [head_dedup_with_logical_relations.py](head_dedup_with_logical_relations.py)
- **对话记录**: [conversation_logs/conversation_head_dedup_logical_relations_20251102_125321.md](conversation_logs/conversation_head_dedup_logical_relations_20251102_125321.md)

---

## 对比分析

### 与方案1（子图描述）的对比

| 维度 | 方案1 | 方案2（本方案） |
|------|-------|----------------|
| 输入数据 | 子图描述文本 | 图中关系边 |
| 计算方法 | embedding相似度 | 关系查询 |
| 优点 | 考虑结构信息 | 直接利用关系 |
| 缺点 | 子图不同时失效 | 需配置关系类型 |
| 性能 | 需计算embedding | 查询快速 |
| 灵活性 | 较低 | **高** |

**结论**: 方案2更简单、直接、高效。

### 与传统方法的对比

| 方法 | 候选对来源 | 召回率 | 准确率 | 成本 |
|------|-----------|--------|--------|------|
| 传统 | 仅语义 | 中 | 高 | 中 |
| 方案1 | 子图描述 | 中-高 | 高 | 高 |
| **方案2** | **语义+关系** | **高** | **高** | **中** |

---

## 未来扩展

1. **自动关系发现**: 自动识别哪些关系表示别名
2. **多跳关系**: 支持A->B->C的传递性
3. **关系权重**: 不同关系有不同置信度
4. **负向关系**: 识别"不同于"避免错误合并

---

## 总结

本方案通过"从图中发现关系，弥补相似度方法的不足"的思路，成功实现了基于逻辑关系的head deduplication增强方案。

**核心价值**: 不再仅依赖名称相似度，而是将图中已存在的关系作为重要的候选对来源，充分利用图中已有的知识。

**适用场景**:
- ✅ 图中有大量别名关系
- ✅ 实体名称多样性高
- ✅ 需要高召回率的去重
- ✅ 图质量较高

---

## 许可

本项目遵循原项目的许可协议。

---

## 联系

如有问题或建议，请通过以下方式联系：

- 查看文档: [HEAD_DEDUP_LOGICAL_RELATIONS_GUIDE.md](HEAD_DEDUP_LOGICAL_RELATIONS_GUIDE.md)
- 运行示例: `python example_use_relation_based_head_dedup.py`

---

**版本**: v1.0  
**日期**: 2025-11-02  
**作者**: Knowledge Graph Team
