import copy
import json
import os
import threading
import time
from concurrent import futures
from typing import Any, Dict, List, Tuple
from collections import defaultdict


import nanoid
import networkx as nx
import tiktoken
import json_repair

from config import get_config
from utils import call_llm_api, graph_processor, tree_comm
from utils.logger import logger

import numpy as np

DEFAULT_SEMANTIC_DEDUP_PROMPT = (
    "You are a knowledge graph curation assistant performing entity deduplication.\n"
    "All listed triples share the same head entity and relation.\n\n"
    "Head entity: {head}\n"
    "Relation: {relation}\n\n"
    "Head contexts:\n{head_context}\n\n"
    "Candidate tails:\n"
    "{candidates}\n\n"
    "TASK: Identify which tails are COREFERENT (refer to the exact same entity/concept).\n\n"
    "⚠️  CRITICAL WARNING - Common Mistake:\n"
    "DO NOT merge tails just because they all satisfy the same relation with the head.\n"
    "For example, if relation = 'common locations include' and tails = ['liver', 'kidney', 'lung'],\n"
    "these are THREE DIFFERENT organs, not coreferent. Keep them separate!\n\n"
    "MERGE CONDITIONS (all must be true):\n"
    "✓ COREFERENCE: Two expressions denote the SAME specific entity/concept\n"
    "  • 'NYC' and 'New York City' → SAME city (merge)\n"
    "  • 'H2O' and '水' → SAME substance (merge)\n"
    "  • '10 cm' and '100 mm' → SAME measurement (merge)\n"
    "  • '跟腱' and 'Achilles tendon' → SAME anatomical structure (merge)\n\n"
    "✗ DIFFERENT ENTITIES: Each describes a distinct entity/concept\n"
    "  • '肌腱' (tendon) and '韧带' (ligament) → DIFFERENT structures (do NOT merge)\n"
    "  • '软骨' (cartilage) and '骨骼' (bone) → DIFFERENT tissues (do NOT merge)\n"
    "  • '肩关节' (shoulder) and '跟腱' (Achilles tendon) → DIFFERENT locations (do NOT merge)\n"
    "  • 'spatial resolution' and 'edge sharpness' → DIFFERENT metrics (do NOT merge)\n\n"
    "GUIDING PRINCIPLES:\n"
    "1. IDENTITY TEST: Merge ONLY if the two tails refer to exactly the same real-world entity.\n"
    "   Ask: \"Are these two names/descriptions for the SAME thing?\"\n"
    "   - If they are different instances/examples/members → do NOT merge\n"
    "   - If they are different types/categories → do NOT merge\n"
    "   - If they are different aspects/properties → do NOT merge\n\n"
    "2. MULTI-VALUED RELATIONS: Many relations connect one head to MULTIPLE distinct tails.\n"
    "   Each tail represents a separate instance. Do NOT merge them just because they share the relation.\n"
    "   Examples: 'includes', 'common sites', 'examples', 'types', 'components', 'causes', 'effects'\n\n"
    "3. SUBSTITUTION TEST: Merge only if the two tails can substitute each other in ALL contexts \n"
    "   without changing the factual information conveyed.\n\n"
    "4. FOCUS ON DENOTATION: Judge based on what each tail DIRECTLY refers to (its referent).\n"
    "   Ignore: associations, semantic fields, causes, effects, co-occurrence, shared properties.\n\n"
    "5. CONSERVATIVE MERGING: When in doubt, keep them separate. \n"
    "   False splits are less harmful than false merges in knowledge graphs.\n\n"
    "6. Every input index must appear in exactly one group.\n"
    "7. Choose the most informative and complete expression as the representative.\n\n"
    "Respond with strict JSON using this schema:\n"
    "{{\n"
    "  \"groups\": [\n"
    "    {{\"members\": [1, 3], \"representative\": 3, \"rationale\": \"Why these tails are coreferent (refer to the same entity).\"}}\n"
    "  ]\n"
    "}}\n"
)

