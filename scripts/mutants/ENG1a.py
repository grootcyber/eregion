"""ENG1a (#1184): the product's output in English, surface by surface — the guard, one ceiling per surface
that only comes down, and the first leftovers translated. Each mutant takes a piece back: French back in a
file brought to 0 (the TUI M7621, Annatar's CLI M7622), the ceiling held file by file again, so a split is
refused (M7623), a ceiling raised (M7624), a surface absent from the ceilings let through in French
(M7625), a text read back counted as a debt (M7626), a text read back gone and kept on the list (M7627),
what the model sees counted (M7628), the detector blind to an elision (M7629), a file filed under another
lot's surface (M7630). M7621–M7630, measured by tests/unit/test_french_output.py. No text read back in the
leftovers themselves (none of their texts is matched by a reader): M7626 holds the rule on the product's.
M7623 was, before the review, the store guard's session said in French again (a third case of M7621).

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GUARD = "scripts/french_output.py"
CEILING = "tests/unit/french_ceiling.json"
TUI = "glorfindel/tui.py"
ANNATAR = "annatar/cli.py"

_T = "tests/unit/test_french_output.py::"

MUTANTS = [
    ("M7621", "the TUI's restore refusal back in French, in a file brought to 0 (ENG1a)", TUI,
     'raise ValueError("this card offers no restore")',
     'raise ValueError("cette carte n\'offre pas de restore")'),
    ("M7622", "a hint of `annatar run` back in French, in a file brought to 0 (ENG1a)", ANNATAR,
     '"incomplete: nothing was played."),',
     '"incomplètes : rien n\'a été joué."),'),
    ("M7623", "the ceiling held file by file again: a file that takes what another of its surface gives up "
     "(a split) refused (ENG1a, review)", GUARD,
     "    return (over_ceiling(total, ceiling, counts, files)\n",
     "    return (over_ceiling(total, ceiling, counts, files)\n"
     "            + [f\"{rel}: over its count\" for rel, n in counts.items() if n > files.get(rel, 0)]\n"),
    ("M7624", "a ceiling raised: the surface brought to 0 given room for French again (ENG1a)", CEILING,
     ' "surfaces": {\n',
     ' "surfaces": {\n  "S0": {\n   "ceiling": 1,\n   "files": {}\n  },\n'),
    ("M7625", "a surface absent from the ceilings let through: French in it, unsaid (ENG1a)", GUARD,
     "        if n > ceiling.get(sid, 0):\n",
     "        if n > ceiling.get(sid, n):\n"),
    ("M7626", "COMPROMISE_MARK no longer known as read back: counted as a debt to translate (ENG1a)", GUARD,
     '    ("glorfindel/escalations.py", "Compte peut-être compromis",\n'
     '     "COMPROMISE_MARK: the cards already filed carry it, and are read back by it (ENG1b: both languages)"),\n',
     ""),
    ("M7627", "a text read back, or an English one, that left its file stays on its list, unsaid (ENG1a)", GUARD,
     "            if not reads_french(said) or not any(said in s if is_lines(rel) else said == s for s in texts):\n",
     "            if not reads_french(said):\n"),
    ("M7628", "what the model sees counted: _build_user_message a debt of ENG1e, without its run end to end "
     "(ENG1a)", GUARD,
     '    "glorfindel/agent.py": ("_build_user_message", "_SOURCE_TAGS", "_SYSTEM_PROMPT", "_DECISION_TOOL"),\n',
     '    "glorfindel/agent.py": ("_SOURCE_TAGS", "_SYSTEM_PROMPT", "_DECISION_TOOL"),\n'),
    ("M7629", "the detector blind to an elision: « n'offre » reads English (ENG1a)", GUARD,
     "    return bool(ACCENT.search(text) or ELISION.search(text) or ONLY_FRENCH.search(text)\n",
     "    return bool(ACCENT.search(text) or ONLY_FRENCH.search(text)\n"),
    ("M7630", "a file filed under the vaguest glob: the providers' files under ENG1g's surface (ENG1a)", GUARD,
     "    return max(held)[1] if held else None\n",
     "    return min(held)[1] if held else None\n"),
]

TESTS = {
    "M7621": f"{_T}test_no_product_file_reads_more_french_than_its_ceiling",
    "M7622": f"{_T}test_no_product_file_reads_more_french_than_its_ceiling",
    "M7623": f"{_T}test_a_file_may_take_what_another_of_its_surface_gives_up",
    "M7624": f"{_T}test_a_ceiling_comes_down_with_its_file",
    "M7625": f"{_T}test_a_new_file_never_makes_its_surface_go_up",
    "M7626": f"{_T}test_no_product_file_reads_more_french_than_its_ceiling",
    "M7627": f"{_T}test_a_text_read_back_that_left_its_file_is_said",
    "M7628": f"{_T}test_no_product_file_reads_more_french_than_its_ceiling",
    "M7629": f"{_T}test_a_ceiling_comes_down_with_its_file",
    "M7630": f"{_T}test_no_product_file_reads_more_french_than_its_ceiling",
}
