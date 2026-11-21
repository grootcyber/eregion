"""ORG1 (#1003, ORO_RUN_GOTHMOG): the Orodruin contract's Stratus guarantees (the dedicated
identity's closed role, the sandbox that blocks the IMDS) gate ONLY an arming for a Stratus run.
Found at the bench (G1): ORO_RUN_GOTHMOG mounts neither the federated assertion nor the sandbox
proof, so once EREGION_STRATUS_SUBSCRIPTION was set in orodruin.env, every arming judged the two
guarantees and Gothmog/Annatar-VM/the drill/orodruin-check turned passive though they run no
Stratus. The fix scopes the guarantees to `for_stratus`, with a net in the executor so the scoping
cannot fail open: a Stratus phase refuses a session not armed with them. One mutant per property,
M6875–M6889, measured by tests/unit/test_orodruin.py and tests/unit/test_annatar_stratus.py.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et
TESTS (ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
ORODRUIN = "eregion_core/orodruin.py"
ENGINE = "annatar/runner/engine.py"
STRATUS_HOST = "annatar/executors/stratus_host.py"

_TO = "tests/unit/test_orodruin.py"
_TAS = "tests/unit/test_annatar_stratus.py"

_GATE = f"{_TO}::test_the_stratus_guarantees_gate_only_an_arming_for_stratus"
_DERIVED = f"{_TO}::test_the_base_set_is_derived_from_the_current_readers"
_JUDGES = f"{_TO}::test_arm_judges_the_stratus_guarantees_only_for_stratus"
_MARKS = f"{_TO}::test_arm_for_stratus_marks_the_session_when_the_guarantees_hold"
_BARE = f"{_TO}::test_a_session_built_without_the_flag_is_not_for_stratus"
_REFUSE = f"{_TAS}::test_the_executor_refuses_a_phase_from_a_base_contract_session"
_MISSING = f"{_TAS}::test_the_executor_refuses_a_session_missing_the_flag"
_ENGINE = f"{_TAS}::test_the_engine_arms_for_stratus_only_for_a_stratus_scenario"

MUTANTS = [
    ("M6875", "the sandbox dropped from the Stratus guarantees: a base arming would judge it (ORG1)",
     ORODRUIN, 'STRATUS_GUARANTEES = ("stratus", "sandbox")', 'STRATUS_GUARANTEES = ("stratus",)'),
    ("M6876", "the closed role dropped from the Stratus guarantees: a base arming would judge it (ORG1)",
     ORODRUIN, 'STRATUS_GUARANTEES = ("stratus", "sandbox")', 'STRATUS_GUARANTEES = ("sandbox",)'),
    ("M6877", "the default check always judges the guarantees — Gothmog turns passive (ORG1)",
     ORODRUIN, "readers = READERS if for_stratus else {k: v",
     "readers = READERS if True else {k: v"),
    ("M6878", "a Stratus check never judges the guarantees — the closed role unproven (ORG1)",
     ORODRUIN, "= READERS if for_stratus else", "= READERS if False else"),
    ("M6879", "the base set keeps only the guarantees, dropping the four base readers (ORG1)",
     ORODRUIN, "if k not in STRATUS_GUARANTEES}", "if k in STRATUS_GUARANTEES}"),
    ("M6880", "check defaults to for_stratus: the base contract judges the guarantees (ORG1)",
     ORODRUIN, "for_stratus: bool = False) -> Verdict:", "for_stratus: bool = True) -> Verdict:"),
    ("M6881", "arm defaults to for_stratus: Gothmog's arming judges the guarantees (ORG1)",
     ORODRUIN, "for_stratus: bool = False) -> tuple[Verdict, Session | None]:",
     "for_stratus: bool = True) -> tuple[Verdict, Session | None]:"),
    ("M6882", "arm always checks the base contract, ignoring a Stratus arming's flag (ORG1)",
     ORODRUIN, "check(for_stratus=for_stratus)", "check(for_stratus=False)"),
    ("M6883", "the session is never marked for_stratus: every Stratus phase refused (ORG1)",
     ORODRUIN, "\n                            for_stratus=for_stratus)",
     "\n                            for_stratus=False)"),
    ("M6884", "the Session field defaults to for_stratus: a bare session fails open (ORG1)",
     ORODRUIN, "    for_stratus: bool = False\n", "    for_stratus: bool = True\n"),
    ("M6885", "the executor net inverted: a base session runs, a Stratus one is refused (ORG1)",
     STRATUS_HOST, 'if not getattr(self._session, "for_stratus", False):',
     'if getattr(self._session, "for_stratus", False):'),
    ("M6886", "the net's getattr defaults to True: a session missing the flag fails open (ORG1)",
     STRATUS_HOST, 'if not getattr(self._session, "for_stratus", False):',
     'if not getattr(self._session, "for_stratus", True):'),
    ("M6887", "the engine never arms for Stratus: a Stratus run armed on the base contract (ORG1)",
     ENGINE, 'for_stratus=scenario.engine == "stratus")', "for_stratus=False)"),
    ("M6888", "the engine's discriminator inverted: VM runs for_stratus, Stratus runs not (ORG1)",
     ENGINE, 'for_stratus=scenario.engine == "stratus")',
     'for_stratus=scenario.engine != "stratus")'),
    ("M6889", "a Stratus arming trusts a supplied base verdict instead of judging the guarantees (ORG1)",
     ORODRUIN, "    if for_stratus or verdict is None:", "    if verdict is None:"),
]

TESTS = {
    "M6875": _GATE,
    "M6876": _GATE,
    "M6877": _GATE,
    "M6878": _GATE,
    "M6879": _DERIVED,
    "M6880": _GATE,
    "M6881": _JUDGES,
    "M6882": _JUDGES,
    "M6883": _MARKS,
    "M6884": _BARE,
    "M6885": _REFUSE,
    "M6886": _MISSING,
    "M6887": _ENGINE,
    "M6888": _ENGINE,
    "M6889": f"{_TO}::test_a_supplied_base_verdict_cannot_mark_a_stratus_session",
}
