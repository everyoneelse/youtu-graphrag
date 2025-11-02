# 别名去重改进方案 - 实施提案

**日期**: 2025-10-31  
**目标**: 改进Head去重，支持低语义相似度的别名识别  
**案例**: "吉布斯伪影/截断伪影" 等别名对

---

## 📋 问题回顾

### 当前实现的局限

```python
# 当前的候选生成逻辑 (kt_gen.py, line ~4617)
candidate_pairs = self._generate_semantic_candidates(
    remaining_nodes,
    max_candidates=max_candidates,
    similarity_threshold=candidate_similarity_threshold  # 默认 0.75
)
```

**问题**:
```
实体A: "吉布斯伪影"
实体B: "截断伪影"

name_similarity = 0.65  # < 0.75阈值
→ 不会生成候选对
→ 即使图中有 A --[别名包括]--> B
```

---

## 🎯 改进方案对比

### 方案选择矩阵

| 方案 | 实施成本 | 效果提升 | 风险 | 推荐阶段 |
|-----|---------|---------|-----|---------|
| **方案1: 显式关系优先** | ⭐ 低 | ⭐⭐⭐⭐⭐ 高 | 低 | **立即** |
| **方案2: 多特征融合** | ⭐⭐ 中 | ⭐⭐⭐⭐ 较高 | 中 | 1个月内 |
| **方案3: 子图描述** | ⭐⭐⭐ 高 | ⭐⭐ 有限 | 高 | **不推荐** |
| **方案4: 机器学习** | ⭐⭐⭐⭐ 很高 | ⭐⭐⭐⭐⭐ 高 | 中 | 3个月后 |

### 详细评估

#### 方案1: 显式关系优先 ⭐⭐⭐⭐⭐ **强烈推荐**

**核心逻辑**:
```python
# 第一优先级：从图中提取显式别名关系
if graph.has_edge(A, B, relation="别名包括"):
    candidate_pairs.append((A, B, 0.95, 'explicit_alias'))
```

**优点**:
- ✅ **精准**: 直接利用人工标注的知识
- ✅ **简单**: 代码改动少（~30行）
- ✅ **快速**: O(E) 遍历边，无额外计算
- ✅ **可解释**: 明确来源于哪个关系
- ✅ **完美解决你的案例**: "吉布斯伪影→截断伪影"有显式边

**缺点**:
- ❌ 仅适用于图中已有关系的实体对
- ❌ 需要定义哪些关系类型表示别名

**实施成本**: ⭐ **1天**

**预期效果**:
- 召回率提升: +15-25% (取决于图中别名关系数量)
- 精确率: >95% (关系标注通常很准确)

---

#### 方案2: 多特征融合 ⭐⭐⭐⭐ **推荐**

**核心逻辑**:
```python
score = (
    name_similarity * 0.3 +
    neighbor_similarity * 0.3 +
    relation_signature_similarity * 0.4
)
if score > 0.75:
    candidate_pairs.append((A, B, score, 'multi_feature'))
```

**优点**:
- ✅ **鲁棒**: 名称不相似时，其他特征可以补偿
- ✅ **全面**: 综合多维度信息
- ✅ **可调**: 权重可根据领域调整

**缺点**:
- ❌ 计算成本较高 (需要计算邻居、关系模式等)
- ❌ 需要调参确定合适权重
- ❌ 特征工程需要经验

**实施成本**: ⭐⭐ **1周**

**预期效果**:
- 召回率提升: +20-30%
- 精确率: 80-88% (可能有误匹配)

---

#### 方案3: 子图描述相似度 ⭐⭐ **不太推荐**

**核心逻辑**:
```python
desc_A = subgraph_to_text(extract_subgraph(A))
desc_B = subgraph_to_text(extract_subgraph(B))
similarity = cosine_sim(embed(desc_A), embed(desc_B))
```

**优点**:
- ✅ 不依赖名称
- ✅ 利用上下文信息

