#!/bin/bash

# Youtu-GraphRAG Startup Script
# Author: Youtu-GraphRAG Team

echo "🌟 Starting Youtu-GraphRAG Server..."
echo "=========================================="

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "❌ Conda not found. Please install Anaconda or Miniconda."
    exit 1
fi

# Activate ktrag environment
# echo "🔧 Activating ktrag environment..."
# source /data/anaconda3/bin/activate ktrag

# if [ $? -ne 0 ]; then
#     echo "❌ Failed to activate ktrag environment."
#     echo "💡 Please run: conda create -n ktrag python=3.8"
#     exit 1
# fi

# Check if required files exist
if [ ! -f "backend.py" ]; then
    echo "❌ backend.py not found. Please run this script from the project root directory."
    exit 1
fi

if [ ! -f "frontend/index.html" ]; then
    echo "❌ frontend/index.html not found."
    exit 1
fi

# Kill any existing backend processes
echo "🔄 Checking for existing processes..."
pkill -f backend.py 2>/dev/null || true

# Start the backend server
echo "🚀 Starting backend server..."
echo "📱 Access the application at: http://localhost:8000"
echo "🛑 Press Ctrl+C to stop the server"
echo "=========================================="

python backend.py

echo "👋 Youtu-GraphRAG server stopped."
