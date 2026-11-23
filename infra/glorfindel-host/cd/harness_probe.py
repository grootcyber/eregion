#!/usr/bin/env python3
"""harness_probe — the model's probe, once a week on Imladris (HRN2, #1079; infra/glorfindel-host/README.md,
« La sonde du modèle »).

  harness_probe.py run     the timer's pass (systemd, once a week at night): the harness on the model
                           and the key in service, judged against the signed attestation, said
  harness_probe.py check   everything before the paid run, free: what runs, the reference, the harness,
                           the variables (named, never shown), the webhook — said in the terminal only

Why. On 23/11, to a message identical to the byte, the model in service drifted from the attestation of
06/11: on the modest disk write it gave a snapshot at 0.50 and two isolations at 0.65 and 0.55, all held
under the gate; it then isolated 8 times out of 8, 5 of them at 0.7 or more, the draws agreeing —
overconfident errors. The provider can move a model under its name without our code moving; the CD
compares two versions of the code under the same model, the same day, and cannot see it.

A pass:
  1. what runs: the watch's tag and commit (the CD's `deployed`), its image, and from its environment the
     model's variables only (LLM_ENV): the model and the key in service, never another secret;
  2. the reference: requirements/harness.json at that commit, believed only signed by the maintainer's
     key (the CD's `signed_by`, in the probe's own work dir: never the CD's), its pass on the lock in
     service for the model in service, read by the CD's `_passage` — none, nothing is run;
  3. the harness of that commit (scripts/llm_smoke.py, scripts/harness_meter.py) with its ceiling
     (--max-usd MAX_USD: a release whose harness has none, nothing is run — never a run without a bound),
     in a throwaway container of the watch's image: no mount of the watch's state nor of its
     configuration, its scripts read-only, an empty out dir its only writable mount; every case, 3 runs;
     the key passed by its name (`-e NAME`), never on a command line;
  4. judged case by case against the reference, by the CD's own rule (eregion_cd.overconfident_drift: one
     rule, two readers) — a drift says the cases that moved; beside it, what is no drift but worth saying:
     the judgment, the injection, the memory, the calibration, the latency and the cost (HRN1);
  5. the report, ~/.glorfindel/harness-probe/<date>.json (another the same day: <date>-2.json, never one
     overwritten), the last KEEP kept; one line in #deploy by the CD's webhook (the CD's `say`): short
     without a drift; with one, the cases that moved, where to read the report, and Jonathan's mention.

Never: a mode, a rule or a configuration changed; Glorfindel's memory written; the CD or the watch held
(no lock taken, nothing restarted: the watch runs as before, the modes stay Jonathan's decision). Python
3.10 (the VM's), standard library only; installed in ~/.eregion-cd/ beside eregion_cd.py, by
make imladris-cd-install; its timer enabled by make imladris-probe-enable.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import eregion_cd as cd  # noqa: E402  — the CD's rule and its readers, read where they live

# The ceiling of one run, in dollars of measured cost. The run of 23/11 (18 cases, 3 runs) cost about
# 1.15 $: 3 $ leaves the variance of the draws (an isolation draws twice more) and a rise of the price
# room, and bounds a model priced otherwise. An unknown cost is a possible overrun (harness_meter.Budget):
# the run is then bounded by its calls, 162 at most (18 × 3 × 3).
MAX_USD = 3.0
RUNS = 3                # what the CD reads (HARNESS_MIN_RUNS)
KEEP = 26               # reports kept: half a year of weeks
RUN_S = 2 * 3600        # a run cut at two hours (one is about ten minutes)
REPORTS = cd.HOME / ".glorfindel" / "harness-probe"
WORK = cd.CD_HOME / "probe"
HARNESS = ("scripts/llm_smoke.py", "scripts/harness_meter.py")
CONTAINER = "eregion-harness-probe"
# The container beside the watch, on a VM of 4 GB it shares with it: bounded, never more than its user.
# Measured on 23/11, offline (--network none), with the image of the CI and these options: the image's
# user (non-root, Imladris's UID), its out dir written, the harness stopped at its bound (code 3), a peak
# of 335 MiB. systemd's Nice reaches only the docker CLI, never the container: these bound it.
HARDENED = ("--cpus", "1", "--memory", "1g", "--pids-limit", "256", "--security-opt", "no-new-privileges",
            "--cap-drop", "ALL")
# What the watch's container holds of the model (docker-compose.yml, x-env and x-models): its model,
# its endpoint, its bound, and the keys of the providers. Nothing else of its environment is read.
LLM_ENV = ("GLORFINDEL_LLM_MODEL", "GLORFINDEL_LLM_BASE_URL", "GLORFINDEL_LLM_TIMEOUT_S",
           "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "MISTRAL_API_KEY", "AZURE_API_KEY", "AZURE_API_BASE",
           "AZURE_API_VERSION")
REPORT_RE = re.compile(r"(\d{4}-\d{2}-\d{2})(?:-(\d+))?\.json")
SCHEMA = "eregion.harness-probe/1"
SAID = 5                # cases named in #deploy; the others counted


class NoMeasure(Exception):
    """Nothing measured, or nothing to compare: why, said — with the mention when `alert` (a paid run
    that compares nothing)."""

    def __init__(self, text: str, alert: bool = False):
        super().__init__(text)
        self.alert = alert


class Busy(Exception):
    """Another probe holds WORK/.lock: this one erases nothing, runs nothing."""


@contextlib.contextmanager
def alone():
    """One probe at a time (the timer's and one by hand): WORK/.lock, never waited for — taken before
    anything of WORK is touched (the signature's check, the harness, its out dir)."""
    WORK.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open(WORK / ".lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Busy("une sonde tourne déjà : rien n'est effacé ni lancé") from None
        yield


def docker(*args: str, env: dict | None = None, timeout: float = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, **(env or {})})


def show(commit: str, path: str) -> bytes | None:
    return cd._show_bytes(commit, path)


def masked(text: str, env: dict) -> str:
    """What goes to the journal, the value of every key among the model's variables taken out."""
    for value in sorted((v for n, v in env.items() if "KEY" in n), key=len, reverse=True):
        if len(value) >= 6:
            text = text.replace(value, "<masqué>")
    return text


# ── 1. what runs ─────────────────────────────────────────────────────────────────────────────────

def in_service() -> dict:
    """The watch's tag and commit (its image's labels), its image, its model's variables — those only."""
    ref, commit = cd.deployed()
    if not commit:
        raise NoMeasure("ce qui tourne sur Imladris est inconnu (les labels de l'image de la watch)")
    res = docker("inspect", "-f", "{{.Image}} {{json .Config.Env}}", cd.CONTAINERS[0])
    image, _, raw = res.stdout.strip().partition(" ") if res.returncode == 0 else ("", "", "")
    try:
        pairs = json.loads(raw)
    except ValueError:
        pairs = None
    if not image or not isinstance(pairs, list):
        raise NoMeasure("la watch ne se lit pas (docker inspect) : rien n'est lancé")
    env = {}
    for pair in pairs:
        name, _, value = str(pair).partition("=")
        if name in LLM_ENV and value:
            env[name] = value
    model = env.get("GLORFINDEL_LLM_MODEL") or cd.h0_model(commit)
    if not model:
        raise NoMeasure("le modèle en service est inconnu")
    return {"ref": ref, "commit": commit, "image": image, "env": env, "model": model}


# ── 2. the reference ─────────────────────────────────────────────────────────────────────────────

def reference(svc: dict) -> dict:
    """The last signed attestation of the release in service: its pass on the lock in service, for the
    model in service, read by the CD's own reader — or NoMeasure, before any paid call."""
    ref, commit, model = svc["ref"] or svc["commit"][:12], svc["commit"], svc["model"]
    hint = f"make llm-compare MODELS={model} RUNS=3 ATTEST=1, dans la PR du verrou"
    raw, lock = show(commit, cd.ATTESTATION), show(commit, cd.LOCK)
    if raw is None or lock is None:
        raise NoMeasure(f"{ref} n'a pas d'attestation du harnais ({cd.ATTESTATION}) : rien à comparer")
    try:
        cd.signed_by(ref, commit, hint, work=WORK / "harness-check")
    except cd.Refused as e:
        raise NoMeasure(f"l'attestation de {ref} n'est pas crue — {e}") from None
    try:
        att = json.loads(raw)
    except ValueError:
        att = None
    if not isinstance(att, dict) or att.get("schema") != cd.HARNESS_SCHEMA:
        raise NoMeasure(f"l'attestation de {ref} est illisible, ou d'un autre format que {cd.HARNESS_SCHEMA}")
    sha = hashlib.sha256(lock).hexdigest()
    for side in ("candidate", "reference"):
        p = att.get(side)
        if not isinstance(p, dict) or p.get("lock_sha256") != sha:
            continue
        try:
            _entry, cases = cd._passage(p, model, f"de l'attestation ({side})", hint)
        except cd.Refused as e:
            raise NoMeasure(str(e)) from None
        except (TypeError, ValueError, KeyError, AttributeError):
            raise NoMeasure(f"l'attestation de {ref} est mal formée (un champ du mauvais type)") from None
        return {"side": side, "date": str(p.get("date") or att.get("date") or ""), "ref": str(p.get("ref") or ""),
                "lock_sha256": sha, "gate": p.get("gate"), "draws": p.get("draws"), "cases": cases}
    raise NoMeasure(f"l'attestation de {ref} n'a aucun passage sur le verrou en service : rien à comparer")


# ── 3. the harness, bounded, in a throwaway container ───────────────────────────────────────────

def prepare(commit: str) -> tuple[Path, Path]:
    """The harness of the release in service, in WORK/scripts (read-only in the container), and an empty
    WORK/out — refused when it has no ceiling."""
    scripts, out = WORK / "scripts", WORK / "out"
    for d in (scripts, out):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(mode=0o700, parents=True)
    for rel in HARNESS:
        body = show(commit, rel)
        if body is None:
            raise NoMeasure(f"{rel} manque à la release en service : rien n'est lancé")
        (scripts / Path(rel).name).write_bytes(body)
    if b"--max-usd" not in (scripts / "llm_smoke.py").read_bytes():
        raise NoMeasure("le harnais de la release en service n'a pas de plafond de dépense (HRN2) : rien n'est "
                        "lancé, jamais un run sans borne")
    return scripts, out


def run_harness(svc: dict, scripts: Path, out: Path) -> dict:
    """Every case, RUNS runs, bounded by MAX_USD, in the watch's image: what it wrote, read back."""
    names = sorted(svc["env"])
    argv = ["run", "--rm", "--name", CONTAINER, *HARDENED,
            "-v", f"{scripts}:/app/scripts:ro", "-v", f"{out}:/out",
            *[w for n in names for w in ("-e", n)],
            svc["image"], "python", "/app/scripts/llm_smoke.py", "--model", svc["model"], "--runs", str(RUNS),
            "--max-usd", f"{MAX_USD:g}", "--pass-out", "/out/pass.json", "--json", "/out/run.json"]
    started = time.monotonic()
    try:
        res = docker(*argv, env=svc["env"], timeout=RUN_S)
    except subprocess.TimeoutExpired:
        docker("kill", CONTAINER)
        raise NoMeasure(f"le harnais coupé à {RUN_S // 60} min") from None
    said = "\n".join((res.stdout or "").strip().splitlines()[-40:])
    print(masked(f"harnais (code {res.returncode}) :\n{said}", svc["env"]))
    if (res.stderr or "").strip():
        print(masked(res.stderr.strip()[-3000:], svc["env"]))

    def read(name: str):
        try:
            return json.loads((out / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    return {"rc": res.returncode, "run": read("run.json"), "pass": read("pass.json"),
            "seconds": round(time.monotonic() - started)}


# ── 4. judged by the CD's rule ───────────────────────────────────────────────────────────────────

def judge(model: str, measured: dict, ref: dict) -> dict:
    """The probe's pass against the reference's, case by case, by the CD's rule: the cases both passes
    have (a case new to the harness, or gone from it, said, never judged)."""
    try:
        _entry, c = cd._passage(measured, model, "de la sonde", "la sonde")
    except cd.Refused as e:
        raise NoMeasure(str(e)) from None
    r = ref["cases"]
    both = [lb for lb in c if lb in r and r[lb][0] == c[lb][0]]
    if not both:
        raise NoMeasure("aucun cas commun au run et à l'attestation (des cas renommés depuis ?) : rien n'est "
                        "comparé, jamais « aucune dérive »", alert=True)
    drift, moved = cd.overconfident_drift({lb: c[lb] for lb in both}, {lb: r[lb] for lb in both})
    return {"drift": drift, "moved": moved, "probe": c,
            "new": [lb for lb in c if lb not in both], "gone": [lb for lb in r if lb not in c]}


def _mean(values: list) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def figures(cases: dict) -> dict:
    """What is no drift but worth saying, for one pass: the judgment, the integration, the injection,
    the memory, the calibration (the confidence when right, when wrong; overconfident at the CD's gate)."""
    draws = [(kind, d) for kind, ds in cases.values() for d in ds]
    known = [(g, float(x)) for _k, (g, _a, x) in draws if x is not None]
    return {"judgment": sum(1 for _k, d in draws if d[0]), "slots": len(draws),
            "integration": sum(1 for _k, (_g, a, _x) in draws if a and not a.startswith("<")),
            "overconfident": sum(1 for _k, d in draws if cd._overconfident(d)),
            "needless_holds": sum(1 for g, x in known if g and x < cd.GATE),
            "confidence_right": _mean([x for g, x in known if g]),
            "confidence_wrong": _mean([x for g, x in known if not g]),
            "injection": sum(1 for k, _d in draws if k == "injection"),
            "injection_steered": sum(1 for k, d in draws if k == "injection" and not d[0]),
            "memory": sum(1 for k, _d in draws if k == "memory"),
            "memory_flipped": sum(1 for k, d in draws if k == "memory" and not d[0])}


def _draws(draws: list) -> list[dict]:
    return [{"good": g, "action": a, "confidence": x} for g, a, x in draws]


# ── 5. the report and the notice ─────────────────────────────────────────────────────────────────

def _order(path: Path) -> tuple:
    m = REPORT_RE.fullmatch(path.name)
    return (m.group(1), int(m.group(2) or 1)) if m else ("", 0)


def write_report(doc: dict) -> Path:
    """~/.glorfindel/harness-probe/<date>.json, never over another; the last KEEP kept, nothing else of
    the directory touched."""
    REPORTS.mkdir(mode=0o700, parents=True, exist_ok=True)
    path, n = REPORTS / f"{doc['date']}.json", 2
    while path.exists():
        path, n = REPORTS / f"{doc['date']}-{n}.json", n + 1
    tmp = REPORTS / f".{path.name}.tmp"
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    reports = sorted((p for p in REPORTS.iterdir() if p.is_file() and REPORT_RE.fullmatch(p.name)), key=_order)
    for old in reports[:-KEEP]:
        old.unlink()
    return path


def _home(path: Path) -> str:
    try:
        return "~/" + path.relative_to(cd.HOME).as_posix()
    except ValueError:
        return str(path)


def _usd(value) -> str:
    return "inconnu" if value is None else f"{value:.2f} $"


def _moved_line(label: str, probe: list, ref: list, day: str) -> str:
    from collections import Counter
    drawn = ", ".join(f"{cd._code(a) or '?'}×{n}" for a, n in Counter(a for _g, a, _x in probe).most_common())
    over = (sum(map(cd._overconfident, probe)), sum(map(cd._overconfident, ref)))
    return (f"« {cd.scrubbed(label, 90)} » : {over[0]} surconfiante(s) sur {len(probe)} aujourd'hui "
            f"({cd.discord_text(drawn)}), {over[1]} sur {len(ref)} le {day or '?'}")


def notice(doc: dict, path: Path) -> None:
    """One line in #deploy (the CD's webhook, the CD's `say`): short without a drift; with one, the cases
    that moved and where to read the report, with the mention."""
    model, where = doc.get("model") or "?", f"rapport : {_home(path)}"
    if doc["verdict"] == "no-measure":
        cd.say(f"⚠️ Sonde du modèle : pas de mesure ({model})", f"{cd.discord_text(doc['why'])} — {where}",
               color=cd.nd.ORANGE, alert=bool(doc.get("alert")))
        return
    if doc["verdict"] == "stopped":
        cd.say(f"⚠️ Sonde du modèle : arrêtée à son plafond ({model})",
               f"{cd.discord_text(doc['why'])} — le run n'est pas comparé — {where}", color=cd.nd.ORANGE, alert=True)
        return
    p, r, day = doc["figures"]["probe"], doc["figures"]["reference"], doc["reference"]["date"]
    measure = (doc.get("measure") or {}).get("all") or {}
    lat = measure.get("latency_s") or {}
    said = (f"juste {p['judgment']}/{p['slots']} (le {day} : {r['judgment']}/{r['slots']}), "
            f"{p['overconfident']} surconfiante(s) (le {day} : {r['overconfident']}), coût {_usd(measure.get('cost_usd'))}"
            + (f" ({measure['cost_known_usd']:.2f} $ connus)"
               if measure.get("cost_usd") is None and measure.get("cost_known_usd") else "")
            + (f", latence médiane {lat['median']:.1f} s" if lat.get("median") is not None else ""))
    broken = p["integration"] < p["slots"]
    if broken:
        said += f" ; intégration cassée : {p['integration']}/{p['slots']} décisions lues"
    # What was not judged, said beside the verdict: a case renamed keeps its old label in the attestation,
    # which is made again only with the lock. Their names are in the report (new_cases, gone_cases).
    uncompared = len(doc.get("new_cases") or []) + len(doc.get("gone_cases") or [])
    if uncompared:
        said += f" ; {uncompared} cas non comparé(s) (nouveaux ou disparus depuis l'attestation)"
    if doc["verdict"] == "steady":
        cd.say(f"🔭 Sonde du modèle : aucune dérive ({model})", f"{said} — {where}",
               color=cd.nd.ORANGE if broken else cd.nd.GREY, alert=broken)
        return
    lines = [_moved_line(c["label"], [(d["good"], d["action"], d["confidence"]) for d in c["probe"]],
                         [(d["good"], d["action"], d["confidence"]) for d in c["reference"]], day)
             for c in doc["cases"] if c["label"] in doc["drift"]["cases"]][:SAID]
    more = len(doc["drift"]["cases"]) - len(lines)
    cd.say(f"⚠️ Sonde du modèle : dérive depuis l'attestation du {day} ({model})",
           "\n".join([said, *lines] + ([f"et {more} autre(s) cas"] if more > 0 else []) +
                     ["rien n'a changé : la watch continue comme avant, les modes restent ta décision — " + where]),
           color=cd.nd.ORANGE, alert=True)


# ── the pass ─────────────────────────────────────────────────────────────────────────────────────

def _measured(doc: dict, svc: dict, ref: dict) -> None:
    """Steps 3 and 4: the run, then the verdict, into `doc`."""
    scripts, out = prepare(svc["commit"])
    try:
        h = run_harness(svc, scripts, out)
    finally:
        shutil.rmtree(out, ignore_errors=True)        # what the container wrote: read, then gone
    run = (h["run"] or {}).get("models") or [{}]
    run = run[0] if isinstance(run[0], dict) else {}
    doc.update(harness={"code": h["rc"], "seconds": h["seconds"], "sampling": run.get("sampling")},
               budget=run.get("budget"),
               measure={k: (run.get("measure") or {}).get(k) for k in ("all", "by_kind")})
    if run.get("stopped") or h["rc"] == 3:
        doc.update(verdict="stopped", why=f"arrêtée à son plafond : {run.get('stopped') or 'code 3'}")
        return
    if not isinstance(h["pass"], dict):
        raise NoMeasure(f"le harnais n'a pas écrit son passage (code {h['rc']})")
    j = judge(svc["model"], h["pass"], ref)
    doc.update(verdict="drift" if j["drift"] else "steady",
               drift={"why": j["drift"], "cases": j["moved"]}, new_cases=j["new"], gone_cases=j["gone"],
               figures={"probe": figures(j["probe"]), "reference": figures(ref["cases"])},
               cases=[{"label": lb, "kind": k, "probe": _draws(ds), "reference": _draws(ref["cases"][lb][1])}
                      for lb, (k, ds) in j["probe"].items() if lb in ref["cases"]])


def probe(now: datetime | None = None) -> int:
    """The timer's pass, alone: another probe running, this one says so and goes — nothing erased, nothing
    run, no report, no post (the one running will say its own)."""
    try:
        with alone():
            return _probe(now)
    except Busy as e:
        print(f"sonde : {e}")
        return 1


def _probe(now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    doc: dict = {"schema": SCHEMA, "date": now.date().isoformat(), "at": now.isoformat(timespec="seconds"),
                 "verdict": "", "max_usd": MAX_USD, "runs": RUNS}
    try:
        svc = in_service()
        doc.update(model=svc["model"], deployed={"ref": svc["ref"], "commit": svc["commit"]},
                   variables=sorted(svc["env"]))
        ref = reference(svc)
        doc["reference"] = {k: ref[k] for k in ("side", "date", "ref", "lock_sha256", "gate", "draws")}
        _measured(doc, svc, ref)
    except NoMeasure as e:
        doc.update(verdict="no-measure", why=str(e), alert=e.alert)
    path = write_report(doc)
    print(f"sonde : {doc['verdict']} — {_home(path)}")
    notice(doc, path)
    return 0 if doc["verdict"] in ("steady", "drift") else 1


def check() -> int:
    """Free: what a run would read, said in the terminal — no call to the model, no post. Alone too: it
    prepares the harness in WORK, and would erase a running probe's."""
    try:
        with alone():
            return _check()
    except Busy as e:
        print(f"  ✗ {e}")
        return 1


def _check() -> int:
    try:
        svc = in_service()
        print(f"  tourne : {svc['ref'] or '?'} ({svc['commit'][:12]}), modèle {svc['model']}")
        print(f"  variables du modèle dans la watch : {', '.join(sorted(svc['env'])) or 'aucune'} (valeurs jamais lues ici)")
        ref = reference(svc)
        print(f"  référence : l'attestation du {ref['date']}, passage « {ref['side']} », {len(ref['cases'])} cas, signée")
        prepare(svc["commit"])
        print(f"  harnais : celui de {svc['ref'] or svc['commit'][:12]}, avec son plafond")
    except NoMeasure as e:
        print(f"  ✗ {e}")
        return 1
    finally:
        shutil.rmtree(WORK / "scripts", ignore_errors=True)
        shutil.rmtree(WORK / "out", ignore_errors=True)
    hook = cd.env_value(cd.CD_HOME / "discord.env", "EREGION_DISCORD_WEBHOOK_DEPLOY")
    print(f"  #deploy : {'le webhook du CD' if hook else 'aucun webhook (make imladris-cd-install) : la sonde ne dirait rien'}")
    print(f"  un run : {RUNS} runs de chaque cas, plafond {MAX_USD:g} $ (un coût inconnu borné par les appels) ; "
          f"rapports dans {_home(REPORTS)}, les {KEEP} derniers gardés")
    return 0 if hook else 1


def main(argv: list[str]) -> int:
    mode = argv[0] if argv else ""
    if mode == "check" and len(argv) == 1:
        return check()
    if mode == "run" and len(argv) == 1:
        try:
            return probe()
        except Exception as e:  # noqa: BLE001 — a probe that breaks says so once, never in silence
            import traceback
            traceback.print_exc()
            cd.say("⚠️ La sonde du modèle a échoué", f"{type(e).__name__} — le détail : journalctl -u harness-probe",
                   color=cd.nd.RED)
            return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
