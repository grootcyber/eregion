"""A restore's rights read before the VM is touched, and Azure's refusals said whole (RST1, #680).

Measured on the bench, 09/11: the console's restore was refused (403 `LinkedAuthorizationFailed`)
AFTER the CLI had neutralized the last Run Command and deallocated the VM, which stayed stopped
three hours; the refusal, cut at 300 characters, lost the part where Azure names the missing action
(`Microsoft.Storage/storageAccounts/listKeys/action`, on the staging account).

Here:
- `restore_rights` reads `Microsoft.Authorization/permissions` on the vault, the VM and the staging
  account — before anything is written — and names a right a restore needs and the identity lacks;
- `explain_refusal` reads Azure's `AuthorizationFailed` / `LinkedAuthorizationFailed`: the action
  and the kind of scope, never an id (no subscription, no object id, no client id);
- `job_error_text` says a finished job's `errorDetails`, masked the same way.

Deny assignments, resource locks, ABAC conditions and PIM are not evaluated: the permissions API
does not return them. A right read here as held can still be refused by one of them; Azure's
refusal is then said whole.
"""
from __future__ import annotations

import json
import re

from glorfindel.providers.azure.sdk import REST_TIMEOUT_S

RESTORE_ACTION = ("Microsoft.RecoveryServices/Vaults/backupFabrics/protectionContainers/protectedItems"
                  "/recoveryPoints/restore/action")
STAGING_LIST_KEYS = "Microsoft.Storage/storageAccounts/listKeys/action"
RESTORE_RUN_COMMAND = "Microsoft.Compute/virtualMachines/runCommand/action"

# What a restore needs, where, and the role of the repository that gives it: the vault's restore,
# what the code calls on the VM (deallocate before, start after), and the staging account's keys —
# the linked right Azure named on the bench (09/11). The other rights of « Eregion Glorfindel
# Restore » (the VM's and the disks' writes, the staging account's write) are not read here: no
# refusal on the bench proved Azure checks them at the trigger, and a restore is never refused on
# an unproven need (recovery first) — a refusal of one of them is said whole by explain_refusal.
RESTORE_NEEDS = (
    ("vault", RESTORE_ACTION, "Eregion Glorfindel Restore"),
    ("vm", "Microsoft.Compute/virtualMachines/deallocate/action", "Eregion Glorfindel Restore"),
    ("vm", "Microsoft.Compute/virtualMachines/start/action", "Eregion Glorfindel Restore"),
    ("staging", STAGING_LIST_KEYS, "Eregion Glorfindel Restore Staging"),
)

RESTORE_SCOPE_NAMES = {
    "vault": "le coffre (Microsoft.RecoveryServices/vaults)",
    "vm": "la VM (Microsoft.Compute/virtualMachines)",
    "staging": "le compte de transit (Microsoft.Storage/storageAccounts)",
}

_GUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_ARM_ID = re.compile(r"/subscriptions/[^\s'\",;()]+", re.IGNORECASE)
# « does not have authorization to perform action 'A' over scope 'S' » (AuthorizationFailed);
# « does not have permission to perform action(s) 'A,B' on the linked scope(s) 'S1,S2' » (Linked…).
_MISSING = re.compile(
    r"does not have (?:authorization|permission) to perform action(?:\(s\))?\s+'([^']+)'\s+"
    r"(?:over scope|on the linked scope\(s\))\s+'([^']+)'", re.IGNORECASE)
_REFUSAL_MAX = 1200


def scope_kind(scope: str) -> str:
    """The kind of an ARM scope, without its id: `Microsoft.Storage/storageAccounts`, a resource
    group, a subscription."""
    parts = [p for p in str(scope or "").strip().strip("/").split("/") if p]
    low = [p.lower() for p in parts]
    if "providers" in low:
        rest = parts[len(low) - low[::-1].index("providers"):]
        if rest:
            return "/".join([rest[0], *rest[1::2]])
    if "resourcegroups" in low:
        return "un groupe de ressources"
    if "subscriptions" in low:
        return "l'abonnement"
    return "une portée illisible"


def masked(text: str) -> str:
    """Azure's words without an id: each ARM id becomes its kind, each GUID `<id>`."""
    out = _ARM_ID.sub(lambda m: f"<{scope_kind(m.group(0))}>", str(text or ""))
    return _GUID.sub("<id>", out)


def _refusal_body(text: str) -> tuple[str, str]:
    """(code, message) of an ARM error body; a body that is no JSON: ("", the text)."""
    try:
        err = (json.loads(text or "") or {}).get("error") or {}
    except (ValueError, AttributeError):
        return "", str(text or "")
    if not isinstance(err, dict):
        return "", str(text or "")
    return str(err.get("code") or ""), str(err.get("message") or text or "")


def missing_from_refusal(message: str) -> list[tuple[str, str]]:
    """The (action, kind of scope) pairs an authorization refusal names as missing."""
    out: list[tuple[str, str]] = []
    for actions, scopes in _MISSING.findall(message or ""):
        acts = [a.strip() for a in actions.split(",") if a.strip()]
        kinds = [scope_kind(s) for s in scopes.split(",") if s.strip()] or ["une portée illisible"]
        for i, action in enumerate(acts):
            out.append((action, kinds[i] if i < len(kinds) else kinds[-1]))
    return out


