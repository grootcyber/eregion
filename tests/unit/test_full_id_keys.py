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


def test_the_8_hex_file_stays_the_first_homonyms():
    """Witness kept beside the next one: the 8-hex file of the first stays the first's."""
    from glorfindel import actions
    _iso(HOMONYM_A, "a")
    _iso(HOMONYM_B, "b")
    names = sorted(f.name for f in actions._ISOLATION_STATE_DIR.glob("*.json"))
    assert names == sorted([f"web--{actions._rid_hash(HOMONYM_A)}.json", f"web--{actions._rid_key(HOMONYM_B)}.json"])


# ── The quarantine NSG a bare NIC's original is read on ────────────────────────────────────

def _bare_world(monkeypatch):
    """web's NIC bare (taken off our quarantine by someone), its state lost; our quarantine NSG in
    web's group says « none » for it."""
    from .fake_azure import FakeAzure, nic_id, nsg_id
    monkeypatch.setenv("GLORFINDEL_QUARANTINE_NSG", "1")
    f = FakeAzure()
    subnet = f.add_subnet("rg-net", "vnet-hub", "app", None)
    f.add_vm("rg-app", "web", [{"rg": "rg-app", "name": "web-nic", "ips": ["10.0.0.4"], "subnet": subnet,
                                "nsg": None}])
    c = AzureConnector(dry_run=False, read_only=False)
    c._network, c._compute = f.network, f.compute
    c._subscription_id = "s"
    c.recent_changes = lambda *a, **k: []
    nic = nic_id("rg-app", "web-nic")
    f.add_nsg("rg-app", "nsg-glorfindel-quarantine-westeurope",
              tags={"managed-by": "glorfindel", c._orig_tag(nic): "none"})
    return f, c, nic, nsg_id


def test_a_decoy_quarantine_nsg_in_another_group_never_chooses_the_original(monkeypatch):
    """The lab's sequence (V-29): a NSG named and tagged like ours in another group names the NSG of
    the decoy's choosing for the NIC — it was put back on the release, over the authentic « none »."""
    from glorfindel.providers.azure.quarantine_origin import OriginalConflict
    f, c, nic, nsg_id = _bare_world(monkeypatch)
    chosen = f.add_nsg("rg-evil", "nsg-open")
    f.add_nsg("rg-evil", "nsg-glorfindel-quarantine-westeurope",
              tags={"managed-by": "glorfindel", c._orig_tag(nic): chosen})
    t0 = {"nic_id": nic, "nic_short": "web-nic", "location": "westeurope"}
    with pytest.raises(OriginalConflict, match="rg-evil"):
        c._bare_nic_original(t0, "rg-app")
    from glorfindel.actions import _save_isolation_state
    rid = "/subscriptions/s/resourceGroups/rg-app/providers/Microsoft.Compute/virtualMachines/web"
    _save_isolation_state(rid, {"resource_id": rid, "isolated_at": "x", "placements": [
        {"nic_id": nic, "kind": "quarantine", "nsg_rg": "rg-app", "nsg_name": "nsg-glorfindel-quarantine-westeurope",
         "nsg_id": nsg_id("rg-app", "nsg-glorfindel-quarantine-westeurope")}]})
    out = c.release_isolation(rid)
    assert out["status"] == "release_partial" and "rg-evil" in " ".join(out["failed"]), out
    from .fake_azure import key
    assert f.nics[key(nic)]["nsg"] is None                     # never the decoy's choice


