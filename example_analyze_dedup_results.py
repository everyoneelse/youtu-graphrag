#!/usr/bin/env python3
"""
示例：分析去重中间结果

用法：
    python example_analyze_dedup_results.py output/dedup_intermediate/hotpot_dedup_20251019_120000.json
"""

import json
import sys
from collections import defaultdict


def analyze_dedup_results(filepath):
    """分析去重中间结果文件"""
    
    print("=" * 80)
    print("去重中间结果分析")
    print("=" * 80)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    # 全局统计
    print(f"\n【全局统计】")
    print(f"数据集: {results['dataset']}")
    print(f"配置参数:")
    for key, value in results['config'].items():
        print(f"  {key}: {value}")
    
    summary = results['summary']
    print(f"\n处理统计:")
    print(f"  总 communities: {summary['total_communities']}")
    print(f"  总候选项: {summary['total_candidates']}")
    print(f"  聚类后 clusters: {summary['total_clusters']}")
    print(f"  单项 clusters: N/A (需计算)")
    print(f"  LLM 调用次数: {summary['total_llm_calls']}")
    print(f"  最终合并次数: {summary['total_merges']}")
    print(f"  去重项数: {summary['total_items_merged']}")
    
    # 去重率
    dedup_rate = summary['total_items_merged'] / summary['total_candidates'] * 100 if summary['total_candidates'] > 0 else 0
    print(f"  去重率: {dedup_rate:.2f}%")
    
    # LLM 效率
    if summary['total_llm_calls'] > 0:
        avg_candidates_per_call = summary['total_candidates'] / summary['total_llm_calls']
        print(f"  平均每次 LLM 调用处理: {avg_candidates_per_call:.2f} 个候选项")
    
    # 聚类效果统计
    print(f"\n【聚类效果分析】")
    cluster_sizes = []
    single_clusters = 0
    multi_clusters = 0
    
    for comm in results['communities']:
        for cluster in comm['clustering']['clusters']:
            size = cluster['size']
            cluster_sizes.append(size)
            if size == 1:
                single_clusters += 1
            else:
                multi_clusters += 1
    
    print(f"  单项 clusters: {single_clusters} ({single_clusters/len(cluster_sizes)*100:.1f}%)")
    print(f"  多项 clusters: {multi_clusters} ({multi_clusters/len(cluster_sizes)*100:.1f}%)")
    
    if cluster_sizes:
        import statistics
        print(f"  Cluster 大小统计:")
        print(f"    平均: {statistics.mean(cluster_sizes):.2f}")
        print(f"    中位数: {statistics.median(cluster_sizes):.0f}")
        print(f"    最大: {max(cluster_sizes)}")
        print(f"    最小: {min(cluster_sizes)}")
    
    # LLM 分组效果
    print(f"\n【LLM 分组效果】")
    total_groups = 0
    group_sizes = []
    
    for comm in results['communities']:
        for llm_result in comm['llm_groups']:
            for group in llm_result['groups']:
                total_groups += 1
                group_sizes.append(len(group['members']))
    
    print(f"  总分组数: {total_groups}")
    if group_sizes:
        print(f"  分组大小统计:")
        print(f"    平均: {statistics.mean(group_sizes):.2f}")
        print(f"    中位数: {statistics.median(group_sizes):.0f}")
        print(f"    最大: {max(group_sizes)}")
    
    # 详细案例展示
    print(f"\n【详细案例】（前3个 communities）")
    for idx, comm in enumerate(results['communities'][:3]):
        print(f"\n--- Community {idx+1}: {comm['community_name']} ---")
        print(f"候选项数: {comm['total_candidates']}")
        print(f"聚类结果: {comm['summary']['total_clusters']} clusters")
        print(f"  - 单项: {comm['summary']['single_item_clusters']}")
        print(f"  - 多项: {comm['summary']['multi_item_clusters']}")
        print(f"LLM 调用: {comm['summary']['total_llm_calls']} 次")
        print(f"最终合并: {comm['summary']['total_merges']} 次，去重 {comm['summary']['items_merged']} 项")
        
        # 显示具体的合并操作
        if comm['final_merges']:
            print(f"\n合并操作示例:")
            for merge_idx, merge in enumerate(comm['final_merges'][:2]):  # 只显示前2个
                print(f"  {merge_idx+1}. 保留: {merge['representative']['description']}")
                print(f"     合并: {[d['description'] for d in merge['duplicates']]}")
                if merge['rationale']:
                    print(f"     理由: {merge['rationale'][:100]}...")
    
    # 问题诊断
    print(f"\n【问题诊断】")
    issues = []
    
    # 检查是否有过多单项 clusters
    if single_clusters / len(cluster_sizes) > 0.7:
        issues.append("⚠️  单项 clusters 占比过高 (>70%)，考虑降低 embedding_threshold")
    
    # 检查去重率
    if dedup_rate < 5:
        issues.append("⚠️  去重率很低 (<5%)，可能阈值设置过高或候选项本身就不重复")
    elif dedup_rate > 50:
        issues.append("⚠️  去重率很高 (>50%)，需要检查是否过度合并")
    
    # 检查 LLM 调用效率
    if summary['total_llm_calls'] > 0:
        llm_waste_rate = (summary['total_llm_calls'] - summary['total_merges']) / summary['total_llm_calls'] * 100
        if llm_waste_rate > 50:
            issues.append(f"⚠️  {llm_waste_rate:.1f}% 的 LLM 调用没有产生合并，考虑优化聚类阈值")
    
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print(f"  ✅ 未发现明显问题")
    
    # 优化建议
    print(f"\n【优化建议】")
    
    if single_clusters / len(cluster_sizes) > 0.6:
        current_threshold = results['config']['threshold']
        print(f"  1. 考虑降低 embedding_threshold 从 {current_threshold} 到 {current_threshold - 0.05}")
    
    if dedup_rate < 10 and single_clusters / len(cluster_sizes) > 0.7:
        print(f"  2. 聚类效果不佳，建议检查 embedding 模型是否适合当前数据")
    
    avg_batch = summary['total_candidates'] / summary['total_llm_calls'] if summary['total_llm_calls'] > 0 else 0
    max_batch = results['config']['max_batch_size']
    if avg_batch < max_batch * 0.5:
        print(f"  3. 平均批次大小 ({avg_batch:.1f}) 远小于最大批次 ({max_batch})，可以考虑增大 max_batch_size")
    
    print("\n" + "=" * 80)


def compare_before_after(results):
    """对比去重前后的效果"""
    print(f"\n【去重前后对比】")
    
    for comm in results['communities'][:3]:
        print(f"\nCommunity: {comm['community_name']}")
        print(f"  去重前: {comm['total_candidates']} 个候选项")
        kept = comm['total_candidates'] - comm['summary']['items_merged']
        print(f"  去重后: {kept} 个候选项")
        print(f"  减少: {comm['summary']['items_merged']} 个 ({comm['summary']['items_merged']/comm['total_candidates']*100:.1f}%)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python example_analyze_dedup_results.py <intermediate_results.json>")
        print("示例: python example_analyze_dedup_results.py output/dedup_intermediate/hotpot_dedup_20251019_120000.json")
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    try:
        analyze_dedup_results(filepath)
    except FileNotFoundError:
        print(f"❌ 文件不存在: {filepath}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"❌ 无效的 JSON 文件: {filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
