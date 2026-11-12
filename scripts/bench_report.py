#!/usr/bin/env python3
"""bench_report — the chronology of a bench run, composed alone: `make bench-report RUN=<run_id>` (BNC1, #682).

On 09/11 (RAN1, #665) the step 8 of docs/banc-t1486.md was rebuilt by hand: each source read, its
output masked, then copied into the report's tables. Here it is read and composed — nothing is
written on Azure, on Imladris nor on Orodruin:

  on Imladris, by ssh   the run's report (runs/glorfindel/<run_id>.json: T0, the detection, the Dagorlad
                  request it was a wire of), the watch's cycles of the run, its own recovery_complete
                  (REC1), the lifts of runs/console|bot/manual_actions.jsonl, the target's isolation
                  state if it is still isolated (scripts/bench_h0_reader.py, in a disposable,
                  network-less container of the deployed image, its mounts read-only); only once
                  Imladris's host key is verified by its fingerprint;
  the activity log  the target's own resources, each read apart (`--resource-id`: the VM, its NICs),
                  never the whole group: each Run Command on the target, its start, its end, its
                  status, its caller as a role (the console, the bot, Imladris, Orodruin, a human,
                  unknown) and its duration; Imladris's write on a NIC of the target (the isolation, when
                  its state is gone: an isolation by an NSG's rules alone does not show there); the
                  target's deallocations and starts. A read that reaches MAX_EVENTS is said cut;
  the vault       its jobs on the target (`az backup job list`, up to the day after today: the day's
                  bound leaves that day out, measured 12/11): the operation, start, end, status;
  the instance view  the guest agent's status (`az vm get-instance-view`), read once, when composed.

When (BNC3a, #753): by hand, at once; at the end of `make bench-run`, `--wait cycle` — Imladris read
again until the run's cycle is written (10 min at most: on 12/11 the report composed 7 s after the
detection saw neither the isolation nor its cycle); at the end of `make bench-restore`, `--wait lift`
— until the lift, or the lift held by the watch's recovery (30 min at most). In reading only; past the
bound, the report is composed anyway and says what is not yet written. Azure is read after the wait.

The output: Markdown on stdout, in the form of the 09/11 report (« Les chiffres » from T0, the
restore_time in two numbers, « La chronologie », the Run Commands), and the same in JSON —
runs/bench/<run_id>.json, or OUT= (the Markdown beside it, .md) —, ready to feed docs/proofs.json
later (not yet). The identifiers are masked by construction: a caller becomes its role, a resource
the bench's public name; every line also goes through bench_shared.scrub.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE.parent), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bench_shared as bs  # noqa: E402

FORMAT = 1
DEFAULT_TARGET = "vm-celebrimbor-gondolin"
# How far before T0 the activity log and the vault are read: the clean point of the step 2, the
# preparations of Orodruin.
BEFORE_T0_S = 3 * 3600
TERMINAL = ("succeeded", "failed", "canceled")
# The isolation, once Imladris's state is gone: Imladris puts the quarantine NSG on each of the target's NICs.
NIC_WRITE = "microsoft.network/networkinterfaces/write"
# What one activity-log read returns at most: a read that reaches it may be cut, and says so.
MAX_EVENTS = 5000
START_OP = "microsoft.compute/virtualmachines/start/action"
DEALLOCATE_OP = "microsoft.compute/virtualmachines/deallocate/action"
# The attack's Run Command: Orodruin's, submitted within this of T0 (09/11: one second after).
ATTACK_WINDOW_S = (-5.0, 30.0)
# The start after a restore held by the quarantine: the lift within this of its end (09/11: 16 s).
HELD_MARGIN_S = 120.0
# BNC3a: what the workstation waits for before composing, in reading, bounded — the run's cycle after
# Orodruin's exit (12/11: written 5 min 15 s after it, the session drain waits 300 s at most), the lift
# after the restore (30 min: the decision of 12/11; measured then, 5 min 45 s after the start, the
# recovery's grace of 5 min); Imladris read again every POLL_S.
CYCLE_WAIT_S = 600.0
LIFT_WAIT_S = 1800.0
POLL_S = 30.0


def _name(rid) -> str:
    return str(rid or "").rstrip("/").rsplit("/", 1)[-1].lower()


def operations(events: list[dict], roles: bs.Roles) -> list[dict]:
    """The activity log's events, one operation each (its correlation id, its operation, its
    resource): {"op", "resource" (the name), "start", "end", "status", "sub", "role"}, oldest
    first. The end is the terminal event's time (Succeeded, Failed, Canceled), None while none."""
    groups: dict[tuple, list[dict]] = {}
    for e in events:
        op = str((e.get("operationName") or {}).get("value") or "").lower()
        key = (str(e.get("correlationId") or id(e)), op, str(e.get("resourceId") or "").rstrip("/").lower())
        groups.setdefault(key, []).append(e)
    out = []
    for (_, op, rid), evs in groups.items():
        evs = sorted(evs, key=lambda x: bs.epoch(x.get("eventTimestamp")) or 0.0)
        times = [bs.epoch(x.get("eventTimestamp")) for x in evs]
        terminal = [(t, x) for t, x in zip(times, evs)
                    if str((x.get("status") or {}).get("value") or "").lower() in TERMINAL and t is not None]
        last = terminal[-1][1] if terminal else evs[-1]
        role = next((r for r in (roles.of(x) for x in evs) if r != "unknown"), "unknown")
        out.append({"op": op, "resource": _name(rid), "start": times[0], "end": terminal[-1][0] if terminal else None,
                    "status": str((last.get("status") or {}).get("value") or ""),
                    "sub": str((last.get("subStatus") or {}).get("value") or ""), "role": role})
    return sorted((o for o in out if o["start"] is not None), key=lambda o: o["start"])


