"""SDK1b (#1017): the anonymization of the bodies scripts/sdk_capture.py captures — a module of its own
(the rule of the big files, 21/11). Pure functions over JSON: nothing here reads Azure or the network.

The same real, the same stand-in, across every file of a capture (`Anonymizer`):
- GUIDs (subscription, tenant, object ids, job names, etags) → `00000000-0000-4000-8000-<n>`, the
  subscription the first;
- names — those of every ARM id, the VM and group of a backup container, the VM's user, its host
  names, a property bag's « … Name » — → `<kind>-example-<n>` (a storage account `stexample<n>`), the
  shape of an ARM id kept; Azure's own names and Glorfindel's prefixes kept, what they embed replaced;
- the marks Glorfindel's rule names and quarantine tags end with (hashes of a NIC's id) → the same
  hashes of the stand-in id: the rule still names its NIC; any other 32 hex → `0…0<n>`;
- IPv4: private → 10.240.<n>.<last octet> (by /24), public → 192.0.2.0/24, 198.51.100.0/24,
  203.0.113.0/24, also dashed in a block's name; IPv6 → 2001:db8::<n> (the documentation range);
  Azure's platform addresses kept; MACs → 00-00-5E-00-53-<n>; e-mail addresses → example.org;
- a domain outside Azure's → `domain-example-<n>.example.org`, whole (under Azure's suffixes, its
  first label);
- a tag's key that is not Glorfindel's or Eregion's → `tag-example-<n>`, its value a stand-in text;
- free text (a description, an error's words, a task's details) → a stand-in text unless Azure's or
  Glorfindel's own; a secret — a key that says key, token, secret, password or SAS, an SSH key, user
  data, a SAS signature — → a stand-in.

Then a check, before anything is written: no real value met may remain (`leaked`), and every GUID,
address, MAC, e-mail, host, domain, ARM name, 32 hex in the output must be a stand-in's form, with no
JWT, long base64, SSH key, SAS signature or secret left (`structural`, which `check` runs on a folder).

**Its limit**: a word of free text no id, no key and no form names — a person's name, a server's, in
a text Azure writes under a key not listed here — cannot be told from any other word. The maintainer's
reading of each file before it is copied stays the last net (scripts/sdk_capture.py, the way of use).
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re

GUID = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
                  r"(?![0-9a-fA-F])")
FAKE_GUID = re.compile(r"^00000000-0000-4000-8000-[0-9a-f]{12}$")
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.]*\d)")
# An IPv6 candidate: hex groups and at least two colons — an address only if `ipaddress` reads one.
IPV6 = re.compile(r"(?<![0-9A-Za-z:_-])(?:[0-9A-Fa-f]{1,4})?(?::[0-9A-Fa-f]{0,4}){2,7}(?![0-9A-Za-z:_-])")
MAC = re.compile(r"(?<![0-9A-Fa-f:-])[0-9A-Fa-f]{2}([-:])[0-9A-Fa-f]{2}(?:\1[0-9A-Fa-f]{2}){4}(?![0-9A-Fa-f:-])")
FAKE_MAC = re.compile(r"^00[-:]00[-:]5E[-:]00[-:]53[-:][0-9A-F]{2}$")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
ARM_ID = re.compile(r"/subscriptions/[^\s\"'?#&]+", re.IGNORECASE)
# A host of Azure: its first label is someone's (a storage account, a VM's DNS, a key vault).
HOST = re.compile(r"(?<![A-Za-z0-9.-])([A-Za-z0-9-]+)((?:\.[A-Za-z0-9-]+)*\.(?:core\.windows\.net|cloudapp\.net|"
                  r"cloudapp\.azure\.com|vault\.azure\.net))", re.IGNORECASE)
DOMAIN = re.compile(r"(?<![A-Za-z0-9_.@-])((?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,24})"
                    r"(?![A-Za-z0-9_-])")
DASHED_BLOCK = re.compile(r"glorfindel-block-(\d{1,3})-(\d{1,3})-(\d{1,3})-(\d{1,3})(?![0-9])", re.IGNORECASE)
SKIP_TOKEN = re.compile(r"((?:\$|%24)skiptoken=)([^&\s\"]*)", re.IGNORECASE)
SAS_SIG = re.compile(r"((?:[?&]|%26|%3F)sig=)([^&\s\"]*)", re.IGNORECASE)
HEX32 = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])")
FAKE_HEX32 = re.compile(r"^0{20}[0-9a-f]{12}$")
JWT = re.compile(r"eyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]*")
SSH_KEY = re.compile(r"ssh-(?:rsa|dss|ed25519|ecdsa-\S+) [A-Za-z0-9+/]{20,}")
LONG_B64 = re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$")
# Azure's platform addresses and the like: no one's.
KEPT_IPS = frozenset({"0.0.0.0", "127.0.0.1", "168.63.129.16", "169.254.169.254", "255.255.255.255"})
KEPT_IPV6 = frozenset({"::", "::1"})
DOC_NETS = tuple(ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24"))
DOC_V6 = ipaddress.ip_network("2001:db8::/32")
# The private stand-ins: 10.240.<n>.<last octet> — outside 10.0.0.0/16, the range most real networks use.
FAKE_PRIVATE = ipaddress.ip_network("10.240.0.0/16")
# Domains: Azure's (a first label is someone's, replaced as a name), well-known hosts of Azure kept,
# the documentation's; a namespace or a file name is not a domain.
AZURE_SUFFIXES = ("core.windows.net", "cloudapp.net", "cloudapp.azure.com", "vault.azure.net", "azure.com",
                  "azure.net", "windows.net", "microsoft.com", "microsoftonline.com")
KEPT_HOSTS = frozenset({"management.azure.com", "login.microsoftonline.com", "learn.microsoft.com",
                        "schemas.microsoft.com", "github.com"})
EXAMPLE_SUFFIXES = ("example.org", "example.com", "example.net")
# A file's ending that is no top-level domain (`.py`, `.sh`, `.md`, `.zip` are: never here).
FILE_ENDINGS = frozenset({"json", "config", "conf", "ps1", "exe", "log", "txt", "gz", "tar", "vhd", "vhdx", "msi",
                          "yaml", "yml", "xml", "js", "dll", "cfg", "ini"})
# A namespace of ARM (`Microsoft.Network`, `Microsoft.Azure.Monitor`): a domain's form, never one.
NAMESPACE = re.compile(r"Microsoft(?:\.[A-Z][A-Za-z0-9]*)+")
# The operation a capture file names, the value of its key `operation` (`network.subnets.get`).
OPERATION = re.compile(r"(?:network|compute|backup)\.[a-z_]+\.[a-z_]+")
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
# Tags whose key and value are Glorfindel's or Eregion's own words: kept (an id in them anonymized).
OUR_TAG_KEYS = ("managed-by", "glorfindel-", "eregion-", "always-on")
SAFE_TAG_VALUES = frozenset({"glorfindel", "true", "false", "bench", "twin", "production", "eregion"})
# A key that says it holds a secret: its text value a stand-in, whatever it is.
SECRET_WORDS = ("key", "token", "secret", "password", "sas")
SECRET_STAND_INS = frozenset({"stand-in", "ssh-rsa AAAAstand-in", "c3RhbmQtaW4=", ""})
STAND_IN_FOR = {"keydata": "ssh-rsa AAAAstand-in", "userdata": "c3RhbmQtaW4=", "customdata": "c3RhbmQtaW4="}
# Keys whose value names someone or something: a stand-in of this kind.
NAMED_BY_KEY = {"adminusername": "user", "computername": "host", "fqdn": "host", "domainnamelabel": "host",
                "reversefqdn": "host", "internalfqdn": "host", "hostname": "host", "entityfriendlyname": "vm",
                "friendlyname": "vm"}
# Free text: a stand-in unless Azure's or Glorfindel's own.
FREE_TEXT = frozenset({"description", "errorstring", "errortitle", "dynamicerrormessage", "recommendations",
                       "taskexecutiondetails", "additionaldetails"})
BAG_WORDS = ("name", "account", "group", "vault", "disk", "storage", "server")
AZURE_TEXTS = frozenset({
    "Allow inbound traffic from all VMs in VNET", "Allow inbound traffic from azure load balancer",
    "Deny all inbound traffic", "Allow outbound traffic from all VMs to all VMs in VNET",
    "Allow outbound traffic from all VMs to Internet", "Deny all outbound traffic"})


class Leak(RuntimeError):
    """The anonymized output still holds a real value, or a value not of a stand-in's form."""


