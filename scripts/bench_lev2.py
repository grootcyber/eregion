#!/usr/bin/env python3
"""bench_lev2 — the measure of H7, H9 and H12 on the bench, READ ONLY (LEV2, #690; docs/banc-lev2.md).

  bench_lev2.py fetch --vm NAME --out DIR [--since ISO] [--every 30] [--for 1800]
      the activity log of a bench VM, read as Glorfindel reads it (each resource exactly, each group
      whole), every EVERY seconds for FOR seconds: each answer saved raw under DIR (ids included: the
      operator's machine only, never the repository)
  bench_lev2.py report --dir DIR --gestures FILE [--out FILE]
      what the reads say of the gestures Jonathan wrote by hand (FILE: one line per gesture, its
      time then its operation, `docs/banc-lev2.md`), without any identifier:
        H7  the resource each gesture's events name, and whether a Run Command v1 also leaves an
            extension write under the same caller, at the same moment;
        H9  whether the exact filter (`resourceUri eq`) gives the children of the VM, and the pages
            each read needed (the bound is 20);
        H12 the latency between a gesture and its first reading, read every EVERY seconds.

Nothing is written on Azure: `az vm show`, `az network … show` and `az rest --method get`, under the
operator's `az login`. No tool here writes a gesture: they are typed by hand from the guide. `fetch`
refuses inside a code session (EREGION_AGENT_SESSION, a lot's worktree: scripts/bench_reader.py's
guard), and a VM whose zone (`eregion-zone`) is not `bench`. `report` reads files only: it runs
anywhere, the tests run it on sample logs.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE.parent), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bench_reader  # noqa: E402
import bench_shared as bs  # noqa: E402

ARM = "https://management.azure.com"
BOUND = 20                    # Glorfindel's bound (REC1b, LEV2)
MEASURE_PAGES = 40            # read past it here, to know how far a group goes (H9)
# A gesture's events are looked for from this long before its noted time to this long after — and
# never past the next gesture noted of the same operation, less SKEW_S (the workstation's clock is
# not Azure's): two gestures of one operation are never read as one (review round 1).
BEFORE_S, AFTER_S, SKEW_S = 120, 3600, 20
RUN_COMMAND_V1 = "microsoft.compute/virtualmachines/runcommand/action"
EXTENSION_WRITE = "microsoft.compute/virtualmachines/extensions/write"
SAME_MOMENT_S = 120


class Lev2Error(Exception):
    """Said on stderr, exit 1."""


def _k(rid) -> str:
    return str(rid or "").strip().rstrip("/").lower()


def _epoch(value) -> float | None:
    return bs.epoch(value)


# ── fetch ────────────────────────────────────────────────────────────────────

def targets_of(vm: dict, nics: list[dict], subnets: dict[str, dict]) -> dict:
    """The VM's resources from `az vm show`, `az network nic show`, `az network vnet subnet show`."""
    storage = vm.get("storageProfile") or {}
    disks = [((storage.get("osDisk") or {}).get("managedDisk") or {}).get("id")]
    disks += [(d.get("managedDisk") or {}).get("id") for d in storage.get("dataDisks") or []]
    nsgs, pips, subs = [], [], []
    for n in nics:
        if (n.get("networkSecurityGroup") or {}).get("id"):
            nsgs.append(n["networkSecurityGroup"]["id"])
        for c in n.get("ipConfigurations") or []:
            if (c.get("publicIPAddress") or {}).get("id"):
                pips.append(c["publicIPAddress"]["id"])
            if (c.get("subnet") or {}).get("id"):
                subs.append(c["subnet"]["id"])
            sub = subnets.get(_k((c.get("subnet") or {}).get("id")))
            if sub and (sub.get("networkSecurityGroup") or {}).get("id"):
                nsgs.append(sub["networkSecurityGroup"]["id"])
    vm_id = vm["id"]
    group = "/".join(vm_id.split("/")[:5])
    return {"vm": vm_id, "group": group, "nics": [n["id"] for n in nics], "disks": [d for d in disks if d],
            "nsgs": sorted(set(nsgs), key=str.lower), "public_ips": sorted(set(pips), key=str.lower),
            "identities": sorted(((vm.get("identity") or {}).get("userAssignedIdentities") or {})),
            "subnets": sorted(set(subs), key=str.lower)}


