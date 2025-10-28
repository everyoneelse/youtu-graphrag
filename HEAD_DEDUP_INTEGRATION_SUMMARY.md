# Head节点去重功能集成总结

**日期**: 2025-10-27  
**功能**: Head节点全局去重  
**状态**: ✅ 已集成到代码库

---

## 📦 修改文件清单

### 1. 配置文件
- **文件**: `config/base_config.yaml`
- **修改内容**:
  - ✅ 在 `construction.semantic_dedup` 下添加 `head_dedup` 配置节
  - ✅ 在 `prompts` 下添加 `head_dedup.general` prompt模板

### 2. 核心实现
- **文件**: `models/constructor/kt_gen.py`
- **添加**: 约700行代码，14个新方法
- **修改**: prompt**仅**从配置文件加载，无fallback

### 3. 使用示例
- **文件**: `example_use_head_dedup.py` (新建)
- **内容**: 7个使用场景示例

### 4. 文档
- **文件**: `HEAD_DEDUP_PROMPT_CUSTOMIZATION.md` (新建)
- **内容**: Prompt自定义指南

---

## 🎯 功能特性

### 核心功能
✅ **两阶段去重**：精确匹配 + 语义相似度  
✅ **双模式支持**：Embedding快速模式 / LLM高精度模式  
✅ **完整溯源**：记录所有合并历史和依据  
✅ **图结构安全**：自动转移边、合并属性、验证完整性  
✅ **人工审核**：导出中等置信度案例供审核  

### 与现有代码的兼容性
✅ 使用相同的配置体系 (`config.construction.semantic_dedup`)  
✅ 复用现有的 `_concurrent_llm_calls` 并发调用  
✅ 复用现有的 `_batch_get_embeddings` 批量embedding  
✅ 复用现有的 `_describe_node` 节点描述方法  
✅ 日志风格与现有代码一致  

---

## 📋 使用方式

### 方式1: 使用配置文件（推荐）

**Step 1**: 编辑 `config/base_config.yaml`

```yaml
construction:
  semantic_dedup:
    enabled: true  # 先启用tail去重
    
    head_dedup:
      enabled: true                      # 启用head去重
      enable_semantic: true               # 启用语义去重
      similarity_threshold: 0.85          # 相似度阈值
      use_llm_validation: false           # false=快速，true=精确
      max_candidates: 1000                # 最大候选对数量
      candidate_similarity_threshold: 0.75
      max_relations_context: 10
      export_review: false                # 是否导出审核文件
      review_confidence_range: [0.70, 0.90]
      review_output_dir: "output/review"
```

**Step 2**: 在代码中调用

```python
from models.constructor.kt_gen import KnowledgeTreeGen
from config import get_config

config = get_config()
builder = KnowledgeTreeGen(dataset_name="demo", config=config)

# 构建图谱
builder.build_knowledge_graph("data/demo/demo_corpus.json")

# Tail去重（如果启用）
if config.construction.semantic_dedup.enabled:
    builder.triple_deduplicate_semantic()

# Head去重（自动读取配置）
stats = builder.deduplicate_heads()

print(f"Merged {stats['total_merges']} head nodes")
```

### 方式2: 使用自定义参数

```python
# 覆盖配置文件的参数
stats = builder.deduplicate_heads(
    enable_semantic=True,
    similarity_threshold=0.90,  # 更严格
    use_llm_validation=True,    # 使用LLM
    max_candidates=500          # 限制LLM调用
)
```

---

## 🔧 主要方法说明

### 1. 主入口方法

```python
def deduplicate_heads(
    self,
    enable_semantic: bool = None,
    similarity_threshold: float = None,
    use_llm_validation: bool = None,
    max_candidates: int = None
) -> Dict[str, Any]:
    """
    主入口：执行head节点去重
    
    Returns:
        {
            "enabled": True,
            "total_candidates": 100,
            "exact_merges": 10,
            "semantic_merges": 5,
            "total_merges": 15,
            "initial_entity_count": 100,
            "final_entity_count": 85,
            "reduction_rate": 15.0,
            "elapsed_time_seconds": 12.34,
            "integrity_issues": {...}
        }
    """
```

### 2. 辅助方法

| 方法 | 功能 |
|------|------|
| `_collect_head_candidates()` | 收集所有entity节点 |
| `_deduplicate_heads_exact()` | 精确匹配去重 |
| `_generate_semantic_candidates()` | 生成语义候选对 |
| `_validate_candidates_with_embedding()` | Embedding验证 |
| `_validate_candidates_with_llm()` | LLM验证 |
| `_merge_head_nodes()` | 执行节点合并 |
| `validate_graph_integrity_after_head_dedup()` | 完整性验证 |
| `export_head_merge_candidates_for_review()` | 导出审核文件 |

---

