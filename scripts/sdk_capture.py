#!/usr/bin/env python3
"""SDK1b (#1017): the bodies Azure sends for the ten `azure.mgmt` operations Glorfindel's adapters read
most, captured at the bench, read-only, anonymized before anything is written. The maintainer's
gesture, with his own identity: a session never runs it.

    az login                                                  # your identity (Reader is enough)
    cd ~/eregion
    .venv/bin/python scripts/sdk_capture.py capture \\
        --subscription "$(az account show --query id -o tsv)" \\
        --vm <group>/<vm> --vault <group>/<vault> --out ~/eregion-banc/sdk1b
    .venv/bin/python scripts/sdk_capture.py check ~/eregion-banc/sdk1b \\
        --forbid <group> --forbid <vm> --forbid <vault>

The subscription is given on the command line, read from `az account show` at that moment: an
`AZURE_SUBSCRIPTION_ID` exported by hand may have been replaced since (direnv reloading `.envrc`).
Then **read each file** (a few KB) — the last net, see below — and copy them into
tests/unit/sdk_bodies/ in the branch that replaces the hypotheses (SDK1b's second time):
`cp ~/eregion-banc/sdk1b/*.json tests/unit/sdk_bodies/`.

**What it reads**, and nothing else — the closed list `READS`, `get` and `list` only:

- every NSG and every network interface of the subscription (`list_all`, what the watch's pass reads
  each minute), kept only for the groups it is given (`--vm`'s, `--vault`'s, `--group`): the bench's;
- each `--vm` (`virtual_machines.get`), each of its network interfaces, their subnets, every NSG that
  governs them (their own and their subnet's) and its rules (`security_rules.list`);
- with `--vault`: the vault's jobs (`backup_jobs.list`) of the named VMs, the newest ten; the details of
  the newest job of each kind (`job_details.get`); each VM's protected item (its stored names, as the
  adapters ask for them) and its recovery points.

**Its guards.** A read outside `READS` is refused before any call; every client's transport refuses
any method but GET before it leaves (`ReadOnlyTransport`: a `begin_*`, a `create`, an `update`, a
`delete`, and ARM's own resource provider registration, all refused); the identity is `az login`'s
(`AzureCliCredential`), never a credential of the environment. tests/unit/test_sdk_capture.py reads
this file and fails on any write it would call. A response the SDK retried (a 429, then a 200) is
kept once: the last 2xx of each request.

**What it writes**: one file per operation, `<sdk>.<group>.<operation>.json` — the operation, the SDK's
version, the API version the request carried, and each response as the API sent it (its raw body,
`raw_response_hook`, never the SDK's object written back), anonymized. Into `--out` only, a folder
under no git checkout (this repository, its worktrees, any other: the review comes before the copy).
It prints counts, never a value.

**The anonymization** (scripts/sdk_anonymize.py): GUIDs, names, the marks of Glorfindel's rule names,
IPv4 and IPv6 addresses, MACs, e-mail addresses, domains outside Azure's, tag keys and values, free
text, secrets — the same real always the same stand-in, across files, the shape of an ARM id kept.
Then a check, before anything is written: no real value it met may remain, and every value of a
known form must be a stand-in's; either fails, nothing is written, the kind and the place said,
never the value. `check` runs the second half on a folder.

**The last net is the maintainer's reading.** A word of free text that no id, no key and no form
names (a person's name, a server's, in a text Azure writes under a key the anonymization does not
list) cannot be told from any other word: read every file before copying it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import sdk_anonymize as an  # noqa: E402,F401 — the module the tests read and patch, as this one imports it
from sdk_anonymize import Anonymizer, Leak, anonymize, structural  # noqa: E402,F401

REPO = _HERE.parent

# The closed list of reads: "<sdk>.<operation group>.<operation>". Nothing else is ever called.
READS = (
    "network.network_security_groups.list_all",
    "network.network_interfaces.list_all",
    "compute.virtual_machines.get",
    "network.network_interfaces.get",
    "network.subnets.get",
    "network.security_rules.list",
    "network.network_security_groups.get",
    "backup.backup_jobs.list",
    "backup.job_details.get",
    "backup.recovery_points.list",
    "backup.protected_items.get",       # the item's stored names, as the adapters ask for them
)
READ_VERBS = frozenset({"get", "list", "list_all"})
PACKAGES = {"network": "azure-mgmt-network", "compute": "azure-mgmt-compute",
            "backup": "azure-mgmt-recoveryservicesbackup"}
JOBS_KEPT = 10


class Refused(RuntimeError):
    """A read outside the closed list, or a request that is not a GET: never sent."""


# ── the clients: reads only ─────────────────────────────────────────────────────────────────────

def _read_only_transport(session=None):
    """azure-core's RequestsTransport, refusing any method but GET before it leaves — the last
    gate of every request, ARM's own resource provider registration included."""
    from azure.core.pipeline.transport import RequestsTransport

    class ReadOnlyTransport(RequestsTransport):
        def send(self, request, **kwargs):
            if str(request.method).upper() != "GET":
                raise Refused(f"sdk_capture: {request.method} refused — this script reads only")
            return super().send(request, **kwargs)

    if session is None:
        return ReadOnlyTransport()
    return ReadOnlyTransport(session=session, session_owner=False)


