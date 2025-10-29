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
            information_identity = parsed.get("information_identity", False)
            preferred_representative = parsed.get("preferred_representative")
            rationale = parsed.get("rationale", "")
            substitution_lossless_1to2 = parsed.get("substitution_lossless_1to2")
            substitution_lossless_2to1 = parsed.get("substitution_lossless_2to1")
            
            # Only merge if information identity is true
            if information_identity and preferred_representative:
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
                    "method": "llm_v2_information_identity",
                    "llm_chosen_representative": canonical,
                    "information_identity": True,
                    "substitution_lossless_1to2": substitution_lossless_1to2,
                    "substitution_lossless_2to1": substitution_lossless_2to1
                }
                
                logger.debug(
                    f"LLM decided: {duplicate} is alias of {canonical} "
                    f"(information identity confirmed, rationale: {rationale[:100]}...)"
                )
            elif is_coreferent and not information_identity:
                # Log cases where entities refer to same object but have different information
                node_id_1 = meta["node_id_1"]
                node_id_2 = meta["node_id_2"]
                logger.info(
                    f"Coreferent but not identical: {node_id_1} and {node_id_2} "
                    f"refer to same object but contain different information. "
                    f"Keeping separate to preserve distinctions."
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
        graph_context_1 = self._collect_node_context(node_id_1, max_relations=10)
        graph_context_2 = self._collect_node_context(node_id_2, max_relations=10)
        
        # Check if hybrid context is enabled
        config = self.config.construction.semantic_dedup.head_dedup if hasattr(
            self.config.construction.semantic_dedup, 'head_dedup'
        ) else None
        
        use_hybrid_context = False
        if config:
            use_hybrid_context = getattr(config, 'use_hybrid_context', False)
        
        # Collect chunk context if hybrid mode is enabled
        if use_hybrid_context:
            chunk_context_1 = self._collect_chunk_context(node_id_1)
            chunk_context_2 = self._collect_chunk_context(node_id_2)
        else:
            chunk_context_1 = "  (Not available)"
            chunk_context_2 = "  (Not available)"
        
        # Try to load from config first
        try:
            prompt_template = self.config.get_prompt_formatted(
                "head_dedup", 
                "with_representative_selection",  # New template
                entity_1_id=node_id_1,
                entity_1_desc=desc_1,
                graph_context_1=graph_context_1,
                chunk_context_1=chunk_context_1,
                entity_2_id=node_id_2,
                entity_2_desc=desc_2,
                graph_context_2=graph_context_2,
                chunk_context_2=chunk_context_2
            )
            return prompt_template
        except Exception as e:
            # Fallback to embedded template
            logger.warning(f"Failed to load prompt from config: {e}. Using embedded template.")
            return self._get_embedded_prompt_template_v2(
                node_id_1, desc_1, graph_context_1, chunk_context_1,
                node_id_2, desc_2, graph_context_2, chunk_context_2
            )
    
    def _get_embedded_prompt_template_v2(
        self, 
        entity_1_id: str, entity_1_desc: str, graph_context_1: str, chunk_context_1: str,
        entity_2_id: str, entity_2_desc: str, graph_context_2: str, chunk_context_2: str
    ) -> str:
        """
        Embedded fallback prompt template based on Information Identity principle.
        """
        return f"""You are an expert in knowledge graph entity deduplication.

TASK: Determine if two entities contain EXACTLY THE SAME INFORMATION.

Entity 1 (ID: {entity_1_id}): {entity_1_desc}
Graph relationships:
{graph_context_1}
Source text:
{chunk_context_1}

Entity 2 (ID: {entity_2_id}): {entity_2_desc}
Graph relationships:
{graph_context_2}
Source text:
{chunk_context_2}

═══════════════════════════════════════════════════════════

FUNDAMENTAL PRINCIPLE: Information Identity

Entities should be merged if and only if they contain EXACTLY THE SAME INFORMATION.

Two conditions must BOTH be satisfied:

1. REFERENTIAL IDENTITY (指称相同)
   → They refer to the exact same real-world object

2. INFORMATION EQUIVALENCE (信息等价)
   → Replacing one with the other is lossless in BOTH directions

═══════════════════════════════════════════════════════════

STEP 1: NAME SEMANTIC ANALYSIS (CRITICAL)

Before checking contexts, analyze the NAMES themselves:

Question: Do the names reveal a hierarchical or specialization relationship?

CRITICAL PATTERNS TO DETECT:

Pattern 1: Generic vs Specific
  • "X" vs "[Modifier] + X" → HIERARCHICAL, KEEP SEPARATE
  Examples:
    - "伪影" vs "魔角伪影" ❌ (generic artifact vs specific type)
    - "带宽" vs "读出带宽" ❌ (generic vs specific bandwidth)
    - "癌症" vs "肺癌" ❌ (generic vs specific cancer)

Pattern 2: Base Concept vs Specialized Term
  • Entity 1 name is a SUBSTRING of Entity 2 name → Likely hierarchical
  • Entity 2 = [Modifier] + Entity 1 → Entity 2 is a SUBTYPE of Entity 1
  
Pattern 3: Different Specificity Levels
  • One name is more specific/detailed than the other
  Examples:
    - "提高带宽" vs "提高接收带宽" ❌ (one specifies which bandwidth)
    - "成像" vs "T1加权成像" ❌ (one specifies imaging type)

⚠️ CRITICAL RULE:
If one entity name is clearly a SPECIALIZATION of the other:
  → They are in HIERARCHICAL relationship
  → OUTPUT: is_coreferent = false, STOP immediately
  → Do NOT proceed to context analysis

Why? Because:
- Generic term ("伪影") refers to ALL types of artifacts
- Specific term ("魔角伪影") refers to ONE type
- They refer to DIFFERENT SCOPE of objects
- Merging them loses critical categorical information

═══════════════════════════════════════════════════════════

STEP 2: REFERENTIAL IDENTITY CHECK (only if Step 1 passed)

Question: Do Entity 1 and Entity 2 refer to the EXACT SAME real-world object?

Use evidence from:
- Source text contexts (how they are described and used)
- Graph relationships (their connections to other entities)
- Domain knowledge (what you know about this domain)

Tests:
✓ Same object with different names → Potentially yes (go to Step 3)
✗ Different objects (even if related) → No, KEEP SEPARATE
✗ Part-whole relationship → No, KEEP SEPARATE
✗ Hierarchical relationship → No, KEEP SEPARATE
✗ ANY contradicting evidence → No, KEEP SEPARATE

⚠️ CONTEXT SIMILARITY IS NOT ENOUGH:
- If two entities appear in similar contexts, it does NOT mean they are the same
- "伪影" and "魔角伪影" might be discussed together, but they are NOT the same
- Similar usage patterns do NOT override name semantic differences

If referentially different → OUTPUT: is_coreferent = false, STOP

═══════════════════════════════════════════════════════════

STEP 3: INFORMATION EQUIVALENCE CHECK (only if Steps 1 & 2 = YES)

Even if they refer to the same object, they might contain DIFFERENT INFORMATION about it.

Question: Do they contain the exact same information, or does one contain more specific/detailed information?

CRITICAL: Test substitution in BOTH directions

Test A - Entity 1 → Entity 2:
  • Take Entity 1's source context
  • Imagine replacing Entity 1's name/description with Entity 2's
  • Ask: "Is there ANY information loss?"
    - Precision loss? (specific term → vague term)
    - Detail loss? (detailed description → simplified)
    - Specificity loss? (unambiguous → ambiguous)
    - Contextual information loss? (bound to specific scenario → generic)
  • Verdict: LOSSLESS (yes) or HAS LOSS (no)

Test B - Entity 2 → Entity 1:
  • Take Entity 2's source context
  • Imagine replacing Entity 2's name/description with Entity 1's
  • Ask: "Is there ANY information loss?"
  • Verdict: LOSSLESS (yes) or HAS LOSS (no)

Symmetry Evaluation:
  IF both Test A = LOSSLESS AND Test B = LOSSLESS
    → SYMMETRIC substitution
    → Information is equivalent
    → Should MERGE
  
  IF Test A = HAS LOSS OR Test B = HAS LOSS
    → ASYMMETRIC substitution
    → Different information content
    → Should KEEP SEPARATE

═══════════════════════════════════════════════════════════

EXAMPLES:

Example 1 - Symmetric (MERGE):
  Entity A: "United Nations"
  Entity B: "UN"
  
  Test A→B: "The United Nations voted" → "The UN voted"
            Information loss? No ✓
  Test B→A: "The UN voted" → "The United Nations voted"
            Information loss? No ✓
  
  Result: Symmetric → Same information → MERGE

Example 2 - Asymmetric (KEEP SEPARATE):
  Entity A: "增加读出带宽" (increase readout bandwidth - specific)
  Entity B: "加大带宽" (increase bandwidth - vague)
  
  Test A→B: "通过增加读出带宽解决伪影"
         → "通过加大带宽解决伪影"
            Information loss? Yes, "读出" specificity lost ✗
  
  Test B→A: "解决方法：加大带宽"
         → "解决方法：增加读出带宽"
            Information loss? No ✓
  
  Result: Asymmetric → Different information → KEEP SEPARATE
  
  Explanation: Entity A contains MORE SPECIFIC information (which bandwidth).
  They refer to the same operation, but A is more precise than B.

Example 3 - Hierarchical Relationship (KEEP SEPARATE):
  Entity A: "伪影" (artifact - generic)
  Entity B: "魔角伪影" (magic angle artifact - specific type)
  
  NAME ANALYSIS:
    "魔角伪影" = "魔角" + "伪影"
    → Entity B is a SPECIALIZATION of Entity A
    → HIERARCHICAL relationship detected
  
  SCOPE ANALYSIS:
    Entity A: Refers to ALL types of MRI artifacts (流动伪影, 化学位移伪影, 魔角伪影, etc.)
    Entity B: Refers to ONE specific type (magic angle artifact only)
  
  SUBSTITUTION TEST:
    A→B: "MRI中的伪影包括多种类型" → "MRI中的魔角伪影包括多种类型"
          Information loss? YES, loses generic scope ✗
    B→A: "魔角伪影出现在55°角时" → "伪影出现在55°角时"
          Information loss? YES, loses type specificity ✗
  
  Result: HIERARCHICAL → KEEP SEPARATE
  
  CRITICAL: Even if they appear in similar contexts or are discussed together,
  they represent different LEVELS of abstraction and must remain separate.

Example 4 - Another Hierarchical Case (KEEP SEPARATE):
  Entity A: "癌症" (cancer - generic)
  Entity B: "肺癌" (lung cancer - specific)
  
  These are NOT the same entity, even if:
  ✗ They appear in the same medical text
  ✗ They share many properties
  ✗ They have similar treatments
  
  Why? Because "癌症" refers to ALL cancers, "肺癌" refers to ONE type.
  This is a CLASS-INSTANCE or SUPERCLASS-SUBCLASS relationship.

═══════════════════════════════════════════════════════════

PROHIBITED MERGE REASONS:

These are NOT valid reasons to merge:
✗ Similar names
✗ Same category or type
✗ Similar graph relationships
✗ Same community membership
✗ Related/associated entities
✗ Co-occurrence in contexts
✗ Partial information overlap

Only merge if information is COMPLETELY identical.

═══════════════════════════════════════════════════════════

CONSERVATIVE PRINCIPLE:

When uncertain about information loss → KEEP SEPARATE

Rationale: Preserving information distinctions is more important than graph simplicity.
False negatives (missing a merge) are better than false positives (losing information).

═══════════════════════════════════════════════════════════

REPRESENTATIVE SELECTION (only if merging):

If information is equivalent, choose the representative based on:
• Formality and completeness (more formal/complete preferred)
• Domain convention (standard terminology preferred)
• Information richness (more graph relationships preferred)
• Naming quality (official/standard preferred over colloquial)

═══════════════════════════════════════════════════════════

OUTPUT FORMAT (strict JSON):
{{
  "is_coreferent": true/false,
  "substitution_lossless_1to2": true/false/null,
  "substitution_lossless_2to1": true/false/null,
  "information_identity": true/false,
  "preferred_representative": "{entity_1_id}" or "{entity_2_id}" or null,
  "rationale": "Provide UNIFIED analysis: (1) Referential identity - do they refer to the same object? Cite specific evidence from source text and graph. (2) Information equivalence - test BOTH substitution directions explicitly. State clearly if there is ANY information loss in either direction (precision, detail, specificity, context). (3) Decision and reasoning. (4) If merging, explain choice of representative."
}}

CRITICAL REQUIREMENTS:
- Set substitution_lossless_* to null if is_coreferent = false
- Set information_identity = true ONLY if BOTH substitution tests are lossless
- Set preferred_representative ONLY if information_identity = true
- In rationale, EXPLICITLY describe what information (if any) would be lost in each substitution direction
- Do NOT merge if you detect ANY information asymmetry
"""
    
    def _parse_coreference_response_v2(self, response: str) -> dict:
        """
        Parse LLM response with information identity check.
        
        Expected format:
        {
          "is_coreferent": true/false,
          "substitution_lossless_1to2": true/false/null,
          "substitution_lossless_2to1": true/false/null,
          "information_identity": true/false,
          "preferred_representative": "entity_XXX" or null,
          "rationale": "..."
        }
        
        Args:
            response: LLM JSON response
            
        Returns:
            Parsed dict with information identity evaluation
        """
        try:
            import json_repair
            parsed = json_repair.loads(response)
            
            is_coreferent = bool(parsed.get("is_coreferent", False))
            substitution_lossless_1to2 = parsed.get("substitution_lossless_1to2")
            substitution_lossless_2to1 = parsed.get("substitution_lossless_2to1")
            information_identity = bool(parsed.get("information_identity", False))
            preferred_representative = parsed.get("preferred_representative")
            rationale = str(parsed.get("rationale", ""))
            
            # Validate: only merge if information identity is true
            if is_coreferent and not information_identity:
                logger.info(
                    f"Entities are coreferent but information is not identical. "
                    f"Keeping separate to preserve information distinctions."
                )
                is_coreferent = False
                preferred_representative = None
            
            # Validate: if merging, must have representative
            if information_identity and not preferred_representative:
                logger.warning(
                    f"LLM said information_identity=true but didn't provide preferred_representative. "
                    f"Response: {response[:200]}"
                )
                information_identity = False
                is_coreferent = False
            
            if not information_identity:
                preferred_representative = None
            
            return {
                "is_coreferent": is_coreferent,
                "substitution_lossless_1to2": substitution_lossless_1to2,
                "substitution_lossless_2to1": substitution_lossless_2to1,
                "information_identity": information_identity,
                "preferred_representative": preferred_representative,
                "rationale": rationale
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            logger.debug(f"Response: {response[:500]}...")
            return {
                "is_coreferent": False,
                "substitution_lossless_1to2": None,
                "substitution_lossless_2to1": None,
                "information_identity": False,
                "preferred_representative": None,
                "rationale": "Parse error"
            }
    
    def _revise_representative_selection_llm_driven(
        self, 
        merge_mapping: Dict[str, str],
        metadata: Dict[str, dict]
    ) -> Dict[str, str]:
        """
        Revised version with frequency-based priority.
        
        Key improvement: If an entity appears in multiple pairs (high frequency),
        it's likely a more standard/canonical name and should become the representative.
        
        Example:
          Pairs: (A, B), (A, C), (A, D) all coreferent
          → A is high-frequency, so A becomes representative
          Result: B -> A, C -> A, D -> A
        
        Args:
            merge_mapping: Initial {duplicate: canonical} from LLM
            metadata: Metadata containing LLM's rationale
            
        Returns:
            Revised merge_mapping with frequency-aware selection
        """
        from collections import defaultdict
        
        # Step 1: Count entity frequency (how many pairs each entity appears in)
        entity_frequency = defaultdict(int)
        for duplicate, canonical in merge_mapping.items():
            entity_frequency[duplicate] += 1
            entity_frequency[canonical] += 1
        
        # Step 2: Identify high-frequency entities
        # Adaptive threshold: min(3, max_freq - 1)
        if entity_frequency:
            max_freq = max(entity_frequency.values())
            HIGH_FREQ_THRESHOLD = max(2, min(3, max_freq - 1))
        else:
            HIGH_FREQ_THRESHOLD = 2
        
        high_freq_entities = {
            entity for entity, freq in entity_frequency.items()
            if freq >= HIGH_FREQ_THRESHOLD
        }
        
        if high_freq_entities:
            logger.info(
                f"Identified {len(high_freq_entities)} high-frequency entities "
                f"(threshold={HIGH_FREQ_THRESHOLD}): "
                f"{sorted(high_freq_entities)[:5]}{'...' if len(high_freq_entities) > 5 else ''}"
            )
        
        # Step 3: Build Union-Find with frequency priority
        parent = {}
        rank = {}
        
        def find(x):
            if x not in parent:
                parent[x] = x
                rank[x] = 0
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(entity1, entity2):
            """Union with frequency priority."""
            root1, root2 = find(entity1), find(entity2)
            if root1 == root2:
                return
            
            # Check if either is high-frequency
            is_high_freq_1 = root1 in high_freq_entities
            is_high_freq_2 = root2 in high_freq_entities
            
            if is_high_freq_1 and not is_high_freq_2:
                # root1 is high-freq → make it representative
                parent[root2] = root1
                logger.debug(
                    f"Union: {root2} -> {root1} "
                    f"(high-freq priority, freq={entity_frequency[root1]})"
                )
            elif is_high_freq_2 and not is_high_freq_1:
                # root2 is high-freq → make it representative
                parent[root1] = root2
                logger.debug(
                    f"Union: {root1} -> {root2} "
                    f"(high-freq priority, freq={entity_frequency[root2]})"
                )
            elif is_high_freq_1 and is_high_freq_2:
                # Both high-freq → choose one with higher frequency
                if entity_frequency[root1] > entity_frequency[root2]:
                    parent[root2] = root1
                    logger.debug(
                        f"Union: {root2} -> {root1} "
                        f"(higher freq: {entity_frequency[root1]} > {entity_frequency[root2]})"
                    )
                elif entity_frequency[root1] < entity_frequency[root2]:
                    parent[root1] = root2
                    logger.debug(
                        f"Union: {root1} -> {root2} "
                        f"(higher freq: {entity_frequency[root2]} > {entity_frequency[root1]})"
                    )
                else:
                    # Same frequency → use rank optimization
                    if rank[root1] < rank[root2]:
                        parent[root1] = root2
                    elif rank[root1] > rank[root2]:
                        parent[root2] = root1
                    else:
                        parent[root2] = root1
                        rank[root1] += 1
            else:
                # Neither is high-freq → use rank optimization (standard Union-Find)
                if rank[root1] < rank[root2]:
                    parent[root1] = root2
                elif rank[root1] > rank[root2]:
                    parent[root2] = root1
                else:
                    parent[root2] = root1
                    rank[root1] += 1
        
        # Step 4: Apply all merge decisions with frequency-aware union
        for duplicate, canonical in merge_mapping.items():
            union(duplicate, canonical)
        
        # Step 5: Build final mapping
        revised_mapping = {}
        representative_changes = 0
        
        for duplicate, original_canonical in merge_mapping.items():
            final_canonical = find(duplicate)
            if duplicate != final_canonical:
                revised_mapping[duplicate] = final_canonical
                
                # Log if representative changed
                if final_canonical != original_canonical:
                    representative_changes += 1
                    logger.info(
                        f"Representative revised: {duplicate} -> {original_canonical} "
                        f"changed to {duplicate} -> {final_canonical} "
                        f"(freq: {entity_frequency[final_canonical]})"
                    )
        
        if representative_changes > 0:
            logger.info(
                f"✓ Revised {representative_changes} representatives based on frequency"
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
