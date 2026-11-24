"""SEC2d (#1147): the lateral movement seen — the time 2 of SEC2, behind a switch off by default.

Decisions of Jonathan of 23/11 (1, 2, 5, 8) and of 24/11: `GLORFINDEL_LATERAL` off, nothing the model sees
changes to the byte (the shipped rule, the message, the prompt, the tool); on, `ssh-brute-force` sees every
source, and the code classes the address in the order of decision 8 — the platform, `never_block`, an
expected origin, the exposed zone, the rest of the client's network, the Internet. The Internet is blocked
as before; an expected origin set aside, said and counted; the client's network never blocked, and a card
proposes to isolate the monitored VM that holds the address — never an isolation alone, `full_auto` too.

The client's network is the store the discovery writes (glorfindel/client_network.py, under the conftest's
tmp home); the rule runs on lines the test writes (tests/unit/kql_subset.py). Every identifier is made up
(the repository is public): private ranges, documentation addresses (RFC 5737), example names. No Azure, no
model (patched). Mutants M7360–M7379 (scripts/mutants/SEC2d.py).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from glorfindel import agent, client_network as cn, client_network_watch as cnw, config, escalations, lateral
from glorfindel.config import AutonomyConfig
from glorfindel.detection_rules import DetectionRule, RulePoller, base_rule_sha256, load_config, shipped_rules_path
from glorfindel.discovery import AssetRegistry, DiscoveredAsset
from glorfindel.response.policy import (
    CLIENT, EXPECTED, EXPOSED, NEVER_BLOCK, ProtectedAddressError, blockable_ip, held_words, protection,
)

from . import kql_subset

ROOT = Path(__file__).resolve().parents[2]
SUB = "/subscriptions/00000000-0000-0000-0000-0000000000dd"
NET = f"{SUB}/resourceGroups/rg-net/providers/Microsoft.Network"
SRC_IP = "10.1.1.4"              # vm-src, a monitored VM of the client's VNet
FW_IP = "10.1.1.5"               # an appliance (its NIC forwards packets)
TWICE = "10.1.1.6"               # two VMs hold it (two VNets reuse it)
LONE = "10.1.1.7"                # held by a VM Glorfindel does not watch
NOBODY = "10.1.1.9"              # no NIC read holds it
SCANNER = "10.1.2.0/28"          # the client's internal scanner: an expected origin
SCAN_IP = "10.1.2.9"
DMZ = "203.0.113.0/26"           # the exposed zone, in the client's VNet
DMZ_HOST = "203.0.113.40"        # one host of it
INTERNET = "198.51.100.77"
SHIPPED_SHA256 = "4f13b251c9d4abed6686e32a0a4cd55f2a31b56e87b09895b8d38e69c7f696ec"   # the whole shipped rule
QUERY_SHA256 = "1ffd9d9a07bc9f24de22b62b19d41c03c5341156a96ba97d55a977d14424af19"     # its query, to the byte
NOW = datetime.now(timezone.utc)


def _vm(name: str) -> str:
    return f"{SUB}/resourceGroups/rg-app/providers/Microsoft.Compute/virtualMachines/{name}"


TARGET = _vm("vm-target")
SOURCE = _vm("vm-src")


def _nic(name: str, vm: str, ips: list[str], forwarding: bool = False) -> dict:
    return {"id": f"{NET}/networkInterfaces/{name}", "vm": _vm(vm), "forwarding": forwarding, "private_ips": ips}


def _read() -> dict:
    return {
        "vnets": [{"id": f"{NET}/virtualNetworks/vnet-hub", "name": "vnet-hub",
                   "prefixes": ["10.1.0.0/16", "203.0.113.0/24"],
                   "subnets": [{"name": "snet-app", "prefixes": ["10.1.1.0/24"]},
                               {"name": "snet-ops", "prefixes": ["10.1.2.0/24"]},
                               {"name": "snet-dmz", "prefixes": [DMZ]}]}],
        "public_ips": [], "prefixes": [], "frontends": [],
        "nics": [_nic("nic-src", "vm-src", [SRC_IP]), _nic("nic-tgt", "vm-target", ["10.1.1.10"]),
                 _nic("nic-fw", "vm-fw", [FW_IP], forwarding=True), _nic("nic-a", "vm-a", [TWICE]),
                 _nic("nic-b", "vm-b", [TWICE]), _nic("nic-lone", "vm-lone", [LONE]),
                 _nic("nic-dmz", "vm-dmz", [DMZ_HOST]), _nic("nic-scan", "vm-scan", [SCAN_IP])],
        "unread": [],
    }


@pytest.fixture
def cfg_file(tmp_path, monkeypatch):
    path = tmp_path / "glorfindel-config.yaml"
    monkeypatch.setattr(config, "_DEFAULT_PATHS", [path])
    path.write_text(f"networks:\n  scanner: [{SCANNER}]\nnetwork_zones:\n  expected_origins: [scanner]\n"
                    f"  exposed: [{DMZ}]\n")
    return path


@pytest.fixture
def lateral_on(monkeypatch):
    monkeypatch.setenv(lateral.SWITCH, "on")


@pytest.fixture
def network(cfg_file):
    """The client's network read, fresh; vm-src and vm-target watched."""
    cn.save(_read(), datetime.now(timezone.utc), config.load_glorfindel_config().networks)
    now = datetime.now(timezone.utc).isoformat()
    AssetRegistry().update([DiscoveredAsset(name=n, resource_id=_vm(n), monitoring_backend="law", last_seen=now)
                            for n in ("vm-src", "vm-target", "vm-dmz")])


