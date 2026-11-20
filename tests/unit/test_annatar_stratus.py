"""R2 — the Stratus Red Team adapter: a technique id is resolved against a CLOSED allow-list
(the catalog's ``engine: stratus`` entries), the pinned binary is checked at run time, the
warmup → detonate → revert → cleanup cycle runs from an armed Orodruin with every phase
journaled, and a read-only Graph probe verifies the initial state before and after. Anything the
adapter cannot run faithfully is refused (fail closed). No Azure, no LLM, no subprocess reaches a
real binary — a FAKE Stratus (an injected runner) and dry_run throughout.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from annatar.engines.stratus import (
    BINARY_LABEL,
    PHASES,
    STRATUS_DIR,
    GraphProbe,
    StratusError,
    airgap_env,
    allowed_techniques,
    azure_provider_env,
    describe,
    pinned_digests,
    resolve,
    stratus_run_env,
    verify_binary,
)
from annatar.executors.stratus_assertion import EXCHANGE_AUDIENCE, fetch_assertion
from annatar.executors.stratus_host import StagedLayout, StratusExecutor, staged_layout
from annatar.runner.engine import Engine
from annatar.runner.parser import KNOWN_ENGINES, Scenario, ScenarioParser
from eregion_core.orodruin import CapReached, Passive, Session

TID = "azure.execution.vm-run-command"
FIC = "azure.persistence.backdoor-managed-identity-fic"
ENTRA_SP = "entra-id.persistence.backdoor-application-sp"  # RID2, the directory identity card
RG_SCOPE = "/subscriptions/sub-123/resourceGroups/rg-celebrimbor"
ENROLLED = {"eregion-target": "celebrimbor", "eregion-zone": "bench"}


# ── A temp pinned binary, to exercise the guards deterministically ────────────────────

def _fake_binary(tmp_path: Path, content: bytes = b"fake-stratus-binary\n") -> tuple[Path, str]:
    d = tmp_path / "bin"
    d.mkdir(exist_ok=True)
    path = d / "stratus"
    path.write_bytes(content)
    return path, hashlib.sha256(content).hexdigest()


def _stratus_dir(tmp_path: Path, digest: str) -> Path:
    d = tmp_path / "pin"
    d.mkdir(exist_ok=True)
    (d / "PIN").write_text(f"#   {digest}  {BINARY_LABEL}\n", encoding="utf-8")
    return d


def _catalog(engine_ref: str = TID, **over) -> dict:
    entry = {"ttp": "T1651", "tactic": "execution", "status": "planned",
             "name": "Run Command", "engine": "stratus", "engine_ref": engine_ref}
    entry.update(over)
    return {entry["ttp"]: entry}


def _session(tmp_path: Path, max_injections: int = 20) -> Session:
    return Session(run_id="r1", injector="annatar", max_injections=max_injections,
                   path=tmp_path / "audit.jsonl", offhost=lambda *a, **k: None)


def _journal(session: Session) -> list[dict]:
    return [json.loads(x) for x in session.path.read_text().splitlines() if x.strip()]


def _ok_run(record: list | None = None):
    def run(argv, **kw):
        if record is not None:
            record.append(SimpleNamespace(argv=argv, env=kw.get("env")))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")
    return run


# ── The closed allow-list is the catalog (fail closed on the rest) ────────────────────

def test_allowed_techniques_is_the_catalog_closed_list():
    allowed = allowed_techniques()
    assert TID in allowed and FIC in allowed
    # RID2 adds the directory identity card (entra-id.*) alongside the control-plane (azure.*)
    assert ENTRA_SP in allowed
    assert all(a.startswith(("azure.", "entra-id.")) for a in allowed)


def test_resolve_refuses_a_technique_off_the_allowlist(tmp_path):
    binary, digest = _fake_binary(tmp_path)
    with pytest.raises(StratusError, match="closed allow-list"):
        resolve("azure.execution.not-in-catalog", binary_path=binary,
                stratus_dir=_stratus_dir(tmp_path, digest), catalog=_catalog())


@pytest.mark.parametrize("bad", [
    "aws.execution.vm-run-command",          # not azure/entra-id
    "gcp.persistence.x",                      # not azure/entra-id
    "kubernetes.persistence.x",               # not azure/entra-id (RID2 adds entra-id only)
    "azure.execution.vm-run-command/extra",   # a path separator
    "azure.Execution.vm-run-command",         # upper case
    "azure.execution.--help",                 # an option-looking segment
    "azure.execution.vm run command",         # a space
    "entra-id.persistence.x/extra",           # a path separator (entra-id too)
    "",                                        # empty
])
def test_resolve_refuses_a_malformed_id(tmp_path, bad):
    binary, digest = _fake_binary(tmp_path)
    with pytest.raises(StratusError):
        resolve(bad, binary_path=binary, stratus_dir=_stratus_dir(tmp_path, digest),
                catalog=_catalog(engine_ref=bad))


def test_resolve_accepts_an_entra_id_technique(tmp_path):
    """RID2: the adapter also runs Entra ID directory techniques (entra-id.<tactic>.<name>), held
    to the catalog's closed allow-list exactly like the azure ones."""
    binary, digest = _fake_binary(tmp_path)
    tid = "entra-id.persistence.backdoor-application-sp"
    r = resolve(tid, binary_path=binary, stratus_dir=_stratus_dir(tmp_path, digest),
                catalog=_catalog(engine_ref=tid))
    assert r.technique_id == tid
    assert [p.name for p in r.phases] == list(PHASES)


# ── The pinned binary is checked at run time (SEC5) ───────────────────────────────────

def test_verify_binary_accepts_the_pinned_bytes(tmp_path):
    binary, digest = _fake_binary(tmp_path)
    assert verify_binary(binary, _stratus_dir(tmp_path, digest)) == digest


def test_verify_binary_refuses_a_changed_binary(tmp_path):
    binary, digest = _fake_binary(tmp_path)
    binary.write_bytes(b"tampered\n")   # the bytes on disk are no longer the pinned ones
    with pytest.raises(StratusError, match="does not match its sha256"):
        verify_binary(binary, _stratus_dir(tmp_path, digest))


def test_verify_binary_refuses_when_pin_has_no_binary(tmp_path):
    binary, _ = _fake_binary(tmp_path)
    d = tmp_path / "stratus"
    d.mkdir()
    (d / "PIN").write_text("# a PIN with no binary line\n", encoding="utf-8")
    with pytest.raises(StratusError, match="no sha256"):
        verify_binary(binary, d)


def test_verify_binary_refuses_a_missing_binary(tmp_path):
    digest = hashlib.sha256(b"x").hexdigest()
    with pytest.raises(StratusError, match="cannot be read"):
        verify_binary(tmp_path / "absent", _stratus_dir(tmp_path, digest))


def test_repo_pin_records_the_stratus_binary():
    """The committed PIN carries the digest of the binary we BUILD from the pinned submodule +
    our patch (R2BW) — the one the adapter re-checks before every phase."""
    digests = pinned_digests(STRATUS_DIR)
    assert digests.get(BINARY_LABEL) == \
        "834976c9df9584c8d02e9559139cc4ca9a46af658134c160b2b1205d0d8db21e"


