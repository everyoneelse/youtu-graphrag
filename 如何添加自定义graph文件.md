# 如何在Web界面上选择手动拷贝的graph.json文件

## 修改内容

已经修改了 `backend.py` 中的 `/api/datasets` 接口，使其能够自动识别 `output/graphs/` 目录下的所有graph文件。

---

## 关于检索索引的重要说明 ⚠️

### 索引会自动构建

**好消息**：你**不需要**手动为新添加的graph文件构建检索索引！

当你在Web界面的 **Q&A Interface** 标签页中：
1. 选择数据集
2. 第一次提问时，系统会**自动构建FAISS索引**

索引会被缓存到 `retriever/faiss_cache_new/{数据集名称}/` 目录，后续查询会直接使用缓存。

### 索引构建内容

系统会自动构建以下索引（基于graph文件）：
- ✅ **节点索引** (Node Index) - 基于图中的实体节点
- ✅ **关系索引** (Relation Index) - 基于实体间的关系
- ✅ **三元组索引** (Triple Index) - 基于完整的三元组
- ✅ **社区摘要索引** (Community Index) - 基于社区层级结构

### Chunks文件的影响

如果你**只有graph文件，没有chunks文件**：
- ✅ 图谱可视化：**正常工作**
- ✅ 问答功能：**基本正常**（使用节点、关系、三元组检索）
- ⚠️ 原始文本检索：**受限**（无法检索原始文档片段）

如果你**同时有graph和chunks文件**：
- ✅ 所有功能都**完全正常**
- ✅ 可以检索到原始文档片段
- ✅ 答案质量更高

---

## 使用方法

### 方案A：仅使用Graph文件（推荐用于快速测试）

适用场景：你只有构建好的graph文件，没有原始语料

**步骤**：
1. 将graph文件重命名为 `{数据集名称}_new.json`
2. 拷贝到 `output/graphs/` 目录
3. 在Web界面选择该数据集即可使用

**限制**：无法检索原始文档片段

### 方案B：同时准备Graph和Chunks文件（推荐用于生产环境）

适用场景：你有完整的构建输出，包括graph和chunks

**步骤**：
1. 准备文件：
   ```
   output/graphs/{数据集名称}_new.json       # graph文件
   output/chunks/{数据集名称}.txt            # chunks文件
   ```

2. Chunks文件格式示例：
   ```
   id: chunk_0	Chunk: 这是第一个文档片段的内容...
   id: chunk_1	Chunk: 这是第二个文档片段的内容...
   id: chunk_2	Chunk: 这是第三个文档片段的内容...
   ```

3. 在Web界面选择该数据集即可使用

**优势**：功能完整，检索质量最佳

### 方案C：完整的数据集（支持重新构建）

适用场景：你想支持重新构建图谱的功能

**步骤**：
1. 创建目录结构：
   ```
   data/uploaded/{数据集名称}/
   ├── corpus.json                        # 原始语料
   output/graphs/{数据集名称}_new.json     # graph文件
   output/chunks/{数据集名称}.txt          # chunks文件（可选）
   ```

2. `corpus.json` 格式：
   ```json
   [
     {
       "title": "文档1标题",
       "text": "文档1内容..."
     },
     {
       "title": "文档2标题",
       "text": "文档2内容..."
     }
   ]
   ```

**优势**：支持所有功能，包括重新构建图谱

---

## 文件命名规则

### Graph文件
```
{数据集名称}_new.json
```

例如：
- `my_custom_graph_new.json` → 数据集名称：`my_custom_graph`
- `project_alpha_new.json` → 数据集名称：`project_alpha`

### Chunks文件（可选）
```
{数据集名称}.txt
```

例如：
- `my_custom_graph.txt`
- `project_alpha.txt`

⚠️ **注意**：数据集名称必须一致！

---

## 在Web界面中使用

1. **启动服务**：
   ```bash
   python3 backend.py
   ```

2. **访问界面**：
   ```
   http://localhost:8000
   ```

3. **Graph Visualization** 标签页：
   - 下拉框会显示你的自定义数据集
   - 选择后查看图谱可视化

