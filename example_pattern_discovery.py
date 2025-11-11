"""
通用模式发现示例 - Generic Pattern Discovery Example

展示如何使用通用的模式发现框架，而不是case-by-case的硬编码方案。

核心特点：
1. 基于图结构的模式识别（而非文本模式）
2. 支持多种知识图谱设计模式
3. 可配置的模式定义系统
4. 可选的LLM驱动的智能发现
5. 从数据中学习模式的能力

使用示例：
    python example_pattern_discovery.py
"""

import json
import yaml
import networkx as nx
from utils.kg_pattern_discovery import (
    PatternDiscoveryEngine,
    ChainPattern,
    StarPattern,
    ReificationPattern,
    discover_and_optimize
)
from utils.graph_processor import save_graph_to_json, load_graph_from_json
from utils.logger import logger
from utils.call_llm_api import LLM
from config import get_config


def create_diverse_example_graph():
    """创建多样化的示例图谱，包含多种模式"""
    graph = nx.MultiDiGraph()
    
    # === 链式模式示例 ===
    # 化学位移伪影 → 采用高带宽 → 高带宽 → 信噪比
    entities_chain = [
        ('entity_0', '化学位移伪影', 'MRI伪影类型'),
        ('entity_1', '采用高带宽', '解决方案'),
        ('entity_2', '高带宽', '参数状态'),
        ('entity_3', '信噪比', '图像质量指标'),
    ]
    
    for node_id, name, desc in entities_chain:
        graph.add_node(node_id, label='entity', 
                      properties={'name': name, 'description': desc}, level=2)
    
    graph.add_edge('entity_0', 'entity_1', relation='解决方案为')
    graph.add_edge('entity_1', 'entity_2', relation='设置为')
    graph.add_edge('entity_2', 'entity_3', relation='影响')
    
    # === 星型模式示例 ===
    # T1加权序列连接多个相关概念
    central_entity = ('entity_10', 'T1加权序列', 'MRI扫描序列')
    graph.add_node(central_entity[0], label='entity',
                  properties={'name': central_entity[1], 'description': central_entity[2]}, level=2)
    
    related_entities = [
        ('entity_11', '对比度', '图像特征'),
        ('entity_12', '扫描时间', '时间参数'),
        ('entity_13', '空间分辨率', '分辨率参数'),
        ('entity_14', '信噪比', '质量指标'),
    ]
    
    for node_id, name, desc in related_entities:
        graph.add_node(node_id, label='entity',
                      properties={'name': name, 'description': desc}, level=2)
        graph.add_edge('entity_10', node_id, relation='影响')
    
    # === 多重边示例（需要具体化） ===
    # 梯度回波序列和自旋回波序列之间有多种关系
    graph.add_node('entity_20', label='entity',
                  properties={'name': '梯度回波序列', 'description': '一种扫描序列'}, level=2)
    graph.add_node('entity_21', label='entity',
                  properties={'name': '自旋回波序列', 'description': '另一种扫描序列'}, level=2)
    
    # 多条边
    graph.add_edge('entity_20', 'entity_21', relation='速度快于')
    graph.add_edge('entity_20', 'entity_21', relation='对比度低于')
    graph.add_edge('entity_20', 'entity_21', relation='对磁敏感')
    
    # === 另一个链式模式 ===
    # 运动伪影 → 使用门控技术 → 门控技术 → 扫描时间
    entities_chain2 = [
        ('entity_30', '运动伪影', '伪影类型'),
        ('entity_31', '使用门控技术', '解决方案'),
        ('entity_32', '门控技术', '技术方法'),
        ('entity_33', '扫描时间', '时间参数'),
    ]
    
    for node_id, name, desc in entities_chain2:
        graph.add_node(node_id, label='entity',
                      properties={'name': name, 'description': desc}, level=2)
    
    graph.add_edge('entity_30', 'entity_31', relation='解决方案为')
    graph.add_edge('entity_31', 'entity_32', relation='采用')
    graph.add_edge('entity_32', 'entity_33', relation='增加')
    
    logger.info(f"创建多样化示例图谱：{graph.number_of_nodes()} 个节点，{graph.number_of_edges()} 条边")
    
    return graph


def example_1_basic_pattern_discovery():
    """示例1：基本模式发现"""
    print("\n" + "="*80)
    print("示例1：基本模式发现（不使用LLM）")
    print("="*80)
    
    # 创建示例图谱
    graph = create_diverse_example_graph()
    
    # 初始化模式发现引擎
    engine = PatternDiscoveryEngine(llm_client=None)
    
    # 发现所有模式
    print("\n发现图中的模式...")
    pattern_matches = engine.discover_patterns(graph)
    
    # 显示结果
    print(f"\n找到的模式类型：{len(pattern_matches)} 种")
    for pattern_name, matches in pattern_matches.items():
        print(f"\n【{pattern_name}】")
        print(f"  匹配数量: {len(matches)}")
        print(f"  平均置信度: {sum(m.confidence for m in matches) / len(matches):.2f}")
        
        # 显示前2个匹配的详细信息
        for i, match in enumerate(matches[:2], 1):
            print(f"\n  匹配 #{i}:")
            print(f"    节点数: {len(match.matched_nodes)}")
            print(f"    边数: {len(match.matched_edges)}")
            print(f"    置信度: {match.confidence:.2f}")
            print(f"    元数据: {match.metadata}")
            
            if match.recommendation:
                print(f"    建议操作:")
                for action in match.recommendation.get('actions', []):
                    print(f"      - {action.get('description')}")


