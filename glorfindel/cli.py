from __future__ import annotations

from eregion_core.models import glorfindel_model
# #205: empty AZURE_CLIENT_* dropped before any Azure call — in the shared core since BL1c,
# where the console and the analysis commands take it too.
from eregion_core.identity import drop_empty_service_principal_env as _drop_empty_service_principal_env

import contextlib
import json
import os
import shlex
import sys
from pathlib import Path

import click
from rich.panel import Panel
from rich.table import Table
from rich.markup import escape as _esc_markup

from glorfindel.masking import ids_masked as _ids_masked, shown as _shown
from glorfindel.terminal import GlorfindelConsole, outside as _outside, say_failure as _say_failure
from glorfindel.vm_command import UNNAMED, group_and_name

# SEC-F (#845): a print never raises on markup — the last guard; text from outside is escaped
# where it is printed (`_outside`, glorfindel/terminal.py).
console = GlorfindelConsole()


def _signal_head(sig) -> None:
    """A signal's head as the watch and `respond` print it: its id, technique and gravity — each
    written by whoever wrote the line (an injector, a file), said as it is (SEC-F)."""
    console.rule(f"[bold cyan]Signal — {_outside(sig.signal_id)}[/bold cyan]")
    console.print(f"  TTP      : {_outside(sig.ttp)}  |  Severity: [red]{_outside(sig.severity)}[/red]")


def _record_manual_action(action: str, resource_id: str, outcome: dict, hand: str | None = None) -> None:
    """Append a manual operator action to manual_actions.jsonl for the live feed — in the directory
    of the operator's hand (SEC18): runs/console (the console, this CLI), or runs/bot when the bot
    runs it (FS1c, ``EREGION_RUNS_WRITER=bot``: the bot never writes the console's directory)."""
    import json as _json
    from datetime import datetime, timezone as _tz
    from eregion_core import runs_layout
    runs = runs_layout.dir_of(runs_layout.CONSOLE)
    hand = hand or runs_layout.hand()
    if hand != runs_layout.CONSOLE:      # FS1c: the bot's hand, its own directory
        runs = runs_layout.dir_of(hand)
    record = {
        "timestamp": datetime.now(_tz.utc).isoformat(),
        "action": action,
        "confidence": 1.0,
        "escalate": False,
        "signal": {"resource_id": resource_id, "ttp": "", "severity": ""},
        "outcome": outcome,
    }
    # SEC16: a regular file only, never through a link, never blocking — refused, or any error of
    # the write, the action stands (it was made), and it is said once.
    from eregion_core import channel_reader
    path = runs / "manual_actions.jsonl"
    try:
        runs.mkdir(parents=True, exist_ok=True)
        channel_reader.append_line(path, _json.dumps(record))
    except OSError as exc:
        why = channel_reader.why_not_written(exc)
        if channel_reader.say_once(path, why):
            console.print(f"[yellow]{_esc_markup(str(path))} : {_esc_markup(why)} — l'action n'y est pas "
                          "notée (runs/ s'écrit comme il se lit)[/yellow]")


def _backup_vault_from_config(vault: str | None) -> tuple[str, str, str]:
    """(vault, vault_rg, staging_storage) — see config.resolve_backup_vault. No vault
    configured → a clear error instead of the retired "rsv-annatar" default."""
    from glorfindel.config import NO_VAULT_MSG, resolve_backup_vault
    resolved = resolve_backup_vault(vault)
    if not resolved[0]:
        raise click.ClickException(NO_VAULT_MSG)
    return resolved


def _find_rules_file() -> str | None:
    """Look for detection_rules.yaml in canonical locations."""
    for candidate in (
        Path("glorfindel/rules/azure/detection_rules.yaml"),
        Path(__file__).parent / "rules" / "azure" / "detection_rules.yaml",
    ):
        if candidate.exists():
            return str(candidate)
    return None


def _resolve_resource_id(arg: str) -> str:
    """Accept a short VM name (what `list` and the console display) or a full ARM id.

    The Azure calls parse the full resource path (resource group + VM name), so a bare
    name must be resolved to it — otherwise the command either silently matches nothing
    ("Nothing to reset" on a VM that IS blocked) or crashes in _parse_vm_resource_id.
    Resolve via the active isolation/block state, then the discovered VMs (`audit
    vm-celebrimbor-bree` answered « not found in ? », 16/10). Two VMs of that name in two
    resource groups → refused, never the first one (third review, T1) — the state and the
    discovery together (SEC4c): one isolated, the other blocked, is two VMs too. A full id
    (an ARM id, or any form with a '/' but `<groupe>/<nom>`) or an unknown short name is returned
    unchanged — the command then reports 'nothing to do' rather than crash on an unresolvable name.

    `<groupe>/<nom>` (MSK3, #772): what the Discord bot's commands to copy name a VM by — never its
    full id (the subscription's), never its name alone, checked on the bot's host but pasted on
    another (an operator's terminal, whose discovery may know only a homonym of another group).
    Resolved on the same sources, its group AND its name matching, whatever their case; none known
    here, or several (one group and one name in two subscriptions): refused — never the argument
    passed to Azure as it is, never another VM.
    """
    text = str(arg or "").strip()
    pair = _group_and_name(text)
    if "/" in text and pair is None:
        return arg
    from glorfindel.actions import active_blocks, active_isolations
    target = (pair or ("", text))[1].lower()
    group = (pair or ("", ""))[0].lower()
    found: dict[str, str] = {}             # one entry per VM: ids differ in case only

    def add(rid) -> None:
        rid = str(rid or "")
        key = rid.rstrip("/").lower()
        if key and key.rsplit("/", 1)[-1] == target and (pair is None or _group_of(key) == group):
            found.setdefault(key, rid)

    for entry in (*active_isolations(), *active_blocks()):
        add(entry.get("resource_id"))
    try:
        from glorfindel.discovery import AssetRegistry
        for a in AssetRegistry().all():
            add(a.resource_id)
    except Exception:  # an unreadable cache must not break a command
        pass
    if pair is not None and not found:
        raise click.ClickException(
            f"{text} : inconnue de ce poste — glorfindel list --ids (this terminal only), or the "
            "full id (az vm show -g <groupe> -n <nom> --query id -o tsv)")
    if len(found) > 1:
        raise click.ClickException(
            f"{arg}: several VMs have this name — pass the full id:\n  "
            + "\n  ".join(_vms_said(found.values()))
            + "\n(az vm show -g <groupe> -n <nom> --query id -o tsv, or glorfindel list --ids — "
              "this terminal only)")
    return next(iter(found.values()), arg)


def _group_and_name(text: str) -> tuple[str, str] | None:
    """(group, name) of `<groupe>/<nom>` — one « / », both sides given, no leading slash —, or None
    (a short name, a full ARM id, anything else)."""
    parts = str(text or "").split("/")
    if len(parts) == 2 and all(p.strip() for p in parts) and parts[0].lower() != "subscriptions":
        return parts[0].strip(), parts[1].strip()
    return None


def _group_of(resource_id: str) -> str:
    """The resource group of an ARM id, lower case, or ""."""
    low = str(resource_id or "").rstrip("/").lower().split("/")
    if "resourcegroups" in low[:-1]:
        i = low.index("resourcegroups")
        return low[i + 1] if i + 1 < len(low) else ""
    return ""


def _say_vm(resource_id: str) -> None:
    """The VM a command acts on, as resolved, said before it acts — `--yes` too (MSK3): a name
    pasted from elsewhere is read back by its name and its group, never its id."""
    console.print(f"  VM       : {_esc_markup(_vm_said(resource_id))}")


def _vms_said(resource_ids) -> list[str]:
    """Several VMs by their name and group, never their ids (MSK2): two that would read the same
    (one name, one group, two subscriptions) are told apart by their rank, not by an id."""
    said = sorted((_vm_said(rid), rid.lower()) for rid in resource_ids)
    seen: dict[str, int] = {}
    for text, _ in said:
        seen[text] = seen.get(text, 0) + 1
    out, rank = [], {}
    for text, _ in said:
        if seen[text] > 1:
            rank[text] = rank.get(text, 0) + 1
            text = f"{text}, abonnement n°{rank[text]}"
        out.append(text)
    return out


class _GlorfindelCli(click.Group):
    """Render operational failures as a clean one-liner, not a raw traceback.

    Missing creds, a root-owned state file (written by the root container), an Azure
    API error — these are operator conditions, not bugs. Dumping a 20-line stack on
    `AZURE_SUBSCRIPTION_ID is not set` helps no one. Print the cause + a targeted hint
    and exit non-zero. GLORFINDEL_DEBUG=1 restores the full traceback for real debugging.
    """

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except click.ClickException as e:
            # A refusal is pasted too: never a subscription's id in it (MSK2).
            e.message = _ids_masked(e.message)
            raise
        except (click.exceptions.Abort, click.exceptions.Exit, SystemExit, KeyboardInterrupt):
            raise
        except Exception as e:  # noqa: BLE001 — deliberate CLI boundary
            if os.environ.get("GLORFINDEL_DEBUG"):
                raise
            # Azure's text (a 403 cites « over scope '/subscriptions/…' »), said without the id (MSK2).
            console.print(f"[red]✗ {type(e).__name__}: {_esc_markup(_ids_masked(e))}[/red]")
            msg = str(e)
            if "AZURE_SUBSCRIPTION_ID" in msg or "credential" in msg.lower():
                console.print(
                    "[dim]  → environnement non chargé : `direnv allow` ou "
                    "`source .envrc` avant de relancer.[/dim]"
                )
            elif isinstance(e, PermissionError):
                console.print(
                    "[dim]  → fichier d'état appartenant à root (écrit par le "
                    "container). Lance la commande dans le container "
                    "(`docker compose exec watch glorfindel …`) ou corrige "
                    "l'ownership de ~/.glorfindel.[/dim]"
                )
            console.print("[dim]  (GLORFINDEL_DEBUG=1 pour la stack complète)[/dim]")
            ctx.exit(1)


@click.group(cls=_GlorfindelCli)
@click.version_option(package_name="eregion", prog_name="glorfindel")   # the package's, never by hand
def cli():
    """Glorfindel — detect, respond, restore."""
    _drop_empty_service_principal_env()


@cli.command()
@click.argument("signals_file", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, help="Reason and decide without executing actions.")
@click.option("--model", default=lambda: glorfindel_model(), show_default=True)
@click.option("--memory-path", default=None, help="Override default ChromaDB path.")
def respond(signals_file: str, dry_run: bool, model: str, memory_path: str | None):
    """Process all signals in a JSONL file and respond to each."""
    from glorfindel.agent import GlorfindelAgent
    from eregion_core.channel_reader import Refused
    from glorfindel.signals import load_signals

    try:
        signals = load_signals(signals_file)
    except Refused as exc:   # SEC-A1 (V-02): a pipe, a link, a file too large — never read
        raise click.ClickException(f"{signals_file} refusé : {exc} — jamais lu") from None
    if not signals:
        console.print("[yellow]No signals found in file.[/yellow]")
        return

    agent = GlorfindelAgent(dry_run=dry_run, model=model, memory_path=memory_path)
    # SEC3: a recovery_complete lifts an isolation alone only from where the defender alone
    # writes it (`glorfindel restore`, glorfindel/signal_origin.py) — not from runs/.
    from glorfindel import signal_origin
    trusted = signal_origin.in_recovery_dir(signals_file)

    for sig in signals:
        if trusted and sig.event == "recovery_complete":
            signal_origin.vouch({"signal_id": sig.signal_id})
        _signal_head(sig)
        console.print(f"  Event    : {_outside(sig.event)}  |  Resource: {_outside(sig.resource_type)}")
        console.print(f"  Provider : {_outside(sig.provider)}\n")

        state = agent.respond(sig.__dict__ if hasattr(sig, '__dict__') else dict(sig))

        _render_decision(state, dry_run)
        console.print()


@cli.command("door")
@click.argument("resource_id")
@click.option("--days", type=click.FloatRange(0.01, 90.0), default=7.0, show_default=True,
              help="How far back the activity log is read (90 days at most: its retention).")
@click.option("--json", "as_json", is_flag=True, help="The facts as JSON (ids included: this terminal only).")
def door(resource_id: str, days: float, as_json: bool):
    """Who acted on a VM by the control plane, and whether they keep their rights — READ ONLY, under
    this host's identity (LEV2, #690). Nothing is written, on Azure or here; nothing lifts or holds.
    On Imladris, the reads its Reader can make (H1, H2: docs/banc-lev2.md)."""
    from datetime import datetime, timedelta, timezone
    from glorfindel.actions import AzureConnector

    resource_id = _resolve_resource_id(resource_id)
    if "/" not in resource_id:
        raise click.ClickException(f"{resource_id} : ni isolée, ni bloquée, ni découverte — donner son id ARM")
    from glorfindel.actions import _load_isolation_state
    connector = AzureConnector(dry_run=False)
    now = datetime.now(timezone.utc)
    iso = _load_isolation_state(resource_id) or {}
    try:
        seen = connector.observed_actors(resource_id, (now - timedelta(days=days)).isoformat(), until=now.isoformat(),
                                         disks=((iso.get("disks_at_isolation") or {}).get("ids") or ()),
                                         rules_at_isolation=iso.get("nsg_rules_at_isolation") or None)
        reading: dict = {}
        for a in seen.get("actors") or []:
            a["rights"] = connector.observed_rights(a.get("ids") or [], resource_id, scopes=seen.get("scopes") or (),
                                                    reading=reading)
        seen["rights_reads"] = [r for v in reading.values() for r in (getattr(v, "reads", None) or [])]
        if not seen.get("actors"):      # H1, H2: the rights read even with nobody, the VM's scopes
            probe = connector.observed_rights([], resource_id, scopes=seen.get("scopes") or (), reading=reading)
            seen["rights_reads"] = probe.get("reads") or []
    except Exception as exc:            # an answer of a shape not read: said in a sentence, never a trace
        raise click.ClickException(f"la porte ne se lit pas : {_esc_markup(_ids_masked(exc))[:240]}")
    if as_json:
        click.echo(json.dumps(seen, indent=1, default=str))
        return
    console.rule("[bold]Glorfindel — la porte (lecture seule, pour information)[/bold]")
    console.print(f"  {_esc_markup(resource_id.rsplit('/', 1)[-1])} · {seen.get('since')} → {seen.get('until')} "
                  f"· [bold]{seen.get('verdict')}[/bold]")
    for w in seen.get("unreadable") or []:
        console.print(f"  [orange1]illisible[/orange1] : {_esc_markup(_ids_masked(w))}")
    for a in seen.get("actors") or []:
        r = a.get("rights") or {}
        console.print(f"  · {_esc_markup(', '.join(a.get('ids') or []))} {_esc_markup(a.get('role') or '')} "
                      f"— droits [bold]{r.get('verdict')}[/bold]")
        for g in a.get("gestures") or []:
            console.print(f"      {g['at']} {_esc_markup(g['operation'])} ({g['kind']}, {_esc_markup(g['status'])})")
        for w in r.get("unreadable") or []:
            console.print(f"      {_esc_markup(_ids_masked(w))}")
    for r in seen.get("reads") or []:
        console.print(f"  lecture {r.get('how')} {r.get('what')} : "
                      + (f"[red]{_esc_markup(_ids_masked(r['error']))}[/red]" if r.get("error") else
                         f"{r.get('pages')} page(s), {r.get('events')} événement(s)"))
    for r in seen.get("rights_reads") or []:
        console.print(f"  droits {r.get('what')} sur {_esc_markup(_ids_masked(r.get('scope')))} : "
                      + (f"[red]{_esc_markup(_ids_masked(r['error']))}[/red]" if r.get("error") else
                         f"{r.get('items')} lue(s), dont {r.get('inherited')} d'une autre portée"))


