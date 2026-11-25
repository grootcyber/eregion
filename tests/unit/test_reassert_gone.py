"""RSM3 (#1036, #1057): what the reassertion says of what is no longer there — a VM deleted (Q6), a perimeter
pair on an NSG taken off its subnet (E7) —, case by case, on the invariant machine's fake Azure (hermetic, no
call to Azure): its card, its words, and nothing written (docs/design/reaffirmation.md §3.5, §3.6, E7, E8)."""
from __future__ import annotations

import pytest

from .fake_azure import ATTACKER, key, subnet_id
from .test_invariant_regressions import _NSG, DB, WEB1, WEB2, Script, _net
from .test_invariants import _CURRENT, IsolationMachine, invariant_env

_APP = key(subnet_id("rg-net", "vnet-hub", "app"))
_SUBNET_NSG = _NSG.format(rg="rg-net", name="nsg-subnet")
_WRITES = ("rule.write", "rule.delete", "nic.write", "nsg.write", "nsg.tags")


@pytest.fixture
def machine(monkeypatch):
    invariant_env(monkeypatch)
    made = []

    def make(net, mode="human_only"):
        m = IsolationMachine()
        made.append(m)
        m.build(net)
        _CURRENT.mode = mode
        return m
    yield make
    for m in made:
        m.teardown()


def _pass(m) -> tuple[list[dict], list[dict]]:
    """One pass of the reassertion: (its report, what it wrote on the fake Azure)."""
    from glorfindel import reassert
    at = len(m.fake.journal)
    report = reassert.reassert_pass(m.connector, None)
    return report, [e for e in m.fake.journal[at:] if e.get("op") in _WRITES]


def _cards(vm: str, **match) -> list[dict]:
    from glorfindel import escalations
    return [e for e in escalations.pending() if key(e.get("resource_id") or "") == key(vm)
            and all(e.get(k) == v for k, v in match.items())]


# ── a VM deleted (Q6) ───────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mode", ["human_only", "non_disruptive"])
@pytest.mark.parametrize("quarantine", [False, True], ids=["by rules", "in quarantine"])
def test_an_isolated_vm_deleted_has_its_own_card_closed_at_the_release(machine, mode, quarantine):
    """Its own card, « n'existe plus », with the release command — never « non vérifiée » nor « le reposer a
    échoué : (ResourceNotFound) » —, said once, nothing written; closed once the release lifts it (I7S)."""
    m = machine(_net(quarantine=quarantine, web_nic={"own": "dedicated"}), mode)
    m.isolate(data=Script(WEB1, WEB1, None))
    m._delete_vm(WEB1)
    report, writes = _pass(m)
    (card,) = _cards(WEB1)
    assert card["action"] == "review_gone_vm" and card["escalation_type"] == "vm_gone", card
    assert "web n'existe plus sur Azure" in card["reason"] and "glorfindel release rg-app1/web --yes" in card["reason"]
    assert "ResourceNotFound" not in card["reason"] and not _cards(WEB1, action="review_unverified")
    assert [r["outcome"] for r in report if r.get("vm") == "web"] == ["escalated"], report
    assert not writes, writes
    _, writes = _pass(m)
    assert len(_cards(WEB1)) == 1 and not writes, "said once"
    from glorfindel import escalations
    escalations.resolve(card["id"])                       # acknowledged: not said again
    _pass(m)
    assert not _cards(WEB1)
    assert m.connector.release_isolation(WEB1).get("status") in ("released", "not_isolated"), "the lift of a VM gone"


