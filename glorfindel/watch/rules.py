"""The watch's detection rules — WCH1 (#1019): out of glorfindel/cli.py's `watch()`, nothing changed in
what it loads, starts or says.

The rules loaded and polled (the RulePoller), expanded for every asset discovery finds, the client's
layer said; the private IP → VM listing and the control plane's topology both read once, cached; the
non-blocking audit at startup.
"""
from __future__ import annotations

import threading

from rich.markup import escape as _esc_markup

from glorfindel.terminal import outside as _outside


def _shared_private_ips():
    """The watch's one private IP → VM map (detection_rules.IpOwners): the connector made
    at its first read, the listing cached 5 min."""
    from glorfindel.detection_rules import IpOwners
    made: list = []

    def listing() -> dict:
        if not made:
            from glorfindel.actions import AzureConnector
            made.append(AzureConnector(dry_run=False))
        return made[0].private_ip_owners()
    return IpOwners(listing)


def _shared_topology():
    """What a card of the control plane is filed on (AL1c, glorfindel/card_target.py): the VMs an
    NSG covers, a disk's VM, a snapshot's source — read on Azure by the connector made at the
    first need, cached."""
    from glorfindel.card_target import Topology
    made: list = []

    def listing() -> dict:
        if not made:
            from glorfindel.actions import AzureConnector
            made.append(AzureConnector(dry_run=False))
        return made[0].control_topology()
    return Topology(listing)


def _say_inert(console, rules, dry_run: bool) -> None:
    """Honest signal > silence: if no rule can actually poll a backend (no
    monitoring_backend with a workspace_id resolved, or every rule disabled),
    detection fires NOTHING. Say so loudly at startup instead of looking
    healthy while detecting nothing — the failure mode that torpedoes a first
    external test ("your thing detects nothing")."""
    from glorfindel.detection_rules import detection_inert as _det_inert
    if not dry_run and rules and _det_inert(rules):
        console.print(
            "[bold red]⚠ DÉTECTION INERTE[/bold red] — aucune règle ne peut "
            "interroger un backend de monitoring.\n"
            "  Cause probable : aucun [bold]monitoring_backend[/bold] (avec "
            "workspace_id) résolu dans glorfindel-config.yaml, ou toutes les "
            "règles désactivées.\n"
            "  → Renseigne la section [bold]monitoring_backends[/bold] de "
            "glorfindel-config.yaml. Sans ça, Glorfindel ne détecte rien."
        )


def _say_layers(console, det_cfg) -> None:
    """P1: the client's layer, and what it did to the base — said, not silent."""
    rules = det_cfg.rules
    if det_cfg.client_file:
        n_client = sum(1 for r in rules if r.layer == "client")
        console.print(f"[dim]Couche du client :[/dim] {n_client} règle(s) — "
                      f"[dim]{det_cfg.client_file}[/dim]")
    for note in det_cfg.notes:
        console.print(f"  [yellow]·[/yellow] {_esc_markup(note)}")
    # SEC2: a shipped rule replaced by the client's layer — its detection is gone
    # unless the replacement detects as well. Said loudly, not as one note among others.
    for name in det_cfg.overrides:
        console.print(f"[bold red]⚠ Règle livrée « {_esc_markup(name)} » remplacée par la "
                      f"couche du client[/bold red] — la règle livrée n'est plus chargée "
                      f"([dim]{det_cfg.client_file}[/dim]) ; si ce n'est pas voulu, la "
                      f"retirer de la couche du client.")
    for name in det_cfg.disabled_base:
        console.print(f"[bold red]⚠ Règle livrée « {_esc_markup(name)} » désactivée par la "
                      f"couche du client[/bold red] — sa technique n'est plus détectée "
                      f"([dim]{det_cfg.client_file}[/dim]) ; si ce n'est pas voulu, la "
                      f"réactiver.")
    # WL1: a client rule copied from a shipped one that changed (or went) since — stale.
    for name in det_cfg.drifted:
        console.print(f"[bold red]⚠ Règle du client « {_esc_markup(name)} » : copie périmée "
                      f"d'une règle livrée[/bold red] — la base a changé depuis la copie (la "
                      f"note ci-dessus dit laquelle tourne) ; reprendre la copie dans "
                      f"[dim]{det_cfg.client_file}[/dim].")


