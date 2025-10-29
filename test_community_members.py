#!/usr/bin/env python3
"""
测试community成员处理

验证：当A和B都在community C中，且A→B去重后，
community的处理是否正确
"""

import json
import networkx as nx

from apply_tail_dedup_results import TailDedupApplicator
from utils import graph_processor


def create_community_test_graph() -> nx.MultiDiGraph:
    """
    创建包含community的测试图
    
    结构：
    - A和B都属于Community C
    - A和B是等价的（B是代表）
    """
    graph = nx.MultiDiGraph()
    
    # 添加实体节点
    graph.add_node('entity_A',
                   label='entity',
                   level=2,
                   properties={'name': 'TE参数A', 'chunk id': 'A'})
    
    graph.add_node('entity_B',
                   label='entity',
                   level=2,
                   properties={'name': 'TE参数B', 'chunk id': 'B'})
    
    # 添加community节点
    # 关键问题：community的properties中是否有members字段？
    community_props = {
        'name': 'TE参数社区',
        'description': 'MRI TE相关参数的社区'
    }
    
    # 可能的情况1：community有members列表
    # community_props['members'] = ['TE参数A', 'TE参数B']
    
    graph.add_node('community_C',
                   label='community',
                   level=4,
                   properties=community_props)
    
    # 通过边表示成员关系
    graph.add_edge('entity_A', 'community_C', relation='belongs_to')
    graph.add_edge('entity_B', 'community_C', relation='belongs_to')
    
    return graph


def create_community_dedup_results() -> list:
    """创建去重结果：A→B"""
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


