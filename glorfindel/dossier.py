"""The dossier of an isolation, step 0: the facts the cycle already holds, written at its end with no call
(DOS3, #1043; `docs/design/dossier-isolation.md` §3.1, §3.5 to §3.7, §4.1, §4.5, §4.6, §12).

**Facts, never a verdict.** Each fact says its source, its author, what it read and its state: `lu`,
`vide`, `sans_objet` (a source that cannot say anything here: the Process counter of `investigate`
under Linux), `illisible` with its reason, `en_attente` (the source has not delivered yet: a drain
followed by DRN1). An unreadable source is never written empty.

**Step 0** (`at_cycle_end`, called by `store_cycle` after the action and its check): F3c (the VM's past
cards for the rule), F4c (what the model saw of a successful login), F5b (the drain), F5c (the
verification), F6a to F6h (the decision as it was taken; `glorfindel/cycle_line.py`) — read in
`glorfindel/dossier_local.py`. Local files and the cycle's state only: no call to Azure nor to a model,
under the VM's thread, after the action.

**The scope** (Q2): every isolation executed, and every card that proposes `isolate_vm` or
`block_suspicious_ip` without executing it (held by the mode, the confidence, D-1, a gate; the floor's
card, the ceiling's). Never a dry-run, a cycle of the control plane or of an identity, a snapshot alone.

**The file**: `~/.glorfindel/dossier/<vm>-<h8>-<s8>.json` (h8 of the VM's id, s8 of the signal's id),
written by Glorfindel (the watch, and `respond` out of dry-run), never by the console nor the bot; whole,
0600, never through a link. **The ceiling** (Q9): at most GLORFINDEL_DOSSIER_MAX_PER_H (6) dossiers
composed per hour, counted by each process; past it, or 0, a dossier « non composé » that says why —
never silence. **The retention** (Q7): 30 days after the lift (`retention_pass`).

**Apart.** No gate reads it, nor the model, nor the memory, nor a lift: nothing here enters the signal
(`tests/unit/test_dossier.py` freezes the message to the byte; no guard imports these modules).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import stat
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

DOSSIER_DIR = Path.home() / ".glorfindel" / "dossier"
FORMAT = 1
LU, VIDE, SANS_OBJET, ILLISIBLE, EN_ATTENTE = "lu", "vide", "sans_objet", "illisible", "en_attente"
ETATS = (LU, VIDE, SANS_OBJET, ILLISIBLE, EN_ATTENTE)
ISOLATION, PROPOSITION = "isolation", "proposition"
PROPOSED = ("isolate_vm", "block_suspicious_ip")
MAX_PER_H = 6                 # Q9 (12/11): for the whole watch
RETENTION_DAYS = 30           # Q7 (12/11): after the lift
RETENTION_EVERY_S = 3600      # the retention's pass, at the watch's housekeeping (local files only)
RECURRENCE_DAYS = 10          # Q6 (12/11): N, the cards of the same VM and rule
LISTED = 10                   # values listed by a fact, the rest counted
CUT = 200
# The investigative queries that read the Process counter `IO Write Bytes/sec`: Windows only, always
# [] under Linux (agent.py, « KNOWN LIMITATION ») — nothing to say there: sans objet, never empty.
WINDOWS_ONLY = ("top_write_processes", "backup_agent_check")
_LOCK = threading.Lock()      # the count of the hour and the write: one at a time (the VMs' threads)


# ── The form of a fact (§3.1) ───────────────────────────────────────────────────────────────────────

def fact(code: str, id_: str, *, etat: str, dit: str, source: str, lecture: str, lu_a: str,
         valeurs: dict | None = None, pourquoi: str = "", auteur: str = "glorfindel") -> dict:
    """One fact of the dossier. An `illisible` always says why."""
    if etat not in ETATS:
        raise ValueError(f"état inconnu : {etat}")
    out = {"code": code, "id": id_, "etat": etat, "dit": _cut(dit, 600), "valeurs": valeurs or {},
           "source": source, "lecture": lecture, "auteur": auteur, "lu_a": lu_a, "mesure": "local"}
    if etat == ILLISIBLE:
        out["pourquoi"] = _cut(pourquoi or "raison non dite", 300)
    return out


def _cut(value, n: int = CUT) -> str:
    text = str(value if value is not None else "")
    return text if len(text) <= n else text[: n - 1] + "…"


def _kept(value):
    """A value of the cycle as it is when it is a number, a boolean or null; else its text, cut."""
    return value if value is None or isinstance(value, (bool, int, float)) else _cut(value)


def _first_line(exc: BaseException) -> str:
    return (str(exc).strip().splitlines() or [type(exc).__name__])[0][:200]


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _epoch(text) -> float | None:
    try:
        dt = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt.timestamp() if dt.tzinfo is not None else None      # a time without a zone is never placed


def _same_id(a, b) -> bool:
    return str(a or "").rstrip("/").lower() == str(b or "").rstrip("/").lower()


def signal_time(signal: dict) -> tuple[str, str]:
    """(T, where it was read): the time of the row that fired (`ligne`), else the signal's (`signal`: an
    aggregated row has none — the poll's time, not the event's), else ("", "")."""
    raw = _dict(signal.get("raw_signal"))
    row = _dict(raw.get("first_result_row") or raw.get("detected_data"))
    for value, where in ((row.get("TimeGenerated"), "ligne"), (signal.get("timestamp"), "signal")):
        at = _epoch(value)
        if at is not None:
            return _iso(at), where
    return "", ""


# ── The scope (§4.6, Q2) ────────────────────────────────────────────────────────────────────────────

def scope(state: dict, data_plane: bool) -> tuple[str, str]:
    """(`isolation` | `proposition` | "", the action executed or proposed)."""
    if state.get("dry_run") or not data_plane:
        return "", ""
    outcome, action = _dict(state.get("outcome")), str(state.get("action") or "")
    if action == "isolate_vm" and outcome.get("executed") and outcome.get("status") not in ("dry_run", "no_op"):
        return ISOLATION, action
    if state.get("escalate") and action in PROPOSED and not outcome.get("executed"):
        return PROPOSITION, action
    if state.get("floor_card"):                     # B3a: its card proposes isolate_vm
        return PROPOSITION, "isolate_vm"
    proposed = str(_dict(state.get("ceiling")).get("proposed") or "")
    if state.get("ceiling_card") and proposed == "isolate_vm":      # RDW1: its card proposes it
        return PROPOSITION, proposed
    return "", ""


# ── The VM's isolation state, read for the header and F5b ─────────────────────────────────────────

def _isolation_state(rid: str) -> tuple[dict | None, str]:
    """(the VM's isolation state, why it cannot be read); (None, "") when there is none."""
    from glorfindel.response import state as st
    f = st._state_file(st._ISOLATION_STATE_DIR, rid)
    if f is None or not f.exists():
        return None, ""
    try:
        data = json.loads(f.read_text())
    except (OSError, ValueError) as exc:
        return None, f"état d'isolement illisible : {_first_line(exc)}"
    return (data, "") if isinstance(data, dict) else (None, "état d'isolement d'une autre forme")


# ── The file (§4.1), the ceiling (Q9), the retention (Q7) ────────────────────────────────────────────

def file_for(resource_id: str, signal_id: str) -> Path:
    rid = str(resource_id or "").rstrip("/").lower()
    name = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in rid.rsplit("/", 1)[-1])[:64]
    h8 = hashlib.sha256(rid.encode()).hexdigest()[:8]
    s8 = hashlib.sha256(str(signal_id or "").encode()).hexdigest()[:8]
    return DOSSIER_DIR / f"{name}-{h8}-{s8}.json"


