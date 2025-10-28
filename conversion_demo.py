#!/usr/bin/env python3
"""
演示 JSON 到 Cypher 的转换过程
Demo of JSON to Cypher conversion process
"""

import json
from collections import defaultdict

def demo_conversion_process():
    """演示转换过程"""
    
    print("🔄 JSON 到 Cypher 转换过程演示")
    print("=" * 50)
    
    # 1. 读取原始JSON数据（模拟前几条）
    print("\n📂 步骤1: 读取原始JSON数据")
    sample_data = [
        {
            "start_node": {
                "label": "entity",
                "properties": {
                    "name": "FC Barcelona",
                    "chunk id": "0FCIUkTr",
                    "schema_type": "organization"
                }
            },
            "relation": "has_attribute",
            "end_node": {
                "label": "attribute",
                "properties": {
                    "name": "type: football club",
                    "chunk id": "0FCIUkTr"
                }
            }
        },
        {
            "start_node": {
                "label": "entity",
                "properties": {
                    "name": "FC Barcelona",
                    "chunk id": "0FCIUkTr",
                    "schema_type": "organization"
                }
            },
            "relation": "participates_in",
            "end_node": {
                "label": "entity",
                "properties": {
                    "name": "Copa del Rey",
                    "chunk id": "0FCIUkTr",
                    "schema_type": "event"
                }
            }
        }
    ]
    
    print("原始JSON数据示例:")
    print(json.dumps(sample_data[0], indent=2, ensure_ascii=False))
    
    # 2. 提取节点
    print("\n🔍 步骤2: 提取唯一节点")
    nodes = {}
    relationships = []
    
    for item in sample_data:
        start_node = item['start_node']
        end_node = item['end_node']
        relation = item['relation']
        
        # 提取起始节点
        start_key = (start_node['label'], start_node['properties']['name'])
        if start_key not in nodes:
            nodes[start_key] = {
                'label': start_node['label'],
                'properties': start_node['properties']
            }
            print(f"添加节点: {start_node['label']} - {start_node['properties']['name']}")
        
        # 提取结束节点
        end_key = (end_node['label'], end_node['properties']['name'])
        if end_key not in nodes:
            nodes[end_key] = {
                'label': end_node['label'],
                'properties': end_node['properties']
            }
            print(f"添加节点: {end_node['label']} - {end_node['properties']['name']}")
        
        # 添加关系
        relationships.append({
            'start_label': start_node['label'],
            'start_name': start_node['properties']['name'],
            'relation': relation,
            'end_label': end_node['label'],
            'end_name': end_node['properties']['name']
        })
        print(f"添加关系: {relation}")
    
    print(f"\n统计: 发现 {len(nodes)} 个唯一节点, {len(relationships)} 个关系")
    
    # 3. 生成Cypher语句
    print("\n⚙️ 步骤3: 生成Cypher语句")
    
    def sanitize_property_value(value):
        """处理属性值中的特殊字符"""
        if isinstance(value, str):
            return value.replace('\\', '\\\\').replace("'", "\\'")
        return str(value).replace("'", "\\'")
    
    cypher_statements = []
    
    # 3.1 创建约束
    print("\n创建约束:")
    labels = set(node['label'] for node in nodes.values())
    for label in labels:
        constraint = f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label.capitalize()}) REQUIRE n.name IS UNIQUE;"
        cypher_statements.append(constraint)
        print(f"  {constraint}")
    
    cypher_statements.append("")
    
    # 3.2 创建节点
    print("\n创建节点:")
    node_groups = defaultdict(list)
    for node in nodes.values():
        node_groups[node['label']].append(node)
    
    for label, label_nodes in node_groups.items():
        print(f"\n创建 {label} 类型节点:")
        cypher_statements.append(f"// Create {label} nodes")
        
        for node in label_nodes:
            properties = []
            for key, value in node['properties'].items():
                if key == 'name':
                    properties.append(f"name: '{sanitize_property_value(value)}'")
                else:
                    properties.append(f"`{key}`: '{sanitize_property_value(value)}'")
            
            props_str = ", ".join(properties)
            cypher_stmt = f"MERGE (:{label.capitalize()} {{{props_str}}});"
            cypher_statements.append(cypher_stmt)
            print(f"  {cypher_stmt}")
        
        cypher_statements.append("")
    
    # 3.3 创建关系
    print("\n创建关系:")
    relation_groups = defaultdict(list)
    for rel in relationships:
        key = (rel['start_label'], rel['relation'], rel['end_label'])
        relation_groups[key].append(rel)
    
    for (start_label, relation, end_label), group_rels in relation_groups.items():
        print(f"\n创建 {relation} 关系 ({start_label} -> {end_label}):")
        cypher_statements.append(f"// Create {relation} relationships between {start_label} and {end_label}")
        
        for rel in group_rels:
            start_name = sanitize_property_value(rel['start_name'])
            end_name = sanitize_property_value(rel['end_name'])
            relation_name = relation.upper().replace(' ', '_').replace('-', '_')
            
            cypher_stmt = (
                f"MATCH (start:{start_label.capitalize()} {{name: '{start_name}'}}), "
                f"(end:{end_label.capitalize()} {{name: '{end_name}'}}) "
                f"MERGE (start)-[:{relation_name}]->(end);"
            )
            cypher_statements.append(cypher_stmt)
            print(f"  {cypher_stmt}")
        
        cypher_statements.append("")
    
    # 4. 输出最终结果
    print("\n📄 步骤4: 生成最终Cypher文件")
    final_cypher = "\n".join(cypher_statements)
    
    print("\n生成的完整Cypher语句:")
    print("-" * 50)
    print(final_cypher)
    print("-" * 50)
    
    return final_cypher

if __name__ == "__main__":
    demo_conversion_process()