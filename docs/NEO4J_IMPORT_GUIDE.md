# 🔗 Neo4j 导入指南 | Neo4j Import Guide

本指南说明如何将 Youtu-GraphRAG 生成的知识树导入到 Neo4j 数据库中进行可视化。

This guide explains how to import the Youtu-GraphRAG knowledge tree into Neo4j database for visualization.

---

## 📊 四层知识树结构 | Four-Level Knowledge Tree Structure

Youtu-GraphRAG 构建的知识图谱包含四个层次：

The knowledge graph built by Youtu-GraphRAG contains four levels:

| 层级 Level | 标签 Label | 说明 Description |
|-----------|-----------|-----------------|
| **Level 1** | `attribute` | 实体属性层 - 存储实体的各种属性信息 <br> Entity Attributes - Stores various properties of entities |
| **Level 2** | `entity` | 实体关系层 - 核心实体及其关系三元组 <br> Entity Relations - Core entities and relationship triples |
| **Level 3** | `keyword` | 关键词索引层 - 用于检索的关键词体系 <br> Keyword Index - Keyword system for retrieval |
| **Level 4** | `community` | 社区结构层 - 层次化的知识社区 <br> Community Structure - Hierarchical knowledge communities |

---

## 🚀 快速开始 | Quick Start

### 方法一：使用 Cypher 脚本导入 (推荐) | Method 1: Import via Cypher Script (Recommended)

#### 1. 生成导入文件 | Generate Import Files

```bash
# 在项目根目录运行 | Run in project root directory
cd /path/to/Youtu-GraphRAG

# 导出为 Neo4j 格式 | Export to Neo4j format
python3 -c "
import sys
sys.path.insert(0, '.')
from utils.neo4j_exporter import export_graph_to_neo4j
export_graph_to_neo4j('output/graphs/demo_new.json')
"
```

这将生成：
This will generate:
- `output/graphs/demo_new_neo4j.cypher` - Cypher 脚本
- `output/graphs/demo_new_neo4j_csv/` - CSV 文件（备用方法）

#### 2. 启动 Neo4j | Start Neo4j

```bash
# 使用 Docker 启动 Neo4j | Start Neo4j with Docker
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# 或使用本地安装 | Or use local installation
neo4j start
```

#### 3. 导入数据 | Import Data

**选项 A: 通过 Neo4j Browser (Web UI)**

1. 打开浏览器访问 http://localhost:7474
2. 登录 (默认用户名/密码: neo4j/neo4j)
3. 复制 `demo_new_neo4j.cypher` 文件内容
4. 粘贴到查询窗口并执行
5. 等待导入完成

**选项 B: 通过 cypher-shell 命令行**

```bash
# 使用 cypher-shell 导入 | Import using cypher-shell
cat output/graphs/demo_new_neo4j.cypher | cypher-shell -u neo4j -p password

# 或者分批导入（处理大文件）| Or batch import (for large files)
cypher-shell -u neo4j -p password -f output/graphs/demo_new_neo4j.cypher
```

#### 4. 验证导入 | Verify Import

在 Neo4j Browser 中运行以下查询：

Run these queries in Neo4j Browser:

```cypher
// 查看节点统计 | View node statistics
MATCH (n)
RETURN labels(n)[0] as NodeType, count(*) as Count
ORDER BY Count DESC;

// 查看关系统计 | View relationship statistics  
MATCH ()-[r]->()
RETURN type(r) as RelationType, count(*) as Count
ORDER BY Count DESC
LIMIT 20;

// 可视化四层结构 | Visualize four-level structure
MATCH (n)
RETURN n.level as Level, labels(n)[0] as Type, count(*) as Count
ORDER BY Level;
```

---

### 方法二：使用 CSV 批量导入 | Method 2: Bulk Import via CSV

适用于大规模数据（>10万节点）的场景。

For large-scale data (>100K nodes).

#### 1. 生成 CSV 文件 | Generate CSV Files

```bash
# 同方法一的步骤1 | Same as Method 1 Step 1
python3 -c "
import sys
sys.path.insert(0, '.')
from utils.neo4j_exporter import export_graph_to_neo4j
export_graph_to_neo4j('output/graphs/demo_new.json')
"
```

#### 2. 使用 neo4j-admin 导入 | Import with neo4j-admin

```bash
# 停止 Neo4j 服务 | Stop Neo4j service
neo4j stop

# 进入 CSV 目录 | Navigate to CSV directory
cd output/graphs/demo_new_neo4j_csv

# 执行批量导入 | Execute bulk import
neo4j-admin database import full \
  --nodes=Entity=entity_nodes.csv \
  --nodes=Attribute=attribute_nodes.csv \
  --nodes=Keyword=keyword_nodes.csv \
  --nodes=Community=community_nodes.csv \
  --relationships=relationships.csv \
  neo4j

# 启动 Neo4j | Start Neo4j
neo4j start
```

