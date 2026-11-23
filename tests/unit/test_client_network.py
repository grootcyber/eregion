"""SEC2b (#1089): the client's network, never blocked — the discovery's read, the guard, a list that
can't be trusted, `::ffff:`, the named networks, the order of the layers.

The read goes through the pinned SDK's own client on an in-memory ARM (tests/unit/sdk_mgmt.py): the
body ARM sends, deserialized by the SDK, read by the adapter. The guard is judged on the store the
discovery writes (glorfindel/client_network.py, under the conftest's tmp home). Every identifier is
made up (repository public): documentation addresses (RFC 5737, RFC 3849), example names. No Azure,
no model.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from glorfindel import client_network as cn
from glorfindel import client_network_watch as cnw
from glorfindel import config, escalations
from glorfindel.config_networks import NamedNetwork
from glorfindel.response.policy import (
    CLIENT, NEVER_BLOCK, PLATFORM, ProtectedAddressError, blockable_ip, held_words, protection, single_host_ip,
)

from . import sdk_mgmt as m

SUB = m.SUB
NET = f"/subscriptions/{SUB}/resourceGroups/rg-net/providers/Microsoft.Network"
VNET_PUBLIC = "203.0.113.0/24"       # a VNet whose address space is outside the private ranges
IN_VNET = "203.0.113.200"             # in the VNet, outside its subnets
IN_DMZ = "203.0.113.40"              # in its subnet snet-dmz
NAT_IP = "198.51.100.20"             # the NAT gateway's public IP
NIC_IP = "198.51.100.30"             # a VM's public IP
INTERNET = "192.0.2.77"              # nobody's: blockable
NOW = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)


def _vnet(name: str, prefixes: list[str], subnets: dict[str, str], rg: str = "rg-net") -> dict:
    rid = f"/subscriptions/{SUB}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{name}"
    return {"id": rid, "name": name, "location": "westeurope",
            "properties": {"addressSpace": {"addressPrefixes": prefixes},
                           "subnets": [{"id": f"{rid}/subnets/{s}", "name": s, "properties": {"addressPrefix": p}}
                                       for s, p in subnets.items()]}}


def _arm(vnets: list[dict] | None = None, refused: str = "") -> m.Arm:
    """The client's network as ARM lists it: two VNets, a NAT gateway's IP, a NIC's, one not
    allocated, a public prefix, a load balancer's private frontend. `refused`: a listing ARM refuses."""
    arm = m.Arm()
    base = f"/subscriptions/{SUB}/providers/Microsoft.Network"
    lists = {
        "virtualNetworks": vnets if vnets is not None else [
            _vnet("vnet-hub", ["10.1.0.0/16", VNET_PUBLIC], {"snet-dmz": "203.0.113.0/26", "snet-app": "10.1.1.0/24"}),
            _vnet("vnet-hub-2", ["10.9.0.0/16"], {"snet-dmz": "10.9.0.0/24"})],
        "publicIPAddresses": [
            {"id": f"{NET}/publicIPAddresses/pip-nat", "name": "pip-nat",
             "properties": {"ipAddress": NAT_IP, "natGateway": {"id": f"{NET}/natGateways/nat-out"}}},
            {"id": f"{NET}/publicIPAddresses/pip-web", "name": "pip-web",
             "properties": {"ipAddress": NIC_IP,
                            "ipConfiguration": {"id": f"{NET}/networkInterfaces/nic-web/ipConfigurations/ipconfig1"}}},
            {"id": f"{NET}/publicIPAddresses/pip-off", "name": "pip-off", "properties": {}}],
        "publicIPPrefixes": [{"id": f"{NET}/publicIPPrefixes/pfx", "name": "pfx",
                              "properties": {"ipPrefix": "198.51.100.64/28"}}],
        "loadBalancers": [{"id": f"{NET}/loadBalancers/lb-in", "name": "lb-in", "properties": {
            "frontendIPConfigurations": [{"id": f"{NET}/loadBalancers/lb-in/frontendIPConfigurations/fe",
                                          "name": "fe", "properties": {"privateIPAddress": "10.1.1.10"}}]}}],
    }
    for kind, items in lists.items():
        if kind == refused:
            arm.serve(f"{base}/{kind}", {"error": {"code": "AuthorizationFailed", "message": (
                f"The client does not have authorization to perform action 'Microsoft.Network/{kind}/read'")}}, 403)
        else:
            arm.serve(f"{base}/{kind}", {"value": items})
    return arm


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    m.offline(monkeypatch)


