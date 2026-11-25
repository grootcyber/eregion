"""ROT2 (#968): the console token of Imladris turned in one command, `make imladris-console-rotate`,
and the day to turn it again reminded in #deploy, like the pairs' secrets (ROT1).

On fakes only, in tmp_path — no Imladris, no ssh, no Discord:
  - a fake `ssh` that runs the remote command by bash in a fake home of Imladris, where the real CD
    agent (infra/glorfindel-host/cd/eregion_cd.py) is installed as `make imladris-cd-install` puts it,
    and a fake `scp` that copies into it;
  - on that fake Imladris, a fake `docker` (`compose up … war-room` makes the console read ~/eregion/.env
    again, as compose recreating it does) and a fake `curl` that answers as the console does: 200 for
    the token it runs with, 401 for any other, 000 when it does not run;
  - a fake push (the function-level tests) or the real `make imladris-push` (one test, from a copy of
    the checkout, its host key pinned by a throwaway key);
  - host.env factices, written here; the fake Discord (tests/unit/fake_discord.py) for #deploy.
Held here: only the token's line changes; 0600 and an atomic write; the token never on the screen nor
in an argv; refused in a code session, on a host.env without a token, before anything; the console
alone restarted, the old token refused after; the day noted; the reminders at their tiers.
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
import console_rotate as cr  # noqa: E402

AGENT = ROOT / "infra" / "glorfindel-host" / "cd" / "eregion_cd.py"
OLD = "OLD-console_token-never-shown-0123456789"
NOW = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
IP = "192.0.2.10"
HOOK = "HOOK-TOKEN-never-shown"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash needed")

# A host.env as Imladris's is: comments, blanks, quotes, a value with a « # » after a blank, the
# former name of the token, a last line without its line break.
HOST_ENV = (
    "# Imladris — written by make imladris-env\n"
    "AZURE_SUBSCRIPTION_ID=00000000-0000-4000-8000-000000000000\n"
    "GLORFINDEL_LLM_MODEL=anthropic/claude-test\n"
    "ANTHROPIC_API_KEY=\"model-key-kept\"   # posé le 15/10\n"
    "\n"
    "GLORFINDEL_READ_ONLY=1\r\n"
    f"GLORFINDEL_WARROOM_TOKEN={OLD}\n"
    "DISCORD_ALLOWED_USERS=42  \n"
    "GLORFINDEL_DISCOVERY_RETENTION_H=168")

_FAKE_SSH = r'''#!PYTHON
"""A fake ssh to Imladris: the remote command run by bash in $FAKE_IMLADRIS, its stdin given."""
import json, os, subprocess, sys
args = sys.argv[1:]
data = "" if sys.stdin is None or sys.stdin.isatty() else sys.stdin.read()
with open(os.environ["FAKE_EVENTS"], "a") as f:
    f.write(json.dumps({"who": "ssh", "argv": args, "stdin": data}) + "\n")
home = os.environ["FAKE_IMLADRIS"]
env = {"PATH": os.environ["FAKE_IMLADRIS_BIN"] + os.pathsep + os.environ["PATH"], "HOME": home,
       "FAKE_EVENTS": os.environ["FAKE_EVENTS"], "FAKE_DOCKER_FAIL": os.environ.get("FAKE_DOCKER_FAIL", ""),
       "FAKE_STALE": os.environ.get("FAKE_STALE", "")}
res = subprocess.run(["bash", "-c", args[-1]], cwd=home, input=data, text=True, env=env, capture_output=True)
sys.stdout.write(res.stdout); sys.stderr.write(res.stderr)
sys.exit(res.returncode)
'''

_FAKE_SCP = r'''#!PYTHON
"""A fake scp to Imladris: the last two arguments, a local file and user@host:path."""
import json, os, shutil, sys
args = sys.argv[1:]
with open(os.environ["FAKE_EVENTS"], "a") as f:
    f.write(json.dumps({"who": "scp", "argv": args}) + "\n")
src, dst = args[-2], args[-1].split(":", 1)[1]
shutil.copy(src, os.path.join(os.environ["FAKE_IMLADRIS"], dst))
'''

_FAKE_PUSH = r'''#!PYTHON
"""make imladris-push, faked: host.env checked as the push checks it, then copied to ~/eregion/.env."""
import json, os, shutil, sys
with open(os.environ["FAKE_EVENTS"], "a") as f:
    f.write(json.dumps({"who": "push", "argv": sys.argv[1:]}) + "\n")
if os.environ.get("FAKE_PUSH_FAIL"):
    sys.exit(2)
shutil.copy("infra/glorfindel-host/host.env", os.path.join(os.environ["FAKE_IMLADRIS"], "eregion", ".env"))
'''

# On the fake Imladris: compose recreating the console makes it read ~/eregion/.env (the console's rule:
# the new name when not empty, else the former; the last line of a key wins).
_FAKE_DOCKER = r'''#!PYTHON
import json, os, re, sys
args = sys.argv[1:]
with open(os.environ["FAKE_EVENTS"], "a") as f:
    f.write(json.dumps({"who": "docker", "argv": args}) + "\n")
if os.environ.get("FAKE_DOCKER_FAIL"):
    sys.exit(1)
if "up" in args and args[-1] == "war-room" and not os.environ.get("FAKE_STALE"):
    env = {}
    for line in open(".env", encoding="utf-8").read().splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            v = re.sub(r"\s+#.*$", "", v.strip()).strip()
            env[k.strip()] = v[1:-1] if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'" else v
    token = env.get("EREGION_CONSOLE_TOKEN") or env.get("GLORFINDEL_WARROOM_TOKEN") or ""
    open(os.path.join(os.environ["HOME"], ".console-running"), "w").write(token)
'''

_FAKE_CURL = r'''#!PYTHON
"""The console behind 127.0.0.1:7007, as curl -w '%{http_code}' -H @- reads it: 200 for its token."""
import json, os, sys
args = sys.argv[1:]
header = sys.stdin.read() if "@-" in args else ""
with open(os.environ["FAKE_EVENTS"], "a") as f:
    f.write(json.dumps({"who": "curl", "argv": args}) + "\n")
running = os.path.join(os.environ["HOME"], ".console-running")
if not os.path.exists(running):
    print("000", end=""); sys.exit(7)
token = header.strip().removeprefix("Authorization: Bearer ")
print("200" if token and token == open(running).read() else "401", end="")
'''


@pytest.fixture(autouse=True)
def only_fakes_on_the_path(tmp_path, monkeypatch):
    """Whatever runs a tool by its name finds the fake first — never a real ssh, scp or docker."""
    (tmp_path / "bin").mkdir()
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}")


def _script(path: Path, body: str) -> None:
    path.write_text(body.replace("PYTHON", sys.executable))
    path.chmod(0o755)


class World:
    """The fakes of one test: the workstation's host.env, Imladris with its console and its CD."""

    def __init__(self, tmp_path: Path, host_env: str | bytes | None = HOST_ENV, mode: int = 0o600, cd: bool = True,
                 repo: Path | None = None):
        self.tmp = tmp_path
        self.bin = tmp_path / "bin"
        self.bin.mkdir(exist_ok=True)
        self.events = tmp_path / "events.jsonl"
        self.events.write_text("")
        self.imladris = tmp_path / "imladris"
        (self.imladris / "eregion").mkdir(parents=True)
        self.imladris_bin = tmp_path / "imladris-bin"
        self.imladris_bin.mkdir()
        for name, body in (("docker", _FAKE_DOCKER), ("curl", _FAKE_CURL)):
            _script(self.imladris_bin / name, body)
        _script(self.imladris_bin / "sleep", "#!PYTHON\n")          # the probe's wait, at once
        if cd:
            cd_home = self.imladris / ".eregion-cd"
            cd_home.mkdir(mode=0o700)
            for src in (AGENT, ROOT / "scripts" / "notify_discord.py", ROOT / "glorfindel" / "chat_text.py",
                        ROOT / "scripts" / "published_image.py"):
                shutil.copy(src, cd_home / src.name)
        for name, body in (("ssh", _FAKE_SSH), ("scp", _FAKE_SCP), ("fake-push", _FAKE_PUSH)):
            _script(self.bin / name, body)
        self.repo = repo or tmp_path / "repo"
        self.host_env = self.repo / "infra" / "glorfindel-host" / "host.env"
        self.host_env.parent.mkdir(parents=True, exist_ok=True)
        if host_env is not None:
            (self.host_env.write_bytes if isinstance(host_env, bytes) else self.host_env.write_text)(host_env)
            self.host_env.chmod(mode)
            shutil.copy(self.host_env, self.imladris / "eregion" / ".env")
        (self.imladris / ".console-running").write_text(OLD)          # the console runs on the old token
        self.said: list[str] = []

    def env(self, **extra) -> dict:
        base = {k: v for k, v in os.environ.items() if k not in ("EREGION_AGENT_SESSION", "EREGION_HOST_SSH",
                                                                 "EREGION_PUSH")}
        return {**base, "FAKE_EVENTS": str(self.events), "FAKE_IMLADRIS": str(self.imladris),
                "FAKE_IMLADRIS_BIN": str(self.imladris_bin), **extra}

    def ctx(self, ssh=f"ssh -o StrictHostKeyChecking=yes glorfindel@{IP}", push=None, **kw):
        kw = {"cwd": self.tmp, "here": self.tmp, **kw}
        return cr.Ctx(env=kw.pop("env", None) or self.env(), root=self.repo, ssh=ssh,
                      push=str(self.bin / "fake-push") if push is None else push, say=self.said.append, now=NOW,
                      **kw)

    def text(self) -> str:
        """host.env as it is, its line endings kept (read_text would turn a CRLF into a LF)."""
        return self.host_env.read_bytes().decode("utf-8")

    def rotate(self, days="", **kw) -> int:
        return cr.rotate(days, self.ctx(**kw))

    def calls(self, who=None) -> list[dict]:
        out = [json.loads(line) for line in self.events.read_text().splitlines() if line]
        return [c for c in out if who is None or c["who"] == who]

    def token(self) -> str:
        env = cr.he.read_env(self.host_env)
        return env.get("EREGION_CONSOLE_TOKEN", "")

    def noted(self) -> dict | None:
        p = self.imladris / ".eregion-cd" / "expiry" / "console-token.json"
        return json.loads(p.read_text()) if p.exists() else None


