#!/usr/bin/env python3
"""bench_preflight — the bench's step 0 in one verdict: `make bench-preflight [TARGET=<vm>]` (BNC1, #682).

On 09/11 (RAN1, #665) every check of the step 0 of docs/banc-t1486.md was typed by hand, and a
missing right (`listKeys` on the staging account) was seen only at the restore, three hours in.
Here each check is one line, ✓, ⚠ or ✗, then a summary; exit 0 when nothing is ✗ (a ⚠ does not
stop the run), 1 otherwise. Everything is read, nothing is written — on Azure, on Imladris, on Orodruin:

  Imladris            its deployed reference, its three containers and what `make glorfindel-host-status`
                marks ✗; its CD (`make glorfindel-host-cd-status`): the timer, the release it runs;
  the workstation  no local watch (`docker ps`);
  Orodruin      its contract read on it without being published (`check()` in its hardened
                container), armed or passive, and its cap; deallocated, a ⚠: read once it runs;
  the pairs     `scripts/credential_expiry.py` (RST1): each secret's end — the console's pair, which
                restores, is required;
  the target    its group (one VM of that name), its power; on Imladris: its mode (configured, effective),
                its readiness and the quarantine, no isolation already;
  the point     the newest recovery point of the target in the vault, its age (⚠ past POINT_MAX_H,
                24 h by default);
  the rights    the console, under its own pair, by `Microsoft.Authorization/permissions` (Glorfindel's
                reader, glorfindel/providers/azure/restore_rights.py): what a restore reads, and the
                neutralization's Run Command; Imladris and Orodruin by their role assignments and the roles'
                definitions (wildcards and `notActions` read as Azure reads them, the same
                `action_held`), their ids from Terraform's outputs, read locally; an assignment
                at a management group is not read (a missing right then says so: a false ✗,
                never a false ✓);
  the drifts    « Eregion Glorfindel Restore » that still holds `runCommand/action` (before SEC17): ⚠;
                « Eregion Glorfindel Restore Staging » not on the console at the staging account: ✗.

No identifier is printed, in any form: each line says a role, a kind of scope, or a name of the
bench already public; and every line goes through bench_shared.scrub before it is printed.
It runs under the operator's `az login` and the pairs of their environment (`.envrc`).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE.parent), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bench_shared as bs  # noqa: E402
import credential_expiry  # noqa: E402

DEFAULT_TARGET = "vm-celebrimbor-gondolin"
POINT_MAX_H = 24.0
RESTORE_ROLE = "Eregion Glorfindel Restore"
STAGING_ROLE = "Eregion Glorfindel Restore Staging"
TOKEN_SCOPE = "https://management.azure.com/.default"
OPERATIONS = "docs/operations.md, « Identités Azure »"
PRE_SEC17 = "docs/operations.md, « Depuis un rôle Restore d'avant SEC17 »"
# The contract read on Orodruin without being published: the verdict, its codes, the cap.
ORO_CHECK = ("import json; from eregion_core.orodruin import check; v = check(); "
             "print(json.dumps({'verdict': v.verdict, 'codes': sorted({m['code'] for m in v.missing}), "
             "'notes': sorted({m['code'] for m in v.notes}), 'cap': v.cap}))")


def line(mark: str, text: str) -> tuple[str, str]:
    return (mark, text)


# ── what each principal needs ─────────────────────────────────────────────────
# (what for, where, action). `where`: "vm", "rg" (the target's group), "vault".

def h0_needs() -> list[tuple[str, str, str]]:
    """Imladris's watch: isolate (the quarantine and the deny rules: Glorfindel's own capabilities, MC0),
    drain the sessions, take the clean point, read the activity log and the vault's jobs (REC1)."""
    from glorfindel.providers.azure.capabilities import CAPABILITIES
    from glorfindel.providers.interface import NETWORK_QUARANTINE, NETWORK_RULES, SESSION_DRAIN
    by = {c.name: sorted(c.rights) for c in CAPABILITIES.capabilities}
    needs = [("l'isolement", "rg", a) for a in by[NETWORK_QUARANTINE] + by[NETWORK_RULES]]
    needs += [("la coupure", "vm", a) for a in by[SESSION_DRAIN]]
    needs += [("le point de restauration", "vault",
               "Microsoft.RecoveryServices/Vaults/backupFabrics/protectionContainers/protectedItems/backup/action"),
              ("la lecture du journal", "rg", "Microsoft.Insights/eventtypes/values/read"),
              ("la lecture du journal", "vault", "Microsoft.RecoveryServices/Vaults/backupJobs/read")]
    return needs


