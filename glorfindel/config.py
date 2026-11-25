"""Glorfindel infrastructure configuration.

Separate from detection_rules.yaml which contains rules only.
Loaded from glorfindel-config.yaml (Docker volume or local dev).
Values are direct (no ${VAR} substitution needed — edit the file directly).
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

# Default search paths, first match wins
_DEFAULT_PATHS = [
    Path("glorfindel-config.yaml"),
    Path(__file__).parent.parent / "glorfindel-config.yaml",
    Path.home() / ".glorfindel" / "config.yaml",
]


class ConfigError(ValueError):
    """glorfindel-config.yaml exists but can't be read or is invalid. Callers that act
    on Azure must STOP on it: falling back to the defaults made an isolation pick
    another quarantine NSG and record "no NSG" as the NIC's original (sixth review, S1).
    A missing file is not an error — the defaults apply."""


# ── Environment switches (G2): a malformed value never makes Glorfindel bolder ──

# GLORFINDEL_READ_ONLY is off only when it clearly says so. The connector accepted
# "1/true/yes" and the War Room "1/true/True": `on`, `TRUE` or `y` left the writes on
# — the observe-only deployment the operator asked for, silently not one.
_SWITCH_OFF = {"", "0", "false", "no", "off", "n"}


def read_only_requested(value: str | None = None) -> bool:
    """GLORFINDEL_READ_ONLY (or `value`): read-only unless unset, empty, or clearly off
    (0, false, no, off). Any other value — a typo included — keeps Glorfindel read-only."""
    import os
    raw = os.environ.get("GLORFINDEL_READ_ONLY", "") if value is None else value
    return str(raw).strip().lower() not in _SWITCH_OFF


CONFIDENCE_THRESHOLD = 0.7


def confidence_threshold() -> float:
    """GLORFINDEL_CONFIDENCE_THRESHOLD: 0.7 when unset or empty; a value in [0, 1]
    otherwise. Malformed, out of range or not a number → infinite: every autonomous
    action is held (G2, configuration fails closed).

    A malformed value used to raise inside decide() and drop the whole cycle, then fell
    back to 0.7 — more permissive than the 0.95 an operator mistyped as "O.95" — and
    `nan` parsed: `confidence < nan` is never true, the gate let everything through.
    Here, next to read_only_requested, so the War Room reads the gate's own value
    without importing the agent (G2 review): an import that failed there dropped the
    whole capability matrix, silently."""
    import math
    import os
    raw = (os.environ.get("GLORFINDEL_CONFIDENCE_THRESHOLD") or "").strip()
    if not raw:
        return CONFIDENCE_THRESHOLD
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = math.nan
    if not 0.0 <= value <= 1.0:          # nan fails the comparison too
        return math.inf
    return value


# A decision call is bounded: LiteLLM's own default is 6000 s per attempt (measured with
# litellm 1.86.1), three attempts with the retries — a provider that hangs held the VM's
# decision queue for hours, with no card. Bounded, it ends as a cycle_failed card.
LLM_TIMEOUT_S = 120.0
_LLM_TIMEOUT_MAX_S = 3600.0


def llm_timeout_s() -> float:
    """GLORFINDEL_LLM_TIMEOUT_S, in (0, 3600]. Unset, malformed, zero, negative or
    infinite → 120 s: a malformed value never unbounds the call."""
    import math
    import os
    raw = os.environ.get("GLORFINDEL_LLM_TIMEOUT_S", "").strip()
    if not raw:
        return LLM_TIMEOUT_S
    try:
        value = float(raw)
    except ValueError:
        return LLM_TIMEOUT_S
    if not math.isfinite(value) or not 0 < value <= _LLM_TIMEOUT_MAX_S:
        return LLM_TIMEOUT_S
    return value


# A disruptive autonomous action runs only when this many draws of the decision agree
# (D-1): the first, then the others at the model's default sampling. The same brute force
# drew a block at 0.80 on 21/10 and an isolation at 0.78 on 23/10.
DECISION_DRAWS = 3
_DECISION_DRAWS_MAX = 10


def decision_draws() -> int:
    """GLORFINDEL_DECISION_DRAWS: 3 when unset or empty; an integer in [2, 10] otherwise.
    Malformed, 1 or less, or above 10 → 0: every disruptive autonomous action is held
    (configuration fails closed, like the confidence threshold). One draw is no agreement."""
    import os
    raw = (os.environ.get("GLORFINDEL_DECISION_DRAWS") or "").strip()
    if not raw:
        return DECISION_DRAWS
    try:
        value = int(raw)
    except ValueError:
        return 0
    if not 2 <= value <= _DECISION_DRAWS_MAX:
        return 0
    return value


# Past the isolation's TTL, one ttl_exceeded card — never a release (Q1, reassert.ttl_alerts).
ISOLATION_TTL_H = 4.0


class TTLRefused(ValueError):
    """The isolation's TTL given is negative or unreadable (TTL1): `check-ttl` refuses it, the
    watch says it and keeps ISOLATION_TTL_H. Its text is the reason, ready to be said."""


def isolation_ttl_h(option: float | None = None) -> float:
    """The isolation's TTL in hours, read once for the watch and for `check-ttl` (TTL1).

    `option` (`check-ttl --ttl`) wins when it is given, 0 included; otherwise
    GLORFINDEL_ISOLATION_TTL_H, 4 h when unset or empty. 0 means « escalate every isolation at
    once » (Jonathan, 14/11), by the option as by the variable. A negative value, or one that is not a
    number (unreadable, `nan`), raises TTLRefused with its reason — never a fallback here: what to do
    with a refused TTL is the caller's (refused by `check-ttl`, said by the watch, which keeps 4 h).

    Before, `check-ttl --ttl 0` was silently the variable or 4 h (`ttl or …`), a negative TTL
    escalated everything as 0 did, and an unreadable variable raised a ValueError that stopped the
    watch at its start."""
    import math
    import os
    if option is not None:
        value, said = option, f"--ttl {option:g}"
    else:
        raw = (os.environ.get("GLORFINDEL_ISOLATION_TTL_H") or "").strip()
        if not raw:
            return ISOLATION_TTL_H
        said = f"GLORFINDEL_ISOLATION_TTL_H={raw[:40]!r}"
        try:
            value = float(raw)
        except ValueError:
            raise TTLRefused(f"{said} : illisible, pas un nombre d'heures") from None
    if math.isnan(value):
        raise TTLRefused(f"{said} : illisible, pas un nombre d'heures")
    if value < 0:
        raise TTLRefused(f"{said} : négatif, refusé (0 escalade toutes les isolations tout de suite)")
    return value


def _flock(f, exclusive: bool) -> None:
    try:
        import fcntl
        fcntl.flock(f, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
    except (ImportError, OSError):
        pass


def _read_text(path: Path) -> str:
    """The config's text, under a shared lock: never half of an in-place write."""
    with open(path) as f:
        _flock(f, exclusive=False)
        return f.read()


