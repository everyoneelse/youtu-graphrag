# 实施指南：别名关系方法的Head去重

**日期**: 2025-10-28  
**目标**: 将当前的head去重实现改进为别名关系方法  

---

## 📋 实施方案

### 方案A: 最小改动（快速修复self-loop）

**适用场景**: 紧急修复，暂时解决self-loop问题

**改动内容**:
1. 修改 `_reassign_outgoing_edges()` 和 `_reassign_incoming_edges()`
2. 添加更严格的self-loop检测

**代码位置**: `/workspace/models/constructor/kt_gen.py` 第5118-5146行

**具体改动**:

```python
# 在 _reassign_outgoing_edges 中 (第5122行后)
for _, tail_id, key, data in outgoing:
    # === 添加这段 ===
    if tail_id == target_id or tail_id == source_id:
        logger.debug(
            f"Skipping edge to avoid self-loop: {source_id} -> {tail_id} "
            f"(relation: {data.get('relation')})"
        )
        continue
    # === 结束 ===
    
    if tail_id == target_id:  # 这行可以删除，被上面的逻辑覆盖了
        continue

# 在 _reassign_incoming_edges 中 (第5137行后)  
for head_id, _, key, data in incoming:
    # === 添加这段 ===
    if head_id == target_id or head_id == source_id:
        logger.debug(
            f"Skipping edge to avoid self-loop: {head_id} -> {source_id} "
            f"(relation: {data.get('relation')})"
        )
        continue
    # === 结束 ===
    
    if head_id == target_id:  # 这行可以删除
        continue
```

**优点**:
- 改动最小（约10行代码）
- 快速修复self-loop问题
- 不改变现有架构

**缺点**:
- 别名信息仍然丢失
- 不是长期方案

**测试**:
```bash
# 运行现有测试
python test_head_dedup_integration.py

# 检查是否还有self-loop
python -c "
from models.constructor.kt_gen import KnowledgeTreeGen
from config import get_config
config = get_config()
builder = KnowledgeTreeGen('demo', config)
# ... 构建图并去重 ...
issues = builder.validate_graph_integrity_after_head_dedup()
assert len(issues['self_loops']) == 0, f'Still have self-loops: {issues}'
print('✓ No self-loops found')
"
```

---

### 方案B: 完整实现（推荐）

**适用场景**: 长期方案，完全解决问题并提升图谱质量

**改动内容**:
1. 添加新的合并函数 `_merge_head_nodes_with_alias()`
2. 添加辅助函数（选择representative、安全转移边等）
3. 添加别名相关的工具函数
4. 更新配置文件
5. 更新主入口函数
6. 更新完整性验证

#### 步骤1: 添加核心函数

**文件**: `/workspace/models/constructor/kt_gen.py`  
**位置**: 在现有的head去重代码后添加（约5324行后）

**添加内容**:
```python
# 从 head_dedup_alias_implementation.py 复制以下函数：
# 1. _merge_head_nodes_with_alias()         - 核心合并函数
# 2. _revise_representative_selection()     - 选择代表
# 3. _reassign_outgoing_edges_safe()        - 安全转移出边
# 4. _reassign_incoming_edges_safe()        - 安全转移入边
# 5. _remove_non_alias_edges()              - 清理边
# 6. deduplicate_heads_with_alias()         - 新的主入口
# 7. validate_graph_integrity_with_alias()  - 验证完整性
# 8. is_alias_node()                        - 工具函数
# 9. get_main_entities_only()               - 工具函数
# 10. resolve_alias()                       - 工具函数
# 11. get_all_aliases()                     - 工具函数
# 12. export_alias_mapping()                - 导出函数
```

**完整代码**: 参见 `/workspace/head_dedup_alias_implementation.py`

#### 步骤2: 更新配置文件

**文件**: `/workspace/config/base_config.yaml`  
**位置**: `construction.semantic_dedup.head_dedup` 节

