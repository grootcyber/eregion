"""RST1 (#680): the restore from the console, as the bench met it on 09/11 (rejeu T1486).

Under the console's pair, `glorfindel restore` neutralized the last Run Command, deallocated the
VM, then met a 403 `LinkedAuthorizationFailed` at the trigger: `listKeys` missing on the staging
account. The refusal, cut at 300 characters, lost the action it named; the VM stayed deallocated,
unsaid, for three hours. Once the right was given, the job failed in 4.5 s (code 400625: the
`restoreDiskLunList` of a restore in place), and the job search, which kept only an InProgress
job, said « not found after trigger ». What is held here, on a fake Azure (the permissions API per
scope, the VM's writes in their order, the trigger's answer, the vault's jobs), no Azure, no model:
  - a right a restore needs, missing, refuses it before any write on the VM, and names it — on
    the vault, the VM, the staging account; wildcards and notActions read as Azure reads them;
    Run Command missing on the VM is no refusal (SEC17); permissions unreadable: said, and the
    restore goes on as before;
  - Azure's refusal at the trigger is said whole — the action and the kind of scope, never an id
    — with the VM deallocated and the gesture to start it again;
  - the payload of a restore in place carries no list of LUNs, with or without data disks;
  - a job already finished is read with its error, the restore's and the snapshot's; the search
    lasts at least 2 min; nothing found: « lire les jobs du coffre avant de relancer », the VM
    deallocated;
  - the CLI says which kind of identity it restores under, never an id (h).
"""
from __future__ import annotations

import json
import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from glorfindel.providers.azure.restore_rights import (RESTORE_ACTION, STAGING_LIST_KEYS, explain_refusal,
                                                       job_error_text, masked, scope_kind)

_RID = "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm"
_AFTER_EVERY_POINT = "2999-01-01T00:00:00+00:00"
_OBJECT_ID = "1b2c3d4e-0000-4000-8000-00000000abcd"
_CLIENT_ID = "9f8e7d6c-0000-4000-8000-00000000dcba"
_SUB_ID = "00000000-1111-4222-8333-444444444444"

# What the console holds when every right is there: Reader, Restore on the group, Restore Staging
# on the staging account, Restore Neutralize on the VM.
_READER = {"actions": ["*/read"], "notActions": []}
_RESTORE = {"actions": ["Microsoft.Compute/virtualMachines/deallocate/action",
                        "Microsoft.Compute/virtualMachines/start/action",
                        "Microsoft.Compute/virtualMachines/write", "Microsoft.Compute/disks/write",
                        RESTORE_ACTION, "Microsoft.Storage/storageAccounts/write"], "notActions": []}
_STAGING = {"actions": [STAGING_LIST_KEYS], "notActions": []}
_NEUTRALIZE = {"actions": ["Microsoft.Compute/virtualMachines/runCommand/action"], "notActions": []}


def _all_rights() -> dict:
    return {"vault": [_READER, _RESTORE], "vm": [_READER, _RESTORE, _NEUTRALIZE],
            "staging": [_READER, _RESTORE, _STAGING]}


def _linked_refusal() -> str:
    """The 403 of 09/11, its shape as ARM gives it (ids are examples): the action it names lies
    past the 300th character."""
    vault = (f"/subscriptions/{_SUB_ID}/resourceGroups/rg/providers/Microsoft.RecoveryServices/vaults/rsv"
             "/backupFabrics/Azure/protectionContainers/IaasVMContainer;iaasvmcontainerv2;rg;vm")
    staging = f"/subscriptions/{_SUB_ID}/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/st"
    message = (f"The client '{_CLIENT_ID}' with object id '{_OBJECT_ID}' has permission to perform action "
               f"'{RESTORE_ACTION}' on scope '{vault}'; however, it does not have permission to perform "
               f"action(s) '{STAGING_LIST_KEYS}' on the linked scope(s) '{staging}' (respectively) or the "
               "linked scope(s) are invalid.")
    return json.dumps({"error": {"code": "LinkedAuthorizationFailed", "message": message}})


