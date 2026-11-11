"""Who acted on a VM by the control plane, read on the activity log (LEV2, #690;
docs/design/levee-probation.md §4.1, §4.3).

A FACT, never a decision: `observed_actors` says who made which gesture of the table below on
the VM, its children, its disks, its NICs, the rules of the NSGs that govern it, its identity —
whatever the status, a refusal of the platform aside (`Conflict`, `OperationNotAllowed`, the
reading of REC1b: it reached nothing). Nothing here lifts or holds: the lift is unchanged
(LEV3 will judge these facts); today they are said on the isolation card, for information.

The table is CLOSED and lives here: an operation that is missing is a lot, never the model's.
Reading, the REST API of the activity log (`Microsoft.Insights/eventtypes/management/values`,
under `*/read` — the Reader Imladris already holds):
  - one EXACT read per resource (`resourceUri eq '<id>'`): the VM, each NIC, each disk (the
    current ones and those noted at the isolation, §8), each NSG that governs it, each public IP
    of its NICs, each identity it carries;
  - one read of the VM's GROUP (`resourceGroupName eq '<rg>'`) — and of the group of each NSG or
    NIC that lives elsewhere —, filtered here on the children of the VM and of its NSGs (the
    prefix of their id, case folded): a Run Command managed, an extension, a rule of an NSG, the
    serial console, the tags. Hypothesis H9 (to measure on the bench before LEV3): the exact
    filter does not give the children; if it does, the events read twice count once;
  - each read BOUNDED, ACTIVITY_PAGES pages (20, as REC1b): a page left past the bound, or a
    read that fails, makes the actors UNREADABLE — never « nobody ».

On a shared NSG only a rule that covers the VM counts: its destination (inbound) or its source
(outbound) holds an address of the VM, `*`, a tag (`VirtualNetwork` and any other: a tag is not
evaluated here, it counts), a prefix that holds one of its addresses, or an ASG of one of its
NICs. A rule WRITTEN is read from the event's request body (hypothesis: Administrative events
carry it), else as it is on Azure now; neither: it counts. A rule DELETED (Q16, Jonathan 10/11)
is read from the rules the isolation noted (`nsg_rules_at_isolation`): it does not count only
when that list shows it did not cover the VM — no list (an isolation before LEV2, or one made by
the quarantine NSG, which reads no customer rule), or the rule not in it: it counts. On an NSG
that governs this VM alone, every rule counts. The subnet of the VM written counts always (Q16).

An answer of ARM that is not the shape it documents (a page without its `value` list, a `nextLink`
that is no text, a role without its permissions) is an error: unreadable, never « nobody ».
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from glorfindel.providers.azure.activity import is_app_token, token_identities
from glorfindel.providers.azure.recovery import (
    ACTIVITY_PAGES, _fold, _refused, _refused_operations, _utc)
from glorfindel.providers.azure.door_rules import _k, _rule_fields, rule_covers
from glorfindel.providers.azure.sdk import REST_TIMEOUT_S

ARM = "https://management.azure.com"
ACTIVITY_API = "2015-04-01"
ACTIVITY_SELECT = ("caller,claims,operationName,operationId,eventTimestamp,submissionTimestamp,status,"
                   "subStatus,properties,resourceId,resourceGroupName,eventDataId")

# §4.1, closed: (the operation, the kinds of resource its event names, why it is a door).
# Kinds: vm (the VM itself), vm_child (`<vm>/…`), disk, nic, public_ip, nsg, nsg_rule
# (`<nsg>/securityRules/<name>`), subnet (a subnet of its NICs), identity, group (the VM's group).
DOOR_TABLE = (
    ("Microsoft.Compute/virtualMachines/runCommand/action", ("vm",),
     "du code dans l'invité, en root (Run Command v1)"),
    ("Microsoft.Compute/virtualMachines/runCommands/write", ("vm_child",),
     "une Run Command managée (v2), rejouée au démarrage"),
    ("Microsoft.Compute/virtualMachines/runCommands/delete", ("vm_child",),
     "une Run Command managée (v2) retirée"),
    ("Microsoft.Compute/virtualMachines/extensions/write", ("vm_child",),
     "une extension : du code, un accès remis ou ouvert (VMAccess, connexion AAD), un agent"),
    ("Microsoft.Compute/virtualMachines/extensions/delete", ("vm_child",),
     "une extension retirée"),
    ("Microsoft.Compute/virtualMachines/write", ("vm",),
     "le profil d'OS, userData, customData, une identité, un disque, les tags"),
    ("Microsoft.Compute/virtualMachines/attachDetachDataDisks/action", ("vm",),
     "un disque attaché ou détaché hors du restore"),
    ("Microsoft.Compute/virtualMachines/reimage/action", ("vm",), "la VM réimagée"),
    ("Microsoft.Compute/virtualMachines/redeploy/action", ("vm",), "la VM redéployée"),
    ("Microsoft.Compute/disks/write", ("disk",), "un disque de la VM écrit"),
    ("Microsoft.Compute/disks/beginGetAccess/action", ("disk",), "un disque de la VM exporté par un SAS"),
    ("Microsoft.SerialConsole/serialPorts/connect/action", ("vm_child",),
     "une console interactive sur la VM (hypothèse H6 : sa ressource)"),
    ("Microsoft.Network/networkInterfaces/write", ("nic",),
     "une carte changée : une adresse, une IP publique, un autre NSG"),
    ("Microsoft.Network/publicIPAddresses/join/action", ("public_ip", "nic"),
     "une IP publique posée sur une carte (hypothèse H7 : sa ressource)"),
    ("Microsoft.Network/networkSecurityGroups/securityRules/write", ("nsg_rule",),
     "un port ouvert devant la VM"),
    ("Microsoft.Network/networkSecurityGroups/securityRules/delete", ("nsg_rule",),
     "une règle retirée devant la VM : un refus retiré rouvre un port (Q16)"),
    ("Microsoft.Network/virtualNetworks/subnets/write", ("subnet",),
     "le sous-réseau de la VM : un NSG ou une table de routes détachés ou changés (Q16)"),
    ("Microsoft.Network/networkSecurityGroups/write", ("nsg",), "le NSG de la VM réécrit"),
    ("Microsoft.ManagedIdentity/userAssignedIdentities/assign/action", ("identity",),
     "une identité donnée à la VM"),
    ("Microsoft.Resources/tags/write", ("vm", "vm_child", "group"),
     "les tags d'inscription et de zone"),
    ("Microsoft.Resources/subscriptions/resourceGroups/write", ("group",),
     "le groupe de la VM et ses tags"),
)
DOOR_OPERATIONS = {op.lower(): (kinds, why) for op, kinds, why in DOOR_TABLE}
_RULE_OP = "microsoft.network/networksecuritygroups/securityrules/write"
_RULE_DELETE = "microsoft.network/networksecuritygroups/securityrules/delete"
_RULES = "/securityrules/"
# What the card may name, for information only (LEV3 decides who is excused, §4.2).
_OWN_ENV = ("AZURE_CLIENT_ID", "GLORFINDEL_OWN_CALLERS")
_RESTORE_ENV = "GLORFINDEL_RESTORE_PRINCIPALS"


class CutRead(RuntimeError):
    """A paged read left pages past its bound: what they hold is unknown."""


def _group_of(resource_id: str) -> str:
    parts = str(resource_id or "").split("/")
    low = [p.lower() for p in parts]
    return parts[low.index("resourcegroups") + 1] if "resourcegroups" in low else ""


def _group_id(resource_id: str) -> str:
    parts = str(resource_id or "").split("/")
    low = [p.lower() for p in parts]
    return "/".join(parts[:low.index("resourcegroups") + 2]) if "resourcegroups" in low else ""


def _ids_env(*names: str) -> frozenset[str]:
    out = set()
    for n in names:
        out |= {p.strip().lower() for p in (os.environ.get(n) or "").split(",") if p.strip()}
    return frozenset(out)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class DoorMixin:
    """Who acted on a VM by the control plane (part of AzureConnector)."""

    # ── REST, read only ──────────────────────────────────────────────────────────

    def _arm_get(self, url: str, params: dict | None) -> dict:
        """One GET on Azure Resource Manager, its JSON: the test's fake when it gave one (`_rest`).
        Raises on an answer that is not one."""
        given = getattr(self, "_rest", None)
        if given is not None:
            return given(url, params)
        if not url.startswith(f"{ARM}/"):
            raise RuntimeError("page suivante hors d'Azure Resource Manager, refusée")
        import requests
        token = self._credential.get_token(f"{ARM}/.default").token
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=REST_TIMEOUT_S)
        if not r.ok:
            code = ""
            try:
                code = str(((r.json() or {}).get("error") or {}).get("code") or "")
            except ValueError:
                pass
            raise RuntimeError(f"HTTP {r.status_code}{' ' + code if code else ''}")
        return r.json()

    def _arm_paged(self, url: str, params: dict | None, bound: int = ACTIVITY_PAGES) -> tuple[list, int]:
        """Every page of a listing, at most `bound`: (items, pages read). A page left past the bound
        raises CutRead; a next page outside ARM is refused (SEC8)."""
        items: list = []
        for page in range(1, bound + 1):
            if not str(url).startswith(f"{ARM}/"):
                raise RuntimeError("page suivante hors d'Azure Resource Manager, refusée")
            body = self._arm_get(url, params)
            value = body.get("value") if isinstance(body, dict) else None
            link = body.get("nextLink") if isinstance(body, dict) else None
            # The documented shape, or an error: a page without its list never reads « nothing ».
            if not isinstance(value, list) or not all(isinstance(i, dict) for i in value) \
                    or not (link is None or isinstance(link, str)):
                raise RuntimeError("réponse d'ARM mal formée : pas la liste `value` d'une page")
            items += value
            url, params = link, None
            if not url:
                return items, page
        raise CutRead(f"plus de {bound} pages, la suite n'est pas lue")

    def _activity_read(self, how: str, value: str, since: datetime, until: datetime) -> tuple[list, int]:
        """The activity log's events, `how`: "uri" (resourceUri eq) or "group" (resourceGroupName
        eq), bounded. Raises when it can't be read whole."""
        field = "resourceUri" if how == "uri" else "resourceGroupName"
        url = (f"{ARM}/subscriptions/{self._subscription_id}"
               "/providers/Microsoft.Insights/eventtypes/management/values")
        params = {"api-version": ACTIVITY_API,
                  "$filter": (f"eventTimestamp ge '{_iso(since)}' and eventTimestamp le '{_iso(until)}' "
                              f"and {field} eq '{value}'"),
                  "$select": ACTIVITY_SELECT}
        return self._arm_paged(url, params)

    # ── what the VM is made of ───────────────────────────────────────────────────

    def _door_targets(self, resource_id: str, disks=(), rules=None) -> dict:
        """The VM's resources, read now (ARM): its NICs, their NSGs (the NIC's and the subnet's),
        addresses, public IPs and ASGs, its disks and the ones given, its identities. Raises when
        the VM or a NIC can't be read: the gestures on what is unknown can't be told."""
        from glorfindel.response.ids import _parse_vm_resource_id
        self._ensure_clients()
        rg, name = _parse_vm_resource_id(resource_id)
        vm = self._compute.virtual_machines.get(rg, name)
        storage = getattr(vm, "storage_profile", None)
        found = [getattr(getattr(getattr(storage, "os_disk", None), "managed_disk", None), "id", None)]
        found += [getattr(getattr(d, "managed_disk", None), "id", None) for d in getattr(storage, "data_disks", None) or []]
        noted = {_k(n): {str(k).lower(): r for k, r in (v or {}).items()}
                 for n, v in (rules or {}).items() if isinstance(v, dict)}
        out = {"vm": resource_id, "group": _group_id(resource_id), "nics": [], "nsgs": {}, "ips": [], "asgs": set(),
               "subnets": [], "at_isolation": noted,
               "public_ips": [], "disks": sorted({str(d) for d in [*found, *disks] if d}, key=str.lower),
               "identities": sorted(str(i) for i in (getattr(getattr(vm, "identity", None),
                                                              "user_assigned_identities", None) or {}))}
        for ref in getattr(getattr(vm, "network_profile", None), "network_interfaces", None) or []:
            nic_rg, nic_name = _parse_vm_resource_id(ref.id)
            nic = self._network.network_interfaces.get(nic_rg, nic_name)
            out["nics"].append(ref.id)
            own = getattr(getattr(nic, "network_security_group", None), "id", None)
            if own:
                out["nsgs"].setdefault(own, None)
            for c in getattr(nic, "ip_configurations", None) or []:
                if getattr(c, "private_ip_address", None):
                    out["ips"].append(c.private_ip_address)
                if pip := getattr(getattr(c, "public_ip_address", None), "id", None):
                    out["public_ips"].append(pip)
                out["asgs"] |= {_k(getattr(a, "id", "")) for a in getattr(c, "application_security_groups", None) or []}
            sub = getattr(getattr((getattr(nic, "ip_configurations", None) or [None])[0], "subnet", None), "id", None)
            if sub:
                if _k(sub) not in {_k(x) for x in out["subnets"]}:
                    out["subnets"].append(sub)
                parts = sub.split("/")
                low = [p.lower() for p in parts]
                s = self._network.subnets.get(parts[low.index("resourcegroups") + 1],
                                              parts[low.index("virtualnetworks") + 1], parts[-1])
                if nsg := getattr(getattr(s, "network_security_group", None), "id", None):
                    out["nsgs"].setdefault(nsg, None)
        mine = {_k(n) for n in out["nics"]}
        for nsg_id in list(out["nsgs"]):
            try:
                n_rg, n_name = _parse_vm_resource_id(nsg_id)
                view = self._network.network_security_groups.get(n_rg, n_name)
                alone = (not (getattr(view, "subnets", None) or [])
                         and {_k(getattr(x, "id", "")) for x in getattr(view, "network_interfaces", None) or []} <= mine)
                rules = {str(getattr(r, "name", "")).lower(): _rule_fields(r) for r in getattr(view, "security_rules", None) or []}
                out["nsgs"][nsg_id] = {"alone": alone, "rules": rules}
            except Exception as exc:          # its rules count whole: who wrote one is still read
                out["nsgs"][nsg_id] = {"alone": None, "rules": {}, "why": f"NSG illisible : {str(exc)[:120]}"}
        return out

    # ── the gestures ─────────────────────────────────────────────────────────────

    def observed_actors(self, resource_id: str, since: str, until: str = "", disks=(),
                        rules_at_isolation=None) -> dict:
        """Who made a gesture of DOOR_TABLE on the VM since `since` (ISO 8601) until `until` (now),
        read only — facts, never a verdict of the lift (LEV2).

        {"verdict": "none" | "seen" | "unreadable", "since", "until", "actors": [{"ids", "role",
        "gestures": [{"at", "operation", "resource", "kind", "status", "covers"?}]}], "reads":
        [{"how", "what", "pages", "events"} | {"how", "what", "error"}], "unreadable": [why],
        "scopes": [the resources where a gesture is made: the VM, its NICs, disks, NSGs,
        identities, subnets], "notes": [...]}. `unreadable`: a read failed or was cut — the actors
        listed are those seen, never all of them. `role`: "glorfindel", "restore" or "" —
        information. `rules_at_isolation`: the state's `nsg_rules_at_isolation` (a deleted rule of
        a shared NSG, Q16)."""
        start, end = _utc(since), _utc(until) or datetime.now(timezone.utc)
        if self.dry_run:
            return {"verdict": "unreadable", "since": since, "until": until, "actors": [], "reads": [],
                    "unreadable": ["dry run : rien n'est lu"], "scopes": [], "notes": [], "dry_run": True}
        if start is None:
            return {"verdict": "unreadable", "since": since, "until": until, "actors": [], "reads": [],
                    "unreadable": [f"début de fenêtre illisible : {str(since)[:40]}"], "scopes": [], "notes": []}
        out = {"since": _iso(start), "until": _iso(end), "actors": [], "reads": [], "unreadable": [],
               "scopes": [], "notes": []}
        try:
            t = self._door_targets(resource_id, disks, rules_at_isolation)
        except Exception as exc:
            out["unreadable"].append(f"la VM ou une de ses cartes ne se lit pas : {str(exc)[:160]}")
            out["verdict"] = "unreadable"
            return out
        out["notes"] += [n["why"] for n in t["nsgs"].values() if n.get("why")]
        exact = [("vm", t["vm"])] + [("nic", n) for n in t["nics"]] + [("disk", d) for d in t["disks"]]
        exact += [("nsg", n) for n in t["nsgs"]] + [("public_ip", p) for p in t["public_ips"]]
        exact += [("identity", i) for i in t["identities"]] + [("subnet", x) for x in t["subnets"]]
        groups = sorted({_group_of(t["vm"])} | {_group_of(x) for x in [*t["nsgs"], *t["nics"], *t["subnets"]]} - {""},
                        key=str.lower)
        out["scopes"] = [t["vm"], *t["nics"], *t["disks"], *t["nsgs"], *t["identities"], *t["subnets"]]
        events: dict[str, dict] = {}
        reads = [("uri", what, rid) for what, rid in exact] + [("group", "group", g) for g in groups]
        for how, what, value in reads:
            try:
                got, pages = self._activity_read(how, value, start, end)
            except Exception as exc:
                out["reads"].append({"how": how, "what": what, "error": str(exc)[:160]})
                out["unreadable"].append(f"journal d'activité ({'groupe' if how == 'group' else what}) : "
                                         f"{str(exc)[:160]}")
                continue
            out["reads"].append({"how": how, "what": what, "pages": pages, "events": len(got)})
            for e in got:
                events.setdefault(_event_key(e), e)
        gestures = [g for g in (self._gesture(e, t) for e in events.values()) if g]
        refused = _refused_operations([e for e, _ in gestures])
        kept = [(e, g) for e, g in gestures if not (_refused(e) or _fold(e.get("operationId")) in refused)]
        out["actors"] = _by_actor(kept)
        out["verdict"] = "unreadable" if out["unreadable"] else "seen" if out["actors"] else "none"
        return out

    def _gesture(self, e: dict, t: dict):
        """(event, gesture) when the event is a gesture of the table on this VM; else None."""
        op = _fold((e.get("operationName") or {}).get("value"))
        if op not in DOOR_OPERATIONS:
            return None
        rid = _k(e.get("resourceId") or e.get("resourceUri"))
        kind = _kind_of(rid, t)
        if kind is None or kind not in DOOR_OPERATIONS[op][0]:
            return None
        at = _utc(e.get("eventTimestamp"))
        g = {"at": at.isoformat() if at else "", "operation": (e.get("operationName") or {}).get("value") or op,
             "resource": e.get("resourceId") or e.get("resourceUri") or "", "kind": kind,
             "status": str((e.get("status") or {}).get("value") or "")}
        if op in (_RULE_OP, _RULE_DELETE):
            nsg = next((n for n in t["nsgs"] if rid.startswith(_k(n) + _RULES)), None)
            info = t["nsgs"].get(nsg) or {}
            if info.get("alone"):
                g["covers"] = True
            elif op == _RULE_DELETE:
                # Q16: what it covered, as the isolation noted it; no list, or not in it: it counts.
                listed = (t.get("at_isolation") or {}).get(_k(nsg)) if nsg else None
                was = (listed or {}).get(rid.rsplit("/", 1)[-1]) if listed is not None else None
                g["covers"] = True if was is None else rule_covers(was, t["ips"], t["asgs"])
                if not g["covers"]:
                    return None               # a rule that never covered the VM, of a shared NSG
            else:
                body = (e.get("properties") or {}).get("requestbody") if isinstance(e.get("properties"), dict) else None
                rule = _rule_fields(body) or (info.get("rules") or {}).get(rid.rsplit("/", 1)[-1])
                g["covers"] = rule_covers(rule, t["ips"], t["asgs"])
                if not g["covers"]:
                    return None               # a rule aimed at another VM of a shared NSG
        return e, g


