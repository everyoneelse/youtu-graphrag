"""
Example: Multi-Signal Head Entity Deduplication

This example demonstrates how to use the multi-signal approach for head entity
deduplication, which goes beyond simple name semantic similarity.

Author: Knowledge Graph Team
Date: 2025-11-02
"""

import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.constructor.kt_gen import KnowledgeTreeGen
from config import get_config
from utils.logger import logger


def example_basic_usage():
    """Basic usage with default configuration."""
    
    print("=" * 70)
    print("Example 1: Basic Multi-Signal Head Deduplication")
    print("=" * 70)
    
    # 1. Load configuration
    config = get_config("config/multi_signal_head_dedup.yaml")
    
    # 2. Initialize builder
    builder = KnowledgeTreeGen(
        dataset_name="medical_imaging",
        schema_path="schemas/medical.json",
        config=config
    )
    
    # 3. Build knowledge graph (includes extraction + deduplication)
    knowledge_graph = builder.build_knowledge_graph("data/medical/corpus.json")
    
    # 4. Check results
    print(f"\nFinal graph statistics:")
    print(f"  - Total nodes: {knowledge_graph.number_of_nodes()}")
    print(f"  - Total edges: {knowledge_graph.number_of_edges()}")
    
    # 5. Export alias mapping
    builder.export_alias_mapping("output/alias_mapping.csv")
    
    print("\n✓ Deduplication completed!")


def example_custom_config():
    """Usage with custom configuration."""
    
    print("=" * 70)
    print("Example 2: Custom Configuration")
    print("=" * 70)
    
    # 1. Load base config
    config = get_config("config/base_config.yaml")
    
    # 2. Initialize builder
    builder = KnowledgeTreeGen(
        dataset_name="my_dataset",
        schema_path="schemas/demo.json",
        config=config
    )
    
    # 3. Build graph first (without dedup)
    knowledge_graph = builder.build_knowledge_graph(
        "data/my_data/corpus.json",
        skip_deduplication=True  # Skip automatic dedup
    )
    
    # 4. Run multi-signal deduplication with custom config
    dedup_config = {
        # Enable all signals
        "enable_semantic_signal": True,
        "enable_subgraph_signal": True,
        "enable_alias_signal": True,
        "enable_attribute_signal": True,
        
        # Custom thresholds (more conservative)
        "semantic_threshold": 0.80,      # Higher threshold for semantic
        "subgraph_threshold": 0.65,      # Higher threshold for structure
        "attribute_threshold": 0.70,     # Higher threshold for attributes
        
        # Custom weights (trust alias more, semantic less)
        "signal_weights": {
            "semantic": 0.20,     # Lower weight for semantic
            "subgraph": 0.30,     # Higher weight for structure
            "alias": 0.40,        # Highest weight for alias
            "attribute": 0.10
        },
        
        # LLM validation
        "use_llm_validation": True,
        "llm_validation_threshold": 0.75,  # Only validate high-scoring pairs
        
        # Merge strategy
        "merge_strategy": "alias",  # Preserve nodes as aliases
        "max_semantic_candidates": 1000
    }
    
    # 5. Run deduplication
    stats = builder.deduplicate_heads_multi_signal(config=dedup_config)
    
    # 6. Analyze results
    print("\nDeduplication Statistics:")
    print(f"  - Initial entities: {stats['initial_entity_count']}")
    print(f"  - Final main entities: {stats['final_main_entity_count']}")
    print(f"  - Final alias entities: {stats['final_alias_count']}")
    print(f"  - Total merged: {stats['total_merged']}")
    print(f"  - Time elapsed: {stats['elapsed_time_seconds']:.2f}s")
    
    print("\nMerge decisions by primary signal:")
    for signal, count in stats['signal_breakdown'].items():
        percentage = count / stats['total_merged'] * 100 if stats['total_merged'] > 0 else 0
        print(f"  - {signal}: {count} ({percentage:.1f}%)")


