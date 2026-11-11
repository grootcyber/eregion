"""`make bench-preflight [TARGET=<vm>]`: the bench's step 0 in one verdict (BNC1, #682).

On a fake bench (tests/unit/bench_world.py: `az`, `terraform`, `docker`, `make`, Orodruin and Imladris
read by ssh — Imladris through scripts/bench_h0_reader.py, run for real on a fake Imladris) and a fake Azure
Resource Manager (the console pair's token, `Microsoft.Authorization/permissions`, on `requests`),
shaped as the bench was on 09/11 (RAN1, #665), the preflight sees what that night found too late:
  - `listKeys` missing to the console on the staging account (read by Glorfindel's own reader);
  - « Eregion Glorfindel Restore Staging » not assigned there;
  - the tenant's « Eregion Glorfindel Restore » that still holds `runCommand/action` (before SEC17);
  - a recovery point too old;
and, apart, a console pair absent. A bench in order exits 0; a ✗ exits 1, a ⚠ does not. Imladris's and
Orodruin's rights are read from their assignments and the roles' definitions — wildcards and
`notActions` as Azure reads them. No identifier leaves: the output is scanned for GUIDs, IPs, UPNs.
No Azure, no Imladris, no Orodruin, no model.
"""
from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_world as bw  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


bs = _load("bench_shared")
bp = _load("bench_preflight")

NOW = datetime(2026, 11, 9, 16, 0, tzinfo=timezone.utc)
GUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
UPN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
DEF = f"/subscriptions/{bw.SUB}/providers/Microsoft.Authorization/roleDefinitions/"
RG_SCOPE = f"/subscriptions/{bw.SUB}/resourceGroups/{bw.RG}"
STAGING_SCOPE = f"{RG_SCOPE}/providers/Microsoft.Storage/storageAccounts/{bw.STAGING}"

ROLES = {
    "Reader": ["*/read"],
    "Log Analytics Reader": ["*/read", "Microsoft.OperationalInsights/workspaces/search/action"],
    "Eregion Glorfindel Response": json.loads((ROOT / "infra/identities/glorfindel-response.json").read_text())["Actions"],
    "Eregion Glorfindel Session Drain": ["Microsoft.Compute/virtualMachines/runCommand/action"],
    "Eregion Glorfindel Restore Neutralize": ["Microsoft.Compute/virtualMachines/runCommand/action"],
    "Eregion Glorfindel Restore Staging": ["Microsoft.Storage/storageAccounts/listKeys/action"],
    "Eregion Bench Injector": ["Microsoft.Compute/virtualMachines/runCommand/action",
                               "Microsoft.Compute/virtualMachines/read"],
}
# The tenant's restore role of 09/11: SEC17 took Run Command out of the repository's file, not out of it.
RESTORE_PRE_SEC17 = json.loads((ROOT / "infra/identities/glorfindel-restore.json").read_text())["Actions"] + [
    "Microsoft.Compute/virtualMachines/runCommand/action"]


def leaks(text: str) -> list[str]:
    return (GUID.findall(text) + IP.findall(text) + UPN.findall(text)
            + [s for s in (bw.SECRET, "bot-secret", "/subscriptions/", "fake-token") if s in text])


def _assign(role: str, scope: str, n: int) -> dict:
    return {"roleDefinitionName": role, "roleDefinitionId": f"{DEF}00000000-0000-4000-8000-{n:012d}",
            "scope": scope, "principalId": "x"}


def _definition(role: str, n: int, actions: list[str], not_actions: list[str] | None = None) -> list[dict]:
    return [{"roleName": role, "id": f"{DEF}00000000-0000-4000-8000-{n:012d}",
             "permissions": [{"actions": actions, "notActions": not_actions or []}]}]