def main():
    """主测试函数"""
    print("=" * 70)
    print("Community成员处理测试")
    print("=" * 70)
    
    # 创建测试图
    print("\n1. 创建原始图...")
    graph = create_community_test_graph()
    
    print(f"\n原始图结构:")
    print(f"  节点数: {graph.number_of_nodes()}")
    print(f"  边数: {graph.number_of_edges()}")
    
    # 打印community信息
    print(f"\n原始Community节点:")
    for node_id, data in graph.nodes(data=True):
        if data.get('label') == 'community':
            print(f"  节点ID: {node_id}")
            print(f"  Properties: {data.get('properties')}")
            
            # 检查是否有members字段
            if 'members' in data.get('properties', {}):
                print(f"  ⚠️  Community properties中有members字段!")
                print(f"    members: {data['properties']['members']}")
            else:
                print(f"  ✓ Community properties中没有members字段")
    
    # 打印成员关系（通过边）
    print(f"\n原始成员关系（通过边）:")
    for u, v, data in graph.edges(data=True):
        u_data = graph.nodes[u]
        v_data = graph.nodes[v]
        if v_data.get('label') == 'community':
            print(f"  {u_data['properties']['name']} --{data.get('relation')}--> {v_data['properties']['name']}")
    
    # 应用去重
    print("\n" + "=" * 70)
    print("2. 应用去重（A → B）...")
    print("=" * 70)
    
    dedup_results = create_community_dedup_results()
    applicator = TailDedupApplicator(graph)
    stats = applicator.apply_all(dedup_results)
    
    print(f"\n统计:")
    for key, value in stats.items():
        if value > 0:
            print(f"  {key}: {value}")
    
    # 检查结果
    print("\n" + "=" * 70)
    print("3. 检查处理后的结果")
    print("=" * 70)
    
    print(f"\n处理后图结构:")
    print(f"  节点数: {graph.number_of_nodes()}")
    print(f"  边数: {graph.number_of_edges()}")
    
    # 检查community节点
    print(f"\n处理后Community节点:")
    community_node_id = None
    for node_id, data in graph.nodes(data=True):
        if data.get('label') == 'community':
            community_node_id = node_id
            print(f"  节点ID: {node_id}")
            print(f"  Properties: {data.get('properties')}")
            
            if 'members' in data.get('properties', {}):
                print(f"  ⚠️  Community properties中有members字段!")
                print(f"    members: {data['properties']['members']}")
                print(f"    ❌ 问题：members字段没有被更新！")
            else:
                print(f"  ✓ Community properties中没有members字段（正常）")
    
    # 检查成员关系（通过边）
    print(f"\n处理后成员关系（通过边）:")
    member_edges = []
    for u, v, data in graph.edges(data=True):
        u_data = graph.nodes[u]
        v_data = graph.nodes[v]
        if v_data.get('label') == 'community':
            member_name = u_data['properties']['name']
            relation = data.get('relation')
            community_name = v_data['properties']['name']
            print(f"  {member_name} --{relation}--> {community_name}")
            member_edges.append(member_name)
    
    # 验证
    print("\n" + "=" * 70)
    print("4. 验证结果")
    print("=" * 70)
    
    all_passed = True
    
    # 检查1：A是否被删除
    print("\n检查1: A节点是否被删除？")
    a_exists = any(d['properties']['name'] == 'TE参数A' 
                   for _, d in graph.nodes(data=True))
    if not a_exists:
        print("  ✅ A节点已被删除")
    else:
        print("  ❌ A节点仍然存在")
        all_passed = False
    
    # 检查2：B是否存在
    print("\n检查2: B节点是否存在？")
    b_exists = any(d['properties']['name'] == 'TE参数B' 
                   for _, d in graph.nodes(data=True))
    if b_exists:
        print("  ✅ B节点存在")
    else:
        print("  ❌ B节点不存在")
        all_passed = False
    
    # 检查3：通过边表示的成员关系
    print("\n检查3: Community的成员关系（通过边）？")
    if len(member_edges) == 1 and member_edges[0] == 'TE参数B':
        print("  ✅ 只有B在community中（边去重成功）")
    elif len(member_edges) == 2:
        print(f"  ❌ 有2个成员：{member_edges}")
        print("  问题：边没有正确去重")
        all_passed = False
    else:
        print(f"  ⚠️  成员数：{len(member_edges)}, 成员：{member_edges}")
        all_passed = False
    
    # 检查4：如果community有members属性
    print("\n检查4: Community节点的properties中的members字段？")
    has_members_prop = False
    for node_id, data in graph.nodes(data=True):
        if data.get('label') == 'community':
            if 'members' in data.get('properties', {}):
                has_members_prop = True
                members_list = data['properties']['members']
                print(f"  ⚠️  Community有members属性: {members_list}")
                if 'TE参数A' in str(members_list):
                    print(f"  ❌ members中还包含A！")
                    print(f"  问题：properties中的members字段没有被更新")
                    all_passed = False
                else:
                    print(f"  ✓ members中不包含A")
    
    if not has_members_prop:
        print("  ✓ Community没有members属性（通过边表示成员关系）")
    
    # 总结
    print("\n" + "=" * 70)
    print("结论")
    print("=" * 70)
    
    if all_passed:
        print("\n✅ Community处理正确！")
    else:
        print("\n❌ Community处理有问题！")
    
    print("\n当前实现：")
    print("  1. 处理通过【边】表示的成员关系 ✓")
    print("     原始：A → community, B → community")
    print("     结果：B → community (去重)")
    
    print("\n  2. 处理community节点properties中的members字段？")
    if has_members_prop:
        print("     ❌ 如果存在members字段，当前实现【不会】更新它")
        print("     建议：需要添加逻辑来更新properties中的members")
    else:
        print("     ✓ 当前图中community没有members字段，通过边表示即可")
    
    print("\n" + "=" * 70)
    print("用户的问题")
    print("=" * 70)
    print("\n问：A==B，A和B都属于C，去重后是否从community的member中删掉A？")
    print("\n答：")
    print("  - 如果member关系通过【边】表示：✅ 会去重，只保留B")
    print("  - 如果member存储在community的【properties】中：❌ 当前不会更新")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
