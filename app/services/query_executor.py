"""
Query execution service with result formatting and visualization support
"""
import time
import uuid
from typing import List, Dict, Any, Optional
import logging
from app.core.database import db
from app.models.query import QueryResult, QueryHistory
from datetime import datetime

logger = logging.getLogger(__name__)

class QueryExecutorService:
    def __init__(self):
        self.query_history: List[QueryHistory] = []
    
    def execute_cypher_query(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> QueryResult:
        """Execute a Cypher query and return formatted results"""
        start_time = time.time()
        
        try:
            # Execute the query
            raw_results = db.execute_query(cypher, parameters)
            execution_time = time.time() - start_time
            
            # Format results for better display
            formatted_results = self._format_results(raw_results)
            
            result = QueryResult(
                success=True,
                data=formatted_results,
                cypher_query=cypher,
                execution_time=execution_time,
                row_count=len(formatted_results)
            )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Query execution failed: {e}")
            
            return QueryResult(
                success=False,
                data=[],
                cypher_query=cypher,
                execution_time=execution_time,
                row_count=0,
                error_message=str(e)
            )
    
    def _format_results(self, raw_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format raw Neo4j results for better display"""
        formatted = []
        
        for record in raw_results:
            formatted_record = {}
            
            for key, value in record.items():
                if hasattr(value, '_properties'):  # Neo4j Node
                    formatted_record[key] = {
                        'type': 'node',
                        'labels': list(value.labels),
                        'properties': dict(value._properties),
                        'id': value.id
                    }
                elif hasattr(value, 'type'):  # Neo4j Relationship
                    formatted_record[key] = {
                        'type': 'relationship',
                        'relationship_type': value.type,
                        'properties': dict(value._properties) if hasattr(value, '_properties') else {},
                        'start_node': value.start_node.id if hasattr(value, 'start_node') else None,
                        'end_node': value.end_node.id if hasattr(value, 'end_node') else None,
                        'id': value.id
                    }
                else:
                    formatted_record[key] = value
            
            formatted.append(formatted_record)
        
        return formatted
    
    def add_to_history(self, natural_query: str, cypher_query: str, result: QueryResult):
        """Add query to history"""
        history_entry = QueryHistory(
            id=str(uuid.uuid4()),
            natural_language_query=natural_query,
            cypher_query=cypher_query,
            timestamp=datetime.now(),
            execution_time=result.execution_time,
            success=result.success,
            row_count=result.row_count
        )
        
        self.query_history.append(history_entry)
        
        # Keep only last 100 queries
        if len(self.query_history) > 100:
            self.query_history = self.query_history[-100:]
    
    def get_query_history(self, limit: int = 20) -> List[QueryHistory]:
        """Get recent query history"""
        return sorted(self.query_history, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def get_query_suggestions(self) -> List[str]:
        """Get suggested queries based on database schema"""
        suggestions = [
            "Show me all entities in the knowledge graph",
            "Find entities related to [topic]",
            "What are the different types of entities?",
            "Show me the relationships between entities",
            "Find the most connected entities",
            "What documents mention [entity]?",
            "Show me entities of type Person",
            "Find all relationships of type RELATED_TO",
            "What are the properties of entity [name]?",
            "Show me recent entities added to the graph"
        ]
        return suggestions

# Global service instance
query_executor = QueryExecutorService()