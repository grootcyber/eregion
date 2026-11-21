#!/usr/bin/env python3
"""SDK1b (#1017): the bodies Azure sends for the ten `azure.mgmt` operations Glorfindel's adapters read
most, captured at the bench, read-only, anonymized before anything is written. The maintainer's
gesture, with his own identity: a session never runs it.

    az login                                                  # your identity (Reader is enough)
    az account set --subscription <the bench's subscription>
    export AZURE_SUBSCRIPTION_ID=$(az account show --query id -o tsv)
    python scripts/sdk_capture.py capture --vm <group>/<vm> --vault <group>/<vault> \\
        --out ~/eregion-banc/sdk1b
    python scripts/sdk_capture.py check ~/eregion-banc/sdk1b --forbid <group> --forbid <vm> --forbid <vault>

then read each file (a few KB), and copy them into tests/unit/sdk_bodies/ in the branch that replaces
the hypotheses (SDK1b's second time): `cp ~/eregion-banc/sdk1b/*.json tests/unit/sdk_bodies/`.

**What it reads**, and nothing else — the closed list `READS`, `get` and `list` only:

- every NSG and every network interface of the subscription (`list_all`, what the watch's pass reads
  each minute), kept only for the groups it is given (`--vm`'s, `--vault`'s, `--group`): the bench's;
- each `--vm` (`virtual_machines.get`), each of its network interfaces, their subnets, every NSG that
  governs them (their own and their subnet's) and its rules (`security_rules.list`);
- with `--vault`: the vault's jobs (`backup_jobs.list`) of the named VMs, the newest ten; the details of
  the newest job of each kind (`job_details.get`); each VM's protected item (its stored names, as the
  adapters ask for them) and its recovery points.

**Its guards.** A read outside `READS` is refused before any call; every client's transport refuses
any method but GET before it leaves (`ReadOnlyTransport`: a `begin_*`, a `create`, an `update`, a
`delete`, and ARM's own resource provider registration, all refused); the identity is `az login`'s
(`AzureCliCredential`), never a credential of the environment. tests/unit/test_sdk_capture.py reads
this file and fails on any write it would call.

**What it writes**: one file per operation, `<sdk>.<group>.<operation>.json` — the operation, the SDK's
version, the API version the request carried, and each response as the API sent it (its raw body,
`raw_response_hook`, never the SDK's object written back), anonymized. Into `--out` only, a folder
outside this repository (the review comes before the copy). It prints counts, never a value.

**The anonymization** (`Anonymizer`), the same real always the same stand-in, across files:
- GUIDs (subscription, tenant, object ids, job names, etags) → `00000000-0000-4000-8000-<n>`;
- names — resource groups, VMs, network interfaces, NSGs, networks, subnets, disks, vaults, storage
  accounts, every name an ARM id carries, the VM and group a backup container names, the user of the
  VM, its host names — → `<kind>-example-<n>` (a storage account `stexample<n>`), the structure of an
  ARM id kept (`/subscriptions/…/resourceGroups/rg-example-01/providers/…`), Azure's own names
  (`Azure`, `default`, the default rules) and Glorfindel's prefixes kept, what they embed replaced;
- the marks Glorfindel's rule names and quarantine tags end with (hashes of a NIC's id) → the same
  hashes of the stand-in id: the rule still names its NIC;
- private IPv4 → `10.240.<n>.<last octet>` (by /24, the prefix length kept), public → the documentation
  ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24), also in the dashed form of a block's name;
  Azure's platform addresses kept; MACs → 00-00-5E-00-53-<n>; e-mail addresses → example.org;
- free text that is not Azure's or Glorfindel's (a rule's description, a tag's value) → a stand-in;
  an SSH public key, user data → a stand-in.
Then a check, before anything is written: no real value it met may appear in the output, and every
GUID, address, e-mail, MAC and ARM name in it must be a stand-in's form. Either fails: nothing is
written, the kind and the place said, never the value. `check` runs the second half on a folder.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The closed list of reads: "<sdk>.<operation group>.<operation>". Nothing else is ever called.
READS = (
    "network.network_security_groups.list_all",
    "network.network_interfaces.list_all",
    "compute.virtual_machines.get",
    "network.network_interfaces.get",
    "network.subnets.get",
    "network.security_rules.list",
    "network.network_security_groups.get",
    "backup.backup_jobs.list",
    "backup.job_details.get",
    "backup.recovery_points.list",
    "backup.protected_items.get",       # the item's stored names, as the adapters ask for them
)
READ_VERBS = frozenset({"get", "list", "list_all"})
PACKAGES = {"network": "azure-mgmt-network", "compute": "azure-mgmt-compute",
            "backup": "azure-mgmt-recoveryservicesbackup"}
JOBS_KEPT = 10


class Refused(RuntimeError):
    """A read outside the closed list, or a request that is not a GET: never sent."""


class Leak(RuntimeError):
    """The anonymized output still holds a real value, or a value not of a stand-in's form."""


