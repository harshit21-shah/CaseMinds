"""
NetworkX citation graph store.

Nodes  = Judgments (doc_id as key)
Edges  = CITES / DISTINGUISHES / OVERRULES / OVERRULED_BY

Persisted to data/graph.pkl. Load time for 10K nodes / 50K edges ≈ 0.3s.
"""

import logging
import os
import pickle
from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx

from services.config import settings
from services.ingestion.parser import ParsedJudgment

logger = logging.getLogger(__name__)


@dataclass
class TraversalResult:
    doc_id: str
    case_name: str
    hops: int
    path: list[str]
    is_overruled: bool
    citation: str | None = None


class GraphStore:
    def __init__(self, path: str | None = None) -> None:
        self._path = Path(path or settings.graph_path)
        self.G: nx.DiGraph = nx.DiGraph()
        self._load()

    # ── Persistence ────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._path.exists():
            with open(self._path, "rb") as f:
                self.G = pickle.load(f)
            logger.info(
                "graph loaded nodes=%d edges=%d",
                self.G.number_of_nodes(),
                self.G.number_of_edges(),
            )
        else:
            logger.info("no graph file found at %s — starting fresh", self._path)

    def save(self) -> None:
        os.makedirs(self._path.parent, exist_ok=True)
        with open(self._path, "wb") as f:
            pickle.dump(self.G, f, protocol=pickle.HIGHEST_PROTOCOL)
        logger.info(
            "graph saved nodes=%d edges=%d path=%s",
            self.G.number_of_nodes(),
            self.G.number_of_edges(),
            self._path,
        )

    # ── Mutations ──────────────────────────────────────────────────────────

    def add_judgment(self, judgment: ParsedJudgment) -> None:
        self.G.add_node(
            judgment.doc_id,
            type="judgment",
            case_name=judgment.case_name,
            citation=judgment.citation,
            court=judgment.court,
            date=str(judgment.date) if judgment.date else None,
            is_overruled=judgment.is_overruled,
            overruled_by=judgment.overruled_by,
        )

    def add_edge(
        self,
        citing_doc_id: str,
        cited_doc_id: str,
        rel: str = "CITES",
        confidence: float = 1.0,
        extracted_by: str = "regex",
    ) -> None:
        # Ensure both nodes exist (may be referenced before being ingested)
        if citing_doc_id not in self.G:
            self.G.add_node(citing_doc_id, type="judgment")
        if cited_doc_id not in self.G:
            self.G.add_node(cited_doc_id, type="judgment")

        self.G.add_edge(
            citing_doc_id,
            cited_doc_id,
            rel=rel,
            confidence=confidence,
            extracted_by=extracted_by,
        )

        # If this is an OVERRULES edge, also set the node flag
        if rel == "OVERRULES":
            self.G.nodes[cited_doc_id]["is_overruled"] = True
            self.G.nodes[cited_doc_id]["overruled_by"] = citing_doc_id

    # ── Traversal ──────────────────────────────────────────────────────────

    def traverse(
        self,
        start_id: str,
        directions: list[str] | None = None,
        max_hops: int = 2,
        limit: int = 20,
    ) -> list[TraversalResult]:
        """
        BFS traversal from start_id.

        directions: list of "CITES" (follow outgoing) and/or "CITED_BY" (follow incoming).
        Returns list of TraversalResult, sorted by hop count.
        """
        if directions is None:
            directions = ["CITES", "CITED_BY"]

        if start_id not in self.G:
            logger.debug("traverse: start_id=%s not in graph", start_id)
            return []

        visited: set[str] = set()
        results: list[TraversalResult] = []
        queue: list[tuple[str, int, list[str]]] = [(start_id, 0, [])]

        while queue and len(results) < limit:
            node, hops, path = queue.pop(0)

            if node in visited or hops > max_hops:
                continue
            visited.add(node)

            node_data = self.G.nodes.get(node, {})
            if hops > 0:
                results.append(
                    TraversalResult(
                        doc_id=node,
                        case_name=node_data.get("case_name", ""),
                        hops=hops,
                        path=path[:],
                        is_overruled=node_data.get("is_overruled", False),
                        citation=node_data.get("citation"),
                    )
                )

            for neighbor in self._neighbors(node, directions):
                queue.append((neighbor, hops + 1, path + [node]))

        return sorted(results, key=lambda r: r.hops)

    def _neighbors(self, node: str, directions: list[str]) -> list[str]:
        neighbors: list[str] = []
        if "CITES" in directions:
            neighbors.extend(self.G.successors(node))
        if "CITED_BY" in directions:
            neighbors.extend(self.G.predecessors(node))
        return neighbors

    # ── Queries ────────────────────────────────────────────────────────────

    def is_overruled(self, doc_id: str) -> bool:
        return bool(self.G.nodes.get(doc_id, {}).get("is_overruled", False))

    def get_node(self, doc_id: str) -> dict:
        return dict(self.G.nodes.get(doc_id, {}))

    def stats(self) -> dict:
        return {
            "nodes": self.G.number_of_nodes(),
            "edges": self.G.number_of_edges(),
        }