def _write_atomic(path: Path, text: str, locked=None) -> None:
    """Temp file + os.replace: the watch never reads a half-written config (the War
    Room rewrites it — sixth review, S1).

    A file mounted on its own in a container — docker-compose mounts
    glorfindel-config.yaml alone — can't be replaced: a rename over a mount point fails
    with EBUSY (measured, seventh review U3: the War Room's mode change failed). Then it
    is written in place, under the exclusive lock `locked` the caller holds on it;
    readers take the shared one (_read_text), so none sees it half-written."""
    import errno
    import os
    import tempfile
    try:
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    except OSError:
        fd, tmp = None, None
    if fd is not None:
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp, path)
            return
        except OSError as exc:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            if exc.errno not in (errno.EBUSY, errno.EXDEV) or locked is None:
                raise
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    if locked is None:
        raise OSError(errno.EBUSY, f"{path} can't be replaced and isn't held for an in-place write")
    locked.seek(0)
    locked.write(text)
    locked.truncate()
    locked.flush()
    os.fsync(locked.fileno())


def edit_config(cfg_path: Path, op: dict, base: str | None = None, vms=None) -> dict:
    """CFG4 (#1129): apply one operation of the closed list (glorfindel/config_edit.py) to the file, in
    round trip — its comments and every other byte kept —, under one exclusive lock: two War Room
    requests don't lose each other's change. If the file was replaced while we waited for the lock
    (an atomic write on the host), read the new one. ``base``: the digest the caller read; the file
    changed since → refused, ``config_changed``. A file the strict reading refuses, or a result it
    would refuse, is never written (EditRefused). Returns the digests before and after, and the class
    of the change (glorfindel/config_class.py). CFG4b (#1136): ``loud`` counts the VMs really touched,
    by ``loud()`` (Q11), never the entries: ``vms``, the names the caller knows; None → the discovery's
    registry (``discovered_assets.json``). ``loud_said``: its sentence, « response disarmed on N VMs ». A
    list empty, or a registry absent or unreadable: the entries are counted, as CFG4, and the sentence says
    why (Jonathan, 24/11) — a registry emptied never silences a change en masse."""
    from glorfindel.config_class import classify, loud
    from glorfindel.config_edit import EditRefused, apply_change, digest
    import os
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        cfg_path.touch(exist_ok=True)
        f = open(cfg_path, "r+", encoding="utf-8")   # not "a+": every write there goes to the end; utf-8, the in-place write too
        try:
            _flock(f, exclusive=True)
            try:
                same = os.fstat(f.fileno()).st_ino == os.stat(cfg_path).st_ino
            except OSError:
                same = False
            if not same:
                continue
            f.seek(0)
            raw = f.buffer.read() if hasattr(f, "buffer") else f.read().encode("utf-8")
            if base is not None and digest(raw) != base:
                raise EditRefused("config_changed", f"{cfg_path} a changé depuis sa lecture : relire, puis redemander")
            text = raw.decode("utf-8")
            new = apply_change(text, op)
            said = classify(text, new)                   # before the write: a class that fails writes nothing
            names, unread = _discovered_names() if vms is None else (list(vms), "the list of VMs given is empty")
            said["loud_said"] = loud(text, new, names if names else None)
            if said["loud_said"] is not None and not names:
                said["loud_said"] += f" ({unread}: counted by entry)"
            said["loud"] = said["loud_said"] is not None
            if new != text:
                _write_atomic(cfg_path, new, locked=f)
            return {"before": digest(raw), "after": digest(new.encode("utf-8")), **said}
        finally:
            f.close()


def _discovered_names() -> tuple[list[str], str | None]:
    """CFG4b: the names of the VMs the discovery knows today, for the loud announcement (Q11), and why there
    are none: the registry absent, unreadable (AssetRegistry._load swallows every error: its entries are
    read here first, so one it could not load is told from a registry read with no VM), or empty."""
    import json
    from glorfindel import discovery
    path = discovery._CACHE_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [], "the discovery's registry is absent"
    except (OSError, ValueError):
        return [], "the discovery's registry could not be read"
    if not isinstance(raw, list):
        return [], "the discovery's registry could not be read"
    names = [a.name for a in discovery.AssetRegistry(path).all()]
    if raw and not names:
        return [], "the discovery's registry could not be read"
    return names, None if names else "the discovery lists no VM"


@dataclass
class DiscoveryConfig:
    enabled: bool = True
    interval_s: float = 1800.0   # 30 min default


@dataclass
class MonitoringBackendConfig:
    name: str
    type: str                    # "azure_monitor", "prometheus", ...
    workspace_id: str = ""       # LAW workspace GUID or Prometheus URL
    endpoint: str = ""
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)


@dataclass
class ActionBackendConfig:
    name: str
    type: str                    # "azure_backup_vault"
    vault_name: str = ""
    resource_group: str = ""
    # Staging storage account for Azure Backup IaaS restore (same region/subscription).
    # Namespaced per Celebrimbor instance → resolved from `make celebrimbor-output`, never
    # hardcoded. Empty → restore_from_backup raises a clear error rather than a stale name.
    restore_staging_storage: str = ""


def vm_name_matches(asset_name: str, pattern: str) -> bool:
    """AUC (#447): a VM's name against a pattern of the config (fnmatch), case ignored —
    Azure ignores it in a VM's name, and `fnmatch.fnmatch` keeps it on Linux: a VM the
    config wrote `VM-PROD-DB`, its state `vm-prod-db`, was not the config's VM."""
    return fnmatch.fnmatchcase(asset_name.lower(), pattern.lower())


@dataclass
class ExceptionConfig:
    """Opt-out rule: prevent a rule (or all rules) from being applied to an asset."""
    asset_pattern: str           # fnmatch pattern matched against VM name, case ignored (AUC)
    exclude_all: bool = False    # exclude from all rules
    exclude_rules: list[str] = field(default_factory=list)  # specific rule names
    # CFG2 (#1128): why the VM is set aside — optional, said on its card, in its audit line and the
    # Overview (glorfindel/exclusions.py); "" when the file gives none (written before CFG2).
    reason: str = ""

    def matches(self, asset_name: str) -> bool:
        return vm_name_matches(asset_name, self.asset_pattern)

    def excludes_rule(self, rule_name: str) -> bool:
        return self.exclude_all or rule_name in self.exclude_rules


