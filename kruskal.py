"""Kruskal's algorithm, recorded as a sequence of visualisation steps.

1. ``start``    - sort every edge by weight; each node is its own tree.
2. ``consider`` - take the cheapest edge not yet checked (``pick``); ``candidates``
                  is the remaining queue in sorted order, including the pick.
3. ``add``      - its ends are in different trees, so keep it and merge them; or
   ``skip``     - its ends are already connected, so it would form a cycle.

Steps 2-3 repeat until the tree has n-1 edges (``add`` carries ``done``) or the
queue runs out first - the graph is disconnected, and a final ``done`` step
reports the weight of the spanning forest.

Ties on weight are broken by the lowest edge index, matching Prim's trace.
"""

from __future__ import annotations

from .models import Graph, MSTTrace, Step
from .prim import label


class DisjointSet:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.size = [1] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]
        return True


def kruskal_trace(graph: Graph) -> MSTTrace:
    n = len(graph.nodes)
    if n == 0:
        return MSTTrace(algorithm="kruskal", steps=[], total=0, connected=True, mst=[])

    nm = lambda i: label(graph, i)  # noqa: E731
    edges = graph.edges
    order = sorted(range(len(edges)), key=lambda i: (edges[i].w, i))
    ds = DisjointSet(n)
    touched: set[int] = set()
    mst: list[int] = []
    skipped: list[int] = []
    total = 0
    steps: list[Step] = []

    def snap(**kw) -> Step:
        return Step(in_tree=sorted(touched), mst=list(mst), skipped=list(skipped), total=total, **kw)

    if n == 1:
        steps.append(snap(kind="start", message="Done. A single node is already its own spanning tree.",
                          log="Only one node: nothing to connect.", done=True))
        return MSTTrace(algorithm="kruskal", steps=steps, total=0, connected=True, mst=[])

    count = len(edges)
    steps.append(
        snap(
            kind="start",
            candidates=order,
            message=f"Sort all {count} edge{'s' if count != 1 else ''} from cheapest to most expensive. Every node starts as its own tree.",
            log=f"Sorted {count} edge{'s' if count != 1 else ''} by weight.",
        )
    )

    for pos, i in enumerate(order):
        e = edges[i]
        a, b = nm(e.a), nm(e.b)
        joins = ds.find(e.a) != ds.find(e.b)
        steps.append(
            snap(
                kind="consider",
                pick=i,
                candidates=order[pos:],
                message=f"Next cheapest edge is {a}–{b}, weight {e.w}. "
                + (f"{a} and {b} are in different trees." if joins else f"{a} and {b} are already connected."),
                log=f"Check {a}–{b} ({e.w}).",
            )
        )
        if joins:
            ds.union(e.a, e.b)
            mst.append(i)
            touched.update((e.a, e.b))
            total += e.w
            done = len(mst) == n - 1
            log = f"Kept {a}–{b}. Total = {total}."
            if done:
                log += " All nodes connected. MST complete."
            steps.append(
                snap(
                    kind="add",
                    new_edge=i,
                    candidates=order[pos + 1:],
                    message=f"Done. Every node is connected, with a minimum total weight of {total}." if done
                    else f"Kept {a}–{b}, joining two trees. Total weight is now {total}.",
                    log=log,
                    done=done,
                )
            )
            if done:
                return MSTTrace(algorithm="kruskal", steps=steps, total=total, connected=True, mst=mst)
        else:
            skipped.append(i)
            steps.append(
                snap(
                    kind="skip",
                    candidates=order[pos + 1:],
                    message=f"Skipped {a}–{b}. It would close a cycle, since {a} and {b} are already in one tree.",
                    log=f"Skipped {a}–{b}: would form a cycle.",
                )
            )

    trees = len({ds.find(i) for i in range(n)})
    steps.append(
        snap(
            kind="done",
            message=f"Stopped. No edges left, so the graph is disconnected into {trees} pieces. The spanning forest weighs {total}.",
            log="Edge queue empty but nodes remain apart: graph is disconnected.",
            done=True,
        )
    )
    return MSTTrace(algorithm="kruskal", steps=steps, total=total, connected=False, mst=mst)
