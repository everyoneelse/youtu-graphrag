# Head节点去重 - 快速开始

**5分钟快速上手指南**

---

## 📖 背景

您已经实现了**tail去重**（对共享head和relation的tail列表去重），现在需要实现**head去重**（对指代同一实体的不同head节点去重）。

### 问题示例

```
当前状态（有重复）:
  entity_0 (name: "北京")    → capital_of → entity_10 (name: "中国")
  entity_5 (name: "北京市")  → located_in → entity_15 (name: "华北")
  entity_8 (name: "Beijing") → has_population → entity_20 (name: "2100万")

期望状态（去重后）:
  entity_0 (name: "北京")    → capital_of → entity_10
                            → located_in → entity_15  
                            → has_population → entity_20
  
  [entity_5 和 entity_8 被合并到 entity_0，所有关系转移]
```

---

## 🎯 核心方案

### 架构总览

```
┌─────────────────────────────────┐
│   Phase 1: 精确匹配去重          │
│   "北京" = "北京" ✓              │
│   O(n) 复杂度，快速              │
└─────────────────────────────────┘
            ↓
┌─────────────────────────────────┐
│   Phase 2: 语义相似度去重        │
│   "北京" ≈ "北京市" ✓            │
│   "北京" ≈ "Beijing" ✓           │
│   使用Embedding + LLM（可选）    │
└─────────────────────────────────┘
            ↓
┌─────────────────────────────────┐
│   Phase 3: 图结构更新            │
│   • 转移所有边（入边+出边）       │
│   • 合并节点属性                 │
│   • 记录溯源信息                 │
│   • 删除重复节点                 │
└─────────────────────────────────┘
```

### 关键特点

| 特性 | 说明 |
|------|------|
| ✅ **两阶段处理** | 精确匹配 + 语义去重，与tail去重保持一致 |
| ✅ **保守策略** | 不确定时保持分离，避免错误合并 |
| ✅ **完整溯源** | 记录所有合并历史和依据 |
| ✅ **图结构安全** | 事务性操作，保证完整性 |
| ✅ **可扩展** | 支持大规模图谱的批处理 |

---

## 🚀 快速集成（3步）

### Step 1: 添加代码到项目

将以下文件内容合并到 `models/constructor/kt_gen.py`:

```python
# 从 head_deduplication_reference.py 复制所有方法到 KnowledgeTreeGen 类
# 或者使用Mixin继承（推荐）

from head_deduplication_reference import HeadDeduplicationMixin

class KnowledgeTreeGen(HeadDeduplicationMixin, ...):
    # 现在自动具有以下方法：
    # - deduplicate_heads()
    # - validate_graph_integrity_after_head_dedup()
    # - export_head_merge_candidates_for_review()
    pass
```

### Step 2: 添加配置

在 `config/base_config.yaml` 中添加:

```yaml
semantic_dedup:
  # ... 现有配置 ...
  
  head_dedup:
    enabled: true
    enable_semantic: true
    similarity_threshold: 0.85
    use_llm_validation: false
    max_candidates: 1000
```

### Step 3: 在Pipeline中调用

```python
# 在处理完文档和tail去重后，添加head去重
def build_graph(documents):
    builder = KnowledgeTreeGen(dataset_name="demo")
    
    # 1. 处理文档
    for doc in documents:
        builder.process_document(doc)
    
    # 2. Tail去重（现有）
    builder.triple_deduplicate_semantic()
    
    # 3. 【新增】Head去重
    stats = builder.deduplicate_heads(
        enable_semantic=True,
        similarity_threshold=0.85,
        use_llm_validation=False,
        max_candidates=1000
    )
    
    print(f"✓ Merged {stats['total_merges']} head nodes")
    
    return builder
```

---

## 📊 参数配置指南

### 快速选择配置模式

| 场景 | 配置 |
|------|------|
| **快速模式**（性能优先） | `enable_semantic=False` |
| **平衡模式**（推荐） | `enable_semantic=True, threshold=0.85, use_llm=False` |
| **高精度模式**（质量优先） | `enable_semantic=True, threshold=0.90, use_llm=True` |

### 参数详解

#### `similarity_threshold` - 最重要参数

```
0.95-1.00: 极严格，几乎只合并完全相同的
0.90-0.95: 严格，适合生产环境
0.85-0.90: 平衡，推荐默认  ← 推荐
0.70-0.85: 宽松，适合探索分析
0.00-0.70: 太宽松，不推荐
```

#### `use_llm_validation`

- `false`: 快速模式，仅用embedding判断（推荐）
- `true`: 高精度模式，LLM二次验证（慢但准）

#### `max_candidates`

根据图规模调整：
- 小图谱 (< 1k实体): `1000-5000`
- 中图谱 (1k-10k): `500-1000`  ← 推荐
- 大图谱 (> 10k): `200-500`

---

## 📁 文档结构

本次提供的完整方案包含以下文件：

```
/workspace/
├── HEAD_DEDUPLICATION_SOLUTION.md           # 完整方案设计（必读）
├── head_deduplication_reference.py          # 参考实现代码
├── example_head_deduplication.py            # 8个使用示例
├── HEAD_DEDUP_IMPLEMENTATION_GUIDE.md       # 详细集成指南
└── HEAD_DEDUP_QUICKSTART.md                 # 本文档（快速开始）
```

