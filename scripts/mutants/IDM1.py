"""IDM1 (#687): the identity map (docs/design/identites.md) held to what the repository declares — its
reader, scripts/identity_map.py, which finds each role, Terraform identity or right, identity variable
and workflow secret or write permission, and says the one without its line. M4765–M4769; the review's
controls, M4773–M4775: an assignment keyed by its role and its scope, every action of a role named in
the matrix.

Each is caught by tests/unit/test_identity_map.py: a reader that misses a kind of declaration, or a key
that loses its role or its scope, leaves the register's rows unmatched (« le dépôt ne la déclare plus »)
on the real map; a check removed lets a declaration added without its line, a line marked « dépôt »
that nothing feeds, or an action no line names pass on the copy the test breaks.
"""
MAP = "scripts/identity_map.py"
_TEST = "tests/unit/test_identity_map.py"

MUTANTS = [
    ("M4765", "a role assignment is no identity to the reader: a new right passes without its line (IDM1)", MAP,
     'IDENTITY_TYPES = ("azurerm_role_assignment", "azurerm_role_definition", "azurerm_user_assigned_identity",',
     'IDENTITY_TYPES = ("azurerm_role_definition", "azurerm_user_assigned_identity",'),
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
    # The review of IDM1: a right softened in the map passed in silence.
    ("M4773", "an assignment's key loses its role: Reader turned Owner on the same address passes unsaid (IDM1)",
     MAP,
     '    return f"{addr} [{role} @ {scope}]"\n',
     '    return f"{addr} [? @ {scope}]"\n'),
    ("M4774", "an action of a role no line of the matrix names passes: the map softens what a role can do (IDM1)",
     MAP,
     '        if f"`{right}`" not in named:\n',
     '        if False:\n'),
    ("M4775", "an assignment's key loses its scope: a VM's right widened to the group passes unsaid (IDM1)", MAP,
     '    return f"{addr} [{role} @ {scope}]"\n',
     '    return f"{addr} [{role} @ ?]"\n'),
]
TESTS = {mid: _TEST for mid in ("M4765", "M4766", "M4767", "M4768", "M4769", "M4773", "M4774", "M4775")}
