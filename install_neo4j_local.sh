#!/bin/bash

# 本地 Neo4j 安装脚本（无需 Docker）
# Local Neo4j installation script (without Docker)

echo "🌐 安装本地 Neo4j 数据库..."
echo "🌐 Installing local Neo4j database..."

# 检查 Java 是否已安装
if ! command -v java &> /dev/null; then
    echo "☕ 安装 Java 11..."
    echo "☕ Installing Java 11..."
    sudo apt update
    sudo apt install -y openjdk-11-jdk
fi

# 显示 Java 版本
java -version

# 添加 Neo4j 仓库
echo "📦 添加 Neo4j 仓库..."
echo "📦 Adding Neo4j repository..."
wget -O - https://debian.neo4j.com/neotechnology.gpg.key | sudo apt-key add -
echo 'deb https://debian.neo4j.com stable latest' | sudo tee -a /etc/apt/sources.list.d/neo4j.list

# 更新包列表
sudo apt update

# 安装 Neo4j Community Edition
echo "🔧 安装 Neo4j Community Edition..."
echo "🔧 Installing Neo4j Community Edition..."
sudo apt install -y neo4j

# 设置初始密码
echo "🔑 设置 Neo4j 密码..."
echo "🔑 Setting Neo4j password..."
sudo neo4j-admin set-initial-password graphrag123

# 启动 Neo4j 服务
echo "🚀 启动 Neo4j 服务..."
echo "🚀 Starting Neo4j service..."
sudo systemctl enable neo4j
sudo systemctl start neo4j

# 检查服务状态
echo "🔍 检查服务状态..."
echo "🔍 Checking service status..."
sudo systemctl status neo4j

echo ""
echo "✅ Neo4j 安装完成！"
echo "✅ Neo4j installation completed!"
echo ""
echo "📋 访问信息："
echo "📋 Access Information:"
echo "   🌐 Neo4j Browser: http://localhost:7474"
echo "   👤 用户名 / Username: neo4j"
echo "   🔑 密码 / Password: graphrag123"
echo ""
echo "📋 服务管理命令："
echo "📋 Service management commands:"
echo "   启动 / Start: sudo systemctl start neo4j"
echo "   停止 / Stop: sudo systemctl stop neo4j"
echo "   重启 / Restart: sudo systemctl restart neo4j"
echo "   状态 / Status: sudo systemctl status neo4j"