def _cards(kind: str | None = None) -> list[dict]:
    return [e for e in escalations.pending() if kind is None or e["escalation_type"] == kind]


def _shipped() -> dict:
    return next(r for r in yaml.safe_load(shipped_rules_path().read_text())["rules"] if r["name"] == lateral.RULE)


def _loaded(**kw):
    return next(r for r in load_config(shipped_rules_path(), client_layer=False, **kw).rules if r.name == lateral.RULE)


# ── The switch ─────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,on", [(None, False), ("", False), ("off", False), (" on ", True), ("on", True)])
def test_the_switch_is_off_unless_on(value, on):
    assert lateral.switch({} if value is None else {lateral.SWITCH: value}) == (on, "")


@pytest.mark.parametrize("value", ["ON", "1", "true", "oui"])
def test_an_unknown_switch_stays_off_and_is_said_once(value, monkeypatch, capsys):
    """M7360: only `on` switches it on — never a guess."""
    monkeypatch.setenv(lateral.SWITCH, value)
    monkeypatch.setattr(lateral, "_said", set())
    assert lateral.on() is False and lateral.on() is False
    err = capsys.readouterr().err
    assert err.count("inconnu") == 1 and "l'interrupteur reste éteint" in err
    assert ("loud", lateral.switch()[1]) in lateral.start_lines(config.GlorfindelConfig(), cn.load())


def test_the_switch_is_the_watch_s_alone_in_compose():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    services = compose["services"]
    assert services["watch"]["environment"][lateral.SWITCH] == "${GLORFINDEL_LATERAL:-}"
    assert [n for n, s in services.items() if lateral.SWITCH in (s.get("environment") or {})] == ["watch"]


# ── Off: nothing the model sees changes to the byte ────────────────────────────────────────────

def _brute_force(ip: str, rid: str = TARGET, **context) -> dict:
    row = {"Computer": rid.rsplit("/", 1)[-1], "_ResourceId": rid, "SourceIP": ip, "FailedAttempts": 31}
    return {"signal_id": f"rule-ssh-brute-force-{ip}", "event": "detection", "ttp": "T1110.001", "severity": "high",
            "resource_id": rid, "resource_type": "vm", "timestamp": "2026-11-24T10:05:00+00:00",
            "context": {"rule_name": lateral.RULE, "attribution": "asset",
                        "run_id": "watch-ssh-brute-force-20261124T100500Z", **context},
            "raw_signal": {"first_result_row": row}}


def _llm(action: str) -> MagicMock:
    call = MagicMock()
    call.function.arguments = json.dumps({
        "reasoning": f"r — {action}", "confidence": 0.95, "action": action, "reversible": True,
        "explanation": "e", "escalate": False, "escalation_reason": "", "suggested_steps": []})
    resp = MagicMock()
    resp.choices[0].message.tool_calls = [call]
    resp.usage = None
    return resp


