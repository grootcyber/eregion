"""SEC-H (#849): REC1 and the local state, by the full identifier.

- REC1 reads who ran a Run Command by object id only: a user's delegated token carries the appId of the
  application it signed in through — read as that application, a user's command passed for the
  neutralization of a principal that restores. Its next pages stay on Azure Resource Manager: the
  bearer token goes nowhere else.
- A block file that can't be read is set aside, never read as empty nor deleted with the entries of
  other addresses.
- The quarantine NSG a bare NIC's original is looked for on is searched in the configured group
  only, and the original a tag names is checked before it goes back on the NIC.
- The jobs, the restore claims and the last restore are keyed by the VM's full identifier; the
  vault's job is chosen by its container too.
- An ARM write waits a bounded time; the reassertion says a VM it skips pass after pass.
- A state file is used only when the resource id it records is the VM's.

0 Azure call, 0 LLM call: the in-memory Azure of tests/unit/fake_azure.py, or the SDK's shapes.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from glorfindel import recovery_watch
from glorfindel.actions import AzureConnector
from glorfindel.providers.azure import recovery

SUB = "00000000-0000-0000-0000-000000000000"
VM = f"/subscriptions/{SUB}/resourceGroups/rg-app/providers/Microsoft.Compute/virtualMachines/web"
TRUSTED_OID = "11111111-1111-1111-1111-111111111111"
TRUSTED_APPID = "22222222-2222-2222-2222-222222222222"
USER_OID = "33333333-3333-3333-3333-333333333333"
_OID = "http://schemas.microsoft.com/identity/claims/objectidentifier"


def _app_event(at: str, oid: str = TRUSTED_OID, appid: str = TRUSTED_APPID) -> dict:
    """A Run Command by an application's token (a service principal): `caller` its object id."""
    return {"caller": oid, "claims": {"appid": appid, _OID: oid, "idtyp": "app"},
            "operationName": {"value": recovery.RUN_COMMAND_OP}, "status": {"value": "Succeeded"},
            "eventTimestamp": at, "resourceId": VM, "operationId": f"op-{at}"}


def _user_event(at: str, appid: str = TRUSTED_APPID) -> dict:
    """A Run Command by a USER's delegated token, signed in through the application `appid`."""
    return {"caller": "someone@example.invalid",
            "claims": {"appid": appid, _OID: USER_OID, "idtyp": "user",
                       "http://schemas.microsoft.com/identity/claims/scope": "user_impersonation",
                       "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn": "someone@example.invalid"},
            "operationName": {"value": recovery.RUN_COMMAND_OP}, "status": {"value": "Succeeded"},
            "eventTimestamp": at, "resourceId": VM, "operationId": f"op-{at}"}


def _connector(events) -> AzureConnector:
    c = AzureConnector(dry_run=False, read_only=True)
    c._subscription_id = SUB
    c._activity = lambda rid, since: list(events)
    return c


def _epoch(text: str) -> float:
    from datetime import datetime
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


# ── REC1: object ids only ───────────────────────────────────────────────────────────────────

def test_a_users_delegated_token_is_never_its_applications_principal():
    """The appId a user's token carries is the client application's: never one of its ids."""
    assert TRUSTED_APPID not in recovery._callers(_user_event("2026-11-18T10:00:00Z"))
    assert recovery._callers(_user_event("2026-11-18T10:00:00Z")) == [USER_OID]
    assert recovery._apps(_user_event("2026-11-18T10:00:00Z")) == []


def test_a_user_token_without_idtyp_is_told_by_its_scope_and_upn():
    """An event's claims carry the long names of `scp` and `upn`: a user's token all the same."""
    e = _user_event("2026-11-18T10:00:00Z")
    del e["claims"]["idtyp"]
    assert recovery._callers(e) == [USER_OID]


def test_an_applications_token_is_read_by_its_object_id():
    ids = recovery._callers(_app_event("2026-11-18T10:00:00Z"))
    assert ids == [TRUSTED_OID]
    assert recovery._apps(_app_event("2026-11-18T10:00:00Z")) == [TRUSTED_APPID]


def test_a_user_through_the_trusted_application_neutralizes_nothing():
    """The lab's sequence: the last Run Command before the job by a delegated token carrying the
    appId GLORFINDEL_RESTORE_PRINCIPALS names — (True, "") before; now refused."""
    runs = _connector([_user_event("2026-11-18T10:00:00Z")])._run_commands_on(VM, "2026-11-18T09:00:00Z")
    got, why = recovery_watch.neutralized_by_the_control_plane(
        {"run_commands": runs}, _epoch("2026-11-18T11:00:00Z"), frozenset({TRUSTED_APPID}))
    assert got is False and "pas d'un principal qui restaure" in why


def test_the_object_id_of_the_principal_that_restores_still_neutralizes():
    """Witness: the same command by the application's token, its object id configured."""
    runs = _connector([_app_event("2026-11-18T10:00:00Z")])._run_commands_on(VM, "2026-11-18T09:00:00Z")
    assert recovery_watch.neutralized_by_the_control_plane(
        {"run_commands": runs}, _epoch("2026-11-18T11:00:00Z"), frozenset({TRUSTED_OID})) == (True, "")


def test_an_appid_configured_is_said_never_matched():
    """An appId in GLORFINDEL_RESTORE_PRINCIPALS no longer matches even the application's own token:
    object ids only — the card says what to put there instead."""
    runs = _connector([_app_event("2026-11-18T10:00:00Z")])._run_commands_on(VM, "2026-11-18T09:00:00Z")
    got, why = recovery_watch.neutralized_by_the_control_plane(
        {"run_commands": runs}, _epoch("2026-11-18T11:00:00Z"), frozenset({TRUSTED_APPID}))
    assert got is False and "object id" in why


# ── REC1: the activity log stays on ARM ────────────────────────────────────────────────────

def _page(value, link=None):
    return SimpleNamespace(ok=True, status_code=200, text="", json=lambda: {"value": value, "nextLink": link})


def _reading_connector() -> AzureConnector:
    c = AzureConnector(dry_run=False, read_only=True)
    c._subscription_id = SUB
    c._credential = MagicMock()
    c._credential.get_token.return_value = SimpleNamespace(token="t0k3n")
    return c


def test_a_next_page_outside_arm_is_refused_before_the_token_goes_there():
    c = _reading_connector()
    calls = []

    def get(url, headers=None, timeout=None, params=None):
        calls.append(url)
        return _page([], "https://elsewhere.example.invalid/page2")
    with patch("requests.get", side_effect=get):
        with pytest.raises(RuntimeError, match="hors d'Azure Resource Manager"):
            c._activity_events(VM, "2026-11-18T09:00:00Z")
    assert len(calls) == 1 and calls[0].startswith("https://management.azure.com/")


def test_a_next_page_on_arm_is_followed():
    """Witness: a next page on ARM is read, with the token."""
    c = _reading_connector()
    pages = [_page([{"a": 1}], "https://management.azure.com/next?page=2"), _page([{"b": 2}])]
    with patch("requests.get", side_effect=lambda *a, **k: pages.pop(0)):
        assert c._activity_events(VM, "2026-11-18T09:00:00Z") == [{"a": 1}, {"b": 2}]
