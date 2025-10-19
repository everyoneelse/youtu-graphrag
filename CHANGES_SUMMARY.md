# 去重功能完整改进总结

## 改进内容

本次更新对 `models/constructor/kt_gen.py` 中的语义去重功能进行了全面改进：

### 1. ✅ 聚类算法升级（两处）

#### 改进位置
- `_cluster_candidate_tails` 函数

#### 改进内容
- **从 Single Linkage → Average Linkage**
- 使用 sklearn 的 `AgglomerativeClustering`
- 解决了链式效应问题
- 解决了多 cluster 冲突问题

#### 影响范围
该函数被以下两处调用，**全部受益**：
1. ✅ `_deduplicate_keyword_nodes` - 关键词节点去重
2. ✅ `_semantic_deduplicate_group` - 三元组边去重

### 2. ✅ 性能优化（两处）

#### 改进位置
- `_deduplicate_keyword_nodes` 函数（第 1201-1203 行）
- `_semantic_deduplicate_group` 函数（第 1586-1591 行）

#### 改进内容
```python
# 对于单项 cluster，直接跳过 LLM 调用
if len(cluster_indices) == 1:
    # 直接标记为已处理，不调用 LLM
    processed_indices.add(cluster_indices[0])
    continue
```

#### 性能提升
- 避免不必要的 LLM API 调用
- 节省 token 消耗和时间
- 大规模数据集效果尤其明显

### 3. ✅ 中间结果保存（两处）

#### 改进位置
- `_deduplicate_keyword_nodes` - 保存关键词节点去重过程
- `_semantic_deduplicate_group` + `triple_deduplicate_semantic` - 保存边去重过程

#### 保存内容
每种去重类型保存：
1. **聚类结果**：所有 cluster 及其成员
2. **LLM 分组结果**：每次 LLM 调用的输入和输出
3. **最终合并操作**：保留节点、重复节点、合并理由
4. **统计摘要**：各阶段的统计数据

#### 输出文件
- `{dataset}_dedup_{timestamp}.json` - 关键词节点去重
- `{dataset}_edge_dedup_{timestamp}.json` - 三元组边去重

### 4. ✅ 配置支持

#### 新增配置项
在 `config/base_config.yaml` 中：
```yaml
construction:
  semantic_dedup:
    save_intermediate_results: false  # 启用/禁用
    intermediate_results_path: "output/dedup_intermediate/"  # 可选路径
```

## 修改的函数清单

| 函数名 | 修改类型 | 说明 |
|--------|---------|------|
| `_cluster_candidate_tails` | ✅ 重写 | 升级为 Average Linkage 聚类 |
| `_deduplicate_keyword_nodes` | ✅ 增强 | 添加单项优化 + 中间结果保存 |
| `_semantic_deduplicate_group` | ✅ 增强 | 添加单项优化 + 中间结果保存 |
| `triple_deduplicate_semantic` | ✅ 增强 | 添加中间结果收集和保存逻辑 |

## 影响的去重流程

### 关键词节点去重
**调用链**：
```
_deduplicate_keyword_nodes
  └─> _cluster_candidate_tails (Average Linkage) ✅
  └─> 单项 cluster 优化 ✅
  └─> _llm_semantic_group
  └─> 保存中间结果 ✅
```

### 三元组边去重
**调用链**：
```
triple_deduplicate_semantic
  └─> _deduplicate_exact
  └─> _semantic_deduplicate_group
        └─> _cluster_candidate_tails (Average Linkage) ✅
        └─> 单项 cluster 优化 ✅
        └─> _llm_semantic_group
        └─> 累积中间结果 ✅
  └─> 保存中间结果 ✅
```

## 完整性检查

### ✅ 聚类算法改进
- [x] `_cluster_candidate_tails` 升级为 Average Linkage
- [x] 影响关键词节点去重
- [x] 影响三元组边去重

### ✅ 单项 cluster 优化
- [x] `_deduplicate_keyword_nodes` 添加优化
- [x] `_semantic_deduplicate_group` 添加优化

### ✅ 中间结果保存
- [x] `_deduplicate_keyword_nodes` 保存逻辑
- [x] `_semantic_deduplicate_group` 保存逻辑
- [x] `triple_deduplicate_semantic` 聚合和保存
- [x] 配置文件支持
- [x] 文档完善

### ✅ 文档和工具
- [x] `DEDUP_INTERMEDIATE_RESULTS.md` - 完整功能说明
- [x] `example_analyze_dedup_results.py` - 分析工具
- [x] `config/example_with_dedup_results.yaml` - 配置示例
- [x] `example_intermediate_result_structure.json` - 结构示例

## 使用方法

### 启用新功能
```yaml
# config/base_config.yaml 或你的配置文件
construction:
  semantic_dedup:
    enabled: true
    embedding_threshold: 0.85
    save_intermediate_results: true  # 启用中间结果保存
```

### 运行构建
```bash
# 正常运行你的构建流程
python your_build_script.py
```

### 查看结果
```bash
# 生成的文件
ls output/dedup_intermediate/
# -> hotpot_dedup_20251019_120000.json
# -> hotpot_edge_dedup_20251019_120000.json

# 分析结果
python example_analyze_dedup_results.py output/dedup_intermediate/hotpot_dedup_20251019_120000.json
```

## 测试验证

- [x] 语法检查通过 (`python3 -m py_compile`)
- [x] 聚类算法测试通过
- [x] 文档完整
- [x] 示例代码完整

## 性能影响

### 正面影响
- ✅ 聚类质量提升（Average Linkage 更稳定）
- ✅ LLM 调用减少（跳过单项 cluster）
- ✅ Token 消耗减少
- ✅ 处理速度提升

### 可选开销
- ⚠️ 启用中间结果保存会增加少量内存和 I/O
- ⚠️ 建议仅在调试/分析时启用
- ⚠️ 生产环境可关闭 `save_intermediate_results`

## 向后兼容性

- ✅ 默认配置下行为与之前一致（除了聚类算法改进）
- ✅ 中间结果保存默认关闭
- ✅ 所有改进都可选
- ✅ 不影响现有功能

## 总结

**现在两种去重流程都已完全升级：**

1. ✅ **关键词节点去重** (`_deduplicate_keyword_nodes`)
   - Average Linkage 聚类
   - 单项 cluster 优化
   - 完整中间结果保存

2. ✅ **三元组边去重** (`_semantic_deduplicate_group`)
   - Average Linkage 聚类
   - 单项 cluster 优化
   - 完整中间结果保存

两处使用同一个升级后的 `_cluster_candidate_tails` 函数，确保了一致性！
