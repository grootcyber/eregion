"""MSK2 (#762) — no subscription's id in what the CLI shows a human; no webhook from the shell.

1. The masking itself (glorfindel/masking.py): an ARM id is said by its name and group, a
   subscription's id left bare becomes « <abonnement> »; a text without one is unchanged.
2. Every path IML1c left out: Azure's own error text at the CLI's boundary, a refusal, the
   refusal of an ambiguous short name, the decision rendered (explanation, reasoning,
   escalation reason, « Glorfindel agent error »), `release`, `unblock`, `snapshot`, `list`,
   `door`, `jobs`, `reset`. The signal, the state and the journals keep the full id, and every
   command still takes one: only the display changes, never what the model sees.
3. The suite's hygiene: no webhook nor bot variable from the developer's shell
   (tests/unit/conftest.py, `drop_alerting_env`).

No Azure call, no model call, no Discord call. Every identifier is made up (repository public).
Mutants M4950–M4959 (scripts/mutants/MSK2.py) are measured here.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from glorfindel import masking

ROOT = Path(__file__).resolve().parents[2]
SUB = "00000000-0000-0000-0000-0000000000cc"
SUB2 = "00000000-0000-0000-0000-0000000000dd"
RG, RG_B = "rg-example-a", "rg-example-b"


def _vm(name: str = "vm-example-01", rg: str = RG, sub: str = SUB) -> str:
    return f"/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{name}"


VM = _vm()
NSG = f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Network/networkSecurityGroups/nsg-a"
FORBIDDEN = (f"(AuthorizationFailed) The client 'agent' with object id '11111111-2222-3333-4444-555555555555' "
             f"does not have authorization to perform action 'Microsoft.Network/networkSecurityGroups/write' "
             f"over scope '{NSG}' or the scope is invalid.")


def _clean(output: str) -> None:
    flat = "".join(str(output).split())             # a line wrapped by the terminal is read whole
    assert SUB not in flat.lower() and SUB2 not in flat.lower(), output
    assert "/subscriptions/" not in flat.lower() and "subscriptions/" not in flat.lower(), output


def _run(args, **kw):
    from glorfindel import cli
    return CliRunner().invoke(cli.cli, args, terminal_width=200, **kw)


# ── 1. The masking ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("rid,said", [
    (VM, f"vm-example-01 (groupe {RG})"),
    (VM + "/", f"vm-example-01 (groupe {RG})"),
    (VM.replace("resourceGroups", "resourcegroups").replace("/subscriptions/", "/SUBSCRIPTIONS/"),
     f"vm-example-01 (groupe {RG})"),
    (NSG + "/securityRules/glorfindel-deny", f"nsg-a/glorfindel-deny (groupe {RG})"),
    (f"/subscriptions/{SUB}/resourceGroups/{RG}", f"groupe {RG}"),
    (f"/subscriptions/{SUB}", "l'abonnement"),
    (f"/subscriptions/{SUB}/providers/Microsoft.Authorization/roleDefinitions/rd-1", "rd-1"),
    ("vm-example-01", "vm-example-01"),
    ("", ""),
])
def test_an_arm_id_is_said_by_its_name_and_group(rid, said):
    assert masking.resource_said(rid) == said
    _clean(masking.resource_said(rid))


@pytest.mark.parametrize("text", [
    FORBIDDEN,
    f"Operation returned an invalid status 'Forbidden' for url "
    f"https://management.azure.com{VM}?api-version=2024-07-01",
    f"https://management.azure.com/subscriptions%2F{SUB}%2FresourceGroups%2F{RG}",
    f"The subscription '{SUB}' could not be found.",
    f"abonnement {SUB.upper()} refusé",
    f"recovery point {NSG.replace('Microsoft.Network/networkSecurityGroups/nsg-a', '')}providers/"
    f"Microsoft.RecoveryServices/vaults/rsv/backupFabrics/Azure/protectionContainers/"
    f"iaasvmcontainer;iaasvmcontainerv2;{RG};vm/protectedItems/vm;iaasvmcontainerv2;{RG};vm/recoveryPoints/42",
    f"subscriptions/{SUB}/resourceGroups/{RG} (without its slash); [{VM}]; \"{VM}\", {VM}.",
])
def test_no_subscription_id_is_left_in_a_text(text):
    _clean(masking.ids_masked(text, environ={}))


def test_what_carries_no_id_is_unchanged_and_the_names_stay():
    plain = "403 runCommand — glorfindel-deny-all (priority 100), job 11111111-2222-3333-4444-555555555555"
    assert masking.ids_masked(plain, environ={}) == plain           # a GUID that is no subscription stays
    said = masking.ids_masked(FORBIDDEN, environ={})
    assert f"over scope 'nsg-a (groupe {RG})' or the scope is invalid." in said
    assert "object id '11111111-2222-3333-4444-555555555555'" in said
    assert masking.ids_masked(f"see {VM}.", environ={}) == f"see vm-example-01 (groupe {RG})."
    assert masking.ids_masked(None, environ={}) == ""


def test_the_environment_s_subscription_is_masked_even_bare():
    """A bare GUID nothing names, the one this environment calls its subscription."""
    text = f"deployment failed in {SUB2}"
    assert SUB2 in masking.ids_masked(text, environ={})
    for name in ("AZURE_SUBSCRIPTION_ID", "ARM_SUBSCRIPTION_ID", "EREGION_BANC_SUBSCRIPTION_ID"):
        assert masking.ids_masked(text, environ={name: SUB2.upper()}) == "deployment failed in <abonnement>"
    assert masking.ids_masked(text, environ={"AZURE_SUBSCRIPTION_ID": "not-a-guid"}) == text
    # One cited by an ARM id of the text is masked wherever else the text says it.
    _clean(masking.ids_masked(f"{VM} ({SUB})", environ={}))


def test_only_the_cli_masks_never_what_the_model_sees():
    """The masking is the display's: nothing of the graph, the prompt or the cycle imports it."""
    users = []
    for path in (ROOT / "glorfindel").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import) else
                     [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            if any(n == "glorfindel.masking" or n.endswith(".masking") for n in names):
                users.append(path.relative_to(ROOT).as_posix())
    assert users == ["glorfindel/cli.py"]


# ── 2. The paths of the CLI ───────────────────────────────────────────────────────────

@pytest.fixture
def recorded(monkeypatch):
    """The manual actions journal, kept in memory: it keeps the full id (it is the machine's)."""
    from glorfindel import cli
    lines: list[tuple] = []
    monkeypatch.setattr(cli, "_record_manual_action", lambda action, rid, outcome, *a, **k:
                        lines.append((action, rid, outcome)))
    monkeypatch.setattr("glorfindel.discovery.AssetRegistry", lambda: SimpleNamespace(all=lambda: []))
    monkeypatch.setattr("glorfindel.actions.active_isolations", lambda: [])
    monkeypatch.setattr("glorfindel.actions.active_blocks", lambda: [])
    return lines


def _connector(monkeypatch, **methods):
    made = []

    def factory(dry_run=False):
        c = SimpleNamespace(dry_run=dry_run, **methods)
        made.append(c)
        return c
    monkeypatch.setattr("glorfindel.actions.AzureConnector", factory)
    return made


def test_azure_s_error_at_the_boundary_is_said_without_the_subscription(monkeypatch, recorded):
    def refused(*a, **k):
        raise RuntimeError(FORBIDDEN)
    _connector(monkeypatch, release_isolation=refused)
    monkeypatch.setattr("glorfindel.gestures.release_needed", lambda c, rid: True)
    out = _run(["release", VM, "--yes"])
    assert out.exit_code == 1, out.output
    assert "✗ RuntimeError" in out.output and f"nsg-a (groupe {RG})" in " ".join(out.output.split())
    _clean(out.output)


def test_a_refusal_is_said_without_the_subscription(monkeypatch, recorded):
    """A ClickException of any command is masked at the boundary too."""
    def unreadable(*a, **k):
        raise RuntimeError(FORBIDDEN)
    _connector(monkeypatch, observed_actors=unreadable)
    monkeypatch.setattr("glorfindel.actions._load_isolation_state", lambda rid: None)
    out = _run(["door", VM])
    assert out.exit_code != 0 and "la porte ne se lit pas" in out.output, out.output
    _clean(out.output)

    # A refusal whose own text carries the id (another restore running on it): masked by the boundary.
    from glorfindel import cli
    monkeypatch.setattr(cli, "_backup_vault_from_config", lambda v: ("rsv-example", "rg-backup", "stexample"))
    monkeypatch.setattr("glorfindel.jobs.restore_in_progress", lambda vm: f"un restore tourne déjà sur {VM}")
    busy = _run(["restore", VM, "--before", "2026-10-29T07:30:00Z", "--yes"])
    assert busy.exit_code != 0 and "Restore refusé : un restore tourne déjà sur vm-example-01" in busy.output, \
        busy.output
    _clean(busy.output)


def test_door_says_its_scopes_and_errors_without_the_subscription(monkeypatch, recorded):
    seen = {"since": "a", "until": "b", "verdict": "aucun geste", "actors": [], "scopes": [VM],
            "unreadable": [f"lecture refusée sur {VM}"],
            "reads": [{"how": "activity", "what": "log", "error": FORBIDDEN}]}
    _connector(monkeypatch, observed_actors=lambda *a, **k: dict(seen),
               observed_rights=lambda ids, rid, scopes=(), reading=None: {
                   "reads": [{"what": "rôles", "scope": f"/subscriptions/{SUB}/resourceGroups/{RG}",
                              "error": FORBIDDEN}]})
    monkeypatch.setattr("glorfindel.actions._load_isolation_state", lambda rid: None)
    out = _run(["door", VM])
    assert out.exit_code == 0, out.output
    assert f"sur groupe {RG}" in out.output
    _clean(out.output)
    raw = _run(["door", VM, "--json"])                  # the facts as JSON keep the ids: asked for
    assert raw.exit_code == 0 and VM in raw.output


def test_two_vms_of_one_name_are_said_by_their_group_never_their_ids(monkeypatch, recorded):
    monkeypatch.setattr("glorfindel.actions.active_isolations", lambda: [{"resource_id": VM}])
    monkeypatch.setattr("glorfindel.discovery.AssetRegistry", lambda: SimpleNamespace(all=lambda: [
        SimpleNamespace(resource_id=_vm(rg=RG_B)), SimpleNamespace(resource_id=_vm(sub=SUB2))]))
    out = _run(["release", "vm-example-01", "--yes"])
    assert out.exit_code != 0 and "several VMs have this name" in out.output, out.output
    said = " ".join(out.output.split())
    assert f"vm-example-01 (groupe {RG}), abonnement n°1" in said
    assert f"vm-example-01 (groupe {RG}), abonnement n°2" in said
    assert f"vm-example-01 (groupe {RG_B})" in said and "glorfindel list --ids" in said
    _clean(out.output)
    full = _run(["release", VM, "--dry-run"])            # the full id is still taken
    assert full.exit_code == 0, full.output


def _decision(**over) -> dict:
    state = {"action": "release_isolation", "confidence": 0.9, "escalate": True,
             "explanation": f"VM {VM} restored.",
             "reasoning": f"The signal names {VM} in subscription {SUB} — [bold]sure[/bold].",
             "escalation_reason": f"check {NSG} first", "outcome": {}}
    state.update(over)
    return state


def test_the_decision_is_rendered_without_the_subscription_and_kept_whole(capsys):
    from glorfindel import cli
    state = _decision()
    before = dict(state)
    cli._render_decision(state, dry_run=False)
    out = capsys.readouterr().out
    _clean(out)
    said = " ".join(out.split())
    assert f"VM vm-example-01 (groupe {RG}) restored." in said and f"check nsg-a (groupe {RG}) first" in said
    assert "<abonnement>" in said and "[bold]sure[/bold]" in said   # the model's words, as said: no markup
    assert state == before                               # the state, the cycle's, keeps the ids


@pytest.mark.parametrize("agent_fails", [False, True])
def test_restore_wait_renders_the_recovery_s_decision_without_the_subscription(tmp_path, monkeypatch,
                                                                                agent_fails, recorded):
    from glorfindel import cli
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "_backup_vault_from_config", lambda v: ("rsv-example", "rg-backup", "stexample"))
    _connector(monkeypatch, restore_from_backup=lambda *a, **k: {
        "recovery_point_time": "2026-10-29 08:00:00+00:00", "run_command_neutralized": True})
    monkeypatch.setattr("glorfindel.actions._load_isolation_state", lambda rid: None)
    signals = []
    monkeypatch.setattr(cli, "_write_signal", lambda sig: signals.append(sig) or tmp_path / "recovery.json")

    class Agent:
        def __init__(self, **kw):
            pass

        def respond(self, sig):
            if agent_fails:
                raise RuntimeError(f"model refused for {sig['resource_id']}")
            return _decision(explanation=f"lifting {sig['resource_id']}")
    monkeypatch.setattr("glorfindel.agent.GlorfindelAgent", Agent)
    out = _run(["restore", VM, "--before", "2026-10-29T07:30:00Z", "--yes", "--wait"])
    assert out.exit_code == 0, out.output
    _clean(out.output)
    said = " ".join(out.output.split())
    assert (f"Glorfindel agent error: model refused for vm-example-01 (groupe {RG})" if agent_fails
            else f"lifting vm-example-01 (groupe {RG})") in said
    assert signals and signals[0]["resource_id"] == VM   # the signal keeps the full id