def test_the_conflict_met_at_the_isolation_is_said_again_at_the_release(monkeypatch):
    """The NIC isolated again while another group's quarantine NSG names its original: unknown, and
    why — kept on the placement, said at the release with that NSG's name, not only « unknown »."""
    from glorfindel.actions import _load_isolation_state
    from .fake_azure import key
    f, c, nic, _ = _bare_world(monkeypatch)
    chosen = f.add_nsg("rg-evil", "nsg-open")
    f.add_nsg("rg-evil", "nsg-glorfindel-quarantine-westeurope",
              tags={"managed-by": "glorfindel", c._orig_tag(nic): chosen})
    rid = "/subscriptions/s/resourceGroups/rg-app/providers/Microsoft.Compute/virtualMachines/web"
    assert c.isolate_vm(rid)["status"] == "isolated"
    p = next(p for p in _load_isolation_state(rid)["placements"] if p.get("kind") == "quarantine")
    assert "original_nsg_id" not in p and "rg-evil/nsg-glorfindel-quarantine-westeurope" in p["original_conflict"]
    # Applied again on the NIC already in quarantine (the reassertion, a re-isolation): still unknown,
    # the reason kept on the new placement.
    assert c.isolate_vm(rid)["status"] == "isolated"
    p = next(p for p in _load_isolation_state(rid)["placements"] if p.get("kind") == "quarantine")
    assert "rg-evil/nsg-glorfindel-quarantine-westeurope" in p.get("original_conflict", "")
    out = c.release_isolation(rid)
    assert out["status"] == "release_partial" and "rg-evil/nsg-glorfindel-quarantine-westeurope" in " ".join(
        out["failed"]), out
    assert actions_is_quarantine(f.nics[key(nic)]["nsg"])


def actions_is_quarantine(nsg) -> bool:
    from glorfindel.actions import _is_quarantine_nsg
    return bool(nsg) and _is_quarantine_nsg(nsg)


def test_the_conflict_says_our_tag_when_our_groups_quarantine_nsg_exists(monkeypatch):
    """SEC-Hb (#947): our group holds the region's quarantine NSG — the way out is our tag there."""
    from glorfindel.providers.azure.quarantine_origin import OriginalConflict
    f, c, nic, _ = _bare_world(monkeypatch)
    f.add_nsg("rg-evil", "nsg-glorfindel-quarantine-westeurope",
              tags={"managed-by": "glorfindel", c._orig_tag(nic): f.add_nsg("rg-evil", "nsg-open")})
    t0 = {"nic_id": nic, "nic_short": "web-nic", "location": "westeurope"}
    with pytest.raises(OriginalConflict) as said:
        c._bare_nic_original(t0, "rg-app")
    assert f"poser le tag {c._orig_tag(nic)}=<id du NSG> sur nsg-glorfindel-quarantine-westeurope (rg-app)" in str(
        said.value) and "az network nic update" not in str(said.value)


def test_with_no_quarantine_nsg_in_our_group_the_conflict_says_the_nsg_put_back_by_hand(monkeypatch):
    """SEC-Hb (#947): the invariant machine's sequences, CI py3.12 — our own isolation made in the VM's
    group, its state lost, the configuration naming another group since, the quarantine off there. Nothing
    proves the VM's group's NSG ours: refused, as a decoy (SEC-H). Its way out said a tag on our group's NSG,
    which doesn't exist: no way out. Now: the NSG put back on the NIC by hand, the NIC's own group and name,
    the NSG for the operator to name — never the other group's choice, written in for a copy and paste."""
    from glorfindel.providers.azure.quarantine_origin import OriginalConflict

    from .fake_azure import FakeAzure, nic_id
    f = FakeAzure()
    subnet = f.add_subnet("rg-net", "vnet-hub", "app", None)
    f.add_vm("rg-app", "web", [{"rg": "rg-nics", "name": "web-nic", "ips": ["10.0.0.4"], "subnet": subnet,
                                "nsg": None}])
    c = AzureConnector(dry_run=False, read_only=False)
    c._network, c._compute = f.network, f.compute
    c._subscription_id = "s"
    c._quarantine_settings = lambda: (False, "rg-sec")          # quarantine_nsg: false, quarantine_rg: rg-sec
    nic = nic_id("rg-nics", "web-nic")
    chosen = f.add_nsg("rg-app", "nsg-web")
    f.add_nsg("rg-app", "nsg-glorfindel-quarantine-westeurope",
              tags={"managed-by": "glorfindel", c._orig_tag(nic): chosen})
    t0 = {"nic_id": nic, "nic_short": "web-nic", "location": "westeurope"}
    with pytest.raises(OriginalConflict) as said:
        c._bare_nic_original(t0, "rg-app")
    text = str(said.value)
    assert "hors du groupe rg-sec" in text and "rg-app/nsg-glorfindel-quarantine-westeurope" in text, text
    assert "az network nic update -g rg-nics -n web-nic --network-security-group <id du NSG>" in text, text
    assert chosen not in text and "poser le tag" not in text, text


