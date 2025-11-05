"""
改进的Semantic Dedup Prompt方案
用于解决rationale与members不一致的问题

使用方法：
1. 将此文件中的IMPROVED_SEMANTIC_DEDUP_PROMPT复制到models/constructor/kt_gen.py
2. 替换原来的DEFAULT_SEMANTIC_DEDUP_PROMPT（第23-94行）
"""

IMPROVED_SEMANTIC_DEDUP_PROMPT = (
    "You are a knowledge graph curation assistant performing entity deduplication.\n"
    "All listed triples share the same head entity and relation.\n\n"
    
    "🚨 ===== CRITICAL RULE - READ THIS FIRST ===== 🚨\n"
    "ABSOLUTE REQUIREMENT FOR OUTPUT CONSISTENCY:\n"
    "• If your rationale says candidates X and Y are 'the same', 'coreferent', 'should be merged',\n"
    "  '应该合并', '视为同一实体', '予以合并', or ANY similar phrase,\n"
    "  then X and Y MUST appear together in the SAME group's members array.\n"
    "• DO NOT create separate groups for items you describe as being the same entity!\n\n"
    
    "✅ CORRECT Example - All same-entity candidates in ONE group:\n"
    "   Input: [1] NYC, [2] New York City, [3] The Big Apple\n"
    "   Output: {\"members\": [1, 2, 3], \"representative\": 2, \n"
    "            \"rationale\": \"[1], [2], and [3] all refer to the same city\"}\n\n"
    
    "❌ WRONG Example - Creating separate groups (DO NOT DO THIS!):\n"
    "   ❌ Group A: {\"members\": [1], \"rationale\": \"NYC is ...\"}\n"
    "   ❌ Group B: {\"members\": [2], \"rationale\": \"与[1]是同一实体，应该合并\"} ← WRONG!\n"
    "   ❌ Group C: {\"members\": [3], \"rationale\": \"与[1][2]相同，予以合并\"} ← WRONG!\n"
    "   ☝️ If you think [1], [2], [3] are the same, put them in ONE group, not three!\n\n"
    
    "🚨 ============================================== 🚨\n\n"
    
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
    "3. Choose the most informative expression as representative\n"
    "4. Provide clear rationale based on REFERENTIAL IDENTITY\n"
    
    "5. **RATIONALE WRITING RULES** (VERY IMPORTANT):\n"
    "   a) Each rationale should ONLY describe the members in THIS group\n"
    "   b) Use candidate numbers (e.g., \"[1] and [2] and [5]\") for items IN THIS GROUP\n"
    "   c) ⚠️ NEVER reference merging with candidates NOT in this group's members array!\n"
    "   d) ⚠️ If you write \"[1] and [5] are the same\", then members MUST be [1, 5]\n"
    "   e) If comparing with non-members, only explain why they are DIFFERENT\n\n"
    
    "6. **FINAL CONSISTENCY CHECK BEFORE RESPONDING**:\n"
    "   → Read each rationale you wrote\n"
    "   → Extract all candidate numbers mentioned as \"same\"/\"merge\"/\"coreferent\"/\"合并\"\n"
    "   → Verify ALL those numbers are in that group's members array\n"
    "   → If not, either:\n"
    "      • Add them to members, OR\n"
    "      • Rewrite rationale to not mention them as being the same\n\n"
    
    "Respond with strict JSON using this schema:\n"
    "{{\n"
    "  \"groups\": [\n"
    "    {{\"members\": [1, 3], \"representative\": 3, \"rationale\": \"Why [1] and [3] are coreferent (same referent).\"}}\n"
    "  ]\n"
    "}}\n"
)


