#!/usr/bin/env python3
"""bench_restore — the bench's restore from the workstation: `make bench-restore TARGET=<vm> [BEFORE=…] [RUN=…] [DRY_RUN=1]` (MOB1, #686).

Imladris never restores (its identity has no Restore role): the restore leaves from the workstation, under
the console's pair for this one command (docs/banc-t1486.md, step 6; docs/operations.md, « Identités
Azure »). Until FS1g and TOT1, the phone reaches it through the workstation's terminal
(docs/demarrer/mobile.md): the hardware key of the SSH stands as the second factor. In order:

  0  the guard     never in a code session (EREGION_AGENT_SESSION, a lot's worktree); a terminal on
                   stdin, or nothing is read (a name through a pipe is no name typed)
  1  the pair      EREGION_CONSOLE_AZURE_CLIENT_ID and EREGION_CONSOLE_AZURE_CLIENT_SECRET both set
                   (RST1: an empty pair silently takes another identity) — their names said, never
                   their values; the restore runs with AZURE_CLIENT_ID / AZURE_CLIENT_SECRET set to
                   them, and nothing else changed
  2  the moment    BEFORE= wins; else the run's T0 — its attack_started, the rule of SEC4c — as
                   `make bench-report` wrote it in runs/bench/<run_id>.json: RUN= (what `make bench-run`
                   prints), else the one report of TARGET there — two or more, refused, their runs
                   listed: the latest is not the safe way. The restored point is the newest one before
                   it: the clean point of the step 2, never a snapshot taken after the attack. No
                   moment: refused
  3  the target    one VM of that name (az vm list, the operator's az login); the vault and its staging
                   account in the workstation's glorfindel-config.yaml (without the staging account
                   the real restore fails, the dry run does not read it)
  4  the name      the plan shown, the VM's name typed here and compared to Azure's
  5  the dry run   `glorfindel restore <id> --before <moment> --keep-isolated --dry-run`, under the pair
                   (it says its identity, RST1); a failure stops here. DRY_RUN=1 stops here too
  6  the restore   « [o/N] », then the same with `--wait --yes` instead of `--dry-run`. The restore
                   reads its own rights before touching the VM (RST1), neutralizes Run Command (SEC17)
  7  the report    the restore done, `make bench-report RUN=<run_id>` follows the lift by Imladris — in
                   reading, 30 min at most — then composes alone (BNC3a, #753): the run of RUN=, or the
                   one report of TARGET the moment came from; BEFORE= without RUN= names no run, and
                   no report is composed. The restore done and the report not composed: exit 1, said

`--keep-isolated` always: the lift is Imladris's (REC1, REC1b; LEV1 will change the rule), never the
workstation's — a restore without it would release in its own process, under the workstation's
configuration, and Imladris would put the isolation back.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE.parent), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bench_shared as bs  # noqa: E402

PAIR = ("EREGION_CONSOLE_AZURE_CLIENT_ID", "EREGION_CONSOLE_AZURE_CLIENT_SECRET")
YES = ("o", "oui", "y", "yes")
MAX_REPORT_BYTES = 4 * 1024 * 1024


class Steps:
    """The outside steps, each a parameter: the tests run the command on fakes."""

    def __init__(self, env: dict):
        self.env = env

    def locate(self, target: str) -> list[dict]:
        return bs.locate_vm(target)

    def vault(self) -> tuple[str, str, str]:
        return bs.local_vault(str(bs.REPO / "glorfindel-config.yaml"))

    def report(self, run_id: str, target: str) -> int:
        """The run's report, once the lift is read on Imladris (bounded: bench_report.LIFT_WAIT_S),
        under the operator's environment — never the console's pair, which is the restore's alone."""
        import bench_report
        return bench_report.main(["--run", run_id, "--target", target, "--wait", "lift"], self.env)

    def restore(self, argv: list[str], env: dict) -> int:
        """`glorfindel restore …`, its output on the operator's terminal (it is his command)."""
        return subprocess.run([str(bs.REPO / ".venv" / "bin" / "glorfindel"), *argv], env=env,
                              cwd=bs.REPO).returncode