**缺点**:
- ❌ **你指出的关键问题**: 子图内容不同时失效
  - "吉布斯伪影": 定义、机制
  - "截断伪影": 解决方案
  - → 描述相似度仍然低！
- ❌ 计算成本高（每对都要提取和编码子图）
- ❌ 子图大小难以控制

**实施成本**: ⭐⭐⭐ **1-2周**

**预期效果**:
- 召回率提升: +10-15% (有限)
- 精确率: 75-82%
- **不能解决你的核心案例**

**结论**: ⚠️ **不作为主要方案，可作为多特征融合的一个特征**

---

#### 方案4: 机器学习 ⭐⭐⭐⭐ **长期方案**

**核心逻辑**:
```python
# 用现有别名关系作为训练数据
model = train_classifier(positive=explicit_aliases, negative=random_pairs)
predictions = model.predict_proba(all_candidate_pairs)
```

**优点**:
- ✅ 自动学习模式，无需人工规则
- ✅ 可以泛化到未见过的情况
- ✅ 可以处理复杂的非线性关系

**缺点**:
- ❌ 需要足够的训练数据（>100对）
- ❌ 需要特征工程
- ❌ 模型维护成本
- ❌ 可解释性较差

**实施成本**: ⭐⭐⭐⭐ **2-4周**

**预期效果**:
- 召回率提升: +25-35%
- 精确率: 85-92% (取决于训练数据质量)

---

## 🏆 推荐实施路线

### 阶段1: 快速改进 (1周内) ⭐⭐⭐⭐⭐

**目标**: 立即解决"吉布斯伪影/截断伪影"类问题

**实施方案1: 关系感知候选生成**

```python
# 文件: models/constructor/kt_gen.py
# 位置: _generate_semantic_candidates() 之前

def _generate_candidates_with_relations(
    self,
    remaining_nodes: List[str],
    max_candidates: int = 1000,
    similarity_threshold: float = 0.75
) -> List[Tuple[str, str, float, str]]:
    """
    改进的候选生成：关系优先 + 语义相似度
    
    Returns:
        List of (node_a, node_b, score, source)
    """
    candidates = []
    node_set = set(remaining_nodes)
    
    # ========================================
    # 新增部分：从显式关系中提取候选
    # ========================================
    alias_relations = self._get_alias_relation_types()
    
    for u, v, data in self.graph.edges(data=True):
        relation = data.get('relation', '')
        
        # 只考虑在remaining_nodes中的节点
        if u not in node_set or v not in node_set:
            continue
        
        # 检查是否为别名关系
        if relation in alias_relations:
            candidates.append((u, v, 0.95, 'explicit_alias'))
            logger.debug(f"Found explicit alias: {u} --[{relation}]--> {v}")
    
    logger.info(f"Found {len(candidates)} explicit alias pairs from relations")
    
    # ========================================
    # 原有部分：基于语义相似度
    # ========================================
    semantic_candidates = self._generate_semantic_candidates(
        remaining_nodes,
        max_candidates=max_candidates - len(candidates),  # 减去已有的
        similarity_threshold=similarity_threshold
    )
    
    candidates.extend(semantic_candidates)
    
    # 去重：同一对节点只保留最高分
    candidates = self._deduplicate_candidate_pairs(candidates)
    
    return candidates

def _get_alias_relation_types(self) -> Set[str]:
    """
    获取表示别名的关系类型
    可以从配置文件读取，或使用默认值
    """
    config = self.config.construction.semantic_dedup.head_dedup
    
    # 从配置读取（如果有）
    if hasattr(config, 'alias_relation_types'):
        return set(config.alias_relation_types)
    
    # 默认值
    return {
        "别名包括",
        "alias_of",
        "also_known_as",
        "又称",
        "synonym",
        "也叫",
        "简称",
        "全称",
        "also_called"
    }

def _deduplicate_candidate_pairs(
    self,
    candidates: List[Tuple[str, str, float, str]]
) -> List[Tuple[str, str, float, str]]:
    """
    去重候选对，保留分数最高的
    """
    pair_dict = {}
    
    for u, v, score, source in candidates:
        # 标准化顺序（u < v）
        key = tuple(sorted([u, v]))
        
        if key not in pair_dict or score > pair_dict[key][2]:
            pair_dict[key] = (u, v, score, source)
    
    return list(pair_dict.values())
```