def _never_shown(w: World, *values: str) -> None:
    """Not on the screen, in no argv (ssh, scp, docker, curl, the push), in no file of Imladris but its .env."""
    said = "\n".join(w.said)
    for value in values:
        assert value and value not in said
        for c in w.calls():
            assert value not in json.dumps(c.get("argv", []))
        for f in (w.imladris / ".eregion-cd").rglob("*"):
            if f.is_file():
                assert value not in f.read_text(errors="replace")


def _others(text: str) -> list[str]:
    """Every line of host.env but the token's, to the byte (line endings kept)."""
    return [ln for ln in text.splitlines(keepends=True) if cr._key(ln) not in (cr.he.TOKEN, cr.he.LEGACY_TOKEN)]


# ── the rotation ─────────────────────────────────────────────────────────────────────

def test_a_rotation_changes_the_token_s_line_alone_restarts_the_console_alone_and_refuses_the_old_one(tmp_path):
    w = World(tmp_path)
    before = w.text()
    assert w.rotate() == 0, w.said
    new = w.token()
    drawn = cr.he.host_env({"AZURE_SUBSCRIPTION_ID": "s", "ANTHROPIC_API_KEY": "k"})[cr.he.TOKEN]
    assert new and new != OLD and len(new) == len(drawn)            # the form make imladris-env draws
    # host.env: the token's line alone, at its place, under the new name; every other line to the byte.
    after = w.text()
    assert "GLORFINDEL_READ_ONLY=1\r\n" in after
    assert _others(after) == _others(before)
    assert after.splitlines()[6] == f"EREGION_CONSOLE_TOKEN={new}"
    assert "GLORFINDEL_WARROOM_TOKEN" not in after
    assert after.endswith("GLORFINDEL_DISCOVERY_RETENTION_H=168")
    assert stat.S_IMODE(w.host_env.stat().st_mode) == 0o600
    assert not (w.host_env.parent / cr.TMP).exists()
    # Pushed, then the console alone recreated — the watch and the bot untouched.
    assert (w.imladris / "eregion" / ".env").read_bytes().decode() == after
    whos = [c["who"] for c in w.calls() if c["who"] in ("push", "docker", "curl")]
    assert whos[0] == "push" and "docker" in whos and whos.index("docker") < whos.index("curl")
    (up,) = w.calls("docker")
    assert up["argv"] == ["compose", "up", "-d", "--no-deps", "--force-recreate", "war-room"]
    assert (w.imladris / ".eregion-deploy.lock").exists()        # taken, as deploy.sh takes it
    # The console answers the new one, refuses the old one (read on Imladris, the tokens on stdin).
    assert (w.imladris / ".console-running").read_text() == new
    assert any("accepte le nouveau jeton et refuse l'ancien" in s for s in w.said)
    probe = [c for c in w.calls("ssh") if c["argv"][-1] == cr.PROBE]
    assert len(probe) == 1 and probe[0]["stdin"] == f"{new}\n{OLD}\n"
    # The day to turn it again, on Imladris: 90 days after the draw, its name and a date only.
    assert w.noted() == {"pair": "console-token", "end": "2027-02-18T09:00:00Z", "noted_at": "2026-11-20T09:00:00Z",
                         "by": "imladris-console-rotate"}
    assert stat.S_IMODE((w.imladris / ".eregion-cd" / "expiry" / "console-token.json").stat().st_mode) == 0o600
    assert any("à faire tourner le 2027-02-18" in s for s in w.said)
    assert any("rappels · console-token" in s and "J-14 le 2027-02-04" in s for s in w.said)
    assert any("make imladris-url" in s for s in w.said)
    _never_shown(w, OLD, new)


