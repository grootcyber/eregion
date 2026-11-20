"""IPS2a (Partie de #950) — the NSG audit gives the addresses of a VM without NSG, and a failed
public IP read carries its code.

The contract, set with the Console session:
- a VM with a NIC that has no NSG (neither its own nor its subnet's): the « NSG access » check stays
  `fail`, with its reason as before, and carries `data.nsgs[]`, one entry per NIC — `nsg_scope:
  "none"` and `nsg: ""` for a NIC without NSG, the rest as before for one that has one, `ips` and
  `public_ips` for each;
- an element of `public_ips` that failed carries `code` (forbidden, not_found, not_allocated,
  unreadable) beside `error`, the French text, unchanged; a read address has no `code`;
- nothing else changes in the shape rendered.

And the safety: a `fail` that carries data stays a failure for every reader of the audit — the
audit's own verdict (the console's /api/audit and the watch's startup audit read it), the
readiness (and so the autonomy gate of `decide`, and the bot's « held » card), the posture. None
takes `data.nsgs` for an NSG that reads, nor for an isolation or a block that is possible.

On the in-memory Azure (fake_azure.py): no Azure call. Documentation addresses only (RFC 5737,
RFC 1918).
"""
from __future__ import annotations

from unittest.mock import MagicMock

from glorfindel.actions import AzureConnector
from glorfindel.audit import AuditResult, _check_nsg
from glorfindel.config import ActionBackendConfig, GlorfindelConfig
from glorfindel.discovery import DiscoveredAsset
from glorfindel.posture import PostureChecker
from glorfindel.providers.azure.public_ips import CODES, NOT_ALLOCATED, NOT_FOUND
from glorfindel.readiness import ReadinessGate, assess

from .fake_azure import FakeAzure, key, nic_id, public_ip_id, throttled, vm_id

WEB = vm_id("rg-app", "web")
PUBLIC = "198.51.100.10"        # RFC 5737
OTHER = "203.0.113.20"          # RFC 5737
NO_NSG = "NIC web-nic and its subnet have no NSG — cannot isolate VM"
ENTRY = {"nsg", "nsg_scope", "nic_id", "ips", "public_ips"}


def _world(nics: list[dict], pips: dict | None = None):
    """web in rg-app. Two subnets: `bare` (no NSG) and `app` (behind nsg-web). `nics`: what
    add_vm takes, `subnet` given by name; `public_ips` by the names of `pips` = {name: (rg,
    address)}, created first."""
    f = FakeAzure()
    ids = {name: f.add_public_ip(rg, name, address) for name, (rg, address) in (pips or {}).items()}
    nsg = f.add_nsg("rg-app", "nsg-web")
    subnets = {"bare": f.add_subnet("rg-net", "vnet", "bare", None),
               "app": f.add_subnet("rg-net", "vnet", "app", nsg)}
    f.add_vm("rg-app", "web", [{"rg": "rg-app", "nsg": None, **n, "subnet": subnets[n["subnet"]],
                                "public_ips": [ids[p] for p in n.get("public_ips", [])]}
                               for n in nics])
    c = AzureConnector(dry_run=False, read_only=True)
    c._network, c._compute = f.network, f.compute
    c._subscription_id = "s"
    return f, c, ids


def _one_bare_nic(**pips):
    return _world([{"name": "web-nic", "ips": ["10.0.0.4"], "subnet": "bare",
                    "public_ips": list(pips)}], pips)


def _access(c):
    check = _check_nsg(WEB, c)
    return check[0] if isinstance(check, list) else check


# ── The contract ────────────────────────────────────────────────────────────────

