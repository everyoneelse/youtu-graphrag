"""
DSPy Semantic Dedup 演示脚本

这个脚本演示如何使用DSPy优化semantic deduplication。

运行前提：
1. pip install dspy-ai
2. export OPENAI_API_KEY=your_key

运行方法：
    python example_dspy_demo.py
"""

import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import dspy
    from models.constructor.dspy_semantic_dedup import (
        SemanticClusteringModule,
        SemanticDedupModule,
        DSPySemanticDedupOptimizer,
        clustering_metric,
        dedup_metric
    )
    from scripts.prepare_dspy_training_data import create_synthetic_training_examples
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
    lm = dspy.OpenAI(model="gpt-3.5-turbo", api_key=api_key, max_tokens=2000)
    dspy.settings.configure(lm=lm)
    print("✓ DSPy 配置完成\n")


def demo_clustering():
    """演示聚类功能"""
    print("="*80)
    print("示例 1: LLM-based Clustering")
    print("="*80)
    
    # 创建聚类模块
    clustering = SemanticClusteringModule(use_cot=True)
    
    # 测试数据
    head_entity = "United States"
    relation = "president"
    tails = [
        "Barack Obama",
        "Obama",
        "Barack H. Obama",
        "Donald Trump",
        "Trump",
        "Donald J. Trump"
    ]
    
    print(f"\nHead Entity: {head_entity}")
    print(f"Relation: {relation}")
    print(f"\nTail Candidates:")
    for i, tail in enumerate(tails, 1):
        print(f"  [{i}] {tail}")
    
    print("\n🤖 调用 LLM 进行聚类...")
    
    try:
        clusters = clustering(
            head_entity=head_entity,
            relation=relation,
            tail_descriptions=tails
        )
        
        print(f"\n✓ 聚类完成！共 {len(clusters)} 个cluster:")
        for i, cluster in enumerate(clusters, 1):
            members = cluster.get('members', [])
            description = cluster.get('description', 'No description')
            
            print(f"\n  Cluster {i}:")
            print(f"    Members: {[tails[m-1] for m in members]}")
            print(f"    Rationale: {description}")
    
    except Exception as e:
        print(f"\n❌ 聚类失败: {e}")
        import traceback
        traceback.print_exc()


def demo_dedup():
    """演示去重功能"""
    print("\n" + "="*80)
    print("示例 2: Semantic Deduplication (Coreference Resolution)")
    print("="*80)
    
    # 创建去重模块
    dedup = SemanticDedupModule(prompt_type="general", use_cot=True)
    
    # 测试数据
    head_entity = "Star Wars film series"
    relation = "director"
    tails = [
        "George Lucas",
        "G. Lucas",
        "George Walton Lucas Jr.",
        "J.J. Abrams",
        "Jeffrey Jacob Abrams"
    ]
    
    print(f"\nHead Entity: {head_entity}")
    print(f"Relation: {relation}")
    print(f"\nTail Candidates:")
    for i, tail in enumerate(tails, 1):
        print(f"  [{i}] {tail}")
    
    # 准备batch entries
    batch_entries = [
        {
            "description": tail,
            "context_summaries": [
                f"- {tail} is mentioned as a director of Star Wars films"
            ]
        }
        for tail in tails
    ]
    
    head_contexts = [
        "- Star Wars is a film series with multiple directors",
        "- Different directors worked on different films in the series"
    ]
    
    print("\n🤖 调用 LLM 进行去重...")
    
    try:
        groups, reasoning = dedup(
            head_entity=head_entity,
            relation=relation,
            head_contexts=head_contexts,
            batch_entries=batch_entries
        )
        
        print(f"\n✓ 去重完成！共 {len(groups)} 个group:")
        
        # 显示推理过程
        if reasoning:
            print(f"\n💭 LLM Reasoning:")
            print(f"  {reasoning[:300]}..." if len(reasoning) > 300 else f"  {reasoning}")
        
        # 显示分组结果
        for i, group in enumerate(groups, 1):
            members = group.get('members', [])
            representative = group.get('representative', members[0] if members else 1)
            rationale = group.get('rationale', 'No rationale')
            
            print(f"\n  Group {i}:")
            print(f"    Members: {[tails[m-1] for m in members]}")
            print(f"    Representative: {tails[representative-1]}")
            print(f"    Rationale: {rationale}")
    
    except Exception as e:
        print(f"\n❌ 去重失败: {e}")
        import traceback
        traceback.print_exc()


