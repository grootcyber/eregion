"""SDK1b (#1017): scripts/sdk_capture.py — the maintainer's capture of the bodies ARM sends for the
ten operations, read-only and anonymized. Its guards read in its code (a closed list of reads, no
write anywhere, az login's identity), then run: the script's own clients over the in-memory ARM of
tests/unit/sdk_mgmt.py, serving a bench made up to look real — names, GUIDs (one uppercase),
addresses private and public, a MAC, an e-mail, a user, a host, one of Glorfindel's rules naming its
NIC by its mark and a block naming its attacker by its address. Nothing of it may come out.

No Azure, no network (`sdk_mgmt.offline`); every « real » value here is made up.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import uuid
from pathlib import Path

import pytest

from . import sdk_mgmt as m
from .test_sdk_mgmt_contracts import TEN

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "sdk_capture.py"
ANON = ROOT / "scripts" / "sdk_anonymize.py"

# The made-up bench: each stand-in of the bodies given a value that looks real.
REAL = {"rg-example-01": "rg-acme-paris", "vm-example-01": "web-front-7", "vm-example-02": "db-back-3",
        "nic-example-01": "web-front-7-nic", "nic-example-02": "db-back-3-nic", "nsg-example-01": "web-front-7-nsg",
        "nsg-example-02": "app-tier-nsg", "vnet-example-01": "acme-hub-vnet", "snet-example-01": "app-tier",
        "pip-example-01": "web-front-7-ip", "disk-example-01": "web-front-7_OsDisk_1_a1b2c3",
        "rsv-example-01": "rsv-acme-central", "rule-example-01": "allow-ssh-from-hq",
        "example.ax.internal": "q2w3e4r5.ax.internal", "azureuser": "dvalmont"}
ATTACKER = "45.67.89.10"
EMAIL = "ops.lead@acme-corp.test"


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    m.offline(monkeypatch)


@pytest.fixture(scope="module")
def sc():
    spec = importlib.util.spec_from_file_location("sdk_capture", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _real_guid(fake: str) -> str:
    n = int(fake.rsplit("-", 1)[1], 16)
    return str(uuid.UUID(int=(n * 0x9E3779B97F4A7C15 + 0x4F3C2A1E5D6B7C8D9E0F1A2B3C4D5E6F) % (1 << 128)))


def _realize(text: str) -> str:
    text = re.sub(r"00000000-0000-4000-8000-[0-9a-f]{12}", lambda g: _real_guid(g.group(0)), text)
    text = text.replace("10.240.1.", "10.42.7.").replace("00-00-5E-00-53-0", "7C-1E-52-AA-01-0")
    for stand_in in sorted(REAL, key=len, reverse=True):
        text = text.replace(stand_in, REAL[stand_in])
    return text


def _world() -> tuple[list[dict], dict]:
    """The bodies of tests/unit/sdk_bodies/ made to look real, and more: a tag with an e-mail, an
    NSG of another group, an uppercase GUID, an isolation rule ending with its NIC's mark, a block
    naming its attacker's address."""
    caps = [json.loads(_realize(json.dumps(c))) for c in m.captures()]
    by_op = {c["operation"]: c for c in caps}
    nic_id = m.body(by_op["network.network_interfaces.get"])["id"]
    mark = hashlib.sha256(nic_id.lower().encode()).hexdigest()[:32]
    iso = f"glorfindel-iso-{REAL['vm-example-01']}-{REAL['nic-example-01']}-{mark}"
    block = f"glorfindel-block-{ATTACKER.replace('.', '-')}"
    nsgs = by_op["network.network_security_groups.list_all"]
    own = m.named(nsgs, REAL["nsg-example-01"])
    own["tags"] = {"owner": EMAIL, "costcenter": "Paris HQ", "managed-by": "terraform"}
    own["properties"]["securityRules"][0]["properties"]["description"] = "Allow from the laptop of D. Valmont"
    for name, prio, prefix in ((iso, 101, "*"), (block, 200, f"{ATTACKER}/32")):
        own["properties"]["securityRules"].append({"name": name, "id": f"{own['id']}/securityRules/{name}", "properties": {
            "access": "Deny", "direction": "Inbound", "priority": prio, "protocol": "*", "sourceAddressPrefix": prefix,
            "destinationAddressPrefix": "*", "sourcePortRange": "*", "destinationPortRange": "*",
            "description": "Glorfindel — isolation"}})
    other = json.loads(json.dumps(m.named(nsgs, REAL["nsg-example-02"]))
                       .replace(REAL["rg-example-01"], "rg-other-team").replace(REAL["nsg-example-02"], "secret-nsg"))
    m.items(nsgs).append(other)
    jobs = m.items(by_op["backup.backup_jobs.list"])
    jobs[0]["properties"]["activityId"] = jobs[0]["properties"]["activityId"].upper()
    world = {"sub": m.body(by_op["compute.virtual_machines.get"])["id"].split("/")[2], "iso": iso, "block": block,
             "nic_id": nic_id}
    return caps, world


