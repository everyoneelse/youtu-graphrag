# 语义去重功能说明

## 功能概述

本项目实现了基于语义的三元组去重功能，能够识别并合并具有相同主体（head）和关系（relation）但尾实体（tail）描述略有不同但语义等价的三元组。

## 核心特性

### 1. 多级去重策略
- **精确去重**：移除完全相同的三元组
- **语义去重**：识别语义等价但表述不同的三元组

### 2. 智能语义判断
结合多种信息源进行准确的语义等价判断：

#### 2.1 Embedding 相似度筛选
- 使用 Sentence Transformers 计算文本嵌入
- 通过余弦相似度快速筛选候选等价对
- 减少 LLM 调用次数，提高效率

#### 2.2 原始文本 Chunk 上下文
- **关键创新**：利用实体和关系来源的原始文本 chunk 作为上下文
- 每个实体节点都关联了 `chunk id`
- LLM 判断时会参考原始 chunk 内容，提高准确性

#### 2.3 关键词（Keywords）特征
- 利用图谱中的 keyword 节点作为语义特征
- 帮助 LLM 理解实体的语义范围

#### 2.4 LLM 语义验证
- 支持成对验证（pairwise）模式
- 支持批量聚类（batch）模式
- 自动选择最优策略

### 3. 高效算法实现

#### 并查集（Union-Find）
- 管理等价关系的传递性
- 高效的集合合并和查询操作

#### 分组处理
- 按 (head, relation) 分组
- 每组独立处理，避免跨组误判

#### 代表选择
- 自动选择最完整、信息量最大的描述作为代表

## 配置说明

在 `config/base_config.yaml` 中配置语义去重参数：

```yaml
construction:
  semantic_dedup:
    enable: true                    # 是否启用语义去重
    similarity_threshold: 0.7       # 嵌入相似度阈值（0-1）
    batch_size: 8                   # LLM 批量处理大小
    use_chunk_context: true         # 是否使用原始 chunk 上下文
    use_keywords: true              # 是否使用关键词特征
```

### 参数说明

- **enable**: 
  - `true`: 启用语义去重
  - `false`: 仅使用精确去重

- **similarity_threshold**: 
  - 范围：0.0 ~ 1.0
  - 推荐值：0.7
  - 较高的值会更保守（减少误合并），较低的值会更激进

- **batch_size**: 
  - 每次 LLM 调用处理的尾实体数量
  - 较大的值减少调用次数但可能降低准确性
  - 推荐：5-10

- **use_chunk_context**: 
  - **强烈推荐启用**
  - 利用原始文本提高判断准确性

- **use_keywords**: 
  - 利用关键词作为额外的语义特征
  - 依赖于图谱中是否有 keyword 节点

## 工作流程

### 1. 图构建阶段
```
文档 → 分块 → 实体/关系抽取 → 图构建 → 三元组去重
                   ↓
              记录 chunk_id
```

### 2. 三元组去重流程
```
1. 精确去重（移除完全相同的三元组）
   ↓
2. 按 (head, relation) 分组
   ↓
3. 对每组：
   a. 提取所有 tail 实体
   b. 获取每个 tail 的 chunk 上下文和 keywords
   c. 计算 embedding 相似度（如果可用）
   d. 筛选出相似度高的候选对
   e. LLM 验证语义等价性
   f. 使用并查集合并等价实体
   g. 选择代表实体
   ↓
4. 移除非代表实体的边
   ↓
5. 输出去重后的图谱
```

## 使用示例

### 命令行使用
```bash
# 使用默认配置（启用语义去重）
python main.py --datasets demo

# 使用自定义配置
python main.py --datasets demo --config config/base_config.yaml

# 通过 JSON 覆盖配置（禁用语义去重）
python main.py --datasets demo --override '{"construction": {"semantic_dedup": {"enable": false}}}'
```

### 程序化使用
```python
from models.constructor import kt_gen
from config import get_config

# 加载配置
config = get_config("config/base_config.yaml")

# 创建图构建器
builder = kt_gen.KTBuilder(
    dataset_name="your_dataset",
    schema_path="schemas/your_schema.json",
    mode="agent",
    config=config
)

# 构建知识图谱（自动执行语义去重）
builder.build_knowledge_graph("data/your_corpus.json")
```

### 单独使用语义去重模块
```python
from utils.semantic_dedup import semantic_deduplicate_triples

# 准备三元组列表
triples = [
    "[公司A, 完成融资, 2018年获得1000万美元投资]",
    "[公司A, 完成融资, 在2018年完成了1000万美元的融资]",
    "[公司A, 完成融资, 2019年获得2000万美元投资]"
]

# 执行语义去重
deduplicated = semantic_deduplicate_triples(
    triples=triples,
    config=config,
    similarity_threshold=0.7,
    batch_size=8,
    use_chunk_context=True,
    use_keywords=True,
    graph=builder.graph,           # 可选：提供图对象以使用 chunk 信息
    all_chunks=builder.all_chunks  # 可选：提供 chunk 字典
)

print(f"原始: {len(triples)} 个三元组")
print(f"去重后: {len(deduplicated)} 个三元组")
```

## 示例场景

### 场景 1：同义表述
**输入三元组：**
- `[张三, 担任, CEO]`
- `[张三, 担任, 首席执行官]`
- `[张三, 担任, 公司总裁]`

**Chunk 上下文：**
- Chunk 1: "张三于2020年被任命为公司CEO..."
- Chunk 2: "张三担任首席执行官一职..."

