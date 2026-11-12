"""bench_h0_reader — what the bench's two targets read on Imladris, sent by ssh (BNC1, #682).

Sent on stdin by scripts/bench_shared.py (`read_h0`), never into the watch itself: it runs in a
disposable container of the deployed watch's image (`docker run --rm --network none --read-only
--cap-drop ALL --security-opt no-new-privileges`), with the watch's runs/, its ~/.glorfindel and its
glorfindel-config.yaml mounted `readonly` — read-only by construction: no network (no IMDS, no
token), no capability, nothing it could write. It reads files, calls no cloud and no model, and
prints one JSON object on stdout, only what the two targets need (a later step: a read-only
sub-command shipped in the image, in place of this script from the workstation's checkout):

  preflight   the target as Imladris sees it: its configured and effective mode, its readiness (verdict
              and codes), the quarantine NSG enabled or not, its isolation if any; Orodruin's
              contract as Orodruin last published it (runs/glorfindel/orodruin/contract.json, DG-b);
  report      the same isolation, the run's report (runs/glorfindel/<run_id>.json: its metrics, a
              few of them), the watch's cycles of that run (`exercise_run`) and its own
              `recovery_complete` on the VM after T0 (REC1), the lifts of the console and of the bot
              (runs/console|bot/manual_actions.jsonl, `release_isolation` on the VM after T0), and the
              lift held by the watch's recovery (~/.glorfindel/escalations.jsonl, `release_hold` on the
              VM after T0: its kind, its time and whether it is still pending — a card closed stays in
              the file —, never its reason — BNC3a);
  history     the VM's quarantines over every run (BNC3b, #770), for the clean point and the drains
              of « restore d'abord »: each isolation of the VM — the watch's `isolate_vm` cycles in
              every runs/glorfindel/*_debug.jsonl (executed, verified, partial; `verified_at`,
              `action_s`), the console's and the bot's (manual_actions.jsonl) —, each lift — the
              watch's `release_isolation` cycles (verified or not), a `release_isolation` or a
              `reset` of the console or the bot with its status —, its isolation now, and the files
              it could not read, a line that is not JSON, a mount of runs/console or runs/bot missing (said,
              never skipped: a quarantine unread is no quarantine absent); and how many cycle files
              it read — none is unreadable too, judged on the workstation.

What it never sends back: a reasoning, a signal's raw content, a resource id (a VM is its name),
an identifier of any kind. The caller masks again what it prints (bench_shared.scrub).

Stdlib only, Python 3.10 (the image's floor is 3.11; Imladris's host is 3.10): the product's modules
are imported only for the mode and the readiness, each in its own try.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path

RUNS = Path("runs")
HOME = Path(os.environ.get("HOME") or "/root")
# The cycle and lift fields kept: nothing the model wrote, nothing a signal carried but its event.
_OUTCOME_KEYS = ("executed", "verified", "verified_at", "action_s", "status")
_SINCE_MARGIN_S = 600.0
# The kinds of a held lift's card (glorfindel/recovery_watch.py, `card(…)`): the last word of its id.
_HOLD_KINDS = ("failed", "point_unknown", "not_this_vm", "not_in_place", "point_after", "stopped")


def _epoch(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _name(resource_id) -> str:
    return str(resource_id or "").rstrip("/").rsplit("/", 1)[-1].lower()


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _lines(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    doc = json.loads(line)
                except ValueError:
                    continue
                if isinstance(doc, dict):
                    yield doc
    except OSError:
        return


def isolation(vm: str) -> dict | None:
    """The VM's isolation state, if Imladris holds one: its times, never its rules nor its ids."""
    for f in sorted(glob.glob(str(HOME / ".glorfindel" / "isolation" / "*.json"))):
        st = _json(Path(f))
        if isinstance(st, dict) and _name(st.get("resource_id")) == vm:
            drains = st.get("drains_at")
            return {"isolated_at": str(st.get("isolated_at") or ""),
                    "drains_at": [str(d) for d in drains] if isinstance(drains, list) else [],
                    "releasing_at": str(st.get("releasing_at") or "")}
    return None