---

## 🎨 可视化示例查询 | Visualization Example Queries

### 1. 查看完整知识树 | View Complete Knowledge Tree

```cypher
// 限制显示前100个节点和关系 | Limit to first 100 nodes and relationships
MATCH (n)
WITH n LIMIT 100
OPTIONAL MATCH (n)-[r]->(m)
RETURN n, r, m;
```

### 2. 按层级查看 | View by Level

```cypher
// 查看第2层（实体层）及其关系 | View Level 2 (Entity layer) and relationships
MATCH (n:Entity)
WHERE n.level = 2
WITH n LIMIT 50
OPTIONAL MATCH (n)-[r]->(m)
RETURN n, r, m;
```

### 3. 查看特定实体的知识子图 | View Knowledge Subgraph for Specific Entity

```cypher
// 以 "FC Barcelona" 为中心的知识图 | Knowledge graph centered on "FC Barcelona"
MATCH (center:Entity {name: "FC Barcelona"})
MATCH path = (center)-[*1..2]-(connected)
RETURN path
LIMIT 100;
```

### 4. 查看社区结构 | View Community Structure

```cypher
// 查看社区节点及其成员 | View community nodes and members
MATCH (c:Community)
OPTIONAL MATCH (c)-[r:MEMBER_OF|BELONGS_TO]-(member)
RETURN c, r, member
LIMIT 50;
```

### 5. 关键词到实体的路径 | Keyword to Entity Paths

```cypher
// 从关键词追踪到相关实体 | Trace from keywords to related entities
MATCH (k:Keyword)-[r*1..2]-(e:Entity)
WHERE k.name CONTAINS "football"
RETURN k, r, e
LIMIT 50;
```

### 6. 查看属性丰富的实体 | View Entities with Rich Attributes

```cypher
// 找出拥有最多属性的实体 | Find entities with most attributes
MATCH (e:Entity)-[:HAS_ATTRIBUTE]->(a:Attribute)
WITH e, count(a) as attrCount
ORDER BY attrCount DESC
LIMIT 10
MATCH (e)-[r:HAS_ATTRIBUTE]->(a)
RETURN e, r, a;
```

---

## 🔧 高级配置 | Advanced Configuration

### 优化查询性能 | Optimize Query Performance

```cypher
// 创建索引 | Create indexes
CREATE INDEX entity_name_idx IF NOT EXISTS FOR (n:Entity) ON (n.name);
CREATE INDEX keyword_name_idx IF NOT EXISTS FOR (n:Keyword) ON (n.name);
CREATE INDEX level_idx IF NOT EXISTS FOR (n) ON (n.level);

// 创建全文索引 | Create full-text index
CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS 
FOR (n:Entity) ON EACH [n.name];
```

### 自定义节点样式 | Customize Node Styles

在 Neo4j Browser 中，点击节点标签（如 Entity）可以自定义：
- 颜色 (Color)
- 大小 (Size)  
- 显示属性 (Caption)

建议配置：
```
Entity: 蓝色, 显示 name
Attribute: 绿色, 显示 name
Keyword: 橙色, 显示 name
Community: 紫色, 显示 name
```

---

## 🐛 故障排查 | Troubleshooting

### 问题 1: 导入时内存不足 | Issue 1: Out of Memory During Import

**解决方案 | Solution:**
```bash
# 增加 Neo4j 内存配置 | Increase Neo4j memory
# 编辑 neo4j.conf | Edit neo4j.conf
dbms.memory.heap.initial_size=2G
dbms.memory.heap.max_size=4G
```

### 问题 2: 字符编码错误 | Issue 2: Character Encoding Error

**解决方案 | Solution:**
确保所有文件使用 UTF-8 编码
Ensure all files use UTF-8 encoding

```bash
# 转换文件编码 | Convert file encoding
iconv -f ISO-8859-1 -t UTF-8 input.cypher > output.cypher
```

### 问题 3: 约束冲突 | Issue 3: Constraint Violation

**解决方案 | Solution:**
```cypher
// 清空数据库重新导入 | Clear database and re-import
MATCH (n) DETACH DELETE n;
```

---

## 📚 参考资源 | References

- [Neo4j Official Documentation](https://neo4j.com/docs/)
- [Cypher Query Language](https://neo4j.com/docs/cypher-manual/current/)
- [Neo4j Browser Guide](https://neo4j.com/docs/browser-manual/current/)
- [Youtu-GraphRAG Paper](../Youtu-GraphRAG.pdf)

---

## 🤝 贡献 | Contributing

欢迎提交 Issue 和 Pull Request 改进导入工具！

Welcome to submit Issues and Pull Requests to improve the import tool!

---

**生成时间 | Generated:** 2025-10-11
**版本 | Version:** 1.0
