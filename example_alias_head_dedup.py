"""
Example usage of alias-based head deduplication

This demonstrates the improved approach that:
1. Avoids self-loops
2. Creates explicit alias relationships
3. Preserves semantic information

Date: 2025-10-28
"""

import sys
import networkx as nx
from typing import Dict, List

# Mock logger for standalone execution
class MockLogger:
    def info(self, msg): print(f"[INFO] {msg}")
    def debug(self, msg): print(f"[DEBUG] {msg}")
    def warning(self, msg): print(f"[WARN] {msg}")
    def error(self, msg): print(f"[ERROR] {msg}")

logger = MockLogger()


def create_test_graph_with_alias_issue():
    """
    Create a test graph that demonstrates the self-loop problem.
    
    Scenario:
    - entity_198 (血流伪影) has an edge to entity_361 (流动伪影)
    - entity_361 has edges to other entities
    - LLM determines they are equivalent (aliases)
    - Traditional merge would create self-loop
    """
    G = nx.MultiDiGraph()
    
    # Add nodes
    G.add_node("entity_198", label="entity", properties={
        "name": "血流伪影",
        "chunk_ids": ["chunk_1", "chunk_2"]
    })
    
    G.add_node("entity_361", label="entity", properties={
        "name": "流动伪影",
        "chunk_ids": ["chunk_3", "chunk_4", "chunk_5"]
    })
    
    G.add_node("entity_500", label="entity", properties={
        "name": "MRI伪影"
    })
    
    G.add_node("entity_600", label="entity", properties={
        "name": "流动补偿"
    })
    
    # Add edges
    G.add_edge("entity_198", "entity_361", 
               relation="别名包括", source_chunks=["chunk_1"])
    G.add_edge("entity_361", "entity_500",
               relation="是一种", source_chunks=["chunk_3"])
    G.add_edge("entity_361", "entity_600",
               relation="解决方案", source_chunks=["chunk_4"])
    
    return G


def demonstrate_traditional_problem(G):
    """
    Demonstrate the self-loop problem with traditional merge.
    """
    print("\n" + "="*70)
    print("TRADITIONAL APPROACH - Demonstrating the Problem")
    print("="*70)
    
    print("\nOriginal Graph:")
    print(f"  Nodes: {list(G.nodes())}")
    print(f"  Edges:")
    for u, v, data in G.edges(data=True):
        print(f"    {u} --[{data.get('relation')}]--> {v}")
    
    # Simulate traditional merge: entity_198 -> entity_361
    print("\nSimulating traditional merge (entity_198 -> entity_361)...")
    print("  Step 1: Transfer outgoing edges from entity_198")
    print("    - entity_198 --[别名包括]--> entity_361")
    print("    - Would become: entity_361 --[别名包括]--> entity_361")
    print("    - ✗ SELF-LOOP CREATED!")
    
    print("\n  Step 2: Transfer incoming edges to entity_198")
    print("    - (none in this example)")
    
    print("\n  Step 3: Delete entity_198")
    print("    - Node entity_198 removed from graph")
    
    print("\n✗ Problem: Self-loop created and alias information lost!")
    
    return


def demonstrate_alias_approach():
    """
    Demonstrate the improved alias-based approach.
    """
    print("\n" + "="*70)
    print("ALIAS APPROACH - Solving the Problem")
    print("="*70)
    
    G = create_test_graph_with_alias_issue()
    
    print("\nStep 1: Choose representative")
    print("  Evaluating candidates:")
    print("    - entity_198: out_degree=1, name_length=5, chunks=2")
    print("    - entity_361: out_degree=2, name_length=5, chunks=3")
    print("  ✓ Choose entity_361 as representative (higher out_degree)")
    
    canonical_id = "entity_361"
    duplicate_id = "entity_198"
    
    print("\nStep 2: Transfer edges from entity_198 to entity_361")
    print("  Checking outgoing edges:")
    print("    - entity_198 --[别名包括]--> entity_361")
    print("    - Target is canonical node, SKIP (avoid self-loop) ✓")
    print("  No edges transferred (all would create self-loops)")
    
    print("\nStep 3: Create explicit alias relationship")
    G.add_edge(duplicate_id, canonical_id,
               relation="alias_of",
               source_chunks=[],
               created_by="head_deduplication")
    print(f"  ✓ Created: {duplicate_id} --[alias_of]--> {canonical_id}")
    
    print("\nStep 4: Clean up entity_198's other edges")
    # Remove the old edge
    G.remove_edge("entity_198", "entity_361", key=0)
    # Add back only the alias_of edge (already added above)
    print("  ✓ Removed old edges, kept only alias_of")
    
    print("\nStep 5: Mark node roles")
    G.nodes[duplicate_id]["properties"]["node_role"] = "alias"
    G.nodes[duplicate_id]["properties"]["alias_of"] = canonical_id
    G.nodes[canonical_id]["properties"]["node_role"] = "representative"
    G.nodes[canonical_id]["properties"]["aliases"] = [{
        "alias_id": duplicate_id,
        "alias_name": "血流伪影",
        "confidence": 0.92,
        "method": "llm"
    }]
    print(f"  ✓ Marked {duplicate_id} as 'alias'")
    print(f"  ✓ Marked {canonical_id} as 'representative'")
    
    print("\n" + "="*70)
    print("FINAL GRAPH:")
    print("="*70)
    print(f"\nNodes:")
    for node_id in G.nodes():
        props = G.nodes[node_id]["properties"]
        role = props.get("node_role", "normal")
        name = props.get("name", "")
        print(f"  {node_id} ({name}) [{role}]")
    
    print(f"\nEdges:")
    for u, v, data in G.edges(data=True):
        relation = data.get("relation", "unknown")
        print(f"  {u} --[{relation}]--> {v}")
    
    # Verify no self-loops
    print("\n" + "="*70)
    print("VERIFICATION:")
    print("="*70)
    
    self_loops = [(u, v) for u, v in G.edges() if u == v]
    if self_loops:
        print(f"✗ Found {len(self_loops)} self-loops: {self_loops}")
    else:
        print("✓ No self-loops found!")
    
    # Check alias node
    alias_nodes = [
        n for n in G.nodes() 
        if G.nodes[n]["properties"].get("node_role") == "alias"
    ]
    print(f"✓ Found {len(alias_nodes)} alias nodes: {alias_nodes}")
    
    # Check alias edges
    alias_edges = [
        (u, v) for u, v, d in G.edges(data=True)
        if d.get("relation") == "alias_of"
    ]
    print(f"✓ Found {len(alias_edges)} alias relationships: {alias_edges}")
    
    return G


