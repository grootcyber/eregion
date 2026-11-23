"""MEM3 (#1029): the analysis index on a SQLite table, no ChromaDB — the rows and their order kept,
measured against chromadb itself on an index of before, migrated; the separation of IA1 under the new
form; a row that cannot be read never an empty run; the import of the old index, which never writes in
the copy it reads; an old index never imported, said. No model, no cloud: chromadb embedded, its rows
given an embedding of their own (no model fetched). Mutants M7035–M7039 (scripts/mutants/MEM3.py);
MEM3b (#1052): a file of ChromaDB never the table, the temporary directory, the source of the import —
M7071–M7074 (scripts/mutants/MEM3b.py)."""
import ast
import json
import sqlite3
from pathlib import Path

import pytest

from analysis import campaign_index as ci
from analysis import campaign_report as cr
from analysis import index_import, run_index, separation
from tests.unit.test_campaign_changes import VM, _bench, _campaign, _Model, _run

ANALYSIS = Path(__file__).resolve().parents[2] / "analysis"
EMBEDDING = [1.0, 0.0, 0.0]


class _Chroma:
    """The index as it was before MEM3: a real chromadb collection, its rows given a fixed embedding."""
    def __init__(self, path):
        import chromadb
        from chromadb.config import Settings
        client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
        self.coll = client.get_or_create_collection(name=cr.COLLECTION, metadata={"hnsw:space": "cosine"})

    def __call__(self, path=None):
        return self

    def upsert(self, ids, documents, metadatas):
        self.coll.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=[EMBEDDING] * len(ids))

    def count(self):
        return self.coll.count()

    def get(self, ids=None, where=None, limit=None):
        got = self.coll.get(ids=ids, where=where, limit=limit)
        return {"ids": got["ids"], "metadatas": got["metadatas"]}


@pytest.fixture
def chroma(tmp_path, monkeypatch):
    """The old index, at tmp_path/old/chroma: what cr._collection opened before MEM3."""
    pytest.importorskip("chromadb")
    monkeypatch.setenv("ANONYMIZED_TELEMETRY", "False")
    old = _Chroma(tmp_path / "old" / "chroma")

    def opened(path=None):
        return old
    return old, opened


def _with(monkeypatch, opened, step):
    """``step`` run with the report's index opened by ``opened`` (the old chroma), then put back."""
    with monkeypatch.context() as m:
        m.setattr(cr, "_collection", opened)
        return step()


CLAIMS = [
    {"kind": "trend", "text": "T1110.001 détectée ici comme à la campagne précédente.", "runs": ["R2", "P1"]},
    {"kind": "detected", "text": "La création de compte a été détectée.", "runs": ["R1"]},
    {"kind": "trend", "text": "Le blocage de C0 devient un isolement.", "runs": ["R2", "Q9"]},
]


def _reports(cdirs, index_path):
    return [cr.render(cr.build(cdirs[n], model="fake/model", llm=_Model(CLAIMS), index_path=index_path))
            for n in ("C0", "CA", "CX", "C2", "C1")]


# ── The rows and their order: as chromadb gave them ────────────────────────────────────────────────

def test_the_campaign_reports_are_the_same_on_the_table_as_on_chromadb(tmp_path, chroma, monkeypatch):
    """The example campaigns of D-2 (C0, CA, CX, C2, C1, tests/unit/test_campaign_changes.py), reported
    one after the other: on chromadb before MEM3, on the table now — the same reports, to the byte."""
    _, cdirs = _bench(tmp_path)
    old, opened = chroma
    before = _with(monkeypatch, opened, lambda: _reports(cdirs, None))
    after = _reports(cdirs, tmp_path / "new" / "index.sqlite")
    assert after == before
    assert "C0" in after[-1] and "P1" in after[-1]         # C1's report faces C0, cites its run


def _many(tmp_path):
    """Sixty runs of one technique, one per campaign, put in an order that is not their ids': R05…R54
    first, then R55…R59, then R00…R04 — what a ``limit`` takes first tells the orders apart."""
    order = [f"R{i:02d}" for i in (*range(5, 55), *range(55, 60), *range(0, 5))]
    for rid in order:
        fact = cr.RunFact(rid, f"C{rid}", 1, "T1110.001", "Brute Force", "executed", "detected", target=VM)
        yield [fact], cr.CampaignInfo(f"C{rid}", "done", 1_700_000_000.0 + int(rid[1:]))


