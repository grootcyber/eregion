"""ORPH2 (#1113) — an older isolation left on an NSG that governs nothing: said, never taken off.

The world INV8's review measured (a remainder accepted since I8F): an isolation of a version older
than the placements — the fixed names `glorfindel-isolation-deny-all` and `-out`, a deny any/any on
the VM's own NSG — its state lost; then our quarantine, its tags lost; someone leaves the NIC bare;
the state lost again. The pair stays on an NSG that governs no NIC and no subnet: the release says
`released` (right), the orphan sweep and the reset find nothing — and put back on the NIC, the NSG
cuts the VM. Jonathan's decision (23/11): say it, take nothing off (SEC-H: the name alone never
proves whose the rules are). On the in-memory Azure (fake_azure.py): no Azure call.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from glorfindel import actions, escalations
from glorfindel.actions import AzureConnector
from glorfindel.config import GlorfindelConfig
from glorfindel.dormant_isolations import _alerts_path, say_dormant_isolations
from glorfindel.orphans import sweep_orphan_rules
from glorfindel.posture import PostureChecker

from .fake_azure import FakeAzure, _rule_record, key, nsg_id, open_flows, throttled, vm_id

WEB = vm_id("rg-app1", "web")
FIXED = AzureConnector.ISOLATION_RULE_NAME


def _rule(name, priority, **tpl):
    return SimpleNamespace(name=name, priority=priority, protocol="*", source_port_range="*", **tpl)


def _deny_all(direction, name=FIXED, access="Deny"):
    return _rule(name if direction == "Inbound" else f"{name}-out", 100, access=access, direction=direction,
                 source_address_prefix="*", destination_address_prefix="*", destination_port_range="*")


def _world(monkeypatch, legacy=True, out_access="Deny"):
    """`web` on its own NSG, nsg-web, which carries an older version's isolation (its state lost)."""
    monkeypatch.delenv("GLORFINDEL_QUARANTINE_NSG", raising=False)
    f = FakeAzure()
    rules = [_deny_all("Inbound"), _deny_all("Outbound", access=out_access)] if legacy else []
    web_nsg = f.add_nsg("rg-app1", "nsg-web", rules)
    subnet = f.add_subnet("rg-net", "vnet-hub", "app", None)
    f.add_vm("rg-app1", "web", [{"rg": "rg-app1", "name": "web-nic", "ips": ["10.0.0.4"], "subnet": subnet,
                                 "nsg": web_nsg}])
    c = AzureConnector(dry_run=False, read_only=False)
    c._network, c._compute = f.network, f.compute
    c._subscription_id = "s"
    c.recent_changes = lambda *a, **k: []
    return f, c, web_nsg


def _lose_state():
    for p in (actions._ISOLATION_STATE_DIR.glob("*.json") if actions._ISOLATION_STATE_DIR.exists() else []):
        p.unlink()


def _left_dormant(f, c):
    """The narrow world: our quarantine, its tags lost, the NIC left bare, the state lost again."""
    assert c.isolate_vm(WEB)["status"] == "isolated"
    nic = f.nics[key(f.vms[key(WEB)]["nics"][0])]
    assert actions._is_quarantine_nsg(nic["nsg"])
    for n in f.nsgs.values():
        n["tags"] = {k: v for k, v in n["tags"].items() if not k.startswith("glorfindel-orig-")}
    _lose_state()
    nic["nsg"] = None                                  # someone leaves the NIC bare
    _lose_state()
    return nic


def _cards(status=None):
    return [e for e in escalations.all_escalations() if e.get("escalation_type") == "dormant_isolation"
            and (status is None or e.get("status", "pending") == status)]


def _pending():
    return [e for e in escalations.pending() if e.get("escalation_type") == "dormant_isolation"]


def _fixed_on(f, nsg):
    return sorted(n for n in f.nsgs[key(nsg)]["rules"] if n.startswith(FIXED))


def _writes(f):
    return list(f.journal)                             # writes only (fake_azure.py)


def test_the_narrow_world_is_said_once_and_nothing_is_taken_off(monkeypatch):
    """The fiche's world: the release is right to say `released`, the orphan sweep and the reset find
    nothing; the pass says the NSG, its rules, why nothing goes and how to take them off by hand."""
    f, c, web_nsg = _world(monkeypatch)
    _left_dormant(f, c)
    assert c.release_isolation(WEB)["status"] == "released"
    assert c.find_orphan_rules() == []
    assert c.sweep_vm_rules(WEB, dry_run=True)["deleted"] == []
    assert _fixed_on(f, web_nsg) == [FIXED, f"{FIXED}-out"]          # nothing said them, until now
    writes = len(_writes(f))
    report = sweep_orphan_rules(c, None)
    assert len(_writes(f)) == writes                                   # read only
    assert _fixed_on(f, web_nsg) == [FIXED, f"{FIXED}-out"]            # never taken off (SEC-H)
    [card] = _pending()
    assert card["resource_id"].lower() == web_nsg.lower()
    assert card["action"] == "review_dormant_isolation" and card["severity"] == "medium"
    reason = card["reason"]
    assert "nsg-web" in reason and FIXED in reason and f"{FIXED}-out" in reason
    assert "ne gouverne aucune carte ni aucun sous-réseau" in reason and "SEC-H" in reason
    assert f"az network nsg rule delete -g rg-app1 --nsg-name nsg-web -n {FIXED}-out" in card["suggested_steps"][-1]
    assert [r["kind"] for r in report] == ["dormant_isolation"]
    # Said once: the next passes neither add a card nor bump it.
    sweep_orphan_rules(c, None)
    sweep_orphan_rules(c, None)
    assert len(_cards()) == 1 and _pending()[0].get("occurrences", 1) == card.get("occurrences", 1)


