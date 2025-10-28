"""
专业方案实现：LLM检测 + 代码修正

核心思想：
1. LLM只做它擅长的：语义理解，检测不一致
2. 代码做它擅长的：数据操作，执行修正
"""

import copy
import json
import logging
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class SemanticDedupValidator:
    """
    语义去重验证器（专业方案）
    """
    
    # Prompt：LLM只检测，不修正
    VALIDATION_PROMPT = """
You are validating semantic deduplication results.

INPUT:
{dedup_results}

TASK:
Find groups where the rationale's intent doesn't match the actual grouping.

RULE:
A group is INCONSISTENT when:
- Rationale says should merge with another group, but members are separate
- Rationale says should stay separate, but members include other groups

OUTPUT FORMAT:
Return JSON with only the inconsistencies:
{
  "has_inconsistencies": true/false,
  "inconsistencies": [
    {
      "group_id": N,
      "issue": "brief description of the problem",
      "action": "merge" or "split",
      "target_groups": [list of group IDs to merge with]
    }
  ]
}

If no inconsistencies:
{
  "has_inconsistencies": false,
  "inconsistencies": []
}

IMPORTANT:
- Only report the inconsistencies, don't try to fix them
- Focus on understanding the rationale's intent
- Use your language understanding
- Don't generate corrected_groups - the code will handle that
"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    def validate_and_correct(
        self, 
        groups: List[Dict],
        original_candidates: List[str]
    ) -> Tuple[List[Dict], Optional[Dict]]:
        """
        验证并修正语义去重结果
        
        Args:
            groups: 去重后的groups
            original_candidates: 原始候选项
            
        Returns:
            (corrected_groups, validation_report)
        """
        # Phase 1: LLM检测不一致
        validation_result = self._detect_inconsistencies(groups)
        
        validation_report = {
            'validation_attempted': True,
            'has_inconsistencies': validation_result['has_inconsistencies'],
            'inconsistencies': validation_result['inconsistencies']
        }
        
        if not validation_result['has_inconsistencies']:
            logger.info("No inconsistencies found")
            validation_report['corrected'] = False
            return groups, validation_report
        
        # Phase 2: 代码执行修正
        logger.info("Found %d inconsistencies, applying corrections", 
                   len(validation_result['inconsistencies']))
        
        try:
            corrected_groups = self._apply_corrections(
                groups,
                validation_result['inconsistencies']
            )
        except Exception as e:
            logger.error("Failed to apply corrections: %s", e)
            validation_report['corrected'] = False
            validation_report['error'] = str(e)
            return groups, validation_report
        
        # Phase 3: 验证数据完整性
        integrity_ok, error_msg = self._verify_data_integrity(
            corrected_groups,
            original_candidates
        )
        
        if not integrity_ok:
            logger.warning("Data integrity check failed: %s. Keeping original groups.", error_msg)
            validation_report['corrected'] = False
            validation_report['error'] = error_msg
            return groups, validation_report
        
        # 成功
        logger.info("Corrections applied successfully: %d groups → %d groups",
                   len(groups), len(corrected_groups))
        validation_report['corrected'] = True
        validation_report['original_group_count'] = len(groups)
        validation_report['corrected_group_count'] = len(corrected_groups)
        
        return corrected_groups, validation_report
    
    def _detect_inconsistencies(self, groups: List[Dict]) -> Dict:
        """
        Phase 1: LLM检测不一致
        
        LLM只做语义理解，不做数据操作
        """
        # 构建prompt
        dedup_results_text = self._format_groups_for_llm(groups)
        prompt = self.VALIDATION_PROMPT.format(dedup_results=dedup_results_text)
        
        # 调用LLM
        try:
            response = self.llm_client.call_api(prompt)
            result = json.loads(response)
        except Exception as e:
            logger.warning("LLM validation failed: %s", e)
            return {'has_inconsistencies': False, 'inconsistencies': []}
        
        return result
    
    def _apply_corrections(
        self, 
        groups: List[Dict],
        inconsistencies: List[Dict]
    ) -> List[Dict]:
        """
        Phase 2: 代码执行修正
        
        代码做数据操作，保证正确性
        """
        # 深拷贝，避免修改原始数据
        corrected = copy.deepcopy(groups)
        merged_groups = set()  # 记录已被合并的groups
        
        for inconsistency in inconsistencies:
            group_id = inconsistency['group_id']
            action = inconsistency['action']
            target_groups = inconsistency.get('target_groups', [])
            
            if group_id in merged_groups:
                # 已经被合并过，跳过
                continue
            
            if action == 'merge' and target_groups:
                # 执行合并
                self._merge_groups(corrected, group_id, target_groups[0], merged_groups)
            
            elif action == 'split':
                # TODO: 实现split逻辑
                logger.warning("Split action not implemented yet")
        
        # 移除已合并的groups
        corrected = [g for i, g in enumerate(corrected) if i not in merged_groups]
        
        return corrected
    
    def _merge_groups(
        self,
        groups: List[Dict],
        source_id: int,
        target_id: int,
        merged_groups: set
    ):
        """
        合并两个groups
        
        这是代码层面的操作，保证数据正确性
        """
        if source_id >= len(groups) or target_id >= len(groups):
            logger.error("Invalid group IDs: source=%d, target=%d", source_id, target_id)
            return
        
        source_group = groups[source_id]
        target_group = groups[target_id]
        
        logger.info("Merging group %d into group %d", source_id, target_id)
        
        # 合并members
        target_group['members'].extend(source_group['members'])
        target_group['members'] = sorted(set(target_group['members']))
        
        # 合并rationale（简单拼接，可以优化）
        target_group['rationale'] = self._merge_rationales(
            target_group['rationale'],
            source_group['rationale']
        )
        
        # 标记source_group已被合并
        merged_groups.add(source_id)
        
        logger.debug("After merge: group %d has %d members", 
                    target_id, len(target_group['members']))
    
    def _merge_rationales(self, rationale1: str, rationale2: str) -> str:
        """
        合并两个rationale
        
        简单实现：如果rationale2提到了合并，就用rationale1
        可以根据需要优化
        """
        # 如果rationale2明确说要合并，主要保留rationale1
        merge_keywords = ['合并', '一致', 'merge', 'same', 'identical']
        if any(kw in rationale2 for kw in merge_keywords):
            return rationale1
        
        # 否则拼接
        return f"{rationale1} 与另一组合并。"
    
    def _verify_data_integrity(
        self,
        groups: List[Dict],
        original_candidates: List[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Phase 3: 验证数据完整性
        
        确保修正后的数据是正确的
        """
        all_items = set(range(len(original_candidates)))
        covered_items = set()
        
        # 收集所有covered items
        for group in groups:
            covered_items.update(group['members'])
        
        # 检查missing items
        missing_items = all_items - covered_items
        if missing_items:
            return False, f"Missing items: {sorted(missing_items)}"
        
        # 检查extra items
        extra_items = covered_items - all_items
        if extra_items:
            return False, f"Invalid items (out of range): {sorted(extra_items)}"
        
        # 检查重复items
        all_members = []
        for group in groups:
            all_members.extend(group['members'])
        
        if len(all_members) != len(set(all_members)):
            duplicates = [item for item in all_members if all_members.count(item) > 1]
            return False, f"Duplicate items: {sorted(set(duplicates))}"
        
        # 通过所有检查
        return True, None
    
    def _format_groups_for_llm(self, groups: List[Dict]) -> str:
        """
        格式化groups给LLM看
        """
        lines = []
        for i, group in enumerate(groups):
            members_1based = [m + 1 for m in group['members']]
            lines.append(
                f"Group {i}: {{members: {members_1based}, "
                f"rationale: \"{group['rationale']}\"}}"
            )
        return "\n".join(lines)