@pytest.mark.parametrize("rules", ["in place", "gone"])
@pytest.mark.parametrize("mode", ["human_only", "non_disruptive"])
def test_a_blocked_vm_deleted_has_its_own_card_and_nothing_is_written(machine, monkeypatch, rules, mode):
    """A block of a VM deleted: its rules in place, « non vérifiée » was said; gone, the pass tried to put them
    back (« le reposer a échoué : (ResourceNotFound) »). Its own card, with the unblock command, no write — no
    put-back even tried —; closed at the unblock."""
    m = machine(_net(web_nic={"own": "dedicated"}), mode)
    m.block(data=Script(WEB1, WEB1, None, 22))
    if rules == "gone":
        nsg = key(_NSG.format(rg="rg-app1", name="nsg-web-nic"))
        for n in [n for n in m.fake.nsgs[nsg]["rules"] if n.startswith("glorfindel-block-")]:
            m.fake.nsgs[nsg]["rules"].pop(n)
    m._delete_vm(WEB1)
    tried = []
    real = m.connector.block_suspicious_ip
    monkeypatch.setattr(m.connector, "block_suspicious_ip", lambda *a, **k: tried.append(a) or real(*a, **k))
    _, writes = _pass(m)
    (card,) = _cards(WEB1)
    assert card["action"] == "review_gone_vm" and card["action_params"] == {"ip": ATTACKER}, card
    assert f"glorfindel unblock {ATTACKER} rg-app1/web --yes" in card["reason"], card
    assert "de le blocage" not in card["reason"] and "a échoué" not in card["reason"]
    assert not tried and not writes, (tried, writes)
    m.connector.unblock_ip(ATTACKER, WEB1)
    _pass(m)
    assert not _cards(WEB1), "closed at the unblock"


def test_a_vm_whose_read_fails_is_never_read_gone(machine, monkeypatch):
    """A VM read refused (a 429), not a 404: never gone on a guess (A0) — « non vérifiée », as before."""
    m = machine(_net(web_nic={"own": "dedicated"}))
    m.block(data=Script(WEB1, WEB1, None, 22))
    with monkeypatch.context() as mp:                    # the teardown's release reads the VM again
        mp.setattr(m.connector, "verify_block_ip", lambda *a: {"verified": None, "error": "illisible"})
        mp.setattr(m.connector._compute.virtual_machines, "get",
                   lambda *a: (_ for _ in ()).throw(RuntimeError("(TooManyRequests) vm.get")))
        assert m.connector.vm_gone(WEB1) is None
        _pass(m)
    assert [e["action"] for e in _cards(WEB1)] == ["review_unverified"]
    assert "La vérification du blocage de" in _cards(WEB1)[0]["reason"], "« du blocage », never « de le »"


def test_the_unverified_card_says_du_blocage():
    from glorfindel.reassert_cards import _unverified_reason
    assert _unverified_reason(f"le blocage de {ATTACKER} sur web", "x", "x").startswith(
        f"La vérification du blocage de {ATTACKER} sur web échoue (x)")
    assert _unverified_reason("l'isolation de web", "x", "x").startswith("La vérification de l'isolation de web")


# ── a perimeter pair on an NSG taken off its subnet (E7, #1057, night n° 50) ────────────────────────────────

def _off_card(vm: str) -> list[dict]:
    return _cards(vm, escalation_type="perimeter_off")


@pytest.mark.parametrize("allow", [False, True], ids=["alone", "an allow there"])
@pytest.mark.parametrize("how", ["off", "replaced"])
@pytest.mark.parametrize("mode", ["human_only", "non_disruptive"])
def test_a_perimeter_alone_on_an_nsg_taken_off_is_said_gone_never_bypassed_nor_another_subnet(
        machine, allow, how, mode):
    """A perimeter block alone, its subnet's NSG taken off (or another put in its place), an allow added there
    or not: one card of the block that names the NSG — never « contourné » (#1057), never « autre subnet » (M5,
    #1036) —, nothing written, the subnet's new NSG left as it is; said once."""
    m = machine(_net(subnet_nsg=[]), mode)
    m.block_perimeter(data=Script(WEB1, WEB1, None, False))
    m.customer_changes_subnet_nsg(data=Script(_APP, how))
    if allow:
        m._tamper_with_our_rule(Script("rogue", key(_SUBNET_NSG)))
    check = m.connector.verify_block_ip(ATTACKER, WEB1)
    assert check["verified"] is False and check["perimeter_off"] == "rg-net/nsg-subnet", check
    assert "shadowed_by" not in check and "uncovered_nics" not in check and "missing_rules" not in check, check
    _, writes = _pass(m)
    (card,) = _cards(WEB1)
    assert card["action"] == "block_suspicious_ip" and card["escalation_type"] == "perimeter_off", card
    reason = card["reason"]
    assert "rg-net/nsg-subnet" in reason and "a disparu du sous-réseau de web" in reason and "ne couvre plus web." in reason
    assert "ou la VM a changé de sous-réseau" in reason and "la VM déplacée, elle les couvre encore" in reason
    assert "autre subnet" not in reason and "contourné" not in reason and "ne couvre pas" not in reason
    assert f"glorfindel block {ATTACKER} rg-app1/web --scope subnet --yes" in reason
    assert not writes, writes
    _, writes = _pass(m)
    assert len(_cards(WEB1)) == 1 and not writes, "said once, nothing written"


