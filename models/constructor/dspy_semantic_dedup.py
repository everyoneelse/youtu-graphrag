"""
DSPy-based Semantic Deduplication Modules

This module provides DSPy implementations for:
1. LLM-based clustering of tail entities
2. Semantic deduplication (coreference resolution)
3. Attribute equivalence detection

使用DSPy可以自动优化prompt，提升去重质量并降低成本。
"""

import dspy
from typing import List, Dict, Tuple, Optional
import json
import json_repair
from utils.logger import logger


# ========== DSPy Signature Definitions ==========

class TailClustering(dspy.Signature):
    """
    初步聚类tail entities。
    
    目标：将可能指向同一实体的tails分到一组，为后续精细去重做准备。
    这是一个宽松的聚类步骤，宁可over-cluster也不要miss potential coreferences。
    """
    
    head_entity: str = dspy.InputField(
        desc="The head entity in the knowledge graph triple"
    )
    relation: str = dspy.InputField(
        desc="The relation connecting head to tails"
    )
    tail_candidates: str = dspy.InputField(
        desc="List of tail entities to cluster, numbered format: [1] tail1\\n[2] tail2\\n..."
    )
    
    reasoning: str = dspy.OutputField(
        desc=(
            "Brief analysis: Which tails are semantically similar or potentially coreferent? "
            "Consider: lexical similarity, semantic relatedness, potential aliases."
        )
    )
    
    clusters: str = dspy.OutputField(
        desc=(
            "JSON array of clusters. Each cluster contains semantically similar tails. "
            "Format: [{\"members\": [1, 2], \"description\": \"rationale\"}, ...]. "
            "Every tail index must appear exactly once. "
            "Group tails that might refer to the same entity or are very similar."
        )
    )


class CoreferenceResolution(dspy.Signature):
    """
    识别共指实体 - 判断哪些tail expressions指向同一个real-world entity。
    
    这是严格的去重步骤：只有真正指向同一实体的tails才应该被合并。
    """
    
    head_entity: str = dspy.InputField(
        desc="The head entity description"
    )
    relation: str = dspy.InputField(
        desc="The relation name (e.g., 'director', 'has_attribute')"
    )
    head_contexts: str = dspy.InputField(
        desc="Context passages where the head entity appears"
    )
    tail_candidates: str = dspy.InputField(
        desc=(
            "List of tail entities with their contexts. "
            "Format: [idx] Tail: description\\n    Contexts: context1\\n        context2\\n..."
        )
    )
    
    reasoning: str = dspy.OutputField(
        desc=(
            "Step-by-step coreference analysis for each pair of tails:\\n"
            "1. REFERENT TEST: Do they refer to the exact same entity?\\n"
            "2. SUBSTITUTION TEST: Can you swap them without changing meaning?\\n"
            "3. CONTEXT VALIDATION: Do contexts confirm coreference?\\n\\n"
            "CRITICAL: Don't merge just because tails satisfy the same relation. "
            "Multiple distinct entities can have the same relation to the head. "
            "Only merge if they are different names/expressions for THE SAME entity."
        )
    )
    
    coreference_groups: str = dspy.OutputField(
        desc=(
            "JSON array of coreference groups. Each group contains tail indices that refer to the SAME entity. "
            "Format: [{\"members\": [1, 2], \"representative\": 1, \"rationale\": \"...\"}, ...]. "
            "- 'members': 1-based indices of coreferent tails\\n"
            "- 'representative': index of the most informative expression\\n"
            "- 'rationale': why these are coreferent (not just related)\\n\\n"
            "Every tail must appear exactly once. "
            "Conservative principle: When in doubt, keep them separate."
        )
    )


