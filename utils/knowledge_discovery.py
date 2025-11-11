"""
知识发现模块 - Knowledge Discovery Module

功能：
1. 检测可连接的三元组（一个的尾实体可以连接另一个的头实体）
2. 使用事件建模模式重构知识图谱：
   - 对象实体（Object Entity）：核心概念
   - 状态实体（State Entity）：对象的状态描述
   - 动作实体（Action Entity）：改变状态的动作

示例：
原始三元组：
  ['化学位移伪影', '解决方案为', '采用高带宽']
  ['高带宽', '影响', '信噪比']

重构后：
  对象实体：带宽
  状态实体：高带宽
  动作实体：采用高带宽
  
  新三元组：
  ['化学位移伪影', '解决方案为', '采用高带宽'] (动作)
  ['采用高带宽', '改变', '带宽'] (动作->对象)
  ['带宽', '处于状态', '高带宽'] (对象->状态)
  ['高带宽', '影响', '信噪比'] (状态->影响)
"""

import re
import json
from typing import List, Dict, Tuple, Set, Any
from collections import defaultdict
import networkx as nx
from utils.logger import logger
from utils.call_llm_api import LLM


class KnowledgeDiscovery:
    """知识发现和重构类"""
    
    def __init__(self, llm_client: LLM = None):
        """
        初始化知识发现模块
        
        Args:
            llm_client: LLM客户端，用于语义分析（可选）
        """
        self.llm_client = llm_client
        self.graph = None
        
        # 状态修饰词模式（中文）
        self.state_patterns = [
            r'高(.+)', r'低(.+)', r'大(.+)', r'小(.+)',
            r'快(.+)', r'慢(.+)', r'强(.+)', r'弱(.+)',
            r'长(.+)', r'短(.+)', r'厚(.+)', r'薄(.+)',
            r'多(.+)', r'少(.+)', r'好(.+)', r'差(.+)',
            r'新(.+)', r'旧(.+)', r'增加的(.+)', r'减少的(.+)',
            r'提高的(.+)', r'降低的(.+)', r'优化的(.+)',
        ]
        
        # 动作动词模式（中文）
        self.action_patterns = [
            r'采用(.+)', r'使用(.+)', r'应用(.+)', r'实施(.+)',
            r'提高(.+)', r'降低(.+)', r'增加(.+)', r'减少(.+)',
            r'优化(.+)', r'改善(.+)', r'调整(.+)', r'设置(.+)',
            r'选择(.+)', r'确定(.+)', r'控制(.+)', r'改变(.+)',
        ]
        
    def load_graph(self, graph: nx.MultiDiGraph):
        """加载知识图谱"""
        self.graph = graph
        logger.info(f"已加载知识图谱：{self.graph.number_of_nodes()} 个节点，{self.graph.number_of_edges()} 条边")
        
    def find_connectable_triples(self) -> List[Dict[str, Any]]:
        """
        查找可连接的三元组
        
        Returns:
            可连接的三元组对列表，每个元素包含：
            {
                'triple1': (head1, relation1, tail1),
                'triple2': (head2, relation2, tail2),
                'connection_type': 'tail_to_head',  # 连接类型
                'overlap_entity': entity_name  # 重叠的实体名称
            }
        """
        if not self.graph:
            logger.error("请先加载知识图谱")
            return []
        
        connectable_pairs = []
        
        # 获取所有实体三元组（排除属性节点）
        entity_triples = []
        for u, v, data in self.graph.edges(data=True):
            u_data = self.graph.nodes[u]
            v_data = self.graph.nodes[v]
            
            # 只考虑实体之间的关系
            if u_data.get('label') == 'entity' and v_data.get('label') == 'entity':
                head_name = u_data['properties'].get('name', '')
                tail_name = v_data['properties'].get('name', '')
                relation = data.get('relation', '')
                
                entity_triples.append({
                    'head_id': u,
                    'head_name': head_name,
                    'relation': relation,
                    'tail_id': v,
                    'tail_name': tail_name,
                })
        
        logger.info(f"找到 {len(entity_triples)} 个实体三元组")
        
        # 查找可连接的三元组对
        for i, triple1 in enumerate(entity_triples):
            for j, triple2 in enumerate(entity_triples):
                if i >= j:  # 避免重复比较
                    continue
                
                # 检查 triple1 的尾是否可以连接到 triple2 的头
                if self._can_connect(triple1['tail_name'], triple2['head_name']):
                    connectable_pairs.append({
                        'triple1': (triple1['head_name'], triple1['relation'], triple1['tail_name']),
                        'triple2': (triple2['head_name'], triple2['relation'], triple2['tail_name']),
                        'connection_type': 'tail_to_head',
                        'overlap_entity': triple1['tail_name'],
                        'triple1_ids': (triple1['head_id'], triple1['tail_id']),
                        'triple2_ids': (triple2['head_id'], triple2['tail_id']),
                    })
                
                # 检查 triple2 的尾是否可以连接到 triple1 的头
                elif self._can_connect(triple2['tail_name'], triple1['head_name']):
                    connectable_pairs.append({
                        'triple1': (triple2['head_name'], triple2['relation'], triple2['tail_name']),
                        'triple2': (triple1['head_name'], triple1['relation'], triple1['tail_name']),
                        'connection_type': 'tail_to_head',
                        'overlap_entity': triple2['tail_name'],
                        'triple1_ids': (triple2['head_id'], triple2['tail_id']),
                        'triple2_ids': (triple1['head_id'], triple1['tail_id']),
                    })
        
        logger.info(f"发现 {len(connectable_pairs)} 对可连接的三元组")
        return connectable_pairs
    
    def _can_connect(self, tail_entity: str, head_entity: str) -> bool:
        """
        检查两个实体是否可以连接
        
        Args:
            tail_entity: 第一个三元组的尾实体
            head_entity: 第二个三元组的头实体
            
        Returns:
            是否可以连接
        """
        # 1. 完全匹配
        if tail_entity == head_entity:
            return True
        
        # 2. 包含关系（尾实体包含头实体，或头实体包含尾实体）
        if tail_entity in head_entity or head_entity in tail_entity:
            return True
        
        # 3. 提取核心概念后匹配（去除修饰词）
        tail_core = self._extract_core_concept(tail_entity)
        head_core = self._extract_core_concept(head_entity)
        
        if tail_core and head_core and tail_core == head_core:
            return True
        
        return False
    
    def _extract_core_concept(self, entity: str) -> str:
        """
        从实体中提取核心概念（去除状态修饰词和动作动词）
        
        Args:
            entity: 实体名称
            
        Returns:
            核心概念
        """
        # 尝试匹配状态模式
        for pattern in self.state_patterns:
            match = re.match(pattern, entity)
            if match:
                return match.group(1)
        
        # 尝试匹配动作模式
        for pattern in self.action_patterns:
            match = re.match(pattern, entity)
            if match:
                return match.group(1)
        
        return entity
    
    def decompose_entity(self, entity: str) -> Dict[str, str]:
        """
        将实体分解为对象、状态、动作
        
        Args:
            entity: 实体名称
            
        Returns:
            {
                'object': '对象实体',
                'state': '状态实体（如果有）',
                'action': '动作实体（如果有）',
                'type': 'object|state|action'
            }
        """
        result = {
            'object': entity,
            'state': None,
            'action': None,
            'type': 'object'
        }
        
        # 检查是否为状态实体
        for pattern in self.state_patterns:
            match = re.match(pattern, entity)
            if match:
                result['object'] = match.group(1)
                result['state'] = entity
                result['type'] = 'state'
                return result
        
        # 检查是否为动作实体
        for pattern in self.action_patterns:
            match = re.match(pattern, entity)
            if match:
                result['object'] = match.group(1)
                result['action'] = entity
                result['type'] = 'action'
                return result
        
        return result
    
    def reconstruct_with_event_modeling(self, connectable_pairs: List[Dict]) -> nx.MultiDiGraph:
        """
        使用事件建模模式重构知识图谱
        
        Args:
            connectable_pairs: 可连接的三元组对列表
            
        Returns:
            重构后的知识图谱
        """
        if not self.graph:
            logger.error("请先加载知识图谱")
            return None
        
        # 创建新图谱，复制原始图谱
        new_graph = self.graph.copy()
        node_counter = max([int(node.split('_')[-1]) for node in new_graph.nodes() if '_' in node], default=0) + 1
        
        logger.info("开始重构知识图谱...")
        
        for pair in connectable_pairs:
            overlap_entity = pair['overlap_entity']
            
            # 分解重叠实体
            decomposition = self.decompose_entity(overlap_entity)
            
            if decomposition['type'] == 'object':
                # 如果是纯对象实体，不需要重构
                continue
            
            logger.info(f"处理可连接三元组对：")
            logger.info(f"  三元组1: {pair['triple1']}")
            logger.info(f"  三元组2: {pair['triple2']}")
            logger.info(f"  重叠实体: {overlap_entity}")
            logger.info(f"  分解结果: {decomposition}")
            
            # 创建对象实体节点（如果不存在）
            object_entity = decomposition['object']
            object_node_id = self._find_or_create_entity_node(
                new_graph, object_entity, 'entity', node_counter
            )
            if object_node_id.startswith('entity_') and int(object_node_id.split('_')[1]) >= node_counter:
                node_counter = int(object_node_id.split('_')[1]) + 1
            
            if decomposition['type'] == 'state':
                # 状态实体：创建 对象 -> 状态 的关系
                state_entity = decomposition['state']
                state_node_id = self._find_or_create_entity_node(
                    new_graph, state_entity, 'entity', node_counter,
                    entity_subtype='state'
                )
                if state_node_id.startswith('entity_') and int(state_node_id.split('_')[1]) >= node_counter:
                    node_counter = int(state_node_id.split('_')[1]) + 1
                
                # 添加关系：对象 -> 处于状态 -> 状态
                new_graph.add_edge(object_node_id, state_node_id, relation='处于状态')
                logger.info(f"  添加关系: [{object_entity}] --处于状态--> [{state_entity}]")
                
            elif decomposition['type'] == 'action':
                # 动作实体：创建 动作 -> 作用于 -> 对象 的关系
                action_entity = decomposition['action']
                action_node_id = self._find_or_create_entity_node(
                    new_graph, action_entity, 'entity', node_counter,
                    entity_subtype='action'
                )
                if action_node_id.startswith('entity_') and int(action_node_id.split('_')[1]) >= node_counter:
                    node_counter = int(action_node_id.split('_')[1]) + 1
                
                # 添加关系：动作 -> 作用于 -> 对象
                new_graph.add_edge(action_node_id, object_node_id, relation='作用于')
                logger.info(f"  添加关系: [{action_entity}] --作用于--> [{object_entity}]")
        
        logger.info(f"重构完成：新增 {new_graph.number_of_nodes() - self.graph.number_of_nodes()} 个节点，"
                   f"{new_graph.number_of_edges() - self.graph.number_of_edges()} 条边")
        
        return new_graph
    
    def _find_or_create_entity_node(self, graph: nx.MultiDiGraph, entity_name: str, 
                                    label: str, node_counter: int, 
                                    entity_subtype: str = None) -> str:
        """
        查找或创建实体节点
        
        Args:
            graph: 知识图谱
            entity_name: 实体名称
            label: 节点标签
            node_counter: 节点计数器
            entity_subtype: 实体子类型（state/action/object）
            
        Returns:
            节点ID
        """
        # 查找是否存在同名实体
        for node_id, node_data in graph.nodes(data=True):
            if (node_data.get('label') == label and 
                node_data.get('properties', {}).get('name') == entity_name):
                return node_id
        
        # 创建新节点
        node_id = f"{label}_{node_counter}"
        properties = {'name': entity_name}
        if entity_subtype:
            properties['subtype'] = entity_subtype
        
        graph.add_node(
            node_id,
            label=label,
            properties=properties,
            level=2  # 实体层
        )
        
        return node_id
    
    def analyze_with_llm(self, connectable_pairs: List[Dict]) -> List[Dict]:
        """
        使用LLM分析可连接的三元组，提供更智能的重构建议
        
        Args:
            connectable_pairs: 可连接的三元组对列表
            
        Returns:
            增强的分析结果
        """
        if not self.llm_client:
            logger.warning("未配置LLM客户端，跳过LLM分析")
            return connectable_pairs
        
        enhanced_results = []
        
        for pair in connectable_pairs:
            prompt = self._build_analysis_prompt(pair)
            
            try:
                response = self.llm_client.call_api(prompt)
                analysis = json.loads(response)
                
                pair['llm_analysis'] = analysis
                enhanced_results.append(pair)
                
                logger.info(f"LLM分析结果：{analysis}")
                
            except Exception as e:
                logger.error(f"LLM分析失败: {e}")
                enhanced_results.append(pair)
        
        return enhanced_results
    
    def _build_analysis_prompt(self, pair: Dict) -> str:
        """构建LLM分析提示"""
        prompt = f"""你是一个知识图谱专家，请分析以下可连接的三元组对，并提供重构建议。

三元组1: {pair['triple1']}
三元组2: {pair['triple2']}
重叠实体: {pair['overlap_entity']}

请分析：
1. 重叠实体的类型（对象/状态/动作）
2. 核心对象实体是什么
3. 如何使用事件建模模式重构这两个三元组
4. 建议添加哪些新的实体和关系

请以JSON格式返回结果：
{{
    "entity_type": "object|state|action",
    "core_object": "核心对象实体",
    "state_entity": "状态实体（如果有）",
    "action_entity": "动作实体（如果有）",
    "new_triples": [
        ["实体1", "关系", "实体2"],
        ...
    ],
    "reasoning": "重构的理由"
}}
"""
        return prompt
    
    def export_discovery_results(self, connectable_pairs: List[Dict], 
                                 output_path: str):
        """
        导出知识发现结果
        
        Args:
            connectable_pairs: 可连接的三元组对列表
            output_path: 输出文件路径
        """
        results = {
            'total_pairs': len(connectable_pairs),
            'pairs': []
        }
        
        for pair in connectable_pairs:
            decomposition = self.decompose_entity(pair['overlap_entity'])
            
            result_item = {
                'triple1': list(pair['triple1']),
                'triple2': list(pair['triple2']),
                'overlap_entity': pair['overlap_entity'],
                'decomposition': decomposition,
            }
            
            if 'llm_analysis' in pair:
                result_item['llm_analysis'] = pair['llm_analysis']
            
            results['pairs'].append(result_item)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"知识发现结果已导出到：{output_path}")
    
    def visualize_connectable_pairs(self, connectable_pairs: List[Dict], 
                                    output_path: str = None):
        """
        可视化可连接的三元组对
        
        Args:
            connectable_pairs: 可连接的三元组对列表
            output_path: 输出图片路径（可选）
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')
            
            # 设置中文字体
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
            
            fig, ax = plt.subplots(figsize=(12, 8))
            
            # 绘制三元组对
            y_offset = 0
            for i, pair in enumerate(connectable_pairs[:10]):  # 最多显示10对
                triple1 = pair['triple1']
                triple2 = pair['triple2']
                overlap = pair['overlap_entity']
                decomposition = self.decompose_entity(overlap)
                
                # 绘制三元组1
                ax.text(0.1, y_offset, f"{triple1[0]}", ha='center', va='center', 
                       bbox=dict(boxstyle='round', facecolor='lightblue'))
                ax.arrow(0.2, y_offset, 0.15, 0, head_width=0.02, head_length=0.02)
                ax.text(0.3, y_offset + 0.05, triple1[1], ha='center', fontsize=8)
                ax.text(0.45, y_offset, f"{triple1[2]}", ha='center', va='center',
                       bbox=dict(boxstyle='round', facecolor='lightgreen'))
                
                # 绘制连接
                ax.text(0.55, y_offset, "→", ha='center', fontsize=16, color='red')
                
                # 绘制三元组2
                ax.text(0.65, y_offset, f"{triple2[0]}", ha='center', va='center',
                       bbox=dict(boxstyle='round', facecolor='lightgreen'))
                ax.arrow(0.75, y_offset, 0.15, 0, head_width=0.02, head_length=0.02)
                ax.text(0.85, y_offset + 0.05, triple2[1], ha='center', fontsize=8)
                ax.text(0.95, y_offset, f"{triple2[2]}", ha='center', va='center',
                       bbox=dict(boxstyle='round', facecolor='lightyellow'))
                
                # 显示分解结果
                if decomposition['type'] != 'object':
                    ax.text(0.55, y_offset - 0.08, 
                           f"类型: {decomposition['type']}\n对象: {decomposition['object']}", 
                           ha='center', fontsize=7, color='darkred')
                
                y_offset -= 0.2
            
            ax.set_xlim(0, 1)
            ax.set_ylim(y_offset - 0.1, 0.1)
            ax.axis('off')
            ax.set_title('可连接的三元组对', fontsize=16, fontweight='bold')
            
            if output_path:
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                logger.info(f"可视化结果已保存到：{output_path}")
            else:
                plt.show()
            
            plt.close()
            
        except Exception as e:
            logger.error(f"可视化失败: {e}")


def discover_and_reconstruct(graph: nx.MultiDiGraph, 
                            llm_client: LLM = None,
                            output_dir: str = None) -> Dict[str, Any]:
    """
    知识发现和重构的便捷函数
    
    Args:
        graph: 知识图谱
        llm_client: LLM客户端（可选）
        output_dir: 输出目录（可选）
        
    Returns:
        {
            'connectable_pairs': 可连接的三元组对,
            'reconstructed_graph': 重构后的图谱,
            'stats': 统计信息
        }
    """
    kd = KnowledgeDiscovery(llm_client)
    kd.load_graph(graph)
    
    # 查找可连接的三元组
    connectable_pairs = kd.find_connectable_triples()
    
    # 使用LLM分析（如果提供）
    if llm_client:
        connectable_pairs = kd.analyze_with_llm(connectable_pairs)
    
    # 重构图谱
    reconstructed_graph = kd.reconstruct_with_event_modeling(connectable_pairs)
    
    # 导出结果
    if output_dir:
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        kd.export_discovery_results(
            connectable_pairs, 
            os.path.join(output_dir, 'knowledge_discovery_results.json')
        )
        
        kd.visualize_connectable_pairs(
            connectable_pairs,
            os.path.join(output_dir, 'connectable_pairs_visualization.png')
        )
    
    # 统计信息
    stats = {
        'original_nodes': graph.number_of_nodes(),
        'original_edges': graph.number_of_edges(),
        'reconstructed_nodes': reconstructed_graph.number_of_nodes(),
        'reconstructed_edges': reconstructed_graph.number_of_edges(),
        'connectable_pairs_count': len(connectable_pairs),
        'new_nodes': reconstructed_graph.number_of_nodes() - graph.number_of_nodes(),
        'new_edges': reconstructed_graph.number_of_edges() - graph.number_of_edges(),
    }
    
    logger.info("知识发现完成！")
    logger.info(f"统计信息：{stats}")
    
    return {
        'connectable_pairs': connectable_pairs,
        'reconstructed_graph': reconstructed_graph,
        'stats': stats
    }
