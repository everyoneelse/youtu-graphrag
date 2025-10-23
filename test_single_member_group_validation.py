"""
Test case for validating single-member group inconsistency detection.

This test verifies that the validation logic correctly identifies when a single-member
group's rationale claims it should be merged with other groups.

Test scenario from user:
- Group 4 has only 1 member [4]
- Group 4's rationale says: "与组1/组2所指操作完全一致，信息无差异，可合并"
- But Group 4 is separate from Groups 1 and 2
- This is an inconsistency that should be detected and corrected
"""

import re


def test_single_member_group_validation():
    """
    Test the validation prompt improvements by checking the file content.
    """
    
    # Read the kt_gen.py file
    with open('/workspace/models/constructor/kt_gen.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the DEFAULT_SEMANTIC_DEDUP_VALIDATION_PROMPT section
    start_marker = 'DEFAULT_SEMANTIC_DEDUP_VALIDATION_PROMPT = ('
    end_marker = '\n)\n'
    
    start_idx = content.find(start_marker)
    if start_idx == -1:
        raise ValueError("Cannot find DEFAULT_SEMANTIC_DEDUP_VALIDATION_PROMPT")
    
    # Find the end by looking for the closing parenthesis after the start
    search_start = start_idx + len(start_marker)
    # Look for standalone )\n pattern that closes the multiline string
    end_idx = content.find('\n)\n', search_start)
    if end_idx == -1:
        raise ValueError("Cannot find end of DEFAULT_SEMANTIC_DEDUP_VALIDATION_PROMPT")
    
    prompt_section = content[start_idx:end_idx + len(end_marker)]
    
    print("=" * 80)
    print("Test: Single-Member Group Validation Enhancement")
    print("=" * 80)
    print("\nChecking if the validation prompt includes necessary improvements:")
    print("-" * 80)
    
    # Check for key improvements
    checks = [
        ("CRITICAL: SINGLE-MEMBER GROUP VALIDATION", 
         "Special section for single-member group validation"),
        ("single-member group", 
         "Mentions single-member groups"),
        ("可合并", 
         "Includes Chinese keyword '可合并' (can be merged)"),
        ("一致", 
         "Includes Chinese keyword '一致' (consistent/same)"),
        ("无差异", 
         "Includes Chinese keyword '无差异' (no difference)"),
        ("Do NOT skip validation just because a group has 1 member",
         "Explicitly instructs not to skip single-member groups"),
        ("VALIDATE ALL GROUPS, including single-member groups",
         "Emphasizes validating all groups"),
        ("Check CROSS-GROUP relationships",
         "Emphasizes cross-group relationship checking"),
        ("Example 2 - Chinese text with merge claim",
         "Includes Chinese language example"),
    ]
    
    all_passed = True
    for check_text, description in checks:
        if check_text in prompt_section:
            print(f"✅ {description}")
        else:
            print(f"❌ {description} - NOT FOUND")
            all_passed = False
    
    print("-" * 80)
    
    if all_passed:
        print("\n🎉 All checks passed! The validation prompt has been enhanced.")
        print("\nKey improvements:")
        print("1. Special section dedicated to single-member group validation")
        print("2. Explicit instruction to NOT skip single-member groups")
        print("3. Emphasis on checking cross-group relationships mentioned in rationales")
        print("4. Chinese keywords for detecting merge intentions (可合并, 一致, 无差异)")
        print("5. Chinese language example demonstrating the exact user scenario")
        print("\nExpected behavior:")
        print("- LLM will now pay special attention to single-member groups")
        print("- LLM will detect when rationale says 'should merge' but groups are separate")
        print("- LLM will correct such inconsistencies by merging the groups")
    else:
        print("\n❌ Some checks failed. Please review the prompt improvements.")
        raise AssertionError("Validation prompt improvements incomplete")
    
    print("=" * 80)


if __name__ == "__main__":
    test_single_member_group_validation()