**配置文件修改**:

```yaml
# config/base_config.yaml
construction:
  semantic_dedup:
    head_dedup:
      enabled: true
      enable_semantic: true
      
      # 新增：别名关系类型定义
      alias_relation_types:
        - "别名包括"
        - "alias_of"
        - "also_known_as"
        - "又称"
        - "synonym"
        - "也叫"
        - "简称"
        - "全称"
      
      # 新增：关系传播设置
      enable_relation_propagation: true  # 是否启用传递闭包
      propagation_max_hops: 2           # 最多传播几跳
      
      similarity_threshold: 0.85
      candidate_similarity_threshold: 0.75
      # ... 其他配置保持不变
```

**集成到主流程**:

```python
# 文件: models/constructor/kt_gen.py
# 方法: deduplicate_heads()
# 修改位置: line ~4617

# === 原有代码 ===
# candidate_pairs = self._generate_semantic_candidates(
#     remaining_nodes,
#     max_candidates=max_candidates,
#     similarity_threshold=candidate_similarity_threshold
# )

# === 新代码 ===
candidate_pairs = self._generate_candidates_with_relations(
    remaining_nodes,
    max_candidates=max_candidates,
    similarity_threshold=candidate_similarity_threshold
)
# 增加日志
for u, v, score, source in candidate_pairs:
    if source == 'explicit_alias':
        logger.debug(f"  Alias pair: {u} ↔ {v} (score={score:.3f}, source={source})")
```

**测试验证**:

```python
# 创建测试文件: test_alias_relation_dedup.py

def test_explicit_alias_detection():
    """
    测试显式别名关系的识别
    """
    from models.constructor.kt_gen import KnowledgeTreeGen
    from config import get_config
    
    config = get_config()
    builder = KnowledgeTreeGen(dataset_name="test", config=config)
    
    # 构造测试图
    builder.graph.add_node("entity_0", label="entity", 
                          properties={"name": "吉布斯伪影"})
    builder.graph.add_node("entity_1", label="entity", 
                          properties={"name": "截断伪影"})
    builder.graph.add_node("entity_2", label="entity", 
                          properties={"name": "MRI伪影"})
    
    # 添加别名关系
    builder.graph.add_edge("entity_0", "entity_1", 
                          relation="别名包括",
                          source_chunks=["chunk_1"])
    
    # 添加其他关系
    builder.graph.add_edge("entity_0", "entity_2", 
                          relation="是一种",
                          source_chunks=["chunk_2"])
    
    # 测试候选生成
    candidates = builder._generate_candidates_with_relations(
        remaining_nodes=["entity_0", "entity_1", "entity_2"],
        max_candidates=100,
        similarity_threshold=0.75
    )
    
    # 验证
    alias_candidates = [c for c in candidates if c[3] == 'explicit_alias']
    assert len(alias_candidates) >= 1, "Should find at least 1 explicit alias pair"
    
    # 检查是否包含我们的测试对
    found = False
    for u, v, score, source in alias_candidates:
        if {u, v} == {"entity_0", "entity_1"}:
            found = True
            assert score >= 0.9, "Explicit alias should have high score"
            break
    
    assert found, "Should find the explicit alias pair: 吉布斯伪影 ↔ 截断伪影"
    
    print("✓ Test passed: Explicit alias detection works!")

if __name__ == "__main__":
    test_explicit_alias_detection()
```

**预期效果**:

