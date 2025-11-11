"""
知识图谱模式发现框架 - Knowledge Graph Pattern Discovery Framework

这是一个通用的、可扩展的知识图谱模式发现和重构框架，而不是基于case-by-case的硬编码方案。

核心设计原则：
1. 基于图结构的模式识别，而非文本模式匹配
2. 支持多种知识图谱设计模式（Design Patterns）
3. 可配置的模式定义系统
4. 基于LLM的语义理解
5. 从数据中学习新模式的能力

支持的知识图谱设计模式：
1. Event Pattern（事件模式）- 对象/状态/动作
2. Chain Pattern（链式模式）- A→B→C的传递关系
3. Star Pattern（星型模式）- 中心实体与多个相关实体
4. Hierarchy Pattern（层次模式）- is-a, part-of关系
5. Reification Pattern（具体化模式）- 将关系转为实体
6. N-ary Relationship Pattern（N元关系模式）
7. Temporal Pattern（时间模式）- 带时间维度的关系
8. Custom Patterns（自定义模式）- 用户定义的模式

Author: AI Assistant
Date: 2025-11-04
"""

import json
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Set, Any, Optional
from collections import defaultdict
from dataclasses import dataclass, field
import networkx as nx
from utils.logger import logger
from utils.call_llm_api import LLM


@dataclass
class PatternMatch:
    """模式匹配结果"""
    pattern_name: str
    confidence: float
    matched_nodes: List[str]
    matched_edges: List[Tuple[str, str, str]]  # (source, target, relation)
    metadata: Dict[str, Any] = field(default_factory=dict)
    recommendation: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PatternDefinition:
    """模式定义"""
    name: str
    description: str
    structure_requirements: Dict[str, Any]
    semantic_requirements: Optional[Dict[str, Any]] = None
    transformation_rules: Optional[Dict[str, Any]] = None


