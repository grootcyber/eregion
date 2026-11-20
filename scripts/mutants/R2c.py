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
tests/unit/test_stratus_contract.py ; M4467–M4469 = la vérif du bac à sable côté contrat (Pièce 3B,
read_sandbox / sandbox_drops_imds) ; M4482–M4484 = le bac à sable posé au démarrage (Pièce 3A,
infra/orodruin/main.tf, mesuré par tests/unit/test_orodruin.py) ; M4485–M4489 = le lancement sous
l'identité dédiée par l'échange fédéré (Pièce 4, annatar/, tests/unit/test_annatar_stratus.py).

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et
TESTS (ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
ORODRUIN = "eregion_core/orodruin.py"
KILL = "infra/orodruin/kill.py"
MAIN = "infra/orodruin/main.tf"
STRATUS_ENGINE = "annatar/engines/stratus.py"
STRATUS_HOST = "annatar/executors/stratus_host.py"
PARSER = "annatar/runner/parser.py"
STRATUS_ASSERT = "annatar/executors/stratus_assertion.py"
MAKEFILE = "Makefile"

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

# Pièce 3 — le bac à sable durci (sandbox_drops_imds / read_sandbox).
_SANDBOX_MISS = f"{_TC}::test_read_sandbox_flags_a_missing_rule"
_SANDBOX_DEST = f"{_TC}::test_a_drop_to_another_destination_does_not_count"
_SANDBOX_SRC = f"{_TC}::test_a_drop_from_another_network_does_not_count"
_SANDBOX_POSED = f"{_TO}::test_the_stratus_sandbox_is_posed_at_startup"

# Pièce 4 — le lancement sous l'identité dédiée, par l'échange fédéré (annatar/).
_TAS = "tests/unit/test_annatar_stratus.py"
_FED_EMPTY = f"{_TAS}::test_stratus_run_env_is_empty_without_the_dedicated_subscription"
_FED_AUTH = f"{_TAS}::test_stratus_run_env_authenticates_as_stratus_by_the_federated_exchange"
_FED_REFUSE = f"{_TAS}::test_stratus_run_env_refuses_an_incomplete_federated_identity"
_FED_EXEC = f"{_TAS}::test_the_executor_env_uses_the_federated_identity_over_msi"

# Pièce 4D — le scope Stratus refuse kind:fault (annatar/runner/parser.py, authoring).
_KIND_FAULT = f"{_TAS}::test_stratus_scenario_with_kind_fault_is_refused"

# Pièce 4B — le run fédéré depuis le bac à sable (assertion côté hôte, câblage Makefile).
_ASSERT_AUD = f"{_TAS}::test_the_assertion_is_fetched_for_the_exchange_audience"
_ASSERT_EMPTY = f"{_TAS}::test_an_empty_assertion_fails_closed"
_STRATUS_WIRED = f"{_TAS}::test_the_orodruin_stratus_run_is_wired_for_the_federated_exchange"

# Decision A — la garde sandbox lit une preuve en fichier (fraîcheur, pose, montage).
_SANDBOX_STALE = f"{_TC}::test_read_sandbox_refuses_a_stale_proof"
_SANDBOX_MOUNTED = f"{_TAS}::test_the_sandbox_proof_is_mounted_into_the_contract_and_the_run"
_STRATUS_CRED = f"{_TC}::test_the_stratus_credential_is_built_from_the_dedicated_env"

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
    # ── Pièce 3 — le bac à sable durci (sandbox_drops_imds, read_sandbox) ──
    ("M4467", "orodruin-check no longer refuses an open sandbox — it arms for Stratus though no "
     "DOCKER-USER rule cuts the IMDS, so a Stratus container could read Orodruin's token "
     "(R2c, pièce 3)",
     ORODRUIN, "    if not sandbox_drops_imds(rules):", "    if sandbox_drops_imds(rules):"),
    ("M4468", "the DROP rule's destination is no longer checked — a rule dropping the sandbox net "
     "to ANY address passes for the IMDS cut, though the IMDS stays reachable (R2c, pièce 3)",
     ORODRUIN, '        if _flag_value(p, "-s") == SANDBOX_NET and _flag_value(p, "-d") in imds:',
     '        if _flag_value(p, "-s") == SANDBOX_NET:'),
    ("M4469", "the DROP rule's source is no longer checked — a rule on another network passes for "
     "the sandbox's IMDS cut, though the sandbox stays open (R2c, pièce 3)",
     ORODRUIN, '        if _flag_value(p, "-s") == SANDBOX_NET and _flag_value(p, "-d") in imds:',
     '        if _flag_value(p, "-d") in imds:'),
    # ── Pièce 3, partie A — le bac à sable posé au démarrage (infra/orodruin/main.tf) ──
    ("M4482", "the DROP rule is gone from the cloud-init — the sandbox network exists but its "
     "traffic to the IMDS is no longer cut, so a Stratus container could read Orodruin's token "
     "(R2c, pièce 3)", MAIN,
     "iptables -C DOCKER-USER -s 172.30.250.0/24 -d 169.254.169.254/32 -j DROP || iptables -I "
     "DOCKER-USER -s 172.30.250.0/24 -d 169.254.169.254/32 -j DROP", "true"),
    ("M4483", "the dedicated sandbox network is no longer created — Stratus would fall back to the "
     "bridge, where the IMDS is reachable (the DROP rule binds only the sandbox network) "
     "(R2c, pièce 3)", MAIN,
     "docker network create --subnet 172.30.250.0/24 eregion-stratus-sandbox || true", "true"),
    ("M4484", "the DROP service no longer runs after docker — it could apply the rule before the "
     "DOCKER-USER chain exists, leaving the IMDS reachable until the next boot (R2c, pièce 3)",
     MAIN, "After=docker.service", "After=network.target"),
    # ── Pièce 4 — le lancement sous l'identité dédiée, par l'échange fédéré (annatar/) ──
    ("M4485", "the federated identity is never used — a Stratus run with its dedicated subscription "
     "falls through instead of authenticating as Stratus by the federated exchange (R2c, pièce 4)",
     STRATUS_ENGINE, "    if not sub:", "    if sub:"),
    ("M4486", "an incomplete federated identity no longer refuses — a dedicated-subscription run with "
     "a missing client id, token file or tenant falls back to the managed identity or the bench "
     "(the v1 blocker) instead of failing closed (R2c, pièce 4)",
     STRATUS_ENGINE, "    if not (client_id and token_file and tenant):",
     "    if (client_id and token_file and tenant):"),
    ("M4487", "the run's subscription is read from the bench, not the dedicated one — Stratus would "
     "act on the bench subscription (R2c, pièce 4)",
     STRATUS_ENGINE, "    sub = _first_set(environ, (STRATUS_SUBSCRIPTION_ENV,))",
     '    sub = _first_set(environ, ("AZURE_SUBSCRIPTION_ID",))'),
    ("M4488", "the exchange directive becomes the managed-identity one — the run would try the IMDS "
     "(blocked from the sandbox) instead of the federated exchange (R2c, pièce 4)",
     STRATUS_ENGINE, '        "ARM_USE_OIDC": "true",', '        "ARM_USE_MSI": "true",'),
    ("M4489", "the executor no longer prefers the federated identity — a configured dedicated "
     "identity is ignored and the run authenticates by the managed identity (R2c, pièce 4)",
     STRATUS_HOST,
     "        identity = stratus_run_env(os.environ) or azure_provider_env(os.environ)",
     "        identity = azure_provider_env(os.environ)"),
    ("M6606", "the stratus engine no longer refuses a kind:fault scenario — a fault could be "
     "routed through the Stratus adapter, which runs control-plane techniques only (R2c, pièce 4D)",
     PARSER, '            if str(data.get("kind") or "technique") == "fault":',
     '            if str(data.get("kind") or "technique") == "technique":'),
    ("M6607", "the assertion is fetched for the wrong audience — the federated exchange gets a "
     "token the Stratus app does not trust and the run cannot authenticate (R2c, pièce 4B)",
     STRATUS_ASSERT, 'EXCHANGE_AUDIENCE = "api://AzureADTokenExchange"',
     'EXCHANGE_AUDIENCE = "api://Wrong"'),
    ("M6608", "an empty managed-identity assertion no longer fails closed — the run would start "
     "without a real assertion (R2c, pièce 4B)",
     STRATUS_ASSERT, "    if not token:", "    if token:"),
    ("M6609", "the federated Stratus run drops the sandbox network for the host network — the IMDS "
     "becomes reachable and the run could fall back to Orodruin's identity (R2c, pièce 4B)",
     MAKEFILE, "--network $(ORO_SANDBOX_NET) --env-file", "--network host --env-file"),
    ("M6610", "the run no longer names the mounted assertion to EREGION_STRATUS_ASSERTION_FILE — "
     "stratus_run_env sees an incomplete federated identity (R2c, pièce 4B)",
     MAKEFILE, "-e EREGION_STRATUS_ASSERTION_FILE=$(ORO_STRATUS_MOUNT)",
     "-e EREGION_STRATUS_ASSERTION_FILE=/wrong/path"),
    ("M6611", "the sandbox proof's freshness is no longer checked — a stale proof arms, so a DROP "
     "rule removed after the last refresh would not be caught (R2c, pièce 3, decision A)",
     ORODRUIN, "    if now() - mtime > SANDBOX_PROOF_MAX_AGE_S:",
     "    if now() - mtime > SANDBOX_PROOF_MAX_AGE_S + 10**9:"),
    ("M6612", "the root service no longer writes the DROP-rule proof — read_sandbox has nothing to "
     "read from the hardened container, the contract can never arm for Stratus (R2c, pièce 3, dec. A)",
     MAIN, "iptables -S DOCKER-USER > /run/eregion-sandbox-rules",
     "iptables -S DOCKER-USER > /dev/null"),
    ("M6613", "the proof timer is not enabled — the proof is written once and goes stale, so the "
     "contract stops arming after SANDBOX_PROOF_MAX_AGE_S (R2c, pièce 3, decision A)",
     MAIN, "systemctl enable --now eregion-stratus-sandbox.timer",
     "systemctl enable --now eregion-stratus-sandbox.service"),
    ("M6614", "the proof is no longer mounted into the contract run — read_sandbox cannot read it "
     "and the contract never arms for Stratus (R2c, pièce 3, decision A)",
     MAKEFILE,
     "--env-file orodruin.env -v $(ORO_SANDBOX_PROOF):$(ORO_SANDBOX_PROOF):ro $(call ORO_MOUNT,orodruin) $(ORO_IMAGE)",
     "--env-file orodruin.env $(call ORO_MOUNT,orodruin) $(ORO_IMAGE)"),
    ("M6615", "the Stratus read credential's fail-closed guard is inverted — an incomplete federated "
     "identity would be used, or a complete one refused, breaking the contract's read as Stratus "
     "(R2c, pièce 2/4B)",
     ORODRUIN, "    if not (client_id and tenant_id and token_file):",
     "    if (client_id and tenant_id and token_file):"),
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
    "M4467": _SANDBOX_MISS,
    "M4468": _SANDBOX_DEST,
    "M4469": _SANDBOX_SRC,
    "M4482": _SANDBOX_POSED,
    "M4483": _SANDBOX_POSED,
    "M4484": _SANDBOX_POSED,
    "M4485": _FED_EMPTY,
    "M4486": _FED_REFUSE,
    "M4487": _FED_AUTH,
    "M4488": _FED_AUTH,
    "M4489": _FED_EXEC,
    "M6606": _KIND_FAULT,
    "M6607": _ASSERT_AUD,
    "M6608": _ASSERT_EMPTY,
    "M6609": _STRATUS_WIRED,
    "M6610": _STRATUS_WIRED,
    "M6611": _SANDBOX_STALE,
    "M6612": _SANDBOX_POSED,
    "M6613": _SANDBOX_POSED,
    "M6614": _SANDBOX_MOUNTED,
    "M6615": _STRATUS_CRED,
}
