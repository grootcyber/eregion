"""The rule's ceiling (RDW1, #994; Jonathan, 20/11): what a detection rule lets its detection lead
to, at most, whatever the model proposes and however sure it is.

The bench of 20/11 (G1, v0.6.3): Gothmog's benign fault `vm-disk-write`, a backup's sustained writes
(about 74 MB/s for 10 min), fired `ransomware-disk-write`; the model proposed `isolate_vm` at 80 %,
above the threshold of 0.7. Only `human_only` held it: under `non_disruptive`, gondolin would have
been isolated. The throughput alone does not tell a backup from an encryption (the rule's comment: the
highest benign 60-s average 23.2 MB/s, attacks from 26.8 to 91.7 MB/s) — raising the threshold would
miss attacks. So the rule carries the bound, in the shipped base, and a guard of `decide` reads it:
safety held by the rule, never by the model's confidence.

    ceiling:
      allow: [snapshot]      # the autonomous actions this rule's detection may lead to, at most
      lifted_by: []          # facts of the detection that lift the ceiling (the corroboration, later)
      why: "…"               # said on the card: what the rule proves, and what it does not

- `allow`: autonomous actions only (`AUTONOMOUS_ACTIONS`), `snapshot` always among them — the action a
  decision above the ceiling is brought back to: it contains nothing, it keeps the disk as it is.
- `lifted_by`: names of facts (`agent.confirmed_facts`, B3a; the corroboration's verdict, SEC-A3, when
  it comes): one of them present in the detection's facts, and the ceiling does not play. Empty for
  every shipped rule in RDW1: the isolation of a disk write comes back with the corroboration, measured
  on the bench, in a lot of its own.
- The client's layer (P1) may lower a rule's ceiling, never raise it above the shipped one: a client
  rule of a shipped rule's name is bound by the shipped ceiling whatever it says (`allow` and
  `lifted_by` intersected with the base's), and keeps it when it says none. A rule without a ceiling
  behaves as before.

Never in the signal, so never in what the model reads (`_build_user_message` dumps the signal): the
guard reads the rules on disk, by the rule's name — the same layers as the watch.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from glorfindel.response.policy import AUTONOMOUS_ACTIONS

# The action a decision above the ceiling is brought back to: it contains nothing, and keeps the disk
# as it was when the rule fired (the evidence). Never capped itself.
LOWERED_TO = "snapshot"
KEY = "ceiling"
_KEYS = ("allow", "lifted_by", "why")
_FACT = re.compile(r"[a-z][a-z0-9_]{0,63}")
_WHY_MAX = 300


@dataclass(frozen=True)
class Ceiling:
    """A rule's ceiling: the autonomous actions it allows (`snapshot` always), the facts that lift it,
    and what the card says of it."""
    allow: tuple[str, ...] = (LOWERED_TO,)
    lifted_by: tuple[str, ...] = ()
    why: str = ""

    def as_dict(self) -> dict:
        return {"allow": list(self.allow), "lifted_by": list(self.lifted_by), "why": self.why}


# An unreadable ceiling of the shipped base: the lowest one, never none (fail closed).
LOWEST = Ceiling()


def refusal(value) -> str:
    """Why a rule's `ceiling:` cannot be read — '' when it can."""
    if not isinstance(value, dict):
        return "`ceiling` n'est pas un dictionnaire (allow:, lifted_by:, why:)"
    unknown = sorted(str(k) for k in value if k not in _KEYS)
    if unknown:
        return f"`ceiling` : clé inconnue « {unknown[0]} » ({', '.join(_KEYS)})"
    allow = value.get("allow")
    if not (isinstance(allow, list) and all(isinstance(a, str) for a in allow)):
        return "`ceiling.allow` n'est pas une liste d'actions"
    other = [a for a in allow if a not in AUTONOMOUS_ACTIONS]
    if other:
        return (f"`ceiling.allow` : « {other[0]} » n'est pas une action autonome "
                f"({', '.join(sorted(AUTONOMOUS_ACTIONS))})")
    if LOWERED_TO not in allow:
        return (f"`ceiling.allow` doit garder « {LOWERED_TO} » : la décision au-dessus du plafond y est "
                "ramenée")
    lifted = value.get("lifted_by", [])
    if not (isinstance(lifted, list) and all(isinstance(f, str) and _FACT.fullmatch(f) for f in lifted)):
        return "`ceiling.lifted_by` n'est pas une liste de noms de faits (minuscules, chiffres, _)"
    why = value.get("why", "")
    if not isinstance(why, str) or len(why) > _WHY_MAX:
        return f"`ceiling.why` n'est pas un texte de {_WHY_MAX} caractères au plus"
    return ""


