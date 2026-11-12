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
    assert files == ["00-uri-vm.json", "01-uri-nic.json", "02-uri-disk.json", "03-uri-nsg.json", "04-uri-subnet.json",
                     "05-group-group.json"]
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


def _one_round(tmp_path: Path, events: list[dict]) -> Path:
    d = tmp_path / "reads"
    (d / "round-001").mkdir(parents=True)
    (d / "targets.json").write_text(json.dumps(_targets()))
    (d / "round-001" / "00-group-group.json").write_text(json.dumps({
        "fetched_at": (T + timedelta(minutes=10)).isoformat(), "how": "group", "what": "group",
        "value": "rg-celebrimbor", "pages": 1, "cut": False, "events": events}))
    return d


def test_two_gestures_of_one_operation_are_never_read_as_one(tmp_path):
    """Review round 1: each gesture is bounded by the next one noted of the same operation."""
    rule = "Microsoft.Network/networkSecurityGroups/securityRules/write"
    d = _one_round(tmp_path, [_event(NSG + "/securityRules/a", rule, T + timedelta(seconds=3)),
                              _event(VM, rule, T + timedelta(seconds=63))])
    out = lev2.report(d, f"{T.isoformat()} {rule} first\n{(T + timedelta(seconds=60)).isoformat()} {rule} second\n")
    rows = {ln.split("|")[1].strip(): ln for ln in out.splitlines() if ln.startswith("| ") and "`" in ln}
    assert "une règle de NSG" in rows["first"] and "la VM" not in rows["first"]
    assert "la VM" in rows["second"] and "une règle de NSG" not in rows["second"]


def test_a_failure_says_its_status_its_code_and_whether_it_counts(tmp_path):
    """The guide's gesture 8: a `grant-access` on an attached disk may come back Conflict; the report
    says the status, the code, and the verdict Glorfindel gives it (REC1b's refusal, or a failure)."""
    sas = "Microsoft.Compute/disks/beginGetAccess/action"

    def failed(at, status, code, op_id):
        e = _event(DISK, sas, at, status="Failed")
        e.update({"operationId": op_id, "properties": {
            "statusCode": status, "statusMessage": json.dumps({"error": {"code": code}})}})
        return e
    d = _one_round(tmp_path, [failed(T + timedelta(seconds=2), "Conflict", "OperationNotAllowed", "op-1"),
                              failed(T + timedelta(seconds=62), "Conflict", "SomethingElse", "op-2")])
    out = lev2.report(d, f"{T.isoformat()} {sas} refused\n{(T + timedelta(seconds=60)).isoformat()} {sas} failed\n")
    rows = {ln.split("|")[1].strip(): ln for ln in out.splitlines() if ln.startswith("| ") and "`" in ln}
    assert "`Conflict` `OperationNotAllowed` : refus de la plateforme, écarté" in rows["refused"]
    assert "`Conflict` `SomethingElse` : un échec, il compte" in rows["failed"]


# ── LEV2b (#763): the three defects of the tool seen on the bench on 12/11 ─────────────────────────

@pytest.fixture
def no_outside(monkeypatch, tmp_path):
    """`az`, `ssh`, `docker`, `terraform`: fakes on the PATH that refuse, and the script's own ways to
    them that raise. The report reads files only; a call to any of them fails the test."""
    called: list = []
    bin_dir = tmp_path / "refusing-bin"
    bin_dir.mkdir()
    for tool in ("az", "ssh", "docker", "terraform"):
        (bin_dir / tool).write_text(f"#!/bin/sh\necho '{tool} refusé par le test' >&2\nexit 97\n")
        (bin_dir / tool).chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")

    def refuse(*a, **k):
        called.append(a)
        raise AssertionError(f"an outside call from the report: {a}")
    monkeypatch.setattr(lev2.bs, "az_json", refuse)
    monkeypatch.setattr(lev2.bs, "run", refuse)
    yield called
    assert called == []


def _rows(out: str) -> dict[str, str]:
    return {ln.split("|")[1].strip(): ln for ln in out.splitlines() if ln.startswith("| ") and "`" in ln}


SAS = "Microsoft.Compute/disks/beginGetAccess/action"


def _sas(at, status, op_id, event_id, *, code="", http=""):
    """A `grant-access` event of the shape the bench read on 12/11: its HTTP status in
    `properties.statusCode` and in `subStatus`, its code in the JSON of `statusMessage`."""
    e = _event(DISK, SAS, at, status=status)
    e.update({"operationId": op_id, "eventDataId": event_id})
    if http:
        e["subStatus"] = {"value": http, "localizedValue": f"{http} (HTTP Status Code: 409)"}
        e["properties"] = {"statusCode": http, "statusMessage": json.dumps(
            {"error": {"code": code, "message": "Access not permitted because disk x is attached"}})}
    return e