def _seen(signal: dict) -> str:
    """What the model is sent for this signal (its messages and its tool), as text."""
    seen: list[dict] = []

    def completion(**kw):
        seen.append(kw)
        return _llm("no_action")
    state = {"signal": signal, "past_cycles": [], "incident": None, "dry_run": True, "telemetry_gaps": []}
    with patch("litellm.completion", side_effect=completion):
        agent.decide(state, model="anthropic/claude-test", autonomy=AutonomyConfig(default="human_only"))
    return json.dumps({"messages": seen[0]["messages"], "tools": seen[0]["tools"]}, sort_keys=True, ensure_ascii=False)


def test_off_nothing_the_model_sees_changes_to_the_byte(monkeypatch):
    """The criterion of the lot, said: off, the shipped rule loads to the byte, the prompt, the tool and the
    message are the ones frozen by the suite — and on, for one signal, the message and the prompt and the tool
    are the same: the switch changes which detections reach the model, never what it reads of one."""
    from tests.unit.test_cycle_line import PAST, USER_SHA256, _bree
    from tests.unit.test_identity_plan import PROMPT_SHA256, TOOL_SHA256
    rule = _loaded()
    assert hashlib.sha256(rule.query.encode()).hexdigest() == QUERY_SHA256 and base_rule_sha256(_shipped()) == SHIPPED_SHA256
    assert hashlib.sha256(agent._SYSTEM_PROMPT.encode()).hexdigest() == PROMPT_SHA256
    assert hashlib.sha256(json.dumps(agent._DECISION_TOOL, sort_keys=True).encode()).hexdigest() == TOOL_SHA256
    assert hashlib.sha256(agent._build_user_message(_bree(), PAST).encode()).hexdigest() == USER_SHA256
    off = _seen(_brute_force(INTERNET))
    monkeypatch.setenv(lateral.SWITCH, "on")
    assert _seen(_brute_force(INTERNET)) == off
    assert hashlib.sha256(agent._build_user_message(_bree(), PAST).encode()).hexdigest() == USER_SHA256


def test_off_the_base_is_read_as_shipped_the_very_object():
    base = {"rules": [_shipped()]}
    assert lateral.base_rules(base, shipped_rules_path()) == (base, []) and lateral.base_rules(base, shipped_rules_path())[0] is base


# ── On: the rule sees every source ─────────────────────────────────────────────────────────────

def _line(ip: str, minutes_ago: float = 1, i: int = 0, rid: str = TARGET) -> dict:
    return {"Type": "Syslog", "TimeGenerated": NOW - timedelta(minutes=minutes_ago), "Facility": "auth",
            "ProcessName": "sshd", "Computer": rid.rsplit("/", 1)[-1], "_ResourceId": rid,
            "SyslogMessage": f"Failed password for root from {ip} port {40000 + i} ssh2"}


def _attempts(ip: str, n: int = 12) -> list[dict]:
    return [_line(ip, i=i) for i in range(n)]


def test_on_the_variant_sees_the_client_s_network_the_shipped_rule_does_not(lateral_on, monkeypatch):
    """M7361: the variant takes off the filter of the private ranges — the loopback stays out; every other key
    as shipped."""
    lines = _attempts(SRC_IP) + _attempts("127.0.0.1") + _attempts(INTERNET)
    variant = _loaded()
    assert sorted(r["SourceIP"] for r in kql_subset.run(variant.query, lines, now=NOW)) == [SRC_IP, INTERNET]
    assert [r["SourceIP"] for r in kql_subset.run(_shipped()["query"], lines, now=NOW)] == [INTERNET]
    v, shipped = lateral.variant(_shipped()), _shipped()
    assert {k: x for k, x in v.items() if k not in ("query", "description")} == \
           {k: x for k, x in shipped.items() if k not in ("query", "description")}
    monkeypatch.setenv(lateral.SWITCH, "off")
    assert _loaded().query == shipped["query"]


