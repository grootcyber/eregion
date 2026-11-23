"""HRN2 (#1079) — the model's probe, once a week on Imladris (infra/glorfindel-host/cd/harness_probe.py).

The provider can move a model under its name: on 23/11, to a message identical to the byte, the modest
disk write that drew a snapshot at 0.50 and two isolations at 0.65 and 0.55 on 06/11 (all held under the
gate) drew 8 isolations out of 8, 5 of them at 0.7 or more. The probe runs the harness on the model and
the key in service, judges each case against the signed attestation of the release in service by the
CD's own rule (eregion_cd.overconfident_drift: one rule, two readers), writes its report in its own
folder and says it in #deploy — never changing anything.

Here nothing reaches a model, Docker, git or Discord: the agent runs as on Imladris, in a throwaway HOME,
its `docker` a fake that writes what the harness would (the pass, the run's measure), its git a dict of
the release's files, the signature and #deploy (the CD's `signed_by` and `say`) noted. Placeholder
secrets only.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CD_DIR = ROOT / "infra" / "glorfindel-host" / "cd"
PROBE = CD_DIR / "harness_probe.py"
MODEL = "anthropic/claude-sonnet-5-5"
SECRET = "sk-ant-PLACEHOLDER-not-a-key-0000"
COMMIT = "c" * 40
LOCK = b"litellm==1.100.4 --hash=sha256:0000\n"
OTHER_LOCK = b"litellm==1.86.1 --hash=sha256:1111\n"
DISK = "modest disk write — likely a large copy, not ransomware"
NOW = datetime(2026, 11, 29, 2, 41, tzinfo=timezone.utc)


def _scenarios():
    spec = importlib.util.spec_from_file_location("llm_smoke_hrn2", ROOT / "scripts" / "llm_smoke.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return [(s["label"], s["kind"]) for s in mod.SCENARIOS]


CASES = _scenarios()


def _d(good=True, action="isolate_vm", conf=0.85):
    return {"good": good, "action": action, "confidence": conf}


# 06/11 on the modest disk write: a snapshot, two isolations under the gate — each held, so each right.
DISK_0611 = [_d(True, "snapshot", 0.5), _d(True, "isolate_vm", 0.65), _d(True, "isolate_vm", 0.55)]
# 23/11: isolated on every draw, at 0.7 or more, the draws agreeing — wrong, and through the gate.
DISK_2311 = [_d(False, "isolate_vm", 0.85), _d(False, "isolate_vm", 0.75), _d(False, "isolate_vm", 0.7)]


def _pass(lock=LOCK, draws=None, drop=(), extra=(), date="2026-11-06"):
    draws = draws or {}
    cases = [{"label": lb, "kind": k, "draws": draws.get(lb, [_d()] * 3)} for lb, k in CASES if lb not in drop]
    cases += [{"label": lb, "kind": k, "draws": ds} for lb, k, ds in extra]
    every = [d for c in cases for d in c["draws"]]
    return {"schema": "eregion.harness-pass/2", "ref": "", "lock": "requirements/glorfindel.txt",
            "lock_sha256": hashlib.sha256(lock).hexdigest(), "date": date, "runs": 3, "draws": "3", "gate": 0.7,
            "kinds": "all", "models": [{"model": MODEL, "integration": len(every), "slots": len(every),
                                        "judgment": sum(d["good"] for d in every), "cases": cases}]}


def _attestation(cand=None, ref=None):
    return json.dumps({"schema": "eregion.harness/2", "lock": "requirements/glorfindel.txt", "date": "2026-11-06",
                       "candidate": cand or _pass(draws={DISK: DISK_0611}),
                       "reference": ref or _pass(OTHER_LOCK, date="2026-11-06")}).encode()


SMOKE = b"#!/usr/bin/env python3\n# the harness of the release (fake)\nap.add_argument('--max-usd')\n"


def _run_doc(stopped="", cost=1.15):
    summary = {"calls": 140, "failed": 0, "draws": 86, "latency_s": {"median": 5.8, "p95": 9.6, "max": 12.0},
               "cost_usd": cost, "cost_unknown": 0, "cost_known_usd": cost}
    return {"runs": 3, "draws": "3", "models": [{
        "model": MODEL, "sampling": "the model's default sampling — it refuses a temperature",
        "measure": {"all": summary, "by_kind": {"act": summary}, "calls": [{"slot": 1, "error": ""}]},
        "budget": {"max_usd": 3.0, "max_calls": 162, "calls": 140, "known_usd": cost, "unknown": 0,
                   "charged_usd": cost, "stopped": stopped},
        "stopped": stopped, "cases": [{"label": DISK, "slots": [{"reasoning": SECRET}]}]}]}


class FakeDocker:
    """`docker inspect` the watch (its image, its environment), `docker run` the harness: writes its pass
    and its run where the probe mounted /out, as llm_smoke.py would."""

    def __init__(self, probe_pass=None, run=None, rc=0, write_pass=True):
        self.probe_pass = probe_pass if probe_pass is not None else _pass(draws={DISK: DISK_0611})
        self.run = run if run is not None else _run_doc()
        self.rc, self.write_pass = rc, write_pass
        self.watch_env = {"GLORFINDEL_LLM_MODEL": MODEL, "ANTHROPIC_API_KEY": SECRET, "OPENAI_API_KEY": "",
                          "DISCORD_BOT_TOKEN": "bot-PLACEHOLDER-token", "GLORFINDEL_WEBHOOK_URL": "https://h/x",
                          "PATH": "/usr/local/bin"}
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, *args, env=None, timeout=60):
        self.calls.append((list(args), dict(env or {})))
        if args[0] == "inspect":
            env_list = [f"{k}={v}" for k, v in self.watch_env.items()]
            return subprocess.CompletedProcess(args, 0, f"sha256:feedface {json.dumps(env_list)}\n", "")
        if args[0] == "run":
            out = Path(next(a for a in args if a.endswith(":/out")).rsplit(":", 1)[0])
            if self.write_pass:
                (out / "pass.json").write_text(json.dumps(self.probe_pass))
            (out / "run.json").write_text(json.dumps(self.run))
            # What a provider's error may echo: the journal gets it with the key taken out.
            return subprocess.CompletedProcess(args, self.rc, f"✓ [act] ransomware — good 3/3\nkey {SECRET}\n",
                                               f"AuthenticationError: {SECRET} refused")
        return subprocess.CompletedProcess(args, 0, "", "")

    def runs(self):
        return [a for a, _e in self.calls if a[0] == "run"]


class Imladris:
    """The probe as installed on Imladris, in a throwaway HOME: its fakes and what it said."""

    def __init__(self, tmp_path, monkeypatch, files=None, docker=None, signed=True):
        self.home = tmp_path / "home"
        for d in (".eregion-cd", "eregion", ".glorfindel/isolation", ".glorfindel/memory"):
            (self.home / d).mkdir(parents=True, exist_ok=True)
        # The watch's state and Imladris's configuration: what the probe must never touch.
        (self.home / "eregion" / "glorfindel-config.yaml").write_text("assets:\n  vm-a: {autonomy: non_disruptive}\n")
        (self.home / "eregion" / ".env").write_text(f"ANTHROPIC_API_KEY={SECRET}\nGLORFINDEL_LLM_MODEL={MODEL}\n")
        (self.home / ".glorfindel" / "isolation" / "vm-a.json").write_text('{"isolated": false}')
        (self.home / ".glorfindel" / "memory" / "cycles.jsonl").write_text('{"cycle": 1}\n')
        (self.home / ".glorfindel" / "2026-11-01.json").write_text('{"not": "a report of the probe"}')
        monkeypatch.setenv("HOME", str(self.home))
        monkeypatch.setenv("EREGION_CD_HOME", str(self.home / ".eregion-cd"))
        monkeypatch.setenv("EREGION_CD_REPO", str(self.home / "eregion"))
        monkeypatch.setattr(sys, "path", list(sys.path))
        for name in ("eregion_cd", "notify_discord", "published_image", "chat_text"):
            monkeypatch.delitem(sys.modules, name, raising=False)
        spec = importlib.util.spec_from_file_location("harness_probe_t", PROBE)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.files = {"requirements/harness.json": _attestation(), "requirements/glorfindel.txt": LOCK,
                      "scripts/llm_smoke.py": SMOKE, "scripts/harness_meter.py": b"# the meter (fake)\n",
                      **(files or {})}
        self.docker = docker or FakeDocker()
        self.said: list[tuple[str, str, dict]] = []
        self.signed: list[Path] = []
        cd = self.mod.cd
        monkeypatch.setattr(cd, "deployed", lambda: ("v0.6.5", COMMIT))
        monkeypatch.setattr(self.mod, "show", lambda commit, path: self.files.get(path) if commit == COMMIT else None)
        monkeypatch.setattr(self.mod, "docker", self.docker)

        def signed_by(tag, commit, hint, work=None):
            self.signed.append(work)
            if not signed:
                raise cd.Refused("l'attestation n'est pas signée (placeholder)")
        monkeypatch.setattr(cd, "signed_by", signed_by)
        monkeypatch.setattr(cd, "say", lambda title, text="", **kw: self.said.append((title, text, kw)) or True)

    def run(self, now=NOW) -> int:
        return self.mod.probe(now)

    def reports(self) -> list[Path]:
        return sorted((self.home / ".glorfindel" / "harness-probe").glob("*.json"))

    def report(self) -> dict:
        return json.loads(self.reports()[-1].read_text())

    def tree(self) -> dict[str, bytes]:
        return {p.relative_to(self.home).as_posix(): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}


@pytest.fixture
def imladris(tmp_path, monkeypatch):
    def make(**kw):
        return Imladris(tmp_path, monkeypatch, **kw)
    return make


# ── The drift, by the CD's rule ──────────────────────────────────────────────────────────────────

def test_the_drift_of_23_11_is_said_with_the_cases_that_moved(imladris):
    """M7115: the modest disk write isolating on every draw at 0.7 or more, where the attestation of 06/11
    held it — a drift, said in #deploy with the mention, the case named, where to read the report."""
    h = imladris(docker=FakeDocker(probe_pass=_pass(draws={DISK: DISK_2311})))
    assert h.run() == 0
    doc = h.report()
    assert doc["verdict"] == "drift" and doc["drift"]["cases"] == [DISK]
    assert "erreurs surconfiantes : 1 cas en gagne(nt) 2 ou plus" in doc["drift"]["why"]
    (title, text, kw) = h.said[-1]
    assert "dérive depuis l'attestation du 2026-11-06" in title and MODEL in title and kw["alert"] is True
    assert f"« {DISK} » : 3 surconfiante(s) sur 3 aujourd'hui" in text and "0 sur 3 le 2026-11-06" in text
    assert "rapport : ~/.glorfindel/harness-probe/2026-11-29.json" in text
    assert "rien n'a changé : la watch continue comme avant, les modes restent ta décision" in text