def pair_env(env: dict) -> dict:
    """The environment of the restore: the console's pair as AZURE_CLIENT_ID / AZURE_CLIENT_SECRET,
    writes allowed for this one command (GLORFINDEL_READ_ONLY=0) — nothing else changed."""
    out = dict(env)
    out["AZURE_CLIENT_ID"] = env[PAIR[0]]
    out["AZURE_CLIENT_SECRET"] = env[PAIR[1]]
    out["GLORFINDEL_READ_ONLY"] = "0"
    return out


def restore_argv(resource_id: str, moment: str, *, dry: bool) -> list[str]:
    """Always --before and --keep-isolated: the point before the attack, the lift Imladris's."""
    return ["restore", resource_id, "--before", moment, "--keep-isolated",
            *(["--dry-run"] if dry else ["--wait", "--yes"])]


def _report(path: Path) -> dict | None:
    """A report of runs/bench/, a regular file of ours, bounded — or None."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
            return None
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def run_moment(runs_dir: Path, target: str, run_id: str = "") -> tuple[str, str, str]:
    """(the run's T0 as ISO, its run id, why not) from runs/bench/: RUN=, else the one report of TARGET
    there. ('', '', why) when none says one, or when two or more do: their runs listed, never the
    latest taken for the operator (SEC4c's safe way is the earliest, and the run is his to name)."""
    if run_id:
        doc = _report(runs_dir / f"{run_id}.json")
        if doc is None:
            return "", "", (f"aucun rapport du run {run_id} dans runs/bench/ : make bench-report RUN={run_id} "
                            "d'abord, ou BEFORE=<instant>")
        if str(doc.get("target") or "").lower() != target:
            return "", "", f"le run {run_id} ne visait pas {target} : rien n'est restauré"
        t0 = str(doc.get("t0") or "")
        return (t0, run_id, "") if bs.epoch(t0) is not None else ("", "", f"le rapport du run {run_id} n'a pas de T0")
    found: list[tuple[float, str, str]] = []
    try:
        files = sorted(runs_dir.glob("*.json"))
    except OSError:
        files = []
    for path in files:
        doc = _report(path)
        if not doc or str(doc.get("target") or "").lower() != target:
            continue
        t0 = bs.epoch(doc.get("t0"))
        rid = str(doc.get("run_id") or "")
        if t0 is None or not bs.RUN_ID.fullmatch(rid):
            continue
        found.append((t0, str(doc.get("t0")), rid))
    if not found:
        return "", "", (f"aucun rapport de {target} dans runs/bench/ : make bench-report RUN=<run_id> d'abord, "
                        "ou BEFORE=<instant>")
    if len(found) > 1:
        runs = ", ".join(f"{rid} (T0 {t})" for _, t, rid in sorted(found))
        return "", "", (f"{len(found)} rapports de {target} dans runs/bench/ : RUN=<run_id> pour dire lequel "
                        f"({runs}), ou BEFORE=<instant>. Rien n'est restauré")
    (_, t0_text, rid), = found
    return t0_text, rid, ""


def main(argv: list[str] | None = None, env: dict | None = None, *, cwd=None, here=None, runs_dir=None,
         ask=input, say=print, steps: Steps | None = None, now: float | None = None,
         tty: bool | None = None) -> int:
    env = dict(os.environ) if env is None else env
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--target", default=env.get("BENCH_TARGET") or "")
    p.add_argument("--before", default=env.get("BENCH_BEFORE") or "")
    p.add_argument("--run", default=env.get("BENCH_RUN") or "")
    p.add_argument("--dry-run", action="store_true", default=(env.get("BENCH_DRY_RUN") or "") == "1")
    p.add_argument("--guard-only", action="store_true",
                   help="the guard alone: make runs it before anything else is expanded")
    args = p.parse_args(argv)

    refusal = bs.session_refusal(env, cwd, here)
    if refusal:
        say(f"✗ make bench-restore refusé : {refusal}. Rien n'est lu, rien n'est restauré.")
        return 1
    if args.guard_only:
        return 0
    if not (sys.stdin.isatty() if tty is None else tty):
        say("✗ pas de terminal : le nom de la VM se tape au clavier, jamais par un tube. Rien n'est lu, "
            "rien n'est restauré.")
        return 1
    target, before, run_id = args.target.strip().lower(), args.before.strip(), args.run.strip()
    if not bs.VM_NAME.fullmatch(target):
        say("✗ TARGET=<vm> exigé : le nom de la VM à restaurer (make bench-restore TARGET=<vm> [BEFORE=…])")
        return 2
    if run_id and not bs.RUN_ID.fullmatch(run_id):
        say("✗ RUN invalide : un run_id, celui que donne Orodruin (« Run: … »)")
        return 2
    if (env.get("BENCH_DRY_RUN") or "") not in ("", "1"):
        say("✗ DRY_RUN=1, ou rien")
        return 2
    missing = [n for n in PAIR if not (env.get(n) or "").strip()]
    if missing:
        say(f"✗ la paire de la console manque ({', '.join(missing)} vide) : sans elle, le restore prendrait "
            "une autre identité sans le dire (RST1). .envrc, puis relancer. Rien n'est restauré.")
        return 1

    from glorfindel import restore_plan
    report_run = run_id
    if before:
        source = "BEFORE="
        text = before
    else:
        text, found, why = run_moment(Path(runs_dir) if runs_dir else bs.REPO / "runs" / "bench", target, run_id)
        if why:
            say(f"✗ {why}")
            return 1
        source = f"le T0 du run {found} (son attack_started, runs/bench/{found}.json)"
        report_run = found
    try:
        moment = restore_plan.parse_moment(text, now=now)
    except ValueError as e:
        say(f"✗ le moment ne se lit pas ({e}) : rien n'est restauré.")
        return 1

    steps = steps or Steps(env)
    try:
        hits = steps.locate(target)
    except RuntimeError as e:
        say(f"✗ la cible ne se lit pas sur Azure ({bs.scrub(str(e))}) : rien n'est restauré.")
        return 1
    if len(hits) != 1:
        say(f"✗ {len(hits)} VM nommée(s) {target} : une seule attendue, rien n'est restauré.")
        return 1
    rid = hits[0]["id"]
    name = rid.rstrip("/").rsplit("/", 1)[-1]
    try:
        vault, _, staging = steps.vault()
    except Exception as e:  # noqa: BLE001 — its message may repeat the file's values: only its type
        say(f"✗ la configuration du poste ne se lit pas ({type(e).__name__}) : rien n'est restauré.")
        return 1
    if not vault or not staging:
        say("✗ glorfindel-config.yaml du poste : " + ("aucun coffre" if not vault else "aucun compte de transit "
            "(restore_staging_storage)") + " — make celebrimbor-output en donne le fragment. Rien n'est restauré.")
        return 1

    say(f"Restore de {name} (groupe {hits[0]['rg']}) :")
    say(f"  le point : le plus récent avant {moment} ({source})")
    say("  l'identité : la paire de la console, pour cette seule commande")
    say("  --keep-isolated : la VM reste isolée, la levée est celle d'Imladris")
    try:
        got = ask("Tape le nom de la VM à restaurer : ").strip()
    except EOFError:
        got = ""
    if not got:
        say("✗ aucun nom tapé : rien n'est restauré.")
        return 1
    if got != name:
        say(f"✗ « {got[:80]} » n'est pas la VM : rien n'est restauré.")
        return 1

    restore_env = pair_env(env)
    say("→ à blanc d'abord")
    if steps.restore(restore_argv(rid, moment, dry=True), restore_env) != 0:
        say("✗ l'essai à blanc a échoué (ci-dessus) : rien n'est restauré.")
        return 1
    if args.dry_run:
        say("DRY_RUN : rien n'est restauré.")
        return 0
    try:
        answer = ask(f"Restaurer {name} maintenant (15 à 30 min) ? [o/N] ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in YES:
        say("Rien n'est restauré.")
        return 1
    code = steps.restore(restore_argv(rid, moment, dry=False), restore_env)
    if code != 0:
        return code
    if not report_run:
        say("Ensuite : la levée par Imladris (docs/banc-t1486.md, étape 7), puis make bench-report RUN=<run_id> : "
            "BEFORE= sans RUN= ne nomme aucun run, aucun rapport n'est composé.")
        return 0
    say(f"→ le rapport du run {report_run} : il suit la levée par Imladris, en lecture, 30 min au plus, puis se "
        "compose (Ctrl-C : tout de suite)")
    if steps.report(report_run, target) != 0:
        say(f"✗ le restore a abouti ; le rapport n'a pas pu être composé : make bench-report RUN={report_run}.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