# Autonomy modes — resolved per asset, defaults to the safest (human_only).
# full_auto is deferred: the mechanism resolves it but config validation refuses
# the value for now. Order of precedence: asset match > global default.
VALID_AUTONOMY_MODES = {"human_only", "non_disruptive"}
DEFERRED_AUTONOMY_MODES = {"full_auto"}
# AUC (#447): from the most prudent mode to the most permissive — two entries that name a VM
# alike (`VM-A` and `vm-a`, or two patterns as long) and disagree give the most prudent.
_MODE_PRUDENCE = {"human_only": 0, "non_disruptive": 1, "full_auto": 2}


def _most_prudent(rules: list[AutonomyRule]) -> str:
    return min(rules, key=lambda r: _MODE_PRUDENCE.get(r.mode, len(_MODE_PRUDENCE))).mode


@dataclass
class AutonomyRule:
    """An asset-scoped autonomy mode override (fnmatch, like ExceptionConfig; case ignored).

    `critical` (PRT2, #1160): the object is critical — its grave detections draw on the graves' reserve
    of the model's budget (glorfindel/model_budget.py), never held by the other buckets. Written by hand
    for now, read strictly: true or false, nothing else; no Azure tag, no other source."""
    match: str                   # fnmatch pattern matched against VM name, case ignored (AUC)
    mode: str

    def matches(self, asset_name: str) -> bool:
        return vm_name_matches(asset_name, self.match)

    critical: bool = False       # PRT2: a field after the method, its default kept — a dataclass all the same


@dataclass
class AutonomyConfig:
    """Per-asset autonomy policy.

    - human_only (default): nothing executes autonomously — every action, even
      reversible ones (isolate_vm/block/snapshot), is recommended and escalated.
    - non_disruptive: current behaviour — AUTONOMOUS_ACTIONS run, destructive gated.

    allow_destructive is a SEPARATE axis from the mode (Review 2026-06-10):
    delete_resource/wipe_storage are NEVER controlled by a mode. Empty = never
    autonomous, regardless of mode.
    """
    default: str = "human_only"
    assets: list[AutonomyRule] = field(default_factory=list)
    allow_destructive: list[str] = field(default_factory=list)

    def resolve(self, asset_name: str) -> str:
        """Resolve the autonomy mode for an asset. Most specific match > global default.

        Precedence: an exact match (pattern == asset_name, e.g. an entry written by
        the War Room dropdown) wins over any wildcard. Among wildcard matches, the
        longest pattern wins (proxy for specificity) — so a broad "vm-*" never
        shadows a targeted "vm-prod-db". Unknown assets fall back to the global
        default — never an accidental inheritance toward a more permissive mode.

        AUC (#447): names and patterns compared case ignored, as Azure compares a VM's
        name — a `human_only` entry written `VM-PROD-DB` holds `vm-prod-db` under a
        `non_disruptive` default. Entries tied (exact alike, or wildcards as long) that
        disagree give the most prudent mode, never the first listed.
        """
        name = asset_name.lower()
        exact = [r for r in self.assets if r.match.lower() == name]
        if exact:
            return _most_prudent(exact)
        matches = [r for r in self.assets if r.matches(asset_name)]
        if matches:
            longest = max(len(r.match) for r in matches)
            return _most_prudent([r for r in matches if len(r.match) == longest])
        return self.default

    def is_critical(self, asset_name: str) -> bool:
        """PRT2: an entry that names this VM — exactly or by its pattern, case ignored — says
        `critical: true`. Any one is enough: criticality only tightens."""
        return any(r.critical and r.matches(asset_name) for r in self.assets)

    def critical_count(self) -> int:
        """PRT2: the critical objects — the entries that say `critical: true`, one per name or pattern
        (case ignored) — which the graves' reserve of the model's budget is proportional to."""
        return len({r.match.lower() for r in self.assets if r.critical})


@dataclass
class IsolationConfig:
    """How Glorfindel isolates a VM.

    quarantine_nsg: a NIC with no NSG of its own gets Glorfindel's quarantine NSG
      (deny-all in and out) attached for the time of the isolation — no customer rule
      touched, nothing evaluated before it, untouched by a `terraform apply` (lot L4).
      False → the deny goes into the subnet's NSG, as before.
    quarantine_rg: resource group where Glorfindel creates its quarantine NSGs (one per
      region, on first need). Empty → the isolated VM's resource group.
    """
    quarantine_nsg: bool = True
    quarantine_rg: str = ""
    # CIDRs allowed IN to an isolated VM (Bastion subnet, investigation jump host),
    # before the quarantine's deny: isolate while keeping investigation access. Only
    # what validate_forensic_sources keeps is ever applied.
    forensic_sources: list[str] = field(default_factory=list)
    # TCP ports those sources reach (SSH, RDP) — not every port of a compromised VM.
    forensic_ports: list[int] = field(default_factory=lambda: [22, 3389])


# The widest forensic source accepted: a Bastion subnet (/26), a jump host (/32), a
# small management subnet (/24). Wider would let a whole network into an isolated VM.
_FORENSIC_MAX_ADDRESSES = 256


def validate_forensic_sources(values) -> tuple[list[str], list[tuple[str, str]]]:
    """(accepted CIDRs in canonical form, [(rejected value, why)]).

    The value became an NSG allow before the quarantine's deny AND part of the shell
    filter of the session drain (fourth review, Q5): a service tag (`Internet`), `*`,
    a /0 or a stray quote opened the isolated VM to everyone, or broke the command.
    Only plain addresses and small prefixes pass, rewritten by `ipaddress`."""
    import ipaddress
    accepted: list[str] = []
    rejected: list[tuple[str, str]] = []
    for raw in values or []:
        text = str(raw).strip()
        try:
            net = ipaddress.ip_network(text, strict=False)
        except ValueError:
            rejected.append((text, "ni une adresse ni un préfixe CIDR (tags et * refusés)"))
            continue
        if net.num_addresses > _FORENSIC_MAX_ADDRESSES:
            rejected.append((text, f"préfixe trop large ({net.num_addresses} adresses, "
                                   f"{_FORENSIC_MAX_ADDRESSES} au plus)"))
        elif (net.is_loopback or net.is_link_local or net.is_multicast or net.is_reserved
              or net.network_address.is_unspecified
              or (net.version == 4 and net.overlaps(ipaddress.ip_network("0.0.0.0/8")))):
            rejected.append((text, "adresse réservée"))
        elif str(net) not in accepted:
            accepted.append(str(net))
    return accepted, rejected


