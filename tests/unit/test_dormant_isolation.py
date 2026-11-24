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
    report = sweep_orphan_rules(c, None)
    assert len(_pending()) == 1
    # Kept, and said (the review of ORPH2): one record of the pass, never silence.
    [said] = [r for r in report if r["kind"] == "dormant_isolation"]
    assert said["outcome"] == "unread" and said["vm"] == "nsg-web" and "AuthorizationFailed" in said["detail"]


def test_a_closure_refused_is_tried_again(monkeypatch):
    """The card closed before its mark is forgotten (the review of ORPH2): `resolve` refused (a full
    disk), the mark stays, and the next pass closes it — never a card pending for ever."""
    f, c, web_nsg = _world(monkeypatch)
    _left_dormant(f, c)
    sweep_orphan_rules(c, None)
    for n in (FIXED, f"{FIXED}-out"):
        f.nsgs[key(web_nsg)]["rules"].pop(n)
    real = escalations.resolve

    def refused(*a, **k):
        raise OSError("No space left on device")
    monkeypatch.setattr(escalations, "resolve", refused)
    sweep_orphan_rules(c, None)
    assert len(_pending()) == 1 and key(web_nsg) in json.loads(_alerts_path().read_text())
    monkeypatch.setattr(escalations, "resolve", real)
    sweep_orphan_rules(c, None)
    assert _pending() == [] and json.loads(_alerts_path().read_text()) == {}


def test_a_card_follows_what_the_nsg_governs(monkeypatch):
    """The NSG moved from NIC A to NIC B, then given a subnet too: each time a card that names what
    it governs now, the one before closed — and each state said once (the review of ORPH2)."""
    f, c, web_nsg = _world(monkeypatch)
    nic = _left_dormant(f, c)
    other = f.add_vm("rg-app2", "app", [{"rg": "rg-app2", "name": "app-nic", "ips": ["10.0.0.5"],
                                        "subnet": nic["subnet"], "nsg": None}])
    sweep_orphan_rules(c, None)
    nic["nsg"] = web_nsg
    sweep_orphan_rules(c, None)
    [on_a] = _pending()
    assert "la carte web-nic" in on_a["reason"]
    nic["nsg"] = None
    f.nics[key(f.vms[key(other)]["nics"][0])]["nsg"] = web_nsg
    sweep_orphan_rules(c, None)
    [on_b] = _pending()
    assert on_b["id"] != on_a["id"] and "la carte app-nic" in on_b["reason"] and "web-nic" not in on_b["reason"]
    assert "gouverne désormais app-nic" in next(e for e in _cards() if e["id"] == on_a["id"])["resolution"]
    f.add_subnet("rg-net", "vnet-hub", "data", web_nsg)
    sweep_orphan_rules(c, None)
    [both] = _pending()
    assert both["id"] != on_b["id"] and "la carte app-nic" in both["reason"] and "le sous-réseau data" in both["reason"]
    sweep_orphan_rules(c, None)
    assert len(_cards()) == 4                       # dormant, A, B, B and the subnet: each once


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


def test_only_the_older_names_denied_count(monkeypatch):
    """A fixed name, or one suffixed by a VM, turned into an allow cuts nothing: the card names the
    deny only; a rule of the customer's, or ours under another name, is no older isolation."""
    f, c, web_nsg = _world(monkeypatch, out_access="Allow")
    _left_dormant(f, c)
    for r in (*_suffixed("web", "10.0.0.4", access="Allow"),
              _rule("glorfindel-iso-web-web-nic-0a1b2c", 310, access="Deny", direction="Inbound",
                    source_address_prefix="*", destination_address_prefix="*", destination_port_range="*"),
              _rule("deny-all-web", 320, access="Deny", direction="Inbound", source_address_prefix="*",
                    destination_address_prefix="*", destination_port_range="*")):
        FakeAzure._put_rule(f.nsgs[key(web_nsg)], _rule_record(r))
    sweep_orphan_rules(c, None)
    [card] = _pending()
    assert f"{FIXED} (inbound" in card["reason"] and f"{FIXED}-out" not in card["reason"]
    assert "deny-all-web" not in card["reason"] and "glorfindel-iso-web" not in card["reason"]
    assert "suffixés" not in card["reason"]