def _jobs(raw: list[dict], vm: str) -> list[dict]:
    out = []
    for j in raw or []:
        p = j.get("properties") or {}
        if str(p.get("entityFriendlyName") or "").lower() != vm:
            continue
        start = bs.epoch(p.get("startTime"))
        if start is None:
            continue
        out.append({"operation": str(p.get("operation") or ""), "status": str(p.get("status") or ""),
                    "start": start, "end": bs.epoch(p.get("endTime"))})
    return sorted(out, key=lambda j: j["start"])


def _agent(view: dict | None) -> dict:
    iv = (view or {}).get("instanceView") or view or {}
    st = ((iv.get("vmAgent") or {}).get("statuses") or [{}])[0] or {}
    power = [str(s.get("code")).split("/", 1)[1] for s in iv.get("statuses") or []
             if str(s.get("code") or "").lower().startswith("powerstate/")]
    return {"status": str(st.get("displayStatus") or ""), "at": bs.epoch(st.get("time")),
            "power": power[0] if power else ""}


def _what(rc: dict, attack: dict | None, neutralization: dict | None) -> str:
    role = rc["role"]
    if rc is attack:
        return "l'attaque"
    if role == "orodruin":
        return ("les préparatifs de l'attaque (mise en place, contrôle d'intégrité)"
                if attack is None or rc["start"] < attack["start"] else "une Run Command d'Orodruin après l'attaque")
    if role == "h0":
        return "la coupure des sessions"
    if rc is neutralization:
        return "la neutralisation"
    if role in ("console", "bot"):
        return "une tentative refusée" if rc["status"].lower() == "failed" else f"une Run Command {'de la console' if role == 'console' else 'du bot'}"
    if role == "human":
        return "une Run Command humaine"
    return "une Run Command d'un appelant inconnu"


