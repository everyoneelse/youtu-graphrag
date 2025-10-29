#!/usr/bin/env python3
"""
测试完整的全图去重（head和tail都去重）

这个测试验证去重不仅对tail节点生效，也对head节点生效。
"""

import json
import tempfile
from pathlib import Path

import networkx as nx

from apply_tail_dedup_results import TailDedupApplicator
from utils import graph_processor


def create_test_graph_with_head_dedup() -> nx.MultiDiGraph:
    """
    创建一个测试图，其中待去重的节点既出现在head位置，也出现在tail位置。
    
    结构:
    - 增加TE值 --解决方案为--> 魔角效应
    - 延长TE --解决方案为--> 魔角效应  
    - 延长TE值 --解决方案为--> 魔角效应
    
    - 魔角效应 --解决方案为--> 增加TE值
    - 魔角效应 --解决方案为--> 延长TE
    - 魔角效应 --解决方案为--> 延长TE值
    
    所有三个TE相关节点都应该映射到"延长TE值"
    """
    graph = nx.MultiDiGraph()
    
    # 添加中心节点
    graph.add_node('entity_center', 
                   label='entity',
                   level=2,
                   properties={'name': '魔角效应', 'chunk id': 'Dwjxk2M8'})
    
    # 添加TE相关节点
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
    
    # 添加边：TE节点作为HEAD指向中心节点
    graph.add_edge('entity_1', 'entity_center', relation='解决方案为')
    graph.add_edge('entity_2', 'entity_center', relation='解决方案为')
    graph.add_edge('entity_3', 'entity_center', relation='解决方案为')
    
    # 添加边：中心节点作为HEAD指向TE节点（tail位置）
    graph.add_edge('entity_center', 'entity_1', relation='包括')
    graph.add_edge('entity_center', 'entity_2', relation='包括')
    graph.add_edge('entity_center', 'entity_3', relation='包括')
    
    return graph


def create_test_dedup_results_full() -> list:
    """创建测试去重结果"""
    return [
        {
            "head_node": {
                "label": "entity",
                "properties": {
                    "name": "任意节点",
                    "chunk id": "xxx"
                }
            },
            "relation": "任意关系",
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
                        "延长TE值 (chunk id: A) [entity]"  # 代表节点
                    ],
                    "llm_judge_reason": "三个节点表示相同概念"
                }
            },
            "deduped_tails": [
                "延长TE值 (chunk id: A) [entity]"
            ]
        }
    ]


