# Prompt对比：Head去重 vs Tail去重

**日期**: 2025-10-27  
**目的**: 对比现有tail去重和提出的head去重在prompt设计和信息使用上的差异

---

## 📊 整体对比总览

| 维度 | Tail去重（现有） | Head去重（提出） |
|------|----------------|----------------|
| **任务类型** | 一对多判断 | 两两比较 |
| **判断对象** | 共享(head, relation)的多个tails | 两个独立的head节点 |
| **输入信息** | head + relation + chunk contexts | entity1 + entity2 + 图关系 |
| **上下文类型** | 文本片段（chunk） | 图结构（edges） |
| **输出格式** | 多个groups（N个tail分组） | 单个判断（是/否） |
| **调用频率** | 每个(head, relation)一次 | 每个候选对一次 |

---

## 🔍 详细对比

### 1. 输入信息对比

#### 1.1 Tail去重的输入信息

```python
def _build_semantic_dedup_prompt(
    head_text: str,           # "Entity: 张三, Type: entity, Properties: {...}"
    relation: str,            # "works_at"
    head_context_lines: list, # ["- (chunk_1) 张三在清华大学工作...", 
                              #  "- (chunk_3) 张三是一位教授..."]
    batch_entries: list       # 多个tail候选
):
    # 为每个tail构建：
    for entry in batch_entries:
        description = entry["description"]      # Tail描述
        context_lines = entry["context_summaries"]  # Tail相关的chunk

    # Prompt包含：
    """
    Head entity: 张三
    Relation: works_at
    Head contexts:
      - (chunk_1) 张三在清华大学工作...
      - (chunk_3) 张三是一位教授...
    
    Candidate tails:
      [1] Tail: 清华大学
          Contexts:
            - (chunk_1) 张三在清华大学工作...
            - (chunk_5) 清华大学成立于1911年...
      
      [2] Tail: Tsinghua University
          Contexts:
            - (chunk_7) Tsinghua University is located in Beijing...
      
      [3] Tail: 清华
          Contexts:
            - (chunk_9) 清华是中国顶尖学府...
    """
```

**关键特点**：
- ✅ 使用原始文本（chunk）作为上下文
- ✅ 能看到实体被提及时的完整语境
- ✅ 适合消歧义（例如区分"清华"作为学校 vs 地名）
- ❌ 无法直接看到实体之间的关系结构
- ❌ 依赖文本质量和覆盖度

#### 1.2 Head去重的输入信息（我提出的）

```python
def _build_head_dedup_prompt(node_id_1: str, node_id_2: str):
    desc_1 = self._describe_node(node_id_1)  # "Entity: 北京, Type: entity"
    desc_2 = self._describe_node(node_id_2)  # "Entity: 北京市, Type: entity"
    
    # 收集关系上下文（关键创新）
    context_1 = self._collect_node_context(node_id_1, max_relations=10)
    context_2 = self._collect_node_context(node_id_2, max_relations=10)
    
    # Prompt包含：
    """
    Entity 1: 北京
    Related knowledge about Entity 1:
      • capital_of → 中国
      • located_in → 华北地区
      • has_population → 2100万
      • has_landmark → 故宫
      • 中华人民共和国 → capital (reverse)
    
    Entity 2: 北京市
    Related knowledge about Entity 2:
      • is_capital_of → 中华人民共和国
      • located_in → 华北平原
      • has_area → 16410平方公里
      • 天安门 → located_in (reverse)
    """
```

**关键特点**：
- ✅ 使用图结构（关系）作为上下文
- ✅ 能看到实体在知识图谱中的"行为模式"
- ✅ 适合识别等价实体（关系模式相似）
- ✅ 不依赖原始文本的质量
- ❌ 无法看到原始文本语境
- ❌ 需要图已经构建好且关系准确

---

### 2. Prompt结构对比

#### 2.1 现有Tail去重Prompt（摘要）

```
DEFAULT_SEMANTIC_DEDUP_PROMPT = """
You are a knowledge graph curation assistant performing entity deduplication.
All listed triples share the same head entity and relation.

Head entity: {head}
Relation: {relation}

Head contexts:
{head_context}  ← 使用chunk文本片段

Candidate tails:
{candidates}    ← 每个tail也有chunk contexts

TASK: Identify which tails are COREFERENT.

FUNDAMENTAL PRINCIPLE:
COREFERENCE requires REFERENTIAL IDENTITY...

MERGE CONDITIONS:
1. REFERENT TEST
2. SUBSTITUTION TEST  
3. EQUIVALENCE CLASS

PROHIBITED MERGE REASONS:
✗ Shared relation
✗ Semantic similarity
✗ Same category
...

OUTPUT: JSON with groups
{
  "groups": [
    {"members": [1, 3], "representative": 3, "rationale": "..."}
  ]
}
"""
```