def demonstrate_query_with_aliases(G):
    """
    Demonstrate how to query using alias information.
    """
    print("\n" + "="*70)
    print("QUERY EXAMPLES:")
    print("="*70)
    
    # Query 1: Find main entity for an alias
    print("\nQuery 1: User searches for '血流伪影' (entity_198)")
    query_node = "entity_198"
    
    # Check if it's an alias
    if G.nodes[query_node]["properties"].get("node_role") == "alias":
        main_entity = G.nodes[query_node]["properties"]["alias_of"]
        print(f"  → It's an alias, main entity is: {main_entity}")
        
        # Get all relations of main entity
        print(f"  → Relations of main entity:")
        for _, tail_id, data in G.out_edges(main_entity, data=True):
            relation = data.get("relation", "unknown")
            tail_name = G.nodes[tail_id]["properties"].get("name", tail_id)
            print(f"      • {relation} → {tail_name}")
    
    # Query 2: Find all aliases for a main entity
    print("\nQuery 2: Get all aliases for '流动伪影' (entity_361)")
    query_node = "entity_361"
    
    aliases = G.nodes[query_node]["properties"].get("aliases", [])
    print(f"  → Found {len(aliases)} aliases:")
    for alias_info in aliases:
        print(f"      • {alias_info['alias_name']} (confidence: {alias_info['confidence']})")
    
    # Query 3: Expanded search (include aliases)
    print("\nQuery 3: Search for entities related to 'MRI伪影' or its aliases")
    target_entity = "entity_361"  # 流动伪影
    
    # Find all entities that can refer to this concept
    all_names = [G.nodes[target_entity]["properties"]["name"]]
    for alias_info in G.nodes[target_entity]["properties"].get("aliases", []):
        all_names.append(alias_info["alias_name"])
    
    print(f"  → This entity can be referred to as: {', '.join(all_names)}")
    print(f"  → Relations:")
    for _, tail_id, data in G.out_edges(target_entity, data=True):
        if data.get("relation") != "alias_of":
            relation = data.get("relation", "unknown")
            tail_name = G.nodes[tail_id]["properties"].get("name", tail_id)
            print(f"      • {relation} → {tail_name}")


def demonstrate_statistics(G):
    """
    Show statistics comparing traditional vs alias approach.
    """
    print("\n" + "="*70)
    print("STATISTICS COMPARISON:")
    print("="*70)
    
    total_nodes = G.number_of_nodes()
    alias_nodes = len([
        n for n in G.nodes() 
        if G.nodes[n]["properties"].get("node_role") == "alias"
    ])
    main_nodes = total_nodes - alias_nodes
    total_edges = G.number_of_edges()
    alias_edges = len([
        e for e in G.edges(data=True)
        if e[2].get("relation") == "alias_of"
    ])
    regular_edges = total_edges - alias_edges
    
    print("\nTraditional Approach (hypothetical):")
    print(f"  - Total nodes: 3 (1 merged away)")
    print(f"  - Total edges: 3")
    print(f"  - Self-loops: 1 ✗")
    print(f"  - Alias information: Hidden in metadata")
    
    print("\nAlias Approach (actual):")
    print(f"  - Total nodes: {total_nodes} (all preserved)")
    print(f"  - Main entities: {main_nodes}")
    print(f"  - Alias entities: {alias_nodes}")
    print(f"  - Total edges: {total_edges}")
    print(f"  - Regular edges: {regular_edges}")
    print(f"  - Alias edges: {alias_edges}")
    print(f"  - Self-loops: 0 ✓")
    print(f"  - Alias information: Explicit in graph structure")


def main():
    """
    Run all demonstrations.
    """
    print("\n")
    print("╔" + "═"*68 + "╗")
    print("║" + " "*10 + "HEAD DEDUPLICATION: ALIAS APPROACH DEMO" + " "*19 + "║")
    print("╚" + "═"*68 + "╝")
    
    # Part 1: Show the problem
    G_original = create_test_graph_with_alias_issue()
    demonstrate_traditional_problem(G_original)
    
    # Part 2: Show the solution
    G_improved = demonstrate_alias_approach()
    
    # Part 3: Query examples
    demonstrate_query_with_aliases(G_improved)
    
    # Part 4: Statistics
    demonstrate_statistics(G_improved)
    
    print("\n" + "="*70)
    print("CONCLUSION:")
    print("="*70)
    print("""
The alias approach provides:
✓ No self-loops (graph integrity maintained)
✓ Explicit alias relationships (semantic correctness)
✓ Query-friendly (can find entities by any alias)
✓ Information preservation (no data loss)
✓ Better alignment with LLM's semantic understanding

Recommended for production use!
""")


if __name__ == "__main__":
    main()