@pytest.fixture
def cfg_file(tmp_path, monkeypatch):
    path = tmp_path / "glorfindel-config.yaml"
    monkeypatch.setattr(config, "_DEFAULT_PATHS", [path])
    return path


def _read(arm: m.Arm | None = None) -> dict:
    from glorfindel.providers.azure.client_network import read_client_network
    return read_client_network((arm or _arm()).network())


def _saved(cfg=None, arm=None, at=None) -> cn.Snapshot:
    return cn.save(_read(arm), at or datetime.now(timezone.utc), (cfg or config.GlorfindelConfig()).networks)


# ── The read ─────────────────────────────────────────────────────────────────────────────────

def test_the_read_lists_the_vnets_and_every_public_ip_of_the_client():
    read = _read()
    assert read["unread"] == []
    hub = next(v for v in read["vnets"] if v["name"] == "vnet-hub")
    assert hub["prefixes"] == ["10.1.0.0/16", VNET_PUBLIC]
    assert {s["name"]: s["prefixes"] for s in hub["subnets"]} == {"snet-dmz": ["203.0.113.0/26"],
                                                                   "snet-app": ["10.1.1.0/24"]}
    by_address = {p["address"]: p for p in read["public_ips"]}
    assert set(by_address) == {NAT_IP, NIC_IP}               # the one not allocated: no address, left out
    assert by_address[NAT_IP]["kind"] == "nat_gateway" and by_address[NAT_IP]["attached_to"].endswith("/nat-out")
    assert by_address[NIC_IP]["kind"] == "nic" and by_address[NIC_IP]["attached_to"].endswith("/nic-web")
    assert [p["prefix"] for p in read["prefixes"]] == ["198.51.100.64/28"]
    assert [f["address"] for f in read["frontends"]] == ["10.1.1.10"]


def test_a_listing_refused_is_said_and_the_others_read():
    read = _read(_arm(refused="publicIPAddresses"))
    assert read["public_ips"] == [] and read["vnets"]
    [unread] = read["unread"]
    assert unread["what"] == "IP publiques" and unread["code"] == "forbidden"
    assert "droits" in unread["error"]


def test_the_read_writes_nothing():
    arm = _arm()
    _read(arm)
    assert arm.writes == [] and len(arm.requests) == 4


# ── The guard ────────────────────────────────────────────────────────────────────────────────

def test_an_address_of_a_client_vnet_outside_the_private_ranges_is_never_blocked(cfg_file):
    """M7143."""
    _saved()
    with pytest.raises(ProtectedAddressError, match="réseau du client"):
        blockable_ip(IN_VNET)
    p = protection(IN_VNET)
    assert (p.entry, p.layer, p.source) == (VNET_PUBLIC, CLIENT, "VNet vnet-hub") and p.degraded == ""
    assert blockable_ip(INTERNET) == INTERNET


@pytest.mark.parametrize("ip,said", [(NAT_IP, "passerelle NAT nat-out"), (NIC_IP, "carte réseau nic-web"),
                                     ("198.51.100.70", "IP publique pfx")])
def test_a_public_ip_of_the_client_is_never_blocked(ip, said, cfg_file):
    """M7144: a NAT gateway's, a NIC's, a prefix's."""
    _saved()
    with pytest.raises(ProtectedAddressError, match=said):
        blockable_ip(ip)