def _event_key(e: dict) -> str:
    """One event once, whichever read gave it: its eventDataId, else what it is made of."""
    if e.get("eventDataId"):
        return str(e["eventDataId"]).lower()
    return "|".join(_fold(x) for x in (e.get("operationId"), (e.get("status") or {}).get("value"),
                                       e.get("eventTimestamp"), e.get("resourceId"), e.get("caller")))


def _kind_of(rid: str, t: dict) -> str | None:
    vm = _k(t["vm"])
    if rid == vm:
        return "vm"
    if rid.startswith(vm + "/"):
        return "vm_child"
    if rid in {_k(d) for d in t["disks"]}:
        return "disk"
    if rid in {_k(n) for n in t["nics"]}:
        return "nic"
    if rid in {_k(n) for n in t["nsgs"]}:
        return "nsg"
    if any(rid.startswith(_k(n) + _RULES) for n in t["nsgs"]):
        return "nsg_rule"
    if rid in {_k(p) for p in t["public_ips"]}:
        return "public_ip"
    if rid in {_k(i) for i in t["identities"]}:
        return "identity"
    if rid in {_k(x) for x in t.get("subnets") or []}:
        return "subnet"
    if rid == _k(t["group"]) or rid.startswith(_k(t["group"]) + "/providers/microsoft.resources/tags"):
        return "group"
    return None