4. **Q&A Interface** 标签页：
   - 选择数据集
   - 第一次提问时会自动构建索引（约需10-30秒）
   - 后续查询使用缓存，速度很快

---

## 数据集类型标识

在 **Data Upload** 标签页的 "Available Datasets" 列表中：

| 类型 | 说明 | 功能支持 |
|------|------|----------|
| `demo` | 示例数据集 | ✅ 可视化、✅ 问答、✅ 重构 |
| `uploaded` | Web上传的数据集 | ✅ 可视化、✅ 问答、✅ 重构、🗑️ 删除 |
| `custom` | 手动拷贝的graph | ✅ 可视化、✅ 问答 |

---

## 完整示例

### 示例1：只有graph文件

```bash
# 你有一个graph文件
ls my_data_graph.json

# 重命名并拷贝
cp my_data_graph.json output/graphs/my_data_new.json

# Web界面会显示 "my_data" 数据集
# 可以进行可视化和问答（基础功能）
```

### 示例2：有graph和chunks文件

```bash
# 你有两个文件
ls my_data_graph.json my_data_chunks.txt

# 拷贝到对应位置
cp my_data_graph.json output/graphs/my_data_new.json
cp my_data_chunks.txt output/chunks/my_data.txt

# Web界面会显示 "my_data" 数据集
# 可以进行可视化和问答（完整功能）
```

### 示例3：完整数据集

```bash
# 创建目录
mkdir -p data/uploaded/my_data

# 准备corpus.json
cat > data/uploaded/my_data/corpus.json << 'EOF'
[
  {
    "title": "文档1",
    "text": "这是第一个文档的内容..."
  }
]
EOF

# 拷贝graph和chunks
cp my_data_graph.json output/graphs/my_data_new.json
cp my_data_chunks.txt output/chunks/my_data.txt

# Web界面会显示 "my_data" 数据集
# 支持所有功能：可视化、问答、重构、删除
```

---

## 常见问题

### Q1: 索引构建需要多久？
**A**: 取决于图的大小：
- 小型图（<1000节点）：10-20秒
- 中型图（1000-10000节点）：20-60秒  
- 大型图（>10000节点）：1-3分钟

索引只需构建一次，之后会使用缓存。

### Q2: 如何重新构建索引？
**A**: 删除缓存目录即可：
```bash
rm -rf retriever/faiss_cache_new/{数据集名称}
```
下次查询时会自动重建。

### Q3: 没有chunks文件会影响问答质量吗？
**A**: 会有一定影响：
- 无chunks：主要基于图结构检索（准确但可能不够详细）
- 有chunks：可以检索原始文本片段（更详细、上下文更丰富）

建议生产环境使用完整的graph + chunks。

### Q4: 如何生成chunks文件？
**A**: 如果你有原始corpus，可以通过构建流程生成：
```bash
# 方法1：使用Web界面上传corpus，系统会自动生成chunks
# 方法2：使用命令行工具
python3 main.py --dataset my_data --mode build
```

### Q5: 删除数据集会删除哪些文件？
**A**: 
- 对于`custom`类型：只删除graph文件
- 对于`uploaded`类型：删除所有相关文件（corpus、graph、chunks、cache）
- 对于`demo`类型：不允许删除

---

## 技术细节

### 索引存储位置
```
retriever/faiss_cache_new/{数据集名称}/
├── node.index              # 节点FAISS索引
├── relation.index          # 关系FAISS索引
├── triple.index            # 三元组FAISS索引
├── comm.index              # 社区FAISS索引
├── node_embeddings.pt      # 节点向量
├── relation_embeddings.pt  # 关系向量
└── node_map.json           # 节点映射
```

### 自动索引构建时机
系统在以下时机自动构建索引：
1. 第一次调用 `build_indices()` 时
2. 检测到graph变化时
3. 检测到模型维度变化时
4. 缓存不一致或损坏时

缓存一致性检查包括：
- Graph节点数量和ID
- 模型向量维度
- 文件完整性
