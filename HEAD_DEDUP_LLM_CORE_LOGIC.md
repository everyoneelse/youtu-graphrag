# Head实体去重 - LLM核心逻辑详解

**日期**: 2025-10-27  
**主题**: 深度解析LLM在head节点去重中的判断逻辑

---

## 📌 核心问题

LLM需要回答：
```
给定两个head节点，它们是否指代现实世界中的同一个实体？
```

这是一个**二分类任务** + **置信度评估** + **可解释性要求**。

---

## 🎯 完整处理流程

```
┌─────────────────────────────────────────────────────────┐
│  Step 1: 候选对生成（Embedding预筛选）                   │
│  ├─ 计算所有节点的embedding                              │
│  ├─ 相似度矩阵计算                                       │
│  └─ 提取高相似度对（threshold=0.75，宽松）               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Step 2: 构建LLM Prompt                                  │
│  ├─ 提取两个实体的描述信息                               │
│  ├─ 收集两个实体的关系上下文（入边+出边）                 │
│  └─ 按照模板组装prompt                                   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Step 3: 并发调用LLM                                     │
│  ├─ 批量构建所有prompts                                  │
│  ├─ 并发调用（利用现有_concurrent_llm_calls）            │
│  └─ 收集所有响应                                         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Step 4: 解析LLM响应                                     │
│  ├─ JSON解析（使用json_repair容错）                      │
│  ├─ 提取is_coreferent, confidence, rationale            │
│  └─ 验证结果有效性                                       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Step 5: 决策与执行                                      │
│  ├─ 根据置信度阈值过滤（threshold=0.85-0.90）            │
│  ├─ 构建merge_mapping                                    │
│  └─ 记录rationale和metadata                             │
└─────────────────────────────────────────────────────────┘
```

---

## 🧠 LLM判断的核心逻辑

### 1. 输入信息的构建

#### 1.1 实体描述（Entity Description）

```python
desc_1 = self._describe_node(node_id_1)
# 输出示例：
# "Entity: 北京
#  Type: entity
#  Properties: {name: '北京', chunk_id: [1, 3, 5]}"

desc_2 = self._describe_node(node_id_2)
# 输出示例：
# "Entity: 北京市
#  Type: entity  
#  Properties: {name: '北京市', chunk_id: [2, 4]}"
```

#### 1.2 关系上下文（Relational Context）

这是**关键创新点**！不仅看名称，还要看实体在图中的"行为"：

```python
context_1 = self._collect_node_context(node_id_1, max_relations=10)
# 输出示例：
# "  • capital_of → 中国
#   • located_in → 华北地区
#   • has_population → 2100万
#   • has_landmark → 故宫
#   • (reverse) 北京烤鸭 → originated_from"

context_2 = self._collect_node_context(node_id_2, max_relations=10)
# 输出示例：
# "  • is_capital_of → 中华人民共和国
#   • located_in → 华北平原
#   • has_area → 16410平方公里
#   • (reverse) 天安门 → located_in"
```

**为什么关系上下文重要？**

```
场景1: 仅靠名称无法区分
  "张三(教授)" vs "张三(学生)"
  → 名称相同，但关系不同：
     - 教授: teaches_course, published_paper
     - 学生: takes_course, enrolled_in

场景2: 别名/简称的识别
  "北京" vs "北京市"
  → 名称相似，关系高度重合：
     - 都是: capital_of 中国
     - 都有: 故宫、天安门等地标
     → 高度可能是同一实体

场景3: 跨语言的识别  
  "北京" vs "Beijing"
  → 名称不同，但关系完全一致：
     - 相同的capital_of, located_in关系
     → 确定是同一实体
```

### 2. Prompt设计的核心原则

#### 2.1 判断标准（Decision Criteria）

Prompt中明确了3个测试：

