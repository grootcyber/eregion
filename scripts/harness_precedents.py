"""MEM-H (#1028): the genre `precedents` of the harness — the same cases, played under three memories:
none (`aucune`), the memory by distance (`distance`, ChromaDB, today's) and the memory by keys (`cles`,
SQLite, MEM2). Run by `scripts/llm_smoke.py --precedents` (`make llm-compare … PRECEDENTS=1`): C1, C2 and
C3 of the matrix (docs/design/enquete-raisonnee.md §9.1); with `--enquete`, the enquiry's loop under the
same three memories, C4, C5 and C6. The maintainer's gesture: its calls are paid. In the tests the model is
always replaced.

**The precedents are built here**, never read from a real memory (Imladris's, or the operator's): each
case's history (`history`) is written by the harness — a VM of the case, three others, the case's
technique and three others, decisions that contained and decisions closed without action, an exercise and
a cycle past the 90 days — and stored, cycle by cycle at its date, in **a fresh memory of each kind, for
this case alone** (a folder of its own under a throwaway directory, removed before the first call). One
case's memory never reaches another's (a test, M7032). The two memories are the code of the watch
(`glorfindel.memory.CycleMemory`, its mode given, the switch `GLORFINDEL_MEMORY` never read), searched as
`load_context` searches them (`retrieve_similar(signal, n=3)`), with the signal as the RulePoller emits
it (its rule, `provider: azure`).

**What the model sees changes by the precedents only**: decide's state is the harness's (`_state` of
llm_smoke, or the enquiry's), its signal the one the memory was searched with (`signal_of`: the
RulePoller's, its rule and its provider — the enquiry's reads kept in it), its `past_cycles` the memory's.
Nothing of the production changes: the prompt, `_build_user_message()`, the few-shot and the tool are
untouched. C1–C3 here are the decision without an enquiry (no `investigative_context`), on seven cases of
llm_smoke; C4–C6 the ten cases of ENQ4 — the two passages share no case: one compares memories within its
own cases, never the loop against the decision alone.

**What is said**, before any call: each case's precedents under each memory, and the ceiling (HRN2) —
the bound of calls, the dollars, the cost at the reference run's price. After: per case, the decision and
the confidence under each memory, **what moves** between them (the most frequent action, the median
confidence; counted, never left unsaid — M7033), the overconfident errors by the CD's rule
(`eregion_cd.overconfident_drift`, one rule, three readers), then HRN1's cost and latency by memory
(genre `precedents/<memory>`). Nothing of it enters the attestation.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from statistics import median

GENRE = "precedents"
NONE, DISTANCE, KEYS = "aucune", "distance", "cles"
MEMORIES = (NONE, DISTANCE, KEYS)
# Each pair read « from → to »: what the memory by distance adds to none, what the keys add to none, what
# the keys change from the distance (MEM2 against today's).
PAIRS = ((NONE, DISTANCE), (NONE, KEYS), (DISTANCE, KEYS))
# A median confidence that moves by this much or more is counted as moved.
CONF_MOVE = 0.10
DAY = 86400
NOW = 1_795_000_000.0          # 2026-11-17 (fixed: the history's dates, and the 90 days counted from it)
ROOT = Path(__file__).resolve().parents[1]
RID = ("/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Compute"
       "/virtualMachines/vm-smoke")
# The reference run of 23/11 (HRN1): 18 cases × 3 runs, 126 calls made of its bound of 162, about 1.15 $.
REFERENCE_USD, REFERENCE_CALLS, REFERENCE_BOUND = 1.15, 126, 162
# ENQ4's estimate of one passage of the enquiry (docs/operations.md, « Le harnais de l'enquête »): 1 to 2.5 $.
ENQUETE_PASS_USD = (1.0, 2.5)

# The shipped rules (glorfindel/rules/azure/detection_rules.yaml) — the signal's, and each cycle's.
RULES = {"T1486": "ransomware-disk-write", "T1041": "data-exfiltration-blob",
         "T1110.001": "ssh-brute-force", "T1548.003": "sudo-privilege-escalation",
         "T1136.001": "t1136-001-local-account-creation-linux-v1"}
TECHNIQUES = tuple(RULES)

# What was decided before on each technique, written by the harness (never a real cycle): a decision that
# contained, and one closed without action (a false positive explained). (action, confidence, reasoning)
CONTAINED = {
    "T1486": ("isolate_vm", 0.92, "Écriture disque soutenue à 140 Mo/s pendant six minutes, fichiers renommés "
              "en série : chiffrement probable. Isolement pour couper la propagation, instantané pris avant."),
    "T1041": ("isolate_vm", 0.86, "Envois soutenus vers un compte de stockage externe depuis une IP interne : "
              "exfiltration probable, bloquer une IP interne ne sert à rien. Isolement pour couper le canal."),
    "T1110.001": ("block_suspicious_ip", 0.88, "52 échecs SSH en dix minutes depuis une seule IP externe, aucune "
                  "connexion acceptée : blocage de la source, la VM continue de servir."),
    "T1548.003": ("isolate_vm", 0.9, "sudo vers un shell root interactif par un compte sans droit attendu : "
                  "élévation confirmée, isolement de la VM."),
    "T1136.001": ("snapshot", 0.55, "Compte local créé hors de toute fenêtre de changement, peu d'indicateurs : "
                  "instantané, et la décision laissée à un humain."),
}
CLOSED = {
    "T1486": ("no_action", 0.8, "Écriture à 60 Mo/s pendant la sauvegarde nocturne planifiée, aucun fichier "
              "renommé : la copie de la sauvegarde, rien à faire."),
    "T1041": ("no_action", 0.75, "Envoi vers le compte de stockage de l'équipe, par l'outil de copie habituel, "
              "dans la fenêtre de la réplication : transfert attendu."),
    "T1110.001": ("monitor", 0.7, "Douze échecs depuis l'IP du bastion de l'équipe après un changement de mot "
                  "de passe : erreur de saisie, surveillance seulement."),
    "T1548.003": ("no_action", 0.8, "sudo apt-get upgrade par le compte d'administration, dans la fenêtre de "
                  "maintenance : administration courante."),
    "T1136.001": ("no_action", 0.7, "Compte de service créé par l'outil de déploiement, annoncé dans le "
                  "changement du jour : création attendue."),
}
_CONTAIN, _CLOSE = "contained", "closed"
# Each case's history: (days ago, VM, technique — 0 the case's, 1 to 3 the others in TECHNIQUES' order —,
# with its rule, what was decided, source, judged). Built so that the keys and the distance may choose
# otherwise: a rule seen on one other VM only, the case's VM newest on another technique, the newest of the
# technique elsewhere a decision closed without action. The bounds of the memory are in it: an exercise, and
# a cycle past the 90 days — neither is ever a precedent (SEC4a, SEC17). The cycles are those of the session
# of 24/11 (MEM-H, passage 1), unchanged: only their verdicts are new (MEM2b).
# MEM2b (#1161): `judged` — the operator judged the card the day after, `right`: a real attack where it
# contained (140 MB/s, files renamed), a false alarm where it was closed (the nightly backup). The oldest
# decisions of vm-bench-b were never judged: what the keys say « non jugé ». Read by the memory by keys only
# (the distance gives no verdict, as in production).
HISTORY = (
    (2, "vm-smoke", 1, True, _CONTAIN, "real", True),       # this VM, the newest: another technique
    (40, "vm-smoke", 0, False, _CONTAIN, "real", True),     # this VM, this technique, older, by `respond`
    (6, "vm-bench-a", 0, True, _CLOSE, "real", True),       # this rule elsewhere, the newest: closed
    (20, "vm-bench-a", 0, True, _CONTAIN, "real", True),    # this rule elsewhere, older: contained
    (3, "vm-bench-b", 2, True, _CLOSE, "real", False),
    (50, "vm-bench-b", 0, False, _CONTAIN, "real", False),
    (5, "vm-bench-c", 3, True, _CONTAIN, "real", True),
    (1, "vm-bench-c", 0, True, _CLOSE, "exercise", True),   # an exercise: never a precedent (SEC4a)
    (120, "vm-bench-d", 0, True, _CONTAIN, "real", True),   # past the 90 days: never a precedent (SEC17)
)

# The cases: the decision cases of llm_smoke (their rows), each with the technique its rule carries — the
# benign twins too (in production their rule names a technique: the precedents are that technique's).
CASES = [
    {"kind": "act", "label": "ransomware — sustained disk write (T1486)", "ttp": "T1486",
     "row": {"Computer": "vm-smoke", "MaxWrite": 147000000},
     "expected": {"isolate_vm", "restore_from_backup", "snapshot"}},
    {"kind": "act", "label": "brute force — failed SSH from one IP (T1110.001)", "ttp": "T1110.001",
     "row": {"SourceIP": "185.220.101.5", "FailedAttempts": 47}, "expected": {"block_suspicious_ip"}},
    {"kind": "act", "label": "sudo privilege escalation (T1548.003)", "ttp": "T1548.003",
     "row": {"ProcessName": "sudo", "SyslogMessage": "alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; "
             "COMMAND=/bin/bash", "Computer": "vm-smoke"}, "expected": {"isolate_vm"}},
    {"kind": "act", "label": "data exfiltration — upload from internal IP (T1041)", "ttp": "T1041",
     "row": {"CallerIpAddress": "10.0.0.4", "OperationName": "PutBlob", "Computer": "vm-smoke"},
     "expected": {"isolate_vm"}},
    {"kind": "caution", "label": "account creation — few indicators (T1136.001)", "ttp": "T1136.001",
     "row": {"SyslogMessage": "useradd: new user: name=svc-deploy, UID=1001", "Computer": "vm-smoke"}},
    {"kind": "caution", "label": "modest disk write under the ransomware rule — likely a large copy",
     "ttp": "T1486", "row": {"Computer": "vm-smoke", "MaxWrite": 5000000}},
    {"kind": "caution", "label": "sudo running a routine package update, under the sudo rule", "ttp": "T1548.003",
     "row": {"ProcessName": "sudo", "SyslogMessage": "alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; "
             "COMMAND=/usr/bin/apt-get update", "Computer": "vm-smoke"}},
]


def _vm(name: str) -> str:
    return RID.rsplit("/", 1)[0] + "/" + name


class _Clock:
    """The memory's clock: each cycle stored at its date, the search at NOW."""

    def __init__(self, at: float = NOW):
        self.at = at

    def __call__(self) -> float:
        return self.at