def test_the_token_under_its_new_name_beside_the_former_takes_the_new_and_the_former_goes(tmp_path):
    text = (f"GLORFINDEL_WARROOM_TOKEN=older-one\nANTHROPIC_API_KEY=k\nEREGION_CONSOLE_TOKEN=first\n"
            f"# EREGION_CONSOLE_TOKEN=a-comment-stays\nEREGION_CONSOLE_TOKEN={OLD}   # posé le 01/11\nX=1\n")
    w = World(tmp_path, host_env=text)
    assert w.rotate() == 0, w.said
    after = w.host_env.read_text()
    assert after == ("ANTHROPIC_API_KEY=k\n# EREGION_CONSOLE_TOKEN=a-comment-stays\n"
                     f"EREGION_CONSOLE_TOKEN={w.token()}\nX=1\n")


def test_an_empty_new_name_and_the_token_under_the_former_one(tmp_path):
    w = World(tmp_path, host_env=f"EREGION_CONSOLE_TOKEN=\nANTHROPIC_API_KEY=k\nGLORFINDEL_WARROOM_TOKEN={OLD}\n")
    assert w.rotate() == 0, w.said
    assert w.host_env.read_text() == f"ANTHROPIC_API_KEY=k\nEREGION_CONSOLE_TOKEN={w.token()}\n"
    assert any("ancien nom GLORFINDEL_WARROOM_TOKEN retiré" in s for s in w.said)


