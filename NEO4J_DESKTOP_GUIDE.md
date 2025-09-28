# 🖥️ Neo4j Desktop 安装和使用指南

如果您不想使用命令行，可以使用 Neo4j Desktop 的图形界面。

## 📥 下载和安装

1. **访问 Neo4j 官网**
   - 前往：https://neo4j.com/download/
   - 点击 "Download Neo4j Desktop"

2. **注册账户**（免费）
   - 填写邮箱和基本信息
   - 获取激活密钥

3. **安装 Neo4j Desktop**
   - 下载适合您操作系统的安装包
   - 运行安装程序

## 🚀 创建数据库

1. **启动 Neo4j Desktop**
   - 输入激活密钥

2. **创建新项目**
   - 点击 "New Project"
   - 命名为 "Youtu-GraphRAG"

3. **添加数据库**
   - 点击 "Add Database"
   - 选择 "Local DBMS"
   - 名称：youtu-graphrag-db
   - 密码：graphrag123
   - 版本：选择最新的 Community 版本

4. **启动数据库**
   - 点击数据库旁边的 "Start" 按钮
   - 等待状态变为 "Running"

## 📊 导入数据

1. **打开 Neo4j Browser**
   - 点击 "Open" 按钮
   - 或访问：http://localhost:7474

2. **连接数据库**
   - 用户名：neo4j
   - 密码：graphrag123

3. **导入知识图谱**
   - 复制 `demo_neo4j_import.cypher` 文件内容
   - 粘贴到 Neo4j Browser 的查询框
   - 点击运行按钮

## 🎨 可视化查询

```cypher
// 查看所有节点类型
CALL db.labels() YIELD label
RETURN label, count(*) as count
ORDER BY count DESC;

// 可视化实体关系
MATCH (e:Entity)-[r]-(connected)
RETURN e, r, connected
LIMIT 50;

// 探索特定实体
MATCH (e:Entity {name: "FC Barcelona"})-[r]-(connected)
RETURN e, r, connected;
```

## 🔧 配置优化

在 Neo4j Desktop 中：

1. **设置 -> Settings**
2. **编辑配置文件**
3. **添加内存配置**：
```
dbms.memory.heap.initial_size=1G
dbms.memory.heap.max_size=2G
dbms.memory.pagecache.size=1G
```

## 💡 优势

- ✅ 图形界面，易于使用
- ✅ 内置可视化工具
- ✅ 自动管理数据库
- ✅ 支持插件扩展
- ✅ 无需命令行操作