def test_decide_holds_a_block_of_a_client_address_and_says_it(cfg_file):
    """M7145: the card says « réseau du client », whatever the model said."""
    from glorfindel.agent import decide
    from glorfindel.config import AutonomyConfig
    from .test_agent_nodes import _mock_llm_response
    from .test_forged_logs import _block_state
    _saved()
    for ip in (IN_VNET, NAT_IP):
        with patch("litellm.completion", return_value=_mock_llm_response("block_suspicious_ip", confidence=0.99)):
            out = decide(_block_state(ip), model="claude-test", autonomy=AutonomyConfig(default="non_disruptive"))
        assert out["escalate"] is True and out["held_by"] == "never_block", out
        assert out["escalation_reason"].startswith(f"Blocage de {ip} retenu : adresse protégée (")
        assert "réseau du client" in out["escalation_reason"]
    with patch("litellm.completion", return_value=_mock_llm_response("block_suspicious_ip", confidence=0.99)):
        out = decide(_block_state(INTERNET), model="claude-test", autonomy=AutonomyConfig(default="non_disruptive"))
    assert out["held_by"] != "never_block"


def test_the_azure_connector_refuses_a_client_address_before_any_write(cfg_file, monkeypatch):
    from glorfindel.actions import AzureConnector
    _saved()
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", SUB)
    c = AzureConnector(dry_run=False)
    monkeypatch.setattr(c, "_guard_write", lambda *_a: pytest.fail("a write was attempted"))
    monkeypatch.setattr(c, "_ensure_clients", lambda *_a: pytest.fail("Azure was reached"))
    for scope in ("vm", "subnet"):
        with pytest.raises(ProtectedAddressError, match="réseau du client"):
            c.block_suspicious_ip(NAT_IP, f"/subscriptions/{SUB}/resourceGroups/rg/providers/"
                                          "Microsoft.Compute/virtualMachines/vm-a", scope=scope)


def test_an_approval_refuses_a_client_address(cfg_file):
    from glorfindel.approval import address_refusal
    _saved()
    ip, why = address_refusal(IN_VNET)
    assert not ip and "réseau du client" in why


# ── A list that can't be trusted (decision 4) ────────────────────────────────────────────────

def test_an_unreadable_list_is_said_never_read_as_an_empty_one(cfg_file):
    """M7146: the private ranges and never_block stay protected, an address neither private nor known
    stays blockable — and every refusal, every card says the list can't be trusted."""
    cn._STORE.parent.mkdir(parents=True, exist_ok=True)
    cn._STORE.write_text("{not json")
    snap = cn.load()
    assert snap.state == "unreadable" and "illisible" in snap.degraded()
    assert blockable_ip(IN_VNET) == IN_VNET                   # unknown: blockable as the Internet's
    with pytest.raises(ProtectedAddressError, match="illisible"):
        blockable_ip("10.1.1.5")
    assert "illisible" in held_words("10.1.1.5") and "Attention" in held_words("10.1.1.5")


@pytest.mark.parametrize("make,state", [
    (lambda: None, "absent"),
    (lambda: _saved(at=datetime.now(timezone.utc) - timedelta(seconds=cn.MAX_AGE_S + 60)), "stale"),
    (lambda: cn.save(_read(_arm(refused="publicIPPrefixes")), datetime.now(timezone.utc)), "partial"),
    (lambda: (_saved(), cn.note_failure("HttpResponseError: (AuthorizationFailed)", datetime.now(timezone.utc))),
     "failed"),
])
def test_each_list_that_can_t_be_trusted_is_said(make, state, cfg_file):
    """M7151: a read partial, a read failed, a list too old or never read — each said."""
    make()
    snap = cn.load()
    assert snap.state == state and snap.degraded()
    assert protection("10.1.1.5").degraded == snap.degraded()


def test_what_an_older_read_listed_stays_protected(cfg_file):
    """The most prudent wins: a list too old, or whose last read failed, still protects what it listed."""
    _saved(at=datetime.now(timezone.utc) - timedelta(hours=3))
    cn.note_failure("TimeoutError: read timed out", datetime.now(timezone.utc))
    with pytest.raises(ProtectedAddressError, match="réseau du client"):
        blockable_ip(NAT_IP)
    assert "échec" in protection(NAT_IP).degraded


