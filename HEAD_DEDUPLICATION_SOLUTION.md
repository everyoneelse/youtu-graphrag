# Head节点去重方案设计文档

**日期**: 2025-10-27  
**版本**: v1.0  
**作者**: 知识图谱架构师

---

## 📋 目录

1. [背景与现状分析](#背景与现状分析)
2. [问题定义](#问题定义)
3. [方案设计原则](#方案设计原则)
4. [技术方案](#技术方案)
5. [实现细节](#实现细节)
6. [数据一致性保障](#数据一致性保障)
7. [性能优化策略](#性能优化策略)
8. [风险评估与缓解](#风险评估与缓解)

---

## 背景与现状分析

### 当前Tail去重实现

当前系统已实现对**共享head和relation的tail列表**的去重，核心逻辑如下：

```python
# 按 (head, relation) 分组
for (head, relation), edges in grouped_edges.items():
    # 1. 精确去重
    exact_unique = self._deduplicate_exact(edges)
    
    # 2. 语义去重（如果启用且有多个tail）
    if self._semantic_dedup_enabled() and len(exact_unique) > 1:
        semantic_deduplicated = self._semantic_deduplicate_group(head, relation, exact_unique)
```

**关键特点**：
- ✅ 分组粒度：`(head, relation)`
- ✅ 去重对象：tail节点
- ✅ 两阶段处理：精确去重 + 语义去重
- ✅ 元数据保留：完整溯源信息

### 当前实体节点管理

```python
def _find_or_create_entity(self, entity_name: str, chunk_id: int, ...):
    # 通过名称查找现有实体
    entity_node_id = next(
        (n for n, d in self.graph.nodes(data=True)
         if d.get("label") == "entity" and d["properties"]["name"] == entity_name),
        None,
    )
    
    if not entity_node_id:
        # 创建新实体节点
        entity_node_id = f"entity_{self.node_counter}"
        # ...
```

**问题**：仅基于**精确字符串匹配**进行节点复用，无法识别语义等价的实体。

---

## 问题定义

### 核心问题

在知识图谱构建过程中，同一实体可能被以不同形式提及：

| 场景 | 示例 | 问题 |
|------|------|------|
| 别名/简称 | "北京" vs "北京市" | 创建重复节点 |
| 全称/简称 | "中国人民大学" vs "人大" | 语义相同，形式不同 |
| 缩写 | "United Nations" vs "UN" | 同一组织不同表达 |
| 翻译差异 | "New York" vs "纽约" | 跨语言等价 |
| 歧义指代 | "他"，"张三" 在不同chunk中 | 上下文依赖的指代 |

**后果**：
- 🔴 图结构冗余：重复节点增加存储开销
- 🔴 查询效率低：同一实体的关系分散在多个节点
- 🔴 推理完整性差：无法整合同一实体的所有知识

### 目标

实现**head节点的语义去重**，使得：
1. 识别并合并语义等价的head节点
2. 整合所有关联关系到代表性节点
3. 保留完整溯源信息
4. 保持图结构一致性

---

## 方案设计原则

### 1. 专业原则

#### 1.1 实体等价性判定原则（Entity Coreference Resolution）

**核心定义**：两个head节点等价 ⟺ 它们指代现实世界中的**同一实体**

**判定标准**（参考NLP中的实体链接/Entity Linking）：

```
等价条件（ALL必须满足）：
├─ 指称一致性 (Referential Identity)
│  └─ 是否指向同一真实世界对象？
├─ 替换测试 (Substitutability Test)  
│  └─ 在所有上下文中互换不改变语义？
└─ 属性一致性 (Property Consistency)
   └─ 关键属性（类型/类别）是否兼容？
```

**错误示例**（不应合并）：
- ❌ "苹果(水果)" ≠ "苹果(公司)" → 不同实体类型
- ❌ "张三(教授)" ≠ "张三(学生)" → 同名不同人
- ❌ "北京(古代燕京)" ≠ "北京(现代首都)" → 时间语境不同

#### 1.2 保守性原则（Conservative Principle）

```
错误成本不对等：
  False Merge (错误合并) >> False Split (错误分离)
  
策略：
  不确定时 → 保持分离
  置信度阈值 → 严格设定（建议 ≥ 0.85）
```

**理由**：
- 错误合并会导致**信息污染**（不同实体的知识混淆）
- 错误分离仅导致**信息分散**（可通过查询聚合补救）

#### 1.3 可解释性原则

每次合并必须提供：
- **合并依据**：为什么这两个节点是同一实体？
- **置信度**：决策可靠性量化
- **溯源路径**：从原始节点到合并节点的完整路径

---

### 2. 技术原则

#### 2.1 两阶段处理（与tail去重保持一致）

```
Phase 1: 精确匹配去重
  ├─ 完全相同的字符串 → 直接合并
  └─ 性能：O(n)，快速过滤

Phase 2: 语义相似度去重
  ├─ 嵌入向量聚类
  ├─ LLM判断（可选）
  └─ 性能：O(n²) 或 O(n log n)，精细处理
```

#### 2.2 图结构一致性

**节点合并操作**必须保证：
1. **边的完整性**：所有入边和出边正确转移
2. **元数据完整性**：所有属性信息合并
3. **溯源完整性**：记录合并前的所有原始节点ID

#### 2.3 批量并发处理

与现有tail去重逻辑保持一致：
- 批量收集所有待判断的节点对
- 并发调用LLM/embedding模型
- 统一解析结果后批量应用

---

## 技术方案

### 方案架构

```
┌─────────────────────────────────────────────────────┐
│           Head Deduplication Pipeline               │
└─────────────────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
┌──────────────┐              ┌──────────────────┐
│ Phase 1:     │              │ Phase 2:         │
│ Exact Match  │─────────────▶│ Semantic Dedup   │
│ Deduplication│              │                  │
└──────────────┘              └──────────────────┘
        │                               │
        ├─ String normalization         ├─ Candidate Generation
        ├─ Hash-based grouping          ├─ Embedding Clustering
        └─ Direct merge                 ├─ LLM Validation (optional)
                                        └─ Merge with metadata
                        │
                        ▼
        ┌───────────────────────────────┐
        │ Phase 3:                      │
        │ Graph Structure Update        │
        └───────────────────────────────┘
                        │
        ├─ Edge reassignment (in/out)
        ├─ Metadata consolidation
        ├─ Node removal
        └─ Provenance recording
```

### 核心流程

#### 1. 候选节点收集

```python
def _collect_head_candidates(self) -> List[str]:
    """收集所有需要去重的head节点（entity节点）"""
    candidates = [
        node_id
        for node_id, data in self.graph.nodes(data=True)
        if data.get("label") == "entity"  # 只处理实体节点
    ]
    return candidates
```

**关键决策**：
- 仅对 `label == "entity"` 的节点去重
- 不处理 `attribute`、`keyword`、`community` 节点
- 理由：这些节点有不同的语义和生命周期

#### 2. Phase 1: 精确匹配去重

```python
def _deduplicate_heads_exact(self, candidates: List[str]) -> Dict[str, str]:
    """
    精确匹配去重
    
    Returns:
        Dict[old_id, canonical_id]: 映射表
    """
    # 按标准化名称分组
    name_groups = defaultdict(list)
    
    for node_id in candidates:
        node_data = self.graph.nodes[node_id]
        name = node_data.get("properties", {}).get("name", "")
        
        # 标准化处理
        normalized_name = self._normalize_entity_name(name)
        name_groups[normalized_name].append(node_id)
    
    # 构建合并映射
    merge_mapping = {}
    for normalized_name, node_ids in name_groups.items():
        if len(node_ids) > 1:
            # 选择代表性节点（启发式：最早创建的节点）
            canonical_id = min(node_ids, key=lambda x: int(x.split('_')[1]))
            for node_id in node_ids:
                if node_id != canonical_id:
                    merge_mapping[node_id] = canonical_id
    
    return merge_mapping

def _normalize_entity_name(self, name: str) -> str:
    """实体名称标准化"""
    # 1. 转小写
    normalized = name.lower().strip()
    # 2. 去除多余空格
    normalized = ' '.join(normalized.split())
    # 3. 去除常见标点符号
    normalized = normalized.replace('.', '').replace(',', '').replace('!', '')
    # 4. 统一全角/半角（中文环境）
    # ... 可扩展更多规则
    return normalized
```

**性能**：O(n)，适合大规模图

#### 3. Phase 2: 语义去重

##### 3.1 候选对生成（Candidate Pair Generation）

```python
def _generate_semantic_candidates(
    self, 
    remaining_nodes: List[str],
    max_candidates: int = 1000
) -> List[Tuple[str, str, float]]:
    """
    生成需要语义判断的候选节点对
    
    策略：基于embedding相似度预筛选，避免O(n²)暴力比较
    
    Returns:
        List[(node_id_1, node_id_2, similarity_score)]
    """
    # 1. 批量获取节点描述
    node_descriptions = {
        node_id: self._describe_node_for_clustering(node_id)
        for node_id in remaining_nodes
    }
    
    # 2. 批量获取embedding
    embeddings = self._batch_get_embeddings(list(node_descriptions.values()))
    node_to_embedding = dict(zip(node_descriptions.keys(), embeddings))
    
    # 3. 基于余弦相似度聚类（快速预筛选）
    from sklearn.metrics.pairwise import cosine_similarity
    similarity_matrix = cosine_similarity(list(node_to_embedding.values()))
    
    # 4. 提取高相似度候选对
    candidates = []
    nodes = list(node_to_embedding.keys())
    threshold = 0.75  # 预筛选阈值（较宽松）
    
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            sim = similarity_matrix[i][j]
            if sim >= threshold:
                candidates.append((nodes[i], nodes[j], float(sim)))
    
    # 5. 按相似度降序排序，取top-K
    candidates.sort(key=lambda x: x[2], reverse=True)
    return candidates[:max_candidates]
```

**关键技术**：
- **Blocking/Indexing**：避免O(n²)复杂度
- **两阶段过滤**：embedding预筛选 + LLM精确判断
- **可扩展性**：支持LSH、FAISS等近似最近邻算法

##### 3.2 LLM语义判断（可选增强）

```python
def _validate_head_coreference_with_llm(
    self,
    node_id_1: str,
    node_id_2: str
) -> Tuple[bool, str, float]:
    """
    使用LLM判断两个head节点是否指代同一实体
    
    Returns:
        (is_coreferent, rationale, confidence)
    """
    desc_1 = self._describe_node(node_id_1)
    desc_2 = self._describe_node(node_id_2)
    
    # 收集上下文（关联的关系和属性）
    context_1 = self._collect_node_context(node_id_1)
    context_2 = self._collect_node_context(node_id_2)
    
    prompt = self._build_head_dedup_prompt(
        entity_1=desc_1,
        entity_2=desc_2,
        context_1=context_1,
        context_2=context_2
    )
    
    response = self.extract_with_llm(prompt)
    parsed = self._parse_coreference_response(response)
    
    return (
        parsed.get("is_coreferent", False),
        parsed.get("rationale", ""),
        parsed.get("confidence", 0.0)
    )

def _collect_node_context(self, node_id: str, max_relations: int = 10) -> str:
    """收集节点的关系上下文，用于LLM判断"""
    contexts = []
    
    # 出边（该实体作为head）
    out_edges = list(self.graph.out_edges(node_id, data=True))[:max_relations]
    for _, tail_id, data in out_edges:
        relation = data.get("relation", "related_to")
        tail_desc = self._describe_node(tail_id)
        contexts.append(f"  - {relation}: {tail_desc}")
    
    # 入边（该实体作为tail）
    in_edges = list(self.graph.in_edges(node_id, data=True))[:max_relations]
    for head_id, _, data in in_edges:
        relation = data.get("relation", "related_to")
        head_desc = self._describe_node(head_id)
        contexts.append(f"  - (reverse) {head_desc} → {relation}")
    
    return "\n".join(contexts) if contexts else "No relations found"
```

##### 3.3 Prompt设计

```python
HEAD_DEDUP_PROMPT_TEMPLATE = """
You are an expert in knowledge graph entity resolution.

TASK: Determine if the following two entities refer to the SAME real-world object.

Entity 1: {entity_1}
Related knowledge about Entity 1:
{context_1}

Entity 2: {entity_2}
Related knowledge about Entity 2:
{context_2}

CRITICAL RULES:
1. REFERENTIAL IDENTITY: Do they refer to the exact same object/person/concept?
   - Same entity with different names → YES (e.g., "NYC" = "New York City")
   - Different but related entities → NO (e.g., "Apple Inc." ≠ "Apple Store")

2. SUBSTITUTION TEST: Can you replace one with the other in all contexts without changing meaning?
   - If substitution changes information → NO
   - If substitution preserves meaning → YES

3. TYPE CONSISTENCY: Check entity types/categories
   - "Beijing (city)" ≠ "Beijing (ancient capital)" if contexts differ significantly
   - Same name, different types → carefully verify with context

4. CONSERVATIVE PRINCIPLE:
   - When uncertain → answer NO
   - False merge is worse than false split

PROHIBITED MERGE REASONS (NOT valid):
✗ Similar names (e.g., "John Smith" vs "John Smith Jr.")
✗ Related entities (e.g., "Apple" company vs "Apple" product)
✗ Same category (e.g., both are cities, but different cities)

OUTPUT FORMAT (strict JSON):
{{
  "is_coreferent": true/false,
  "confidence": 0.0-1.0,
  "rationale": "Clear explanation based on referential identity test"
}}

EXAMPLES:
✓ "北京" and "北京市" → is_coreferent: true (same city, different name format)
✓ "UN" and "United Nations" → is_coreferent: true (abbreviation of same organization)
✗ "张三(教授)" and "张三(学生)" → is_coreferent: false (same name, different persons based on context)
✗ "Apple Inc." and "Apple Store" → is_coreferent: false (company vs retail location)

Now, analyze Entity 1 and Entity 2:
"""
```

**设计要点**：
- 明确**指代一致性**（referential identity）原则
- 提供**正例和反例**，few-shot learning
- 要求**结构化输出**（JSON）便于解析
- **保守性提示**：不确定时选择不合并

#### 4. Phase 3: 图结构更新

```python
def _merge_head_nodes(
    self,
    merge_mapping: Dict[str, str],
    merge_metadata: Dict[str, dict]
) -> int:
    """
    执行head节点合并，更新图结构
    
    Args:
        merge_mapping: {duplicate_id: canonical_id}
        merge_metadata: {duplicate_id: {"rationale": ..., "confidence": ...}}
    
    Returns:
        合并的节点数量
    """
    merged_count = 0
    
    for duplicate_id, canonical_id in merge_mapping.items():
        if duplicate_id not in self.graph:
            continue  # 已被删除
        
        if canonical_id not in self.graph:
            logger.warning(f"Canonical node {canonical_id} not found, skipping")
            continue
        
        # 1. 转移所有出边 (duplicate_id作为head的边)
        self._reassign_outgoing_edges(duplicate_id, canonical_id)
        
        # 2. 转移所有入边 (duplicate_id作为tail的边)
        self._reassign_incoming_edges(duplicate_id, canonical_id)
        
        # 3. 合并节点属性
        self._merge_node_properties(duplicate_id, canonical_id, merge_metadata.get(duplicate_id, {}))
        
        # 4. 删除重复节点
        self.graph.remove_node(duplicate_id)
        merged_count += 1
        
        logger.debug(f"Merged {duplicate_id} into {canonical_id}")
    
    return merged_count

def _reassign_outgoing_edges(self, source_id: str, target_id: str):
    """转移出边（source_id作为head的所有关系）"""
    outgoing = list(self.graph.out_edges(source_id, keys=True, data=True))
    
    for _, tail_id, key, data in outgoing:
        # 避免自环 (如果tail就是target_id)
        if tail_id == target_id:
            continue
        
        # 检查是否已存在相同的边
        if not self._edge_exists(target_id, tail_id, data):
            self.graph.add_edge(target_id, tail_id, **copy.deepcopy(data))
        else:
            # 如果边已存在，合并chunk信息
            self._merge_edge_chunks(target_id, tail_id, data)

def _reassign_incoming_edges(self, source_id: str, target_id: str):
    """转移入边（source_id作为tail的所有关系）"""
    incoming = list(self.graph.in_edges(source_id, keys=True, data=True))
    
    for head_id, _, key, data in incoming:
        # 避免自环
        if head_id == target_id:
            continue
        
        # 检查是否已存在相同的边
        if not self._edge_exists(head_id, target_id, data):
            self.graph.add_edge(head_id, target_id, **copy.deepcopy(data))
        else:
            self._merge_edge_chunks(head_id, target_id, data)

def _merge_node_properties(self, duplicate_id: str, canonical_id: str, metadata: dict):
    """合并节点属性，记录溯源信息"""
    canonical_data = self.graph.nodes[canonical_id]
    duplicate_data = self.graph.nodes[duplicate_id]
    
    # 初始化head_dedup元数据
    if "head_dedup" not in canonical_data.get("properties", {}):
        canonical_data.setdefault("properties", {})["head_dedup"] = {
            "merged_nodes": [],
            "merge_history": []
        }
    
    # 记录合并信息
    canonical_data["properties"]["head_dedup"]["merged_nodes"].append(duplicate_id)
    canonical_data["properties"]["head_dedup"]["merge_history"].append({
        "merged_node_id": duplicate_id,
        "merged_node_name": duplicate_data.get("properties", {}).get("name", ""),
        "rationale": metadata.get("rationale", "Exact match or semantic similarity"),
        "confidence": metadata.get("confidence", 1.0),
        "timestamp": time.time()
    })
    
    # 合并chunk信息
    canonical_chunks = set(canonical_data.get("properties", {}).get("chunk_ids", []))
    duplicate_chunks = set(duplicate_data.get("properties", {}).get("chunk_ids", []))
    merged_chunks = list(canonical_chunks | duplicate_chunks)
    if merged_chunks:
        canonical_data["properties"]["chunk_ids"] = merged_chunks

def _edge_exists(self, u: str, v: str, new_data: dict) -> bool:
    """检查是否已存在相同的边（基于relation）"""
    new_relation = new_data.get("relation")
    for _, _, data in self.graph.edges(u, v, data=True):
        if data.get("relation") == new_relation:
            return True
    return False

def _merge_edge_chunks(self, u: str, v: str, new_data: dict):
    """合并边的chunk信息到已存在的边"""
    new_relation = new_data.get("relation")
    new_chunks = set(new_data.get("source_chunks", []))
    
    for key, data in self.graph[u][v].items():
        if data.get("relation") == new_relation:
            existing_chunks = set(data.get("source_chunks", []))
            merged_chunks = list(existing_chunks | new_chunks)
            if merged_chunks:
                data["source_chunks"] = merged_chunks
            break
```

---

## 实现细节

### 完整Pipeline接口

```python
def deduplicate_heads(
    self,
    enable_semantic: bool = True,
    similarity_threshold: float = 0.85,
    use_llm_validation: bool = False,
    max_candidates: int = 1000
) -> Dict[str, Any]:
    """
    主入口：执行head节点去重
    
    Args:
        enable_semantic: 是否启用语义去重
        similarity_threshold: 语义相似度阈值（0.0-1.0）
        use_llm_validation: 是否使用LLM验证（提高准确率但更慢）
        max_candidates: 最大处理候选对数量
    
    Returns:
        去重统计信息
    """
    logger.info("=" * 60)
    logger.info("Starting Head Node Deduplication")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    # Phase 1: 收集候选节点
    logger.info("Phase 1: Collecting head candidates...")
    candidates = self._collect_head_candidates()
    logger.info(f"  Found {len(candidates)} entity nodes")
    
    # Phase 2: 精确匹配去重
    logger.info("Phase 2: Exact match deduplication...")
    exact_merge_mapping = self._deduplicate_heads_exact(candidates)
    logger.info(f"  Exact matches: {len(exact_merge_mapping)} merges")
    
    # 应用精确匹配合并
    exact_merged_count = self._merge_head_nodes(exact_merge_mapping, {})
    
    # Phase 3: 语义去重（可选）
    semantic_merge_mapping = {}
    semantic_merged_count = 0
    
    if enable_semantic:
        logger.info("Phase 3: Semantic deduplication...")
        
        # 3.1 获取剩余节点（排除已合并的）
        remaining_nodes = [
            node_id for node_id in candidates
            if node_id not in exact_merge_mapping and node_id in self.graph
        ]
        logger.info(f"  Remaining nodes: {len(remaining_nodes)}")
        
        # 3.2 生成候选对
        candidate_pairs = self._generate_semantic_candidates(
            remaining_nodes, 
            max_candidates=max_candidates
        )
        logger.info(f"  Generated {len(candidate_pairs)} candidate pairs")
        
        # 3.3 验证候选对
        if use_llm_validation:
            logger.info("  Using LLM validation (slower but more accurate)...")
            semantic_merge_mapping, metadata = self._validate_candidates_with_llm(
                candidate_pairs, 
                similarity_threshold
            )
        else:
            logger.info("  Using embedding-only validation (faster)...")
            semantic_merge_mapping, metadata = self._validate_candidates_with_embedding(
                candidate_pairs, 
                similarity_threshold
            )
        
        logger.info(f"  Semantic matches: {len(semantic_merge_mapping)} merges")
        
        # 3.4 应用语义合并
        semantic_merged_count = self._merge_head_nodes(semantic_merge_mapping, metadata)
    
    elapsed_time = time.time() - start_time
    
    # 统计信息
    stats = {
        "total_candidates": len(candidates),
        "exact_merges": exact_merged_count,
        "semantic_merges": semantic_merged_count,
        "total_merges": exact_merged_count + semantic_merged_count,
        "remaining_nodes": len([n for n, d in self.graph.nodes(data=True) if d.get("label") == "entity"]),
        "elapsed_time_seconds": elapsed_time
    }
    
    logger.info("=" * 60)
    logger.info("Head Deduplication Completed")
    logger.info(f"  Total merges: {stats['total_merges']}")
    logger.info(f"  Reduction rate: {stats['total_merges'] / stats['total_candidates'] * 100:.2f}%")
    logger.info(f"  Time elapsed: {elapsed_time:.2f}s")
    logger.info("=" * 60)
    
    return stats

def _validate_candidates_with_embedding(
    self,
    candidate_pairs: List[Tuple[str, str, float]],
    threshold: float
) -> Tuple[Dict[str, str], Dict[str, dict]]:
    """基于embedding相似度验证候选对"""
    merge_mapping = {}
    metadata = {}
    
    for node_id_1, node_id_2, similarity in candidate_pairs:
        if similarity >= threshold:
            # 选择canonical节点（启发式：ID更小的）
            canonical = min(node_id_1, node_id_2, key=lambda x: int(x.split('_')[1]))
            duplicate = node_id_2 if canonical == node_id_1 else node_id_1
            
            merge_mapping[duplicate] = canonical
            metadata[duplicate] = {
                "rationale": f"High embedding similarity: {similarity:.3f}",
                "confidence": float(similarity)
            }
    
    return merge_mapping, metadata

def _validate_candidates_with_llm(
    self,
    candidate_pairs: List[Tuple[str, str, float]],
    threshold: float
) -> Tuple[Dict[str, str], Dict[str, dict]]:
    """使用LLM验证候选对（并发处理）"""
    # 构建LLM prompts
    prompts = []
    for node_id_1, node_id_2, embedding_sim in candidate_pairs:
        prompts.append({
            "prompt": self._build_head_dedup_prompt(node_id_1, node_id_2),
            "metadata": {
                "node_id_1": node_id_1,
                "node_id_2": node_id_2,
                "embedding_similarity": embedding_sim
            }
        })
    
    # 并发调用LLM
    logger.info(f"  Processing {len(prompts)} LLM validation calls...")
    llm_results = self._concurrent_llm_calls(prompts)
    
    # 解析结果
    merge_mapping = {}
    metadata = {}
    
    for result in llm_results:
        meta = result.get("metadata", {})
        response = result.get("response", "")
        
        parsed = self._parse_coreference_response(response)
        is_coreferent = parsed.get("is_coreferent", False)
        confidence = parsed.get("confidence", 0.0)
        rationale = parsed.get("rationale", "")
        
        # 只合并高置信度的结果
        if is_coreferent and confidence >= threshold:
            node_id_1 = meta["node_id_1"]
            node_id_2 = meta["node_id_2"]
            
            canonical = min(node_id_1, node_id_2, key=lambda x: int(x.split('_')[1]))
            duplicate = node_id_2 if canonical == node_id_1 else node_id_1
            
            merge_mapping[duplicate] = canonical
            metadata[duplicate] = {
                "rationale": rationale,
                "confidence": confidence,
                "embedding_similarity": meta.get("embedding_similarity", 0.0)
            }
    
    return merge_mapping, metadata

def _parse_coreference_response(self, response: str) -> dict:
    """解析LLM的共指判断响应"""
    try:
        parsed = json_repair.loads(response)
        return {
            "is_coreferent": parsed.get("is_coreferent", False),
            "confidence": float(parsed.get("confidence", 0.0)),
            "rationale": parsed.get("rationale", "")
        }
    except Exception as e:
        logger.warning(f"Failed to parse LLM response: {e}")
        return {"is_coreferent": False, "confidence": 0.0, "rationale": "Parse error"}
```

---

## 数据一致性保障

### 1. 事务性保证

```python
def _merge_head_nodes_with_rollback(self, merge_mapping: Dict[str, str], metadata: Dict[str, dict]):
    """带回滚机制的节点合并"""
    # 1. 保存图快照（仅元数据，不深拷贝整个图）
    snapshot = {
        "removed_nodes": [],
        "added_edges": [],
        "modified_nodes": []
    }
    
    try:
        for duplicate_id, canonical_id in merge_mapping.items():
            # 记录变更
            snapshot["removed_nodes"].append((duplicate_id, copy.deepcopy(self.graph.nodes[duplicate_id])))
            
            # 执行合并
            self._merge_single_head_node(duplicate_id, canonical_id, metadata, snapshot)
        
        return True
    
    except Exception as e:
        logger.error(f"Error during head merge: {e}, rolling back...")
        self._rollback_merge(snapshot)
        return False

def _rollback_merge(self, snapshot: dict):
    """回滚合并操作"""
    # 恢复删除的节点
    for node_id, node_data in snapshot["removed_nodes"]:
        if node_id not in self.graph:
            self.graph.add_node(node_id, **node_data)
    
    # 删除新增的边
    for u, v, key in snapshot["added_edges"]:
        if self.graph.has_edge(u, v, key):
            self.graph.remove_edge(u, v, key)
    
    # 恢复修改的节点
    for node_id, original_data in snapshot["modified_nodes"]:
        if node_id in self.graph:
            self.graph.nodes[node_id].update(original_data)
```

### 2. 图完整性验证

```python
def validate_graph_integrity_after_head_dedup(self) -> Dict[str, Any]:
    """验证去重后图结构的完整性"""
    issues = {
        "orphan_nodes": [],
        "self_loops": [],
        "dangling_references": [],
        "missing_metadata": []
    }
    
    # 1. 检查孤立节点（无入边也无出边的entity节点）
    for node_id, data in self.graph.nodes(data=True):
        if data.get("label") == "entity":
            in_degree = self.graph.in_degree(node_id)
            out_degree = self.graph.out_degree(node_id)
            if in_degree == 0 and out_degree == 0:
                issues["orphan_nodes"].append(node_id)
    
    # 2. 检查自环
    for u, v in self.graph.edges():
        if u == v:
            issues["self_loops"].append((u, v))
    
    # 3. 检查边引用的节点是否存在
    for u, v, data in self.graph.edges(data=True):
        if u not in self.graph.nodes:
            issues["dangling_references"].append(("head", u, v, data))
        if v not in self.graph.nodes:
            issues["dangling_references"].append(("tail", u, v, data))
    
    # 4. 检查合并元数据的完整性
    for node_id, data in self.graph.nodes(data=True):
        if "head_dedup" in data.get("properties", {}):
            dedup_info = data["properties"]["head_dedup"]
            if "merged_nodes" not in dedup_info or "merge_history" not in dedup_info:
                issues["missing_metadata"].append(node_id)
    
    return issues
```

---

## 性能优化策略

### 1. 分批处理大规模图

```python
def deduplicate_heads_batched(self, batch_size: int = 1000):
    """分批处理大规模图的head去重"""
    candidates = self._collect_head_candidates()
    
    # 分批
    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i + batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}/{(len(candidates) + batch_size - 1)//batch_size}")
        
        # 对每批独立去重
        self.deduplicate_heads_on_subset(batch)
```

### 2. 缓存优化

```python
@lru_cache(maxsize=10000)
def _describe_node_cached(self, node_id: str) -> str:
    """缓存节点描述，避免重复计算"""
    return self._describe_node(node_id)

@lru_cache(maxsize=10000)
def _get_node_embedding_cached(self, node_id: str) -> np.ndarray:
    """缓存节点embedding"""
    description = self._describe_node_cached(node_id)
    return self._get_embedding(description)
```

### 3. 索引加速

```python
def _build_entity_index(self):
    """构建实体名称倒排索引，加速查找"""
    self.entity_name_index = defaultdict(list)
    
    for node_id, data in self.graph.nodes(data=True):
        if data.get("label") == "entity":
            name = data.get("properties", {}).get("name", "")
            normalized = self._normalize_entity_name(name)
            self.entity_name_index[normalized].append(node_id)
```

---

## 风险评估与缓解

### 风险矩阵

| 风险 | 严重性 | 概率 | 缓解措施 |
|------|--------|------|----------|
| 错误合并不同实体 | 🔴 高 | 中 | 1. 严格阈值(≥0.85)<br>2. LLM二次验证<br>3. 人工审核接口 |
| 性能瓶颈（大图） | 🟡 中 | 高 | 1. 分批处理<br>2. 并发LLM调用<br>3. embedding预筛选 |
| 图结构破坏 | 🔴 高 | 低 | 1. 事务性操作<br>2. 完整性验证<br>3. 回滚机制 |
| 元数据丢失 | 🟡 中 | 低 | 1. 完整溯源记录<br>2. 合并历史保存<br>3. chunk信息聚合 |

### 人工审核接口

```python
def export_head_merge_candidates_for_review(
    self,
    output_path: str,
    min_confidence: float = 0.7,
    max_confidence: float = 0.9
):
    """
    导出中等置信度的合并候选，供人工审核
    
    置信度区间 [min_confidence, max_confidence] 的案例需要人工确认
    """
    candidates = []
    
    for node_id, data in self.graph.nodes(data=True):
        dedup_info = data.get("properties", {}).get("head_dedup", {})
        for merge_record in dedup_info.get("merge_history", []):
            confidence = merge_record.get("confidence", 1.0)
            if min_confidence <= confidence <= max_confidence:
                candidates.append({
                    "canonical_node": node_id,
                    "canonical_name": data.get("properties", {}).get("name", ""),
                    "merged_node": merge_record["merged_node_id"],
                    "merged_name": merge_record["merged_node_name"],
                    "confidence": confidence,
                    "rationale": merge_record["rationale"]
                })
    
    # 导出为CSV
    import csv
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=candidates[0].keys() if candidates else [])
        writer.writeheader()
        writer.writerows(candidates)
    
    logger.info(f"Exported {len(candidates)} merge candidates to {output_path}")
```

---

## 使用示例

### 基础用法

```python
# 创建知识图谱构建器
builder = KnowledgeTreeGen(dataset_name="demo", ...)

# 执行文档处理和初步去重
builder.process_document(doc)

# 【新增】执行head节点去重
stats = builder.deduplicate_heads(
    enable_semantic=True,
    similarity_threshold=0.85,
    use_llm_validation=False,  # 快速模式：仅使用embedding
    max_candidates=1000
)

print(f"Merged {stats['total_merges']} head nodes")
print(f"Reduction rate: {stats['total_merges'] / stats['total_candidates'] * 100:.1f}%")

# 验证图完整性
issues = builder.validate_graph_integrity_after_head_dedup()
if any(issues.values()):
    print(f"Warning: Found integrity issues: {issues}")
```

### 高精度模式（使用LLM验证）

```python
stats = builder.deduplicate_heads(
    enable_semantic=True,
    similarity_threshold=0.90,  # 更严格
    use_llm_validation=True,    # 启用LLM二次验证
    max_candidates=500          # 限制LLM调用次数
)
```

### 导出人工审核

```python
builder.export_head_merge_candidates_for_review(
    output_path="output/head_merge_candidates.csv",
    min_confidence=0.70,
    max_confidence=0.90
)
```

---

## 后续优化方向

### 短期（1-2周）

1. **实现基础版本**：
   - 精确匹配去重
   - Embedding-based语义去重
   - 图结构更新逻辑

2. **测试与验证**：
   - 单元测试（每个组件）
   - 集成测试（完整pipeline）
   - 小规模数据验证

### 中期（1个月）

3. **性能优化**：
   - 并发处理优化
   - 缓存机制完善
   - 大规模图分批处理

4. **可观测性增强**：
   - 详细日志记录
   - 中间结果保存
   - 可视化dashboard

### 长期（3个月+）

5. **高级特性**：
   - 主动学习（Active Learning）：模型不确定时请求人工标注
   - 增量去重：新增节点时实时去重
   - 跨社区去重：考虑community结构的全局去重

6. **领域适配**：
   - 领域特定规则（如人名、地名的特殊处理）
   - 多语言支持（跨语言实体链接）
   - 时间感知去重（区分历史实体vs现代实体）

---

## 总结

本方案提供了**专业、完整、可实施**的head节点去重解决方案，核心特点：

✅ **理论基础扎实**：基于NLP中的实体链接（Entity Linking）和共指消解（Coreference Resolution）理论  
✅ **架构设计合理**：两阶段处理（精确+语义），与现有tail去重保持一致  
✅ **实现细节完整**：包含完整代码框架和关键函数实现  
✅ **数据安全可靠**：事务性操作、回滚机制、完整性验证  
✅ **性能可扩展**：支持大规模图的批处理和并发优化  
✅ **可观测可审核**：完整溯源信息、人工审核接口  

**建议实施路径**：
1. 先实现精确匹配去重（快速见效）
2. 再实现embedding-based语义去重（覆盖主要场景）
3. 最后根据需要添加LLM验证（提升精度）

---

**文档版本历史**
- v1.0 (2025-10-27): 初始版本，完整方案设计