# ── A resolved technique carries its phases, verified binary and probe ────────────────

def test_resolve_builds_the_four_phases(tmp_path):
    binary, digest = _fake_binary(tmp_path)
    r = resolve(TID, binary_path=binary, stratus_dir=_stratus_dir(tmp_path, digest),
                catalog=_catalog())
    assert [p.name for p in r.phases] == ["warmup", "detonate", "revert", "cleanup"]
    for p in r.phases:
        assert p.argv == [str(binary), p.name, TID]   # the exact process argv: binary phase id
    assert r.binary_digest == digest
    assert r.ttp == "T1651" and r.tactic == "execution"
    assert r.graph_probe is None


def test_graph_probe_defaults_to_expect_absent(tmp_path):
    binary, digest = _fake_binary(tmp_path)
    cat = _catalog(engine_ref=FIC, graph_probe={   # no expect_absent → defaults to True
        "name": "fic-absent", "read": "/v1.0/applications?$select=id"})
    r = resolve(FIC, binary_path=binary, stratus_dir=_stratus_dir(tmp_path, digest), catalog=cat)
    assert r.graph_probe.expect_absent is True


def test_resolve_parses_a_read_only_graph_probe(tmp_path):
    binary, digest = _fake_binary(tmp_path)
    cat = _catalog(engine_ref=FIC, graph_probe={
        "name": "fic-absent", "read": "/v1.0/applications?$select=id", "expect_absent": True})
    r = resolve(FIC, binary_path=binary, stratus_dir=_stratus_dir(tmp_path, digest), catalog=cat)
    assert r.graph_probe.request() == ("GET", "/v1.0/applications?$select=id")


def test_describe_needs_no_binary(tmp_path):
    info = describe(TID, catalog=_catalog())
    assert info["technique_id"] == TID and info["phases"] == list(PHASES)


def test_describe_fails_closed_off_the_allowlist():
    with pytest.raises(StratusError, match="closed allow-list"):
        describe("azure.execution.nope", catalog=_catalog())


# ── The Graph probe can only read ─────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [
    "https://graph.microsoft.com/v1.0/applications",   # a scheme/host
    "/beta/applications",                               # not v1.0
    "/v1.0/applications\n/users",                       # a newline
    "/v1.0/app lications",                              # a space
    "/v1.0/<script>",                                   # angle brackets
])
def test_graph_probe_rejects_a_non_read_path(bad):
    with pytest.raises(StratusError, match="can only read"):
        GraphProbe(name="p", read=bad).request()


def test_graph_probe_holds_on_absence_and_presence():
    probe = GraphProbe(name="p", read="/v1.0/applications", expect_absent=True)
    assert probe.holds({"value": []}) is True        # absent as expected
    assert probe.holds({"value": [{"id": "x"}]}) is False  # present: not clean
    present = GraphProbe(name="p", read="/v1.0/applications", expect_absent=False)
    assert present.holds({"value": [{"id": "x"}]}) is True


# ── The offline environment (Orodruin has no Internet) ────────────────────────────────

def test_airgap_env_points_terraform_offline(tmp_path):
    env = airgap_env(tmp_path / "home", terraform_binary=tmp_path / "tf",
                     terraformrc=tmp_path / "rc")
    assert env["HOME"] == str(tmp_path / "home")
    assert env["STRATUS_TERRAFORM_BINARY_PATH"] == str(tmp_path / "tf")
    assert env["TF_CLI_CONFIG_FILE"] == str(tmp_path / "rc")
    assert "TF_PLUGIN_CACHE_DIR" not in env   # Stratus keeps its default, writable plugin cache


def test_staged_layout_reads_the_environment():
    layout = staged_layout(env={"EREGION_STRATUS_BINARY": "/x/stratus"})
    assert layout.binary == "/x/stratus"
    assert layout.home and layout.plugin_cache and layout.terraformrc   # defaults for the rest


# ── The azurerm provider authenticates the warmup by the host's managed identity (MSI1) ──

def test_azure_provider_env_uses_msi_when_only_a_managed_identity():
    """On an armed Orodruin there is no service-principal secret — only the host's managed
    identity — so the provider is told to use it: ARM_USE_MSI with the subscription and tenant."""
    env = azure_provider_env({"AZURE_SUBSCRIPTION_ID": "sub-123",
                              "EREGION_TENANT_ID": "tenant-abc"})
    assert env == {"ARM_USE_MSI": "true", "ARM_SUBSCRIPTION_ID": "sub-123",
                   "ARM_TENANT_ID": "tenant-abc"}


def test_azure_provider_env_leaves_service_principal_auth_untouched():
    """A developer run carries a service-principal secret — MSI is NOT forced over it (returns
    nothing, so the provider keeps authenticating by the secret)."""
    base = {"AZURE_SUBSCRIPTION_ID": "sub-123", "EREGION_TENANT_ID": "tenant-abc"}
    assert azure_provider_env({**base, "ARM_CLIENT_SECRET": "x"}) == {}
    assert azure_provider_env({**base, "AZURE_CLIENT_SECRET": "x"}) == {}


def test_azure_provider_env_sets_nothing_without_both_subscription_and_tenant():
    """A half-configured provider fails less clearly than the unchanged one — so with the
    subscription or the tenant missing, nothing is set."""
    assert azure_provider_env({"AZURE_SUBSCRIPTION_ID": "sub-123"}) == {}   # no tenant
    assert azure_provider_env({"EREGION_TENANT_ID": "tenant-abc"}) == {}    # no subscription
    assert azure_provider_env({}) == {}


def test_azure_provider_env_prefers_the_explicit_arm_names():
    """ARM_* names win over Eregion's own when both are present (an operator override)."""
    env = azure_provider_env({"ARM_SUBSCRIPTION_ID": "arm-sub", "AZURE_SUBSCRIPTION_ID": "az-sub",
                              "ARM_TENANT_ID": "arm-tenant", "EREGION_TENANT_ID": "er-tenant"})
    assert env["ARM_SUBSCRIPTION_ID"] == "arm-sub" and env["ARM_TENANT_ID"] == "arm-tenant"


def test_azure_provider_env_accepts_the_azure_tenant_name():
    """A control-plane technique with no Graph probe may leave EREGION_TENANT_ID unset, so the
    tenant is taken from AZURE_TENANT_ID too (else the warmup would no-op silently)."""
    env = azure_provider_env({"AZURE_SUBSCRIPTION_ID": "sub-123", "AZURE_TENANT_ID": "tenant-abc"})
    assert env == {"ARM_USE_MSI": "true", "ARM_SUBSCRIPTION_ID": "sub-123",
                   "ARM_TENANT_ID": "tenant-abc"}


