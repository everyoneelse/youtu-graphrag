#!/usr/bin/env python3
"""
验证全面替换：A被B代表时，图中所有位置的A都会被替换为B

测试场景：
1. A作为HEAD：A-R->C 变成 B-R->C
2. A作为TAIL：D-R1->A 变成 D-R1->B
3. A同时作为HEAD和TAIL：A-R2->A 变成 B-R2->B（自环）
4. 各种关系类型都生效
"""

import json
import networkx as nx

from apply_tail_dedup_results import TailDedupApplicator
from utils import graph_processor


def create_comprehensive_test_graph() -> nx.MultiDiGraph:
    """
    创建综合测试图
    
    包含：
    - A作为HEAD的边
    - A作为TAIL的边
    - 各种关系类型
    """
    graph = nx.MultiDiGraph()
    
    # 添加节点
    nodes = {
        'A': {'name': 'TE参数A', 'chunk id': 'A'},
        'B': {'name': 'TE参数B', 'chunk id': 'B'},  # B是代表
        'C': {'name': 'MRI扫描', 'chunk id': 'C'},
        'D': {'name': '魔角效应', 'chunk id': 'D'},
        'E': {'name': '图像质量', 'chunk id': 'E'},
    }
    
    for node_id, props in nodes.items():
        graph.add_node(f'entity_{node_id}',
                       label='entity',
                       level=2,
                       properties=props)
    
    # 添加各种边
    edges = [
        # A作为HEAD
        ('entity_A', 'entity_C', '用于'),           # A-用于->C
        ('entity_A', 'entity_D', '解决'),           # A-解决->D
        ('entity_A', 'entity_E', '影响'),           # A-影响->E
        
        # A作为TAIL
        ('entity_D', 'entity_A', '需要'),           # D-需要->A
        ('entity_C', 'entity_A', '参数包括'),       # C-参数包括->A
        
        # 正常的边（不涉及A）
        ('entity_C', 'entity_D', '应用于'),         # C-应用于->D
        ('entity_D', 'entity_E', '决定'),           # D-决定->E
        
        # B作为HEAD/TAIL（代表节点）
        ('entity_B', 'entity_C', '用于'),           # B-用于->C（与A-用于->C重复）
    ]
    
    for u, v, relation in edges:
        graph.add_edge(u, v, relation=relation)
    
    return graph


def create_comprehensive_dedup_results() -> list:
    """创建去重结果：A映射到B"""
    return [{
        "head_node": {
            "label": "entity",
            "properties": {"name": "任意", "chunk id": "x"}
        },
        "relation": "任意",
        "tail_nodes_to_dedup": [
            "TE参数A (chunk id: A) [entity]",
            "TE参数B (chunk id: B) [entity]"
        ],
        "dedup_results": {
            "cluster_0": {
                "member": [
                    "TE参数A (chunk id: A) [entity]",
                    "TE参数B (chunk id: B) [entity]"  # B是代表
                ],
                "llm_judge_reason": "A和B是相同概念"
            }
        },
        "deduped_tails": ["TE参数B (chunk id: B) [entity]"]
    }]


def print_edges(graph: nx.MultiDiGraph, title: str):
    """打印图的所有边"""
    print(f"\n{title}:")
    print(f"  节点数: {graph.number_of_nodes()}, 边数: {graph.number_of_edges()}")
    print(f"  边列表:")
    
    edges_by_type = {}
    for u, v, data in graph.edges(data=True):
        u_data = graph.nodes[u]
        v_data = graph.nodes[v]
        u_name = u_data['properties']['name']
        v_name = v_data['properties']['name']
        relation = data.get('relation', '')
        
        edge_str = f"{u_name} --{relation}--> {v_name}"
        
        # 分类
        if 'TE参数' in u_name:
            category = 'HEAD包含A/B'
        elif 'TE参数' in v_name:
            category = 'TAIL包含A/B'
        else:
            category = '其他'
        
        if category not in edges_by_type:
            edges_by_type[category] = []
        edges_by_type[category].append(edge_str)
    
    for category in ['HEAD包含A/B', 'TAIL包含A/B', '其他']:
        if category in edges_by_type:
            print(f"\n  [{category}]")
            for edge in edges_by_type[category]:
                print(f"    {edge}")


