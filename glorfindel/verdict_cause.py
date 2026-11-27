"""VRD1 (#1285): a finer verdict — a « wrong » says why, when the operator says it (decision of Jonathan of
24/11, after the harness's session MEM-H).

Two causes of a « wrong »:
- **a false alarm** (``false_alarm``): nothing happened;
- **an action too strong** (``too_strong``): the signal was real, the gesture too strong.

**The form keeps the old one readable.** ``verdict`` stays the verdict (right, wrong, unsure,
glorfindel/escalations.py); the cause is a field of its own beside it (``verdict_cause``), optional: a
« wrong » given before VRD1, or without a cause (``glorfindel verdict … wrong`` without ``--cause``), carries
none and reads as it read before, everywhere — the report counts it « cause unsaid », the memory by keys
says MEM2b's text. A cause goes with « wrong » only.

**« Too strong » only after a gesture** (`gesture`): the card's action responded to a threat — isolate,
block, snapshot, restore… (``RESPONSES``, the same reading as the memory's, MEM2b). A card that made no
gesture (a detection for a human, a decision to do nothing) cannot have acted too strongly: the store
refuses the cause there (`checked`), whoever asks — the console, the bot, the command. On such a card the
console and the bot offer one « wrong », the false alarm: written as such, never inferred when reading.

**Read, never trusted** (`of`): a cause the store holds is said only when it is one of the two, on a
« wrong », and « too strong » only on a card that made a gesture — anything else (a line written by hand, a
card of before) reads as a « wrong » whose cause is unsaid, never as an error.
"""
from __future__ import annotations

from glorfindel.response.policy import AUTONOMOUS_ACTIONS, MODEL_GATED_ACTIONS

FIELD = "verdict_cause"
FALSE_ALARM = "false_alarm"
TOO_STRONG = "too_strong"
CAUSES = (FALSE_ALARM, TOO_STRONG)
UNSAID = "unsaid"
# The actions that respond to a threat — a gesture. MEM2b's reading (glorfindel/memory_keys.py): for them,
# « judged right » says a real attack; VRD1: only after one can an action be too strong.
RESPONSES = frozenset((AUTONOMOUS_ACTIONS - {"release_isolation"}) | MODEL_GATED_ACTIONS)
# What the surfaces say of a cause (ENG1a: the product's output is in English).
WORDS = {FALSE_ALARM: "false alarm", TOO_STRONG: "too strong"}


def gesture(action) -> bool:
    """The card's action responded to a threat: an action can have been too strong."""
    return isinstance(action, str) and action in RESPONSES


def checked(verdict: str, cause, action) -> str:
    """The cause to write with ``verdict`` on a card whose action is ``action`` — "" when none is given.
    ValueError: an unknown cause, a cause with a verdict other than « wrong », or « too strong » on a card
    that made no gesture."""
    cause = "" if cause is None else cause
    if not isinstance(cause, str):
        raise ValueError("cause must be a text")
    cause = cause.strip()
    if not cause:
        return ""
    if cause not in CAUSES:
        raise ValueError(f"cause must be one of {', '.join(CAUSES)}")
    if verdict != "wrong":
        raise ValueError("a cause goes with 'wrong' only")
    if cause == TOO_STRONG and not gesture(action):
        raise ValueError("'too_strong': the card made no gesture — on a detection without an action, "
                         "a wrong is a false alarm")
    return cause


def asked(body) -> tuple[str, str, str]:
    """What the console's request asks (`POST /api/escalations/<id>/verdict`): ``(verdict, note, cause)``,
    each a text — the cause "" when none is given, held by `checked` when the store writes it."""
    body = body if isinstance(body, dict) else {}
    cause = body.get("cause")
    return (str(body.get("verdict", "")), str(body.get("note", "")),
            cause if isinstance(cause, str) else "" if cause is None else str(cause))


def of(e: dict) -> str:
    """The cause a card carries, read again: one of `CAUSES` on a « wrong » — « too strong » only on a card
    that made a gesture —, else "" (none given, a card of before, a line written by hand)."""
    if not isinstance(e, dict) or e.get("verdict") != "wrong":
        return ""
    cause = e.get(FIELD)
    if cause == FALSE_ALARM or (cause == TOO_STRONG and gesture(e.get("action"))):
        return cause
    return ""


def said(e: dict) -> str:
    """The verdict as the surfaces say it: « wrong · false alarm », « wrong · too strong », else the verdict
    alone (« wrong » whose cause is unsaid, « right », « unsure »); "" when none."""
    verdict = e.get("verdict") if isinstance(e, dict) else None
    if not isinstance(verdict, str) or not verdict:
        return ""
    cause = of(e)
    return f"{verdict} · {WORDS[cause]}" if cause else verdict


def counts() -> dict:
    return {FALSE_ALARM: 0, TOO_STRONG: 0, UNSAID: 0}


def counts_said(c) -> str:
    """The « wrong » by their cause, as `glorfindel report` says them: « 2 false alarm · 1 too strong · 0
    cause unsaid ». A count it was not given reads 0."""
    c = c if isinstance(c, dict) else {}
    n = {k: v if type(v) is int and v >= 0 else 0 for k, v in ((k, c.get(k)) for k in (*CAUSES, UNSAID))}
    return f"{n[FALSE_ALARM]} false alarm · {n[TOO_STRONG]} too strong · {n[UNSAID]} cause unsaid"


def count(into: dict, e: dict) -> None:
    """A « wrong » card counted by its cause in ``into`` (`counts`); any other verdict, nothing."""
    if isinstance(e, dict) and e.get("verdict") == "wrong":
        into[of(e) or UNSAID] += 1