def demo_optimization():
    """演示优化过程（简化版）"""
    print("\n" + "="*80)
    print("示例 3: DSPy Optimization (使用合成数据)")
    print("="*80)
    
    print("\n📊 创建训练样本...")
    examples = create_synthetic_training_examples()
    print(f"✓ 创建了 {len(examples)} 个训练样本")
    
    # 分割训练集和验证集
    split_idx = int(len(examples) * 0.7)
    train_examples = examples[:split_idx]
    val_examples = examples[split_idx:]
    
    print(f"  训练集: {len(train_examples)} 个样本")
    print(f"  验证集: {len(val_examples)} 个样本")
    
    # 评估baseline
    print("\n📈 评估 Baseline 性能...")
    baseline_clustering = SemanticClusteringModule(use_cot=True)
    
    baseline_scores = []
    for ex in val_examples[:2]:  # 只评估前2个样本（演示用）
        try:
            pred = baseline_clustering(
                head_entity=ex.head_entity,
                relation=ex.relation,
                tail_descriptions=ex.tail_descriptions
            )
            score = clustering_metric(ex, pred)
            baseline_scores.append(score)
            print(f"  Example: {ex.head_entity} - {ex.relation}")
            print(f"    Score: {score:.2f}")
        except Exception as e:
            print(f"  ❌ 评估失败: {e}")
    
    avg_baseline = sum(baseline_scores) / len(baseline_scores) if baseline_scores else 0
    print(f"\n  Baseline 平均分数: {avg_baseline:.2f}")
    
    print("\n💡 提示:")
    print("  要进行完整的优化训练，运行:")
    print("  python scripts/train_dspy_modules.py --train-all --use-synthetic")
    print("\n  优化过程会:")
    print("  1. 使用 GPT-4 作为 teacher 生成高质量示例")
    print("  2. 训练 GPT-3.5-turbo 学习这些示例")
    print("  3. 在验证集上评估提升效果")
    print("  4. 保存优化后的模块供生产使用")


def demo_cost_comparison():
    """演示成本对比"""
    print("\n" + "="*80)
    print("示例 4: 成本对比分析")
    print("="*80)
    
    # 假设的成本数据（美元/1k tokens）
    costs = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002}
    }
    
    # 估算一次去重任务的token使用
    num_tails = 100
    clustering_calls = num_tails // 30  # 每30个tails一次clustering call
    dedup_calls = num_tails // 8  # 每8个tails一次dedup call
    
    avg_tokens_per_call = 1500  # 假设每次调用平均1500 tokens
    
    print(f"\n假设场景: 去重 {num_tails} 个 tail entities")
    print(f"  Clustering 调用次数: ~{clustering_calls}")
    print(f"  Deduplication 调用次数: ~{dedup_calls}")
    print(f"  每次调用平均 tokens: ~{avg_tokens_per_call}")
    
    total_calls = clustering_calls + dedup_calls
    total_tokens = total_calls * avg_tokens_per_call / 1000  # Convert to k tokens
    
    # 计算不同方案的成本
    scenarios = {
        "GPT-4 原始prompt": {
            "model": "gpt-4",
            "description": "使用GPT-4和手工优化的prompt"
        },
        "GPT-4 DSPy优化": {
            "model": "gpt-4", 
            "description": "使用GPT-4和DSPy优化的prompt（更高效）",
            "efficiency": 0.9  # DSPy优化后tokens减少10%
        },
        "GPT-3.5 DSPy优化": {
            "model": "gpt-3.5-turbo",
            "description": "使用GPT-3.5-turbo和DSPy优化（推荐）",
            "efficiency": 1.0
        }
    }
    
    print("\n" + "-"*80)
    print("成本对比:")
    print("-"*80)
    
    for scenario_name, config in scenarios.items():
        model = config["model"]
        efficiency = config.get("efficiency", 1.0)
        adjusted_tokens = total_tokens * efficiency
        
        # 简化计算：假设input和output各占50%
        cost = (adjusted_tokens * costs[model]["input"] * 0.5 + 
                adjusted_tokens * costs[model]["output"] * 0.5)
        
        print(f"\n{scenario_name}:")
        print(f"  模型: {model}")
        print(f"  描述: {config['description']}")
        print(f"  Token使用: {adjusted_tokens:.1f}k tokens")
        print(f"  估算成本: ${cost:.2f}")
    
    # 计算节省
    baseline_cost = (total_tokens * costs["gpt-4"]["input"] * 0.5 + 
                    total_tokens * costs["gpt-4"]["output"] * 0.5)
    optimized_cost = (total_tokens * costs["gpt-3.5-turbo"]["input"] * 0.5 + 
                     total_tokens * costs["gpt-3.5-turbo"]["output"] * 0.5)
    savings = baseline_cost - optimized_cost
    savings_pct = (savings / baseline_cost) * 100
    
    print("\n" + "-"*80)
    print(f"💰 使用 DSPy + GPT-3.5-turbo 可节省:")
    print(f"  绝对节省: ${savings:.2f}")
    print(f"  相对节省: {savings_pct:.1f}%")
    print("-"*80)
    
    print("\n📝 注意:")
    print("  - 以上是估算值，实际成本取决于具体使用情况")
    print("  - DSPy优化后，GPT-3.5-turbo 可以达到接近GPT-4的质量")
    print("  - 长期来看，成本节省非常可观")


def main():
    """主函数"""
    print("\n" + "="*80)
    print("DSPy Semantic Dedup 演示")
    print("="*80)
    print("\n这个脚本演示如何使用DSPy优化semantic deduplication")
    print("包括: clustering, deduplication, optimization, cost analysis\n")
    
    # 设置环境
    setup()
    
    # 运行演示
    try:
        demo_clustering()
        demo_dedup()
        demo_optimization()
        demo_cost_comparison()
        
        print("\n" + "="*80)
        print("✅ 演示完成！")
        print("="*80)
        
        print("\n下一步:")
        print("1. 查看详细文档: DSPY_QUICKSTART.md")
        print("2. 准备训练数据: python scripts/prepare_dspy_training_data.py")
        print("3. 训练优化模块: python scripts/train_dspy_modules.py --train-all --use-synthetic")
        print("4. 集成到生产环境: 更新 config/base_config.yaml 设置 use_dspy: true")
        
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
