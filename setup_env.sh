#!/bin/bash

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

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
