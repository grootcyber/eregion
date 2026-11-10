"""Does the one who acted on the VM keep their rights? Read only (LEV2, #690;
docs/design/levee-probation.md §4.4).

With the Reader H0 already holds (`Microsoft.Authorization/*/read` is under `*/read`): NO right
is added to H0, in ARM nor in Graph (Q11). At each scope where a gesture of the table is made
(the VM, its NICs, disks, NSGs, identities):
  - the role assignments, `GET {scope}/providers/Microsoft.Authorization/roleAssignments` — a
    listing at a scope also gives those of the scopes above it, the group and the subscription
    (hypothesis H1: read by the Reader of the group, to measure);
  - the PIM eligibilities, `roleEligibilityScheduleInstances` (hypothesis H2: readable under
    `*/read`; unreadable, every verdict is);
  - the definition of each role that bears on the actor, `GET {roleDefinitionId}`.

A role gives the door when it holds an operation of DOOR_TABLE — or a right that gives one back:
`Microsoft.Authorization/roleAssignments/write`, `…/roleDefinitions/write` — or the data actions
of a connection to the VM (`virtualMachines/login/action`, `loginAsAdmin/action`). Read as Azure
reads it: `action_held`, its wildcards and notActions, its dataActions and notDataActions.

The verdict, for one actor:
  held        a direct assignment (its principalId one of the actor's ids) gives the door;
  absent      every scope read whole, no assignment nor eligibility — direct, to a group, at a
              management group — would give it;
  unreadable  a read failed or was cut, a definition can't be read, or a path H0 can't read: an
              assignment to a GROUP that would give the door (its members are not read), a PIM
              ELIGIBILITY that would (to the actor or a group), an assignment at a MANAGEMENT
              GROUP that would, a DELETED principal with an assignment left (restorable from
              Entra's recycle bin, hypothesis H11: an orphan reads `principalType: Unknown`), or
              an actor known by no object id.
Ignored, the prudent way: deny assignments, ABAC conditions, locks — they only take away.
"""
from __future__ import annotations

import re

from glorfindel.providers.azure.door import ARM, DOOR_TABLE, CutRead
from glorfindel.providers.azure.restore_rights import action_held, scope_kind

ASSIGNMENTS_API = "2022-04-01"
ELIGIBILITY_API = "2020-10-01"
REGRANT = ("Microsoft.Authorization/roleAssignments/write", "Microsoft.Authorization/roleDefinitions/write")
DOOR_ACTIONS = tuple(op for op, _, _ in DOOR_TABLE) + REGRANT
DOOR_DATA_ACTIONS = ("Microsoft.Compute/virtualMachines/login/action",
                     "Microsoft.Compute/virtualMachines/loginAsAdmin/action")
_OBJECT_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_MG = "/providers/microsoft.management/managementgroups/"


def door_held(perms: list) -> list[str]:
    """The door's operations a role's permission blocks hold (actions and data actions)."""
    held = [a for a in DOOR_ACTIONS if action_held(perms, a)]
    # The data actions read the same way, in dataActions and notDataActions: a `*` of actions
    # never gives one (Azure's rule).
    data = [{"actions": p.get("dataActions") or [], "notActions": p.get("notDataActions") or []}
            for p in perms if isinstance(p, dict)]
    return held + [a for a in DOOR_DATA_ACTIONS if action_held(data, a)]


def _props(item: dict) -> dict:
    p = item.get("properties") if isinstance(item, dict) else None
    return p if isinstance(p, dict) else {}


def _norm(item: dict, kind: str) -> dict:
    p = _props(item)
    return {"id": str(item.get("id") or ""), "kind": kind,
            "principal": str(p.get("principalId") or "").lower(),
            "type": str(p.get("principalType") or "").lower(),
            "role": str(p.get("roleDefinitionId") or ""),
            "scope": str(p.get("scope") or "")}


class RightsReading:
    """What was read at each scope, once per pass whatever the number of actors."""

    def __init__(self):
        self.assignments: dict[str, dict] = {}
        self.eligibilities: dict[str, dict] = {}
        self.definitions: dict[str, dict] = {}      # role id (lowercase) → {"name", "perms"} or {"error"}
        self.read: set[str] = set()
        self.errors: list[str] = []
        self.reads: list[dict] = []


