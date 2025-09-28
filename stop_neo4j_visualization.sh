#!/bin/bash

# Youtu-GraphRAG Neo4j 可视化环境停止脚本
# Stop script for Youtu-GraphRAG Neo4j visualization environment

set -e

echo "🛑 停止 Youtu-GraphRAG Neo4j 可视化环境..."
echo "🛑 Stopping Youtu-GraphRAG Neo4j visualization environment..."

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ 错误：未找到 Docker。请确保 Docker 已安装。"
    echo "❌ Error: Docker not found. Please ensure Docker is installed."
    exit 1
fi

# 尝试使用 docker-compose (旧版本)
if command -v docker-compose &> /dev/null; then
    echo "🐳 使用 docker-compose 停止服务..."
    echo "🐳 Using docker-compose to stop services..."
    docker-compose -f docker-compose.neo4j.yml down
elif docker compose version &> /dev/null; then
    echo "🐳 使用 docker compose 停止服务..."
    echo "🐳 Using docker compose to stop services..."
    docker compose -f docker-compose.neo4j.yml down
else
    echo "⚠️  未找到 docker-compose，尝试手动停止容器..."
    echo "⚠️  docker-compose not found, trying to stop container manually..."
    
    # 手动停止和删除容器
    if docker ps | grep -q "youtu-graphrag-neo4j"; then
        echo "🔄 停止 Neo4j 容器..."
        echo "🔄 Stopping Neo4j container..."
        docker stop youtu-graphrag-neo4j
        
        echo "🗑️  删除 Neo4j 容器..."
        echo "🗑️  Removing Neo4j container..."
        docker rm youtu-graphrag-neo4j
    else
        echo "ℹ️  Neo4j 容器未运行"
        echo "ℹ️  Neo4j container is not running"
    fi
fi

# 检查是否还有相关容器在运行
echo "🔍 检查剩余容器..."
echo "🔍 Checking remaining containers..."
if docker ps | grep -q "neo4j"; then
    echo "⚠️  发现其他 Neo4j 容器仍在运行："
    echo "⚠️  Found other Neo4j containers still running:"
    docker ps | grep neo4j
    echo ""
    echo "如需停止所有 Neo4j 容器，请运行："
    echo "To stop all Neo4j containers, run:"
    echo "docker stop \$(docker ps -q --filter ancestor=neo4j)"
else
    echo "✅ 所有 Neo4j 容器已停止"
    echo "✅ All Neo4j containers stopped"
fi

echo ""
echo "🎉 Neo4j 可视化环境已停止！"
echo "🎉 Neo4j visualization environment stopped!"
echo ""
echo "📋 如需重新启动 / To restart:"
echo "   ./start_neo4j_visualization.sh"
echo ""
echo "📋 如需完全清理（删除数据卷）/ To completely clean up (remove data volumes):"
echo "   docker volume rm youtu_graphrag_neo4j_data youtu_graphrag_neo4j_logs youtu_graphrag_neo4j_import youtu_graphrag_neo4j_plugins"