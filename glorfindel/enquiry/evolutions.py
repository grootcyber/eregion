"""The store of the base's evolutions (ENQ3, #1077; `docs/design/enquete-raisonnee.md` §3.2): one SQLite
table of events, appended to and never rewritten. **Empty, and written by nobody yet**: the watch alone
will write it (ENQ6), the console and the bot read it to show it. No reader in production either: neither
the watch, nor the graph, nor `investigate` imports this module (tests/unit/test_enquiry_knowledge.py).

- **Where**: `~/.glorfindel/enquiry/knowledge.sqlite` (`MAGASIN`), 0600, in a folder 0700, never through a
  link (SEC13, SEC16): a link, or anything but a regular file, in its place is refused before SQLite
  opens it. A file that is not a database raises (`sqlite3.DatabaseError`): a store that cannot be read is
  never an empty one.
- **What**: per event, the hypothesis, its source (its genre, its author, its reference: the card, the
  run, the cycle), its verdict, the accord of a lesson that relaxes, the weight drawn from the source, the
  host's date. Never a VM (Q9). A trigger refuses every UPDATE and DELETE: nothing is rewritten nor erased;
  a seed that withdraws a hypothesis keeps its events.
- **The current state** is computed, never stored: `knowledge.evolutions` over the events read. The weight
  written with each event is for whoever reads the file; the rules draw it again from its source.
- A row that does not read (a genre or a verdict unknown: a file written by hand) is left out and said.
"""
from __future__ import annotations

import contextlib
import os
import sqlite3
import stat
from datetime import datetime, timezone
from pathlib import Path

from glorfindel.enquiry import knowledge

MAGASIN = Path.home() / ".glorfindel" / "enquiry" / "knowledge.sqlite"
BUSY_S = 30.0
COLONNES = ("hypothese", "genre", "auteur", "verdict", "ref", "accord", "texte", "effet", "date")

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS evenements (seq INTEGER PRIMARY KEY, hypothese TEXT NOT NULL, "
    "genre TEXT NOT NULL, auteur TEXT NOT NULL, verdict TEXT NOT NULL, ref TEXT NOT NULL, "
    "accord TEXT NOT NULL, texte TEXT NOT NULL, effet TEXT NOT NULL, poids REAL NOT NULL, date TEXT NOT NULL)",
    "CREATE TRIGGER IF NOT EXISTS evenements_jamais_reecrits BEFORE UPDATE ON evenements "
    "BEGIN SELECT RAISE(ABORT, 'un événement ne se réécrit jamais'); END",
    "CREATE TRIGGER IF NOT EXISTS evenements_jamais_effaces BEFORE DELETE ON evenements "
    "BEGIN SELECT RAISE(ABORT, 'un événement ne s''efface jamais'); END",
)
_FLAGS = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)


class MagasinRefuse(PermissionError):
    """The store's path is a link, or not a regular file, or its folder is not a folder: never opened."""


def _preparer(path: Path) -> None:
    """The folder 0700, the file 0600 and regular, neither reached through a link."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = os.lstat(path.parent)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        raise MagasinRefuse(f"{path.parent} n'est pas un répertoire (un lien, jamais suivi)")
    if stat.S_IMODE(st.st_mode) & 0o077:
        os.chmod(path.parent, 0o700)
    try:
        fd = os.open(path, _FLAGS, 0o600)
    except OSError as exc:                     # ELOOP: a link in its place
        raise MagasinRefuse(f"{path} : refusé, jamais ouvert à travers un lien ({exc.strerror})") from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise MagasinRefuse(f"{path} n'est pas un fichier ordinaire")
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)


class Evolutions:
    """The events of the store at `path` (`MAGASIN` by default, read at the call)."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else MAGASIN
        _preparer(self.path)
        with self._connect() as conn, conn:
            for statement in _SCHEMA:
                conn.execute(statement)

    @contextlib.contextmanager
    def _connect(self):
        if self.path.is_symlink():
            raise MagasinRefuse(f"{self.path} : un lien à sa place, jamais suivi")
        conn = sqlite3.connect(self.path, timeout=BUSY_S)
        try:
            yield conn
        finally:
            conn.close()

    def ajouter(self, lecon: knowledge.Lecon, now: datetime | None = None) -> int:
        """`lecon` appended, dated by the host (its own date never kept), its weight drawn from its source."""
        knowledge.verifier(lecon)
        at = (now or datetime.now(timezone.utc)).isoformat()
        values = [getattr(lecon, c) for c in COLONNES[:-1]] + [at]
        with self._connect() as conn, conn:
            cur = conn.execute(
                f"INSERT INTO evenements ({', '.join(COLONNES)}, poids) VALUES ({', '.join('?' * len(COLONNES))}, ?)",
                values + [knowledge.poids(lecon.genre, lecon.auteur)])
            return cur.lastrowid

    def lire(self) -> tuple[list[knowledge.Lecon], list[str]]:
        """Every event, in the order written, and why each row left out does not read."""
        with self._connect() as conn:
            rows = conn.execute(f"SELECT seq, {', '.join(COLONNES)} FROM evenements ORDER BY seq").fetchall()
        lecons, refus = [], []
        for seq, *values in rows:
            try:
                lecons.append(knowledge.verifier(knowledge.Lecon(**dict(zip(COLONNES, values)))))
            except (TypeError, ValueError) as exc:
                refus.append(f"événement {seq} : {exc}")
        return lecons, refus

    def compte(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM evenements").fetchone()[0]
