"""Prim's algorithm, recorded as a sequence of visualisation steps.

The trace mirrors how the UI teaches the algorithm:

1. ``start``    - the start node joins the tree.
2. ``frontier`` - every edge crossing the cut (one end in the tree, one out) is a
                  candidate; the cheapest one is highlighted as the pick.
3. ``add``      - the picked edge and its outside node join the tree.

Steps 2-3 repeat until every node is in the tree (``add`` carries ``done``), or
the frontier is empty while nodes remain - the graph is disconnected, and a
final ``done`` step reports the spanning-forest weight of the reached component.

Ties on weight are broken by the lowest edge index, so traces are deterministic.
"""

from __future__ import annotations

from .models import Graph, MSTTrace, Step


def label(graph: Graph, i: int) -> str:
    node = graph.nodes[i]
    if node.label:
        return node.label
    suffix = str(i // 26) if i >= 26 else ""
    return chr(65 + i % 26) + suffix


def prim_trace(graph: Graph, start: int = 0) -> MSTTrace:
    n = len(graph.nodes)
    if n == 0:
        return MSTTrace(algorithm="prim", steps=[], total=0, connected=True, mst=[])
    if start >= n:
        start = 0

    nm = lambda i: label(graph, i)  # noqa: E731
    edges = graph.edges
    in_tree: set[int] = {start}
    mst: list[int] = []
    total = 0
    steps: list[Step] = []

    def snap(**kw) -> Step:
        return Step(in_tree=sorted(in_tree), mst=list(mst), total=total, **kw)

    first_done = n == 1
    steps.append(
        snap(
            kind="start",
            message="Done. A single node is already its own spanning tree." if first_done else f"Starting at {nm(start)}. It is the first node in the tree.",
            log=f"Start at {nm(start)}: add it to the tree.",
            done=first_done,
        )
    )
    if first_done:
        return MSTTrace(algorithm="prim", steps=steps, total=0, connected=True, mst=[])

    while True:
        cand = [i for i, e in enumerate(edges) if (e.a in in_tree) != (e.b in in_tree)]
        if not cand:
            steps.append(
                snap(
                    kind="done",
                    message=f"Stopped. No edge reaches the remaining nodes, so the graph is disconnected. The tree that was reached weighs {total}.",
                    log="No frontier edges but nodes remain: graph is disconnected.",
                    done=True,
                )
            )
            return MSTTrace(algorithm="prim", steps=steps, total=total, connected=False, mst=mst)

        pick = min(cand, key=lambda i: (edges[i].w, i))
        p = edges[pick]
        steps.append(
            snap(
                kind="frontier",
                candidates=cand,
                pick=pick,
                message=(f"{len(cand)} edges cross out of the tree. " if len(cand) > 1 else "1 edge crosses out of the tree. ") + f"The cheapest is {nm(p.a)}–{nm(p.b)}, weight {p.w}.",
                log=f"Cheapest crossing edge: {nm(p.a)}–{nm(p.b)} ({p.w}).",
            )
        )

        new = p.b if p.a in in_tree else p.a
        mst.append(pick)
        in_tree.add(new)
        total += p.w
        done = len(in_tree) == n
        log = f"Added edge {nm(p.a)}–{nm(p.b)} and node {nm(new)}. Total = {total}."
        if done:
            log += " All nodes connected. MST complete."
        steps.append(
            snap(
                kind="add",
                new_node=new,
                new_edge=pick,
                message=f"Done. Every node is connected, with a minimum total weight of {total}." if done else f"{nm(new)} joins the tree through {nm(p.a)}–{nm(p.b)}. Total weight is now {total}.",
                log=log,
                done=done,
            )
        )
        if done:
            return MSTTrace(algorithm="prim", steps=steps, total=total, connected=True, mst=mst)
