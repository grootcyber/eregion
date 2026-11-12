"""PAIR1 (#736): a pair's secret read on its application and on its service principal, its
certificates too, the nearest end deciding, an unread object never read as « aucun ». M4824–M4827,
measured by tests/unit/test_credential_expiry.py."""
EXPIRY = "scripts/credential_expiry.py"
_T = "tests/unit/test_credential_expiry.py"

MUTANTS = [
    ("M4824", "the application read alone: a secret on the service principal (the console's, on the bench "
     "of 12/11) said « aucun », its expiry never seen (PAIR1, the defect back)", EXPIRY,
     'OBJECTS = (("app", "son application"), ("sp", "son principal de service"))\n',
     'OBJECTS = (("app", "son application"),)\n'),
    ("M4825", "an object az can't read taken for an empty one: « aucun secret » said of a pair whose "
     "service principal was not read, the failure gone (PAIR1)", EXPIRY,
     "                lines.append(f\"✗ {name} : date de fin illisible sur {where} ({_GUID.sub('<id>', str(e))})\")\n"
     "                unread.append(where)\n"
     "                broken = True\n",
     "                continue\n"),
    ("M4826", "the dates of the two objects not sorted together: the application's first date decides, "
     "a nearer one on the service principal is not said (PAIR1)", EXPIRY,
     "        found.sort(key=lambda c: c.end)\n",
     "        found = found\n"),
    ("M4827", "the certificates (`keyCredentials`) not read: a pair held by a certificate said « aucun », "
     "a certificate's end never seen (PAIR1)", EXPIRY,
     'KINDS = (("secrets", "secret", ""), ("certificates", "certificat", " --cert"))\n',
     'KINDS = (("secrets", "secret", ""),)\n'),
]
TESTS = {
    "M4824": f"{_T}::test_a_secret_on_the_service_principal_only_is_seen_with_its_days_left",
    "M4825": f"{_T}::test_an_object_az_can_t_read_is_said_never_read_as_none",
    "M4826": f"{_T}::test_on_both_objects_the_nearest_end_decides_whichever_holds_it",
    "M4827": f"{_T}::test_a_certificate_is_read_too",
}
