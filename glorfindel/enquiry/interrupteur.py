"""The switch of the enquiry in production (ENQ5b, #1284; `docs/design/enquete-raisonnee.md` §5, §6, §7, §9.4):
``GLORFINDEL_ENQUIRY``, the operator's, read where the watch starts (host.env on Imladris) — never a key of the
config, which the console rewrites and which is read strictly (MEM2's reasons).

- ``fixed`` — the default, unset or empty: today's enquiry (`fixed.enquire`, the routing on the line's
  columns) and today's decision. **Nothing changes**: the message `_build_user_message()` writes, the
  `_SYSTEM_PROMPT`, the `_DECISION_TOOL` and `few_shot_examples.yaml` are origin/main's, to the byte
  (tests/unit/test_enquiry_production.py, their sha256 on fixed signals, Linux and Windows); no module of the
  loop is loaded.
- ``loop`` — the loop of ENQ4 in the watch (`production.py`): the model chooses its reads in the closed
  catalogue within N and T, the obligatory reads of the sheet first; then `decide` reads the enquiry with
  its seven states, the sheet, the last enquiry on the object, and may cite its hypotheses, which the code
  checks (`decision.py`). Switched on Imladris only after Jonathan's end-to-end run (§9.4), with MEM2.

**Any other value is refused at the start** (`Refuse`): the watch does not start, and says why
(`refuser`) — an unknown value is never read as one of the two, neither the old enquiry for a typo of
``loop`` nor the new one for a typo of ``fixed``. `GlorfindelAgent` refuses it too (`glorfindel respond`).

**T and N** (§5.1, Q2): N = 4 reads the model chooses, T = 30 s for the whole enquiry, its turns
included — Jonathan's values of 24/11, kept on the measure (§9.5, `docs/raisonnement.md` §10.2): at the
harness's session of 24/11, an enquiry took 12 s in median, 17.2 s at most with T = 120 s (0 of 120 past
30 s), a turn 1.7 to 2.0 s in median and 7.5 to 7.7 s at the p95; the model chose 1 to 3 reads and
concluded in 3 turns 21 times out of 30 — N = 4 is never what stops it. What the measure does not say:
the reads there were replayed at 1 s each, and five turns at the p95 make 38.5 s before any read. So the
end-to-end run recalibrates them on the real KQL and ARM reads (MEM-Hb, ENQ5a): ``GLORFINDEL_ENQUIRY_T_S``
(5 to 120) and ``GLORFINDEL_ENQUIRY_N`` (1 to 8), the operator's too, refused at the start outside their
bounds.

**The calls of a decision with an enquiry** (§5.1, PRT1, PRT2): N + 1 turns (N reads, then `conclure`),
announced to the gate (`tours`: the reserve and the share of the decision, `glorfindel/decision_queue.py`),
counted when it ends (`calls_made`, from the state's `enquete.appels`). Each turn goes through
`completion_with_tool`, so through the breaker in dollars; a turn refused stops the enquiry, and `decide`
takes the code's path.

This module loads nothing of the loop: `agent.py` and the gate import it alone; the loop's modules are
imported only once the switch says ``loop``, and a cycle carries an enquiry (`state["enquete"]`).
"""
from __future__ import annotations

import math
import os

SWITCH = "GLORFINDEL_ENQUIRY"
FIXED, LOOP = "fixed", "loop"
MODES = (FIXED, LOOP)
T_SWITCH, N_SWITCH = "GLORFINDEL_ENQUIRY_T_S", "GLORFINDEL_ENQUIRY_N"
# Q2 (23/11), kept by Jonathan on 24/11 after the harness's session (§9.5): the module's docstring says why.
N_DEFAUT, T_DEFAUT = 4, 30.0
N_BORNES, T_BORNES = (1, 8), (5.0, 120.0)


class Refuse(ValueError):
    """A value of the switch, or of T or N, that is none of theirs: refused at the start, said."""


def _shown(raw: str) -> str:
    return "".join(c if c.isprintable() else "?" for c in raw)[:40]


def mode(env=None) -> str:
    """``fixed`` (unset or empty: the default) or ``loop``, spaces around aside — anything else raises
    `Refuse`, which says the value and the two expected."""
    raw = (os.environ if env is None else env).get(SWITCH)
    value = raw.strip() if isinstance(raw, str) else ""
    if not value:
        return FIXED
    if value in MODES:
        return value
    raise Refuse(f"{SWITCH}={_shown(raw)!r} refusé : {FIXED} (le défaut, l'enquête d'aujourd'hui) ou {LOOP} "
                 "(la boucle de l'enquête) — aucune autre valeur n'est lue comme l'une des deux")


def boucle(env=None) -> bool:
    """The switch says ``loop``."""
    return mode(env) == LOOP


def _borne(env, name: str, default, bornes, kind):
    raw = (os.environ if env is None else env).get(name)
    if not isinstance(raw, str) or not raw.strip():
        return default
    try:
        value = kind(raw.strip())
    except ValueError:
        value = None
    if value is None or (isinstance(value, float) and not math.isfinite(value)) or not bornes[0] <= value <= bornes[1]:
        raise Refuse(f"{name}={_shown(raw)!r} refusé : un nombre de {bornes[0]:g} à {bornes[1]:g} "
                     f"(le défaut : {default:g})")
    return value


