"""
Head Deduplication with LLM-Driven Representative Selection

This improved version delegates the representative selection decision to LLM,
which is more intelligent than simple heuristics like string length comparison.

Key Improvements:
1. LLM decides which entity should be the primary representative
2. Considers semantic, contextual, and domain-specific factors
3. More accurate than code-based heuristics

Author: Knowledge Graph Team
Date: 2025-10-28 (Updated)
"""

import copy
import time
from typing import Dict, List, Tuple, Any
from utils.logger import logger


class HeadDeduplicationLLMDrivenMixin:
    """
    Improved head deduplication with LLM-driven representative selection.
    """
    
    def _validate_candidates_with_llm_v2(
        self,
        candidate_pairs: List[Tuple[str, str, float]],
        threshold: float = 0.85
    ) -> Tuple[Dict[str, str], Dict[str, dict]]:
        """
        Validate candidates using LLM with representative selection.
        
        This version asks LLM to:
        1. Determine if entities are coreferent
        2. Choose which entity should be the primary representative
        
        Args:
            candidate_pairs: List of (node_id_1, node_id_2, similarity)
            threshold: Confidence threshold (not used for representative selection)
            
        Returns:
            (merge_mapping, metadata): {duplicate_id: representative_id}, metadata
        """
        logger.info(f"Validating {len(candidate_pairs)} candidates with LLM (v2: LLM-driven representative)...")
        
        # Build prompts
        prompts = []
        for node_id_1, node_id_2, embedding_sim in candidate_pairs:
            prompt_text = self._build_head_dedup_prompt_v2(node_id_1, node_id_2)
            prompts.append({
                "prompt": prompt_text,
                "metadata": {
                    "node_id_1": node_id_1,
                    "node_id_2": node_id_2,
                    "embedding_similarity": embedding_sim
                }
            })
        
        # Concurrent LLM calls
        logger.info(f"Sending {len(prompts)} requests to LLM...")
        llm_results = self._concurrent_llm_calls(prompts)
        
        # Parse results
        merge_mapping = {}
        metadata = {}
        
        for result in llm_results:
            meta = result.get("metadata", {})
            response = result.get("response", "")
            
            # Parse LLM response
            parsed = self._parse_coreference_response_v2(response)
            is_coreferent = parsed.get("is_coreferent", False)
            preferred_representative = parsed.get("preferred_representative")
            rationale = parsed.get("rationale", "")
            
            if is_coreferent and preferred_representative:
                node_id_1 = meta["node_id_1"]
                node_id_2 = meta["node_id_2"]
                
                # Validate that preferred_representative is one of the two entities
                if preferred_representative not in [node_id_1, node_id_2]:
                    logger.warning(
                        f"LLM returned invalid representative {preferred_representative} "
                        f"for pair ({node_id_1}, {node_id_2}). Skipping."
                    )
                    continue
                
                # Determine canonical and duplicate based on LLM's choice
                canonical = preferred_representative
                duplicate = node_id_2 if canonical == node_id_1 else node_id_1
                
                # Record the merge decision
                merge_mapping[duplicate] = canonical
                metadata[duplicate] = {
                    "rationale": rationale,
                    "confidence": 1.0,  # LLM made the decision
                    "embedding_similarity": meta.get("embedding_similarity", 0.0),
                    "method": "llm_v2",
                    "llm_chosen_representative": canonical
                }
                
                logger.debug(
                    f"LLM decided: {duplicate} is alias of {canonical} "
                    f"(rationale: {rationale[:100]}...)"
                )
        
        logger.info(f"LLM validated {len(merge_mapping)} merges with representative selection")
        return merge_mapping, metadata
    
    def _collect_chunk_context(self, node_id: str, max_length: int = 500) -> str:
        """
        Collect chunk text context for a node.
        
        Args:
            node_id: Node ID
            max_length: Maximum length of chunk text to include (characters)
            
        Returns:
            Formatted chunk context string
        """
        if node_id not in self.graph:
            return "  (Node not found in graph)"
        
        node_data = self.graph.nodes[node_id]
        properties = node_data.get("properties", {})
        chunk_id = properties.get("chunk id") or properties.get("chunk_id")
        
        if not chunk_id:
            return "  (No chunk information)"
        
        chunk_text = self.all_chunks.get(chunk_id)
        if not chunk_text:
            return f"  (Chunk {chunk_id} not found)"
        
        # Truncate if too long
        if len(chunk_text) > max_length:
            chunk_text = chunk_text[:max_length] + "..."
        
        return f"  Source text: \"{chunk_text}\""
    
    def _build_head_dedup_prompt_v2(self, node_id_1: str, node_id_2: str) -> str:
        """
        Build improved LLM prompt that asks for representative selection.
        
        Args:
            node_id_1, node_id_2: Entity IDs
            
        Returns:
            Complete prompt text
        """
        # Get entity descriptions
        desc_1 = self._describe_node(node_id_1)
        desc_2 = self._describe_node(node_id_2)
        
        # Get graph context (always included)
        context_1 = self._collect_node_context(node_id_1, max_relations=10)
        context_2 = self._collect_node_context(node_id_2, max_relations=10)
        
        # Check if hybrid context is enabled
        config = self.config.construction.semantic_dedup.head_dedup if hasattr(
            self.config.construction.semantic_dedup, 'head_dedup'
        ) else None
        
        use_hybrid_context = False
        if config:
            use_hybrid_context = getattr(config, 'use_hybrid_context', False)
        
        # Add chunk context if hybrid mode is enabled
        if use_hybrid_context:
            chunk_context_1 = self._collect_chunk_context(node_id_1)
            chunk_context_2 = self._collect_chunk_context(node_id_2)
            
            # Combine graph relations and chunk text
            context_1 = f"{context_1}\n{chunk_context_1}"
            context_2 = f"{context_2}\n{chunk_context_2}"
        
        # Try to load from config first
        try:
            prompt_template = self.config.get_prompt_formatted(
                "head_dedup", 
                "with_representative_selection",  # New template
                entity_1_id=node_id_1,
                entity_1_desc=desc_1,
                context_1=context_1,
                entity_2_id=node_id_2,
                entity_2_desc=desc_2,
                context_2=context_2
            )
            return prompt_template
        except Exception as e:
            # Fallback to embedded template
            logger.warning(f"Failed to load prompt from config: {e}. Using embedded template.")
            return self._get_embedded_prompt_template_v2(
                node_id_1, desc_1, context_1,
                node_id_2, desc_2, context_2
            )
    
    def _get_embedded_prompt_template_v2(
        self, 
        entity_1_id: str, entity_1_desc: str, context_1: str,
        entity_2_id: str, entity_2_desc: str, context_2: str
    ) -> str:
        """
        Embedded prompt template with representative selection.
        """
        return f"""You are an expert in knowledge graph entity resolution.

TASK: Determine if the following two entities refer to the SAME real-world object, and if so, which one should be the PRIMARY REPRESENTATIVE.

Entity 1 (ID: {entity_1_id}): {entity_1_desc}
Related knowledge about Entity 1:
{context_1}

Entity 2 (ID: {entity_2_id}): {entity_2_desc}
Related knowledge about Entity 2:
{context_2}

CRITICAL RULES:

1. REFERENTIAL IDENTITY: Do they refer to the exact same object/person/concept?
   - Same entity with different names → YES (e.g., "NYC" = "New York City")
   - Different but related entities → NO (e.g., "Apple Inc." ≠ "Apple Store")

2. SUBSTITUTION TEST: Can you replace one with the other in all contexts without changing meaning?

3. PRIMARY REPRESENTATIVE SELECTION (if they are coreferent):
   Choose the entity that should serve as the main reference based on:
   
   a) **Formality and Completeness**:
      - Full name > Abbreviation (e.g., "World Health Organization" > "WHO")
      - BUT: Common abbreviations may be preferred (e.g., "AI" in tech context)
   
   b) **Domain Convention**:
      - Medical: Prefer standard terminology
      - Popular: Prefer commonly used form
      - Academic: Prefer formal names
   
   c) **Information Richness** (visible in the graph):
      - Entity with more relationships → Better representative
      - Entity with more context → Better representative
   
   d) **Naming Quality**:
      - Official name > Colloquial name
      - Standard spelling > Variant spelling

4. CONSERVATIVE PRINCIPLE:
   - When uncertain about coreference → answer NO
   - When uncertain about representative → choose the one with more graph connections

OUTPUT FORMAT (strict JSON):
{{
  "is_coreferent": true/false,
  "preferred_representative": "{entity_1_id}" or "{entity_2_id}" or null,
  "rationale": "Explain: (1) WHY they are the same/different, (2) If same, WHY you chose this representative"
}}

IMPORTANT:
- Set "preferred_representative" ONLY if "is_coreferent" is true
- The ID must be exactly "{entity_1_id}" or "{entity_2_id}"
- Explain your representative choice clearly
"""
    
    def _parse_coreference_response_v2(self, response: str) -> dict:
        """
        Parse LLM response with representative selection.
        
        Expected format:
        {
          "is_coreferent": true/false,
          "preferred_representative": "entity_XXX" or null,
          "rationale": "..."
        }
        
        Args:
            response: LLM JSON response
            
        Returns:
            Parsed dict with is_coreferent, preferred_representative, rationale
        """
        try:
            import json_repair
            parsed = json_repair.loads(response)
            
            is_coreferent = bool(parsed.get("is_coreferent", False))
            preferred_representative = parsed.get("preferred_representative")
            rationale = str(parsed.get("rationale", ""))
            
            # Validate
            if is_coreferent and not preferred_representative:
                logger.warning(
                    f"LLM said is_coreferent=true but didn't provide preferred_representative. "
                    f"Response: {response[:200]}"
                )
                # Don't mark as coreferent if no representative
                is_coreferent = False
            
            if not is_coreferent:
                preferred_representative = None
            
            return {
                "is_coreferent": is_coreferent,
                "preferred_representative": preferred_representative,
                "rationale": rationale
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            logger.debug(f"Response: {response[:500]}...")
            return {
                "is_coreferent": False,
                "preferred_representative": None,
                "rationale": "Parse error"
            }
    
    def _revise_representative_selection_llm_driven(
        self, 
        merge_mapping: Dict[str, str],
        metadata: Dict[str, dict]
    ) -> Dict[str, str]:
        """
        Revised version: Trust LLM's representative selection.
        
        This function now does minimal post-processing, mainly handling
        transitive cases where LLM decisions need to be reconciled.
        
        Example:
          LLM says: A -> B (B is representative)
          LLM says: B -> C (C is representative)
          Result: Both A and B should point to C
        
        Args:
            merge_mapping: Initial {duplicate: canonical} from LLM
            metadata: Metadata containing LLM's rationale
            
        Returns:
            Revised merge_mapping handling transitivity
        """
        from collections import defaultdict
        
        # Build a graph of merge relationships
        parent = {}
        
        def find(x):
            if x not in parent:
                parent[x] = x
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(duplicate, canonical):
            # Canonical is preferred, so canonical becomes the root
            pd, pc = find(duplicate), find(canonical)
            if pd != pc:
                parent[pd] = pc  # Duplicate's root points to canonical's root
        
        # Apply all LLM decisions
        for duplicate, canonical in merge_mapping.items():
            union(duplicate, canonical)
        
        # Build final mapping
        revised_mapping = {}
        for duplicate, original_canonical in merge_mapping.items():
            final_canonical = find(duplicate)
            if duplicate != final_canonical:
                revised_mapping[duplicate] = final_canonical
                
                # Update metadata if changed
                if final_canonical != original_canonical:
                    logger.debug(
                        f"Transitive merge: {duplicate} -> {original_canonical} "
                        f"revised to {duplicate} -> {final_canonical}"
                    )
        
        return revised_mapping
    
    def deduplicate_heads_with_llm_v2(
        self,
        enable_semantic: bool = True,
        similarity_threshold: float = 0.85,
        max_candidates: int = 1000,
        alias_relation: str = "alias_of"
    ) -> Dict[str, Any]:
        """
        Main entry: Head deduplication with LLM-driven representative selection.
        
        Key difference from v1:
        - LLM decides which entity should be the representative
        - No code-based heuristics for representative selection
        - More accurate and context-aware
        
        Args:
            enable_semantic: Enable semantic deduplication
            similarity_threshold: Embedding similarity threshold for candidate generation
            max_candidates: Maximum candidate pairs
            alias_relation: Name of alias relationship
            
        Returns:
            Statistics dict
        """
        logger.info("=" * 70)
        logger.info("Head Deduplication (LLM-Driven Representative Selection)")
        logger.info("=" * 70)
        
        start_time = time.time()
        
        # Phase 1: Collect candidates
        logger.info("\n[Phase 1/4] Collecting head candidates...")
        candidates = self._collect_head_candidates()
        logger.info(f"✓ Found {len(candidates)} entity nodes")
        
        # Phase 2: Exact match
        logger.info("\n[Phase 2/4] Exact match deduplication...")
        exact_merge_mapping = self._deduplicate_heads_exact(candidates)
        logger.info(f"✓ Identified {len(exact_merge_mapping)} exact matches")
        
        # For exact matches, use simple heuristic (ID order) since names are identical
        exact_stats = self._merge_head_nodes_with_alias(
            exact_merge_mapping, 
            {},
            alias_relation
        )
        logger.info(f"✓ Created {exact_stats['alias_relations_created']} alias relationships")
        
        # Phase 3: Semantic deduplication with LLM
        semantic_stats = {"alias_relations_created": 0, "edges_transferred": 0}
        
        if enable_semantic:
            logger.info("\n[Phase 3/4] Semantic deduplication (LLM-driven)...")
            
            remaining_nodes = [
                node_id for node_id in candidates
                if node_id not in exact_merge_mapping and 
                   node_id in self.graph and
                   self.graph.nodes[node_id].get("properties", {}).get("node_role") != "alias"
            ]
            logger.info(f"  Remaining nodes: {len(remaining_nodes)}")
            
            if len(remaining_nodes) >= 2:
                # Generate candidate pairs
                candidate_pairs = self._generate_semantic_candidates(
                    remaining_nodes,
                    max_candidates=max_candidates,
                    similarity_threshold=0.75  # Pre-filtering threshold
                )
                logger.info(f"✓ Generated {len(candidate_pairs)} candidate pairs")
                
                if candidate_pairs:
                    # LLM validation with representative selection
                    logger.info("  Using LLM to validate AND select representatives...")
                    semantic_merge_mapping, metadata = self._validate_candidates_with_llm_v2(
                        candidate_pairs,
                        similarity_threshold
                    )
                    
                    logger.info(f"✓ LLM identified {len(semantic_merge_mapping)} semantic matches")
                    
                    # Handle transitivity
                    semantic_merge_mapping = self._revise_representative_selection_llm_driven(
                        semantic_merge_mapping,
                        metadata
                    )
                    
                    # Apply merges
                    semantic_stats = self._merge_head_nodes_with_alias(
                        semantic_merge_mapping,
                        metadata,
                        alias_relation
                    )
                    logger.info(f"✓ Created {semantic_stats['alias_relations_created']} alias relationships")
        else:
            logger.info("\n[Phase 3/4] Semantic deduplication skipped")
        
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
            "initial_entity_count": len(candidates),
            "final_main_entity_count": final_main_count,
            "final_alias_count": alias_count,
            "elapsed_time_seconds": elapsed_time,
            "integrity_issues": issues,
            "method": "llm_driven_v2"
        }
        
        logger.info("\n" + "=" * 70)
        logger.info("Head Deduplication Completed (LLM-Driven)")
        logger.info("=" * 70)
        logger.info(f"Summary:")
        logger.info(f"  - Initial entities: {stats['initial_entity_count']}")
        logger.info(f"  - Final main entities: {stats['final_main_entity_count']}")
        logger.info(f"  - Final alias entities: {stats['final_alias_count']}")
        logger.info(f"  - Total alias relations: {stats['total_alias_created']}")
        logger.info(f"  - Time elapsed: {elapsed_time:.2f}s")
        logger.info(f"  - Representative selection: LLM-driven ✓")
        logger.info("=" * 70)
        
        return stats
