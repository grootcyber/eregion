"""ROT1 (#737): a pair's secret turned in one command, `make pair-rotate PAIR=…`, and its end noted
on Imladris, `make pair-expiry-note PAIR=…`, whose CD reminds in #deploy at J-14, J-7, J-1 and on
the day.

On fakes only, in tmp_path — no Azure, no Graph, no Imladris, no Discord:
  - a fake `az` first on PATH: each pair's two objects (`app`, `sp`), their secrets (key id, end,
    value), answering PAIR1's dates query, the key ids, `credential reset --append` (a new value
    drawn) and `credential delete`; every call logged, in one journal with the others;
  - a fake `docker`: the compose services that run, `up --force-recreate` recording which secret
    each pair's variable carried in its environment (never its argv);
  - a fake `ssh` that runs the remote command in a fake home of Imladris, where the real CD agent
    (infra/glorfindel-host/cd/eregion_cd.py) is installed, as `make glorfindel-host-cd-install`
    puts it;
  - the token endpoint and Azure Resource Manager answered in-process: a token only for a secret
    the fake az holds;
  - a fake .envrc in tmp_path; the fake Discord (tests/unit/fake_discord.py) for #deploy.
Held here: the secret never on the screen, in a log, in an argv; the old one removed only after the
new one is verified; a failure leaves all in place; refused in a code session and without a
terminal; the reminders at J-14, J-7, J-1 and on the day, once per tier, even after a restart.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from .fake_discord import FakeDiscord

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import pair_rotate as pr  # noqa: E402

AGENT = ROOT / "infra" / "glorfindel-host" / "cd" / "eregion_cd.py"
TENANT = "dddddddd-4444-4444-8444-00000000000d"
IDS = {"watch": "aaaaaaaa-1111-4111-8111-000000000001", "console": "aaaaaaaa-1111-4111-8111-000000000002",
       "bot": "aaaaaaaa-1111-4111-8111-000000000003"}
OLD = "old~SECRET.value-never-shown_1"
NOW = datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc)
HOOK = "HOOK-TOKEN-never-shown"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash needed")

_FAKE_AZ = r'''#!PYTHON
"""A fake az: the pairs' objects in az.json, every call in events.jsonl, beside its bin/."""
import json, os, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent     # its state beside it: whatever environment az is given
args = sys.argv[1:]
with open(HERE / "events.jsonl", "a") as f:
    f.write(json.dumps({"who": "az", "argv": args}) + "\n")
p = HERE / "az.json"
st = json.load(open(p))
def save():
    json.dump(st, open(p, "w"))
def arg(name):
    return args[args.index(name) + 1] if name in args else ""
if args[:1] != ["ad"] or len(args) < 3 or args[1] not in ("app", "sp"):
    sys.stderr.write("fake az: unknown command\n"); sys.exit(99)
obj, app = args[1], arg("--id")
held = st["apps"].get(app, {}).get(obj)
if held is None or obj in st.get("unreadable", []):
    sys.stderr.write("ERROR: Resource '%s' does not exist or one of its queried reference-property objects are not present.\n" % app)
    sys.exit(1)
if args[2] == "show":
    q = arg("--query")
    if q == "{secrets: passwordCredentials[].endDateTime, certificates: keyCredentials[].endDateTime}":
        print(json.dumps({"secrets": [s["end"] for s in held["secrets"]], "certificates": held.get("certificates", [])}))
    elif q == "passwordCredentials[].keyId":
        print(json.dumps([s["keyId"] for s in held["secrets"]]))
    else:
        sys.stderr.write("fake az: unknown query\n"); sys.exit(99)
    sys.exit(0)
if args[2:4] == ["credential", "reset"]:
    if "--append" not in args or st.get("fail_reset"):
        sys.stderr.write("ERROR: refused by the fake\n"); sys.exit(1)
    st["drawn"] = st.get("drawn", 0) + 1
    value = "NEW~secret.%d-never-shown" % st["drawn"]
    held["secrets"].append({"keyId": "eeeeeeee-5555-4555-8555-%012d" % st["drawn"], "end": arg("--end-date"),
                            "value": value, "name": arg("--display-name")})
    save()
    sys.stderr.write("WARNING: The output includes credentials that you must protect.\n")
    print(json.dumps({"appId": app, "password": value, "tenant": st["tenant"]}))
    sys.exit(0)
if args[2:4] == ["credential", "delete"]:
    key = arg("--key-id")
    if key in st.get("fail_delete", []):
        sys.stderr.write("ERROR: refused by the fake\n"); sys.exit(1)
    held["secrets"] = [s for s in held["secrets"] if s["keyId"] != key]
    save()
    sys.exit(0)
