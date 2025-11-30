#!/usr/bin/env python3
"""示例：使用事件模式发现器整合知识图谱三元组。

运行方式：
    python3 example_event_pattern_discovery.py

该脚本构造一个包含“化学位移伪影 → 解决方案为 → 采用高带宽”以及
“高带宽 → 影响 → 信噪比”这两条三元组的迷你图谱，并通过事件模式
发现器自动补全出对象/动作/状态结构以及传播关系。
"""

from __future__ import annotations

import networkx as nx

from utils.event_discovery import discover_event_patterns


def build_sample_graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()

    graph.add_node(
        "entity_1",
        label="entity",
        properties={"name": "化学位移伪影", "description": "MRI 成像常见伪影"},
    )
    graph.add_node(
        "action_phrase_1",
        label="attribute",
        properties={"name": "采用高带宽"},
    )
    graph.add_node(
        "state_1",
        label="attribute",
        properties={"name": "高带宽"},
    )
    graph.add_node(
        "metric_1",
        label="attribute",
        properties={"name": "信噪比"},
    )
    graph.add_node(
        "object_1",
        label="attribute",
        properties={"name": "带宽"},
    )

    graph.add_edge("entity_1", "action_phrase_1", relation="解决方案为")
    graph.add_edge("state_1", "metric_1", relation="影响")

    return graph


def format_node(graph: nx.MultiDiGraph, node_id: str) -> str:
    data = graph.nodes[node_id]
    name = data.get("properties", {}).get("name", node_id)
    label = data.get("label", "?")
    return f"{name}({label})"


def main():
    graph = build_sample_graph()

    print("原始节点与关系：")
    for node_id in graph.nodes:
        print(f"  节点 {format_node(graph, node_id)}")
    for u, v, data in graph.edges(data=True):
        print(
            f"  关系 {format_node(graph, u)} -[{data.get('relation')}]-> {format_node(graph, v)}"
        )

    patterns = discover_event_patterns(graph)

    print("\n事件模式发现完成。")
    print(f"共发现 {len(patterns)} 个事件。\n")

    for idx, pattern in enumerate(patterns, start=1):
        event_name = format_node(graph, pattern.event_node)
        action_name = format_node(graph, pattern.action_node)
        state_name = format_node(graph, pattern.state_node)
        object_name = format_node(graph, pattern.object_node)

        print(f"事件 #{idx}: {event_name}")
        print(f"  动作实体: {action_name}")
        print(f"  状态实体: {state_name}")
        print(f"  对象实体: {object_name}")

        if pattern.propagated_targets:
            print("  事件继承的影响：")
            for target, relation in pattern.propagated_targets:
                print(
                    f"    - {format_node(graph, target)} (关系: {relation})"
                )
        print()

    print("新增推理关系：")
    for u, v, data in graph.edges(data=True):
        if data.get("inferred"):
            print(
                f"  {format_node(graph, u)} -[{data.get('relation')}]-> {format_node(graph, v)}"
            )


if __name__ == "__main__":
    main()

