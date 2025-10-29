#!/usr/bin/env python3
"""
Test script for apply_tail_dedup_results.py

Creates a minimal test case to verify the deduplication logic works correctly.
"""

import json
import tempfile
from pathlib import Path

import networkx as nx

from apply_tail_dedup_results import TailDedupApplicator
from utils import graph_processor


def create_test_graph() -> nx.MultiDiGraph:
    """
    Create a test graph with duplicate tail nodes.
    
    Structure:
    - 魔角效应 --解决方案为--> 延长TE值 (chunk: Dwjxk2M8)
    - 魔角效应 --解决方案为--> 增加TE值 (chunk: PHuCr1nf)  [should map to 延长TE值]
    - 魔角效应 --解决方案为--> 延长TE (chunk: IwfMagF6)      [should map to 延长TE值]
    - 魔角效应 --解决方案为--> 改变扫描体位 (chunk: Dwjxk2M8)
    - 魔角效应 --解决方案为--> 改变体位 (chunk: IwfMagF6)    [should map to 改变扫描体位]
    - Community_0 <-- 延长TE值, 增加TE值, 延长TE (all should deduplicate)
    """
    graph = nx.MultiDiGraph()
    
    # Add head node
    graph.add_node('entity_0', 
                   label='entity',
                   level=2,
                   properties={'name': '魔角效应', 'chunk id': 'Dwjxk2M8', 'schema_type': 'MRI伪影'})
    
    # Add tail nodes
    graph.add_node('entity_1',
                   label='entity',
                   level=2,
                   properties={'name': '延长TE值', 'chunk id': 'Dwjxk2M8'})
    
    graph.add_node('entity_2',
                   label='entity',
                   level=2,
                   properties={'name': '增加TE值', 'chunk id': 'PHuCr1nf'})
    
    graph.add_node('entity_3',
                   label='entity',
                   level=2,
                   properties={'name': '延长TE', 'chunk id': 'IwfMagF6'})
    
    graph.add_node('entity_4',
                   label='entity',
                   level=2,
                   properties={'name': '改变扫描体位', 'chunk id': 'Dwjxk2M8'})
    
    graph.add_node('entity_5',
                   label='entity',
                   level=2,
                   properties={'name': '改变体位', 'chunk id': 'IwfMagF6'})
    
    # Add edges from head to tails
    graph.add_edge('entity_0', 'entity_1', relation='解决方案为')
    graph.add_edge('entity_0', 'entity_2', relation='解决方案为')
    graph.add_edge('entity_0', 'entity_3', relation='解决方案为')
    graph.add_edge('entity_0', 'entity_4', relation='解决方案为')
    graph.add_edge('entity_0', 'entity_5', relation='解决方案为')
    
    # Add community node
    graph.add_node('community_0',
                   label='community',
                   level=4,
                   properties={'name': 'TE调整方法社区', 'description': 'TE相关解决方案'})
    
    # Add edges from tail nodes to community
    graph.add_edge('entity_1', 'community_0', relation='belongs_to')
    graph.add_edge('entity_2', 'community_0', relation='belongs_to')
    graph.add_edge('entity_3', 'community_0', relation='belongs_to')
    
    return graph


def create_test_dedup_results() -> list:
    """Create test deduplication results matching the test graph."""
    return [
        {
            "head_node": {
                "label": "entity",
                "properties": {
                    "name": "魔角效应",
                    "chunk id": "Dwjxk2M8",
                    "schema_type": "MRI伪影"
                }
            },
            "relation": "解决方案为",
            "tail_nodes_to_dedup": [
                "延长TE值 (chunk id: Dwjxk2M8) [entity]",
                "改变扫描体位 (chunk id: Dwjxk2M8) [entity]",
                "增加TE值 (chunk id: PHuCr1nf) [entity]",
                "延长TE (chunk id: IwfMagF6) [entity]",
                "改变体位 (chunk id: IwfMagF6) [entity]"
            ],
            "dedup_results": {
                "cluster_0": {
                    "member": [
                        "增加TE值 (chunk id: PHuCr1nf) [entity]",
                        "延长TE (chunk id: IwfMagF6) [entity]",
                        "延长TE值 (chunk id: Dwjxk2M8) [entity]"  # This is the representative
                    ],
                    "llm_judge_reason": "三条尾巴均指延长回波时间(TE)这一完全相同的成像参数调整操作。"
                },
                "cluster_1": {
                    "member": [
                        "改变体位 (chunk id: IwfMagF6) [entity]",
                        "改变扫描体位 (chunk id: Dwjxk2M8) [entity]"  # This is the representative
                    ],
                    "llm_judge_reason": "改变扫描体位与改变体位指代同一操作。"
                }
            },
            "deduped_tails": [
                "改变扫描体位 (chunk id: Dwjxk2M8) [entity]",
                "延长TE值 (chunk id: Dwjxk2M8) [entity]"
            ]
        }
    ]


