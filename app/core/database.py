"""
Neo4j database connection and operations
"""
from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class Neo4jConnection:
    def __init__(self):
        self.driver = None
        self.connect()
    
    def connect(self):
        """Establish connection to Neo4j database"""
        try:
            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_username, settings.neo4j_password)
            )
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info("Successfully connected to Neo4j database")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.driver:
            self.driver.close()
    
    def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results"""
        if not self.driver:
            raise Exception("Database connection not established")
        
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def get_schema_info(self) -> Dict[str, Any]:
        """Get database schema information"""
        schema_queries = {
            "node_labels": "CALL db.labels()",
            "relationship_types": "CALL db.relationshipTypes()",
            "property_keys": "CALL db.propertyKeys()",
            "constraints": "SHOW CONSTRAINTS",
            "indexes": "SHOW INDEXES"
        }
        
        schema_info = {}
        for key, query in schema_queries.items():
            try:
                schema_info[key] = self.execute_query(query)
            except Exception as e:
                logger.warning(f"Failed to get {key}: {e}")
                schema_info[key] = []
        
        return schema_info
    
    def get_sample_data(self, limit: int = 10) -> Dict[str, Any]:
        """Get sample nodes and relationships"""
        sample_queries = {
            "sample_nodes": f"MATCH (n) RETURN n LIMIT {limit}",
            "sample_relationships": f"MATCH (a)-[r]->(b) RETURN a, r, b LIMIT {limit}"
        }
        
        sample_data = {}
        for key, query in sample_queries.items():
            try:
                sample_data[key] = self.execute_query(query)
            except Exception as e:
                logger.warning(f"Failed to get {key}: {e}")
                sample_data[key] = []
        
        return sample_data

# Global database connection instance
db = Neo4jConnection()