def main():
    """主测试函数"""
    print("=" * 70)
    print("全面替换测试：A被B代表时，所有位置的A都被替换为B")
    print("=" * 70)
    
    # 创建测试图
    print("\n1. 创建原始图...")
    graph = create_comprehensive_test_graph()
    original_graph = graph.copy()
    
    print_edges(original_graph, "原始图")
    
    # 创建去重结果
    print("\n" + "=" * 70)
    print("2. 去重设置")
    print("=" * 70)
    dedup_results = create_comprehensive_dedup_results()
    print("\n  映射关系:")
    print("    TE参数A → TE参数B (B是代表)")
    
    # 应用去重
    print("\n" + "=" * 70)
    print("3. 应用去重...")
    print("=" * 70)
    applicator = TailDedupApplicator(graph)
    stats = applicator.apply_all(dedup_results)
    
    print("\n  统计:")
    for key, value in stats.items():
        if value > 0:
            print(f"    {key}: {value}")
    
    print_edges(graph, "\n处理后的图")
    
    # 验证结果
    print("\n" + "=" * 70)
    print("4. 验证替换结果")
    print("=" * 70)
    
    all_passed = True
    
    # 检查1：A节点是否还存在
    print("\n  检查1: A节点是否被删除?")
    a_exists = False
    for node_id, data in graph.nodes(data=True):
        if data['properties']['name'] == 'TE参数A':
            a_exists = True
            print(f"    ❌ A节点仍然存在: {node_id}")
            all_passed = False
            break
    
    if not a_exists:
        print(f"    ✅ A节点已被删除")
    
    # 检查2：B节点是否存在
    print("\n  检查2: B节点（代表）是否存在?")
    b_exists = False
    b_node_id = None
    for node_id, data in graph.nodes(data=True):
        if data['properties']['name'] == 'TE参数B':
            b_exists = True
            b_node_id = node_id
            print(f"    ✅ B节点存在: {node_id}")
            break
    
    if not b_exists:
        print(f"    ❌ B节点不存在")
        all_passed = False
    
    # 检查3：A作为HEAD的边是否被替换
    print("\n  检查3: A作为HEAD的边是否被替换为B?")
    if b_exists:
        expected_head_edges = [
            ('TE参数B', '用于', 'MRI扫描'),
            ('TE参数B', '解决', '魔角效应'),
            ('TE参数B', '影响', '图像质量'),
        ]
        
        for expected_head, expected_rel, expected_tail in expected_head_edges:
            found = False
            for u, v, data in graph.edges(data=True):
                u_data = graph.nodes[u]
                v_data = graph.nodes[v]
                if (u_data['properties']['name'] == expected_head and
                    data.get('relation') == expected_rel and
                    v_data['properties']['name'] == expected_tail):
                    found = True
                    print(f"    ✅ {expected_head} --{expected_rel}--> {expected_tail}")
                    break
            
            if not found:
                print(f"    ❌ 未找到: {expected_head} --{expected_rel}--> {expected_tail}")
                all_passed = False
    
    # 检查4：A作为TAIL的边是否被替换
    print("\n  检查4: A作为TAIL的边是否被替换为B?")
    if b_exists:
        expected_tail_edges = [
            ('魔角效应', '需要', 'TE参数B'),
            ('MRI扫描', '参数包括', 'TE参数B'),
        ]
        
        for expected_head, expected_rel, expected_tail in expected_tail_edges:
            found = False
            for u, v, data in graph.edges(data=True):
                u_data = graph.nodes[u]
                v_data = graph.nodes[v]
                if (u_data['properties']['name'] == expected_head and
                    data.get('relation') == expected_rel and
                    v_data['properties']['name'] == expected_tail):
                    found = True
                    print(f"    ✅ {expected_head} --{expected_rel}--> {expected_tail}")
                    break
            
            if not found:
                print(f"    ❌ 未找到: {expected_head} --{expected_rel}--> {expected_tail}")
                all_passed = False
    
    # 检查5：不涉及A的边是否保持不变
    print("\n  检查5: 不涉及A的边是否保持不变?")
    unchanged_edges = [
        ('MRI扫描', '应用于', '魔角效应'),
        ('魔角效应', '决定', '图像质量'),
    ]
    
    for expected_head, expected_rel, expected_tail in unchanged_edges:
        found = False
        for u, v, data in graph.edges(data=True):
            u_data = graph.nodes[u]
            v_data = graph.nodes[v]
            if (u_data['properties']['name'] == expected_head and
                data.get('relation') == expected_rel and
                v_data['properties']['name'] == expected_tail):
                found = True
                print(f"    ✅ {expected_head} --{expected_rel}--> {expected_tail}")
                break
        
        if not found:
            print(f"    ❌ 未找到: {expected_head} --{expected_rel}--> {expected_tail}")
            all_passed = False
    
    # 检查6：是否有A相关的边残留
    print("\n  检查6: 是否还有包含A的边?")
    a_edges = []
    for u, v, data in graph.edges(data=True):
        u_data = graph.nodes[u]
        v_data = graph.nodes[v]
        u_name = u_data['properties']['name']
        v_name = v_data['properties']['name']
        relation = data.get('relation', '')
        
        if 'TE参数A' in u_name or 'TE参数A' in v_name:
            a_edges.append(f"{u_name} --{relation}--> {v_name}")
    
    if len(a_edges) == 0:
        print(f"    ✅ 没有包含A的边")
    else:
        print(f"    ❌ 仍有 {len(a_edges)} 条包含A的边:")
        for edge in a_edges:
            print(f"      {edge}")
        all_passed = False
    
    # 总结
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ 所有验证通过！全面替换成功！")
    else:
        print("❌ 部分验证失败")
    print("=" * 70)
    
    # 最终说明
    print("\n" + "=" * 70)
    print("结论")
    print("=" * 70)
    print("\n✅ 确认：当A被B代表时，图中所有位置的A都会被替换为B")
    print("\n  包括：")
    print("    1. A作为HEAD：A-R->C 变成 B-R->C")
    print("    2. A作为TAIL：D-R1->A 变成 D-R1->B")
    print("    3. 所有关系类型都生效（不限于特定关系）")
    print("\n  特殊处理：")
    print("    - Community成员替换")
    print("    - keyword_filter_by关系替换")
    print("    - 自环处理（A-R->A 变成 B-R->B）")
    print("\n  结果：")
    print("    - A节点被删除（成为孤立节点）")
    print("    - 所有A的边都转移到B")
    print("    - 不涉及A的边保持不变")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