```
1. 指称一致性测试 (Referential Identity Test)
   问题: 两个表达式是否指向同一真实世界对象？
   
   ✓ 正例: "NYC" = "New York City" (同一城市)
   ✗ 反例: "Apple Inc." ≠ "Apple Store" (公司 vs 门店)

2. 替换测试 (Substitutability Test)  
   问题: 在所有上下文中互换，是否保持语义不变？
   
   ✓ 正例: "UN" ↔ "United Nations" (可互换)
   ✗ 反例: "北京(古代)" ↔ "北京(现代)" (不能互换，时代不同)

3. 类型一致性测试 (Type Consistency Test)
   问题: 实体类型/类别是否一致？
   
   ✓ 正例: "北京" = "北京市" (都是城市)
   ✗ 反例: "苹果(水果)" ≠ "苹果(公司)" (类型不同)
```

#### 2.2 保守性原则（Conservative Principle）

```python
"""
4. CONSERVATIVE PRINCIPLE:
   - When uncertain → answer NO
   - False merge is worse than false split
"""
```

**为什么保守？**

```
错误成本分析：
┌──────────────────────────────────────────────────────┐
│  False Merge (错误合并)                              │
│  ├─ 后果: 不同实体的知识混淆                         │
│  ├─ 影响: 推理错误、信息污染                         │
│  └─ 修复: 很难检测和撤销                             │
│                                                      │
│  False Split (错误分离)                              │
│  ├─ 后果: 同一实体的知识分散                         │
│  ├─ 影响: 查询不完整                                 │
│  └─ 修复: 可以通过查询聚合、后续人工补救             │
└──────────────────────────────────────────────────────┘

结论: False Merge >> False Split
策略: 不确定时选择 NO (不合并)
```

### 3. LLM的判断过程（推理链）

LLM在内部会进行类似这样的推理：

```
给定: Entity1="北京", Entity2="北京市"

Step 1: 名称分析
  ├─ "北京" vs "北京市"
  ├─ 高度相似，可能是简称/全称关系
  └─ 初步判断: 可能相同 (待验证)

Step 2: 关系比对
  ├─ Entity1: capital_of → 中国
  ├─ Entity2: is_capital_of → 中华人民共和国
  ├─ 分析: "中国" = "中华人民共和国" (同义)
  └─ 证据1: 关系一致 ✓

  ├─ Entity1: located_in → 华北地区
  ├─ Entity2: located_in → 华北平原
  ├─ 分析: 地理位置一致
  └─ 证据2: 位置一致 ✓

  ├─ Entity1: has_landmark → 故宫
  ├─ Entity2: (no 故宫, but has) located_in ← 天安门
  ├─ 分析: 故宫和天安门都是北京地标
  └─ 证据3: 地标一致 ✓

Step 3: 替换测试
  ├─ 如果将"北京"替换为"北京市"
  ├─ 所有关系语义不变
  └─ 测试通过 ✓

Step 4: 类型一致性
  ├─ 都是地理实体（城市）
  ├─ 都有首都属性
  └─ 类型一致 ✓

Step 5: 综合判断
  ├─ 所有测试通过
  ├─ 证据充分
  └─ 结论: is_coreferent=true, confidence=0.95
```

### 4. 输出格式（Structured Output）

```json
{
  "is_coreferent": true,
  "confidence": 0.95,
  "rationale": "Both entities refer to Beijing, the capital of China. '北京' is the simplified name while '北京市' is the full administrative name. They share consistent relationships: both are the capital of China, located in North China, and have the same landmarks. The substitution test confirms they can be used interchangeably in all contexts."
}
```

**关键字段解释**：

| 字段 | 说明 | 用途 |
|------|------|------|
| `is_coreferent` | 是否共指（二分类） | 决策依据 |
| `confidence` | 置信度（0.0-1.0） | 阈值过滤 |
| `rationale` | 判断理由 | 可解释性、审核 |

---

## 🔍 实际案例分析

### 案例1: 应该合并（True Positive）

```
输入:
  Entity1: "UN"
    • founded → 1945
    • has_member → United States
    • has_member → China
    
  Entity2: "United Nations"
    • established_in → 1945
    • member_state → USA
    • member_state → China

LLM推理:
  1. 名称: "UN" 是 "United Nations" 的缩写 ✓
  2. 关系: 成立时间一致、成员国一致 ✓
  3. 替换: "UN通过决议" = "联合国通过决议" ✓
  4. 类型: 都是国际组织 ✓

输出:
  {
    "is_coreferent": true,
    "confidence": 0.98,
    "rationale": "UN is the abbreviation of United Nations. All contextual relations (founding year, member states) are consistent."
  }

决策: 合并 ✓
```