def _capture(sc, monkeypatch):
    caps, world = _world()
    arm = m.Arm(*caps)
    clients = sc.clients(m._Credential(), world["sub"], session=arm.session())
    vm, vault = (REAL["rg-example-01"], REAL["vm-example-01"]), (REAL["rg-example-01"], REAL["rsv-example-01"])
    got = sc.capture(clients, [vm], vault, say=lambda _line: None)
    files = sc.files(got, "2026-11-21", {"network": "33.1.0", "compute": "39.0.0", "backup": "11.2.0"})
    seeds = {vm[0]: "rg", vm[1]: "vm", vault[1]: "rsv"}
    return arm, got, files, seeds, world


def _anonymized(sc, monkeypatch):
    arm, got, files, seeds, world = _capture(sc, monkeypatch)
    out, a = sc.anonymize(files, seeds, world["sub"])
    return out, a, files, world


def _reals(world: dict) -> list[str]:
    caps, _ = _world()
    text = json.dumps(caps)
    guids = {g.lower() for g in re.findall(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                                           r"[0-9a-fA-F]{12}", text)}
    return sorted(set(REAL.values()) | guids | {"10.42.7.4", "10.42.7.5", "10-42-7-4", ATTACKER,
                                                ATTACKER.replace(".", "-"), "7C-1E-52-AA-01-01", EMAIL,
                                                "Paris HQ", "rg-other-team", "secret-nsg", "q2w3e4r5", "Valmont",
                                                world["iso"].rsplit("-", 1)[1]})


# ── the guards, read in the code ────────────────────────────────────────────────────────────────

def _trees():
    """The script and its anonymization module: what the capture runs."""
    return [ast.parse(SCRIPT.read_text()), ast.parse(ANON.read_text())]


# An operation that changes something, as the SDKs name theirs.
WRITE_WORDS = re.compile(r"^(begin_\w+|create\w*|update\w*|delete\w*|set_\w+|put|post|patch|run_command|start|"
                         r"restart|deallocate|power_off|trigger\w*|cancel\w*|register\w*|reimage|redeploy)$")


def test_the_script_reads_only_from_a_closed_list(sc):
    """The closed list is the ten, and the protected item's names the adapters ask for: `get` and
    `list` only. Nowhere in the script an attribute, a name or a text of a write — no `begin_*`, no
    `create`, no `update`, no `delete` —; `getattr` only in `_read`, which checks the list first;
    no HTTP client of its own (the SDKs' read-only transport only). Its anonymization module the
    same, and it imports no SDK at all."""
    assert set(sc.READS) == set(TEN) | {"backup.protected_items.get"}
    assert all(op.rsplit(".", 1)[1] in sc.READ_VERBS for op in sc.READS)
    assert sc.READ_VERBS == {"get", "list", "list_all"}
    script, anon = _trees()
    assert not [n for n in ast.walk(anon) if isinstance(n, (ast.Import, ast.ImportFrom))
                and any((a.name if isinstance(n, ast.Import) else n.module or "").startswith("azure") for a in n.names)]
    for node in (n for tree in (script, anon) for n in ast.walk(tree)):
        if isinstance(node, ast.Attribute):
            assert not WRITE_WORDS.match(node.attr), node.attr
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not re.search(r"\.(begin_|create|update|delete)\w*", node.value), node.value
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + [getattr(node, "module", "") or ""]
            assert not any(n.split(".")[0] in ("requests", "http", "socket", "urllib3") or n == "urllib.request"
                           for n in names), names
    getattrs = [f.name for tree in (script, anon) for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)
                for n in ast.walk(f) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "getattr"]
    assert set(getattrs) == {"_read"}


