"""What the watch should see when a scheduled drill plays (DRL1, docs/design/drill-banc.md §1.2):
``expectations/<drill>.yaml``, beside the drill but apart from it.

For each wire of the drill, at its rank and of its experiment: the rule of the shipped base that
should match, and how long after the wire's T0. Read on Imladris (VP1) and by the session « Banc »
(BRO1) — never on Orodruin: the injectors' image does not copy ``expectations/`` (annatar/Dockerfile),
and neither ``eregion_core/scheduled_drill.py`` nor ``eregion_core/exercise_runner.py`` imports this
reader (tests/unit/test_drill_expectations.py reads their imports). The request does not carry them,
nor the exercise window, nor the decision: Annatar stays blind to Glorfindel, Glorfindel to Annatar
(§8.1).

``read`` is the one way in, exact like the drill's (no field more, none of the wrong kind): its own
reader stands for a schema. A drill's fingerprint never covers them (decision 5): an expectation
changed is a PR reviewed, never a re-arming.

D1: the shared core — Imladris and the Banc session read it, neither importing the other.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from eregion_core.orodruin import CEILING_INJECTIONS, CEILING_RUN_S

FIELDS = ("drill", "wires")
WIRE_FIELDS = ("rank", "experiment", "rule", "within_s")
MAX_BYTES = 64 * 1024
_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,47}")
_EXPERIMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
# A rule's name as the shipped base writes them (glorfindel/rules/azure/detection_rules.yaml).
_RULE = re.compile(r"[a-z0-9][a-z0-9-]{0,99}")


class ExpectationsRefused(ValueError):
    """Expectations the one reader does not take: why, in a sentence."""


@dataclass(frozen=True)
class Expected:
    rank: int
    experiment: str
    rule: str
    within_s: int


@dataclass(frozen=True)
class Expectations:
    drill: str
    wires: tuple[Expected, ...]


def _exact(doc, fields: tuple[str, ...], what: str) -> None:
    if not isinstance(doc, dict):
        raise ExpectationsRefused(f"{what} is not a mapping")
    extra = sorted(str(k) for k in set(doc) - set(fields))
    if extra:
        raise ExpectationsRefused(f"{what} carries a field it never holds: {', '.join(extra)}")
    missing = [f for f in fields if f not in doc]
    if missing:
        raise ExpectationsRefused(f"{what} lacks {', '.join(missing)}")


def read(doc) -> Expectations:
    """The expectations, or ``ExpectationsRefused``: a drill's name, then 1 to CEILING_INJECTIONS
    wires, each exactly its rank (1, 2, … in order), its experiment, its rule and its delay in
    seconds (1 to CEILING_RUN_S, after the wire's T0)."""
    _exact(doc, FIELDS, "the expectations")
    if not isinstance(doc["drill"], str) or not _NAME.fullmatch(doc["drill"]):
        raise ExpectationsRefused("their drill is not a drill's name")
    wires = doc["wires"]
    if not isinstance(wires, list) or not 1 <= len(wires) <= CEILING_INJECTIONS:
        raise ExpectationsRefused(f"their wires are not a list of 1 to {CEILING_INJECTIONS}")
    out = []
    for i, w in enumerate(wires, 1):
        _exact(w, WIRE_FIELDS, f"expectation {i}")
        rank, e, rule, within = w["rank"], w["experiment"], w["rule"], w["within_s"]
        if isinstance(rank, bool) or rank != i:
            raise ExpectationsRefused(f"expectation {i}: its rank is not {i}")
        if not isinstance(e, str) or not _EXPERIMENT.fullmatch(e):
            raise ExpectationsRefused(f"expectation {i}: its experiment is not a catalogue id")
        if not isinstance(rule, str) or not _RULE.fullmatch(rule):
            raise ExpectationsRefused(f"expectation {i}: its rule is not a rule's name")
        if isinstance(within, bool) or not isinstance(within, int) or not 0 < within <= CEILING_RUN_S:
            raise ExpectationsRefused(f"expectation {i}: within_s is not 1 to {CEILING_RUN_S} s")
        out.append(Expected(rank, e, rule, within))
    return Expectations(doc["drill"], tuple(out))


def shipped_dir() -> Path:
    """``expectations/`` at the repository's root — in Glorfindel's image, never the injectors'."""
    return Path(__file__).resolve().parents[1] / "expectations"


def load_file(path: str | Path) -> Expectations:
    """One drill's expectations: read bounded, never through a link, named for their drill."""
    import stat

    import yaml
    path = Path(path)
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    except OSError as e:
        raise ExpectationsRefused(f"{path.name} unreadable: {e.strerror or e}") from None
    with os.fdopen(fd, "rb") as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise ExpectationsRefused(f"{path.name} is not a regular file")
        body = f.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ExpectationsRefused(f"{path.name} larger than {MAX_BYTES} bytes")
    try:
        doc = yaml.safe_load(body.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError, RecursionError):
        raise ExpectationsRefused(f"{path.name} is not YAML") from None
    exp = read(doc)
    if f"{exp.drill}.yaml" != path.name:
        raise ExpectationsRefused(f"{path.name} holds the expectations of {exp.drill!r}: their file is "
                                  "<the drill's name>.yaml")
    return exp