def validate_never_block(values) -> tuple[list[str], list[tuple[str, str]]]:
    """(the never-block entries in canonical CIDR form, [(rejected value, why)]) (SEC2).

    An address or a prefix; a prefix that holds every address (/0) would turn blocking
    off altogether — that is a mode (`autonomy`), not a list, and it is refused."""
    import ipaddress
    accepted: list[str] = []
    rejected: list[tuple[str, str]] = []
    for raw in values or []:
        text = str(raw).strip()
        try:
            net = ipaddress.ip_network(text, strict=False)
        except ValueError:
            rejected.append((text, "ni une adresse ni un préfixe CIDR"))
            continue
        if net.prefixlen == 0:
            rejected.append((text, "toutes les adresses : couper les blocages se fait par le mode "
                                   "d'autonomie, pas par cette liste"))
        elif str(net) not in accepted:
            accepted.append(str(net))
    return accepted, rejected


def validate_forensic_ports(values) -> list[int]:
    """TCP ports, 1–65535. A single port written without a list (`forensic_ports: 22`)
    raised TypeError and made the whole config unreadable; `"22"` iterated as "2", "2"
    (sixth review, S1/S8). Anything else than a port number is a config error."""
    if values is None:
        return []
    items = values if isinstance(values, (list, tuple)) else [values]
    ports: list[int] = []
    for raw in items:
        if isinstance(raw, bool):
            raise ValueError(f"isolation.forensic_ports : {raw!r} n'est pas un port")
        try:
            port = int(str(raw).strip())
        except ValueError:
            raise ValueError(f"isolation.forensic_ports : {raw!r} n'est pas un port") from None
        if not 0 < port < 65536:
            raise ValueError(f"isolation.forensic_ports : {port} hors de 1–65535")
        if port not in ports:
            ports.append(port)
    return ports


# ADM1 (#284): an account name as sudo writes it before « : » — a Linux login, or an
# Entra ID one (`user@domain`). No glob: `admin*` would trust `admin_evil` in silence.
_ACCOUNT_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.@-]{0,255}\$?")


@dataclass
class ExpectedAdmins:
    """ADM1 (#284): the accounts whose sudo to root is expected on the VMs `match` names
    (fnmatch, like `autonomy.assets`; case ignored, as Azure ignores it in a VM's name)."""
    match: str
    accounts: list[str] = field(default_factory=list)
    # COR1 (#407): where their SSH sessions are expected to come from (CIDR ranges, a bastion
    # is a range). A root shell is set aside only if every session comes from one of them.
    origins: list[str] = field(default_factory=list)
    # SEC2b (#1089): the named networks of `origins` that name an object of the client's Azure (a
    # VNet, a subnet), resolved by the discovery — read fresh only, never from a list too old.
    origin_objects: list = field(default_factory=list)

    def matches(self, asset_name: str) -> bool:
        return vm_name_matches(asset_name, self.match)


@dataclass
class ExpectedSudoConfig:
    """ADM1 (#284): the sudo the administrators are expected to run. A sudo to root of an
    account expected on its VM opens no card — unless its command is sensitive (the shipped
    list, `glorfindel.expected_sudo.SENSITIVE_SHIPPED`, plus `sensitive_commands`: texts found
    in the command line, case ignored). Empty: every sudo is a card, as before."""
    admins: list[ExpectedAdmins] = field(default_factory=list)
    sensitive_commands: list[str] = field(default_factory=list)
    # COR2 (#427): the source outside the VM that confirms each SSH session behind a root shell
    # set aside by its origin — `bastion` (Azure Bastion's audit logs) or `flows` (the VNet's
    # flow logs); `none`: COR1, the origin read in the VM only (`glorfindel.correlation.PROOFS`).
    origin_proof: str = "none"

    def accounts_for(self, asset_name: str) -> frozenset[str]:
        """The accounts expected on this VM: every entry that names it, together."""
        if not asset_name:
            return frozenset()
        return frozenset(a for e in self.admins if e.matches(asset_name) for a in e.accounts)

    def origins_for(self, asset_name: str, account: str) -> tuple[str, ...]:
        """COR1: the origins declared for this account on this VM — every entry that names both,
        together; empty when none declares any (a root shell then stays a card, ADM1)."""
        if not asset_name:
            return ()
        named = [e for e in self.admins if e.matches(asset_name) and account in e.accounts]
        objects = [n for e in named for n in e.origin_objects]
        resolved: list[str] = []
        if objects:   # SEC2b: an object unresolved, or a list too old, expects nothing from it
            from glorfindel.client_network import load
            resolved = load().origins_of(objects)
        return tuple(dict.fromkeys([o for e in named for o in e.origins] + resolved))


@dataclass
class MemoryConfig:
    """SEC17 (V-12): the memory of past cycles. ``max_age_days``: a cycle stored longer ago is no
    precedent — left out of the search (glorfindel/memory.py), never erased. 90 days by default,
    at most ten years."""
    max_age_days: float = 90.0


@dataclass
class GlorfindelConfig:
    monitoring_backends: list[MonitoringBackendConfig] = field(default_factory=list)
    action_backends: list[ActionBackendConfig] = field(default_factory=list)
    exceptions: list[ExceptionConfig] = field(default_factory=list)
    autonomy: AutonomyConfig = field(default_factory=AutonomyConfig)
    isolation: IsolationConfig = field(default_factory=IsolationConfig)
    # Addresses never blocked, on top of the shipped ones (SEC2,
    # glorfindel.response.policy.NEVER_BLOCK_SHIPPED): canonical CIDRs.
    never_block: list[str] = field(default_factory=list)
    # ADM1 (#284): the administrators' expected sudo, per VM or pattern of VMs.
    expected_sudo: ExpectedSudoConfig = field(default_factory=ExpectedSudoConfig)
    # SEC2b (#1089): the named networks (glorfindel/config_networks.py), name → NamedNetwork; the
    # names `never_block` cites (their ranges in `never_block` itself, an object's resolved by the
    # discovery); where each name is cited; what is said without refusing the file.
    networks: dict = field(default_factory=dict)
    never_block_names: list[str] = field(default_factory=list)
    network_uses: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    # SEC2c (#1107): `network_zones.exposed` (glorfindel/config_zones.py) — its ranges (a named network's
    # too), and the names it cites (an object's range resolved by the discovery).
    exposed: list[str] = field(default_factory=list)
    exposed_names: list[str] = field(default_factory=list)
    # SEC2d (#1147): `network_zones.expected_origins` — its ranges and the names it cites, read whatever the
    # switch of the lateral movement (glorfindel/lateral.py); in force only while it is on.
    expected_origins: list[str] = field(default_factory=list)
    expected_names: list[str] = field(default_factory=list)
    # SEC17 (V-12): how old a past cycle may be to be given as a precedent.
    memory: MemoryConfig = field(default_factory=MemoryConfig)

    def monitoring_backend(self, name: str) -> MonitoringBackendConfig | None:
        return next((b for b in self.monitoring_backends if b.name == name), None)

    def action_backend(self, name: str) -> ActionBackendConfig | None:
        return next((b for b in self.action_backends if b.name == name), None)

    def backup_vault(self) -> ActionBackendConfig | None:
        return next(
            (b for b in self.action_backends if b.type == "azure_backup_vault"),
            None,
        )

    def is_excluded(self, asset_name: str, rule_name: str) -> bool:
        """Return True if the asset should NOT be monitored by the given rule."""
        return any(
            exc.matches(asset_name) and exc.excludes_rule(rule_name)
            for exc in self.exceptions
        )


