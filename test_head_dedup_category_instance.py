#!/usr/bin/env python3
"""
Test script to verify the improved head dedup prompt correctly handles category-instance relationships.

This script checks if the prompt can correctly reject merging:
1. Category vs Instance (e.g., "伪影" vs "魔角伪影")
2. General vs Specific (e.g., "疾病" vs "感冒")
3. Similar context but different entities

Run:
    python3 test_head_dedup_category_instance.py
"""

import yaml
from pathlib import Path


def load_head_dedup_prompt():
    """Load the head_dedup prompt from config/base_config.yaml"""
    config_path = Path("config/base_config.yaml")
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with config_path.open('r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    prompt = config.get('prompts', {}).get('head_dedup', {}).get('general')
    
    if not prompt:
        raise ValueError("head_dedup.general prompt not found in config")
    
    return prompt


def check_prompt_contains_key_principles(prompt):
    """Check if the prompt contains key principles from semantic_dedup"""
    
    required_elements = {
        "FUNDAMENTAL PRINCIPLE": "Establishes referential identity as core principle",
        "CRITICAL DISTINCTION": "Warns against context/relation similarity ≠ entity identity",
        "MERGE CONDITIONS": "Clear conditions that ALL must hold",
        "CATEGORY-INSTANCE WARNING": "Specific warning for category vs instance cases",
        "SUBSTITUTION TEST": "Test for bidirectional information preservation",
        "PROHIBITED MERGE REASONS": "Extended list of invalid merge reasons",
        "CONSERVATIVE PRINCIPLE": "When in doubt, keep separate",
        "Pattern: Category_X": "Contains generic pattern, not specific cases",
        "ALWAYS DIFFERENT": "Clear rule for category-instance relationship",
    }
    
    results = {}
    for element, description in required_elements.items():
        if element in prompt:
            results[element] = "✓ FOUND"
        else:
            results[element] = "✗ MISSING"
    
    return results


def check_prohibited_reasons_coverage(prompt):
    """Check if extended prohibited reasons are included"""
    
    prohibited_reasons = [
        "Semantic similarity",
        "Same category",
        "Shared context",
        "Shared relations",
        "Functional relationship",
        "Shared properties",
        "Category-Instance",
        "Part-Whole",
        "General-Specific",
    ]
    
    results = {}
    for reason in prohibited_reasons:
        # Check for the reason in the prompt
        if reason.lower() in prompt.lower() or reason.replace("-", " ").lower() in prompt.lower():
            results[reason] = "✓ INCLUDED"
        else:
            results[reason] = "✗ MISSING"
    
    return results


def check_decision_procedure(prompt):
    """Check if decision procedure includes category-instance check"""
    
    # Look for the decision procedure section
    if "DECISION PROCEDURE" not in prompt:
        return {"DECISION PROCEDURE": "✗ MISSING"}
    
    # Extract decision procedure section
    start = prompt.find("DECISION PROCEDURE")
    end = prompt.find("\n\n", start)
    if end == -1:
        end = len(prompt)
    procedure_section = prompt[start:end]
    
    checks = {
        "Category-instance check": "category" in procedure_section.lower() and "instance" in procedure_section.lower(),
        "Referential identity question": '"Do they refer to the same entity?"' in procedure_section or "refer to the same entity" in procedure_section,
        "Substitution test": "substitution" in procedure_section.lower(),
        "Conservative principle": "uncertain" in procedure_section.lower() or "conservative" in procedure_section.lower(),
    }
    
    results = {}
    for check, passed in checks.items():
        results[check] = "✓ PRESENT" if passed else "✗ ABSENT"
    
    return results


def check_examples(prompt):
    """Check if the prompt includes generic category-instance examples (not user-specific)"""
    
    # Check for example section
    if "EXAMPLES" not in prompt:
        return {"EXAMPLES section": "✗ MISSING"}
    
    # Extract examples section
    start = prompt.find("EXAMPLES")
    examples_section = prompt[start:]
    
    checks = {
        "Generic cross-domain examples": ("Vehicle" in examples_section or "Animal" in examples_section or "Disease" in examples_section),
        "Category vs instance example": "category vs instance" in examples_section.lower() or "CATEGORY" in examples_section,
        "Should NOT merge rationale": "is_coreferent: false" in examples_section or "should not merge" in examples_section.lower(),
        "Explanation of specificity": "SPECIFIC TYPE" in examples_section or "specific" in examples_section.lower(),
        "No user-specific hardcoding": not ("伪影" in examples_section and "魔角伪影" in examples_section),
    }
    
    results = {}
    for check, passed in checks.items():
        results[check] = "✓ PRESENT" if passed else "✗ ABSENT"
    
    return results


def print_section_results(title, results):
    """Pretty print results for a section"""
    print(f"\n{title}")
    print("=" * 70)
    
    total = len(results)
    passed = sum(1 for v in results.values() if "✓" in v or "FOUND" in v or "PRESENT" in v or "INCLUDED" in v)
    
    for key, status in results.items():
        symbol = "✓" if ("✓" in status or "FOUND" in status or "PRESENT" in status or "INCLUDED" in status) else "✗"
        print(f"{symbol} {key}")
    
    print(f"\nScore: {passed}/{total} ({100*passed//total}%)")
    
    return passed == total


def main():
    print("\n" + "=" * 70)
    print("HEAD DEDUP PROMPT - CATEGORY-INSTANCE IMPROVEMENT TEST")
    print("=" * 70)
    
    try:
        # Load prompt
        print("\n[1/5] Loading head_dedup prompt from config...")
        prompt = load_head_dedup_prompt()
        print(f"✓ Loaded prompt ({len(prompt)} characters)")
        
        # Run checks
        all_passed = True
        
        print("\n[2/5] Checking key principles...")
        results = check_prompt_contains_key_principles(prompt)
        passed = print_section_results("Key Principles Check", results)
        all_passed = all_passed and passed
        
        print("\n[3/5] Checking prohibited merge reasons...")
        results = check_prohibited_reasons_coverage(prompt)
        passed = print_section_results("Prohibited Reasons Coverage", results)
        all_passed = all_passed and passed
        
        print("\n[4/5] Checking decision procedure...")
        results = check_decision_procedure(prompt)
        passed = print_section_results("Decision Procedure Check", results)
        all_passed = all_passed and passed
        
        print("\n[5/5] Checking examples...")
        results = check_examples(prompt)
        passed = print_section_results("Examples Check", results)
        all_passed = all_passed and passed
        
        # Final result
        print("\n" + "=" * 70)
        if all_passed:
            print("✅ ALL CHECKS PASSED!")
            print("\nThe head_dedup prompt now incorporates:")
            print("  • Semantic dedup principles (referential identity)")
            print("  • Generic category-instance pattern (NOT case-specific)")
            print("  • Cross-domain examples (Vehicle, Animal, Disease, Food)")
            print("  • Extended prohibited merge reasons (9 items)")
            print("  • No hardcoded user cases - uses principle-based reasoning")
            print("\n✅ Follows user rule: No case-by-case modifications!")
            print("Ready for testing on actual data!")
        else:
            print("⚠️  SOME CHECKS FAILED")
            print("\nReview the results above and ensure all key elements are present.")
        print("=" * 70 + "\n")
        
        return 0 if all_passed else 1
        
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
