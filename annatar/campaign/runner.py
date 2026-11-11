"""Sequential, budgeted campaign executor — the blind-loop driver.

Runs a ratified campaign's scenarios one at a time, with a detection window and an
NSG reset between each (clean attribution vs IncidentRegistry; kill-chain logic;
detection latency). Honours the load-bearing guardrails at EXECUTION time (a
hand-edited manifest cannot bypass them):

  - re-check scope per scenario (allowlist Celebrimbor);
  - destructive scenario only runs if budget.allow_destructive;
  - stop at budget.max_scenarios; honour an externally-set kill_switch, re-read before each
    run and before each write of the manifest, kept once seen — and stop when it cannot be
    read or is gone (KS1, #648: fail-closed), said once and recorded in the manifest.

Annatar announces NOTHING to Glorfindel — it just runs and records detected/missed
into the manifest (read post-hoc by the blue replay engine).
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone
from importlib.util import find_spec
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.markup import escape

from annatar.campaign.manifest import CampaignManifest
from annatar.runner.engine import Engine, RunOutcome
from eregion_core import watch_gate
from eregion_core.channel_reader import Refused, read_json

console = Console()


# SEC5 (V-18): what the manifest says of the reset after a run refused before it acted.
REFUSED_NO_RESET = "not run: the run was refused before it touched the target"
# The refusals of the target itself (eregion_core/inscription.py, Orodruin's contract): the
# next runs on that target would be refused too — the campaign stops there for it.
TARGET_REFUSALS = ("safety:", "passive:")
# An engine that raised: no proof it touched the target, nor that its zone allows a reset.
ENGINE_RAISED = "engine raised:"
RAISED_NO_RESET = ("not run: the engine raised — whether it touched the target is unknown; "
                   "reset it by hand if it did (glorfindel reset <resource_id> --yes)")


# KS1 (#648): why a campaign stops before its next run (the manifest's ``stop_reason``).
KILL_SWITCH_SET = "kill switch set"
KILL_SWITCH_UNREADABLE = "kill switch unreadable — stopped, fail-closed"


class CampaignRefused(ValueError):
    """A campaign that does not start (V1): no live Glorfindel watch, or a resume with another
    --without-glorfindel than the one it started with. Its manifest is left as it was."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_reset(resource_id: str) -> str:
    """Reset NSG state (isolation + IP blocks) between scenarios.

    Returns what happened, recorded in the manifest: ``"reset"``, ``"skipped: …"`` or
    ``"failed: exit <rc>"`` (a non-zero exit did not reset). ``glorfindel reset`` is not in
    the Orodruin image (and outside the ``injector`` role). There, the ``glorfindel`` launcher
    IS on PATH — ``pip install -e ".[annatar]"`` installs every ``[project.scripts]`` entry —
    but the ``glorfindel`` package is not copied (annatar/Dockerfile), so the launcher would
    exit 1 on ``ModuleNotFoundError``. The guard therefore tests the PACKAGE first
    (``find_spec``), then the launcher: when either is missing, the reset is SKIPPED — quietly
    (no loud failure), without shelling out or writing anything — and the manifest says so.
    On Imladris nothing isolates (human_only, read-only), so there is nothing to reset anyway.
    """
    if find_spec("glorfindel") is None:
        return "skipped: glorfindel absent (package not installed — reset is not in the Orodruin image)"
    if shutil.which("glorfindel") is None:
        return "skipped: glorfindel absent (no launcher on PATH)"
    proc = subprocess.run(
        ["glorfindel", "reset", resource_id, "--yes"],
        check=False,
        capture_output=True,
        timeout=120,
    )
    # A reset that exits non-zero did not reset: say so, never "reset".
    if proc.returncode != 0:
        return f"failed: exit {proc.returncode}"
    return "reset"


