"""ENG1a (#1184): the product's output in English, surface by surface — the guard, a ratchet that only comes
down, and the first leftovers translated. Each mutant takes a piece back: French back in a file brought to
0 (the TUI M7621, Annatar's CLI M7622, the core M7623), a ceiling raised (M7624), a new file let through in
French (M7625), a text read back counted as a debt (M7626), a text read back gone and kept on the list
(M7627), what the model sees counted (M7628), the detector blind to an elision (M7629), a file filed under
another lot's surface (M7630). M7621–M7630, measured by tests/unit/test_french_output.py. No text read back
in the leftovers themselves (none of their texts is matched by a reader): M7626 holds the rule on the
product's.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GUARD = "scripts/french_output.py"
CEILING = "tests/unit/french_ceiling.json"
TUI = "glorfindel/tui.py"
ANNATAR = "annatar/cli.py"
STORE = "eregion_core/store_guard.py"

_T = "tests/unit/test_french_output.py::"

MUTANTS = [
    ("M7621", "the TUI's restore refusal back in French, in a file brought to 0 (ENG1a)", TUI,
     'raise ValueError("this card offers no restore")',
     'raise ValueError("cette carte n\'offre pas de restore")'),
    ("M7622", "a hint of `annatar run` back in French, in a file brought to 0 (ENG1a)", ANNATAR,
     '"incomplete: nothing was played."),',
     '"incomplètes : rien n\'a été joué."),'),
    ("M7623", "the guard of the operator's stores says its session in French again (ENG1a)", STORE,
     'return f"an agent session ({SESSION_VAR})"',
     'return f"une session d\'agent ({SESSION_VAR})"'),
    ("M7624", "a ceiling raised: a file brought to 0 given room for French again (ENG1a)", CEILING,
     ' "surfaces": {\n',
     ' "surfaces": {\n  "S0": {\n   "glorfindel/tui.py": 1\n  },\n'),
    ("M7625", "a file absent from the ceilings is let through: a new file, or one at 0, in French (ENG1a)", GUARD,
     "if n > ceiling.get(rel, 0)]",
     "if n > ceiling.get(rel, n)]"),
    ("M7626", "COMPROMISE_MARK no longer known as read back: counted as a debt to translate (ENG1a)", GUARD,
     '    ("glorfindel/escalations.py", "Compte peut-être compromis",\n'
     '     "COMPROMISE_MARK: the cards already filed carry it, and are read back by it (ENG1b: both languages)"),\n',
     ""),
    ("M7627", "a text read back that left its file stays on the list, unsaid (ENG1a)", GUARD,
     "        if not reads_french(said) or not any(said in s if is_lines(rel) else said == s for s in texts):\n",
     "        if not reads_french(said):\n"),
    ("M7628", "what the model sees counted: _build_user_message a debt of ENG1e, without its run end to end "
     "(ENG1a)", GUARD,
     '    "glorfindel/agent.py": ("_build_user_message", "_SYSTEM_PROMPT", "_DECISION_TOOL"),\n',
     '    "glorfindel/agent.py": ("_SYSTEM_PROMPT", "_DECISION_TOOL"),\n'),
    ("M7629", "the detector blind to an elision: « n'offre » reads English (ENG1a)", GUARD,
     "    return bool(ACCENT.search(text) or ELISION.search(text) or ONLY_FRENCH.search(text)\n",
     "    return bool(ACCENT.search(text) or ONLY_FRENCH.search(text)\n"),
    ("M7630", "a file filed under the vaguest glob: an identity provider's file under ENG1n's surface (ENG1a)",
     GUARD,
     "    return max(held)[1] if held else None\n",
     "    return min(held)[1] if held else None\n"),
]

TESTS = {
    "M7621": f"{_T}test_no_product_file_reads_more_french_than_its_ceiling",
    "M7622": f"{_T}test_no_product_file_reads_more_french_than_its_ceiling",
    "M7623": f"{_T}test_no_product_file_reads_more_french_than_its_ceiling",
    "M7624": f"{_T}test_a_ceiling_comes_down_with_its_file",
    "M7625": f"{_T}test_a_new_file_or_one_brought_to_0_must_stay_at_0",
    "M7626": f"{_T}test_no_product_file_reads_more_french_than_its_ceiling",
    "M7627": f"{_T}test_a_text_read_back_that_left_its_file_is_said",
    "M7628": f"{_T}test_no_product_file_reads_more_french_than_its_ceiling",
    "M7629": f"{_T}test_a_ceiling_comes_down_with_its_file",
    "M7630": f"{_T}test_each_file_is_under_its_own_surface_and_each_surface_has_its_lot",
}