def clients(credential, subscription: str, session=None) -> dict:
    """The three SDKs' clients, each on a read-only transport (`session`: the tests' socket)."""
    from azure.mgmt.compute import ComputeManagementClient
    from azure.mgmt.network import NetworkManagementClient
    from azure.mgmt.recoveryservicesbackup import RecoveryServicesBackupClient
    return {
        "network": NetworkManagementClient(credential, subscription, transport=_read_only_transport(session)),
        "compute": ComputeManagementClient(credential, subscription, transport=_read_only_transport(session)),
        "backup": RecoveryServicesBackupClient(credential, subscription, transport=_read_only_transport(session)),
    }


def _read(clients_: dict, op: str, *args, **kwargs) -> list[dict]:
    """One read of the closed list, its responses as the API sent them: [{"url", "status",
    "body"}], one per page. Anything else is refused before any call."""
    if op not in READS:
        raise Refused(f"sdk_capture: {op} is not in the closed list of reads")
    sdk, group, verb = op.split(".")
    if verb not in READ_VERBS:
        raise Refused(f"sdk_capture: {op} is not a read")
    call = getattr(getattr(clients_[sdk], group), verb)
    pages: list = []
    result = call(*args, raw_response_hook=pages.append, **kwargs)
    if verb != "get":
        for _ in result:                       # the pager reads every page
            pass
    # The hook sees every attempt (it runs after the retry policy): a 429 then a 200 are two. Kept:
    # the last 2xx of each request, in the order the requests were first sent.
    kept: dict[str, object] = {}
    for p in pages:
        if 200 <= p.http_response.status_code < 300:
            kept[p.http_request.url] = p
    return [{"url": p.http_request.url, "status": p.http_response.status_code,
             "body": json.loads(p.http_response.text() or "null")} for p in kept.values()]


# ── the capture ─────────────────────────────────────────────────────────────────────────────────

def _segments(arm_id: str) -> dict:
    """An ARM id's resource group and its (type → name) pairs, types lowercase."""
    parts = [p for p in str(arm_id or "").split("/") if p]
    low = [p.lower() for p in parts]
    out: dict = {"rg": parts[low.index("resourcegroups") + 1] if "resourcegroups" in low else ""}
    if "providers" in low:
        rest = parts[low.index("providers") + 2:]
        out |= {rest[i].lower(): rest[i + 1] for i in range(0, len(rest) - 1, 2)}
    return out


def _in_groups(item: dict, groups: set[str]) -> bool:
    return _segments(item.get("id", "")).get("rg", "").lower() in groups


def _kept(responses: list[dict], groups: set[str]) -> list[dict]:
    """A subscription-wide listing, each page's items kept for the named groups only."""
    out = []
    for r in responses:
        b = r["body"] if isinstance(r["body"], dict) else {}
        out.append({**r, "body": {**b, "value": [i for i in b.get("value") or [] if _in_groups(i, groups)]}})
    return out


def _api_version(url: str) -> str:
    m = re.search(r"[?&]api-version=([^&]+)", url)
    return m.group(1) if m else ""


def capture(clients_: dict, vms: list[tuple[str, str]], vault: tuple[str, str] | None = None,
            groups: set[str] | None = None, say=print) -> dict[str, list[dict]]:
    """Every read, its responses by operation. A read that fails is said (its status), its
    operation left without a body; nothing else stops."""
    got: dict[str, list[dict]] = {}
    groups = {g.lower() for g in (groups or set())} | {rg.lower() for rg, _ in vms}
    if vault:
        groups.add(vault[0].lower())

    def read(op, *args, **kwargs) -> list[dict]:
        try:
            responses = _read(clients_, op, *args, **kwargs)
        except Refused:
            raise
        except Exception as exc:               # 403, 404, throttled: said, the rest goes on
            say(f"  {op}: not read ({type(exc).__name__}, {vars(exc).get('status_code', '?')})")
            return []
        got.setdefault(op, []).extend(responses)
        return responses

    for op in ("network.network_security_groups.list_all", "network.network_interfaces.list_all"):
        if read(op):
            got[op] = _kept(got[op], groups)
    seen_nsgs: set[str] = set()
    for rg, name in vms:
        _read_vm(read, rg, name, seen_nsgs)
    if vault:
        _read_vault(read, got, vms, vault)
    return got


