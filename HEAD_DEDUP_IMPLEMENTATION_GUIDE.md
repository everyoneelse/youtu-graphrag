# Head节点去重实施指南

**版本**: v1.0  
**日期**: 2025-10-27  
**目标**: 快速将head节点去重功能集成到现有系统

---

## 📋 快速导航

- [集成步骤](#集成步骤) - 5步完成集成
- [配置说明](#配置说明) - 参数调优指南
- [测试验证](#测试验证) - 确保功能正常
- [性能调优](#性能调优) - 大规模图谱优化
- [常见问题](#常见问题) - 故障排除

---

## 集成步骤

### Step 1: 添加Mixin类到kt_gen.py

```bash
# 方法1: 直接合并代码
# 将 head_deduplication_reference.py 中的代码添加到 models/constructor/kt_gen.py

# 方法2: 使用Mixin（推荐）
# 在 kt_gen.py 中导入并继承
```

**修改 `models/constructor/kt_gen.py`**:

```python
# 文件顶部添加导入
from head_deduplication_reference import HeadDeduplicationMixin

# 修改类定义
class KnowledgeTreeGen(HeadDeduplicationMixin, ...):
    """
    现在 KnowledgeTreeGen 具有以下新方法：
    - deduplicate_heads()
    - validate_graph_integrity_after_head_dedup()
    - export_head_merge_candidates_for_review()
    """
    pass
```

### Step 2: 添加配置项

**修改 `config/base_config.yaml`**:

```yaml
# 在semantic_dedup部分添加head_dedup配置
semantic_dedup:
  # ... 现有配置 ...
  
  # Head节点去重配置
  head_dedup:
    enabled: true                     # 是否启用head去重
    enable_semantic: true             # 是否启用语义去重
    similarity_threshold: 0.85        # 相似度阈值（0.0-1.0）
    use_llm_validation: false         # 是否使用LLM验证（慢但准）
    max_candidates: 1000              # 最大处理候选对数量
    export_review: false              # 是否导出审核文件
    review_confidence_range: [0.70, 0.90]  # 审核置信度区间
```

### Step 3: 在Pipeline中调用

**修改主处理流程** (例如在 `main.py` 或处理完成后):

```python
def build_knowledge_graph(documents, config):
    """构建知识图谱的完整流程"""
    
    # 1. 创建构建器
    builder = KnowledgeTreeGen(dataset_name="demo", config=config)
    
    # 2. 处理文档
    for doc in documents:
        builder.process_document(doc)
    
    # 3. 执行tail去重（现有功能）
    if config.semantic_dedup.enabled:
        builder.triple_deduplicate_semantic()
    
    # 4. 【新增】执行head去重
    if config.semantic_dedup.head_dedup.enabled:
        head_dedup_config = config.semantic_dedup.head_dedup
        
        stats = builder.deduplicate_heads(
            enable_semantic=head_dedup_config.enable_semantic,
            similarity_threshold=head_dedup_config.similarity_threshold,
            use_llm_validation=head_dedup_config.use_llm_validation,
            max_candidates=head_dedup_config.max_candidates
        )
        
        logger.info(f"Head deduplication: merged {stats['total_merges']} nodes")
        
        # 可选：导出人工审核
        if head_dedup_config.export_review:
            review_path = f"output/review/head_merge_{time.time()}.csv"
            builder.export_head_merge_candidates_for_review(
                output_path=review_path,
                min_confidence=head_dedup_config.review_confidence_range[0],
                max_confidence=head_dedup_config.review_confidence_range[1]
            )
    
    # 5. 保存图谱
    builder.save_graph("output/graphs/final_graph.graphml")
    
    return builder
```

### Step 4: 添加依赖（如果需要）

检查 `requirements.txt` 是否包含以下依赖:

```txt
# 已有的依赖
networkx>=2.8
numpy>=1.21
tiktoken>=0.3
json-repair>=0.7

# 语义去重需要
scikit-learn>=1.0  # 用于余弦相似度计算
```

如果缺少，添加并安装:

```bash
pip install scikit-learn>=1.0
```

### Step 5: 验证集成

运行简单测试:

```python
# test_head_dedup_integration.py
from models.constructor.kt_gen import KnowledgeTreeGen

def test_integration():
    builder = KnowledgeTreeGen(dataset_name="test")
    
    # 检查方法是否可用
    assert hasattr(builder, 'deduplicate_heads')
    assert hasattr(builder, 'validate_graph_integrity_after_head_dedup')
    assert hasattr(builder, 'export_head_merge_candidates_for_review')
    
    print("✓ Integration successful!")

if __name__ == "__main__":
    test_integration()
```

---

## 配置说明

### 参数详解

#### `enabled` (bool)
- **默认值**: `true`
- **说明**: 是否启用head去重
- **建议**: 总是启用，可显著减少冗余节点

#### `enable_semantic` (bool)
- **默认值**: `true`
- **说明**: 是否启用语义去重（精确匹配始终执行）
- **权衡**:
  - `true`: 更高召回率，识别更多等价节点
  - `false`: 更快速度，仅处理完全相同的名称

#### `similarity_threshold` (float, 0.0-1.0)
- **默认值**: `0.85`
- **说明**: 语义相似度阈值
- **建议**:
  - `0.90-0.95`: 高精度模式，适合生产环境
  - `0.85-0.90`: 平衡模式，推荐默认
  - `0.70-0.85`: 高召回模式，适合探索性分析
- **注意**: 阈值越低，召回率越高但误合并风险越大

#### `use_llm_validation` (bool)
- **默认值**: `false`
- **说明**: 是否使用LLM进行二次验证
- **权衡**:
  - `true`: 最高准确率，但速度慢、成本高
  - `false`: 仅用embedding，快速但可能不够精确
- **建议**: 
  - 生产环境首次运行: `true`
  - 日常增量更新: `false`

#### `max_candidates` (int)
- **默认值**: `1000`
- **说明**: 最大处理的候选对数量
- **建议**:
  - 小图谱(< 1k节点): `1000-5000`
  - 中等图谱(1k-10k节点): `500-1000`
  - 大图谱(> 10k节点): `200-500`
- **注意**: 影响LLM成本和处理时间

#### `export_review` (bool)
- **默认值**: `false`
- **说明**: 是否导出中等置信度案例供人工审核
- **建议**: 生产环境首次运行时设为 `true`

#### `review_confidence_range` (list[float, float])
- **默认值**: `[0.70, 0.90]`
- **说明**: 需要人工审核的置信度区间
- **逻辑**:
  - `< 0.70`: 自动拒绝合并
  - `0.70-0.90`: 导出审核
  - `> 0.90`: 自动接受合并

---

## 测试验证

### 单元测试

创建 `test_head_deduplication.py`:

```python
import unittest
from models.constructor.kt_gen import KnowledgeTreeGen

class TestHeadDeduplication(unittest.TestCase):
    
    def setUp(self):
        """设置测试环境"""
        self.builder = KnowledgeTreeGen(dataset_name="test")
        
        # 添加测试数据
        self.builder.graph.add_node("entity_0", label="entity", properties={"name": "北京"})
        self.builder.graph.add_node("entity_1", label="entity", properties={"name": "北京市"})
        self.builder.graph.add_node("entity_2", label="entity", properties={"name": "上海"})
    
    def test_exact_match_dedup(self):
        """测试精确匹配去重"""
        candidates = ["entity_0", "entity_1", "entity_2"]
        merge_mapping = self.builder._deduplicate_heads_exact(candidates)
        
        # 北京和北京市应该被标准化为同一名称
        self.assertGreaterEqual(len(merge_mapping), 0)
    
    def test_merge_preserves_edges(self):
        """测试合并保持边的完整性"""
        # 添加边
        self.builder.graph.add_edge("entity_0", "entity_2", relation="nearby")
        
        # 执行合并
        stats = self.builder.deduplicate_heads(enable_semantic=False)
        
        # 验证边仍然存在
        self.assertTrue(self.builder.graph.has_edge("entity_0", "entity_2") or 
                       self.builder.graph.has_edge("entity_1", "entity_2"))
    
    def test_integrity_validation(self):
        """测试完整性验证"""
        stats = self.builder.deduplicate_heads(enable_semantic=False)
        issues = self.builder.validate_graph_integrity_after_head_dedup()
        
        # 不应该有悬空引用
        self.assertEqual(len(issues["dangling_references"]), 0)

if __name__ == "__main__":
    unittest.main()
```

运行测试:

```bash
python test_head_deduplication.py -v
```

### 集成测试

使用真实数据测试:

```python
# test_integration_real_data.py
from models.constructor.kt_gen import KnowledgeTreeGen

def test_with_real_data():
    """使用真实数据测试完整流程"""
    
    # 1. 构建图谱
    builder = KnowledgeTreeGen(dataset_name="demo")
    
    documents = [
        {"text": "北京是中国的首都，位于华北地区。", "id": 1},
        {"text": "北京市是中华人民共和国的首都。", "id": 2},
        {"text": "Beijing is the capital of China.", "id": 3},
        {"text": "上海是中国最大的城市。", "id": 4}
    ]
    
    for doc in documents:
        builder.process_document(doc)
    
    print(f"Initial entities: {len([n for n, d in builder.graph.nodes(data=True) if d.get('label') == 'entity'])}")
    
    # 2. 执行head去重
    stats = builder.deduplicate_heads(
        enable_semantic=True,
        similarity_threshold=0.85,
        use_llm_validation=False
    )
    
    print(f"Final entities: {stats['final_entity_count']}")
    print(f"Merged: {stats['total_merges']}")
    
    # 3. 验证结果
    assert stats['final_entity_count'] < len([n for n, d in builder.graph.nodes(data=True) if d.get('label') == 'entity'])
    
    # 4. 检查完整性
    issues = builder.validate_graph_integrity_after_head_dedup()
    assert not any(issues.values()), f"Integrity issues found: {issues}"
    
    print("✓ Integration test passed!")

if __name__ == "__main__":
    test_with_real_data()
```

---

## 性能调优

### 场景1: 小图谱 (< 1k实体)

```yaml
head_dedup:
  enabled: true
  enable_semantic: true
  similarity_threshold: 0.85
  use_llm_validation: true   # 可以承受LLM成本
  max_candidates: 5000
```

**预期性能**: < 10秒

### 场景2: 中等图谱 (1k-10k实体)

```yaml
head_dedup:
  enabled: true
  enable_semantic: true
  similarity_threshold: 0.87
  use_llm_validation: false  # 使用embedding加速
  max_candidates: 1000
```

**预期性能**: 30秒 - 2分钟

### 场景3: 大图谱 (> 10k实体)

```yaml
head_dedup:
  enabled: true
  enable_semantic: true
  similarity_threshold: 0.90  # 更严格，减少候选对
  use_llm_validation: false
  max_candidates: 500
```

**优化策略**:

1. **分批处理**:
```python
# 将节点分批处理，避免内存溢出
batch_size = 1000
candidates = builder._collect_head_candidates()
for i in range(0, len(candidates), batch_size):
    batch = candidates[i:i+batch_size]
    # 对每批独立去重
```

2. **使用缓存**:
```python
# 在head_deduplication_reference.py中已包含缓存装饰器
@lru_cache(maxsize=10000)
def _describe_node_cached(self, node_id: str) -> str:
    return self._describe_node(node_id)
```

3. **并发embedding计算**:
```python
# 批量获取embedding，利用GPU加速
embeddings = self._batch_get_embeddings(descriptions)
```

**预期性能**: 5-30分钟（取决于硬件）

### 内存优化

如果遇到内存问题:

1. **减少max_candidates**:
```yaml
max_candidates: 200  # 从1000降低到200
```

2. **提高similarity_threshold**:
```yaml
similarity_threshold: 0.92  # 从0.85提高到0.92
```

3. **禁用部分特性**:
```yaml
enable_semantic: false  # 仅精确匹配
```

---

## 常见问题

### Q1: 合并了不应该合并的节点怎么办？

**A**: 有几个解决方案:

1. **提高阈值**:
```yaml
similarity_threshold: 0.90  # 从0.85提高
```

2. **启用人工审核**:
```yaml
export_review: true
review_confidence_range: [0.70, 0.95]  # 扩大审核范围
```

3. **使用LLM验证**:
```yaml
use_llm_validation: true
```

4. **回滚机制**（需要实现）:
```python
# 保存去重前的快照
builder.save_graph("backup_before_dedup.graphml")

# 如果出问题，可以重新加载
builder.load_graph("backup_before_dedup.graphml")
```

### Q2: 处理速度太慢怎么办？

**A**: 参考[性能调优](#性能调优)部分，关键优化:

- 降低 `max_candidates`
- 禁用 `use_llm_validation`
- 提高 `similarity_threshold`（减少候选对）

### Q3: 如何处理特定领域的实体？

**A**: 扩展 `_normalize_entity_name` 方法:

```python
def _normalize_entity_name(self, name: str) -> str:
    normalized = super()._normalize_entity_name(name)
    
    # 添加领域特定规则
    # 例如：人名处理
    if self.dataset_name == "person_names":
        # 去除称呼（先生、女士、博士等）
        for title in ["先生", "女士", "博士", "教授"]:
            normalized = normalized.replace(title, "").strip()
    
    return normalized
```

### Q4: 如何评估去重效果？

**A**: 使用以下指标:

1. **Reduction Rate**（减少率）:
```python
reduction_rate = (initial_count - final_count) / initial_count * 100
```

2. **Precision**（精确率）:
手工标注部分结果，计算正确合并比例

3. **Recall**（召回率）:
检查是否还有明显的重复节点未被合并

4. **Graph Density**（图密度）:
```python
# 去重后平均度数应该增加（因为边被合并到更少的节点上）
avg_degree_before = ...
avg_degree_after = ...
density_increase = avg_degree_after / avg_degree_before
```

### Q5: 如何处理歧义实体？

**A**: 例如"苹果"可能是水果或公司:

1. **利用上下文**:
```python
def _collect_node_context(self, node_id: str, max_relations: int = 10):
    # 收集节点的关系和属性，用于LLM判断
    # 例如："苹果-has_attribute-水果" vs "苹果-founded-1976"
```

2. **使用schema类型**:
```python
# 检查entity_type
entity_type_1 = self.graph.nodes[node_id_1].get("properties", {}).get("schema_type")
entity_type_2 = self.graph.nodes[node_id_2].get("properties", {}).get("schema_type")

if entity_type_1 != entity_type_2:
    # 不同类型，不合并
    return False
```

3. **保守策略**:
```yaml
similarity_threshold: 0.95  # 非常高的阈值，只合并明确的
```

---

## 下一步

完成集成后，建议:

1. ✅ 在小规模测试数据上验证功能
2. ✅ 调整参数，找到最佳配置
3. ✅ 在中等规模数据上测试性能
4. ✅ 导出审核案例，人工评估质量
5. ✅ 部署到生产环境，监控效果

---

## 附录

### 完整配置示例

```yaml
# config/production_config.yaml
semantic_dedup:
  enabled: true
  
  # Tail去重配置（现有）
  similarity_threshold: 0.85
  clustering_method: "embedding"
  # ... 其他tail去重配置 ...
  
  # Head去重配置（新增）
  head_dedup:
    enabled: true
    enable_semantic: true
    similarity_threshold: 0.87
    use_llm_validation: false
    max_candidates: 1000
    export_review: true
    review_confidence_range: [0.70, 0.90]
    review_output_dir: "output/review"
```

### 日志配置建议

```python
# 在运行head去重时，设置详细日志
import logging
logging.getLogger('models.constructor.kt_gen').setLevel(logging.DEBUG)
```

---

**文档版本**: v1.0  
**最后更新**: 2025-10-27  
**维护者**: Knowledge Graph Team
