"""CFG2 (#1128): the excluded VM made visible (glorfindel/exclusions.py, glorfindel/audit.py,
glorfindel/config.py, eregion_console/static/glorfindel.js). M7246–M7252: the band absent under a pattern; a
partial exclusion read as a total one; the band that says « every rule » while a rule written for the VM still
watches it; the audit that counts « exclue » a rule outside auto_apply; the audit line of an excluded VM left
green; a reason of two lines read; the reason written raw on the card. Measured by
tests/unit/test_exclusion_visible.py (and tests/unit/test_console_escaping.py for the last one)."""
EXC = "glorfindel/exclusions.py"
AUD = "glorfindel/audit.py"
_T = "tests/unit/test_exclusion_visible.py"

MUTANTS = [
    ("M7246", "the band absent under a pattern: only an entry naming the VM exactly takes it (CFG2)", EXC,
     "    entries = [e for e in getattr(cfg, \"exceptions\", None) or [] if e.matches(vm_name)]\n",
     "    entries = [e for e in getattr(cfg, \"exceptions\", None) or [] if e.asset_pattern.lower() == vm_name.lower()]\n"),
    ("M7247", "a partial exclusion read as a total one: the card says EXCLUDED from every rule (CFG2)", EXC,
     "        \"all\": any(e.exclude_all for e in entries),\n", "        \"all\": True,\n"),
    ("M7248", "the band says no rule still watches the VM while one written for it does (CFG2)", EXC,
     "    if own:\n        parts.append(", "    if False:\n        parts.append("),
    ("M7249", "the audit counts « exclue » a rule written for the VM, outside auto_apply: it still watches it (CFG2)",
     AUD, "        elif is_excluded is not None and getattr(r, \"auto_apply\", False) and is_excluded(vm, r.name):\n",
     "        elif is_excluded is not None and is_excluded(vm, r.name):\n"),
    ("M7250", "the audit line of an excluded VM left green, without its reason (CFG2)", AUD,
     "    if not weak and not excluded:\n", "    if not weak:\n"),
    ("M7251", "a reason of two lines, or with a control character, read: the file no longer refused (CFG2)",
     "glorfindel/config.py",
     "    if any(unicodedata.category(c) in (\"Cc\", \"Zl\", \"Zp\") for c in reason):\n", "    if False:\n"),
    ("M7252", "the reason written raw on the card of an excluded VM (CFG2, #254)",
     "eregion_console/static/glorfindel.js",
     "${_attr(x.said)}</div>`;", "${x.said}</div>`;"),
]

# The review of CFG2: M7271 — a rule with no resource id counted as watching the VM by its asset's name.
MUTANTS += [
    ("M7271", "a rule written for a VM but without a resource id said to still watch it, by its asset's name: "
     "RulePoller._targets watches nothing for it (CFG2 review)", EXC,
     "    return bool(rid) and rid.split(\"/\")[-1] == vm_name.lower()\n",
     "    return (getattr(rule, \"asset_name\", \"\") or rid.split(\"/\")[-1]).lower() == vm_name.lower()\n"),
]

TESTS = {**{f"M{n}": _T for n in (*range(7246, 7252), 7271)},
         "M7252": f"{_T} tests/unit/test_console_escaping.py"}
