"""
Head Node Deduplication Usage Examples

演示如何使用head节点去重功能的各种场景。

Author: Knowledge Graph Architect
Date: 2025-10-27
"""

from models.constructor.kt_gen import KnowledgeTreeGen
from utils.logger import logger


def example_1_basic_usage():
    """
    示例1: 基础用法 - 仅精确匹配去重
    
    适用场景：
    - 快速去重，性能优先
    - 对准确率要求不高
    - 数据质量较好，名称规范
    """
    print("\n" + "="*80)
    print("Example 1: Basic Usage - Exact Match Only")
    print("="*80)
    
    # 创建知识图谱构建器
    builder = KnowledgeTreeGen(
        dataset_name="demo",
        # ... 其他配置
    )
    
    # 1. 构建初步图谱
    documents = [
        {"text": "北京是中国的首都。", "id": 1},
        {"text": "北京市位于华北地区。", "id": 2},
        {"text": "Beijing is the capital of China.", "id": 3}
    ]
    
    for doc in documents:
        builder.process_document(doc)
    
    # 2. 执行head去重（仅精确匹配）
    stats = builder.deduplicate_heads(
        enable_semantic=False,  # 禁用语义去重
        similarity_threshold=0.85,
        use_llm_validation=False,
        max_candidates=1000
    )
    
    # 3. 查看结果
    print(f"\n✓ Deduplication completed:")
    print(f"  - Total merges: {stats['total_merges']}")
    print(f"  - Reduction rate: {stats['reduction_rate']:.2f}%")
    print(f"  - Time: {stats['elapsed_time_seconds']:.2f}s")
    
    # 4. 保存图谱
    builder.save_graph("output/graphs/demo_after_head_dedup.graphml")


def example_2_semantic_dedup_embedding_only():
    """
    示例2: 语义去重 - 仅使用Embedding
    
    适用场景：
    - 中等规模图谱（< 10k实体）
    - 需要语义理解，但成本敏感
    - 不需要最高精度
    """
    print("\n" + "="*80)
    print("Example 2: Semantic Deduplication - Embedding Only")
    print("="*80)
    
    builder = KnowledgeTreeGen(
        dataset_name="demo",
        # ... 其他配置
    )
    
    # 假设已经构建好图谱
    # builder.process_documents(documents)
    
    # 执行head去重（embedding-based语义去重）
    stats = builder.deduplicate_heads(
        enable_semantic=True,          # 启用语义去重
        similarity_threshold=0.85,     # 相似度阈值（推荐0.85-0.90）
        use_llm_validation=False,      # 不使用LLM，仅用embedding
        max_candidates=1000            # 最多处理1000对候选
    )
    
    print(f"\n✓ Results:")
    print(f"  - Exact merges: {stats['exact_merges']}")
    print(f"  - Semantic merges: {stats['semantic_merges']}")
    print(f"  - Total: {stats['total_merges']}")
    print(f"  - Entity count: {stats['initial_entity_count']} → {stats['final_entity_count']}")


def example_3_high_precision_with_llm():
    """
    示例3: 高精度模式 - 使用LLM验证
    
    适用场景：
    - 对准确性要求极高
    - 可接受较长处理时间
    - 预算充足（更多LLM调用）
    """
    print("\n" + "="*80)
    print("Example 3: High Precision Mode - With LLM Validation")
    print("="*80)
    
    builder = KnowledgeTreeGen(
        dataset_name="demo",
        # ... 其他配置
    )
    
    # 执行head去重（LLM验证）
    stats = builder.deduplicate_heads(
        enable_semantic=True,
        similarity_threshold=0.90,     # 更严格的阈值
        use_llm_validation=True,       # 启用LLM验证
        max_candidates=500             # 限制LLM调用次数（成本控制）
    )
    
    print(f"\n✓ High precision results:")
    print(f"  - Total merges: {stats['total_merges']}")
    print(f"  - Precision: HIGH (LLM validated)")
    print(f"  - Time: {stats['elapsed_time_seconds']:.2f}s")


