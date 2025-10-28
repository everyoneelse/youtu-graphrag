"""Apply offline deduplication results to graph.json.

This script reads previously saved semantic dedup and keyword dedup results,
then applies them to the original graph.json by replacing duplicates with their
representatives.

Usage:
    python apply_dedup_results.py \
        --graph output/graphs/demo_new.json \
        --keyword-dedup output/dedup_intermediate/demo_dedup_*.json \
        --edge-dedup output/dedup_intermediate/demo_edge_dedup_*.json \
        --output output/graphs/demo_deduped.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict

import networkx as nx

from utils import graph_processor
from utils.logger import logger


class DedupResultsApplier:
    """Apply deduplication results to a graph."""

    def __init__(self):
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph()
        # 节点ID映射：duplicate -> representative
        self.node_mapping: Dict[str, str] = {}
        # 边映射：(head, relation, tail) -> representative_tail
        self.edge_mapping: Dict[tuple, str] = {}
        
    def load_keyword_dedup_results(self, results_file: Path) -> None:
        """Load keyword deduplication results and build node mapping."""
        logger.info(f"Loading keyword dedup results from {results_file}")
        
        with results_file.open("r", encoding="utf-8") as f:
            results = json.load(f)
        
        total_mappings = 0
        
        # 从communities中提取final_merges
        for community in results.get("communities", []):
            for merge in community.get("final_merges", []):
                representative = merge["representative"]
                duplicates = merge.get("duplicates", [])
                
                rep_id = representative["node_id"]
                
                # 将所有duplicate映射到representative
                for dup in duplicates:
                    dup_id = dup["node_id"]
                    self.node_mapping[dup_id] = rep_id
                    total_mappings += 1
                    
                    logger.debug(
                        f"Keyword mapping: {dup_id} ({dup.get('description', '')}) "
                        f"-> {rep_id} ({representative.get('description', '')})"
                    )
        
        logger.info(f"Loaded {total_mappings} keyword node mappings from {len(results.get('communities', []))} communities")
        
    def load_edge_dedup_results(self, results_file: Path) -> None:
        """Load edge/triple deduplication results and build edge mapping."""
        logger.info(f"Loading edge dedup results from {results_file}")
        
        with results_file.open("r", encoding="utf-8") as f:
            results = json.load(f)
        
        total_mappings = 0
        
        # 从triples中提取final_merges
        for triple in results.get("triples", []):
            head_id = triple["head_id"]
            relation = triple["relation"]
            
            for merge in triple.get("final_merges", []):
                representative = merge["representative"]
                duplicates = merge.get("duplicates", [])
                
                rep_tail_id = representative["node_id"]
                
                # 将所有duplicate tail映射到representative tail
                for dup in duplicates:
                    dup_tail_id = dup["node_id"]
                    # 使用(head, relation, tail)作为key
                    edge_key = (head_id, relation, dup_tail_id)
                    self.edge_mapping[edge_key] = rep_tail_id
                    total_mappings += 1
                    
                    logger.debug(
                        f"Edge mapping: ({head_id}, {relation}, {dup_tail_id}) "
                        f"-> ({head_id}, {relation}, {rep_tail_id})"
                    )
        
        logger.info(f"Loaded {total_mappings} edge mappings from {len(results.get('triples', []))} triple groups")
    
    def apply_dedup_to_graph(self) -> None:
        """Apply deduplication mappings to the graph."""
        logger.info("Applying deduplication results to graph...")
        
        # 统计信息
        nodes_removed = 0
        edges_removed = 0
        edges_redirected = 0
        
        # 1. 处理节点去重（关键词节点）
        nodes_to_remove = set()
        for dup_id, rep_id in self.node_mapping.items():
            if dup_id in self.graph.nodes and rep_id in self.graph.nodes:
                # 获取duplicate节点的所有边
                # 处理出边
                for _, target, key, data in list(self.graph.out_edges(dup_id, keys=True, data=True)):
                    # 将边重定向到representative
                    if not self.graph.has_edge(rep_id, target, key=key):
                        self.graph.add_edge(rep_id, target, key=key, **data)
                        edges_redirected += 1
                
                # 处理入边
                for source, _, key, data in list(self.graph.in_edges(dup_id, keys=True, data=True)):
                    # 将边重定向到representative
                    if not self.graph.has_edge(source, rep_id, key=key):
                        self.graph.add_edge(source, rep_id, key=key, **data)
                        edges_redirected += 1
                
                # 标记节点为待删除
                nodes_to_remove.add(dup_id)
                
        # 删除duplicate节点
        for node_id in nodes_to_remove:
            self.graph.remove_node(node_id)
            nodes_removed += 1
        
        logger.info(f"Removed {nodes_removed} duplicate keyword nodes, redirected {edges_redirected} edges")
        
        # 2. 处理边去重（三元组）
        edges_to_remove = []
        edges_to_add = []
        
        for (head_id, relation, dup_tail_id), rep_tail_id in self.edge_mapping.items():
            # 查找所有匹配的边
            if self.graph.has_node(head_id) and self.graph.has_node(dup_tail_id):
                for key, data in list(self.graph[head_id][dup_tail_id].items()):
                    if data.get("relation") == relation:
                        # 记录要删除的边
                        edges_to_remove.append((head_id, dup_tail_id, key))
                        
                        # 如果representative tail存在，添加新边
                        if self.graph.has_node(rep_tail_id):
                            # 检查是否已存在相同的边
                            edge_exists = False
                            if self.graph.has_edge(head_id, rep_tail_id):
                                for existing_data in self.graph[head_id][rep_tail_id].values():
                                    if existing_data.get("relation") == relation:
                                        edge_exists = True
                                        break
                            
                            if not edge_exists:
                                edges_to_add.append((head_id, rep_tail_id, data))
        
        # 删除duplicate边
        for head, tail, key in edges_to_remove:
            self.graph.remove_edge(head, tail, key)
            edges_removed += 1
        
        # 添加新边（重定向到representative）
        for head, tail, data in edges_to_add:
            self.graph.add_edge(head, tail, **data)
        
        logger.info(f"Removed {edges_removed} duplicate edges, added {len(edges_to_add)} redirected edges")
        
        # 3. 清理孤立节点（可选）
        isolated_nodes = list(nx.isolates(self.graph))
        if isolated_nodes:
            logger.info(f"Found {len(isolated_nodes)} isolated nodes (not removing them by default)")
        
        logger.info(
            f"Final graph stats: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply offline deduplication results to graph.json"
    )
    parser.add_argument(
        "--graph",
        required=True,
        type=Path,
        help="Path to the input graph JSON file"
    )
    parser.add_argument(
        "--keyword-dedup",
        type=Path,
        help="Path to keyword deduplication results JSON file"
    )
    parser.add_argument(
        "--edge-dedup",
        type=Path,
        help="Path to edge deduplication results JSON file"
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Where to save the deduplicated graph JSON"
    )
    parser.add_argument(
        "--remove-isolated",
        action="store_true",
        help="Remove isolated nodes after deduplication"
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    
    if not args.keyword_dedup and not args.edge_dedup:
        raise ValueError(
            "At least one of --keyword-dedup or --edge-dedup must be provided"
        )
    
    applier = DedupResultsApplier()
    
    # Load graph
    logger.info(f"Loading graph from {args.graph}")
    applier.graph = graph_processor.load_graph_from_json(str(args.graph))
    
    original_nodes = applier.graph.number_of_nodes()
    original_edges = applier.graph.number_of_edges()
    logger.info(f"Original graph: {original_nodes} nodes, {original_edges} edges")
    
    # Load dedup results
    if args.keyword_dedup:
        applier.load_keyword_dedup_results(args.keyword_dedup)
    
    if args.edge_dedup:
        applier.load_edge_dedup_results(args.edge_dedup)
    
    # Apply deduplication
    applier.apply_dedup_to_graph()
    
    # Remove isolated nodes if requested
    if args.remove_isolated:
        isolated = list(nx.isolates(applier.graph))
        if isolated:
            logger.info(f"Removing {len(isolated)} isolated nodes")
            applier.graph.remove_nodes_from(isolated)
    
    # Save result
    args.output.parent.mkdir(parents=True, exist_ok=True)
    graph_processor.save_graph_to_json(applier.graph, str(args.output))
    
    final_nodes = applier.graph.number_of_nodes()
    final_edges = applier.graph.number_of_edges()
    
    logger.info(
        f"Deduplication complete:\n"
        f"  Nodes: {original_nodes} -> {final_nodes} "
        f"(removed {original_nodes - final_nodes})\n"
        f"  Edges: {original_edges} -> {final_edges} "
        f"(removed {original_edges - final_edges})"
    )
    logger.info(f"Deduplicated graph saved to {args.output}")


if __name__ == "__main__":
    main()