def verify_full_deduplication(graph: nx.MultiDiGraph, original_graph: nx.MultiDiGraph) -> bool:
    """
    验证全图去重是否正确应用。
    
    检查：
    1. head位置的节点是否被替换
    2. tail位置的节点是否被替换
    3. 最终只保留代表节点
    """
    all_passed = True
    
    print("\n" + "=" * 60)
    print("全图去重验证结果")
    print("=" * 60)
    
    # 检查1: 图大小
    original_nodes = original_graph.number_of_nodes()
    deduped_nodes = graph.number_of_nodes()
    original_edges = original_graph.number_of_edges()
    deduped_edges = graph.number_of_edges()
    
    print(f"\n1. 图大小变化:")
    print(f"   节点: {original_nodes} → {deduped_nodes}")
    print(f"   边:   {original_edges} → {deduped_edges}")
    
    # 应该删除2个节点（增加TE值, 延长TE）
    if deduped_nodes < original_nodes:
        print(f"   ✓ PASS: 节点减少了 {original_nodes - deduped_nodes} 个")
    else:
        print(f"   ✗ FAIL: 节点数量未减少")
        all_passed = False
    
    # 检查2: 代表节点存在
    print("\n2. 检查代表节点存在:")
    rep_found = False
    for node_id, data in graph.nodes(data=True):
        props = data.get('properties', {})
        if props.get('name') == '延长TE值' and props.get('chunk id') == 'A':
            rep_found = True
            print(f"   ✓ 找到代表节点: 延长TE值 (chunk: A)")
            break
    
    if not rep_found:
        print(f"   ✗ FAIL: 代表节点不存在")
        all_passed = False
    
    # 检查3: 被替换的节点不存在
    print("\n3. 检查被替换节点已删除:")
    removed_nodes = [
        ('增加TE值', 'B'),
        ('延长TE', 'C')
    ]
    
    removed_count = 0
    for name, chunk_id in removed_nodes:
        found = False
        for node_id, data in graph.nodes(data=True):
            props = data.get('properties', {})
            if props.get('name') == name and props.get('chunk id') == chunk_id:
                found = True
                print(f"   ✗ {name} (chunk: {chunk_id}) 仍然存在")
                all_passed = False
                break
        
        if not found:
            print(f"   ✓ {name} (chunk: {chunk_id}) 已删除")
            removed_count += 1
    
    # 检查4: HEAD位置的替换
    print("\n4. 检查HEAD位置的节点替换:")
    print("   查找: 延长TE值 → 魔角效应")
    
    head_edges_found = 0
    for u, v, data in graph.edges(data=True):
        u_data = graph.nodes[u]
        v_data = graph.nodes[v]
        
        u_props = u_data.get('properties', {})
        v_props = v_data.get('properties', {})
        
        # 查找代表节点作为HEAD的边
        if (u_props.get('name') == '延长TE值' and 
            u_props.get('chunk id') == 'A' and
            v_props.get('name') == '魔角效应'):
            relation = data.get('relation', '')
            print(f"   ✓ 找到: 延长TE值 --{relation}--> 魔角效应")
            head_edges_found += 1
    
    if head_edges_found > 0:
        print(f"   ✓ PASS: 找到 {head_edges_found} 条HEAD位置的边")
    else:
        print(f"   ✗ FAIL: 没有找到HEAD位置的边")
        all_passed = False
    
    # 检查5: TAIL位置的替换
    print("\n5. 检查TAIL位置的节点替换:")
    print("   查找: 魔角效应 → 延长TE值")
    
    tail_edges_found = 0
    for u, v, data in graph.edges(data=True):
        u_data = graph.nodes[u]
        v_data = graph.nodes[v]
        
        u_props = u_data.get('properties', {})
        v_props = v_data.get('properties', {})
        
        # 查找代表节点作为TAIL的边
        if (u_props.get('name') == '魔角效应' and
            v_props.get('name') == '延长TE值' and 
            v_props.get('chunk id') == 'A'):
            relation = data.get('relation', '')
            print(f"   ✓ 找到: 魔角效应 --{relation}--> 延长TE值")
            tail_edges_found += 1
    
    if tail_edges_found > 0:
        print(f"   ✓ PASS: 找到 {tail_edges_found} 条TAIL位置的边")
    else:
        print(f"   ✗ FAIL: 没有找到TAIL位置的边")
        all_passed = False
    
    # 检查6: 不应该存在被替换节点的边
    print("\n6. 检查被替换节点的边已删除:")
    bad_edges = []
    for u, v, data in graph.edges(data=True):
        u_data = graph.nodes[u]
        v_data = graph.nodes[v]
        
        u_props = u_data.get('properties', {})
        v_props = v_data.get('properties', {})
        
        # 检查是否还有增加TE值或延长TE的边
        if u_props.get('name') in ['增加TE值', '延长TE']:
            bad_edges.append(f"{u_props.get('name')} → {v_props.get('name')}")
        if v_props.get('name') in ['增加TE值', '延长TE']:
            bad_edges.append(f"{u_props.get('name')} → {v_props.get('name')}")
    
    if len(bad_edges) == 0:
        print(f"   ✓ PASS: 没有找到被替换节点的边")
    else:
        print(f"   ✗ FAIL: 找到 {len(bad_edges)} 条不应该存在的边:")
        for edge in bad_edges[:5]:  # 只显示前5条
            print(f"     - {edge}")
        all_passed = False
    
    # 总结
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 全图去重验证通过！")
    else:
        print("❌ 全图去重验证失败！")
    print("=" * 60 + "\n")
    
    return all_passed


def main():
    """运行测试"""
    print("=" * 60)
    print("测试完整的全图去重（HEAD + TAIL）")
    print("=" * 60)
    
    # 创建测试图
    print("\n创建测试图...")
    graph = create_test_graph_with_head_dedup()
    original_graph = graph.copy()
    
    print(f"  原始节点: {graph.number_of_nodes()}")
    print(f"  原始边: {graph.number_of_edges()}")
    
    print("\n原始图结构:")
    print("  HEAD位置出现的TE节点:")
    for u, v, data in graph.edges(data=True):
        u_data = graph.nodes[u]
        u_props = u_data.get('properties', {})
        if 'TE' in u_props.get('name', ''):
            print(f"    {u_props.get('name')} → ...")
    
    print("\n  TAIL位置出现的TE节点:")
    for u, v, data in graph.edges(data=True):
        v_data = graph.nodes[v]
        v_props = v_data.get('properties', {})
        if 'TE' in v_props.get('name', ''):
            print(f"    ... → {v_props.get('name')}")
    
    # 创建去重结果
    print("\n创建去重结果...")
    dedup_results = create_test_dedup_results_full()
    print(f"  Cluster数: {sum(len(g['dedup_results']) for g in dedup_results)}")
    print(f"  代表节点: 延长TE值 (chunk: A)")
    
    # 应用去重
    print("\n应用全图去重...")
    applicator = TailDedupApplicator(graph)
    stats = applicator.apply_all(dedup_results)
    
    print("\n去重统计:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print(f"\n最终节点: {graph.number_of_nodes()}")
    print(f"最终边: {graph.number_of_edges()}")
    
    # 验证结果
    success = verify_full_deduplication(graph, original_graph)
    
    # 显示最终图结构
    print("\n最终图结构:")
    for u, v, data in graph.edges(data=True):
        u_data = graph.nodes[u]
        v_data = graph.nodes[v]
        u_props = u_data.get('properties', {})
        v_props = v_data.get('properties', {})
        relation = data.get('relation', '')
        print(f"  {u_props.get('name')} --{relation}--> {v_props.get('name')}")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
