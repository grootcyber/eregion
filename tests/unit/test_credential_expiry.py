"""RST1 (#680, g): `make azure-pairs-expiry`, the end date of the secrets of the workstation's three
pairs (the watch, the console, the bot), read on demand under the operator's `az login`.

On the bench (09/11) the console's pair was left commented in `.envrc`, and a restore under an empty
pair takes another identity without saying so; the session reactivated it with a 30-day secret.
Held here, on a fake `az` put first on PATH — no Azure, no Graph:
  - a date under 14 days warns, a far one is quiet (« ✓ »), an expired one fails (exit 1);
  - an absent pair says « aucune paire », and az is not asked about it;
  - only `endDateTime` is asked of az: a secret is never printed, nor a client id;
  - a date az can't give is said, its ids masked (exit 1); several secrets are said;
  - `check-azure-env` (the start of Glorfindel) never calls az;
  - the bench's step 0 calls the target, and the rotation cites it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")

_SECRET = "s3cr3t-never-printed"
_HINT = "Zq8"
_IDS = {"GLORFINDEL_AZURE_CLIENT_ID": "aaaaaaaa-1111-4111-8111-000000000001",
        "EREGION_CONSOLE_AZURE_CLIENT_ID": "aaaaaaaa-1111-4111-8111-000000000002",
        "GLORFINDEL_BOT_AZURE_CLIENT_ID": "aaaaaaaa-1111-4111-8111-000000000003"}

# The fake az: what Graph would give for each application id (a list of end dates, or "fail"),
# every call logged. Asked anything but `[].endDateTime`, it gives the whole credentials — a hint
# and a secret text included —, so a target that asked for more would print them.
_FAKE_AZ = r'''#!PYTHON
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_AZ_LOG"], "a") as f:
    f.write(json.dumps(args) + "\n")
plan = json.load(open(os.environ["FAKE_AZ_PLAN"]))
app = args[args.index("--id") + 1] if "--id" in args else ""
dates = plan.get(app, [])
if dates == "fail":
    sys.stderr.write("ERROR: AADSTS700016: Application with identifier '%s' was not found. Please run 'az login'.\n" % app)
    sys.exit(1)
query = args[args.index("--query") + 1] if "--query" in args else ""
if query == "[].endDateTime":
    print(json.dumps(dates))
else:
    print(json.dumps([{"endDateTime": d, "hint": "HINT", "secretText": "SECRET", "keyId": app} for d in dates]))
'''


def _iso(days: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(tmp_path, plan: dict, env: dict, target: str = "azure-pairs-expiry"):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    az = bin_dir / "az"
    az.write_text(_FAKE_AZ.replace("PYTHON", sys.executable).replace("HINT", _HINT).replace("SECRET", _SECRET))
    az.chmod(0o755)
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    log = tmp_path / "az.log"
    log.write_text("")
    base = {k: v for k, v in os.environ.items() if "AZURE_CLIENT" not in k}
    run_env = {**base, "HOME": str(tmp_path / "home"), "PATH": f"{bin_dir}{os.pathsep}{base.get('PATH', '')}",
               "FAKE_AZ_LOG": str(log), "FAKE_AZ_PLAN": str(tmp_path / "plan.json"), **env}
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(ROOT), target,
                          "AZURE_SUBSCRIPTION_ID=s"], env=run_env, capture_output=True, text=True, timeout=60)
    calls = [json.loads(line) for line in log.read_text().splitlines() if line]
    return res, calls


def _pairs(*names: str) -> dict:
    """The …_CLIENT_ID of these pairs, and each one's secret (the sentinel)."""
    out = {}
    for var in names:
        out[var] = _IDS[var]
        out[var.replace("_ID", "_SECRET")] = _SECRET
    return out


def test_a_close_date_warns_a_far_one_is_quiet_and_an_absent_pair_is_said(tmp_path):
    env = _pairs("GLORFINDEL_AZURE_CLIENT_ID", "EREGION_CONSOLE_AZURE_CLIENT_ID")
    plan = {_IDS["GLORFINDEL_AZURE_CLIENT_ID"]: [_iso(200)],
            _IDS["EREGION_CONSOLE_AZURE_CLIENT_ID"]: [_iso(5)]}
    res, calls = _run(tmp_path, plan, env)
    assert res.returncode == 0, res.stdout + res.stderr
    out = res.stdout
    watch = next(line for line in out.splitlines() if " watch " in line)
    console = next(line for line in out.splitlines() if " console " in line)
    assert watch.startswith("✓ watch : secret valable jusqu'au") and "⚠" not in watch
    assert console.startswith("⚠ console : secret qui expire dans") and "Faire tourner un secret" in console
    assert "ℹ bot : aucune paire (GLORFINDEL_BOT_AZURE_CLIENT_ID vide)" in out
    # Only the end dates were asked, of the two pairs set; nothing of the absent one.
    assert len(calls) == 2
    for args in calls:
        assert args[:4] == ["ad", "app", "credential", "list"]
        assert args[args.index("--query") + 1] == "[].endDateTime"
    assert {a[a.index("--id") + 1] for a in calls} == {_IDS["GLORFINDEL_AZURE_CLIENT_ID"],
                                                       _IDS["EREGION_CONSOLE_AZURE_CLIENT_ID"]}
    # Never a secret, a hint, nor a client id.
    assert _SECRET not in out + res.stderr and _HINT not in out
    assert not [v for v in _IDS.values() if v in out + res.stderr]


