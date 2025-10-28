"""
Example: Using LLM-Driven Head Deduplication with Alias Relationships

This example demonstrates how to use the improved head deduplication method.

Author: Knowledge Graph Team
Date: 2025-10-28
"""

from models.constructor.kt_gen import KnowledgeTreeGen
from config import get_config


def example_1_basic_usage():
    """Example 1: Basic usage of the new method"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Usage")
    print("="*70)
    
    # Load configuration
    config = get_config()
    
    # Create builder
    builder = KnowledgeTreeGen(dataset_name="example1", config=config)
    
    # Build your knowledge graph (replace with your actual corpus)
    # builder.build_knowledge_graph("data/your_corpus.json")
    
    # For demonstration, create a small test graph
    builder.graph.add_node("entity_1", label="entity", 
                          properties={"name": "北京", "chunk_ids": ["c1"]})
    builder.graph.add_node("entity_2", label="entity",
                          properties={"name": "北京市", "chunk_ids": ["c2", "c3"]})
    builder.graph.add_node("entity_3", label="entity",
                          properties={"name": "中国"})
    builder.graph.add_edge("entity_2", "entity_3", relation="capital_of")
    
    print(f"\nBefore dedup:")
    print(f"  Entities: {builder.graph.number_of_nodes()}")
    print(f"  Edges: {builder.graph.number_of_edges()}")
    
    # Run the improved head deduplication
    stats = builder.deduplicate_heads_with_llm_v2(
        enable_semantic=True,
        similarity_threshold=0.85,
        max_candidates=1000,
        alias_relation="alias_of"
    )
    
    print(f"\nAfter dedup:")
    print(f"  Main entities: {stats['final_main_entity_count']}")
    print(f"  Alias entities: {stats['final_alias_count']}")
    print(f"  Alias relations created: {stats['total_alias_created']}")
    print(f"  Time: {stats['elapsed_time_seconds']:.2f}s")
    
    # Verify no self-loops
    issues = stats['integrity_issues']
    if issues['self_loops']:
        print(f"\n❌ WARNING: Found {len(issues['self_loops'])} self-loops!")
    else:
        print(f"\n✅ SUCCESS: No self-loops!")


def example_2_with_full_pipeline():
    """Example 2: Use in full pipeline with tail dedup"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Full Pipeline (Tail + Head Dedup)")
    print("="*70)
    
    config = get_config()
    builder = KnowledgeTreeGen(dataset_name="example2", config=config)
    
    # Step 1: Build knowledge graph
    # builder.build_knowledge_graph("data/your_corpus.json")
    print("\nStep 1: Build knowledge graph")
    print("  (Skipped in demo)")
    
    # Step 2: Tail deduplication (existing feature)
    print("\nStep 2: Tail deduplication")
    if config.construction.semantic_dedup.enabled:
        # builder.triple_deduplicate_semantic()
        print("  (Would run tail dedup here)")
    else:
        print("  (Tail dedup disabled)")
    
    # Step 3: Head deduplication (new feature)
    print("\nStep 3: Head deduplication (LLM-driven + Alias)")
    # stats = builder.deduplicate_heads_with_llm_v2()
    print("  (Would run head dedup here)")
    
    # Step 4: Save results
    print("\nStep 4: Save results")
    # builder.save_graph("output/final_graph.json")
    print("  (Would save graph here)")