# 如果需要attribute版本，也要相应修改
IMPROVED_ATTRIBUTE_DEDUP_PROMPT = (
    "You are a knowledge graph curation assistant performing attribute value deduplication.\n"
    "All listed triples share the same head entity and relation.\n\n"
    
    "🚨 ===== CRITICAL RULE - READ THIS FIRST ===== 🚨\n"
    "ABSOLUTE REQUIREMENT FOR OUTPUT CONSISTENCY:\n"
    "• If your rationale says values X and Y are 'equivalent', 'the same', 'should be merged',\n"
    "  '应该合并', '等价', '予以合并', or ANY similar phrase,\n"
    "  then X and Y MUST appear together in the SAME group's members array.\n"
    "• DO NOT create separate groups for items you describe as being equivalent!\n\n"
    
    "✅ CORRECT Example - All equivalent values in ONE group:\n"
    "   Input: [1] 10cm, [2] 100mm, [3] 0.1m\n"
    "   Output: {\"members\": [1, 2, 3], \"representative\": 3, \n"
    "            \"rationale\": \"[1], [2], and [3] express the same length in different units\"}\n\n"
    
    "❌ WRONG Example - Creating separate groups (DO NOT DO THIS!):\n"
    "   ❌ Group A: {\"members\": [1], \"rationale\": \"10cm ...\"}\n"
    "   ❌ Group B: {\"members\": [2], \"rationale\": \"与[1]等价，应该合并\"} ← WRONG!\n"
    "   ❌ Group C: {\"members\": [3], \"rationale\": \"与[1][2]相同\"} ← WRONG!\n"
    "   ☝️ If you think [1], [2], [3] are equivalent, put them in ONE group!\n\n"
    
    "🚨 ============================================== 🚨\n\n"
    
    "Head entity: {head}\n"
    "Relation: {relation}\n\n"
    "Head contexts:\n{head_context}\n\n"
    "Candidate attribute values:\n"
    "{candidates}\n\n"
    
    "TASK: Identify which attribute values are EQUIVALENT (express the exact same property-value pair).\n\n"
    
    "[... rest of the attribute prompt remains similar ...]\n"
    
    "OUTPUT REQUIREMENTS:\n"
    "1. Every input index must appear in exactly one group\n"
    "2. Each group represents ONE property-value pair with its various expressions\n"
    "3. Choose the most complete and informative expression as representative\n"
    "4. Provide clear rationale based on VALUE IDENTITY\n"
    
    "5. **RATIONALE WRITING RULES** (VERY IMPORTANT):\n"
    "   a) Each rationale should ONLY describe the members in THIS group\n"
    "   b) Use candidate numbers (e.g., \"[1] and [2] and [5]\") for items IN THIS GROUP\n"
    "   c) ⚠️ NEVER reference merging with candidates NOT in this group's members array!\n"
    "   d) ⚠️ If you write \"[1] and [5] are equivalent\", then members MUST be [1, 5]\n"
    "   e) If comparing with non-members, only explain why they are DIFFERENT\n\n"
    
    "6. **FINAL CONSISTENCY CHECK BEFORE RESPONDING**:\n"
    "   → Read each rationale you wrote\n"
    "   → Extract all candidate numbers mentioned as \"equivalent\"/\"same\"/\"合并\"\n"
    "   → Verify ALL those numbers are in that group's members array\n"
    "   → If not, either add them to members OR rewrite rationale\n\n"
    
    "Respond with strict JSON using this schema:\n"
    "{{\n"
    "  \"groups\": [\n"
    "    {{\"members\": [1, 3], \"representative\": 3, \"rationale\": \"Why [1] and [3] are equivalent.\"}}\n"
    "  ]\n"
    "}}\n"
)