def reads_of(t: dict) -> list[tuple[str, str, str]]:
    """(how, what, value) of each read Glorfindel makes (glorfindel/providers/azure/door.py)."""
    exact = [("vm", t["vm"])] + [("nic", n) for n in t["nics"]] + [("disk", d) for d in t["disks"]]
    exact += [("nsg", n) for n in t["nsgs"]] + [("public_ip", p) for p in t["public_ips"]]
    exact += [("identity", i) for i in t["identities"]] + [("subnet", x) for x in t.get("subnets") or []]
    groups = sorted({x.split("/")[4] for x in [t["vm"], *t["nsgs"], *t["nics"], *(t.get("subnets") or [])]
                     if len(x.split("/")) > 4},
                    key=str.lower)
    return [("uri", what, rid) for what, rid in exact] + [("group", "group", g) for g in groups]


def activity_url(sub: str, how: str, value: str, since: str, until: str) -> str:
    field = "resourceUri" if how == "uri" else "resourceGroupName"
    query = urllib.parse.urlencode({
        "api-version": "2015-04-01",
        "$filter": f"eventTimestamp ge '{since}' and eventTimestamp le '{until}' and {field} eq '{value}'",
        "$select": ("caller,claims,operationName,operationId,eventTimestamp,submissionTimestamp,status,"
                    "subStatus,properties,resourceId,resourceGroupName,eventDataId")})
    return f"{ARM}/subscriptions/{sub}/providers/Microsoft.Insights/eventtypes/management/values?{query}"


def get_pages(url: str, az=bs.az_json) -> dict:
    """Every page, MEASURE_PAGES at most: {"pages", "cut", "events"} — GET only, ARM only."""
    events, pages = [], 0
    while url and pages < MEASURE_PAGES:
        if not url.startswith(f"{ARM}/"):
            raise Lev2Error("une page suivante hors d'Azure Resource Manager : refusée")
        body = az(["rest", "--method", "get", "--uri", url]) or {}
        pages += 1
        events += list(body.get("value") or [])
        url = body.get("nextLink")
    return {"pages": pages, "cut": bool(url), "events": events}


def bench_vm(name: str, az=bs.az_json) -> dict:
    """The VM of that name, alone in the subscription, of the zone `bench`; else refused."""
    found = [v for v in (az(["vm", "list", "--query", "[].{name:name, id:id}"]) or [])
             if str(v.get("name") or "").lower() == name.lower()]
    if len(found) != 1:
        raise Lev2Error(f"{len(found)} VM nommée(s) {name} : il en faut une seule")
    vm = az(["vm", "show", "--ids", found[0]["id"]]) or {}
    zone = str((vm.get("tags") or {}).get("eregion-zone") or "")
    if zone.lower() != "bench":
        raise Lev2Error(f"{name} n'est pas du banc (eregion-zone={zone or 'absent'}) : refusé")
    return vm


def fetch(name: str, out: Path, since: str, every: float, duration: float, az=bs.az_json,
          sleep=time.sleep, now=lambda: datetime.now(timezone.utc)) -> int:
    """The rounds of reads, saved under `out`. Returns the number of rounds."""
    vm = bench_vm(name, az)
    nics = [az(["network", "nic", "show", "--ids", r["id"]]) or {} for r in
            (vm.get("networkProfile") or {}).get("networkInterfaces") or []]
    subnets = {}
    for n in nics:
        for c in n.get("ipConfigurations") or []:
            sid = (c.get("subnet") or {}).get("id")
            if sid and _k(sid) not in subnets:
                subnets[_k(sid)] = az(["network", "vnet", "subnet", "show", "--ids", sid]) or {}
    t = targets_of(vm, nics, subnets)
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    (out / "targets.json").write_text(json.dumps(t, indent=1))
    sub = t["vm"].split("/")[2]
    start = now()
    rounds = 0
    while True:
        rounds += 1
        folder = out / f"round-{rounds:03d}"
        folder.mkdir(exist_ok=True)
        until = now().strftime("%Y-%m-%dT%H:%M:%SZ")
        for i, (how, what, value) in enumerate(reads_of(t)):
            at = now().isoformat()
            try:
                got = get_pages(activity_url(sub, how, value, since, until), az)
                rec = {"fetched_at": at, "how": how, "what": what, "value": value, **got}
            except Exception as exc:   # noqa: BLE001 — said in the file, the round goes on
                rec = {"fetched_at": at, "how": how, "what": what, "value": value, "error": bs.scrub(str(exc))[:200]}
            (folder / f"{i:02d}-{how}-{what}.json").write_text(json.dumps(rec, indent=1))
        if (now() - start).total_seconds() + every > duration:
            return rounds
        sleep(every)