@pytest.mark.parametrize("mode", ["human_only", "non_disruptive"])
def test_a_merged_perimeter_on_an_nsg_taken_off_is_said_and_closes_when_it_is_back(machine, mode):
    """Night n° 50: web (rg-app2) blocked on its subnet and for itself, the subnet's NSG taken off. The VM held by
    its own placement (`True`), its pair said gone on a card of its own — the VM's rules read apart —, nothing
    written. The NSG put back: the card closes, the mark goes; taken off again, said again."""
    from glorfindel import actions
    m = machine(_net(subnet_nsg=[], web_nic={"own": "tier"}), mode)
    m.block_perimeter(data=Script(WEB2, WEB2, None, False))
    m.block(data=Script(WEB2, WEB2, None, 22))
    m.customer_changes_subnet_nsg(data=Script(_APP, "off"))
    _, writes = _pass(m)
    (card,) = _off_card(WEB2)
    assert "propres règles de blocage, lues à part" in card["reason"], card
    assert not writes and len(_cards(WEB2)) == 1
    assert actions._load_block_entries(WEB2)[0]["perimeter_off_said"] == "rg-net/nsg-subnet"
    m.customer_changes_subnet_nsg(data=Script(_APP, "back"))
    _pass(m)
    assert not _off_card(WEB2) and not actions._load_block_entries(WEB2)[0].get("perimeter_off_said")
    m.customer_changes_subnet_nsg(data=Script(_APP, "off"))
    _pass(m)
    assert len(_off_card(WEB2)) == 1, "a new episode, said again"


def test_a_merged_entry_its_rules_gone_and_its_pair_off_puts_back_its_own_rules_only(machine):
    """The VM's own rules gone too, outside human_only: they are put back — the pair never, neither on the NSG
    taken off nor on the one the subnet carries now (a « replaced »). Two cards: the put-back's, the pair's."""
    m = machine(_net(subnet_nsg=[], web_nic={"own": "tier"}), "non_disruptive")
    m.block_perimeter(data=Script(WEB2, WEB2, None, False))
    m.block(data=Script(WEB2, WEB2, None, 22))
    m.customer_changes_subnet_nsg(data=Script(_APP, "replaced"))
    tier = key(_NSG.format(rg="rg-net", name="nsg-tier"))
    for n in [n for n in m.fake.nsgs[tier]["rules"] if n.startswith("glorfindel-block-")]:
        m.fake.nsgs[tier]["rules"].pop(n)
    report, writes = _pass(m)
    assert writes and {e["nsg"] for e in writes} == {tier}, writes
    assert [r["outcome"] for r in report if r.get("kind") == "block"].count("reapplied") == 1, report
    assert len(_off_card(WEB2)) == 1 and len(_cards(WEB2, escalation_type="verification_failed")) == 1


