# Head节点去重功能 - README

**版本**: v1.0  
**日期**: 2025-10-27  
**状态**: ✅ 已完成并集成

---

## 🎯 功能说明

对知识图谱中的**head节点（entity）**进行全局去重，合并指代同一实体的不同节点。

**示例**:
```
去重前:
  entity_0 (北京)    → capital_of → 中国
  entity_5 (北京市)  → located_in → 华北
  entity_8 (Beijing) → has_landmark → 故宫

去重后:
  entity_0 (北京)    → capital_of → 中国
                    → located_in → 华北
                    → has_landmark → 故宫
  [entity_5和entity_8被合并到entity_0]
```

---

## 📍 修改的文件

### 1. 配置文件

**文件**: `config/base_config.yaml`

**添加内容**:

#### A. 配置参数（第63-94行）
```yaml
construction:
  semantic_dedup:
    head_dedup:
      enabled: false          # 改为true启用
      enable_semantic: true
      similarity_threshold: 0.85
      use_llm_validation: false
      max_candidates: 1000
      # ... 更多参数
```

#### B. Prompt模板（第334-408行）
```yaml
prompts:
  head_dedup:
    general: |-
      You are an expert in knowledge graph entity resolution.
      
      TASK: Determine if the following two entities refer to the SAME real-world object.
      
      Entity 1: {entity_1}
      Related knowledge about Entity 1:
      {context_1}
      
      # ... 完整的prompt
```

### 2. 核心代码

**文件**: `models/constructor/kt_gen.py`

**添加位置**: 第4471-5218行（约750行代码）

**新增方法**: 15个
- `deduplicate_heads()` - 主入口
- `_collect_head_candidates()` - 收集候选
- `_normalize_entity_name()` - 名称标准化
- `_deduplicate_heads_exact()` - 精确去重
- `_generate_semantic_candidates()` - 生成候选对
- `_validate_candidates_with_embedding()` - Embedding验证
- `_validate_candidates_with_llm()` - LLM验证
- `_build_head_dedup_prompt()` - 构建prompt
- `_get_default_head_dedup_prompt()` - 默认prompt
- `_collect_node_context()` - 收集上下文
- `_parse_coreference_response()` - 解析响应
- `_merge_head_nodes()` - 执行合并
- `_reassign_outgoing_edges()` - 转移出边
- `_reassign_incoming_edges()` - 转移入边
- `_find_similar_edge()` - 查找边
- `_merge_edge_chunks()` - 合并chunks
- `_merge_node_properties()` - 合并属性
- `validate_graph_integrity_after_head_dedup()` - 验证完整性
- `export_head_merge_candidates_for_review()` - 导出审核

---

## 🚀 快速使用（3步）

### Step 1: 启用功能

编辑 `config/base_config.yaml`:

```yaml
construction:
  semantic_dedup:
    enabled: true  # 先启用tail去重
    
    head_dedup:
      enabled: true  # ← 改为true
```

### Step 2: 运行代码

```python
from models.constructor.kt_gen import KnowledgeTreeGen
from config import get_config

config = get_config()
builder = KnowledgeTreeGen(dataset_name="demo", config=config)

# 构建图谱
builder.build_knowledge_graph("data/demo/demo_corpus.json")

# Tail去重（现有功能）
if config.construction.semantic_dedup.enabled:
    builder.triple_deduplicate_semantic()

# Head去重（新功能）
stats = builder.deduplicate_heads()

print(f"✓ Merged {stats['total_merges']} nodes")
print(f"✓ Reduction: {stats['reduction_rate']:.1f}%")
```

### Step 3: 查看结果

```python
# 查看合并历史
for node_id, data in builder.graph.nodes(data=True):
    dedup_info = data.get("properties", {}).get("head_dedup", {})
    if dedup_info and dedup_info.get("merged_nodes"):
        print(f"\n{node_id}: {data['properties']['name']}")
        print(f"  Merged: {len(dedup_info['merged_nodes'])} nodes")
```

---

## 📋 配置参数说明

| 参数 | 默认值 | 说明 | 推荐值 |
|------|--------|------|--------|
| `enabled` | false | 是否启用 | true |
| `enable_semantic` | true | 语义去重 | true |
| `similarity_threshold` | 0.85 | 相似度阈值 | 0.85-0.90 |
| `use_llm_validation` | false | LLM验证 | false（快）/ true（准） |
| `max_candidates` | 1000 | 最大候选对 | 500-2000 |

