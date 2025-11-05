"""
DSPy Validation演示脚本

演示如何使用DSPy进行semantic dedup的质量验证和自动修正。

运行前提：
1. pip install dspy-ai
2. export OPENAI_API_KEY=your_key

运行方法：
    python example_dspy_validation_demo.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    import dspy
    from models.constructor.dspy_semantic_dedup import (
        SemanticDedupModule,
        DedupValidationModule,
        DedupCorrectionModule,
        MultiStageDedupPipeline
    )
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("\n请确保:")
    print("1. 已安装 dspy-ai: pip install dspy-ai")
    print("2. 在项目根目录运行此脚本")
    sys.exit(1)


def setup():
    """设置DSPy环境"""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ 错误: 未找到 OPENAI_API_KEY 环境变量")
        print("\n请设置 API key:")
        print("  export OPENAI_API_KEY=your_key")
        sys.exit(1)
    
    print("🔧 配置 DSPy...")
    lm = dspy.OpenAI(model="gpt-3.5-turbo", api_key=api_key, max_tokens=2500)
    dspy.settings.configure(lm=lm)
    print("✓ DSPy 配置完成\n")


def demo_validation_good_case():
    """
    演示1: 验证一个高质量的去重结果
    
    这个case的去重结果是正确的，validation应该给出高分。
    """
    print("="*80)
    print("演示 1: 验证高质量的去重结果")
    print("="*80)
    
    # 1. 先进行去重
    dedup_module = SemanticDedupModule()
    
    tails = [
        "Barack Obama",
        "Obama",
        "Barack H. Obama",
        "Donald Trump",
        "Trump"
    ]
    
    print(f"\nOriginal Tails: {len(tails)}")
    for i, tail in enumerate(tails, 1):
        print(f"  [{i}] {tail}")
    
    batch_entries = [
        {
            "description": tail,
            "context_summaries": [
                f"- {tail} served as President of the United States"
            ]
        }
        for tail in tails
    ]
    
    print("\n🤖 执行去重...")
    groups, reasoning = dedup_module(
        head_entity="United States",
        relation="president",
        head_contexts=["- United States has had multiple presidents"],
        batch_entries=batch_entries
    )
    
    print(f"\n✓ 去重完成！{len(groups)} 个group:")
    for i, group in enumerate(groups, 1):
        members = [tails[idx-1] for idx in group['members']]
        rep = tails[group['representative']-1]
        print(f"\n  Group {i}:")
        print(f"    Members: {members}")
        print(f"    Representative: {rep}")
        print(f"    Rationale: {group['rationale'][:80]}...")
    
    # 2. 验证去重结果
    print("\n" + "="*80)
    print("开始验证去重质量...")
    print("="*80)
    
    validation_module = DedupValidationModule()
    
    contexts = [
        ["- Barack Obama was the 44th President"],
        ["- Obama served from 2009-2017"],
        ["- Barack H. Obama was born in Hawaii"],
        ["- Donald Trump was the 45th President"],
        ["- Trump served from 2017-2021"]
    ]
    
    validation_result = validation_module(
        head_entity="United States",
        relation="president",
        original_tails=tails,
        dedup_groups=groups,
        contexts=contexts
    )
    
    print(f"\n✓ 验证完成！")
    print(f"\n📊 验证结果:")
    print(f"  Overall Quality: {validation_result['overall_quality']:.2f}")
    print(f"  Issues Found: {len(validation_result['issues'])}")
    
    if validation_result['analysis']:
        print(f"\n💭 分析:")
        analysis = validation_result['analysis']
        print(f"  {analysis[:200]}..." if len(analysis) > 200 else f"  {analysis}")
    
    if validation_result['issues']:
        print(f"\n⚠️  发现的问题:")
        for issue in validation_result['issues']:
            print(f"\n  Issue Type: {issue['type']}")
            print(f"    Severity: {issue['severity']}")
            print(f"    Description: {issue['description']}")
            print(f"    Suggestion: {issue['suggestion']}")
    else:
        print(f"\n✅ 没有发现问题 - 去重质量良好！")


def demo_validation_bad_case():
    """
    演示2: 验证一个有问题的去重结果
    
    这个case故意创建一个错误的去重结果，validation应该检测出问题。
    """
    print("\n\n" + "="*80)
    print("演示 2: 验证有问题的去重结果")
    print("="*80)
    
    tails = [
        "iPhone 13",
        "iPhone 14",
        "iPhone 15",
        "iPad"
    ]
    
    print(f"\nOriginal Tails: {len(tails)}")
    for i, tail in enumerate(tails, 1):
        print(f"  [{i}] {tail}")
    
    # 故意创建一个错误的去重结果：把所有产品都合并了
    wrong_groups = [
        {
            "members": [1, 2, 3, 4],
            "representative": 1,
            "rationale": "All are Apple products"  # 错误的reasoning
        }
    ]
    
    print(f"\n⚠️  错误的去重结果（故意制造）:")
    for i, group in enumerate(wrong_groups, 1):
        members = [tails[idx-1] for idx in group['members']]
        print(f"  Group {i}: {members}")
        print(f"  (错误: 不同产品被错误地合并在一起！)")
    
    # 验证这个错误的结果
    print("\n" + "="*80)
    print("开始验证...")
    print("="*80)
    
    validation_module = DedupValidationModule()
    
    contexts = [
        ["- iPhone 13 is a smartphone released in 2021"],
        ["- iPhone 14 is a smartphone released in 2022"],
        ["- iPhone 15 is a smartphone released in 2023"],
        ["- iPad is a tablet computer"]
    ]
    
    validation_result = validation_module(
        head_entity="Apple Inc.",
        relation="product",
        original_tails=tails,
        dedup_groups=wrong_groups,
        contexts=contexts
    )
    
    print(f"\n✓ 验证完成！")
    print(f"\n📊 验证结果:")
    print(f"  Overall Quality: {validation_result['overall_quality']:.2f} ⚠️  (低分!)")
    print(f"  Issues Found: {len(validation_result['issues'])}")
    
    if validation_result['issues']:
        print(f"\n⚠️  检测到的问题:")
        for i, issue in enumerate(validation_result['issues'], 1):
            print(f"\n  Issue {i}:")
            print(f"    Type: {issue['type']}")
            print(f"    Severity: {issue['severity']}")
            print(f"    Description: {issue['description']}")
            print(f"    Suggestion: {issue['suggestion']}")


def demo_auto_correction():
    """
    演示3: 自动修正错误的去重结果
    
    使用DedupCorrectionModule自动修正validation发现的问题。
    """
    print("\n\n" + "="*80)
    print("演示 3: 自动修正错误的去重结果")
    print("="*80)
    
    tails = [
        "New York City",
        "NYC",
        "Los Angeles",
        "LA",
        "San Francisco"
    ]
    
    print(f"\nOriginal Tails: {len(tails)}")
    for i, tail in enumerate(tails, 1):
        print(f"  [{i}] {tail}")
    
    # 创建一个部分正确但有问题的去重结果
    problematic_groups = [
        {
            "members": [1, 2, 3],  # 错误: NYC和LA被合并了
            "representative": 1,
            "rationale": "Major US cities"
        },
        {
            "members": [4],
            "representative": 4,
            "rationale": "Different city"
        },
        {
            "members": [5],
            "representative": 5,
            "rationale": "West coast city"
        }
    ]
    
    print(f"\n⚠️  有问题的去重结果:")
    for i, group in enumerate(problematic_groups, 1):
        members = [tails[idx-1] for idx in group['members']]
        print(f"  Group {i}: {members}")
    
    # Step 1: Validation
    print("\n" + "="*80)
    print("Step 1: 验证去重质量...")
    print("="*80)
    
    validation_module = DedupValidationModule()
    
    contexts = [
        ["- New York City is on the East Coast"],
        ["- NYC is the most populous city in the US"],
        ["- Los Angeles is on the West Coast"],
        ["- LA is the second largest city"],
        ["- San Francisco is in California"]
    ]
    
    validation_result = validation_module(
        head_entity="United States",
        relation="has_city",
        original_tails=tails,
        dedup_groups=problematic_groups,
        contexts=contexts
    )
    
    quality = validation_result['overall_quality']
    issues = validation_result['issues']
    
    print(f"\n  Quality Score: {quality:.2f}")
    print(f"  Issues: {len(issues)}")
    
    for issue in issues:
        print(f"    - {issue['type']}: {issue['description'][:60]}...")
    
    # Step 2: Correction
    if quality < 0.7 and issues:
        print("\n" + "="*80)
        print(f"Step 2: 自动修正 (quality {quality:.2f} < 0.7)...")
        print("="*80)
        
        correction_module = DedupCorrectionModule()
        
        corrected_groups, reasoning = correction_module(
            head_entity="United States",
            relation="has_city",
            original_tails=tails,
            current_groups=problematic_groups,
            validation_issues=issues,
            contexts=contexts
        )
        
        print(f"\n✓ 修正完成！")
        print(f"\n📊 修正后的分组:")
        for i, group in enumerate(corrected_groups, 1):
            members = [tails[idx-1] for idx in group['members']]
            rep = tails[group['representative']-1]
            print(f"\n  Group {i}:")
            print(f"    Members: {members}")
            print(f"    Representative: {rep}")
            print(f"    Rationale: {group.get('rationale', 'N/A')[:80]}...")
        
        if reasoning:
            print(f"\n💭 修正reasoning:")
            print(f"  {reasoning[:300]}..." if len(reasoning) > 300 else f"  {reasoning}")


def demo_full_pipeline():
    """
    演示4: 完整的多阶段pipeline
    
    使用MultiStageDedupPipeline执行 Clustering → Dedup → Validation → Correction
    """
    print("\n\n" + "="*80)
    print("演示 4: 完整的多阶段Pipeline")
    print("="*80)
    
    tails = [
        "United States",
        "USA",
        "US",
        "United Kingdom",
        "UK",
        "Britain"
    ]
    
    print(f"\nInput: {len(tails)} country names")
    for i, tail in enumerate(tails, 1):
        print(f"  [{i}] {tail}")
    
    contexts = [
        ["- United States is in North America"],
        ["- USA is a federal republic"],
        ["- US has 50 states"],
        ["- United Kingdom is in Europe"],
        ["- UK consists of England, Scotland, Wales, N. Ireland"],
        ["- Britain is a sovereign state"]
    ]
    
    print("\n" + "="*80)
    print("执行完整Pipeline...")
    print("="*80)
    
    # 创建pipeline with validation and correction
    pipeline = MultiStageDedupPipeline(
        enable_validation=True,
        enable_correction=True,
        validation_threshold=0.7
    )
    
    try:
        result = pipeline(
            head_entity="United Nations",
            relation="member_country",
            tail_descriptions=tails,
            contexts=contexts
        )
        
        print(f"\n✓ Pipeline完成！")
        print(f"\n📊 Pipeline结果:")
        print(f"  Stage 1 - Clusters: {len(result['clusters'])}")
        print(f"  Stage 2 - Initial Groups: {len(result['initial_groups'])}")
        
        if result['validation']:
            print(f"  Stage 3 - Validation Quality: {result['validation']['overall_quality']:.2f}")
            print(f"  Stage 3 - Issues Found: {len(result['validation']['issues'])}")
        
        print(f"  Stage 4 - Corrections Applied: {result['corrections_applied']}")
        print(f"  Final Groups: {len(result['final_groups'])}")
        
        print(f"\n📋 最终分组:")
        for i, group in enumerate(result['final_groups'], 1):
            members = [tails[idx-1] for idx in group['members']]
            rep = tails[group['representative']-1] if 'representative' in group else members[0]
            print(f"\n  Group {i}:")
            print(f"    Members: {members}")
            print(f"    Representative: {rep}")
    
    except Exception as e:
        print(f"\n❌ Pipeline失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    print("\n" + "="*80)
    print("DSPy Validation & Correction 演示")
    print("="*80)
    print("\n这个脚本演示如何使用DSPy进行semantic dedup的质量验证和自动修正")
    print("包括: validation, correction, multi-stage pipeline\n")
    
    # 设置环境
    setup()
    
    # 运行演示
    try:
        demo_validation_good_case()
        demo_validation_bad_case()
        demo_auto_correction()
        demo_full_pipeline()
        
        print("\n" + "="*80)
        print("✅ 所有演示完成！")
        print("="*80)
        
        print("\n📚 了解更多:")
        print("  - 详细文档: DSPY_VALIDATION_DESIGN.md")
        print("  - 代码实现: models/constructor/dspy_semantic_dedup.py")
        print("  - 集成指南: 查看文档中的集成章节")
        
        print("\n💡 下一步:")
        print("  1. 训练validation模块（可选）")
        print("  2. 在config中启用validation")
        print("  3. 在生产环境测试效果")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  演示被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 演示过程中出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