def test_a_bypass_said_before_the_nsg_is_taken_off_closes(machine):
    """A perimeter alone said « contourné » while its NSG governed the subnet; the NSG taken off: the bypass card
    closes (« contournée » supposes the hold intact), the pair's card says what is."""
    m = machine(_net(subnet_nsg=[]))
    m.block_perimeter(data=Script(WEB1, WEB1, None, False))
    m._tamper_with_our_rule(Script("rogue", key(_SUBNET_NSG)))
    _pass(m)
    assert [e["action"] for e in _cards(WEB1)] == ["review_bypass"]
    m.customer_changes_subnet_nsg(data=Script(_APP, "off"))
    _pass(m)
    assert [e["escalation_type"] for e in _cards(WEB1)] == ["perimeter_off"], [e["reason"] for e in _cards(WEB1)]


@pytest.mark.parametrize("entry", ["merged", "alone"])
def test_an_unreadable_attachment_is_never_read_gone_nor_held(machine, monkeypatch, entry):
    """The subnet of the VM's NIC unreadable (a 429), the pair's NSG governing none of its NICs as read: whether it
    still governs the subnet is not known (A0) — `None`, never `perimeter_off` (gone), never `True` (held); no
    card of the pair, nothing written."""
    m = machine(_net(subnet_nsg=[], web_nic={"own": "tier"}))
    m.block_perimeter(data=Script(WEB2, WEB2, None, False))
    if entry == "merged":
        m.block(data=Script(WEB2, WEB2, None, 22))
    real = m.connector._subnet_nsg_of

    def subnet_of(nic):
        if "web-nic" in str(getattr(nic, "id", "")).lower():
            raise RuntimeError("(TooManyRequests) subnet.get")
        return real(nic)
    with monkeypatch.context() as mp:                    # the teardown's release reads the subnet again
        mp.setattr(m.connector, "_subnet_nsg_of", subnet_of)
        check = m.connector.verify_block_ip(ATTACKER, WEB2)
        assert check["verified"] is None and "perimeter_off" not in check, check
        _, writes = _pass(m)
    assert not _off_card(WEB2) and not writes


def test_a_pair_on_its_subnet_is_never_read_off(machine):
    """The NSG on the subnet as written: the check never says the pair off — the perimeter covers it (`True`)."""
    m = machine(_net(subnet_nsg=[]))
    m.block_perimeter(data=Script(DB, DB, None, False))
    check = m.connector.verify_block_ip(ATTACKER, DB)
    assert "perimeter_off" not in check and check["verified"] is True, check
    assert not _off_card(DB)


# ── the review of RSM3 (25/11): no write without a read, the cause said as it may be ────────────────────────

def _merged_off(machine, how):
    """web (rg-app2) blocked on its subnet and for itself, the subnet's NSG `how`, its own rules taken off
    nsg-tier, outside human_only."""
    m = machine(_net(subnet_nsg=[], web_nic={"own": "tier"}), "non_disruptive")
    m.block_perimeter(data=Script(WEB2, WEB2, None, False))
    m.block(data=Script(WEB2, WEB2, None, 22))
    m.customer_changes_subnet_nsg(data=Script(_APP, how))
    tier = key(_NSG.format(rg="rg-net", name="nsg-tier"))
    for n in [n for n in m.fake.nsgs[tier]["rules"] if n.startswith("glorfindel-block-")]:
        m.fake.nsgs[tier]["rules"].pop(n)
    return m, tier