@cli.command()
@click.argument("resource_id")
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing.")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def release(resource_id: str, dry_run: bool, yes: bool):
    """Release an isolation applied by Glorfindel on a VM.

    RESOURCE_ID: the VM's short name, <group>/<name> (what the Discord bot's commands give) or
    its full id; the VM resolved is said before anything is done, --yes too.
    """
    from glorfindel.actions import AzureConnector

    resource_id = _resolve_resource_id(resource_id)
    connector = AzureConnector(dry_run=dry_run)

    console.rule("[bold yellow]Glorfindel — Release Isolation[/bold yellow]")
    console.print(f"  Resource : {_esc_markup(_vm_said(resource_id))}")
    console.print(f"  Dry-run  : {dry_run}\n")

    if not dry_run:
        # "Nothing to release" means NO NIC still carries an isolation rule (glorfindel/gestures.py,
        # FS1b: the watch's request of the queue runs the same code).
        from glorfindel.gestures import release_needed
        if not release_needed(connector, resource_id):
            console.print("[yellow]No active isolation found on NSG — state cleared.[/yellow]")
            return

    if not dry_run and not yes:
        if not click.confirm("Release isolation on this VM?", default=False):
            console.print("Aborted.")
            return

    result = connector.release_isolation(resource_id)

    if dry_run:
        console.print("[yellow]DRY RUN — no changes made.[/yellow]")
    elif result.get("status") == "release_partial":
        console.print("[red]✗ Isolation partiellement levée — règles encore en place :[/red]")
        for item in result.get("failed", []):
            console.print(f"  • {_esc_markup(_ids_masked(item))}")
        console.print("[dim]État conservé : relancer `glorfindel release` après correction.[/dim]")
        _record_manual_action("release_isolation", resource_id, result)
        sys.exit(2)
    else:
        console.print(f"[green]✓ Isolation released.[/green]  ({_esc_markup(_ids_masked(result))})")
        _record_manual_action("release_isolation", resource_id, result)
        if result.get("status") == "released":
            from glorfindel.gestures import released
            released(resource_id)            # SEC-E (#846): B3a's facts forgotten


@cli.command()
@click.argument("ip")
@click.argument("resource_id")
@click.option("--dry-run", is_flag=True)
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def unblock(ip: str, resource_id: str, dry_run: bool, yes: bool):
    """Remove a block rule created by Glorfindel for a suspicious IP.

    RESOURCE_ID: the VM's short name, <group>/<name> (what the Discord bot's commands give) or
    its full id; the VM resolved is said before anything is done, --yes too.
    """
    from glorfindel.actions import AzureConnector

    resource_id = _resolve_resource_id(resource_id)
    connector = AzureConnector(dry_run=dry_run)

    console.rule("[bold yellow]Glorfindel — Unblock IP[/bold yellow]")
    console.print(f"  IP       : {ip}")
    console.print(f"  Resource : {_esc_markup(_vm_said(resource_id))}")
    console.print(f"  Dry-run  : {dry_run}\n")

    if not dry_run and not yes:
        if not click.confirm(f"Remove block rules for {ip}?", default=False):
            console.print("Aborted.")
            return

    result = connector.unblock_ip(ip, resource_id)

    if dry_run:
        console.print("[yellow]DRY RUN — no changes made.[/yellow]")
    elif result["status"] == "not_found":
        console.print(f"[yellow]No block rules found for {ip} — already removed?[/yellow]")
    elif result["status"] == "unblock_partial":
        console.print(f"[red]✗ Blocage de {ip} partiellement retiré — règles encore en place :[/red]")
        for item in result.get("failed", []):
            console.print(f"  • {_esc_markup(_ids_masked(item))}")
        _record_manual_action("unblock_ip", resource_id, {**result, "ip": ip})
        sys.exit(2)
    else:
        console.print(f"[green]✓ Unblocked {ip}.[/green]  Deleted: {_esc_markup(_ids_masked(result['deleted_rules']))}")
        _record_manual_action("unblock_ip", resource_id, {**result, "ip": ip})


# ── CMD1 (#797): isolate, block — a containment by a human's hand ────────────────────────────────────
# The console's approval of a held card, from a terminal (the console closed, the phone's shell, MOB1),
# for the reassertion's card on a NIC a perimeter does not cover, or with no card at all: the same calls
# and the same guards (glorfindel/gestures.py), the state written as the watch writes it — reasserted,
# lifted by `release` and `unblock`. The cards are never resolved here: the human acknowledges them.

def _contain_preamble(resource_id: str, action: str, dry_run: bool, scope: str = "vm"):
    """The guards before any call to the cloud, and what the human is told before the prompt — the
    connector once they hold, the VM's zone (read once they hold, a dry run too: reads only), and whether
    a watch lives here (a session cut it rereads). Refused: a ClickException, nothing done, no tag read —
    a dry run too: the guards are local reads."""
    from glorfindel import gestures
    from glorfindel.actions import AzureConnector
    why = gestures.direct_refusal(resource_id)
    if why:
        raise click.ClickException(why)
    connector = AzureConnector(dry_run=dry_run)
    if getattr(connector, "read_only", False):
        raise click.ClickException("credentials en lecture seule (GLORFINDEL_READ_ONLY) : cet hôte ne peut "
                                   "pas agir — rien n'est fait")
    _zone_said(resource_id, action, scope)
    for e in gestures.held_cards(resource_id, action):
        console.print(f"  [cyan]Carte {e['id'][:8]} en attente pour ce geste : elle reste en attente — "
                      f"glorfindel ack {e['id'][:8]} une fois le geste vérifié.[/cyan]")
    return connector, _state_here_said()


def _zone_said(resource_id: str, action: str, scope: str = "vm") -> None:
    """CMD1b (#811): the VM's enrollment zone, on one line before the prompt — --yes and --dry-run too.
    Said, never refused (Jonathan's decision of 14/11): no zone, and no read that fails, stops the gesture
    or changes its exit code. A dry run reads it too, and says the real zone (Jonathan's decision of
    14/11: a dry run writes nothing on Azure, it may read — two GETs, bounded). A VM not enrolled, a zone none of the three, tags unread or no answer in time: each said as such, never taken
    for the bench. A block on the subnet reaches its other VMs, whose zones are not read: said too."""
    from glorfindel import gestures
    # The rule of `--scope subnet` sits on the subnet's NSG: every VM of the subnet, any of them perhaps a
    # real load — the zone said is the named VM's only (review of CMD1b).
    reach = (" — la zone de cette VM seulement : le blocage touche toutes les VM de son sous-réseau, leurs "
             "zones non lues") if scope == "subnet" else ""
    kind, why = gestures.zone_of(resource_id)
    # Tag values and Azure's text: masked (no subscription's id, MSK2), one printable line, cut, no markup.
    why = " ".join("".join(c if c.isprintable() else " " for c in _ids_masked(why)).split())
    why = _esc_markup(why[:200])
    note = f" ({why})" if why else ""            # an enrolled zone's: « ancien tag »; never « () »
    if kind == "production":
        lift = "glorfindel release" if action == "isolate_vm" else "glorfindel unblock"
        console.print(f"  [bold red]Zone     : production{note} — une charge réelle : ce geste la touche pour "
                      f"de vrai (réversible : {lift}){reach}.[/bold red]")
    elif kind in ("bench", "twin"):
        console.print(f"  Zone     : {kind}{note}{reach}")
    else:
        said = {"not_enrolled": f"VM non inscrite{note}",
                "unknown": f"« {why} », inconnue (ni bench, ni twin, ni production)",
                }.get(kind, f"illisible{note}")
        console.print(f"  [yellow]Zone     : {said} — rien ne dit qu'elle soit du banc : peut-être une "
                      f"charge réelle{reach}.[/yellow]")


def _state_here_said() -> bool:
    """The state a gesture writes is this host's ~/.glorfindel: the watch that reasserts it, and whose
    console lifts it, is the one that runs here. No live watch here (a terminal of a workstation while
    the watch runs on Imladris): said, never refused — a watch stopped is when a hand is needed.
    True when one lives here."""
    from datetime import datetime, timezone
    from eregion_core import watch_gate
    if watch_gate.fresh(watch_gate.local_beat(), datetime.now(timezone.utc)):
        return True
    console.print("  [yellow]Aucune watch vivante sur cet hôte : l'état de ce geste s'écrit dans le "
                  "~/.glorfindel de cet hôte, qu'une watch d'un autre hôte (Imladris) ne relit pas — ni "
                  "réaffirmation, ni levée par sa console. La watch sur Imladris : lancer ce geste dans son "
                  "conteneur (docker exec -it eregion-watch …).[/yellow]")
    return False


def _contained_said(out: dict, what: str, dry_run: bool) -> None:
    """What the gesture did and what its check says — exit 2 when the check is not True (a
    ``verification_failed`` card left), as a partial release."""
    result, verification = out.get("result") or {}, out.get("verification")
    if dry_run:
        console.print("[yellow]DRY RUN — no changes made.[/yellow]")
        return
    if result.get("note"):
        console.print(f"  [dim]{_esc_markup(_ids_masked(result['note']))}[/dim]")
    verified = (verification or {}).get("verified")
    if verified is True:
        tail = (" — la coupure des sessions court encore, la réaffirmation la relit"
                if (verification or {}).get("drain_case") == "pending" else "")
        console.print(f"[green]✓ {what} — la vérification le confirme{tail}.[/green]")
        if result.get("status", "").endswith("_partial"):
            console.print(f"[yellow]  En partie : {_esc_markup(result['status'])} (la note ci-dessus).[/yellow]")
            sys.exit(2)
        return
    word = "la vérification a échoué" if verified is False else "elle n'a pas pu être vérifiée"
    console.print(f"[red]✗ {what}, mais {word} : "
                  f"{_esc_markup(_ids_masked((verification or {}).get('error') or '?'))}[/red]")
    console.print("[dim]  Carte verification_failed laissée : glorfindel pending.[/dim]")
    sys.exit(2)


@cli.command()
@click.argument("resource_id")
@click.option("--dry-run", is_flag=True, help="Check the guards, read the VM's zone and show what would be done: "
              "reads only, nothing written on Azure.")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def isolate(resource_id: str, dry_run: bool, yes: bool):
    """Isolate a VM by hand: a deny-all on each of its NICs, as an approved card (CMD1).

    RESOURCE_ID: the VM's short name, <group>/<name> (what the commands to copy give) or its full id;
    the VM resolved is said before anything is done, --yes too. A VM the watch knows only, never one a
    card is only anchored on (AL1). Its state is written here — reasserted, then lifted by `release`.
    A pending card is never resolved: `ack` it once verified.
    """
    from glorfindel import gestures

    resource_id = _resolve_resource_id(resource_id)
    console.rule("[bold red]Glorfindel — Isolate VM[/bold red]")
    console.print(f"  Resource : {_esc_markup(_vm_said(resource_id))}")
    console.print(f"  Dry-run  : {dry_run}\n")
    connector, watched = _contain_preamble(resource_id, "isolate_vm", dry_run)

    if not dry_run and not yes:
        if not click.confirm("Isolate this VM (every NIC cut off)?", default=False):
            console.print("Aborted.")
            return

    out = gestures.contain(connector, "isolate_vm", resource_id,
                           record=None if dry_run else _record_manual_action,
                           drain_followed=None if watched else False)
    _contained_said(out, "VM isolée", dry_run)


@cli.command()
@click.argument("ip")
@click.argument("resource_id")
@click.option("--scope", type=click.Choice(["vm", "subnet"]), default="vm", show_default=True,
              help="vm: this VM alone; subnet: one rule on its subnet's NSG, every VM of the subnet.")
@click.option("--dry-run", is_flag=True, help="Check the guards, read the VM's zone and show what would be done: "
              "reads only, nothing written on Azure.")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def block(ip: str, resource_id: str, scope: str, dry_run: bool, yes: bool):
    """Block one suspicious IP by hand, as an approved card (CMD1).

    RESOURCE_ID: the VM's short name, <group>/<name> or its full id, said before anything is done. One
    host address, never one of the never-block list (SEC2). Its state is written here — reasserted,
    then lifted by `unblock`. A pending card is never resolved: `ack` it once verified.
    """
    from glorfindel import gestures

    resource_id = _resolve_resource_id(resource_id)
    host, why = gestures.address_refusal(ip)
    if why:
        raise click.ClickException(why)
    console.rule("[bold red]Glorfindel — Block IP[/bold red]")
    console.print(f"  IP       : {host}")
    console.print(f"  Resource : {_esc_markup(_vm_said(resource_id))}")
    console.print(f"  Scope    : {scope}" + ("  (every VM of its subnet)" if scope == "subnet" else ""))
    console.print(f"  Dry-run  : {dry_run}\n")
    connector, watched = _contain_preamble(resource_id, "block_suspicious_ip", dry_run, scope)

    if not dry_run and not yes:
        ask = (f"Block {host} for every VM of this VM's subnet?" if scope == "subnet"
               else f"Block {host} on this VM?")
        if not click.confirm(ask, default=False):
            console.print("Aborted.")
            return

    out = gestures.contain(connector, "block_suspicious_ip", resource_id, ip=host, scope=scope,
                           record=None if dry_run else _record_manual_action,
                           drain_followed=None if watched else False)
    _contained_said(out, f"{host} bloquée", dry_run)


@cli.command()
@click.argument("runs_dir", type=click.Path(exists=True), default="runs")
@click.option("--dry-run", is_flag=True)
@click.option("--model", default=lambda: glorfindel_model(), show_default=True)
@click.option("--memory-path", default=None)
@click.option("--interval", default=2, show_default=True, help="Poll interval in seconds.")
@click.option("--rules", "rules_file", default=None, metavar="PATH",
              help="Detection rules YAML (default: detection_rules.yaml in cwd or project root).")
@click.option("--mode", "mode_override", default=None,
              type=click.Choice(["human_only", "non_disruptive"]),
              help="Override the GLOBAL autonomy default for this session "
                   "(per-asset rules in glorfindel-config.yaml still apply).")
def watch(runs_dir: str, dry_run: bool, model: str, memory_path: str | None, interval: int, rules_file: str | None, mode_override: str | None):
    """Watch a runs/ directory and respond to signals as they arrive.

    Start this before (or during) an Annatar run to get real-time responses.
    Existing signal files are tracked from their current end — only new signals
    are processed.

    Signals from different resource_ids are processed in parallel.
    Signals from the same resource_id are serialized (queue per resource).
    """
    from glorfindel.watch.loop import run

    # WCH1 (#1019): the loop is glorfindel/watch/ — its state in objects, each part tested alone. The
    # CLI hands it its console and its own displays, read here at each call (a test's, patched).
    run(runs_dir, dry_run=dry_run, model=model, memory_path=memory_path, interval=interval,
        rules_file=rules_file or _find_rules_file(), mode_override=mode_override,
        console=console, show_signal=_signal_head, show_decision=_render_decision)


@cli.command()
@click.argument("resource_id")
@click.option("--vault", default=None, metavar="VAULT",
              help="RSV vault name (default: first azure_backup_vault in glorfindel-config.yaml).")
