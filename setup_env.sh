#!/bin/bash

# Youtu-GraphRAG Environment Setup Script
# Author: Youtu-GraphRAG Team

# echo "🌟 Setting up Youtu-GraphRAG Environment..."
# echo "==========================================="

# # Check if conda is available
# if ! command -v conda &> /dev/null; then
#     echo "❌ Conda not found. Please install Anaconda or Miniconda first."
#     echo "💡 Download from: https://docs.conda.io/en/latest/miniconda.html"
#     exit 1
# fi

# # Create conda environment
# echo "🔧 Creating ktrag conda environment..."
# conda create -n ktrag python=3.10 -y

# if [ $? -ne 0 ]; then
#     echo "❌ Failed to create conda environment."
#     exit 1
# fi

# # Activate environment
# echo "🔧 Activating ktrag environment..."
# source /data/anaconda3/bin/activate ktrag

# if [ $? -ne 0 ]; then
#     echo "❌ Failed to activate ktrag environment."
#     exit 1
# fi

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install PyTorch with CPU support
echo "🤖 Installing PyTorch (CPU version)..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install requirements
echo "📦 Installing requirements..."
pip install -r requirements.txt

# Download spaCy model
echo "🧠 Downloading spaCy English model..."
python -m spacy download en_core_web_sm

# Verify installation
echo "✅ Verifying installation..."
python -c "
import fastapi
import uvicorn
import torch
import sentence_transformers
import faiss
import spacy
print('✅ All dependencies installed successfully!')
print(f'FastAPI version: {fastapi.__version__}')
print(f'PyTorch version: {torch.__version__}')
print(f'Sentence Transformers version: {sentence_transformers.__version__}')
"

if [ $? -eq 0 ]; then
    echo "==========================================="
    echo "🎉 Environment setup completed successfully!"
    echo "🚀 You can now start the server with: ./start.sh"
    echo "==========================================="
else
    echo "❌ Installation verification failed. Please check the error messages above."
    exit 1
fi
