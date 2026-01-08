#!/bin/bash

# Phase B: Setup Script for Offline LLM Experimentation
# Downloads required models for comparative evaluation

echo "=========================================="
echo "Phase B: LLM Model Setup"
echo "=========================================="
echo ""
echo "This script will download 3 models for evaluation:"
echo "  1. qwen2.5:7b-instruct (Primary - Recommended)"
echo "  2. gemma:7b (Google's model)"
echo "  3. glm4:9b (ChatGLM model)"
echo ""
echo "Total download size: ~20-25 GB"
echo "Estimated time: 15-30 minutes (depending on connection)"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 1
fi

echo ""
echo "=========================================="
echo "Step 1/3: Pulling qwen2.5:7b-instruct"
echo "=========================================="
ollama pull qwen2.5:7b-instruct

if [ $? -ne 0 ]; then
    echo "❌ Failed to pull qwen2.5:7b-instruct"
    exit 1
fi

echo ""
echo "=========================================="
echo "Step 2/3: Pulling gemma:7b"
echo "=========================================="
ollama pull gemma:7b

if [ $? -ne 0 ]; then
    echo "❌ Failed to pull gemma:7b"
    exit 1
fi

echo ""
echo "=========================================="
echo "Step 3/3: Pulling glm4:9b"
echo "=========================================="
ollama pull glm4:9b

if [ $? -ne 0 ]; then
    echo "❌ Failed to pull glm4:9b"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ All models downloaded successfully!"
echo "=========================================="
echo ""
echo "Verifying installation..."
ollama list

echo ""
echo "✅ Setup complete! You can now run:"
echo "   python scripts/experiment_llm.py"
echo ""