def test_release_says_the_vm_by_its_name_and_group(monkeypatch, recorded):
    _connector(monkeypatch, release_isolation=lambda rid: {"status": "released", "nsg": NSG, "vm": rid})
    monkeypatch.setattr("glorfindel.gestures.release_needed", lambda c, rid: True)
    dry = _run(["release", VM, "--dry-run"])
    assert dry.exit_code == 0 and f"Resource : vm-example-01 (groupe {RG})" in dry.output, dry.output
    _clean(dry.output)
    out = _run(["release", VM, "--yes"])
    assert out.exit_code == 0 and "Isolation released" in out.output, out.output
    _clean(out.output)
    assert recorded[-1][:2] == ("release_isolation", VM) and recorded[-1][2]["nsg"] == NSG   # the journal keeps it


def test_a_partial_release_says_what_stays_without_the_subscription(monkeypatch, recorded):
    _connector(monkeypatch, release_isolation=lambda rid: {"status": "release_partial", "failed": [FORBIDDEN]})
    monkeypatch.setattr("glorfindel.gestures.release_needed", lambda c, rid: True)
    out = _run(["release", VM, "--yes"])
    assert out.exit_code == 2 and "partiellement levée" in out.output, out.output
    _clean(out.output)


def test_unblock_says_the_vm_and_its_rules_without_the_subscription(monkeypatch, recorded):
    rule = NSG + "/securityRules/glorfindel-block-203-0-113-5"
    _connector(monkeypatch, unblock_ip=lambda ip, rid: {"status": "unblocked", "deleted_rules": [rule]})
    out = _run(["unblock", "203.0.113.5", VM, "--yes"])
    assert out.exit_code == 0, out.output
    said = " ".join(out.output.split())
    assert f"Resource : vm-example-01 (groupe {RG})" in said
    assert f"nsg-a/glorfindel-block-203-0-113-5 (groupe {RG})" in said
    _clean(out.output)
    assert recorded[-1][1] == VM
    _connector(monkeypatch, unblock_ip=lambda ip, rid: {"status": "unblock_partial", "failed": [FORBIDDEN]})
    partial = _run(["unblock", "203.0.113.5", VM, "--yes"])
    assert partial.exit_code == 2, partial.output
    _clean(partial.output)


