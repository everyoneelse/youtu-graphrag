"""
知识发现示例 - Knowledge Discovery Example

展示如何使用知识发现模块来：
1. 检测可连接的三元组
2. 使用事件建模模式重构知识图谱
3. 分析和可视化结果

使用示例：
    python example_knowledge_discovery.py
"""

import json
import networkx as nx
from utils.knowledge_discovery import KnowledgeDiscovery, discover_and_reconstruct
from utils.graph_processor import save_graph_to_json, load_graph_from_json
from utils.logger import logger
from utils.call_llm_api import LLM
from config import get_config


def create_example_graph():
    """创建示例知识图谱（MR伪影相关）"""
    graph = nx.MultiDiGraph()
    
    # 添加实体节点
    entities = [
        ('entity_0', '化学位移伪影', '一种MRI成像伪影'),
        ('entity_1', '采用高带宽', '解决化学位移伪影的方法'),
        ('entity_2', '高带宽', '扫描参数设置'),
        ('entity_3', '信噪比', 'MRI图像质量指标'),
        ('entity_4', '带宽', 'MRI扫描参数'),
        ('entity_5', '运动伪影', '另一种MRI伪影'),
        ('entity_6', '使用快速序列', '减少运动伪影的方法'),
        ('entity_7', '快速序列', '一种扫描序列类型'),
        ('entity_8', '扫描时间', 'MRI扫描的时间长度'),
    ]
    
    for node_id, name, description in entities:
        graph.add_node(
            node_id,
            label='entity',
            properties={'name': name, 'description': description},
            level=2
        )
    
    # 添加三元组关系
    triples = [
        ('entity_0', 'entity_1', '解决方案为'),  # 化学位移伪影 -> 采用高带宽
        ('entity_1', 'entity_2', '设置为'),      # 采用高带宽 -> 高带宽
        ('entity_2', 'entity_3', '影响'),        # 高带宽 -> 信噪比
        ('entity_2', 'entity_4', '是一种'),      # 高带宽 -> 带宽
        ('entity_5', 'entity_6', '解决方案为'),  # 运动伪影 -> 使用快速序列
        ('entity_6', 'entity_7', '设置为'),      # 使用快速序列 -> 快速序列
        ('entity_7', 'entity_8', '影响'),        # 快速序列 -> 扫描时间
    ]
    
    for u, v, relation in triples:
        graph.add_edge(u, v, relation=relation)
    
    logger.info(f"创建示例图谱：{graph.number_of_nodes()} 个节点，{graph.number_of_edges()} 条边")
    
    return graph


def example_basic_usage():
    """示例1：基本使用方法"""
    print("\n" + "="*80)
    print("示例1：基本使用方法")
    print("="*80)
    
    # 创建示例图谱
    graph = create_example_graph()
    
    # 初始化知识发现模块
    kd = KnowledgeDiscovery()
    kd.load_graph(graph)
    
    # 查找可连接的三元组
    print("\n步骤1：查找可连接的三元组")
    print("-" * 80)
    connectable_pairs = kd.find_connectable_triples()
    
    if connectable_pairs:
        print(f"\n找到 {len(connectable_pairs)} 对可连接的三元组：\n")
        for i, pair in enumerate(connectable_pairs, 1):
            print(f"第 {i} 对：")
            print(f"  三元组1: {pair['triple1']}")
            print(f"  三元组2: {pair['triple2']}")
            print(f"  重叠实体: {pair['overlap_entity']}")
            print(f"  连接类型: {pair['connection_type']}")
            
            # 分解重叠实体
            decomposition = kd.decompose_entity(pair['overlap_entity'])
            print(f"  实体分解:")
            print(f"    - 类型: {decomposition['type']}")
            print(f"    - 对象实体: {decomposition['object']}")
            if decomposition['state']:
                print(f"    - 状态实体: {decomposition['state']}")
            if decomposition['action']:
                print(f"    - 动作实体: {decomposition['action']}")
            print()
    else:
        print("未找到可连接的三元组对")
    
    # 重构图谱
    print("\n步骤2：使用事件建模模式重构图谱")
    print("-" * 80)
    reconstructed_graph = kd.reconstruct_with_event_modeling(connectable_pairs)
    
    print(f"\n重构结果：")
    print(f"  原始图谱：{graph.number_of_nodes()} 个节点，{graph.number_of_edges()} 条边")
    print(f"  重构图谱：{reconstructed_graph.number_of_nodes()} 个节点，{reconstructed_graph.number_of_edges()} 条边")
    print(f"  新增节点：{reconstructed_graph.number_of_nodes() - graph.number_of_nodes()} 个")
    print(f"  新增边：{reconstructed_graph.number_of_edges() - graph.number_of_edges()} 条")
    
    # 显示新增的三元组
    print("\n新增的三元组：")
    original_edges = set((u, v, d.get('relation')) for u, v, d in graph.edges(data=True))
    new_edges = set((u, v, d.get('relation')) for u, v, d in reconstructed_graph.edges(data=True))
    added_edges = new_edges - original_edges
    
    for u, v, relation in added_edges:
        u_name = reconstructed_graph.nodes[u]['properties']['name']
        v_name = reconstructed_graph.nodes[v]['properties']['name']
        print(f"  [{u_name}] --{relation}--> [{v_name}]")
    
    return graph, reconstructed_graph, connectable_pairs


