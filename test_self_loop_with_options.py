#!/usr/bin/env python3
"""
测试自环的不同处理选项
"""

import networkx as nx

from apply_tail_dedup_results import TailDedupApplicator


def create_simple_self_loop_graph() -> nx.MultiDiGraph:
    """创建简单的测试图"""
    graph = nx.MultiDiGraph()
    
    graph.add_node('entity_1', label='entity', level=2,
                   properties={'name': '延长TE值', 'chunk id': 'A'})
    graph.add_node('entity_2', label='entity', level=2,
                   properties={'name': '增加TE值', 'chunk id': 'B'})
    graph.add_node('entity_3', label='entity', level=2,
                   properties={'name': '延长TE', 'chunk id': 'C'})
    
    # 创建会变成自环的边
    graph.add_edge('entity_2', 'entity_1', relation='等价于')  # 增加TE值 → 延长TE值
    graph.add_edge('entity_3', 'entity_1', relation='等价于')  # 延长TE → 延长TE值
    graph.add_edge('entity_2', 'entity_3', relation='等价于')  # 增加TE值 → 延长TE
    
    return graph


def create_dedup_results() -> list:
    """创建去重结果"""
    return [{
        "head_node": {"label": "entity", "properties": {"name": "任意", "chunk id": "x"}},
        "relation": "任意",
        "tail_nodes_to_dedup": [
            "延长TE值 (chunk id: A) [entity]",
            "增加TE值 (chunk id: B) [entity]",
            "延长TE (chunk id: C) [entity]"
        ],
        "dedup_results": {
            "cluster_0": {
                "member": [
                    "增加TE值 (chunk id: B) [entity]",
                    "延长TE (chunk id: C) [entity]",
                    "延长TE值 (chunk id: A) [entity]"
                ],
                "llm_judge_reason": "相同概念"
            }
        },
        "deduped_tails": ["延长TE值 (chunk id: A) [entity]"]
    }]


def test_option(remove_self_loops: bool, option_name: str):
    """测试特定选项"""
    print(f"\n{'='*70}")
    print(f"测试 {option_name}")
    print(f"{'='*70}")
    
    graph = create_simple_self_loop_graph()
    dedup_results = create_dedup_results()
    
    print(f"\n原始图:")
    print(f"  节点数: {graph.number_of_nodes()}")
    print(f"  边数: {graph.number_of_edges()}")
    print(f"  边:")
    for u, v, data in graph.edges(data=True):
        u_name = graph.nodes[u]['properties']['name']
        v_name = graph.nodes[v]['properties']['name']
        rel = data.get('relation', '')
        print(f"    {u_name} --{rel}--> {v_name}")
    
    # 应用去重
    applicator = TailDedupApplicator(graph, remove_self_loops=remove_self_loops)
    stats = applicator.apply_all(dedup_results)
    
    print(f"\n处理后:")
    print(f"  节点数: {graph.number_of_nodes()}")
    print(f"  边数: {graph.number_of_edges()}")
    print(f"  边:")
    
    has_self_loop = False
    self_loop_count = 0
    for u, v, data in graph.edges(data=True):
        u_name = graph.nodes[u]['properties']['name']
        v_name = graph.nodes[v]['properties']['name']
        rel = data.get('relation', '')
        edge_str = f"    {u_name} --{rel}--> {v_name}"
        
        if u == v:
            edge_str += "  ⚠️ 自环"
            has_self_loop = True
            self_loop_count += 1
        
        print(edge_str)
    
    print(f"\n统计:")
    print(f"  edges_updated: {stats['edges_updated']}")
    print(f"  self_loops_kept: {stats['self_loops_kept']}")
    print(f"  self_loops_removed: {stats['self_loops_removed']}")
    print(f"  isolated_nodes_removed: {stats['isolated_nodes_removed']}")
    
    print(f"\n结果:")
    if remove_self_loops:
        if not has_self_loop:
            print(f"  ✅ 成功：所有自环已删除")
        else:
            print(f"  ❌ 失败：仍有 {self_loop_count} 个自环")
    else:
        if has_self_loop:
            print(f"  ✅ 成功：保留了 {self_loop_count} 个自环")
            if self_loop_count == 1:
                print(f"  ✅ 去重正确：多个重复自环合并为1个")
            else:
                print(f"  ⚠️  警告：有 {self_loop_count} 个自环（可能有重复）")
        else:
            print(f"  ⚠️  没有自环（可能全部被删除了）")


def main():
    """主函数"""
    print("\n" + "="*70)
    print("自环处理选项测试")
    print("="*70)
    
    print("\n场景：u --relation--> v, 其中 u 和 v 都映射到同一个代表节点")
    print("\n选项1: 保留自环（remove_self_loops=False, 默认）")
    print("选项2: 删除自环（remove_self_loops=True）")
    
    # 测试选项1：保留自环
    test_option(remove_self_loops=False, option_name="选项1: 保留自环")
    
    # 测试选项2：删除自环
    test_option(remove_self_loops=True, option_name="选项2: 删除自环")
    
    print(f"\n{'='*70}")
    print("总结")
    print(f"{'='*70}")
    
    print("\n选项1 (保留自环) - 默认行为:")
    print("  适用于: 需要表示自反关系的场景")
    print("  例如: '等价于'、'相同概念'、'循环依赖' 等")
    print("  结果: rep --relation--> rep")
    
    print("\n选项2 (删除自环):")
    print("  适用于: 不需要自环的场景")
    print("  例如: 有向无环图(DAG)、层次结构等")
    print("  结果: 边被删除")
    
    print(f"\n{'='*70}")


if __name__ == "__main__":
    main()