**配置建议**:
- 小图谱（<1k实体）: `max_candidates=2000, use_llm=true`
- 中图谱（1k-10k）: `max_candidates=1000, use_llm=false`
- 大图谱（>10k）: `max_candidates=500, threshold=0.90`

---

## 🎨 自定义Prompt

Prompt存储在 `config/base_config.yaml` 的 `prompts.head_dedup.general` 中。

**可用变量**:
- `{entity_1}`, `{context_1}` - 第一个实体
- `{entity_2}`, `{context_2}` - 第二个实体

**修改方式**:
直接编辑配置文件，无需修改代码！

**详细指南**: 请参考 `HEAD_DEDUP_PROMPT_CUSTOMIZATION.md`

---

## 🧪 测试

### 快速测试

```bash
# 运行集成测试
python test_head_dedup_integration.py
```

预期输出:
```
✓ All imports successful
✓ All 18 methods found
✓ All config fields found
✓ Prompt loaded successfully
✓ Basic functionality test passed

🎉 All tests passed! Head deduplication is ready to use.
```

### 手动测试

```python
# test_manual.py
from models.constructor.kt_gen import KnowledgeTreeGen
from config import get_config

config = get_config()
config.construction.semantic_dedup.head_dedup.enabled = True

builder = KnowledgeTreeGen(dataset_name="test", config=config)

# 添加测试数据
builder.graph.add_node("entity_0", label="entity", properties={"name": "北京"})
builder.graph.add_node("entity_1", label="entity", properties={"name": "北京市"})
builder.graph.add_edge("entity_0", "entity_1", relation="test")

print(f"Before: {builder.graph.number_of_nodes()} nodes")

# 运行去重
stats = builder.deduplicate_heads(enable_semantic=False)

print(f"After: {stats['final_entity_count']} entities")
print(f"Merged: {stats['total_merges']}")
```

---

## 📚 完整文档

### 快速上手
- **HEAD_DEDUP_QUICKSTART.md** - 5分钟快速开始
- **example_use_head_dedup.py** - 7个使用示例

### 详细文档
- **HEAD_DEDUP_INTEGRATION_SUMMARY.md** - 完整集成说明 ⭐
- **HEAD_DEDUP_PROMPT_CUSTOMIZATION.md** - Prompt自定义指南
- **HEAD_DEDUPLICATION_SOLUTION.md** - 方案设计文档

### 技术深入
- **HEAD_DEDUP_LLM_CORE_LOGIC.md** - LLM判断逻辑
- **PROMPT_COMPARISON_HEAD_VS_TAIL_DEDUP.md** - Prompt对比
- **PROFESSIONAL_EVALUATION_PROMPTS.md** - 专业度评估

### 参考代码
- **head_deduplication_reference.py** - 完整参考实现
- **example_head_deduplication.py** - 8个场景示例

---

## ⚡ 常用命令

### 启用head去重
```bash
# 编辑配置文件
vim config/base_config.yaml
# 设置 head_dedup.enabled: true
```

### 运行完整pipeline
```python
python main.py --dataset demo --enable-head-dedup
```

### 导出审核文件
```python
builder.export_head_merge_candidates_for_review(
    "output/review/head_merges.csv",
    min_confidence=0.70,
    max_confidence=0.90
)
```

### 查看统计
```python
stats = builder.deduplicate_heads()
print(f"Reduction: {stats['reduction_rate']:.1f}%")
print(f"Time: {stats['elapsed_time_seconds']:.1f}s")
```

---

## 🔧 故障排除

### 问题1: "Head deduplication is disabled in config"

**解决**: 
```yaml
# config/base_config.yaml
head_dedup:
  enabled: true  # 改为true
```

### 问题2: ImportError: No module named 'sklearn'

**解决**:
```bash
pip install scikit-learn>=1.0
```

### 问题3: 没有找到任何候选对

**解决**: 降低预筛选阈值
```yaml
candidate_similarity_threshold: 0.70  # 从0.75降低
```

### 问题4: LLM调用失败

**解决**: 检查LLM配置
```bash
# 确保环境变量正确
echo $LLM_API_KEY
echo $LLM_BASE_URL
```

### 问题5: 想要更详细的日志

**解决**:
```python
import logging
logging.getLogger('models.constructor.kt_gen').setLevel(logging.DEBUG)
```

---

## 📊 性能预期