@pytest.mark.parametrize("args", [["--dry-run"], ["--yes"], ["--yes", "--wait"]])
def test_snapshot_says_the_vm_and_the_vault_by_their_names(monkeypatch, recorded, args):
    from glorfindel import cli
    vault = f"/subscriptions/{SUB}/resourceGroups/rg-backup/providers/Microsoft.RecoveryServices/vaults/rsv-example"
    monkeypatch.setattr(cli, "_backup_vault_from_config", lambda v: (vault, "rg-backup", "stexample"))
    _connector(monkeypatch, snapshot=lambda rid, **k: "rsv:rsv-example/rg-backup/job-1",
               verify_snapshot=lambda snap: {"verified": False, "detail": f"no point yet on {VM}"})
    monkeypatch.setattr("glorfindel.jobs.start_snapshot", lambda rid, c, v, vault_rg="": {
        "job_id": "j-1", "snap_id": "rsv:rsv-example/rg-backup/job-1"})
    out = _run(["snapshot", VM, *args])
    assert out.exit_code == 0, out.output
    said = " ".join(out.output.split())
    assert f"Resource : vm-example-01 (groupe {RG})" in said and "Vault : rsv-example" in said
    if args == ["--yes"]:
        assert "glorfindel jobs vm-example-01 --refresh" in said
    if args == ["--yes", "--wait"]:
        assert f"no point yet on vm-example-01 (groupe {RG})" in said
    _clean(out.output)
    if args != ["--dry-run"]:
        assert recorded[-1][:2] == ("snapshot", VM)


