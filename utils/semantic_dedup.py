"""
Semantic Triple Deduplication Module

This module implements semantic deduplication for knowledge graph triples.
It groups triples by (head, relation) and uses embeddings + LLM to identify
semantically equivalent tails.

Main Strategy:
1. Group triples by (head, relation)
2. Use sentence embeddings for initial similarity filtering
3. Use LLM for semantic equivalence judgment
4. Use Union-Find to manage equivalence relations
"""

import ast
import json
import re
from collections import defaultdict
from typing import List, Dict, Set, Tuple, Optional
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from utils.logger import logger
from utils.call_llm_api import LLMCompletionCall


class UnionFind:
    """Union-Find data structure for managing equivalence relations."""
    
    def __init__(self, n: int):
        """
        Initialize Union-Find structure.
        
        Args:
            n: Number of elements
        """
        self.parent = list(range(n))
        self.rank = [0] * n
    
    def find(self, x: int) -> int:
        """
        Find the root of element x with path compression.
        
        Args:
            x: Element to find
            
        Returns:
            Root of the set containing x
        """
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]
    
    def union(self, x: int, y: int) -> None:
        """
        Union two sets containing x and y.
        
        Args:
            x: First element
            y: Second element
        """
        root_x = self.find(x)
        root_y = self.find(y)
        
        if root_x == root_y:
            return
        
        if self.rank[root_x] < self.rank[root_y]:
            self.parent[root_x] = root_y
        elif self.rank[root_x] > self.rank[root_y]:
            self.parent[root_y] = root_x
        else:
            self.parent[root_y] = root_x
            self.rank[root_x] += 1
    
    def get_groups(self) -> Dict[int, List[int]]:
        """
        Get all groups (equivalence classes).
        
        Returns:
            Dictionary mapping root to list of members
        """
        groups = defaultdict(list)
        for i in range(len(self.parent)):
            root = self.find(i)
            groups[root].append(i)
        return dict(groups)