def compose(run_id: str, target: str, h0: dict, events: list[dict], jobs: list[dict], view: dict | None,
            roles: bs.Roles, now: datetime, gaps: list[str] | None = None, nics=()) -> dict:
    """The report as data: its figures from T0, its chronology, its Run Commands, its jobs. `nics`:
    the names of the target's NICs, where Imladris's quarantine is put (the isolation, its state gone)."""
    gaps = list(gaps or [])
    run = h0.get("run")
    if not isinstance(run, dict):
        raise RuntimeError(f"le rapport du run {run_id} est absent d'Imladris (runs/glorfindel/{run_id}.json)")
    t0 = bs.epoch(run.get("attack_time"))
    if t0 is None:
        raise RuntimeError("le rapport du run ne donne pas de T0 (attack_time)")
    ops = operations(events, roles)
    on_vm = [o for o in ops if o["resource"] == target]
    rcs = [o for o in on_vm if o["op"] == bs.RUN_COMMAND_OP]
    jobs_vm = _jobs(jobs, target)
    restores = [j for j in jobs_vm if j["operation"].lower() == "restore" and j["start"] >= t0]
    done = [j for j in restores if j["status"].lower() == "completed" and j["end"] is not None]
    final = done[-1] if done else None
    lo, hi = ATTACK_WINDOW_S
    attack = next((r for r in rcs if r["role"] == "orodruin" and t0 + lo <= r["start"] <= t0 + hi), None)
    before = final["start"] if final else float("inf")
    neutral = [r for r in rcs if r["role"] in ("console", "bot") and r["status"].lower() == "succeeded"
               and r["start"] > t0 and r["start"] < before]
    neutralization = neutral[-1] if neutral else None
    for i, r in enumerate(rcs, 1):
        r["n"], r["what"] = i, _what(r, attack, neutralization)
        r["duration_s"] = (r["end"] - r["start"]) if r["end"] is not None else None

    figures: list[dict] = []

    def fig(key, label, at, source, end=None, tenth=False, note=""):
        figures.append({"key": key, "label": label, "at": at, "end": end, "source": source, "tenth": tenth,
                        "since_t0_s": (at - t0) if at is not None and key not in ("neutralization", "restore_job", "restart", "agent") else None,
                        "note": note})

    fig("t0", "T0", t0, "`attack_time`, le rapport du run sur Imladris")
    latency = run.get("detection_latency_s")
    if isinstance(latency, (int, float)) and not isinstance(latency, bool):
        fig("detection", "Détection", t0 + float(latency),
            f"`detection_latency_s`, verdict `{run.get('detection') or '?'}`")
    else:
        gaps.append(f"la détection : verdict `{run.get('detection') or 'unknown'}`, aucune latence dans le rapport")
    st = h0.get("isolation") or None
    isolated = bs.epoch((st or {}).get("isolated_at"))
    if isolated is not None:
        fig("isolation", "Isolement exécuté (NSG de quarantaine posé)", isolated, "`isolated_at`, l'état d'isolation d'Imladris", tenth=True)
    else:
        mine = {str(n).lower() for n in nics}
        net = next((o for o in ops if o["role"] == "h0" and o["op"] == NIC_WRITE and o["resource"] in mine
                    and o["start"] >= t0 and o["status"].lower() == "succeeded"), None)
        if net is not None:
            fig("isolation", "Isolement exécuté (carte réseau de la cible écrite par Imladris)", net["end"],
                "journal d'activité : la première écriture d'Imladris sur une carte réseau de la cible après T0 "
                "(l'état d'Imladris est levé ; une isolation par les seules règles d'un NSG n'y paraît pas)")
        else:
            gaps.append("l'isolement : ni l'état d'Imladris (levé ?) ni une écriture d'Imladris sur une carte réseau de la "
                        "cible au journal d'activité")
    drain = next((r for r in rcs if r["role"] == "h0" and r["start"] >= t0), None)
    drains = [d for d in (bs.epoch(x) for x in (st or {}).get("drains_at") or []) if d is not None and d >= t0 - 60]
    if drains:
        fig("drain_asked", "Coupure des sessions demandée", drains[0], "`drains_at`, l'état d'Imladris", tenth=True)
    elif drain is not None:
        fig("drain_asked", "Coupure des sessions demandée", drain["start"], "journal d'activité : Started")
    if drain is not None and drain["end"] is not None:
        fig("drain_done", f"Coupure {'aboutie' if drain['status'].lower() == 'succeeded' else drain['status']} sur Azure",
            drain["end"], f"journal d'activité : {drain['status']}, {bs.duration(drain['end'] - drain['start'])} après sa soumission")
    cycle = next((c for c in h0.get("cycles") or [] if c.get("kind") == "run" and c.get("action") == "isolate_vm"), None)
    if cycle is not None:
        o = cycle.get("outcome") or {}
        at = bs.epoch(o.get("verified_at")) or bs.epoch(cycle.get("timestamp"))
        verdict = "vraie" if o.get("verified") is True else "**fausse**" if o.get("verified") is False else "non dite"
        fig("verified", f"Vérification relue, {verdict}", at,
            f"le cycle `isolate_vm`, `verified={o.get('verified')}`, `action_s` = {o.get('action_s', '?')}", tenth=True)
    else:
        mine = [c for c in h0.get("cycles") or [] if c.get("kind") == "run"]
        if mine:
            chose = ", ".join(sorted({f"`{c.get('action') or 'aucune action'}`" for c in mine}))
            gaps.append(f"aucun cycle `isolate_vm` de ce run sur Imladris (la watch a écrit {chose}) : une action "
                        "retenue, ou une recommandation")
        elif _detected(run):
            # BNC3a: composed before the watch closed its cycle (12/11: 7 s after the detection) — said so,
            # never taken for an action held back.
            gaps.append("le cycle de ce run n'est pas encore écrit sur Imladris : la watch l'écrit une fois "
                        "l'action vérifiée, la coupure des sessions comprise — "
                        f"`make bench-report RUN={run_id}` le relira")
        else:
            gaps.append("aucun cycle de ce run sur Imladris : aucune détection")
    if neutralization is not None:
        fig("neutralization", f"Neutralisation ({bs.ROLE_NAMES[neutralization['role']]})", neutralization["start"],
            f"journal d'activité, {neutralization['status']}, {bs.duration(neutralization['duration_s'])}",
            end=neutralization["end"])
    elif final is not None:
        gaps.append("aucune neutralisation réussie avant le restore au journal d'activité")
    for j in restores:
        if j is not final:
            continue
        fig("restore_job", "Job de restore", j["start"], f"le coffre : `{j['status']}`, **{bs.duration(j['end'] - j['start'])}**",
            end=j["end"])
    if not restores:
        gaps.append("aucun job de restore de la cible après T0 dans le coffre")
    restart = next((o for o in on_vm if o["op"] == START_OP and o["start"] >= (final or {"start": t0})["start"]), None)
    if restart is not None:
        fig("restart", "Démarrage après restore", restart["start"], f"journal d'activité (`start/action`), {restart['status'] or '?'}",
            end=restart["end"])
    lift, lift_source = None, ""
    if h0.get("lifts"):
        x = h0["lifts"][0]
        lift, lift_source = bs.epoch(x.get("timestamp")), f"`manual_actions.jsonl` d'Imladris ({x.get('hand')}), `{x.get('status')}`"
    else:
        rec = next((c for c in h0.get("cycles") or [] if c.get("kind") == "recovery" and c.get("action") == "release_isolation"), None)
        if rec is not None:
            o = rec.get("outcome") or {}
            lift = bs.epoch(o.get("verified_at")) or bs.epoch(rec.get("timestamp"))
            lift_source = f"le cycle `recovery_complete` de la watch (REC1), `verified={o.get('verified')}`"
    if lift is not None:
        fig("lift", "Levée (service rendu)", lift, lift_source)
    else:
        held = h0.get("holds") or []
        if held:
            x = held[-1]
            gaps.append("la levée retenue par la reprise de la watch (une carte `release_hold`, "
                        f"`{x.get('kind') or '?'}`, {bs.hms(bs.epoch(x.get('timestamp')))}) : aucune levée")
        else:
            gaps.append("aucune levée de la cible après T0 sur Imladris (manual_actions.jsonl, ni un cycle "
                        "recovery_complete)")
    agent = _agent(view)
    if agent["status"]:
        fig("agent", f"Agent invité `{agent['status']}`", agent["at"], f"la vue d'instance, relue en composant ({agent['power'] or '?'})")
    else:
        gaps.append("la vue d'instance : aucun statut de l'agent invité")

    restore_time = None
    if final is not None:
        job_s = final["end"] - final["start"]
        start_s = (restart["end"] - restart["start"]) if restart is not None and restart["end"] is not None else None
        held = (restart is not None and lift is not None and restart["start"] <= lift
                and (restart["end"] is None or lift <= restart["end"] + HELD_MARGIN_S))
        restore_time = {"job_s": job_s, "start_s": start_s, "held_by_quarantine": bool(held)}

    timeline: list[dict] = []

    def at(t, what, end=None):
        if t is not None:
            timeline.append({"at": t, "end": end, "what": what})

    backups = [j for j in jobs_vm if j["operation"].lower() == "backup" and j["start"] < t0
               and j["status"].lower() == "completed"]
    if backups:
        b = backups[-1]
        at(b["start"], "point de restauration pris (job de sauvegarde)", b["end"])
    for f in figures:
        if f["key"] in ("drain_done",):
            continue
        if f["key"] == "drain_asked" and drain is not None:
            at(drain["start"], f"coupure des sessions par Imladris ({bs.duration(drain['duration_s'])}, {drain['status']})", drain["end"])
            continue
        label = {"t0": "**T0**, l'attaque", "lift": "**levée**"}.get(f["key"], f["label"][0].lower() + f["label"][1:])
        at(f["at"], label, f["end"])
    for r in rcs:
        if r is not drain and r is not neutralization and r["start"] is not None and r["role"] != "h0":
            at(r["start"], f"Run Command, {bs.ROLE_NAMES[r['role']]} : {r['what']} ({r['status']})", r["end"])
    for o in on_vm:
        if o["op"] == DEALLOCATE_OP:
            at(o["start"], f"désallocation de {target} ({o['status']})", o["end"])
    for j in restores:
        if j is not final:
            at(j["start"], f"job de restore {j['status']} ({bs.duration((j['end'] or j['start']) - j['start'])})", j["end"])
    timeline.sort(key=lambda x: x["at"])
    return {"format": FORMAT, "run_id": run_id, "request": str(run.get("request") or ""),
            "target": target, "technique": str(run.get("mitre") or ""), "scenario": str(run.get("scenario") or ""),
            "result": str(run.get("result") or ""), "composed_at": now.isoformat(), "t0": bs.iso(t0),
            "figures": [{**f, "at": bs.iso(f["at"]), "end": bs.iso(f["end"]) if f["end"] is not None else ""} for f in figures],
            "restore_time": restore_time,
            "timeline": [{"at": bs.iso(x["at"]), "end": bs.iso(x["end"]) if x["end"] is not None else "", "what": x["what"]}
                         for x in timeline],
            "run_commands": [{"n": r["n"], "caller": r["role"], "start": bs.iso(r["start"]),
                              "end": bs.iso(r["end"]) if r["end"] is not None else "", "status": r["status"],
                              "sub_status": r["sub"], "duration_s": r["duration_s"], "what": r["what"]} for r in rcs],
            "jobs": [{"operation": j["operation"], "status": j["status"], "start": bs.iso(j["start"]),
                      "end": bs.iso(j["end"]) if j["end"] is not None else "",
                      "duration_s": (j["end"] - j["start"]) if j["end"] is not None else None} for j in jobs_vm],
            "agent": {"status": agent["status"], "at": bs.iso(agent["at"]), "power": agent["power"]},
            "gaps": gaps}