class CampaignRunner:
    def __init__(
        self,
        campaign_dir: str | Path,
        *,
        dry_run: bool = False,
        reset_fn: Callable[[str], str | None] | None = None,
        engine_factory: Callable[[], Engine] | None = None,
        without_glorfindel: bool = False,
    ):
        self.campaign_dir = Path(campaign_dir)
        self.dry_run = dry_run
        self.reset_fn = reset_fn or _default_reset
        # V1 (#214): each run checks the watch itself; --without-glorfindel reaches each one.
        self.without_glorfindel = without_glorfindel
        self.engine_factory = engine_factory or (
            lambda: Engine(skip_preflight=False, without_glorfindel=without_glorfindel))
        # KS1 (#648): the stop met at a write of the manifest, kept — never written over.
        self._pending_stop: str | None = None

    def run(self) -> CampaignManifest:
        m = CampaignManifest.load(self.campaign_dir)
        self._pending_stop = None
        scope = m.scope
        budget = m.budget

        # A dry-run is a no-op preview — allowed in any state, mutates nothing.
        if self.dry_run:
            self._preview(m)
            return m

        if m.state not in ("ratified", "running"):
            if m.state in ("done", "aborted"):
                hint = "re-plan to run again (terminal state)"
            else:
                hint = "ratify it with --yes before running"
            raise ValueError(
                f"campaign {m.campaign_id} is '{m.state}' — {hint}"
            )

        # V1 (#214): a campaign is resumed the way it started — with Glorfindel, or without it:
        # its runs would otherwise mix measured and unmeasured detections.
        if m.state == "running" and m.without_glorfindel != self.without_glorfindel:
            said = "without" if m.without_glorfindel else "with"
            raise CampaignRefused(
                f"campaign {m.campaign_id} started {said} Glorfindel — resume it the same way "
                f"({'with' if m.without_glorfindel else 'without'} {watch_gate.FLAG})")
        # No live Glorfindel watch, no campaign — refused before its first run, its state left
        # as it was (ratified: it can run once the watch is up).
        if not self.without_glorfindel:
            no_watch = watch_gate.refusal()
            if no_watch:
                raise CampaignRefused(
                    f"campaign {m.campaign_id} refused — no live Glorfindel watch: {no_watch}")

        m.without_glorfindel = self.without_glorfindel
        m.set_state("running")
        self._save(m)

        # Multi-scenario advisory: an autonomous blue response (isolate_vm) mid-chain
        # persists and can break every downstream scenario (AMA/egress cut → no
        # telemetry, no attack traffic). Recommend running the chain with Glorfindel
        # in human_only so it detects+decides without executing. See 2026-07-30 e2e
        # finding (Fix A). Not enforced here — cross-container, operator's call.
        pending = sum(1 for s in m.scenarios if s.status == "pending")
        if pending > 1:
            console.print(
                "[yellow]⚠ Multi-scenario campaign: run Glorfindel in "
                "[bold]human_only[/bold] to avoid an autonomous isolation "
                "persisting across scenarios and breaking the chain "
                "(egress/telemetry cut).[/yellow]"
            )

        executed = sum(1 for s in m.scenarios if s.status == "executed")
        aborted = False
        # SEC5 (V-18): a target the engine refused (its inscription, its zone, the production
        # rule, Orodruin passive) is refused for the rest of the campaign — never run again,
        # never reset: nothing of the campaign acted on it.
        refused_targets: dict[str, str] = {}

        for entry in m.scenarios:
            if entry.status != "pending":
                continue  # resume: skip already-processed scenarios

            # kill switch — re-read from disk so an operator can stop mid-campaign; one that
            # cannot be read, or gone, stops it too (KS1); one seen at any write of the manifest
            # (during a run, at its reset) is kept (`_pending_stop`). Said here once.
            stop = self._pending_stop or self._stop_requested()
            if stop is not None:
                self._stopped(m, stop)
                aborted = True
                break

            # budget ceiling
            if executed >= budget.max_scenarios:
                entry.status = "skipped"
                entry.error = "budget: max_scenarios reached"
                self._save(m)
                continue

            # scope re-check (defence against a hand-edited manifest)
            guard = scope.check(entry.target_resource_id)
            if not guard.allowed:
                entry.status = "error"
                entry.error = f"out of scope: {guard.reason}"
                self._save(m)
                continue

            refused_why = refused_targets.get(entry.target_resource_id.lower())
            if refused_why:
                entry.status = "skipped"
                entry.error = f"target refused earlier in this campaign: {refused_why}"
                entry.reset = REFUSED_NO_RESET
                self._save(m)
                continue

            # destructive policy — the catalog's word, not the manifest's (SEC5, V-19): a
            # hand-edited manifest cannot call a destructive technique harmless.
            if self._destructive(entry, self.campaign_dir) and not budget.allow_destructive:
                entry.status = "skipped"
                entry.error = "destructive but budget.allow_destructive is false"
                self._save(m)
                continue

            outcome = self._execute(entry, m)
            if entry.status == "pending":
                # A stop met as the run was written down (KS1): the engine was never called.
                self._stopped(m, self._pending_stop)
                aborted = True
                break
            if entry.status == "executed":
                executed += 1
            elif (entry.error or "").startswith("glorfindel:"):
                # The watch died mid-campaign: every next run would be refused too.
                aborted = True
                break
            if (entry.error or "").startswith(ENGINE_RAISED):
                # Raised: whether it touched the target is unknown — a reset could release an
                # isolation on a VM the run never reached (its zone unread). None, and said.
                entry.reset = RAISED_NO_RESET
                self._save(m)
                continue
            if outcome is not None and outcome.refused:
                # Refused before it touched the target: nothing to reset, and the manifest
                # says so. A refusal of the target itself stops the campaign there.
                entry.reset = REFUSED_NO_RESET
                if (entry.error or "").startswith(TARGET_REFUSALS):
                    refused_targets[entry.target_resource_id.lower()] = entry.error
                self._save(m)
                continue

            # NSG reset between scenarios (clean attribution for the next one). What happened
            # is recorded on the entry — including a quiet skip when glorfindel is absent.
            if budget.reset_nsg_between:
                try:
                    status = self.reset_fn(entry.target_resource_id)
                except Exception as e:  # reset failure must not abort the campaign
                    status = f"failed: {e}"
                    console.print(f"[yellow]NSG reset failed: {e}[/yellow]")
                if isinstance(status, str):
                    entry.reset = status
                    self._save(m)

        # A stop asked during the last run, or met at its last write: the campaign did not end
        # as it was asked to — aborted, said once (KS1).
        if not aborted:
            stop = self._pending_stop or self._stop_requested()
            if stop is not None:
                self._stopped(m, stop)
                aborted = True
        m.set_state("aborted" if aborted else "done")
        self._save(m)
        return m

    # ── internals ────────────────────────────────────────────────────────────
    @staticmethod
    def _destructive(entry, campaign_dir: Path) -> bool:
        """Destructive if the manifest says so, or if the scenario the run will play is — read
        from its file, as the engine reads it (``scenario_destructive``: the catalog's word on
        its technique and source, unknown is destructive), never from the manifest's ``ttp``.
        A file that does not parse falls back to the manifest's ``ttp`` in the catalog: the
        engine refuses that scenario anyway."""
        from annatar.campaign.catalog import catalog_destructive
        from annatar.runner.engine import scenario_destructive
        from annatar.runner.parser import ScenarioParser

        if entry.destructive:
            return True
        try:
            scenario = ScenarioParser().load(str(campaign_dir / entry.scenario_file))
        except Exception:
            return catalog_destructive(entry.ttp) is not False
        return scenario_destructive(scenario)[0]

    def _execute(self, entry, m: CampaignManifest) -> RunOutcome | None:
        path = self.campaign_dir / entry.scenario_file
        entry.status = "running"
        entry.started_at = _utcnow()
        self._save(m)
        if self._pending_stop is not None:
            # The stop read at this very write (KS1): the engine is not called, the entry left
            # as it was.
            entry.status, entry.started_at = "pending", None
            self._save(m)
            return None

        console.print(
            f"[cyan]==>[/cyan] [{entry.seq}] {entry.ttp} ({entry.tactic}) — {path.name}"
        )
        try:
            outcome: RunOutcome | None = self.engine_factory().run(
                str(path), skip_confirm=True
            )
        except Exception as e:  # unexpected engine failure → error, continue campaign
            entry.status = "error"
            entry.error = f"{ENGINE_RAISED} {e}"
            entry.finished_at = _utcnow()
            self._save(m)
            return None

        entry.finished_at = _utcnow()
        if outcome is None or outcome.error:
            entry.status = "error"
            entry.error = (outcome.error if outcome else "run produced no outcome")
            entry.run_id = outcome.run_id if outcome else None
        else:
            entry.status = "executed"
            entry.run_id = outcome.run_id
            entry.detection = outcome.detection
            entry.detection_latency_s = outcome.detection_latency_s
        self._save(m)
        return outcome

    def _stop(self, m: CampaignManifest, stop: str) -> None:
        """Keep the stop met (the first one, never written over) and carry it into ``m``: the
        operator's kill switch set stays set in what the runner writes next."""
        if self._pending_stop is None:
            self._pending_stop = stop
        m.kill_switch = m.kill_switch or self._pending_stop == KILL_SWITCH_SET
        m.stop_reason = self._pending_stop

    def _stopped(self, m: CampaignManifest, stop: str) -> None:
        """The campaign stops here: the stop carried into ``m``, said once."""
        self._stop(m, stop)
        console.print(f"[red]✗ campaign {escape(m.campaign_id)} stopped: "
                      f"{escape(self._pending_stop)}[/red]")

    def _save(self, m: CampaignManifest) -> None:
        """Every write of the manifest by the runner (KS1): the stop on disk read first — a kill
        switch set during a run, a pipe or a file that cannot be read put there, is kept and
        carried into ``m``, never overwritten by what the runner holds in memory. A campaign
        whose directory is gone is not written again (never recreated from the runner)."""
        stop = self._pending_stop or self._stop_requested()
        if stop is not None:
            self._stop(m, stop)
        if not self.campaign_dir.is_dir():
            return
        m.save(self.campaign_dir)

    def _stop_requested(self) -> str | None:
        """Why the campaign stops before its next run, or None — its manifest's ``kill_switch``,
        re-read from disk so an operator can stop it mid-campaign. A manifest that cannot be
        read stops the campaign (KS1, #648: fail-closed — a stop never read is never taken for
        "go on"): gone (the runner never leaves it absent: deleted from outside), refused by the
        bounded reader (a pipe, a link, a file too large: SEC-A1), not JSON, nested too deep,
        an I/O error, not an object, or a ``kill_switch`` that is neither true nor false."""
        try:
            doc = read_json(self.campaign_dir / "manifest.json")
        except FileNotFoundError:
            return f"{KILL_SWITCH_UNREADABLE} (manifest gone)"
        except Refused as exc:
            return f"{KILL_SWITCH_UNREADABLE} (refused: {exc})"
        except Exception as exc:  # any other failure to read it stops it too
            return f"{KILL_SWITCH_UNREADABLE} ({type(exc).__name__})"
        switch = doc.get("kill_switch", False) if isinstance(doc, dict) else None
        if switch is True:
            return KILL_SWITCH_SET
        if switch is False:
            return None
        return f"{KILL_SWITCH_UNREADABLE} (kill_switch is not true or false)"

    def _preview(self, m: CampaignManifest) -> None:
        console.print(f"[yellow]DRY RUN — campaign {m.campaign_id}[/yellow]")
        for e in m.scenarios:
            console.print(
                f"  [{e.seq}] {e.ttp} ({e.tactic}) → {e.scenario_file} "
                f"[dim]target={e.target_resource_id}[/dim]"
            )
        console.print(
            f"[dim]budget: max_scenarios={m.budget.max_scenarios}, "
            f"allow_destructive={m.budget.allow_destructive}[/dim]"
        )

