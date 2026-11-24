"""PRT2 (#1160): the breaker in dollars — two envelopes, three buckets, the criticality in the config (the
maintainer's decisions of 23/11 and 24/11; docs/raisonnement.md §2.5, docs/operations.md, « Le budget du
modèle »).

PRT1's gate (glorfindel/decision_queue.py) bounds how many calls a minute; this bounds what they cost, a day
at a time (UTC). It never changes what PRT1 holds: it is judged before the gate takes a reserve, and the
gate's bounds stay whole behind it.

**Two envelopes, each with its general breaker**, both reset at midnight UTC:
- **the real**: `REAL_USD` a day (5 $, `GLORFINDEL_MODEL_REAL_USD_PER_DAY`);
- **the exercises** (Annatar, Gothmog, the drill): `EXERCISE_USD` a day for all of them (5 $,
  `GLORFINDEL_MODEL_EXERCISE_USD_PER_DAY`), and `CAMPAIGN_USD` for one campaign — one exercise's run (2 $,
  `GLORFINDEL_MODEL_EXERCISE_USD_PER_CAMPAIGN`). Exhausted, the exercise is paused — a card, no call —,
  never the real. Annatar's planner stays out of the gate: its own process, no guard.

**The envelope by the source of the event** (`_cycle_source`, B2): an exercise only when an injector's
window covers the VM *and* the VM's zone, as the watch reads it, is `bench` or `twin`. Anything else is the
real: a brute force from the Internet on a bench VM outside a window, a source unknown, a zone unread — and
in zone `production`, a source « exercise » is never believed. The real never waits on an exercise.

**Three buckets.**
- **The graves** (`call_class` critical or grave: a compromise, a technique of `GRAVE_TTPS`, the release
  after a restore): a reserve (`reserve`) the ordinaries never take — a floor of `GRAVE_FLOOR_USD` (1 $), and
  `CRITICAL_USD` (0.50 $) more per critical object — an entry of `autonomy.assets` that says
  `critical: true` (glorfindel/config.py) —, up to `RESERVE_MAX_USD` (2.50 $; the maintainer's decision of
  24/11). A grave draws on the whole envelope, the reserve included — on a critical object always: it never
  waits for money; only the general breaker sends it to the code's path, at once.
- **The ordinaries**: each VM at most `VM_USD` a day (1 $, `GLORFINDEL_MODEL_VM_USD_PER_DAY`); together, what
  the reserve leaves (`real/rest`).
- **The exercises**: their own envelope.

**The count.** Each call at its real cost — LiteLLM's price for its tokens (`litellm.completion_cost`, as
HRN1's meter). Checked before each call (`before`, the guard of eregion_core/llm_call.py): a call refused is
never made (`Refused`). A cost unknown (a model LiteLLM cannot price, a call that failed) is charged
`UNKNOWN_USD` (0.05 $: about five calls as measured on 24/11, `GLORFINDEL_MODEL_UNKNOWN_CALL_USD`, never
0) — a possible overrun, never 0; a call the provider refused for its limit (a 429) is charged 0: it was not
served.

**The overrun is bounded by the share of a decision admitted.** A decision is admitted (`judge`) only when
its share — the calls it may make (`DecisionGate.share`), each priced `UNKNOWN_USD` — fits in every bucket it
draws on, beside the shares of the decisions in flight. Admitted, its share's calls pass whatever the count;
beyond its share, a call passes only when one more at `UNKNOWN_USD` fits. A call outside any decision (none
today) is the real's, and checked the same way.

**It survives the watch's restart**: `~/.glorfindel/model_budget.json` (docs/fichiers-cles.md), written after
each call; a file of another day is a new day, from zero. Unreadable: from zero, said.

**Exhausted.** A grave goes the code's path (`code_decision`: what a refused call already had — the snapshot,
under the VM's mode and the attribution's guard, SEC4a's card beside it; B3a's floor proposing the
isolation; the release after a restore left to a human); an ordinary becomes a card; an exercise, a card that
says the pause. An alert — a card `model_budget_tripped` — says a breaker tripped, once a day for each.

**The provider's limits** (a 429, a quota, a credit spent): after LiteLLM's own retries, the decision goes the
code's path instead of failing its cycle, and the breaker slows: for a cool-down (`COOLDOWN_S`, doubled at each
limit again, at most `COOLDOWN_MAX_S`) a grave waits in its queue (a grave on a critical object never: the
code's path), an ordinary or an exercise is a card; limited again, a grave goes the code's path at once. A call
that succeeds ends the episode; one alert an episode.

**The hard ceiling is at the provider's**: Eregion counts, only the provider guarantees (docs/operations.md: a
monthly spending limit on the key's workspace, in the Anthropic console — the operator's gesture).
"""
from __future__ import annotations