ORODRUIN_NEEDS = [("l'attaque", "vm", "Microsoft.Compute/virtualMachines/runCommand/action"),
                  ("l'attaque", "vm", "Microsoft.Compute/virtualMachines/read")]


def applies(assignment_scope: str, scope: str) -> bool:
    a, s = assignment_scope.rstrip("/").lower(), scope.rstrip("/").lower()
    return bool(a) and (s == a or s.startswith(a + "/") or a == "/")


def held_by_assignments(assignments: list[dict], roles: dict[str, list], scope: str, action: str) -> bool:
    """`action` at `scope` by one of the assignments: its scope above or at `scope`, its role holding
    the action (restore_rights.action_held: wildcards, the role's own notActions)."""
    from glorfindel.providers.azure.restore_rights import action_held
    for a in assignments:
        if applies(str(a.get("scope") or ""), scope):
            if action_held(roles.get(str(a.get("roleDefinitionId") or "").lower(), []), action):
                return True
    return False


def role_permissions(assignments: list[dict]) -> dict[str, list]:
    """Each assigned role's permission blocks, by its definition id (lowercase), read once."""
    out: dict[str, list] = {}
    for a in assignments:
        rid = str(a.get("roleDefinitionId") or "").lower()
        if not rid or rid in out:
            continue
        name = str(a.get("roleDefinitionName") or rid.rsplit("/", 1)[-1])
        found = bs.az_json(["role", "definition", "list", "--name", name]) or []
        match = [d for d in found if str(d.get("id") or "").lower() == rid] or found[:1]
        out[rid] = list((match[0].get("permissions") if match else None) or [])
    return out


# ── the checks ────────────────────────────────────────────────────────────────

class Context:
    """What the checks share: the target, its scopes, the vault — read once."""

    def __init__(self, target: str, env: dict, now: datetime, point_max_h: float, config: str):
        self.target, self.env, self.now, self.point_max_h = target, env, now, point_max_h
        self.config = config
        self.sub = (env.get("AZURE_SUBSCRIPTION_ID") or "").strip()
        self.rg = ""
        self.vm_id = ""
        self.vault = self.vault_rg = self.staging = ""
        self.h0: dict | None = None
        self.h0_error = ""

    def scopes(self) -> dict[str, str]:
        base = f"/subscriptions/{self.sub}/resourceGroups"
        return {"vm": f"{base}/{self.rg}/providers/Microsoft.Compute/virtualMachines/{self.target}",
                "rg": f"{base}/{self.rg}",
                "vault": f"{base}/{self.vault_rg or self.rg}/providers/Microsoft.RecoveryServices/vaults/{self.vault}",
                "staging": f"{base}/{self.rg}/providers/Microsoft.Storage/storageAccounts/{self.staging}"}


def check_h0(ctx: Context) -> list:
    res = bs.run(["make", "-s", "--no-print-directory", "glorfindel-host-status"], timeout=300)
    text = res.out + "\n" + res.err
    ref = re.search(r"([✓⚠✗]) référence déployée : (\S+)(?: \(([0-9a-f]{7,40})\))?", text)
    up = {name: mark for mark, name in re.findall(r"([✓✗])\s+(watch|console|bot)\s+eregion-", text)}
    failed = [ln.strip()[1:].strip() for ln in text.splitlines()
              if ln.strip().startswith(bs.FAIL) and "référence déployée" not in ln]
    if ref is None and not up:
        return [line(bs.FAIL, f"Imladris : illisible par make glorfindel-host-status ({res.first_error()})")]
    out = []
    if ref is None:
        out.append(line(bs.FAIL, "Imladris : la référence déployée ne se lit pas"))
    else:
        sha = f" ({ref.group(3)[:12]})" if ref.group(3) else ""
        out.append(line(bs.OK if ref.group(1) == bs.OK else bs.WARN if ref.group(1) == bs.WARN else bs.FAIL,
                        f"Imladris : {ref.group(2)}{sha} déployée"))
    down = [n for n in ("watch", "console", "bot") if up.get(n) != bs.OK]
    out.append(line(bs.FAIL, f"Imladris : conteneur(s) arrêté(s) ou absent(s) : {', '.join(down)}") if down
               else line(bs.OK, "Imladris : watch, console et bot en marche"))
    others = [f for f in failed if not re.match(r"(watch|console|bot)\s+eregion-", f)]
    if others:
        out.append(line(bs.FAIL, "Imladris : " + " ; ".join(others[:4])[:300]))
    return out


