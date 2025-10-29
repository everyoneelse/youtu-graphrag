# 跨场景合并问题分析与解决方案

## 问题诊断

### 原始LLM判断（正确）：
```python
entity_565 vs entity_666:
  - 同社区: "带宽优化与图像失真控制" ✓
  - 同场景: "化学位移伪影" ✓
  - LLM判断: 合并 ✅ 正确
```

### 汇总结果（存疑）：
```python
entity_403 vs entity_565:
  - 不同社区 ✗
  - 不同场景: "流动伪影" vs "化学位移伪影" ✗
  - 汇总结果: 合并 ⚠️ 存疑
```

## 根本原因：Union-Find导致的跨场景传递

### 当前代码逻辑（head_dedup_llm_driven_representative.py:354-501）

```python
def _revise_representative_selection_llm_driven(self, merge_mapping, metadata):
    # Step 1: 统计频率
    entity_frequency = defaultdict(int)
    for duplicate, canonical in merge_mapping.items():
        entity_frequency[duplicate] += 1
        entity_frequency[canonical] += 1
    
    # Step 2-3: 使用Union-Find合并
    def union(entity1, entity2):
        # 基于频率优先的union
        # 问题：没有检查场景一致性！
        ...
    
    # Step 4: 应用所有merge决策
    for duplicate, canonical in merge_mapping.items():
        union(duplicate, canonical)  # ⚠️ 无条件union
```

### 问题场景

假设LLM给出以下判断：

```python
# Pair 1: 正确判断
565 (化学位移) = 666 (化学位移) ✓

# Pair 2: 可能的其他判断
403 (流动伪影) = XXX

# Pair 3: 如果有任何连接
XXX = 565

# Union-Find传递性结果：
403 → XXX → 565  # ⚠️ 跨场景合并！
```

或者更直接的：

```python
# 如果565出现频率很高（因为是标准术语）
# Union-Find会倾向于让565成为很多实体的代表
# 即使它们场景不同

entity_frequency = {
    'entity_565': 5,  # 高频
    'entity_403': 2,
    'entity_666': 1
}

# 频率优先 → 565成为中心
# 导致403也被合并到565
```

## 解决方案

### 方案1: 添加社区/场景一致性检查（推荐）

```python
def _revise_representative_selection_with_scenario_check(
    self, 
    merge_mapping: Dict[str, str],
    metadata: Dict[str, dict]
) -> Dict[str, str]:
    """
    修订版：添加场景一致性检查
    """
    from collections import defaultdict
    
    # Step 1: 为每个merge对收集场景信息
    def get_entity_community(node_id):
        """获取实体所属的社区"""
        if node_id not in self.graph:
            return None
        
        # 方式1: 从图中查找社区信息
        node_data = self.graph.nodes[node_id]
        community = node_data.get("properties", {}).get("community")
        
        # 方式2: 从关系中推断应用场景
        # 例如，查找 "用于解决" 关系指向的问题
        scenarios = set()
        for _, target, edge_data in self.graph.out_edges(node_id, data=True):
            if edge_data.get("label") in ["用于解决", "解决", "reduces"]:
                scenarios.add(target)
        
        return {
            "community": community,
            "scenarios": scenarios
        }
    
    # Step 2: 构建场景感知的连通分量
    scenario_groups = defaultdict(list)
    
    for duplicate, canonical in merge_mapping.items():
        dup_info = get_entity_community(duplicate)
        can_info = get_entity_community(canonical)
        
        # 检查场景一致性
        if dup_info and can_info:
            # 如果社区相同，或场景有交集
            same_community = dup_info["community"] == can_info["community"]
            scenario_overlap = bool(dup_info["scenarios"] & can_info["scenarios"])
            
            if same_community or scenario_overlap:
                # 场景一致，可以合并
                scenario_key = (dup_info["community"], frozenset(dup_info["scenarios"]))
                scenario_groups[scenario_key].append((duplicate, canonical))
            else:
                # 场景不一致，独立处理
                logger.warning(
                    f"⚠️ Cross-scenario merge detected: {duplicate} -> {canonical}\n"
                    f"   {duplicate}: community={dup_info['community']}, scenarios={dup_info['scenarios']}\n"
                    f"   {canonical}: community={can_info['community']}, scenarios={can_info['scenarios']}\n"
                    f"   Keeping as independent merge (not propagating)"
                )
                # 保留为独立的二元关系，不参与Union-Find
    
    # Step 3: 对每个场景组独立进行Union-Find
    revised_mapping = {}
    
    for scenario_key, pairs in scenario_groups.items():
        # 在同一场景内使用Union-Find
        parent = {}
        rank = {}
        entity_frequency = defaultdict(int)
        
        # 统计本场景内的频率
        for dup, can in pairs:
            entity_frequency[dup] += 1
            entity_frequency[can] += 1
        
        def find(x):
            if x not in parent:
                parent[x] = x
                rank[x] = 0
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(entity1, entity2):
            """场景内的Union-Find，基于频率优先"""
            root1, root2 = find(entity1), find(entity2)
            if root1 == root2:
                return
            
            # 频率高的成为代表
            if entity_frequency[root1] > entity_frequency[root2]:
                parent[root2] = root1
            elif entity_frequency[root1] < entity_frequency[root2]:
                parent[root1] = root2
            else:
                # 频率相同，使用rank
                if rank[root1] < rank[root2]:
                    parent[root1] = root2
                elif rank[root1] > rank[root2]:
                    parent[root2] = root1
                else:
                    parent[root2] = root1
                    rank[root1] += 1
        
        # 在本场景内合并
        for dup, can in pairs:
            union(dup, can)
        
        # 生成本场景的映射
        for dup, _ in pairs:
            final_rep = find(dup)
            if dup != final_rep:
                revised_mapping[dup] = final_rep
    
    logger.info(
        f"✓ Scenario-aware merge: processed {len(scenario_groups)} scenario groups, "
        f"created {len(revised_mapping)} merge mappings"
    )
    
    return revised_mapping
```