def test_jobs_says_its_next_step_by_the_vm_s_name(monkeypatch):
    job = {"job_id": "j-1", "type": "restore", "status": "Completed", "rg": RG,
           "error": FORBIDDEN, "snap_id": "rsv:rsv-example/rg-backup/job-1"}
    monkeypatch.setattr("glorfindel.jobs.get_job", lambda vm: dict(job))
    out = _run(["jobs", VM])
    assert out.exit_code == 0, out.output
    said = " ".join(out.output.split())
    assert "2. glorfindel release vm-example-01 --yes" in said and f"az vm start -g {RG} -n vm-example-01" in said
    _clean(out.output)

    def poll_fails(job, connector):
        raise RuntimeError(FORBIDDEN)
    monkeypatch.setattr("glorfindel.jobs.get_job", lambda vm: {**job, "status": "InProgress", "error": ""})
    monkeypatch.setattr("glorfindel.jobs.refresh_job", poll_fails)
    _connector(monkeypatch)
    polled = _run(["jobs", VM, "--refresh"])
    assert polled.exit_code == 0 and "Azure poll error" in polled.output, polled.output
    _clean(polled.output)


def _listed(monkeypatch, isolations=(), blocks=(), discovered=()):
    monkeypatch.setattr("glorfindel.actions.active_isolations", lambda: [dict(i) for i in isolations])
    monkeypatch.setattr("glorfindel.actions.active_blocks", lambda: [dict(b) for b in blocks])
    monkeypatch.setattr("glorfindel.discovery.AssetRegistry", lambda: SimpleNamespace(
        all=lambda: [SimpleNamespace(resource_id=r) for r in discovered]))


