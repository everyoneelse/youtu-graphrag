# Offline Semantic Dedup 使用指南

## 概述

`offline_semantic_dedup.py` 是一个离线工具，用于对已经构建好的知识图谱进行语义去重。它可以：

- ✅ 对三元组（triples）进行语义去重
- ✅ 对关键词（keywords）节点进行语义去重
- ✅ 支持精确去重和语义去重两种模式
- ✅ 保留所有去重信息的元数据
- ✅ 无需重新构建图谱

## 前提条件

### 1. 环境依赖

确保已安装以下 Python 包：

```bash
pip install networkx nanoid json-repair tiktoken sentence-transformers \
            openai requests numpy scipy scikit-learn pydantic python-dotenv PyYAML
```

或者直接安装项目的所有依赖：

```bash
pip install -r requirements.txt
```

### 2. 运行环境

**重要**：使用系统 Python 而非虚拟环境中的 Python：

```bash
# 推荐使用完整路径
/usr/bin/python3 offline_semantic_dedup.py [参数]

# 或者确保 python3 在 PATH 中且正确配置
python3 offline_semantic_dedup.py [参数]
```

### 3. API Key（仅语义去重需要）

如果要使用语义去重功能，需要配置 LLM API Key：

创建 `.env` 文件：
```bash
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.deepseek.com  # 可选，默认 deepseek
LLM_MODEL=deepseek-chat  # 可选，默认 deepseek-chat
```

或者设置环境变量：
```bash
export LLM_API_KEY=your_api_key_here
export LLM_BASE_URL=https://api.deepseek.com
export LLM_MODEL=deepseek-chat
```

## 基本用法

### 查看帮助信息

```bash
/usr/bin/python3 offline_semantic_dedup.py --help
```

输出：
```
usage: offline_semantic_dedup.py [-h] --graph GRAPH --chunks CHUNKS
                                 --output OUTPUT [--config CONFIG]
                                 [--force-enable]

Offline semantic deduplication for Youtu-GraphRAG graphs

options:
  -h, --help       show this help message and exit
  --graph GRAPH    Path to the input graph JSON file
  --chunks CHUNKS  Path to the chunk file or directory
  --output OUTPUT  Where to save the deduplicated graph JSON
  --config CONFIG  Optional path to a configuration YAML file overriding the
                   default base_config.yaml
  --force-enable   Force-enable semantic dedup even if disabled in the
                   configuration
```

### 参数说明

| 参数 | 必需 | 说明 | 示例 |
|-----|------|------|------|
| `--graph` | ✅ | 输入的图谱 JSON 文件路径 | `output/graphs/demo_new.json` |
| `--chunks` | ✅ | Chunk 文件或目录路径 | `output/chunks/demo.txt` |
| `--output` | ✅ | 输出的去重后图谱文件路径 | `output/graphs/demo_deduped.json` |
| `--config` | ❌ | 自定义配置文件（可选） | `config/semantic_dedup_enabled.yaml` |
| `--force-enable` | ❌ | 强制启用语义去重 | - |

## 使用示例

### 示例 1：精确去重（无需 API Key）

默认情况下，如果配置中 `semantic_dedup.enabled: false`，脚本会进行精确去重：

```bash
/usr/bin/python3 offline_semantic_dedup.py \
    --graph output/graphs/demo_new.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_deduped.json
```

输出示例：
```
[WARNING] Semantic deduplication is disabled in the configuration.
[INFO] Use --force-enable to enable semantic dedup, or enable it in config.
[INFO] Falling back to exact deduplication only.
[INFO] Edges: 239 → 238 | Keyword nodes: 31 → 31
[INFO] Deduplicated graph written to output/graphs/demo_deduped.json
```

**特点**：
- ✅ 不需要 LLM API Key
- ✅ 速度快，无成本
- ✅ 只去除完全相同的三元组

### 示例 2：语义去重（需要 API Key）

#### 方法 1：修改配置文件

编辑 `config/base_config.yaml`：

```yaml
construction:
  semantic_dedup:
    enabled: true  # 改为 true
    embedding_threshold: 0.85
    max_batch_size: 8
    max_candidates: 50
    use_embeddings: true
```

然后运行：

```bash
# 确保已设置 LLM_API_KEY
export LLM_API_KEY=your_api_key_here

/usr/bin/python3 offline_semantic_dedup.py \
    --graph output/graphs/demo_new.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_semantic_deduped.json
```

#### 方法 2：使用自定义配置文件

使用提供的启用语义去重的配置文件：

