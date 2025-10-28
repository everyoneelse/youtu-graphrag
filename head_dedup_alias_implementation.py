"""
Head Deduplication with Alias Relationship - Implementation

This file provides the improved implementation that:
1. Preserves duplicate nodes as alias nodes
2. Creates explicit "alias_of" relationships
3. Avoids self-loops
4. Maintains semantic correctness

Author: Knowledge Graph Team
Date: 2025-10-28
"""

import copy
import time
from typing import Dict, List, Tuple, Any, Set
from collections import defaultdict
from utils.logger import logger


class HeadDeduplicationAliasMixin:
    """
    Improved head deduplication using explicit alias relationships.
    
    This mixin can be added to KnowledgeTreeGen to replace or complement
    the existing head deduplication functionality.
    """
    
    # ============================================================
    # Core: Alias-based Merging
    # ============================================================
    
    def _merge_head_nodes_with_alias(
        self,
        merge_mapping: Dict[str, str],
        metadata: Dict[str, dict],
        alias_relation: str = "alias_of"
    ) -> Dict[str, int]:
        """
        Merge head nodes using explicit alias relationships.
        
        Strategy:
        1. Revise representative selection (prefer nodes with more relations)
        2. Transfer all non-alias edges to representative
        3. Keep duplicate node (don't delete)
        4. Create explicit: duplicate --[alias_of]--> representative
        5. Clean up other edges from duplicate
        6. Mark node roles
        
        Args:
            merge_mapping: {duplicate_id: canonical_id}
            metadata: Merge metadata from LLM/embedding
            alias_relation: Name of the alias relationship
            
        Returns:
            Statistics dict with counts
        """
        if not merge_mapping:
            logger.info("No head nodes to merge")
            return {"alias_relations_created": 0, "edges_transferred": 0}
        
        logger.info(f"Merging {len(merge_mapping)} head nodes with alias relationships...")
        
        # Step 1: Revise representative selection
        revised_mapping = self._revise_representative_selection(merge_mapping)
        logger.info(f"Revised {len(revised_mapping)} merge decisions after representative re-evaluation")
        
        alias_count = 0
        edges_transferred = 0
        
        for duplicate_id, canonical_id in revised_mapping.items():
            # Validate nodes exist
            if duplicate_id not in self.graph or canonical_id not in self.graph:
                logger.debug(f"Nodes not found: {duplicate_id} or {canonical_id}")
                continue
            
            if duplicate_id == canonical_id:
                logger.warning(f"Duplicate and canonical are same: {duplicate_id}")
                continue
            
            try:
                # Step 2: Transfer edges safely (avoiding self-loops)
                out_count = self._reassign_outgoing_edges_safe(
                    duplicate_id, canonical_id
                )
                in_count = self._reassign_incoming_edges_safe(
                    duplicate_id, canonical_id
                )
                edges_transferred += (out_count + in_count)
                
                # Step 3: Create alias relationship
                self.graph.add_edge(
                    duplicate_id,
                    canonical_id,
                    relation=alias_relation,
                    source_chunks=[],  # Inferred from deduplication
                    dedup_metadata=metadata.get(duplicate_id, {}),
                    created_by="head_deduplication",
                    timestamp=time.time()
                )
                alias_count += 1
                
                # Step 4: Remove non-alias edges from duplicate
                self._remove_non_alias_edges(
                    duplicate_id, 
                    keep_edge=(duplicate_id, canonical_id)
                )
                
                # Step 5: Mark node roles
                self.graph.nodes[duplicate_id]["properties"]["node_role"] = "alias"
                self.graph.nodes[duplicate_id]["properties"]["alias_of"] = canonical_id
                
                canonical_props = self.graph.nodes[canonical_id].get("properties", {})
                canonical_props["node_role"] = "representative"
                
                # Step 6: Record aliases in canonical node
                if "aliases" not in canonical_props:
                    canonical_props["aliases"] = []
                
                canonical_props["aliases"].append({
                    "alias_id": duplicate_id,
                    "alias_name": self.graph.nodes[duplicate_id]["properties"].get("name", ""),
                    "confidence": metadata.get(duplicate_id, {}).get("confidence", 1.0),
                    "method": metadata.get(duplicate_id, {}).get("method", "unknown"),
                    "timestamp": time.time()
                })
                
                logger.debug(
                    f"Created alias relationship: {duplicate_id} -> {canonical_id} "
                    f"(transferred {out_count + in_count} edges)"
                )
                
            except Exception as e:
                logger.error(f"Error creating alias relationship {duplicate_id} -> {canonical_id}: {e}")
                continue
        
        logger.info(
            f"Successfully created {alias_count} alias relationships, "
            f"transferred {edges_transferred} edges"
        )
        
        return {
            "alias_relations_created": alias_count,
            "edges_transferred": edges_transferred
        }
    
    # ============================================================
    # Helper: Representative Selection
    # ============================================================
    
    def _revise_representative_selection(
        self, 
        merge_mapping: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Revise representative selection to choose better candidates.
        
        Strategy (in priority order):
        1. Prefer nodes with higher out-degree (more relationships)
        2. Prefer nodes with longer names (likely more formal/complete)
        3. Prefer nodes with more chunk_ids (more evidence)
        4. Default to smaller ID (created earlier)
        
        Args:
            merge_mapping: Original {duplicate: canonical} mapping
            
        Returns:
            Revised {duplicate: canonical} mapping
        """
        # Group by canonical (find all nodes that should merge together)
        groups = defaultdict(set)
        for dup, can in merge_mapping.items():
            groups[can].add(dup)
            groups[can].add(can)
        
        revised_mapping = {}
        
        for original_canonical, node_set in groups.items():
            if len(node_set) <= 1:
                continue
            
            # Evaluate each node as potential representative
            node_list = list(node_set)
            node_scores = []
            
            for node_id in node_list:
                if node_id not in self.graph:
                    continue
                
                node_data = self.graph.nodes[node_id]
                props = node_data.get("properties", {})
                
                # Compute score components
                out_degree = self.graph.out_degree(node_id)
                in_degree = self.graph.in_degree(node_id)
                name = props.get("name", "")
                name_length = len(name)
                chunk_count = len(props.get("chunk_ids", []))
                node_id_num = int(node_id.split('_')[1])
                
                # Combined score (weighted)
                score = (
                    out_degree * 100 +      # Out-degree most important
                    in_degree * 50 +        # In-degree also important
                    name_length * 10 +      # Name length moderately important
                    chunk_count * 20 +      # Evidence count important
                    -node_id_num * 0.1      # Earlier ID slightly preferred
                )
                
                node_scores.append((node_id, score, out_degree, name_length))
            
            # Sort by score (descending)
            node_scores.sort(key=lambda x: x[1], reverse=True)
            
            if node_scores:
                best_representative = node_scores[0][0]
                
                logger.debug(
                    f"Representative for group {node_set}: {best_representative} "
                    f"(score={node_scores[0][1]:.1f}, out_degree={node_scores[0][2]}, "
                    f"name_len={node_scores[0][3]})"
                )
                
                # All other nodes become aliases of the best representative
                for node_id, score, _, _ in node_scores:
                    if node_id != best_representative:
                        revised_mapping[node_id] = best_representative
        
        return revised_mapping
    
    # ============================================================
    # Helper: Safe Edge Transfer (Avoiding Self-loops)
    # ============================================================
    
    def _reassign_outgoing_edges_safe(
        self, 
        source_id: str, 
        target_id: str
    ) -> int:
        """
        Safely transfer outgoing edges, avoiding self-loops.
        
        Args:
            source_id: Source node (will become alias)
            target_id: Target node (representative)
            
        Returns:
            Number of edges transferred
        """
        outgoing = list(self.graph.out_edges(source_id, keys=True, data=True))
        transferred = 0
        
        for _, tail_id, key, data in outgoing:
            # Skip edges that would create self-loops
            if tail_id == target_id:
                logger.debug(
                    f"Skipping edge to avoid self-loop: {source_id} -> {tail_id} "
                    f"(relation: {data.get('relation')})"
                )
                continue
            
            if tail_id == source_id:
                logger.debug(f"Skipping self-reference edge: {source_id} -> {tail_id}")
                continue
            
            # Check if similar edge already exists
            edge_exists, existing_key = self._find_similar_edge(target_id, tail_id, data)
            
            if not edge_exists:
                # Add new edge
                self.graph.add_edge(target_id, tail_id, **copy.deepcopy(data))
                transferred += 1
                logger.debug(
                    f"Transferred edge: {target_id} -> {tail_id} "
                    f"(relation: {data.get('relation')})"
                )
            else:
                # Merge chunk information
                self._merge_edge_chunks(target_id, tail_id, existing_key, data)
                logger.debug(
                    f"Merged chunks for existing edge: {target_id} -> {tail_id}"
                )
        
        return transferred
    
    def _reassign_incoming_edges_safe(
        self, 
        source_id: str, 
        target_id: str
    ) -> int:
        """
        Safely transfer incoming edges, avoiding self-loops.
        
        Args:
            source_id: Source node (will become alias)
            target_id: Target node (representative)
            
        Returns:
            Number of edges transferred
        """
        incoming = list(self.graph.in_edges(source_id, keys=True, data=True))
        transferred = 0
        
        for head_id, _, key, data in incoming:
            # Skip edges that would create self-loops
            if head_id == target_id:
                logger.debug(
                    f"Skipping edge to avoid self-loop: {head_id} -> {source_id} "
                    f"(relation: {data.get('relation')})"
                )
                continue
            
            if head_id == source_id:
                logger.debug(f"Skipping self-reference edge: {head_id} -> {source_id}")
                continue
            
            # Check if similar edge already exists
            edge_exists, existing_key = self._find_similar_edge(head_id, target_id, data)
            
            if not edge_exists:
                # Add new edge
                self.graph.add_edge(head_id, target_id, **copy.deepcopy(data))
                transferred += 1
                logger.debug(
                    f"Transferred edge: {head_id} -> {target_id} "
                    f"(relation: {data.get('relation')})"
                )
            else:
                # Merge chunk information
                self._merge_edge_chunks(head_id, target_id, existing_key, data)
                logger.debug(
                    f"Merged chunks for existing edge: {head_id} -> {target_id}"
                )
        
        return transferred
    
    def _remove_non_alias_edges(
        self, 
        node_id: str, 
        keep_edge: Tuple[str, str]
    ):
        """
        Remove all edges from a node except the alias_of edge.
        
        This "cleans up" the alias node so it only has one outgoing edge
        (the alias_of relationship) and no incoming edges.
        
        Args:
            node_id: Node to clean up
            keep_edge: Edge to keep (source, target) - the alias_of edge
        """
        # Remove all outgoing edges except alias_of
        outgoing = list(self.graph.out_edges(node_id, keys=True))
        for _, tail_id, key in outgoing:
            if (node_id, tail_id) != keep_edge:
                self.graph.remove_edge(node_id, tail_id, key)
                logger.debug(f"Removed outgoing edge: {node_id} -> {tail_id}")
        
        # Remove all incoming edges
        incoming = list(self.graph.in_edges(node_id, keys=True))
        for head_id, _, key in incoming:
            self.graph.remove_edge(head_id, node_id, key)
            logger.debug(f"Removed incoming edge: {head_id} -> {node_id}")
    
    # ============================================================
    # Modified Main Entry Point
    # ============================================================
    
    def deduplicate_heads_with_alias(
        self,
        enable_semantic: bool = True,
        similarity_threshold: float = 0.85,
        use_llm_validation: bool = False,
        max_candidates: int = 1000,
        alias_relation: str = "alias_of"
    ) -> Dict[str, Any]:
        """
        Main entry point: Head deduplication with alias relationships.
        
        This is similar to deduplicate_heads() but uses the alias approach
        instead of deleting duplicate nodes.
        
        Args:
            enable_semantic: Enable semantic deduplication
            similarity_threshold: Similarity threshold (0.0-1.0)
            use_llm_validation: Use LLM validation (slower but more accurate)
            max_candidates: Maximum candidate pairs to process
            alias_relation: Name of the alias relationship
            
        Returns:
            Statistics dict
        """
        logger.info("=" * 70)
        logger.info("Starting Head Node Deduplication (Alias Method)")
        logger.info("=" * 70)
        logger.info(f"Configuration:")
        logger.info(f"  - Enable semantic dedup: {enable_semantic}")
        logger.info(f"  - Similarity threshold: {similarity_threshold}")
        logger.info(f"  - Use LLM validation: {use_llm_validation}")
        logger.info(f"  - Max candidates: {max_candidates}")
        logger.info(f"  - Alias relation: {alias_relation}")
        logger.info("=" * 70)
        
        start_time = time.time()
        
        # Phase 1: Collect candidates
        logger.info("\n[Phase 1/4] Collecting head candidates...")
        candidates = self._collect_head_candidates()
        logger.info(f"✓ Found {len(candidates)} entity nodes")
        
        # Phase 2: Exact match deduplication
        logger.info("\n[Phase 2/4] Exact match deduplication...")
        exact_merge_mapping = self._deduplicate_heads_exact(candidates)
        logger.info(f"✓ Identified {len(exact_merge_mapping)} exact matches")
        
        # Apply exact match with alias
        exact_stats = self._merge_head_nodes_with_alias(
            exact_merge_mapping, 
            {},
            alias_relation
        )
        logger.info(
            f"✓ Created {exact_stats['alias_relations_created']} alias relationships"
        )
        
        # Phase 3: Semantic deduplication (optional)
        semantic_stats = {"alias_relations_created": 0, "edges_transferred": 0}
        
        if enable_semantic:
            logger.info("\n[Phase 3/4] Semantic deduplication...")
            
            # Get remaining nodes (exclude already processed aliases)
            remaining_nodes = [
                node_id for node_id in candidates
                if node_id not in exact_merge_mapping and 
                   node_id in self.graph and
                   self.graph.nodes[node_id].get("properties", {}).get("node_role") != "alias"
            ]
            logger.info(f"  Remaining nodes after exact match: {len(remaining_nodes)}")
            
            if len(remaining_nodes) >= 2:
                # Generate candidate pairs
                candidate_pairs = self._generate_semantic_candidates(
                    remaining_nodes,
                    max_candidates=max_candidates,
                    similarity_threshold=0.75
                )
                logger.info(f"✓ Generated {len(candidate_pairs)} candidate pairs")
                
                if candidate_pairs:
                    # Validate candidates
                    if use_llm_validation:
                        logger.info("  Using LLM validation...")
                        semantic_merge_mapping, metadata = self._validate_candidates_with_llm(
                            candidate_pairs,
                            similarity_threshold
                        )
                    else:
                        logger.info("  Using embedding validation...")
                        semantic_merge_mapping, metadata = self._validate_candidates_with_embedding(
                            candidate_pairs,
                            similarity_threshold
                        )
                    
                    logger.info(f"✓ Identified {len(semantic_merge_mapping)} semantic matches")
                    
                    # Apply semantic merge with alias
                    semantic_stats = self._merge_head_nodes_with_alias(
                        semantic_merge_mapping,
                        metadata,
                        alias_relation
                    )
                    logger.info(
                        f"✓ Created {semantic_stats['alias_relations_created']} alias relationships"
                    )
        else:
            logger.info("\n[Phase 3/4] Semantic deduplication skipped")
        
        # Phase 4: Integrity validation
        logger.info("\n[Phase 4/4] Validating graph integrity...")
        issues = self.validate_graph_integrity_with_alias()
        
        if any(v for v in issues.values() if v):  # Check if any list is non-empty
            logger.warning(f"⚠ Found integrity issues: {issues}")
        else:
            logger.info("✓ Graph integrity validated")
        
        elapsed_time = time.time() - start_time
        
        # Statistics
        final_entity_count = len([
            n for n, d in self.graph.nodes(data=True)
            if d.get("label") == "entity" and
               d.get("properties", {}).get("node_role") != "alias"
        ])
        
        alias_count = len([
            n for n, d in self.graph.nodes(data=True)
            if d.get("properties", {}).get("node_role") == "alias"
        ])
        
        stats = {
            "total_candidates": len(candidates),
            "exact_alias_created": exact_stats["alias_relations_created"],
            "semantic_alias_created": semantic_stats["alias_relations_created"],
            "total_alias_created": (
                exact_stats["alias_relations_created"] + 
                semantic_stats["alias_relations_created"]
            ),
            "total_edges_transferred": (
                exact_stats["edges_transferred"] + 
                semantic_stats["edges_transferred"]
            ),
            "initial_entity_count": len(candidates),
            "final_main_entity_count": final_entity_count,
            "final_alias_count": alias_count,
            "final_total_entities": final_entity_count + alias_count,
            "elapsed_time_seconds": elapsed_time,
            "integrity_issues": issues
        }
        
        logger.info("\n" + "=" * 70)
        logger.info("Head Deduplication Completed (Alias Method)")
        logger.info("=" * 70)
        logger.info(f"Summary:")
        logger.info(f"  - Initial entities: {stats['initial_entity_count']}")
        logger.info(f"  - Final main entities: {stats['final_main_entity_count']}")
        logger.info(f"  - Final alias entities: {stats['final_alias_count']}")
        logger.info(f"  - Total alias relations created: {stats['total_alias_created']}")
        logger.info(f"    • From exact matches: {stats['exact_alias_created']}")
        logger.info(f"    • From semantic matches: {stats['semantic_alias_created']}")
        logger.info(f"  - Edges transferred: {stats['total_edges_transferred']}")
        logger.info(f"  - Time elapsed: {elapsed_time:.2f}s")
        logger.info("=" * 70)
        
        return stats
    
    # ============================================================
    # Integrity Validation (Modified for Alias Nodes)
    # ============================================================
    
    def validate_graph_integrity_with_alias(self) -> Dict[str, List]:
        """
        Validate graph integrity after alias-based deduplication.
        
        Modified rules:
        - Alias nodes are NOT considered orphans (they have alias_of edge)
        - Self-loops should not exist
        - All alias_of edges should point to representative nodes
        
        Returns:
            Dict with lists of issues
        """
        issues = {
            "orphan_nodes": [],
            "self_loops": [],
            "dangling_references": [],
            "invalid_alias_nodes": [],
            "alias_chains": []
        }
        
        # Check orphan nodes (excluding valid alias nodes)
        for node_id, data in self.graph.nodes(data=True):
            if data.get("label") == "entity":
                in_degree = self.graph.in_degree(node_id)
                out_degree = self.graph.out_degree(node_id)
                node_role = data.get("properties", {}).get("node_role")
                
                # Alias nodes with only alias_of edge are valid
                if node_role == "alias":
                    if out_degree == 1:
                        out_edges = list(self.graph.out_edges(node_id, data=True))
                        if out_edges[0][2].get("relation") == "alias_of":
                            continue  # Valid alias node
                    # Invalid alias node
                    issues["invalid_alias_nodes"].append(
                        (node_id, f"in={in_degree}, out={out_degree}")
                    )
                elif in_degree == 0 and out_degree == 0:
                    issues["orphan_nodes"].append(node_id)
        
        # Check self-loops (should not exist with alias method!)
        for u, v in self.graph.edges():
            if u == v:
                issues["self_loops"].append((u, v))
        
        # Check alias chains (alias pointing to alias)
        for node_id, data in self.graph.nodes(data=True):
            if data.get("properties", {}).get("node_role") == "alias":
                out_edges = list(self.graph.out_edges(node_id, data=True))
                for _, target_id, edge_data in out_edges:
                    if edge_data.get("relation") == "alias_of":
                        target_data = self.graph.nodes.get(target_id, {})
                        target_role = target_data.get("properties", {}).get("node_role")
                        if target_role == "alias":
                            issues["alias_chains"].append((node_id, target_id))
        
        # Check dangling references
        for u, v, data in self.graph.edges(data=True):
            if u not in self.graph.nodes:
                issues["dangling_references"].append(("head", u, v))
            if v not in self.graph.nodes:
                issues["dangling_references"].append(("tail", u, v))
        
        return issues
    
    # ============================================================
    # Utility Functions
    # ============================================================
    
    def is_alias_node(self, node_id: str) -> bool:
        """Check if a node is an alias node."""
        if node_id not in self.graph:
            return False
        return (
            self.graph.nodes[node_id]
            .get("properties", {})
            .get("node_role") == "alias"
        )
    
    def get_main_entities_only(self) -> List[str]:
        """Get only main entities (excluding aliases)."""
        return [
            node_id
            for node_id, data in self.graph.nodes(data=True)
            if data.get("label") == "entity" and
               data.get("properties", {}).get("node_role") != "alias"
        ]
    
    def resolve_alias(self, node_id: str) -> str:
        """
        Resolve alias to main entity.
        If node is an alias, return its representative; otherwise return itself.
        """
        if not self.is_alias_node(node_id):
            return node_id
        
        # Follow alias_of edge
        for _, target_id, data in self.graph.out_edges(node_id, data=True):
            if data.get("relation") == "alias_of":
                return target_id
        
        return node_id  # Fallback
    
    def get_all_aliases(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Get all aliases for a given entity.
        
        Args:
            entity_id: Main entity ID
            
        Returns:
            List of alias info dicts
        """
        if entity_id not in self.graph:
            return []
        
        properties = self.graph.nodes[entity_id].get("properties", {})
        return properties.get("aliases", [])
    
    def export_alias_mapping(self, output_path: str):
        """
        Export alias mapping for external use.
        
        Format: CSV with columns:
        - alias_id
        - alias_name
        - main_entity_id
        - main_entity_name
        - confidence
        - method
        """
        import csv
        
        rows = []
        
        for node_id, data in self.graph.nodes(data=True):
            if data.get("label") != "entity":
                continue
            
            props = data.get("properties", {})
            if props.get("node_role") == "representative":
                main_entity_id = node_id
                main_entity_name = props.get("name", "")
                
                for alias_info in props.get("aliases", []):
                    rows.append({
                        "alias_id": alias_info["alias_id"],
                        "alias_name": alias_info["alias_name"],
                        "main_entity_id": main_entity_id,
                        "main_entity_name": main_entity_name,
                        "confidence": alias_info.get("confidence", 1.0),
                        "method": alias_info.get("method", "unknown")
                    })
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                "alias_id", "alias_name",
                "main_entity_id", "main_entity_name",
                "confidence", "method"
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        logger.info(f"✓ Exported {len(rows)} alias mappings to {output_path}")