class AttributeEquivalence(dspy.Signature):
    """
    识别属性值的等价关系。
    
    判断哪些属性值表达相同的property-value pair（只是表达方式不同）。
    """
    
    head_entity: str = dspy.InputField(
        desc="The entity that has these attributes"
    )
    relation: str = dspy.InputField(
        desc="The attribute relation (e.g., 'has_attribute', 'property')"
    )
    head_contexts: str = dspy.InputField(
        desc="Context passages about the head entity"
    )
    attribute_candidates: str = dspy.InputField(
        desc="List of attribute values with their contexts"
    )
    
    reasoning: str = dspy.OutputField(
        desc=(
            "For each pair of attribute values, check:\\n"
            "1. SAME PROPERTY: Do they describe the same attribute dimension?\\n"
            "2. SAME VALUE: Do they express the same measurement/quantity/state?\\n"
            "3. LINGUISTIC VARIATION: Is the difference only in notation/language?\\n\\n"
            "Examples of VALID merges:\\n"
            "- '10 cm' = '100 mm' (unit conversion)\\n"
            "- 'water' = 'H₂O' (notation)\\n"
            "- 'fifty' = '50' (number format)\\n\\n"
            "Do NOT merge different property values even if related."
        )
    )
    
    equivalence_groups: str = dspy.OutputField(
        desc=(
            "JSON array of equivalence groups. Each group contains attribute values expressing the SAME property-value. "
            "Format: [{\"members\": [1, 2], \"representative\": 1, \"rationale\": \"...\"}, ...]. "
            "Every attribute must appear exactly once."
        )
    )


# ========== DSPy Module Implementations ==========

class SemanticClusteringModule(dspy.Module):
    """
    DSPy模块: 使用LLM进行tail entities的初步聚类
    
    这个模块可以通过DSPy的optimizer自动优化，提升聚类质量。
    """
    
    def __init__(self, use_cot: bool = True):
        """
        Args:
            use_cot: 是否使用Chain-of-Thought reasoning (推荐开启)
        """
        super().__init__()
        
        if use_cot:
            self.cluster = dspy.ChainOfThought(TailClustering)
        else:
            self.cluster = dspy.Predict(TailClustering)
    
    def forward(self, head_entity: str, relation: str, tail_descriptions: List[str]) -> List[Dict]:
        """
        执行聚类
        
        Args:
            head_entity: 头实体描述
            relation: 关系名称
            tail_descriptions: 尾实体描述列表
        
        Returns:
            clusters: List of cluster dicts with 'members' and 'description'
        """
        # Format candidates with 1-based indices
        candidates_text = "\n".join([
            f"[{i+1}] {desc}" 
            for i, desc in enumerate(tail_descriptions)
        ])
        
        # Call DSPy module
        try:
            result = self.cluster(
                head_entity=head_entity,
                relation=relation,
                tail_candidates=candidates_text
            )
            
            # Parse JSON output
            clusters = json_repair.loads(result.clusters)
            
            # Validate format
            if not isinstance(clusters, list):
                raise ValueError("Clusters must be a list")
            
            # Ensure all indices are covered
            all_indices = set()
            for cluster in clusters:
                if isinstance(cluster, dict) and "members" in cluster:
                    all_indices.update(cluster["members"])
            
            # Add missing indices as singletons
            for i in range(1, len(tail_descriptions) + 1):
                if i not in all_indices:
                    clusters.append({
                        "members": [i],
                        "description": "Unassigned by LLM (added as singleton)"
                    })
            
            return clusters
            
        except Exception as e:
            logger.warning(f"DSPy clustering failed: {e}, returning single cluster fallback")
            # Fallback: return all items in one cluster
            return [{
                "members": list(range(1, len(tail_descriptions) + 1)),
                "description": f"Fallback cluster due to error: {str(e)}"
            }]