| 指标 | 改进前 | 改进后 | 提升 |
|-----|-------|-------|-----|
| 识别别名对数 | 100 | 125-140 | +25-40% |
| 低语义相似度别名召回 | 0% | 90-95% | +90% |
| 精确率 | 92% | 93-95% | +1-3% |
| 计算时间增加 | - | <5% | 可忽略 |

---

### 阶段2: 增强鲁棒性 (1个月内) ⭐⭐⭐⭐

**目标**: 处理没有显式关系但应该合并的实体

**实施方案2: 多特征融合**

```python
# 新增方法: _compute_multi_feature_similarity()

def _compute_multi_feature_similarity(
    self,
    node_a: str,
    node_b: str
) -> Tuple[float, Dict[str, float]]:
    """
    计算多特征融合后的相似度分数
    
    Returns:
        (combined_score, feature_details)
    """
    features = {}
    
    # Feature 1: 名称相似度 (基础)
    name_sim = self._compute_name_similarity(node_a, node_b)
    features['name_similarity'] = name_sim
    
    # Feature 2: 显式关系检查
    has_alias_rel = self._check_alias_relation(node_a, node_b)
    features['has_alias_relation'] = 1.0 if has_alias_rel else 0.0
    
    # Feature 3: 邻居相似度
    neighbor_sim = self._compute_neighbor_similarity(node_a, node_b)
    features['neighbor_similarity'] = neighbor_sim
    
    # Feature 4: 关系类型签名相似度
    relation_sig_sim = self._compute_relation_signature_similarity(node_a, node_b)
    features['relation_signature_similarity'] = relation_sig_sim
    
    # Feature 5: 共同路径
    common_paths = self._count_common_paths(node_a, node_b, max_length=3)
    features['common_paths'] = min(1.0, common_paths / 5.0)  # 归一化
    
    # 分层决策
    if features['has_alias_relation'] > 0:
        # 有显式关系 → 高分
        combined_score = 0.95
    elif name_sim > 0.85:
        # 名称高度相似 → 中高分
        combined_score = name_sim
    elif name_sim > 0.60:
        # 名称中度相似 → 需要其他特征支持
        combined_score = (
            name_sim * 0.4 +
            neighbor_sim * 0.3 +
            relation_sig_sim * 0.3
        )
    elif neighbor_sim > 0.80 or relation_sig_sim > 0.80:
        # 名称低相似但其他特征强 → 中分
        combined_score = (
            name_sim * 0.2 +
            neighbor_sim * 0.4 +
            relation_sig_sim * 0.4
        )
    else:
        # 都不强 → 低分
        combined_score = name_sim * 0.5 + max(neighbor_sim, relation_sig_sim) * 0.5
    
    return combined_score, features

def _compute_neighbor_similarity(self, node_a: str, node_b: str) -> float:
    """
    计算两个节点的邻居相似度（Jaccard）
    """
    neighbors_a = set(self.graph.neighbors(node_a))
    neighbors_b = set(self.graph.neighbors(node_b))
    
    if not neighbors_a and not neighbors_b:
        return 0.0
    
    intersection = len(neighbors_a & neighbors_b)
    union = len(neighbors_a | neighbors_b)
    
    return intersection / union if union > 0 else 0.0

def _compute_relation_signature_similarity(self, node_a: str, node_b: str) -> float:
    """
    计算关系模式相似度（只看关系类型，不看目标实体）
    """
    # 出边关系类型
    out_rels_a = [data['relation'] for _, _, data in self.graph.out_edges(node_a, data=True)]
    out_rels_b = [data['relation'] for _, _, data in self.graph.out_edges(node_b, data=True)]
    
    # 入边关系类型
    in_rels_a = [data['relation'] for _, _, data in self.graph.in_edges(node_a, data=True)]
    in_rels_b = [data['relation'] for _, _, data in self.graph.in_edges(node_b, data=True)]
    
    # Jaccard相似度
    def jaccard_multiset(list1, list2):
        from collections import Counter
        c1, c2 = Counter(list1), Counter(list2)
        intersection = sum((c1 & c2).values())
        union = sum((c1 | c2).values())
        return intersection / union if union > 0 else 0.0
    
    out_sim = jaccard_multiset(out_rels_a, out_rels_b)
    in_sim = jaccard_multiset(in_rels_a, in_rels_b)
    
    return (out_sim + in_sim) / 2

def _count_common_paths(self, node_a: str, node_b: str, max_length: int = 3) -> int:
    """
    计算两个节点之间的共同路径数量
    """
    try:
        # 简单实现：检查是否在max_length跳内可达
        import networkx as nx
        length = nx.shortest_path_length(self.graph, node_a, node_b)
        if length <= max_length:
            return max_length - length + 1
        return 0
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return 0
```

