"""FS1g (#1127; Jonathan, 24/11): a restore of a VM the vault runs already — started from another host
(`make bench-restore` from the workstation), which this host's claim cannot see — refuses this one,
before the VM is touched: the executor's restore and the CLI's alike (both reach
``restore_from_backup``).

When the vault's jobs do not read, Glorfindel stays closed — no option forces it. The refusal says
everything needed to restore by hand, outside Glorfindel (az, or the Azure portal), where none of its
guards applies: the VM, the vault, the protected item and its container, the point chosen, the staging
account. First, the equivalent of Glorfindel's restore — the portal's « Restore VM », then « Replace
existing » (the disks replaced in place, OriginalLocation), with its guards to check oneself (no restore
running, the VM deallocated, the last Run Command neutralized: PowerShell on Windows, as the code does).
Then, apart, ``az backup restore restore-disks`` — which restores DISKS and a template into the target
group and leaves the VM unchanged: the swap of the disks is still to be done. Neither the portal's path
nor the command is measured on the bench, and the refusal says so; ``--restore-mode OriginalLocation``
is not given until it is. Never a secret: names, a point's id, a time.

**What remains open**: the job of a restore started elsewhere appears in the vault only once that
restore has neutralized and deallocated its VM — a window of minutes, read by neither side. The risk is
reduced, not closed. No ``$filter`` on the listing: its syntax for the jobs is not measured on the bench,
and a filter written wrong would either close every restore or miss the one running.
"""
from __future__ import annotations

import shlex

RUNNING = ("inprogress", "cancelling")


class RestoreJobRunning(RuntimeError):
    """The vault runs a restore of this VM already, or its jobs cannot be read — refused before
    anything is touched, wherever the other restore started."""
    code = "vault_job_running"


def running(client, vault: str, v_rg: str, vm_rg: str, vm_name: str) -> list[str]:
    """The vault's restore jobs of THIS VM still running. A job naming another group's container is
    another VM's; one naming none counts (the safe side). Raises when the jobs cannot be read."""
    want = f";{vm_rg.lower()};{vm_name.lower()}"
    out = []
    for j in client.backup_jobs.list(vault, v_rg):
        p = getattr(j, "properties", None)
        if p is None or str(getattr(p, "operation", "") or "").lower() != "restore":
            continue
        if str(getattr(p, "entity_friendly_name", "") or "").lower() != vm_name.lower():
            continue
        container = str(getattr(p, "container_name", "") or "").lower()
        if container and not container.endswith(want):
            continue
        if str(getattr(p, "status", "") or "").lower() in RUNNING:
            out.append(str(getattr(j, "name", "") or "?"))
    return out


def by_hand(*, vm_name: str, vm_rg: str, vault: str, v_rg: str, container: str, item: str, point: str,
            point_time: str, before: str, staging: str, windows: bool = False) -> str:
    """Everything to restore this VM by hand, outside Glorfindel — Glorfindel's own restore (« Replace
    existing ») first, its guards, then the az command that restores disks only — neither measured."""
    q = shlex.quote
    command = (f"az backup restore restore-disks --resource-group {q(v_rg)} --vault-name {q(vault)} "
               f"--container-name {q(container)} --item-name {q(item)} --rp-name {q(point)} "
               f"--storage-account {q(staging)} --target-resource-group {q(vm_rg)}")
    if windows:      # as the code neutralizes (restore.py, _neutralize_run_command)
        neutralize = (f"az vm run-command invoke -g {q(vm_rg)} -n {q(vm_name)} --command-id RunPowerShellScript "
                      "--scripts \"Write-Output 'glorfindel: run command neutralized'\"")
    else:
        neutralize = (f"az vm run-command invoke -g {q(vm_rg)} -n {q(vm_name)} --command-id RunShellScript "
                      "--scripts \"echo 'glorfindel: run command neutralized'\"")
    return "\n".join([
        "Pour restaurer à la main, hors de Glorfindel (le portail Azure ou az : aucune de ses gardes ne s'y "
        "applique). Ni ce chemin du portail ni la commande az ci-dessous n'ont été mesurés au banc : les "
        "relire avant de les suivre.",
        f"  VM               : {vm_name} (groupe {vm_rg})",
        f"  Coffre           : {vault} (groupe {v_rg})",
        f"  Élément protégé  : {item}",
        f"  Conteneur        : {container}",
        f"  Point retenu     : {point_time} (id {point}) — le plus récent avant {before}",
        f"  Compte de transit: {staging}",
        "  1. Les gardes, d'abord, dans cet ordre :",
        f"    - aucun restore en cours : az backup job list -g {q(v_rg)} -v {q(vault)} --status InProgress "
        "-o table",
        f"    - la dernière Run Command neutralisée, la VM allumée (un disque restauré la rejoue au "
        f"démarrage) : {neutralize}",
        f"    - la VM désallouée : az vm deallocate -g {q(vm_rg)} -n {q(vm_name)}",
        "  2. L'équivalent du restore de Glorfindel (les disques remplacés en place, OriginalLocation) — le "
        f"portail : Coffres Recovery Services → {vault} → Éléments de sauvegarde → Machine virtuelle Azure → "
        f"{vm_name} → Restaurer la machine virtuelle → le point de {point_time} → « Remplacer l'existant » "
        f"(pas « Créer ») → le compte de transit {staging}.",
        "  3. À part, la commande az : elle restaure des DISQUES — des disques gérés et un modèle dans le "
        f"groupe cible ({vm_rg}) —, et laisse la VM inchangée : l'échange de ses disques reste à faire "
        f"ensuite. {command}",
    ])


def refuse_if_running(client, vault: str, v_rg: str, vm_rg: str, vm_name: str, manual=None) -> None:
    """Before anything is touched: RestoreJobRunning when the vault runs a restore of this VM, or when
    its jobs cannot be read — then, with ``manual`` (a callable giving ``by_hand``'s text), what to do
    by hand. Never two restores of one VM, wherever the other started."""
    try:
        jobs = running(client, vault, v_rg, vm_rg, vm_name)
    except Exception as exc:
        said = ""
        if manual is not None:
            try:
                said = "\n" + manual()
            except Exception:
                said = ""
        raise RestoreJobRunning(
            f"Restore refusé avant de toucher la VM : les jobs du coffre {vault} ne se lisent pas "
            f"({type(exc).__name__}) — un restore lancé ailleurs n'y serait pas vu, et Glorfindel ne restaure "
            f"pas sans cette lecture.{said}") from None
    if jobs:
        raise RestoreJobRunning(
            f"Restore refusé avant de toucher la VM : le coffre {vault} restaure déjà {vm_name} (job "
            f"{', '.join(jobs[:3])}), lancé ailleurs — attendre sa fin (`az backup job list -g {v_rg} -v "
            f"{vault} --status InProgress`)")