class FakeRestoreAzure:
    """Just enough of Azure for restore_from_backup and snapshot: what each call did, in order."""

    def __init__(self, monkeypatch, *, rights=None, trigger=(202, ""), jobs=None, data_disks=(),
                 details=None):
        from glorfindel.actions import AzureConnector
        self.events: list[tuple] = []
        self.rights = _all_rights() if rights is None else rights    # where → entries, or an HTTP status
        self.trigger = trigger
        self.posted: list[dict] = []
        self.sleeps: list[float] = []
        now = datetime.now(timezone.utc)
        self.now = now
        # The vault's jobs, listed again at each attempt: a callable (attempt → jobs) or a list.
        self.jobs = jobs if jobs is not None else (lambda attempt: [_job("restore-1", "Restore", now)])
        self.listings = 0

        client = MagicMock()
        point = MagicMock(properties=MagicMock(recovery_point_time=now - timedelta(hours=1),
                                                recovery_point_tier_details=[]))
        point.name = "rp-1"
        client.recovery_points.list.return_value = [point]
        client.protected_items.get.side_effect = Exception("not found")
        client.backup_jobs.list.side_effect = self._list_jobs
        client.job_details.get.side_effect = lambda vault, rg, name: details.get(name) if details else \
            self._job_named(name)
        self.client = client
        fake_mod = types.ModuleType("azure.mgmt.recoveryservicesbackup")
        fake_mod.RecoveryServicesBackupClient = lambda *a, **k: client
        monkeypatch.setitem(sys.modules, "azure.mgmt.recoveryservicesbackup", fake_mod)

        fake_requests = types.ModuleType("requests")
        fake_requests.Timeout = type("Timeout", (Exception,), {})
        fake_requests.ConnectTimeout = type("ConnectTimeout", (fake_requests.Timeout,), {})
        fake_requests.get = self._get
        fake_requests.post = self._post
        self.requests = fake_requests
        monkeypatch.setitem(sys.modules, "requests", fake_requests)
        monkeypatch.setattr("time.sleep", self.sleeps.append)

        connector = AzureConnector(dry_run=False)
        monkeypatch.setattr(connector, "_ensure_clients", lambda: None)
        monkeypatch.setattr(connector, "_replayable_scripts", lambda rg, vm: [])
        connector._credential = MagicMock()
        connector._subscription_id = "s"
        compute = MagicMock()
        compute.virtual_machines.get.return_value = SimpleNamespace(
            id=_RID, location="westeurope",
            storage_profile=SimpleNamespace(
                os_disk=SimpleNamespace(os_type="Linux"),
                data_disks=[SimpleNamespace(lun=n) for n in data_disks]))
        compute.virtual_machines.begin_run_command.side_effect = self._write("vm.run_command")
        compute.virtual_machines.begin_deallocate.side_effect = self._write("vm.deallocate")
        compute.virtual_machines.begin_start.side_effect = self._write("vm.start")
        connector._compute = compute
        self.connector = connector

    # ── the calls ───────────────────────────────────────────────────────────────

    def _write(self, op):
        def call(*args, **kwargs):
            self.events.append((op,))
            poller = MagicMock()
            poller.done.return_value = True
            return poller
        return call

    @staticmethod
    def _where(url: str) -> str:
        low = url.lower()
        return ("staging" if "/storageaccounts/" in low else "vault" if "/vaults/" in low
                else "vm" if "/virtualmachines/" in low else "?")

    def _get(self, url, headers=None, params=None, timeout=None):
        assert timeout, "every REST call carries a timeout (SEC4c)"
        assert url.endswith("/providers/Microsoft.Authorization/permissions"), url
        where = self._where(url)
        self.events.append(("permissions", where))
        answer = self.rights.get(where, [])
        if isinstance(answer, int):
            return SimpleNamespace(ok=False, status_code=answer, text=json.dumps(
                {"error": {"code": "AuthorizationFailed", "message": f"client '{_CLIENT_ID}' refused"}}))
        return SimpleNamespace(ok=True, status_code=200, text="", json=lambda: {"value": answer})

    def _post(self, url, json=None, headers=None, timeout=None):
        assert timeout, "every REST call carries a timeout (SEC4c)"
        self.events.append(("trigger", url.rsplit("/", 1)[-1].split("?")[0]))
        self.posted.append(json)
        if isinstance(self.trigger, Exception):
            raise self.trigger
        return SimpleNamespace(status_code=self.trigger[0], text=self.trigger[1])

    def _list_jobs(self, vault, rg):
        self.listings += 1
        return self.jobs(self.listings) if callable(self.jobs) else self.jobs

    def _job_named(self, name):
        for j in (self.jobs(self.listings) if callable(self.jobs) else self.jobs):
            if j.name == name:
                return j
        raise KeyError(name)

    # ── what happened ───────────────────────────────────────────────────────────

    def vm_writes(self) -> list[str]:
        return [e[0] for e in self.events if e[0].startswith("vm.")]

    def triggered(self) -> bool:
        return any(e[0] == "trigger" for e in self.events)

    def restore(self, **kw):
        return self.connector.restore_from_backup(_RID, vault="rsv", staging_storage="st",
                                                  before_attack_time=_AFTER_EVERY_POINT,
                                                  wait=kw.pop("wait", False), **kw)


