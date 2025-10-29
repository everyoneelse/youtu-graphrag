#!/usr/bin/env python3
"""
完整的端到端去重工作流

这个脚本展示了从graph.json到deduped_graph.json的完整流程
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

from apply_tail_dedup_results import TailDedupApplicator
from utils import graph_processor
from utils.logger import logger


def print_section(title: str):
    """打印分节标题"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def analyze_dedup_results(dedup_results: List[Dict]) -> Dict:
    """分析去重结果的统计信息"""
    stats = {
        'total_groups': len(dedup_results),
        'total_clusters': 0,
        'total_members': 0,
        'cluster_sizes': [],
        'relations': set(),
        'node_types': set(),
    }
    
    for group in dedup_results:
        stats['relations'].add(group.get('relation', 'unknown'))
        
        if 'head_node' in group:
            stats['node_types'].add(group['head_node'].get('label', 'unknown'))
        
        dedup_clusters = group.get('dedup_results', {})
        stats['total_clusters'] += len(dedup_clusters)
        
        for cluster_name, cluster_data in dedup_clusters.items():
            members = cluster_data.get('member', [])
            stats['total_members'] += len(members)
            stats['cluster_sizes'].append(len(members))
    
    return stats


def print_dedup_stats(stats: Dict):
    """打印去重统计信息"""
    print(f"\n  去重组数量: {stats['total_groups']}")
    print(f"  Cluster总数: {stats['total_clusters']}")
    print(f"  成员总数: {stats['total_members']}")
    
    if stats['cluster_sizes']:
        avg_size = sum(stats['cluster_sizes']) / len(stats['cluster_sizes'])
        print(f"  平均cluster大小: {avg_size:.2f}")
        print(f"  最大cluster大小: {max(stats['cluster_sizes'])}")
        print(f"  最小cluster大小: {min(stats['cluster_sizes'])}")
    
    print(f"\n  涉及的关系类型: {len(stats['relations'])}")
    for rel in sorted(stats['relations']):
        print(f"    - {rel}")
    
    print(f"\n  涉及的节点类型: {len(stats['node_types'])}")
    for nt in sorted(stats['node_types']):
        print(f"    - {nt}")


def verify_graph_files(graph_path: str, dedup_path: str):
    """验证输入文件"""
    print("\n  检查输入文件...")
    
    # 检查graph文件
    if not Path(graph_path).exists():
        raise FileNotFoundError(f"图谱文件不存在: {graph_path}")
    print(f"    ✅ 图谱文件: {graph_path}")
    
    # 检查dedup文件
    if not Path(dedup_path).exists():
        raise FileNotFoundError(f"去重结果文件不存在: {dedup_path}")
    print(f"    ✅ 去重文件: {dedup_path}")


def load_and_analyze_graph(graph_path: str):
    """加载并分析图谱"""
    print(f"\n  加载图谱: {graph_path}")
    graph = graph_processor.load_graph_from_json(graph_path)
    
    num_nodes = graph.number_of_nodes()
    num_edges = graph.number_of_edges()
    
    print(f"    节点数: {num_nodes}")
    print(f"    边数: {num_edges}")
    
    # 统计节点类型
    node_types = {}
    for node_id, data in graph.nodes(data=True):
        label = data.get('label', 'unknown')
        node_types[label] = node_types.get(label, 0) + 1
    
    print(f"\n    节点类型分布:")
    for label, count in sorted(node_types.items()):
        print(f"      {label}: {count}")
    
    # 统计关系类型
    relation_types = {}
    for u, v, data in graph.edges(data=True):
        rel = data.get('relation', 'unknown')
        relation_types[rel] = relation_types.get(rel, 0) + 1
    
    print(f"\n    关系类型分布 (Top 10):")
    for rel, count in sorted(relation_types.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"      {rel}: {count}")
    
    return graph


def load_and_analyze_dedup(dedup_path: str):
    """加载并分析去重结果"""
    print(f"\n  加载去重结果: {dedup_path}")
    
    with open(dedup_path, 'r', encoding='utf-8') as f:
        dedup_results = json.load(f)
    
    stats = analyze_dedup_results(dedup_results)
    print_dedup_stats(stats)
    
    return dedup_results


