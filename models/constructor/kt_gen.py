import copy
import json
import os
import threading
import time
from concurrent import futures
from typing import Any, Dict, List, Tuple
from collections import defaultdict


import nanoid
import networkx as nx
import tiktoken
import json_repair
from tqdm import tqdm

from config import get_config
from utils import call_llm_api, graph_processor, tree_comm
from utils.logger import logger

import numpy as np

DEFAULT_SEMANTIC_DEDUP_PROMPT = (
    "You are a knowledge graph curation assistant performing entity deduplication.\n"
    "All listed triples share the same head entity and relation.\n\n"
    "Head entity: {head}\n"
    "Relation: {relation}\n\n"
    "Head contexts:\n{head_context}\n\n"
    "Candidate tails:\n"
    "{candidates}\n\n"
    "TASK: Identify which tails are COREFERENT (refer to the exact same entity/concept).\n\n"
    "FUNDAMENTAL PRINCIPLE:\n"
    "COREFERENCE requires REFERENTIAL IDENTITY: Two expressions must denote the exact same referent.\n"
    "- MERGE: 'Entity_A' and 'Entity_A_alias' → same referent (different names for one thing)\n"
    "- DO NOT MERGE: 'Entity_X' and 'Entity_Y' → different referents (two distinct things)\n\n"
    "CRITICAL DISTINCTION - Relation Satisfaction vs Entity Identity:\n"
    "⚠️  If multiple tails all satisfy relation R with head H, this does NOT make them coreferent.\n"
    "Each tail can be a DIFFERENT entity that happens to satisfy the SAME relation.\n"
    "Formal logic: (H,R,X) ∧ (H,R,Y) ↛ X=Y  (relation satisfaction does not imply entity identity)\n\n"
    "MERGE CONDITIONS - ALL must hold:\n"
    "1. REFERENT TEST: Do the two tails refer to exactly the same entity in the real world?\n"
    "   • Same entity, different names → MERGE (e.g., 'NYC' = 'New York City')\n"
    "   • Different entities → KEEP SEPARATE (even if highly related)\n\n"
    "2. SUBSTITUTION TEST: Can you replace one tail with the other in ALL contexts without changing truth value?\n"
    "   • If substitution changes meaning/information → KEEP SEPARATE\n"
    "   • If substitution preserves meaning → MERGE\n\n"
    "3. EQUIVALENCE CLASS: After merging, all members must denote the SAME single entity.\n"
    "   • Do NOT create groups containing multiple distinct entities\n"
    "   • Each group = one entity with different linguistic expressions\n\n"
    "PROHIBITED MERGE REASONS (these are NOT valid reasons to merge):\n"
    "✗ Shared relation: \"Both satisfy R with H\" → NOT sufficient for coreference\n"
    "✗ Semantic similarity: \"X and Y are similar/related\" → similarity ≠ identity\n"
    "✗ Same category: \"Both are type T\" → category membership ≠ entity identity\n"
    "✗ Co-occurrence: \"X and Y appear together\" → contextual proximity ≠ coreference\n"
    "✗ Functional relationship: \"X causes/affects/contains Y\" → relationship ≠ identity\n"
    "✗ Shared properties: \"X and Y have property P\" → property sharing ≠ entity identity\n"
    "✗ Part of same set: \"X, Y ∈ Set_S\" → set membership ≠ element identity\n\n"
    "MULTI-VALUED RELATIONS:\n"
    "Many relations map one head to MULTIPLE distinct tail entities. Each tail is a separate instance.\n"
    "Pattern: If H has relation R to {T1, T2, ..., Tn}, each Ti is typically a DIFFERENT entity.\n"
    "Only merge Ti and Tj if they are different names for the SAME entity, not just because both satisfy R.\n\n"
    "DECISION PROCEDURE:\n"
    "For each pair of tails (Ti, Tj):\n"
    "  1. Ask: \"Do Ti and Tj refer to the same entity?\" (not \"Are they related?\")\n"
    "  2. Apply SUBSTITUTION TEST: Would swapping them change the information?\n"
    "  3. If uncertain → KEEP SEPARATE (conservative principle)\n\n"
    "CONSERVATIVE PRINCIPLE:\n"
    "False splits (keeping coreferent entities separate) < False merges (merging distinct entities)\n"
    "When in doubt, preserve distinctions.\n\n"
    "OUTPUT REQUIREMENTS:\n"
    "1. Every input index must appear in exactly one group\n"
    "2. Each group represents ONE entity with its various expressions\n"
    "3. Choose representative following these priority rules:\n"
    "   a) PREFER full form over abbreviation (e.g., 'Magnetic Resonance Imaging' > 'MRI')\n"
    "   b) PREFER complete name over shortened form (e.g., 'spin echo sequence' > 'SE sequence')\n"
    "   c) PREFER descriptive term over acronym/code (e.g., 'hypertension' > 'HTN')\n"
    "   d) PREFER the most informative and self-explanatory expression\n"
    "   e) AVOID selecting abbreviations/acronyms unless no full form exists\n"
    "4. Provide clear rationale based on REFERENTIAL IDENTITY\n\n"
    "Respond with strict JSON using this schema:\n"
    "{{\n"
    "  \"groups\": [\n"
    "    {{\"members\": [1, 3], \"representative\": 3, \"rationale\": \"Why these expressions are coreferent (same referent).\"}}\n"
    "  ]\n"
    "}}\n"
)

DEFAULT_ATTRIBUTE_DEDUP_PROMPT = (
    "You are a knowledge graph curation assistant performing attribute value deduplication.\n"
    "All listed triples share the same head entity and relation.\n\n"
    "Head entity: {head}\n"
    "Relation: {relation}\n\n"
    "Head contexts:\n{head_context}\n\n"
    "Candidate attribute values:\n"
    "{candidates}\n\n"
    "TASK: Identify which attribute values are EQUIVALENT (express the exact same property-value pair).\n\n"
    "FUNDAMENTAL PRINCIPLE:\n"
    "EQUIVALENCE requires VALUE IDENTITY: Two expressions must denote the exact same property-value combination.\n"
    "- MERGE: 'Value_A' and 'Value_A_expressed_differently' → same value (different expressions)\n"
    "- DO NOT MERGE: 'Value_X' and 'Value_Y' → different values (distinct property-value pairs)\n\n"
    "CRITICAL DISTINCTION - Relation Satisfaction vs Value Identity:\n"
    "⚠️  If multiple values all satisfy relation R with head H, this does NOT make them equivalent.\n"
    "Each value can be a DIFFERENT property/measurement that happens to satisfy the SAME relation.\n"
    "Formal: (H,R,V1) ∧ (H,R,V2) ↛ V1=V2  (co-satisfaction does not imply value equivalence)\n\n"
    "MERGE CONDITIONS - ALL must hold:\n"
    "1. SAME PROPERTY: Both values describe the same property/dimension/attribute.\n"
    "   • Property_A and Property_B → KEEP SEPARATE (different properties)\n"
    "   • Property_A and Property_A → proceed to condition 2\n\n"
    "2. SAME VALUE: Both express the same measurement/state/quantity for that property.\n"
    "   • Value_1 and Value_2 → KEEP SEPARATE (different values)\n"
    "   • Value_X and Value_X → proceed to condition 3\n\n"
    "3. LINGUISTIC VARIATION: The difference is only in expression, not in meaning.\n"
    "   Acceptable variations:\n"
    "   • Unit conversion: '10 cm' = '100 mm' (same length, different units)\n"
    "   • Language: 'water' = 'H₂O' = '水' (same substance, different languages/notations)\n"
    "   • Notation: 'fifty' = '50' = '5×10¹' (same number, different representations)\n\n"
    "PROHIBITED MERGE REASONS (these are NOT valid reasons to merge):\n"
    "✗ Shared entity: \"Both are attributes of H\" → NOT sufficient for equivalence\n"
    "✗ Shared relation: \"Both satisfy R with H\" → NOT sufficient for equivalence\n"
    "✗ Same domain: \"Both are from domain D\" → domain membership ≠ value identity\n"
    "✗ Related properties: \"Property_A affects Property_B\" → relationship ≠ equivalence\n"
    "✗ Similar magnitude: \"Value_1 ≈ Value_2\" → similarity ≠ identity\n"
    "✗ Co-occurrence: \"V1 and V2 appear together\" → correlation ≠ equivalence\n"
    "✗ Part of pattern: \"V1, V2 ∈ {set of attributes}\" → set membership ≠ element identity\n\n"
    "MULTI-VALUED ATTRIBUTES:\n"
    "Many entities possess MULTIPLE distinct attribute values for the same relation type.\n"
    "Pattern: If H has relation R to {A1, A2, ..., An}, each Ai is typically a DIFFERENT attribute value.\n"
    "Only merge Ai and Aj if they express the SAME property-value in different ways.\n\n"
    "DECISION PROCEDURE:\n"
    "For each pair of values (Vi, Vj):\n"
    "  1. Ask: \"Do Vi and Vj express the same property?\" → If NO, KEEP SEPARATE\n"
    "  2. Ask: \"Do Vi and Vj express the same value/measurement?\" → If NO, KEEP SEPARATE\n"
    "  3. Ask: \"Is the difference only linguistic/notational?\" → If NO, KEEP SEPARATE\n"
    "  4. If uncertain → KEEP SEPARATE (conservative principle)\n\n"
    "CONSERVATIVE PRINCIPLE:\n"
    "False splits (keeping equivalent values separate) < False merges (merging distinct values)\n"
    "When in doubt, preserve distinctions.\n\n"
    "OUTPUT REQUIREMENTS:\n"
    "1. Every input index must appear in exactly one group\n"
    "2. Each group represents ONE property-value pair with its various expressions\n"
    "3. Choose representative following these priority rules:\n"
    "   a) PREFER full form over abbreviation (e.g., 'Magnetic Resonance Imaging' > 'MRI')\n"
    "   b) PREFER complete name over shortened form (e.g., 'spin echo sequence' > 'SE sequence')\n"
    "   c) PREFER descriptive term over acronym/code (e.g., 'hypertension' > 'HTN')\n"
    "   d) PREFER the most complete and informative expression\n"
    "   e) AVOID selecting abbreviations/acronyms unless no full form exists\n"
    "4. Provide clear rationale based on VALUE IDENTITY\n\n"
    "Respond with strict JSON using this schema:\n"
    "{{\n"
    "  \"groups\": [\n"
    "    {{\"members\": [1, 3], \"representative\": 3, \"rationale\": \"Why these are equivalent (same property-value).\"}}\n"
    "  ]\n"
    "}}\n"
)

# 中文版实体去重prompt
DEFAULT_SEMANTIC_DEDUP_PROMPT_ZH = (
    "你是一个知识图谱管理助手，负责执行实体去重任务。\n"
    "所有列出的三元组共享相同的头实体和关系。\n\n"
    "头实体：{head}\n"
    "关系：{relation}\n\n"
    "头实体上下文：\n{head_context}\n\n"
    "候选尾实体：\n"
    "{candidates}\n\n"
    "任务：识别哪些尾实体是共指的（指代完全相同的实体/概念）。\n\n"
    "基本原则：\n"
    "共指要求指称同一性：两个表达必须指代完全相同的指称对象。\n"
    "- 合并：'实体_A' 和 '实体_A_别名' → 相同指称对象（一个事物的不同名称）\n"
    "- 不合并：'实体_X' 和 '实体_Y' → 不同指称对象（两个不同的事物）\n\n"
    "关键区别 - 关系满足 vs 实体同一性：\n"
    "⚠️  如果多个尾实体都满足与头实体H的关系R，这并不意味着它们是共指的。\n"
    "每个尾实体可以是恰好满足同一关系的不同实体。\n"
    "形式逻辑：(H,R,X) ∧ (H,R,Y) ↛ X=Y（关系满足不意味着实体同一性）\n\n"
    "合并条件 - 必须全部满足：\n"
    "1. 指称测试：两个尾实体是否指代现实世界中完全相同的实体？\n"
    "   • 相同实体，不同名称 → 合并（例如：'NYC' = 'New York City'）\n"
    "   • 不同实体 → 保持分离（即使高度相关）\n\n"
    "2. 替换测试：你能在所有上下文中用一个尾实体替换另一个而不改变真值吗？\n"
    "   • 如果替换改变含义/信息 → 保持分离\n"
    "   • 如果替换保留含义 → 合并\n\n"
    "3. 等价类：合并后，所有成员必须指代同一个单一实体。\n"
    "   • 不要创建包含多个不同实体的组\n"
    "   • 每个组 = 一个实体的不同语言表达\n\n"
    "禁止的合并理由（这些不是合并的有效理由）：\n"
    "✗ 共享关系：\"都满足与H的关系R\" → 不足以构成共指\n"
    "✗ 语义相似：\"X和Y相似/相关\" → 相似性 ≠ 同一性\n"
    "✗ 相同类别：\"都是类型T\" → 类别成员资格 ≠ 实体同一性\n"
    "✗ 共现：\"X和Y一起出现\" → 上下文接近 ≠ 共指\n"
    "✗ 功能关系：\"X导致/影响/包含Y\" → 关系 ≠ 同一性\n"
    "✗ 共享属性：\"X和Y有属性P\" → 属性共享 ≠ 实体同一性\n"
    "✗ 同一集合的一部分：\"X, Y ∈ 集合_S\" → 集合成员资格 ≠ 元素同一性\n\n"
    "多值关系：\n"
    "许多关系将一个头实体映射到多个不同的尾实体。每个尾实体是一个独立的实例。\n"
    "模式：如果H与关系R有{T1, T2, ..., Tn}，每个Ti通常是一个不同的实体。\n"
    "只有当Ti和Tj是同一实体的不同名称时才合并它们，而不仅仅因为它们都满足R。\n\n"
    "决策程序：\n"
    "对于每对尾实体(Ti, Tj)：\n"
    "  1. 问：\"Ti和Tj是否指代同一实体？\"（不是\"它们相关吗？\"）\n"
    "  2. 应用替换测试：交换它们会改变信息吗？\n"
    "  3. 如果不确定 → 保持分离（保守原则）\n\n"
    "保守原则：\n"
    "错误分割（保持共指实体分离）< 错误合并（合并不同实体）\n"
    "有疑问时，保留区别。\n\n"
    "输出要求：\n"
    "1. 每个输入索引必须恰好出现在一个组中\n"
    "2. 每个组代表一个实体及其各种表达形式\n"
    "3. 按照以下优先级规则选择代表性表达：\n"
    "   a) 优先选择完整形式而非缩写（例如：'磁共振成像' > 'MRI'）\n"
    "   b) 优先选择全称而非简称（例如：'自旋回波序列' > 'SE序列'）\n"
    "   c) 优先选择描述性术语而非首字母缩写/代码（例如：'高血压' > 'HTN'）\n"
    "   d) 优先选择信息量最大、最具自解释性的表达\n"
    "   e) 避免选择缩写/首字母缩写，除非不存在完整形式\n"
    "4. 提供基于指称同一性的清晰理由\n\n"
    "使用以下严格的JSON格式响应：\n"
    "{{\n"
    "  \"groups\": [\n"
    "    {{\"members\": [1, 3], \"representative\": 3, \"rationale\": \"为什么这些表达是共指的（相同指称对象）。\"}}\n"
    "  ]\n"
    "}}\n"
)

