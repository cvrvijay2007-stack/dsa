"""Validation, limits and persistence edge cases for the API and helpers."""

import time

import pytest
from fastapi.testclient import TestClient

from app.graphs import parse_edge_list, random_graph
from app.main import create_app
from app.models import SavedGraphIn
from app.prim import prim_trace
from app.storage import GraphStore


@pytest.fixture
def client():
    return TestClient(create_app(":memory:"))


def two_nodes(**edge):
    return {"nodes": [{"x": 10, "y": 10}, {"x": 50, "y": 50}], "edges": [{"a": 0, "b": 1, "w": 3, **edge}]}


# ---------- request validation ----------

@pytest.mark.parametrize("w", [0, -4, 10000])
def test_prim_rejects_out_of_range_weights(client, w):
    assert client.post("/api/prim", json=two_nodes(w=w)).status_code == 422


def test_prim_rejects_self_loop(client):
    r = client.post("/api/prim", json=two_nodes(b=0))
    assert r.status_code == 422
    assert "self-loop" in r.text


@pytest.mark.parametrize("node", [{"x": -1, "y": 10}, {"x": 801, "y": 10}, {"x": 10, "y": 501}])
def test_prim_rejects_nodes_off_canvas(client, node):
    body = {"nodes": [node], "edges": []}
    assert client.post("/api/prim", json=body).status_code == 422


def test_prim_rejects_too_many_nodes(client):
    body = {"nodes": [{"x": 1, "y": 1}] * 201, "edges": []}
    assert client.post("/api/prim", json=body).status_code == 422


def test_prim_empty_graph_returns_empty_trace(client):
    r = client.post("/api/prim", json={"nodes": [], "edges": []})
    assert r.status_code == 200
    assert r.json() == {"algorithm": "prim", "steps": [], "total": 0, "connected": True, "mst": []}


def test_prim_duplicate_parallel_edges_uses_cheapest(client):
    body = {
        "nodes": [{"x": 1, "y": 1}, {"x": 2, "y": 2}],
        "edges": [{"a": 0, "b": 1, "w": 9}, {"a": 1, "b": 0, "w": 2}],
    }
    assert client.post("/api/prim", json=body).json()["total"] == 2


@pytest.mark.parametrize("q", ["n=1", "n=31", "extra=-1", "extra=101", "n=abc"])
def test_random_param_bounds(client, q):
    assert client.get(f"/api/generate/random?{q}").status_code == 422


def test_random_is_reproducible_with_seed(client):
    a = client.get("/api/generate/random?n=12&seed=7").json()
    b = client.get("/api/generate/random?n=12&seed=7").json()
    assert a == b


def test_random_graph_is_connected():
    for seed in range(30):
        g = random_graph(15, 5, seed=seed)
        assert prim_trace(g, 0).connected


def test_parse_too_long_text_rejected(client):
    assert client.post("/api/parse", json={"text": "A B 1\n" * 10_000}).status_code == 422


def test_parse_too_many_nodes_rejected(client):
    text = "\n".join(f"n{i}" for i in range(201))
    r = client.post("/api/parse", json={"text": text})
    assert r.status_code == 422 and "max 200" in r.text


# ---------- parser details ----------

@pytest.mark.parametrize(
    "line, weight",
    [("A B 4.6", 5), ("A B 0.2", 1), ("A B -3", 1), ("A B x", 1), ("A B", 1), ("A>B>7", 7), ("A – B 2", 2), ("A;B;3", 3), ("1-2 5", 5), ("A--B 6", 6), ("A B 20000", 9999), ("A B inf", 9999), ("A B nan", 1)],
)
def test_parse_weight_rules(line, weight):
    g = parse_edge_list(line)
    assert [e.w for e in g.edges] == [weight]


def test_parse_trims_long_labels_and_blank_lines():
    g = parse_edge_list("\n\n   " + "x" * 40 + " y 2\n\n")
    assert len(g.nodes[0].label) == 24
    assert len(g.edges) == 1


def test_parse_layout_stays_on_canvas():
    g = parse_edge_list("\n".join(f"n{i} n{i + 1} 1" for i in range(60)))
    assert all(0 <= n.x <= 800 and 0 <= n.y <= 500 for n in g.nodes)


# ---------- saved graphs ----------

def test_saved_graph_validation(client):
    g = client.get("/api/generate/sample").json()
    assert client.post("/api/graphs", json={**g, "name": ""}).status_code == 422
    assert client.post("/api/graphs", json={**g, "name": "x" * 81}).status_code == 422
    assert client.post("/api/graphs", json={"name": "bad", "nodes": [], "edges": [{"a": 0, "b": 1, "w": 1}]}).status_code == 422


def test_saved_graph_missing_ids(client):
    g = client.get("/api/generate/sample").json()
    assert client.get("/api/graphs/999").status_code == 404
    assert client.put("/api/graphs/999", json={**g, "name": "x"}).status_code == 404
    assert client.delete("/api/graphs/999").status_code == 404


def test_saved_names_are_trimmed_and_list_is_newest_first(client):
    g = client.get("/api/generate/sample").json()
    client.post("/api/graphs", json={**g, "name": "  first  "})
    time.sleep(1.05)  # updated_at has second precision
    client.post("/api/graphs", json={**g, "name": "second"})
    names = [x["name"] for x in client.get("/api/graphs").json()]
    assert names == ["second", "first"]


def test_labels_survive_round_trip(client):
    g = client.post("/api/parse", json={"text": "Paris Lyon 4"}).json()
    gid = client.post("/api/graphs", json={**g, "name": "cities"}).json()["id"]
    assert [n["label"] for n in client.get(f"/api/graphs/{gid}").json()["nodes"]] == ["Paris", "Lyon"]


def test_store_persists_to_disk(tmp_path):
    db = tmp_path / "sub" / "graphs.db"
    s1 = GraphStore(db)
    created = s1.create(SavedGraphIn(name="keep", nodes=[{"x": 1, "y": 1}], edges=[]))
    s2 = GraphStore(db)
    assert s2.get(created.id).name == "keep"


# ---------- frontend serving ----------

def test_static_assets_served_without_stale_cache(client):
    for path in ("/", "/static/app.js", "/static/styles.css"):
        r = client.get(path)
        assert r.status_code == 200
        assert r.headers["cache-control"] == "no-cache"
    assert client.get("/static/missing.js").status_code == 404


def test_openapi_docs_available(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/api/prim", "/api/parse", "/api/graphs", "/api/graphs/{gid}"} <= set(paths)


# ---------- performance ----------

def test_large_graph_is_fast():
    g = random_graph(30, 100, seed=3)
    big = g.model_copy(update={"nodes": g.nodes * 6})  # 180 nodes, edges only among first 30
    t0 = time.perf_counter()
    trace = prim_trace(big, 0)
    assert time.perf_counter() - t0 < 2
    assert not trace.connected


def test_compiled_tailwind_is_served(client):
    r = client.get("/static/tailwind.css")
    assert r.status_code == 200 and "lg\\:grid-cols" in r.text
    assert "cdn.tailwindcss.com" not in client.get("/").text