def max_per_h() -> int:
    """GLORFINDEL_DOSSIER_MAX_PER_H (6; 0: none composed); malformed or negative: 6."""
    raw = os.environ.get("GLORFINDEL_DOSSIER_MAX_PER_H", "").strip()
    try:
        n = int(raw) if raw else MAX_PER_H
    except ValueError:
        return MAX_PER_H
    return n if n >= 0 else MAX_PER_H


def _own_dir() -> Path:
    """The dossiers' directory, a real directory (never a link: what is written there never lands
    elsewhere), its owner's only: made 0700 when absent, put back to 0700 when it is open to others.
    Raises OSError."""
    from eregion_core.channel_reader import Refused
    try:
        st = os.lstat(DOSSIER_DIR)
    except FileNotFoundError:
        DOSSIER_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        st = os.lstat(DOSSIER_DIR)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        raise Refused(f"{DOSSIER_DIR} n'est pas un répertoire (un lien, jamais suivi)")
    if stat.S_IMODE(st.st_mode) & 0o077:
        os.chmod(DOSSIER_DIR, 0o700)
    return DOSSIER_DIR


def _write(path: Path, doc: dict) -> None:
    """Whole, 0600, never through a link (SEC13, SEC16): a new file beside it, renamed over it — a link in
    its place is replaced, never followed."""
    from glorfindel.response.state import _atomic_write_text
    _own_dir()
    _atomic_write_text(path, json.dumps(doc, indent=1, sort_keys=True, default=str))