def _body(responses: list[dict]) -> dict | None:
    """The body of a `get` read, None when it was not read."""
    return responses[-1]["body"] if responses else None


def _read_vm(read, rg: str, name: str, seen_nsgs: set[str]) -> None:
    """A VM, its network interfaces, their subnets, and every NSG that governs them with its rules."""
    vm = _body(read("compute.virtual_machines.get", rg, name))
    if vm is None:
        return
    for ref in ((vm.get("properties") or {}).get("networkProfile") or {}).get("networkInterfaces") or []:
        seg = _segments(ref.get("id", ""))
        nic = _body(read("network.network_interfaces.get", seg["rg"], seg.get("networkinterfaces", "")))
        if nic is None:
            continue
        props = nic.get("properties") or {}
        nsgs = [(props.get("networkSecurityGroup") or {}).get("id")]
        for cfg in props.get("ipConfigurations") or []:
            sub_id = ((cfg.get("properties") or {}).get("subnet") or {}).get("id")
            if sub_id:
                s = _segments(sub_id)
                subnet = _body(read("network.subnets.get", s["rg"], s.get("virtualnetworks", ""), s.get("subnets", "")))
                nsgs.append((((subnet or {}).get("properties") or {}).get("networkSecurityGroup") or {}).get("id"))
        for nsg_id in filter(None, nsgs):
            if nsg_id.lower() not in seen_nsgs:
                seen_nsgs.add(nsg_id.lower())
                n = _segments(nsg_id)
                read("network.network_security_groups.get", n["rg"], n.get("networksecuritygroups", ""))
                read("network.security_rules.list", n["rg"], n.get("networksecuritygroups", ""))


def _read_vault(read, got: dict, vms: list[tuple[str, str]], vault: tuple[str, str]) -> None:
    """The vault's jobs of the named VMs, the details of the newest of each kind, each VM's
    protected item (its stored names) and its recovery points."""
    v_rg, v_name = vault
    if read("backup.backup_jobs.list", v_name, v_rg):
        got["backup.backup_jobs.list"] = _jobs_kept(got["backup.backup_jobs.list"], {n.lower() for _, n in vms})
    newest: dict = {}
    for r in got.get("backup.backup_jobs.list", []):
        for j in (r["body"] or {}).get("value") or []:
            p = j.get("properties") or {}
            key = (str(p.get("entityFriendlyName", "")).lower(), p.get("operation"))
            if key not in newest or str(p.get("startTime", "")) > newest[key][0]:
                newest[key] = (str(p.get("startTime", "")), j.get("name"))
    for (_vm, operation), (_at, job_name) in sorted(newest.items()):
        if operation in ("Restore", "Backup") and job_name:
            read("backup.job_details.get", v_name, v_rg, job_name)
    for rg, name in vms:
        container, item = f"IaasVMContainer;iaasvmcontainerv2;{rg};{name}", f"VM;iaasvmcontainerv2;{rg};{name}"
        found = _body(read("backup.protected_items.get", v_name, v_rg, "Azure", container, item))
        seg = [x for x in str((found or {}).get("id", "")).split("/") if x]
        low = [x.lower() for x in seg]
        if "protectioncontainers" in low and "protecteditems" in low:
            container, item = seg[low.index("protectioncontainers") + 1], seg[low.index("protecteditems") + 1]
        read("backup.recovery_points.list", v_name, v_rg, "Azure", container, item)


def _jobs_kept(responses: list[dict], names: set[str]) -> list[dict]:
    """The vault's jobs of the named VMs only, the newest JOBS_KEPT, on one page as listed."""
    jobs = [j for r in responses for j in (r["body"] or {}).get("value") or []
            if str((j.get("properties") or {}).get("entityFriendlyName", "")).lower() in names]
    jobs.sort(key=lambda j: str((j.get("properties") or {}).get("startTime", "")), reverse=True)
    first = responses[0]
    return [{**first, "body": {**(first["body"] or {}), "value": jobs[:JOBS_KEPT], "nextLink": None}}]


def files(got: dict[str, list[dict]], captured: str, versions: dict[str, str]) -> dict[str, dict]:
    """One file per operation, as tests/unit/sdk_bodies/ holds them."""
    out = {}
    for op, responses in got.items():
        if not responses:
            continue
        sdk = op.split(".")[0]
        out[f"{op}.json"] = {
            "operation": op, "source": "measured", "captured": captured,
            "sdk": f"{PACKAGES[sdk]}=={versions.get(sdk, '?')}",
            "api_version": _api_version(responses[0]["url"]),
            "note": "Measured at the bench (scripts/sdk_capture.py), anonymized.",
            "responses": [{"url": _path_and_query(r["url"]), "status": r["status"], "body": r["body"]}
                          for r in responses],
        }
    return out


