#!/usr/bin/env python3
"""
Example script demonstrating how to use apply_tail_dedup_results.py

This example shows:
1. How to prepare your dedup_results data
2. How to apply the deduplication to your graph
3. How to verify the results
"""

import json
from pathlib import Path

# Example of dedup_results structure
# This is what you would get from semantic_dedup_group processing
example_dedup_results = [
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
                    "延长TE值 (chunk id: Dwjxk2M8) [entity]"
                ],
                "llm_judge_reason": "三条尾巴均指"延长回波时间（TE）"这一完全相同的成像参数调整操作，只是表述略有差异（"延长TE值""增加TE值""延长TE"）。它们在任何上下文中可互相替换而不丢失信息，均用于减轻魔角伪影，故为同一实体。"
            },
            "cluster_1": {
                "member": [
                    "改变体位 (chunk id: IwfMagF6) [entity]",
                    "改变扫描体位 (chunk id: Dwjxk2M8) [entity]"
                ],
                "llm_judge_reason": ""改变扫描体位"与"改变体位"指代同一操作：通过调整患者体位来改变纤维组织长轴与主磁场的夹角，从而减轻魔角效应。两者在语境中可互换，无信息差异，故为同一实体。"
            }
        },
        "deduped_tails": [
            "改变扫描体位 (chunk id: Dwjxk2M8) [entity]",
            "延长TE值 (chunk id: Dwjxk2M8) [entity]"
        ]
    },
    # Add more dedup groups here...
]


def create_example_dedup_file():
    """Create an example deduplication results file."""
    output_path = Path("example_tail_dedup_results.json")
    
    with output_path.open('w', encoding='utf-8') as f:
        json.dump(example_dedup_results, f, ensure_ascii=False, indent=2)
    
    print(f"Created example dedup results file: {output_path}")
    return output_path


def main():
    """
    Main example workflow.
    
    Steps:
    1. Create example dedup results file
    2. Show command to apply deduplication
    3. Explain the output
    """
    print("=" * 60)
    print("Example: Applying Tail Deduplication Results")
    print("=" * 60)
    print()
    
    # Step 1: Create example file
    print("Step 1: Create dedup results file")
    print("-" * 60)
    dedup_file = create_example_dedup_file()
    print()
    
    # Step 2: Show usage
    print("Step 2: Apply deduplication to your graph")
    print("-" * 60)
    print("Command:")
    print(f"""
    python apply_tail_dedup_results.py \\
        --graph output/graphs/original.json \\
        --dedup-results {dedup_file} \\
        --output output/graphs/deduped.json
    """)
    print()
    
    # Step 3: Explain what happens
    print("Step 3: What the script does")
    print("-" * 60)
    print("""
    The script will:
    
    1. Build Mapping:
       - For each cluster in dedup_results
       - Map all members to the LAST member (representative)
       - Example: cluster_0 members all map to "延长TE值 (chunk id: Dwjxk2M8) [entity]"
    
    2. Update Triples (Edges):
       - For each edge in the graph
       - If tail node is in a cluster, replace with representative
       - Remove duplicate edges
    
    3. Update Communities:
       - For each community node
       - Replace member nodes with their representatives
       - Deduplicate members that map to the same representative
    
    4. Update keyword_filter_by Relations:
       - Similar to regular edges
       - Special handling for keyword filtering relationships
    
    5. Clean Up:
       - Remove isolated nodes (nodes with no edges)
       - Report statistics
    """)
    print()
    
    # Step 4: Expected output
    print("Step 4: Expected output")
    print("-" * 60)
    print("""
    You will see statistics like:
    
    Deduplication Statistics:
      Total clusters processed: 2
      Total members in clusters: 5
      Edges updated: 3
      Communities updated: 1
      Community members deduplicated: 2
      Keyword_filter_by relations updated: 0
      Isolated nodes removed: 2
      Graph size: 100 → 98 nodes (2 removed)
      Graph edges: 150 → 147 edges (3 removed)
    """)
    print()
    
    # Step 5: Verification
    print("Step 5: Verify the results")
    print("-" * 60)
    print("""
    To verify the deduplication worked correctly:
    
    1. Check the output file size (should be smaller)
    2. Look for the representative nodes in the output graph
    3. Verify that cluster members no longer appear as separate entities
    4. Check that community memberships are correct
    
    Example verification code:
    
    import json
    from utils import graph_processor
    
    # Load deduplicated graph
    graph = graph_processor.load_graph_from_json('output/graphs/deduped.json')
    
    # Check if representative node exists
    for node_id, data in graph.nodes(data=True):
        props = data.get('properties', {})
        if props.get('name') == '延长TE值' and props.get('chunk id') == 'Dwjxk2M8':
            print(f"Found representative node: {node_id}")
            print(f"  Degree: {graph.degree(node_id)}")
            print(f"  Successors: {list(graph.successors(node_id))}")
            print(f"  Predecessors: {list(graph.predecessors(node_id))}")
    """)
    print()
    
    print("=" * 60)
    print("Example complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