def test_the_identity_is_az_login_s(sc):
    """The capture runs as the maintainer's `az login`, never as a credential the environment holds
    (the watch's service principal, a secret in .envrc)."""
    text = SCRIPT.read_text()
    assert "AzureCliCredential()" in text
    for other in ("DefaultAzureCredential", "EnvironmentCredential", "ClientSecretCredential",
                  "ManagedIdentityCredential"):
        assert other not in text


def test_a_read_outside_the_list_is_refused_before_any_call(sc):
    arm = m.Arm(*m.captures())
    clients = sc.clients(m._Credential(), m.SUB, session=arm.session())
    for op in ("network.security_rules.begin_delete", "network.public_ip_addresses.get",
               "network.network_security_groups.begin_create_or_update"):
        with pytest.raises(sc.Refused):
            sc._read(clients, op, m.RG, "nsg-example-01", "any")
    assert arm.requests == []


def test_the_transport_refuses_any_method_but_get_before_it_leaves(sc):
    """Even called past the closed list, a write never leaves: each client's transport refuses a
    DELETE, a PUT, a PATCH — nothing reaches the socket."""
    from azure.mgmt.network.models import SecurityRule
    arm = m.Arm(*m.captures())
    net = sc.clients(m._Credential(), m.SUB, session=arm.session())["network"]
    writes = (lambda: net.security_rules.begin_delete(m.RG, "nsg-example-01", "r").result(),
              lambda: net.security_rules.begin_create_or_update(m.RG, "nsg-example-01", "r", SecurityRule(
                  priority=100, access="Deny", direction="Inbound", protocol="*")).result(),
              lambda: net.network_security_groups.update_tags(m.RG, "nsg-example-01", {"tags": {}}))
    for write in writes:
        with pytest.raises(sc.Refused):
            write()
    assert arm.requests == []


# ── the capture ─────────────────────────────────────────────────────────────────────────────────

def test_a_capture_reads_the_ten_and_writes_nothing(sc, monkeypatch):
    """The capture of the made-up bench: a body for each of the ten, GETs only; the subscription's
    listings kept for the bench's group (another group's NSG left out); the raw bodies, as sent."""
    arm, got, files, _seeds, _world_ = _capture(sc, monkeypatch)
    assert set(TEN) <= set(got)
    assert {r["method"] for r in arm.requests} == {"GET"} and arm.writes == []
    listed = [n["name"] for r in got["network.network_security_groups.list_all"] for n in r["body"]["value"]]
    assert "secret-nsg" not in listed and REAL["nsg-example-02"] in listed
    for op in TEN:
        cap = files[f"{op}.json"]
        assert cap["source"] == "measured" and cap["api_version"] == m.load(op)["api_version"]
        assert not cap["responses"][0]["url"].startswith("http")


def test_nothing_real_leaves_the_anonymization(sc, monkeypatch):
    """Every made-up real value of the bench — names, GUIDs (the uppercase one too), addresses
    private and public (and the dashed one in a block's name), the MAC, the e-mail, the user, the
    host, a free text, another group's names, the NIC's mark — is out of the files; every GUID,
    address, MAC, e-mail and ARM name in them is a stand-in's."""
    out, _a, _files, world = _anonymized(sc, monkeypatch)
    text = json.dumps(out).lower()
    for real in _reals(world):
        assert not re.search(r"(?<![a-z0-9])" + re.escape(real.lower()) + r"(?![a-z0-9])", text), real
    assert sc.structural(out) == []


