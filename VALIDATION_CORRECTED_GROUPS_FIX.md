# Validation Corrected Groups Fix

## 📅 日期: 2025-10-23

## 🎯 问题

用户发现 `_llm_validate_semantic_dedup` 存在一个数据丢失的风险：

### 问题描述

```python
# LLM返回的corrected_groups
corrected_groups_raw = parsed.get('corrected_groups')

# 代码直接用corrected_groups替换所有groups
return corrected_groups, validation_report
```

**问题**：
- 如果LLM只返回需要修正的groups（而不是所有groups）
- 那些本来就正确的groups会丢失！

### 具体场景

```python
# 原始groups
groups = [
    {'members': [0, 1], 'rationale': '正确的'},
    {'members': [2], 'rationale': '正确的'},  
    {'members': [3], 'rationale': '错误的，应该合并到第一组'}
]

# 如果LLM只返回需要修正的
corrected_groups = [
    {'members': [0, 1, 3], 'rationale': '修正后的第一组'}
    # ❌ 缺少第二组！
]

# 结果：第二组[2]丢失了！
```

## ✅ 解决方案

### 1. 明确Prompt要求

**Before**:
```python
"corrected_groups": [
  {"members": [...], "representative": N, "rationale": "..."}
]
```
→ 歧义：是所有groups还是只有修正的？

**After**:
```python
"corrected_groups": [
  {"members": [...], "representative": N, "rationale": "..."}
]

IMPORTANT: corrected_groups should contain ALL groups (both corrected and unchanged).
Do not omit groups that were already consistent.
```
→ 明确：必须包含所有groups

### 2. 添加验证逻辑

```python
# Verify we got all items covered
all_items = set(range(len(original_candidates)))
covered_items = set()
for group in corrected_groups:
    covered_items.update(group['members'])

missing_items = all_items - covered_items
if missing_items:
    logger.warning(
        "LLM validation output missing items %s. Keeping original groups to avoid data loss.",
        sorted(missing_items)
    )
    validation_report['corrected'] = False
    validation_report['error'] = f"Missing items in corrected_groups: {sorted(missing_items)}"
    return groups, validation_report  # 保留原始groups，避免数据丢失
```

**验证逻辑**：
1. 检查所有原始items是否都在corrected_groups中
2. 如果有缺失，拒绝应用修正，保留原始groups
3. 记录警告日志和错误信息

## 📊 修改内容

### Prompt修改

```diff
  "OUTPUT FORMAT:\n"
  "Return strict JSON:\n"
  "{\n"
  "  \"has_inconsistencies\": true/false,\n"
  "  \"inconsistencies\": [...],\n"
  "  \"corrected_groups\": [\n"
  "    {\"members\": [...], \"representative\": N, \"rationale\": \"...\"}\n"
  "  ]\n"
  "}\n\n"
+ "IMPORTANT: corrected_groups should contain ALL groups (both corrected and unchanged).\n"
+ "Do not omit groups that were already consistent.\n\n"
  "If all groups are consistent, return:\n"
  "{\n"
  "  \"has_inconsistencies\": false,\n"
  "  \"inconsistencies\": [],\n"
  "  \"corrected_groups\": null\n"
  "}\n"
```

### 代码修改

```diff
  # Apply corrections
  logger.info("LLM semantic dedup validation found %d inconsistencies, applying corrections", len(inconsistencies))
  
  corrected_groups = []
  for group_info in corrected_groups_raw:
      # ... 处理corrected_groups_raw ...
  
+ # Verify we got all items covered
+ all_items = set(range(len(original_candidates)))
+ covered_items = set()
+ for group in corrected_groups:
+     covered_items.update(group['members'])
+ 
+ missing_items = all_items - covered_items
+ if missing_items:
+     logger.warning(
+         "LLM validation output missing items %s. Keeping original groups to avoid data loss.",
+         sorted(missing_items)
+     )
+     validation_report['corrected'] = False
+     validation_report['error'] = f"Missing items in corrected_groups: {sorted(missing_items)}"
+     return groups, validation_report
  
  validation_report['corrected'] = True
  validation_report['corrected_group_count'] = len(corrected_groups)
  validation_report['inconsistencies_fixed'] = inconsistencies
  
  return corrected_groups, validation_report
```

