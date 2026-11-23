"""MEM3 (#1029): the analysis index on a table of its own — SQLite, the standard library, no ChromaDB.

The index was a ChromaDB collection (``campaign_runs``, ``~/.eregion/analysis/chroma``), read only by
keys, never by a similarity search: its documents were embedded for nothing (docs/design/memoire.md,
§1.4). It is now one SQLite table, ``campaign_runs``, in one file (``EREGION_ANALYSIS_INDEX``, else
``~/.eregion/analysis/index.sqlite``), with an index on each key the reads use: the technique
(``prior_runs``), the campaign's state (``previous_campaign``), the run id (unique: ``get(ids=…)``,
the upsert). Its interface is the collection's, for its callers (analysis/campaign_report.py,
analysis/campaign_index.py): ``upsert``, ``count``, ``get`` by ids or by equal keys — and it answers
as the collection answered (measured on chromadb 1.5.9, tests/unit/test_analysis_index.py):

- **the rows in the order they were first put in** (``seq``, an INTEGER PRIMARY KEY, which VACUUM
  keeps): an upsert of a row already there keeps its place, a ``limit`` takes the first ones, and
  ``get(ids=…)`` answers in that order too — never the order asked —, an id it does not hold left out;
- **an upsert merges a row's keys**: a key it leaves out keeps its value;
- **a key without a value is absent** from the row: nothing is ever stored as ``None``.

**Refused at the opening** (IA1, analysis/separation.py): a path in Glorfindel's state is refused by
the caller (``check_index``); here, a file that holds Glorfindel's memory, whatever its path — its
table ``cycles``, the form MEM2 gives it (a copy, a link, a mount elsewhere). Nothing is written in it.
A file of ChromaDB (its tables ``collections``, ``embeddings``: a ``chroma.sqlite3``, the old index's or
a copy of Glorfindel's memory of today) is refused too, before anything is written (MEM3b, #1052).
A folder at the index's path is the ChromaDB index of before MEM3: refused, and said with the import
(analysis/index_import.py). A file that is not a database raises (``sqlite3.DatabaseError``): an index
that cannot be read is never an empty one.

**Not imported**: an old ChromaDB index beside the table (``chroma/``, the old default, in the same
folder) is no longer read. Until it is imported once (``python -m analysis.index_import``, which
marks the table with the source it read: ``imported``, the source resolved — the import of another
copy does not count), the report names it (campaign_report.py, ``index_note``) — never an
index read as empty in silence.

**The guard of an agent session** (HY2b, HY2c): ``sqlite3.connect`` is one of the events the audit hook
of eregion_core/store_guard.py sees. In an agent session, the operator's ~/.eregion/analysis is
refused at its opening, before a page is written: no native writer left out of the hook's sight.
"""
from __future__ import annotations

import contextlib
import sqlite3
import time
from pathlib import Path

from analysis import separation

TABLE = "campaign_runs"
# The keys of a row (what campaign_report.index_facts writes), each a column; `fact` holds the run's
# facts (JSON), `document` its summary — the text ChromaDB embedded, kept to be read by a human.
KEYS = ("campaign_id", "run_id", "ttp", "detection", "vm", "campaign_state", "campaign_started",
        "fact", "document")
# The keys a `where` may name: equal values only, as the callers ask.
WHERE = frozenset({"campaign_id", "run_id", "ttp", "detection", "vm", "campaign_state"})
# The old ChromaDB index, beside the table (its default before MEM3: ~/.eregion/analysis/chroma).
LEGACY = "chroma"
LEGACY_MARK = "chroma.sqlite3"
# The tables of a ChromaDB file (chromadb 1.5.9): never those of an index (MEM3b).
CHROMA_TABLES = frozenset({"collections", "embeddings"})
# How long a writer waits for another (the watch's report and a command by hand, at once).
BUSY_S = 30.0

_SCHEMA = (
    # No column type but the keys': a value keeps its own (a start is a float, or "" when unknown).
    f"CREATE TABLE IF NOT EXISTS {TABLE} (seq INTEGER PRIMARY KEY, run_id TEXT NOT NULL UNIQUE, "
    "campaign_id, ttp, detection, vm, campaign_state, campaign_started, fact, document)",
    f"CREATE INDEX IF NOT EXISTS {TABLE}_ttp ON {TABLE} (ttp)",
    f"CREATE INDEX IF NOT EXISTS {TABLE}_state ON {TABLE} (campaign_state)",
    # Each import of an old index (analysis/index_import.py): what it read, when, what it did.
    "CREATE TABLE IF NOT EXISTS imports (seq INTEGER PRIMARY KEY, source TEXT NOT NULL, at REAL NOT NULL, "
    "imported INTEGER NOT NULL, kept INTEGER NOT NULL, unreadable INTEGER NOT NULL)",
)


class OldIndex(RuntimeError):
    """The index's path is a folder: the ChromaDB index of before MEM3, never opened as the table."""