**添加参数**:
```yaml
construction:
  semantic_dedup:
    head_dedup:
      enabled: true
      
      # 新增：合并策略选择
      merge_strategy: "alias"  # "delete" 或 "alias"
      
      # 新增：别名关系配置
      alias_relation_name: "alias_of"
      prefer_comprehensive_representative: true
      prefer_longer_names: true
      prefer_more_evidence: true
      
      # 新增：验证选项
      validate_no_self_loops: true
      validate_alias_chains: true
      
      # 新增：导出选项
      export_alias_mapping: true
      export_path: "output/alias_mapping.csv"
      
      # 现有参数保持不变
      enable_semantic: true
      similarity_threshold: 0.85
      # ...
```

#### 步骤3: 更新主入口

**文件**: `/workspace/models/constructor/kt_gen.py`  
**位置**: `deduplicate_heads()` 函数（约4587行）

**选项1**: 根据配置选择方法（推荐）

```python
def deduplicate_heads(
    self,
    enable_semantic: bool = True,
    similarity_threshold: float = 0.85,
    use_llm_validation: bool = False,
    max_candidates: int = 1000
) -> Dict[str, Any]:
    """Main entry for head deduplication."""
    
    # 从配置读取合并策略
    config = getattr(self.config.construction.semantic_dedup, 'head_dedup', None)
    merge_strategy = getattr(config, 'merge_strategy', 'delete') if config else 'delete'
    
    if merge_strategy == 'alias':
        # 使用别名方法
        alias_relation = getattr(config, 'alias_relation_name', 'alias_of')
        return self.deduplicate_heads_with_alias(
            enable_semantic=enable_semantic,
            similarity_threshold=similarity_threshold,
            use_llm_validation=use_llm_validation,
            max_candidates=max_candidates,
            alias_relation=alias_relation
        )
    else:
        # 使用传统方法（原有逻辑）
        # ... 原有代码 ...
```

**选项2**: 提供两个独立的入口

```python
# 保持原有函数不变
def deduplicate_heads(...):
    """Traditional head deduplication (deletes duplicate nodes)."""
    # ... 原有逻辑 ...

# 添加新函数
def deduplicate_heads_with_alias(...):
    """Improved head deduplication using alias relationships."""
    # ... 新逻辑 ...
```

#### 步骤4: 适配下游模块

**需要检查的模块**:

1. **图谱导出** (`export_graph()`):
   - 确保alias节点正确导出
   - 标记alias_of关系

2. **统计函数**:
   - 分别统计主实体和别名数量
   - 更新reduction_rate计算

3. **可视化** (如果有):
   - 提供选项隐藏alias节点
   - 或用不同颜色/样式显示alias

4. **检索/查询**:
   - 支持别名扩展查询
   - 从alias自动跳转到主实体

#### 步骤5: 测试

**创建测试文件**: `test_alias_head_dedup.py`