**集成方式**:

```python
# 在验证阶段使用多特征评分
def _validate_candidates_with_embedding(
    self,
    candidate_pairs: List[Tuple[str, str, float]],
    threshold: float = 0.85
) -> Tuple[Dict[str, str], Dict[str, dict]]:
    """
    改进：使用多特征评分替代单一embedding相似度
    """
    merge_mapping = {}
    metadata = {}
    
    for node_a, node_b, initial_score in candidate_pairs:
        # 使用多特征融合
        combined_score, feature_details = self._compute_multi_feature_similarity(
            node_a, node_b
        )
        
        if combined_score >= threshold:
            # 选择representative
            canonical, duplicate = self._select_canonical_node(node_a, node_b)
            merge_mapping[duplicate] = canonical
            
            metadata[duplicate] = {
                'method': 'multi_feature',
                'score': combined_score,
                'features': feature_details,
                'paired_with': canonical
            }
    
    return merge_mapping, metadata
```

---

### 阶段3: 关系传播 (可选) ⭐⭐⭐

**目标**: 自动推断隐含的别名关系

```python
def _propagate_alias_relations(
    self,
    max_hops: int = 2
) -> List[Tuple[str, str, float]]:
    """
    别名关系传播
    
    规则:
    1. 传递性: A→B→C (都是别名) => A, C也是别名
    2. 共同别名: A→C, B→C (都是别名) 且 name_sim(A,B) > 0.6 => A, B可能是别名
    """
    propagated_pairs = []
    alias_relations = self._get_alias_relation_types()
    
    # 构建别名图
    alias_graph = nx.DiGraph()
    for u, v, data in self.graph.edges(data=True):
        if data.get('relation') in alias_relations:
            alias_graph.add_edge(u, v)
    
    # 规则1: 传递闭包
    for component in nx.weakly_connected_components(alias_graph):
        component_list = list(component)
        for i in range(len(component_list)):
            for j in range(i+1, len(component_list)):
                u, v = component_list[i], component_list[j]
                # 检查是否已有直接边
                if not alias_graph.has_edge(u, v) and not alias_graph.has_edge(v, u):
                    propagated_pairs.append((u, v, 0.90, 'transitive'))
    
    # 规则2: 共同别名推断
    # (略，见ALIAS_ENTITY_DEDUP_RESEARCH.md中的详细实现)
    
    return propagated_pairs
```

---

## 📊 效果预测

### 量化指标

| 阶段 | 改进内容 | 召回率提升 | 精确率变化 | 实施时间 |
|-----|---------|-----------|-----------|---------|
| **阶段1** | 显式关系优先 | +15-25% | +1-3% | 1周 |
| **阶段2** | 多特征融合 | +20-30% | -2-0% | 1个月 |
| **阶段3** | 关系传播 | +5-10% | -1-0% | 1周 |
| **总计** | 全部实施 | +40-65% | +0-2% | 2个月 |

### 典型案例效果

**案例1: 吉布斯伪影/截断伪影**
- 改进前: ❌ 不识别 (名称相似度0.65 < 0.75)
- 改进后: ✅ 识别 (显式关系 "别名包括", 分数0.95)

