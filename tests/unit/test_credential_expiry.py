"""RST1 (#680, g): `make azure-pairs-expiry`, the end date of the secrets of the workstation's three
pairs (the watch, the console, the bot), read on demand under the operator's `az login`.

On the bench (09/11) the console's pair was left commented in `.envrc`, and a restore under an empty
pair takes another identity without saying so; the session reactivated it with a 30-day secret.
PAIR1 (#736): on the bench (12/11) the console's secret was on its service principal, none on its
application — the watch's on its application —, and the check read the application only: « aucun
secret » of a pair that connected, its expiry never seen. Both objects are read now.
Held here, on a fake `az` put first on PATH — no Azure, no Graph:
  - a date under 14 days warns, a far one is quiet (« ✓ »), an expired one fails (exit 1);
  - a secret on the application only, on the service principal only, on both (the nearest
    decides), on neither (« aucun » only then), a certificate; each said with where it lives;
  - an object az can't read is said, ✗, never « aucun », and no ✓ beside it, its ids masked;
  - an absent pair says « aucune paire », and az is not asked about it;
  - only the end dates are asked of az: a secret is never printed, nor a client id, nor a key id;
  - several valid secrets are said, an old expired one beside a valid one is to remove, the pair
    holding, with the command of its own object;
  - `check-azure-env` (the start of Glorfindel) never calls az;
  - the bench's step 0 calls the target, and the rotation cites it and says the two forms.
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
_KEY_ID = "bbbbbbbb-2222-4222-8222-00000000000b"
_IDS = {"GLORFINDEL_AZURE_CLIENT_ID": "aaaaaaaa-1111-4111-8111-000000000001",
        "EREGION_CONSOLE_AZURE_CLIENT_ID": "aaaaaaaa-1111-4111-8111-000000000002",
        "GLORFINDEL_BOT_AZURE_CLIENT_ID": "aaaaaaaa-1111-4111-8111-000000000003"}
_QUERY = "{secrets: passwordCredentials[].endDateTime, certificates: keyCredentials[].endDateTime}"

# The fake az: what Graph would give for each application id, object by object (`app`, `sp`): its
# secrets' and certificates' end dates, or "fail"; every call logged. Asked anything but the dates
# query, it gives the whole object — hints, key ids and a secret text included —, so a target that
# asked for more would print them.
_FAKE_AZ = r'''#!PYTHON
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_AZ_LOG"], "a") as f:
    f.write(json.dumps(args) + "\n")
plan = json.load(open(os.environ["FAKE_AZ_PLAN"]))
app = args[args.index("--id") + 1] if "--id" in args else ""
obj = args[1] if len(args) > 2 and args[0] == "ad" and args[2] == "show" else None
if obj not in ("app", "sp"):
    sys.stderr.write("fake az: not a show of an application or a service principal: %s\n" % args)
    sys.exit(99)
held = plan.get(app, {}).get(obj, {})
if held == "fail":
    sys.stderr.write("ERROR: Resource '%s' does not exist or one of its queried reference-property objects "
                     "are not present. Please run 'az login'.\n" % app)
    sys.exit(1)
secrets, certs = held.get("secrets", []), held.get("certificates", [])
query = args[args.index("--query") + 1] if "--query" in args else ""
if query == "QUERY":
    print(json.dumps({"secrets": secrets, "certificates": certs}))
else:
    cred = lambda d: {"endDateTime": d, "hint": "HINT", "secretText": "SECRET", "keyId": "KEY"}
    print(json.dumps({"appId": app, "passwordCredentials": [cred(d) for d in secrets],
                      "keyCredentials": [cred(d) for d in certs]}))
'''


def _iso(days: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day(days: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")


def _held(app=None, sp=None, app_certs=None, sp_certs=None) -> dict:
    """What one application id holds: secrets on the application, on its service principal."""
    out = {}
    for obj, secrets, certs in (("app", app, app_certs), ("sp", sp, sp_certs)):
        out[obj] = secrets if secrets == "fail" else {"secrets": secrets or [], "certificates": certs or []}
    return out


def _run(tmp_path, plan: dict, env: dict, target: str = "azure-pairs-expiry"):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    az = bin_dir / "az"
    az.write_text(_FAKE_AZ.replace("PYTHON", sys.executable).replace("HINT", _HINT).replace("SECRET", _SECRET)
                  .replace('"KEY"', json.dumps(_KEY_ID)).replace('"QUERY"', json.dumps(_QUERY)))
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


def _console(tmp_path, **held):
    return _run(tmp_path, {_IDS["EREGION_CONSOLE_AZURE_CLIENT_ID"]: _held(**held)},
                _pairs("EREGION_CONSOLE_AZURE_CLIENT_ID"))


def _line(out: str, name: str) -> str:
    return next(line for line in out.splitlines() if line.strip()[2:].startswith(f"{name} :"))


def _no_value(res) -> None:
    said = res.stdout + res.stderr
    assert _SECRET not in said and _HINT not in said and _KEY_ID not in said
    assert not [v for v in _IDS.values() if v in said]


def test_a_close_date_warns_a_far_one_is_quiet_and_an_absent_pair_is_said(tmp_path):
    env = _pairs("GLORFINDEL_AZURE_CLIENT_ID", "EREGION_CONSOLE_AZURE_CLIENT_ID")
    plan = {_IDS["GLORFINDEL_AZURE_CLIENT_ID"]: _held(app=[_iso(200)]),
            _IDS["EREGION_CONSOLE_AZURE_CLIENT_ID"]: _held(app=[_iso(5)])}
    res, calls = _run(tmp_path, plan, env)
    assert res.returncode == 0, res.stdout + res.stderr
    out = res.stdout
    watch, console = _line(out, "watch"), _line(out, "console")
    assert watch.startswith("✓ watch : secret valable jusqu'au") and "⚠" not in watch
    assert console.startswith("⚠ console : secret qui expire dans") and "Faire tourner un secret" in console
    assert "ℹ bot : aucune paire (GLORFINDEL_BOT_AZURE_CLIENT_ID vide)" in out
    # Only the end dates were asked, of both objects of the two pairs set; nothing of the absent one.
    assert sorted((a[1], a[a.index("--id") + 1]) for a in calls) == sorted(
        (obj, _IDS[var]) for obj in ("app", "sp") for var in ("GLORFINDEL_AZURE_CLIENT_ID",
                                                               "EREGION_CONSOLE_AZURE_CLIENT_ID"))
    for args in calls:
        assert args[0] == "ad" and args[2] == "show"
        assert args[args.index("--query") + 1] == _QUERY
    _no_value(res)


def test_a_secret_on_the_application_only_is_seen_and_said_there(tmp_path):
    """The watch's form on the bench (12/11): its secret on its application."""
    res, _ = _console(tmp_path, app=[_iso(200)])
    assert res.returncode == 0, res.stdout
    assert _line(res.stdout, "console") == f"✓ console : secret valable jusqu'au {_day(200)} (199 j), sur son application"
    _no_value(res)