def test_list_says_each_vm_by_its_name_and_group_and_the_ids_when_asked(monkeypatch):
    _listed(monkeypatch,
            isolations=[{"resource_id": VM, "isolated_at": "2026-10-29T06:00:00+00:00", "placements": [],
                         "drain": {"status": "failed", "error": FORBIDDEN}}],
            blocks=[{"resource_id": VM, "ip": "203.0.113.5", "blocked_at": "2026-10-29T06:00:00+00:00"}])
    out = _run(["list"])
    assert out.exit_code == 0, out.output
    said = " ".join(out.output.split())
    assert f"vm-example-01 (groupe {RG})" in said and "open sessions not cut" in said
    for hint in ("glorfindel release vm-example-01 --yes", "glorfindel unblock 203.0.113.5 vm-example-01 --yes",
                 "glorfindel reset vm-example-01 --yes"):
        assert hint in said, said
    _clean(out.output)
    ids = _run(["list", "--ids"])                         # asked for: this terminal only
    flat = "".join(ids.output.split())
    assert ids.exit_code == 0 and VM in flat and f"glorfindelrelease{VM}--yes" in flat


def test_list_never_suggests_a_name_two_vms_hold(monkeypatch):
    """The short name of two VMs is refused by every command: the hint asks for the id."""
    _listed(monkeypatch, isolations=[{"resource_id": VM, "isolated_at": "2026-10-29T06:00:00+00:00",
                                      "placements": []}],
            discovered=[VM, _vm(rg=RG_B)])
    out = _run(["list"])
    assert out.exit_code == 0, out.output
    said = " ".join(out.output.split())
    assert "glorfindel release vm-example-01 --yes" not in said
    assert "glorfindel release <id: glorfindel list --ids> --yes" in said
    assert f"vm-example-01 (groupe {RG_B})" in said
    _clean(out.output)


def test_reset_says_what_stays_without_the_subscription(monkeypatch, recorded):
    _connector(monkeypatch, sweep_vm_rules=lambda rid, dry_run=False: {
        "failed": [FORBIDDEN], "deleted": [NSG + "/securityRules/glorfindel-x"], "kept_perimeter": [],
        "note": ""})
    out = _run(["reset", VM, "--from-azure", "--yes"])
    assert out.exit_code == 2, out.output
    _clean(out.output)
