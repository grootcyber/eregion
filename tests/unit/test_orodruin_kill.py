"""M-1: orodruin-kill stops what runs, whatever the operator's CLI context — it revokes on
the contract's subscription and never concludes « nothing to revoke » from a listing of
another one; it cancels the chaos experiments still running, closes the exercise windows
still open, and says what is left in flight. Mutants M191–M193
(scripts/mutation_check.py) are measured here; the order of the steps (M66) in
test_orodruin.py."""
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import eregion_core.orodruin as orodruin
from eregion_core import exercise

KILL = Path(__file__).resolve().parents[2] / "infra" / "orodruin" / "kill.py"
CONTRACT, ELSEWHERE = "sub-contract-0001", "sub-elsewhere-0002"
VM = (f"/subscriptions/{CONTRACT}/resourceGroups/rg-orodruin/providers/Microsoft.Compute"
      "/virtualMachines/vm-orodruin")
GONDOLIN = (f"/subscriptions/{CONTRACT}/resourceGroups/rg-celebrimbor/providers"
            "/Microsoft.Compute/virtualMachines/vm-celebrimbor-gondolin")
ASSIGNMENTS = [
    f"/subscriptions/{CONTRACT}/resourceGroups/rg-celebrimbor/providers/Microsoft.Authorization/roleAssignments/a1",
    f"/subscriptions/{CONTRACT}/providers/Microsoft.Authorization/roleAssignments/a2",
]
CHANNEL = "https://storodruin.blob.core.windows.net/exercises"
CRED = SimpleNamespace(get_token=lambda scope: SimpleNamespace(token="tok"))
# The real clock, not a fixed date: the exercise windows are purged PURGE_AFTER_S after their last
# moment, by the real clock (eregion_core/exercise.py) — a fixed date turned these tests red seven
# days after it.
NOW = datetime.now(timezone.utc).replace(second=0, microsecond=0)