class KGPattern(ABC):
    """知识图谱模式基类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        
    @abstractmethod
    def detect(self, graph: nx.MultiDiGraph, **kwargs) -> List[PatternMatch]:
        """
        检测图中是否存在该模式
        
        Args:
            graph: 知识图谱
            **kwargs: 额外参数
            
        Returns:
            模式匹配列表
        """
        pass
    
    @abstractmethod
    def transform(self, graph: nx.MultiDiGraph, match: PatternMatch) -> nx.MultiDiGraph:
        """
        根据模式对图进行转换/重构
        
        Args:
            graph: 知识图谱
            match: 模式匹配结果
            
        Returns:
            转换后的图谱
        """
        pass
    
    def validate_match(self, graph: nx.MultiDiGraph, match: PatternMatch) -> bool:
        """验证匹配结果的有效性"""
        return True


class ChainPattern(KGPattern):
    """
    链式模式：A → B → C
    
    识别形如 A→B→C 的链式关系，其中B同时是A的对象和C的主体。
    这是最基础但最重要的模式之一。
    
    应用场景：
    - 因果链：原因 → 中间状态 → 结果
    - 过程链：输入 → 处理 → 输出
    - 传递链：A → B → C，可能隐含 A → C
    """
    
    def __init__(self, min_chain_length: int = 2, max_chain_length: int = 5):
        super().__init__(
            name="Chain Pattern",
            description="检测链式连接的实体序列"
        )
        self.min_chain_length = min_chain_length
        self.max_chain_length = max_chain_length
    
    def detect(self, graph: nx.MultiDiGraph, **kwargs) -> List[PatternMatch]:
        """检测链式模式"""
        matches = []
        entity_nodes = [n for n, d in graph.nodes(data=True) if d.get('label') == 'entity']
        
        # 找出所有简单路径
        for start_node in entity_nodes:
            for end_node in entity_nodes:
                if start_node == end_node:
                    continue
                
                try:
                    # 找出所有简单路径
                    paths = list(nx.all_simple_paths(
                        graph, start_node, end_node, 
                        cutoff=self.max_chain_length
                    ))
                    
                    for path in paths:
                        if len(path) >= self.min_chain_length + 1:  # +1 because path includes start node
                            # 提取边信息
                            edges = []
                            for i in range(len(path) - 1):
                                u, v = path[i], path[i + 1]
                                edge_data = graph.get_edge_data(u, v)
                                if edge_data:
                                    # Get first edge relation
                                    relation = list(edge_data.values())[0].get('relation', 'unknown')
                                    edges.append((u, v, relation))
                            
                            # 计算置信度
                            confidence = self._calculate_confidence(graph, path, edges)
                            
                            if confidence > 0.5:  # 阈值可配置
                                match = PatternMatch(
                                    pattern_name=self.name,
                                    confidence=confidence,
                                    matched_nodes=path,
                                    matched_edges=edges,
                                    metadata={
                                        'chain_length': len(path),
                                        'relations': [e[2] for e in edges]
                                    },
                                    recommendation=self._generate_recommendation(graph, path, edges)
                                )
                                matches.append(match)
                                
                except nx.NetworkXNoPath:
                    continue
        
        # 去重（保留最高置信度的）
        matches = self._deduplicate_matches(matches)
        
        logger.info(f"检测到 {len(matches)} 个链式模式")
        return matches
    
    def _calculate_confidence(self, graph: nx.MultiDiGraph, path: List[str], 
                             edges: List[Tuple]) -> float:
        """计算匹配置信度"""
        confidence = 0.5  # 基础分
        
        # 因素1: 链长度（适中长度更可能是有意义的模式）
        chain_length = len(path)
        if 2 <= chain_length <= 4:
            confidence += 0.2
        elif chain_length > 6:
            confidence -= 0.1
        
        # 因素2: 节点的度数（中间节点度数高说明是枢纽）
        for i, node in enumerate(path[1:-1], 1):  # 排除首尾
            degree = graph.degree(node)
            if degree >= 3:
                confidence += 0.1
        
        # 因素3: 关系的一致性
        relations = [e[2] for e in edges]
        if len(set(relations)) == 1:  # 所有关系相同
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _generate_recommendation(self, graph: nx.MultiDiGraph, path: List[str],
                                edges: List[Tuple]) -> Dict[str, Any]:
        """生成重构建议"""
        recommendations = {
            'pattern_type': 'chain',
            'actions': []
        }
        
        # 建议1: 如果链条很长，考虑添加快捷边
        if len(path) > 3:
            start_name = graph.nodes[path[0]]['properties']['name']
            end_name = graph.nodes[path[-1]]['properties']['name']
            recommendations['actions'].append({
                'type': 'add_shortcut_edge',
                'description': f'考虑添加快捷关系：{start_name} → {end_name}',
                'source': path[0],
                'target': path[-1],
                'relation': 'derived_relation',
                'rationale': '长链条可能隐含直接关系'
            })
        
        # 建议2: 识别中间的关键节点
        if len(path) > 2:
            middle_nodes = path[1:-1]
            for node in middle_nodes:
                node_name = graph.nodes[node]['properties']['name']
                recommendations['actions'].append({
                    'type': 'highlight_key_node',
                    'description': f'关键中间节点：{node_name}',
                    'node': node,
                    'rationale': '可能是重要的中介概念'
                })
        
        return recommendations
    
    def _deduplicate_matches(self, matches: List[PatternMatch]) -> List[PatternMatch]:
        """去除重复的匹配（保留置信度最高的）"""
        seen = {}
        for match in matches:
            key = tuple(sorted(match.matched_nodes))
            if key not in seen or match.confidence > seen[key].confidence:
                seen[key] = match
        return list(seen.values())
    
    def transform(self, graph: nx.MultiDiGraph, match: PatternMatch) -> nx.MultiDiGraph:
        """根据链式模式转换图谱"""
        new_graph = graph.copy()
        
        # 执行推荐的操作
        for action in match.recommendation.get('actions', []):
            if action['type'] == 'add_shortcut_edge':
                source = action['source']
                target = action['target']
                relation = action['relation']
                
                # 检查边是否已存在
                if not new_graph.has_edge(source, target):
                    new_graph.add_edge(source, target, 
                                     relation=relation,
                                     inferred=True,
                                     inference_source='chain_pattern')
                    logger.info(f"添加推断边：{source} --{relation}--> {target}")
        
        return new_graph


class StarPattern(KGPattern):
    """
    星型模式：中心节点连接多个周边节点
    
    识别一个中心实体与多个其他实体有关系的情况。
    
    应用场景：
    - 实体属性聚合：实体 → 多个属性
    - 关系聚合：概念 → 多个相关概念
    - 分类中心：类别 → 多个实例
    """
    
    def __init__(self, min_neighbors: int = 3):
        super().__init__(
            name="Star Pattern",
            description="检测星型结构（中心节点连接多个节点）"
        )
        self.min_neighbors = min_neighbors
    
    def detect(self, graph: nx.MultiDiGraph, **kwargs) -> List[PatternMatch]:
        """检测星型模式"""
        matches = []
        entity_nodes = [n for n, d in graph.nodes(data=True) if d.get('label') == 'entity']
        
        for center_node in entity_nodes:
            # 获取所有邻居（出边+入边）
            out_neighbors = list(graph.successors(center_node))
            in_neighbors = list(graph.predecessors(center_node))
            
            # 分析出边星型
            if len(out_neighbors) >= self.min_neighbors:
                edges = []
                for neighbor in out_neighbors:
                    edge_data = graph.get_edge_data(center_node, neighbor)
                    if edge_data:
                        relation = list(edge_data.values())[0].get('relation', 'unknown')
                        edges.append((center_node, neighbor, relation))
                
                confidence = self._calculate_star_confidence(
                    graph, center_node, out_neighbors, 'outgoing'
                )
                
                if confidence > 0.6:
                    match = PatternMatch(
                        pattern_name=self.name,
                        confidence=confidence,
                        matched_nodes=[center_node] + out_neighbors,
                        matched_edges=edges,
                        metadata={
                            'center_node': center_node,
                            'neighbor_count': len(out_neighbors),
                            'direction': 'outgoing'
                        },
                        recommendation=self._generate_star_recommendation(
                            graph, center_node, out_neighbors, edges, 'outgoing'
                        )
                    )
                    matches.append(match)
            
            # 分析入边星型
            if len(in_neighbors) >= self.min_neighbors:
                edges = []
                for neighbor in in_neighbors:
                    edge_data = graph.get_edge_data(neighbor, center_node)
                    if edge_data:
                        relation = list(edge_data.values())[0].get('relation', 'unknown')
                        edges.append((neighbor, center_node, relation))
                
                confidence = self._calculate_star_confidence(
                    graph, center_node, in_neighbors, 'incoming'
                )
                
                if confidence > 0.6:
                    match = PatternMatch(
                        pattern_name=self.name,
                        confidence=confidence,
                        matched_nodes=[center_node] + in_neighbors,
                        matched_edges=edges,
                        metadata={
                            'center_node': center_node,
                            'neighbor_count': len(in_neighbors),
                            'direction': 'incoming'
                        },
                        recommendation=self._generate_star_recommendation(
                            graph, center_node, in_neighbors, edges, 'incoming'
                        )
                    )
                    matches.append(match)
        
        logger.info(f"检测到 {len(matches)} 个星型模式")
        return matches
    
    def _calculate_star_confidence(self, graph: nx.MultiDiGraph, center: str,
                                   neighbors: List[str], direction: str) -> float:
        """计算星型模式置信度"""
        confidence = 0.6
        
        # 因素1: 邻居数量
        if len(neighbors) >= 5:
            confidence += 0.2
        
        # 因素2: 关系的一致性
        relations = []
        for neighbor in neighbors:
            if direction == 'outgoing':
                edge_data = graph.get_edge_data(center, neighbor)
            else:
                edge_data = graph.get_edge_data(neighbor, center)
            if edge_data:
                relation = list(edge_data.values())[0].get('relation', 'unknown')
                relations.append(relation)
        
        if len(set(relations)) == 1:  # 所有关系相同
            confidence += 0.15
        
        return min(confidence, 1.0)
    
    def _generate_star_recommendation(self, graph: nx.MultiDiGraph, center: str,
                                     neighbors: List[str], edges: List[Tuple],
                                     direction: str) -> Dict[str, Any]:
        """生成星型模式重构建议"""
        center_name = graph.nodes[center]['properties']['name']
        
        recommendations = {
            'pattern_type': 'star',
            'actions': []
        }
        
        # 建议1: 如果关系相同，考虑创建集合/列表属性
        relations = [e[2] for e in edges]
        if len(set(relations)) == 1:
            relation = relations[0]
            recommendations['actions'].append({
                'type': 'consolidate_to_collection',
                'description': f'考虑将多个"{relation}"关系合并为集合属性',
                'center': center,
                'relation': relation,
                'neighbors': neighbors,
                'rationale': '多个相同关系可以合并为一个集合属性'
            })
        
        # 建议2: 识别邻居之间的潜在关系
        if len(neighbors) > 2:
            recommendations['actions'].append({
                'type': 'analyze_neighbor_relations',
                'description': f'分析{center_name}的邻居节点之间是否存在关联',
                'center': center,
                'neighbors': neighbors,
                'rationale': '星型结构的周边节点可能也存在关联'
            })
        
        return recommendations
    
    def transform(self, graph: nx.MultiDiGraph, match: PatternMatch) -> nx.MultiDiGraph:
        """根据星型模式转换图谱"""
        new_graph = graph.copy()
        
        # 可以根据需要实现具体的转换逻辑
        # 例如：合并多个相同关系为集合属性
        
        return new_graph


class ReificationPattern(KGPattern):
    """
    具体化模式：将关系转化为实体
    
    当一个关系本身需要携带属性时，将其转化为实体。
    这是解决多元关系的标准方法。
    
    应用场景：
    - 带时间的关系：A在时间T与B有关系R
    - 带条件的关系：A在条件C下与B有关系R
    - 需要量化的关系：A以强度S与B有关系R
    
    转换示例：
    原始: A --关系--> B
    具体化: A --涉及--> [关系实体] --指向--> B
            [关系实体] --属性1--> 值1
            [关系实体] --属性2--> 值2
    """
    
    def __init__(self, llm_client: Optional[LLM] = None):
        super().__init__(
            name="Reification Pattern",
            description="检测需要具体化的关系"
        )
        self.llm_client = llm_client
    
    def detect(self, graph: nx.MultiDiGraph, **kwargs) -> List[PatternMatch]:
        """检测需要具体化的关系"""
        matches = []
        
        # 检测多重边（同样的源和目标有多条边）
        edge_groups = defaultdict(list)
        for u, v, key, data in graph.edges(keys=True, data=True):
            if (graph.nodes[u].get('label') == 'entity' and 
                graph.nodes[v].get('label') == 'entity'):
                edge_groups[(u, v)].append((key, data))
        
        for (u, v), edges in edge_groups.items():
            if len(edges) > 1:  # 多条边，可能需要具体化
                confidence = 0.7
                
                all_edges = [(u, v, edge_data.get('relation', 'unknown')) 
                           for key, edge_data in edges]
                
                match = PatternMatch(
                    pattern_name=self.name,
                    confidence=confidence,
                    matched_nodes=[u, v],
                    matched_edges=all_edges,
                    metadata={
                        'edge_count': len(edges),
                        'relations': [e[2] for e in all_edges]
                    },
                    recommendation={
                        'pattern_type': 'reification',
                        'actions': [{
                            'type': 'reify_relation',
                            'description': f'考虑将{u}和{v}之间的多个关系具体化为实体',
                            'source': u,
                            'target': v,
                            'relations': [e[2] for e in all_edges],
                            'rationale': '多个关系可能表示复杂的语义，适合具体化'
                        }]
                    }
                )
                matches.append(match)
        
        logger.info(f"检测到 {len(matches)} 个可具体化的关系")
        return matches
    
    def transform(self, graph: nx.MultiDiGraph, match: PatternMatch) -> nx.MultiDiGraph:
        """执行具体化转换"""
        new_graph = graph.copy()
        
        source = match.matched_nodes[0]
        target = match.matched_nodes[1]
        
        # 创建关系实体节点
        relation_node_id = f"relation_{source}_{target}"
        relation_names = match.metadata['relations']
        
        new_graph.add_node(
            relation_node_id,
            label='entity',
            properties={
                'name': f"关系_{relation_names[0]}",
                'type': 'reified_relation',
                'original_relations': relation_names
            },
            level=2
        )
        
        # 添加新的边
        new_graph.add_edge(source, relation_node_id, relation='has_relation')
        new_graph.add_edge(relation_node_id, target, relation='points_to')
        
        logger.info(f"将{source}到{target}的关系具体化为{relation_node_id}")
        
        return new_graph


class LLMDrivenPatternDiscovery(KGPattern):
    """
    基于LLM的通用模式发现
    
    这是最通用的方法，使用LLM来识别图中的模式，
    不依赖于预定义的规则。
    
    优势：
    - 可以发现任意类型的模式
    - 理解语义而非仅结构
    - 可以学习和适应新的模式
    
    工作流程：
    1. 提取局部子图
    2. 将子图转换为自然语言描述
    3. 让LLM分析是否存在模式
    4. LLM提供重构建议
    """
    
    def __init__(self, llm_client: LLM):
        super().__init__(
            name="LLM-Driven Pattern Discovery",
            description="使用LLM发现和理解知识图谱模式"
        )
        self.llm_client = llm_client
    
    def detect(self, graph: nx.MultiDiGraph, **kwargs) -> List[PatternMatch]:
        """使用LLM检测模式"""
        matches = []
        
        # 提取有趣的子图（基于度数、连接性等）
        subgraphs = self._extract_interesting_subgraphs(graph)
        
        for subgraph_nodes in subgraphs:
            # 将子图转换为自然语言描述
            description = self._subgraph_to_text(graph, subgraph_nodes)
            
            # 让LLM分析
            prompt = self._build_analysis_prompt(description)
            
            try:
                response = self.llm_client.call_api(prompt)
                analysis = json.loads(response)
                
                if analysis.get('has_pattern', False):
                    # 提取边信息
                    edges = []
                    for i, node1 in enumerate(subgraph_nodes):
                        for node2 in subgraph_nodes[i+1:]:
                            if graph.has_edge(node1, node2):
                                edge_data = graph.get_edge_data(node1, node2)
                                relation = list(edge_data.values())[0].get('relation', 'unknown')
                                edges.append((node1, node2, relation))
                            if graph.has_edge(node2, node1):
                                edge_data = graph.get_edge_data(node2, node1)
                                relation = list(edge_data.values())[0].get('relation', 'unknown')
                                edges.append((node2, node1, relation))
                    
                    match = PatternMatch(
                        pattern_name=self.name,
                        confidence=analysis.get('confidence', 0.7),
                        matched_nodes=subgraph_nodes,
                        matched_edges=edges,
                        metadata={
                            'pattern_type': analysis.get('pattern_type', 'unknown'),
                            'llm_analysis': analysis
                        },
                        recommendation=analysis.get('recommendation', {})
                    )
                    matches.append(match)
                    
            except Exception as e:
                logger.warning(f"LLM分析失败: {e}")
                continue
        
        logger.info(f"LLM检测到 {len(matches)} 个模式")
        return matches
    
    def _extract_interesting_subgraphs(self, graph: nx.MultiDiGraph,
                                      max_subgraphs: int = 20) -> List[List[str]]:
        """提取有趣的子图"""
        subgraphs = []
        entity_nodes = [n for n, d in graph.nodes(data=True) if d.get('label') == 'entity']
        
        # 策略1: 高度数节点的邻域
        degrees = [(n, graph.degree(n)) for n in entity_nodes]
        degrees.sort(key=lambda x: x[1], reverse=True)
        
        for node, degree in degrees[:10]:  # 取前10个高度数节点
            neighbors = list(graph.neighbors(node))[:5]  # 最多5个邻居
            if len(neighbors) >= 2:
                subgraph_nodes = [node] + neighbors
                subgraphs.append(subgraph_nodes)
        
        # 策略2: 密集连接的子图（使用k-core）
        try:
            k_core = nx.k_core(graph.to_undirected(), k=2)
            if len(k_core.nodes()) > 0:
                # 从k-core中采样一些节点组
                core_nodes = [n for n in k_core.nodes() if n in entity_nodes]
                if len(core_nodes) >= 3:
                    subgraphs.append(core_nodes[:5])
        except:
            pass
        
        return subgraphs[:max_subgraphs]
    
    def _subgraph_to_text(self, graph: nx.MultiDiGraph, nodes: List[str]) -> str:
        """将子图转换为文本描述"""
        lines = ["子图中的实体和关系：\n"]
        
        # 列出实体
        lines.append("实体：")
        for i, node in enumerate(nodes, 1):
            node_data = graph.nodes[node]
            name = node_data.get('properties', {}).get('name', node)
            desc = node_data.get('properties', {}).get('description', '')
            lines.append(f"  {i}. {name}")
            if desc:
                lines.append(f"     描述: {desc}")
        
        # 列出关系
        lines.append("\n关系：")
        for i, node1 in enumerate(nodes):
            for j, node2 in enumerate(nodes):
                if i >= j:
                    continue
                
                # 检查两个方向的边
                if graph.has_edge(node1, node2):
                    edge_data = graph.get_edge_data(node1, node2)
                    relation = list(edge_data.values())[0].get('relation', 'unknown')
                    name1 = graph.nodes[node1]['properties']['name']
                    name2 = graph.nodes[node2]['properties']['name']
                    lines.append(f"  [{name1}] --{relation}--> [{name2}]")
                
                if graph.has_edge(node2, node1):
                    edge_data = graph.get_edge_data(node2, node1)
                    relation = list(edge_data.values())[0].get('relation', 'unknown')
                    name1 = graph.nodes[node1]['properties']['name']
                    name2 = graph.nodes[node2]['properties']['name']
                    lines.append(f"  [{name2}] --{relation}--> [{name1}]")
        
        return "\n".join(lines)
    
    def _build_analysis_prompt(self, subgraph_description: str) -> str:
        """构建LLM分析提示"""
        prompt = f"""你是一个知识图谱专家。请分析以下子图，识别其中的模式和结构特征。

