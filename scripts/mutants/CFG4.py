"""CFG4 (#1129): the round-trip write of glorfindel-config.yaml (glorfindel/config_edit.py) and the class of a
change (glorfindel/config_class.py). M7253–M7262: a comment lost (the dictionary dumped again); a result
written without the strict reading; a pattern written instead of a name; a relaxation classed a tightening; a
mixed change classed a tightening; an exclusion of a VM no discovery knows classed neutral; an exact entry that
changes nothing today classed neutral (under a pattern or the default of its mode); a public host in never_block
classed a tightening (Q10); a wrong inverse; the default to human_only not said loud (Q11). Measured by
tests/unit/test_config_edit.py."""
EDIT = "glorfindel/config_edit.py"
CLS = "glorfindel/config_class.py"
_T = "tests/unit/test_config_edit.py"

MUTANTS = [
    ("M7253", "a comment lost: the dictionary dumped again instead of the text spliced (CFG4)", EDIT,
     "    new = _splice(text, data, name, args, want)\n", "    new = yaml.safe_dump(want, sort_keys=False)\n"),
    ("M7254", "a result written without the strict reading: a reason it refuses reaches the file (CFG4)", EDIT,
     "    try:\n        _parse_config(got)\n", "    try:\n        pass\n"),
    ("M7255", "a pattern written instead of a name: a VM created tomorrow taken in silence (CFG4, Q7)", EDIT,
     "    if any(c in vm for c in \"*?[]\"):\n", "    if False:\n"),
    ("M7256", "a relaxation classed a tightening: an exclusion added applies at once (CFG4)", CLS,
     "            said.append((\"relax\", f\"exclusion added: {pattern}\", False))\n",
     "            said.append((\"tighten\", f\"exclusion added: {pattern}\", False))\n"),
    ("M7257", "a mixed change classed a tightening: a relaxation hidden behind a tightening (CFG4)", CLS,
     "    kind = \"relax\" if relax else \"tighten\" if tighten else \"neutral\"\n",
     "    kind = \"tighten\" if tighten else \"relax\" if relax else \"neutral\"\n"),
    ("M7258", "an exclusion of a VM no discovery knows classed neutral (CFG4, §5.3)", CLS,
     "        if added:\n", "        if False:\n"),
    ("M7259", "an exact entry non_disruptive under a pattern, or the default, of its mode classed neutral: the "
     "latent relaxation (CFG4, §5.3)", CLS,
     "            if ma is not None and _PRUDENCE.get(ma, 0) > 0:\n", "            if False:\n"),
    ("M7260", "a public host added to never_block classed a tightening (CFG4, Q10)", CLS,
     "                            and any(item.version == n.version and item.subnet_of(n) for n in _PRIVATE))\n",
     "                            )\n"),
    ("M7261", "a wrong inverse: a mode set where there was no entry undone as human_only, never removed (CFG4)",
     EDIT, "            return {\"op\": \"unset_mode\", \"args\": {\"vm\": args[\"vm\"]}}\n",
     "            return {\"op\": \"set_mode\", \"args\": {\"vm\": args[\"vm\"], \"mode\": \"human_only\"}}\n"),
    ("M7262", "the default to human_only not said loud: the response disarmed without a sound (CFG4, Q11)", CLS,
     "        said.append((\"loud\", \"response disarmed on the VMs the default governs\", False))\n", ""),
]

# The review of CFG4: M7282–M7285.
MUTANTS += [
    ("M7282", "a text that reads back otherwise than asked written: a reason holding U+0085 folded (CFG4 review)",
     EDIT, "    if got != want:\n", "    if False:\n"),
    ("M7283", "a block scalar's end mark past its last line: a comment after it lost or moved (CFG4 review)", EDIT,
     "        if isinstance(node, yaml.ScalarNode) and node.style in (\"|\", \">\"):\n", "        if False:\n"),
    ("M7284", "a pattern's human_only entry removed classed latent: the VMs it held change today (CFG4 review)",
     CLS, "its entry human_only no longer holds it\", not _is_pattern(key)))\n",
     "its entry human_only no longer holds it\", True))\n"),
    ("M7285", "set_mode on an empty autonomy: crashes instead of writing the entry (CFG4 review)", EDIT,
     "        autonomy = out.get(\"autonomy\") or {}", "        autonomy = out.setdefault(\"autonomy\", {})"),
]

TESTS = {f"M{n}": _T for n in (*range(7253, 7263), *range(7282, 7286))}
