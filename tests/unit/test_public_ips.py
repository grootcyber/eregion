"""IPS1a (#931) — the public IP of each network interface in the NSG audit.

`check_nsg_access` gives, for each entry of `nsgs[]`, `public_ips`: a list, empty without any
public IP on the NIC; an element is `{"address": "<address>"}`, or `{"address": None, "error":
"<reason>"}` when the read failed. A failed read never fails the audit. Each public IP is read
once per call, in its own resource group (taken from its id). On the in-memory Azure
(fake_azure.py): no Azure call. Documentation addresses only (RFC 5737, RFC 1918).
"""
from __future__ import annotations

from unittest.mock import MagicMock

from glorfindel.actions import AzureConnector
from glorfindel.audit import _check_nsg
from glorfindel.providers.azure.public_ips import NOT_ALLOCATED, NOT_FOUND, read_public_ips

from .fake_azure import FakeAzure, key, public_ip_id, throttled, vm_id

WEB = vm_id("rg-app", "web")
PUBLIC = "198.51.100.10"        # RFC 5737
OTHER = "203.0.113.20"          # RFC 5737


def _world(nics: list[dict]):
    """web in rg-app, behind nsg-web on its subnet; `nics`: what add_vm takes, rg and subnet
    filled in."""
    f = FakeAzure()
    nsg = f.add_nsg("rg-app", "nsg-web")
    subnet = f.add_subnet("rg-net", "vnet", "app", nsg)
    f.add_vm("rg-app", "web", [{"rg": "rg-app", "subnet": subnet, "nsg": None, **n} for n in nics])
    c = AzureConnector(dry_run=False, read_only=True)
    c._network, c._compute = f.network, f.compute
    c._subscription_id = "s"
    return f, c


def _audit(c) -> dict:
    res = c.check_nsg_access(WEB)
    assert res["ok"] is True, res
    return res


def test_a_nic_without_public_ip_says_an_empty_list():
    f, c = _world([{"name": "web-nic", "ips": ["10.0.0.4"]}])
    res = _audit(c)
    assert res["nsgs"][0]["public_ips"] == []
    assert f.public_ip_reads == []


def test_a_nic_with_a_public_ip_says_its_address():
    f = FakeAzure()
    pip = f.add_public_ip("rg-app", "web-pip", PUBLIC)
    nsg = f.add_nsg("rg-app", "nsg-web")
    subnet = f.add_subnet("rg-net", "vnet", "app", nsg)
    f.add_vm("rg-app", "web", [{"rg": "rg-app", "name": "web-nic", "ips": ["10.0.0.4"], "subnet": subnet,
                                "nsg": None, "public_ips": [pip]}])
    c = AzureConnector(dry_run=False, read_only=True)
    c._network, c._compute = f.network, f.compute
    res = _audit(c)
    entry = res["nsgs"][0]
    assert entry["public_ips"] == [{"address": PUBLIC}]
    # Nothing else changes in the shape rendered.
    assert set(entry) == {"nsg", "nsg_scope", "nic_id", "ips", "public_ips"}
    assert entry["ips"] == ["10.0.0.4"]


def _with_pips(pips: dict, nics: list[dict]):
    """A world whose public IPs are created first: pips = {name: (rg, address)}."""
    f = FakeAzure()
    ids = {name: f.add_public_ip(rg, name, address) for name, (rg, address) in pips.items()}
    nsg = f.add_nsg("rg-app", "nsg-web")
    subnet = f.add_subnet("rg-net", "vnet", "app", nsg)
    f.add_vm("rg-app", "web", [{"rg": "rg-app", "subnet": subnet, "nsg": None,
                                **{**n, "public_ips": [ids.get(p) if p else None for p in n.get("public_ips", [])]}}
                               for n in nics])
    c = AzureConnector(dry_run=False, read_only=True)
    c._network, c._compute = f.network, f.compute
    return f, c, ids


def test_two_ip_configurations_only_the_second_public():
    f, c, _ = _with_pips({"web-pip": ("rg-app", PUBLIC)},
                         [{"name": "web-nic", "ips": ["10.0.0.4", "10.0.0.5"], "public_ips": [None, "web-pip"]}])
    res = _audit(c)
    assert res["nsgs"][0]["ips"] == ["10.0.0.4", "10.0.0.5"]
    assert res["nsgs"][0]["public_ips"] == [{"address": PUBLIC}]


def test_a_public_ip_refused_403_is_said_and_the_nsg_check_stays_ok():
    f, c, ids = _with_pips({"web-pip": ("rg-app", PUBLIC)},
                           [{"name": "web-nic", "ips": ["10.0.0.4"], "public_ips": ["web-pip"]}])
    f.unreadable.add(key(ids["web-pip"]))
    res = _audit(c)
    [pip] = res["nsgs"][0]["public_ips"]
    assert pip["address"] is None
    assert pip["error"].startswith("lecture refusée (droits)"), pip
    assert res["nsg"] == "rg-app/nsg-web" and isinstance(res["rules"], int)
    # The audit check built from it stays ok, the reason carried to the page.
    check = _check_nsg(WEB, c)
    check = check[0] if isinstance(check, list) else check
    assert check.status == "ok"
    assert check.data["nsgs"][0]["public_ips"] == [pip]


