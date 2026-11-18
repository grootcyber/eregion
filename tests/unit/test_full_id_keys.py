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


# ── The block file that can't be read ──────────────────────────────────────────────────────

def _rid(rg: str, name: str = "web") -> str:
    return f"/subscriptions/{SUB}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{name}"


def _block(rid: str, ip: str) -> None:
    from glorfindel import actions
    actions._save_block_state("web", ip, rid, nsg="rg-app/nsg-web", nsg_scope="nic", rule=f"r-{ip}",
                              placements=[{"nsg_rg": "rg-app", "nsg_name": "nsg-web", "rule": f"r-{ip}"}])


def _spoil(rid: str) -> None:
    from glorfindel import actions
    actions._state_file(actions._BLOCK_STATE_DIR, rid).write_text("{not json")


def test_unblocking_one_address_of_an_unreadable_file_keeps_the_file():
    """The lab's sequence: two addresses blocked, the file corrupted, one unblocked — the file was
    deleted with the other's entry. It stays, listed unreadable."""
    from glorfindel import actions
    rid = _rid("rg-app")
    _block(rid, "203.0.113.7")
    _block(rid, "198.51.100.9")
    _spoil(rid)
    actions._clear_block_state(rid, "203.0.113.7")
    f = actions._state_file(actions._BLOCK_STATE_DIR, rid)
    assert f is not None and f.read_text() == "{not json"
    assert f"blocks/{f.name}" in actions.unreadable_states()


def test_a_readable_file_keeps_the_other_addresses_entries():
    """Witness: a readable file loses the unblocked address only."""
    from glorfindel import actions
    rid = _rid("rg-app")
    _block(rid, "203.0.113.7")
    _block(rid, "198.51.100.9")
    actions._clear_block_state(rid, "203.0.113.7")
    assert [e["ip"] for e in actions._load_block_entries(rid)] == ["198.51.100.9"]


def test_a_new_block_sets_an_unreadable_file_aside_never_writes_over_it():
    from glorfindel import actions
    rid = _rid("rg-app")
    _block(rid, "203.0.113.7")
    _spoil(rid)
    _block(rid, "198.51.100.9")
    aside = list((actions._BLOCK_STATE_DIR / actions.ASIDE_DIR).glob("*.json"))
    assert len(aside) == 1 and aside[0].read_text() == "{not json"
    assert [e["ip"] for e in actions._load_block_entries(rid)] == ["198.51.100.9"]
    assert f"blocks/{actions.ASIDE_DIR}/{aside[0].name}" in actions.unreadable_states()
    # Never a state again: out of the blocks listed.
    assert [e["ip"] for e in actions.active_blocks()] == ["198.51.100.9"]


def test_an_annotation_never_writes_over_an_unreadable_file():
    from glorfindel import actions
    rid = _rid("rg-app")
    _block(rid, "203.0.113.7")
    _spoil(rid)
    actions._update_block_entry(rid, "203.0.113.7", unblock_failed=["x"])
    assert actions._state_file(actions._BLOCK_STATE_DIR, rid).read_text() == "{not json"


# ── A state file is a VM's only when the id it records is ─────────────────────────────────

# Two VMs named `web` in two groups whose ids meet on the 8 hex of a state file's name (32 bits: found
# in a few seconds; whoever can create a group and a VM in the subscription finds it as fast).
HOMONYM_A, HOMONYM_B = _rid("rg-14652"), _rid("rg-42874")


def _iso(rid: str, at: str) -> None:
    from glorfindel import actions
    actions._save_isolation_state(rid, {"resource_id": rid, "placements": [], "isolated_at": at})


def test_the_two_homonyms_meet_on_their_8_hex():
    from glorfindel import actions
    assert actions._rid_hash(HOMONYM_A) == actions._rid_hash(HOMONYM_B)
    assert actions._rid_key(HOMONYM_A) != actions._rid_key(HOMONYM_B)


def test_two_homonyms_whose_keys_meet_keep_two_states():
    """The second's state wrote over the first's — the first out of the reassertion, REC1, the TTL card."""
    from glorfindel import actions
    _iso(HOMONYM_A, "a")
    _iso(HOMONYM_B, "b")
    assert actions._load_isolation_state(HOMONYM_A)["isolated_at"] == "a"
    assert actions._load_isolation_state(HOMONYM_B)["isolated_at"] == "b"
    assert sorted(i["resource_id"] for i in actions.active_isolations()) == sorted([HOMONYM_A, HOMONYM_B])
    actions._clear_isolation_state(HOMONYM_B)
    assert actions._load_isolation_state(HOMONYM_A)["isolated_at"] == "a"
    assert actions._load_isolation_state(HOMONYM_B) is None


def test_a_file_found_by_its_name_is_read_only_when_its_id_is_the_vms():
    """The file of the first homonym, there under the 8-hex name: never the second's."""
    from glorfindel import actions
    _iso(HOMONYM_A, "a")
    assert actions._state_file(actions._ISOLATION_STATE_DIR, HOMONYM_B) is None
    assert actions._load_isolation_state(HOMONYM_B) is None


def test_the_start_up_migration_keeps_both_homonyms():
    from glorfindel import actions
    _iso(HOMONYM_A, "a")
    _iso(HOMONYM_B, "b")
    actions.migrate_state_files()
    assert actions._load_isolation_state(HOMONYM_A)["isolated_at"] == "a"
    assert actions._load_isolation_state(HOMONYM_B)["isolated_at"] == "b"


def test_the_second_homonym_finds_its_file_once_the_first_is_gone():
    """Its 128-bit file, read by id whatever the 8-hex name holds; written again under the 8-hex one."""
    from glorfindel import actions
    _iso(HOMONYM_A, "a")
    _iso(HOMONYM_B, "b")
    actions._clear_isolation_state(HOMONYM_A)
    assert actions._load_isolation_state(HOMONYM_B)["isolated_at"] == "b"
    _iso(HOMONYM_B, "c")
    files = list(actions._ISOLATION_STATE_DIR.glob("*.json"))
    assert len(files) == 1 and actions._load_isolation_state(HOMONYM_B)["isolated_at"] == "c"
