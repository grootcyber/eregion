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
  `glorfindel_version`, `{ref, revision, package}` (`eregion_core/version.py`); `rule_fingerprint`, the
  rule that detected and the first eight hex characters of the sha256 of its query, read from the rules
  as they stand on disk (`rule_ceiling.current()`, the rules the ceiling reads: the shipped base and the
  client's layer), by its name — a rule changes from one version to the next, the human must know which
  one fired.

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


def rule_fingerprint(signal: dict) -> dict:
    """{name, query_sha256}: the rule that detected — the RulePoller's names it; an attack_started
    resolved by the graph, the rule of its query or of its TTP (`RuleCeilings.for_signal`) — and the
    first eight hex characters of the sha256 of its query as the rules stand. A rule no longer there (or
    disabled): its name, no fingerprint. The rules unreadable: said."""
    name = str((signal.get("context") or {}).get("rule_name") or "")
    try:
        from glorfindel import own_channel, rule_ceiling
        rules = rule_ceiling.current()
        name, _ = rules.for_signal(signal)
        query = next((q for n, _ttp, q in rules.rules if n == name), "")
    except Exception as exc:
        return {"name": name, "query_sha256": "", "unreadable": _first_line(exc)}
    return {"name": name, "query_sha256": own_channel.query_sha256(query)[:FINGERPRINT_LEN] if query else ""}


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
    out["rule_fingerprint"] = rule_fingerprint(state.get("signal") or {})
    return out