def test_a_run_like_its_reference_says_no_drift_in_one_short_line(imladris):
    """M7116: wrong draws under the gate are no overconfidence — a run that varies, held where it should be,
    is no drift: one line, silent."""
    noisy = {DISK: [_d(True, "snapshot", 0.5), _d(False, "isolate_vm", 0.6), _d(False, "isolate_vm", 0.55)],
             CASES[0][0]: [_d(), _d(False, "snapshot", 0.5), _d()],
             CASES[1][0]: [_d(False, "no_action", 0.4)] * 3}
    h = imladris(docker=FakeDocker(probe_pass=_pass(draws=noisy)))
    assert h.run() == 0
    assert h.report()["verdict"] == "steady" and h.report()["drift"] == {"why": "", "cases": []}
    [(title, text, kw)] = h.said
    assert title == f"🔭 Sonde du modèle : aucune dérive ({MODEL})" and "\n" not in text
    assert kw.get("alert") is False
    assert text.startswith(f"juste {3 * len(CASES) - 6}/{3 * len(CASES)} (le 2026-11-06 : {3 * len(CASES)}/")
    assert "0 surconfiante(s)" in text and "coût 1.15 $" in text and "latence médiane 5.8 s" in text


def test_a_cost_unknown_is_said_with_its_known_part(imladris):
    run = _run_doc(cost=None)
    run["models"][0]["measure"]["all"].update(cost_unknown=2, cost_known_usd=1.12)
    h = imladris(docker=FakeDocker(run=run))
    assert h.run() == 0
    assert "coût inconnu (1.12 $ connus), latence médiane" in h.said[-1][1]