# ── the clients: reads only ─────────────────────────────────────────────────────────────────────

def _read_only_transport(session=None):
    """azure-core's RequestsTransport, refusing any method but GET before it leaves — the last
    gate of every request, ARM's own resource provider registration included."""
    from azure.core.pipeline.transport import RequestsTransport

    class ReadOnlyTransport(RequestsTransport):
        def send(self, request, **kwargs):
            if str(request.method).upper() != "GET":
                raise Refused(f"sdk_capture: {request.method} refused — this script reads only")
            return super().send(request, **kwargs)

    if session is None:
        return ReadOnlyTransport()
    return ReadOnlyTransport(session=session, session_owner=False)


def clients(credential, subscription: str, session=None) -> dict:
    """The three SDKs' clients, each on a read-only transport (`session`: the tests' socket)."""
    from azure.mgmt.compute import ComputeManagementClient
    from azure.mgmt.network import NetworkManagementClient
    from azure.mgmt.recoveryservicesbackup import RecoveryServicesBackupClient
    return {
        "network": NetworkManagementClient(credential, subscription, transport=_read_only_transport(session)),
        "compute": ComputeManagementClient(credential, subscription, transport=_read_only_transport(session)),
        "backup": RecoveryServicesBackupClient(credential, subscription, transport=_read_only_transport(session)),
    }


def _read(clients_: dict, op: str, *args, **kwargs) -> list[dict]:
    """One read of the closed list, its responses as the API sent them: [{"url", "status",
    "body"}], one per page. Anything else is refused before any call."""
    if op not in READS:
        raise Refused(f"sdk_capture: {op} is not in the closed list of reads")
    sdk, group, verb = op.split(".")
    if verb not in READ_VERBS:
        raise Refused(f"sdk_capture: {op} is not a read")
    call = getattr(getattr(clients_[sdk], group), verb)
    pages: list = []
    result = call(*args, raw_response_hook=pages.append, **kwargs)
    if verb != "get":
        for _ in result:                       # the pager reads every page
            pass
    return [{"url": p.http_request.url, "status": p.http_response.status_code,
             "body": json.loads(p.http_response.text() or "null")} for p in pages]


# ── the capture ─────────────────────────────────────────────────────────────────────────────────

def _segments(arm_id: str) -> dict:
    """An ARM id's resource group and its (type → name) pairs, types lowercase."""
    parts = [p for p in str(arm_id or "").split("/") if p]
    low = [p.lower() for p in parts]
    out: dict = {"rg": parts[low.index("resourcegroups") + 1] if "resourcegroups" in low else ""}
    if "providers" in low:
        rest = parts[low.index("providers") + 2:]
        out |= {rest[i].lower(): rest[i + 1] for i in range(0, len(rest) - 1, 2)}
    return out


def _in_groups(item: dict, groups: set[str]) -> bool:
    return _segments(item.get("id", "")).get("rg", "").lower() in groups


def _kept(responses: list[dict], groups: set[str]) -> list[dict]:
    """A subscription-wide listing, each page's items kept for the named groups only."""
    out = []
    for r in responses:
        b = r["body"] if isinstance(r["body"], dict) else {}
        out.append({**r, "body": {**b, "value": [i for i in b.get("value") or [] if _in_groups(i, groups)]}})
    return out


def _api_version(url: str) -> str:
    m = re.search(r"[?&]api-version=([^&]+)", url)
    return m.group(1) if m else ""