sys.stderr.write("fake az: unknown command\n"); sys.exit(99)
'''

_FAKE_DOCKER = r'''#!PYTHON
"""A fake docker compose: the running services in $FAKE_DOCKER_STATE; every call in $FAKE_EVENTS,
with the secret each pair's variable carries in its environment."""
import json, os, sys
args = sys.argv[1:]
p = os.environ["FAKE_DOCKER_STATE"]
st = json.load(open(p))
names = ("GLORFINDEL_AZURE_CLIENT_SECRET", "EREGION_CONSOLE_AZURE_CLIENT_SECRET", "GLORFINDEL_BOT_AZURE_CLIENT_SECRET",
         "AZURE_CLIENT_SECRET")
with open(os.environ["FAKE_EVENTS"], "a") as f:
    f.write(json.dumps({"who": "docker", "argv": args, "env": {n: os.environ.get(n, "") for n in names}}) + "\n")
if st.get("down"):
    sys.exit(1)
if "ps" in args:
    print("\n".join(st["running"]))
    sys.exit(0)
if "up" in args:
    svc = args[-1]
    var = {"watch": "GLORFINDEL_AZURE_CLIENT_SECRET", "war-room": "EREGION_CONSOLE_AZURE_CLIENT_SECRET",
           "bot": "GLORFINDEL_BOT_AZURE_CLIENT_SECRET"}[svc]
    if os.environ.get(var, "") in st.get("refuse", []):
        st["running"] = [s for s in st["running"] if s != svc]
        json.dump(st, open(p, "w"))
        sys.exit(1)
    if svc not in st["running"]:
        st["running"].append(svc)
        json.dump(st, open(p, "w"))
    sys.exit(0)
sys.exit(99)
'''

_FAKE_SSH = r'''#!PYTHON
"""A fake ssh to Imladris: the remote command run by bash in $FAKE_IMLADRIS, its stdin given."""
import json, os, subprocess, sys
args = sys.argv[1:]
data = sys.stdin.read()
with open(os.environ["FAKE_EVENTS"], "a") as f:
    f.write(json.dumps({"who": "ssh", "argv": args, "stdin": data}) + "\n")