@pytest.mark.parametrize("cases, drift", [(1, False), (2, True)])
def test_one_case_newly_overconfident_is_noise_two_are_a_drift(imladris, cases, drift):
    """The CD's tolerance, read where it lives: one case, one draw — the noise of a lock against itself."""
    labels = [lb for lb, k in CASES if k == "act"][:cases]
    once = {lb: [_d(), _d(), _d(False, "snapshot", 0.9)] for lb in labels}
    h = imladris(docker=FakeDocker(probe_pass=_pass(draws=once)))
    assert h.run() == 0
    assert (h.report()["verdict"] == "drift") is drift


def test_the_rule_is_the_cd_s_own_never_a_copy(imladris):
    """One rule, two readers: the probe holds none of the CD's thresholds, and follows what the CD's
    function says."""
    src = PROBE.read_text()
    for own in ("OVERCONFIDENT_GAIN", "NEW_OVERCONFIDENT_CASES", ">= 0.7", ">= 2", "GATE =", "def _overconfident"):
        assert own not in src
    h = imladris()
    seen = []

    def rule(c, r):
        seen.append((sorted(c), sorted(r)))
        return "la règle du CD a parlé", [CASES[0][0]]
    h.mod.cd.overconfident_drift = rule
    assert h.run() == 0
    assert h.report()["verdict"] == "drift" and h.report()["drift"]["why"] == "la règle du CD a parlé"
    assert seen and seen[0][0] == seen[0][1] == sorted(lb for lb, _k in CASES)