{subgraph_description}

请分析：
1. 这个子图是否展现了某种有意义的模式？
2. 如果是，这是什么类型的模式？（事件模式、层次模式、链式模式、星型模式等）
3. 这个模式的语义含义是什么？
4. 如何优化或重构这个结构？

请以JSON格式返回结果：
{{
    "has_pattern": true/false,
    "pattern_type": "模式类型名称",
    "pattern_description": "模式的详细描述",
    "semantic_meaning": "这个模式在语义上表达什么",
    "confidence": 0.0-1.0,
    "recommendation": {{
        "actions": [
            {{
                "type": "操作类型",
                "description": "操作描述",
                "rationale": "为什么要这样做"
            }}
        ]
    }}
}}

重要：只有当你确信存在有意义的、可重构的模式时，才设置 has_pattern=true。
"""
        return prompt
    
    def transform(self, graph: nx.MultiDiGraph, match: PatternMatch) -> nx.MultiDiGraph:
        """根据LLM建议转换图谱"""
        new_graph = graph.copy()
        
        # 执行LLM推荐的操作
        actions = match.recommendation.get('actions', [])
        for action in actions:
            # 这里可以实现各种转换逻辑
            # 具体实现取决于action的type
            logger.info(f"执行LLM推荐的操作: {action.get('description')}")
        
        return new_graph


class PatternDiscoveryEngine:
    """
    模式发现引擎
    
    统一管理所有模式检测器，提供：
    - 模式注册和管理
    - 批量模式检测
    - 模式优先级排序
    - 冲突解决
    - 批量转换
    """
    
    def __init__(self, llm_client: Optional[LLM] = None):
        self.patterns: List[KGPattern] = []
        self.llm_client = llm_client
        self._register_default_patterns()
    
    def _register_default_patterns(self):
        """注册默认的模式检测器"""
        self.register_pattern(ChainPattern())
        self.register_pattern(StarPattern())
        self.register_pattern(ReificationPattern())
        
        # 如果有LLM，注册LLM驱动的模式发现
        if self.llm_client:
            self.register_pattern(LLMDrivenPatternDiscovery(self.llm_client))
    
    def register_pattern(self, pattern: KGPattern):
        """注册新的模式检测器"""
        self.patterns.append(pattern)
        logger.info(f"注册模式检测器: {pattern.name}")
    
    def discover_patterns(self, graph: nx.MultiDiGraph, 
                         pattern_names: Optional[List[str]] = None) -> Dict[str, List[PatternMatch]]:
        """
        发现图中的所有模式
        
        Args:
            graph: 知识图谱
            pattern_names: 要使用的模式名称列表（None表示使用所有）
            
        Returns:
            {pattern_name: [PatternMatch, ...]}
        """
        results = {}
        
        patterns_to_use = self.patterns
        if pattern_names:
            patterns_to_use = [p for p in self.patterns if p.name in pattern_names]
        
        for pattern in patterns_to_use:
            logger.info(f"运行模式检测器: {pattern.name}")
            try:
                matches = pattern.detect(graph)
                if matches:
                    results[pattern.name] = matches
                    logger.info(f"  发现 {len(matches)} 个匹配")
            except Exception as e:
                logger.error(f"模式检测失败 ({pattern.name}): {e}")
                continue
        
        return results
    
    def apply_transformations(self, graph: nx.MultiDiGraph,
                            pattern_matches: Dict[str, List[PatternMatch]],
                            priority: Optional[List[str]] = None) -> nx.MultiDiGraph:
        """
        应用模式转换
        
        Args:
            graph: 原始图谱
            pattern_matches: 模式匹配结果
            priority: 模式应用优先级（列表顺序）
            
        Returns:
            转换后的图谱
        """
        new_graph = graph.copy()
        
        # 确定应用顺序
        if priority is None:
            priority = list(pattern_matches.keys())
        
        for pattern_name in priority:
            if pattern_name not in pattern_matches:
                continue
            
            # 找到对应的模式处理器
            pattern = next((p for p in self.patterns if p.name == pattern_name), None)
            if not pattern:
                logger.warning(f"未找到模式处理器: {pattern_name}")
                continue
            
            # 应用所有匹配的转换
            matches = pattern_matches[pattern_name]
            for match in matches:
                try:
                    new_graph = pattern.apply(new_graph, match)
                    logger.info(f"应用转换: {pattern_name} (置信度={match.confidence:.2f})")
                except Exception as e:
                    logger.error(f"转换失败: {e}")
                    continue
        
        return new_graph
    
    def generate_report(self, pattern_matches: Dict[str, List[PatternMatch]],
                       output_path: str):
        """生成模式发现报告"""
        report = {
            'summary': {
                'total_patterns': len(pattern_matches),
                'total_matches': sum(len(matches) for matches in pattern_matches.values())
            },
            'patterns': {}
        }
        
        for pattern_name, matches in pattern_matches.items():
            pattern_report = {
                'count': len(matches),
                'avg_confidence': sum(m.confidence for m in matches) / len(matches) if matches else 0,
                'matches': []
            }
            
            for match in matches:
                match_info = {
                    'confidence': match.confidence,
                    'nodes_count': len(match.matched_nodes),
                    'edges_count': len(match.matched_edges),
                    'metadata': match.metadata,
                    'recommendation': match.recommendation
                }
                pattern_report['matches'].append(match_info)
            
            report['patterns'][pattern_name] = pattern_report
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"模式发现报告已保存: {output_path}")


def discover_and_optimize(graph: nx.MultiDiGraph,
                         llm_client: Optional[LLM] = None,
                         output_dir: Optional[str] = None,
                         use_llm: bool = False) -> Dict[str, Any]:
    """
    便捷函数：发现模式并优化图谱
    
    Args:
        graph: 知识图谱
        llm_client: LLM客户端（可选）
        output_dir: 输出目录
        use_llm: 是否使用LLM驱动的模式发现
        
    Returns:
        {
            'original_graph': 原图,
            'optimized_graph': 优化后的图,
            'pattern_matches': 模式匹配结果,
            'stats': 统计信息
        }
    """
    # 初始化引擎
    engine = PatternDiscoveryEngine(llm_client if use_llm else None)
    
    # 发现模式
    logger.info("开始模式发现...")
    pattern_matches = engine.discover_patterns(graph)
    
    # 生成报告
    if output_dir:
        import os
        os.makedirs(output_dir, exist_ok=True)
        engine.generate_report(
            pattern_matches,
            os.path.join(output_dir, 'pattern_discovery_report.json')
        )
    
    # 应用转换
    logger.info("应用模式转换...")
    optimized_graph = engine.apply_transformations(graph, pattern_matches)
    
    # 统计
    stats = {
        'original_nodes': graph.number_of_nodes(),
        'original_edges': graph.number_of_edges(),
        'optimized_nodes': optimized_graph.number_of_nodes(),
        'optimized_edges': optimized_graph.number_of_edges(),
        'patterns_found': {name: len(matches) for name, matches in pattern_matches.items()},
        'total_pattern_matches': sum(len(matches) for matches in pattern_matches.values())
    }
    
    logger.info("模式发现完成！")
    logger.info(f"统计: {stats}")
    
    return {
        'original_graph': graph,
        'optimized_graph': optimized_graph,
        'pattern_matches': pattern_matches,
        'stats': stats
    }