@click.option("--dry-run", is_flag=True)
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
@click.option("--wait", is_flag=True, help="Block until backup completes (default: fire-and-forget).")
def snapshot(resource_id: str, vault: str | None, dry_run: bool, yes: bool, wait: bool):
    """Trigger an on-demand Azure Backup for a VM (pre-scenario setup).

    By default, returns immediately with a job_id (fire-and-forget).
    Use --wait to block until the backup completes (~5-20 min).
    Use 'glorfindel jobs <resource_id>' to check job status.

    Workflow:
        annatar clean <scenario.yaml>
        glorfindel snapshot <resource_id> --yes --wait   # --wait for setup
        annatar run <scenario.yaml>

    RESOURCE_ID: the VM's short name, <group>/<name> (what the Discord bot's commands give) or
    its full id; the VM resolved is said before anything is done, --yes too.
    """
    from glorfindel.actions import AzureConnector

    # MSK3 (review 2): the card's step « glorfindel snapshot <groupe>/<nom> --yes » is resolved here,
    # as every command that acts on a VM — it was passed to Azure as it is, and failed.
    resource_id = _resolve_resource_id(resource_id)
    vault, vault_rg, _ = _backup_vault_from_config(vault)

    connector = AzureConnector(dry_run=dry_run)

    console.rule("[bold yellow]Glorfindel — On-demand Snapshot[/bold yellow]")
    console.print(f"  Resource : {_esc_markup(_vm_said(resource_id))}")
    console.print(f"  Vault    : {_esc_markup(_short_name(vault))}")
    console.print(f"  Dry-run  : {dry_run}")
    console.print(f"  Wait     : {wait}\n")

    if not dry_run and not yes:
        if not click.confirm("Trigger on-demand Azure Backup for this VM?", default=False):
            console.print("Aborted.")
            return

    if dry_run:
        console.print("[yellow]DRY RUN — no changes made.[/yellow]")
        return

    if not wait:
        from glorfindel.jobs import start_snapshot
        console.print("[cyan]->[/cyan] Triggering on-demand backup (fire-and-forget)...")
        job = start_snapshot(resource_id, connector, vault, vault_rg=vault_rg)
        console.print("[green]✓ Backup job started.[/green]")
        console.print(f"  job_id : [dim]{job['job_id']}[/dim]")
        console.print(f"  snap_id: [dim]{_esc_markup(_ids_masked(job['snap_id']))}[/dim]")
        short = _short_name(resource_id)          # what `jobs` reads: the VM's name (MSK2)
        console.print(f"\n[dim]Check status: glorfindel jobs {_esc_markup(short)} --refresh[/dim]")
        console.print("[dim]Use --wait to block until completion (needed for setup workflow).[/dim]")
        _record_manual_action("snapshot", resource_id, {"snap_id": job["snap_id"], "status": "InProgress"})
        return

    import time as _time
    console.print("[cyan]->[/cyan] Triggering on-demand backup (blocking)...")
    t0 = _time.time()
    snap_id = connector.snapshot(resource_id, vault=vault, wait=True, vault_rg=vault_rg)
    elapsed = round(_time.time() - t0)

    elapsed_label = f"{elapsed // 60}min {elapsed % 60}s"
    console.print(f"[green]✓ Backup complete.[/green]  Time: {elapsed_label}")
    console.print(f"  snap_id: [dim]{_esc_markup(_ids_masked(snap_id))}[/dim]")

    verification = connector.verify_snapshot(snap_id)
    if verification.get("verified"):
        console.print("[green]✓ Recovery point verified in vault.[/green]")
    else:
        console.print(f"[yellow]⚠ Verification inconclusive: {_esc_markup(_ids_masked(verification))}[/yellow]")

    _record_manual_action("snapshot", resource_id, {"snap_id": snap_id, **verification})


@cli.command()
@click.argument("resource_id")
@click.option("--refresh", is_flag=True, help="Poll Azure for current job status (requires credentials).")
def jobs(resource_id: str, refresh: bool):
    """Show the status of an active snapshot or restore job for a VM.

    Jobs are persisted in ~/.glorfindel/active_jobs/<vm>.json.
    Use --refresh to query Azure for the latest status.
    """
    from glorfindel.jobs import get_job, refresh_job, save_job

    vm_name = resource_id.split("/")[-1]
    job = get_job(resource_id)          # by its full id (SEC-H): a homonym's job is another VM's
    if not job:
        console.print(f"[dim]No active job recorded for {vm_name}.[/dim]")
        return

    if refresh and job.get("status") == "InProgress":
        from glorfindel.actions import AzureConnector
        before = job.get("status")
        try:
            refresh_job(job, AzureConnector())
            if job.get("status") != before:
                save_job(resource_id, job)
        except Exception as e:
            console.print(f"[yellow]Azure poll error: {_esc_markup(_ids_masked(e))}[/yellow]")

    status = job.get("status", "?")
    color = {"Completed": "green", "Failed": "red", "InProgress": "cyan",
             "Stale": "yellow"}.get(status, "white")
    console.rule(f"[bold]Glorfindel — Job Status: [{color}]{status}[/{color}][/bold]")
    console.print(f"  job_id  : {job.get('job_id')}")
    console.print(f"  type    : {job.get('type')}")
    console.print(f"  started : {job.get('started_at', '?')}")
    if job.get("completed_at"):
        console.print(f"  completed: {job.get('completed_at')}")
    if job.get("snap_id"):
        console.print(f"  snap_id : {_esc_markup(_ids_masked(job.get('snap_id')))}")
    if job.get("restore_job_name"):
        console.print(f"  azure_job: {job.get('restore_job_name')}")
    if job.get("recovery_point_time"):
        console.print(f"  RP      : {job.get('recovery_point_time')}")
    if job.get("error"):
        console.print(f"  [red]error   : {_esc_markup(_ids_masked(job.get('error')))}[/red]")
    if status == "InProgress":
        console.print("\n[dim]Run with --refresh to poll Azure for current status.[/dim]")
    if status == "Completed" and job.get("type") == "restore":
        console.print("\n[yellow]Restore done. Next steps:[/yellow]")
        rg = job.get("rg", "<rg>")
        console.print(f"  1. az vm start -g {rg} -n {vm_name}")
        # The job's own VM (it keeps the full id), by a name that takes it back — never another
        # VM of its name, whose quarantine `release … --yes` would lift without a question (MSK2).
        console.print(f"  2. glorfindel release {_esc_markup(_name_for_a_command(job.get('resource_id') or resource_id))} --yes")


@cli.command()
@click.argument("resource_id")
@click.option("--vault", default=None, help="Recovery Services vault (default: glorfindel-config.yaml).")
@click.option("--dry-run", is_flag=True)
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
@click.option("--keep-isolated", is_flag=True, envvar="GLORFINDEL_KEEP_ISOLATED",
              help="Skip recovery_complete signal — VM stays isolated after restore. "
                   "Also honoured via GLORFINDEL_KEEP_ISOLATED=1.")
@click.option("--before", default=None, metavar="ISO8601",
              help="Restore the newest recovery point before this moment (ISO8601 with its "
                   "time zone; a time without one is refused, never guessed): when the attack "
                   "began. Without it, the moment of this VM's card (its first detection; an "
                   "exercise's attack_started, never on a real incident); unknown → the "
                   "command asks for it. Example: 2026-11-19T14:05:00Z")
@click.option("--model", default=lambda: glorfindel_model(), show_default=True)
@click.option("--memory-path", default=None)
@click.option("--wait", is_flag=True, help="Block until restore completes (~15-30 min). Default: fire-and-forget.")
def restore(resource_id: str, vault: str, dry_run: bool, yes: bool, keep_isolated: bool, before: str | None, model: str, memory_path: str | None, wait: bool):
    """Trigger an Azure Backup restore on a VM (human approval action).

    By default, returns after triggering the restore job (fire-and-forget).
    The VM stays deallocated until the restore completes; start it manually
    with 'az vm start' and then run 'glorfindel release'. Use --wait for the
    old blocking behavior that handles post-restore steps automatically.

    The recovery point is the newest one before the attack began (SEC4c): --before, or the
    moment of this VM's card (SEC8); never the newest point when neither says when.

    RESOURCE_ID: the VM's short name, <group>/<name> (what the Discord bot's commands give) or
    its full id; the VM resolved is said before anything is done, --yes too.
    """
    from glorfindel.actions import AzureConnector

    resource_id = _resolve_resource_id(resource_id)
    connector = AzureConnector(dry_run=dry_run)

    # Resolve vault + staging storage from glorfindel-config.yaml (source of truth,
    # namespaced per Celebrimbor instance). Overrides the stale CLI defaults; the staging
    # SA is required by the IaaS restore and must never be a hardcoded name.
    vault, vault_rg, staging_storage = _backup_vault_from_config(vault)

    console.rule("[bold yellow]Glorfindel — Restore from Backup[/bold yellow]")
    console.print(f"  Resource : {_esc_markup(_vm_said(resource_id))}")
    console.print(f"  Vault    : {_esc_markup(_short_name(vault))}")
    identity, restores = _restore_identity()
    console.print(f"  Identity : {'' if restores else '[yellow]'}{_esc_markup(identity)}"
                  f"{'' if restores else '[/yellow]'}")
    before, why_before = _restore_before(resource_id, before)
    if before:
        console.print(f"  Before   : {before}  [dim]({_esc_markup(why_before)})[/dim]")
        from glorfindel.restore_plan import moment_warning
        warning = moment_warning(resource_id, before)
        if warning:
            console.print(f"  [yellow]⚠ {_esc_markup(warning)}[/yellow]")
    console.print(f"  Dry-run  : {dry_run}")
    console.print(f"  Wait     : {wait}\n")

    if not before:
        # Never the newest point by default: it may have been taken after the attack.
        if dry_run:
            console.print(f"[yellow]{_esc_markup(why_before)}[/yellow]")
            console.print("[yellow]DRY RUN — no changes made.[/yellow]")
            return
        raise click.ClickException(why_before)

    # One restore at a time per VM (SEC4c): another one running, or about to, refuses this one.
    from glorfindel.jobs import restore_in_progress
    busy = restore_in_progress(resource_id)          # by its full id (SEC-H)
    if busy and not dry_run:
        raise click.ClickException(f"Restore refusé : {busy}.")

    if not dry_run and not yes:
        if not click.confirm("Trigger Azure Backup restore on this VM?", default=False):
            console.print("Aborted.")
            return

    if dry_run:
        console.print("[yellow]DRY RUN — no changes made.[/yellow]")
        return

    if not wait:
        from glorfindel.jobs import start_restore
        console.print("[cyan]->[/cyan] Triggering restore (fire-and-forget — VM deallocation ~1-2 min)...")
        with _restore_claimed(resource_id):
            job = start_restore(resource_id, connector, vault, before,
                                staging_storage=staging_storage, vault_rg=vault_rg)
        console.print("[green]✓ Restore job started.[/green]")
        console.print(f"  job_id  : [dim]{job['job_id']}[/dim]")
        console.print(f"  azure_job: [dim]{job.get('restore_job_name', '?')}[/dim]")
        console.print(f"  RP      : [dim]{job.get('recovery_point_time', '?')}[/dim]")
        _say_recovery_point(job, before, why_before)
        console.print(f"\n[dim]Check status : glorfindel jobs {_esc_markup(_short_name(resource_id))} --refresh[/dim]")
        console.print("[dim]When Completed: az vm start + glorfindel release (or the console)[/dim]")
        _record_manual_action("restore", resource_id, {"status": "InProgress", "job": job.get("restore_job_name")})
        return

    import time as _time
    console.print("[cyan]->[/cyan] Triggering restore (blocking ~15-30 min)...")
    t0 = _time.time()
    with _restore_claimed(resource_id):
        result = connector.restore_from_backup(resource_id, vault=vault, before_attack_time=before, wait=True,
                                               staging_storage=staging_storage, vault_rg=vault_rg)
    rto_s = round(_time.time() - t0)

    restore_label = f"{rto_s // 60}min {rto_s % 60}s"
    console.print(f"[green]✓ Restore complete.[/green]  restore_time: {restore_label}  RP: {result.get('recovery_point_time')}")
    _say_recovery_point(result, before, why_before)
    if result.get("run_command_neutralized") is True:
        console.print("[dim]✓ Run Command neutralisée avant le restore (pas de rejeu de la "
                      "dernière commande au démarrage).[/dim]")
    if result.get("run_command_neutralized") is False:
        console.print(
            "[bold red]⚠ Run Command non neutralisée avant le restore[/bold red] "
            f"({result.get('run_command_error', '?')}) : le disque restauré a pu rejouer la "
            "dernière commande au démarrage. Vérifier l'intégrité avant de lever "
            "l'isolation — Glorfindel ne la lèvera pas seul."
        )
    console.print("[dim]RTO = detection_s + isolation_s + restore_time  (human decision time excluded)[/dim]\n")

    from glorfindel import escalations as _esc
    resolved = _esc.resolve_by_resource(resource_id, "restore_from_backup")
    if resolved:
        console.print(f"[dim]✓ {resolved} pending escalation(s) resolved.[/dim]\n")

    if keep_isolated:
        console.print("[yellow]--keep-isolated: VM stays isolated. Run 'glorfindel release' when ready.[/yellow]")
        return

    # Emit recovery_complete and let Glorfindel decide (release_isolation)
    sig = _build_recovery_signal(resource_id, result, rto_s)
    out = _write_signal(sig)
    console.rule("[bold cyan]Glorfindel — Recovery Response[/bold cyan]")
    console.print(f"  Event    : recovery_complete  |  Resource: {_esc_markup(_vm_said(resource_id))}\n")

    try:
        from glorfindel.agent import GlorfindelAgent
        agent = GlorfindelAgent(dry_run=dry_run, model=model, memory_path=memory_path)
        state = agent.respond(sig)
        _render_decision(state, dry_run)
    except Exception as e:
        console.print(f"[red]Glorfindel agent error:[/red] {_esc_markup(_ids_masked(e))}")
        console.print(
            f"[yellow]Signal saved to {out.name} — process manually:[/yellow]\n"
            f"  glorfindel respond {out}"
        )


def _render_proposal(p: dict) -> None:
    from rich.syntax import Syntax

    vm = p["resource_id"].split("/")[-1]
    conf_pct = int(p["confidence"] * 100)
    console.print(
        f"  [bold cyan]{_esc_markup(p['rule_name'])}[/bold cyan]  "
        f"[dim]{_outside(p['ttp'])}  {_outside(vm)}  {conf_pct}% confidence[/dim]"
    )
    if p.get("renamed_from"):
        console.print(f"  [yellow]Nom proposé « {_esc_markup(p['renamed_from'])} » : celui d'une règle "
                      f"livrée — renommée, elle ne la remplace pas.[/yellow]")
    if p.get("replaces") == "client":
        console.print(f"  [yellow]⚠ L'approuver remplace la règle « {_esc_markup(p['rule_name'])} » "
                      f"de la couche du client.[/yellow]")
    # The model's words and query, written with the full id in its prompt: said without the
    # subscription, here only — the proposal keeps them, and approve-rule takes its id (MSK2).
    console.print(f"  Analysis  : [dim]{_esc_markup(_ids_masked(p['analysis'])[:100])}…[/dim]")
    console.print(f"  Why better: {_esc_markup(_ids_masked(p['explanation'])[:100])}")
    console.print(Syntax(_ids_masked(p["query"]).strip(), "sql", theme="monokai", line_numbers=False))
    console.print(
        f"  [dim]→ approve: glorfindel approve-rule {_outside(shlex.quote(str(p['id'])))}[/dim]"
    )
    console.print(
        f"  [dim]→ dismiss: glorfindel reject-rule {_outside(shlex.quote(str(p['id'])))}[/dim]\n"
    )