def example_2_chain_pattern_analysis():
    """示例2：深入分析链式模式"""
    print("\n" + "="*80)
    print("示例2：链式模式深入分析")
    print("="*80)
    
    graph = create_diverse_example_graph()
    
    # 只使用链式模式检测器
    chain_detector = ChainPattern(min_chain_length=2, max_chain_length=5)
    
    print("\n检测链式模式...")
    matches = chain_detector.detect(graph)
    
    print(f"\n找到 {len(matches)} 个链式模式：\n")
    
    for i, match in enumerate(matches, 1):
        print(f"链 #{i}:")
        print(f"  长度: {match.metadata['chain_length']}")
        print(f"  置信度: {match.confidence:.2f}")
        
        # 显示链条
        print(f"  路径: ", end="")
        for j, node_id in enumerate(match.matched_nodes):
            node_name = graph.nodes[node_id]['properties']['name']
            print(node_name, end="")
            if j < len(match.matched_nodes) - 1:
                relation = match.matched_edges[j][2]
                print(f" --{relation}--> ", end="")
        print()
        
        # 显示建议
        if match.recommendation.get('actions'):
            print(f"  建议:")
            for action in match.recommendation['actions']:
                print(f"    {action['type']}: {action['description']}")
        print()


def example_3_star_pattern_analysis():
    """示例3：星型模式分析"""
    print("\n" + "="*80)
    print("示例3：星型模式分析")
    print("="*80)
    
    graph = create_diverse_example_graph()
    
    # 只使用星型模式检测器
    star_detector = StarPattern(min_neighbors=3)
    
    print("\n检测星型模式...")
    matches = star_detector.detect(graph)
    
    print(f"\n找到 {len(matches)} 个星型模式：\n")
    
    for i, match in enumerate(matches, 1):
        center_id = match.metadata['center_node']
        center_name = graph.nodes[center_id]['properties']['name']
        neighbor_count = match.metadata['neighbor_count']
        direction = match.metadata['direction']
        
        print(f"星型 #{i}:")
        print(f"  中心节点: {center_name}")
        print(f"  邻居数量: {neighbor_count}")
        print(f"  方向: {direction}")
        print(f"  置信度: {match.confidence:.2f}")
        
        # 显示所有关系
        print(f"  关系:")
        for edge in match.matched_edges[:5]:  # 最多显示5条
            source_name = graph.nodes[edge[0]]['properties']['name']
            target_name = graph.nodes[edge[1]]['properties']['name']
            relation = edge[2]
            print(f"    [{source_name}] --{relation}--> [{target_name}]")
        
        if len(match.matched_edges) > 5:
            print(f"    ... 还有 {len(match.matched_edges) - 5} 条边")
        print()


