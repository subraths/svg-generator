from __future__ import annotations

from typing import Dict, List, Set, Tuple
from app.schemas import ConceptGraph, Relationship


def validate_and_repair_graph(graph: ConceptGraph) -> ConceptGraph:
    """
    Validate and repair graph invariants in-place style (returns a new ConceptGraph object).
    Logic-first rules:
      1) Concept IDs must be unique.
      2) Relationships must reference existing concept IDs.
      3) Remove self-loops for now.
      4) Deduplicate relationships by (from_node, to_node, type).
      5) narration_order contains only valid IDs and is completed deterministically.
    """

    # --- 1) Ensure unique concepts by ID (keep first occurrence) ---
    unique_concepts = []
    seen_ids: Set[str] = set()
    for concept in graph.concepts:
        # Keep first instance of each ID to remain deterministic.
        if concept.id not in seen_ids:
            seen_ids.add(concept.id)
            unique_concepts.append(concept)

    valid_ids = {c.id for c in unique_concepts}

    # --- 2/3/4) Filter invalid/self-loop/dedup relationships ---
    unique_edges: List[Relationship] = []
    seen_edge_keys: Set[Tuple[str, str, str]] = set()

    for rel in graph.relationships:
        # Skip edge if either endpoint does not exist in concept IDs.
        if rel.from_node not in valid_ids or rel.to_node not in valid_ids:
            continue

        # Skip self loops for current logic policy.
        if rel.from_node == rel.to_node:
            continue

        edge_key = (rel.from_node, rel.to_node, rel.type)
        if edge_key in seen_edge_keys:
            continue

        seen_edge_keys.add(edge_key)
        unique_edges.append(rel)

    # --- 5) Repair narration_order deterministically ---
    repaired_narration = _repair_narration_order(
        concept_ids=[c.id for c in unique_concepts],
        relationships=unique_edges,
        existing_order=graph.narration_order,
    )

    return ConceptGraph(
        title=graph.title,
        type=graph.type,
        concepts=unique_concepts,
        relationships=unique_edges,
        subtopics=graph.subtopics,
        narration_order=repaired_narration,
    )


def _repair_narration_order(
    concept_ids: List[str],
    relationships: List[Relationship],
    existing_order: List[str],
) -> List[str]:
    """
    Build stable narration order:
      A) Keep valid IDs from existing_order in given sequence.
      B) Append reachable flow order via simple in-degree traversal.
      C) Append any remaining isolated nodes sorted by concept_ids order.
    """
    concept_set = set(concept_ids)

    # A) Keep only valid unique IDs from existing order.
    ordered: List[str] = []
    seen: Set[str] = set()
    for nid in existing_order:
        if nid in concept_set and nid not in seen:
            ordered.append(nid)
            seen.add(nid)

    # Build adjacency + indegree for B.
    outgoing: Dict[str, List[str]] = {nid: [] for nid in concept_ids}
    indegree: Dict[str, int] = {nid: 0 for nid in concept_ids}

    for rel in relationships:
        outgoing[rel.from_node].append(rel.to_node)
        indegree[rel.to_node] += 1

    # Deterministic queue: nodes with indegree 0 in original concept order.
    queue = [nid for nid in concept_ids if indegree[nid] == 0]
    topo: List[str] = []

    while queue:
        current = queue.pop(0)
        topo.append(current)
        for nxt in outgoing[current]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    # B) Append topo nodes not already included.
    for nid in topo:
        if nid not in seen:
            ordered.append(nid)
            seen.add(nid)

    # C) Append any remaining nodes (cycle leftovers / disconnected) deterministically.
    for nid in concept_ids:
        if nid not in seen:
            ordered.append(nid)
            seen.add(nid)

    return ordered
