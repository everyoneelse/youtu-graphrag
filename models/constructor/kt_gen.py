import asyncio
import copy
import json
import os
import threading
import time
from concurrent import futures
from datetime import datetime
from typing import Any, Dict, List, Tuple
from tqdm import tqdm
import pickle

import nanoid
import networkx as nx
import tiktoken
import json_repair

from collections import defaultdict

import numpy as np
from config import get_config
from utils_ import call_llm_api, graph_processor, tree_comm
from utils_.logger import logger
import datetime

DEFAULT_LLM_CLUSTERING_PROMPT = (
    "You are a knowledge graph curation assistant performing initial clustering of tail entities.\n"
    "All listed tail entities share the same head entity and relation.\n\n"
    "Head entity: {head}\n"
    "Relation: {relation}\n\n"
    "Candidate tails:\n"
    "{candidates}\n\n"
    "TASK: Group these tails into PRELIMINARY CLUSTERS based on semantic similarity.\n"
    "This is an initial clustering step - your goal is to group tails that MIGHT refer to the same entity.\n\n"
    "CLUSTERING PRINCIPLE:\n"
    "Group tails together if they are:\n"
    "1. POTENTIALLY COREFERENT: Could refer to the same entity (e.g., 'NYC' and 'New York City')\n"
    "2. SEMANTICALLY VERY SIMILAR: Very similar concepts that need further examination\n"
    "3. LEXICALLY RELATED: Different expressions of potentially the same thing\n\n"
    "KEEP SEPARATE if tails are:\n"
    "1. CLEARLY DISTINCT: Obviously different entities (e.g., 'Paris' vs 'London')\n"
    "2. SEMANTICALLY DIFFERENT: Different concepts (e.g., 'color' vs 'size')\n"
    "3. UNRELATED: No clear semantic connection\n\n"
    "CLUSTERING GUIDELINES:\n"
    "- Be INCLUSIVE in this initial clustering - it's better to over-cluster than under-cluster\n"
    "- Subsequent LLM refinement will separate false positives within clusters\n"
    "- Focus on semantic similarity, not just string matching\n"
    "- Group by meaning/concept rather than exact wording\n"
    "- Each tail must appear in exactly ONE cluster\n\n"
    "EXAMPLES:\n"
    "✓ Cluster together: ['New York', 'NYC', 'New York City'] - potential coreference\n"
    "✓ Cluster together: ['United States', 'USA', 'US', 'America'] - potential coreference\n"
    "✓ Keep separate: ['Paris', 'London', 'Berlin'] - clearly distinct cities\n"
    "✓ Keep separate: ['red', 'large', 'heavy'] - different property types\n\n"
    "OUTPUT REQUIREMENTS:\n"
    "1. Every input index must appear in exactly one cluster\n"
    "2. Each cluster should contain semantically similar tails\n"
    "3. Provide a brief description for each cluster explaining the grouping rationale\n\n"
    "4. Please provide a description in Chinese for each group."
    "Respond with strict JSON using this schema:\n"
    "{{\n"
    "  \"clusters\": [\n"
    "    {{\n"
    "      \"members\": [1, 3, 5],\n"
    "      \"description\": \"Brief explanation of why these tails are clustered together\"\n"
    "    }},\n"
    "    {{\n"
    "      \"members\": [2],\n"
    "      \"description\": \"This tail is semantically distinct from others\"\n"
    "    }}\n"
    "  ]\n"
    "}}\n"
)

# Validation prompt for checking semantic deduplication consistency
# Design principle: Use general consistency rules, NOT case-by-case patterns
DEFAULT_SEMANTIC_DEDUP_VALIDATION_PROMPT = (
    "You are validating semantic deduplication results.\n\n"
    "INPUT DATA:\n"
    "{dedup_results}\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "YOUR TASK: Find groups where rationale's conclusion contradicts members\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "WHAT TO CHECK:\n\n"
    "For each group, ask:\n"
    "  Q1: What does the rationale CONCLUDE? (merge into another group OR stay separate)\n"
    "  Q2: What do the members show? (actually merged OR actually separate)\n"
    "  Q3: Do they match?\n\n"
    "❌ INCONSISTENT if:\n"
    "  - Rationale concludes \"merge\" → but members show \"separate\"\n"
    "  - Rationale concludes \"separate\" → but members show \"merged\"\n\n"
    "✅ CONSISTENT if:\n"
    "  - Rationale concludes \"merge\" → members show \"merged\" ✓\n"
    "  - Rationale concludes \"separate\" → members show \"separate\" ✓\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "MERGE conclusion indicators (rationale says to merge):\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "English: \"merge\", \"identical\", \"same as\", \"归入\"\n"
    "Chinese: \"可合并\", \"应合并\", \"完全一致\", \"归入一组\", \"归为一组\", \"视为同一\"\n\n"
    "⚠️ CRITICAL: \"故归入一组\" / \"归入XX组\" = says to MERGE\n"
    "   → Check if members actually include the referenced group's items!\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "SEPARATE conclusion indicators (rationale says to keep separate):\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "English: \"keep separate\", \"distinct\", \"independent\"\n"
    "Chinese: \"保持独立\", \"单独保留\", \"不宜合并\", \"保留为独立组\"\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "IGNORE (out of scope):\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "🚫 Content accuracy of rationale\n"
    "🚫 Whether reasoning makes sense\n"
    "🚫 Details mentioned in rationale\n\n"
    "✅ ONLY check: conclusion vs structure\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "OUTPUT FORMAT:\n"
    "═══════════════════════════════════════════════════════════════════\n\n"
    "Respond with strict JSON:\n"
    "{{\n"
    "  \"has_inconsistencies\": true/false,\n"
    "  \"inconsistencies\": [\n"
    "    {{\n"
    "      \"group_ids\": [affected group IDs],\n"
    "      \"issue_type\": \"conclusion_structure_mismatch\",\n"
    "      \"description\": \"Rationale says X but members show Y\",\n"
    "      \"suggested_fix\": \"merge/split action\"\n"
    "    }}\n"
    "  ],\n"
    "  \"corrected_groups\": [\n"
    "    {{\n"
    "      \"members\": [corrected member indices],\n"
    "      \"representative\": index,\n"
    "      \"rationale\": \"Updated rationale matching the corrected grouping\"\n"
    "    }}\n"
    "  ]\n"
    "}}\n\n"
    "IMPORTANT: corrected_groups should contain ALL groups (both corrected and unchanged).\n"
    "Do not omit groups that were already consistent.\n\n"
    "If NO inconsistencies:\n"
    "{{\n"
    "  \"has_inconsistencies\": false,\n"
    "  \"inconsistencies\": [],\n"
    "  \"corrected_groups\": null\n"
    "}}\n\n"
    "═══════════════════════════════════════════════════════════════════\n"
    "EXAMPLES:\n"
    "═══════════════════════════════════════════════════════════════════\n\n"
    "Example 1 (English):\n"
    "Input:\n"
    "- Group 0: {{members: [1, 2], rationale: \"These refer to the same entity\"}}\n"
    "- Group 1: {{members: [3], rationale: \"This is the same entity as group 0\"}}\n\n"
    "Analysis:\n"
    "Group 1's rationale says \"same entity as group 0\" (merge intention),\n"
    "but Group 1 is separate with only [3], not merged with [1, 2].\n"
    "❌ Conclusion (merge) ≠ Structure (separate) → INCONSISTENT\n\n"
    "Output:\n"
    "{{\n"
    "  \"has_inconsistencies\": true,\n"
    "  \"inconsistencies\": [{{\n"
    "    \"group_ids\": [1, 0],\n"
    "    \"issue_type\": \"rationale_conclusion_vs_grouping_mismatch\",\n"
    "    \"description\": \"Group 1 says 'same as group 0' but is separate\",\n"
    "    \"suggested_fix\": \"merge group 1 into group 0\"\n"
    "  }}],\n"
    "  \"corrected_groups\": [\n"
    "    {{\"members\": [1, 2, 3], \"representative\": 1, \"rationale\": \"These refer to the same entity\"}}\n"
    "  ]\n"
    "}}\n"
    "═══════════════════════════════════════════════════════════════════\n"
    "Remember: ONLY check conclusion vs structure. Ignore content details!\n"
    "═══════════════════════════════════════════════════════════════════\n"
)