def memory_max_age_days(path: str | Path | None = None) -> float:
    """SEC17 (V-12): the memory's age bound, from the config — its default (90 days) when there
    is no config, or one the watch refuses (it does not start on it, A3)."""
    try:
        return load_glorfindel_config(path).memory.max_age_days
    except Exception:
        return MemoryConfig().max_age_days


NO_VAULT_MSG = ("Aucun coffre de sauvegarde configuré : action_backends (type "
                "azure_backup_vault) dans glorfindel-config.yaml, GLORFINDEL_BACKUP_VAULT, "
                "ou --vault.")


def resolve_backup_vault(explicit: str | None = None) -> tuple[str, str, str]:
    """(vault, vault_rg, staging_storage). Name: explicit (--vault) > config > env
    GLORFINDEL_BACKUP_VAULT > "" — never the retired "rsv-annatar", which sent a restore
    to a vault that no longer exists (third review, details). The vault's resource group
    and the staging account come from config (a central vault lives outside the VM's
    resource group)."""
    import os
    vault, vault_rg, staging = (explicit or "").strip(), "", ""
    try:
        rsv = load_glorfindel_config().backup_vault()
    except Exception:
        rsv = None
    if rsv:
        vault = vault or rsv.vault_name or ""
        vault_rg = rsv.resource_group or ""
        staging = rsv.restore_staging_storage or ""
    vault = vault or os.environ.get("GLORFINDEL_BACKUP_VAULT", "").strip()
    return vault, vault_rg, staging


def load_glorfindel_config(path: str | Path | None = None) -> GlorfindelConfig:
    """Load infrastructure config from glorfindel-config.yaml.

    If path is None, searches default locations. Returns empty config if not found.
    A file that is there but badly written — a key nobody reads, a value of the wrong
    type, `"false"` in quotes — raises ConfigError naming every problem (A3).
    """
    if yaml is None:
        raise ImportError("PyYAML is required: pip install pyyaml")

    if path is not None:
        candidates = [Path(path)]
    else:
        candidates = _DEFAULT_PATHS

    cfg_path = next((p for p in candidates if p.exists()), None)
    if cfg_path is None:
        return GlorfindelConfig()
    try:
        return _parse_config(yaml.safe_load(_read_text(cfg_path)) or {})
    except ConfigError as exc:
        raise ConfigError(f"{cfg_path} refusé — {exc}") from exc
    except Exception as exc:
        raise ConfigError(f"{cfg_path} : {type(exc).__name__}: {exc}") from exc


# ── Strict validation (A3) ────────────────────────────────────────────────────────
# A key nobody reads was ignored and its default stood in silently: `quarantaine_nsg:
# false` left the quarantine on. A value of the wrong type was read by Python's rules:
# `exclude_all: "false"` is a non-empty string, true — the VM left every rule; a single
# `allow_destructive: "vm-*"` became the patterns v, m, - and *. Every key is known,
# every value has its type, and every problem is said, all at once.

_SECTIONS = {
    "monitoring_backends": "list", "action_backends": "list", "exceptions": "list",
    "autonomy": "table", "isolation": "table", "never_block": "list",
    "expected_sudo": "table", "memory": "table", "networks": "table", "network_zones": "table",
}
_MONITORING_KEYS = ("name", "type", "workspace_id", "endpoint", "discovery")
_DISCOVERY_KEYS = ("enabled", "interval_s")
_ACTION_KEYS = ("name", "type", "vault_name", "resource_group", "restore_staging_storage")
_EXCEPTION_KEYS = ("asset_pattern", "exclude_all", "exclude_rules", "reason")
# CFG2 (#1128): a reason is one line the console shows — said whole on a card, never cut.
REASON_MAX = 200
_AUTONOMY_KEYS = ("default", "assets", "allow_destructive")
_AUTONOMY_ASSET_KEYS = ("match", "mode", "critical")
_ISOLATION_KEYS = ("quarantine_nsg", "quarantine_rg", "forensic_sources", "forensic_ports")
_EXPECTED_SUDO_KEYS = ("admins", "sensitive_commands", "origin_proof")
_EXPECTED_ADMIN_KEYS = ("match", "accounts", "origins")
_MEMORY_KEYS = ("max_age_days",)
# The backend types something reads (discovery.py, detection_rules.py, backup_vault()):
# `type: azure_monitr` was a backend nothing used, in silence. A new type is added here.
_MONITORING_TYPES = ("azure_monitor", "prometheus")
_ACTION_TYPES = ("azure_backup_vault",)


def _shown(value) -> str:
    return f'"{value}"' if isinstance(value, str) else str(value)


