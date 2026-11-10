"""The bench's world, faked, for `make bench-preflight` and `make bench-report` (BNC1, #682).

One fake executable, put first on PATH under the names `az`, `ssh`, `terraform`, `docker` and `make`:
it answers each call from a plan (a list of rules: the command, the words its arguments must hold),
and logs it. The ssh to H0 runs scripts/bench_h0_reader.py for real, on a fake H0 — its /app (the
watch's runs/, its glorfindel-config.yaml) and its HOME (~/.glorfindel) in tmp —, with this
repository's glorfindel. Azure Resource Manager (the token of the console's pair, the permissions
API) is faked in-process by the tests, on `requests`.

The data is the shape measured on the bench on 09/11 (RAN1, #665; its report kept outside the
repository): the times, the durations, the callers' shapes (`caller` an object id, `claims.appid`,
`claims.oid`), the vault's jobs. Every identifier is invented: GUIDs of zeros, documentation
addresses (RFC 5737), example.com.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUB = "00000000-0000-4000-8000-000000000000"
RG = "rg-celebrimbor"
VM = "vm-celebrimbor-gondolin"
RID = f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Compute/virtualMachines/{VM}"
BREE = f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Compute/virtualMachines/vm-celebrimbor-bree"
NIC = f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Network/networkInterfaces/nic-celebrimbor-gondolin"
ORO_VM = f"/subscriptions/{SUB}/resourceGroups/rg-orodruin/providers/Microsoft.Compute/virtualMachines/vm-orodruin"
VAULT, STAGING = "rsv-celebrimbor-erebor", "stcelebrimborstaging"

H0_OID = "00000000-0000-4000-8000-0000000000b0"
ORO_OID = "00000000-0000-4000-8000-0000000000a0"
CONSOLE_APP = "00000000-0000-4000-8000-0000000000c0"
CONSOLE_OID = "00000000-0000-4000-8000-0000000000c1"
BOT_APP = "00000000-0000-4000-8000-0000000000d0"
TENANT = "00000000-0000-4000-8000-0000000000e0"
SECRET = "s3cr3t-of-the-console-never-printed"
HUMAN_OID = "00000000-0000-4000-8000-0000000000f0"
HUMAN_UPN = "operator@example.com"
H0_IP, ORO_IP, LEAKED_IP = "192.0.2.10", "192.0.2.20", "203.0.113.9"

RUN = "20261109T164009Z-0a0a"
REQUEST = "r-20261109T163409Z-000aaa"
DAY = "2026-11-09"

_FAKE = r'''#!PYTHON
import json, os, shlex, subprocess, sys
name, args = os.path.basename(sys.argv[0]), sys.argv[1:]
plan = json.load(open(os.environ["BENCH_FAKE_PLAN"]))
with open(os.environ["BENCH_FAKE_LOG"], "a") as f:
    f.write(json.dumps([name, *args]) + "\n")
if name == "ssh":
    cmd = args[-1]
    if "eregion-watch python -" in cmd and plan.get("h0"):
        words = shlex.split(cmd)
        rest = words[words.index("-") + 1:]
        h0 = plan["h0"]
        env = {**os.environ, "HOME": h0["home"], "PYTHONPATH": h0["pythonpath"]}
        sys.exit(subprocess.run([sys.executable, "-", *rest], stdin=sys.stdin, cwd=h0["app"], env=env).returncode)
def holds(w):
    return any(w[1:] in a for a in args) if w.startswith("~") else w in args
for rule in plan["rules"]:
    if rule["cmd"] == name and all(holds(w) for w in rule.get("has", [])):
        sys.stdout.write(rule.get("out", ""))
        sys.stderr.write(rule.get("err", ""))
        sys.exit(rule.get("rc", 0))
sys.stderr.write("fake %s: no rule for %s\n" % (name, args))
sys.exit(99)
'''


def ts(hms: str, day: str = DAY) -> str:
    return f"{day}T{hms}+00:00"


def rule(cmd: str, has: list[str], out="", rc: int = 0, err: str = "") -> dict:
    return {"cmd": cmd, "has": has, "out": out if isinstance(out, str) else json.dumps(out), "rc": rc, "err": err}


class World:
    """A fake bench in tmp: PATH, the plan, the log, a fake H0."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.bin = tmp / "bin"
        self.bin.mkdir(parents=True)
        self.plan_file, self.log = tmp / "plan.json", tmp / "calls.log"
        self.log.write_text("")
        self.app, self.home = tmp / "h0" / "app", tmp / "h0" / "home"
        (self.app / "runs" / "glorfindel" / "orodruin").mkdir(parents=True)
        (self.app / "runs" / "console").mkdir(parents=True)
        (self.home / ".glorfindel" / "isolation").mkdir(parents=True)
        fake = self.bin / "fake"
        fake.write_text(_FAKE.replace("#!PYTHON", f"#!{sys.executable}"))
        fake.chmod(0o755)
        for name in ("az", "ssh", "terraform", "docker", "make"):
            (self.bin / name).symlink_to(fake)
        self.rules: list[dict] = []
        self.config = tmp / "glorfindel-config.yaml"
        self.config.write_text(
            "action_backends:\n  - name: vault\n    type: azure_backup_vault\n"
            f"    vault_name: {VAULT}\n    resource_group: {RG}\n    restore_staging_storage: {STAGING}\n")

    def env(self, **extra) -> dict:
        self.plan_file.write_text(json.dumps({
            "rules": self.rules,
            "h0": {"app": str(self.app), "home": str(self.home), "pythonpath": str(ROOT)}}))
        base = {k: v for k, v in os.environ.items()
                if not k.startswith(("AZURE_", "EREGION_", "GLORFINDEL_", "BENCH_", "ARM_"))}
        return {**base, "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                "BENCH_FAKE_PLAN": str(self.plan_file), "BENCH_FAKE_LOG": str(self.log),
                "BENCH_H0_SSH": f"ssh -o StrictHostKeyChecking=yes glorfindel@{H0_IP}",
                "BENCH_ORO_SSH": f"ssh -o StrictHostKeyChecking=yes orodruin@{ORO_IP}",
                "BENCH_ORO_RUN": "docker run --rm --read-only --env-file orodruin.env eregion-annatar:orodruin",
                "AZURE_SUBSCRIPTION_ID": SUB, "AZURE_TENANT_ID": TENANT,
                "EREGION_CONSOLE_AZURE_CLIENT_ID": CONSOLE_APP, "EREGION_CONSOLE_AZURE_CLIENT_SECRET": SECRET,
                "GLORFINDEL_BOT_AZURE_CLIENT_ID": BOT_APP, "GLORFINDEL_BOT_AZURE_CLIENT_SECRET": "bot-secret",
                **extra}

    def calls(self) -> list[list[str]]:
        return [json.loads(x) for x in self.log.read_text().splitlines() if x.strip()]

    def write(self, rel: str, doc, home: bool = False) -> Path:
        p = (self.home if home else self.app) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(doc if isinstance(doc, str) else json.dumps(doc))
        return p


