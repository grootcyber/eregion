"""Lot R2c (docs/design/stratus-cible.md) — première pièce : l'outillage du kill coupe
l'identité Stratus seule. `orodruin-kill` tient maintenant une étape de plus, après sa propre
révocation : l'opérateur retire le rôle de l'identité Stratus sur son abonnement dédié
(Orodruin ne le peut pas — il n'y a que `AUTHZ_READ_ONLY`). Les mutants portent sur
l'orchestration (l'étape appelée, à la bonne place) et sur l'outil `stratus_revoke_step`
(la relecture après suppression, la suppression elle-même, le motif M191 `--all` /
`--assignee-object-id` / `--subscription`, la garde « absente sans identité », la rédaction de
l'abonnement). M4440–M4447. Mesurés par tests/unit/test_orodruin.py et test_orodruin_kill.py.
M4448–M4460 sont allés à R2BGc (les garde-fous en Terraform) ; M4461–M4466 = le contrat qui
s'arme POUR Stratus (Pièce 2, ci-dessous, eregion_core/orodruin.py), mesurés par
tests/unit/test_stratus_contract.py ; M4467–M4469 restent réservés au bac à sable durci (Pièce 3).

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

# Pièce 2 — le contrat s'arme POUR Stratus (eregion_core/orodruin.py, assess_stratus).
_TC = "tests/unit/test_stratus_contract.py"
_FORBIDDEN = f"{_TC}::test_a_forbidden_subscription_is_refused_and_stops_everything"
_UNPROVABLE = f"{_TC}::test_an_empty_or_partial_listing_is_never_an_absence"
_BEYOND = f"{_TC}::test_a_right_beyond_the_closed_role_is_passive"
_AUTHZ = f"{_TC}::test_an_authorization_action_is_more_than_the_closed_role"
_COLD = f"{_TC}::test_a_subscription_that_is_not_cold_is_passive"
_DIAG = f"{_TC}::test_a_missing_or_dead_diagnostic_is_passive"

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
    # ── Pièce 2 — le contrat s'arme POUR Stratus (assess_stratus) ──
    ("M4461", "a forbidden subscription is not refused — the contract arms for Stratus on the "
     "bench's, the VM's or Imladris's subscription, where its rights would reach the bench (the "
     "v1 blocker) (R2c, pièce 2)",
     ORODRUIN, "    if subscription.lower() in protected:",
     "    if subscription.lower() in frozenset():"),
    ("M4462", "an empty or partial listing is taken for an absence — an assignment Orodruin cannot "
     "read is assumed not to exist, so Stratus arms though it may hold more elsewhere (M5) "
     "(R2c, pièce 2)",
     ORODRUIN,
     '    if not sees_subscription:  # M5: a listing Orodruin cannot fully read is no absence\n'
     '        missing.append(_miss("stratus_identity_unprovable",',
     '    if sees_subscription:  # M5: a listing Orodruin cannot fully read is no absence\n'
     '        missing.append(_miss("stratus_identity_unprovable",'),
    ("M4463", "a right beyond the closed role is not caught — the allow-list subtraction is "
     "neutered, so Stratus arms while holding more than its measured role (SEC11) (R2c, pièce 2)",
     ORODRUIN, "        unlisted = sorted(actions - STRATUS_CLOSED_ROLE_ACTIONS)",
     "        unlisted = sorted(actions - actions)"),
    ("M4464", "a Microsoft.Authorization action slips into the allow-list — Stratus could grant "
     "itself roles and still be armed (the one family the closed role must never hold) "
     "(R2c, pièce 2)",
     ORODRUIN, '    "Microsoft.Network/publicIPAddresses/join/action",',
     '    "Microsoft.Authorization/roleAssignments/write",'),
    ("M4465", "COLD is no longer checked — the contract arms on a subscription that is not empty "
     "(a leftover group of a previous run beside Azure's own) (M6) (R2c, pièce 2)",
     ORODRUIN, "    extra = sorted(g for g in groups if not _azure_own_group(g))",
     "    extra = []"),
    ("M4466", "a missing activity-log diagnostic no longer holds the contract — Stratus arms "
     "though the watch would be blind to it (R2c, pièce 2)",
     ORODRUIN, "    if not diag_ok:", "    if diag_ok:"),
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
    "M4461": _FORBIDDEN,
    "M4462": _UNPROVABLE,
    "M4463": _BEYOND,
    "M4464": _AUTHZ,
    "M4465": _COLD,
    "M4466": _DIAG,
}
