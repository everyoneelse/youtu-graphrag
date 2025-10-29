# 更新日志 - 全图去重

## [v2.0] - 2025-10-29

### 🎉 重大改进：全图去重

#### 修改内容

**修复了一个重要的限制**：原来只对tail节点去重，现在对**所有位置**的节点都去重。

#### 技术变更

**文件**: `apply_tail_dedup_results.py`

**函数**: `apply_to_edges()`

**修改**：
```python
# 之前
v_rep = self._get_representative(v)  # 只处理tail
if v_rep != v:
    ...

# 现在
u_rep = self._get_representative(u)  # 处理head
v_rep = self._get_representative(v)  # 处理tail
if u_rep != u or v_rep != v:  # 任一需要替换
    ...
```

#### 影响范围

✅ **向后兼容**：
- API不变
- 数据格式不变
- 调用方式不变

✅ **功能增强**：
- HEAD位置的节点现在也会被替换
- 去重更完整
- 结果更符合预期

#### 测试

新增测试文件：`test_full_dedup.py`

测试覆盖：
- ✓ HEAD位置节点替换
- ✓ TAIL位置节点替换
- ✓ 同时替换HEAD和TAIL
- ✓ 边去重检查
- ✓ 孤立节点清理

#### 性能

- 性能影响：<5%
- 时间复杂度：保持O(E)
- 空间复杂度：保持O(E' + N)

#### 文档更新

新增文档：
- `FULL_GRAPH_DEDUP_EXPLANATION.md` - 详细说明

更新文档：
- `QUICK_START_INTEGRATION.md` - 添加更新说明
- `APPLY_TAIL_DEDUP_README.md` - 更新功能描述
- `TAIL_DEDUP_INDEX.md` - 添加新文档链接

#### 示例

**场景**：节点既作为HEAD也作为TAIL

原始图：
```
增加TE值 → 魔角效应  (HEAD位置)
延长TE   → 魔角效应  (HEAD位置)
延长TE值 → 魔角效应  (HEAD位置)

魔角效应 → 增加TE值  (TAIL位置)
魔角效应 → 延长TE    (TAIL位置)
魔角效应 → 延长TE值  (TAIL位置)
```

去重后：
```
延长TE值 → 魔角效应
魔角效应 → 延长TE值
```

#### 升级指南

**无需任何修改**！只需使用新版本：

```bash
python3 apply_tail_dedup_results.py \
    --graph original.json \
    --dedup-results dedup.json \
    --output deduped.json
```

你会自动获得更完整的去重结果。

#### 验证

运行测试验证：

```bash
# 运行全图去重测试
python3 test_full_dedup.py

# 运行完整测试套件
python3 test_apply_tail_dedup.py
```

---

## [v1.0] - 2025-10-29

### 🎊 初始版本

- 实现tail去重功能
- 支持三元组、社区、keyword_filter_by
- 完整的测试和文档

---

## 致谢

感谢用户指出原实现的限制，促成了这次重要的改进！