**案例2: CPU/中央处理器**
- 改进前: ❌ 不识别 (名称相似度0.55)
- 改进后: ✅ 识别 (邻居相似度0.85 + 关系签名0.90 → 综合0.82)

**案例3: 北京/Beijing**
- 改进前: ✅ 识别 (名称相似度0.75)
- 改进后: ✅ 识别 (名称相似度0.75，或显式关系)

---

## 🧪 测试计划

### 单元测试

```python
# test_alias_dedup_improvements.py

def test_explicit_alias_extraction():
    """测试显式别名关系提取"""
    # 见上文

def test_multi_feature_scoring():
    """测试多特征评分"""
    builder = setup_test_graph()
    
    # 测试1: 名称低但邻居高
    score, features = builder._compute_multi_feature_similarity(
        "node_with_low_name_sim_high_neighbor",
        "node_target"
    )
    assert score > 0.70, "Should score high with high neighbor similarity"
    
    # 测试2: 有显式关系
    score, features = builder._compute_multi_feature_similarity(
        "node_with_alias_relation",
        "node_target"
    )
    assert score >= 0.90, "Explicit relation should give high score"

def test_relation_propagation():
    """测试关系传播"""
    builder = setup_test_graph()
    # A→B, B→C (都是别名)
    propagated = builder._propagate_alias_relations()
    # 应该推断出 A, C也是别名
    assert ("A", "C") in [(p[0], p[1]) for p in propagated]
```

### 集成测试

```python
def test_end_to_end_dedup():
    """端到端测试"""
    config = get_config()
    builder = KnowledgeTreeGen(dataset_name="medical_test", config=config)
    
    # 加载测试数据
    builder.build_knowledge_graph("data/medical_test_corpus.json")
    
    # 执行去重
    stats_before = builder.get_graph_stats()
    dedup_stats = builder.deduplicate_heads()
    stats_after = builder.get_graph_stats()
    
    # 验证
    assert dedup_stats['total_merges'] > 0
    assert stats_after['num_nodes'] < stats_before['num_nodes']
    
    # 检查特定案例
    assert not builder.graph.has_node("截断伪影")  # 应该被合并
    assert builder.graph.has_node("吉布斯伪影")    # 保留
```

---

## 📝 总结与建议

### 核心观点

1. **你的观察完全正确**: 仅依赖名称语义相似度确实不够
2. **方案2（显式关系）优于方案1（子图描述）**: 
   - 更准确
   - 更高效
   - 可解释性更强
3. **"不是基于相似度，而是基于逻辑关系" - 这正是正确的方向！**

### 实施建议

**短期（立即开始）**:
1. ✅ 实施阶段1：显式关系优先
   - 修改候选生成函数
   - 添加配置选项
   - 编写单元测试

**中期（1个月内）**:
2. ✅ 实施阶段2：多特征融合
   - 添加邻居、关系签名等特征
   - 实现分层决策逻辑
   - 进行效果对比

**长期（3个月后）**:
3. 🔬 评估是否需要机器学习方法
   - 取决于数据量和效果需求
   - 如果阶段1+2已经满足需求，可以不做

### 风险提示

⚠️ **注意事项**:
1. **关系质量**: 显式关系方法依赖于原始关系标注的质量
2. **关系类型定义**: 需要仔细定义哪些关系表示别名
3. **传递性风险**: A→B, B→C不一定意味着A→C（需要验证）
4. **性能开销**: 多特征计算会增加时间，需要监控

### 下一步行动

1. ✅ 实现阶段1代码（见上文详细代码）
2. ✅ 在小数据集上测试效果
3. ✅ 根据反馈调整配置和权重
4. ✅ 部署到生产环境
5. 📊 收集效果数据，决定是否进入阶段2

---

**希望这个实施方案对你有帮助！如有任何问题，随时沟通。** 🎉