# Azure's longest names (SEC-Hb's review): a resource group 90 characters, a NIC 80.
_LONG_RG, _LONG_NIC_RG, _LONG_Q_RG = ("rg-" + "a" * 87), ("rg-" + "n" * 87), ("rg-" + "q" * 87)
_LONG_NIC = "nic-" + "x" * 76


def _long_world(monkeypatch, ours: bool):
    """web's NIC bare, in a group of 90 characters, named on 80; our quarantine group of 90 configured,
    its NSG there (ours) or not; a quarantine NSG of another group of 90 naming an original for it."""
    from .fake_azure import FakeAzure, nic_id
    f = FakeAzure()
    subnet = f.add_subnet("rg-net", "vnet-hub", "app", None)
    f.add_vm(_LONG_RG, "web", [{"rg": _LONG_NIC_RG, "name": _LONG_NIC, "ips": ["10.0.0.4"], "subnet": subnet,
                                "nsg": None}])
    c = AzureConnector(dry_run=False, read_only=False)
    c._network, c._compute = f.network, f.compute
    c._subscription_id = "s"
    c.recent_changes = lambda *a, **k: []
    c._quarantine_settings = lambda: (True, _LONG_Q_RG)
    monkeypatch.setenv("GLORFINDEL_QUARANTINE_NSG", "1")
    nic = nic_id(_LONG_NIC_RG, _LONG_NIC)
    if ours:
        f.add_nsg(_LONG_Q_RG, "nsg-glorfindel-quarantine-westeurope",
                  tags={"managed-by": "glorfindel", "purpose": "incident-quarantine"})
    f.add_nsg(_LONG_RG, "nsg-glorfindel-quarantine-westeurope",
              tags={"managed-by": "glorfindel", c._orig_tag(nic): f.add_nsg(_LONG_RG, "nsg-" + "w" * 76)})
    return f, c, nic


def _tag_way(c, nic) -> str:
    return (f"poser le tag {c._orig_tag(nic)}=<id du NSG> sur nsg-glorfindel-quarantine-westeurope ({_LONG_Q_RG}), "
            "puis relancer")


@pytest.mark.parametrize("ours", [True, False], ids=["tag", "by-hand"])
def test_the_way_out_is_whole_in_the_release_with_azures_longest_names(monkeypatch, ours):
    """SEC-Hb's review: the release keeps `_ERR_MAX` characters of the conflict; the way out came last,
    and with long names (667 characters at 33–38) it lost `--network-security-group <id du NSG>, puis
    relancer`. Said first now: whole, with the NSG to tag and its group, for both ways."""
    from glorfindel.providers.azure.quarantine_origin import OriginalConflict
    from glorfindel.response.policy import _ERR_MAX
    f, c, nic = _long_world(monkeypatch, ours)
    t0 = {"nic_id": nic, "nic_short": _LONG_NIC, "location": "westeurope"}
    with pytest.raises(OriginalConflict) as said:
        c._bare_nic_original(t0, _LONG_RG)
    kept = str(said.value)[:_ERR_MAX]
    way = (_tag_way(c, nic) if ours else
           f"az network nic update -g {_LONG_NIC_RG} -n {_LONG_NIC} --network-security-group <id du NSG>, "
           "puis relancer")
    assert way in kept, kept


def test_the_way_out_kept_on_the_placement_is_whole_with_azures_longest_names(monkeypatch):
    """SEC-Hb's review: the isolation keeps the conflict on its placement — cut at 400, the tag's way lost
    its « sur <NSG> (<groupe>) » from 532 characters. Kept as the release keeps it, the way out first."""
    from glorfindel.actions import _load_isolation_state
    f, c, nic = _long_world(monkeypatch, ours=True)
    rid = f"/subscriptions/s/resourceGroups/{_LONG_RG}/providers/Microsoft.Compute/virtualMachines/web"
    assert c.isolate_vm(rid)["status"] == "isolated"
    p = next(p for p in _load_isolation_state(rid)["placements"] if p.get("kind") == "quarantine")
    assert "original_nsg_id" not in p
    assert _tag_way(c, nic) in p["original_conflict"], p["original_conflict"]