## 🛡️ 安全保障

### 三重保护机制

1. **Prompt明确要求** - 告诉LLM必须返回所有groups
2. **数据完整性验证** - 检查是否有缺失items
3. **失败时回退** - 如果验证失败，保留原始groups

### 错误处理

```python
# 如果检测到数据缺失
if missing_items:
    # ✅ 保留原始groups（不丢失数据）
    # ✅ 记录警告日志
    # ✅ 在validation_report中记录错误
    # ✅ 返回corrected=False标记
    return groups, validation_report
```

## 📝 测试场景

### 场景1：正常情况（LLM正确返回所有groups）

```python
# 输入
groups = [
    {'members': [0, 1], 'rationale': 'A'},
    {'members': [2], 'rationale': 'B'},
    {'members': [3], 'rationale': 'C, 应该合并到A'}
]

# LLM输出（正确）
corrected_groups = [
    {'members': [0, 1, 3], 'rationale': 'A merged with C'},
    {'members': [2], 'rationale': 'B'}
]

# 验证
all_items = {0, 1, 2, 3}
covered = {0, 1, 3} ∪ {2} = {0, 1, 2, 3}
missing = {} ✅

# 结果：应用修正
```

### 场景2：异常情况（LLM只返回修正的groups）

```python
# 输入
groups = [
    {'members': [0, 1], 'rationale': 'A'},
    {'members': [2], 'rationale': 'B'},
    {'members': [3], 'rationale': 'C, 应该合并到A'}
]

# LLM输出（错误，缺少B组）
corrected_groups = [
    {'members': [0, 1, 3], 'rationale': 'A merged with C'}
    # ❌ 缺少 {'members': [2], ...}
]

# 验证
all_items = {0, 1, 2, 3}
covered = {0, 1, 3}
missing = {2} ❌

# 结果：拒绝修正，保留原始groups
logger.warning("Missing items [2]. Keeping original groups.")
return groups, validation_report  # 不丢失数据
```

## 🎯 修改的文件

- ✅ `models/constructor/kt_gen.py` - 添加验证逻辑和prompt说明
- ✅ `VALIDATION_CORRECTED_GROUPS_FIX.md` - 本文档

## 💡 设计原则

### 数据安全优先

> "宁可不修正，也不能丢数据"

如果LLM的输出有问题（缺少items），宁可保留原始groups，也不能导致数据丢失。

### 明确的契约

Prompt和代码之间需要明确的契约：
- Prompt: "你必须返回所有groups"
- 代码: "我会验证你是否真的返回了所有groups"

### 防御性编程

不要假设LLM总是正确的：
- ✅ 验证输出完整性
- ✅ 检测异常情况
- ✅ 安全回退机制

## 📊 影响范围

### 影响的功能
- `_llm_validate_semantic_dedup` - 语义去重验证

### 不影响的功能
- 其他验证逻辑（clustering validation等）保持不变

### 向后兼容
- ✅ 完全兼容
- 如果LLM本来就返回所有groups，不受影响
- 如果LLM只返回部分groups，现在会被检测并拒绝

## 🚀 后续建议

### 类似问题排查

检查其他验证函数是否有同样的问题：
- `_llm_validate_clustering` - 也可能有类似问题
- 建议添加同样的验证逻辑

### 监控建议

添加监控指标：
- 记录验证被拒绝的次数
- 如果经常出现"missing items"警告，说明prompt需要进一步优化

---

**问题**: LLM可能只返回修正的groups，导致数据丢失  
**解决**: 明确要求+验证逻辑+安全回退  
**状态**: ✅ 已修复  
**原则**: 数据安全优先，宁可不修正也不丢数据