def test_on_a_shipped_rule_that_lost_its_filter_loads_as_shipped_and_is_said(lateral_on, tmp_path, monkeypatch):
    rule = {**_shipped(), "query": "Syslog | where SourceIP != \"\"\n"}
    assert lateral.variant(rule) is None
    base, notes = lateral.base_rules({"rules": [rule]}, shipped_rules_path())
    assert base["rules"] == [rule] and "n'a plus le filtre des plages privées" in notes[0]


def test_on_a_base_that_is_not_the_shipped_one_is_never_changed(lateral_on, tmp_path):
    other = tmp_path / "rules.yaml"
    base = {"rules": [_shipped()]}
    assert lateral.base_rules(base, other) == (base, [])


def test_on_the_client_s_layer_overrides_the_variant_and_a_copy_of_the_shipped_rule_is_set_aside(lateral_on, tmp_path):
    """P1: a client rule of its name wins; WL1: a copy of the shipped rule (its `base_sha256`) is stale against
    the variant — set aside, the variant loads."""
    layer = tmp_path / "client_rules.yaml"
    own = {**_shipped(), "query": _shipped()["query"] + "| where FailedAttempts >= 20\n"}
    layer.write_text(yaml.safe_dump({"rules": [own]}))
    loaded = next(r for r in load_config(shipped_rules_path(), client_layer=layer).rules if r.name == lateral.RULE)
    assert loaded.query == own["query"] and loaded.layer == "client"
    layer.write_text(yaml.safe_dump({"rules": [{**own, "base_sha256": SHIPPED_SHA256}]}))
    cfg = load_config(shipped_rules_path(), client_layer=layer)
    loaded = next(r for r in cfg.rules if r.name == lateral.RULE)
    assert loaded.query == lateral.variant(_shipped())["query"] and loaded.layer == "base"
    assert any("variante du temps 2" in n for n in cfg.notes)


# ── network_zones.expected_origins, read strictly ──────────────────────────────────────────────

def test_the_expected_origins_are_read_their_names_cited_where_they_serve(cfg_file):
    cfg_file.write_text(f"networks:\n  scanner: [{SCANNER}]\n  ops: {{subnet: vnet-hub/snet-ops}}\n"
                        "network_zones:\n  expected_origins: [scanner, ops, 198.51.100.8/29]\n")
    cfg = config.load_glorfindel_config()
    assert cfg.expected_origins == [SCANNER, "198.51.100.8/29"] and cfg.expected_names == ["scanner", "ops"]
    assert cfg.network_uses == {"scanner": ["network_zones.expected_origins"], "ops": ["network_zones.expected_origins"]}


@pytest.mark.parametrize("entry,said", [
    ("10.0.0.0/8", "plus large que /16"),                                       # M7362: never a /8
    ("168.63.129.16/32", "plateforme Azure"),
    ("127.0.0.0/24", "touche 127.0.0.0/8"),
    ("inconnu", "aucun réseau nommé « inconnu » déclaré"),                     # M7363: an unknown name
    ("10.1.2.1/28", "bits d'hôte"),
])
def test_an_origin_too_wide_on_the_platform_or_unknown_refuses_the_file(entry, said, cfg_file):
    cfg_file.write_text(f"network_zones:\n  expected_origins: [\"{entry}\"]\n")
    with pytest.raises(config.ConfigError, match="network_zones.expected_origins") as err:
        config.load_glorfindel_config()
    assert said in str(err.value)


def test_an_empty_list_of_origins_refuses_the_file(cfg_file):
    cfg_file.write_text("network_zones:\n  expected_origins: []\n")
    with pytest.raises(config.ConfigError, match="une liste vide ne déclare aucune origine"):
        config.load_glorfindel_config()


# ── The order of decision 8: one test per frontier ─────────────────────────────────────────────

def test_off_an_expected_origin_is_the_client_s_network_as_before(network):
    assert protection(SCAN_IP).layer == CLIENT


def test_never_block_wins_over_an_expected_origin(cfg_file, lateral_on):
    """M7364: an address both in never_block and an expected origin is never_block's — never set aside."""
    cfg_file.write_text(f"never_block: [{SCAN_IP}]\nnetworks:\n  scanner: [{SCANNER}]\n"
                        "network_zones:\n  expected_origins: [scanner]\n")
    cn.save(_read(), datetime.now(timezone.utc), config.load_glorfindel_config().networks)
    cfg = config.load_glorfindel_config()
    assert protection(SCAN_IP).layer == NEVER_BLOCK and protection("10.1.2.10").layer == EXPECTED
    rows = [{"SourceIP": SCAN_IP}, {"SourceIP": "10.1.2.10"}]
    assert lateral.origin_rows(rows, cfg) == {id(rows[1])}


