# 自定义Graph快速上手指南

## 📝 简介

本指南帮助你快速将已构建好的graph.json文件添加到Youtu-GraphRAG Web界面中使用。

---

## 🚀 快速开始（3步）

### 1️⃣ 准备文件

将你的graph文件重命名并拷贝到指定位置：

```bash
# 假设你的graph文件叫 my_graph.json
# 重命名为: {数据集名称}_new.json
cp my_graph.json output/graphs/my_dataset_new.json
```

### 2️⃣ 启动服务

```bash
python3 backend.py
```

### 3️⃣ 使用Web界面

浏览器访问 `http://localhost:8000`，在数据集下拉框中选择 `my_dataset`

---

## ✅ 检索索引会自动构建

**不需要手动构建！** 

- ✅ 第一次问答时自动构建FAISS索引
- ✅ 索引会缓存到 `retriever/faiss_cache_new/` 目录
- ✅ 后续查询直接使用缓存，速度很快

---

## 📊 功能对比

| 文件配置 | 可视化 | 基础问答 | 完整问答 | 重新构建 |
|---------|-------|---------|---------|---------|
| 仅Graph | ✅ | ✅ | ❌ | ❌ |
| Graph + Chunks | ✅ | ✅ | ✅ | ❌ |
| Graph + Chunks + Corpus | ✅ | ✅ | ✅ | ✅ |

**推荐配置**：Graph + Chunks（平衡功能和复杂度）

---

## 📁 文件配置方案

### 方案A：仅Graph（最简单）

适合快速测试

```bash
output/graphs/my_dataset_new.json   # 必需
```

**限制**：无法检索原始文档片段

### 方案B：Graph + Chunks（推荐）

适合生产环境

```bash
output/graphs/my_dataset_new.json   # Graph文件
output/chunks/my_dataset.txt        # Chunks文件
```

**Chunks文件格式**：
```
id: chunk_0	Chunk: 这是第一个文档片段...
id: chunk_1	Chunk: 这是第二个文档片段...
```

### 方案C：完整配置（最强大）

支持所有功能

```bash
data/uploaded/my_dataset/corpus.json   # 原始语料
output/graphs/my_dataset_new.json      # Graph文件
output/chunks/my_dataset.txt           # Chunks文件
```

**Corpus文件格式**：
```json
[
  {"title": "文档1", "text": "内容..."},
  {"title": "文档2", "text": "内容..."}
]
```

---

## 🔍 检查工具

使用内置工具检查数据集配置：

```bash
# 列出所有数据集
python3 check_dataset.py --list

# 检查特定数据集
python3 check_dataset.py my_dataset
```

工具会显示：
- ✅ 文件存在性检查
- 📊 文件大小和内容统计
- 🔧 功能支持情况
- 💡 配置建议

---

## ⚙️ 常见操作

### 重新构建索引

```bash
# 删除缓存
rm -rf retriever/faiss_cache_new/my_dataset

# 下次查询时会自动重建
```

### 删除数据集

在Web界面的 **Data Upload** 标签页中点击删除按钮

或手动删除：

```bash
# 删除graph文件
rm output/graphs/my_dataset_new.json

# 删除chunks文件（如果有）
rm output/chunks/my_dataset.txt

# 删除缓存（如果有）
rm -rf retriever/faiss_cache_new/my_dataset
```

### 查看索引状态

```bash
# 检查索引文件是否存在
ls retriever/faiss_cache_new/my_dataset/

# 应该包含这些文件：
# - node.index
# - relation.index
# - triple.index
# - comm.index
# - node_embeddings.pt
# - relation_embeddings.pt
```

---

## 🎯 实战示例

### 示例1：添加单个Graph文件

```bash
# 你有一个graph文件
ls knowledge_graph.json

# 添加到系统
cp knowledge_graph.json output/graphs/knowledge_new.json

# 启动服务
python3 backend.py

# 访问 http://localhost:8000
# 选择数据集 "knowledge"
# 开始使用！
```

### 示例2：添加Graph + Chunks

```bash
# 你有两个文件
ls my_graph.json my_chunks.txt

# 拷贝到指定位置
cp my_graph.json output/graphs/mydata_new.json
cp my_chunks.txt output/chunks/mydata.txt

# 检查配置
python3 check_dataset.py mydata

# 启动服务
python3 backend.py
```

### 示例3：从demo创建测试数据集

```bash
# 复制demo文件作为测试
cp output/graphs/demo_new.json output/graphs/test_new.json
cp output/chunks/demo.txt output/chunks/test.txt

# 检查配置
python3 check_dataset.py test

# 在Web界面中选择 "test" 数据集使用
```

---

## ❓ 常见问题

### Q: 索引构建需要多久？

**A**: 取决于graph大小
- 小型（<1K节点）：10-20秒
- 中型（1K-10K节点）：20-60秒
- 大型（>10K节点）：1-3分钟

### Q: 没有Chunks文件影响大吗？

**A**: 有一定影响
- 无Chunks：基于图结构检索（准确但简洁）
- 有Chunks：可检索原文（更详细、更丰富）

建议生产环境使用完整配置。

### Q: 可以同时使用多个数据集吗？

**A**: 可以！每个数据集独立管理，互不影响。

### Q: Graph文件格式有要求吗？

**A**: 必须是GraphRAG生成的标准格式：
- 关系列表格式：`[{start_node, end_node, relation}, ...]`
- 或标准图格式：`{nodes: [...], edges: [...]}`

---

## 📚 参考文档

- 详细说明：[如何添加自定义graph文件.md](./如何添加自定义graph文件.md)
- 主README：[README-CN.md](./README-CN.md)

---

## 💡 最佳实践

1. **命名规范**：使用有意义的数据集名称
   ```bash
   ✅ project_alpha_new.json
   ✅ customer_service_kb_new.json
   ❌ graph1_new.json
   ❌ test_new.json
   ```

2. **文件备份**：原始文件保留备份
   ```bash
   # 备份原始文件
   cp my_graph.json backup/my_graph_$(date +%Y%m%d).json
   # 然后拷贝到系统
   cp my_graph.json output/graphs/my_dataset_new.json
   ```

3. **定期清理缓存**：如果graph更新
   ```bash
   rm -rf retriever/faiss_cache_new/my_dataset
   ```

4. **使用检查工具**：部署前验证配置
   ```bash
   python3 check_dataset.py my_dataset
   ```

---

## 🎉 开始使用

现在你可以：

1. ✅ 拷贝你的graph文件到 `output/graphs/`
2. ✅ 运行 `python3 check_dataset.py --list` 确认
3. ✅ 启动 `python3 backend.py`
4. ✅ 访问 `http://localhost:8000` 开始使用！

祝使用愉快！🚀