### 案例2: 不应该合并（True Negative）

```
输入:
  Entity1: "Apple Inc."
    • founded_by → Steve Jobs
    • produces → iPhone
    • headquarters_in → Cupertino
    
  Entity2: "Apple Store"
    • owned_by → Apple Inc.
    • located_in → New York
    • sells → iPhone

LLM推理:
  1. 名称: 相似，但可能不同层级 ⚠️
  2. 关系: 
     - Entity1: 创建产品（produces）
     - Entity2: 销售产品（sells）
     - Entity2 被 Entity1 拥有（owned_by）
     - 明显的所属关系！✗
  3. 替换: "Apple Inc.在纽约" ≠ "Apple Store在纽约" ✗
  4. 类型: 公司 vs 零售店 ✗

输出:
  {
    "is_coreferent": false,
    "confidence": 0.95,
    "rationale": "These are two different entities. Apple Inc. is the company that owns Apple Store. The relationship 'Apple Store owned_by Apple Inc.' clearly indicates a hierarchical ownership, not coreference."
  }

决策: 不合并 ✓
```

### 案例3: 不确定（边界案例）

```
输入:
  Entity1: "张三"
    • works_at → 清华大学
    • age → 45
    
  Entity2: "张三"
    • studies_at → 北京大学
    • age → 22

LLM推理:
  1. 名称: 完全相同 ⚠️
  2. 关系: 
     - Entity1: 工作（works_at）+ 45岁
     - Entity2: 学习（studies_at）+ 22岁
     - 年龄和职业不一致！⚠️
  3. 替换: 无法互换（不同年龄、不同职业）✗
  4. 类型: 都是人，但可能是不同的人 ⚠️

输出:
  {
    "is_coreferent": false,
    "confidence": 0.72,
    "rationale": "Although both entities have the same name '张三', the contextual information suggests they are different persons: one is a 45-year-old worker at Tsinghua, the other is a 22-year-old student at Peking University. Given the name ambiguity and conservative principle, they should NOT be merged."
  }

决策: 不合并（置信度0.72，即使is_coreferent=false也表明不确定） ✓
```

---

## ⚖️ 与Embedding-only方法的对比

### Embedding方法的局限

```python
# Embedding仅基于语义相似度
similarity = cosine_similarity(emb1, emb2)

问题:
  1. "Apple Inc." 和 "Apple Store" 
     → embedding相似度很高（0.88）
     → 但不是同一实体！

  2. "北京" 和 "Beijing"
     → 如果是单语embedding，相似度可能不高（0.65）
     → 但实际是同一实体！

  3. "张三(教授)" 和 "张三(学生)"
     → 名称相同，embedding很相似（0.95）
     → 但可能是不同人！
```

### LLM方法的优势

```python
# LLM可以进行推理
LLM考虑:
  1. 关系结构 (Structural Context)
     → "owned_by" 关系说明层级，不应合并
  
  2. 语义理解 (Semantic Understanding)
     → "北京" = "Beijing" (跨语言知识)
  
  3. 常识推理 (Commonsense Reasoning)
     → 45岁工作者 ≠ 22岁学生 (即使同名)
  
  4. 上下文整合 (Context Integration)
     → 综合所有证据做出判断
```

### 混合策略（推荐）

```
Pipeline:
  ┌────────────────────────────────┐
  │ Embedding预筛选                │
  │ - 快速过滤明显不相关的          │
  │ - 提取高相似度候选对            │
  │ - 复杂度: O(n²) → O(k*n)       │
  └────────────────────────────────┘
                ↓
  ┌────────────────────────────────┐
  │ LLM精确判断                    │
  │ - 对候选对进行深度分析          │
  │ - 利用关系和常识推理            │
  │ - 给出可解释的结果              │
  └────────────────────────────────┘

优点:
  ✓ 结合两者优势
  ✓ 高召回率（embedding）+ 高精确率（LLM）
  ✓ 成本可控（LLM只处理候选对）
```

---

## 🎛️ 关键参数调优

### 1. Embedding预筛选阈值