def legacy(path: Path) -> Path | None:
    """The old ChromaDB index beside the table (``chroma/`` in its folder), or None."""
    old = Path(path).parent / LEGACY
    return old if (old / LEGACY_MARK).is_file() else None


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {name.lower() for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _row(rid: str, document, meta) -> tuple[list[str], list]:
    """A row's columns and values: the keys of ``meta`` the table holds, none without a value; its
    document when given; its run id, the row's."""
    row = {**{k: v for k, v in (meta or {}).items() if k in KEYS and v is not None},
           **({"document": document} if document is not None else {}), "run_id": rid}
    return list(row), list(row.values())


class RunIndex:
    """The ``campaign_runs`` table of the file at ``path``, answering as the ChromaDB collection did."""

    def __init__(self, path: Path, table: str = TABLE):
        self.path = Path(path)
        self.table = separation.check_table(table)
        if self.path.is_dir():
            raise OldIndex(
                f"set EREGION_ANALYSIS_INDEX to a file (…/index.sqlite): {self.path} is a folder, the ChromaDB "
                "index of before MEM3 — no longer read; python -m analysis.index_import imports it, once")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            if separation.GLORFINDEL_COLLECTION in _tables(conn):   # IA1: the defender's memory, elsewhere
                raise separation.SharedWithGlorfindel(
                    f"set EREGION_ANALYSIS_INDEX to another file: {self.path} holds Glorfindel's memory (its "
                    f"table {separation.GLORFINDEL_COLLECTION}) — the analysis never reads nor writes it")
            if _tables(conn) & CHROMA_TABLES:   # MEM3b: a chroma.sqlite3 — the old index, or Glorfindel's memory
                raise OldIndex(
                    f"set EREGION_ANALYSIS_INDEX to a file of its own (…/index.sqlite): {self.path} is a file of "
                    "ChromaDB — the old index, or a copy of Glorfindel's memory —, never opened as the table, "
                    f"nothing written in it; an old index is imported once: python -m analysis.index_import "
                    f"{self.path.parent}")
            with conn:
                for statement in _SCHEMA:
                    conn.execute(statement)

    @contextlib.contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=BUSY_S)
        try:
            yield conn
        finally:
            conn.close()

    def _insert(self, cols: list[str]) -> str:
        return f"INSERT INTO {self.table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {self.table}").fetchone()[0]

    def upsert(self, ids, documents=None, metadatas=None) -> None:
        """Each row by its run id: put in at the end, or its keys given replaced in place — a key left
        out keeps its value, its place is kept."""
        documents = list(documents) if documents is not None else [None] * len(ids)
        metadatas = list(metadatas) if metadatas is not None else [{}] * len(ids)
        with self._connect() as conn, conn:
            for rid, document, meta in zip(ids, documents, metadatas):
                cols, values = _row(rid, document, meta)
                sets = ", ".join(f"{c} = excluded.{c}" for c in cols if c != "run_id") or "run_id = run_id"
                conn.execute(f"{self._insert(cols)} ON CONFLICT(run_id) DO UPDATE SET {sets}", values)

    def add_missing(self, ids, documents, metadatas) -> tuple[list[str], list[str]]:
        """The rows not yet here put in, in the order given; a row already here kept as it is.
        ``(the ids put in, the ids kept)``."""
        added, kept = [], []
        with self._connect() as conn, conn:
            for rid, document, meta in zip(ids, documents, metadatas):
                cols, values = _row(rid, document, meta)
                cur = conn.execute(f"{self._insert(cols)} ON CONFLICT(run_id) DO NOTHING", values)
                (added if cur.rowcount == 1 else kept).append(rid)
        return added, kept

    def get(self, ids=None, where=None, limit=None) -> dict:
        """The rows of ``ids`` (those held), or those whose keys equal ``where``'s — in the order they were
        first put in, the first ``limit``: ``{"ids": […], "metadatas": [{key: value}, …]}``."""
        clauses, args = [], []
        if ids is not None:
            ids = list(ids)
            clauses.append(f"run_id IN ({', '.join('?' * len(ids))})" if ids else "0")
            args += ids
        for key, value in (where or {}).items():
            if key not in WHERE:
                raise ValueError(f"the index is read by {sorted(WHERE)}, not by {key!r}")
            clauses.append(f"{key} = ?")
            args.append(value)
        sql = f"SELECT {', '.join(KEYS)} FROM {self.table}"
        sql += f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql += " ORDER BY seq"
        if limit is not None:
            sql += " LIMIT ?"
            args.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        metas = [{k: v for k, v in zip(KEYS, row) if v is not None and k != "document"} for row in rows]
        return {"ids": [m["run_id"] for m in metas], "metadatas": metas}

    def record_import(self, source: str, imported: int, kept: int, unreadable: int) -> None:
        with self._connect() as conn, conn:
            conn.execute("INSERT INTO imports (source, at, imported, kept, unreadable) VALUES (?, ?, ?, ?, ?)",
                         (source, time.time(), imported, kept, unreadable))

    def imported(self, source: Path) -> bool:
        """The old index at ``source`` was imported into this table (analysis/index_import.py): one of
        the sources recorded, resolved, is ``source`` resolved — the import of another copy is not its."""
        with self._connect() as conn:
            sources = [s for (s,) in conn.execute("SELECT source FROM imports")]
        return any(_same(s, source) for s in sources)


def _same(a, b) -> bool:
    return Path(a).expanduser().resolve() == Path(b).expanduser().resolve()
