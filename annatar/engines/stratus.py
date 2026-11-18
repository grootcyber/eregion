"""Stratus Red Team adapter (R2): invoke a PINNED Stratus binary by technique id to drive the
warmup → detonate → revert → cleanup cycle on the enrolled bench — no home-grown offensive
logic. The adapter never writes an attack: it resolves a technique id against a CLOSED
allow-list (the catalog's ``engine: stratus`` entries) and, for a resolved technique, hands the
runner the exact argv of each phase of Stratus's own cycle. An injector runs those phases from
an armed Orodruin, every phase journaled and capped by the contract
(``annatar/executors/stratus_host.py``).

Where the Atomic adapter (``annatar/engines/atomic.py``) runs a shell test inside a target VM,
Stratus attacks the Azure control plane: each technique provisions its own prerequisites,
detonates against the cloud API and tears them down. Its activity shows in the Azure Activity
Log (detection lot AL1); the real bench run is ID1 (#281).

Fail closed, like the Atomic adapter:
  - a technique id not shaped ``azure.<tactic>.<name>`` is refused — we run only Azure
    control-plane techniques (an aws/gcp/kubernetes id, a path separator, an option-looking
    segment, never reach a process argv);
  - a technique id not on the catalog's closed allow-list is refused (the catalog is the
    contract; an id Stratus knows but the catalog does not is not ours to run);
  - the Stratus binary is checked against its sha256 in ``annatar/stratus/PIN`` at resolve time,
    and the injector (annatar/executors/stratus_host.py) re-checks it BEFORE EVERY phase (not
    only once per run): a binary that is not the pinned one, or one swapped mid-run, runs
    nothing. We pin the binary we exec; the upstream archive's published sha256 sits beside it
    as provenance (annatar/stratus/PIN);
  - the read-only Graph probe a technique declares is held to a GET of a Microsoft Graph read
    path — never a write — so verifying the initial state can only read the directory.

Orodruin has no Internet (docs/design/orodruin-contract.md). Stratus's ``warmup`` provisions
with Terraform, which would otherwise download the Terraform binary and the provider plugins.
Both are to be staged into the image and pinned (annatar/stratus/PIN) — not delivered yet (R2b,
#608): without the binary, ``resolve`` refuses. ``airgap_env`` points Stratus at them offline
(a run-scoped ``HOME`` with the pre-installed Terraform, a filesystem mirror of the providers
and the plugin cache), so once they are there ``terraform init`` never reaches the network.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

STRATUS_DIR = Path(__file__).resolve().parents[1] / "stratus"

# We run two Stratus platforms: ``azure`` (the Azure resource control plane) and ``entra-id``
# (the Entra ID directory plane, RID2) — never aws/gcp/kubernetes. A Stratus technique id is
# ``platform.tactic.name``, each of tactic/name a lower-case word of [a-z0-9] with '-' between
# inner words; the catalog's closed allow-list is still what a run is held to.
_TECHNIQUE_ID = re.compile(
    r"^(?:azure|entra-id)\.[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*$")

# The cycle, in order — Stratus's own verbs, mapped onto the injector interface
# (prepare, inject, revert, clean up). ``cleanup`` always runs last, whatever the rest did.
PHASES = ("warmup", "detonate", "revert", "cleanup")

# A PIN line: "#   <sha256>  <label>" (same shape as annatar/atomics/PIN).
_PIN_LINE = re.compile(r"^#\s+([0-9a-f]{64})\s+(\S+)\s*$")
# The label of the binary the adapter execs; the other PIN lines are provenance / staging.
BINARY_LABEL = "stratus"

# A Microsoft Graph read path a probe may name: a v1.0 path (optionally with a query), fetched
# with GET only. The read-only guarantee is the GET method the executor hard-codes; this just
# pins Graph v1.0 and rejects anything malformed — no scheme, no host, no whitespace, no
# control character — so a probe can only read the directory.
_GRAPH_READ = re.compile(r"^/v1\.0/[A-Za-z0-9$()',./_=&?:@%+-]+$")


class StratusError(ValueError):
    """The technique cannot be run faithfully — refused before anything runs."""


@dataclass
class GraphProbe:
    """A read-only Microsoft Graph check of the initial state, run before ``detonate`` and after
    ``cleanup``. ``read`` is a Graph v1.0 path fetched with GET; ``expect_absent`` says the
    initial state is the target NOT existing (an empty listing) — the technique creates it, the
    cleanup removes it. Held to a read path, so the probe can only read."""

    name: str
    read: str
    expect_absent: bool = True

    def request(self) -> tuple[str, str]:
        """``(method, path)`` — always GET; raises if ``read`` is not a Graph read path."""
        if not _GRAPH_READ.fullmatch(self.read or ""):
            raise StratusError(
                f"graph probe {self.name!r}: {self.read!r} is not a Microsoft Graph v1.0 read "
                "path — a probe can only read the directory (GET), never change it"
            )
        return "GET", self.read

    def holds(self, body: dict) -> bool:
        """Does the initial state hold, given the Graph answer? An empty ``value`` list (or no
        object) means the target is absent; a non-empty one means it is present."""
        value = body.get("value") if isinstance(body, dict) else None
        present = bool(value) if isinstance(value, list) else bool(body)
        return (not present) if self.expect_absent else present


@dataclass
class StratusPhase:
    """One phase of the cycle, resolved to the exact process argv the injector will run."""

    name: str
    argv: list[str]
    label: str


@dataclass
class ResolvedTechnique:
    """One Stratus technique, resolved to the phases the runner will invoke and its read-only
    initial-state probe — ready to run, or refused."""

    technique_id: str
    tactic: str
    ttp: str
    name: str
    binary_digest: str
    phases: list[StratusPhase] = field(default_factory=list)
    graph_probe: GraphProbe | None = None

    def phase(self, name: str) -> StratusPhase:
        for p in self.phases:
            if p.name == name:
                return p
        raise StratusError(f"no phase {name!r} in {self.technique_id}")


def pinned_digests(stratus_dir: Path | None = None) -> dict[str, str]:
    """``{label: sha256}`` as ``PIN`` records them — ``{}`` when there is no PIN."""
    stratus_dir = stratus_dir or STRATUS_DIR
    try:
        text = (stratus_dir / "PIN").read_text(encoding="utf-8")
    except OSError:
        return {}
    return {m.group(2): m.group(1) for m in map(_PIN_LINE.match, text.splitlines()) if m}


def verify_binary(binary_path: str | Path, stratus_dir: Path | None = None) -> str:
    """The sha256 of the staged Stratus binary, checked against ``annatar/stratus/PIN`` at run
    time (SEC5): a binary that is not the pinned one refuses before any phase runs. Returns the
    digest."""
    path = Path(binary_path)
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise StratusError(
            f"the Stratus binary at {path} cannot be read ({type(e).__name__}) — not run; stage "
            "it into the Orodruin image (annatar/stratus/README.md)"
        ) from e
    pinned = pinned_digests(stratus_dir).get(BINARY_LABEL)
    if pinned is None:
        raise StratusError(
            f"annatar/stratus/PIN records no sha256 for the Stratus binary ({BINARY_LABEL!r}) "
            "— not run"
        )
    digest = hashlib.sha256(raw).hexdigest()
    if digest != pinned:
        raise StratusError(
            "the Stratus binary does not match its sha256 in annatar/stratus/PIN — not the "
            "pinned binary (v2.38.1); not run"
        )
    return digest


def _stratus_entries(catalog: dict | None = None) -> dict[str, dict]:
    """``{engine_ref: entry}`` for every catalog technique on the ``stratus`` engine — the
    closed allow-list. Loads the shared catalog when none is given (best effort: ``{}``)."""
    if catalog is None:
        from annatar.campaign.catalog import load_catalog
        catalog = load_catalog()
    out: dict[str, dict] = {}
    for entry in catalog.values():
        if entry.get("engine") == "stratus" and entry.get("engine_ref"):
            out[str(entry["engine_ref"])] = entry
    return out


def allowed_techniques(catalog: dict | None = None) -> set[str]:
    """The closed allow-list: the Stratus technique ids the catalog vouches for (fail closed on
    the rest)."""
    return set(_stratus_entries(catalog))


def _graph_probe(entry: dict) -> GraphProbe | None:
    """The entry's read-only initial-state probe, or ``None``. Its shape is held (fail closed):
    a mapping with a ``name`` and a ``read`` path, an optional boolean ``expect_absent``."""
    spec = entry.get("graph_probe")
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise StratusError("graph_probe must be a mapping (name, read, expect_absent)")
    name, read = spec.get("name"), spec.get("read")
    if not isinstance(name, str) or not name.strip():
        raise StratusError("graph_probe needs a name")
    if not isinstance(read, str) or not read.strip():
        raise StratusError(f"graph_probe {name!r} needs a Graph v1.0 read path")
    absent = spec.get("expect_absent", True)
    if not isinstance(absent, bool):
        raise StratusError(f"graph_probe {name!r}: expect_absent must be true or false")
    probe = GraphProbe(name=name.strip(), read=read.strip(), expect_absent=absent)
    probe.request()   # hold it to a read path now (fail closed before any run)
    return probe


def _lookup(technique_id: str, catalog: dict | None) -> tuple[str, dict]:
    """``(technique_id, entry)`` for a technique on the closed allow-list — the two fail-closed
    checks shared by ``resolve`` and ``describe``: the id is an Azure or Entra ID Stratus id, and
    it is one the catalog vouches for. Raises ``StratusError`` otherwise, before anything runs."""
    tid = (technique_id or "").strip()
    if not _TECHNIQUE_ID.fullmatch(tid):
        raise StratusError(
            f"technique id {technique_id!r} is not an 'azure.<tactic>.<name>' or "
            "'entra-id.<tactic>.<name>' Stratus id (lower-case, dot-separated) — refused, never "
            "sent to a process"
        )
    entries = _stratus_entries(catalog)
    entry = entries.get(tid)
    if entry is None:
        raise StratusError(
            f"technique {tid!r} is not on the catalog's closed allow-list "
            f"({sorted(entries) or '(none)'}) — not ours to run"
        )
    return tid, entry


def resolve(technique_id: str, *, binary_path: str | Path,
            stratus_dir: Path | None = None, catalog: dict | None = None) -> ResolvedTechnique:
    """Resolve a Stratus technique id to the phases to run — or refuse (fail closed).

    ``binary_path`` is the staged Stratus binary; its sha256 is checked against the PIN here,
    so a resolved technique already carries a verified binary."""
    tid, entry = _lookup(technique_id, catalog)
    digest = verify_binary(binary_path, stratus_dir)
    binary = str(binary_path)
    phases = [
        StratusPhase(name=name, argv=[binary, name, tid], label=f"stratus {name} {tid}")
        for name in PHASES
    ]
    return ResolvedTechnique(
        technique_id=tid,
        tactic=str(entry.get("tactic") or ""),
        ttp=str(entry.get("ttp") or ""),
        name=str(entry.get("name") or tid),
        binary_digest=digest,
        phases=phases,
        graph_probe=_graph_probe(entry),
    )


def describe(technique_id: str, *, catalog: dict | None = None) -> dict:
    """What a dry run shows, from the catalog alone — no binary check, no process. Raises
    ``StratusError`` if the id is not on the closed allow-list (the same fail-closed checks)."""
    tid, entry = _lookup(technique_id, catalog)
    return {
        "technique_id": tid,
        "ttp": str(entry.get("ttp") or ""),
        "tactic": str(entry.get("tactic") or ""),
        "name": str(entry.get("name") or tid),
        "phases": list(PHASES),
        "graph_probe": _graph_probe(entry),
    }


# Stratus's own override for the Terraform binary it runs (runner.go, EnvVarStratusTerraformBinaryPath):
# set it and Stratus uses that binary (when it is >= its TerraformVersion) instead of downloading one.
STRATUS_TERRAFORM_BINARY_ENV = "STRATUS_TERRAFORM_BINARY_PATH"


def airgap_env(run_home: str | Path, *, terraform_binary: str | Path | None = None,
               terraformrc: str | Path | None = None) -> dict[str, str]:
    """The offline environment Stratus runs its warmup Terraform with — no network.

    ``run_home`` is a WRITABLE, run-scoped ``HOME``: Stratus writes its state under
    ``<run_home>/.stratus-red-team/<technique>/`` (internal/state/state.go: ``os.UserHomeDir()`` +
    ``.stratus-red-team``), so it must be writable — the staged ``/opt/stratus/home`` is read-only
    in the image, which is why the executor builds a fresh HOME per run (R2BS).

    ``terraform_binary`` is the pinned Terraform staged read-only in the image. Passed as
    ``STRATUS_TERRAFORM_BINARY_PATH`` (runner.go), Stratus runs it — it is 1.3.10, its ``>=`` check
    passes — and never downloads one; the binary is only executed, so a read-only path is fine.
    ``terraformrc`` (``TF_CLI_CONFIG_FILE``, a filesystem mirror of the providers that excludes
    direct installs) keeps ``terraform init`` off the registry; Stratus leaves its plugin cache at
    its default under the writable HOME. Stratus passes the inherited environment through to
    Terraform (pkg/stratus/runner/terraform.go), so these reach ``terraform init``.

    These are overrides layered over the process environment (the Azure credentials of Orodruin's
    identity stay); the injector merges them (annatar/executors/stratus_host.py)."""
    env = {"HOME": str(run_home)}
    if terraform_binary is not None:
        env[STRATUS_TERRAFORM_BINARY_ENV] = str(terraform_binary)
    if terraformrc is not None:
        env["TF_CLI_CONFIG_FILE"] = str(terraformrc)
    return env


# The warmup's Terraform authenticates to Azure through the azurerm provider. On an armed Orodruin
# the hardened container carries ONLY the host's SYSTEM-ASSIGNED managed identity — no
# service-principal credential, no Azure CLI — so the provider, which otherwise finds no credential
# offline, must be told to use that identity: ``ARM_USE_MSI`` with the subscription and tenant (the
# IMDS token names neither). The azurerm provider reads these from its ``ARM_*`` schema (MSI1, #608).
ARM_USE_MSI_ENV = "ARM_USE_MSI"
ARM_SUBSCRIPTION_ENV = "ARM_SUBSCRIPTION_ID"
ARM_TENANT_ENV = "ARM_TENANT_ID"
# A service-principal credential in the environment means a run authenticating by it (a developer's
# ``.envrc``) — MSI is then NOT forced over it. Every service principal carries a CLIENT ID, whatever
# the secret form (password, certificate, federated/OIDC token); the host's system-assigned managed
# identity carries none (orodruin.env sets no AZURE_CLIENT_*), so a client id — or any explicit SP
# secret — means "a credential is configured, leave the provider's auth alone".
_SP_CREDENTIAL_ENV = (
    "ARM_CLIENT_ID", "AZURE_CLIENT_ID",                              # every SP carries a client id
    "ARM_CLIENT_SECRET", "AZURE_CLIENT_SECRET",                      # by password
    "ARM_CLIENT_CERTIFICATE_PATH", "AZURE_CLIENT_CERTIFICATE_PATH",  # by certificate
    "ARM_USE_OIDC", "AZURE_FEDERATED_TOKEN_FILE",                    # by federated / OIDC token
)
# The subscription and tenant the managed identity acts in (the IMDS token names neither). Read from
# the ARM_* names first, then Eregion's own: AZURE_SUBSCRIPTION_ID is mandatory; the bench tenant is
# EREGION_TENANT_ID (the name Orodruin's contract uses), but a control-plane technique with no Graph
# probe may leave it unset, so AZURE_TENANT_ID is accepted too.
_SUBSCRIPTION_SRC = ("ARM_SUBSCRIPTION_ID", "AZURE_SUBSCRIPTION_ID")
_TENANT_SRC = ("ARM_TENANT_ID", "EREGION_TENANT_ID", "AZURE_TENANT_ID")


def _first_set(environ: Mapping[str, str], names) -> str | None:
    """The first of ``names`` whose value is set and not blank — whitespace is not a value, stripped
    the same way ``graph_declared`` strips the tenant (``eregion_core/orodruin.py``)."""
    for name in names:
        value = (environ.get(name) or "").strip()
        if value:
            return value
    return None


def azure_provider_env(environ: Mapping[str, str]) -> dict[str, str]:
    """Tell Terraform's azurerm provider to authenticate the warmup by the HOST's managed identity.

    On an armed Orodruin no service-principal credential is in the environment — the hardened
    container holds only the host's system-assigned managed identity — and the provider finds no
    credential offline (no SP secret, no Azure CLI), so it must be told to use that identity:
    ``ARM_USE_MSI`` with the subscription and tenant (the IMDS token names neither). When a
    service-principal credential IS present (a client id, a secret, a certificate or a federated
    token — a developer run) nothing is set and the provider's own auth is left to resolve it; MSI
    is never forced over a configured credential. Both the subscription and the tenant must be
    named, else nothing is set: a half-configured provider would fail less clearly than the
    unchanged one — so a control-plane technique that leaves ``EREGION_TENANT_ID`` unset must name
    the tenant another way (``infra/orodruin/orodruin.env.example``).

    Returned as overrides the executor layers over the process environment
    (``annatar/executors/stratus_host.py``)."""
    if any((environ.get(k) or "").strip() for k in _SP_CREDENTIAL_ENV):
        return {}
    sub = _first_set(environ, _SUBSCRIPTION_SRC)
    tenant = _first_set(environ, _TENANT_SRC)
    if not (sub and tenant):
        return {}
    return {ARM_USE_MSI_ENV: "true", ARM_SUBSCRIPTION_ENV: sub, ARM_TENANT_ENV: tenant}
