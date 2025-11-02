"""
Multi-Signal Head Entity Deduplication - Complete Implementation

This module implements a comprehensive multi-signal approach for head entity deduplication,
addressing the limitation of relying solely on name semantic similarity.

Key Features:
1. Signal 1: Semantic Similarity (name-based)
2. Signal 2: Subgraph Structure Similarity (relation pattern-based)
3. Signal 3: Explicit Alias Relations (graph-based)
4. Signal 4: Attribute Overlap (property-based)
5. Multi-signal fusion with configurable weights
6. Enhanced LLM validation with signal context

Author: Knowledge Graph Team
Date: 2025-11-02
"""

import copy
import time
import numpy as np
from typing import Dict, List, Tuple, Any, Set
from collections import defaultdict
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm

from utils.logger import logger
import json_repair


class MultiSignalHeadDeduplication:
    """
    Multi-signal head entity deduplication mixin.
    
    This can be mixed into KnowledgeTreeGen to provide enhanced deduplication.
    """
    
    # ============================================================
    # Signal 1: Semantic Similarity (Original)
    # ============================================================
    
    # Keep existing _generate_semantic_candidates() implementation
    # (already in head_deduplication_reference.py)
    
    # ============================================================
    # Signal 2: Subgraph Structure Similarity (NEW)
    # ============================================================
    
    def _compute_subgraph_fingerprint(
        self, 
        node_id: str, 
        depth: int = 1
    ) -> Dict[str, float]:
        """
        Compute structural fingerprint of a node's subgraph.
        
        Key Insight: Instead of requiring exact subgraph match, we extract
        statistical features (relation distribution, neighbor types) that can
        be compared using similarity metrics.
        
        Example:
            Gibbs Artifact:
                Out: {"is_a": 1, "alias_of": 1, "definition": 1, "manifestation": 1}
                In: {}
            
            Truncation Artifact:
                Out: {"contained_in": 1, "solution": 1}
                In: {"alias_of": 1}
            
            Fingerprint vectors:
                V1 = [is_a:1, alias_of:1, definition:1, manifestation:1, ...]
                V2 = [is_a:0, alias_of:1, solution:1, contained_in:1, ...]
            
            Structural similarity = cosine(V1, V2) = 0.45 (due to shared alias_of)
        
        Args:
            node_id: Entity node ID
            depth: Subgraph depth (1=immediate neighbors, 2=2-hop neighbors)
            
        Returns:
            Dict mapping feature names to counts
        """
        if node_id not in self.graph:
            return {}
        
        fingerprint = defaultdict(float)
        
        # 1. Outgoing relation distribution
        for _, _, data in self.graph.out_edges(node_id, data=True):
            relation = data.get("relation", "unknown")
            fingerprint[f"out:{relation}"] += 1.0
        
        # 2. Incoming relation distribution
        for _, _, data in self.graph.in_edges(node_id, data=True):
            relation = data.get("relation", "unknown")
            fingerprint[f"in:{relation}"] += 1.0
        
        # 3. Neighbor node type distribution (if schema_type exists)
        try:
            neighbors = list(self.graph.neighbors(node_id))
            for neighbor in neighbors:
                neighbor_data = self.graph.nodes.get(neighbor, {})
                neighbor_type = neighbor_data.get("properties", {}).get(
                    "schema_type", 
                    neighbor_data.get("label", "entity")
                )
                fingerprint[f"neighbor_type:{neighbor_type}"] += 1.0
        except:
            pass
        
        # 4. Degree features
        fingerprint["out_degree"] = float(self.graph.out_degree(node_id))
        fingerprint["in_degree"] = float(self.graph.in_degree(node_id))
        
        # 5. If depth > 1, recursively collect 2-hop information (with decay)
        if depth > 1:
            try:
                neighbors = list(self.graph.neighbors(node_id))
                for neighbor in neighbors:
                    if neighbor == node_id:  # Skip self-loops
                        continue
                    
                    sub_fingerprint = self._compute_subgraph_fingerprint(neighbor, depth=1)
                    for key, value in sub_fingerprint.items():
                        # 2-hop features with decay weight
                        fingerprint[f"2hop:{key}"] += value * 0.5
            except:
                pass
        
        return dict(fingerprint)
    
    def _generate_subgraph_candidates(
        self,
        remaining_nodes: List[str],
        subgraph_similarity_threshold: float = 0.6,
        subgraph_depth: int = 1
    ) -> List[Tuple[str, str, float]]:
        """
        Generate candidate pairs based on subgraph structure similarity.
        
        Key Advantage: Even if entity names are semantically dissimilar,
        similar structural patterns may indicate alias relationship.
        
        Args:
            remaining_nodes: List of node IDs to consider
            subgraph_similarity_threshold: Minimum structure similarity
            subgraph_depth: Subgraph extraction depth
            
        Returns:
            List of (node_1, node_2, similarity) tuples
        """
        if len(remaining_nodes) < 2:
            return []
        
        logger.info(f"[SubgraphSignal] Computing subgraph fingerprints (depth={subgraph_depth})...")
        
        # 1. Compute fingerprints for all nodes
        fingerprints = {}
        for node_id in tqdm(remaining_nodes, desc="Computing fingerprints", disable=True):
            try:
                fp = self._compute_subgraph_fingerprint(node_id, depth=subgraph_depth)
                if fp:  # Only include non-empty fingerprints
                    fingerprints[node_id] = fp
            except Exception as e:
                logger.debug(f"Failed to compute fingerprint for {node_id}: {e}")
                continue
        
        if len(fingerprints) < 2:
            logger.info("[SubgraphSignal] Not enough valid fingerprints")
            return []
        
        logger.info(f"[SubgraphSignal] Computed {len(fingerprints)} valid fingerprints")
        
        # 2. Vectorize fingerprints
        try:
            vectorizer = DictVectorizer()
            nodes = list(fingerprints.keys())
            vectors = vectorizer.fit_transform([fingerprints[n] for n in nodes])
            
            logger.info(f"[SubgraphSignal] Vectorized to shape {vectors.shape}")
        except Exception as e:
            logger.error(f"[SubgraphSignal] Vectorization failed: {e}")
            return []
        
        # 3. Compute pairwise cosine similarity
        try:
            similarity_matrix = cosine_similarity(vectors)
        except Exception as e:
            logger.error(f"[SubgraphSignal] Similarity computation failed: {e}")
            return []
        
        # 4. Extract candidate pairs
        candidates = []
        n = len(nodes)
        
        for i in range(n):
            for j in range(i + 1, n):
                sim = similarity_matrix[i][j]
                if sim >= subgraph_similarity_threshold:
                    candidates.append((nodes[i], nodes[j], float(sim)))
        
        logger.info(f"[SubgraphSignal] Found {len(candidates)} candidates above threshold")
        return candidates
    
    # ============================================================
    # Signal 3: Explicit Alias Relations (NEW)
    # ============================================================
    
    def _extract_explicit_alias_candidates(
        self,
        remaining_nodes: Set[str] = None
    ) -> List[Tuple[str, str, float, str]]:
        """
        Extract explicit alias relationships from the graph as strong signals.
        
        Strategy:
        1. Direct alias edges: A --[alias_of/别名包括]--> B
        2. Mutual aliases: A --[alias]--> B AND B --[alias]--> A
        3. Transitive aliases: A --[alias]--> C, B --[alias]--> C => A~B
        4. Semantic equivalence relations: also_known_as, same_as, etc.
        
        Args:
            remaining_nodes: Set of node IDs to filter (optional)
            
        Returns:
            List of (entity1, entity2, confidence, reason) tuples
        """
        logger.info("[AliasSignal] Extracting explicit alias relationships...")
        
        # Define alias relation patterns (configurable)
        alias_relations = {
            "别名包括", "alias_of", "also_known_as", "same_as", 
            "equivalent_to", "is_alias_of", "aka", "又称",
            "also_called", "known_as"
        }
        
        candidates = []
        direct_aliases = 0
        
        # 1. Direct alias relationships
        for head, tail, data in self.graph.edges(data=True):
            relation = data.get("relation", "")
            
            # Check if it's an alias relation
            if relation in alias_relations:
                # Ensure both are entity nodes
                head_label = self.graph.nodes.get(head, {}).get("label")
                tail_label = self.graph.nodes.get(tail, {}).get("label")
                
                if head_label == "entity" and tail_label == "entity":
                    # Filter by remaining_nodes if provided
                    if remaining_nodes is not None:
                        if head not in remaining_nodes or tail not in remaining_nodes:
                            continue
                    
                    candidates.append((
                        head, 
                        tail, 
                        1.0,  # High confidence
                        f"explicit_alias:{relation}"
                    ))
                    direct_aliases += 1
                    
                    logger.debug(
                        f"[AliasSignal] {self._get_entity_name(head)} "
                        f"--[{relation}]--> {self._get_entity_name(tail)}"
                    )
        
        logger.info(f"[AliasSignal] Found {direct_aliases} direct alias relations")
        
        # 2. Transitive aliases (shared alias hub)
        # If A --[alias]--> C and B --[alias]--> C, then A~B (with lower confidence)
        alias_hubs = defaultdict(set)
        
        for head, tail, data in self.graph.edges(data=True):
            if data.get("relation") in alias_relations:
                if self.graph.nodes.get(head, {}).get("label") == "entity":
                    alias_hubs[tail].add(head)
        
        transitive_count = 0
        for hub, aliases in alias_hubs.items():
            if len(aliases) >= 2:
                alias_list = list(aliases)
                for i, alias_1 in enumerate(alias_list):
                    for alias_2 in alias_list[i+1:]:
                        # Filter by remaining_nodes
                        if remaining_nodes is not None:
                            if alias_1 not in remaining_nodes or alias_2 not in remaining_nodes:
                                continue
                        
                        # Check if not already in direct aliases
                        if not any(
                            (a1, a2) == (alias_1, alias_2) or (a1, a2) == (alias_2, alias_1)
                            for a1, a2, _, _ in candidates
                        ):
                            candidates.append((
                                alias_1,
                                alias_2,
                                0.8,  # Transitive confidence (slightly lower)
                                f"transitive_alias_via:{hub}"
                            ))
                            transitive_count += 1
        
        logger.info(f"[AliasSignal] Found {transitive_count} transitive alias pairs")
        logger.info(f"[AliasSignal] Total: {len(candidates)} alias candidates")
        
        return candidates
    
    # ============================================================
    # Signal 4: Attribute Overlap (NEW)
    # ============================================================
    
    def _generate_attribute_overlap_candidates(
        self,
        remaining_nodes: List[str],
        min_overlap_ratio: float = 0.6
    ) -> List[Tuple[str, str, float]]:
        """
        Generate candidate pairs based on attribute overlap.
        
        Intuition: If two entities share many properties (definition, description,
        type, etc.), they might be referring to the same concept with different names.
        
        Example:
            Entity A: {name: "Gibbs Artifact", definition: "MRI artifact due to...", type: "artifact"}
            Entity B: {name: "吉布斯伪影", definition: "MRI artifact due to...", type: "artifact"}
            
            High attribute overlap (same definition) → likely aliases
        
        Args:
            remaining_nodes: List of node IDs
            min_overlap_ratio: Minimum Jaccard similarity for attributes
            
        Returns:
            List of (node_1, node_2, jaccard_similarity) tuples
        """
        if len(remaining_nodes) < 2:
            return []
        
        logger.info("[AttributeSignal] Computing attribute overlap...")
        
        # 1. Extract attribute sets for each node
        attribute_sets = {}
        
        for node_id in remaining_nodes:
            if node_id not in self.graph:
                continue
            
            props = self.graph.nodes[node_id].get("properties", {})
            
            # Extract key attributes (excluding name and technical fields)
            attr_values = []
            for key in ["definition", "description", "type", "category", "schema_type"]:
                value = props.get(key)
                if value and value not in (None, "", []):
                    # Normalize
                    value_str = str(value).strip().lower()
                    if value_str:
                        attr_values.append(f"{key}:{value_str}")
            
            if attr_values:
                attribute_sets[node_id] = set(attr_values)
        
        if len(attribute_sets) < 2:
            logger.info("[AttributeSignal] Not enough nodes with attributes")
            return []
        
        logger.info(f"[AttributeSignal] Collected attributes for {len(attribute_sets)} nodes")
        
        # 2. Compute Jaccard similarity for all pairs
        candidates = []
        nodes = list(attribute_sets.keys())
        n = len(nodes)
        
        for i in range(n):
            for j in range(i + 1, n):
                set_i = attribute_sets[nodes[i]]
                set_j = attribute_sets[nodes[j]]
                
                # Jaccard similarity
                intersection = len(set_i & set_j)
                union = len(set_i | set_j)
                
                if union > 0:
                    jaccard = intersection / union
                    
                    if jaccard >= min_overlap_ratio:
                        candidates.append((nodes[i], nodes[j], jaccard))
        
        logger.info(f"[AttributeSignal] Found {len(candidates)} candidates")
        return candidates
    
    # ============================================================
    # Multi-Signal Fusion
    # ============================================================
    
    def _generate_multi_signal_candidates(
        self,
        remaining_nodes: List[str],
        config: Dict[str, Any]
    ) -> List[Tuple[str, str, float, Dict]]:
        """
        Generate candidate pairs using multiple signals with fusion.
        
        This is the core of the multi-signal approach: collect candidates from
        all signals, fuse their scores with configurable weights, and return
        a ranked list.
        
        Args:
            remaining_nodes: List of entity node IDs
            config: Configuration dict with:
                - enable_semantic_signal: bool
                - enable_subgraph_signal: bool
                - enable_alias_signal: bool
                - enable_attribute_signal: bool
                - semantic_threshold: float
                - subgraph_threshold: float
                - attribute_threshold: float
                - signal_weights: dict
                
        Returns:
            List of (entity1, entity2, fusion_score, signals_dict) tuples
        """
        logger.info("=" * 70)
        logger.info("Multi-Signal Candidate Generation")
        logger.info("=" * 70)
        
        # Storage: {(e1, e2): {"signals": {...}, "entities": (e1, e2)}}
        all_candidates = defaultdict(lambda: {
            "signals": {},
            "entities": None
        })
        
        # Signal 1: Semantic similarity (original)
        if config.get("enable_semantic_signal", True):
            logger.info("\n[Signal 1/4] Semantic Similarity...")
            try:
                semantic_candidates = self._generate_semantic_candidates(
                    remaining_nodes,
                    max_candidates=config.get("max_semantic_candidates", 2000),
                    similarity_threshold=config.get("semantic_threshold", 0.75)
                )
                
                for e1, e2, sim in semantic_candidates:
                    key = tuple(sorted([e1, e2]))
                    all_candidates[key]["entities"] = (e1, e2)
                    all_candidates[key]["signals"]["semantic"] = sim
                
                logger.info(f"  ✓ Collected {len(semantic_candidates)} semantic candidates")
            except Exception as e:
                logger.error(f"  ✗ Semantic signal failed: {e}")
        
        # Signal 2: Subgraph structure similarity (NEW)
        if config.get("enable_subgraph_signal", True):
            logger.info("\n[Signal 2/4] Subgraph Structure Similarity...")
            try:
                subgraph_candidates = self._generate_subgraph_candidates(
                    remaining_nodes,
                    subgraph_similarity_threshold=config.get("subgraph_threshold", 0.6),
                    subgraph_depth=config.get("subgraph_depth", 1)
                )
                
                for e1, e2, sim in subgraph_candidates:
                    key = tuple(sorted([e1, e2]))
                    all_candidates[key]["entities"] = (e1, e2)
                    all_candidates[key]["signals"]["subgraph"] = sim
                
                logger.info(f"  ✓ Collected {len(subgraph_candidates)} subgraph candidates")
            except Exception as e:
                logger.error(f"  ✗ Subgraph signal failed: {e}")
        
        # Signal 3: Explicit alias relations (NEW)
        if config.get("enable_alias_signal", True):
            logger.info("\n[Signal 3/4] Explicit Alias Relations...")
            try:
                remaining_set = set(remaining_nodes)
                alias_candidates = self._extract_explicit_alias_candidates(remaining_set)
                
                for e1, e2, conf, reason in alias_candidates:
                    key = tuple(sorted([e1, e2]))
                    all_candidates[key]["entities"] = (e1, e2)
                    all_candidates[key]["signals"]["alias"] = conf
                    all_candidates[key]["alias_reason"] = reason
                
                logger.info(f"  ✓ Collected {len(alias_candidates)} alias candidates")
            except Exception as e:
                logger.error(f"  ✗ Alias signal failed: {e}")
        
        # Signal 4: Attribute overlap (NEW)
        if config.get("enable_attribute_signal", True):
            logger.info("\n[Signal 4/4] Attribute Overlap...")
            try:
                attr_candidates = self._generate_attribute_overlap_candidates(
                    remaining_nodes,
                    min_overlap_ratio=config.get("attribute_threshold", 0.6)
                )
                
                for e1, e2, overlap in attr_candidates:
                    key = tuple(sorted([e1, e2]))
                    all_candidates[key]["entities"] = (e1, e2)
                    all_candidates[key]["signals"]["attribute"] = overlap
                
                logger.info(f"  ✓ Collected {len(attr_candidates)} attribute candidates")
            except Exception as e:
                logger.error(f"  ✗ Attribute signal failed: {e}")
        
        # Fusion: Weighted combination
        logger.info("\n[Fusion] Combining signals with weights...")
        
        weights = config.get("signal_weights", {
            "semantic": 0.30,
            "subgraph": 0.25,
            "alias": 0.35,      # Highest weight for explicit alias
            "attribute": 0.10
        })
        
        logger.info(f"  Weights: {weights}")
        
        fusion_results = []
        
        for key, data in all_candidates.items():
            signals = data["signals"]
            
            if not signals:
                continue
            
            # Weighted fusion
            fusion_score = 0.0
            active_weight_sum = 0.0
            
            for signal_name, weight in weights.items():
                if signal_name in signals:
                    fusion_score += signals[signal_name] * weight
                    active_weight_sum += weight
            
            # Normalize by active weights
            if active_weight_sum > 0:
                fusion_score = fusion_score / active_weight_sum
            
            # Boost: If explicit alias signal exists with high confidence, boost score
            if "alias" in signals and signals["alias"] >= 0.9:
                fusion_score = max(fusion_score, 0.95)
                logger.debug(f"  Boosted pair {key} due to explicit alias")
            
            e1, e2 = data["entities"]
            fusion_results.append((e1, e2, fusion_score, signals.copy()))
        
        # Sort by fusion score (descending)
        fusion_results.sort(key=lambda x: x[2], reverse=True)
        
        # Statistics
        logger.info("\n[Fusion] Statistics:")
        logger.info(f"  Total unique pairs: {len(fusion_results)}")
        
        for signal_name in weights.keys():
            count = sum(1 for _, _, _, s in fusion_results if signal_name in s)
            logger.info(f"  - {signal_name}: {count} pairs")
        
        # Signal overlap analysis
        signal_combo_counts = defaultdict(int)
        for _, _, _, signals in fusion_results:
            combo = tuple(sorted(signals.keys()))
            signal_combo_counts[combo] += 1
        
        logger.info("  Signal combinations:")
        for combo, count in sorted(signal_combo_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            logger.info(f"    {'+'.join(combo)}: {count} pairs")
        
        logger.info("=" * 70)
        
        return fusion_results
    
    # ============================================================
    # Enhanced LLM Validation with Signal Context
    # ============================================================
    
    def _validate_candidates_with_llm_multi_signal(
        self,
        candidate_pairs: List[Tuple[str, str, float, Dict]],
        threshold: float = 0.70
    ) -> Tuple[Dict[str, str], Dict[str, dict]]:
        """
        Validate candidate pairs using LLM with multi-signal context.
        
        Key Improvement: Provide LLM with all signal evidence, allowing it to
        make informed decisions based on multiple sources of information.
        
        Args:
            candidate_pairs: List of (e1, e2, fusion_score, signals) tuples
            threshold: Minimum fusion score to submit to LLM
            
        Returns:
            (merge_mapping, metadata)
        """
        logger.info(f"Validating {len(candidate_pairs)} candidates with LLM (multi-signal)...")
        logger.info(f"  Fusion score threshold: {threshold}")
        
        # Filter by threshold
        filtered_pairs = [
            (e1, e2, score, signals)
            for e1, e2, score, signals in candidate_pairs
            if score >= threshold
        ]
        
        logger.info(f"  Candidates above threshold: {len(filtered_pairs)}")
        
        if not filtered_pairs:
            return {}, {}
        
        merge_mapping = {}
        metadata = {}
        
        for entity_1, entity_2, fusion_score, signals in tqdm(
            filtered_pairs, 
            desc="LLM validation"
        ):
            # Skip if already processed (transitive)
            if entity_1 in merge_mapping or entity_2 in merge_mapping:
                continue
            
            try:
                # Format signal context for LLM
                signal_context = self._format_signals_for_llm(entity_1, entity_2, signals)
                
                # Format entity subgraphs
                subgraph_1 = self._format_entity_subgraph(entity_1, max_edges=5)
                subgraph_2 = self._format_entity_subgraph(entity_2, max_edges=5)
                
                # Build prompt
                prompt = f"""You are validating whether two entities should be merged as aliases.

Entity 1: {self._get_entity_name(entity_1)}
Entity 2: {self._get_entity_name(entity_2)}

=== Multi-Signal Evidence ===
{signal_context}

=== Entity 1 Subgraph ===
{subgraph_1}

=== Entity 2 Subgraph ===
{subgraph_2}

=== Question ===
Based on ALL the evidence above (especially explicit alias relations if present),
should these two entities be merged as aliases/coreferent entities?

Important considerations:
1. If there is an EXPLICIT alias relation between them → Strong evidence to merge
2. If their subgraphs show similar patterns → Moderate evidence to merge
3. If only name similarity → Weak evidence (need more signals to confirm)
4. If subgraphs are COMPLETELY different → May indicate distinct entities

Respond in JSON:
{{
  "should_merge": true/false,
  "confidence": 0.0-1.0,
  "rationale": "Explain your decision based on the signal evidence",
  "primary_signal": "which signal was most decisive (semantic/subgraph/alias/attribute)"
}}
"""
                
                # Call LLM
                response = self.llm_client.call_api(prompt)
                result = json_repair.loads(response)
                
                if result.get("should_merge", False):
                    # Choose representative
                    representative = self._choose_better_representative(
                        entity_1, entity_2, signals
                    )
                    duplicate = entity_2 if representative == entity_1 else entity_1
                    
                    merge_mapping[duplicate] = representative
                    metadata[duplicate] = {
                        "confidence": result.get("confidence", fusion_score),
                        "method": "multi_signal_llm",
                        "rationale": result.get("rationale", ""),
                        "primary_signal": result.get("primary_signal", "unknown"),
                        "signals": signals,
                        "fusion_score": fusion_score
                    }
                    
                    logger.debug(
                        f"  ✓ Merge: {self._get_entity_name(duplicate)} -> "
                        f"{self._get_entity_name(representative)} "
                        f"(confidence={result.get('confidence', 0):.2f}, "
                        f"signal={result.get('primary_signal', 'unknown')})"
                    )
                
            except Exception as e:
                logger.error(f"  ✗ LLM validation failed for ({entity_1}, {entity_2}): {e}")
                continue
        
        logger.info(f"✓ LLM validated {len(merge_mapping)} merge decisions")
        
        return merge_mapping, metadata
    
    def _format_signals_for_llm(
        self, 
        entity_1: str, 
        entity_2: str, 
        signals: Dict[str, float]
    ) -> str:
        """Format signal information in human-readable format for LLM."""
        lines = []
        
        # Highlight explicit alias if present
        if "alias" in signals:
            lines.append(f"🔴 EXPLICIT ALIAS RELATION: confidence={signals['alias']:.2f}")
            lines.append("   → These entities are DIRECTLY connected by an alias relation in the graph!")
            lines.append("   → This is the STRONGEST signal for merging")
            lines.append("")
        
        if "semantic" in signals:
            lines.append(f"📝 Name Semantic Similarity: {signals['semantic']:.2f}")
            lines.append("   → How similar are their names in meaning?")
        
        if "subgraph" in signals:
            lines.append(f"🔗 Subgraph Structure Similarity: {signals['subgraph']:.2f}")
            lines.append("   → Do they have similar relation patterns?")
        
        if "attribute" in signals:
            lines.append(f"📊 Attribute Overlap: {signals['attribute']:.2f}")
            lines.append("   → Do they share properties/definitions?")
        
        if not lines:
            lines.append("(No signal information available)")
        
        return "\n".join(lines)
    
    def _format_entity_subgraph(self, entity_id: str, max_edges: int = 5) -> str:
        """Format entity's local subgraph for LLM context."""
        if entity_id not in self.graph:
            return "[Entity not found]"
        
        lines = []
        entity_name = self._get_entity_name(entity_id)
        
        # Outgoing edges
        out_edges = list(self.graph.out_edges(entity_id, data=True))
        if out_edges:
            lines.append("Outgoing relations:")
            for _, tail, data in out_edges[:max_edges]:
                tail_name = self._get_entity_name(tail)
                relation = data.get("relation", "unknown")
                lines.append(f"  - {entity_name} --[{relation}]--> {tail_name}")
            
            if len(out_edges) > max_edges:
                lines.append(f"  ... and {len(out_edges) - max_edges} more")
        else:
            lines.append("Outgoing relations: (none)")
        
        # Incoming edges
        in_edges = list(self.graph.in_edges(entity_id, data=True))
        if in_edges:
            lines.append("\nIncoming relations:")
            for head, _, data in in_edges[:max_edges]:
                head_name = self._get_entity_name(head)
                relation = data.get("relation", "unknown")
                lines.append(f"  - {head_name} --[{relation}]--> {entity_name}")
            
            if len(in_edges) > max_edges:
                lines.append(f"  ... and {len(in_edges) - max_edges} more")
        else:
            lines.append("\nIncoming relations: (none)")
        
        return "\n".join(lines)
    
    def _choose_better_representative(
        self,
        entity_1: str,
        entity_2: str,
        signals: Dict[str, float]
    ) -> str:
        """
        Choose the better entity to serve as representative.
        
        Strategy (in priority order):
        1. If alias signal exists, follow the direction of the alias edge
        2. Prefer entity with higher out-degree (more relationships)
        3. Prefer entity with longer name (more formal)
        4. Prefer entity with more chunk evidence
        5. Prefer entity with smaller ID (created earlier)
        """
        # 1. Check alias direction
        if "alias" in signals:
            # Check which direction the alias edge points
            for head, tail, data in self.graph.edges(data=True):
                relation = data.get("relation", "")
                if relation in ["alias_of", "别名包括", "aka"]:
                    if head == entity_1 and tail == entity_2:
                        return entity_2  # entity_2 is the main entity
                    elif head == entity_2 and tail == entity_1:
                        return entity_1  # entity_1 is the main entity
        
        # 2. Compare out-degrees
        deg1 = self.graph.out_degree(entity_1)
        deg2 = self.graph.out_degree(entity_2)
        if deg1 != deg2:
            return entity_1 if deg1 > deg2 else entity_2
        
        # 3. Compare name lengths
        name1 = self._get_entity_name(entity_1)
        name2 = self._get_entity_name(entity_2)
        if len(name1) != len(name2):
            return entity_1 if len(name1) > len(name2) else entity_2
        
        # 4. Compare chunk evidence
        props1 = self.graph.nodes[entity_1].get("properties", {})
        props2 = self.graph.nodes[entity_2].get("properties", {})
        
        chunks1 = len(props1.get("chunk_ids", []))
        chunks2 = len(props2.get("chunk_ids", []))
        if chunks1 != chunks2:
            return entity_1 if chunks1 > chunks2 else entity_2
        
        # 5. Default: smaller ID
        id1 = int(entity_1.split('_')[1])
        id2 = int(entity_2.split('_')[1])
        return entity_1 if id1 < id2 else entity_2
    
    # ============================================================
    # Main Entry Point
    # ============================================================
    
    def deduplicate_heads_multi_signal(
        self,
        config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for multi-signal head deduplication.
        
        Args:
            config: Configuration dict (optional, uses defaults if not provided)
            
        Returns:
            Statistics dict
        """
        if config is None:
            config = {
                "enable_semantic_signal": True,
                "enable_subgraph_signal": True,
                "enable_alias_signal": True,
                "enable_attribute_signal": True,
                
                "semantic_threshold": 0.75,
                "subgraph_threshold": 0.60,
                "attribute_threshold": 0.60,
                "subgraph_depth": 1,
                
                "signal_weights": {
                    "semantic": 0.30,
                    "subgraph": 0.25,
                    "alias": 0.35,
                    "attribute": 0.10
                },
                
                "use_llm_validation": True,
                "llm_validation_threshold": 0.70,
                "max_semantic_candidates": 2000,
                
                "merge_strategy": "alias"  # "alias" or "delete"
            }
        
        logger.info("\n" + "=" * 70)
        logger.info("Multi-Signal Head Entity Deduplication")
        logger.info("=" * 70)
        logger.info("Configuration:")
        for key, value in config.items():
            if isinstance(value, dict):
                logger.info(f"  {key}:")
                for k, v in value.items():
                    logger.info(f"    - {k}: {v}")
            else:
                logger.info(f"  - {key}: {value}")
        logger.info("=" * 70)
        
        start_time = time.time()
        
        # Phase 1: Collect head candidates
        logger.info("\n[Phase 1/4] Collecting head entity candidates...")
        candidates = self._collect_head_candidates()
        logger.info(f"✓ Found {len(candidates)} entity nodes")
        
        # Phase 2: Multi-signal candidate generation
        logger.info("\n[Phase 2/4] Multi-signal candidate generation...")
        multi_signal_candidates = self._generate_multi_signal_candidates(
            candidates,
            config
        )
        logger.info(f"✓ Generated {len(multi_signal_candidates)} candidate pairs")
        
        # Phase 3: LLM validation (if enabled)
        merge_mapping = {}
        metadata = {}
        
        if config.get("use_llm_validation", True) and multi_signal_candidates:
            logger.info("\n[Phase 3/4] LLM validation with signal context...")
            merge_mapping, metadata = self._validate_candidates_with_llm_multi_signal(
                multi_signal_candidates,
                threshold=config.get("llm_validation_threshold", 0.70)
            )
            logger.info(f"✓ Validated {len(merge_mapping)} merge decisions")
        else:
            logger.info("\n[Phase 3/4] LLM validation skipped")
        
        # Phase 4: Apply merges
        logger.info("\n[Phase 4/4] Applying merges...")
        
        if config.get("merge_strategy") == "alias":
            # Use alias relationship method (preserves nodes)
            merge_stats = self._merge_head_nodes_with_alias(
                merge_mapping,
                metadata,
                alias_relation="alias_of"
            )
        else:
            # Use traditional deletion method
            merge_stats = self._merge_head_nodes(
                merge_mapping,
                metadata
            )
        
        elapsed = time.time() - start_time
        
        # Collect statistics
        final_entity_count = len([
            n for n, d in self.graph.nodes(data=True)
            if d.get("label") == "entity" and
               d.get("properties", {}).get("node_role") != "alias"
        ])
        
        alias_count = len([
            n for n, d in self.graph.nodes(data=True)
            if d.get("properties", {}).get("node_role") == "alias"
        ])
        
        # Signal breakdown
        signal_breakdown = defaultdict(int)
        for meta in metadata.values():
            primary_signal = meta.get("primary_signal", "unknown")
            signal_breakdown[primary_signal] += 1
        
        stats = {
            "initial_entity_count": len(candidates),
            "final_main_entity_count": final_entity_count,
            "final_alias_count": alias_count,
            "total_merged": len(merge_mapping),
            "merge_strategy": config.get("merge_strategy", "alias"),
            "elapsed_time_seconds": elapsed,
            "signal_breakdown": dict(signal_breakdown),
            "merge_stats": merge_stats
        }
        
        logger.info("\n" + "=" * 70)
        logger.info("Multi-Signal Head Deduplication Completed")
        logger.info("=" * 70)
        logger.info(f"Summary:")
        logger.info(f"  - Initial entities: {stats['initial_entity_count']}")
        logger.info(f"  - Final main entities: {stats['final_main_entity_count']}")
        logger.info(f"  - Final alias entities: {stats['final_alias_count']}")
        logger.info(f"  - Total merged: {stats['total_merged']}")
        logger.info(f"  - Time elapsed: {elapsed:.2f}s")
        logger.info(f"\nSignal breakdown:")
        for signal, count in signal_breakdown.items():
            logger.info(f"  - {signal}: {count}")
        logger.info("=" * 70 + "\n")
        
        return stats
    
    # ============================================================
    # Helper Methods
    # ============================================================
    
    def _get_entity_name(self, entity_id: str) -> str:
        """Get display name for an entity."""
        if entity_id not in self.graph:
            return entity_id
        
        props = self.graph.nodes[entity_id].get("properties", {})
        return props.get("name", props.get("title", entity_id))