"""
使用说明：

1. 修改 /workspace/models/constructor/kt_gen.py

   替换第23-94行的 DEFAULT_SEMANTIC_DEDUP_PROMPT 为上面的 IMPROVED_SEMANTIC_DEDUP_PROMPT
   替换第96-169行的 DEFAULT_ATTRIBUTE_DEDUP_PROMPT 为上面的 IMPROVED_ATTRIBUTE_DEDUP_PROMPT

2. 关键改进点：

   a) 将一致性要求放在最前面（"CRITICAL RULE - READ THIS FIRST"）
   b) 使用emoji和边框使其更醒目
   c) 提供了正确和错误的对比例子
   d) 使用中英文混合的关键词匹配
   e) 增加了"FINAL CONSISTENCY CHECK"步骤
   f) 修改了RATIONALE WRITING RULES，更明确地禁止引用不在members中的候选项

3. 测试建议：

   修改后，使用相同的测试数据，观察：
   - LLM是否将[1]、[5]、[6]正确地放在同一个group中
   - rationale是否不再包含"与[X]合并"这样的表述（当X不在members中时）

4. 如果问题仍然存在：

   a) 降低temperature到0.1（在配置文件中或调用时）
   b) 考虑切换到更强大的模型（如GPT-4o、Claude 3.5）
   c) 实施后处理验证（见下面的validation函数）
"""


def validate_group_consistency(groups_raw: list, logger=None) -> tuple[list, list]:
    """
    验证并报告groups中rationale与members的不一致问题
    
    Args:
        groups_raw: LLM返回的groups列表
        logger: 日志对象
        
    Returns:
        (fixed_groups, warnings): 修正后的groups和警告信息列表
    """
    import re
    
    fixed_groups = []
    warnings = []
    
    for group_idx, group in enumerate(groups_raw):
        if not isinstance(group, dict):
            continue
            
        rationale = group.get("rationale", "")
        members = group.get("members", [])
        representative = group.get("representative")
        
        # 从rationale中提取所有被引用的候选项索引
        referenced_indices = set()
        for match in re.finditer(r'\[(\d+)\]', rationale):
            try:
                idx = int(match.group(1))
                referenced_indices.add(idx)
            except ValueError:
                continue
        
        # 检查是否提到"合并"、"相同"等关键词
        merge_keywords = [
            '合并', '一致', '等价', '相同', '同一',
            'merge', 'same', 'identical', 'coreferent', 'equivalent',
            '视为同一', '予以合并', '应该合并'
        ]
        mentions_merge = any(keyword in rationale.lower() for keyword in merge_keywords)
        
        # 检测不一致性：rationale中提到要合并的索引，但不在members中
        if referenced_indices and mentions_merge:
            members_set = set(members)
            missing_refs = referenced_indices - members_set
            
            if missing_refs:
                warning_msg = (
                    f"Group {group_idx}: Inconsistency detected!\n"
                    f"  Rationale mentions merging with {sorted(missing_refs)}\n"
                    f"  But members only contains {sorted(members)}\n"
                    f"  Referenced indices: {sorted(referenced_indices)}\n"
                    f"  Rationale snippet: {rationale[:100]}..."
                )
                warnings.append(warning_msg)
                
                if logger:
                    logger.warning(warning_msg)
        
        # 保留原始group（不自动修改，因为无法确定LLM意图）
        fixed_groups.append(group)
    
    return fixed_groups, warnings


# 在 kt_gen.py 中集成validation的示例代码：
def example_integration_in_parse_semantic_dedup_results():
    """
    这是一个示例，展示如何在_parse_semantic_dedup_results中集成validation
    """
    # 在 kt_gen.py 第3996-4032行的位置，解析完groups_raw后添加：
    
    # --- 添加这段代码 ---
    from utils.logger import logger
    
    # 验证一致性
    groups, warnings = validate_group_consistency(groups_raw, logger)
    
    if warnings:
        logger.warning(
            f"Found {len(warnings)} consistency issues in semantic dedup results. "
            f"Consider reviewing the prompt or using a different model."
        )
        # 可选：记录到文件用于后续分析
        # with open("consistency_warnings.log", "a") as f:
        #     for w in warnings:
        #         f.write(f"{w}\n\n")
    # --- 集成结束 ---
    
    # 继续原有的处理流程...
    pass