@pytest.mark.parametrize("mode", [0o600, 0o644])
def test_host_env_is_written_0600_whatever_it_was(tmp_path, mode):
    w = World(tmp_path, mode=mode)
    assert w.rotate() == 0, w.said
    assert stat.S_IMODE(w.host_env.stat().st_mode) == 0o600


def test_a_write_cut_short_leaves_host_env_as_it_was_and_no_temporary_file(tmp_path, monkeypatch):
    w = World(tmp_path)
    before = w.host_env.read_bytes()

    def cut(*_a):
        raise KeyboardInterrupt
    monkeypatch.setattr(cr.os, "replace", cut)
    with pytest.raises(KeyboardInterrupt):
        w.rotate()
    assert w.host_env.read_bytes() == before
    assert not (w.host_env.parent / cr.TMP).exists()
    assert w.calls() == []


def test_a_host_env_the_push_would_refuse_is_never_written(tmp_path):
    """The new host.env checked as `make imladris-push` checks it, before it replaces the old one: here
    the model's key is missing — the check refuses, nothing is replaced, nothing pushed."""
    text = HOST_ENV.replace('ANTHROPIC_API_KEY="model-key-kept"   # posé le 15/10\n', "")
    w = World(tmp_path, host_env=text)
    assert w.rotate() == 1
    assert w.text() == text
    assert not (w.host_env.parent / cr.TMP).exists()
    assert "host_env.py --check" in w.said[-1] and "ANTHROPIC_API_KEY" in w.said[-1]
    assert str(cr.TMP) not in w.said[-1]
    assert w.calls() == []


def test_a_temporary_file_left_by_an_interrupted_run_is_replaced(tmp_path):
    w = World(tmp_path)
    (w.host_env.parent / cr.TMP).write_text("EREGION_CONSOLE_TOKEN=left-over\n")
    assert w.rotate() == 0, w.said
    assert not (w.host_env.parent / cr.TMP).exists()


def test_a_quoted_token_is_probed_as_the_console_receives_it(tmp_path):
    """compose removes one pair of quotes: the old token the probe sends is the one the console runs with,
    never with its quotes — else « the old one refused » would hold for a value nobody uses."""
    w = World(tmp_path, host_env=HOST_ENV.replace(f"GLORFINDEL_WARROOM_TOKEN={OLD}",
                                                  f'EREGION_CONSOLE_TOKEN="{OLD}"'))
    assert w.rotate() == 0, w.said
    (probe,) = [c for c in w.calls("ssh") if c["argv"][-1] == cr.PROBE]
    assert probe["stdin"] == f"{w.token()}\n{OLD}\n"


