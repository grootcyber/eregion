"""The Stratus injector transport (R2): run the four phases of a resolved technique
(``annatar/engines/stratus.py``) through an armed Orodruin contract — every phase journaled by
``Session.before_call`` BEFORE the process starts and counted against the cap, exactly like the
VM executor (``annatar/executors/azure_vm.py``). The read-only Graph probe is journaled as a
declared read (``Session.declare``), never counted against the cap — it writes nothing.

Nothing runs without a session (passive → ``Passive``, nothing touched). In ``dry_run`` the
argv and the offline environment are shown, no process starts. The subprocess runner and the
Graph reader are injected (``run`` / ``get``), so the tests drive a FAKE Stratus binary with no
cloud call and no LLM call.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from annatar.console import console, outside
from annatar.engines.stratus import ResolvedTechnique, airgap_env, azure_provider_env


GRAPH = "https://graph.microsoft.com"

# R2BZ (#608): a dedicated EXEC tmpfs mounted on an armed Orodruin (ORO_HARDEN). The warmup's
# Terraform extracts the providers under HOME and EXECUTES them, so HOME must be on an executable
# filesystem — while the container's /tmp stays noexec (the hardening). The run HOME is built here
# when this mount is present; absent (a test, a non-container run), tempfile's default is used.
EXEC_HOME = "/stratus-home"

# The layout to stage inside the Orodruin image (annatar/stratus/README.md) — not delivered yet:
# the staging step comes with R2b (#608).
# Env overrides so the image can place them where it likes; the tests point them at a fake tree.
BINARY_ENV = "EREGION_STRATUS_BINARY"
HOME_ENV = "EREGION_STRATUS_HOME"
PLUGIN_CACHE_ENV = "EREGION_STRATUS_PLUGIN_CACHE"
TERRAFORMRC_ENV = "EREGION_STRATUS_TERRAFORMRC"

_DEFAULTS = {
    BINARY_ENV: "/opt/stratus/stratus",
    HOME_ENV: "/opt/stratus/home",
    PLUGIN_CACHE_ENV: "/opt/stratus/plugin-cache",
    TERRAFORMRC_ENV: "/opt/stratus/terraformrc",
}

# A Stratus phase can provision/destroy cloud infrastructure; give it room, but bounded.
PHASE_TIMEOUT_S = 900


@dataclass
class StagedLayout:
    binary: str
    home: str
    plugin_cache: str
    terraformrc: str


def staged_layout(env=None) -> StagedLayout:
    """Where the Orodruin image stages the pinned binary and the offline warmup assets, from the
    environment (``_DEFAULTS`` otherwise). Read by the runner (the binary, to resolve + verify
    before arming) and by this executor (the rest, for the offline environment)."""
    env = os.environ if env is None else env
    return StagedLayout(
        binary=env.get(BINARY_ENV) or _DEFAULTS[BINARY_ENV],
        home=env.get(HOME_ENV) or _DEFAULTS[HOME_ENV],
        plugin_cache=env.get(PLUGIN_CACHE_ENV) or _DEFAULTS[PLUGIN_CACHE_ENV],
        terraformrc=env.get(TERRAFORMRC_ENV) or _DEFAULTS[TERRAFORMRC_ENV],
    )


ARM = "https://management.azure.com"
_RG_API = "2021-04-01"


def _default_graph_get(path: str) -> dict:
    """A read-only GET of Microsoft Graph with this host's identity (Orodruin's, read-only in
    Graph by its contract). Not used in the tests, which inject ``get``."""
    import requests

    from azure.identity import DefaultAzureCredential
    token = DefaultAzureCredential().get_token(f"{GRAPH}/.default").token
    r = requests.get(f"{GRAPH}{path}", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} reading Microsoft Graph")
    return r.json()


def _default_arm_get(path: str, api: str) -> dict:
    """A read of Azure Resource Manager with this host's identity. Not used in the tests, which
    inject ``arm_get``."""
    import requests

    from azure.identity import DefaultAzureCredential
    token = DefaultAzureCredential().get_token(f"{ARM}/.default").token
    r = requests.get(f"{ARM}{path}", headers={"Authorization": f"Bearer {token}"},
                     params={"api-version": api}, timeout=15)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} reading {path.rsplit('/', 1)[-1]}")
    return r.json()


class StratusExecutor:
    """Runs a resolved Stratus technique's phases from an armed Orodruin. One instance per run."""

    def __init__(self, resolved: ResolvedTechnique, session, *, target: str,
                 dry_run: bool = False, layout: StagedLayout | None = None,
                 run=None, get=None, arm_get=None):
        self.resolved = resolved
        self._session = session
        self.target = target          # the control-plane scope this run touches (journaled)
        self.dry_run = dry_run
        self.layout = layout or staged_layout()
        self._run = run or subprocess.run
        self._get = get or _default_graph_get
        self._arm_get = arm_get or _default_arm_get
        self._run_home_path: str | None = None   # a writable HOME built per run (R2BS)

    def resource_group_tags(self, subscription_id: str, resource_group: str) -> dict:
        """The bench group's tags, read through ARM — the control-plane enrollment guard
        (eregion_core/inscription.py). The reader (``arm_get``) is injected in the tests; a
        read that fails raises, so the run refuses before anything is provisioned."""
        path = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
        body = self._arm_get(path, _RG_API)
        return (body.get("tags") if isinstance(body, dict) else {}) or {}

    def _staged_terraform(self) -> str:
        """The pinned Terraform binary staged read-only in the image (make stratus-build, R2BS)."""
        return os.path.join(self.layout.home, "terraform")

    def _verify_staged_terraform(self) -> None:
        """Re-check the staged Terraform before a run, like the Stratus binary (SEC5): its sha256
        against the one `make stratus-build` recorded beside it. Missing or mismatched → the run
        refuses rather than provisioning with an unknown Terraform."""
        import hashlib
        from pathlib import Path
        tf = Path(self._staged_terraform())
        recorded = Path(self.layout.home) / "terraform.sha256"
        try:
            want = recorded.read_text(encoding="utf-8").split()[0]
        except (OSError, IndexError) as e:
            raise RuntimeError(
                f"the staged Terraform checksum {recorded} is missing or empty "
                f"({type(e).__name__}) — stage it with `make stratus-build`; not run") from e
        try:
            got = hashlib.sha256(tf.read_bytes()).hexdigest()
        except OSError as e:
            raise RuntimeError(
                f"the staged Terraform {tf} cannot be read ({type(e).__name__}) — stage it with "
                "`make stratus-build`; not run") from e
        if got != want:
            raise RuntimeError(
                "the staged Terraform does not match the sha256 recorded beside it — not the "
                "staged binary; not run")

    def _ensure_run_home(self) -> str:
        """A writable HOME for this run: Stratus writes its state under
        ``<HOME>/.stratus-red-team/`` and the staged ``/opt/stratus/home`` is read-only in the
        image (R2BS). Built once (the staged Terraform re-checked first), removed by ``close()``."""
        if self._run_home_path is None:
            self._verify_staged_terraform()
            import tempfile
            base = EXEC_HOME if os.path.isdir(EXEC_HOME) else None
            self._run_home_path = tempfile.mkdtemp(prefix="stratus-home-", dir=base)
        return self._run_home_path

    def close(self) -> None:
        """Remove the run-scoped HOME. The ``docker run --rm`` tmpfs clears it too, but a test or
        a reused process should not leak it."""
        if self._run_home_path is not None:
            import shutil
            shutil.rmtree(self._run_home_path, ignore_errors=True)
            self._run_home_path = None

    def _env(self) -> dict[str, str]:
        """The process environment: the inherited one (Orodruin's Azure credentials) with the
        offline overrides layered on (annatar/engines/stratus.py::airgap_env) — a writable run
        HOME, the staged Terraform binary (STRATUS_TERRAFORM_BINARY_PATH) and the provider mirror
        (TF_CLI_CONFIG_FILE) — plus the azurerm provider's identity directive (MSI1): on a host
        carrying only a managed identity (no service-principal secret), ARM_USE_MSI with the
        subscription and tenant, so the warmup's Terraform authenticates by that identity."""
        overrides = airgap_env(self._ensure_run_home(),
                               terraform_binary=self._staged_terraform(),
                               terraformrc=self.layout.terraformrc)
        identity = azure_provider_env(os.environ)
        return {**os.environ, **overrides, **identity}

    def _before_call(self, phase: str, detail: str) -> None:
        """The journal precedes the call (O1) — a phase runs only from an armed contract."""
        from eregion_core.orodruin import Passive
        if self._session is None:
            raise Passive(f"stratus {phase} on {self.target}: no armed Orodruin contract")
        self._session.before_call(f"stratus:{phase}", self.target, detail)

    def _verify_binary_unchanged(self, phase) -> None:
        """SEC5 (R2a review): the pinned sha256 is re-checked before EVERY phase, not only when
        the technique was resolved — a binary swapped between resolution and a later phase runs
        nothing. Compared to the digest captured (and PIN-checked) by resolve()."""
        import hashlib
        from pathlib import Path
        binary = phase.argv[0]
        try:
            digest = hashlib.sha256(Path(binary).read_bytes()).hexdigest()
        except OSError as e:
            raise RuntimeError(f"the Stratus binary {binary} is unreadable before {phase.name}: "
                               f"{e} — phase not run") from e
        if digest != self.resolved.binary_digest:
            raise RuntimeError(f"the Stratus binary changed since it was pinned this run — "
                               f"{phase.name} not run")

    def run_phase(self, name: str) -> str:
        """Journal, then run one phase of the Stratus cycle (warmup/detonate/revert/cleanup).
        In dry_run nothing starts; the argv and the offline environment are shown."""
        phase = self.resolved.phase(name)
        if self.dry_run:   # nothing runs, so nothing is journaled against the contract
            console.print(f"  [yellow]DRY RUN[/yellow] stratus {name}: {outside(' '.join(phase.argv))}")
            return ""
        self._verify_binary_unchanged(phase)   # re-check the pinned sha256 before every phase
        self._before_call(name, phase.label)
        console.print(f"  [dim]Stratus → {name} : {self.resolved.technique_id}[/dim]")
        completed = self._run(phase.argv, env=self._env(), capture_output=True, text=True,
                              timeout=PHASE_TIMEOUT_S)
        out = (getattr(completed, "stdout", "") or "")
        err = (getattr(completed, "stderr", "") or "")
        if getattr(completed, "returncode", 0) != 0:
            raise RuntimeError(
                f"stratus {name} {self.resolved.technique_id} exited "
                f"{getattr(completed, 'returncode', '?')}: {err.strip()[-300:]}"
            )
        console.print(f"  [dim]{outside(out.strip()[-200:])}[/dim]")   # what Stratus answered
        return out

    def warmup(self) -> str:
        return self.run_phase("warmup")

    def detonate(self) -> str:
        return self.run_phase("detonate")

    def revert(self) -> str:
        return self.run_phase("revert")

    def cleanup(self) -> str:
        return self.run_phase("cleanup")

    def probe_initial_state(self, when: str) -> bool | None:
        """The read-only Graph probe (before detonate / after cleanup). ``None`` when the
        technique declares none. Journaled as a declared read (never counted against the cap);
        the request is held to a GET of a Graph read path by the adapter — this only reads."""
        probe = self.resolved.graph_probe
        if probe is None:
            return None
        method, path = probe.request()
        if method != "GET":   # the adapter guarantees GET; defend it here all the same
            raise RuntimeError(f"graph probe {probe.name!r}: {method} is not read-only")
        if self.dry_run:
            console.print(f"  [yellow]DRY RUN[/yellow] graph probe ({when}): GET {outside(path)}")
            return True
        if self._session is not None:
            self._session.declare(f"stratus:graph-probe:{when}", f"{probe.name} GET {path}")
        body = self._get(path)
        ok = probe.holds(body if isinstance(body, dict) else {})
        mark = "[green]✓[/green]" if ok else "[red]✗[/red]"
        console.print(f"  {mark} graph probe {probe.name} ({when})")
        return ok