class _Checker:
    """Reads one table of the file, noting every problem instead of stopping at the first."""

    def __init__(self) -> None:
        self.problems: list[str] = []

    def bad(self, where: str, what: str) -> None:
        self.problems.append(f"{where} : {what}")

    def keys(self, raw: dict, where: str, allowed) -> None:
        import difflib
        for k in raw:
            if k in allowed:
                continue
            close = difflib.get_close_matches(str(k), list(allowed), n=1, cutoff=0.6)
            hint = f" — vouliez-vous dire « {close[0]} » ?" if close else ""
            self.bad(f"{where}{'.' if where else ''}{k}",
                     f"clé inconnue, que rien ne lit{hint} (clés possibles : {', '.join(allowed)})")

    def table(self, value, where: str) -> dict:
        if value is None:
            return {}
        if not isinstance(value, dict):
            self.bad(where, f"une table (clé: valeur) est attendue, pas {_shown(value)}")
            return {}
        return value

    def items(self, value, where: str) -> list:
        if value is None:
            return []
        if not isinstance(value, list):
            self.bad(where, f"une liste (- élément) est attendue, pas {_shown(value)}")
            return []
        return value

    def text(self, raw: dict, k: str, where: str, default: str = "", required: bool = False) -> str:
        value = raw.get(k)
        if value is None:
            if required:
                self.bad(f"{where}.{k}", "obligatoire")
            return default
        if not isinstance(value, str):
            self.bad(f"{where}.{k}", f"un texte est attendu, pas {_shown(value)}"
                     + (" (entre guillemets si c'est voulu)" if isinstance(value, (bool, int, float)) else ""))
            return default
        if required and not value.strip():
            self.bad(f"{where}.{k}", "obligatoire, et vide ici")
        return value

    def choice(self, raw: dict, k: str, where: str, allowed, default: str) -> str:
        """A text among `allowed` — a near miss is named."""
        import difflib
        value = self.text(raw, k, where, default=default)
        if raw.get(k) is None or not isinstance(raw.get(k), str) or value in allowed:
            return value
        close = difflib.get_close_matches(value, list(allowed), n=1, cutoff=0.6)
        hint = f" — vouliez-vous dire « {close[0]} » ?" if close else ""
        self.bad(f"{where}.{k}", f"type inconnu {_shown(value)}{hint} (types possibles : {', '.join(allowed)})")
        return default

    def flag(self, raw: dict, k: str, where: str, default: bool) -> bool:
        value = raw.get(k)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in ("true", "false", "yes", "no", "on", "off"):
            self.bad(f"{where}.{k}", f"{_shown(value)} est un texte entre guillemets, pas un booléen — "
                                     f"écrire {value.strip().lower()} sans guillemets")
        else:
            self.bad(f"{where}.{k}", f"true ou false est attendu, pas {_shown(value)}")
        return default

    def seconds(self, raw: dict, k: str, where: str, default: float) -> float:
        import math
        value = raw.get(k)
        if value is None:
            return default
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            self.bad(f"{where}.{k}", f"un nombre de secondes est attendu (sans guillemets ni unité), "
                                     f"pas {_shown(value)}")
            return default
        if not math.isfinite(value) or value <= 0:
            self.bad(f"{where}.{k}", f"un nombre de secondes positif est attendu, pas {value}")
            return default
        return float(value)

    def days(self, raw: dict, k: str, where: str, default: float, ceiling: float) -> float:
        """A number of days: finite, positive, at most ``ceiling`` (SEC17)."""
        import math
        value = raw.get(k)
        if value is None:
            return default
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            self.bad(f"{where}.{k}", f"un nombre de jours est attendu (sans guillemets ni unité), "
                                     f"pas {_shown(value)}")
            return default
        if not math.isfinite(value) or not 0 < value <= ceiling:
            self.bad(f"{where}.{k}", f"un nombre de jours entre 0 (exclu) et {ceiling:g} est attendu, "
                                     f"pas {value}")
            return default
        return float(value)

    def texts(self, raw: dict, k: str, where: str) -> list[str]:
        value = raw.get(k)
        if value is None:
            return []
        if not isinstance(value, list):
            self.bad(f"{where}.{k}", f"une liste est attendue, pas {_shown(value)}"
                     + (f" — écrire [{value}]" if isinstance(value, str) else ""))
            return []
        out = []
        for i, item in enumerate(value):
            if isinstance(item, str):
                out.append(item)
            else:
                self.bad(f"{where}.{k}[{i}]", f"un texte est attendu, pas {_shown(item)}")
        return out


def _check_reason(raw: dict, where: str, check: _Checker) -> str:
    """CFG2 (#1128): `exceptions[].reason`, optional — a text of one line, at most REASON_MAX
    characters: a number, a list, a line break or a control character refuses the file, as every
    other key does (A3)."""
    import unicodedata
    reason = check.text(raw, "reason", where)
    # Control characters (U+0085 too) and the line and paragraph separators (U+2028, U+2029).
    if any(unicodedata.category(c) in ("Cc", "Zl", "Zp") for c in reason):
        check.bad(f"{where}.reason", "une seule ligne est attendue, sans caractère de contrôle")
        return ""
    if len(reason) > REASON_MAX:
        check.bad(f"{where}.reason", f"{len(reason)} caractères, au plus {REASON_MAX}")
        return ""
    return reason.strip()


