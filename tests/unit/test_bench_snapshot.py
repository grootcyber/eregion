"""The clean point after the confirmation, and the route of the 📸 button (BNC3b, #770).

docs/design/banc-autonome.md, §3.1. On fakes only: the bench's world (tests/unit/bench_world.py: `az`,
`ssh`, `terraform`, `docker` first on PATH, Imladris read by scripts/bench_h0_reader.py run for real on
a fake Imladris), a fake `ssh` that holds the forward's port, a fake console in-process, and the real
console's entry checks (eregion_console/api.py) through its TestClient. No Azure, no Imladris, no
console reached, no Orodruin.

The oracles are the design's: the newest point kept only after the VM's last restore and outside every
quarantine, a read that fails never a clean point; the forward opened by the script, pinned, without a
multiplexed master, closed whatever the end; the token by the environment only, never in an argv nor
printed, as a Bearer; a JSON body and a Host of 127.0.0.1:<port>, which the console's own middleware
accepts; under FS1 each final refusal stops; the job followed to Completed, bounded.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_world as bw  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


bs = _load("bench_shared")
bh = _load("bench_history")
bsn = _load("bench_snapshot")

NOW = datetime(2026, 11, 12, 22, 0, tzinfo=timezone.utc)
TOKEN = "tok-of-the-console-never-shown-Z9"
CONTAINER_FULL = f"IaasVMContainer;iaasvmcontainerv2;{bw.RG};{bw.VM}"
ITEM_NAME = f"VM;iaasvmcontainerv2;{bw.RG};{bw.VM}"
ITEM = {"id": (f"/subscriptions/{bw.SUB}/resourceGroups/{bw.RG}/providers/Microsoft.RecoveryServices/vaults/"
               f"{bw.VAULT}/backupFabrics/Azure/protectionContainers/{CONTAINER_FULL}/protectedItems/{ITEM_NAME}"),
        "name": ITEM_NAME, "properties": {"friendlyName": bw.VM}}


DISK = f"/subscriptions/{bw.SUB}/resourceGroups/{bw.RG}/providers/Microsoft.Compute/disks/gondolin-osdisk"


def _at(**ago) -> datetime:
    return NOW - timedelta(**ago)


def _restore(end: datetime) -> dict:
    return {"name": "00000000-0000-4000-8000-0000000000ab",
            "properties": {"entityFriendlyName": bw.VM, "operation": "Restore", "status": "Completed",
                           "containerName": f"iaasvmcontainerv2;{bw.RG};{bw.VM}",
                           "startTime": (end - timedelta(minutes=20)).isoformat(), "endTime": end.isoformat()}}


def _world(tmp_path, *, point: datetime, jobs=None, created="2026-07-01T09:00:00+00:00") -> bw.World:
    w = bw.World(tmp_path)
    w.rules = [
        bw.rule("az", ["vm", "list"], [{"name": bw.VM, "rg": bw.RG, "id": bw.RID}]),
        bw.rule("az", ["backup", "item", "list"], [ITEM]),
        bw.rule("az", ["backup", "recoverypoint", "list", "-c", CONTAINER_FULL, "-i", ITEM_NAME],
                [{"name": "1", "properties": {"recoveryPointTime": point.isoformat()}},
                 {"name": "2", "properties": {"recoveryPointTime": (point - timedelta(days=1)).isoformat()}}]),
        bw.rule("az", ["backup", "job", "list"], [_restore(_at(days=2))] if jobs is None else jobs),
        bw.rule("az", ["vm", "show", bw.RID, "timeCreated"], json.dumps(created)),
        # the restore of 2 days ago, proven in place as REC1 proves it: its « Job Type » (measured,
        # 09/11), and the VM's OS disk created during the job
        bw.rule("az", ["backup", "job", "show"],
                {"properties": {"extendedInfo": {"propertyBag": {"Job Type ": "Replace disks"}}}}),
        bw.rule("az", ["vm", "show", bw.RID, "storageProfile.osDisk.managedDisk.id"], json.dumps(DISK)),
        bw.rule("az", ["disk", "show", DISK, "timeCreated"], json.dumps(_at(days=2, minutes=10).isoformat())),
    ]
    return w


def _env(w: bw.World, monkeypatch) -> dict:
    env = w.env()
    for k in ("PATH", "BENCH_FAKE_PLAN", "BENCH_FAKE_LOG"):
        monkeypatch.setenv(k, env[k])
    return env


def _cycle(w: bw.World, *, action: str, verified_at: datetime, action_s=3, verified=True, name="watch") -> None:
    path = w.app / "runs" / "glorfindel" / f"{name}_debug.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps({"timestamp": (verified_at + timedelta(minutes=5)).isoformat(),
                            "signal": {"resource_id": bw.RID}, "action": action, "reasoning": "never sent back",
                            "outcome": {"executed": True, "verified": verified, "verified_at": verified_at.isoformat(),
                                        **({"action_s": action_s} if action_s is not None else {})}}) + "\n")


def _judge(w, monkeypatch):
    return bsn.judge(bw.VM, _env(w, monkeypatch), str(w.config), now=NOW.timestamp())


# ── the clean point ───────────────────────────────────────────────────────────

def test_the_newest_point_after_the_restore_and_outside_any_quarantine_is_kept(tmp_path, monkeypatch):
    w = _world(tmp_path, point=_at(hours=3))
    # a quarantine of an earlier run, lifted before the point, and one before the restore
    _cycle(w, action="isolate_vm", verified_at=_at(days=3))
    _cycle(w, action="isolate_vm", verified_at=_at(hours=6))
    _cycle(w, action="release_isolation", verified_at=_at(hours=5))
    got = _judge(w, monkeypatch)
    assert got["clean"] is True, got
    assert got["said"].startswith("le plus récent (19:00:00), pris après le dernier restore")
    history = [c for c in w.calls() if c[0] == "ssh" and " history " in f" {c[-1]} "]
    assert len(history) == 1 and "--network none" in history[0][-1] and "--read-only" in history[0][-1]
    assert not [c for c in w.calls() if c[0] == "ssh" and "exec" in c[-1].split()]


def test_a_point_from_before_the_last_restore_is_refused(tmp_path, monkeypatch):
    w = _world(tmp_path, point=_at(days=3))
    got = _judge(w, monkeypatch)
    assert got["clean"] is False and "d'avant son dernier restore" in got["said"]


@pytest.mark.parametrize("lifted", [None, "after"])
def test_a_point_taken_in_a_quarantine_is_refused(tmp_path, monkeypatch, lifted):
    """Over every run: an isolation before the point, its lift after it — or no lift read."""
    w = _world(tmp_path, point=_at(hours=3))
    _cycle(w, action="isolate_vm", verified_at=_at(hours=4))
    if lifted:
        _cycle(w, action="release_isolation", verified_at=_at(hours=1))
    got = _judge(w, monkeypatch)
    assert got["clean"] is False and "pris dans une quarantaine" in got["said"], got
    assert ("sans levée lue" in got["said"]) is (lifted is None)


def test_a_lift_of_the_console_ends_a_quarantine_only_when_it_held(tmp_path, monkeypatch):
    w = _world(tmp_path, point=_at(hours=3))
    _cycle(w, action="isolate_vm", verified_at=_at(hours=5))
    w.write("runs/console/manual_actions.jsonl", json.dumps(
        {"timestamp": _at(hours=4).isoformat(), "action": "release_isolation", "signal": {"resource_id": bw.RID},
         "outcome": {"status": "release_partial"}}) + "\n")
    assert _judge(w, monkeypatch)["clean"] is False
    w.write("runs/console/manual_actions.jsonl", json.dumps(
        {"timestamp": _at(hours=4).isoformat(), "action": "release_isolation", "signal": {"resource_id": bw.RID},
         "outcome": {"status": "released"}}) + "\n")
    assert _judge(w, monkeypatch)["clean"] is True


@pytest.mark.parametrize("case", ["no_restore", "jobs_fail", "isolation_unreadable", "h0_unpinned", "points_fail"])
def test_a_read_that_fails_is_no_clean_point(tmp_path, monkeypatch, case):
    w = _world(tmp_path, point=_at(hours=3), jobs=[] if case == "no_restore" else None)
    if case == "jobs_fail":
        w.rules.insert(0, bw.rule("az", ["backup", "job", "list"], rc=1, err="ERROR: (Forbidden) no\n"))
    if case == "isolation_unreadable":
        _cycle(w, action="isolate_vm", verified_at=_at(hours=4), action_s=None)
    if case == "points_fail":
        w.rules.insert(0, bw.rule("az", ["backup", "recoverypoint", "list"], rc=1, err="ERROR: boom\n"))
    env = _env(w, monkeypatch)
    if case == "h0_unpinned":
        env["BENCH_H0_SSH"] = f"ssh -o StrictHostKeyChecking=accept-new glorfindel@{bw.H0_IP}"
    got = bsn.judge(bw.VM, env, str(w.config), now=NOW.timestamp())
    assert got["clean"] is False and got["said"], got
    if case == "h0_unpinned":
        assert not [c for c in w.calls() if c[0] == "ssh"]


def test_the_quarantine_now_on_imladris_holds_every_point_after_it(tmp_path, monkeypatch):
    w = _world(tmp_path, point=_at(hours=3))
    w.write("runs/glorfindel/watch_debug.jsonl", "")
    w.write(".glorfindel/isolation/gondolin.json", {"resource_id": bw.RID, "isolated_at": _at(hours=4).isoformat()},
            home=True)
    got = _judge(w, monkeypatch)
    assert got["clean"] is False and "sans levée lue" in got["said"]


def test_the_history_reader_sends_back_no_reasoning_nor_id(tmp_path, monkeypatch):
    w = _world(tmp_path, point=_at(hours=3))
    _cycle(w, action="isolate_vm", verified_at=_at(hours=4))
    doc = bs.read_h0("history", bw.VM, env=_env(w, monkeypatch))
    text = json.dumps(doc)
    assert "never sent back" not in text and "/subscriptions/" not in text and bw.SUB not in text
    assert doc["files"] == 1 and doc["unreadable"] == [] and len(doc["isolations"]) == 1


# ── BNC3b, review round 1 ─────────────────────────────────────────────────────

def test_a_lift_before_the_line_of_a_console_isolation_never_closes_it(tmp_path, monkeypatch):
    """The watch lifts at 10:00, the console isolates again at 10:05 (its start taken at 09:55), the next
    lift at 12:00: a point of 11:00 is in that quarantine — the lift of 10:00 never closes it."""
    w = _world(tmp_path, point=_at(hours=1))
    _cycle(w, action="isolate_vm", verified_at=_at(hours=4))
    _cycle(w, action="release_isolation", verified_at=_at(hours=2))
    w.write("runs/console/manual_actions.jsonl", json.dumps(
        {"timestamp": _at(hours=1, minutes=55).isoformat(), "action": "isolate_vm", "signal": {"resource_id": bw.RID},
         "outcome": {"status": "isolated"}}) + "\n")
    _cycle(w, action="release_isolation", verified_at=_at(minutes=30), name="later")
    got = _judge(w, monkeypatch)
    assert got["clean"] is False and "pris dans une quarantaine" in got["said"], got


@pytest.mark.parametrize("case", ["bad_line", "no_files", "no_console_mount"])
def test_a_history_that_reads_in_part_is_no_quarantine_absent(tmp_path, monkeypatch, case):
    w = _world(tmp_path, point=_at(hours=3))
    if case == "bad_line":
        _cycle(w, action="isolate_vm", verified_at=_at(days=3))
        with open(w.app / "runs" / "glorfindel" / "watch_debug.jsonl", "a") as f:
            f.write('{"timestamp": "2026-11-12T20:00:00+00:00", "action": "isolate_vm", "sig\n')
    elif case == "no_console_mount":
        _cycle(w, action="isolate_vm", verified_at=_at(days=3))
    env = _env(w, monkeypatch)
    if case == "no_console_mount":
        plan = json.loads(w.plan_file.read_text())
        plan["h0"]["mounts"] = [m for m in plan["h0"]["mounts"] if m["Destination"] != "/app/runs/console"]
        w.plan_file.write_text(json.dumps(plan))
    got = bsn.judge(bw.VM, env, str(w.config), now=NOW.timestamp())
    assert got["clean"] is False and "ne se lisent pas" in got["said"], got
    said = {"bad_line": "ligne(s) illisible(s)", "no_files": "aucun fichier de cycles",
            "no_console_mount": "runs/console : absent"}[case]
    assert said in got["said"], got


def test_a_job_name_of_the_vault_given_by_the_console_is_followed_and_its_own_never_taken_for_one(monkeypatch):
    """`action_snapshot` gives `snapshot-<vm>-<ts>`, Glorfindel's own record — no job of the vault: then
    the job is looked for by its time. A name of the vault (a GUID, or `rsv:<vault>/<rg>/<name>`): followed."""
    assert bsn.vault_job_name("snapshot-vm-celebrimbor-gondolin-20261112T220000", PLAN) == ""
    assert bsn.vault_job_name("00000000-0000-4000-8000-0000000000aa", PLAN) == "00000000-0000-4000-8000-0000000000aa"
    assert bsn.vault_job_name(f"rsv:{bw.VAULT}/{bw.RG}/00000000-0000-4000-8000-0000000000aa", PLAN) == \
        "00000000-0000-4000-8000-0000000000aa"
    assert bsn.vault_job_name("rsv:other-vault/rg/00000000-0000-4000-8000-0000000000aa", PLAN) == ""
    import bench_preflight as bp
    az, asked = _jobs("Completed")
    monkeypatch.setattr(bs, "az_json", az)
    monkeypatch.setattr(bp, "point_times", lambda t, rg, v: [NOW.timestamp() + 60])
    clock = Clock()
    bsn.take(bw.VM, {}, PLAN, lambda s: None, token=TOKEN, tunnel=FakeTunnel([]),
             open_=FakeConsole({"status": "started", "job_id": "00000000-0000-4000-8000-0000000000cc"}),
             clock=clock, sleep=clock.sleep, now=NOW.timestamp)
    assert not [a for a in asked if a[:3] == ["backup", "job", "list"]], "the job given was looked for by its time"
    (show,) = [a for a in asked if a[:3] == ["backup", "job", "show"]]
    assert show[show.index("-n") + 1].endswith("0cc")


# ── the forward ───────────────────────────────────────────────────────────────

PINNED_SSH = f"ssh {bw.PINNED} glorfindel@{bw.H0_IP}"


@pytest.fixture
def fake_ssh(tmp_path):
    """An `ssh` that logs its argv and its pid, then holds the forward's local port, as `-N -L` does."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "ssh.jsonl"
    (bindir / "ssh").write_text(
        f"#!{sys.executable}\nimport json, os, socket, sys, time\n"
        f"open({str(log)!r}, 'a').write(json.dumps({{'argv': sys.argv[1:], 'pid': os.getpid(), "
        "'env': {k: v for k, v in os.environ.items() if k.startswith('BENCH_CONSOLE')}}) + '\\n')\n"
        "if os.environ.get('FAKE_SSH_FAIL'):\n    sys.exit(255)\n"
        "spec = sys.argv[sys.argv.index('-L') + 1]\n"
        "host, port = spec.split(':')[0], int(spec.split(':')[1])\n"
        "s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind((host, port)); s.listen(8)\n"
        "while True:\n    c, _ = s.accept(); c.close()\n")
    (bindir / "ssh").chmod(0o755)

    def calls():
        return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
    yield bindir, calls
    # nothing left running after the test, whatever its end (a forward left open: the test fails)
    import signal
    for c in calls():
        try:
            os.kill(c["pid"], signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_the_forward_is_opened_pinned_without_a_master_and_closed_after(fake_ssh, monkeypatch):
    bindir, calls = fake_ssh
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    env = {"BENCH_H0_SSH": PINNED_SSH, bsn.TOKEN_ENV: TOKEN}
    with bsn.Tunnel(env) as port:
        (seen,) = calls()
        argv = seen["argv"]
        assert argv[argv.index("-L") + 1] == f"127.0.0.1:{port}:127.0.0.1:7007"
        # a bounded remote command, never -N: a SIGTERM that skips the close leaves nothing open past it
        assert "-N" not in argv and argv[-1] == f"sleep {int(bsn.FORWARD_MAX_S)}"
        for opt in ("ControlMaster=no", "ControlPath=none", "ExitOnForwardFailure=yes", "BatchMode=yes",
                    "StrictHostKeyChecking=yes"):
            assert opt in argv, opt
        assert argv[-2] == f"glorfindel@{bw.H0_IP}"
        assert _alive(seen["pid"])
    assert not _alive(seen["pid"]), "the forward outlives the request"
    assert TOKEN not in json.dumps(calls()), "the token reached ssh"


def test_the_forward_is_closed_when_the_request_fails(fake_ssh, monkeypatch):
    bindir, calls = fake_ssh
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    with pytest.raises(RuntimeError, match="refusée"):
        with bsn.Tunnel({"BENCH_H0_SSH": PINNED_SSH}):
            raise RuntimeError("la console refusée")
    (seen,) = calls()
    assert not _alive(seen["pid"])


def test_a_forward_that_does_not_open_is_said(fake_ssh, monkeypatch):
    bindir, _ = fake_ssh
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_SSH_FAIL", "1")
    with pytest.raises(RuntimeError, match="ne s'ouvre pas"):
        with bsn.Tunnel({"BENCH_H0_SSH": PINNED_SSH}):
            pass


@pytest.mark.parametrize("ssh", [f"ssh -o StrictHostKeyChecking=accept-new glorfindel@{bw.H0_IP}", "", "ssh glorfindel@"])
def test_an_imladris_whose_host_key_is_not_pinned_gets_no_forward(fake_ssh, monkeypatch, ssh):
    bindir, calls = fake_ssh
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    with pytest.raises(RuntimeError):
        with bsn.Tunnel({"BENCH_H0_SSH": ssh}):
            pass
    assert calls() == []


# ── the console's route ───────────────────────────────────────────────────────

class _Resp:
    def __init__(self, doc, status=200):
        self.status, self._body = status, json.dumps(doc).encode()

    def read(self, n=-1):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeConsole:
    """The console as `call` reaches it: each answer in turn; each request kept."""

    def __init__(self, *answers):
        self.answers, self.asked = list(answers), []

    def __call__(self, req, timeout=None):
        self.asked.append(req)
        return _Resp(self.answers.pop(0) if len(self.answers) > 1 else self.answers[0])


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def test_the_request_carries_a_bearer_a_json_body_and_the_forward_s_host():
    console = FakeConsole({"status": "started", "job_id": "snapshot-x"})
    bsn.ask_snapshot(43210, bw.VM, TOKEN, open_=console, say=lambda s: None)
    (req,) = console.asked
    assert req.get_method() == "POST" and req.full_url == f"http://127.0.0.1:43210/api/action/snapshot/{bw.VM}"
    assert req.get_header("Authorization") == f"Bearer {TOKEN}"
    assert req.get_header("Content-type") == "application/json" and json.loads(req.data) == {}
    assert req.get_header("Host") == "127.0.0.1:43210"
    assert TOKEN not in req.full_url


def test_the_console_s_own_entry_checks_accept_the_request(monkeypatch):
    """The request `call` builds, replayed on the console's app (its middleware, its route): accepted —
    the route itself answers; without its JSON body, the console refuses it (415)."""
    from console_client import TOKEN as CONSOLE_TOKEN
    from fastapi.testclient import TestClient

    import eregion_console.api as api
    monkeypatch.setattr(api, "_find_resource_id", lambda vm: None)
    console = FakeConsole({"status": "started"})
    bsn.call(43210, "POST", f"/api/action/snapshot/{bw.VM}", CONSOLE_TOKEN, body={}, open_=console)
    (req,) = console.asked
    client = TestClient(api.app, base_url="http://127.0.0.1:43210")
    headers = dict(req.header_items())
    got = client.request(req.get_method(), req.full_url, headers=headers, content=req.data)
    assert got.status_code == 200 and got.json() == {"error": f"Resource ID not found for {bw.VM}"}, got.text
    bare = {k: v for k, v in headers.items() if k.lower() != "content-type"}
    assert client.request("POST", req.full_url, headers=bare).status_code == 415
    followed = client.request("GET", "http://127.0.0.1:43210/api/queue/r-0", headers=bare)
    assert followed.status_code == 200


def test_no_proxy_is_ever_taken(monkeypatch):
    """A proxy of the environment would carry the token elsewhere: the opener has none."""
    import urllib.request
    monkeypatch.setenv("http_proxy", "http://192.0.2.99:3128")
    monkeypatch.setenv("HTTP_PROXY", "http://192.0.2.99:3128")

    def proxies(opener):
        return [h for h in opener.handlers if isinstance(h, urllib.request.ProxyHandler) and h.proxies]
    assert proxies(urllib.request.build_opener()), "the default opener would take the proxy"
    assert proxies(bsn.opener()) == []


QUEUED = {"via": "queue", "request": "r-20261112T220000Z-abc123", "state": "deposited", "pending": True}


def test_under_fs1_the_receipt_is_followed_until_done():
    clock = Clock()
    console = FakeConsole(QUEUED, {"via": "queue", "request": QUEUED["request"], "state": "accepted", "pending": True},
                          {"via": "queue", "state": "done", "ok": True, "status": "started", "job_id": "snapshot-x"})
    bsn.ask_snapshot(1, bw.VM, TOKEN, open_=console, clock=clock, sleep=clock.sleep, say=lambda s: None)
    paths = [r.full_url.split(":1", 1)[1] for r in console.asked]
    assert paths == [f"/api/action/snapshot/{bw.VM}", f"/api/queue/{QUEUED['request']}",
                     f"/api/queue/{QUEUED['request']}"]
    assert all(r.get_header("Authorization") == f"Bearer {TOKEN}" for r in console.asked)


@pytest.mark.parametrize("final", [
    {"via": "queue", "state": "not_taken", "error": "the watch did not take the request"},
    {"via": "queue", "state": "untrusted", "error": "a receipt of another key"},
    {"via": "queue", "state": "refused", "error": "refused", "refused": "point_refused"},
    {"via": "queue", "state": "failed", "error": "Snapshot trigger failed"},
    {"via": "queue", "state": "unknown", "error": "no request of this id here"},
    {"via": "queue", "state": "done"},                                     # never said ok
])
def test_under_fs1_each_final_refusal_stops(final):
    clock = Clock()
    with pytest.raises(RuntimeError, match="la demande d'instantané : "):
        bsn.ask_snapshot(1, bw.VM, TOKEN, open_=FakeConsole(QUEUED, final), clock=clock, sleep=clock.sleep,
                         say=lambda s: None)


def test_under_fs1_a_request_past_its_life_stops():
    clock = Clock()
    with pytest.raises(RuntimeError, match="expired"):
        bsn.ask_snapshot(1, bw.VM, TOKEN, open_=FakeConsole(QUEUED), clock=clock, sleep=clock.sleep,
                         say=lambda s: None)
    assert clock.t <= bsn.QUEUE_WAIT_S + bsn.QUEUE_POLL_S


@pytest.mark.parametrize("answer", [{"error": "No backup vault configured"}, {"status": "queued?"}])
def test_a_console_that_refuses_or_says_nothing_stops(answer):
    with pytest.raises(RuntimeError):
        bsn.ask_snapshot(1, bw.VM, TOKEN, open_=FakeConsole(answer), say=lambda s: None)


def test_a_console_error_answer_is_said_without_the_token():
    import urllib.error

    def refuse(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, _Resp({"error": "Eregion console: open /?token=<…>"}))
    with pytest.raises(RuntimeError) as got:
        bsn.ask_snapshot(1, bw.VM, TOKEN, open_=refuse, say=lambda s: None)
    assert "Eregion console" in str(got.value) and TOKEN not in str(got.value)


# ── the vault's job ───────────────────────────────────────────────────────────

PLAN = {"vault": bw.VAULT, "vault_rg": bw.RG, "rg": bw.RG, "point": _at(days=1).timestamp()}


def _jobs(*statuses, shown=None):
    """`az_json` faked: the job list, then each `job show` in turn — a backup of the target, as Azure
    names its VM and its operation, or `shown`'s properties instead (SNP1b)."""
    asked = []
    shows = list(statuses)
    shown = {"entityFriendlyName": bw.VM, "operation": "Backup",
             "containerName": f"iaasvmcontainerv2;{bw.RG};{bw.VM}"} if shown is None else shown

    def az_json(args, timeout=120):
        asked.append(args)
        if args[:3] == ["backup", "job", "list"]:
            return [{"name": "00000000-0000-4000-8000-0000000000aa",
                     "properties": {"entityFriendlyName": bw.VM, "operation": "Backup", "status": "InProgress",
                                    "startTime": NOW.isoformat()}},
                    {"name": "00000000-0000-4000-8000-0000000000bb",
                     "properties": {"entityFriendlyName": bw.VM, "operation": "Backup", "status": "Completed",
                                    "startTime": _at(days=1).isoformat()}}]
        if args[:3] == ["backup", "job", "show"]:
            s = shows.pop(0) if len(shows) > 1 else shows[0]
            if isinstance(s, Exception):
                raise s
            return {"properties": {**shown, "status": s}}
        raise AssertionError(args)
    return az_json, asked


def test_the_job_started_since_the_gesture_is_followed_to_completed(monkeypatch):
    az, asked = _jobs("InProgress", "InProgress", "Completed")
    monkeypatch.setattr(bs, "az_json", az)
    clock = Clock()
    name = bsn.find_job(bw.VM, PLAN, NOW.timestamp(), clock=clock, sleep=clock.sleep)
    assert name.endswith("0aa")                      # the job of the gesture, never yesterday's
    bsn.await_job(name, PLAN, 0.0, target=bw.VM, clock=clock, sleep=clock.sleep, say=lambda s: None)
    shows = [a for a in asked if a[:3] == ["backup", "job", "show"]]
    assert len(shows) == 3 and all(a[a.index("-n") + 1] == name for a in shows)


@pytest.mark.parametrize("status", ["Failed", "Cancelled", "CompletedWithWarnings"])
def test_a_job_that_fails_stops(monkeypatch, status):
    az, _ = _jobs("InProgress", status)
    monkeypatch.setattr(bs, "az_json", az)
    clock = Clock()
    with pytest.raises(RuntimeError, match=f"le job du coffre : {status}"):
        bsn.await_job("j", PLAN, 0.0, target=bw.VM, clock=clock, sleep=clock.sleep, say=lambda s: None)


def test_a_job_past_its_bound_stops(monkeypatch):
    az, _ = _jobs("InProgress")
    monkeypatch.setattr(bs, "az_json", az)
    clock = Clock()
    with pytest.raises(RuntimeError, match="pas Completed en 60 min"):
        bsn.await_job("j", PLAN, 0.0, target=bw.VM, clock=clock, sleep=clock.sleep, say=lambda s: None)
    assert bsn.JOB_WAIT_S <= clock.t <= bsn.JOB_WAIT_S + bsn.JOB_POLL_S


def test_a_job_that_cannot_be_read_stops(monkeypatch):
    az, _ = _jobs(RuntimeError("ERROR: (Forbidden)"))
    monkeypatch.setattr(bs, "az_json", az)
    clock = Clock()
    with pytest.raises(RuntimeError, match="ne se lit plus"):
        bsn.await_job("j", PLAN, 0.0, target=bw.VM, clock=clock, sleep=clock.sleep, say=lambda s: None)


# ── the whole route ───────────────────────────────────────────────────────────

class FakeTunnel:
    def __init__(self, journal):
        self.journal = journal

    def __enter__(self):
        self.journal.append("open")
        return 43210

    def __exit__(self, *a):
        self.journal.append("close")
        return False


def test_take_asks_through_the_forward_then_follows_the_job_then_reads_the_new_point(monkeypatch):
    import bench_preflight as bp
    journal: list = []
    az, asked = _jobs("Completed")
    monkeypatch.setattr(bs, "az_json", az)
    monkeypatch.setattr(bp, "point_times", lambda t, rg, v: journal.append("points") or [NOW.timestamp() + 60])
    console = FakeConsole({"status": "started", "job_id": "snapshot-x"})
    clock = Clock()
    said: list[str] = []
    got = bsn.take(bw.VM, {bsn.TOKEN_ENV: TOKEN}, PLAN, said.append, tunnel=FakeTunnel(journal), open_=console,
                   clock=clock, sleep=clock.sleep, now=NOW.timestamp)
    assert got == NOW.timestamp() + 60
    assert journal == ["open", "close", "points"]               # the forward closed before the job's wait
    assert TOKEN not in "\n".join(said)


@pytest.mark.parametrize("env", [{}, {bsn.TOKEN_ENV: "  "}])
def test_without_the_console_s_token_nothing_is_asked(env):
    journal: list = []
    with pytest.raises(RuntimeError, match="le jeton de la console manque"):
        bsn.take(bw.VM, env, PLAN, print, tunnel=FakeTunnel(journal), open_=FakeConsole({}))
    assert journal == []


def test_a_job_completed_without_a_newer_point_stops(monkeypatch):
    import bench_preflight as bp
    az, _ = _jobs("Completed")
    monkeypatch.setattr(bs, "az_json", az)
    monkeypatch.setattr(bp, "point_times", lambda t, rg, v: [PLAN["point"]])
    clock = Clock()
    with pytest.raises(RuntimeError, match="aucun point plus récent"):
        bsn.take(bw.VM, {bsn.TOKEN_ENV: TOKEN}, PLAN, lambda s: None, tunnel=FakeTunnel([]),
                 open_=FakeConsole({"status": "started"}), clock=clock, sleep=clock.sleep, now=NOW.timestamp)


def test_the_real_clock_is_the_default():
    assert bsn.take.__kwdefaults__["clock"] is time.monotonic


# ── SNP1 (#789): the console names the vault's job, the bench follows it ─────

VAULT_GUID = "00000000-0000-4000-8000-0000000000dd"
VAULT_JOB = f"rsv:{bw.VAULT}/{bw.RG}/{VAULT_GUID}"


class RealConsole:
    """The console's app itself behind the forward: `call`'s request replayed on its middleware and its
    route (TestClient), its answer handed back as the forward would."""

    def __init__(self, port: int = 43210):
        from fastapi.testclient import TestClient

        import eregion_console.api as api
        self.client, self.answers = TestClient(api.app, base_url=f"http://127.0.0.1:{port}"), []

    def __call__(self, req, timeout=None):
        got = self.client.request(req.get_method(), req.full_url, headers=dict(req.header_items()), content=req.data)
        self.answers.append(got.json())
        return _Resp(got.json(), got.status_code)


@pytest.fixture
def snapshot_console(tmp_path, monkeypatch):
    """The console's direct route (no queue) on a VM of the bench, Azure's answer to the snapshot faked
    (`snap_id` given as `snap`, a list to set), Glorfindel's job record in tmp."""
    pytest.importorskip("fastapi")
    import eregion_console.api as api
    from glorfindel import jobs
    monkeypatch.delenv("EREGION_ACTION_QUEUE", raising=False)
    monkeypatch.setattr(jobs, "_JOBS_DIR", tmp_path / "active_jobs")
    monkeypatch.setattr(api, "_find_resource_id", lambda vm: bw.RID if vm == bw.VM else None)
    monkeypatch.setattr("glorfindel.config.resolve_backup_vault", lambda *a: (bw.VAULT, bw.RG, ""))
    snap = [VAULT_JOB]

    class Connector:
        def __init__(self, dry_run=True):
            assert dry_run is False

        def snapshot(self, resource_id, vault="", wait=True, vault_rg=""):
            assert (resource_id, vault, vault_rg, wait) == (bw.RID, bw.VAULT, bw.RG, False)
            return snap[0]
    monkeypatch.setattr("glorfindel.actions.AzureConnector", Connector)
    return snap


def _take_through(console, monkeypatch, *, token=None, statuses=("Completed",), shown=None, read=None,
                  stopped=False):
    """`take` through `console`: (asked, said); with `stopped`, the run must stop — (asked, said, error),
    the `az` calls made before it stopped included."""
    import bench_preflight as bp
    from console_client import TOKEN as CONSOLE_TOKEN
    az, asked = _jobs(*statuses, shown=shown)
    monkeypatch.setattr(bs, "az_json", az)
    monkeypatch.setattr(bp, "point_times",
                        lambda t, rg, v: (read.append("points") if read is not None else None) or [NOW.timestamp() + 60])
    clock, said = Clock(), []
    try:
        bsn.take(bw.VM, {}, PLAN, said.append, token=token or CONSOLE_TOKEN, tunnel=FakeTunnel([]), open_=console,
                 clock=clock, sleep=clock.sleep, now=NOW.timestamp)
    except RuntimeError as e:
        if not stopped:
            raise
        return asked, said, e
    assert not stopped, "the run went on"
    return asked, said


def _shows(asked):
    return [a for a in asked if a[:3] == ["backup", "job", "show"]]


def test_the_console_names_the_vault_s_job_and_the_bench_follows_it_without_looking_for_it_by_time(
        snapshot_console, monkeypatch):
    """The real route: `job_id` stays Glorfindel's own record, `vault_job` names the vault's job; the bench
    follows that job directly — no job list read by its time."""
    console = RealConsole()
    asked, said = _take_through(console, monkeypatch)
    (answer,) = console.answers
    assert answer["status"] == "started" and answer["resource_id"] == bw.RID, answer
    assert answer["job_id"].startswith(f"snapshot-{bw.VM}-"), "job_id changed for those who read it"
    assert answer["vault_job"] == VAULT_JOB, answer
    assert not [a for a in asked if a[:3] == ["backup", "job", "list"]], "the job named was looked for by its time"
    shows = [a for a in asked if a[:3] == ["backup", "job", "show"]]
    assert shows and all(a[a.index("-n") + 1] == VAULT_GUID for a in shows), shows
    assert any("le job du coffre que la console nomme" in s for s in said), said
    assert not any(VAULT_GUID in s for s in said), "the job's name printed"


def test_a_snapshot_that_names_no_vault_job_is_looked_for_by_its_time(snapshot_console, monkeypatch):
    """A dry run's `snap-dry-run-000` names no job of the vault: the answer says none, and the bench falls
    back on the job of the VM started since the gesture."""
    snapshot_console[0] = "snap-dry-run-000"
    console = RealConsole()
    asked, said = _take_through(console, monkeypatch)
    assert console.answers[0]["vault_job"] == "" and console.answers[0]["job_id"].startswith("snapshot-")
    assert [a for a in asked if a[:3] == ["backup", "job", "list"]], "no job named, and none looked for"
    (show,) = [a for a in asked if a[:3] == ["backup", "job", "show"]]
    assert show[show.index("-n") + 1].endswith("0aa")                # the job of the gesture, by its time
    assert any("cherché par son heure" in s for s in said), said


def test_under_fs1_the_vault_s_job_of_the_receipt_is_followed(monkeypatch):
    done = {"via": "queue", "state": "done", "ok": True, "status": "started", "job_id": "snapshot-x",
            "vault_job": VAULT_JOB}
    asked, _ = _take_through(FakeConsole(QUEUED, done), monkeypatch, token=TOKEN)
    assert not [a for a in asked if a[:3] == ["backup", "job", "list"]]
    (show,) = [a for a in asked if a[:3] == ["backup", "job", "show"]]
    assert show[show.index("-n") + 1] == VAULT_GUID


@pytest.mark.parametrize("vault_job", [
    f"rsv:another-vault/{bw.RG}/{VAULT_GUID}",                # another vault than the operator's
    f"rsv:{bw.VAULT}/rg-other/{VAULT_GUID}",                  # its group differs
    "snapshot-x",                                             # a shape not read
])
@pytest.mark.parametrize("queued", [False, True])
def test_a_vault_job_the_bench_cannot_follow_stops_and_is_never_looked_for_by_its_time(monkeypatch, vault_job,
                                                                                       queued):
    """A job named, but not of the vault the operator reads: the point would land where the bench never
    reads it. The run stops before Orodruin — never the job of the VM taken by its time instead."""
    done = {"status": "started", "job_id": "snapshot-x", "vault_job": vault_job}
    console = FakeConsole(QUEUED, {"via": "queue", "state": "done", "ok": True, **done}) if queued else FakeConsole(done)
    with pytest.raises(RuntimeError, match="pas du coffre du poste"):
        _take_through(console, monkeypatch, token=TOKEN)


def test_without_a_vault_job_a_job_id_of_the_vault_is_still_followed():
    """A console that names its job by `job_id` alone (a GUID, or the record's `rsv:` name) stays followed."""
    assert bsn.named_job({"job_id": VAULT_GUID, "vault_job": ""}, PLAN) == VAULT_GUID
    assert bsn.named_job({"job_id": VAULT_JOB, "vault_job": ""}, PLAN) == VAULT_GUID
    assert bsn.named_job({"job_id": "snapshot-x", "vault_job": ""}, PLAN) == ""
    assert bsn.named_job({"job_id": "snapshot-x", "vault_job": VAULT_JOB.upper().replace("RSV:", "rsv:")}, PLAN) \
        == VAULT_GUID.upper()


# ── SNP1b (#801): the job the console names, checked before it is followed ────

def _named(vault_job):
    return FakeConsole({"status": "started", "job_id": "snapshot-x", "vault_job": vault_job})


@pytest.mark.parametrize("shown, said", [
    ({"entityFriendlyName": "vm-celebrimbor-bree", "operation": "Backup"}, f"sa VM n'est pas {bw.VM}"),
    ({"entityFriendlyName": bw.VM, "operation": "Restore"}, "son opération est Restore, pas Backup"),
    ({"entityFriendlyName": bw.VM, "operation": "ConfigureBackup"}, "son opération est ConfigureBackup, pas Backup"),
    ({"entityFriendlyName": "vm-celebrimbor-bree", "operation": "DeleteBackupData"},
     f"sa VM n'est pas {bw.VM}, son opération est DeleteBackupData, pas Backup"),
])
@pytest.mark.parametrize("queued", [False, True])
def test_a_named_job_of_another_vm_or_operation_stops_at_its_first_show_and_is_never_followed(
        monkeypatch, shown, said, queued):
    """The console names a job of the vault, but Azure reads it as no backup of the target: another VM's,
    a restore, a configuration. The run stops at its first `show`, says what differs — never followed to
    Completed, no point read, nothing to Orodruin."""
    done = {"status": "started", "job_id": "snapshot-x", "vault_job": VAULT_JOB}
    console = FakeConsole(QUEUED, {"via": "queue", "state": "done", "ok": True, **done}) if queued else FakeConsole(done)
    read: list = []
    asked, _, err = _take_through(console, monkeypatch, token=TOKEN, statuses=("InProgress", "Completed"),
                                  shown=shown, read=read, stopped=True)
    assert "n'est pas une sauvegarde de" in str(err) and said in str(err), err
    assert VAULT_GUID not in str(err), "the job's name printed"
    assert len(_shows(asked)) == 1, "followed past its first show"
    assert read == [], "the point read after a job that is no backup of the target"


@pytest.mark.parametrize("shown, said", [
    ({"operation": "Backup"}, "sa VM ne se lit pas"),
    ({"entityFriendlyName": bw.VM}, "son opération ne se lit pas"),
    ({}, "sa VM ne se lit pas, son opération ne se lit pas"),
])
def test_a_named_job_whose_vm_or_operation_does_not_read_stops(monkeypatch, shown, said):
    """A `show` that does not say the job's VM or its operation proves no backup of the target: it stops
    — never taken for one because nothing contradicts it."""
    read: list = []
    asked, _, err = _take_through(_named(VAULT_JOB), monkeypatch, token=TOKEN, statuses=("InProgress", "Completed"),
                                  shown=shown, read=read, stopped=True)
    assert said in str(err), err
    assert len(_shows(asked)) == 1, "followed past its first show"
    assert read == []


def test_a_namesake_of_another_group_whose_backup_stayed_in_the_vault_stops(monkeypatch):
    """The job's container names another group than the target's: a VM of the same name, deleted, whose
    backups the vault kept. Not the target: stopped at the first show. A job that names no container is
    judged by its VM's name alone, as a restore is (glorfindel/providers/azure/recovery.py)."""
    read: list = []
    asked, _, err = _take_through(_named(VAULT_JOB), monkeypatch, token=TOKEN, statuses=("InProgress", "Completed"),
                                  shown={"entityFriendlyName": bw.VM, "operation": "Backup",
                                         "containerName": f"iaasvmcontainerv2;rg-gone;{bw.VM}"},
                                  read=read, stopped=True)
    assert "son conteneur n'est pas celui de" in str(err) and "rg-gone" not in str(err), err
    assert len(_shows(asked)) == 1 and read == []
    asked, _ = _take_through(_named(VAULT_JOB), monkeypatch, token=TOKEN,
                             shown={"entityFriendlyName": bw.VM, "operation": "Backup"})
    assert len(_shows(asked)) == 1


def test_a_read_in_error_is_read_again_and_the_job_followed_to_completed(monkeypatch):
    """`az` fails on a read, then answers: read again, never a stop on one error; and a good read
    counts the errors from zero again — three errors apart are no three in a row."""
    asked, _ = _take_through(_named(VAULT_JOB), monkeypatch, token=TOKEN,
                             statuses=(RuntimeError("ERROR: (TooManyRequests)"), "InProgress", "Completed"))
    assert len(_shows(asked)) == 3
    boom = RuntimeError("ERROR: (TooManyRequests)")
    asked, _ = _take_through(_named(VAULT_JOB), monkeypatch, token=TOKEN,
                             statuses=(boom, boom, "InProgress", boom, boom, "InProgress", "Completed"))
    assert len(_shows(asked)) == 7


def test_a_named_job_of_the_target_in_azure_s_own_case_is_followed(monkeypatch):
    """Azure may give the VM's name in its own case: the same VM, followed."""
    asked, _ = _take_through(_named(VAULT_JOB), monkeypatch, token=TOKEN,
                             shown={"entityFriendlyName": bw.VM.upper(), "operation": "Backup"})
    assert [a for a in asked if a[:3] == ["backup", "job", "show"]]


@pytest.mark.parametrize("key", ["vault_job", "job_id"])
@pytest.mark.parametrize("name, said, unsaid", [
    (f"rsv:another-vault/{bw.RG}/{VAULT_GUID}", "son coffre diffère", "son groupe"),
    (f"rsv:{bw.VAULT}/rg-other/{VAULT_GUID}", "son groupe diffère", "son coffre"),
    (f"rsv:another-vault/rg-other/{VAULT_GUID}", "son coffre et son groupe diffèrent", None),
    (f"rsv:{bw.VAULT}/{bw.RG}/not_a_job!", "sa forme ne se lit pas", "son coffre"),
])
def test_a_rsv_name_of_another_vault_or_group_stops_whether_named_by_vault_job_or_job_id(
        monkeypatch, key, name, said, unsaid):
    """`rsv:<vault>/<group>/<name>` names a job of the vault — wherever the console puts it. Of another
    vault or group than the operator's, it stops the run and says which: never replaced, in silence, by
    the job of the VM looked for by its time."""
    given = {"status": "started", "job_id": "snapshot-x", "vault_job": ""}
    given[key] = name
    import bench_preflight as bp
    az, asked = _jobs("Completed")
    monkeypatch.setattr(bs, "az_json", az)
    monkeypatch.setattr(bp, "point_times", lambda t, rg, v: [NOW.timestamp() + 60])
    clock = Clock()
    with pytest.raises(RuntimeError) as got:
        bsn.take(bw.VM, {}, PLAN, lambda s: None, token=TOKEN, tunnel=FakeTunnel([]), open_=FakeConsole(given),
                 clock=clock, sleep=clock.sleep, now=NOW.timestamp)
    text = str(got.value)
    assert "pas du coffre du poste" in text and said in text and f"`{key}`" in text, text
    assert unsaid is None or unsaid not in text, text
    assert VAULT_GUID not in text and "another-vault" not in text and "rg-other" not in text, "a name printed"
    assert asked == [], "a job looked for by its time, or followed"



# ── BNC3b, review round 2: the point the 📸 route took, judged again ─────────

def test_the_point_taken_is_judged_again_against_the_quarantines_read_again(tmp_path, monkeypatch):
    """An isolation opened during the job (or one still open): the new point is in it — refused."""
    w = _world(tmp_path, point=_at(hours=3))
    _cycle(w, action="isolate_vm", verified_at=_at(minutes=30))
    env = _env(w, monkeypatch)
    clean, why = bsn.rejudge(bw.VM, env, str(w.config), _at(minutes=5).timestamp(), now=NOW.timestamp())
    assert clean is False and "pris dans une quarantaine" in why and "sans levée lue" in why
    clean, why = bsn.rejudge(bw.VM, env, str(w.config), _at(hours=1).timestamp(), now=NOW.timestamp())
    assert clean is True, why


def test_a_point_taken_that_cannot_be_judged_again_is_refused(tmp_path, monkeypatch):
    w = _world(tmp_path, point=_at(hours=3))            # no cycle file on Imladris: the history unread
    clean, why = bsn.rejudge(bw.VM, _env(w, monkeypatch), str(w.config), _at(minutes=5).timestamp(),
                             now=NOW.timestamp())
    assert clean is False and "ne se rejuge pas" in why
