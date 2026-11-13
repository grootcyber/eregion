"""CDJ1 (#783): `make imladris-cd-status` shows the last 15 lines of the CD's journal over the last day,
on Imladris's systemd 249 (Ubuntu 22.04) too, where `--since` with `-n` reads forward and stops at the
window's first lines (measured on 13/11: the passes of the day before). M5120–M5124, measured by
tests/unit/test_host_cd.py (the real recipe, its ssh faked, against a fake journalctl of either version)."""
MAKEFILE = "Makefile"
_LAST = "tests/unit/test_host_cd.py::test_cd_status_shows_the_last_fifteen_lines_of_the_day_on_imladris_systemd_too"
_WINDOW = "tests/unit/test_host_cd.py::test_cd_status_reads_its_own_unit_over_the_last_day"

MUTANTS = [
    ("M5120", "the status back to `--since -1d -n 15`: on Imladris's systemd 249 it shows the day's first 15 "
     "lines, the passes of the day before, never the deployment just made (CDJ1)", MAKEFILE,
     'journalctl -u eregion-cd --since -1d --no-pager -o cat 2>/dev/null | tail -n 15 | sed',
     'journalctl -u eregion-cd --since -1d -n 15 --no-pager -o cat 2>/dev/null | sed'),
    ("M5121", "the status keeps the window's oldest 15 lines whatever the version: the latest pass of the CD "
     "never shown (CDJ1)", MAKEFILE,
     '--no-pager -o cat 2>/dev/null | tail -n 15 | sed "s/^/  | /"',
     '--no-pager -o cat 2>/dev/null | head -n 15 | sed "s/^/  | /"'),
    ("M5122", "the status reads the whole journal, not the last day: lines of another week shown as today's "
     "(CDJ1)", MAKEFILE,
     "journalctl -u eregion-cd --since -1d --no-pager", "journalctl -u eregion-cd --no-pager"),
    ("M5123", "the status reads every unit's journal, not the CD's: the host's other lines taken for the CD's "
     "passes (CDJ1)", MAKEFILE,
     "journalctl -u eregion-cd --since -1d --no-pager", "journalctl --since -1d --no-pager"),
    ("M5124", "the read bounded again, by a larger -n before tail: on Imladris's systemd 249 it reads from the "
     "window's start once more, and a day of more than 500 lines hides the latest passes (CDJ1, review)", MAKEFILE,
     "journalctl -u eregion-cd --since -1d --no-pager", "journalctl -u eregion-cd --since -1d -n 500 --no-pager"),
]
TESTS = {
    "M5120": _LAST,
    "M5121": _LAST,
    "M5122": _WINDOW,
    "M5123": _WINDOW,
    "M5124": _WINDOW,
}