home = os.environ["FAKE_IMLADRIS"]
env = {"PATH": os.environ["PATH"], "HOME": home}
res = subprocess.run(["bash", "-c", args[-1]], cwd=home, input=data, text=True, env=env, capture_output=True)
sys.stdout.write(res.stdout); sys.stderr.write(res.stderr)
sys.exit(res.returncode)
'''


@pytest.fixture(autouse=True)
def only_fakes_on_the_path(tmp_path, monkeypatch):
    """Whatever runs a tool by its name finds the fake first — never a real az, docker or ssh."""
    (tmp_path / "bin").mkdir()
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}")


class World:
    """The fakes of one test: the pairs on Azure, the workstation's .envrc, docker, Imladris."""

    def __init__(self, tmp_path: Path, held: dict | None = None, running=("watch", "war-room"),
                 envrc: str | None = None, cd: bool = True, mode: int = 0o600):
        self.tmp = tmp_path
        self.bin = tmp_path / "bin"
        self.bin.mkdir(exist_ok=True)
        self.events = tmp_path / "events.jsonl"
        self.events.write_text("")
        self.az_state = tmp_path / "az.json"
        apps = {app: {"app": {"secrets": [], "certificates": []}, "sp": {"secrets": [], "certificates": []}}
                for app in IDS.values()}
        apps[IDS["console"]]["sp"]["secrets"].append(
            {"keyId": "cccccccc-3333-4333-8333-000000000001", "end": "2026-12-08T10:00:00Z", "value": OLD})
        apps[IDS["watch"]]["app"]["secrets"].append(
            {"keyId": "cccccccc-3333-4333-8333-000000000002", "end": "2027-10-01T10:00:00Z", "value": "watch-OLD-never"})
        for app, objs in (held or {}).items():
            apps[app] = objs
        self.az_state.write_text(json.dumps({"apps": apps, "tenant": TENANT}))
        self.docker_state = tmp_path / "docker.json"
        self.docker_state.write_text(json.dumps({"running": list(running)}))
        self.imladris = tmp_path / "imladris"
        self.imladris.mkdir()
        if cd:
            cd_home = self.imladris / ".eregion-cd"
            cd_home.mkdir(mode=0o700)
            for src in (AGENT, ROOT / "scripts" / "notify_discord.py", ROOT / "glorfindel" / "chat_text.py",
                        ROOT / "scripts" / "published_image.py"):
                shutil.copy(src, cd_home / src.name)
        for name, body in (("az", _FAKE_AZ), ("docker", _FAKE_DOCKER), ("ssh", _FAKE_SSH)):
            f = self.bin / name
            f.write_text(body.replace("PYTHON", sys.executable))
            f.chmod(0o755)
        self.repo = tmp_path / "repo"
        (self.repo / "infra" / "glorfindel-host").mkdir(parents=True)
        self.envrc = self.repo / ".envrc"
        self.envrc.write_text(envrc if envrc is not None else (
            "# the workstation's pairs\n"
            f"export GLORFINDEL_AZURE_CLIENT_ID={IDS['watch']}\n"
            "export GLORFINDEL_AZURE_CLIENT_SECRET='watch-OLD-never'\n"
            f"export EREGION_CONSOLE_AZURE_CLIENT_ID={IDS['console']}\n"
            f"export EREGION_CONSOLE_AZURE_CLIENT_SECRET='{OLD}'   # posé le 09/11\n"
            f"export AZURE_TENANT_ID={TENANT}\n"
            "export AZURE_CLIENT_ID=$GLORFINDEL_AZURE_CLIENT_ID\n"
            "export AZURE_CLIENT_SECRET=$GLORFINDEL_AZURE_CLIENT_SECRET\n"))
        self.envrc.chmod(mode)
        self.said: list[str] = []
        self.tokens: dict[str, str] = {}
        self.unusable: set[str] = set()      # values the token endpoint refuses (a secret that never connects)

    # the token endpoint and ARM, in-process: a token only for a secret the fake az holds
    def http(self, method, url, data=None, headers=None, timeout=30):
        with open(self.events, "a") as f:
            f.write(json.dumps({"who": "http", "method": method, "url": url,
                                "client_id": (data or {}).get("client_id")}) + "\n")
        st = json.loads(self.az_state.read_text())
        if method == "POST":
            held = st["apps"].get(data["client_id"], {})
            values = {s["value"] for o in held.values() for s in o["secrets"]}
            if data["client_secret"] in values and data["client_secret"] not in self.unusable \
                    and f"/{st['tenant']}/" in url:
                token = f"tok-{len(self.tokens)}"
                self.tokens[token] = data["client_id"]
                return 200, {"access_token": token}
            return 401, {"error": "invalid_client", "error_description": "AADSTS7000215 " + data["client_secret"]}
        token = (headers or {}).get("Authorization", "").removeprefix("Bearer ")
        return (200, {"value": []}) if token in self.tokens else (401, {})

    def env(self, **extra) -> dict:
        base = {k: v for k, v in os.environ.items()
                if "AZURE" not in k and k not in ("EREGION_AGENT_SESSION", "EREGION_HOST_SSH")}
        loaded = {"GLORFINDEL_AZURE_CLIENT_ID": IDS["watch"], "GLORFINDEL_AZURE_CLIENT_SECRET": "watch-OLD-never",
                  "EREGION_CONSOLE_AZURE_CLIENT_ID": IDS["console"], "EREGION_CONSOLE_AZURE_CLIENT_SECRET": OLD,
                  "AZURE_TENANT_ID": TENANT, "AZURE_CLIENT_ID": IDS["watch"], "AZURE_CLIENT_SECRET": "watch-OLD-never"}
        return {**base, **loaded, "PATH": f"{self.bin}{os.pathsep}{base.get('PATH', '')}",
                "FAKE_EVENTS": str(self.events), "FAKE_AZ_STATE": str(self.az_state),
                "FAKE_DOCKER_STATE": str(self.docker_state), "FAKE_IMLADRIS": str(self.imladris), **extra}

    def ctx(self, answer="o", tty=True, ssh="ssh -o StrictHostKeyChecking=yes glorfindel@192.0.2.10", **kw):
        return pr.Ctx(env=kw.pop("env", None) or self.env(), root=self.repo, az=str(self.bin / "az"), ssh=ssh, http=self.http,
                      ask=lambda _prompt: answer, say=self.said.append, now=NOW, sleep=lambda _s: None,
                      verify_s=20, step_s=10, tty=tty, cwd=self.tmp, here=self.tmp, **kw)

    def rotate(self, pair="console", days=90, **kw) -> int:
        return pr.rotate(pair, days, self.ctx(**kw))

    def calls(self, who=None) -> list[dict]:
        out = [json.loads(line) for line in self.events.read_text().splitlines() if line]
        return [c for c in out if who is None or c["who"] == who]

    def secrets(self, pair="console", obj="sp") -> list[dict]:
        return json.loads(self.az_state.read_text())["apps"][IDS[pair]][obj]["secrets"]

    def new_values(self) -> list[str]:
        st = json.loads(self.az_state.read_text())
        return [f"NEW~secret.{n}-never-shown" for n in range(1, st.get("drawn", 0) + 1)]

    def noted(self, pair="console") -> dict | None:
        p = self.imladris / ".eregion-cd" / "expiry" / f"{pair}.json"
        return json.loads(p.read_text()) if p.exists() else None


def _never_shown(w: World, *values: str) -> None:
    """Not on the screen, in no argv (az, docker, ssh), in nothing sent to Imladris, in no file
    of Imladris, in no URL."""
    said = "\n".join(w.said)
    for value in values:
        assert value not in said
        for c in w.calls():
            assert value not in json.dumps(c.get("argv", [])) and value not in c.get("stdin", "")
            assert value not in c.get("url", "")
        for f in w.imladris.rglob("*"):
            if f.is_file() and f.suffix in (".json", ".tmp", ""):
                assert value not in f.read_text(errors="replace")


# ── the rotation ─────────────────────────────────────────────────────────────────────

def test_a_rotation_adds_verifies_writes_restarts_removes_the_old_one_and_notes_the_end(tmp_path):
    w = World(tmp_path)
    before = w.envrc.read_text()
    assert w.rotate() == 0, w.said
    (new,) = w.new_values()
    # On Azure: the old one gone, the new one alone, on the object that held it (the console's SP).
    assert [s["value"] for s in w.secrets()] == [new]
    assert w.secrets("console", "app") == []
    assert w.secrets()[0]["end"] == "2027-02-10T09:00:00Z"            # 90 days, said explicitly
    # .envrc: the line rewritten, its comment kept, nothing else changed; its mode kept; no copy left.
    after = w.envrc.read_text()
    assert f"export EREGION_CONSOLE_AZURE_CLIENT_SECRET={pr.shlex.quote(new)}   # posé le 09/11\n" in after
    assert [ln for ln in after.splitlines() if "CONSOLE_AZURE_CLIENT_SECRET" not in ln] == \
        [ln for ln in before.splitlines() if "CONSOLE_AZURE_CLIENT_SECRET" not in ln]
    assert stat.S_IMODE(w.envrc.stat().st_mode) == 0o600
    assert not (w.repo / pr.BACKUP).exists() and not (w.repo / pr.TMP).exists()
    # The console recreated on the new value, by its environment; the watch untouched.
    ups = [c for c in w.calls("docker") if "up" in c["argv"]]
    assert [c["argv"][-1] for c in ups] == ["war-room"]
    assert ups[0]["env"]["EREGION_CONSOLE_AZURE_CLIENT_SECRET"] == new
    # Imladris: a date and the pair's name, 0600, and what its CD says of the reminders.
    assert w.noted() == {"pair": "console", "end": "2027-02-10T09:00:00Z", "noted_at": "2026-11-12T09:00:00Z",
                         "by": "pair-rotate"}
    assert stat.S_IMODE((w.imladris / ".eregion-cd" / "expiry" / "console.json").stat().st_mode) == 0o600
    assert any("rappels · console : fin le 2027-02-10" in s for s in w.said)
    _never_shown(w, OLD, new)


def test_the_old_secret_is_removed_only_after_the_new_one_is_verified_and_the_service_restarted(tmp_path):
    w = World(tmp_path)
    assert w.rotate() == 0, w.said
    calls = w.calls()
    at = {k: next(i for i, c in enumerate(calls) if f(c)) for k, f in {
        "reset": lambda c: c["who"] == "az" and c["argv"][2:4] == ["credential", "reset"],
        "token": lambda c: c["who"] == "http" and c["method"] == "POST",
        "arm": lambda c: c["who"] == "http" and c["method"] == "GET",
        "up": lambda c: c["who"] == "docker" and "up" in c["argv"],
        "delete": lambda c: c["who"] == "az" and c["argv"][2:4] == ["credential", "delete"],
        "note": lambda c: c["who"] == "ssh"}.items()}
    assert at["reset"] < at["token"] < at["arm"] < at["up"] < at["delete"] < at["note"]
    reset = next(c["argv"] for c in calls if c["who"] == "az" and "reset" in c["argv"])
    assert "--append" in reset and "--end-date" in reset                # never a reset that cuts at once
    deleted = [c["argv"][c["argv"].index("--key-id") + 1] for c in calls if "delete" in c.get("argv", [])]
    assert deleted == ["cccccccc-3333-4333-8333-000000000001"]           # the old one, by its key id, only it


def test_a_new_secret_that_does_not_connect_is_removed_and_nothing_else_moves(tmp_path):
    w = World(tmp_path)
    w.unusable.add("NEW~secret.1-never-shown")
    before = w.envrc.read_bytes()
    assert w.rotate() == 1
    assert [s["value"] for s in w.secrets()] == [OLD]                    # the old one stays, the new one gone
    assert w.envrc.read_bytes() == before
    assert not [c for c in w.calls("docker") if "up" in c["argv"]]
    assert not [c for c in w.calls("az") if "delete" in c["argv"] and "cccccccc-3333-4333-8333-000000000001" in c["argv"]]
    assert w.noted() is None
    assert "ne se connecte pas" in w.said[-1] and "l'ancien reste" in w.said[-1]
    tries = [c for c in w.calls("http") if c["method"] == "POST"]
    assert len(tries) == 3                                               # tried again while Entra propagates
    _never_shown(w, OLD, "NEW~secret.1-never-shown")


def test_a_service_that_does_not_restart_on_the_new_secret_puts_everything_back(tmp_path):
    w = World(tmp_path)
    st = json.loads(w.docker_state.read_text())
    st["refuse"] = ["NEW~secret.1-never-shown"]
    w.docker_state.write_text(json.dumps(st))
    before = w.envrc.read_bytes()
    assert w.rotate() == 1
    assert w.envrc.read_bytes() == before
    assert stat.S_IMODE(w.envrc.stat().st_mode) == 0o600
    assert [s["value"] for s in w.secrets()] == [OLD]
    ups = [c for c in w.calls("docker") if "up" in c["argv"]]
    assert [c["env"]["EREGION_CONSOLE_AZURE_CLIENT_SECRET"] for c in ups] == ["NEW~secret.1-never-shown", OLD]
    assert "war-room" in json.loads(w.docker_state.read_text())["running"]
    assert not (w.repo / pr.BACKUP).exists()
    assert w.noted() is None
    assert ".envrc remise comme avant" in w.said[-1] and "relancé(s) sur l'ancien secret" in w.said[-1]
    _never_shown(w, OLD, "NEW~secret.1-never-shown")


def test_a_failed_reset_changes_nothing(tmp_path):
    w = World(tmp_path)
    st = json.loads(w.az_state.read_text())
    st["fail_reset"] = True
    w.az_state.write_text(json.dumps(st))
    before = w.envrc.read_bytes()
    assert w.rotate() == 1
    assert w.envrc.read_bytes() == before and [s["value"] for s in w.secrets()] == [OLD]
    assert "az n'a pas rendu de nouveau secret" in w.said[-1]


@pytest.mark.parametrize("how", ["variable", "worktree"])
def test_refused_in_a_code_session_before_anything(tmp_path, how):
    w = World(tmp_path)
    ctx = w.ctx(env=w.env(EREGION_AGENT_SESSION="1")) if how == "variable" else w.ctx()
    if how == "worktree":
        ctx.cwd = tmp_path / ".claude" / "worktrees" / "lot"
        ctx.cwd.mkdir(parents=True)
    assert pr.rotate("console", 90, ctx) == 1
    assert pr.note("console", ctx) == 1
    assert w.calls() == []                                    # nothing read, nothing written
    assert len(w.said) == 2 and all("refusé" in s and "Rien n'est lu" in s for s in w.said)
    # make runs the guard alone first, on both targets
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in ("pair-rotate", "pair-expiry-note"):
        recipe = makefile.split(f"\n{target}:\n", 1)[1].split("\n\n", 1)[0].splitlines()
        assert recipe[0].strip() == "@$(PAIR_GUARD) $@"
        go = makefile.split(f"\n{target}-go:\n", 1)[1].split("\n\n", 1)[0].splitlines()
        assert go[0].strip() == f"@$(PAIR_GUARD) {target}"


def test_the_guard_alone_refuses_a_code_session(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("EREGION_AGENT_SESSION", "1")
    assert pr.main(["guard", "pair-rotate"]) == 1
    assert "refusé" in capsys.readouterr().err


def test_refused_without_a_terminal(tmp_path):
    w = World(tmp_path)
    assert w.rotate(tty=False) == 1
    assert w.calls() == [] and "sans terminal" in w.said[0]


def test_a_no_does_nothing(tmp_path):
    w = World(tmp_path)
    before = w.envrc.read_bytes()
    assert w.rotate(answer="") == 1
    assert w.envrc.read_bytes() == before
    assert not [c for c in w.calls("az") if "reset" in c["argv"]]
    plan = "\n".join(w.said)
    assert "sur son principal de service" in plan and "…0002 (masqué)" in plan and IDS["console"] not in plan
    assert "fin le 2027-02-10" in plan and "war-room" in plan and "restore lancé du poste" in plan
    _never_shown(w, OLD)


@pytest.mark.parametrize("days, said", [("", "pour 90 jours : fin le 2027-02-10"), ("30", "pour 30 jours : fin le 2026-12-12"),
                                        ("400", "DAYS=400 : de 1 à 365"), ("x", "DAYS=x")])
def test_the_duration_is_explicit_90_days_unless_days_says_otherwise(tmp_path, days, said):
    w = World(tmp_path)
    assert pr.main(["rotate", "console", "--days", days], ctx=w.ctx(answer="")) == 1   # « N »: nothing done
    assert any(said in s for s in w.said), w.said
    assert not [c for c in w.calls("az") if "reset" in c["argv"]]


@pytest.mark.parametrize("mode", [0o600, 0o640])
def test_the_rewritten_envrc_keeps_its_mode(tmp_path, mode):
    w = World(tmp_path, mode=mode)
    assert w.rotate() == 0, w.said
    assert stat.S_IMODE(w.envrc.stat().st_mode) == mode


def test_the_watch_s_copies_take_the_new_value_a_reference_is_left_as_it_is(tmp_path):
    envrc = (f"export GLORFINDEL_AZURE_CLIENT_ID={IDS['watch']}\n"
             "export GLORFINDEL_AZURE_CLIENT_SECRET=\"watch-OLD-never\"\n"
             f"export AZURE_TENANT_ID={TENANT}\n"
             f"export AZURE_CLIENT_ID={IDS['watch']}\n"
             "export AZURE_CLIENT_SECRET=watch-OLD-never\n"
             "export ANNATAR_AZURE_CLIENT_SECRET=$GLORFINDEL_AZURE_CLIENT_SECRET\n")
    w = World(tmp_path, envrc=envrc)
    assert w.rotate("watch") == 0, w.said
    (new,) = w.new_values()
    lines = w.envrc.read_text().splitlines()
    assert lines[1] == f"export GLORFINDEL_AZURE_CLIENT_SECRET={pr.shlex.quote(new)}"
    assert lines[4] == f"export AZURE_CLIENT_SECRET={pr.shlex.quote(new)}"
    assert lines[5] == "export ANNATAR_AZURE_CLIENT_SECRET=$GLORFINDEL_AZURE_CLIENT_SECRET"
    (up,) = [c for c in w.calls("docker") if "up" in c["argv"]]
    assert up["argv"][-1] == "watch"
    assert up["env"]["GLORFINDEL_AZURE_CLIENT_SECRET"] == new and up["env"]["AZURE_CLIENT_SECRET"] == new
    assert [s["value"] for s in w.secrets("watch", "app")] == [new]
    assert any("une watch lancée depuis le venv" in s for s in w.said)
    _never_shown(w, "watch-OLD-never", new)


def test_a_service_that_does_not_run_is_not_started(tmp_path):
    w = World(tmp_path, running=("watch",))
    assert w.rotate() == 0, w.said
    assert not [c for c in w.calls("docker") if "up" in c["argv"]]
    assert [s["value"] for s in w.secrets()] == w.new_values()


@pytest.mark.parametrize("case, said", [
    ("both", "sur son application et sur son principal de service"),
    ("none", "aucun secret"),
    ("unreadable", "ne se lit pas"),
])
def test_what_cannot_be_turned_safely_is_refused_before_anything(tmp_path, case, said):
    held = None
    if case == "both":
        held = {IDS["console"]: {
            "app": {"secrets": [{"keyId": "k-app", "end": "2027-01-01T00:00:00Z", "value": "other-never"}],
                    "certificates": []},
            "sp": {"secrets": [{"keyId": "k-sp", "end": "2026-12-08T10:00:00Z", "value": OLD}], "certificates": []}}}
    elif case == "none":
        held = {IDS["console"]: {"app": {"secrets": [], "certificates": []}, "sp": {"secrets": [], "certificates": []}}}
    w = World(tmp_path, held=held)
    if case == "unreadable":
        st = json.loads(w.az_state.read_text())
        st["unreadable"] = ["app"]
        w.az_state.write_text(json.dumps(st))
    before = w.envrc.read_bytes()
    assert w.rotate() == 1
    assert said in w.said[-1]
    assert not [c for c in w.calls("az") if "reset" in c["argv"] or "delete" in c["argv"]]
    assert w.envrc.read_bytes() == before


@pytest.mark.parametrize("envrc, said", [
    (f"export EREGION_CONSOLE_AZURE_CLIENT_ID={IDS['console']}\n# export EREGION_CONSOLE_AZURE_CLIENT_SECRET=x\n",
     "aucune ligne"),
    (f"export EREGION_CONSOLE_AZURE_CLIENT_ID={IDS['console']}\nexport EREGION_CONSOLE_AZURE_CLIENT_SECRET=$(pass x)\n",
     "pas une valeur écrite"),
    (f"export EREGION_CONSOLE_AZURE_CLIENT_ID={IDS['console']}\nEREGION_CONSOLE_AZURE_CLIENT_SECRET=a\n"
     "EREGION_CONSOLE_AZURE_CLIENT_SECRET=b\n", "2 lignes"),
])
def test_an_envrc_it_cannot_write_safely_is_refused(tmp_path, envrc, said):
    w = World(tmp_path, envrc=envrc)
    assert w.rotate() == 1
    assert said in w.said[-1]
    assert not [c for c in w.calls("az") if "reset" in c["argv"]]


def test_a_copy_left_by_an_interrupted_rotation_refuses(tmp_path):
    w = World(tmp_path)
    (w.repo / pr.BACKUP).write_text("x")
    assert w.rotate() == 1
    assert "interrompue" in w.said[-1] and w.calls() == []


def test_host_env_holding_the_secret_refuses(tmp_path):
    w = World(tmp_path)
    (w.repo / "infra" / "glorfindel-host" / "host.env").write_text(f"SOMETHING={OLD}\n")
    assert w.rotate() == 1
    assert "host.env" in w.said[-1]
    _never_shown(w, OLD)


def test_an_old_secret_that_will_not_go_is_said_and_the_end_still_noted(tmp_path):
    w = World(tmp_path)
    st = json.loads(w.az_state.read_text())
    st["fail_delete"] = ["cccccccc-3333-4333-8333-000000000001"]
    w.az_state.write_text(json.dumps(st))
    assert w.rotate() == 1
    assert any("ne se retire" in s for s in w.said)
    assert w.noted()["end"] == "2026-12-08T10:00:00Z"                    # the nearest still decides (PAIR1)


def test_imladris_out_of_reach_the_rotation_holds_and_says_what_to_type(tmp_path):
    w = World(tmp_path)
    assert w.rotate(ssh="") == 1
    assert [s["value"] for s in w.secrets()] == w.new_values()
    assert any("make pair-expiry-note PAIR=console" in s for s in w.said)


# ── the note of the end in place ─────────────────────────────────────────────────────

def test_the_note_reads_both_objects_and_writes_a_date_only_on_imladris(tmp_path):
    w = World(tmp_path)
    assert pr.note("console", w.ctx(tty=False)) == 0, w.said
    assert w.noted() == {"pair": "console", "end": "2026-12-08T10:00:00Z", "noted_at": "2026-11-12T09:00:00Z",
                         "by": "pair-expiry-note"}
    shows = [c["argv"][1] for c in w.calls("az")]
    assert shows == ["app", "sp"]                                         # PAIR1: both objects, nothing written
    assert "sur son principal de service" in w.said[0]
    assert any("J-14 le 2026-11-24" in s for s in w.said)
    (ssh,) = w.calls("ssh")
    assert json.loads(ssh["stdin"]) == w.noted()
    _never_shown(w, OLD)


def test_the_note_refuses_an_object_it_cannot_read(tmp_path):
    w = World(tmp_path)
    st = json.loads(w.az_state.read_text())
    st["unreadable"] = ["sp"]
    w.az_state.write_text(json.dumps(st))
    assert pr.note("console", w.ctx()) == 1
    assert "illisible sur son principal de service" in w.said[-1] and w.noted() is None


def test_the_note_without_the_cd_on_imladris_says_so(tmp_path):
    w = World(tmp_path, cd=False)
    assert pr.note("console", w.ctx()) == 1
    assert "son CD n'est pas installé" in w.said[-1]


def test_the_note_with_an_agent_from_before_rot1_says_to_update_it(tmp_path):
    w = World(tmp_path)
    old_agent = w.imladris / ".eregion-cd" / "eregion_cd.py"
    old_agent.write_text("import sys\nprint('usage')\nsys.exit(2)\n")
    assert pr.note("console", w.ctx()) == 1
    assert "make glorfindel-host-cd-install" in w.said[-1] and w.noted() is not None


# ── the reminders, on Imladris ───────────────────────────────────────────────────────

@pytest.fixture
def fake():
    f = FakeDiscord()
    yield f
    f.close()


def _agent(tmp_path, monkeypatch, fake):
    """The CD agent, loaded as on Imladris: its home in tmp_path, #deploy's webhook on the fake Discord."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    spec = importlib.util.spec_from_file_location(f"eregion_cd_rot1_{len(list(tmp_path.iterdir()))}", AGENT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cd = tmp_path / ".eregion-cd"
    cd.mkdir(exist_ok=True)
    (cd / "discord.env").write_text(f"EREGION_DISCORD_WEBHOOK_DEPLOY={fake.base}/api/webhooks/9/{HOOK}\n"
                                    "EREGION_DISCORD_MENTION=42\n")
    mod.CD_HOME, mod.HOME = cd, tmp_path
    return mod


def _note(tmp_path, pair="console", end="2026-12-08T10:00:00Z"):
    d = tmp_path / ".eregion-cd" / "expiry"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{pair}.json").write_text(json.dumps({"pair": pair, "end": end}))


def _posts(fake):
    return fake.webhook_posts(HOOK)


def test_the_reminders_leave_at_j14_j7_j1_and_on_the_day_once_per_tier_even_after_a_restart(tmp_path, monkeypatch,
                                                                                             fake):
    agent = _agent(tmp_path, monkeypatch, fake)
    _note(tmp_path)
    end = datetime(2026, 12, 8, 10, tzinfo=timezone.utc)
    sent_at = []
    for days_before in range(20, -3, -1):
        for hour in (0, 12):                       # several passes a day (every 5 minutes, in truth)
            if days_before == 10 and hour == 12:   # a reboot: the agent loaded again, its state from disk
                agent = _agent(tmp_path, monkeypatch, fake)
            n = len(_posts(fake))
            agent.reminders(now=(end - timedelta(days=days_before)).replace(hour=hour))
            if len(_posts(fake)) > n:
                sent_at.append(days_before)
    assert sent_at == [14, 7, 1, 0]
    titles = [p["embeds"][0]["title"] for p in _posts(fake)]
    assert titles[0] == "🔑 Le secret de la paire « console » expire dans 14 jours, le 2026-12-08"
    assert titles[2:] == ["🔑 Le secret de la paire « console » expire demain, le 2026-12-08",
                          "🔑 Le secret de la paire « console » expire aujourd'hui, le 2026-12-08"]
    for p in _posts(fake):
        assert p["content"] == "<@42>" and p["allowed_mentions"] == {"parse": [], "users": ["42"]}
        assert "`make pair-rotate PAIR=console`" in p["embeds"][0]["description"]


def test_a_date_noted_late_sends_the_tier_it_is_in_never_the_ones_it_passed(tmp_path, monkeypatch, fake):
    agent = _agent(tmp_path, monkeypatch, fake)
    _note(tmp_path)
    agent.reminders(now=datetime(2026, 12, 3, 8, tzinfo=timezone.utc))        # J-5
    agent.reminders(now=datetime(2026, 12, 4, 8, tzinfo=timezone.utc))
    assert [p["embeds"][0]["title"] for p in _posts(fake)] == \
        ["🔑 Le secret de la paire « console » expire dans 5 jours, le 2026-12-08"]
    agent.reminders(now=datetime(2026, 12, 7, 8, tzinfo=timezone.utc))        # J-1
    assert len(_posts(fake)) == 2


def test_a_new_end_after_a_rotation_starts_its_tiers_over(tmp_path, monkeypatch, fake):
    agent = _agent(tmp_path, monkeypatch, fake)
    _note(tmp_path)
    agent.reminders(now=datetime(2026, 11, 24, 8, tzinfo=timezone.utc))       # J-14 sent
    _note(tmp_path, end="2027-02-10T09:00:00Z")                                # turned: a new end
    agent.reminders(now=datetime(2026, 11, 25, 8, tzinfo=timezone.utc))
    assert len(_posts(fake)) == 1
    agent.reminders(now=datetime(2027, 1, 27, 8, tzinfo=timezone.utc))        # J-14 of the new end
    assert len(_posts(fake)) == 2 and "2027-02-10" in _posts(fake)[-1]["embeds"][0]["title"]


def test_a_reminder_discord_refuses_is_tried_again_at_the_next_pass(tmp_path, monkeypatch, fake):
    agent = _agent(tmp_path, monkeypatch, fake)
    _note(tmp_path)
    fake.fail["/api/webhooks/"] = 500
    agent.reminders(now=datetime(2026, 11, 24, 8, tzinfo=timezone.utc))
    assert _posts(fake) and fake.messages == {}                              # tried, refused
    assert not (tmp_path / ".eregion-cd" / "reminders.json").exists()       # not marked sent
    fake.fail.clear()
    agent.reminders(now=datetime(2026, 11, 24, 8, 5, tzinfo=timezone.utc))
    agent.reminders(now=datetime(2026, 11, 24, 8, 10, tzinfo=timezone.utc))
    assert len(fake.messages) == 1


def test_the_timer_s_pass_sends_the_reminders_before_the_release(tmp_path, monkeypatch, fake):
    agent = _agent(tmp_path, monkeypatch, fake)
    monkeypatch.setattr(agent, "API", f"{fake.base}/gh")
    monkeypatch.setattr(agent, "SLUG", "o/r")
    _note(tmp_path, end=(datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    assert agent.main(["run"]) == 0                     # no release published: the pass has nothing else to do
    (post,) = _posts(fake)
    assert "expire dans 3 jours" in post["embeds"][0]["title"]


def test_an_unreadable_note_is_said_never_guessed(tmp_path, monkeypatch, fake, capsys):
    agent = _agent(tmp_path, monkeypatch, fake)
    _note(tmp_path, end="bientôt")
    assert agent.reminders(now=NOW) == ["  rappels · console : date de fin illisible (~/.eregion-cd/expiry/console.json)"]
    assert _posts(fake) == []
    assert agent.main(["reminders"]) == 0
    assert "illisible" in capsys.readouterr().out


# ── the documents ────────────────────────────────────────────────────────────────────

def test_the_targets_are_phony_helped_and_the_rotation_s_doc_is_written_around_them():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    phony = makefile.split(".PHONY:", 1)[1].split("\n\n", 1)[0]
    helped = makefile.split("\nhelp:\n", 1)[1]
    for target in ("pair-rotate", "pair-expiry-note"):
        assert target in phony and f"make {target} PAIR=" in helped
    ops = (ROOT / "docs" / "operations.md").read_text(encoding="utf-8")
    rotation = ops.split("**Faire tourner un secret**", 1)[1].split("\n**Retirer l'ancien principal partagé**", 1)[0]
    for said in ("make pair-rotate PAIR=console", "make pair-expiry-note PAIR=console", "--append", "#deploy",
                 "J-14", "n'est pas vue", "make glorfindel-host-cd-install"):
        assert said in rotation, said
    readme = (ROOT / "infra" / "glorfindel-host" / "README.md").read_text(encoding="utf-8")
    assert "ROT1 change l'agent" in readme
    # The reader of the bench is checked on both objects now (relevé par la relecture de PAIR1).
    assert "az ad app credential list --id <client_id> -o table" not in ops


def test_the_cd_never_holds_a_secret_of_a_pair_only_its_date():
    src = AGENT.read_text(encoding="utf-8")
    reminders = src.split("# ── the reminders of the pairs' secrets", 1)[1].split("# ── the pass", 1)[0]
    assert "CLIENT_SECRET" not in reminders and "CLIENT_ID" not in reminders
    assert subprocess.run([sys.executable, str(ROOT / "scripts" / "identity_map.py"), "check"],
                          capture_output=True, text=True, cwd=ROOT).returncode == 0
