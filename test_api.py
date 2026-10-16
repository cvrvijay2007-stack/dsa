import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    return TestClient(create_app(":memory:"))


def test_health_and_index(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    r = client.get("/")
    assert r.status_code == 200 and "Prim" in r.text


def test_prim_endpoint(client):
    g = client.get("/api/generate/sample").json()
    r = client.post("/api/prim", json={**g, "start": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 32 and body["connected"]


def test_prim_validation(client):
    bad = {"nodes": [{"x": 1, "y": 1}], "edges": [{"a": 0, "b": 4, "w": 2}]}
    assert client.post("/api/prim", json=bad).status_code == 422
    assert client.post("/api/prim", json={"nodes": [{"x": 1, "y": 1}], "edges": [], "start": 5}).status_code == 422


def test_random_and_parse(client):
    g = client.get("/api/generate/random", params={"n": 6, "extra": 3, "seed": 1}).json()
    assert len(g["nodes"]) == 6 and len(g["edges"]) >= 5
    r = client.post("/api/parse", json={"text": "A B 4\nB C 1"})
    assert [n["label"] for n in r.json()["nodes"]] == ["A", "B", "C"]
    assert client.post("/api/parse", json={"text": "   \n"}).status_code == 422


def test_saved_graph_crud(client):
    g = client.get("/api/generate/sample").json()
    created = client.post("/api/graphs", json={**g, "name": "Sample"}).json()
    gid = created["id"]
    assert client.get("/api/graphs").json()[0]["node_count"] == 8
    upd = client.put(f"/api/graphs/{gid}", json={**g, "name": "Renamed"}).json()
    assert upd["name"] == "Renamed"
    assert client.get(f"/api/graphs/{gid}").json()["edges"] == g["edges"]
    assert client.delete(f"/api/graphs/{gid}").status_code == 204
    assert client.get(f"/api/graphs/{gid}").status_code == 404