def test_the_watch_files_a_card_while_the_list_can_t_be_trusted_then_closes_it(cfg_file):
    cfg = config.load_glorfindel_config()

    def refused():
        raise RuntimeError("no credential")
    cnw.refresh(refused, cfg)
    cnw.refresh(refused, cfg)
    [card] = [e for e in escalations.pending() if e["escalation_type"] == cn.CARD_TYPE]
    assert card["resource_id"] == cn.CARD_RESOURCE and card["occurrences"] == 2
    assert "non fiable" in card["reason"] and "no credential" in card["reason"]
    assert "bloquable" in card["reason"]
    cnw.refresh(lambda: _read(), cfg)
    assert not [e for e in escalations.pending() if e["escalation_type"] == cn.CARD_TYPE]


# ── ::ffff: ──────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ip", ["::ffff:169.254.169.254", "::ffff:169.254.10.1", "::ffff:127.0.0.1",
                                "::ffff:0.0.0.0", "::ffff:224.0.0.1"])
def test_an_ipv4_written_as_ipv6_is_judged_as_that_ipv4(ip):
    """M7147."""
    with pytest.raises(ValueError, match="non routable ou réservée"):
        single_host_ip(ip)


def test_an_ipv4_written_as_ipv6_is_that_ipv4_for_the_block():
    assert single_host_ip("::ffff:192.0.2.77") == "192.0.2.77"
    assert single_host_ip("2001:db8::1") == "2001:db8::1"


# ── The named networks (decisions 5 and 9) ───────────────────────────────────────────────────

@pytest.mark.parametrize("text,said", [
    ("never_block: [bureau]\n", "aucun réseau nommé « bureau » déclaré dans networks"),
    ("networks: {bureau: [198.51.100.0/28]}\nnever_block: [burreau]\n", "aucun réseau nommé « burreau »"),
    ("expected_sudo:\n  admins:\n    - {match: vm-a, accounts: [ops], origins: [bastion]}\n",
     "aucun réseau nommé « bastion »"),
])
def test_a_name_cited_and_not_declared_refuses_the_file(text, said, cfg_file):
    """M7148."""
    cfg_file.write_text(text)
    with pytest.raises(config.ConfigError, match=said):
        config.load_glorfindel_config()


@pytest.mark.parametrize("text,said", [
    ("networks: {dmz: {vnet: 'vnet-*'}}\n", "jamais un motif"),
    ("networks: {dmz: {subnet: 'vnet-hub/snet-?'}}\n", "jamais un motif"),
    ("networks: {dmz: {subnet: 'vnet-hub'}}\n", "<vnet>/<sous-réseau>"),
    ("networks: {dmz: {vnet: a, subnet: a/b}}\n", "une seule clé"),
    ("networks: {dmz: {vnets: a}}\n", "clé inconnue"),
    ("networks: {bureau: [198.51.100.7/24]}\n", "bits d'hôte"),
    ("networks: {bureau: [0.0.0.0/0]}\n", "/0"),
    ("networks: {bureau: []}\n", "liste vide"),
    ("networks: {10.0.0.0/8: [10.0.0.0/8]}\n", "un nom commence par une lettre"),
    ("networks: {bureau: 198.51.100.0/28}\n", "une liste de plages CIDR"),
])
def test_the_networks_are_read_strictly(text, said, cfg_file):
    cfg_file.write_text(text)
    with pytest.raises(config.ConfigError, match=said):
        config.load_glorfindel_config()


