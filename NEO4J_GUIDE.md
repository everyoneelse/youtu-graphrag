# 🌐 Youtu-GraphRAG Neo4j 可视化指南

本指南将帮助您将 Youtu-GraphRAG 生成的知识图谱导入到 Neo4j 中进行可视化和查询。

## 📋 目录
- [快速开始](#快速开始)
- [环境准备](#环境准备)
- [导入知识图谱](#导入知识图谱)
- [Neo4j 查询示例](#neo4j-查询示例)
- [可视化技巧](#可视化技巧)
- [故障排除](#故障排除)

---

## 🚀 快速开始

### 方法一：使用 Docker Compose（推荐）

1. **启动 Neo4j 数据库**
```bash
# 启动 Neo4j 容器
docker-compose -f docker-compose.neo4j.yml up -d

# 查看启动状态
docker-compose -f docker-compose.neo4j.yml ps
```

2. **访问 Neo4j Browser**
- 打开浏览器访问：http://localhost:7474
- 用户名：`neo4j`
- 密码：`graphrag123`

3. **导入知识图谱**
```bash
# 安装 neo4j 驱动（如需直接导入）
pip install neo4j

# 导出为 Cypher 文件
python neo4j_importer.py --input output/graphs/demo_new.json --output demo_neo4j.cypher

# 或直接导入到数据库
python neo4j_importer.py --input output/graphs/demo_new.json --neo4j-uri bolt://localhost:7687 --username neo4j --password graphrag123
```

### 方法二：使用本地 Neo4j 安装

1. **下载并安装 Neo4j Desktop**
   - 访问：https://neo4j.com/download/
   - 创建新数据库，设置密码

2. **导入数据**
```bash
python neo4j_importer.py --input output/graphs/demo_new.json --neo4j-uri bolt://localhost:7687 --username neo4j --password your_password
```

---

## 🛠️ 环境准备

### 系统要求
- Docker & Docker Compose（推荐方式）
- 或 Java 11+ （本地安装）
- Python 3.8+
- 至少 4GB 内存

### 安装依赖
```bash
# 安装 Neo4j Python 驱动
pip install neo4j

# 或添加到项目依赖中
echo "neo4j>=5.0.0" >> requirements.txt
pip install -r requirements.txt
```

---

## 📊 导入知识图谱

### 使用导入脚本

我们提供了 `neo4j_importer.py` 脚本来处理知识图谱的导入：

```bash
# 查看图谱统计信息
python neo4j_importer.py --input output/graphs/demo_new.json --stats

# 导出为 Cypher 文件（推荐用于大型图谱）
python neo4j_importer.py --input output/graphs/demo_new.json --output demo_import.cypher

# 直接导入到 Neo4j 数据库
python neo4j_importer.py \
    --input output/graphs/demo_new.json \
    --neo4j-uri bolt://localhost:7687 \
    --username neo4j \
    --password graphrag123
```

### 手动导入 Cypher 文件

如果您选择导出 Cypher 文件，可以通过以下方式导入：

**方式1：Neo4j Browser**
1. 打开 Neo4j Browser (http://localhost:7474)
2. 将生成的 Cypher 文件内容复制粘贴到查询框
3. 执行查询

**方式2：cypher-shell 命令行**
```bash
# 进入 Neo4j 容器
docker exec -it youtu-graphrag-neo4j cypher-shell -u neo4j -p graphrag123

# 或使用文件导入
docker exec -i youtu-graphrag-neo4j cypher-shell -u neo4j -p graphrag123 < demo_import.cypher
```

---

## 🔍 Neo4j 查询示例

导入知识图谱后，您可以使用以下 Cypher 查询来探索数据：

### 基础查询

```cypher
// 查看所有节点标签和数量
CALL db.labels() YIELD label
CALL apoc.cypher.run('MATCH (:`'+label+'`) RETURN count(*) as count', {}) YIELD value
RETURN label, value.count as count
ORDER BY count DESC;

// 查看所有关系类型和数量
CALL db.relationshipTypes() YIELD relationshipType
CALL apoc.cypher.run('MATCH ()-[:`'+relationshipType+'`]->() RETURN count(*) as count', {}) YIELD value
RETURN relationshipType, value.count as count
ORDER BY count DESC;

// 查看图谱的四层结构
MATCH (n)
RETURN DISTINCT labels(n) as NodeType, count(n) as Count
ORDER BY Count DESC;
```

### 实体探索

```cypher
// 查找特定实体
MATCH (e:Entity {name: "FC Barcelona"})
RETURN e;

// 查找实体的所有关系
MATCH (e:Entity {name: "FC Barcelona"})-[r]-(connected)
RETURN e, r, connected
LIMIT 50;

// 查找实体的属性
MATCH (e:Entity)-[:HAS_ATTRIBUTE]->(a:Attribute)
WHERE e.name CONTAINS "Barcelona"
RETURN e.name as Entity, a.name as Attribute;
```

### 路径查询

```cypher
// 查找两个实体之间的路径
MATCH path = (start:Entity {name: "Lionel Messi"})-[*1..3]-(end:Entity {name: "FC Barcelona"})
RETURN path
LIMIT 10;

// 查找多跳关系
MATCH (person:Entity)-[:PLAYS_FOR]->(club:Entity)-[:PARTICIPATES_IN]->(competition:Entity)
WHERE person.schema_type = "person"
RETURN person.name as Player, club.name as Club, competition.name as Competition
LIMIT 20;
```

### 社区分析

```cypher
// 查看社区结构
MATCH (c:Community)
RETURN c.name as Community, c.level as Level
ORDER BY c.level, c.name;

// 查看社区包含的实体
MATCH (c:Community)-[:CONTAINS]->(e:Entity)
RETURN c.name as Community, collect(e.name) as Entities
LIMIT 10;
```

### 关键词搜索

```cypher
// 通过关键词查找相关内容
MATCH (k:Keyword)-[:RELATES_TO]->(e:Entity)
WHERE k.name CONTAINS "football"
RETURN k.name as Keyword, collect(e.name) as RelatedEntities;
```

---

## 🎨 可视化技巧

### Neo4j Browser 可视化设置

1. **节点样式设置**
```cypher
// 为不同类型的节点设置不同颜色
:style Entity {
  color: #FF6B6B;
  border-color: #FF6B6B;
  text-color-internal: #FFFFFF;
  caption: '{name}';
}

:style Attribute {
  color: #4ECDC4;
  border-color: #4ECDC4;
  text-color-internal: #FFFFFF;
  caption: '{name}';
}

:style Community {
  color: #45B7D1;
  border-color: #45B7D1;
  text-color-internal: #FFFFFF;
  caption: '{name}';
}

:style Keyword {
  color: #96CEB4;
  border-color: #96CEB4;
  text-color-internal: #FFFFFF;
  caption: '{name}';
}
```

2. **关系样式设置**
```cypher
:style relationship {
  shaft-width: 3px;
  font-size: 12px;
  padding: 3px;
  text-color-external: #000000;
  text-color-internal: #FFFFFF;
  caption: '{type}';
}
```

### 推荐的可视化查询

```cypher
// 显示核心实体及其直接关系（适合概览）
MATCH (e:Entity)-[r]-(connected)
WHERE e.name IN ["FC Barcelona", "Lionel Messi", "Copa del Rey"]
RETURN e, r, connected
LIMIT 100;

// 显示社区结构（适合理解知识组织）
MATCH (c:Community)-[:CONTAINS]->(e:Entity)-[r:HAS_ATTRIBUTE]->(a:Attribute)
RETURN c, e, r, a
LIMIT 50;

// 显示推理路径（适合理解问答过程）
MATCH path = (start:Entity)-[*2..4]-(end:Entity)
WHERE start.name CONTAINS "Messi" AND end.name CONTAINS "Barcelona"
RETURN path
LIMIT 5;
```

---

## 🔧 故障排除

### 常见问题

**1. 连接失败**
```bash
# 检查 Neo4j 容器状态
docker ps | grep neo4j

# 查看容器日志
docker logs youtu-graphrag-neo4j

# 重启容器
docker-compose -f docker-compose.neo4j.yml restart
```

**2. 内存不足**
```yaml
# 修改 docker-compose.neo4j.yml 中的内存设置
environment:
  - NEO4J_dbms_memory_heap_max__size=4G  # 增加堆内存
  - NEO4J_dbms_memory_pagecache_size=2G  # 增加页缓存
```

**3. 导入速度慢**
```bash
# 对于大型图谱，建议分批导入
python neo4j_importer.py --input large_graph.json --output large_graph.cypher
# 然后手动分段执行 Cypher 文件
```

**4. 中文字符显示问题**
```cypher
// 确保数据库使用 UTF-8 编码
CALL db.info() YIELD name, value
WHERE name = "dbms.default_database"
RETURN name, value;
```

### 性能优化

**1. 创建索引**
```cypher
// 为常用查询字段创建索引
CREATE INDEX entity_name_index IF NOT EXISTS FOR (e:Entity) ON (e.name);
CREATE INDEX attribute_name_index IF NOT EXISTS FOR (a:Attribute) ON (a.name);
CREATE INDEX community_level_index IF NOT EXISTS FOR (c:Community) ON (c.level);
```

**2. 查询优化**
```cypher
// 使用 EXPLAIN 查看查询计划
EXPLAIN MATCH (e:Entity {name: "FC Barcelona"})-[r]-(connected)
RETURN e, r, connected;

// 使用 PROFILE 查看查询性能
PROFILE MATCH (e:Entity {name: "FC Barcelona"})-[r]-(connected)
RETURN e, r, connected;
```

---

## 📚 进阶使用

### 图算法应用

如果安装了 Graph Data Science (GDS) 插件，可以使用高级图算法：

```cypher
// 计算节点重要性（PageRank）
CALL gds.pageRank.stream('myGraph')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name AS name, score
ORDER BY score DESC
LIMIT 20;

// 社区检测
CALL gds.louvain.stream('myGraph')
YIELD nodeId, communityId
RETURN gds.util.asNode(nodeId).name AS name, communityId
ORDER BY communityId;
```

### 数据导出

```cypher
// 导出特定子图
MATCH (e:Entity)-[r]-(connected)
WHERE e.name = "FC Barcelona"
WITH collect(e) + collect(connected) AS nodes, collect(r) AS relationships
CALL apoc.export.json.data(nodes, relationships, "barcelona_subgraph.json", {})
YIELD file, source, format, nodes, relationships, properties, time
RETURN file, source, format, nodes, relationships, properties, time;
```

---

## 🎯 总结

通过本指南，您现在可以：

1. ✅ 使用 Docker 快速启动 Neo4j 数据库
2. ✅ 将 Youtu-GraphRAG 的知识图谱导入到 Neo4j
3. ✅ 使用 Cypher 查询语言探索知识图谱
4. ✅ 通过 Neo4j Browser 进行可视化
5. ✅ 解决常见的导入和使用问题

**下一步建议：**
- 尝试导入您自己的数据集
- 探索更复杂的 Cypher 查询
- 学习图算法在知识图谱中的应用
- 集成到您的应用程序中

如有问题，请参考 [Neo4j 官方文档](https://neo4j.com/docs/) 或在项目中提出 Issue。