```bash
export LLM_API_KEY=your_api_key_here

/usr/bin/python3 offline_semantic_dedup.py \
    --graph output/graphs/demo_new.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_semantic_deduped.json \
    --config config/semantic_dedup_enabled.yaml
```

#### 方法 3：使用 --force-enable 参数

即使配置文件中禁用了语义去重，也可以通过参数强制启用：

```bash
export LLM_API_KEY=your_api_key_here

/usr/bin/python3 offline_semantic_dedup.py \
    --graph output/graphs/demo_new.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_semantic_deduped.json \
    --force-enable
```

输出示例：
```
[INFO] Semantic deduplication is enabled
[INFO] Config: threshold=0.85, max_batch_size=8, use_embeddings=True
[INFO] Loading graph from output/graphs/demo_new.json
[INFO] Loading chunk contexts from output/chunks/demo.txt
[INFO] Loaded 3 chunks
[INFO] Running triple semantic deduplication
[INFO] Using semantic deduplication for triples
[INFO] Running keyword semantic deduplication
[INFO] Found 31 keyword nodes to deduplicate
[INFO] Edges: 239 → 235 | Keyword nodes: 31 → 28
[INFO] Deduplicated graph written to output/graphs/demo_semantic_deduped.json
```

**特点**：
- ✅ 基于 LLM 和 embedding 进行语义判断
- ✅ 能识别语义相同但表述不同的内容
- ✅ 保留所有去重信息在元数据中
- ⚠️ 需要 LLM API Key，有调用成本

## 完整工作流示例

假设你已经构建了图谱，现在想对其进行离线语义去重：

```bash
# 1. 确保环境依赖已安装
pip install -r requirements.txt

# 2. 配置 LLM API Key（如果使用语义去重）
cat > .env << 'EOF'
LLM_API_KEY=sk-xxxxxxxxxxxxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
EOF

# 3. 运行语义去重
/usr/bin/python3 offline_semantic_dedup.py \
    --graph output/graphs/demo_new.json \
    --chunks output/chunks/demo.txt \
    --output output/graphs/demo_deduped.json \
    --config config/semantic_dedup_enabled.yaml

# 4. 检查输出
ls -lh output/graphs/demo_deduped.json
```

## 配置参数详解

在配置文件中调整语义去重参数：

```yaml
construction:
  semantic_dedup:
    # 是否启用语义去重
    enabled: true
    
    # Embedding 相似度阈值（0-1）
    # 用于初步聚类，降低 LLM 调用次数
    # 建议：0.75-0.90
    embedding_threshold: 0.85
    
    # 每批发送给 LLM 的最大候选数
    # 建议：5-10
    max_batch_size: 8
    
    # 每个 (head, relation) 分组最多处理的候选数
    # 建议：50-100
    max_candidates: 50
    
    # 是否使用 embedding 进行预筛选
    # 建议：true（可大幅降低成本）
    use_embeddings: true
    
    # Prompt 类型
    # 可选：general, novel
    prompt_type: general
```

### 参数调优建议

| 场景 | embedding_threshold | max_batch_size | max_candidates |
|-----|---------------------|----------------|----------------|
| 高精度（保守） | 0.90 | 5 | 50 |
| 平衡（推荐） | 0.85 | 8 | 50 |
| 高召回（激进） | 0.75 | 10 | 100 |
| 成本优先 | 0.90 | 5 | 30 |

## 输出结果

### 统计信息

脚本会输出去重前后的统计信息：

```
Edges: 239 → 235 | Keyword nodes: 31 → 28
```

- **Edges**：三元组数量变化
- **Keyword nodes**：关键词节点数量变化

### 元数据

去重后的边会包含 `semantic_dedup` 元数据：

```json
{
  "relation": "founded_in",
  "source_chunks": ["chunk_001", "chunk_005"],
  "semantic_dedup": {
    "representative_chunk_ids": ["chunk_001"],
    "representative_contexts": [
      "- (chunk_001) The company was founded in 2010…"
    ],
    "rationales": [
      "Both describe the same founding event."
    ],
    "duplicates": [
      {
        "tail_node": "entity_123",
        "tail_description": "2010",
        "context_chunk_ids": ["chunk_005"]
      }
    ]
  }
}
```

## 故障排查

### 问题 1：找不到模块

```
ModuleNotFoundError: No module named 'networkx'
```

**解决方案**：
```bash
pip install -r requirements.txt
```

### 问题 2：LLM API key not provided

```
ValueError: LLM API key not provided
```