class Rules:
    """The rules file the watch runs on (`rules_file`, None: no rules) and its RulePoller, kept as
    soon as it is made — stopped at Ctrl+C even when what followed it failed."""

    def __init__(self, console, rules_file: str | None, *, dry_run: bool, mode_override) -> None:
        self.console = console
        self._rules_file = rules_file
        self.dry_run = dry_run
        self.mode_override = mode_override
        self._rule_poller = None
        self.loaded: list = []           # LOGF1: the rules polled, their tables followed (log_tasks.py)

    def start(self, rule_dispatch, ip_owners) -> None:
        """Load the rules and start polling them; what fails is said, never stops the watch."""
        if not self._rules_file:
            return
        console, dry_run = self.console, self.dry_run
        try:
            from glorfindel.config import load_glorfindel_config
            from glorfindel.detection_rules import RulePoller, load_config as _load_det_cfg
            import glorfindel.discovery  # noqa: F401 — imported here, before the poller's threads, as ever

            _glorfindel_cfg = load_glorfindel_config()
            det_cfg = _load_det_cfg(self._rules_file, glorfindel_cfg=_glorfindel_cfg)
            rules = det_cfg.rules
            self.loaded = list(rules or [])
            _say_inert(console, rules, dry_run)

            if rules:
                # Private IP → VM (the shared listing, above): routes a row made FROM a
                # VM (T1041 storage calls) to that VM.
                # What a card of the control plane is filed on (AL1c): read on Azure, cached.
                self._rule_poller = RulePoller(rules, rule_dispatch, dry_run=dry_run, ip_owners=ip_owners,
                                               topology=None if dry_run else _shared_topology())
                self._rule_poller.start()
                self._start_discovery(_glorfindel_cfg)
                auto_count = sum(1 for r in rules if r.auto_apply)
                static_count = len(rules) - auto_count
                console.print(
                    f"[dim]Detection rules:[/dim] {static_count} static, "
                    f"{auto_count} auto-apply — from [dim]{_outside(self._rules_file)}[/dim]"
                )
            _say_layers(console, det_cfg)
        except Exception as exc:
            console.print(f"[yellow]⚠ Could not load rules: {_outside(exc)}[/yellow]")

    def _start_discovery(self, _glorfindel_cfg) -> None:
        """Start discovery service (non-blocking background thread), and the rules expanded for
        every asset it finds."""
        from glorfindel.discovery import AssetRegistry, start_discovery
        _registry = AssetRegistry()
        if self.dry_run or not _glorfindel_cfg.monitoring_backends:
            return
        from glorfindel.actions import AzureConnector
        from glorfindel.posture import PostureChecker
        from glorfindel.readiness import ReadinessTracker
        _posture = PostureChecker(
            _glorfindel_cfg, AzureConnector(dry_run=False)
        )
        _posture_s = _glorfindel_cfg.monitoring_backends[0].discovery.interval_s
        start_discovery(
            _glorfindel_cfg,
            dry_run=self.dry_run,
            posture_checker=_posture,
            # L6 gate: VMs configured autonomous are checked when discovered,
            # then at the posture cadence; held in human_only until ready.
            readiness_tracker=ReadinessTracker(
                AzureConnector(dry_run=False), interval_s=_posture_s,
                autonomy_override=self.mode_override),
            # SEC2b: the client's network (its VNets, its public IPs), never blocked — read here.
            network_reader=AzureConnector(dry_run=False).client_network,
        )
        posture_min = int(_posture_s / 60)
        self.console.print(
            f"[dim]Discovery:[/dim] "
            f"{len(_glorfindel_cfg.monitoring_backends)} backend(s) "
            f"— Heartbeat every 60s, posture (RSV/NSG) every {posture_min}min"
        )
        # The registry the discovery service FILLS — the one built above only
        # read the disk cache once, so a VM discovered after start-up (or
        # off when the watch started) was never polled (validation run,
        # 2026-10-06: no rule thread for the whole life of the watch).
        from glorfindel.discovery import get_registry
        _registry = get_registry()
        threading.Thread(target=self._expand_loop, args=(_registry, _glorfindel_cfg), daemon=True,
                         name="expand-rules").start()

    def _expand_loop(self, _registry, _glorfindel_cfg) -> None:
        """Expand auto-apply rules for every newly discovered asset, every
        minute (idempotent: running (rule, asset) threads are skipped; an
        evicted asset's thread stops and restarts when it comes back)."""
        import time as _t
        _t.sleep(10)  # give discovery 10s head start
        while True:
            self._expand_once(_registry, _glorfindel_cfg)
            _t.sleep(60)

    def _expand_once(self, _registry, _glorfindel_cfg) -> None:
        try:
            self._rule_poller.expand_for_discovered(_registry, _glorfindel_cfg)
        except Exception as exc:
            self.console.print(f"[yellow]expand rules: {_outside(exc)}[/yellow]")

    def stop(self) -> None:
        if self._rule_poller:
            self._rule_poller.stop()

    def start_audit(self) -> None:
        """Non-blocking audit at startup — warn if remediation capabilities are missing."""
        if not self.dry_run and self._rules_file:
            threading.Thread(target=self._startup_audit, daemon=True, name="audit-startup").start()

    def _startup_audit(self) -> None:
        try:
            from glorfindel import audit as _audit
            from glorfindel.actions import AzureConnector
            from glorfindel.detection_rules import load_rules
            connector = AzureConnector(dry_run=False)
            from glorfindel.config import resolve_backup_vault as _rbv
            _vault, _vault_rg, _staging = _rbv()
            _gcfg = None
            try:
                from glorfindel.config import load_glorfindel_config
                _gcfg = load_glorfindel_config()
                _rsv = _gcfg.backup_vault()
                if _rsv:
                    _vault = _rsv.vault_name or _vault
                    _vault_rg = _rsv.resource_group or ""
                    _staging = _rsv.restore_staging_storage
            except Exception:
                pass
            seen: set[str] = set()
            # With the config: rules bind to its backends. Without it, every rule
            # logged a misleading "rule disabled" warning at each start.
            for rule in load_rules(self._rules_file, glorfindel_cfg=_gcfg):
                rid = rule.resource_id
                if rid and "${" not in rid and rid not in seen:
                    seen.add(rid)
                    result = _audit.run(rid, connector, vault=_vault,
                                        vault_rg=_vault_rg, staging_storage=_staging)
                    if not result.ready:
                        vm = rid.split("/")[-1]
                        gaps = [c for c in result.checks if c.status == "fail"]
                        self.console.print(
                            f"[yellow]⚠ Audit gap on {_outside(vm)}:[/yellow] "
                            + _outside("; ".join(c.name for c in gaps))
                            + " — run 'glorfindel audit' for details"
                        )
        except Exception:
            pass
