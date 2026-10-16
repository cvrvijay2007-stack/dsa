# MST Visualizer — Prim's and Kruskal's

Interactive, step-by-step visualizer for minimum spanning tree algorithms.
Python (FastAPI) backend computes every step; vanilla HTML/JS + Tailwind frontend draws them.

## Run

```bash
./run.sh
```

Open http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs.

## Use

- **Pick an algorithm** with the Prim's / Kruskal's switch (remembered between visits).
  - *Prim's*: grow one tree from a start node, always taking the cheapest edge leaving it.
  - *Kruskal's*: check every edge cheapest first, keep it unless it closes a cycle.
- **Edit on the canvas:** click empty space to add a node, drag to move, click two nodes to connect,
  click a weight to change it, double-click a node or edge to delete, Escape cancels a selection.
- **Edge list tab:** one `node node weight` per line (e.g. `A B 4`), then *Build graph from list*.
- **Play:** play / pause, step, step back, reset, the scrubber, or click any entry in the Steps tab.
  Keys: `Space` play/pause, `←` `→` step, `R` reset.
- **Saved tab:** graphs are stored in SQLite (`data/graphs.db`; override with `PRIMS_DB`).

## Layout

```
backend/app/
  main.py      FastAPI routes + serves the frontend
  prim.py      Prim's algorithm as a step trace
  kruskal.py   Kruskal's algorithm (union-find) as a step trace
  graphs.py    sample / random graphs, edge-list parser
  storage.py   SQLite store for saved graphs
  models.py    Pydantic schemas
backend/tests/ unit + API tests (pytest)
frontend/      index.html, app.js, styles.css, tailwind.css (compiled)
e2e/           Playwright browser tests against a real server
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/mst` | `{nodes, edges, algorithm: "prim"\|"kruskal", start}` → step trace |
| POST | `/api/prim`, `/api/kruskal` | same, algorithm fixed |
| GET | `/api/generate/sample` | built-in 8-node example |
| GET | `/api/generate/random?n=8&extra=6&seed=` | random connected graph |
| POST | `/api/parse` | `{text}` edge list → graph |
| GET/POST | `/api/graphs` | list / save graphs |
| GET/PUT/DELETE | `/api/graphs/{id}` | open / update / delete |

## Test

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
cd backend && ../.venv/bin/python -m pytest -q   # unit + API
cd ../e2e && ../.venv/bin/python -m pytest -q    # browser end-to-end
```

## Styling

Tailwind is compiled ahead of time so the app runs offline. After changing utility classes in
`index.html` or `app.js`, rebuild:

```bash
cd frontend && npm install && npm run build:css
```