def test_a_secret_on_the_service_principal_only_is_seen_with_its_days_left(tmp_path):
    """The console's form on the bench (12/11): 0 secret on its application, 1 on its service principal,
    26 days left — said « aucun secret lu » before PAIR1, its expiry never seen."""
    res, _ = _console(tmp_path, sp=[_iso(26.5)])
    assert res.returncode == 0, res.stdout
    line = _line(res.stdout, "console")
    assert line == f"✓ console : secret valable jusqu'au {_day(26.5)} (26 j), sur son principal de service"
    assert "aucun secret" not in res.stdout
    # Under 14 days, it warns there too: the 26/11 the bench would have passed in silence.
    res, _ = _console(tmp_path, sp=[_iso(12.5)])
    assert _line(res.stdout, "console").startswith("⚠ console : secret qui expire dans 12 j, le ")
    assert "sur son principal de service — le faire tourner" in res.stdout
    _no_value(res)


def test_on_both_objects_the_nearest_end_decides_whichever_holds_it(tmp_path):
    res, _ = _console(tmp_path, app=[_iso(200)], sp=[_iso(5.5)])
    line = _line(res.stdout, "console")
    assert line.startswith("⚠ console : secret qui expire dans 5 j") and "sur son principal de service" in line
    assert (f"2 secrets valables ({_day(5.5)} sur son principal de service, {_day(200)} sur son application)"
            in res.stdout) and "un seul attendu" in res.stdout
    res, _ = _console(tmp_path, app=[_iso(5.5)], sp=[_iso(200)])
    line = _line(res.stdout, "console")
    assert line.startswith("⚠ console : secret qui expire dans 5 j") and "sur son application" in line


def test_a_certificate_is_read_too(tmp_path):
    res, _ = _console(tmp_path, sp_certs=[_iso(100.5)])
    assert res.returncode == 0, res.stdout
    assert _line(res.stdout, "console") == (f"✓ console : certificat valable jusqu'au {_day(100.5)} (100 j), "
                                           "sur son principal de service")
    res, _ = _console(tmp_path, app=[_iso(300)], app_certs=[_iso(2.5)])
    assert _line(res.stdout, "console").startswith("⚠ console : certificat qui expire dans 2 j")
    assert "2 secrets ou certificats valables (certificat " in res.stdout


def test_no_secret_on_either_object_is_a_failure(tmp_path):
    res, _ = _console(tmp_path)
    assert res.returncode != 0
    assert _line(res.stdout, "console") == ("✗ console : aucun secret ni certificat, ni sur son application ni sur "
                                           "son principal de service — la paire ne peut pas se connecter")


def test_an_object_az_can_t_read_is_said_never_read_as_none(tmp_path):
    """The service principal unread, the application empty: not « aucun » — a secret may be there."""
    res, _ = _console(tmp_path, sp="fail")
    assert res.returncode != 0
    assert "✗ console : date de fin illisible sur son principal de service (ERROR: Resource '<id>'" in res.stdout
    assert "aucun secret" not in res.stdout
    _no_value(res)


