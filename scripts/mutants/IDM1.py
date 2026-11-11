"""IDM1 (#687): the identity map (docs/design/identites.md) held to what the repository declares — its
reader, scripts/identity_map.py, which finds each role, Terraform identity or right, identity variable
and workflow secret or write permission, and says the one without its line. M4765–M4769; the first
review's controls, M4773–M4775: an assignment keyed by its role and its scope, every right named in the
matrix; the second review's, M4781–M4783: the actions role by role, the principal in the key, the joker.

Each is caught by tests/unit/test_identity_map.py: a reader that misses a kind of declaration, or a key
that loses its role, its scope or its principal, leaves the register's rows unmatched (« le dépôt ne la
déclare plus ») on the real map; a check removed, or a joker unread, lets a declaration added without
its line, a line marked « dépôt » that nothing feeds, a right no line names or an action added to a
role pass on the copy the test breaks.
"""
MAP = "scripts/identity_map.py"
_TEST = "tests/unit/test_identity_map.py"
_KEY = '    return f"{addr} [{role} @ {scope} → {principal}]"\n'

MUTANTS = [
    # Since the second review, any type naming a role assignment is read; the mutant takes that rule away.
    ("M4765", "a role assignment of another type (PIM, Cosmos DB) is no right to the reader: it passes unmapped "
     "(IDM1)", MAP,
     'or kind.startswith("azuread_") or "role_assignment" in kind',
     'or kind.startswith("azuread_") or False'),
    ("M4766", "a managed identity carried by a resource is never read: a VM's identity passes unmapped (IDM1)", MAP,
     '|(identity|admin_ssh_key|access_policy))\\s*\\{\')',
     '|(admin_ssh_key|access_policy))\\s*\\{\')'),
    ("M4767", "a secret is no identity variable: a new pair, a TOTP secret pass without their line (IDM1)", MAP,
     'IDENTITY_VAR = re.compile(r"CLIENT_ID|SECRET|PASSWORD|',
     'IDENTITY_VAR = re.compile(r"CLIENT_ID|PASSWORD|'),
    ("M4768", "a declaration without its line in the register is not said: the map lies by omission (IDM1)", MAP,
     "        if key not in register:\n"
     '            out.append(f"{key} ({declared[key]}) : déclarée dans le dépôt, sans sa ligne',
     "        if False:\n"
     '            out.append(f"{key} ({declared[key]}) : déclarée dans le dépôt, sans sa ligne'),
    ("M4769", "a line marked « dépôt » that nothing feeds passes: a hand-made identity reads as declared (IDM1)",
     MAP,
     '        if "dépôt" in source and ident not in fed:\n',
     '        if False and "dépôt" in source and ident not in fed:\n'),
    # The first review of IDM1: a right softened in the map passed in silence.
    ("M4773", "an assignment's key loses its role: Reader turned Owner on the same address passes unsaid (IDM1)",
     MAP, _KEY, '    return f"{addr} [? @ {scope} → {principal}]"\n'),
    ("M4774", "a not-action, a Graph permission, a directory role no line of the matrix names passes (IDM1)", MAP,
     '        if f"`{right}`" not in named:\n',
     '        if False:\n'),
    ("M4775", "an assignment's key loses its scope: a VM's right widened to the group passes unsaid (IDM1)", MAP,
     _KEY, '    return f"{addr} [{role} @ ? → {principal}]"\n'),
    # The second review of IDM1: an action added to a role, a principal changed, a joker.
    ("M4781", "a role's actions not compared row by row: an action added to a role passes if named elsewhere (IDM1)",
     MAP,
     "        elif said != grants:\n",
     "        elif False:\n"),
    ("M4782", "an assignment's key loses its principal: a right moved to another identity passes unsaid (IDM1)", MAP,
     _KEY, '    return f"{addr} [{role} @ {scope} → ?]"\n'),
    ("M4783", 'a role definition\'s joker is never read: "*" passes as no action at all (IDM1)', MAP,
     "LIST_ITEM = re.compile(r'\"([^\"]+)\"')",
     "LIST_ITEM = re.compile(r'\"(Microsoft\\.[^\"]+)\"')"),
]
TESTS = {mid: _TEST for mid in ("M4765", "M4766", "M4767", "M4768", "M4769", "M4773", "M4774", "M4775",
                                "M4781", "M4782", "M4783")}
