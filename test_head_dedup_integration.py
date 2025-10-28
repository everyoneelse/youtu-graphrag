"""
Test head node deduplication integration.

This test verifies that the head deduplication feature is properly integrated
into the KnowledgeTreeGen class.

Usage:
    python test_head_dedup_integration.py

Author: Knowledge Graph Team
Date: 2025-10-27
"""

import sys
import networkx as nx


def test_imports():
    """Test that all required imports work."""
    print("Testing imports...")
    try:
        from models.constructor.kt_gen import KnowledgeTreeGen
        from config import get_config
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_methods_exist():
    """Test that head dedup methods exist in KnowledgeTreeGen."""
    print("\nTesting method existence...")
    
    from models.constructor.kt_gen import KnowledgeTreeGen
    from config import get_config
    
    config = get_config()
    builder = KnowledgeTreeGen(dataset_name="test", config=config)
    
    required_methods = [
        'deduplicate_heads',
        '_collect_head_candidates',
        '_normalize_entity_name',
        '_deduplicate_heads_exact',
        '_generate_semantic_candidates',
        '_validate_candidates_with_embedding',
        '_validate_candidates_with_llm',
        '_build_head_dedup_prompt',
        '_collect_node_context',
        '_parse_coreference_response',
        '_merge_head_nodes',
        '_reassign_outgoing_edges',
        '_reassign_incoming_edges',
        '_find_similar_edge',
        '_merge_edge_chunks',
        '_merge_node_properties',
        'validate_graph_integrity_after_head_dedup',
        'export_head_merge_candidates_for_review',
        # Note: _get_default_head_dedup_prompt removed - prompt only in config
    ]
    
    missing = []
    for method_name in required_methods:
        if not hasattr(builder, method_name):
            missing.append(method_name)
            print(f"✗ Missing method: {method_name}")
        else:
            print(f"✓ Found method: {method_name}")
    
    if missing:
        print(f"\n✗ Missing {len(missing)} methods")
        return False
    else:
        print(f"\n✓ All {len(required_methods)} methods found")
        return True


def test_config_loading():
    """Test that head_dedup config can be loaded."""
    print("\nTesting config loading...")
    
    from config import get_config
    
    config = get_config()
    
    # Check if head_dedup config exists
    if not hasattr(config.construction.semantic_dedup, 'head_dedup'):
        print("✗ head_dedup config not found")
        return False
    
    head_config = config.construction.semantic_dedup.head_dedup
    
    # Check required config fields
    required_fields = [
        'enabled', 'enable_semantic', 'similarity_threshold',
        'use_llm_validation', 'max_candidates'
    ]
    
    missing = []
    for field in required_fields:
        if not hasattr(head_config, field):
            missing.append(field)
            print(f"✗ Missing config field: {field}")
        else:
            value = getattr(head_config, field)
            print(f"✓ Config field: {field} = {value}")
    
    if missing:
        print(f"\n✗ Missing {len(missing)} config fields")
        return False
    else:
        print(f"\n✓ All config fields found")
        return True


def test_prompt_loading():
    """Test that head_dedup prompt can be loaded."""
    print("\nTesting prompt loading...")
    
    from config import get_config
    
    config = get_config()
    
    try:
        prompt = config.get_prompt_formatted(
            "head_dedup",
            "general",
            entity_1="Test Entity 1",
            context_1="Test context 1",
            entity_2="Test Entity 2",
            context_2="Test context 2"
        )
        
        # Check if variables were replaced
        if "Test Entity 1" in prompt and "Test Entity 2" in prompt:
            print("✓ Prompt loaded successfully")
            print(f"✓ Prompt length: {len(prompt)} characters")
            print(f"✓ Variables replaced correctly")
            return True
        else:
            print("✗ Variables not replaced in prompt")
            return False
            
    except Exception as e:
        print(f"✗ Failed to load prompt: {e}")
        return False


def test_basic_functionality():
    """Test basic head deduplication functionality with a simple graph."""
    print("\nTesting basic functionality...")
    
    from models.constructor.kt_gen import KnowledgeTreeGen
    from config import get_config
    
    config = get_config()
    builder = KnowledgeTreeGen(dataset_name="test", config=config)
    
    # Manually enable head_dedup
    if hasattr(config.construction.semantic_dedup, 'head_dedup'):
        config.construction.semantic_dedup.head_dedup.enabled = True
    
    # Create a simple test graph
    print("  Creating test graph...")
    builder.graph.add_node("entity_0", label="entity", properties={"name": "北京", "chunk id": 1})
    builder.graph.add_node("entity_1", label="entity", properties={"name": "北京市", "chunk id": 2})
    builder.graph.add_node("entity_2", label="entity", properties={"name": "上海", "chunk id": 3})
    builder.graph.add_node("entity_3", label="keyword", properties={"name": "test"})  # Non-entity
    
    # Add some edges
    builder.graph.add_edge("entity_0", "entity_2", relation="nearby")
    builder.graph.add_edge("entity_1", "entity_2", relation="similar_to")
    
    initial_entities = len([n for n, d in builder.graph.nodes(data=True) if d.get("label") == "entity"])
    print(f"  Initial entities: {initial_entities}")
    
    # Run head deduplication (only exact match to avoid LLM calls)
    try:
        stats = builder.deduplicate_heads(
            enable_semantic=False,  # Only exact match
            similarity_threshold=0.85,
            use_llm_validation=False,
            max_candidates=100
        )
        
        if not stats.get("enabled"):
            print("✗ Head dedup not enabled")
            return False
        
        final_entities = len([n for n, d in builder.graph.nodes(data=True) if d.get("label") == "entity"])
        
        print(f"  Final entities: {final_entities}")
        print(f"  Merged: {stats['total_merges']}")
        print(f"  Reduction rate: {stats['reduction_rate']:.1f}%")
        
        # Verify graph integrity
        issues = stats.get('integrity_issues', {})
        if any(issues.values()):
            print(f"✗ Integrity issues found: {issues}")
            return False
        
        print("✓ Basic functionality test passed")
        return True
        
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all integration tests."""
    print("="*80)
    print("HEAD NODE DEDUPLICATION - INTEGRATION TESTS")
    print("="*80)
    
    tests = [
        ("Imports", test_imports),
        ("Method Existence", test_methods_exist),
        ("Config Loading", test_config_loading),
        ("Prompt Loading", test_prompt_loading),
        ("Basic Functionality", test_basic_functionality),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print("\n" + "="*80)
        print(f"TEST: {test_name}")
        print("="*80)
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ Test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*80)
    print(f"Results: {passed}/{total} tests passed")
    print("="*80)
    
    if passed == total:
        print("\n🎉 All tests passed! Head deduplication is ready to use.")
        return 0
    else:
        print(f"\n⚠ {total - passed} test(s) failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
