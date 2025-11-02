"""
Head Node Deduplication Reference Implementation

这个文件提供了head节点去重的参考实现，可以作为添加到kt_gen.py的模块。
核心功能包括：
1. 精确匹配去重
2. 语义相似度去重（基于embedding）
3. LLM验证（可选）
4. 图结构更新
5. 完整性验证

Author: Knowledge Graph Architect
Date: 2025-10-27
"""

import copy
import json
import time
from typing import Any, Dict, List, Tuple, Set
from collections import defaultdict
from functools import lru_cache

import numpy as np
from utils.logger import logger


class HeadDeduplicationMixin:
    """
    Head节点去重功能的Mixin类
    
    将此类混入到KnowledgeTreeGen中使用：
    class KnowledgeTreeGen(HeadDeduplicationMixin, ...):
        pass
    """
    
    # ============================================================
    # Phase 1: 候选节点收集
    # ============================================================
    
    def _collect_head_candidates(self) -> List[str]:
        """
        收集所有需要去重的head节点
        
        策略：
        - 仅处理label == "entity"的节点
        - 不处理attribute、keyword、community节点
        
        Returns:
            实体节点ID列表
        """
        candidates = [
            node_id
            for node_id, data in self.graph.nodes(data=True)
            if data.get("label") == "entity"
        ]
        
        logger.info(f"Collected {len(candidates)} entity nodes as head deduplication candidates")
        return candidates
    
    # ============================================================
    # Phase 2: 精确匹配去重
    # ============================================================
    
    def _normalize_entity_name(self, name: str) -> str:
        """
        实体名称标准化
        
        规则：
        1. 转小写
        2. 去除首尾空格
        3. 合并多个连续空格为一个
        4. 去除常见标点符号
        5. 统一全角/半角（可选）
        
        Args:
            name: 原始实体名称
            
        Returns:
            标准化后的名称
        """
        if not name:
            return ""
        
        # 1. 转小写并去除首尾空格
        normalized = name.lower().strip()
        
        # 2. 合并多个空格
        normalized = ' '.join(normalized.split())
        
        # 3. 去除常见标点符号（保留连字符和下划线）
        remove_chars = ['.', ',', '!', '?', ':', ';', '"', "'", '(', ')', '[', ']', '{', '}']
        for char in remove_chars:
            normalized = normalized.replace(char, '')
        
        # 4. 可选：统一全角/半角（中文环境）
        # 这里简化处理，实际可使用unicodedata.normalize
        
        return normalized
    
    def _deduplicate_heads_exact(self, candidates: List[str]) -> Dict[str, str]:
        """
        基于精确字符串匹配的head节点去重
        
        策略：
        1. 按标准化名称分组
        2. 每组选择一个代表性节点（canonical node）
        3. 其他节点标记为重复（duplicate）
        
        Args:
            candidates: 候选节点ID列表
            
        Returns:
            Dict[duplicate_id, canonical_id]: 合并映射表
        """
        logger.info("Starting exact match deduplication for head nodes...")
        
        # 按标准化名称分组
        name_groups = defaultdict(list)
        
        for node_id in candidates:
            if node_id not in self.graph:
                continue
                
            node_data = self.graph.nodes[node_id]
            name = node_data.get("properties", {}).get("name", "")
            
            if not name:
                logger.debug(f"Node {node_id} has no name, skipping")
                continue
            
            # 标准化名称
            normalized_name = self._normalize_entity_name(name)
            name_groups[normalized_name].append((node_id, name))
        
        # 构建合并映射
        merge_mapping = {}
        
        for normalized_name, node_list in name_groups.items():
            if len(node_list) <= 1:
                continue  # 无重复
            
            # 选择代表性节点（启发式：ID编号最小的，通常是最早创建的）
            node_list_sorted = sorted(node_list, key=lambda x: int(x[0].split('_')[1]))
            canonical_id = node_list_sorted[0][0]
            
            logger.debug(f"Canonical node for '{normalized_name}': {canonical_id} (original: {node_list_sorted[0][1]})")
            
            # 其他节点标记为重复
            for node_id, original_name in node_list_sorted[1:]:
                merge_mapping[node_id] = canonical_id
                logger.debug(f"  Duplicate: {node_id} (original: {original_name}) -> {canonical_id}")
        
        logger.info(f"Exact match found {len(merge_mapping)} duplicate head nodes")
        return merge_mapping
    
    # ============================================================
    # Phase 3: 语义去重
    # ============================================================
    
    def _generate_semantic_candidates(
        self,
        remaining_nodes: List[str],
        max_candidates: int = 1000,
        similarity_threshold: float = 0.75
    ) -> List[Tuple[str, str, float]]:
        """
        生成需要语义判断的候选节点对
        
        策略：
        1. 批量获取所有节点的embedding
        2. 计算余弦相似度矩阵
        3. 提取高相似度对（预筛选）
        4. 按相似度降序排序
        
        Args:
            remaining_nodes: 剩余待处理的节点ID列表
            max_candidates: 最大返回候选对数量
            similarity_threshold: 预筛选相似度阈值（较宽松）
            
        Returns:
            List[(node_id_1, node_id_2, similarity)]: 候选节点对及其相似度
        """
        logger.info("Generating semantic deduplication candidates...")
        
        if len(remaining_nodes) < 2:
            logger.info("Less than 2 nodes remaining, skipping semantic deduplication")
            return []
        
        # 1. 批量获取节点描述
        node_descriptions = {}
        for node_id in remaining_nodes:
            if node_id not in self.graph:
                continue
            desc = self._describe_node_for_clustering(node_id)
            if desc:
                node_descriptions[node_id] = desc
        
        if len(node_descriptions) < 2:
            logger.info("Not enough valid descriptions, skipping semantic deduplication")
            return []
        
        logger.info(f"Collected {len(node_descriptions)} valid node descriptions")
        
        # 2. 批量获取embedding
        nodes = list(node_descriptions.keys())
        descriptions = [node_descriptions[node_id] for node_id in nodes]
        
        try:
            embeddings = self._batch_get_embeddings(descriptions)
            embeddings_array = np.array(embeddings)
        except Exception as e:
            logger.error(f"Failed to get embeddings: {e}")
            return []
        
        logger.info(f"Generated embeddings with shape {embeddings_array.shape}")
        
        # 3. 计算相似度矩阵（仅计算上三角，避免重复）
        from sklearn.metrics.pairwise import cosine_similarity
        similarity_matrix = cosine_similarity(embeddings_array)
        
        # 4. 提取高相似度候选对
        candidates = []
        n = len(nodes)
        
        for i in range(n):
            for j in range(i + 1, n):
                sim = similarity_matrix[i][j]
                if sim >= similarity_threshold:
                    candidates.append((nodes[i], nodes[j], float(sim)))
        
        logger.info(f"Found {len(candidates)} candidate pairs above threshold {similarity_threshold}")
        
        # 5. 按相似度降序排序，取top-K
        candidates.sort(key=lambda x: x[2], reverse=True)
        
        if len(candidates) > max_candidates:
            logger.info(f"Limiting to top {max_candidates} candidates")
            candidates = candidates[:max_candidates]
        
        return candidates
    
    def _validate_candidates_with_embedding(
        self,
        candidate_pairs: List[Tuple[str, str, float]],
        threshold: float
    ) -> Tuple[Dict[str, str], Dict[str, dict]]:
        """
        基于embedding相似度验证候选对（不使用LLM，快速模式）
        
        Args:
            candidate_pairs: 候选节点对列表
            threshold: 最终判定阈值（严格）
            
        Returns:
            (merge_mapping, metadata): 合并映射和元数据
        """
        logger.info(f"Validating {len(candidate_pairs)} candidates with embedding (threshold={threshold})...")
        
        merge_mapping = {}
        metadata = {}
        
        # 使用Union-Find防止传递性错误
        # 例如：A~B (0.86), B~C (0.86)，但A~C (0.60)
        parent = {}
        
        def find(x):
            if x not in parent:
                parent[x] = x
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                # 合并到ID较小的（作为canonical）
                if int(px.split('_')[1]) < int(py.split('_')[1]):
                    parent[py] = px
                else:
                    parent[px] = py
        
        # 处理所有高相似度对
        valid_pairs = []
        for node_id_1, node_id_2, similarity in candidate_pairs:
            if similarity >= threshold:
                union(node_id_1, node_id_2)
                valid_pairs.append((node_id_1, node_id_2, similarity))
        
        logger.info(f"Found {len(valid_pairs)} valid pairs above threshold {threshold}")
        
        # 构建merge_mapping
        canonical_map = {}  # 每个连通分量的canonical node
        
        for node_id_1, node_id_2, similarity in valid_pairs:
            root = find(node_id_1)
            
            # 确定canonical node（连通分量中ID最小的）
            if root not in canonical_map:
                canonical_map[root] = root
            
            # 更新当前节点对
            for node in [node_id_1, node_id_2]:
                node_root = find(node)
                if node != canonical_map[node_root]:
                    merge_mapping[node] = canonical_map[node_root]
                    if node not in metadata:
                        metadata[node] = {
                            "rationale": f"High embedding similarity (threshold={threshold})",
                            "confidence": float(similarity),
                            "method": "embedding"
                        }
        
        logger.info(f"Generated {len(merge_mapping)} merge decisions")
        return merge_mapping, metadata
    
    def _validate_candidates_with_llm(
        self,
        candidate_pairs: List[Tuple[str, str, float]],
        threshold: float
    ) -> Tuple[Dict[str, str], Dict[str, dict]]:
        """
        使用LLM验证候选对（高精度模式，较慢）
        
        Args:
            candidate_pairs: 候选节点对列表
            threshold: LLM置信度阈值
            
        Returns:
            (merge_mapping, metadata): 合并映射和元数据
        """
        logger.info(f"Validating {len(candidate_pairs)} candidates with LLM (threshold={threshold})...")
        
        # 1. 构建LLM prompts
        prompts = []
        for node_id_1, node_id_2, embedding_sim in candidate_pairs:
            prompt_text = self._build_head_dedup_prompt(node_id_1, node_id_2)
            prompts.append({
                "prompt": prompt_text,
                "metadata": {
                    "node_id_1": node_id_1,
                    "node_id_2": node_id_2,
                    "embedding_similarity": embedding_sim
                }
            })
        
        # 2. 并发调用LLM
        logger.info(f"Processing {len(prompts)} LLM validation calls concurrently...")
        llm_results = self._concurrent_llm_calls(prompts)
        
        # 3. 解析结果
        merge_mapping = {}
        metadata = {}
        
        for result in llm_results:
            meta = result.get("metadata", {})
            response = result.get("response", "")
            
            # 解析LLM响应
            parsed = self._parse_coreference_response(response)
            is_coreferent = parsed.get("is_coreferent", False)
            confidence = parsed.get("confidence", 0.0)
            rationale = parsed.get("rationale", "")
            
            # 只合并高置信度的结果
            if is_coreferent and confidence >= threshold:
                node_id_1 = meta["node_id_1"]
                node_id_2 = meta["node_id_2"]
                
                # 选择canonical节点（ID较小的）
                canonical = min(node_id_1, node_id_2, key=lambda x: int(x.split('_')[1]))
                duplicate = node_id_2 if canonical == node_id_1 else node_id_1
                
                merge_mapping[duplicate] = canonical
                metadata[duplicate] = {
                    "rationale": rationale,
                    "confidence": confidence,
                    "embedding_similarity": meta.get("embedding_similarity", 0.0),
                    "method": "llm"
                }
        
        # 4. 将图中已存在的"别名包括"关系添加到merge_mapping
        # 统一语义：A --[别名包括]--> B 表示 "B是A的别名"
        # 因此：canonical_id = A（主实体），duplicate_id = B（别名）
        # 结果：merge_mapping[B] = A
        logger.info("扫描图中已存在的'别名包括'关系...")
        alias_count = 0
        skipped_count = 0
        transitive_count = 0
        cascade_count = 0
        
        for source_id, target_id, edge_data in self.graph.edges(data=True):
            if edge_data.get("relation", "") != "别名包括":
                continue
            
            # 统一语义：source_id --[别名包括]--> target_id
            # 表示："target_id 是 source_id 的别名"
            canonical_id = source_id  # 主实体
            duplicate_id = target_id  # 别名
            
            if duplicate_id in merge_mapping:
                # duplicate_id 已经有合并决定
                existing_canonical = merge_mapping[duplicate_id]
                
                if existing_canonical == canonical_id:
                    # 已经正确，跳过
                    skipped_count += 1
                    logger.debug(
                        f"跳过 {duplicate_id} -> {canonical_id}：merge_mapping中已正确"
                    )
                else:
                    # 冲突：duplicate_id 是 canonical_id 的别名，但LLM说 duplicate_id -> existing_canonical
                    # 解决方案：传递合并 - canonical_id 也应该合并到 existing_canonical
                    # 逻辑：如果B是A的别名，而B合并到C，那么A也应该合并到C
                    if canonical_id not in merge_mapping:
                        merge_mapping[canonical_id] = existing_canonical
                        metadata[canonical_id] = {
                            "rationale": f"传递合并：{duplicate_id} 是 {canonical_id} 的别名，且 {duplicate_id} 合并到 {existing_canonical}",
                            "confidence": 1.0,
                            "embedding_similarity": 0.0,
                            "method": "existing_alias_transitive"
                        }
                        transitive_count += 1
                        logger.info(
                            f"传递合并：{canonical_id} → {existing_canonical} "
                            f"（因为 {duplicate_id} 是 {canonical_id} 的别名且 {duplicate_id} → {existing_canonical}）"
                        )
                    elif merge_mapping[canonical_id] != existing_canonical:
                        # 复杂冲突：canonical_id 也有不同的决定
                        # A --[别名包括]--> B，但 B→C 且 A→D (D≠C)
                        # 解决方案：强制传递 - A和B应该合并到同一实体
                        canonical_target = merge_mapping[canonical_id]  # D
                        
                        # 强制传递（覆盖A的决定）
                        # 理由：图说B是A的别名，如果B→C，那么A也应该→C
                        logger.info(
                            f"通过传递覆盖解决复杂冲突："
                            f"{canonical_id} --[别名包括]--> {duplicate_id}，"
                            f"其中 {duplicate_id} → {existing_canonical} 且 {canonical_id} → {canonical_target}。"
                            f"覆盖为 {canonical_id} → {existing_canonical} 以遵守别名关系。"
                        )
                        merge_mapping[canonical_id] = existing_canonical
                        metadata[canonical_id]["rationale"] = (
                            f"覆盖：{duplicate_id} 是 {canonical_id} 的别名，"
                            f"且 {duplicate_id} → {existing_canonical}，"
                            f"因此 {canonical_id} 也应该 → {existing_canonical}"
                        )
                        metadata[canonical_id]["method"] = "existing_alias_conflict_resolved"
                        transitive_count += 1
                        
                        # 如果需要，也将canonical_target级联合并
                        if canonical_target in self.graph.nodes() and canonical_target != existing_canonical:
                            if canonical_target not in merge_mapping or merge_mapping[canonical_target] == canonical_target:
                                merge_mapping[canonical_target] = existing_canonical
                                metadata[canonical_target] = {
                                    "rationale": f"从 {canonical_id} 级联合并",
                                    "confidence": 0.8,
                                    "method": "alias_cascade"
                                }
                                logger.info(f"级联合并：{canonical_target} → {existing_canonical}")
            else:
                # duplicate_id 还没有决定，使用图中的关系
                merge_mapping[duplicate_id] = canonical_id
                metadata[duplicate_id] = {
                    "rationale": "图中已存在的别名关系",
                    "confidence": 1.0,
                    "embedding_similarity": 0.0,
                    "method": "existing_alias"
                }
                alias_count += 1
        
        logger.info(
            f"从图中添加了 {alias_count} 个已存在的别名关系到merge_mapping。"
            f"跳过了 {skipped_count} 个（已正确）。"
            f"通过传递合并解决了 {transitive_count} 个冲突。"
        )
        logger.info(f"LLM validated {len(merge_mapping)} merges (including existing aliases)")
        return merge_mapping, metadata
    
    def _build_head_dedup_prompt(self, node_id_1: str, node_id_2: str) -> str:
        """
        构建head去重的LLM prompt
        
        Args:
            node_id_1, node_id_2: 待判断的两个节点ID
            
        Returns:
            完整的prompt文本
        """
        # 获取节点描述
        desc_1 = self._describe_node(node_id_1)
        desc_2 = self._describe_node(node_id_2)
        
        # 获取节点上下文（关联关系）
        context_1 = self._collect_node_context(node_id_1, max_relations=10)
        context_2 = self._collect_node_context(node_id_2, max_relations=10)
        
        # 使用模板
        prompt = f"""You are an expert in knowledge graph entity resolution.

TASK: Determine if the following two entities refer to the SAME real-world object.

Entity 1: {desc_1}
Related knowledge about Entity 1:
{context_1}

Entity 2: {desc_2}
Related knowledge about Entity 2:
{context_2}

CRITICAL RULES:
1. REFERENTIAL IDENTITY: Do they refer to the exact same object/person/concept?
   - Same entity with different names → YES (e.g., "NYC" = "New York City")
   - Different but related entities → NO (e.g., "Apple Inc." ≠ "Apple Store")

2. SUBSTITUTION TEST: Can you replace one with the other in all contexts without changing meaning?
   - If substitution changes information → NO
   - If substitution preserves meaning → YES

3. TYPE CONSISTENCY: Check entity types/categories
   - Same name, different types → carefully verify with context

4. CONSERVATIVE PRINCIPLE:
   - When uncertain → answer NO
   - False merge is worse than false split

OUTPUT FORMAT (strict JSON):
{{
  "is_coreferent": true/false,
  "confidence": 0.0-1.0,
  "rationale": "Clear explanation based on referential identity test"
}}
"""
        return prompt
    
    def _collect_node_context(self, node_id: str, max_relations: int = 10) -> str:
        """
        收集节点的关系上下文
        
        Args:
            node_id: 节点ID
            max_relations: 最大收集的关系数量
            
        Returns:
            格式化的上下文字符串
        """
        contexts = []
        
        # 出边（该实体作为head）
        out_edges = list(self.graph.out_edges(node_id, data=True))[:max_relations]
        for _, tail_id, data in out_edges:
            relation = data.get("relation", "related_to")
            tail_desc = self._describe_node(tail_id)
            contexts.append(f"  • {relation} → {tail_desc}")
        
        # 入边（该实体作为tail）
        in_edges = list(self.graph.in_edges(node_id, data=True))[:max_relations]
        for head_id, _, data in in_edges:
            relation = data.get("relation", "related_to")
            head_desc = self._describe_node(head_id)
            contexts.append(f"  • {head_desc} → {relation}")
        
        if not contexts:
            return "  (No relations found)"
        
        return "\n".join(contexts)
    
    def _parse_coreference_response(self, response: str) -> dict:
        """
        解析LLM的共指判断响应
        
        Args:
            response: LLM返回的JSON字符串
            
        Returns:
            解析后的字典 {"is_coreferent": bool, "confidence": float, "rationale": str}
        """
        try:
            import json_repair
            parsed = json_repair.loads(response)
            return {
                "is_coreferent": bool(parsed.get("is_coreferent", False)),
                "confidence": float(parsed.get("confidence", 0.0)),
                "rationale": str(parsed.get("rationale", ""))
            }
        except Exception as e:
            logger.warning(f"Failed to parse LLM coreference response: {e}")
            logger.debug(f"Response: {response[:200]}...")
            return {
                "is_coreferent": False,
                "confidence": 0.0,
                "rationale": "Parse error"
            }
    
    # ============================================================
    # Phase 4: 图结构更新
    # ============================================================
    
    def _merge_head_nodes(
        self,
        merge_mapping: Dict[str, str],
        metadata: Dict[str, dict]
    ) -> int:
        """
        执行head节点合并，更新图结构
        
        操作：
        1. 转移所有出边（duplicate作为head的边）
        2. 转移所有入边（duplicate作为tail的边）
        3. 合并节点属性和元数据
        4. 删除重复节点
        
        Args:
            merge_mapping: {duplicate_id: canonical_id}
            metadata: {duplicate_id: {"rationale": ..., "confidence": ...}}
            
        Returns:
            成功合并的节点数量
        """
        if not merge_mapping:
            logger.info("No head nodes to merge")
            return 0
        
        logger.info(f"Merging {len(merge_mapping)} head nodes...")
        merged_count = 0
        
        for duplicate_id, canonical_id in merge_mapping.items():
            # 验证节点存在性
            if duplicate_id not in self.graph:
                logger.debug(f"Duplicate node {duplicate_id} not in graph, skipping")
                continue
            
            if canonical_id not in self.graph:
                logger.warning(f"Canonical node {canonical_id} not in graph, skipping")
                continue
            
            # 防止自引用
            if duplicate_id == canonical_id:
                logger.warning(f"Duplicate and canonical are same node {duplicate_id}, skipping")
                continue
            
            try:
                # 1. 转移出边
                self._reassign_outgoing_edges(duplicate_id, canonical_id)
                
                # 2. 转移入边
                self._reassign_incoming_edges(duplicate_id, canonical_id)
                
                # 3. 合并节点属性
                self._merge_node_properties(
                    duplicate_id,
                    canonical_id,
                    metadata.get(duplicate_id, {})
                )
                
                # 4. 删除重复节点
                self.graph.remove_node(duplicate_id)
                merged_count += 1
                
                logger.debug(f"Successfully merged {duplicate_id} into {canonical_id}")
                
            except Exception as e:
                logger.error(f"Error merging {duplicate_id} into {canonical_id}: {e}")
                continue
        
        logger.info(f"Successfully merged {merged_count} head nodes")
        return merged_count
    
    def _reassign_outgoing_edges(self, source_id: str, target_id: str):
        """
        转移出边：source_id作为head的所有边转移到target_id
        
        Args:
            source_id: 源节点（将被删除）
            target_id: 目标节点（canonical）
        """
        outgoing = list(self.graph.out_edges(source_id, keys=True, data=True))
        
        for _, tail_id, key, data in outgoing:
            # 避免自环
            if tail_id == target_id:
                logger.debug(f"Skipping self-loop: {target_id} -> {tail_id}")
                continue
            
            # 检查是否已存在相同的边
            edge_exists, existing_key = self._find_similar_edge(target_id, tail_id, data)
            
            if not edge_exists:
                # 添加新边
                self.graph.add_edge(target_id, tail_id, **copy.deepcopy(data))
            else:
                # 合并chunk信息到已存在的边
                self._merge_edge_chunks(target_id, tail_id, existing_key, data)
    
    def _reassign_incoming_edges(self, source_id: str, target_id: str):
        """
        转移入边：source_id作为tail的所有边转移到target_id
        
        Args:
            source_id: 源节点（将被删除）
            target_id: 目标节点（canonical）
        """
        incoming = list(self.graph.in_edges(source_id, keys=True, data=True))
        
        for head_id, _, key, data in incoming:
            # 避免自环
            if head_id == target_id:
                logger.debug(f"Skipping self-loop: {head_id} -> {target_id}")
                continue
            
            # 检查是否已存在相同的边
            edge_exists, existing_key = self._find_similar_edge(head_id, target_id, data)
            
            if not edge_exists:
                # 添加新边
                self.graph.add_edge(head_id, target_id, **copy.deepcopy(data))
            else:
                # 合并chunk信息到已存在的边
                self._merge_edge_chunks(head_id, target_id, existing_key, data)
    
    def _find_similar_edge(self, u: str, v: str, new_data: dict) -> Tuple[bool, Any]:
        """
        查找是否存在相似的边（基于relation）
        
        Args:
            u, v: 边的起点和终点
            new_data: 新边的数据
            
        Returns:
            (exists, edge_key): 是否存在及对应的edge key
        """
        new_relation = new_data.get("relation")
        
        if not self.graph.has_edge(u, v):
            return False, None
        
        # MultiDiGraph可能有多条边
        for key, data in self.graph[u][v].items():
            if data.get("relation") == new_relation:
                return True, key
        
        return False, None
    
    def _merge_edge_chunks(self, u: str, v: str, edge_key: Any, new_data: dict):
        """
        合并边的chunk信息到已存在的边
        
        Args:
            u, v: 边的起点和终点
            edge_key: 边的key（MultiDiGraph）
            new_data: 新边的数据（包含要合并的chunks）
        """
        existing_data = self.graph[u][v][edge_key]
        
        # 合并source_chunks
        existing_chunks = set(existing_data.get("source_chunks", []))
        new_chunks = set(new_data.get("source_chunks", []))
        merged_chunks = list(existing_chunks | new_chunks)
        
        if merged_chunks:
            existing_data["source_chunks"] = merged_chunks
    
    def _merge_node_properties(
        self,
        duplicate_id: str,
        canonical_id: str,
        merge_meta: dict
    ):
        """
        合并节点属性，记录溯源信息
        
        Args:
            duplicate_id: 重复节点ID
            canonical_id: 标准节点ID
            merge_meta: 合并元数据（rationale, confidence等）
        """
        canonical_data = self.graph.nodes[canonical_id]
        duplicate_data = self.graph.nodes[duplicate_id]
        
        # 初始化head_dedup元数据
        properties = canonical_data.setdefault("properties", {})
        if "head_dedup" not in properties:
            properties["head_dedup"] = {
                "merged_nodes": [],
                "merge_history": []
            }
        
        # 记录合并信息
        properties["head_dedup"]["merged_nodes"].append(duplicate_id)
        properties["head_dedup"]["merge_history"].append({
            "merged_node_id": duplicate_id,
            "merged_node_name": duplicate_data.get("properties", {}).get("name", ""),
            "rationale": merge_meta.get("rationale", "Semantic similarity"),
            "confidence": merge_meta.get("confidence", 1.0),
            "method": merge_meta.get("method", "unknown"),
            "timestamp": time.time()
        })
        
        # 合并chunk信息（如果有）
        canonical_chunks = set(properties.get("chunk_ids", []))
        duplicate_chunks = set(duplicate_data.get("properties", {}).get("chunk_ids", []))
        merged_chunks = list(canonical_chunks | duplicate_chunks)
        
        if merged_chunks:
            properties["chunk_ids"] = merged_chunks
    
    # ============================================================
    # 主入口函数
    # ============================================================
    
    def deduplicate_heads(
        self,
        enable_semantic: bool = True,
        similarity_threshold: float = 0.85,
        use_llm_validation: bool = False,
        max_candidates: int = 1000
    ) -> Dict[str, Any]:
        """
        主入口：执行head节点去重
        
        Args:
            enable_semantic: 是否启用语义去重
            similarity_threshold: 语义相似度阈值（0.0-1.0）
            use_llm_validation: 是否使用LLM验证（提高准确率但更慢）
            max_candidates: 最大处理候选对数量
            
        Returns:
            去重统计信息
        """
        logger.info("=" * 70)
        logger.info("Starting Head Node Deduplication")
        logger.info("=" * 70)
        logger.info(f"Configuration:")
        logger.info(f"  - Enable semantic dedup: {enable_semantic}")
        logger.info(f"  - Similarity threshold: {similarity_threshold}")
        logger.info(f"  - Use LLM validation: {use_llm_validation}")
        logger.info(f"  - Max candidates: {max_candidates}")
        logger.info("=" * 70)
        
        start_time = time.time()
        
        # Phase 1: 收集候选节点
        logger.info("\n[Phase 1/4] Collecting head candidates...")
        candidates = self._collect_head_candidates()
        logger.info(f"✓ Found {len(candidates)} entity nodes")
        
        # Phase 2: 精确匹配去重
        logger.info("\n[Phase 2/4] Exact match deduplication...")
        exact_merge_mapping = self._deduplicate_heads_exact(candidates)
        logger.info(f"✓ Identified {len(exact_merge_mapping)} exact matches")
        
        # 应用精确匹配合并
        exact_merged_count = self._merge_head_nodes(exact_merge_mapping, {})
        logger.info(f"✓ Merged {exact_merged_count} nodes")
        
        # Phase 3: 语义去重（可选）
        semantic_merge_mapping = {}
        semantic_merged_count = 0
        
        if enable_semantic:
            logger.info("\n[Phase 3/4] Semantic deduplication...")
            
            # 3.1 获取剩余节点
            remaining_nodes = [
                node_id for node_id in candidates
                if node_id not in exact_merge_mapping and node_id in self.graph
            ]
            logger.info(f"  Remaining nodes after exact match: {len(remaining_nodes)}")
            
            if len(remaining_nodes) >= 2:
                # 3.2 生成候选对
                candidate_pairs = self._generate_semantic_candidates(
                    remaining_nodes,
                    max_candidates=max_candidates,
                    similarity_threshold=0.75  # 预筛选阈值（宽松）
                )
                logger.info(f"✓ Generated {len(candidate_pairs)} candidate pairs")
                
                # 3.3 验证候选对
                if candidate_pairs:
                    if use_llm_validation:
                        logger.info("  Using LLM validation (high accuracy mode)...")
                        semantic_merge_mapping, metadata = self._validate_candidates_with_llm(
                            candidate_pairs,
                            similarity_threshold
                        )
                    else:
                        logger.info("  Using embedding validation (fast mode)...")
                        semantic_merge_mapping, metadata = self._validate_candidates_with_embedding(
                            candidate_pairs,
                            similarity_threshold
                        )
                    
                    logger.info(f"✓ Identified {len(semantic_merge_mapping)} semantic matches")
                    
                    # 3.4 应用语义合并
                    semantic_merged_count = self._merge_head_nodes(semantic_merge_mapping, metadata)
                    logger.info(f"✓ Merged {semantic_merged_count} nodes")
                else:
                    logger.info("  No candidate pairs generated")
            else:
                logger.info("  Not enough nodes for semantic deduplication")
        else:
            logger.info("\n[Phase 3/4] Semantic deduplication skipped (disabled)")
        
        # Phase 4: 完整性验证
        logger.info("\n[Phase 4/4] Validating graph integrity...")
        issues = self.validate_graph_integrity_after_head_dedup()
        
        if any(issues.values()):
            logger.warning(f"⚠ Found integrity issues: {issues}")
        else:
            logger.info("✓ Graph integrity validated")
        
        elapsed_time = time.time() - start_time
        
        # 统计信息
        final_entity_count = len([
            n for n, d in self.graph.nodes(data=True)
            if d.get("label") == "entity"
        ])
        
        stats = {
            "total_candidates": len(candidates),
            "exact_merges": exact_merged_count,
            "semantic_merges": semantic_merged_count,
            "total_merges": exact_merged_count + semantic_merged_count,
            "initial_entity_count": len(candidates),
            "final_entity_count": final_entity_count,
            "reduction_rate": (exact_merged_count + semantic_merged_count) / len(candidates) * 100 if candidates else 0,
            "elapsed_time_seconds": elapsed_time,
            "integrity_issues": issues
        }
        
        logger.info("\n" + "=" * 70)
        logger.info("Head Deduplication Completed")
        logger.info("=" * 70)
        logger.info(f"Summary:")
        logger.info(f"  - Initial entities: {stats['initial_entity_count']}")
        logger.info(f"  - Final entities: {stats['final_entity_count']}")
        logger.info(f"  - Total merges: {stats['total_merges']}")
        logger.info(f"    • Exact matches: {stats['exact_merges']}")
        logger.info(f"    • Semantic matches: {stats['semantic_merges']}")
        logger.info(f"  - Reduction rate: {stats['reduction_rate']:.2f}%")
        logger.info(f"  - Time elapsed: {elapsed_time:.2f}s")
        logger.info("=" * 70)
        
        return stats
    
    # ============================================================
    # 辅助功能：完整性验证
    # ============================================================
    
    def validate_graph_integrity_after_head_dedup(self) -> Dict[str, List]:
        """
        验证去重后图结构的完整性
        
        检查项：
        1. 孤立节点（无入边也无出边的entity节点）
        2. 自环（head和tail相同的边）
        3. 悬空引用（边引用的节点不存在）
        4. 元数据完整性
        
        Returns:
            包含各类问题的字典
        """
        issues = {
            "orphan_nodes": [],
            "self_loops": [],
            "dangling_references": [],
            "missing_metadata": []
        }
        
        # 1. 检查孤立节点
        for node_id, data in self.graph.nodes(data=True):
            if data.get("label") == "entity":
                in_degree = self.graph.in_degree(node_id)
                out_degree = self.graph.out_degree(node_id)
                if in_degree == 0 and out_degree == 0:
                    issues["orphan_nodes"].append(node_id)
        
        # 2. 检查自环
        for u, v in self.graph.edges():
            if u == v:
                issues["self_loops"].append((u, v))
        
        # 3. 检查悬空引用
        for u, v, data in self.graph.edges(data=True):
            if u not in self.graph.nodes:
                issues["dangling_references"].append(("head", u, v))
            if v not in self.graph.nodes:
                issues["dangling_references"].append(("tail", u, v))
        
        # 4. 检查合并元数据完整性
        for node_id, data in self.graph.nodes(data=True):
            if "head_dedup" in data.get("properties", {}):
                dedup_info = data["properties"]["head_dedup"]
                if not isinstance(dedup_info, dict):
                    issues["missing_metadata"].append((node_id, "invalid_type"))
                elif "merged_nodes" not in dedup_info or "merge_history" not in dedup_info:
                    issues["missing_metadata"].append((node_id, "missing_fields"))
        
        return issues
    
    # ============================================================
    # 辅助功能：导出人工审核
    # ============================================================
    
    def export_head_merge_candidates_for_review(
        self,
        output_path: str,
        min_confidence: float = 0.70,
        max_confidence: float = 0.90
    ):
        """
        导出中等置信度的合并候选，供人工审核
        
        Args:
            output_path: 输出CSV文件路径
            min_confidence: 最小置信度
            max_confidence: 最大置信度
        """
        logger.info(f"Exporting head merge candidates for review (confidence: {min_confidence}-{max_confidence})...")
        
        candidates = []
        
        for node_id, data in self.graph.nodes(data=True):
            if data.get("label") != "entity":
                continue
            
            dedup_info = data.get("properties", {}).get("head_dedup", {})
            
            for merge_record in dedup_info.get("merge_history", []):
                confidence = merge_record.get("confidence", 1.0)
                
                if min_confidence <= confidence <= max_confidence:
                    candidates.append({
                        "canonical_node_id": node_id,
                        "canonical_name": data.get("properties", {}).get("name", ""),
                        "merged_node_id": merge_record["merged_node_id"],
                        "merged_name": merge_record["merged_node_name"],
                        "confidence": confidence,
                        "method": merge_record.get("method", "unknown"),
                        "rationale": merge_record["rationale"]
                    })
        
        # 导出为CSV
        if candidates:
            import csv
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = [
                    "canonical_node_id", "canonical_name",
                    "merged_node_id", "merged_name",
                    "confidence", "method", "rationale"
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(candidates)
            
            logger.info(f"✓ Exported {len(candidates)} merge candidates to {output_path}")
        else:
            logger.info("No candidates found in the specified confidence range")
