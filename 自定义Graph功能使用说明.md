# 自定义Graph功能使用说明

## 🎯 功能概述

现在你可以将**手动拷贝的graph.json文件**直接添加到Web界面中使用，无需通过Web界面上传语料和重新构建。

---

## ✅ 修改内容

### 修改了 `backend.py`

- **位置**: `/api/datasets` 接口（第832-865行）
- **功能**: 自动扫描 `output/graphs/` 目录，识别所有 `*_new.json` 文件
- **效果**: 手动拷贝的graph文件会自动显示在Web界面的数据集列表中

---

## 🚀 快速开始（3步）

### 1. 拷贝graph文件

```bash
# 将你的graph文件重命名并拷贝到指定位置
cp your_graph.json output/graphs/my_dataset_new.json
```

**命名规则**: `{数据集名称}_new.json`

### 2. 启动服务

```bash
python3 backend.py
```

### 3. 使用Web界面

访问 `http://localhost:8000`，在数据集下拉框中选择 `my_dataset`

---

## ⚙️ 关于检索索引

### ✅ 不需要手动构建索引！

- 第一次问答时，系统会**自动构建FAISS索引**
- 索引会缓存到 `retriever/faiss_cache_new/{数据集名称}/`
- 后续查询直接使用缓存，速度很快

### 索引构建时间

- 小型图（<1K节点）：10-20秒
- 中型图（1K-10K节点）：20-60秒
- 大型图（>10K节点）：1-3分钟

---

## 📊 配置方案

### 方案A：仅Graph文件（最简单）

```bash
output/graphs/my_dataset_new.json   # 必需
```

**功能**:
- ✅ 图谱可视化
- ✅ 基础问答
- ❌ 无法检索原始文档片段

**适用**: 快速测试

### 方案B：Graph + Chunks（推荐）

```bash
output/graphs/my_dataset_new.json   # Graph文件
output/chunks/my_dataset.txt        # Chunks文件
```

**Chunks格式**:
```
id: chunk_0	Chunk: 第一个文档片段的内容...
id: chunk_1	Chunk: 第二个文档片段的内容...
```

**功能**:
- ✅ 图谱可视化
- ✅ 基础问答
- ✅ 完整问答（可检索原文片段）

**适用**: 生产环境

### 方案C：完整配置（最强大）

```bash
data/uploaded/my_dataset/corpus.json   # 原始语料
output/graphs/my_dataset_new.json      # Graph文件
output/chunks/my_dataset.txt           # Chunks文件
```

**Corpus格式**:
```json
[
  {"title": "文档1", "text": "内容..."},
  {"title": "文档2", "text": "内容..."}
]
```

**功能**: 支持所有功能（包括重新构建图谱）

---

## 🛠️ 检查工具

### 列出所有数据集

```bash
python3 check_dataset.py --list
```

### 检查特定数据集

```bash
python3 check_dataset.py my_dataset
```

**输出内容**:
- ✅ 文件存在性检查
- 📊 文件大小和统计
- 🔧 功能支持情况
- 💡 配置建议

---

## 📖 完整文档

| 文档 | 说明 |
|------|------|
| [CUSTOM_GRAPH_QUICK_START.md](./CUSTOM_GRAPH_QUICK_START.md) | 快速上手指南 |
| [如何添加自定义graph文件.md](./如何添加自定义graph文件.md) | 详细使用说明 |
| [CUSTOM_GRAPH_SUMMARY.md](./CUSTOM_GRAPH_SUMMARY.md) | 技术总结文档 |

---

## 🎯 实战示例

### 示例1：添加单个Graph

```bash
# 拷贝文件
cp knowledge_graph.json output/graphs/knowledge_new.json

# 检查配置
python3 check_dataset.py knowledge

# 启动服务
python3 backend.py

# 访问 http://localhost:8000 使用
```

### 示例2：添加Graph + Chunks

```bash
# 拷贝文件
cp my_graph.json output/graphs/mydata_new.json
cp my_chunks.txt output/chunks/mydata.txt

# 检查配置
python3 check_dataset.py mydata

# 启动服务
python3 backend.py
```

---

## ❓ 常见问题

### Q: 是否需要手动构建索引？

**A**: 不需要！第一次问答时会自动构建。

### Q: Chunks文件必须吗？

**A**: 不是必须，但强烈推荐：
- 无Chunks：基础问答功能
- 有Chunks：完整问答功能（含原文检索）

### Q: 如何重新构建索引？

**A**: 删除缓存目录：
```bash
rm -rf retriever/faiss_cache_new/my_dataset
```
下次查询时会自动重建。

### Q: 支持多个数据集吗？

**A**: 支持！每个数据集独立管理。

---

## 📝 新增文件列表

| 文件 | 大小 | 说明 |
|------|------|------|
| `check_dataset.py` | 9.7K | 数据集检查工具 |
| `CUSTOM_GRAPH_QUICK_START.md` | 5.8K | 快速上手指南 |
| `CUSTOM_GRAPH_SUMMARY.md` | 9.8K | 技术总结文档 |
| `如何添加自定义graph文件.md` | 7.3K | 详细使用说明 |
| `自定义Graph功能使用说明.md` | 本文件 | 简明使用指南 |

---

## 🎉 总结

✅ **已完成**:
1. 修改 `backend.py` 支持自动识别自定义graph文件
2. 创建数据集检查工具 `check_dataset.py`
3. 编写完整的使用文档

✅ **你现在可以**:
- 直接拷贝graph文件到系统使用
- 无需手动构建索引（自动完成）
- 使用检查工具验证配置
- 参考文档快速上手

---

**开始使用**: 参考 [快速上手指南](./CUSTOM_GRAPH_QUICK_START.md)

**更新时间**: 2025-10-21
