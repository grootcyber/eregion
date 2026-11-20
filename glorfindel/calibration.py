"""The observation report by confidence (B4a, #991, part of #75): how often a decision given at a
confidence was judged right — what the autonomy gate's threshold (`GLORFINDEL_CONFIDENCE_THRESHOLD`)
can rest on —, and where the cards come from (docs/observation.md, « Par confiance et par provenance »).

Read from the cards alone: no call to the cloud, none to the model, nothing the model reads changed.

- The confidence a verdict judges is the card's `confidence` (`judged_confidence`): the one the card
  shows beside the reason and the explanation it was judged on — a material re-fire rewrites the
  three together, the first kept in `first_confidence`, which no console, bot or CLI shows.
- The bands (`BANDS`) are closed at their bottom, open at their top, the last closed at 1. 0 is no
  confidence: the first band holds what lies above it.
- A share is said on `FEW_JUDGED` judged cards or more; under that, « too few », never a percentage.
  A share is the part judged right among the judged (right, wrong, unsure): an `unsure` is not a
  card judged right — the side to err on when a gate is set from it.
- Above the threshold: the cards the gate would let through, `confidence >= threshold` as the gate
  compares (`agent._apply_confidence_gate`). A malformed threshold is infinite: none above it.
- The provenance (`provenance`): `bench` inside the bench's perimeter, `unknown` otherwise.
"""
from __future__ import annotations

import math
from datetime import datetime

from glorfindel.escalations import UNATTRIBUTED, VERDICTS, rule_of

# (label, bottom, top): closed at the bottom, open at the top — the last band closed at 1.
BANDS: tuple[tuple[str, float, float], ...] = (
    ("(0, 0.5)", 0.0, 0.5),
    ("[0.5, 0.7)", 0.5, 0.7),
    ("[0.7, 0.8)", 0.7, 0.8),
    ("[0.8, 0.9)", 0.8, 0.9),
    ("[0.9, 1]", 0.9, 1.0),
)
# Under this many judged cards, a share says nothing: « too few ».
FEW_JUDGED = 10
BENCH, UNKNOWN = "bench", "unknown"
PROVENANCES = (BENCH, UNKNOWN)
NO_RULE = "(sans règle)"


def gate_threshold() -> float:
    """The gate's threshold, resolved as the gate resolves it (`agent._confidence_threshold` reads
    this same function): GLORFINDEL_CONFIDENCE_THRESHOLD, 0.7 unset, infinite when malformed. The
    environment's of the process that reports — on Imladris, the watch's."""
    from glorfindel.config import confidence_threshold
    return confidence_threshold()


def _instant(value) -> datetime | None:
    """A time of the card that can be placed — read, and with a time zone; None otherwise (VP1c:
    never compared to one with a zone, never taken for UTC)."""
    try:
        at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo is not None else None


def judged_confidence(e: dict) -> float | None:
    """The confidence the card's verdict judged (its decision's, unjudged), or None when there is none.

    The card's `confidence`: written with the reason and the explanation it shows, and rewritten with
    them on a material re-fire (`escalations.record`). The operator judges what the card shows; its
    `first_confidence`, the first decision's, is shown by no console, bot or CLI.

    None:
    - not a number of (0, 1]: 0 is `record`'s default — a card written without a decision of the
      model (a failed cycle, a detection without a decision, an operator's gesture whose check
      failed) carries it, and so does a decision whose confidence was unreadable (`_parse_decision`);
      the console and the bot show no confidence there;
    - judged, then refreshed: a card that a re-fire rewrote (`first_confidence`) after its verdict, or
      without both times to tell (`verdict_at`, `updated_at`) — the confidence judged is no longer on
      the card. A verdict given in the console or on Discord acknowledges the card, which no re-fire
      rewrites again; `glorfindel verdict` leaves it pending."""
    c = e.get("confidence")
    if isinstance(c, bool) or not isinstance(c, (int, float)) or not 0.0 < c <= 1.0:   # nan fails too
        return None
    if e.get("verdict") in VERDICTS and "first_confidence" in e:
        judged_at, rewritten = _instant(e.get("verdict_at")), _instant(e.get("updated_at"))
        if judged_at is None or rewritten is None or rewritten > judged_at:
            return None
    return float(c)


def band_of(confidence: float) -> str:
    """The band of a confidence of (0, 1] (`judged_confidence`)."""
    for label, bottom, top in BANDS[:-1]:
        if bottom <= confidence < top:
            return label
    return BANDS[-1][0]


def provenance(e: dict, scope) -> str:
    """Where a card comes from, read from the card alone — no call.

    `bench`: what it is about lies inside the bench's perimeter, as the injectors' guard draws it
    (`eregion_core.inscription.Scope.check`: the subscription AZURE_SUBSCRIPTION_ID names, a resource
    group of Celebrimbor's, `rg-celebrimbor*`), read from its `resource_id` — bree, the VM of the
    pre-observation, which is not enrolled, included. The criteria before the autonomous mode do not
    count these cards (ROADMAP.md, « Critères avant le mode autonome »).

    `unknown`: everything else — outside the perimeter (the twin, production, any other park: a card
    does not carry its zone, and a VM of a real park is not enrolled, so its tags would not say it
    either), the subscription not named, or a card attributed to no VM (SLF1: its resource is the VM
    it is filed on, not what it is about)."""
    a = e.get("attribution")
    if isinstance(a, dict) and a.get("state") == UNATTRIBUTED:
        return UNKNOWN
    return BENCH if scope.check(str(e.get("resource_id") or "")).allowed else UNKNOWN


def _cell() -> dict:
    return {"right": 0, "wrong": 0, "unsure": 0, "unjudged": 0}


def _said(c: dict) -> dict:
    """A cell with its count of judged cards, and its share judged right — None, `too_few`, under
    FEW_JUDGED."""
    judged = c["right"] + c["wrong"] + c["unsure"]
    too_few = judged < FEW_JUDGED
    return {**c, "judged": judged, "too_few": too_few, "right_share": None if too_few else c["right"] / judged}


def tables(cards: list[dict], *, threshold: float, scope) -> dict:
    """The report's tables by confidence and by provenance, over `cards` — the decision cards the
    report counts (in its window, exercises left out)."""
    bands = {label: _cell() for label, _, _ in BANDS}
    unknown = _cell()
    by_rule: dict[str, dict[str, dict]] = {}
    above = _cell()
    where = {p: _cell() for p in PROVENANCES}
    for e in cards:
        v = e.get("verdict") if e.get("verdict") in VERDICTS else "unjudged"
        where[provenance(e, scope)][v] += 1
        c = judged_confidence(e)
        if c is None:
            unknown[v] += 1
            continue
        band = band_of(c)
        bands[band][v] += 1
        by_rule.setdefault(rule_of(e) or NO_RULE, {}).setdefault(band, _cell())[v] += 1
        if c >= threshold:                  # the gate's own comparison; an infinite threshold, never
            above[v] += 1
    return {
        "few_judged": FEW_JUDGED,
        "by_confidence": {label: _said(c) for label, c in bands.items()},
        "confidence_unknown": _said(unknown),
        "by_rule_confidence": {rule: {label: _said(rows[label]) for label, _, _ in BANDS if label in rows}
                               for rule, rows in by_rule.items()},
        # JSON has no infinity: a malformed threshold is said `null`, nothing above it.
        "above_threshold": {"threshold": threshold if math.isfinite(threshold) else None, **_said(above)},
        "by_provenance": {p: _said(c) for p, c in where.items()},
    }