def _rule(case: dict) -> str:
    return case.get("regle") or RULES.get(case["ttp"], "")


def history(case: dict, index: int) -> list[tuple[float, dict]]:
    """The case's cycles, (their date, the cycle as `store_cycle` hands it to the memory): each tagged with
    the case (`run_id` memh-<index>, never shown to the model) — what proves no other case's memory leaked."""
    others = [t for t in TECHNIQUES if t != case["ttp"]]
    out = []
    for i, (days, vm, which, ruled, decided, source, _judged) in enumerate(HISTORY):
        ttp = case["ttp"] if which == 0 else others[which - 1]
        action, confidence, reasoning = (CONTAINED if decided == _CONTAIN else CLOSED)[ttp]
        out.append((NOW - days * DAY, {
            "signal_id": f"memh-{index}-{i}", "run_id": f"memh-{index}", "ttp": ttp, "severity": "critical",
            "resource_type": "vm", "event": "detection", "action": action, "reasoning": reasoning,
            "outcome": "success", "confidence": confidence, "source": source,
            "exercise_run": "memh-exercise" if source == "exercise" else "",
            "resource_id": _vm(vm), "rule_name": RULES[ttp] if ruled else ""}))
    return out


def verdicts_of(case: dict, index: int) -> dict[str, dict]:
    """The human verdicts of the case's history, as the memory by keys reads the cards'
    (`memory_keys.card_verdicts`): {signal_id: {"verdict", "at", "action"}} — `right`, the day after."""
    from datetime import datetime, timezone
    cycles = dict(enumerate(c for _at, c in history(case, index)))
    return {cycles[i]["signal_id"]: {
        "verdict": "right", "action": cycles[i]["action"],
        "at": datetime.fromtimestamp(NOW - (days - 1) * DAY, timezone.utc).isoformat()}
        for i, (days, *_rest, judged) in enumerate(HISTORY) if judged}