def test_the_rows_come_back_in_the_order_they_were_first_put_in_as_chromadb_gave_them(tmp_path, chroma,
                                                                                       monkeypatch):
    """M7035: ``prior_runs`` reads the first 50 rows of a technique: those first put in, as chromadb
    gave them — never the first by id. An upsert keeps a row's place; ``get(ids=…)`` answers in that
    order too, an unknown id left out. The same answers from the table as from chromadb."""
    old, opened = chroma
    new = tmp_path / "new" / "index.sqlite"
    for facts, info in _many(tmp_path):
        _with(monkeypatch, opened, lambda: cr.index_facts(facts, None, info))
        cr.index_facts(facts, new, info)
    mine = [cr.RunFact("N1", "CN", 1, "T1110.001", "Brute Force", "executed", "detected", target=VM)]
    told = _with(monkeypatch, opened, lambda: [f.run_id for f in cr.prior_runs(mine)])
    assert told == ["R54", "R53", "R52"]                     # chromadb's: the first 50 put in
    assert [f.run_id for f in cr.prior_runs(mine, new)] == told
    for asked in (dict(ids=["R59", "R00", "R05", "nope"]), dict(where={"ttp": "T1110.001"}, limit=7),
                  dict(where={"campaign_state": "done"}), dict()):
        assert cr._collection(new).get(**asked) == old.get(**asked), asked
    # an upsert of a row already there: its place kept, its keys merged
    again = [cr.RunFact("R05", "CR05", 1, "T1110.001", "Brute Force", "executed", "missed", target=VM)]
    _with(monkeypatch, opened, lambda: cr.index_facts(again))
    cr.index_facts(again, new)
    assert cr._collection(new).get() == old.get()
    assert cr._collection(new).get(ids=["R05"])["metadatas"][0]["campaign_state"] == "done"


def test_an_index_of_before_migrated_gives_the_same_rows_in_the_same_order(tmp_path, chroma, monkeypatch, capsys):
    """An index of before, written by chromadb (the D-2 campaigns reported, then sixty runs), migrated:
    every row, its keys, its place; ``prior_runs``, ``previous_campaign`` and the replay of
    ``campaign_index`` read the same lines, in the same order, and the reports are the same."""
    _, cdirs = _bench(tmp_path)
    old, opened = chroma
    _with(monkeypatch, opened, lambda: _reports(cdirs, None))
    for facts, info in _many(tmp_path):
        _with(monkeypatch, opened, lambda: cr.index_facts(facts, None, info))
    migrated = tmp_path / "migrated" / "index.sqlite"
    assert index_import.main([str(tmp_path / "old" / "chroma"), "--to", str(migrated)]) == 0
    assert "69 run(s) importé(s) ; 0 déjà dans la table" in capsys.readouterr().out
    assert cr._collection(migrated).get() == old.get()
    facts = cr.collect_facts(cdirs["C1"])
    info = cr.campaign_info(cdirs["C1"])
    for read in (lambda p: [f.run_id for f in cr.prior_runs(facts, p)],
                 lambda p: cr.previous_campaign(facts, info, p),
                 lambda p: ci.verse(cdirs["C0"], p)):
        assert read(migrated) == _with(monkeypatch, opened, lambda: read(None))
    report = cr.render(cr.build(cdirs["C1"], model="fake/model", llm=_Model(CLAIMS), index_path=migrated))
    assert report == _with(monkeypatch, opened, lambda: cr.render(
        cr.build(cdirs["C1"], model="fake/model", llm=_Model(CLAIMS), index_path=None)))


# ── IA1 under the new form ─────────────────────────────────────────────────────────────────────────