def _rounds(tmp_path: Path, rounds: list[list[dict]]) -> Path:
    """Each round reads the same events twice, exactly (the disk) and through the group."""
    d = tmp_path / "reads"
    d.mkdir(parents=True)
    (d / "targets.json").write_text(json.dumps(_targets()))
    for n, events in enumerate(rounds, 1):
        (d / f"round-{n:03d}").mkdir()
        for i, (how, what) in enumerate([("uri", "disk"), ("group", "group")]):
            (d / f"round-{n:03d}" / f"{i:02d}-{how}-{what}.json").write_text(json.dumps({
                "fetched_at": (T + timedelta(minutes=n)).isoformat(), "how": how, "what": what,
                "value": DISK if how == "uri" else "rg-celebrimbor", "pages": 1, "cut": False, "events": events}))
    return d


def test_a_conflict_under_its_own_code_is_said_as_azure_wrote_it_and_why_it_counts(tmp_path, no_outside):
    """Defect 1: the disk's refusal of 12/11 said « Conflict conflict : un échec, il compte », read as a
    comparison by case. The code was `Conflict`, not `OperationNotAllowed`: Glorfindel counts it
    (REC1b's refusal is the pair), and the line now says so, the code as Azure wrote it."""
    started = _sas(T + timedelta(seconds=1), "Started", "op-1", "e-1")
    conflict = _sas(T + timedelta(seconds=2), "Failed", "op-1", "e-2", code="Conflict", http="Conflict")
    out = lev2.report(_rounds(tmp_path, [[started, conflict]]), f"{T.isoformat()} {SAS} disk-sas\n")
    row = _rows(out)["disk-sas"]
    assert "`Conflict` `Conflict` : un échec, il compte" in row and "conflict`" not in row
    assert "n'écarte un `Conflict` que sous le code `OperationNotAllowed`" in row
    # The comparison is never by case: the same refusal in other cases is REC1b's, left out.
    upper = _sas(T + timedelta(seconds=2), "FAILED", "op-1", "e-2", code="operationNotAllowed", http="CONFLICT")
    out = lev2.report(_rounds(tmp_path / "b", [[started, upper]]), f"{T.isoformat()} {SAS} disk-sas\n")
    assert "`CONFLICT` `operationNotAllowed` : refus de la plateforme, écarté" in _rows(out)["disk-sas"]


def test_an_event_read_in_several_rounds_is_judged_once(tmp_path, no_outside):
    """Each round reads the same events again, exactly and through the group. Glorfindel reads each
    once: a refusal whose `Started` was read one round before it is still REC1b's refusal."""
    started = _sas(T + timedelta(seconds=1), "Started", "op-1", "e-1")
    refusal = _sas(T + timedelta(seconds=2), "Failed", "op-1", "e-2", code="OperationNotAllowed", http="Conflict")
    d = _rounds(tmp_path, [[started], [started, refusal], [started, refusal]])
    row = _rows(lev2.report(d, f"{T.isoformat()} {SAS} disk-sas\n"))["disk-sas"]
    assert "refus de la plateforme, écarté" in row and "compte" not in row


def test_a_refusal_whose_operation_still_counts_is_never_said_left_out(tmp_path, no_outside):
    """Two `Started` under one operation, one refusal: Glorfindel keeps the one left over (a command cut,
    hidden behind a later refusal, REC1b). The refusal is not said « écarté »."""
    s1 = _sas(T + timedelta(seconds=1), "Started", "op-1", "e-1")
    s2 = _sas(T + timedelta(seconds=1, milliseconds=500), "Started", "op-1", "e-3")
    refusal = _sas(T + timedelta(seconds=2), "Failed", "op-1", "e-2", code="OperationNotAllowed", http="Conflict")
    d = _rounds(tmp_path, [[s1, s2, refusal]])
    row = _rows(lev2.report(d, f"{T.isoformat()} {SAS} disk-sas\n"))["disk-sas"]
    assert "mais son opération compte" in row and "écarté" not in row