class SemanticTripleDeduplicator:
    """
    Semantic deduplication for knowledge graph triples.
    
    Uses embeddings and LLM to identify semantically equivalent triples
    with the same head and relation but different tails.
    
    Can leverage chunk context and keywords for better semantic judgment.
    """
    
    def __init__(
        self,
        embedding_model_name: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = 0.7,
        batch_size: int = 8,
        enable_llm_verification: bool = True,
        use_chunk_context: bool = True,
        use_keywords: bool = True,
        config=None,
        graph=None,
        all_chunks: Dict[str, str] = None
    ):
        """
        Initialize the semantic deduplicator.
        
        Args:
            embedding_model_name: Name of the sentence transformer model
            similarity_threshold: Similarity threshold for initial filtering
            batch_size: Batch size for LLM calls
            enable_llm_verification: Whether to use LLM for verification
            use_chunk_context: Whether to use chunk context for verification
            use_keywords: Whether to use keywords as semantic features
            config: Configuration object
            graph: NetworkX graph (for accessing chunk and keyword info)
            all_chunks: Dictionary mapping chunk_id to chunk_text
        """
        self.similarity_threshold = similarity_threshold
        self.batch_size = batch_size
        self.enable_llm_verification = enable_llm_verification
        self.use_chunk_context = use_chunk_context
        self.use_keywords = use_keywords
        self.config = config
        self.graph = graph
        self.all_chunks = all_chunks or {}
        
        # Initialize embedding model
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer(embedding_model_name)
                logger.info(f"Loaded embedding model: {embedding_model_name}")
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")
                self.embedding_model = None
        else:
            logger.warning("sentence-transformers not available, skipping embedding-based filtering")
            self.embedding_model = None
        
        # Initialize LLM client
        if self.enable_llm_verification:
            try:
                self.llm_client = LLMCompletionCall()
                logger.info("Initialized LLM client for semantic verification")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM client: {e}")
                self.llm_client = None
                self.enable_llm_verification = False
    
    def parse_triple(self, triple_str: str) -> Optional[Tuple[str, str, str]]:
        """
        Parse a triple string into (head, relation, tail).
        
        Supports formats:
        - "[head, relation, tail]"
        - "(head, relation, tail)"
        - "head|relation|tail"
        
        Args:
            triple_str: String representation of triple
            
        Returns:
            Tuple of (head, relation, tail) or None if parsing fails
        """
        try:
            # Try to parse as list/tuple
            if triple_str.startswith('[') and triple_str.endswith(']'):
                parts = ast.literal_eval(triple_str)
                if isinstance(parts, (list, tuple)) and len(parts) == 3:
                    return tuple(str(p).strip() for p in parts)
            
            # Try to parse as tuple
            elif triple_str.startswith('(') and triple_str.endswith(')'):
                parts = ast.literal_eval(triple_str)
                if isinstance(parts, tuple) and len(parts) == 3:
                    return tuple(str(p).strip() for p in parts)
            
            # Try to parse as pipe-separated
            elif '|' in triple_str:
                parts = triple_str.split('|')
                if len(parts) == 3:
                    return tuple(p.strip() for p in parts)
            
            # Try to parse as comma-separated with various brackets
            else:
                # Remove outer brackets/parentheses
                cleaned = triple_str.strip('[](){}')
                # Split by comma (but be careful about commas inside strings)
                parts = [p.strip().strip('"\'') for p in cleaned.split(',')]
                if len(parts) == 3:
                    return tuple(parts)
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to parse triple '{triple_str}': {e}")
            return None
    
    def group_triples_by_head_relation(
        self, 
        triples: List[str]
    ) -> Dict[Tuple[str, str], List[Tuple[int, str, str]]]:
        """
        Group triples by (head, relation) key.
        
        Args:
            triples: List of triple strings
            
        Returns:
            Dictionary mapping (head, relation) to list of (index, tail, original_triple)
        """
        groups = defaultdict(list)
        
        for idx, triple_str in enumerate(triples):
            parsed = self.parse_triple(triple_str)
            if parsed:
                head, relation, tail = parsed
                key = (head, relation)
                groups[key].append((idx, tail, triple_str))
        
        return dict(groups)
    
    def compute_embeddings(self, texts: List[str]) -> Optional[np.ndarray]:
        """
        Compute embeddings for a list of texts.
        
        Args:
            texts: List of text strings
            
        Returns:
            Numpy array of embeddings or None if model not available
        """
        if not self.embedding_model or not texts:
            return None
        
        try:
            embeddings = self.embedding_model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            return embeddings
        except Exception as e:
            logger.warning(f"Failed to compute embeddings: {e}")
            return None
    
    def compute_similarity_matrix(
        self, 
        embeddings: np.ndarray
    ) -> np.ndarray:
        """
        Compute cosine similarity matrix.
        
        Args:
            embeddings: Array of embeddings (n, d)
            
        Returns:
            Similarity matrix (n, n)
        """
        # Normalize embeddings
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized = embeddings / (norms + 1e-8)
        
        # Compute cosine similarity
        similarity = np.dot(normalized, normalized.T)
        
        return similarity
    
    def get_similar_pairs(
        self,
        similarity_matrix: np.ndarray,
        threshold: float
    ) -> List[Tuple[int, int, float]]:
        """
        Get pairs of indices with similarity above threshold.
        
        Args:
            similarity_matrix: Similarity matrix
            threshold: Similarity threshold
            
        Returns:
            List of (i, j, similarity) tuples sorted by similarity descending
        """
        n = similarity_matrix.shape[0]
        pairs = []
        
        for i in range(n):
            for j in range(i + 1, n):
                sim = similarity_matrix[i, j]
                if sim >= threshold:
                    pairs.append((i, j, sim))
        
        # Sort by similarity descending
        pairs.sort(key=lambda x: x[2], reverse=True)
        
        return pairs
    
    def get_entity_chunk_info(self, entity_name: str) -> Dict[str, any]:
        """
        Get chunk information for an entity.
        
        Args:
            entity_name: Name of the entity
            
        Returns:
            Dictionary with chunk_id, chunk_text, and keywords
        """
        if not self.graph:
            return {}
        
        # Find entity node
        entity_node = None
        for node, data in self.graph.nodes(data=True):
            if (data.get("label") == "entity" and 
                data.get("properties", {}).get("name") == entity_name):
                entity_node = node
                break
        
        if not entity_node:
            return {}
        
        # Get chunk ID
        chunk_id = self.graph.nodes[entity_node].get("properties", {}).get("chunk id")
        chunk_text = ""
        if chunk_id and self.all_chunks:
            chunk_text = self.all_chunks.get(chunk_id, "")
        
        # Get associated keywords if enabled
        keywords = []
        if self.use_keywords:
            try:
                # Check for connected keyword nodes
                for neighbor in self.graph.neighbors(entity_node):
                    neighbor_data = self.graph.nodes[neighbor]
                    if neighbor_data.get("label") == "keyword":
                        kw_name = neighbor_data.get("properties", {}).get("name", "")
                        if kw_name:
                            keywords.append(kw_name)
            except Exception as e:
                logger.debug(f"Failed to get keywords for {entity_name}: {e}")
        
        return {
            "chunk_id": chunk_id,
            "chunk_text": chunk_text,
            "keywords": keywords
        }
    
    def build_llm_verification_prompt(
        self,
        head: str,
        relation: str,
        tail1: str,
        tail2: str,
        head_info: Dict = None,
        tail1_info: Dict = None,
        tail2_info: Dict = None
    ) -> str:
        """
        Build prompt for LLM to verify semantic equivalence.
        
        Args:
            head: Head entity
            relation: Relation
            tail1: First tail
            tail2: Second tail
            head_info: Chunk and keyword info for head (optional)
            tail1_info: Chunk and keyword info for tail1 (optional)
            tail2_info: Chunk and keyword info for tail2 (optional)
            
        Returns:
            Prompt string
        """
        # Build context sections
        context_sections = []
        
        if self.use_chunk_context and head_info and head_info.get("chunk_text"):
            context_sections.append(f"主体上下文：{head_info['chunk_text'][:200]}")
        
        if self.use_chunk_context and tail1_info and tail1_info.get("chunk_text"):
            context_sections.append(f"尾实体1上下文：{tail1_info['chunk_text'][:200]}")
        
        if self.use_chunk_context and tail2_info and tail2_info.get("chunk_text"):
            context_sections.append(f"尾实体2上下文：{tail2_info['chunk_text'][:200]}")
        
        # Build keywords section
        keywords_section = ""
        if self.use_keywords:
            all_keywords = []
            if head_info and head_info.get("keywords"):
                all_keywords.extend([f"主体关键词: {', '.join(head_info['keywords'])}"])
            if tail1_info and tail1_info.get("keywords"):
                all_keywords.extend([f"尾实体1关键词: {', '.join(tail1_info['keywords'])}"])
            if tail2_info and tail2_info.get("keywords"):
                all_keywords.extend([f"尾实体2关键词: {', '.join(tail2_info['keywords'])}"])
            
            if all_keywords:
                keywords_section = f"\n相关关键词：\n" + "\n".join(all_keywords) + "\n"
        
        context_text = ""
        if context_sections:
            context_text = f"\n原始文本上下文：\n" + "\n".join(context_sections) + "\n"
        
        prompt = f"""你是一个知识图谱专家。请判断以下两个三元组是否表达了相同的语义含义。

主体（Head）: {head}
关系（Relation）: {relation}

尾实体1（Tail 1）: {tail1}
尾实体2（Tail 2）: {tail2}
{context_text}{keywords_section}
判断标准：
1. 如果两个尾实体表达的是完全相同的概念、实体或信息，则认为语义等价
2. 如果两个尾实体只是表述方式不同，但指向同一个事物，则认为语义等价
3. 如果两个尾实体表达了不同的信息或概念，则认为不等价
4. 注意：同义词、缩写、全称/简称应该认为是等价的
5. 优先参考原始文本上下文和关键词来判断语义

请严格按照以下JSON格式回答（不要添加任何其他内容）：
{{
  "equivalent": true 或 false,
  "confidence": 0.0到1.0之间的数字,
  "reasoning": "简短的判断理由"
}}"""
        
        return prompt
    
    def build_batch_llm_prompt(
        self,
        head: str,
        relation: str,
        tails: List[str],
        head_info: Dict = None,
        tails_info: List[Dict] = None
    ) -> str:
        """
        Build prompt for batch LLM verification.
        
        Args:
            head: Head entity
            relation: Relation
            tails: List of tail entities
            head_info: Chunk and keyword info for head (optional)
            tails_info: List of chunk and keyword info for each tail (optional)
            
        Returns:
            Prompt string
        """
        # Build tails with context
        tails_lines = []
        for i, tail in enumerate(tails):
            line = f"[{i+1}] {tail}"
            
            # Add chunk context if available
            if self.use_chunk_context and tails_info and i < len(tails_info):
                tail_info = tails_info[i]
                if tail_info and tail_info.get("chunk_text"):
                    chunk_preview = tail_info["chunk_text"][:100]
                    line += f"\n    上下文: {chunk_preview}..."
            
            # Add keywords if available
            if self.use_keywords and tails_info and i < len(tails_info):
                tail_info = tails_info[i]
                if tail_info and tail_info.get("keywords"):
                    keywords_str = ", ".join(tail_info["keywords"])
                    line += f"\n    关键词: {keywords_str}"
            
            tails_lines.append(line)
        
        tails_str = "\n".join(tails_lines)
        
        # Build head context
        head_context = ""
        if self.use_chunk_context and head_info and head_info.get("chunk_text"):
            head_context = f"\n主体上下文: {head_info['chunk_text'][:200]}\n"
        
        if self.use_keywords and head_info and head_info.get("keywords"):
            head_keywords = ", ".join(head_info["keywords"])
            head_context += f"主体关键词: {head_keywords}\n"
        
        prompt = f"""你是一个知识图谱专家。请对以下同一主体和关系下的多个尾实体进行语义聚类。

主体（Head）: {head}
关系（Relation）: {relation}
{head_context}
候选尾实体：
{tails_str}

任务：
1. 将语义相同或高度相似的尾实体分为一组
2. 每组选择一个最完整、最准确的表述作为代表
3. 提供分组理由
4. 优先参考原始文本上下文和关键词来判断语义

判断标准：
- 完全相同的概念、实体或信息应该归为一组
- 同义词、缩写、全称/简称应该归为一组
- 来自相同上下文的相似描述应该归为一组
- 不同的信息或概念应该分为不同组

请严格按照以下JSON格式回答（不要添加任何其他内容）：
{{
  "groups": [
    {{
      "group_id": "Group-1",
      "members": [1, 2, 5],
      "representative": 2,
      "rationale": "这些表述都指向同一个实体"
    }},
    {{
      "group_id": "Group-2",
      "members": [3, 4],
      "representative": 3,
      "rationale": "这些表述表达了不同的信息"
    }}
  ]
}}"""
        
        return prompt
    
    def verify_with_llm_pairwise(
        self,
        head: str,
        relation: str,
        tail1: str,
        tail2: str
    ) -> bool:
        """
        Verify semantic equivalence using LLM (pairwise).
        
        Args:
            head: Head entity
            relation: Relation
            tail1: First tail
            tail2: Second tail
            
        Returns:
            True if equivalent, False otherwise
        """
        if not self.llm_client:
            return False
        
        try:
            # Get chunk and keyword info if available
            head_info = self.get_entity_chunk_info(head) if self.graph else {}
            tail1_info = self.get_entity_chunk_info(tail1) if self.graph else {}
            tail2_info = self.get_entity_chunk_info(tail2) if self.graph else {}
            
            prompt = self.build_llm_verification_prompt(
                head, relation, tail1, tail2,
                head_info, tail1_info, tail2_info
            )
            response = self.llm_client.call_api(prompt)
            
            # Parse JSON response
            result = json.loads(response)
            
            equivalent = result.get("equivalent", False)
            confidence = result.get("confidence", 0.0)
            
            # Log the reasoning
            reasoning = result.get("reasoning", "")
            logger.debug(f"LLM verification: {tail1} vs {tail2} -> {equivalent} (confidence: {confidence}) - {reasoning}")
            
            # Require high confidence for equivalence
            return equivalent and confidence >= 0.7
            
        except Exception as e:
            logger.warning(f"LLM verification failed: {e}")
            return False
    
    def verify_with_llm_batch(
        self,
        head: str,
        relation: str,
        tails: List[str]
    ) -> List[Set[int]]:
        """
        Verify semantic equivalence using LLM (batch mode).
        
        Args:
            head: Head entity
            relation: Relation
            tails: List of tail entities
            
        Returns:
            List of sets, each set contains indices of equivalent tails
        """
        if not self.llm_client or len(tails) <= 1:
            return [{i} for i in range(len(tails))]
        
        try:
            # Get chunk and keyword info if available
            head_info = self.get_entity_chunk_info(head) if self.graph else {}
            tails_info = []
            if self.graph:
                for tail in tails:
                    tails_info.append(self.get_entity_chunk_info(tail))
            
            prompt = self.build_batch_llm_prompt(head, relation, tails, head_info, tails_info)
            response = self.llm_client.call_api(prompt)
            
            # Parse JSON response
            result = json.loads(response)
            groups = result.get("groups", [])
            
            # Convert to list of sets
            equivalence_sets = []
            for group in groups:
                members = group.get("members", [])
                # Convert 1-indexed to 0-indexed
                members_set = {m - 1 for m in members if 0 < m <= len(tails)}
                if members_set:
                    equivalence_sets.append(members_set)
            
            # Add any tails not in any group
            all_assigned = set()
            for s in equivalence_sets:
                all_assigned.update(s)
            
            for i in range(len(tails)):
                if i not in all_assigned:
                    equivalence_sets.append({i})
            
            logger.debug(f"Batch LLM verification for ({head}, {relation}): {len(tails)} tails -> {len(equivalence_sets)} groups")
            
            return equivalence_sets
            
        except Exception as e:
            logger.warning(f"Batch LLM verification failed: {e}")
            # Fallback: each tail is its own group
            return [{i} for i in range(len(tails))]
    
    def deduplicate_group(
        self,
        head: str,
        relation: str,
        tail_items: List[Tuple[int, str, str]]
    ) -> List[int]:
        """
        Deduplicate a group of tails with the same head and relation.
        
        Returns indices of representative triples to keep.
        
        Args:
            head: Head entity
            relation: Relation
            tail_items: List of (original_index, tail, original_triple)
            
        Returns:
            List of original indices to keep
        """
        n = len(tail_items)
        
        # If only one tail, no deduplication needed
        if n <= 1:
            return [item[0] for item in tail_items]
        
        # Extract tails
        tails = [item[1] for item in tail_items]
        
        # Step 1: Embedding-based filtering (if available)
        uf = UnionFind(n)
        
        if self.embedding_model:
            embeddings = self.compute_embeddings(tails)
            
            if embeddings is not None:
                similarity_matrix = self.compute_similarity_matrix(embeddings)
                similar_pairs = self.get_similar_pairs(
                    similarity_matrix,
                    self.similarity_threshold
                )
                
                logger.debug(f"Found {len(similar_pairs)} similar pairs for ({head}, {relation}) with {n} tails")
                
                # Step 2: LLM verification for similar pairs
                if self.enable_llm_verification and similar_pairs:
                    # Use pairwise verification for pairs above threshold
                    verified_count = 0
                    for i, j, sim in similar_pairs:
                        # Skip if already in same group
                        if uf.find(i) == uf.find(j):
                            continue
                        
                        # Verify with LLM
                        if self.verify_with_llm_pairwise(head, relation, tails[i], tails[j]):
                            uf.union(i, j)
                            verified_count += 1
                    
                    logger.debug(f"LLM verified {verified_count} equivalent pairs")
                else:
                    # No LLM verification, just use embedding similarity
                    for i, j, _ in similar_pairs:
                        uf.union(i, j)
        
        # If no embedding model or batch mode preferred
        elif self.enable_llm_verification and n <= self.batch_size:
            # Use batch LLM verification
            equivalence_sets = self.verify_with_llm_batch(head, relation, tails)
            
            # Build union-find from equivalence sets
            for equiv_set in equivalence_sets:
                indices = list(equiv_set)
                if len(indices) > 1:
                    for i in range(1, len(indices)):
                        uf.union(indices[0], indices[i])
        
        # Step 3: Get representative for each group
        groups = uf.get_groups()
        representatives = []
        
        for root, members in groups.items():
            # Choose the representative (e.g., longest tail)
            best_idx = max(members, key=lambda i: len(tails[i]))
            representatives.append(tail_items[best_idx][0])  # original index
        
        logger.info(f"Deduplicated group ({head}, {relation}): {n} tails -> {len(representatives)} representatives")
        
        return representatives
    
    def deduplicate(self, triples: List[str]) -> List[str]:
        """
        Perform semantic deduplication on a list of triples.
        
        Args:
            triples: List of triple strings
            
        Returns:
            Deduplicated list of triples
        """
        if not triples:
            return []
        
        logger.info(f"Starting semantic deduplication on {len(triples)} triples")
        
        # Step 1: Group by (head, relation)
        groups = self.group_triples_by_head_relation(triples)
        logger.info(f"Grouped into {len(groups)} (head, relation) groups")
        
        # Step 2: Deduplicate each group
        keep_indices = set()
        
        for (head, relation), tail_items in groups.items():
            representatives = self.deduplicate_group(head, relation, tail_items)
            keep_indices.update(representatives)
        
        # Step 3: Collect deduplicated triples
        deduplicated = [triples[i] for i in sorted(keep_indices)]
        
        logger.info(f"Semantic deduplication complete: {len(triples)} -> {len(deduplicated)} triples")
        
        return deduplicated


