"""SLF1b (#976): BlobWriters read in either form the SDK hands it on — a list, or its JSON text —, a text
unreadable, past its bound or not a list of objects setting nothing aside, never raising, and said; the
other reader of a dynamic column (auditd's records) on the SDK's objects too. One mutant per property,
M6715–M6727, measured by tests/unit/test_own_channel_sdk.py."""
OWN = "glorfindel/own_channel.py"
RULES = "glorfindel/detection_rules.py"
_T = "tests/unit/test_own_channel_sdk.py"
_DECODE = ("        try:\n            value = json.loads(value)\n"
           "        except (ValueError, RecursionError):\n            return None\n")

MUTANTS = [
    ("M6715", "the text not decoded: BlobWriters as the SDK hands it on sets nothing aside, the row of the "
     "20/11 a card again (SLF1b)", OWN,
     _DECODE,
     "        return None\n"),
    ("M6716", "an unreadable text raises: the decoding without its net (SLF1b)", OWN,
     _DECODE,
     "        value = json.loads(value)\n"),
    ("M6717", "a text nested too deep raises: RecursionError not caught (SLF1b)", OWN,
     "        except (ValueError, RecursionError):\n            return None\n",
     "        except ValueError:\n            return None\n"),
    ("M6718", "the text unbounded: a BlobWriters text past WRITERS_MAX decoded (SLF1b)", OWN,
     "        if len(value) > WRITERS_MAX:\n            return None\n",
     ""),
    ("M6719", "the bound one short: a text of WRITERS_MAX characters not read (SLF1b)", OWN,
     "        if len(value) > WRITERS_MAX:\n",
     "        if len(value) >= WRITERS_MAX:\n"),
    ("M6720", "a list of other things than objects accepted: its objects set aside (SLF1b)", OWN,
     "    if not isinstance(value, list) or not all(isinstance(e, dict) for e in value):\n",
     "    if not isinstance(value, list):\n"),
    ("M6721", "the unreadable column no longer counted by settle (SLF1b)", OWN,
     "            said[\"unparsed\"] += 1\n",
     ""),
    ("M6722", "the unreadable column no longer said in the rule's status (SLF1b)", RULES,
     "            if own[\"writes\"] or own[\"unread\"] or own[\"unparsed\"]:\n",
     "            if own[\"writes\"] or own[\"unread\"]:\n"),
    ("M6723", "the counter of the unreadable column reset at each pass (SLF1b)", RULES,
     "                unparsed = was[\"own_channel_unparsed\"] + own[\"unparsed\"]\n",
     "                unparsed = own[\"unparsed\"]\n"),
    ("M6724", "the counter of the unreadable column lost from what the console and the snapshot read "
     "(SLF1b)", RULES,
     "            \"own_channel_unparsed\": n(\"unparsed\"),\n",
     "            \"own_channel_unparsed\": 0,\n"),
    ("M6725", "the unreadable column no longer said in the watch's log (SLF1b)", RULES,
     "        if own[\"unparsed\"]:\n            # SLF1b",
     "        if False:\n            # SLF1b"),
    ("M6726", "a reader of a dynamic column brought back to its list-only form: auditd's records as the SDK "
     "hands them on read as none (SLF1b, A11)", "glorfindel/auditd.py",
     "    if isinstance(value, str):\n        try:\n            value = json.loads(value)\n"
     "        except (ValueError, RecursionError):\n            return []\n",
     ""),
    ("M6727", "the console no longer says the rows whose BlobWriters could not be read (SLF1b)",
     "eregion_console/static/glorfindel.js",
     "  return [said, unread, unparsed].filter(Boolean).join(' · ');\n",
     "  return [said, unread].filter(Boolean).join(' · ');\n"),
]
TESTS = {
    "M6715": f"{_T}::test_the_row_of_the_20_11_through_the_sdk_is_set_aside_and_said",
    "M6716": f"{_T}::test_settle_never_raises_on_an_unreadable_column",
    "M6717": f"{_T}::test_settle_never_raises_on_an_unreadable_column",
    "M6718": f"{_T}::test_an_unreadable_column_sets_nothing_aside_never_raises_and_is_said",
    "M6719": f"{_T}::test_the_bound_is_the_text_s_and_a_text_at_it_is_read",
    "M6720": f"{_T}::test_an_unreadable_column_sets_nothing_aside_never_raises_and_is_said",
    "M6721": f"{_T}::test_settle_never_raises_on_an_unreadable_column",
    "M6722": f"{_T}::test_an_unreadable_column_sets_nothing_aside_never_raises_and_is_said",
    "M6723": f"{_T}::test_unparsed_rows_count_on_across_passes_and_writes_keep_them",
    "M6724": f"{_T}::test_an_unreadable_column_sets_nothing_aside_never_raises_and_is_said",
    "M6725": f"{_T}::test_an_unreadable_column_sets_nothing_aside_never_raises_and_is_said",
    "M6726": f"{_T}::test_auditd_s_records_through_the_sdk_are_read_as_text",
    "M6727": f"{_T}::test_the_console_says_the_unparsed_rows_on_the_rule",
}