class SemanticDedupModule(dspy.Module):
    """
    DSPy模块: 使用LLM进行语义去重（共指消解）
    
    支持两种模式:
    1. general: 通用实体去重 (coreference resolution)
    2. attribute: 属性值等价检测
    """
    
    def __init__(self, prompt_type: str = "general", use_cot: bool = True):
        """
        Args:
            prompt_type: "general" or "attribute"
            use_cot: 是否使用Chain-of-Thought reasoning
        """
        super().__init__()
        self.prompt_type = prompt_type
        
        if prompt_type == "attribute":
            if use_cot:
                self.dedup = dspy.ChainOfThought(AttributeEquivalence)
            else:
                self.dedup = dspy.Predict(AttributeEquivalence)
        else:
            if use_cot:
                self.dedup = dspy.ChainOfThought(CoreferenceResolution)
            else:
                self.dedup = dspy.Predict(CoreferenceResolution)
    
    def forward(
        self, 
        head_entity: str, 
        relation: str, 
        head_contexts: List[str], 
        batch_entries: List[Dict]
    ) -> Tuple[List[Dict], str]:
        """
        执行语义去重
        
        Args:
            head_entity: 头实体描述
            relation: 关系名称
            head_contexts: 头实体的上下文
            batch_entries: 待去重的tail entries列表
        
        Returns:
            (groups, reasoning): 去重结果和推理过程
        """
        # Format inputs
        head_context_text = "\n".join(head_contexts) if head_contexts else "- (no context available)"
        
        candidates_blocks = []
        for idx, entry in enumerate(batch_entries, start=1):
            desc = entry.get("description", "[NO DESCRIPTION]")
            contexts = entry.get("context_summaries", ["- (no context available)"])
            context_block = "\n        ".join(contexts)
            candidates_blocks.append(
                f"[{idx}] Tail: {desc}\n    Contexts:\n        {context_block}"
            )
        
        candidates_text = "\n".join(candidates_blocks)
        
        # Call DSPy module
        try:
            if self.prompt_type == "attribute":
                result = self.dedup(
                    head_entity=head_entity,
                    relation=relation,
                    head_contexts=head_context_text,
                    attribute_candidates=candidates_text
                )
                groups_json = result.equivalence_groups
            else:
                result = self.dedup(
                    head_entity=head_entity,
                    relation=relation,
                    head_contexts=head_context_text,
                    tail_candidates=candidates_text
                )
                groups_json = result.coreference_groups
            
            # Parse JSON output
            groups = json_repair.loads(groups_json)
            
            # Validate and ensure all items are assigned
            if not isinstance(groups, list):
                raise ValueError("Groups must be a list")
            
            # Check all indices are covered
            all_indices = set()
            for group in groups:
                if isinstance(group, dict) and "members" in group:
                    all_indices.update(group["members"])
            
            # Add missing indices as singletons
            for i in range(1, len(batch_entries) + 1):
                if i not in all_indices:
                    groups.append({
                        "members": [i],
                        "representative": i,
                        "rationale": "Unassigned by LLM (kept separate)"
                    })
            
            reasoning = getattr(result, 'reasoning', '')
            return groups, reasoning
            
        except Exception as e:
            logger.warning(f"DSPy dedup failed: {e}, returning no groups")
            # Fallback: return empty groups (each item stays separate)
            return [], str(e)


# ========== Evaluation Metrics ==========

def clustering_metric(example, pred, trace=None) -> float:
    """
    评估聚类质量的metric
    
    使用pair-wise F1 score: 将clusters转换为成对关系，计算precision和recall
    
    Args:
        example: dspy.Example with gold_clusters
        pred: prediction (dspy.Prediction object or dict)
        trace: optional trace info
    
    Returns:
        F1 score (0-100)
    """
    try:
        # Extract gold clusters
        gold_clusters = example.gold_clusters
        
        # Extract predicted clusters
        if hasattr(pred, 'clusters'):
            # It's a dspy.Prediction object
            pred_clusters = json_repair.loads(pred.clusters)
        elif isinstance(pred, list):
            pred_clusters = pred
        else:
            return 0.0
        
        # Convert to sets of pairs
        def clusters_to_pairs(clusters):
            pairs = set()
            for cluster in clusters:
                if isinstance(cluster, dict):
                    members = cluster.get("members", [])
                elif isinstance(cluster, list):
                    members = cluster
                else:
                    continue
                
                # Create all pairs within this cluster
                for i in range(len(members)):
                    for j in range(i + 1, len(members)):
                        pair = tuple(sorted([members[i], members[j]]))
                        pairs.add(pair)
            
            return pairs
        
        gold_pairs = clusters_to_pairs(gold_clusters)
        pred_pairs = clusters_to_pairs(pred_clusters)
        
        # Handle edge cases
        if len(pred_pairs) == 0:
            return 100.0 if len(gold_pairs) == 0 else 0.0
        
        # Calculate metrics
        true_positive = len(gold_pairs & pred_pairs)
        false_positive = len(pred_pairs - gold_pairs)
        false_negative = len(gold_pairs - pred_pairs)
        
        precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) > 0 else 0
        recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) > 0 else 0
        
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        return f1 * 100
    
    except Exception as e:
        logger.warning(f"Error in clustering_metric: {e}")
        return 0.0


