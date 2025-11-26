#!/usr/bin/env python3
"""
Apply tail deduplication results to the original knowledge graph.

This script takes deduplication results from semantic_dedup_group processing
and applies them to the graph by replacing all cluster members with their
representative (the last member in each cluster).

Supports both regular deduplication and alias deduplication.

Usage:
    # Apply regular deduplication
    python apply_tail_dedup_results.py \
        --graph output/graphs/original.json \
        --dedup-results tail_dedup_results.json \
        --output output/graphs/deduped.json

    # Apply alias deduplication
    python apply_tail_dedup_results.py \
        --graph output/graphs/original.json \
        --alias-dedup-results alias_dedup_results.json \
        --output output/graphs/deduped.json

    # Apply both (alias first, then regular)
    python apply_tail_dedup_results.py \
        --graph output/graphs/original.json \
        --alias-dedup-results alias_dedup_results.json \
        --dedup-results tail_dedup_results.json \
        --output output/graphs/deduped.json
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import regex as re
import networkx as nx

from utils_ import graph_processor
from utils_.logger import logger


class TailDedupApplicator:
    """Apply tail deduplication results to a knowledge graph."""
    
    def __init__(self, graph: nx.MultiDiGraph):
        self.graph = graph
        # Mapping from node identifier string to its representative
        self.node_mapping: Dict[str, str] = {}
        self.node_mapping_reverse: Dict[str,list[str]] = defaultdict(list[str])
        self.name_mapping: Dict[str, str] = {}
        self.name_mapping_reverse: Dict['str', list[str]] = defaultdict(list[str])
        # Statistics
        self.stats = {
            'total_clusters': 0,
            'total_members': 0,
            'edges_updated': 0,
            'communities_updated': 0,
            'community_members_deduplicated': 0,
            'keyword_filter_relations_updated': 0,
        }
    
    def _parse_node_identifier_(self, line):
        
        #outer_re = re.compile(
        #    r'^\s*(?P<name>.+?)\s*'                    # 名称
        #    r'(?:\([^)]*\)\s*)*'                        # 跳过中间壳
        #    r'\(\s*(?P<core>[^)]*)\s*\)'                # 真正有用的括号整块
        #    r'.*?'                                      # 任意中间字符
        #    r'(?P<tag>\[[^\]]+\])'                      # [tag] 只要出现即可
        #)

        pattern = re.compile(
            r'^\s*(?P<name>.*?)\s*'          # 第一部分：名称
            r'\(\s*'                         # 左括号
            # 循环抓键值对：chunk id 或 schema_type
            r'(?:'
            r'(?:(?P<key>chunk\s+id|schema_type)\s*:\s*(?P<val>[^,)]*))\s*,?\s*'
            r')+'
            r'\)\s*'                         # 右括号
            r'(?P<tag>\[[^\]]+\])'           # 最后的 [xxx]
        )
        match = pattern.match(line)
        if not match:
            import pdb; pdb.set_trace()
            raise ValueError(f'格式不匹配, {line}')
        name = match.group('name').strip()
        tag = match.group('tag').replace('[', '').replace(']', '')
        kv = dict(zip(match.captures('key'), match.captures('val')))
        chunk_id = kv.get('chunk id', '').strip()
        schema_type = kv.get('schema_type', '').strip()

        if schema_type == "" and "schema_type" not in line:
            reconstruct = f"{name} (chunk id: {chunk_id}) [{tag}]"
        else:
            reconstruct = f"{name} (chunk id: {chunk_id}, schema_type: {schema_type}) [{tag}]"

        reconstruct_flag = True
        if reconstruct != line:
            logger.warning(f"Reconstruct: {reconstruct} != {line}")
            reconstruct_flag = False

        return name, chunk_id, schema_type, tag, reconstruct_flag

    
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
        name, chunk_id, schema_type, label, reconstruct_flag = self._parse_node_identifier_(node_str)
        if not reconstruct_flag:
            return None
        label = label.replace('[', '').replace(']', '')
        
        # Search for matching node in the graph
        for node_id, node_data in self.graph.nodes(data=True):
            props = node_data.get('properties', {})
            #if '单位: 百万分比 (ppm)' in props.get('name', '') and '单位: 百万分比 (ppm)' in node_str:
            #    import pdb; pdb.set_trace()
            
            if node_data.get('label') != label:
                continue
            
            node_name = props.get('name', '')
            node_chunk_id = props.get('chunk id', '')
            schema_type = props.get('schema_type', '')
            if node_name == name and node_chunk_id == chunk_id and schema_type == schema_type:
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
        #import pdb; pdb.set_trace()
        for group in dedup_results:
            dedup_clusters = group.get('dedup_results', {})
            
            for cluster_name, cluster_data in dedup_clusters.items():
                members = cluster_data.get('member', [])
                
                if not members:
                    logger.warning(f"No members found for cluster {cluster_name}")
                    continue
                
                #if "脑脊液流动伪影 (chunk id: JICjXeah, schema_type: MRI伪影) [entity]" in members:
                #    import pdb;pdb.set_trace()
                
                # Use the LAST member as the representative
                representative = members[-1]
                
                # Map all members to the representative
                for member in members:
                    self.node_mapping[member] = representative
                    self.node_mapping_reverse[representative].append(member)

                    representative_node = self._find_node_by_identifier(representative)
                    member_node = self._find_node_by_identifier(member)
                    if member_node is None or representative_node is None:
                        logger.warning(f"Member node or representative node not found for {member} -> {representative}")
                        continue
                    try:
                        self.name_mapping[self.graph.nodes[member_node]['properties']['name']] = self.graph.nodes[representative_node]['properties']['name']
                    except:
                        import pdb; pdb.set_trace()
                    self.name_mapping_reverse[self.graph.nodes[representative_node]['properties']['name']].append(self.graph.nodes[member_node]['properties']['name'])

                    
                self.stats['total_clusters'] += 1
                self.stats['total_members'] += len(members)
        #import pdb;pdb.set_trace()
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
        schema_type = props.get('schema_type', '')
        
        # Construct identifier string
        if chunk_id and schema_type:
            node_str = f"{name} (chunk id: {chunk_id}, schema_type: {schema_type}) [{label}]"
        elif chunk_id:
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
            #import pdb; pdb.set_trace()
            logger.warning(f"Representative node not found for {node_str} -> {rep_str}, keeping original")
            return node_id
        
        return rep_node_id
    
    def apply_to_edges(self) -> None:
        """
        Apply deduplication mapping to all edges (triples) in the graph.
        
        For each edge, replace BOTH head and tail nodes with their representatives
        if they are in a dedup cluster. This ensures all occurrences of deduplicated
        nodes are replaced, regardless of their position in the triple.
        """
        logger.info("Applying deduplication to edges...")
        
        edges_to_add = []
        edges_to_remove = []
        edges_to_save = []

        ori_graph_has_save_head_and_tails = defaultdict(bool)

        edge_to_remove_edge_to_add_dict = defaultdict(str)
        
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            
            if (key != 0):
                logger.warning(f"key: {key} is not 0, {self.graph.nodes[u]['properties']['name']} -> {data.get('relation', '')} -> {self.graph.nodes[v]['properties']['name']}")
            
            # Get representatives for BOTH head and tail nodes
            u_rep = self._get_representative(u)
            v_rep = self._get_representative(v)
            u_meta = self.graph.nodes[u].get('properties', {})
            v_meta = self.graph.nodes[v].get('properties', {})
            u_meta_rep = self.graph.nodes[u_rep].get('properties', {})
            v_meta_rep = self.graph.nodes[v_rep].get('properties', {})

            ori_graph_has_save_head_and_tail = False
            if u == v:
                ori_graph_has_save_head_and_tail = True
                        
            if u == u_rep and v in self.node_mapping_reverse[u_rep]:
                import pdb; pdb.set_trace()

            if v == v_rep and u in self.node_mapping_reverse[v_rep]:
                import pdb; pdb.set_trace()

            #if "环状伪影" in u_meta.get('name', '') or "截断伪影" in u_meta_rep.get('name', ''):
            #    import pdb; pdb.set_trace()

            #if "空间预饱和" in u_meta.get('name', '') and "可细分为" in data.get('relation', ''):
            #    import ipdb; ipdb.set_trace()

            #if u_rep == v_rep and "别名包括" in data.get('relation', ''):
            #    logger.warning(f"{self.graph.nodes[u]['properties']['name']}({u}) "\
            #        f"and {self.graph.nodes[v]['properties']['name']}({v}) has same representative {self.graph.nodes[u_rep]['properties']['name']}({u_rep})")
            #    #import pdb; pdb.set_trace()
            #    has_alias_edge = False
            #    if self.graph.has_edge(u_rep, v):
            #        for edge_key, edge_data in self.graph[u][v].items():
            #            if edge_data.get('relation') == '别名包括':
            #                #import pdb; pdb.set_trace()
            #                has_alias_edge = True
            #                break
            #    if has_alias_edge:
            #        pass
            #    else:
            #        logger.warning(f"Adding alias edge: {self.graph.nodes[u_rep]['properties']['name']}({u_rep}) -> {data.get('relation', '')} -> {self.graph.nodes[v]['properties']['name']}({v})")
            #        edges_to_add.append((u_rep, v, {'relation': '别名包括'}))
            #        edges_to_remove.append((u, v, key, data))
            #else:

            # If either head or tail should be replaced
            if u_rep != u or v_rep != v:
                relation = data.get('relation', '')
                
                # Check if edge with representatives already exists
                if u_rep != v_rep or ori_graph_has_save_head_and_tail:
                    edge_exists = False
                    if self.graph.has_edge(u_rep, v_rep):
                        for edge_key, edge_data in self.graph[u_rep][v_rep].items():
                            if edge_data.get('relation') == relation:
                                edge_exists = True
                                break
                                
                    if not edge_exists:
                        if (u_rep, v_rep, data) in edges_to_add:
                            continue
                        edges_to_add.append((u_rep, v_rep, data))
                        assert (u_rep + '_' + v_rep + '_' + data.get('relation', '')) not in ori_graph_has_save_head_and_tails, f"{(u_rep + '_' + v_rep + '_' + data.get('relation', ''))} already in ori_graph_has_save_head_and_tails"
                        ori_graph_has_save_head_and_tails[(u_rep + '_' + v_rep + '_' + data.get('relation', ''))] = ori_graph_has_save_head_and_tail
                        
                        dickey = "+".join([u, v, str(key), data.get('relation', '')])
                        edge_to_remove_edge_to_add_dict[dickey] = "+".join([u_rep, v_rep, data.get('relation', '')])
                
                alias_edge_exists = False
                if u_rep != u:
                    if self.graph.has_edge(u_rep, u):
                        for edge_key, edge_data in self.graph[u_rep][u].items():
                            if edge_data.get('relation') == '别名包括' or edge_data.get('relation') == '等同于':
                                alias_edge_exists = True
                                break
                    selected_alias_relation = {'relation': '等同于'}
                    if (u_rep, u, {'relation': '别名包括'}) in edges_to_add or (u_rep, u, {'relation': '等同于'}) in edges_to_add:                        
                        alias_edge_exists = True
                        if (u_rep, u, {'relation': '等同于'}) in edges_to_add:
                            selected_alias_relation = {'relation': '等同于'}
                    if not alias_edge_exists:
                        #if "奈奎斯特伪影" in u_meta.get('name', '') or "折绕伪影" in u_meta_rep.get('name', ''):
                        #    import pdb; pdb.set_trace()
                        edges_to_add.append((u_rep, u, selected_alias_relation))

                        #self.graph.nodes[u_rep]['properties']['chunk id'] += ',' + self.graph.nodes[u]['properties']['chunk id']
                    edges_to_save.append((u_rep, u, selected_alias_relation))

                alias_edge_exists = False
                if v_rep != v:
                    if self.graph.has_edge(v_rep, v):
                        for edge_key, edge_data in self.graph[v_rep][v].items():
                            if edge_data.get('relation') == '别名包括' or edge_data.get('relation') == '等同于' :
                                alias_edge_exists = True
                                break
                    selected_alias_relation = {'relation': '等同于'}
                    if (v_rep, v, {'relation': '别名包括'}) in edges_to_add or (v_rep, v, {'relation': '等同于'}) in edges_to_add:
                        alias_edge_exists = True
                        if (v_rep, v, {'relation': '等同于'}) in edges_to_add:
                            selected_alias_relation = {'relation': '等同于'}
                    if not alias_edge_exists:
                        #if "奈奎斯特伪影" in v_meta.get('name', '') or "折绕伪影" in v_meta_rep.get('name', ''):
                        #    import pdb; pdb.set_trace()
                        edges_to_add.append((v_rep, v, selected_alias_relation))

                        #self.graph.nodes[v_rep]['properties']['chunk id'] += ',' + self.graph.nodes[v]['properties']['chunk id']
                    edges_to_save.append((v_rep, v, selected_alias_relation))

                edges_to_remove.append((u, v, key, data))
                self.stats['edges_updated'] += 1
        
        # Apply changes
        for u, v, key, data in edges_to_remove:
            if (u,v,data) in edges_to_save:
                continue
            dictkey = "+".join([u, v, str(key), data.get('relation', '')])

            self.graph.remove_edge(u, v, key)
            
            #if dictkey in edge_to_remove_edge_to_add_dict:
#
            #    try:
#
            #        to_add_edge = edge_to_remove_edge_to_add_dict[dictkey]
            #        to_add_edge_split = to_add_edge.split("+")
            #        to_add_u = to_add_edge_split[0]
            #        to_add_v = to_add_edge_split[1]
            #        to_add_relation = to_add_edge_split[2]
#
            #        logger.info(f"Removed edge: "\
            #        f"{self.graph.nodes[u]['properties']['name']} -> "\
            #        f"{data.get('relation', '')} -> "\
            #        f"{self.graph.nodes[v]['properties']['name']}"\
            #        f"  | To Add edge: {self.graph.nodes[to_add_u]['properties']['name']} -> {to_add_relation} -> {self.graph.nodes[to_add_v]['properties']['name']}")
            #    except:
            #        import pdb; pdb.set_trace()
            #        print()
            #else:
            logger.info(f"Removed edge: "\
                    f"{self.graph.nodes[u]['properties']['name']} -> "\
                    f"{data.get('relation', '')} -> "\
                    f"{self.graph.nodes[v]['properties']['name']}")

        
        for u, v, data in edges_to_add:
            #if u=='entity_237' and v=='entity_237':
            #    import ipdb; ipdb.set_trace()
            if u == v and not ori_graph_has_save_head_and_tails[(u + '_' + v + '_' + data.get('relation', ''))]:
                logger.warning(f"Skipping self-loop edge: {self.graph.nodes[u]['properties']['name']} -> {data.get('relation', '')} -> {self.graph.nodes[v]['properties']['name']}")
                continue
            elif u == v and ori_graph_has_save_head_and_tails[(u + '_' + v + '_' + data.get('relation', ''))]:
                logger.warning(f"Adding edge Which has same head and tail in ori graph: {self.graph.nodes[u]['properties']['name']}({self.name_mapping_reverse[self.graph.nodes[u]['properties']['name']]}) -> {data.get('relation', '')} -> {self.graph.nodes[v]['properties']['name']}({self.name_mapping_reverse[self.graph.nodes[v]['properties']['name']]})")

            if self.graph.has_edge(u, v):
                exists_edge_data = self.graph[u][v]
                if data.get('relation', '') in exists_edge_data:
                    if data.get("relation") == exists_edge_data.get("relation"):
                        logger.warning(f"Skipping existing edge: {self.graph.nodes[u]['properties']['name']} -> {data.get('relation', '')} -> {self.graph.nodes[v]['properties']['name']}")
                        import pdb; pdb.set_trace()
                        continue
                    else:
                        logger.warning(f"---Skipping existing edge: {self.graph.nodes[u]['properties']['name']} -> {data.get('relation', '')} -> {self.graph.nodes[v]['properties']['name']}")
                        import pdb; pdb.set_trace()

            self.graph.add_edge(u, v, **data)
            #if "数据采样不足" in self.graph.nodes[u]['properties']['name'] and \
            #    'member_of' in data.get('relation','') and '采样优化策略' in self.graph.nodes[v]['properties']['name']:
            #    import pdb; pdb.set_trace()
            logger.info(f"Added edge: "\
                f"{self.graph.nodes[u]['properties']['name']} -> {data.get('relation', '')} -> "\
                f"{self.graph.nodes[v]['properties']['name']}")
            

        
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
            #import pdb;pdb.set_trace()

            
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
                if self.graph.has_edge(u, v):
                    logger.warning(f"Skipping existing edge: {self.graph.nodes[u]['properties']['name']} -> {data.get('relation', '')} -> {self.graph.nodes[v]['properties']['name']}")
                    import pdb; pdb.set_trace()
                    continue
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
        isolated_nodes = []
        for node_id in self.graph.nodes():
            if self.graph.degree(node_id) == 0:
                isolated.append(node_id)
                isolated_nodes.append(self.graph.nodes[node_id])
        #import pdb;pdb.set_trace()
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
    #import pdb; pdb.set_trace()
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

    # Return the deduplicated graph
    return graph


def apply_dedup_results_to_graph(graph: nx.MultiDiGraph, dedup_results: List[Dict]) -> nx.MultiDiGraph:
    """
    Apply deduplication results to a graph and return the deduplicated graph.

    Args:
        graph: The input knowledge graph
        dedup_results: List of deduplication result dictionaries

    Returns:
        The deduplicated graph
    """
    applicator = TailDedupApplicator(graph)
    stats = applicator.apply_all(dedup_results)
    return applicator.graph


def apply_entity_dedup_results_to_graph(graph: nx.MultiDiGraph, entity_dedup_results: List[Dict]) -> nx.MultiDiGraph:
    """
    Apply entity deduplication results to a graph and return the deduplicated graph.

    Args:
        graph: The input knowledge graph
        entity_dedup_results: List of entity deduplication result dictionaries

    Returns:
        The deduplicated graph
    """
    # Apply using existing TailDedupApplicator
    applicator = TailDedupApplicator(graph)
    stats = applicator.apply_all(entity_dedup_results)
    return applicator.graph


if __name__ == "__main__":
    main()