## 📊 配置参数详解

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | bool | false | 是否启用head去重 |
| `enable_semantic` | bool | true | 是否启用语义去重（精确匹配总是执行） |
| `similarity_threshold` | float | 0.85 | 语义相似度阈值（0.0-1.0） |
| `use_llm_validation` | bool | false | 是否使用LLM验证 |
| `max_candidates` | int | 1000 | 最大候选对数量 |
| `candidate_similarity_threshold` | float | 0.75 | 预筛选相似度阈值 |
| `max_relations_context` | int | 10 | 上下文中包含的最大关系数 |
| `export_review` | bool | false | 是否导出审核文件 |
| `review_confidence_range` | list | [0.70, 0.90] | 审核置信度区间 |
| `review_output_dir` | string | "output/review" | 审核文件输出目录 |

### 参数调优建议

#### 小图谱 (< 1k实体)
```yaml
similarity_threshold: 0.85
use_llm_validation: true   # 可以承受LLM成本
max_candidates: 5000
```

#### 中等图谱 (1k-10k实体)
```yaml
similarity_threshold: 0.87
use_llm_validation: false  # 使用embedding加速
max_candidates: 1000
```

#### 大图谱 (> 10k实体)
```yaml
similarity_threshold: 0.90  # 更严格，减少候选对
use_llm_validation: false
max_candidates: 500
```

---

## 🎨 Prompt自定义

### Prompt位置

Head去重的prompt现在存储在配置文件中：

**文件**: `config/base_config.yaml`  
**路径**: `prompts.head_dedup.general`

### 可用变量

在prompt中可以使用以下变量：
- `{entity_1}` - 第一个实体的描述
- `{context_1}` - 第一个实体的关系上下文
- `{entity_2}` - 第二个实体的描述
- `{context_2}` - 第二个实体的关系上下文

### 自定义示例

编辑 `config/base_config.yaml`:

```yaml
prompts:
  head_dedup:
    general: |-
      You are an expert in knowledge graph entity resolution.
      
      TASK: Determine if the following two entities refer to the SAME real-world object.
      
      Entity 1: {entity_1}
      Related knowledge about Entity 1:
      {context_1}
      
      Entity 2: {entity_2}
      Related knowledge about Entity 2:
      {context_2}
      
      # 在这里自定义你的判断规则...
      # 详见 HEAD_DEDUP_PROMPT_CUSTOMIZATION.md
```

**详细的Prompt自定义指南**: 请参考 `HEAD_DEDUP_PROMPT_CUSTOMIZATION.md`

---

## 🔄 完整Pipeline示例

```python
from models.constructor.kt_gen import KnowledgeTreeGen
from config import get_config

def build_complete_graph(corpus_path, dataset_name):
    """完整的知识图谱构建流程"""
    
    # 1. 初始化
    config = get_config()
    builder = KnowledgeTreeGen(dataset_name=dataset_name, config=config)
    
    # 2. 构建图谱
    print("Step 1: Building knowledge graph...")
    builder.build_knowledge_graph(corpus_path)
    
    # 3. Tail去重（如果启用）
    if config.construction.semantic_dedup.enabled:
        print("\nStep 2: Tail deduplication...")
        builder.triple_deduplicate_semantic()
    
    # 4. Head去重（如果启用）
    if hasattr(config.construction.semantic_dedup, 'head_dedup'):
        head_config = config.construction.semantic_dedup.head_dedup
        if getattr(head_config, 'enabled', False):
            print("\nStep 3: Head deduplication...")
            stats = builder.deduplicate_heads()
            
            print(f"\n✓ Head deduplication results:")
            print(f"  - Merged: {stats['total_merges']} nodes")
            print(f"  - Reduction: {stats['reduction_rate']:.1f}%")
            print(f"  - Time: {stats['elapsed_time_seconds']:.1f}s")
    
    # 5. 保存最终图谱
    print("\nStep 4: Saving final graph...")
    output_path = f"output/graphs/{dataset_name}_final.graphml"
    builder.save_graphml(output_path)
    print(f"✓ Saved to {output_path}")
    
    return builder

# 使用
builder = build_complete_graph(
    corpus_path="data/demo/demo_corpus.json",
    dataset_name="demo"
)
```

---

## 📈 性能预期

| 图规模 | 配置 | 预期时间 |
|--------|------|----------|
| 100实体 | 平衡模式 | < 5秒 |
| 1,000实体 | 平衡模式 | 10-30秒 |
| 10,000实体 | 平衡模式 | 1-5分钟 |
| 100,000实体 | 平衡模式 | 10-30分钟 |

**注**: 使用 `use_llm_validation=True` 会增加3-10倍时间

---

## 🔍 查看去重结果

### 1. 查看统计信息

```python
stats = builder.deduplicate_heads()

print(f"Initial entities: {stats['initial_entity_count']}")
print(f"Final entities: {stats['final_entity_count']}")
print(f"Exact merges: {stats['exact_merges']}")
print(f"Semantic merges: {stats['semantic_merges']}")
print(f"Reduction rate: {stats['reduction_rate']:.2f}%")
```

### 2. 查看合并历史