# ============================================================================
# 使用示例
# ============================================================================

def example_usage():
    """
    使用示例
    """
    # 模拟LLM client
    class MockLLMClient:
        def call_api(self, prompt):
            # 模拟LLM返回
            return json.dumps({
                'has_inconsistencies': True,
                'inconsistencies': [
                    {
                        'group_id': 2,
                        'issue': 'Rationale says merge but members are separate',
                        'action': 'merge',
                        'target_groups': [0]
                    }
                ]
            })
    
    # 测试数据
    groups = [
        {'members': [0, 1], 'representative': 0, 'rationale': '二者信息完全一致'},
        {'members': [2], 'representative': 2, 'rationale': '保持独立'},
        {'members': [3], 'representative': 3, 'rationale': '与第一组完全一致，可合并'}
    ]
    
    original_candidates = ['候选1', '候选2', '候选3', '候选4']
    
    # 执行验证和修正
    validator = SemanticDedupValidator(MockLLMClient())
    corrected_groups, report = validator.validate_and_correct(
        groups,
        original_candidates
    )
    
    print("=" * 60)
    print("原始groups:")
    for i, g in enumerate(groups):
        print(f"  Group {i}: members={g['members']}, rationale=\"{g['rationale']}\"")
    
    print("\n修正后:")
    for i, g in enumerate(corrected_groups):
        print(f"  Group {i}: members={g['members']}, rationale=\"{g['rationale']}\"")
    
    print("\n报告:")
    print(f"  不一致数量: {len(report['inconsistencies'])}")
    print(f"  修正成功: {report['corrected']}")
    print(f"  原始group数: {report.get('original_group_count')}")
    print(f"  修正后group数: {report.get('corrected_group_count')}")


if __name__ == '__main__':
    example_usage()
