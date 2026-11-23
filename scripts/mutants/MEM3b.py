"""MEM3b (#1052): the suites of MEM3's review — a file of ChromaDB (the old index, or a copy of Glorfindel's
memory) never opened as the analysis index; nothing made in the copy the import reads, its temporary
directory in it; the import of another copy never silences the note on the old index beside the table.
M7071–M7074, measured by tests/unit/test_analysis_index.py. The fourth point of the lot (the order in the
table after a report wrote in it, said in docs/analysis.md) is documentation: no mutant — M7073 and
M7074 both measure the third, at its two ends (the table, the note)."""
INDEX = "analysis/run_index.py"
REPORT = "analysis/campaign_report.py"
IMPORT = "analysis/index_import.py"
_T = "tests/unit/test_analysis_index.py::"

MUTANTS = [
    ("M7071", "a file of ChromaDB opened as the analysis index: the table and the imports written in a "
              "chroma.sqlite3 — the old index's own, or a copy of Glorfindel's memory (MEM3b)", INDEX,
     "            if _tables(conn) & CHROMA_TABLES:   # MEM3b: a chroma.sqlite3 — the old index, or Glorfindel's memory\n",
     "            if False:\n"),
    ("M7072", "the import's working folder made in the copy it reads, the temporary directory in it — "
              "refused only once made (MEM3b)", IMPORT,
     "    if _inside(Path(tempfile.gettempdir()), source):   # MEM3b: before the working folder is made, in it\n",
     "    if False:\n"),
    ("M7073", "imported() without the source: any import recorded counts as the old index's, the import "
              "of another copy silences the note (MEM3b)", INDEX,
     "        return any(_same(s, source) for s in sources)\n",
     "        return bool(sources)\n"),
    ("M7074", "the note silenced by a table that holds rows: rows a report wrote, or the import of another "
              "copy, read as the old index imported (MEM3b)", REPORT,
     "    if (old := run_index.legacy(p)) is None or _collection(p).imported(old):\n",
     "    if (old := run_index.legacy(p)) is None or _collection(p).count() > 0:\n"),
]
TESTS = {
    "M7071": _T + "test_the_index_never_opens_a_file_of_chromadb_as_the_table",
    "M7072": _T + "test_a_temporary_directory_in_the_copy_is_refused_before_anything_is_made_in_it",
    "M7073": _T + "test_the_note_names_the_old_index_until_that_one_is_imported",
    "M7074": _T + "test_the_note_names_the_old_index_until_that_one_is_imported",
}
