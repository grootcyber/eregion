"""DOS2 (#1042; `docs/design/dossier-isolation.md` §3.7, F6): the decision as it was taken, noted on the
cycle's debug line — the model called, how its draws were sampled, the settings in force, the version
of Glorfindel that decided and the rule that detected.

What it writes (`decision_fields`, merged into the line by `agent._write_debug_record`):
- `decision_temperature` and `decision_draws`, as before (D-1: `scripts/llm_smoke.py` reads the first);
- once the model was called (`decision_model` in the state, set by `decide` even on a failed call):
  `decision_model`, the model's string; `decision_sampling`, the first draw's — the temperature asked,
  whether the model refused it, and what it then was (`fixed`, or `provider_default`: a model that
  refuses a temperature, claude-sonnet-5-5 the default, measured 26/10); `confirming_sampling`, the other
  draws' (D-1: asked with no temperature, always the provider's default — `decision_draws` says whether
  any was asked);
- on every line: `confidence_threshold` (null when GLORFINDEL_CONFIDENCE_THRESHOLD is malformed: every
  autonomous action held — no Infinity in a line the console serves as JSON) and
  `decision_draws_required` (0 when GLORFINDEL_DECISION_DRAWS is malformed), the settings as they stand
  at the cycle's end (the environment of the watch, read again — no line in the graph's state);
  `glorfindel_version`, `{ref, revision, package}` (`eregion_core/version.py`);
- on a detection: `rule_fingerprint`, the rule that detected and the first eight hex characters of the
  sha256 of the query that fired — the one the RulePoller of this process loaded (`note_polled`), never
  the rules on disk since; a polled `detection_query`; else the rules on disk (`rule_fingerprint`) — a
  rule changes from one version to the next, the human must know which one fired.

**Never in the memory.** The `cycle` that `store_cycle` writes to ChromaDB does not change: the memory
feeds `past_cycles`, so the message to the model — `tests/unit/test_cycle_line.py` freezes both, to the
byte. Nothing here reaches the signal either (`_build_user_message` dumps it). A field that cannot be
read never costs the line: it is a failed cycle's last trace too.
"""
from __future__ import annotations

import math

# The first draw of a decision is asked at temperature 0 (D-1): reproducible where the model accepts
# it (claude-sonnet-4-6, local models). claude-sonnet-5-5, the default, refuses any temperature but its
# own (measured 26/10): there the first draw is the provider's default sampling, and the cycle records it
# (decision_temperature: None). Read by `agent.decide` (`_DECISION_TEMPERATURE`) and said here.
DECISION_TEMPERATURE = 0.0
FIXED, PROVIDER_DEFAULT = "fixed", "provider_default"
FINGERPRINT_LEN = 8


def _first_line(exc: BaseException) -> str:
    return (str(exc).splitlines() or [type(exc).__name__])[0][:200]


def sampling(state: dict) -> dict:
    """The first draw's sampling: the temperature asked, whether the model refused it, what it was."""
    if "decision_temperature" in state:
        refused = state["decision_temperature"] is None
    else:                                 # a failed call: what this process learnt of the model
        from eregion_core.llm_call import temperature_refused
        refused = temperature_refused(str(state.get("decision_model") or ""))
    return {"requested_temperature": DECISION_TEMPERATURE, "refused": refused,
            "sampling": PROVIDER_DEFAULT if refused else FIXED}


# The confirming draws (D-1, `agent._confirming_draws`) ask no temperature: the variance the first
# draw's removes is the one they probe.
CONFIRMING_SAMPLING = {"requested_temperature": None, "refused": False, "sampling": PROVIDER_DEFAULT}


def settings() -> dict:
    """The threshold of the confidence gate and the draws required, as they stand."""
    from glorfindel.config import confidence_threshold, decision_draws
    threshold = confidence_threshold()
    return {"confidence_threshold": threshold if math.isfinite(threshold) else None,
            "decision_draws_required": decision_draws()}


def glorfindel_version() -> dict:
    """{ref, revision, package} of what this watch runs (`eregion_core/version.py`)."""
    try:
        from eregion_core.version import version
        v = version()
        return {k: str(v.get(k) or "") for k in ("ref", "revision", "package")}
    except Exception as exc:              # said, never the line lost
        return {"ref": "", "revision": "", "package": "", "unreadable": _first_line(exc)}