#### 2.2 提出的Head去重Prompt（摘要）

```
HEAD_DEDUP_PROMPT = """
You are an expert in knowledge graph entity resolution.

TASK: Determine if the following two entities refer to the SAME real-world object.

Entity 1: {desc_1}
Related knowledge about Entity 1:
{context_1}  ← 使用图关系（入边+出边）

Entity 2: {desc_2}
Related knowledge about Entity 2:
{context_2}  ← 使用图关系（入边+出边）

CRITICAL RULES:
1. REFERENTIAL IDENTITY
2. SUBSTITUTION TEST
3. TYPE CONSISTENCY
4. CONSERVATIVE PRINCIPLE

OUTPUT: JSON with binary decision
{
  "is_coreferent": true/false,
  "confidence": 0.0-1.0,
  "rationale": "..."
}
"""
```

---

### 3. 核心判断逻辑对比

#### 3.1 共同点

两者都基于相同的理论基础：

| 原则 | Tail去重 | Head去重 |
|------|---------|---------|
| **指称一致性** | ✅ REFERENT TEST | ✅ REFERENTIAL IDENTITY |
| **替换测试** | ✅ SUBSTITUTION TEST | ✅ SUBSTITUTION TEST |
| **保守原则** | ✅ When in doubt, keep separate | ✅ When uncertain → NO |
| **禁止错误理由** | ✅ 详细列举 | ✅ 详细列举 |

#### 3.2 关键差异

##### Tail去重的特殊考虑

```
CRITICAL DISTINCTION - Relation Satisfaction vs Entity Identity:
⚠️  If multiple tails all satisfy relation R with head H, 
    this does NOT make them coreferent.

Example:
  张三 --works_at--> 清华大学
  张三 --works_at--> 计算机系
  
  → "清华大学" 和 "计算机系" 都满足works_at关系
  → 但它们是不同的实体（学校 vs 院系）
  → 不应该合并
```

**为什么需要强调？**
- Tail去重中，所有候选都共享同一个relation
- LLM容易被"共享关系"误导
- 必须明确：共享关系 ≠ 实体等价

##### Head去重的特殊考虑

```
TYPE CONSISTENCY:
Check entity types/categories
- Same name, different types → carefully verify with context

Example:
  Entity1: "苹果" → produces → iPhone
  Entity2: "苹果" → nutritional_value → 维生素C
  
  → 虽然名称相同
  → 但关系模式完全不同（公司 vs 水果）
  → 不应该合并
```

**为什么需要强调？**
- Head去重中，两个节点完全独立（没有共享关系的约束）
- 同名不同实体的风险更大
- 必须利用关系模式判断类型

---

### 4. 上下文信息的本质差异

#### 4.1 Tail去重：文本驱动（Text-Driven）

```python
# Head context (chunk texts)
head_context_lines = [
    "- (chunk_1) 张三在清华大学担任教授，专注于计算机视觉研究。",
    "- (chunk_3) 张三获得了IEEE Fellow称号。"
]

# Tail context (chunk texts)
tail_context_lines = [
    "- (chunk_1) 清华大学位于北京市海淀区。",
    "- (chunk_5) 清华大学成立于1911年，是中国顶尖大学。"
]
```

**优势**：
- ✅ 丰富的语义信息
- ✅ 能处理复杂的语言现象（比喻、指代等）
- ✅ 适合早期图谱构建（关系还不完善）

**劣势**：
- ❌ 依赖文本质量
- ❌ 可能包含噪声
- ❌ 无法直接利用图结构

#### 4.2 Head去重：图结构驱动（Graph-Driven）

```python
# Entity1 context (graph relations)
context_1 = """
  • capital_of → 中国
  • located_in → 华北地区
  • has_population → 2100万
  • has_landmark → 故宫
  • 天坛 → located_in (reverse)
"""

# Entity2 context (graph relations)
context_2 = """
  • is_capital_of → 中华人民共和国
  • located_in → 华北平原
  • has_area → 16410平方公里
  • 天安门 → located_in (reverse)
"""
```

