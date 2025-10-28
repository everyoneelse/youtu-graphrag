"""
Example usage of head node deduplication feature.

This example shows how to use the head node deduplication functionality
after building a knowledge graph.

Author: Knowledge Graph Team
Date: 2025-10-27
"""

from models.constructor.kt_gen import KnowledgeTreeGen
from config import get_config


def example_basic_usage():
    """Example 1: Basic usage with default config settings"""
    print("\n" + "="*80)
    print("Example 1: Basic Usage - Using Config Settings")
    print("="*80)
    
    # 1. Load config
    config = get_config()
    
    # 2. Create knowledge graph builder
    builder = KnowledgeTreeGen(dataset_name="demo", config=config)
    
    # 3. Build graph (假设已经完成)
    # builder.build_knowledge_graph("data/demo/demo_corpus.json")
    
    # 4. Run tail deduplication first (if enabled)
    if config.construction.semantic_dedup.enabled:
        print("\nRunning tail deduplication...")
        builder.triple_deduplicate_semantic()
    
    # 5. Run head deduplication
    # 需要先在config中启用: head_dedup.enabled = true
    print("\nRunning head deduplication...")
    stats = builder.deduplicate_heads()
    
    # 6. Check results
    if stats.get("enabled"):
        print(f"\n✓ Head deduplication completed:")
        print(f"  - Initial entities: {stats['initial_entity_count']}")
        print(f"  - Final entities: {stats['final_entity_count']}")
        print(f"  - Total merges: {stats['total_merges']}")
        print(f"  - Reduction rate: {stats['reduction_rate']:.2f}%")
    else:
        print("\n⚠ Head deduplication is disabled in config")


def example_custom_parameters():
    """Example 2: Using custom parameters (override config)"""
    print("\n" + "="*80)
    print("Example 2: Custom Parameters")
    print("="*80)
    
    config = get_config()
    builder = KnowledgeTreeGen(dataset_name="demo", config=config)
    
    # Manually enable and configure head deduplication
    # (even if disabled in config file)
    if hasattr(config.construction.semantic_dedup, 'head_dedup'):
        config.construction.semantic_dedup.head_dedup.enabled = True
    
    # Run with custom parameters
    stats = builder.deduplicate_heads(
        enable_semantic=True,
        similarity_threshold=0.90,  # More strict
        use_llm_validation=False,   # Fast mode
        max_candidates=500          # Limit candidates
    )
    
    print(f"\n✓ Custom parameters applied:")
    print(f"  - Threshold: 0.90 (strict)")
    print(f"  - LLM validation: False (fast)")
    print(f"  - Max candidates: 500")


def example_with_llm_validation():
    """Example 3: High precision mode with LLM validation"""
    print("\n" + "="*80)
    print("Example 3: High Precision Mode (with LLM)")
    print("="*80)
    
    config = get_config()
    builder = KnowledgeTreeGen(dataset_name="demo", config=config)
    
    # Enable head dedup in config
    if hasattr(config.construction.semantic_dedup, 'head_dedup'):
        config.construction.semantic_dedup.head_dedup.enabled = True
    
    # Run with LLM validation
    stats = builder.deduplicate_heads(
        enable_semantic=True,
        similarity_threshold=0.85,
        use_llm_validation=True,  # High precision mode
        max_candidates=200        # Limit LLM calls for cost control
    )
    
    print(f"\n✓ High precision mode:")
    print(f"  - LLM validated: {stats.get('semantic_merges', 0)} merges")
    print(f"  - Time: {stats.get('elapsed_time_seconds', 0):.2f}s")


def example_complete_pipeline():
    """Example 4: Complete pipeline from building to head dedup"""
    print("\n" + "="*80)
    print("Example 4: Complete Pipeline")
    print("="*80)
    
    config = get_config()
    builder = KnowledgeTreeGen(dataset_name="demo", config=config)
    
    # Step 1: Build knowledge graph
    print("\n[Step 1] Building knowledge graph...")
    # builder.build_knowledge_graph("data/demo/demo_corpus.json")
    print("  ✓ Graph built")
    
    # Step 2: Tail deduplication (if enabled)
    if config.construction.semantic_dedup.enabled:
        print("\n[Step 2] Running tail deduplication...")
        builder.triple_deduplicate_semantic()
        print("  ✓ Tail deduplication completed")
    
    # Step 3: Head deduplication
    if hasattr(config.construction.semantic_dedup, 'head_dedup'):
        head_config = config.construction.semantic_dedup.head_dedup
        if getattr(head_config, 'enabled', False):
            print("\n[Step 3] Running head deduplication...")
            stats = builder.deduplicate_heads()
            print(f"  ✓ Merged {stats['total_merges']} head nodes")
            
            # Step 4: Verify integrity
            print("\n[Step 4] Verifying graph integrity...")
            issues = stats.get('integrity_issues', {})
            if any(issues.values()):
                print(f"  ⚠ Found issues: {issues}")
            else:
                print("  ✓ Graph integrity verified")
    
    # Step 5: Save graph
    print("\n[Step 5] Saving final graph...")
    builder.save_graphml("output/graphs/demo_after_head_dedup.graphml")
    print("  ✓ Graph saved")


