"""Lot R2c (docs/design/stratus-cible.md) — première pièce : l'outillage du kill coupe
l'identité Stratus seule. `orodruin-kill` tient maintenant une étape de plus, après sa propre
révocation : l'opérateur retire le rôle de l'identité Stratus sur son abonnement dédié
(Orodruin ne le peut pas — il n'y a que `AUTHZ_READ_ONLY`). Les mutants portent sur
l'orchestration (l'étape appelée, à la bonne place) et sur l'outil `stratus_revoke_step`
(la relecture après suppression, la suppression elle-même, le motif M191 `--all` /
`--assignee-object-id` / `--subscription`, la garde « absente sans identité », la rédaction de
l'abonnement). M4440–M4447. Mesurés par tests/unit/test_orodruin.py et test_orodruin_kill.py.
M4448–M4469 restent réservés aux pièces suivantes de R2c (refus du contrat, scope Stratus +
`kind: fault`, rôle fermé, fédération) — à monter avec la session Annatar.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et
TESTS (ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
ORODRUIN = "eregion_core/orodruin.py"
KILL = "infra/orodruin/kill.py"

_TO = "tests/unit/test_orodruin.py"
_TK = "tests/unit/test_orodruin_kill.py"
_ORDER = f"{_TO}::test_revoke_stratus_runs_right_after_the_revocation_when_given"
_STILL = f"{_TK}::test_a_stratus_role_still_listed_after_the_deletion_is_an_error"
_GONE = f"{_TK}::test_the_stratus_role_is_revoked_and_proven_gone"
_ABSENT = f"{_TK}::test_the_stratus_step_is_absent_without_an_identity"
_REDACT = f"{_TK}::test_the_stratus_subscription_is_never_printed"

# The listing spans two lines; built here so the whitespace is exact (32-space continuation).
_LIST_ALL = '"list", "--all",\n' + " " * 32 + '"--assignee-object-id"'
_LIST_NOALL = '"list",\n' + " " * 32 + '"--assignee-object-id"'

MUTANTS = [
    ("M4440", "the Stratus revocation is never run — the kill cuts Orodruin's identity but leaves "
     "the Stratus identity's role on the dedicated subscription intact (R2c)",
     ORODRUIN, 'run("revoke_stratus", revoke_stratus)', "pass"),
    ("M4441", "the Stratus revocation runs in the wrong place — after close instead of right after "
     "the revocation, so a warmup keeps its rights while the rest of the kill drags (R2c)",
     ORODRUIN, 'if name == "revoke":   # R2c:', 'if name == "close":   # R2c:'),
    ("M4442", "« nothing left » is assumed, not read again — a deletion that did not take is "
     "reported as a clean revocation (R2c)",
     KILL, "        left = listed()", "        left = []"),
    ("M4443", "the assignments are listed but never deleted — the Stratus identity keeps its role "
     "and the kill still claims success (R2c)",
     KILL, 'call(["role", "assignment", "delete", "--subscription", subscription, "--ids", *ids])',
     "ids"),
    ("M4444", "the --assignee-object-id filter is dropped — the listing (and its deletion) would "
     "reach every identity's assignments on the dedicated subscription, not Stratus's (R2c)",
     KILL, '"--assignee-object-id", oid, "--subscription", subscription,',
     '"--subscription", subscription,'),
    ("M4445", "--all is dropped — an assignment posed on a resource group escapes the listing "
     "(the M191 bug), so the kill misses it and proves nothing (R2c)",
     KILL, _LIST_ALL, _LIST_NOALL),
    ("M4446", "the « absent without an identity » guard is inverted — the step is built when no "
     "Stratus identity is given and skipped when one is (R2c)",
     KILL, "    if not (oid and subscription):", "    if (oid and subscription):"),
    ("M4447", "the dedicated subscription is no longer redacted — the kill prints it on screen "
     "(M124: a kill's lines never name a subscription) (R2c)",
     KILL,
     'say(redact(("[dry-run] az " if dry_run else "az ") + " ".join(args), [subscription]))',
     'say(("[dry-run] az " if dry_run else "az ") + " ".join(args))'),
]

TESTS = {
    "M4440": _ORDER,
    "M4441": _ORDER,
    "M4442": _STILL,
    "M4443": _GONE,
    "M4444": _GONE,
    "M4445": _GONE,
    "M4446": _ABSENT,
    "M4447": _REDACT,
}