def test_an_expected_origin_wins_over_the_exposed_zone_and_the_overlap_is_said(cfg_file, lateral_on):
    """M7365: an origin inside the exposed zone is the origin's — set aside, never blockable — and the
    overlap said at the start, never refused."""
    cfg_file.write_text(f"network_zones:\n  expected_origins: [203.0.113.32/28]\n  exposed: [{DMZ}]\n")
    cn.save(_read(), datetime.now(timezone.utc), {})
    cfg = config.load_glorfindel_config()
    assert protection(DMZ_HOST).layer == EXPECTED and protection("203.0.113.20").layer != EXPECTED
    with pytest.raises(ProtectedAddressError, match="origine attendue"):
        blockable_ip(DMZ_HOST)
    assert "origine attendue" in held_words(DMZ_HOST)
    notes = [t for lvl, t in cnw.start_lines(cfg) if lvl == "note"]
    assert any(t.startswith("chevauchement : 203.0.113.32/28 (origine attendue) chevauche 203.0.113.0/26 (zone "
                            "exposée) — origine attendue l'emporte") for t in notes), notes


def test_the_exposed_zone_wins_over_the_client_s_network_no_card_of_the_source(network, lateral_on):
    """M7366: one host of the exposed zone is blockable (SEC2c), never the client's network's card."""
    assert protection(DMZ_HOST).layer == EXPOSED
    assert lateral.judge(_brute_force(DMZ_HOST)) is None


def test_the_rest_of_the_client_s_network_is_never_blocked_and_gets_its_card(network, lateral_on):
    j = lateral.judge(_brute_force(SRC_IP))
    assert j["vm"] == SOURCE and j["entry"] == "10.0.0.0/8" and j["why"] == ""
    assert lateral.judge(_brute_force(INTERNET)) is None                         # the Internet: as before


# ── An expected origin: set aside, said, counted ───────────────────────────────────────────────

class _Registry:
    def __init__(self):
        self.assets = [type("A", (), {"name": "vm-target", "resource_id": TARGET})()]

    def for_backend(self, _name):
        return self.assets


class _Kql:
    def __init__(self, lines):
        self.lines = lines

    def run_query(self, query, timespan=None):
        return kql_subset.run(query, self.lines, now=NOW)


def _poll(lines, cfg, times: int = 1):
    r = _loaded()
    rule = DetectionRule(name=r.name, source="azure_monitor", workspace_id="ws", query=r.query, ttp=r.ttp,
                         resource_id="", interval_s=30, auto_apply=True, monitoring_backend_name="law")
    sent: list = []
    p = RulePoller([rule], sent.append)
    p._detector = lambda _r: _Kql(lines)
    p._registry = _Registry()
    p._cfg = cfg
    for _ in range(times):
        p.poll_once(rule)
    return sent, p


def _ips(sent) -> list[str]:
    return sorted(s["raw_signal"]["first_result_row"]["SourceIP"] for s in sent)


def test_a_detection_from_an_expected_origin_is_set_aside_said_and_counted_once(network, lateral_on, caplog):
    """M7367, M7368: the scanner's brute force opens no signal, counted once per window — the source of the
    client's network still one."""
    cfg = config.load_glorfindel_config()
    caplog.set_level("INFO", logger="glorfindel.detection_rules")
    sent, p = _poll(_attempts(SCAN_IP) + _attempts(SRC_IP), cfg, times=2)
    assert _ips(sent) == [SRC_IP]
    assert lateral.origin_counts(p._status[lateral.RULE])["expected_origin_count"] == 1
    assert "from an expected origin set aside" in caplog.text