def test_the_cd_refuses_a_lock_on_the_same_function(imladris):
    """The CD's attestation reads the rule through the function the probe reads (eregion_cd.attested)."""
    src = (CD_DIR / "eregion_cd.py").read_text()
    body = src.split("def attested(", 1)[1].split("\ndef ", 1)[0]
    assert "overconfident_drift(c, r)" in body and "OVERCONFIDENT_GAIN" not in body


def test_a_case_new_to_the_harness_is_said_never_judged(imladris):
    """A case the attestation does not have (one added since): no reference, so no drift on it."""
    new = ("a case added since the attestation", "caution", DISK_2311)
    h = imladris(docker=FakeDocker(probe_pass=_pass(extra=[new], drop=[CASES[-1][0]])))
    assert h.run() == 0
    doc = h.report()
    assert doc["verdict"] == "steady" and doc["new_cases"] == [new[0]] and doc["gone_cases"] == [CASES[-1][0]]
    # « aucune dérive », but never without what was not compared: their count in #deploy, names in the report.
    assert "aucune dérive" in h.said[-1][0]
    assert "2 cas non comparé(s) (nouveaux ou disparus depuis l'attestation)" in h.said[-1][1]


def test_a_run_without_a_case_in_common_is_no_measure_with_the_mention(imladris):
    """M7122: every case renamed since the attestation — nothing compared, so never « aucune dérive »."""
    renamed = _pass(draws={}, drop=[lb for lb, _k in CASES],
                    extra=[(f"{lb} (renamed)", k, [_d()] * 3) for lb, k in CASES])
    h = imladris(docker=FakeDocker(probe_pass=renamed))
    assert h.run() == 1
    doc = h.report()
    assert doc["verdict"] == "no-measure" and "aucun cas commun" in doc["why"] and doc["alert"] is True
    [(title, text, kw)] = h.said
    assert "pas de mesure" in title and "aucune dérive" not in title and kw["alert"] is True


def test_the_reference_is_the_attestation_s_pass_on_the_lock_in_service(imladris):
    """The attestation holds two passes: the probe compares with the one on the lock that runs."""
    att = _attestation(cand=_pass(OTHER_LOCK), ref=_pass(LOCK, draws={DISK: DISK_2311}))
    h = imladris(files={"requirements/harness.json": att},
                 docker=FakeDocker(probe_pass=_pass(draws={DISK: DISK_2311})))
    assert h.run() == 0
    assert h.report()["reference"]["side"] == "reference" and h.report()["verdict"] == "steady"


# ── Nothing run without a bound, a reference, a signature ───────────────────────────────────────

