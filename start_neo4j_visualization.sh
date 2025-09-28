#!/bin/bash

# Youtu-GraphRAG Neo4j 可视化快速启动脚本
# Quick start script for Youtu-GraphRAG Neo4j visualization

set -e

echo "🚀 启动 Youtu-GraphRAG Neo4j 可视化环境..."
echo "🚀 Starting Youtu-GraphRAG Neo4j visualization environment..."

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ 错误：未找到 Docker。请先安装 Docker。"
    echo "❌ Error: Docker not found. Please install Docker first."
    exit 1
fi

# 检查 Docker Compose 是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "❌ 错误：未找到 Docker Compose。请先安装 Docker Compose。"
    echo "❌ Error: Docker Compose not found. Please install Docker Compose first."
    exit 1
fi

# 启动 Neo4j 容器
echo "🐳 启动 Neo4j 数据库容器..."
echo "🐳 Starting Neo4j database container..."
docker-compose -f docker-compose.neo4j.yml up -d

# 等待 Neo4j 启动
echo "⏳ 等待 Neo4j 启动完成..."
echo "⏳ Waiting for Neo4j to start..."
sleep 20

# 检查 Neo4j 是否启动成功
echo "🔍 检查 Neo4j 状态..."
echo "🔍 Checking Neo4j status..."
if docker-compose -f docker-compose.neo4j.yml ps | grep -q "Up"; then
    echo "✅ Neo4j 启动成功！"
    echo "✅ Neo4j started successfully!"
else
    echo "❌ Neo4j 启动失败，请检查日志："
    echo "❌ Neo4j failed to start, please check logs:"
    docker-compose -f docker-compose.neo4j.yml logs
    exit 1
fi

# 检查是否存在演示数据
DEMO_GRAPH="output/graphs/demo_new.json"
if [ -f "$DEMO_GRAPH" ]; then
    echo "📊 发现演示数据，准备导入..."
    echo "📊 Demo data found, preparing to import..."
    
    # 生成 Cypher 导入文件
    echo "🔄 生成 Cypher 导入文件..."
    echo "🔄 Generating Cypher import file..."
    python3 neo4j_importer.py --input "$DEMO_GRAPH" --output demo_neo4j_import.cypher
    
    echo "📝 Cypher 文件已生成：demo_neo4j_import.cypher"
    echo "📝 Cypher file generated: demo_neo4j_import.cypher"
else
    echo "⚠️  未找到演示数据文件：$DEMO_GRAPH"
    echo "⚠️  Demo data file not found: $DEMO_GRAPH"
    echo "请先运行 Youtu-GraphRAG 生成知识图谱，或使用自己的数据。"
    echo "Please run Youtu-GraphRAG to generate knowledge graph first, or use your own data."
fi

echo ""
echo "🎉 Neo4j 可视化环境已就绪！"
echo "🎉 Neo4j visualization environment is ready!"
echo ""
echo "📋 访问信息 / Access Information:"
echo "   🌐 Neo4j Browser: http://localhost:7474"
echo "   👤 用户名 / Username: neo4j"
echo "   🔑 密码 / Password: graphrag123"
echo ""
echo "📋 导入数据 / Import Data:"
if [ -f "demo_neo4j_import.cypher" ]; then
    echo "   1. 在 Neo4j Browser 中复制粘贴 demo_neo4j_import.cypher 的内容"
    echo "   1. Copy and paste content from demo_neo4j_import.cypher in Neo4j Browser"
    echo "   2. 或使用命令行："
    echo "   2. Or use command line:"
    echo "      docker exec -i youtu-graphrag-neo4j cypher-shell -u neo4j -p graphrag123 < demo_neo4j_import.cypher"
fi
echo ""
echo "📋 其他图谱导入 / Import Other Graphs:"
echo "   python3 neo4j_importer.py --input output/graphs/your_graph.json --output your_graph.cypher"
echo ""
echo "📋 停止服务 / Stop Services:"
echo "   docker-compose -f docker-compose.neo4j.yml down"
echo ""
echo "📖 详细指南 / Detailed Guide:"
echo "   请查看 NEO4J_GUIDE.md 文件"
echo "   Please check NEO4J_GUIDE.md file"