def _marks(nic_id: str) -> list[str]:
    """Every mark Glorfindel derives from a NIC's id (glorfindel/providers/azure/nsg.py,
    quarantine_origin.py): 128 bits of SHA-256, 12, 8 and 6 hex of SHA-1, and 8 of the id as written."""
    low = nic_id.rstrip("/").lower().encode()
    return [hashlib.sha256(low).hexdigest()[:32], hashlib.sha1(low).hexdigest()[:12],
            hashlib.sha1(low).hexdigest()[:8], hashlib.sha1(low).hexdigest()[:6],
            hashlib.sha1(nic_id.rstrip("/").encode()).hexdigest()[:8]]


def _stand_in(low: str) -> bool:
    return bool(re.fullmatch(r"[a-z]+-example-\d+|stexample\d+", low))


def _ipv6(text: str):
    try:
        return ipaddress.IPv6Address(text)
    except ValueError:
        return None


def _is_domain(text: str, m) -> bool:
    """`m`, a match of DOMAIN in the value `text`, is a domain name: not a namespace of ARM — its
    form, followed by `/` or ending the value (`Microsoft.Network/…`, `Microsoft.Azure.Monitor`) —
    nor a file's name (an ending no domain has). `compute.example.fr`, `microsoft.example.fr`,
    `example.md` are domains."""
    token, after = m.group(1), text[m.end(1):m.end(1) + 1]
    if NAMESPACE.fullmatch(token) and after in ("", "/"):
        return False
    return token.rsplit(".", 1)[-1].lower() not in FILE_ENDINGS