```python
"""Test cases for alias-based head deduplication."""

import pytest
from models.constructor.kt_gen import KnowledgeTreeGen
from config import get_config


def test_no_self_loops():
    """Ensure no self-loops are created."""
    config = get_config()
    config.construction.semantic_dedup.head_dedup.enabled = True
    config.construction.semantic_dedup.head_dedup.merge_strategy = "alias"
    
    builder = KnowledgeTreeGen("test", config)
    
    # Create test data with potential self-loop scenario
    builder.graph.add_node("entity_0", label="entity", 
                          properties={"name": "血流伪影"})
    builder.graph.add_node("entity_1", label="entity",
                          properties={"name": "流动伪影"})
    builder.graph.add_edge("entity_0", "entity_1", relation="别名包括")
    builder.graph.add_edge("entity_1", "entity_2", relation="是一种")
    
    # Run deduplication
    stats = builder.deduplicate_heads_with_alias(enable_semantic=False)
    
    # Verify no self-loops
    issues = builder.validate_graph_integrity_with_alias()
    assert len(issues["self_loops"]) == 0, f"Self-loops found: {issues['self_loops']}"
    
    print("✓ No self-loops test passed")


def test_alias_relationship_created():
    """Verify alias relationships are created."""
    config = get_config()
    config.construction.semantic_dedup.head_dedup.merge_strategy = "alias"
    
    builder = KnowledgeTreeGen("test", config)
    
    # Create duplicate entities
    builder.graph.add_node("entity_0", label="entity", 
                          properties={"name": "北京"})
    builder.graph.add_node("entity_1", label="entity",
                          properties={"name": "北京市"})
    
    # Run deduplication
    merge_mapping = {"entity_1": "entity_0"}
    stats = builder._merge_head_nodes_with_alias(merge_mapping, {})
    
    # Verify alias relationship
    alias_edges = [
        (u, v) for u, v, d in builder.graph.edges(data=True)
        if d.get("relation") == "alias_of"
    ]
    
    assert len(alias_edges) == 1, "Should have 1 alias relationship"
    assert alias_edges[0] == ("entity_1", "entity_0"), "Alias edge direction wrong"
    
    # Verify node roles
    assert builder.graph.nodes["entity_0"]["properties"]["node_role"] == "representative"
    assert builder.graph.nodes["entity_1"]["properties"]["node_role"] == "alias"
    
    print("✓ Alias relationship test passed")


def test_representative_selection():
    """Test that entity with more relations is chosen as representative."""
    config = get_config()
    builder = KnowledgeTreeGen("test", config)
    
    # entity_0 has 1 out edge, entity_1 has 2 out edges
    builder.graph.add_node("entity_0", label="entity", 
                          properties={"name": "A"})
    builder.graph.add_node("entity_1", label="entity",
                          properties={"name": "B"})
    builder.graph.add_edge("entity_0", "entity_2", relation="rel1")
    builder.graph.add_edge("entity_1", "entity_3", relation="rel2")
    builder.graph.add_edge("entity_1", "entity_4", relation="rel3")
    
    # Original mapping says entity_0 -> entity_1
    merge_mapping = {"entity_0": "entity_1"}
    
    # Revise should keep entity_1 as representative (more edges)
    revised = builder._revise_representative_selection(merge_mapping)
    
    assert revised["entity_0"] == "entity_1", "Should choose entity_1 (more edges)"
    
    print("✓ Representative selection test passed")


def test_alias_utilities():
    """Test utility functions for alias handling."""
    config = get_config()
    builder = KnowledgeTreeGen("test", config)
    
    # Create nodes
    builder.graph.add_node("entity_0", label="entity",
                          properties={"name": "Main", "node_role": "representative",
                                     "aliases": [{"alias_id": "entity_1", "alias_name": "Alias1"}]})
    builder.graph.add_node("entity_1", label="entity",
                          properties={"name": "Alias1", "node_role": "alias", "alias_of": "entity_0"})
    
    # Test is_alias_node
    assert builder.is_alias_node("entity_1") == True
    assert builder.is_alias_node("entity_0") == False
    
    # Test resolve_alias
    assert builder.resolve_alias("entity_1") == "entity_0"
    assert builder.resolve_alias("entity_0") == "entity_0"
    
    # Test get_all_aliases
    aliases = builder.get_all_aliases("entity_0")
    assert len(aliases) == 1
    assert aliases[0]["alias_id"] == "entity_1"
    
    print("✓ Alias utilities test passed")


if __name__ == "__main__":
    test_no_self_loops()
    test_alias_relationship_created()
    test_representative_selection()
    test_alias_utilities()
    
    print("\n🎉 All tests passed!")
```

**运行测试**:
```bash
python test_alias_head_dedup.py
```

---

## 📊 对比总结

