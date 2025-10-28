"""
Test Head Deduplication with LLM-Driven Representative Selection + Alias Relationships

This test file demonstrates the improved head deduplication method.

Run with:
    python test_head_dedup_llm_driven.py

Author: Knowledge Graph Team
Date: 2025-10-28
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.constructor.kt_gen import KnowledgeTreeGen
from config import get_config
import networkx as nx


def test_1_self_loop_elimination():
    """Test 1: Verify no self-loops are created"""
    print("\n" + "="*70)
    print("TEST 1: Self-Loop Elimination")
    print("="*70)
    
    config = get_config()
    builder = KnowledgeTreeGen("test_self_loop", config)
    
    # Create scenario that would cause self-loop in old implementation
    builder.graph.add_node("entity_198", label="entity", 
                          properties={"name": "血流伪影", "chunk_ids": ["chunk_1"]})
    builder.graph.add_node("entity_361", label="entity",
                          properties={"name": "流动伪影", "chunk_ids": ["chunk_3", "chunk_4"]})
    builder.graph.add_node("entity_500", label="entity",
                          properties={"name": "MRI伪影"})
    
    # Original relationship that would become self-loop
    builder.graph.add_edge("entity_198", "entity_361", relation="别名包括", source_chunks=["chunk_1"])
    builder.graph.add_edge("entity_361", "entity_500", relation="是一种", source_chunks=["chunk_3"])
    
    print(f"\nBefore dedup:")
    print(f"  Nodes: {builder.graph.number_of_nodes()}")
    print(f"  Edges: {builder.graph.number_of_edges()}")
    
    # Simulate merge decision
    merge_mapping = {"entity_198": "entity_361"}
    metadata = {
        "entity_198": {
            "rationale": "Both refer to flow artifacts",
            "confidence": 0.92,
            "method": "llm_v2"
        }
    }
    
    # Apply merge with alias method
    stats = builder._merge_head_nodes_with_alias(merge_mapping, metadata)
    
    print(f"\nAfter dedup:")
    print(f"  Nodes: {builder.graph.number_of_nodes()}")
    print(f"  Edges: {builder.graph.number_of_edges()}")
    print(f"  Alias relations created: {stats['alias_relations_created']}")
    
    # Verify no self-loops
    issues = builder.validate_graph_integrity_with_alias()
    
    if issues["self_loops"]:
        print(f"\n✗ FAILED: Found self-loops: {issues['self_loops']}")
        return False
    else:
        print(f"\n✓ PASSED: No self-loops found")
    
    # Verify alias relationship exists
    alias_edges = [
        (u, v) for u, v, d in builder.graph.edges(data=True)
        if d.get("relation") == "alias_of"
    ]
    
    if len(alias_edges) == 1:
        print(f"✓ PASSED: Alias relationship created: {alias_edges[0]}")
    else:
        print(f"✗ FAILED: Expected 1 alias edge, found {len(alias_edges)}")
        return False
    
    # Verify node roles
    if builder.graph.nodes["entity_198"]["properties"].get("node_role") == "alias":
        print(f"✓ PASSED: entity_198 marked as alias")
    else:
        print(f"✗ FAILED: entity_198 not marked as alias")
        return False
    
    if builder.graph.nodes["entity_361"]["properties"].get("node_role") == "representative":
        print(f"✓ PASSED: entity_361 marked as representative")
    else:
        print(f"✗ FAILED: entity_361 not marked as representative")
        return False
    
    return True


def test_2_llm_prompt_loading():
    """Test 2: Verify new prompt template loads correctly"""
    print("\n" + "="*70)
    print("TEST 2: LLM Prompt Loading")
    print("="*70)
    
    config = get_config()
    builder = KnowledgeTreeGen("test_prompt", config)
    
    # Add test nodes
    builder.graph.add_node("entity_1", label="entity", 
                          properties={"name": "Test Entity 1"})
    builder.graph.add_node("entity_2", label="entity",
                          properties={"name": "Test Entity 2"})
    
    try:
        # Try to build prompt with new template
        prompt = builder._build_head_dedup_prompt_v2("entity_1", "entity_2")
        
        # Check if prompt contains key elements
        required_elements = [
            "PRIMARY REPRESENTATIVE",
            "preferred_representative",
            "entity_1",
            "entity_2",
            "Formality and Completeness",
            "Domain Convention",
            "Information Richness"
        ]
        
        missing = []
        for element in required_elements:
            if element not in prompt:
                missing.append(element)
        
        if missing:
            print(f"✗ FAILED: Missing elements in prompt: {missing}")
            print(f"\nPrompt preview:\n{prompt[:500]}...")
            return False
        
        print(f"✓ PASSED: Prompt loaded successfully")
        print(f"  Prompt length: {len(prompt)} characters")
        print(f"  Contains all required elements: {', '.join(required_elements[:3])}...")
        
        return True
        
    except Exception as e:
        print(f"✗ FAILED: Error loading prompt: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_3_utility_functions():
    """Test 3: Test utility functions (is_alias_node, resolve_alias, etc.)"""
    print("\n" + "="*70)
    print("TEST 3: Utility Functions")
    print("="*70)
    
    config = get_config()
    builder = KnowledgeTreeGen("test_utils", config)
    
    # Create test graph with aliases
    builder.graph.add_node("entity_main", label="entity",
                          properties={
                              "name": "Main Entity",
                              "node_role": "representative",
                              "aliases": [
                                  {"alias_id": "entity_alias1", "alias_name": "Alias 1"},
                                  {"alias_id": "entity_alias2", "alias_name": "Alias 2"}
                              ]
                          })
    builder.graph.add_node("entity_alias1", label="entity",
                          properties={
                              "name": "Alias 1",
                              "node_role": "alias",
                              "alias_of": "entity_main"
                          })
    builder.graph.add_edge("entity_alias1", "entity_main", relation="alias_of")
    
    builder.graph.add_node("entity_alias2", label="entity",
                          properties={
                              "name": "Alias 2",
                              "node_role": "alias",
                              "alias_of": "entity_main"
                          })
    builder.graph.add_edge("entity_alias2", "entity_main", relation="alias_of")
    
    # Test is_alias_node
    if not builder.is_alias_node("entity_alias1"):
        print("✗ FAILED: is_alias_node returned False for alias")
        return False
    if builder.is_alias_node("entity_main"):
        print("✗ FAILED: is_alias_node returned True for main entity")
        return False
    print("✓ PASSED: is_alias_node works correctly")
    
    # Test resolve_alias
    resolved = builder.resolve_alias("entity_alias1")
    if resolved != "entity_main":
        print(f"✗ FAILED: resolve_alias returned {resolved}, expected entity_main")
        return False
    print("✓ PASSED: resolve_alias works correctly")
    
    # Test get_all_aliases
    aliases = builder.get_all_aliases("entity_main")
    if len(aliases) != 2:
        print(f"✗ FAILED: get_all_aliases returned {len(aliases)} aliases, expected 2")
        return False
    print("✓ PASSED: get_all_aliases works correctly")
    
    # Test get_main_entities_only
    main_entities = builder.get_main_entities_only()
    if "entity_main" not in main_entities:
        print("✗ FAILED: get_main_entities_only missing main entity")
        return False
    if "entity_alias1" in main_entities:
        print("✗ FAILED: get_main_entities_only includes alias")
        return False
    print("✓ PASSED: get_main_entities_only works correctly")
    
    return True


def test_4_export_alias_mapping():
    """Test 4: Test alias mapping export"""
    print("\n" + "="*70)
    print("TEST 4: Export Alias Mapping")
    print("="*70)
    
    config = get_config()
    builder = KnowledgeTreeGen("test_export", config)
    
    # Create test graph
    builder.graph.add_node("entity_main", label="entity",
                          properties={
                              "name": "Main Entity",
                              "node_role": "representative",
                              "aliases": [
                                  {
                                      "alias_id": "entity_alias",
                                      "alias_name": "Alias Entity",
                                      "confidence": 0.92,
                                      "method": "llm_v2"
                                  }
                              ]
                          })
    
    try:
        output_path = "output/test_alias_mapping.csv"
        builder.export_alias_mapping(output_path)
        
        # Check if file was created
        if not os.path.exists(output_path):
            print(f"✗ FAILED: Output file not created: {output_path}")
            return False
        
        # Read and verify content
        import csv
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        if len(rows) != 1:
            print(f"✗ FAILED: Expected 1 row, found {len(rows)}")
            return False
        
        row = rows[0]
        if row["alias_id"] != "entity_alias":
            print(f"✗ FAILED: Wrong alias_id: {row['alias_id']}")
            return False
        
        if row["main_entity_id"] != "entity_main":
            print(f"✗ FAILED: Wrong main_entity_id: {row['main_entity_id']}")
            return False
        
        print(f"✓ PASSED: Alias mapping exported successfully")
        print(f"  Output file: {output_path}")
        print(f"  Rows: {len(rows)}")
        
        # Clean up
        os.remove(output_path)
        
        return True
        
    except Exception as e:
        print(f"✗ FAILED: Error exporting alias mapping: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_5_integration():
    """Test 5: Full integration test"""
    print("\n" + "="*70)
    print("TEST 5: Full Integration Test")
    print("="*70)
    
    config = get_config()
    builder = KnowledgeTreeGen("test_integration", config)
    
    # Create a small test graph
    entities = [
        ("entity_100", "北京"),
        ("entity_101", "北京市"),
        ("entity_200", "AI"),
        ("entity_201", "Artificial Intelligence"),
        ("entity_300", "WHO"),
        ("entity_301", "World Health Organization"),
    ]
    
    for entity_id, name in entities:
        builder.graph.add_node(entity_id, label="entity",
                              properties={"name": name, "chunk_ids": [f"chunk_{entity_id}"]})
    
    # Add some relations
    builder.graph.add_edge("entity_100", "entity_999", relation="capital_of", source_chunks=["chunk_1"])
    builder.graph.add_edge("entity_200", "entity_998", relation="field_of", source_chunks=["chunk_2"])
    builder.graph.add_edge("entity_300", "entity_997", relation="established_in", source_chunks=["chunk_3"])
    
    print(f"\nBefore dedup:")
    print(f"  Entities: {builder.graph.number_of_nodes()}")
    print(f"  Edges: {builder.graph.number_of_edges()}")
    
    # Run exact match dedup (should catch Beijing variants)
    candidates = builder._collect_head_candidates()
    exact_mapping = builder._deduplicate_heads_exact(candidates)
    
    if exact_mapping:
        stats = builder._merge_head_nodes_with_alias(exact_mapping, {})
        print(f"\nExact match:")
        print(f"  Mappings: {len(exact_mapping)}")
        print(f"  Aliases created: {stats['alias_relations_created']}")
    else:
        print("\nExact match: No duplicates found")
    
    print(f"\nAfter dedup:")
    print(f"  Entities: {builder.graph.number_of_nodes()}")
    print(f"  Main entities: {len(builder.get_main_entities_only())}")
    print(f"  Alias entities: {len([n for n in builder.graph.nodes() if builder.is_alias_node(n)])}")
    
    # Validate
    issues = builder.validate_graph_integrity_with_alias()
    
    has_issues = any(v for v in issues.values() if v)
    if has_issues:
        print(f"\n✗ FAILED: Found integrity issues:")
        for issue_type, issue_list in issues.items():
            if issue_list:
                print(f"  {issue_type}: {issue_list}")
        return False
    else:
        print(f"\n✓ PASSED: No integrity issues")
    
    return True


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "═"*68 + "╗")
    print("║" + " "*15 + "HEAD DEDUPLICATION TEST SUITE" + " "*24 + "║")
    print("║" + " "*10 + "LLM-Driven + Alias Relationships" + " "*25 + "║")
    print("╚" + "═"*68 + "╝")
    
    tests = [
        ("Self-Loop Elimination", test_1_self_loop_elimination),
        ("LLM Prompt Loading", test_2_llm_prompt_loading),
        ("Utility Functions", test_3_utility_functions),
        ("Export Alias Mapping", test_4_export_alias_mapping),
        ("Full Integration", test_5_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ EXCEPTION in {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status:12} | {test_name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print("="*70)
    print(f"TOTAL: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print("="*70)
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready to use.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
