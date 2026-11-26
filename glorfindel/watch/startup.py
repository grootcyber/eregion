"""What the watch says and checks before its loop — WCH1 (#1019): out of glorfindel/cli.py's `watch()`,
nothing changed in what it says, refuses, or in its order (glorfindel/watch/loop.py, `Watch.start`).

The libraries' logs, a config refused, the TTL, the state migrated; its autonomy, its credentials and its
identity said; the signed action queue; the return channel and the campaign reports; its own writes and
Orodruin's set aside from the exfiltration rule.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from rich.markup import escape as _esc_markup

from glorfindel.terminal import outside as _outside


def identity_note(environ=os.environ, in_container: bool | None = None) -> str:
    """What the watch says of its identity at start when it has no service principal of its own
    (SEC11, V-17): compose no longer falls back on AZURE_CLIENT_*, the former shared principal.
    "" when it has one. In a container, only a VM's managed identity can stand in (Imladris); on a
    workstation, none — the `az login` of the machine is not in the container. From the venv,
    the machine's `az login`."""
    if (environ.get("AZURE_CLIENT_ID") or "").strip():
        return ""
    if in_container is None:
        in_container = Path("/.dockerenv").exists()
    if in_container:
        return ("no service principal (its …_AZURE_CLIENT_* pair empty) — the VM's managed identity "
                "if this container runs on one (Imladris); on a workstation, no identity at all: every "
                "Azure call will fail")
    return ("no service principal (AZURE_CLIENT_* empty) — this machine's `az login`, or the VM's "
            "managed identity")


def _setup_logging() -> None:
    """Surface library logs (discovery cycles, posture, query failures) on stdout so
    the daemon threads aren't silent — `make glorfindel-logs` shows discovery
    activity and errors. basicConfig is a no-op if the root logger is already set up."""
    import logging as _logging
    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # The Azure SDK logs every HTTP request and response at INFO: 1.5 MB in 44 min of
    # watch (real run, 2026-10-05), drowning Glorfindel's own lines. Warnings still show.
    for _noisy in ("azure", "urllib3", "httpx", "LiteLLM"):
        _logging.getLogger(_noisy).setLevel(_logging.WARNING)


def _refuse_bad_config(console) -> None:
    """A badly written config is refused, and said (A3): the watch used to start on it —
    "Could not load rules", then no detection at all, or the defaults standing in for
    a key nobody read. It doesn't start until the file is fixed."""
    from glorfindel.config import ConfigError, load_glorfindel_config
    try:
        load_glorfindel_config()
    except ConfigError as exc:
        console.print("[bold red]glorfindel-config.yaml refusé[/bold red] — la watch ne démarre pas "
                      "sur une configuration mal écrite.\n" + _esc_markup(str(exc)))
        raise SystemExit(2)


def _watch_ttl_h(console) -> float:
    """The watch's TTL (TTL1): `config.isolation_ttl_h`, as `check-ttl` reads it. A negative or
    unreadable GLORFINDEL_ISOLATION_TTL_H never stops the watch — it used to (`float(...)` before the
    loop): said at its start, on the console and in the log, and the watch keeps 4 h."""
    import logging

    from glorfindel import config as _cfg
    try:
        return _cfg.isolation_ttl_h()
    except _cfg.TTLRefused as exc:
        ttl_h = _cfg.ISOLATION_TTL_H
        said = f"{exc} — la watch garde {ttl_h:g} h jusqu'à correction"
        console.print(f"[bold yellow]⚠ TTL refusé[/bold yellow] — {_esc_markup(said)}")
        logging.getLogger("glorfindel.ttl").warning("TTL refusé — %s", said)
        return ttl_h


def _warm_up_and_migrate(console, dry_run: bool) -> None:
    """Import the Azure SDK once, on the main thread, before discovery/poll/audit
    threads start — avoids concurrent first-import deadlocks (azure.core _ModuleLock).
    Then the state files, one lowercase keyed file per VM (fifth review, C2)."""
    if not dry_run:
        from glorfindel.actions import warm_up_azure_sdk
        warm_up_azure_sdk()
    try:
        from glorfindel.actions import migrate_state_files
        _moved = migrate_state_files()     # one lowercase keyed file per VM (fifth review, C2)
        if _moved:
            console.print(f"[dim]State: {_moved} file(s) migrated to the lowercase keyed names.[/dim]")
    except Exception as exc:
        console.print(f"[yellow]State migration skipped: {_outside(exc)}[/yellow]")