# ORPH2b (#1126) — the same version's names suffixed by a VM (`glorfindel-isolation-deny-all-<vm>`,
# `-<vm>-out`: its deny scoped to the VM's address on a subnet's NSG), said the same way.

def _suffixed(vm, ip, access="Deny", name=None, priority=300):
    base = name or f"{FIXED}-{vm}"
    return (_rule(base, priority, access=access, direction="Inbound", source_address_prefix="*",
                  destination_address_prefix=ip, destination_port_range="*"),
            _rule(f"{base}-out", priority + 1, access=access, direction="Outbound", source_address_prefix=ip,
                  destination_address_prefix="*", destination_port_range="*"))


def _detached_subnet_nsg(f, rules):
    """A subnet's NSG that carried an older isolation, taken off its subnet since."""
    nsg = f.add_nsg("rg-net", "nsg-app-subnet", rules)
    subnet = f.add_subnet("rg-net", "vnet-hub", "legacy", nsg)
    f.subnets[key(subnet)]["nsg"] = None
    return nsg, subnet


def test_the_names_suffixed_by_a_vm_are_said_once_and_nothing_is_taken_off(monkeypatch):
    """The fiche's world under the suffixed names: the release says `released`, the orphan sweep
    and the reset find nothing (no other voice); the pass says the NSG, the rules, the VM they
    named, why nothing goes — and nothing is taken off, by the pass, a release or a reset."""
    f, c, web_nsg = _world(monkeypatch, legacy=False)
    for r in _suffixed("web", "10.0.0.4"):
        FakeAzure._put_rule(f.nsgs[key(web_nsg)], _rule_record(r))
    _left_dormant(f, c)
    assert c.release_isolation(WEB)["status"] == "released"
    assert c.find_orphan_rules() == []
    assert c.sweep_vm_rules(WEB, dry_run=True)["deleted"] == []
    writes = len(_writes(f))
    report = sweep_orphan_rules(c, None)
    assert len(_writes(f)) == writes                                   # read only
    assert [r["kind"] for r in report] == ["dormant_isolation"]        # one voice
    [card] = _pending()
    assert card["resource_id"].lower() == web_nsg.lower() and card["severity"] == "medium"
    reason = card["reason"]
    assert f"{FIXED}-web (inbound, priorité 300, VM web)" in reason
    assert f"{FIXED}-web-out (outbound, priorité 301, VM web)" in reason
    assert "les noms suffixés par la VM qu'ils isolaient (web)" in reason and "noms fixes" not in reason
    assert "peut-être une ancienne isolation de web" in reason and "SEC-H" in reason
    assert "ne gouverne aucune carte ni aucun sous-réseau" in reason
    assert f"az network nsg rule delete -g rg-app1 --nsg-name nsg-web -n {FIXED}-web-out" in card["suggested_steps"][-1]
    c.release_isolation(WEB)
    c.sweep_vm_rules(WEB)
    sweep_orphan_rules(c, None)
    sweep_orphan_rules(c, None)
    assert _fixed_on(f, web_nsg) == [f"{FIXED}-web", f"{FIXED}-web-out"]   # never taken off (SEC-H)
    assert len(_cards()) == 1 and _pending()[0].get("occurrences", 1) == card.get("occurrences", 1)