def test_a_vm_without_nsg_fails_and_carries_its_addresses():
    f, c, _ = _one_bare_nic(**{"web-pip": ("rg-app", PUBLIC)})
    res = c.check_nsg_access(WEB)
    assert res["ok"] is False and res["error"] == NO_NSG and res["iam"] is False
    [entry] = res["nsgs"]
    assert entry == {"nsg": "", "nsg_scope": "none", "nic_id": nic_id("rg-app", "web-nic"),
                     "ips": ["10.0.0.4"], "public_ips": [{"address": PUBLIC}]}
    # Nothing that would say an NSG reads: no rule count, no precedence, no primary NSG.
    assert set(res) == {"ok", "iam", "no_nsg", "error", "nsgs"}


def test_the_audit_check_stays_fail_with_its_reason_and_carries_nsgs():
    f, c, _ = _one_bare_nic(**{"web-pip": ("rg-app", PUBLIC)})
    check = _access(c)
    assert check.status == "fail"
    assert check.message == f"NSG not found or VM has no NSG — {NO_NSG}"
    assert check.fix == "Attach an NSG to the VM's NIC in resource group rg-app"
    assert check.data == {"nsgs": c.check_nsg_access(WEB)["nsgs"]}
    assert check.data["nsgs"][0]["nsg_scope"] == "none"
    assert check.data["nsgs"][0]["public_ips"] == [{"address": PUBLIC}]


def test_two_nics_one_without_nsg_each_its_entry():
    f, c, _ = _world([{"name": "web-nic", "ips": ["10.0.0.4"], "subnet": "bare", "public_ips": ["a-pip"]},
                      {"name": "web-nic2", "ips": ["10.0.1.4", "10.0.1.5"], "subnet": "app",
                       "public_ips": ["b-pip"]}],
                     {"a-pip": ("rg-app", PUBLIC), "b-pip": ("rg-edge", OTHER)})
    res = c.check_nsg_access(WEB)
    assert res["ok"] is False and res["error"] == NO_NSG
    bare, behind = res["nsgs"]
    assert bare == {"nsg": "", "nsg_scope": "none", "nic_id": nic_id("rg-app", "web-nic"),
                    "ips": ["10.0.0.4"], "public_ips": [{"address": PUBLIC}]}
    assert behind == {"nsg": "rg-app/nsg-web", "nsg_scope": "subnet", "nic_id": nic_id("rg-app", "web-nic2"),
                      "ips": ["10.0.1.4", "10.0.1.5"], "public_ips": [{"address": OTHER}]}
    check = _access(c)
    assert check.status == "fail" and [e["nsg_scope"] for e in check.data["nsgs"]] == ["none", "subnet"]


def test_the_nic_without_nsg_second_is_the_one_named():
    f, c, _ = _world([{"name": "web-nic2", "ips": ["10.0.1.4"], "subnet": "app"},
                      {"name": "web-nic", "ips": ["10.0.0.4"], "subnet": "bare"}])
    res = c.check_nsg_access(WEB)
    assert res["ok"] is False and res["error"] == NO_NSG
    assert [e["nsg_scope"] for e in res["nsgs"]] == ["subnet", "none"]


def test_a_nic_with_its_own_nsg_on_a_bare_subnet_is_not_bare():
    f, c, _ = _world([{"name": "web-nic", "ips": ["10.0.0.4"], "subnet": "bare"}])
    own = f.add_nsg("rg-app", "nsg-nic")
    f.nics[key(nic_id("rg-app", "web-nic"))]["nsg"] = own
    res = c.check_nsg_access(WEB)
    assert res["ok"] is True and res["nsgs"][0]["nsg_scope"] == "nic"


def test_a_subnet_that_does_not_read_is_never_said_none():
    """Unknown, not "none" (L24): the failure says as before, no address claimed."""
    def chaos(op, phase, write):
        if op == "subnet.get":
            raise throttled(op)
    f, c, _ = _one_bare_nic(**{"web-pip": ("rg-app", PUBLIC)})
    f.chaos = chaos
    res = c.check_nsg_access(WEB)
    assert res == {"ok": False, "iam": False, "no_nsg": True, "error": NO_NSG}
    assert f.public_ip_reads == []
    check = _access(c)
    assert check.status == "fail" and check.data == {}