def check_cd(ctx: Context) -> list:
    res = bs.run(["make", "-s", "--no-print-directory", "glorfindel-host-cd-status"], timeout=120)
    text = res.out + "\n" + res.err
    runs = re.search(r"tourne : (\S+)", text)
    latest = re.search(r"dernière release : (\S+)", text)
    timer = re.search(r"timer : (\S+)", text)
    if not runs:
        return [line(bs.WARN, f"le CD d'Imladris : illisible ({res.first_error()})")]
    said = f"le CD d'Imladris : Imladris sur {runs.group(1)}"
    if latest and latest.group(1) not in ("illisible", "aucune") and latest.group(1) != runs.group(1):
        return [line(bs.WARN, f"{said}, la dernière release est {latest.group(1)} : le CD peut basculer "
                              "pendant la session (make glorfindel-host-cd-disable)")]
    state = timer.group(1) if timer else "illisible"
    if state == "enabled":
        return [line(bs.OK, f"{said}, la dernière release ; minuteur actif — ne publier aucune release "
                            "pendant la session")]
    if state == "disabled":
        return [line(bs.OK, f"{said} ; minuteur en pause (make glorfindel-host-cd-enable à la fin)")]
    return [line(bs.WARN, f"{said} ; minuteur {state}")]


# A watch of Eregion on the workstation, whatever started it (BNC1b, #724), read three ways:
#   - its command, `glorfindel watch …`, whatever its image and its name: compose's service
#     (`glorfindel watch /app/runs`), `make glorfindel-watch` (`docker run --rm … glorfindel watch runs/`,
#     a name drawn by docker, no compose label), an instance of any name on a rebuilt image;
#   - the compose service `watch` of the image `eregion-glorfindel`, as docker-compose.yml declares it;
#   - its container's name, `${EREGION_INSTANCE:-eregion}-watch` (a team's: eregion-<team>-watch).
# Never by a name that only holds « watch »: another project's « …-watcher » is none.
WATCH_SERVICE = "watch"
WATCH_IMAGE = "eregion-glorfindel"
WATCH_NAME = re.compile(r"eregion(?:-[a-z0-9-]+)?-watch")
PS_FORMAT = '{{.Names}}\t{{.Image}}\t{{.Label "com.docker.compose.service"}}\t{{.Command}}'
PS_ARGV = ["docker", "ps", "--no-trunc", "--format", PS_FORMAT]


def _image_name(image: str) -> str:
    """`registry/eregion-glorfindel:tag` → `eregion-glorfindel`."""
    return image.split("@", 1)[0].rsplit("/", 1)[-1].split(":", 1)[0]


def is_watch_command(command: str) -> bool:
    """`"glorfindel watch runs/"` as `docker ps --no-trunc` says it (the command between double quotes):
    the program `glorfindel` (or a path to it), its first word that is no option `watch`."""
    words = command.strip().removeprefix('"').removesuffix('"').split()
    if not words or words[0].rsplit("/", 1)[-1] != "glorfindel":
        return False
    return next((w for w in words[1:] if not w.startswith("-")), "") == "watch"


def eregion_watches(ps_out: str) -> list[str]:
    """The names of the containers of `docker ps --no-trunc --format PS_FORMAT` that are a watch of Eregion."""
    out = []
    for ln in ps_out.splitlines():
        name, image, service, command = ([*ln.split("\t"), "", "", ""])[:4]
        name = name.strip()
        if not name:
            continue
        if (is_watch_command(command)
                or WATCH_NAME.fullmatch(name)
                or (service.strip() == WATCH_SERVICE and _image_name(image.strip()) == WATCH_IMAGE)):
            out.append(name)
    return out


