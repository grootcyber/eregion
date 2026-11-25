"""Les champs que la watch écrit pour `/api/watch/status`, sortis d'api.py (SUBN1, #1190 ; WCH1 : api.py
tient son plafond de taille).

- `log_freshness` (LOGF1, #1183) : la fraîcheur des journaux de chaque table que les règles lisent
  (glorfindel/log_freshness.py).
- `subscriptions` (SUBN1) : le nom lisible de chaque abonnement vu, sous sa clé masquée
  (glorfindel/subscription_names.py).

Chacun gardé comme `_model_breakers` : un module qui lève fait disparaître son champ, jamais la route ni le
battement. Le module est lu à l'appel (`__import__`) : un test le remplace sur le module lui-même.
"""
from __future__ import annotations


def _field(module: str) -> dict:
    """Le champ d'un module de Glorfindel (son `console_field`), {} quand il lève."""
    try:
        return __import__(module, fromlist=["console_field"]).console_field()
    except Exception:
        return {}


def log_freshness() -> dict:
    """LOGF1 : la fraîcheur des journaux que la watch a écrite ; {} quand elle ne se lit pas."""
    return _field("glorfindel.log_freshness")


def subscription_names() -> dict:
    """SUBN1 : les noms des abonnements que la watch a lus ; {} quand ils ne se lisent pas."""
    return _field("glorfindel.subscription_names")


def watch_fields() -> dict:
    """Les champs de la watch pour `/api/watch/status`, chacun présent seulement quand il se lit."""
    return {**log_freshness(), **subscription_names()}
