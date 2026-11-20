"""ROW1 (#1002): the identity of an aggregated row leaves out the JSON text of a dynamic column — an array
or an object, read by `own_channel.json_of` (bounded, never raising) —, keeps its grouping keys and every
other text, and leaves a row with its instant untouched; the shipped rules' identities unchanged.
M6910–M6919, measured by tests/unit/test_row_identity_sdk.py."""
RULES = "glorfindel/detection_rules.py"
_T = "tests/unit/test_row_identity_sdk.py::"
_READ = "    return isinstance(own_channel.json_of(value), (list, dict))\n"

MUTANTS = [
    ("M6910", "the JSON text kept in the identity: a make_set that grows makes a new card at each value more "
     "(ROW1)", RULES,
     "        if isinstance(v, str) and v and not _looks_numeric(v) and not _dynamic_text(v)\n",
     "        if isinstance(v, str) and v and not _looks_numeric(v)\n"),
    ("M6911", "a JSON scalar text left out: an account written \"true\" or \"carol\" no longer tells two rows "
     "apart (ROW1)", RULES,
     _READ,
     "    return own_channel.json_of(value) is not None\n"),
    ("M6912", "a plain text left out by its first character: an account \"[alice\" taken for a JSON array "
     "(ROW1)", RULES,
     _READ,
     "    return value.lstrip().startswith((\"[\", \"{\"))\n"),
    ("M6913", "a grouping key left out: the identity narrowed to the VM's columns, another address on the "
     "same VM taken for the first (ROW1)", RULES,
     "        f\"{k}={v}\" for k, v in row.items()\n        if isinstance(v, str)",
     "        f\"{k}={v}\" for k, v in row.items()\n        if k in (\"Computer\", \"_ResourceId\") and isinstance(v, str)"),
    ("M6914", "the reading unbounded: a JSON text past WRITERS_MAX decoded (ROW1)", RULES,
     _READ,
     "    try:\n        return isinstance(json.loads(value), (list, dict))\n"
     "    except (ValueError, RecursionError):\n        return False\n"),
    ("M6915", "an unreadable value raises: the identity read without its net, a plain text out of the poll "
     "(ROW1)", RULES,
     _READ,
     "    return isinstance(json.loads(value), (list, dict)) if len(value) <= own_channel.WRITERS_MAX else False\n"),
    ("M6916", "a text nested too deep raises: RecursionError not caught by the identity (ROW1)", RULES,
     _READ,
     "    try:\n        return len(value) <= own_channel.WRITERS_MAX and isinstance(json.loads(value), (list, dict))\n"
     "    except ValueError:\n        return False\n"),
    ("M6917", "an object kept in the identity: a pack or a make_bag that changes makes a new card (ROW1)",
     RULES,
     _READ,
     "    return isinstance(own_channel.json_of(value), list)\n"),
    ("M6918", "a row with its instant touched: read as an aggregated row when it carries a JSON column, an "
     "audit event's identity no longer its instant (ROW1)", RULES,
     "    ts = row.get(\"TimeGenerated\")\n    if ts:\n",
     "    ts = row.get(\"TimeGenerated\")\n"
     "    if ts and not any(isinstance(v, str) and _dynamic_text(v) for v in row.values()):\n"),
    ("M6919", "an empty set kept in the identity: a make_set empty at the first pass, filled at the next, a "
     "new card (ROW1)", RULES,
     _READ,
     "    decoded = own_channel.json_of(value)\n    return isinstance(decoded, (list, dict)) and bool(decoded)\n"),
]
TESTS = {
    "M6910": _T + "test_a_grown_set_makes_no_new_card",
    "M6911": _T + "test_a_plain_text_that_changes_is_still_a_new_identity",
    "M6912": _T + "test_a_plain_text_that_changes_is_still_a_new_identity",
    "M6913": _T + "test_another_address_still_makes_its_card",
    "M6914": _T + "test_a_text_past_the_bound_or_unreadable_stays_and_never_raises",
    "M6915": _T + "test_a_plain_text_that_changes_is_still_a_new_identity",
    "M6916": _T + "test_a_text_past_the_bound_or_unreadable_stays_and_never_raises",
    "M6917": _T + "test_the_identity_is_the_same_whether_the_set_is_a_list_or_its_json_text",
    "M6918": _T + "test_a_row_with_its_instant_is_untouched",
    "M6919": _T + "test_the_identity_is_the_same_whether_the_set_is_a_list_or_its_json_text",
}