def test_a_name_is_cited_where_a_range_is_and_a_range_stays_accepted(cfg_file):
    cfg_file.write_text("networks:\n  bureau: [198.51.100.0/28]\n  dmz: {subnet: vnet-hub/snet-dmz}\n"
                        "  libre: [192.0.2.128/25]\n"
                        "never_block: [bureau, 203.0.113.9]\n"
                        "expected_sudo:\n  admins:\n    - {match: vm-a, accounts: [ops], origins: [bureau, dmz]}\n")
    cfg = config.load_glorfindel_config()
    assert cfg.never_block == ["198.51.100.0/28", "203.0.113.9/32"] and cfg.never_block_names == ["bureau"]
    assert cfg.network_uses == {"bureau": ["never_block", "expected_sudo.admins[0].origins"],
                                "dmz": ["expected_sudo.admins[0].origins"]}
    [note] = cfg.notes                                          # said, never refused
    assert note.startswith("networks.libre : déclaré, cité par aucune clé")
    assert cfg.expected_sudo.origins_for("vm-a", "ops") == ("198.51.100.0/28",)     # dmz: nothing read yet
    _saved(cfg)
    assert cfg.expected_sudo.origins_for("vm-a", "ops") == ("198.51.100.0/28", "203.0.113.0/26")


def test_an_origin_is_never_read_from_a_list_that_can_t_be_trusted(cfg_file):
    cfg_file.write_text("networks:\n  dmz: {subnet: vnet-hub/snet-dmz}\n"
                        "expected_sudo:\n  admins:\n    - {match: vm-a, accounts: [ops], origins: [dmz]}\n")
    cfg = config.load_glorfindel_config()
    _saved(cfg, at=datetime.now(timezone.utc) - timedelta(seconds=cn.MAX_AGE_S + 60))
    assert cfg.expected_sudo.origins_for("vm-a", "ops") == ()


def test_a_named_object_is_resolved_by_its_exact_name_never_a_pattern(cfg_file):
    """M7149: `vnet-hub` is vnet-hub, never vnet-hub-2."""
    cfg_file.write_text("networks:\n  hub: {vnet: vnet-hub}\n  dmz: {subnet: vnet-hub/snet-dmz}\n"
                        "  twin: {vnet: VNET-HUB-2}\n")
    snap = _saved(config.load_glorfindel_config())
    cfg = config.load_glorfindel_config()
    assert snap.resolve(cfg.networks["hub"]) == (["10.1.0.0/16", VNET_PUBLIC], "")
    assert snap.resolve(cfg.networks["dmz"]) == (["203.0.113.0/26"], "")
    assert snap.resolve(cfg.networks["twin"]) == (["10.9.0.0/16"], "")              # Azure ignores the case
    assert snap.resolve(NamedNetwork("x", vnet="vnet")) == ([], "VNet « vnet » introuvable")


def test_two_vnets_of_one_name_are_no_exact_name(cfg_file):
    cfg_file.write_text("networks:\n  hub: {vnet: vnet-hub}\n")
    cfg = config.load_glorfindel_config()
    snap = _saved(cfg, arm=_arm([_vnet("vnet-hub", ["10.1.0.0/16"], {}),
                                 _vnet("vnet-hub", ["10.2.0.0/16"], {}, rg="rg-other")]))
    assert snap.resolve(cfg.networks["hub"]) == ([], "2 VNet portent le nom « vnet-hub » : aucun nom exact")


def test_a_named_object_not_found_is_a_list_that_can_t_be_trusted(cfg_file):
    cfg_file.write_text("networks:\n  partenaire: {vnet: vnet-partenaire}\nnever_block: [partenaire]\n")
    _saved(config.load_glorfindel_config())
    p = protection("10.1.1.5")
    assert "réseau nommé « partenaire » (VNet vnet-partenaire) : VNet « vnet-partenaire » introuvable" in p.degraded


def test_a_named_network_cited_by_never_block_protects_its_object(cfg_file):
    cfg_file.write_text("networks:\n  dmz: {subnet: vnet-hub/snet-dmz}\nnever_block: [dmz]\n")
    _saved(config.load_glorfindel_config())
    p = protection(IN_DMZ)
    assert (p.entry, p.layer, p.source) == ("203.0.113.0/26", NEVER_BLOCK, "never_block, réseau nommé « dmz »")