def signal_of(case: dict) -> dict:
    """The signal the memory is searched with, as the RulePoller emits it: its rule, its provider."""
    return {"signal_id": "smoke_detection", "resource_id": RID, "resource_type": "vm", "ttp": case["ttp"],
            "severity": "critical", "event": "detection", "provider": "azure",
            "raw_signal": {"first_result_row": case["row"]},
            "context": {"run_id": "smoke", "rule_name": _rule(case)}}


def open_memory(mode: str, where: Path, clock, verdicts=None):
    """The watch's own memory of `mode`, at `where` — its mode given, the switch never read; the keys reading
    the case's verdicts (`verdicts`, MEM2b), never the cards' store."""
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")     # ChromaDB: nothing sent
    from glorfindel import memory
    return memory.CycleMemory(path=where, clock=clock, mode=mode, verdicts=verdicts)


def precedents_of(case: dict, index: int, root: Path, opener=open_memory, modes=(DISTANCE, KEYS)) -> dict:
    """{memory: {"precedents": what it gives the model, "held": the cycles it held}} — each memory fresh,
    in the case's own folder under `root`, filled with the case's history only; the keys given its verdicts
    (`verdicts_of`). `aucune`: nothing."""
    out = {NONE: {"precedents": [], "held": 0}}
    for mode in modes:
        clock = _Clock()
        where = root / f"cas-{index}" / mode
        judged = {"verdicts": lambda: verdicts_of(case, index)} if mode == KEYS else {}
        mem = opener(mode, where / ("cycles.sqlite3" if mode == KEYS else "cycles"), clock, **judged)
        for at, cycle in history(case, index):
            clock.at = at
            mem.store(cycle)
        clock.at = NOW
        out[mode] = {"precedents": mem.retrieve_similar(signal_of(case), n=3), "held": mem.count()}
    return out