| 特性 | 方案A (最小改动) | 方案B (完整实现) |
|------|-----------------|----------------|
| **Self-loop问题** | ✅ 修复 | ✅ 修复 |
| **别名信息** | ❌ 丢失（metadata中） | ✅ 显式保留（图结构中） |
| **节点数量** | 减少 | 保持（角色明确） |
| **语义正确性** | ⚠️ 部分 | ✅ 完全 |
| **查询支持** | ❌ 需要遍历metadata | ✅ 直接图查询 |
| **代码改动** | ~10行 | ~500行 |
| **实施时间** | 1小时 | 1-2天 |
| **长期维护** | 需后续改进 | 长期方案 |

---

## 🎯 推荐实施路径

### 第一阶段（本周）：快速修复
1. ✅ 实施方案A（最小改动）
2. ✅ 验证self-loop问题解决
3. ✅ 发布紧急修复版本

### 第二阶段（下周）：完整实现
1. ✅ 实施方案B（添加所有新函数）
2. ✅ 更新配置文件
3. ✅ 编写完整测试
4. ✅ 更新文档

### 第三阶段（下下周）：下游适配
1. ✅ 适配检索模块
2. ✅ 适配导出模块
3. ✅ 适配可视化（如有）
4. ✅ 性能优化

### 第四阶段（未来）：高级功能
1. ✅ 别名链检测和解析
2. ✅ 多语言别名支持
3. ✅ 别名置信度评分
4. ✅ 人工审核界面

---

## 📝 关键代码位置

### 需要修改的文件

1. **`/workspace/models/constructor/kt_gen.py`**
   - 第5118-5146行: `_reassign_outgoing_edges`, `_reassign_incoming_edges`
   - 第4587行: `deduplicate_heads()` 主入口
   - 添加: 新的别名方法函数（~500行）

2. **`/workspace/config/base_config.yaml`**
   - 第63-94行: `construction.semantic_dedup.head_dedup` 配置节
   - 添加: 新的别名配置参数

3. **新文件**:
   - `/workspace/test_alias_head_dedup.py` - 测试文件
   - `/workspace/HEAD_DEDUP_ALIAS_APPROACH.md` - 方案文档（已创建）
   - `/workspace/head_dedup_alias_implementation.py` - 参考实现（已创建）

---

## 🔧 故障排除

### 问题1: 合并后仍有self-loop

**检查**:
```python
issues = builder.validate_graph_integrity_with_alias()
if issues["self_loops"]:
    for u, v in issues["self_loops"]:
        print(f"Self-loop: {u} -> {v}")
        # 检查edge data
        for key, data in builder.graph[u][v].items():
            print(f"  Relation: {data.get('relation')}")
```

**解决**: 确保在 `_reassign_*_edges_safe()` 中正确检查了 `tail_id == target_id` 和 `head_id == target_id`

### 问题2: Alias节点被认为是orphan

**检查**:
```python
for node_id in issues["orphan_nodes"]:
    node = builder.graph.nodes[node_id]
    print(f"Orphan: {node_id}, role: {node['properties'].get('node_role')}")
```

**解决**: 更新 `validate_graph_integrity_with_alias()` 以正确识别alias节点

### 问题3: Alias chains (alias -> alias)

**检查**:
```python
if issues["alias_chains"]:
    print(f"Found alias chains: {issues['alias_chains']}")
```

**解决**: 在 `_revise_representative_selection()` 中正确处理传递性合并

---

## ✅ 验收标准

完成实施后，应满足：

- [ ] 运行head去重后，`validate_graph_integrity_with_alias()` 返回的 `self_loops` 列表为空
- [ ] 所有等价实体对之间都有 `alias_of` 关系
- [ ] Alias节点的 `node_role` 属性为 `"alias"`
- [ ] Representative节点的 `aliases` 列表包含所有别名信息
- [ ] 工具函数 `is_alias_node()`, `resolve_alias()`, `get_all_aliases()` 正常工作
- [ ] 所有原有测试仍然通过
- [ ] 新的测试 `test_alias_head_dedup.py` 全部通过

---

**准备好开始实施了吗？建议从方案A开始，快速修复当前的self-loop问题。**