class Arm:
    """Azure Resource Manager, faked on requests: the token endpoint, the permissions API by scope."""

    def __init__(self, perms: dict[str, list[dict]]):
        self.perms, self.asked, self.posted = perms, [], []

    def post(self, url, data=None, timeout=None, **kw):
        self.posted.append((url, dict(data or {})))
        ok = data.get("client_secret") == bw.SECRET
        return _Resp(200 if ok else 401, {"access_token": "fake-token"} if ok else {"error": "invalid_client"})

    def get(self, url, headers=None, params=None, timeout=None, **kw):
        assert headers["Authorization"] == "Bearer fake-token"
        self.asked.append(url)
        for kind, perms in self.perms.items():
            if url.split("/providers/Microsoft.Authorization/")[0].lower().endswith(kind):
                return _Resp(200, {"value": perms})
        return _Resp(200, {"value": [{"actions": ["*/read"], "notActions": []}]})


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body, self.ok, self.text = status, body, status < 400, json.dumps(body)

    def json(self):
        return self._body


def arm_0911() -> Arm:
    """The console's rights on 09/11: the restore on the vault, the VM's writes and its Run Command,
    nothing but Reader on the staging account — `listKeys` missing."""
    return Arm({
        f"vaults/{bw.VAULT}": [{"actions": ["*/read"], "notActions": []},
                               {"actions": RESTORE_PRE_SEC17, "notActions": []}],
        f"virtualmachines/{bw.VM}": [{"actions": ["*/read"], "notActions": []},
                                     {"actions": RESTORE_PRE_SEC17, "notActions": []}],
        f"storageaccounts/{bw.STAGING}": [{"actions": ["*/read"], "notActions": []},
                                          {"actions": RESTORE_PRE_SEC17, "notActions": []}],
    })


def arm_in_order() -> Arm:
    a = arm_0911()
    a.perms[f"storageaccounts/{bw.STAGING}"].append({"actions": ROLES["Eregion Glorfindel Restore Staging"], "notActions": []})
    return a


def _h0(w: bw.World, mode: str = "non_disruptive", readiness: str = "ready") -> None:
    w.write("glorfindel-config.yaml", f"autonomy:\n  default: human_only\n  assets:\n    - match: {bw.VM}\n      mode: {mode}\n")
    w.write(".glorfindel/readiness.json", {bw.VM: {"vm": bw.VM, "resource_id": bw.RID, "verdict": readiness,
                                                   "reserve_codes": [], "reasons": [], "checked_at": bw.ts("15:00:00")}},
            home=True)
    w.write("runs/glorfindel/orodruin/contract.json", {"verdict": "armed", "codes": [], "at": bw.ts("15:50:00")})