def test_azure_provider_env_ignores_blank_values():
    """Whitespace is not a value (as graph_declared strips the tenant): a blank tenant is treated
    as absent, and a blank credential does not block MSI (orodruin.env warns empty vars mask the
    identity)."""
    assert azure_provider_env({"AZURE_SUBSCRIPTION_ID": "sub-123",
                               "EREGION_TENANT_ID": "   "}) == {}            # blank tenant → absent
    env = azure_provider_env({"AZURE_SUBSCRIPTION_ID": "sub-123", "EREGION_TENANT_ID": "tenant-abc",
                              "AZURE_CLIENT_SECRET": ""})                    # blank secret ignored
    assert env["ARM_USE_MSI"] == "true"


def test_azure_provider_env_leaves_every_service_principal_form_untouched():
    """A service principal authenticates by a secret, a certificate or a federated/OIDC token — each
    carries a client id the managed identity lacks; any of them means a credential is configured, so
    MSI is not forced over it."""
    base = {"AZURE_SUBSCRIPTION_ID": "sub-123", "EREGION_TENANT_ID": "tenant-abc"}
    for marker in ("ARM_CLIENT_ID", "AZURE_CLIENT_ID", "ARM_CLIENT_CERTIFICATE_PATH",
                   "AZURE_CLIENT_CERTIFICATE_PATH", "ARM_USE_OIDC", "AZURE_FEDERATED_TOKEN_FILE"):
        assert azure_provider_env({**base, marker: "x"}) == {}, marker


# ── R2c pièce 4: the dedicated Stratus identity, by the federated exchange ─────────────

def test_stratus_run_env_is_empty_without_the_dedicated_subscription():
    # a developer run: no dedicated identity — the run keeps MSI1 / its own credentials.
    assert stratus_run_env({"AZURE_SUBSCRIPTION_ID": "bench-sub"}) == {}


def test_stratus_run_env_authenticates_as_stratus_by_the_federated_exchange():
    env = stratus_run_env({"EREGION_STRATUS_SUBSCRIPTION": "ded-sub",
                           "EREGION_STRATUS_CLIENT_ID": "stratus-app",
                           "EREGION_STRATUS_ASSERTION_FILE": "/run/assertion",
                           "EREGION_TENANT_ID": "tenant-abc",
                           "AZURE_SUBSCRIPTION_ID": "bench-sub"})   # the bench sub is NOT used
    assert env["ARM_USE_OIDC"] == "true"
    assert env["ARM_CLIENT_ID"] == "stratus-app" and env["AZURE_CLIENT_ID"] == "stratus-app"
    assert env["ARM_SUBSCRIPTION_ID"] == "ded-sub" and env["AZURE_SUBSCRIPTION_ID"] == "ded-sub"
    assert env["ARM_OIDC_TOKEN_FILE_PATH"] == "/run/assertion"
    assert env["AZURE_FEDERATED_TOKEN_FILE"] == "/run/assertion"
    assert env["ARM_TENANT_ID"] == "tenant-abc"


def test_stratus_run_env_refuses_an_incomplete_federated_identity():
    # the dedicated subscription is set but the federated identity is incomplete: refuse rather than
    # fall back to the managed identity or the bench subscription (the v1 blocker, fail closed).
    full = {"EREGION_STRATUS_SUBSCRIPTION": "ded-sub", "EREGION_STRATUS_CLIENT_ID": "stratus-app",
            "EREGION_STRATUS_ASSERTION_FILE": "/run/assertion", "EREGION_TENANT_ID": "tenant-abc"}
    for missing in ("EREGION_STRATUS_CLIENT_ID", "EREGION_STRATUS_ASSERTION_FILE", "EREGION_TENANT_ID"):
        env = {k: v for k, v in full.items() if k != missing}
        with pytest.raises(RuntimeError, match="federated identity is incomplete"):
            stratus_run_env(env)


def test_stratus_run_env_ignores_a_blank_dedicated_subscription():
    assert stratus_run_env({"EREGION_STRATUS_SUBSCRIPTION": "   "}) == {}


def test_the_assertion_is_fetched_for_the_exchange_audience():
    """R2c pièce 4B: the host fetches Orodruin's managed-identity token for the exchange audience
    (api://AzureADTokenExchange) — the federated assertion the sandbox run exchanges for a Stratus
    token. The scope is that audience's /.default."""
    asked: list[str] = []
    token = fetch_assertion(get_token=lambda scope: asked.append(scope) or "the-jwt")
    assert token == "the-jwt"
    assert asked == [f"{EXCHANGE_AUDIENCE}/.default"]
    assert EXCHANGE_AUDIENCE == "api://AzureADTokenExchange"


def test_an_empty_assertion_fails_closed():
    """An empty (or whitespace) managed-identity token is a failure, never a value — the Stratus
    run must not start without a real assertion."""
    import pytest
    with pytest.raises(RuntimeError, match="assertion"):
        fetch_assertion(get_token=lambda scope: "   ")


def test_the_executor_env_uses_the_federated_identity_over_msi(tmp_path, monkeypatch):
    # when the dedicated identity is configured, _env authenticates as Stratus, not by MSI.
    for k, v in {"EREGION_STRATUS_SUBSCRIPTION": "ded-sub",
                 "EREGION_STRATUS_CLIENT_ID": "stratus-app",
                 "EREGION_STRATUS_ASSERTION_FILE": "/run/assertion",
                 "EREGION_TENANT_ID": "tenant-abc", "AZURE_SUBSCRIPTION_ID": "bench-sub"}.items():
        monkeypatch.setenv(k, v)
    env = _executor(tmp_path, dry_run=True)._env()
    assert env["ARM_USE_OIDC"] == "true" and "ARM_USE_MSI" not in env
    assert env["ARM_SUBSCRIPTION_ID"] == "ded-sub"


# ── The executor journals every phase through the armed contract ──────────────────────

def _staged_home(tmp_path) -> Path:
    """A staged ``/opt/stratus/home`` with a fake pinned Terraform and its recorded sha256 (R2BS):
    what ``make stratus-build`` lays into the read-only image."""
    home = tmp_path / "staged-home"
    home.mkdir(exist_ok=True)
    tf = home / "terraform"
    tf.write_bytes(b"#!/bin/sh\necho 'Terraform v1.3.10'\n")
    tf.chmod(0o755)
    (home / "terraform.sha256").write_text(
        hashlib.sha256(tf.read_bytes()).hexdigest() + "  terraform\n", encoding="utf-8")
    return home


def _executor(tmp_path, *, dry_run=False, run=None, get=None, session=None, record=None,
              layout=None):
    binary, digest = _fake_binary(tmp_path)
    r = resolve(TID, binary_path=binary, stratus_dir=_stratus_dir(tmp_path, digest),
                catalog=_catalog(graph_probe={"name": "absent",
                                              "read": "/v1.0/applications?$select=id"}))
    if layout is None:
        layout = StagedLayout(binary=str(binary), home=str(_staged_home(tmp_path)),
                              plugin_cache=str(tmp_path / "mirror"),
                              terraformrc=str(tmp_path / "terraformrc"))
    return StratusExecutor(r, session if session is not None else _session(tmp_path),
                           target=RG_SCOPE, dry_run=dry_run,
                           run=run or _ok_run(record), get=get, layout=layout)