def semantic_deduplicate_triples(
    triples: List[str],
    config=None,
    similarity_threshold: float = 0.7,
    batch_size: int = 8,
    enable_llm_verification: bool = True,
    use_chunk_context: bool = True,
    use_keywords: bool = True,
    graph=None,
    all_chunks: Dict[str, str] = None
) -> List[str]:
    """
    Convenience function for semantic triple deduplication.
    
    Args:
        triples: List of triple strings
        config: Configuration object
        similarity_threshold: Similarity threshold for embedding filtering
        batch_size: Batch size for LLM calls
        enable_llm_verification: Whether to use LLM verification
        use_chunk_context: Whether to use chunk context for verification
        use_keywords: Whether to use keywords as semantic features
        graph: NetworkX graph (for accessing chunk and keyword info)
        all_chunks: Dictionary mapping chunk_id to chunk_text
        
    Returns:
        Deduplicated list of triples
    """
    deduplicator = SemanticTripleDeduplicator(
        similarity_threshold=similarity_threshold,
        batch_size=batch_size,
        enable_llm_verification=enable_llm_verification,
        use_chunk_context=use_chunk_context,
        use_keywords=use_keywords,
        config=config,
        graph=graph,
        all_chunks=all_chunks
    )
    
    return deduplicator.deduplicate(triples)