def check_workstation(ctx: Context) -> list:
    res = bs.run(PS_ARGV, timeout=30)
    if not res.ok:
        return [line(bs.WARN, f"le poste : docker ne répond pas ({res.first_error()}) — aucune watch locale lue")]
    watches = eregion_watches(res.out)
    if watches:
        return [line(bs.FAIL, f"le poste : une watch locale tourne ({', '.join(watches)}) : elle répondrait "
                              "aussi — make glorfindel-stop")]
    return [line(bs.OK, "le poste : aucune watch locale")]


def _power(vm_id: str) -> str:
    codes = bs.az_json(["vm", "get-instance-view", "--ids", vm_id, "--query", "instanceView.statuses[].code"]) or []
    power = [str(c).split("/", 1)[1] for c in codes if str(c).lower().startswith("powerstate/")]
    return power[0].lower() if power else "unknown"


def check_orodruin(ctx: Context) -> list:
    vm_id = bs.tf_output("orodruin", "vm_id")
    if not vm_id:
        return [line(bs.FAIL, "Orodruin : sa VM ne se lit pas (terraform output vm_id d'infra/orodruin)")]
    try:
        power = _power(vm_id)
    except RuntimeError as e:
        return [line(bs.FAIL, f"Orodruin : son état ne se lit pas ({e})")]
    if power != "running":
        return [line(bs.WARN, f"Orodruin : {power} — son contrat se lit une fois démarrée (make orodruin-start), "
                              "puis relancer le préflight avant la demande")]
    known = bs.run(["make", "-s", "--no-print-directory", "orodruin-known"], timeout=60)
    if not known.ok:
        return [line(bs.FAIL, "Orodruin : sa clé d'hôte n'est pas vérifiée (ORO_SSH_FINGERPRINT, make orodruin-known)")]
    base = bs.ssh_argv("BENCH_ORO_SSH", ctx.env)
    prefix = (ctx.env.get("BENCH_ORO_RUN") or "").strip()
    if not base or not prefix:
        return [line(bs.FAIL, "Orodruin : BENCH_ORO_SSH ou BENCH_ORO_RUN vide (lancer par make)")]
    if not bs.host_key_pinned(base):
        return [line(bs.FAIL, "Orodruin : sa clé d'hôte n'est pas épinglée (StrictHostKeyChecking=yes) : rien n'est envoyé")]
    res = bs.run(bs.remote(base, f"{prefix} python -c {shlex.quote(ORO_CHECK)}"), timeout=180)
    try:
        doc = json.loads(res.out.strip().splitlines()[-1])
        verdict = str(doc["verdict"])
    except (ValueError, IndexError, KeyError, TypeError):
        return [line(bs.FAIL, f"Orodruin : son contrat ne se lit pas ({res.first_error()})")]
    if verdict != "armed":
        return [line(bs.FAIL, f"Orodruin : {verdict} — il manque : {', '.join(doc.get('codes') or ['?'])}")]
    cap = doc.get("cap") or {}
    said = ", ".join(f"{k}={v}" for k, v in sorted(cap.items())) or "non dit"
    notes = f" ; à noter : {', '.join(doc['notes'])}" if doc.get("notes") else ""
    return [line(bs.OK if not notes else bs.WARN, f"Orodruin : armé, plafond {said}{notes}")]


def check_pairs(ctx: Context) -> list:
    out = []
    cid = (ctx.env.get("EREGION_CONSOLE_AZURE_CLIENT_ID") or "").strip()
    sec = (ctx.env.get("EREGION_CONSOLE_AZURE_CLIENT_SECRET") or "").strip()
    if not cid or not sec:
        out.append(line(bs.FAIL, "les paires : celle de la console est absente ou incomplète "
                                 "(EREGION_CONSOLE_AZURE_CLIENT_ID / _SECRET) — le restore prendrait une autre "
                                 "identité sans le dire : .envrc, puis source .envrc"))
    said, _ = credential_expiry.report(ctx.env, ctx.now)
    for text in said:
        t = text.strip()
        mark = t[:1]
        body = t[1:].strip()
        if mark == "ℹ" and body.startswith("console"):
            continue                      # said above, as a ✗
        mark = {"ℹ": bs.OK, "✓": bs.OK, "⚠": bs.WARN, "✗": bs.FAIL}.get(mark, bs.WARN)
        out.append(line(mark, f"les paires · {body}"))
    return out


