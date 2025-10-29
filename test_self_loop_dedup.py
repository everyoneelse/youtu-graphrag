#!/usr/bin/env python3
"""
测试自环情况：当u和v都映射到同一个代表节点时会发生什么

场景：u --relation--> v
如果 u 和 v 都在同一个cluster中，都映射到代表节点 rep
结果：rep --relation--> rep (自环)
"""

import json
import networkx as nx

from apply_tail_dedup_results import TailDedupApplicator
from utils import graph_processor


def create_self_loop_test_graph() -> nx.MultiDiGraph:
    """
    创建测试图：u → v，其中u和v应该映射到同一个代表
    
    结构：
    - 增加TE值 --相同概念--> 延长TE值
    - 延长TE   --相同概念--> 延长TE值
    
    这两条边中，所有三个节点都在同一个cluster中
    """
    graph = nx.MultiDiGraph()
    
    # 添加三个节点（都在同一个cluster）
    graph.add_node('entity_1',
                   label='entity',
                   level=2,
                   properties={'name': '延长TE值', 'chunk id': 'A'})
    
    graph.add_node('entity_2',
                   label='entity',
                   level=2,
                   properties={'name': '增加TE值', 'chunk id': 'B'})
    
    graph.add_node('entity_3',
                   label='entity',
                   level=2,
                   properties={'name': '延长TE', 'chunk id': 'C'})
    
    # 添加边：这些边连接的节点都在同一个cluster中
    graph.add_edge('entity_2', 'entity_1', relation='相同概念')  # 增加TE值 → 延长TE值
    graph.add_edge('entity_3', 'entity_1', relation='相同概念')  # 延长TE → 延长TE值
    graph.add_edge('entity_2', 'entity_3', relation='相同概念')  # 增加TE值 → 延长TE
    
    # 再添加一些正常的边
    graph.add_node('entity_center',
                   label='entity',
                   level=2,
                   properties={'name': '魔角效应', 'chunk id': 'X'})
    
    graph.add_edge('entity_1', 'entity_center', relation='解决方案为')
    
    return graph


def create_self_loop_dedup_results() -> list:
    """创建去重结果：所有TE相关节点都在一个cluster"""
    return [
        {
            "head_node": {
                "label": "entity",
                "properties": {"name": "任意", "chunk id": "xxx"}
            },
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
                        "延长TE值 (chunk id: A) [entity]"  # 代表
                    ],
                    "llm_judge_reason": "三个节点表示相同概念"
                }
            },
            "deduped_tails": ["延长TE值 (chunk id: A) [entity]"]
        }
    ]


def main():
    """测试自环情况"""
    print("=" * 70)
    print("测试自环情况：u和v都映射到同一个代表节点")
    print("=" * 70)
    
    # 创建测试图
    print("\n1. 创建原始图...")
    graph = create_self_loop_test_graph()
    original_graph = graph.copy()
    
    print(f"   节点数: {graph.number_of_nodes()}")
    print(f"   边数: {graph.number_of_edges()}")
    
    print("\n   原始边:")
    for u, v, data in graph.edges(data=True):
        u_data = graph.nodes[u]
        v_data = graph.nodes[v]
        u_name = u_data['properties']['name']
        v_name = v_data['properties']['name']
        relation = data.get('relation', '')
        print(f"     {u_name} --{relation}--> {v_name}")
    
    # 创建去重结果
    print("\n2. 去重设置...")
    dedup_results = create_self_loop_dedup_results()
    print("   Cluster: [增加TE值, 延长TE, 延长TE值]")
    print("   代表节点: 延长TE值")
    
    # 应用去重
    print("\n3. 应用去重...")
    applicator = TailDedupApplicator(graph)
    stats = applicator.apply_all(dedup_results)
    
    print("\n   统计:")
    for key, value in stats.items():
        print(f"     {key}: {value}")
    
    # 分析结果
    print("\n4. 结果分析...")
    print(f"   最终节点数: {graph.number_of_nodes()}")
    print(f"   最终边数: {graph.number_of_edges()}")
    
    print("\n   最终边:")
    has_self_loop = False
    for u, v, data in graph.edges(data=True):
        u_data = graph.nodes[u]
        v_data = graph.nodes[v]
        u_name = u_data['properties']['name']
        v_name = v_data['properties']['name']
        relation = data.get('relation', '')
        
        edge_str = f"     {u_name} --{relation}--> {v_name}"
        
        # 检查是否是自环
        if u == v:
            edge_str += "  ⚠️  自环！"
            has_self_loop = True
        
        print(edge_str)
    
    # 详细分析
    print("\n" + "=" * 70)
    print("详细分析")
    print("=" * 70)
    
    print("\n原始边的转换:")
    print("  1. 增加TE值 --相同概念--> 延长TE值")
    print("     ↓ 替换 (增加TE值 → 延长TE值, 延长TE值 → 延长TE值)")
    print("     = 延长TE值 --相同概念--> 延长TE值  ⚠️ 自环！")
    
    print("\n  2. 延长TE --相同概念--> 延长TE值")
    print("     ↓ 替换 (延长TE → 延长TE值, 延长TE值 → 延长TE值)")
    print("     = 延长TE值 --相同概念--> 延长TE值  ⚠️ 自环（重复）")
    
    print("\n  3. 增加TE值 --相同概念--> 延长TE")
    print("     ↓ 替换 (增加TE值 → 延长TE值, 延长TE → 延长TE值)")
    print("     = 延长TE值 --相同概念--> 延长TE值  ⚠️ 自环（重复）")
    
    print("\n去重检查:")
    print("  - 三条边都变成同一个自环")
    print("  - 去重机制会保留一条")
    print("  - 结果: 只有1条自环边")
    
    print("\n" + "=" * 70)
    print("结论")
    print("=" * 70)
    
    if has_self_loop:
        print("\n✅ 当前行为: 创建自环")
        print("\n   优点:")
        print("     - 保留了关系信息")
        print("     - 明确表示节点与自身的关系")
        print("\n   缺点:")
        print("     - 可能不符合某些应用场景")
        print("     - 自环可能被认为是冗余信息")
        print("\n   适用场景:")
        print("     - 表示自反关系（如：等价于、相同概念）")
        print("     - 图论分析（某些算法需要自环）")
        print("\n   不适用场景:")
        print("     - 不希望有自环的图")
        print("     - 自环被认为是无意义的")
    else:
        print("\n✅ 自环已被去除")
    
    print("\n" + "=" * 70)
    print("建议的处理选项")
    print("=" * 70)
    
    print("\n选项1: 保留自环（当前行为）")
    print("  - 适合: 需要表示自反关系的场景")
    print("  - 代码: 不需要修改")
    
    print("\n选项2: 删除自环")
    print("  - 适合: 不需要自环的场景")
    print("  - 代码: 在 apply_to_edges() 中添加检查")
    print("    if u_rep == v_rep:")
    print("        continue  # 跳过自环")
    
    print("\n选项3: 可配置")
    print("  - 适合: 需要灵活性的场景")
    print("  - 代码: 添加参数 remove_self_loops=True/False")
    
    print("\n" + "=" * 70)
    
    return 0


if __name__ == "__main__":
    exit(main())
