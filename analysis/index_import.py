"""MEM3 (#1029): the old ChromaDB index of the analysis, imported once into its table — offline.

    python -m analysis.index_import <old index> [--to <index.sqlite>]

On Imladris (Jonathan; once the watch runs a version with MEM3, and before MEM4 takes chromadb out of
the image — this command needs it):

    make imladris-ssh
    docker exec eregion-watch python -m analysis.index_import /root/.eregion/analysis/chroma

Why: ``campaign_index --all`` does not compute again a run whose exercise window is purged (a week
after its end, eregion_core/exercise.py ``PURGE_AFTER_S``): its decision would be unknown. The facts
the old index holds — those its reports saw — are brought over as they are.

**What it reads**: the old index (a folder with ``chroma.sqlite3``), never opened in place. Its files
are copied first into a working folder of the system's temporary directory (removed at the end), and
ChromaDB opens that copy only — its telemetry off, no model, no network: it may write in what it opens
(its sqlite, its log), never in the folder given. Its collection ``campaign_runs`` is read whole, in
its own order (the order its rows were first put in), which the table keeps.

**What it writes**: the table only (``--to``, else the report's: ``EREGION_ANALYSIS_INDEX``, else
``~/.eregion/analysis/index.sqlite``) — each row not yet there, at the end, in that order; a row
already there (written since, by a report) kept as it is, and named. A row whose facts cannot be read
(``campaign_report.fact_of``) is never written: named, left. The import is recorded in the table: the
reports stop saying the old index is not imported. Run twice, the table is the same.

**Refused** (exit 2, nothing written): a folder that is no ChromaDB index, or without the collection
``campaign_runs``; one that holds a link (ChromaDB would follow it, out of the copy); one in
Glorfindel's state, or a table in it or holding Glorfindel's memory (IA1, analysis/separation.py); a
table in the folder given, or that folder itself — the import never writes in the copy it reads.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from analysis import campaign_report as cr
from analysis import run_index, separation

REFUSED = 2


class Refused(Exception):
    """What the import will not read or write: said, exit 2."""


def _inside(path: Path, folder: Path) -> bool:
    p, f = Path(path).resolve(), Path(folder).resolve()
    return p == f or f in p.parents


def refusal(source: Path, dest: Path) -> str | None:
    """Why the import does not run, or None — before anything is opened or written."""
    if not (Path(source) / run_index.LEGACY_MARK).is_file():
        return f"refusé : {source} n'est pas un index ChromaDB (pas de {run_index.LEGACY_MARK}) ; rien n'est créé."
    for top, folders, files in os.walk(source):
        if any(os.path.islink(os.path.join(top, name)) for name in folders + files):
            return f"refusé : {source} tient un lien ; ChromaDB le suivrait hors de la copie. Une copie sans lien."
    if _inside(dest, source):
        return (f"refusé : la table ({dest}) s'écrirait dans le dossier de la copie ({source}) ; l'import "
                "n'écrit jamais dans ce qu'il lit. --to ailleurs, ou EREGION_ANALYSIS_INDEX.")
    if Path(dest).is_dir():
        return f"refusé : la table ({dest}) est un dossier ; elle est un fichier (…/index.sqlite)."
    return None


def read_old(source: Path) -> tuple[list[str], list[str | None], list[dict]]:
    """The rows of the old index's ``campaign_runs``, in its order: ``(ids, documents, metadatas)`` — read
    from a working copy, never from ``source``."""
    os.environ["ANONYMIZED_TELEMETRY"] = "False"
    import chromadb   # only here: analysis/ no longer opens ChromaDB, but to import it (MEM3)
    from chromadb.config import Settings

    with tempfile.TemporaryDirectory(prefix="eregion-index-import-") as work:
        if _inside(Path(work), source):
            raise Refused(f"refusé : le dossier temporaire ({work}) est dans la copie ({source}).")
        copy = Path(work) / "chroma"
        _copy(Path(source), copy)
        client = chromadb.PersistentClient(path=str(copy), settings=Settings(anonymized_telemetry=False))
        try:
            collection = client.get_collection(cr.COLLECTION)
        except Exception as exc:   # chromadb 1.x: NotFoundError, ValueError before
            raise Refused(f"refusé : {source} n'a pas de collection « {cr.COLLECTION} » "
                          f"({type(exc).__name__}).") from None
        got = collection.get(include=["metadatas", "documents"])
        ids = list(got.get("ids") or [])
        return ids, list(got.get("documents") or [None] * len(ids)), [m or {} for m in got.get("metadatas") or []]


def _copy(source: Path, copy: Path) -> None:
    """The files of ``source`` copied under ``copy`` — read only, ``source`` holds no link (``refusal``)."""
    for top, _folders, files in os.walk(source):
        here = copy / Path(top).relative_to(source)
        here.mkdir(parents=True, exist_ok=True)
        for name in files:
            (here / name).write_bytes((Path(top) / name).read_bytes())


def run(source: Path, dest: Path, say=print) -> int:
    """Import ``source`` into the table at ``dest``: the exit code, what was done said."""
    source, dest = Path(source), Path(dest)
    try:
        try:
            separation.check_index(source)   # IA1: never the defender's memory, even to read it
        except separation.SharedWithGlorfindel:
            raise Refused(f"refusé : {source} est dans l'état de Glorfindel ({separation.glorfindel_state()}) ; "
                          "l'analyse ne lit jamais sa mémoire, même pour l'importer.") from None
        separation.check_index(dest)
        if why := refusal(source, dest):
            raise Refused(why)
        ids, documents, metadatas = read_old(source)
        table = cr._collection(dest)
    except (Refused, separation.SharedWithGlorfindel, run_index.OldIndex) as exc:
        say(str(exc))
        return REFUSED
    rows, unreadable = [], []
    for rid, document, meta in zip(ids, documents, metadatas):
        fact = cr.fact_of(meta)
        if fact is None or fact.run_id != rid:
            unreadable.append(rid)   # never an empty run: named, left
            continue
        rows.append((rid, document, meta))
    added, kept = table.add_missing(*(list(x) for x in zip(*rows))) if rows else ([], [])
    table.record_import(str(source), len(added), len(kept), len(unreadable))
    say(f"index : {dest}")
    say(f"ancien index lu : {source} (par une copie de travail, jamais ouvert en place) — {len(ids)} ligne(s)")
    say(f"{len(added)} run(s) importé(s) ; {len(kept)} déjà dans la table, gardé(s) tel(s) quel(s)"
        + (f" : {', '.join(kept)}" if kept else "")
        + f" ; {len(unreadable)} illisible(s), laissé(s)" + (f" : {', '.join(unreadable)}" if unreadable else ""))
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m analysis.index_import", description=__doc__.splitlines()[0])
    ap.add_argument("source", type=Path, help="the old ChromaDB index (a folder with chroma.sqlite3)")
    ap.add_argument("--to", type=Path, default=None, help="the table (default: the report's index)")
    a = ap.parse_args(argv)
    return run(a.source, a.to or cr.index_path())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