def test_beside_an_unread_object_a_valid_secret_is_no_check_mark(tmp_path):
    """The application unread, a far secret on the service principal: a nearer one may be on the
    application — a ⚠ that says it, never a ✓; the run exits 1 on the unread object."""
    res, _ = _console(tmp_path, app="fail", sp=[_iso(200)])
    assert res.returncode != 0
    assert "✗ console : date de fin illisible sur son application" in res.stdout
    line = [ln for ln in res.stdout.splitlines() if "valable" in ln][0]
    assert line.startswith("⚠ console : secret valable jusqu'au") and "sur son principal de service" in line
    assert "son application illisible : une date plus proche peut s'y trouver" in line
    assert "✓" not in res.stdout


def test_both_objects_unread_are_both_said(tmp_path):
    res, _ = _console(tmp_path, app="fail", sp="fail")
    assert res.returncode != 0
    assert res.stdout.count("✗ console : date de fin illisible sur ") == 2 and "aucun secret" not in res.stdout


def test_an_unexpected_answer_is_unreadable_never_none(tmp_path):
    """az answering an empty body, or a list where the two lists are asked: unreadable, not « aucun »."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for body in ("", "[]", '{"secrets": null, "certificates": []}'):
        (bin_dir / "az").write_text(f"#!{sys.executable}\nprint({body!r})\n")
        (bin_dir / "az").chmod(0o755)
        env = {**{k: v for k, v in os.environ.items() if "AZURE_CLIENT" not in k},
               "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}", "HOME": str(tmp_path / "home"),
               **_pairs("EREGION_CONSOLE_AZURE_CLIENT_ID")}
        res = subprocess.run([sys.executable, str(ROOT / "scripts" / "credential_expiry.py")], env=env,
                             capture_output=True, text=True, timeout=60)
        assert res.returncode == 1, (body, res.stdout)
        assert res.stdout.count("✗ console : date de fin illisible sur ") == 2, (body, res.stdout)
        assert "aucun secret" not in res.stdout


def test_the_boundary_is_fourteen_days(tmp_path):
    res, _ = _console(tmp_path, sp=[_iso(13.5)])
    assert "⚠ console" in res.stdout
    res, _ = _console(tmp_path, sp=[_iso(14.5)])
    assert "✓ console" in res.stdout


def test_an_expired_secret_fails(tmp_path):
    res, _ = _console(tmp_path, app=[_iso(-1)])
    assert res.returncode != 0 and "✗ console : secret expiré le" in res.stdout and "sur son application" in res.stdout
    res, _ = _console(tmp_path, sp=[_iso(-1)])
    assert res.returncode != 0 and "✗ console : secret expiré le" in res.stdout
    assert "sur son principal de service" in res.stdout


def test_a_date_az_can_t_give_is_said_its_ids_masked(tmp_path):
    env = _pairs("GLORFINDEL_BOT_AZURE_CLIENT_ID")
    res, _ = _run(tmp_path, {_IDS["GLORFINDEL_BOT_AZURE_CLIENT_ID"]: _held(app="fail", sp="fail")}, env)
    assert res.returncode != 0
    assert "✗ bot : date de fin illisible" in res.stdout and "az login" in res.stdout
    assert _IDS["GLORFINDEL_BOT_AZURE_CLIENT_ID"] not in res.stdout and "<id>" in res.stdout


def test_several_secrets_are_said_the_nearest_decides(tmp_path):
    res, _ = _console(tmp_path, app=[_iso(300), _iso(3)])
    assert "⚠ console : secret qui expire dans" in res.stdout
    assert "2 secrets valables" in res.stdout and "un seul attendu" in res.stdout


def test_an_old_expired_secret_beside_a_valid_one_is_to_remove_the_pair_holds(tmp_path):
    """RST1 review: the oldest secret expired, a valid one beside it — not « expiré », no failure. PAIR1:
    the rotation that moved the secret to the service principal left the old one on the application."""
    res, _ = _console(tmp_path, app=[_iso(-40)], sp=[_iso(200)])
    assert res.returncode == 0, res.stdout
    assert "✓ console : secret valable jusqu'au" in res.stdout and "sur son principal de service" in res.stdout
    assert ("un ancien secret expiré le " + _day(-40) + " sur son application, à retirer "
            "(az ad app credential delete)") in res.stdout
    assert "✗" not in res.stdout and "un seul attendu" not in res.stdout
    res, _ = _console(tmp_path, sp=[_iso(-40)], app=[_iso(200)], sp_certs=[_iso(-3)])
    assert "sur son principal de service, à retirer (az ad sp credential delete)" in res.stdout
    assert "un ancien certificat expiré le" in res.stdout and "(az ad sp credential delete --cert)" in res.stdout


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
    # PAIR1: the two forms, and both objects read.
    assert "az ad app show" in rotation and "az ad sp show" in rotation
    assert "sur son principal de service" in rotation and "sur son application" in rotation