def test_a_transient_looking_nic_name_does_not_turn_the_failure_into_a_warn():
    """The data's failure is never a transient warn, whatever the NIC's name."""
    f, c, _ = _world([{"name": "web-timeout", "ips": ["10.0.0.4"], "subnet": "bare"}])
    check = _access(c)
    assert check.status == "fail" and check.data["nsgs"][0]["nsg_scope"] == "none"


# ── The four codes ──────────────────────────────────────────────────────────────

def _codes_world():
    # One IP configuration per public IP (the fake pairs them by index).
    f, c, ids = _world([{"name": "web-nic", "ips": [f"10.0.0.{i}" for i in range(4, 9)], "subnet": "bare",
                         "public_ips": ["ok-pip", "refused-pip", "idle-pip", "slow-pip"]}],
                       {"ok-pip": ("rg-app", PUBLIC), "refused-pip": ("rg-edge", OTHER),
                        "idle-pip": ("rg-app", None), "slow-pip": ("rg-app", OTHER)})
    f.unreadable.add(key(ids["refused-pip"]))
    gone = public_ip_id("rg-app", "gone-pip")
    f.nics[key(nic_id("rg-app", "web-nic"))]["public_ips"].append(gone)

    calls = []

    def chaos(op, phase, write):              # the 4th read, slow-pip's, throttled
        if op == "public_ip.get":
            calls.append(op)
            if len(calls) == 4:
                raise throttled(op)
    f.chaos = chaos
    return f, c


def test_each_failed_read_carries_its_code_beside_its_unchanged_text():
    f, c = _codes_world()
    pips = c.check_nsg_access(WEB)["nsgs"][0]["public_ips"]
    read, refused, idle, slow, gone = pips
    assert read == {"address": PUBLIC}                     # a read address: no code
    assert refused["code"] == "forbidden" and refused["error"].startswith("lecture refusée (droits) : ")
    assert idle == {"address": None, "error": NOT_ALLOCATED, "code": "not_allocated"}
    assert slow["code"] == "unreadable" and slow["error"].startswith("illisible : ")
    assert gone == {"address": None, "error": NOT_FOUND, "code": "not_found"}
    assert {p["code"] for p in pips if "code" in p} == set(CODES)
    for p in (refused, idle, slow, gone):
        assert set(p) == {"address", "error", "code"} and p["address"] is None


def test_a_403_by_its_status_alone_is_forbidden_never_not_found():
    from glorfindel.providers.azure.public_ips import read_public_ips
    rid = public_ip_id("rg-app", "web-pip")
    exc = Exception("denied")
    exc.status_code = 403
    net = MagicMock()
    net.public_ip_addresses.get.side_effect = exc
    [pip] = read_public_ips(net, [rid], {})
    assert pip["code"] == "forbidden" and pip["error"] == "lecture refusée (droits) : denied"


def test_the_codes_also_on_a_vm_with_nsg():
    f, c, ids = _world([{"name": "web-nic", "ips": ["10.0.0.4", "10.0.0.5"], "subnet": "app",
                         "public_ips": ["web-pip", "idle-pip"]}],
                       {"web-pip": ("rg-app", PUBLIC), "idle-pip": ("rg-app", None)})
    res = c.check_nsg_access(WEB)
    assert res["ok"] is True
    assert res["nsgs"][0]["public_ips"] == [
        {"address": PUBLIC}, {"address": None, "error": NOT_ALLOCATED, "code": "not_allocated"}]


# ── The witness: a VM with NSG, unchanged ───────────────────────────────────────

