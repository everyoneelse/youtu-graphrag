"""Example usage of apply_dedup_results module.

This script demonstrates different ways to use the DedupResultsApplier class
to apply deduplication results to a graph.
"""

from pathlib import Path
import sys

# Import the applier class
from apply_dedup_results import DedupResultsApplier
from utils import graph_processor
from utils.logger import logger


def example_basic_usage():
    """Basic usage example: apply both keyword and edge dedup."""
    print("\n" + "="*60)
    print("Example 1: Basic Usage - Apply Both Dedup Types")
    print("="*60 + "\n")
    
    # Initialize applier
    applier = DedupResultsApplier()
    
    # Load graph
    graph_path = "output/graphs/demo_new.json"
    print(f"Loading graph from: {graph_path}")
    applier.graph = graph_processor.load_graph_from_json(graph_path)
    
    original_nodes = applier.graph.number_of_nodes()
    original_edges = applier.graph.number_of_edges()
    print(f"Original graph: {original_nodes} nodes, {original_edges} edges\n")
    
    # Load dedup results
    keyword_dedup_file = Path("output/dedup_intermediate/demo_dedup_20251021_120000.json")
    edge_dedup_file = Path("output/dedup_intermediate/demo_edge_dedup_20251021_120000.json")
    
    if keyword_dedup_file.exists():
        print(f"Loading keyword dedup results from: {keyword_dedup_file}")
        applier.load_keyword_dedup_results(keyword_dedup_file)
    else:
        print(f"Warning: Keyword dedup file not found: {keyword_dedup_file}")
    
    if edge_dedup_file.exists():
        print(f"Loading edge dedup results from: {edge_dedup_file}")
        applier.load_edge_dedup_results(edge_dedup_file)
    else:
        print(f"Warning: Edge dedup file not found: {edge_dedup_file}")
    
    # Apply deduplication
    print("\nApplying deduplication...")
    applier.apply_dedup_to_graph()
    
    # Save result
    output_path = "output/graphs/demo_deduped.json"
    graph_processor.save_graph_to_json(applier.graph, output_path)
    
    final_nodes = applier.graph.number_of_nodes()
    final_edges = applier.graph.number_of_edges()
    
    print(f"\nResults:")
    print(f"  Nodes: {original_nodes} -> {final_nodes} (removed {original_nodes - final_nodes})")
    print(f"  Edges: {original_edges} -> {final_edges} (removed {original_edges - final_edges})")
    print(f"  Saved to: {output_path}")


def example_keyword_only():
    """Apply only keyword deduplication."""
    print("\n" + "="*60)
    print("Example 2: Apply Only Keyword Deduplication")
    print("="*60 + "\n")
    
    applier = DedupResultsApplier()
    
    # Load graph
    graph_path = "output/graphs/demo_new.json"
    applier.graph = graph_processor.load_graph_from_json(graph_path)
    
    # Load only keyword dedup results
    keyword_dedup_file = Path("output/dedup_intermediate/demo_dedup_20251021_120000.json")
    
    if keyword_dedup_file.exists():
        applier.load_keyword_dedup_results(keyword_dedup_file)
        applier.apply_dedup_to_graph()
        
        # Save result
        output_path = "output/graphs/demo_keyword_deduped.json"
        graph_processor.save_graph_to_json(applier.graph, output_path)
        print(f"Saved to: {output_path}")
    else:
        print(f"Error: Keyword dedup file not found: {keyword_dedup_file}")


def example_edge_only():
    """Apply only edge deduplication."""
    print("\n" + "="*60)
    print("Example 3: Apply Only Edge Deduplication")
    print("="*60 + "\n")
    
    applier = DedupResultsApplier()
    
    # Load graph
    graph_path = "output/graphs/demo_new.json"
    applier.graph = graph_processor.load_graph_from_json(graph_path)
    
    # Load only edge dedup results
    edge_dedup_file = Path("output/dedup_intermediate/demo_edge_dedup_20251021_120000.json")
    
    if edge_dedup_file.exists():
        applier.load_edge_dedup_results(edge_dedup_file)
        applier.apply_dedup_to_graph()
        
        # Save result
        output_path = "output/graphs/demo_edge_deduped.json"
        graph_processor.save_graph_to_json(applier.graph, output_path)
        print(f"Saved to: {output_path}")
    else:
        print(f"Error: Edge dedup file not found: {edge_dedup_file}")