def test_without_a_decoy_the_authentic_none_stands(monkeypatch):
    f, c, nic, _ = _bare_world(monkeypatch)
    t0 = {"nic_id": nic, "nic_short": "web-nic", "location": "westeurope"}
    original, q = c._bare_nic_original(t0, "rg-app")
    assert original is None and q["nsg_rg"] == "rg-app"


def test_our_own_groups_tag_naming_an_nsg_is_followed(monkeypatch):
    f, c, nic, nsg_id = _bare_world(monkeypatch)
    x = f.add_nsg("rg-app", "nsg-web")
    f.nsgs[next(k for k in f.nsgs if k.endswith("nsg-glorfindel-quarantine-westeurope"))]["tags"][c._orig_tag(nic)] = x
    t0 = {"nic_id": nic, "nic_short": "web-nic", "location": "westeurope"}
    assert c._bare_nic_original(t0, "rg-app")[0] == x


@pytest.mark.parametrize("value", [
    "/subscriptions/other/resourceGroups/rg/providers/Microsoft.Network/networkSecurityGroups/nsg-x",
    "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Network/networkSecurityGroups/nsg-glorfindel-quarantine-x",
    "not-an-id",
])
def test_a_tag_that_names_what_cant_be_an_original_is_unknown(value):
    from glorfindel.providers.azure.quarantine import OriginalUnknown
    c = AzureConnector()
    c._subscription_id = "s"
    c._quarantine_tags = lambda q: {c._orig_tag("/n"): value}
    with pytest.raises(OriginalUnknown, match="ne nomme pas un NSG d'origine possible"):
        c._original_from_tags({"nsg_name": "q"}, "/n")


# ── The jobs, the claims, the last restore: by the full id ─────────────────────────────────

def test_a_homonyms_restore_is_never_this_vms():
    """V-30: web restored in one group; its homonym's last restore, its job, its claim are its own."""
    from glorfindel import jobs
    a, b = _rid("rg-a"), _rid("rg-b")
    connector = MagicMock()
    connector.restore_from_backup.return_value = {"job_name": "j1", "rg": "rg-a"}
    jobs.start_restore(a, connector, vault="v")
    assert jobs.get_last_restore(a) and jobs.get_last_restore(a)["resource_id"] == a
    assert jobs.get_last_restore(b) is None
    assert jobs.get_job(a)["restore_job_name"] == "j1" and jobs.get_job(b) is None
    assert jobs.restore_in_progress(a) and not jobs.restore_in_progress(b)
    with jobs.restore_claim(b):                    # a homonym's restore never holds this one
        assert jobs.restore_in_progress(b)
        assert "j1" in jobs.restore_in_progress(a)


def test_by_its_short_name_one_vms_restore_reads_as_before():
    """The model's message reads it by the short name (agent.py, unchanged): the one VM of that name
    with a record gets the same value as before; two homonyms with records give none."""
    from glorfindel import jobs
    a, b = _rid("rg-a"), _rid("rg-b")
    connector = MagicMock()
    connector.restore_from_backup.return_value = {"job_name": "j1", "rg": "rg-a"}
    jobs.start_restore(a, connector, vault="v")
    rec = jobs.get_last_restore("web")
    assert rec == jobs.get_last_restore(a) and set(rec) == {"last_restore_at", "resource_id"}
    jobs.start_restore(b, connector, vault="v")
    assert jobs.get_last_restore("web") is None


def test_an_earlier_versions_record_is_read_by_the_id_it_records():
    import json as _json
    from datetime import datetime, timezone
    from glorfindel import jobs
    a, b = _rid("rg-a"), _rid("rg-b")
    jobs._RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    (jobs._RECOVERY_DIR / "web.json").write_text(_json.dumps(
        {"last_restore_at": datetime.now(timezone.utc).isoformat(), "resource_id": a}))
    assert jobs.get_last_restore(a) is not None and jobs.get_last_restore(b) is None