# ── report ───────────────────────────────────────────────────────────────────

def read_gestures(text: str) -> list[dict]:
    """`<ISO time> <operation> [label…]` per line; `#` starts a comment."""
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2 or _epoch(parts[0]) is None or "/" not in parts[1]:
            raise Lev2Error(f"geste illisible : {bs.scrub(line)[:80]}")
        out.append({"at": _epoch(parts[0]), "op": parts[1].lower(), "label": " ".join(parts[2:])})
    return out


def _door_targets(t: dict) -> dict:
    return {"vm": t["vm"], "group": t["group"], "nics": t["nics"], "disks": t["disks"],
            "nsgs": {n: None for n in t["nsgs"]}, "public_ips": t["public_ips"], "identities": t["identities"],
            "subnets": t.get("subnets") or []}


def _kind(rid: str, t: dict) -> str:
    from glorfindel.providers.azure.door import _kind_of
    kind = _kind_of(_k(rid), _door_targets(t))
    if kind == "vm_child":
        rest = _k(rid)[len(_k(t["vm"])) + 1:].split("/")
        return f"enfant de la VM ({rest[0]}{'/' + rest[-2] if len(rest) > 2 else ''})"
    if kind is None:
        return elsewhere(rid, t)
    return {"vm": "la VM", "disk": "un disque", "nic": "une carte", "nsg": "un NSG", "nsg_rule": "une règle de NSG",
            "public_ip": "une IP publique", "identity": "une identité", "group": "le groupe",
            "subnet": "le sous-réseau"}.get(kind, str(kind))


# The words a type may say, a closed list (review round 1: a pattern let a name of letters through,
# `…/disks/d/secretname/x`). A word outside it is said `?`: the report says less, never a name.
_NAMESPACES = frozenset({
    "microsoft.compute", "microsoft.network", "microsoft.managedidentity", "microsoft.resources",
    "microsoft.authorization", "microsoft.insights", "microsoft.storage", "microsoft.recoveryservices",
    "microsoft.keyvault", "microsoft.operationalinsights", "microsoft.serialconsole", "microsoft.security",
    "microsoft.maintenance", "microsoft.guestconfiguration", "microsoft.hybridcompute"})
_TYPES = frozenset({
    "virtualmachines", "virtualmachinescalesets", "availabilitysets", "disks", "snapshots", "images",
    "extensions", "runcommands", "restorepointcollections", "restorepoints", "diskencryptionsets",
    "galleries", "sshpublickeys", "networkinterfaces", "ipconfigurations", "networksecuritygroups",
    "securityrules", "applicationsecuritygroups", "publicipaddresses", "virtualnetworks", "subnets",
    "routetables", "routes", "networkwatchers", "flowlogs", "privateendpoints", "loadbalancers",
    "natgateways", "bastionhosts", "userassignedidentities", "tags", "deployments", "roleassignments",
    "roledefinitions", "denyassignments", "locks", "policyassignments", "diagnosticsettings",
    "datacollectionrules", "datacollectionruleassociations", "actiongroups", "activitylogalerts",
    "scheduledqueryrules", "storageaccounts", "vaults", "backupfabrics", "protectioncontainers",
    "protecteditems", "workspaces", "serialports", "configurationassignments",
    "guestconfigurationassignments", "maintenanceconfigurations", "machines"})