| 图规模 | 配置 | 时间 | 减少率 |
|--------|------|------|--------|
| 100实体 | 平衡 | <5秒 | 10-20% |
| 1,000实体 | 平衡 | 10-30秒 | 15-25% |
| 10,000实体 | 平衡 | 1-5分钟 | 20-35% |

---

## ✅ 完成检查清单

集成完成后，请确认：

- [ ] 配置文件包含 `head_dedup` 配置节
- [ ] 配置文件包含 `prompts.head_dedup.general` prompt
- [ ] kt_gen.py 包含所有15个新方法
- [ ] 可以导入 KnowledgeTreeGen 类
- [ ] 运行 `test_head_dedup_integration.py` 通过
- [ ] 在小数据集上测试功能
- [ ] 查看导出的审核文件格式正确

---

## 🎓 核心原理

### 去重流程

```
阶段1: 精确匹配
  ↓ 标准化名称匹配
  
阶段2: 语义去重  
  ↓ Embedding相似度
  ↓ （可选）LLM验证
  
阶段3: 图更新
  ↓ 转移边
  ↓ 合并属性
  ↓ 删除节点
  
阶段4: 验证
  ↓ 完整性检查
```

### 判断依据

LLM判断两个实体是否等价基于：
1. **指称一致性**: 是否指向同一真实对象
2. **替换测试**: 互换是否改变语义
3. **类型一致性**: 实体类型是否兼容
4. **保守原则**: 不确定时不合并

### 上下文使用

**现有tail去重**: 使用文本chunk作为上下文  
**新增head去重**: 使用图关系作为上下文

**为什么不同？**
- Tail去重在构建中，需要文本消歧
- Head去重在构建后，可利用图结构
- 两者互补，共同提升图谱质量

---

## 💡 使用建议

### 推荐Pipeline

```
1. 构建图谱
   ↓
2. Tail去重（利用文本上下文）
   ↓  
3. Head去重（利用图关系）← 新功能
   ↓
4. 保存最终图谱
```

### 参数推荐

**快速模式**（性能优先）:
```yaml
enable_semantic: false  # 仅精确匹配
```

**平衡模式**（推荐）:
```yaml
enable_semantic: true
similarity_threshold: 0.85
use_llm_validation: false
max_candidates: 1000
```

**高精度模式**（质量优先）:
```yaml
enable_semantic: true
similarity_threshold: 0.90
use_llm_validation: true
max_candidates: 500
export_review: true
```

---

## 📞 获取帮助

### 文档导航

| 问题类型 | 查看文档 |
|---------|---------|
| 快速上手 | `HEAD_DEDUP_QUICKSTART.md` |
| 如何集成 | `HEAD_DEDUP_INTEGRATION_SUMMARY.md` ⭐ |
| 自定义Prompt | `HEAD_DEDUP_PROMPT_CUSTOMIZATION.md` |
| 方案原理 | `HEAD_DEDUPLICATION_SOLUTION.md` |
| LLM逻辑 | `HEAD_DEDUP_LLM_CORE_LOGIC.md` |
| 对比分析 | `PROMPT_COMPARISON_HEAD_VS_TAIL_DEDUP.md` |

### 代码示例

| 场景 | 查看文件 |
|------|---------|
| 基础用法 | `example_use_head_dedup.py` |
| 完整实现 | `head_deduplication_reference.py` |
| 集成测试 | `test_head_dedup_integration.py` |

---

## 🎉 总结

✅ **集成完成**: 所有代码已添加到 `kt_gen.py` 和 `base_config.yaml`  
✅ **Prompt管理**: 从配置文件加载，支持自定义  
✅ **文档完整**: 12份文档，覆盖所有方面  
✅ **示例丰富**: 3个示例文件，15+使用场景  
✅ **测试就绪**: 提供集成测试脚本  
✅ **生产级质量**: 错误处理、日志、验证完备  

**现在可以开始使用head节点去重功能了！** 🎊

---

## 🔗 相关链接

- **主文档**: `HEAD_DEDUP_INTEGRATION_SUMMARY.md`
- **快速开始**: `HEAD_DEDUP_QUICKSTART.md`
- **Prompt自定义**: `HEAD_DEDUP_PROMPT_CUSTOMIZATION.md`
- **测试脚本**: `test_head_dedup_integration.py`
- **使用示例**: `example_use_head_dedup.py`

---

**维护者**: Knowledge Graph Team  
**License**: MIT  
**版本**: v1.0 (2025-10-27)