def _span(a: str, b: str, tenth: bool = False) -> str:
    ta, tb = bs.epoch(a), bs.epoch(b)
    return f"{bs.hms(ta, tenth)} → {bs.hms(tb, tenth)}" if tb is not None else bs.hms(ta, tenth)


def markdown(doc: dict) -> str:
    """The report, in the form of the 09/11 one."""
    out = [f"# Rapport du banc — {doc['target']}, run `{doc['run_id']}`", "",
           "> Composé par `make bench-report` (BNC1) : lu sur Imladris, au journal d'activité, au coffre et à la vue",
           "> d'instance, sans rien écrire. Aucun identifiant ici : un appelant est un rôle. Heures en UTC.", "",
           "| Identifiant | Valeur |", "|---|---|",
           f"| Demande Dagorlad | {'`' + doc['request'] + '`' if doc['request'] else 'aucune (le run ne porte pas de demande)'} |",
           f"| `run_id` | `{doc['run_id']}` |",
           f"| Technique | {doc['technique'] or '?'} ({doc['scenario'] or '?'}), résultat `{doc['result'] or '?'}` |",
           f"| Composé le | {doc['composed_at'][:19].replace('T', ' ')} |", "",
           "## Les chiffres", "", f"T0 = **{bs.hms(bs.epoch(doc['t0']))}** (`attack_time` du run).", "",
           "| Chiffre | Heure | Depuis T0 | Source |", "|---|---|---|---|"]
    for f in doc["figures"]:
        hour = _span(f["at"], f["end"], f["tenth"]) if f["end"] else bs.hms(bs.epoch(f["at"]), f["tenth"])
        since = bs.since_t0(f["since_t0_s"]) if f["since_t0_s"] is not None else "—"
        if f["key"] in ("detection", "isolation", "lift") and f["since_t0_s"] is not None:
            since = f"**{since}**"
        out.append(f"| {f['label']} | {hour} | {since} | {f['source']} |")
    rt = doc.get("restore_time")
    if rt:
        out += ["", "**Le `restore_time` s'écrit en deux nombres, chacun avec sa cause** :",
                f"- le job : **{bs.duration(rt['job_s'])}** ;"]
        if rt.get("start_s") is not None:
            held = ", retenu par la quarantaine jusqu'à la levée" if rt["held_by_quarantine"] else ""
            out.append(f"- le démarrage : **{bs.duration(rt['start_s'])}**{held}.")
        else:
            out.append("- le démarrage : sa fin ne se lit pas au journal d'activité.")
    out += ["", "## La chronologie", "", "| Heure | Ce qui se passe |", "|---|---|"]
    for x in doc["timeline"]:
        out.append(f"| {_span(x['at'], x['end'])} | {x['what']} |")
    out += ["", "## Les Run Command de la cible", "", "| # | Appelant | Début → fin | Statut | Durée | Ce que c'est |",
            "|---|---|---|---|---|---|"]
    for r in doc["run_commands"]:
        status = r["status"] + (f" (`{r['sub_status']}`)" if r["sub_status"] else "")
        out.append(f"| {r['n']} | {bs.ROLE_NAMES.get(r['caller'], r['caller'])} | {_span(r['start'], r['end'])} | {status} "
                   f"| {bs.duration(r['duration_s'])} | {r['what']} |")
    if not doc["run_commands"]:
        out.append("| — | — | — | — | — | aucune Run Command lue sur la cible |")
    out += ["", "## Les jobs du coffre", "", "| Opération | Début → fin | Statut | Durée |", "|---|---|---|---|"]
    for j in doc["jobs"]:
        out.append(f"| {j['operation']} | {_span(j['start'], j['end'])} | {j['status']} | {bs.duration(j['duration_s'])} |")
    if not doc["jobs"]:
        out.append("| — | — | — | aucun job lu |")
    if doc["gaps"]:
        out += ["", "## Ce qui n'a pas pu être lu", ""] + [f"- {g}" for g in doc["gaps"]]
    return "\n".join(bs.scrub(x) for x in out) + "\n"