def _world(tmp_path, *, point_age_h: float = 50, restore_role=None, staging_assigned=False,
           h0_rights=None) -> bw.World:
    w = bw.World(tmp_path)
    _h0(w)
    point = (NOW - timedelta(hours=point_age_h)).isoformat()
    restore_role = RESTORE_PRE_SEC17 if restore_role is None else restore_role
    console = [_assign("Reader", RG_SCOPE, 1), _assign("Eregion Glorfindel Restore", RG_SCOPE, 2),
               _assign("Eregion Glorfindel Restore Neutralize", bw.RID, 3)]
    if staging_assigned:
        console.append(_assign("Eregion Glorfindel Restore Staging", STAGING_SCOPE, 4))
    h0 = h0_rights if h0_rights is not None else [
        _assign("Reader", RG_SCOPE, 1), _assign("Eregion Glorfindel Response", RG_SCOPE, 5),
        _assign("Eregion Glorfindel Session Drain", bw.RID, 6)]
    w.rules = [
        bw.rule("make", ["glorfindel-host-status"],
                "== Azure\n  ✓ vm-celebrimbor-gondolin running\n"
                f"== VM {bw.H0_IP}\n  ✓ référence déployée : v0.5.8 (0123456789ab)\n"
                "  ✓ watch    eregion-watch      running depuis 2026-11-09T08:00:00\n"
                "  ✓ console  eregion-war-room   running depuis 2026-11-09T08:00:00\n"
                "  ✓ bot      eregion-bot        running depuis 2026-11-09T08:00:00\n"
                "  ✓ découverte : heartbeat 4 assets\n",
                err=f"  ✓ Clé d'hôte de {bw.H0_IP} vérifiée par son empreinte\n"),
        bw.rule("make", ["glorfindel-host-cd-status"],
                "  tourne : v0.5.8 (0123456789ab), image sha256:00\n  dernière release : v0.5.8\n  timer : enabled\n"),
        bw.rule("make", ["orodruin-known"]),
        bw.rule("docker", ["ps"], "eregion-annatar-shell\n"),
        bw.rule("terraform", ["~infra/orodruin", "vm_id"], bw.ORO_VM),
        bw.rule("terraform", ["~infra/orodruin", "principal_id"], bw.ORO_OID),
        bw.rule("terraform", ["~infra/glorfindel-host", "principal_id"], bw.H0_OID),
        bw.rule("az", ["get-instance-view", bw.ORO_VM], ["ProvisioningState/succeeded", "PowerState/running"]),
        bw.rule("az", ["get-instance-view", bw.RID], ["ProvisioningState/succeeded", "PowerState/running"]),
        bw.rule("ssh", ["~eregion_core.orodruin"],
                {"verdict": "armed", "codes": [], "notes": [], "cap": {"max_injections": 10, "max_duration_s": 3600}}),
        bw.rule("az", ["credential", bw.CONSOLE_APP], [(NOW + timedelta(days=30)).isoformat()]),
        bw.rule("az", ["credential", bw.BOT_APP], [(NOW + timedelta(days=60)).isoformat()]),
        bw.rule("az", ["vm", "list"], [{"name": bw.VM, "rg": bw.RG, "id": bw.RID},
                                       {"name": "vm-celebrimbor-bree", "rg": bw.RG, "id": bw.BREE}]),
        bw.rule("az", ["backup", "item", "list"], [
            {"name": f"VM;iaasvmcontainerv2;{bw.RG};{bw.VM}",
             "properties": {"friendlyName": bw.VM, "containerName": f"IaasVMContainer;iaasvmcontainerv2;{bw.RG};{bw.VM}"}}]),
        bw.rule("az", ["backup", "recoverypoint", "list"], [
            {"name": "1", "properties": {"recoveryPointTime": point}},
            {"name": "2", "properties": {"recoveryPointTime": (NOW - timedelta(hours=point_age_h + 24)).isoformat()}}]),
        bw.rule("az", ["assignment", bw.H0_OID], h0),
        bw.rule("az", ["assignment", bw.ORO_OID], [_assign("Eregion Bench Injector", RG_SCOPE, 7)]),
        bw.rule("az", ["assignment", bw.CONSOLE_APP], console),
        bw.rule("az", ["definition", "Eregion Glorfindel Restore"], _definition("Eregion Glorfindel Restore", 2, restore_role)),
    ]
    for n, (role, actions) in enumerate(ROLES.items(), 1):
        nid = {"Reader": 1, "Eregion Glorfindel Response": 5, "Eregion Glorfindel Session Drain": 6,
               "Eregion Bench Injector": 7, "Eregion Glorfindel Restore Neutralize": 3,
               "Eregion Glorfindel Restore Staging": 4}.get(role, 90 + n)
        w.rules.append(bw.rule("az", ["definition", role], _definition(role, nid, actions)))
    return w


def _preflight(w: bw.World, arm: Arm, monkeypatch, *args: str, **env_extra):
    env = w.env(**env_extra)
    for k in ("PATH", "BENCH_FAKE_PLAN", "BENCH_FAKE_LOG"):
        monkeypatch.setenv(k, env[k])
    import requests
    monkeypatch.setattr(requests, "get", arm.get)
    monkeypatch.setattr(requests, "post", arm.post)
    so, se = io.StringIO(), io.StringIO()
    with redirect_stdout(so), redirect_stderr(se):
        code = bp.main(["--config", str(w.config), *args], env=env, now=NOW)
    return code, so.getvalue(), se.getvalue()


def _marked(text: str, mark: str) -> list[str]:
    return [ln.strip()[2:] for ln in text.splitlines() if ln.strip().startswith(mark + " ")]