def test_a_vm_with_nsg_is_unchanged():
    f, c, _ = _world([{"name": "web-nic", "ips": ["10.0.0.4"], "subnet": "app", "public_ips": ["web-pip"]}],
                     {"web-pip": ("rg-app", PUBLIC)})
    res = c.check_nsg_access(WEB)
    assert set(res) == {"ok", "nsg", "scope", "rules", "nsgs", "precedence"}
    assert res["ok"] is True and res["nsg"] == "rg-app/nsg-web" and res["scope"] == "subnet"
    assert res["nsgs"] == [{"nsg": "rg-app/nsg-web", "nsg_scope": "subnet", "nic_id": nic_id("rg-app", "web-nic"),
                            "ips": ["10.0.0.4"], "public_ips": [{"address": PUBLIC}]}]
    check = _access(c)
    assert check.status == "ok" and check.message == "NSG rg-app/nsg-web readable (0 rules)"
    assert set(check.data) == {"nsg", "nsg_scope", "nsgs"} and check.data["nsgs"] == res["nsgs"]
    assert set(check.data["nsgs"][0]) == ENTRY


def test_another_failure_carries_no_data_as_before():
    f, c, _ = _world([{"name": "web-nic", "ips": ["10.0.0.4"], "subnet": "app"}])
    f.vms.clear()                                          # the VM gone: a 404
    res = c.check_nsg_access(WEB)
    assert res["ok"] is False and "nsgs" not in res
    assert _access(c).data == {}


# ── Every reader: a fail that carries data stays a failure ─────────────────────

def _bare_res():
    _, c, _ = _one_bare_nic(**{"web-pip": ("rg-app", PUBLIC)})
    res = c.check_nsg_access(WEB)
    assert res["nsgs"], res
    return c, res


def test_the_audit_verdict_is_not_ready():
    """What /api/audit (the console) and the watch's startup audit read: `ready`, the checks."""
    c, _ = _bare_res()
    result = AuditResult(resource_id=WEB, timestamp="2026-11-19T00:00:00Z", checks=[_access(c)])
    assert result.ready is False
    d = result.to_dict()
    assert d["ready"] is False and d["checks"][0]["status"] == "fail"
    assert d["checks"][0]["data"]["nsgs"][0]["nsg_scope"] == "none"


def _readiness_conn(nsg_res: dict):
    m = MagicMock()
    m.read_only = False
    m._subscription_id = None
    m.check_permissions.return_value = {"ok": True, "missing": []}
    m.vm_os.return_value = "linux"
    m.check_nsg_access.return_value = nsg_res
    return m


def test_the_readiness_still_says_no_block_possible():
    _, res = _bare_res()
    a = assess(WEB, _readiness_conn(res))
    assert a["verdict"] == "reserve" and "no_nsg_for_blocks" in a["reserve_codes"]
    # Exactly as the failure without its data (before IPS2a).
    before = {k: v for k, v in res.items() if k != "nsgs"}
    assert assess(WEB, _readiness_conn(before)) == a


def test_the_autonomy_gate_holds_the_vm_in_human_only():
    """`decide` reads the readiness through ReadinessGate: the VM stays held (the bot's card)."""
    _, res = _bare_res()
    mode, hold = ReadinessGate(_readiness_conn(res))("web", WEB, "non_disruptive")
    assert mode == "human_only"
    assert hold["reason"] == "unconfirmed_reserves" and "no_nsg_for_blocks" in hold["codes"]


def test_the_posture_still_says_the_nsg_gap():
    _, res = _bare_res()
    conn = MagicMock()
    conn.check_nsg_access.return_value = res
    cfg = GlorfindelConfig(action_backends=[ActionBackendConfig(
        name="rsv", type="azure_backup_vault", vault_name="", resource_group="rg-app")])
    checker = PostureChecker(cfg, conn, dry_run=False)
    checker._state = {}
    gaps = checker._check_asset(DiscoveredAsset(name="web", resource_id=WEB, monitoring_backend="law",
                                                last_seen="2026-11-19T00:00:00Z"))
    [gap] = [g for g in gaps if g.check == "nsg_reachable"]
    assert gap.severity == "critical" and "impossible" in gap.message
    assert not getattr(checker, "_inconclusive", set())