def scrubbed(doc):
    """The JSON's every string through scrub — by construction, as the Markdown."""
    if isinstance(doc, dict):
        return {k: scrubbed(v) for k, v in doc.items()}
    if isinstance(doc, list):
        return [scrubbed(v) for v in doc]
    return bs.scrub(doc) if isinstance(doc, str) else doc


# ── the reads ─────────────────────────────────────────────────────────────────

def job_end_date(now: datetime) -> str:
    """`az backup job list --end-date`: the day after today. A day's bound leaves that day out —
    measured on 12/11 (BNC3a): with today's date, only the jobs of the day before came out, and the
    report took yesterday's night backup for the clean point of the morning."""
    return (now.astimezone(timezone.utc) + timedelta(days=1)).strftime("%d-%m-%Y")


def _detected(run: dict) -> bool:
    latency = run.get("detection_latency_s")
    return isinstance(latency, (int, float)) and not isinstance(latency, bool)


def cycle_written(h0: dict) -> bool:
    """What `make bench-run` waits for (BNC3a): the run's report on Imladris, and its cycle — the watch
    writes it once the action is verified, the session drain included (12/11: 5 min 22 s after the
    detection, the report composed 7 s after it saw neither). No detection: no cycle will come."""
    run = h0.get("run")
    if not isinstance(run, dict):
        return False
    return not _detected(run) or any(c.get("kind") == "run" for c in h0.get("cycles") or [])