def test_the_approval_reads_the_cards_own_vm_restore():
    from datetime import datetime, timedelta, timezone
    from glorfindel import approval, jobs
    a, b = _rid("rg-a"), _rid("rg-b")
    connector = MagicMock()
    connector.restore_from_backup.return_value = {"job_name": "j1", "rg": "rg-a"}
    jobs.start_restore(a, connector, vault="v")
    seen = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    card = {"escalation_type": "approval_required", "last_seen": seen, "resource_id": b}
    with patch.object(approval.action_queue, "APPROVABLE_TYPES", {"approval_required"}):
        assert approval.approval_refusal(card, "web") is None
        assert "restore" in (approval.approval_refusal({**card, "resource_id": a}, "web") or "").lower()


def test_the_vaults_job_of_a_homonym_is_never_this_vms():
    """_find_backup_job: the job of `web` in another group (one vault for both) is not taken."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    def job(name, container):
        return SimpleNamespace(name=name, properties=SimpleNamespace(
            operation="Restore", status="InProgress", entity_friendly_name="web",
            container_name=container, start_time=now))
    client = MagicMock()
    client.backup_jobs.list.return_value = [job("theirs", "iaasvmcontainerv2;rg-b;web")]
    c = AzureConnector()
    assert c._find_backup_job(client, "v", "rg-v", "Restore", "web", now, attempts=1, delay_s=0, vm_rg="rg-a") is None
    client.backup_jobs.list.return_value += [job("ours", "iaasvmcontainerv2;rg-a;web")]
    assert c._find_backup_job(client, "v", "rg-v", "Restore", "web", now, attempts=1, delay_s=0,
                              vm_rg="rg-a").name == "ours"


# ── Bounded waits, and the skipped VM said ─────────────────────────────────────────────────

def test_an_arm_write_that_does_not_end_is_never_read_done(monkeypatch):
    from glorfindel.providers.azure.sdk import _finished
    monkeypatch.setenv("GLORFINDEL_ARM_WRITE_TIMEOUT_S", "7")
    waited = []
    poller = SimpleNamespace(result=lambda timeout=None: waited.append(timeout), done=lambda: False)
    with pytest.raises(TimeoutError, match="7 s"):
        _finished(poller, "règle")
    assert waited == [7.0]
    assert _finished(SimpleNamespace(result=lambda timeout=None: "ok", done=lambda: True)) == "ok"


def test_a_writer_waits_for_the_lock_a_bounded_time(monkeypatch):
    from glorfindel.response import locks
    monkeypatch.setenv("GLORFINDEL_VM_LOCK_WAIT_S", "12")
    assert locks.writer_wait_s() == 12.0
    monkeypatch.setenv("GLORFINDEL_VM_LOCK_WAIT_S", "x")
    assert locks.writer_wait_s() == 900.0
    seen = {}
    import contextlib

    @contextlib.contextmanager
    def lock(vm, timeout=None):
        seen["timeout"] = timeout
        yield
    from glorfindel.providers.azure import connector as mod
    monkeypatch.setattr(mod, "_vm_lock", lock)
    c = AzureConnector(dry_run=False, read_only=False)
    c._subscription_id = "s"
    monkeypatch.setattr(c, "_ensure_clients", lambda: None)
    monkeypatch.setattr(c, "_guard_write", lambda *a: (_ for _ in ()).throw(RuntimeError("stop")))
    with pytest.raises(RuntimeError, match="stop"):
        c.release_isolation(_rid("rg-a").replace(SUB, "s", 1))
    assert seen["timeout"] == 900.0


def test_a_vm_skipped_pass_after_pass_is_said_on_one_card(monkeypatch):
    """V-27: its lock held, the reassertion skipped it in silence — now in each report, on a card
    from the fifth pass in a row, closed at the first pass that reads it."""
    import contextlib

    from glorfindel import escalations, reassert, reassert_skipped
    from glorfindel.actions import _save_isolation_state
    monkeypatch.setattr(escalations, "_notify", lambda esc: None)
    rid = _rid("rg-a")
    _save_isolation_state(rid, {"resource_id": rid, "isolated_at": "2026-11-18T10:00:00+00:00", "placements": []})
    busy = {"on": True}

    @contextlib.contextmanager
    def lock(vm, timeout=None):
        if busy["on"]:
            raise TimeoutError("busy")
        yield
    from glorfindel import actions
    monkeypatch.setattr(actions, "_vm_lock", lock)
    monkeypatch.setattr(reassert, "_reassert_isolation", lambda *a, **k: None)
    monkeypatch.setattr(reassert, "_whatever_the_state", lambda *a, **k: None)
    monkeypatch.setattr(reassert, "put_back_perimeters", lambda *a, **k: {})
    cards = lambda: [e for e in escalations.pending() if e["signal_id"].startswith("reassert-busy-")]  # noqa: E731
    for n in range(1, reassert_skipped.skips_said() + 1):
        report = reassert.reassert_active(None)
        assert [r["outcome"] for r in report] == ["skipped"], report
        assert len(cards()) == (1 if n == reassert_skipped.skips_said() else 0)
    reassert.reassert_active(None)
    assert len(cards()) == 1                       # one card, not one per pass
    busy["on"] = False
    assert reassert.reassert_active(None) == []
    assert not cards()


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


# ── The model's message, the same to the byte for an ordinary VM ───────────────────────────

def _earlier_get_last_restore(vm_name: str):
    """`jobs.get_last_restore` as origin/main had it (by the short name, `<name>.json`), restated."""
    import json as _json
    from datetime import datetime, timezone
    from glorfindel import jobs
    p = jobs._RECOVERY_DIR / f"{vm_name}.json"
    if not p.exists():
        return None
    try:
        data = _json.loads(p.read_text())
        age_s = (datetime.now(timezone.utc) - datetime.fromisoformat(data["last_restore_at"])).total_seconds()
        return data if age_s < 3600 else None
    except Exception:
        return None


@pytest.mark.parametrize("restored", [True, False])
def test_the_models_message_is_the_same_to_the_byte_for_an_ordinary_vm(restored):
    """`_build_user_message()` is not touched (CLAUDE.md: its edit asks for a run end to end): its
    call `get_last_restore(vm_name)` keeps its line. For a VM of the perimeter with no homonym — its
    restore recorded now under its full id — the message is the one origin/main gave from its
    `<name>.json`, byte for byte; an isolation and a block recorded, the same."""
    import json as _json
    from datetime import datetime, timedelta, timezone
    from glorfindel import actions, jobs
    from glorfindel.agent import _build_user_message
    rid = "/subscriptions/s/resourceGroups/rg-app/providers/Microsoft.Compute/virtualMachines/web"
    actions._save_isolation_state(rid, {"resource_id": rid, "isolated_at": "x", "placements": []})
    actions._save_block_state("web", "203.0.113.7", rid, placements=[])
    signal = {"resource_id": rid, "signal_id": "s-1", "raw_signal": {}}
    at = (datetime.now(timezone.utc) - timedelta(minutes=10, seconds=30)).isoformat()
    record = _json.dumps({"last_restore_at": at, "resource_id": rid})
    jobs._RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    if restored:
        (jobs._RECOVERY_DIR / f"{jobs._key(rid)}.json").write_text(record)     # as start_restore writes now
    now = _build_user_message(signal, [])
    for f in jobs._RECOVERY_DIR.glob("*.json"):
        f.unlink()
    if restored:
        (jobs._RECOVERY_DIR / "web.json").write_text(record)                   # as origin/main wrote it
    with patch.object(jobs, "get_last_restore", _earlier_get_last_restore):
        before = _build_user_message(signal, [])
    assert now.encode() == before.encode()
    assert ("Restauration Azure Backup déclenchée il y a **10 minutes**" in now) is restored
    assert "Isolée (NSG deny-all actif) : **OUI**" in now and "203.0.113.7" in now


def test_the_line_of_the_models_message_that_reads_the_last_restore_is_untouched():
    """The call in `_build_user_message()` is the one of origin/main, by the short name: the fix
    lies in what `get_last_restore` reads, never in what the model is given."""
    import inspect
    from glorfindel.agent import _build_user_message
    src = inspect.getsource(_build_user_message)
    assert "            _rec = _get_last_restore(vm_name)\n" in src