class DoorRightsMixin:
    """The rights of who acted on a VM (part of AzureConnector)."""

    def _rights_at(self, reading: RightsReading, scope: str) -> None:
        key = scope.rstrip("/").lower()
        if key in reading.read:
            return
        reading.read.add(key)
        kind = scope_kind(scope)
        for what, path, api, extra, into, label in (
                ("assignments", "roleAssignments", ASSIGNMENTS_API, {}, reading.assignments, "attributions"),
                ("eligibilities", "roleEligibilityScheduleInstances", ELIGIBILITY_API, {"$filter": "atScope()"},
                 reading.eligibilities, "éligibilités PIM (hypothèse H2)")):
            url = f"{ARM}{scope.rstrip('/')}/providers/Microsoft.Authorization/{path}"
            try:
                items, pages = self._arm_paged(url, {"api-version": api, **extra})
            except CutRead as exc:
                reading.errors.append(f"{label} sur {kind} : {exc}")
                reading.reads.append({"what": what, "scope": kind, "error": str(exc)[:120]})
                continue
            except Exception as exc:
                reading.errors.append(f"{label} sur {kind} : {str(exc)[:120]}")
                reading.reads.append({"what": what, "scope": kind, "error": str(exc)[:120]})
                continue
            reading.reads.append({"what": what, "scope": kind, "pages": pages, "items": len(items),
                                  "inherited": sum(1 for i in items if _props(i).get("scope", "").rstrip("/").lower()
                                                   != key)})
            for i in items:
                n = _norm(i, what)
                into.setdefault(n["id"].lower() or f"{key}#{len(into)}", n)

    def _definition(self, reading: RightsReading, role: str) -> dict:
        key = role.rstrip("/").lower()
        if key not in reading.definitions:
            try:
                body = self._arm_get(f"{ARM}{role}", {"api-version": ASSIGNMENTS_API}) or {}
                p = _props(body)
                reading.definitions[key] = {"name": str(p.get("roleName") or role.rsplit("/", 1)[-1]),
                                            "perms": list(p.get("permissions") or [])}
            except Exception as exc:
                reading.definitions[key] = {"error": str(exc)[:120]}
        return reading.definitions[key]

    def observed_rights(self, principal_ids, resource_id: str, scopes=(), deleted: bool | None = None,
                        reading: RightsReading | None = None) -> dict:
        """The rights an actor (its ids: object id, appId, UPN, lowercase) keeps on the VM, read
        only (LEV2). {"verdict": "held" | "absent" | "unreadable", "held": [{"role", "scope",
        "assignment", "door"}], "unreadable": [why], "groups": [{"role", "scope"}], "reads": [...]}.
        `scopes`: where its gestures are made (observed_actors' `scopes`; the VM alone if none).
        `reading`: shared by the actors of one pass. `deleted`: the principal is known deleted."""
        if self.dry_run:
            return {"verdict": "unreadable", "held": [], "groups": [], "unreadable": ["dry run : rien n'est lu"],
                    "reads": [], "dry_run": True}
        if isinstance(reading, dict):         # a pass's cache, neutral: this adapter's reading in it
            reading = reading.setdefault("azure", RightsReading())
        reading = reading if reading is not None else RightsReading()
        for scope in list(scopes) or [resource_id]:
            self._rights_at(reading, scope)
        return rights_verdict(reading, principal_ids, deleted, self._definition)


def rights_verdict(reading: RightsReading, principal_ids, deleted, definition) -> dict:
    """The verdict of §4.4 on what `reading` holds (`definition(reading, role_id)` reads a role)."""
    ids = {str(i).strip().lower() for i in principal_ids or [] if str(i).strip()}
    out = {"verdict": "", "held": [], "groups": [], "unreadable": list(reading.errors), "reads": list(reading.reads)}
    if not any(_OBJECT_ID.match(i) for i in ids):
        out["unreadable"].append("l'appelant n'a pas d'identifiant objet dans le journal : ses attributions "
                                 "ne se rattachent pas")
    every = list(reading.assignments.values()) + list(reading.eligibilities.values())
    # Deleted: said by the caller, or an orphan of its object id (hypothesis H11).
    gone = bool(deleted) or any(a["principal"] in ids and a["type"] == "unknown" for a in every)
    for a in every:
        mine, group = a["principal"] in ids, a["type"] == "group"
        if not (mine or group):
            continue
        if mine and gone and a["kind"] == "assignments":
            out["unreadable"].append(f"principal supprimé, restaurable : une attribution reste sur "
                                     f"{scope_kind(a['scope'])} — la supprimer ferme la porte")
            continue
        role = definition(reading, a["role"]) if a["role"] else {"error": "rôle non nommé"}
        if "error" in role:
            out["unreadable"].append(f"la définition d'un rôle sur {scope_kind(a['scope'])} ne se lit pas : "
                                     f"{role['error']}")
            continue
        door = door_held(role["perms"])
        if not door:
            continue
        where = scope_kind(a["scope"])
        said = {"role": role["name"], "scope": where, "door": door[:4]}
        if _MG in a["scope"].lower():
            out["unreadable"].append(f"« {role['name']} » à un groupe d'administration : au-dessus de "
                                     "l'abonnement, hors de ce que H0 lit")
        elif a["kind"] == "eligibilities":
            out["unreadable"].append(f"une éligibilité PIM à « {role['name']} » sur {where}"
                                     + (" (à un groupe)" if group and not mine else ""))
        elif mine:
            out["held"].append({**said, "assignment": a["id"]})
        else:
            out["groups"].append(said)
            out["unreadable"].append(f"« {role['name']} » sur {where} à un groupe : H0 n'en lit pas les membres")
    out["unreadable"] = list(dict.fromkeys(out["unreadable"]))
    out["verdict"] = "held" if out["held"] else "unreadable" if out["unreadable"] else "absent"
    return out
