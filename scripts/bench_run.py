#!/usr/bin/env python3
"""bench_run — a bench run in one command: `make bench-run TARGET=<vm> SCENARIO=<id> [DRY_RUN=1]` (MOB1, #686).

The operator types it on his workstation — at its keyboard, or from his phone through the private
network and the workstation's SSH server (docs/demarrer/mobile.md). Only the path between the phone
and the workstation is new: Orodruin still listens to the workstation's SSH alone (DRL1), and nothing
is installed on Imladris. In order, each step stopping the next one:

  0  the guard     never in a code session (EREGION_AGENT_SESSION, a lot's worktree): a session never
                   launches an attack (bench_shared.session_refusal, the rule of bench_reader.py); and a
                   terminal on stdin, or nothing is sent and nothing is run (the sub-make has already read
                   the local Terraform state, Imladris's and Orodruin's addresses: the threat model's frontier 9):
                   a name « typed » through a pipe is no name typed
  1  the preflight `make bench-preflight` (scripts/bench_preflight.py, BNC1): one ✗ and nothing is
                   asked, nothing is sent
  2  the request   one wire, SCENARIO (a catalogue id) on TARGET, the VM's id read from Azure under the
                   operator's `az login` (one VM of that name, never two) — a request as Dagorlad
                   writes one (eregion_core/exercise_request.new), read back by its one reader
  3  the name      the request shown, then the target's name typed here, destructive or not, and
                   compared to the name Azure gives; then « [o/N] ». Another name, or nothing: nothing
                   is sent
  4  the point     BNC3b (#770), after the confirmation: the newest recovery point of the target, the one
                   the restore will take, kept when clean — taken after the VM's last restore and outside
                   every quarantine, over every run (scripts/bench_snapshot.py, scripts/bench_history.py);
                   otherwise a new one, by the route of the console's 📸 button (a short port forward to
                   Imladris, the console's token by the environment, its receipt under FS1, the vault's job
                   followed to `Completed`, 60 min at most) — any refusal stops the run before Orodruin —,
                   then the preflight replayed, just before the attack: a ✗, and nothing is sent
  5  the launch    the request and the name typed carried to Orodruin by its pinned SSH (the
                   preflight ran `orodruin-known`), then run there by `eregion_core.exercise_runner`,
                   which judges it again (contract, watch, enrollment, zone, the name typed against
                   the name it reads, its cap) — what `make orodruin-exercise` does; the name typed is
                   removed from Orodruin at the end, whatever the end
  6  the report    `make bench-report RUN=<run_id>` for each run Orodruin's output names (« Run: … »),
                   once the run's cycle is written on Imladris — read again, 10 min at most, then
                   composed anyway, saying what is not yet written (BNC3a: on 12/11 the report
                   composed 7 s after the detection saw neither the isolation nor its cycle)

DRY_RUN=1: 0 to 3, the point read (4), then what would follow — no point taken, nothing sent, nothing run.
Nothing is written, on Azure nor on Imladris, before the confirmation (3).
A terminal holds the gesture against a mistake, not against a process of the same user that drives
one (a long-lived tmux session, `tmux send-keys`: docs/demarrer/mobile.md, the threat model's frontier 9).
TARGET, SCENARIO and DRY_RUN reach the script through the environment, never expanded by make, and
are checked here; the ssh command of Orodruin and its container's too (BENCH_ORO_SSH,
BENCH_ORO_RUN_REQUEST), never printed; the console's token too (BENCH_CONSOLE_TOKEN, BNC3b), never in an
argv. Errors are said in a sentence; exit 0 only when the request
ran whole and its report was composed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE.parent), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bench_shared as bs  # noqa: E402
from eregion_core import exercise_request as xr  # noqa: E402

# What the injectors print once a run is written (annatar/runner/report.py): its id.
RUN_LINE = re.compile(r"^\s*Run:\s+([A-Za-z0-9][A-Za-z0-9_.-]{0,95})\s*$")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
YES = ("o", "oui", "y", "yes")


class Steps:
    """The outside steps, each a parameter: the tests run the command on fakes."""

    def __init__(self, env: dict):
        self.env = env

    def preflight(self, target: str) -> int:
        import bench_preflight
        return bench_preflight.main(["--target", target], self.env)

    def locate(self, target: str) -> list[dict]:
        return bs.locate_vm(target)

    def catalog(self) -> dict:
        from eregion_core.exercise_plan import load_catalog
        return load_catalog()

    def launch(self, folder: Path, rid: str, say) -> tuple[int, list[str]]:
        """The request carried to Orodruin and run there; (its exit code, the run ids it printed)."""
        base = bs.ssh_argv("BENCH_ORO_SSH", self.env)
        prefix = (self.env.get("BENCH_ORO_RUN_REQUEST") or "").strip()
        if not base or not prefix:
            raise RuntimeError("BENCH_ORO_SSH ou BENCH_ORO_RUN_REQUEST vide : lancer par make bench-run")
        if not bs.host_key_pinned(base):
            raise RuntimeError("la clé d'hôte d'Orodruin n'est pas vérifiée par son empreinte "
                               "(ORO_SSH_FINGERPRINT, make orodruin-known) : rien n'est envoyé")
        made = bs.run([*base[:-1], base[-1], "mkdir -p requests && chmod 700 requests"], timeout=60)
        if not made.ok:
            raise RuntimeError(f"Orodruin ne répond pas par ssh ({made.first_error()}) : rien n'est envoyé")
        sent = bs.run(["scp", "-q", *base[1:-1], str(folder / f"{rid}.json"), str(folder / f"{rid}.typed.json"),
                       f"{base[-1]}:requests/"], timeout=120)
        if not sent.ok:
            raise RuntimeError(f"la demande n'a pas été copiée sur Orodruin ({sent.first_error()}) : rien n'est lancé")
        command = (f"trap 'rm -f requests/{rid}.typed.json' EXIT HUP INT TERM; "
                   f"{prefix} python -m eregion_core.exercise_runner /app/requests/{rid}.json")
        runs: list[str] = []
        proc = subprocess.Popen([*base[:-1], "-o", "ServerAliveInterval=60", base[-1], command],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=bs.REPO)
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            say(line)
            got = RUN_LINE.match(ANSI.sub("", line))
            if got and got.group(1) not in runs:
                runs.append(got.group(1))
        return proc.wait(), runs

    def point(self, target: str) -> dict:
        """BNC3b: the newest point of the target, judged (bench_snapshot.judge)."""
        import bench_snapshot
        return bench_snapshot.judge(target, self.env, str(bs.REPO / "glorfindel-config.yaml"))

    def snapshot(self, target: str, plan: dict, say) -> float:
        """BNC3b: a new point by the 📸 route, its job followed to Completed (bench_snapshot.take)."""
        import bench_snapshot
        return bench_snapshot.take(target, self.env, plan, say)

    def report(self, run_id: str, target: str) -> int:
        """The run's report, once its cycle is written on Imladris (bounded: bench_report.CYCLE_WAIT_S)."""
        import bench_report
        return bench_report.main(["--run", run_id, "--target", target, "--wait", "cycle"], self.env)