def test_the_0911_bench_is_stopped_before_the_attack(tmp_path, monkeypatch):
    """What that night found three hours in, read before: listKeys, the staging role, the old restore
    role, an old point."""
    w = _world(tmp_path)
    code, out, err = _preflight(w, arm_0911(), monkeypatch)
    assert code == 1, out + err
    fails, warns = _marked(out, bs.FAIL), _marked(out, bs.WARN)
    assert ("droits · console : il manque Microsoft.Storage/storageAccounts/listKeys/action sur le compte de transit "
            "(Microsoft.Storage/storageAccounts) (rôle « Eregion Glorfindel Restore Staging », "
            "docs/operations.md, « Identités Azure »)") in fails
    assert any(f.startswith("dérive : « Eregion Glorfindel Restore Staging » n'est pas attribué à la console")
               for f in fails)
    assert any(x.startswith("dérive : le rôle « Eregion Glorfindel Restore » du tenant porte encore "
                            "Microsoft.Compute/virtualMachines/runCommand/action (d'avant SEC17)") for x in warns)
    assert any(x.startswith("le point de restauration : le plus récent il y a 50 h 0 min 0 s (seuil 24 h) — trop vieux")
               for x in warns)
    assert len(fails) == 2, fails
    assert out.splitlines()[-1].startswith("Verdict : 2 ✗, 2 ⚠, ")


def test_a_bench_in_order_lets_the_run_go(tmp_path, monkeypatch):
    w = _world(tmp_path, point_age_h=3, restore_role=json.loads(
        (ROOT / "infra/identities/glorfindel-restore.json").read_text())["Actions"], staging_assigned=True)
    code, out, err = _preflight(w, arm_in_order(), monkeypatch)
    assert code == 0, out + err
    assert _marked(out, bs.FAIL) == [] and _marked(out, bs.WARN) == [], out
    oks = _marked(out, bs.OK)
    for said in ("Imladris : v0.5.8 (0123456789ab) déployée", "Imladris : watch, console et bot en marche",
                 "le poste : aucune watch locale", "son mode sur Imladris : non_disruptive",
                 "la quarantaine : prête (préparation ready)",
                 "droits · console : le restore (coffre, VM, compte de transit) et la neutralisation",
                 "droits · Imladris : l'isolement, la coupure, le point de restauration, la lecture du journal",
                 "droits · Orodruin : l'attaque",
                 "dérive : « Eregion Glorfindel Restore Staging » attribué à la console sur le compte de transit"):
        assert said in oks, (said, out)
    assert any(o.startswith("Orodruin : armé, plafond max_duration_s=3600, max_injections=10") for o in oks)
    assert any(o.startswith("les paires · console : secret valable jusqu'au") for o in oks)
    assert out.splitlines()[-1].endswith("le run peut partir")


def test_an_absent_console_pair_is_a_failure(tmp_path, monkeypatch):
    w = _world(tmp_path, point_age_h=3, staging_assigned=True)
    arm = arm_in_order()
    code, out, _ = _preflight(w, arm, monkeypatch, EREGION_CONSOLE_AZURE_CLIENT_ID="", EREGION_CONSOLE_AZURE_CLIENT_SECRET="")
    assert code == 1
    fails = _marked(out, bs.FAIL)
    assert any(f.startswith("les paires : celle de la console est absente ou incomplète") for f in fails)
    assert "droits · console : sa paire absente, rien n'est lu" in fails
    assert arm.posted == [] and arm.asked == []


def test_h0_s_rights_read_wildcards_and_not_actions(tmp_path, monkeypatch):
    """Imladris under a role `Microsoft.Network/*` whose notActions take securityRules/delete: the isolation
    is missing that one action; the Run Command of the drain held by a wildcard. Its Response role on
    another group, whose name begins as the bench's (`rg-celeb`), covers nothing of the bench."""
    w = _world(tmp_path, point_age_h=3, staging_assigned=True, h0_rights=[
        _assign("Reader", RG_SCOPE, 1), _assign("Wide Network", RG_SCOPE, 80), _assign("Wide Compute", RG_SCOPE, 81),
        _assign("Eregion Glorfindel Response", f"/subscriptions/{bw.SUB}/resourceGroups/rg-celeb", 5)])
    w.rules.insert(0, bw.rule("az", ["definition", "Wide Network"], _definition(
        "Wide Network", 80, ["Microsoft.Network/*", "Microsoft.RecoveryServices/*"],
        ["Microsoft.Network/networkSecurityGroups/securityRules/delete"])))
    w.rules.insert(0, bw.rule("az", ["definition", "Wide Compute"], _definition(
        "Wide Compute", 81, ["Microsoft.Compute/virtualMachines/*"])))
    code, out, _ = _preflight(w, arm_in_order(), monkeypatch)
    assert code == 1
    fails = [f for f in _marked(out, bs.FAIL) if f.startswith("droits · Imladris")]
    assert fails == ["droits · Imladris : pour l'isolement, il manque Microsoft.Network/networkSecurityGroups/securityRules/delete"]


