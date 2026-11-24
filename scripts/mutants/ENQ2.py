"""ENQ2 (#1064): the catalogue of the enquiry's reads, out of glorfindel/agent.py
(glorfindel/enquiry/catalog.py, glorfindel/enquiry/fixed.py). M7095–M7099: a Linux read said
applicable where its source does not exist; a failure rendered empty; a value out of its literal; the
`_ResourceId` bound taken out of a query; the message to the model changed. Measured by
tests/unit/test_enquiry_catalog.py."""
CATALOG = "glorfindel/enquiry/catalog.py"
FIXED = "glorfindel/enquiry/fixed.py"
_T = "tests/unit/test_enquiry_catalog.py"

MUTANTS = [
    ("M7095", "a Linux read said applicable where its source does not exist: the Process counter read under "
     "Linux (ENQ2)", CATALOG,
     "MappingProxyType({LINUX: _PROCESS_LINUX, WINDOWS: READS_HERE})),          # if the DCR collects Process\n",
     "MappingProxyType({LINUX: READS_HERE, WINDOWS: READS_HERE})),          # if the DCR collects Process\n"),
    ("M7096", "a failed read rendered empty: the guard of decide no longer sees the gap (ENQ2, G2)", CATALOG,
     "        return Reading(read.id, ECHEC, why=",
     "        return Reading(read.id, VIDE, why="),
    ("M7097", "a value of the line out of its KQL literal: the VM's id and the address written bare (ENQ2, "
     "SEC4c)", FIXED,
     "            return kql.literal(check(raw_value))\n",
     "            return check(raw_value)\n"),
    ("M7098", "the _ResourceId bound taken out of a read: it reads every VM of the workspace (ENQ2, SEC-I)",
     CATALOG,
     '| where TimeGenerated > ago(10m)\n| where _ResourceId =~ {vm}\n| where ObjectName in ("Logical Disk"',
     '| where TimeGenerated > ago(10m)\n| where ObjectName in ("Logical Disk"'),
    ("M7099", "the message to the model changed: a read that said nothing shown as its state (ENQ2)", CATALOG,
     "        return self.rows if self.etat == LIGNES else []\n",
     '        return self.rows if self.etat == LIGNES else [{"etat": self.etat, "pourquoi": self.why}]\n'),
]

TESTS = {mid: _T for mid in ("M7095", "M7096", "M7097", "M7098", "M7099")}