**解决方案**：
```bash
# 方法 1：创建 .env 文件
echo "LLM_API_KEY=your_key_here" > .env

# 方法 2：设置环境变量
export LLM_API_KEY=your_key_here

# 方法 3：如果只想用精确去重，不要使用 --force-enable
# 并确保配置中 semantic_dedup.enabled: false
```

### 问题 3：Python 命令找不到

```
python: command not found
```

**解决方案**：
```bash
# 使用 python3
python3 offline_semantic_dedup.py [参数]

# 或使用完整路径
/usr/bin/python3 offline_semantic_dedup.py [参数]
```

### 问题 4：Chunk 文件不存在

```
FileNotFoundError: Chunk file or directory not found
```

**解决方案**：
- 确保在构建图谱时生成了 chunk 文件
- 检查 chunk 文件路径是否正确
- chunk 文件通常在 `output/chunks/` 目录下

### 问题 5：语义去重没有效果

**可能原因**：
1. 数据本身没有语义重复项
2. `embedding_threshold` 设置过高

**解决方案**：
- 降低 `embedding_threshold` 到 0.75
- 检查日志，查看是否有聚类和 LLM 调用
- 使用 `--force-enable` 确保语义去重已启用

## 性能和成本

### 精确去重
- **速度**：非常快（秒级）
- **成本**：无
- **适用场景**：数据质量较好，重复项少

### 语义去重
- **速度**：取决于数据量和 LLM 调用次数
- **成本**：每次 LLM 调用约 0.001-0.01 元（取决于 API 提供商）
- **优化策略**：
  - 启用 `use_embeddings: true` 可减少 90% 以上的 LLM 调用
  - 调整 `max_candidates` 限制处理的最大候选数
  - 使用更便宜的 LLM 模型

### 估算成本

假设：
- 图谱有 1000 个三元组
- 其中 100 个有潜在重复
- 使用 embedding 预筛选后，需要 LLM 判断 20 次
- 每次调用成本 0.002 元

**总成本**：20 × 0.002 = 0.04 元

## 最佳实践

1. **先测试小数据集**
   ```bash
   # 用小图谱测试
   /usr/bin/python3 offline_semantic_dedup.py \
       --graph output/graphs/demo_new.json \
       --chunks output/chunks/demo.txt \
       --output output/graphs/test_deduped.json \
       --force-enable
   ```

2. **逐步调整参数**
   - 从默认参数开始
   - 观察去重效果和成本
   - 根据需要调整 threshold 和 batch_size

3. **保留原始图谱**
   - 始终指定不同的输出文件名
   - 保留原始图谱文件以便对比

4. **检查去重质量**
   - 查看输出的统计信息
   - 随机抽查一些去重后的节点
   - 检查 `semantic_dedup` 元数据

5. **监控 LLM 调用**
   - 查看日志中的 LLM 调用次数
   - 评估成本是否在预期范围内
   - 必要时调整参数减少调用

## 完整示例脚本

创建 `run_dedup.sh`：

```bash
#!/bin/bash
set -e

# 配置
GRAPH_INPUT="output/graphs/demo_new.json"
CHUNKS_INPUT="output/chunks/demo.txt"
GRAPH_OUTPUT="output/graphs/demo_deduped_$(date +%Y%m%d_%H%M%S).json"

# 设置 API Key（如果使用语义去重）
export LLM_API_KEY="${LLM_API_KEY:-sk-your-key-here}"

# 运行去重
echo "Starting semantic deduplication..."
echo "Input: $GRAPH_INPUT"
echo "Output: $GRAPH_OUTPUT"

/usr/bin/python3 offline_semantic_dedup.py \
    --graph "$GRAPH_INPUT" \
    --chunks "$CHUNKS_INPUT" \
    --output "$GRAPH_OUTPUT" \
    --config config/semantic_dedup_enabled.yaml

echo "Deduplication completed!"
echo "Output saved to: $GRAPH_OUTPUT"

# 显示统计
echo ""
echo "File sizes:"
ls -lh "$GRAPH_INPUT" "$GRAPH_OUTPUT"
```

使用：
```bash
chmod +x run_dedup.sh
./run_dedup.sh
```

## 总结

`offline_semantic_dedup.py` 提供了灵活的离线去重功能：

- ✅ 支持精确去重和语义去重
- ✅ 无需重新构建图谱
- ✅ 保留完整的去重信息
- ✅ 可配置和可扩展

根据你的需求选择合适的模式和参数，即可获得高质量的去重结果。
