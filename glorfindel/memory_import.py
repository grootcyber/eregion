"""MEM2 (#1027, Q3): the cycles of a copy of the memory by distance (ChromaDB), imported once into the
memory by keys (SQLite, glorfindel/memory_keys.py) — offline.

    python -m glorfindel.memory_import <the copy's cycles folder> [--to <cycles.sqlite3>]

Why: the memory stays continuous when the switch is turned on (ENQ5) — the same cycles, ranked
otherwise —, and Jonathan's run end to end compares the same memory. Pushing it on Imladris is his
gesture (docs/operations.md, « La mémoire par clés »).

**What it reads**: a copy, never the store of a running watch — read as scripts/memory_replay.py reads
one (its `refusal`): a path in the operator's ~/.glorfindel, ~/.eregion or ~/.annatar, under the home
the system gives him and under HOME, as given and resolved, is refused; so is a copy one of whose files
or folders leads there through a link, and a folder that is no store (no ``chroma.sqlite3``). Opened by
the embedded client, its telemetry off, no model (no embedding is read nor computed): ChromaDB may
write in what it opens, a copy only. Its collection ``cycles`` is read whole, its texts and metadata as
they are — the date each was given (SEC17) kept, an undated one left undated (the B2 floor dates it at
retrieval, as today), its identifier kept.

**What it writes**: the table only (``--to``, else the memory by keys' own:
``~/.eregion/watch-memory/cycles.sqlite3``), the cycles in the order of their dates (at equal dates,
the copy's): a cycle already there, by its identifier, kept as it is. Run twice, the table is the same;
a newer copy adds only what it holds more. Each import is recorded in the table (``imports``), with the
source it read, resolved. **Refused** (exit 2, nothing written) too: a table in the copy's folder, or a
file the memory by keys does not open (memory_keys.NotTheMemory).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from eregion_core import store_guard
from glorfindel import memory, memory_keys

REFUSED = 2
COLLECTION = "cycles"


class Refused(Exception):
    """What the import will not read or write: said, exit 2."""


def _inside(path: Path, folder: Path) -> bool:
    p, f = Path(path).resolve(), Path(folder).resolve()
    return p == f or f in p.parents


def refusal(source, dest, homes=None) -> str | None:
    """Why the import does not run, or None — before anything is opened or written."""
    homes = (store_guard.operator_home(), Path.home()) if homes is None else homes
    roots = tuple(dict.fromkeys(root for home in homes for root in store_guard.roots_of(home)))
    found = store_guard.located(source, roots)
    if found is not None:
        return (f"refusé : {source} est dans le ~/{found[1]} de l'opérateur. Une copie seulement : celle de "
                "make imladris-pull, extraite dans un dossier à part (l'en-tête de ce module).")
    for top, folders, files in os.walk(source):
        for name in files + folders:
            linked = store_guard.located(os.path.join(top, name), roots)
            if linked is not None:
                return (f"refusé : un fichier de {source} mène par un lien au ~/{linked[1]} de l'opérateur. "
                        "Une copie seulement, sans lien vers l'original.")
    if not (Path(source) / "chroma.sqlite3").is_file():
        return f"refusé : {source} n'est pas la copie d'un magasin (pas de chroma.sqlite3) ; rien n'est créé."
    if _inside(dest, source):
        return (f"refusé : la table ({dest}) s'écrirait dans la copie ({source}) ; l'import n'écrit jamais "
                "dans ce qu'il lit. --to ailleurs.")
    return None


def read_copy(source) -> list[tuple[str, str, dict]]:
    """The cycles of the copy, (id, document, metadata), in the order of their dates (the B2 floor for an
    undated one, as the memory dates it) — the copy's order at equal dates."""
    os.environ["ANONYMIZED_TELEMETRY"] = "False"
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(path=str(source), settings=Settings(anonymized_telemetry=False))
    try:
        collection = client.get_collection(COLLECTION)
    except Exception as exc:   # chromadb 1.x: NotFoundError, ValueError before
        raise Refused(f"refusé : {source} n'a pas de collection « {COLLECTION} » ({type(exc).__name__}).") from None
    got = collection.get(include=["metadatas", "documents"])
    rows = [(cid, document or "", dict(meta or {}))
            for cid, document, meta in zip(got["ids"], got["documents"], got["metadatas"])]
    return [row for _i, row in sorted(enumerate(rows), key=lambda p: (memory._stored_at(p[1][2]), p[0]))]


def run(source, dest, say=print) -> int:
    """Import ``source`` into the table at ``dest``: the exit code, what was done said."""
    source, dest = Path(source), Path(dest)
    try:
        if why := refusal(source, dest):
            raise Refused(why)
        table = memory_keys.KeyedMemory(path=dest)
        rows = read_copy(source)
    except (Refused, memory_keys.NotTheMemory) as exc:
        say(str(exc))
        return REFUSED
    added, kept = table.add_imported(rows, str(source.resolve()))
    real = sum(meta.get("source") == "real" for _cid, _doc, meta in rows)
    undated = sum(not memory._dated(meta) for _cid, _doc, meta in rows)
    say(f"mémoire par clés : {dest}")
    say(f"copie lue : {source} — {len(rows)} cycle(s), dont {real} réel(s) et {undated} sans date (datés au "
        "plancher B2 à la lecture)")
    say(f"{added} cycle(s) importé(s) ; {kept} déjà dans la table, gardé(s) tel(s) quel(s)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m glorfindel.memory_import", description=__doc__.splitlines()[0])
    ap.add_argument("source", type=Path, help="the cycles folder of a COPY of the memory (make imladris-pull, extracted)")
    ap.add_argument("--to", type=Path, default=None,
                    help="the table (default: the memory by keys' own, ~/.eregion/watch-memory/cycles.sqlite3)")
    a = ap.parse_args(argv)
    return run(a.source, a.to or memory_keys.DEFAULT_PATH)


if __name__ == "__main__":
    sys.exit(main())