def test_the_same_real_gives_the_same_stand_in_and_the_ids_keep_their_shape(sc, monkeypatch):
    """One VM, one stand-in in every file; an ARM id keeps its shape; the subscription is the same
    stand-in everywhere, the first one — the hypotheses' (tests/unit/sdk_mgmt.py, SUB)."""
    out, _a, _files, _world_ = _anonymized(sc, monkeypatch)
    vm = m.body(out["compute.virtual_machines.get.json"])
    nic = m.body(out["network.network_interfaces.get.json"])
    assert nic["properties"]["virtualMachine"]["id"] == vm["id"]
    assert re.fullmatch(r"/subscriptions/00000000-0000-4000-8000-[0-9a-f]{12}/resourceGroups/rg-example-01/"
                        r"providers/Microsoft\.Compute/virtualMachines/vm-example-01", vm["id"])
    subs = {i.split("/")[2] for i in re.findall(r"/subscriptions/[^/\"]+", json.dumps(out), re.IGNORECASE)}
    assert subs == {m.SUB}


def test_a_rule_of_glorfindel_still_names_its_nic_and_its_attacker(sc, monkeypatch):
    """Glorfindel's isolation rule, named by its VM, its NIC and the NIC's mark: anonymized, it is
    the name the adapters give the stand-in NIC — the rule still names its NIC. A block's name
    carries its attacker's address dashed: the stand-in address's."""
    from glorfindel.actions import AzureConnector
    out, a, _files, _world_ = _anonymized(sc, monkeypatch)
    nsg = m.named(out["network.network_security_groups.list_all.json"], "nsg-example-01")
    names = [r["name"] for r in nsg["properties"]["securityRules"]]
    nic = m.body(out["network.network_interfaces.get.json"])
    expected = AzureConnector(dry_run=True)._placement_rule_base("glorfindel-iso", "vm-example-01", "nic-example-01",
                                                                 nic["id"])
    assert expected in names
    import ipaddress
    fake = a.ip(ATTACKER)
    assert any(ipaddress.ip_address(fake) in net for net in sc.an.DOC_NETS)
    assert f"glorfindel-block-{fake.replace('.', '-')}" in names


def test_the_anonymized_bodies_read_as_the_real_ones(sc, monkeypatch):
    """The adapters read the anonymized bodies as they read the real ones: the same audit (the allow
    before the deny), the quarantine on standby `ok`."""
    def read(captures, sub):
        c = m.Arm(*captures).connector(monkeypatch, subscription=sub)
        vm = m.body(next(x for x in captures if x["operation"] == "compute.virtual_machines.get"))["id"]
        audit = c.check_nsg_access(vm)
        return (audit["ok"], audit["scope"], len(audit["precedence"]),
                [q["status"] for q in c.find_altered_quarantines(c.nsg_listing())])
    out, _a, files, world = _anonymized(sc, monkeypatch)
    real = read(list(files.values()), world["sub"])
    assert real == (True, "nic", 2, ["ok"])
    assert read(list(out.values()), m.SUB) == real


def test_a_leak_writes_nothing(sc, monkeypatch, tmp_path):
    """A real value the anonymization would leave: `anonymize` raises, saying its kind and its
    file, never its value — and `capture` writes no file."""
    _arm, _got, files, seeds, world = _capture(sc, monkeypatch)
    monkeypatch.setattr(sc.Anonymizer, "mac", lambda self, real: real)
    with pytest.raises(sc.Leak) as exc:
        sc.anonymize(files, seeds)
    assert "MAC" in str(exc.value) and "7C-1E-52" not in str(exc.value)
    got = _capture(sc, monkeypatch)[1]
    monkeypatch.setattr(sc, "capture", lambda *a, **k: got)
    monkeypatch.setattr(sc, "clients", lambda *a, **k: {})
    monkeypatch.setitem(__import__("sys").modules, "azure.identity", type("M", (), {"AzureCliCredential": object}))
    with pytest.raises(sc.Leak):
        sc.main(["capture", "--vm", "rg-acme-paris/web-front-7", "--out", str(tmp_path / "out"),
                 "--subscription", world["sub"]])
    assert not (tmp_path / "out").exists()


