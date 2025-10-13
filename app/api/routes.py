"""
FastAPI routes for the Natural Language Neo4j Query Interface
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
import logging
from app.models.query import NaturalLanguageQuery, QueryResult, SchemaInfo
from app.services.nl_to_cypher import nl_to_cypher_service
from app.services.query_executor import query_executor
from app.core.database import db

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Natural Language Neo4j Query Interface API", "status": "running"}

@router.post("/query/natural", response_model=QueryResult)
async def query_natural_language(query: NaturalLanguageQuery) -> QueryResult:
    """Convert natural language to Cypher and execute query"""
    try:
        # Convert natural language to Cypher
        cypher_query = nl_to_cypher_service.convert_to_cypher(
            query.question, 
            query.context
        )
        
        # Add LIMIT if not present and max_results is specified
        if query.max_results and "LIMIT" not in cypher_query.cypher.upper():
            cypher_query.cypher += f" LIMIT {query.max_results}"
        
        # Execute the query
        result = query_executor.execute_cypher_query(cypher_query.cypher)
        
        # Add to history
        query_executor.add_to_history(query.question, cypher_query.cypher, result)
        
        return result
        
    except Exception as e:
        logger.error(f"Natural language query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query/cypher", response_model=QueryResult)
async def query_cypher(cypher: str, parameters: Dict[str, Any] = None) -> QueryResult:
    """Execute a direct Cypher query"""
    try:
        result = query_executor.execute_cypher_query(cypher, parameters)
        return result
    except Exception as e:
        logger.error(f"Cypher query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/schema", response_model=Dict[str, Any])
async def get_schema():
    """Get database schema information"""
    try:
        schema_info = db.get_schema_info()
        sample_data = db.get_sample_data(limit=5)
        
        return {
            "schema": schema_info,
            "sample_data": sample_data
        }
    except Exception as e:
        logger.error(f"Failed to get schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/suggestions")
async def get_query_suggestions() -> List[str]:
    """Get suggested natural language queries"""
    return query_executor.get_query_suggestions()

@router.get("/history")
async def get_query_history(limit: int = 20):
    """Get recent query history"""
    try:
        history = query_executor.get_query_history(limit)
        return [h.dict() for h in history]
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_database_stats():
    """Get database statistics"""
    try:
        stats_queries = {
            "total_nodes": "MATCH (n) RETURN count(n) as count",
            "total_relationships": "MATCH ()-[r]->() RETURN count(r) as count",
            "node_types": "MATCH (n) RETURN labels(n) as labels, count(n) as count ORDER BY count DESC",
            "relationship_types": "MATCH ()-[r]->() RETURN type(r) as type, count(r) as count ORDER BY count DESC"
        }
        
        stats = {}
        for key, query in stats_queries.items():
            try:
                result = db.execute_query(query)
                stats[key] = result
            except Exception as e:
                logger.warning(f"Failed to get {key}: {e}")
                stats[key] = []
        
        return stats
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))