def test_neither_a_release_nor_a_reset_nor_the_pass_takes_them_off(monkeypatch):
    f, c, web_nsg = _world(monkeypatch)
    _left_dormant(f, c)
    sweep_orphan_rules(c, None)
    c.release_isolation(WEB)
    c.sweep_vm_rules(WEB)
    sweep_orphan_rules(c, None)
    assert _fixed_on(f, web_nsg) == [FIXED, f"{FIXED}-out"]
    assert len(_pending()) == 1


def test_an_acknowledged_card_stays_closed(monkeypatch):
    f, c, _ = _world(monkeypatch)
    _left_dormant(f, c)
    sweep_orphan_rules(c, None)
    escalations.resolve(_pending()[0]["id"])
    sweep_orphan_rules(c, None)
    assert _pending() == [] and len(_cards()) == 1


def test_the_card_closes_when_the_rules_are_taken_off(monkeypatch):
    f, c, web_nsg = _world(monkeypatch)
    _left_dormant(f, c)
    sweep_orphan_rules(c, None)
    for n in (FIXED, f"{FIXED}-out"):
        f.nsgs[key(web_nsg)]["rules"].pop(n)                   # the operator, by hand
    sweep_orphan_rules(c, None)
    [card] = _cards()
    assert card["status"] == "resolved" and "retirés" in card["resolution"]
    assert json.loads(_alerts_path().read_text()) == {}


def test_the_card_closes_when_the_nsg_is_deleted_proven_by_its_id(monkeypatch):
    f, c, web_nsg = _world(monkeypatch)
    _left_dormant(f, c)
    sweep_orphan_rules(c, None)
    f.nsgs.pop(key(web_nsg))
    sweep_orphan_rules(c, None)
    [card] = _cards()
    assert card["status"] == "resolved" and "n'existe plus" in card["resolution"]


def test_an_nsg_the_listing_leaves_out_keeps_its_card(monkeypatch):
    """A listing that omits an NSG (403: the identity no longer reads it) proves nothing (A0)."""
    f, c, web_nsg = _world(monkeypatch)
    _left_dormant(f, c)
    sweep_orphan_rules(c, None)
    f.unreadable.add(key(web_nsg))
    sweep_orphan_rules(c, None)
    assert len(_pending()) == 1


def test_a_listing_that_fails_keeps_every_card(monkeypatch):
    f, c, _ = _world(monkeypatch)
    _left_dormant(f, c)
    sweep_orphan_rules(c, None)

    def chaos(op, phase, write):
        if op == "nsg.list":
            raise throttled(op)
    f.chaos = chaos
    say_dormant_isolations(c, [])
    assert len(_pending()) == 1


def test_put_back_on_a_nic_the_card_is_replaced_by_what_it_cuts(monkeypatch):
    """The NSG put back on the NIC is when the rules cut: the card does not close, it is replaced
    by one that names what the NSG governs now — said once too."""
    f, c, web_nsg = _world(monkeypatch)
    nic = _left_dormant(f, c)
    sweep_orphan_rules(c, None)
    [first] = _pending()
    nic["nsg"] = web_nsg                                       # a redeployment
    flows = open_flows({"nsgs": f.nsgs, "nics": f.nics, "subnets": f.subnets, "vms": f.vms}, WEB)
    assert not [fl for fl in flows if fl[2] == "in"]           # the VM is cut
    sweep_orphan_rules(c, None)
    [card] = _pending()
    assert card["id"] != first["id"] and card["severity"] == "high"
    assert "gouverne de nouveau la carte web-nic" in card["reason"]
    old = next(e for e in _cards() if e["id"] == first["id"])
    assert old["status"] == "resolved" and "gouverne de nouveau" in old["resolution"]
    sweep_orphan_rules(c, None)
    assert len(_cards()) == 2
    assert _fixed_on(f, web_nsg) == [FIXED, f"{FIXED}-out"]


def test_a_pair_on_an_nsg_that_governs_something_is_left_to_its_paths(monkeypatch):
    """Never said dormant: the release and the reset of its VM judge it, as before."""
    f, c, _ = _world(monkeypatch)
    sweep_orphan_rules(c, None)
    assert _cards() == []