_UPN_CLAIMS = ("upn", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn", "unique_name")
_SCOPE_CLAIMS = ("scp", "http://schemas.microsoft.com/identity/claims/scope")


def actor_ids(e: dict) -> set[str]:
    """Who made an event, as AL1 reads a token (activity.py, `token_identities`): an application's
    token (a service principal, a managed identity) by its appid, azp and oid; a USER's by its oid
    and its caller (its UPN) only — its appid names the client tool (the Azure CLI, the portal), the
    same for the whole tenant: two people under `az` are two actors, never one."""
    raw = e.get("claims") if isinstance(e.get("claims"), dict) else {}
    claims = {**raw, "upn": next((raw[k] for k in _UPN_CLAIMS if raw.get(k)), ""),
              "scp": next((raw[k] for k in _SCOPE_CLAIMS if raw.get(k)), "")}
    if not claims.get("oid"):
        claims["oid"] = raw.get("http://schemas.microsoft.com/identity/claims/objectidentifier") or ""
    caller = str(e.get("caller") or "").strip().lower()
    if "@" in caller and not claims["upn"]:
        claims["upn"] = caller                # a user's caller is its UPN
    ids = token_identities(claims) if is_app_token(claims) else {
        str(claims["oid"]).strip().lower()} - {""}
    return ids | ({caller} if caller else set())


def _by_actor(kept: list) -> list[dict]:
    """The gestures by who made them: ids that meet are one actor (a UPN and an object id of one
    event; never a client tool's appid: actor_ids). Oldest gesture first, actors by their first
    gesture."""
    actors: list[dict] = []
    for e, g in sorted(kept, key=lambda x: x[1]["at"]):
        ids = actor_ids(e)
        mine = [a for a in actors if a["_ids"] & ids] if ids else []
        if mine:
            a = mine[0]
            for other in mine[1:]:
                a["_ids"] |= other["_ids"]
                a["gestures"] += other["gestures"]
                actors.remove(other)
        else:
            a = {"_ids": set(), "gestures": []}
            actors.append(a)
        a["_ids"] |= ids
        a["gestures"].append(g)
    own, restore = _ids_env(*_OWN_ENV), _ids_env(_RESTORE_ENV)
    out = []
    for a in actors:
        ids = sorted(a["_ids"])
        role = "glorfindel" if own & a["_ids"] else "restore" if restore & a["_ids"] else ""
        out.append({"ids": ids, "role": role, "gestures": sorted(a["gestures"], key=lambda g: g["at"])})
    return out

