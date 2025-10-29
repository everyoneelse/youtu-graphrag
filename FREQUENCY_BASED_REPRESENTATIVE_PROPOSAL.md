# 基于频率的 Representative 选择方案

## 问题描述

当前 head deduplication 中的问题：

### 场景
```
实体 A 与多个实体相似度都超过阈值：
- Pair (A, B): similarity = 0.90 → LLM 判断 coreferent, preferred = B
- Pair (A, C): similarity = 0.88 → LLM 判断 coreferent, preferred = C
- Pair (A, D): similarity = 0.87 → LLM 判断 coreferent, preferred = D
```

### 当前行为

使用 Union-Find 处理传递性：
```python
union(A, B): A -> B
union(A, C): B -> C, 结果 A -> C
union(A, D): C -> D, 结果 A -> D, B -> D, C -> D
```

**最终结果**：D 成为 representative（不一定合理）

### 问题

1. **A 是高频实体**：如果 A 出现在多个 pair 中，说明 A 可能是：
   - 更标准/通用的名称
   - 在图中关系更丰富
   - 在语料中出现更多次

2. **LLM 视野局限**：LLM 在两两比较时看不到全局信息，不知道 A 是高频实体

3. **链式传递问题**：最后一个被处理的实体意外成为 representative

## 解决方案

### 方案 1：频率优先（推荐）

**核心思想**：高频实体应该作为 representative

```python
def _revise_representative_with_frequency_priority(
    self,
    merge_mapping: Dict[str, str],
    metadata: Dict[str, dict]
) -> Dict[str, str]:
    """
    Frequency-aware representative selection.
    
    If an entity appears in multiple pairs (high frequency),
    it should become the representative.
    """
    from collections import defaultdict
    
    # Step 1: 统计每个实体出现的频率
    entity_frequency = defaultdict(int)
    for duplicate, canonical in merge_mapping.items():
        entity_frequency[duplicate] += 1
        entity_frequency[canonical] += 1
    
    # Step 2: 识别高频实体（出现在多个 pair 中）
    HIGH_FREQ_THRESHOLD = 3  # 出现在3个以上pair中视为高频
    high_freq_entities = {
        entity for entity, freq in entity_frequency.items()
        if freq >= HIGH_FREQ_THRESHOLD
    }
    
    logger.info(f"Identified {len(high_freq_entities)} high-frequency entities")
    
    # Step 3: 使用 Union-Find，但优先选择高频实体作为 root
    parent = {}
    rank = {}  # 用于优化 union 操作
    
    def find(x):
        if x not in parent:
            parent[x] = x
            rank[x] = 0
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    
    def union(entity1, entity2):
        """Union with frequency priority."""
        root1, root2 = find(entity1), find(entity2)
        if root1 == root2:
            return
        
        # 优先选择高频实体作为 root
        is_high_freq_1 = root1 in high_freq_entities
        is_high_freq_2 = root2 in high_freq_entities
        
        if is_high_freq_1 and not is_high_freq_2:
            # root1 是高频，root2 不是 → root1 作为 representative
            parent[root2] = root1
            logger.debug(f"Union: {root2} -> {root1} (high-freq priority)")
        elif is_high_freq_2 and not is_high_freq_1:
            # root2 是高频，root1 不是 → root2 作为 representative
            parent[root1] = root2
            logger.debug(f"Union: {root1} -> {root2} (high-freq priority)")
        else:
            # 都是高频或都不是高频 → 使用 rank 优化
            if rank[root1] < rank[root2]:
                parent[root1] = root2
            elif rank[root1] > rank[root2]:
                parent[root2] = root1
            else:
                parent[root2] = root1
                rank[root1] += 1
    
    # Step 4: Apply all merge decisions
    for duplicate, canonical in merge_mapping.items():
        union(duplicate, canonical)
    
    # Step 5: Build final mapping
    revised_mapping = {}
    for duplicate, original_canonical in merge_mapping.items():
        final_canonical = find(duplicate)
        if duplicate != final_canonical:
            revised_mapping[duplicate] = final_canonical
            
            if final_canonical != original_canonical:
                logger.info(
                    f"Representative changed: {duplicate} -> {original_canonical} "
                    f"revised to {duplicate} -> {final_canonical} "
                    f"(freq: {entity_frequency[final_canonical]})"
                )
    
    return revised_mapping
```

