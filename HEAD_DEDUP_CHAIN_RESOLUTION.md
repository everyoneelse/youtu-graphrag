# Head Dedup中的链式等价处理方案

## 问题描述

在head_dedup中，LLM对entity进行两两(pair)去重时，可能会产生**链式等价关系**：

```
例如：
LLM判断: A -> B  (A是duplicate, B是canonical)
LLM判断: B -> C  (B是duplicate, C是canonical)

问题: 此时A最终应该指向谁？
答案: A应该指向C (传递闭包)
```

如果直接使用原始的`merge_mapping`，会导致：
- A -> B
- B -> C
- 但B即将被删除，导致A的映射失效！

## 解决方案汇总

项目中有**两种主要方案**来解决这个问题：

### 方案1: 并查集（Union-Find）- 推荐 ✅

**位置**: 
- `head_dedup_llm_driven_representative.py` → `_revise_representative_selection_llm_driven()`
- `models/constructor/kt_gen.py` → `_choose_representative_by_frequency_llm_driven()`

**核心思想**: 使用并查集数据结构，自动处理传递闭包，并且支持频率优先选择representative。

**实现代码**:

```python
def _revise_representative_selection_llm_driven(
    self, 
    merge_mapping: Dict[str, str],  # 原始的 {duplicate: canonical}
    metadata: Dict[str, dict]
) -> Dict[str, str]:
    """
    使用并查集处理链式等价，并基于频率选择最佳representative
    
    Example:
      输入: {A: B, B: C, D: C}
      输出: {A: C, B: C, D: C}  (C是高频entity，成为最终representative)
    """
    from collections import defaultdict
    
    # Step 1: 统计每个entity出现的频率
    entity_frequency = defaultdict(int)
    for duplicate, canonical in merge_mapping.items():
        entity_frequency[duplicate] += 1
        entity_frequency[canonical] += 1
    
    # Step 2: 识别高频entity (更可能是标准名称)
    max_freq = max(entity_frequency.values()) if entity_frequency else 0
    HIGH_FREQ_THRESHOLD = max(2, min(3, max_freq - 1))
    
    high_freq_entities = {
        entity for entity, freq in entity_frequency.items()
        if freq >= HIGH_FREQ_THRESHOLD
    }
    
    # Step 3: 构建并查集
    parent = {}
    rank = {}
    
    def find(x):
        """带路径压缩的查找 - 核心！"""
        if x not in parent:
            parent[x] = x
            rank[x] = 0
        if parent[x] != x:
            parent[x] = find(parent[x])  # 路径压缩
        return parent[x]
    
    def union(entity1, entity2):
        """带频率优先的合并"""
        root1, root2 = find(entity1), find(entity2)
        if root1 == root2:
            return
        
        # 高频entity优先成为representative
        is_high_freq_1 = root1 in high_freq_entities
        is_high_freq_2 = root2 in high_freq_entities
        
        if is_high_freq_1 and not is_high_freq_2:
            parent[root2] = root1
        elif is_high_freq_2 and not is_high_freq_1:
            parent[root1] = root2
        elif is_high_freq_1 and is_high_freq_2:
            # 都是高频，选择频率更高的
            if entity_frequency[root1] >= entity_frequency[root2]:
                parent[root2] = root1
            else:
                parent[root1] = root2
        else:
            # 都不是高频，使用rank优化
            if rank[root1] < rank[root2]:
                parent[root1] = root2
            elif rank[root1] > rank[root2]:
                parent[root2] = root1
            else:
                parent[root2] = root1
                rank[root1] += 1
    
    # Step 4: 应用所有merge决策
    for duplicate, canonical in merge_mapping.items():
        union(duplicate, canonical)
    
    # Step 5: 构建最终映射 - 关键步骤！
    revised_mapping = {}
    for duplicate, original_canonical in merge_mapping.items():
        final_canonical = find(duplicate)  # 通过find获取最终的canonical
        if duplicate != final_canonical:
            revised_mapping[duplicate] = final_canonical
    
    return revised_mapping
```

**工作流程示例**:

```python
# 输入
merge_mapping = {
    'entity_1': 'entity_2',  # LLM判断: 1->2
    'entity_2': 'entity_3',  # LLM判断: 2->3
    'entity_4': 'entity_3',  # LLM判断: 4->3
}

# 处理过程:
# union(1, 2): parent[1] = 2
# union(2, 3): parent[2] = 3
# union(4, 3): parent[4] = 3

# find(1) 调用链:
#   parent[1] = 2
#   parent[2] = 3
#   parent[3] = 3 (root)
#   返回 3，同时压缩路径: parent[1] = 3

# 最终输出
revised_mapping = {
    'entity_1': 'entity_3',  # ✓ 正确指向最终root
    'entity_2': 'entity_3',  # ✓ 正确指向最终root
    'entity_4': 'entity_3',  # ✓ 正确指向最终root
}
```

