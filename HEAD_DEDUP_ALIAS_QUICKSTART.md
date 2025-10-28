# Head去重别名方法 - 5分钟快速开始

## 🎯 核心思想

**问题**: 当前head去重会导致self-loops（自环），别名信息丢失  
**原因**: 删除duplicate节点，导致原本连接两个节点的边指向同一节点  
**解决**: 不删除节点，建立显式的 `alias_of` 关系

## 📋 实施步骤

### 步骤1: 应急修复（2小时）

编辑 `/workspace/models/constructor/kt_gen.py` 第5122-5139行：

```python
# 在 _reassign_outgoing_edges 中
for _, tail_id, key, data in outgoing:
    # 添加这两行 ↓
    if tail_id == target_id or tail_id == source_id:
        continue
    # 原有代码
    if tail_id == target_id:
        continue
    # ...

# 在 _reassign_incoming_edges 中  
for head_id, _, key, data in incoming:
    # 添加这两行 ↓
    if head_id == target_id or head_id == source_id:
        continue
    # 原有代码
    if head_id == target_id:
        continue
    # ...
```

**效果**: 立即消除self-loops

### 步骤2: 完整实施（2天）

1. **复制代码**: 将 `head_dedup_alias_implementation.py` 的函数添加到 `kt_gen.py`
2. **更新配置**: 添加 `merge_strategy: "alias"` 到 `base_config.yaml`
3. **运行测试**: `python test_alias_head_dedup.py`

## 📚 文档导航

- **评估报告**: `HEAD_DEDUP_ALIAS_EVALUATION_SUMMARY.md` (14KB, ⭐⭐⭐⭐⭐)
- **技术方案**: `HEAD_DEDUP_ALIAS_APPROACH.md` (19KB)
- **实施指南**: `IMPLEMENTATION_GUIDE_ALIAS_HEAD_DEDUP.md` (15KB)
- **参考代码**: `head_dedup_alias_implementation.py` (28KB, 600行)
- **配置示例**: `config_alias_head_dedup_example.yaml` (2.8KB)

## 🎉 预期效果

- ✅ Self-loops: 100% 消除
- ✅ 别名信息: 完整保留
- ✅ 查询能力: 显著提升

**推荐**: 先实施步骤1（应急），再计划步骤2（完整）