# ── the activity log of 09/11, its shapes ─────────────────────────────────────

def event(op: str, resource: str, at: str, status: str, caller: str = "", claims: dict | None = None,
          corr: str = "", sub: str = "") -> dict:
    return {"caller": caller, "claims": claims or {}, "correlationId": corr,
            "eventTimestamp": at, "operationName": {"value": op, "localizedValue": op},
            "resourceId": resource, "status": {"value": status, "localizedValue": status},
            "subStatus": {"value": sub, "localizedValue": sub}}


def operation(op, resource, start, end, status, who, corr, sub="", day=DAY) -> list[dict]:
    """An operation as the activity log writes it: Started under its caller, then its end."""
    callers = {"orodruin": (ORO_OID, {"appid": "00000000-0000-4000-8000-0000000000a9", "oid": ORO_OID,
                                      "idtyp": "app"}),
               "h0": (H0_OID, {"appid": "00000000-0000-4000-8000-0000000000b9", "oid": H0_OID, "idtyp": "app"}),
               "console": (CONSOLE_OID, {"appid": CONSOLE_APP, "oid": CONSOLE_OID, "idtyp": "app"}),
               "human": (HUMAN_UPN, {"upn": HUMAN_UPN, "oid": HUMAN_OID, "idtyp": "user"}),
               "unknown": ("00000000-0000-4000-8000-00000000ffff", {"oid": "00000000-0000-4000-8000-00000000ffff"})}
    caller, claims = callers[who]
    out = [event(op, resource, ts(start, day), "Started", caller, claims, corr)]
    if end:
        out.append(event(op, resource, ts(end, day), status, caller, claims, corr, sub))
    return out