**优点**:
- ✅ 自动处理任意长度的链式等价
- ✅ 支持频率优先选择representative
- ✅ 时间复杂度接近O(n)（带路径压缩）
- ✅ 逻辑清晰，不易出错

---

### 方案2: 分组重选（Grouping）

**位置**: 
- `head_dedup_alias_implementation.py` → `_revise_representative_selection()`

**核心思想**: 将所有相关entity分组，然后在组内重新选择最佳representative。

**实现代码**:

```python
def _revise_representative_selection(
    self, 
    merge_mapping: Dict[str, str]
) -> Dict[str, str]:
    """
    通过分组方式处理链式等价
    
    注意: 这种方式只能处理一层传递，不能处理多层链式！
    """
    from collections import defaultdict
    
    # Step 1: 按canonical分组
    groups = defaultdict(set)
    for dup, can in merge_mapping.items():
        groups[can].add(dup)
        groups[can].add(can)
    
    # Step 2: 为每组重新选择representative
    revised_mapping = {}
    
    for original_canonical, node_set in groups.items():
        if len(node_set) <= 1:
            continue
        
        # 评估每个节点作为representative的得分
        node_scores = []
        for node_id in node_set:
            if node_id not in self.graph:
                continue
            
            props = self.graph.nodes[node_id].get("properties", {})
            
            # 计算综合得分
            score = (
                self.graph.out_degree(node_id) * 100 +     # 出度最重要
                self.graph.in_degree(node_id) * 50 +       # 入度也重要
                len(props.get("name", "")) * 10 +          # 名称长度
                len(props.get("chunk_ids", [])) * 20 +     # 证据数量
                -int(node_id.split('_')[1]) * 0.1          # 早期ID略优
            )
            
            node_scores.append((score, node_id))
        
        # 选择得分最高的作为representative
        if node_scores:
            node_scores.sort(reverse=True)
            best_representative = node_scores[0][1]
            
            # 其他节点都指向它
            for node_id in node_set:
                if node_id != best_representative:
                    revised_mapping[node_id] = best_representative
    
    return revised_mapping
```

**局限性**:
- ⚠️ 只能处理一层传递（如果有A->B->C->D这样的长链，需要多次迭代）
- ⚠️ 不考虑频率信息
- ⚠️ 分组逻辑可能遗漏某些传递关系

---

## 推荐使用方式

### 对于LLM驱动的去重（推荐）

使用**方案1（并查集）**，位于：
- `head_dedup_llm_driven_representative.py`
- `models/constructor/kt_gen.py`

调用方式:
```python
# 在LLM去重之后
merge_mapping = self._perform_llm_dedup(...)  # 原始的pair-wise结果

# 应用并查集处理链式等价
revised_mapping = self._revise_representative_selection_llm_driven(
    merge_mapping, 
    metadata
)

# 使用revised_mapping进行merge
self._merge_head_nodes_with_alias(revised_mapping, metadata)
```

### 对于Alias实现

使用**方案2（分组）**，位于：
- `head_dedup_alias_implementation.py`

但建议替换为方案1以获得更好的效果。

---

## 关键要点总结

### 问题核心
```python
# ❌ 错误: 直接使用原始mapping
merge_mapping = {'A': 'B', 'B': 'C'}
# 问题: B会被删除，A -> B的映射失效！

# ✅ 正确: 解析传递闭包
revised_mapping = {'A': 'C', 'B': 'C'}
# A和B都直接指向最终的root节点C
```

### 解决方案
1. **并查集 (Union-Find)**: 
   - 通过`find(x)`函数获取每个duplicate_id的最终canonical_id
   - 自动处理任意长度的链式关系
   - 支持频率优先策略

2. **核心代码**:
```python
for duplicate_id, original_canonical in merge_mapping.items():
    final_canonical = find(duplicate_id)  # 获取最终的can_id
    if duplicate_id != final_canonical:
        revised_mapping[duplicate_id] = final_canonical
```

### 实际应用
- 在`merge_mapping`应用前，必须先调用revision函数
- revision函数会返回处理过传递闭包的新mapping
- 使用新mapping进行实际的节点合并操作

---

## 代码位置索引

| 文件 | 函数 | 方法 | 备注 |
|------|------|------|------|
| `head_dedup_llm_driven_representative.py` | `_revise_representative_selection_llm_driven()` | 并查集+频率 | ✅ 推荐 |
| `models/constructor/kt_gen.py` | `_choose_representative_by_frequency_llm_driven()` | 并查集+频率 | ✅ 推荐 |
| `head_dedup_alias_implementation.py` | `_revise_representative_selection()` | 分组重选 | ⚠️ 有局限 |
| `head_deduplication_reference.py` | `_merge_head_nodes()` | 直接应用 | ❌ 无处理 |
| `kt_gen_new_functions.py` | `_merge_head_nodes_with_alias()` | 直接应用 | ❌ 无处理 |