def _render_escalation(e: dict) -> None:
    from datetime import datetime, timezone
    from rich.table import Table

    now = datetime.now(timezone.utc)
    ts = datetime.fromisoformat(e["timestamp"])
    # VP1c (#920): a time without a zone is said as written — its age not known, never guessed.
    when = (f"{ts.strftime('%H:%M')} ({int((now - ts).total_seconds() // 60)}m ago)" if ts.tzinfo is not None
            else f"{_outside(str(e['timestamp']))} (no time zone: age unknown)")
    resource_short = e["resource_id"].split("/")[-1]
    # SLF1 (#929): a detection attributed to no VM — « not attributed », its candidates, never the
    # name of the VM it is filed on.
    from glorfindel import escalations as _esc
    loose = _esc.unattributed(e)
    if loose is not None:
        cands = loose["candidates"]
        resource_short = "not attributed"
        if loose["appliance"]:
            resource_short += f" — through the appliance {loose['appliance']}"
        elif cands:
            more = f" and {len(cands) - 8} more" if len(cands) > 8 else ""
            resource_short += f" — candidates: {', '.join(cands[:8])}{more}"

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="dim", width=18)
    table.add_column()
    # SEC-F: every field read from the cards' store, said as it is — the action is the model's.
    table.add_row("ID", f"[dim]{_outside(e['id'])}[/dim]")
    table.add_row("Time", when)
    table.add_row("Action", f"[bold yellow]{_outside(e['action'])}[/bold yellow]")
    table.add_row("Resource", _outside(resource_short))
    table.add_row("Type", _outside(e["escalation_type"]))
    reason = _ids_masked(e["reason"])                   # the model's words: masked, then cut (MSK2)
    table.add_row("Reason", _esc_markup(reason[:120]) + ("…" if len(reason) > 120 else ""))
    table.add_row("Run", _outside(e["run_id"]))
    console.print(table)

    _render_next_steps(e)
    console.print(f"  [dim]glorfindel ack {_outside(shlex.quote(str(e['id'])))}[/dim]\n")



def _card_moment(e: dict) -> str:
    """The card's first detection (UTC), the moment a restore's --before starts from: the
    attack began before it (SEC4c) — « <ISO8601> » when it has none, a time without its zone
    too (RTZ1: never guessed; `_card_moment_said` says what the card carries)."""
    from glorfindel.restore_plan import card_moment
    return card_moment(e)[0] or "<ISO8601>"


def _card_moment_said(e: dict) -> list[str]:
    """The step that says why a card's restore names no moment, when its time does not read (RTZ1)."""
    from glorfindel.restore_plan import card_moment
    moment, why = card_moment(e)
    return [] if moment else [f"--before: {why}"]


def _name_for_a_command(resource_id: str) -> str:
    """What a suggested command names a VM by: « <groupe>/<nom> » (MSK3b, #787; the bot's form,
    MSK3), only when every command takes it back to this very resource (`_resolve_resource_id`);
    otherwise the id that `list --ids` shows (MSK2). Never its name alone: copied to another
    terminal, or with a VM of that name in another group, it could take that one — two VMs of one
    name in two groups are each named by theirs. A VM this host no longer knows, one group and one
    name in two subscriptions, or a resource that is no VM (a NSG, an account): the id is asked."""
    named = group_and_name(resource_id)
    if named == UNNAMED:
        return UNNAMED
    try:
        resolved = _resolve_resource_id(shlex.split(named)[0])
    except click.ClickException:
        return UNNAMED
    if resolved.rstrip("/").lower() != str(resource_id or "").rstrip("/").lower():
        return UNNAMED
    return named


def _loose_words(loose: dict) -> str:
    """ATT1: « not attributed », then its candidates (eight, the rest counted) or the appliance."""
    if loose.get("appliance"):
        return f"Not attributed — the call came through the appliance {loose['appliance']}"
    cands = loose.get("candidates") or []
    if not cands:
        return "Not attributed — the detection names no VM"
    more = f" and {len(cands) - 8} more" if len(cands) > 8 else ""
    return f"Not attributed — candidates: {', '.join(cands[:8])}{more}"


def _render_next_steps(e: dict) -> None:
    rid = _name_for_a_command(e["resource_id"])      # never the full id on the card (MSK2)
    action = e["action"]
    esc_type = e["escalation_type"]

    llm_steps = e.get("suggested_steps") or []
    if llm_steps:
        console.print("  [bold cyan]Next steps (Glorfindel):[/bold cyan]")
        from glorfindel import escalations as _esc_steps
        loose_steps = _esc_steps.unattributed(e)
        if loose_steps is not None:
            # ATT1 (#936): the model's steps as written — they may name the VM the card is filed on,
            # which the detection does not name. Said first, by the code, never by the model.
            console.print(f"  [yellow]{_outside(_loose_words(loose_steps))}; judge from the CLI — "
                          "these steps aim at the VM the card is filed on[/yellow]")
        for i, step in enumerate(llm_steps, 1):
            # A command of the card naming its VM by its id or its name alone (a card written before
            # MSK3b, the model's) names it by « <groupe>/<nom> »: masked, an id is no command (MSK3b).
            # Masked by the subscriptions the step named as written and the card's id, learned before
            # the rewriting takes the id away: a bare GUID of one further on is masked too (review).
            step = _shown(str(step), e["resource_id"])
            console.print(f"  [cyan]{i}.[/cyan] {_esc_markup(step)}")
        return

    # Fallback statique pour les escalades sans suggested_steps (anciennes ou dry-run)
    from glorfindel import escalations as _esc
    unnamed = _esc.unattributed(e)
    if unnamed is not None:
        # ATT1 (#936): a detection attributed to no VM — whatever the card's type, never a command on
        # the VM it is filed on (`az vm show`, `restore`, `release`…): « not attributed », its
        # candidates, and the judgement to the CLI.
        steps = [
            f"{_loose_words(unnamed)}: judge which VM the detection is about (its row, in Log "
            "Analytics), then act on that VM from the CLI",
            f"If it is a false positive: glorfindel ack {shlex.quote(str(e['id']))}",
        ]
    elif esc_type == "low_confidence" and action == "snapshot":
        steps = [
            # The name from the cards' store, quoted for the shell like every other (SEC-Fc).
            f"Check VM state: az vm show -g <rg> -n {shlex.quote(_short_name(e['resource_id']))} "
            "--query powerState",
            f"If compromise confirmed: glorfindel restore {rid} --yes --before {_card_moment(e)}"
            "   # un instant avant le début de l'attaque",
            *_card_moment_said(e),
            f"If false positive: glorfindel ack {shlex.quote(str(e['id']))}",
        ]
    elif action == "restore_from_backup":
        steps = [
            f"glorfindel restore {rid} --yes --before {_card_moment(e)}"
            "   # un instant avant le début de l'attaque",
            *_card_moment_said(e),
            "Glorfindel releases isolation automatically after restore (~20 min)",
        ]
    elif action == "release_isolation":
        steps = [f"glorfindel release {rid} --yes"]
    elif esc_type == "proposed_action":
        steps = [
            f"Review proposed action: {action}",
            "If approved: implement manually, then glorfindel ack",
        ]
    elif esc_type == "destructive_action":
        steps = [
            f"glorfindel {shlex.quote(str(action).replace('_', '-'))} {rid} --yes",
            "Requires explicit human approval — review before executing",
        ]
    else:
        steps = [f"Review and act manually on: {action}"]

    console.print("  [bold cyan]Next steps:[/bold cyan]")
    for i, step in enumerate(steps, 1):
        console.print(f"  [cyan]{i}.[/cyan] {_outside(step)}")     # the action is the model's (SEC-F)


def _render_card_or_say(render, card) -> None:
    """`render(card)`, or what kept it from being shown, said (SEC-F): a card the store holds
    malformed — or one a writer of the store forged — never hides the cards after it."""
    try:
        render(card)
    except Exception as exc:
        cid = card.get("id") if isinstance(card, dict) else None
        _say_failure(console, f"Carte {str(cid or '?')[:8]} illisible", exc)


@cli.command()
@click.option("--watch", is_flag=True, help="Stay running and print new escalations as they arrive.")
def pending(watch: bool):
    """Show pending escalations waiting for human action.

    With --watch: stays running and prints new escalations in real-time.
    Use this in a dedicated terminal during an Annatar run.
    """
    import time
    from glorfindel import escalations

    items = escalations.pending()

    if not watch:
        from glorfindel.proposed_rules import pending as pending_rules
        proposals = pending_rules()
        if not items and not proposals:
            console.print("[green]No pending escalations or rule proposals.[/green]")
            return
        if items:
            console.rule(
                f"[bold yellow]Glorfindel — {len(items)} pending escalation(s)[/bold yellow]"
            )
            for e in items:
                _render_card_or_say(_render_escalation, e)
        if proposals:
            console.rule("[bold cyan]Proposed detection rules[/bold cyan]")
            for p in proposals:
                _render_card_or_say(_render_proposal, p)
        return

    # Watch mode — poll every 2s, print new escalations as they arrive
    seen_ids = {e["id"] for e in items}
    if items:
        console.rule(f"[bold yellow]Glorfindel — {len(items)} existing escalation(s)[/bold yellow]")
        for e in items:
            _render_card_or_say(_render_escalation, e)

    console.print("[dim]Watching for escalations... (Ctrl+C to stop)[/dim]")
    try:
        while True:
            time.sleep(2)
            for e in escalations.pending():
                if e["id"] not in seen_ids:
                    seen_ids.add(e["id"])
                    console.rule("[bold red]NEW ESCALATION[/bold red]")
                    _render_card_or_say(_render_escalation, e)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")


@cli.command()
@click.argument("escalation_id", required=False)
@click.option("--all", "all_pending", is_flag=True, help="Acknowledge all pending escalations.")
def ack(escalation_id: str | None, all_pending: bool):
    """Acknowledge (resolve) a pending escalation.

    ESCALATION_ID: the id, or its first 6+ characters (the console's and the TUI's commands give 8).
    Use 'glorfindel pending' to list escalation IDs.
    Use --all to acknowledge everything at once.
    """
    from glorfindel import escalations

    if all_pending:
        items = escalations.pending()
        for e in items:
            escalations.resolve(e["id"])
        console.print(f"[green]✓ {len(items)} escalation(s) acknowledged.[/green]")
        return

    if not escalation_id:
        console.print("[red]Provide an escalation ID or use --all.[/red]")
        return

    # CMD1: the id or its first 6+ characters, as `verdict` — the commands to copy give 8; an id that
    # names no card is said, never « acknowledged ».
    try:
        e = escalations.card_of(escalation_id)
    except (KeyError, ValueError) as exc:
        raise click.ClickException(str(exc).strip(chr(39))) from None
    if e.get("status") != "pending":
        console.print(f"[yellow]Escalation {_outside(str(e['id'])[:8])} already "
                      f"{_outside(e.get('status', 'resolved'))}.[/yellow]")
        return
    escalations.resolve(e["id"])
    console.print(f"[green]✓ Escalation {_outside(e['id'])} acknowledged.[/green]")


@cli.command()
@click.argument("escalation_id")
@click.argument("judgement", type=click.Choice(["right", "wrong", "unsure"]))
@click.option("--note", default="", help="Why — kept with the verdict.")
def verdict(escalation_id: str, judgement: str, note: str):
    """Say whether a card's recommendation was right (observation, docs/observation.md).

    ESCALATION_ID: the id, or its first 6+ characters, from 'glorfindel pending'.
    Independent of 'ack': a card can be judged before or after it is acknowledged.
    """
    from glorfindel import escalations
    try:
        e = escalations.set_verdict(escalation_id, judgement, note)
    except (KeyError, ValueError) as exc:
        console.print(f"[red]✗ {str(exc).strip(chr(39))}[/red]")
        raise SystemExit(1)
    console.print(f"[green]✓ {_outside(e['action'])} on {_outside(e['resource_id'].rstrip('/').rsplit('/', 1)[-1])}: "
                  f"{judgement}[/green]")


def _since(value: str):
    """'7d', '24h', '4w' or 'all' → a UTC datetime (None for all)."""
    from datetime import datetime, timedelta, timezone
    if value == "all":
        return None
    units = {"h": "hours", "d": "days", "w": "weeks"}
    try:
        n, unit = int(value[:-1]), units[value[-1]]
    except (ValueError, KeyError, IndexError):
        raise click.BadParameter("use a number followed by h, d or w (7d, 24h, 4w), or 'all'")
    return datetime.now(timezone.utc) - timedelta(**{unit: n})


@cli.command()
@click.option("--since", "since_text", default="7d", show_default=True, help="Period: 24h, 7d, 4w or all.")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
def report(since_text: str, as_json: bool):
    """What the observation measured: the operator's verdicts on Glorfindel's
    recommendations, and the false rate of the disruptive ones (isolate, block)."""
    import json as _json
    from glorfindel import escalations, expected_sudo
    since = _since(since_text)
    r = escalations.observation_report(since)
    # ADM1: the administrators' sudo that opened no card — counted, never silent.
    r["expected_sudo"] = expected_sudo.summary(since)
    # SEC17 (V-12): the past cycles the memory's age bound leaves out of the search — kept, counted.
    from glorfindel.config import memory_max_age_days
    from glorfindel.memory import age_census
    r["memory"] = age_census(max_age_days=memory_max_age_days())
    if as_json:
        click.echo(_json.dumps(r, indent=2))
        return
    console.print(f"[bold]Observation — {since_text}[/bold]  ·  {r['cards']} recommendation(s), {r['judged']} judged")
    d = r["disruptive"]
    rate = "—" if d["false_rate"] is None else f"{d['false_rate']:.0%}"
    console.print(f"Disruptive (isolate, block): {d['right']} right · {d['wrong']} wrong · {d['unsure']} unsure · "
                  f"{d['unjudged']} not judged — [bold]false rate {rate}[/bold]")
    for title, rows in (("By action", r["by_action"]), ("By detection rule", r["by_rule"])):
        table = Table(title=title, title_justify="left")
        for col in ("", "right", "wrong", "unsure", "not judged"):
            table.add_column(col, justify="left" if not col else "right")
        for name, b in sorted(rows.items()):
            table.add_row(_outside(name), str(b["right"]), str(b["wrong"]), str(b["unsure"]), str(b["unjudged"]))
        console.print(table)
    if r["cards"] and r["judged"] < r["cards"]:
        console.print(f"[dim]{r['cards'] - r['judged']} card(s) not judged: glorfindel verdict <id> right|wrong|unsure[/dim]")
    _print_confidence(r)
    b = r.get("blocks") or {}
    if b.get("cards"):
        console.print(f"Block recommendations: {b['cards']} card(s) for {b['distinct_ips']} distinct IP(s)")
    if r.get("exercises"):
        console.print(f"[dim]{r['exercises']} exercise card(s) left out (an injector's window covered the VM)[/dim]")
    if r.get("undated"):
        console.print(f"[yellow]{r['undated']} card(s) left out: their time carries no time zone or cannot be read — "
                      "in the period or not, unknown, never guessed (glorfindel report --since all counts them)[/yellow]")
    _print_expected_sudo(r["expected_sudo"])
    _print_memory(r["memory"])
    _print_auditd()


def _share(cell: dict) -> str:
    """B4a: a share said on enough judged cards only — « too few » under them, never a percentage."""
    return "too few" if cell["too_few"] else f"{cell['right_share']:.0%}"


def _counts(cell: dict) -> list[str]:
    return [str(cell[k]) for k in ("right", "wrong", "unsure", "unjudged", "judged")] + [_share(cell)]


