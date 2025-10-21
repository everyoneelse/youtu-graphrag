# 对话记录：关键词去重逻辑 - 按 Community 还是全局

**日期**: 2025-10-21 01:10:47  
**分支**: cursor/deduplicate-keywords-by-community-326c  
**主题**: 关键词去重是头尾一致的还是按 community 去重

---

## 问题

**用户提问**:
> 对于关键词的去重是 头尾一致的吗？还是属于同一个community的keywords的去重

---

## 回答

通过代码分析，**关键词的去重是按照 community 进行的**。

### 代码分析

查看 `models/constructor/kt_gen.py` 中的 `_deduplicate_keyword_nodes` 方法（从1509行开始），去重逻辑如下：

```python
# 第1517-1527行
community_to_keywords: dict = defaultdict(list)
for keyword_node_id in list(keyword_mapping.keys()):
    if keyword_node_id not in self.graph:
        continue
    for _, target, _, data in self.graph.out_edges(keyword_node_id, keys=True, data=True):
        if isinstance(data, dict) and data.get("relation") == "keyword_of":
            community_to_keywords[target].append(keyword_node_id)

if not community_to_keywords:
    return
```

```python
# 第1544-1548行
for community_id, keyword_ids in community_to_keywords.items():
    keyword_ids = [kw for kw in keyword_ids if kw in self.graph]
    if len(keyword_ids) <= 1:
        continue
```

### 核心逻辑

1. **按 community 分组**: 首先通过 `keyword_of` 关系，将所有关键词按照它们所属的 **community** 进行分组（第1517-1523行）

2. **community 内部去重**: 然后**对每个 community 内部的关键词单独进行去重**（第1544行循环）

3. **不跨 community**: 不同 community 的关键词不会互相去重

### 结论

这是 **属于同一个 community 的 keywords 的去重**，而不是全局的头尾一致去重。这也符合当前分支名称 `cursor/deduplicate-keywords-by-community-326c` 的含义。

---

## 相关文件

- `models/constructor/kt_gen.py`: 第1509-1650行左右，`_deduplicate_keyword_nodes` 方法
- `offline_semantic_dedup.py`: 离线语义去重脚本

## 相关分支

- 当前分支: `cursor/deduplicate-keywords-by-community-326c`
- 相关历史分支:
  - `cursor/add-keyword-semantic-deduplication-by-chunk-context-3891`
  - `cursor/print-keyword-deduplication-count-7e2b`
  - `cursor/check-for-duplicate-community-keywords-faac`