@pytest.mark.parametrize("defence", ["the write asks too", "the read alone"])
@pytest.mark.parametrize("how", ["replaced", "off"])
def test_nics_unread_at_the_check_never_put_the_pair_on_another_nsg(machine, monkeypatch, how, defence):
    """The review's finding 1: the VM's NICs unread at the check (a 429), its pair's NSG taken off or replaced,
    its own rules gone. The pair, where it lies unread, was read « at home » and put back on the subnet's NSG of
    the moment (nsg-subnet-b). Now the pair is unread (`pair_unread`, « rattachement illisible »), and neither
    time writes it: only the VM's own rules are put back, on nsg-tier. Measured with the write's own check
    (`refused_elsewhere`) and without it: each guard holds alone."""
    from glorfindel.actions import AzureConnector
    m, tier = _merged_off(machine, how)
    real_targets, real_verify, busy = m.connector._get_vm_nic_targets, m.connector.verify_block_ip, []

    def targets(*a, **k):
        if busy:
            raise RuntimeError("(TooManyRequests) nic.get")
        return real_targets(*a, **k)

    def verify(*a, **k):
        busy.append(1)
        try:
            return real_verify(*a, **k)
        finally:
            busy.pop()
    with monkeypatch.context() as mp:
        mp.setattr(m.connector, "_get_vm_nic_targets", targets)
        mp.setattr(m.connector, "verify_block_ip", verify)
        if defence == "the read alone":
            mp.setattr(AzureConnector, "perimeter_nsg_now", None)      # a provider that cannot say
        check = verify(ATTACKER, WEB2)
        assert check.get("pair_unread") and check.get("nics_unread") and "perimeter_off" not in check, check
        _, writes = _pass(m)
    assert writes and {e["nsg"] for e in writes} == {tier}, writes


@pytest.mark.parametrize("time", ["first", "second"])
def test_a_put_back_never_lays_a_perimeter_on_an_nsg_its_entry_does_not_name(machine, monkeypatch, time):
    """Defence in depth (the review's finding 1): a perimeter alone, its pair gone on the NSG that governs the
    subnet, yet the subnet read carrying another NSG at the write. The put-back refuses, and says so — at the
    first time, and at the second (the first one skipped)."""
    from glorfindel import reassert
    from glorfindel.actions import AzureConnector
    m = machine(_net(subnet_nsg=[]), "non_disruptive")
    m.block_perimeter(data=Script(WEB1, WEB1, None, False))
    for n in [n for n in m.fake.nsgs[key(_SUBNET_NSG)]["rules"] if n.startswith("glorfindel-block-")]:
        m.fake.nsgs[key(_SUBNET_NSG)]["rules"].pop(n)
    with monkeypatch.context() as mp:
        mp.setattr(AzureConnector, "perimeter_nsg_now", lambda self, rid: "rg-net/nsg-other")
        if time == "second":
            mp.setattr(reassert, "put_back_perimeters", lambda *a, **k: {})
        _, writes = _pass(m)
    assert not writes, writes
    (card,) = _cards(WEB1)
    assert "refusé : le sous-réseau porte rg-net/nsg-other, l'entrée enregistre rg-net/nsg-subnet" in card["reason"]
    assert m.connector.perimeter_nsg_now(WEB1).lower() == "rg-net/nsg-subnet", "read as it is, unpatched"


def test_a_fresh_block_whose_pair_is_off_is_never_blocked():
    """The review's finding 3: a block's answer read `perimeter_off` at its check is `blocked_partial`, said."""
    from glorfindel.actions import AzureConnector
    out = {"status": "blocked", "ip": ATTACKER, "nsg": "rg-net/nsg-subnet", "note": "denied for ALL VMs"}
    AzureConnector._say_gone(out, {"verified": True, "perimeter_off": "rg-net/nsg-subnet",
                                   "perimeter_nsg": "nsg-subnet"}, "web")
    assert out["status"] == "blocked_partial" and out["perimeter_off"] == "rg-net/nsg-subnet", out
    assert "governs none of web's NICs" in out["note"] and "denied for ALL" not in out["note"], out


def test_the_pair_off_is_said_on_a_put_back_of_an_earlier_pass(machine):
    """The review's finding 4: an entry whose pair a pass wrote partial (`partial_unsaid`, RW2) goes through
    the put-back's return — its pair now on an NSG off the subnet, said in that same pass."""
    from glorfindel.actions import _update_block_entry
    m = machine(_net(subnet_nsg=[], web_nic={"own": "tier"}))
    m.block_perimeter(data=Script(WEB2, WEB2, None, False))
    m.block(data=Script(WEB2, WEB2, None, 22))
    _update_block_entry(WEB2, ATTACKER, partial=True, partial_unsaid="la paire en partie")
    m.customer_changes_subnet_nsg(data=Script(_APP, "off"))
    _, writes = _pass(m)
    assert len(_off_card(WEB2)) == 1 and not writes, writes