def test_executor_journals_each_phase_before_it_runs(tmp_path):
    session = _session(tmp_path)
    ex = _executor(tmp_path, session=session)
    for name in PHASES:
        ex.run_phase(name)
    assert session.calls == len(PHASES)   # four injector calls, counted against the cap
    journal = _journal(session)
    actions = [r["action"] for r in journal if r.get("outcome") == "about_to_call"]
    assert actions == [f"stratus:{p}" for p in PHASES]
    assert all(r["target"] == RG_SCOPE for r in journal)
    ex.close()


def test_executor_sends_the_exact_argv_and_offline_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-123")   # inherited by the subprocess
    record: list = []
    ex = _executor(tmp_path, record=record)
    ex.detonate()
    assert record[0].argv[1:] == ["detonate", TID]
    assert record[0].env["AZURE_SUBSCRIPTION_ID"] == "sub-123"   # credentials inherited
    # HOME is a fresh, WRITABLE run-scoped dir — never the read-only staged home (R2BS)
    assert record[0].env["HOME"] == ex._run_home_path != ex.layout.home
    assert record[0].env["STRATUS_TERRAFORM_BINARY_PATH"] == ex._staged_terraform()
    assert record[0].env["TF_CLI_CONFIG_FILE"] == ex.layout.terraformrc
    assert "TF_PLUGIN_CACHE_DIR" not in record[0].env
    ex.close()


def _only_managed_identity(monkeypatch):
    """A host carrying only a system-assigned managed identity: the subscription and bench tenant
    named, no service-principal credential of any form and no ARM_* overrides from the ambient
    shell."""
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-123")
    monkeypatch.setenv("EREGION_TENANT_ID", "tenant-abc")
    for var in ("ARM_SUBSCRIPTION_ID", "ARM_TENANT_ID", "AZURE_TENANT_ID", "ARM_USE_MSI",
                "ARM_CLIENT_ID", "AZURE_CLIENT_ID", "ARM_CLIENT_SECRET", "AZURE_CLIENT_SECRET",
                "ARM_CLIENT_CERTIFICATE_PATH", "AZURE_CLIENT_CERTIFICATE_PATH",
                "ARM_USE_OIDC", "AZURE_FEDERATED_TOKEN_FILE"):
        monkeypatch.delenv(var, raising=False)


def test_executor_hands_the_warmup_the_managed_identity_directive(tmp_path, monkeypatch):
    """MSI1: on a host carrying only a managed identity, the subprocess env carries ARM_USE_MSI
    with the subscription and tenant, so the warmup's azurerm provider authenticates by it."""
    _only_managed_identity(monkeypatch)
    record: list = []
    ex = _executor(tmp_path, record=record)
    ex.detonate()
    assert record[0].env["ARM_USE_MSI"] == "true"
    assert record[0].env["ARM_SUBSCRIPTION_ID"] == "sub-123"
    assert record[0].env["ARM_TENANT_ID"] == "tenant-abc"
    ex.close()


def test_executor_omits_the_msi_directive_under_a_service_principal_secret(tmp_path, monkeypatch):
    """A developer run authenticating by a service-principal secret keeps it — MSI is not forced,
    so ARM_USE_MSI never reaches the subprocess."""
    _only_managed_identity(monkeypatch)
    monkeypatch.setenv("ARM_CLIENT_SECRET", "a-secret")
    record: list = []
    ex = _executor(tmp_path, record=record)
    ex.detonate()
    assert "ARM_USE_MSI" not in record[0].env
    ex.close()


def test_executor_run_home_is_writable_and_close_removes_it(tmp_path):
    """R2BS: the staged /opt/stratus/home is read-only in the image, so the executor builds a
    fresh writable HOME per run (Stratus writes its state under <HOME>/.stratus-red-team/) and
    close() removes it."""
    ex = _executor(tmp_path)
    home = ex._ensure_run_home()
    assert os.path.isdir(home) and home != ex.layout.home
    (Path(home) / ".stratus-red-team").mkdir()   # writable, as Stratus needs
    ex.close()
    assert not os.path.exists(home)


def test_executor_run_home_uses_the_exec_tmpfs_when_present(tmp_path, monkeypatch):
    """R2BZ: on an armed Orodruin a dedicated EXEC tmpfs is mounted, so Terraform can execute the
    providers (extracted under HOME) while /tmp stays noexec; the run HOME is built there."""
    exec_home = tmp_path / "stratus-home"
    exec_home.mkdir()
    monkeypatch.setattr("annatar.executors.stratus_host.EXEC_HOME", str(exec_home))
    ex = _executor(tmp_path)
    home = ex._ensure_run_home()
    assert Path(home).parent == exec_home   # built under the exec tmpfs, not /tmp
    ex.close()


def test_executor_run_home_falls_back_without_the_exec_tmpfs(tmp_path, monkeypatch):
    """R2BZ: absent (a test, a non-container run), the default temp dir is used."""
    monkeypatch.setattr("annatar.executors.stratus_host.EXEC_HOME", str(tmp_path / "absent"))
    ex = _executor(tmp_path)
    home = ex._ensure_run_home()
    assert os.path.isdir(home) and Path(home).parent != tmp_path / "absent"
    ex.close()


def test_the_exec_home_is_only_on_the_annatar_runs_not_the_shared_hardening():
    """R2BZ: the dedicated exec tmpfs (so Terraform runs the providers) is added only to the annatar
    run defs — those that may run the control-plane library — never to the shared ORO_HARDEN, which
    stays hardened exactly as docker-compose, nor to the control/gothmog/contract runs; /tmp noexec."""
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text(encoding="utf-8")

    def line(prefix):
        return next(ln for ln in makefile.splitlines() if ln.startswith(prefix))

    harden = line("ORO_HARDEN")
    assert "/stratus-home" not in harden and "--tmpfs /tmp:exec" not in harden   # shared hardening strict
    assert "ORO_EXEC_HOME  = --tmpfs /stratus-home:exec" in makefile             # the exec tmpfs (M6081)
    assert "$(ORO_EXEC_HOME)" in line("ORO_RUN ")                                # annatar run
    assert "$(ORO_EXEC_HOME)" in line("ORO_RUN_REQUEST")                         # the exercise run
    assert "$(ORO_EXEC_HOME)" not in line("ORO_RUN_GOTHMOG")                     # gothmog: never
    assert "$(ORO_EXEC_HOME)" not in line("ORO_RUN_CONTRACT")                    # the contract: never


