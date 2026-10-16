import pytest

from app.graphs import parse_edge_list, random_graph, sample_graph
from app.models import Edge, Graph, Node
from app.prim import prim_trace


def brute_mst_weight(graph: Graph) -> int:
    """Kruskal with union-find, as an independent reference."""
    parent = list(range(len(graph.nodes)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    total = 0
    for e in sorted(graph.edges, key=lambda e: e.w):
        ra, rb = find(e.a), find(e.b)
        if ra != rb:
            parent[ra] = rb
            total += e.w
    return total


def test_sample_graph_mst_weight():
    t = prim_trace(sample_graph(), 0)
    assert t.connected
    assert t.total == 32
    assert len(t.mst) == 7
    assert t.steps[0].kind == "start"
    assert t.steps[-1].done and t.steps[-1].message == "Done. Every node is connected, with a minimum total weight of 32."


def test_step_shape_alternates_frontier_add():
    t = prim_trace(sample_graph(), 0)
    kinds = [s.kind for s in t.steps]
    assert kinds == ["start"] + ["frontier", "add"] * 7
    for f, a in zip(t.steps[1::2], t.steps[2::2]):
        assert f.pick in f.candidates
        assert a.new_edge == f.pick


def test_pick_is_cheapest_with_lowest_index_tiebreak():
    g = Graph(
        nodes=[Node(x=10, y=10), Node(x=20, y=20), Node(x=30, y=30)],
        edges=[Edge(a=0, b=2, w=5), Edge(a=0, b=1, w=5)],
    )
    t = prim_trace(g, 0)
    assert t.steps[1].pick == 0


@pytest.mark.parametrize("seed", range(25))
def test_matches_kruskal_on_random_graphs(seed):
    g = random_graph(10, 12, seed=seed)
    for start in (0, 5, 9):
        assert prim_trace(g, start).total == brute_mst_weight(g)


def test_disconnected_graph():
    g = Graph(
        nodes=[Node(x=10, y=10), Node(x=20, y=20), Node(x=30, y=30), Node(x=40, y=40)],
        edges=[Edge(a=0, b=1, w=3), Edge(a=2, b=3, w=1)],
    )
    t = prim_trace(g, 0)
    assert not t.connected
    assert t.total == 3
    assert t.steps[-1].kind == "done"
    assert "disconnected" in t.steps[-1].message


def test_single_and_empty():
    assert prim_trace(Graph(), 0).steps == []
    t = prim_trace(Graph(nodes=[Node(x=1, y=1)]), 0)
    assert t.connected and t.steps[0].done


def test_parse_edge_list():
    g = parse_edge_list("A B 4\nB-C 2\nC,A,9\nD\nA B 7\nX X 3\nE F")
    assert [n.label for n in g.nodes] == ["A", "B", "C", "D", "X", "E", "F"]
    pairs = [(e.a, e.b, e.w) for e in g.edges]
    assert pairs == [(0, 1, 4), (1, 2, 2), (2, 0, 9), (5, 6, 1)]


def test_messages_use_labels():
    g = parse_edge_list("Paris Lyon 4\nLyon Nice 3")
    t = prim_trace(g, 0)
    assert "Paris" in t.steps[0].log
    assert "Lyon–Nice" in t.steps[3].message and "The cheapest is" in t.steps[3].message
