# Head去重与offline_semantic_dedup.py集成说明

**日期**: 2025-10-27  
**问题**: Head去重功能是否可以配合offline_semantic_dedup.py使用？  
**答案**: ✅ 可以！已完成集成

---

## ✅ 集成完成

Head去重功能已经集成到`offline_semantic_dedup.py`，可以对现有图谱进行离线head去重。

---

## 📊 当前状态

### 继承关系

```
KTBuilder (models/constructor/kt_gen.py)
  ├─ deduplicate_heads()           ← 新增的head去重
  ├─ triple_deduplicate()          ← 现有tail去重
  ├─ _deduplicate_keyword_nodes()  ← 现有keyword去重
  └─ ... 其他方法
  
OfflineSemanticDeduper (offline_semantic_dedup.py)
  └─ 继承自 KTBuilder
```

### 当前offline_semantic_dedup.py暴露的方法

```python
class OfflineSemanticDeduper(KTBuilder):
    # 暴露的方法
    triple_deduplicate = KTBuilder.triple_deduplicate
    _deduplicate_keyword_nodes = KTBuilder._deduplicate_keyword_nodes
    _semantic_dedup_enabled = KTBuilder._semantic_dedup_enabled
    
    # ⚠️ deduplicate_heads 没有暴露！
```

---

## 🚀 使用方法

### 基本用法

```bash
# 离线对图谱进行去重（包括tail、keyword、head去重）
python offline_semantic_dedup.py \
    --graph output/graphs/demo.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_deduped.json
```

### 启用Head去重

确保配置文件中启用了head去重：

```yaml
# config/base_config.yaml
construction:
  semantic_dedup:
    enabled: true
    
    head_dedup:
      enabled: true  # ← 确保为true
      enable_semantic: true
      similarity_threshold: 0.85
      use_llm_validation: false
      max_candidates: 1000
```

### 完整示例

```bash
# 1. 准备图谱和chunks
# （假设已有构建好的图谱）

# 2. 运行离线去重（包含head去重）
python offline_semantic_dedup.py \
    --graph output/graphs/my_graph.json \
    --chunks output/chunks/my_chunks.txt \
    --output output/graphs/my_graph_fully_deduped.json \
    --force-enable

# 输出示例：
# [INFO] Running triple semantic deduplication
# [INFO] Running keyword semantic deduplication
# [INFO] Running head entity deduplication  ← 新增
# [INFO] Head dedup: 1000 entities → 850 entities (merged 150, reduced 15.0%)
# [INFO] Edges: 5000 → 4800 | Keyword nodes: 200 → 180 | Entity nodes: 1000 → 850
```

---

## 🔧 实现细节

### 修改内容

#### 1. 暴露deduplicate_heads方法

```python
# offline_semantic_dedup.py (第54行)
class OfflineSemanticDeduper(KTBuilder):
    # Expose methods
    triple_deduplicate = KTBuilder.triple_deduplicate
    _deduplicate_keyword_nodes = KTBuilder._deduplicate_keyword_nodes
    _semantic_dedup_enabled = KTBuilder._semantic_dedup_enabled
    deduplicate_heads = KTBuilder.deduplicate_heads  # ✅ 新增
```

#### 2. 在main()中调用head去重

```python
# offline_semantic_dedup.py (第242-259行)
def main() -> None:
    # ... 前面的tail和keyword去重 ...
    
    # Head entity deduplication
    head_dedup_config = getattr(config.construction.semantic_dedup, 'head_dedup', None)
    if head_dedup_config and getattr(head_dedup_config, 'enabled', False):
        logger.info("Running head entity deduplication")
        try:
            head_stats = deduper.deduplicate_heads()
            logger.info(
                "Head dedup: %d entities → %d entities (merged %d, reduced %.1f%%)",
                head_stats['initial_entity_count'],
                head_stats['final_entity_count'],
                head_stats['total_merges'],
                head_stats['reduction_rate']
            )
        except Exception as e:
            logger.error(f"Head deduplication failed: {e}")
            logger.info("Continuing without head deduplication...")
    else:
        logger.info("Head entity deduplication is disabled; skipping")
```

#### 3. 统计信息更新

```python
# 输出统计（第265-273行）
logger.info(
    "Edges: %d → %d | Keyword nodes: %d → %d | Entity nodes: %d → %d",
    original_edge_count, deduped_edge_count,
    original_keyword_count, deduped_keyword_count,
    original_entity_count, deduped_entity_count  # ✅ 新增
)
```

---

## 📋 去重Pipeline

### 完整流程

```
1. Tail去重 (triple_deduplicate)
   ↓ 对共享(head, relation)的tail列表去重
   ↓ 基于文本chunk上下文

2. Keyword去重 (_deduplicate_keyword_nodes)
   ↓ 对关键词节点去重
   ↓ 基于社区聚类

3. Head去重 (deduplicate_heads) ✅ 新增
   ↓ 对实体节点全局去重
   ↓ 基于图关系上下文
   ↓ 两阶段：精确匹配 + 语义相似度

4. 保存最终图谱
   ↓ 包含所有去重结果
```