def dedup_metric(example, pred, trace=None) -> float:
    """
    评估去重质量的metric
    
    同样使用pair-wise F1 score，但考虑representative的选择
    
    Args:
        example: dspy.Example with gold_groups
        pred: prediction (dspy.Prediction object or dict)
        trace: optional trace info
    
    Returns:
        F1 score (0-100)
    """
    try:
        # Extract gold groups
        gold_groups = example.gold_groups
        
        # Extract predicted groups
        if hasattr(pred, 'coreference_groups'):
            pred_groups = json_repair.loads(pred.coreference_groups)
        elif hasattr(pred, 'equivalence_groups'):
            pred_groups = json_repair.loads(pred.equivalence_groups)
        elif isinstance(pred, tuple) and len(pred) > 0:
            pred_groups = pred[0]  # (groups, reasoning) tuple
        elif isinstance(pred, list):
            pred_groups = pred
        else:
            return 0.0
        
        # Use same pair-wise comparison as clustering
        return clustering_metric(
            type('Example', (), {'gold_clusters': gold_groups})(),
            pred_groups,
            trace
        )
    
    except Exception as e:
        logger.warning(f"Error in dedup_metric: {e}")
        return 0.0


# ========== Optimizer Wrapper ==========

class DSPySemanticDedupOptimizer:
    """
    DSPy优化器包装类
    
    用于训练和优化semantic dedup的DSPy模块
    """
    
    def __init__(
        self, 
        train_examples: List[dspy.Example], 
        validation_examples: List[dspy.Example]
    ):
        """
        Args:
            train_examples: 训练样本列表
            validation_examples: 验证样本列表
        """
        self.train_examples = train_examples
        self.validation_examples = validation_examples
    
    def optimize_clustering(
        self, 
        teacher_model: str = "gpt-4",
        student_model: str = "gpt-3.5-turbo",
        max_bootstrapped_demos: int = 4,
        max_labeled_demos: int = 4
    ) -> SemanticClusteringModule:
        """
        优化聚类模块
        
        使用BootstrapFewShot策略，用teacher model生成高质量示例，
        然后训练student model达到类似效果。
        
        Args:
            teacher_model: 高质量LLM (如GPT-4)
            student_model: 目标LLM (如GPT-3.5-turbo，更便宜)
            max_bootstrapped_demos: bootstrap示例数量
            max_labeled_demos: 标注示例数量
        
        Returns:
            优化后的聚类模块
        """
        logger.info(f"Optimizing clustering module: teacher={teacher_model}, student={student_model}")
        
        # Configure LLMs
        teacher_lm = dspy.OpenAI(model=teacher_model, max_tokens=2000, temperature=0.1)
        student_lm = dspy.OpenAI(model=student_model, max_tokens=2000, temperature=0.1)
        
        dspy.settings.configure(lm=student_lm)
        
        # Initialize module
        clustering_module = SemanticClusteringModule(use_cot=True)
        
        # Use BootstrapFewShot optimizer
        from dspy.teleprompt import BootstrapFewShot
        
        optimizer = BootstrapFewShot(
            metric=clustering_metric,
            max_bootstrapped_demos=max_bootstrapped_demos,
            max_labeled_demos=max_labeled_demos,
            teacher_settings=dict(lm=teacher_lm)
        )
        
        # Compile the module
        logger.info("Compiling clustering module...")
        optimized_module = optimizer.compile(
            clustering_module,
            trainset=self.train_examples
        )
        
        logger.info("Clustering module optimization completed")
        return optimized_module
    
    def optimize_dedup(
        self,
        prompt_type: str = "general",
        teacher_model: str = "gpt-4",
        student_model: str = "gpt-3.5-turbo",
        max_bootstrapped_demos: int = 3,
        max_labeled_demos: int = 3
    ) -> SemanticDedupModule:
        """
        优化去重模块
        
        Args:
            prompt_type: "general" or "attribute"
            teacher_model: 高质量LLM
            student_model: 目标LLM
            max_bootstrapped_demos: bootstrap示例数量
            max_labeled_demos: 标注示例数量
        
        Returns:
            优化后的去重模块
        """
        logger.info(f"Optimizing dedup module ({prompt_type}): teacher={teacher_model}, student={student_model}")
        
        # Configure LLMs
        teacher_lm = dspy.OpenAI(model=teacher_model, max_tokens=3000, temperature=0.0)
        student_lm = dspy.OpenAI(model=student_model, max_tokens=3000, temperature=0.0)
        
        dspy.settings.configure(lm=student_lm)
        
        # Initialize module
        dedup_module = SemanticDedupModule(prompt_type=prompt_type, use_cot=True)
        
        # Use BootstrapFewShot optimizer
        from dspy.teleprompt import BootstrapFewShot
        
        optimizer = BootstrapFewShot(
            metric=dedup_metric,
            max_bootstrapped_demos=max_bootstrapped_demos,
            max_labeled_demos=max_labeled_demos,
            teacher_settings=dict(lm=teacher_lm)
        )
        
        # Compile the module
        logger.info("Compiling dedup module...")
        optimized_module = optimizer.compile(
            dedup_module,
            trainset=self.train_examples
        )
        
        logger.info("Dedup module optimization completed")
        return optimized_module
    
    def evaluate_module(
        self, 
        module: dspy.Module, 
        examples: List[dspy.Example], 
        metric_fn: callable
    ) -> Dict:
        """
        评估模块性能
        
        Args:
            module: DSPy模块
            examples: 测试样本
            metric_fn: 评估metric函数
        
        Returns:
            评估结果字典 {avg_score, scores, num_examples}
        """
        scores = []
        
        for example in examples:
            try:
                # Run prediction
                inputs = example.inputs()
                pred = module(**inputs)
                
                # Compute metric
                score = metric_fn(example, pred)
                scores.append(score)
            
            except Exception as e:
                logger.warning(f"Evaluation failed for example: {e}")
                scores.append(0.0)
        
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        return {
            "avg_score": avg_score,
            "scores": scores,
            "num_examples": len(examples),
            "min_score": min(scores) if scores else 0.0,
            "max_score": max(scores) if scores else 0.0
        }


