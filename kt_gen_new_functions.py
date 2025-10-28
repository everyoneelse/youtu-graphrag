"""
New functions to add to kt_gen.py after line 5297
These implement LLM-driven representative selection with alias relationships

插入位置: kt_gen.py 第5297行之前
"""

# ============================================================
# Improved Head Deduplication: LLM-Driven + Alias Relationships
# ============================================================

def _validate_candidates_with_llm_v2(
    self,
    candidate_pairs: List[Tuple[str, str, float]],
    threshold: float = 0.85
) -> Tuple[Dict[str, str], Dict[str, dict]]:
    """
    Validate candidates using LLM with representative selection.
    
    This improved version asks LLM to:
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
    
    # Get graph context
    context_1 = self._collect_node_context(node_id_1, max_relations=10)
    context_2 = self._collect_node_context(node_id_2, max_relations=10)
    
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
        logger.warning(f"Failed to load 'with_representative_selection' prompt from config: {e}")
        logger.info("Using embedded fallback prompt template")
        return self._get_embedded_prompt_template_v2(
            node_id_1, desc_1, context_1,
            node_id_2, desc_2, context_2
        )

def _get_embedded_prompt_template_v2(
    self, 
    entity_1_id: str, entity_1_desc: str, context_1: str,
    entity_2_id: str, entity_2_desc: str, context_2: str
) -> str:
    """Embedded fallback prompt template with representative selection."""
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

2. SUBSTITUTION TEST: Can you replace one with the other in all contexts?

3. PRIMARY REPRESENTATIVE SELECTION (if they are coreferent):
   Choose the entity that should serve as the main reference based on:
   
   a) **Formality and Completeness**:
      - Full name > Abbreviation (e.g., "World Health Organization" > "WHO")
      - BUT: In technical domains, common abbreviations may be preferred (e.g., "AI")
   
   b) **Domain Convention**:
      - Medical: Prefer standard terminology
      - Popular: Prefer commonly used form
      - Academic: Prefer formal names
   
   c) **Information Richness** (visible in the graph):
      - Entity with MORE relationships → Better representative
      - Entity with MORE context → Better representative
   
   d) **Naming Quality**:
      - Official name > Colloquial name
      - Standard spelling > Variant spelling

4. CONSERVATIVE PRINCIPLE:
   - When uncertain about coreference → answer NO
   - When uncertain about representative → choose the one with MORE relationships

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

def _merge_head_nodes_with_alias(
    self,
    merge_mapping: Dict[str, str],
    metadata: Dict[str, dict],
    alias_relation: str = "alias_of"
) -> Dict[str, int]:
    """
    Merge head nodes using explicit alias relationships.
    
    Strategy:
    1. Transfer all non-alias edges to representative
    2. Keep duplicate node (don't delete)
    3. Create explicit: duplicate --[alias_of]--> representative
    4. Clean up other edges from duplicate
    5. Mark node roles
    
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
    
    alias_count = 0
    edges_transferred = 0
    
    for duplicate_id, canonical_id in merge_mapping.items():
        # Validate nodes exist
        if duplicate_id not in self.graph or canonical_id not in self.graph:
            logger.debug(f"Nodes not found: {duplicate_id} or {canonical_id}")
            continue
        
        if duplicate_id == canonical_id:
            logger.warning(f"Duplicate and canonical are same: {duplicate_id}")
            continue
        
        try:
            # Step 1: Transfer edges safely (avoiding self-loops)
            out_count = self._reassign_outgoing_edges_safe(
                duplicate_id, canonical_id
            )
            in_count = self._reassign_incoming_edges_safe(
                duplicate_id, canonical_id
            )
            edges_transferred += (out_count + in_count)
            
            # Step 2: Create alias relationship
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
            
            # Step 3: Remove non-alias edges from duplicate
            self._remove_non_alias_edges(
                duplicate_id, 
                keep_edge=(duplicate_id, canonical_id)
            )
            
            # Step 4: Mark node roles
            self.graph.nodes[duplicate_id]["properties"]["node_role"] = "alias"
            self.graph.nodes[duplicate_id]["properties"]["alias_of"] = canonical_id
            
            canonical_props = self.graph.nodes[canonical_id].get("properties", {})
            canonical_props["node_role"] = "representative"
            
            # Step 5: Record aliases in canonical node
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
        if tail_id == target_id or tail_id == source_id:
            logger.debug(
                f"Skipping edge to avoid self-loop: {source_id} -> {tail_id} "
                f"(relation: {data.get('relation')})"
            )
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
        if head_id == target_id or head_id == source_id:
            logger.debug(
                f"Skipping edge to avoid self-loop: {head_id} -> {source_id} "
                f"(relation: {data.get('relation')})"
            )
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

def deduplicate_heads_with_llm_v2(
    self,
    enable_semantic: bool = True,
    similarity_threshold: float = 0.85,
    max_candidates: int = 1000,
    alias_relation: str = "alias_of"
) -> Dict[str, Any]:
    """
    Main entry: Head deduplication with LLM-driven representative selection.
    
    Key improvements:
    1. LLM decides which entity should be the representative (not code heuristics)
    2. Uses alias relationships (doesn't delete duplicate nodes)
    3. No self-loops
    4. Semantic correctness
    
    Args:
        enable_semantic: Enable semantic deduplication
        similarity_threshold: Embedding similarity threshold for candidate generation
        max_candidates: Maximum candidate pairs
        alias_relation: Name of alias relationship
        
    Returns:
        Statistics dict
    """
    logger.info("=" * 70)
    logger.info("Head Deduplication (LLM-Driven + Alias Relationships)")
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
    logger.info("Head Deduplication Completed (LLM-Driven + Alias)")
    logger.info("=" * 70)
    logger.info(f"Summary:")
    logger.info(f"  - Initial entities: {stats['initial_entity_count']}")
    logger.info(f"  - Final main entities: {stats['final_main_entity_count']}")
    logger.info(f"  - Final alias entities: {stats['final_alias_count']}")
    logger.info(f"  - Total alias relations: {stats['total_alias_created']}")
    logger.info(f"  - Time elapsed: {elapsed_time:.2f}s")
    logger.info(f"  - Method: LLM-driven representative selection ✓")
    logger.info("=" * 70)
    
    return stats

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

# Utility functions for working with aliases

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
    - alias_id, alias_name, main_entity_id, main_entity_name, confidence, method
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
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
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