def n(env=None) -> int:
    """N: the reads the model may choose (`N_DEFAUT`, else ``GLORFINDEL_ENQUIRY_N`` within its bounds)."""
    return _borne(env, N_SWITCH, N_DEFAUT, N_BORNES, int)


def t(env=None) -> float:
    """T: the real delay of the whole enquiry, in seconds (`T_DEFAUT`, else ``GLORFINDEL_ENQUIRY_T_S``)."""
    return float(_borne(env, T_SWITCH, T_DEFAUT, T_BORNES, float))


def verifier(env=None) -> str:
    """What the start says of the switch: "" in ``fixed``; in ``loop``, the switch, T and N. Raises
    `Refuse` on a value that is none of theirs — the switch, T or N."""
    if mode(env) == FIXED:
        n(env), t(env)
        return ""
    return (f"{SWITCH}={LOOP} : la boucle de l'enquête — au plus {n(env)} lecture(s) choisies par le modèle, "
            f"en {t(env):g} s, les obligatoires de la fiche d'abord")


def refuser(console) -> None:
    """At the start of the watch: the switch said (``loop``), or refused — the watch does not start."""
    try:
        said = verifier()
    except Refuse as exc:
        from rich.markup import escape
        console.print(f"[bold red]{SWITCH} refusé[/bold red] — la watch ne démarre pas sur un interrupteur "
                      f"qu'elle ne sait pas lire.\n{escape(str(exc))}")
        raise SystemExit(2) from None
    if said:
        from rich.markup import escape
        console.print(f"[bold]Enquête :[/bold] [cyan]{escape(said)}[/cyan]")


def tours(data: dict, env=None) -> int:
    """The turns a decision's enquiry may make (N + 1: N reads, then `conclure`) — announced to the gate,
    beside the draws: in ``loop``, on a detection of the data plane (the only signal `investigate` enquires
    on); else 0. A value that does not read counts the default's: never fewer calls than may be made."""
    try:
        on = boucle(env)
        count = n(env)
    except Refuse:
        on, count = True, N_DEFAUT
    ctx = data.get("context") if isinstance(data.get("context"), dict) else {}
    if not on or data.get("event") != "detection" or ctx.get("plane") in ("control", "identity"):
        return 0
    return count + 1


# ── What agent.py calls: nothing of the loop in ``fixed``, nor without an enquiry on the cycle ─────────

def enqueter(state: dict, workspace_id: str, model: str, connector=None) -> dict | None:
    """`investigate` in ``loop``: the watch's enquiry (`production.enqueter`); None in ``fixed`` —
    `investigate` runs today's."""
    if not boucle():
        return None
    from glorfindel.enquiry import production
    return production.enqueter(state, workspace_id, model=model, connector=connector)


def decision(state: dict, message: str, prompt: str, tool: dict, build) -> tuple[str, str, dict]:
    """`decide`'s message, prompt and tool: today's, unless the cycle carries an enquiry (§6)."""
    if not state.get("enquete"):
        return message, prompt, tool
    from glorfindel.enquiry import decision as d_
    return (d_.message(state, build), d_.prompt(prompt), d_.outil(tool))


def citations(response, state: dict) -> dict:
    """The hypotheses the model cited, checked by the code (§6.3): the cycle's enquiry with them, or {}."""
    if not state.get("enquete"):
        return {}
    from glorfindel.enquiry import decision as d_
    return d_.citations(response, state["enquete"])


def dire_trous(d: dict, enquete: dict) -> None:
    """After the telemetry guard (§7.2), held on the enquiry's gaps: each said with its state."""
    if not enquete:
        return
    from glorfindel.enquiry import decision as d_
    d_.dire_trous(d, enquete)


def plancher_grave(d: dict, signal: dict, enquete: dict, floor: str, ceiling: dict) -> tuple[str, dict]:
    """The extension of the floor V-11 (§7.3): (floor, ceiling), unchanged without an enquiry."""
    if not enquete:
        return floor, ceiling
    from glorfindel.enquiry import decision as d_
    return d_.plancher_grave(d, signal, enquete, floor, ceiling)


def carte(state: dict) -> dict | None:
    """What the card says of the enquiry (its hypotheses, their state, what settled them), or None."""
    if not state.get("enquete"):
        return None
    from glorfindel.enquiry import decision as d_
    return d_.carte(state["enquete"])


def etapes(state: dict) -> list[str]:
    """The steps of a floor's card the extension of V-11 wrote (§7.3), [] otherwise."""
    if not state.get("enquete") or not (state["enquete"].get("plancher") or ""):
        return []
    from glorfindel.enquiry import decision as d_
    return d_.ETAPES_PLANCHER


def retenir(state: dict) -> None:
    """At the end of the cycle: the memory per object, written by the watch (§5.5) — never raises."""
    if not state.get("enquete") or state.get("dry_run"):
        return
    try:
        from glorfindel.enquiry import memoire
        memoire.retenir(state)
    except Exception as exc:                    # said, the cycle goes on: the next enquiry has no reference
        from glorfindel.terminal import GlorfindelConsole
        from rich.markup import escape
        GlorfindelConsole().print(f"[yellow]enquête : la mémoire par objet non écrite — "
                                  f"{escape(type(exc).__name__)}[/yellow]")