# ========== Validation and Correction Signatures ==========

class DedupValidation(dspy.Signature):
    """
    验证semantic dedup的质量。
    
    检查合并决策是否正确，识别潜在错误（false positives/negatives），
    并给出质量评分。这是一个质量保证步骤。
    """
    
    head_entity: str = dspy.InputField(desc="The head entity")
    relation: str = dspy.InputField(desc="The relation type")
    original_tails: str = dspy.InputField(
        desc="Original list of tails before dedup. Format: [1] tail1\\n[2] tail2\\n..."
    )
    dedup_groups: str = dspy.InputField(
        desc=(
            "Deduplication results to validate. JSON format: "
            "[{\"members\": [1,2], \"representative\": 1, \"rationale\": \"...\"}]"
        )
    )
    contexts: str = dspy.InputField(desc="Context information for each tail")
    
    analysis: str = dspy.OutputField(
        desc=(
            "Detailed validation analysis:\\n"
            "1. Check each group for correctness\\n"
            "2. Identify potential FALSE POSITIVES (wrong merges - different entities merged together)\\n"
            "   Example: iPhone 13 and iPhone 14 should NOT be merged\\n"
            "3. Identify potential FALSE NEGATIVES (missed merges - same entity kept separate)\\n"
            "   Example: NYC and New York City should be merged but aren't\\n"
            "4. Evaluate representative selection (is the best expression chosen?)\\n"
            "5. Assess evidence quality from contexts"
        )
    )
    
    validation_results: str = dspy.OutputField(
        desc=(
            "JSON validation results:\\n"
            "{\\n"
            "  \"overall_quality\": 0.0-1.0,  // Overall quality score\\n"
            "  \"issues\": [\\n"
            "    {\\n"
            "      \"type\": \"false_positive|false_negative|bad_representative\",\\n"
            "      \"severity\": \"high|medium|low\",\\n"
            "      \"group_id\": int,\\n"
            "      \"description\": \"Clear explanation of the issue\",\\n"
            "      \"suggestion\": \"How to fix this issue\"\\n"
            "    }\\n"
            "  ],\\n"
            "  \"group_scores\": [{\"group_id\": 0, \"confidence\": 0.95}, ...]\\n"
            "}"
        )
    )


