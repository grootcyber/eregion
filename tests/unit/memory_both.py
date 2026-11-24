"""MEM2 (#1027): the tests of the memory, in both positions of its switch (GLORFINDEL_MEMORY).

``MODES``: the memory by distance (ChromaDB, today's, the switch off) and the memory by keys (SQLite).
What a test reads or writes past the interface — a cycle stored as before SEC17 or SEC-I, the metadata
kept — goes through these helpers, whichever the memory.
"""
from __future__ import annotations

import json

from glorfindel import memory, memory_keys

MODES = (memory.DISTANCE, memory.KEYS)


def at_path(tmp_path, mode: str, name: str = "cycles"):
    """Where a test's memory lives: a folder for ChromaDB, a file for SQLite."""
    return tmp_path / name if mode == memory.DISTANCE else tmp_path / f"{name}.sqlite3"


def raw_add(mem, cid: str, document: str, meta: dict) -> None:
    """A cycle put in as it was stored by an older code (no date, no VM…), never through `store`."""
    if isinstance(mem, memory_keys.KeyedMemory):
        mem.add_imported([(cid, document, meta)], "test")
    else:
        mem._collection.add(ids=[cid], documents=[document], metadatas=[meta])


def metas(mem) -> list[dict]:
    """The metadata of every cycle, in the order they were stored."""
    if isinstance(mem, memory_keys.KeyedMemory):
        with mem._db() as db:
            return [json.loads(m) for (m,) in db.execute(f"SELECT meta FROM {memory_keys.TABLE} ORDER BY seq")]
    return list(mem._collection.get(include=["metadatas"])["metadatas"])