def explain_refusal(status: int, text: str) -> str:
    """Azure's refusal of a trigger, said whole and without an id: its code, then each missing
    action and the kind of scope it lacks on — or, a refusal of another shape, its message masked.
    The code stays in the text: the watch reads « AuthorizationFailed » as a write refused."""
    code, message = _refusal_body(text)
    head = f"{status}{' ' + code if code else ''}"
    missing = missing_from_refusal(message) if "authorization" in code.lower() or not code else []
    if missing:
        said = " ; ".join(f"il manque {a} sur {k}" for a, k in missing)
        hint = (" — le rôle « Eregion Glorfindel Restore Staging », sur le seul compte de transit "
                "(docs/operations.md, « Identités Azure »)"
                if any(a.lower() == STAGING_LIST_KEYS.lower() for a, _ in missing) else "")
        return f"{head} : {said}{hint}"
    return f"{head} : {masked(message).strip()[:_REFUSAL_MAX]}"


def refused_outright(status: int) -> bool:
    """A refusal that applied nothing: a 4xx of authorization or validation (400, 401, 403, 404,
    422…). A 409 (a conflict: an operation already running) and a 5xx may have been applied, or
    name a job under way: the vault's jobs are read before anything else."""
    return 400 <= int(status) < 500 and int(status) != 409


def job_error_text(job) -> str:
    """A backup job's errorDetails, masked: `code 400625 : …` for each; "" when it gives none."""
    p = getattr(job, "properties", None)
    said = []
    for e in getattr(p, "error_details", None) or []:
        code = getattr(e, "error_code", None)
        words = getattr(e, "error_string", None) or getattr(e, "error_title", None) or ""
        line = f"code {code} : {words}" if code not in (None, "") else str(words)
        if line.strip():
            said.append(masked(line.strip()))
    return " ; ".join(said)[:_REFUSAL_MAX]


def action_held(perms: list, action: str) -> bool:
    """`action` is held by one of the permission entries: in its actions (wildcards), not in its
    notActions — each entry is one role, its notActions only take from its own actions."""
    import fnmatch
    a = action.lower()
    return any(
        any(fnmatch.fnmatch(a, str(x).lower()) for x in (p.get("actions") or []))
        and not any(fnmatch.fnmatch(a, str(x).lower()) for x in (p.get("notActions") or []))
        for p in perms if isinstance(p, dict))


def _read_permissions(token: str, scope_path: str) -> list:
    """Every page of `Microsoft.Authorization/permissions` at a scope — the caller's own rights
    there. Raises on an unreadable answer (said by restore_rights, never a success)."""
    import requests
    url = f"https://management.azure.com{scope_path}/providers/Microsoft.Authorization/permissions"
    params: dict | None = {"api-version": "2022-04-01"}
    perms: list = []
    while url:
        # The token goes to Azure Resource Manager only (SEC8): a next page elsewhere is refused.
        if not url.startswith("https://management.azure.com/"):
            raise RuntimeError("page suivante hors d'Azure Resource Manager, refusée")
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params,
                         timeout=REST_TIMEOUT_S)
        if not r.ok:
            code, _ = _refusal_body(getattr(r, "text", ""))
            raise RuntimeError(f"HTTP {r.status_code}{' ' + code if code else ''}")
        body = r.json()
        perms += body.get("value") or []
        url, params = body.get("nextLink"), None
    return perms


def restore_scopes(sub: str, rg: str, vm_name: str, vault_rg: str, vault: str, staging: str) -> dict:
    """The scopes a restore's rights are read at: the vault, the VM, the staging account (in the
    VM's group, as restore_from_backup builds its id)."""
    base = f"/subscriptions/{sub}/resourceGroups"
    return {
        "vault": f"{base}/{vault_rg}/providers/Microsoft.RecoveryServices/vaults/{vault}",
        "vm": f"{base}/{rg}/providers/Microsoft.Compute/virtualMachines/{vm_name}",
        "staging": f"{base}/{rg}/providers/Microsoft.Storage/storageAccounts/{staging}",
    }


def restore_rights(token: str, scopes: dict) -> dict:
    """What the identity holds of RESTORE_NEEDS, read at each scope, nothing written.

    {"readable": True, "missing": [{"where", "action", "role"}], "run_command": bool} — or
    {"readable": False, "error": …} when a scope's permissions can't be read: the restore then
    goes on as before (a hypothesis to measure on the bench: Reader on the group reads them)."""
    from glorfindel.response.policy import _ERR_MAX, _first_line
    perms: dict[str, list] = {}
    for where, path in scopes.items():
        try:
            perms[where] = _read_permissions(token, path)
        except Exception as e:
            return {"readable": False,
                    "error": f"{RESTORE_SCOPE_NAMES.get(where, where)} : {masked(_first_line(e))[:_ERR_MAX]}"}
    missing = [{"where": where, "action": action, "role": role}
               for where, action, role in RESTORE_NEEDS if not action_held(perms.get(where, []), action)]
    return {"readable": True, "missing": missing,
            "run_command": action_held(perms.get("vm", []), RESTORE_RUN_COMMAND)}


def rights_refusal(missing: list[dict]) -> str:
    """The early refusal: each missing right, where, and its role — the VM untouched."""
    said = " ; ".join(f"{m['action']} sur {RESTORE_SCOPE_NAMES.get(m['where'], m['where'])} "
                      f"(rôle « {m['role']} »)" for m in missing)
    return (f"Restore refusé avant de toucher la VM : il manque {said}. La VM n'a été ni neutralisée "
            "ni désallouée. Droits lus par Microsoft.Authorization/permissions (docs/operations.md, "
            "« Identités Azure »).")