def test_a_change_of_what_a_name_designates_is_said_on_a_card(cfg_file):
    """M7152: each change on its own card, the one before replaced."""
    cfg_file.write_text("networks:\n  dmz: {subnet: vnet-hub/snet-dmz}\nnever_block: [dmz]\n")
    cfg = config.load_glorfindel_config()
    cnw.refresh(lambda: _read(), cfg)
    assert not [e for e in escalations.pending() if e["escalation_type"] == cn.CHANGE_TYPE]   # a first read
    for prefix in ("203.0.113.64/26", "203.0.113.128/26"):
        moved = _arm([_vnet("vnet-hub", ["10.1.0.0/16", VNET_PUBLIC], {"snet-dmz": prefix})])
        cnw.refresh(lambda: _read(moved), cfg)
    [card] = [e for e in escalations.pending() if e["escalation_type"] == cn.CHANGE_TYPE]
    assert card["resource_id"] == f"{cn.CARD_RESOURCE}/dmz"
    assert "maintenant 203.0.113.128/26 — avant : 203.0.113.64/26" in card["reason"]
    assert "Où il sert : never_block" in card["reason"]


# ── The order of the layers (decision 8) ─────────────────────────────────────────────────────

def test_never_block_keeps_its_place_before_the_client_s_network(cfg_file):
    """M7150: an address both in never_block and in the client's network is said never_block's; the
    platform's before never_block's."""
    cfg_file.write_text(f"networks:\n  bureau: [{NAT_IP}/32]\nnever_block: [bureau, 168.63.129.16, 10.1.1.0/24]\n")
    _saved(config.load_glorfindel_config())
    assert protection(NAT_IP).layer == NEVER_BLOCK
    assert protection(NAT_IP).source == "never_block, réseau nommé « bureau »"
    assert protection("10.1.1.5").layer == NEVER_BLOCK                       # never the private range's
    assert protection("168.63.129.16").layer == PLATFORM
    with pytest.raises(ProtectedAddressError, match="adresse protégée"):
        blockable_ip(NAT_IP)


def test_the_watch_says_each_name_its_overlaps_and_the_list_at_its_start(cfg_file):
    cfg_file.write_text("networks:\n  bureau: [198.51.100.0/28]\n  dmz: {subnet: vnet-hub/snet-dmz}\n"
                        "  libre: [203.0.113.0/25]\nnever_block: [bureau, dmz]\n")
    cfg = config.load_glorfindel_config()
    before = cnw.start_lines(cfg)
    assert before[-1][0] == "loud" and "jamais lue" in before[-1][1] and "bloquable" in before[-1][1]
    _saved(cfg)
    lines = cnw.start_lines(cfg)
    said = [t for _, t in lines]
    assert "réseau nommé « dmz » : sous-réseau vnet-hub/snet-dmz → 203.0.113.0/26 — sert : never_block" in said
    assert "réseau nommé « libre » : 203.0.113.0/25 — sert : aucune clé" in said
    assert any(t.startswith("networks.libre : déclaré") for t in said)
    assert any(t.startswith("chevauchement : 203.0.113.0/26 (never_block, réseau nommé « dmz ») chevauche")
               for t in said)
    assert not [t for t in said if t.startswith("chevauchement") and t.count("« bureau »") == 2]   # one name
    assert lines[-1][0] == "info" and "jamais bloqué" in lines[-1][1]


def test_the_discovery_reads_the_network_at_its_own_cadence(cfg_file):
    from glorfindel.discovery import AssetRegistry, DiscoveryService
    calls = []
    svc = DiscoveryService(config.GlorfindelConfig(), AssetRegistry(cn._STORE.parent / "assets.json"),
                           network_reader=lambda: calls.append(1) or _read())
    svc.run_once()
    svc.run_once()
    assert calls == [1] and cn.load().state == "fresh"
    svc._network_read_at -= cn.READ_INTERVAL_S
    svc.run_once()
    assert calls == [1, 1]