def _cells_table(title: str, heads: tuple[str, ...]) -> Table:
    table = Table(title=title, title_justify="left")
    for head in heads:
        table.add_column(head)
    for col in ("right", "wrong", "unsure", "not judged", "judged", "judged right"):
        table.add_column(col, justify="right", no_wrap=True)
    return table


def _print_confidence(r: dict) -> None:
    """B4a (#991): the verdicts by the confidence they judged, by rule × band, above the gate's
    threshold, and by provenance — each cell with its count, too few said (docs/observation.md)."""
    table = _cells_table(f"By confidence (a share on {r['few_judged']} judged or more)", ("band",))
    for band, cell in r["by_confidence"].items():
        table.add_row(_esc_markup(band), *_counts(cell))
    console.print(table)
    u = r["confidence_unknown"]
    if u["judged"] or u["unjudged"]:
        console.print(f"[dim]{u['judged'] + u['unjudged']} card(s) left out of the bands ({u['judged']} judged): no "
                      "confidence their verdict judged — none given (a failed cycle, no decision of the model), "
                      "or the card rewritten after its verdict[/dim]")
    a = r["above_threshold"]
    if a["threshold"] is None:
        console.print("[yellow]Above the gate's threshold: GLORFINDEL_CONFIDENCE_THRESHOLD invalid — every "
                      "autonomous action is held, none above it[/yellow]")
    else:
        console.print(f"Above the gate's threshold (≥ {a['threshold']:g}): {a['judged']} judged — {a['right']} right · "
                      f"{a['wrong']} wrong · {a['unsure']} unsure · {a['unjudged']} not judged — "
                      f"[bold]judged right: {_share(a)}[/bold]")
    if r["by_rule_confidence"]:
        table = _cells_table("By detection rule × confidence", ("rule", "band"))
        for rule, bands in sorted(r["by_rule_confidence"].items()):
            for band, cell in bands.items():
                table.add_row(_outside(rule), _esc_markup(band), *_counts(cell))
        console.print(table)
    table = _cells_table("By provenance", ("from",))
    for where, cell in r["by_provenance"].items():
        table.add_row(_outside(where), *_counts(cell))
    console.print(table)
    console.print("[dim]bench: the bench's perimeter (rg-celebrimbor, rg-celebrimbor-*), the pre-observation — the "
                  "criteria before autonomy do not count it; unknown: outside it (the twin, production, any park), "
                  "a card attributed to no VM, or every card without AZURE_SUBSCRIPTION_ID[/dim]")


def _print_auditd() -> None:
    """AUD1 (#408): what the audit rule's window held at its last poll — a human login's execs as
    root, how many sensitive (cards), how many unreadable (cards). Zero events: no line arrives."""
    from glorfindel import auditd
    from glorfindel.detection_rules import _load_status
    for name, st in sorted(_load_status().items()):
        a = st.get("auditd") if isinstance(st, dict) else None
        if not isinstance(a, dict):
            continue
        n = {k: a[k] if type(a.get(k)) is int and a[k] >= 0 else 0 for k in auditd.COUNTS}
        at = _esc_markup("".join(c for c in str(a.get("at") or "")[:19] if c.isprintable()))
        console.print(f"auditd (AUD1), {_esc_markup(name)}: {n['events']} root exec(s) of a human login in its window, "
                      f"{n['sensitive']} sensitive, {n['unreadable']} unreadable (each a card) — last poll {at}")


def _memory_said(m: dict) -> str:
    """SEC17 (V-12): the memory's real cycles by age — those the bound leaves out of the search,
    kept and counted, never erased; and apart, those stored before cycles were dated, dated by the
    B2 floor (2026-10-16: an age at least their true one)."""
    days = f"{m.get('max_age_days', 0):g}"
    if m.get("error"):
        return f"[yellow]Memory: unreadable — {_esc_markup(''.join(c for c in str(m['error']) if c.isprintable()))}[/yellow]"
    if m.get("absent"):
        return f"Memory: none yet (age bound {days} days)"
    said = (f"Memory: {m.get('real', 0)} real cycle(s), {m.get('within', 0)} within {days} days "
            f"— {m.get('too_old', 0)} older left out of the search")
    said += " (kept, never erased)"
    if m.get("b2_dated"):
        said += (f"; of them {m['b2_dated']} dated by the B2 floor ({m.get('b2_floor', '2026-10-16')}: "
                 "stored before SEC17, no date of their own)")
    return said


def _print_memory(m: dict) -> None:
    console.print(_memory_said(m))


def _origin_proof_said(es: dict) -> str:
    """COR2 (#427): how far the origins of the root shells set aside are proven — confirmed
    outside the VM (Bastion, flows), or read in the VM only (COR1, a noise reducer)."""
    n, confirmed = int(es.get("origin_count") or 0), int(es.get("origin_confirmed") or 0)
    if confirmed <= 0:
        return "origin read in the VM only"
    if confirmed >= n:
        return "every one confirmed outside the VM (COR2)"
    return f"{confirmed} confirmed outside the VM (COR2), {n - confirmed} read in the VM only"


def _print_expected_sudo(es: dict) -> None:
    """ADM1: the sudo set aside as the administrators' expected ones, in `glorfindel report`.
    Every text here comes from a log line (an account, a command): printable only, no markup."""
    def shown(text) -> str:
        return _esc_markup("".join(c for c in str(text) if c.isprintable()))

    if es.get("error"):
        console.print(f"[yellow]Expected sudo: journal unreadable — {shown(es['error'])}[/yellow]")
        return
    if es.get("unreadable"):
        console.print(f"[yellow]Expected sudo: {es['unreadable']} journal line(s) unreadable[/yellow]")
    if not es.get("count"):
        if es.get("journal_from"):
            console.print("Expected sudo (no card, ADM1): 0 in this period")
        return
    per_vm = ", ".join(f"{shown(k)} {v}" for k, v in sorted(es["by_asset"].items()))
    per_account = ", ".join(f"{shown(k)} {v}" for k, v in sorted(es["by_account"].items()))
    console.print(f"Expected sudo (no card, ADM1): [bold]{es['count']}[/bold] — per VM: {per_vm} · "
                  f"per account: {per_account}")
    if es.get("origin_count"):
        # COR1: root shells set aside because every SSH session came from an expected origin.
        per_origin = ", ".join(f"{shown(k)} {v}" for k, v in sorted(es["by_origin"].items()))
        console.print(f"  of which root shells from an expected origin (COR1): [bold]{es['origin_count']}[/bold]"
                      f" — {per_origin} · {_origin_proof_said(es)}")
    for e in es.get("latest") or []:
        via = ""
        if e.get("origin"):
            how = f"confirmed by {shown(e['proof'])}" if e.get("proof") else "origin read in the VM only"
            via = f"  (from {shown(e['origin'])}, {how})"
        console.print(f"[dim]  {shown(e['at'][:19])}  {shown(e['asset'])}  {shown(e['account'])}  "
                      f"{shown(e['command'])}{via}[/dim]")
    if es.get("journal_from"):
        console.print(f"[dim]  journal from {shown(es['journal_from'][:19])} "
                      f"(~/.glorfindel/expected_sudo.jsonl)[/dim]")


@cli.command()
@click.argument("vm")
@click.option("--yes", is_flag=True, help="Accept the reserves shown without prompting.")
def activate(vm: str, yes: bool):
    """Turn on autonomous response for a VM after its readiness check (lot L6).

    VM: short name, <group>/<name> or full resource id. Shows the verdict and every reserve; a VM that
    is not ready is refused. The reserves accepted are recorded: one that appears later
    puts the VM back in human_only, with an alert.
    """
    from glorfindel import readiness
    from glorfindel.actions import AzureConnector
    from glorfindel.config import load_glorfindel_config, set_asset_mode

    rid = _resolve_resource_id(vm)
    if "/" not in rid:
        raise click.ClickException(
            f"{vm}: resource id unknown — pass the full id, or start `glorfindel watch` so discovery finds the VM.")
    _say_vm(rid)                                # read back before anything, --yes too (MSK3)

    try:
        quarantine = load_glorfindel_config().isolation.quarantine_nsg
    except Exception:
        quarantine = True
    connector = AzureConnector(dry_run=False)
    a = readiness.assess(rid, connector, quarantine_nsg=quarantine)
    # « VM dans l'abonnement <target>, Glorfindel agit dans <mine> » (other_subscription): both said without their ids (MSK2).
    from glorfindel.actions import _subscription_of
    subs = [s for s in (getattr(connector, "_subscription_id", None), _subscription_of(rid))
            if isinstance(s, str) and s]
    colors = {"ready": "green", "reserve": "yellow", "not_ready": "red"}
    console.rule(f"[bold]Autonomous response — {a['vm']}[/bold]")
    console.print(f"  Verdict : [{colors[a['verdict']]}]{a['verdict']}[/{colors[a['verdict']]}]")
    for r in a["reasons"]:
        console.print(f"  • [{r['level']}] {_esc_markup(_ids_masked(r['message'], subscriptions=subs))}",
                      soft_wrap=True)
        if r.get("fix"):
            console.print(f"    [dim]fix: {_esc_markup(_ids_masked(r['fix'], subscriptions=subs))}[/dim]", soft_wrap=True)
    refusal = readiness.activation_refusal(a, a["reserve_codes"])
    if refusal:
        raise click.ClickException(_ids_masked(refusal, subscriptions=subs))
    if a["reserve_codes"] and not yes and not click.confirm(
            f"Accept these reserves ({', '.join(a['reserve_codes'])}) and turn on "
            "autonomous response?", default=False):
        console.print("Aborted.")
        return
    try:
        set_asset_mode(a["vm"], "non_disruptive")
    except ValueError as exc:                # CFG4: EditRefused — the file refused, or not an exact name
        raise click.ClickException(str(exc)) from exc
    readiness.record_assessment(a, rid)
    readiness.acknowledge(rid, a["reserve_codes"], by="cli")
    readiness.resolve_card(rid)
    console.print(f"[green]✓ {a['vm']}: autonomous response on (non_disruptive).[/green]")


@cli.command("list")
@click.option("--ids", "show_ids", is_flag=True,
              help="The VMs' full ARM ids, the subscription's included (this terminal only: never "
                   "to paste). Without it, a VM is said by its name and group.")
