"""FastAPI app: minimum spanning tree API (Prim and Kruskal) plus the static frontend."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .graphs import parse_edge_list, random_graph, sample_graph
from .kruskal import kruskal_trace
from .models import Graph, MSTRequest, MSTTrace, ParseRequest, SavedGraph, SavedGraphIn, SavedGraphSummary
from .prim import prim_trace
from .storage import GraphStore

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
DB_PATH = os.environ.get("PRIMS_DB", str(ROOT / "data" / "graphs.db"))


def create_app(db_path: str = DB_PATH) -> FastAPI:
    app = FastAPI(title="MST Visualizer API", version="1.0.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    store = GraphStore(db_path)

    @app.middleware("http")
    async def revalidate_frontend(request: Request, call_next):
        # Frontend files are small; make browsers revalidate so edits show on reload.
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/api/mst", response_model=MSTTrace)
    def run_mst(req: MSTRequest) -> MSTTrace:
        """Step-by-step trace of Prim's or Kruskal's algorithm."""
        if req.algorithm == "kruskal":
            return kruskal_trace(req)
        if req.nodes and req.start >= len(req.nodes):
            raise HTTPException(422, "start node out of range")
        return prim_trace(req, req.start)

    @app.post("/api/prim", response_model=MSTTrace)
    def run_prim(req: MSTRequest) -> MSTTrace:
        return run_mst(req.model_copy(update={"algorithm": "prim"}))

    @app.post("/api/kruskal", response_model=MSTTrace)
    def run_kruskal(req: MSTRequest) -> MSTTrace:
        return run_mst(req.model_copy(update={"algorithm": "kruskal"}))

    @app.get("/api/generate/sample", response_model=Graph)
    def gen_sample() -> Graph:
        return sample_graph()

    @app.get("/api/generate/random", response_model=Graph)
    def gen_random(
        n: int = Query(8, ge=2, le=30),
        extra: int = Query(6, ge=0, le=100),
        seed: int | None = None,
    ) -> Graph:
        return random_graph(n, extra, seed)

    @app.post("/api/parse", response_model=Graph)
    def parse(req: ParseRequest) -> Graph:
        try:
            g = parse_edge_list(req.text)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        if not g.nodes:
            raise HTTPException(422, "No edges found. Write one edge per line, like 'A B 4'.")
        return g

    @app.get("/api/graphs", response_model=list[SavedGraphSummary])
    def list_graphs() -> list[SavedGraphSummary]:
        return store.list()

    @app.post("/api/graphs", response_model=SavedGraph, status_code=201)
    def create_graph(item: SavedGraphIn) -> SavedGraph:
        return store.create(item)

    @app.get("/api/graphs/{gid}", response_model=SavedGraph)
    def get_graph(gid: int) -> SavedGraph:
        g = store.get(gid)
        if not g:
            raise HTTPException(404, "Graph not found")
        return g

    @app.put("/api/graphs/{gid}", response_model=SavedGraph)
    def update_graph(gid: int, item: SavedGraphIn) -> SavedGraph:
        g = store.update(gid, item)
        if not g:
            raise HTTPException(404, "Graph not found")
        return g

    @app.delete("/api/graphs/{gid}", status_code=204)
    def delete_graph(gid: int) -> None:
        if not store.delete(gid):
            raise HTTPException(404, "Graph not found")

    if FRONTEND.is_dir():
        app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            return FileResponse(FRONTEND / "index.html")

    return app


app = create_app()
