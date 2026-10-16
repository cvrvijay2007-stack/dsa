"""Graph builders: sample, random, and parsing a plain-text edge list."""

from __future__ import annotations

import math
import random
import re

from .models import CANVAS_H, CANVAS_W, Edge, Graph, Node

SAMPLE_POINTS = [(110, 110), (330, 60), (570, 90), (700, 230), (560, 400), (320, 420), (130, 330), (390, 240)]
SAMPLE_EDGES = [
    (0, 1, 4), (0, 6, 8), (1, 2, 8), (1, 7, 11), (2, 3, 7), (2, 7, 2), (3, 4, 9),
    (3, 7, 6), (4, 5, 10), (4, 7, 4), (5, 6, 1), (5, 7, 14), (6, 7, 7),
]

# "-" separates names ("B-C 2") but a leading "-" before digits is a negative weight ("A B -3").
_SPLIT = re.compile(r"[\s,;>–]+|(?<!\s)-+|-+(?!\d)")
MAX_NODES = 200
MAX_WEIGHT = 9999


def _add_edge(edges: list[Edge], a: int, b: int, w: int) -> None:
    """Append an undirected edge unless it is a self-loop or a duplicate."""
    if a == b or any({e.a, e.b} == {a, b} for e in edges):
        return
    edges.append(Edge(a=a, b=b, w=w))


def sample_graph() -> Graph:
    return Graph(
        nodes=[Node(x=x, y=y) for x, y in SAMPLE_POINTS],
        edges=[Edge(a=a, b=b, w=w) for a, b, w in SAMPLE_EDGES],
    )


def random_graph(n: int = 8, extra: int = 6, seed: int | None = None) -> Graph:
    """Random connected graph: a random spanning tree plus ``extra`` random edges."""
    rng = random.Random(seed)
    min_gap = 110 if n <= 10 else max(50, 110 - (n - 10) * 5)
    pts: list[tuple[float, float]] = []
    tries = 0
    while len(pts) < n:
        p = (60 + rng.random() * 680, 50 + rng.random() * 400)
        tries += 1
        if tries > 5000 or all(math.hypot(q[0] - p[0], q[1] - p[1]) > min_gap for q in pts):
            pts.append(p)
    edges: list[Edge] = []
    for i in range(1, n):
        _add_edge(edges, i, rng.randrange(i), rng.randint(1, 20))
    for _ in range(extra):
        _add_edge(edges, rng.randrange(n), rng.randrange(n), rng.randint(1, 20))
    return Graph(nodes=[Node(x=round(x, 1), y=round(y, 1)) for x, y in pts], edges=edges)


def circle_layout(count: int) -> list[tuple[float, float]]:
    if count == 1:
        return [(CANVAS_W / 2, CANVAS_H / 2)]
    out = []
    for i in range(count):
        g = 2 * math.pi * i / count - math.pi / 2
        out.append((round(400 + 300 * math.cos(g), 1), round(250 + 190 * math.sin(g), 1)))
    return out


def parse_edge_list(text: str) -> Graph:
    """Parse lines of ``node node weight``; a lone name declares an isolated node.

    Separators may be spaces, commas, semicolons, ``-``, ``>`` or ``–``.
    Missing or non-positive weights default to 1, weights above 9999 are capped.
    Node names keep first-seen order.
    """
    labels: list[str] = []
    index: dict[str, int] = {}

    def nid(name: str) -> int:
        if name not in index:
            index[name] = len(labels)
            labels.append(name[:24])
        return index[name]

    raw: list[tuple[int, int, int]] = []
    for line in text.splitlines():
        tokens = [t for t in _SPLIT.split(line.strip()) if t]
        if not tokens:
            continue
        a = nid(tokens[0])
        if len(tokens) > 1:
            b = nid(tokens[1])
            try:
                w = float(tokens[2])
            except (IndexError, ValueError):
                w = 1.0
            # Non-positive or non-numeric weights become 1; huge ones are capped.
            w = min(MAX_WEIGHT, max(1, round(w))) if math.isfinite(w) and w > 0 else (MAX_WEIGHT if w == math.inf else 1)
            raw.append((a, b, w))

    if len(labels) > MAX_NODES:
        raise ValueError(f"Too many nodes ({len(labels)}, max {MAX_NODES}).")
    nodes = [Node(x=x, y=y, label=l) for (x, y), l in zip(circle_layout(len(labels)), labels)]
    edges: list[Edge] = []
    for a, b, w in raw:
        _add_edge(edges, a, b, w)
    return Graph(nodes=nodes, edges=edges)