def example_inspect_mappings():
    """Inspect the dedup mappings before applying."""
    print("\n" + "="*60)
    print("Example 4: Inspect Dedup Mappings")
    print("="*60 + "\n")
    
    applier = DedupResultsApplier()
    
    # Load dedup results
    keyword_dedup_file = Path("output/dedup_intermediate/demo_dedup_20251021_120000.json")
    edge_dedup_file = Path("output/dedup_intermediate/demo_edge_dedup_20251021_120000.json")
    
    if keyword_dedup_file.exists():
        applier.load_keyword_dedup_results(keyword_dedup_file)
        print(f"Keyword node mappings: {len(applier.node_mapping)}")
        
        # Show first 5 mappings
        if applier.node_mapping:
            print("\nSample keyword mappings:")
            for i, (dup, rep) in enumerate(list(applier.node_mapping.items())[:5]):
                print(f"  {i+1}. {dup} -> {rep}")
    
    if edge_dedup_file.exists():
        applier.load_edge_dedup_results(edge_dedup_file)
        print(f"\nEdge mappings: {len(applier.edge_mapping)}")
        
        # Show first 5 mappings
        if applier.edge_mapping:
            print("\nSample edge mappings:")
            for i, ((h, r, t), rep_t) in enumerate(list(applier.edge_mapping.items())[:5]):
                print(f"  {i+1}. ({h}, {r}, {t}) -> ({h}, {r}, {rep_t})")


def example_batch_processing():
    """Process multiple graphs with the same dedup results."""
    print("\n" + "="*60)
    print("Example 5: Batch Processing Multiple Graphs")
    print("="*60 + "\n")
    
    # List of graph files to process
    graph_files = [
        "output/graphs/demo_new.json",
        # Add more graph files here
    ]
    
    # Dedup results (shared across all graphs)
    keyword_dedup_file = Path("output/dedup_intermediate/demo_dedup_20251021_120000.json")
    edge_dedup_file = Path("output/dedup_intermediate/demo_edge_dedup_20251021_120000.json")
    
    for graph_file in graph_files:
        if not Path(graph_file).exists():
            print(f"Skipping {graph_file} (not found)")
            continue
        
        print(f"\nProcessing: {graph_file}")
        
        applier = DedupResultsApplier()
        applier.graph = graph_processor.load_graph_from_json(graph_file)
        
        if keyword_dedup_file.exists():
            applier.load_keyword_dedup_results(keyword_dedup_file)
        
        if edge_dedup_file.exists():
            applier.load_edge_dedup_results(edge_dedup_file)
        
        applier.apply_dedup_to_graph()
        
        # Generate output filename
        output_file = graph_file.replace(".json", "_deduped.json")
        graph_processor.save_graph_to_json(applier.graph, output_file)
        print(f"  Saved to: {output_file}")


def main():
    """Run all examples or a specific one."""
    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        if example_num == "1":
            example_basic_usage()
        elif example_num == "2":
            example_keyword_only()
        elif example_num == "3":
            example_edge_only()
        elif example_num == "4":
            example_inspect_mappings()
        elif example_num == "5":
            example_batch_processing()
        else:
            print(f"Unknown example: {example_num}")
            print("Available examples: 1, 2, 3, 4, 5")
    else:
        print("Usage: python example_apply_dedup_usage.py <example_number>")
        print("\nAvailable examples:")
        print("  1 - Basic usage (apply both keyword and edge dedup)")
        print("  2 - Apply only keyword deduplication")
        print("  3 - Apply only edge deduplication")
        print("  4 - Inspect dedup mappings before applying")
        print("  5 - Batch processing multiple graphs")
        print("\nExample:")
        print("  python example_apply_dedup_usage.py 1")


if __name__ == "__main__":
    main()