def _job(name, op, start, status="InProgress", vm="vm", errors=None):
    j = MagicMock(properties=SimpleNamespace(operation=op, status=status, entity_friendly_name=vm,
                                             start_time=start, error_details=errors))
    j.name = name
    return j


def _error(code, words):
    return SimpleNamespace(error_code=code, error_string=words, error_title=None)


@pytest.fixture
def said(monkeypatch):
    """What the restore prints on the console (rich), line by line."""
    lines: list[str] = []
    import glorfindel.providers.azure.restore as restore_mod
    monkeypatch.setattr(restore_mod, "_console", SimpleNamespace(print=lambda *a, **k: lines.append(
        " ".join(str(x) for x in a))))
    return lines


# ── (c) the rights, read before the VM is touched ───────────────────────────────

@pytest.mark.parametrize("where, action, words", [
    ("staging", STAGING_LIST_KEYS, "le compte de transit"),
    ("vault", RESTORE_ACTION, "le coffre"),
    ("vm", "Microsoft.Compute/virtualMachines/deallocate/action", "la VM"),
    ("vm", "Microsoft.Compute/virtualMachines/start/action", "la VM"),
])
def test_a_missing_right_refuses_the_restore_before_any_write_on_the_vm_and_names_it(monkeypatch, where,
                                                                                     action, words):
    rights = _all_rights()
    rights[where] = [{"actions": [a for a in e["actions"] if a != action], "notActions": []}
                     for e in rights[where]]
    az = FakeRestoreAzure(monkeypatch, rights=rights)
    with pytest.raises(RuntimeError) as exc:
        az.restore()
    msg = str(exc.value)
    assert action in msg and words in msg and "avant de toucher la VM" in msg
    assert "ni neutralisée ni désallouée" in msg
    assert az.vm_writes() == [] and not az.triggered()
    # Read on each of the three scopes, before anything was written.
    assert {e[1] for e in az.events if e[0] == "permissions"} == {"vault", "vm", "staging"}


def test_the_staging_account_s_right_names_its_role(monkeypatch):
    rights = _all_rights()
    rights["staging"] = [_READER, _RESTORE]
    az = FakeRestoreAzure(monkeypatch, rights=rights)
    with pytest.raises(RuntimeError, match="Eregion Glorfindel Restore Staging"):
        az.restore()


def test_a_right_taken_back_by_notactions_is_missing_a_wildcard_holds(monkeypatch):
    rights = _all_rights()
    rights["vm"] = [{"actions": ["Microsoft.Compute/*"],
                     "notActions": ["Microsoft.Compute/virtualMachines/deallocate/*"]}]
    az = FakeRestoreAzure(monkeypatch, rights=rights)
    with pytest.raises(RuntimeError, match="virtualMachines/deallocate/action"):
        az.restore()
    assert az.vm_writes() == []
    # One role's notActions take nothing from another role's actions.
    rights["vm"].append({"actions": ["Microsoft.Compute/virtualMachines/deallocate/action"], "notActions": []})
    rights["staging"] = [{"actions": ["Microsoft.Storage/storageAccounts/*"], "notActions": []}]
    rights["vault"] = [{"actions": ["*"], "notActions": []}]
    az = FakeRestoreAzure(monkeypatch, rights=rights)
    out = az.restore()
    assert out["status"] == "restore_triggered" and az.triggered()


