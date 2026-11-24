"""The predicates the code computes on the rows (ENQ5a, #1162; `docs/design/enquete-raisonnee.md` §2.3,
§6.3; the sheet: `glorfindel/enquiry/fiches/T1486.yaml`). **At the harness only**, like the loop that
reads them (`loop.PREDICATS`): no module of the product imports this one.

A predicate reads today's readings of its hypothesis, the signal's hour T and the moment it judges
(`now`); it says `confirme`, `infirme`, `en_attente` (what it needs is not ingested yet) or `inconnu`.
Never the model: where a hypothesis has a predicate, its verdict wins over the model's (§6.3, step 3).

**T1486-H1** — « a minute's mean past 25 MB/s on the volume of the detection », on `perf_minute_series`:
- a minute is *settled* when it is complete — as many samples as the series' own cadence (the most a
  minute of that volume holds: read from the data, like the rule's step) — and ingested: the table has
  ingested a sample after it (`Reading.ingere`, its `Horizon`, EH10), or, when the read does not tell,
  its end plus the declared latency of `Perf` has passed;
- **confirme**: a settled minute, on any volume, whose mean is ≥ 25;
- **infirme**: the minute of the first sample past the rule's threshold (`PremierPic`, 25 MB/s on one
  sample) and the next one, both settled, on **every** volume, each mean < 15 — the detected row does
  not name its volume (the rule's output: `MaxWrite` by VM), so every volume must say it; one minute
  never infirms (the attack of 09/11 passes the threshold at its second minute only: 18.4, then 59.4);
- **en_attente** while these minutes can still be ingested; **inconnu** after, or when the rows do not
  read (a row without its minute: nothing is taken from a series read in part).

**T1486-H2** — « a short peak at the start of a backup », on `perf_minute_series` and `vault_jobs`:
- **confirme**: H1 infirmed AND a `Backup` job of this VM started in [T0 − 5 min, T0], T0 the first
  sample past the threshold (`PremierPic`), the earliest of the volumes;
- **infirme**: H1 confirmed, OR the vault's jobs read whole (`vide`, or `lignes` once the end of the
  read's window plus its latency has passed) and none started in that interval;
- **inconnu** otherwise — never `en_attente`: the sheet says « sinon : inconnu ».
**Its known limit** (EH10): two settled minutes come 1 to 3 min after the first sample, plus the
ingestion of `Perf`, past T = 30 s: H1 and H2 are most often `en_attente` or `inconnu` when `decide`
runs, and settled afterwards, for the human (the card, ENQ5b). And « H1 infirmed » reads `Perf`, which
the guest writes: a ransomware bridled under 15 MB/s at the hour of the backup confirms H2 — it helps
the human, it never lifts a guard (§7.3).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Callable, Mapping

from glorfindel.enquiry import catalog

CONFIRME, INFIRME, INCONNU, EN_ATTENTE = "confirme", "infirme", "inconnu", "en_attente"
VERDICTS_DU_CODE = (CONFIRME, INFIRME, INCONNU, EN_ATTENTE)

SEUIL_CONFIRME = 25.0        # MB/s (10^6 B/s, the rule's unit): a settled minute's mean that confirms H1
SEUIL_INFIRME = 15.0         # MB/s: each of the two minutes under it infirms H1
SEUIL_PIC = 25.0             # MB/s: the rule's threshold on one sample (coarse sampling), `PremierPic` in the query
JOB_AVANT = timedelta(minutes=5)
MINUTE = timedelta(minutes=1)
SERIE, JOBS = "perf_minute_series", "vault_jobs"


@dataclass(frozen=True)
class Minute:
    volume: str
    debut: datetime
    echantillons: int
    moyenne: float
    premier_pic: datetime | None


def _nombre(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def minutes(reading: catalog.Reading) -> list[Minute] | None:
    """The minutes of the series, or None when one row does not read (its minute, its volume, its count
    or its mean): a series read in part says nothing."""
    out = []
    for row in reading.rows:
        if not isinstance(row, dict):
            return None
        debut, n, moyenne = catalog._when(row.get("Minute")), row.get("Echantillons"), _nombre(row.get("MoyenneMBs"))
        volume = row.get("InstanceName")
        if debut is None or not isinstance(volume, str) or isinstance(n, bool) or not isinstance(n, int) \
                or n < 1 or moyenne is None:
            return None
        out.append(Minute(volume, debut, n, moyenne, catalog._when(row.get("PremierPic"))))
    return out


class _Serie:
    """The series of one reading, judged at `now`: which minute is settled, and which can still be."""

    def __init__(self, reading: catalog.Reading, ms: list[Minute], now: datetime):
        self.par = {(m.volume, m.debut): m for m in ms}
        self.volumes = sorted({m.volume for m in ms})
        self.cadence = {v: max(m.echantillons for m in ms if m.volume == v) for v in self.volumes}
        self.horizon, self.now = catalog._when(reading.ingere), now

    def ingeree(self, debut: datetime) -> bool:
        """The table has ingested past this minute: a sample after it (the horizon), else its end plus the
        declared latency of `Perf`."""
        if self.horizon is not None:
            return self.horizon >= debut + MINUTE
        return self.now >= debut + MINUTE + timedelta(seconds=catalog.PERF_LATENCY_S)

    def reglee(self, m: Minute) -> bool:
        return m.echantillons >= self.cadence[m.volume] and self.ingeree(m.debut)


def h1(lectures: Mapping[str, catalog.Reading], at: datetime | None, now: datetime) -> str:
    """T1486-H1 (the module's docstring)."""
    lu = lectures.get(SERIE)
    if lu is not None and lu.etat == catalog.EN_ATTENTE:
        return EN_ATTENTE
    if lu is None or lu.etat != catalog.LIGNES or (ms := minutes(lu)) is None:
        return INCONNU
    s = _Serie(lu, ms, now)
    if any(s.reglee(m) and m.moyenne >= SEUIL_CONFIRME for m in ms):
        return CONFIRME
    pics = [m.premier_pic for m in ms if m.premier_pic is not None]
    if not pics:
        return INCONNU
    m1 = min(pics).replace(second=0, microsecond=0)
    attente = False
    for volume in s.volumes:
        for debut in (m1, m1 + MINUTE):
            m = s.par.get((volume, debut))
            if m is not None and s.reglee(m):
                if m.moyenne >= SEUIL_INFIRME:
                    return INCONNU
            elif not s.ingeree(debut):
                attente = True                   # it can still come, or still fill
            else:
                return INCONNU                   # past it, absent or incomplete: it will not be whole
    return EN_ATTENTE if attente else INFIRME


def _t0(lectures: Mapping[str, catalog.Reading]) -> datetime | None:
    lu = lectures.get(SERIE)
    ms = minutes(lu) if lu is not None and lu.etat == catalog.LIGNES else None
    pics = [m.premier_pic for m in ms or () if m.premier_pic is not None]
    return min(pics) if pics else None


def _entiers(lu: catalog.Reading | None, at: datetime | None, now: datetime) -> bool:
    """The vault's jobs read whole: an answer `vide`, or rows once the end of the read's window plus its
    latency has passed (a job just started may not be listed yet)."""
    if lu is None or at is None:
        return False
    if lu.etat == catalog.VIDE:
        return True
    read = catalog.READS[JOBS]
    return lu.etat == catalog.LIGNES and now >= catalog.window(read, at)[1] + timedelta(seconds=read.latency_s)


def h2(lectures: Mapping[str, catalog.Reading], at: datetime | None, now: datetime) -> str:
    """T1486-H2 (the module's docstring)."""
    v1 = h1(lectures, at, now)
    if v1 == CONFIRME:
        return INFIRME
    jobs, t0 = lectures.get(JOBS), _t0(lectures)
    partis = []
    if jobs is not None and jobs.etat == catalog.LIGNES and t0 is not None:
        for row in jobs.rows:
            start = catalog._when(row.get("start")) if isinstance(row, dict) else None
            if start is not None and str(row.get("operation", "")).strip().lower() == "backup" \
                    and t0 - JOB_AVANT <= start <= t0:
                partis.append(row)
    if t0 is not None and not partis and _entiers(jobs, at, now):
        return INFIRME
    if v1 == INFIRME and partis:
        return CONFIRME
    return INCONNU


PREDICATS: Mapping[str, Callable[[Mapping[str, catalog.Reading], datetime | None, datetime], str]] = \
    MappingProxyType({"T1486-H1": h1, "T1486-H2": h2})
