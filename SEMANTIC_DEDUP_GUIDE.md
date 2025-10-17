# 语义去重功能使用指南

## 概述

本仓库现已支持基于 LLM 和 embedding 的**语义去重**功能，可对知识图谱中的三元组（triples）和关键词节点（keywords）进行智能去重。

## 功能特性

### 1. **三元组语义去重**
- 对 `(head, relation)` 相同但 `tail` 不同的三元组进行语义判断
- 基于 chunk 上下文，使用 LLM 判断多个 tail 是否语义等价
- 保留最具信息量的代表 tail，其他等价的 tail 信息会被合并到元数据中

### 2. **Keyword 语义去重**
- Keyword 节点继承其代表实体的 `chunk_id`
- 利用 chunk 上下文判断 keyword 的语义等价性
- 同一社区内的语义相同的 keyword 会被合并

## 配置说明

在 `config/base_config.yaml` 中配置语义去重参数：

```yaml
construction:
  semantic_dedup:
    enabled: true  # 是否启用语义去重
    embedding_threshold: 0.85  # embedding 相似度阈值（用于初步聚类）
    max_batch_size: 8  # 每次发送给 LLM 判断的最大候选数
    max_candidates: 50  # 每个聚类最多处理的候选数
    use_embeddings: true  # 是否使用 embedding 进行预筛选
    prompt_type: general  # 使用的 prompt 类型
```

### 参数说明

- **enabled**: 是否启用语义去重（默认 `false`）
- **embedding_threshold**: embedding 相似度阈值（0-1），用于初步将相似的候选聚类，减少 LLM 调用次数
- **max_batch_size**: 每批发送给 LLM 的候选数量，建议 5-10
- **max_candidates**: 每个 `(head, relation)` 分组最多处理的候选数量，避免处理超大分组
- **use_embeddings**: 是否使用 embedding 进行预筛选（建议开启，可大幅降低成本）
- **prompt_type**: Prompt 类型，可选 `general`、`novel` 等

## 使用方法

### 方式一：在线构建时自动去重

在构建知识图谱时，如果启用了 `semantic_dedup.enabled: true`，系统会自动在构建过程中进行语义去重：

```bash
python main.py --dataset demo --mode construct
```

### 方式二：离线对已有图谱进行去重

对于已经构建好的图谱，可以使用离线脚本进行语义去重：

```bash
python offline_semantic_dedup.py \
    --graph output/graphs/demo_new.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_deduped.json \
    --force-enable
```

#### 参数说明

- `--graph`: 输入的图谱 JSON 文件路径
- `--chunks`: chunk 文件路径（支持目录或单个文件）
- `--output`: 输出的去重后图谱 JSON 文件路径
- `--config`: （可选）自定义配置文件路径
- `--force-enable`: 强制启用语义去重（即使配置中禁用）

## 工作原理

### 三元组去重流程

1. **精确去重**：首先移除完全相同的三元组（包括 chunk 来源合并）
2. **分组**：按 `(head, relation)` 对三元组进行分组
3. **Embedding 聚类**（可选）：
   - 对每组内的所有 `tail` 计算 embedding
   - 基于余弦相似度进行初步聚类
   - 相似度低于阈值的直接分到不同组，无需 LLM 判断
4. **LLM 语义判断**：
   - 对每个聚类分批发送给 LLM
   - LLM 根据 `head`、`relation` 和 chunk 上下文判断哪些 tail 语义等价
   - 返回分组结果及代表项
5. **合并元数据**：
   - 保留代表项，删除重复边
   - 将被去重的信息存储在 `semantic_dedup` 元数据字段中

### Keyword 去重流程

1. **提取 Keyword 映射**：找出每个 keyword 对应的源实体
2. **继承 Chunk 上下文**：keyword 继承其源实体的 chunk_id
3. **社区内去重**：
   - 按社区分组 keyword
   - 在每个社区内，使用与三元组相同的流程进行语义去重
