"""LEV2 (#690): the measure of H7, H9 and H12 on the bench, prepared for Jonathan (docs/banc-lev2.md).

scripts/bench_lev2.py reads only (`az … show`, `az rest --method get`), refuses inside a code session
and on a VM outside the zone `bench`, and composes its report from the saved answers without an
identifier. Tested here on sample logs and a fake `az`: nothing is run against Azure.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


lev2 = _load("bench_lev2")

SUB = "00000000-0000-0000-0000-000000000000"
RG = f"/subscriptions/{SUB}/resourceGroups/rg-celebrimbor"
VM = f"{RG}/providers/Microsoft.Compute/virtualMachines/vm-celebrimbor-gondolin"
NIC = f"{RG}/providers/Microsoft.Network/networkInterfaces/nic-gondolin"
NSG = f"{RG}/providers/Microsoft.Network/networkSecurityGroups/nsg-celebrimbor"
SUBNET = f"{RG}/providers/Microsoft.Network/virtualNetworks/vnet/subnets/app"
DISK = f"{RG}/providers/Microsoft.Compute/disks/gondolin-os"
CALLER = "11111111-2222-3333-4444-555555555555"
T = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)
GUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def _event(rid, op, at, status="Succeeded", caller=CALLER):
    return {"resourceId": rid, "operationName": {"value": op}, "status": {"value": status},
            "eventTimestamp": at.isoformat(), "submissionTimestamp": (at + timedelta(seconds=40)).isoformat(),
            "caller": caller, "claims": {"appid": caller, "oid": caller}}


def _targets():
    return {"vm": VM, "group": RG, "nics": [NIC], "disks": [DISK], "nsgs": [NSG], "public_ips": [], "identities": []}


def _sample(tmp_path: Path, *, children: bool = False, pages: int = 1) -> Path:
    """Two rounds 30 s apart: the Run Command v1 and its extension write in both, the managed Run
    Command and the rule only in the second (late in the log)."""
    d = tmp_path / "reads"
    d.mkdir()
    (d / "targets.json").write_text(json.dumps(_targets()))
    v1 = _event(VM, "Microsoft.Compute/virtualMachines/runCommand/action", T + timedelta(seconds=2))
    ext = _event(VM + "/extensions/RunCommandLinux", "Microsoft.Compute/virtualMachines/extensions/write",
                 T + timedelta(seconds=3))
    v2 = _event(VM + "/runCommands/lev2-true", "Microsoft.Compute/virtualMachines/runCommands/write",
                T + timedelta(seconds=62))
    rule = _event(NSG + "/securityRules/eregion-lev2-deny",
                  "Microsoft.Network/networkSecurityGroups/securityRules/write", T + timedelta(seconds=121))
    for n, (exact, group) in enumerate([([v1], [v1, ext]), ([v1], [v1, ext, v2, rule])], 1):
        r = d / f"round-{n:03d}"
        r.mkdir()
        at = (T + timedelta(seconds=150 + 30 * n)).isoformat()
        (r / "00-uri-vm.json").write_text(json.dumps({"fetched_at": at, "how": "uri", "what": "vm", "value": VM,
                                                      "pages": 1, "cut": False,
                                                      "events": exact + ([ext] if children else [])}))
        (r / "01-group-group.json").write_text(json.dumps({"fetched_at": at, "how": "group", "what": "group",
                                                           "value": "rg-celebrimbor", "pages": pages,
                                                           "cut": pages > 40, "events": group}))
    return d


GESTURES = f"""# the guide's gestures, noted by hand
{T.isoformat()} Microsoft.Compute/virtualMachines/runCommand/action run-command-true
{(T + timedelta(seconds=60)).isoformat()} Microsoft.Compute/virtualMachines/runCommands/write managed-true
{(T + timedelta(seconds=120)).isoformat()} Microsoft.Network/networkSecurityGroups/securityRules/write deny-rule
{(T + timedelta(seconds=180)).isoformat()} Microsoft.Compute/disks/beginGetAccess/action disk-sas
"""


def test_the_report_answers_h7_h9_h12_without_an_identifier(tmp_path):
    out = lev2.report(_sample(tmp_path), GESTURES)
    assert not GUID.search(out) and "/subscriptions/" not in out and "gondolin" not in out
    rows = {ln.split("|")[1].strip(): ln for ln in out.splitlines() if ln.startswith("| ") and "`" in ln}
    # H7: the resource each gesture's events name.
    assert "la VM" in rows["run-command-true"] and "exacte vm" in rows["run-command-true"]
    assert "enfant de la VM (runcommands)" in rows["managed-true"] and "groupe" in rows["managed-true"]
    assert "une règle de NSG" in rows["deny-rule"]
    assert "**non**" in rows["disk-sas"]
    assert "**oui**, sous le même appelant" in out and "enfant de la VM (extensions)" in out
    # H12: the first round that read it, 30 s apart; its time in the log; its submission.
    assert "| 180 s |" in rows["run-command-true"]           # noted at T, read in the first round, T + 180
    assert "| 90 s |" in rows["deny-rule"]                   # noted at T + 120, late: read in the second
    assert "| 40 s |" in rows["deny-rule"]
    # H9: the exact filter, the pages.
    assert "(**exact**)" in out and "groupe : 1 page(s) au plus" in out


def test_the_report_says_an_exact_filter_that_gives_children_and_a_group_past_the_bound(tmp_path):
    out = lev2.report(_sample(tmp_path, children=True, pages=23), GESTURES)
    assert "le filtre n'est **pas exact**" in out and "enfant de la VM (extensions)" in out
    assert "groupe : 23 page(s) au plus — **au-delà de la borne de 20**" in out


def test_a_gesture_line_that_cant_be_read_is_refused(tmp_path):
    with pytest.raises(lev2.Lev2Error):
        lev2.report(_sample(tmp_path), "hier runCommand\n")


class _Az:
    """A fake `az`: the bench VM, its NIC and subnet, the activity log in two pages."""

    def __init__(self, zone="bench"):
        self.calls, self.zone = [], zone

    def __call__(self, args):
        self.calls.append(args)
        if args[:2] == ["vm", "list"]:
            return [{"name": "vm-celebrimbor-gondolin", "id": VM}, {"name": "vm-celebrimbor-bree", "id": VM + "x"}]
        if args[:2] == ["vm", "show"]:
            return {"id": VM, "tags": {"eregion-zone": self.zone},
                    "storageProfile": {"osDisk": {"managedDisk": {"id": DISK}}, "dataDisks": []},
                    "networkProfile": {"networkInterfaces": [{"id": NIC}]}}
        if args[:3] == ["network", "nic", "show"]:
            return {"id": NIC, "ipConfigurations": [{"subnet": {"id": SUBNET}}]}
        if args[:4] == ["network", "vnet", "subnet", "show"]:
            return {"id": SUBNET, "networkSecurityGroup": {"id": NSG}}
        if args[:3] == ["rest", "--method", "get"]:
            url = args[4]
            if "page=2" in url:
                return {"value": [_event(VM, "Microsoft.Compute/virtualMachines/write", T)]}
            return {"value": [], "nextLink": "https://management.azure.com/next?page=2"}
        raise AssertionError(f"az {args}: not a read the script makes")


def test_fetch_reads_only_and_saves_each_read_of_each_round(tmp_path):
    az = _Az()
    clock = [T]

    def now():
        return clock[0]

    def sleep(s):
        clock[0] += timedelta(seconds=s)
    n = lev2.fetch("vm-celebrimbor-gondolin", tmp_path / "reads", T.isoformat(), 30, 60, az=az, sleep=sleep, now=now)
    assert n == 3                                                # at 0, 30 and 60 s
    for args in az.calls:                                        # GET only
        assert args[:2] in (["vm", "list"], ["vm", "show"]) or "show" in args[:4] or args[:3] == ["rest", "--method", "get"]
        assert not any(w in args for w in ("create", "delete", "update", "set", "put", "post", "patch", "invoke"))
    t = json.loads((tmp_path / "reads" / "targets.json").read_text())
    assert t["nsgs"] == [NSG] and t["disks"] == [DISK]
    files = sorted(p.name for p in (tmp_path / "reads" / "round-001").iterdir())
    assert files == ["00-uri-vm.json", "01-uri-nic.json", "02-uri-disk.json", "03-uri-nsg.json", "04-group-group.json"]
    rec = json.loads((tmp_path / "reads" / "round-002" / "00-uri-vm.json").read_text())
    assert rec["pages"] == 2 and not rec["cut"] and len(rec["events"]) == 1
    url = next(a[4] for a in az.calls if a[:3] == ["rest", "--method", "get"])
    assert "resourceUri+eq" in url and "eventTimestamp+le" in url


def test_fetch_refuses_a_vm_outside_the_bench():
    with pytest.raises(lev2.Lev2Error, match="pas du banc"):
        lev2.fetch("vm-celebrimbor-gondolin", Path("unused"), T.isoformat(), 30, 30, az=_Az(zone="production"))


def test_fetch_refuses_inside_a_code_session(monkeypatch, tmp_path, capsys):
    called = []
    monkeypatch.setattr(lev2.bs, "az_json", lambda *a, **k: called.append(a))
    monkeypatch.setenv("EREGION_AGENT_SESSION", "1")
    assert lev2.main(["fetch", "--vm", "vm-celebrimbor-gondolin", "--out", str(tmp_path / "x")]) == 1
    assert "session de code" in capsys.readouterr().err and called == []
    monkeypatch.delenv("EREGION_AGENT_SESSION")
    monkeypatch.chdir(ROOT)                                       # a lot's worktree, or the repository
    if ".claude" in ROOT.parts:
        assert lev2.main(["fetch", "--vm", "vm-celebrimbor-gondolin", "--out", str(tmp_path / "x")]) == 1
        assert called == []


def test_a_next_page_outside_arm_is_refused():
    with pytest.raises(lev2.Lev2Error):
        lev2.get_pages("https://management.azure.com/x", az=lambda a: {"value": [], "nextLink": "https://example.org/n"})


def test_the_script_names_no_tool_that_writes():
    text = (ROOT / "scripts" / "bench_lev2.py").read_text()
    for verb in ('"create"', '"delete"', '"update"', '"invoke"', "--method put", "--method post", "--method patch"):
        assert verb not in text