def capture(clients_: dict, vms: list[tuple[str, str]], vault: tuple[str, str] | None = None,
            groups: set[str] | None = None, say=print) -> dict[str, list[dict]]:
    """Every read, its responses by operation. A read that fails is said (its status), its
    operation left without a body; nothing else stops."""
    got: dict[str, list[dict]] = {}
    groups = {g.lower() for g in (groups or set())} | {rg.lower() for rg, _ in vms}
    if vault:
        groups.add(vault[0].lower())

    def read(op, *args, **kwargs) -> list[dict]:
        try:
            responses = _read(clients_, op, *args, **kwargs)
        except Refused:
            raise
        except Exception as exc:               # 403, 404, throttled: said, the rest goes on
            say(f"  {op}: not read ({type(exc).__name__}, {vars(exc).get('status_code', '?')})")
            return []
        got.setdefault(op, []).extend(responses)
        return responses

    for op in ("network.network_security_groups.list_all", "network.network_interfaces.list_all"):
        if read(op):
            got[op] = _kept(got[op], groups)
    seen_nsgs: set[str] = set()
    for rg, name in vms:
        [vm] = read("compute.virtual_machines.get", rg, name) or [None]
        if vm is None:
            continue
        for ref in ((vm["body"].get("properties") or {}).get("networkProfile") or {}).get("networkInterfaces") or []:
            seg = _segments(ref.get("id", ""))
            [nic] = read("network.network_interfaces.get", seg["rg"], seg.get("networkinterfaces", "")) or [None]
            if nic is None:
                continue
            props = nic["body"].get("properties") or {}
            nsgs = [(props.get("networkSecurityGroup") or {}).get("id")]
            for cfg in props.get("ipConfigurations") or []:
                sub_id = ((cfg.get("properties") or {}).get("subnet") or {}).get("id")
                if not sub_id:
                    continue
                s = _segments(sub_id)
                [subnet] = read("network.subnets.get", s["rg"], s.get("virtualnetworks", ""), s.get("subnets", "")) \
                    or [None]
                if subnet is not None:
                    nsgs.append(((subnet["body"].get("properties") or {}).get("networkSecurityGroup") or {}).get("id"))
            for nsg_id in filter(None, nsgs):
                if nsg_id.lower() in seen_nsgs:
                    continue
                seen_nsgs.add(nsg_id.lower())
                n = _segments(nsg_id)
                read("network.network_security_groups.get", n["rg"], n.get("networksecuritygroups", ""))
                read("network.security_rules.list", n["rg"], n.get("networksecuritygroups", ""))
    if vault:
        v_rg, v_name = vault
        names = {name.lower() for _, name in vms}
        jobs = read("backup.backup_jobs.list", v_name, v_rg)
        if jobs:
            got["backup.backup_jobs.list"] = _jobs_kept(got["backup.backup_jobs.list"], names)
        newest: dict = {}
        for r in got.get("backup.backup_jobs.list", []):
            for j in (r["body"] or {}).get("value") or []:
                p = j.get("properties") or {}
                key = (str(p.get("entityFriendlyName", "")).lower(), p.get("operation"))
                if key not in newest or str(p.get("startTime", "")) > newest[key][0]:
                    newest[key] = (str(p.get("startTime", "")), j.get("name"))
        for (_vm, operation), (_at, job_name) in sorted(newest.items()):
            if operation in ("Restore", "Backup") and job_name:
                read("backup.job_details.get", v_name, v_rg, job_name)
        for rg, name in vms:
            container = f"IaasVMContainer;iaasvmcontainerv2;{rg};{name}"
            item = f"VM;iaasvmcontainerv2;{rg};{name}"
            [found] = read("backup.protected_items.get", v_name, v_rg, "Azure", container, item) or [None]
            if found is not None:
                seg = [p for p in str(found["body"].get("id", "")).split("/") if p]
                low = [p.lower() for p in seg]
                if "protectioncontainers" in low and "protecteditems" in low:
                    container = seg[low.index("protectioncontainers") + 1]
                    item = seg[low.index("protecteditems") + 1]
            read("backup.recovery_points.list", v_name, v_rg, "Azure", container, item)
    return got


def _jobs_kept(responses: list[dict], names: set[str]) -> list[dict]:
    """The vault's jobs of the named VMs only, the newest JOBS_KEPT, on one page as listed."""
    jobs = [j for r in responses for j in (r["body"] or {}).get("value") or []
            if str((j.get("properties") or {}).get("entityFriendlyName", "")).lower() in names]
    jobs.sort(key=lambda j: str((j.get("properties") or {}).get("startTime", "")), reverse=True)
    first = responses[0]
    return [{**first, "body": {**(first["body"] or {}), "value": jobs[:JOBS_KEPT], "nextLink": None}}]


def files(got: dict[str, list[dict]], captured: str, versions: dict[str, str]) -> dict[str, dict]:
    """One file per operation, as tests/unit/sdk_bodies/ holds them."""
    out = {}
    for op, responses in got.items():
        if not responses:
            continue
        sdk = op.split(".")[0]
        out[f"{op}.json"] = {
            "operation": op, "source": "measured", "captured": captured,
            "sdk": f"{PACKAGES[sdk]}=={versions.get(sdk, '?')}",
            "api_version": _api_version(responses[0]["url"]),
            "note": "Measured at the bench (scripts/sdk_capture.py), anonymized.",
            "responses": [{"url": _path_and_query(r["url"]), "status": r["status"], "body": r["body"]}
                          for r in responses],
        }
    return out