4. **合并节点**：删除重复 keyword 节点，重新连接边

## 输出元数据

去重后的三元组或节点会包含 `semantic_dedup` 元数据，记录去重信息：

```json
{
  "relation": "founded_in",
  "source_chunks": ["chunk_001", "chunk_005", "chunk_012"],
  "semantic_dedup": {
    "representative_chunk_ids": ["chunk_001", "chunk_005"],
    "representative_contexts": [
      "- (chunk_001) The company was founded in 2010…",
      "- (chunk_005) It started operations in 2010…"
    ],
    "rationales": [
      "Both chunks describe the same founding event in 2010."
    ],
    "duplicates": [
      {
        "tail_node": "entity_123",
        "tail_description": "2010 (from founding event)",
        "context_chunk_ids": ["chunk_012"],
        "context_summaries": ["- (chunk_012) The establishment year was 2010"]
      }
    ]
  }
}
```

## 算法复杂度优化

为避免 `O(n²)` 的成对比较，本实现采用以下策略：

1. **Embedding 预筛选**：将 n 个候选快速聚类成若干小组
2. **分批处理**：每次只向 LLM 发送小批量（如 8 个）候选
3. **代表驱动**：每个聚类维护代表项，新候选只需与代表项比较
4. **阈值限制**：对超大分组（如 >50 个）进行截断，避免过度调用

实际场景中，10 个候选通常只需要 2-3 次 LLM 调用即可完成去重。

## 成本与效果

- **无 embedding 预筛选**：n=10 时约 45 次 LLM 调用（最坏情况）
- **有 embedding 预筛选**：n=10 时约 2-3 次 LLM 调用（实际场景）
- **准确率**：基于上下文的 LLM 判断，显著优于纯字符串匹配

## 注意事项

1. **LLM 成本**：语义去重会调用 LLM，请根据数据规模评估成本
2. **Embedding 模型**：默认使用 `all-MiniLM-L6-v2`，可在配置中修改
3. **Chunk 必需**：语义去重依赖 chunk 上下文，确保 chunks 文件完整
4. **阈值调优**：根据数据特点调整 `embedding_threshold` 和 `max_batch_size`

## 示例

假设有以下三元组（head 和 relation 相同）：

```
(Tesla, founded_in, 2003)  [chunk_001: "Tesla was incorporated in 2003"]
(Tesla, founded_in, 2003)  [chunk_005: "The company Tesla Motors was founded in 2003"]
(Tesla, founded_in, July 2003)  [chunk_012: "Tesla started in July 2003"]
```

语义去重后：
- 保留 `(Tesla, founded_in, July 2003)` 作为代表（信息最完整）
- 其他两条信息合并到 `semantic_dedup.duplicates` 中
- 所有 chunk_id 都保留在 `source_chunks` 中

## 故障排查

### 问题：语义去重没有生效

**检查项**：
1. 确认 `semantic_dedup.enabled: true`
2. 查看日志，确认是否有 "Using semantic deduplication" 信息
3. 使用 `--force-enable` 参数强制启用

### 问题：Embedding 加载失败

**解决方案**：
```bash
# 安装 sentence-transformers
pip install sentence-transformers

# 如果需要从 huggingface 下载模型，设置镜像
export HF_ENDPOINT=https://hf-mirror.com
```

### 问题：去重效果不理想

**调优建议**：
1. 降低 `embedding_threshold`（如 0.75），扩大候选范围
2. 增加 `max_batch_size`，让 LLM 一次看到更多候选
3. 检查 prompt 是否适合你的领域，考虑自定义 prompt

## 总结

基于 chunks 和 LLM 的语义去重能够：
- ✅ 识别语义等价的三元组和 keyword
- ✅ 基于上下文进行高质量判断
- ✅ 保留所有证据信息（chunk 来源）
- ✅ 通过 embedding 预筛选控制成本

适用于构建高质量、去重后的知识图谱。