def target(vm: str) -> dict:
    out: dict = {"vm": vm, "isolation": isolation(vm)}
    try:
        from glorfindel.config import load_glorfindel_config
        cfg = load_glorfindel_config()
        out["configured"] = cfg.autonomy.resolve(vm)
        out["quarantine_nsg"] = bool(cfg.isolation.quarantine_nsg)
    except Exception as e:  # noqa: BLE001 — said, never a mode
        out["config_error"] = f"{type(e).__name__}"
        return out
    try:
        from glorfindel import readiness
        mode, hold = readiness.effective_mode(vm, out["configured"])
        out["effective"] = mode
        out["hold"] = str((hold or {}).get("reason") or (hold or {}).get("code") or "") if hold else ""
        rec = readiness.get(vm) or {}
        out["readiness"] = str(rec.get("verdict") or "")
        out["readiness_codes"] = sorted({str(r.get("code")) for r in rec.get("reasons") or []
                                         if isinstance(r, dict) and r.get("code")})
    except Exception as e:  # noqa: BLE001
        out["readiness_error"] = f"{type(e).__name__}"
    return out


def contract() -> dict | None:
    doc = _json(RUNS / "glorfindel" / "orodruin" / "contract.json")
    if not isinstance(doc, dict):
        return None
    codes = doc.get("codes")
    return {"verdict": str(doc.get("verdict") or ""), "at": str(doc.get("at") or ""),
            "codes": [str(c) for c in codes] if isinstance(codes, list) else []}


def _cycle(doc: dict) -> dict:
    o = doc.get("outcome") if isinstance(doc.get("outcome"), dict) else {}
    s = doc.get("signal") if isinstance(doc.get("signal"), dict) else {}
    return {"timestamp": str(doc.get("timestamp") or ""), "action": str(doc.get("action") or ""),
            "escalate": bool(doc.get("escalate")), "event": str(s.get("event") or ""),
            "outcome": {k: o[k] for k in _OUTCOME_KEYS if k in o}}


def run_view(run_id: str, vm: str) -> dict:
    out: dict = {"isolation": isolation(vm)}
    report = _json(RUNS / "glorfindel" / f"{run_id}.json")
    if not isinstance(report, dict):
        out["run"] = None
        return out
    m = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    out["run"] = {"scenario": str(report.get("scenario") or ""), "mitre": str(report.get("mitre") or ""),
                  "result": str(report.get("result") or ""),
                  "attack_time": m.get("attack_time"), "detection": str(m.get("detection") or ""),
                  "detection_latency_s": m.get("detection_latency_s"),
                  "request": str(m.get("request") or ""), "target": _name(m.get("resource_id"))}
    t0 = _epoch(m.get("attack_time"))
    cycles = []
    for f in sorted(glob.glob(str(RUNS / "glorfindel" / "*_debug.jsonl"))):
        try:
            if t0 is not None and os.path.getmtime(f) < t0 - _SINCE_MARGIN_S:
                continue
        except OSError:
            continue
        for doc in _lines(Path(f)):
            s = doc.get("signal") if isinstance(doc.get("signal"), dict) else {}
            at = _epoch(doc.get("timestamp"))
            if doc.get("exercise_run") == run_id:
                cycles.append({**_cycle(doc), "kind": "run"})
            elif (s.get("event") == "recovery_complete" and t0 is not None and at is not None and at > t0
                  and _name(s.get("resource_id")) == vm):
                cycles.append({**_cycle(doc), "kind": "recovery"})
    out["cycles"] = sorted(cycles, key=lambda c: c["timestamp"])
    lifts = []
    for hand in ("console", "bot"):
        for doc in _lines(RUNS / hand / "manual_actions.jsonl"):
            s = doc.get("signal") if isinstance(doc.get("signal"), dict) else {}
            at = _epoch(doc.get("timestamp"))
            if (doc.get("action") == "release_isolation" and t0 is not None and at is not None and at > t0
                    and _name(s.get("resource_id")) == vm):
                o = doc.get("outcome") if isinstance(doc.get("outcome"), dict) else {}
                lifts.append({"timestamp": str(doc.get("timestamp")), "hand": hand,
                              "status": str(o.get("status") or "")})
    out["lifts"] = sorted(lifts, key=lambda x: x["timestamp"])
    # BNC3a: the lift held by the watch's recovery (recovery_watch._card, `release_hold`) — its kind and
    # its time, never its reason (it names the job, the point, the VM's id).
    holds = []
    for doc in _lines(HOME / ".glorfindel" / "escalations.jsonl"):
        at = _epoch(doc.get("first_seen") or doc.get("timestamp"))
        if (doc.get("escalation_type") == "release_hold" and t0 is not None and at is not None and at > t0
                and _name(doc.get("resource_id")) == vm):
            kind = str(doc.get("signal_id") or "").rsplit("-", 1)[-1]
            holds.append({"timestamp": str(doc.get("first_seen") or doc.get("timestamp")),
                          "kind": kind if kind in _HOLD_KINDS else "",
                          "status": "pending" if doc.get("status") == "pending" else "closed"})
    out["holds"] = sorted(holds, key=lambda x: x["timestamp"])
    return out