def locate_target(ctx: Context) -> list:
    """The target's group: exactly one VM of that name in the subscription."""
    hits = bs.locate_vm(ctx.target)
    if len(hits) != 1:
        return [line(bs.FAIL, f"la cible : {len(hits)} VM nommée(s) {ctx.target} dans l'abonnement — une seule attendue")]
    ctx.rg, ctx.vm_id = hits[0]["rg"], hits[0]["id"]
    try:
        power = _power(ctx.vm_id)
    except RuntimeError as e:
        power = f"illisible ({e})"
    mark = bs.OK if power == "running" else bs.WARN
    hint = "" if power == "running" else " — make celebrimbor-start VM=… avant le calme de l'étape 1"
    return [line(mark, f"la cible : {ctx.target}, groupe {ctx.rg}, {power}{hint}")]


def check_target_on_h0(ctx: Context) -> list:
    try:
        ctx.h0 = bs.read_h0("preflight", ctx.target, env=ctx.env)
    except RuntimeError as e:
        ctx.h0_error = str(e)
        return [line(bs.FAIL, f"la cible sur Imladris : {e}")]
    t = ctx.h0.get("target") or {}
    out = []
    if t.get("config_error"):
        return [line(bs.FAIL, f"la cible sur Imladris : sa configuration ne se lit pas ({t['config_error']})")]
    configured, effective = t.get("configured") or "?", t.get("effective") or "?"
    if effective == configured and effective not in ("human_only", "?"):
        out.append(line(bs.OK, f"son mode sur Imladris : {effective}"))
    elif configured != effective:
        out.append(line(bs.FAIL, f"son mode sur Imladris : {configured} configuré, retenu en {effective} "
                                 f"({t.get('hold') or 'préparation'}) — le confinement serait une mesure, pas le confinement"))
    else:
        out.append(line(bs.WARN, f"son mode sur Imladris : {effective} — l'isolement attendrait un humain, "
                                 "et se mesurerait comme tel"))
    verdict = t.get("readiness") or "jamais contrôlée"
    codes = f" ({', '.join(t.get('readiness_codes') or [])})" if t.get("readiness_codes") else ""
    if not t.get("quarantine_nsg", True):
        out.append(line(bs.FAIL, "la quarantaine : désactivée (isolation.quarantine_nsg) sur Imladris"))
    elif verdict == "ready":
        out.append(line(bs.OK, "la quarantaine : prête (préparation ready)"))
    elif verdict == "reserve":
        out.append(line(bs.WARN, f"la quarantaine : préparation reserve{codes}"))
    else:
        out.append(line(bs.FAIL, f"la quarantaine : préparation {verdict}{codes}"))
    if t.get("isolation"):
        out.append(line(bs.FAIL, f"la cible : déjà isolée sur Imladris (depuis {t['isolation'].get('isolated_at') or '?'}) — "
                                 "l'étape 7, puis une nouvelle demande"))
    return out


def resolve_vault(ctx: Context) -> None:
    ctx.vault, ctx.vault_rg, ctx.staging = bs.local_vault(ctx.config)


# The item's container and its own name, as its ARM id carries them:
# `…/protectionContainers/<container>/protectedItems/<item>`.
ITEM_SEGMENTS = re.compile(r"/protectionContainers/([^/]+)/protectedItems/([^/]+)/?$", re.IGNORECASE)


