"""
Natural Language to Cypher conversion service using OpenAI
"""
import openai
from typing import Dict, Any, Optional
import json
import logging
from app.core.config import settings
from app.models.query import CypherQuery
from app.core.database import db

logger = logging.getLogger(__name__)

class NLToCypherService:
    def __init__(self):
        if settings.openai_api_key:
            openai.api_key = settings.openai_api_key
        else:
            logger.warning("OpenAI API key not provided. NL to Cypher conversion will not work.")
    
    def get_schema_context(self) -> str:
        """Get database schema as context for the LLM"""
        try:
            schema_info = db.get_schema_info()
            sample_data = db.get_sample_data(limit=3)
            
            context = f"""
Database Schema Information:
- Node Labels: {', '.join([item['label'] for item in schema_info.get('node_labels', [])])}
- Relationship Types: {', '.join([item['relationshipType'] for item in schema_info.get('relationship_types', [])])}
- Property Keys: {', '.join([item['propertyKey'] for item in schema_info.get('property_keys', [])])}

This appears to be a GraphRAG knowledge graph with entities and relationships extracted from documents.
Common patterns include:
- Entity nodes with properties like name, type, description
- Relationship nodes connecting entities
- Document or chunk nodes containing source text
- Typical relationships: RELATED_TO, MENTIONS, PART_OF, etc.
"""
            return context
        except Exception as e:
            logger.error(f"Failed to get schema context: {e}")
            return "Database schema information unavailable."
    
    def convert_to_cypher(self, natural_query: str, context: Optional[str] = None) -> CypherQuery:
        """Convert natural language query to Cypher"""
        if not settings.openai_api_key:
            raise Exception("OpenAI API key not configured")
        
        schema_context = self.get_schema_context()
        
        system_prompt = f"""You are an expert Neo4j Cypher query generator. Convert natural language questions into valid Cypher queries.

{schema_context}

Guidelines:
1. Generate syntactically correct Cypher queries
2. Use MATCH, WHERE, RETURN appropriately
3. Limit results to reasonable numbers (use LIMIT)
4. Handle case-insensitive searches with toLower() when appropriate
5. For GraphRAG data, focus on entities, relationships, and their properties
6. Return only the Cypher query, no explanations unless asked
7. Use proper Neo4j syntax and functions

Additional context: {context or 'None provided'}

Examples:
- "Find all entities related to X" → MATCH (e:Entity)-[r]-(related) WHERE toLower(e.name) CONTAINS toLower('X') RETURN e, r, related LIMIT 20
- "What are the relationships between A and B" → MATCH (a:Entity)-[r]-(b:Entity) WHERE toLower(a.name) CONTAINS toLower('A') AND toLower(b.name) CONTAINS toLower('B') RETURN a, r, b
- "Show me entities of type Person" → MATCH (e:Entity) WHERE toLower(e.type) = 'person' RETURN e LIMIT 20
"""

        user_prompt = f"Convert this natural language question to Cypher: {natural_query}"
        
        try:
            response = openai.ChatCompletion.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            cypher_query = response.choices[0].message.content.strip()
            
            # Clean up the response - remove markdown formatting if present
            if cypher_query.startswith("```"):
                lines = cypher_query.split('\n')
                cypher_query = '\n'.join(lines[1:-1]) if len(lines) > 2 else cypher_query
            
            # Generate explanation
            explanation = f"Converted natural language query: '{natural_query}' to Cypher query."
            
            return CypherQuery(
                cypher=cypher_query,
                explanation=explanation
            )
            
        except Exception as e:
            logger.error(f"Failed to convert natural language to Cypher: {e}")
            raise Exception(f"Failed to generate Cypher query: {str(e)}")
    
    def validate_cypher(self, cypher: str) -> bool:
        """Validate Cypher query syntax by attempting to explain it"""
        try:
            explain_query = f"EXPLAIN {cypher}"
            db.execute_query(explain_query)
            return True
        except Exception:
            return False

# Global service instance
nl_to_cypher_service = NLToCypherService()