"""
训练和优化DSPy模块

这个脚本训练semantic dedup的DSPy模块，使其性能更好且成本更低。

使用方法:
    # 基本使用
    python scripts/train_dspy_modules.py --api-key YOUR_API_KEY
    
    # 指定训练数据和输出路径
    python scripts/train_dspy_modules.py \\
        --train-data data/dspy_training_examples.json \\
        --output-dir models/dspy_optimized \\
        --api-key YOUR_API_KEY
    
    # 只训练聚类模块
    python scripts/train_dspy_modules.py --train-clustering --api-key YOUR_API_KEY
    
    # 只训练去重模块  
    python scripts/train_dspy_modules.py --train-dedup --api-key YOUR_API_KEY
"""

import argparse
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import dspy
from models.constructor.dspy_semantic_dedup import (
    DSPySemanticDedupOptimizer,
    SemanticClusteringModule,
    SemanticDedupModule,
    clustering_metric,
    dedup_metric
)
from scripts.prepare_dspy_training_data import (
    load_training_examples,
    create_synthetic_training_examples,
    print_example_stats
)
from utils.logger import logger


def setup_dspy(api_key: str, base_url: str = None):
    """配置DSPy环境"""
    if not api_key:
        raise ValueError("API key is required. Use --api-key or set OPENAI_API_KEY environment variable")
    
    os.environ['OPENAI_API_KEY'] = api_key
    
    # Set default LLM
    lm_kwargs = {"api_key": api_key, "max_tokens": 2000}
    if base_url:
        lm_kwargs["base_url"] = base_url
    
    lm = dspy.OpenAI(model="gpt-3.5-turbo", **lm_kwargs)
    dspy.settings.configure(lm=lm)
    
    logger.info("DSPy configured successfully")


def evaluate_baseline(module, examples, metric_fn, module_name: str):
    """评估baseline（未优化）模块"""
    print(f"\n{'='*80}")
    print(f"Evaluating Baseline {module_name}")
    print('='*80)
    
    scores = []
    for i, ex in enumerate(examples, 1):
        try:
            inputs = ex.inputs()
            pred = module(**inputs)
            score = metric_fn(ex, pred)
            scores.append(score)
            
            print(f"Example {i}/{len(examples)}: {score:.2f}")
        
        except Exception as e:
            logger.warning(f"Evaluation failed for example {i}: {e}")
            scores.append(0.0)
    
    avg_score = sum(scores) / len(scores) if scores else 0.0
    
    print(f"\n{'='*80}")
    print(f"Baseline {module_name} Performance")
    print('='*80)
    print(f"Average Score: {avg_score:.2f}")
    print(f"Min Score: {min(scores) if scores else 0:.2f}")
    print(f"Max Score: {max(scores) if scores else 0:.2f}")
    print('='*80 + '\n')
    
    return avg_score, scores


