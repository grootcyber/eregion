"""The watch's `dossier` thread: the reads of Azure of each dossier, after step 0 (DOS4, #1138;
`docs/design/dossier-isolation.md` §4.5, §7, §12).

**The steps** (§4.5), at the watch's housekeeping (every ~60 s), one pass at a time, in a thread of its own
— never the VM's, never under its lock, never in the queue of decisions:
  1      the first pass after step 0: the five reads of `glorfindel/enquiry/platform.py`;
  1 bis  at T + 5, T + 15 min, and when its last read is complete (`SETTLE_S`: the activity log's window
         to T + 30 min and its latency, T + 35 min), the reads whose window was still open or whose
         source had not delivered (`a_relire`) — read again, their facts replaced;
  2      the drain settled (DRN1: cut, refused, or never confirmed): F5b read again (local) and the
         activity log (F5a, Glorfindel's own gestures and their duration);
  réglé  after that last reading: what is still `en_attente` becomes `illisible`, with why — the source
         delivered nothing in its window and its latency, or its window was still open at its last
         reading and the budget did not let it be read again — and the dossier is read no more.

**Never for a detection attributed to no VM** (the decision of 23/11): its dossier keeps its local facts
and says « pas de lecture d'Azure, aucune VM attribuée » (written at step 0, `glorfindel/dossier.py`).

**The budget** (the decisions of 24/11): each step takes its calls from the ARM budget, the dossier's own
(`glorfindel/read_budget.py`, `ARM`) — never from Log Analytics', the detection's. The dossiers wait in
their order — a real one before an exercise, a critical object (`critique`) before the others, the oldest
first — and a dossier refused never lets one behind it read (strict order). A dossier whose step 1 has not
found room by `SETTLE_S` says « non composé » on its card, with what held the budget; a critical object
never: it waits until the budget lets it read. A dossier written before DOS4 (no `lectures`) is left as it is.

Facts only, for the human: nothing here reaches the model, the signal, the memory or a gate.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from glorfindel import dossier, read_budget
from glorfindel.dossier import EN_ATTENTE, ILLISIBLE, ISOLATION, LU, fact
from glorfindel.dossier_platform import (
    MARKS_S, SETTLE_S, complete, done_at, platform_facts, system_of, with_system,
)
from glorfindel.enquiry import catalog
from glorfindel.enquiry.platform import PLATFORM_READS
# The calls each read makes when its log holds one page (the budget is taken before; the pages past it
# are noted after): the activity log reads the VM and its group, the instance view the model and the view.
CALLS = {"activity_window": 2, "backup_jobs": 1, "instance_view": 2, "host_metrics": 1, "resource_health": 1}
STEP2_READS = ("activity_window",)
NOTHING = "la source n'a rien livré : sa fenêtre close et sa latence passée"
NOT_READ_AGAIN = "sa fenêtre n'était pas close à sa dernière lecture, et le budget ne l'a pas laissé relire"
DRAIN_OPEN = "la coupure est toujours en attente sur Azure au réglage du dossier"
WAITING, NOT_COMPOSED, DONE, SETTLED = "attente_budget", "non_composees", "faites", "reglees"
_SUMMARY = ("F1", "platform_reads")


def _when(text) -> datetime | None:
    return catalog._when(text)


def _priority(doc: dict) -> tuple:
    """A real dossier before an exercise; a critical object first; the oldest first."""
    return (doc.get("source") == "exercise", not doc.get("critique", True), str(doc.get("T") or ""))


def _drain_now(doc: dict, now: datetime) -> dict:
    from glorfindel.dossier_local import _drain
    return _drain({"signal": {"resource_id": doc.get("resource_id")}, "outcome": {}}, ISOLATION, now.isoformat())


def _facts_of(doc: dict) -> dict:
    return {(f.get("code"), f.get("id")): f for f in doc.get("faits") or [] if isinstance(f, dict)}


def due(doc: dict, now: datetime) -> tuple[str, list[str]]:
    """(the step due now — "1", "1 bis", "2", "réglé" or "" — and the reads it makes)."""
    lec = doc.get("lectures")
    if not doc.get("compose") or not isinstance(lec, dict) or lec.get("etat") in (NOT_COMPOSED, SETTLED, "sans_lecture"):
        return "", []
    t = _when(doc.get("T"))
    if not lec.get("faites_a"):
        return "1", list(PLATFORM_READS)
    last = _when(lec.get("faites_a"))
    if t is None or last is None:
        return "réglé", []
    drain = _facts_of(doc).get(("F5b", "drain"))
    if doc.get("perimetre") == ISOLATION and drain and drain.get("etat") == EN_ATTENTE \
            and _drain_now(doc, now).get("etat") != EN_ATTENTE:
        return "2", list(STEP2_READS)
    again = [i for i in lec.get("a_relire") or [] if i in PLATFORM_READS]
    if again and any(last < t + timedelta(seconds=m) <= now for m in MARKS_S):
        return "1 bis", again
    if now >= t + timedelta(seconds=SETTLE_S):
        return "réglé", []
    return "", []


def _summary(etat: str, dit: str, now: datetime, pourquoi: str = "", valeurs=None) -> dict:
    return fact(*_SUMMARY, etat=etat, dit=dit, pourquoi=pourquoi, valeurs=valeurs, lu_a=now.isoformat(),
                source="la watch (le fil dossier)", lecture="les lectures d'Azure du dossier (DOS4)")


def _merged(doc: dict, new: list[dict]) -> list[dict]:
    """The facts of `doc` with each of `new` in place of the one of its code and id, the others kept."""
    by = {(f["code"], f["id"]): f for f in new}
    kept = [by.pop((f.get("code"), f.get("id")), f) for f in doc.get("faits") or [] if isinstance(f, dict)]
    return kept + list(by.values())


def _apply(doc: dict, readings: dict, calls: int, step: str, t: datetime, now: datetime) -> dict:
    new = platform_facts(readings, t, now)
    if system := system_of(readings):
        f6g = _facts_of(doc).get(("F6g", "model_inputs"))
        if f6g:
            new.append(with_system(f6g, system))
    if step == "2":
        new.append(_drain_now(doc, now))
    lec = dict(doc.get("lectures") or {})
    etats = {**(lec.get("etats") or {}), **{i: r.etat for i, r in readings.items()}}
    open_ = [i for i, r in readings.items() if r.etat == catalog.EN_ATTENTE
             or (r.etat == catalog.LIGNES and not complete(i, t, now))]
    again = sorted((set(lec.get("a_relire") or []) - set(readings)) | set(open_)) if lec.get("faites_a") else sorted(open_)
    lec.update(etat=DONE, faites_a=now.isoformat(), etats=etats, a_relire=again,
               appels=int(lec.get("appels") or 0) + calls, passes=[*(lec.get("passes") or []), now.isoformat()][-8:])
    lec.pop("attente_budget_depuis", None)
    unread = sorted(i for i, e in etats.items() if catalog.CARD_STATE[e] == ILLISIBLE)
    new.append(_summary(LU, f"lectures d'Azure faites ({lec['appels']} appel(s))" + (
        f" ; illisibles : {', '.join(unread)}" if unread else ""), now, valeurs={"etats": etats}))
    step_key = "1" if step == "1 bis" else step
    return {**doc, "faits": _merged(doc, new), "lectures": lec, "etape": max(int(doc.get("etape") or 0), int(step_key)),
            "etapes": {**(doc.get("etapes") or {}), step.replace(" ", "_"): now.isoformat()}}


def _why_waiting(f: dict, t: datetime | None) -> str:
    """Why a fact still waiting at the settling is unreadable: its source delivered nothing once its read
    was complete, or it was last read before that (the budget did not let it be read again)."""
    if (f.get("code"), f.get("id")) == ("F5b", "drain"):
        return DRAIN_OPEN
    read_id, last = f.get("lecture_id"), _when(f.get("lu_a"))
    if t is not None and read_id in PLATFORM_READS and last is not None and last < done_at(read_id, t):
        return NOT_READ_AGAIN
    return NOTHING


def _settled(doc: dict, now: datetime) -> dict:
    """After the last reading: what is still waiting is unreadable, with why (`_why_waiting`)."""
    facts, t = [], _when(doc.get("T"))
    for f in doc.get("faits") or []:
        if isinstance(f, dict) and (f.get("code"), f.get("id")) == ("F5b", "drain") and f.get("etat") == EN_ATTENTE:
            f = _drain_now(doc, now)
        if isinstance(f, dict) and f.get("etat") == EN_ATTENTE:
            f = {**f, "etat": ILLISIBLE, "pourquoi": _why_waiting(f, t), "lu_a": now.isoformat()}
            f.pop("etat_lecture", None)
        facts.append(f)
    return {**doc, "faits": facts, "lectures": {**(doc.get("lectures") or {}), "etat": SETTLED},
            "regle_a": now.isoformat()}


def _budget_why(budget) -> str:
    """What held the ARM budget, as its count says it — never a guess."""
    cap, used = budget.per_min(), budget.used()
    if not cap:
        return f"lectures d'Azure du dossier éteintes ({budget.env}=0)"
    return (f"budget {budget.service} du dossier tenu : {sum(used.values())} appel(s) dans la minute "
            f"({', '.join(f'{k} {v}' for k, v in sorted(used.items())) or 'aucun'}) sur {cap} ({budget.env})")


def _waiting(doc: dict, now: datetime, t: datetime | None, why: str) -> dict | None:
    """Step 1 refused by the budget: the dossier waits, said; past SETTLE_S, not composed — a critical
    object never: it waits."""
    lec = dict(doc.get("lectures") or {})
    since = lec.get("attente_budget_depuis") or now.isoformat()
    if not doc.get("critique", True) and (t is None or now >= t + timedelta(seconds=SETTLE_S)):
        lec.update(etat=NOT_COMPOSED, pourquoi=why, attente_budget_depuis=since)
        summary = _summary(ILLISIBLE, "lectures d'Azure non composées", now, pourquoi=why)
    else:
        if lec.get("etat") == WAITING:
            return None                       # said already: nothing to write
        lec.update(etat=WAITING, pourquoi=why, attente_budget_depuis=since)
        summary = _summary(EN_ATTENTE, "lectures d'Azure en attente du budget ARM du dossier", now, pourquoi=why)
    return {**doc, "lectures": lec, "faits": _merged(doc, [summary])}


def _read(connector, doc: dict, ids: list[str], t: datetime | None, now: datetime, vault: tuple) -> tuple[dict, int]:
    if t is None:
        why = "l'heure du signal ne se lit pas : la fenêtre ne s'ancre pas"
        return {i: catalog.Reading(i, catalog.REFUSEE, why=why) for i in ids}, 0
    try:
        return connector.dossier_reads(str(doc.get("resource_id") or ""), t, vault=vault[0], vault_rg=vault[1],
                                       only=ids, now=now)
    except NotImplementedError:
        why = "le fournisseur ne lit pas le dossier"
    except Exception as exc:
        why = f"lecture en erreur : {dossier._first_line(exc)}"
    return {i: catalog.Reading(i, catalog.ECHEC, why=why) for i in ids}, 0


def reads_pass(connector, now: datetime | None = None, budget=None) -> list[dict]:
    """One pass of the `dossier` thread over every dossier on disk, in their order. Returns
    [{"vm", "dossier", "etape", "issue"}] — `issue`: `lu`, `attente_budget`, `non_compose`, `regle`."""
    from glorfindel.config import resolve_backup_vault
    now = now or datetime.now(timezone.utc)
    budget = budget or read_budget.ARM
    try:
        vault = resolve_backup_vault(None)[:2]
    except Exception:
        vault = ("", "")
    report, blocked = [], False
    for path, doc in sorted(dossier.dossiers(), key=lambda p: _priority(p[1])):
        step, ids = due(doc, now)
        if not step:
            continue
        line = {"vm": str(doc.get("vm") or ""), "dossier": path.name, "etape": step}
        if step == "réglé":
            dossier.update(path, lambda d: _settled(d, now))
            report.append({**line, "issue": "regle"})
            continue
        t = _when(doc.get("T"))
        need = sum(CALLS[i] for i in ids) if t is not None else 0
        if blocked or (need and not budget.take(need)):
            blocked = True                   # strict order: no dossier behind it reads in this pass
            if step == "1":
                why = _budget_why(budget)
                written = dossier.update(path, lambda d: _waiting(d, now, t, why))
                issue = (written or doc).get("lectures", {}).get("etat")
                report.append({**line, "issue": "non_compose" if issue == NOT_COMPOSED else "attente_budget"})
            elif t is not None and now >= t + timedelta(seconds=SETTLE_S):
                # Its last reading refused: settled all the same, each fact still open saying why.
                dossier.update(path, lambda d: _settled(d, now))
                report.append({**line, "issue": "regle"})
            continue
        readings, calls = _read(connector, doc, ids, t, now, vault)
        if calls > need:
            budget.spend(calls - need, read_budget.DOSSIER)
        dossier.update(path, lambda d: _apply(d, readings, calls, step, t or now, now))
        report.append({**line, "issue": "lu"})
    return report