def table_of(cases, opener=open_memory) -> dict:
    """Every case's precedents under each memory, before any call: {label: precedents_of(…)}. The stores
    live in a throwaway directory, removed once the precedents are read."""
    with tempfile.TemporaryDirectory(prefix="eregion-memh-") as tmp:
        return {c["label"]: precedents_of(c, i, Path(tmp), opener) for i, c in enumerate(cases)}


def said(p: dict) -> dict:
    """A precedent as the report says it: its technique, its action, its VM, its age, its rule, its source,
    and its human verdict (MEM2b: the keys' — "" when none, or under the distance)."""
    at = p.get("stored_at")
    return {"ttp": p.get("ttp", ""), "action": p.get("action", ""),
            "vm": str(p.get("resource_id") or "").rsplit("/", 1)[-1], "rule": p.get("rule_name", ""),
            "age_days": round((NOW - float(at)) / DAY) if isinstance(at, (int, float)) else None,
            "source": p.get("source", ""), "cycle": p.get("signal_id", ""), "verdict": p.get("verdict", "")}


def precedent_lines(label: str, table: dict) -> list[str]:
    lines = [f"  {label}"]
    for mode in (DISTANCE, KEYS):
        shown = [said(p) for p in table[mode]["precedents"]]
        lines.append(f"      {mode:<8} : " + (" · ".join(
            f"{s['ttp']}/{s['action']} ({s['vm']}, {s['age_days']} d"
            + (f", {s['verdict'] or 'unjudged'})" if mode == KEYS else ")") for s in shown) or "none"))
    return lines