def test_the_watch_prints_its_lines_loud_when_the_list_can_t_be_trusted(cfg_file):
    from rich.console import Console
    from glorfindel.watch.networks import say_networks
    console = Console(record=True, width=400)
    say_networks(console, dry_run=True)
    assert console.export_text() == ""                        # a dry run reads nothing
    cfg_file.write_text("networks:\n  bureau: [198.51.100.0/28]\nnever_block: [bureau]\n")
    say_networks(console, dry_run=False)
    out = console.export_text()
    assert "réseau nommé « bureau » : 198.51.100.0/28 — sert : never_block" in out
    assert "⚠ Réseau du client non fiable : liste du réseau du client jamais lue" in out


# ── Never read from a file the console writes (the review of CFG1) ──────────────────────────

def test_a_range_taken_out_of_a_file_the_console_writes_never_makes_its_address_blockable(cfg_file):
    """The console and the bot mount ~/.glorfindel writable: what decides the guard is the watch's own
    file, in runs/glorfindel/ — a list without the VNet written in ~/.glorfindel (where the registry is),
    and the registry itself rewritten, change nothing."""
    from glorfindel import discovery
    _saved()
    glorfindel_home = discovery._CACHE_FILE.parent             # ~/.glorfindel, under the conftest
    glorfindel_home.mkdir(parents=True, exist_ok=True)
    forged = _read(_arm([_vnet("vnet-hub", ["10.1.0.0/16"], {})]))
    forged["public_ips"] = []
    for name in ("client_network.json", "discovered_assets.json"):
        cn.save(forged, datetime.now(timezone.utc), path=glorfindel_home / name)
    assert not cn._STORE.is_relative_to(glorfindel_home)
    for ip in (IN_VNET, NAT_IP):
        with pytest.raises(ProtectedAddressError, match="réseau du client"):
            blockable_ip(ip)


def test_the_list_lives_in_the_watch_s_directory_read_only_to_the_console_and_the_bot():
    import yaml
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    assert cn.STORE_PARTS[0] == "network"
    source = (root / "glorfindel" / "client_network.py").read_text()
    assert "_STORE = runs_layout.dir_of(runs_layout.GLORFINDEL).joinpath(*STORE_PARTS)\n" in source
    assert ".glorfindel" not in source.split("_STORE = ", 1)[1].split("\n", 1)[0]
    assert "network" in __import__("eregion_core.runs_layout", fromlist=["_DIRS"])._DIRS["glorfindel"]
    services = yaml.safe_load((root / "docker-compose.yml").read_text())["services"]

    def mounts(service):
        return [v for v in services[service]["volumes"] if isinstance(v, str)]
    watch = [v for v in mounts("watch") if v.endswith(":/app/runs/glorfindel")]
    assert watch, "the watch mounts runs/glorfindel writable"
    assert any(v.endswith("/glorfindel:/app/runs/glorfindel:ro") for v in mounts("war-room"))
    assert not any(v.endswith("/glorfindel:/app/runs/glorfindel") for v in mounts("war-room"))
    bot = [v for v in mounts("bot") if "/app/runs/glorfindel" in v]
    assert sorted(bot) == sorted(["${EREGION_RUNS:-./runs}/glorfindel/queue:/app/runs/glorfindel/queue:ro",
                                  "${EREGION_RUNS:-./runs}/glorfindel/network:/app/runs/glorfindel/network:ro"])


def test_the_network_directory_is_made_before_compose_mounts_it():
    """Left to docker, the bot's mount made runs/glorfindel/network as root: the watch could no longer
    write the list there — never read, every block outside the Internet refused, said."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    make = (root / "Makefile").read_text()
    deploy = (root / "infra" / "glorfindel-host" / "deploy.sh").read_text()
    start = deploy.split("\nstart() {", 1)[1].split("\n}", 1)[0]
    assert start.index("runs/glorfindel/network") < start.index("docker compose --profile bot up")
    assert "runs/glorfindel/network" in make.split("RUNS_DIRS =", 1)[1].split("\n#", 1)[0]
    team = make.split("\nteam-start:", 1)[1].split("\n\n", 1)[0]
    assert team.index('mkdir -p "$(TEAM_DIR)/runs/glorfindel/network"') < team.index("up -d watch war-room")