def example_4_with_human_review():
    """
    示例4: 人工审核流程
    
    适用场景：
    - 生产环境部署
    - 需要质量保证
    - 关键业务数据
    """
    print("\n" + "="*80)
    print("Example 4: With Human Review Process")
    print("="*80)
    
    builder = KnowledgeTreeGen(
        dataset_name="demo",
        # ... 其他配置
    )
    
    # 1. 执行自动去重
    stats = builder.deduplicate_heads(
        enable_semantic=True,
        similarity_threshold=0.85,
        use_llm_validation=False,
        max_candidates=1000
    )
    
    print(f"\n✓ Automatic deduplication completed")
    print(f"  - Total merges: {stats['total_merges']}")
    
    # 2. 导出中等置信度的案例供人工审核
    review_file = "output/review/head_merge_candidates_for_review.csv"
    builder.export_head_merge_candidates_for_review(
        output_path=review_file,
        min_confidence=0.70,  # 置信度70%-90%的需要审核
        max_confidence=0.90
    )
    
    print(f"\n✓ Exported candidates for human review: {review_file}")
    print(f"  - Review items with confidence 0.70-0.90")
    print(f"  - High confidence (>0.90): auto-accepted")
    print(f"  - Low confidence (<0.70): auto-rejected")
    
    # 3. 人工审核后，可以根据审核结果调整
    # （实际流程需要额外的审核和回滚逻辑）


def example_5_batch_processing_large_graph():
    """
    示例5: 大规模图谱的分批处理
    
    适用场景：
    - 超大规模图谱（> 100k实体）
    - 内存受限
    - 需要断点续传
    """
    print("\n" + "="*80)
    print("Example 5: Batch Processing for Large Graphs")
    print("="*80)
    
    builder = KnowledgeTreeGen(
        dataset_name="large_demo",
        # ... 其他配置
    )
    
    # 分批处理（伪代码，实际需要实现批处理逻辑）
    batch_size = 1000
    all_candidates = builder._collect_head_candidates()
    
    print(f"Total candidates: {len(all_candidates)}")
    print(f"Batch size: {batch_size}")
    print(f"Number of batches: {(len(all_candidates) + batch_size - 1) // batch_size}")
    
    total_merges = 0
    
    for i in range(0, len(all_candidates), batch_size):
        batch = all_candidates[i:i + batch_size]
        batch_num = i // batch_size + 1
        
        print(f"\nProcessing batch {batch_num}...")
        
        # 对每批进行去重
        # （需要实现_deduplicate_heads_on_subset方法）
        # stats = builder._deduplicate_heads_on_subset(batch)
        # total_merges += stats['total_merges']
    
    print(f"\n✓ All batches processed")
    print(f"  - Total merges: {total_merges}")


def example_6_inspect_merge_results():
    """
    示例6: 检查去重结果
    
    展示如何检查哪些节点被合并了，以及合并的原因
    """
    print("\n" + "="*80)
    print("Example 6: Inspect Merge Results")
    print("="*80)
    
    builder = KnowledgeTreeGen(
        dataset_name="demo",
        # ... 其他配置
    )
    
    # 执行去重
    stats = builder.deduplicate_heads(
        enable_semantic=True,
        similarity_threshold=0.85,
        use_llm_validation=False,
        max_candidates=1000
    )
    
    # 检查哪些节点有合并历史
    print("\n" + "="*80)
    print("Merge History:")
    print("="*80)
    
    for node_id, data in builder.graph.nodes(data=True):
        if data.get("label") != "entity":
            continue
        
        dedup_info = data.get("properties", {}).get("head_dedup", {})
        
        if dedup_info and dedup_info.get("merged_nodes"):
            canonical_name = data.get("properties", {}).get("name", "")
            merged_nodes = dedup_info.get("merged_nodes", [])
            merge_history = dedup_info.get("merge_history", [])
            
            print(f"\n✓ Canonical node: {node_id} ({canonical_name})")
            print(f"  Merged {len(merged_nodes)} duplicate node(s):")
            
            for record in merge_history:
                print(f"    • {record['merged_node_id']} ({record['merged_node_name']})")
                print(f"      - Confidence: {record['confidence']:.3f}")
                print(f"      - Method: {record['method']}")
                print(f"      - Rationale: {record['rationale'][:100]}...")