def _parse_config(data: dict) -> GlorfindelConfig:
    if not isinstance(data, dict):
        raise ConfigError("le fichier ne contient pas une table YAML")
    check = _Checker()
    check.keys(data, "", tuple(_SECTIONS))
    sections = {name: (check.items if kind == "list" else check.table)(data.get(name), name)
                for name, kind in _SECTIONS.items()}

    monitoring_backends = []
    for i, b in enumerate(sections["monitoring_backends"]):
        where = f"monitoring_backends[{i}]"
        if not isinstance(b, dict):
            check.bad(where, f"une table (name, type, workspace_id…) est attendue, pas {_shown(b)}")
            continue
        check.keys(b, where, _MONITORING_KEYS)
        disc_raw = check.table(b.get("discovery"), f"{where}.discovery")
        check.keys(disc_raw, f"{where}.discovery", _DISCOVERY_KEYS)
        monitoring_backends.append(MonitoringBackendConfig(
            name=check.text(b, "name", where, required=True),
            type=check.choice(b, "type", where, _MONITORING_TYPES, default="azure_monitor"),
            workspace_id=check.text(b, "workspace_id", where),
            endpoint=check.text(b, "endpoint", where),
            discovery=DiscoveryConfig(
                enabled=check.flag(disc_raw, "enabled", f"{where}.discovery", True),
                interval_s=check.seconds(disc_raw, "interval_s", f"{where}.discovery", 1800.0),
            ),
        ))

    action_backends = []
    for i, b in enumerate(sections["action_backends"]):
        where = f"action_backends[{i}]"
        if not isinstance(b, dict):
            check.bad(where, f"une table (name, type, vault_name…) est attendue, pas {_shown(b)}")
            continue
        check.keys(b, where, _ACTION_KEYS)
        action_backends.append(ActionBackendConfig(
            name=check.text(b, "name", where, required=True),
            type=check.choice(b, "type", where, _ACTION_TYPES, default="azure_backup_vault"),
            vault_name=check.text(b, "vault_name", where),
            resource_group=check.text(b, "resource_group", where),
            restore_staging_storage=check.text(b, "restore_staging_storage", where),
        ))

    exceptions = []
    for i, e in enumerate(sections["exceptions"]):
        where = f"exceptions[{i}]"
        if not isinstance(e, dict):
            check.bad(where, f"une table (asset_pattern, exclude_all, exclude_rules, reason) est attendue, pas {_shown(e)}")
            continue
        check.keys(e, where, _EXCEPTION_KEYS)
        exceptions.append(ExceptionConfig(
            asset_pattern=check.text(e, "asset_pattern", where, required=True),
            exclude_all=check.flag(e, "exclude_all", where, False),
            exclude_rules=check.texts(e, "exclude_rules", where),
            reason=_check_reason(e, where, check),
        ))

    autonomy = _check_autonomy(sections["autonomy"], check)

    iso = sections["isolation"]
    check.keys(iso, "isolation", _ISOLATION_KEYS)
    try:
        ports = validate_forensic_ports(iso.get("forensic_ports", [22, 3389]))
    except ValueError as exc:
        check.problems.append(str(exc))
        ports = []
    isolation = IsolationConfig(
        quarantine_nsg=check.flag(iso, "quarantine_nsg", "isolation", True),
        quarantine_rg=check.text(iso, "quarantine_rg", "isolation"),
        forensic_sources=check.texts(iso, "forensic_sources", "isolation"),
        forensic_ports=ports,
    )

    from glorfindel.config_networks import check_networks, unused_notes
    networks = check_networks(sections["networks"], check)
    uses: dict[str, list[str]] = {}
    never_block, never_block_names = _check_never_block(sections["never_block"], networks, uses, check)
    expected_sudo = _check_expected_sudo(sections["expected_sudo"], check, networks, uses)
    from glorfindel.config_zones import check_zones
    exposed, exposed_names, expected_origins, expected_names = check_zones(
        sections["network_zones"], networks, uses, check)

    # SEC17 (V-12): the age bound of the memory, read as strictly as the rest.
    from glorfindel.memory import DEFAULT_MAX_AGE_DAYS, MAX_AGE_CEILING_DAYS
    mem = sections["memory"]
    check.keys(mem, "memory", _MEMORY_KEYS)
    memory = MemoryConfig(max_age_days=check.days(mem, "max_age_days", "memory", DEFAULT_MAX_AGE_DAYS,
                                                  MAX_AGE_CEILING_DAYS))

    if check.problems:
        n = len(check.problems)
        raise ConfigError(f"{n} problème{'s' if n > 1 else ''} :\n  - " + "\n  - ".join(check.problems))
    return GlorfindelConfig(
        monitoring_backends=monitoring_backends,
        action_backends=action_backends,
        exceptions=exceptions,
        autonomy=autonomy,
        isolation=isolation,
        never_block=never_block,
        expected_sudo=expected_sudo,
        memory=memory,
        networks=networks,
        never_block_names=never_block_names,
        network_uses=uses,
        notes=unused_notes(networks, uses),
        exposed=exposed,
        exposed_names=exposed_names,
        expected_origins=expected_origins,
        expected_names=expected_names,
    )


def _check_never_block(items: list, networks: dict, uses: dict, check: _Checker) -> tuple[list[str], list[str]]:
    """SEC2: `never_block`, each an address, a prefix, or (SEC2b) a named network of `networks` —
    its ranges added to the list, an object's name kept for the discovery to resolve."""
    from glorfindel.config_networks import cite
    never_block: list[str] = []
    names: list[str] = []
    for i, item in enumerate(items):
        if not isinstance(item, str):
            check.bad(f"never_block[{i}]", f"une adresse ou un préfixe (texte) est attendu, pas {_shown(item)}")
            continue
        accepted, rejected = validate_never_block([item])
        never_block += [a for a in accepted if a not in never_block]
        net, unknown = cite(item.strip(), networks) if rejected else (None, "")
        if net is not None:
            names += [net.name] if net.name not in names else []
            never_block += [c for c in net.cidrs if c not in never_block]
            uses.setdefault(net.name, []).append("never_block")
            continue
        for value, why in rejected:
            check.bad(f"never_block[{i}]", f"{_shown(value)} : {why}" + (f" ; {unknown}" if unknown else ""))
    return never_block, names


def _check_expected_sudo(raw: dict, check: _Checker, networks: dict | None = None,
                         uses: dict | None = None) -> ExpectedSudoConfig:
    """ADM1 (#284), read as strictly as the rest (A3): a form nobody reads refuses the file —
    the watch does not start on it, so nothing is ever excluded on a list half read."""
    where = "expected_sudo"
    check.keys(raw, where, _EXPECTED_SUDO_KEYS)
    admins: list[ExpectedAdmins] = []
    for i, a in enumerate(check.items(raw.get("admins"), f"{where}.admins")):
        at = f"{where}.admins[{i}]"
        if not isinstance(a, dict):
            check.bad(at, f"une table (match, accounts) est attendue, pas {_shown(a)}")
            continue
        check.keys(a, at, _EXPECTED_ADMIN_KEYS)
        match = check.text(a, "match", at, required=True)
        if a.get("accounts") is None:
            check.bad(f"{at}.accounts", "obligatoire : la liste des comptes attendus sur ces VMs")
            continue
        accounts = check.texts(a, "accounts", at)
        if a["accounts"] == []:
            check.bad(f"{at}.accounts", "au moins un compte — une liste vide n'attend personne")
        for j, name in enumerate(accounts):
            if not _ACCOUNT_RE.fullmatch(name):
                check.bad(f"{at}.accounts[{j}]",
                          f"{_shown(name)} n'est pas un nom de compte (lettres, chiffres, « _ . @ - », "
                          f"sans motif : un compte s'écrit en entier)")
        origins, objects = _check_origins(a, at, check, networks or {}, {} if uses is None else uses)
        admins.append(ExpectedAdmins(match=match, accounts=accounts, origins=origins, origin_objects=objects))
    sensitive: list[str] = []
    for j, text in enumerate(check.texts(raw, "sensitive_commands", where)):
        if text.strip():
            sensitive.append(text.strip())
        else:
            check.bad(f"{where}.sensitive_commands[{j}]", "un texte vide est refusé (il serait dans toute commande)")
    return ExpectedSudoConfig(admins=admins, sensitive_commands=sensitive,
                              origin_proof=_check_origin_proof(raw, admins, check))


