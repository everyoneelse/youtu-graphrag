#!/usr/bin/env python3
"""
Apply tail deduplication results to the original knowledge graph.

This script takes deduplication results from semantic_dedup_group processing
and applies them to the graph by replacing all cluster members with their 
representative (the last member in each cluster).

Usage:
    python apply_tail_dedup_results.py \
        --graph output/graphs/original.json \
        --dedup-results tail_dedup_results.json \
        --output output/graphs/deduped.json
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict

import networkx as nx

from utils import graph_processor
from utils.logger import logger


class TailDedupApplicator:
    """Apply tail deduplication results to a knowledge graph."""
    
    def __init__(self, graph: nx.MultiDiGraph):
        self.graph = graph
        # Mapping from node identifier string to its representative
        self.node_mapping: Dict[str, str] = {}
        # Statistics
        self.stats = {
            'total_clusters': 0,
            'total_members': 0,
            'edges_updated': 0,
            'communities_updated': 0,
            'community_members_deduplicated': 0,
            'keyword_filter_relations_updated': 0,
        }
    
    def _parse_node_identifier(self, node_str: str) -> Tuple[str, str, str]:
        """
        Parse node identifier string into (name, chunk_id, label).
        
        Format: "name (chunk id: xxx) [label]"
        Example: "延长TE值 (chunk id: Dwjxk2M8) [entity]"
        
        Returns:
            Tuple of (name, chunk_id, label)
        """
        # Extract label (last part in brackets)
        if '[' in node_str and ']' in node_str:
            label_start = node_str.rfind('[')
            label_end = node_str.rfind(']')
            label = node_str[label_start+1:label_end].strip()
            remaining = node_str[:label_start].strip()
        else:
            label = ""
            remaining = node_str
        
        # Extract chunk_id
        if '(chunk id:' in remaining:
            chunk_start = remaining.find('(chunk id:')
            chunk_end = remaining.find(')', chunk_start)
            chunk_id = remaining[chunk_start+10:chunk_end].strip()
            name = remaining[:chunk_start].strip()
        else:
            chunk_id = ""
            name = remaining
        
        return name, chunk_id, label
    
    def _find_node_by_identifier(self, node_str: str) -> str | None:
        """
        Find a node in the graph by its identifier string.
        
        Returns the node ID if found, None otherwise.
        """
        name, chunk_id, label = self._parse_node_identifier(node_str)
        
        # Search for matching node in the graph
        for node_id, node_data in self.graph.nodes(data=True):
            if node_data.get('label') != label:
                continue
            
            props = node_data.get('properties', {})
            node_name = props.get('name', '')
            node_chunk_id = props.get('chunk id', '')
            
            if node_name == name and node_chunk_id == chunk_id:
                return node_id
        
        return None
    
    def build_mapping_from_dedup_results(self, dedup_results: List[Dict]) -> None:
        """
        Build mapping from cluster members to representatives.
        
        Args:
            dedup_results: List of deduplication result dictionaries, each containing:
                - head_node: The head node info
                - relation: The relation
                - tail_nodes_to_dedup: List of tail node identifiers
                - dedup_results: Dict of clusters with members
                - deduped_tails: List of final representative tails
        """
        logger.info("Building node mapping from deduplication results...")
        
        for group in dedup_results:
            dedup_clusters = group.get('dedup_results', {})
            
            for cluster_name, cluster_data in dedup_clusters.items():
                members = cluster_data.get('member', [])
                
                if not members:
                    continue
                
                # Use the LAST member as the representative
                representative = members[-1]
                
                # Map all members to the representative
                for member in members:
                    self.node_mapping[member] = representative
                    
                self.stats['total_clusters'] += 1
                self.stats['total_members'] += len(members)
        
        logger.info(f"Built mapping with {self.stats['total_clusters']} clusters and {self.stats['total_members']} total members")
        logger.info(f"Mapping entries: {len(self.node_mapping)}")
    
    def _get_representative(self, node_id: str) -> str:
        """
        Get the representative node ID for a given node.
        
        If the node is part of a dedup cluster, return its representative.
        Otherwise, return the node itself.
        """
        # First, get the node identifier string for this node_id
        node_data = self.graph.nodes.get(node_id)
        if not node_data:
            return node_id
        
        props = node_data.get('properties', {})
        name = props.get('name', '')
        chunk_id = props.get('chunk id', '')
        label = node_data.get('label', '')
        
        # Construct identifier string
        if chunk_id:
            node_str = f"{name} (chunk id: {chunk_id}) [{label}]"
        else:
            node_str = f"{name} [{label}]"
        
        # Check if this node has a mapping
        if node_str not in self.node_mapping:
            return node_id
        
        # Get representative identifier
        rep_str = self.node_mapping[node_str]
        
        # If representative is same as current, no change needed
        if rep_str == node_str:
            return node_id
        
        # Find the representative node in the graph
        rep_node_id = self._find_node_by_identifier(rep_str)
        
        if rep_node_id is None:
            logger.warning(f"Representative node not found for {node_str} -> {rep_str}, keeping original")
            return node_id
        
        return rep_node_id
    
    def apply_to_edges(self) -> None:
        """
        Apply deduplication mapping to all edges (triples) in the graph.
        
        For each edge, if the target (tail) node should be replaced,
        create a new edge with the representative and remove the old one.
        """
        logger.info("Applying deduplication to edges...")
        
        edges_to_add = []
        edges_to_remove = []
        
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            # Get representative for the tail node
            v_rep = self._get_representative(v)
            
            # If tail should be replaced
            if v_rep != v:
                relation = data.get('relation', '')
                
                # Check if edge with representative already exists
                edge_exists = False
                if self.graph.has_edge(u, v_rep):
                    for edge_key, edge_data in self.graph[u][v_rep].items():
                        if edge_data.get('relation') == relation:
                            edge_exists = True
                            break
                
                if not edge_exists:
                    edges_to_add.append((u, v_rep, data))
                
                edges_to_remove.append((u, v, key))
                self.stats['edges_updated'] += 1
        
        # Apply changes
        for u, v, key in edges_to_remove:
            self.graph.remove_edge(u, v, key)
        
        for u, v, data in edges_to_add:
            self.graph.add_edge(u, v, **data)
        
        logger.info(f"Updated {self.stats['edges_updated']} edges")
    
    def apply_to_communities(self) -> None:
        """
        Apply deduplication mapping to community nodes.
        
        Community nodes may contain member lists that need deduplication.
        Multiple members in a cluster might all be in the same community,
        so we need to deduplicate the member list.
        """
        logger.info("Applying deduplication to communities...")
        
        for node_id, node_data in list(self.graph.nodes(data=True)):
            if node_data.get('label') != 'community':
                continue
            
            # Check if community has incoming edges that need updating
            updated = False
            members_deduplicated = 0
            
            # Get all nodes that point to this community
            predecessors = list(self.graph.predecessors(node_id))
            
            # Build a set of representative predecessors
            representative_preds = set()
            preds_to_remove = []
            edges_to_add = []
            
            for pred in predecessors:
                pred_rep = self._get_representative(pred)
                
                if pred_rep != pred:
                    # Check what relation(s) connect pred to community
                    for key, edge_data in self.graph[pred][node_id].items():
                        relation = edge_data.get('relation', '')
                        
                        # Check if representative already has this relation to community
                        edge_exists = False
                        if self.graph.has_edge(pred_rep, node_id):
                            for edge_key, rep_edge_data in self.graph[pred_rep][node_id].items():
                                if rep_edge_data.get('relation') == relation:
                                    edge_exists = True
                                    break
                        
                        if not edge_exists:
                            edges_to_add.append((pred_rep, node_id, edge_data))
                        
                        preds_to_remove.append((pred, node_id, key))
                        members_deduplicated += 1
                        updated = True
                
                representative_preds.add(pred_rep)
            
            # Apply changes
            for u, v, key in preds_to_remove:
                if self.graph.has_edge(u, v):
                    self.graph.remove_edge(u, v, key)
            
            for u, v, data in edges_to_add:
                self.graph.add_edge(u, v, **data)
            
            if updated:
                self.stats['communities_updated'] += 1
                self.stats['community_members_deduplicated'] += members_deduplicated
        
        logger.info(f"Updated {self.stats['communities_updated']} communities")
        logger.info(f"Deduplicated {self.stats['community_members_deduplicated']} community members")
    
    def apply_to_keyword_filter_relations(self) -> None:
        """
        Apply deduplication mapping to keyword_filter_by relations.
        
        These are special relations where keywords may point to entities
        that need to be deduplicated.
        """
        logger.info("Applying deduplication to keyword_filter_by relations...")
        
        edges_to_add = []
        edges_to_remove = []
        
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            relation = data.get('relation', '')
            
            if relation != 'keyword_filter_by':
                continue
            
            # Get representative for the tail node
            v_rep = self._get_representative(v)
            
            # If tail should be replaced
            if v_rep != v:
                # Check if edge with representative already exists
                edge_exists = False
                if self.graph.has_edge(u, v_rep):
                    for edge_key, edge_data in self.graph[u][v_rep].items():
                        if edge_data.get('relation') == 'keyword_filter_by':
                            edge_exists = True
                            break
                
                if not edge_exists:
                    edges_to_add.append((u, v_rep, data))
                
                edges_to_remove.append((u, v, key))
                self.stats['keyword_filter_relations_updated'] += 1
        
        # Apply changes
        for u, v, key in edges_to_remove:
            self.graph.remove_edge(u, v, key)
        
        for u, v, data in edges_to_add:
            self.graph.add_edge(u, v, **data)
        
        logger.info(f"Updated {self.stats['keyword_filter_relations_updated']} keyword_filter_by relations")
    
    def remove_isolated_nodes(self) -> int:
        """
        Remove nodes that have no incoming or outgoing edges after deduplication.
        
        Returns:
            Number of nodes removed
        """
        isolated = []
        for node_id in self.graph.nodes():
            if self.graph.degree(node_id) == 0:
                isolated.append(node_id)
        
        for node_id in isolated:
            self.graph.remove_node(node_id)
        
        if isolated:
            logger.info(f"Removed {len(isolated)} isolated nodes")
        
        return len(isolated)
    
    def apply_all(self, dedup_results: List[Dict]) -> Dict:
        """
        Apply all deduplication operations.
        
        Args:
            dedup_results: List of deduplication result dictionaries
        
        Returns:
            Statistics dictionary
        """
        # Build mapping
        self.build_mapping_from_dedup_results(dedup_results)
        
        # Apply to different parts of the graph
        self.apply_to_edges()
        self.apply_to_communities()
        self.apply_to_keyword_filter_relations()
        
        # Clean up isolated nodes
        isolated_count = self.remove_isolated_nodes()
        self.stats['isolated_nodes_removed'] = isolated_count
        
        return self.stats


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply tail deduplication results to knowledge graph"
    )
    parser.add_argument(
        "--graph",
        required=True,
        type=Path,
        help="Path to the input graph JSON file"
    )
    parser.add_argument(
        "--dedup-results",
        required=True,
        type=Path,
        help="Path to the tail deduplication results JSON file"
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path to save the deduplicated graph JSON"
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    
    # Load graph
    logger.info(f"Loading graph from {args.graph}")
    graph = graph_processor.load_graph_from_json(str(args.graph))
    
    original_nodes = graph.number_of_nodes()
    original_edges = graph.number_of_edges()
    logger.info(f"Original graph: {original_nodes} nodes, {original_edges} edges")
    
    # Load dedup results
    logger.info(f"Loading deduplication results from {args.dedup_results}")
    with args.dedup_results.open('r', encoding='utf-8') as f:
        dedup_results = json.load(f)
    
    if not isinstance(dedup_results, list):
        raise ValueError("Dedup results must be a list of deduplication groups")
    
    logger.info(f"Loaded {len(dedup_results)} deduplication groups")
    
    # Apply deduplication
    applicator = TailDedupApplicator(graph)
    stats = applicator.apply_all(dedup_results)
    
    final_nodes = graph.number_of_nodes()
    final_edges = graph.number_of_edges()
    
    # Print statistics
    logger.info("=" * 60)
    logger.info("Deduplication Statistics:")
    logger.info(f"  Total clusters processed: {stats['total_clusters']}")
    logger.info(f"  Total members in clusters: {stats['total_members']}")
    logger.info(f"  Edges updated: {stats['edges_updated']}")
    logger.info(f"  Communities updated: {stats['communities_updated']}")
    logger.info(f"  Community members deduplicated: {stats['community_members_deduplicated']}")
    logger.info(f"  Keyword_filter_by relations updated: {stats['keyword_filter_relations_updated']}")
    logger.info(f"  Isolated nodes removed: {stats['isolated_nodes_removed']}")
    logger.info(f"  Graph size: {original_nodes} → {final_nodes} nodes ({original_nodes - final_nodes} removed)")
    logger.info(f"  Graph edges: {original_edges} → {final_edges} edges ({original_edges - final_edges} removed)")
    logger.info("=" * 60)
    
    # Save deduplicated graph
    args.output.parent.mkdir(parents=True, exist_ok=True)
    graph_processor.save_graph_to_json(graph, str(args.output))
    logger.info(f"Deduplicated graph saved to {args.output}")


if __name__ == "__main__":
    main()
