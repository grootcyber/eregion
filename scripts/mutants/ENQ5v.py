"""ENQ5v (#1221): why four reads of the enquiry came back empty at the bench — the one fault of the code, the
vault's listing asked without its window (glorfindel/providers/azure/dossier_reads.py, `jobs_filter`): an
episode captured days later read no job of its own window, and the dossier's ten days of jobs were the
service's default range. M7811–M7813, measured by tests/unit/test_enquiry_reads.py."""
READS = "glorfindel/providers/azure/dossier_reads.py"
_R = "tests/unit/test_enquiry_reads.py"

MUTANTS = [
    ("M7811", "the vault's listing asked without its window: the service's default range, an episode read days "
     "later finds no job of its window — « no backup » where one ran (ENQ5v)", READS,
     "        listed = self._backup_client().backup_jobs.list(parts[-1], parts[4], filter=jobs_filter(start, end))\n",
     "        listed = self._backup_client().backup_jobs.list(parts[-1], parts[4])\n"),
    ("M7812", "the filter's hour on 24 hours where the service reads `hh:mm:ss tt`: an afternoon refused, or read "
     "twelve hours off (ENQ5v)", READS,
     "        return f\"{u:%Y-%m-%d} {(u.hour + 11) % 12 + 1:02d}:{u:%M:%S} {'PM' if u.hour >= 12 else 'AM'}\"\n",
     "        return f\"{u:%Y-%m-%d} {u:%H:%M:%S} {'PM' if u.hour >= 12 else 'AM'}\"\n"),
    ("M7813", "the filter's margin dropped: whatever the service compares its bounds to (a job's start, its end), "
     "a job at the window's edge falls out of the listing (ENQ5v)", READS,
     "    return f\"startTime eq '{at(start - JOBS_FILTER_MARGIN)}' and endTime eq '{at(end + JOBS_FILTER_MARGIN)}'\"\n",
     "    return f\"startTime eq '{at(start)}' and endTime eq '{at(end)}'\"\n"),
]

TESTS = {
    "M7811": f"{_R}::test_an_episode_read_days_later_still_reads_the_vault_s_job_of_its_window "
             f"{_R}::test_the_dossier_s_ten_days_of_jobs_are_asked_whole",
    "M7812": f"{_R}::test_the_vault_s_filter_is_the_service_s_form_in_utc_widened_by_its_margin",
    "M7813": f"{_R}::test_the_vault_s_filter_is_the_service_s_form_in_utc_widened_by_its_margin",
}