```python
similarity_threshold_for_candidates = 0.75  # 推荐值

效果:
  - 0.70: 召回率高，但LLM调用多（成本高）
  - 0.75: 平衡 ← 推荐
  - 0.80: 召回率降低，可能漏掉一些等价实体
```

### 2. LLM置信度阈值

```python
confidence_threshold = 0.85  # 推荐值

决策规则:
  if is_coreferent and confidence >= 0.85:
      合并
  else:
      不合并

调优策略:
  - 0.95: 极保守，只合并非常确定的
  - 0.90: 保守，适合生产环境
  - 0.85: 平衡 ← 推荐
  - 0.80: 积极，可能有误合并
```

### 3. 关系上下文数量

```python
max_relations = 10  # 推荐值

权衡:
  - 太少（5）: 上下文不足，判断不准
  - 适中（10）: 平衡 ← 推荐
  - 太多（20）: Prompt过长，LLM可能混淆
```

---

## 📊 预期效果

基于类似NLP任务的经验：

| 指标 | Embedding-only | LLM | 提升 |
|------|---------------|-----|------|
| **Precision** | 82-85% | 92-95% | +10% |
| **Recall** | 75-80% | 85-90% | +10% |
| **F1 Score** | 78-82% | 88-92% | +10% |
| **处理速度** | 快（秒级） | 慢（分钟级） | -10x |
| **成本** | 低 | 高（LLM调用） | +100x |

**建议**：
- 生产环境首次运行：用LLM，确保质量
- 日常增量更新：用Embedding，兼顾效率
- 重要数据：用LLM + 人工审核

---

## 🔧 实现细节

### 并发处理优化

```python
# 批量调用LLM，避免串行等待
prompts = []
for node_id_1, node_id_2, _ in candidate_pairs:
    prompts.append({
        "prompt": self._build_head_dedup_prompt(node_id_1, node_id_2),
        "metadata": {"node_id_1": node_id_1, "node_id_2": node_id_2}
    })

# 并发调用（利用现有基础设施）
llm_results = self._concurrent_llm_calls(prompts)

性能提升:
  - 串行: N个候选对 × 2秒/调用 = 2N秒
  - 并发: N个候选对 / 10并发 × 2秒 = 0.2N秒
  - 提升: 10倍加速
```

### 容错处理

```python
def _parse_coreference_response(self, response: str) -> dict:
    try:
        parsed = json_repair.loads(response)  # 容错JSON解析
        return {
            "is_coreferent": bool(parsed.get("is_coreferent", False)),
            "confidence": float(parsed.get("confidence", 0.0)),
            "rationale": str(parsed.get("rationale", ""))
        }
    except Exception as e:
        # 解析失败，保守处理
        logger.warning(f"Failed to parse LLM response: {e}")
        return {
            "is_coreferent": False,  # 默认不合并
            "confidence": 0.0,
            "rationale": "Parse error"
        }
```

---

## 💡 总结

### LLM去重的核心价值

1. **深度理解**：不仅看表面名称，还分析关系和上下文
2. **推理能力**：能进行常识推理和类型推断
3. **可解释性**：给出明确的判断理由
4. **处理歧义**：能区分同名不同实体

### 适用场景

✅ **推荐使用LLM的情况**：
- 生产环境首次去重
- 高价值/关键数据
- 需要高精确率
- 有预算支持

❌ **不推荐使用LLM的情况**：
- 日常增量更新
- 大规模图谱（> 100k实体）
- 成本敏感
- 时效性要求高

### 最佳实践

```
方案A: 生产环境（质量优先）
  1. Embedding预筛选（threshold=0.75）
  2. LLM验证（threshold=0.90）
  3. 人工审核（confidence=0.70-0.90）

方案B: 日常维护（效率优先）
  1. Embedding预筛选（threshold=0.75）
  2. Embedding判断（threshold=0.88）
  3. 定期人工抽检

方案C: 混合模式（平衡）
  1. Embedding预筛选（threshold=0.75）
  2. 高相似度（>0.85）用Embedding直接判断
  3. 中等相似度（0.75-0.85）用LLM验证
  4. 低相似度（<0.75）直接过滤
```

---

**文档版本**: v1.0  
**最后更新**: 2025-10-27