# The queries the RulePoller of this process runs, {rule: sha256 of its query}, as it loaded them at its
# creation (`note_polled`): the watch never reloads its rules (glorfindel/watch/rules.py) — after a
# `glorfindel approve` or an edited client layer, the rules on disk are no longer the ones that fire,
# until the restart. Never in the signal: the signal reaches the model (`_build_user_message`).
_POLLED: dict[str, str] = {}


def note_polled(rules) -> None:
    """The queries a RulePoller runs, by rule — called at its creation (`RulePoller.__init__`), with its
    own rules, the query as loaded (to the byte, as `detection_rules.shipped_query` hashes it)."""
    from glorfindel.own_channel import query_sha256
    for rule in rules:
        _POLLED[str(rule.name)] = query_sha256(rule.query)


def _short(sha: str) -> str:
    return sha[:FINGERPRINT_LEN]


def _dict(value) -> dict:
    """A part of the signal as a dict, or empty: a signal that is not what it should be (its raw_signal
    a list, OV1's review) never costs the line."""
    return value if isinstance(value, dict) else {}


def rule_fingerprint(signal: dict) -> dict | None:
    """{name, query_sha256, read}: the rule that detected and the first eight hex characters of the
    sha256 of the query that fired — None but on a detection (a `detection_timeout` names no rule).

    `read` says where the query was read: `poller`, the RulePoller of this process names its rule, and
    its query is the one it loaded (`note_polled`), whatever the disk says since; `detection_query`, an
    attack_started resolved by the graph or a `respond <file>` carries the query it polled — that one is
    hashed, the rule named when one of the rules on disk is identical to it; `rules_on_disk`, the rest (a
    rule named but polled by no poller of this process, a detection resolved by its TTP): the rules as
    they stand on disk (`rule_ceiling.current()`, the base and the client's layer). A rule no longer
    there (or disabled): its name, no fingerprint. The rules unreadable: said."""
    if signal.get("event") != "detection":
        return None
    from glorfindel import own_channel
    name = str(_dict(signal.get("context")).get("rule_name") or "")
    if name and name in _POLLED:
        return {"name": name, "query_sha256": _short(_POLLED[name]), "read": "poller"}
    polled = str(_dict(signal.get("raw_signal")).get("detection_query") or "")
    try:
        from glorfindel import rule_ceiling
        rules = rule_ceiling.current()
        name, _ = rules.for_signal(signal)
        query = next((q for n, _ttp, q in rules.rules if n == name), "")
    except Exception as exc:
        out = {"name": name, "query_sha256": "", "read": "rules_on_disk", "unreadable": _first_line(exc)}
        if polled:
            out.update(query_sha256=_short(own_channel.query_sha256(polled)), read="detection_query")
        return out
    if polled:
        return {"name": name, "query_sha256": _short(own_channel.query_sha256(polled)), "read": "detection_query"}
    return {"name": name, "query_sha256": _short(own_channel.query_sha256(query)) if query else "",
            "read": "rules_on_disk"}


def decision_fields(state: dict) -> dict:
    """What the debug line says of the decision (the module's docstring), never what the memory keeps."""
    out: dict = {}
    if "decision_temperature" in state:
        out["decision_temperature"] = state["decision_temperature"]
    if state.get("decision_draws"):
        out["decision_draws"] = state["decision_draws"]
    if state.get("decision_model"):
        out["decision_model"] = str(state["decision_model"])
        out["decision_sampling"] = sampling(state)
        out["confirming_sampling"] = dict(CONFIRMING_SAMPLING)
    try:
        out.update(settings())
    except Exception as exc:              # the settings never cost the line
        out.update(confidence_threshold=None, decision_draws_required=None,
                   settings_unreadable=_first_line(exc))
    out["glorfindel_version"] = glorfindel_version()
    try:
        fingerprint = rule_fingerprint(_dict(state.get("signal")))
    except Exception as exc:              # the fingerprint never costs the line
        fingerprint = {"name": "", "query_sha256": "", "unreadable": _first_line(exc)}
    if fingerprint is not None:
        out["rule_fingerprint"] = fingerprint
    return out