def test_the_staging_role_on_the_group_is_not_the_staging_account_s(tmp_path, monkeypatch):
    """RST1's rule: « Restore Staging » on the staging account alone — given on the group (which holds
    other accounts), the drift is said; the permissions API reads listKeys there, held."""
    w = _world(tmp_path, point_age_h=3)
    w.rules.insert(0, bw.rule("az", ["assignment", bw.CONSOLE_APP], [
        _assign("Reader", RG_SCOPE, 1), _assign("Eregion Glorfindel Restore", RG_SCOPE, 2),
        _assign("Eregion Glorfindel Restore Neutralize", bw.RID, 3),
        _assign("Eregion Glorfindel Restore Staging", RG_SCOPE, 4)]))
    code, out, _ = _preflight(w, arm_in_order(), monkeypatch)
    assert code == 1
    assert [f for f in _marked(out, bs.FAIL) if f.startswith("dérive")] == [
        "dérive : « Eregion Glorfindel Restore Staging » n'est pas attribué à la console sur le compte de transit "
        "stcelebrimborstaging — le restore serait refusé (LinkedAuthorizationFailed) ; docs/operations.md, "
        "« Identités Azure »"]


def test_orodruin_deallocated_is_a_warning_and_its_contract_is_never_published(tmp_path, monkeypatch):
    w = _world(tmp_path, point_age_h=3, staging_assigned=True)
    w.rules.insert(0, bw.rule("az", ["get-instance-view", bw.ORO_VM], ["PowerState/deallocated"]))
    code, out, _ = _preflight(w, arm_in_order(), monkeypatch)
    assert code == 0
    assert any(x.startswith("Orodruin : deallocated — son contrat se lit une fois démarrée") for x in _marked(out, bs.WARN))
    assert not [c for c in w.calls() if c[0] == "ssh" and any(bw.ORO_IP in a for a in c)]
    # running, the contract is read by check(), never by `python -m eregion_core.orodruin` (it publishes)
    w2 = _world(tmp_path / "b", point_age_h=3, staging_assigned=True)
    _preflight(w2, arm_in_order(), monkeypatch)
    oro = [c for c in w2.calls() if c[0] == "ssh" and "eregion_core.orodruin" in c[-1]]
    assert oro and all("import check" in c[-1] and "-m eregion_core.orodruin" not in c[-1]
                       and "publish" not in c[-1] for c in oro)


def test_a_local_watch_and_a_held_mode_are_failures(tmp_path, monkeypatch):
    w = _world(tmp_path, point_age_h=3, staging_assigned=True)
    w.rules.insert(0, bw.rule("docker", ["ps"], "eregion-watch\neregion-war-room\n"))
    _h0(w, readiness="not_ready")
    code, out, _ = _preflight(w, arm_in_order(), monkeypatch)
    assert code == 1
    fails = _marked(out, bs.FAIL)
    assert any(f.startswith("le poste : une watch locale tourne (eregion-watch)") for f in fails)
    assert any(f.startswith("son mode sur Imladris : non_disruptive configuré, retenu en human_only (not_ready)") for f in fails)
    assert "la quarantaine : préparation not_ready" in fails


