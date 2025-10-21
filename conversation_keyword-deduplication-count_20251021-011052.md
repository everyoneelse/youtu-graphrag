# 对话记录：关键词去重计数功能

**日期时间**: 2025-10-21 01:10:52  
**主题**: 在关键词去重过程中添加待处理个数的打印功能

---

## 用户请求

在进行keywords去重的时候，是否可以打印出待处理的个数

---

## 解决方案

### 问题分析

用户希望在关键词去重过程中，能够看到待处理的关键词数量，以便了解工作量和进度。

### 实现步骤

通过搜索代码库，找到了关键词去重的主要实现位置：

1. **主要去重函数**: `models/constructor/kt_gen.py` 中的 `_deduplicate_keyword_nodes` 方法
2. **离线去重脚本**: `offline_semantic_dedup.py`

### 代码修改

#### 1. 在 `models/constructor/kt_gen.py` 中的修改

在 `_deduplicate_keyword_nodes` 函数中添加了两处日志打印：

**第一处：总体统计**（第1530行后）
```python
# 打印待处理的关键词总数
total_keywords = sum(len(kws) for kws in community_to_keywords.values())
logger.info(f"开始关键词去重，共 {len(community_to_keywords)} 个社区，总计 {total_keywords} 个关键词待处理")
```

**第二处：每个社区的统计**（第1547行后）
```python
# 打印当前社区待处理的关键词数量
logger.info(f"处理社区 {community_id}，包含 {len(keyword_ids)} 个关键词")
```

#### 2. 在 `offline_semantic_dedup.py` 中的修改

在关键词去重开始前添加统计信息（第190行）：
```python
if keyword_mapping:
    logger.info(f"检测到 {len(keyword_mapping)} 个关键词待去重")
    deduper._deduplicate_keyword_nodes(keyword_mapping)
```

### 效果展示

修改后，运行关键词去重时会输出类似以下的日志信息：

```
检测到 156 个关键词待去重
开始关键词去重，共 10 个社区，总计 156 个关键词待处理
处理社区 comm_4_0，包含 15 个关键词
处理社区 comm_4_1，包含 23 个关键词
处理社区 comm_4_2，包含 18 个关键词
...
```

### 技术细节

1. **总数计算**: 通过遍历 `community_to_keywords` 字典，累加所有社区的关键词数量
2. **社区级别统计**: 在处理每个社区的循环开始时，打印该社区的关键词数量
3. **日志级别**: 使用 `logger.info` 级别，确保在正常运行时可见

### 相关文件

- `models/constructor/kt_gen.py`: 主要的关键词去重逻辑
- `offline_semantic_dedup.py`: 离线语义去重脚本
- `utils/tree_comm.py`: 社区检测和关键词提取相关功能

---

## 后续建议

1. 可以考虑添加去重完成后的统计信息（如：去重前后的数量对比）
2. 可以添加进度条显示（如使用 tqdm）
3. 可以添加每个社区去重的耗时统计

---

## 技术栈

- Python
- NetworkX (图处理)
- 日志系统 (logger)
- 语义去重 (Semantic Deduplication)
