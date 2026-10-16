import pytest
from fastapi.testclient import TestClient

from app.graphs import parse_edge_list, random_graph, sample_graph
from app.kruskal import DisjointSet, kruskal_trace
from app.main import create_app
from app.models import Edge, Graph, Node
from app.prim import prim_trace


def nodes(n):
    return [Node(x=10 + i, y=10 + i) for i in range(n)]


def test_sample_graph():
    t = kruskal_trace(sample_graph())
    assert t.algorithm == "kruskal"
    assert t.connected and t.total == 32 and len(t.mst) == 7
    # start + 8 checked edges x (consider, decision); the 9th-cheapest edge is never needed
    assert len(t.steps) == 17
    assert [s.kind for s in t.steps].count("skip") == 1
    assert t.steps[-1].done and t.steps[-1].message == "Done. Every node is connected, with a minimum total weight of 32."


def test_edges_checked_in_weight_order():
    t = kruskal_trace(sample_graph())
    g = sample_graph()
    picks = [s.pick for s in t.steps if s.kind == "consider"]
    weights = [g.edges[i].w for i in picks]
    assert weights == sorted(weights)
    assert picks[0] == 10  # F-G, weight 1


def test_step_shape_and_queue():
    t = kruskal_trace(sample_graph())
    assert t.steps[0].kind == "start"
    assert len(t.steps[0].candidates) == 13
    for c, d in zip(t.steps[1::2], t.steps[2::2]):
        assert c.kind == "consider" and d.kind in ("add", "skip")
        assert c.candidates[0] == c.pick
        assert d.candidates == c.candidates[1:]
        if d.kind == "add":
            assert d.new_edge == c.pick and d.mst[-1] == c.pick
        else:
            assert d.skipped[-1] == c.pick and "cycle" in d.message


def test_skipped_edge_is_the_cycle_edge():
    g = sample_graph()
    t = kruskal_trace(g)
    skip = next(s for s in t.steps if s.kind == "skip")
    e = g.edges[skip.skipped[0]]
    assert (e.a, e.b, e.w) == (2, 3, 7)  # C-D closes C-H-D


def test_tie_break_lowest_index():
    g = Graph(nodes=nodes(3), edges=[Edge(a=0, b=2, w=5), Edge(a=0, b=1, w=5), Edge(a=1, b=2, w=5)])
    t = kruskal_trace(g)
    assert t.mst == [0, 1]


@pytest.mark.parametrize("seed", range(40))
def test_matches_prim_on_random_graphs(seed):
    g = random_graph(12, 15, seed=seed)
    assert kruskal_trace(g).total == prim_trace(g, seed % 12).total


def test_disconnected_forest():
    g = Graph(nodes=nodes(5), edges=[Edge(a=0, b=1, w=3), Edge(a=2, b=3, w=1)])
    t = kruskal_trace(g)
    assert not t.connected
    assert t.total == 4  # Kruskal builds the whole forest, unlike Prim
    assert t.steps[-1].kind == "done"
    assert "3 pieces" in t.steps[-1].message


def test_single_and_empty():
    assert kruskal_trace(Graph()).steps == []
    t = kruskal_trace(Graph(nodes=nodes(1)))
    assert t.connected and t.steps[0].done


def test_no_edges():
    t = kruskal_trace(Graph(nodes=nodes(2)))
    assert [s.kind for s in t.steps] == ["start", "done"]
    assert "Sort all 0 edges" in t.steps[0].message


def test_labels_in_messages():
    t = kruskal_trace(parse_edge_list("Paris Lyon 4\nLyon Nice 3"))
    assert t.steps[1].message.startswith("Next cheapest edge is Lyon–Nice, weight 3.")


def test_disjoint_set():
    ds = DisjointSet(4)
    assert ds.union(0, 1) and ds.union(2, 3)
    assert not ds.union(1, 0)
    assert ds.union(1, 3)
    assert len({ds.find(i) for i in range(4)}) == 1


# ---------- API ----------

@pytest.fixture
def client():
    return TestClient(create_app(":memory:"))


def test_mst_endpoint_dispatches(client):
    g = client.get("/api/generate/sample").json()
    prim = client.post("/api/mst", json={**g, "algorithm": "prim", "start": 2}).json()
    kr = client.post("/api/mst", json={**g, "algorithm": "kruskal"}).json()
    assert prim["algorithm"] == "prim" and kr["algorithm"] == "kruskal"
    assert prim["total"] == kr["total"] == 32
    assert len(kr["steps"]) == 17


def test_kruskal_ignores_start(client):
    g = client.get("/api/generate/sample").json()
    assert client.post("/api/mst", json={**g, "algorithm": "kruskal", "start": 99}).status_code == 200
    assert client.post("/api/mst", json={**g, "algorithm": "prim", "start": 99}).status_code == 422


def test_unknown_algorithm_rejected(client):
    g = client.get("/api/generate/sample").json()
    assert client.post("/api/mst", json={**g, "algorithm": "dijkstra"}).status_code == 422


def test_dedicated_endpoints(client):
    g = client.get("/api/generate/sample").json()
    assert client.post("/api/kruskal", json=g).json()["algorithm"] == "kruskal"
    assert client.post("/api/prim", json={**g, "algorithm": "kruskal"}).json()["algorithm"] == "prim"