def test_check_says_a_folder_clean_or_not(sc, monkeypatch, tmp_path, capsys):
    """`check` on a folder: clean for stand-ins only (the hypotheses too); not clean for a GUID, an
    address or a word the maintainer forbids — its kind said, never the value. The subscription of
    the environment is forbidden by itself."""
    out, _a, _files, _world_ = _anonymized(sc, monkeypatch)
    sc.write(tmp_path, out)
    monkeypatch.delenv("AZURE_SUBSCRIPTION_ID", raising=False)
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    assert sc.main(["check", str(tmp_path)]) == 0
    assert sc.main(["check", str(m.BODIES)]) == 0
    assert sc.main(["check", str(tmp_path), "--forbid", "nic-example-01"]) == 1
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "vm-example-01")
    assert sc.main(["check", str(tmp_path)]) == 1
    monkeypatch.delenv("AZURE_SUBSCRIPTION_ID")
    path = tmp_path / "network.network_interfaces.get.json"
    path.write_text(path.read_text().replace("10.240.1.4", "10.42.7.4", 1))
    capsys.readouterr()
    assert sc.main(["check", str(tmp_path)]) == 1
    said = capsys.readouterr().out
    assert "IPv4" in said and "10.42.7.4" not in said


def test_the_out_folder_is_under_no_git_checkout(sc, tmp_path):
    """The files are read before they are copied: never written into this repository, nor into the
    checkout its worktree belongs to (run from a worktree, `~/eregion/tests/…` was accepted), nor
    into any folder under a `.git` — a directory or a worktree's file."""
    import subprocess
    proc = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                          capture_output=True, text=True)
    # The checkout this one belongs to — none in a mutant's copy (no git there): the folders made below
    # still prove the rule.
    checkout = [Path(proc.stdout.strip()).parent / "tests" / "unit"] if proc.returncode == 0 else []
    for inside in (ROOT, ROOT / "tests/unit/sdk_bodies", ROOT / "scripts", *checkout):
        with pytest.raises(SystemExit):
            sc._outside_repo(inside)
    main, worktree = tmp_path / "main", tmp_path / "wt"
    (main / ".git").mkdir(parents=True)
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: /elsewhere/.git/worktrees/wt\n")
    for inside in (main / "tests" / "unit" / "sdk_bodies", worktree / "out", main):
        with pytest.raises(SystemExit, match="git checkout"):
            sc._outside_repo(inside)
    assert sc._outside_repo(tmp_path / "capture") == (tmp_path / "capture").resolve()


def test_the_script_says_how_to_run_it(sc):
    """Its way of use, at its head: `az login`, the subscription, `capture`, `check`, where it
    writes, where the files go after the review."""
    doc = sc.__doc__
    for said in ("az login", ".venv/bin/python scripts/sdk_capture.py capture",
                 '--subscription "$(az account show --query id -o tsv)"', "--vm", "--vault", "--out", "check",
                 "tests/unit/sdk_bodies/", "a session never runs it", "read each file", "last net"):
        assert said in doc, said
    assert "last net" in sc.an.__doc__


# ── the review of SDK1b: what the anonymization had let through ──────────────────────────────────

TRAP_REALS = ("2a01:4f8:c17:1::1", "2a02:1234::", "fe80::1ff:fe23:4567:890a", "acmecorp.fr", "web01",
              "acmecorp-cost-center", "Sup3rS3cret!", "c2hhcmVkLWtleS1mb3ItdGhlLXRlc3RzLW9ubHktbWFkZS11cA==",
              "sv2026sig", "0123456789abcdef0123456789abcdef", "jean", "srv-paris-01")
JWT = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJtYWRlLXVwIn0.c2ln"