def test_off_nothing_is_set_aside_and_the_shipped_rule_sees_no_private_source(network, monkeypatch):
    cfg = config.load_glorfindel_config()
    assert lateral.origin_rows([{"SourceIP": SCAN_IP}], cfg) == set()
    sent, p = _poll(_attempts(SCAN_IP) + _attempts(SRC_IP) + _attempts(INTERNET), cfg)
    assert _ips(sent) == [INTERNET] and "expected_origins" not in p._status[lateral.RULE]


def test_on_without_an_expected_origin_every_source_is_a_signal(network, lateral_on, cfg_file):
    cfg_file.write_text("network_zones:\n  exposed: [203.0.113.0/26]\n")
    sent, _ = _poll(_attempts(SCAN_IP) + _attempts(SRC_IP), config.load_glorfindel_config())
    assert _ips(sent) == sorted([SCAN_IP, SRC_IP])


# ── The card of the source: a proposal, never an isolation alone ───────────────────────────────

class _Recorder:
    """Azure in place: each write recorded with the VM it aims at."""
    read_only = False
    dry_run = False
    _subscription_id = "s"

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def isolate_vm(self, resource_id):
        self.calls.append(("isolate_vm", resource_id))
        return {"status": "isolated", "resource_id": resource_id}

    def block_suspicious_ip(self, ip, resource_id, **_kw):
        self.calls.append(("block_suspicious_ip", ip))
        return {"status": "blocked", "ip": ip}

    def snapshot(self, resource_id, **_kw):
        self.calls.append(("snapshot", resource_id))
        return {"status": "snapshot_started", "snapshot_id": "snap-1"}

    def verify_isolation(self, resource_id):
        return {"verified": True, "method": "test"}

    def verify_block_ip(self, ip, resource_id):
        return {"verified": True, "method": "test"}

    def __getattr__(self, name):          # every other read: nothing to say
        return lambda *a, **k: {}


@pytest.fixture
def graph(tmp_path, monkeypatch):
    for var in ("GLORFINDEL_WEBHOOK_URL", "DISCORD_BOT_TOKEN", "GLORFINDEL_LLM_BASE_URL", "GLORFINDEL_READ_ONLY",
                "GLORFINDEL_CONFIDENCE_THRESHOLD", "GLORFINDEL_DECISION_DRAWS"):
        monkeypatch.delenv(var, raising=False)
    from eregion_core import llm_call
    monkeypatch.setattr(llm_call, "_AUTO_TOOL_CHOICE", set())
    monkeypatch.setattr(llm_call, "_NO_TEMPERATURE", set())
    monkeypatch.setattr(escalations, "notify_action", lambda **kw: None)
    from tests.unit.test_dependency_failures import FakeMemory
    monkeypatch.setattr(agent, "CycleMemory", FakeMemory)
    monkeypatch.chdir(tmp_path)                 # the cycle's debug line under runs/, in tmp

    def run(signal, action, mode="full_auto"):
        from tests.unit.test_dependency_failures import LogAnalytics
        conn = _Recorder()
        a = agent.GlorfindelAgent(connector=conn, memory_path="unused", incidents_path=str(tmp_path / "inc.jsonl"),
                                  model="anthropic/claude-test", dry_run=False,
                                  autonomy=AutonomyConfig(default=mode),
                                  readiness_gate=lambda vm, rid, configured: (configured, {}))
        with patch("litellm.completion", return_value=_llm(action)), \
                patch("glorfindel.detectors.detector_for", return_value=LogAnalytics(fail=False)):
            final = a.respond(signal)
        return final, conn
    return run


@pytest.mark.parametrize("mode", ["full_auto", "non_disruptive", "human_only"])
@pytest.mark.parametrize("action", ["block_suspicious_ip", "isolate_vm", "no_action"])
def test_a_source_vm_is_proposed_never_isolated_whatever_the_mode(network, lateral_on, graph, mode, action):
    """M7369, M7370: full_auto too — the source VM never isolated, the client's address never blocked; one card
    proposes the isolation of the source, approvable by the path of every held card. The model's own choice on
    the target runs as its gates judge it."""
    final, conn = graph(_brute_force(SRC_IP), action, mode)
    assert ("isolate_vm", SOURCE) not in conn.calls
    assert not [c for c in conn.calls if c[0] == "block_suspicious_ip"]
    [card] = _cards(lateral.SOURCE_TYPE)
    assert (card["resource_id"], card["action"]) == (SOURCE, "isolate_vm")
    assert "jamais exécutée seule" in card["reason"] and "que son invité peut écrire" in card["reason"]
    from eregion_core.action_queue import APPROVABLE_TYPES
    from glorfindel import approval
    assert lateral.SOURCE_TYPE in APPROVABLE_TYPES and approval.approval_refusal(card, "vm-src") is None
    if action == "block_suspicious_ip":
        assert final["held_by"] == "never_block" and final["escalate"] is True           # SEC2b, on
    if action == "isolate_vm" and mode == "full_auto":
        assert conn.calls == [("isolate_vm", TARGET)]                                   # the model's, on the target