**优势**：
- ✅ 结构化信息，清晰直观
- ✅ 能发现关系模式的相似性
- ✅ 不受文本质量影响
- ✅ 适合已构建好的图谱（关系较完善）

**劣势**：
- ❌ 需要图谱已经构建
- ❌ 如果关系缺失，信息量不足
- ❌ 无法利用原始文本的语义

---

## 💡 使用场景对比

### Tail去重适用场景

```
✅ 场景1: 同一个head的多个tail需要去重
  Example: 
    张三 --born_in--> 北京
    张三 --born_in--> 北京市
    张三 --born_in--> Beijing
  
  → 三个tail指同一地点，需要合并

✅ 场景2: 图谱构建早期，关系还不完善
  → 依赖chunk文本提供上下文

✅ 场景3: Tail之间的区分需要原始文本
  Example:
    论文A --published_in--> 2020
    论文A --published_in--> 2020年
    论文A --published_in--> CVPR 2020
  
  → 需要文本区分"年份"还是"会议+年份"
```

### Head去重适用场景

```
✅ 场景1: 全局实体去重
  Example:
    entity_5: "北京" (works_at的tail)
    entity_10: "北京市" (located_in的tail)
    entity_15: "Beijing" (capital_of的head)
  
  → 跨关系、跨位置的全局去重

✅ 场景2: 图谱构建后期，关系已经完善
  → 可以利用关系模式判断等价

✅ 场景3: 原始文本不可用或质量差
  → 仅依赖图结构进行判断
```

---

## 🔄 两种方法的互补性

### 方案A: 顺序应用（推荐）

```
Pipeline:
  1. 构建初步图谱
     ↓
  2. Tail去重（现有方法）
     → 利用chunk contexts
     → 对每个(head, relation)组合去重
     ↓
  3. Head去重（新方法）
     → 利用图关系
     → 全局去重所有entity节点
     ↓
  4. 最终图谱
```

**优势**：
- 两阶段互补，充分利用文本和图结构
- Tail去重减少冗余，为Head去重提供更好的关系
- Head去重进一步整合，提升图谱质量

### 方案B: 混合上下文（实验性）

可以考虑在Head去重中同时使用两种上下文：

```python
def _build_head_dedup_prompt_hybrid(node_id_1, node_id_2):
    # 节点描述
    desc_1 = self._describe_node(node_id_1)
    desc_2 = self._describe_node(node_id_2)
    
    # 关系上下文（图结构）
    graph_context_1 = self._collect_node_context(node_id_1)
    graph_context_2 = self._collect_node_context(node_id_2)
    
    # 文本上下文（chunks）← 新增
    chunk_context_1 = self._summarize_contexts(
        self._collect_node_chunk_ids(node_id_1)
    )
    chunk_context_2 = self._summarize_contexts(
        self._collect_node_chunk_ids(node_id_2)
    )
    
    prompt = f"""
    Entity 1: {desc_1}
    
    Graph relations:
    {graph_context_1}
    
    Text contexts:
    {chunk_context_1}
    
    Entity 2: {desc_2}
    
    Graph relations:
    {graph_context_2}
    
    Text contexts:
    {chunk_context_2}
    
    TASK: Determine if they are the same entity using BOTH graph structure and text evidence.
    """
```

**潜在优势**：
- 结合两种信息源
- 更鲁棒的判断

**潜在劣势**：
- Prompt更长，LLM处理更慢
- 可能引入混淆（信息过载）

---

## 📈 性能对比（估算）

| 指标 | Tail去重（文本驱动） | Head去重（图驱动） | Head去重（混合） |
|------|-------------------|-----------------|----------------|
| **信息丰富度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **结构化程度** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **依赖前提** | 需要原始文本 | 需要完善图谱 | 两者都需要 |
| **Prompt长度** | 中等 | 短 | 长 |
| **处理速度** | 中等 | 快 | 慢 |
| **适用阶段** | 构建早期 | 构建后期 | 任何阶段 |

---

## 🎯 建议

### 1. 当前实施建议

**保持现有Tail去重不变**，**新增Head去重**：