### 阅读顺序

1. **快速了解** → 本文档（5分钟）
2. **深入理解** → `HEAD_DEDUPLICATION_SOLUTION.md`（30分钟）
3. **开始编码** → `HEAD_DEDUP_IMPLEMENTATION_GUIDE.md` + 参考实现
4. **学习用法** → `example_head_deduplication.py`

---

## 🧪 快速测试

### 最小可运行示例

```python
from models.constructor.kt_gen import KnowledgeTreeGen

# 创建构建器
builder = KnowledgeTreeGen(dataset_name="test")

# 手动添加测试数据
builder.graph.add_node("entity_0", label="entity", properties={"name": "北京"})
builder.graph.add_node("entity_1", label="entity", properties={"name": "北京市"})
builder.graph.add_node("entity_2", label="entity", properties={"name": "上海"})

# 添加一些边
builder.graph.add_edge("entity_0", "entity_2", relation="nearby")
builder.graph.add_edge("entity_1", "entity_2", relation="located_with")

print(f"Before dedup: {builder.graph.number_of_nodes()} nodes")

# 执行去重
stats = builder.deduplicate_heads(
    enable_semantic=True,
    similarity_threshold=0.85,
    use_llm_validation=False
)

print(f"After dedup: {stats['final_entity_count']} nodes")
print(f"Merged: {stats['total_merges']} nodes")

# 验证完整性
issues = builder.validate_graph_integrity_after_head_dedup()
print(f"Integrity: {'✓ OK' if not any(issues.values()) else '⚠ Issues found'}")
```

---

## ⚡ 性能预期

| 图规模 | 配置 | 预期时间 |
|--------|------|----------|
| 100实体 | 平衡模式 | < 5秒 |
| 1,000实体 | 平衡模式 | 10-30秒 |
| 10,000实体 | 平衡模式 | 1-5分钟 |
| 100,000实体 | 平衡模式 | 10-30分钟 |

**注**: 使用 `use_llm_validation=True` 会增加3-10倍时间

---

## 🎓 核心原则（专业视角）

### 1. 实体等价性判定

```
两个head节点等价 ⟺ 指代同一真实世界对象

判定依据：
✓ 指称一致性 (Referential Identity)
✓ 替换测试 (Substitutability Test)  
✓ 属性一致性 (Property Consistency)
```

### 2. 保守性原则

```
错误成本不对等：
  False Merge (错误合并) >> False Split (错误分离)

策略：
  不确定时 → 保持分离
  置信度阈值 → 严格设定
```

### 3. 可解释性

每次合并都记录：
- 为什么合并？（rationale）
- 置信度多少？（confidence）
- 使用什么方法？（method: exact/embedding/llm）
- 何时合并的？（timestamp）

---

## 🔍 效果验证

### 查看合并结果

```python
# 检查哪些节点被合并了
for node_id, data in builder.graph.nodes(data=True):
    dedup_info = data.get("properties", {}).get("head_dedup", {})
    
    if dedup_info and dedup_info.get("merged_nodes"):
        print(f"\n✓ {node_id} ({data['properties']['name']})")
        print(f"  Merged: {len(dedup_info['merged_nodes'])} nodes")
        
        for record in dedup_info["merge_history"]:
            print(f"    • {record['merged_node_name']}")
            print(f"      Confidence: {record['confidence']:.2f}")
            print(f"      Rationale: {record['rationale'][:80]}...")
```

### 导出人工审核

```python
# 导出中等置信度的合并供审核
builder.export_head_merge_candidates_for_review(
    output_path="output/review/head_merges.csv",
    min_confidence=0.70,
    max_confidence=0.90
)

# 在Excel中打开 head_merges.csv，检查合并是否正确
```

---

## ❓ 常见问题速查

| 问题 | 快速解决 |
|------|----------|
| **处理太慢** | 降低 `max_candidates`，提高 `threshold`，禁用 `use_llm` |
| **合并错误** | 提高 `threshold` 到 0.90+，启用 `use_llm=True` |
| **漏掉重复** | 降低 `threshold` 到 0.80，但要人工审核 |
| **内存溢出** | 减少 `max_candidates`，或实现分批处理 |
| **想要审核** | 设置 `export_review=True` |

---

## 📚 延伸阅读

### 理论基础

- **Entity Resolution**: 数据集成中的实体解析技术
- **Coreference Resolution**: NLP中的共指消解
- **Entity Linking**: 知识图谱中的实体链接

### 相关论文

- DeepER: Deep Learning for Entity Resolution
- Neural Coreference Resolution (Clark & Manning, 2016)
- GraphER: Entity Resolution in Knowledge Graphs

---

## 🎉 开始使用

您现在已经了解了head去重的核心方案，可以：

1. ✅ 查看 `HEAD_DEDUP_IMPLEMENTATION_GUIDE.md` 进行详细集成
2. ✅ 参考 `head_deduplication_reference.py` 中的代码实现
3. ✅ 运行 `example_head_deduplication.py` 中的示例
4. ✅ 阅读 `HEAD_DEDUPLICATION_SOLUTION.md` 了解设计细节

**祝您实施顺利！**

---

**版本**: v1.0  
**日期**: 2025-10-27  
**作者**: Knowledge Graph Architect