import contextvars
import json
import logging
import math
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

log = logging.getLogger(__name__)

REAL, EXERCISE = "real", "exercise"
REAL_USD = 5.0
EXERCISE_USD = 5.0
CAMPAIGN_USD = 2.0
VM_USD = 1.0
UNKNOWN_USD = 0.05
# The graves' reserve (the maintainer's decision of 24/11): a floor of 1 $ the ordinaries never take, and
# 0.50 $ more per critical object — about ten decisions with an enquiry (0.051 $ measured on 24/11) —, up to
# 2.50 $: reserve = min(2.50 $, 1 $ + 0.50 $ × critical objects), never more than the real itself.
GRAVE_FLOOR_USD = 1.0
CRITICAL_USD = 0.50
RESERVE_MAX_USD = 2.50
COOLDOWN_S = 30.0
COOLDOWN_MAX_S = 300.0
VERSION = 1
TYPE = "model_budget_tripped"
_ZONES = ("bench", "twin")
_ENV = {"real": "GLORFINDEL_MODEL_REAL_USD_PER_DAY", "exercise": "GLORFINDEL_MODEL_EXERCISE_USD_PER_DAY",
        "campaign": "GLORFINDEL_MODEL_EXERCISE_USD_PER_CAMPAIGN", "vm": "GLORFINDEL_MODEL_VM_USD_PER_DAY",
        "unknown": "GLORFINDEL_MODEL_UNKNOWN_CALL_USD"}
_LIMIT_WORDS = ("rate limit", "rate_limit", "ratelimit", "quota", "credit balance", "usage limit", "spend limit")


class Refused(Exception):
    """A call to the model the budget refused (PRT2): never made."""


def provider_limited(exc) -> bool:
    """The provider refused for its limit: a 429, a quota, a credit spent — what slows the breaker."""
    if exc is None or isinstance(exc, Refused):
        return False
    if getattr(exc, "status_code", None) == 429 or type(exc).__name__ == "RateLimitError":
        return True
    msg = str(exc).lower()
    return any(w in msg for w in _LIMIT_WORDS)


def refused(exc) -> bool:
    """`decide`'s question on a call that raised: refused by the budget, or — under the watch's guard only —
    by the provider's limit: the code's path, never a failed cycle. Without the guard (the harness, `glorfindel
    respond` by hand), a limit stays a failed cycle: the harness counts it as no valid decision."""
    from eregion_core import llm_call
    return isinstance(exc, Refused) or (llm_call._GUARD is not None and provider_limited(exc))


