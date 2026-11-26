"""ENQ5v (#1221): why four reads of the enquiry came back empty at the bench — the one fault of the code, the
vault's listing asked without its window (glorfindel/providers/azure/dossier_reads.py, `jobs_filter`): an
episode captured days later read no job of its own window, and the dossier's ten days of jobs were the
service's default range. From the review: the upper bound widened by a day, never past the moment of the read,
whatever the service compares its bounds to. M7811–M7815, measured by tests/unit/test_enquiry_reads.py."""
READS = "glorfindel/providers/azure/dossier_reads.py"
_R = "tests/unit/test_enquiry_reads.py"
_FORM = f"{_R}::test_the_vault_s_filter_is_the_service_s_form_in_utc_widened_by_its_margin"

MUTANTS = [
    ("M7811", "the vault's listing asked without its window: the service's default range, an episode read days "
     "later finds no job of its window — « no backup » where one ran (ENQ5v)", READS,
     "        listed = self._backup_client().backup_jobs.list(parts[-1], parts[4], filter=jobs_filter(start, end, now))\n",
     "        listed = self._backup_client().backup_jobs.list(parts[-1], parts[4])\n"),
    ("M7812", "the filter's hour on 24 hours where the service reads `hh:mm:ss tt`: an afternoon refused, or read "
     "twelve hours off (ENQ5v)", READS,
     "        return f\"{u:%Y-%m-%d} {(u.hour + 11) % 12 + 1:02d}:{u:%M:%S} {'PM' if u.hour >= 12 else 'AM'}\"\n",
     "        return f\"{u:%Y-%m-%d} {u:%H:%M:%S} {'PM' if u.hour >= 12 else 'AM'}\"\n"),
    ("M7813", "the filter's upper bound not widened: if the service compares it to a job's end, a long backup "
     "started before T falls out of the listing (ENQ5v, the review)", READS,
     "    hi = utc(end) + JOBS_FILTER_AHEAD\n",
     "    hi = utc(end)\n"),
    ("M7814", "the filter's upper bound past the moment of the read: the service asked a range into the future "
     "(ENQ5v, the review)", READS,
     "        hi = max(utc(end), min(hi, utc(now)))\n",
     "        hi = max(utc(end), hi)\n"),
    ("M7815", "the filter's lower margin dropped: a job at the window's start, under a comparison the service "
     "does not document, falls out (ENQ5v)", READS,
     "    return f\"startTime eq '{at(start - JOBS_FILTER_MARGIN)}' and endTime eq '{at(hi)}'\"\n",
     "    return f\"startTime eq '{at(start)}' and endTime eq '{at(hi)}'\"\n"),
]

TESTS = {
    "M7811": f"{_R}::test_an_episode_read_days_later_still_reads_the_vault_s_job_of_its_window "
             f"{_R}::test_the_dossier_s_ten_days_of_jobs_are_asked_whole",
    "M7812": _FORM,
    "M7813": f"{_R}::test_a_long_backup_still_listed_if_the_service_compares_the_end {_FORM}",
    "M7814": _FORM,
    "M7815": _FORM,
}