def elsewhere(rid, t: dict) -> str:
    """A resource that is none of the VM's, named by its type and its place, never by its name
    (LEV2b, #763: on 12/11, `disk-tag` said « une autre ressource » — a disk of the group outside the
    VM, written within the hour). The type is that of the id's last provider, each of its words read in
    a closed list (_NAMESPACES, _TYPES), any other said `?`."""
    parts, mine = _k(rid).split("/"), _k(t["group"]).split("/")
    if len(parts) < 3 or parts[:2] != ["", "subscriptions"]:
        return "une autre ressource (sans identifiant ARM)"
    other_sub = parts[2] != mine[2]
    if "providers" not in parts[3:]:
        if len(parts) <= 3:
            return "un autre abonnement" if other_sub else "l'abonnement de la VM"
        return "un groupe d'un autre abonnement" if other_sub else "un autre groupe"
    i = len(parts) - 1 - parts[::-1].index("providers")
    words = [w if w in _NAMESPACES else "?" for w in parts[i + 1:i + 2]]
    words += [w if w in _TYPES else "?" for w in parts[i + 2::2]]
    what = "/".join(words) or "?"
    if other_sub:
        where = "d'un autre abonnement"
    elif parts[3] == "providers":
        where = "de l'abonnement de la VM"
    else:
        where = "du groupe de la VM, hors de la VM" if parts[:5] == mine[:5] else "d'un autre groupe"
    return f"une autre ressource (`{what}`, {where})"


def window(gestures: list[dict], i: int) -> tuple[float, float]:
    """[start, end) where gesture `i`'s events are looked for: from BEFORE_S before it (SKEW_S when a
    gesture of the same operation came before), to AFTER_S after it, or to the next gesture of the
    same operation, less SKEW_S."""
    g = gestures[i]
    same = sorted(x["at"] for x in gestures if x["op"] == g["op"])
    before = [a for a in same if a < g["at"]]
    after = [a for a in same if a > g["at"]]
    start = g["at"] - (SKEW_S if before else BEFORE_S)
    end = min([g["at"] + AFTER_S] + [a - SKEW_S for a in after])
    return start, end


def failure_said(events: list[dict]) -> str:
    """What the gesture's failed events say (the guide's gesture 8): their HTTP status and code, and
    whether Glorfindel counts them — an operation the platform refused (`Conflict` under the code
    `OperationNotAllowed`, its one `Started` before it: REC1b, `_refused_operations`) is left out, any
    other failure counts. The status and code are said as Azure wrote them; a `Conflict` under another
    code counts, and the line says why (LEV2b, #763: the disk's `Conflict` `Conflict` of 12/11, read as
    a comparison by case). « — » without a failure."""
    from glorfindel.providers.azure.recovery import _fold, _refused, _refused_operations
    events = list(unique(events).values())
    failed = [e for e in events if _fold((e.get("status") or {}).get("value")) == "failed"]
    if not failed:
        return "—"
    refused = _refused_operations(events)
    said = set()
    for e in failed:
        props = e.get("properties") if isinstance(e.get("properties"), dict) else {}
        status = str(props.get("statusCode") or (e.get("subStatus") or {}).get("value") or "?").strip()
        code = error_code(props.get("statusMessage")) or "?"
        if _fold(e.get("operationId")) in refused:
            verdict = "refus de la plateforme, écarté"
        elif _refused(e):
            verdict = ("refus de la plateforme, mais son opération compte : un autre de ses événements "
                       "n'est pas le `Started` qui le précède (REC1b)")
        elif _fold(status) == "conflict":
            verdict = ("un échec, il compte : Glorfindel n'écarte un `Conflict` que sous le code "
                       "`OperationNotAllowed` (REC1b)")
        else:
            verdict = "un échec, il compte"
        said.add(f"`{status}` `{code}` : {verdict}")
    return " ; ".join(sorted(said))


def error_code(message) -> str:
    """The top-level error code of a status message as Azure wrote it, its case kept (LEV2b, #763: the
    report of 12/11 said « Conflict conflict », the code folded, and read as a comparison by case).
    Glorfindel's verdict still folds both (`_refused`)."""
    body = message
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            return ""
    err = body.get("error") if isinstance(body, dict) else None
    return str(err.get("code") or "").strip() if isinstance(err, dict) else ""