# 中文版属性去重prompt
DEFAULT_ATTRIBUTE_DEDUP_PROMPT_ZH = (
    "你是一个知识图谱管理助手，负责执行属性值去重任务。\n"
    "所有列出的三元组共享相同的头实体和关系。\n\n"
    "头实体：{head}\n"
    "关系：{relation}\n\n"
    "头实体上下文：\n{head_context}\n\n"
    "候选属性值：\n"
    "{candidates}\n\n"
    "任务：识别哪些属性值是等价的（表达完全相同的属性-值对）。\n\n"
    "基本原则：\n"
    "等价要求值同一性：两个表达必须指代完全相同的属性-值组合。\n"
    "- 合并：'值_A' 和 '值_A_不同表达' → 相同值（不同表达）\n"
    "- 不合并：'值_X' 和 '值_Y' → 不同值（不同的属性-值对）\n\n"
    "关键区别 - 关系满足 vs 值同一性：\n"
    "⚠️  如果多个值都满足与头实体H的关系R，这并不意味着它们是等价的。\n"
    "每个值可以是恰好满足同一关系的不同属性/测量。\n"
    "形式逻辑：(H,R,V1) ∧ (H,R,V2) ↛ V1=V2（共同满足不意味着值等价）\n\n"
    "合并条件 - 必须全部满足：\n"
    "1. 相同属性：两个值描述相同的属性/维度/特性。\n"
    "   • 属性_A 和 属性_B → 保持分离（不同属性）\n"
    "   • 属性_A 和 属性_A → 进入条件2\n\n"
    "2. 相同值：两者表达该属性的相同测量/状态/数量。\n"
    "   • 值_1 和 值_2 → 保持分离（不同值）\n"
    "   • 值_X 和 值_X → 进入条件3\n\n"
    "3. 语言变体：差异仅在表达上，而非含义上。\n"
    "   可接受的变体：\n"
    "   • 单位转换：'10厘米' = '100毫米'（相同长度，不同单位）\n"
    "   • 语言：'水' = 'H₂O' = 'water'（相同物质，不同语言/记号）\n"
    "   • 记法：'五十' = '50' = '5×10¹'（相同数字，不同表示）\n\n"
    "禁止的合并理由（这些不是合并的有效理由）：\n"
    "✗ 共享实体：\"都是H的属性\" → 不足以构成等价\n"
    "✗ 共享关系：\"都满足与H的关系R\" → 不足以构成等价\n"
    "✗ 相同领域：\"都来自领域D\" → 领域成员资格 ≠ 值同一性\n"
    "✗ 相关属性：\"属性_A影响属性_B\" → 关系 ≠ 等价\n"
    "✗ 相似量级：\"值_1 ≈ 值_2\" → 相似性 ≠ 同一性\n"
    "✗ 共现：\"V1和V2一起出现\" → 相关性 ≠ 等价\n"
    "✗ 模式的一部分：\"V1, V2 ∈ {属性集合}\" → 集合成员资格 ≠ 元素同一性\n\n"
    "多值属性：\n"
    "许多实体对于同一关系类型拥有多个不同的属性值。\n"
    "模式：如果H与关系R有{A1, A2, ..., An}，每个Ai通常是一个不同的属性值。\n"
    "只有当Ai和Aj以不同方式表达相同的属性-值时才合并它们。\n\n"
    "决策程序：\n"
    "对于每对值(Vi, Vj)：\n"
    "  1. 问：\"Vi和Vj表达相同的属性吗？\" → 如果否，保持分离\n"
    "  2. 问：\"Vi和Vj表达相同的值/测量吗？\" → 如果否，保持分离\n"
    "  3. 问：\"差异仅在语言/记号上吗？\" → 如果否，保持分离\n"
    "  4. 如果不确定 → 保持分离（保守原则）\n\n"
    "保守原则：\n"
    "错误分割（保持等价值分离）< 错误合并（合并不同值）\n"
    "有疑问时，保留区别。\n\n"
    "输出要求：\n"
    "1. 每个输入索引必须恰好出现在一个组中\n"
    "2. 每个组代表一个属性-值对及其各种表达形式\n"
    "3. 按照以下优先级规则选择代表性表达：\n"
    "   a) 优先选择完整形式而非缩写（例如：'磁共振成像' > 'MRI'）\n"
    "   b) 优先选择全称而非简称（例如：'自旋回波序列' > 'SE序列'）\n"
    "   c) 优先选择描述性术语而非首字母缩写/代码（例如：'高血压' > 'HTN'）\n"
    "   d) 优先选择最完整、最具信息量的表达\n"
    "   e) 避免选择缩写/首字母缩写，除非不存在完整形式\n"
    "4. 提供基于值同一性的清晰理由\n\n"
    "使用以下严格的JSON格式响应：\n"
    "{{\n"
    "  \"groups\": [\n"
    "    {{\"members\": [1, 3], \"representative\": 3, \"rationale\": \"为什么这些是等价的（相同属性-值）。\"}}\n"
    "  ]\n"
    "}}\n"
)

DEFAULT_LLM_CLUSTERING_PROMPT = (
    "You are a knowledge graph curation assistant performing initial clustering of tail entities.\n"
    "All listed tail entities share the same head entity and relation.\n\n"
    "Head entity: {head}\n"
    "Relation: {relation}\n\n"
    "Candidate tails:\n"
    "{candidates}\n\n"
    "TASK: Group these tails into PRELIMINARY CLUSTERS based on semantic similarity.\n"
    "This is an initial clustering step - your goal is to group tails that MIGHT refer to the same entity.\n\n"
    "CLUSTERING PRINCIPLE:\n"
    "Group tails together if they are:\n"
    "1. POTENTIALLY COREFERENT: Could refer to the same entity (e.g., 'NYC' and 'New York City')\n"
    "2. SEMANTICALLY VERY SIMILAR: Very similar concepts that need further examination\n"
    "3. LEXICALLY RELATED: Different expressions of potentially the same thing\n\n"
    "KEEP SEPARATE if tails are:\n"
    "1. CLEARLY DISTINCT: Obviously different entities (e.g., 'Paris' vs 'London')\n"
    "2. SEMANTICALLY DIFFERENT: Different concepts (e.g., 'color' vs 'size')\n"
    "3. UNRELATED: No clear semantic connection\n\n"
    "CLUSTERING GUIDELINES:\n"
    "- Be INCLUSIVE in this initial clustering - it's better to over-cluster than under-cluster\n"
    "- Subsequent LLM refinement will separate false positives within clusters\n"
    "- Focus on semantic similarity, not just string matching\n"
    "- Group by meaning/concept rather than exact wording\n"
    "- Each tail must appear in exactly ONE cluster\n\n"
    "EXAMPLES:\n"
    "✓ Cluster together: ['New York', 'NYC', 'New York City'] - potential coreference\n"
    "✓ Cluster together: ['United States', 'USA', 'US', 'America'] - potential coreference\n"
    "✓ Keep separate: ['Paris', 'London', 'Berlin'] - clearly distinct cities\n"
    "✓ Keep separate: ['red', 'large', 'heavy'] - different property types\n\n"
    "OUTPUT REQUIREMENTS:\n"
    "1. Every input index must appear in exactly one cluster\n"
    "2. Each cluster should contain semantically similar tails\n"
    "3. Provide a brief description for each cluster explaining the grouping rationale\n\n"
    "Respond with strict JSON using this schema:\n"
    "{{\n"
    "  \"clusters\": [\n"
    "    {{\n"
    "      \"members\": [1, 3, 5],\n"
    "      \"description\": \"Brief explanation of why these tails are clustered together\"\n"
    "    }},\n"
    "    {{\n"
    "      \"members\": [2],\n"
    "      \"description\": \"This tail is semantically distinct from others\"\n"
    "    }}\n"
    "  ]\n"
    "}}\n"
)