DEFAULT_ATTRIBUTE_DEDUP_PROMPT = (
    "You are a knowledge graph curation assistant performing attribute value deduplication.\n"
    "All listed triples share the same head entity and relation.\n\n"
    "Head entity: {head}\n"
    "Relation: {relation}\n\n"
    "Head contexts:\n{head_context}\n\n"
    "Candidate attribute values:\n"
    "{candidates}\n\n"
    "TASK: Identify which attribute values are EQUIVALENT (express the exact same property/value).\n\n"
    "⚠️  CRITICAL WARNING - Common Mistake:\n"
    "DO NOT merge values just because they all relate to the same head entity.\n"
    "For example, if head = 'patient' and values = ['fever', 'cough', 'fatigue'],\n"
    "these are THREE DIFFERENT symptoms, not equivalent. Keep them separate!\n\n"
    "MERGE CONDITIONS (all must be true):\n"
    "✓ EQUIVALENCE: Two values express the SAME property with the SAME measurement/state\n"
    "  • '10 cm' and '100 mm' → SAME length (merge)\n"
    "  • 'red' and 'color: red' → SAME color (merge)\n"
    "  • 'temperature 37°C' and 'temperature 98.6°F' → SAME temperature (merge)\n"
    "  • 'H₂O' and '水' → SAME substance (merge)\n\n"
    "✗ DIFFERENT VALUES: Each describes a distinct property or value\n"
    "  • 'length 10 cm' and 'width 10 cm' → DIFFERENT properties (do NOT merge)\n"
    "  • 'temperature 37°C' and 'temperature 38°C' → DIFFERENT values (do NOT merge)\n"
    "  • 'spatial resolution' and 'edge sharpness' → DIFFERENT dimensions (do NOT merge)\n"
    "  • '空间分辨率降低' and '边缘锐利度降低' → DIFFERENT effects (do NOT merge)\n\n"
    "GUIDING PRINCIPLES:\n"
    "1. IDENTITY TEST: Merge ONLY if the two values represent exactly the same property-value pair.\n"
    "   Ask: \"Do these describe the SAME attribute with the SAME value?\"\n"
    "   - Different properties (even with same value) → do NOT merge\n"
    "   - Different values (even for same property) → do NOT merge\n"
    "   - Different aspects/dimensions → do NOT merge\n\n"
    "2. MULTI-VALUED ATTRIBUTES: Many entities have MULTIPLE distinct attribute values.\n"
    "   Each value represents a separate attribute. Do NOT merge them just because they relate to the same entity.\n"
    "   Examples: multiple symptoms, multiple effects, multiple components, multiple properties\n\n"
    "3. UNIT CONVERSION ONLY: The only acceptable transformations for merging are:\n"
    "   - Unit conversions (e.g., cm ↔ mm, °C ↔ °F)\n"
    "   - Linguistic variations of identical meaning (e.g., 'red' ↔ 'color: red')\n"
    "   - Synonyms referring to the exact same property-value (e.g., 'H₂O' ↔ 'water')\n\n"
    "4. DIRECT DENOTATION: Focus on what each value DIRECTLY describes.\n"
    "   Ignore: causal relationships, correlation, hierarchy, co-occurrence, shared domain.\n\n"
    "5. CONSERVATIVE MERGING: When in doubt, keep them separate.\n"
    "   In technical and scientific domains, different terms usually denote different concepts.\n\n"
    "6. Every input index must appear in exactly one group.\n"
    "7. Choose the most complete and informative description as the representative.\n\n"
    "Respond with strict JSON using this schema:\n"
    "{{\n"
    "  \"groups\": [\n"
    "    {{\"members\": [1, 3], \"representative\": 3, \"rationale\": \"Why these values are equivalent (express the same property-value).\"}}\n"
    "  ]\n"
    "}}\n"
)