### 方案2: 在LLM判断阶段就过滤跨场景候选

```python
def _generate_semantic_candidates_with_scenario_filter(
    self,
    remaining_nodes: List[str],
    max_candidates: int = 1000,
    similarity_threshold: float = 0.75
) -> List[Tuple[str, str, float]]:
    """
    生成候选对，并过滤掉明显跨场景的对
    """
    # 原有的embedding相似度计算
    candidates = self._generate_semantic_candidates(
        remaining_nodes, max_candidates, similarity_threshold
    )
    
    # 添加场景过滤
    filtered_candidates = []
    
    for node1, node2, sim in candidates:
        # 检查社区
        community1 = self.graph.nodes[node1].get("properties", {}).get("community")
        community2 = self.graph.nodes[node2].get("properties", {}).get("community")
        
        # 如果社区相同，或者相似度很高（>0.9），才保留
        if community1 == community2 or sim > 0.9:
            filtered_candidates.append((node1, node2, sim))
        else:
            logger.debug(
                f"Filtered out cross-community pair: {node1} (community={community1}) "
                f"vs {node2} (community={community2}), sim={sim:.3f}"
            )
    
    logger.info(
        f"Scenario filtering: {len(candidates)} -> {len(filtered_candidates)} candidates"
    )
    
    return filtered_candidates
```

### 方案3: 在Prompt中强化场景检查

```python
def _build_head_dedup_prompt_v2(self, node_id_1: str, node_id_2: str) -> str:
    # ... 现有代码 ...
    
    # 添加社区信息到prompt
    community1 = self.graph.nodes[node_id_1].get("properties", {}).get("community", "未知")
    community2 = self.graph.nodes[node_id_2].get("properties", {}).get("community", "未知")
    
    community_prompt = f"""
COMMUNITY INFORMATION:
- Entity 1 belongs to community: {community1}
- Entity 2 belongs to community: {community2}

⚠️ CRITICAL: If entities belong to DIFFERENT communities, they are likely used in 
DIFFERENT SCENARIOS. Even if they describe similar technical operations, consider 
whether they are scenario-specific solutions that should remain separate.
"""
    
    # 插入到prompt中
    return prompt_with_community_warning
```

## 推荐实施方案

### 短期（立即实施）：

**1. 添加跨场景警告日志**

在`_revise_representative_selection_llm_driven`中添加：

```python
def union(entity1, entity2):
    root1, root2 = find(entity1), find(entity2)
    if root1 == root2:
        return
    
    # ⚠️ 添加：检查社区一致性
    comm1 = self.graph.nodes[root1].get("properties", {}).get("community")
    comm2 = self.graph.nodes[root2].get("properties", {}).get("community")
    
    if comm1 != comm2 and comm1 and comm2:
        logger.warning(
            f"⚠️ Cross-community union: {root1} (community={comm1}) "
            f"with {root2} (community={comm2})"
        )
    
    # 原有的union逻辑
    ...
```

**2. 在候选生成阶段添加社区过滤**

使用方案2，过滤掉不同社区的低相似度对。

### 中期（优化）：

**3. 实施完整的场景感知Union-Find**

使用方案1的完整实现。

### 长期（架构优化）：

**4. 层次化去重**

```python
# 第一阶段：场景内去重
for community in communities:
    deduplicate_within_community(community)

# 第二阶段：跨场景去重（更保守）
deduplicate_across_communities(threshold=0.95)  # 更高阈值
```

## 验证方法

### 测试用例

```python
test_cases = [
    {
        "name": "同场景同义词",
        "entities": [
            ("entity_565", "增加读出带宽", "化学位移伪影"),
            ("entity_666", "加大带宽", "化学位移伪影")
        ],
        "expected": "MERGE",
        "confidence": "HIGH"
    },
    {
        "name": "跨场景相似操作",
        "entities": [
            ("entity_403", "提高接收带宽", "流动伪影"),
            ("entity_565", "增加读出带宽", "化学位移伪影")
        ],
        "expected": "KEEP_SEPARATE",
        "confidence": "MEDIUM"
    }
]
```

### 验证检查点

1. ✓ 统计跨社区合并的数量
2. ✓ 人工审查高频实体的合并对象
3. ✓ 检查是否有场景信息丢失
4. ✓ 对比去重前后的社区分布变化

## 总结

**当前问题：**
- Union-Find的无条件传递性导致跨场景合并
- 频率优先可能让高频实体吸收不同场景的实体

**解决思路：**
1. 🎯 **预防**：候选生成阶段过滤跨场景对（方案2）
2. 🎯 **检测**：添加警告日志，识别跨场景合并（短期方案）
3. 🎯 **修正**：场景感知的Union-Find（方案1）
4. 🎯 **指导**：Prompt中强化场景检查（方案3）

**优先级：**
1. 立即实施：方案2（候选过滤）+ 警告日志
2. 短期优化：方案1（场景感知Union-Find）
3. 长期改进：层次化去重架构