def _trap() -> dict:
    """A body made to trap the anonymization: IPv6 addresses, a domain outside Azure's under its
    host keys, a tag key, secrets under their keys and in a URL, 32 hex, an error's free text."""
    base = m.load("network.network_interfaces.get")
    nic = m.body(base)
    nic["properties"]["dnsSettings"] |= {"internalFqdn": "web01.acmecorp.fr"}
    nic["properties"]["ipConfigurations"][0]["properties"]["publicIPAddressV6"] = "2a01:4f8:c17:1::1"
    nic["tags"] = {"acmecorp-cost-center": "42", "managed-by": "glorfindel"}
    nic["properties"] |= {
        "fqdn": "web01.acmecorp.fr", "reverseFqdn": "web01.acmecorp.fr.", "linkLocal": "fe80::1ff:fe23:4567:890a",
        "sourceAddressPrefix": "2a02:1234::/32", "password": "Sup3rS3cret!",
        "sharedKey": "c2hhcmVkLWtleS1mb3ItdGhlLXRlc3RzLW9ubHktbWFkZS11cA==", "accessToken": JWT,
        "blob": "https://stexample01.blob.core.windows.net/c/x?sv=2026&sig=sv2026sig",
        "checksum": "0123456789abcdef0123456789abcdef",
        "errorDetails": [{"errorString": "jean could not reach srv-paris-01", "errorCode": 400}]}
    return base


def test_a_body_made_to_trap_the_anonymization_comes_out_clean(sc):
    """IPv6 (an address, a prefix, a link-local in a field), a domain outside Azure's in `fqdn`,
    `reverseFqdn`, `internalFqdn`, a tag's key, a password, a shared key, a JWT, a SAS signature, 32 hex,
    an error's words: none comes out; every form left is a stand-in's."""
    out, a = sc.anonymize({"trap.json": _trap()})
    text = json.dumps(out)
    for real in TRAP_REALS + (JWT,):
        assert real.lower() not in text.lower(), real
    nic = m.body(out["trap.json"])
    assert nic["properties"]["fqdn"].endswith(".example.org")
    assert nic["properties"]["ipConfigurations"][0]["properties"]["publicIPAddressV6"].startswith("2001:db8::")
    assert nic["properties"]["sourceAddressPrefix"].startswith("2001:db8::") and nic["properties"][
        "sourceAddressPrefix"].endswith("/32")
    assert set(nic["tags"]) == {"tag-example-01", "managed-by"} and nic["tags"]["managed-by"] == "glorfindel"
    assert sc.structural(out) == []


@pytest.mark.parametrize("planted, said", [
    ("2a01:4f8:c17:1::1", "IPv6"),
    ("web01.acmecorp.fr", "domain"),
    (JWT, "JWT"),
    ("https://stexample01.blob.core.windows.net/c?sv=2026&sig=abcdef0123", "SAS"),
    ("ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC", "SSH"),
    ("0123456789abcdef0123456789abcdef", "32 hex"),
    ("c2hhcmVkLWtleS1mb3ItdGhlLXRlc3RzLW9ubHktbWFkZS11cA==", "base64"),
], ids=["ipv6", "domain", "jwt", "sas", "ssh", "hex", "base64"])
def test_check_refuses_each_form_the_anonymization_must_not_leave(sc, planted, said):
    """`check`'s half of the check: each of these forms, planted in a clean body, is refused — its
    kind said, never its value."""
    clean = {"x.json": m.load("network.network_interfaces.get")}
    assert sc.structural(clean) == []
    m.body(clean["x.json"])["properties"]["planted"] = planted
    found = sc.structural(clean)
    assert found and any(said.lower() in f.lower() for f in found), found
    assert planted not in " ".join(found)


def test_a_secret_left_under_its_key_is_refused(sc):
    """A key that says key, token, secret, password or SAS holding anything but a stand-in: refused."""
    for key in ("password", "primaryKey", "accessToken", "clientSecret", "sasUrl"):
        body = {"x.json": {"properties": {key: "plain-value"}}}
        assert any("secret" in f for f in sc.structural(body)), key
    assert sc.structural({"x.json": {"properties": {"password": "stand-in"}}}) == []