def test_the_orodruin_stratus_run_is_wired_for_the_federated_exchange():
    """R2c pièce 4B: orodruin-stratus runs on the sandbox network (the IMDS is DROPped there, pièce
    3), mounts Orodruin's assertion read-only and names it to the run, and fetches that assertion on
    the host (default bridge, IMDS reachable) for the exchange audience — so the run authenticates as
    Stratus by the federated exchange, never by Orodruin's managed identity (unreachable there)."""
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text(encoding="utf-8")

    def line(prefix):
        return next(ln for ln in makefile.splitlines() if ln.startswith(prefix))

    run = line("ORO_RUN_STRATUS")
    assert "--network $(ORO_SANDBOX_NET)" in run                           # the sandbox (IMDS blocked)
    assert "--network host" not in run                                     # never host (IMDS exposed)
    assert "-v $(ORO_STRATUS_ASSERTION):$(ORO_STRATUS_MOUNT):ro" in run    # assertion mounted read-only
    assert "-e EREGION_STRATUS_ASSERTION_FILE=$(ORO_STRATUS_MOUNT)" in run     # named to stratus_run_env
    assert "ORO_SANDBOX_NET = eregion-stratus-sandbox" in makefile         # the pièce 3 network
    fetch = line("ORO_STRATUS_FETCH")
    assert "python -m annatar.executors.stratus_assertion" in fetch        # Orodruin's assertion
    assert "--network" not in fetch                                        # default bridge: IMDS reachable
    assert "$(ORO_STRATUS_FETCH) && $(ORO_RUN_STRATUS)" in makefile        # fetch on the host, then run


def test_the_sandbox_proof_is_mounted_into_the_contract_and_the_run():
    """R2c decision A: the DROP-rule proof (written on the host by the root service) is mounted
    read-only into both the contract run (orodruin-check's read_sandbox reads it — it cannot read
    live iptables) and the Stratus run (its arming checks it too)."""
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text(encoding="utf-8")

    def line(prefix):
        return next(ln for ln in makefile.splitlines() if ln.startswith(prefix))

    mount = "-v $(ORO_SANDBOX_PROOF):$(ORO_SANDBOX_PROOF):ro"
    assert mount in line("ORO_RUN_CONTRACT ")
    assert mount in line("ORO_RUN_STRATUS ")
    assert "ORO_SANDBOX_PROOF = /run/eregion-sandbox-rules" in makefile


def test_executor_refuses_when_the_staged_terraform_is_missing(tmp_path):
    """R2BS: no staged Terraform (image not staged) → the run refuses before provisioning."""
    empty = tmp_path / "empty-home"
    empty.mkdir()
    layout = StagedLayout(binary="/x/stratus", home=str(empty),
                          plugin_cache="/m", terraformrc="/rc")
    ex = _executor(tmp_path, layout=layout)
    with pytest.raises(RuntimeError, match="staged Terraform"):
        ex.detonate()


def test_executor_refuses_a_staged_terraform_that_does_not_match_its_sha256(tmp_path):
    """R2BS (SEC5): the staged Terraform re-checked before a run, like the Stratus binary — a
    binary changed since its sha256 was recorded runs nothing."""
    home = _staged_home(tmp_path)
    (home / "terraform").write_bytes(b"tampered\n")   # changed after its sha256 was recorded
    layout = StagedLayout(binary="/x/stratus", home=str(home),
                          plugin_cache="/m", terraformrc="/rc")
    ex = _executor(tmp_path, layout=layout)
    with pytest.raises(RuntimeError, match="does not match"):
        ex.detonate()


def test_executor_passive_without_a_session(tmp_path):
    binary, digest = _fake_binary(tmp_path)
    r = resolve(TID, binary_path=binary, stratus_dir=_stratus_dir(tmp_path, digest),
                catalog=_catalog())
    ex = StratusExecutor(r, None, target=RG_SCOPE, run=_ok_run())   # no armed contract
    with pytest.raises(Passive):
        ex.warmup()


def test_executor_dry_run_starts_no_process_and_journals_nothing(tmp_path):
    session = _session(tmp_path)

    def boom(*a, **k):
        raise AssertionError("no process in dry_run")

    ex = _executor(tmp_path, dry_run=True, run=boom, session=session)
    assert ex.warmup() == ""
    assert session.calls == 0           # nothing runs, nothing is counted
    assert not session.path.exists()    # nothing is journaled


def test_executor_raises_on_a_nonzero_exit(tmp_path):
    def fail(argv, **k):
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    ex = _executor(tmp_path, run=fail)
    with pytest.raises(RuntimeError, match="exited 1"):
        ex.detonate()


def test_executor_cap_is_enforced(tmp_path):
    ex = _executor(tmp_path, session=_session(tmp_path, max_injections=2))
    ex.warmup()
    ex.detonate()
    with pytest.raises(CapReached):
        ex.revert()


# ── The read-only Graph probe (before / after) ────────────────────────────────────────

def test_graph_probe_reads_and_is_declared_not_counted(tmp_path):
    session = _session(tmp_path)
    seen: list = []

    def get(path):
        seen.append(path)
        return {"value": []}   # the technique's objects are absent — the initial state holds

    ex = _executor(tmp_path, session=session, get=get)
    assert ex.probe_initial_state("before") is True
    assert seen == ["/v1.0/applications?$select=id"]
    assert session.calls == 0   # a read: declared, never counted against the cap
    declared = [r for r in _journal(session) if r.get("outcome") == "declared"]
    assert declared and declared[0]["action"] == "stratus:graph-probe:before"


def test_graph_probe_none_when_the_technique_declares_none(tmp_path):
    binary, digest = _fake_binary(tmp_path)
    r = resolve(TID, binary_path=binary, stratus_dir=_stratus_dir(tmp_path, digest),
                catalog=_catalog())   # no graph_probe
    ex = StratusExecutor(r, _session(tmp_path), target=RG_SCOPE, run=_ok_run())
    assert ex.probe_initial_state("before") is None


# ── Engine dispatch: the cycle on the control plane ───────────────────────────────────

def _scenario(**over) -> Scenario:
    raw = {"name": "stratus run", "mitre": "T1651", "engine": "stratus", "engine_ref": TID,
           "target": {"type": "azure_subscription", "resource_group": "rg-celebrimbor",
                      "subscription_id": "sub-123"},
           "detection": {"timeout": "300s"}}
    raw.update(over)
    return Scenario(name=raw["name"], description="", mitre=raw["mitre"], version="1.0.0",
                    target=raw["target"], setup=[], steps=[], detection=raw["detection"],
                    detection_hints={}, raw=raw, engine="stratus", engine_ref=raw["engine_ref"])


def _fake_executor(tmp_path, *, before=True, after=True, rg_tags=None,
                   detonate_raises=False, warmup_raises=False,
                   before_raises=False, after_raises=False,
                   warmup_interrupt=False, detonate_interrupt=False, interrupt_in=""):
    binary, digest = _fake_binary(tmp_path)
    r = resolve(TID, binary_path=binary, stratus_dir=_stratus_dir(tmp_path, digest),
                catalog=_catalog())
    calls: list = []

    class Fake:
        target = RG_SCOPE
        binary_digest = r.binary_digest
        resolved = r

        def resource_group_tags(self, sub, rg):
            return ENROLLED if rg_tags is None else rg_tags

        def _interrupt(self, phase):
            if interrupt_in == phase:
                raise KeyboardInterrupt(f"interrupted during {phase}")

        def warmup(self):
            calls.append("warmup")
            self._interrupt("warmup")
            if warmup_interrupt:
                raise KeyboardInterrupt("interrupted during warmup")
            if warmup_raises:
                raise RuntimeError("warmup failed")

        def detonate(self):
            calls.append("detonate")
            self._interrupt("detonate")
            if detonate_interrupt:
                raise KeyboardInterrupt("interrupted during detonate")
            if detonate_raises:
                raise RuntimeError("detonate failed")

        def revert(self):
            calls.append("revert")
            self._interrupt("revert")

        def cleanup(self):
            calls.append("cleanup")
            self._interrupt("cleanup")

        def probe_initial_state(self, when):
            calls.append(f"probe:{when}")
            self._interrupt("before" if when == "before" else "after")
            if when == "before":
                if before_raises:
                    raise RuntimeError("before-probe failed")
                return before
            if after_raises:
                raise RuntimeError("after-probe failed")
            return after

    return Fake(), r, calls


