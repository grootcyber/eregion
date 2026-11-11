"""IDM1 (#687): the identity map (docs/design/identites.md) held to what the repository declares — its
reader, scripts/identity_map.py, which finds each role, Terraform identity or right, identity variable
and workflow secret or write permission, and says the one without its line. M4765–M4769.

Each is caught by tests/unit/test_identity_map.py: a reader that misses a kind of declaration leaves
its register rows unmatched (« le dépôt ne la déclare plus ») on the real map, and a check removed
lets a declaration added without its line — or a line marked « dépôt » that nothing feeds — pass on
the copy the test breaks.
"""
MAP = "scripts/identity_map.py"
_TEST = "tests/unit/test_identity_map.py"

MUTANTS = [
    ("M4765", "a role assignment is no identity to the reader: a new right passes without its line (IDM1)", MAP,
     'IDENTITY_TYPES = ("azurerm_role_assignment", "azurerm_role_definition", "azurerm_user_assigned_identity",',
     'IDENTITY_TYPES = ("azurerm_role_definition", "azurerm_user_assigned_identity",'),
    ("M4766", "a managed identity carried by a resource is never read: a VM's identity passes unmapped (IDM1)", MAP,
     'NESTED = re.compile(r"^  (identity|admin_ssh_key) \\{")',
     'NESTED = re.compile(r"^  (admin_ssh_key) \\{")'),
    ("M4767", "a service principal's secret is no identity variable: a new pair passes without its line (IDM1)", MAP,
     'IDENTITY_VAR = re.compile(r"CLIENT_ID|CLIENT_SECRET|TENANT_ID|',
     'IDENTITY_VAR = re.compile(r"CLIENT_ID|TENANT_ID|'),
    ("M4768", "a declaration without its line in the register is not said: the map lies by omission (IDM1)", MAP,
     "        if key not in register:\n"
     '            out.append(f"{key} ({declared[key]}) : déclarée dans le dépôt, sans sa ligne',
     "        if False:\n"
     '            out.append(f"{key} ({declared[key]}) : déclarée dans le dépôt, sans sa ligne'),
    ("M4769", "a line marked « dépôt » that nothing feeds passes: a hand-made identity reads as declared (IDM1)",
     MAP,
     '        if "dépôt" in source and ident not in fed:\n',
     '        if False and "dépôt" in source and ident not in fed:\n'),
]
TESTS = {mid: _TEST for mid in ("M4765", "M4766", "M4767", "M4768", "M4769")}