@pytest.mark.parametrize("files, signed, said", [
    ({"requirements/harness.json": None}, True, "n'a pas d'attestation du harnais"),
    ({}, False, "n'est pas crue"),
    ({"scripts/llm_smoke.py": b"# a harness from before HRN2\n"}, True, "pas de plafond de dépense"),
    ({"requirements/glorfindel.txt": b"litellm==9.9.9\n"}, True, "aucun passage sur le verrou en service"),
])
def test_without_a_signed_reference_or_a_ceiling_nothing_is_run(imladris, files, signed, said):
    h = imladris(files=files, signed=signed)
    assert h.run() == 1
    assert h.docker.runs() == []
    doc = h.report()
    assert doc["verdict"] == "no-measure" and said in doc["why"]
    [(title, text, kw)] = h.said
    assert "pas de mesure" in title and said in text


def test_the_signature_is_checked_in_the_probe_s_own_folder_never_the_cd_s(imladris):
    h = imladris()
    assert h.run() == 0
    assert h.signed == [h.home / ".eregion-cd" / "probe" / "harness-check"]


def test_the_run_is_bounded_every_case_three_runs_on_the_model_in_service(imladris):
    h = imladris()
    assert h.run() == 0
    [argv] = h.docker.runs()
    tail = argv[argv.index("sha256:feedface"):]
    assert tail == ["sha256:feedface", "python", "/app/scripts/llm_smoke.py", "--model", MODEL, "--runs", "3",
                    "--max-usd", "3", "--pass-out", "/out/pass.json", "--json", "/out/run.json"]
    assert "--kinds" not in argv
    # Bounded beside the watch (4 GB shared): systemd's Nice reaches the docker CLI only.
    head = argv[:argv.index("-v")]
    for opt in (["--cpus", "1"], ["--memory", "1g"], ["--pids-limit", "256"],
                ["--security-opt", "no-new-privileges"], ["--cap-drop", "ALL"]):
        assert any(head[i:i + 2] == opt for i in range(len(head))), opt
    assert "--privileged" not in argv and "--user" not in argv          # the image's own user, non-root


def test_two_probes_never_run_at_once(imladris):
    """M7121: a probe holds WORK/.lock — a second one (the timer's, or one by hand) says so and goes: it
    erases nothing (the running one's out dir kept), runs nothing, writes no report, posts nothing."""
    import fcntl
    h = imladris()
    work = h.home / ".eregion-cd" / "probe"
    (work / "out").mkdir(parents=True)
    (work / "out" / "run.json").write_text("the running probe's")
    with open(work / ".lock", "a") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert h.run() == 1
        assert h.mod.check() == 1
    assert h.docker.calls == [] and h.said == [] and not h.reports() and h.signed == []
    assert (work / "out" / "run.json").read_text() == "the running probe's"
    assert h.run() == 0                                       # the lock let go: the next one runs


def test_a_run_stopped_at_its_ceiling_is_said_never_compared(imladris):
    """M7117/M7118's consequence on Imladris: the harness stopped (code 3, no pass) — said, with the
    mention, never judged on what it drew before."""
    h = imladris(docker=FakeDocker(run=_run_doc(stopped="the ceiling of $3.00 reached: $3.0100 measured"),
                                   rc=3, write_pass=False))
    assert h.run() == 1
    doc = h.report()
    assert doc["verdict"] == "stopped" and "the ceiling of $3.00 reached" in doc["why"] and "cases" not in doc
    [(title, text, kw)] = h.said
    assert "arrêtée à son plafond" in title and "le run n'est pas comparé" in text and kw["alert"] is True


# ── What it writes, what it never touches ────────────────────────────────────────────────────────

def test_nothing_is_written_outside_its_folder_and_no_mode_changes(imladris):
    """M7119: a whole pass, with a drift — what changed in HOME is its report in ~/.glorfindel/harness-probe
    and its work dir in ~/.eregion-cd/probe; the watch's state, its memory, its configuration (the modes)
    and Imladris's .env are as they were, to the byte."""
    h = imladris(docker=FakeDocker(probe_pass=_pass(draws={DISK: DISK_2311})))
    before = h.tree()
    assert h.run() == 0
    after = h.tree()
    changed = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
    assert changed and all(p.startswith((".glorfindel/harness-probe/", ".eregion-cd/probe/")) for p in changed), changed
    assert ".glorfindel/harness-probe/2026-11-29.json" in changed
    assert not any(p.startswith(".eregion-cd/probe/out") for p in after), "what the container wrote, gone"