def apply_dedup(graph, dedup_results):
    """应用去重"""
    print("\n  应用去重处理...")
    
    applicator = TailDedupApplicator(graph)
    stats = applicator.apply_all(dedup_results)
    
    return stats


def print_dedup_results(stats: Dict, original_nodes: int, original_edges: int, 
                       final_nodes: int, final_edges: int):
    """打印去重结果"""
    print("\n  处理统计:")
    print(f"    Clusters处理: {stats['total_clusters']}")
    print(f"    成员总数: {stats['total_members']}")
    print(f"    边更新: {stats['edges_updated']}")
    print(f"    社区更新: {stats['communities_updated']}")
    print(f"    社区成员去重: {stats['community_members_deduplicated']}")
    print(f"    keyword_filter_by更新: {stats['keyword_filter_relations_updated']}")
    print(f"    孤立节点删除: {stats['isolated_nodes_removed']}")
    
    print(f"\n  图谱变化:")
    print(f"    节点: {original_nodes} → {final_nodes} (减少 {original_nodes - final_nodes}, {(original_nodes - final_nodes) / original_nodes * 100:.1f}%)")
    print(f"    边:   {original_edges} → {final_edges} (减少 {original_edges - final_edges}, {(original_edges - final_edges) / original_edges * 100:.1f}%)")


def save_graph(graph, output_path: str):
    """保存图谱"""
    print(f"\n  保存去重后的图谱: {output_path}")
    
    # 确保输出目录存在
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    graph_processor.save_graph_to_json(graph, output_path)
    
    file_size = Path(output_path).stat().st_size
    print(f"    文件大小: {file_size / 1024:.2f} KB")


def main():
    """主函数"""
    if len(sys.argv) != 4:
        print("用法: python3 complete_dedup_workflow.py <graph.json> <dedup_results.json> <output.json>")
        print("\n示例:")
        print("  python3 complete_dedup_workflow.py \\")
        print("      output/graphs/original.json \\")
        print("      your_dedup_results.json \\")
        print("      output/graphs/deduped.json")
        sys.exit(1)
    
    graph_path = sys.argv[1]
    dedup_path = sys.argv[2]
    output_path = sys.argv[3]
    
    try:
        # 标题
        print("\n" + "🎯"*35)
        print("    完整的Tail去重工作流")
        print("🎯"*35)
        
        # 步骤1: 验证输入文件
        print_section("步骤1: 验证输入文件")
        verify_graph_files(graph_path, dedup_path)
        
        # 步骤2: 加载并分析原始图谱
        print_section("步骤2: 加载并分析原始图谱")
        graph = load_and_analyze_graph(graph_path)
        original_nodes = graph.number_of_nodes()
        original_edges = graph.number_of_edges()
        
        # 步骤3: 加载并分析去重结果
        print_section("步骤3: 加载并分析去重结果")
        dedup_results = load_and_analyze_dedup(dedup_path)
        
        # 步骤4: 应用去重
        print_section("步骤4: 应用去重")
        stats = apply_dedup(graph, dedup_results)
        
        final_nodes = graph.number_of_nodes()
        final_edges = graph.number_of_edges()
        
        # 步骤5: 打印结果
        print_section("步骤5: 去重结果")
        print_dedup_results(stats, original_nodes, original_edges, final_nodes, final_edges)
        
        # 步骤6: 保存图谱
        print_section("步骤6: 保存去重后的图谱")
        save_graph(graph, output_path)
        
        # 总结
        print_section("✅ 完成！")
        print(f"\n  输入文件:")
        print(f"    原始图谱: {graph_path}")
        print(f"    去重结果: {dedup_path}")
        print(f"\n  输出文件:")
        print(f"    去重图谱: {output_path}")
        print(f"\n  建议:")
        print(f"    1. 查看输出文件确认结果")
        print(f"    2. 对比原始图谱和去重图谱")
        print(f"    3. 在下游任务中使用去重后的图谱")
        print()
        
    except Exception as e:
        logger.error(f"处理失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