def _glorfindel_memory(path: Path) -> bytes:
    """Glorfindel's memory in the form MEM2 gives it: a SQLite file and its table ``cycles``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    with conn:
        conn.execute("CREATE TABLE cycles (id TEXT PRIMARY KEY, document TEXT)")
        conn.execute("INSERT INTO cycles VALUES ('cycle-1', 'TTP: T1486')")
    conn.close()
    return path.read_bytes()


def test_the_index_never_opens_a_file_that_holds_glorfindel_s_memory_wherever_it_lies(tmp_path):
    """M7036: a copy of Glorfindel's memory (its table ``cycles``) outside ~/.glorfindel, named as the
    analysis index: refused at its opening — nothing written in it, read nor written by the report."""
    memory = tmp_path / "elsewhere" / "memory.sqlite"
    was = _glorfindel_memory(memory)
    fact = cr.RunFact("R1", "C1", 1, "T1486", "R", "executed", "detected", target=VM)
    for step in (lambda: cr.index_facts([fact], memory), lambda: cr.prior_runs([fact], memory),
                 lambda: cr.previous_campaign([fact], cr.CampaignInfo("C1", "done", 1.0), memory)):
        with pytest.raises(separation.SharedWithGlorfindel, match="Glorfindel's memory"):
            step()
    assert memory.read_bytes() == was
    link = tmp_path / "index.sqlite"
    link.symlink_to(memory)                      # through a link too
    with pytest.raises(separation.SharedWithGlorfindel):
        cr.index_facts([fact], link)
    assert memory.read_bytes() == was


def test_a_file_in_glorfindel_s_state_is_refused_before_it_is_made(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(cr.INDEX_ENV, str(tmp_path / ".glorfindel" / "index.sqlite"))
    with pytest.raises(separation.SharedWithGlorfindel, match="EREGION_ANALYSIS_INDEX"):
        cr.index_facts([cr.RunFact("R1", "C1", 1, "T1486", "R", "executed", "detected")])
    assert not (tmp_path / ".glorfindel").exists()


# ── A row that cannot be read ──────────────────────────────────────────────────────────────────────

def _put(path: Path, rid: str, fact: str, **keys):
    with sqlite3.connect(path) as conn:
        cols = {"run_id": rid, "fact": fact, "ttp": "T1110.001", "campaign_id": f"C{rid}",
                "campaign_state": "done", "campaign_started": 1_700_000_000.0, "vm": VM.lower(), **keys}
        conn.execute(f"INSERT INTO campaign_runs ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                     list(cols.values()))
    conn.close()


def test_a_row_that_cannot_be_read_is_never_an_empty_run(tmp_path):
    """M7037: beside a good row, rows whose facts are no JSON, no object, an empty run, or another
    run's: none comes back as a run — neither as an earlier run nor as the previous campaign's — and
    none breaks the report."""
    idx = tmp_path / "index.sqlite"
    good = cr.RunFact("G1", "CG1", 1, "T1110.001", "Brute Force", "executed", "detected", target=VM)
    cr.index_facts([good], idx, cr.CampaignInfo("CG1", "done", 1_700_000_000.0))
    empty = {"run_id": "", "campaign_id": "", "seq": 0, "ttp": "", "name": "", "status": "", "detection": ""}
    _put(idx, "B1", "{not json")
    _put(idx, "B2", "[]")
    _put(idx, "B3", "null")
    _put(idx, "B4", json.dumps(empty), campaign_id="")
    _put(idx, "B5", json.dumps({**empty, "run_id": "G1", "campaign_id": "CB5", "ttp": "T1110.001"}))
    mine = [cr.RunFact("N1", "CN", 1, "T1110.001", "Brute Force", "executed", "detected", target=VM)]
    assert [f.run_id for f in cr.prior_runs(mine, idx)] == ["G1"]
    previous, runs, _ = cr.previous_campaign(mine, cr.CampaignInfo("CN", "done", 1_800_000_000.0), idx)
    assert (previous, [f.run_id for f in runs]) == ("CG1", ["G1"])
    for rid in ("B1", "B2", "B3", "B4", "B5"):
        [meta] = cr._collection(idx).get(ids=[rid])["metadatas"]
        assert cr.fact_of(meta) is None, rid


def test_a_file_that_is_no_database_is_never_an_empty_index(tmp_path):
    idx = tmp_path / "index.sqlite"
    idx.write_text("not a database, by far, not a database at all")
    with pytest.raises(sqlite3.DatabaseError):
        cr.prior_runs([cr.RunFact("R1", "C1", 1, "T1486", "R", "executed", "detected")], idx)


def test_a_folder_at_the_index_s_path_is_the_old_index_never_opened(tmp_path, monkeypatch):
    old = tmp_path / "chroma-index"
    old.mkdir()
    (old / "chroma.sqlite3").write_text("x")
    monkeypatch.setenv(cr.INDEX_ENV, str(old))
    with pytest.raises(run_index.OldIndex, match="analysis.index_import"):
        cr.index_facts([cr.RunFact("R1", "C1", 1, "T1486", "R", "executed", "detected")])
    assert sorted(p.name for p in old.iterdir()) == ["chroma.sqlite3"]


# ── The import: offline, never in the copy it reads ────────────────────────────────────────────────

def _shot(folder: Path) -> dict:
    return {str(p.relative_to(folder)): (p.read_bytes() if p.is_file() else None, p.stat().st_mtime_ns)
            for p in sorted(folder.rglob("*"))}


@pytest.fixture
def copy(tmp_path, chroma, monkeypatch):
    """A copy of an old index: two runs, one of which cannot be read."""
    old, opened = chroma
    _with(monkeypatch, opened, lambda: cr.index_facts(
        [cr.RunFact("P1", "C0", 1, "T1110.001", "Brute Force", "executed", "detected", target=VM)], None,
        cr.CampaignInfo("C0", "done", 1_700_000_000.0)))
    old.coll.upsert(ids=["U1"], metadatas=[{"run_id": "U1", "ttp": "T1041", "fact": "{broken"}],
                    embeddings=[EMBEDDING])
    return tmp_path / "old" / "chroma"


def test_the_import_never_writes_in_the_copy_it_reads(tmp_path, copy, capsys, monkeypatch):
    """M7038: a table asked in the copy's folder — or the folder itself — is refused, nothing written;
    elsewhere, ChromaDB opens a working copy only, never the copy given, which stays as it was."""
    was = _shot(copy)
    for inside in (copy / "index.sqlite", copy, copy / "sub" / "index.sqlite"):
        assert index_import.main([str(copy), "--to", str(inside)]) == index_import.REFUSED
        assert "dossier de la copie" in capsys.readouterr().out
        assert _shot(copy) == was
    import chromadb
    opened = []
    real = chromadb.PersistentClient

    def client(path, **kw):
        opened.append(Path(path))
        return real(path=path, **kw)
    monkeypatch.setattr(chromadb, "PersistentClient", client)
    dest = tmp_path / "dest" / "index.sqlite"
    assert index_import.main([str(copy), "--to", str(dest)]) == 0
    assert opened and all(not index_import._inside(p, copy) for p in opened)
    assert not any(p.exists() for p in opened)              # the working copy, removed
    assert _shot(copy) == was


def test_the_import_brings_the_rows_names_those_kept_and_those_it_cannot_read(tmp_path, copy, capsys):
    """A row already in the table (written since, by a report) is kept as it is; a row whose facts
    cannot be read is never written — both named; run twice, the table is the same."""
    dest = tmp_path / "dest" / "index.sqlite"
    newer = cr.RunFact("P1", "C0", 1, "T1110.001", "Brute Force", "executed", "missed", target=VM)
    cr.index_facts([newer], dest)
    assert index_import.main([str(copy), "--to", str(dest)]) == 0
    out = capsys.readouterr().out
    assert "0 run(s) importé(s) ; 1 déjà dans la table, gardé(s) tel(s) quel(s) : P1" in out
    assert "1 illisible(s), laissé(s) : U1" in out
    table = cr._collection(dest)
    assert table.get()["ids"] == ["P1"] and cr.fact_of(table.get()["metadatas"][0]).detection == "missed"
    first = table.get()
    assert index_import.main([str(copy), "--to", str(dest)]) == 0
    assert table.get() == first


@pytest.mark.parametrize("case", ["no-store", "link", "glorfindel", "no-collection", "dest-folder"])
def test_the_import_refuses_what_it_should_not_read_and_writes_nothing(tmp_path, monkeypatch, capsys, case):
    pytest.importorskip("chromadb")
    monkeypatch.setenv("HOME", str(tmp_path))
    source, dest = tmp_path / "copy", tmp_path / "dest" / "index.sqlite"
    source.mkdir()
    (source / "chroma.sqlite3").write_text("x")
    if case == "no-store":
        (source / "chroma.sqlite3").unlink()
    elif case == "link":
        (tmp_path / "far").mkdir()
        (source / "seg").symlink_to(tmp_path / "far")
    elif case == "glorfindel":
        source = tmp_path / ".glorfindel" / "cycles"
        source.mkdir(parents=True)
        (source / "chroma.sqlite3").write_text("x")
    elif case == "no-collection":
        import chromadb
        from chromadb.config import Settings
        (source / "chroma.sqlite3").unlink()
        client = chromadb.PersistentClient(path=str(source), settings=Settings(anonymized_telemetry=False))
        client.get_or_create_collection(name="cycles")             # Glorfindel's memory, copied
    elif case == "dest-folder":
        dest.mkdir(parents=True)
    assert index_import.main([str(source), "--to", str(dest)]) == index_import.REFUSED
    assert "refusé" in capsys.readouterr().out
    assert not dest.exists() or dest.is_dir()


# ── An old index never imported: said ─────────────────────────────────────────────────────────────

def test_an_old_index_never_imported_is_said_never_read_as_empty(tmp_path, copy, capsys):
    """M7039: beside an old ChromaDB index never imported (its default, ``chroma/`` in the index's
    folder), the report says it — its runs are no longer read — and ``campaign_index`` refuses to
    compute them again; once imported, nothing more is said, and the runs come back."""
    _, cdirs = _bench(tmp_path)
    idx = copy.parent / "index.sqlite"                      # beside it: tmp_path/old/
    report = cr.build(cdirs["C1"], model="fake/model", llm=_Model(), index_path=idx)
    assert report.prior == [] and report.index_note
    md = cr.render(report)
    assert "Index vide ou non importé" in md and str(copy) in md and "analysis.index_import" in md
    capsys.readouterr()
    assert index_import.main([str(copy), "--to", str(idx)]) == 0
    report = cr.build(cdirs["C1"], model="fake/model", llm=_Model(), index_path=idx)
    assert report.index_note == "" and "non importé" not in cr.render(report)
    assert "P1" in {f.run_id for f in report.prior}


def test_the_index_command_waits_for_the_import(tmp_path, copy, monkeypatch, capsys):
    """campaign_index --all, beside an old index never imported: refused, said — the runs it holds,
    their windows purged, would be computed again with their decision unknown."""
    runs, _ = _bench(tmp_path)
    monkeypatch.setenv(cr.INDEX_ENV, str(copy.parent / "index.sqlite"))
    assert ci.main(["--all", str(runs / "campaigns")]) == 1
    out = capsys.readouterr().out
    assert "non importé" in out and "rien n'est versé avant l'import" in out
    assert index_import.main([str(copy)]) == 0
    assert ci.main(["--all", str(runs / "campaigns")]) == 0


# ── MEM3b (#1052): a file of ChromaDB, the temporary directory, the source of the import ───────────

def _tables_of(path: Path) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        return {n for (n,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    finally:
        conn.close()


def test_the_index_never_opens_a_file_of_chromadb_as_the_table(tmp_path, copy, monkeypatch, capsys):
    """M7071: a ``chroma.sqlite3`` named as the index — the old index's own, or a copy of Glorfindel's
    memory of today (ChromaDB, its collection ``cycles``) elsewhere — is refused at its opening, said:
    never read as an empty index, nothing written in it (no ``campaign_runs``, no ``imports``)."""
    import chromadb
    from chromadb.config import Settings
    glorfindel = tmp_path / "glorfindel-copy"
    client = chromadb.PersistentClient(path=str(glorfindel), settings=Settings(anonymized_telemetry=False))
    client.get_or_create_collection(name="cycles").upsert(ids=["cycle-1"], documents=["TTP: T1486"],
                                                         embeddings=[EMBEDDING])
    memory = tmp_path / "elsewhere" / "memory.sqlite"
    memory.parent.mkdir()
    memory.write_bytes((glorfindel / "chroma.sqlite3").read_bytes())
    fact = cr.RunFact("R1", "C1", 1, "T1486", "R", "executed", "detected", target=VM)
    for chroma_file in (copy / "chroma.sqlite3", memory):
        was, shot = chroma_file.read_bytes(), _shot(chroma_file.parent)
        for step in (lambda: cr.index_facts([fact], chroma_file), lambda: cr.prior_runs([fact], chroma_file),
                     lambda: cr.previous_campaign([fact], cr.CampaignInfo("C1", "done", 1.0), chroma_file)):
            with pytest.raises(run_index.OldIndex, match="a file of ChromaDB"):
                step()
        with monkeypatch.context() as m:
            m.setenv(cr.INDEX_ENV, str(chroma_file))
            with pytest.raises(run_index.OldIndex, match="EREGION_ANALYSIS_INDEX"):
                cr.index_facts([fact])
        assert chroma_file.read_bytes() == was and _shot(chroma_file.parent) == shot
        assert not _tables_of(chroma_file) & {"campaign_runs", "imports"}
    dest = tmp_path / "far" / "chroma.sqlite3"            # the import's table: a copy of the old index elsewhere
    dest.parent.mkdir()
    dest.write_bytes((copy / "chroma.sqlite3").read_bytes())
    capsys.readouterr()
    assert index_import.main([str(copy), "--to", str(dest)]) == index_import.REFUSED
    assert "a file of ChromaDB" in capsys.readouterr().out
    assert not _tables_of(dest) & {"campaign_runs", "imports"}


def test_a_temporary_directory_in_the_copy_is_refused_before_anything_is_made_in_it(tmp_path, copy,
                                                                                    monkeypatch, capsys):
    """M7072: a temporary directory in the copy — ``TMPDIR``, ``TEMP`` or ``TMP`` in a fresh process
    (``tempfile.tempdir`` unset: ``gettempdir()`` would write its probe file in it), or
    ``tempfile.tempdir`` itself; in the copy, the copy, through a link and ``..`` — is refused before
    anything is opened to write or made under the copy, not even for a while."""
    import os
    import tempfile
    (copy / "tmp").mkdir()
    (tmp_path / "lnk").symlink_to(copy)
    written = []
    real_open, real_mkdir = os.open, os.mkdir

    def under_copy(path):
        return isinstance(path, (str, bytes, os.PathLike)) and index_import._inside(Path(os.fsdecode(path)), copy)

    def spy_open(path, flags, *a, **kw):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT) and under_copy(path):
            written.append(("open", path))
        return real_open(path, flags, *a, **kw)

    def spy_mkdir(path, *a, **kw):
        if under_copy(path):
            written.append(("mkdir", path))
        return real_mkdir(path, *a, **kw)
    monkeypatch.setattr(os, "open", spy_open)
    monkeypatch.setattr(os, "mkdir", spy_mkdir)
    was = _shot(copy)
    dest = tmp_path / "dest" / "index.sqlite"
    places = (copy / "tmp", copy, tmp_path / "lnk" / "tmp", copy / "tmp" / "..")
    for name in ("TMPDIR", "TEMP", "TMP", "tempfile.tempdir"):
        for inside in places:
            with monkeypatch.context() as m:
                for env in ("TMPDIR", "TEMP", "TMP"):
                    m.delenv(env, raising=False)
                m.setattr(tempfile, "tempdir", str(inside) if name == "tempfile.tempdir" else None)
                if name != "tempfile.tempdir":
                    m.setenv(name, str(inside))
                assert index_import.main([str(copy), "--to", str(dest)]) == index_import.REFUSED, (name, inside)
            assert "répertoire temporaire" in capsys.readouterr().out
            assert written == [] and _shot(copy) == was, (name, inside)
    assert not dest.exists()
    assert index_import.main([str(copy), "--to", str(dest)]) == 0     # elsewhere: imported
    assert written == [] and _shot(copy) == was


def test_a_hot_copy_in_wal_is_read_only_before_it_is_refused(tmp_path):
    """A file of ChromaDB copied hot, in WAL with its ``-wal``: its tables read by a connection read only
    — a connection that writes would checkpoint the ``-wal`` into the file. Refused, the file and its
    ``-wal`` as they were."""
    live = tmp_path / "live" / "chroma.sqlite3"
    live.parent.mkdir()
    conn = sqlite3.connect(live)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    with conn:
        conn.execute("CREATE TABLE collections (id TEXT, name TEXT)")
        conn.execute("CREATE TABLE embeddings (id INTEGER)")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    with conn:
        conn.execute("INSERT INTO collections VALUES ('c1', 'campaign_runs')")
    hot = tmp_path / "hot" / "chroma.sqlite3"
    hot.parent.mkdir()
    for suffix in ("", "-wal"):
        Path(f"{hot}{suffix}").write_bytes(Path(f"{live}{suffix}").read_bytes())
    conn.close()
    was = {s: Path(f"{hot}{s}").read_bytes() for s in ("", "-wal")}
    assert len(was["-wal"]) > 0
    with pytest.raises(run_index.OldIndex, match="a file of ChromaDB"):
        cr.prior_runs([cr.RunFact("R1", "C1", 1, "T1486", "R", "executed", "detected")], hot)
    assert {s: Path(f"{hot}{s}").read_bytes() for s in ("", "-wal")} == was


# A writer killed in the middle of a transaction (the watch restarted during an upsert, the host stopped):
# its pages spilled into the file, its rollback journal left hot beside it.
_KILLED_WRITER = """
import os, sqlite3, sys
c = sqlite3.connect(sys.argv[1], isolation_level=None)
c.execute("PRAGMA cache_size=1")
c.execute("BEGIN")
for i in range(2000):
    c.execute(f"INSERT INTO {sys.argv[2]} VALUES (?, ?)", ("K%d" % i, "y" * 3000))