def example_with_export():
    """示例2：导出分析结果"""
    print("\n" + "="*80)
    print("示例2：导出分析结果")
    print("="*80)
    
    # 创建示例图谱
    graph = create_example_graph()
    
    # 使用便捷函数进行知识发现和重构
    results = discover_and_reconstruct(
        graph=graph,
        output_dir='./output/knowledge_discovery'
    )
    
    print(f"\n分析完成！")
    print(f"统计信息：")
    for key, value in results['stats'].items():
        print(f"  {key}: {value}")
    
    print(f"\n结果已导出到：./output/knowledge_discovery/")
    print(f"  - knowledge_discovery_results.json (JSON格式的分析结果)")
    print(f"  - connectable_pairs_visualization.png (可视化图表)")
    
    return results


def example_entity_decomposition():
    """示例3：实体分解"""
    print("\n" + "="*80)
    print("示例3：实体分解示例")
    print("="*80)
    
    kd = KnowledgeDiscovery()
    
    # 测试各种实体
    test_entities = [
        '高带宽',
        '采用高带宽',
        '带宽',
        '提高信噪比',
        '低剂量',
        '使用快速序列',
        '优化参数',
        '增加对比度',
    ]
    
    print("\n实体分解结果：\n")
    print(f"{'实体':<20} {'类型':<10} {'对象实体':<15} {'状态/动作':<15}")
    print("-" * 80)
    
    for entity in test_entities:
        decomposition = kd.decompose_entity(entity)
        state_or_action = decomposition.get('state') or decomposition.get('action') or '-'
        print(f"{entity:<20} {decomposition['type']:<10} {decomposition['object']:<15} {state_or_action:<15}")


def example_custom_graph():
    """示例4：使用自定义图谱"""
    print("\n" + "="*80)
    print("示例4：从JSON文件加载图谱并进行知识发现")
    print("="*80)
    
    # 这里可以加载实际的图谱文件
    # graph = load_graph_from_json('path/to/your/graph.json')
    
    # 为了演示，我们创建一个示例图谱并保存
    graph = create_example_graph()
    save_graph_to_json(graph, './output/example_graph.json')
    print("\n示例图谱已保存到：./output/example_graph.json")
    
    # 加载图谱
    loaded_graph = load_graph_from_json('./output/example_graph.json')
    print(f"已加载图谱：{loaded_graph.number_of_nodes()} 个节点，{loaded_graph.number_of_edges()} 条边")
    
    # 进行知识发现
    results = discover_and_reconstruct(
        graph=loaded_graph,
        output_dir='./output/knowledge_discovery_custom'
    )
    
    print(f"\n知识发现完成！")
    print(f"发现 {results['stats']['connectable_pairs_count']} 对可连接的三元组")
    
    # 保存重构后的图谱
    save_graph_to_json(
        results['reconstructed_graph'], 
        './output/reconstructed_graph.json'
    )
    print(f"\n重构后的图谱已保存到：./output/reconstructed_graph.json")


def example_with_llm():
    """示例5：使用LLM增强分析（可选）"""
    print("\n" + "="*80)
    print("示例5：使用LLM增强分析")
    print("="*80)
    
    try:
        # 获取配置并初始化LLM客户端
        config = get_config()
        llm_client = LLM(config=config)
        
        # 创建示例图谱
        graph = create_example_graph()
        
        # 使用LLM进行知识发现
        print("\n使用LLM进行智能分析...")
        results = discover_and_reconstruct(
            graph=graph,
            llm_client=llm_client,
            output_dir='./output/knowledge_discovery_llm'
        )
        
        print(f"\nLLM增强分析完成！")
        
        # 显示LLM分析结果
        if results['connectable_pairs']:
            print("\nLLM分析结果示例：")
            for i, pair in enumerate(results['connectable_pairs'][:2], 1):
                if 'llm_analysis' in pair:
                    print(f"\n第 {i} 对三元组的LLM分析：")
                    print(json.dumps(pair['llm_analysis'], ensure_ascii=False, indent=2))
        
    except Exception as e:
        print(f"\n注意：LLM分析需要配置LLM API")
        print(f"错误信息：{e}")
        print("您可以跳过此示例，或配置LLM后重试")


def main():
    """运行所有示例"""
    print("\n" + "="*80)
    print("知识发现示例程序")
    print("="*80)
    print("\n本程序展示如何使用知识发现模块来：")
    print("1. 检测可连接的三元组")
    print("2. 使用事件建模模式（对象、状态、动作）重构知识图谱")
    print("3. 导出和可视化分析结果")
    
    # 确保输出目录存在
    import os
    os.makedirs('./output', exist_ok=True)
    
    # 运行示例
    try:
        # 示例1：基本使用
        example_basic_usage()
        
        # 示例2：导出结果
        example_with_export()
        
        # 示例3：实体分解
        example_entity_decomposition()
        
        # 示例4：自定义图谱
        example_custom_graph()
        
        # 示例5：LLM增强（可选）
        # 取消注释以下行来运行LLM示例
        # example_with_llm()
        
        print("\n" + "="*80)
        print("所有示例运行完成！")
        print("="*80)
        print("\n您可以查看 ./output/ 目录中的结果文件")
        
    except Exception as e:
        logger.error(f"运行示例时出错：{e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
