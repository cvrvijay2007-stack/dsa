"""Pydantic schemas shared by the API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

CANVAS_W = 800
CANVAS_H = 500


class Node(BaseModel):
    x: float = Field(ge=0, le=CANVAS_W)
    y: float = Field(ge=0, le=CANVAS_H)
    label: str | None = Field(default=None, max_length=24)


class Edge(BaseModel):
    a: int = Field(ge=0)
    b: int = Field(ge=0)
    w: int = Field(ge=1, le=9999)


class Graph(BaseModel):
    nodes: list[Node] = Field(default_factory=list, max_length=200)
    edges: list[Edge] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def _check_edges(self) -> "Graph":
        n = len(self.nodes)
        for e in self.edges:
            if e.a >= n or e.b >= n:
                raise ValueError(f"edge {e.a}-{e.b} references a missing node")
            if e.a == e.b:
                raise ValueError(f"self-loop on node {e.a} is not allowed")
        return self


Algorithm = Literal["prim", "kruskal"]


class MSTRequest(Graph):
    algorithm: Algorithm = "prim"
    start: int = Field(default=0, ge=0, description="Start node (Prim only)")


class Step(BaseModel):
    # Prim: start -> (frontier -> add)* [-> done]
    # Kruskal: start -> (consider -> add | skip)* [-> done]
    kind: Literal["start", "frontier", "consider", "add", "skip", "done"]
    message: str
    log: str
    in_tree: list[int]
    mst: list[int]
    # Prim: edges crossing the cut. Kruskal: edges not yet checked, in sorted order.
    candidates: list[int] = Field(default_factory=list)
    skipped: list[int] = Field(default_factory=list)
    pick: int | None = None
    new_node: int | None = None
    new_edge: int | None = None
    total: int
    done: bool = False


class MSTTrace(BaseModel):
    algorithm: Algorithm = "prim"
    steps: list[Step]
    total: int
    connected: bool
    mst: list[int]


class ParseRequest(BaseModel):
    text: str = Field(max_length=50_000)


class SavedGraphIn(Graph):
    name: str = Field(min_length=1, max_length=80)


class SavedGraphSummary(BaseModel):
    id: int
    name: str
    node_count: int
    edge_count: int
    updated_at: str


class SavedGraph(SavedGraphIn):
    id: int
    updated_at: str