def _operation(key: str, value: str) -> bool:
    """The value of a capture file's key `operation`: an operation's name, no domain."""
    return key.lower() == "operation" and bool(OPERATION.fullmatch(value))


def _domain_kept(low: str) -> bool:
    return (low in KEPT_HOSTS or low.endswith(EXAMPLE_SUFFIXES)
            or any(low == s or low.endswith("." + s) for s in AZURE_SUFFIXES))


def _secret_key(low_key: str) -> bool:
    return any(w in low_key for w in SECRET_WORDS)


def _sub_all(text: str, table: dict[str, str], before: str, after: str) -> str:
    """Every key of `table` (lowercase) replaced in `text`, whatever its case, the longest first."""
    if not table:
        return text
    keys = sorted(table, key=len, reverse=True)
    pattern = re.compile(before + "(" + "|".join(re.escape(k) for k in keys) + ")" + after, re.IGNORECASE)
    return pattern.sub(lambda m: table[m.group(1).lower()], text)


def _strings(value, key: str = ""):
    """Every (key, text) of a body, its keys included (with an empty key)."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield "", str(k)
            yield from _strings(v, str(k))
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v, key)
    elif isinstance(value, str):
        yield key, value


class Anonymizer:
    """The same real, the same stand-in — across every file of a capture. `collect` every capture
    first (the names, the addresses), then `anonymize` each."""

    def __init__(self, seeds: dict[str, str] | None = None, subscription: str = "",
                 protected: frozenset[str] = frozenset()):
        # The words the bodies are made of (`structure_words`): never taken for a name — replaced
        # everywhere, one would break every id (`network` in `Microsoft.Network`).
        self.protected = protected
        self.guids: dict[str, str] = {}
        self.names: dict[str, str] = {}            # real (lowercase) → stand-in
        self.counters: dict[str, int] = {}
        self.ips: dict[str, str] = {}
        self.nets: dict[str, int] = {}
        self.publics = 0
        self.ipv6s: dict[str, str] = {}
        self.macs: dict[str, str] = {}
        self.emails: dict[str, str] = {}
        self.domains: dict[str, str] = {}
        self.marks: dict[str, str] = {}
        self.hexes: dict[str, str] = {}
        self.tag_keys: dict[str, str] = {}
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
        if (not low or low in KEPT_NAMES or low in self.protected or low.startswith(OUR_PREFIXES)
                or low.isdigit() or GUID.fullmatch(low) or _stand_in(low)):
            return real                             # a word of the structure left real: refused by the check
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

    def ipv6(self, real: str) -> str:
        addr = _ipv6(real)
        if addr is None or str(addr) in KEPT_IPV6 or addr in DOC_V6:
            return real
        key = str(addr)
        if key not in self.ipv6s:
            self.ipv6s[key] = str(DOC_V6.network_address + len(self.ipv6s) + 1)
        return self.ipv6s[key]

    def mac(self, real: str) -> str:
        key = real.upper().replace(":", "-")
        if FAKE_MAC.match(key):
            return real.upper()
        if key not in self.macs:
            self.macs[key] = f"00-00-5E-00-53-{len(self.macs) + 1:02X}"
        return self.macs[key].replace("-", ":") if ":" in real else self.macs[key]

    def email(self, real: str) -> str:
        key = real.lower()
        if key.endswith("@example.org"):
            return key
        if key not in self.emails:
            self.emails[key] = f"someone-{len(self.emails) + 1:02d}@example.org"
        return self.emails[key]

    def domain(self, real: str) -> str:
        """A domain's stand-in (its caller has judged it a domain, `_is_domain`)."""
        low = real.lower()
        if _domain_kept(low):
            return real
        if low not in self.domains:               # replaced whole: its labels are not names
            self.domains[low] = f"domain-example-{len(self.domains) + 1:02d}.example.org"
        return self.domains[low]

    def hex32(self, real: str) -> str:
        low = real.lower()
        if low in self.marks or low in self.marks.values() or FAKE_HEX32.match(low):
            return real                             # a mark: replaced, or a stand-in already
        if low not in self.hexes:
            self.hexes[low] = f"{len(self.hexes) + 1:032x}"
        return self.hexes[low]

    def tag_key(self, real: str) -> str:
        if real.lower().startswith(OUR_TAG_KEYS):
            return self.replace(real)
        if real.lower() not in self.tag_keys:
            self.tag_keys[real.lower()] = f"tag-example-{len(self.tag_keys) + 1:02d}"
        return self.tag_keys[real.lower()]

    def token(self, real: str) -> str:
        if real not in self.tokens:
            self.tokens[real] = f"page-{len(self.tokens) + 2}"
        return self.tokens[real]

    def text(self) -> str:
        self.texts += 1
        return f"text-example-{self.texts:02d}"

    # ── first pass: the names, the addresses
    def collect(self, value) -> None:
        """Every name the bodies carry: those of the ARM ids first (their kind is sure), then those
        a key names, a host or a domain carries, a backup container or a property bag holds; and
        every address, before any text is replaced (a block's name carries its address dashed,
        often before the rule's prefix carries it dotted)."""
        strings = list(_strings(value))
        for _key, text in strings:
            for m in ARM_ID.finditer(text):
                self._collect_id(m.group(0))
        for key, text in strings:
            low = key.lower()
            for m in IPV4.finditer(text):
                self.ip(m.group(0))
            for m in DASHED_BLOCK.finditer(text):
                self.ip(".".join(m.groups()))
            for m in HOST.finditer(text):
                self.name("st" if "core.windows.net" in m.group(2).lower() else "host", m.group(1))
            for m in ([] if _operation(key, text) else DOMAIN.finditer(text)):
                if _is_domain(text, m) and not _domain_kept(m.group(1).lower()):
                    self.domain(m.group(1))
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
            tags = key.lower() == "tags"
            return {(self.tag_key(str(k)) if tags else self.replace(str(k))): self.anonymize(v, str(k), in_tags=tags)
                    for k, v in value.items()}
        if isinstance(value, list):
            return [self.anonymize(v, key) for v in value]
        if not isinstance(value, str):
            return value
        low = key.lower()
        if _operation(low, value):
            return value
        if low in STAND_IN_FOR:
            return STAND_IN_FOR[low]
        if _secret_key(low) and not ARM_ID.match(value):
            return "stand-in" if value else value
        if low in FREE_TEXT and not value.lower().startswith("glorfindel") and value not in AZURE_TEXTS:
            return self.text()
        if in_tags and not (low.startswith(OUR_TAG_KEYS) or value.lower() in SAFE_TAG_VALUES
                            or ARM_ID.search(value)):
            return self.text()
        return self.replace(value)

    def replace(self, text: str) -> str:
        """`text` with every real it holds replaced."""
        out = GUID.sub(lambda m: self.guid(m.group(0)), text)
        out = SKIP_TOKEN.sub(lambda m: m.group(1) + self.token(m.group(2)), out)
        out = SAS_SIG.sub(lambda m: m.group(1) + "stand-in", out)
        out = MAC.sub(lambda m: self.mac(m.group(0)), out)
        out = EMAIL.sub(lambda m: self.email(m.group(0)), out)
        out = IPV4.sub(lambda m: self.ip(m.group(0)), out)
        out = IPV6.sub(lambda m: self.ipv6(m.group(0)), out)
        out = DOMAIN.sub(lambda m: self.domain(m.group(1)) if _is_domain(m.string, m) else m.group(1), out)
        out = _sub_all(out, {k.replace(".", "-"): v.replace(".", "-") for k, v in self.ips.items()},
                       r"(?<![0-9])", r"(?![0-9])")
        out = HEX32.sub(lambda m: self.hex32(m.group(0)), out)
        out = _sub_all(out, self.marks, r"(?<![0-9a-fA-F])", r"(?![0-9a-fA-F])")
        return _sub_all(out, self.names, r"(?<![A-Za-z0-9])", r"(?![A-Za-z0-9])")

    # ── what the output must not hold
    def reals(self) -> dict[str, set[str]]:
        """Every real value met, by kind — those equal to a stand-in left out."""
        fakes = set(self.ips.values()) | {v.replace(".", "-") for v in self.ips.values()}
        return {"guid": set(self.guids),
                "name": {n for n in self.names if len(n) >= 3},
                "ip": ({ip for ip in self.ips} | {ip.replace(".", "-") for ip in self.ips}) - fakes,
                "ipv6": set(self.ipv6s), "domain": set(self.domains), "tag key": set(self.tag_keys),
                "mac": set(self.macs) - set(self.macs.values()), "email": set(self.emails),
                "mark": set(self.marks) - set(self.marks.values()), "hex": set(self.hexes)}