def _signals(tmp_path):
    out = []
    for f in (tmp_path / "runs" / "annatar").glob("*_signals.jsonl"):
        out += [json.loads(x)["event"] for x in f.read_text().splitlines() if x.strip()]
    return out


def _report(tmp_path):
    return json.loads(next((tmp_path / "runs" / "annatar").glob("2*.json")).read_text())


def test_run_stratus_cycle_runs_all_phases_and_emits_attack_started(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake, r, calls = _fake_executor(tmp_path)
    engine = Engine()
    engine._run_stratus_cycle(_scenario(), fake, "20260101T000000Z", r)
    assert calls == ["warmup", "probe:before", "detonate", "revert", "cleanup", "probe:after"]
    assert "attack_started" in _signals(tmp_path)
    rpt = _report(tmp_path)
    assert rpt["result"] == "PASS"
    assert rpt["metrics"]["engine"] == "stratus"
    assert rpt["metrics"]["detection"] == "unknown"      # control-plane detection is ID1
    assert "ID1" in rpt["metrics"]["detection_note"]


def test_run_stratus_cycle_cleans_up_even_when_detonate_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake, r, calls = _fake_executor(tmp_path, detonate_raises=True)
    engine = Engine()
    with pytest.raises(RuntimeError, match="detonate failed"):
        engine._run_stratus_cycle(_scenario(), fake, "20260101T000001Z", r)
    assert "cleanup" in calls                       # the prerequisites are always destroyed
    assert "revert" not in calls                    # no detonation, nothing to revert
    assert "attack_started" not in _signals(tmp_path)   # no effect, no signal
    rpt = _report(tmp_path)
    assert rpt["checks"]["detonate"] == "ERROR"     # the failed phase, labelled right
    assert rpt["result"] == "FAIL"                  # a failed detonation is never a PASS


def test_run_stratus_cycle_before_probe_error_is_not_a_pass(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake, r, calls = _fake_executor(tmp_path, before_raises=True)
    with pytest.raises(RuntimeError, match="before-probe failed"):
        Engine()._run_stratus_cycle(_scenario(), fake, "20260101T000013Z", r)
    assert "detonate" not in calls                  # the before-probe failed: never detonated
    assert "cleanup" in calls
    rpt = _report(tmp_path)
    assert rpt["checks"]["initial_state_before"] == "ERROR"
    assert rpt["result"] == "FAIL"                  # never a PASS without a detonation


def test_run_stratus_cycle_watch_lost_after_warmup_is_not_a_pass(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    monkeypatch.chdir(tmp_path)
    fake, r, calls = _fake_executor(tmp_path)
    engine = Engine()
    engine._watch_lost = MagicMock(side_effect=["", "the watch died"])   # ok, then lost
    out = engine._run_stratus_cycle(_scenario(), fake, "20260101T000014Z", r)
    assert out.error and "glorfindel" in out.error
    assert "detonate" not in calls and "cleanup" in calls
    rpt = _report(tmp_path)
    assert rpt["checks"]["detonate"] == "SKIPPED"
    assert rpt["result"] == "FAIL"                  # a lost watch is never a PASS


def test_run_stratus_cycle_after_probe_error_surfaces_an_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake, r, calls = _fake_executor(tmp_path, after_raises=True)
    out = Engine()._run_stratus_cycle(_scenario(), fake, "20260101T000015Z", r)
    assert out.error == "initial state not verified after cleanup"   # not a silent unknown
    rpt = _report(tmp_path)
    assert rpt["checks"]["initial_state_after"] == "ERROR"


def test_run_stratus_cycle_interrupt_in_warmup_is_not_a_pass(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake, r, calls = _fake_executor(tmp_path, warmup_interrupt=True)
    with pytest.raises(KeyboardInterrupt):
        Engine()._run_stratus_cycle(_scenario(), fake, "20260101T000018Z", r)
    assert "cleanup" in calls and "detonate" not in calls   # cleaned even on an interrupt
    assert _report(tmp_path)["result"] == "FAIL"             # a BaseException is never a PASS


def test_run_stratus_cycle_interrupt_in_detonate_is_not_a_pass(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake, r, calls = _fake_executor(tmp_path, detonate_interrupt=True)
    with pytest.raises(KeyboardInterrupt):
        Engine()._run_stratus_cycle(_scenario(), fake, "20260101T000019Z", r)
    # Every labelled phase is PASS here (warmup/before/cleanup/after) — only the missing
    # detonation keeps the report FAIL.
    assert _report(tmp_path)["result"] == "FAIL"
    assert "cleanup" in calls and "revert" not in calls


def test_run_stratus_cycle_error_after_detonation_is_not_before_probe(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake, r, calls = _fake_executor(tmp_path)
    # A bad detonation timeout raises AFTER a successful detonate (in the attack_started emit).
    sc = _scenario(detection={"timeout": "not-a-duration"})
    with pytest.raises(ValueError):
        Engine()._run_stratus_cycle(sc, fake, "20260101T000020Z", r)
    rpt = _report(tmp_path)
    assert rpt["checks"]["detonate"] == "PASS"             # the detonation itself succeeded
    assert rpt["checks"]["attack_started"] == "ERROR"      # the failure is labelled after it
    assert "initial_state_before" not in rpt["checks"] or \
        rpt["checks"]["initial_state_before"] != "ERROR"   # never mislabelled as the before-probe


# A Ctrl-C in ANY phase cleans the bench and writes a FAIL report, then re-raises (round 4).
# "emit" is the attack_started signal, between detonate and the teardown — engine-internal, so
# it is interrupted by patching the emitter rather than the fake executor.
_PHASE_CHECK = {"warmup": "warmup", "before": "initial_state_before", "detonate": "detonate",
                "emit": "attack_started", "revert": "revert", "cleanup": "cleanup",
                "after": "initial_state_after"}


@pytest.mark.parametrize("phase", list(_PHASE_CHECK))
def test_run_stratus_cycle_interrupt_in_any_phase_cleans_up_and_reports(tmp_path, monkeypatch,
                                                                        phase):
    monkeypatch.chdir(tmp_path)
    if phase == "emit":
        fake, r, calls = _fake_executor(tmp_path)   # detonate succeeds; the emit is interrupted
        import annatar.runner.engine as eng

        def boom(*a, **k):
            raise KeyboardInterrupt("interrupted during emit")

        monkeypatch.setattr(eng.SignalEmitter, "emit", boom)
    else:
        fake, r, calls = _fake_executor(tmp_path, interrupt_in=phase)
    with pytest.raises(KeyboardInterrupt):
        Engine()._run_stratus_cycle(_scenario(), fake, "20260101T000021Z", r)
    rpt = _report(tmp_path)
    assert rpt["result"] == "FAIL"                             # an interrupt is never a PASS
    assert rpt["checks"][_PHASE_CHECK[phase]] == "INTERRUPTED"  # the phase in flight, labelled
    assert "cleanup" in calls                                  # the bench is always cleaned up


def test_stratus_report_never_passes_without_detonation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    binary, digest = _fake_binary(tmp_path)
    r = resolve(TID, binary_path=binary, stratus_dir=_stratus_dir(tmp_path, digest),
                catalog=_catalog())
    # A double Ctrl-C can leave the attack phase unlabelled while the teardown is all-PASS
    # (a second interrupt lands inside the except BaseException handler, before its label); only
    # the `detonated` guard keeps the report FAIL. Not an equivalent mutant (M4350).
    Engine()._stratus_report("20260101T000030Z", _scenario(), r,
                             {"cleanup": "PASS", "initial_state_after": "PASS"}, {},
                             detonated=False)
    assert _report(tmp_path)["result"] == "FAIL"


def test_run_stratus_cycle_does_not_detonate_on_a_dirty_initial_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake, r, calls = _fake_executor(tmp_path, before=False)
    engine = Engine()
    out = engine._run_stratus_cycle(_scenario(), fake, "20260101T000002Z", r)
    assert "detonate" not in calls
    assert out.detection == "unknown" and out.error and "not clean" in out.error
    assert "cleanup" in calls   # warmup provisioned, so cleanup still destroys


def test_run_stratus_refuses_an_unenrolled_group(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-123")   # scope OK: enrollment is what fails
    fake, r, _ = _fake_executor(tmp_path, rg_tags={})   # no enrollment tags
    engine = Engine()
    out = engine._run_stratus(_scenario(), "20260101T000003Z", _session(tmp_path), r,
                              executor=fake)
    # Refused by the enrollment guard with its own reason (not the later bench-zone message).
    assert out.refused and "missing tag" in out.error


def test_run_stratus_refuses_a_target_without_subscription(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AZURE_SUBSCRIPTION_ID", raising=False)
    fake, r, _ = _fake_executor(tmp_path)
    sc = _scenario(target={"type": "azure_subscription", "resource_group": "rg-celebrimbor"})
    out = Engine()._run_stratus(sc, "20260101T000004Z", _session(tmp_path), r, executor=fake)
    assert out.refused and "subscription_id" in out.error


def test_run_stratus_refuses_a_legacy_enrolled_group(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-123")
    legacy = {"annatar-test": "true"}   # the old migration tag alone — zone bench, but legacy
    fake, r, calls = _fake_executor(tmp_path, rg_tags=legacy)
    out = Engine()._run_stratus(_scenario(), "20260101T000016Z", _session(tmp_path), r,
                                executor=fake)
    assert out.refused and "annatar-test" in out.error   # a new engine never runs on it
    assert "warmup" not in calls


def test_run_stratus_refuses_a_non_destructive_technique_in_production(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-123")
    prod = {"eregion-target": "celebrimbor", "eregion-zone": "production"}
    fake, r, calls = _fake_executor(tmp_path, rg_tags=prod)   # the case check_zone lets through
    out = Engine()._run_stratus(_scenario(), "20260101T000017Z", _session(tmp_path), r,
                                executor=fake)
    assert out.refused and "bench" in out.error
    assert "warmup" not in calls


def test_run_stratus_runs_the_cycle_on_an_enrolled_group(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-123")   # the bench scope's subscription
    fake, r, calls = _fake_executor(tmp_path)   # ENROLLED, zone bench
    out = Engine()._run_stratus(_scenario(), "20260101T000010Z", _session(tmp_path), r,
                                executor=fake)
    assert not out.refused                       # the guard allowed the enrolled bench group
    assert calls == ["warmup", "probe:before", "detonate", "revert", "cleanup", "probe:after"]
    # The exercise window (isolated_exercise_windows redirects it under tmp/exercises).
    window = json.loads((tmp_path / "exercises" / "20260101T000010Z.json").read_text())
    assert window["end"] is not None             # opened then closed


def test_run_stratus_refuses_a_non_bench_zone(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-123")
    twin = {"eregion-target": "celebrimbor", "eregion-zone": "twin"}
    fake, r, calls = _fake_executor(tmp_path, rg_tags=twin)   # enrolled, but not bench
    out = Engine()._run_stratus(_scenario(), "20260101T000011Z", _session(tmp_path), r,
                                executor=fake)
    assert out.refused and "bench" in out.error
    assert "warmup" not in calls                 # refused before the cycle


def test_run_stratus_cycle_cleans_up_when_warmup_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake, r, calls = _fake_executor(tmp_path, warmup_raises=True)
    with pytest.raises(RuntimeError, match="warmup failed"):
        Engine()._run_stratus_cycle(_scenario(), fake, "20260101T000012Z", r)
    assert "cleanup" in calls                     # a half-provisioned warmup is still cleaned
    assert "revert" not in calls and "detonate" not in calls   # never revert without a detonation
    rpt = _report(tmp_path)
    assert rpt["checks"]["warmup"] == "ERROR"     # the failed phase, labelled right


def test_executor_reverifies_binary_before_each_phase(tmp_path):
    binary, digest = _fake_binary(tmp_path)
    r = resolve(TID, binary_path=binary, stratus_dir=_stratus_dir(tmp_path, digest),
                catalog=_catalog())
    ex = StratusExecutor(r, _session(tmp_path), target=RG_SCOPE, run=_ok_run())
    binary.write_bytes(b"swapped-after-resolve\n")   # tampered between resolve and the phase
    with pytest.raises(RuntimeError, match="binary changed"):
        ex.detonate()


# ── Authoring + dispatch surface ──────────────────────────────────────────────────────

def test_known_engines_has_stratus():
    assert "stratus" in KNOWN_ENGINES


def test_parser_accepts_a_stratus_scenario(tmp_path):
    import yaml
    path = tmp_path / "s.yaml"
    path.write_text(yaml.safe_dump({
        "name": "s", "description": "d", "mitre": "T1651", "engine": "stratus",
        "engine_ref": TID,
        "target": {"type": "azure_subscription", "resource_group": "rg-celebrimbor"},
    }), encoding="utf-8")
    assert ScenarioParser().validate(str(path)).valid


def test_parser_refuses_a_stratus_scenario_without_engine_ref(tmp_path):
    import yaml
    path = tmp_path / "s.yaml"
    path.write_text(yaml.safe_dump({
        "name": "s", "description": "d", "mitre": "T1651", "engine": "stratus",
        "target": {"type": "azure_subscription", "resource_group": "rg-celebrimbor"},
    }), encoding="utf-8")
    result = ScenarioParser().validate(str(path))
    assert not result.valid and any("engine_ref" in e for e in result.errors)


def test_dry_run_display_shows_the_cycle(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import yaml
    path = tmp_path / "s.yaml"
    path.write_text(yaml.safe_dump({
        "name": "s", "description": "d", "mitre": "T1651", "engine": "stratus",
        "engine_ref": TID,
        "target": {"type": "azure_subscription", "resource_group": "rg-celebrimbor"},
        "detection": {"timeout": "300s"},
    }), encoding="utf-8")
    Engine(dry_run=True).run(str(path), skip_confirm=True)
    out = capsys.readouterr().out
    assert TID in out and "warmup" in out and "detonate" in out


# ── #819: the FIC identity scenario (the 0.6.0 identity card) and stratus authoring ──────

FIC_SCENARIO = (
    Path(__file__).resolve().parents[2]
    / "annatar/scenarios/azure/managed-identity-federated-credential.yaml"
)


def test_fic_identity_scenario_is_valid_and_resolves_to_the_catalog():
    """#819: the shipped FIC scenario loads, names the catalog's control-plane identity technique,
    and describes its cycle from the catalog alone (dry-run, no binary)."""
    result = ScenarioParser().validate(str(FIC_SCENARIO))
    assert result.valid, result.errors
    scenario = ScenarioParser().load(str(FIC_SCENARIO))
    assert scenario.engine == "stratus"
    assert scenario.engine_ref == FIC
    assert scenario.target.get("type") != "azure_vm" and "vm_name" not in scenario.target
    assert FIC in allowed_techniques()
    d = describe(FIC)
    assert d["ttp"] == "T1098"
    assert list(d["phases"]) == list(PHASES)
    assert d["graph_probe"] is not None and d["graph_probe"].expect_absent is True
    # grounding for the purple loop: a control-plane log source Glorfindel can anchor on
    assert scenario.detection_hints.get("log_source") == "azure_activity"


# ── RID2: the Entra ID directory identity scenario (the 0.6.0 identity card, directory side) ──

ENTRA_SP_SCENARIO = (
    Path(__file__).resolve().parents[2]
    / "annatar/scenarios/azure/backdoor-application-service-principal.yaml"
)


def test_entra_sp_scenario_is_valid_and_resolves_to_the_catalog():
    """RID2: the shipped backdoor-application-sp scenario loads, names the catalog's directory
    identity technique, and describes its cycle from the catalog alone (dry-run, no binary). Its
    target is the directory (entra_id) — no resource_group — and its grounding is Entra AuditLogs."""
    result = ScenarioParser().validate(str(ENTRA_SP_SCENARIO))
    assert result.valid, result.errors
    scenario = ScenarioParser().load(str(ENTRA_SP_SCENARIO))
    assert scenario.engine == "stratus"
    assert scenario.engine_ref == ENTRA_SP
    assert scenario.target.get("type") == "entra_id"
    assert "resource_group" not in scenario.target
    assert ENTRA_SP in allowed_techniques()
    d = describe(ENTRA_SP)
    assert d["ttp"] == "T1098.001"
    assert list(d["phases"]) == list(PHASES)
    # the read-only Graph probe, held to the Graph v1.0 read grammar (spaces as %20)
    assert d["graph_probe"] is not None and d["graph_probe"].expect_absent is True
    # grounding for the purple loop: the Entra ID audit log Glorfindel's C2 detection anchors on
    assert scenario.detection_hints.get("log_source") == "AuditLogs"


def test_parser_accepts_an_entra_id_target_without_a_resource_group(tmp_path):
    """RID2: an entra_id target acts in the directory, not under a resource group — the parser
    requires no resource_group for it (every other target still names its group)."""
    import yaml
    path = tmp_path / "s.yaml"
    path.write_text(yaml.safe_dump({
        "name": "s", "description": "d", "mitre": "T1098.001", "engine": "stratus",
        "engine_ref": ENTRA_SP,
        "target": {"type": "entra_id"},
    }), encoding="utf-8")
    assert ScenarioParser().validate(str(path)).valid
    # a control-plane target with no resource_group is still refused
    path2 = tmp_path / "s2.yaml"
    path2.write_text(yaml.safe_dump({
        "name": "s", "description": "d", "mitre": "T1098", "engine": "stratus",
        "engine_ref": FIC, "target": {"type": "azure_control_plane"},
    }), encoding="utf-8")
    assert any("resource_group" in e for e in ScenarioParser().validate(str(path2)).errors)


def _stratus_yaml(tmp_path, **over):
    import yaml
    data = {
        "name": "s", "description": "d", "mitre": "T1098", "engine": "stratus",
        "engine_ref": FIC,
        "target": {"type": "azure_control_plane", "resource_group": "rg-celebrimbor"},
        "detection": {"hints": {"log_source": "azure_activity"}},
    }
    data.update(over)
    path = tmp_path / "s.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


def test_stratus_scenario_on_a_vm_target_is_refused(tmp_path):
    """#819: a stratus scenario attacks the control plane, not a VM — a VM target (or a vm_name)
    is a misauthoring, refused at authoring before any run."""
    path = _stratus_yaml(
        tmp_path, target={"type": "azure_vm", "resource_group": "rg-celebrimbor"})
    result = ScenarioParser().validate(path)
    assert not result.valid and any("not a VM" in e for e in result.errors)
    # a vm_name on an otherwise control-plane target is refused too
    path2 = _stratus_yaml(
        tmp_path,
        target={"type": "azure_control_plane", "resource_group": "rg-celebrimbor",
                "vm_name": "vm-celebrimbor-gondolin"})
    assert any("not a VM" in e for e in ScenarioParser().validate(path2).errors)


def test_stratus_scenario_with_kind_fault_is_refused(tmp_path):
    """R2c pièce 4D: the stratus engine runs control-plane techniques, never a fault (that is
    Gothmog's engine) — a kind: fault routed through stratus is a misauthoring, refused at
    authoring before any run. A technique (and the absent default) stays valid."""
    result = ScenarioParser().validate(_stratus_yaml(tmp_path, kind="fault"))
    assert not result.valid and any("never a fault" in e for e in result.errors)
    assert ScenarioParser().validate(_stratus_yaml(tmp_path, kind="technique")).valid
    assert ScenarioParser().validate(_stratus_yaml(tmp_path)).valid


def test_stratus_authoring_checks_do_not_touch_other_engines(tmp_path):
    """#819: the authoring checks are stratus-only — a local-script scenario with a VM target and
    no detection hints stays valid."""
    import yaml
    path = tmp_path / "s.yaml"
    path.write_text(yaml.safe_dump({
        "name": "s", "description": "d", "mitre": "T1136.001",
        "target": {"type": "azure_vm", "resource_group": "rg-celebrimbor",
                   "vm_name": "vm-celebrimbor-gondolin"},
        "steps": [{"name": "x", "action": "run_script_on_vm", "script": "scripts/vm/x.sh"}],
    }), encoding="utf-8")
    assert ScenarioParser().validate(path).valid