def train_clustering_module(
    train_examples, 
    val_examples,
    teacher_model: str = "gpt-4",
    student_model: str = "gpt-3.5-turbo",
    output_path: str = None
):
    """训练聚类模块"""
    print("\n" + "="*80)
    print("Training Clustering Module")
    print("="*80)
    print(f"Teacher Model: {teacher_model}")
    print(f"Student Model: {student_model}")
    print(f"Training Examples: {len(train_examples)}")
    print(f"Validation Examples: {len(val_examples)}")
    print("="*80)
    
    # Evaluate baseline
    baseline_module = SemanticClusteringModule(use_cot=True)
    baseline_score, baseline_scores = evaluate_baseline(
        baseline_module, val_examples, clustering_metric, "Clustering"
    )
    
    # Create optimizer
    print("\n" + "="*80)
    print("Optimizing Clustering Module...")
    print("="*80)
    print("This may take several minutes...")
    
    optimizer = DSPySemanticDedupOptimizer(train_examples, val_examples)
    
    try:
        optimized_module = optimizer.optimize_clustering(
            teacher_model=teacher_model,
            student_model=student_model,
            max_bootstrapped_demos=4,
            max_labeled_demos=4
        )
        
        print("\n✓ Optimization completed successfully")
        
        # Evaluate optimized module
        print("\n" + "="*80)
        print("Evaluating Optimized Clustering Module")
        print("="*80)
        
        optimized_score, optimized_scores = evaluate_baseline(
            optimized_module, val_examples, clustering_metric, "Optimized Clustering"
        )
        
        # Show improvement
        improvement = optimized_score - baseline_score
        print("\n" + "="*80)
        print("Clustering Module Results")
        print("="*80)
        print(f"Baseline Score:  {baseline_score:.2f}")
        print(f"Optimized Score: {optimized_score:.2f}")
        print(f"Improvement:     {improvement:+.2f} ({improvement/baseline_score*100:+.1f}%)" if baseline_score > 0 else "N/A")
        print("="*80 + "\n")
        
        # Save optimized module
        if output_path:
            output_file = Path(output_path) / "clustering_module.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            optimized_module.save(str(output_file))
            print(f"✓ Saved optimized clustering module to {output_file}\n")
        
        return optimized_module, {
            "baseline_score": baseline_score,
            "optimized_score": optimized_score,
            "improvement": improvement
        }
    
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def train_dedup_module(
    train_examples,
    val_examples,
    prompt_type: str = "general",
    teacher_model: str = "gpt-4",
    student_model: str = "gpt-3.5-turbo",
    output_path: str = None
):
    """训练去重模块"""
    print("\n" + "="*80)
    print(f"Training Deduplication Module ({prompt_type})")
    print("="*80)
    print(f"Teacher Model: {teacher_model}")
    print(f"Student Model: {student_model}")
    print(f"Training Examples: {len(train_examples)}")
    print(f"Validation Examples: {len(val_examples)}")
    print("="*80)
    
    # Evaluate baseline
    baseline_module = SemanticDedupModule(prompt_type=prompt_type, use_cot=True)
    
    # For dedup evaluation, we need to add contexts to examples
    # (Simplified for now - in real usage, you'd need actual context data)
    val_examples_with_context = []
    for ex in val_examples:
        ex_dict = ex.toDict()
        # Add dummy contexts for evaluation
        ex_dict['head_contexts'] = ["- (no context available)"]
        ex_dict['batch_entries'] = [
            {
                "description": desc,
                "context_summaries": ["- (no context available)"]
            }
            for desc in ex.tail_descriptions
        ]
        val_examples_with_context.append(dspy.Example(**ex_dict).with_inputs(
            "head_entity", "relation", "head_contexts", "batch_entries"
        ))
    
    baseline_score, baseline_scores = evaluate_baseline(
        baseline_module, val_examples_with_context, dedup_metric, "Deduplication"
    )
    
    # Create optimizer
    print("\n" + "="*80)
    print("Optimizing Deduplication Module...")
    print("="*80)
    print("This may take several minutes...")
    
    # Prepare train examples with contexts
    train_examples_with_context = []
    for ex in train_examples:
        ex_dict = ex.toDict()
        ex_dict['head_contexts'] = ["- (no context available)"]
        ex_dict['batch_entries'] = [
            {
                "description": desc,
                "context_summaries": ["- (no context available)"]
            }
            for desc in ex.tail_descriptions
        ]
        train_examples_with_context.append(dspy.Example(**ex_dict).with_inputs(
            "head_entity", "relation", "head_contexts", "batch_entries"
        ))
    
    optimizer = DSPySemanticDedupOptimizer(train_examples_with_context, val_examples_with_context)
    
    try:
        optimized_module = optimizer.optimize_dedup(
            prompt_type=prompt_type,
            teacher_model=teacher_model,
            student_model=student_model,
            max_bootstrapped_demos=3,
            max_labeled_demos=3
        )
        
        print("\n✓ Optimization completed successfully")
        
        # Evaluate optimized module
        print("\n" + "="*80)
        print("Evaluating Optimized Deduplication Module")
        print("="*80)
        
        optimized_score, optimized_scores = evaluate_baseline(
            optimized_module, val_examples_with_context, dedup_metric, "Optimized Deduplication"
        )
        
        # Show improvement
        improvement = optimized_score - baseline_score
        print("\n" + "="*80)
        print("Deduplication Module Results")
        print("="*80)
        print(f"Baseline Score:  {baseline_score:.2f}")
        print(f"Optimized Score: {optimized_score:.2f}")
        print(f"Improvement:     {improvement:+.2f} ({improvement/baseline_score*100:+.1f}%)" if baseline_score > 0 else "N/A")
        print("="*80 + "\n")
        
        # Save optimized module
        if output_path:
            output_file = Path(output_path) / f"dedup_module_{prompt_type}.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            optimized_module.save(str(output_file))
            print(f"✓ Saved optimized dedup module to {output_file}\n")
        
        return optimized_module, {
            "baseline_score": baseline_score,
            "optimized_score": optimized_score,
            "improvement": improvement
        }
    
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def main():
    parser = argparse.ArgumentParser(description="Train DSPy modules for semantic dedup")
    
    # Data arguments
    parser.add_argument(
        '--train-data',
        type=str,
        default='data/dspy_training_examples.json',
        help='Path to training data JSON file'
    )
    parser.add_argument(
        '--use-synthetic',
        action='store_true',
        help='Use synthetic training data (ignore --train-data)'
    )
    
    # Output arguments
    parser.add_argument(
        '--output-dir',
        type=str,
        default='models/dspy_optimized',
        help='Directory to save optimized modules'
    )
    
    # Training selection
    parser.add_argument(
        '--train-clustering',
        action='store_true',
        help='Train clustering module only'
    )
    parser.add_argument(
        '--train-dedup',
        action='store_true',
        help='Train deduplication module only'
    )
    parser.add_argument(
        '--train-all',
        action='store_true',
        help='Train both modules (default if neither specified)'
    )
    
    # Model selection
    parser.add_argument(
        '--teacher-model',
        type=str,
        default='gpt-4',
        help='Teacher model for optimization (default: gpt-4)'
    )
    parser.add_argument(
        '--student-model',
        type=str,
        default='gpt-3.5-turbo',
        help='Student model for optimization (default: gpt-3.5-turbo)'
    )
    
    # API configuration
    parser.add_argument(
        '--api-key',
        type=str,
        default=None,
        help='OpenAI API key (or set OPENAI_API_KEY env var)'
    )
    parser.add_argument(
        '--base-url',
        type=str,
        default=None,
        help='Custom API base URL'
    )
    
    # Train/val split
    parser.add_argument(
        '--val-split',
        type=float,
        default=0.3,
        help='Validation split ratio (default: 0.3)'
    )
    
    args = parser.parse_args()
    
    # Get API key from env if not provided
    api_key = args.api_key or os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("ERROR: API key required. Use --api-key or set OPENAI_API_KEY environment variable")
        sys.exit(1)
    
    # Setup DSPy
    print("Setting up DSPy...")
    setup_dspy(api_key, args.base_url)
    
    # Load or create training data
    if args.use_synthetic or not Path(args.train_data).exists():
        print("\nUsing synthetic training data...")
        examples = create_synthetic_training_examples()
    else:
        print(f"\nLoading training data from {args.train_data}...")
        examples = load_training_examples(args.train_data)
    
    print(f"Loaded {len(examples)} training examples")
    print_example_stats(examples)
    
    # Split into train/val
    split_idx = int(len(examples) * (1 - args.val_split))
    train_examples = examples[:split_idx]
    val_examples = examples[split_idx:]
    
    print(f"\nTrain/Val split: {len(train_examples)}/{len(val_examples)}")
    
    # Determine what to train
    train_clustering = args.train_clustering or args.train_all or (not args.train_dedup)
    train_dedup = args.train_dedup or args.train_all or (not args.train_clustering)
    
    results = {}
    
    # Train clustering module
    if train_clustering:
        clustering_module, clustering_results = train_clustering_module(
            train_examples=train_examples,
            val_examples=val_examples,
            teacher_model=args.teacher_model,
            student_model=args.student_model,
            output_path=args.output_dir
        )
        results['clustering'] = clustering_results
    
    # Train dedup module
    if train_dedup:
        dedup_module, dedup_results = train_dedup_module(
            train_examples=train_examples,
            val_examples=val_examples,
            prompt_type="general",
            teacher_model=args.teacher_model,
            student_model=args.student_model,
            output_path=args.output_dir
        )
        results['dedup'] = dedup_results
    
    # Print final summary
    print("\n" + "="*80)
    print("Training Summary")
    print("="*80)
    
    if 'clustering' in results and results['clustering']:
        r = results['clustering']
        print(f"\nClustering Module:")
        print(f"  Baseline:  {r['baseline_score']:.2f}")
        print(f"  Optimized: {r['optimized_score']:.2f}")
        print(f"  Gain:      {r['improvement']:+.2f} ({r['improvement']/r['baseline_score']*100:+.1f}%)" if r['baseline_score'] > 0 else "  Gain: N/A")
    
    if 'dedup' in results and results['dedup']:
        r = results['dedup']
        print(f"\nDeduplication Module:")
        print(f"  Baseline:  {r['baseline_score']:.2f}")
        print(f"  Optimized: {r['optimized_score']:.2f}")
        print(f"  Gain:      {r['improvement']:+.2f} ({r['improvement']/r['baseline_score']*100:+.1f}%)" if r['baseline_score'] > 0 else "  Gain: N/A")
    
    print("\n" + "="*80)
    print("Training completed!")
    print("="*80)
    
    print(f"\nOptimized modules saved to: {args.output_dir}")
    print("\nNext steps:")
    print("1. Test the optimized modules on real data")
    print("2. Update config to enable DSPy: use_dspy: true")
    print("3. Run deduplication with optimized modules")


if __name__ == "__main__":
    main()