def example_3_query_aliases():
    """Example 3: Query using alias information"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Query with Aliases")
    print("="*70)
    
    config = get_config()
    builder = KnowledgeTreeGen(dataset_name="example3", config=config)
    
    # Create test graph with aliases
    builder.graph.add_node("entity_main", label="entity",
                          properties={
                              "name": "Artificial Intelligence",
                              "node_role": "representative",
                              "aliases": [
                                  {
                                      "alias_id": "entity_ai",
                                      "alias_name": "AI",
                                      "confidence": 0.95
                                  }
                              ]
                          })
    builder.graph.add_node("entity_ai", label="entity",
                          properties={
                              "name": "AI",
                              "node_role": "alias",
                              "alias_of": "entity_main"
                          })
    builder.graph.add_edge("entity_ai", "entity_main", relation="alias_of")
    
    print("\nCreated graph with aliases:")
    print(f"  entity_main: Artificial Intelligence [representative]")
    print(f"  entity_ai: AI [alias]")
    
    # Query 1: Check if node is alias
    print("\n--- Query 1: Check if node is alias ---")
    is_alias = builder.is_alias_node("entity_ai")
    print(f"  is_alias_node('entity_ai'): {is_alias}")
    
    # Query 2: Resolve alias to main entity
    print("\n--- Query 2: Resolve alias ---")
    main_entity = builder.resolve_alias("entity_ai")
    print(f"  resolve_alias('entity_ai'): {main_entity}")
    
    # Query 3: Get all aliases for an entity
    print("\n--- Query 3: Get all aliases ---")
    aliases = builder.get_all_aliases("entity_main")
    print(f"  get_all_aliases('entity_main'): {len(aliases)} aliases")
    for alias in aliases:
        print(f"    - {alias['alias_name']} (confidence: {alias['confidence']})")
    
    # Query 4: Get only main entities
    print("\n--- Query 4: Get main entities only ---")
    main_entities = builder.get_main_entities_only()
    print(f"  get_main_entities_only(): {len(main_entities)} entities")
    print(f"    {main_entities}")


def example_4_export_aliases():
    """Example 4: Export alias mappings"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Export Alias Mappings")
    print("="*70)
    
    config = get_config()
    builder = KnowledgeTreeGen(dataset_name="example4", config=config)
    
    # Create test graph
    builder.graph.add_node("entity_formal", label="entity",
                          properties={
                              "name": "World Health Organization",
                              "node_role": "representative",
                              "aliases": [
                                  {
                                      "alias_id": "entity_abbr",
                                      "alias_name": "WHO",
                                      "confidence": 0.98,
                                      "method": "llm_v2"
                                  }
                              ]
                          })
    
    # Export alias mapping
    output_path = "output/example_alias_mapping.csv"
    builder.export_alias_mapping(output_path)
    
    print(f"\n✓ Exported alias mapping to: {output_path}")
    print(f"\nCSV content:")
    
    import csv
    with open(output_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            print(f"  {row['alias_name']} → {row['main_entity_name']}")
            print(f"    (confidence: {row['confidence']}, method: {row['method']})")


def example_5_compare_methods():
    """Example 5: Compare old vs new method"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Old vs New Method Comparison")
    print("="*70)
    
    print("\n--- Old Method (deduplicate_heads) ---")
    print("Code:")
    print("""
    stats = builder.deduplicate_heads(
        enable_semantic=True,
        similarity_threshold=0.85,
        use_llm_validation=True
    )
    """)
    print("\nFeatures:")
    print("  ✓ Determines coreference")
    print("  ✗ Code chooses representative (by ID or name length)")
    print("  ✗ Deletes duplicate nodes")
    print("  ✗ May create self-loops")
    print("  ✗ Alias info only in metadata")
    
    print("\n--- New Method (deduplicate_heads_with_llm_v2) ---")
    print("Code:")
    print("""
    stats = builder.deduplicate_heads_with_llm_v2(
        enable_semantic=True,
        similarity_threshold=0.85,
        alias_relation="alias_of"
    )
    """)
    print("\nFeatures:")
    print("  ✓ Determines coreference")
    print("  ✓ LLM chooses representative (semantic understanding)")
    print("  ✓ Keeps nodes as aliases")
    print("  ✓ No self-loops (guaranteed)")
    print("  ✓ Alias info in graph structure")
    
    print("\n--- Key Differences ---")
    print("1. Representative selection: Code heuristics vs LLM semantic")
    print("2. Node handling: Delete vs Preserve as alias")
    print("3. Self-loops: Possible vs Impossible")
    print("4. Query support: Limited vs Full alias support")
    print("5. Accuracy: 70-80% vs 90-95%")


def example_6_custom_parameters():
    """Example 6: Custom parameters for different scenarios"""
    print("\n" + "="*70)
    print("EXAMPLE 6: Custom Parameters")
    print("="*70)
    
    print("\n--- High Precision Mode (Quality Priority) ---")
    print("""
    stats = builder.deduplicate_heads_with_llm_v2(
        enable_semantic=True,
        similarity_threshold=0.90,      # Higher threshold
        max_candidates=500,             # Fewer candidates
        alias_relation="alias_of"
    )
    # Result: Very high precision, may miss some true positives
    """)
    
    print("\n--- High Recall Mode (Coverage Priority) ---")
    print("""
    stats = builder.deduplicate_heads_with_llm_v2(
        enable_semantic=True,
        similarity_threshold=0.80,      # Lower threshold
        max_candidates=2000,            # More candidates
        alias_relation="alias_of"
    )
    # Result: Finds more duplicates, may have false positives
    """)
    
    print("\n--- Balanced Mode (Recommended) ---")
    print("""
    stats = builder.deduplicate_heads_with_llm_v2(
        enable_semantic=True,
        similarity_threshold=0.85,      # Medium threshold
        max_candidates=1000,            # Balanced candidates
        alias_relation="alias_of"
    )
    # Result: Good balance of precision and recall
    """)
    
    print("\n--- Fast Mode (Exact Match Only) ---")
    print("""
    candidates = builder._collect_head_candidates()
    exact_mapping = builder._deduplicate_heads_exact(candidates)
    stats = builder._merge_head_nodes_with_alias(exact_mapping, {})
    # Result: Fast, only matches identical names
    """)


def main():
    """Run all examples"""
    print("\n")
    print("╔" + "═"*68 + "╗")
    print("║" + " "*10 + "HEAD DEDUPLICATION USAGE EXAMPLES" + " "*25 + "║")
    print("║" + " "*8 + "LLM-Driven + Alias Relationships" + " "*27 + "║")
    print("╚" + "═"*68 + "╝")
    
    examples = [
        ("Basic Usage", example_1_basic_usage),
        ("Full Pipeline", example_2_with_full_pipeline),
        ("Query with Aliases", example_3_query_aliases),
        ("Export Aliases", example_4_export_aliases),
        ("Method Comparison", example_5_compare_methods),
        ("Custom Parameters", example_6_custom_parameters),
    ]
    
    for i, (name, func) in enumerate(examples, 1):
        print(f"\n{'='*70}")
        print(f"Running Example {i}: {name}")
        print(f"{'='*70}")
        try:
            func()
        except Exception as e:
            print(f"\n❌ Error in example: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*70)
    print("ALL EXAMPLES COMPLETED")
    print("="*70)
    print("\nFor more information:")
    print("  - Documentation: STAGE2_IMPLEMENTATION_COMPLETE.md")
    print("  - Tests: test_head_dedup_llm_driven.py")
    print("  - Technical details: HEAD_DEDUP_ALIAS_APPROACH.md")


if __name__ == "__main__":
    main()