def _read(path: Path) -> dict | None:
    """A dossier of the directory, or None (a link, not a file, unreadable)."""
    try:
        if not stat.S_ISREG(os.lstat(path).st_mode):
            return None
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _composed_within_hour(now: float, but: str) -> int:
    """The dossiers composed in the hour before `now`, all VMs, `but` this one."""
    n = 0
    for f in DOSSIER_DIR.glob("*.json"):
        try:
            if f.name == but or os.lstat(f).st_mtime < now - 3600:
                continue
        except OSError:
            continue
        doc = _read(f)
        at = _epoch((doc or {}).get("compose_a"))
        n += bool(doc and doc.get("compose") is True and at is not None and now - 3600 < at <= now + 60)
    return n


def _header(state: dict, kind: str, action: str, source: str, exercise_run: str, now: float) -> dict:
    signal = state["signal"]
    ctx = _dict(signal.get("context"))
    rid = str(signal.get("resource_id") or "")
    t, where = signal_time(signal)
    iso, _ = _isolation_state(rid) if kind == ISOLATION else (None, "")
    return {"format": FORMAT, "pour_information": True, "resource_id": rid, "vm": rid.rstrip("/").rsplit("/", 1)[-1],
            "signal_id": str(signal.get("signal_id") or ""), "run_id": str(ctx.get("run_id") or ""),
            "rule_name": str(ctx.get("rule_name") or ""), "ttp": str(signal.get("ttp") or ""),
            "attribution": str(ctx.get("attribution") or ""), "T": t, "T_lu_dans": where,
            "perimetre": kind, "action": action, "executee": kind == ISOLATION,
            "isolated_at": str((iso or {}).get("isolated_at") or ""), "source": source,
            "exercise_run": exercise_run, "etape": 0, "etapes": {"0": _iso(now)}, "compose_a": _iso(now),
            "leve_vu_a": ""}


def at_cycle_end(state: dict, data_plane: bool, source: str, exercise_run: str, now: float | None = None) -> str:
    """Step 0, at the end of `store_cycle`: the dossier of a cycle in scope written, its file's name
    returned for the debug line ("" out of scope, or unwritten — said in the log). Never raises; never
    touches the state nor the signal. The facts are read first, outside the lock (the cycles of the VMs
    never wait behind one another's reads); under it, only the hour's count and the write — the facts
    dropped when the ceiling is reached. The ceiling holds within this process (its lock): the watch,
    and a `glorfindel respond` beside it, each count their own writes against the same files."""
    try:
        kind, action = scope(state, data_plane)
        if not kind:
            return ""
        now = time.time() if now is None else now
        signal = state["signal"]
        path = file_for(str(signal.get("resource_id") or ""), str(signal.get("signal_id") or ""))
        doc = _header(state, kind, action, source, exercise_run, now)
        cap = max_per_h()
        facts = []
        if cap:
            from glorfindel.dossier_local import local_facts
            facts = local_facts(state, kind, source, exercise_run, _iso(now))
        with _LOCK:
            _own_dir()
            if cap == 0:
                doc.update(compose=False, faits=[], pourquoi="dossier éteint (GLORFINDEL_DOSSIER_MAX_PER_H=0)")
            elif _composed_within_hour(now, path.name) >= cap:
                doc.update(compose=False, faits=[], pourquoi=f"plafond atteint : {cap} dossiers composés dans "
                                                              "l'heure (GLORFINDEL_DOSSIER_MAX_PER_H)")
            else:
                doc.update(compose=True, faits=facts)
            _write(path, doc)
        return path.name
    except Exception as exc:          # the dossier never costs the cycle nor its debug line
        log.warning("dossier non écrit : %s", _first_line(exc))
        return ""