def list_active(show_ids: bool):
    """List discovered VMs and any active Glorfindel actions (isolation, blocked IPs).

    A VM is said by its name and its resource group, never its full id (MSK2): the output is
    pasted in an issue or a thread. The commands it suggests take the short name; two VMs of one
    name take the full id, which --ids shows."""
    from datetime import datetime, timezone
    from glorfindel.actions import active_blocks, active_isolations
    from glorfindel.exposed_blocks import said as _exposed_said      # SEC2c: the exposed zone's deadline
    now = datetime.now(timezone.utc)

    def _age(ts: str) -> str:
        if not ts:
            return ""
        age_m = int((now - datetime.fromisoformat(ts)).total_seconds() // 60)
        return f"{ts[:19].replace('T', ' ')} UTC ({age_m}m ago)"

    isolations = {i["resource_id"].lower(): i for i in active_isolations()}
    blocks: dict[str, list] = {}
    for b in active_blocks():
        blocks.setdefault(b["resource_id"].lower(), []).append(b)

    # Discovered assets from AssetRegistry (survives between runs)
    discovered: dict[str, str] = {}  # resource_id.lower() → resource_id (canonical)
    try:
        from glorfindel.discovery import AssetRegistry
        for asset in AssetRegistry().all():
            discovered[asset.resource_id.lower()] = asset.resource_id
    except Exception:
        pass

    # Resolved autonomy mode per asset (for display)
    try:
        from glorfindel.config import load_glorfindel_config
        _autonomy = load_glorfindel_config().autonomy
    except Exception:
        _autonomy = None

    all_ids_lower = sorted(set(isolations) | set(blocks) | set(discovered))
    if not all_ids_lower:
        console.print("[dim]No discovered VMs and no active actions.[/dim]")
        console.print("[dim]Start 'glorfindel watch' to discover assets via Heartbeat.[/dim]")
        return

    console.rule(f"[bold cyan]Glorfindel — {len(all_ids_lower)} VM(s)[/bold cyan]")
    for rid_lower in all_ids_lower:
        resource_id = discovered.get(rid_lower) or (
            isolations.get(rid_lower, {}).get("resource_id")
            or blocks.get(rid_lower, [{}])[0].get("resource_id", rid_lower)
        )
        vm_short = resource_id.split("/")[-1]

        has_action = rid_lower in isolations or rid_lower in blocks
        status_color = "bold red" if rid_lower in isolations else (
            "bold yellow" if rid_lower in blocks else "bold"
        )
        console.print(f"[{status_color}]{vm_short}[/{status_color}]")
        # The name every command takes back to this VM (`_name_for_a_command`), else the full id,
        # shown with --ids only (MSK2).
        target = resource_id if show_ids else _name_for_a_command(resource_id)
        console.print(f"  [dim]{_esc_markup(resource_id if show_ids else _vm_said(resource_id))}[/dim]",
                      soft_wrap=True)

        if _autonomy is not None:
            from glorfindel.readiness import effective_mode
            _mode, _hold = effective_mode(resource_id, _autonomy.resolve(vm_short))
            _mode_color = "yellow" if _mode == "human_only" else "green"
            _held = (f"  [dim](configured {_hold['configured']}, held: {_esc_markup(_ids_masked(_hold['message']))}"
                     f" → glorfindel activate {_esc_markup(target)})[/dim]") if _hold else ""
            console.print(f"  mode: [{_mode_color}]{_mode}[/{_mode_color}]{_held}",
                          soft_wrap=True)

        if rid_lower in isolations:
            iso = isolations[rid_lower]
            ts = iso.get("isolated_at", "")
            label = "ISOLATED (PARTIAL)" if iso.get("partial") else "ISOLATED"
            if any(p.get("kind") == "quarantine" for p in iso.get("placements") or []):
                label += " · quarantine NSG"
            checked = f"  [dim]verified {_age(iso['verified_at'])}[/dim]" if iso.get("verified_at") else ""
            console.print(f"  [red]{label}[/red]  {_age(ts)}{checked}")
            for w in _state_warnings(iso, "release_failed"):
                console.print(f"    [bold red]⚠ {_esc_markup(_ids_masked(w))}[/bold red]", soft_wrap=True)
            console.print(f"  [dim]→ glorfindel release {_esc_markup(target)} --yes[/dim]",
                          soft_wrap=True)

        for b in blocks.get(rid_lower, []):
            ts = b.get("blocked_at", "")
            label = "BLOCKED (PARTIAL)" if b.get("partial") else "BLOCKED"
            console.print(f"  [yellow]{label}[/yellow]   {b['ip']}  {_age(ts)}{_esc_markup(_exposed_said(b, now))}")
            for w in _state_warnings(b, "unblock_failed"):
                console.print(f"    [bold red]⚠ {_esc_markup(_ids_masked(w))}[/bold red]", soft_wrap=True)
            console.print(f"  [dim]→ glorfindel unblock {b['ip']} {_esc_markup(target)} --yes[/dim]",
                          soft_wrap=True)

        if has_action:
            console.print(
                f"  [dim]→ glorfindel reset {_esc_markup(target)} --yes  (all at once)[/dim]",
                soft_wrap=True)
        console.print()


def _state_warnings(entry: dict, failed_key: str) -> list[str]:
    """What `list` must say next to ISOLATED / BLOCKED — the same flags the console
    shows as chips. A partial isolation used to print as a plain ISOLATED while one
    NIC carried no rule at all (real run, 2026-10-05, topology multinic)."""
    out = []
    if entry.get("partial"):
        nic = entry.get("failed_nic")
        out.append(f"partial: NIC {nic} not covered" if nic else "partial: not every NIC is covered")
    if entry.get(failed_key):
        out.append("rules still on Azure after a failed removal: " + ", ".join(entry[failed_key]))
    if failed_key == "release_failed":
        from glorfindel.actions import platform_open_nics
        nics = platform_open_nics(entry.get("placements"))
        if nics:
            out.append("DNS/IMDS reachable on " + ", ".join(nics) + ": isolated by rules, not the "
                       "quarantine NSG — Azure only lets a rule deny them for every NIC behind an NSG")
    drain = entry.get("drain") or {}
    if drain.get("status") in ("failed", "partial", "unsupported"):
        out.append("open sessions not cut: " + str(drain.get("error") or drain.get("note") or drain["status"]))
    elif drain.get("status") == "pending":     # DRN1: still running on Azure at its last read
        from glorfindel.response.policy import drain_followed
        out.append("session cut pending: Run Command still running on Azure at its last read"
                   + (f" (asked {drain['asked_at']})" if drain.get("asked_at") else "")
                   + ("; the watch's reassertion pass reads it again" if drain_followed() else
                      "; the reassertion is off (GLORFINDEL_REASSERT_INTERVAL_S): not followed — "
                      "sessions perhaps still open"))
    found = [s for p in entry.get("placements") or [] for s in (p.get("shadowed_by") or [])]
    shadowed = [s for s in found if s.get("threat_port_open", True)]
    exposure = [s for s in found if not s.get("threat_port_open", True)]
    if shadowed:
        rules = ", ".join(sorted({f"{s.get('rule')} (priority {s.get('priority')})" for s in shadowed}))
        out.append(f"bypassed: {rules} evaluated before Glorfindel's deny")
    if exposure:
        rules = ", ".join(sorted({f"{s.get('rule')} (ports {s.get('ports')})" for s in exposure}))
        out.append(f"threat port blocked; other ports still reachable: {rules}")
    return out


def _do_reset_from_azure(resource_id: str, yes: bool, dry_run: bool) -> None:
    """reset --from-azure: the rules on Azure are the truth, local state is not needed."""
    from glorfindel.actions import AzureConnector

    vm_short = resource_id.split("/")[-1]
    connector = AzureConnector(dry_run=False)
    preview = connector.sweep_vm_rules(resource_id, dry_run=True)
    console.rule(f"[bold yellow]Reset (source : Azure) — {vm_short}[/bold yellow]")
    # What the preview could not settle comes first: an original NSG nobody knows (the
    # NIC stays in quarantine, the message says which tag to set), a subnet or a rule
    # list unreadable. It said "nothing to do" and exited 0 (sixth review, S4).
    if preview["failed"]:
        console.print(f"[red]✗ Impossible de tout établir pour {vm_short} :[/red]")
        for item in preview["failed"]:
            console.print(f"  • {_esc_markup(_ids_masked(item))}")
    elif not preview["deleted"]:
        console.print(f"[green]Aucune règle Glorfindel de {vm_short} sur ses NSG.[/green]")
    for name in preview["deleted"]:
        console.print(f"  • supprimer {_esc_markup(_ids_masked(name))}")
    for name in preview["kept_perimeter"]:
        console.print(f"  [dim]• conservée (blocage de périmètre, toutes les VMs) : {name}[/dim]")
    if dry_run or not preview["deleted"]:
        if preview["failed"]:
            sys.exit(2)
        return
    if not yes:
        click.confirm("\nProceed?", abort=True)
    result = connector.sweep_vm_rules(resource_id)
    if result["failed"]:
        console.print("\n[red]✗ Reset incomplet — règles encore en place :[/red]")
        for item in result["failed"]:
            console.print(f"  • {_esc_markup(_ids_masked(item))}")
        _record_manual_action("reset", resource_id, {"status": "partial", "vm": vm_short,
                                                     "source": "azure", "failed": result["failed"]})
        sys.exit(2)
    console.print(f"\n[green]✓ {len(result['deleted'])} règle(s) retirée(s), états locaux effacés.[/green]")
    console.print(f"[dim]{result['note']}[/dim]")
    _record_manual_action("reset", resource_id, {"status": "clean", "vm": vm_short, "source": "azure"})


def _do_reset(resource_id: str, yes: bool, dry_run: bool, from_azure: bool = False) -> None:
    """Shared implementation for reset/revert — what it lifts and how, glorfindel/gestures.py
    (FS1b: the watch's request of the queue runs the same code)."""
    from glorfindel.actions import AzureConnector
    from glorfindel.gestures import reset_apply, reset_targets

    resource_id = _resolve_resource_id(resource_id)
    _say_vm(resource_id)                        # read back before anything, --yes too (MSK3)
    if from_azure:
        _do_reset_from_azure(resource_id, yes, dry_run)
        return
    # Case-insensitive match; release_isolation clears the local file even when Azure has no
    # matching rule, so matching here is enough to recover.
    isolations, blocks = reset_targets(resource_id)

    if not isolations and not blocks:
        console.print(f"[green]Nothing to reset on {resource_id.split('/')[-1]}.[/green]")
        return

    vm_short = resource_id.split("/")[-1]
    console.rule(f"[bold yellow]Reset — {vm_short}[/bold yellow]")
    if isolations:
        console.print("  • Release isolation")
    for b in blocks:
        console.print(f"  • Unblock {b['ip']}")

    if dry_run:
        # An outline, never « clean »: nothing is read on Azure, nothing written — it said
        # « Reset complete — <vm> is clean » (I3V, #450).
        would = (["lever l'isolation"] if isolations else []) + [f"débloquer {b['ip']}" for b in blocks]
        console.print(f"\n[yellow]DRY RUN — aucune modification. Le reset ferait : {', '.join(would)} "
                      f"sur {vm_short} (rien n'est lu sur Azure : `--from-azure --dry-run` montre les "
                      "règles).[/yellow]")
        return

    if not yes:
        click.confirm("\nProceed?", abort=True)

    connector = AzureConnector(dry_run=dry_run)
    leftovers = reset_apply(connector, resource_id, isolations, blocks, say=console.print)

    if leftovers:
        # Say what is still in place instead of "is clean": these rules still cut the
        # VM off or block the IP, and their state is kept for a retry.
        console.print(f"\n[red]✗ Reset incomplet — {vm_short} garde des règles :[/red]")
        for item in leftovers:
            console.print(f"  • {_esc_markup(_ids_masked(item))}")
        if not dry_run:
            _record_manual_action("reset", resource_id, {"status": "partial", "vm": vm_short,
                                                         "failed": leftovers})
        sys.exit(2)
    console.print(f"\n[green]✓ Reset complete — {vm_short} is clean.[/green]")
    if not dry_run:
        _record_manual_action("reset", resource_id, {"status": "clean", "vm": vm_short})


@cli.command("reset")
@click.argument("resource_id")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
@click.option("--dry-run", is_flag=True)
@click.option("--from-azure", is_flag=True,
              help="Use the NSG rules on Azure as the source of truth (works without local "
                   "state): remove every glorfindel-* rule that belongs to this VM.")
def reset(resource_id: str, yes: bool, dry_run: bool, from_azure: bool):
    """Reset a VM to clean state: release isolation + unblock all IPs.

    Use when a VM has both isolation and IP blocks and you want to clear
    everything in one command. For finer control use 'release' or 'unblock'.
    With --from-azure, local state is not needed (lost state file, another
    container's state): the VM's own Glorfindel rules are found on its NSGs.

    RESOURCE_ID: the VM's short name, <group>/<name> (what the Discord bot's commands give) or
    its full id; the VM resolved is said before anything is done, --yes too.
    """
    _do_reset(resource_id, yes, dry_run, from_azure)


@cli.command("revert", hidden=True)
@click.argument("resource_id")
@click.option("--yes", is_flag=True)
@click.option("--dry-run", is_flag=True)
def revert(resource_id: str, yes: bool, dry_run: bool):
    """Alias for 'reset' (deprecated name)."""
    console.print("[dim]Note: 'revert' is an alias — prefer 'glorfindel reset'[/dim]")
    _do_reset(resource_id, yes, dry_run)


@cli.command("watch-key")
@click.option("--create", is_flag=True, help="Draw the key when there is none (the watch does it at its first start).")
def watch_key_cmd(create: bool):
    """The watch's public key and its fingerprint, to pin on the injectors' side (SEC19, N-03):
    EREGION_WATCH_KEY in orodruin.env, or in the operator's environment. Never the private key."""
    from eregion_core import watch_key
    try:
        public = watch_key.load_or_create().public if create else watch_key.read_public()
    except watch_key.KeyUnavailable as e:
        click.echo(f"✗ {e}", err=True)
        sys.exit(1)
    click.echo(f"export {watch_key.KEY_ENV}={watch_key.public_text(public)}")
    click.echo(f"# empreinte : {watch_key.fingerprint(public)}")


@cli.command("identity-contract")
def identity_contract_cmd():
    """The identity executor's contract (IR1b): what its own identity holds in Entra ID, read from its
    Graph token and read only on Graph, against the closed list — armed or passive, each right beyond
    the contract named. Its environment: EREGION_TENANT_ID, EREGION_IDENTITY_EXECUTOR_CLIENT_ID,
    EREGION_IDENTITY_EXECUTOR_CERTIFICATE (docs/operations.md, « L'exécuteur d'identité »). Writes
    nothing; exit 0 only if armed."""
    from glorfindel.providers.azure import identity_contract
    verdict = identity_contract.check()
    click.echo(f"identity executor: {verdict.verdict}")
    for m in verdict.missing:
        click.echo(f"  ✗ {m['code']}: {m['detail']}")
    for note in verdict.notes:
        click.echo(f"  note — {note}")
    if verdict.held:
        click.echo(f"  held: {', '.join(sorted(verdict.held))}")
    if verdict.armed:
        verbs = sorted(v for v in identity_contract.VERB_RIGHTS if verdict.allows(v))
        click.echo(f"  verbs its rights allow: {', '.join(verbs) or 'none'}")
    sys.exit(0 if verdict.armed else 1)


@cli.command()
@click.option("--memory-path", default=None)
def memory_stats(memory_path: str | None):
    """Show the memory the switch opens (MEM2), its cycles, those its age bound leaves out (SEC17)."""
    from glorfindel.config import memory_max_age_days
    from glorfindel.memory import CycleMemory
    m = CycleMemory(path=memory_path, max_age_days=memory_max_age_days())
    console.print(f"Cycles in memory: [cyan]{m.count()}[/cyan]  [dim]({_esc_markup(m.said())})[/dim]")
    console.print(_memory_said(m.age_census()))


@cli.command("check-ttl")
@click.option("--ttl", default=None, type=float, metavar="HOURS",
              help="Max isolation age in hours before its card (ttl_exceeded) — never a release. "
                   "0 escalates every isolation at once; a negative value is refused. "
                   "Given, it wins over GLORFINDEL_ISOLATION_TTL_H; else that variable, or 4h.")
@click.option("--dry-run", is_flag=True)
def check_ttl(ttl: float | None, dry_run: bool):
    """Escalate isolations that have exceeded the TTL — never release them.

    Releasing un-contains a VM: past the TTL a human decides (a VM can be waiting for a
    restore, or under investigation). Default TTL: 4h (--ttl or
    GLORFINDEL_ISOLATION_TTL_H). Safe to run from cron.
    """
    from glorfindel import config as _cfg
    try:
        ttl_h = _cfg.isolation_ttl_h(ttl)        # the watch's own reading (TTL1)
    except _cfg.TTLRefused as exc:               # negative or unreadable: refused, nothing escalated
        console.print(f"[bold red]TTL refusé[/bold red] — {_esc_markup(str(exc))} ; rien n'est escaladé.")
        raise SystemExit(1)
    if dry_run:
        console.print("[dim]DRY RUN — nothing recorded.[/dim]")
        return
    from glorfindel.reassert import ttl_alerts
    alerts = ttl_alerts(ttl_h)
    for a in alerts:
        console.print(f"[yellow]TTL exceeded[/yellow] — {a['vm']} isolated for {a['age_h']:.1f}h "
                      f"(limit {ttl_h}h): escalated, not released.")
    if not alerts:
        console.print(f"[green]No new isolation older than {ttl_h}h.[/green]")
    # JUG2c review: a card is written under its VM's lock, so its webhook notification is queued
    # (vm_notices.must_defer) — and no pass of this process would post it: from cron, without the
    # watch, never said. Posted here, outside the lock, bounded (10 s a post, a pass ~86 s at most);
    # a card an earlier run left in the queue too.
    _post_queued_notices()


def _post_queued_notices() -> None:
    """A one-off command's queued notices, posted before it ends (JUG2c review): the notices' relay
    pass, as the watch runs it — never raises, a notice left is the next pass's."""
    from glorfindel import vm_notices
    try:
        vm_notices.relay_pass()
    except Exception as exc:          # a notification never fails the command
        console.print(f"[yellow]Notices not posted ({type(exc).__name__}): the next pass says them.[/yellow]")


def _build_recovery_signal(resource_id: str, restore_result: dict, restore_time_s: int) -> dict:
    """The recovery_complete of a restore this process ran — vouched for in this process
    only (SEC3, glorfindel/signal_origin.py): the release precondition knows it is ours."""
    from datetime import datetime, timezone

    from glorfindel.signal_origin import vouch
    ts = datetime.now(timezone.utc)
    run_id = ts.strftime("%Y%m%dT%H%M%SZ")
    return vouch({
        "signal_id": f"{run_id}_recovery_complete",
        "timestamp": ts.isoformat(),
        "provider": "azure",
        "resource_id": resource_id,
        "resource_type": "vm",
        "ttp": "",
        "severity": "low",
        "event": "recovery_complete",
        "raw_signal": {
            "recovery_point_time": restore_result.get("recovery_point_time", ""),
            "restore_time_s": restore_time_s,
            "run_command_neutralized": restore_result.get("run_command_neutralized"),
            # What holds the release, when it isn't Run Command v1 itself: an extension
            # outside the allowlist, a managed Run Command (A3) — the card names it.
            **({"replay_vectors": list(restore_result["replay_vectors"])}
               if restore_result.get("replay_vectors") else {}),
            # SEC17: the VM is outside the list the restore defends (restore_vms): Run Command
            # was refused there — the card says it, a flag set by the code, never Azure's words.
            **({"run_command_refused": True} if restore_result.get("run_command_refused") is True else {}),
        },
        "context": {"run_id": run_id},
    })


def _restore_before(resource_id: str, before: str | None) -> tuple[str, str]:
    """(the moment the recovery point must precede, ISO 8601 UTC; why that one) — or
    ("", what to do) when nothing says when the attack on this VM began (SEC4c).

    --before wins (with its time zone: one without is refused, never guessed, RTZ1). Otherwise
    the moment the console and the bot
    propose for this VM's first-detected pending card (glorfindel/restore_plan.py, `card_of`,
    `proposed_moment`): the
    earliest the defender recorded — the card's first detection, the VM's isolation —, or, for
    an exercise card, the attack_started of its run in runs/, never after its first detection.
    A line of runs/ never gives the moment of a real incident (SEC8); no card, no moment."""
    from glorfindel import restore_plan
    if before:
        try:
            return restore_plan.parse_moment(before), "--before"
        except ValueError as exc:
            raise click.ClickException(f"--before : {exc}")
    plan = restore_plan.proposed_moment(resource_id, restore_plan.card_of(resource_id))
    if plan["before"]:
        return plan["before"], plan["why"]
    vm = resource_id.rstrip("/").split("/")[-1]
    if plan.get("no_zone"):      # RTZ1: what the card or the state carries, said — never guessed
        return "", (f"Moment de l'attaque non deviné pour {vm} : {plan['why']}. Passer --before "
                    "<ISO 8601 avec fuseau>, un instant avant son début.")
    _, isolated = restore_plan.isolation_time(resource_id)
    hint = f" La VM est isolée depuis {isolated} : l'attaque a commencé avant." if isolated else ""
    return "", (f"Moment de l'attaque inconnu pour {vm} : aucune carte en attente de cette VM "
                "n'en donne un (sa première détection, ou pour un exercice la ligne "
                "attack_started de son run). Le point le plus récent peut être postérieur à "
                "l'attaque : passer --before <ISO8601>, un instant avant son début." + hint)


# RST1 (h): the pairs a restore may run under. In the compose, the console's and the bot's
# containers name theirs (GLORFINDEL_AZURE_PAIR, a constant: docker-compose.yml); on a workstation,
# by the variable that holds each one's client id.
_PAIR_MARKS = {"console": "la paire de la console", "bot": "la paire du bot"}
_RESTORE_PAIRS = (("EREGION_CONSOLE_AZURE_CLIENT_ID", "la paire de la console", True),
                  ("GLORFINDEL_BOT_AZURE_CLIENT_ID", "la paire du bot", True),
                  ("GLORFINDEL_AZURE_CLIENT_ID", "la paire de la watch — elle ne restaure pas "
                                                 "(aucun rôle Restore) : un refus est attendu", False))


def _restore_identity() -> tuple[str, bool]:
    """(the kind of identity this restore runs under, whether it is a pair that restores) —
    never an id (RST1, h). DefaultAzureCredential takes AZURE_TENANT_ID, AZURE_CLIENT_ID and
    AZURE_CLIENT_SECRET when all three are set; otherwise it goes down its chain (a managed
    identity, the operator's `az login`…) without saying so: a console pair left empty on the
    workstation restored as someone else (bench, 09/11)."""
    def env(name: str) -> str:
        return os.environ.get(name, "").strip()
    cid, secret, tenant = env("AZURE_CLIENT_ID"), env("AZURE_CLIENT_SECRET"), env("AZURE_TENANT_ID")
    other = ("DefaultAzureCredential prend une autre identité (une identité managée, l'az login de "
             "l'opérateur…), sans le dire — pas forcément celle de la console")
    if not (cid or secret):
        return f"aucune paire AZURE_CLIENT_* dans l'environnement : {other}", False
    if not (cid and secret and tenant):
        empty = ", ".join(n for n, v in (("AZURE_CLIENT_ID", cid), ("AZURE_CLIENT_SECRET", secret),
                                         ("AZURE_TENANT_ID", tenant)) if not v)
        return f"paire de l'environnement incomplète ({empty} vide) : {other}", False
    mark = env("GLORFINDEL_AZURE_PAIR")
    if mark in _PAIR_MARKS:
        return f"{_PAIR_MARKS[mark]} (GLORFINDEL_AZURE_PAIR = {mark}, son conteneur)", True
    for var, said, restores in _RESTORE_PAIRS:
        if env(var) and env(var) == cid:
            return f"{said} (AZURE_CLIENT_ID = {var})", restores
    return "une paire AZURE_CLIENT_* de l'environnement, ni celle de la console ni celle du bot", False


@contextlib.contextmanager
def _restore_claimed(resource_id: str):
    """The VM claimed for this restore while it starts (glorfindel/jobs.py, SEC4c), or the command refused:
    another restore of it running or about to — here, or in the vault from another host (FS1g), said whole."""
    from glorfindel.jobs import RestoreBusy, restore_claim
    try:
        with restore_claim(resource_id):          # by its full id (SEC-H)
            yield
    except RestoreBusy as exc:
        raise click.ClickException(f"Restore refusé : {exc}.") from None
    except Exception as exc:
        if getattr(exc, "code", "") == "vault_job_running":     # FS1g: never a traceback, what to do said
            raise click.ClickException(str(exc)) from None
        raise


def _short_name(ref: str) -> str:
    """The last segment of an ARM id (a VM's, a vault's), or the name given as it is."""
    return str(ref or "").strip().rstrip("/").rsplit("/", 1)[-1]


def _vm_said(resource_id: str) -> str:
    """A VM as `glorfindel restore` says it: its name and its resource group, never its full id —
    the subscription's id stays off a terminal whose output is pasted in an issue or a thread
    (IML1c; read in the output of make bench-restore, 12/11)."""
    parts = str(resource_id or "").strip().rstrip("/").split("/")
    low = [p.lower() for p in parts]
    name = parts[-1]
    if "resourcegroups" in low[:-1]:
        i = low.index("resourcegroups")
        if i + 1 < len(parts) - 1:
            return f"{name} (groupe {parts[i + 1]})"
    return name


def _say_recovery_point(result: dict, before: str, why: str) -> None:
    """The point chosen, and why that one."""
    tier = " (niveau coffre, immuable)" if result.get("recovery_point_vault_tier") else ""
    console.print(f"  Point de restauration : {_esc_markup(str(result.get('recovery_point_time') or '?'))}"
                  f"{tier} — le plus récent avant {before} ({_esc_markup(why)})")


def _write_signal(signal: dict) -> Path:
    """A recovery signal is kept where only the defender writes (SEC3, #274):
    ~/.glorfindel/recovery_signals/ — not runs/, which the injectors write too."""
    from glorfindel.signal_origin import write_recovery_signal
    return write_recovery_signal(signal)


def _render_decision(state: dict, dry_run: bool) -> None:
    # SEC-F: the action is the model's free text — no guard replaces it before it is shown here.
    action = _outside(state.get("action", "?"))
    escalated = state.get("escalate", False)
    confidence = state.get("confidence", 0.0)
    outcome = state.get("outcome") or {}

    verified = outcome.get("verified")
    status_color = "yellow" if escalated else "green"
    status_label = "ESCALATED — awaiting human approval" if escalated else (
        "DRY RUN" if dry_run else "EXECUTED"
    )

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="dim", width=18)
    table.add_column()
    table.add_row("Decision", f"[bold]{action}[/bold]")
    table.add_row("[dim]LLM confidence (self-reported)[/dim]", f"[dim]{confidence:.0%}[/dim]")
    table.add_row("Status", f"[{status_color}]{status_label}[/{status_color}]")
    if "action_s" in outcome and not escalated and not dry_run:
        detection_s = state.get("signal", {}).get("raw_signal", {}).get("detection_time_s")
        action_s = outcome["action_s"]
        timing = f"{_outside(action_s)}s"
        if detection_s:
            timing = f"detect {_outside(detection_s)}s + {action} {_outside(action_s)}s"
        table.add_row("Timing", f"[dim]{timing}[/dim]")
    if "verified" in outcome and not escalated:
        if verified is True:
            verified_label = "[green]✓ action confirmed[/green]"
        elif verified is False:
            verified_label = "[red]✗ action failed — check manually[/red]"
        else:
            verified_label = "[yellow]⚠ verification not implemented[/yellow]"
        table.add_row("Verification", verified_label)
    # The model's words may copy the signal's id: said without it, here only — what the model
    # saw, and what the cycle stores, keep it (MSK2).
    table.add_row("Explanation", _esc_markup(_ids_masked(state.get("explanation", ""))))
    if escalated:
        table.add_row("Escalation reason", _esc_markup(_ids_masked(state.get("escalation_reason", ""))))
    console.print(table)

    console.print(Panel(
        _esc_markup(_ids_masked(state.get("reasoning", ""))),
        title="[dim]Reasoning[/dim]",
        border_style="dim",
        padding=(0, 1),
    ))