def _path_and_query(url: str) -> str:
    """The request's path, decoded (a backup container's `;` is sent as `%3B`: encoded, the names
    after it escaped the anonymization), and its query; its host left out (always ARM's)."""
    from urllib.parse import unquote, urlsplit
    parts = urlsplit(url)
    return unquote(parts.path) + (f"?{parts.query}" if parts.query else "")


# ── the anonymization ───────────────────────────────────────────────────────────────────────────

GUID = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
                  r"(?![0-9a-fA-F])")
FAKE_GUID = re.compile(r"^00000000-0000-4000-8000-[0-9a-f]{12}$")
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.]*\d)")
MAC = re.compile(r"(?<![0-9A-Fa-f-])[0-9A-Fa-f]{2}(?:-[0-9A-Fa-f]{2}){5}(?![0-9A-Fa-f-])")
FAKE_MAC = re.compile(r"^00-00-5E-00-53-[0-9A-F]{2}$")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
ARM_ID = re.compile(r"/subscriptions/[^\s\"'?#&]+", re.IGNORECASE)
# A host of Azure: its first label is someone's (a storage account, a VM's DNS, a key vault).
HOST = re.compile(r"(?<![A-Za-z0-9.-])([A-Za-z0-9-]+)((?:\.[A-Za-z0-9-]+)*\.(?:core\.windows\.net|cloudapp\.net|"
                  r"cloudapp\.azure\.com|vault\.azure\.net))", re.IGNORECASE)