def test_a_deployment_in_progress_refuses_the_restart_and_leaves_the_new_token_to_push_again(tmp_path):
    """The CD holds ~/.eregion-deploy.lock for its pass (deploy.sh, `lock`): the console is never
    recreated in the middle of a switch — refused, said, nothing noted."""
    import fcntl
    w = World(tmp_path)
    with open(w.imladris / ".eregion-deploy.lock", "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        assert w.rotate() == 1
    assert "un déploiement est en cours" in w.said[-1] and "make imladris-console-rotate" in w.said[-1]
    assert w.calls("docker") == [] and w.noted() is None
    assert w.token() and w.token() != OLD                          # host.env holds the new one, to push again


def test_the_temporary_host_env_is_ignored_by_git(tmp_path):
    """The repository is public: the file written beside host.env holds all of it, until it is renamed —
    a SIGKILL there leaves it in the checkout. Read in a throwaway repository with the .gitignore of this
    tree (the mutation harness copies the tree without its .git)."""
    if shutil.which("git") is None:
        pytest.skip("git needed")
    repo = tmp_path / "ignore"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    shutil.copy(ROOT / ".gitignore", repo / ".gitignore")
    rel = f"infra/glorfindel-host/{cr.TMP}"
    assert subprocess.run(["git", "check-ignore", "-q", rel], cwd=repo).returncode == 0
    assert cr.HOST_ENV.parent.as_posix() == "infra/glorfindel-host"


# ── what refuses before anything ─────────────────────────────────────────────────────

@pytest.mark.parametrize("how", ["env", "worktree"])
def test_refused_in_a_code_session_before_anything(tmp_path, how):
    w = World(tmp_path)
    before = w.host_env.read_bytes()
    if how == "env":
        ctx = w.ctx(env=w.env(EREGION_AGENT_SESSION="1"))
    else:
        wt = tmp_path / ".claude" / "worktrees" / "lot"
        wt.mkdir(parents=True)
        ctx = w.ctx(cwd=wt)
    assert cr.rotate("", ctx) == 1
    assert "refusé" in w.said[-1] and "Rien n'est lu, rien n'est écrit" in w.said[-1]
    assert w.host_env.read_bytes() == before and w.calls() == []
    assert cr.note("", w.ctx(env=w.env(EREGION_AGENT_SESSION="1"))) == 1 and w.noted() is None


def test_the_guard_alone_refuses_a_code_session(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("EREGION_AGENT_SESSION", "1")
    assert cr.main(["guard", "imladris-console-rotate"]) == 1
    assert "make imladris-console-rotate refusé" in capsys.readouterr().err


@pytest.mark.parametrize("host_env, said", [
    (None, "host.env manquant"),
    ("AZURE_SUBSCRIPTION_ID=s\nGLORFINDEL_READ_ONLY=1\n", "aucun jeton de la console"),
    ("EREGION_CONSOLE_TOKEN=\nGLORFINDEL_WARROOM_TOKEN=\n", "aucun jeton de la console"),
    ("# EREGION_CONSOLE_TOKEN=only-a-comment\n", "aucun jeton de la console"),
    (b"EREGION_CONSOLE_TOKEN=\xff\xfe\n", "illisible"),
])
def test_a_host_env_without_a_token_or_unreadable_refuses_before_anything(tmp_path, host_env, said):
    w = World(tmp_path, host_env=host_env)
    before = w.host_env.read_bytes() if w.host_env.exists() else None
    assert w.rotate() == 1
    assert said in w.said[-1], w.said
    assert (w.host_env.read_bytes() if w.host_env.exists() else None) == before
    assert w.calls() == [] and not (w.host_env.parent / cr.TMP).exists()


def test_imladris_out_of_reach_refuses_before_anything(tmp_path):
    w = World(tmp_path)
    before = w.host_env.read_bytes()
    assert w.rotate(ssh="") == 1
    assert "Imladris injoignable" in w.said[-1] and "rien n'est tiré" in w.said[-1]
    assert w.host_env.read_bytes() == before and w.calls() == []


@pytest.mark.parametrize("days", ["0", "366", "trois"])
def test_days_out_of_bounds_refuses(tmp_path, days):
    w = World(tmp_path)
    assert w.rotate(days=days) == 1 and w.calls() == []


def test_days_sets_the_day_to_turn_it_again(tmp_path):
    w = World(tmp_path)
    assert w.rotate(days="30") == 0, w.said
    assert w.noted()["end"] == (NOW + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── a failure after the write ────────────────────────────────────────────────────────

def test_a_push_that_fails_leaves_the_new_token_on_the_workstation_and_says_what_to_type(tmp_path):
    w = World(tmp_path)
    assert w.rotate(env=w.env(FAKE_PUSH_FAIL="1")) == 1
    new = w.token()
    assert new and new != OLD
    assert cr._checked(w.host_env, w.host_env) == ""              # host.env coherent: the push would take it
    assert "la pose a échoué" in w.said[-1] and "make imladris-console-rotate" in w.said[-1]
    assert "accepte encore l'ancien" in w.said[-1]
    assert w.calls("docker") == [] and w.noted() is None
    assert (w.imladris / ".console-running").read_text() == OLD
    _never_shown(w, OLD, new)


def test_a_restart_that_fails_is_said_and_nothing_noted(tmp_path):
    w = World(tmp_path)
    assert w.rotate(env=w.env(FAKE_DOCKER_FAIL="1")) == 1
    assert "ne redémarre pas" in w.said[-1] and w.noted() is None


def test_a_console_still_on_the_old_token_is_said_and_nothing_noted(tmp_path):
    """The restart answered, but the console kept its environment: the new token refused, the old one
    accepted — said, never taken for a rotation."""
    w = World(tmp_path)
    assert w.rotate(env=w.env(FAKE_STALE="1")) == 1
    assert "ne répond pas comme attendu" in w.said[-1] and "le nouveau : 401, l'ancien : 200" in w.said[-1]
    assert w.noted() is None


# ── the note of the token in place ───────────────────────────────────────────────────

def test_the_note_writes_the_day_on_imladris_and_turns_nothing(tmp_path):
    w = World(tmp_path)
    before = w.host_env.read_bytes()
    assert cr.note("", w.ctx()) == 0, w.said
    assert w.noted() == {"pair": "console-token", "end": "2027-02-18T09:00:00Z", "noted_at": "2026-11-20T09:00:00Z",
                         "by": "imladris-console-token-note"}
    assert w.host_env.read_bytes() == before
    assert [c["who"] for c in w.calls()] == ["ssh"]               # the note, nothing else
    assert any("J-14 le 2027-02-04" in s for s in w.said)
    _never_shown(w, OLD)


def test_the_note_without_a_token_refuses(tmp_path):
    w = World(tmp_path, host_env="AZURE_SUBSCRIPTION_ID=s\n")
    assert cr.note("", w.ctx()) == 1 and w.calls() == [] and w.noted() is None


def test_the_note_without_the_cd_on_imladris_says_so(tmp_path):
    w = World(tmp_path, cd=False)
    assert cr.note("", w.ctx()) == 1
    assert "son CD n'est pas installé" in w.said[-1] and "make imladris-console-token-note" in w.said[-1]


def test_an_agent_from_before_rot2_is_said_the_date_noted(tmp_path):
    """The agent of ROT1 reads the three pairs only: the date is written, no reminder would leave — said."""
    w = World(tmp_path)
    agent = w.imladris / ".eregion-cd" / "eregion_cd.py"
    agent.write_text(agent.read_text().replace(
        'REMIND_PAIRS = ("watch", "console", "bot", CONSOLE_TOKEN)', 'REMIND_PAIRS = ("watch", "console", "bot")'))
    assert cr.note("", w.ctx()) == 1
    assert "d'avant ROT2" in w.said[-1] and "make imladris-cd-install" in w.said[-1]
    assert w.noted() is not None


# ── the reminders, on Imladris ───────────────────────────────────────────────────────

@pytest.fixture
def fake():
    f = FakeDiscord()
    yield f
    f.close()


def _agent(tmp_path, monkeypatch, fake):
    """The CD agent, loaded as on Imladris: its home in tmp_path, #deploy's webhook on the fake Discord."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    spec = importlib.util.spec_from_file_location(f"eregion_cd_rot2_{len(list(tmp_path.iterdir()))}", AGENT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cd = tmp_path / ".eregion-cd"
    cd.mkdir(exist_ok=True)
    (cd / "discord.env").write_text(f"EREGION_DISCORD_WEBHOOK_DEPLOY={fake.base}/api/webhooks/9/{HOOK}\n"
                                    "EREGION_DISCORD_MENTION=42\n")
    mod.CD_HOME, mod.HOME, mod.REPO = cd, tmp_path, tmp_path / "no-repository"
    return mod


def test_the_token_s_reminders_leave_at_j14_j7_j1_and_on_the_day_once_each(tmp_path, monkeypatch, fake):
    agent = _agent(tmp_path, monkeypatch, fake)
    d = tmp_path / ".eregion-cd" / "expiry"
    d.mkdir(parents=True)
    (d / "console-token.json").write_text(json.dumps({"pair": "console-token", "end": "2027-02-18T09:00:00Z"}))
    end = datetime(2027, 2, 18, 9, tzinfo=timezone.utc)
    sent_at = []
    for days_before in range(20, -3, -1):
        for hour in (0, 12):
            n = len(fake.webhook_posts(HOOK))
            agent.reminders(now=(end - timedelta(days=days_before)).replace(hour=hour))
            if len(fake.webhook_posts(HOOK)) > n:
                sent_at.append(days_before)
    assert sent_at == [14, 7, 1, 0]
    posts = fake.webhook_posts(HOOK)
    titles = [p["embeds"][0]["title"] for p in posts]
    assert titles == ["🔑 Le jeton de la console d'Imladris est à faire tourner dans 14 jours, le 2027-02-18",
                      "🔑 Le jeton de la console d'Imladris est à faire tourner dans 7 jours, le 2027-02-18",
                      "🔑 Le jeton de la console d'Imladris est à faire tourner demain, le 2027-02-18",
                      "🔑 Le jeton de la console d'Imladris est à faire tourner aujourd'hui, le 2027-02-18"]
    for p in posts:
        text = p["embeds"][0]["description"]
        assert p["content"] == "<@42>"
        assert "`make imladris-console-rotate`" in text and "`make imladris-console-token-note`" in text
        assert "pair-rotate" not in text
    status = agent.reminders(now=end, send=False)
    assert any("rappels · console-token : fin le 2027-02-18" in s for s in status)


def test_the_token_turned_after_its_reminder_is_confirmed_once_with_its_own_words(tmp_path, monkeypatch, fake):
    """ROT3: the J-14 of the token sent, then a later day to turn it again (make imladris-console-rotate, or
    make imladris-console-token-note, which turns nothing: the card claims a new day, never a draw)."""
    agent = _agent(tmp_path, monkeypatch, fake)
    d = tmp_path / ".eregion-cd" / "expiry"
    d.mkdir(parents=True)
    note = d / "console-token.json"
    note.write_text(json.dumps({"pair": "console-token", "end": "2027-02-18T09:00:00Z"}))
    agent.reminders(now=datetime(2027, 2, 4, 8, tzinfo=timezone.utc))                 # J-14
    note.write_text(json.dumps({"pair": "console-token", "end": "2027-05-06T09:00:00Z"}))
    for minute in (0, 5, 10):
        agent.reminders(now=datetime(2027, 2, 5, 8, minute, tzinfo=timezone.utc))
    posts = fake.webhook_posts(HOOK)
    assert [p["embeds"][0]["title"] for p in posts] == [
        "🔑 Le jeton de la console d'Imladris est à faire tourner dans 14 jours, le 2027-02-18",
        "✅ Le jeton de la console d'Imladris : nouvelle date, à refaire le 2027-05-06 (dans 90 jours)"]
    assert posts[-1]["embeds"][0]["description"] == \
        "Les rappels repartent pour cette date : J-14, J-7, J-1 et le jour même."
    assert "content" not in posts[-1]
    (status,) = agent.reminders(now=datetime(2027, 2, 5, 9, tzinfo=timezone.utc), send=False)
    assert status.startswith("  rappels · console-token : fin le 2027-05-06") and \
        status.endswith("renouvelé le 2027-02-05")


def test_the_cd_never_holds_the_token_only_its_day():
    src = AGENT.read_text(encoding="utf-8")
    reminders = src.split("# ── the reminders of the pairs' secrets", 1)[1].split("# ── the pass", 1)[0]
    assert "CONSOLE_TOKEN =" in reminders
    assert "EREGION_CONSOLE_TOKEN" not in reminders and "WARROOM" not in reminders and "read_env" not in reminders


# ── the Makefile ─────────────────────────────────────────────────────────────────────

def test_the_targets_are_phony_helped_guarded_and_never_expand_days(tmp_path):
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    phony = makefile.split(".PHONY:", 1)[1].split("\n\n", 1)[0]
    helped = makefile.split("\nhelp:\n", 1)[1]
    for target in ("imladris-console-rotate", "imladris-console-token-note"):
        assert target in phony.split() and f"{target}-go" in phony.split()
        assert f"make {target} [DAYS=90]" in helped
        recipe = makefile.split(f"\n{target}-go:\n", 1)[1].split("\n\n", 1)[0]
        assert recipe.splitlines()[0].strip() == f"@$(CONSOLE_ROTATE) guard {target}"
        assert "$(PAIR_SSH)" in recipe and "$(HOST_IP)" not in recipe and "$(DAYS)" not in recipe
        assert "$(MAKE)" not in recipe          # a line naming $(MAKE) runs even under make -n
    assert "imladris-console-rotate-go imladris-console-token-note-go: export EREGION_CONSOLE_DAYS = $(value DAYS)" \
        in makefile
    assert "CONSOLE_PUSH  := $(MAKE) --no-print-directory imladris-push" in makefile
    # A real make, refused by the guard: had make expanded DAYS before it, the file would exist.
    env = {**os.environ, "EREGION_AGENT_SESSION": "1"}
    for target in ("imladris-console-rotate", "imladris-console-rotate-go", "imladris-console-token-note",
                   "imladris-console-token-note-go"):
        pwned = tmp_path / f"pwned-{target}"
        res = subprocess.run(["make", "--no-print-directory", "-C", str(ROOT), target,
                              f"DAYS=$(shell touch {pwned})"], capture_output=True, text=True, timeout=60, env=env,
                             stdin=subprocess.DEVNULL)
        assert res.returncode != 0 and "refusé" in res.stderr, (target, res.stderr)
        assert not pwned.exists(), target


def _key(tmp_path, name):
    path = tmp_path / name
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)], check=True)
    pub = path.with_suffix(".pub").read_text().split()
    fp = subprocess.run(["ssh-keygen", "-lf", str(path.with_suffix(".pub"))], capture_output=True,
                        text=True, check=True).stdout.split()[1]
    return f"{IP} {pub[0]} {pub[1]}", fp


@pytest.mark.skipif(not (shutil.which("make") and shutil.which("ssh-keygen")), reason="make or ssh-keygen needed")
def test_make_imladris_console_rotate_end_to_end_through_make_imladris_push(tmp_path):
    """The whole gesture as Jonathan types it, from a copy of the checkout (never a lot's worktree: the
    guard refuses one): the key of Imladris pinned, the real `make imladris-push` (host_env.py --check,
    host_config.py, scp), then the console alone restarted, the old token refused, the day noted."""
    root = tmp_path / "checkout"
    for rel in ("Makefile", "scripts/console_rotate.py", "scripts/pair_rotate.py", "scripts/bench_shared.py",
                "scripts/credential_expiry.py", "infra/glorfindel-host/host_env.py",
                "infra/glorfindel-host/host_config.py", "infra/glorfindel-host/known_host.sh",
                "infra/glorfindel-host/ssh_opts.sh"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, root / rel)
    shutil.copytree(ROOT / "eregion_core", root / "eregion_core", ignore=shutil.ignore_patterns("__pycache__"))
    (root / "glorfindel-config.yaml").write_text("autonomy:\n  default: human_only\n")
    (root / ".venv" / "bin").mkdir(parents=True)
    _script(root / ".venv" / "bin" / "python", '#!/bin/sh\nexec "PYTHON" "$@"\n')
    w = World(tmp_path, repo=root)
    before = w.text()
    _script(w.bin / "terraform", f"#!/bin/sh\nprintf '%s' '{IP}'\n")
    _script(w.bin / "ssh-keyscan", "#!/bin/sh\nexit 1\n")
    line, fp = _key(tmp_path, "hostkey")
    known = tmp_path / "kh"
    known.write_text(line + "\n")
    known.chmod(0o600)
    env = w.env(HOME=str(tmp_path))
    for k in ("HOST_SSH_FINGERPRINT", "HOST_KNOWN_HOSTS", "HOST_IP", "HOST_SSH_KEY", "DAYS", "MAKEFLAGS", "MFLAGS"):
        env.pop(k, None)
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(root), "imladris-console-rotate",
                          f"HOST_SSH_FINGERPRINT={fp}", f"HOST_KNOWN_HOSTS={known}"], env=env, capture_output=True,
                         text=True, timeout=120, stdin=subprocess.DEVNULL)
    said = res.stdout + res.stderr
    assert res.returncode == 0, said
    new = w.token()
    assert new and new != OLD and OLD not in said and new not in said
    assert _others(w.text()) == _others(before)
    assert (w.imladris / "eregion" / ".env").read_bytes() == w.host_env.read_bytes()      # scp'd by imladris-push
    assert (w.imladris / ".console-running").read_text() == new
    assert [c["argv"] for c in w.calls("docker")] == [["compose", "up", "-d", "--no-deps", "--force-recreate",
                                                       "war-room"]]
    assert "accepte le nouveau jeton et refuse l'ancien" in said
    noted = w.noted()
    assert noted["pair"] == "console-token" and noted["by"] == "imladris-console-rotate"
    end = datetime.strptime(noted["end"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert abs(end - (datetime.now(timezone.utc) + timedelta(days=90))) < timedelta(minutes=5)
    for c in w.calls():
        assert new not in json.dumps(c["argv"]) and OLD not in json.dumps(c["argv"])
        if c["who"] in ("ssh", "scp"):
            assert f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={known}" in " ".join(c["argv"]), c


# ── the documents ────────────────────────────────────────────────────────────────────

def test_the_doc_says_the_gesture_its_reminder_and_the_threat_model_its_rotation():
    ops = (ROOT / "docs" / "operations.md").read_text(encoding="utf-8")
    part = ops.split("**Faire tourner le jeton de la console d'Imladris**", 1)[1].split("\n**Retirer l'ancien", 1)[0]
    for said in ("make imladris-console-rotate", "make imladris-console-token-note", "make imladris-url",
                 "make imladris-push", "war-room", "GLORFINDEL_WARROOM_TOKEN", "#deploy", "J-14", "0600",
                 "make imladris-cd-install"):
        assert said in part, said
    readme = (ROOT / "infra" / "glorfindel-host" / "README.md").read_text(encoding="utf-8")
    assert "ROT2 change l'agent" in readme and "make imladris-console-rotate" in readme
    threat = (ROOT / "docs" / "design" / "modele-de-menace.md").read_text(encoding="utf-8")
    line = next(ln for ln in threat.splitlines() if ln.startswith("| S | Un autre site"))
    assert "make imladris-console-rotate" in line and "#deploy" in line
