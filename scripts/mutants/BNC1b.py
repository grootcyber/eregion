"""BNC1b (#724): the bench's preflight, corrected on what the bench of 11/11 measured — az's warning
is not its error, another project's « watcher » is no watch of Eregion, the recovery point asked by
the full container of the item's id. M4800–M4806, measured by tests/unit/test_bench_preflight.py."""
PRE = "scripts/bench_preflight.py"
SHARED = "scripts/bench_shared.py"
_P = "tests/unit/test_bench_preflight.py"

MUTANTS = [
    ("M4800", "az's `WARNING:` taken for the error: the point said « illisible (WARNING: ) », the true "
     "error hidden (BNC1b, the defect back)", SHARED,
     'WARNING_PREFIXES = ("Warning:", "WARNING:")\n',
     'WARNING_PREFIXES = ("Warning:",)\n'),
    ("M4801", "the indented lines of az's warning said as the error (BNC1b)", SHARED,
     "            if in_warning and ln[:1].isspace():\n",
     "            if False:\n"),
    ("M4802", "a command that says only warnings answered by an empty line (BNC1b)", SHARED,
     '            return scrub(f"code {self.rc}, rien que des avertissements" + (f" : {first}"[:200] if first else ""))\n',
     "            return scrub(warnings[0])\n"),
    ("M4803", "any container whose name holds « watch » read as a watch of Eregion: another project's "
     "« …-watcher » stops the run (BNC1b, the defect back)", PRE,
     "    watches = eregion_watches(res.out)\n",
     '    watches = [n.split("\\t")[0] for n in res.out.splitlines() if "watch" in n.lower()]\n'),
    ("M4804", "the compose service `watch` of any image read as Eregion's: another project's `watch` "
     "service stops the run (BNC1b)", PRE,
     "        if WATCH_NAME.fullmatch(name) or (service.strip() == WATCH_SERVICE\n"
     "                                          and _image_name(image.strip()) == WATCH_IMAGE):\n",
     "        if WATCH_NAME.fullmatch(name) or service.strip() == WATCH_SERVICE:\n"),
    ("M4805", "the three-segment containerName passed to `-c` and the item's name to `-i`: az refuses "
     "it (BMSUserErrorContainerNameIncorrectFormat), the point is never read (BNC1b, the defect back)", PRE,
     '    return ["backup", "recoverypoint", "list", "-g", v_rg, "-v", vault, "-c", found.group(1),\n'
     '            "-i", found.group(2), "--backup-management-type", "AzureIaasVM"]\n',
     '    return ["backup", "recoverypoint", "list", "-g", v_rg, "-v", vault, "-c",\n'
     '            str((item.get("properties") or {}).get("containerName") or ""),\n'
     '            "-i", str(item.get("name") or ""), "--backup-management-type", "AzureIaasVM"]\n'),
    ("M4806", "an item's id without its container falls back to the item's own fields: a form not "
     "measured tried on the vault, instead of an unreadable ✗ (BNC1b)", PRE,
     '        raise RuntimeError("l\'id de l\'item ne porte pas son conteneur et son nom "\n'
     '                           "(/protectionContainers/…/protectedItems/…)")\n',
     '        found = re.search(r"(.+);(.+)", "IaasVMContainer;" + str((item.get("properties") or {})\n'
     '                          .get("containerName") or "") + ";" + str(item.get("name") or ""))\n'),
]
TESTS = {
    "M4800": f"{_P}::test_az_s_warning_is_not_the_error_said",
    "M4801": f"{_P}::test_az_s_warning_and_its_indented_lines_are_skipped",
    "M4802": f"{_P}::test_only_warnings_are_said_so_never_an_empty_line",
    "M4803": f"{_P}::test_a_foreign_watcher_on_the_workstation_is_no_watch_of_eregion",
    "M4804": f"{_P}::test_a_foreign_watcher_on_the_workstation_is_no_watch_of_eregion",
    "M4805": f"{_P}::test_the_point_is_asked_by_the_full_container_of_the_item_s_id",
    "M4806": f"{_P}::test_an_item_without_its_container_or_name_is_unreadable_never_a_fallback",
}