def _usd(name: str, default: float, *, positive: bool = False) -> float:
    """A variable of dollars: unset, malformed, negative or infinite → the default; 0 is a budget of
    nothing (every call refused) — never for the price of an unknown call (`positive`)."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        return default
    return value


def _used(response) -> bool:
    """The response says what it read: a `usage` with tokens in (as HRN1's meter) — else its cost is unknown."""
    if response is None:
        return False
    usage = response.get("usage") if isinstance(response, dict) else getattr(response, "usage", None)
    inp = usage.get("prompt_tokens") if isinstance(usage, dict) else getattr(usage, "prompt_tokens", None)
    return isinstance(inp, int) and not isinstance(inp, bool) and inp > 0


def price(litellm, response, model: str) -> float | None:
    """What LiteLLM prices this call, in dollars; None when it cannot — an unknown cost, never 0."""
    try:
        cost = litellm.completion_cost(completion_response=response, model=model)
    except Exception:
        return None
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
        return None
    return float(cost)


def _default_path():
    from glorfindel import actions
    return actions._ISOLATION_STATE_DIR.parent / "model_budget.json"


def _default_source(data: dict) -> tuple[str, str]:
    from glorfindel.agent import _cycle_source
    return _cycle_source(data)


def _default_zone(resource_id: str) -> str:
    from eregion_core.exercise import zone_of
    return zone_of(resource_id)


def _default_autonomy():
    """The config's autonomy, read fresh (the console's changes taken at the next decision); unreadable:
    None — no object critical, no reserve."""
    try:
        from glorfindel.config import load_glorfindel_config
        return load_glorfindel_config().autonomy
    except Exception:
        return None


@dataclass(eq=False)
class _Decision:
    """One decision's draw on the budget: its buckets, its share left, its calls in flight."""
    keys: tuple
    share: int
    envelope: str
    refused: str = ""           # the code's path: every call refused, with this reason
    calls: int = 0


@dataclass
class Verdict:
    """`judge`'s word: `model` (admitted, its `decision`), `code` (a grave, the code's path), `card` (its
    kind for the card, `card`), `wait` (a grave, the provider's cool-down: `wait_s`)."""
    kind: str
    why: str = ""
    card: str = ""
    wait_s: float = 0.0
    decision: _Decision | None = None


_CURRENT: contextvars.ContextVar = contextvars.ContextVar("glorfindel_model_budget", default=None)


def _counted(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0


def _vm(data: dict) -> str:
    return str(data.get("resource_id") or "").rstrip("/").rsplit("/", 1)[-1].lower() or "?"


class Ledger:
    """The watch's breaker in dollars (module docstring): one for the watch, the guard of its calls."""

    def __init__(self, path=None, *, clock=time.time, source=None, zone=None, autonomy=None,
                 dry_run: bool = False) -> None:
        self._path = path
        self._clock = clock
        self._source = source or _default_source
        self._zone = zone or _default_zone
        self._autonomy = autonomy or _default_autonomy
        self.dry_run = dry_run
        self.real_usd = _usd(_ENV["real"], REAL_USD)
        self.exercise_usd = _usd(_ENV["exercise"], EXERCISE_USD)
        self.campaign_usd = _usd(_ENV["campaign"], CAMPAIGN_USD)
        self.vm_usd = _usd(_ENV["vm"], VM_USD)
        self.unknown_usd = _usd(_ENV["unknown"], UNKNOWN_USD, positive=True)
        self._lock = threading.Lock()
        self._flight: set[_Decision] = set()
        # A call outside any decision: the real's, checked call by call (no share).
        self._loose = _Decision(keys=("real",), share=0, envelope=REAL)
        self._flight.add(self._loose)
        self._critical_count = 0
        self._strikes = 0
        self._until = 0.0
        self._limit_said = False
        self.note = ""
        self._state = self._load()
        if self.note:                   # a count that could not be read: a card, once, beside the log
            self._emit([("count", self.note)])

    # ── the file ──────────────────────────────────────────────────────────────────────────────────

    @property
    def path(self):
        return self._path if self._path is not None else _default_path()

    def _today(self) -> str:
        return datetime.fromtimestamp(self._clock(), timezone.utc).date().isoformat()

    def _fresh(self) -> dict:
        return {"version": VERSION, "day": self._today(), "spent": {}, "calls": {}, "unknown": {}, "tripped": {}}

    def _load(self) -> dict:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return self._fresh()
        except (OSError, ValueError) as exc:
            self.note = f"compte du budget du modèle illisible ({type(exc).__name__}) : compté depuis zéro"
            log.warning("model budget: %s", self.note)
            return self._fresh()
        ok = (isinstance(raw, dict) and raw.get("version") == VERSION
              and all(isinstance(raw.get(k), dict) for k in ("spent", "calls", "unknown", "tripped")))
        if not ok:
            self.note = "compte du budget du modèle d'une autre forme : compté depuis zéro"
            log.warning("model budget: %s", self.note)
            return self._fresh()
        if raw.get("day") != self._today():
            return self._fresh()
        if not all(_counted(v) for k in ("spent", "calls", "unknown") for v in raw[k].values()):
            self.note = "compte du budget du modèle avec une valeur illisible : compté depuis zéro"
            log.warning("model budget: %s", self.note)
            return self._fresh()
        return {**raw, "spent": {k: float(v) for k, v in raw["spent"].items()}}

    def _save(self) -> None:
        """Under the lock: the day's count, written at once (never half a file)."""
        try:
            from glorfindel import actions
            self.path.parent.mkdir(parents=True, exist_ok=True)
            actions._atomic_write_text(self.path, json.dumps(self._state, sort_keys=True))
        except Exception as exc:         # counted in memory all the same; said
            log.warning("model budget: count not written (%s)", exc)

    def _roll(self) -> None:
        """Under the lock: midnight UTC passed — a new day, from zero (its breakers rearmed)."""
        if self._state.get("day") != self._today():
            self._state = self._fresh()

    # ── the buckets ───────────────────────────────────────────────────────────────────────────────

    def reserve(self) -> float:
        """The graves' reserve, which the ordinaries never take: `GRAVE_FLOOR_USD`, and `CRITICAL_USD` more per
        critical object, at most `RESERVE_MAX_USD` — never more than the real itself."""
        return min(self.real_usd, RESERVE_MAX_USD, GRAVE_FLOOR_USD + self._critical_count * CRITICAL_USD)

    def _limit(self, key: str) -> float | None:
        if key == "real":
            return self.real_usd
        if key == "real/rest":                 # the ordinaries': what the graves' reserve leaves
            return self.real_usd - self.reserve()
        if key.startswith("real/vm/"):
            return self.vm_usd
        if key == "exercise":
            return self.exercise_usd
        if key.startswith("exercise/run/"):
            return self.campaign_usd
        return None                     # real/grave, real/critical: counted, bounded by the real alone

    @staticmethod
    def _keys(envelope: str, grave: bool, critical: bool, vm: str, campaign: str) -> tuple:
        if envelope == EXERCISE:
            return ("exercise", f"exercise/run/{campaign or '?'}")
        if grave and critical:
            return ("real", "real/critical")
        if grave:
            return ("real", "real/grave")
        return ("real", "real/rest", f"real/vm/{vm}")

    def _pending(self, key: str) -> float:
        return sum((d.share + d.calls) * self.unknown_usd for d in self._flight if key in d.keys)

    def _refusal(self, keys: tuple, calls: int) -> tuple[str, str] | None:
        """Under the lock: the first bucket these calls (at `UNKNOWN_USD` each) do not fit in, beside what
        is spent today and the shares in flight — (its key, why), or None."""
        for key in keys:
            limit = self._limit(key)
            if limit is None:
                continue
            spent = self._state["spent"].get(key, 0.0)
            pending = self._pending(key)
            if spent + pending + calls * self.unknown_usd > limit + 1e-9:
                return key, (f"{_word(key)} : {spent:.2f} $ comptés aujourd'hui (UTC), {pending:.2f} $ "
                             f"réservés par les décisions en cours, au plus {max(0.0, limit):.2f} $")
        return None

    def _envelope(self, data: dict) -> tuple[str, str]:
        """(envelope, campaign): an exercise only when its window covers the VM and the zone read is the
        bench's or the twin's — in production, unread, unknown: the real."""
        try:
            source, run = self._source(data)
        except Exception:
            return REAL, ""
        if source != EXERCISE:
            return REAL, ""
        try:
            zone = self._zone(str(data.get("resource_id") or ""))
        except Exception:
            zone = ""
        if zone not in _ZONES:
            return REAL, ""
        return EXERCISE, run

    # ── the decision ──────────────────────────────────────────────────────────────────────────────

    def judge(self, data: dict, share: int) -> Verdict:
        """Before the gate takes a reserve: may this decision call the model, and on which buckets."""
        from glorfindel.decision_queue import LOW, call_class
        envelope, campaign = self._envelope(data)
        grave = call_class(data) != LOW
        vm = _vm(data)
        autonomy = self._autonomy()
        try:
            critical = bool(envelope == REAL and grave and autonomy is not None and autonomy.is_critical(vm))
            count = autonomy.critical_count() if autonomy is not None else 0
        except Exception:
            critical, count = False, 0
        keys = self._keys(envelope, grave, critical, vm, campaign)
        alerts: list = []
        with self._lock:
            self._critical_count = count
            self._roll()
            now = self._clock()
            if self._until > now:
                verdict = self._slowed(envelope, grave, critical, keys, now)
            else:
                hit = self._refusal(keys, max(1, int(share)))
                if hit is None:
                    decision = _Decision(keys=keys, share=max(1, int(share)), envelope=envelope)
                    self._flight.add(decision)
                    return Verdict("model", decision=decision)
                alerts = self._trip(*hit)
                verdict = self._exhausted(envelope, grave, keys, hit[1])
        self._emit(alerts)
        return verdict

    def _slowed(self, envelope: str, grave: bool, critical: bool, keys: tuple, now: float) -> Verdict:
        why = (f"limite du fournisseur du modèle atteinte ({self._strikes} fois de suite) : la watch ralentit "
               f"encore {int(self._until - now) + 1} s")
        if envelope == EXERCISE or not grave:
            return Verdict("card", why=why, card="provider_limit")
        if critical or self._strikes >= 2:
            return Verdict("code", why=why, decision=_Decision(keys=keys, share=0, envelope=envelope, refused=why))
        return Verdict("wait", why=why, wait_s=max(0.1, self._until - now))

    @staticmethod
    def _exhausted(envelope: str, grave: bool, keys: tuple, why: str) -> Verdict:
        if envelope == EXERCISE:
            return Verdict("card", why=f"exercice en pause, {why}", card="exercise_budget")
        if grave:
            said = f"budget du modèle épuisé, {why}"
            return Verdict("code", why=said, decision=_Decision(keys=keys, share=0, envelope=envelope, refused=said))
        return Verdict("card", why=f"budget du modèle épuisé, {why}", card="budget")

    def bound(self, verdict: Verdict, respond):
        """`respond` with this decision's draw on the budget while it runs; given back at its end."""
        def run(data):
            token = _CURRENT.set(verdict.decision)
            try:
                return respond(data)
            finally:
                _CURRENT.reset(token)
                self.done(verdict)
        return run

    def done(self, verdict: Verdict) -> None:
        """The decision ended, or was never admitted: its share given back."""
        if verdict.decision is not None:
            with self._lock:
                self._flight.discard(verdict.decision)

    # ── each call (the guard of eregion_core/llm_call.py) ─────────────────────────────────────────

    def before(self, model: str):
        """Before each call: refused (`Refused`, never made) on the code's path, or beyond the decision's
        share when one more call at `UNKNOWN_USD` does not fit."""
        decision = _CURRENT.get() or self._loose
        alerts: list = []
        why = ""
        with self._lock:
            self._roll()
            if decision.refused:
                why = decision.refused
            elif decision.share > 0:
                decision.share -= 1
            else:
                hit = self._refusal(decision.keys, 1)
                if hit is not None:
                    alerts = self._trip(*hit)
                    why = f"budget du modèle épuisé, {hit[1]}"
            if not why:
                decision.calls += 1
        self._emit(alerts)
        if why:
            raise Refused(why)
        return decision, model

    def after(self, token, litellm, response, exc) -> None:
        """Once the call returned or failed: counted at its price (unknown: `UNKNOWN_USD`; the provider's
        limit: 0), the day's file written. Never raises."""
        try:
            decision, model = token
            limited = provider_limited(exc)
            cost = 0.0 if limited else (price(litellm, response, model) if _used(response) else None)
            charged = self.unknown_usd if cost is None else cost
            alerts: list = []
            with self._lock:
                self._roll()
                decision.calls = max(0, decision.calls - 1)
                state = self._state
                for key in decision.keys:
                    state["spent"][key] = state["spent"].get(key, 0.0) + charged
                    state["calls"][key] = state["calls"].get(key, 0) + 1
                    if cost is None:
                        state["unknown"][key] = state["unknown"].get(key, 0) + 1
                alerts += self._limited(limited, exc)
                for key in decision.keys:        # the widest bucket reached first: one alert, not two
                    limit = self._limit(key)
                    if limit is not None and state["spent"].get(key, 0.0) >= limit:
                        alerts += self._trip(key, f"{_word(key)} : {state['spent'][key]:.2f} $ comptés "
                                                  f"aujourd'hui (UTC), au plus {max(0.0, limit):.2f} $")
                        break
                self._save()
            self._emit(alerts)
        except Exception as e:           # the count never breaks a call
            log.warning("model budget: call not counted (%s)", e)

    def _limited(self, limited: bool, exc) -> list:
        """Under the lock: the provider's limit slows the breaker; a call served ends the episode."""
        if limited:
            self._strikes += 1
            self._until = self._clock() + min(COOLDOWN_S * 2 ** (self._strikes - 1), COOLDOWN_MAX_S)
            if not self._limit_said:
                self._limit_said = True
                return [("provider", f"limite du fournisseur du modèle atteinte ({str(exc)[:200]})")]
        elif exc is None:
            self._strikes, self._until, self._limit_said = 0, 0.0, False
        return []

    # ── the alert ─────────────────────────────────────────────────────────────────────────────────

    def _trip(self, key: str, why: str) -> list:
        """Under the lock: a breaker tripped — said once a day (the file keeps it across a restart)."""
        if key in self._state["tripped"]:
            return []
        self._state["tripped"][key] = datetime.fromtimestamp(self._clock(), timezone.utc).isoformat()
        self._save()
        return [(key, why)]

    def _emit(self, alerts: list) -> None:
        """Outside the lock: each breaker tripped, a card `model_budget_tripped` (none in dry-run)."""
        day = self._state.get("day") or self._today()
        for key, why in alerts:
            reason = _alert_reason(key, why, day)
            log.warning("model budget: %s", reason)
            if self.dry_run:
                continue
            try:
                from glorfindel import escalations
                escalations.record(
                    signal_id=f"model-budget-{day}-{key}" if key != "provider"
                    else f"model-provider-limit-{int(self._clock())}",
                    resource_id="", action="", escalation_type=TYPE, reason=reason,
                    suggested_steps=list(_ALERT_STEPS))
            except Exception as exc:
                log.warning("model budget: alert not recorded (%s)", exc)

    def said(self) -> str:
        """One line for the watch's start: the two envelopes, what is spent today, the reserve."""
        with self._lock:
            self._roll()
            spent = self._state["spent"]
            return (f"budget du modèle : réel {spent.get('real', 0.0):.2f} / {self.real_usd:.2f} $ aujourd'hui "
                    f"(UTC ; réserve des graves {self.reserve():.2f} $, {self.vm_usd:.2f} $ par VM), exercices "
                    f"{spent.get('exercise', 0.0):.2f} / {self.exercise_usd:.2f} $ "
                    f"({self.campaign_usd:.2f} $ par campagne) — le plafond dur est chez le fournisseur"
                    + (f" ; {self.note}" if self.note else ""))


def _word(key: str) -> str:
    if key == "real":
        return "le budget du réel"
    if key == "real/rest":
        return "la part des ordinaires (le réel hors de la réserve des graves)"
    if key.startswith("real/vm/"):
        return f"la part de la VM {key[len('real/vm/'):]}"
    if key == "exercise":
        return "le budget des exercices"
    if key.startswith("exercise/run/"):
        return f"le budget de la campagne {key[len('exercise/run/'):]}"
    return key


def _alert_reason(key: str, why: str, day: str) -> str:
    """The alert's text, by the kind of bucket that tripped: what stops, what goes on."""
    if key == "count":
        return (f"Compte du budget du modèle, le {day} (UTC) : {why}. Ce qui était dépensé aujourd'hui n'est "
                "plus compté : le plafond dur reste chez le fournisseur.")
    if key.startswith("real/vm/"):
        return (f"Disjoncteur du modèle sauté le {day} (UTC) : {why}. Jusqu'à minuit UTC, les détections "
                "ordinaires de cette VM deviennent des cartes ; les autres VM et les graves continuent.")
    if key == "real/rest":
        return (f"Disjoncteur du modèle sauté le {day} (UTC) : {why}. Jusqu'à minuit UTC, une détection "
                "ordinaire devient une carte ; les graves gardent leur réserve.")
    if key.startswith("exercise/run/"):
        return (f"Disjoncteur du modèle sauté le {day} (UTC) : {why}. Cette campagne est en pause jusqu'à "
                "minuit UTC (une carte, aucun appel) ; les autres exercices et le réel continuent.")
    if key == "provider":
        return (f"Disjoncteur du modèle, le {day} (UTC) : {why}. La watch ralentit ; une détection grave passe par le chemin "
                "du code (instantané, carte), une ordinaire devient une carte, jusqu'à ce qu'un appel passe.")
    if key.startswith("exercise"):
        return (f"Disjoncteur du modèle sauté le {day} (UTC) : {why}. Les exercices sont en pause jusqu'à minuit UTC (une "
                "carte, aucun appel) ; le réel continue.")
    return (f"Disjoncteur du modèle sauté le {day} (UTC) : {why}. Jusqu'à minuit UTC, une détection grave passe par le "
            "chemin du code (l'instantané sous le mode de la VM, une carte), une ordinaire devient une carte.")


_ALERT_STEPS = (
    "Lire les cartes undecided_detection et uncontained_detection du jour : le modèle ne les a pas vues.",
    "Relever le budget si c'est voulu : GLORFINDEL_MODEL_REAL_USD_PER_DAY (ou celui des exercices), puis "
    "redémarrer la watch (docs/operations.md, « Le budget du modèle »).",
    "Le plafond dur reste chez le fournisseur : la limite de dépense mensuelle de l'espace de travail de la clé.",
)


def install(ledger: Ledger | None):
    """The ledger as the guard of every call of this process (eregion_core/llm_call.py); the previous one
    returned."""
    from eregion_core import llm_call
    return llm_call.set_guard(ledger)


# ── the code's path ───────────────────────────────────────────────────────────────────────────────────

_CODE_STEPS = (
    "Juger la détection : le modèle ne l'a pas vue (budget du jour épuisé, ou limite du fournisseur).",
    "Isoler la VM ou bloquer la source à la main si la détection le demande : le code ne fait seul que "
    "l'instantané, sous le mode de la VM.",
)


def code_decision(state: dict, exc: BaseException, mode: str, gate: dict, model: str) -> dict:
    """`decide`'s decision when its call is refused (PRT2: the budget, or the provider's limit) — the code's
    path, no call: what a refused call already had. For a grave one, a snapshot, as the model's would be
    judged: the attribution's guard (never on a VM the detection does not name), the VM's mode (human_only:
    proposed on its card); run alone, SEC4a's card beside it says nothing is contained (`_contained_now`: a VM
    already contained has none). B3a's floor proposes the isolation where its pair is confirmed — never runs
    it. The release after a restore: its precondition read (what a restored disk may replay, an origin not
    vouched for), then a card — the VM stays isolated until a human approves it. An ordinary one (a limit of
    the provider on its call): no action, a card. `decision_model` set only when the provider was reached
    (its limit): the gate counts that call."""
    from glorfindel import agent
    from glorfindel.decision_queue import LOW, call_class
    signal = state["signal"]
    limited = provider_limited(exc)
    said = (f"limite du fournisseur du modèle ({agent._first_line(exc)[:200]})" if limited else str(exc)[:400])
    lead = f"Décision du code, sans appel au modèle (PRT2) — {said}."
    release = signal.get("event") == "recovery_complete"
    ordinary = not release and call_class(signal) == LOW
    d = {"action": "release_isolation" if release else "" if ordinary else "snapshot", "confidence": 0.0,
         "reversible": True, "escalate": False, "reasoning": lead, "explanation": lead, "escalation_reason": "",
         "suggested_steps": list(_CODE_STEPS)}
    if release:
        agent._apply_release_precondition(d, signal)        # its warnings on the card
        d["escalate"] = True
        d["escalation_reason"] = " ".join(filter(None, (
            lead, d["escalation_reason"], "La levée de l'isolation après le restore reste à un humain : la VM "
            "reste isolée jusqu'à son approbation.")))
    elif ordinary:
        d["escalate"], d["held_by"] = True, "model_budget"
        d["escalation_reason"] = f"{lead} Détection ordinaire : aucune action, triage humain."
    agent._apply_attribution_guard(d, signal)
    mode_hold = agent._apply_autonomy_mode(d, mode, gate)
    if mode_hold:
        d["escalation_reason"] = f"{lead} {d['escalation_reason']}"
    floor = "" if release or ordinary else agent._root_compromise_floor(d, signal, state.get("incident"))
    if floor and d["escalate"]:
        d["escalation_reason"] = f"{floor} — {lead}"
    elif d.get("held_by") == "attribution" and lead not in d["escalation_reason"]:
        d["escalation_reason"] = f"{lead} {d['escalation_reason']}"
    uncontained = ""
    if not (d["escalate"] or floor):
        contained, note = agent._contained_now(signal)
        if not contained:
            uncontained = (f"{lead} Seul un instantané a répondu : la VM n'est pas isolée{note}, l'attaque peut "
                           "continuer. Juger s'il faut isoler la VM ou bloquer la source.")
    return {
        **state,
        "reasoning": d["reasoning"], "confidence": 0.0, "action": d["action"], "reversible": True,
        "explanation": d["explanation"], "escalate": d["escalate"],
        "escalation_reason": d.get("escalation_reason", ""), "suggested_steps": d["suggested_steps"],
        "llm_usage": None, "autonomy_mode": mode, "mode_hold": mode_hold, "held_by": d.get("held_by", ""),
        "autonomy_gate": gate, "decision_temperature": None, "decision_draws": [],
        "decision_model": model if limited else "",
        "uncontained": uncontained, "floor": floor, "floor_card": bool(floor) and not d["escalate"],
        "floor_displaced": d.get("displaced", "") if floor else "", "ceiling": None, "ceiling_card": False,
    }