os._exit(0)
"""


def _killed_in_a_transaction(path: Path, table: str, cols: str, script: str = _KILLED_WRITER) -> Path:
    import subprocess
    import sys
    subprocess.run([sys.executable, "-I", "-c", script.replace("VALUES", f"({cols}) VALUES"),
                    str(path), table], check=True, timeout=60)
    journal = Path(f"{path}-journal")
    assert journal.is_file() and journal.stat().st_size > 0      # hot: its writer is gone
    return journal


def test_an_index_with_a_hot_journal_opens_and_rolls_it_back(tmp_path):
    """M7107: a table of the analysis whose writer was killed in a transaction: read only, its journal
    cannot be rolled back (SQLITE_READONLY_ROLLBACK) — the file is read as it lies, it is the analysis's
    own, and the connection that writes rolls the journal back: the rows committed come back, never an
    index that no longer opens."""
    idx = tmp_path / "index.sqlite"
    facts = [cr.RunFact(f"R{i}", f"C{i}", 1, "T1110.001", "Brute Force", "executed", "detected", target=VM)
             for i in range(5)]
    cr.index_facts(facts, idx)
    journal = _killed_in_a_transaction(idx, "campaign_runs", "run_id, fact")
    for _ in range(2):
        assert cr._collection(idx).get()["ids"] == [f"R{i}" for i in range(5)]
        assert not journal.exists()                               # rolled back
    assert [f.run_id for f in cr.prior_runs([facts[0]], idx)] == ["R4", "R3", "R2"]


# A migration of the schema killed half way: four hundred tables added, then rows — ``sqlite_master``,
# on many pages, rewritten in the file by pages not committed.
_KILLED_MIGRATION = _KILLED_WRITER.replace('c.execute("BEGIN")\n', 'c.execute("BEGIN")\n'
                                           'for i in range(400):\n'
                                           '    c.execute(f"CREATE TABLE newer{i} (a, b, c, d, e, f, g, h)")\n')


def _tables_in(path: Path, how: str) -> set[str]:
    conn = sqlite3.connect(f"file:{path}?{how}", uri=True)
    try:
        return {n for (n,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    finally:
        conn.close()


@pytest.mark.parametrize("guarded, refused", [
    (("CREATE TABLE collections (id TEXT, name TEXT)", "CREATE TABLE embeddings (id TEXT, seq_id TEXT)"),
     run_index.OldIndex),
    (("CREATE TABLE cycles (id TEXT, document TEXT)",), separation.SharedWithGlorfindel),
], ids=["chromadb", "glorfindel"])
def test_a_guarded_file_with_a_hot_journal_stays_refused(tmp_path, guarded, refused):
    """M7114: a file of ChromaDB, or of Glorfindel's memory (``cycles``), its ``sqlite_master`` on many
    pages, whose writer was killed in a migration: read as the file lies (``immutable``), its tables are
    not there — the connection that writes rolls the journal back, reads them again, and refuses. The
    rollback is the only write: the file is back to its committed state, as any reader of SQLite would
    leave it — no ``campaign_runs``, no ``imports``."""
    guarded_file = tmp_path / "copy" / "file.sqlite3"
    guarded_file.parent.mkdir()
    conn = sqlite3.connect(guarded_file)
    with conn:
        for i in range(300):
            conn.execute(f"CREATE TABLE filler{i} (a TEXT, b TEXT, c TEXT, d TEXT, e TEXT, f TEXT, g TEXT, h TEXT)")
        for statement in guarded:
            conn.execute(statement)
        conn.execute("CREATE TABLE bulk (k TEXT, v TEXT)")
    conn.close()
    committed = _tables_in(guarded_file, "mode=ro")
    names = committed - {f"filler{i}" for i in range(300)} - {"bulk"}
    journal = _killed_in_a_transaction(guarded_file, "bulk", "k, v", _KILLED_MIGRATION)
    assert not names & _tables_in(guarded_file, "mode=ro&immutable=1")     # the view as the file lies
    with pytest.raises(refused):
        cr.prior_runs([cr.RunFact("R1", "C1", 1, "T1486", "R", "executed", "detected")], guarded_file)
    assert not journal.exists()                                            # rolled back, the only write
    assert _tables_in(guarded_file, "mode=ro") == committed                # no campaign_runs, no imports


def test_the_note_names_the_old_index_until_that_one_is_imported(tmp_path, copy, capsys):
    """M7073, M7074: beside the old index (``chroma/``), the import of another copy of it, or rows a
    report wrote in the table, never silence the note — the old index beside the table is still not
    imported. The import of that one does, under any spelling of its path (``..``, a link): the source
    is compared resolved."""
    import shutil
    _, cdirs = _bench(tmp_path)
    idx = copy.parent / "index.sqlite"
    cr.index_facts([cr.RunFact("N1", "CN", 1, "T1041", "X", "executed", "detected", target=VM)], idx)
    assert cr.index_note(idx)                                # rows in the table: not an import
    other = tmp_path / "other" / "chroma"
    shutil.copytree(copy, other)
    assert index_import.main([str(other), "--to", str(idx)]) == 0
    assert "P1" in cr._collection(idx).get()["ids"]
    report = cr.build(cdirs["C1"], model="fake/model", llm=_Model(), index_path=idx)
    assert str(copy) in report.index_note and "non importé" in cr.render(report)
    assert not cr._collection(idx).imported(copy) and cr._collection(idx).imported(other)
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "old")
    assert index_import.main([str(link / ".." / "old" / "chroma"), "--to", str(idx)]) == 0
    assert cr._collection(idx).imported(copy) and cr._collection(idx).imported(link / "chroma")
    assert cr.index_note(idx) == ""
    capsys.readouterr()


# ── chromadb: no longer imported by the analysis, but to import the old index ──────────────────────

def test_the_analysis_no_longer_imports_chromadb_but_to_migrate():
    """chromadb stays a dependency until MEM4: analysis/ imports it nowhere at its top, and only the
    import of the old index, in the function that reads it."""
    where = []
    for path in sorted(ANALYSIS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            if any(n == "chromadb" or n.startswith("chromadb.") for n in names):
                where.append(path.name)
        assert not any(isinstance(n, (ast.Import, ast.ImportFrom)) and "chromadb" in ast.dump(n)
                       for n in tree.body), path.name
    assert set(where) == {"index_import.py"}


def test_the_example_campaign_needs_no_index_of_chromadb(tmp_path, monkeypatch):
    """A report built where chromadb is not (a component's tests, D1): the table is the standard library's."""
    import sys
    monkeypatch.setitem(sys.modules, "chromadb", None)       # an import of it would raise
    runs = tmp_path / "runs" / "glorfindel"
    cdir = _campaign(runs, "CZ", "2026-10-25T08:00:00Z", [_run(1, "Z9", "T1041", latency=12.0, action="snapshot")])
    report = cr.build(cdir, model="fake/model", llm=_Model(), index_path=tmp_path / "index.sqlite")
    assert [f.run_id for f in report.facts] == ["Z9"]