def test_a_response_retried_by_the_sdk_is_kept_once(sc):
    """A 429, then a 200: the SDK retries, the hook sees both — the read keeps the 200 alone, and
    the capture goes on (it raised outside its guard)."""
    vm_id = m.body(m.load("compute.virtual_machines.get"))["id"]
    arm = m.Arm(*m.captures()).once(vm_id, {"error": {"code": "TooManyRequests", "message": "later"}}, 429)
    clients = sc.clients(m._Credential(), m.SUB, session=arm.session())
    [one] = sc._read(clients, "compute.virtual_machines.get", vm_id.split("/")[4], vm_id.rsplit("/", 1)[1])
    assert one["status"] == 200 and len(arm.sent("virtualMachines/")) == 2
    arm.once(vm_id, {"error": {"code": "TooManyRequests", "message": "later"}}, 429)
    got = sc.capture(clients, [(vm_id.split("/")[4], vm_id.rsplit("/", 1)[1])], say=lambda _line: None)
    assert len(got["compute.virtual_machines.get"]) == 1


def test_a_name_that_is_a_word_of_the_structure_is_refused_never_spread(sc):
    """A resource group named `network`, a domain whose first label is `api`: replaced as names
    everywhere, they would break every id (`Microsoft.Network`) and every URL (`api-version`). The
    domain is replaced whole; the group stays real — and the check refuses the files."""
    trap = m.load("network.network_interfaces.get")
    m.body(trap)["properties"]["dnsSettings"]["internalFqdn"] = "api.acmecorp.fr"
    out, _a = sc.anonymize({"x.json": trap})
    text = json.dumps(out)
    assert "Microsoft.Network/networkInterfaces" in text and "api-version=" in text and "acmecorp" not in text
    grouped = json.loads(json.dumps(m.load("network.network_interfaces.get")).replace(m.RG, "network"))
    with pytest.raises(sc.Leak, match="ARM id naming something real"):
        sc.anonymize({"x.json": grouped})


@pytest.mark.parametrize("domain", ["compute.acmecorp.fr", "network.acmecorp.fr", "microsoft.acmecorp.fr",
                                    "acmecorp.md", "acmecorp.py"])
def test_a_domain_shaped_like_an_operation_a_namespace_or_a_file_is_a_domain(sc, domain):
    """Excluded by their form in the review's second round: an operation's name (`compute.…`), a
    namespace (`microsoft.…`), a file's ending that is a top-level domain (`.md`, `.py`). Each is a
    domain: replaced, and `check` refuses it when it is left."""
    trap = m.load("network.network_interfaces.get")
    m.body(trap)["properties"]["dnsSettings"]["internalFqdn"] = domain
    out, _a = sc.anonymize({"x.json": trap})
    assert domain not in json.dumps(out)
    clean = {"x.json": m.load("network.network_interfaces.get")}
    m.body(clean["x.json"])["properties"]["planted"] = domain
    assert any("domain" in f for f in sc.structural(clean))


def test_a_namespace_of_arm_and_the_file_s_operation_are_kept(sc):
    """What the domains' form must not take: a namespace of ARM, before a `/` or ending its value
    (`Microsoft.Network/…`, an extension's publisher `Microsoft.Azure.Monitor`), and the operation's
    name a capture file carries under its key `operation` — kept, and `check` says them clean."""
    cap = m.load("network.subnets.get")
    m.body(cap)["properties"]["publisher"] = "Microsoft.Azure.Monitor"
    out, _a = sc.anonymize({"x.json": cap})
    assert out["x.json"]["operation"] == "network.subnets.get"
    assert m.body(out["x.json"])["properties"]["publisher"] == "Microsoft.Azure.Monitor"
    assert "Microsoft.Network/virtualNetworks" in json.dumps(out)
    assert sc.structural(out) == []
    m.body(cap)["properties"]["planted"] = "network.subnets.get"      # not under `operation`: a domain
    assert any("domain" in f for f in sc.structural({"x.json": cap}))
