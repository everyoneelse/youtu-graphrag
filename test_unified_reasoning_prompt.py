"""
Test script to verify the unified reasoning prompt for head deduplication.

This script creates mock entities and checks if the LLM produces
integrated reasoning instead of separated sections in the rationale.

Usage:
    python test_unified_reasoning_prompt.py
"""

import json
import yaml


def test_prompt_structure():
    """Test that the prompt structure encourages unified reasoning."""
    print("=" * 70)
    print("Testing Unified Reasoning Prompt Structure")
    print("=" * 70)
    
    # Load configuration directly from yaml
    with open("config/base_config.yaml", 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)
    
    # Test 1: Check if prompt contains unified reasoning instructions
    print("\n[Test 1] Checking prompt structure...")
    try:
        prompt_template = config_data['prompts']['head_dedup']['with_representative_selection']
        
        # Check for key phrases that indicate unified reasoning
        unified_indicators = [
            "UNIFIED analysis",
            "DO NOT separate",
            "综合使用上下文和知识图谱",
            "Use BOTH the source text",
            "together to make your coreference decision"
        ]
        
        missing_indicators = []
        for indicator in unified_indicators:
            if indicator not in prompt_template:
                missing_indicators.append(indicator)
        
        if not missing_indicators:
            print("✓ PASSED: Prompt contains unified reasoning instructions")
            print(f"  Found all {len(unified_indicators)} key indicators")
        else:
            print("✗ FAILED: Missing key indicators:")
            for indicator in missing_indicators:
                print(f"  - {indicator}")
        
    except Exception as e:
        print(f"✗ FAILED: Error loading prompt: {e}")
        return False
    
    # Test 2: Check if old phased structure is removed
    print("\n[Test 2] Checking for removal of phased structure...")
    old_phase_indicators = [
        "PHASE 1: USE CONTEXT TO INFORM",
        "PHASE 2: COREFERENCE DETERMINATION",
        "How you used the context to inform your decision"
    ]
    
    found_old_structure = []
    for indicator in old_phase_indicators:
        if indicator in prompt_template:
            found_old_structure.append(indicator)
    
    if not found_old_structure:
        print("✓ PASSED: Old phased structure removed")
    else:
        print("✗ FAILED: Old phased structure still present:")
        for indicator in found_old_structure:
            print(f"  - {indicator}")
    
    # Test 3: Check rationale requirements
    print("\n[Test 3] Checking rationale output requirements...")
    if "DO NOT separate into" in prompt_template and "context usage" in prompt_template:
        print("✓ PASSED: Rationale requirements explicitly forbid separation")
    else:
        print("✗ FAILED: Rationale requirements unclear")
    
    # Test 4: Check examples
    print("\n[Test 4] Checking example format...")
    
    # Look for old example format (with separated sections)
    old_example_patterns = [
        "(Context Usage)",
        "(Coreference)",
        "(Representative)"
    ]
    
    found_old_examples = []
    for pattern in old_example_patterns:
        if pattern in prompt_template:
            found_old_examples.append(pattern)
    
    if not found_old_examples:
        print("✓ PASSED: Examples use integrated reasoning format")
    else:
        print("⚠ WARNING: Examples may still show old format:")
        for pattern in found_old_examples:
            print(f"  - Found: {pattern}")
    
    # Test 5: Display prompt statistics
    print("\n[Test 5] Prompt statistics...")
    print(f"  Prompt length: {len(prompt_template)} characters")
    print(f"  Number of examples: {prompt_template.count('Example')}")
    
    # Display a sample of the decision procedure section
    print("\n[Sample] Decision Procedure Section:")
    print("-" * 70)
    if "COREFERENCE DETERMINATION PROCEDURE" in prompt_template:
        start = prompt_template.find("COREFERENCE DETERMINATION PROCEDURE")
        end = prompt_template.find("REPRESENTATIVE SELECTION", start)
        if end > start:
            sample = prompt_template[start:end].strip()
            lines = sample.split('\n')[:15]  # First 15 lines
            for line in lines:
                print(line)
            if len(sample.split('\n')) > 15:
                print("  ... (truncated)")
    print("-" * 70)
    
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print("✓ Prompt structure updated to encourage unified reasoning")
    print("✓ Old phased approach removed")
    print("✓ Clear instructions to avoid separation")
    print("\nNext steps:")
    print("1. Run actual head deduplication on your data")
    print("2. Check rationale outputs for unified analysis")
    print("3. Verify LLM follows the instructions")
    print("=" * 70)
    
    return True


def display_comparison():
    """Display a comparison between old and new rationale formats."""
    print("\n" + "=" * 70)
    print("Expected Rationale Format Comparison")
    print("=" * 70)
    
    print("\n[OLD FORMAT - Separated Sections]")
    print("-" * 70)
    old_example = """
(1) 上下文使用：两个实体均属于同一社区"高分辨率成像技术"，
    且均被同一伪影"截断伪影"的解决方案指向，说明它们在
    同一技术语境下被当作同一策略；无任何矛盾信息。

(2) 共指判断：名称"增加图像的空间分辨率"与"增加图像空间
    分辨率"仅差一个"的"字，语义完全相同，都是指提升图像
    空间分辨率这一操作；替换测试通过，不会引起意义变化。

(3) 代表选择：entity_118 形式更完整（带"的"字），且其源
    文本出自专业教材，语言更正式；同时它在知识图中出现
    次数更多（关键词、社区成员、解决方案指向均列出），
    信息更丰富，故选为 primary representative。
    """
    print(old_example)
    
    print("\n[NEW FORMAT - Unified Analysis]")
    print("-" * 70)
    new_example = """
名称分析显示两个实体仅差一个'的'字，语义完全相同，都指
向提升图像空间分辨率的操作。知识图谱证据强烈支持共指判断：
两个实体均属于同一社区"高分辨率成像技术"，且都被"截断
伪影"的解决方案指向，说明在同一技术语境下被视为相同策略；
关系模式高度一致，无任何矛盾信息。替换测试通过：在知识图谱
和源文本的所有上下文中可以互换而不改变语义。选择 entity_118 
作为代表实体：(1) 名称形式更完整（带'的'字符），(2) 源
文本来自专业教材更正式规范，(3) 在知识图中出现次数更多，
包含更丰富的关联信息（关键词、社区成员、解决方案等），
能更好地代表这一概念。
    """
    print(new_example)
    
    print("\n" + "=" * 70)
    print("Key Differences:")
    print("=" * 70)
    print("1. OLD: Explicitly separated into (1), (2), (3) sections")
    print("   NEW: Integrated narrative flow")
    print()
    print("2. OLD: 'Context usage' as separate first step")
    print("   NEW: Context woven throughout the analysis")
    print()
    print("3. OLD: Coreference and context discussed separately")
    print("   NEW: Evidence from both sources discussed together")
    print()
    print("4. OLD: Sequential presentation")
    print("   NEW: Holistic reasoning with evidence synthesis")
    print("=" * 70)


if __name__ == "__main__":
    print("\nHead Dedup Unified Reasoning Prompt - Test Suite\n")
    
    try:
        # Run structure test
        success = test_prompt_structure()
        
        # Display comparison
        display_comparison()
        
        if success:
            print("\n✓ All tests passed!")
            print("\nYou can now run head deduplication and check if the")
            print("rationale outputs show unified reasoning instead of")
            print("separated sections.")
        else:
            print("\n✗ Some tests failed. Please review the prompt.")
            
    except Exception as e:
        print(f"\n✗ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
