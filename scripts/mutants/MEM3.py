"""MEM3 (#1029): the analysis index on a SQLite table, no ChromaDB — its rows in the order they were
first put in, as chromadb gave them; never a file that holds Glorfindel's memory (IA1); a row that
cannot be read never an empty run; the import of the old index never writes in the copy it reads; an
old index never imported, said. M7035–M7039, measured by tests/unit/test_analysis_index.py."""
INDEX = "analysis/run_index.py"
REPORT = "analysis/campaign_report.py"
IMPORT = "analysis/index_import.py"
_T = "tests/unit/test_analysis_index.py::"

MUTANTS = [
    ("M7035", "the rows read in the order of their ids, not the order they were first put in: a technique "
              "with more than fifty runs brings back other earlier runs than chromadb did (MEM3)", INDEX,
     '        sql += " ORDER BY seq"\n',
     '        sql += " ORDER BY run_id"\n'),
    ("M7036", "a file that holds Glorfindel's memory opened as the analysis index: the report reads and "
              "writes the defender's memory, from a copy outside ~/.glorfindel (IA1, MEM3)", INDEX,
     "        if separation.GLORFINDEL_COLLECTION in tables:   # IA1: the defender's memory, elsewhere\n",
     "        if False:\n"),
    ("M7037", "a row that cannot be read taken as a run: an empty one, or another run's facts, comes back "
              "as an earlier run — or breaks the report (MEM3)", REPORT,
     '        if not isinstance(raw, dict) or not raw.get("run_id") or raw["run_id"] != meta.get("run_id", raw["run_id"]):\n'
     "            return None\n",
     ""),
    ("M7038", "the import writes its table in the folder of the copy it reads (MEM3)", IMPORT,
     "    if _inside(dest, source):\n",
     "    if False:\n"),
    ("M7039", "an old index never imported read as an empty one, unsaid: its runs no longer come back, and "
              "nothing says why (MEM3)", REPORT,
     "    return NOT_IMPORTED.format(old=old)\n",
     '    return ""\n'),
]
TESTS = {
    "M7035": (_T + "test_the_rows_come_back_in_the_order_they_were_first_put_in_as_chromadb_gave_them "
              + _T + "test_an_index_of_before_migrated_gives_the_same_rows_in_the_same_order"),
    "M7036": _T + "test_the_index_never_opens_a_file_that_holds_glorfindel_s_memory_wherever_it_lies",
    "M7037": _T + "test_a_row_that_cannot_be_read_is_never_an_empty_run",
    "M7038": _T + "test_the_import_never_writes_in_the_copy_it_reads",
    "M7039": (_T + "test_an_old_index_never_imported_is_said_never_read_as_empty "
              + _T + "test_the_index_command_waits_for_the_import"),
}