def example_inspect_results():
    """Example 5: Inspect head deduplication results"""
    print("\n" + "="*80)
    print("Example 5: Inspect Merge Results")
    print("="*80)
    
    config = get_config()
    builder = KnowledgeTreeGen(dataset_name="demo", config=config)
    
    # Run head dedup
    if hasattr(config.construction.semantic_dedup, 'head_dedup'):
        config.construction.semantic_dedup.head_dedup.enabled = True
    
    stats = builder.deduplicate_heads(
        enable_semantic=True,
        similarity_threshold=0.85
    )
    
    # Inspect merge history
    print("\n" + "="*80)
    print("Merge History:")
    print("="*80)
    
    merge_count = 0
    for node_id, data in builder.graph.nodes(data=True):
        if data.get("label") != "entity":
            continue
        
        dedup_info = data.get("properties", {}).get("head_dedup", {})
        
        if dedup_info and dedup_info.get("merged_nodes"):
            canonical_name = data.get("properties", {}).get("name", "")
            merged_nodes = dedup_info.get("merged_nodes", [])
            merge_history = dedup_info.get("merge_history", [])
            
            print(f"\n✓ Canonical: {node_id} ({canonical_name})")
            print(f"  Merged {len(merged_nodes)} duplicate(s):")
            
            for record in merge_history:
                print(f"    • {record['merged_node_id']} ({record['merged_node_name']})")
                print(f"      - Confidence: {record['confidence']:.3f}")
                print(f"      - Method: {record['method']}")
                print(f"      - Rationale: {record['rationale'][:80]}...")
            
            merge_count += 1
            if merge_count >= 5:  # Show only first 5 for brevity
                break
    
    if merge_count == 0:
        print("\nNo merges found (or all exact matches)")


def example_export_for_review():
    """Example 6: Export candidates for human review"""
    print("\n" + "="*80)
    print("Example 6: Export for Human Review")
    print("="*80)
    
    config = get_config()
    builder = KnowledgeTreeGen(dataset_name="demo", config=config)
    
    # Enable head dedup with review export
    if hasattr(config.construction.semantic_dedup, 'head_dedup'):
        head_config = config.construction.semantic_dedup.head_dedup
        head_config.enabled = True
        head_config.export_review = True
        head_config.review_confidence_range = [0.70, 0.90]
    
    # Run head dedup (will auto-export based on config)
    stats = builder.deduplicate_heads()
    
    # Or manually export
    builder.export_head_merge_candidates_for_review(
        output_path="output/review/head_merges_manual.csv",
        min_confidence=0.65,
        max_confidence=0.95
    )
    
    print("\n✓ Review file exported to:")
    print("  - Auto: output/review/head_merge_demo_*.csv")
    print("  - Manual: output/review/head_merges_manual.csv")
    print("\nOpen in Excel to review merges with confidence 0.65-0.95")


def example_config_file_usage():
    """Example 7: Using config file to control behavior"""
    print("\n" + "="*80)
    print("Example 7: Config File Usage")
    print("="*80)
    
    print("\nTo enable head deduplication in config/base_config.yaml:")
    print("""
# In config/base_config.yaml:
construction:
  semantic_dedup:
    enabled: true  # Enable tail dedup first
    
    head_dedup:
      enabled: true                      # Enable head dedup
      enable_semantic: true               # Use semantic matching
      similarity_threshold: 0.85          # Threshold (0.85-0.90 recommended)
      use_llm_validation: false           # false=fast, true=accurate
      max_candidates: 1000                # Max pairs to process
      candidate_similarity_threshold: 0.75  # Pre-filtering threshold
      max_relations_context: 10           # Relations to include as context
      export_review: true                 # Export uncertain cases
      review_confidence_range: [0.70, 0.90]  # Range for review
      review_output_dir: "output/review"
""")
    
    print("\nThen simply call:")
    print("  builder.deduplicate_heads()  # Uses config settings")


if __name__ == "__main__":
    """
    Run examples
    
    Note: These examples assume you have already built a knowledge graph.
    Modify the dataset_name and paths according to your setup.
    """
    
    print("\n" + "="*80)
    print("Head Node Deduplication Examples")
    print("="*80)
    print("\nThese examples demonstrate various ways to use head deduplication.")
    print("Make sure to enable head_dedup in config/base_config.yaml first!")
    print("="*80)
    
    # Uncomment the examples you want to run:
    
    # example_basic_usage()
    # example_custom_parameters()
    # example_with_llm_validation()
    # example_complete_pipeline()
    # example_inspect_results()
    # example_export_for_review()
    example_config_file_usage()
    
    print("\n✓ Examples completed")
    print("\nTo run a specific example, uncomment it in the __main__ section.")