### 为什么是这个顺序？

1. **先Tail去重**: 
   - 清理每个(head, relation)下的重复tail
   - 利用文本chunk进行消歧

2. **再Keyword去重**:
   - 合并重复的关键词节点

3. **最后Head去重**:
   - 此时图结构已相对干净
   - 可以利用更准确的关系进行判断
   - 避免在混乱的图上做head合并

---

## ⚙️ 配置说明

### Head去重相关配置

```yaml
# config/base_config.yaml
construction:
  semantic_dedup:
    enabled: true  # 总开关
    
    head_dedup:
      enabled: true  # Head去重开关
      
      # 语义去重配置
      enable_semantic: true
      similarity_threshold: 0.85
      
      # LLM验证（可选，更准确但更慢）
      use_llm_validation: false
      
      # 性能配置
      max_candidates: 1000
      candidate_similarity_threshold: 0.75
      max_relations_context: 10
      
      # Human review（可选）
      export_review: false
      review_confidence_range: [0.70, 0.90]
      review_output_dir: "output/review"
```

### 配置建议
| 场景 | 推荐配置 |
|------|----------|
| 快速测试 | `enable_semantic: false` (仅精确匹配) |
| 平衡模式 | `use_llm_validation: false, threshold: 0.85` |
| 高精度模式 | `use_llm_validation: true, threshold: 0.90` |
| 大图谱 | `max_candidates: 500, threshold: 0.90` |

---

## ✅ 优势

### 离线去重的好处

1. **灵活性**: 可以对已有图谱反复实验不同参数
2. **安全性**: 不影响原始图谱，生成新文件
3. **可重复**: 相同配置产生相同结果
4. **效率**: 可以只对需要的部分进行去重

### Head去重的价值

1. **全局视角**: 跨relation合并重复实体
2. **利用图结构**: 基于关系网络而非单个文本
3. **提升查询**: 减少实体冗余，提高检索准确度
4. **改善可视化**: 更简洁的图谱结构

---

## 📝 实际案例

### 案例1: 已有图谱去重

```bash
# 场景：构建时没有启用head去重，现在想补充
python offline_semantic_dedup.py \
    --graph output/graphs/my_old_graph.json \
    --chunks output/chunks/my_chunks.txt \
    --output output/graphs/my_graph_with_head_dedup.json

# 配置文件中启用head_dedup.enabled: true
```

### 案例2: 实验不同参数

```bash
# 先尝试保守参数
# config/base_config.yaml: similarity_threshold: 0.90
python offline_semantic_dedup.py \
    --graph original.json \
    --chunks chunks.txt \
    --output deduped_conservative.json

# 再尝试激进参数
# config/base_config.yaml: similarity_threshold: 0.80
python offline_semantic_dedup.py \
    --graph original.json \
    --chunks chunks.txt \
    --output deduped_aggressive.json

# 对比两个结果，选择最佳参数
```

### 案例3: 只做head去重

```bash
# 场景：tail和keyword已经去重过了，只想做head去重
# 1. 配置文件中禁用tail和keyword去重
# config/base_config.yaml:
#   semantic_dedup:
#     enabled: true  # 保持true
#     # 注释掉或禁用tail/keyword相关配置
#     head_dedup:
#       enabled: true

# 2. 运行
python offline_semantic_dedup.py \
    --graph already_tail_deduped.json \
    --chunks chunks.txt \
    --output fully_deduped.json
```

---

## 🎯 总结

### ✅ 已完成

1. **暴露方法**: `deduplicate_heads` 已添加到 `OfflineSemanticDeduper`
2. **集成调用**: main()函数中已集成head去重流程
3. **配置支持**: 支持所有head去重配置参数
4. **错误处理**: head去重失败时不影响其他去重
5. **统计输出**: 显示entity节点数量变化

### 使用步骤

1. ✅ 确保配置文件中 `head_dedup.enabled: true`
2. ✅ 运行 `python offline_semantic_dedup.py --graph ... --chunks ... --output ...`
3. ✅ 查看输出统计，确认head去重效果

### 兼容性

- ✅ 向后兼容：如果`head_dedup.enabled: false`，行为与之前完全一致
- ✅ 错误容忍：head去重失败时，其他去重仍正常进行
- ✅ 配置灵活：所有head去重参数都可配置

---

**状态**: ✅ 完成  
**测试**: 建议在小图谱上验证  
**文档**: 本文档

**修改文件**:
- `offline_semantic_dedup.py` (3处修改)
- `OFFLINE_DEDUP_INTEGRATION.md` (本文档)
