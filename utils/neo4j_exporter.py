"""
Neo4j Export Utilities for Knowledge Tree Visualization

This module provides utilities to export the knowledge tree structure 
from JSON format to Neo4j-compatible formats (Cypher scripts and CSV).
"""

import json
import csv
from typing import Dict, List, Set, Tuple
from pathlib import Path
from utils.logger import logger


class Neo4jExporter:
    """Export knowledge graph to Neo4j-compatible formats"""
    
    def __init__(self, json_path: str):
        """
        Initialize exporter with JSON graph file
        
        Args:
            json_path: Path to the knowledge graph JSON file
        """
        self.json_path = json_path
        self.relationships = []
        self.nodes = {}  # (label, name) -> properties
        
    def load_graph(self):
        """Load graph from JSON file"""
        logger.info(f"Loading graph from {self.json_path}")
        with open(self.json_path, 'r', encoding='utf-8') as f:
            self.relationships = json.load(f)
        
        # Extract unique nodes
        for rel in self.relationships:
            start_node = rel['start_node']
            end_node = rel['end_node']
            
            start_key = (start_node['label'], start_node['properties'].get('name', ''))
            end_key = (end_node['label'], end_node['properties'].get('name', ''))
            
            if start_key not in self.nodes:
                self.nodes[start_key] = start_node['properties']
            if end_key not in self.nodes:
                self.nodes[end_key] = end_node['properties']
        
        logger.info(f"Loaded {len(self.nodes)} nodes and {len(self.relationships)} relationships")
        
    def _sanitize_property_value(self, value) -> str:
        """Sanitize property value for Cypher"""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            # Convert list to string representation
            return json.dumps(value, ensure_ascii=False)
        # String - escape quotes and backslashes
        value = str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        return f'"{value}"'
    
    def _escape_node_name(self, name: str) -> str:
        """Escape node name for use in Cypher"""
        # Remove or replace special characters that could cause issues
        name = str(name).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')
        return name
    
    def export_to_cypher(self, output_path: str):
        """
        Export graph to Cypher script for direct Neo4j import
        
        Args:
            output_path: Path to save the Cypher script
        """
        logger.info(f"Exporting to Cypher script: {output_path}")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # Write header
            f.write("// Youtu-GraphRAG Knowledge Tree - Neo4j Import Script\n")
            f.write("// Four-level Knowledge Tree Structure:\n")
            f.write("//   Level 1: Attribute - Entity attributes\n")
            f.write("//   Level 2: Entity - Main entities and relationships\n")
            f.write("//   Level 3: Keyword - Keyword indices\n")
            f.write("//   Level 4: Community - Community structures\n\n")
            
            # Write constraints and indexes
            f.write("// Create constraints and indexes for better performance\n")
            for label in ['Entity', 'Attribute', 'Keyword', 'Community']:
                f.write(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.name IS UNIQUE;\n")
            f.write("\n")
            
            # Group nodes by label
            nodes_by_label = {}
            for (label, name), properties in self.nodes.items():
                if label not in nodes_by_label:
                    nodes_by_label[label] = []
                nodes_by_label[label].append((name, properties))
            
            # Write nodes
            f.write("// Create nodes by level\n")
            for label in ['attribute', 'entity', 'keyword', 'community']:
                if label not in nodes_by_label:
                    continue
                    
                f.write(f"\n// Level {self._get_level_number(label)}: {label.capitalize()} nodes\n")
                
                for name, properties in nodes_by_label[label]:
                    # Escape and clean name
                    clean_name = self._escape_node_name(name)
                    
                    # Build properties string
                    props = []
                    for key, value in properties.items():
                        clean_key = key.replace(' ', '_').replace('-', '_')
                        props.append(f"{clean_key}: {self._sanitize_property_value(value)}")
                    
                    # Add level property
                    props.append(f"level: {self._get_level_number(label)}")
                    
                    props_str = ", ".join(props)
                    
                    # Write MERGE statement to avoid duplicates
                    f.write(f"MERGE (:{label.capitalize()} {{{props_str}}});\n")
            
            # Write relationships
            f.write("\n// Create relationships\n")
            relation_count = {}
            
            for rel in self.relationships:
                start_node = rel['start_node']
                end_node = rel['end_node']
                relation = rel['relation']
                
                # Track relation types
                if relation not in relation_count:
                    relation_count[relation] = 0
                relation_count[relation] += 1
                
                # Escape names
                start_name = self._escape_node_name(start_node['properties'].get('name', ''))
                end_name = self._escape_node_name(end_node['properties'].get('name', ''))
                
                # Convert relation to uppercase for Neo4j convention
                relation_upper = relation.upper()
                
                # Write MATCH + MERGE for relationships
                f.write(f"MATCH (a:{start_node['label'].capitalize()} {{name: \"{start_name}\"}})\n")
                f.write(f"MATCH (b:{end_node['label'].capitalize()} {{name: \"{end_name}\"}})\n")
                f.write(f"MERGE (a)-[:{relation_upper}]->(b);\n\n")
            
            # Write summary
            f.write("// Import Summary\n")
            f.write(f"// Total nodes: {len(self.nodes)}\n")
            f.write(f"// Total relationships: {len(self.relationships)}\n")
            f.write("// Relationship types:\n")
            for rel_type, count in sorted(relation_count.items()):
                f.write(f"//   {rel_type}: {count}\n")
        
        logger.info(f"Successfully exported Cypher script with {len(self.nodes)} nodes and {len(self.relationships)} relationships")
    
    def export_to_csv(self, output_dir: str):
        """
        Export graph to CSV files for Neo4j bulk import
        
        Args:
            output_dir: Directory to save CSV files
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Exporting to CSV files in: {output_dir}")
        
        # Export nodes by label
        nodes_by_label = {}
        for (label, name), properties in self.nodes.items():
            if label not in nodes_by_label:
                nodes_by_label[label] = []
            nodes_by_label[label].append(properties)
        
        for label, nodes in nodes_by_label.items():
            csv_path = output_path / f"{label}_nodes.csv"
            
            # Get all property keys
            all_keys = set()
            for node in nodes:
                all_keys.update(node.keys())
            all_keys = sorted(all_keys)
            
            # Add level column
            all_keys.append('level')
            
            with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=all_keys)
                writer.writeheader()
                
                for node in nodes:
                    row = {k: node.get(k, '') for k in all_keys}
                    row['level'] = self._get_level_number(label)
                    writer.writerow(row)
            
            logger.info(f"Exported {len(nodes)} {label} nodes to {csv_path}")
        
        # Export relationships
        rel_csv_path = output_path / "relationships.csv"
        with open(rel_csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'start_label', 'start_name', 'relation', 'end_label', 'end_name'
            ])
            writer.writeheader()
            
            for rel in self.relationships:
                writer.writerow({
                    'start_label': rel['start_node']['label'],
                    'start_name': rel['start_node']['properties'].get('name', ''),
                    'relation': rel['relation'],
                    'end_label': rel['end_node']['label'],
                    'end_name': rel['end_node']['properties'].get('name', '')
                })
        
        logger.info(f"Exported {len(self.relationships)} relationships to {rel_csv_path}")
        
        # Create import script
        import_script_path = output_path / "neo4j_import.sh"
        self._create_csv_import_script(import_script_path, nodes_by_label)
    
    def _create_csv_import_script(self, script_path: Path, nodes_by_label: Dict):
        """Create shell script for CSV import"""
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write("#!/bin/bash\n")
            f.write("# Neo4j CSV Import Script for Youtu-GraphRAG Knowledge Tree\n\n")
            f.write("# Usage: ./neo4j_import.sh <neo4j-home-directory>\n\n")
            f.write("NEO4J_HOME=${1:-$NEO4J_HOME}\n")
            f.write("if [ -z \"$NEO4J_HOME\" ]; then\n")
            f.write("  echo \"Error: Please provide Neo4j home directory\"\n")
            f.write("  echo \"Usage: ./neo4j_import.sh <neo4j-home-directory>\"\n")
            f.write("  exit 1\n")
            f.write("fi\n\n")
            
            f.write("# Import nodes\n")
            for label in nodes_by_label.keys():
                f.write(f"$NEO4J_HOME/bin/neo4j-admin import \\\n")
                f.write(f"  --nodes={label.capitalize()}={label}_nodes.csv \\\n")
            
            f.write("\n# Import relationships\n")
            f.write("$NEO4J_HOME/bin/neo4j-admin import \\\n")
            f.write("  --relationships=relationships.csv\n")
        
        # Make script executable
        script_path.chmod(0o755)
        logger.info(f"Created CSV import script: {script_path}")
    
    def _get_level_number(self, label: str) -> int:
        """Get level number for node label"""
        level_map = {
            'attribute': 1,
            'entity': 2,
            'keyword': 3,
            'community': 4
        }
        return level_map.get(label.lower(), 0)


def export_graph_to_neo4j(json_path: str, output_dir: str = None):
    """
    Main function to export knowledge graph to Neo4j formats
    
    Args:
        json_path: Path to the knowledge graph JSON file
        output_dir: Directory to save export files (default: same as JSON path)
    """
    if output_dir is None:
        output_dir = str(Path(json_path).parent)
    
    exporter = Neo4jExporter(json_path)
    exporter.load_graph()
    
    # Export to Cypher
    cypher_path = str(Path(output_dir) / f"{Path(json_path).stem}_neo4j.cypher")
    exporter.export_to_cypher(cypher_path)
    
    # Export to CSV
    csv_dir = str(Path(output_dir) / f"{Path(json_path).stem}_neo4j_csv")
    exporter.export_to_csv(csv_dir)
    
    logger.info("=" * 60)
    logger.info("Neo4j export completed!")
    logger.info(f"Cypher script: {cypher_path}")
    logger.info(f"CSV files: {csv_dir}")
    logger.info("=" * 60)
    
    return cypher_path, csv_dir


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python neo4j_exporter.py <json_graph_path> [output_dir]")
        sys.exit(1)
    
    json_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    export_graph_to_neo4j(json_path, output_dir)