def test_the_boundary_is_fourteen_days(tmp_path):
    env = _pairs("EREGION_CONSOLE_AZURE_CLIENT_ID")
    res, _ = _run(tmp_path, {_IDS["EREGION_CONSOLE_AZURE_CLIENT_ID"]: [_iso(13.5)]}, env)
    assert "⚠ console" in res.stdout
    res, _ = _run(tmp_path, {_IDS["EREGION_CONSOLE_AZURE_CLIENT_ID"]: [_iso(14.5)]}, env)
    assert "✓ console" in res.stdout


def test_an_expired_secret_fails(tmp_path):
    env = _pairs("EREGION_CONSOLE_AZURE_CLIENT_ID")
    res, _ = _run(tmp_path, {_IDS["EREGION_CONSOLE_AZURE_CLIENT_ID"]: [_iso(-1)]}, env)
    assert res.returncode != 0 and "✗ console : secret expiré le" in res.stdout


def test_a_date_az_can_t_give_is_said_its_ids_masked(tmp_path):
    env = _pairs("GLORFINDEL_BOT_AZURE_CLIENT_ID")
    res, _ = _run(tmp_path, {_IDS["GLORFINDEL_BOT_AZURE_CLIENT_ID"]: "fail"}, env)
    assert res.returncode != 0
    assert "✗ bot : date de fin illisible" in res.stdout and "az login" in res.stdout
    assert _IDS["GLORFINDEL_BOT_AZURE_CLIENT_ID"] not in res.stdout and "<id>" in res.stdout


def test_an_application_without_a_secret_is_said(tmp_path):
    env = _pairs("EREGION_CONSOLE_AZURE_CLIENT_ID")
    res, _ = _run(tmp_path, {_IDS["EREGION_CONSOLE_AZURE_CLIENT_ID"]: []}, env)
    assert res.returncode != 0 and "⚠ console : aucun secret lu" in res.stdout


def test_several_secrets_are_said_the_nearest_decides(tmp_path):
    env = _pairs("EREGION_CONSOLE_AZURE_CLIENT_ID")
    res, _ = _run(tmp_path, {_IDS["EREGION_CONSOLE_AZURE_CLIENT_ID"]: [_iso(300), _iso(3)]}, env)
    assert "⚠ console : secret qui expire dans" in res.stdout
    assert "2 secrets" in res.stdout and "un seul attendu" in res.stdout


def test_no_pair_at_all_says_three_absent_pairs_and_calls_nothing(tmp_path):
    res, calls = _run(tmp_path, {}, {})
    assert res.returncode == 0 and calls == []
    assert res.stdout.count("aucune paire") == 3


def test_check_azure_env_never_calls_az(tmp_path):
    """Glorfindel's start reads no Graph: the expiry is read on demand only."""
    env = _pairs("GLORFINDEL_AZURE_CLIENT_ID", "EREGION_CONSOLE_AZURE_CLIENT_ID", "GLORFINDEL_BOT_AZURE_CLIENT_ID")
    res, calls = _run(tmp_path, {}, env, target="check-azure-env")
    assert res.returncode == 0, res.stderr
    assert calls == []
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    recipe = makefile.split("\ncheck-azure-env:\n", 1)[1].split("\n\n", 1)[0]
    assert "az " not in recipe and "credential_expiry" not in recipe


def test_the_target_is_phony_helped_called_at_the_bench_s_step_0_and_cited_in_the_rotation():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    phony = makefile.split(".PHONY:", 1)[1].split("\n\n", 1)[0]
    assert "azure-pairs-expiry" in phony and "make azure-pairs-expiry" in makefile.split("\nhelp:\n", 1)[1]
    bench = (ROOT / "docs" / "banc-t1486.md").read_text(encoding="utf-8")
    step0 = bench.split("### 0. Avant", 1)[1].split("\n### 1.", 1)[0]
    assert "make azure-pairs-expiry" in step0
    ops = (ROOT / "docs" / "operations.md").read_text(encoding="utf-8")
    rotation = ops.split("**Faire tourner un secret**", 1)[1].split("\n\n", 1)[0]
    assert "make azure-pairs-expiry" in rotation