class KTBuilder:
    def __init__(self, dataset_name, schema_path=None, mode=None, config=None):
        if config is None:
            config = get_config()
        
        self.config = config
        self.dataset_name = dataset_name
        self.schema = self.load_schema(schema_path or config.get_dataset_config(dataset_name).schema_path)
        self.graph = nx.MultiDiGraph()
        self.node_counter = 0
        self.datasets_no_chunk = config.construction.datasets_no_chunk
        self.token_len = 0
        self.lock = threading.Lock()
        
        # Initialize LLM clients
        self._init_llm_clients()
        
        self.all_chunks = {}
        self.mode = mode or config.construction.mode
        self._semantic_dedup_embedder = None
    
    def _init_llm_clients(self):
        """Initialize LLM clients for different tasks."""
        # Default LLM client (for general construction tasks)
        self.llm_client = call_llm_api.LLMCompletionCall()
        
        # Get semantic dedup config
        semantic_config = getattr(self.config.construction, "semantic_dedup", None)
        
        if semantic_config:
            # Clustering LLM client
            clustering_llm_config = getattr(semantic_config, "clustering_llm", None)
            if clustering_llm_config and clustering_llm_config.model:
                # Use custom clustering LLM
                self.clustering_llm_client = call_llm_api.LLMCompletionCall(
                    model=clustering_llm_config.model or None,
                    base_url=clustering_llm_config.base_url or None,
                    api_key=clustering_llm_config.api_key or None,
                    temperature=clustering_llm_config.temperature
                )
                logger.info(f"Initialized custom clustering LLM: {clustering_llm_config.model}")
            else:
                # Use default LLM for clustering
                self.clustering_llm_client = self.llm_client
                logger.info("Using default LLM for clustering")
            
            # Deduplication LLM client
            dedup_llm_config = getattr(semantic_config, "dedup_llm", None)
            if dedup_llm_config and dedup_llm_config.model:
                # Use custom dedup LLM
                self.dedup_llm_client = call_llm_api.LLMCompletionCall(
                    model=dedup_llm_config.model or None,
                    base_url=dedup_llm_config.base_url or None,
                    api_key=dedup_llm_config.api_key or None,
                    temperature=dedup_llm_config.temperature
                )
                logger.info(f"Initialized custom deduplication LLM: {dedup_llm_config.model}")
            else:
                # Use default LLM for deduplication
                self.dedup_llm_client = self.llm_client
                logger.info("Using default LLM for deduplication")
        else:
            # No semantic dedup config, use default for both
            self.clustering_llm_client = self.llm_client
            self.dedup_llm_client = self.llm_client

    def load_schema(self, schema_path) -> Dict[str, Any]:
        try:
            with open(schema_path) as f:
                schema = json.load(f)
                return schema
        except FileNotFoundError:
            return dict()


    def chunk_text(self, text) -> Tuple[List[str], Dict[str, str]]:
        if self.dataset_name in self.datasets_no_chunk:
            chunks = [f"{text.get('title', '')} {text.get('text', '')}".strip() 
                     if isinstance(text, dict) else str(text)]
        else:
            chunks = [str(text)]

        chunk2id = {}
        for chunk in chunks:
            try:
                chunk_id = nanoid.generate(size=8)
                chunk2id[chunk_id] = chunk
            except Exception as e:
                logger.warning(f"Failed to generate chunk id with nanoid: {type(e).__name__}: {e}")

        with self.lock:
            self.all_chunks.update(chunk2id)

        return chunks, chunk2id

    def _clean_text(self, text: str) -> str:
        if not text:
            return "[EMPTY_TEXT]"
        
        if self.dataset_name == "graphrag-bench":
            safe_chars = {
                *" .:,!?()-+=[]{}()\\/|_^~<>*&%$#@!;\"'`"
            }
            cleaned = "".join(
                char for char in text 
                if char.isalnum() or char.isspace() or char in safe_chars
            ).strip()
        else:
            safe_chars = {
                *" .:,!?()-+="  
            }
            cleaned = "".join(
                char for char in text 
                if char.isalnum() or char.isspace() or char in safe_chars
            ).strip()
        
        return cleaned if cleaned else "[EMPTY_AFTER_CLEANING]"
    
    def save_chunks_to_file(self):
        os.makedirs("output/chunks", exist_ok=True)
        chunk_file = f"output/chunks/{self.dataset_name}.txt"
        
        existing_data = {}
        if os.path.exists(chunk_file):
            try:
                with open(chunk_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and "\t" in line:
                            # Parse line format: "id: {id} \tChunk: {chunk text}"
                            parts = line.split("\t", 1)
                            if len(parts) == 2 and parts[0].startswith("id: ") and parts[1].startswith("Chunk: "):
                                chunk_id = parts[0][4:] 
                                chunk_text = parts[1][7:] 
                                existing_data[chunk_id] = chunk_text
            except Exception as e:
                logger.warning(f"Failed to parse existing chunks from {chunk_file}: {type(e).__name__}: {e}")
        
        all_data = {**existing_data, **self.all_chunks}
        
        with open(chunk_file, "w", encoding="utf-8") as f:
            for chunk_id, chunk_text in all_data.items():
                f.write(f"id: {chunk_id}\tChunk: {chunk_text}\n")
        
        logger.info(f"Chunk data saved to {chunk_file} ({len(all_data)} chunks)")
    
    def extract_with_llm(self, prompt: str):
        response = self.llm_client.call_api(prompt)
        parsed_dict = json_repair.loads(response)
        parsed_json = json.dumps(parsed_dict, ensure_ascii=False)
        return parsed_json 

    def token_cal(self, text: str):
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    
    def _get_construction_prompt(self, chunk: str) -> str:
        """Get the appropriate construction prompt based on dataset name and mode (agent/noagent)."""
        recommend_schema = json.dumps(self.schema, ensure_ascii=False)
        
        # Base prompt type mapping
        prompt_type_map = {
            "novel": "novel",
            "novel_eng": "novel_eng"
        }
        
        base_prompt_type = prompt_type_map.get(self.dataset_name, "general")
        
        # Add agent suffix if in agent mode
        if self.mode == "agent":
            prompt_type = f"{base_prompt_type}_agent"
        else:
            prompt_type = base_prompt_type
        
        return self.config.get_prompt_formatted("construction", prompt_type, schema=recommend_schema, chunk=chunk)
    
    def _validate_and_parse_llm_response(self, prompt: str, llm_response: str) -> dict:
        """Validate and parse LLM response, returning None if invalid."""
        if llm_response is None:
            return None
            
        try:
            self.token_len += self.token_cal(prompt + llm_response)
            return json_repair.loads(llm_response)
        except Exception as e:
            llm_response_str = str(llm_response) if llm_response is not None else "None"
            return None
    
    def _find_or_create_entity(self, entity_name: str, chunk_id: int, nodes_to_add: list, entity_type: str = None) -> str:
        """Find existing entity or create a new one, returning the entity node ID."""
        with self.lock:
            entity_node_id = next(
                (
                    n
                    for n, d in self.graph.nodes(data=True)
                    if d.get("label") == "entity" and d["properties"]["name"] == entity_name
                ),
                None,
            )
            
            if not entity_node_id:
                entity_node_id = f"entity_{self.node_counter}"
                properties = {"name": entity_name, "chunk id": chunk_id}
                if entity_type:
                    properties["schema_type"] = entity_type
                
                nodes_to_add.append((
                    entity_node_id,
                    {
                        "label": "entity", 
                        "properties": properties, 
                        "level": 2
                    }
                ))
                self.node_counter += 1
                
        return entity_node_id
    
    def _validate_triple_format(self, triple: list) -> tuple:
        """Validate and normalize triple format, returning (subject, predicate, object) or None."""
        try:
            if len(triple) > 3:
                triple = triple[:3]
            elif len(triple) < 3:
                return None
            
            return tuple(triple)
        except Exception as e:
            return None
    
    def _process_attributes(self, extracted_attr: dict, chunk_id: int, entity_types: dict = None) -> tuple[list, list]:
        """Process extracted attributes and return nodes and edges to add."""
        nodes_to_add = []
        edges_to_add = []
        
        for entity, attributes in extracted_attr.items():
            for attr in attributes:
                # Create attribute node
                attr_node_id = f"attr_{self.node_counter}"
                nodes_to_add.append((
                    attr_node_id,
                    {
                        "label": "attribute",
                        "properties": {"name": attr, "chunk id": chunk_id},
                        "level": 1,
                    }
                ))
                self.node_counter += 1

                entity_type = entity_types.get(entity) if entity_types else None
                entity_node_id = self._find_or_create_entity(entity, chunk_id, nodes_to_add, entity_type)
                edges_to_add.append((entity_node_id, attr_node_id, "has_attribute"))
        
        return nodes_to_add, edges_to_add
    
    def _process_triples(self, extracted_triples: list, chunk_id: int, entity_types: dict = None) -> tuple[list, list]:
        """Process extracted triples and return nodes and edges to add."""
        nodes_to_add = []
        edges_to_add = []
        
        for triple in extracted_triples:
            validated_triple = self._validate_triple_format(triple)
            if not validated_triple:
                continue
                
            subj, pred, obj = validated_triple
            
            subj_type = entity_types.get(subj) if entity_types else None
            obj_type = entity_types.get(obj) if entity_types else None
            
            subj_node_id = self._find_or_create_entity(subj, chunk_id, nodes_to_add, subj_type)
            obj_node_id = self._find_or_create_entity(obj, chunk_id, nodes_to_add, obj_type)
            
            edges_to_add.append((subj_node_id, obj_node_id, pred))
        
        return nodes_to_add, edges_to_add

    def process_level1_level2(self, chunk: str, id: int):
        """Process attributes (level 1) and triples (level 2) with optimized structure."""
        prompt = self._get_construction_prompt(chunk)
        llm_response = self.extract_with_llm(prompt)
        
        # Validate and parse response
        parsed_response = self._validate_and_parse_llm_response(prompt, llm_response)
        if not parsed_response:
            return
        
        extracted_attr = parsed_response.get("attributes", {})
        extracted_triples = parsed_response.get("triples", [])
        entity_types = parsed_response.get("entity_types", {})
        
        # Process attributes and triples
        attr_nodes, attr_edges = self._process_attributes(extracted_attr, id, entity_types)
        triple_nodes, triple_edges = self._process_triples(extracted_triples, id, entity_types)
        
        all_nodes = attr_nodes + triple_nodes
        #all_edges = attr_edges + triple_edges
        
        with self.lock:
            for node_id, node_data in all_nodes:
                self.graph.add_node(node_id, **node_data)
            
            for u, v, relation in attr_edges:
                self.graph.add_edge(u, v, relation=relation)

            for subj, obj, relation, source_chunk_id in triple_edges:
                edge_data = {"relation": relation}
                if source_chunk_id:
                    edge_data["source_chunks"] = [source_chunk_id]
                self.graph.add_edge(subj, obj, **edge_data)

    
    def _find_or_create_entity_direct(self, entity_name: str, chunk_id: int, entity_type: str = None) -> str:
        """Find existing entity or create a new one directly in graph (for agent mode)."""
        entity_node_id = next(
            (
                n
                for n, d in self.graph.nodes(data=True)
                if d.get("label") == "entity" and d["properties"]["name"] == entity_name
            ),
            None,
        )
        
        if not entity_node_id:
            entity_node_id = f"entity_{self.node_counter}"
            properties = {"name": entity_name, "chunk id": chunk_id}
            if entity_type:
                properties["schema_type"] = entity_type
                
            self.graph.add_node(
                entity_node_id, 
                label="entity", 
                properties=properties, 
                level=2
            )
            self.node_counter += 1
            
        return entity_node_id
    
    def _process_attributes_agent(self, extracted_attr: dict, chunk_id: int, entity_types: dict = None):
        """Process extracted attributes in agent mode (direct graph operations)."""
        for entity, attributes in extracted_attr.items():
            for attr in attributes:
                # Create attribute node
                attr_node_id = f"attr_{self.node_counter}"
                self.graph.add_node(
                    attr_node_id,
                    label="attribute",
                    properties={
                        "name": attr,
                        "chunk id": chunk_id
                    },
                    level=1,
                )
                self.node_counter += 1

                entity_type = entity_types.get(entity) if entity_types else None
                entity_node_id = self._find_or_create_entity_direct(entity, chunk_id, entity_type)
                self.graph.add_edge(entity_node_id, attr_node_id, relation="has_attribute")
    
    def _process_triples_agent(self, extracted_triples: list, chunk_id: int, entity_types: dict = None):
        """Process extracted triples in agent mode (direct graph operations)."""
        for triple in extracted_triples:
            validated_triple = self._validate_triple_format(triple)
            if not validated_triple:
                continue
                
            subj, pred, obj = validated_triple
            
            subj_type = entity_types.get(subj) if entity_types else None
            obj_type = entity_types.get(obj) if entity_types else None
            
            # Find or create subject and object entities
            subj_node_id = self._find_or_create_entity_direct(subj, chunk_id, subj_type)
            obj_node_id = self._find_or_create_entity_direct(obj, chunk_id, obj_type)
            
            #self.graph.add_edge(subj_node_id, obj_node_id, relation=pred)
            edge_data = {"relation": pred}
            if chunk_id:
                edge_data["source_chunks"] = [chunk_id]
            self.graph.add_edge(subj_node_id, obj_node_id, **edge_data)
    

    def process_level1_level2_agent(self, chunk: str, id: int):
        """Process attributes (level 1) and triples (level 2) with agent mechanism for schema evolution.
        
        This method enables dynamic schema evolution by allowing the LLM to suggest new entity types,
        relation types, and attribute types that can be added to the existing schema.
        """
        prompt = self._get_construction_prompt(chunk)
        llm_response = self.extract_with_llm(prompt)
        
        # Validate and parse response (reuse helper method)
        parsed_response = self._validate_and_parse_llm_response(prompt, llm_response)
        if not parsed_response:
            return

        # Handle schema evolution
        new_schema_types = parsed_response.get("new_schema_types", {})
        if new_schema_types:
            self._update_schema_with_new_types(new_schema_types)
        
        extracted_attr = parsed_response.get("attributes", {})
        extracted_triples = parsed_response.get("triples", [])
        entity_types = parsed_response.get("entity_types", {})
        
        with self.lock:
            self._process_attributes_agent(extracted_attr, id, entity_types)
            self._process_triples_agent(extracted_triples, id, entity_types)

    def _update_schema_with_new_types(self, new_schema_types: Dict[str, List[str]]):
        """Update the schema file with new types discovered by the agent.
        
        This method processes schema evolution suggestions from the LLM and updates
        the corresponding schema file with new node types, relations, and attributes.
        Only adds types that don't already exist in the current schema.
        
        Args:
            new_schema_types: Dictionary containing 'nodes', 'relations', and 'attributes' lists
        """
        try:
            schema_paths = {
                "hotpot": "schemas/hotpot.json",
                "2wiki": "schemas/2wiki.json", 
                "musique": "schemas/musique.json",
                "novel": "schemas/novels_chs.json",
                "graphrag-bench": "schemas/graphrag-bench.json"
            }
            
            schema_path = schema_paths.get(self.dataset_name)
            if not schema_path:
                return
                
            with open(schema_path, 'r', encoding='utf-8') as f:
                current_schema = json.load(f)
            
            updated = False
            
            if "nodes" in new_schema_types:
                for new_node in new_schema_types["nodes"]:
                    if new_node not in current_schema.get("Nodes", []):
                        current_schema.setdefault("Nodes", []).append(new_node)
                        updated = True
            
            if "relations" in new_schema_types:
                for new_relation in new_schema_types["relations"]:
                    if new_relation not in current_schema.get("Relations", []):
                        current_schema.setdefault("Relations", []).append(new_relation)
                        updated = True

            if "attributes" in new_schema_types:
                for new_attribute in new_schema_types["attributes"]:
                    if new_attribute not in current_schema.get("Attributes", []):
                        current_schema.setdefault("Attributes", []).append(new_attribute)
                        updated = True
            
            # Save updated schema back to file
            if updated:
                with open(schema_path, 'w', encoding='utf-8') as f:
                    json.dump(current_schema, f, ensure_ascii=False, indent=2)
                
                # Update the in-memory schema
                self.schema = current_schema
                
        except Exception as e:
            logger.error(f"Failed to update schema for dataset '{self.dataset_name}': {type(e).__name__}: {e}")

    def process_level4(self, method = "semantic"):
        """Process communities using Tree-Comm algorithm"""
        level2_nodes = [n for n, d in self.graph.nodes(data=True) if d['level'] == 2]
        start_comm = time.time()
        _tree_comm = tree_comm.FastTreeComm(
            self.graph, 
            embedding_model=self.config.tree_comm.embedding_model,
            struct_weight=self.config.tree_comm.struct_weight,
        )
        comm_to_nodes = _tree_comm.detect_communities(level2_nodes)
        if method == 'semantic':
            _, keyword_mapping = _tree_comm.create_super_nodes_with_keywords(comm_to_nodes, level=4)
            if keyword_mapping:
                try:
                    self._deduplicate_keyword_nodes(keyword_mapping)
                except Exception as keyword_error:
                    logger.warning(
                        "Keyword semantic deduplication failed: %s: %s",
                        type(keyword_error).__name__,
                        keyword_error,
                    )
        else:                    
            # create super nodes (level 4 communities)
            _tree_comm.create_super_nodes_with_keywords(comm_to_nodes, level=4)
            # _tree_comm.add_keywords_to_level3(comm_to_nodes)
            # connect keywords to communities (optional)
            # self._connect_keywords_to_communities()
        end_comm = time.time()
        logger.info(f"Community Indexing Time: {end_comm - start_comm}s")
    
    def _connect_keywords_to_communities(self):
        """Connect relevant keywords to communities"""
        # comm_names = [self.graph.nodes[n]['properties']['name'] for n, d in self.graph.nodes(data=True) if d['level'] == 4]
        comm_nodes = [n for n, d in self.graph.nodes(data=True) if d['level'] == 4]
        kw_nodes = [n for n, d in self.graph.nodes(data=True) if d['label'] == 'keyword']
        with self.lock:
            for comm in comm_nodes:
                comm_name = self.graph.nodes[comm]['properties']['name'].lower()
                for kw in kw_nodes:
                    kw_name = self.graph.nodes[kw]['properties']['name'].lower()
                    if kw_name in comm_name or comm_name in kw_name:
                        self.graph.add_edge(kw, comm, relation="describes")

    def process_document(self, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process a single document and return its results."""
        try:
            if not doc:
                raise ValueError("Document is empty or None")
            
            chunks, chunk2id = self.chunk_text(doc)
            
            if not chunks or not chunk2id:
                raise ValueError(f"No valid chunks generated from document. Chunks: {len(chunks)}, Chunk2ID: {len(chunk2id)}")
            
            for chunk in chunks:
                try:
                    id = next(key for key, value in chunk2id.items() if value == chunk)
                except StopIteration:
                    id = nanoid.generate(size=8)
                    chunk2id[id] = chunk
                
                # Route to appropriate processing method based on mode
                if self.mode == "agent":
                    # Agent mode: includes schema evolution capabilities
                    self.process_level1_level2_agent(chunk, id)
                else:
                    # NoAgent mode: standard processing without schema evolution
                    self.process_level1_level2(chunk, id)
                
        except Exception as e:
            error_msg = f"Error processing document: {type(e).__name__}: {str(e)}"
            raise Exception(error_msg) from e

    def process_all_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Process all documents with high concurrency and pass results to process_level4."""

        max_workers = min(self.config.construction.max_workers, (os.cpu_count() or 1) + 4)
        start_construct = time.time()
        total_docs = len(documents)
        
        logger.info(f"Starting processing {total_docs} documents with {max_workers} workers...")

        all_futures = []
        processed_count = 0
        failed_count = 0
        
        try:
            with futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all documents for processing and store futures
                all_futures = [executor.submit(self.process_document, doc) for doc in documents]

                for i, future in enumerate(futures.as_completed(all_futures)):
                    try:
                        future.result()
                        processed_count += 1
                        
                        if processed_count % 10 == 0 or processed_count == total_docs:
                            elapsed_time = time.time() - start_construct
                            avg_time_per_doc = elapsed_time / processed_count if processed_count > 0 else 0
                            remaining_docs = total_docs - processed_count
                            estimated_remaining_time = remaining_docs * avg_time_per_doc
                            
                            logger.info(f"Progress: {processed_count}/{total_docs} documents processed "
                                  f"({processed_count/total_docs*100:.1f}%) "
                                  f"[{failed_count} failed] "
                                  f"ETA: {estimated_remaining_time/60:.1f} minutes")
                        
                    except Exception as e:
                        failed_count += 1

        except Exception as e:
            return

        end_construct = time.time()
        logger.info(f"Construction Time: {end_construct - start_construct}s")
        logger.info(f"Successfully processed: {processed_count}/{total_docs} documents")
        logger.info(f"Failed: {failed_count} documents")
        
        logger.info(f"🚀🚀🚀🚀 {'Processing Level 3 and 4':^20} 🚀🚀🚀🚀")
        logger.info(f"{'➖' * 20}")
        self.triple_deduplicate()
        self.process_level4()

    def _semantic_dedup_enabled(self) -> bool:
        config = getattr(self.config.construction, "semantic_dedup", None)
        return bool(config and config.enabled)

    def _get_semantic_dedup_config(self):
        return getattr(self.config.construction, "semantic_dedup", None)

    def _get_semantic_dedup_embedder(self):
        config = self._get_semantic_dedup_config()
        if not config or not config.use_embeddings:
            return None

        if self._semantic_dedup_embedder is not None:
            return self._semantic_dedup_embedder

        model_name = getattr(config, "embedding_model", "") or getattr(self.config.embeddings, "model_name", "all-MiniLM-L6-v2")
        try:
            from sentence_transformers import SentenceTransformer

            self._semantic_dedup_embedder = SentenceTransformer(model_name)
        except Exception as e:
            logger.warning(
                "Failed to initialize semantic dedup embedder with model '%s': %s: %s",
                model_name,
                type(e).__name__,
                e,
            )
            self._semantic_dedup_embedder = None

        return self._semantic_dedup_embedder

    def _describe_node(self, node_id: str) -> str:
        node_data = self.graph.nodes.get(node_id, {})
        label = node_data.get("label", "node")
        properties = node_data.get("properties", {})

        if isinstance(properties, dict):
            name = properties.get("name") or properties.get("title")
            extras = []
            for key, value in properties.items():
                if key == "name" or value in (None, ""):
                    continue
                extras.append(f"{key}: {value}")

            extra_text = ", ".join(extras)
            if name and extra_text:
                return f"{name} ({extra_text}) [{label}]"
            if name:
                return f"{name} [{label}]"
            if extra_text:
                return f"{label} ({extra_text})"

        return f"{label}:{node_id}"

    def _describe_node_for_clustering(self, node_id: str) -> str:
        """Generate a simplified description for semantic clustering.
        
        This method excludes chunk_id and label information to focus on
        the semantic content of the node for better clustering results.
        """
        node_data = self.graph.nodes.get(node_id, {})
        properties = node_data.get("properties", {})

        if isinstance(properties, dict):
            name = properties.get("name") or properties.get("title")
            extras = []
            for key, value in properties.items():
                # Skip name, chunk_id, and empty values
                if key == "name" or key == "chunk id" or key == "chunk_id" or value in (None, ""):
                    continue
                extras.append(f"{key}: {value}")

            extra_text = ", ".join(extras)
            if name and extra_text:
                return f"{name} ({extra_text})"
            if name:
                return name
            if extra_text:
                return extra_text

        # Fallback to node name only
        return properties.get("name") or properties.get("title") or node_id

    def _collect_node_chunk_ids(self, node_id: str) -> list:
        node_data = self.graph.nodes.get(node_id, {})
        properties = node_data.get("properties", {}) if isinstance(node_data, dict) else {}
        chunk_id = None
        if isinstance(properties, dict):
            chunk_id = properties.get("chunk id") or properties.get("chunk_id")

        if not chunk_id:
            return []

        return [chunk_id] if isinstance(chunk_id, str) else list(chunk_id)

    def _extract_edge_chunk_ids(self, edge_data: dict | None) -> list:
        if not isinstance(edge_data, dict):
            return []

        chunk_ids = edge_data.get("source_chunks") or edge_data.get("source_chunk_ids")
        if not chunk_ids:
            return []

        if isinstance(chunk_ids, (list, tuple, set)):
            return [chunk for chunk in chunk_ids if isinstance(chunk, str) and chunk]

        if isinstance(chunk_ids, str):
            return [chunk_ids]

        return []

    def _summarize_contexts(self, chunk_ids: list, max_items: int = 2, max_chars: int = 200) -> list:
        summaries: list = []
        seen: set = set()

        for chunk_id in chunk_ids:
            if not chunk_id or chunk_id in seen:
                continue

            seen.add(chunk_id)
            chunk_text = self.all_chunks.get(chunk_id)
            if not chunk_text:
                summaries.append(f"- ({chunk_id}) [context not available]")
                if len(summaries) >= max_items:
                    break
                continue

            snippet = " ".join(str(chunk_text).split())
            if len(snippet) > max_chars:
                snippet = snippet[:max_chars].rstrip() + "…"

            summaries.append(f"- ({chunk_id}) {snippet}")
            if len(summaries) >= max_items:
                break

        if not summaries:
            summaries.append("- (no context available)")

        return summaries

    def _cluster_candidate_tails_with_llm(self, head_text: str, relation: str, descriptions: list, max_batch_size: int = 30) -> tuple:
        """
        Cluster candidate tails using LLM for initial grouping.
        
        This method uses LLM to perform semantic clustering based on tail descriptions only,
        without context. It's more accurate than embedding-based clustering for complex cases.
        
        Args:
            head_text: Description of the head entity
            relation: The relation name
            descriptions: List of tail descriptions to cluster
            max_batch_size: Maximum number of tails to send to LLM at once
            
        Returns:
            Tuple of (clusters, cluster_details):
                - clusters: List of clusters, where each cluster is a list of indices
                - cluster_details: List of dicts with LLM's clustering rationale
        """
        if len(descriptions) <= 1:
            single_cluster = [list(range(len(descriptions)))]
            single_details = [{
                "cluster_id": 0,
                "members": list(range(len(descriptions))),
                "description": "Single item, no clustering needed",
                "llm_rationale": ""
            }]
            return single_cluster, single_details
        
        # If there are too many tails, batch them
        all_clusters = []
        all_details = []
        
        if len(descriptions) > max_batch_size:
            # Process in batches
            for batch_start in range(0, len(descriptions), max_batch_size):
                batch_end = min(batch_start + max_batch_size, len(descriptions))
                batch_descriptions = descriptions[batch_start:batch_end]
                batch_offset = batch_start
                
                batch_clusters, batch_details = self._llm_cluster_batch(head_text, relation, batch_descriptions, batch_offset)
                all_clusters.extend(batch_clusters)
                all_details.extend(batch_details)
            return all_clusters, all_details
        else:
            # Process all at once
            return self._llm_cluster_batch(head_text, relation, descriptions, 0)
    
    def _llm_cluster_batch(self, head_text: str, relation: str, descriptions: list, index_offset: int = 0) -> tuple:
        """
        Use LLM to cluster a batch of tail descriptions.
        
        Args:
            head_text: Description of the head entity
            relation: The relation name
            descriptions: List of tail descriptions to cluster
            index_offset: Offset to add to indices (for batched processing)
            
        Returns:
            Tuple of (clusters, cluster_details):
                - clusters: List of clusters with adjusted indices
                - cluster_details: List of dicts with clustering rationale from LLM
        """
        # Build candidate list for prompt
        candidate_blocks = []
        for idx, description in enumerate(descriptions, start=1):
            candidate_blocks.append(f"[{idx}] {description}")
        
        candidates_text = "\n".join(candidate_blocks) if candidate_blocks else "[No candidates]"
        
        # Build prompt
        prompt = DEFAULT_LLM_CLUSTERING_PROMPT.format(
            head=head_text or "[UNKNOWN_HEAD]",
            relation=relation or "[UNKNOWN_RELATION]",
            candidates=candidates_text
        )
        
        # Call LLM (use clustering LLM client)
        try:
            response = self.clustering_llm_client.call_api(prompt)
        except Exception as e:
            logger.warning("LLM clustering call failed: %s: %s, falling back to single cluster", type(e).__name__, e)
            # Fallback: put all items in one cluster
            fallback_cluster = [[idx + index_offset for idx in range(len(descriptions))]]
            fallback_details = [{"description": "Fallback cluster (LLM call failed)", "members": fallback_cluster[0]}]
            return fallback_cluster, fallback_details
        
        # Parse response
        try:
            parsed = json_repair.loads(response)
        except Exception:
            try:
                parsed = json.loads(response)
            except Exception as parse_error:
                logger.warning("Failed to parse LLM clustering response: %s: %s, using fallback", type(parse_error).__name__, parse_error)
                fallback_cluster = [[idx + index_offset for idx in range(len(descriptions))]]
                fallback_details = [{"description": "Fallback cluster (parse failed)", "members": fallback_cluster[0]}]
                return fallback_cluster, fallback_details
        
        clusters_raw = parsed.get("clusters") if isinstance(parsed, dict) else None
        if not isinstance(clusters_raw, list):
            logger.warning("LLM clustering response missing 'clusters' field, using fallback")
            fallback_cluster = [[idx + index_offset for idx in range(len(descriptions))]]
            fallback_details = [{"description": "Fallback cluster (invalid response)", "members": fallback_cluster[0]}]
            return fallback_cluster, fallback_details
        
        # Convert LLM output to cluster format and preserve details
        clusters = []
        cluster_details = []
        assigned = set()
        
        for cluster_idx, cluster_info in enumerate(clusters_raw):
            if not isinstance(cluster_info, dict):
                continue
            
            members_raw = cluster_info.get("members")
            if not isinstance(members_raw, list):
                continue
            
            # Convert 1-based indices to 0-based and add offset
            cluster_members = []
            for member in members_raw:
                try:
                    member_idx = int(member) - 1  # Convert to 0-based
                except (TypeError, ValueError):
                    continue
                if 0 <= member_idx < len(descriptions):
                    adjusted_idx = member_idx + index_offset
                    cluster_members.append(adjusted_idx)
                    assigned.add(member_idx)
            
            if cluster_members:
                clusters.append(cluster_members)
                # Save the LLM's description/rationale for this cluster
                cluster_details.append({
                    "cluster_id": cluster_idx,
                    "members": cluster_members,
                    "description": cluster_info.get("description", "No description provided"),
                    "llm_rationale": cluster_info.get("description", "")
                })
        
        # Add unassigned items as singleton clusters
        for idx in range(len(descriptions)):
            if idx not in assigned:
                singleton_idx = idx + index_offset
                clusters.append([singleton_idx])
                cluster_details.append({
                    "cluster_id": len(clusters) - 1,
                    "members": [singleton_idx],
                    "description": "Singleton cluster (unassigned by LLM)",
                    "llm_rationale": ""
                })
        
        return clusters, cluster_details

    def _cluster_candidate_tails(self, descriptions: list, threshold: float) -> list:
        """
        Cluster candidate descriptions using Average Linkage hierarchical clustering.
        
        This uses sklearn's AgglomerativeClustering with average linkage to ensure
        that items are only clustered together if they have high average similarity
        to all members of the cluster, avoiding the chaining effect of single linkage.
        
        Args:
            descriptions: List of text descriptions to cluster
            threshold: Similarity threshold (cosine similarity, 0-1)
            
        Returns:
            List of clusters, where each cluster is a list of indices
        """
        if len(descriptions) <= 1:
            return [list(range(len(descriptions)))]

        embedder = self._get_semantic_dedup_embedder()
        if embedder is None:
            return [list(range(len(descriptions)))]

        try:
            embeddings = embedder.encode(descriptions, normalize_embeddings=True)
        except Exception as e:
            logger.warning("Failed to encode descriptions for semantic dedup: %s: %s", type(e).__name__, e)
            return [list(range(len(descriptions)))]

        try:
            from sklearn.cluster import AgglomerativeClustering
            
            # Convert embeddings to numpy array
            embeddings = np.asarray(embeddings, dtype=float)
            
            # Compute cosine similarity matrix (embeddings are already normalized)
            similarity_matrix = np.dot(embeddings, embeddings.T)
            
            # Convert similarity to distance: distance = 1 - similarity
            distance_matrix = 1 - similarity_matrix
            
            # Ensure distance matrix is symmetric and has zero diagonal
            distance_matrix = (distance_matrix + distance_matrix.T) / 2
            np.fill_diagonal(distance_matrix, 0)
            
            # Convert similarity threshold to distance threshold
            distance_threshold = 1 - threshold
            
            # Apply AgglomerativeClustering with average linkage
            clustering = AgglomerativeClustering(
                n_clusters=None,  # Don't specify number of clusters
                distance_threshold=distance_threshold,  # Use distance threshold instead
                linkage='average',  # Average linkage: mean distance between all pairs
                metric='precomputed'  # Use our precomputed distance matrix
            )
            
            labels = clustering.fit_predict(distance_matrix)
            
            # Convert cluster labels to list of index lists
            clusters_dict = {}
            for idx, label in enumerate(labels):
                if label not in clusters_dict:
                    clusters_dict[label] = []
                clusters_dict[label].append(idx)
            
            return list(clusters_dict.values())
            
        except ImportError:
            logger.warning("sklearn not available, falling back to simple single-linkage clustering")
            # Fallback to original implementation if sklearn is not available
            clusters: list = []
            for idx, vector in enumerate(embeddings):
                vector_arr = np.asarray(vector, dtype=float)
                assigned = False
                for cluster in clusters:
                    if any(float(np.dot(existing_vec, vector_arr)) >= threshold for existing_vec in cluster["vectors"]):
                        cluster["members"].append(idx)
                        cluster["vectors"].append(vector_arr)
                        assigned = True
                        break

                if not assigned:
                    clusters.append({"members": [idx], "vectors": [vector_arr]})

            return [cluster["members"] for cluster in clusters]
        except Exception as e:
            logger.warning("Clustering failed: %s: %s, using fallback", type(e).__name__, e)
            # If anything goes wrong, put all items in one cluster
            return [list(range(len(descriptions)))]

    def _build_semantic_dedup_prompt(
        self,
        head_text: str,
        relation: str,
        head_context_lines: list,
        batch_entries: list,
    ) -> str:
        candidate_blocks = []
        for idx, entry in enumerate(batch_entries, start=1):
            description = entry.get("description") or "[NO DESCRIPTION]"
            context_lines = entry.get("context_summaries") or ["- (no context available)"]
            context_block = "\n        ".join(context_lines)
            candidate_blocks.append(
                f"[{idx}] Tail: {description}\n    Contexts:\n        {context_block}"
            )

        candidates_text = "\n".join(candidate_blocks) if candidate_blocks else "[No candidates]"
        relation_text = relation or "[UNKNOWN]"
        head_context_text = "\n".join(head_context_lines) if head_context_lines else "- (no context available)"

        # Auto-detect prompt type based on relation
        config = self._get_semantic_dedup_config()
        prompt_type = getattr(config, "prompt_type", "general")
        
        # Use 'attribute' prompt for attribute-related relations
        if prompt_type == "general":
            attribute_relations = {"has_attribute", "attribute", "property", "has_property", "characteristic"}
            relation_lower = relation.lower() if relation else ""
            if relation_lower in attribute_relations or "attribute" in relation_lower:
                prompt_type = "attribute"
                logger.debug(f"Auto-selected 'attribute' prompt type for relation: {relation}")
        
        prompt_kwargs = {
            "head": head_text or "[UNKNOWN_HEAD]",
            "relation": relation_text,
            "head_context": head_context_text,
            "candidates": candidates_text,
        }

        try:
            return self.config.get_prompt_formatted("semantic_dedup", prompt_type, **prompt_kwargs)
        except Exception:
            # Fallback to appropriate default prompt based on type
            if prompt_type == "attribute":
                return DEFAULT_ATTRIBUTE_DEDUP_PROMPT.format(**prompt_kwargs)
            else:
                return DEFAULT_SEMANTIC_DEDUP_PROMPT.format(**prompt_kwargs)

    def _llm_semantic_group(
        self,
        head_text: str,
        relation: str,
        head_context_lines: list,
        batch_entries: list,
    ) -> list:
        prompt = self._build_semantic_dedup_prompt(head_text, relation, head_context_lines, batch_entries)

        try:
            # Use deduplication LLM client for semantic grouping
            response = self.dedup_llm_client.call_api(prompt)
        except Exception as e:
            logger.warning("Semantic dedup LLM call failed: %s: %s", type(e).__name__, e)
            return []

        try:
            parsed = json_repair.loads(response)
        except Exception:
            try:
                parsed = json.loads(response)
            except Exception as parse_error:
                logger.warning("Failed to parse semantic dedup LLM response: %s: %s", type(parse_error).__name__, parse_error)
                return []

        groups_raw = parsed.get("groups") if isinstance(parsed, dict) else None
        if not isinstance(groups_raw, list):
            return []

        groups: list = []
        assigned = set()
        for group in groups_raw:
            if not isinstance(group, dict):
                continue

            members_raw = group.get("members")
            if not isinstance(members_raw, list):
                continue

            normalized_members = []
            for member in members_raw:
                try:
                    member_idx = int(member) - 1
                except (TypeError, ValueError):
                    continue
                if 0 <= member_idx < len(batch_entries):
                    normalized_members.append(member_idx)

            if not normalized_members:
                continue

            rep_raw = group.get("representative")
            try:
                rep_idx = int(rep_raw) - 1 if rep_raw is not None else None
            except (TypeError, ValueError):
                rep_idx = None

            if rep_idx is None or rep_idx not in normalized_members:
                rep_idx = normalized_members[0]

            rationale = group.get("rationale")
            groups.append(
                {
                    "representative": rep_idx,
                    "members": normalized_members,
                    "rationale": rationale,
                }
            )
            assigned.update(normalized_members)

        for idx in range(len(batch_entries)):
            if idx not in assigned:
                groups.append({"representative": idx, "members": [idx], "rationale": None})

        return groups

    def _concurrent_llm_calls(self, prompts_with_metadata: list) -> list:
        """
        Concurrently process multiple LLM prompts.
        
        Args:
            prompts_with_metadata: List of dicts with keys:
                - 'type': 'clustering' or 'semantic'
                - 'prompt': the prompt string
                - 'metadata': additional metadata for processing results
                
        Returns:
            List of dicts with keys:
                - 'type': same as input
                - 'response': raw LLM response
                - 'metadata': same as input
                - 'error': error message if failed (None if successful)
        """
        if not prompts_with_metadata:
            return []
        
        results = []
        
        def _call_single_llm(item):
            """Call LLM for a single prompt."""
            prompt_type = item.get('type')
            prompt = item.get('prompt')
            metadata = item.get('metadata', {})
            
            result = {
                'type': prompt_type,
                'metadata': metadata,
                'response': None,
                'error': None
            }
            
            try:
                # Choose appropriate client based on type
                if prompt_type == 'clustering':
                    response = self.clustering_llm_client.call_api(prompt)
                elif prompt_type == 'semantic':
                    response = self.dedup_llm_client.call_api(prompt)
                else:
                    raise ValueError(f"Unknown prompt type: {prompt_type}")
                
                result['response'] = response
            except Exception as e:
                result['error'] = f"{type(e).__name__}: {e}"
                logger.warning("LLM call failed for type %s: %s", prompt_type, result['error'])
            
            return result
        
        # Use ThreadPoolExecutor for concurrent API calls with progress bar
        max_workers = min(10, len(prompts_with_metadata))  # Limit concurrent requests
        
        # Submit all tasks and collect futures
        with futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_item = {
                executor.submit(_call_single_llm, item): item 
                for item in prompts_with_metadata
            }
            
            # Collect results with progress bar
            results = []
            with tqdm(total=len(prompts_with_metadata), desc="Processing LLM calls", unit="call") as pbar:
                for future in futures.as_completed(future_to_item):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        # This shouldn't happen as exceptions are caught in _call_single_llm
                        logger.error(f"Unexpected error in concurrent call: {e}")
                        results.append({
                            'type': 'unknown',
                            'metadata': {},
                            'response': None,
                            'error': str(e)
                        })
                    pbar.update(1)
        
        return results

    def _merge_duplicate_metadata(self, base_entry: dict, duplicates: list, rationale: str = None):
        if isinstance(base_entry, dict):
            base_data = base_entry.get("data", {})
            representative_chunks = list(base_entry.get("context_chunk_ids") or [])
            representative_contexts = list(base_entry.get("context_summaries") or [])
        else:
            base_data = base_entry
            representative_chunks = []
            representative_contexts = []

        merged = copy.deepcopy(base_data)

        combined_chunks: list = []

        def _append_chunk(chunk_id: str):
            if chunk_id and chunk_id not in combined_chunks:
                combined_chunks.append(chunk_id)

        for chunk_id in representative_chunks:
            _append_chunk(chunk_id)

        for chunk_id in self._extract_edge_chunk_ids(merged):
            _append_chunk(chunk_id)

        for duplicate in duplicates or []:
            if not isinstance(duplicate, dict):
                continue

            for chunk_id in duplicate.get("context_chunk_ids", []) or []:
                _append_chunk(chunk_id)

            duplicate_data = duplicate.get("raw_data") or duplicate.get("data")
            for chunk_id in self._extract_edge_chunk_ids(duplicate_data):
                _append_chunk(chunk_id)

        if combined_chunks:
            merged["source_chunks"] = combined_chunks

        semantic_info = merged.get("semantic_dedup")

        if rationale or duplicates or representative_contexts or combined_chunks:
            if semantic_info is None:
                semantic_info = {}
                merged["semantic_dedup"] = semantic_info

            if combined_chunks:
                semantic_info.setdefault("representative_chunk_ids", combined_chunks)

            if representative_contexts:
                semantic_info.setdefault("representative_contexts", representative_contexts)
            elif combined_chunks:
                semantic_info.setdefault(
                    "representative_contexts",
                    self._summarize_contexts(combined_chunks),
                )

            if rationale:
                rationales = semantic_info.setdefault("rationales", [])
                rationales.append(rationale)

            if duplicates:
                duplicate_entries = semantic_info.setdefault("duplicates", [])
                for duplicate in duplicates:
                    if not isinstance(duplicate, dict):
                        continue

                    duplicate_chunk_ids = list(duplicate.get("context_chunk_ids") or [])
                    duplicate_contexts = duplicate.get("context_summaries")
                    if not duplicate_contexts and duplicate_chunk_ids:
                        duplicate_contexts = self._summarize_contexts(duplicate_chunk_ids)

                    duplicate_entries.append(
                        {
                            "tail_node": duplicate.get("node_id"),
                            "tail_description": duplicate.get("description"),
                            "edge_attributes": copy.deepcopy(duplicate.get("raw_data", duplicate.get("data", {}))),
                            "context_chunk_ids": duplicate_chunk_ids,
                            "context_summaries": copy.deepcopy(duplicate_contexts or []),
                        }
                    )

        return merged

    def _set_node_chunk_ids(self, properties: dict, chunk_ids: set):
        if not isinstance(properties, dict):
            return

        normalized = [chunk_id for chunk_id in sorted(chunk_ids) if chunk_id]

        if not normalized:
            properties.pop("chunk id", None)
            properties.pop("chunk_id", None)
            return

        if len(normalized) == 1:
            properties["chunk id"] = normalized[0]
        else:
            properties["chunk id"] = normalized

    def _edge_exists(self, source: str, target: str, data: dict) -> bool:
        relation = data.get("relation") if isinstance(data, dict) else None
        existing = self.graph.get_edge_data(source, target, default={})

        for edge_data in existing.values() if isinstance(existing, dict) else []:
            if not isinstance(edge_data, dict):
                continue
            if relation and edge_data.get("relation") != relation:
                continue
            return True

        return False

    def _reassign_keyword_edges(self, source_id: str, target_id: str):
        incoming_edges = list(self.graph.in_edges(source_id, keys=True, data=True))
        for origin, _, _, data in incoming_edges:
            if origin == target_id:
                continue
            data_copy = copy.deepcopy(data)
            if not self._edge_exists(origin, target_id, data_copy):
                self.graph.add_edge(origin, target_id, **data_copy)

        outgoing_edges = list(self.graph.out_edges(source_id, keys=True, data=True))
        for _, destination, _, data in outgoing_edges:
            if destination == target_id:
                continue
            data_copy = copy.deepcopy(data)
            if not self._edge_exists(target_id, destination, data_copy):
                self.graph.add_edge(target_id, destination, **data_copy)

    def _merge_keyword_nodes(
        self,
        representative_entry: dict,
        duplicates: list,
        rationale: str | None,
        keyword_mapping: dict | None,
    ) -> list:
        rep_id = representative_entry.get("node_id") if isinstance(representative_entry, dict) else None
        if not rep_id or rep_id not in self.graph or not duplicates:
            return []

        rep_node = self.graph.nodes.get(rep_id, {})
        rep_properties = rep_node.setdefault("properties", {}) if isinstance(rep_node, dict) else {}

        representative_chunks = set(self._collect_node_chunk_ids(rep_id))
        for chunk_id in representative_entry.get("chunk_ids", []) or []:
            if chunk_id:
                representative_chunks.add(chunk_id)

        metadata = rep_properties.setdefault("semantic_dedup", {})
        metadata.setdefault("node_type", "keyword")

        rep_source_name = representative_entry.get("source_entity_name")
        if rep_source_name and "representative_source_entity" not in metadata:
            metadata["representative_source_entity"] = rep_source_name
            metadata["representative_source_entity_id"] = representative_entry.get("source_entity_id")

        rep_contexts = representative_entry.get("context_summaries") or []
        if rep_contexts and "representative_contexts" not in metadata:
            metadata["representative_contexts"] = list(rep_contexts)

        removed_nodes: list = []
        duplicates_info = metadata.setdefault("duplicates", [])

        if rationale:
            metadata.setdefault("rationales", []).append(rationale)

        for duplicate in duplicates:
            if not isinstance(duplicate, dict):
                continue

            dup_id = duplicate.get("node_id")
            if not dup_id or dup_id == rep_id or dup_id not in self.graph:
                continue

            dup_node = self.graph.nodes.get(dup_id, {})
            dup_props = dup_node.get("properties", {}) if isinstance(dup_node, dict) else {}

            duplicate_chunks = set(self._collect_node_chunk_ids(dup_id))
            for chunk_id in duplicate.get("chunk_ids", []) or []:
                if chunk_id:
                    duplicate_chunks.add(chunk_id)

            representative_chunks.update(duplicate_chunks)

            duplicate_contexts = duplicate.get("context_summaries") or []
            if not duplicate_contexts and duplicate_chunks:
                duplicate_contexts = self._summarize_contexts(sorted(duplicate_chunks))

            duplicates_info.append(
                {
                    "node_id": dup_id,
                    "name": dup_props.get("name") or duplicate.get("raw_name") or duplicate.get("description"),
                    "chunk_ids": sorted(duplicate_chunks),
                    "contexts": list(duplicate_contexts),
                    "source_entity": duplicate.get("source_entity_name"),
                    "source_entity_id": duplicate.get("source_entity_id"),
                }
            )

            self._reassign_keyword_edges(dup_id, rep_id)
            self.graph.remove_node(dup_id)
            removed_nodes.append(dup_id)

            if keyword_mapping is not None:
                keyword_mapping.pop(dup_id, None)

        if keyword_mapping is not None and not keyword_mapping.get(rep_id):
            for duplicate in duplicates or []:
                source_candidate = duplicate.get("source_entity_id") if isinstance(duplicate, dict) else None
                if source_candidate:
                    keyword_mapping[rep_id] = source_candidate
                    break

        if representative_chunks:
            self._set_node_chunk_ids(rep_properties, representative_chunks)
            metadata["representative_chunk_ids"] = sorted(representative_chunks)

        return removed_nodes

    def _deduplicate_keyword_nodes(self, keyword_mapping: dict):
        """
        Deduplicate keyword nodes using batch concurrent LLM processing.
        
        This method uses a multi-phase approach similar to triple_deduplicate_semantic:
        1. Prepare all communities and collect metadata
        2. Batch collect and process all clustering prompts concurrently
        3. Batch collect and process all semantic dedup prompts concurrently
        4. Apply results and merge keyword nodes
        """
        if not keyword_mapping or not self._semantic_dedup_enabled():
            return

        config = self._get_semantic_dedup_config()
        if not config:
            return

        # Group keywords by community
        community_to_keywords: dict = defaultdict(list)
        for keyword_node_id in list(keyword_mapping.keys()):
            if keyword_node_id not in self.graph:
                continue
            for _, target, _, data in self.graph.out_edges(keyword_node_id, keys=True, data=True):
                if isinstance(data, dict) and data.get("relation") == "keyword_of":
                    community_to_keywords[target].append(keyword_node_id)

        if not community_to_keywords:
            return

        # Get config parameters
        # 打印待处理的关键词总数
        total_keywords = sum(len(kws) for kws in community_to_keywords.values())
        logger.info(f"开始关键词去重，共 {len(community_to_keywords)} 个社区，总计 {total_keywords} 个关键词待处理")

        threshold = getattr(config, "embedding_threshold", 0.85) or 0.85
        max_batch_size = max(1, int(getattr(config, "max_batch_size", 8) or 8))
        max_candidates = int(getattr(config, "max_candidates", 0) or 0)
        clustering_method = getattr(config, "clustering_method", "embedding")
        llm_clustering_batch_size = getattr(config, "llm_clustering_batch_size", 30)
        save_intermediate = getattr(config, "save_intermediate_results", False)
        
        # Initialize intermediate results collector
        intermediate_results = {
            "dataset": self.dataset_name,
            "config": {
                "threshold": threshold,
                "max_batch_size": max_batch_size,
                "max_candidates": max_candidates,
                "clustering_method": clustering_method,
            },
            "communities": []
        } if save_intermediate else None

        # ================================================================
        # PHASE 1: Prepare all communities and collect metadata
        # ================================================================
        dedup_communities = []  # List of dicts with all info needed for deduplication
        
        for community_id, keyword_ids in community_to_keywords.items():
            keyword_ids = [kw for kw in keyword_ids if kw in self.graph]
            if len(keyword_ids) <= 1:
                continue

            # Prepare community data
            community_data = self._prepare_keyword_dedup_community(
                community_id, keyword_ids, keyword_mapping, config
            )
            if community_data:
                dedup_communities.append(community_data)
        
        logger.info(f"Prepared {len(dedup_communities)} communities for keyword deduplication")
        
        if not dedup_communities:
            return
        
        # ================================================================
        # PHASE 2: Batch collect and process clustering prompts
        # ================================================================
        clustering_prompts = []
        
        if clustering_method == "llm":
            logger.info("Collecting all keyword clustering prompts...")
            for comm_idx, community_data in enumerate(dedup_communities):
                prompts = self._collect_clustering_prompts(community_data)
                for prompt_data in prompts:
                    prompt_data['metadata']['comm_idx'] = comm_idx
                    clustering_prompts.append(prompt_data)
            
            logger.info(f"Collected {len(clustering_prompts)} keyword clustering prompts, processing concurrently...")
            clustering_results = self._concurrent_llm_calls(clustering_prompts)
            
            # Parse clustering results and update community_data
            logger.info("Parsing keyword clustering results...")
            self._parse_keyword_clustering_results(dedup_communities, clustering_results)
        else:
            # Use embedding-based clustering
            logger.info("Using embedding-based clustering for keywords...")
            for community_data in dedup_communities:
                self._apply_embedding_clustering(community_data)
        
        # ================================================================
        # PHASE 3: Batch collect and process semantic dedup prompts
        # ================================================================
        logger.info("Collecting all keyword semantic dedup prompts...")
        semantic_prompts = []
        
        for comm_idx, community_data in enumerate(dedup_communities):
            prompts = self._collect_semantic_dedup_prompts(community_data)
            for prompt_data in prompts:
                prompt_data['metadata']['comm_idx'] = comm_idx
                semantic_prompts.append(prompt_data)
        
        logger.info(f"Collected {len(semantic_prompts)} keyword semantic dedup prompts, processing concurrently...")
        semantic_results = self._concurrent_llm_calls(semantic_prompts)
        
        # Parse semantic dedup results and update community_data
        logger.info("Parsing keyword semantic dedup results...")
        self._parse_semantic_dedup_results(dedup_communities, semantic_results)
        
        # ================================================================
        # PHASE 4: Apply results and merge keyword nodes
        # ================================================================
        logger.info("Applying keyword deduplication results...")
        for community_data in dedup_communities:
            self._apply_keyword_dedup_results(community_data, keyword_mapping, save_intermediate, intermediate_results)
        
        logger.info("Keyword deduplication completed")
        
        # Save intermediate results to file
        if save_intermediate and intermediate_results:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = getattr(config, "intermediate_results_path", None)
            
            if not output_path:
                output_path = f"output/dedup_intermediate/{self.dataset_name}_keyword_dedup_{timestamp}.json"
            else:
                # If path is a directory, add filename
                if output_path.endswith('/'):
                    output_path = f"{output_path}{self.dataset_name}_keyword_dedup_{timestamp}.json"
                else:
                    # Add _keyword suffix
                    base, ext = os.path.splitext(output_path)
                    output_path = f"{base}_keyword_{timestamp}{ext}"
            
            # Ensure directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # Add summary statistics
            intermediate_results["summary"] = {
                "total_communities": len(intermediate_results["communities"]),
                "total_candidates": sum(c["total_candidates"] for c in intermediate_results["communities"]),
                "total_clusters": sum(len(c["clustering"]["clusters"]) for c in intermediate_results["communities"]),
                "total_llm_calls": sum(len(c["llm_groups"]) for c in intermediate_results["communities"]),
                "total_merges": sum(len(c["final_merges"]) for c in intermediate_results["communities"]),
                "total_items_merged": sum(c["summary"]["items_merged"] for c in intermediate_results["communities"])
            }
            
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(intermediate_results, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved keyword deduplication intermediate results to: {output_path}")
                logger.info(f"Summary: {intermediate_results['summary']}")
            except Exception as e:
                logger.warning(f"Failed to save intermediate results: {e}")

    def _prepare_keyword_dedup_community(self, community_id: str, keyword_ids: list, 
                                         keyword_mapping: dict, config) -> dict:
        """
        Prepare metadata for a keyword deduplication community.
        
        Returns:
            dict with keys: community_id, entries, head_text, head_context_lines, 
                           candidate_descriptions, config_params, etc.
        """
        threshold = getattr(config, "embedding_threshold", 0.85) or 0.85
        
        entries: list = []
        for kw_id in keyword_ids:
            node_data = self.graph.nodes.get(kw_id, {})
            properties = node_data.get("properties", {}) if isinstance(node_data, dict) else {}
            raw_name = properties.get("name") or properties.get("title") or kw_id

            chunk_ids = set(self._collect_node_chunk_ids(kw_id))
            source_entity_id = keyword_mapping.get(kw_id)
            source_entity_name_full = None
            source_entity_name_simple = None

            if source_entity_id and source_entity_id in self.graph:
                source_entity_name_full = self._describe_node(source_entity_id)  # Full for LLM
                source_entity_name_simple = self._describe_node_for_clustering(source_entity_id)  # Simple for clustering
                for chunk_id in self._collect_node_chunk_ids(source_entity_id):
                    if chunk_id:
                        chunk_ids.add(chunk_id)

            # Full description for LLM prompt
            description_full = raw_name
            if source_entity_name_full and source_entity_name_full not in description_full:
                description_full = f"{raw_name} (from {source_entity_name_full})"
            
            # Simplified description for vector clustering
            description_simple = raw_name
            if source_entity_name_simple and source_entity_name_simple not in description_simple:
                description_simple = f"{raw_name} (from {source_entity_name_simple})"

            context_summaries = self._summarize_contexts(list(chunk_ids))

            entries.append({
                "node_id": kw_id,
                "description": description_full,  # Full for LLM
                "description_for_clustering": description_simple,  # Simple for clustering
                "raw_name": raw_name,
                "chunk_ids": list(chunk_ids),
                "context_summaries": context_summaries,
                "source_entity_id": source_entity_id,
                "source_entity_name": source_entity_name_full,
            })

        if len(entries) <= 1:
            return None

        # Add index to each entry
        for idx, entry in enumerate(entries):
            entry["index"] = idx

        # Collect community context
        community_chunk_ids = set()
        for entry in entries:
            for chunk_id in entry.get("chunk_ids", []):
                if chunk_id:
                    community_chunk_ids.add(chunk_id)

        head_context_lines = self._summarize_contexts(list(community_chunk_ids))
        head_text = self._describe_node(community_id)
        candidate_descriptions = [entry["description_for_clustering"] for entry in entries]
        
        # Extract config parameters
        config_params = {
            'clustering_method': getattr(config, "clustering_method", "embedding"),
            'threshold': getattr(config, "embedding_threshold", 0.85) or 0.85,
            'llm_clustering_batch_size': getattr(config, "llm_clustering_batch_size", 30),
            'max_batch_size': max(1, int(getattr(config, "max_batch_size", 8) or 8)),
            'max_candidates': int(getattr(config, "max_candidates", 0) or 0),
        }

        return {
            'community_id': community_id,
            'head_text': head_text,
            'relation': 'keyword_of',
            'entries': entries,
            'head_context_lines': head_context_lines,
            'candidate_descriptions': candidate_descriptions,
            'config_params': config_params,
            'initial_clusters': None,  # Will be filled by clustering
            'llm_clustering_details': None,  # Will be filled by LLM clustering
            'semantic_results': {},  # Will be filled by semantic dedup
        }
    
    def _parse_keyword_clustering_results(self, dedup_communities: list, clustering_results: list):
        """
        Parse keyword clustering results and update dedup_communities.
        Similar to _parse_clustering_results but uses comm_idx instead of group_idx.
        """
        # Group results by comm_idx
        results_by_comm = defaultdict(list)
        for result in clustering_results:
            comm_idx = result['metadata'].get('comm_idx')
            if comm_idx is not None:
                results_by_comm[comm_idx].append(result)
        
        # Parse results for each community
        for comm_idx, results in results_by_comm.items():
            if comm_idx >= len(dedup_communities):
                continue
            
            community_data = dedup_communities[comm_idx]
            all_clusters = []
            all_details = []
            
            for result in results:
                metadata = result['metadata']
                batch_offset = metadata['batch_offset']
                batch_descriptions = metadata['descriptions']
                
                if result['error']:
                    # Fallback: single cluster
                    fallback_cluster = [idx + batch_offset for idx in range(len(batch_descriptions))]
                    all_clusters.append(fallback_cluster)
                    all_details.append({
                        "description": f"Fallback cluster (error: {result['error']})",
                        "members": fallback_cluster
                    })
                    continue
                
                # Parse clustering response
                try:
                    parsed = json_repair.loads(result['response'])
                except Exception:
                    try:
                        parsed = json.loads(result['response'])
                    except Exception:
                        # Fallback
                        fallback_cluster = [idx + batch_offset for idx in range(len(batch_descriptions))]
                        all_clusters.append(fallback_cluster)
                        all_details.append({
                            "description": "Fallback cluster (parse failed)",
                            "members": fallback_cluster
                        })
                        continue
                
                clusters_raw = parsed.get("clusters") if isinstance(parsed, dict) else None
                if not isinstance(clusters_raw, list):
                    fallback_cluster = [idx + batch_offset for idx in range(len(batch_descriptions))]
                    all_clusters.append(fallback_cluster)
                    all_details.append({
                        "description": "Fallback cluster (invalid response)",
                        "members": fallback_cluster
                    })
                    continue
                
                # Process clusters
                assigned = set()
                for cluster_info in clusters_raw:
                    if not isinstance(cluster_info, dict):
                        continue
                    
                    members_raw = cluster_info.get("members")
                    if not isinstance(members_raw, list):
                        continue
                    
                    cluster_members = []
                    for member in members_raw:
                        try:
                            member_idx = int(member) - 1  # 1-based to 0-based
                        except (TypeError, ValueError):
                            continue
                        if 0 <= member_idx < len(batch_descriptions):
                            adjusted_idx = member_idx + batch_offset
                            cluster_members.append(adjusted_idx)
                            assigned.add(member_idx)
                    
                    if cluster_members:
                        all_clusters.append(cluster_members)
                        all_details.append({
                            "description": cluster_info.get("description", ""),
                            "llm_rationale": cluster_info.get("rationale", ""),
                            "members": cluster_members
                        })
                
                # Add unassigned as singletons
                for idx in range(len(batch_descriptions)):
                    if idx not in assigned:
                        adjusted_idx = idx + batch_offset
                        all_clusters.append([adjusted_idx])
                        all_details.append({
                            "description": f"Singleton cluster for item {adjusted_idx}",
                            "members": [adjusted_idx]
                        })
            
            community_data['initial_clusters'] = all_clusters
            community_data['llm_clustering_details'] = all_details
    
    def _apply_keyword_dedup_results(self, community_data: dict, keyword_mapping: dict,
                                     save_intermediate: bool, intermediate_results: dict):
        """
        Apply deduplication results for a community and merge keyword nodes.
        """
        entries = community_data['entries']
        initial_clusters = community_data.get('initial_clusters', [])
        semantic_results = community_data.get('semantic_results', {})
        community_id = community_data['community_id']
        head_text = community_data['head_text']
        
        processed_indices = set()
        duplicate_indices = set()
        
        # Initialize community result for intermediate results
        community_result = None
        if save_intermediate:
            # 打印当前社区待处理的关键词数量
            logger.info(f"处理社区 {community_id}，包含 {len(keyword_ids)} 个关键词")

            # Initialize community result collector
            community_result = {
                "community_id": community_id,
                "community_name": head_text,
                "relation": "keyword_of",
                "total_candidates": len(entries),
                "candidates": [
                    {
                        "index": e["index"],
                        "node_id": e["node_id"],
                        "description": e["description"],
                        "raw_name": e["raw_name"],
                        "source_entity_id": e.get("source_entity_id"),
                        "source_entity_name": e.get("source_entity_name")
                    }
                    for e in entries
                ],
                "head_contexts": community_data['head_context_lines'],
                "clustering": {
                    "method": community_data['config_params']['clustering_method'],
                    "threshold": community_data['config_params']['threshold'],
                    "clusters": []
                },
                "llm_groups": [],
                "final_merges": []
            }
            
            # Save clustering info
            for cluster_idx, cluster in enumerate(initial_clusters):
                cluster_info = {
                    "cluster_id": cluster_idx,
                    "size": len(cluster),
                    "member_indices": cluster,
                    "members": [
                        {
                            "index": idx,
                            "node_id": entries[idx]["node_id"],
                            "description": entries[idx]["description"]
                        }
                        for idx in cluster if 0 <= idx < len(entries)
                    ]
                }
                llm_clustering_details = community_data.get('llm_clustering_details')
                if llm_clustering_details and cluster_idx < len(llm_clustering_details):
                    detail = llm_clustering_details[cluster_idx]
                    cluster_info["llm_description"] = detail.get("description", "")
                    cluster_info["llm_rationale"] = detail.get("llm_rationale", "")
                community_result["clustering"]["clusters"].append(cluster_info)
        
        # Process each cluster
        for cluster_idx, cluster in enumerate(initial_clusters):
            cluster_indices = [idx for idx in cluster if idx not in processed_indices and idx not in duplicate_indices]
            if not cluster_indices:
                continue
            
            # Single-item clusters - no dedup needed
            if len(cluster_indices) == 1:
                processed_indices.add(cluster_indices[0])
                continue
            
            # Process semantic dedup results for this cluster
            batch_num = 0
            while True:
                key = (cluster_idx, batch_num)
                if key not in semantic_results:
                    break
                
                result = semantic_results[key]
                groups = result['groups']
                batch_indices = result['batch_indices']
                overflow_indices = result.get('overflow_indices', [])
                
                # Save LLM groups
                if save_intermediate:
                    llm_result = {
                        "cluster_id": cluster_idx,
                        "batch_indices": batch_indices,
                        "batch_size": len(batch_indices),
                        "groups": []
                    }
                    for group in groups:
                        group_info = {
                            "members": group.get("members", []),
                            "representative": group.get("representative"),
                            "rationale": group.get("rationale"),
                            "member_details": [
                                {
                                    "local_idx": m,
                                    "global_idx": batch_indices[m] if 0 <= m < len(batch_indices) else None,
                                    "description": entries[batch_indices[m]]["description"] if 0 <= m < len(batch_indices) else None
                                }
                                for m in group.get("members", [])
                                if 0 <= m < len(batch_indices)
                            ]
                        }
                        llm_result["groups"].append(group_info)
                    community_result["llm_groups"].append(llm_result)
                
                # Process groups
                if not groups:
                    # No grouping - keep all separate
                    for global_idx in batch_indices:
                        if global_idx not in processed_indices:
                            processed_indices.add(global_idx)
                else:
                    for group in groups:
                        rep_local = group.get("representative")
                        if rep_local is None or rep_local < 0 or rep_local >= len(batch_indices):
                            continue
                        
                        rep_global = batch_indices[rep_local]
                        if rep_global in processed_indices:
                            continue
                        
                        # Collect duplicates
                        duplicates = []
                        for member_local in group.get("members", []):
                            if member_local < 0 or member_local >= len(batch_indices):
                                continue
                            member_global = batch_indices[member_local]
                            if member_global == rep_global or member_global in processed_indices:
                                continue
                            duplicates.append(entries[member_global])
                            duplicate_indices.add(member_global)
                        
                        # Save merge info
                        if save_intermediate and duplicates:
                            merge_info = {
                                "representative": {
                                    "index": rep_global,
                                    "node_id": entries[rep_global]["node_id"],
                                    "description": entries[rep_global]["description"]
                                },
                                "duplicates": [
                                    {
                                        "index": d.get("index"),
                                        "node_id": d["node_id"],
                                        "description": d["description"]
                                    }
                                    for d in duplicates
                                ],
                                "rationale": group.get("rationale")
                            }
                            community_result["final_merges"].append(merge_info)
                        
                        # Merge keyword nodes
                        if duplicates:
                            self._merge_keyword_nodes(
                                entries[rep_global],
                                duplicates,
                                group.get("rationale"),
                                keyword_mapping,
                            )
                        
                        processed_indices.add(rep_global)
                        for duplicate_entry in duplicates:
                            duplicate_idx = duplicate_entry.get("index")
                            if duplicate_idx is not None:
                                processed_indices.add(duplicate_idx)
                
                # Handle overflow
                if batch_num == 0:
                    for global_idx in overflow_indices:
                        if global_idx not in processed_indices:
                            processed_indices.add(global_idx)
                
                batch_num += 1
        
        # Save results
        if save_intermediate and community_result:
            community_result["summary"] = {
                "total_candidates": len(entries),
                "total_clusters": len(initial_clusters),
                "single_item_clusters": sum(1 for c in initial_clusters if len(c) == 1),
                "multi_item_clusters": sum(1 for c in initial_clusters if len(c) > 1),
                "total_llm_calls": len(community_result["llm_groups"]),
                "total_merges": len(community_result["final_merges"]),
                "items_merged": sum(len(m["duplicates"]) for m in community_result["final_merges"])
            }
            intermediate_results["communities"].append(community_result)

    def _deduplicate_exact(self, edges: list) -> list:
        unique_edges: list = []
        index_by_key: dict = {}

        for tail_id, data in edges:
            data_copy = copy.deepcopy(data)

            if isinstance(data_copy, dict):
                chunk_ids = self._extract_edge_chunk_ids(data_copy)
                normalized_chunks: list = []
                seen_chunks: set = set()
                for chunk_id in chunk_ids:
                    if chunk_id and chunk_id not in seen_chunks:
                        normalized_chunks.append(chunk_id)
                        seen_chunks.add(chunk_id)

                # ensure chunk provenance stored in a consistent field
                if normalized_chunks:
                    data_copy["source_chunks"] = normalized_chunks
                if "source_chunk_ids" in data_copy:
                    data_copy.pop("source_chunk_ids", None)

                key_payload = copy.deepcopy(data_copy)
                key_payload.pop("source_chunks", None)
            else:
                chunk_ids = []
                key_payload = copy.deepcopy(data_copy)

            try:
                frozen = json.dumps(key_payload, ensure_ascii=False, sort_keys=True, default=str)
            except Exception:
                frozen = str(key_payload)

            key = (tail_id, frozen)
            if key in index_by_key:
                _, existing_data = unique_edges[index_by_key[key]]
                if isinstance(existing_data, dict):
                    existing_chunks = self._extract_edge_chunk_ids(existing_data)
                    combined = list(existing_chunks)
                    seen_chunks = set(existing_chunks)
                    for chunk_id in chunk_ids:
                        if chunk_id and chunk_id not in seen_chunks:
                            combined.append(chunk_id)
                            seen_chunks.add(chunk_id)
                    if combined:
                        existing_data["source_chunks"] = combined
                        existing_data.pop("source_chunk_ids", None)
                continue

            unique_edges.append((tail_id, data_copy))
            index_by_key[key] = len(unique_edges) - 1

        return unique_edges

    def _semantic_deduplicate_group(self, head_id: str, relation: str, edges: list) -> list:
        config = self._get_semantic_dedup_config()
        if not config or len(edges) <= 1:
            return edges

        head_text = self._describe_node(head_id)
        entries = []
        for idx, (tail_id, data) in enumerate(edges):
            chunk_ids = self._extract_edge_chunk_ids(data)
            if not chunk_ids:
                chunk_ids = self._collect_node_chunk_ids(tail_id)
            entries.append(
                {
                    "index": idx,
                    "node_id": tail_id,
                    "data": copy.deepcopy(data),
                    "raw_data": copy.deepcopy(data),
                    "description": self._describe_node(tail_id),  # Full description for LLM
                    "description_for_clustering": self._describe_node_for_clustering(tail_id),  # Simplified for clustering
                    "context_chunk_ids": chunk_ids,
                    "context_summaries": self._summarize_contexts(chunk_ids),
                }
            )

        head_chunk_ids = set()
        for entry in entries:
            for chunk_id in entry.get("context_chunk_ids", []):
                if chunk_id:
                    head_chunk_ids.add(chunk_id)

        if not head_chunk_ids:
            for chunk_id in self._collect_node_chunk_ids(head_id):
                if chunk_id:
                    head_chunk_ids.add(chunk_id)

        head_context_lines = self._summarize_contexts(list(head_chunk_ids))

        # Get configuration parameters
        clustering_method = getattr(config, "clustering_method", "embedding")
        threshold = getattr(config, "embedding_threshold", 0.85) or 0.85
        llm_clustering_batch_size = getattr(config, "llm_clustering_batch_size", 30)
        max_batch_size = max(1, int(getattr(config, "max_batch_size", 8) or 8))
        max_candidates = int(getattr(config, "max_candidates", 0) or 0)
        
        # Use simplified descriptions for clustering (without context, chunk_id, etc.)
        candidate_descriptions = [entry["description_for_clustering"] for entry in entries]
        
        # ============================================================
        # PHASE 1: Collect all prompts (clustering + semantic grouping)
        # ============================================================
        prompts_to_process = []
        
        # 1.1: Collect clustering prompts (if using LLM clustering)
        clustering_prompt_indices = []  # Track which prompts are for clustering
        initial_clusters = None
        llm_clustering_details = None
        
        if clustering_method == "llm":
            logger.debug("Collecting LLM clustering prompts for head '%s' relation '%s' with %d tails", 
                        head_text, relation, len(entries))
            
            # Build clustering prompts (may be batched)
            descriptions = candidate_descriptions
            if len(descriptions) > llm_clustering_batch_size:
                # Need multiple batches for clustering
                for batch_start in range(0, len(descriptions), llm_clustering_batch_size):
                    batch_end = min(batch_start + llm_clustering_batch_size, len(descriptions))
                    batch_descriptions = descriptions[batch_start:batch_end]
                    batch_offset = batch_start
                    
                    # Build clustering prompt
                    candidate_blocks = []
                    for idx, description in enumerate(batch_descriptions, start=1):
                        candidate_blocks.append(f"[{idx}] {description}")
                    candidates_text = "\n".join(candidate_blocks) if candidate_blocks else "[No candidates]"
                    
                    prompt = DEFAULT_LLM_CLUSTERING_PROMPT.format(
                        head=head_text or "[UNKNOWN_HEAD]",
                        relation=relation or "[UNKNOWN_RELATION]",
                        candidates=candidates_text
                    )
                    
                    clustering_prompt_idx = len(prompts_to_process)
                    clustering_prompt_indices.append(clustering_prompt_idx)
                    prompts_to_process.append({
                        'type': 'clustering',
                        'prompt': prompt,
                        'metadata': {
                            'batch_start': batch_start,
                            'batch_end': batch_end,
                            'batch_offset': batch_offset,
                            'descriptions': batch_descriptions
                        }
                    })
            else:
                # Single batch for clustering
                candidate_blocks = []
                for idx, description in enumerate(descriptions, start=1):
                    candidate_blocks.append(f"[{idx}] {description}")
                candidates_text = "\n".join(candidate_blocks) if candidate_blocks else "[No candidates]"
                
                prompt = DEFAULT_LLM_CLUSTERING_PROMPT.format(
                    head=head_text or "[UNKNOWN_HEAD]",
                    relation=relation or "[UNKNOWN_RELATION]",
                    candidates=candidates_text
                )
                
                clustering_prompt_idx = len(prompts_to_process)
                clustering_prompt_indices.append(clustering_prompt_idx)
                prompts_to_process.append({
                    'type': 'clustering',
                    'prompt': prompt,
                    'metadata': {
                        'batch_start': 0,
                        'batch_end': len(descriptions),
                        'batch_offset': 0,
                        'descriptions': descriptions
                    }
                })
        else:
            # Use embedding-based clustering (no prompts needed)
            initial_clusters = self._cluster_candidate_tails(candidate_descriptions, threshold)
        
        # 1.2: Collect semantic grouping prompts (prepare for each cluster batch)
        # We need to predict which batches will be processed for semantic grouping
        # For now, we'll collect prompts after getting clustering results
        # So this phase is split into two sub-phases
        
        # ============================================================
        # PHASE 2A: Process clustering prompts (if any)
        # ============================================================
        if clustering_method == "llm" and prompts_to_process:
            logger.debug("Processing %d clustering prompt(s) concurrently", len(prompts_to_process))
            clustering_results = self._concurrent_llm_calls(prompts_to_process)
            
            # Parse clustering results
            all_clusters = []
            all_details = []
            
            for result in clustering_results:
                if result['error']:
                    # Fallback for failed clustering
                    metadata = result['metadata']
                    batch_descriptions = metadata['descriptions']
                    batch_offset = metadata['batch_offset']
                    fallback_cluster = [[idx + batch_offset for idx in range(len(batch_descriptions))]]
                    fallback_details = [{"description": f"Fallback cluster (LLM call failed: {result['error']})", 
                                       "members": fallback_cluster[0]}]
                    all_clusters.extend(fallback_cluster)
                    all_details.extend(fallback_details)
                    continue
                
                # Parse clustering response
                response = result['response']
                metadata = result['metadata']
                batch_offset = metadata['batch_offset']
                batch_descriptions = metadata['descriptions']
                
                try:
                    parsed = json_repair.loads(response)
                except Exception:
                    try:
                        parsed = json.loads(response)
                    except Exception as parse_error:
                        logger.warning("Failed to parse LLM clustering response: %s: %s, using fallback", 
                                     type(parse_error).__name__, parse_error)
                        fallback_cluster = [[idx + batch_offset for idx in range(len(batch_descriptions))]]
                        fallback_details = [{"description": "Fallback cluster (parse failed)", 
                                           "members": fallback_cluster[0]}]
                        all_clusters.extend(fallback_cluster)
                        all_details.extend(fallback_details)
                        continue
                
                clusters_raw = parsed.get("clusters") if isinstance(parsed, dict) else None
                if not isinstance(clusters_raw, list):
                    logger.warning("LLM clustering response missing 'clusters' field, using fallback")
                    fallback_cluster = [[idx + batch_offset for idx in range(len(batch_descriptions))]]
                    fallback_details = [{"description": "Fallback cluster (invalid response)", 
                                       "members": fallback_cluster[0]}]
                    all_clusters.extend(fallback_cluster)
                    all_details.extend(fallback_details)
                    continue
                
                # Convert LLM output to cluster format
                assigned = set()
                for cluster_idx, cluster_info in enumerate(clusters_raw):
                    if not isinstance(cluster_info, dict):
                        continue
                    
                    members_raw = cluster_info.get("members")
                    if not isinstance(members_raw, list):
                        continue
                    
                    cluster_members = []
                    for member in members_raw:
                        try:
                            member_idx = int(member) - 1  # Convert to 0-based
                        except (TypeError, ValueError):
                            continue
                        if 0 <= member_idx < len(batch_descriptions):
                            adjusted_idx = member_idx + batch_offset
                            cluster_members.append(adjusted_idx)
                            assigned.add(member_idx)
                    
                    if cluster_members:
                        all_clusters.append(cluster_members)
                        detail = {
                            "description": cluster_info.get("description", ""),
                            "llm_rationale": cluster_info.get("rationale", ""),
                            "members": cluster_members
                        }
                        all_details.append(detail)
                
                # Add unassigned items as singleton clusters
                for idx in range(len(batch_descriptions)):
                    if idx not in assigned:
                        adjusted_idx = idx + batch_offset
                        all_clusters.append([adjusted_idx])
                        all_details.append({
                            "description": f"Singleton cluster for item {adjusted_idx}",
                            "members": [adjusted_idx]
                        })
            
            initial_clusters = all_clusters
            llm_clustering_details = all_details
        
        # ============================================================
        # PHASE 2B: Collect semantic grouping prompts based on clusters
        # ============================================================
        semantic_prompts = []
        semantic_prompt_metadata = []  # Store metadata for each semantic prompt
        
        for cluster_idx, cluster in enumerate(initial_clusters):
            cluster_indices = cluster.copy()
            
            # Skip single-item clusters (no grouping needed)
            if len(cluster_indices) <= 1:
                continue
            
            # Apply max_candidates limit
            overflow_indices = []
            if max_candidates and len(cluster_indices) > max_candidates:
                overflow_indices = cluster_indices[max_candidates:]
                cluster_indices = cluster_indices[:max_candidates]
            
            # Batch the cluster into semantic grouping batches
            while cluster_indices:
                batch_indices = cluster_indices[:max_batch_size]
                batch_entries = [entries[i] for i in batch_indices]
                
                # Build semantic grouping prompt
                prompt = self._build_semantic_dedup_prompt(head_text, relation, head_context_lines, batch_entries)
                
                semantic_prompts.append({
                    'type': 'semantic',
                    'prompt': prompt,
                    'metadata': {
                        'cluster_idx': cluster_idx,
                        'batch_indices': batch_indices,
                        'overflow_indices': overflow_indices,
                        'original_cluster': cluster
                    }
                })
                
                cluster_indices = cluster_indices[len(batch_indices):]
        
        # ============================================================
        # PHASE 3: Process all semantic grouping prompts concurrently
        # ============================================================
        semantic_results = []
        if semantic_prompts:
            logger.debug("Processing %d semantic grouping prompt(s) concurrently", len(semantic_prompts))
            semantic_results = self._concurrent_llm_calls(semantic_prompts)
        
        # Parse semantic grouping results
        semantic_groups_by_batch = []
        for result in semantic_results:
            metadata = result['metadata']
            batch_indices = metadata['batch_indices']
            batch_entries = [entries[i] for i in batch_indices]
            
            if result['error']:
                # Fallback: no grouping
                logger.warning("Semantic grouping LLM call failed for batch: %s", result['error'])
                semantic_groups_by_batch.append({
                    'groups': [],
                    'metadata': metadata
                })
                continue
            
            # Parse semantic grouping response
            response = result['response']
            try:
                parsed = json_repair.loads(response)
            except Exception:
                try:
                    parsed = json.loads(response)
                except Exception as parse_error:
                    logger.warning("Failed to parse semantic dedup LLM response: %s: %s", 
                                 type(parse_error).__name__, parse_error)
                    semantic_groups_by_batch.append({
                        'groups': [],
                        'metadata': metadata
                    })
                    continue
            
            groups_raw = parsed.get("groups") if isinstance(parsed, dict) else None
            if not isinstance(groups_raw, list):
                semantic_groups_by_batch.append({
                    'groups': [],
                    'metadata': metadata
                })
                continue
            
            # Convert to group format
            groups = []
            assigned = set()
            for group in groups_raw:
                if not isinstance(group, dict):
                    continue
                
                members_raw = group.get("members")
                if not isinstance(members_raw, list):
                    continue
                
                normalized_members = []
                for member in members_raw:
                    try:
                        member_idx = int(member) - 1
                    except (TypeError, ValueError):
                        continue
                    if 0 <= member_idx < len(batch_entries):
                        normalized_members.append(member_idx)
                
                if not normalized_members:
                    continue
                
                rep_raw = group.get("representative")
                try:
                    rep_idx = int(rep_raw) - 1 if rep_raw is not None else None
                except (TypeError, ValueError):
                    rep_idx = None
                
                if rep_idx is None or rep_idx not in normalized_members:
                    rep_idx = normalized_members[0]
                
                rationale = group.get("rationale")
                groups.append({
                    "representative": rep_idx,
                    "members": normalized_members,
                    "rationale": rationale,
                })
                assigned.update(normalized_members)
            
            # Add unassigned items as singleton groups
            for idx in range(len(batch_entries)):
                if idx not in assigned:
                    groups.append({"representative": idx, "members": [idx], "rationale": None})
            
            semantic_groups_by_batch.append({
                'groups': groups,
                'metadata': metadata
            })
        
        # ============================================================
        # PHASE 4: Process results and build final edges
        # ============================================================

        # Initialize intermediate results collector for edge deduplication
        save_intermediate = getattr(config, "save_intermediate_results", False)
        edge_dedup_result = {
            "head_id": head_id,
            "head_name": head_text,
            "relation": relation,
            "total_edges": len(edges),
            "candidates": [],
            "clustering": {
                "method": "average_linkage",
                "threshold": threshold,
                "clusters": []
            },
            "llm_groups": [],
            "final_merges": []
        } if save_intermediate else None
        
        # Save candidates info
        if save_intermediate:
            edge_dedup_result["head_contexts"] = head_context_lines
            for entry in entries:
                edge_dedup_result["candidates"].append({
                    "index": entry["index"],
                    "node_id": entry["node_id"],
                    "description": entry["description"]
                })

        # Save clustering results
        if save_intermediate:
            # Add clustering method info
            edge_dedup_result["clustering"]["method"] = clustering_method
            
            for cluster_idx, cluster in enumerate(initial_clusters):
                cluster_info = {
                    "cluster_id": cluster_idx,
                    "size": len(cluster),
                    "member_indices": cluster,
                    "members": [
                        {
                            "index": idx,
                            "node_id": entries[idx]["node_id"],
                            "description": entries[idx]["description"]
                        }
                        for idx in cluster if 0 <= idx < len(entries)
                    ]
                }
                
                # Add LLM clustering details if available
                if llm_clustering_details and cluster_idx < len(llm_clustering_details):
                    detail = llm_clustering_details[cluster_idx]
                    cluster_info["llm_description"] = detail.get("description", "")
                    cluster_info["llm_rationale"] = detail.get("llm_rationale", "")
                
                edge_dedup_result["clustering"]["clusters"].append(cluster_info)

        # Build final edges from semantic grouping results
        final_edges: list = []
        processed_indices: set = set()
        duplicate_indices: set = set()
        
        # Create a mapping from cluster_idx to semantic results
        semantic_results_map = {}
        for batch_result in semantic_groups_by_batch:
            metadata = batch_result['metadata']
            cluster_idx = metadata['cluster_idx']
            if cluster_idx not in semantic_results_map:
                semantic_results_map[cluster_idx] = []
            semantic_results_map[cluster_idx].append(batch_result)
        
        # Process each cluster
        for cluster_idx, cluster in enumerate(initial_clusters):
            cluster_indices = [idx for idx in cluster if idx not in processed_indices and idx not in duplicate_indices]
            if not cluster_indices:
                continue
            
            # Optimization: Skip LLM call for single-item clusters
            if len(cluster_indices) == 1:
                idx = cluster_indices[0]
                entry = entries[idx]
                final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
                processed_indices.add(idx)
                continue
            
            # Get semantic grouping results for this cluster
            cluster_semantic_results = semantic_results_map.get(cluster_idx, [])
            
            # Process each batch result for this cluster
            for batch_result in cluster_semantic_results:
                groups = batch_result['groups']
                metadata = batch_result['metadata']
                batch_indices = metadata['batch_indices']
                overflow_indices = metadata.get('overflow_indices', [])
                
                # Save LLM groups result
                if save_intermediate:
                    llm_result = {
                        "cluster_id": cluster_idx,
                        "batch_indices": batch_indices,
                        "batch_size": len(batch_indices),
                        "groups": []
                    }
                    if groups:
                        for group in groups:
                            group_info = {
                                "members": group.get("members", []),
                                "representative": group.get("representative"),
                                "rationale": group.get("rationale"),
                                "member_details": [
                                    {
                                        "local_idx": m,
                                        "global_idx": batch_indices[m] if 0 <= m < len(batch_indices) else None,
                                        "description": entries[batch_indices[m]]["description"] if 0 <= m < len(batch_indices) else None
                                    }
                                    for m in group.get("members", [])
                                    if 0 <= m < len(batch_indices)
                                ]
                            }
                            llm_result["groups"].append(group_info)
                    edge_dedup_result["llm_groups"].append(llm_result)
                
                # Process groups
                if not groups:
                    # No grouping, add all batch items as separate edges
                    for global_idx in batch_indices:
                        if global_idx not in processed_indices:
                            entry = entries[global_idx]
                            final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
                            processed_indices.add(global_idx)
                else:
                    # Process each group
                    for group in groups:
                        rep_local = group.get("representative")
                        if rep_local is None or rep_local < 0 or rep_local >= len(batch_indices):
                            continue
                        
                        rep_global = batch_indices[rep_local]
                        if rep_global in processed_indices:
                            continue
                        
                        # Collect duplicates
                        duplicates = []
                        for member_local in group.get("members", []):
                            if member_local < 0 or member_local >= len(batch_indices):
                                continue
                            member_global = batch_indices[member_local]
                            if member_global == rep_global or member_global in processed_indices:
                                continue
                            duplicates.append(entries[member_global])
                            duplicate_indices.add(member_global)
                        
                        # Save merge operation
                        if save_intermediate and duplicates:
                            merge_info = {
                                "representative": {
                                    "index": rep_global,
                                    "node_id": entries[rep_global]["node_id"],
                                    "description": entries[rep_global]["description"]
                                },
                                "duplicates": [
                                    {
                                        "index": d.get("index"),
                                        "node_id": d["node_id"],
                                        "description": d["description"]
                                    }
                                    for d in duplicates
                                ],
                                "rationale": group.get("rationale")
                            }
                            edge_dedup_result["final_merges"].append(merge_info)
                        
                        # Merge metadata and add to final edges
                        merged_data = self._merge_duplicate_metadata(
                            entries[rep_global],
                            duplicates,
                            group.get("rationale"),
                        )
                        
                        final_edges.append((entries[rep_global]["node_id"], merged_data))
                        processed_indices.add(rep_global)
                
                # Process overflow indices (items that exceeded max_candidates)
                for global_idx in overflow_indices:
                    if global_idx not in processed_indices:
                        entry = entries[global_idx]
                        final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
                        processed_indices.add(global_idx)

        for entry in entries:
            idx = entry["index"]
            if idx in processed_indices or idx in duplicate_indices:
                continue
            final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
            processed_indices.add(idx)

        # Save edge dedup result with summary
        if save_intermediate:
            edge_dedup_result["summary"] = {
                "total_edges": len(edges),
                "total_clusters": len(initial_clusters),
                "single_item_clusters": sum(1 for c in initial_clusters if len(c) == 1),
                "multi_item_clusters": sum(1 for c in initial_clusters if len(c) > 1),
                "total_llm_calls": len(edge_dedup_result["llm_groups"]),
                "total_merges": len(edge_dedup_result["final_merges"]),
                "edges_merged": sum(len(m["duplicates"]) for m in edge_dedup_result["final_merges"]),
                "final_edges": len(final_edges)
            }
            
            # Accumulate to class-level collector
            if not hasattr(self, '_edge_dedup_results'):
                self._edge_dedup_results = []
            self._edge_dedup_results.append(edge_dedup_result)

        return final_edges

    def triple_deduplicate(self):
        """deduplicate triples in lv1 and lv2"""
        new_graph = nx.MultiDiGraph()

        for node, node_data in self.graph.nodes(data=True):
            new_graph.add_node(node, **node_data)

        seen_triples = set()
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            relation = data.get('relation') 
            if (u, v, relation) not in seen_triples:
                seen_triples.add((u, v, relation))
                new_graph.add_edge(u, v, **data)
        self.graph = new_graph

    def _prepare_dedup_group(self, head_id: str, relation: str, edges: list, config) -> dict:
        """
        Prepare metadata for a deduplication group.
        
        Returns:
            dict with keys: head_id, head_text, relation, edges, entries, 
                           head_context_lines, candidate_descriptions, config_params
        """
        head_text = self._describe_node(head_id)
        entries = []
        
        for idx, (tail_id, data) in enumerate(edges):
            chunk_ids = self._extract_edge_chunk_ids(data)
            if not chunk_ids:
                chunk_ids = self._collect_node_chunk_ids(tail_id)
            entries.append({
                "index": idx,
                "node_id": tail_id,
                "data": copy.deepcopy(data),
                "raw_data": copy.deepcopy(data),
                "description": self._describe_node(tail_id),
                "description_for_clustering": self._describe_node_for_clustering(tail_id),
                "context_chunk_ids": chunk_ids,
                "context_summaries": self._summarize_contexts(chunk_ids),
            })
        
        # Collect head context
        head_chunk_ids = set()
        for entry in entries:
            for chunk_id in entry.get("context_chunk_ids", []):
                if chunk_id:
                    head_chunk_ids.add(chunk_id)
        
        if not head_chunk_ids:
            for chunk_id in self._collect_node_chunk_ids(head_id):
                if chunk_id:
                    head_chunk_ids.add(chunk_id)
        
        head_context_lines = self._summarize_contexts(list(head_chunk_ids))
        candidate_descriptions = [entry["description_for_clustering"] for entry in entries]
        
        # Extract config parameters
        config_params = {
            'clustering_method': getattr(config, "clustering_method", "embedding"),
            'threshold': getattr(config, "embedding_threshold", 0.85) or 0.85,
            'llm_clustering_batch_size': getattr(config, "llm_clustering_batch_size", 30),
            'max_batch_size': max(1, int(getattr(config, "max_batch_size", 8) or 8)),
            'max_candidates': int(getattr(config, "max_candidates", 0) or 0),
        }
        
        return {
            'head_id': head_id,
            'head_text': head_text,
            'relation': relation,
            'edges': edges,
            'entries': entries,
            'head_context_lines': head_context_lines,
            'candidate_descriptions': candidate_descriptions,
            'config_params': config_params,
            'initial_clusters': None,  # Will be filled by clustering
            'llm_clustering_details': None,  # Will be filled by LLM clustering
            'semantic_results': {},  # Will be filled by semantic dedup
        }
    
    def _collect_clustering_prompts(self, group_data: dict) -> list:
        """
        Collect all clustering prompts for a deduplication group.
        
        Returns:
            List of prompt dicts with keys: type, prompt, metadata
        """
        prompts = []
        head_text = group_data['head_text']
        relation = group_data['relation']
        descriptions = group_data['candidate_descriptions']
        llm_clustering_batch_size = group_data['config_params']['llm_clustering_batch_size']
        
        if len(descriptions) > llm_clustering_batch_size:
            # Multiple batches needed
            for batch_start in range(0, len(descriptions), llm_clustering_batch_size):
                batch_end = min(batch_start + llm_clustering_batch_size, len(descriptions))
                batch_descriptions = descriptions[batch_start:batch_end]
                
                candidate_blocks = [f"[{i+1}] {desc}" for i, desc in enumerate(batch_descriptions)]
                candidates_text = "\n".join(candidate_blocks) if candidate_blocks else "[No candidates]"
                
                prompt = DEFAULT_LLM_CLUSTERING_PROMPT.format(
                    head=head_text or "[UNKNOWN_HEAD]",
                    relation=relation or "[UNKNOWN_RELATION]",
                    candidates=candidates_text
                )
                
                prompts.append({
                    'type': 'clustering',
                    'prompt': prompt,
                    'metadata': {
                        'batch_start': batch_start,
                        'batch_end': batch_end,
                        'batch_offset': batch_start,
                        'descriptions': batch_descriptions,
                    }
                })
        else:
            # Single batch
            candidate_blocks = [f"[{i+1}] {desc}" for i, desc in enumerate(descriptions)]
            candidates_text = "\n".join(candidate_blocks) if candidate_blocks else "[No candidates]"
            
            prompt = DEFAULT_LLM_CLUSTERING_PROMPT.format(
                head=head_text or "[UNKNOWN_HEAD]",
                relation=relation or "[UNKNOWN_RELATION]",
                candidates=candidates_text
            )
            
            prompts.append({
                'type': 'clustering',
                'prompt': prompt,
                'metadata': {
                    'batch_start': 0,
                    'batch_end': len(descriptions),
                    'batch_offset': 0,
                    'descriptions': descriptions,
                }
            })
        
        return prompts
    
    def _parse_clustering_results(self, dedup_groups: list, clustering_results: list):
        """
        Parse clustering results and update dedup_groups with initial_clusters.
        """
        # Group results by group_idx
        results_by_group = defaultdict(list)
        for result in clustering_results:
            group_idx = result['metadata'].get('group_idx')
            if group_idx is not None:
                results_by_group[group_idx].append(result)
        
        # Parse results for each group
        for group_idx, results in results_by_group.items():
            if group_idx >= len(dedup_groups):
                continue
            
            group_data = dedup_groups[group_idx]
            all_clusters = []
            all_details = []
            
            for result in results:
                metadata = result['metadata']
                batch_offset = metadata['batch_offset']
                batch_descriptions = metadata['descriptions']
                
                if result['error']:
                    # Fallback: single cluster
                    fallback_cluster = [idx + batch_offset for idx in range(len(batch_descriptions))]
                    all_clusters.append(fallback_cluster)
                    all_details.append({
                        "description": f"Fallback cluster (error: {result['error']})",
                        "members": fallback_cluster
                    })
                    continue
                
                # Parse clustering response
                try:
                    parsed = json_repair.loads(result['response'])
                except Exception:
                    try:
                        parsed = json.loads(result['response'])
                    except Exception:
                        # Fallback
                        fallback_cluster = [idx + batch_offset for idx in range(len(batch_descriptions))]
                        all_clusters.append(fallback_cluster)
                        all_details.append({
                            "description": "Fallback cluster (parse failed)",
                            "members": fallback_cluster
                        })
                        continue
                
                clusters_raw = parsed.get("clusters") if isinstance(parsed, dict) else None
                if not isinstance(clusters_raw, list):
                    fallback_cluster = [idx + batch_offset for idx in range(len(batch_descriptions))]
                    all_clusters.append(fallback_cluster)
                    all_details.append({
                        "description": "Fallback cluster (invalid response)",
                        "members": fallback_cluster
                    })
                    continue
                
                # Process clusters
                assigned = set()
                for cluster_info in clusters_raw:
                    if not isinstance(cluster_info, dict):
                        continue
                    
                    members_raw = cluster_info.get("members")
                    if not isinstance(members_raw, list):
                        continue
                    
                    cluster_members = []
                    for member in members_raw:
                        try:
                            member_idx = int(member) - 1  # 1-based to 0-based
                        except (TypeError, ValueError):
                            continue
                        if 0 <= member_idx < len(batch_descriptions):
                            adjusted_idx = member_idx + batch_offset
                            cluster_members.append(adjusted_idx)
                            assigned.add(member_idx)
                    
                    if cluster_members:
                        all_clusters.append(cluster_members)
                        all_details.append({
                            "description": cluster_info.get("description", ""),
                            "llm_rationale": cluster_info.get("rationale", ""),
                            "members": cluster_members
                        })
                
                # Add unassigned as singletons
                for idx in range(len(batch_descriptions)):
                    if idx not in assigned:
                        adjusted_idx = idx + batch_offset
                        all_clusters.append([adjusted_idx])
                        all_details.append({
                            "description": f"Singleton cluster for item {adjusted_idx}",
                            "members": [adjusted_idx]
                        })
            
            group_data['initial_clusters'] = all_clusters
            group_data['llm_clustering_details'] = all_details
    
    def _apply_embedding_clustering(self, group_data: dict):
        """Apply embedding-based clustering to a group."""
        threshold = group_data['config_params']['threshold']
        candidate_descriptions = group_data['candidate_descriptions']
        initial_clusters = self._cluster_candidate_tails(candidate_descriptions, threshold)
        group_data['initial_clusters'] = initial_clusters
    
    def _collect_semantic_dedup_prompts(self, group_data: dict) -> list:
        """
        Collect all semantic dedup prompts for a deduplication group.
        
        Returns:
            List of prompt dicts with keys: type, prompt, metadata
        """
        prompts = []
        initial_clusters = group_data.get('initial_clusters', [])
        if not initial_clusters:
            return prompts
        
        head_text = group_data['head_text']
        relation = group_data['relation']
        head_context_lines = group_data['head_context_lines']
        entries = group_data['entries']
        max_batch_size = group_data['config_params']['max_batch_size']
        max_candidates = group_data['config_params']['max_candidates']
        
        for cluster_idx, cluster in enumerate(initial_clusters):
            cluster_indices = cluster.copy()
            
            # Skip single-item clusters
            if len(cluster_indices) <= 1:
                continue
            
            # Apply max_candidates limit
            overflow_indices = []
            if max_candidates and len(cluster_indices) > max_candidates:
                overflow_indices = cluster_indices[max_candidates:]
                cluster_indices = cluster_indices[:max_candidates]
            
            # Batch the cluster
            batch_num = 0
            while cluster_indices:
                batch_indices = cluster_indices[:max_batch_size]
                batch_entries = [entries[i] for i in batch_indices]
                
                # Build prompt
                prompt = self._build_semantic_dedup_prompt(
                    head_text, relation, head_context_lines, batch_entries
                )
                
                prompts.append({
                    'type': 'semantic',
                    'prompt': prompt,
                    'metadata': {
                        'cluster_idx': cluster_idx,
                        'batch_num': batch_num,
                        'batch_indices': batch_indices,
                        'overflow_indices': overflow_indices if batch_num == 0 else [],
                    }
                })
                
                cluster_indices = cluster_indices[len(batch_indices):]
                batch_num += 1
        
        return prompts
    
    def _parse_semantic_dedup_results(self, dedup_groups: list, semantic_results: list):
        """
        Parse semantic dedup results and update dedup_groups.
        """
        # Group results by group_idx
        results_by_group = defaultdict(list)
        for result in semantic_results:
            group_idx = result['metadata'].get('group_idx')
            if group_idx is not None:
                results_by_group[group_idx].append(result)
        
        # Parse results for each group
        for group_idx, results in results_by_group.items():
            if group_idx >= len(dedup_groups):
                continue
            
            group_data = dedup_groups[group_idx]
            entries = group_data['entries']
            
            # Store parsed groups by (cluster_idx, batch_num)
            semantic_groups = {}
            
            for result in results:
                metadata = result['metadata']
                cluster_idx = metadata['cluster_idx']
                batch_num = metadata['batch_num']
                batch_indices = metadata['batch_indices']
                overflow_indices = metadata.get('overflow_indices', [])
                
                key = (cluster_idx, batch_num)
                
                if result['error']:
                    # No grouping
                    semantic_groups[key] = {
                        'groups': [],
                        'batch_indices': batch_indices,
                        'overflow_indices': overflow_indices,
                    }
                    continue
                
                # Parse response
                try:
                    parsed = json_repair.loads(result['response'])
                except Exception:
                    try:
                        parsed = json.loads(result['response'])
                    except Exception:
                        semantic_groups[key] = {
                            'groups': [],
                            'batch_indices': batch_indices,
                            'overflow_indices': overflow_indices,
                        }
                        continue
                
                groups_raw = parsed.get("groups") if isinstance(parsed, dict) else None
                if not isinstance(groups_raw, list):
                    semantic_groups[key] = {
                        'groups': [],
                        'batch_indices': batch_indices,
                        'overflow_indices': overflow_indices,
                    }
                    continue
                
                # Parse groups
                groups = []
                assigned = set()
                for group in groups_raw:
                    if not isinstance(group, dict):
                        continue
                    
                    members_raw = group.get("members")
                    if not isinstance(members_raw, list):
                        continue
                    
                    normalized_members = []
                    for member in members_raw:
                        try:
                            member_idx = int(member) - 1
                        except (TypeError, ValueError):
                            continue
                        if 0 <= member_idx < len(batch_indices):
                            normalized_members.append(member_idx)
                    
                    if not normalized_members:
                        continue
                    
                    rep_raw = group.get("representative")
                    try:
                        rep_idx = int(rep_raw) - 1 if rep_raw is not None else None
                    except (TypeError, ValueError):
                        rep_idx = None
                    
                    if rep_idx is None or rep_idx not in normalized_members:
                        rep_idx = normalized_members[0]
                    
                    groups.append({
                        "representative": rep_idx,
                        "members": normalized_members,
                        "rationale": group.get("rationale"),
                    })
                    assigned.update(normalized_members)
                
                # Add unassigned as singletons
                for idx in range(len(batch_indices)):
                    if idx not in assigned:
                        groups.append({
                            "representative": idx,
                            "members": [idx],
                            "rationale": None
                        })
                
                semantic_groups[key] = {
                    'groups': groups,
                    'batch_indices': batch_indices,
                    'overflow_indices': overflow_indices,
                }
            
            group_data['semantic_results'] = semantic_groups
    
    def _build_final_edges(self, group_data: dict, save_intermediate: bool) -> list:
        """
        Build final deduplicated edges from parsed results.
        
        Returns:
            List of (tail_id, edge_data) tuples
        """
        entries = group_data['entries']
        initial_clusters = group_data.get('initial_clusters', [])
        semantic_results = group_data.get('semantic_results', {})
        
        final_edges = []
        processed_indices = set()
        duplicate_indices = set()
        
        # Initialize intermediate results if needed
        edge_dedup_result = None
        if save_intermediate:
            edge_dedup_result = {
                "head_id": group_data['head_id'],
                "head_name": group_data['head_text'],
                "relation": group_data['relation'],
                "total_edges": len(group_data['edges']),
                "candidates": [
                    {
                        "index": e["index"],
                        "node_id": e["node_id"],
                        "description": e["description"]
                    }
                    for e in entries
                ],
                "clustering": {
                    "method": group_data['config_params']['clustering_method'],
                    "threshold": group_data['config_params']['threshold'],
                    "clusters": []
                },
                "llm_groups": [],
                "final_merges": []
            }
            
            # Save clustering info
            for cluster_idx, cluster in enumerate(initial_clusters):
                cluster_info = {
                    "cluster_id": cluster_idx,
                    "size": len(cluster),
                    "member_indices": cluster,
                    "members": [
                        {
                            "index": idx,
                            "node_id": entries[idx]["node_id"],
                            "description": entries[idx]["description"]
                        }
                        for idx in cluster if 0 <= idx < len(entries)
                    ]
                }
                llm_clustering_details = group_data.get('llm_clustering_details')
                if llm_clustering_details and cluster_idx < len(llm_clustering_details):
                    detail = llm_clustering_details[cluster_idx]
                    cluster_info["llm_description"] = detail.get("description", "")
                    cluster_info["llm_rationale"] = detail.get("llm_rationale", "")
                edge_dedup_result["clustering"]["clusters"].append(cluster_info)
        
        # Process each cluster
        for cluster_idx, cluster in enumerate(initial_clusters):
            cluster_indices = [idx for idx in cluster if idx not in processed_indices and idx not in duplicate_indices]
            if not cluster_indices:
                continue
            
            # Single-item clusters - no dedup needed
            if len(cluster_indices) == 1:
                idx = cluster_indices[0]
                entry = entries[idx]
                final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
                processed_indices.add(idx)
                continue
            
            # Process semantic dedup results for this cluster
            batch_num = 0
            while True:
                key = (cluster_idx, batch_num)
                if key not in semantic_results:
                    break
                
                result = semantic_results[key]
                groups = result['groups']
                batch_indices = result['batch_indices']
                overflow_indices = result.get('overflow_indices', [])
                
                # Save LLM groups
                if save_intermediate:
                    llm_result = {
                        "cluster_id": cluster_idx,
                        "batch_indices": batch_indices,
                        "batch_size": len(batch_indices),
                        "groups": []
                    }
                    for group in groups:
                        group_info = {
                            "members": group.get("members", []),
                            "representative": group.get("representative"),
                            "rationale": group.get("rationale"),
                            "member_details": [
                                {
                                    "local_idx": m,
                                    "global_idx": batch_indices[m] if 0 <= m < len(batch_indices) else None,
                                    "description": entries[batch_indices[m]]["description"] if 0 <= m < len(batch_indices) else None
                                }
                                for m in group.get("members", [])
                                if 0 <= m < len(batch_indices)
                            ]
                        }
                        llm_result["groups"].append(group_info)
                    edge_dedup_result["llm_groups"].append(llm_result)
                
                # Process groups
                if not groups:
                    # No grouping - add all as separate edges
                    for global_idx in batch_indices:
                        if global_idx not in processed_indices:
                            entry = entries[global_idx]
                            final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
                            processed_indices.add(global_idx)
                else:
                    for group in groups:
                        rep_local = group.get("representative")
                        if rep_local is None or rep_local < 0 or rep_local >= len(batch_indices):
                            continue
                        
                        rep_global = batch_indices[rep_local]
                        if rep_global in processed_indices:
                            continue
                        
                        # Collect duplicates
                        duplicates = []
                        for member_local in group.get("members", []):
                            if member_local < 0 or member_local >= len(batch_indices):
                                continue
                            member_global = batch_indices[member_local]
                            if member_global == rep_global or member_global in processed_indices:
                                continue
                            duplicates.append(entries[member_global])
                            duplicate_indices.add(member_global)
                        
                        # Save merge info
                        if save_intermediate and duplicates:
                            merge_info = {
                                "representative": {
                                    "index": rep_global,
                                    "node_id": entries[rep_global]["node_id"],
                                    "description": entries[rep_global]["description"]
                                },
                                "duplicates": [
                                    {
                                        "index": d.get("index"),
                                        "node_id": d["node_id"],
                                        "description": d["description"]
                                    }
                                    for d in duplicates
                                ],
                                "rationale": group.get("rationale")
                            }
                            edge_dedup_result["final_merges"].append(merge_info)
                        
                        # Merge and add to final edges
                        merged_data = self._merge_duplicate_metadata(
                            entries[rep_global],
                            duplicates,
                            group.get("rationale"),
                        )
                        final_edges.append((entries[rep_global]["node_id"], merged_data))
                        processed_indices.add(rep_global)
                
                # Handle overflow
                if batch_num == 0:
                    for global_idx in overflow_indices:
                        if global_idx not in processed_indices:
                            entry = entries[global_idx]
                            final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
                            processed_indices.add(global_idx)
                
                batch_num += 1
        
        # Add any remaining unprocessed entries
        for entry in entries:
            idx = entry["index"]
            if idx not in processed_indices and idx not in duplicate_indices:
                final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
                processed_indices.add(idx)
        
        # Save results
        if save_intermediate:
            edge_dedup_result["summary"] = {
                "total_edges": len(group_data['edges']),
                "total_clusters": len(initial_clusters),
                "single_item_clusters": sum(1 for c in initial_clusters if len(c) == 1),
                "multi_item_clusters": sum(1 for c in initial_clusters if len(c) > 1),
                "total_llm_calls": len(edge_dedup_result["llm_groups"]),
                "total_merges": len(edge_dedup_result["final_merges"]),
                "edges_merged": sum(len(m["duplicates"]) for m in edge_dedup_result["final_merges"]),
                "final_edges": len(final_edges)
            }
            
            if not hasattr(self, '_edge_dedup_results'):
                self._edge_dedup_results = []
            self._edge_dedup_results.append(edge_dedup_result)
        
        return final_edges

    def triple_deduplicate_semantic(self):
        """
        Deduplicate triples in lv1 and lv2 using batch concurrent LLM processing.
        
        This method uses a multi-phase approach:
        1. Prepare all head-relation groups
        2. Batch collect and process all clustering prompts concurrently
        3. Batch collect and process all semantic dedup prompts concurrently
        4. Build final deduplicated graph
        """
        
        # Initialize edge dedup results collector
        config = self._get_semantic_dedup_config()
        save_intermediate = config and getattr(config, "save_intermediate_results", False)
        if save_intermediate:
            self._edge_dedup_results = []
        
        new_graph = nx.MultiDiGraph()

        for node, node_data in self.graph.nodes(data=True):
            new_graph.add_node(node, **node_data)

        # Group edges by (head, relation)
        grouped_edges: dict = defaultdict(list)
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            relation = data.get('relation')
            grouped_edges[(u, relation)].append((v, copy.deepcopy(data)))

        # ================================================================
        # PHASE 1: Prepare all groups and collect metadata
        # ================================================================
        dedup_groups = []  # List of dicts with all info needed for deduplication
        
        for (head, relation), edges in grouped_edges.items():
            exact_unique = self._deduplicate_exact(edges)
            
            # Only process if semantic dedup is enabled and there are multiple edges
            if not (self._semantic_dedup_enabled() and len(exact_unique) > 1):
                # No dedup needed, add directly to graph
                for tail_id, edge_data in exact_unique:
                    new_graph.add_edge(head, tail_id, **edge_data)
                continue
            
            # Prepare group metadata
            group_data = self._prepare_dedup_group(head, relation, exact_unique, config)
            if group_data:
                dedup_groups.append(group_data)
        
        logger.info(f"Prepared {len(dedup_groups)} groups for semantic deduplication")
        
        if not dedup_groups:
            self.graph = new_graph
            return
        
        # ================================================================
        # PHASE 2: Batch collect and process clustering prompts
        # ================================================================
        clustering_prompts = []
        clustering_method = getattr(config, "clustering_method", "embedding")
        
        if clustering_method == "llm":
            logger.info("Collecting all clustering prompts...")
            for group_idx, group_data in enumerate(dedup_groups):
                prompts = self._collect_clustering_prompts(group_data)
                for prompt_data in prompts:
                    prompt_data['metadata']['group_idx'] = group_idx
                    clustering_prompts.append(prompt_data)
            
            logger.info(f"Collected {len(clustering_prompts)} clustering prompts, processing concurrently...")
            clustering_results = self._concurrent_llm_calls(clustering_prompts)
            
            # Parse clustering results and update group_data
            logger.info("Parsing clustering results...")
            self._parse_clustering_results(dedup_groups, clustering_results)
        else:
            # Use embedding-based clustering
            logger.info("Using embedding-based clustering...")
            for group_data in dedup_groups:
                self._apply_embedding_clustering(group_data)
        
        # ================================================================
        # PHASE 3: Batch collect and process semantic dedup prompts
        # ================================================================
        logger.info("Collecting all semantic dedup prompts...")
        semantic_prompts = []
        
        for group_idx, group_data in enumerate(dedup_groups):
            prompts = self._collect_semantic_dedup_prompts(group_data)
            for prompt_data in prompts:
                prompt_data['metadata']['group_idx'] = group_idx
                semantic_prompts.append(prompt_data)
        
        logger.info(f"Collected {len(semantic_prompts)} semantic dedup prompts, processing concurrently...")
        semantic_results = self._concurrent_llm_calls(semantic_prompts)
        
        # Parse semantic dedup results and update group_data
        logger.info("Parsing semantic dedup results...")
        self._parse_semantic_dedup_results(dedup_groups, semantic_results)
        
        # ================================================================
        # PHASE 4: Build final deduplicated edges
        # ================================================================
        logger.info("Building final deduplicated graph...")
        for group_data in dedup_groups:
            final_edges = self._build_final_edges(group_data, save_intermediate)
            head = group_data['head_id']
            for tail_id, edge_data in final_edges:
                new_graph.add_edge(head, tail_id, **edge_data)
        
        self.graph = new_graph
        logger.info("Semantic deduplication completed")
        
        # Save edge deduplication intermediate results
        if save_intermediate and hasattr(self, '_edge_dedup_results') and self._edge_dedup_results:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = getattr(config, "intermediate_results_path", None)
            
            if not output_path:
                output_path = f"output/dedup_intermediate/{self.dataset_name}_edge_dedup_{timestamp}.json"
            else:
                # If path is a directory, add filename
                if output_path.endswith('/'):
                    output_path = f"{output_path}{self.dataset_name}_edge_dedup_{timestamp}.json"
                else:
                    # Add _edge suffix to distinguish from keyword dedup
                    base, ext = os.path.splitext(output_path)
                    output_path = f"{base}_edge_{timestamp}{ext}"
            
            # Ensure directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # Build complete results structure
            edge_intermediate_results = {
                "dataset": self.dataset_name,
                "dedup_type": "edge_deduplication",
                "config": {
                    "threshold": getattr(config, "embedding_threshold", 0.85) or 0.85,
                    "max_batch_size": max(1, int(getattr(config, "max_batch_size", 8) or 8)),
                    "max_candidates": int(getattr(config, "max_candidates", 0) or 0),
                },
                "triples": self._edge_dedup_results,
                "summary": {
                    "total_triples": len(self._edge_dedup_results),
                    "total_edges": sum(r["total_edges"] for r in self._edge_dedup_results),
                    "total_clusters": sum(len(r["clustering"]["clusters"]) for r in self._edge_dedup_results),
                    "total_llm_calls": sum(len(r["llm_groups"]) for r in self._edge_dedup_results),
                    "total_merges": sum(len(r["final_merges"]) for r in self._edge_dedup_results),
                    "total_edges_merged": sum(r["summary"]["edges_merged"] for r in self._edge_dedup_results),
                    "final_total_edges": sum(r["summary"]["final_edges"] for r in self._edge_dedup_results)
                }
            }
            
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(edge_intermediate_results, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved edge deduplication intermediate results to: {output_path}")
                logger.info(f"Summary: {edge_intermediate_results['summary']}")
            except Exception as e:
                logger.warning(f"Failed to save edge deduplication intermediate results: {e}")
            
            # Clean up
            del self._edge_dedup_results


    def format_output(self) -> List[Dict[str, Any]]:
        """convert graph to specified output format"""
        output = []

        for u, v, data in self.graph.edges(data=True):
            u_data = self.graph.nodes[u]
            v_data = self.graph.nodes[v]

            relationship = {
                "start_node": {
                    "label": u_data["label"],
                    "properties": u_data["properties"],
                },
                "relation": data["relation"],
                "end_node": {
                    "label": v_data["label"],
                    "properties": v_data["properties"],
                },
            }
            output.append(relationship)

        return output
    
    def save_graphml(self, output_path: str):
        graph_processor.save_graph(self.graph, output_path)
    
    def build_knowledge_graph(self, corpus):
        logger.info(f"========{'Start Building':^20}========")
        logger.info(f"{'➖' * 30}")
        
        with open(corpus, 'r', encoding='utf-8') as f:
            documents = json_repair.load(f)
        
        self.process_all_documents(documents)
        
        logger.info(f"All Process finished, token cost: {self.token_len}")
        
        self.save_chunks_to_file()
        
        output = self.format_output()
        
        json_output_path = f"output/graphs/{self.dataset_name}_new.json"
        os.makedirs("output/graphs", exist_ok=True)
        with open(json_output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        logger.info(f"Graph saved to {json_output_path}")
        
        return output