def verify_deduplication(graph: nx.MultiDiGraph, original_graph: nx.MultiDiGraph) -> bool:
    """
    Verify that deduplication was applied correctly.
    
    Returns:
        True if all checks pass, False otherwise
    """
    all_passed = True
    
    print("\n" + "=" * 60)
    print("VERIFICATION RESULTS")
    print("=" * 60)
    
    # Check 1: Graph should have fewer nodes
    original_nodes = original_graph.number_of_nodes()
    deduped_nodes = graph.number_of_nodes()
    print(f"\n1. Node count: {original_nodes} → {deduped_nodes}")
    if deduped_nodes < original_nodes:
        print("   ✓ PASS: Nodes reduced")
    else:
        print("   ✗ FAIL: Nodes not reduced")
        all_passed = False
    
    # Check 2: Graph should have fewer edges
    original_edges = original_graph.number_of_edges()
    deduped_edges = graph.number_of_edges()
    print(f"\n2. Edge count: {original_edges} → {deduped_edges}")
    if deduped_edges < original_edges:
        print("   ✓ PASS: Edges reduced")
    else:
        print("   ✗ FAIL: Edges not reduced")
        all_passed = False
    
    # Check 3: Representatives should exist
    print("\n3. Checking representatives exist:")
    representatives = [
        ('延长TE值', 'Dwjxk2M8', 'entity'),
        ('改变扫描体位', 'Dwjxk2M8', 'entity'),
    ]
    
    for name, chunk_id, label in representatives:
        found = False
        for node_id, data in graph.nodes(data=True):
            props = data.get('properties', {})
            if (props.get('name') == name and 
                props.get('chunk id') == chunk_id and 
                data.get('label') == label):
                found = True
                print(f"   ✓ Found: {name} (chunk: {chunk_id})")
                break
        
        if not found:
            print(f"   ✗ Missing: {name} (chunk: {chunk_id})")
            all_passed = False
    
    # Check 4: Cluster members (except representatives) should be removed
    print("\n4. Checking cluster members removed:")
    removed_members = [
        ('增加TE值', 'PHuCr1nf', 'entity'),
        ('延长TE', 'IwfMagF6', 'entity'),
        ('改变体位', 'IwfMagF6', 'entity'),
    ]
    
    for name, chunk_id, label in removed_members:
        found = False
        for node_id, data in graph.nodes(data=True):
            props = data.get('properties', {})
            if (props.get('name') == name and 
                props.get('chunk id') == chunk_id and 
                data.get('label') == label):
                found = True
                print(f"   ✗ Still exists: {name} (chunk: {chunk_id})")
                all_passed = False
                break
        
        if not found:
            print(f"   ✓ Removed: {name} (chunk: {chunk_id})")
    
    # Check 5: Head node should have correct number of outgoing edges
    print("\n5. Checking head node edges:")
    head_node = None
    for node_id, data in graph.nodes(data=True):
        props = data.get('properties', {})
        if props.get('name') == '魔角效应':
            head_node = node_id
            break
    
    if head_node:
        out_degree = graph.out_degree(head_node)
        print(f"   Head node '魔角效应' has {out_degree} outgoing edges")
        # Should have 2 edges after dedup (one to each representative)
        if out_degree == 2:
            print("   ✓ PASS: Correct number of edges")
        else:
            print(f"   ✗ FAIL: Expected 2 edges, got {out_degree}")
            all_passed = False
    else:
        print("   ✗ FAIL: Head node not found")
        all_passed = False
    
    # Check 6: Community should have only one member (the representative)
    print("\n6. Checking community membership:")
    community_node = None
    for node_id, data in graph.nodes(data=True):
        if data.get('label') == 'community':
            community_node = node_id
            break
    
    if community_node:
        # Count predecessors (entities belonging to community)
        predecessors = list(graph.predecessors(community_node))
        print(f"   Community has {len(predecessors)} members")
        
        # Should have only 1 member after dedup (the representative)
        if len(predecessors) == 1:
            print("   ✓ PASS: Community deduplicated correctly")
            
            # Verify it's the correct representative
            for pred in predecessors:
                pred_data = graph.nodes[pred]
                props = pred_data.get('properties', {})
                name = props.get('name')
                chunk_id = props.get('chunk id')
                print(f"   Member: {name} (chunk: {chunk_id})")
                
                if name == '延长TE值' and chunk_id == 'Dwjxk2M8':
                    print("   ✓ PASS: Correct representative in community")
                else:
                    print("   ✗ FAIL: Wrong member in community")
                    all_passed = False
        else:
            print(f"   ✗ FAIL: Expected 1 member, got {len(predecessors)}")
            all_passed = False
    else:
        print("   ✗ FAIL: Community node not found")
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("=" * 60 + "\n")
    
    return all_passed


def main():
    """Run the test."""
    print("=" * 60)
    print("Testing Tail Deduplication Application")
    print("=" * 60)
    
    # Create test graph
    print("\nCreating test graph...")
    graph = create_test_graph()
    original_graph = graph.copy()
    print(f"  Nodes: {graph.number_of_nodes()}")
    print(f"  Edges: {graph.number_of_edges()}")
    
    # Create test dedup results
    print("\nCreating test dedup results...")
    dedup_results = create_test_dedup_results()
    print(f"  Dedup groups: {len(dedup_results)}")
    print(f"  Total clusters: {sum(len(g['dedup_results']) for g in dedup_results)}")
    
    # Apply deduplication
    print("\nApplying deduplication...")
    applicator = TailDedupApplicator(graph)
    stats = applicator.apply_all(dedup_results)
    
    # Print statistics
    print("\nDeduplication Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Verify results
    success = verify_deduplication(graph, original_graph)
    
    # Save test results to temp files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Save original graph
        original_path = tmpdir / "original_test_graph.json"
        graph_processor.save_graph_to_json(original_graph, str(original_path))
        print(f"\nSaved original graph to: {original_path}")
        
        # Save deduplicated graph
        deduped_path = tmpdir / "deduped_test_graph.json"
        graph_processor.save_graph_to_json(graph, str(deduped_path))
        print(f"Saved deduplicated graph to: {deduped_path}")
        
        # Save dedup results
        dedup_results_path = tmpdir / "test_dedup_results.json"
        with dedup_results_path.open('w', encoding='utf-8') as f:
            json.dump(dedup_results, f, ensure_ascii=False, indent=2)
        print(f"Saved dedup results to: {dedup_results_path}")
        
        print(f"\nFiles saved in: {tmpdir}")
        print("(They will be deleted when script exits)")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