def _path_and_query(url: str) -> str:
    """The request's path, decoded (a backup container's `;` is sent as `%3B`: encoded, the names
    after it escaped the anonymization), and its query; its host left out (always ARM's)."""
    from urllib.parse import unquote, urlsplit
    parts = urlsplit(url)
    return unquote(parts.path) + (f"?{parts.query}" if parts.query else "")


# ── the command ─────────────────────────────────────────────────────────────────────────────────

def _pair(text: str) -> tuple[str, str]:
    group, _, name = text.partition("/")
    if not group or not name or "/" in name:
        raise argparse.ArgumentTypeError(f"expected <group>/<name>, got {text!r}")
    return group, name


def _outside_repo(path: Path) -> Path:
    """`--out`, resolved, under no git checkout: neither this repository nor the one its worktree
    belongs to (a worktree's `.git` is a file), nor any other — a folder that holds a `.git`, itself
    or above. The files are read before they are copied into tests/unit/sdk_bodies/."""
    resolved = path.expanduser().resolve()
    for folder in (resolved, *resolved.parents):
        if folder == REPO or (folder / ".git").exists():
            raise SystemExit(f"sdk_capture: --out must be under no git checkout — {folder} holds one; "
                             "the files are read before they are copied into tests/unit/sdk_bodies/")
    return resolved


def _versions() -> dict[str, str]:
    from importlib.metadata import version
    return {sdk: version(pkg) for sdk, pkg in PACKAGES.items()}


def write(out_dir: Path, anonymized: dict[str, dict]) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, cap in sorted(anonymized.items()):
        path = out_dir / name
        path.write_text(json.dumps(cap, indent=2, ensure_ascii=False) + "\n")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    cap = sub.add_parser("capture", help="read the bench, anonymize, write the bodies")
    cap.add_argument("--vm", type=_pair, action="append", required=True, help="<group>/<vm>, again for more")
    cap.add_argument("--vault", type=_pair, help="<group>/<vault>")
    cap.add_argument("--group", action="append", default=[], help="one more group kept from the listings")
    cap.add_argument("--out", type=Path, required=True, help="a folder outside this repository")
    cap.add_argument("--subscription", default=os.environ.get("AZURE_SUBSCRIPTION_ID", ""))
    chk = sub.add_parser("check", help="check a folder of bodies: nothing but stand-ins")
    chk.add_argument("folder", type=Path)
    chk.add_argument("--forbid", action="append", default=[], help="a word that must not appear")
    args = parser.parse_args(argv)

    if args.cmd == "check":
        loaded = {p.name: json.loads(p.read_text()) for p in sorted(args.folder.expanduser().glob("*.json"))}
        forbid = tuple(args.forbid) + tuple(v for v in (os.environ.get("AZURE_SUBSCRIPTION_ID"),
                                                         os.environ.get("AZURE_TENANT_ID")) if v)
        leaks = structural(loaded, forbid)
        for line in leaks:
            print(f"  {line}")
        print(f"sdk_capture check: {len(loaded)} file(s), {'NOT clean' if leaks else 'clean'}")
        return 1 if leaks or not loaded else 0

    if not args.subscription:
        raise SystemExit("sdk_capture: no subscription — export AZURE_SUBSCRIPTION_ID (az account show)")
    out_dir = _outside_repo(args.out)
    from azure.identity import AzureCliCredential
    got = capture(clients(AzureCliCredential(), args.subscription), args.vm, args.vault, set(args.group))
    captured = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    seeds = {g: "rg" for g, _ in args.vm} | {n: "vm" for _, n in args.vm}
    if args.vault:
        seeds |= {args.vault[0]: "rg", args.vault[1]: "rsv"}
    seeds |= {g: "rg" for g in args.group}
    anonymized, a = anonymize(files(got, captured, _versions()), seeds, args.subscription)
    for path in write(out_dir, anonymized):
        print(f"  wrote {path.name}")
    print(f"sdk_capture: {len(anonymized)} file(s) in {out_dir} — replaced {len(a.guids)} GUID(s), "
          f"{len(a.names)} name(s), {len(a.ips)} address(es), {len(a.macs)} MAC(s), {len(a.emails)} "
          f"e-mail(s), {len(a.marks)} mark(s), {a.texts} text(s). Read them, then `check`.")
    missing = [op for op in READS if op not in got and op != "backup.protected_items.get"]
    if missing:
        print("  no body for: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