def test_run_command_missing_on_the_vm_is_no_refusal(monkeypatch, said):
    """SEC17: a VM outside restore_vms is restored all the same, its neutralization refused."""
    rights = _all_rights()
    rights["vm"] = [_READER, _RESTORE]
    az = FakeRestoreAzure(monkeypatch, rights=rights)
    out = az.restore()
    assert out["status"] == "restore_triggered" and az.triggered()
    assert any("Run Command absent" in line and "Restore Neutralize" in line for line in said)


def test_unreadable_rights_are_said_and_the_restore_goes_on_as_before(monkeypatch, said):
    rights = _all_rights()
    rights["staging"] = 403
    az = FakeRestoreAzure(monkeypatch, rights=rights)
    out = az.restore()
    assert out["status"] == "restore_triggered"
    assert az.vm_writes() == ["vm.run_command", "vm.deallocate"] and az.triggered()
    line = next(line for line in said if "illisibles" in line)
    assert "compte de transit" in line and "403" in line and _CLIENT_ID not in line


def test_with_every_right_the_order_is_read_neutralize_deallocate_trigger(monkeypatch):
    az = FakeRestoreAzure(monkeypatch)
    az.restore()
    kinds = [e[0] for e in az.events]
    assert kinds.index("vm.run_command") > max(i for i, k in enumerate(kinds) if k == "permissions")
    assert kinds.index("vm.run_command") < kinds.index("vm.deallocate") < kinds.index("trigger")


# ── (b) Azure's refusal at the trigger, said whole ──────────────────────────────

def test_a_linked_refusal_names_the_action_and_the_kind_of_scope_without_an_id(monkeypatch):
    """The 09/11 refusal: here the permissions read as held (a deny assignment, a condition — the
    API does not return them), and Azure refuses at the trigger."""
    text = _linked_refusal()
    assert text.index(STAGING_LIST_KEYS) > 300                     # what [:300] used to cut
    az = FakeRestoreAzure(monkeypatch, trigger=(403, text))
    with pytest.raises(RuntimeError) as exc:
        az.restore()
    msg = str(exc.value)
    assert "403 LinkedAuthorizationFailed" in msg
    assert f"il manque {STAGING_LIST_KEYS} sur Microsoft.Storage/storageAccounts" in msg
    assert "Eregion Glorfindel Restore Staging" in msg
    assert _OBJECT_ID not in msg and _CLIENT_ID not in msg and _SUB_ID not in msg
    assert "/subscriptions/" not in msg
    # The VM is deallocated: said, with the gesture to start it again; no job to look for.
    assert "reste désallouée" in msg and "az vm start -g rg -n vm" in msg
    assert az.vm_writes() == ["vm.run_command", "vm.deallocate"] and az.listings == 0


def test_an_authorization_refusal_names_its_action_and_scope():
    text = json.dumps({"error": {"code": "AuthorizationFailed", "message": (
        f"The client '{_CLIENT_ID}' with object id '{_OBJECT_ID}' does not have authorization to perform "
        "action 'Microsoft.Compute/virtualMachines/write' over scope "
        f"'/subscriptions/{_SUB_ID}/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm' or the "
        "scope is invalid. If access was recently granted, please refresh your credentials.")}})
    said = explain_refusal(403, text)
    assert said == ("403 AuthorizationFailed : il manque Microsoft.Compute/virtualMachines/write sur "
                    "Microsoft.Compute/virtualMachines")