@cli.command("approve-rule")
@click.argument("proposal_id")
@click.option(
    "--rules",
    "rules_file",
    default=None,
    metavar="PATH",
    help="The shipped base detection_rules.yaml, read to resolve the rule's asset "
         "(default: auto-detected). Never written.",
)
def approve_rule(proposal_id: str, rules_file: str | None) -> None:
    """Approve a proposed detection rule into the client's layer.

    PROPOSAL_ID is the UUID shown by 'glorfindel pending' for a proposed_rule
    escalation. The rule is written to ~/.glorfindel/client_rules.yaml (P1: the
    client's layer, loaded over the shipped base, which an update replaces) and the
    proposal is marked approved in ~/.glorfindel/proposed_rules.jsonl.
    """
    from glorfindel.proposed_rules import approve

    target = rules_file or _find_rules_file()
    if not target:
        console.print(
            "[red]detection_rules.yaml not found.[/red] "
            "Pass --rules PATH or run from the project root."
        )
        return

    try:
        proposal = approve(proposal_id, target)
        from glorfindel import escalations as _esc
        _esc.resolve_by_proposal(proposal_id)
        vm = proposal["resource_id"].split("/")[-1]
        console.print(
            f"[green]✓ Rule '{proposal['rule_name']}' approved[/green] "
            f"for {vm} ({proposal['ttp']})."
        )
        verb = {"replaced": "Replaced in", "same": "Already in"}.get(proposal.get("rule_write"), "Written to")
        console.print(f"  {verb} the client's layer [dim]{proposal.get('rules_file')}[/dim]")
        if proposal.get("renamed_from"):
            console.print(f"  [yellow]Proposed as « {_esc_markup(proposal['renamed_from'])} », a shipped "
                          f"rule's name: approved as « {_esc_markup(proposal['rule_name'])} », the shipped "
                          "rule stays.[/yellow]")
        if proposal.get("replaces") == "client":
            console.print(f"  [yellow]⚠ It REPLACES the client rule « {_esc_markup(proposal['rule_name'])} » "
                          "that was there: its query is no longer loaded.[/yellow]")
        if not proposal.get("rule_bound", True):
            console.print(f"  [yellow]⚠ Not bound ({_esc_markup(proposal.get('rule_unbound_reason', ''))}): "
                          "written with the workspace in line, it applies to no "
                          "discovered VM — bind it in ~/.glorfindel/client_rules.yaml: "
                          "monitoring_backends: \\[<backend>], assets: \\[auto].[/yellow]")
        console.print(
            "  Restart 'glorfindel watch' to activate, "
            "then re-run the scenario to validate."
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")


@cli.command("reject-rule")
@click.argument("proposal_id")
def reject_rule(proposal_id: str) -> None:
    """Dismiss a proposed detection rule without adding it to detection_rules.yaml.

    PROPOSAL_ID is the UUID shown by 'glorfindel pending'.
    The proposal is marked rejected in ~/.glorfindel/proposed_rules.jsonl
    and will no longer appear in 'glorfindel pending'.
    """
    from glorfindel.proposed_rules import reject

    try:
        proposal = reject(proposal_id)
        from glorfindel import escalations as _esc
        _esc.resolve_by_proposal(proposal_id)
        console.print(
            f"[yellow]✗ Rule '{proposal['rule_name']}' rejected[/yellow] "
            f"({proposal['ttp']}) — removed from pending."
        )
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")


# ── P1: the client's layer of rules ──────────────────────────────────────────────

@cli.group("rules", invoke_without_command=True)
@click.option("--rules", "rules_file", default=None, metavar="PATH",
              help="The shipped base detection_rules.yaml (default: auto-detected).")
@click.pass_context
def rules_cmd(ctx: click.Context, rules_file: str | None) -> None:
    """The detection rules loaded: the shipped base, then the client's layer over it.

    Each rule says its layer; what the client's layer does to the base (a rule replaced,
    one disabled) is said under the table. `glorfindel rules check [--live]`: each rule
    bound to its backend, and (--live) its query run once, read-only (H2).
    """
    if ctx.invoked_subcommand:
        return
    from glorfindel.detection_rules import client_rules_path, load_config

    target = rules_file or _find_rules_file()
    if not target:
        console.print("[red]detection_rules.yaml not found.[/red] Pass --rules PATH.")
        raise SystemExit(1)
    try:  # with the config, rules bind to its backends (no misleading "rule disabled")
        from glorfindel.config import load_glorfindel_config
        gcfg = load_glorfindel_config()
    except Exception:
        gcfg = None
    cfg = load_config(target, glorfindel_cfg=gcfg)
    table = Table(box=None, pad_edge=False)
    for col in ("rule", "layer", "ttp", "assets"):
        table.add_column(col)
    for r in cfg.rules:
        layer = ("[bold red]client (remplace)[/bold red]" if r.replaces_base
                 else "[cyan]client[/cyan]" if r.layer == "client" else "base")
        if r.auto_apply:   # the backend whose VMs it applies to: a rule on none is inert
            assets = (f"auto ({r.monitoring_backend_name})" if r.monitoring_backend_name
                      else "[yellow]auto (aucun backend : inerte)[/yellow]")
        else:
            assets = r.asset_name or r.resource_id.split("/")[-1]
        table.add_row(_esc_markup(r.name), layer, r.ttp, assets)
    console.print(table)
    console.print(f"[dim]Base :[/dim] {target}")
    if cfg.client_file:
        state = ""
    elif client_rules_path().exists():
        state = " [yellow](ignorée : voir la note)[/yellow]"
    else:
        state = " [dim](absente)[/dim]"
    console.print(f"[dim]Couche du client :[/dim] {client_rules_path()}{state}")
    for note in cfg.notes:
        console.print(f"  [yellow]·[/yellow] {_esc_markup(note)}")
    for name in cfg.overrides:          # SEC2: said loudly, not as one note among others
        console.print(f"[bold red]⚠ Règle livrée « {_esc_markup(name)} » remplacée par la couche du "
                      "client[/bold red] — la règle livrée n'est plus chargée.")
    for name in cfg.disabled_base:
        console.print(f"[bold red]⚠ Règle livrée « {_esc_markup(name)} » désactivée par la couche du "
                      "client[/bold red] — sa technique n'est plus détectée.")
    for name in cfg.drifted:            # WL1: a stale copy of a shipped rule
        console.print(f"[bold red]⚠ Règle du client « {_esc_markup(name)} » : copie périmée d'une règle "
                      "livrée[/bold red] — la base a changé depuis la copie (la note ci-dessus dit "
                      "laquelle tourne).")


@rules_cmd.command("check")
@click.option("--rules", "rules_file", default=None, metavar="PATH",
              help="The shipped base detection_rules.yaml (default: auto-detected).")
@click.option("--live", is_flag=True, help="Run each rule's query once, read-only, on its backend.")
@click.option("--json", "as_json", is_flag=True, help="One JSON object (what Imladris's CD reads), errors reduced.")
@click.option("--query-timeout", "query_timeout_s", type=click.FloatRange(0.1, 600), default=30.0,
              show_default=True, help="Seconds a query is waited for.")
@click.option("--total", "total_s", type=click.FloatRange(0.1, 3600), default=120.0, show_default=True,
              help="Seconds for the whole check: the rules left past it are not run, and said.")
@click.pass_context
def rules_check_cmd(ctx: click.Context, rules_file: str | None, live: bool, as_json: bool,
                    query_timeout_s: float, total_s: float) -> None:
    """Each loaded rule (base, client's layer, approved): bound to its backend, and with
    --live its query run once — ok (zero rows included), error (syntax, a table absent, no
    backend bound), timeout. No model, no write, no action. Exit 0 ok, 1 an error, 3
    timeouts only (H2, docs/operations.md)."""
    from glorfindel.rule_check import main as _check
    target = rules_file or ctx.parent.params.get("rules_file") or _find_rules_file()
    ctx.exit(_check(target, live=live, as_json=as_json, query_timeout_s=query_timeout_s, total_s=total_s,
                    echo=click.echo, console=console, echo_err=lambda line: click.echo(line, err=True)))


@cli.command("migrate-rules")
@click.option("--from", "from_file", required=True, metavar="PATH",
              help="detection_rules.yaml as this deployment modified it (rules approved into it before P1).")
@click.option("--base", "base_file", required=True, metavar="PATH",
              help="The same file as shipped by the reference it was modified from "
                   "(e.g. git show HEAD:glorfindel/rules/azure/detection_rules.yaml).")
@click.option("--dry-run", is_flag=True, help="Say what would move, write nothing.")
def migrate_rules(from_file: str, base_file: str, dry_run: bool) -> None:
    """Move rules approved into the shipped base (before P1) to the client's layer.

    What --from holds beyond --base goes to ~/.glorfindel/client_rules.yaml: a new rule
    as is, a changed base rule as a client rule of the same name (it overrides), a base
    rule --from removed as `disable`. Running it twice changes nothing more. Procedure on
    Imladris: infra/glorfindel-host/README.md, « Migrer les règles approuvées vers la couche du
    client ».
    """
    from glorfindel.rule_layers import ClientLayerError, migrate

    config_error = ""
    try:
        from glorfindel.config import load_glorfindel_config
        gcfg = load_glorfindel_config()
    except Exception as exc:   # said: a rule in line would otherwise read "no backend"
        gcfg, config_error = None, str(exc)
        console.print(f"[yellow]⚠ glorfindel-config.yaml illisible : {_esc_markup(config_error)} — "
                      "aucune règle au workspace en ligne ne peut être liée à son backend[/yellow]")
    try:
        report = migrate(from_file, base_file, dry_run=dry_run, glorfindel_cfg=gcfg,
                         config_error=config_error)
    except (FileNotFoundError, ClientLayerError) as e:
        console.print(f"[red]Error:[/red] {e} — nothing written")
        raise SystemExit(1)
    head = "[yellow]Dry run[/yellow] — would write" if dry_run else "[green]✓ Written[/green]"
    console.print(f"{head} to the client's layer [dim]{report['dest']}[/dim]")
    for key, label in (("added", "added"), ("replaced", "replaced"), ("same", "already there"),
                       ("overrides", "overrides a base rule"), ("disable", "base rule disabled"),
                       ("assets", "asset"), ("monitoring_backends", "monitoring backend")):
        for name in report[key]:
            console.print(f"  · {_esc_markup(name)}: {label}")
    for line in report["converted"]:
        console.print(f"  · [cyan]bound[/cyan] {_esc_markup(line)} — inert before (no VM), it detects from now on")
    for line in report["legacy"]:
        console.print(f"  [yellow]⚠ {_esc_markup(line)}[/yellow]")
    if not any(report[k] for k in ("added", "replaced", "same", "disable", "assets", "monitoring_backends")):
        console.print("  nothing to move: --from holds nothing beyond --base")
    elif not dry_run:
        console.print("  Restart the watch and the console to load it (rules are read at start).")


@cli.command("propose-rules")
@click.option("--ttp", "ttps", multiple=True,
              help="Restrict to specific TTPs (repeatable). Default: all uncovered.")
@click.option("--source", default="azure_monitor", show_default=True,
              help="Monitoring source to author for.")
@click.option("--include-planned", is_flag=True,
              help="Also author for 'planned' techniques (best-effort — the table "
                   "may not exist yet, so no schema grounding).")
@click.option("--model",
              default=lambda: glorfindel_model(),
              show_default=True)
@click.option("--rules", "rules_file", default=None, metavar="PATH",
              help="detection_rules.yaml (default: auto-detected) — TTPs already "
                   "covered there are skipped.")
@click.option("--dry-run", is_flag=True,
              help="Author and print, but do not record proposals.")
def propose_rules(ttps, source, include_planned, model, rules_file, dry_run):
    """Proactively author detection rules for catalog techniques with no rule yet.

    The cold-start half of the generative purple loop: instead of waiting for an
    attack to slip through (detection_missed), author detection up front from the
    technique catalog. For each uncovered technique in technique_catalog.yaml,
    introspect the target LAW table schema (getschema) and ask the LLM for a
    grounded query. Each result is a PROPOSAL — review with 'glorfindel pending',
    apply with 'glorfindel approve-rule <id>'. Nothing is activated automatically.
    """
    from glorfindel import detection_authoring as da

    catalog = da.load_catalog()
    if not catalog:
        console.print("[red]technique_catalog.yaml not found or empty.[/red]")
        return

    # TTPs already covered by an existing rule → skip. Pass the glorfindel config so
    # backends resolve (otherwise the loader prints misleading "rule disabled" warnings;
    # the .ttp we need is present regardless, but the noise is a false alarm).
    existing_ttps: set[str] = set()
    target = rules_file or _find_rules_file()
    if target:
        from glorfindel.detection_rules import load_rules
        from glorfindel.config import load_glorfindel_config as _lgc
        for r in load_rules(target, glorfindel_cfg=_lgc()):
            if r.ttp:
                existing_ttps.add(r.ttp)

    todo = da.techniques_needing_rules(
        catalog, existing_ttps,
        include_planned=include_planned, only_ttps=set(ttps),
    )
    if not todo:
        console.print(
            "[green]Nothing to author[/green] — every selected technique already "
            "has a rule (or none matched). Use --include-planned to widen."
        )
        return

    # Resolve a workspace_id for schema introspection (mono-LAW: first matching backend).
    workspace_id = ""
    try:
        from glorfindel.config import load_glorfindel_config
        cfg = load_glorfindel_config()
        be = next((b for b in cfg.monitoring_backends
                   if b.type == source and b.workspace_id), None)
        if be:
            workspace_id = be.workspace_id
    except Exception:
        pass

    # getschema introspection is READ-ONLY → run it even in --dry-run (dry-run only
    # suppresses recording the proposal, not the read). This lets `--dry-run` actually
    # exercise schema grounding for validation.
    detector = None
    if workspace_id and source in ("azure_monitor", "sentinel"):
        try:
            from glorfindel.detectors import detector_for
            detector = detector_for(source, workspace_id=workspace_id)
        except Exception as e:
            console.print(f"[dim]schema introspection unavailable: {e}[/dim]")

    grounding = "on" if detector else "off (no workspace resolved)"
    console.print(
        f"Authoring [bold]{len(todo)}[/bold] rule(s) "
        f"[dim](source={source}, schema-grounding={grounding})[/dim]\n"
    )

    authored = 0
    for entry in todo:
        ttp = entry["ttp"]
        try:
            proposal = da.author_rule(
                ttp=ttp, resource_id="", source=source,
                workspace_id=workspace_id, model=model, detector=detector,
            )
        except Exception as e:
            console.print(f"[red]✗ {ttp}: authoring failed:[/red] {e}")
            continue

        tag = "schema-grounded" if proposal.get("grounded_schema") else "no schema"
        console.print(
            f"[green]✓ {ttp}[/green] {proposal['rule_name']} "
            f"[dim](conf {proposal['confidence']:.2f}, {tag})[/dim]"
        )
        console.print(f"  {proposal['explanation']}")

        from glorfindel import proposed_rules as _pr
        # SEC-A4b: judged as soon as it is proposed — never offered when its approval would refuse it.
        refused = _pr.approval_refusal(proposal.get("source") or source, proposal.get("query") or "")
        if refused:
            console.print(f"  [yellow]Non approuvable : {_esc_markup(refused)}[/yellow]")
        if not dry_run:
            rk = {k: v for k, v in proposal.items() if k != "grounded_schema"}
            pid = _pr.record(run_id="propose-rules", signal_id="",
                             ttp=ttp, resource_id="", **rk)
            if refused:
                console.print(f"  [dim]proposal {pid} — inscrite non approuvable, "
                              "hors de glorfindel pending[/dim]")
            else:
                console.print(
                    f"  [dim]proposal {pid} — apply: "
                    f"glorfindel approve-rule {pid}[/dim]"
                )
        authored += 1
        console.print()

    verb = "would author" if dry_run else "authored"
    console.print(f"[bold]{authored}[/bold] proposal(s) {verb}. "
                  "Review: [dim]glorfindel pending[/dim]")


@cli.command("replay-campaign")
@click.argument("campaign_id")
@click.option("--runs-dir", default="runs", show_default=True,
              help="The runs root: the campaign under annatar/ or glorfindel/campaigns/<id>/ (SEC18).")
@click.option("--source", default="azure_monitor", show_default=True)
@click.option("--dry-run", is_flag=True,
              help="Replay and print, but do not write replay.json.")
def replay_campaign_cmd(campaign_id, runs_dir, source, dry_run):
    """Replay the missed scenarios of a campaign — "would the proposed rule have caught it?".

    Closes the generative purple loop: for each scenario the deterministic poller MISSED,
    re-run the LLM-proposed rule against the attack's traces (read-only) and record the
    verdict in runs/glorfindel/campaigns/<id>/replay.json. Reads Annatar's manifest.json post-hoc only.
    Activates nothing — a rule that would have caught it stays a proposal until approve-rule.
    """
    from glorfindel import campaign_replay as _cr
    from glorfindel import proposed_rules as _pr

    # Resolve a workspace_id for the read-only replay query (mono-LAW: first matching backend).
    workspace_id = ""
    try:
        from glorfindel.config import load_glorfindel_config
        cfg = load_glorfindel_config()
        be = next((b for b in cfg.monitoring_backends
                   if b.type == source and b.workspace_id), None)
        if be:
            workspace_id = be.workspace_id
    except Exception:
        pass

    detector = None
    if workspace_id and source in ("azure_monitor", "sentinel"):
        try:
            from glorfindel.detectors import detector_for
            detector = detector_for(source, workspace_id=workspace_id)
        except Exception as e:
            console.print(f"[dim]replay query backend unavailable: {e}[/dim]")

    try:
        doc = _cr.replay_campaign(
            campaign_id, runs_dir=runs_dir, detector=detector,
            proposals=_pr.all_proposals(), write=not dry_run,
        )
    except FileNotFoundError:
        console.print(f"[red]No manifest for campaign '{campaign_id}'[/red] "
                      f"under {runs_dir}/annatar/ nor {runs_dir}/glorfindel/campaigns/.")
        return
    except OSError as exc:   # SEC-A1 (V-02): Refused — a pipe, a link, a file too large
        console.print(f"[red]Manifest of campaign '{campaign_id}' refused:[/red] {exc} — never read")
        raise SystemExit(1) from None

    replays = doc["replays"]
    if not replays:
        console.print("[green]No missed scenarios to replay[/green] — detection caught "
                      "everything (or the campaign had no executed misses).")
        return

    for r in replays:
        if r["would_have_caught"] is True:
            tag = "[green]✓ would catch[/green]"
        elif r["would_have_caught"] is False:
            tag = "[yellow]✗ still misses[/yellow]"
        else:
            tag = "[dim]– not replayed[/dim]"
        console.print(f"  seq {r['seq']} {r['ttp']}: {tag} [dim]({r['detail']})[/dim]")

    caught = sum(1 for r in replays if r["would_have_caught"] is True)
    where = "(dry-run, not written)" if dry_run else \
        f"→ {runs_dir}/glorfindel/campaigns/{campaign_id}/replay.json"
    console.print(f"\n[bold]{caught}/{len(replays)}[/bold] missed scenarios would now be "
                  f"caught by the proposed rules. {where}")


@cli.command()
@click.argument("resource_id", required=False)
@click.option("--all", "audit_all", is_flag=True,
              help="Audit all resources from detection_rules.yaml.")
@click.option("--vault", default=None, help="Recovery Services vault (default: glorfindel-config.yaml).")
@click.option("--vault-rg", "vault_rg", default="",
              help="Vault resource group (central vault ≠ VM RG). Default: from config.")
@click.option("--dry-run", is_flag=True)
def audit(resource_id: str | None, audit_all: bool, vault: str, vault_rg: str, dry_run: bool):
    """Check that Glorfindel can execute all remediation actions.

    Verifies NSG access (isolate_vm / block_suspicious_ip), backup vault +
    recovery points (restore_from_backup), and compute access (snapshot).
    Surfaces IAM gaps and missing infrastructure with actionable fix commands.

    With --all: audits every resource_id referenced in detection_rules.yaml.
    """
    from glorfindel import audit as _audit
    from glorfindel.actions import AzureConnector

    # Resolve vault + its resource group from glorfindel-config.yaml (source of truth).
    # A central vault protects VMs across RGs, so the vault's RG must come from config,
    # not be derived from the VM's resource_id.
    from glorfindel.config import resolve_backup_vault
    vault, cfg_vault_rg, staging_storage = resolve_backup_vault(vault)
    vault_rg = vault_rg or cfg_vault_rg      # empty vault → the audit says so per VM

    connector = AzureConnector(dry_run=dry_run)
    targets: list[str] = []

    if audit_all or not resource_id:
        rules_file = _find_rules_file()
        if rules_file:
            from glorfindel.detection_rules import load_rules
            from glorfindel.config import load_glorfindel_config
            # Pass the glorfindel config so backends/workspace_id resolve — otherwise
            # every rule looks "disabled / no backend" (false alarm), the exact misleading
            # signal a config-fantôme produces. watch already loads rules this way.
            for rule in load_rules(rules_file, glorfindel_cfg=load_glorfindel_config()):
                if rule.resource_id and "${" not in rule.resource_id:
                    targets.append(rule.resource_id)
        if not targets:
            if resource_id:
                targets = [resource_id]
            else:
                console.print(
                    "[yellow]No resource_id provided and no resolved resources "
                    "in detection_rules.yaml.[/yellow]"
                )
                return
    else:
        targets = [_resolve_resource_id(resource_id)]

    targets = list(dict.fromkeys(targets))  # deduplicate, preserve order

    for rid in targets:
        vm = rid.split("/")[-1]
        console.rule(f"[bold cyan]Audit — {vm}[/bold cyan]")
        result = _audit.run(rid, connector, vault=vault, vault_rg=vault_rg,
                            staging_storage=staging_storage)
        _render_audit(result)
        console.print()


def _render_audit(result) -> None:
    from rich.table import Table

    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("Action", style="dim", width=36)
    table.add_column("Check", width=22)
    table.add_column("Status", width=8)
    table.add_column("Details")

    for c in result.checks:
        if c.status == "ok":
            badge = "[green]✓ ok[/green]"
        elif c.status == "warn":
            badge = "[yellow]⚠ warn[/yellow]"
        elif c.status == "fail":
            badge = "[red]✗ fail[/red]"
        else:
            badge = "[dim]— skip[/dim]"

        table.add_row(c.action, c.name, badge, c.message)
        if c.fix:
            table.add_row("", "", "", f"[dim]Fix: {c.fix}[/dim]")

    console.print(table)
    if result.ready:
        console.print("  [green]✓ All remediation capabilities confirmed.[/green]")
    else:
        fails = sum(1 for c in result.checks if c.status == "fail")
        console.print(
            f"  [red]✗ {fails} gap(s) detected — remediation may fail during an incident.[/red]"
        )


@cli.command()
def bot():
    """Start the Discord bot — watches escalations and posts interactive embeds."""
    from glorfindel.bot import run
    run()


@cli.command()
def dashboard():
    """Full-screen TUI: resources, live feed, and escalations in one view.

    Refreshes every 2s. Reads active isolations/blocks from ~/.glorfindel/
    and the most recent run from runs/. Press Ctrl+C to exit.
    """
    from glorfindel.tui import run
    run()


@cli.command("war-room", hidden=True)
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=7007, show_default=True)
def war_room(host: str, port: int):
    """Alias for 'eregion console' (former name: the War Room became the Eregion console)."""
    from eregion_console.api import serve
    serve(host=host, port=port)
