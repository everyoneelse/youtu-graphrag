# LLM聚类不一致性检测 - 使用指南

## 快速开始

当你在LLM聚类去重中遇到类似问题时：
- **rationale说要合并，但members只有1个成员**
- **聚类结果与描述不符**

这个新功能会自动检测并警告这些问题。

## 功能说明

### 自动检测

系统会在以下聚类操作后自动检测不一致：

1. **Tail实体去重** - `_cluster_candidate_tails_with_llm()`
2. **关键词去重** - 关键词聚类阶段
3. **边去重** - 边聚类阶段

### 检测内容

**检查模式：**
- ✅ rationale说"合并/一致/等同"，members确实有多个成员 → 正常
- ❌ rationale说"合并/一致/等同"，members只有1个成员 → **不一致！**
- ✅ rationale说"独立/不同/分开"，members只有1个成员 → 正常

**关键词检测（中英文）：**
- 合并：`应该?合并`、`可合并`、`完全一致`、`同义`、`identical`、`equivalent`、`same`
- 分开：`应该?分开`、`保持.*独立`、`不同`、`distinct`、`different`

## 如何使用

### 1. 正常运行去重

无需任何配置改动，系统自动检测：

```bash
python main.py --dataset demo --mode all
```

### 2. 查看日志输出

如果发现不一致，日志会输出警告：

```
WARNING: Clustering inconsistency detected: Cluster 4 has 1 member [10] but rationale says merge: 
'"增加相位编码方向的矩阵"即扩大相位编码步数，与组1/组2所指操作完全一致，信息无差异，可合并。'

WARNING: Found 1 clustering inconsistencies. These are likely LLM output errors.
```

### 3. 检查不一致数量

运行后检查日志：

```bash
# 统计不一致数量
grep "Clustering inconsistency" logs/construction.log | wc -l

# 查看详细信息
grep -A 2 "Clustering inconsistency" logs/construction.log
```

### 4. 分析和处理

**少量不一致（<5%）：**
- 属于正常情况，LLM偶尔会犯错
- 系统会记录但不影响运行
- 可以忽略或手动检查

**大量不一致（>10%）：**
- 需要优化prompt或调整LLM配置
- 参考下面的"优化建议"

## 测试示例

运行测试脚本验证功能：

```bash
python3 test_clustering_inconsistency.py
```

输出示例：

```
================================================================================
测试案例1: 用户报告的截断伪影解决方案去重问题
================================================================================

发现 1 处不一致

❌ 不一致 #3:
   类型: singleton_but_should_merge
   成员: [4]
   引用的组: [0, 1]
   理由: "增加相位编码方向的矩阵"即扩大相位编码步数，与组1/组2所指操作完全一致...
   严重性: high

💡 修复建议:
   - 将成员 [4] 合并到 组1, 组2
```

## 优化建议

### 当不一致率较高时

**1. 调整Prompt（已自动应用）**

系统已经改进了聚类prompt，明确要求rationale与members一致。如果仍有问题，可以进一步调整：

```python
# 在 config/base_config.yaml 中添加自定义prompt
semantic_dedup:
  clustering_llm:
    custom_prompt: "你的自定义聚类prompt..."
```

**2. 更换更强的LLM模型**

```yaml
# config/base_config.yaml
semantic_dedup:
  clustering_llm:
    api_name: "gpt-4"  # 从gpt-3.5升级到gpt-4
    temperature: 0.3   # 降低temperature提高一致性
```

**3. 调整聚类策略**

```yaml
semantic_dedup:
  clustering_method: "embedding"  # 改用embedding聚类，避免LLM错误
  # 或
  clustering_method: "llm"
  embedding_threshold: 0.85  # 提高阈值，减少边界case
```

**4. 启用Few-shot Learning**

在prompt中添加正确示例：

```python
# 在DEFAULT_LLM_CLUSTERING_PROMPT中添加
"CORRECT EXAMPLE:\n"
"Input: [1] 'NYC', [2] 'New York City', [3] 'Paris'\n"
"Output:\n"
"{{\n"
"  \"clusters\": [\n"
"    {{\"members\": [1, 2], \"description\": \"These refer to the same city and should be merged\"}},\n"
"    {{\"members\": [3], \"description\": \"Different city, keep separate\"}}\n"
"  ]\n"
"}}\n"
```

## 常见问题

### Q1: 检测到不一致会影响结果吗？

**A:** 不会自动修改结果。系统只记录警告，不会自动合并。这是为了保证安全性，避免误合并。

### Q2: 如何手动修复不一致？

**A:** 
1. 查看日志找到不一致的cluster ID
2. 检查rationale判断应该合并到哪个组
3. 根据实际情况，可以：
   - 重新运行并调整配置
   - 在后处理阶段手动合并节点
   - 接受现状（如果影响不大）

### Q3: 能否启用自动修复？

**A:** 当前版本为安全考虑，不支持自动修复。未来版本可能会添加：
- 半自动修复（提供建议，用户确认）
- 基于规则的安全修复（只修复明确的case）

### Q4: 如何减少不一致发生？

**A:** 
1. ✅ 使用更强的LLM模型（GPT-4 > GPT-3.5）
2. ✅ 降低temperature（0.3比0.7更稳定）
3. ✅ 提高embedding_threshold（减少需要LLM判断的case）
4. ✅ 添加few-shot examples
5. ✅ 定期review日志，积累case优化prompt

## 技术细节

### 验证函数位置

```python
# models/constructor/kt_gen.py

def _validate_and_fix_clustering_inconsistencies(
    self, clusters: list, cluster_details: list, 
    descriptions: list, index_offset: int
) -> tuple:
    """验证并修复聚类结果中的不一致"""
    # 详细实现见源码
```

### 集成点

验证逻辑已集成到所有LLM聚类解析函数：
- `_cluster_candidate_tails_with_llm()`
- `_parse_keyword_clustering_results()`
- `_parse_clustering_results()`

### 日志级别

```python
logger.warning(  # 使用WARNING级别
    "Clustering inconsistency detected: Cluster %d has 1 member but rationale says merge",
    cluster_idx
)
```

## 相关文档

- **详细技术文档**: `LLM_CLUSTERING_INCONSISTENCY_FIX.md`
- **测试脚本**: `test_clustering_inconsistency.py`
- **源码**: `models/constructor/kt_gen.py`

## 反馈和改进

如果你发现：
- 新的不一致模式
- 误报（正常case被标记为不一致）
- 其他问题

请记录case并反馈，帮助我们改进检测逻辑。

---

**更新日期**: 2025-10-23  
**版本**: 1.0