def recoverypoint_args(v_rg: str, vault: str, item: dict) -> list[str]:
    """`az backup recoverypoint list`'s arguments for one item of `az backup item list` (BNC1b, #724).

    Measured on the bench, 11/11, read only: `properties.containerName` has three segments
    (`iaasvmcontainerv2;<rg>;<vm>`), and `-c` with it is refused (BMSUserErrorContainerNameIncorrectFormat);
    `-c IaasVMContainer;iaasvmcontainerv2;<rg>;<vm> -i VM;iaasvmcontainerv2;<rg>;<vm>` answers. On the
    item, the id's segment between /protectionContainers/ and /protectedItems/ is that full container,
    to the exact case (`"IaasVMContainer;" + properties.containerName`), and its last segment is the
    item's `name`: both are read from the id — never built by hand, nor a short name, which two groups
    of one vault could share. A segment missing: a RuntimeError, never a fallback to a form not measured."""
    found = ITEM_SEGMENTS.search(str(item.get("id") or ""))
    if not found:
        raise RuntimeError("l'id de l'item ne porte pas son conteneur et son nom "
                           "(/protectionContainers/…/protectedItems/…)")
    return ["backup", "recoverypoint", "list", "-g", v_rg, "-v", vault, "-c", found.group(1),
            "-i", found.group(2), "--backup-management-type", "AzureIaasVM"]


def check_point(ctx: Context) -> list:
    if not ctx.vault:
        return [line(bs.FAIL, f"le point de restauration : aucun coffre dans {Path(ctx.config).name} "
                              "(action_backends, type azure_backup_vault)")]
    v_rg = ctx.vault_rg or ctx.rg
    items = bs.az_json(["backup", "item", "list", "-g", v_rg, "-v", ctx.vault,
                        "--backup-management-type", "AzureIaasVM"]) or []
    item = next((i for i in items if str((i.get("properties") or {}).get("friendlyName") or "").lower() == ctx.target), None)
    if item is None:
        return [line(bs.FAIL, f"le point de restauration : {ctx.target} n'est pas protégée par le coffre {ctx.vault}")]
    try:
        args = recoverypoint_args(v_rg, ctx.vault, item)
    except RuntimeError as e:
        return [line(bs.FAIL, f"le point de restauration : illisible ({e})")]
    points = bs.az_json(args) or []
    times = [t for t in (bs.epoch((p.get("properties") or {}).get("recoveryPointTime")) for p in points) if t is not None]
    if not times:
        return [line(bs.FAIL, "le point de restauration : aucun point lu pour la cible")]
    age_h = (ctx.now.timestamp() - max(times)) / 3600
    said = f"le point de restauration : le plus récent il y a {bs.duration(age_h * 3600)} (seuil {ctx.point_max_h:g} h)"
    if age_h > ctx.point_max_h:
        return [line(bs.WARN, f"{said} — trop vieux : l'étape 2 en prend un propre, depuis Imladris")]
    return [line(bs.OK, said)]


def pair_token(tenant: str, client_id: str, secret: str, post=None) -> str:
    """A token of the console's pair, for Azure Resource Manager (client credentials); the secret
    goes in the request's body only, never in a line."""
    import requests
    post = post or requests.post
    if not bs.GUID.fullmatch(tenant or ""):
        raise RuntimeError("AZURE_TENANT_ID vide ou invalide (l'id du tenant, un GUID)")
    r = post(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
             data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret,
                   "scope": TOKEN_SCOPE}, timeout=30)
    if not getattr(r, "ok", False):
        try:
            code = str((r.json() or {}).get("error") or "")
        except Exception:  # noqa: BLE001
            code = ""
        raise RuntimeError(f"jeton de la paire refusé : HTTP {getattr(r, 'status_code', '?')} {code}".strip())
    return str(r.json()["access_token"])


