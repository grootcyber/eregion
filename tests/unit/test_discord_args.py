"""RMD1 (#1171) — a Discord script never writes on an argument it does not know.

On 24/11 a reviewer ran `scripts/roadmap_discord.py --help` to check a format: the script looked
for « --dry-run » alone, the EREGION_DISCORD_* were in the environment, and it rewrote #roadmap's
pinned message for real. Every `scripts/*_discord.py` is run here as the command line runs it,
with `--help`, `-h` and arguments it does not know, in an environment where every
EREGION_DISCORD_* (and GitHub's API) names the fake (tests/unit/fake_discord.py): not one request
reaches it, and no connection leaves the loopback (refused in the child, before any name is
resolved). A new `*_discord.py` is taken by the glob: without this guard, it fails here.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from .fake_discord import FakeDiscord

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = sorted((ROOT / "scripts").glob("*_discord.py"))

# The child: no connection outside the loopback (said on stderr, refused), then the script run as
# `python3 scripts/<name>.py <args>` runs it — its own sys.argv, its `if __name__ == "__main__"`.
CHILD = r"""
import os, runpy, socket, sys
LOOPBACK = ("127.0.0.1", "::1", "localhost")
def _refuse(host):
    print(f"RMD1-OUTSIDE {host}", file=sys.stderr, flush=True)
    raise OSError(f"RMD1: no connection outside the loopback ({host})")
_getaddrinfo, _connect = socket.getaddrinfo, socket.socket.connect
def getaddrinfo(host, *a, **k):
    if str(host) not in LOOPBACK:
        _refuse(host)
    return _getaddrinfo(host, *a, **k)
def connect(self, address):
    host = address[0] if isinstance(address, tuple) else address
    if str(host) not in LOOPBACK:
        _refuse(host)
    return _connect(self, address)
socket.getaddrinfo, socket.socket.connect = getaddrinfo, connect
script = sys.argv[1]
sys.argv = sys.argv[1:]
sys.path.insert(0, os.path.dirname(script))
runpy.run_path(script, run_name="__main__")
"""

HELP = (["--help"], ["-h"])
UNKNOWN = (["--nope"], ["nope"], ["--dry-run", "--nope"], ["--help-me"])


@pytest.fixture
def fake():
    f = FakeDiscord()
    yield f
    f.close()


def environment(f: FakeDiscord, home: Path) -> dict:
    """Built from nothing (never the session's environment, which may hold the real
    EREGION_DISCORD_*): every key the scripts read names the fake, the home is thrown away."""
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home), "LANG": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
        "XDG_STATE_HOME": str(home / "state"), "CLAUDE_HOME": str(home / "claude"),
        "EREGION_DISCORD_ENV": str(home / "absent.env"),
        "EREGION_DISCORD_API": f.base + "/api",
        "EREGION_DISCORD_WEBHOOK_CI": f"{f.base}/api/webhooks/1/CI-SECRET",
        "EREGION_DISCORD_WEBHOOK_AGENTS": f"{f.base}/api/webhooks/2/AGENTS-SECRET",
        "EREGION_DISCORD_WEBHOOK_RELEASES": f"{f.base}/api/webhooks/3/RELEASES-SECRET",
        "EREGION_DISCORD_WEBHOOK_DEPLOY": f"{f.base}/api/webhooks/4/DEPLOY-SECRET",
        "EREGION_DISCORD_BOT_TOKEN": "BOT-SECRET", "EREGION_DISCORD_LOTS_FORUM": "FORUM",
        "EREGION_DISCORD_ROADMAP_CHANNEL": "ROADMAP", "EREGION_DISCORD_MENTION": "42",
        "EREGION_DISCORD_SYNC": "1",
        "GITHUB_API_URL": f.base + "/gh", "GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "GH-SECRET",
    }


def run(script: Path, args: list[str], env: dict, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", "-c", CHILD, str(script), *args], env=env, cwd=cwd,
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)


def test_the_glob_takes_the_three_scripts():
    """The guard below is only as wide as its glob: the three scripts of 24/11 are in it."""
    assert {p.name for p in SCRIPTS} >= {"notify_discord.py", "agents_discord.py", "roadmap_discord.py"}


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
@pytest.mark.parametrize("args", HELP, ids=" ".join)
def test_help_prints_its_usage_and_calls_nothing(script, args, fake, tmp_path):
    r = run(script, args, environment(fake, tmp_path), tmp_path)
    assert r.returncode == 0, r.stderr
    assert "usage:" in r.stdout
    assert fake.requests == [], f"{script.name} {' '.join(args)} called {fake.requests}"
    assert "RMD1-OUTSIDE" not in r.stderr


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
@pytest.mark.parametrize("args", UNKNOWN, ids=" ".join)
def test_an_unknown_argument_exits_2_and_calls_nothing(script, args, fake, tmp_path):
    r = run(script, args, environment(fake, tmp_path), tmp_path)
    assert r.returncode == 2, (r.returncode, r.stderr)
    assert fake.requests == [], f"{script.name} {' '.join(args)} called {fake.requests}"
    assert "RMD1-OUTSIDE" not in r.stderr


def test_the_environment_reaches_the_fake(fake, tmp_path):
    """The control: the same environment and child, roadmap_discord without an argument (as
    roadmap.yml runs it) writes #roadmap — in the fake. A guard whose environment named nothing
    would pass above without proving anything."""
    r = run(ROOT / "scripts" / "roadmap_discord.py", [], environment(fake, tmp_path), tmp_path)
    assert r.returncode == 0, r.stderr
    assert [m for m in fake.writes("/api/channels/ROADMAP/messages") if m["method"] == "POST"], fake.requests
    assert "RMD1-OUTSIDE" not in r.stderr


def test_the_child_refuses_a_connection_outside_the_loopback(fake, tmp_path):
    """The other control: a script that calls out is stopped before its name is resolved, and said."""
    out = tmp_path / "out_discord.py"
    out.write_text("import urllib.request\nurllib.request.urlopen('https://discord.invalid/', timeout=2)\n",
                   encoding="utf-8")
    r = run(out, [], environment(fake, tmp_path), tmp_path)
    assert r.returncode != 0 and "RMD1-OUTSIDE discord.invalid" in r.stderr
