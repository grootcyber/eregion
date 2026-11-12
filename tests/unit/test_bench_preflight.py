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

# The vault's item of the target, as `az backup item list` gave it on 11/11 (BNC1b, #724), in template:
# `properties.containerName` in three segments, `name` in four, the full container in the item's id.
CONTAINER_SHORT = f"iaasvmcontainerv2;{bw.RG};{bw.VM}"
CONTAINER_FULL = f"IaasVMContainer;iaasvmcontainerv2;{bw.RG};{bw.VM}"
ITEM_NAME = f"VM;iaasvmcontainerv2;{bw.RG};{bw.VM}"
ITEM = {"id": (f"/subscriptions/{bw.SUB}/resourceGroups/{bw.RG}/providers/Microsoft.RecoveryServices/vaults/"
               f"{bw.VAULT}/backupFabrics/Azure/protectionContainers/{CONTAINER_FULL}/protectedItems/{ITEM_NAME}"),
        "name": ITEM_NAME,
        "properties": {"friendlyName": bw.VM, "containerName": CONTAINER_SHORT}}
# az's stderr on 11/11 at `az backup recoverypoint list -c <containerName>`, in template: a WARNING
# first (the backup management type), then the ERROR, then its code and message.
AZ_WARNING_THEN_ERROR = (
    "WARNING: Could not extract the backup management type, please provide it using "
    "--backup-management-type, or try using container friendly name instead.\n"
    "ERROR: (BMSUserErrorContainerNameIncorrectFormat) Container name is not in the correct format\n"
    "Code: BMSUserErrorContainerNameIncorrectFormat\n"
    "Message: Container name is not in the correct format\n")


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


def _pair_rules(app_id: str, held: dict) -> list[dict]:
    """`az ad app show` and `az ad sp show` of one pair: its secrets' end dates, or "fail"."""
    out = []
    for obj in ("app", "sp"):
        if held[obj] == "fail":
            out.append(bw.rule("az", ["ad", obj, "show", app_id], rc=1,
                               err=f"ERROR: Resource '{app_id}' does not exist or one of its queried "
                                   "reference-property objects are not present.\n"))
        else:
            out.append(bw.rule("az", ["ad", obj, "show", app_id], {"secrets": held[obj], "certificates": []}))
    return out


# The console's pair as the bench held it on 12/11: no secret on its application, one on its service
# principal, 26 days left.
CONSOLE_ON_ITS_SP = {"app": [], "sp": [(NOW + timedelta(days=26, hours=12)).isoformat()]}