def test_several_linked_actions_are_each_named_with_their_scope():
    text = json.dumps({"error": {"code": "LinkedAuthorizationFailed", "message": (
        "it does not have permission to perform action(s) "
        "'Microsoft.Network/virtualNetworks/subnets/join/action,Microsoft.Storage/storageAccounts/listKeys/action'"
        " on the linked scope(s) '/subscriptions/s/resourceGroups/rg/providers/Microsoft.Network/virtualNetworks/v"
        "/subnets/a,/subscriptions/s/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/st' "
        "(respectively) or the linked scope(s) are invalid.")}})
    said = explain_refusal(403, text)
    assert ("il manque Microsoft.Network/virtualNetworks/subnets/join/action sur "
            "Microsoft.Network/virtualNetworks/subnets") in said
    assert f"il manque {STAGING_LIST_KEYS} sur Microsoft.Storage/storageAccounts" in said


@pytest.mark.parametrize("text, kept", [
    (json.dumps({"error": {"code": "BadRequest", "message":
                           f"Recovery point of /subscriptions/{_SUB_ID}/resourceGroups/rg is invalid ({_OBJECT_ID})"}}),
     "400 BadRequest : Recovery point of <un groupe de ressources> is invalid (<id>)"),
    ("<html>gateway</html>", "400 : <html>gateway</html>"),
])
def test_another_refusal_is_said_whole_its_ids_masked(text, kept):
    assert explain_refusal(400, text) == kept


@pytest.mark.parametrize("scope, kind", [
    ("/subscriptions/s/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/st",
     "Microsoft.Storage/storageAccounts"),
    ("/subscriptions/s/resourceGroups/rg/providers/Microsoft.RecoveryServices/vaults/v/backupFabrics/Azure",
     "Microsoft.RecoveryServices/vaults/backupFabrics"),
    ("/subscriptions/s/resourceGroups/rg", "un groupe de ressources"),
    ("/subscriptions/s", "l'abonnement"),
    ("", "une portée illisible"),
])
def test_the_kind_of_a_scope_is_read_without_its_id(scope, kind):
    assert scope_kind(scope) == kind


def test_the_snapshot_s_refusal_is_said_whole_and_stays_a_write_refused(monkeypatch):
    """The watch reads « AuthorizationFailed » in the error as write_blocked (agent.py): kept."""
    az = FakeRestoreAzure(monkeypatch, trigger=(403, _linked_refusal()))
    with pytest.raises(RuntimeError) as exc:
        az.connector.snapshot(_RID, vault="rsv", wait=False)
    assert "AuthorizationFailed" in str(exc.value) and STAGING_LIST_KEYS in str(exc.value)
    assert _OBJECT_ID not in str(exc.value)


def test_a_trigger_without_an_answer_says_the_vm_is_deallocated(monkeypatch):
    az = FakeRestoreAzure(monkeypatch)
    az.trigger = az.requests.Timeout("read timed out")
    with pytest.raises(RuntimeError) as exc:
        az.restore()
    msg = str(exc.value)
    assert "vérifier les jobs du coffre" in msg and "az backup job list -g rg -v rsv" in msg
    assert "est désallouée" in msg and "az vm start -g rg -n vm" in msg


# ── (e) the payload of a restore in place ───────────────────────────────────────

@pytest.mark.parametrize("luns", [(), (10,), (0, 1)])
def test_a_restore_in_place_sends_no_list_of_luns(monkeypatch, luns):
    az = FakeRestoreAzure(monkeypatch, data_disks=luns)
    az.restore()
    props = az.posted[0]["properties"]
    assert props["recoveryType"] == "OriginalLocation"
    assert "restoreDiskLunList" not in props


# ── (f) the job, found finished, searched long enough ───────────────────────────

def test_a_restore_job_already_failed_is_read_with_its_error(monkeypatch):
    """09/11: the job failed in 4.5 s, code 400625 — « not found after trigger » before."""
    def jobs(attempt):
        now = datetime.now(timezone.utc)
        return [_job("restore-9", "Restore", now, status="Failed", errors=[_error(
            400625, "The restore request selected a subset of disks to restore, but selective disk restore is "
                    "not supported for this restore type.")])]
    az = FakeRestoreAzure(monkeypatch, jobs=jobs)
    with pytest.raises(RuntimeError) as exc:
        az.restore()
    msg = str(exc.value)
    assert "restore-9 Failed" in msg and "code 400625" in msg and "selective disk restore" in msg
    assert "reste désallouée" in msg and "az vm start -g rg -n vm" in msg
    assert "not found" not in msg