def test_the_name_of_an_operation_is_no_identifier(tmp_path, no_outside):
    """Defect 2: the mask read `microsoft.resources<ressource>` for the operation of gesture 6. An
    operation's path is kept; an ARM id, even after the same namespace, is masked."""
    op = "Microsoft.Resources/subscriptions/resourceGroups/write"
    for text in (f"`{op}`", op, op.upper(), f"`{op.upper()}`", "microsoft.resources/subscriptions/read",
                 f"| `{op.lower()}` | oui |", "Microsoft.Resources/subscriptions/resourceGroups/deployments/write",
                 "Microsoft.Resources/subscriptions/tagNames/tagValues/delete."):
        assert lev2.bs.scrub(text) == text
    letters = "abcdef01-2345-6789-abcd-ef0123456789"           # a subscription id that starts with letters
    for text in (f"https://management.azure.com/subscriptions/{SUB}/resourceGroups/rg-celebrimbor",
                 f"Microsoft.Resources/subscriptions/{letters}/resourceGroups/rg-celebrimbor",
                 "Microsoft.Resources/subscriptions/resourceGroups/rg-celebrimbor",
                 "--scope /subscriptions/resourcegroups/celebrimbor", VM):
        said = lev2.bs.scrub(text)
        assert "celebrimbor" not in said and "<ressource>" in said and not GUID.search(said), said
    # A name of letters only, right after the namespace, is no operation (review round 1): masked,
    # whatever follows it and whatever its case.
    for tail in ("", "`", ".", "'", "’", "/providers/x", "/write", "/providers/Microsoft.Compute/disks/write"):
        for text in (f"Microsoft.Resources/subscriptions/resourceGroups/gondolin{tail}",
                     f"MICROSOFT.RESOURCES/SUBSCRIPTIONS/RESOURCEGROUPS/GONDOLIN{tail}",
                     f"`microsoft.resources/subscriptions/write/gondolin{tail}`"):
            said = lev2.bs.scrub(text)
            assert "gondolin" not in said.lower() and "<ressource>" in said, said
    d = _one_round(tmp_path, [_event(RG, op, T + timedelta(seconds=2))])
    row = _rows(lev2.report(d, f"{T.isoformat()} {op} group-tag\n"))["group-tag"]
    assert f"`{op.lower()}` | oui | le groupe" in row


def test_another_resource_is_named_by_its_type_and_its_place_never_its_name(tmp_path, no_outside):
    """Defect 3: `disk-tag` said « une autre ressource » — on 12/11, a disk of the group outside the VM,
    the one gesture 15 creates, written within the hour."""
    other_sub = RG.replace(SUB, "99999999-0000-0000-0000-000000000000")
    disks = "Microsoft.Compute/disks/write"
    events = [_event(f"{RG}/providers/Microsoft.Compute/disks/eregion-lev2-disk", disks, T + timedelta(seconds=2)),
              _event(f"/subscriptions/{SUB}/resourceGroups/rg-elsewhere/providers/Microsoft.Compute/disks/far-disk",
                     disks, T + timedelta(seconds=3)),
              _event(f"{other_sub}/providers/Microsoft.Compute/disks/twin-disk", disks, T + timedelta(seconds=4)),
              _event(DISK, disks, T + timedelta(seconds=5))]
    out = lev2.report(_one_round(tmp_path, events), f"{T.isoformat()} {disks} disk-tag\n")
    row = _rows(out)["disk-tag"]
    assert "un disque" in row
    assert "une autre ressource (`microsoft.compute/disks`, du groupe de la VM, hors de la VM)" in row
    assert "une autre ressource (`microsoft.compute/disks`, d'un autre groupe)" in row
    assert "une autre ressource (`microsoft.compute/disks`, d'un autre abonnement)" in row
    for name in ("eregion-lev2-disk", "far-disk", "twin-disk", "elsewhere"):
        assert name not in out
    t = _targets()
    assert lev2.elsewhere(f"{RG}/providers/Microsoft.Network/virtualNetworks/vnet2/subnets/db", t) == \
        "une autre ressource (`microsoft.network/virtualnetworks/subnets`, du groupe de la VM, hors de la VM)"
    # An id out of shape never says a name where a type is read: a type's words come from a closed
    # list, with a hyphen or without (review round 1).
    for name in ("lev2-secret-name", "secretname"):
        odd = lev2.elsewhere(f"{RG}/providers/Microsoft.Compute/disks/d/{name}/x", t)
        assert name not in odd and "`microsoft.compute/disks/?`" in odd, odd
    assert "secretns" not in lev2.elsewhere(f"{RG}/providers/secretns/disks/d", t)
    # A resource at the subscription's level is of the subscription, never of a group.
    assert lev2.elsewhere(f"/subscriptions/{SUB}/providers/Microsoft.Authorization/roleAssignments/x", t) == \
        "une autre ressource (`microsoft.authorization/roleassignments`, de l'abonnement de la VM)"
    assert lev2.elsewhere(f"{other_sub.split('/resourceGroups')[0]}/providers/Microsoft.Authorization/"
                          "roleAssignments/x", t).endswith("d'un autre abonnement)")
    assert lev2.elsewhere(f"/subscriptions/{SUB}/resourceGroups/rg-elsewhere", t) == "un autre groupe"
    assert lev2.elsewhere("", t) == "une autre ressource (sans identifiant ARM)"