def test_an_nsg_on_a_subnet_only_governs_something(monkeypatch):
    """The NSG left by the NIC, put on a subnet since: it governs every NIC there — not dormant."""
    f, c, web_nsg = _world(monkeypatch)
    _left_dormant(f, c)
    f.add_subnet("rg-net", "vnet-hub", "data", web_nsg)
    sweep_orphan_rules(c, None)
    assert _cards() == []


def test_only_the_fixed_names_denied_count(monkeypatch):
    """A fixed name turned into an allow cuts nothing: the card names the deny only; a rule of the
    customer's, or ours under another name, is no older isolation."""
    f, c, web_nsg = _world(monkeypatch, out_access="Allow")
    _left_dormant(f, c)
    FakeAzure._put_rule(f.nsgs[key(web_nsg)], _rule_record(_rule(
        "glorfindel-isolation-deny-all-web", 300, access="Deny", direction="Inbound", source_address_prefix="*",
        destination_address_prefix="*", destination_port_range="*")))
    sweep_orphan_rules(c, None)
    [card] = _pending()
    assert f"{FIXED} (inbound" in card["reason"] and f"{FIXED}-out" not in card["reason"]
    assert "deny-all-web" not in card["reason"]


def test_an_nsg_with_no_fixed_name_says_nothing(monkeypatch):
    f, c, _ = _world(monkeypatch, legacy=False)
    _left_dormant(f, c)
    sweep_orphan_rules(c, None)
    assert _cards() == []


def test_the_posture_check_says_it_when_the_reassertion_does_not_run(monkeypatch):
    f, c, _ = _world(monkeypatch)
    _left_dormant(f, c)
    c.read_only = True
    PostureChecker(GlorfindelConfig(), c).check_and_escalate([])
    assert len(_pending()) == 1


def test_dry_run_reads_nothing():
    c = AzureConnector(dry_run=True)
    assert c.find_dormant_isolations() == []
    assert say_dormant_isolations(c) == [] and _cards() == []


def test_a_said_nsg_of_another_subscription_is_never_read_here(monkeypatch):
    f, c, _ = _world(monkeypatch)
    other = nsg_id("rg-x", "nsg-x").replace("/subscriptions/s/", "/subscriptions/t/")
    [entry] = c.find_dormant_isolations(nsgs=[], said=[other])
    assert "unread" in entry and not entry.get("gone")


def test_the_watch_reassertion_pass_says_it(monkeypatch):
    """Every pass of the watch, on the listing it shares with the quarantine check and the orphans."""
    from glorfindel.cli import console
    from glorfindel.watch.passes import _watch_reassert_pass
    f, c, _ = _world(monkeypatch)
    _left_dormant(f, c)
    report = _watch_reassert_pass(console, c, mode_override="non_disruptive")
    assert [r["outcome"] for r in report if r["kind"] == "dormant_isolation"] == ["escalated"]
    assert len(_pending()) == 1


def test_the_finder_reads_the_sdk_s_nsg_listing(monkeypatch):
    """On the pinned SDK's own objects (SDK1b, tests/unit/sdk_mgmt.py): an NSG of the listing that
    carries the fixed names and no association (`networkInterfaces`, `subnets` left out, as ARM
    leaves them out of an NSG attached to nothing) is found, governing nothing — the denies, by name."""
    import copy

    from . import sdk_mgmt as m
    m.offline(monkeypatch)
    cap = m.load("network.network_security_groups.list_all")
    body = m.body(cap)
    nsg = copy.deepcopy(body["value"][0])
    nsg["id"] = nsg["id"].rsplit("/", 1)[0] + "/nsg-example-old"
    nsg["name"] = "nsg-example-old"
    for k in ("networkInterfaces", "subnets"):
        nsg["properties"].pop(k, None)
    nsg["properties"]["securityRules"] = [{
        "name": n, "id": f"{nsg['id']}/securityRules/{n}",
        "properties": {"access": "Deny", "direction": d, "priority": 100, "protocol": "*",
                       "sourceAddressPrefix": "*", "destinationAddressPrefix": "*", "sourcePortRange": "*",
                       "destinationPortRange": "*", "provisioningState": "Succeeded"}}
        for n, d in ((FIXED, "Inbound"), (f"{FIXED}-out", "Outbound"))]
    body["value"].append(nsg)
    c = m.Arm(*[x for x in m.captures() if x["operation"] != cap["operation"]], cap).connector(monkeypatch)
    [entry] = c.find_dormant_isolations(c.nsg_listing())
    assert entry["nsg_id"].endswith("/nsg-example-old") and entry["nics"] == [] and entry["subnets"] == []
    assert [(r["name"], r["direction"]) for r in entry["rules"]] == [(FIXED, "inbound"), (f"{FIXED}-out", "outbound")]