@pytest.mark.parametrize("ip,why", [
    (FW_IP, "adresse d'une appliance"),
    (TWICE, "tenue par 2 VM"),
    (LONE, "une VM que Glorfindel ne surveille pas"),
    (NOBODY, "aucune carte réseau lue ne la tient"),
])
def test_no_monitored_vm_to_isolate_gives_a_card_for_a_human(network, lateral_on, graph, ip, why):
    """M7371: by the exact address only — an appliance, two VMs, a VM unwatched, nobody: a card for a human,
    on the target, nothing to approve."""
    graph(_brute_force(ip), "block_suspicious_ip")
    assert _cards(lateral.SOURCE_TYPE) == []
    [card] = _cards(lateral.HUMAN_TYPE)
    assert card["resource_id"] == TARGET and card["action"] == "none" and why in card["reason"]
    assert card["action_params"] == {"ip": ip}
    from eregion_core.action_queue import APPROVABLE_TYPES
    assert lateral.HUMAN_TYPE not in APPROVABLE_TYPES


def test_a_list_that_can_t_be_trusted_names_no_source_vm(cfg_file, lateral_on, graph):
    """M7372: the list never read — the VM that holds the address is not sure: a card for a human."""
    AssetRegistry().update([DiscoveredAsset(name="vm-src", resource_id=SOURCE, monitoring_backend="law",
                                            last_seen=datetime.now(timezone.utc).isoformat())])
    graph(_brute_force(SRC_IP), "no_action")
    [card] = _cards(lateral.HUMAN_TYPE)
    assert "liste du réseau du client non fiable" in card["reason"] and _cards(lateral.SOURCE_TYPE) == []


def test_a_detection_that_names_no_vm_proposes_no_source(network, lateral_on):
    j = lateral.judge(_brute_force(SRC_IP, attribution="unattributed"))
    assert j["vm"] == "" and "la ligne ne nomme aucune VM" in j["why"]


def test_off_no_card_of_the_source(network, graph):
    graph(_brute_force(SRC_IP), "block_suspicious_ip")
    assert _cards(lateral.SOURCE_TYPE) == _cards(lateral.HUMAN_TYPE) == []


def test_never_in_a_dry_run(network, lateral_on):
    lateral.record_card({"signal": _brute_force(SRC_IP), "dry_run": True}, "real", "")
    assert _cards() == []


def test_what_comes_from_outside_is_never_written_raw(network, lateral_on):
    """#254: the address the line writes reaches the card only judged, canonical — a forged text never."""
    lateral.record_card({"signal": _brute_force(f"{SRC_IP}<script>"), "dry_run": False}, "real", "")
    assert _cards() == []
    lateral.record_card({"signal": _brute_force(f"::ffff:{SRC_IP}"), "dry_run": False}, "real", "")
    [card] = _cards(lateral.SOURCE_TYPE)
    assert "::ffff" not in card["reason"] and f"depuis {SRC_IP}," in card["reason"] and "<" not in card["reason"]


@pytest.mark.parametrize("on", [False, True])
def test_the_guard_and_the_connector_refuse_a_block_in_the_client_s_network_on_or_off(network, monkeypatch, on):
    """M7373 (SEC2b, on or off): decide's guard holds the block, `blockable_ip` refuses it."""
    if on:
        monkeypatch.setenv(lateral.SWITCH, "on")
    d = {"action": "block_suspicious_ip", "escalate": False, "escalation_reason": ""}
    agent._apply_never_block_guard(d, _brute_force(SRC_IP))
    assert d["escalate"] is True and d["held_by"] == "never_block"
    with pytest.raises(ProtectedAddressError, match="réseau du client"):
        blockable_ip(SRC_IP)
    assert blockable_ip(INTERNET) == INTERNET