def _check_origin_proof(raw: dict, admins: list[ExpectedAdmins], check: _Checker) -> str:
    """COR2 (#427): `origin_proof`, one of `glorfindel.correlation.PROOFS`; a source with no
    `origins` to confirm is a key nobody reads — refused, like the rest (A3)."""
    from glorfindel.correlation import PROOFS
    where = "expected_sudo.origin_proof"
    value = check.text(raw, "origin_proof", "expected_sudo", default="none")
    if raw.get("origin_proof") is None or not isinstance(raw.get("origin_proof"), str):
        return "none"
    if value not in PROOFS:
        check.bad(where, f"{_shown(value)} : une source parmi {', '.join(PROOFS)}")
        return "none"
    if value != "none" and not any(a.origins or a.origin_objects for a in admins):
        check.bad(where, f"{value} sans aucune entrée qui déclare origins : rien à confirmer — "
                         "déclarer origins, ou omettre la clé")
    return value


def _check_origins(raw: dict, where: str, check: _Checker, networks: dict,
                   uses: dict) -> tuple[list[str], list]:
    """COR1 (#407): `origins`, each a CIDR range or an address (`glorfindel.correlation.origin`) —
    or (SEC2b) a named network: its ranges added, an object kept for the discovery to resolve."""
    from glorfindel.config_networks import cite
    from glorfindel.correlation import origin
    if raw.get("origins") == []:
        check.bad(f"{where}.origins", "une liste vide n'attend aucune origine — omettre la clé")
    out: list[str] = []
    objects: list = []
    for j, text in enumerate(check.texts(raw, "origins", where)):
        net, why = origin(text)
        named, unknown = cite(text.strip(), networks) if why else (None, "")
        if named is not None:
            uses.setdefault(named.name, []).append(f"{where}.origins")
            out += [c for c in named.cidrs if c not in out]
            objects += [named] if named.is_object and named not in objects else []
        elif why:
            check.bad(f"{where}.origins[{j}]", f"{_shown(text)} : {why}" + (f" ; {unknown}" if unknown else ""))
        elif net not in out:
            out.append(net)
    return out, objects


def _validate_mode(mode: str, where: str) -> str:
    """Validate an autonomy mode value, raising a clear error for refused values."""
    if mode in VALID_AUTONOMY_MODES:
        return mode
    if mode in DEFERRED_AUTONOMY_MODES:
        raise ValueError(
            f"Autonomy mode '{mode}' ({where}) is not available yet — it is deferred. "
            f"Use one of {sorted(VALID_AUTONOMY_MODES)}."
        )
    raise ValueError(
        f"Unknown autonomy mode '{mode}' ({where}). "
        f"Valid modes: {sorted(VALID_AUTONOMY_MODES)}."
    )


def _check_autonomy(raw: dict, check: _Checker) -> AutonomyConfig:
    check.keys(raw, "autonomy", _AUTONOMY_KEYS)

    def mode(value, where: str) -> str | None:
        if not isinstance(value, str):
            check.bad(where, f"un mode (texte) est attendu, pas {_shown(value)}")
            return None
        try:
            return _validate_mode(value, where=where)
        except ValueError as exc:
            check.problems.append(str(exc))
            return None

    default = mode(raw.get("default", "human_only"), "autonomy.default") or "human_only"
    assets = []
    for i, a in enumerate(check.items(raw.get("assets"), "autonomy.assets")):
        where = f"autonomy.assets[{i}]"
        if not isinstance(a, dict):
            check.bad(where, f"une table (match, mode, critical) est attendue, pas {_shown(a)}")
            continue
        check.keys(a, where, _AUTONOMY_ASSET_KEYS)
        match = check.text(a, "match", where, required=True)
        if "mode" not in a:
            check.bad(f"{where}.mode", "obligatoire")
            continue
        m = mode(a["mode"], f"autonomy.assets[match={match or '?'}]")
        # PRT2 (#1160): true or false without quotes — a text, a number, a key left empty: said, refused.
        critical = check.flag(a, "critical", where, False)
        if "critical" in a and a["critical"] is None:
            check.bad(f"{where}.critical", "true ou false est attendu, et la clé est vide ici")
        if m is not None:
            assets.append(AutonomyRule(match=match, mode=m, critical=critical))
    return AutonomyConfig(
        default=default,
        assets=assets,
        allow_destructive=check.texts(raw, "allow_destructive", "autonomy"),
    )


def _parse_autonomy(raw: dict) -> AutonomyConfig:
    """Parse + validate the autonomy section. Empty/absent → safe defaults."""
    check = _Checker()
    autonomy = _check_autonomy(check.table(raw, "autonomy"), check)
    if check.problems:
        raise ConfigError("\n".join(check.problems))
    return autonomy


def set_default_mode(mode: str, path: str | Path | None = None) -> str:
    """Set the global default autonomy mode and persist to glorfindel-config.yaml.

    Backend for the War Room Config panel global dropdown. Validates the mode
    (refuses full_auto / unknown), updates ``autonomy.default``, and writes the
    file back. Returns the resolved path.
    """
    if yaml is None:
        raise ImportError("PyYAML is required: pip install pyyaml")
    _validate_mode(mode, where="set_default_mode()")

    if path is not None:
        cfg_path = Path(path)
    else:
        cfg_path = next((p for p in _DEFAULT_PATHS if p.exists()), _DEFAULT_PATHS[0])

    edit_config(cfg_path, {"op": "set_default_mode", "args": {"mode": mode}})
    return str(cfg_path)


def set_asset_mode(asset_name: str, mode: str, path: str | Path | None = None) -> str:
    """Set the autonomy mode for a single asset and persist to glorfindel-config.yaml.

    Backend for the War Room mode selector / change-mode endpoint. Validates the
    mode (refuses full_auto / unknown), upserts an exact-match `autonomy.assets`
    entry for asset_name, and writes the file back. Returns the resolved path.
    Every entry that names it exactly, case ignored (AUC: `VM-A` for `vm-a`), takes
    the mode, its spelling kept — one left behind would hold the VM in its own.

    CFG4 (#1129): written in round trip (glorfindel/config_edit.py) — the file's comments and every
    other entry kept to the byte; an exact name only (a pattern is refused); a file the strict reading
    refuses is never rewritten.
    """
    if yaml is None:
        raise ImportError("PyYAML is required: pip install pyyaml")
    _validate_mode(mode, where=f"set_asset_mode({asset_name})")

    if path is not None:
        cfg_path = Path(path)
    else:
        cfg_path = next((p for p in _DEFAULT_PATHS if p.exists()), _DEFAULT_PATHS[0])

    edit_config(cfg_path, {"op": "set_mode", "args": {"vm": asset_name, "mode": mode}})
    return str(cfg_path)