def _held(doc: dict, isolations: list[dict]) -> bool:
    """The dossier's VM still under quarantine since the moment it is about: an active isolation of the
    VM isolated at that moment or later — its own isolation (`isolated_at`; isolating an isolated VM
    again rewrites it, with no lift: providers/azure/isolation.py), or, for a proposal, an isolation
    since its signal (the proposal approved). Held is the side that keeps a dossier."""
    mine = _epoch(doc.get("isolated_at"))
    since = mine if mine is not None else (_epoch(doc.get("T")) or _epoch(doc.get("compose_a")) or 0.0) - 60
    for iso in isolations:
        if not _same_id(iso.get("resource_id"), doc.get("resource_id")):
            continue
        at = _epoch(iso.get("isolated_at"))
        if at is not None and at >= since:
            return True
        if doc.get("isolated_at") and str(iso.get("isolated_at") or "") == doc["isolated_at"]:
            return True                    # a moment that does not parse: the same text, the same one
    return False


def _gone(f: Path) -> int:
    """The file removed (1), or left and said (0): an entry that cannot be removed (a directory named
    `*.json`, a permission) never stops the pass."""
    try:
        f.unlink(missing_ok=True)
        return 1
    except OSError as exc:
        log.warning("dossier non retiré : %s — %s", f.name, _first_line(exc))
        return 0


def _rewritten(f: Path, doc: dict) -> None:
    try:
        _write(f, doc)
    except OSError as exc:
        log.warning("dossier non réécrit : %s — %s", f.name, _first_line(exc))


def retention_pass(now: float | None = None) -> int:
    """Q7: a dossier is kept RETENTION_DAYS after the lift — the clock starts at the first pass that sees
    its VM out of that quarantine (`leve_vu_a`), stops if it is held again; a proposal never executed,
    from its first pass. Removed past it; an unreadable file, past it by its date. Nothing done while an
    isolation state cannot be read (whose VM is held is then unknown). Returns the files removed."""
    from glorfindel.response.state import active_isolations, unreadable_states
    now = time.time() if now is None else now
    try:
        _own_dir()
    except OSError:
        return 0
    if any(u.startswith("isolation/") for u in unreadable_states()):
        return 0
    isolations, removed, limit = active_isolations(), 0, RETENTION_DAYS * 86400
    with _LOCK:
        for f in sorted(DOSSIER_DIR.glob("*.json")):
            try:
                st = os.lstat(f)
            except OSError:
                continue
            doc = _read(f)
            if doc is None:
                if not stat.S_ISREG(st.st_mode) or now - st.st_mtime > limit:
                    removed += _gone(f)              # a link, or an unreadable file past its time
                continue
            lifted = _epoch(doc.get("leve_vu_a"))
            if _held(doc, isolations):
                if doc.get("leve_vu_a"):
                    _rewritten(f, {**doc, "leve_vu_a": ""})
            elif lifted is None:
                _rewritten(f, {**doc, "leve_vu_a": _iso(now)})
            elif now - lifted > limit:
                removed += _gone(f)
    return removed


def load(resource_id: str, signal_id: str) -> dict | None:
    """The dossier of this VM and signal, or None (absent, unreadable, another VM's)."""
    doc = _read(file_for(resource_id, signal_id))
    return doc if doc is not None and _same_id(doc.get("resource_id"), resource_id) else None