def confirm(request: xr.Request, catalog: dict, ask, say) -> dict | None:
    """The request shown, its target's name typed — always, destructive or not —, then « [o/N] ».
    The names typed (``read_typed``'s shape), or None: nothing is sent."""
    (wire,) = request.wires
    e = catalog.get(wire.experiment)
    what = f"{e.kind} {e.id} {e.name}" if e else wire.experiment
    flag = "  ← DESTRUCTIVE" if e is not None and e.destructive else ""
    say(f"Demande {xr.shown(request.id)} — un fil : {xr.shown(what)} → {xr.shown(wire.target_name)} "
        f"(groupe {xr.shown(wire.target.split('/')[4])}){flag}")
    try:
        got = ask("Tape le nom de la VM cible pour lancer : ").strip()
    except EOFError:
        got = ""
    if not got:
        say("✗ aucun nom tapé : rien n'est envoyé.")
        return None
    if got != wire.target_name:
        say(f"✗ « {xr.shown(got)} » n'est pas la cible : rien n'est envoyé.")
        return None
    try:
        answer = ask("Lancer ce fil depuis Orodruin ? [o/N] ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in YES:
        say("Rien n'est envoyé.")
        return None
    return {"request": request.id, "typed": {str(wire.rank): got}}


def _write(path: Path, doc: dict) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(doc, f)


def main(argv: list[str] | None = None, env: dict | None = None, *, cwd=None, here=None,
         ask=input, say=print, steps: Steps | None = None, tty: bool | None = None) -> int:
    env = dict(os.environ) if env is None else env
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--target", default=env.get("BENCH_TARGET") or "")
    p.add_argument("--scenario", default=env.get("BENCH_SCENARIO") or "")
    p.add_argument("--dry-run", action="store_true", default=(env.get("BENCH_DRY_RUN") or "") == "1")
    p.add_argument("--guard-only", action="store_true",
                   help="the guard alone: make runs it before anything else is expanded")
    args = p.parse_args(argv)

    refusal = bs.session_refusal(env, cwd, here)
    if refusal:
        say(f"✗ make bench-run refusé : {refusal}. Rien n'est envoyé, rien n'est lancé.")
        return 1
    if args.guard_only:
        return 0
    if not (sys.stdin.isatty() if tty is None else tty):
        say("✗ pas de terminal : le nom de la cible se tape au clavier, jamais par un tube. Rien n'est "
            "envoyé, rien n'est lancé.")
        return 1
    target, scenario = args.target.strip().lower(), args.scenario.strip()
    if not bs.VM_NAME.fullmatch(target):
        say("✗ TARGET=<vm> exigé : le nom d'une VM du banc (make bench-run TARGET=<vm> SCENARIO=<id>)")
        return 2
    if (env.get("BENCH_DRY_RUN") or "") not in ("", "1"):
        say("✗ DRY_RUN=1, ou rien")
        return 2
    steps = steps or Steps(env)
    catalog = steps.catalog()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", scenario) or scenario not in catalog:
        say("✗ SCENARIO=<id> exigé : une technique ou une panne du catalogue (technique_catalog.yaml), "
            "comme T1486")
        return 2

    say(f"→ 1/5 le préflight de {target}")
    if steps.preflight(target) != 0:
        say("✗ le préflight est rouge (une ligne ✗ ci-dessus) : rien n'est demandé, rien n'est lancé.")
        return 1
    try:
        hits = steps.locate(target)
    except RuntimeError as e:
        say(f"✗ la cible ne se lit pas sur Azure ({bs.scrub(str(e))}) : rien n'est demandé.")
        return 1
    if len(hits) != 1:
        say(f"✗ {len(hits)} VM nommée(s) {target} : une seule attendue, rien n'est demandé.")
        return 1
    try:
        request = xr.new([(scenario, hits[0]["id"])])
    except xr.RequestRefused as e:
        say(f"✗ la demande ne se forme pas ({e}) : rien n'est envoyé.")
        return 1

    say("→ 2/5 la demande, et le nom de la cible tapé")
    typed = confirm(request, catalog, ask, say)
    if typed is None:
        return 1
    with tempfile.TemporaryDirectory(prefix="bench-run-") as tmp:
        folder = Path(tmp)
        _write(folder / f"{request.id}.json", request.to_dict())
        _write(folder / f"{request.id}.typed.json", typed)
        xr.load_typed(folder / f"{request.id}.typed.json", xr.load(folder / f"{request.id}.json"))
        say("→ 3/5 le point de restauration propre (le plus récent, celui que le restore prendra)")
        try:
            plan = steps.point(target)
        except (RuntimeError, OSError) as e:
            plan = {"clean": False, "said": f"illisible ({bs.scrub(str(e))[:200]})"}
        if plan.get("clean"):
            say(f"✓ le point : gardé — {bs.scrub(plan.get('said') or '')}")
        elif args.dry_run:
            say(f"✗ le point : {bs.scrub(plan.get('said') or 'non propre')} — sans DRY_RUN, un nouveau par la route "
                "du bouton 📸, puis le préflight rejoué.")
        else:
            say(f"✗ le point : {bs.scrub(plan.get('said') or 'non propre')} — un nouveau, par la route du bouton 📸")
            if not plan.get("vault"):
                say("✗ la cible ou son coffre ne se lit pas : aucun point demandé, rien n'est envoyé à Orodruin.")
                return 1
            try:
                steps.snapshot(target, plan, say)
            except (RuntimeError, OSError) as e:
                say(f"✗ le point : {bs.scrub(str(e))} — le run s'arrête, rien n'est envoyé à Orodruin.")
                return 1
            say("✓ le point : pris, son job Completed")
            say(f"→ le préflight rejoué, juste avant l'attaque ({target})")
            if steps.preflight(target) != 0:
                say("✗ le préflight rejoué est rouge (une ligne ✗ ci-dessus) : rien n'est envoyé à Orodruin. "
                    "Le point pris reste : il est propre, et sans danger.")
                return 1
        if args.dry_run:
            say("DRY_RUN : rien n'est envoyé. Sans lui : la demande et le nom tapé copiés sur Orodruin "
                f"(requests/), puis python -m eregion_core.exercise_runner /app/requests/{request.id}.json, "
                "puis make bench-report RUN=<le run>.")
            return 0
        say(f"→ 4/5 le lancement par Orodruin ({request.id})")
        try:
            code, runs = steps.launch(folder, request.id, say)
        except (RuntimeError, OSError) as e:
            say(f"✗ {bs.scrub(str(e))}")
            return 1
    if not runs:
        say(f"✗ aucun run lu dans la sortie d'Orodruin (code {code}) : pas de rapport. La chronologie de "
            "la demande est dans Dagorlad ; make bench-report RUN=<run_id> à la main.")
        return 1
    say("→ 5/5 le rapport, une fois le cycle du run écrit sur Imladris (relu, 10 min au plus)")
    worst = code
    for run_id in runs:
        rc = steps.report(run_id, target)
        worst = worst or rc
    say(f"Ensuite, le restore : make bench-restore TARGET={target} RUN={runs[-1]} (le T0 du run, --keep-isolated).")
    return 0 if worst == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