```python
for node_id, data in builder.graph.nodes(data=True):
    if data.get("label") != "entity":
        continue
    
    dedup_info = data.get("properties", {}).get("head_dedup", {})
    
    if dedup_info and dedup_info.get("merged_nodes"):
        print(f"\nCanonical: {node_id}")
        print(f"  Name: {data['properties']['name']}")
        print(f"  Merged: {len(dedup_info['merged_nodes'])} nodes")
        
        for record in dedup_info["merge_history"]:
            print(f"    • {record['merged_node_name']}")
            print(f"      Confidence: {record['confidence']:.2f}")
            print(f"      Method: {record['method']}")
```

### 3. 导出CSV审核

```python
builder.export_head_merge_candidates_for_review(
    output_path="output/review/head_merges.csv",
    min_confidence=0.70,
    max_confidence=0.90
)
```

CSV格式：
```
canonical_node_id,canonical_name,merged_node_id,merged_name,confidence,method,rationale
entity_5,北京,entity_10,北京市,0.85,embedding,High embedding similarity...
entity_15,Apple Inc.,entity_20,Apple Company,0.88,llm,Both refer to the same...
```

---

## ⚠️ 注意事项

### 1. 执行顺序
```
✓ 正确顺序:
  1. 构建图谱
  2. Tail去重（如果启用）
  3. Head去重
  4. 保存图谱

✗ 错误顺序:
  - 先Head去重后Tail去重（会有问题）
  - 在图谱构建中间执行（不完整）
```

### 2. 配置依赖
```python
# Head去重依赖这些现有功能：
- _batch_get_embeddings()      # 需要embedding模型
- _concurrent_llm_calls()       # 如果use_llm_validation=True
- _describe_node()              # 节点描述
- _describe_node_for_clustering()  # 简化描述
```

### 3. 性能考虑
- Embedding模式：O(n²) 相似度计算，但有预筛选
- LLM模式：更慢但更准，建议限制 `max_candidates`
- 大图谱建议分批处理或提高阈值

### 4. 图结构安全
- 所有边会自动转移到canonical节点
- 重复边会自动合并chunk信息
- 删除节点前会验证引用完整性
- 支持完整性验证方法

---

## 🐛 故障排除

### 问题1: "Head deduplication is disabled in config"

**原因**: 配置文件中 `head_dedup.enabled = false`

**解决**:
```yaml
# config/base_config.yaml
head_dedup:
  enabled: true  # 改为true
```

### 问题2: 没有找到任何候选对

**可能原因**:
- `candidate_similarity_threshold` 太高
- 实体名称太不相似
- Embedding模型问题

**解决**:
```yaml
candidate_similarity_threshold: 0.70  # 降低阈值试试
```

### 问题3: ImportError: scikit-learn

**原因**: 缺少依赖

**解决**:
```bash
pip install scikit-learn>=1.0
```

### 问题4: 合并了不该合并的节点

**解决**:
1. 提高 `similarity_threshold` (如 0.90)
2. 启用 `use_llm_validation: true`
3. 导出审核文件人工检查

---

## 📚 相关文档

详细设计和原理请参考：
- `HEAD_DEDUPLICATION_SOLUTION.md` - 完整方案设计
- `HEAD_DEDUP_LLM_CORE_LOGIC.md` - LLM判断逻辑详解
- `PROMPT_COMPARISON_HEAD_VS_TAIL_DEDUP.md` - 与tail去重对比
- `PROFESSIONAL_EVALUATION_PROMPTS.md` - 专业度评估
- `example_use_head_dedup.py` - 使用示例代码

---

## ✅ 测试建议

### 小规模测试
```python
# 1. 准备小数据集（10-20个文档）
# 2. 构建图谱
# 3. 查看初始实体数量
# 4. 执行head去重
# 5. 检查结果是否合理
# 6. 查看合并历史
```

### 验证正确性
```python
# 1. 运行完整性验证
issues = builder.validate_graph_integrity_after_head_dedup()
assert not any(issues.values()), f"Integrity issues: {issues}"

# 2. 检查图的基本属性
assert builder.graph.number_of_nodes() > 0
assert builder.graph.number_of_edges() > 0

# 3. 抽查几个合并结果
# 人工验证是否正确
```

---

## 🎉 总结

✅ **已集成功能**：
- 配置管理
- 精确匹配去重
- 语义相似度去重（Embedding）
- LLM验证（可选）
- 图结构更新
- 完整性验证
- 人工审核导出

✅ **代码质量**：
- 与现有代码风格一致
- 完整的错误处理
- 详细的日志输出
- 类型提示完整
- 文档字符串清晰

✅ **即用性**：
- 配置文件开箱即用
- 提供多种使用方式
- 包含完整示例代码
- 详细的使用文档

---

**集成状态**: ✅ 完成  
**测试状态**: ⏳ 待测试  
**文档状态**: ✅ 完整  

**建议下一步**：
1. 在小规模数据上测试功能
2. 根据实际效果调整参数
3. 考虑是否需要进一步优化Prompt

---

**版本**: v1.0  
**最后更新**: 2025-10-27
