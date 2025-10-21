# 如何在Web界面上选择手动拷贝的graph.json文件

## 修改内容

已经修改了 `backend.py` 中的 `/api/datasets` 接口，使其能够自动识别 `output/graphs/` 目录下的所有graph文件。

## 使用方法

### 1. 准备你的graph.json文件

将你构建好的graph.json文件拷贝到 `output/graphs/` 目录下。

### 2. 文件命名规则

文件必须按照以下格式命名：
```
{数据集名称}_new.json
```

例如：
- `my_custom_graph_new.json` - 数据集名称为 `my_custom_graph`
- `project_alpha_new.json` - 数据集名称为 `project_alpha`
- `test_data_new.json` - 数据集名称为 `test_data`

### 3. 在Web界面中查看

1. 启动后端服务：`python backend.py`
2. 打开浏览器访问：`http://localhost:8000`
3. 在 **Graph Visualization** 标签页中，下拉框里会显示你的自定义数据集
4. 选择数据集后即可查看图谱可视化
5. 在 **Q&A Interface** 标签页中，也可以选择该数据集进行问答

### 4. 数据集类型标识

在 **Data Upload** 标签页的 "Available Datasets" 列表中：
- `demo` - 示例数据集
- `uploaded` - 通过Web界面上传的数据集
- `custom` - 手动拷贝的graph文件（新增类型）

## 示例

假设你有一个名为 `my_knowledge_graph.json` 的文件：

1. 将文件重命名为：`my_knowledge_new.json`
2. 拷贝到：`output/graphs/my_knowledge_new.json`
3. 刷新Web界面，在数据集下拉框中就能看到 `my_knowledge` 这个选项
4. 选择后即可使用

## 注意事项

1. **文件格式**：确保你的graph.json文件格式正确，应该是GraphRAG生成的标准格式
2. **文件命名**：必须以 `_new.json` 结尾
3. **仅用于可视化和问答**：这些自定义数据集可以用于图谱可视化和问答，但不能重新构建（因为没有原始corpus）
4. **删除操作**：在Web界面删除这类数据集时，会删除对应的graph文件，请谨慎操作

## 完整的数据集添加（可选）

如果你想让数据集支持重新构建功能，需要额外提供corpus文件：

1. 在 `data/uploaded/` 下创建目录：`data/uploaded/{数据集名称}/`
2. 在该目录下创建 `corpus.json` 文件，格式如下：
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
3. 将graph文件放到：`output/graphs/{数据集名称}_new.json`

这样数据集就完整了，可以支持重新构建、删除等全部功能。