def test_no_identifier_leaves_the_preflight(tmp_path, monkeypatch):
    w = _world(tmp_path)
    w.rules.insert(0, bw.rule("make", ["glorfindel-host-status"],
                              f"== VM {bw.H0_IP}\n  ✓ référence déployée : v0.5.8 (0123456789ab)\n"
                              "  ✓ watch    eregion-watch  running\n  ✓ console  eregion-war-room  running\n"
                              "  ✓ bot      eregion-bot  running\n"
                              f"  ✗ sauvegarde {bw.VM} Failed par {bw.HUMAN_UPN} sur {bw.RID} ({bw.H0_OID}) "
                              f"depuis {bw.H0_IP}\n"))
    code, out, err = _preflight(w, arm_0911(), monkeypatch)
    assert code == 1
    assert leaks(out + err) == [], leaks(out + err)
    assert any(f.startswith(f"Imladris : sauvegarde {bw.VM} Failed par <upn> sur <ressource> (<id>) depuis <ip>")
               for f in _marked(out, bs.FAIL))
    # the console's secret went to the token endpoint's body only
    assert all(bw.SECRET not in " ".join(c) for c in w.calls())


def test_a_target_that_is_not_a_vm_name_is_refused_before_anything(tmp_path, monkeypatch):
    w = _world(tmp_path)
    code, out, err = _preflight(w, arm_0911(), monkeypatch, "--target", "$(id)")
    assert code == 2 and w.calls() == [] and "TARGET invalide" in err


@pytest.mark.parametrize("ref,mark", [("✓", bs.OK), ("⚠", bs.WARN)])
def test_the_deployed_reference_keeps_its_mark(tmp_path, monkeypatch, ref, mark):
    w = _world(tmp_path, point_age_h=3, staging_assigned=True)
    w.rules.insert(0, bw.rule("make", ["glorfindel-host-status"],
                              f"  {ref} référence déployée : v0.5.8 (0123456789ab)\n"
                              "  ✓ watch    eregion-watch  running\n  ✓ console  eregion-war-room  running\n"
                              "  ✓ bot      eregion-bot  running\n"))
    _, out, _ = _preflight(w, arm_in_order(), monkeypatch)
    assert "Imladris : v0.5.8 (0123456789ab) déployée" in _marked(out, mark)


# ── the review's findings (BNC1, round 1) ──────────────────────────────────────

_IN_ORDER = dict(point_age_h=3, staging_assigned=True,
                 restore_role=json.loads((ROOT / "infra/identities/glorfindel-restore.json").read_text())["Actions"])


@pytest.mark.parametrize("said", ["console : pas de réponse", "console : jeton refusé, ou réponse inattendue"])
def test_a_silent_console_stops_the_run(tmp_path, monkeypatch, said):
    """The containers' lines are said apart; the console's own ✗ (no answer, its token refused) is not
    one of them: it stays a failure."""
    w = _world(tmp_path, **_IN_ORDER)
    w.rules.insert(0, bw.rule("make", ["glorfindel-host-status"],
                              "  ✓ référence déployée : v0.5.8 (0123456789ab)\n"
                              "  ✓ watch    eregion-watch  running\n  ✓ console  eregion-war-room  running\n"
                              f"  ✓ bot      eregion-bot  running\n  ✗ {said}\n"))
    code, out, _ = _preflight(w, arm_in_order(), monkeypatch)
    assert code == 1
    assert f"Imladris : {said}" in _marked(out, bs.FAIL)


def test_a_tenant_that_is_not_a_guid_is_refused_before_any_request(tmp_path, monkeypatch):
    w = _world(tmp_path, **_IN_ORDER)
    arm = arm_in_order()
    code, out, _ = _preflight(w, arm, monkeypatch, AZURE_TENANT_ID="contoso.example.com")
    assert code == 1 and arm.posted == []
    assert "droits · console : AZURE_TENANT_ID vide ou invalide (l'id du tenant, un GUID)" in _marked(out, bs.FAIL)
    assert "contoso" not in out


def test_a_management_group_assignment_is_said_unread(tmp_path, monkeypatch):
    mg = "/providers/Microsoft.Management/managementGroups/mg-bench"
    w = _world(tmp_path, **_IN_ORDER, h0_rights=[_assign("Reader", RG_SCOPE, 1),
                                                 _assign("Eregion Glorfindel Response", mg, 5)])
    code, out, _ = _preflight(w, arm_in_order(), monkeypatch)
    assert code == 1
    fails = [f for f in _marked(out, bs.FAIL) if f.startswith("droits · Imladris")]
    assert fails and all(f.endswith("(une attribution à un groupe d'administration n'est pas lue : à vérifier "
                                    "à la main)") for f in fails)