class DedupCorrection(dspy.Signature):
    """
    基于validation结果修正dedup决策。
    
    当validation发现质量问题时，这个模块尝试修正错误的合并决策。
    """
    
    head_entity: str = dspy.InputField(desc="The head entity")
    relation: str = dspy.InputField(desc="The relation")
    original_tails: str = dspy.InputField(desc="Original tails before dedup")
    current_groups: str = dspy.InputField(
        desc="Current dedup groups (possibly incorrect based on validation)"
    )
    validation_issues: str = dspy.InputField(
        desc="Issues identified by validation module (JSON format)"
    )
    contexts: str = dspy.InputField(desc="Context information for decision making")
    
    reasoning: str = dspy.OutputField(
        desc=(
            "Step-by-step reasoning for corrections:\\n"
            "1. Review each validation issue\\n"
            "2. For FALSE POSITIVES: Explain why the merge was wrong and how to split\\n"
            "3. For FALSE NEGATIVES: Explain why items should be merged\\n"
            "4. For BAD REPRESENTATIVES: Explain better choice\\n"
            "5. Justify final corrected grouping"
        )
    )
    
    corrected_groups: str = dspy.OutputField(
        desc=(
            "Corrected deduplication groups in JSON format.\\n"
            "Same format as input but with issues fixed.\\n"
            "Format: [{\"members\": [1, 2], \"representative\": 1, \"rationale\": \"...\"}, ...]"
        )
    )


# ========== Validation and Correction Modules ==========

class DedupValidationModule(dspy.Module):
    """
    DSPy模块: 验证semantic dedup的质量
    
    这个模块检查dedup结果，识别潜在错误，并给出质量评分。
    可以用于：
    1. 质量监控 - 识别可疑的去重结果
    2. 报告生成 - 生成去重质量报告
    3. 触发修正 - 当质量太低时触发自动修正
    """
    
    def __init__(self, use_cot: bool = True):
        """
        Args:
            use_cot: 是否使用Chain-of-Thought reasoning
        """
        super().__init__()
        
        if use_cot:
            self.validate = dspy.ChainOfThought(DedupValidation)
        else:
            self.validate = dspy.Predict(DedupValidation)
    
    def forward(
        self,
        head_entity: str,
        relation: str,
        original_tails: List[str],
        dedup_groups: List[Dict],
        contexts: List[List[str]] = None
    ) -> Dict:
        """
        验证去重结果
        
        Args:
            head_entity: 头实体
            relation: 关系
            original_tails: 原始的tail列表
            dedup_groups: 去重后的分组
            contexts: 每个tail的上下文（可选）
        
        Returns:
            验证结果字典 {
                "analysis": str,
                "overall_quality": float,
                "issues": List[Dict],
                "group_scores": List[Dict],
                "raw_results": Dict
            }
        """
        # Format inputs
        tails_text = "\\n".join([f"[{i+1}] {tail}" for i, tail in enumerate(original_tails)])
        groups_json = json.dumps(dedup_groups, ensure_ascii=False)
        
        # Format contexts
        if contexts:
            contexts_blocks = []
            for i, tail_contexts in enumerate(contexts, 1):
                context_str = "\\n    ".join(tail_contexts) if tail_contexts else "- (no context)"
                contexts_blocks.append(f"[{i}] Contexts:\\n    {context_str}")
            contexts_text = "\\n".join(contexts_blocks)
        else:
            contexts_text = "- (no context available)"
        
        try:
            # Call validation
            result = self.validate(
                head_entity=head_entity,
                relation=relation,
                original_tails=tails_text,
                dedup_groups=groups_json,
                contexts=contexts_text
            )
            
            # Parse validation results
            validation_results = json_repair.loads(result.validation_results)
            
            return {
                "analysis": result.analysis,
                "overall_quality": validation_results.get("overall_quality", 0.0),
                "issues": validation_results.get("issues", []),
                "group_scores": validation_results.get("group_scores", []),
                "raw_results": validation_results
            }
        
        except Exception as e:
            logger.warning(f"Validation failed: {e}")
            # Return default (assume OK)
            return {
                "analysis": f"Validation failed: {e}",
                "overall_quality": 0.5,
                "issues": [],
                "group_scores": [],
                "raw_results": {}
            }


