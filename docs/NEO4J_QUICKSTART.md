# 🚀 Neo4j 快速开始 | Quick Start with Neo4j

只需 **3 个命令**，即可在 Neo4j 中可视化您的知识图谱！

Visualize your knowledge graph in Neo4j with just **3 commands**!

---

## ⚡ 最快方式 | Fastest Way

```bash
# 1️⃣ 导出知识图谱到 Neo4j 格式 | Export knowledge graph to Neo4j format
python3 export_to_neo4j.py output/graphs/demo_new.json

# 2️⃣ 启动 Neo4j (Docker) | Start Neo4j (Docker)
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# 3️⃣ 导入数据 | Import data
cat output/graphs/demo_new_neo4j.cypher | \
  docker exec -i neo4j cypher-shell -u neo4j -p password
```

访问 http://localhost:7474 查看可视化结果！

Visit http://localhost:7474 to see the visualization!

---

## 📊 四层知识树可视化 | Four-Level Knowledge Tree Visualization

导入后，您可以在 Neo4j Browser 中运行以下查询来探索知识树：

After import, run these queries in Neo4j Browser to explore the knowledge tree:

### 1️⃣ 查看整体结构 | View Overall Structure

```cypher
// 统计各层节点数量 | Count nodes by level
MATCH (n)
RETURN n.level as Level, 
       labels(n)[0] as Type, 
       count(*) as Count
ORDER BY Level;
```

**预期输出 | Expected Output:**
```
Level | Type      | Count
------|-----------|-------
1     | Attribute | 46
2     | Entity    | 45
3     | Keyword   | 31
4     | Community | 8
```

### 2️⃣ 可视化实体关系 | Visualize Entity Relationships

```cypher
// 显示所有实体及其关系 | Show all entities and relationships
MATCH (e:Entity)
WHERE e.level = 2
WITH e LIMIT 20
OPTIONAL MATCH (e)-[r]->(related)
RETURN e, r, related;
```

### 3️⃣ 查看特定实体的知识子图 | View Knowledge Subgraph

```cypher
// 以 "Messi" 为中心展开 | Expand from "Messi"
MATCH (center:Entity)
WHERE center.name CONTAINS "Messi"
MATCH path = (center)-[*1..2]-(connected)
RETURN path
LIMIT 50;
```

### 4️⃣ 社区层次结构 | Community Hierarchy

```cypher
// 查看社区及其成员 | View communities and members
MATCH (c:Community)
OPTIONAL MATCH (c)-[r]-(member)
RETURN c, r, member
LIMIT 30;
```

### 5️⃣ 知识推理路径 | Knowledge Reasoning Paths

```cypher
// 查找两个实体之间的路径 | Find paths between entities
MATCH (start:Entity {name: "Messi"}),
      (end:Entity {name: "FC Barcelona"})
MATCH path = shortestPath((start)-[*..5]-(end))
RETURN path;
```

---

## 🎨 可视化配置建议 | Visualization Configuration Tips

在 Neo4j Browser 中，点击节点类型可以自定义样式：

In Neo4j Browser, click on node types to customize styles:

| 节点类型 Node Type | 建议颜色 Color | 建议大小 Size | 显示属性 Caption |
|-------------------|---------------|--------------|-----------------|
| **Entity**        | 🔵 蓝色 Blue   | 大 Large     | `name`          |
| **Attribute**     | 🟢 绿色 Green  | 小 Small     | `name`          |
| **Keyword**       | 🟠 橙色 Orange | 中 Medium    | `name`          |
| **Community**     | 🟣 紫色 Purple | 大 Large     | `name`          |

### 关系样式配置 | Relationship Style Configuration

```cypher
// 查看所有关系类型 | View all relationship types
MATCH ()-[r]->()
RETURN DISTINCT type(r) as RelationType, count(*) as Count
ORDER BY Count DESC;
```

---

## 🔍 高级查询示例 | Advanced Query Examples

### 查找最重要的节点 | Find Most Important Nodes

```cypher
// 按连接数排序 | Sort by connection count
MATCH (n)
WITH n, size((n)--()) as connections
WHERE connections > 5
RETURN labels(n)[0] as Type, 
       n.name as Name, 
       connections
ORDER BY connections DESC
LIMIT 10;
```

### 分析社区分布 | Analyze Community Distribution

```cypher
// 社区成员统计 | Community member statistics
MATCH (c:Community)
OPTIONAL MATCH (c)-[]-(member)
WITH c, count(DISTINCT member) as memberCount
RETURN c.name as Community, 
       memberCount
ORDER BY memberCount DESC;
```

### 关键词网络 | Keyword Network

```cypher
// 展示关键词如何连接实体 | Show how keywords connect entities
MATCH (k:Keyword)-[]-(e:Entity)
WITH k, collect(DISTINCT e.name) as entities
WHERE size(entities) > 2
RETURN k.name as Keyword, 
       entities,
       size(entities) as EntityCount
ORDER BY EntityCount DESC
LIMIT 10;
```

---

## 💡 使用技巧 | Tips & Tricks

### 1. 性能优化 | Performance Optimization

```cypher
// 创建索引加速查询 | Create indexes for faster queries
CREATE INDEX entity_name IF NOT EXISTS FOR (n:Entity) ON (n.name);
CREATE INDEX level_idx IF NOT EXISTS FOR (n) ON (n.level);
```

### 2. 数据清理 | Data Cleanup

```cypher
// 删除所有数据（重新导入前） | Delete all data (before re-import)
MATCH (n) DETACH DELETE n;
```

### 3. 导出查询结果 | Export Query Results

在 Neo4j Browser 中：
1. 运行查询
2. 点击右上角的下载图标
3. 选择 CSV、JSON 或 PNG 格式

---

## 📚 更多资源 | More Resources

- 📖 **完整导入指南**: [docs/NEO4J_IMPORT_GUIDE.md](NEO4J_IMPORT_GUIDE.md)
- 🔗 **Neo4j 官方文档**: https://neo4j.com/docs/
- 🎓 **Cypher 查询语言**: https://neo4j.com/docs/cypher-manual/
- 📄 **Youtu-GraphRAG 论文**: ../Youtu-GraphRAG.pdf

---

## ❓ 常见问题 | FAQ

**Q: 导入需要多长时间？**
A: 对于 demo 数据集（130个节点，239个关系），通常需要 5-10 秒。

**Q: 可以导入多个数据集吗？**
A: 可以！使用 `python3 export_to_neo4j.py` 会导出所有数据集。

**Q: Neo4j 占用多少内存？**
A: Demo 数据集约占用 200MB。建议分配至少 2GB 给 Neo4j。

**Q: 支持哪些 Neo4j 版本？**
A: 支持 Neo4j 4.x 和 5.x 版本。

---

**开始探索您的知识图谱吧！🚀**

**Start exploring your knowledge graph! 🚀**