def example_4_with_configuration():
    """示例4：使用配置文件"""
    print("\n" + "="*80)
    print("示例4：使用配置文件进行模式发现")
    print("="*80)
    
    # 加载配置
    with open('config/pattern_discovery_config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    print(f"\n配置摘要:")
    print(f"  启用的模式:")
    for pattern_name, pattern_config in config['patterns'].items():
        if pattern_config['enabled']:
            print(f"    - {pattern_name}")
    
    # 创建图谱
    graph = create_diverse_example_graph()
    
    # 根据配置初始化引擎
    engine = PatternDiscoveryEngine(llm_client=None)
    
    # 只使用配置中启用的模式
    enabled_patterns = []
    if config['patterns']['chain_pattern']['enabled']:
        chain_params = config['patterns']['chain_pattern']['params']
        enabled_patterns.append(ChainPattern(
            min_chain_length=chain_params['min_chain_length'],
            max_chain_length=chain_params['max_chain_length']
        ))
    
    if config['patterns']['star_pattern']['enabled']:
        star_params = config['patterns']['star_pattern']['params']
        enabled_patterns.append(StarPattern(
            min_neighbors=star_params['min_neighbors']
        ))
    
    # 清空默认模式，使用配置的模式
    engine.patterns = enabled_patterns
    
    # 发现模式
    pattern_matches = engine.discover_patterns(graph)
    
    # 保存报告
    import os
    os.makedirs('./output/pattern_discovery', exist_ok=True)
    engine.generate_report(
        pattern_matches,
        './output/pattern_discovery/pattern_report_configured.json'
    )
    
    print(f"\n模式发现完成！")
    print(f"  报告已保存到: ./output/pattern_discovery/pattern_report_configured.json")
    
    # 显示统计
    total_matches = sum(len(matches) for matches in pattern_matches.values())
    print(f"\n统计:")
    print(f"  模式类型: {len(pattern_matches)}")
    print(f"  总匹配数: {total_matches}")


def example_5_complete_workflow():
    """示例5：完整的发现和优化工作流"""
    print("\n" + "="*80)
    print("示例5：完整的模式发现和图谱优化工作流")
    print("="*80)
    
    # 创建图谱
    graph = create_diverse_example_graph()
    
    # 保存原始图谱
    import os
    os.makedirs('./output/pattern_discovery', exist_ok=True)
    save_graph_to_json(graph, './output/pattern_discovery/original_graph.json')
    print(f"\n原始图谱已保存")
    
    # 使用便捷函数进行完整处理
    print(f"\n开始模式发现和优化...")
    results = discover_and_optimize(
        graph=graph,
        output_dir='./output/pattern_discovery',
        use_llm=False  # 不使用LLM
    )
    
    # 显示结果
    print(f"\n处理完成！")
    print(f"\n统计信息:")
    for key, value in results['stats'].items():
        print(f"  {key}: {value}")
    
    # 显示发现的模式
    print(f"\n发现的模式:")
    for pattern_name, count in results['stats']['patterns_found'].items():
        print(f"  {pattern_name}: {count} 个匹配")
    
    # 保存优化后的图谱
    save_graph_to_json(
        results['optimized_graph'],
        './output/pattern_discovery/optimized_graph.json'
    )
    print(f"\n优化后的图谱已保存")
    
    # 分析新增的内容
    original_edges = set((u, v, d.get('relation')) 
                        for u, v, d in graph.edges(data=True))
    optimized_edges = set((u, v, d.get('relation')) 
                         for u, v, d in results['optimized_graph'].edges(data=True))
    new_edges = optimized_edges - original_edges
    
    if new_edges:
        print(f"\n新增的边 ({len(new_edges)} 条):")
        for u, v, relation in list(new_edges)[:5]:
            u_name = results['optimized_graph'].nodes[u]['properties']['name']
            v_name = results['optimized_graph'].nodes[v]['properties']['name']
            print(f"  [{u_name}] --{relation}--> [{v_name}]")
        if len(new_edges) > 5:
            print(f"  ... 还有 {len(new_edges) - 5} 条新边")


def example_6_compare_approaches():
    """示例6：对比不同方法"""
    print("\n" + "="*80)
    print("示例6：对比硬编码方法 vs 通用框架方法")
    print("="*80)
    
    graph = create_diverse_example_graph()
    
    print("\n方法1: 硬编码的文本模式匹配（旧方法）")
    print("-" * 80)
    print("优点:")
    print("  + 简单直接")
    print("  + 不需要额外依赖")
    print("\n缺点:")
    print("  - case-by-case，不通用")
    print("  - 只能处理预定义的模式")
    print("  - 依赖实体名称，不考虑图结构")
    print("  - 难以扩展和维护")
    
    print("\n方法2: 通用模式发现框架（新方法）")
    print("-" * 80)
    print("优点:")
    print("  + 基于图结构，不依赖文本")
    print("  + 支持多种设计模式")
    print("  + 可配置和扩展")
    print("  + 可选的LLM增强")
    print("  + 从数据学习新模式")
    print("\n缺点:")
    print("  - 初期设置较复杂")
    print("  - 计算开销较大")
    
    # 实际运行新方法
    print("\n运行通用框架...")
    engine = PatternDiscoveryEngine()
    pattern_matches = engine.discover_patterns(graph)
    
    print(f"\n新方法发现的模式:")
    for pattern_name, matches in pattern_matches.items():
        avg_conf = sum(m.confidence for m in matches) / len(matches) if matches else 0
        print(f"  {pattern_name}: {len(matches)} 个匹配 (平均置信度: {avg_conf:.2f})")
    
    print("\n结论: 通用框架方法更加专业和可持续！")


def main():
    """运行所有示例"""
    print("\n" + "="*80)
    print("通用模式发现框架示例程序")
    print("="*80)
    print("\n本程序展示如何使用通用的、可扩展的模式发现框架，")
    print("而不是基于case-by-case的硬编码方案。")
    
    import os
    os.makedirs('./output/pattern_discovery', exist_ok=True)
    
    try:
        # 示例1: 基本模式发现
        example_1_basic_pattern_discovery()
        
        # 示例2: 链式模式分析
        example_2_chain_pattern_analysis()
        
        # 示例3: 星型模式分析
        example_3_star_pattern_analysis()
        
        # 示例4: 使用配置文件
        example_4_with_configuration()
        
        # 示例5: 完整工作流
        example_5_complete_workflow()
        
        # 示例6: 方法对比
        example_6_compare_approaches()
        
        print("\n" + "="*80)
        print("所有示例运行完成！")
        print("="*80)
        print("\n查看输出:")
        print("  - ./output/pattern_discovery/pattern_report_configured.json")
        print("  - ./output/pattern_discovery/original_graph.json")
        print("  - ./output/pattern_discovery/optimized_graph.json")
        
    except Exception as e:
        logger.error(f"运行示例时出错：{e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
