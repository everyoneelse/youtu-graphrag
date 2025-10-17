"""Offline semantic deduplication script for existing Youtu-GraphRAG graphs.

This utility loads a previously constructed knowledge graph JSON file together
with its associated chunk store and runs the same semantic deduplication
routines that the online builder applies to triples and community keywords.

Example
-------
    python scripts/offline_semantic_dedup.py \
        --graph output/graphs/demo_new.json \
        --chunks output/chunks/demo.txt \
        --output output/graphs/demo_deduped.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

import networkx as nx

from config import ConfigManager, get_config
from models.constructor.kt_gen import KTBuilder
from utils import graph_processor
from utils import call_llm_api
from utils.logger import logger


class OfflineSemanticDeduper(KTBuilder):
    """Thin wrapper around :class:`KTBuilder` focused on semantic deduplication."""

    def __init__(self, config: ConfigManager | None = None):
        # Intentionally avoid calling ``KTBuilder.__init__`` because it expects a
        # dataset name and schema paths. We only need a configuration object along
        # with the semantic dedup helpers defined on ``KTBuilder``.
        if config is None:
            config = get_config()

        self.config = config
        self.graph = nx.MultiDiGraph()
        self.llm_client = call_llm_api.LLMCompletionCall()
        self.all_chunks: Dict[str, str] = {}
        self._semantic_dedup_embedder = None

    # Expose protected helpers for external script usage while keeping the
    # original implementations in ``KTBuilder`` intact.
    triple_deduplicate = KTBuilder.triple_deduplicate
    _deduplicate_keyword_nodes = KTBuilder._deduplicate_keyword_nodes
    _semantic_dedup_enabled = KTBuilder._semantic_dedup_enabled


def _load_chunk_mapping(path: Path) -> Dict[str, str]:
    """Load chunk id → text mapping from ``path``.

    The chunk export is typically stored as ``.txt`` with each line formatted as
    ``id: <chunk_id>\tChunk: <text>``. The loader also supports JSON files that
    map chunk ids to texts.
    """

    if not path.exists():
        raise FileNotFoundError(f"Chunk file or directory not found: {path}")

    if path.is_dir():
        chunk_map: Dict[str, str] = {}
        for file in sorted(path.iterdir()):
            if file.is_dir():
                chunk_map.update(_load_chunk_mapping(file))
            else:
                chunk_map.update(_load_chunk_mapping(file))
        return chunk_map

    chunk_map: Dict[str, str] = {}
    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(key, str) and isinstance(value, str):
                    chunk_map[key] = value
        elif isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                chunk_id = item.get("id") or item.get("chunk_id")
                text = item.get("text") or item.get("chunk")
                if isinstance(chunk_id, str) and isinstance(text, str):
                    chunk_map[chunk_id] = text
        else:
            raise ValueError(f"Unrecognised chunk JSON structure in {path}")
        return chunk_map

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue

            chunk_id: str | None = None
            chunk_text: str | None = None

            if "\t" in raw:
                prefix, chunk_part = raw.split("\t", 1)
                if prefix.startswith("id: "):
                    chunk_id = prefix[4:].strip()
                if chunk_part.startswith("Chunk: "):
                    chunk_text = chunk_part[7:].strip()
            else:
                # Fallback parser for space separated exports.
                if raw.startswith("id:") and "Chunk:" in raw:
                    id_part, chunk_part = raw.split("Chunk:", 1)
                    chunk_id = id_part.replace("id:", "").strip()
                    chunk_text = chunk_part.strip()

            if chunk_id and chunk_text:
                chunk_map[chunk_id] = chunk_text

    return chunk_map


def _build_keyword_mapping(graph: nx.MultiDiGraph) -> Dict[str, str]:
    """Reconstruct keyword → source entity mapping from the graph."""

    mapping: Dict[str, str] = {}
    for source, target, data in graph.edges(data=True):
        if not isinstance(data, dict):
            continue
        if data.get("relation") != "represented_by":
            continue

        source_data = graph.nodes.get(source, {})
        target_data = graph.nodes.get(target, {})
        if source_data.get("label") == "entity" and target_data.get("label") == "keyword":
            mapping[target] = source

    return mapping


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline semantic deduplication for Youtu-GraphRAG graphs")
    parser.add_argument("--graph", required=True, type=Path, help="Path to the input graph JSON file")
    parser.add_argument("--chunks", required=True, type=Path, help="Path to the chunk file or directory")
    parser.add_argument("--output", required=True, type=Path, help="Where to save the deduplicated graph JSON")
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional path to a configuration YAML file overriding the default base_config.yaml",
    )
    parser.add_argument(
        "--force-enable",
        action="store_true",
        help="Force-enable semantic dedup even if disabled in the configuration",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    config = ConfigManager(str(args.config)) if args.config else get_config()

    if args.force_enable:
        try:
            config.construction.semantic_dedup.enabled = True
        except Exception as e:
            raise RuntimeError("Failed to force-enable semantic dedup in configuration") from e

    deduper = OfflineSemanticDeduper(config)

    logger.info("Loading graph from %s", args.graph)
    deduper.graph = graph_processor.load_graph_from_json(str(args.graph))

    logger.info("Loading chunk contexts from %s", args.chunks)
    deduper.all_chunks = _load_chunk_mapping(args.chunks)
    logger.info("Loaded %d chunks", len(deduper.all_chunks))

    original_edge_count = deduper.graph.number_of_edges()
    original_keyword_count = sum(1 for _, data in deduper.graph.nodes(data=True) if data.get("label") == "keyword")

    if not deduper._semantic_dedup_enabled():
        logger.warning("Semantic deduplication is disabled in the configuration. No changes will be made.")
    else:
        logger.info("Running triple semantic deduplication")
        deduper.triple_deduplicate()

        logger.info("Running keyword semantic deduplication")
        keyword_mapping = _build_keyword_mapping(deduper.graph)
        if keyword_mapping:
            deduper._deduplicate_keyword_nodes(keyword_mapping)
        else:
            logger.info("No keyword mapping detected; skipping keyword deduplication")

    deduped_edge_count = deduper.graph.number_of_edges()
    deduped_keyword_count = sum(1 for _, data in deduper.graph.nodes(data=True) if data.get("label") == "keyword")

    logger.info(
        "Edges: %d → %d | Keyword nodes: %d → %d",
        original_edge_count,
        deduped_edge_count,
        original_keyword_count,
        deduped_keyword_count,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    graph_processor.save_graph_to_json(deduper.graph, str(args.output))
    logger.info("Deduplicated graph written to %s", args.output)


if __name__ == "__main__":
    main()