def check_console_rights(ctx: Context) -> list:
    from glorfindel.providers.azure import restore_rights as rr
    cid = (ctx.env.get("EREGION_CONSOLE_AZURE_CLIENT_ID") or "").strip()
    sec = (ctx.env.get("EREGION_CONSOLE_AZURE_CLIENT_SECRET") or "").strip()
    if not cid or not sec:
        return [line(bs.FAIL, "droits · console : sa paire absente, rien n'est lu")]
    if not (ctx.vault and ctx.staging):
        return [line(bs.FAIL, "droits · console : le coffre ou son compte de transit manque dans la configuration "
                              "du poste (restore_staging_storage)")]
    try:
        token = pair_token(ctx.env.get("AZURE_TENANT_ID", ""), cid, sec)
    except Exception as e:  # noqa: BLE001
        return [line(bs.FAIL, f"droits · console : {bs.scrub(str(e))[:200]}")]
    got = rr.restore_rights(token, rr.restore_scopes(ctx.sub, ctx.rg, ctx.target, ctx.vault_rg or ctx.rg,
                                                     ctx.vault, ctx.staging))
    if not got.get("readable"):
        return [line(bs.WARN, f"droits · console : illisibles ({got.get('error')}) — le restore les relira")]
    out = [line(bs.FAIL, f"droits · console : il manque {m['action']} sur {rr.RESTORE_SCOPE_NAMES.get(m['where'], m['where'])} "
                         f"(rôle « {m['role']} », {OPERATIONS})") for m in got.get("missing") or []]
    if not got.get("run_command"):
        out.append(line(bs.FAIL, f"droits · console : la neutralisation manque ({rr.RESTORE_RUN_COMMAND} sur la cible ; "
                                 f"rôle « Eregion Glorfindel Restore Neutralize », {PRE_SEC17})"))
    if not out:
        out.append(line(bs.OK, "droits · console : le restore (coffre, VM, compte de transit) et la neutralisation"))
    return out


def _principal_rights(ctx: Context, who: str, module: str, needs: list) -> list:
    oid = bs.tf_output(module, "principal_id")
    if not bs.GUID.fullmatch(oid or ""):
        return [line(bs.FAIL, f"droits · {who} : son identité ne se lit pas (terraform output principal_id d'infra/{module})")]
    assignments = bs.az_json(["role", "assignment", "list", "--assignee", oid, "--all", "--include-inherited"]) or []
    roles = role_permissions(assignments)
    scopes = ctx.scopes()
    missing: dict[str, list[str]] = {}
    for what, where, action in needs:
        if not held_by_assignments(assignments, roles, scopes[where], action):
            missing.setdefault(what, []).append(action)
    if missing:
        unread = any("/providers/microsoft.management/managementgroups/" in str(a.get("scope") or "").lower()
                     for a in assignments)
        note = (" (une attribution à un groupe d'administration n'est pas lue : à vérifier à la main)"
                if unread else "")
        return [line(bs.FAIL, f"droits · {who} : pour {what}, il manque {', '.join(actions)}{note}")
                for what, actions in missing.items()]
    said = ", ".join(dict.fromkeys(w for w, _, _ in needs))
    return [line(bs.OK, f"droits · {who} : {said}")]


def check_h0_rights(ctx: Context) -> list:
    return _principal_rights(ctx, "Imladris", "glorfindel-host", h0_needs())


def check_orodruin_rights(ctx: Context) -> list:
    return _principal_rights(ctx, "Orodruin", "orodruin", ORODRUIN_NEEDS)


def check_drifts(ctx: Context) -> list:
    from glorfindel.providers.azure.restore_rights import RESTORE_RUN_COMMAND, action_held
    out = []
    found = bs.az_json(["role", "definition", "list", "--name", RESTORE_ROLE, "--custom-role-only", "true"]) or []
    role = next((d for d in found if str(d.get("roleName") or "") == RESTORE_ROLE), None)
    if role is None:
        out.append(line(bs.WARN, f"dérive : le rôle « {RESTORE_ROLE} » est absent du tenant"))
    elif action_held(list(role.get("permissions") or []), RESTORE_RUN_COMMAND):
        out.append(line(bs.WARN, f"dérive : le rôle « {RESTORE_ROLE} » du tenant porte encore {RESTORE_RUN_COMMAND} "
                                 f"(d'avant SEC17) — {PRE_SEC17}"))
    else:
        out.append(line(bs.OK, f"dérive : le rôle « {RESTORE_ROLE} » sans Run Command (SEC17)"))
    cid = (ctx.env.get("EREGION_CONSOLE_AZURE_CLIENT_ID") or "").strip()
    if not cid or not ctx.staging:
        out.append(line(bs.FAIL, f"dérive : « {STAGING_ROLE} » ne se vérifie pas (paire de la console ou compte "
                                 "de transit absent)"))
        return out
    mine = bs.az_json(["role", "assignment", "list", "--assignee", cid, "--all"]) or []
    staging = ctx.scopes()["staging"].lower()
    if any(str(a.get("roleDefinitionName") or "") == STAGING_ROLE and str(a.get("scope") or "").rstrip("/").lower() == staging
           for a in mine):
        out.append(line(bs.OK, f"dérive : « {STAGING_ROLE} » attribué à la console sur le compte de transit"))
    else:
        out.append(line(bs.FAIL, f"dérive : « {STAGING_ROLE} » n'est pas attribué à la console sur le compte de transit "
                                 f"{ctx.staging} — le restore serait refusé (LinkedAuthorizationFailed) ; {OPERATIONS}"))
    return out