def _say_autonomy(console, agent, mode_override, dry_run: bool) -> None:
    """Surface the resolved autonomy policy at startup — it determines whether
    actions execute or are held for human approval."""
    _autonomy = agent.autonomy
    if getattr(agent, "config_error", ""):
        # Unreadable config: every VM runs in human_only, --mode included (G2) — not the
        # `default = <--mode>` the banner showed.
        console.print(
            f"[bold]Autonomy:[/bold] [yellow]glorfindel-config.yaml illisible "
            f"({_outside(agent.config_error[:200])}) — toutes les VM en human_only"
            + (f", --mode {mode_override} ignoré" if mode_override else "")
            + " jusqu'à correction[/yellow]"
        )
    else:
        modes = [a for a in _autonomy.assets if a.mode is not None]     # PRI2a: an entry may give a priority only
        console.print(
            f"[bold]Autonomy:[/bold] default = [cyan]{_autonomy.default}[/cyan]"
            + (f"  ([dim]{len(modes)} per-asset override(s)[/dim])" if modes else "")
        )
        for note in getattr(_autonomy, "notes", []):    # PRI2a: the former format, read until the 1.0
            console.print(f"[yellow]  note: {_outside(note)}[/yellow]")
    if not dry_run and (_autonomy.default != "human_only"
                        or any(a.mode not in (None, "human_only") for a in _autonomy.assets)):
        console.print(
            "[dim]  Readiness gate: a VM configured autonomous acts alone once checked "
            "ready (or its reserves confirmed); until then it stays in human_only.[/dim]"
        )
    _say_alerting(console, _autonomy)


def _say_alerting(console, _autonomy) -> None:
    """Process warning: human_only = detection without response until a human acts.
    On a critical asset with nobody watching the escalations, the threat runs free."""
    _has_human_only = (
        _autonomy.default == "human_only"
        or any(a.mode == "human_only" for a in _autonomy.assets)
    )
    from glorfindel.escalations import alerting_configured
    _has_alerting = alerting_configured()
    if _has_human_only and not _has_alerting:
        console.print(
            "[yellow]⚠ human_only mode active but no alerting configured.[/yellow]\n"
            "  In human_only, Glorfindel detects and recommends but does NOT act — "
            "escalations need a human.\n"
            "  Set GLORFINDEL_WEBHOOK_URL or the Discord bot (DISCORD_BOT_TOKEN and "
            "DISCORD_CHANNEL_ID), or watch the console (eregion console), "
            "so escalations are seen."
        )


def _say_memory(console, memory) -> None:
    """MEM2 (#1027): the memory by keys, switched on (GLORFINDEL_MEMORY=cles), said at the start — off,
    nothing is said, nothing changes. MEM2b: the memory by keys asked for and not opened, or an unknown
    switch — the memory by distance in its place (`memory.CycleMemory`) — said loud, here and on a card,
    closed at the next start that opens what was asked for."""
    from glorfindel import memory_keys
    if why := getattr(memory, "fallback", ""):
        console.print(f"[bold red]Memory:[/bold red] [red]{_esc_markup(why)}[/red]")
        memory_keys.fallback_card(why)
        return
    if memory is not None:
        memory_keys.fallback_card("")
    if getattr(memory, "mode", "") == "cles":
        console.print(f"[bold]Memory:[/bold] [cyan]{_esc_markup(memory.said())}[/cyan] — the precedents by "
                      "rule, VM, technique, then the newest")


def _say_credentials(console, agent, dry_run: bool) -> None:
    """Permission regime — read-only means no action can execute, by design."""
    _autonomy = agent.autonomy
    _perm = getattr(agent.connector, "permission_mode", lambda: "read_write")()
    console.print(f"[bold]Credentials:[/bold] [cyan]{_perm}[/cyan]")
    # SEC11 (V-17): no fallback on a former shared principal — a watch without its own says so.
    _identity = identity_note()
    if not dry_run and _identity:
        console.print(f"[bold]Identity:[/bold] {_identity}")
    if _perm == "read_only":
        # On read-only creds, any mode that would execute will fail at action time.
        _executing_modes = (
            _autonomy.default != "human_only"
            or any(a.mode not in (None, "human_only") for a in _autonomy.assets)
        )
        if _executing_modes:
            console.print(
                "[yellow]⚠ Read-only credentials with a non-human_only mode.[/yellow]\n"
                "  Autonomous actions will fail (no write permission). Either grant write "
                "roles to the SP, or keep all assets in human_only (observe-only)."
            )
        else:
            console.print(
                "[dim]  Observe-only deployment: detection + recommendations, no writes.[/dim]"
            )


def _start_action_queue(console, dry_run: bool, signer, say, runs_dir) -> None:
    """FS1a (#551): each card this watch writes that holds an action carries the proposal it signs
    with this key (eregion_core/action_queue.py, under eregion.action-queue/1) — nobody reads it
    yet to act (FS1b); the console and the bot keep their direct call. FS1b (#563): behind
    EREGION_ACTION_QUEUE=1 only, the watch picks the signed action queue up — runs/console/queue,
    runs/bot/queue — in a thread of its own, never this loop nor the heartbeat
    (glorfindel/queue_watch.py). Without the flag, nothing is read."""
    from glorfindel import escalations as _escalations
    from glorfindel import queue_watch as _queue_watch
    from glorfindel.actions import AzureConnector
    _escalations.sign_proposals(signer)
    try:
        _queue_watch.start(AzureConnector(dry_run=dry_run), signer, say=say, root=runs_dir)
    except _queue_watch.SecondWatch as exc:
        # SEC-B (audit du 06/11, V-10): with the queue, a second watch on this HOME is refused — never
        # two writers of the registers, nor two executions of one request. Before its heartbeat.
        console.print(f"[red]Watch refusée :[/red] {_esc_markup(str(exc))}")
        sys.exit(1)
    except Exception as exc:   # the watch goes on without its queue, and says it
        console.print(f"[red]File d'actions non relevée :[/red] {_esc_markup(str(exc))}")


