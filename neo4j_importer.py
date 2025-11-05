#!/usr/bin/env python3
"""
Neo4j Importer for Youtu-GraphRAG Knowledge Graphs

This script converts the JSON knowledge graph format from Youtu-GraphRAG 
to Neo4j Cypher statements for import and visualization.

Usage:
    python neo4j_importer.py --input output/graphs/demo_new.json --output neo4j_import.cypher
    python neo4j_importer.py --input output/graphs/demo_new.json --neo4j-uri bolt://localhost:7687 --username neo4j --password password
"""

import json
import argparse
import os
from typing import Dict, List, Set, Any
from collections import defaultdict

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    print("Warning: neo4j driver not installed. Only Cypher export available.")
    print("Install with: pip install neo4j")


class Neo4jImporter:
    """Import Youtu-GraphRAG knowledge graphs into Neo4j"""
    
    def __init__(self, uri: str = None, username: str = None, password: str = None):
        self.driver = None
        if uri and username and password and NEO4J_AVAILABLE:
            try:
                self.driver = GraphDatabase.driver(uri, auth=(username, password))
                print(f"Connected to Neo4j at {uri}")
            except Exception as e:
                print(f"Failed to connect to Neo4j: {e}")
    
    def close(self):
        if self.driver:
            self.driver.close()
    
    def load_graph_json(self, json_path: str) -> List[Dict]:
        """Load the knowledge graph JSON file"""
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def extract_nodes_and_relationships(self, graph_data: List[Dict]) -> tuple:
        """Extract unique nodes and relationships from graph data"""
        nodes = {}  # key: (label, name) -> node_data
        relationships = []
        
        for item in graph_data:
            start_node = item['start_node']
            end_node = item['end_node']
            relation = item['relation']
            
            # Process start node
            start_key = (start_node['label'], start_node['properties']['name'])
            if start_key not in nodes:
                nodes[start_key] = {
                    'label': start_node['label'],
                    'properties': start_node['properties']
                }
            
            # Process end node
            end_key = (end_node['label'], end_node['properties']['name'])
            if end_key not in nodes:
                nodes[end_key] = {
                    'label': end_node['label'],
                    'properties': end_node['properties']
                }
            
            # Add relationship
            relationships.append({
                'start_label': start_node['label'],
                'start_name': start_node['properties']['name'],
                'relation': relation,
                'end_label': end_node['label'],
                'end_name': end_node['properties']['name']
            })
        
        return list(nodes.values()), relationships
    
    def sanitize_property_value(self, value: Any) -> str:
        """Sanitize property values for Cypher queries"""
        if isinstance(value, str):
            # Escape single quotes and backslashes
            return value.replace('\\', '\\\\').replace("'", "\\'")
        elif isinstance(value, (int, float, bool)):
            return str(value)
        elif isinstance(value, list):
            # Convert list to string representation
            return str(value).replace("'", "\\'")
        else:
            return str(value).replace("'", "\\'")
    
    def generate_cypher_statements(self, nodes: List[Dict], relationships: List[Dict]) -> str:
        """Generate Cypher statements for nodes and relationships"""
        cypher_statements = []
        
        # Clear existing data (optional - uncomment if needed)
        cypher_statements.append("// Clear existing data (uncomment if needed)")
        cypher_statements.append("// MATCH (n) DETACH DELETE n;")
        cypher_statements.append("")
        
        # Create constraints and indexes
        cypher_statements.append("// Create constraints and indexes")
        labels = set(node['label'] for node in nodes)
        for label in labels:
            cypher_statements.append(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label.capitalize()}) REQUIRE n.name IS UNIQUE;")
        cypher_statements.append("")
        
        # Create nodes
        cypher_statements.append("// Create nodes")
        node_groups = defaultdict(list)
        for node in nodes:
            node_groups[node['label']].append(node)
        
        for label, label_nodes in node_groups.items():
            cypher_statements.append(f"// Create {label} nodes")
            for node in label_nodes:
                properties = []
                for key, value in node['properties'].items():
                    if key == 'name':
                        properties.append(f"name: '{self.sanitize_property_value(value)}'")
                    else:
                        properties.append(f"`{key}`: '{self.sanitize_property_value(value)}'")
                
                props_str = ", ".join(properties)
                cypher_statements.append(f"MERGE (:{label.capitalize()} {{{props_str}}});")
            cypher_statements.append("")
        
        # Create relationships
        cypher_statements.append("// Create relationships")
        relation_groups = defaultdict(list)
        for rel in relationships:
            key = (rel['start_label'], rel['relation'], rel['end_label'])
            relation_groups[key].append(rel)
        
        for (start_label, relation, end_label), group_rels in relation_groups.items():
            cypher_statements.append(f"// Create {relation} relationships between {start_label} and {end_label}")
            for rel in group_rels:
                start_name = self.sanitize_property_value(rel['start_name'])
                end_name = self.sanitize_property_value(rel['end_name'])
                relation_name = relation.upper().replace(' ', '_').replace('-', '_')
                
                cypher_statements.append(
                    f"MATCH (start:{start_label.capitalize()} {{name: '{start_name}'}}), "
                    f"(end:{end_label.capitalize()} {{name: '{end_name}'}}) "
                    f"MERGE (start)-[:{relation_name}]->(end);"
                )
            cypher_statements.append("")
        
        return "\n".join(cypher_statements)
    
    def export_to_cypher_file(self, json_path: str, output_path: str):
        """Export knowledge graph to Cypher file"""
        print(f"Loading graph from {json_path}...")
        graph_data = self.load_graph_json(json_path)
        
        print("Extracting nodes and relationships...")
        nodes, relationships = self.extract_nodes_and_relationships(graph_data)
        
        print(f"Found {len(nodes)} unique nodes and {len(relationships)} relationships")
        
        print("Generating Cypher statements...")
        cypher_content = self.generate_cypher_statements(nodes, relationships)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cypher_content)
        
        print(f"Cypher statements exported to {output_path}")
        print(f"\nTo import into Neo4j:")
        print(f"1. Start Neo4j database")
        print(f"2. Open Neo4j Browser (http://localhost:7474)")
        print(f"3. Copy and paste the Cypher statements from {output_path}")
        print(f"4. Or use: cypher-shell -f {output_path}")
    
    def import_to_neo4j(self, json_path: str):
        """Import knowledge graph directly to Neo4j"""
        if not self.driver:
            raise Exception("Neo4j connection not established")
        
        print(f"Loading graph from {json_path}...")
        graph_data = self.load_graph_json(json_path)
        
        print("Extracting nodes and relationships...")
        nodes, relationships = self.extract_nodes_and_relationships(graph_data)
        
        print(f"Found {len(nodes)} unique nodes and {len(relationships)} relationships")
        
        with self.driver.session() as session:
            # Clear existing data (optional)
            # session.run("MATCH (n) DETACH DELETE n")
            
            # Create constraints
            labels = set(node['label'] for node in nodes)
            for label in labels:
                try:
                    session.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label.capitalize()}) REQUIRE n.name IS UNIQUE")
                except:
                    pass  # Constraint might already exist
            
            # Create nodes
            print("Creating nodes...")
            for i, node in enumerate(nodes):
                if i % 100 == 0:
                    print(f"Progress: {i}/{len(nodes)} nodes")
                
                properties = {key: value for key, value in node['properties'].items()}
                label = node['label'].capitalize()
                
                session.run(
                    f"MERGE (n:{label} {{name: $name}}) SET n += $properties",
                    name=properties['name'],
                    properties=properties
                )
            
            # Create relationships
            print("Creating relationships...")
            for i, rel in enumerate(relationships):
                if i % 100 == 0:
                    print(f"Progress: {i}/{len(relationships)} relationships")
                
                start_label = rel['start_label'].capitalize()
                end_label = rel['end_label'].capitalize()
                relation_name = rel['relation'].upper().replace(' ', '_').replace('-', '_')
                
                session.run(
                    f"MATCH (start:{start_label} {{name: $start_name}}), "
                    f"(end:{end_label} {{name: $end_name}}) "
                    f"MERGE (start)-[:{relation_name}]->(end)",
                    start_name=rel['start_name'],
                    end_name=rel['end_name']
                )
        
        print("Import completed successfully!")
    
    def get_graph_statistics(self, json_path: str):
        """Get statistics about the knowledge graph"""
        graph_data = self.load_graph_json(json_path)
        nodes, relationships = self.extract_nodes_and_relationships(graph_data)
        
        # Node statistics
        node_labels = defaultdict(int)
        for node in nodes:
            node_labels[node['label']] += 1
        
        # Relationship statistics
        relation_types = defaultdict(int)
        for rel in relationships:
            relation_types[rel['relation']] += 1
        
        print("\n=== Knowledge Graph Statistics ===")
        print(f"Total Nodes: {len(nodes)}")
        print(f"Total Relationships: {len(relationships)}")
        
        print("\nNode Labels:")
        for label, count in sorted(node_labels.items()):
            print(f"  {label}: {count}")
        
        print("\nRelationship Types:")
        for rel_type, count in sorted(relation_types.items()):
            print(f"  {rel_type}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Import Youtu-GraphRAG knowledge graphs to Neo4j")
    parser.add_argument("--input", required=True, help="Path to input JSON graph file")
    parser.add_argument("--output", help="Path to output Cypher file")
    parser.add_argument("--neo4j-uri", help="Neo4j URI (e.g., bolt://localhost:7687)")
    parser.add_argument("--username", help="Neo4j username")
    parser.add_argument("--password", help="Neo4j password")
    parser.add_argument("--stats", action="store_true", help="Show graph statistics only")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file {args.input} not found")
        return
    
    importer = Neo4jImporter(args.neo4j_uri, args.username, args.password)
    
    try:
        if args.stats:
            importer.get_graph_statistics(args.input)
        elif args.output:
            # Export to Cypher file
            importer.export_to_cypher_file(args.input, args.output)
        elif args.neo4j_uri and args.username and args.password:
            # Direct import to Neo4j
            importer.import_to_neo4j(args.input)
        else:
            # Default: export to Cypher file
            output_path = args.input.replace('.json', '_neo4j_import.cypher')
            importer.export_to_cypher_file(args.input, output_path)
    
    finally:
        importer.close()


if __name__ == "__main__":
    main()