CHECKS = (check_h0, check_cd, check_workstation, check_orodruin, check_pairs)
TARGET_CHECKS = (check_target_on_h0, check_point, check_console_rights, check_h0_rights,
                 check_orodruin_rights, check_drifts)


def _safe(check, ctx: Context) -> list:
    try:
        return check(ctx)
    except Exception as e:  # noqa: BLE001 — a check that breaks is a ✗, never a success
        name = check.__name__.removeprefix("check_").replace("_", " ")
        return [line(bs.FAIL, f"{name} : illisible ({type(e).__name__}: {bs.scrub(str(e))[:200]})")]


H0_UNPINNED = "Imladris : sa clé d'hôte n'est pas vérifiée par son empreinte (HOST_SSH_FINGERPRINT) : rien n'est envoyé"
# What reaches Imladris by ssh: none of it without its host key verified (the make targets included: they
# would connect in accept-new).
H0_CHECKS = ("check_h0", "check_cd", "check_target_on_h0")


def preflight(ctx: Context) -> list:
    lines: list = []
    h0_pinned = bs.host_key_pinned(bs.ssh_argv("BENCH_H0_SSH", ctx.env))
    if not h0_pinned:
        lines.append(line(bs.FAIL, H0_UNPINNED))
    for check in CHECKS:
        if h0_pinned or check.__name__ not in H0_CHECKS:
            lines += _safe(check, ctx)
    if not ctx.sub:
        lines.append(line(bs.FAIL, "la cible : AZURE_SUBSCRIPTION_ID vide (.envrc)"))
        return lines
    try:
        resolve_vault(ctx)
    except Exception as e:  # noqa: BLE001
        lines.append(line(bs.FAIL, f"la configuration du poste : illisible ({type(e).__name__})"))
    located = _safe(locate_target, ctx)
    lines += located
    if not ctx.rg:
        lines.append(line(bs.FAIL, "les contrôles de la cible : sautés, sa VM ne se trouve pas"))
        return lines
    for check in TARGET_CHECKS:
        if h0_pinned or check.__name__ not in H0_CHECKS:
            lines += _safe(check, ctx)
    return lines


def render(target: str, lines: list) -> tuple[str, int]:
    n = {m: sum(1 for mk, _ in lines if mk == m) for m in (bs.OK, bs.WARN, bs.FAIL)}
    out = [f"Préflight du banc — {target}"]
    out += [f"  {mark} {text}" for mark, text in lines]
    verdict = ("le run peut partir" if not n[bs.FAIL] else "le run ne part pas : lever chaque ✗ d'abord")
    out.append(f"Verdict : {n[bs.FAIL]} ✗, {n[bs.WARN]} ⚠, {n[bs.OK]} ✓ — {verdict}")
    return "\n".join(bs.scrub(x) for x in out), 1 if n[bs.FAIL] else 0


def main(argv: list[str] | None = None, env: dict | None = None, now: datetime | None = None) -> int:
    env = dict(os.environ) if env is None else env
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--target", default=env.get("BENCH_TARGET") or DEFAULT_TARGET)
    p.add_argument("--point-max-h", type=float,
                   default=float(env.get("BENCH_POINT_MAX_H") or POINT_MAX_H))
    p.add_argument("--config", default=str(bs.REPO / "glorfindel-config.yaml"))
    args = p.parse_args(argv)
    target = args.target.strip().lower()
    if not bs.VM_NAME.fullmatch(target):
        print("TARGET invalide : le nom d'une VM du banc", file=sys.stderr)
        return 2
    ctx = Context(target, env, now or datetime.now(timezone.utc), args.point_max_h, args.config)
    text, code = render(target, preflight(ctx))
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