def lift_seen(h0: dict) -> bool:
    """What `make bench-restore` waits for (BNC3a): the lift — by the console or the bot, the watch's
    own `recovery_complete` (REC1) —, or the lift held by the watch's recovery (a `release_hold` card,
    but `stopped`: the watch reads again, and releases once the VM runs)."""
    if not isinstance(h0.get("run"), dict):
        return True                                 # nothing to follow: composing says it
    return (bool(h0.get("lifts")) or any(c.get("kind") == "recovery" for c in h0.get("cycles") or [])
            or any(h.get("kind") != "stopped" for h in h0.get("holds") or []))


# What each wait follows, its bound, and what it is said to be.
WAITS = {"cycle": (cycle_written, CYCLE_WAIT_S, "le cycle du run"),
         "lift": (lift_seen, LIFT_WAIT_S, "la levée de la cible")}


def await_h0(read, ready, max_s: float, what: str, *, poll_s: float = POLL_S, sleep=time.sleep,
             clock=time.monotonic, say=None) -> tuple[dict, list[str]]:
    """Imladris read again, every poll_s, until ready(its view) or max_s — in reading only, bounded.
    (The last view read, what the wait left unsaid). The first read's failure is the caller's; a later
    one is counted, and the view before it kept. Ctrl-C ends the wait, never the report."""
    say = say or (lambda s: print(s, file=sys.stderr))
    start = clock()
    h0 = read()
    if ready(h0):
        return h0, []
    say(f"… {what} n'est pas encore écrit sur Imladris : relu toutes les {int(poll_s)} s, "
        f"{int(max_s // 60)} min au plus, puis le rapport se compose (Ctrl-C : tout de suite)")
    failed, ended = 0, "bound"
    while True:
        left = max_s - (clock() - start)
        if left <= 0:
            break
        try:
            sleep(min(poll_s, left))
            h0 = read()
        except KeyboardInterrupt:
            ended = "interrupted"
            break
        except RuntimeError:
            failed += 1
            continue
        if ready(h0):
            ended = "ready"
            break
    waited = bs.duration(clock() - start)
    if ended == "ready":
        say(f"✓ {what} lu après {waited}")
        return h0, []
    why = "attente interrompue" if ended == "interrupted" else f"attendu {waited}, la borne"
    more = f", {failed} relecture(s) d'Imladris échouée(s)" if failed else ""
    return h0, [f"{what} : pas encore écrit sur Imladris ({why}{more}) — `make bench-report RUN=<run_id>` "
                "le relira plus tard"]