# ── At the watch's start ───────────────────────────────────────────────────────────────────────

def test_on_the_switch_is_said_loud_and_each_origin(network, lateral_on):
    """M7374."""
    lines = cnw.start_lines(config.load_glorfindel_config())
    strong = [t for lvl, t in lines if lvl == "strong"]
    assert any(t.startswith("Mouvement latéral vu (GLORFINDEL_LATERAL=on") for t in strong)
    assert any(t.startswith(f"Origine attendue {SCANNER} (origine attendue, réseau nommé « scanner »)")
               for lvl, t in lines if lvl == "info")
    assert any("réseau nommé « scanner »" in t and "sert : network_zones.expected_origins" in t for _, t in lines)
    assert not any("en plage privée : la règle livrée" in t for _, t in lines)       # decision 6's note: time 1


def test_off_the_origins_are_said_without_effect(network):
    lines = cnw.start_lines(config.load_glorfindel_config())
    assert ("note", "network_zones.expected_origins : scanner — sans effet tant que l'interrupteur "
                    "GLORFINDEL_LATERAL est éteint (SEC2d, 0.7)") in lines
    assert not any("Mouvement latéral vu" in t for _, t in lines)


# ── The review of SEC2c: a failed lift's card of a replaced episode ────────────────────────────

def test_the_card_of_a_failed_lift_closes_once_its_episode_is_replaced(monkeypatch):
    """M7375: a block written again over a failed lift (a new mark, a new deadline) closes the old card; a card
    of the block still there, its mark older than the card, stays."""
    from glorfindel import exposed_blocks as eb
    vm = _vm("vm-dmz")
    escalations.record(signal_id="exposed-x", resource_id=vm, action="none", escalation_type=eb.FAILED_TYPE,
                       reason="levée en échec", severity="high", source="real", action_params={"ip": DMZ_HOST})
    before = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    entry = {"resource_id": vm, "vm_name": "vm-dmz", "ip": DMZ_HOST, "exposed": {"at": before}}
    eb._close_replaced([entry])
    assert len(_cards(eb.FAILED_TYPE)) == 1
    eb._close_replaced([{**entry, "exposed": {"at": (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat()}}])
    assert _cards(eb.FAILED_TYPE) == []
    [closed] = [e for e in escalations.all_escalations() if e["escalation_type"] == eb.FAILED_TYPE]
    assert closed["resolution"].startswith("remplacée : un nouveau blocage")


def test_the_expiry_pass_closes_it(monkeypatch):
    from glorfindel import exposed_blocks as eb
    vm = _vm("vm-dmz")
    escalations.record(signal_id="exposed-x", resource_id=vm, action="none", escalation_type=eb.FAILED_TYPE,
                       reason="levée en échec", severity="high", source="real", action_params={"ip": DMZ_HOST})
    later = (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat()
    deadline = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    monkeypatch.setattr(eb, "marked", lambda: [{"resource_id": vm, "vm_name": "vm-dmz", "ip": DMZ_HOST,
                                                 "exposed": {"at": later, "expires_at": deadline}}])
    assert eb.expiry_pass(connector=None) == [] and _cards(eb.FAILED_TYPE) == []


# ── The console ────────────────────────────────────────────────────────────────────────────────

def test_the_console_names_both_cards_and_approves_the_source_s_only():
    js = (ROOT / "eregion_console/static/glorfindel.js").read_text()
    import re
    held = re.search(r"const _HELD_TYPES = new Set\(\[([^\]]*)\]\);", js).group(1)
    assert f"'{lateral.SOURCE_TYPE}'" in held and lateral.HUMAN_TYPE not in held
    assert f"  {lateral.SOURCE_TYPE}:" in js and f"  {lateral.HUMAN_TYPE}:" in js
    assert lateral.SOURCE_TYPE in escalations._ESCALATION_LABELS and lateral.HUMAN_TYPE in escalations._ESCALATION_LABELS
