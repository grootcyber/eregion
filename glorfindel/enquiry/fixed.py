"""Today's enquiry, the fixed routing of `investigate`, through the catalogue (ENQ2, #1064;
`docs/design/enquete-raisonnee.md` §1.1).

The reads are chosen on the detected row's columns, as before ENQ2 (`selection`): a disk write
(`MaxWrite`, `DiskWrite`) → who writes, a backup agent, a recent reboot; a brute force (`FailedAttempts`
and `SourceIP`) → a login that succeeded from that address; an escalation (`USER=root` and `COMMAND=`
in `SyslogMessage`) → what ran as root, the disk written. The choice still does not depend on the rule
(§1.1: what the loop of ENQ4 changes). Each value the code fills enters its query as a KQL literal,
checked for what it is (SEC4c); each query is scoped by the VM the registry names (SEC-I). The same
queries, in the same order, the same rows for the model (`Enquiry.context`), the same gaps for the
guard of `decide` (`Enquiry.gaps`, G2).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from glorfindel import kql
from glorfindel.enquiry import catalog


def run_query(workspace_id: str, query: str) -> list[dict] | None:
    """Run a single investigative query: its rows, or None when it FAILED (workspace
    unreachable, throttled, query refused).

    A failure used to come back as [] — "no rows": no backup agent writing, no reboot,
    no successful login. The model read an absence the telemetry never vouched for, and
    that absence argues for the disruptive action (G2). The model still sees [] (what it
    sees is unchanged); the failure is kept apart, for the telemetry guard of `decide`."""
    try:
        from glorfindel.detectors import detector_for
        det = detector_for("azure_monitor", workspace_id=workspace_id)
        return det.run_query(query.strip()) or []
    except Exception:
        return None


def selection(first_row: dict) -> list[str]:
    """Today's routing: the reads the detected row's columns call for, in their order."""
    reads: list[str] = []
    # ── Disk write anomaly → which process is writing? backup agent present? recent reboot?
    # Azure Backup OriginalLocation restore causes high I/O during boot rewrite.
    # A Heartbeat gap > 10min indicates a recent VM reboot — raises suspicion of
    # legitimate post-restore I/O rather than active ransomware encryption.
    if "MaxWrite" in first_row or "DiskWrite" in first_row:
        reads += ["top_write_processes", "backup_agent_check", "heartbeat_gap"]
    # ── Brute force → did any attempt succeed from this IP?
    if "FailedAttempts" in first_row and first_row.get("SourceIP", ""):
        reads.append("successful_auth_from_ip")
    # ── Privilege escalation → what ran as root after? disk writes?
    syslog_msg = str(first_row.get("SyslogMessage", ""))
    if "USER=root" in syslog_msg and "COMMAND=" in syslog_msg:
        reads += ["root_commands", "disk_write_after_escalation"]
    return reads


@dataclass
class Enquiry:
    """The readings of one enquiry, in their order, and the values the code refused (raw → why)."""
    readings: list[catalog.Reading] = field(default_factory=list)
    refused: dict[str, str] = field(default_factory=dict)

    @property
    def context(self) -> dict[str, list]:
        """`raw_signal.investigative_context`: what the model reads, each read's rows or `[]`."""
        return {r.id: r.seen for r in self.readings}

    @property
    def gaps(self) -> list[str]:
        """`telemetry_gaps`: the reads that failed or were not run — never shown to the model."""
        return [r.id for r in self.readings if r.gap]


_UNATTRIBUTED = "détection non attribuée : aucune VM du registre à interroger"


def enquire(first_row: dict, rid: str, workspace_id: str, *, unattributed: bool, system: str = "",
            at=None, now=None) -> Enquiry:
    """Run today's reads for this row on the VM `rid` names. `system`, `at` (the signal's hour) and `now`
    only shape the states of the readings (`catalog.outcome`); the watch passes none yet (ENQ4, ENQ5)."""
    out = Enquiry()

    # Each value enters its query as a KQL literal, checked for what it is (SEC4c): a host
    # name, an address — read from a log line, which anyone on the VM can shape. A value
    # that is not one: its queries are not run, and the enquiry says so (a gap, like a
    # failed query: the guard of `decide` holds a disruptive action).
    def value(check, raw_value) -> str | None:
        try:
            return kql.literal(check(raw_value))
        except kql.UnsafeValue as exc:
            out.refused.setdefault(str(raw_value)[:60], str(exc))
            return None

    # SEC-I (V-09): the queries are scoped by the VM the registry names — the signal's
    # resource id, never the line's `Computer` (root on any host of the workspace writes it). A
    # detection not attributed to a VM (its resource id an anchor, the line naming none) has no
    # VM to enquire on: its queries are not run — unknown, a gap, never another VM's rows.
    vm_lit = None if unattributed else value(kql.resource_id, rid)
    filled = {"vm": lambda: vm_lit,
              "ip": lambda: value(kql.ip, first_row.get("SourceIP", ""))}

    for read_id in selection(first_row):
        read = catalog.READS[read_id]
        values = {p: filled[p]() for p in read.params}
        if any(v is None for v in values.values()):
            why = _UNATTRIBUTED if unattributed and "vm" in read.params else "une valeur refusée (kql.literal)"
            out.readings.append(catalog.outcome(read, None, refused=why))   # not run: unknown
            continue
        rows = run_query(workspace_id, read.query.format(**values))       # None: failed, unknown (G2)
        out.readings.append(catalog.outcome(read, rows, system=system, at=at, now=now))
    return out


def console_lines(enquiry: Enquiry, vm: str, *, unattributed: bool) -> list[str]:
    """What the watch's console says of an enquiry: not run, refused, failed, or all empty."""
    from rich.markup import escape as _esc_markup

    gaps, lines = enquiry.gaps, []
    if unattributed:
        lines.append(
            "  [yellow]investigate: détection non attribuée à une VM — requête(s) d'enquête non "
            "lancée(s) (aucune VM du registre à interroger)[/yellow]"
        )
    if enquiry.refused:
        lines.append(
            "  [yellow]investigate: valeur refusée, requête(s) non lancée(s) — "
            + "; ".join(_esc_markup(why) for why in enquiry.refused.values())
            + " — aucune action disruptive autonome sur ce cycle[/yellow]"
        )
    if gaps:
        lines.append(
            f"  [yellow]investigate: {len(gaps)} requête(s) en échec pour '{_esc_markup(vm)}' "
            f"({', '.join(gaps)}) — télémétrie incomplète, aucune action disruptive "
            f"autonome sur ce cycle[/yellow]"
        )
    if all(len(v) == 0 for v in enquiry.context.values()) and not gaps:
        lines.append(
            f"  [dim]investigate: all queries empty for '{_esc_markup(vm)}' "
            f"— data not yet ingested (LAW latency ~60s, normal)[/dim]"
        )
    return lines
