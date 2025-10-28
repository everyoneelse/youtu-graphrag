#!/bin/bash
# Example script to apply deduplication results to graph.json
#
# This script demonstrates how to use apply_dedup_results.py to apply
# previously saved semantic and keyword deduplication results to the
# original graph.json file.

set -e  # Exit on error

# Configuration
GRAPH_FILE="output/graphs/demo_new.json"
OUTPUT_FILE="output/graphs/demo_deduped.json"

# Find the latest dedup result files
# You should replace these with your actual dedup result file paths
KEYWORD_DEDUP_FILE=$(find output/dedup_intermediate -name "*_dedup_*.json" -not -name "*edge*" 2>/dev/null | sort -r | head -1)
EDGE_DEDUP_FILE=$(find output/dedup_intermediate -name "*_edge_dedup_*.json" 2>/dev/null | sort -r | head -1)

# Check if files exist
if [ ! -f "$GRAPH_FILE" ]; then
    echo "Error: Graph file not found: $GRAPH_FILE"
    echo "Please specify the correct path to your graph.json file"
    exit 1
fi

echo "========================================="
echo "Apply Deduplication Results to Graph"
echo "========================================="
echo ""
echo "Graph file: $GRAPH_FILE"
echo "Output file: $OUTPUT_FILE"
echo ""

# Build the command
CMD="python apply_dedup_results.py --graph \"$GRAPH_FILE\" --output \"$OUTPUT_FILE\""

# Add keyword dedup if available
if [ -n "$KEYWORD_DEDUP_FILE" ] && [ -f "$KEYWORD_DEDUP_FILE" ]; then
    echo "Keyword dedup file: $KEYWORD_DEDUP_FILE"
    CMD="$CMD --keyword-dedup \"$KEYWORD_DEDUP_FILE\""
else
    echo "Warning: No keyword dedup results found"
    echo "Please specify with --keyword-dedup option if you have one"
fi

# Add edge dedup if available
if [ -n "$EDGE_DEDUP_FILE" ] && [ -f "$EDGE_DEDUP_FILE" ]; then
    echo "Edge dedup file: $EDGE_DEDUP_FILE"
    CMD="$CMD --edge-dedup \"$EDGE_DEDUP_FILE\""
else
    echo "Warning: No edge dedup results found"
    echo "Please specify with --edge-dedup option if you have one"
fi

echo ""
echo "Running command:"
echo "$CMD"
echo ""

# Check if at least one dedup file is available
if [ -z "$KEYWORD_DEDUP_FILE" ] && [ -z "$EDGE_DEDUP_FILE" ]; then
    echo "Error: No deduplication results found!"
    echo ""
    echo "Please provide at least one of:"
    echo "  - Keyword dedup results (e.g., output/dedup_intermediate/demo_dedup_*.json)"
    echo "  - Edge dedup results (e.g., output/dedup_intermediate/demo_edge_dedup_*.json)"
    echo ""
    echo "You can specify them manually:"
    echo "  python apply_dedup_results.py \\"
    echo "      --graph $GRAPH_FILE \\"
    echo "      --keyword-dedup <path-to-keyword-dedup.json> \\"
    echo "      --edge-dedup <path-to-edge-dedup.json> \\"
    echo "      --output $OUTPUT_FILE"
    exit 1
fi

# Execute the command
eval "$CMD"

echo ""
echo "========================================="
echo "Deduplication Complete!"
echo "========================================="
echo "Output saved to: $OUTPUT_FILE"