def gather(run_id: str, target: str, env: dict, config: str, now, wait: str = "", *, sleep=time.sleep,
           clock=time.monotonic) -> tuple[dict, list, list, dict | None, list, list, datetime]:
    """(Imladris's view, the activity log's events, the vault's jobs, the instance view, what failed, the
    target's NICs, when it was composed). Imladris is read only once its host key is verified: else
    nothing is sent. `wait` (BNC3a): `cycle` or `lift`, Imladris read again until it is written, bounded
    (WAITS); Azure is read after the wait, up to its end. `now`: a datetime, or what gives one."""
    gaps: list[str] = []
    known = bs.run(["make", "-s", "--no-print-directory", "imladris-known"], timeout=60)
    if not known.ok:
        raise RuntimeError("la clé d'hôte d'Imladris n'est pas vérifiée par son empreinte (HOST_SSH_FINGERPRINT, "
                           f"make imladris-known : {known.first_error()}) : rien n'est envoyé")

    def read() -> dict:
        return bs.read_h0("report", target, run_id, env=env)
    if wait:
        ready, max_s, what = WAITS[wait]
        h0, unsaid = await_h0(read, ready, max_s, what, sleep=sleep, clock=clock)
        gaps += [u.replace("<run_id>", run_id) for u in unsaid]
    else:
        h0 = read()
    now = now() if callable(now) else now
    t0 = bs.epoch((h0.get("run") or {}).get("attack_time"))
    if t0 is None:
        return h0, [], [], None, gaps, [], now
    hits = bs.locate_vm(target)
    if len(hits) != 1:
        gaps.append(f"{len(hits)} VM nommée(s) {target} : le journal d'activité, le coffre et la vue d'instance ne sont pas lus")
        return h0, [], [], None, gaps, [], now
    rg, vm_id = hits[0]["rg"], hits[0]["id"]
    start = datetime.fromtimestamp(t0 - BEFORE_T0_S, timezone.utc)
    nic_ids: list = []
    try:
        nic_ids = [str(n) for n in bs.az_json(["vm", "show", "--ids", vm_id, "--query",
                                               "networkProfile.networkInterfaces[].id"]) or []]
    except RuntimeError as e:
        gaps.append(f"les cartes réseau de la cible : illisibles ({e})")
    # The target's own resources, each read apart (the VM, its NICs): never the whole group.
    events: list = []
    for rid in [vm_id, *nic_ids]:
        try:
            got = bs.az_json(["monitor", "activity-log", "list", "--resource-id", rid,
                              "--start-time", start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                              "--end-time", now.strftime("%Y-%m-%dT%H:%M:%SZ"), "--max-events", str(MAX_EVENTS)],
                             timeout=300) or []
        except RuntimeError as e:
            gaps.append(f"le journal d'activité de {_name(rid)} : illisible ({e})")
            continue
        if len(got) >= MAX_EVENTS:
            gaps.append(f"le journal d'activité de {_name(rid)} : {MAX_EVENTS} événements lus, le plafond — la suite "
                        "n'est pas lue, la chronologie peut être coupée")
        events += got
    jobs: list = []
    try:
        vault, vault_rg, _ = bs.local_vault(config)
    except Exception as e:  # noqa: BLE001 — its message may repeat the file's values: only its type
        vault, vault_rg = "", ""
        gaps.append(f"la configuration du poste : illisible ({type(e).__name__}) — les jobs du coffre ne sont pas lus")
    if vault:
        try:
            jobs = bs.az_json(["backup", "job", "list", "-g", vault_rg or rg, "-v", vault,
                               "--start-date", (start - timedelta(days=1)).strftime("%d-%m-%Y"),
                               "--end-date", job_end_date(now)]) or []
        except RuntimeError as e:
            gaps.append(f"les jobs du coffre : illisibles ({e})")
    elif not any(g.startswith("la configuration du poste") for g in gaps):
        gaps.append("les jobs du coffre : aucun coffre dans la configuration du poste")
    view = None
    try:
        view = bs.az_json(["vm", "get-instance-view", "-g", rg, "-n", target])
    except RuntimeError as e:
        gaps.append(f"la vue d'instance : illisible ({e})")
    return h0, events, jobs, view, gaps, [_name(n) for n in nic_ids], now


