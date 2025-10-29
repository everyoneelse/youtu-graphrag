# Tail Deduplication Application Guide

## Overview

This guide explains how to apply tail deduplication results to your knowledge graph after using `semantic_dedup_group` processing.

## Background

When processing a knowledge graph with shared head/relation pairs, you may have used `semantic_dedup_group` to deduplicate the tail nodes. This process produces a `dedup_results` structure that needs to be applied to the original graph to replace cluster members with their representatives.

## Dedup Results Format

Your deduplication results should be a JSON list with the following structure:

```json
[
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
        "llm_judge_reason": "三条尾巴均指"延长回波时间（TE）"..."
      },
      "cluster_1": {
        "member": [
          "改变体位 (chunk id: IwfMagF6) [entity]",
          "改变扫描体位 (chunk id: Dwjxk2M8) [entity]"
        ],
        "llm_judge_reason": ""改变扫描体位"与"改变体位"..."
      }
    },
    "deduped_tails": [
      "改变扫描体位 (chunk id: Dwjxk2M8) [entity]",
      "延长TE值 (chunk id: Dwjxk2M8) [entity]"
    ]
  }
]
```

## Key Concepts

### Representative Selection

For each cluster, **the LAST member in the cluster's member list is used as the representative**. All other members in the cluster will be replaced with this representative.

Example:
- Cluster members: `["增加TE值", "延长TE", "延长TE值"]`
- Representative: `"延长TE值"` (the last one)

### Graph Structures Handled

The deduplication process handles three types of graph structures:

1. **Regular Triples (Edges)**: Normal head→relation→tail relationships
2. **Communities**: Groups of related entities that may contain cluster members
3. **keyword_filter_by Relations**: Special keyword filtering relationships

### Special Considerations

#### Community Deduplication

When multiple members of a cluster belong to the same community:
- All are replaced with the representative
- The community membership list is deduplicated
- Only one instance of the representative remains in the community

#### Duplicate Prevention

The script ensures no duplicate edges are created:
- Before adding an edge with the representative, it checks if it already exists
- Existing edges with the same (head, relation, representative) are preserved
- Only the redundant edges are removed

## Usage

### Basic Command

```bash
python apply_tail_dedup_results.py \
    --graph output/graphs/original.json \
    --dedup-results tail_dedup_results.json \
    --output output/graphs/deduped.json
```

### Parameters

- `--graph`: Path to your original knowledge graph JSON file
- `--dedup-results`: Path to your deduplication results JSON file
- `--output`: Path where the deduplicated graph will be saved

### Example Workflow

1. **Prepare your dedup results**:
   ```python
   import json
   
   # Your dedup_results from semantic_dedup_group
   with open('tail_dedup_results.json', 'w', encoding='utf-8') as f:
       json.dump(dedup_results, f, ensure_ascii=False, indent=2)
   ```

2. **Run the deduplication**:
   ```bash
   python apply_tail_dedup_results.py \
       --graph output/graphs/my_graph.json \
       --dedup-results tail_dedup_results.json \
       --output output/graphs/my_graph_deduped.json
   ```

3. **Review the statistics**:
   ```
   Deduplication Statistics:
     Total clusters processed: 10
     Total members in clusters: 35
     Edges updated: 25
     Communities updated: 5
     Community members deduplicated: 8
     Keyword_filter_by relations updated: 2
     Isolated nodes removed: 7
     Graph size: 200 → 193 nodes (7 removed)
     Graph edges: 350 → 325 edges (25 removed)
   ```

## How It Works

### Step 1: Build Mapping

```python
# For each cluster
for cluster in dedup_results:
    members = cluster['member']
    representative = members[-1]  # Last member
    
    # Map all members to representative
    for member in members:
        mapping[member] = representative
```

### Step 2: Apply to Edges

```python
# For each edge (u, v, relation)
for edge in graph.edges():
    v_representative = get_representative(v)
    
    if v_representative != v:
        # Replace edge: (u, relation, v) → (u, relation, v_representative)
        if not edge_exists(u, relation, v_representative):
            add_edge(u, relation, v_representative)
        remove_edge(u, relation, v)
```

### Step 3: Apply to Communities

```python
# For each community
for community in communities:
    # Get all members of the community
    members = get_community_members(community)
    
    # Replace each member with its representative
    for member in members:
        representative = get_representative(member)
        
        if representative != member:
            # Update community membership
            if not is_member(community, representative):
                add_member(community, representative)
            remove_member(community, member)
```

### Step 4: Clean Up

```python
# Remove isolated nodes
for node in graph.nodes():
    if graph.degree(node) == 0:
        graph.remove_node(node)
```

## Verification

### Check Node Counts

```python
import json
from utils import graph_processor

# Load original and deduplicated graphs
original = graph_processor.load_graph_from_json('output/graphs/original.json')
deduped = graph_processor.load_graph_from_json('output/graphs/deduped.json')

print(f"Original nodes: {original.number_of_nodes()}")
print(f"Deduped nodes: {deduped.number_of_nodes()}")
print(f"Nodes removed: {original.number_of_nodes() - deduped.number_of_nodes()}")
```