def test_a_failed_job_s_error_left_out_of_the_listing_is_read_from_its_details(monkeypatch):
    now = datetime.now(timezone.utc)
    detailed = _job("restore-9", "Restore", now, status="Failed", errors=[_error(400625, "selective")])
    az = FakeRestoreAzure(monkeypatch, jobs=[_job("restore-9", "Restore", now, status="Failed")],
                          details={"restore-9": detailed})
    with pytest.raises(RuntimeError, match="code 400625 : selective"):
        az.restore()


def test_a_finished_job_without_any_error_says_so(monkeypatch):
    now = datetime.now(timezone.utc)
    az = FakeRestoreAzure(monkeypatch, jobs=[_job("restore-9", "Restore", now, status="Cancelled")])
    with pytest.raises(RuntimeError, match="restore-9 Cancelled : aucun détail d'erreur lu"):
        az.restore()


def test_a_previous_attempt_s_failed_job_is_never_taken_for_this_one(monkeypatch):
    """The 3rd attempt's failed job, minutes before the 4th trigger: not this trigger's."""
    def jobs(attempt):
        now = datetime.now(timezone.utc)
        old = _job("restore-3", "Restore", now - timedelta(seconds=90), status="Failed",
                   errors=[_error(400625, "selective")])
        return [old] + ([_job("restore-4", "Restore", now)] if attempt >= 3 else [])
    az = FakeRestoreAzure(monkeypatch, jobs=jobs)
    out = az.restore()
    assert out["job_name"] == "restore-4"


def test_a_job_found_late_is_still_found_the_search_lasts_at_least_two_minutes(monkeypatch):
    def jobs(attempt):
        return [_job("restore-1", "Restore", datetime.now(timezone.utc))] if attempt >= 8 else []
    az = FakeRestoreAzure(monkeypatch, jobs=jobs)
    assert az.restore()["job_name"] == "restore-1"
    assert sum(az.sleeps) >= 120


def test_no_job_found_says_read_the_vault_s_jobs_and_the_vm_deallocated(monkeypatch):
    az = FakeRestoreAzure(monkeypatch, jobs=[])
    with pytest.raises(RuntimeError) as exc:
        az.restore()
    msg = str(exc.value)
    assert "lire les jobs du coffre avant de relancer" in msg and "az backup job list -g rg -v rsv" in msg
    assert "est désallouée" in msg and "az vm start -g rg -n vm" in msg
    assert sum(az.sleeps) >= 120


def test_a_job_completed_at_once_is_this_restore_s(monkeypatch):
    az = FakeRestoreAzure(monkeypatch, jobs=[_job("restore-1", "Restore", datetime.now(timezone.utc),
                                                  status="Completed")])
    assert az.restore()["job_name"] == "restore-1"


def test_a_restore_that_ends_with_warnings_stops_the_wait_and_leaves_the_vm_stopped(monkeypatch):
    now = datetime.now(timezone.utc)
    az = FakeRestoreAzure(monkeypatch, jobs=[_job("restore-1", "Restore", now)],
                          details={"restore-1": _job("restore-1", "Restore", now, status="CompletedWithWarnings",
                                                     errors=[_error(1, "one disk")])})
    with pytest.raises(RuntimeError) as exc:
        az.restore(wait=True)
    assert "CompletedWithWarnings" in str(exc.value) and "one disk" in str(exc.value)
    assert "vm.start" not in az.vm_writes()


def test_a_snapshot_whose_job_fails_at_once_says_so(monkeypatch):
    now = datetime.now(timezone.utc)
    az = FakeRestoreAzure(monkeypatch, jobs=[_job("backup-1", "Backup", now, status="Failed",
                                                  errors=[_error(42, "UserErrorGuestAgentStatusUnavailable")])])
    with pytest.raises(RuntimeError) as exc:
        az.connector.snapshot(_RID, vault="rsv", wait=False)
    assert "backup-1 Failed" in str(exc.value) and "code 42 : UserErrorGuestAgentStatusUnavailable" in str(exc.value)