def unique(events: list[dict]) -> dict[str, dict]:
    """Each event once, by Glorfindel's own key (`door._event_key`: its `eventDataId`, else what it is
    made of): every round reads it again, exactly and through the group, as the door reads a VM and its
    group (LEV2b, #763: counted per copy, a `Started` read in one round more than its refusal is left
    over, and the operation is no longer refused)."""
    from glorfindel.providers.azure.door import _event_key
    out: dict[str, dict] = {}
    for e in events:
        out.setdefault(_event_key(e), e)
    return out


def load_rounds(d: Path) -> list[list[dict]]:
    return [[json.loads(f.read_text()) for f in sorted(r.glob("*.json"))] for r in sorted(d.glob("round-*"))]


def _callers(e: dict) -> frozenset[str]:
    claims = e.get("claims") if isinstance(e.get("claims"), dict) else {}
    ids = [e.get("caller"), claims.get("appid"), claims.get("oid"),
           claims.get("http://schemas.microsoft.com/identity/claims/objectidentifier")]
    return frozenset(str(i).lower() for i in ids if i)


def _op(e: dict) -> str:
    return str((e.get("operationName") or {}).get("value") or "").lower()


def report(d: Path, gestures_text: str) -> str:
    t = json.loads((d / "targets.json").read_text())
    gestures = read_gestures(gestures_text)
    rounds = load_rounds(d)
    lines = ["# LEV2 au banc : H7, H9, H12", "",
             f"{len(gestures)} geste(s), {len(rounds)} tour(s) de lecture. Aucun identifiant : des sortes de "
             "ressources, des opérations, des durées.", ""]
    # ── H7 and H12, gesture by gesture
    lines += ["## Les gestes (H7, H12)", "",
              "| Geste | Opération | Lu | Ressource de l'événement (H7) | Par quelle lecture | Statuts | "
              "Un échec : son statut, son code, ce qu'il compte | "
              "Latence de la première lecture (H12) | eventTimestamp − geste | submission − event |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    found_events: dict[int, list[tuple[dict, dict]]] = {}
    for gi, g in enumerate(gestures):
        start, end = window(gestures, gi)
        first, hits = None, []
        for rnd in rounds:
            for rec in rnd:
                for e in rec.get("events") or []:
                    at = _epoch(e.get("eventTimestamp"))
                    if _op(e) == g["op"] and at is not None and start <= at < end:
                        hits.append((rec, e))
                        if first is None:
                            first = _epoch(rec.get("fetched_at"))
        found_events[gi] = hits
        if not hits:
            lines.append(f"| {bs.scrub(g['label'] or '—')} | `{g['op']}` | **non** | — | — | — | — | — | — | — |")
            continue
        kinds = sorted({_kind(e.get("resourceId"), t) for _, e in hits})
        how = sorted({("exacte " + rec["what"]) if rec["how"] == "uri" else "groupe" for rec, _ in hits})
        statuses = sorted({str((e.get("status") or {}).get("value") or "") for _, e in hits})
        ev = min(_epoch(e.get("eventTimestamp")) for _, e in hits)
        subm = [(_epoch(e.get("submissionTimestamp")) or 0) - (_epoch(e.get("eventTimestamp")) or 0)
                for _, e in hits if e.get("submissionTimestamp")]
        lines.append(f"| {bs.scrub(g['label'] or '—')} | `{g['op']}` | oui | {', '.join(kinds)} | {', '.join(how)} | "
                     f"{', '.join(statuses)} | {failure_said([e for _, e in hits])} | "
                     f"{bs.duration(first - g['at']) if first else '—'} | "
                     f"{bs.duration(ev - g['at'])} | {bs.duration(max(subm)) if subm else '—'} |")
    # ── H7: a Run Command v1 and its extension write
    lines += ["", "## Une Run Command v1 écrit-elle aussi une extension ? (H7)", ""]
    v1 = [(gi, g) for gi, g in enumerate(gestures) if g["op"] == RUN_COMMAND_V1]
    if not v1:
        lines.append("Aucune Run Command v1 notée.")
    all_events = {json.dumps(e, sort_keys=True): e for rnd in rounds for rec in rnd for e in rec.get("events") or []}
    for gi, g in v1:
        callers = frozenset().union(*[_callers(e) for _, e in found_events[gi]]) if found_events[gi] else frozenset()
        at = min((_epoch(e.get("eventTimestamp")) for _, e in found_events[gi]), default=g["at"])
        ext = [e for e in all_events.values() if _op(e) == EXTENSION_WRITE and _callers(e) & callers
               and abs((_epoch(e.get("eventTimestamp")) or 0) - at) <= SAME_MOMENT_S]
        said = ", ".join(sorted({_kind(e.get("resourceId"), t) for e in ext}))
        lines.append(f"- {bs.scrub(g['label'] or 'Run Command v1')} : "
                     + (f"**oui**, sous le même appelant, à moins de {SAME_MOMENT_S} s : {said}" if ext else
                        "non : aucune écriture d'extension du même appelant au même moment"))
    # ── H9: the exact filter, and the pages
    lines += ["", "## Le filtre exact, et les pages (H9)", ""]
    children, pages, cut, errors = {}, {}, set(), []
    for rnd in rounds:
        for rec in rnd:
            key = ("exacte " + rec["what"]) if rec["how"] == "uri" else "groupe"
            if rec.get("error"):
                errors.append(f"{key} : {rec['error']}")
                continue
            pages[key] = max(pages.get(key, 0), int(rec.get("pages") or 0))
            if rec.get("cut") or int(rec.get("pages") or 0) > BOUND:
                cut.add(key)
            if rec["how"] == "uri":
                want = _k(rec.get("value"))
                other = [e for e in rec.get("events") or [] if _k(e.get("resourceId")) != want]
                if other:
                    children.setdefault(key, set()).update(_kind(e.get("resourceId"), t) for e in other)
    if children:
        for key, kinds in sorted(children.items()):
            lines.append(f"- la lecture {key} rend d'autres ressources que la sienne : {', '.join(sorted(kinds))} "
                         "(le filtre n'est **pas exact**)")
    else:
        lines.append("- le filtre exact ne rend que sa ressource, jamais ses enfants (**exact**)")
    for key in sorted(pages):
        lines.append(f"- {key} : {pages[key]} page(s) au plus" + (" — **au-delà de la borne de 20**" if key in cut else ""))
    for e in sorted(set(errors)):
        lines.append(f"- en échec : {bs.scrub(e)}")
    return bs.scrub("\n".join(lines)) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench_lev2.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--vm", required=True)
    f.add_argument("--out", required=True)
    f.add_argument("--since", default="")
    f.add_argument("--every", type=float, default=30.0)
    f.add_argument("--for", dest="duration", type=float, default=1800.0)
    r = sub.add_parser("report")
    r.add_argument("--dir", required=True)
    r.add_argument("--gestures", required=True)
    r.add_argument("--out", default="")
    a = parser.parse_args(argv)
    try:
        if a.cmd == "fetch":
            refusal = bench_reader.code_session_refusal()
            if refusal:
                raise Lev2Error(refusal.replace("l'identité de lecture du banc est", "la mesure au banc est"))
            if not bs.VM_NAME.fullmatch(a.vm):
                raise Lev2Error("--vm : un nom de VM du banc")
            since = a.since or datetime.now(timezone.utc).replace(minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%SZ")
            if _epoch(since) is None:
                raise Lev2Error("--since : une date ISO 8601")
            n = fetch(a.vm, Path(a.out), since, a.every, a.duration)
            print(f"{n} tour(s) de lecture sous {a.out} (identifiants compris : ne pas les publier). "
                  f"Puis : bench_lev2.py report --dir {a.out} --gestures <fichier>")
        else:
            text = report(Path(a.dir), Path(a.gestures).read_text(encoding="utf-8"))
            if a.out:
                Path(a.out).write_text(text, encoding="utf-8")
            else:
                sys.stdout.write(text)
    except (Lev2Error, OSError, ValueError) as e:
        print(f"bench_lev2 : {bs.scrub(str(e))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