class DedupCorrectionModule(dspy.Module):
    """
    DSPy模块: 基于validation结果修正去重决策
    
    当validation发现质量问题时，这个模块尝试修正错误。
    """
    
    def __init__(self, use_cot: bool = True):
        super().__init__()
        
        if use_cot:
            self.correct = dspy.ChainOfThought(DedupCorrection)
        else:
            self.correct = dspy.Predict(DedupCorrection)
    
    def forward(
        self,
        head_entity: str,
        relation: str,
        original_tails: List[str],
        current_groups: List[Dict],
        validation_issues: List[Dict],
        contexts: List[List[str]] = None
    ) -> Tuple[List[Dict], str]:
        """
        修正去重结果
        
        Args:
            head_entity: 头实体
            relation: 关系
            original_tails: 原始tails
            current_groups: 当前的分组（可能有错误）
            validation_issues: 发现的问题
            contexts: 上下文
        
        Returns:
            (corrected_groups, reasoning)
        """
        # Format inputs
        tails_text = "\\n".join([f"[{i+1}] {tail}" for i, tail in enumerate(original_tails)])
        groups_json = json.dumps(current_groups, ensure_ascii=False)
        issues_json = json.dumps(validation_issues, ensure_ascii=False)
        
        if contexts:
            contexts_blocks = []
            for i, tail_contexts in enumerate(contexts, 1):
                context_str = "\\n    ".join(tail_contexts) if tail_contexts else "- (no context)"
                contexts_blocks.append(f"[{i}]:\\n    {context_str}")
            contexts_text = "\\n".join(contexts_blocks)
        else:
            contexts_text = "- (no context)"
        
        try:
            result = self.correct(
                head_entity=head_entity,
                relation=relation,
                original_tails=tails_text,
                current_groups=groups_json,
                validation_issues=issues_json,
                contexts=contexts_text
            )
            
            corrected_groups = json_repair.loads(result.corrected_groups)
            reasoning = result.reasoning
            
            return corrected_groups, reasoning
        
        except Exception as e:
            logger.warning(f"Correction failed: {e}")
            # Return original groups
            return current_groups, f"Correction failed: {e}"