def _world(tmp_path, *, point_age_h: float = 50, restore_role=None, staging_assigned=False,
           h0_rights=None, console_pair: dict = CONSOLE_ON_ITS_SP) -> bw.World:
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
        bw.rule("make", ["imladris-status"],
                "== Azure\n  ✓ vm-celebrimbor-gondolin running\n"
                f"== VM {bw.H0_IP}\n  ✓ référence déployée : v0.5.8 (0123456789ab)\n"
                "  ✓ watch    eregion-watch      running depuis 2026-11-09T08:00:00\n"
                "  ✓ console  eregion-war-room   running depuis 2026-11-09T08:00:00\n"
                "  ✓ bot      eregion-bot        running depuis 2026-11-09T08:00:00\n"
                "  ✓ découverte : heartbeat 4 assets\n",
                err=f"  ✓ Clé d'hôte de {bw.H0_IP} vérifiée par son empreinte\n"),
        bw.rule("make", ["imladris-cd-status"],
                "  tourne : v0.5.8 (0123456789ab), image sha256:00\n  dernière release : v0.5.8\n  timer : enabled\n"),
        bw.rule("make", ["orodruin-known"]),
        bw.rule("docker", ["ps", "--no-trunc", bp.PS_FORMAT],
                "eregion-annatar-shell\teregion-annatar\t\t\"bash --init-file /root/.annatar/.bashrc\"\n"),
        bw.rule("terraform", ["~infra/orodruin", "vm_id"], bw.ORO_VM),
        bw.rule("terraform", ["~infra/orodruin", "principal_id"], bw.ORO_OID),
        bw.rule("terraform", ["~infra/glorfindel-host", "principal_id"], bw.H0_OID),
        bw.rule("az", ["get-instance-view", bw.ORO_VM], ["ProvisioningState/succeeded", "PowerState/running"]),
        bw.rule("az", ["get-instance-view", bw.RID], ["ProvisioningState/succeeded", "PowerState/running"]),
        bw.rule("ssh", ["~eregion_core.orodruin"],
                {"verdict": "armed", "codes": [], "notes": [], "cap": {"max_injections": 10, "max_duration_s": 3600}}),
        # The pairs as the bench held them on 12/11 (PAIR1): the console's secret on its service
        # principal, none on its application; the bot's on its application.
        *_pair_rules(bw.CONSOLE_APP, console_pair),
        *_pair_rules(bw.BOT_APP, {"app": [(NOW + timedelta(days=60)).isoformat()], "sp": []}),
        bw.rule("az", ["vm", "list"], [{"name": bw.VM, "rg": bw.RG, "id": bw.RID},
                                       {"name": "vm-celebrimbor-bree", "rg": bw.RG, "id": bw.BREE}]),
        bw.rule("az", ["backup", "item", "list"], [ITEM]),
        # Measured on 11/11: the three-segment containerName refused, the full name of the item's id answers.
        bw.rule("az", ["backup", "recoverypoint", "list", "-c", CONTAINER_SHORT], rc=1, err=AZ_WARNING_THEN_ERROR),
        bw.rule("az", ["backup", "recoverypoint", "list", "-c", CONTAINER_FULL, "-i", ITEM_NAME], [
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


def test_the_console_s_secret_on_its_service_principal_is_seen_with_its_days_left(tmp_path, monkeypatch):
    """PAIR1 (#736), the bench of 12/11: « ⚠ les paires · console : aucun secret lu sur son application »
    beside « ✓ droits · console », read under the same pair. Its secret was on its service principal:
    seen now, its days left, where it lives."""
    w = _world(tmp_path, point_age_h=3, staging_assigned=True)
    code, out, err = _preflight(w, arm_in_order(), monkeypatch)
    assert code == 0, out + err
    assert ("les paires · console : secret valable jusqu'au 2026-12-06 (26 j), sur son principal de service"
            in _marked(out, bs.OK)), out
    assert "les paires · bot : secret valable jusqu'au 2027-01-08 (60 j), sur son application" in _marked(out, bs.OK)
    assert "aucun secret" not in out
    asked = [c for c in w.calls() if c[:3] == ["az", "ad", "sp"] or c[:3] == ["az", "ad", "app"]]
    assert sorted(c[3] for c in asked) == ["show"] * 4


@pytest.mark.parametrize("held, said", [
    ({"app": [], "sp": []}, "les paires · console : aucun secret ni certificat, ni sur son application ni sur "
                            "son principal de service — la paire ne peut pas se connecter"),
    ({"app": [], "sp": "fail"}, "les paires · console : date de fin illisible sur son principal de service "
                                "(ERROR: Resource '<id>' does not exist or one of its queried reference-property "
                                "objects are not present.)"),
])
def test_a_console_pair_without_a_secret_or_unread_is_a_failure_never_none_read(tmp_path, monkeypatch, held, said):
    """« aucun » only when both objects are read empty; an unread service principal is said so."""
    w = _world(tmp_path, point_age_h=3, staging_assigned=True, console_pair=held)
    code, out, err = _preflight(w, arm_in_order(), monkeypatch)
    assert code == 1, out + err
    assert said in _marked(out, bs.FAIL), out
    if held["sp"] == "fail":
        assert "aucun secret" not in out


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
    w.rules.insert(0, bw.rule("docker", ["ps"], "eregion-watch\teregion-glorfindel\twatch\t\"glorfindel watch /app/runs\"\n"
                                               "eregion-war-room\teregion-glorfindel\twar-room\t\"glorfindel serve\"\n"))
    _h0(w, readiness="not_ready")
    code, out, _ = _preflight(w, arm_in_order(), monkeypatch)
    assert code == 1
    fails = _marked(out, bs.FAIL)
    assert any(f.startswith("le poste : une watch locale tourne (eregion-watch)") for f in fails)
    assert any(f.startswith("son mode sur Imladris : non_disruptive configuré, retenu en human_only (not_ready)") for f in fails)
    assert "la quarantaine : préparation not_ready" in fails


def test_no_identifier_leaves_the_preflight(tmp_path, monkeypatch):
    w = _world(tmp_path)
    w.rules.insert(0, bw.rule("make", ["imladris-status"],
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
    w.rules.insert(0, bw.rule("make", ["imladris-status"],
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
    w.rules.insert(0, bw.rule("make", ["imladris-status"],
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


H0_TARGETS = ("imladris-status", "imladris-cd-status")


@pytest.mark.parametrize("h0_ssh", [
    f"ssh -o StrictHostKeyChecking=accept-new glorfindel@{bw.H0_IP}",       # the Makefile's, no fingerprint
    f"ssh -o StrictHostKeyChecking=no {bw.PINNED} glorfindel@{bw.H0_IP}",   # ssh keeps the first value
    f"ssh -o StrictHostKeyChecking=yes glorfindel@{bw.H0_IP}",              # no known_hosts file of its own
])
def test_an_unpinned_host_key_sends_nothing_to_orodruin_nor_h0(tmp_path, monkeypatch, h0_ssh):
    """Nothing reaches Imladris by ssh — the reader, nor `make imladris-status` and
    `imladris-cd-status`, which would connect in accept-new: one ✗, and make never called for them."""
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


# ── BNC1b (#724): what the bench of 11/11 measured ───────────────────────────────

def test_az_s_warning_is_not_the_error_said():
    res = bs.Result(1, "", AZ_WARNING_THEN_ERROR)
    assert res.first_error() == ("ERROR: (BMSUserErrorContainerNameIncorrectFormat) Container name is not "
                                 "in the correct format")


def test_az_s_warning_and_its_indented_lines_are_skipped():
    res = bs.Result(1, "", "WARNING: \n    the warning, told on the line after\n    and on one more\n"
                           f"ERROR: (AuthorizationFailed) on /subscriptions/{bw.SUB}/resourceGroups/{bw.RG}\n")
    said = res.first_error()
    assert said.startswith("ERROR: (AuthorizationFailed) on <ressource>"), said
    assert not leaks(said)


def test_az_s_error_alone_on_its_line_says_the_next_one():
    assert bs.Result(1, "", "WARNING: a warning\nERROR:\n(ResourceNotFound) the vault\n").first_error() == \
        "ERROR: (ResourceNotFound) the vault"


@pytest.mark.parametrize("err, said", [
    ("WARNING: \n    only a warning, on the line after\n",
     "code 1, rien que des avertissements : only a warning, on the line after"),
    ("WARNING: the type\nWarning: Permanently added 'x' (ED25519) to the list of known hosts.\n",
     "code 1, rien que des avertissements : the type"),
    ("WARNING: \n", "code 1, rien que des avertissements"),
    ("", "code 1"),
])
def test_only_warnings_are_said_so_never_an_empty_line(err, said):
    assert bs.Result(1, "", err).first_error() == said


def test_the_point_s_az_warning_is_not_the_error_the_preflight_says(tmp_path, monkeypatch):
    """11/11: « point : illisible (RuntimeError: WARNING: ) » — the true error hidden behind az's
    warning. The ✗ stays a ✗, and says the error."""
    w = _world(tmp_path, point_age_h=3, staging_assigned=True)
    w.rules.insert(0, bw.rule("az", ["backup", "recoverypoint", "list"], rc=1, err=AZ_WARNING_THEN_ERROR))
    code, out, _ = _preflight(w, arm_in_order(), monkeypatch)
    assert code == 1, out
    fails = _marked(out, bs.FAIL)
    assert ("point : illisible (RuntimeError: ERROR: (BMSUserErrorContainerNameIncorrectFormat) Container name "
            "is not in the correct format)") in fails, out
    assert not any("WARNING" in f for f in fails), out


# `docker ps --no-trunc --format PS_FORMAT` on a workstation where another project runs a « watcher ».
FOREIGN = ('billing-watcher-1\tghcr.io/example/watcher:2.1\twatcher\t"/usr/bin/watcher --interval 10s"\n'
           'files-watch-1\texample/files:latest\twatch\t"npm run watch"\n'
           'kind-watchdog\tkindest/node:v1.31.0\t\t"/usr/local/bin/entrypoint /sbin/init"\n'
           'notes-glorfindel-1\texample/notes\tnotes\t"node glorfindel watch"\n')


def test_a_foreign_watcher_on_the_workstation_is_no_watch_of_eregion(tmp_path, monkeypatch):
    w = _world(tmp_path, point_age_h=3, staging_assigned=True)
    w.rules.insert(0, bw.rule("docker", ["ps", "--no-trunc", bp.PS_FORMAT],
                              FOREIGN + 'eregion-annatar-shell\teregion-annatar\t\t"bash"\n'))
    code, out, _ = _preflight(w, arm_in_order(), monkeypatch)
    assert "le poste : aucune watch locale" in _marked(out, bs.OK), out
    assert code == 0, out


@pytest.mark.parametrize("ps, watch", [
    ('eregion-watch\teregion-glorfindel\twatch\t"glorfindel watch /app/runs"\n', "eregion-watch"),
    ('eregion-blue-watch\teregion-glorfindel:latest\twatch\t"glorfindel watch /app/runs"\n', "eregion-blue-watch"),
    # rebuilt under it: docker says the old image by its id; the name compose gives is the watch's
    ('eregion-watch\t0123456789ab\twatch\t"glorfindel watch /app/runs"\n', "eregion-watch"),
    # EREGION_INSTANCE set to another name: the service and the image say it
    ('lab-watch\teregion-glorfindel\twatch\t"glorfindel watch /app/runs"\n', "lab-watch"),
    # its command alone says it (review 1): EREGION_INSTANCE=lab on a rebuilt image — neither the name
    # nor the image say it; `make glorfindel-watch` — a name drawn by docker, no compose label
    ('lab-watch\t3f2a9c1b7d00\twatch\t"glorfindel watch /app/runs"\n', "lab-watch"),
    ('quirky_hopper\teregion-glorfindel\t\t"glorfindel watch runs/"\n', "quirky_hopper"),
])
def test_a_watch_of_eregion_beside_a_foreign_watcher_is_a_failure(tmp_path, monkeypatch, ps, watch):
    w = _world(tmp_path, point_age_h=3, staging_assigned=True)
    w.rules.insert(0, bw.rule("docker", ["ps", "--no-trunc", bp.PS_FORMAT], FOREIGN + ps))
    code, out, _ = _preflight(w, arm_in_order(), monkeypatch)
    assert code == 1, out
    assert f"le poste : une watch locale tourne ({watch}) : elle répondrait aussi — make glorfindel-stop" \
        in _marked(out, bs.FAIL), out


def test_the_watch_read_is_the_service_compose_declares():
    """The service, its image and its container's name, as docker-compose.yml says them: renamed there,
    the preflight would read no watch."""
    import yaml
    watch = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"][bp.WATCH_SERVICE]
    assert bp._image_name(watch["image"]) == bp.WATCH_IMAGE
    assert watch["container_name"] == "${EREGION_INSTANCE:-eregion}-watch"
    assert bp.is_watch_command(f'"{watch["command"]}"')


def test_the_watch_by_hand_is_read_by_its_command():
    """`make glorfindel-watch`: `docker run --rm … eregion-glorfindel glorfindel watch runs/`, no name, no
    compose label — its command, as docker ps --no-trunc says it, is a watch's."""
    make = (ROOT / "Makefile").read_text()
    recipe = re.search(r"^glorfindel-watch:.*\n\t@\$\(DOCKER_GLORFINDEL_WATCH\) (.+)$", make, re.M)
    image_cmd = re.search(r"^DOCKER_GLORFINDEL_WATCH = (?:.*\\\n)*.*\$\(IMAGE_GLORFINDEL\) (\S+)$", make, re.M)
    assert recipe and image_cmd, "make glorfindel-watch is no longer what the preflight reads"
    assert bp.is_watch_command(f'"{image_cmd.group(1)} {recipe.group(1).strip()}"')
    assert bp.PS_ARGV[:3] == ["docker", "ps", "--no-trunc"]


@pytest.mark.parametrize("command, watch", [
    ('"glorfindel watch runs/"', True),
    ('"glorfindel watch /app/runs"', True),
    ('"/usr/local/bin/glorfindel --verbose watch runs/"', True),
    ("glorfindel watch", True),
    ('"glorfindel serve"', False),
    ('"glorfindel respond runs/annatar/x_signals.jsonl"', False),
    ('"bash --init-file /root/.glorfindel/.bashrc"', False),
    ('"node glorfindel watch"', False),
    ('"/usr/bin/watcher --interval 10s"', False),
    ('"glorfindel-watcher watch"', False),
    ("", False),
])
def test_a_watch_s_command(command, watch):
    assert bp.is_watch_command(command) is watch


def test_a_warning_goes_on_neither_over_a_blank_line_nor_over_an_error():
    """Review 1: an indented line after a WARNING was its suite even after a blank line, an indented
    ERROR too — the true error hidden behind « rien que des avertissements »."""
    assert bs.Result(1, "", "WARNING: the type\n\n    (Conflict) the vault is busy\n").first_error() == \
        "(Conflict) the vault is busy"
    assert bs.Result(1, "", "WARNING: the type\n    told on\n  ERROR: (Conflict) the vault is busy\n").first_error() == \
        "ERROR: (Conflict) the vault is busy"


def test_the_point_is_asked_by_the_full_container_of_the_item_s_id():
    """The form measured on 11/11 (B): `-c` the full container's name — not its three-segment
    containerName, refused —, `-i` the item's name, both read from the item's id: the bench confirmed
    the id's segments are `"IaasVMContainer;" + containerName` and the item's `name`, to the case."""
    args = bp.recoverypoint_args("rg-vault", bw.VAULT, ITEM)
    assert args == ["backup", "recoverypoint", "list", "-g", "rg-vault", "-v", bw.VAULT, "-c", CONTAINER_FULL,
                    "-i", ITEM_NAME, "--backup-management-type", "AzureIaasVM"]
    assert CONTAINER_SHORT not in args
    assert CONTAINER_FULL == "IaasVMContainer;" + ITEM["properties"]["containerName"]
    # read from the id alone: neither the name nor the containerName of the item is taken
    bare = {"id": ITEM["id"], "name": "other", "properties": {"containerName": "other"}}
    assert bp.recoverypoint_args("rg-vault", bw.VAULT, bare) == args


def test_the_point_s_container_is_read_whatever_the_id_s_case():
    item = {**ITEM, "id": ITEM["id"].replace("/protectionContainers/", "/protectioncontainers/")
                                    .replace("/protectedItems/", "/protecteditems/")}
    assert bp.recoverypoint_args("rg-vault", bw.VAULT, item)[8] == CONTAINER_FULL


@pytest.mark.parametrize("item, cause", [
    ({k: v for k, v in ITEM.items() if k != "id"}, "l'id de l'item ne porte pas son conteneur"),
    ({**ITEM, "id": f"/subscriptions/{bw.SUB}/resourceGroups/{bw.RG}/providers/Microsoft.RecoveryServices/"
                    f"vaults/{bw.VAULT}/backupFabrics/Azure/protectedItems/{ITEM_NAME}"},
     "l'id de l'item ne porte pas son conteneur"),
    ({**ITEM, "id": ITEM["id"].rsplit("/", 1)[0] + "/"}, "l'id de l'item ne porte pas son conteneur et son nom"),
])
def test_an_item_without_its_container_or_name_is_unreadable_never_a_fallback(tmp_path, monkeypatch, item, cause):
    w = _world(tmp_path, point_age_h=3, staging_assigned=True)
    w.rules.insert(0, bw.rule("az", ["backup", "item", "list"], [item]))
    code, out, _ = _preflight(w, arm_in_order(), monkeypatch)
    assert code == 1, out
    fails = [f for f in _marked(out, bs.FAIL) if f.startswith("le point de restauration : illisible")]
    assert len(fails) == 1 and cause in fails[0], out
    assert not any("recoverypoint" in c for c in w.calls()), "a form not measured was tried"


def test_the_point_of_the_bench_in_order_is_read_by_the_measured_form(tmp_path, monkeypatch):
    w = _world(tmp_path, point_age_h=3, staging_assigned=True)
    code, out, _ = _preflight(w, arm_in_order(), monkeypatch)
    assert any(o.startswith("le point de restauration : le plus récent il y a") for o in _marked(out, bs.OK)), out
    assert code == 0, out
