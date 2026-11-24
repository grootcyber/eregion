"""The dossier's reads of the platform, in the catalogue's form (DOS4, #1138; `docs/design/dossier-isolation.md`
§3.2, §3.3, §3.6, §6, §7; the catalogue's form: `glorfindel/enquiry/catalog.py`).

Each read is a `catalog.Read`: its id, its sentence, its call (`query`: what is asked of ARM, its
parameters named), its parameters from `catalog.PARAMS` (each checked before it names an ARM path), its
window anchored on the signal's hour T (`lookback` before, `ahead` after), its source's declared latency,
its author, and what it says under each system (the platform says the same under both). `kind="arm"`:
run through the provider's adapter (`glorfindel/providers/azure/dossier_reads.py`), never a KQL query.

**Apart from `READS`** (Q8, 23/11: a read enters the catalogue measured): none of these is measured at the
bench yet (DH1, DH2, DH3, DH4, DH7), so the enquiry cannot ask for them — only the dossier reads them, for
the human. Each reads one VM — the registry's, never the line's — and never a detection attributed to
none (the decision of 23/11). Read only, under the Reader Imladris holds (`docs/design/dossier-isolation.md`
§6): no right is added.

The latencies are the documentation's order (a few minutes), not measures: DH1 (the activity log), DH2
(the vault's jobs), DH4 (the metrics), DH7 (the health). `outcome` reads them: an empty answer before its
latency has passed since the end of its window is `en_attente`, never `vide`.
"""
from __future__ import annotations

from datetime import timedelta
from types import MappingProxyType
from typing import Mapping

from glorfindel.enquiry.catalog import GUEST_PROVOCABLE, LINUX, PLATFORM, READS_HERE, WINDOWS, Read

ACTIVITY_LATENCY_S = 300      # DH1: the activity log delivers a VM's events « in a few minutes » (unmeasured)
JOBS_LATENCY_S = 300          # DH2
METRICS_LATENCY_S = 300       # DH4: the platform's metrics, « a few minutes »
HEALTH_LATENCY_S = 0          # DH7: a state read now, not a window
VIEW_LATENCY_S = 0            # the instance view: a state read now
RECURRENCE_DAYS = 10          # Q6 (12/11): the vault's jobs read over N days, for F3b (DOS5) as for F1a

_BOTH = MappingProxyType({LINUX: READS_HERE, WINDOWS: READS_HERE})

ACTIVITY = ("GET /subscriptions/<abonnement>/providers/Microsoft.Insights/eventtypes/management/values "
            "$filter=eventTimestamp ge T−30 min and le T+30 min and resourceUri eq {vm} ; puis resourceGroupName "
            "eq <groupe de {vm}>, filtrée sur les enfants de {vm} (ACTIVITY_PAGES pages au plus)")
JOBS = "backupJobs.list({vault}) filtrée sur {vm} (entity_friendly_name, container), de T − 10 j à T + 10 min"
VIEW = "GET {vm} ; GET {vm}/instanceView (extensions, maintenanceRedeployStatus, système d'exploitation)"
METRICS = ("GET {vm}/providers/Microsoft.Insights/metrics metricnames=OS Disk Write Bytes/sec,Data Disk Write "
           "Bytes/sec,Disk Write Bytes interval=PT1M aggregation=Average,Maximum timespan=T−5 min/T+3 min")
HEALTH = "GET {vm}/providers/Microsoft.ResourceHealth/availabilityStatuses/current"

PLATFORM_READS: Mapping[str, Read] = MappingProxyType({r.id: r for r in (
    Read("activity_window",
         "Le journal d'activité de la VM et de ses enfants autour du signal : extensions, démarrages, santé, et "
         "les gestes de Glorfindel, chacun avec sa durée par opération.",
         ACTIVITY, ("vm",), timedelta(minutes=30), ACTIVITY_LATENCY_S, PLATFORM, _BOTH, kind="arm",
         ahead=timedelta(minutes=30)),
    Read("backup_jobs",
         "Les jobs du coffre sur la VM, sur dix jours jusqu'à dix minutes après le signal.",
         JOBS, ("vm", "vault"), timedelta(days=RECURRENCE_DAYS), JOBS_LATENCY_S, PLATFORM, _BOTH, kind="arm",
         obj="vault", ahead=timedelta(minutes=10)),
    Read("instance_view",
         "La vue d'instance de la VM : l'état de ses extensions (écrit par son agent) et la maintenance planifiée ; "
         "son système, lu dans son modèle.",
         VIEW, ("vm",), timedelta(0), VIEW_LATENCY_S, GUEST_PROVOCABLE, _BOTH, kind="arm"),
    Read("host_metrics",
         "Les métriques d'écriture disque vues par l'hôte, à la minute, de cinq minutes avant le signal à trois "
         "minutes après.",
         METRICS, ("vm",), timedelta(minutes=5), METRICS_LATENCY_S, PLATFORM, _BOTH, kind="arm",
         ahead=timedelta(minutes=3)),
    Read("resource_health",
         "L'état de disponibilité de la VM selon Azure (Resource Health), au moment de la lecture.",
         HEALTH, ("vm",), timedelta(0), HEALTH_LATENCY_S, PLATFORM, _BOTH, kind="arm"),
)})
