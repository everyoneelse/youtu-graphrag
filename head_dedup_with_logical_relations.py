"""
Head Deduplication with Logical Relations Enhancement

This module enhances head deduplication by incorporating logical relations
(such as "别名包括" / "alias_of") to generate candidate pairs, in addition
to semantic similarity-based pair generation.

Key Innovation:
- Even if two entities have low semantic similarity (e.g., "吉布斯伪影" vs "截断伪影"),
  if they are connected by an alias relationship in the graph, they should be
  considered as deduplication candidates.
  
Approach:
1. Generate semantic-based candidate pairs (existing approach)
2. Extract relation-based candidate pairs from graph
3. Merge both sets and send to LLM for validation
4. LLM makes the final decision on whether to merge

Author: Knowledge Graph Team
Date: 2025-11-02
"""

import time
from typing import Dict, List, Tuple, Any, Set
from collections import defaultdict
from utils.logger import logger


class HeadDeduplicationLogicalRelationsMixin:
    """
    Mixin that enhances head deduplication with logical relations.
    
    This can be combined with existing deduplication mixins to add
    relation-based candidate generation.
    """
    
    def _extract_alias_relation_candidates(
        self,
        remaining_nodes: List[str],
        alias_relation_names: List[str] = None
    ) -> List[Tuple[str, str, str]]:
        """
        Extract candidate pairs based on alias relationships in the graph.
        
        This method finds entities that are connected by alias-type relationships,
        even if their names have low semantic similarity.
        
        Example:
            If the graph contains: 吉布斯伪影 --[别名包括]--> 截断伪影
            Then (吉布斯伪影, 截断伪影) is a candidate pair for deduplication.
        
        Args:
            remaining_nodes: List of entity IDs to consider
            alias_relation_names: List of relation names that indicate alias
                                  Default: ["别名包括", "alias_of", "别名", 
                                           "also_known_as", "aka", "又称"]
        
        Returns:
            List of (node_id_1, node_id_2, relation_type) tuples
        """
        if alias_relation_names is None:
            # Default alias relation names (configurable)
            alias_relation_names = [
                "别名包括",
                "alias_of", 
                "别名",
                "also_known_as",
                "aka",
                "又称",
                "又名",
                "简称"
            ]
        
        logger.info(f"Extracting alias relation candidates from graph...")
        logger.info(f"  Looking for relations: {alias_relation_names}")
        
        remaining_nodes_set = set(remaining_nodes)
        relation_candidates = []
        seen_pairs = set()
        
        # Iterate through all edges in the graph
        for u, v, edge_data in self.graph.edges(data=True):
            relation = edge_data.get("relation", "")
            
            # Check if this is an alias-type relationship
            if relation in alias_relation_names:
                # Check if both nodes are in our remaining nodes
                if u in remaining_nodes_set and v in remaining_nodes_set:
                    # Ensure we don't add duplicate pairs (order-independent)
                    pair_key = tuple(sorted([u, v]))
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        relation_candidates.append((u, v, relation))
                        logger.debug(
                            f"Found alias relation: {u} --[{relation}]--> {v}"
                        )
        
        logger.info(
            f"✓ Extracted {len(relation_candidates)} candidate pairs "
            f"based on alias relations"
        )
        
        return relation_candidates
    
    def _extract_related_entity_candidates(
        self,
        remaining_nodes: List[str],
        relation_names: List[str] = None,
        max_candidates: int = 500
    ) -> List[Tuple[str, str, str]]:
        """
        Extract candidate pairs based on various logical relationships.
        
        This is a more general version that can consider multiple types of
        relationships beyond just aliases.
        
        Args:
            remaining_nodes: List of entity IDs to consider
            relation_names: List of relation names to consider
            max_candidates: Maximum number of candidates to return
        
        Returns:
            List of (node_id_1, node_id_2, relation_type) tuples
        """
        if relation_names is None:
            # Default: only alias-type relations
            # Can be extended to include other relation types
            relation_names = [
                "别名包括", "alias_of", "别名", "also_known_as", "aka",
                "又称", "又名", "简称"
            ]
        
        logger.info(f"Extracting relation-based candidates...")
        logger.info(f"  Relation types: {relation_names}")
        
        remaining_nodes_set = set(remaining_nodes)
        relation_candidates = []
        seen_pairs = set()
        
        # Iterate through edges
        for u, v, edge_data in self.graph.edges(data=True):
            relation = edge_data.get("relation", "")
            
            if relation in relation_names:
                if u in remaining_nodes_set and v in remaining_nodes_set:
                    pair_key = tuple(sorted([u, v]))
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        relation_candidates.append((u, v, relation))
        
        # Sort by some criteria if needed (e.g., prioritize certain relations)
        # For now, just limit the count
        if len(relation_candidates) > max_candidates:
            logger.warning(
                f"Too many relation-based candidates ({len(relation_candidates)}). "
                f"Limiting to {max_candidates}."
            )
            relation_candidates = relation_candidates[:max_candidates]
        
        logger.info(f"✓ Extracted {len(relation_candidates)} relation-based candidates")
        
        return relation_candidates
    
    def _generate_semantic_and_relation_candidates(
        self,
        remaining_nodes: List[str],
        max_candidates: int = 1000,
        similarity_threshold: float = 0.75,
        enable_relation_candidates: bool = True,
        alias_relation_names: List[str] = None
    ) -> List[Tuple[str, str, float, str]]:
        """
        Generate candidate pairs using BOTH semantic similarity AND logical relations.
        
        This is the key method that combines both approaches:
        1. Semantic-based pairs (using embeddings)
        2. Relation-based pairs (using graph structure)
        
        Args:
            remaining_nodes: List of entity IDs to consider
            max_candidates: Maximum total candidates
            similarity_threshold: Similarity threshold for semantic candidates
            enable_relation_candidates: Whether to include relation-based candidates
            alias_relation_names: List of alias relation names
        
        Returns:
            List of (node_id_1, node_id_2, similarity_score, source_type) tuples
            - similarity_score: float for semantic pairs, 1.0 for relation pairs
            - source_type: "semantic" or "relation:<relation_name>"
        """
        logger.info("=" * 70)
        logger.info("Generating candidates (Semantic + Logical Relations)")
        logger.info("=" * 70)
        
        all_candidates = []
        seen_pairs = set()
        
        # Step 1: Generate semantic-based candidates (existing approach)
        logger.info("\n[Step 1/2] Generating semantic similarity candidates...")
        semantic_candidates = self._generate_semantic_candidates(
            remaining_nodes,
            max_candidates=max_candidates,
            similarity_threshold=similarity_threshold
        )
        
        for node_id_1, node_id_2, similarity in semantic_candidates:
            pair_key = tuple(sorted([node_id_1, node_id_2]))
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                all_candidates.append((node_id_1, node_id_2, float(similarity), "semantic"))
        
        logger.info(f"✓ Generated {len(semantic_candidates)} semantic candidates")
        
        # Step 2: Extract relation-based candidates
        if enable_relation_candidates:
            logger.info("\n[Step 2/2] Extracting logical relation candidates...")
            relation_candidates = self._extract_alias_relation_candidates(
                remaining_nodes,
                alias_relation_names=alias_relation_names
            )
            
            # Add relation-based pairs
            new_relation_pairs = 0
            for node_id_1, node_id_2, relation_type in relation_candidates:
                pair_key = tuple(sorted([node_id_1, node_id_2]))
                if pair_key not in seen_pairs:
                    seen_pairs.add(pair_key)
                    # Use 1.0 as placeholder similarity for relation-based pairs
                    # The actual decision will be made by LLM
                    all_candidates.append(
                        (node_id_1, node_id_2, 1.0, f"relation:{relation_type}")
                    )
                    new_relation_pairs += 1
                    logger.debug(
                        f"Added relation-based pair: ({node_id_1}, {node_id_2}) "
                        f"via relation '{relation_type}'"
                    )
                else:
                    logger.debug(
                        f"Pair ({node_id_1}, {node_id_2}) already in semantic candidates"
                    )
            
            logger.info(
                f"✓ Added {new_relation_pairs} NEW relation-based candidates "
                f"(total: {len(relation_candidates)})"
            )
        else:
            logger.info("\n[Step 2/2] Logical relation candidates disabled")
        
        # Step 3: Prioritize and limit
        logger.info(f"\nTotal candidates: {len(all_candidates)}")
        
        if len(all_candidates) > max_candidates:
            logger.warning(
                f"Too many candidates ({len(all_candidates)}). "
                f"Limiting to {max_candidates}."
            )
            # Prioritize: keep all relation-based pairs, then top semantic pairs
            relation_pairs = [c for c in all_candidates if c[3].startswith("relation:")]
            semantic_pairs = [c for c in all_candidates if c[3] == "semantic"]
            
            # Sort semantic pairs by similarity
            semantic_pairs.sort(key=lambda x: x[2], reverse=True)
            
            # Combine
            remaining_budget = max_candidates - len(relation_pairs)
            if remaining_budget > 0:
                all_candidates = relation_pairs + semantic_pairs[:remaining_budget]
            else:
                all_candidates = relation_pairs[:max_candidates]
            
            logger.info(
                f"Final: {len([c for c in all_candidates if c[3].startswith('relation:')])} "
                f"relation-based + "
                f"{len([c for c in all_candidates if c[3] == 'semantic'])} semantic"
            )
        
        logger.info("=" * 70)
        return all_candidates
    
    def deduplicate_heads_with_relations(
        self,
        enable_semantic: bool = True,
        enable_relation_candidates: bool = True,
        similarity_threshold: float = 0.85,
        use_llm_validation: bool = True,
        max_candidates: int = 1000,
        alias_relation: str = "alias_of",
        alias_relation_names: List[str] = None
    ) -> Dict[str, Any]:
        """
        Main entry point: Head deduplication with logical relations enhancement.
        
        This method combines:
        1. Semantic similarity-based candidate generation (embeddings)
        2. Logical relation-based candidate generation (graph structure)
        3. LLM validation for all candidates
        4. Alias-based merging (preserving both entities)
        
        Args:
            enable_semantic: Enable semantic similarity candidates
            enable_relation_candidates: Enable relation-based candidates
            similarity_threshold: Threshold for semantic candidates
            use_llm_validation: Use LLM to validate candidates
            max_candidates: Maximum total candidates
            alias_relation: Name of alias relationship to create
            alias_relation_names: List of relation names indicating aliases
        
        Returns:
            Statistics dict with deduplication results
        """
        logger.info("=" * 70)
        logger.info("Head Deduplication (Semantic + Logical Relations)")
        logger.info("=" * 70)
        logger.info(f"Configuration:")
        logger.info(f"  - Enable semantic candidates: {enable_semantic}")
        logger.info(f"  - Enable relation candidates: {enable_relation_candidates}")
        logger.info(f"  - Similarity threshold: {similarity_threshold}")
        logger.info(f"  - Use LLM validation: {use_llm_validation}")
        logger.info(f"  - Max candidates: {max_candidates}")
        logger.info(f"  - Alias relation: {alias_relation}")
        if alias_relation_names:
            logger.info(f"  - Alias relation names: {alias_relation_names}")
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
        
        # Apply exact matches with alias approach
        exact_stats = self._merge_head_nodes_with_alias(
            exact_merge_mapping,
            {},
            alias_relation
        )
        logger.info(f"✓ Created {exact_stats['alias_relations_created']} alias relationships")
        
        # Phase 3: Enhanced semantic + relation deduplication
        semantic_stats = {"alias_relations_created": 0, "edges_transferred": 0}
        relation_based_count = 0
        
        if enable_semantic or enable_relation_candidates:
            logger.info("\n[Phase 3/4] Enhanced deduplication (Semantic + Relations)...")
            
            # Get remaining nodes (exclude already processed)
            remaining_nodes = [
                node_id for node_id in candidates
                if node_id not in exact_merge_mapping and
                   node_id in self.graph and
                   self.graph.nodes[node_id].get("properties", {}).get("node_role") != "alias"
            ]
            logger.info(f"  Remaining nodes: {len(remaining_nodes)}")
            
            if len(remaining_nodes) >= 2:
                # Generate candidates using BOTH approaches
                if enable_semantic:
                    candidate_pairs = self._generate_semantic_and_relation_candidates(
                        remaining_nodes,
                        max_candidates=max_candidates,
                        similarity_threshold=0.75,  # Pre-filtering threshold
                        enable_relation_candidates=enable_relation_candidates,
                        alias_relation_names=alias_relation_names
                    )
                else:
                    # Only relation-based candidates
                    if enable_relation_candidates:
                        logger.info("Generating relation-based candidates only...")
                        relation_candidates = self._extract_alias_relation_candidates(
                            remaining_nodes,
                            alias_relation_names=alias_relation_names
                        )
                        candidate_pairs = [
                            (u, v, 1.0, f"relation:{rel}")
                            for u, v, rel in relation_candidates
                        ]
                    else:
                        candidate_pairs = []
                
                logger.info(f"✓ Total candidates: {len(candidate_pairs)}")
                
                # Count relation-based candidates
                relation_based_count = len([
                    c for c in candidate_pairs if c[3].startswith("relation:")
                ])
                logger.info(
                    f"  - Relation-based: {relation_based_count}"
                )
                logger.info(
                    f"  - Semantic-based: {len(candidate_pairs) - relation_based_count}"
                )
                
                if candidate_pairs:
                    # Validate candidates
                    if use_llm_validation:
                        logger.info("  Using LLM validation...")
                        # Convert to format expected by LLM validator
                        # Remove source_type for LLM call, but keep it for metadata
                        pairs_for_llm = [
                            (node_id_1, node_id_2, similarity)
                            for node_id_1, node_id_2, similarity, _ in candidate_pairs
                        ]
                        source_types = {
                            (node_id_1, node_id_2): source_type
                            for node_id_1, node_id_2, _, source_type in candidate_pairs
                        }
                        
                        # Call LLM validator (v2 if available, else v1)
                        if hasattr(self, '_validate_candidates_with_llm_v2'):
                            semantic_merge_mapping, metadata = self._validate_candidates_with_llm_v2(
                                pairs_for_llm,
                                similarity_threshold
                            )
                        else:
                            semantic_merge_mapping, metadata = self._validate_candidates_with_llm(
                                pairs_for_llm,
                                similarity_threshold
                            )
                        
                        # Add source_type to metadata
                        for (node_id_1, node_id_2), source_type in source_types.items():
                            # Find which node is in the merge mapping
                            if node_id_1 in metadata:
                                metadata[node_id_1]["source_type"] = source_type
                            elif node_id_2 in metadata:
                                metadata[node_id_2]["source_type"] = source_type
                    else:
                        logger.info("  Using embedding validation...")
                        pairs_for_embedding = [
                            (node_id_1, node_id_2, similarity)
                            for node_id_1, node_id_2, similarity, _ in candidate_pairs
                        ]
                        semantic_merge_mapping, metadata = self._validate_candidates_with_embedding(
                            pairs_for_embedding,
                            similarity_threshold
                        )
                    
                    logger.info(f"✓ Identified {len(semantic_merge_mapping)} matches")
                    
                    # Revise representative selection if method exists
                    if hasattr(self, '_revise_representative_selection_llm_driven'):
                        semantic_merge_mapping = self._revise_representative_selection_llm_driven(
                            semantic_merge_mapping,
                            metadata
                        )
                    
                    # Apply merges with alias approach
                    semantic_stats = self._merge_head_nodes_with_alias(
                        semantic_merge_mapping,
                        metadata,
                        alias_relation
                    )
                    logger.info(f"✓ Created {semantic_stats['alias_relations_created']} alias relationships")
        else:
            logger.info("\n[Phase 3/4] Enhanced deduplication skipped")
        
        # Phase 4: Validation
        logger.info("\n[Phase 4/4] Validating graph integrity...")
        issues = self.validate_graph_integrity_with_alias()
        
        if any(v for v in issues.values() if v):
            logger.warning(f"⚠ Found integrity issues: {issues}")
        else:
            logger.info("✓ Graph integrity validated")
        
        elapsed_time = time.time() - start_time
        
        # Statistics
        final_main_count = len([
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
            "relation_based_candidates": relation_based_count,
            "initial_entity_count": len(candidates),
            "final_main_entity_count": final_main_count,
            "final_alias_count": alias_count,
            "elapsed_time_seconds": elapsed_time,
            "integrity_issues": issues,
            "method": "semantic_and_logical_relations"
        }
        
        logger.info("\n" + "=" * 70)
        logger.info("Head Deduplication Completed (Semantic + Relations)")
        logger.info("=" * 70)
        logger.info(f"Summary:")
        logger.info(f"  - Initial entities: {stats['initial_entity_count']}")
        logger.info(f"  - Final main entities: {stats['final_main_entity_count']}")
        logger.info(f"  - Final alias entities: {stats['final_alias_count']}")
        logger.info(f"  - Total alias relations: {stats['total_alias_created']}")
        logger.info(f"    • From exact matches: {stats['exact_alias_created']}")
        logger.info(f"    • From semantic+relation matches: {stats['semantic_alias_created']}")
        logger.info(f"  - Relation-based candidates: {stats['relation_based_candidates']}")
        logger.info(f"  - Time elapsed: {elapsed_time:.2f}s")
        logger.info("=" * 70)
        
        return stats