def example_analyze_signals():
    """Analyze which signals contributed to finding duplicates."""
    
    print("=" * 70)
    print("Example 3: Signal Analysis")
    print("=" * 70)
    
    config = get_config("config/multi_signal_head_dedup.yaml")
    
    builder = KnowledgeTreeGen(
        dataset_name="analysis_example",
        schema_path="schemas/demo.json",
        config=config
    )
    
    # Build graph
    builder.build_knowledge_graph("data/demo/demo_corpus.json")
    
    # Run diagnosis to see signal coverage
    # This shows which signals identified which pairs
    print("\n=== Signal Coverage Analysis ===")
    
    # Get all entity nodes
    entities = [
        n for n, d in builder.graph.nodes(data=True)
        if d.get("label") == "entity" and
           d.get("properties", {}).get("node_role") != "alias"
    ]
    
    print(f"Analyzing {len(entities)} main entities...")
    
    # Identify all alias relationships
    alias_count = 0
    signal_sources = defaultdict(int)
    
    for node_id, data in builder.graph.nodes(data=True):
        if data.get("properties", {}).get("node_role") == "alias":
            alias_count += 1
            
            # Check what signal led to this alias
            out_edges = list(builder.graph.out_edges(node_id, data=True))
            for _, target, edge_data in out_edges:
                if edge_data.get("relation") == "alias_of":
                    # Check metadata for signal info
                    metadata = edge_data.get("dedup_metadata", {})
                    primary_signal = metadata.get("primary_signal", "unknown")
                    signal_sources[primary_signal] += 1
    
    print(f"\nFound {alias_count} alias entities")
    print("\nPrimary signals that identified aliases:")
    for signal, count in sorted(signal_sources.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {signal}: {count} aliases")
    
    # Show some examples
    print("\n=== Example Alias Pairs ===")
    for node_id, data in list(builder.graph.nodes(data=True))[:5]:
        if data.get("properties", {}).get("node_role") == "alias":
            node_name = data.get("properties", {}).get("name", "")
            
            # Find the main entity
            out_edges = list(builder.graph.out_edges(node_id, data=True))
            for _, target, edge_data in out_edges:
                if edge_data.get("relation") == "alias_of":
                    target_name = builder.graph.nodes[target]["properties"]["name"]
                    metadata = edge_data.get("dedup_metadata", {})
                    signals = metadata.get("signals", {})
                    
                    print(f"\n  {node_name} → {target_name}")
                    print(f"    Signals:")
                    for sig_name, sig_value in signals.items():
                        print(f"      - {sig_name}: {sig_value:.2f}")


def example_signal_ablation():
    """Compare results with different signal combinations (ablation study)."""
    
    print("=" * 70)
    print("Example 4: Signal Ablation Study")
    print("=" * 70)
    
    config = get_config("config/base_config.yaml")
    corpus_path = "data/demo/demo_corpus.json"
    
    # Test configurations
    test_configs = [
        {
            "name": "Semantic Only (Baseline)",
            "config": {
                "enable_semantic_signal": True,
                "enable_subgraph_signal": False,
                "enable_alias_signal": False,
                "enable_attribute_signal": False,
            }
        },
        {
            "name": "Semantic + Subgraph",
            "config": {
                "enable_semantic_signal": True,
                "enable_subgraph_signal": True,
                "enable_alias_signal": False,
                "enable_attribute_signal": False,
            }
        },
        {
            "name": "Semantic + Alias",
            "config": {
                "enable_semantic_signal": True,
                "enable_subgraph_signal": False,
                "enable_alias_signal": True,
                "enable_attribute_signal": False,
            }
        },
        {
            "name": "All Signals",
            "config": {
                "enable_semantic_signal": True,
                "enable_subgraph_signal": True,
                "enable_alias_signal": True,
                "enable_attribute_signal": True,
            }
        }
    ]
    
    results = []
    
    for test in test_configs:
        print(f"\n--- Testing: {test['name']} ---")
        
        # Create fresh builder
        builder = KnowledgeTreeGen(
            dataset_name=f"ablation_{test['name'].replace(' ', '_')}",
            schema_path="schemas/demo.json",
            config=config
        )
        
        # Build graph
        builder.build_knowledge_graph(corpus_path, skip_deduplication=True)
        
        # Run dedup with test config
        test_config = {
            **test['config'],
            "use_llm_validation": False,  # Disable for speed
            "semantic_threshold": 0.75,
            "subgraph_threshold": 0.60,
            "attribute_threshold": 0.60,
            "merge_strategy": "alias"
        }
        
        stats = builder.deduplicate_heads_multi_signal(config=test_config)
        
        results.append({
            "name": test['name'],
            "merged": stats['total_merged'],
            "time": stats['elapsed_time_seconds']
        })
        
        print(f"  Merged: {stats['total_merged']} pairs")
        print(f"  Time: {stats['elapsed_time_seconds']:.2f}s")
    
    # Summary comparison
    print("\n" + "=" * 70)
    print("Ablation Study Results")
    print("=" * 70)
    print(f"{'Configuration':<30} {'Merged Pairs':<15} {'Time (s)':<10}")
    print("-" * 70)
    for result in results:
        print(f"{result['name']:<30} {result['merged']:<15} {result['time']:<10.2f}")
    print("=" * 70)
    
    # Calculate improvements
    baseline_merged = results[0]['merged']
    final_merged = results[-1]['merged']
    improvement = ((final_merged - baseline_merged) / baseline_merged * 100) if baseline_merged > 0 else 0
    
    print(f"\nImprovement: Multi-signal found {improvement:.1f}% more duplicates than baseline")


def example_diagnostic_tools():
    """Use diagnostic tools to understand deduplication decisions."""
    
    print("=" * 70)
    print("Example 5: Diagnostic Tools")
    print("=" * 70)
    
    config = get_config("config/multi_signal_head_dedup.yaml")
    
    builder = KnowledgeTreeGen(
        dataset_name="diagnostic_example",
        schema_path="schemas/demo.json",
        config=config
    )
    
    # Build graph with dedup
    builder.build_knowledge_graph("data/demo/demo_corpus.json")
    
    # Tool 1: Export alias mapping for manual review
    print("\n1. Exporting alias mapping...")
    builder.export_alias_mapping("output/diagnostic_alias_mapping.csv")
    print("   ✓ Saved to: output/diagnostic_alias_mapping.csv")
    
    # Tool 2: Check for potential issues
    print("\n2. Checking graph integrity...")
    if hasattr(builder, 'validate_graph_integrity_with_alias'):
        issues = builder.validate_graph_integrity_with_alias()
        
        if any(v for v in issues.values() if v):
            print("   ⚠ Found issues:")
            for issue_type, issue_list in issues.items():
                if issue_list:
                    print(f"     - {issue_type}: {len(issue_list)}")
        else:
            print("   ✓ No integrity issues found")
    
    # Tool 3: Analyze signal contribution
    print("\n3. Analyzing signal contributions...")
    
    # Count how many aliases were found by each signal
    signal_contribution = defaultdict(int)
    total_aliases = 0
    
    for node_id, data in builder.graph.nodes(data=True):
        props = data.get("properties", {})
        if props.get("node_role") == "representative":
            aliases = props.get("aliases", [])
            for alias_info in aliases:
                total_aliases += 1
                method = alias_info.get("method", "unknown")
                signal_contribution[method] += 1
    
    print(f"   Total aliases: {total_aliases}")
    print("   Signal contributions:")
    for signal, count in sorted(signal_contribution.items(), key=lambda x: x[1], reverse=True):
        percentage = count / total_aliases * 100 if total_aliases > 0 else 0
        print(f"     - {signal}: {count} ({percentage:.1f}%)")
    
    # Tool 4: Sample some alias decisions for manual inspection
    print("\n4. Sample alias decisions:")
    
    sample_count = 0
    for node_id, data in builder.graph.nodes(data=True):
        if sample_count >= 3:
            break
        
        props = data.get("properties", {})
        if props.get("node_role") == "representative":
            aliases = props.get("aliases", [])
            if aliases:
                main_name = props.get("name", "")
                print(f"\n   Main Entity: {main_name}")
                
                for alias_info in aliases[:2]:  # Show first 2 aliases
                    alias_name = alias_info.get("alias_name", "")
                    confidence = alias_info.get("confidence", 0)
                    print(f"     ← Alias: {alias_name} (confidence: {confidence:.2f})")
                
                sample_count += 1


if __name__ == "__main__":
    import sys
    from collections import defaultdict
    
    # Choose which example to run
    if len(sys.argv) > 1:
        example_num = sys.argv[1]
    else:
        print("Choose an example to run:")
        print("  1: Basic usage")
        print("  2: Custom configuration")
        print("  3: Signal analysis")
        print("  4: Signal ablation study")
        print("  5: Diagnostic tools")
        example_num = input("\nEnter number (1-5): ")
    
    try:
        example_num = int(example_num)
        
        if example_num == 1:
            example_basic_usage()
        elif example_num == 2:
            example_custom_config()
        elif example_num == 3:
            example_analyze_signals()
        elif example_num == 4:
            example_signal_ablation()
        elif example_num == 5:
            example_diagnostic_tools()
        else:
            print("Invalid example number. Please choose 1-5.")
    except ValueError:
        print("Invalid input. Please enter a number.")
    except Exception as e:
        logger.error(f"Example failed: {e}")
        import traceback
        traceback.print_exc()
