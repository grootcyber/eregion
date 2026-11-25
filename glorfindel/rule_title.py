"""The title of a cloud detection's card, declared by its rule (RTT1a, #1174; Jonathan, 25/11).

A card of the control plane (`control_plane_change`) or of an identity (`identity_change`) was titled
by its type alone: « Entra ID identity change » for a mere sign-in, « Control-plane change » for a
Run Command or a disk's export. Its rule now says what it detects, in a short title, in English:

    - name: entra-sp-unusual-signin
      title: "Entra ID unusual sign-in"

- **Declared by the rule, read from the rule alone**: the eleven shipped rules of the two families
  carry one (glorfindel/rules/azure/detection_rules.yaml). A card keeps it in `rule_title`, written
  once with the card (`escalations.record`): never from the signal, the model, nor any text from
  outside — the rule's name only chooses which rule's title. Never `title`, which a VM's notice
  already holds (`escalations._action_words`).
- **Checked at load, as any field of a rule (P1)**: a string, not empty, at most `MAX_LEN` characters,
  on one line, no control character (`refusal`). The client's layer may declare one: an invalid one
  skips its entry, said, the shipped rule of its name loading instead (`_invalid_client_entry`). The
  shipped base stays as it is: an unreadable title there is said, and its cards take the neutral one.
- **The neutral title**: a rule without a title (the client's, one approved), a card written before
  RTT1a, rules unreadable when the card is written: « Entra ID detection », « Control-plane detection »,
  by the card's type (`NEUTRAL`).
- **The type and its guards unchanged**: `identity_change` and `control_plane_change` stay what the
  approval, the policy, the folding of cards, the bot, the console and the analysis read. The title
  is only shown — escaped on every surface, as any text (SEC6, glorfindel/chat_text.py).
- **A rule renamed never rewrites a card**: a card keeps the title it was written with.
"""
from __future__ import annotations

import unicodedata

KEY = "title"
FIELD = "rule_title"
MAX_LEN = 80
# The neutral title of each card type a cloud rule's detection is filed as — the two families.
NEUTRAL = {
    "identity_change": "Entra ID detection",
    "control_plane_change": "Control-plane detection",
}


def refusal(value) -> str:
    """Why a rule's `title:` cannot be read — '' when it can."""
    if not isinstance(value, str):
        return "`title` n'est pas une chaîne"
    if not value.strip():
        return "`title` est vide"
    if len(value) > MAX_LEN:
        return f"`title` dépasse {MAX_LEN} caractères ({len(value)})"
    if any(unicodedata.category(c)[0] == "C" or unicodedata.category(c) in ("Zl", "Zp") for c in value):
        return "`title` tient un retour à la ligne ou un caractère de contrôle (une ligne de texte)"
    return ""


def parse(value: str) -> str:
    """A `title:` `refusal` accepted, its spaces as one."""
    return " ".join(value.split())


def of_rules(base_rules: list[dict], merged_rules: list[dict], layer: dict[str, str],
             notes: list[str]) -> dict[str, str]:
    """{name: its title} of every merged rule that declares a readable one. A rule of the client's
    layer has its own or none — never the shipped one of its name (a copy declares it again);
    checked by the layer (`_invalid_client_entry`): an unreadable one skipped the entry. A shipped
    rule's unreadable title: none, and said — the base stays as it is."""
    out: dict[str, str] = {}
    for item in merged_rules:
        name = item.get("name") if isinstance(item, dict) else None
        if not name or KEY not in item:
            continue
        why = refusal(item[KEY])
        if why:
            if layer.get(name) != "client":
                notes.append(f"règle de base « {name} » : titre illisible ({why}) — ses cartes prennent le "
                             "titre neutre")
            continue
        out[name] = parse(item[KEY])
    return out


def current() -> dict[str, str]:
    """The titles as the shipped base and the client's layer stand now (the same layers as the watch,
    read when the card is written, as the ceiling is). Raises when the shipped base cannot be read."""
    from glorfindel import detection_rules as dr
    layers = dr.rule_layers(dr.shipped_rules_path())
    rules = [r for r in dr._named(layers.merged.get("rules")) if r.get("enabled", True)]
    return of_rules(dr._named(layers.base.get("rules")), rules, layers.layer_of, [])


def for_card(rule_name: str, escalation_type: str) -> str:
    """The `rule_title` a new card carries: its rule's title, else the neutral one of its type — for a
    card of a cloud detection only ('' for any other type). Never raises: rules unreadable, the
    neutral one (a card is never lost for its title)."""
    neutral = NEUTRAL.get(escalation_type) if isinstance(escalation_type, str) else None
    if neutral is None:
        return ""
    if not rule_name:
        return neutral
    try:
        return current().get(str(rule_name)) or neutral
    except Exception:
        return neutral


def shown(card: dict) -> str:
    """What a surface shows as a cloud card's title: its `rule_title`, checked again (a store written
    by hand, a forged line), else the neutral one of its type — a card written before RTT1a too. ''
    for a card of any other type: its title stays what it was."""
    if not isinstance(card, dict):
        return ""
    etype = card.get("escalation_type")
    # A forged line's type may be anything — a list is not even a key: never raises (RTT1b).
    neutral = NEUTRAL.get(etype) if isinstance(etype, str) else None
    if neutral is None:
        return ""
    title = card.get(FIELD)
    return parse(title) if not refusal(title) else neutral
