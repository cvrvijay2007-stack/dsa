"""SQLite persistence for saved graphs."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .models import Graph, SavedGraph, SavedGraphIn, SavedGraphSummary


class GraphStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        # A single shared connection keeps ":memory:" databases alive for tests.
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._tx() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS graphs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    data TEXT NOT NULL,
                    node_count INTEGER NOT NULL,
                    edge_count INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )

    @contextmanager
    def _tx(self):
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def list(self) -> list[SavedGraphSummary]:
        rows = self._conn.execute(
            "SELECT id, name, node_count, edge_count, updated_at FROM graphs ORDER BY updated_at DESC, id DESC"
        ).fetchall()
        return [SavedGraphSummary(**dict(r)) for r in rows]

    def get(self, gid: int) -> SavedGraph | None:
        r = self._conn.execute("SELECT * FROM graphs WHERE id = ?", (gid,)).fetchone()
        if not r:
            return None
        g = Graph.model_validate_json(r["data"])
        return SavedGraph(id=r["id"], name=r["name"], updated_at=r["updated_at"], nodes=g.nodes, edges=g.edges)

    def create(self, item: SavedGraphIn) -> SavedGraph:
        data = Graph(nodes=item.nodes, edges=item.edges).model_dump_json()
        with self._tx() as c:
            cur = c.execute(
                "INSERT INTO graphs (name, data, node_count, edge_count, updated_at) VALUES (?, ?, ?, ?, ?)",
                (item.name.strip(), data, len(item.nodes), len(item.edges), self._now()),
            )
        return self.get(cur.lastrowid)  # type: ignore[return-value]

    def update(self, gid: int, item: SavedGraphIn) -> SavedGraph | None:
        data = Graph(nodes=item.nodes, edges=item.edges).model_dump_json()
        with self._tx() as c:
            cur = c.execute(
                "UPDATE graphs SET name = ?, data = ?, node_count = ?, edge_count = ?, updated_at = ? WHERE id = ?",
                (item.name.strip(), data, len(item.nodes), len(item.edges), self._now(), gid),
            )
        return self.get(gid) if cur.rowcount else None

    def delete(self, gid: int) -> bool:
        with self._tx() as c:
            cur = c.execute("DELETE FROM graphs WHERE id = ?", (gid,))
        return cur.rowcount > 0