class KTBuilder:
    def __init__(self, dataset_name, schema_path=None, mode=None, config=None):
        if config is None:
            config = get_config()
        
        self.config = config
        self.dataset_name = dataset_name
        self.schema = self.load_schema(schema_path or config.get_dataset_config(dataset_name).schema_path)

        dataset_config = None
        try:
            dataset_config = config.get_dataset_config(dataset_name)
        except ValueError:
            dataset_config = None
        
        self.resolved_schema_path_for_update = f"schemas/{dataset_name}.json"
        
        # if not self.resolved_schema_path_for_update and dataset_config:
        #     self.resolved_schema_path_for_update = dataset_config.schema_path
        
        if dataset_config is None:
            self.resolved_schema_path_for_update = f"schemas/{dataset_name}.json"
        else:
            self.resolved_schema_path_for_update = dataset_config.schema_path

        self.graph = nx.MultiDiGraph()
        self.node_counter = 0
        self.datasets_no_chunk = config.construction.datasets_no_chunk
        self.token_len = 0
        self.lock = threading.Lock()
        self.llm_client = call_llm_api.LLMCompletionCall()
        self.llm_dedup_client = call_llm_api.LLMCompletionCall_Dedup()
        self.all_chunks = {}
        self.mode = mode or config.construction.mode
        self._semantic_dedup_embedder = None
        self.llm_embed_client = call_llm_api.LLMEmbeddingCall()


    def load_schema(self, schema_path) -> Dict[str, Any]:
        try:
            with open(schema_path) as f:
                schema = json.load(f)
                return schema
        except FileNotFoundError:
            return dict()


    def chunk_text(self, text) -> Tuple[List[str], Dict[str, str]]:
        if self.dataset_name in self.datasets_no_chunk:
            chunks = [f"{text.get('title', '')} {text.get('text', '')}".strip() 
                     if isinstance(text, dict) else str(text)]
        else:
            chunks = [str(text)]

        chunk2id = {}
        for chunk in chunks:
            try:
                chunk_id = nanoid.generate(size=8)
                chunk2id[chunk_id] = chunk
            except Exception as e:
                logger.warning(f"Failed to generate chunk id with nanoid: {type(e).__name__}: {e}")

        with self.lock:
            self.all_chunks.update(chunk2id)

        return chunks, chunk2id

    def _clean_text(self, text: str) -> str:
        if not text:
            return "[EMPTY_TEXT]"
        
        if self.dataset_name == "graphrag-bench":
            safe_chars = {
                *" .:,!?()-+=[]{}()\\/|_^~<>*&%$#@!;\"'`"
            }
            cleaned = "".join(
                char for char in text 
                if char.isalnum() or char.isspace() or char in safe_chars
            ).strip()
        else:
            safe_chars = {
                *" .:,!?()-+="  
            }
            cleaned = "".join(
                char for char in text 
                if char.isalnum() or char.isspace() or char in safe_chars
            ).strip()
        
        return cleaned if cleaned else "[EMPTY_AFTER_CLEANING]"
    
    def save_chunks_to_file(self):
        os.makedirs("output/chunks", exist_ok=True)
        chunk_file = f"output/chunks/{self.dataset_name}.txt"
        
        existing_data = {}
        if os.path.exists(chunk_file):
            try:
                with open(chunk_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and "\t" in line:
                            # Parse line format: "id: {id} \tChunk: {chunk text}"
                            parts = line.split("\t", 1)
                            if len(parts) == 2 and parts[0].startswith("id: ") and parts[1].startswith("Chunk: "):
                                chunk_id = parts[0][4:] 
                                chunk_text = parts[1][7:] 
                                existing_data[chunk_id] = chunk_text
            except Exception as e:
                logger.warning(f"Failed to parse existing chunks from {chunk_file}: {type(e).__name__}: {e}")
        
        all_data = {**existing_data, **self.all_chunks}
        
        with open(chunk_file, "w", encoding="utf-8") as f:
            for chunk_id, chunk_text in all_data.items():
                f.write(f"id: {chunk_id}\tChunk: {chunk_text}\n")
        
        logger.info(f"Chunk data saved to {chunk_file} ({len(all_data)} chunks)")
    
    def extract_with_llm(self, prompt: str):
        response = self.llm_client.call_api(prompt)
        parsed_dict = json_repair.loads(response)
        parsed_json = json.dumps(parsed_dict, ensure_ascii=False)
        return parsed_json 

    def token_cal(self, text: str):
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    
    def _get_construction_prompt(self, chunk: str) -> str:
        """Get the appropriate construction prompt based on dataset name and mode (agent/noagent)."""
        recommend_schema = json.dumps(self.schema, ensure_ascii=False)
        
        # Base prompt type mapping
        prompt_type_map = {
            "novel": "novel",
            "novel_eng": "novel_eng"
        }
        
        base_prompt_type = prompt_type_map.get(self.dataset_name, "general")
        
        # Add agent suffix if in agent mode
        if self.mode == "agent":
            prompt_type = f"{base_prompt_type}_agent"
        else:
            prompt_type = base_prompt_type
        
        return self.config.get_prompt_formatted("construction", prompt_type, schema=recommend_schema, chunk=chunk)
    
    def _validate_and_parse_llm_response(self, prompt: str, llm_response: str) -> dict:
        """Validate and parse LLM response, returning None if invalid."""
        if llm_response is None:
            return None
            
        try:
            self.token_len += self.token_cal(prompt + llm_response)
            return json_repair.loads(llm_response)
        except Exception as e:
            llm_response_str = str(llm_response) if llm_response is not None else "None"
            return None
    
    def _find_or_create_entity(self, entity_name: str, chunk_id: int, nodes_to_add: list, entity_type: str = None) -> str:
        """Find existing entity or create a new one, returning the entity node ID."""
        with self.lock:
            entity_node_id = next(
                (
                    n
                    for n, d in self.graph.nodes(data=True)
                    if d.get("label") == "entity" and d["properties"]["name"] == entity_name
                ),
                None,
            )
            
            if not entity_node_id:
                entity_node_id = f"entity_{self.node_counter}"
                properties = {"name": entity_name, "chunk id": chunk_id}
                if entity_type:
                    properties["schema_type"] = entity_type
                
                nodes_to_add.append((
                    entity_node_id,
                    {
                        "label": "entity", 
                        "properties": properties, 
                        "level": 2
                    }
                ))
                self.node_counter += 1
                
        return entity_node_id
    
    def _validate_triple_format(self, triple: list) -> tuple:
        """Validate and normalize triple format, returning (subject, predicate, object) or None."""
        try:
            if len(triple) > 3:
                triple = triple[:3]
            elif len(triple) < 3:
                return None
            
            return tuple(triple)
        except Exception as e:
            return None
    
    def _process_attributes(self, extracted_attr: dict, chunk_id: int, entity_types: dict = None) -> tuple[list, list]:
        """Process extracted attributes and return nodes and edges to add."""
        nodes_to_add = []
        edges_to_add = []
        
        for entity, attributes in extracted_attr.items():
            for attr in attributes:
                # Create attribute node
                attr_node_id = f"attr_{self.node_counter}"
                nodes_to_add.append((
                    attr_node_id,
                    {
                        "label": "attribute",
                        "properties": {"name": attr, "chunk id": chunk_id},
                        "level": 1,
                    }
                ))
                self.node_counter += 1

                entity_type = entity_types.get(entity) if entity_types else None
                entity_node_id = self._find_or_create_entity(entity, chunk_id, nodes_to_add, entity_type)
                edges_to_add.append((entity_node_id, attr_node_id, "has_attribute"))
        
        return nodes_to_add, edges_to_add
    
    def _process_triples(self, extracted_triples: list, chunk_id: int, entity_types: dict = None) -> tuple[list, list]:
        """Process extracted triples and return nodes and edges to add."""
        nodes_to_add = []
        edges_to_add = []
        
        for triple in extracted_triples:
            validated_triple = self._validate_triple_format(triple)
            if not validated_triple:
                continue
                
            subj, pred, obj = validated_triple
            
            subj_type = entity_types.get(subj) if entity_types else None
            obj_type = entity_types.get(obj) if entity_types else None
            
            subj_node_id = self._find_or_create_entity(subj, chunk_id, nodes_to_add, subj_type)
            obj_node_id = self._find_or_create_entity(obj, chunk_id, nodes_to_add, obj_type)
            
            edges_to_add.append((subj_node_id, obj_node_id, pred, chunk_id))
        
        return nodes_to_add, edges_to_add

    def process_level1_level2(self, chunk: str, id: int):
        """Process attributes (level 1) and triples (level 2) with optimized structure."""
        prompt = self._get_construction_prompt(chunk)
        llm_response = self.extract_with_llm(prompt)
        
        # Validate and parse response
        parsed_response = self._validate_and_parse_llm_response(prompt, llm_response)
        if not parsed_response:
            return
        
        extracted_attr = parsed_response.get("attributes", {})
        extracted_triples = parsed_response.get("triples", [])
        entity_types = parsed_response.get("entity_types", {})
        
        # Process attributes and triples
        attr_nodes, attr_edges = self._process_attributes(extracted_attr, id, entity_types)
        triple_nodes, triple_edges = self._process_triples(extracted_triples, id, entity_types)
        
        all_nodes = attr_nodes + triple_nodes
        # all_edges = attr_edges + triple_edges
        
        with self.lock:
            for node_id, node_data in all_nodes:
                self.graph.add_node(node_id, **node_data)
            
            # for u, v, relation in all_edges:
            #     self.graph.add_edge(u, v, relation=relation)

            for u, v, relation in attr_edges:
                self.graph.add_edge(u, v, relation=relation)

            for subj, obj, relation, source_chunk_id in triple_edges:
                edge_data = {"relation": relation}
                if source_chunk_id:
                    edge_data["source_chunks"] = [source_chunk_id]
                self.graph.add_edge(subj, obj, **edge_data)


    def _find_or_create_entity_direct(self, entity_name: str, chunk_id: int, entity_type: str = None) -> str:
        """Find existing entity or create a new one directly in graph (for agent mode)."""
        entity_node_id = next(
            (
                n
                for n, d in self.graph.nodes(data=True)
                if d.get("label") == "entity" and d["properties"]["name"] == entity_name
            ),
            None,
        )
        
        if not entity_node_id:
            entity_node_id = f"entity_{self.node_counter}"
            properties = {"name": entity_name, "chunk id": chunk_id}
            if entity_type:
                properties["schema_type"] = entity_type
                
            self.graph.add_node(
                entity_node_id, 
                label="entity", 
                properties=properties, 
                level=2
            )
            self.node_counter += 1
            
        return entity_node_id
    
    def _process_attributes_agent(self, extracted_attr: dict, chunk_id: int, entity_types: dict = None):
        """Process extracted attributes in agent mode (direct graph operations)."""
        for entity, attributes in extracted_attr.items():
            for attr in attributes:
                # Create attribute node
                attr_node_id = f"attr_{self.node_counter}"
                self.graph.add_node(
                    attr_node_id,
                    label="attribute",
                    properties={
                        "name": attr,
                        "chunk id": chunk_id
                    },
                    level=1,
                )
                self.node_counter += 1

                entity_type = entity_types.get(entity) if entity_types else None
                entity_node_id = self._find_or_create_entity_direct(entity, chunk_id, entity_type)
                self.graph.add_edge(entity_node_id, attr_node_id, relation="has_attribute")
    
    def _process_triples_agent(self, extracted_triples: list, chunk_id: int, entity_types: dict = None):
        """Process extracted triples in agent mode (direct graph operations)."""
        for triple in extracted_triples:
            validated_triple = self._validate_triple_format(triple)
            if not validated_triple:
                continue
                
            subj, pred, obj = validated_triple
            
            subj_type = entity_types.get(subj) if entity_types else None
            obj_type = entity_types.get(obj) if entity_types else None
            
            # Find or create subject and object entities
            subj_node_id = self._find_or_create_entity_direct(subj, chunk_id, subj_type)
            obj_node_id = self._find_or_create_entity_direct(obj, chunk_id, obj_type)
            
            # self.graph.add_edge(subj_node_id, obj_node_id, relation=pred)

            edge_data = {"relation": pred}
            if chunk_id:
                edge_data["source_chunks"] = [chunk_id]
            self.graph.add_edge(subj_node_id, obj_node_id, **edge_data)


    def process_level1_level2_agent(self, chunk: str, id: int):
        """Process attributes (level 1) and triples (level 2) with agent mechanism for schema evolution.
        
        This method enables dynamic schema evolution by allowing the LLM to suggest new entity types,
        relation types, and attribute types that can be added to the existing schema.
        """
        prompt = self._get_construction_prompt(chunk)
        llm_response = self.extract_with_llm(prompt)
        
        # Validate and parse response (reuse helper method)
        parsed_response = self._validate_and_parse_llm_response(prompt, llm_response)
        if not parsed_response:
            return

        # Handle schema evolution
        new_schema_types = parsed_response.get("new_schema_types", {})
        if new_schema_types:
            self._update_schema_with_new_types(new_schema_types)
        
        extracted_attr = parsed_response.get("attributes", {})
        extracted_triples = parsed_response.get("triples", [])
        entity_types = parsed_response.get("entity_types", {})
        
        with self.lock:
            self._process_attributes_agent(extracted_attr, id, entity_types)
            self._process_triples_agent(extracted_triples, id, entity_types)

    def _update_schema_with_new_types(self, new_schema_types: Dict[str, List[str]]):
        """Update the schema file with new types discovered by the agent.
        
        This method processes schema evolution suggestions from the LLM and updates
        the corresponding schema file with new node types, relations, and attributes.
        Only adds types that don't already exist in the current schema.
        
        Args:
            new_schema_types: Dictionary containing 'nodes', 'relations', and 'attributes' lists
        """
        try:
            schema_paths = {
                "hotpot": "schemas/hotpot.json",
                "2wiki": "schemas/2wiki.json", 
                "musique": "schemas/musique.json",
                "novel": "schemas/novels_chs.json",
                "graphrag-bench": "schemas/graphrag-bench.json"
            }
            
            schema_path = schema_paths.get(self.dataset_name)
            if not schema_path:
                return
                
            with open(schema_path, 'r', encoding='utf-8') as f:
                current_schema = json.load(f)
            
            updated = False
            
            if "nodes" in new_schema_types:
                for new_node in new_schema_types["nodes"]:
                    if new_node not in current_schema.get("Nodes", []):
                        current_schema.setdefault("Nodes", []).append(new_node)
                        updated = True
            
            if "relations" in new_schema_types:
                for new_relation in new_schema_types["relations"]:
                    if new_relation not in current_schema.get("Relations", []):
                        current_schema.setdefault("Relations", []).append(new_relation)
                        updated = True

            if "attributes" in new_schema_types:
                for new_attribute in new_schema_types["attributes"]:
                    if new_attribute not in current_schema.get("Attributes", []):
                        current_schema.setdefault("Attributes", []).append(new_attribute)
                        updated = True
            
            # Save updated schema back to file
            if updated:
                with open(schema_path, 'w', encoding='utf-8') as f:
                    json.dump(current_schema, f, ensure_ascii=False, indent=2)
                
                # Update the in-memory schema
                self.schema = current_schema
                
        except Exception as e:
            logger.error(f"Failed to update schema for dataset '{self.dataset_name}': {type(e).__name__}: {e}")

    def process_level4(self, dedup = "normal"):
        """Process communities using Tree-Comm algorithm"""
        level2_nodes = [n for n, d in self.graph.nodes(data=True) if d['level'] == 2]
        start_comm = time.time()
        _tree_comm = tree_comm.FastTreeComm(
            self.graph, 
            embedding_model=self.config.tree_comm.embedding_model,
            struct_weight=self.config.tree_comm.struct_weight,
        )
        comm_to_nodes = _tree_comm.detect_communities(level2_nodes)

        if dedup == "semantic":
            _, keyword_mapping = _tree_comm.create_super_nodes_with_keywords(comm_to_nodes, level=4)
            if keyword_mapping:
                try:
                    self._deduplicate_keyword_nodes(keyword_mapping)
                except Exception as keyword_error:
                    logger.warning(
                        "Keyword semantic deduplication failed: %s: %s",
                        type(keyword_error).__name__,
                        keyword_error,
                    )
        else:

        # create super nodes (level 4 communities)
            _tree_comm.create_super_nodes_with_keywords(comm_to_nodes, level=4)
        # _tree_comm.add_keywords_to_level3(comm_to_nodes)
        # connect keywords to communities (optional)
        # self._connect_keywords_to_communities()
        end_comm = time.time()
        logger.info(f"Community Indexing Time: {end_comm - start_comm}s")
    
    def _connect_keywords_to_communities(self):
        """Connect relevant keywords to communities"""
        # comm_names = [self.graph.nodes[n]['properties']['name'] for n, d in self.graph.nodes(data=True) if d['level'] == 4]
        comm_nodes = [n for n, d in self.graph.nodes(data=True) if d['level'] == 4]
        kw_nodes = [n for n, d in self.graph.nodes(data=True) if d['label'] == 'keyword']
        with self.lock:
            for comm in comm_nodes:
                comm_name = self.graph.nodes[comm]['properties']['name'].lower()
                for kw in kw_nodes:
                    kw_name = self.graph.nodes[kw]['properties']['name'].lower()
                    if kw_name in comm_name or comm_name in kw_name:
                        self.graph.add_edge(kw, comm, relation="describes")

    def process_document(self, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process a single document and return its results."""
        try:
            if not doc:
                raise ValueError("Document is empty or None")
            
            chunks, chunk2id = self.chunk_text(doc)
            
            if not chunks or not chunk2id:
                raise ValueError(f"No valid chunks generated from document. Chunks: {len(chunks)}, Chunk2ID: {len(chunk2id)}")
            
            for chunk in chunks:
                try:
                    id = next(key for key, value in chunk2id.items() if value == chunk)
                except StopIteration:
                    id = nanoid.generate(size=8)
                    chunk2id[id] = chunk
                
                # Route to appropriate processing method based on mode
                if self.mode == "agent":
                    # Agent mode: includes schema evolution capabilities
                    self.process_level1_level2_agent(chunk, id)
                else:
                    # NoAgent mode: standard processing without schema evolution
                    self.process_level1_level2(chunk, id)
                
        except Exception as e:
            error_msg = f"Error processing document: {type(e).__name__}: {str(e)}"
            raise Exception(error_msg) from e

    def process_all_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Process all documents with high concurrency and pass results to process_level4."""

        max_workers = min(self.config.construction.max_workers, (os.cpu_count() or 1) + 4)
        start_construct = time.time()
        total_docs = len(documents)
        
        logger.info(f"Starting processing {total_docs} documents with {max_workers} workers...")

        all_futures = []
        processed_count = 0
        failed_count = 0
        
        try:
            with futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all documents for processing and store futures
                all_futures = [executor.submit(self.process_document, doc) for doc in documents]

                for i, future in enumerate(futures.as_completed(all_futures)):
                    try:
                        future.result()
                        processed_count += 1
                        
                        if processed_count % 10 == 0 or processed_count == total_docs:
                            elapsed_time = time.time() - start_construct
                            avg_time_per_doc = elapsed_time / processed_count if processed_count > 0 else 0
                            remaining_docs = total_docs - processed_count
                            estimated_remaining_time = remaining_docs * avg_time_per_doc
                            
                            logger.info(f"Progress: {processed_count}/{total_docs} documents processed "
                                  f"({processed_count/total_docs*100:.1f}%) "
                                  f"[{failed_count} failed] "
                                  f"ETA: {estimated_remaining_time/60:.1f} minutes")
                        
                    except Exception as e:
                        failed_count += 1

        except Exception as e:
            return

        end_construct = time.time()
        logger.info(f"Construction Time: {end_construct - start_construct}s")
        logger.info(f"Successfully processed: {processed_count}/{total_docs} documents")
        logger.info(f"Failed: {failed_count} documents")
        
        logger.info(f"🚀🚀🚀🚀 {'Processing Level 3 and 4':^20} 🚀🚀🚀🚀")
        logger.info(f"{'➖' * 20}")
        self.triple_deduplicate()
        self.process_level4()

    def _semantic_dedup_enabled(self) -> bool:
        config = getattr(self.config.construction, "semantic_dedup", None)
        return bool(config and config.enabled)

    def _get_semantic_dedup_config(self):
        return getattr(self.config.construction, "semantic_dedup", None)
    
    def _get_online_API_embedder(self):

        class OnlineAPIEmbedder:
            def __init__(self, config):
                self.online_embed_client = call_llm_api.LLMEmbeddingCall()
                # Get embedding batch size from config, default to 100
                self.batch_size = getattr(config, "embedding_batch_size", 100) if config else 100

            def encode(self, texts, normalize_embeddings=True):
                if len(texts) <= self.batch_size:
                    # Single batch
                    embeddings_list = self.online_embed_client.call_api(texts)
                    num_embeddings = len(texts)
                    embeddings = []
                    for i in range(num_embeddings):
                        embeddings.append(embeddings_list[i])
                    embeddings_array = np.array(embeddings)
                else:
                    # Process in batches
                    embeddings_array = []
                    to_retry = []
                    for batch_start in range(0, len(texts), self.batch_size):
                        batch_end = min(batch_start + self.batch_size, len(texts))
                        batch_texts = texts[batch_start:batch_end]
                        logger.info(f"Processing embedding batch {batch_start//self.batch_size + 1}/{(len(texts)-1)//self.batch_size + 1} ({batch_end - batch_start} texts)")

                        try:
                            batch_embeddings_list = self.online_embed_client.call_api(batch_texts)
                            for embedding in batch_embeddings_list:
                                embeddings_array.append(embedding)
                        except Exception as e:
                            logger.error(f"Failed to process embedding batch {batch_start}-{batch_end}: {e}")
                            # On failure, add zero vectors as fallback
                            for _ in batch_texts:
                                embeddings_array.append([0.0] * 1536)  # Assuming 1536-dim embeddings

                    embeddings_array = np.array(embeddings_array)

                if normalize_embeddings:
                    # Normalize each embedding
                    norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
                    norms[norms == 0] = 1  # Avoid division by zero
                    embeddings_array = embeddings_array / norms

                return embeddings_array

        config = self._get_semantic_dedup_config()
        return OnlineAPIEmbedder(config)
        
    def _get_semantic_dedup_embedder(self):
        config = self._get_semantic_dedup_config()
        if not config or not config.use_embeddings:
            return None

        if self._semantic_dedup_embedder is not None:
            return self._semantic_dedup_embedder

        model_name = getattr(config, "embedding_model", "") or getattr(self.config.embeddings, "model_name", "all-MiniLM-L6-v2")
        try:
            from sentence_transformers import SentenceTransformer

            self._semantic_dedup_embedder = SentenceTransformer(f"/home/hhy/GPT/workspace/m_youtu/sentence-transformers/{model_name}")
        except Exception as e:
            logger.warning(
                "Failed to initialize semantic dedup embedder with model '%s': %s: %s",
                model_name,
                type(e).__name__,
                e,
            )
            self._semantic_dedup_embedder = None

        return self._semantic_dedup_embedder

    def _describe_node(self, node_id: str) -> str:
        node_data = self.graph.nodes.get(node_id, {})
        label = node_data.get("label", "node")
        properties = node_data.get("properties", {})

        if isinstance(properties, dict):
            name = properties.get("name") or properties.get("title")
            extras = []
            for key, value in properties.items():
                if key == "name" or value in (None, "") or key in ['node_role', 'aliases', 'alias_of']:
                    continue
                extras.append(f"{key}: {value}")

            extra_text = ", ".join(extras)
            if name and extra_text:
                return f"{name} ({extra_text}) [{label}]"
            if name:
                return f"{name} [{label}]"
            if extra_text:
                return f"{label} ({extra_text})"

        return f"{label}:{node_id}"

    def _describe_node_for_clustering(self, node_id: str) -> str:
        """Generate a simplified description for semantic clustering.
        
        This method excludes chunk_id and label information to focus on
        the semantic content of the node for better clustering results.
        """
        node_data = self.graph.nodes.get(node_id, {})
        properties = node_data.get("properties", {})

        if isinstance(properties, dict):
            name = properties.get("name") or properties.get("title")
            extras = []
            for key, value in properties.items():
                # Skip name, chunk_id, and empty values
                if key == "name" or key == "chunk id" or key == "chunk_id" or value in (None, ""):
                    continue
                extras.append(f"{key}: {value}")

            extra_text = ", ".join(extras)
            if name and extra_text:
                return f"{name} ({extra_text})"
            if name:
                return name
            if extra_text:
                return extra_text

        # Fallback to node name only
        return properties.get("name") or properties.get("title") or node_id

    def _collect_node_chunk_ids(self, node_id: str) -> list:
        node_data = self.graph.nodes.get(node_id, {})
        properties = node_data.get("properties", {}) if isinstance(node_data, dict) else {}
        chunk_id = None
        if isinstance(properties, dict):
            chunk_id = properties.get("chunk id") or properties.get("chunk_id")

        if not chunk_id:
            return []

        return [chunk_id] if isinstance(chunk_id, str) else list(chunk_id)

    def _extract_edge_chunk_ids(self, edge_data: dict | None) -> list:
        if not isinstance(edge_data, dict):
            return []

        chunk_ids = edge_data.get("source_chunks") or edge_data.get("source_chunk_ids")
        if not chunk_ids:
            return []

        if isinstance(chunk_ids, (list, tuple, set)):
            return [chunk for chunk in chunk_ids if isinstance(chunk, str) and chunk]

        if isinstance(chunk_ids, str):
            return [chunk_ids]

        return []

    def _summarize_contexts(self, chunk_ids: list, max_items: int = 10, max_chars: int = 5000) -> list:
        summaries: list = []
        seen: set = set()

        for chunk_id in chunk_ids:
            if not chunk_id or chunk_id in seen:
                continue

            seen.add(chunk_id)
            chunk_text = self.all_chunks.get(chunk_id)
            if not chunk_text:
                summaries.append(f"- ({chunk_id}) [context not available]")
                if len(summaries) >= max_items:
                    break
                continue

            snippet = " ".join(str(chunk_text).split())
            if len(snippet) > max_chars:
                snippet = snippet[:max_chars].rstrip() + "…"

            summaries.append(f"- ({chunk_id}) {snippet}")
            if len(summaries) >= max_items:
                break

        if not summaries:
            summaries.append("- (no context available)")

        return summaries
    def _llm_validate_semantic_dedup(self, groups: list, original_candidates: list,
                                     head_text: str = None, relation: str = None) -> tuple:
        """
        Use LLM to validate semantic deduplication results and fix inconsistencies.
        This validates that each group's rationale matches its members.
        
        Args:
            groups: List of dedup groups, each with members, representative, rationale
            original_candidates: Original candidate descriptions  
            head_text: Head entity text (optional, for context)
            relation: Relation text (optional, for context)
            
        Returns:
            Tuple of (corrected_groups, validation_report)
        """
        # Check if validation is enabled
        semantic_config = getattr(self.config.construction, "semantic_dedup", None)
        if not semantic_config or not getattr(semantic_config, "enable_semantic_dedup_validation", False):
            # Validation disabled, return original
            return groups, None
        
        if not groups or len(groups) <= 1:
            # Nothing to validate (need at least 2 groups to check for merge opportunities)
            return groups, None
        
        # Prepare candidates text
        candidates_blocks = []
        for idx, candidate in enumerate(original_candidates, start=1):
            candidates_blocks.append(f"[{idx}] {candidate}")
        candidates_text = "\n".join(candidates_blocks) if candidates_blocks else "[No candidates]"
        
        # Prepare dedup results text
        dedup_results_blocks = []
        for group_idx, group in enumerate(groups):
            members = group.get('members', [])
            # Convert to 1-based for LLM
            members_1based = [m + 1 for m in members]
            representative = group.get('representative', members[0] if members else 0) + 1
            rationale = group.get('rationale', '')
            dedup_results_blocks.append(
                f"Group {group_idx}: {{members: {members_1based}, representative: {representative}, "
                f"rationale: \"{rationale}\"}}"
            )
        dedup_results_text = "\n".join(dedup_results_blocks)
        
        # Build validation prompt
        prompt = DEFAULT_SEMANTIC_DEDUP_VALIDATION_PROMPT.format(
            head=head_text or "[UNKNOWN_HEAD]",
            relation=relation or "[UNKNOWN_RELATION]",
            candidates=candidates_text,
            dedup_results=dedup_results_text
        )
        
        # Call LLM for validation
        try:
            response = self.llm_dedup_client.call_api(prompt)
        except Exception as e:
            logger.warning("LLM semantic dedup validation call failed: %s, skipping validation", e)
            return groups, None
        
        # Parse validation response
        try:
            parsed = json_repair.loads(response)
        except Exception:
            try:
                parsed = json.loads(response)
            except Exception as parse_error:
                logger.warning("Failed to parse LLM semantic dedup validation response: %s, skipping validation", parse_error)
                return groups, None
        #import pdb; pdb.set_trace()
        try:
            has_inconsistencies = parsed.get('has_inconsistencies', False)
            inconsistencies = parsed.get('inconsistencies', [])
            corrected_groups_raw = parsed.get('corrected_groups')
        except Exception as e:
            logger.warning("Failed to parse LLM semantic dedup validation response: %s, skipping validation", e)
            #import pdb; pdb.set_trace()
        
        validation_report = {
            'has_inconsistencies': has_inconsistencies,
            'inconsistencies': inconsistencies,
            'original_group_count': len(groups),
            'validation_attempted': True
        }
        
        if not has_inconsistencies or not corrected_groups_raw:
            logger.info("LLM semantic dedup validation: No inconsistencies found or no corrections provided")
            validation_report['corrected'] = False
            return groups, validation_report
        
        # Apply corrections
        logger.info("LLM semantic dedup validation found %d inconsistencies, applying corrections", len(inconsistencies))
        logger.info("--------------------------")
        logger.debug("Groups: %s", groups)
        logger.info("--------------------------")
        logger.debug("Parsed: %s", parsed)
        logger.info("--------------------------")
        
        corrected_groups = []
        for group_info in corrected_groups_raw:
            if not isinstance(group_info, dict):
                continue
            
            members_raw = group_info.get("members")
            if not isinstance(members_raw, list):
                continue
            
            # Convert 1-based to 0-based
            corrected_members = []
            for member in members_raw:
                try:
                    member_idx = int(member) - 1  # Convert to 0-based
                except (TypeError, ValueError):
                    continue
                if 0 <= member_idx < len(original_candidates):
                    corrected_members.append(member_idx)
            
            if corrected_members:
                representative_raw = group_info.get("representative", corrected_members[0] + 1)
                try:
                    representative = int(representative_raw) - 1 if isinstance(representative_raw, (int, str)) else corrected_members[0]
                except:
                    representative = corrected_members[0]
                
                corrected_groups.append({
                    "members": corrected_members,
                    "representative": representative,
                    "rationale": group_info.get("rationale", "Corrected by validation"),
                    "validation_corrected": True
                })
        
        # Verify we got all items covered
        all_items = set(range(len(original_candidates)))
        covered_items = set()
        for group in corrected_groups:
            covered_items.update(group['members'])
        
        missing_items = all_items - covered_items
        if missing_items:
            logger.warning(
                "LLM validation output missing items %s. Keeping original groups to avoid data loss.",
                sorted(missing_items)
            )
            validation_report['corrected'] = False
            validation_report['error'] = f"Missing items in corrected_groups: {sorted(missing_items)}"
            return groups, validation_report

        validation_report['corrected'] = True
        validation_report['corrected_group_count'] = len(corrected_groups)
        validation_report['inconsistencies_fixed'] = inconsistencies
        
        logger.info(
            "LLM semantic dedup validation corrections applied: %d groups → %d groups, fixed %d inconsistencies",
            len(groups), len(corrected_groups), len(inconsistencies)
        )
        
        return groups, validation_report

    def _llm_validate_clustering(self, clusters: list, cluster_details: list, 
                                 descriptions: list, head_text: str = None, relation: str = None,
                                 index_offset: int = 0) -> tuple:
        """
        Use LLM to validate clustering results and fix inconsistencies.
        This is a second-pass validation where LLM checks its own clustering output.
        
        Args:
            clusters: List of cluster member lists
            cluster_details: List of cluster detail dicts with rationale
            descriptions: Original candidate descriptions
            head_text: Head entity text (optional, for context)
            relation: Relation text (optional, for context)
            index_offset: Offset for indices
            
        Returns:
            Tuple of (corrected_clusters, corrected_details, validation_report)
        """
        # Check if validation is enabled
        semantic_config = getattr(self.config.construction, "semantic_dedup", None)
        if not semantic_config or not getattr(semantic_config, "enable_clustering_validation", False):
            # Validation disabled, return original
            return clusters, cluster_details, None
        
        if not cluster_details or len(cluster_details) <= 1:
            # Nothing to validate (need at least 2 clusters to check for merge opportunities)
            return clusters, cluster_details, None
        
        # Prepare candidates text
        candidates_blocks = []
        for idx, desc in enumerate(descriptions, start=1):
            candidates_blocks.append(f"[{idx}] {desc}")
        candidates_text = "\n".join(candidates_blocks) if candidates_blocks else "[No candidates]"
        
        # Prepare clustering results text
        clustering_results_blocks = []
        for cluster_idx, detail in enumerate(cluster_details):
            members = detail.get('members', [])
            # Convert back to 1-based for LLM
            members_1based = [m - index_offset + 1 for m in members]
            rationale = detail.get('rationale', '') or detail.get('llm_rationale', '') or detail.get('description', '')
            clustering_results_blocks.append(
                f"Cluster {cluster_idx}: {{members: {members_1based}, description: \"{rationale}\"}}"
            )
        clustering_results_text = "\n".join(clustering_results_blocks)
        
        # Build validation prompt
        prompt = DEFAULT_CLUSTERING_VALIDATION_PROMPT.format(
            head=head_text or "[UNKNOWN_HEAD]",
            relation=relation or "[UNKNOWN_RELATION]",
            candidates=candidates_text,
            clustering_results=clustering_results_text
        )
        
        # Call LLM for validation
        try:
            response = self.clustering_llm_client.call_api(prompt)
        except Exception as e:
            logger.warning("LLM validation call failed: %s, skipping validation", e)
            return clusters, cluster_details, None
        
        # Parse validation response
        try:
            parsed = json_repair.loads(response)
        except Exception:
            try:
                parsed = json.loads(response)
            except Exception as parse_error:
                logger.warning("Failed to parse LLM validation response: %s, skipping validation", parse_error)
                return clusters, cluster_details, None
        
        has_inconsistencies = parsed.get('has_inconsistencies', False)
        inconsistencies = parsed.get('inconsistencies', [])
        corrected_clusters_raw = parsed.get('corrected_clusters')
        
        validation_report = {
            'has_inconsistencies': has_inconsistencies,
            'inconsistencies': inconsistencies,
            'original_cluster_count': len(clusters),
            'validation_attempted': True
        }
        
        if not has_inconsistencies or not corrected_clusters_raw:
            logger.info("LLM validation: No inconsistencies found or no corrections provided")
            validation_report['corrected'] = False
            return clusters, cluster_details, validation_report
        
        # Apply corrections
        logger.info("LLM validation found %d inconsistencies, applying corrections", len(inconsistencies))
        
        corrected_clusters = []
        corrected_details = []
        assigned = set()
        
        for cluster_idx, cluster_info in enumerate(corrected_clusters_raw):
            if not isinstance(cluster_info, dict):
                continue
            
            members_raw = cluster_info.get("members")
            if not isinstance(members_raw, list):
                continue
            
            # Convert 1-based to 0-based and add offset
            cluster_members = []
            for member in members_raw:
                try:
                    member_idx = int(member) - 1  # Convert to 0-based
                except (TypeError, ValueError):
                    continue
                if 0 <= member_idx < len(descriptions):
                    adjusted_idx = member_idx + index_offset
                    cluster_members.append(adjusted_idx)
                    assigned.add(member_idx)
            
            if cluster_members:
                corrected_clusters.append(cluster_members)
                corrected_details.append({
                    "cluster_id": cluster_idx,
                    "members": cluster_members,
                    "description": cluster_info.get("description", "Corrected by validation"),
                    "llm_rationale": cluster_info.get("description", ""),
                    "rationale": cluster_info.get("description", ""),
                    "validation_corrected": True
                })
        
        # Add any unassigned items as singletons
        for idx in range(len(descriptions)):
            if idx not in assigned:
                singleton_idx = idx + index_offset
                corrected_clusters.append([singleton_idx])
                corrected_details.append({
                    "cluster_id": len(corrected_clusters) - 1,
                    "members": [singleton_idx],
                    "description": "Singleton cluster (unassigned after correction)",
                    "llm_rationale": "",
                    "rationale": ""
                })
        
        validation_report['corrected'] = True
        validation_report['corrected_cluster_count'] = len(corrected_clusters)
        validation_report['inconsistencies_fixed'] = inconsistencies
        
        logger.info(
            "LLM validation corrections applied: %d clusters → %d clusters, fixed %d inconsistencies",
            len(clusters), len(corrected_clusters), len(inconsistencies)
        )
        
        return corrected_clusters, corrected_details, validation_report
    
    def _validate_and_fix_clustering_inconsistencies(self, clusters: list, cluster_details: list, 
                                                     descriptions: list, index_offset: int) -> tuple:
        """
        Validate and fix inconsistencies between cluster members and rationales.
        
        Detects cases where:
        - Rationale says items should be "merged/combined/same/identical/equivalent" but are in separate clusters
        - Rationale says items should be "separate/distinct/different" but are in the same cluster
        
        Args:
            clusters: List of cluster member lists
            cluster_details: List of cluster detail dicts
            descriptions: Original descriptions (for logging)
            index_offset: Offset applied to indices
            
        Returns:
            Tuple of (fixed_clusters, fixed_cluster_details)
        """
        import re
        
        merge_keywords = [
            r'应该?合并', r'可合并', r'需要合并', r'建议合并',
            r'should.*merge', r'can.*merge', r'need.*merge',
            r'identical', r'equivalent', r'same', r'完全一致', r'信息.*一致',
            r'互换使用', r'interchangeable', r'同义', r'synonym'
        ]
        
        separate_keywords = [
            r'应该?分开', r'保持.*独立', r'单独.*组', r'不.*合并',
            r'should.*separate', r'keep.*separate', r'distinct', r'different',
            r'不同', r'有差异', r'不一致'
        ]
        
        inconsistencies_found = []
        
        for idx, detail in enumerate(cluster_details):
            rationale = detail.get('rationale', '') or detail.get('llm_rationale', '') or detail.get('description', '')
            members = detail.get('members', [])
            
            if not rationale or len(members) == 0:
                continue
            
            rationale_lower = rationale.lower()
            
            # Check for merge keywords
            has_merge_keyword = any(re.search(pattern, rationale_lower, re.IGNORECASE) 
                                   for pattern in merge_keywords)
            
            # Check for separation keywords
            has_separate_keyword = any(re.search(pattern, rationale_lower, re.IGNORECASE)
                                      for pattern in separate_keywords)
            
            # Case 1: Rationale says "merge" but only 1 member (singleton cluster)
            if has_merge_keyword and len(members) == 1 and not has_separate_keyword:
                # Look for references to other clusters/groups in the rationale
                # Common patterns: "与组1", "with group 1", "cluster 1", "成员0"
                referenced_groups = []
                
                # Extract group numbers mentioned
                group_matches = re.findall(r'组\s*(\d+)', rationale)
                referenced_groups.extend([int(g) - 1 for g in group_matches if g.isdigit()])
                
                # Extract cluster numbers
                cluster_matches = re.findall(r'cluster\s*(\d+)', rationale_lower)
                referenced_groups.extend([int(c) for c in cluster_matches if c.isdigit()])
                
                # Extract member indices mentioned
                member_matches = re.findall(r'(?:成员|member|项)\s*(\d+)', rationale_lower)
                referenced_members = [int(m) - 1 + index_offset for m in member_matches if m.isdigit()]
                
                inconsistency = {
                    'type': 'singleton_but_should_merge',
                    'cluster_idx': idx,
                    'members': members,
                    'rationale': rationale,
                    'referenced_groups': referenced_groups,
                    'referenced_members': referenced_members,
                    'description': f"Cluster {idx} has only 1 member {members} but rationale says should merge"
                }
                inconsistencies_found.append(inconsistency)
                
                logger.warning(
                    "Clustering inconsistency detected: Cluster %d has 1 member %s but rationale says merge: '%s...'",
                    idx, members, rationale[:100]
                )
        
        # Log summary
        if inconsistencies_found:
            logger.warning(
                "Found %d clustering inconsistencies. These are likely LLM output errors where rationale "
                "contradicts the members array. Consider adjusting clustering prompt or reviewing results.",
                len(inconsistencies_found)
            )
            
            # Optionally save to file for analysis
            if hasattr(self, '_save_clustering_inconsistencies'):
                self._save_clustering_inconsistencies(inconsistencies_found, descriptions)
        
        # For now, we return the original clusters without automatic fixing
        # Automatic fixing is risky without understanding the full context
        # Users can review the logs and fix manually if needed
        
        return clusters, cluster_details

    def _cluster_candidate_tails_with_llm(self, head_text: str, relation: str, descriptions: list, max_batch_size: int = 30) -> list:
        """
        Cluster candidate tails using LLM for initial grouping.
        
        This method uses LLM to perform semantic clustering based on tail descriptions only,
        without context. It's more accurate than embedding-based clustering for complex cases.
        
        Args:
            head_text: Description of the head entity
            relation: The relation name
            descriptions: List of tail descriptions to cluster
            max_batch_size: Maximum number of tails to send to LLM at once
            
        Returns:
            List of clusters, where each cluster is a list of indices
        """
        if len(descriptions) <= 1:
            return [list(range(len(descriptions)))]
        
        # If there are too many tails, batch them
        all_clusters = []
        if len(descriptions) > max_batch_size:
            # Process in batches
            for batch_start in range(0, len(descriptions), max_batch_size):
                batch_end = min(batch_start + max_batch_size, len(descriptions))
                batch_descriptions = descriptions[batch_start:batch_end]
                batch_offset = batch_start
                
                batch_clusters = self._llm_cluster_batch(head_text, relation, batch_descriptions, batch_offset)
                all_clusters.extend(batch_clusters)
            return all_clusters
        else:
            # Process all at once
            return self._llm_cluster_batch(head_text, relation, descriptions, 0)
    
    def _llm_cluster_batch(self, head_text: str, relation: str, descriptions: list, index_offset: int = 0) -> list:
        """
        Use LLM to cluster a batch of tail descriptions.
        
        Args:
            head_text: Description of the head entity
            relation: The relation name
            descriptions: List of tail descriptions to cluster
            index_offset: Offset to add to indices (for batched processing)
            
        Returns:
            List of clusters with adjusted indices
        """
        # Build candidate list for prompt
        candidate_blocks = []
        for idx, description in enumerate(descriptions, start=1):
            candidate_blocks.append(f"[{idx}] {description}")
        
        candidates_text = "\n".join(candidate_blocks) if candidate_blocks else "[No candidates]"
        
        # Build prompt
        prompt = DEFAULT_LLM_CLUSTERING_PROMPT.format(
            head=head_text or "[UNKNOWN_HEAD]",
            relation=relation or "[UNKNOWN_RELATION]",
            candidates=candidates_text
        )
        
        # Call LLM
        try:
            response = self.llm_client.call_api(prompt)
        except Exception as e:
            logger.warning("LLM clustering call failed: %s: %s, falling back to single cluster", type(e).__name__, e)
            # Fallback: put all items in one cluster
            fallback_cluster = [[idx + index_offset for idx in range(len(descriptions))]]
            fallback_details = [{"description": "Fallback cluster (LLM call failed)", "members": fallback_cluster[0]}]
            return fallback_cluster, fallback_details
        
        # Parse response
        try:
            parsed = json_repair.loads(response)
        except Exception:
            try:
                parsed = json.loads(response)
            except Exception as parse_error:
                logger.warning("Failed to parse LLM clustering response: %s: %s, using fallback", type(parse_error).__name__, parse_error)
                fallback_cluster = [[idx + index_offset for idx in range(len(descriptions))]]
                fallback_details = [{"description": "Fallback cluster (parse failed)", "members": fallback_cluster[0]}]
                return fallback_cluster, fallback_details
            

        # import pdb; pdb.set_trace()
        clusters_raw = parsed.get("clusters") if isinstance(parsed, dict) else None
        if not isinstance(clusters_raw, list):
            logger.warning("LLM clustering response missing 'clusters' field, using fallback")
            fallback_cluster = [[idx + index_offset for idx in range(len(descriptions))]]
            fallback_details = [{"description": "Fallback cluster (invalid response)", "members": fallback_cluster[0]}]
            return fallback_cluster, fallback_details
        
        # Convert LLM output to cluster format
        clusters = []
        cluster_details = []
        assigned = set()
        
        for cluster_idx, cluster_info in enumerate(clusters_raw):
            if not isinstance(cluster_info, dict):
                continue
            
            members_raw = cluster_info.get("members")
            if not isinstance(members_raw, list):
                logger.warning(f"Invalid cluster members format, assert LIST, get {type(members_raw)} skipping cluster")
                continue
            
            # Convert 1-based indices to 0-based and add offset
            cluster_members = []
            for member in members_raw:
                try:
                    member_idx = int(member) - 1  # Convert to 0-based
                except (TypeError, ValueError):
                    continue
                if 0 <= member_idx < len(descriptions):
                    adjusted_idx = member_idx + index_offset
                    cluster_members.append(adjusted_idx)
                    assigned.add(member_idx)
            
            if cluster_members:
                clusters.append(cluster_members)
                # Save the LLM's description/rationale for this cluster
                cluster_details.append({
                    "cluster_id": cluster_idx,
                    "members": cluster_members,
                    "description": cluster_info.get("description", "No description provided"),
                    "llm_rationale": cluster_info.get("description", ""),
                    "rationale": cluster_info.get("rationale", "")  # Preserve rationale if provided separately
                })        
        
        # Add unassigned items as singleton clusters
        for idx in range(len(descriptions)):
            if idx not in assigned:
                singleton_idx = idx + index_offset
                clusters.append([singleton_idx])
                cluster_details.append({
                    "cluster_id": len(clusters) - 1,
                    "members": [singleton_idx],
                    "description": "Singleton cluster (unassigned by LLM)",
                    "llm_rationale": "",
                    "rationale": ""
                })
            
        # Two-step validation approach:
        # Step 1: LLM self-validation and correction (if enabled)
        clusters, cluster_details, validation_report = self._llm_validate_clustering(
            clusters, cluster_details, descriptions, head_text, relation, index_offset
        )
        
        # Step 2: Rule-based inconsistency detection (always run as backup)
        clusters, cluster_details = self._validate_and_fix_clustering_inconsistencies(
            clusters, cluster_details, descriptions, index_offset
        )

        return clusters, cluster_details

    def _cluster_candidate_tails(self, descriptions: list, threshold: float) -> list:
        if len(descriptions) <= 1:
            return [list(range(len(descriptions)))]

        embedder = self._get_semantic_dedup_embedder()
        if embedder is None:
            return [list(range(len(descriptions)))]

        try:
            embeddings = embedder.encode(descriptions, normalize_embeddings=True)
        except Exception as e:
            logger.warning("Failed to encode descriptions for semantic dedup: %s: %s", type(e).__name__, e)
            return [list(range(len(descriptions)))]

        # clusters: list = []
        # for idx, vector in enumerate(embeddings):
        #     vector_arr = np.asarray(vector, dtype=float)
        #     assigned = False
        #     for cluster in clusters:
        #         if any(float(np.dot(existing_vec, vector_arr)) >= threshold for existing_vec in cluster["vectors"]):
        #             cluster["members"].append(idx)
        #             cluster["vectors"].append(vector_arr)
        #             assigned = True
        #             break
        # import pdb; pdb.set_trace()
        try:
            from sklearn.cluster import AgglomerativeClustering
            
            # Convert embeddings to numpy array
            embeddings = np.asarray(embeddings, dtype=float)
            
            # Compute cosine similarity matrix (embeddings are already normalized)
            similarity_matrix = np.dot(embeddings, embeddings.T)
            
            # Convert similarity to distance: distance = 1 - similarity
            distance_matrix = 1 - similarity_matrix
            
            # Ensure distance matrix is symmetric and has zero diagonal
            distance_matrix = (distance_matrix + distance_matrix.T) / 2
            np.fill_diagonal(distance_matrix, 0)
            
            # Convert similarity threshold to distance threshold
            distance_threshold = 1 - threshold
            
            # Apply AgglomerativeClustering with average linkage
            clustering = AgglomerativeClustering(
                n_clusters=None,  # Don't specify number of clusters
                distance_threshold=distance_threshold,  # Use distance threshold instead
                linkage='average',  # Average linkage: mean distance between all pairs
                metric='precomputed'  # Use our precomputed distance matrix
            )
            
            labels = clustering.fit_predict(distance_matrix)
            
            # Convert cluster labels to list of index lists
            clusters_dict = {}
            for idx, label in enumerate(labels):
                if label not in clusters_dict:
                    clusters_dict[label] = []
                clusters_dict[label].append(idx)
            
            return list(clusters_dict.values())
            
        except ImportError:
            logger.warning("sklearn not available, falling back to simple single-linkage clustering")
            # Fallback to original implementation if sklearn is not available
            clusters: list = []
            for idx, vector in enumerate(embeddings):
                vector_arr = np.asarray(vector, dtype=float)
                assigned = False
                for cluster in clusters:
                    if any(float(np.dot(existing_vec, vector_arr)) >= threshold for existing_vec in cluster["vectors"]):
                        cluster["members"].append(idx)
                        cluster["vectors"].append(vector_arr)
                        assigned = True
                        break

                if not assigned:
                    clusters.append({"members": [idx], "vectors": [vector_arr]})

        # return [cluster["members"] for cluster in clusters]
        except Exception as e:
            logger.warning("Clustering failed: %s: %s, using fallback", type(e).__name__, e)
            # If anything goes wrong, put all items in one cluster
            return [list(range(len(descriptions)))]


    def _build_semantic_dedup_prompt(
        self,
        head_text: str,
        relation: str,
        head_context_lines: list,
        batch_entries: list,
        only_head_context: list,
    ) -> str:
        candidate_blocks = []
        for idx, entry in enumerate(batch_entries, start=1):
            description = entry.get("description") or "[NO DESCRIPTION]"
            context_lines = entry.get("context_summaries") or ["- (no context available)"]
            context_block = "\n        ".join(context_lines)
            candidate_blocks.append(
                f"[{idx}] Tail: {description}\n    Contexts:\n        {context_block}"
            )

        candidates_text = "\n".join(candidate_blocks) if candidate_blocks else "[No candidates]"
        relation_text = relation or "[UNKNOWN]"
        head_context_text = "\n".join(head_context_lines) if head_context_lines else "- (no context available)"
        only_head_context_text = "\n".join(only_head_context) if only_head_context else "- (no context available)"

        prompt_type = getattr(self._get_semantic_dedup_config(), "prompt_type", "general")
        prompt_kwargs = {
            "head": head_text or "[UNKNOWN_HEAD]",
            "relation": relation_text,
            "head_context": only_head_context_text,
            "candidates": candidates_text,
        }

        return self.config.get_prompt_formatted("semantic_dedup", prompt_type, **prompt_kwargs)

    def _llm_semantic_group(
        self,
        head_text: str,
        relation: str,
        head_context_lines: list,
        batch_entries: list,
    ) -> list:
        prompt = self._build_semantic_dedup_prompt(head_text, relation, head_context_lines, batch_entries)

        # Log LLM input in the requested format
        logger.info("=" * 80)
        logger.info("LLM Semantic Deduplication Input:")
        logger.info("Head and relation:")
        logger.info(f"{head_text} | {relation}")
        logger.info("")
        logger.info("Tail:")
        for idx, entry in enumerate(batch_entries):
            description = entry.get("description") or "[NO DESCRIPTION]"
            logger.info(f"{idx}: {description}")
        logger.info("=" * 80)

        try:
            response = self.llm_dedup_client.call_api(prompt)
        except Exception as e:
            logger.warning("Semantic dedup LLM call failed: %s: %s", type(e).__name__, e)
            return []

        try:
            parsed = json_repair.loads(response)
        except Exception:
            try:
                parsed = json.loads(response)
            except Exception as parse_error:
                logger.warning("Failed to parse semantic dedup LLM response: %s: %s", type(parse_error).__name__, parse_error)
                return []

        groups_raw = parsed.get("groups") if isinstance(parsed, dict) else None
        if not isinstance(groups_raw, list):
            return []

        groups: list = []
        assigned = set()
        for group in groups_raw:
            if not isinstance(group, dict):
                continue

            members_raw = group.get("members")
            if not isinstance(members_raw, list):
                continue

            normalized_members = []
            for member in members_raw:
                try:
                    member_idx = int(member) - 1
                except (TypeError, ValueError):
                    continue
                if 0 <= member_idx < len(batch_entries):
                    normalized_members.append(member_idx)

            if not normalized_members:
                continue

            rep_raw = group.get("representative")
            try:
                rep_idx = int(rep_raw) - 1 if rep_raw is not None else None
            except (TypeError, ValueError):
                rep_idx = None

            if rep_idx is None or rep_idx not in normalized_members:
                rep_idx = normalized_members[0]

            rationale = group.get("rationale")
            groups.append(
                {
                    "representative": rep_idx,
                    "members": normalized_members,
                    "rationale": rationale,
                }
            )
            assigned.update(normalized_members)

        for idx in range(len(batch_entries)):
            if idx not in assigned:
                groups.append({"representative": idx, "members": [idx], "rationale": None})

        # Log LLM output in the requested format
        # logger.info("=" * 80)
        logger.info("LLM Semantic Deduplication Output:")
        
        # Check if output is unchanged (each tail in its own cluster)
        is_unchanged = all(len(group.get("members", [])) == 1 for group in groups)
        
        if is_unchanged:
            logger.info("未做更改")
        else:
            # Group outputs by cluster
            for cluster_idx, group in enumerate(groups, start=1):
                members = group.get("members", [])
                if len(members) > 1:  # Only show clusters with multiple members
                    logger.info(f"cluster{cluster_idx}:")
                    for member_idx in members:
                        if 0 <= member_idx < len(batch_entries):
                            description = batch_entries[member_idx].get("description") or "[NO DESCRIPTION]"
                            logger.info(f"{description},")
                    logger.info("")
                    logger.info(f"Rationale: {group.get('rationale')}")
        
        logger.info("=" * 80)

        return groups
    
    def _generate_embedding_cache_key(self, texts: list) -> str:
        """
        Generate a cache key based on graph state and chunks for LLM results caching.
        """
        import hashlib
        import json

        cache_data = {
            'texts': texts}
        cache_str = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        cache_hash = hashlib.sha256(cache_str.encode('utf-8')).hexdigest()[:16]
        return f"embedding_cache_{cache_hash}.json"

    def _generate_llm_cache_key(self, prompts_with_metadata: list) -> str:
        """
        Generate a cache key based on graph state and chunks for LLM results caching.

        Args:
            prompts_with_metadata: List of prompt dictionaries

        Returns:
            str: Hash string that can be used as filename
        """
        import hashlib
        import json

        # Collect key data for hashing
        cache_data = {
            'dataset_name': self.dataset_name,
            'graph_nodes': sorted([str(node) for node in self.ori_graph.nodes()]),
            'graph_edges': sorted([f"{u}({self.ori_graph.nodes[u]['properties']['name']})-{v}({self.ori_graph.nodes[v]['properties']['name']})  -{k}" for u, v, k in self.ori_graph.edges(keys=True)]),
            'chunks_count': len(self.all_chunks),
            'chunks_keys': sorted(list(self.all_chunks.keys())),
            'prompts_count': len(prompts_with_metadata),
            'prompt_types': sorted([p.get('type') for p in prompts_with_metadata]),  # Sort for consistency
            'prompt_hashes': sorted([hashlib.md5(p.get('prompt', '').encode('utf-8')).hexdigest()[:8] for p in prompts_with_metadata])  # Sort for consistency
        }
        # Convert to JSON string and hash
        cache_str = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        cache_hash = hashlib.sha256(cache_str.encode('utf-8')).hexdigest()[:16]
        #print(f"cache_data: {cache_data}")
        #print(f"cache_hash: {cache_hash}")
        #with open("/home/hhy/GPT/workspace/m_youtu/cache/cache_data.json", "w", encoding="utf-8") as f:
        #    json.dump(cache_data, f, indent=2, ensure_ascii=False)
        return f"llm_cache_{cache_hash}.json"

    def _save_llm_results(self, cache_key: str, results: list) -> None:
        """
        Save LLM call results to local cache file.

        Args:
            cache_key: Cache key generated by _generate_llm_cache_key
            results: LLM call results to save
        """
        import os
        import json

        cache_dir = os.path.join("cache", "llm_results")
        os.makedirs(cache_dir, exist_ok=True)

        cache_path = os.path.join(cache_dir, cache_key)

        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': str(datetime.datetime.now()),
                    'results': results}, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved LLM results to cache: {cache_path}")
        except Exception as e:
            logger.warning(f"Failed to save LLM results to cache: {e}")

    def _load_llm_results(self, cache_key: str) -> list | None:
        """
        Load LLM call results from local cache file.

        Args:
            cache_key: Cache key generated by _generate_llm_cache_key

        Returns:
            List of cached results or None if not found/invalid
        """
        import os
        import json

        cache_dir = os.path.join("cache", "llm_results")
        cache_path = os.path.join(cache_dir, cache_key)

        if not os.path.exists(cache_path):
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                #import pdb; pdb.set_trace()
                data = json.load(f)
                results = data.get('results', [])
                logger.info(f"Loaded cached LLM results: {cache_path}")
                return results
        except Exception as e:
            logger.warning(f"Failed to load cached LLM results: {e}")
            return None

    def _save_embedding_results(self, cache_key: str, results: list) -> None:
        """
        Save embedding results to local cache file.
        """
        import os
        import json
        
        cache_dir = os.path.join("cache", "embedding_results")
        os.makedirs(cache_dir, exist_ok=True)

        cache_path = os.path.join(cache_dir, cache_key)

        try:
            with open(cache_path, 'wb') as f:
                pickle.dump({
                    'timestamp': str(datetime.datetime.now()),
                    'results': results
                }, f, protocol=4)
            logger.info(f"Saved embedding results to cache: {cache_path}")
        except Exception as e:
            logger.warning(f"Failed to save embedding results to cache: {e}")

    def _load_embedding_results(self, cache_key: str) -> list | None:
        """
        Load embedding results from local cache file.
        """
        import os
        import json

        cache_dir = os.path.join("cache", "embedding_results")
        cache_path = os.path.join(cache_dir, cache_key)

        if not os.path.exists(cache_path):
            return None

        try:
            with open(cache_path, 'rb') as f:
                data = pickle.load(f)
                results = data.get('results', [])
                logger.info(f"Loaded cached embedding results: {cache_path}")
                return np.concatenate(results, axis=0)
        except Exception as e:
            logger.warning(f"Failed to load cached embedding results: {e}")
            return None
    
    def _generate_embedding_cache_key(self, texts: list) -> str:
        """
        Generate a cache key based on graph state and chunks for LLM results caching.
        """
        import hashlib
        import json
        
        cache_data = {
            'texts': texts}
        cache_str = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        cache_hash = hashlib.sha256(cache_str.encode('utf-8')).hexdigest()[:16]
        return f"embedding_cache_{cache_hash}.json"

    def _concurrent_embedding_calls(self, texts: list, enable_cache: bool = True) -> list:
        """
        Concurrently process multiple embedding calls.
        """
        embedder = self._get_online_API_embedder()
        embedding_batch_size = getattr(self._get_semantic_dedup_config(), "embedding_batch_size", 1000)

        if embedder is None:
            return []
        
        cached_results = None

        if enable_cache:
            
            cache_key = self._generate_embedding_cache_key(texts)
            cached_results = self._load_embedding_results(cache_key)
            if cached_results is not None:
                logger.info(f"Using cached embedding results for {len(cached_results)} texts")
                return cached_results

        def retry_sync(fun, item, index):
            """Synchronous retry function"""
            start_time = datetime.datetime.now()
            max_wait_time = 1 * 3600
            attempt_count = 0
            retry_delay = 10  # Initial retry delay
            MAX_RETRY_WAIT_SECONDS = 300  # Max 5 minutes between retries

            while True:
                attempt_count += 1
                elapsed = (datetime.datetime.now() - start_time).total_seconds()
                if elapsed > max_wait_time:
                    logger.error("Max wait time (%ds) exceeded. ", max_wait_time)
                    return None
                try:
                    return fun(item, index)
                except Exception as e:
                    import traceback
                    logger.warning(f"Embedding call failed: {e}\n{traceback.format_exc()}")

                    # Wait before retry (with exponential backoff) - sync sleep
                    retry_delay = min(retry_delay * 1.5, MAX_RETRY_WAIT_SECONDS)
                    logger.info(f"Embedding batch {index} waiting {retry_delay:.0f}s before next attempt...")
                    time.sleep(retry_delay)

        def _call_single_batch_embedding_sync(item, index):
            """Call embedding for a single batch of texts synchronously."""
            batch_texts = texts[item:item + embedding_batch_size]
            return embedder.encode(batch_texts)

        # Process batches synchronously with progress bar
        embeddings_array = []
        total_batches = (len(texts) + embedding_batch_size - 1) // embedding_batch_size

        with tqdm(total=total_batches, desc="Processing Embedding calls", unit="batch") as pbar:
            for batch_index in range(total_batches):
                start_index = batch_index * embedding_batch_size
                result = retry_sync(_call_single_batch_embedding_sync, start_index, batch_index)
                if result is not None:
                    embeddings_array.append(result)
                pbar.update(1)

        # Save results to cache if caching is enabled
        if enable_cache and embeddings_array:
            try:
                cache_key = self._generate_embedding_cache_key(texts)
                self._save_embedding_results(cache_key, embeddings_array)
            except Exception as e:
                logger.warning(f"Failed to save embedding results to cache: {e}")

        return np.concatenate(embeddings_array, axis=0)

    def _concurrent_llm_calls(self, prompts_with_metadata: list, enable_cache: bool = True, type: str = "clustering") -> list:
        """
        Concurrently process multiple LLM prompts.

        Args:
            prompts_with_metadata: List of dicts with keys:
                - 'type': 'clustering' or 'semantic'
                - 'prompt': the prompt string
                - 'metadata': additional metadata for processing results
            enable_cache: Whether to enable caching of LLM results

        Returns:
            List of dicts with keys:
                - 'type': same as input
                - 'response': raw LLM response
                - 'metadata': same as input
                - 'error': error message if failed (None if successful)
        """


        if not prompts_with_metadata:
            return []

        # Check for cached results if caching is enabled
        if enable_cache:
            cache_key = self._generate_llm_cache_key(prompts_with_metadata)
            cached_results = self._load_llm_results(cache_key)
            if cached_results is not None:
                logger.info(f"Using cached LLM results for {len(cached_results)} prompts")
                return cached_results
        
        results = []
        
        def retry_sync(fun, item, index):
            """Synchronous retry function"""
            start_time = datetime.datetime.now()
            max_wait_time = 1 * 3600
            attempt_count = 0
            retry_delay = 10  # Initial retry delay
            MAX_RETRY_WAIT_SECONDS = 300  # Max 5 minutes between retries

            while True:
                attempt_count += 1
                elapsed = (datetime.datetime.now() - start_time).total_seconds()
                if elapsed > max_wait_time:
                    logger.error("Max wait time (%ds) exceeded. ", max_wait_time)
                    return None

                try:
                    return fun(item, index)
                except Exception as e:
                    import traceback
                    logger.warning(f"LLM call failed: {e}\n{traceback.format_exc()}")

                    # Wait before retry (with exponential backoff) - sync sleep
                    retry_delay = min(retry_delay * 1.5, MAX_RETRY_WAIT_SECONDS)
                    logger.info(f"Prompt {index} waiting {retry_delay:.0f}s before next attempt...")
                    time.sleep(retry_delay)

        def _call_single_llm(item, index):
            """Call LLM for a single prompt."""
            prompt_type = item.get('type')
            prompt = item.get('prompt')
            metadata = item.get('metadata', {})

            result = {
                'type': prompt_type,
                'metadata': metadata,
                'response': None,
                'error': None,
                'index': index
            }

            try:
                # Choose appropriate client based on type
                if prompt_type == 'clustering':
                    response = self.llm_client.call_api(prompt)
                elif prompt_type == 'semantic':
                    response = self.llm_dedup_client.call_api(prompt)
                elif prompt_type == 'head_dedup':
                    response = self.llm_dedup_client.call_api(prompt)
                else:
                    raise ValueError(f"Unknown prompt type: {prompt_type}")

                result['response'] = response
            except Exception as e:
                import traceback
                result['error'] = f"{e}\n{traceback.format_exc()}"
                logger.warning("LLM call failed for type %s: %s", prompt_type, result['error'])

            return result


        # Process prompts concurrently using ThreadPoolExecutor
        import concurrent.futures

        # Limit concurrent requests based on prompt type
        if prompts_with_metadata and prompts_with_metadata[0]['type'] == 'semantic':
            max_workers = 10  # LLM semantic dedup calls are not thread-safe, limit to 5
        else:
            max_workers = min(10, len(prompts_with_metadata))

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(retry_sync, _call_single_llm, item, index): index
                for index, item in enumerate(prompts_with_metadata)
            }

            # Process results as they complete with progress bar
            with tqdm(total=len(prompts_with_metadata), desc="Processing LLM calls", unit="call") as pbar:
                for future in concurrent.futures.as_completed(future_to_index):
                    result = future.result()
                    if result is not None:
                        results.append(result)
                    pbar.update(1)
                    time.sleep(0.5)

        # Sort results by original index to maintain order
        results.sort(key=lambda x: x['index'])

        # Save results to cache if caching is enabled
        if enable_cache and results:
            try:
                cache_key = self._generate_llm_cache_key(prompts_with_metadata)
                self._save_llm_results(cache_key, results)
            except Exception as e:
                logger.warning(f"Failed to save LLM results to cache: {e}")

        return results

    def _merge_duplicate_metadata(self, base_entry: dict, duplicates: list, rationale: str = None):
        if isinstance(base_entry, dict):
            base_data = base_entry.get("data", {})
            representative_chunks = list(base_entry.get("context_chunk_ids") or [])
            representative_contexts = list(base_entry.get("context_summaries") or [])
        else:
            base_data = base_entry
            representative_chunks = []
            representative_contexts = []

        merged = copy.deepcopy(base_data)

        combined_chunks: list = []

        def _append_chunk(chunk_id: str):
            if chunk_id and chunk_id not in combined_chunks:
                combined_chunks.append(chunk_id)

        for chunk_id in representative_chunks:
            _append_chunk(chunk_id)

        for chunk_id in self._extract_edge_chunk_ids(merged):
            _append_chunk(chunk_id)

        for duplicate in duplicates or []:
            if not isinstance(duplicate, dict):
                continue

            for chunk_id in duplicate.get("context_chunk_ids", []) or []:
                _append_chunk(chunk_id)

            duplicate_data = duplicate.get("raw_data") or duplicate.get("data")
            for chunk_id in self._extract_edge_chunk_ids(duplicate_data):
                _append_chunk(chunk_id)

        if combined_chunks:
            merged["source_chunks"] = combined_chunks

        semantic_info = merged.get("semantic_dedup")

        if rationale or duplicates or representative_contexts or combined_chunks:
            if semantic_info is None:
                semantic_info = {}
                merged["semantic_dedup"] = semantic_info

            if combined_chunks:
                semantic_info.setdefault("representative_chunk_ids", combined_chunks)

            if representative_contexts:
                semantic_info.setdefault("representative_contexts", representative_contexts)
            elif combined_chunks:
                semantic_info.setdefault(
                    "representative_contexts",
                    self._summarize_contexts(combined_chunks),
                )

            if rationale:
                rationales = semantic_info.setdefault("rationales", [])
                rationales.append(rationale)

            if duplicates:
                duplicate_entries = semantic_info.setdefault("duplicates", [])
                for duplicate in duplicates:
                    if not isinstance(duplicate, dict):
                        continue

                    duplicate_chunk_ids = list(duplicate.get("context_chunk_ids") or [])
                    duplicate_contexts = duplicate.get("context_summaries")
                    if not duplicate_contexts and duplicate_chunk_ids:
                        duplicate_contexts = self._summarize_contexts(duplicate_chunk_ids)

                    duplicate_entries.append(
                        {
                            "tail_node": duplicate.get("node_id"),
                            "tail_description": duplicate.get("description"),
                            "edge_attributes": copy.deepcopy(duplicate.get("raw_data", duplicate.get("data", {}))),
                            "context_chunk_ids": duplicate_chunk_ids,
                            "context_summaries": copy.deepcopy(duplicate_contexts or []),
                        }
                    )

        return merged

    def _set_node_chunk_ids(self, properties: dict, chunk_ids: set):
        if not isinstance(properties, dict):
            return

        normalized = [chunk_id for chunk_id in sorted(chunk_ids) if chunk_id]

        if not normalized:
            properties.pop("chunk id", None)
            properties.pop("chunk_id", None)
            return

        if len(normalized) == 1:
            properties["chunk id"] = normalized[0]
        else:
            properties["chunk id"] = normalized

    def _edge_exists(self, source: str, target: str, data: dict) -> bool:
        relation = data.get("relation") if isinstance(data, dict) else None
        existing = self.graph.get_edge_data(source, target, default={})

        for edge_data in existing.values() if isinstance(existing, dict) else []:
            if not isinstance(edge_data, dict):
                continue
            if relation and edge_data.get("relation") != relation:
                continue
            return True

        return False

    def _reassign_keyword_edges(self, source_id: str, target_id: str):
        incoming_edges = list(self.graph.in_edges(source_id, keys=True, data=True))
        for origin, _, _, data in incoming_edges:
            if origin == target_id:
                continue
            data_copy = copy.deepcopy(data)
            if not self._edge_exists(origin, target_id, data_copy):
                self.graph.add_edge(origin, target_id, **data_copy)

        outgoing_edges = list(self.graph.out_edges(source_id, keys=True, data=True))
        for _, destination, _, data in outgoing_edges:
            if destination == target_id:
                continue
            data_copy = copy.deepcopy(data)
            if not self._edge_exists(target_id, destination, data_copy):
                self.graph.add_edge(target_id, destination, **data_copy)

    def _merge_keyword_nodes(
        self,
        representative_entry: dict,
        duplicates: list,
        rationale: str | None,
        keyword_mapping: dict | None,
    ) -> list:
        rep_id = representative_entry.get("node_id") if isinstance(representative_entry, dict) else None
        if not rep_id or rep_id not in self.graph or not duplicates:
            return []

        rep_node = self.graph.nodes.get(rep_id, {})
        rep_properties = rep_node.setdefault("properties", {}) if isinstance(rep_node, dict) else {}

        representative_chunks = set(self._collect_node_chunk_ids(rep_id))
        for chunk_id in representative_entry.get("chunk_ids", []) or []:
            if chunk_id:
                representative_chunks.add(chunk_id)

        metadata = rep_properties.setdefault("semantic_dedup", {})
        metadata.setdefault("node_type", "keyword")

        rep_source_name = representative_entry.get("source_entity_name")
        if rep_source_name and "representative_source_entity" not in metadata:
            metadata["representative_source_entity"] = rep_source_name
            metadata["representative_source_entity_id"] = representative_entry.get("source_entity_id")

        rep_contexts = representative_entry.get("context_summaries") or []
        if rep_contexts and "representative_contexts" not in metadata:
            metadata["representative_contexts"] = list(rep_contexts)

        removed_nodes: list = []
        duplicates_info = metadata.setdefault("duplicates", [])

        if rationale:
            metadata.setdefault("rationales", []).append(rationale)

        for duplicate in duplicates:
            if not isinstance(duplicate, dict):
                continue

            dup_id = duplicate.get("node_id")
            if not dup_id or dup_id == rep_id or dup_id not in self.graph:
                continue

            dup_node = self.graph.nodes.get(dup_id, {})
            dup_props = dup_node.get("properties", {}) if isinstance(dup_node, dict) else {}

            duplicate_chunks = set(self._collect_node_chunk_ids(dup_id))
            for chunk_id in duplicate.get("chunk_ids", []) or []:
                if chunk_id:
                    duplicate_chunks.add(chunk_id)

            representative_chunks.update(duplicate_chunks)

            duplicate_contexts = duplicate.get("context_summaries") or []
            if not duplicate_contexts and duplicate_chunks:
                duplicate_contexts = self._summarize_contexts(sorted(duplicate_chunks))

            duplicates_info.append(
                {
                    "node_id": dup_id,
                    "name": dup_props.get("name") or duplicate.get("raw_name") or duplicate.get("description"),
                    "chunk_ids": sorted(duplicate_chunks),
                    "contexts": list(duplicate_contexts),
                    "source_entity": duplicate.get("source_entity_name"),
                    "source_entity_id": duplicate.get("source_entity_id"),
                }
            )

            self._reassign_keyword_edges(dup_id, rep_id)
            self.graph.remove_node(dup_id)
            removed_nodes.append(dup_id)

            if keyword_mapping is not None:
                keyword_mapping.pop(dup_id, None)

        if keyword_mapping is not None and not keyword_mapping.get(rep_id):
            for duplicate in duplicates or []:
                source_candidate = duplicate.get("source_entity_id") if isinstance(duplicate, dict) else None
                if source_candidate:
                    keyword_mapping[rep_id] = source_candidate
                    break

        if representative_chunks:
            self._set_node_chunk_ids(rep_properties, representative_chunks)
            metadata["representative_chunk_ids"] = sorted(representative_chunks)

        return removed_nodes

    def _apply_preloaded_clusters(self, dedup_communities: list, preloaded_data: dict) -> None:
        """
        Apply preloaded cluster results to communities, skipping the clustering phase.
        
        Args:
            dedup_communities: List of community data dicts to populate with cluster info
            preloaded_data: Previously saved intermediate results containing cluster info
        """
        logger.info("Applying preloaded cluster results...")
        
        # Build a mapping from community_id to preloaded community data
        preloaded_communities = {}
        for comm_data in preloaded_data.get("communities", []):
            comm_id = comm_data.get("community_id")
            if comm_id:
                preloaded_communities[comm_id] = comm_data
        
        matched_count = 0
        for community_data in dedup_communities:
            comm_id = community_data.get("community_id")
            preloaded_comm = preloaded_communities.get(comm_id)
            
            if not preloaded_comm:
                logger.warning(f"No preloaded cluster data found for community {comm_id}, using fallback single cluster")
                # Fallback: treat all as one cluster
                entries = community_data.get('entries', [])
                community_data['initial_clusters'] = [[e['index'] for e in entries]]
                community_data['llm_clustering_details'] = [{
                    "description": "Fallback cluster (no preloaded data)",
                    "llm_rationale": "",
                    "members": [e['index'] for e in entries]
                }]
                continue
            
            # Extract cluster information from preloaded data
            clustering_info = preloaded_comm.get("clustering", {})
            clusters_data = clustering_info.get("clusters", [])
            
            if not clusters_data:
                logger.warning(f"No cluster data in preloaded results for community {comm_id}")
                entries = community_data.get('entries', [])
                community_data['initial_clusters'] = [[e['index'] for e in entries]]
                community_data['llm_clustering_details'] = [{
                    "description": "Fallback cluster (empty preloaded data)",
                    "llm_rationale": "",
                    "members": [e['index'] for e in entries]
                }]
                continue
            
            # Convert preloaded cluster data to the format expected by semantic dedup
            initial_clusters = []
            llm_clustering_details = []
            
            for cluster_info in clusters_data:
                member_indices = cluster_info.get("member_indices", [])
                if member_indices:
                    initial_clusters.append(member_indices)
                    llm_clustering_details.append({
                        "description": cluster_info.get("llm_description", ""),
                        "llm_rationale": cluster_info.get("llm_rationale", ""),
                        "members": member_indices
                    })
            
            if not initial_clusters:
                logger.warning(f"No valid clusters extracted from preloaded data for community {comm_id}")
                entries = community_data.get('entries', [])
                community_data['initial_clusters'] = [[e['index'] for e in entries]]
                community_data['llm_clustering_details'] = [{
                    "description": "Fallback cluster (no valid clusters)",
                    "llm_rationale": "",
                    "members": [e['index'] for e in entries]
                }]
                continue
            
            community_data['initial_clusters'] = initial_clusters
            community_data['llm_clustering_details'] = llm_clustering_details
            matched_count += 1
            
        logger.info(f"Successfully applied preloaded clusters to {matched_count}/{len(dedup_communities)} communities")

    def _apply_preloaded_clusters_for_edges(self, dedup_groups: list, preloaded_data: dict) -> None:
        """
        Apply preloaded cluster results to edge deduplication groups, skipping the clustering phase.
        
        Args:
            dedup_groups: List of edge group data dicts to populate with cluster info
            preloaded_data: Previously saved intermediate results containing cluster info
        """
        logger.info("Applying preloaded cluster results for edge deduplication...")
        
        # Build a mapping from (head_id, relation) to preloaded triple data
        preloaded_triples = {}
        for triple_data in preloaded_data.get("triples", []):
            head_id = triple_data.get("head_id")
            relation = triple_data.get("relation")
            if head_id and relation:
                key = (head_id, relation)
                preloaded_triples[key] = triple_data
        
        matched_count = 0
        for group_data in dedup_groups:
            head_id = group_data.get("head_id")
            relation = group_data.get("relation")
            key = (head_id, relation)
            preloaded_triple = preloaded_triples.get(key)
            
            if not preloaded_triple:
                logger.warning(f"No preloaded cluster data found for ({head_id}, {relation}), using fallback single cluster")
                # Fallback: treat all as one cluster
                entries = group_data.get('entries', [])
                group_data['initial_clusters'] = [[e['index'] for e in entries]]
                group_data['llm_clustering_details'] = [{
                    "description": "Fallback cluster (no preloaded data)",
                    "llm_rationale": "",
                    "members": [e['index'] for e in entries]
                }]
                continue
            
            # Extract cluster information from preloaded data
            clustering_info = preloaded_triple.get("clustering", {})
            clusters_data = clustering_info.get("clusters", [])
            
            if not clusters_data:
                logger.warning(f"No cluster data in preloaded results for ({head_id}, {relation})")
                entries = group_data.get('entries', [])
                group_data['initial_clusters'] = [[e['index'] for e in entries]]
                group_data['llm_clustering_details'] = [{
                    "description": "Fallback cluster (empty preloaded data)",
                    "llm_rationale": "",
                    "members": [e['index'] for e in entries]
                }]
                continue
            
            # Convert preloaded cluster data to the format expected by semantic dedup
            initial_clusters = []
            llm_clustering_details = []
            
            for cluster_info in clusters_data:
                member_indices = cluster_info.get("member_indices", [])
                if member_indices:
                    initial_clusters.append(member_indices)
                    llm_clustering_details.append({
                        "description": cluster_info.get("llm_description", ""),
                        "llm_rationale": cluster_info.get("llm_rationale", ""),
                        "members": member_indices
                    })
            
            if not initial_clusters:
                logger.warning(f"No valid clusters extracted from preloaded data for ({head_id}, {relation})")
                entries = group_data.get('entries', [])
                group_data['initial_clusters'] = [[e['index'] for e in entries]]
                group_data['llm_clustering_details'] = [{
                    "description": "Fallback cluster (no valid clusters)",
                    "llm_rationale": "",
                    "members": [e['index'] for e in entries]
                }]
                continue
            
            group_data['initial_clusters'] = initial_clusters
            group_data['llm_clustering_details'] = llm_clustering_details
            matched_count += 1
            
        logger.info(f"Successfully applied preloaded clusters to {matched_count}/{len(dedup_groups)} edge groups")

    def _deduplicate_keyword_nodes(self, keyword_mapping: dict):
        if not keyword_mapping or not self._semantic_dedup_enabled():
            return

        config = self._get_semantic_dedup_config()
        if not config:
            return

        community_to_keywords: dict = defaultdict(list)
        for keyword_node_id in list(keyword_mapping.keys()):
            if keyword_node_id not in self.graph:
                continue
            for _, target, _, data in self.graph.out_edges(keyword_node_id, keys=True, data=True):
                if isinstance(data, dict) and data.get("relation") == "keyword_of":
                    community_to_keywords[target].append(keyword_node_id)

        if not community_to_keywords:
            return
        #import pdb; pdb.set_trace()
        # 打印待处理的关键词总数
        total_keywords = sum(len(kws) for kws in community_to_keywords.values())
        logger.info(f"开始关键词去重，共 {len(community_to_keywords)} 个社区，总计 {total_keywords} 个关键词待处理")


        threshold = getattr(config, "embedding_threshold", 0.85) or 0.85
        max_batch_size = max(1, int(getattr(config, "max_batch_size", 8) or 8))
        max_candidates = int(getattr(config, "max_candidates", 0) or 0)

        clustering_method = getattr(config, "clustering_method", "embedding")
        llm_clustering_batch_size = getattr(config, "llm_clustering_batch_size", 30)
        save_intermediate = getattr(config, "save_intermediate_results", False)


        # Initialize intermediate results collector
        # save_intermediate = getattr(config, "save_intermediate_results", False)
        intermediate_results = {
            "dataset": self.dataset_name,
            "config": {
                "threshold": threshold,
                "max_batch_size": max_batch_size,
                "max_candidates": max_candidates,
                "clustering_method": clustering_method,
            },
            "communities": []
        } if save_intermediate else None   


        # ================================================================
        # PHASE 1: Prepare all communities and collect metadata
        # ================================================================
        dedup_communities = []  # List of dicts with all info needed for deduplication
    

        for community_id, keyword_ids in community_to_keywords.items():
            # Deduplicate keyword_ids to prevent duplicate keywords in the same community
            keyword_ids = list(dict.fromkeys([kw for kw in keyword_ids if kw in self.graph]))
            if len(keyword_ids) <= 1:
                continue
            # Prepare community data
            community_data = self._prepare_keyword_dedup_community(
                community_id, keyword_ids, keyword_mapping, config
            )
            if community_data:
                dedup_communities.append(community_data)
        
        logger.info(f"Prepared {len(dedup_communities)} communities for keyword deduplication")
        
        if not dedup_communities:
            return
        
        # ================================================================
        # PHASE 2: Batch collect and process clustering prompts
        # ================================================================
        clustering_prompts = []
        
        # Check if we have preloaded keyword clusters to skip clustering phase
        if hasattr(self, 'preloaded_keyword_clusters') and self.preloaded_keyword_clusters:
            logger.info("Using preloaded keyword cluster results, skipping clustering phase...")
            self._apply_preloaded_clusters(dedup_communities, self.preloaded_keyword_clusters)
        elif clustering_method == "llm":
            logger.info("Collecting all keyword clustering prompts...")
            for comm_idx, community_data in enumerate(dedup_communities):
                prompts = self._collect_clustering_prompts(community_data)
                for prompt_data in prompts:
                    prompt_data['metadata']['comm_idx'] = comm_idx
                    clustering_prompts.append(prompt_data)
            
            logger.info(f"Collected {len(clustering_prompts)} keyword clustering prompts, processing concurrently...")
            clustering_results = self._concurrent_llm_calls(clustering_prompts)
            
            # Parse clustering results and update community_data
            logger.info("Parsing keyword clustering results...")
            self._parse_keyword_clustering_results(dedup_communities, clustering_results)
        else:
            # Use embedding-based clustering
            logger.info("Using embedding-based clustering for keywords...")
            for community_data in dedup_communities:
                self._apply_embedding_clustering(community_data)
        
        # ================================================================
        # PHASE 3: Batch collect and process semantic dedup prompts
        # ================================================================
        logger.info("Collecting all keyword semantic dedup prompts...")
        semantic_prompts = []
        
        for comm_idx, community_data in enumerate(dedup_communities):
            prompts = self._collect_semantic_dedup_prompts(community_data)
            for prompt_data in prompts:
                prompt_data['metadata']['comm_idx'] = comm_idx
                semantic_prompts.append(prompt_data)
        
        logger.info(f"Collected {len(semantic_prompts)} keyword semantic dedup prompts, processing concurrently...")
        semantic_results = self._concurrent_llm_calls(semantic_prompts)
        
        # Parse semantic dedup results and update community_data
        logger.info("Parsing keyword semantic dedup results...")
        self._parse_semantic_dedup_results(dedup_communities, semantic_results)
        
        # ================================================================
        # PHASE 4: Apply results and merge keyword nodes
        # ================================================================
        logger.info("Applying keyword deduplication results...")
        for community_data in dedup_communities:
            self._apply_keyword_dedup_results(community_data, keyword_mapping, save_intermediate, intermediate_results)
        
        logger.info("Keyword deduplication completed")
        
        # Save intermediate results to file
        if save_intermediate and intermediate_results:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = getattr(config, "intermediate_results_path", None)
            
            if not output_path:
                output_path = f"output/dedup_intermediate/{self.dataset_name}_keyword_dedup_{timestamp}.json"
            else:
                # If path is a directory, add filename
                if output_path.endswith('/'):
                    output_path = f"{output_path}{self.dataset_name}_keyword_dedup_{timestamp}.json"
                else:
                    # Add _keyword suffix
                    base, ext = os.path.splitext(output_path)
                    output_path = f"{base}_keyword_{timestamp}{ext}"
            
            # Ensure directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # Add summary statistics
            intermediate_results["summary"] = {
                "total_communities": len(intermediate_results["communities"]),
                "total_candidates": sum(c["total_candidates"] for c in intermediate_results["communities"]),
                "total_clusters": sum(len(c["clustering"]["clusters"]) for c in intermediate_results["communities"]),
                "total_llm_calls": sum(len(c["llm_groups"]) for c in intermediate_results["communities"]),
                "total_merges": sum(len(c["final_merges"]) for c in intermediate_results["communities"]),
                "total_items_merged": sum(c["summary"]["items_merged"] for c in intermediate_results["communities"])
            }
            
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(intermediate_results, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved keyword deduplication intermediate results to: {output_path}")
                logger.info(f"Summary: {intermediate_results['summary']}")
            except Exception as e:
                logger.warning(f"Failed to save intermediate results: {e}")



    def _prepare_keyword_dedup_community(self, community_id: str, keyword_ids: list, 
                                         keyword_mapping: dict, config) -> dict:
        """
        Prepare metadata for a keyword deduplication community.
        
        Returns:
            dict with keys: community_id, entries, head_text, head_context_lines, 
                           candidate_descriptions, config_params, etc.
        """
        threshold = getattr(config, "embedding_threshold", 0.85) or 0.85
        
        entries: list = []
        for kw_id in keyword_ids:
            node_data = self.graph.nodes.get(kw_id, {})
            properties = node_data.get("properties", {}) if isinstance(node_data, dict) else {}
            raw_name = properties.get("name") or properties.get("title") or kw_id
            
            chunk_ids = set(self._collect_node_chunk_ids(kw_id))
            source_entity_id = keyword_mapping.get(kw_id)
#                source_entity_name = None

            source_entity_name_full = None
            source_entity_name_simple = None


            if source_entity_id and source_entity_id in self.graph:
                # source_entity_name = self._describe_node(source_entity_id)
                source_entity_name_full = self._describe_node(source_entity_id)  # Full for LLM
                source_entity_name_simple = self._describe_node_for_clustering(source_entity_id)  # Simple for clustering

                for chunk_id in self._collect_node_chunk_ids(source_entity_id):
                    if chunk_id:
                        chunk_ids.add(chunk_id)

            description_full = raw_name
            if source_entity_name_full and source_entity_name_full not in description_full:
                description_full = f"{raw_name} (from {source_entity_name_full})"

            # Simplified description for vector clustering
            description_simple = raw_name
            if source_entity_name_simple and source_entity_name_simple not in description_simple:
                description_simple = f"{raw_name} (from {source_entity_name_simple})"

            context_summaries = self._summarize_contexts(list(chunk_ids))

            entries.append(
                {
                    "node_id": kw_id,
                    "description": description_full,
                    "description_for_clustering": description_simple,
                    "raw_name": raw_name,
                    "chunk_ids": list(chunk_ids),
                    "context_summaries": context_summaries,
                    "source_entity_id": source_entity_id,
                    "source_entity_name": source_entity_name_full,
                }
            )

            if len(entries) <= 1:
                continue

            for idx, entry in enumerate(entries):
                entry["index"] = idx

            community_chunk_ids = set()
            for entry in entries:
                for chunk_id in entry.get("chunk_ids", []):
                    if chunk_id:
                        community_chunk_ids.add(chunk_id)

        head_context_lines = self._summarize_contexts(list(community_chunk_ids))
        head_text = self._describe_node(community_id)
        candidate_descriptions = [entry["description_for_clustering"] for entry in entries]
        
        # Extract config parameters
        config_params = {
            'clustering_method': getattr(config, "clustering_method", "embedding"),
            'threshold': getattr(config, "embedding_threshold", 0.85) or 0.85,
            'llm_clustering_batch_size': getattr(config, "llm_clustering_batch_size", 30),
            'max_batch_size': max(1, int(getattr(config, "max_batch_size", 8) or 8)),
            'max_candidates': int(getattr(config, "max_candidates", 0) or 0),
        }

        return {
            'community_id': community_id,
            'head_text': head_text,
            'relation': 'keyword_of',
            'entries': entries,
            'head_context_lines': head_context_lines,
            'candidate_descriptions': candidate_descriptions,
            'config_params': config_params,
            'initial_clusters': None,  # Will be filled by clustering
            'llm_clustering_details': None,  # Will be filled by LLM clustering
            'semantic_results': {},  # Will be filled by semantic dedup
        }
    
    def _parse_keyword_clustering_results(self, dedup_communities: list, clustering_results: list):
        """
        Parse keyword clustering results and update dedup_communities.
        Similar to _parse_clustering_results but uses comm_idx instead of group_idx.
        """
        # Group results by comm_idx
        results_by_comm = defaultdict(list)
        for result in clustering_results:
            comm_idx = result['metadata'].get('comm_idx')
            if comm_idx is not None:
                results_by_comm[comm_idx].append(result)
        
        # Parse results for each community
        for comm_idx, results in results_by_comm.items():
            if comm_idx >= len(dedup_communities):
                continue
            
            community_data = dedup_communities[comm_idx]
            all_clusters = []
            all_details = []
            
            for result in results:
                metadata = result['metadata']
                batch_offset = metadata['batch_offset']
                batch_descriptions = metadata['descriptions']
                
                if result['error']:
                    # Fallback: single cluster
                    fallback_cluster = [idx + batch_offset for idx in range(len(batch_descriptions))]
                    all_clusters.append(fallback_cluster)
                    all_details.append({
                        "description": f"Fallback cluster (error: {result['error']})",
                        "members": fallback_cluster
                    })
                    continue
                
                # Parse clustering response
                try:
                    parsed = json_repair.loads(result['response'])
                except Exception:
                    try:
                        parsed = json.loads(result['response'])
                    except Exception:
                        # Fallback
                        fallback_cluster = [idx + batch_offset for idx in range(len(batch_descriptions))]
                        all_clusters.append(fallback_cluster)
                        all_details.append({
                            "description": "Fallback cluster (parse failed)",
                            "members": fallback_cluster
                        })
                        continue
                
                clusters_raw = parsed.get("clusters") if isinstance(parsed, dict) else None
                if not isinstance(clusters_raw, list):
                    fallback_cluster = [idx + batch_offset for idx in range(len(batch_descriptions))]
                    all_clusters.append(fallback_cluster)
                    all_details.append({
                        "description": "Fallback cluster (invalid response)",
                        "members": fallback_cluster
                    })
                    continue
                
                # Process clusters
                assigned = set()
                for cluster_info in clusters_raw:
                    if not isinstance(cluster_info, dict):
                        continue
                    
                    members_raw = cluster_info.get("members")
                    if not isinstance(members_raw, list):
                        continue
                    
                    cluster_members = []
                    for member in members_raw:
                        try:
                            member_idx = int(member) - 1  # 1-based to 0-based
                        except (TypeError, ValueError):
                            continue
                        if 0 <= member_idx < len(batch_descriptions):
                            adjusted_idx = member_idx + batch_offset
                            cluster_members.append(adjusted_idx)
                            assigned.add(member_idx)
                    
                    if cluster_members:
                        all_clusters.append(cluster_members)
                        all_details.append({
                            "description": cluster_info.get("description", ""),
                            "llm_rationale": cluster_info.get("rationale", ""),
                            "members": cluster_members
                        })
                
                # Add unassigned as singletons
                for idx in range(len(batch_descriptions)):
                    if idx not in assigned:
                        adjusted_idx = idx + batch_offset
                        all_clusters.append([adjusted_idx])
                        all_details.append({
                            "description": f"Singleton cluster for item {adjusted_idx}",
                            "members": [adjusted_idx],
                            "rationale": ""
                        })
            
            # Two-step validation
            # Step 1: LLM self-validation (if enabled)
            candidates = community_data.get('candidates', [])
            all_clusters, all_details, _ = self._llm_validate_clustering(
                all_clusters, all_details, candidates, 
                head_text=f"Keywords in community {comm_idx}", 
                relation="keyword_membership", 
                index_offset=0
            )
            
            # Step 2: Rule-based validation
            all_clusters, all_details = self._validate_and_fix_clustering_inconsistencies(
                all_clusters, all_details, candidates, 0
            )

            community_data['initial_clusters'] = all_clusters
            community_data['llm_clustering_details'] = all_details
    
    def _apply_keyword_dedup_results(self, community_data: dict, keyword_mapping: dict,
                                     save_intermediate: bool, intermediate_results: dict):
        """
        Apply deduplication results for a community and merge keyword nodes.
        """
        entries = community_data['entries']
        initial_clusters = community_data.get('initial_clusters', [])
        semantic_results = community_data.get('semantic_results', {})
        community_id = community_data['community_id']
        head_text = community_data['head_text']
        
        processed_indices = set()
        duplicate_indices = set()
        
        # Initialize community result for intermediate results
        community_result = None
        if save_intermediate:
            community_result = {
                "community_id": community_id,
                "community_name": head_text,
                "relation": "keyword_of",
                "total_candidates": len(entries),
                "candidates": [
                    {
                        "index": e["index"],
                        "node_id": e["node_id"],
                        "description": e["description"],
                        "raw_name": e["raw_name"],
                        "source_entity_id": e.get("source_entity_id"),
                        "source_entity_name": e.get("source_entity_name")
                    }
                    for e in entries
                ],
                "head_contexts": community_data['head_context_lines'],
                "clustering": {
                    "method": community_data['config_params']['clustering_method'],
                    "threshold": community_data['config_params']['threshold'],
                    "clusters": []
                },
                "llm_groups": [],
                "final_merges": []
            }
            
            # Save clustering info
            for cluster_idx, cluster in enumerate(initial_clusters):
                cluster_info = {
                    "cluster_id": cluster_idx,
                    "size": len(cluster),
                    "member_indices": cluster,
                    "members": [
                        {
                            "index": idx,
                            "node_id": entries[idx]["node_id"],
                            "description": entries[idx]["description"]
                        }
                        for idx in cluster if 0 <= idx < len(entries)
                    ]
                }
                llm_clustering_details = community_data.get('llm_clustering_details')
                if llm_clustering_details and cluster_idx < len(llm_clustering_details):
                    detail = llm_clustering_details[cluster_idx]
                    cluster_info["llm_description"] = detail.get("description", "")
                    cluster_info["llm_rationale"] = detail.get("llm_rationale", "")
                community_result["clustering"]["clusters"].append(cluster_info)
        
        # Process each cluster
        for cluster_idx, cluster in enumerate(initial_clusters):
            cluster_indices = [idx for idx in cluster if idx not in processed_indices and idx not in duplicate_indices]
            if not cluster_indices:
                continue
            
            # Single-item clusters - no dedup needed
            if len(cluster_indices) == 1:
                processed_indices.add(cluster_indices[0])
                continue
            
            # Process semantic dedup results for this cluster
            batch_num = 0
            while True:
                key = (cluster_idx, batch_num)
                if key not in semantic_results:
                    break
                
                result = semantic_results[key]
                groups = result['groups']
                batch_indices = result['batch_indices']
                overflow_indices = result.get('overflow_indices', [])
                
                # Save LLM groups
                if save_intermediate:
                    llm_result = {
                        "cluster_id": cluster_idx,
                        "batch_indices": batch_indices,
                        "batch_size": len(batch_indices),
                        "groups": []
                    }
                    for group in groups:
                        group_info = {
                            "members": group.get("members", []),
                            "representative": group.get("representative"),
                            "rationale": group.get("rationale"),
                            "member_details": [
                                {
                                    "local_idx": m,
                                    "global_idx": batch_indices[m] if 0 <= m < len(batch_indices) else None,
                                    "description": entries[batch_indices[m]]["description"] if 0 <= m < len(batch_indices) else None
                                }
                                for m in group.get("members", [])
                                if 0 <= m < len(batch_indices)
                            ]
                        }
                        llm_result["groups"].append(group_info)
                    community_result["llm_groups"].append(llm_result)
                
                # Process groups
                if not groups:
                    # No grouping - keep all separate
                    for global_idx in batch_indices:
                        if global_idx not in processed_indices:
                            processed_indices.add(global_idx)
                else:
                    for group in groups:
                        rep_local = group.get("representative")
                        if rep_local is None or rep_local < 0 or rep_local >= len(batch_indices):
                            continue

                        rep_global = batch_indices[rep_local]
                        if rep_global in processed_indices:
                            continue

                        duplicates: list = []
                        for member_local in group.get("members", []):
                            if member_local < 0 or member_local >= len(batch_indices):
                                continue
                            member_global = batch_indices[member_local]
                            if member_global == rep_global or member_global in processed_indices:
                                continue
                            duplicates.append(entries[member_global])
                            duplicate_indices.add(member_global)

                        
                        # Save merge info
                        if save_intermediate and duplicates:
                            merge_info = {
                                "representative": {
                                    "index": rep_global,
                                    "node_id": entries[rep_global]["node_id"],
                                    "description": entries[rep_global]["description"]
                                },
                                "duplicates": [
                                    {
                                        "index": d.get("index"),
                                        "node_id": d["node_id"],
                                        "description": d["description"]
                                    }
                                    for d in duplicates
                                ],
                                "rationale": group.get("rationale")
                            }
                            community_result["final_merges"].append(merge_info)
                        
                        # Merge keyword nodes
                        if duplicates:

                            self._merge_keyword_nodes(
                                entries[rep_global],
                                duplicates,
                                group.get("rationale"),
                                keyword_mapping,
                            )

                        processed_indices.add(rep_global)
                        for duplicate_entry in duplicates:
                            duplicate_idx = duplicate_entry.get("index")
                            if duplicate_idx is not None:
                                processed_indices.add(duplicate_idx)
                
                # Handle overflow
                if batch_num == 0:
                    for global_idx in overflow_indices:
                        if global_idx not in processed_indices:
                            processed_indices.add(global_idx)
                
                batch_num += 1
        
        # Save results
        if save_intermediate and community_result:
            community_result["summary"] = {
                "total_candidates": len(entries),
                "total_clusters": len(initial_clusters),
                "single_item_clusters": sum(1 for c in initial_clusters if len(c) == 1),
                "multi_item_clusters": sum(1 for c in initial_clusters if len(c) > 1),
                "total_llm_calls": len(community_result["llm_groups"]),
                "total_merges": len(community_result["final_merges"]),
                "items_merged": sum(len(m["duplicates"]) for m in community_result["final_merges"])
            }
            intermediate_results["communities"].append(community_result)


    def _deduplicate_exact(self, edges: list) -> list:
        unique_edges = []
        seen = set()

        for tail_id, data in edges:
            try:
                frozen = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
            except Exception:
                frozen = str(data)

            key = (tail_id, frozen)
            if key in seen:
                continue

            seen.add(key)
            unique_edges.append((tail_id, copy.deepcopy(data)))

        return unique_edges

    def _semantic_deduplicate_group(self, head_id: str, relation: str, edges: list) -> list:
        config = self._get_semantic_dedup_config()
        if not config or len(edges) <= 1:
            return edges

        head_text = self._describe_node(head_id)
        entries = []
        for idx, (tail_id, data) in enumerate(edges):
            chunk_ids = self._extract_edge_chunk_ids(data)
            if not chunk_ids:
                chunk_ids = self._collect_node_chunk_ids(tail_id)
            entries.append(
                {
                    "index": idx,
                    "node_id": tail_id,
                    "data": copy.deepcopy(data),
                    "raw_data": copy.deepcopy(data),
                    "description": self._describe_node(tail_id),
                    "description_for_clustering": self._describe_node_for_clustering(tail_id),  # Simplified for clustering
                    "context_chunk_ids": chunk_ids,
                    "context_summaries": self._summarize_contexts(chunk_ids),
                }
            )

        head_chunk_ids = set()
        for entry in entries:
            for chunk_id in entry.get("context_chunk_ids", []):
                if chunk_id:
                    head_chunk_ids.add(chunk_id)

        if not head_chunk_ids:
            for chunk_id in self._collect_node_chunk_ids(head_id):
                if chunk_id:
                    head_chunk_ids.add(chunk_id)

        head_context_lines = self._summarize_contexts(list(head_chunk_ids))

        clustering_method = getattr(config, "clustering_method", "embedding")

        threshold = getattr(config, "embedding_threshold", 0.85) or 0.85
        llm_clustering_batch_size = getattr(config, "llm_clustering_batch_size", 50)

        max_batch_size = max(1, int(getattr(config, "max_batch_size", 8) or 8))
        max_candidates = int(getattr(config, "max_candidates", 0) or 0)

        # candidate_descriptions_ = [entry["description"] for entry in entries]
        
        candidate_descriptions = [entry["description_for_clustering"] for entry in entries]

        # ============================================================
        # PHASE 1: Collect all prompts (clustering + semantic grouping)
        # ============================================================
        prompts_to_process = []
        
        # 1.1: Collect clustering prompts (if using LLM clustering)
        clustering_prompt_indices = []  # Track which prompts are for clustering
        initial_clusters = None

        # import pdb; pdb.set_trace()
        # initial_clusters = self._cluster_candidate_tails(candidate_descriptions, threshold)

        llm_clustering_details = None

        if clustering_method == "llm":
            # Use LLM for initial clustering (more accurate but slower)
            # logger.debug("Using LLM-based clustering for head '%s' relation '%s' with %d tails", head_text, relation, len(entries))
            # initial_clusters, llm_clustering_details = self._cluster_candidate_tails_with_llm(head_text, relation, candidate_descriptions, llm_clustering_batch_size)
            logger.debug("Collecting LLM clustering prompts for head '%s' relation '%s' with %d tails", 
                        head_text, relation, len(entries))
            
            # Build clustering prompts (may be batched)
            descriptions = candidate_descriptions
            if len(descriptions) > llm_clustering_batch_size:
                # Need multiple batches for clustering
                for batch_start in range(0, len(descriptions), llm_clustering_batch_size):
                    batch_end = min(batch_start + llm_clustering_batch_size, len(descriptions))
                    batch_descriptions = descriptions[batch_start:batch_end]
                    batch_offset = batch_start
                    
                    # Build clustering prompt
                    candidate_blocks = []
                    for idx, description in enumerate(batch_descriptions, start=1):
                        candidate_blocks.append(f"[{idx}] {description}")
                    candidates_text = "\n".join(candidate_blocks) if candidate_blocks else "[No candidates]"
                    
                    prompt = DEFAULT_LLM_CLUSTERING_PROMPT.format(
                        head=head_text or "[UNKNOWN_HEAD]",
                        relation=relation or "[UNKNOWN_RELATION]",
                        candidates=candidates_text
                    )
                    
                    clustering_prompt_idx = len(prompts_to_process)
                    clustering_prompt_indices.append(clustering_prompt_idx)
                    prompts_to_process.append({
                        'type': 'clustering',
                        'prompt': prompt,
                        'metadata': {
                            'batch_start': batch_start,
                            'batch_end': batch_end,
                            'batch_offset': batch_offset,
                            'descriptions': batch_descriptions
                        }
                    })
            else:
                # Single batch for clustering
                candidate_blocks = []
                for idx, description in enumerate(descriptions, start=1):
                    candidate_blocks.append(f"[{idx}] {description}")
                candidates_text = "\n".join(candidate_blocks) if candidate_blocks else "[No candidates]"
                
                prompt = DEFAULT_LLM_CLUSTERING_PROMPT.format(
                    head=head_text or "[UNKNOWN_HEAD]",
                    relation=relation or "[UNKNOWN_RELATION]",
                    candidates=candidates_text
                )
                
                clustering_prompt_idx = len(prompts_to_process)
                clustering_prompt_indices.append(clustering_prompt_idx)
                prompts_to_process.append({
                    'type': 'clustering',
                    'prompt': prompt,
                    'metadata': {
                        'batch_start': 0,
                        'batch_end': len(descriptions),
                        'batch_offset': 0,
                        'descriptions': descriptions
                    }
                })

        else:
            # Use embedding-based clustering (faster but less accurate)
            initial_clusters = self._cluster_candidate_tails(candidate_descriptions, threshold)
                # 1.2: Collect semantic grouping prompts (prepare for each cluster batch)
        # We need to predict which batches will be processed for semantic grouping
        # For now, we'll collect prompts after getting clustering results
        # So this phase is split into two sub-phases
        
        # ============================================================
        # PHASE 2A: Process clustering prompts (if any)
        # ============================================================
        if clustering_method == "llm" and prompts_to_process:
            logger.debug("Processing %d clustering prompt(s) concurrently", len(prompts_to_process))
            clustering_results = self._concurrent_llm_calls(prompts_to_process, type="clustering")
            
            # Parse clustering results
            all_clusters = []
            all_details = []
            
            for result in clustering_results:
                if result['error']:
                    # Fallback for failed clustering
                    metadata = result['metadata']
                    batch_descriptions = metadata['descriptions']
                    batch_offset = metadata['batch_offset']
                    fallback_cluster = [[idx + batch_offset for idx in range(len(batch_descriptions))]]
                    fallback_details = [{"description": f"Fallback cluster (LLM call failed: {result['error']})", 
                                       "members": fallback_cluster[0]}]
                    all_clusters.extend(fallback_cluster)
                    all_details.extend(fallback_details)
                    continue
                
                # Parse clustering response
                response = result['response']
                metadata = result['metadata']
                batch_offset = metadata['batch_offset']
                batch_descriptions = metadata['descriptions']
                
                try:
                    parsed = json_repair.loads(response)
                except Exception:
                    try:
                        parsed = json.loads(response)
                    except Exception as parse_error:
                        logger.warning("Failed to parse LLM clustering response: %s: %s, using fallback", 
                                     type(parse_error).__name__, parse_error)
                        fallback_cluster = [[idx + batch_offset for idx in range(len(batch_descriptions))]]
                        fallback_details = [{"description": "Fallback cluster (parse failed)", 
                                           "members": fallback_cluster[0]}]
                        all_clusters.extend(fallback_cluster)
                        all_details.extend(fallback_details)
                        continue
                
                clusters_raw = parsed.get("clusters") if isinstance(parsed, dict) else None
                if not isinstance(clusters_raw, list):
                    logger.warning("LLM clustering response missing 'clusters' field, using fallback")
                    fallback_cluster = [[idx + batch_offset for idx in range(len(batch_descriptions))]]
                    fallback_details = [{"description": "Fallback cluster (invalid response)", 
                                       "members": fallback_cluster[0]}]
                    all_clusters.extend(fallback_cluster)
                    all_details.extend(fallback_details)
                    continue
                
                # Convert LLM output to cluster format
                assigned = set()
                for cluster_idx, cluster_info in enumerate(clusters_raw):
                    if not isinstance(cluster_info, dict):
                        continue
                    
                    members_raw = cluster_info.get("members")
                    if not isinstance(members_raw, list):
                        continue
                    
                    cluster_members = []
                    for member in members_raw:
                        try:
                            member_idx = int(member) - 1  # Convert to 0-based
                        except (TypeError, ValueError):
                            continue
                        if 0 <= member_idx < len(batch_descriptions):
                            adjusted_idx = member_idx + batch_offset
                            cluster_members.append(adjusted_idx)
                            assigned.add(member_idx)
                    
                    if cluster_members:
                        all_clusters.append(cluster_members)
                        detail = {
                            "description": cluster_info.get("description", ""),
                            "llm_rationale": cluster_info.get("rationale", ""),
                            "rationale": cluster_info.get("rationale", ""),
                            "members": cluster_members
                        }
                        all_details.append(detail)
                
                # Add unassigned items as singleton clusters
                for idx in range(len(batch_descriptions)):
                    if idx not in assigned:
                        adjusted_idx = idx + batch_offset
                        all_clusters.append([adjusted_idx])
                        all_details.append({
                            "description": f"Singleton cluster for item {adjusted_idx}",
                            "members": [adjusted_idx],
                            "rationale": ""
                        })
            
            # Two-step validation
            # Step 1: LLM self-validation (if enabled)
            all_clusters, all_details, _ = self._llm_validate_clustering(
                all_clusters, all_details, candidate_descriptions,
                head_text=head_text, relation=relation, index_offset=0
            )
            
            # Step 2: Rule-based validation
            all_clusters, all_details = self._validate_and_fix_clustering_inconsistencies(
                all_clusters, all_details, candidate_descriptions, 0
            )

            initial_clusters = all_clusters
            llm_clustering_details = all_details
        
        # ============================================================
        # PHASE 2B: Collect semantic grouping prompts based on clusters
        # ============================================================
        semantic_prompts = []
        semantic_prompt_metadata = []  # Store metadata for each semantic prompt
        
        for cluster_idx, cluster in enumerate(initial_clusters):
            cluster_indices = cluster.copy()
            
            # Skip single-item clusters (no grouping needed)
            if len(cluster_indices) <= 1:
                continue
            
            # Apply max_candidates limit
            overflow_indices = []
            if max_candidates and len(cluster_indices) > max_candidates:
                overflow_indices = cluster_indices[max_candidates:]
                cluster_indices = cluster_indices[:max_candidates]
            
            # Batch the cluster into semantic grouping batches
            while cluster_indices:
                batch_indices = cluster_indices[:max_batch_size]
                batch_entries = [entries[i] for i in batch_indices]
                
                # Build semantic grouping prompt
                prompt = self._build_semantic_dedup_prompt(head_text, relation, head_context_lines, batch_entries)
                
                semantic_prompts.append({
                    'type': 'semantic',
                    'prompt': prompt,
                    'metadata': {
                        'cluster_idx': cluster_idx,
                        'batch_indices': batch_indices,
                        'overflow_indices': overflow_indices,
                        'original_cluster': cluster
                    }
                })
                
                cluster_indices = cluster_indices[len(batch_indices):]
        
        # ============================================================
        # PHASE 3: Process all semantic grouping prompts concurrently
        # ============================================================
        semantic_results = []
        if semantic_prompts:
            logger.debug("Processing %d semantic grouping prompt(s) concurrently", len(semantic_prompts))
            semantic_results = self._concurrent_llm_calls(semantic_prompts, type="tail_dedup")
        
        # Parse semantic grouping results
        semantic_groups_by_batch = []
        for result in semantic_results:
            metadata = result['metadata']
            batch_indices = metadata['batch_indices']
            batch_entries = [entries[i] for i in batch_indices]
            
            if result['error']:
                # Fallback: no grouping
                logger.warning("Semantic grouping LLM call failed for batch: %s", result['error'])
                semantic_groups_by_batch.append({
                    'groups': [],
                    'metadata': metadata
                })
                continue
            
            # Parse semantic grouping response
            response = result['response']
            try:
                parsed = json_repair.loads(response)
            except Exception:
                try:
                    parsed = json.loads(response)
                except Exception as parse_error:
                    logger.warning("Failed to parse semantic dedup LLM response: %s: %s", 
                                 type(parse_error).__name__, parse_error)
                    semantic_groups_by_batch.append({
                        'groups': [],
                        'metadata': metadata
                    })
                    continue
            
            groups_raw = parsed.get("groups") if isinstance(parsed, dict) else None
            if not isinstance(groups_raw, list):
                semantic_groups_by_batch.append({
                    'groups': [],
                    'metadata': metadata
                })
                continue
            
            # Convert to group format
            groups = []
            assigned = set()
            for group in groups_raw:
                if not isinstance(group, dict):
                    continue
                
                members_raw = group.get("members")
                if not isinstance(members_raw, list):
                    continue
                
                normalized_members = []
                for member in members_raw:
                    try:
                        member_idx = int(member) - 1
                    except (TypeError, ValueError):
                        continue
                    if 0 <= member_idx < len(batch_entries):
                        normalized_members.append(member_idx)
                
                if not normalized_members:
                    continue
                
                rep_raw = group.get("representative")
                try:
                    rep_idx = int(rep_raw) - 1 if rep_raw is not None else None
                except (TypeError, ValueError):
                    rep_idx = None
                
                if rep_idx is None or rep_idx not in normalized_members:
                    rep_idx = normalized_members[0]
                
                rationale = group.get("rationale")
                groups.append({
                    "representative": rep_idx,
                    "members": normalized_members,
                    "rationale": rationale,
                })
                assigned.update(normalized_members)
            
            # Add unassigned items as singleton groups
            for idx in range(len(batch_entries)):
                if idx not in assigned:
                    groups.append({"representative": idx, "members": [idx], "rationale": None})
            
            # ============================================================
            # Two-step validation: Validate semantic dedup results
            # ============================================================
            # Extract candidate descriptions for this batch
            candidate_descriptions = [entry['description'] for entry in batch_entries]
            
            # Validate groups for consistency (rationale vs members)
            groups, validation_report = self._llm_validate_semantic_dedup(
                groups,
                candidate_descriptions,
                head_text=head_text,
                relation=relation
            )

            semantic_groups_by_batch.append({
                'groups': groups,  # Use validated groups
                'metadata': metadata,
                'validation_report': validation_report  # Store validation report
            })
        
        # ============================================================
        # PHASE 4: Process results and build final edges
        # ============================================================
        

        #import pdb; pdb.set_trace()
        max_batch_size = max(1, int(getattr(config, "max_batch_size", 8) or 8))
        max_candidates = int(getattr(config, "max_candidates", 0) or 0)

        # Initialize intermediate results collector for edge deduplication
        save_intermediate = getattr(config, "save_intermediate_results", False)
        edge_dedup_result = {
            "head_id": head_id,
            "head_name": head_text,
            "relation": relation,
            "total_edges": len(edges),
            "candidates": [],
            "clustering": {
                "threshold": threshold,
                "clusters": []
            },
            "llm_groups": [],
            "final_merges": []
        } if save_intermediate else None
        
        # Save candidates info
        if save_intermediate:
            edge_dedup_result["head_contexts"] = head_context_lines
            for entry in entries:
                edge_dedup_result["candidates"].append({
                    "index": entry["index"],
                    "node_id": entry["node_id"],
                    "description": entry["description"]
                })

        # Save clustering results
        if save_intermediate:
            # Add clustering method info
            edge_dedup_result["clustering"]["method"] = clustering_method

            for cluster_idx, cluster in enumerate(initial_clusters):
                cluster_info = {
                    "cluster_id": cluster_idx,
                    "size": len(cluster),
                    "member_indices": cluster,
                    "members": [
                        {
                            "index": idx,
                            "node_id": entries[idx]["node_id"],
                            "description": entries[idx]["description"]
                        }
                        for idx in cluster if 0 <= idx < len(entries)
                    ]
                }

                # Add LLM clustering details if available
                if llm_clustering_details and cluster_idx < len(llm_clustering_details):
                    detail = llm_clustering_details[cluster_idx]
                    cluster_info["llm_description"] = detail.get("description", "")
                    cluster_info["llm_rationale"] = detail.get("llm_rationale", "")


                edge_dedup_result["clustering"]["clusters"].append(cluster_info)

        final_edges: list = []

        save_intermediate = getattr(config, "save_intermediate_results", False)

        processed_indices: set = set()
        duplicate_indices: set = set()

        
        # Create a mapping from cluster_idx to semantic results
        semantic_results_map = {}
        for batch_result in semantic_groups_by_batch:
            metadata = batch_result['metadata']
            cluster_idx = metadata['cluster_idx']
            if cluster_idx not in semantic_results_map:
                semantic_results_map[cluster_idx] = []
            semantic_results_map[cluster_idx].append(batch_result)
        
        # Process each cluster
        for cluster_idx, cluster in enumerate(initial_clusters):
            cluster_indices = [idx for idx in cluster if idx not in processed_indices and idx not in duplicate_indices]
            if not cluster_indices:
                continue

            if len(cluster_indices) == 1:
                idx = cluster_indices[0]
                entry = entries[idx]
                final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
                processed_indices.add(idx)
                continue

            # overflow_indices = []
            # if max_candidates and len(cluster_indices) > max_candidates:
            #     overflow_indices = cluster_indices[max_candidates:]
            #     cluster_indices = cluster_indices[:max_candidates]
            #     logger.debug(
            #         "Semantic dedup limited LLM candidates for head '%s' relation '%s' to %d of %d items",
            #         head_text,
            #         relation,
            #         max_candidates,
            #         len(cluster),
            #     )

            # # import pdb; pdb.set_trace()
            # while cluster_indices:
            #     batch_indices = cluster_indices[:max_batch_size]
            #     batch_entries = [entries[i] for i in batch_indices]
            #     groups = self._llm_semantic_group(head_text, relation, head_context_lines, batch_entries)

            # Get semantic grouping results for this cluster
            cluster_semantic_results = semantic_results_map.get(cluster_idx, [])
            
            # Process each batch result for this cluster
            for batch_result in cluster_semantic_results:
                groups = batch_result['groups']
                metadata = batch_result['metadata']
                batch_indices = metadata['batch_indices']
                overflow_indices = metadata.get('overflow_indices', [])

                # import pdb; pdb.set_trace()
                # Save LLM groups result
                if save_intermediate:
                    llm_result = {
                        "cluster_id": cluster_idx, #initial_clusters.index([idx for idx in cluster if idx not in processed_indices and idx not in duplicate_indices][:len(cluster_indices)]) if cluster_indices else -1,
                        "batch_indices": batch_indices,
                        "batch_size": len(batch_indices),
                        "groups": []
                    }
                    if groups:
                        for group in groups:
                            group_info = {
                                "members": group.get("members", []),
                                "representative": group.get("representative"),
                                "rationale": group.get("rationale"),
                                "member_details": [
                                    {
                                        "local_idx": m,
                                        "global_idx": batch_indices[m] if 0 <= m < len(batch_indices) else None,
                                        "description": entries[batch_indices[m]]["description"] if 0 <= m < len(batch_indices) else None
                                    }
                                    for m in group.get("members", [])
                                    if 0 <= m < len(batch_indices)
                                ]
                            }
                            llm_result["groups"].append(group_info)
                    edge_dedup_result["llm_groups"].append(llm_result)

                if not groups:
                    for global_idx in batch_indices:
                        if global_idx not in processed_indices:
                            entry = entries[global_idx]
                            final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
                            processed_indices.add(global_idx)
                else:
                    # Process each group
                    for group in groups:
                        rep_local = group.get("representative")
                        if rep_local is None or rep_local < 0 or rep_local >= len(batch_indices):
                            continue
                        
                        rep_global = batch_indices[rep_local]
                        if rep_global in processed_indices:
                            continue
                        
                        # Collect duplicates
                        duplicates = []
                        for member_local in group.get("members", []):
                            if member_local < 0 or member_local >= len(batch_indices):
                                continue
                            member_global = batch_indices[member_local]
                            if member_global == rep_global or member_global in processed_indices:
                                continue
                            duplicates.append(entries[member_global])
                            duplicate_indices.add(member_global)
                        
                        # Save merge operation
                        if save_intermediate and duplicates:
                            merge_info = {
                                "representative": {
                                    "index": rep_global,
                                    "node_id": entries[rep_global]["node_id"],
                                    "description": entries[rep_global]["description"]
                                },
                                "duplicates": [
                                    {
                                        "index": d.get("index"),
                                        "node_id": d["node_id"],
                                        "description": d["description"]
                                    }
                                    for d in duplicates
                                ],
                                "rationale": group.get("rationale")
                            }
                            edge_dedup_result["final_merges"].append(merge_info)
                        
                        # Merge metadata and add to final edges
                        merged_data = self._merge_duplicate_metadata(
                            entries[rep_global],
                            duplicates,
                            group.get("rationale"),
                        )
                        
                        final_edges.append((entries[rep_global]["node_id"], merged_data))
                        processed_indices.add(rep_global)
                
                # Process overflow indices (items that exceeded max_candidates)
                for global_idx in overflow_indices:
                    if global_idx not in processed_indices:
                        entry = entries[global_idx]
                        final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
                        processed_indices.add(global_idx)

        for entry in entries:
            idx = entry["index"]
            if idx in processed_indices or idx in duplicate_indices:
                continue
            final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
            processed_indices.add(idx)

        # Save edge dedup result with summary
        if save_intermediate:
            edge_dedup_result["summary"] = {
                "total_edges": len(edges),
                "total_clusters": len(initial_clusters),
                "single_item_clusters": sum(1 for c in initial_clusters if len(c) == 1),
                "multi_item_clusters": sum(1 for c in initial_clusters if len(c) > 1),
                "total_llm_calls": len(edge_dedup_result["llm_groups"]),
                "total_merges": len(edge_dedup_result["final_merges"]),
                "edges_merged": sum(len(m["duplicates"]) for m in edge_dedup_result["final_merges"]),
                "final_edges": len(final_edges)
            }
            
            # Accumulate to class-level collector
            if not hasattr(self, '_edge_dedup_results'):
                self._edge_dedup_results = []
            self._edge_dedup_results.append(edge_dedup_result)


        return final_edges

    def _prepare_dedup_group(self, head_id: str, relation: str, edges: list, config) -> dict:
        """
        Prepare metadata for a deduplication group.
        
        Returns:
            dict with keys: head_id, head_text, relation, edges, entries, 
                           head_context_lines, candidate_descriptions, config_params
        """
        head_text = self._describe_node(head_id)
        entries = []
        
        for idx, (tail_id, data) in enumerate(edges):
            chunk_ids = self._extract_edge_chunk_ids(data)
            if not chunk_ids:
                chunk_ids = self._collect_node_chunk_ids(tail_id)
            entries.append({
                "index": idx,
                "node_id": tail_id,
                "data": copy.deepcopy(data),
                "raw_data": copy.deepcopy(data),
                "description": self._describe_node(tail_id),
                "description_for_clustering": self._describe_node_for_clustering(tail_id),
                "context_chunk_ids": chunk_ids,
                "context_summaries": self._summarize_contexts(chunk_ids),
            })
        #import pdb; pdb.set_trace()
        # Collect head context
        head_chunk_ids = set()
        for entry in entries:
            for chunk_id in entry.get("context_chunk_ids", []):
                if chunk_id:
                    head_chunk_ids.add(chunk_id)
        
        if not head_chunk_ids:
            for chunk_id in self._collect_node_chunk_ids(head_id):
                if chunk_id:
                    head_chunk_ids.add(chunk_id)
        
        head_context_lines = self._summarize_contexts(list(head_chunk_ids))
        candidate_descriptions = [entry["description_for_clustering"] for entry in entries]
        
        # Extract config parameters
        config_params = {
            'clustering_method': getattr(config, "clustering_method", "embedding"),
            'threshold': getattr(config, "embedding_threshold", 0.85) or 0.85,
            'llm_clustering_batch_size': getattr(config, "llm_clustering_batch_size", 50),
            'max_batch_size': max(1, int(getattr(config, "max_batch_size", 5) or 5)),
            'max_candidates': int(getattr(config, "max_candidates", 0) or 0),
        }
        
        return {
            'head_id': head_id,
            'head_text': head_text,
            'relation': relation,
            'edges': edges,
            'entries': entries,
            'head_context_lines': head_context_lines,
            'candidate_descriptions': candidate_descriptions,
            'config_params': config_params,
            'initial_clusters': None,  # Will be filled by clustering
            'llm_clustering_details': None,  # Will be filled by LLM clustering
            'semantic_results': {},  # Will be filled by semantic dedup
            'only_head_context': self._summarize_contexts(list(self._collect_node_chunk_ids(head_id)))
        }
    
    def _collect_clustering_prompts(self, group_data: dict) -> list:
        """
        Collect all clustering prompts for a deduplication group.
        
        Returns:
            List of prompt dicts with keys: type, prompt, metadata
        """
        prompts = []
        head_text = group_data['head_text']
        relation = group_data['relation']
        descriptions = group_data['candidate_descriptions']
        llm_clustering_batch_size = group_data['config_params']['llm_clustering_batch_size']
        
        if len(descriptions) > llm_clustering_batch_size:
            # Multiple batches needed
            for batch_start in range(0, len(descriptions), llm_clustering_batch_size):
                batch_end = min(batch_start + llm_clustering_batch_size, len(descriptions))
                batch_descriptions = descriptions[batch_start:batch_end]
                
                candidate_blocks = [f"[{i+1}] {desc}" for i, desc in enumerate(batch_descriptions)]
                candidates_text = "\n".join(candidate_blocks) if candidate_blocks else "[No candidates]"
                
                prompt = DEFAULT_LLM_CLUSTERING_PROMPT.format(
                    head=head_text or "[UNKNOWN_HEAD]",
                    relation=relation or "[UNKNOWN_RELATION]",
                    candidates=candidates_text
                )
                
                prompts.append({
                    'type': 'clustering',
                    'prompt': prompt,
                    'metadata': {
                        'batch_start': batch_start,
                        'batch_end': batch_end,
                        'batch_offset': batch_start,
                        'descriptions': batch_descriptions,
                    }
                })
        else:
            # Single batch
            candidate_blocks = [f"[{i+1}] {desc}" for i, desc in enumerate(descriptions)]
            candidates_text = "\n".join(candidate_blocks) if candidate_blocks else "[No candidates]"
            
            prompt = DEFAULT_LLM_CLUSTERING_PROMPT.format(
                head=head_text or "[UNKNOWN_HEAD]",
                relation=relation or "[UNKNOWN_RELATION]",
                candidates=candidates_text
            )
            
            prompts.append({
                'type': 'clustering',
                'prompt': prompt,
                'metadata': {
                    'batch_start': 0,
                    'batch_end': len(descriptions),
                    'batch_offset': 0,
                    'descriptions': descriptions,
                }
            })
        
        return prompts
    
    def _parse_clustering_results(self, dedup_groups: list, clustering_results: list):
        """
        Parse clustering results and update dedup_groups with initial_clusters.
        """
        # Group results by group_idx
        #import pdb; pdb.set_trace()
        results_by_group = defaultdict(list)
        for result in clustering_results:
            group_idx = result['metadata'].get('group_idx')
            if group_idx is not None:
                results_by_group[group_idx].append(result)
        
        # Parse results for each group
        for group_idx, results in results_by_group.items():
            if group_idx >= len(dedup_groups):
                continue
            
            group_data = dedup_groups[group_idx]
            all_clusters = []
            all_details = []
            
            for result in results:
                metadata = result['metadata']
                batch_offset = metadata['batch_offset']
                batch_descriptions = metadata['descriptions']
                
                if result['error']:
                    # Fallback: single cluster
                    fallback_cluster = [idx + batch_offset for idx in range(len(batch_descriptions))]
                    all_clusters.append(fallback_cluster)
                    all_details.append({
                        "description": f"Fallback cluster (error: {result['error']})",
                        "members": fallback_cluster
                    })
                    continue
                
                # Parse clustering response
                try:
                    parsed = json_repair.loads(result['response'])
                except Exception:
                    try:
                        parsed = json.loads(result['response'])
                    except Exception:
                        # Fallback
                        fallback_cluster = [idx + batch_offset for idx in range(len(batch_descriptions))]
                        all_clusters.append(fallback_cluster)
                        all_details.append({
                            "description": "Fallback cluster (parse failed)",
                            "members": fallback_cluster
                        })
                        continue
                
                clusters_raw = parsed.get("clusters") if isinstance(parsed, dict) else None
                if not isinstance(clusters_raw, list):
                    fallback_cluster = [idx + batch_offset for idx in range(len(batch_descriptions))]
                    all_clusters.append(fallback_cluster)
                    all_details.append({
                        "description": "Fallback cluster (invalid response)",
                        "members": fallback_cluster
                    })
                    continue
                
                # Process clusters
                assigned = set()
                for cluster_info in clusters_raw:
                    if not isinstance(cluster_info, dict):
                        continue
                    
                    members_raw = cluster_info.get("members")
                    if not isinstance(members_raw, list):
                        continue
                    
                    cluster_members = []
                    for member in members_raw:
                        try:
                            member_idx = int(member) - 1  # 1-based to 0-based
                        except (TypeError, ValueError):
                            continue
                        if 0 <= member_idx < len(batch_descriptions):
                            adjusted_idx = member_idx + batch_offset
                            cluster_members.append(adjusted_idx)
                            assigned.add(member_idx)
                    
                    if cluster_members:
                        all_clusters.append(cluster_members)
                        all_details.append({
                            "description": cluster_info.get("description", ""),
                            "llm_rationale": cluster_info.get("rationale", ""),
                            "members": cluster_members
                        })
                
                # Add unassigned as singletons
                for idx in range(len(batch_descriptions)):
                    if idx not in assigned:
                        adjusted_idx = idx + batch_offset
                        all_clusters.append([adjusted_idx])
                        all_details.append({
                            "description": f"Singleton cluster for item {adjusted_idx}",
                            "members": [adjusted_idx],
                            "rationale": ""                            
                        })
            #import pdb; pdb.set_trace()
            # Two-step validation
            # Step 1: LLM self-validation (if enabled)
            candidate_descriptions = group_data.get('candidate_descriptions', [])
            head_text = group_data.get('head_text', 'Unknown')
            relation = group_data.get('relation', 'Unknown')
            all_clusters, all_details, _ = self._llm_validate_clustering(
                all_clusters, all_details, candidate_descriptions,
                head_text=head_text, relation=relation, index_offset=0
            )
            
            # Step 2: Rule-based validation
            all_clusters, all_details = self._validate_and_fix_clustering_inconsistencies(
                all_clusters, all_details, candidate_descriptions, 0
            )

            group_data['initial_clusters'] = all_clusters
            group_data['llm_clustering_details'] = all_details
    
    def _apply_embedding_clustering(self, group_data: dict):
        """Apply embedding-based clustering to a group."""
        threshold = group_data['config_params']['threshold']
        candidate_descriptions = group_data['candidate_descriptions']
        initial_clusters = self._cluster_candidate_tails(candidate_descriptions, threshold)
        group_data['initial_clusters'] = initial_clusters
    
    def _collect_semantic_dedup_prompts(self, group_data: dict) -> list:
        """
        Collect all semantic dedup prompts for a deduplication group.
        
        Returns:
            List of prompt dicts with keys: type, prompt, metadata
        """
        prompts = []
        initial_clusters = group_data.get('initial_clusters', [])
        if not initial_clusters:
            return prompts
        
        head_text = group_data['head_text']
        relation = group_data['relation']
        head_context_lines = group_data['head_context_lines']
        entries = group_data['entries']
        max_batch_size = group_data['config_params']['max_batch_size']
        max_candidates = group_data['config_params']['max_candidates']
        only_head_context = group_data['only_head_context']
        
        
        for cluster_idx, cluster in enumerate(initial_clusters):
            cluster_indices = cluster.copy()
            
            # Skip single-item clusters
            if len(cluster_indices) <= 1:
                continue
            
            # Apply max_candidates limit
            overflow_indices = []
            if max_candidates and len(cluster_indices) > max_candidates:
                overflow_indices = cluster_indices[max_candidates:]
                cluster_indices = cluster_indices[:max_candidates]
            
            # Batch the cluster
            batch_num = 0
            while cluster_indices:
                batch_indices = cluster_indices[:max_batch_size]
                batch_entries = [entries[i] for i in batch_indices]

                
                # Build prompt
                prompt = self._build_semantic_dedup_prompt(
                    head_text, relation, head_context_lines, batch_entries, only_head_context
                )
                
                prompts.append({
                    'type': 'semantic',
                    'prompt': prompt,
                    'metadata': {
                        'cluster_idx': cluster_idx,
                        'batch_num': batch_num,
                        'batch_indices': batch_indices,
                        'overflow_indices': overflow_indices if batch_num == 0 else [],
                    }
                })
                
                cluster_indices = cluster_indices[len(batch_indices):]
                batch_num += 1
        
        #import ipdb; ipdb.set_trace()
        
        return prompts
    
    def _parse_semantic_dedup_results(self, dedup_groups: list, semantic_results: list):
        """
        Parse semantic dedup results and update dedup_groups.
        """
        # Group results by group_idx
        results_by_group = defaultdict(list)
        for result in semantic_results:
            group_idx = result['metadata'].get('group_idx')
            if group_idx is not None:
                results_by_group[group_idx].append(result)
        
        #import pdb; pdb.set_trace()
        # Parse results for each group
        for group_idx, results in tqdm(results_by_group.items()):
            # if group_idx !=16:
            #     continue

            if group_idx >= len(dedup_groups):
                continue
            
            group_data = dedup_groups[group_idx]
            entries = group_data['entries']
            
            # Store parsed groups by (cluster_idx, batch_num)
            semantic_groups = {}
            
            for idx, result in enumerate(results):
                # if idx == 0:
                #     import pdb; pdb.set_trace()
                metadata = result['metadata']
                cluster_idx = metadata['cluster_idx']
                batch_num = metadata['batch_num']
                batch_indices = metadata['batch_indices']
                overflow_indices = metadata.get('overflow_indices', [])
                
                key = (cluster_idx, batch_num)
                
                if result['error']:
                    # No grouping
                    semantic_groups[key] = {
                        'groups': [],
                        'batch_indices': batch_indices,
                        'overflow_indices': overflow_indices,
                    }
                    continue
                
                # Parse response
                try:
                    parsed = json_repair.loads(result['response'])
                except Exception:
                    try:
                        parsed = json.loads(result['response'])
                    except Exception:
                        semantic_groups[key] = {
                            'groups': [],
                            'batch_indices': batch_indices,
                            'overflow_indices': overflow_indices,
                        }
                        continue
                
                groups_raw = parsed.get("groups") if isinstance(parsed, dict) else None
                if not isinstance(groups_raw, list):
                    semantic_groups[key] = {
                        'groups': [],
                        'batch_indices': batch_indices,
                        'overflow_indices': overflow_indices,
                    }
                    continue
                
                # Parse groups
                groups = []
                assigned = set()
                for group in groups_raw:
                    if not isinstance(group, dict):
                        continue
                    
                    members_raw = group.get("members")
                    if not isinstance(members_raw, list):
                        continue
                    
                    normalized_members = []
                    for member in members_raw:
                        try:
                            member_idx = int(member) - 1
                        except (TypeError, ValueError):
                            continue
                        if 0 <= member_idx < len(batch_indices):
                            normalized_members.append(member_idx)
                    
                    if not normalized_members:
                        continue
                    
                    rep_raw = group.get("representative")
                    try:
                        rep_idx = int(rep_raw) - 1 if rep_raw is not None else None
                    except (TypeError, ValueError):
                        rep_idx = None
                    
                    if rep_idx is None or rep_idx not in normalized_members:
                        rep_idx = normalized_members[0]
                    
                    groups.append({
                        "representative": rep_idx,
                        "members": normalized_members,
                        "rationale": group.get("rationale"),
                    })
                    assigned.update(normalized_members)
                
                # Add unassigned as singletons
                for idx in range(len(batch_indices)):
                    if idx not in assigned:
                        groups.append({
                            "representative": idx,
                            "members": [idx],
                            "rationale": None
                        })
                
                # ============================================================
                # Two-step validation: Validate semantic dedup results
                # ============================================================
                # Extract candidate descriptions for this batch
                try:
                    batch_entries = [entries[i] for i in batch_indices]
                    candidate_descriptions = [entry['description'] for entry in batch_entries]
                except Exception:
                    #import ipdb; ipdb.set_trace()
                    raise Exception("Error parsing semantic dedup results")
                
                # Get head and relation info from group_data
                head_text = group_data.get('head_name', '')
                relation = group_data.get('relation', '')
                
                # import pdb; pdb.set_trace()
                # print()
                # Validate groups for consistency (rationale vs members)
                groups, validation_report = self._llm_validate_semantic_dedup(
                    groups,
                    candidate_descriptions,
                    head_text=head_text,
                    relation=relation
                )

                semantic_groups[key] = {
                    'groups': groups,
                    'batch_indices': batch_indices,
                    'overflow_indices': overflow_indices,
                    'validation_report': validation_report  # Store validation report
                }
            
            group_data['semantic_results'] = semantic_groups
    
    def _build_final_edges(self, group_data: dict, save_intermediate: bool) -> list:
        """
        Build final deduplicated edges from parsed results.
        
        Returns:
            List of (tail_id, edge_data) tuples
        """
        entries = group_data['entries']
        initial_clusters = group_data.get('initial_clusters', [])
        semantic_results = group_data.get('semantic_results', {})
        
        final_edges = []
        processed_indices = set()
        duplicate_indices = set()
        
        # Initialize intermediate results if needed
        edge_dedup_result = None
        if save_intermediate:
            edge_dedup_result = {
                "head_id": group_data['head_id'],
                "head_name": group_data['head_text'],
                "relation": group_data['relation'],
                "total_edges": len(group_data['edges']),
                "candidates": [
                    {
                        "index": e["index"],
                        "node_id": e["node_id"],
                        "description": e["description"]
                    }
                    for e in entries
                ],
                "clustering": {
                    "method": group_data['config_params']['clustering_method'],
                    "threshold": group_data['config_params']['threshold'],
                    "clusters": []
                },
                "llm_groups": [],
                "final_merges": []
            }
            
            # Save clustering info
            for cluster_idx, cluster in enumerate(initial_clusters):
                cluster_info = {
                    "cluster_id": cluster_idx,
                    "size": len(cluster),
                    "member_indices": cluster,
                    "members": [
                        {
                            "index": idx,
                            "node_id": entries[idx]["node_id"],
                            "description": entries[idx]["description"]
                        }
                        for idx in cluster if 0 <= idx < len(entries)
                    ]
                }
                llm_clustering_details = group_data.get('llm_clustering_details')
                if llm_clustering_details and cluster_idx < len(llm_clustering_details):
                    detail = llm_clustering_details[cluster_idx]
                    cluster_info["llm_description"] = detail.get("description", "")
                    cluster_info["llm_rationale"] = detail.get("llm_rationale", "")
                edge_dedup_result["clustering"]["clusters"].append(cluster_info)
        
        # Process each cluster
        for cluster_idx, cluster in enumerate(initial_clusters):
            cluster_indices = [idx for idx in cluster if idx not in processed_indices and idx not in duplicate_indices]
            if not cluster_indices:
                continue
            
            # Single-item clusters - no dedup needed
            if len(cluster_indices) == 1:
                idx = cluster_indices[0]
                entry = entries[idx]
                final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
                processed_indices.add(idx)
                continue
            
            # Process semantic dedup results for this cluster
            batch_num = 0
            while True:
                key = (cluster_idx, batch_num)
                if key not in semantic_results:
                    break
                
                result = semantic_results[key]
                groups = result['groups']
                batch_indices = result['batch_indices']
                overflow_indices = result.get('overflow_indices', [])
                
                # Save LLM groups
                if save_intermediate:
                    llm_result = {
                        "cluster_id": cluster_idx,
                        "batch_indices": batch_indices,
                        "batch_size": len(batch_indices),
                        "groups": []
                    }
                    for group in groups:
                        group_info = {
                            "members": group.get("members", []),
                            "representative": group.get("representative"),
                            "rationale": group.get("rationale"),
                            "member_details": [
                                {
                                    "local_idx": m,
                                    "global_idx": batch_indices[m] if 0 <= m < len(batch_indices) else None,
                                    "description": entries[batch_indices[m]]["description"] if 0 <= m < len(batch_indices) else None
                                }
                                for m in group.get("members", [])
                                if 0 <= m < len(batch_indices)
                            ]
                        }
                        llm_result["groups"].append(group_info)
                    edge_dedup_result["llm_groups"].append(llm_result)
                
                # Process groups
                if not groups:
                    # No grouping - add all as separate edges
                    for global_idx in batch_indices:
                        if global_idx not in processed_indices:
                            entry = entries[global_idx]
                            final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
                            processed_indices.add(global_idx)
                else:
                    for group in groups:
                        rep_local = group.get("representative")
                        if rep_local is None or rep_local < 0 or rep_local >= len(batch_indices):
                            continue
                        
                        rep_global = batch_indices[rep_local]
                        if rep_global in processed_indices:
                            continue
                        
                        # Collect duplicates
                        duplicates = []
                        for member_local in group.get("members", []):
                            if member_local < 0 or member_local >= len(batch_indices):
                                continue
                            member_global = batch_indices[member_local]
                            if member_global == rep_global or member_global in processed_indices:
                                continue
                            duplicates.append(entries[member_global])
                            duplicate_indices.add(member_global)
                        
                        # Save merge info
                        if save_intermediate and duplicates:
                            merge_info = {
                                "representative": {
                                    "index": rep_global,
                                    "node_id": entries[rep_global]["node_id"],
                                    "description": entries[rep_global]["description"]
                                },
                                "duplicates": [
                                    {
                                        "index": d.get("index"),
                                        "node_id": d["node_id"],
                                        "description": d["description"]
                                    }
                                    for d in duplicates
                                ],
                                "rationale": group.get("rationale")
                            }
                            edge_dedup_result["final_merges"].append(merge_info)
                        
                        # Merge and add to final edges
                        merged_data = self._merge_duplicate_metadata(
                            entries[rep_global],
                            duplicates,
                            group.get("rationale"),
                        )
                        final_edges.append((entries[rep_global]["node_id"], merged_data))
                        processed_indices.add(rep_global)
                
                # Handle overflow
                if batch_num == 0:
                    for global_idx in overflow_indices:
                        if global_idx not in processed_indices:
                            entry = entries[global_idx]
                            final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
                            processed_indices.add(global_idx)
                
                batch_num += 1
        
        # Add any remaining unprocessed entries
        for entry in entries:
            idx = entry["index"]
            if idx not in processed_indices and idx not in duplicate_indices:
                final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
                processed_indices.add(idx)
        
        # Save results
        if save_intermediate:
            edge_dedup_result["summary"] = {
                "total_edges": len(group_data['edges']),
                "total_clusters": len(initial_clusters),
                "single_item_clusters": sum(1 for c in initial_clusters if len(c) == 1),
                "multi_item_clusters": sum(1 for c in initial_clusters if len(c) > 1),
                "total_llm_calls": len(edge_dedup_result["llm_groups"]),
                "total_merges": len(edge_dedup_result["final_merges"]),
                "edges_merged": sum(len(m["duplicates"]) for m in edge_dedup_result["final_merges"]),
                "final_edges": len(final_edges)
            }
            
            if not hasattr(self, '_edge_dedup_results'):
                self._edge_dedup_results = []
            self._edge_dedup_results.append(edge_dedup_result)
        
        return final_edges

    def triple_deduplicate(self):
        """deduplicate triples in lv1 and lv2"""
        new_graph = nx.MultiDiGraph()

        for node, node_data in self.graph.nodes(data=True):
            new_graph.add_node(node, **node_data)

        seen_triples = set()
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            relation = data.get('relation') 
            if (u, v, relation) not in seen_triples:
                seen_triples.add((u, v, relation))
                new_graph.add_edge(u, v, **data)
        self.graph = new_graph

    def triple_deduplicate_semantic(self, return_dedup_results=False):
        """deduplicate triples in lv1 and lv2

        Args:
            return_dedup_results: If True, return dedup results in entity_attribution format instead of modifying graph
        """
        new_graph = nx.MultiDiGraph()
        for node, node_data in self.graph.nodes(data=True):
            new_graph.add_node(node, **node_data)

        config = self._get_semantic_dedup_config()
        save_intermediate = config and getattr(config, "save_intermediate_results", False)
        if save_intermediate:
            self._edge_dedup_results = []

        # seen_triples = set()
        grouped_edges: dict = defaultdict(list)
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            # relation = data.get('relation') 
            # if (u, v, relation) not in seen_triples:
            #     seen_triples.add((u, v, relation))
            #     new_graph.add_edge(u, v, **data)
            relation = data.get('relation')
            grouped_edges[(u, relation)].append((v, copy.deepcopy(data)))


        # ================================================================
        # PHASE 1: Prepare all groups and collect metadata
        # ================================================================
        dedup_groups = []  # List of dicts with all info needed for deduplication
 

        for (head, relation), edges in grouped_edges.items():
            exact_unique = self._deduplicate_exact(edges)
            
            # Only process if semantic dedup is enabled and there are multiple edges
            if not (self._semantic_dedup_enabled() and len(exact_unique) > 1):
                # No dedup needed, add directly to graph
                for tail_id, edge_data in exact_unique:
                    new_graph.add_edge(head, tail_id, **edge_data)
                continue

            if "别名包括" in relation or "等同于" in relation or "member_of" in relation or "represented_by" in relation \
                or "kw_filter_by" in relation:
                continue
            
            # Prepare group metadata
            group_data = self._prepare_dedup_group(head, relation, exact_unique, config)
            if group_data:
                dedup_groups.append(group_data)
        
        logger.info(f"Prepared {len(dedup_groups)} groups for semantic deduplication")
        
        if not dedup_groups:
            # No deduplication needed, return empty results or None based on return_dedup_results flag
            return [] if return_dedup_results else None
        
        # ================================================================
        # PHASE 2: Batch collect and process clustering prompts
        # ================================================================
        clustering_prompts = []
        clustering_method = getattr(config, "clustering_method", "embedding")
        
        # Check if we have preloaded clusters to skip clustering phase
        if hasattr(self, 'preloaded_edge_clusters') and self.preloaded_edge_clusters:
            logger.info("Using preloaded cluster results for edge deduplication, skipping clustering phase...")
            self._apply_preloaded_clusters_for_edges(dedup_groups, self.preloaded_edge_clusters)

        elif clustering_method == "llm":
            logger.info("Collecting all clustering prompts...")
            for group_idx, group_data in enumerate(dedup_groups):
                prompts = self._collect_clustering_prompts(group_data)
                for prompt_data in prompts:
                    prompt_data['metadata']['group_idx'] = group_idx
                    clustering_prompts.append(prompt_data)
            
            logger.info(f"Collected {len(clustering_prompts)} clustering prompts, processing concurrently...")
            clustering_results = self._concurrent_llm_calls(clustering_prompts,type = "clustering")
            
            # Parse clustering results and update group_data
            logger.info("Parsing clustering results...")
            self._parse_clustering_results(dedup_groups, clustering_results)
        else:
            # Use embedding-based clustering
            logger.info("Using embedding-based clustering...")
            for group_data in dedup_groups:
                self._apply_embedding_clustering(group_data)
        
        # ================================================================
        # PHASE 3: Batch collect and process semantic dedup prompts
        # ================================================================
        logger.info("Collecting all semantic dedup prompts...")
        semantic_prompts = []
        #import ipdb; ipdb.set_trace()
        for group_idx, group_data in enumerate(dedup_groups):
            entries = group_data['entries']
#            node_ids = [x['node_id'] for x in entries]
#            # "entity_1513" in node_ids or attribute_1417 entity_494 entity_720
#            #if "entity_494" not in node_ids or "entity_720" not in node_ids or "entity_740" not in node_ids:
#            if "entity_201" not in node_ids or "entity_203" not in node_ids:
#                continue
#            print(f"-------------len:{len(node_ids)}-----------------")
#            print(node_ids)
#            import ipdb; ipdb.set_trace()

            prompts = self._collect_semantic_dedup_prompts(group_data)
            for prompt_data in prompts:
                prompt_data['metadata']['group_idx'] = group_idx
                semantic_prompts.append(prompt_data)

        if True:
        #if True:
            #import pdb; pdb.set_trace()
            logger.info(f"Collected {len(semantic_prompts)} semantic dedup prompts, processing concurrently...")
            semantic_results = self._concurrent_llm_calls(semantic_prompts)
        #import pdb; pdb.set_trace()
        #import pickle
        #with open(r"/home/hhy/GPT/workspace/youtu-graphrag/output/dedup_intermediate/Artifacts_5_test_new_semantic_results_20251020_131314.pkl",'rb') as f:
        #with open(r"/home/hhy/GPT/workspace/m_youtu/temp_llm_results.pkl",'rb') as f:
            #semantic_results = pickle.load(f)
            #semantic_results = pickle.load(f)
        
        # Parse semantic dedup results and update group_data
        logger.info("Parsing semantic dedup results...")
        self._parse_semantic_dedup_results(dedup_groups, semantic_results)
        
        # ================================================================
        # PHASE 4: Build final deduplicated edges
        # ================================================================
        logger.info("Building final deduplicated graph...")
        for group_data in dedup_groups:
            final_edges = self._build_final_edges(group_data, save_intermediate)
            head = group_data['head_id']
            for tail_id, edge_data in final_edges:
                new_graph.add_edge(head, tail_id, **edge_data)

        # If return_dedup_results is True, format and return results instead of modifying graph
        if return_dedup_results:
            dedup_results = self._format_dedup_results_for_output(dedup_groups)
            return dedup_results
        else:
            # Only modify self.graph when not returning dedup results
            self.graph = new_graph

        # Save edge deduplication intermediate results
        if save_intermediate and hasattr(self, '_edge_dedup_results') and self._edge_dedup_results:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = getattr(config, "intermediate_results_path", None)

            if not output_path:
                output_path = f"output/dedup_intermediate/{self.dataset_name}_edge_dedup_{timestamp}.json"
            else:
                # If path is a directory, add filename
                if output_path.endswith('/'):
                    output_path = f"{output_path}{self.dataset_name}_edge_dedup_{timestamp}.json"
                else:
                    # Add _edge suffix to distinguish from keyword dedup
                    base, ext = os.path.splitext(output_path)
                    output_path = f"{base}_edge_{timestamp}{ext}"

            # Ensure directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Build complete results structure
            edge_intermediate_results = {
                "dataset": self.dataset_name,
                "dedup_type": "edge_deduplication",
                "config": {
                    "threshold": getattr(config, "embedding_threshold", 0.85) or 0.85,
                    "max_batch_size": max(1, int(getattr(config, "max_batch_size", 8) or 8)),
                    "max_candidates": int(getattr(config, "max_candidates", 0) or 0),
                },
                "triples": self._edge_dedup_results,
                "summary": {
                    "total_triples": len(self._edge_dedup_results),
                    "total_edges": sum(r["total_edges"] for r in self._edge_dedup_results),
                    "total_clusters": sum(len(r["clustering"]["clusters"]) for r in self._edge_dedup_results),
                    "total_llm_calls": sum(len(r["llm_groups"]) for r in self._edge_dedup_results),
                    "total_merges": sum(len(r["final_merges"]) for r in self._edge_dedup_results),
                    "total_edges_merged": sum(r["summary"]["edges_merged"] for r in self._edge_dedup_results),
                    "final_total_edges": sum(r["summary"]["final_edges"] for r in self._edge_dedup_results)
                }
            }

            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(edge_intermediate_results, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved edge deduplication intermediate results to: {output_path}")
                logger.info(f"Summary: {edge_intermediate_results['summary']}")
            except Exception as e:
                logger.warning(f"Failed to save edge deduplication intermediate results: {e}")

            # Clean up
            del self._edge_dedup_results

    def _format_dedup_results_for_output(self, dedup_groups: list) -> List[Dict[str, Any]]:
        """Format dedup groups into entity_attribution_dedup_results.json style format"""
        output = []
        cluster_idx = 0

        

        for group_data in dedup_groups:
            head_id = group_data['head_id']
            relation = group_data['relation']
            entries = group_data['entries']

            # Get head node info
            head_node_data = self.graph.nodes.get(head_id, {})
            head_node = {
                "label": head_node_data.get("label", "entity"),
                "properties": head_node_data.get("properties", {})
            }

            # Get tail nodes to dedup (original candidates)
            tail_nodes_to_dedup = []
            for entry in entries:
                node_id = entry['node_id']
                # Use the existing _describe_node method for consistent formatting
                entity_text = self._describe_node(node_id)
                tail_nodes_to_dedup.append(entity_text)

            # Get dedup results with validation info and convert to clusters
            group_dedup_results = self._extract_dedup_results_with_validation(group_data)
            dedup_results = {}

            # Convert each group to cluster format
            for group_key, group_info in group_dedup_results.items():
                members = group_info.get('members', [])

                # Convert member indices to actual entity texts
                member_texts = []
                for member_idx in members:
                    if isinstance(member_idx, int) and member_idx < len(entries):
                        entry = entries[member_idx]
                        node_id = entry['node_id']
                        # Use the existing _describe_node method for consistent formatting
                        entity_text = self._describe_node(node_id)
                        member_texts.append(entity_text)
                    else:
                        # If member_idx is not an integer index, use it directly
                        member_texts.append(str(member_idx))

                # Only create cluster if there are multiple members (as per deduplication logic)
                if len(member_texts) > 1:
                    cluster_key = f"cluster_{cluster_idx}"
                    dedup_results[cluster_key] = {
                        "member": member_texts,
                        "llm_judge_reason": group_info.get('rationale', '')
                    }
                    cluster_idx += 1

            # Get deduped tails (final edges after dedup)
            deduped_tails = []
            final_edges = self._build_final_edges(group_data, False)
            for tail_id, edge_data in final_edges:
                # Use the existing _describe_node method for consistent formatting
                tail_text = self._describe_node(tail_id)
                deduped_tails.append(tail_text)

            result_item = {
                "head_node": head_node,
                "relation": relation,
                "tail_nodes_to_dedup": tail_nodes_to_dedup,
                "dedup_results": dedup_results,
                "deduped_tails": deduped_tails
            }

            output.append(result_item)

        return output

    def _extract_dedup_results_with_validation(self, group_data: dict) -> Dict[str, Any]:
        """Extract dedup results with LLM validation information"""
        dedup_results = {}

        # Check if we have semantic results with validation info
        semantic_results = group_data.get('semantic_results', {})

        for key, semantic_data in semantic_results.items():
            groups = semantic_data.get('groups', [])
            validation_report = semantic_data.get('validation_report')
            batch_indices = semantic_data.get('batch_indices', [])

            # For each group, add validation info
            for group_idx, group in enumerate(groups):
                group_key = f"group_{group_idx}"

                # Base group info
                dedup_results[group_key] = {
                    "members": [batch_indices[x] for x in group.get('members', [])],
                    "representative": group.get('representative'),
                    "rationale": group.get('rationale', ''),
                }

                # Add validation info if available
                if validation_report:
                    is_valid = not validation_report.get('has_inconsistencies', False)
                    dedup_results[group_key]["llm_validation"] = {
                        "passed": is_valid,
                        "validation_report": validation_report
                    }
                    if not is_valid:
                        # Add the validation output for failed validations
                        dedup_results[group_key]["llm_validation"]["validation_output"] = validation_report
                else:
                    # No validation performed
                    dedup_results[group_key]["llm_validation"] = {
                        "passed": True,  # Assume passed if no validation
                        "validation_report": None
                    }

        return dedup_results

    def format_output(self) -> List[Dict[str, Any]]:
        """convert graph to specified output format"""
        output = []

        for u, v, data in self.graph.edges(data=True):
            u_data = self.graph.nodes[u]
            v_data = self.graph.nodes[v]

            relationship = {
                "start_node": {
                    "label": u_data["label"],
                    "properties": u_data["properties"],
                },
                "relation": data["relation"],
                "end_node": {
                    "label": v_data["label"],
                    "properties": v_data["properties"],
                },
            }
            output.append(relationship)

        return output
    
    def save_graphml(self, output_path: str):
        graph_processor.save_graph(self.graph, output_path)
    
    # ============================================================
    # Head Node Deduplication Methods
    # ============================================================
    
    def deduplicate_heads(
        self,
        enable_semantic: bool = None,
        similarity_threshold: float = None,
        use_llm_validation: bool = None,
        max_candidates: int = None,
        load_llm_results: bool = False
    ) -> Dict[str, Any]:
        """
        Main entry point for head node deduplication.
        
        Deduplicates entity nodes globally (across all relations).
        Should be run AFTER tail deduplication for best results.
        
        Args:
            enable_semantic: Enable semantic deduplication (default from config)
            similarity_threshold: Similarity threshold for semantic dedup (default from config)
            use_llm_validation: Use LLM for validation (default from config)
            max_candidates: Maximum number of candidate pairs to process (default from config)
        
        Returns:
            Dictionary with deduplication statistics
        """
        # Get configuration
        config = self.config.construction.semantic_dedup.head_dedup if hasattr(
            self.config.construction.semantic_dedup, 'head_dedup'
        ) else None
        
        if not config or not config.get('enabled', False):
            logger.info("Head deduplication is disabled in config")
            return {"enabled": False}
        
        # Use config values if not specified
        if enable_semantic is None:
            enable_semantic = config.get('enable_semantic', True)
        if similarity_threshold is None:
            similarity_threshold = config.get('similarity_threshold', 0.85)
        if use_llm_validation is None:
            use_llm_validation = config.get('use_llm_validation', False)
        if max_candidates is None:
            max_candidates = config.get('max_candidates', 1000)
        
        # Check if intermediate results should be saved
        save_intermediate = config.get('save_intermediate_results', False)
        
        # Initialize intermediate results collector
        intermediate_results = {
            "dataset": self.dataset_name,
            "config": {
                "enable_semantic": enable_semantic,
                "similarity_threshold": similarity_threshold,
                "use_llm_validation": use_llm_validation,
                "max_candidates": max_candidates,
                "candidate_similarity_threshold": getattr(config, 'candidate_similarity_threshold', 0.75)
            },
            "phases": {}
        } if save_intermediate else None


        logger.info("=" * 70)
        logger.info("Starting Head Node Deduplication")
        logger.info("=" * 70)
        logger.info(f"Configuration:")
        logger.info(f"  - Enable semantic dedup: {enable_semantic}")
        logger.info(f"  - Similarity threshold: {similarity_threshold}")
        logger.info(f"  - Use LLM validation: {use_llm_validation}")
        logger.info(f"  - Max candidates: {max_candidates}")
        logger.info(f"  - Save intermediate results: {save_intermediate}")
        logger.info("=" * 70)
        
        start_time = time.time()
        
        # Phase 1: Collect head candidates
        logger.info("\n[Phase 1/4] Collecting head candidates...")
        candidates, candidates_names = self._collect_head_candidates()
        logger.info(f"✓ Found {len(candidates)} entity nodes")
        
        # Record candidates info if saving intermediate results
        if save_intermediate:
            intermediate_results["phases"]["phase1_candidates"] = {
                "total_candidates": len(candidates),
                "candidate_ids": candidates[:100],  # Store first 100 for inspection
                "sample_candidates": [{
                    "node_id": node_id,
                    "name": self.graph.nodes[node_id].get("properties", {}).get("name", ""),
                    "description": self.graph.nodes[node_id].get("properties", {}).get("description", "")[:200]
                } for node_id in candidates[:10]] if candidates else []  # Store first 10 samples
            }

        # Phase 2: Exact match deduplication
        logger.info("\n[Phase 2/4] Exact match deduplication...")
        exact_merge_mapping = self._deduplicate_heads_exact(candidates)
        logger.info(f"✓ Identified {len(exact_merge_mapping)} exact matches")
        
        # Record exact match results
        if save_intermediate:
            intermediate_results["phases"]["phase2_exact_match"] = {
                "total_matches": len(exact_merge_mapping),
                "merge_pairs": [{
                    "duplicate_id": dup_id,
                    "duplicate_name": self.graph.nodes.get(dup_id, {}).get("properties", {}).get("name", ""),
                    "canonical_id": can_id,
                    "canonical_name": self.graph.nodes.get(can_id, {}).get("properties", {}).get("name", "")
                } for dup_id, can_id in list(exact_merge_mapping.items())[:50]]  # Store first 50 pairs
            }

        # Apply exact match merging
        exact_merged_count = self._merge_head_nodes(exact_merge_mapping, {})
        logger.info(f"✓ Merged {exact_merged_count} nodes")
        
        # Phase 3: Semantic deduplication (optional)
        semantic_merge_mapping = {}
        semantic_merged_count = 0
        
        if enable_semantic:
            logger.info("\n[Phase 3/4] Semantic deduplication...")
            
            # Get remaining nodes
            remaining_nodes = [
                node_id for node_id in candidates
                if node_id not in exact_merge_mapping and node_id in self.graph
            ]
            to_del_node_names = [candidates_names[node_id] for node_id in remaining_nodes]
            to_del_node_names = list(set(to_del_node_names))
            for node_name in to_del_node_names:
                if node_name in candidates_names:
                    del candidates_names[node_name]
                
            logger.info(f"  Remaining nodes after exact match: {len(remaining_nodes)}")
            
            if len(remaining_nodes) >= 2:
                candidate_pairs = None
                if not load_llm_results:
                    # Generate candidate pairs
                    candidate_similarity_threshold = config.get('candidate_similarity_threshold', 0.75)
                    candidate_pairs = self._generate_semantic_candidates(
                        remaining_nodes,
                        candidates_names,
                        max_candidates=max_candidates,
                        similarity_threshold=candidate_similarity_threshold
                    )
                    logger.info(f"✓ Generated {len(candidate_pairs)} candidate pairs")
                
                #import pdb; pdb.set_trace()
                # Record candidate pairs
                if save_intermediate:
                    if candidate_pairs is not None:
                        intermediate_results["phases"]["phase3_semantic"] = {
                            "remaining_nodes": len(remaining_nodes),
                            "candidate_pairs_generated": len(candidate_pairs),
                            "validation_method": "llm" if use_llm_validation else "embedding",
                            "sample_candidate_pairs": [{
                                "node_id_1": pair[0],
                                "node_name_1": self.graph.nodes.get(pair[0], {}).get("properties", {}).get("name", ""),
                                "node_id_2": pair[1],
                                "node_name_2": self.graph.nodes.get(pair[1], {}).get("properties", {}).get("name", ""),
                                "embedding_similarity": float(pair[2])
                            } for pair in candidate_pairs[:20]]  # Store first 20 pairs
                        }
                    else:
                        # Initialize phase3_semantic when loading LLM results
                        intermediate_results["phases"]["phase3_semantic"] = {
                            "remaining_nodes": len(remaining_nodes),
                            "candidate_pairs_generated": 0,
                            "validation_method": "llm",
                            "load_llm_results": True
                        }

                # Validate candidates
                if candidate_pairs or load_llm_results:
                    if use_llm_validation or load_llm_results:
                        logger.info("  Using LLM validation (high accuracy mode)...")
                        semantic_merge_mapping, metadata = self._validate_candidates_with_llm(
                            candidate_pairs if candidate_pairs is not None else [],
                            similarity_threshold,
                            load_llm_results
                        )
                    else:
                        logger.info("  Using embedding validation (fast mode)...")
                        semantic_merge_mapping, metadata = self._validate_candidates_with_embedding(
                            candidate_pairs if candidate_pairs is not None else [],
                            candidates_names,
                            similarity_threshold
                        )
                    
                    logger.info(f"✓ Identified {len(semantic_merge_mapping)} semantic matches")
                    
                    # Record semantic validation results
                    if save_intermediate:
                        intermediate_results["phases"]["phase3_semantic"]["validation_results"] = {
                            "total_matches": len(semantic_merge_mapping),
                            "merge_decisions": [{
                                "duplicate_id": dup_id,
                                "duplicate_name": self.graph.nodes.get(dup_id, {}).get("properties", {}).get("name", ""),
                                "canonical_id": can_id,
                                "canonical_name": self.graph.nodes.get(can_id, {}).get("properties", {}).get("name", ""),
                                "metadata": metadata.get(dup_id, {})
                            } for dup_id, can_id in list(semantic_merge_mapping.items())[:50]]  # Store first 50
                        }

                    # Apply semantic merging
                    semantic_merged_count = self._merge_head_nodes(semantic_merge_mapping, metadata)
                    logger.info(f"✓ Merged {semantic_merged_count} nodes")
                else:
                    logger.info("  No candidate pairs generated")
            else:
                logger.info("  Not enough nodes for semantic deduplication")
        else:
            logger.info("\n[Phase 3/4] Semantic deduplication skipped (disabled)")
        
        # Phase 4: Integrity validation
        logger.info("\n[Phase 4/4] Validating graph integrity...")
        issues = self.validate_graph_integrity_after_head_dedup()
        
        if any(issues.values()):
            logger.warning(f"⚠ Found integrity issues: {issues}")
        else:
            logger.info("✓ Graph integrity validated")
        
        elapsed_time = time.time() - start_time
        
        # Statistics
        final_entity_count = len([
            n for n, d in self.graph.nodes(data=True)
            if d.get("label") == "entity"
        ])
        
        stats = {
            "enabled": True,
            "total_candidates": len(candidates),
            "exact_merges": exact_merged_count,
            "semantic_merges": semantic_merged_count,
            "total_merges": exact_merged_count + semantic_merged_count,
            "initial_entity_count": len(candidates),
            "final_entity_count": final_entity_count,
            "reduction_rate": (exact_merged_count + semantic_merged_count) / len(candidates) * 100 if candidates else 0,
            "elapsed_time_seconds": elapsed_time,
            "integrity_issues": issues
        }
        
        logger.info("\n" + "=" * 70)
        logger.info("Head Deduplication Completed")
        logger.info("=" * 70)
        logger.info(f"Summary:")
        logger.info(f"  - Initial entities: {stats['initial_entity_count']}")
        logger.info(f"  - Final entities: {stats['final_entity_count']}")
        logger.info(f"  - Total merges: {stats['total_merges']}")
        logger.info(f"    • Exact matches: {stats['exact_merges']}")
        logger.info(f"    • Semantic matches: {stats['semantic_merges']}")
        logger.info(f"  - Reduction rate: {stats['reduction_rate']:.2f}%")
        logger.info(f"  - Time elapsed: {elapsed_time:.2f}s")
        logger.info("=" * 70)
        
        # Save intermediate results to file
        if save_intermediate and intermediate_results:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = getattr(config, "intermediate_results_path", None)
            
            if not output_path:
                output_path = f"output/dedup_intermediate/{self.dataset_name}_head_dedup_{timestamp}.json"
            else:
                # If path is a directory, add filename
                if output_path.endswith('/'):
                    output_path = f"{output_path}{self.dataset_name}_head_dedup_{timestamp}.json"
                else:
                    # Add _head suffix
                    base, ext = os.path.splitext(output_path)
                    output_path = f"{base}_head_{timestamp}{ext}"
            
            # Ensure directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # Add summary statistics
            intermediate_results["summary"] = stats
            
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(intermediate_results, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved head deduplication intermediate results to: {output_path}")
                logger.info(f"Summary: {intermediate_results['summary']}")
            except Exception as e:
                logger.warning(f"Failed to save intermediate results: {e}")

        # Export for review if configured
        if config.get('export_review', False):
            review_path = os.path.join(
                config.get('review_output_dir', 'output/review'),
                f"head_merge_{self.dataset_name}_{int(time.time())}.csv"
            )
            min_conf, max_conf = config.get('review_confidence_range', [0.70, 0.90])
            self.export_head_merge_candidates_for_review(
                output_path=review_path,
                min_confidence=min_conf,
                max_confidence=max_conf
            )
        
        return stats
    
    def _collect_head_candidates(self) -> Tuple[List[str], Dict[str, str]]:
        """Collect all entity nodes for deduplication."""
        from collections import defaultdict
        candidates_names = defaultdict(str)
        candidates_names.update({
            node_id: data.get("properties", {}).get("name", "")
            for node_id, data in self.graph.nodes(data=True)
            if data.get("label") == "entity" or data.get("label") == 'attribute'
        })
        candidates = [
            node_id
            for node_id, data in self.graph.nodes(data=True)
            if data.get("label") == "entity"
        ]
        return candidates, candidates_names
    
    def _normalize_entity_name(self, name: str) -> str:
        """Normalize entity name for exact matching."""
        if not name:
            return ""
        
        # Convert to lowercase and strip
        normalized = name.lower().strip()
        
        # Merge multiple spaces
        normalized = ' '.join(normalized.split())
        
        # Remove common punctuation
        for char in ['.', ',', '!', '?', ':', ';', '"', "'", '(', ')', '[', ']', '{', '}']:
            normalized = normalized.replace(char, '')
        
        return normalized
    
    def _deduplicate_heads_exact(self, candidates: List[str]) -> Tuple[Dict[str, str], List[Tuple[str, str]]]:
        """Exact match deduplication based on normalized names."""
        logger.info("Starting exact match deduplication for head nodes...")
        
        # Group by normalized name
        name_groups = defaultdict(list)

        invalid_nodes = []
        
        for node_id in candidates:
            if node_id not in self.graph:
                continue
            #import pdb; pdb.set_trace()
            node_data = self.graph.nodes[node_id]
            name = node_data.get("properties", {}).get("name", "")
            
            if not name:
                #import pdb; pdb.set_trace()
                continue
            
            normalized_name = self._normalize_entity_name(name)
            if not normalized_name:
                logger.warning(f"Normalized name is empty for node {node_id} with name {name}, will be ignored")
                invalid_nodes.append((node_id, name))

            name_groups[normalized_name].append((node_id, name))
        
        # Build merge mapping
        merge_mapping = {}
        
        for normalized_name, node_list in name_groups.items():
            if len(node_list) <= 1:
                continue
            
            # Choose canonical node (smallest ID)
            node_list_sorted = sorted(node_list, key=lambda x: int(x[0].split('_')[1]))
            canonical_id = node_list_sorted[0][0]
            
            for node_id, original_name in node_list_sorted[1:]:
                merge_mapping[node_id] = canonical_id
        
        logger.info(f"Exact match found {len(merge_mapping)} duplicate head nodes")
        return merge_mapping, invalid_nodes
    
    def _generate_semantic_candidates(
        self,
        remaining_nodes: List[str],
        candidates_names: Dict[str, str],
        max_candidates: int = 1000,
        similarity_threshold: float = 0.75,
        concurrent_calls: bool = True
    ) -> List[Tuple[str, str, float]]:
        """Generate candidate node pairs using embedding similarity."""
        logger.info("Generating semantic deduplication candidates...")
        
        if len(remaining_nodes) < 2:
            return []
        
        #import pdb; pdb.set_trace()
        # Get node descriptions
        node_descriptions = {}
        for node_id in remaining_nodes:
            if node_id not in self.graph:
                continue
            desc = self._describe_node_for_clustering(node_id)
            if desc:
                node_descriptions[node_id] = desc
        
        if len(node_descriptions) < 2:
            return []
        
        # Get embeddings
        nodes = list(node_descriptions.keys())
        descriptions = [node_descriptions[node_id] for node_id in nodes]
        if concurrent_calls:
            embeddings_array = self._concurrent_embedding_calls(descriptions, enable_cache=True)
        else:
            #import pdb; pdb.set_trace()
            #embedder = self._get_semantic_dedup_embedder()
            embedder = self._get_online_API_embedder()  
            if embedder is None:
                return [list(range(len(descriptions)))]

            try:
                embeddings = embedder.encode(descriptions, normalize_embeddings=True)
                embeddings_array = np.array(embeddings)
            except Exception as e:
                logger.error(f"Failed to get embeddings: {e}")
                return []

            #import pdb; pdb.set_trace()
        # Compute similarity matrix
        from sklearn.metrics.pairwise import cosine_similarity
        similarity_matrix = cosine_similarity(embeddings_array)
        
        # Extract high similarity pairs
        candidates = []
        n = len(nodes)
        
        for i in range(n):
            for j in range(i + 1, n):
                sim = similarity_matrix[i][j]
                if sim >= similarity_threshold:
                    candidates.append((nodes[i], nodes[j], float(sim)))
        
        # Sort by similarity and take top-K
        candidates.sort(key=lambda x: x[2], reverse=True)
        
        if len(candidates) > max_candidates:
            candidates = candidates[:max_candidates]
        
        return candidates
    
    def _validate_candidates_with_embedding(
        self,
        candidate_pairs: List[Tuple[str, str, float]],
        candidate_names: Dict[str, str],
        threshold: float
    ) -> Tuple[Dict[str, str], Dict[str, dict]]:
        """Validate candidates using embedding similarity only."""
        merge_mapping = {}
        metadata = {}
        
        # Use Union-Find to handle transitivity
        parent = {}
        
        def find(x):
            if x not in parent:
                parent[x] = x
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                if int(px.split('_')[1]) < int(py.split('_')[1]):
                    parent[py] = px
                else:
                    parent[px] = py
        
        # Process valid pairs
        valid_pairs = []
        valid_pairs_names = []
        for node_id_1, node_id_2, similarity in candidate_pairs:
            if similarity >= threshold:
                union(node_id_1, node_id_2)
                valid_pairs.append((node_id_1, node_id_2, similarity))
                valid_pairs_names.append((candidate_names[node_id_1], candidate_names[node_id_2]))

        #import pdb; pdb.set_trace()
        # Build merge_mapping
        canonical_map = {}
        
        for node_id_1, node_id_2, similarity in valid_pairs:
            root = find(node_id_1)
            
            if root not in canonical_map:
                canonical_map[root] = root
            
            for node in [node_id_1, node_id_2]:
                node_root = find(node)
                if node != canonical_map[node_root]:
                    merge_mapping[node] = canonical_map[node_root]
                    if node not in metadata:
                        metadata[node] = {
                            "rationale": f"High embedding similarity (threshold={threshold})",
                            "confidence": float(similarity),
                            "method": "embedding"
                        }
        
        return merge_mapping, metadata
    
    def _validate_candidates_with_llm(
        self,
        candidate_pairs: List[Tuple[str, str, float]],
        threshold: float,
        load_llm_results: bool = False
    ) -> Tuple[Dict[str, str], Dict[str, dict]]:
        """Validate candidates using LLM."""
        logger.info(f"Validating {len(candidate_pairs)} candidates with LLM...")
        
        if not load_llm_results:
            # Build prompts
            prompts = []
            for node_id_1, node_id_2, embedding_sim in candidate_pairs:
                prompt_text = self._build_head_dedup_prompt(node_id_1, node_id_2)
                prompts.append({
                    "prompt": prompt_text,
                    'type':'semantic',
                    "metadata": {
                        "node_id_1": node_id_1,
                        "node_id_2": node_id_2,
                        "embedding_similarity": embedding_sim
                    }
                })
        
        # Concurrent LLM calls
            llm_results = self._concurrent_llm_calls(prompts, type="head_dedup")
        else:
            with open(r"/home/hhy/GPT/workspace/m_youtu/llm_results.json", "r") as f:
                llm_results = json.load(f)
        
        #import pdb; pdb.set_trace()
        
        # Parse results
        merge_mapping = {}
        metadata = {}
        
        for result in llm_results:
            meta = result.get("metadata", {})
            response = result.get("response", "")
            
            parsed = self._parse_coreference_response(response)
            is_coreferent = parsed.get("is_coreferent", False)
            rationale = parsed.get("rationale", "")
            
            if is_coreferent:
                node_id_1 = meta["node_id_1"]
                node_id_2 = meta["node_id_2"]
                
                canonical = min(node_id_1, node_id_2, key=lambda x: int(x.split('_')[1]))
                duplicate = node_id_2 if canonical == node_id_1 else node_id_1
                
                merge_mapping[duplicate] = canonical
                metadata[duplicate] = {
                    "rationale": rationale,
                    "embedding_similarity": meta.get("embedding_similarity", 0.0),
                    "method": "llm"
                }
        
        return merge_mapping, metadata
    
    def _build_head_dedup_prompt(self, node_id_1: str, node_id_2: str) -> str:
        """Build LLM prompt for head deduplication.
        
        Loads prompt from config file (prompts.head_dedup.general).
        If prompt is missing or malformed, raises an error.
        """
        desc_1 = self._describe_node(node_id_1)
        desc_2 = self._describe_node(node_id_2)
        
        context_1 = self._collect_node_context(node_id_1)
        context_2 = self._collect_node_context(node_id_2)
        
        # Load prompt from config (no fallback)
        try:
            prompt_template = self.config.get_prompt_formatted(
                "head_dedup", 
                "general",
                entity_1=desc_1,
                context_1=context_1,
                entity_2=desc_2,
                context_2=context_2
            )
            return prompt_template
        except Exception as e:
            error_msg = (
                f"Failed to load head_dedup prompt from config: {e}\n"
                f"Please ensure 'prompts.head_dedup.general' is defined in your config file.\n"
                f"See HEAD_DEDUP_PROMPT_CUSTOMIZATION.md for details."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def _collect_node_context(self, node_id: str, max_relations: int = 10) -> str:
        """Collect graph relations as context for a node."""
        config = self.config.construction.semantic_dedup.head_dedup if hasattr(
            self.config.construction.semantic_dedup, 'head_dedup'
        ) else None
        
        if config:
            max_relations = getattr(config, 'max_relations_context', 10)
        
        contexts = []
        
        # Outgoing edges
        out_edges = list(self.graph.out_edges(node_id, data=True))[:max_relations]
        for _, tail_id, data in out_edges:
            relation = data.get("relation", "related_to")
            tail_desc = self._describe_node(tail_id)
            contexts.append(f"  • {relation} → {tail_desc}")
        
        # Incoming edges
        in_edges = list(self.graph.in_edges(node_id, data=True))[:max_relations]
        for head_id, _, data in in_edges:
            relation = data.get("relation", "related_to")
            head_desc = self._describe_node(head_id)
            contexts.append(f"  • {head_desc} → {relation}")
        
        return "\n".join(contexts) if contexts else "  (No relations found)"
    
    def _parse_coreference_response(self, response: str) -> dict:
        """Parse LLM response for coreference decision."""
        try:
            parsed = json_repair.loads(response)
            return {
                "is_coreferent": bool(parsed.get("is_coreferent", False)),
                "confidence": float(parsed.get("confidence", 0.0)),
                "rationale": str(parsed.get("rationale", ""))
            }
        except Exception as e:
            logger.warning(f"Failed to parse LLM coreference response: {e}")
            return {
                "is_coreferent": False,
                "confidence": 0.0,
                "rationale": "Parse error"
            }
    
    def _merge_head_nodes(
        self,
        merge_mapping: Dict[str, str],
        metadata: Dict[str, dict]
    ) -> int:
        """Execute head node merging and update graph structure."""
        if not merge_mapping:
            return 0
        
        merged_count = 0
        
        for duplicate_id, canonical_id in merge_mapping.items():
            if duplicate_id not in self.graph or canonical_id not in self.graph:
                continue
            
            if duplicate_id == canonical_id:
                continue
            
            try:

                # Transfer outgoing edges
                self._reassign_outgoing_edges(duplicate_id, canonical_id)
                
                # Transfer incoming edges
                self._reassign_incoming_edges(duplicate_id, canonical_id)
                
                # Merge node properties
                self._merge_node_properties(
                    duplicate_id,
                    canonical_id,
                    metadata.get(duplicate_id, {})
                )
                
                # Remove duplicate node
                self.graph.remove_node(duplicate_id)
                merged_count += 1
                
            except Exception as e:
                logger.error(f"Error merging {duplicate_id} into {canonical_id}: {e}")
                continue
        
        return merged_count
    
    def _reassign_outgoing_edges(self, source_id: str, target_id: str):
        """Transfer outgoing edges from source to target node."""
        outgoing = list(self.graph.out_edges(source_id, keys=True, data=True))
        #import pdb; pdb.set_trace()
        for _, tail_id, key, data in outgoing:
            if tail_id == target_id:
                continue
            
            edge_exists, existing_key = self._find_similar_edge(target_id, tail_id, data)
            
            if not edge_exists:
                self.graph.add_edge(target_id, tail_id, **copy.deepcopy(data))
            else:
                self._merge_edge_chunks(target_id, tail_id, existing_key, data)
    
    def _reassign_incoming_edges(self, source_id: str, target_id: str):
        """Transfer incoming edges from source to target node."""
        incoming = list(self.graph.in_edges(source_id, keys=True, data=True))
        
        for head_id, _, key, data in incoming:
            if head_id == target_id:
                continue
            
            edge_exists, existing_key = self._find_similar_edge(head_id, target_id, data)
            
            if not edge_exists:
                self.graph.add_edge(head_id, target_id, **copy.deepcopy(data))
            else:
                self._merge_edge_chunks(head_id, target_id, existing_key, data)
    
    def _find_similar_edge(self, u: str, v: str, new_data: dict) -> Tuple[bool, Any]:
        """Check if a similar edge already exists."""
        new_relation = new_data.get("relation")
        
        if not self.graph.has_edge(u, v):
            return False, None
        
        for key, data in self.graph[u][v].items():
            if data.get("relation") == new_relation:
                return True, key
        
        return False, None
    
    def _merge_edge_chunks(self, u: str, v: str, edge_key: Any, new_data: dict):
        """Merge chunk information of edges."""
        existing_data = self.graph[u][v][edge_key]
        
        existing_chunks = set(existing_data.get("source_chunks", []))
        new_chunks = set(new_data.get("source_chunks", []))
        merged_chunks = list(existing_chunks | new_chunks)
        
        if merged_chunks:
            existing_data["source_chunks"] = merged_chunks
    
    def _merge_node_properties(
        self,
        duplicate_id: str,
        canonical_id: str,
        merge_meta: dict
    ):
        """Merge node properties and record provenance."""
        canonical_data = self.graph.nodes[canonical_id]
        duplicate_data = self.graph.nodes[duplicate_id]
        
        # Initialize head_dedup metadata
        properties = canonical_data.setdefault("properties", {})
        if "head_dedup" not in properties:
            properties["head_dedup"] = {
                "merged_nodes": [],
                "merge_history": []
            }
        
        # Record merge info
        properties["head_dedup"]["merged_nodes"].append(duplicate_id)
        properties["head_dedup"]["merge_history"].append({
            "merged_node_id": duplicate_id,
            "merged_node_name": duplicate_data.get("properties", {}).get("name", ""),
            "rationale": merge_meta.get("rationale", "Semantic similarity"),
            "confidence": merge_meta.get("confidence", 1.0),
            "method": merge_meta.get("method", "unknown"),
            "timestamp": time.time()
        })
        
        # Merge chunk info if available
        canonical_chunks = set(properties.get("chunk_ids", []))
        duplicate_chunks = set(duplicate_data.get("properties", {}).get("chunk_ids", []))
        merged_chunks = list(canonical_chunks | duplicate_chunks)
        
        if merged_chunks:
            properties["chunk_ids"] = merged_chunks
    
    def validate_graph_integrity_after_head_dedup(self) -> Dict[str, List]:
        """Validate graph integrity after head deduplication."""
        issues = {
            "orphan_nodes": [],
            "self_loops": [],
            "dangling_references": [],
            "missing_metadata": []
        }
        
        # Check orphan nodes
        for node_id, data in self.graph.nodes(data=True):
            if data.get("label") == "entity":
                in_degree = self.graph.in_degree(node_id)
                out_degree = self.graph.out_degree(node_id)
                if in_degree == 0 and out_degree == 0:
                    issues["orphan_nodes"].append(node_id)
        
        # Check self loops
        for u, v in self.graph.edges():
            if u == v:
                issues["self_loops"].append((u, v))
        
        # Check dangling references
        for u, v, data in self.graph.edges(data=True):
            if u not in self.graph.nodes:
                issues["dangling_references"].append(("head", u, v))
            if v not in self.graph.nodes:
                issues["dangling_references"].append(("tail", u, v))
        
        # Check metadata completeness
        for node_id, data in self.graph.nodes(data=True):
            if "head_dedup" in data.get("properties", {}):
                dedup_info = data["properties"]["head_dedup"]
                if not isinstance(dedup_info, dict):
                    issues["missing_metadata"].append((node_id, "invalid_type"))
                elif "merged_nodes" not in dedup_info or "merge_history" not in dedup_info:
                    issues["missing_metadata"].append((node_id, "missing_fields"))
        
        return issues
    
    def export_head_merge_candidates_for_review(
        self,
        output_path: str,
        min_confidence: float = 0.70,
        max_confidence: float = 0.90
    ):
        """Export merge candidates for human review."""
        logger.info(f"Exporting head merge candidates for review (confidence: {min_confidence}-{max_confidence})...")
        
        candidates = []
        
        for node_id, data in self.graph.nodes(data=True):
            if data.get("label") != "entity":
                continue
            
            dedup_info = data.get("properties", {}).get("head_dedup", {})
            
            for merge_record in dedup_info.get("merge_history", []):
                confidence = merge_record.get("confidence", 1.0)
                
                if min_confidence <= confidence <= max_confidence:
                    candidates.append({
                        "canonical_node_id": node_id,
                        "canonical_name": data.get("properties", {}).get("name", ""),
                        "merged_node_id": merge_record["merged_node_id"],
                        "merged_name": merge_record["merged_node_name"],
                        "confidence": confidence,
                        "method": merge_record.get("method", "unknown"),
                        "rationale": merge_record["rationale"]
                    })
        
        # Export as CSV
        if candidates:
            import csv
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = [
                    "canonical_node_id", "canonical_name",
                    "merged_node_id", "merged_name",
                    "confidence", "method", "rationale"
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(candidates)
            
            logger.info(f"✓ Exported {len(candidates)} merge candidates to {output_path}")
        else:
            logger.info("No candidates found in the specified confidence range")
    
    # ============================================================
    # End of Head Node Deduplication Methods
    # ============================================================
    
    # ============================================================
    # Improved Head Deduplication: LLM-Driven + Alias Relationships
    # ============================================================

    def _validate_candidates_with_llm_v2(
        self,
        candidate_pairs: List[Tuple[str, str, float]],
        threshold: float = 0.85,
        load_llm_results: bool = False,
        candidates_names: Dict[str, str] = {}
    ) -> Tuple[Dict[str, str], Dict[str, dict], List[Dict]]:
        """
        Validate candidates using LLM with representative selection.
        
        This improved version asks LLM to:
        1. Determine if entities are coreferent
        2. Choose which entity should be the primary representative
        
        Args:
            candidate_pairs: List of (node_id_1, node_id_2, similarity)
            threshold: Confidence threshold (not used for representative selection)
            
        Returns:
            (merge_mapping, metadata): {duplicate_id: representative_id}, metadata
        """
        parent = {}
        def find(x):
            if x not in parent:
                parent[x] = x
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(entity1, entity2):
            """Union with frequency priority."""
            root1, root2 = find(entity1), find(entity2)
            if root1 == root2:
                return
            if root1 != root2:
                parent[root1] = root2
 
        if not load_llm_results:
            logger.info(f"Validating {len(candidate_pairs)} candidates with LLM (v2: LLM-driven representative)...")
        # Build prompts
            prompts = []
            for node_id_1, node_id_2, embedding_sim in candidate_pairs:
                #if node_id_1 != "entity_2" or node_id_2 != "entity_188":
                #    continue
                prompt_text = self._build_head_dedup_prompt_v2(node_id_1, node_id_2)
                prompts.append({
                    "prompt": prompt_text,
                    "type": "semantic",
                    "metadata": {
                        "node_id_1": node_id_1,
                        "node_id_2": node_id_2,
                        "embedding_similarity": embedding_sim
                    }
                })
            # Concurrent LLM calls
            logger.info(f"Sending {len(prompts)} requests to LLM...")
            llm_results = self._concurrent_llm_calls(prompts, type="head_dedup")
        else:
            with open(r"/home/hhy/GPT/workspace/m_youtu/llm_results_new.json", "r") as f:
                llm_results = json.load(f)
        
        #import pdb; pdb.set_trace()

        intermediate_results = []
        llm_results_to_replace = []
        try:
            for index, result in enumerate(llm_results):
                meta = result.get("metadata", {})
                response = result.get("response", "")
                parsed, response_to_replace, attempt_count = self._parse_coreference_response_v2(response, prompts[index], index)
                if attempt_count > 1:
                    llm_results_to_replace.append((index, response_to_replace))
                is_coreferent = parsed.get("is_coreferent", False)
                preferred_representative = parsed.get("representative")
                rationale = parsed.get("rationale", "")
                intermediate_results.append(
                    {
                        "entity_1": self.graph.nodes[meta["node_id_1"]]["properties"]["name"],
                        "entity_2": self.graph.nodes[meta["node_id_2"]]["properties"]["name"],
                        "embedding_similarity": meta.get("embedding_similarity", 0.0),
                        "llm_judge_results":{
                        "is_coreferent": is_coreferent, 
                            "representative": self.graph.nodes[preferred_representative]["properties"]["name"] if is_coreferent else None,
                            "rationale": rationale
                        }
                    })
        except Exception as e:
            import pdb; pdb.set_trace()

        #with open("llm_judge_results.json", "w") as f:
        #    json.dump(intermediate_results, f, indent=2, ensure_ascii=False)
        #import pdb; pdb.set_trace()
        if len(llm_results_to_replace) > 0:
            for index, response_to_replace in llm_results_to_replace:
                llm_results[index]['response'] = response_to_replace
                logger.info(f"Replaced response for prompt {index}")

                cache_key = self._generate_llm_cache_key(prompts)
                self._save_llm_results(cache_key, llm_results)
                logger.info(f"Saved LLM results to cache for prompt {index}")

        #import pdb; pdb.set_trace()

        # Parse results
        merge_mapping = {}
        final_merge_mapping = {}
        metadata = {}
        
        
        for index, result in enumerate(llm_results):
            meta = result.get("metadata", {})
            response = result.get("response", "")
            
            # Parse LLM response
            parsed, response_to_replace, attempt_count = self._parse_coreference_response_v2(response, prompts[index], index)
            is_coreferent = parsed.get("is_coreferent", False)
            preferred_representative = parsed.get("representative")
            rationale = parsed.get("rationale", "")
            
            if is_coreferent and preferred_representative:
                node_id_1 = meta["node_id_1"]
                node_id_2 = meta["node_id_2"]
                
                # Validate that preferred_representative is one of the two entities
                if preferred_representative not in [node_id_1, node_id_2]:
                    logger.warning(
                        f"LLM returned invalid representative {preferred_representative} "
                        f"for pair ({node_id_1}, {node_id_2}). Skipping."
                    )
                    continue
                
                # Determine canonical and duplicate based on LLM's choice
                canonical = preferred_representative
                duplicate = node_id_2 if canonical == node_id_1 else node_id_1
                
                # Record the merge decision
                merge_mapping[duplicate] = canonical
                metadata[duplicate] = {
                    "rationale": rationale,
                    "confidence": 1.0,  # LLM made the decision
                    "embedding_similarity": meta.get("embedding_similarity", 0.0),
                    "method": "llm_v2",
                    "llm_chosen_representative": canonical
                }

                
                logger.debug(
                    f"LLM decided: {duplicate} is alias of {canonical} "
                    f"(rationale: {rationale[:100]}...)"
                )

        # Add existing "别名包括" relationships from the graph to merge_mapping
        # Strategy: LLM priority, but resolve complex conflicts with graph canonical
        # - Normal case: respect LLM decisions, don't override
        # - Complex conflict: when graph says A --[别名包括]--> B, but:
        #   * LLM says B → C
        #   * LLM says A → D (D ≠ C)
        #   Solution: Use A (graph canonical) as final canonical, merge B, C, D to A
        # Unified semantic: A --[别名包括]--> B means "B is an alias of A"
        logger.info("Scanning graph for existing '别名包括' relationships (graph canonical priority in conflicts)...")
        alias_count = 0
        skipped_count = 0
        transitive_count = 0
        complex_resolved_count = 0
        graph_canonical_dudep = {}
        
        for source_id, target_id, edge_data in self.graph.edges(data=True):
            if edge_data.get("relation", "") != "别名包括" or edge_data.get("relation", "") != "等同于":
                continue
            
            # Unified semantic: source_id --[别名包括]--> target_id
            # Means: "target_id is an alias of source_id"
            canonical_id = source_id  # A (graph canonical)
            duplicate_id = target_id  # B (alias)

            graph_canonical_dudep[duplicate_id] = canonical_id
            if duplicate_id in merge_mapping:
                # B already has LLM decision: B → C
                existing_canonical = merge_mapping[duplicate_id]  # C
                
                if existing_canonical == canonical_id:
                    # Already correct: B → A, skip
                    skipped_count += 1
                    logger.debug(f"Already correct: {duplicate_id} → {canonical_id}")
                else:
                    # Conflict: B → C (LLM), but graph says B is alias of A
                    # Check if A also has a decision
                    if canonical_id not in merge_mapping:
                        # Use graph canonical: A is the final canonical, override B and cascade C
                        logger.info(
                            f"Graph canonical override: {candidates_names[canonical_id]}({canonical_id}) is canonical, "
                            f"overriding {candidates_names[duplicate_id]}({duplicate_id}) → {candidates_names[existing_canonical]}({existing_canonical}) to {candidates_names[duplicate_id]}({duplicate_id}) → {candidates_names[canonical_id]}({canonical_id})"
                        )
                        if canonical_id == 'entity_1135':
                            pass
                            #import pdb; pdb.set_trace()
                        # Override B → A
                        merge_mapping[duplicate_id] = canonical_id
                        metadata[duplicate_id] = {
                            "rationale": f"{candidates_names[duplicate_id]}({duplicate_id}) is alias of graph canonical {candidates_names[canonical_id]}({canonical_id})",
                            "confidence": 1.0,
                            "method": "existing_alias_graph_canonical_override"
                        }
                        
                        # Cascade C → A
                        if existing_canonical != canonical_id and existing_canonical in self.graph.nodes():
                            merge_mapping[existing_canonical] = canonical_id
                            metadata[existing_canonical] = {
                                "rationale": f"Cascade to graph canonical {candidates_names[canonical_id]}({canonical_id})",
                                "confidence": 0.9,
                                "method": "alias_graph_canonical_cascade"
                            }
                            logger.info(f"Cascade: {candidates_names[existing_canonical]}({existing_canonical}) → {candidates_names[canonical_id]}({canonical_id})")
                        
                        transitive_count += 1
                        
                    elif merge_mapping[canonical_id] != existing_canonical:
                        # Complex conflict: A → D, B → C, but B is alias of A
                        # Solution: Use A (graph canonical) as final canonical
                        canonical_target = merge_mapping[canonical_id]  # D

                        if canonical_id == 'entity_1366':
                            #import pdb; pdb.set_trace()
                            pass
                        
                        graph_canonical_id = None
                        if canonical_id in graph_canonical_dudep:
                            graph_canonical_id = graph_canonical_dudep[canonical_id]

                        if graph_canonical_id and graph_canonical_id == canonical_target:
                            logger.info(
                                f"---Resolving complex conflict: {candidates_names[canonical_id]}({canonical_id}) --[别名包括]--> {candidates_names[duplicate_id]}({duplicate_id}), "
                                f"---where {candidates_names[duplicate_id]}({duplicate_id}) → {candidates_names[existing_canonical]}({existing_canonical}) (LLM) and {candidates_names[canonical_id]}({canonical_id}) → {candidates_names[canonical_target]}({canonical_target}) (LLM). "
                                f"---Using {graph_canonical_id} as final canonical (graph canonical has priority)."
                            )
                            # Override: B → A (use graph canonical)
                            merge_mapping[duplicate_id] = graph_canonical_id
                            metadata[duplicate_id] = {
                                "rationale": f"Graph canonical override: {candidates_names[duplicate_id]}({duplicate_id}) is alias of graph canonical {candidates_names[graph_canonical_id]}({graph_canonical_id})",
                                "confidence": 0.95,
                                "method": "graph_canonical_override"
                            }
                        
                            # Cascade: C → A
                            if existing_canonical != graph_canonical_id and existing_canonical in self.graph.nodes():
                                merge_mapping[existing_canonical] = graph_canonical_id
                                metadata[existing_canonical] = {
                                    "rationale": f"Cascade to graph canonical {candidates_names[graph_canonical_id]}({graph_canonical_id})",
                                    "confidence": 0.9,
                                    "method": "alias_graph_canonical_cascade"
                                }
                                logger.info(f"---Cascade: {candidates_names[existing_canonical]}({existing_canonical}) → {candidates_names[graph_canonical_id]}({graph_canonical_id})")
                        elif graph_canonical_id and graph_canonical_id != canonical_target:
                            logger.info(
                                f"---Resolving complex conflict: {candidates_names[canonical_id]}({canonical_id}) --[别名包括]--> {candidates_names[duplicate_id]}({duplicate_id}), "
                                f"---where {candidates_names[duplicate_id]}({duplicate_id}) → {candidates_names[existing_canonical]}({existing_canonical}) (LLM) and {candidates_names[canonical_id]}({canonical_id}) → {candidates_names[canonical_target]}({canonical_target}) (LLM). "
                                f"---Using {canonical_id} as final canonical (graph canonical has priority)."
                            )
                            #import pdb; pdb.set_trace()


                        else:
                            logger.info(
                                f"Resolving complex conflict: {candidates_names[canonical_id]}({canonical_id}) --[别名包括]--> {candidates_names[duplicate_id]}({duplicate_id}), "
                                f"where {candidates_names[duplicate_id]}({duplicate_id}) → {candidates_names[existing_canonical]}({existing_canonical}) (LLM) and {candidates_names[canonical_id]}({canonical_id}) → {candidates_names[canonical_target]}({canonical_target}) (LLM). "
                                f"Using {canonical_id} as final canonical (graph canonical has priority)."
                            )
                            
                            # Override: B → A (use graph canonical)
                            merge_mapping[duplicate_id] = canonical_id
                            metadata[duplicate_id] = {
                                "rationale": f"Complex conflict resolved: {candidates_names[duplicate_id]}({duplicate_id}) is alias of graph canonical {candidates_names[canonical_id]}({canonical_id})",
                                "confidence": 0.95,
                                "method": "existing_alias_graph_canonical_override"
                            }
                            
                            # Cascade: C → A
                            if existing_canonical != canonical_id and existing_canonical in self.graph.nodes():
                                merge_mapping[existing_canonical] = canonical_id
                                metadata[existing_canonical] = {
                                    "rationale": f"Cascade to graph canonical {candidates_names[canonical_id]}({canonical_id})",
                                    "confidence": 0.9,
                                    "method": "alias_graph_canonical_cascade"
                                }
                                logger.info(f"Cascade: {candidates_names[existing_canonical]}({existing_canonical}) → {candidates_names[canonical_id]}({canonical_id})")
                            
                            # Clear A's decision (A is final canonical, should not merge elsewhere)
                            if canonical_target != canonical_id:
                                # Cascade: D → A
                                if canonical_target in self.graph.nodes():
                                    merge_mapping[canonical_target] = canonical_id
                                    metadata[canonical_target] = {
                                        "rationale": f"Cascade to graph canonical {candidates_names[canonical_id]}({canonical_id})",
                                        "confidence": 0.9,
                                        "method": "alias_graph_canonical_cascade"
                                    }
                                    logger.info(f"Cascade: {candidates_names[canonical_target]}({canonical_target}) → {candidates_names[canonical_id]}({canonical_id})")
                                # Clear A's decision
                                del merge_mapping[canonical_id]
                        
                        complex_resolved_count += 1
            else:
                # B has no LLM decision yet, use graph relationship
                # Check if A has a decision
                if canonical_id in merge_mapping:
                    # A → D, so B should also → D
                    final_canonical = merge_mapping[canonical_id]
                    merge_mapping[duplicate_id] = final_canonical
                    metadata[duplicate_id] = {
                        "rationale": f"Alias of {candidates_names[canonical_id]}({canonical_id}) which merges to {candidates_names[final_canonical]}({final_canonical})",
                        "confidence": 1.0,
                        "method": "existing_alias_transitive"
                    }
                    logger.debug(f"Transitive from graph: {candidates_names[duplicate_id]}({duplicate_id}) → {candidates_names[final_canonical]}({final_canonical}) (via {candidates_names[canonical_id]}({canonical_id}))")
                else:
                    # Simple case: B → A
                    merge_mapping[duplicate_id] = canonical_id
                    metadata[duplicate_id] = {
                        "rationale": "Pre-existing alias relationship in graph",
                        "confidence": 1.0,
                        "method": "existing_alias"
                    }
                alias_count += 1
        
        logger.info(
            f"Added {alias_count} alias relationships from graph. "
            f"Skipped {skipped_count} (already correct). "
            f"Resolved {transitive_count} simple conflicts and {complex_resolved_count} complex conflicts."
        )


        def find_with_path(x):
            """Find root and return the path from x to root.
            
            Returns:
                tuple: (root, path) where path is list of nodes from x to root
            """
            if x not in parent:
                parent[x] = x
                rank[x] = 0
                return x, [x]
            
            path = [x]
            visited = {x}
            current = x
            
            # Traverse to root, detecting cycles
            while parent[current] != current:
                next_node = parent[current]
                
                # Cycle detection
                if next_node in visited:
                    cycle_start = path.index(next_node)
                    cycle = path[cycle_start:] + [next_node]
                    logger.error(
                        f"CYCLE DETECTED: {' -> '.join(cycle)}\n"
                        f"Full path: {' -> '.join(path)} -> {next_node}"
                    )
                    raise ValueError(f"Cycle detected in DSU: {' -> '.join(cycle)}")
                
                visited.add(next_node)
                path.append(next_node)
                current = next_node
            
            return current, path, llm_results
        
        def get_path_to_root(x):
            """Get the path from entity x to its root without modifying structure.
            
            Returns:
                list: Path from x to root (including both x and root)
            """
            if x not in parent:
                return [x]
            
            path = [x]
            visited = {x}
            current = x
            max_depth = len(parent) + 1  # Safety limit
            
            while parent.get(current) != current and len(path) < max_depth:
                next_node = parent[current]
                
                # Cycle detection
                if next_node in visited:
                    cycle_start = path.index(next_node)
                    cycle = path[cycle_start:] + [next_node]
                    logger.warning(
                        f"Cycle in path from {x}: {' -> '.join(cycle)}"
                    )
                    return path + [next_node]  # Return path including cycle point
                
                visited.add(next_node)
                path.append(next_node)
                current = next_node
            
            return path

        #import pdb; pdb.set_trace()
        for dup_id, can_id in merge_mapping.items():
            union(dup_id, can_id)
        final_merge = []
        for dup_id, can_id in merge_mapping.items():
            root = find(dup_id)
            if root != dup_id:
                final_merge_mapping[dup_id] = root
                final_merge.append(
                    {
                        "head_node": {

                        },
                        "relation": "",
                        "tail_nodes_to_dedup": [

                        ],
                        "dedup_results":{
                        "cluster_0": {
                            "member": [
                                self._describe_node(dup_id),
                                self._describe_node(root)
                            ],
                        }
                        }
                    }
                )
            else:
                final_merge_mapping[dup_id] = dup_id
                logger.warning(f"Duplicate and canonical are same: {dup_id}")
        


                #alias_id = u
                #canonical_id = v
                #if 
                #final_merge_mapping[alias_id] = canonical_id
                #metadata[alias_id] = {
                #    "rationale": data.get("rationale", ""),
                #}
        
        #with open("final_merge_mapping_fix1.json", "w") as f:
        #    json.dump(final_merge, f, indent=2,ensure_ascii=False)

        logger.info(f"LLM validated {len(merge_mapping)} merges with representative selection")
        return final_merge_mapping, metadata, llm_results

    def _collect_chunk_context(self, node_id: str, max_length: int = 500) -> str:
        """
        Collect chunk text context for a node.
        
        Args:
            node_id: Node ID
            max_length: Maximum length of chunk text to include (characters)
            
        Returns:
            Formatted chunk context string
        """
        if node_id not in self.graph:
            return "  (Node not found in graph)"
        
        node_data = self.graph.nodes[node_id]
        properties = node_data.get("properties", {})
        chunk_id = properties.get("chunk id") or properties.get("chunk_id")
        
        if not chunk_id:
            return "  (No chunk information)"
        
        chunk_text = self.all_chunks.get(chunk_id)
        if not chunk_text:
            return f"  (Chunk {chunk_id} not found)"
        
        # Truncate if too long
        if len(chunk_text) > max_length:
            chunk_text = chunk_text[:max_length] + "..."
        
        return f"  Source text (chunk id: {chunk_id}): \"{chunk_text}\""

    def _build_head_dedup_prompt_v2(self, node_id_1: str, node_id_2: str) -> str:
        """
        Build improved LLM prompt that asks for representative selection.
        
        Args:
            node_id_1, node_id_2: Entity IDs
            
        Returns:
            Complete prompt text
        """
        # Get entity descriptions
        desc_1 = self._describe_node(node_id_1)
        desc_2 = self._describe_node(node_id_2)
        
        # Get graph context
        graph_context_1 = self._collect_node_context(node_id_1, max_relations=1000)
        graph_context_2 = self._collect_node_context(node_id_2, max_relations=1000)

        # Check if hybrid context is enabled
        config = self.config.construction.semantic_dedup.head_dedup if hasattr(
            self.config.construction.semantic_dedup, 'head_dedup'
        ) else None
        #import pdb; pdb.set_trace()
        use_hybrid_context = False
        if config:
            use_hybrid_context = config.get('use_hybrid_context', False)
        
        if use_hybrid_context:
            chunk_context_1 = self._collect_chunk_context(node_id_1)
            chunk_context_2 = self._collect_chunk_context(node_id_2)
        else:
            chunk_context_1 = "(Not available)"
            chunk_context_2 = "(Not available)"

        # Try to load from config first
        try:
            # 分别传入prompt
            prompt_template = self.config.get_prompt_formatted(
                "head_dedup", 
                "with_representative_selection_fix4",
                entity_1_id=node_id_1,
                entity_1_desc=desc_1,
                graph_context_1=graph_context_1,    # 区分开
                chunk_context_1=chunk_context_1,    # 区分开
                entity_2_id=node_id_2,
                entity_2_desc=desc_2,
                graph_context_2=graph_context_2,
                chunk_context_2=chunk_context_2
            )
            return prompt_template
        except Exception as e:
            error_msg = (
                f"Failed to load head_dedup prompt from config: {e}\n"
                f"Please ensure 'prompts.head_dedup.with_representative_selection' is defined in your config file.\n"
                f"See HEAD_DEDUP_PROMPT_CUSTOMIZATION.md for details."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

    def _parse_coreference_response_v2(self, response: str, prompt: dict, index: int) -> Tuple[dict, str, int]:
        """
        Parse LLM response with representative selection.
        
        Expected format:
        {
        "is_coreferent": true/false,
        "representative": "entity_XXX" or null,
        "rationale": "..."
        }
        
        Args:
            response: LLM JSON response
            prompt: prompt used to generate the response
        Returns:
            Parsed dict with is_coreferent, representative, rationale
        """

        start_time = datetime.datetime.now()
        max_wait_time = 1 * 3600
        attempt_count = 0
        retry_delay = 10  # Initial retry delay
        MAX_RETRY_WAIT_SECONDS = 300  # Max 5 minutes between retries

        response_to_parse = response

        while True:
            attempt_count += 1
            elapsed = (datetime.datetime.now() - start_time).total_seconds()
            if elapsed > max_wait_time:
                logger.error("Max wait time (%ds) exceeded. ", max_wait_time)
                return {
                    "is_coreferent": False,
                    "representative": None,
                    "rationale": "Parse error"
                }, response_to_parse, attempt_count

            try:
                import json_repair
                parsed = json_repair.loads(response_to_parse)
                
                is_coreferent = bool(parsed.get("is_coreferent", False))
                representative = parsed.get("representative")
                rationale = str(parsed.get("rationale", ""))
                
                # Validate
                if is_coreferent and not representative:
                    logger.warning(
                        f"LLM said is_coreferent=true but didn't provide representative. "
                        f"Response: {response_to_parse[:200]}"
                    )
                    # Don't mark as coreferent if no representative
                    is_coreferent = False
                
                if not is_coreferent:
                    representative = None
                
                return {
                    "is_coreferent": is_coreferent,
                    "representative": representative,
                    "rationale": rationale
                }, response_to_parse, attempt_count
                
            except Exception as e:
                logger.warning(f"Failed to parse LLM response: {e}, attempt {attempt_count}")
                logger.debug(f"Response: {response[:500]}...")
             

            retry_delay = min(retry_delay * 1.5, MAX_RETRY_WAIT_SECONDS)
            logger.info(f"Prompt {index} waiting {retry_delay:.0f}s before next attempt...")
            time.sleep(retry_delay)

            response_to_parse = self._concurrent_llm_calls([prompt], type="head_dedup")[0]['response']



    def _merge_head_nodes_with_alias(
        self,
        merge_mapping: Dict[str, str],
        metadata: Dict[str, dict],
        alias_relation: str = "alias_of",
        candidate_pairs: Dict[str, str] = {},
        invalid_nodes: List[Tuple[str, str]] = []
    ) -> Dict[str, int]:
        """
        Merge head nodes using explicit alias relationships.

        Strategy:
        1. Transfer all non-alias edges to representative
        2. Keep duplicate node (don't delete)
        3. Create explicit: duplicate --[alias_of]--> representative
        4. Clean up other edges from duplicate
        5. Mark node roles

        Args:
            merge_mapping: {duplicate_id: canonical_id}
            metadata: Merge metadata from LLM/embedding
            alias_relation: Name of the alias relationship

        Returns:
            Statistics dict with counts
        """
        if not merge_mapping:
            logger.info("No head nodes to merge")
            return {"alias_relations_created": 0, "edges_transferred": 0}

        logger.info(f"Merging {len(merge_mapping)} head nodes with alias relationships...")

        alias_count = 0
        edges_transferred = 0

        for duplicate_id, canonical_id in merge_mapping.items():
            duplicate_name = self.graph.nodes[duplicate_id].get("properties", {}).get("name", "")
            canonical_name = self.graph.nodes[canonical_id].get("properties", {}).get("name", "")
            if (duplicate_id, duplicate_name) in invalid_nodes and (canonical_id, canonical_name) in invalid_nodes:
                logger.warning(f"Invalid nodes: {duplicate_name} -> {canonical_name}")
                continue

            if "entity_109" in duplicate_id or "entity_109" in canonical_id:
                #import pdb; pdb.set_trace()
                pass
                #import pdb; pdb.set_trace()
            # Validate nodes exist
            if duplicate_id not in self.graph or canonical_id not in self.graph:
                logger.warning(f"Nodes not found: {duplicate_id} or {canonical_id}")
                #import pdb; pdb.set_trace()
                continue

            if duplicate_id == canonical_id:
                logger.warning(f"Duplicate and canonical are same: {duplicate_id}")
                #import pdb; pdb.set_trace()
                continue

            try:
                # Step 1: Transfer edges safely (avoiding self-loops)
                out_count = self._reassign_outgoing_edges_safe(
                    duplicate_id, canonical_id, candidate_pairs
                )
                in_count = self._reassign_incoming_edges_safe(
                    duplicate_id, canonical_id
                )
                edges_transferred += (out_count + in_count)

                edge_exists = False
                for source_id, target_id, data in self.graph.edges(duplicate_id, data=True):
                    if data.get("relation") == alias_relation and target_id == canonical_id:
                        #import pdb; pdb.set_trace()
                        edge_exists = True
                        break
                if edge_exists:
                    logger.warning(f"Edge already exists: {duplicate_id} -> {canonical_id}")
                    continue

                # Step 2: Create alias relationship
                self.graph.add_edge(
                    duplicate_id,
                    canonical_id,
                    relation=alias_relation,
                    #source_chunks=[],  # Inferred from deduplication
                    #dedup_metadata=metadata.get(duplicate_id, {}),
                    #created_by="head_deduplication",
                    #timestamp=time.time()
                )
                alias_count += 1

                # Step 3: Remove non-alias edges from duplicate
                self._remove_non_alias_edges(
                    duplicate_id,
                    keep_edge=(duplicate_id, canonical_id)
                )

                # Step 4: Mark node roles
                self.graph.nodes[duplicate_id]["properties"]["node_role"] = "alias"
                self.graph.nodes[duplicate_id]["properties"]["alias_of"] = canonical_id

                canonical_props = self.graph.nodes[canonical_id].get("properties", {})
                canonical_props["node_role"] = "representative"

                # Step 5: Record aliases in canonical node
                if "aliases" not in canonical_props:
                    canonical_props["aliases"] = []
                
                canonical_props["aliases"].append({
                    "alias_id": duplicate_id,
                    "alias_name": self.graph.nodes[duplicate_id]["properties"].get("name", ""),
                    "confidence": metadata.get(duplicate_id, {}).get("confidence", 1.0),
                    "method": metadata.get(duplicate_id, {}).get("method", "unknown"),
                    "timestamp": time.time()
                })
                
                logger.debug(
                    f"Created alias relationship: {duplicate_id} -> {canonical_id} "
                    f"(transferred {out_count + in_count} edges)"
                )
                
            except Exception as e:
                import traceback
                logger.error(f"Error creating alias relationship {duplicate_id} -> {canonical_id}: {e}\n{traceback.format_exc()}")
                continue
        
        logger.info(
            f"Successfully created {alias_count} alias relationships, "
            f"transferred {edges_transferred} edges"
        )
        
        return {
            "alias_relations_created": alias_count,
            "edges_transferred": edges_transferred
        }

    def _merge_head_nodes_with_alias_v2(
        self,
        merge_mapping: Dict[str, str],
        metadata: Dict[str, dict],
        alias_relation: str = "alias_of",
        candidate_pairs: Dict[str, str] = {},
        invalid_nodes: List[Tuple[str, str]] = []
    ) -> Dict[str, int]:
        """
        Merge head nodes using explicit alias relationships.

        Strategy:
        1. Transfer all non-alias edges to representative
        2. Keep duplicate node (don't delete)
        3. Create explicit: duplicate --[alias_of]--> representative
        4. Clean up other edges from duplicate
        5. Mark node roles

        Args:
            merge_mapping: {duplicate_id: canonical_id}
            metadata: Merge metadata from LLM/embedding
            alias_relation: Name of the alias relationship

        Returns:
            Statistics dict with counts
        """
        if not merge_mapping:
            logger.info("No head nodes to merge")
            return {"alias_relations_created": 0, "edges_transferred": 0}

        logger.info(f"Merging {len(merge_mapping)} head nodes with alias relationships...")

        alias_count = 0
        edges_transferred = 0

        for duplicate_id, canonical_id in merge_mapping.items():
            duplicate_name = self.graph.nodes[duplicate_id].get("properties", {}).get("name", "")
            canonical_name = self.graph.nodes[canonical_id].get("properties", {}).get("name", "")
            if (duplicate_id, duplicate_name) in invalid_nodes and (canonical_id, canonical_name) in invalid_nodes:
                logger.warning(f"Invalid nodes: {duplicate_name} -> {canonical_name}")
                continue

            if "entity_109" in duplicate_id and "entity_1099" not in duplicate_id \
                or "entity_109" in canonical_id and "entity_1099" not in canonical_id:
                #import pdb; pdb.set_trace()
                pass
                #import pdb; pdb.set_trace()
            # Validate nodes exist
            if duplicate_id not in self.graph or canonical_id not in self.graph:
                logger.warning(f"Nodes not found: {duplicate_id} or {canonical_id}")
                #import pdb; pdb.set_trace()
                continue

            if duplicate_id == canonical_id:
                logger.warning(f"Duplicate and canonical are same: {duplicate_id}")
                #import pdb; pdb.set_trace()
                continue

            try:
                # Step 1: Transfer edges safely (avoiding self-loops)
                out_count, skip_flag_out = self._reassign_outgoing_edges_safe_v2(
                    duplicate_id, canonical_id, candidate_pairs
                )
                in_count, skip_flag_in = self._reassign_incoming_edges_safe_v2(
                    duplicate_id, canonical_id
                )
                edges_transferred += (out_count + in_count)


                if skip_flag_out or skip_flag_in:
                    logger.warning(
                        f"Skipping merging to avoid self-loop: {duplicate_id} -> {canonical_id} | "
                        f"skip_flag_out: {skip_flag_out}, skip_flag_in: {skip_flag_in}"
                        )
                    #import pdb; pdb.set_trace()
                    continue

                # Step 2: Create alias relationship
                self.graph.add_edge(
                    duplicate_id,
                    canonical_id,
                    relation=alias_relation,
                    #source_chunks=[],  # Inferred from deduplication
                    #dedup_metadata=metadata.get(duplicate_id, {}),
                    #created_by="head_deduplication",
                    #timestamp=time.time()
                )
                alias_count += 1

                # Step 3: Remove non-alias edges from duplicate
                self._remove_non_alias_edges(
                    duplicate_id,
                    keep_edge=(duplicate_id, canonical_id)
                )

                # Step 4: Mark node roles
                self.graph.nodes[duplicate_id]["properties"]["node_role"] = "alias"
                self.graph.nodes[duplicate_id]["properties"]["alias_of"] = canonical_id

                canonical_props = self.graph.nodes[canonical_id].get("properties", {})
                canonical_props["node_role"] = "representative"

                # Step 5: Record aliases in canonical node
                if "aliases" not in canonical_props:
                    canonical_props["aliases"] = []
                
                canonical_props["aliases"].append({
                    "alias_id": duplicate_id,
                    "alias_name": self.graph.nodes[duplicate_id]["properties"].get("name", ""),
                    "confidence": metadata.get(duplicate_id, {}).get("confidence", 1.0),
                    "method": metadata.get(duplicate_id, {}).get("method", "unknown"),
                    "timestamp": time.time()
                })
                
                logger.debug(
                    f"Created alias relationship: {duplicate_id} -> {canonical_id} "
                    f"(transferred {out_count + in_count} edges)"
                )
                
            except Exception as e:
                import traceback
                logger.error(f"Error creating alias relationship {duplicate_id} -> {canonical_id}: {e}\n{traceback.format_exc()}")
                continue
        
        logger.info(
            f"Successfully created {alias_count} alias relationships, "
            f"transferred {edges_transferred} edges"
        )
        
        return {
            "alias_relations_created": alias_count,
            "edges_transferred": edges_transferred
        }

    def _resolve_canonical_chain(self, node_id: str, merge_mapping: Dict[str, str] = None) -> str:
        """
        Resolve the canonical chain for a node by following merge mappings.
        Returns the final canonical node after following all alias relationships.

        Args:
            node_id: The node to resolve
            merge_mapping: Optional merge mapping to use for resolution

        Returns:
            The final canonical node ID
        """
        if merge_mapping is None:
            merge_mapping = {}

        visited = set()
        current = node_id

        while current in merge_mapping and current not in visited:
            visited.add(current)
            current = merge_mapping[current]

        return current

    def _merge_exact_and_semantic_mappings(
        self,
        exact_merge_mapping: Dict[str, str],
        semantic_merge_mapping: Dict[str, str],
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Merge exact and semantic merge mappings, resolving canonical chains.
        Handles cases where semantic mappings affect nodes that were canonical in the exact phase.

        Args:
            exact_merge_mapping: {duplicate_id: canonical_id} from exact matching phase
            semantic_merge_mapping: {duplicate_id: canonical_id} from semantic matching phase

        Returns:
            Combined merge mapping with resolved canonical chains
        """
        # First, resolve all canonical targets in semantic_merge_mapping
        resolved_semantic_mapping = {}
        for dup_id, can_id in semantic_merge_mapping.items():
            resolved_semantic_mapping[dup_id] = self._resolve_canonical_chain(can_id, semantic_merge_mapping)

        # Create a mapping from old canonical to new canonical for updates
        canonical_updates = {}
        for dup_id, resolved_can_id in resolved_semantic_mapping.items():
            if dup_id in exact_merge_mapping.values():  # This was a canonical in exact phase
                canonical_updates[dup_id] = resolved_can_id

        # Update exact_merge_mapping: replace old canonicals with resolved ones
        updated_exact_mapping = {}
        for dup_id, can_id in exact_merge_mapping.items():
            if can_id in canonical_updates:
                updated_exact_mapping[dup_id] = canonical_updates[can_id]
            else:
                updated_exact_mapping[dup_id] = can_id

        # Combine mappings: exact mappings take precedence, then semantic
        final_merge_mapping = dict(updated_exact_mapping)
        final_merge_mapping.update(resolved_semantic_mapping)

        return final_merge_mapping, dict(updated_exact_mapping)

    def _reassign_outgoing_edges_safe(
        self, 
        source_id: str, 
        target_id: str,
        candidate_pairs: Dict[str, str]
    ) -> int:
        """
        Safely transfer outgoing edges, avoiding self-loops.
        
        Args:
            source_id: Source node (will become alias)
            target_id: Target node (representative)
            
        Returns:
            Number of edges transferred
        """
        outgoing = list(self.graph.out_edges(source_id, keys=True, data=True))
        transferred = 0
        
        for _, tail_id, key, data in outgoing:
            # Skip edges that would create self-loops
            if tail_id == target_id or tail_id == source_id:
                logger.warning(
                    f"Skipping edge to avoid self-loop: {source_id} -> {tail_id} "
                    f"(relation: {data.get('relation')})"
                )
                continue
            
            # Check if similar edge already exists
            edge_exists, existing_key = self._find_similar_edge(target_id, tail_id, data)
            
            if not edge_exists:
                # Add new edge
                self.graph.add_edge(target_id, tail_id, **copy.deepcopy(data))
                transferred += 1
                logger.info(
                    f"Transferred edge: {target_id} -> {tail_id} ({candidate_pairs[target_id]}({(candidate_pairs[source_id])}) -> ({candidate_pairs[tail_id]})"
                    f"(relation: {data.get('relation')})"
                )
            else:
                # Merge chunk information
                self._merge_edge_chunks(target_id, tail_id, existing_key, data)
                logger.debug(
                    f"Merged chunks for existing edge: {target_id} -> {tail_id}"
                )
        
        return transferred

    def _reassign_incoming_edges_safe(
        self, 
        source_id: str, 
        target_id: str
    ) -> int:
        """
        Safely transfer incoming edges, avoiding self-loops.
        
        Args:
            source_id: Source node (will become alias)
            target_id: Target node (representative)
            
        Returns:
            Number of edges transferred
        """
        incoming = list(self.graph.in_edges(source_id, keys=True, data=True))
        transferred = 0
        
        for head_id, _, key, data in incoming:
            # Skip edges that would create self-loops
            if head_id == target_id or head_id == source_id:
                logger.debug(
                    f"Skipping edge to avoid self-loop: {head_id} -> {source_id} "
                    f"(relation: {data.get('relation')})"
                )
                continue
            
            # Check if similar edge already exists
            edge_exists, existing_key = self._find_similar_edge(head_id, target_id, data)
            
            if not edge_exists:
                # Add new edge
                self.graph.add_edge(head_id, target_id, **copy.deepcopy(data))
                transferred += 1
                logger.debug(
                    f"Transferred edge: {head_id} -> {target_id} "
                    f"(relation: {data.get('relation')})"
                )
            else:
                # Merge chunk information
                self._merge_edge_chunks(head_id, target_id, existing_key, data)
                logger.debug(
                    f"Merged chunks for existing edge: {head_id} -> {target_id}"
                )
        
        return transferred

    def _reassign_outgoing_edges_safe_v2(
        self, 
        source_id: str, 
        target_id: str,
        candidate_pairs: Dict[str, str]
    ) -> Tuple[int,bool]:
        """
        Safely transfer outgoing edges, avoiding self-loops.
        
        Args:
            source_id: Source node (will become alias)
            target_id: Target node (representative)
            
        Returns:
            Number of edges transferred
        """
        outgoing = list(self.graph.out_edges(source_id, keys=True, data=True))
        transferred = 0
        
        skip_flag = False

        for _, tail_id, key, data in outgoing:
            # Skip edges that would create self-loops
            if tail_id == target_id and data.get("relation") != "等同于":
                skip_flag = True
                logger.warning(
                    f"Besides relation '等同于', "
                    f"There is a another relation of {self.graph.nodes[source_id].get('properties', {}).get('name', source_id)} -> {self.graph.nodes[tail_id].get('properties', {}).get('name', tail_id)} -> {data.get('relation')}")
                logger.warning(
                    f"Skipping merging to avoid self-loop: {source_id} -> {tail_id} "
                    f"(relation: {data.get('relation')})"
                )
                break

        if skip_flag:
            return transferred, skip_flag

        for _, tail_id, key, data in outgoing:
            # Skip edges that would create self-loops
            if tail_id == target_id or tail_id == source_id:
                logger.warning(
                    f"Skipping edge to avoid self-loop: {source_id} -> {tail_id} "
                    f"(relation: {data.get('relation')})"
                )
                if tail_id == target_id and data.get("relation") == "等同于":
                    skip_flag = True
                continue
            
            # Check if similar edge already exists
            edge_exists, existing_key = self._find_similar_edge(target_id, tail_id, data)
            
            if not edge_exists:
                # Add new edge
                self.graph.add_edge(target_id, tail_id, **copy.deepcopy(data))
                transferred += 1
                logger.info(
                    f"Transferred edge: {target_id} -> {tail_id} ({candidate_pairs[target_id]}({(candidate_pairs[source_id])}) -> ({candidate_pairs[tail_id]})"
                    f"(relation: {data.get('relation')})"
                )
            else:
                # Merge chunk information
                self._merge_edge_chunks(target_id, tail_id, existing_key, data)
                logger.debug(
                    f"Merged chunks for existing edge: {target_id} -> {tail_id}"
                )
        
        return transferred, skip_flag

    def _reassign_incoming_edges_safe_v2(
        self, 
        source_id: str, 
        target_id: str
    ) -> Tuple[int,bool]:
        """
        Safely transfer incoming edges, avoiding self-loops.
        
        Args:
            source_id: Source node (will become alias)
            target_id: Target node (representative)
            
        Returns:
            Number of edges transferred
        """
        incoming = list(self.graph.in_edges(source_id, keys=True, data=True))
        transferred = 0

        skip_flag = False

        for head_id, _, key, data in incoming:
            # Skip edges that would create self-loops
            if head_id == target_id and data.get("relation") != "等同于":
                skip_flag = True
                logger.warning(
                    f"Besides relation '等同于', "
                    f"There is a another relation of {self.graph.nodes[source_id].get('properties', {}).get('name', source_id)} -> {self.graph.nodes[target_id].get('properties', {}).get('name', target_id)} -> {data.get('relation')}")
                logger.warning(
                    f"Skipping merging to avoid self-loop: {source_id} -> {target_id} | "
                    f"(relation: {data.get('relation')})"
                )
                break

        if not skip_flag:
            return transferred, skip_flag

        for head_id, _, key, data in incoming:
            # Skip edges that would create self-loops
            if head_id == target_id or head_id == source_id:
                logger.debug(
                    f"Skipping edge to avoid self-loop: {head_id} -> {source_id} "
                    f"(relation: {data.get('relation')})"
                )
                continue
            
            # Check if similar edge already exists
            edge_exists, existing_key = self._find_similar_edge(head_id, target_id, data)
            
            if not edge_exists:
                # Add new edge
                self.graph.add_edge(head_id, target_id, **copy.deepcopy(data))
                transferred += 1
                logger.debug(
                    f"Transferred edge: {head_id} -> {target_id} "
                    f"(relation: {data.get('relation')})"
                )
            else:
                # Merge chunk information
                self._merge_edge_chunks(head_id, target_id, existing_key, data)
                logger.debug(
                    f"Merged chunks for existing edge: {head_id} -> {target_id}"
                )
        
        return transferred, skip_flag

    def _remove_non_alias_edges(
        self, 
        node_id: str, 
        keep_edge: Tuple[str, str]
    ):
        """
        Remove all edges from a node except the alias_of edge.
        
        Args:
            node_id: Node to clean up
            keep_edge: Edge to keep (source, target) - the alias_of edge
        """
        # Remove all outgoing edges except alias_of
        outgoing = list(self.graph.out_edges(node_id, keys=True))
        for _, tail_id, key in outgoing:
            if (node_id, tail_id) != keep_edge:
                self.graph.remove_edge(node_id, tail_id, key)
                logger.info(f"Removed outgoing edge: {self.graph.nodes[node_id].get('properties', {}).get('name', node_id)} -> {self.graph.nodes[tail_id].get('properties', {}).get('name', tail_id)}")
        
        # Remove all incoming edges
        incoming = list(self.graph.in_edges(node_id, keys=True))
        for head_id, _, key in incoming:
            self.graph.remove_edge(head_id, node_id, key)
            logger.info(f"Removed incoming edge: {self.graph.nodes[head_id].get('properties', {}).get('name', head_id)} -> {self.graph.nodes[node_id].get('properties', {}).get('name', node_id)}")

    def _load_intermediate_dedup_head_results(self, intermediate_results_path: str):
        with open(intermediate_results_path, 'r', encoding='utf-8') as f:
            intermediate_results = json.load(f)

        self.dataset_name = intermediate_results['dataset']
        self.config = intermediate_results['config']
        self.phases = intermediate_results['phases']

        phase1_candidates = self.phases.get('phase1_candidates', {})
        phase3_semantic = self.phases.get('phase3_semantic', {})
        return phase1_candidates, phase3_semantic


    def deduplicate_heads_with_llm_v2(
        self,
        enable_semantic: bool = True,
        similarity_threshold: float = 0.85,
        max_candidates: int = 1000,
        alias_relation: str = "等同于",
        load_llm_results :bool = False,
        return_dedup_results: bool = False,
        load_intermediate_results: bool = False
    ) -> Dict[str, Any]:
        """
        Main entry: Head deduplication with LLM-driven representative selection.

        Key improvements:
        1. LLM decides which entity should be the representative (not code heuristics)
        2. Uses alias relationships (doesn't delete duplicate nodes)
        3. No self-loops
        4. Semantic correctness

        Args:
            enable_semantic: Enable semantic deduplication
            similarity_threshold: Embedding similarity threshold for candidate generation
            max_candidates: Maximum candidate pairs
            alias_relation: Name of alias relationship
            load_llm_results: Load pre-computed LLM results instead of generating new ones
            return_dedup_results: If True, return dedup results in entity_attribution format instead of modifying graph

        Returns:
            Statistics dict or dedup results list (depending on return_dedup_results)
        """
        logger.info("=" * 70)
        logger.info("Head Deduplication (LLM-Driven + Alias Relationships)")
        logger.info("=" * 70)

        self.ori_graph = copy.deepcopy(self.graph)
        #import pdb; pdb.set_trace()
        # Get configuration
        config = self.config.construction.semantic_dedup.head_dedup if hasattr(
            self.config.construction.semantic_dedup, 'head_dedup'
        ) else None
        
        if not config or not config.get('enabled', False):
            logger.info("Head deduplication is disabled in config")
            return {"enabled": False}
        #import pdb; pdb.set_trace()
        # Check if intermediate results should be saved
        save_intermediate = config.get('save_intermediate_results', False)

        use_llm_validation = config.get("use_llm_validation", False)

        if load_intermediate_results:
            intermediate_results = self._load_intermediate_results(config.get('intermediate_results_path', None))
        
        # Initialize intermediate results collector
        intermediate_results = {
            "dataset": self.dataset_name,
            "config": {
                "enable_semantic": enable_semantic,
                "similarity_threshold": similarity_threshold,
                "use_llm_validation": use_llm_validation,
                "max_candidates": max_candidates,
                "candidate_similarity_threshold": config.get('candidate_similarity_threshold', 0.75)
            },
            "phases": {}
        } if save_intermediate else None


        start_time = time.time()
        
        # Phase 1: Collect candidates
        logger.info("\n[Phase 1/4] Collecting head candidates...")
        candidates, candidates_names = self._collect_head_candidates()
        logger.info(f"✓ Found {len(candidates)} entity nodes")
        
        # Record candidates info if saving intermediate results
        if save_intermediate:
            intermediate_results["phases"]["phase1_candidates"] = {
                "total_candidates": len(candidates),
                "candidates": [{
                    "node_id": node_id,
                    "name": self.graph.nodes[node_id].get("properties", {}).get("name", ""),
                    "description": self.graph.nodes[node_id].get("properties", {}).get("description", "")[:200]
                } for node_id in candidates] if candidates else []  # Store first 10 samples
            }

        # Phase 2: Exact match
        logger.info("\n[Phase 2/4] Exact match deduplication...")
        exact_merge_mapping, invalid_nodes = self._deduplicate_heads_exact(candidates)
        logger.info(f"✓ Identified {len(exact_merge_mapping)} exact matches")
        
#        # Record exact match results
#        if save_intermediate:
#            intermediate_results["phases"]["phase2_exact_match"] = {
#                "total_matches": len(exact_merge_mapping),
#                "merge_pairs": [{
#                    "duplicate_id": dup_id,
#                    "duplicate_name": self.graph.nodes.get(dup_id, {}).get("properties", {}).get("name", ""),
#                    "canonical_id": can_id,
#                    "canonical_name": self.graph.nodes.get(can_id, {}).get("properties", {}).get("name", "")
#                } for dup_id, can_id in list(exact_merge_mapping.items())[:50]]  # Store first 50 pairs
#            }

        # For exact matches, use simple heuristic (ID order) since names are identical
        exact_stats = self._merge_head_nodes_with_alias(
            exact_merge_mapping,
            {},
            alias_relation,
            candidates_names,
            invalid_nodes
        )
        logger.info(f"✓ Created {exact_stats['alias_relations_created']} alias relationships")
        
        # Phase 3: Semantic deduplication with LLM
        semantic_stats = {"alias_relations_created": 0, "edges_transferred": 0}
        
        if enable_semantic:
            logger.info("\n[Phase 3/4] Semantic deduplication (LLM-driven)...")
            
            remaining_nodes = [
                node_id for node_id in candidates
                if node_id not in exact_merge_mapping and 
                node_id in self.graph and
                self.graph.nodes[node_id].get("properties", {}).get("node_role") != "alias"
            ]
            logger.info(f"  Remaining nodes: {len(remaining_nodes)}")
            
            if len(remaining_nodes) >= 2:
                candidate_pairs = None
                if not load_llm_results:
                    # Generate candidate pairs
                    candidate_pairs = self._generate_semantic_candidates(
                        remaining_nodes,
                        candidates_names,
                        max_candidates=max_candidates,
                        similarity_threshold=0.75  # Pre-filtering threshold
                    )
                    logger.info(f"✓ Generated {len(candidate_pairs)} candidate pairs")
                
                    # Record candidate pairs
                    if save_intermediate:
                        intermediate_results["phases"]["phase3_semantic"] = {
                            "remaining_nodes": len(remaining_nodes),
                            "candidate_pairs_generated": len(candidate_pairs),
                            "validation_method": "llm" if use_llm_validation else "embedding",
                            "sample_candidate_pairs": [{
                                "node_id_1": pair[0],
                                "node_name_1": self.graph.nodes.get(pair[0], {}).get("properties", {}).get("name", ""),
                                "node_id_2": pair[1],
                                "node_name_2": self.graph.nodes.get(pair[1], {}).get("properties", {}).get("name", ""),
                                "embedding_similarity": float(pair[2])
                            } for pair in candidate_pairs[:20]]  # Store first 20 pairs
                        }
                elif save_intermediate:
                    # Initialize phase3_semantic when loading LLM results
                    intermediate_results["phases"]["phase3_semantic"] = {
                        "remaining_nodes": len(remaining_nodes),
                        "candidate_pairs_generated": 0,
                        "validation_method": "llm",
                        "load_llm_results": True
                    }
                

                if load_llm_results or candidate_pairs:
                    # LLM validation with representative selection
                    logger.info("  Using LLM to validate AND select representatives...")
                    semantic_merge_mapping, metadata, llm_results = self._validate_candidates_with_llm_v2(
                        candidate_pairs if candidate_pairs is not None else [],
                        similarity_threshold,
                        load_llm_results,
                        candidates_names
                    )
                    #import pdb; pdb.set_trace()
                    logger.info(f"✓ LLM identified {len(semantic_merge_mapping)} semantic matches")
                    
                    #import pdb; pdb.set_trace()
                    # Record semantic validation results
                    if save_intermediate:
                        intermediate_results["phases"]["phase3_semantic"]["validation_results"] = {
                            "total_matches": len(semantic_merge_mapping),
                            "merge_decisions": [{
                                "duplicate_name": self.graph.nodes.get(dup_id, {}).get("properties", {}).get("name", ""),
                                "canonical_name": self.graph.nodes.get(can_id, {}).get("properties", {}).get("name", ""),
                                "metadata": metadata.get(dup_id, {})
                            } for dup_id, can_id in list(semantic_merge_mapping.items())]  # Store first 50
                        }
                        intermediate_results["phases"]["phase3_semantic"]["llm_results"] = llm_results

                    # Merge exact and semantic mappings with resolved canonical chains
                    final_merge_mapping, updated_exact_mapping = self._merge_exact_and_semantic_mappings(
                        exact_merge_mapping,
                        semantic_merge_mapping,
                    )

                    exact_merge_mapping = updated_exact_mapping

                    #import pdb; pdb.set_trace()

                    # Apply all merges using the first phase function (handles both exact and semantic)
                    semantic_stats = self._merge_head_nodes_with_alias(
                        updated_exact_mapping,
                        {},
                        alias_relation,
                        candidates_names,
                        invalid_nodes
                    )

                    # Apply merges
                    semantic_stats = self._merge_head_nodes_with_alias_v2(
                        semantic_merge_mapping,
                        metadata,
                        alias_relation,
                        candidates_names,
                        invalid_nodes
                    )
                    logger.info(f"✓ Created {semantic_stats['alias_relations_created']} alias relationships")
        else:
            logger.info("\n[Phase 3/4] Semantic deduplication skipped")
        
        # Phase 4: Validation
        logger.info("\n[Phase 4/4] Validating graph integrity...")
        issues = self.validate_graph_integrity_with_alias(candidates_names)
        
        if any(v for v in issues.values() if v):
            logger.warning(f"⚠ Found integrity issues: {issues}")
        else:
            logger.info("✓ Graph integrity validated")
        
        elapsed_time = time.time() - start_time
        
        # Statistics
        final_main_count = len([
            n for n, d in self.graph.nodes(data=True)
            if d.get("label") == "entity" and
            d.get("properties", {}).get("node_role") != "alias"
        ])
        
        alias_count = len([
            n for n, d in self.graph.nodes(data=True)
            if d.get("properties", {}).get("node_role") == "alias"
        ])
        
        stats = {
            "total_candidates": len(candidates),
            "exact_alias_created": exact_stats["alias_relations_created"],
            "semantic_alias_created": semantic_stats["alias_relations_created"],
            "total_alias_created": (
                exact_stats["alias_relations_created"] + 
                semantic_stats["alias_relations_created"]
            ),
            "initial_entity_count": len(candidates),
            "final_main_entity_count": final_main_count,
            "final_alias_count": alias_count,
            "elapsed_time_seconds": elapsed_time,
            "integrity_issues": issues,
            "method": "llm_driven_v2"
        }
        
        logger.info("\n" + "=" * 70)
        logger.info("Head Deduplication Completed (LLM-Driven + Alias)")
        logger.info("=" * 70)
        logger.info(f"Summary:")
        logger.info(f"  - Initial entities: {stats['initial_entity_count']}")
        logger.info(f"  - Final main entities: {stats['final_main_entity_count']}")
        logger.info(f"  - Final alias entities: {stats['final_alias_count']}")
        logger.info(f"  - Total alias relations: {stats['total_alias_created']}")
        logger.info(f"  - Time elapsed: {elapsed_time:.2f}s")
        logger.info(f"  - Method: LLM-driven representative selection ✓")
        logger.info("=" * 70)
        
        # Save intermediate results to file
        if save_intermediate and intermediate_results:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = config.get('intermediate_results_path', None)
            
            if not output_path:
                output_path = f"output/dedup_intermediate/{self.dataset_name}_head_dedup_{timestamp}.json"
            else:
                # If path is a directory, add filename
                if output_path.endswith('/'):
                    output_path = f"{output_path}{self.dataset_name}_head_dedup_{timestamp}.json"
                else:
                    # Add _head suffix
                    base, ext = os.path.splitext(output_path)
                    output_path = f"{base}_head_{timestamp}{ext}"
            
            # Ensure directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # Add summary statistics
            intermediate_results["summary"] = stats
            
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(intermediate_results, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved head deduplication intermediate results to: {output_path}")
                logger.info(f"Summary: {intermediate_results['summary']}")
            except Exception as e:
                logger.warning(f"Failed to save intermediate results: {e}")

        # Export for review if configured
        if config.get('export_review', False):
            review_path = os.path.join(
                config.get('review_output_dir', 'output/review'),
                f"head_merge_{self.dataset_name}_{int(time.time())}.csv"
            )
            min_conf, max_conf = config.get('review_confidence_range', [0.70, 0.90])
            self.export_head_merge_candidates_for_review(
                output_path=review_path,
                min_confidence=min_conf,
                max_confidence=max_conf
            )

        # If return_dedup_results is True, format and return results instead of just modifying graph
        if return_dedup_results:
            head_dedup_results = self._format_head_dedup_results_for_output(
                candidates, exact_merge_mapping, semantic_merge_mapping, metadata, stats
            )
            return head_dedup_results

        return stats

    def _format_head_dedup_results_for_output(self, candidates: List[str], exact_merge_mapping: Dict[str, str],
                                             semantic_merge_mapping: Dict[str, str], metadata: Dict[str, Any],
                                             stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format head deduplication results in a format similar to final_merge_mapping_fix1.json"""
        output = []

        # Group all dedup results by cluster
        cluster_results = {}
        cluster_idx = 0

        # Use _describe_node method for consistent formatting

        # Process exact matches - each pair becomes a cluster
        for dup_id, rep_id in exact_merge_mapping.items():
            cluster_key = f"cluster_{cluster_idx}"
            cluster_results[cluster_key] = {
                "member": [self._describe_node(dup_id), self._describe_node(rep_id)]
            }
            cluster_idx += 1

        # Process semantic matches - each pair becomes a cluster
        for dup_id, rep_id in semantic_merge_mapping.items():
            #import pdb; pdb.set_trace()
            cluster_key = f"cluster_{cluster_idx}"
            cluster_results[cluster_key] = {
                "member": [self._describe_node(dup_id), self._describe_node(rep_id)]
            }
            cluster_idx += 1

        # Create result item in the format similar to final_merge_mapping_fix1.json
        head_dedup_item = {
            "head_node": {},
            "relation": "",
            "tail_nodes_to_dedup": [],
            "dedup_results": cluster_results,
            "dedup_stats": stats
        }

        output.append(head_dedup_item)
        return output

    def validate_graph_integrity_with_alias(self, candidates_names: Dict[str, str]) -> Dict[str, List]:
        """
        Validate graph integrity after alias-based deduplication.
        
        Modified rules:
        - Alias nodes are NOT considered orphans (they have alias_of edge)
        - Self-loops should not exist
        - All alias_of edges should point to representative nodes
        
        Returns:
            Dict with lists of issues
        """
        issues = {
            "orphan_nodes": [],
            "self_loops": [],
            "dangling_references": [],
            "invalid_alias_nodes": [],
            "alias_chains": []
        }
        
        # Check orphan nodes (excluding valid alias nodes)
        for node_id, data in self.graph.nodes(data=True):
            if data.get("label") == "entity":
                in_degree = self.graph.in_degree(node_id)
                out_degree = self.graph.out_degree(node_id)
                node_role = data.get("properties", {}).get("node_role")
                
                # Alias nodes with only alias_of edge are valid
                if node_role == "alias":
                    if out_degree == 1:
                        out_edges = list(self.graph.out_edges(node_id, data=True))
                        if out_edges[0][2].get("relation") == "alias_of" or out_edges[0][2].get("relation") == "等同于" or out_edges[0][2].get("relation") == "别名包括":
                            continue  # Valid alias node
                    #import pdb; pdb.set_trace()
                    # Invalid alias node
                    issues["invalid_alias_nodes"].append(
                        (node_id, f"in={in_degree}, out={out_degree}")
                    )
                elif in_degree == 0 and out_degree == 0:
                    issues["orphan_nodes"].append(node_id)
        
        # Check self-loops (should not exist with alias method!)
        for u, v in self.graph.edges():
            if u == v:
                #import pdb; pdb.set_trace()
                issues["self_loops"].append((u, v))
        
        # Check alias chains (alias pointing to alias)
        for node_id, data in self.graph.nodes(data=True):
            if data.get("properties", {}).get("node_role") == "alias":
                out_edges = list(self.graph.out_edges(node_id, data=True))
                for _, target_id, edge_data in out_edges:
                    if edge_data.get("relation") == "alias_of":
                        target_data = self.graph.nodes.get(target_id, {})
                        target_role = target_data.get("properties", {}).get("node_role")
                        if target_role == "alias":
                            issues["alias_chains"].append((node_id, target_id))
        
        # Check dangling references
        for u, v, data in self.graph.edges(data=True):
            if u not in self.graph.nodes:
                issues["dangling_references"].append(("head", u, v))
            if v not in self.graph.nodes:
                issues["dangling_references"].append(("tail", u, v))
        
        return issues

    # Utility functions for working with aliases

    def is_alias_node(self, node_id: str) -> bool:
        """Check if a node is an alias node."""
        if node_id not in self.graph:
            return False
        return (
            self.graph.nodes[node_id]
            .get("properties", {})
            .get("node_role") == "alias"
        )

    def get_main_entities_only(self) -> List[str]:
        """Get only main entities (excluding aliases)."""
        return [
            node_id
            for node_id, data in self.graph.nodes(data=True)
            if data.get("label") == "entity" and
            data.get("properties", {}).get("node_role") != "alias"
        ]

    def resolve_alias(self, node_id: str) -> str:
        """
        Resolve alias to main entity.
        If node is an alias, return its representative; otherwise return itself.
        """
        if not self.is_alias_node(node_id):
            return node_id
        
        # Follow alias_of edge
        for _, target_id, data in self.graph.out_edges(node_id, data=True):
            if data.get("relation") == "alias_of":
                return target_id
        
        return node_id  # Fallback

    def get_all_aliases(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Get all aliases for a given entity.
        
        Args:
            entity_id: Main entity ID
            
        Returns:
            List of alias info dicts
        """
        if entity_id not in self.graph:
            return []
        
        properties = self.graph.nodes[entity_id].get("properties", {})
        return properties.get("aliases", [])

    def export_alias_mapping(self, output_path: str):
        """
        Export alias mapping for external use.
        
        Format: CSV with columns:
        - alias_id, alias_name, main_entity_id, main_entity_name, confidence, method
        """
        import csv
        
        rows = []
        
        for node_id, data in self.graph.nodes(data=True):
            if data.get("label") != "entity":
                continue
            
            props = data.get("properties", {})
            if props.get("node_role") == "representative":
                main_entity_id = node_id
                main_entity_name = props.get("name", "")
                
                for alias_info in props.get("aliases", []):
                    rows.append({
                        "alias_id": alias_info["alias_id"],
                        "alias_name": alias_info["alias_name"],
                        "main_entity_id": main_entity_id,
                        "main_entity_name": main_entity_name,
                        "confidence": alias_info.get("confidence", 1.0),
                        "method": alias_info.get("method", "unknown")
                    })
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                "alias_id", "alias_name",
                "main_entity_id", "main_entity_name",
                "confidence", "method"
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        logger.info(f"✓ Exported {len(rows)} alias mappings to {output_path}")


    def build_knowledge_graph(self, corpus):
        logger.info(f"========{'Start Building':^20}========")
        logger.info(f"{'➖' * 30}")
        
        with open(corpus, 'r', encoding='utf-8') as f:
            documents = json_repair.load(f)
        
        self.process_all_documents(documents)
        
        logger.info(f"All Process finished, token cost: {self.token_len}")
        
        self.save_chunks_to_file()
        
        output = self.format_output()
        
        json_output_path = f"output/graphs/{self.dataset_name}_new.json"
        os.makedirs("output/graphs", exist_ok=True)
        with open(json_output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        logger.info(f"Graph saved to {json_output_path}")
        
        return output
