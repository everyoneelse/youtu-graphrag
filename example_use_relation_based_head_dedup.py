"""
Example: Using Logical Relations for Head Deduplication

This example demonstrates how to use logical relations (like "别名包括")
to enhance head deduplication, even when entity names have low semantic similarity.

Scenario:
- Entity A: "吉布斯伪影" (Gibbs artifact)
- Entity B: "截断伪影" (Truncation artifact)
- Relationship: A --[别名包括]--> B

Even though their names may have low semantic similarity, the existing
alias relationship in the graph indicates they might be duplicates.

Author: Knowledge Graph Team
Date: 2025-11-02
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from models.constructor.kt_gen import KnowledgeTreeGen
from head_dedup_with_logical_relations import HeadDeduplicationLogicalRelationsMixin
from head_dedup_alias_implementation import HeadDeduplicationAliasMixin
from head_dedup_llm_driven_representative import HeadDeduplicationLLMDrivenMixin
from utils.logger import logger


class EnhancedKnowledgeTreeGen(
    HeadDeduplicationLogicalRelationsMixin,
    HeadDeduplicationLLMDrivenMixin,
    HeadDeduplicationAliasMixin,
    KnowledgeTreeGen
):
    """
    Enhanced KnowledgeTreeGen with logical relations support.
    
    Combines:
    - Logical relations-based candidate generation
    - LLM-driven representative selection
    - Alias-based merging
    """
    pass


def create_test_graph_with_alias_relations():
    """
    Create a test graph with alias relationships.
    
    Scenario:
    - 吉布斯伪影 and 截断伪影 are connected by "别名包括" relation
    - 伪影A and 伪影B are semantically similar
    - 实体X and 实体Y have both alias relation AND semantic similarity
    """
    from config.config_manager import ConfigManager
    import networkx as nx
    
    # Load config
    config_path = project_root / "config" / "kt_gen_default.yaml"
    config = ConfigManager(config_path)
    
    # Initialize builder
    builder = EnhancedKnowledgeTreeGen(config=config)
    
    # Create a fresh graph
    builder.graph = nx.MultiDiGraph()
    builder.all_chunks = {}
    
    # Add test entities and relationships
    
    # Case 1: Alias relation with low semantic similarity
    # 吉布斯伪影 and 截断伪影
    builder.graph.add_node(
        "entity_100",
        label="entity",
        properties={
            "name": "吉布斯伪影",
            "description": "一种由于K空间采样不足导致的MRI伪影",
            "chunk_id": "chunk_100"
        }
    )
    builder.all_chunks["chunk_100"] = (
        "吉布斯伪影是一种由于K空间采样不足而产生的MRI伪影，"
        "表现为图像中的振铃效应和边缘伪影。"
    )
    
    builder.graph.add_node(
        "entity_101",
        label="entity",
        properties={
            "name": "截断伪影",
            "description": "K空间截断导致的伪影，也称为吉布斯振铃",
            "chunk_id": "chunk_101"
        }
    )
    builder.all_chunks["chunk_101"] = (
        "截断伪影是由K空间截断引起的，在图像上表现为边界附近的振铃效应。"
        "这种伪影也被称为吉布斯振铃。"
    )
    
    # Add alias relationship
    builder.graph.add_edge(
        "entity_100", "entity_101",
        relation="别名包括",
        source_chunks=["chunk_100"]
    )
    
    # Case 2: High semantic similarity without explicit alias relation
    builder.graph.add_node(
        "entity_200",
        label="entity",
        properties={
            "name": "运动伪影",
            "description": "患者运动导致的MRI伪影",
            "chunk_id": "chunk_200"
        }
    )
    builder.all_chunks["chunk_200"] = "运动伪影是由于患者在扫描过程中移动造成的。"
    
    builder.graph.add_node(
        "entity_201",
        label="entity",
        properties={
            "name": "运动伪影",  # Same name - should be caught by exact match
            "description": "患者移动引起的伪影",
            "chunk_id": "chunk_201"
        }
    )
    builder.all_chunks["chunk_201"] = "运动伪影表现为图像模糊和重影。"
    
    # Case 3: Both alias relation AND semantic similarity
    builder.graph.add_node(
        "entity_300",
        label="entity",
        properties={
            "name": "磁共振成像",
            "description": "利用磁场和射频脉冲进行成像的技术",
            "chunk_id": "chunk_300"
        }
    )
    builder.all_chunks["chunk_300"] = "磁共振成像(MRI)是一种无创的医学成像技术。"
    
    builder.graph.add_node(
        "entity_301",
        label="entity",
        properties={
            "name": "MRI",
            "description": "Magnetic Resonance Imaging的缩写",
            "chunk_id": "chunk_301"
        }
    )
    builder.all_chunks["chunk_301"] = "MRI是磁共振成像的英文缩写。"
    
    # Add alias relationship
    builder.graph.add_edge(
        "entity_300", "entity_301",
        relation="别名",
        source_chunks=["chunk_300"]
    )
    
    # Case 4: Unrelated entities (should NOT be merged)
    builder.graph.add_node(
        "entity_400",
        label="entity",
        properties={
            "name": "化学位移伪影",
            "description": "由于脂肪和水的化学位移不同导致的伪影",
            "chunk_id": "chunk_400"
        }
    )
    builder.all_chunks["chunk_400"] = "化学位移伪影是由于不同组织的化学位移造成的。"
    
    builder.graph.add_node(
        "entity_401",
        label="entity",
        properties={
            "name": "金属伪影",
            "description": "金属植入物导致的伪影",
            "chunk_id": "chunk_401"
        }
    )
    builder.all_chunks["chunk_401"] = "金属伪影是由于金属植入物的磁敏感性造成的。"
    
    # Add some relationships for context
    builder.graph.add_edge(
        "entity_100", "entity_400",
        relation="不同于",
        source_chunks=["chunk_100"]
    )
    
    return builder


def demonstrate_relation_based_dedup():
    """
    Demonstrate the enhanced head deduplication with logical relations.
    """
    print("\n" + "=" * 70)
    print("Example: Head Deduplication with Logical Relations")
    print("=" * 70)
    
    # Create test graph
    print("\n[1] Creating test graph with alias relationships...")
    builder = create_test_graph_with_alias_relations()
    
    print("\nInitial graph:")
    print(f"  - Entities: {len([n for n, d in builder.graph.nodes(data=True) if d.get('label') == 'entity'])}")
    print(f"  - Edges: {builder.graph.number_of_edges()}")
    
    print("\nTest cases:")
    print("  Case 1: 吉布斯伪影 --[别名包括]--> 截断伪影")
    print("          (Low semantic similarity, but has alias relation)")
    print("  Case 2: 运动伪影 (two entities with same name)")
    print("          (High semantic similarity, no explicit relation)")
    print("  Case 3: 磁共振成像 --[别名]--> MRI")
    print("          (Both semantic similarity AND alias relation)")
    print("  Case 4: 化学位移伪影 vs 金属伪影")
    print("          (Unrelated, should NOT merge)")
    
    # Run enhanced deduplication
    print("\n[2] Running enhanced head deduplication...")
    print("    (Combining semantic similarity + logical relations)")
    
    try:
        stats = builder.deduplicate_heads_with_relations(
            enable_semantic=True,
            enable_relation_candidates=True,
            similarity_threshold=0.85,
            use_llm_validation=True,  # Set to False to skip LLM calls
            max_candidates=100,
            alias_relation="alias_of",
            alias_relation_names=["别名包括", "别名", "alias_of", "aka"]
        )
        
        print("\n[3] Deduplication completed!")
        print(f"\nResults:")
        print(f"  - Initial entities: {stats['initial_entity_count']}")
        print(f"  - Final main entities: {stats['final_main_entity_count']}")
        print(f"  - Final alias entities: {stats['final_alias_count']}")
        print(f"  - Alias relations created: {stats['total_alias_created']}")
        print(f"  - Relation-based candidates: {stats['relation_based_candidates']}")
        print(f"  - Time elapsed: {stats['elapsed_time_seconds']:.2f}s")
        
        # Show final structure
        print("\n[4] Final graph structure:")
        main_entities = [
            (n, d['properties'].get('name'))
            for n, d in builder.graph.nodes(data=True)
            if d.get('label') == 'entity' and
               d.get('properties', {}).get('node_role') != 'alias'
        ]
        print(f"  Main entities ({len(main_entities)}):")
        for node_id, name in main_entities:
            print(f"    - {node_id}: {name}")
        
        alias_entities = [
            (n, d['properties'].get('name'), d['properties'].get('alias_of'))
            for n, d in builder.graph.nodes(data=True)
            if d.get('properties', {}).get('node_role') == 'alias'
        ]
        if alias_entities:
            print(f"\n  Alias entities ({len(alias_entities)}):")
            for node_id, name, alias_of in alias_entities:
                print(f"    - {node_id}: {name} -> (alias of {alias_of})")
        
        # Check for integrity issues
        if stats['integrity_issues']:
            has_issues = any(v for v in stats['integrity_issues'].values() if v)
            if has_issues:
                print("\n⚠ Warning: Integrity issues detected:")
                for issue_type, issues in stats['integrity_issues'].items():
                    if issues:
                        print(f"    - {issue_type}: {len(issues)}")
        else:
            print("\n✓ No integrity issues detected")
        
        return stats
        
    except Exception as e:
        logger.error(f"Error during deduplication: {e}", exc_info=True)
        raise


def demonstrate_relation_extraction_only():
    """
    Demonstrate just the relation extraction component.
    """
    print("\n" + "=" * 70)
    print("Demo: Relation-Based Candidate Extraction")
    print("=" * 70)
    
    # Create test graph
    builder = create_test_graph_with_alias_relations()
    
    # Get all entities
    entities = [
        n for n, d in builder.graph.nodes(data=True)
        if d.get('label') == 'entity'
    ]
    
    print(f"\nEntities in graph: {len(entities)}")
    
    # Extract relation-based candidates
    print("\nExtracting alias relation candidates...")
    relation_candidates = builder._extract_alias_relation_candidates(
        entities,
        alias_relation_names=["别名包括", "别名", "alias_of", "aka"]
    )
    
    print(f"\nFound {len(relation_candidates)} relation-based candidate pairs:")
    for u, v, relation_type in relation_candidates:
        u_name = builder.graph.nodes[u]['properties'].get('name')
        v_name = builder.graph.nodes[v]['properties'].get('name')
        print(f"  - {u} ({u_name}) --[{relation_type}]--> {v} ({v_name})")
    
    # Compare with semantic candidates
    print("\n\nGenerating semantic similarity candidates...")
    semantic_candidates = builder._generate_semantic_candidates(
        entities,
        max_candidates=100,
        similarity_threshold=0.75
    )
    
    print(f"\nFound {len(semantic_candidates)} semantic candidate pairs:")
    for u, v, similarity in semantic_candidates[:5]:  # Show first 5
        u_name = builder.graph.nodes[u]['properties'].get('name')
        v_name = builder.graph.nodes[v]['properties'].get('name')
        print(f"  - {u} ({u_name}) <-> {v} ({v_name}): {similarity:.3f}")
    
    if len(semantic_candidates) > 5:
        print(f"  ... and {len(semantic_candidates) - 5} more")
    
    # Check overlap
    relation_pairs = {tuple(sorted([u, v])) for u, v, _ in relation_candidates}
    semantic_pairs = {tuple(sorted([u, v])) for u, v, _ in semantic_candidates}
    
    overlap = relation_pairs & semantic_pairs
    relation_only = relation_pairs - semantic_pairs
    
    print(f"\n\nAnalysis:")
    print(f"  - Relation-only pairs: {len(relation_only)}")
    print(f"  - Semantic-only pairs: {len(semantic_pairs) - len(overlap)}")
    print(f"  - Overlap (both): {len(overlap)}")
    
    if relation_only:
        print(f"\n  Relation-only pairs (would be missed without this feature):")
        for u, v in relation_only:
            u_name = builder.graph.nodes[u]['properties'].get('name')
            v_name = builder.graph.nodes[v]['properties'].get('name')
            print(f"    - {u} ({u_name}) <-> {v} ({v_name})")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Head Deduplication with Logical Relations - Examples")
    print("=" * 70)
    
    # Demo 1: Show relation extraction
    try:
        demonstrate_relation_extraction_only()
    except Exception as e:
        print(f"\n❌ Demo 1 failed: {e}")
        logger.error("Demo 1 failed", exc_info=True)
    
    # Demo 2: Full deduplication with relations
    print("\n\n" + "=" * 70)
    print("Full Deduplication Pipeline")
    print("=" * 70)
    
    try:
        stats = demonstrate_relation_based_dedup()
        print("\n✓ All demos completed successfully!")
    except Exception as e:
        print(f"\n❌ Demo 2 failed: {e}")
        logger.error("Demo 2 failed", exc_info=True)
        
        print("\nNote: If LLM validation is enabled, make sure:")
        print("  1. LLM API credentials are configured")
        print("  2. LLM service is accessible")
        print("  3. Or set use_llm_validation=False in the example")