def example_7_validate_integrity():
    """
    示例7: 验证图完整性
    
    展示如何在去重后验证图结构的完整性
    """
    print("\n" + "="*80)
    print("Example 7: Validate Graph Integrity")
    print("="*80)
    
    builder = KnowledgeTreeGen(
        dataset_name="demo",
        # ... 其他配置
    )
    
    # 执行去重
    stats = builder.deduplicate_heads(
        enable_semantic=True,
        similarity_threshold=0.85,
        use_llm_validation=False,
        max_candidates=1000
    )
    
    # 验证完整性
    issues = builder.validate_graph_integrity_after_head_dedup()
    
    print("\n" + "="*80)
    print("Integrity Check Results:")
    print("="*80)
    
    if not any(issues.values()):
        print("✓ No issues found - graph is healthy")
    else:
        if issues["orphan_nodes"]:
            print(f"⚠ Orphan nodes: {len(issues['orphan_nodes'])}")
            print(f"  Example: {issues['orphan_nodes'][:5]}")
        
        if issues["self_loops"]:
            print(f"⚠ Self loops: {len(issues['self_loops'])}")
            print(f"  Example: {issues['self_loops'][:5]}")
        
        if issues["dangling_references"]:
            print(f"⚠ Dangling references: {len(issues['dangling_references'])}")
            print(f"  Example: {issues['dangling_references'][:5]}")
        
        if issues["missing_metadata"]:
            print(f"⚠ Missing metadata: {len(issues['missing_metadata'])}")
            print(f"  Example: {issues['missing_metadata'][:5]}")


def example_8_compare_before_after():
    """
    示例8: 对比去重前后的图结构
    
    展示去重对图谱的影响
    """
    print("\n" + "="*80)
    print("Example 8: Compare Before and After")
    print("="*80)
    
    builder = KnowledgeTreeGen(
        dataset_name="demo",
        # ... 其他配置
    )
    
    # 构建图谱
    # builder.process_documents(documents)
    
    # 保存去重前的统计
    before_stats = {
        "entities": len([n for n, d in builder.graph.nodes(data=True) if d.get("label") == "entity"]),
        "edges": builder.graph.number_of_edges(),
        "avg_degree": sum(dict(builder.graph.degree()).values()) / builder.graph.number_of_nodes() if builder.graph.number_of_nodes() > 0 else 0
    }
    
    # 执行去重
    dedup_stats = builder.deduplicate_heads(
        enable_semantic=True,
        similarity_threshold=0.85,
        use_llm_validation=False,
        max_candidates=1000
    )
    
    # 去重后的统计
    after_stats = {
        "entities": len([n for n, d in builder.graph.nodes(data=True) if d.get("label") == "entity"]),
        "edges": builder.graph.number_of_edges(),
        "avg_degree": sum(dict(builder.graph.degree()).values()) / builder.graph.number_of_nodes() if builder.graph.number_of_nodes() > 0 else 0
    }
    
    # 对比
    print("\n" + "="*80)
    print("Comparison:")
    print("="*80)
    print(f"\nBefore Deduplication:")
    print(f"  - Entities: {before_stats['entities']}")
    print(f"  - Edges: {before_stats['edges']}")
    print(f"  - Avg degree: {before_stats['avg_degree']:.2f}")
    
    print(f"\nAfter Deduplication:")
    print(f"  - Entities: {after_stats['entities']} (↓{before_stats['entities'] - after_stats['entities']})")
    print(f"  - Edges: {after_stats['edges']} (↓{before_stats['edges'] - after_stats['edges']})")
    print(f"  - Avg degree: {after_stats['avg_degree']:.2f} (↑{after_stats['avg_degree'] - before_stats['avg_degree']:.2f})")
    
    print(f"\nReduction:")
    print(f"  - Entity reduction: {(before_stats['entities'] - after_stats['entities']) / before_stats['entities'] * 100:.1f}%")
    print(f"  - Edge reduction: {(before_stats['edges'] - after_stats['edges']) / before_stats['edges'] * 100:.1f}%")


if __name__ == "__main__":
    """
    运行所有示例
    
    注意：这些示例需要实际的KnowledgeTreeGen实例和数据才能运行。
    请根据实际情况调整配置和数据路径。
    """
    
    print("\n" + "="*80)
    print("Head Node Deduplication Examples")
    print("="*80)
    print("\nThese are example code snippets demonstrating various use cases.")
    print("Please adapt them to your actual setup before running.")
    print("="*80)
    
    # 选择运行特定示例
    # example_1_basic_usage()
    # example_2_semantic_dedup_embedding_only()
    # example_3_high_precision_with_llm()
    # example_4_with_human_review()
    # example_5_batch_processing_large_graph()
    # example_6_inspect_merge_results()
    # example_7_validate_integrity()
    # example_8_compare_before_after()
    
    print("\n✓ Examples defined successfully")
    print("  Uncomment the example function calls in __main__ to run them.")