### Check Specific Nodes

```python
# Find a specific representative node
def find_node(graph, name, chunk_id):
    for node_id, data in graph.nodes(data=True):
        props = data.get('properties', {})
        if props.get('name') == name and props.get('chunk id') == chunk_id:
            return node_id, data
    return None, None

# Check if representative exists
node_id, data = find_node(deduped, '延长TE值', 'Dwjxk2M8')
if node_id:
    print(f"Found representative: {node_id}")
    print(f"Degree: {deduped.degree(node_id)}")
else:
    print("Representative not found!")
```

### Verify Cluster Members Removed

```python
# Check that cluster members (except representative) are removed
cluster_members = [
    ("增加TE值", "PHuCr1nf"),
    ("延长TE", "IwfMagF6"),
]

for name, chunk_id in cluster_members:
    node_id, _ = find_node(deduped, name, chunk_id)
    if node_id:
        print(f"WARNING: Member {name} still exists (should be removed)")
    else:
        print(f"✓ Member {name} correctly removed")
```

## Common Issues

### Issue 1: Representative Not Found

**Symptom**: Warning messages like "Representative node not found for X -> Y"

**Cause**: The representative node doesn't exist in the graph

**Solution**: 
- Check that your graph contains all representative nodes
- Verify the node identifier format matches exactly
- Ensure chunk IDs and names are correct

### Issue 2: No Changes Applied

**Symptom**: Statistics show 0 edges/communities updated

**Cause**: Node identifiers don't match between dedup results and graph

**Solution**:
- Verify the format of node identifiers in your dedup results
- Check that chunk IDs match exactly (including whitespace)
- Ensure label types match (entity, keyword, etc.)

### Issue 3: Duplicate Edges After Deduplication

**Symptom**: Multiple edges with same (head, relation, tail) after deduplication

**Cause**: Graph already had duplicate edges before deduplication

**Solution**:
- This is expected and harmless (MultiDiGraph allows duplicates)
- Use NetworkX's `number_of_edges()` to count actual edge instances
- Post-process to remove duplicates if needed:
  ```python
  # Remove duplicate edges (keep one)
  edges_seen = set()
  edges_to_remove = []
  
  for u, v, key, data in graph.edges(keys=True, data=True):
      edge_sig = (u, v, data.get('relation'))
      if edge_sig in edges_seen:
          edges_to_remove.append((u, v, key))
      else:
          edges_seen.add(edge_sig)
  
  for u, v, key in edges_to_remove:
      graph.remove_edge(u, v, key)
  ```

## Advanced Usage

### Custom Representative Selection

By default, the script uses the **last member** as representative. To use a different strategy:

```python
# Modify the TailDedupApplicator class
class CustomTailDedupApplicator(TailDedupApplicator):
    def build_mapping_from_dedup_results(self, dedup_results):
        for group in dedup_results:
            for cluster_name, cluster_data in group['dedup_results'].items():
                members = cluster_data['member']
                
                # Use first member instead of last
                representative = members[0]
                
                # Or use most frequent (requires additional data)
                # representative = self._select_most_frequent(members)
                
                for member in members:
                    self.node_mapping[member] = representative
```

### Batch Processing

Process multiple graphs at once:

```python
import glob
from pathlib import Path
from apply_tail_dedup_results import TailDedupApplicator
from utils import graph_processor

dedup_results = load_dedup_results('dedup_results.json')

for graph_file in glob.glob('output/graphs/*.json'):
    graph_path = Path(graph_file)
    output_path = graph_path.parent / f"{graph_path.stem}_deduped.json"
    
    graph = graph_processor.load_graph_from_json(str(graph_path))
    applicator = TailDedupApplicator(graph)
    stats = applicator.apply_all(dedup_results)
    
    graph_processor.save_graph_to_json(graph, str(output_path))
    print(f"Processed {graph_file}: {stats['edges_updated']} edges updated")
```

### Integration with Offline Dedup

Use together with offline semantic dedup:

```bash
# Step 1: Run semantic dedup to get intermediate results
python offline_semantic_dedup.py \
    --graph output/graphs/original.json \
    --chunks output/chunks/ \
    --output output/graphs/semantic_deduped.json

# Step 2: Apply tail dedup results (if you have custom tail dedup)
python apply_tail_dedup_results.py \
    --graph output/graphs/semantic_deduped.json \
    --dedup-results tail_dedup_results.json \
    --output output/graphs/fully_deduped.json
```

## Performance Considerations

- **Large Graphs**: For graphs with >100K nodes, consider processing in batches
- **Memory**: The script loads the entire graph into memory
- **Time Complexity**: O(E) where E is the number of edges

## Summary

The `apply_tail_dedup_results.py` script provides a robust way to apply tail deduplication results to your knowledge graph. It handles:

- ✅ Regular triples (edges)
- ✅ Communities with duplicate members
- ✅ Special keyword_filter_by relations
- ✅ Duplicate prevention
- ✅ Isolated node cleanup
- ✅ Detailed statistics

Use this script after running `semantic_dedup_group` to consolidate your graph and reduce redundancy while preserving all important relationships.
