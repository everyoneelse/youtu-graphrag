"""
Pydantic models for query requests and responses
"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class NaturalLanguageQuery(BaseModel):
    question: str
    context: Optional[str] = None
    max_results: Optional[int] = 100

class CypherQuery(BaseModel):
    cypher: str
    parameters: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = None

class QueryResult(BaseModel):
    success: bool
    data: List[Dict[str, Any]]
    cypher_query: str
    execution_time: float
    row_count: int
    error_message: Optional[str] = None

class SchemaInfo(BaseModel):
    node_labels: List[str]
    relationship_types: List[str]
    property_keys: List[str]
    constraints: List[Dict[str, Any]]
    indexes: List[Dict[str, Any]]

class QueryHistory(BaseModel):
    id: str
    natural_language_query: str
    cypher_query: str
    timestamp: datetime
    execution_time: float
    success: bool
    row_count: int