class MultiStageDedupPipeline(dspy.Module):
    """
    完整的多阶段去重pipeline
    
    Pipeline阶段:
    1. Clustering - 初步聚类相似的tails
    2. Deduplication - 精细去重，识别共指
    3. Validation - 验证去重质量（可选）
    4. Correction - 修正错误（可选）
    
    使用场景:
    - 基础场景: Stage 1+2 (Clustering + Dedup)
    - 质量监控: Stage 1+2+3 (+ Validation)
    - 自动修正: Stage 1+2+3+4 (Full pipeline)
    """
    
    def __init__(
        self,
        enable_validation: bool = True,
        enable_correction: bool = False,
        validation_threshold: float = 0.7
    ):
        """
        Args:
            enable_validation: 是否启用验证
            enable_correction: 是否启用自动修正（需要enable_validation=True）
            validation_threshold: 质量阈值，低于此值触发correction
        """
        super().__init__()
        
        # Stage 1: Clustering
        self.clustering = SemanticClusteringModule(use_cot=True)
        
        # Stage 2: Dedup
        self.dedup = SemanticDedupModule(use_cot=True)
        
        # Stage 3: Validation
        self.enable_validation = enable_validation
        if enable_validation:
            self.validation = DedupValidationModule(use_cot=True)
        
        # Stage 4: Correction
        self.enable_correction = enable_correction and enable_validation
        self.validation_threshold = validation_threshold
        if self.enable_correction:
            self.correction = DedupCorrectionModule(use_cot=True)
    
    def forward(
        self,
        head_entity: str,
        relation: str,
        tail_descriptions: List[str],
        contexts: List[List[str]] = None
    ) -> Dict:
        """
        执行完整的多阶段去重pipeline
        
        Returns:
            {
                "clusters": [...],           # Stage 1结果
                "initial_groups": [...],     # Stage 2结果
                "validation": {...},         # Stage 3结果（如果启用）
                "final_groups": [...],       # 最终结果
                "corrections_applied": bool, # 是否应用了修正
                "reasoning": {...}           # 各阶段的推理过程
            }
        """
        result = {
            "clusters": [],
            "initial_groups": [],
            "validation": None,
            "final_groups": [],
            "corrections_applied": False,
            "reasoning": {}
        }
        
        # Stage 1: Clustering
        logger.info("Stage 1: Clustering...")
        clusters = self.clustering(
            head_entity=head_entity,
            relation=relation,
            tail_descriptions=tail_descriptions
        )
        result["clusters"] = clusters
        
        # Stage 2: Dedup
        logger.info("Stage 2: Deduplication...")
        batch_entries = [
            {
                "description": desc,
                "context_summaries": contexts[i] if contexts else ["- (no context)"]
            }
            for i, desc in enumerate(tail_descriptions)
        ]
        
        head_contexts = ["- Context for head entity"]
        groups, dedup_reasoning = self.dedup(
            head_entity=head_entity,
            relation=relation,
            head_contexts=head_contexts,
            batch_entries=batch_entries
        )
        result["initial_groups"] = groups
        result["reasoning"]["dedup"] = dedup_reasoning
        
        # Stage 3: Validation
        if self.enable_validation:
            logger.info("Stage 3: Validation...")
            validation_result = self.validation(
                head_entity=head_entity,
                relation=relation,
                original_tails=tail_descriptions,
                dedup_groups=groups,
                contexts=contexts
            )
            result["validation"] = validation_result
            
            quality = validation_result.get("overall_quality", 1.0)
            issues = validation_result.get("issues", [])
            
            logger.info(f"  Quality Score: {quality:.2f}")
            logger.info(f"  Issues Found: {len(issues)}")
            
            # Stage 4: Correction (if needed)
            if self.enable_correction and quality < self.validation_threshold and issues:
                logger.info(f"Stage 4: Correction (quality {quality:.2f} < threshold {self.validation_threshold})...")
                corrected_groups, correction_reasoning = self.correction(
                    head_entity=head_entity,
                    relation=relation,
                    original_tails=tail_descriptions,
                    current_groups=groups,
                    validation_issues=issues,
                    contexts=contexts
                )
                result["final_groups"] = corrected_groups
                result["corrections_applied"] = True
                result["reasoning"]["correction"] = correction_reasoning
                logger.info("  ✓ Corrections applied")
            else:
                result["final_groups"] = groups
                logger.info("  ✓ No corrections needed")
        else:
            result["final_groups"] = groups
        
        return result


# ========== Validation Metrics ==========

def validation_metric(example, pred, trace=None) -> float:
    """
    评估validation模块的性能
    
    Args:
        example: 包含真实标签的样本
            - true_quality: 真实质量分数
            - true_issues: 真实的问题列表
        pred: validation模块的输出
    
    Returns:
        综合评分 (0-100)
    """
    try:
        # 提取预测结果
        if hasattr(pred, 'validation_results'):
            pred_results = json_repair.loads(pred.validation_results)
        elif isinstance(pred, dict):
            pred_results = pred
        else:
            return 0.0
        
        pred_quality = pred_results.get('overall_quality', 0.5)
        pred_issues = pred_results.get('issues', [])
        
        # 提取真实标签
        true_quality = example.true_quality
        true_issues = example.true_issues
        
        # 1. Quality score accuracy
        quality_error = abs(pred_quality - true_quality)
        quality_score = max(0, 100 - quality_error * 100)
        
        # 2. Issue detection F1
        pred_issue_types = set([issue['type'] for issue in pred_issues])
        true_issue_types = set([issue['type'] for issue in true_issues])
        
        if len(pred_issue_types) == 0 and len(true_issue_types) == 0:
            issue_f1 = 100.0
        elif len(pred_issue_types) == 0 or len(true_issue_types) == 0:
            issue_f1 = 0.0
        else:
            tp = len(pred_issue_types & true_issue_types)
            fp = len(pred_issue_types - true_issue_types)
            fn = len(true_issue_types - pred_issue_types)
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            issue_f1 = 2 * precision * recall / (precision + recall) * 100 if (precision + recall) > 0 else 0
        
        # 综合评分: 60% quality accuracy + 40% issue detection
        final_score = 0.6 * quality_score + 0.4 * issue_f1
        
        return final_score
    
    except Exception as e:
        logger.warning(f"Error in validation_metric: {e}")
        return 0.0