RC = "Microsoft.Compute/virtualMachines/runCommand/action"


def activity_0911() -> list[dict]:
    ev: list[dict] = []
    ev += operation(RC, RID, "16:40:24", "16:40:46", "Succeeded", "orodruin", "c1")
    ev += operation(RC, RID, "16:40:56", "16:41:17", "Succeeded", "orodruin", "c2")
    ev += operation(RC, RID, "16:41:27", "16:42:28", "Succeeded", "orodruin", "c3")
    ev += operation("Microsoft.Network/networkInterfaces/write", NIC, "16:43:01", "16:43:02", "Succeeded", "h0", "n1")
    ev += operation(RC, RID, "16:43:03", "16:48:05", "Succeeded", "h0", "c4")
    ev += operation(RC, RID, "17:07:22", "17:09:54", "Succeeded", "console", "c5")
    ev += operation("Microsoft.Compute/virtualMachines/deallocate/action", RID, "17:09:57", "17:10:35", "Succeeded",
                    "console", "d1")
    for i, t in enumerate(("20:09:29", "20:22:24", "20:33:52")):
        ev += operation(RC, RID, t, t, "Failed", "console", f"f{i}", sub="Conflict")
    ev += operation("Microsoft.Compute/virtualMachines/start/action", RID, "20:50:19", "21:06:05", "Succeeded",
                    "console", "s1")
    ev += operation(RC, RID, "21:09:54", "21:10:05", "Succeeded", "human", "c9")
    ev += operation("Microsoft.Storage/storageAccounts/ListServiceSas/action",
                    f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Storage/storageAccounts/stother",
                    "17:01:00", "17:01:01", "Succeeded", "unknown", "u1")
    ev += operation(RC, BREE, "16:50:00", "16:50:20", "Succeeded", "h0", "b1")
    return ev


def job(op: str, status: str, start: str, end: str | None, vm: str = VM) -> dict:
    return {"name": "00000000-0000-4000-8000-0000000000aa",
            "properties": {"entityFriendlyName": vm, "operation": op, "status": status, "jobType": "AzureIaaSVMJob",
                           "startTime": ts(start), "endTime": ts(end) if end else None}}


def jobs_0911() -> list[dict]:
    return [job("Backup", "Completed", "15:49:23", "16:15:00"),
            job("Restore", "Failed", "20:22:30", "20:22:34.500000"),
            job("Restore", "Completed", "20:34:25", "20:49:42"),
            job("Backup", "Completed", "16:00:00", "16:20:00", vm="vm-celebrimbor-bree")]


VIEW_0911 = {"instanceView": {"vmAgent": {"vmAgentVersion": "2.x", "statuses": [
    {"code": "ProvisioningState/succeeded", "displayStatus": "Ready", "time": ts("21:06:30")}]},
    "statuses": [{"code": "ProvisioningState/succeeded"}, {"code": "PowerState/running"}]}}
