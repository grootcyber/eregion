"""DOC9 (#1166): the bound of the model's spending said right — on Eregion's side, the watch's breaker is its only
bound; the provider caps at the organisation's tier, or lower where the operator set a limit, recommended, never
required (the maintainer's decision of 24/11). M7482–M7489, measured by tests/unit/test_model_budget.py."""
MB = "glorfindel/model_budget.py"
OPS = "docs/operations.md"
_T = "tests/unit/test_model_budget.py"

MUTANTS = [
    ("M7482", "the watch's start line says the hard ceiling is at the provider's again: a limit supposed set (DOC9)",
     MB,
     '''                    f"({self.campaign_usd:.2f} $ par campagne) — côté Eregion, ce compte est la seule borne de "
                    "cette watch ; le fournisseur plafonne au palier de l'organisation, ou plus bas si l'opérateur "
                    "y a posé une limite (recommandé)"
''',
     '''                    f"({self.campaign_usd:.2f} $ par campagne) — le plafond dur est chez le fournisseur"
'''),
    ("M7483", "a count lost says the hard ceiling still holds at the provider's: no limit is set there (DOC9)", MB,
     '''                "plus compté : jusqu'à minuit UTC, cette watch peut dépenser de nouveau tout son budget, et rien "
                "côté Eregion ne borne ce qui l'a été avant. Chez le fournisseur, seul le plafond du palier de "
                "l'organisation la retient, ou une limite plus basse si l'opérateur en a posé une (recommandé).")
''',
     '''                "plus compté : le plafond dur reste chez le fournisseur.")
'''),
    ("M7484", "a count lost says the breaker still holds what it no longer counts (DOC9)", MB,
     '''cette watch peut dépenser de nouveau tout son budget, et rien "
                "côté Eregion ne borne ce qui l'a été avant.''',
     '''le disjoncteur retient encore ce qui "
                "a été dépensé avant.'''),
    ("M7485", "the alert's last step says the hard ceiling is at the provider's again (DOC9)", MB,
     '''    "Côté Eregion, ce disjoncteur est la seule borne de la watch ; le fournisseur plafonne au palier de "
    "l'organisation, ou plus bas si l'opérateur a posé une limite sur l'espace de travail de la clé — "
    "recommandé, contre une clé qui fuit (docs/operations.md, « Le budget du modèle »).",
''',
     '''    "Le plafond dur reste chez le fournisseur : la limite de dépense mensuelle de l'espace de travail de la clé.",
'''),
    ("M7486", "a limit the operator set (a 400 « API usage limits ») not read as the provider's: a failed cycle "
     "(DOC9)", MB,
     '"credit balance", "usage limit", "spend limit")', '"credit balance", "spend limit")'),
    ("M7487", "the tier's spend cap (a 429 enforced_spend_limit_reached) read only by LiteLLM's class name: a "
     "failed cycle (DOC9)", MB,
     '    if getattr(exc, "status_code", None) == 429 or type(exc).__name__ == "RateLimitError":\n',
     '    if type(exc).__name__ == "RateLimitError":\n'),
    ("M7488", "the docs make the limit at the provider's a step of the install again (DOC9)", OPS,
     "**Une limite chez le fournisseur : recommandée, jamais obligatoire.**",
     "**Le plafond dur est chez le fournisseur : geste de l'opérateur, une fois.**"),
    ("M7489", "the docs forget that a second watch is outside the breaker (DOC9)", OPS,
     '''- une seconde watch : chaque watch a son propre compte, et deux watches sur la même clé dépensent chacune
  tout leur budget ;
''', ""),
]
TESTS = {f"M{n}": _T for n in range(7482, 7490)}