def _start_campaign_reports(console, runs_dir) -> bool:
    """The thread that writes the report of each campaign Orodruin publishes (IA0, #167;
    analysis/hosted_report.py) — only with an exercise channel. Never raises: a report,
    or its thread failing to start, never stops the watch."""
    try:
        from analysis import hosted_report
        # Before the thread: the report reads a run's detections with Annatar's reader, a
        # bridge (scripts/component_check.py). Without Annatar it is said here, once — not by
        # every pass of a thread that could never write a report.
        from analysis import campaign_report  # noqa: F401
        return hosted_report.start(runs_dir) is not None
    except Exception as exc:  # the watch goes on without campaign reports
        # What the import said, as it is (SEC-Fc): a `[/…]` in it raised out of this guard.
        console.print(f"[yellow]Rapports de campagne désactivés — {type(exc).__name__}: "
                      f"{_outside(exc)}[/yellow]")
        return False


def _open_return_channel(console, dry_run: bool, runs_dir):
    """The return channel (#159): a run launched from Orodruin learns from it that this
    watch is up, and what it detected on the VMs that run exercises. Unset → None; a dry run, None."""
    if dry_run:
        return None
    from eregion_core import runs_layout as _layout
    from eregion_core import watch_channel as _wc
    _watch_channel = _wc.start()
    if _watch_channel is not None:
        console.print(f"[dim]Canal retour : {_outside(_watch_channel.channel)}[/dim]")
    else:
        # SEC18: no storage channel — the local channel of verdicts, the one directory of the
        # blue the red mounts (read-only): a run's verdict, never the reasoning.
        _watch_channel = _wc.start_local(_layout.dir_of(_layout.VERDICTS, runs_dir))
        if _watch_channel is not None:
            console.print(f"[dim]Canal des verdicts (local) : {_outside(_watch_channel.directory)}/[/dim]")
    # IA0 (#167): the campaigns published by Orodruin get their report written here.
    # SEC18: everything it pulls and writes goes to the watch's own directory.
    if _start_campaign_reports(console, _layout.dir_of(_layout.GLORFINDEL, runs_dir)):
        console.print("[dim]Rapports de campagne : runs/glorfindel/campaigns/<id>/report.md[/dim]")
    return _watch_channel


def _register_own_writes(console, _watch_channel, dry_run: bool) -> None:
    """SLF1 (#929): the watch's own writes in its return channel, set aside from the exfiltration
    rule (its identity, its container, its objects) — counted on the rule, never silent.
    SLF2 (#1010): Orodruin's writes in its exercise channel — its identity (EREGION_ORODRUIN_PRINCIPAL_ID),
    the container of EREGION_EXERCISE_CHANNEL, its account —, set aside from the same rule, counted."""
    from glorfindel import own_channel as _own_channel
    _own_source = _own_channel.of_publisher(_watch_channel) if _watch_channel is not None else None
    _own_channel.register(_own_source)
    if _own_source is not None:
        console.print("[dim]Voie de retour : ses propres écritures (l'identité de la watch, son conteneur, "
                      "ses objets) écartées de la règle d'exfiltration, comptées sur la règle[/dim]")
    elif getattr(_watch_channel, "channel", ""):
        console.print("[yellow]Voie de retour : URL illisible — aucune de ses écritures n'est écartée "
                      "de la règle d'exfiltration[/yellow]")
    _oro_exercise = _own_channel.of_env() if not dry_run else (None, "")
    _own_channel.register_exercise(_oro_exercise)
    if _oro_exercise[0] is not None:
        console.print("[dim]Canal d'exercices : les écritures d'Orodruin (son identité, son conteneur, son "
                      "compte) écartées de la règle d'exfiltration, comptées sur la règle[/dim]")
    elif _oro_exercise[1]:
        _why = {"unset": f"{_own_channel.ORODRUIN_ENV} absente",
                "malformed": f"{_own_channel.ORODRUIN_ENV} n'est pas un object id"}.get(
                    _oro_exercise[1], f"{_own_channel.EXERCISE_ENV} absente ou refusée")
        console.print(f"[yellow]Canal d'exercices : {_outside(_why)} — aucune écriture d'Orodruin n'est "
                      "écartée de la règle d'exfiltration[/yellow]")