def test_the_container_mounts_neither_the_watch_s_state_nor_a_secret(imladris, capsys):
    """The harness runs in a throwaway container of the watch's image: its scripts read-only, its out dir
    — nothing of ~/.glorfindel nor of the configuration. The key passes by its name; its value is in
    neither a command line, nor the report, nor #deploy, nor the journal. Only the model's variables."""
    h = imladris()
    assert h.run() == 0
    [(argv, env)] = [c for c in h.docker.calls if c[0][0] == "run"]
    mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]
    work = h.home / ".eregion-cd" / "probe"
    assert mounts == [f"{work / 'scripts'}:/app/scripts:ro", f"{work / 'out'}:/out"]
    names = [argv[i + 1] for i, a in enumerate(argv) if a == "-e"]
    assert names == ["ANTHROPIC_API_KEY", "GLORFINDEL_LLM_MODEL"]
    assert env == {"ANTHROPIC_API_KEY": SECRET, "GLORFINDEL_LLM_MODEL": MODEL}
    seen = " ".join(argv) + h.reports()[-1].read_text() + json.dumps(h.said) + capsys.readouterr().out
    for secret in (SECRET, "bot-PLACEHOLDER-token", "https://h/x"):
        assert secret not in seen
    assert "key <masqué>" in seen and "AuthenticationError: <masqué> refused" in seen and MODEL in seen


def test_reports_are_never_overwritten_and_the_last_26_are_kept(imladris):
    h = imladris()
    folder = h.home / ".glorfindel" / "harness-probe"
    folder.mkdir(parents=True)
    for week in range(30):
        (folder / f"2025-{1 + week // 4:02d}-{1 + week % 4 * 7:02d}.json").write_text("{}")
    (folder / "notes.txt").write_text("Jonathan's own")
    for _ in range(3):
        assert h.run() == 0
    names = sorted(p.name for p in folder.iterdir() if p.suffix == ".json")
    assert names[-3:] == ["2026-11-29-2.json", "2026-11-29-3.json", "2026-11-29.json"]
    assert len(names) == 26 and (folder / "notes.txt").exists()
    assert "2025-01-01.json" not in names and (h.home / ".glorfindel" / "2026-11-01.json").exists()


def test_check_is_free_and_names_the_variables_never_their_values(imladris, capsys):
    h = imladris()
    (h.home / ".eregion-cd" / "discord.env").write_text("EREGION_DISCORD_WEBHOOK_DEPLOY=https://discord.example/x\n")
    assert h.mod.check() == 0
    out = capsys.readouterr().out
    assert h.docker.runs() == [] and h.said == [] and not h.reports()
    assert "ANTHROPIC_API_KEY, GLORFINDEL_LLM_MODEL" in out and SECRET not in out
    assert "référence : l'attestation du 2026-11-06" in out and "plafond 3 $" in out


def test_a_probe_that_breaks_says_so(imladris, monkeypatch):
    h = imladris()
    monkeypatch.setattr(h.mod, "in_service", lambda: 1 / 0)
    assert h.mod.main(["run"]) == 1
    assert h.said[-1][0] == "⚠️ La sonde du modèle a échoué"
    assert h.mod.main([]) == 2 and h.mod.main(["run", "x"]) == 2


# ── Installed beside the CD, its timer once a week at night, enabled by Jonathan ─────────────────

def test_the_units_run_the_probe_once_a_week_at_night_as_imladris_s_user():
    service = (CD_DIR / "harness-probe.service").read_text()
    timer = (CD_DIR / "harness-probe.timer").read_text()
    assert "ExecStart=/usr/bin/python3 @HOME@/.eregion-cd/harness_probe.py run" in service
    assert "User=@USER@" in service and "Type=oneshot" in service
    assert "OnCalendar=Sun *-*-* 02:30:00 UTC" in timer and "Persistent=true" in timer
    assert "OnUnitActiveSec" not in timer and "WantedBy=timers.target" in timer


def test_install_sh_installs_the_probe_s_units_its_timer_left_as_it_was():
    src = (CD_DIR / "install.sh").read_text()
    assert "harness_probe.py harness-probe.service harness-probe.timer" in src
    assert "for unit in eregion-cd harness-probe; do" in src
    assert "systemctl disable --now harness-probe.timer" in src.split('if [ "${1:-}" = "--remove" ]', 1)[1]
    assert "systemctl enable" not in src       # installed disabled: enabling is Jonathan's gesture