@pytest.fixture(scope="module")
def kill_script():
    spec = importlib.util.spec_from_file_location("orodruin_kill", KILL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeAz:
    """`az` as the operator's CLI sees it: a current subscription — the wrong one by
    default — role assignments per subscription, and the bench's chaos experiments."""

    def __init__(self, current=ELSEWHERE, experiments=None, cancel_to="Cancelled"):
        self.current = current
        self.assignments = {CONTRACT: list(ASSIGNMENTS), ELSEWHERE: []}
        self.experiments = experiments or {}  # name -> statuses of its executions
        self.cancel_to = cancel_to
        self.vm_principal = "oid-1"
        self.deletes = True
        self.calls = []

    def _sub(self, args):
        return args[args.index("--subscription") + 1] if "--subscription" in args else self.current

    def __call__(self, args):
        self.calls.append(args)
        if args[:3] == ["role", "assignment", "list"]:
            return json.dumps(self.assignments.get(self._sub(args), []))
        if args[:3] == ["role", "assignment", "delete"]:
            ids = args[args.index("--ids") + 1:]
            if self.deletes:
                for sub in self.assignments:
                    self.assignments[sub] = [i for i in self.assignments[sub] if i not in ids]
            return ""
        if args[:2] == ["vm", "show"]:
            return self.vm_principal + "\n"
        if args[:2] == ["vm", "deallocate"]:
            return ""
        url = args[args.index("--url") + 1] if "--url" in args else ""
        path = url.split("?")[0]
        if args[:3] == ["rest", "--method", "get"] and path.endswith("/experiments"):
            if f"/subscriptions/{CONTRACT}/resourceGroups/rg-celebrimbor/" not in path:
                return json.dumps({"value": []})
            return json.dumps({"value": [_experiment(n) for n in self.experiments]})
        name = path.split("/experiments/")[1].split("/")[0] if "/experiments/" in path else ""
        if args[:3] == ["rest", "--method", "get"] and path.endswith("/executions"):
            return json.dumps({"value": [{"properties": {"status": s}} for s in self.experiments[name]]})
        if args[:3] == ["rest", "--method", "post"] and path.endswith("/cancel"):
            self.experiments[name] = [self.cancel_to if s == "Running" else s
                                      for s in self.experiments[name]]
            return ""
        raise AssertionError(f"unexpected az call: {args}")


def _experiment(name):
    return {"id": f"/subscriptions/{CONTRACT}/resourceGroups/rg-celebrimbor/providers/Microsoft.Chaos/experiments/{name}",
            "name": name,
            "properties": {"selectors": [{"type": "List", "targets": [
                {"id": f"{GONDOLIN}/providers/Microsoft.Chaos/targets/Microsoft-VirtualMachine"}]}]}}


class FakeChannel:
    """The exercises container, as exercise_channel's pull and publish reach it."""

    def __init__(self, windows, status=200, listed_at=None):
        self.blobs = {f"{w['run_id']}.json": json.dumps(w).encode() for w in windows}
        self.status = status
        self.puts = {}
        self.listed_at = listed_at

    def get(self, url, headers=None, params=None, timeout=None):
        if self.status != 200:
            return SimpleNamespace(ok=False, status_code=self.status, content=b"")
        if params and params.get("comp") == "list":
            # Written when its window opened, five minutes ago (SEC-A1b: a window pulled starts
            # within FUTURE_SKEW_S of its blob's creation).
            when = format_datetime(self.listed_at or NOW - timedelta(minutes=5), usegmt=True)
            items = "".join(f"<Blob><Name>{n}</Name><Properties><Last-Modified>"
                            f"{when}</Last-Modified></Properties></Blob>"
                            for n in self.blobs)
            body = f"<EnumerationResults><Blobs>{items}</Blobs><NextMarker/></EnumerationResults>"
            return SimpleNamespace(ok=True, status_code=200, content=body.encode())
        return SimpleNamespace(ok=True, status_code=200, content=self.blobs[url.rsplit("/", 1)[1]])

    def put(self, url, headers=None, data=None, timeout=None):
        self.puts[url.rsplit("/", 1)[1]] = json.loads(data)
        return SimpleNamespace(ok=True, status_code=201)


def _window(run_id, injector="annatar", end=None, expires=NOW + timedelta(hours=1)):
    return {"run_id": run_id, "injector": injector, "kind": "technique",
            "experiment": "T1136.001 create-local-account", "targets": [GONDOLIN.lower()],
            "start": (NOW - timedelta(minutes=5)).isoformat(), "end": end,
            "expires": expires.isoformat()}


def _kill(kill_script, az, *, subscription=CONTRACT, channel=None, vm_id=VM, **kw):
    channel = channel or FakeChannel([])
    inflight, said = [], []
    failures = orodruin.kill(*kill_script.steps(
        "oid-1", vm_id, subscription=subscription, channel=CHANNEL, run=az, credential=CRED,
        get=channel.get, put=channel.put, say=said.append, inflight=inflight, now=NOW, **kw))
    return failures, inflight, said


# ── M191: revoke on the contract's subscription, never the CLI's context ───────────

def test_a_wrong_cli_context_never_concludes_nothing_to_revoke(kill_script):
    """The bug of M-1: in another subscription's context, `--all` listed nothing, and the
    kill said « no role assignment left » and exited 0 with every right intact."""
    az = FakeAz(current=ELSEWHERE)
    failures, _, _ = _kill(kill_script, az)
    assert failures == []
    assert az.assignments[CONTRACT] == []
    listings = [c for c in az.calls if c[:3] == ["role", "assignment", "list"]]
    assert listings and all(c[c.index("--subscription") + 1] == CONTRACT for c in listings)


def test_without_a_declared_subscription_the_vms_own_is_checked(kill_script):
    az = FakeAz(current=ELSEWHERE)
    failures, _, _ = _kill(kill_script, az, subscription="")
    assert failures == [] and az.assignments[CONTRACT] == []


def test_a_declared_subscription_and_the_vms_are_both_checked(kill_script):
    """orodruin.env names a subscription the VM is not in: both are listed, so a wrong
    declaration cannot hide the VM's own assignments."""
    az = FakeAz(current=ELSEWHERE)
    failures, _, _ = _kill(kill_script, az, subscription=ELSEWHERE)
    assert failures == [] and az.assignments[CONTRACT] == []
    listed = {c[c.index("--subscription") + 1] for c in az.calls if c[:3] == ["role", "assignment", "list"]}
    assert listed == {CONTRACT, ELSEWHERE}


def test_assignments_still_listed_after_the_deletion_are_a_failure(kill_script):
    az = FakeAz()
    az.deletes = False
    failures, _, _ = _kill(kill_script, az)
    assert len(failures) == 1 and failures[0].startswith("revoke:") and "still listed" in failures[0]


def test_nothing_listed_proves_nothing_for_a_principal_that_is_not_the_vms(kill_script):
    """PRINCIPAL= mistyped: nothing is listed for it — not « already revoked »."""
    az = FakeAz()
    az.assignments[CONTRACT] = []
    az.vm_principal = "oid-someone-else"
    failures, _, _ = _kill(kill_script, az)
    assert len(failures) == 1 and "nothing proven" in failures[0]


def test_nothing_listed_for_the_vms_identity_is_already_revoked(kill_script):
    az = FakeAz()
    az.assignments[CONTRACT] = []
    failures, _, said = _kill(kill_script, az)
    assert failures == []
    assert any("no role assignment left" in s for s in said)


def test_no_subscription_at_all_proves_nothing(kill_script):
    az = FakeAz()
    failures, _, _ = _kill(kill_script, az, subscription="", vm_id="vm-orodruin")
    assert {f.split(":")[0] for f in failures} == {"revoke", "cancel"}


# ── M192: a chaos experiment still running is cancelled ─────────────────────────────

def test_a_running_experiment_is_cancelled_and_its_vm_named(kill_script):
    """An experiment acts with its own identity: revoking Orodruin's does not stop it."""
    az = FakeAz(experiments={"exp-vm-shutdown": ["Success", "Running"], "exp-old": ["Success"]})
    failures, inflight, _ = _kill(kill_script, az)
    assert failures == []
    cancels = [c for c in az.calls if c[:3] == ["rest", "--method", "post"]]
    assert len(cancels) == 1 and "/experiments/exp-vm-shutdown/cancel" in cancels[0][-1]
    assert any("exp-vm-shutdown" in line and "vm-celebrimbor-gondolin" in line for line in inflight)


def test_an_execution_still_cancelling_is_said_in_flight(kill_script):
    az = FakeAz(experiments={"exp-vm-shutdown": ["Running"]}, cancel_to="Cancelling")
    failures, inflight, _ = _kill(kill_script, az)
    assert failures == []
    assert any("still Cancelling" in line for line in inflight)


def test_an_experiment_id_not_under_arm_is_never_called(kill_script):
    """SEC8: an id read from the listing is a path under ARM, or not called — said in flight."""
    class Odd(FakeAz):
        def __call__(self, args):
            url = args[args.index("--url") + 1] if "--url" in args else ""
            if args[:3] == ["rest", "--method", "get"] and url.split("?")[0].endswith("/experiments") \
                    and "rg-celebrimbor" in url:
                self.calls.append(args)
                return json.dumps({"value": [{**_experiment("exp-odd"), "id": "@other-host.example/x"}]})
            return super().__call__(args)
    az = Odd(experiments={"exp-odd": ["Running"]})
    failures, inflight, _ = _kill(kill_script, az)
    assert not [c for c in az.calls if "--url" in c and "other-host" in c[c.index("--url") + 1]]
    assert any("exp-odd" in line and "not a path under Azure Resource Manager" in line for line in inflight)


def test_a_next_page_outside_arm_is_never_followed(kill_script):
    class Elsewhere(FakeAz):
        def __call__(self, args):
            url = args[args.index("--url") + 1] if "--url" in args else ""
            if url.startswith("https://other-host.example"):
                self.calls.append(args)
                return json.dumps({"value": []})
            if args[:3] == ["rest", "--method", "get"] and url.split("?")[0].endswith("/experiments"):
                self.calls.append(args)
                return json.dumps({"value": [], "nextLink": "https://other-host.example/next"})
            return super().__call__(args)
    az = Elsewhere()
    failures, _, _ = _kill(kill_script, az)
    assert any(f.startswith("cancel") and "outside Azure Resource Manager" in f for f in failures)
    assert not [c for c in az.calls if "--url" in c and "other-host" in c[c.index("--url") + 1]]


def test_the_cancel_comes_after_the_revocation(kill_script):
    az = FakeAz(experiments={"exp-vm-shutdown": ["Running"]})
    _kill(kill_script, az)
    kinds = [" ".join(c[:3]) for c in az.calls]
    assert kinds.index("role assignment delete") < kinds.index("rest --method post")
    assert kinds.index("rest --method post") < kinds.index("vm deallocate --ids")


# ── M193: the windows still open are closed, and what ran is said ───────────────────

def test_the_open_windows_are_closed_and_what_ran_is_said(kill_script):
    channel = FakeChannel([
        _window("r-open"),
        _window("r-fault", injector="gothmog"),
        _window("r-done", end=(NOW - timedelta(minutes=1)).isoformat()),
        _window("r-lapsed", expires=NOW - timedelta(minutes=1)),
    ])
    failures, inflight, _ = _kill(kill_script, FakeAz(), channel=channel)
    assert failures == []
    assert set(channel.puts) == {"r-open.json", "r-fault.json"}
    for w in channel.puts.values():
        assert w["end"] == NOW.isoformat() and w["closed_by"] == "orodruin-kill"
    text = "\n".join(inflight)
    assert "r-open: a Run Command already sent runs to its end on vm-celebrimbor-gondolin" in text
    assert "r-fault: the fault may leave vm-celebrimbor-gondolin down" in text
    assert f"until {NOW + timedelta(seconds=exercise.GRACE_AFTER_S):%H:%M} UTC" in text  # the grace after the close


def test_the_kill_judges_a_blobs_age_by_its_own_moment(kill_script):
    """SEC-A1b (relecture) : le kill saute un blob trop vieux pour être ouvert d'après l'heure qu'on
    lui donne (`steps(now=…)`), jamais d'après l'horloge réelle. Un kill daté d'un autre moment
    sauterait sinon tous les blobs, et dirait à tort qu'aucune fenêtre n'est ouverte."""
    then = NOW - timedelta(days=3)
    window = _window("r-then", expires=then + timedelta(hours=1))
    window["start"] = (then - timedelta(minutes=5)).isoformat()
    channel = FakeChannel([window], listed_at=then - timedelta(minutes=5))
    inflight, said = [], []
    failures = orodruin.kill(*kill_script.steps(
        "oid-1", VM, subscription=CONTRACT, channel=CHANNEL, run=FakeAz(), credential=CRED,
        get=channel.get, put=channel.put, say=said.append, inflight=inflight, now=then))
    assert failures == []
    assert set(channel.puts) == {"r-then.json"} and channel.puts["r-then.json"]["end"] == then.isoformat()


def test_a_vm_a_fault_may_leave_down_is_said_once(kill_script):
    """The cancel step and the fault's window both know gondolin may stay down: one line
    (seen twice in the bench's kill, 26/10)."""
    az = FakeAz(experiments={"exp-vm-shutdown": ["Running"]})
    channel = FakeChannel([_window("r-fault", injector="gothmog")])
    failures, inflight, _ = _kill(kill_script, az, channel=channel)
    assert failures == [] and set(channel.puts) == {"r-fault.json"}
    assert sum("vm-celebrimbor-gondolin down" in line for line in inflight) == 1


def test_a_channel_the_operator_cannot_read_is_a_failure_that_says_when_windows_lapse(kill_script):
    failures, _, _ = _kill(kill_script, FakeAz(), channel=FakeChannel([], status=403))
    assert len(failures) == 1 and failures[0].startswith("close:")
    assert "403" in failures[0] and "at most 2 h after it opened" in failures[0]


def test_no_channel_given_proves_nothing_about_the_windows(kill_script):
    inflight = []
    failures = orodruin.kill(*kill_script.steps(
        "oid-1", VM, subscription=CONTRACT, channel="", run=FakeAz(), say=lambda _: None,
        inflight=inflight))
    assert len(failures) == 1 and failures[0].startswith("close:")


# ── Dry run, exit code, and what is printed ─────────────────────────────────────────

def test_the_kill_dry_run_calls_nothing(kill_script, capsys):
    run = MagicMock()
    assert orodruin.kill(*kill_script.steps("oid-1", VM, subscription=CONTRACT,
                                            channel=CHANNEL, run=run, dry_run=True)) == []
    run.assert_not_called()
    out = capsys.readouterr().out
    assert out.index("role assignment list") < out.index("Microsoft.Chaos/experiments")
    assert out.index("Microsoft.Chaos/experiments") < out.index("vm deallocate")
    assert out.index("vm deallocate") < out.index("close the open windows")
    assert CONTRACT not in out  # never the subscription on screen


def test_an_incomplete_kill_exits_1_and_never_prints_the_subscription(kill_script, monkeypatch, capsys):
    az = FakeAz()
    az.deletes = False
    monkeypatch.setattr(kill_script, "az", az)
    code = kill_script.main(["oid-1", VM, "--subscription", CONTRACT, "--channel", ""])
    out = capsys.readouterr()
    assert code == 1 and "kill INCOMPLETE" in out.err
    assert CONTRACT not in out.out + out.err


# ── R2c (stratus-cible.md §1): the operator cuts the Stratus identity's role ─────────
# Orodruin cannot (AUTHZ_READ_ONLY on the dedicated subscription); kill.py tools the gesture.
# Mutants M4440–M4449 (scripts/mutants/R2c.py) are measured here.

STRATUS_OID = "oid-stratus-11112222"
STRATUS_SUB = "sub-stratus-dedicated-9999"
STRATUS_ASSIGNMENTS = [
    f"/subscriptions/{STRATUS_SUB}/providers/Microsoft.Authorization/roleAssignments/s1",
    f"/subscriptions/{STRATUS_SUB}/resourceGroups/rg-stratus/providers"
    "/Microsoft.Authorization/roleAssignments/s2",
]


class StratusAz:
    """`az` for the Stratus identity's assignments on the dedicated subscription. The listing
    answers whatever --assignee-object-id/--subscription it is given; delete removes by --ids."""

    def __init__(self, assignments=None, deletes=True):
        self.assignments = list(STRATUS_ASSIGNMENTS if assignments is None else assignments)
        self.deletes = deletes
        self.calls = []

    def __call__(self, args):
        self.calls.append(args)
        if args[:3] == ["role", "assignment", "list"]:
            return json.dumps(self.assignments)
        if args[:3] == ["role", "assignment", "delete"]:
            ids = args[args.index("--ids") + 1:]
            if self.deletes:
                self.assignments = [i for i in self.assignments if i not in ids]
            return ""
        raise AssertionError(f"unexpected az call: {args}")


def test_the_stratus_role_is_revoked_and_proven_gone(kill_script):
    az = StratusAz()
    said = []
    # the subscription may arrive quoted (a Terraform output): it is stripped, like the contract's
    step = kill_script.stratus_revoke_step(STRATUS_OID, f'"{STRATUS_SUB}"', run=az, say=said.append)
    step()
    assert az.assignments == []  # every assignment deleted
    assert any("no role assignment left for the Stratus identity" in s for s in said)
    lst = [c for c in az.calls if c[:3] == ["role", "assignment", "list"]]
    # M191: --all so a resource-group-scoped assignment does not escape; by the oid; on the sub
    assert lst and all("--all" in c for c in lst)
    assert all(c[c.index("--assignee-object-id") + 1] == STRATUS_OID for c in lst)
    assert all(c[c.index("--subscription") + 1] == STRATUS_SUB for c in lst)  # unquoted
    assert len(lst) >= 2  # read again AFTER the deletion, never assumed
    deletes = [c for c in az.calls if c[:3] == ["role", "assignment", "delete"]]
    assert deletes and all(c[c.index("--subscription") + 1] == STRATUS_SUB for c in deletes)


def test_a_stratus_role_still_listed_after_the_deletion_is_an_error(kill_script):
    az = StratusAz(deletes=False)
    step = kill_script.stratus_revoke_step(STRATUS_OID, STRATUS_SUB, run=az, say=lambda _: None)
    with pytest.raises(RuntimeError, match="still listed"):
        step()


def test_nothing_to_revoke_is_the_proof_not_a_failure(kill_script):
    """Unlike Orodruin's own revoke, an empty listing for the Stratus identity is « rien à
    révoquer » — the proof itself, not « nothing proven »: no delete, no error."""
    az = StratusAz(assignments=[])
    said = []
    step = kill_script.stratus_revoke_step(STRATUS_OID, STRATUS_SUB, run=az, say=said.append)
    step()  # no raise
    assert not any(c[:3] == ["role", "assignment", "delete"] for c in az.calls)
    assert any("no role assignment left" in s for s in said)


def test_the_stratus_step_is_absent_without_an_identity(kill_script):
    assert kill_script.stratus_revoke_step(STRATUS_OID, "") is None
    assert kill_script.stratus_revoke_step("", STRATUS_SUB) is None
    assert kill_script.stratus_revoke_step("", "") is None
    assert kill_script.stratus_revoke_step("   ", STRATUS_SUB) is None


def test_the_stratus_dry_run_lists_but_deletes_nothing(kill_script):
    az = StratusAz()
    said = []
    step = kill_script.stratus_revoke_step(STRATUS_OID, STRATUS_SUB, run=az, dry_run=True,
                                           say=said.append)
    step()
    assert az.calls == []  # dry-run returns "[]" without ever calling az
    assert az.assignments == STRATUS_ASSIGNMENTS  # nothing deleted
    assert any("[dry-run] az role assignment list" in s for s in said)
    assert STRATUS_SUB not in " ".join(said)  # the dedicated subscription is redacted


def test_the_stratus_subscription_is_never_printed(kill_script):
    az = StratusAz()
    said = []
    step = kill_script.stratus_revoke_step(STRATUS_OID, STRATUS_SUB, run=az, say=said.append)
    step()
    joined = " ".join(said)
    assert STRATUS_SUB not in joined and "<subscription>" in joined


def test_main_wires_the_stratus_revocation_and_hides_its_subscription(kill_script, monkeypatch,
                                                                       capsys):
    monkeypatch.setattr(kill_script, "az", MagicMock(return_value="[]"))
    code = kill_script.main(["oid-1", VM, "--subscription", CONTRACT, "--channel", CHANNEL,
                             "--stratus-oid", STRATUS_OID,
                             "--stratus-subscription", STRATUS_SUB, "--dry-run"])
    out = capsys.readouterr().out
    assert code == 0
    assert "--assignee-object-id" in out and STRATUS_OID in out
    assert STRATUS_SUB not in out  # redacted, like the contract's subscription
    assert CONTRACT not in out


def test_main_without_a_stratus_identity_does_no_stratus_revocation(kill_script, monkeypatch,
                                                                     capsys):
    monkeypatch.setattr(kill_script, "az", MagicMock(return_value="[]"))
    code = kill_script.main(["oid-1", VM, "--subscription", CONTRACT, "--channel", CHANNEL,
                             "--dry-run"])
    out = capsys.readouterr().out
    assert code == 0 and "--assignee-object-id" not in out