def test_a_public_ip_in_another_resource_group_is_read_there():
    f, c, _ = _with_pips({"web-pip": ("rg-edge", OTHER)},
                         [{"name": "web-nic", "ips": ["10.0.0.4"], "public_ips": ["web-pip"]}])
    res = _audit(c)
    assert res["nsgs"][0]["public_ips"] == [{"address": OTHER}]
    assert f.public_ip_reads == [("rg-edge", "web-pip")]


def test_a_public_ip_without_an_address_says_so():
    f, c, _ = _with_pips({"web-pip": ("rg-app", None)},
                         [{"name": "web-nic", "ips": ["10.0.0.4"], "public_ips": ["web-pip"]}])
    res = _audit(c)
    assert res["nsgs"][0]["public_ips"] == [{"address": None, "error": NOT_ALLOCATED, "code": "not_allocated"}]


def test_a_public_ip_gone_is_said_not_found():
    f, c, _ = _with_pips({}, [{"name": "web-nic", "ips": ["10.0.0.4"]}])
    f.nics[key(f.vms[key(WEB)]["nics"][0])]["public_ips"] = [public_ip_id("rg-app", "gone-pip")]
    res = _audit(c)
    assert res["nsgs"][0]["public_ips"] == [{"address": None, "error": NOT_FOUND, "code": "not_found"}]


def test_a_throttled_read_is_said_and_the_audit_holds():
    def chaos(op, phase, write):
        if op == "public_ip.get":
            raise throttled(op)
    f, c, _ = _with_pips({"web-pip": ("rg-app", PUBLIC)},
                         [{"name": "web-nic", "ips": ["10.0.0.4"], "public_ips": ["web-pip"]}])
    f.chaos = chaos
    res = _audit(c)
    [pip] = res["nsgs"][0]["public_ips"]
    assert pip["address"] is None and pip["error"].startswith("illisible : ") and "TooManyRequests" in pip["error"]


def test_a_public_ip_is_read_once_per_call_however_many_nics_name_it():
    f, c, ids = _with_pips({"web-pip": ("rg-app", PUBLIC)},
                           [{"name": "web-nic", "ips": ["10.0.0.4"], "public_ips": ["web-pip"]},
                            {"name": "web-nic2", "ips": ["10.0.1.4"], "public_ips": ["web-pip"]}])
    res = _audit(c)
    assert [n["public_ips"] for n in res["nsgs"]] == [[{"address": PUBLIC}], [{"address": PUBLIC}]]
    assert f.public_ip_reads == [("rg-app", "web-pip")]
    _audit(c)                                    # a new call reads again
    assert len(f.public_ip_reads) == 2


def test_two_nics_each_their_own_public_ip():
    f, c, _ = _with_pips({"a-pip": ("rg-app", PUBLIC), "b-pip": ("rg-edge", OTHER)},
                         [{"name": "web-nic", "ips": ["10.0.0.4"], "public_ips": ["a-pip"]},
                          {"name": "web-nic2", "ips": ["10.0.1.4"], "public_ips": ["b-pip"]}])
    res = _audit(c)
    assert [n["public_ips"] for n in res["nsgs"]] == [[{"address": PUBLIC}], [{"address": OTHER}]]


def test_the_reason_carries_no_id():
    """Azure's words without an id: an ARM id becomes its kind, a GUID `<id>`."""
    sub = "00000000-0000-0000-0000-000000000000"
    rid = f"/subscriptions/{sub}/resourceGroups/rg-app/providers/Microsoft.Network/publicIPAddresses/web-pip"
    net = MagicMock()
    net.public_ip_addresses.get.side_effect = Exception(
        f"(AuthorizationFailed) The client '{sub}' does not have authorization over scope '{rid}'\nmore")
    [pip] = read_public_ips(net, [rid], {})
    assert pip["address"] is None and pip["error"].startswith("lecture refusée (droits)")
    assert sub not in pip["error"] and "/subscriptions/" not in pip["error"]
    assert "Microsoft.Network/publicIPAddresses" in pip["error"] and "more" not in pip["error"]
    net.public_ip_addresses.get.assert_called_once_with("rg-app", "web-pip")


def test_a_malformed_id_is_said_never_raised():
    [pip] = read_public_ips(MagicMock(), ["not-an-arm-id"], {})
    assert pip["address"] is None and pip["error"]


def test_dry_run_is_unchanged():
    assert AzureConnector(dry_run=True).check_nsg_access(WEB) == {"ok": True, "nsg": "dry_run"}


def test_a_target_without_public_ip_ids_still_says_an_empty_list(monkeypatch):
    """A target built before IPS1a (a test's simulacre): `public_ips` is there, empty."""
    c = AzureConnector(dry_run=False)
    monkeypatch.setattr(c, "_ensure_clients", lambda: None)
    monkeypatch.setattr(c, "_get_vm_nic_targets", lambda rg, vm, **_k: [
        {"nic_id": "nic-a", "nic_short": "nic-a", "nsg_rg": "rg", "nsg_name": "nsg", "scope": "nic",
         "private_ips": ["10.0.0.5"]}])
    c._network = MagicMock()
    c._network.security_rules.list.return_value = []
    res = c.check_nsg_access(WEB)
    assert res["ok"] is True and res["nsgs"][0]["public_ips"] == []
    c._network.public_ip_addresses.get.assert_not_called()
