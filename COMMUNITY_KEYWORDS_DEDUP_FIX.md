# Community Keywords 重复问题修复

## 问题描述

在 youtu-graphrag 中，community 的 keywords 存在可能重复的问题。

## 根本原因

在 `models/constructor/kt_gen.py` 的 `_deduplicate_keyword_nodes` 方法中（第1517-1523行）：

```python
community_to_keywords: dict = defaultdict(list)
for keyword_node_id in list(keyword_mapping.keys()):
    if keyword_node_id not in self.graph:
        continue
    for _, target, _, data in self.graph.out_edges(keyword_node_id, keys=True, data=True):
        if isinstance(data, dict) and data.get("relation") == "keyword_of":
            community_to_keywords[target].append(keyword_node_id)
```

问题在于：
1. 代码使用 `self.graph.out_edges(keyword_node_id, keys=True, data=True)` 遍历所有出边
2. 在 NetworkX 的 MultiDiGraph 中，同一对节点之间可以有多条边
3. 如果一个 keyword 节点到某个 community 有多条 "keyword_of" 边（虽然理论上不应该，但可能由于某些原因产生），那么这个 keyword_node_id 会被多次 append 到列表中
4. 原代码在第1545行只过滤了不存在的节点，但没有去重：
   ```python
   keyword_ids = [kw for kw in keyword_ids if kw in self.graph]
   ```

## 解决方案

在第1545-1546行添加去重逻辑：

```python
# Deduplicate keyword_ids to prevent duplicate keywords in the same community
keyword_ids = list(dict.fromkeys([kw for kw in keyword_ids if kw in self.graph]))
```

使用 `dict.fromkeys()` 的好处：
- 去除重复元素
- 保持原始顺序（比使用 `set()` 更好）

## 影响范围

此修复影响：
- `models/constructor/kt_gen.py` 中的 `_deduplicate_keyword_nodes` 方法
- 所有使用该方法进行 keyword 去重的流程
- Level 4 社区构建过程（在 `process_level4` 方法中调用）

## 验证

- ✅ Python 语法检查通过
- ✅ 代码逻辑正确性验证