# ── What moves between the memories ─────────────────────────────────────────────────────────────────

def _action(slot: dict) -> str:
    return str(slot.get("proposed") or slot.get("action") or "")


def _top(slots: list[dict]) -> str:
    """The most frequent action — ties broken by name, never by the order drawn."""
    counts = Counter(_action(s) for s in slots)
    return min(counts, key=lambda a: (-counts[a], a)) if counts else ""


def _conf(slots: list[dict]) -> float | None:
    known = [float(s["confidence"]) for s in slots if s.get("confidence") is not None]
    return median(known) if known else None


def move(a: list[dict], b: list[dict]) -> dict | None:
    """From the draws `a` to the draws `b` of one case: whether the decision moves (the most frequent
    action), the median confidence's shift, the good calls on each side. None when a side was not drawn."""
    if not a or not b:
        return None
    ta, tb = _top(a), _top(b)
    ca, cb = _conf(a), _conf(b)
    delta = None if ca is None or cb is None else round(cb - ca, 3)
    return {"decision": ta != tb, "from": ta, "to": tb, "confidence": delta,
            "confidence_moved": delta is not None and abs(delta) >= CONF_MOVE,
            "good": [sum(1 for s in a if s.get("good")), sum(1 for s in b if s.get("good"))]}


def cd_rule():
    """The CD's rule of overconfidence (infra/glorfindel-host/cd/eregion_cd.py), read where it lives; the
    path it adds for its own imports taken out after."""
    if "eregion_cd" in sys.modules:
        return sys.modules["eregion_cd"]
    path = ROOT / "infra" / "glorfindel-host" / "cd" / "eregion_cd.py"
    saved = list(sys.path)
    try:
        spec = importlib.util.spec_from_file_location("eregion_cd", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path[:] = saved
    sys.modules["eregion_cd"] = mod
    return mod


def _draws(slots: list[dict]) -> list[tuple]:
    """The draws as the CD's rule reads them — never one the ceiling cut (its confidence is not a
    decision's: it is in the good calls as a failure, never in the overconfident errors)."""
    return [(bool(s.get("good")), _action(s), s.get("confidence")) for s in slots if not s.get("cut")]


def compare(rows: list[dict], cd=None) -> dict:
    """`rows`: [{"label", "kind", "slots": {memory: [slot]}, "_table": precedents_of(…)}]. Per case the
    moves of each pair; in all, what moved, counted, the good calls and the overconfident errors of each
    memory, and the drift of each pair by the CD's rule (`overconfident_drift`: `to` against `from`)."""
    cd = cd or cd_rule()
    cases = []
    for r in rows:
        prec = r.get("_table") or {}
        same = ([p.get("signal_id") for p in prec.get(DISTANCE, {}).get("precedents", [])]
                == [p.get("signal_id") for p in prec.get(KEYS, {}).get("precedents", [])]) if prec else None
        cases.append({"label": r["label"], "same_precedents": same,
                      "moves": {f"{a}->{b}": move(r["slots"].get(a), r["slots"].get(b)) for a, b in PAIRS}})
    totals = {"memories": {}, "pairs": {}}
    for m in MEMORIES:
        slots = [s for r in rows for s in r["slots"].get(m, [])]
        totals["memories"][m] = {"good": sum(1 for s in slots if s.get("good")), "slots": len(slots),
                                 "overconfident": sum(1 for d in _draws(slots) if cd._overconfident(d))}
    for a, b in PAIRS:
        key = f"{a}->{b}"
        drawn = [c["moves"][key] for c in cases if c["moves"][key]]
        both = [r for r in rows if r["slots"].get(a) and r["slots"].get(b)]
        drift, moved = cd.overconfident_drift({r["label"]: (r["kind"], _draws(r["slots"][b])) for r in both},
                                              {r["label"]: (r["kind"], _draws(r["slots"][a])) for r in both})
        deltas = [d["confidence"] for d in drawn if d["confidence"] is not None]
        totals["pairs"][key] = {"cases": len(drawn), "decisions_moved": sum(1 for d in drawn if d["decision"]),
                                "confidences_moved": sum(1 for d in drawn if d["confidence_moved"]),
                                "mean_confidence_shift": round(sum(deltas) / len(deltas), 3) if deltas else None,
                                "drift": drift, "drift_cases": moved}
    totals["other_precedents"] = sum(1 for c in cases if c["same_precedents"] is False)
    totals["cases"] = len(cases)
    return {"cases": cases, "totals": totals}


def _shift(d: float | None) -> str:
    return "—" if d is None else f"{d:+.2f}"


def case_lines(row: dict, cmp_case: dict, distribution) -> list[str]:
    lines = []
    for m in MEMORIES:
        slots = row["slots"].get(m) or []
        good = sum(1 for s in slots if s.get("good"))
        shown = [{**s, "action": _action(s) or "<none>"} for s in slots]
        lines.append(f"      {m:<8} {distribution(shown) if slots else 'not drawn'} — good {good}/{len(slots)}")
    parts = []
    for key, mv in cmp_case["moves"].items():
        if mv is None:
            parts.append(f"{key}: not drawn")
            continue
        what = f"MOVED ({mv['from']} → {mv['to']})" if mv["decision"] else "same"
        parts.append(f"{key}: decision {what}, confidence {_shift(mv['confidence'])}")
    lines.append("      moves: " + " · ".join(parts))
    return lines


def total_lines(t: dict) -> list[str]:
    mem = t["memories"]
    out = ["Memories   : good " + " · ".join(f"{m} {mem[m]['good']}/{mem[m]['slots']}" for m in MEMORIES)
           + " ; overconfident errors (the CD's rule) " + " · ".join(f"{m} {mem[m]['overconfident']}" for m in MEMORIES)]
    for key, p in t["pairs"].items():
        out.append(f"Moves      : {key}: {p['decisions_moved']}/{p['cases']} decisions moved, "
                   f"{p['confidences_moved']}/{p['cases']} confidences moved by {CONF_MOVE:.2f} or more "
                   f"(mean shift {_shift(p['mean_confidence_shift'])}) — drift by the CD's rule: "
                   + (p["drift"] or "none"))
    out.append(f"Precedents : the keys gave other precedents than the distance on {t['other_precedents']}/{t['cases']} "
               "case(s) — where they gave the same, a move is the draw's, not the memory's")
    return out


# ── The run of the decision's cases (C1, C2, C3) ──────────────────────────────────────────────────────

def run_bound(cases: int, runs: int, draws: int) -> int:
    """The most calls the genre makes: each case under each memory, each run one decision and its
    confirming draws — 7 × 3 × 3 × 3 = 189."""
    return max(1, cases) * len(MEMORIES) * max(1, runs) * max(1, draws)


def ceiling_lines(bound: int, max_usd: float, max_calls: int, enquete: bool = False) -> list[str]:
    """The ceiling said before the run, with the cost estimated as the documentation says it: the decision's
    at the reference run's price, the enquiry's ENQ4's estimate of a passage, times the three memories."""
    per = REFERENCE_USD / REFERENCE_CALLS
    likely = bound * REFERENCE_CALLS / REFERENCE_BOUND
    head = (f"Ceiling    : {max_calls} call(s) at most (the genre's bound {bound}), ${max_usd:.2f} of measured cost "
            "— checked before each call (HRN2)")
    if enquete:
        low, high = ENQUETE_PASS_USD
        n = len(MEMORIES)
        return [head, f"Estimate   : ENQ4's estimate of a passage of the enquiry, ${low:.2f} to ${high:.2f}, × {n} "
                      f"memories = ${n * low:.2f} to ${n * high:.2f} (docs/operations.md)"]
    return [head,
            f"Estimate   : at the reference run's price (23/11: ${REFERENCE_USD:.2f} for {REFERENCE_CALLS} calls, "
            f"${per:.4f} a call), about {likely:.0f} calls ≈ ${likely * per:.2f}, the bound ≈ ${bound * per:.2f} "
            "(a draw only when the decision isolates or blocks: the reference made "
            f"{REFERENCE_CALLS} of its {REFERENCE_BOUND})"]


def _slot(case: dict, out: dict, judge) -> dict:
    action = ((out.get("ceiling") or {}).get("proposed") or out.get("action") or "").strip()
    if not action:
        return {"action": "<no-tool-call>", "confidence": None, "escalate": True, "held_by": "", "good": False}
    good, _ = judge(case, action, bool(out.get("escalate")), bool(out.get("floor")))
    return {"action": action, "confidence": float(out.get("confidence") or 0.0),
            "escalate": bool(out.get("escalate")), "held_by": out.get("held_by") or "", "good": good,
            "draws": out.get("decision_draws") or []}


def state_for(case: dict, state_of, past: list[dict]) -> dict:
    """decide's state: the harness's (`_state`), its signal the one the memory was searched with
    (`signal_of`), its past cycles the memory's — nothing else differs between the memories."""
    state = state_of(case["ttp"], {"first_result_row": case["row"]})
    return {**state, "signal": signal_of(case), "past_cycles": [dict(p) for p in past]}


def etat_for(case: dict, etat):
    """The enquiry's state maker for `case`: its signal `signal_of(case)`, with the raw signal the loop
    built (its reads in it) — the same signal under the three memories."""
    def make(ttp, raw):
        state = etat(ttp, raw)
        return {**state, "signal": {**signal_of(case), "raw_signal": raw}}
    return make


def run(model: str, runs: int, *, meter, decide, state_of, judge, distribution, cases=None,
        opener=open_memory, say=print) -> dict:
    """Every case, `runs` times under each memory (`draw_order`: the memories interleaved within a run, so that
    a ceiling reached leaves them drawn alike). Each decision in its own slot of the meter (genre
    precedents/<memory>)."""
    cases = cases or CASES
    say(f"Precedents (MEM-H) — model: {model} · runs: {runs} · memories: {', '.join(MEMORIES)}")
    table = table_of(cases, opener)
    say("The precedents each memory gives (built by the harness, one fresh memory per case):")
    for c in cases:
        for line in precedent_lines(c["label"], table[c["label"]]):
            say(line)
    say("-" * 72)

    def draw(case: dict, m: str) -> list[dict]:
        state = state_for(case, state_of, table[case["label"]][m]["precedents"])
        with meter.slot(f"{GENRE}/{m}"):
            try:
                return [_slot(case, decide(state), judge)]
            except Exception as exc:
                return [{"action": f"<error: {type(exc).__name__}>", "confidence": None,
                         "escalate": True, "held_by": "", "good": False}]

    slots = drawn_in_order(cases, runs, meter, draw, say)
    rows = [{"label": case["label"], "kind": case["kind"], "expected": sorted(case.get("expected", ())),
             "precedents": {m: [said(p) for p in table[case["label"]][m]["precedents"]] for m in MEMORIES},
             "held": {m: table[case["label"]][m]["held"] for m in MEMORIES}, "slots": got,
             "_table": table[case["label"]]} for case, got in zip(cases, slots) if any(got.values())]
    return finish(model, runs, rows, say, distribution, stopped=meter.stopped)


def draw_order(cases: int, runs: int) -> list[tuple[int, str]]:
    """(case, memory) in the order drawn: the cases outside, each run of a case under the three memories one
    after another — a ceiling reached leaves the memories drawn alike (one draw apart), never the last one
    undrawn."""
    return [(i, m) for i in range(cases) for _ in range(runs) for m in MEMORIES]


def drawn_in_order(cases: list[dict], runs: int, meter, draw, say) -> list[dict]:
    """Each case's draws by memory, drawn in `draw_order` until the ceiling (HRN2): `draw(case, memory)` gives
    the draws of one slot; the draw the ceiling cut is a failure (`cut`), out of the overconfident errors."""
    slots = [{m: [] for m in MEMORIES} for _ in cases]
    for i, m in draw_order(len(cases), runs):
        if meter.stopped:
            break
        got = draw(cases[i], m)
        if got and (cut := meter.stopped):
            got[-1] = {**got[-1], "good": False, "cut": cut}
            say(f"→ Stopped: {cut} — no draw after this one (HRN2)")
        slots[i][m] += got
    return slots


def finish(model: str, runs: int, rows: list[dict], say, distribution, stopped: str = "") -> dict:
    """The comparison of the rows drawn, said, and the run's result (--json)."""
    cmp = compare(rows)
    for r, c in zip(rows, cmp["cases"]):
        say(f"[{GENRE}] {r['label']}" + ("" if c["same_precedents"] is not False else " — other precedents by the keys"))
        for line in case_lines(r, c, distribution):
            say(line)
    say("-" * 72)
    for line in total_lines(cmp["totals"]):
        say(line)
    for r, c in zip(rows, cmp["cases"]):
        r.pop("_table", None)
        r["moves"], r["same_precedents"] = c["moves"], c["same_precedents"]
    return {"model": model, "runs": runs, "cases": rows, "totals": cmp["totals"], "stopped": stopped}


# ── The enquiry under the three memories (C4, C5, C6) ─────────────────────────────────────────────────

def run_enquete(model: str, runs: int, *, he, meter, distribution, say=print, opener=open_memory, **kw) -> dict:
    """harness_enquete's cases under each memory in turn (genre enquete/<memory>), as `run` plays them: the
    cases outside, each run of a case under the three memories one after another — a ceiling reached leaves
    them drawn alike, never the last memory undrawn. The precedents built here before any call; decide's
    signal `signal_of(case)` (`etat_for`). `kw`: harness_enquete.run's own (decide, etat, budget, read_delay,
    modele, cases)."""
    cases = kw.pop("cases", None) or he.CASES
    etat = kw.pop("etat")
    budget = kw.get("budget") or he.loop.Budget()
    table = table_of(cases, opener)
    say(f"Enquiry under three memories (MEM-H) — model: {model} · runs: {runs} · memories: {', '.join(MEMORIES)}")
    say("The precedents each memory gives (built by the harness, one fresh memory per case):")
    for c in cases:
        for line in precedent_lines(c["label"], table[c["label"]]):
            say(line)
    say("-" * 72)

    def draw(c: dict, m: str) -> list[dict]:
        one = he.run(model, 1, meter=meter, say=lambda *_: None, genre=f"enquete/{m}", cases=[c],
                     etat=etat_for(c, etat), passe=lambda _c: table[c["label"]][m]["precedents"], **kw)
        return one["cases"][0]["slots"] if one["cases"] else []

    slots = drawn_in_order(cases, runs, meter, draw, say)
    rows = [{"label": c["label"], "kind": c["expect"], "slots": got, "_table": table[c["label"]],
             "precedents": {m: [said(p) for p in table[c["label"]][m]["precedents"]] for m in MEMORIES}}
            for c, got in zip(cases, slots) if any(got.values())]
    by = {m: {"cases": [{"label": r["label"], "expect": r["kind"], "slots": r["slots"][m]} for r in rows]}
          for m in MEMORIES}
    for m in MEMORIES:
        by[m]["totals"] = he.totals(by[m]["cases"], budget)
        say(f"=== the enquiry under the memory « {m} » ===")
        for line in he.total_lines(by[m]["totals"], budget):
            say(line)
    say("-" * 72)
    result = finish(model, runs, rows, say, distribution, stopped=meter.stopped)
    return {**result, "memories": by}