H0_TARGETS = ("glorfindel-host-status", "glorfindel-host-cd-status")


@pytest.mark.parametrize("h0_ssh", [
    f"ssh -o StrictHostKeyChecking=accept-new glorfindel@{bw.H0_IP}",       # the Makefile's, no fingerprint
    f"ssh -o StrictHostKeyChecking=no {bw.PINNED} glorfindel@{bw.H0_IP}",   # ssh keeps the first value
    f"ssh -o StrictHostKeyChecking=yes glorfindel@{bw.H0_IP}",              # no known_hosts file of its own
])
def test_an_unpinned_host_key_sends_nothing_to_orodruin_nor_h0(tmp_path, monkeypatch, h0_ssh):
    """Nothing reaches Imladris by ssh — the reader, nor `make glorfindel-host-status` and
    `glorfindel-host-cd-status`, which would connect in accept-new: one ✗, and make never called for them."""
    w = _world(tmp_path, **_IN_ORDER)
    code, out, _ = _preflight(w, arm_in_order(), monkeypatch,
                              BENCH_ORO_SSH=f"ssh -o StrictHostKeyChecking=accept-new orodruin@{bw.ORO_IP}",
                              BENCH_H0_SSH=h0_ssh)
    assert code == 1
    fails = _marked(out, bs.FAIL)
    assert "Orodruin : sa clé d'hôte n'est pas épinglée (StrictHostKeyChecking=yes) : rien n'est envoyé" in fails
    assert [f for f in fails if f.startswith(("Imladris", "la cible sur Imladris"))] == [
        "Imladris : sa clé d'hôte n'est pas vérifiée par son empreinte (HOST_SSH_FINGERPRINT) : rien n'est envoyé"]
    assert not [c for c in w.calls() if c[0] == "ssh"]
    assert not [c for c in w.calls() if c[0] == "make" and any(t in c for t in H0_TARGETS)]


def test_a_pinned_host_key_reads_h0_s_status_through_make(tmp_path, monkeypatch):
    w = _world(tmp_path, **_IN_ORDER)
    _preflight(w, arm_in_order(), monkeypatch)
    made = [t for c in w.calls() if c[0] == "make" for t in H0_TARGETS if t in c]
    assert made == list(H0_TARGETS)


@pytest.mark.parametrize("opts,pinned", [
    (bw.PINNED, True),
    ("-o StrictHostKeyChecking=no " + bw.PINNED, False),
    ("-oStrictHostKeyChecking=yes -oUserKnownHostsFile=/k", True),
    ("-o StrictHostKeyChecking=yes", False),
    ("-o UserKnownHostsFile=/k -o StrictHostKeyChecking=accept-new -o StrictHostKeyChecking=yes", False),
    ("-o stricthostkeychecking=YES -o userknownhostsfile=/k", True),
])
def test_the_host_key_options_are_read_as_ssh_reads_them(opts, pinned):
    assert bs.host_key_pinned(["ssh", *opts.split(), "glorfindel@h0"]) is pinned


def test_an_autonomous_mode_as_configured_is_the_run_s_mode(tmp_path, monkeypatch):
    """full_auto (deferred, refused by the config today) or non_disruptive: as configured, a ✓."""
    w = _world(tmp_path, **_IN_ORDER)
    monkeypatch.setattr(bs, "read_h0", lambda *a, **k: {"target": {
        "configured": "full_auto", "effective": "full_auto", "readiness": "ready", "quarantine_nsg": True}})
    code, out, _ = _preflight(w, arm_in_order(), monkeypatch)
    assert code == 0, out
    assert "son mode sur Imladris : full_auto" in _marked(out, bs.OK)


def test_ssh_s_warning_is_not_the_error_said():
    res = bs.Result(255, "", f"Warning: Permanently added '{bw.H0_IP}' (ED25519) to the list of known hosts.\n"
                             "Permission denied (publickey).\n")
    assert res.first_error() == "Permission denied (publickey)."