def _number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _lines_said(path: Path, unread: list):
    """`_lines`, but a file that can't be opened or read through is said in `unread` — and each line
    that is not a JSON object too (a write cut, a full disk: BNC3b review), never skipped silently."""
    bad = 0
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    doc = json.loads(line)
                except ValueError:
                    bad += 1
                    continue
                if isinstance(doc, dict):
                    yield doc
                else:
                    bad += 1
    except (OSError, UnicodeDecodeError) as e:
        unread.append(f"{path.name}: {type(e).__name__}")
    if bad:
        unread.append(f"{path.name}: {bad} ligne(s) illisible(s)")


def history(vm: str) -> dict:
    """BNC3b: the VM's isolations and lifts over every run, as the workstation judges them (the
    clean point, the drains). Times and flags only: never a reasoning, a rule, an id."""
    unread: list[str] = []
    isolations, lifts = [], []
    files = sorted(glob.glob(str(RUNS / "glorfindel" / "*_debug.jsonl")))
    for f in files:
        for doc in _lines_said(Path(f), unread):
            s = doc.get("signal") if isinstance(doc.get("signal"), dict) else {}
            if _name(s.get("resource_id")) != vm:
                continue
            o = doc.get("outcome") if isinstance(doc.get("outcome"), dict) else {}
            if doc.get("action") == "isolate_vm":
                isolations.append({"timestamp": str(doc.get("timestamp") or ""), "source": "watch",
                                   "executed": o.get("executed") is True, "verified": o.get("verified") is True,
                                   "partial": o.get("partial") is True,
                                   "verified_at": str(o.get("verified_at") or ""),
                                   "action_s": _number(o.get("action_s"))})
            elif doc.get("action") == "release_isolation":
                lifts.append({"timestamp": str(doc.get("timestamp") or ""), "source": "watch",
                              "verified_at": str(o.get("verified_at") or ""), "verified": o.get("verified") is True,
                              "status": str(o.get("status") or "")})
    for hand in ("console", "bot"):
        if not (RUNS / hand).is_dir():
            unread.append(f"runs/{hand} : absent (son montage manque)")
            continue
        path = RUNS / hand / "manual_actions.jsonl"
        if not path.exists():
            continue
        for doc in _lines_said(path, unread):
            s = doc.get("signal") if isinstance(doc.get("signal"), dict) else {}
            if _name(s.get("resource_id")) != vm:
                continue
            o = doc.get("outcome") if isinstance(doc.get("outcome"), dict) else {}
            if doc.get("action") == "isolate_vm":
                isolations.append({"timestamp": str(doc.get("timestamp") or ""), "source": hand,
                                   "executed": True, "verified": o.get("verified") is True, "partial": False,
                                   "verified_at": str(o.get("verified_at") or ""),
                                   "action_s": _number(o.get("action_s"))})
            elif doc.get("action") in ("release_isolation", "reset"):
                lifts.append({"timestamp": str(doc.get("timestamp") or ""), "source": hand,
                              "verified_at": str(o.get("verified_at") or ""), "verified": o.get("verified") is True,
                              "status": str(o.get("status") or "")})
    return {"isolation": isolation(vm), "files": len(files), "unreadable": unread,
            "isolations": sorted(isolations, key=lambda x: x["timestamp"]),
            "lifts": sorted(lifts, key=lambda x: x["timestamp"])}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("preflight", "report", "history"):
        print(json.dumps({"error": "usage: preflight <vm> | report <vm> <run_id> | history <vm>"}))
        return 2
    ask, vm = argv[0], argv[1].lower()
    if ask == "preflight":
        out = {"target": target(vm), "contract": contract()}
    elif ask == "history":
        out = history(vm)
    else:
        out = run_view(argv[2] if len(argv) > 2 else "", vm)
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