class KTBuilder:
    def __init__(self, dataset_name, schema_path=None, mode=None, config=None):
        if config is None:
            config = get_config()
        
        self.config = config
        self.dataset_name = dataset_name
        self.schema = self.load_schema(schema_path or config.get_dataset_config(dataset_name).schema_path)
        self.graph = nx.MultiDiGraph()
        self.node_counter = 0
        self.datasets_no_chunk = config.construction.datasets_no_chunk
        self.token_len = 0
        self.lock = threading.Lock()
        self.llm_client = call_llm_api.LLMCompletionCall()
        self.all_chunks = {}
        self.mode = mode or config.construction.mode
        self._semantic_dedup_embedder = None

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
            
            edges_to_add.append((subj_node_id, obj_node_id, pred))
        
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
        #all_edges = attr_edges + triple_edges
        
        with self.lock:
            for node_id, node_data in all_nodes:
                self.graph.add_node(node_id, **node_data)
            
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
            
            #self.graph.add_edge(subj_node_id, obj_node_id, relation=pred)
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

    def process_level4(self, method = "semantic"):
        """Process communities using Tree-Comm algorithm"""
        level2_nodes = [n for n, d in self.graph.nodes(data=True) if d['level'] == 2]
        start_comm = time.time()
        _tree_comm = tree_comm.FastTreeComm(
            self.graph, 
            embedding_model=self.config.tree_comm.embedding_model,
            struct_weight=self.config.tree_comm.struct_weight,
        )
        comm_to_nodes = _tree_comm.detect_communities(level2_nodes)
        if method == 'semantic':
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

    def _get_semantic_dedup_embedder(self):
        config = self._get_semantic_dedup_config()
        if not config or not config.use_embeddings:
            return None

        if self._semantic_dedup_embedder is not None:
            return self._semantic_dedup_embedder

        model_name = getattr(config, "embedding_model", "") or getattr(self.config.embeddings, "model_name", "all-MiniLM-L6-v2")
        try:
            from sentence_transformers import SentenceTransformer

            self._semantic_dedup_embedder = SentenceTransformer(model_name)
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
                if key == "name" or value in (None, ""):
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

    def _summarize_contexts(self, chunk_ids: list, max_items: int = 2, max_chars: int = 200) -> list:
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

    def _cluster_candidate_tails(self, descriptions: list, threshold: float) -> list:
        """
        Cluster candidate descriptions using Average Linkage hierarchical clustering.
        
        This uses sklearn's AgglomerativeClustering with average linkage to ensure
        that items are only clustered together if they have high average similarity
        to all members of the cluster, avoiding the chaining effect of single linkage.
        
        Args:
            descriptions: List of text descriptions to cluster
            threshold: Similarity threshold (cosine similarity, 0-1)
            
        Returns:
            List of clusters, where each cluster is a list of indices
        """
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

            return [cluster["members"] for cluster in clusters]
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

        # Auto-detect prompt type based on relation
        config = self._get_semantic_dedup_config()
        prompt_type = getattr(config, "prompt_type", "general")
        
        # Use 'attribute' prompt for attribute-related relations
        if prompt_type == "general":
            attribute_relations = {"has_attribute", "attribute", "property", "has_property", "characteristic"}
            relation_lower = relation.lower() if relation else ""
            if relation_lower in attribute_relations or "attribute" in relation_lower:
                prompt_type = "attribute"
                logger.debug(f"Auto-selected 'attribute' prompt type for relation: {relation}")
        
        prompt_kwargs = {
            "head": head_text or "[UNKNOWN_HEAD]",
            "relation": relation_text,
            "head_context": head_context_text,
            "candidates": candidates_text,
        }

        try:
            return self.config.get_prompt_formatted("semantic_dedup", prompt_type, **prompt_kwargs)
        except Exception:
            # Fallback to appropriate default prompt based on type
            if prompt_type == "attribute":
                return DEFAULT_ATTRIBUTE_DEDUP_PROMPT.format(**prompt_kwargs)
            else:
                return DEFAULT_SEMANTIC_DEDUP_PROMPT.format(**prompt_kwargs)

    def _llm_semantic_group(
        self,
        head_text: str,
        relation: str,
        head_context_lines: list,
        batch_entries: list,
    ) -> list:
        prompt = self._build_semantic_dedup_prompt(head_text, relation, head_context_lines, batch_entries)

        try:
            response = self.llm_client.call_api(prompt)
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

        return groups

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

        threshold = getattr(config, "embedding_threshold", 0.85) or 0.85
        max_batch_size = max(1, int(getattr(config, "max_batch_size", 8) or 8))
        max_candidates = int(getattr(config, "max_candidates", 0) or 0)
        
        # Initialize intermediate results collector
        save_intermediate = getattr(config, "save_intermediate_results", False)
        intermediate_results = {
            "dataset": self.dataset_name,
            "config": {
                "threshold": threshold,
                "max_batch_size": max_batch_size,
                "max_candidates": max_candidates,
            },
            "communities": []
        } if save_intermediate else None

        for community_id, keyword_ids in community_to_keywords.items():
            keyword_ids = [kw for kw in keyword_ids if kw in self.graph]
            if len(keyword_ids) <= 1:
                continue

            # Initialize community result collector
            community_result = {
                "community_id": community_id,
                "community_name": None,
                "relation": "keyword_of",
                "total_candidates": len(keyword_ids),
                "candidates": [],
                "clustering": {
                    "method": "average_linkage",
                    "threshold": threshold,
                    "clusters": []
                },
                "llm_groups": [],
                "final_merges": []
            } if save_intermediate else None

            entries: list = []
            for kw_id in keyword_ids:
                node_data = self.graph.nodes.get(kw_id, {})
                properties = node_data.get("properties", {}) if isinstance(node_data, dict) else {}
                raw_name = properties.get("name") or properties.get("title") or kw_id

                chunk_ids = set(self._collect_node_chunk_ids(kw_id))
                source_entity_id = keyword_mapping.get(kw_id)
                source_entity_name = None

                if source_entity_id and source_entity_id in self.graph:
                    source_entity_name = self._describe_node(source_entity_id)
                    for chunk_id in self._collect_node_chunk_ids(source_entity_id):
                        if chunk_id:
                            chunk_ids.add(chunk_id)

                description = raw_name
                if source_entity_name and source_entity_name not in description:
                    description = f"{raw_name} (from {source_entity_name})"

                context_summaries = self._summarize_contexts(list(chunk_ids))

                entries.append(
                    {
                        "node_id": kw_id,
                        "description": description,
                        "raw_name": raw_name,
                        "chunk_ids": list(chunk_ids),
                        "context_summaries": context_summaries,
                        "source_entity_id": source_entity_id,
                        "source_entity_name": source_entity_name,
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

            # Save community info to intermediate results
            if save_intermediate:
                community_result["community_name"] = head_text
                community_result["head_contexts"] = head_context_lines
                for entry in entries:
                    community_result["candidates"].append({
                        "index": entry["index"],
                        "node_id": entry["node_id"],
                        "description": entry["description"],
                        "raw_name": entry["raw_name"],
                        "source_entity_id": entry.get("source_entity_id"),
                        "source_entity_name": entry.get("source_entity_name")
                    })

            candidate_descriptions = [entry["description"] for entry in entries]
            initial_clusters = self._cluster_candidate_tails(candidate_descriptions, threshold)

            # Save clustering results
            if save_intermediate:
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
                    community_result["clustering"]["clusters"].append(cluster_info)

            processed_indices: set = set()
            duplicate_indices: set = set()

            for cluster in initial_clusters:
                cluster_indices = [idx for idx in cluster if 0 <= idx < len(entries)]
                if not cluster_indices:
                    continue

                # Optimization: Skip LLM call for single-item clusters
                # No semantic grouping needed when there's only one candidate
                if len(cluster_indices) == 1:
                    processed_indices.add(cluster_indices[0])
                    continue

                overflow_indices = []
                if max_candidates and len(cluster_indices) > max_candidates:
                    overflow_indices = cluster_indices[max_candidates:]
                    cluster_indices = cluster_indices[:max_candidates]

                while cluster_indices:
                    batch_indices = cluster_indices[:max_batch_size]
                    batch_entries = [entries[i] for i in batch_indices]

                    groups = self._llm_semantic_group(head_text, "keyword_of", head_context_lines, batch_entries)

                    # Save LLM groups result
                    if save_intermediate:
                        llm_result = {
                            "cluster_id": initial_clusters.index([idx for idx in cluster if 0 <= idx < len(entries)]),
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
                        community_result["llm_groups"].append(llm_result)

                    if not groups:
                        for idx in batch_indices:
                            processed_indices.add(idx)
                        cluster_indices = cluster_indices[len(batch_indices):]
                        continue

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

                        if duplicates:
                            # Save merge operation
                            if save_intermediate:
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

                    cluster_indices = [idx for idx in cluster_indices if idx not in processed_indices and idx not in duplicate_indices]

                for idx in overflow_indices:
                    processed_indices.add(idx)
            
            # Save community result
            if save_intermediate:
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
        
        # Save intermediate results to file
        if save_intermediate and intermediate_results:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = getattr(config, "intermediate_results_path", None)
            
            if not output_path:
                output_path = f"output/dedup_intermediate/{self.dataset_name}_dedup_{timestamp}.json"
            else:
                # If path is a directory, add filename
                if output_path.endswith('/'):
                    output_path = f"{output_path}{self.dataset_name}_dedup_{timestamp}.json"
            
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
                logger.info(f"Saved deduplication intermediate results to: {output_path}")
                logger.info(f"Summary: {intermediate_results['summary']}")
            except Exception as e:
                logger.warning(f"Failed to save intermediate results: {e}")

    def _deduplicate_exact(self, edges: list) -> list:
        unique_edges: list = []
        index_by_key: dict = {}

        for tail_id, data in edges:
            data_copy = copy.deepcopy(data)

            if isinstance(data_copy, dict):
                chunk_ids = self._extract_edge_chunk_ids(data_copy)
                normalized_chunks: list = []
                seen_chunks: set = set()
                for chunk_id in chunk_ids:
                    if chunk_id and chunk_id not in seen_chunks:
                        normalized_chunks.append(chunk_id)
                        seen_chunks.add(chunk_id)

                # ensure chunk provenance stored in a consistent field
                if normalized_chunks:
                    data_copy["source_chunks"] = normalized_chunks
                if "source_chunk_ids" in data_copy:
                    data_copy.pop("source_chunk_ids", None)

                key_payload = copy.deepcopy(data_copy)
                key_payload.pop("source_chunks", None)
            else:
                chunk_ids = []
                key_payload = copy.deepcopy(data_copy)

            try:
                frozen = json.dumps(key_payload, ensure_ascii=False, sort_keys=True, default=str)
            except Exception:
                frozen = str(key_payload)

            key = (tail_id, frozen)
            if key in index_by_key:
                _, existing_data = unique_edges[index_by_key[key]]
                if isinstance(existing_data, dict):
                    existing_chunks = self._extract_edge_chunk_ids(existing_data)
                    combined = list(existing_chunks)
                    seen_chunks = set(existing_chunks)
                    for chunk_id in chunk_ids:
                        if chunk_id and chunk_id not in seen_chunks:
                            combined.append(chunk_id)
                            seen_chunks.add(chunk_id)
                    if combined:
                        existing_data["source_chunks"] = combined
                        existing_data.pop("source_chunk_ids", None)
                continue

            unique_edges.append((tail_id, data_copy))
            index_by_key[key] = len(unique_edges) - 1

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

        threshold = getattr(config, "embedding_threshold", 0.85) or 0.85
        candidate_descriptions = [entry["description"] for entry in entries]
        initial_clusters = self._cluster_candidate_tails(candidate_descriptions, threshold)

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
                "method": "average_linkage",
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
                edge_dedup_result["clustering"]["clusters"].append(cluster_info)

        final_edges: list = []
        processed_indices: set = set()
        duplicate_indices: set = set()

        for cluster in initial_clusters:
            cluster_indices = [idx for idx in cluster if idx not in processed_indices and idx not in duplicate_indices]
            if not cluster_indices:
                continue

            # Optimization: Skip LLM call for single-item clusters
            # No semantic grouping needed when there's only one edge
            if len(cluster_indices) == 1:
                idx = cluster_indices[0]
                entry = entries[idx]
                final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
                processed_indices.add(idx)
                continue

            overflow_indices = []
            if max_candidates and len(cluster_indices) > max_candidates:
                overflow_indices = cluster_indices[max_candidates:]
                cluster_indices = cluster_indices[:max_candidates]
                logger.debug(
                    "Semantic dedup limited LLM candidates for head '%s' relation '%s' to %d of %d items",
                    head_text,
                    relation,
                    max_candidates,
                    len(cluster),
                )

            while cluster_indices:
                batch_indices = cluster_indices[:max_batch_size]
                batch_entries = [entries[i] for i in batch_indices]
                groups = self._llm_semantic_group(head_text, relation, head_context_lines, batch_entries)

                # Save LLM groups result
                if save_intermediate:
                    llm_result = {
                        "cluster_id": initial_clusters.index([idx for idx in cluster if idx not in processed_indices and idx not in duplicate_indices][:len(cluster_indices)]) if cluster_indices else -1,
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
                        entry = entries[global_idx]
                        final_edges.append((entry["node_id"], copy.deepcopy(entry["data"])))
                        processed_indices.add(global_idx)
                    cluster_indices = cluster_indices[len(batch_indices):]
                    continue

                for group in groups:
                    rep_local = group.get("representative")
                    if rep_local is None or rep_local < 0 or rep_local >= len(batch_indices):
                        continue

                    rep_global = batch_indices[rep_local]
                    if rep_global in processed_indices:
                        continue

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

                    merged_data = self._merge_duplicate_metadata(
                        entries[rep_global],
                        duplicates,
                        group.get("rationale"),
                    )

                    final_edges.append((entries[rep_global]["node_id"], merged_data))
                    processed_indices.add(rep_global)

                cluster_indices = [idx for idx in cluster_indices if idx not in processed_indices and idx not in duplicate_indices]

            for global_idx in overflow_indices:
                if global_idx in processed_indices:
                    continue
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

    def triple_deduplicate_semantic(self):
        """deduplicate triples in lv1 and lv2"""
        
        # Initialize edge dedup results collector
        config = self._get_semantic_dedup_config()
        save_intermediate = config and getattr(config, "save_intermediate_results", False)
        if save_intermediate:
            self._edge_dedup_results = []
        
        new_graph = nx.MultiDiGraph()

        for node, node_data in self.graph.nodes(data=True):
            new_graph.add_node(node, **node_data)

        grouped_edges: dict = defaultdict(list)
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            relation = data.get('relation')
            grouped_edges[(u, relation)].append((v, copy.deepcopy(data)))

        for (head, relation), edges in grouped_edges.items():
            exact_unique = self._deduplicate_exact(edges)
            if self._semantic_dedup_enabled() and len(exact_unique) > 1:
                deduped_edges = self._semantic_deduplicate_group(head, relation, exact_unique)
            else:
                deduped_edges = exact_unique

            for tail_id, edge_data in deduped_edges:
                new_graph.add_edge(head, tail_id, **edge_data)

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
