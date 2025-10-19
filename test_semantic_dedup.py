#!/usr/bin/env python3
"""
Test script for semantic triple deduplication functionality.

This script demonstrates the semantic deduplication feature with example triples.
"""

import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.semantic_dedup import semantic_deduplicate_triples
from utils.logger import logger

def test_basic_deduplication():
    """Test basic semantic deduplication without graph context."""
    logger.info("="*50)
    logger.info("Test 1: Basic Semantic Deduplication")
    logger.info("="*50)
    
    # Example triples with semantic duplicates
    triples = [
        "[公司A, 完成融资, 2018年获得1000万美元投资]",
        "[公司A, 完成融资, 在2018年完成了1000万美元的融资]",
        "[公司A, 完成融资, 2018年1000万美元A轮融资]",
        "[公司A, 完成融资, 2019年获得2000万美元投资]",
        "[张三, 担任, CEO]",
        "[张三, 担任, 首席执行官]",
        "[张三, 担任, 总经理]",
        "[李四, 毕业于, 清华大学]",
        "[李四, 毕业于, 清华]",
    ]
    
    logger.info(f"Original triples ({len(triples)}):")
    for i, triple in enumerate(triples, 1):
        logger.info(f"  {i}. {triple}")
    
    # Perform semantic deduplication
    try:
        deduplicated = semantic_deduplicate_triples(
            triples=triples,
            similarity_threshold=0.7,
            batch_size=8,
            enable_llm_verification=True,
            use_chunk_context=False,  # No graph context in this test
            use_keywords=False
        )
        
        logger.info(f"\nDeduplicated triples ({len(deduplicated)}):")
        for i, triple in enumerate(deduplicated, 1):
            logger.info(f"  {i}. {triple}")
        
        logger.info(f"\nReduction: {len(triples)} -> {len(deduplicated)} ({len(triples) - len(deduplicated)} duplicates removed)")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_exact_duplicates():
    """Test that exact duplicates are also handled."""
    logger.info("\n" + "="*50)
    logger.info("Test 2: Exact + Semantic Deduplication")
    logger.info("="*50)
    
    triples = [
        "[公司A, 位于, 北京]",
        "[公司A, 位于, 北京]",  # Exact duplicate
        "[公司A, 位于, 北京市]",  # Semantic duplicate
        "[公司A, 位于, 北京市海淀区]",  # Different (more specific)
        "[公司B, 位于, 上海]",
        "[公司B, 位于, 上海市]",
    ]
    
    logger.info(f"Original triples ({len(triples)}):")
    for i, triple in enumerate(triples, 1):
        logger.info(f"  {i}. {triple}")
    
    try:
        deduplicated = semantic_deduplicate_triples(
            triples=triples,
            similarity_threshold=0.7,
            batch_size=5,
            enable_llm_verification=True,
            use_chunk_context=False,
            use_keywords=False
        )
        
        logger.info(f"\nDeduplicated triples ({len(deduplicated)}):")
        for i, triple in enumerate(deduplicated, 1):
            logger.info(f"  {i}. {triple}")
        
        logger.info(f"\nReduction: {len(triples)} -> {len(deduplicated)} ({len(triples) - len(deduplicated)} duplicates removed)")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_no_duplicates():
    """Test with triples that have no duplicates."""
    logger.info("\n" + "="*50)
    logger.info("Test 3: No Duplicates (Should Keep All)")
    logger.info("="*50)
    
    triples = [
        "[公司A, 成立于, 2010年]",
        "[公司B, 成立于, 2015年]",
        "[张三, 工作于, 公司A]",
        "[李四, 工作于, 公司B]",
        "[公司A, 主营业务, 互联网服务]",
    ]
    
    logger.info(f"Original triples ({len(triples)}):")
    for i, triple in enumerate(triples, 1):
        logger.info(f"  {i}. {triple}")
    
    try:
        deduplicated = semantic_deduplicate_triples(
            triples=triples,
            similarity_threshold=0.7,
            batch_size=5,
            enable_llm_verification=True,
            use_chunk_context=False,
            use_keywords=False
        )
        
        logger.info(f"\nDeduplicated triples ({len(deduplicated)}):")
        for i, triple in enumerate(deduplicated, 1):
            logger.info(f"  {i}. {triple}")
        
        if len(deduplicated) == len(triples):
            logger.info(f"\n✓ Correct: All {len(triples)} triples preserved (no duplicates)")
        else:
            logger.warning(f"\n✗ Unexpected: {len(triples) - len(deduplicated)} triples removed")
        
        return len(deduplicated) == len(triples)
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    logger.info("Starting Semantic Deduplication Tests")
    logger.info("="*50)
    
    tests = [
        ("Basic Semantic Deduplication", test_basic_deduplication),
        ("Exact + Semantic Deduplication", test_with_exact_duplicates),
        ("No Duplicates", test_no_duplicates),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("Test Summary")
    logger.info("="*50)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