class _Raised(Exception):
    def __init__(self, code: str):
        super().__init__(f"({code}) the resource was not found.")
        self.status_code = 404


@pytest.mark.parametrize("code, gone", [("ResourceNotFound", True), ("ResourceGroupNotFound", True),
                                        ("SubscriptionNotFound", None), ("ParentResourceNotFound", None)])
def test_only_a_vm_not_found_is_gone(code, gone):
    """The review's finding 5: a 404 is a VM gone only when the VM itself (or its group) is not found — the
    identity's subscription not found is not the VM gone: None, never gone on a guess (A0)."""
    from types import SimpleNamespace

    from glorfindel.actions import AzureConnector
    c = AzureConnector(dry_run=False)
    c._ensure_clients = lambda: None

    def get(*a):
        raise _Raised(code)
    c._compute = SimpleNamespace(virtual_machines=SimpleNamespace(get=get))
    assert c.vm_gone(WEB1) is gone


def test_a_provider_that_cant_tell_never_says_a_vm_gone():
    """The interface's default, AWS's too: None — the reassertion then says « non vérifiée », as before."""
    from glorfindel.providers.aws.connector import AwsConnector
    from glorfindel.providers.interface import CloudConnector
    assert CloudConnector.vm_gone(object(), WEB1) is None
    assert AwsConnector.vm_gone is CloudConnector.vm_gone


# ── the second review of RSM3 (25/11): a put-back held back for want of a read is deferred, never spent ──────

def _flaky_nics(m, mp, during: str = "check"):
    """The VM's NICs answer 429 inside `verify_block_ip` (`during="check"`), or, with `during="subnet"`, the
    subnet's NSG of the put-back's own check (`perimeter_nsg_now`) unread."""
    if during == "subnet":
        from glorfindel.actions import AzureConnector

        def unread(self, rid):
            raise RuntimeError("(TooManyRequests) subnet.get")
        mp.setattr(AzureConnector, "perimeter_nsg_now", unread)
        return
    real_targets, real_verify, busy = m.connector._get_vm_nic_targets, m.connector.verify_block_ip, []

    def targets(*a, **k):
        if busy:
            raise RuntimeError("(TooManyRequests) nic.get")
        return real_targets(*a, **k)

    def verify(*a, **k):
        busy.append(1)
        try:
            return real_verify(*a, **k)
        finally:
            busy.pop()
    mp.setattr(m.connector, "_get_vm_nic_targets", targets)
    mp.setattr(m.connector, "verify_block_ip", verify)


def _merged_all_gone(machine):
    """web (rg-app2) blocked on its subnet and for itself, its NSG still on the subnet; the pair and its own
    rules gone, outside human_only."""
    m = machine(_net(subnet_nsg=[], web_nic={"own": "tier"}), "non_disruptive")
    m.block_perimeter(data=Script(WEB2, WEB2, None, False))
    m.block(data=Script(WEB2, WEB2, None, 22))
    for name in ("nsg-subnet", "nsg-tier"):
        rules = m.fake.nsgs[key(_NSG.format(rg="rg-net", name=name))]["rules"]
        for n in [n for n in rules if n.startswith("glorfindel-block-")]:
            rules.pop(n)
    return m


def _pair_on(m, name: str) -> list[str]:
    return sorted(n for n in m.fake.nsgs[key(_NSG.format(rg="rg-net", name=name))]["rules"]
                  if n.startswith("glorfindel-block-") and not n.startswith("glorfindel-block-192-31-196-7-web"))


@pytest.mark.parametrize("during", ["check", "subnet", "subnet, second time"],
                         ids=["NICs unread at the check", "subnet unread at the write", "the same, the first time skipped"])