**去重结果：**
- 保留：`[张三, 担任, CEO]`（选择最简洁的表述）
- 合并：另外两条作为语义等价项被移除

### 场景 2：时间敏感信息
**输入三元组：**
- `[公司A, 完成融资, 2018年1000万美元]`
- `[公司A, 完成融资, 2018年完成1000万A轮融资]`
- `[公司A, 完成融资, 2019年2000万美元]`

**Chunk 上下文：**
- Chunk 1: "公司A在2018年完成了1000万美元的A轮融资..."
- Chunk 2: "2019年，公司A获得了2000万美元的B轮融资..."

**去重结果：**
- 保留：`[公司A, 完成融资, 2018年完成1000万A轮融资]`（信息最完整）
- 保留：`[公司A, 完成融资, 2019年2000万美元]`（不同时间，不去重）

### 场景 3：属性值差异
**输入三元组：**
- `[iPhone 13, 屏幕尺寸, 6.1英寸]`
- `[iPhone 13, 屏幕尺寸, 6.1寸屏幕]`
- `[iPhone 13, 屏幕尺寸, 6.7英寸]`（错误信息）

**去重结果：**
- 保留：`[iPhone 13, 屏幕尺寸, 6.1英寸]`（标准表述）
- 保留：`[iPhone 13, 屏幕尺寸, 6.7英寸]`（虽然可能错误，但数值不同，不去重）

## 性能与成本

### 时间复杂度
- 精确去重：O(n)
- 分组：O(n)
- Embedding 计算：O(n * d)，其中 d 是嵌入维度
- LLM 调用：取决于分组数量和相似对数量

### 优化建议

1. **启用 Embedding 筛选**
   - 显著减少 LLM 调用次数
   - 需要安装 `sentence-transformers`

2. **调整相似度阈值**
   - 较高阈值（0.8-0.9）：更保守，减少 LLM 调用
   - 较低阈值（0.6-0.7）：更全面，但增加计算成本

3. **批量处理**
   - 对于小组（< 10 个 tail），使用批量模式
   - 减少 API 调用次数

4. **利用 Chunk 上下文**
   - 提高准确性，减少误判
   - 几乎不增加额外成本

## 依赖安装

```bash
# 基础依赖（必需）
pip install networkx numpy openai

# 嵌入模型（推荐）
pip install sentence-transformers

# 如需从 HuggingFace 下载模型
export HF_ENDPOINT=https://hf-mirror.com
```

## 日志与调试

语义去重会产生详细的日志输出：

```
INFO: Starting semantic deduplication...
DEBUG: Found 45 similar pairs for (公司A, 完成融资) with 10 tails
DEBUG: LLM verified 3 equivalent pairs
DEBUG: Group (公司A, 完成融资): removed 3 semantic duplicates
INFO: Semantic deduplication progress: 10/25 groups processed, 15 duplicates removed
INFO: Semantic deduplication summary: processed 25 groups, removed 35 duplicate edges
INFO: Semantic deduplication complete
```

## 常见问题

### Q1: 为什么有些明显重复的三元组没有被去重？
**A**: 可能的原因：
1. 相似度阈值设置过高
2. LLM 判断置信度低于 0.7
3. 缺少 chunk 上下文导致判断不准确

**解决方案**：
- 降低 `similarity_threshold` 到 0.6
- 确保 `use_chunk_context: true`
- 检查 LLM API 是否正常工作

### Q2: 语义去重速度很慢怎么办？
**A**: 优化建议：
1. 确保安装了 `sentence-transformers`
2. 提高 `similarity_threshold` 减少 LLM 调用
3. 增加 `batch_size` 减少调用次数
4. 考虑使用更快的 embedding 模型

### Q3: 如何禁用语义去重？
**A**: 在配置文件中设置 `enable: false`：
```yaml
construction:
  semantic_dedup:
    enable: false
```

### Q4: Chunk 上下文是如何工作的？
**A**: 
- 每个实体节点在创建时会记录其来源的 `chunk_id`
- 语义去重时，会查找实体对应的 chunk 内容
- LLM 在判断时会看到原始文本，提高准确性
- 例如：判断"CEO"和"首席执行官"时，如果 chunk 中写的是"张三担任公司CEO..."，LLM 会更倾向于认为这两个是等价的

### Q5: Keywords 特征有什么用？
**A**:
- Keywords 是图谱构建过程中提取的关键概念
- 可以帮助 LLM 理解实体的语义范围
- 例如：如果一个实体关联了"科技公司"、"互联网"等关键词，LLM 在判断时会考虑这些语义特征

## 未来改进方向

1. **增量去重**：支持新增三元组的增量去重
2. **人工审核**：对低置信度的等价判断提供人工审核接口
3. **统计报告**：生成详细的去重统计报告
4. **多语言支持**：优化对英文等其他语言的支持
5. **缓存机制**：缓存 embedding 和 LLM 判断结果

## 技术架构

```
SemanticTripleDeduplicator
│
├── UnionFind (并查集)
│   ├── find()
│   ├── union()
│   └── get_groups()
│
├── Embedding Layer
│   ├── SentenceTransformer
│   ├── compute_embeddings()
│   └── compute_similarity_matrix()
│
├── Context Extraction
│   ├── get_entity_chunk_info()
│   ├── Graph traversal
│   └── Keyword extraction
│
└── LLM Verification
    ├── Pairwise mode
    ├── Batch mode
    └── Prompt engineering
```

## 贡献与反馈

如有问题或建议，请提交 Issue 或 Pull Request。
