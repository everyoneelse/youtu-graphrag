"""Knowledge graph event discovery utilities.

This module implements a lightweight rule-based engine that stitches
pairwise knowledge graph triples into event-centric patterns following
the
``(object entity, action entity, state entity)`` design principle. It is
optimised for post-processing triples extracted via LLM pipelines where
tail-head overlaps suggest latent event structures.

Example usage is showcased in ``example_event_pattern_discovery.py``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

import networkx as nx

from utils.logger import logger


@dataclass
class EventDiscoveryConfig:
    """Configuration for event discovery heuristics."""

    # Relations that indicate actionable triples (subject -> solution/action -> tail phrase)
    trigger_relations: Set[str] = field(
        default_factory=lambda: {
            "解决方案为",
            "解决方案",
            "处理方法",
            "治疗方案",
            "应对策略",
            "改善方式",
            "优化策略",
        }
    )

    # Candidate action verb prefixes detected at the beginning of the tail phrase
    action_prefixes: Sequence[str] = field(
        default_factory=lambda: (
            "采用",
            "使用",
            "利用",
            "采取",
            "引入",
            "配合",
            "结合",
            "提高",
            "增加",
            "减小",
            "降低",
            "增强",
            "减弱",
            "抑制",
            "提升",
            "优化",
        )
    )

    # Normalisation for action verbs (maps detected verb prefix -> canonical verb)
    action_normalisation: Dict[str, str] = field(
        default_factory=lambda: {
            "采用": "采用",
            "使用": "使用",
            "利用": "使用",
            "采取": "采用",
            "引入": "引入",
            "配合": "配合",
            "结合": "结合",
            "提高": "提高",
            "提升": "提高",
            "增强": "增强",
            "增加": "增加",
            "减小": "降低",
            "减弱": "降低",
            "降低": "降低",
            "抑制": "抑制",
            "优化": "优化",
        }
    )

    # State modifiers preceding the target object name (e.g. 高带宽 -> modifier 高)
    state_modifiers: Sequence[str] = field(
        default_factory=lambda: (
            "过高",
            "过低",
            "高",
            "低",
            "增强",
            "增强的",
            "减弱",
            "减少",
            "降低",
            "提高",
            "增加",
            "大",
            "小",
            "快速",
            "慢",
        )
    )

    # Map modifier tokens to canonical action verbs when available
    modifier_to_action: Dict[str, str] = field(
        default_factory=lambda: {
            "高": "提高",
            "提高": "提高",
            "增加": "增加",
            "增强": "增强",
            "过高": "提高",
            "低": "降低",
            "过低": "降低",
            "降低": "降低",
            "减少": "降低",
            "减弱": "降低",
        }
    )

    # Preferred labels when reusing existing nodes
    preferred_state_labels: Sequence[str] = field(
        default_factory=lambda: ("attribute", "state", "condition"))
    preferred_object_labels: Sequence[str] = field(
        default_factory=lambda: ("entity", "attribute", "object", "equipment"))

    # Labels + relations for new nodes and links
    event_label: str = "event"
    action_label: str = "action"
    fallback_state_label: str = "state"
    fallback_object_label: str = "object"

    source_to_event_relation_map: Dict[str, str] = field(
        default_factory=lambda: {
            "解决方案为": "解决方案事件",
            "解决方案": "解决方案事件",
            "处理方法": "处理事件",
            "治疗方案": "治疗事件",
            "应对策略": "策略事件",
            "改善方式": "改善事件",
            "优化策略": "优化事件",
        }
    )
    default_source_to_event_relation: str = "关联事件"

    event_to_action_relation: str = "has_action"
    action_to_object_relation: str = "acts_on"
    event_to_state_relation: str = "achieves_state"
    state_to_event_relation: str = "state_of_event"
    event_to_target_relation_template: str = "event_via_state:{relation}"

    annotate_edges: bool = True
    default_confidence: float = 0.65


@dataclass
class EventComponents:
    """Intermediate extraction result from a tail phrase."""

    action_phrase: str
    verb_prefix: str
    canonical_action: str
    state_text: str
    state_modifier: Optional[str]
    object_text: str

    def canonical_action_name(self) -> str:
        """Join canonical action with object for readable node naming."""

        return f"{self.canonical_action}{self.object_text}" if self.object_text else self.canonical_action


@dataclass
class EventPattern:
    """Captured event pattern metadata returned to the caller."""

    source_node: str
    trigger_relation: str
    action_phrase_node: str
    event_node: str
    action_node: str
    object_node: str
    state_node: str
    propagated_targets: List[Tuple[str, str]]


class EventPatternDiscovery:
    """Rule-based event discovery over a ``nx.MultiDiGraph`` knowledge graph."""

    def __init__(self, graph: nx.MultiDiGraph, config: Optional[EventDiscoveryConfig] = None):
        self.graph = graph
        self.config = config or EventDiscoveryConfig()
        self.name_index = self._build_name_index()
        self.event_signature_index: Dict[Tuple[str, str, str, str], str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> List[EventPattern]:
        """Execute event discovery and return harvested patterns."""

        results: List[EventPattern] = []
        edges_snapshot = list(self.graph.edges(keys=True, data=True))

        for source, tail, edge_key, data in edges_snapshot:
            relation = data.get("relation", "")
            if relation not in self.config.trigger_relations:
                continue

            phrase = self._get_node_name(tail)
            if not phrase:
                continue

            components = self._extract_components(phrase)
            if not components:
                continue

            state_node = self._ensure_state_node(components.state_text)
            if not state_node:
                continue

            object_node = self._ensure_object_node(components.object_text)
            action_node = self._ensure_action_node(components)
            event_node = self._ensure_event_node(
                source_node=source,
                trigger_relation=relation,
                tail_node=tail,
                components=components,
                state_node=state_node,
                object_node=object_node,
                action_node=action_node,
            )

            if not event_node:
                continue

            self._link_event_structure(
                source_node=source,
                tail_node=tail,
                relation=relation,
                event_node=event_node,
                action_node=action_node,
                state_node=state_node,
                object_node=object_node,
                components=components,
            )

            propagated_targets = self._propagate_state_effects(event_node, state_node)

            results.append(
                EventPattern(
                    source_node=source,
                    trigger_relation=relation,
                    action_phrase_node=tail,
                    event_node=event_node,
                    action_node=action_node,
                    object_node=object_node,
                    state_node=state_node,
                    propagated_targets=propagated_targets,
                )
            )

        logger.info("Event discovery generated %d event patterns", len(results))
        return results

    # ------------------------------------------------------------------
    # Discovery helpers
    # ------------------------------------------------------------------
    def _extract_components(self, phrase: str) -> Optional[EventComponents]:
        phrase = (phrase or "").strip()
        if not phrase:
            return None

        verb_prefix = self._match_action_prefix(phrase)
        if not verb_prefix:
            return None

        remainder = phrase[len(verb_prefix):].strip()
        if not remainder:
            return None

        modifier, object_text = self._split_modifier_and_object(remainder)

        state_text = remainder
        canonical_action = self._derive_canonical_action(verb_prefix, modifier)

        return EventComponents(
            action_phrase=phrase,
            verb_prefix=verb_prefix,
            canonical_action=canonical_action,
            state_text=state_text,
            state_modifier=modifier,
            object_text=object_text,
        )

    def _match_action_prefix(self, phrase: str) -> Optional[str]:
        for prefix in sorted(self.config.action_prefixes, key=len, reverse=True):
            if phrase.startswith(prefix):
                return prefix
        return None

    def _split_modifier_and_object(self, remainder: str) -> Tuple[Optional[str], str]:
        for modifier in sorted(self.config.state_modifiers, key=len, reverse=True):
            if remainder.startswith(modifier) and len(remainder) > len(modifier):
                return modifier, remainder[len(modifier):]
        return None, remainder

    def _derive_canonical_action(self, verb_prefix: str, modifier: Optional[str]) -> str:
        if modifier and modifier in self.config.modifier_to_action:
            return self.config.modifier_to_action[modifier]
        return self.config.action_normalisation.get(verb_prefix, verb_prefix)

    def _ensure_state_node(self, state_text: str) -> Optional[str]:
        node = self._find_preferred_node(state_text, self.config.preferred_state_labels)
        if node:
            return node

        if not state_text:
            return None

        return self._create_node(
            label=self.config.fallback_state_label,
            name=state_text,
            extra_properties={"generated": True},
        )

    def _ensure_object_node(self, object_text: str) -> Optional[str]:
        node = self._find_preferred_node(object_text, self.config.preferred_object_labels)
        if node:
            return node

        if not object_text:
            return None

        return self._create_node(
            label=self.config.fallback_object_label,
            name=object_text,
            extra_properties={"generated": True},
        )

    def _ensure_action_node(self, components: EventComponents) -> str:
        action_name = components.canonical_action_name()
        node = self._find_preferred_node(action_name, (self.config.action_label,))
        if node:
            return node

        properties = {
            "name": action_name,
            "canonical_action": components.canonical_action,
            "object": components.object_text,
            "source_phrase": components.action_phrase,
        }

        return self._create_node(self.config.action_label, action_name, properties)

    def _ensure_event_node(
        self,
        *,
        source_node: str,
        trigger_relation: str,
        tail_node: str,
        components: EventComponents,
        state_node: str,
        object_node: str,
        action_node: str,
    ) -> Optional[str]:
        signature = (
            source_node,
            components.canonical_action,
            components.object_text,
            components.state_text,
        )

        if signature in self.event_signature_index:
            return self.event_signature_index[signature]

        source_name = self._get_node_name(source_node)
        event_name = self._compose_event_name(source_name, components)

        properties = {
            "name": event_name,
            "action": components.canonical_action,
            "object": components.object_text,
            "state": components.state_text,
            "state_modifier": components.state_modifier,
            "action_phrase": components.action_phrase,
            "confidence": self.config.default_confidence,
            "source_node": source_node,
            "trigger_relation": trigger_relation,
            "tail_node": tail_node,
        }

        event_node = self._create_node(self.config.event_label, event_name, properties)
        self.event_signature_index[signature] = event_node
        return event_node

    def _compose_event_name(self, source_name: Optional[str], components: EventComponents) -> str:
        parts = []
        if source_name:
            parts.append(source_name)
        parts.append(components.canonical_action_name())
        if components.state_text and components.state_text != components.object_text:
            parts.append(components.state_text)
        return "-".join(parts)

    def _link_event_structure(
        self,
        *,
        source_node: str,
        tail_node: str,
        relation: str,
        event_node: str,
        action_node: str,
        state_node: str,
        object_node: str,
        components: EventComponents,
    ) -> None:
        event_relation = self.config.source_to_event_relation_map.get(
            relation, self.config.default_source_to_event_relation
        )

        self._add_edge_if_missing(
            source_node,
            event_node,
            relation=event_relation,
            inferred=True,
            trigger_relation=relation,
        )

        self._add_edge_if_missing(
            event_node,
            action_node,
            relation=self.config.event_to_action_relation,
            inferred=True,
        )

        self._add_edge_if_missing(
            action_node,
            object_node,
            relation=self.config.action_to_object_relation,
            inferred=True,
        )

        self._add_edge_if_missing(
            event_node,
            state_node,
            relation=self.config.event_to_state_relation,
            inferred=True,
        )

        self._add_edge_if_missing(
            state_node,
            event_node,
            relation=self.config.state_to_event_relation,
            inferred=True,
        )

        # Optionally connect the original tail phrase node to the canonical action node
        if tail_node != action_node:
            self._add_edge_if_missing(
                tail_node,
                action_node,
                relation="normalises_to",
                inferred=True,
                canonical_action=components.canonical_action,
            )

    def _propagate_state_effects(self, event_node: str, state_node: str) -> List[Tuple[str, str]]:
        propagated: List[Tuple[str, str]] = []
        for _, target, data in self.graph.out_edges(state_node, data=True):
            relation = data.get("relation")
            if not relation:
                continue
            if data.get("inferred"):
                continue

            new_relation = self.config.event_to_target_relation_template.format(relation=relation)
            added = self._add_edge_if_missing(
                event_node,
                target,
                relation=new_relation,
                inferred=True,
                source_state=state_node,
                inherited_relation=relation,
            )
            if added:
                propagated.append((target, new_relation))
        return propagated

    # ------------------------------------------------------------------
    # Graph manipulation helpers
    # ------------------------------------------------------------------
    def _build_name_index(self) -> Dict[str, Set[str]]:
        index: Dict[str, Set[str]] = {}
        for node_id, data in self.graph.nodes(data=True):
            name = self._get_node_name(node_id, data)
            if not name:
                continue
            normalized = self._normalise_name(name)
            index.setdefault(normalized, set()).add(node_id)
        return index

    def _find_preferred_node(self, name: str, preferred_labels: Sequence[str]) -> Optional[str]:
        normalized = self._normalise_name(name)
        candidate_ids = self.name_index.get(normalized, set())
        if not candidate_ids:
            return None

        preferred_set = set(preferred_labels)
        for node_id in candidate_ids:
            label = self.graph.nodes[node_id].get("label")
            if label in preferred_set:
                return node_id

        # fallback: first candidate regardless of label
        return next(iter(candidate_ids))

    def _create_node(
        self,
        label: str,
        name: str,
        extra_properties: Optional[Dict] = None,
    ) -> str:
        node_id = f"{label}_{uuid.uuid4().hex[:8]}"
        properties = {"name": name}
        if extra_properties:
            properties.update(extra_properties)
        self.graph.add_node(node_id, label=label, properties=properties)
        normalized = self._normalise_name(name)
        self.name_index.setdefault(normalized, set()).add(node_id)
        logger.debug("Created node %s (%s)", node_id, name)
        return node_id

    def _add_edge_if_missing(self, u: str, v: str, relation: str, **attrs) -> bool:
        edge_dict = self.graph.get_edge_data(u, v, default={})
        for edge_data in edge_dict.values():
            if edge_data.get("relation") == relation:
                return False

        data = {"relation": relation}
        if self.config.annotate_edges:
            data.update(attrs)
        self.graph.add_edge(u, v, **data)
        logger.debug("Added edge %s -> %s (%s)", u, v, relation)
        return True

    def _get_node_name(self, node_id: str, data: Optional[Dict] = None) -> Optional[str]:
        if data is None:
            data = self.graph.nodes.get(node_id, {})
        props = data.get("properties") or {}
        name = props.get("name")
        if isinstance(name, str):
            return name.strip()
        return None

    @staticmethod
    def _normalise_name(name: str) -> str:
        return "".join(name.lower().split())


def discover_event_patterns(
    graph: nx.MultiDiGraph,
    config: Optional[EventDiscoveryConfig] = None,
) -> List[EventPattern]:
    """Convenience wrapper to run event discovery."""

    discovery = EventPatternDiscovery(graph, config=config)
    return discovery.run()