```python
# Pipeline
def build_knowledge_graph(documents):
    builder = KnowledgeTreeGen(...)
    
    # Step 1: 处理文档
    for doc in documents:
        builder.process_document(doc)
    
    # Step 2: Tail去重（现有，使用chunk contexts）
    if config.semantic_dedup.enabled:
        builder.triple_deduplicate_semantic()
    
    # Step 3: Head去重（新增，使用graph relations）
    if config.semantic_dedup.head_dedup.enabled:
        builder.deduplicate_heads(
            enable_semantic=True,
            similarity_threshold=0.85,
            use_llm_validation=False
        )
    
    return builder
```

### 2. 未来优化方向

#### 短期（1-2个月）
- ✅ 实现基础Head去重（仅用图关系）
- ✅ 在真实数据上测试效果
- ✅ 与Tail去重结果对比

#### 中期（3-6个月）
- 🔬 实验混合上下文方法
- 🔬 A/B测试不同信息组合
- 🔬 优化Prompt以减少长度

#### 长期（6个月+）
- 🚀 自适应上下文选择
  - 图关系充足 → 仅用图
  - 图关系稀疏 → 加入文本
  - 自动判断信息源权重
- 🚀 统一的去重框架
  - 同时处理head和tail
  - 共享embedding和LLM资源

---

## 📊 实际案例对比

### 案例1: 别名识别

**Tail去重（文本驱动）**：
```
Head: 张三
Relation: works_at

Candidate tails:
[1] Tail: 清华大学
    Contexts:
      - (chunk_1) 张三在清华大学担任教授
      - (chunk_5) 清华大学是中国顶尖学府

[2] Tail: Tsinghua University
    Contexts:
      - (chunk_7) Zhang San works at Tsinghua University

LLM判断:
  → "清华大学" 和 "Tsinghua University" 从文本可以看出是同一大学
  → 合并 ✓
```

**Head去重（图驱动）**：
```
Entity 1: 清华大学
Related knowledge:
  • located_in → 北京
  • founded → 1911
  • 张三 → works_at (reverse)

Entity 2: Tsinghua University  
Related knowledge:
  • located_in → Beijing
  • established_in → 1911
  • Zhang San → works_at (reverse)

LLM判断:
  → 关系高度一致（地点、成立时间、员工）
  → "Beijing" = "北京" (LLM的常识)
  → 合并 ✓
```

**结论**: 两种方法都能正确识别，但依据不同。

### 案例2: 歧义消除

**Tail去重（文本驱动）**：
```
Head: 苹果公司
Relation: produces

Candidate tails:
[1] Tail: iPhone
    Contexts:
      - (chunk_1) 苹果公司生产iPhone手机

[2] Tail: 苹果
    Contexts:
      - (chunk_5) 市场上销售的苹果价格上涨

LLM判断:
  → "iPhone"是电子产品，"苹果"在chunk_5中指水果
  → 从文本可以明确区分
  → 不合并 ✓
```

**Head去重（图驱动）**：
```
Entity 1: 苹果公司
Related knowledge:
  • produces → iPhone
  • founded_by → Steve Jobs
  • headquartered_in → Cupertino

Entity 2: 苹果 (水果)
Related knowledge:
  • nutritional_value → 维生素C
  • grown_in → 果园
  • is_a → 水果

LLM判断:
  → 关系模式完全不同（科技公司 vs 水果）
  → 不合并 ✓
```

**结论**: 两种方法都能正确区分，图驱动更直观。

---

## 总结

### 核心差异

| 方面 | Tail去重 | Head去重 |
|------|---------|---------|
| **信息类型** | 文本片段（chunks） | 图关系（edges） |
| **判断范围** | 局部（同一head+relation） | 全局（任意两个entities） |
| **上下文来源** | 原始文档 | 知识图谱 |
| **最佳时机** | 图谱构建中 | 图谱构建后 |

### 互补关系

两种方法**不是替代关系，而是互补关系**：

```
Tail去重 → 清理局部冗余，利用文本语义
   ↓
Head去重 → 整合全局等价，利用图结构
   ↓
高质量知识图谱
```

### 最终建议

✅ **保持现有Tail去重prompt不变**（已经很优秀）  
✅ **新增Head去重功能**（使用图关系作为上下文）  
✅ **顺序应用两者**（Tail去重 → Head去重）  
🔬 **未来探索混合方法**（结合文本和图关系）

---

**文档版本**: v1.0  
**最后更新**: 2025-10-27