def test_a_subnet_nsg_detached_since_is_said_with_the_vm_it_named(monkeypatch):
    """The suffixed names' own world: a subnet's NSG taken off its subnet. Azure's names hold no
    case; the VM is read from the rule's direction (`-<vm>-out` outbound). Put back on its
    subnet, the card is replaced by a high one, as for the fixed names."""
    f, c, _ = _world(monkeypatch, legacy=False)
    nsg, subnet = _detached_subnet_nsg(f, _suffixed("App-01", "10.0.1.4", name="Glorfindel-Isolation-Deny-All-App-01"))
    sweep_orphan_rules(c, None)
    [card] = _pending()
    assert "nsg-app-subnet (rg-net)" in card["reason"]
    assert "Glorfindel-Isolation-Deny-All-App-01-out (outbound, priorité 301, VM App-01)" in card["reason"]
    assert "(App-01)" in card["reason"] and "App-01-out)" not in card["reason"]
    f.subnets[key(subnet)]["nsg"] = nsg                                # put back on its subnet
    sweep_orphan_rules(c, None)
    [high] = _pending()
    assert high["id"] != card["id"] and high["severity"] == "high"
    assert "gouverne de nouveau le sous-réseau legacy" in high["reason"]


def test_a_card_says_the_fixed_names_and_the_vms_together(monkeypatch):
    f, c, _ = _world(monkeypatch, legacy=False)
    _detached_subnet_nsg(f, [_deny_all("Inbound"), *_suffixed("web", "10.0.0.4"), *_suffixed("db", "10.0.0.6", priority=310)])
    sweep_orphan_rules(c, None)
    [card] = _pending()
    assert ("les noms fixes du refus total et les noms suffixés par la VM qu'ils isolaient (db, web)"
            in card["reason"])


def test_a_suffixed_rule_taken_off_by_hand_replaces_the_card(monkeypatch):
    """The card says the rules there now: one of the pair taken off, the other left, a card that
    names only what is left; the last taken off, the card closes."""
    f, c, _ = _world(monkeypatch, legacy=False)
    nsg, _ = _detached_subnet_nsg(f, _suffixed("web", "10.0.0.4"))
    sweep_orphan_rules(c, None)
    [first] = _pending()
    f.nsgs[key(nsg)]["rules"].pop(f"{FIXED}-web-out")
    sweep_orphan_rules(c, None)
    [left] = _pending()
    assert left["id"] != first["id"] and f"{FIXED}-web-out" not in left["reason"]
    assert "ont changé" in next(e for e in _cards() if e["id"] == first["id"])["resolution"]
    f.nsgs[key(nsg)]["rules"].pop(f"{FIXED}-web")
    sweep_orphan_rules(c, None)
    assert _pending() == [] and "retirés" in next(e for e in _cards() if e["id"] == left["id"])["resolution"]


def test_a_suffixed_name_on_an_nsg_that_governs_something_stays_to_its_vm(monkeypatch):
    """Never said dormant: on the NSG of its VM's NIC, the reset of that VM reads it by its name,
    as before (no card of ours beside it)."""
    f, c, web_nsg = _world(monkeypatch, legacy=False)
    for r in _suffixed("web", "10.0.0.4"):
        FakeAzure._put_rule(f.nsgs[key(web_nsg)], _rule_record(r))
    sweep_orphan_rules(c, None)
    assert _cards() == []
    assert any(f"{FIXED}-web" in d for d in c.sweep_vm_rules(WEB, dry_run=True)["deleted"])


def test_our_quarantine_rules_are_never_an_older_isolation(monkeypatch):
    """Our quarantine NSG, left empty by a release, governs nothing: its `glorfindel-quarantine-deny-*`
    rules are no older isolation, nothing said."""
    f, c, _ = _world(monkeypatch, legacy=False)
    assert c.isolate_vm(WEB)["status"] == "isolated"
    assert c.release_isolation(WEB)["status"] == "released"
    quarantine = [n for n in f.nsgs.values() if actions._is_quarantine_nsg(n["id"])]
    assert quarantine and any(r.startswith("glorfindel-quarantine-deny") for r in quarantine[0]["rules"])
    sweep_orphan_rules(c, None)
    assert _cards() == []


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
