# Head Dedup Prompt 修复总结

## 问题

用户发现 head_dedup 将 **"伪影"**（通用类别）错误地判断为与 **"魔角伪影"**（特定类型）等价。

**根本原因**：当前 prompt 过于依赖 chunk 内容的相似性，缺少对 **类别-实例关系** 的明确警告。

## 解决方案

参考 `semantic_dedup_group` 使用的 `DEFAULT_SEMANTIC_DEDUP_PROMPT`，将其核心原则融入 head_dedup prompt。

## 主要修改

### ✅ 1. 新增 FUNDAMENTAL PRINCIPLE
明确定义：**COREFERENCE requires REFERENTIAL IDENTITY**

### ✅ 2. 新增 CRITICAL DISTINCTION
警告：**相似上下文/关系 ≠ 实体同一性**

### ✅ 3. 新增 CATEGORY-INSTANCE WARNING
专门警告：**通用类别 ≠ 特定实例**
- 示例：伪影 ≠ 魔角伪影，疾病 ≠ 感冒，动物 ≠ 老虎

### ✅ 4. 扩展 PROHIBITED MERGE REASONS
从 5 条扩展到 9 条，新增：
- Category-Instance
- Part-Whole
- General-Specific
- Shared properties

### ✅ 5. 增强 DECISION PROCEDURE
第 2 步新增：**检查是否为类别-实例关系**

### ✅ 6. 新增针对性示例
添加用户提到的 "伪影" vs "魔角伪影" 作为 Example 3

## 修改文件

- ✅ `config/base_config.yaml` → `prompts.head_dedup.general`

## 测试结果

```bash
$ python3 test_head_dedup_category_instance.py

✅ Key Principles Check: 9/9 (100%)
✅ Prohibited Reasons Coverage: 9/9 (100%)
✅ Decision Procedure Check: 4/4 (100%)
✅ Examples Check: 4/4 (100%)

✅ ALL CHECKS PASSED!
```

## 立即使用

修改已生效，下次运行 head deduplication 时自动使用新 prompt：

```bash
python offline_semantic_dedup.py \
    --graph output/graphs/demo.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_deduped.json
```

⚠️ **重要**：如果之前有缓存，请先删除：
```bash
rm output/intermediate_results/*.pkl
```

## 预期效果

对于 **"伪影" vs "魔角伪影"**：

**修改前（错误）：**
```json
{"is_coreferent": true, "confidence": 1.0}
```

**修改后（正确）：**
```json
{
  "is_coreferent": false,
  "confidence": 0.90,
  "rationale": "'伪影' is GENERAL CATEGORY, '魔角伪影' is SPECIFIC TYPE. 
  Category-instance relationship. KEEP SEPARATE."
}
```

## 相关文档

| 文档 | 说明 |
|------|------|
| `HEAD_DEDUP_PROMPT_SEMANTIC_IMPROVEMENT.md` | 详细改进说明 |
| `HEAD_DEDUP_PROMPT_COMPARISON.md` | 修改前后对比 |
| `test_head_dedup_category_instance.py` | 测试脚本 |

## 设计原则

✅ **原则驱动，非案例驱动**  
✅ **与 semantic_dedup 保持一致**  
✅ **保守原则：宁可误拆，不可误合**

---

**状态**: ✅ 已完成  
**测试**: ✅ 全部通过  
**日期**: 2025-10-29