DASHED_BLOCK = re.compile(r"glorfindel-block-(\d{1,3})-(\d{1,3})-(\d{1,3})-(\d{1,3})(?![0-9])", re.IGNORECASE)
SKIP_TOKEN = re.compile(r"((?:\$|%24)skiptoken=)([^&\s\"]*)", re.IGNORECASE)
# Azure's platform addresses and the like: no one's.
KEPT_IPS = frozenset({"0.0.0.0", "127.0.0.1", "168.63.129.16", "169.254.169.254", "255.255.255.255"})
DOC_NETS = tuple(ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24"))
# The private stand-ins: 10.240.<n>.<last octet> — outside 10.0.0.0/16, the range most real networks use.
FAKE_PRIVATE = ipaddress.ip_network("10.240.0.0/16")
# Names Azure gives, or that name nothing of anyone: kept.
KEPT_NAMES = frozenset({
    "azure", "default", "example", "ipconfig", "ipconfig1", "ipconfig2", "allowvnetinbound",
    "allowazureloadbalancerinbound", "denyallinbound", "allowvnetoutbound", "allowinternetoutbound",
    "denyalloutbound", "iaasvmcontainer", "iaasvmcontainerv2", "vm"})
# Name kinds by an ARM id's type (lowercase); any other type: "res".
KINDS = {
    "resourcegroups": "rg", "virtualmachines": "vm", "networkinterfaces": "nic", "networksecuritygroups": "nsg",
    "virtualnetworks": "vnet", "subnets": "snet", "publicipaddresses": "pip", "disks": "disk",
    "snapshots": "snap", "vaults": "rsv", "storageaccounts": "st", "applicationsecuritygroups": "asg",
    "availabilitysets": "avset", "extensions": "ext", "ipconfigurations": "ipconfig", "securityrules": "rule",
    "userassignedidentities": "id", "routetables": "rt", "loadbalancers": "lb", "images": "img",
    "proximityplacementgroups": "ppg", "networkwatchers": "nw",
}
# Types whose segment is never a name: fixed by Azure, a GUID, or a number.
FIXED_TYPES = frozenset({"defaultsecurityrules", "backupfabrics", "backupjobs", "recoverypoints"})
COMPOSITE_TYPES = frozenset({"protectioncontainers", "protecteditems"})
OUR_PREFIXES = ("glorfindel-", "nsg-glorfindel-quarantine")
# Tags whose value is Glorfindel's or Eregion's own word: kept (an id in it is anonymized as an id).
OUR_TAG_KEYS = ("managed-by", "glorfindel-", "eregion-", "always-on")
SAFE_TAG_VALUES = frozenset({"glorfindel", "true", "false", "bench", "twin", "production", "eregion"})
SECRETS = frozenset({"keydata", "userdata", "customdata", "secretdata", "keybackupdata"})
# Keys whose value names someone or something: a stand-in of this kind.
NAMED_BY_KEY = {"adminusername": "user", "computername": "host", "fqdn": "host", "domainnamelabel": "host",
                "reversefqdn": "host", "entityfriendlyname": "vm", "friendlyname": "vm"}
BAG_WORDS = ("name", "account", "group", "vault", "disk", "storage", "server")
AZURE_TEXTS = frozenset({
    "Allow inbound traffic from all VMs in VNET", "Allow inbound traffic from azure load balancer",
    "Deny all inbound traffic", "Allow outbound traffic from all VMs to all VMs in VNET",
    "Allow outbound traffic from all VMs to Internet", "Deny all outbound traffic"})


def _marks(nic_id: str) -> list[str]:
    """Every mark Glorfindel derives from a NIC's id (glorfindel/providers/azure/nsg.py,
    quarantine_origin.py): 128 bits of SHA-256, 12, 8 and 6 hex of SHA-1, and 8 of the id as written."""
    low = nic_id.rstrip("/").lower().encode()
    return [hashlib.sha256(low).hexdigest()[:32], hashlib.sha1(low).hexdigest()[:12],
            hashlib.sha1(low).hexdigest()[:8], hashlib.sha1(low).hexdigest()[:6],
            hashlib.sha1(nic_id.rstrip("/").encode()).hexdigest()[:8]]


def _stand_in(low: str) -> bool:
    return bool(re.fullmatch(r"[a-z]+-example-\d+|stexample\d+|text-example-\d+", low))


def _sub_all(text: str, table: dict[str, str], before: str, after: str) -> str:
    """Every key of `table` (lowercase) replaced in `text`, whatever its case, the longest first."""
    if not table:
        return text
    keys = sorted(table, key=len, reverse=True)
    pattern = re.compile(before + "(" + "|".join(re.escape(k) for k in keys) + ")" + after, re.IGNORECASE)
    return pattern.sub(lambda m: table[m.group(1).lower()], text)


class Anonymizer:
    """The same real, the same stand-in — across every file of a capture. `collect` every capture
    first (the names), then `anonymize` each."""

    def __init__(self, seeds: dict[str, str] | None = None, subscription: str = ""):
        self.guids: dict[str, str] = {}
        self.names: dict[str, str] = {}            # real (lowercase) → stand-in
        self.counters: dict[str, int] = {}
        self.ips: dict[str, str] = {}
        self.nets: dict[str, int] = {}
        self.publics = 0
        self.macs: dict[str, str] = {}
        self.emails: dict[str, str] = {}
        self.marks: dict[str, str] = {}
        self.tokens: dict[str, str] = {}
        self.nic_ids: set[str] = set()
        self.texts = 0
        if subscription:
            self.guid(subscription)                # the first stand-in: …-000000000001, as the hypotheses'
        for real, kind in (seeds or {}).items():
            self.name(kind, real)

    # ── one value of each kind
    def guid(self, real: str) -> str:
        low = real.lower()
        if FAKE_GUID.match(low):
            return low
        if low not in self.guids:
            self.guids[low] = f"00000000-0000-4000-8000-{len(self.guids) + 1:012x}"
        return self.guids[low]

    def name(self, kind: str, real: str) -> str:
        low = str(real).strip().lower()
        if (not low or low in KEPT_NAMES or low.startswith(OUR_PREFIXES) or low.isdigit()
                or GUID.fullmatch(low) or _stand_in(low)):
            return real
        if low not in self.names:
            n = self.counters[kind] = self.counters.get(kind, 0) + 1
            self.names[low] = f"stexample{n:02d}" if kind == "st" else f"{kind}-example-{n:02d}"
        return self.names[low]

    def ip(self, real: str) -> str:
        if real in KEPT_IPS:
            return real
        try:
            addr = ipaddress.ip_address(real)
        except ValueError:
            return real
        if any(addr in n for n in DOC_NETS):
            return real                             # never a real address
        if real not in self.ips:
            if addr.is_private:
                net, last = real.rsplit(".", 1)
                self.nets.setdefault(net, len(self.nets) + 1)
                self.ips[real] = f"10.240.{self.nets[net]}.{last}"
            else:
                k = self.publics
                self.publics += 1
                self.ips[real] = str(DOC_NETS[k // 254 % 3].network_address + (k % 254) + 1)
        return self.ips[real]

    def mac(self, real: str) -> str:
        key = real.upper()
        if FAKE_MAC.match(key):
            return key
        if key not in self.macs:
            self.macs[key] = f"00-00-5E-00-53-{len(self.macs) + 1:02X}"
        return self.macs[key]

    def email(self, real: str) -> str:
        key = real.lower()
        if key.endswith("@example.org"):
            return key
        if key not in self.emails:
            self.emails[key] = f"someone-{len(self.emails) + 1:02d}@example.org"
        return self.emails[key]

    def token(self, real: str) -> str:
        if real not in self.tokens:
            self.tokens[real] = f"page-{len(self.tokens) + 2}"
        return self.tokens[real]

    def text(self) -> str:
        self.texts += 1
        return f"text-example-{self.texts:02d}"

    # ── first pass: the names
    def collect(self, value) -> None:
        """Every name the bodies carry: those of the ARM ids first (their kind is sure), then those
        a key names, a host carries, a backup container or a property bag holds."""
        strings = list(_strings(value))
        for _key, text in strings:
            for m in ARM_ID.finditer(text):
                self._collect_id(m.group(0))
        for key, text in strings:
            low = key.lower()
            # Every address before any text is replaced: a block's name carries its address dashed,
            # often before the rule's prefix carries it dotted.
            for m in IPV4.finditer(text):
                self.ip(m.group(0))
            for m in DASHED_BLOCK.finditer(text):
                self.ip(".".join(m.groups()))
            for m in HOST.finditer(text):
                self.name("st" if "core.windows.net" in m.group(2).lower() else "host", m.group(1))
            if low in NAMED_BY_KEY:
                self.name(NAMED_BY_KEY[low], text.split(".")[0] if NAMED_BY_KEY[low] == "host" else text)
            elif low in ("containername", "protecteditemname"):
                self._collect_composite(text)
            elif " " in key and any(w in low for w in BAG_WORDS):       # a property bag's « VM Name »
                self.name("name", text)

    def _collect_id(self, arm_id: str) -> None:
        parts = [p for p in arm_id.split("/") if p]
        low = [p.lower() for p in parts]
        for i, part in enumerate(low[:-1]):
            if part == "resourcegroups":
                self.name("rg", parts[i + 1])
        if "providers" not in low:
            return
        start = low.index("providers") + 2
        for i in range(start, len(parts) - 1, 2):
            if low[i] in FIXED_TYPES:
                continue
            if low[i] in COMPOSITE_TYPES:
                self._collect_composite(parts[i + 1])
                continue
            self.name(KINDS.get(low[i], "res"), parts[i + 1])
        if len(parts) > start + 1 and low[start] == "networkinterfaces":
            self.nic_ids.add("/" + "/".join(parts[:start + 2]))

    def _collect_composite(self, value: str) -> None:
        """A backup container or item: `IaasVMContainer;iaasvmcontainerv2;<group>;<vm>`."""
        bits = value.split(";")
        if len(bits) >= 3:
            self.name("rg", bits[-2])
            self.name("vm", bits[-1])

    def finish(self) -> None:
        """The marks of every NIC met: the same hashes of its stand-in id."""
        for real_id in sorted(self.nic_ids):
            fake_id = self.replace(real_id)
            for real, fake in zip(_marks(real_id), _marks(fake_id)):
                self.marks.setdefault(real, fake)

    # ── second pass: every value
    def anonymize(self, value, key: str = "", in_tags: bool = False):
        if isinstance(value, dict):
            return {self.replace(str(k)): self.anonymize(v, str(k), in_tags=key.lower() == "tags")
                    for k, v in value.items()}
        if isinstance(value, list):
            return [self.anonymize(v, key) for v in value]
        if not isinstance(value, str):
            return value
        low = key.lower()
        if low in SECRETS:
            return "ssh-rsa AAAAstand-in" if low == "keydata" else "c3RhbmQtaW4="
        if low == "description" and not value.lower().startswith("glorfindel") and value not in AZURE_TEXTS:
            return self.text()
        if in_tags and not (low.startswith(OUR_TAG_KEYS) or value.lower() in SAFE_TAG_VALUES
                            or ARM_ID.search(value)):
            return self.text()
        return self.replace(value)

    def replace(self, text: str) -> str:
        """`text` with every real it holds replaced."""
        out = GUID.sub(lambda m: self.guid(m.group(0)), text)
        out = SKIP_TOKEN.sub(lambda m: m.group(1) + self.token(m.group(2)), out)
        out = MAC.sub(lambda m: self.mac(m.group(0)), out)
        out = EMAIL.sub(lambda m: self.email(m.group(0)), out)
        out = IPV4.sub(lambda m: self.ip(m.group(0)), out)
        out = _sub_all(out, {k.replace(".", "-"): v.replace(".", "-") for k, v in self.ips.items()},
                       r"(?<![0-9])", r"(?![0-9])")
        out = _sub_all(out, self.marks, r"(?<![0-9a-fA-F])", r"(?![0-9a-fA-F])")
        return _sub_all(out, self.names, r"(?<![A-Za-z0-9])", r"(?![A-Za-z0-9])")

    # ── what the output must not hold
    def reals(self) -> dict[str, set[str]]:
        """Every real value met, by kind — those equal to a stand-in left out."""
        fakes = set(self.ips.values()) | {v.replace(".", "-") for v in self.ips.values()}
        return {"guid": set(self.guids),
                "name": {n for n in self.names if len(n) >= 3},
                "ip": ({ip for ip in self.ips} | {ip.replace(".", "-") for ip in self.ips}) - fakes,
                "mac": set(self.macs) - set(self.macs.values()), "email": set(self.emails),
                "mark": set(self.marks) - set(self.marks.values())}


def _strings(value, key: str = ""):
    """Every (key, text) of a body, keys included."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield "", str(k)
            yield from _strings(v, str(k))
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v, key)
    elif isinstance(value, str):
        yield key, value


def anonymize(captures: dict[str, dict], seeds: dict[str, str] | None = None,
              subscription: str = "") -> tuple[dict[str, dict], Anonymizer]:
    """Every capture anonymized together (the subscription the first GUID, the seeds the first
    names: the bench's group `rg-example-01`, its VM `vm-example-01`), then checked: a leak raises,
    nothing is returned."""
    a = Anonymizer(seeds, subscription)
    for cap in captures.values():
        a.collect(cap)
    a.finish()
    out = {name: a.anonymize(cap) for name, cap in captures.items()}
    leaks = leaked(out, a.reals()) + structural(out)
    if leaks:
        raise Leak("sdk_capture: nothing written — " + "; ".join(sorted(set(leaks))[:20]))
    return out, a


def leaked(captures: dict[str, dict], reals: dict[str, set[str]]) -> list[str]:
    """Where a real value met is still in the output: '<file>: a real <kind>' (never the value)."""
    found = []
    for name, cap in captures.items():
        text = json.dumps(cap, ensure_ascii=False).lower()
        for kind, values in reals.items():
            if any(re.search(r"(?<![a-z0-9])" + re.escape(v.lower()) + r"(?![a-z0-9])", text) for v in values):
                found.append(f"{name}: a real {kind}")
    return found


def structural(captures: dict[str, dict], forbid: tuple[str, ...] = ()) -> list[str]:
    """Where a value is not of a stand-in's form — a GUID, an IPv4, an e-mail, a MAC, a host, a name
    in an ARM id —, or a word `forbid` names: '<file>: <what>' (never the value)."""
    found = []
    for name, cap in captures.items():
        text = json.dumps(cap, ensure_ascii=False)
        if any(not FAKE_GUID.match(g.lower()) for g in GUID.findall(text)):
            found.append(f"{name}: a GUID not of the stand-in's form")
        if any(not _ip_of_stand_in(ip) for ip in IPV4.findall(text)):
            found.append(f"{name}: an IPv4 outside the documentation ranges and {FAKE_PRIVATE}")
        if any(not e.lower().endswith("@example.org") for e in EMAIL.findall(text)):
            found.append(f"{name}: an e-mail address outside example.org")
        if any(not FAKE_MAC.match(m.upper()) for m in MAC.findall(text)):
            found.append(f"{name}: a MAC address not of the stand-in's form")
        if any(not (m.group(1).lower() in KEPT_NAMES or _stand_in(m.group(1).lower())) for m in HOST.finditer(text)):
            found.append(f"{name}: a host not of the stand-in's form")
        if any(not _id_of_stand_ins(m.group(0)) for m in ARM_ID.finditer(text)):
            found.append(f"{name}: an ARM id naming something real")
        low = text.lower()
        if any(w and re.search(r"(?<![a-z0-9])" + re.escape(w.lower()) + r"(?![a-z0-9])", low) for w in forbid):
            found.append(f"{name}: a forbidden word")
    return found


def _ip_of_stand_in(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True                                 # not an address (a version, say)
    return ip in KEPT_IPS or addr in FAKE_PRIVATE or any(addr in n for n in DOC_NETS)


def _id_of_stand_ins(arm_id: str) -> bool:
    parts = [p for p in arm_id.split("/") if p]
    low = [p.lower() for p in parts]
    if any(part == "resourcegroups" and not _stand_in(low[i + 1]) for i, part in enumerate(low[:-1])):
        return False
    if "providers" not in low:
        return True
    start = low.index("providers") + 2
    for i in range(start, len(parts) - 1, 2):
        rtype, value = low[i], low[i + 1]
        if rtype in FIXED_TYPES or value.isdigit() or FAKE_GUID.match(value):
            continue
        if rtype in COMPOSITE_TYPES:
            if not all(b in KEPT_NAMES or _stand_in(b) for b in value.split(";")):
                return False
        elif not (value in KEPT_NAMES or _stand_in(value) or value.startswith(OUR_PREFIXES)):
            return False
    return True


# ── the command ─────────────────────────────────────────────────────────────────────────────────

def _pair(text: str) -> tuple[str, str]:
    group, _, name = text.partition("/")
    if not group or not name or "/" in name:
        raise argparse.ArgumentTypeError(f"expected <group>/<name>, got {text!r}")
    return group, name


def _outside_repo(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved == REPO or REPO in resolved.parents:
        raise SystemExit("sdk_capture: --out must be outside the repository — the files are read "
                         "before they are copied into tests/unit/sdk_bodies/")
    return resolved


def _versions() -> dict[str, str]:
    from importlib.metadata import version
    return {sdk: version(pkg) for sdk, pkg in PACKAGES.items()}


def write(out_dir: Path, anonymized: dict[str, dict]) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, cap in sorted(anonymized.items()):
        path = out_dir / name
        path.write_text(json.dumps(cap, indent=2, ensure_ascii=False) + "\n")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    cap = sub.add_parser("capture", help="read the bench, anonymize, write the bodies")
    cap.add_argument("--vm", type=_pair, action="append", required=True, help="<group>/<vm>, again for more")
    cap.add_argument("--vault", type=_pair, help="<group>/<vault>")
    cap.add_argument("--group", action="append", default=[], help="one more group kept from the listings")
    cap.add_argument("--out", type=Path, required=True, help="a folder outside this repository")
    cap.add_argument("--subscription", default=os.environ.get("AZURE_SUBSCRIPTION_ID", ""))
    chk = sub.add_parser("check", help="check a folder of bodies: nothing but stand-ins")
    chk.add_argument("folder", type=Path)
    chk.add_argument("--forbid", action="append", default=[], help="a word that must not appear")
    args = parser.parse_args(argv)

    if args.cmd == "check":
        loaded = {p.name: json.loads(p.read_text()) for p in sorted(args.folder.expanduser().glob("*.json"))}
        forbid = tuple(args.forbid) + tuple(v for v in (os.environ.get("AZURE_SUBSCRIPTION_ID"),
                                                         os.environ.get("AZURE_TENANT_ID")) if v)
        leaks = structural(loaded, forbid)
        for line in leaks:
            print(f"  {line}")
        print(f"sdk_capture check: {len(loaded)} file(s), {'NOT clean' if leaks else 'clean'}")
        return 1 if leaks or not loaded else 0

    if not args.subscription:
        raise SystemExit("sdk_capture: no subscription — export AZURE_SUBSCRIPTION_ID (az account show)")
    out_dir = _outside_repo(args.out)
    from azure.identity import AzureCliCredential
    got = capture(clients(AzureCliCredential(), args.subscription), args.vm, args.vault, set(args.group))
    captured = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    seeds = {g: "rg" for g, _ in args.vm} | {n: "vm" for _, n in args.vm}
    if args.vault:
        seeds |= {args.vault[0]: "rg", args.vault[1]: "rsv"}
    seeds |= {g: "rg" for g in args.group}
    anonymized, a = anonymize(files(got, captured, _versions()), seeds, args.subscription)
    for path in write(out_dir, anonymized):
        print(f"  wrote {path.name}")
    print(f"sdk_capture: {len(anonymized)} file(s) in {out_dir} — replaced {len(a.guids)} GUID(s), "
          f"{len(a.names)} name(s), {len(a.ips)} address(es), {len(a.macs)} MAC(s), {len(a.emails)} "
          f"e-mail(s), {len(a.marks)} mark(s), {a.texts} text(s). Read them, then `check`.")
    missing = [op for op in READS if op not in got and op != "backup.protected_items.get"]
    if missing:
        print("  no body for: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
