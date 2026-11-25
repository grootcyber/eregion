"""SUBN1 (#1190): the watch reads the readable name of each subscription it sees, for the console. Each
mutant takes a guard back: a subscription segment that is no GUID taken from a resource id (M7661), a
failed read written as a subscription not read yet (M7662), an error's URL or GUID shown (M7663), a
control or format character of the name kept (M7664), a name never cut (M7665), a file of another form
handed to the console as it is (M7666), every subscription read again at every pass (M7667), the route
without the field (M7668), a read in dry-run (M7669), the raw id served as the key (M7670). After the
review (25/11): a subscription seen again after it left kept as read, no entry until the 6 h round
(M7648, outside the lot's range: the only number free). PER_PASS has no mutant: no number left.
M7661–M7670 and M7648, measured by tests/unit/test_subscription_names.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
SN = "glorfindel/subscription_names.py"
TASKS = "glorfindel/watch/name_tasks.py"
WF = "eregion_console/watch_fields.py"

_T = "tests/unit/test_subscription_names.py::"

MUTANTS = [
    ("M7661", "a subscription segment that is no GUID taken: a text of Log Analytics in ARM's URL (SUBN1)", SN,
     "    return key if _SUB_ID.match(key) else None", "    return key or None"),
    ("M7662", "a read that failed written as a subscription not read yet: no error said (SUBN1)", SN,
     '        return {"name": None, "error": _printable(short_error(exc))[:ERROR_MAX]}',
     '        return {"name": None, "error": None}'),
    ("M7663", "an error's text not masked: ARM's URL and a GUID shown in the console (SUBN1)", SN,
     '"error": _printable(short_error(exc))[:ERROR_MAX]}', '"error": _printable(str(exc))[:ERROR_MAX]}'),
    ("M7664", "the name's control and format characters kept: a line break, a direction mark (SUBN1)", SN,
     'unicodedata.category(c)[0] != "C" and c not in _LINE_BREAKS)', "True)"),
    ("M7665", "the name never cut: a text of any length in the console (SUBN1)", SN,
     '.strip()[:NAME_MAX].strip()', ".strip()"),
    ("M7666", "a file of another form handed to the console as it is (SUBN1)", SN,
     "        field = _field_of(load(path))", "        field = load(path) or None"),
    ("M7667", "every subscription read again at every pass of the watch, not every 6 h (SUBN1)", SN,
     "now - self._round_at >= EVERY_S:", "now - self._round_at >= 0:"),
    ("M7668", "/api/watch/status without the field: the console keeps the masked id (SUBN1)", WF,
     "    return {**log_freshness(), **subscription_names()}", "    return {**log_freshness()}"),
    ("M7669", "the names read in dry-run: a call to Azure (SUBN1)", TASKS,
     "        if self.dry_run:\n            return\n        try:", "        try:"),
    ("M7670", "the raw subscription id served as the field's key (SUBN1)", SN,
     "        out[mask(key)] = {", "        out[key] = {"),
    ("M7648", "a subscription seen again after it left kept as read: no entry served until the 6 h round (SUBN1 review)",
     SN, "        self._read &= set(keys)\n", ""),
]

TESTS = {
    "M7661": f"{_T}test_an_id_that_is_not_a_guid_is_never_taken",
    "M7662": f"{_T}test_a_name_read_a_refusal_and_a_network_error",
    "M7663": f"{_T}test_a_name_read_a_refusal_and_a_network_error",
    "M7664": f"{_T}test_the_name_is_cleaned_and_cut",
    "M7665": f"{_T}test_the_name_is_cleaned_and_cut",
    "M7666": f"{_T}test_a_file_that_cannot_be_read_leaves_the_field_out",
    "M7667": f"{_T}test_all_are_read_at_the_start_then_every_6_hours_and_a_new_one_at_once",
    "M7668": f"{_T}test_the_route_carries_the_field_and_leaves_it_out_when_unreadable",
    "M7669": f"{_T}test_the_watch_reads_in_a_thread_and_never_in_dry_run",
    "M7670": f"{_T}test_the_file_is_written_at_once_and_the_key_is_masked_no_raw_id_in_the_field",
    "M7648": f"{_T}test_a_subscription_no_longer_seen_leaves_the_file_and_is_read_again_when_it_comes_back",
}