# ── The order of the NICs never loosens the failure (review of IPS2a) ──────────

def _posture_gaps(res: dict):
    conn = MagicMock()
    conn.check_nsg_access.return_value = res
    cfg = GlorfindelConfig(action_backends=[ActionBackendConfig(
        name="rsv", type="azure_backup_vault", vault_name="", resource_group="rg-app")])
    checker = PostureChecker(cfg, conn, dry_run=False)
    checker._state = {}
    gaps = checker._check_asset(DiscoveredAsset(name="web", resource_id=WEB, monitoring_backend="law",
                                                last_seen="2026-11-19T00:00:00Z"))
    return gaps, getattr(checker, "_inconclusive", set())


def _assert_still_no_nsg(res: dict, name: str = "web-nic"):
    """Every reader still says the VM without NSG: the audit fails (never a warn, never an IAM
    fix), the readiness keeps `no_nsg_for_blocks`, the posture its critical gap."""
    no_nsg = f"NIC {name} and its subnet have no NSG — cannot isolate VM"
    assert res["ok"] is False and res["iam"] is False and res["error"] == no_nsg, res
    conn = MagicMock()
    conn.check_nsg_access.return_value = res
    check = _access(conn)
    assert check.status == "fail" and check.message == f"NSG not found or VM has no NSG — {no_nsg}"
    assert check.fix == "Attach an NSG to the VM's NIC in resource group rg-app"
    a = assess(WEB, _readiness_conn(res))
    assert "no_nsg_for_blocks" in a["reserve_codes"] and "nsg_unreadable" not in a["reserve_codes"]
    gaps, inconclusive = _posture_gaps(res)
    [gap] = [g for g in gaps if g.check == "nsg_reachable"]
    assert gap.severity == "critical" and not inconclusive


def _second_nic_fails(exc_of, first: str = "web-nic"):
    """`first` (no NSG, its subnet readable) read first, then web-nic2's read raises."""
    f, c, _ = _world([{"name": first, "ips": ["10.0.0.4"], "subnet": "bare"},
                      {"name": "web-nic2", "ips": ["10.0.1.4"], "subnet": "app"}])
    reads = []

    def chaos(op, phase, write):
        if op == "nic.get":
            reads.append(op)
            if len(reads) == 2:
                raise exc_of(op)
    f.chaos = chaos
    return c


def test_a_nic_without_nsg_read_before_a_throttled_one_keeps_the_failure():
    c = _second_nic_fails(throttled)
    res = c.check_nsg_access(WEB)
    assert "nsgs" not in res and res["no_nsg"] is True    # the other NIC unread: no data
    _assert_still_no_nsg(res)


def test_a_nic_without_nsg_read_before_a_timed_out_one_keeps_the_failure():
    c = _second_nic_fails(lambda op: TimeoutError(f"{op}: connection timed out"))
    res = c.check_nsg_access(WEB)
    assert "nsgs" not in res
    _assert_still_no_nsg(res)


def test_a_nic_named_like_an_authorization_error_is_never_an_iam_failure():
    from glorfindel.providers.azure.sdk import _is_iam_error
    name = "web-403-forbidden"
    assert _is_iam_error(f"NIC {name} and its subnet have no NSG — cannot isolate VM")
    f, c, _ = _world([{"name": name, "ips": ["10.0.0.4"], "subnet": "bare"}])
    res = c.check_nsg_access(WEB)
    assert res["nsgs"][0]["nsg_scope"] == "none"
    _assert_still_no_nsg(res, name)
    assert _access(c).data["nsgs"] == res["nsgs"]


def test_a_nic_named_like_a_timeout_after_a_failed_read_is_never_a_warn():
    c = _second_nic_fails(throttled, first="web-timeout")
    _assert_still_no_nsg(c.check_nsg_access(WEB), "web-timeout")