def test_a_transient_429_defers_the_pairs_put_back_never_spends_it(machine, monkeypatch, during):
    """The second review's finding: a merged entry, its NSG still on the subnet, its pair and its own rules
    gone, a 429 for one pass — on the VM's NICs at the check, or on the subnet's NSG at the write. Pass 1 puts
    back the VM's rules alone and, spending the put-back (`reasserted_at`), lost the pair for good: pass 2 said
    « une deuxième fois » of a pair never put back, the subnet's other VMs reached. Now pass 1 defers it, and
    says so; pass 2, reading, puts the pair back — on its own NSG only."""
    from glorfindel.actions import _load_block_entries
    m = _merged_all_gone(machine)
    from glorfindel import reassert
    with monkeypatch.context() as mp:
        _flaky_nics(m, mp, during.split(",")[0])
        if during.endswith("second time"):
            mp.setattr(reassert, "put_back_perimeters", lambda *a, **k: {})      # its lock held at the first
        _, writes = _pass(m)
    assert not _pair_on(m, "nsg-subnet"), "pass 1: the pair held back"
    entry = _load_block_entries(WEB2)[0]
    assert entry.get("pair_deferred") and not entry.get("reasserted_at"), entry
    (card,) = _cards(WEB2, escalation_type="verification_failed")
    assert "n'a pas été reposée, faute de lecture" in card["reason"] and "à la passe suivante" in card["reason"], card
    assert "deuxième fois" not in card["reason"] and "ne les réécrit pas de nouveau" not in card["reason"], card
    _, writes = _pass(m)
    assert len(_pair_on(m, "nsg-subnet")) == 2, "pass 2: the pair put back"
    pair = {e["nsg"] for e in writes if not e["rule"].startswith("glorfindel-block-192-31-196-7-web")}
    assert pair == {key(_NSG.format(rg="rg-net", name="nsg-subnet"))}, writes        # on its own NSG only
    assert {e["nsg"] for e in writes} <= {key(_NSG.format(rg="rg-net", name=n)) for n in ("nsg-subnet", "nsg-tier")}
    assert not _load_block_entries(WEB2)[0].get("pair_deferred")
    assert not any("deuxième fois" in e["reason"] for e in _cards(WEB2))


def test_a_read_that_keeps_failing_writes_nothing_and_says_it_once(machine, monkeypatch):
    """The same world, the VM's NICs unread at the check pass after pass: the pair is never written; its card
    said once, then « non vérifiée » once (the VM's rules back, the check concludes nothing) — no card more at
    each pass."""
    m = _merged_all_gone(machine)
    with monkeypatch.context() as mp:
        _flaky_nics(m, mp)
        _pass(m)
        _, writes = _pass(m)
        cards = {e["id"] for e in _cards(WEB2)}
        assert not writes and sorted(e["escalation_type"] for e in _cards(WEB2)) == ["unverified", "verification_failed"]
        for _ in range(2):
            _, writes = _pass(m)
            assert not writes and {e["id"] for e in _cards(WEB2)} == cards, (writes, _cards(WEB2))
    assert not _pair_on(m, "nsg-subnet")


def test_a_refusal_for_another_nsg_still_spends_the_put_back(machine, monkeypatch):
    """A put-back refused because the subnet carries another NSG is a decision to make, not a read to wait for:
    spent (`reasserted_at`), never retried alone."""
    from glorfindel.actions import AzureConnector, _load_block_entries
    m = _merged_all_gone(machine)
    with monkeypatch.context() as mp:
        mp.setattr(AzureConnector, "perimeter_nsg_now", lambda self, rid: "rg-net/nsg-other")
        _pass(m)
    entry = _load_block_entries(WEB2)[0]
    assert entry.get("reasserted_at") and not entry.get("pair_deferred"), entry
    _, writes = _pass(m)
    assert not _pair_on(m, "nsg-subnet") and not writes, writes