def main(argv: list[str] | None = None, env: dict | None = None, now: datetime | None = None, *,
         sleep=time.sleep, clock=time.monotonic) -> int:
    env = dict(os.environ) if env is None else env
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--run", default=env.get("BENCH_RUN") or "")
    p.add_argument("--target", default=env.get("BENCH_TARGET") or DEFAULT_TARGET)
    p.add_argument("--out", default=env.get("BENCH_OUT") or "")
    p.add_argument("--config", default=str(bs.REPO / "glorfindel-config.yaml"))
    p.add_argument("--wait", choices=sorted(WAITS), default="",
                   help="BNC3a: Imladris read again until the run's cycle (cycle) or the lift (lift), bounded")
    args = p.parse_args(argv)
    run_id, target = args.run.strip(), args.target.strip().lower()
    if not bs.RUN_ID.fullmatch(run_id):
        print("RUN=<run_id> exigé : celui que donne Orodruin (« Run: … »)", file=sys.stderr)
        return 2
    if not bs.VM_NAME.fullmatch(target):
        print("TARGET invalide : le nom d'une VM du banc", file=sys.stderr)
        return 2
    try:
        h0, events, jobs, view, gaps, nics, now = gather(
            run_id, target, env, args.config, now or (lambda: datetime.now(timezone.utc)), args.wait,
            sleep=sleep, clock=clock)
        doc = scrubbed(compose(run_id, target, h0, events, jobs, view, bs.Roles.from_environment(env), now, gaps,
                               nics=nics))
        text = markdown(doc)
    except RuntimeError as e:
        print(f"✗ {bs.scrub(str(e))}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 — never a Python trace, never an unmasked word
        print(f"✗ le rapport n'a pas pu être composé ({type(e).__name__}: {bs.scrub(str(e))[:300]})", file=sys.stderr)
        return 1
    # The JSON and the Markdown side by side, never one over the other (OUT=x.md included).
    base = Path(args.out) if args.out else bs.REPO / "runs" / "bench" / f"{run_id}.json"
    out, md = base.with_suffix(".json"), base.with_suffix(".md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md.write_text(text, encoding="utf-8")
    print(text)
    print(f"→ {out} et {md.name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