### 方案 2：度中心性优先

**核心思想**：图中关系更多的实体作为 representative

```python
def _get_entity_centrality(self, entity_id: str) -> int:
    """Get entity's degree (number of relations in graph)."""
    if entity_id not in self.graph:
        return 0
    return self.graph.degree(entity_id)

def union_with_centrality_priority(entity1, entity2):
    """Prefer entity with higher graph centrality."""
    root1, root2 = find(entity1), find(entity2)
    if root1 == root2:
        return
    
    centrality1 = self._get_entity_centrality(root1)
    centrality2 = self._get_entity_centrality(root2)
    
    if centrality1 > centrality2:
        parent[root2] = root1
    else:
        parent[root1] = root2
```

### 方案 3：混合策略（最佳）

**综合考虑**：
1. 高频实体（出现在多个 pair 中）
2. 图中心性（关系数量）
3. LLM 的选择

```python
def _calculate_entity_score(self, entity_id: str, frequency: int) -> float:
    """
    Calculate entity's score for representative selection.
    
    Score = frequency * α + centrality * β + name_quality * γ
    """
    # 频率得分
    freq_score = frequency
    
    # 中心性得分（图中的关系数量）
    centrality = self.graph.degree(entity_id) if entity_id in self.graph else 0
    
    # 名称质量得分（长度适中、包含类型信息等）
    name = self.graph.nodes[entity_id].get("properties", {}).get("name", "")
    name_score = len(name)  # 简化版：更长的名称可能更规范
    
    # 权重
    α, β, γ = 2.0, 1.0, 0.1
    
    return freq_score * α + centrality * β + name_score * γ

def union_with_score_priority(entity1, entity2):
    """Union based on comprehensive score."""
    root1, root2 = find(entity1), find(entity2)
    if root1 == root2:
        return
    
    score1 = self._calculate_entity_score(root1, entity_frequency[root1])
    score2 = self._calculate_entity_score(root2, entity_frequency[root2])
    
    if score1 > score2:
        parent[root2] = root1
    else:
        parent[root1] = root2
```

## 实现建议

### 短期（立即可做）

实现**方案 1：频率优先**，因为：
1. 简单直接，易于理解
2. 解决最主要的问题
3. 不需要额外信息

### 中期（优化）

实现**方案 3：混合策略**，因为：
1. 更全面的考虑
2. 可调节权重
3. 更好的效果

### 配置选项

```yaml
head_dedup:
  representative_selection:
    strategy: "frequency_priority"  # "llm_only" | "frequency_priority" | "mixed"
    high_frequency_threshold: 3  # 出现几次算高频
    centrality_weight: 1.0  # 中心性权重
    frequency_weight: 2.0   # 频率权重
```

## 示例对比

### 原始实现
```
输入 pairs:
- (Apple Inc., Apple)       → LLM: Apple
- (Apple Inc., Apple Corp.) → LLM: Apple Corp.
- (Apple Inc., AAPL)        → LLM: AAPL

结果: Apple Inc. -> AAPL (不合理)
```

### 频率优先
```
检测到 "Apple Inc." 是高频实体（出现3次）

结果: Apple -> Apple Inc.
      Apple Corp. -> Apple Inc.
      AAPL -> Apple Inc.

✓ 更合理！
```

## 潜在问题

1. **如何定义"高频"阈值**？
   - 建议：根据数据集规模自适应
   - 小数据集：threshold = 2
   - 大数据集：threshold = 5

2. **循环引用怎么办**？
   - Union-Find 天然处理循环

3. **LLM 选择是否应该完全信任**？
   - 不完全信任，用频率/中心性作为补充

## 总结

用户的观察非常准确！当一个实体出现在多个 pair 中时，说明它很可能是更标准/通用的表述，应该优先选为 representative。

建议立即实现**方案 1：频率优先**，解决这个问题。