def test_a_snapshot_s_job_is_searched_two_minutes_and_its_absence_says_what_to_do(monkeypatch):
    az = FakeRestoreAzure(monkeypatch, jobs=[])
    with pytest.raises(RuntimeError) as exc:
        az.connector.snapshot(_RID, vault="rsv", wait=False)
    assert "lire les jobs du coffre avant de relancer" in str(exc.value)
    assert sum(az.sleeps) >= 120 and "désallouée" not in str(exc.value)


def test_a_snapshot_s_job_found_late_is_tracked(monkeypatch):
    def jobs(attempt):
        return [_job("backup-1", "Backup", datetime.now(timezone.utc))] if attempt >= 6 else []
    az = FakeRestoreAzure(monkeypatch, jobs=jobs)
    assert az.connector.snapshot(_RID, vault="rsv", wait=False) == "rsv:rsv/rg/backup-1"


def test_a_job_s_errors_are_masked():
    job = _job("j", "Restore", None, status="Failed", errors=[_error(7, f"disk of /subscriptions/{_SUB_ID}/x")])
    assert job_error_text(job) == "code 7 : disk of <l'abonnement>"
    assert masked(_OBJECT_ID) == "<id>"


# ── (h) the identity the CLI restores under ─────────────────────────────────────

_PAIRS = ("AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID", "EREGION_CONSOLE_AZURE_CLIENT_ID",
          "GLORFINDEL_BOT_AZURE_CLIENT_ID", "GLORFINDEL_AZURE_CLIENT_ID")


@pytest.mark.parametrize("env, words, restores", [
    ({}, "aucune paire AZURE_CLIENT_*", False),
    ({"AZURE_CLIENT_ID": "c", "AZURE_TENANT_ID": "t"}, "AZURE_CLIENT_SECRET vide", False),
    ({"AZURE_CLIENT_ID": "c", "AZURE_CLIENT_SECRET": "x"}, "AZURE_TENANT_ID vide", False),
    ({"AZURE_CLIENT_ID": "c", "AZURE_CLIENT_SECRET": "x", "AZURE_TENANT_ID": "t",
      "EREGION_CONSOLE_AZURE_CLIENT_ID": "c"}, "la paire de la console", True),
    ({"AZURE_CLIENT_ID": "b", "AZURE_CLIENT_SECRET": "x", "AZURE_TENANT_ID": "t",
      "GLORFINDEL_BOT_AZURE_CLIENT_ID": "b", "EREGION_CONSOLE_AZURE_CLIENT_ID": ""}, "la paire du bot", True),
    ({"AZURE_CLIENT_ID": "w", "AZURE_CLIENT_SECRET": "x", "AZURE_TENANT_ID": "t",
      "GLORFINDEL_AZURE_CLIENT_ID": "w"}, "la paire de la watch", False),
    ({"AZURE_CLIENT_ID": "o", "AZURE_CLIENT_SECRET": "x", "AZURE_TENANT_ID": "t"},
     "ni celle de la console ni celle du bot", False),
])
def test_the_cli_says_which_kind_of_identity_restores_never_an_id(monkeypatch, env, words, restores):
    from glorfindel.cli import _restore_identity
    for name in _PAIRS:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    said, ok = _restore_identity()
    assert words in said and ok is restores
    assert not [v for k, v in env.items() if v and len(v) > 1 and v in said]


def test_the_restore_command_prints_its_identity(monkeypatch, tmp_path):
    """An empty console pair, `AZURE_CLIENT_ID= … glorfindel restore`: said, before anything."""
    from click.testing import CliRunner
    from glorfindel.cli import cli
    for name in _PAIRS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("glorfindel.cli._backup_vault_from_config", lambda v: ("rsv", "rg", "st"))
    res = CliRunner().invoke(cli, ["restore", _RID, "--before", "2026-11-09T17:00:00Z", "--dry-run"])
    assert res.exit_code == 0, res.output
    assert "Identity" in res.output and "aucune paire AZURE_CLIENT_*" in res.output