STRUCTURE = frozenset({"api", "version", "api-version", "https", "http", "management", "azure", "com", "net",
                       "windows", "core", "microsoft", "subscriptions", "resourcegroups", "providers", "org"})


def structure_words(captures: dict[str, dict]) -> frozenset[str]:
    """The words the bodies are made of: their keys, the namespaces and types of their ARM ids, the
    words of an ARM URL — none is ever a name to replace."""
    words = set(STRUCTURE)
    for cap in captures.values():
        for key, text in _strings(cap):
            if key == "":
                words.add(text.lower())
            for m in ARM_ID.finditer(text):
                parts = [x.lower() for x in m.group(0).split("/") if x]
                if "providers" in parts:
                    i = parts.index("providers")
                    words |= set(parts[i + 1].split("."))
                    words |= set(parts[i + 2::2])
    return frozenset(words)


def anonymize(captures: dict[str, dict], seeds: dict[str, str] | None = None,
              subscription: str = "") -> tuple[dict[str, dict], Anonymizer]:
    """Every capture anonymized together (the subscription the first GUID, the seeds the first
    names: the bench's group `rg-example-01`, its VM `vm-example-01`), then checked: a leak raises,
    nothing is returned."""
    a = Anonymizer(seeds, subscription, structure_words(captures))
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
    """Where a value is not of a stand-in's form — a GUID, an address, an e-mail, a MAC, a host, a
    domain, a name in an ARM id, 32 hex —, a secret's form is left, or a word `forbid` names:
    '<file>: <what>' (never the value)."""
    found = []
    for name, cap in captures.items():
        text = json.dumps(cap, ensure_ascii=False)
        marks = {mk for m in ARM_ID.finditer(text) if "/networkinterfaces/" in m.group(0).lower()
                 for mk in _marks("/".join(m.group(0).split("/")[:9]))}
        checks = (
            ("a GUID not of the stand-in's form", any(not FAKE_GUID.match(g.lower()) for g in GUID.findall(text))),
            (f"an IPv4 outside the documentation ranges and {FAKE_PRIVATE}",
             any(not _ip_of_stand_in(ip) for ip in IPV4.findall(text))),
            (f"an IPv6 outside {DOC_V6}", any(not _ipv6_of_stand_in(c) for c in IPV6.findall(text))),
            ("an e-mail address outside example.org", any(not e.lower().endswith("@example.org")
                                                          for e in EMAIL.findall(text))),
            ("a MAC address not of the stand-in's form", any(not FAKE_MAC.match(m.group(0).upper())
                                                             for m in MAC.finditer(text))),
            ("a host not of the stand-in's form", any(not (m.group(1).lower() in KEPT_NAMES or _stand_in(m.group(1).lower()))
                                                      for m in HOST.finditer(text))),
            ("a domain outside Azure's and the documentation's",
             any(_is_domain(v, m) and not _domain_kept(m.group(1).lower())
                 for k, v in _strings(cap) if not _operation(k, v) for m in DOMAIN.finditer(v))),
            ("an ARM id naming something real", any(not _id_of_stand_ins(m.group(0)) for m in ARM_ID.finditer(text))),
            ("32 hex neither a stand-in nor a stand-in NIC's mark",
             any(not (FAKE_HEX32.match(h.lower()) or h.lower() in marks) for h in HEX32.findall(text))),
            ("a JWT", bool(JWT.search(text))),
            ("an SSH key", bool(SSH_KEY.search(text))),
            ("a SAS signature", any(m.group(2).lower() != "stand-in" for m in SAS_SIG.finditer(text))),
            ("a secret, or a long base64", any(_secret_left(k, v) for k, v in _strings(cap))),
        )
        found += [f"{name}: {what}" for what, failed in checks if failed]
        low = text.lower()
        if any(w and re.search(r"(?<![a-z0-9])" + re.escape(w.lower()) + r"(?![a-z0-9])", low) for w in forbid):
            found.append(f"{name}: a forbidden word")
    return found


def _secret_left(key: str, value: str) -> bool:
    if LONG_B64.match(value):
        return True
    return (_secret_key(key.lower()) and value not in SECRET_STAND_INS
            and not (ARM_ID.match(value) and _id_of_stand_ins(value)))


def _ip_of_stand_in(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True                                 # not an address (a version, say)
    return ip in KEPT_IPS or addr in FAKE_PRIVATE or any(addr in n for n in DOC_NETS)


def _ipv6_of_stand_in(candidate: str) -> bool:
    addr = _ipv6(candidate)
    return addr is None or str(addr) in KEPT_IPV6 or addr in DOC_V6


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
