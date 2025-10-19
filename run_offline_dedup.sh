#!/bin/bash
# Offline Semantic Deduplication Script
# Usage: ./run_offline_dedup.sh [graph_file] [chunks_file] [output_file]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
GRAPH_INPUT="${1:-output/graphs/demo_new.json}"
CHUNKS_INPUT="${2:-output/chunks/demo.txt}"
GRAPH_OUTPUT="${3:-output/graphs/demo_deduped_$(date +%Y%m%d_%H%M%S).json}"
PYTHON_CMD="${PYTHON_CMD:-/usr/bin/python3}"

# Check if Python exists
if ! command -v "$PYTHON_CMD" &> /dev/null; then
    PYTHON_CMD="python3"
fi

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  Offline Semantic Deduplication${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""

# Check input files
echo -e "${YELLOW}Checking input files...${NC}"
if [ ! -f "$GRAPH_INPUT" ]; then
    echo -e "${RED}Error: Graph file not found: $GRAPH_INPUT${NC}"
    exit 1
fi

if [ ! -f "$CHUNKS_INPUT" ] && [ ! -d "$CHUNKS_INPUT" ]; then
    echo -e "${RED}Error: Chunks file/directory not found: $CHUNKS_INPUT${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Input files exist${NC}"
echo ""

# Display configuration
echo -e "${YELLOW}Configuration:${NC}"
echo "  Graph Input:  $GRAPH_INPUT"
echo "  Chunks Input: $CHUNKS_INPUT"
echo "  Graph Output: $GRAPH_OUTPUT"
echo "  Python:       $PYTHON_CMD"
echo ""

# Check if API key is set
if [ -z "$LLM_API_KEY" ]; then
    echo -e "${YELLOW}⚠ LLM_API_KEY not set${NC}"
    echo "  Semantic deduplication will be disabled (exact dedup only)"
    echo "  To enable semantic dedup, set:"
    echo "    export LLM_API_KEY=your_key_here"
    echo ""
    USE_SEMANTIC="no"
else
    echo -e "${GREEN}✓ LLM_API_KEY is set${NC}"
    echo "  Semantic deduplication will be enabled"
    echo ""
    USE_SEMANTIC="yes"
fi

# Ask for confirmation
read -p "Continue? [Y/n] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ ! -z $REPLY ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo -e "${YELLOW}Starting deduplication...${NC}"
echo ""

# Build command
CMD="$PYTHON_CMD offline_semantic_dedup.py \
    --graph '$GRAPH_INPUT' \
    --chunks '$CHUNKS_INPUT' \
    --output '$GRAPH_OUTPUT'"

# Add force-enable if API key is set
if [ "$USE_SEMANTIC" = "yes" ]; then
    CMD="$CMD --force-enable"
fi

# Run the command
eval $CMD

# Check if output was created
if [ -f "$GRAPH_OUTPUT" ]; then
    echo ""
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}  Deduplication Completed Successfully!${NC}"
    echo -e "${GREEN}=========================================${NC}"
    echo ""
    echo "Output file: $GRAPH_OUTPUT"
    echo ""
    echo "File sizes:"
    ls -lh "$GRAPH_INPUT" "$GRAPH_OUTPUT"
    echo ""
    echo -e "${GREEN}✓ Done!${NC}"
else
    echo ""
    echo -e "${RED}Error: Output file was not created${NC}"
    exit 1
fi