def parse(value) -> Ceiling:
    """A `ceiling:` `refusal` accepted, as a Ceiling (its lists without repeats, in their order)."""
    return Ceiling(allow=tuple(dict.fromkeys(value["allow"])),
                   lifted_by=tuple(dict.fromkeys(value.get("lifted_by") or [])),
                   why=" ".join(str(value.get("why") or "").split()))


def _of_base(entry: dict | None, notes: list[str]) -> Ceiling | None:
    """The shipped rule's ceiling (None: it has none). Unreadable: the lowest, and said."""
    if not isinstance(entry, dict) or KEY not in entry:
        return None
    why = refusal(entry[KEY])
    if why:
        notes.append(f"règle de base « {entry.get('name')} » : plafond illisible ({why}) — le plus bas "
                     f"tient : {LOWERED_TO} seul")
        return LOWEST
    return parse(entry[KEY])


def bound(base: Ceiling | None, client: Ceiling | None, name: str, notes: list[str]) -> Ceiling | None:
    """The ceiling of a client rule of a shipped rule's name: the client's lowers the base's, never
    raises it. No ceiling in the base: the client's. None in the client: the base's, kept."""
    if base is None:
        return client
    if client is None:
        return base
    allow = tuple(a for a in base.allow if a in client.allow)
    lifted = tuple(f for f in base.lifted_by if f in client.lifted_by)
    if set(client.allow) - set(base.allow) or set(client.lifted_by) - set(base.lifted_by):
        notes.append(f"règle du client « {name} » : plafond relevé au-dessus de celui de la règle livrée "
                     "— la couche du client l'abaisse, jamais ne le relève ; celui de la base tient")
    return Ceiling(allow=allow, lifted_by=lifted, why=client.why or base.why)


def of_rules(base_rules: list[dict], merged_rules: list[dict], layer: dict[str, str],
             notes: list[str]) -> dict[str, Ceiling | None]:
    """{name: its ceiling, or None} of every merged rule — the shipped ceiling of its name always
    holds (`bound`), whatever the layer did (a rule replaced, disabled then named again)."""
    base = {r["name"]: r for r in base_rules if isinstance(r, dict) and r.get("name")}
    out: dict[str, Ceiling | None] = {}
    for item in merged_rules:
        name = item.get("name") if isinstance(item, dict) else None
        if not name:
            continue
        shipped = _of_base(base.get(name), notes)
        if layer.get(name) == "client":
            # Checked by the layer (`_invalid_client_entry`): an unreadable one skipped the entry.
            own = parse(item[KEY]) if KEY in item and not refusal(item[KEY]) else None
            out[name] = bound(shipped, own, name, notes)
        else:
            out[name] = shipped
    return out


@dataclass
class RuleCeilings:
    """The ceilings of the rules as the layers stand now: by name, and the rules in their order (the
    name, the TTP, the query) for a detection that names no rule (attack_started)."""
    by_name: dict[str, Ceiling | None]
    rules: list[tuple[str, str, str]]

    def for_signal(self, signal: dict) -> tuple[str, Ceiling | None]:
        """(the rule, its ceiling) of a detection. The RulePoller's names its rule; an attack_started
        resolved by the graph names none: the rule of the query it polled (the scenario's own,
        compared to the byte), else the first rule of its TTP — the one `_find_rule_for_ttp` lends."""
        name = str((signal.get("context") or {}).get("rule_name") or "")
        if name:
            return name, self.by_name.get(name)
        query = str((signal.get("raw_signal") or {}).get("detection_query") or "")
        ttp = str(signal.get("ttp") or "")
        for rule, rule_ttp, rule_query in self.rules:
            if (query and rule_query == query) or (not query and ttp and rule_ttp == ttp):
                return rule, self.by_name.get(rule)
        return "", None


def current() -> RuleCeilings:
    """The ceilings as the shipped base and the client's layer stand now (read at each decision, as
    the autonomy is: a ceiling the client lowers takes effect at the next detection). Raises when the
    shipped base cannot be read — `decide` then brings the decision back to the lowest."""
    from glorfindel import detection_rules as dr
    shipped = dr.shipped_rules_path()
    layers = dr.rule_layers(shipped)
    if not dr._named(layers.base.get("rules")):
        # A base read as « nothing » (`_read_layer` gives {} for a file gone) would cap no rule: the
        # shipped file absent or without rules is unreadable, never an empty list (fail closed).
        raise FileNotFoundError(f"base livrée absente ou sans règle : {shipped}")
    rules = [r for r in dr._named(layers.merged.get("rules")) if r.get("enabled", True)]
    by_name = of_rules(dr._named(layers.base.get("rules")), rules, layers.layer_of, [])
    return RuleCeilings(by_name=by_name,
                        rules=[(r["name"], str(r.get("ttp") or ""), str(r.get("query") or "")) for r in rules])
