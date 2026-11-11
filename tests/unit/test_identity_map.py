"""IDM1 (#687): the identity map (docs/design/identites.md) holds every identity the repository
declares — a role of infra/identities/, a Terraform identity or right, an identity variable of the
compose and the example environments, a workflow's secret or write permission — and fails on one
added without its line, an assignment whose role or scope changes, a right the matrix does not name
(scripts/identity_map.py; mutants M4765–M4769, M4773–M4775).

Each « added without its line » case runs on a copy of exactly the files the reader reads, so the
real map is proved clean first, then broken by one declaration. Nothing here calls Azure, GitHub or
Discord, and nothing reads a state, a tfvars, a host.env or an .envrc.
"""
import importlib.util
import re
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("identity_map", REPO / "scripts" / "identity_map.py")
idm = importlib.util.module_from_spec(_spec)
sys.modules["identity_map"] = idm
_spec.loader.exec_module(idm)

_anchors_spec = importlib.util.spec_from_file_location("doc_anchors", REPO / "scripts" / "doc_anchors.py")
doc_anchors = importlib.util.module_from_spec(_anchors_spec)
sys.modules.setdefault("doc_anchors", doc_anchors)
_anchors_spec.loader.exec_module(doc_anchors)

DOC = REPO / idm.DOC


@pytest.fixture
def copy(tmp_path):
    """The files the reader reads, and only those, copied under tmp_path."""
    for p in idm.read_files(REPO):
        dest = tmp_path / p.relative_to(REPO)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
    assert idm.problems(tmp_path) == []
    return tmp_path


def _append(path: Path, text: str) -> None:
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_the_map_holds_every_declaration_of_the_repository():
    assert idm.problems() == []


def test_the_reader_finds_each_kind_of_declaration():
    keys = set(idm.declarations())
    for key in ("infra/identities/glorfindel-restore-staging.json",
                "infra/glorfindel-host:azurerm_linux_virtual_machine.host#identity",
                "infra/orodruin:azurerm_role_definition.injector_vm",
                "infra/terraform:azuread_application.bench_reader",
                "infra/terraform:azurerm_linux_virtual_machine.baseline#admin_ssh_key",
                "env:EREGION_CONSOLE_AZURE_CLIENT_SECRET", "env:DISCORD_BOT_TOKEN", "env:EREGION_HARNESS_KEY",
                "workflow:canary-azurerm.yml:canary:id-token", "workflow:pip-audit.yml:*:issues",
                "workflow:notify.yml:secrets.EREGION_DISCORD_WEBHOOK_CI"):
        assert key in keys, key
    for prefix in ("infra/glorfindel-host:azurerm_role_assignment.restore_staging [Eregion Glorfindel Restore Staging @ ",
                   "infra/orodruin:azurerm_role_assignment.vm_injector [azurerm_role_definition.injector_vm @ ",
                   "infra/orodruin:azuread_app_role_assignment.graph_read ["):
        assert any(k.startswith(prefix) for k in keys), prefix
    # What says no identity stays out: a subscription, a workspace, a channel's URL, a data source.
    for key in ("env:AZURE_SUBSCRIPTION_ID", "env:AZURE_WORKSPACE_ID", "env:EREGION_EXERCISE_CHANNEL",
                "env:DISCORD_CHANNEL_ID"):
        assert key not in keys, key
    addresses = {k.split(" [")[0] for k in keys}
    assert not any(":data." in k or "azuread_service_principal.msgraph" in k for k in addresses)


ADDED = {
    "a role file": ("infra/identities/glorfindel-probe.json",
                    '{"Name": "Eregion Glorfindel Probe", "Actions": []}\n', None,
                    "infra/identities/glorfindel-probe.json"),
    "a role assignment": ("infra/orodruin/main.tf",
                          '\nresource "azurerm_role_assignment" "probe" {\n  scope = "x"\n'
                          '  role_definition_name = "Owner"\n}\n', None,
                          "infra/orodruin:azurerm_role_assignment.probe [Owner @ x → ?]"),
    "a key vault access policy": ("infra/glorfindel-host/main.tf",
                                  '\nresource "azurerm_key_vault_access_policy" "probe" {\n  key_vault_id = "x"\n}\n',
                                  None, "infra/glorfindel-host:azurerm_key_vault_access_policy.probe"),
    "an azapi role assignment": ("infra/terraform/chaos.tf",
                                 '\nresource "azapi_resource" "probe" {\n'
                                 '  type      = "Microsoft.Authorization/roleAssignments@2022-04-01"\n'
                                 '  body = {\n    properties = {}\n  }\n}\n',
                                 None, "infra/terraform:azapi_resource.probe"),
    "an assignment in a .tf.json": ("infra/orodruin/probe.tf.json",
                                    '{"resource": {"azurerm_role_assignment": {"probe": {"scope": "x", '
                                    '"role_definition_name": "Owner"}}}}\n',
                                    None, "infra/orodruin:azurerm_role_assignment.probe [Owner @ x → ?]"),
    "a dynamic identity block": ("infra/glorfindel-host/main.tf",
                                 '\nresource "azurerm_storage_account" "probe" {\n  dynamic "identity" {\n'
                                 '    for_each = []\n    content {\n      type = "SystemAssigned"\n    }\n  }\n}\n',
                                 None, "infra/glorfindel-host:azurerm_storage_account.probe#identity"),
    "an identity block deeper down": ("infra/orodruin/main.tf",
                                      '\nresource "azurerm_container_group" "probe" {\n  container {\n'
                                      '    identity {\n      type = "SystemAssigned"\n    }\n  }\n}\n',
                                      None, "infra/orodruin:azurerm_container_group.probe#identity"),
    "a role definition": ("infra/terraform/chaos.tf",
                          '\nresource "azurerm_role_definition" "probe" {\n  name = "x"\n}\n', None,
                          "infra/terraform:azurerm_role_definition.probe"),
    "an Entra ID resource": ("infra/terraform/entra_identity.tf",
                             '\nresource "azuread_application_password" "probe" {\n  application_id = "x"\n}\n',
                             None, "infra/terraform:azuread_application_password.probe"),
    "a user-assigned identity": ("infra/glorfindel-host/main.tf",
                                 '\nresource "azurerm_user_assigned_identity" "probe" {\n  name = "x"\n}\n',
                                 None, "infra/glorfindel-host:azurerm_user_assigned_identity.probe"),
    "a managed identity on a resource": ("infra/glorfindel-host/main.tf",
                                         '\nresource "azurerm_storage_account" "probe" {\n  identity {\n'
                                         '    type = "SystemAssigned"\n  }\n}\n',
                                         None, "infra/glorfindel-host:azurerm_storage_account.probe#identity"),
    "an SSH key on a VM": ("infra/orodruin/main.tf",
                           '\nresource "azurerm_linux_virtual_machine" "probe" {\n  admin_ssh_key {\n'
                           '    username = "x"\n  }\n}\n',
                           None, "infra/orodruin:azurerm_linux_virtual_machine.probe#admin_ssh_key"),
    "a pair in the compose": ("docker-compose.yml",
                              "\nx-probe: &probe\n  PROBE_AZURE_CLIENT_SECRET: ${PROBE_AZURE_CLIENT_SECRET:-}\n",
                              None, "env:PROBE_AZURE_CLIENT_SECRET"),
    "a token in host.env.example": ("infra/glorfindel-host/host.env.example", "\nPROBE_TOKEN=\n", None,
                                    "env:PROBE_TOKEN"),
    "a key in orodruin.env.example": ("infra/orodruin/orodruin.env.example", "\nEREGION_PROBE_KEY=\n", None,
                                      "env:EREGION_PROBE_KEY"),
    "a commented pair in .envrc.example": (".envrc.example", "\n# export PROBE_CLIENT_ID=xxxx\n", None,
                                           "env:PROBE_CLIENT_ID"),
    "a PIM assignment": ("infra/terraform/chaos.tf",
                         '\nresource "azurerm_pim_eligible_role_assignment" "probe" {\n  scope = "x"\n'
                         '  role_definition_id = "y"\n  principal_id = "z"\n}\n', None,
                         "infra/terraform:azurerm_pim_eligible_role_assignment.probe [y @ x → z]"),
    "a VM's admin password": ("infra/orodruin/main.tf",
                              '\nresource "azurerm_windows_virtual_machine" "probe" {\n  admin_password = var.x\n}\n',
                              None, "infra/orodruin:azurerm_windows_virtual_machine.probe#admin_password"),
    "an assignment with unquoted labels": ("infra/orodruin/main.tf",
                                           '\nresource azurerm_role_assignment probe {\n  scope = "x"\n'
                                           '  role_definition_name = "Owner"\n  principal_id = "z"\n}\n', None,
                                           "infra/orodruin:azurerm_role_assignment.probe [Owner @ x → z]"),
    "an assignment on one line": ("infra/orodruin/main.tf",
                                  '\nresource "azurerm_role_assignment" "probe" { scope = "x" }\n', None,
                                  "infra/orodruin:azurerm_role_assignment.probe [? @ ? → ?]"),
    "a variable in the compose's list form": ("docker-compose.yml",
                                              "\nx-probe:\n  environment:\n    - PROBE_PASSPHRASE=x\n", None,
                                              "env:PROBE_PASSPHRASE"),
    "a principal id": ("infra/orodruin/orodruin.env.example", "\nEREGION_PROBE_PRINCIPAL_ID=\n", None,
                       "env:EREGION_PROBE_PRINCIPAL_ID"),
    "an app id": ("team.env.example", "\nPROBE_APP_ID=\n", None, "env:PROBE_APP_ID"),
    "a tailnet auth key": (".envrc.example", "\n# export TS_AUTHKEY=x\n", None, "env:TS_AUTHKEY"),
    "credentials": ("infra/glorfindel-host/host.env.example", "\nPROBE_CREDENTIALS=\n", None, "env:PROBE_CREDENTIALS"),
    "every secret at once": (".github/workflows/ci.yml", "\n# ${{ toJSON(secrets) }}\n", None,
                             "workflow:ci.yml:toJSON(secrets)"),
    "a secret chosen at run time": (".github/workflows/ci.yml", "\n# ${{ secrets[matrix.name] }}\n", None,
                                    "workflow:ci.yml:secrets[matrix.name]"),
    "a workflow's secret": (".github/workflows/roadmap.yml", "\n# ${{ secrets.PROBE_WEBHOOK }}\n", None,
                            "workflow:roadmap.yml:secrets.PROBE_WEBHOOK"),
    "a workflow's secret by its index": (".github/workflows/ci.yml", "\n# ${{ secrets['PROBE_TOKEN'] }}\n", None,
                                         "workflow:ci.yml:secrets.PROBE_TOKEN"),
    "a job that inherits every secret": (".github/workflows/probe.yaml",
                                         "on: push\njobs:\n  call:\n    uses: ./.github/workflows/ci.yml\n"
                                         "    secrets: inherit\n", None, "workflow:probe.yaml:call:secrets-inherit"),
    "a password": (".envrc.example", "\n# export PROBE_PASSWORD=x\n", None, "env:PROBE_PASSWORD"),
    "a SAS": ("infra/orodruin/orodruin.env.example", "\nEREGION_CHANNEL_SAS=\n", None, "env:EREGION_CHANNEL_SAS"),
    "a connection string": ("team.env.example", "\nPROBE_CONNECTION_STRING=\n", None, "env:PROBE_CONNECTION_STRING"),
    "a fingerprint": ("infra/glorfindel-host/host.env.example", "\nPROBE_SSH_FINGERPRINT=\n", None,
                      "env:PROBE_SSH_FINGERPRINT"),
    "a certificate": ("infra/glorfindel-host/host.env.example", "\nEREGION_PROBE_CERT=\n", None,
                      "env:EREGION_PROBE_CERT"),
    "a secret beside a client": ("infra/glorfindel-host/host.env.example", "\nEREGION_TOTP_SECRET=\n", None,
                                 "env:EREGION_TOTP_SECRET"),
    "a job's OIDC token": (".github/workflows/ci.yml", None,
                           ("  test:\n", "  test:\n    permissions:\n      id-token: write\n"),
                           "workflow:ci.yml:test:id-token"),
    "a workflow's top write": (".github/workflows/images.yml", None,
                               ("permissions:\n  contents: read\n", "permissions:\n  contents: write\n"),
                               "workflow:images.yml:*:contents"),
}


@pytest.mark.parametrize("case", sorted(ADDED))
def test_an_identity_added_without_its_line_fails(copy, case):
    rel, text, edit, key = ADDED[case]
    path = copy / rel
    if text is not None:
        if path.exists():
            _append(path, text)
        else:
            path.write_text(text, encoding="utf-8")
    else:
        _edit(path, *edit)
    found = idm.problems(copy)
    assert any(p.startswith(key + " ") and "sans sa ligne" in p for p in found), found
    # Its line in the register, and the map holds again.
    _append(copy / idm.DOC, "")
    doc = copy / idm.DOC
    _edit(doc, "| `workflow:roadmap.yml:secrets.EREGION_DISCORD_ROADMAP_CHANNEL` | `atelier-bot` |\n",
          "| `workflow:roadmap.yml:secrets.EREGION_DISCORD_ROADMAP_CHANNEL` | `atelier-bot` |\n"
          f"| `{key}` | `imladris-mi` |\n")
    # A new role still wants its rows in §3.0: said as such, and only that.
    rest = [p for p in idm.problems(copy) if "le rôle « Eregion Glorfindel Probe »" not in p
            and not (p.lower().startswith("probe (") and "sans ses actions dans §3.0" in p)]
    assert rest == []


def test_a_line_of_the_register_the_repository_no_longer_declares_fails(copy):
    _edit(copy / "infra/orodruin/main.tf", 'resource "azurerm_role_assignment" "channel_operator" {',
          'resource "azurerm_storage_blob" "channel_operator" {')
    found = idm.problems(copy)
    assert any(p.startswith("infra/orodruin:azurerm_role_assignment.channel_operator [Storage Blob Data Contributor @ "
                            "azurerm_storage_container.exercises → data.azurerm_client_config.operator.object_id] : "
                            "au registre, mais le dépôt ne la déclare plus") for p in found), found


_BENCH_READER = ('resource "azurerm_role_assignment" "bench_reader" {\n'
                 "  scope                = data.azurerm_resource_group.bench.id\n"
                 '  role_definition_name = "Reader"\n'
                 "  principal_id         = azurerm_linux_virtual_machine.host.identity[0].principal_id\n")
_HOST = "azurerm_linux_virtual_machine.host.identity[0].principal_id"


@pytest.mark.parametrize("old,new,key", [
    ('role_definition_name = "Reader"', 'role_definition_name = "Contributor"',
     f"infra/glorfindel-host:azurerm_role_assignment.bench_reader [Contributor @ data.azurerm_resource_group.bench → {_HOST}]"),
    ("scope                = data.azurerm_resource_group.bench.id",
     "scope                = data.azurerm_subscription.current.id",
     f"infra/glorfindel-host:azurerm_role_assignment.bench_reader [Reader @ data.azurerm_subscription.current → {_HOST}]"),
    (f"principal_id         = {_HOST}", "principal_id         = var.someone_else",
     "infra/glorfindel-host:azurerm_role_assignment.bench_reader [Reader @ data.azurerm_resource_group.bench → "
     "var.someone_else]"),
], ids=["role", "scope", "principal"])
def test_an_assignment_whose_role_scope_or_principal_changes_is_a_new_key(copy, old, new, key):
    _edit(copy / "infra/glorfindel-host/main.tf", _BENCH_READER, _BENCH_READER.replace(old, new))
    found = idm.problems(copy)
    assert any(p.startswith(key + " ") and "sans sa ligne" in p for p in found), found
    assert any(p.startswith("infra/glorfindel-host:azurerm_role_assignment.bench_reader [Reader @ "
                            f"data.azurerm_resource_group.bench → {_HOST}] : au registre, mais le dépôt ne la déclare "
                            "plus") for p in found), found


# An action added to a role: said role by role, even when §3.0 already names it on another role's row.
ACTIONS = {
    "an action of another role, added to a role file": (
        "infra/identities/glorfindel-response.json",
        '    "Microsoft.Network/networkInterfaces/write",\n',
        '    "Microsoft.Network/networkInterfaces/write",\n    "Microsoft.Compute/virtualMachines/write",\n',
        "Response", "Microsoft.Compute/virtualMachines/write", "`Microsoft.Network/networkInterfaces/write` |"),
    "a data action added to a role file": (
        "infra/identities/glorfindel-restore-staging.json", '"DataActions": [],',
        '"DataActions": ["Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read"],',
        "Restore Staging", "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read",
        "`Microsoft.Storage/storageAccounts/listKeys/action` |"),
    "an action of another role, added to a Terraform role definition": (
        "infra/orodruin/main.tf", '      "Microsoft.Chaos/experiments/cancel/action",\n',
        '      "Microsoft.Chaos/experiments/cancel/action",\n      "Microsoft.Compute/virtualMachines/runCommand/action",\n',
        "injector_chaos", "Microsoft.Compute/virtualMachines/runCommand/action",
        "`Microsoft.Chaos/experiments/cancel/action` |"),
    "the joker in a Terraform role definition": (
        "infra/terraform/chaos.tf", '      "Microsoft.Compute/virtualMachines/start/action",\n    ]',
        '      "Microsoft.Compute/virtualMachines/start/action",\n      "*",\n    ]',
        "chaos_vm_shutdown", "*", "`Microsoft.Compute/virtualMachines/start/action` |"),
}


@pytest.mark.parametrize("case", sorted(ACTIONS))
def test_a_role_whose_actions_differ_from_its_table_fails(copy, case):
    rel, old, new, role, action, row_end = ACTIONS[case]
    _edit(copy / rel, old, new)
    found = idm.problems(copy)
    assert any(p.startswith(f"{role} ({rel}) : ses actions dans §3.0 ne sont pas les siennes") and action in p
               for p in found), found
    # Its row in §3.0 takes the action, and the map holds again.
    doc = copy / idm.DOC
    lines = doc.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("| **") and (f"**{role}**" in line or f"`{role}`" in line) and row_end in line:
            lines[i] = line.replace(row_end, f"`{action}`, {row_end}".replace(" |", "", 1) + " |", 1)
            break
    else:
        raise AssertionError(f"no row of §3.0 for {role}")
    doc.write_text("".join(lines), encoding="utf-8")
    assert [p for p in idm.problems(copy) if p.startswith(role + " ")] == []


def test_a_role_without_its_rows_in_the_table_fails(copy):
    doc = copy / idm.DOC
    text = doc.read_text(encoding="utf-8")
    doc.write_text("".join(line for line in text.splitlines(keepends=True)
                           if not line.startswith("| **Restore Staging** |")), encoding="utf-8")
    assert ("Restore Staging (infra/identities/glorfindel-restore-staging.json) : un rôle que le dépôt définit, sans ses "
            "actions dans §3.0") in idm.problems(copy)


RIGHTS = {
    "a not-action added to a role file": (
        "infra/identities/glorfindel-restore.json", '"NotActions": [],',
        '"NotActions": ["Microsoft.Storage/storageAccounts/delete"],', "Microsoft.Storage/storageAccounts/delete"),
    "a Graph permission": (
        "infra/orodruin/main.tf", 'toset(["Application.Read.All", "RoleManagement.Read.Directory"])',
        'toset(["Application.Read.All", "RoleManagement.Read.Directory", "Directory.ReadWrite.All"])',
        "Directory.ReadWrite.All"),
    "a Graph permission of any resource": (
        "infra/orodruin/main.tf", 'toset(["Application.Read.All", "RoleManagement.Read.Directory"])',
        'toset(["Application.Read.All", "RoleManagement.Read.Directory", "Mail.Send"])', "Mail.Send"),
    "a directory role": (
        "infra/terraform/entra_bench_unit.tf", '  entra_role_templates = {\n',
        '  entra_role_templates = {\n    "Privileged Role Administrator" = "00000000-0000-0000-0000-000000000001"\n',
        "Privileged Role Administrator"),
}


@pytest.mark.parametrize("case", sorted(RIGHTS))
def test_a_right_the_matrix_does_not_name_fails(copy, case):
    rel, old, new, right = RIGHTS[case]
    _edit(copy / rel, old, new)
    found = idm.problems(copy)
    assert any(p.startswith(f"{right} ({rel}) : un droit que le dépôt déclare, nommé nulle part") for p in found), found
    # Named in the matrix, between backticks, and it holds again.
    _edit(copy / idm.DOC, "### 3.1 Imladris\n", f"Le droit de l'essai : `{right}`.\n\n### 3.1 Imladris\n")
    assert [p for p in idm.problems(copy) if right in p] == []


def test_every_role_is_read_action_by_action():
    roles = idm.role_actions()
    assert {"Response", "Session Drain", "Restore", "Restore Neutralize", "Restore Staging", "injector_read",
            "injector_vm", "injector_chaos", "contract_reader", "chaos_vm_shutdown"} <= set(roles)
    assert {"Microsoft.Compute/virtualMachines/write", "Microsoft.Compute/disks/write",
            "Microsoft.Storage/storageAccounts/write"} <= roles["Restore"][0]
    assert "Microsoft.Network/publicIPAddresses/join/action" in roles["Response"][0]
    assert idm.table_actions(DOC.read_text(encoding="utf-8"))["Restore"] == roles["Restore"][0]
    assert {"Application.ReadWrite.OwnedBy", "User Administrator"} <= set(idm.named_rights())
    assert idm.problems() == []


def test_a_register_row_naming_an_unknown_line_fails(copy):
    _edit(copy / idm.DOC, "| `env:EREGION_HARNESS_KEY` | `cle-harnais` |",
          "| `env:EREGION_HARNESS_KEY` | `cle-harnais`, `cle-inconnue` |")
    assert any("`cle-inconnue`, absente de la matrice" in p for p in idm.problems(copy))


def test_a_line_marked_from_the_repository_must_be_fed_by_a_declaration(copy):
    doc = copy / idm.DOC
    _edit(doc, "| `env:EREGION_RULE_CANARY_APPID` | `canari` |", "| `env:EREGION_RULE_CANARY_APPID` | `cle-modele` |")
    for key in ("canary:id-token", "secrets.CANARY_AZURE_CLIENT_ID", "secrets.CANARY_AZURE_TENANT_ID",
                "secrets.CANARY_AZURE_SUBSCRIPTION_ID"):
        _edit(doc, f"| `workflow:canary-azurerm.yml:{key}` | `canari` |",
              f"| `workflow:canary-azurerm.yml:{key}` | `github-token` |")
    assert "`canari` : marquée « dépôt », mais aucune déclaration du dépôt ne la nourrit" in idm.problems(copy)


def test_a_planned_line_is_not_declared_yet(copy):
    _edit(copy / idm.DOC, "| `env:EREGION_HARNESS_KEY` | `cle-harnais` |",
          "| `env:EREGION_HARNESS_KEY` | `cle-harnais`, `totp` |")
    assert "`totp` : marquée « prévue », mais le dépôt la déclare déjà" in idm.problems(copy)


@pytest.mark.parametrize("ident", idm.PLANNED)
def test_the_planned_identities_are_in_the_map_and_marked_so(ident):
    matrix = idm.read_matrix(DOC.read_text(encoding="utf-8"))
    assert matrix[ident][-1] == "prévue"


def test_a_planned_identity_missing_fails(copy):
    doc = copy / idm.DOC
    text = doc.read_text(encoding="utf-8")
    doc.write_text("\n".join(line for line in text.splitlines() if not line.startswith("| `graph-dediee`")) + "\n",
                   encoding="utf-8")
    assert "`graph-dediee` : l'identité prévue manque à la matrice" in idm.problems(copy)


def test_every_line_has_its_nine_columns_its_frontier_and_its_source():
    matrix = idm.read_matrix(DOC.read_text(encoding="utf-8"))
    assert len(matrix) >= 30
    for ident, cells in matrix.items():
        assert len(cells) == idm.COLUMNS, ident
        assert cells[-1] in idm.SOURCES, ident
        assert idm.FRONTIER.search(cells[-2]), ident


def test_a_line_without_its_frontier_or_with_an_unknown_source_fails(copy):
    doc = copy / idm.DOC
    _edit(doc, "| §8 | dépôt |", "| la session | dépôt |")
    _edit(doc, "| §4 | à la main |", "| §4 | ailleurs |")
    found = idm.problems(copy)
    assert "`lecteur-banc` : aucune frontière du modèle de menace (§1 à §9)" in found
    assert any(p.startswith("`cle-modele` : « ailleurs »") for p in found), found


def test_a_role_not_named_on_its_lines_fails(copy):
    _edit(copy / "infra/identities/glorfindel-restore-staging.json", '"Name": "Eregion Glorfindel Restore Staging"',
          '"Name": "Eregion Glorfindel Restore Transit"')
    assert ("infra/identities/glorfindel-restore-staging.json : le rôle « Eregion Glorfindel Restore Transit » "
            "n'est nommé sur aucune de ses lignes") in idm.problems(copy)


def test_a_file_the_map_reads_gone_is_said(copy):
    (copy / "team.env.example").unlink()
    assert idm.problems(copy) == ["team.env.example : introuvable — la carte ne se relit pas sans lui"]


def test_the_reader_never_reads_a_state_nor_a_secret_file():
    read = {p.relative_to(REPO).as_posix() for p in idm.read_files(REPO)}
    for p in read:
        assert not re.search(r"\.tfstate|\.tfvars$|(^|/)host\.env$|(^|/)\.envrc$|orodruin\.env$|\.terraform/", p), p


def test_the_cli_says_the_map_holds_and_fails_on_a_missing_line(copy, capsys):
    assert idm.main(["check"]) == 0
    assert "tient chaque déclaration" in capsys.readouterr().out
    _append(copy / "infra/orodruin/main.tf", '\nresource "azurerm_role_assignment" "probe" {\n}\n')
    assert idm.main(["check"], repo=copy) == 1
    assert "infra/orodruin:azurerm_role_assignment.probe" in capsys.readouterr().out
    assert idm.main(["list"]) == 0
    assert "env:DISCORD_BOT_TOKEN" in capsys.readouterr().out


def test_the_threat_model_architecture_and_operations_point_to_the_map():
    for rel, link in (("docs/design/modele-de-menace.md", "(identites.md)"),
                      ("docs/architecture.md", "(design/identites.md)"),
                      ("docs/operations.md", "(design/identites.md)")):
        assert link in (REPO / rel).read_text(encoding="utf-8"), rel


def test_the_links_and_anchors_of_the_map_resolve():
    assert doc_anchors.broken(DOC) == []


def test_the_map_names_no_real_identifier():
    text = DOC.read_text(encoding="utf-8")
    assert not re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", text)
    assert not re.search(r"onmicrosoft\.com|[\w.-]+@[\w-]+\.[a-z]{2,}|\bsha256:[0-9a-f]{16,}", text, re.I)
    # Public addresses: none; the tailnet's range and the loopback only.
    for ip in re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text):
        assert ip.startswith(("127.", "100.64.", "10.", "169.254.", "168.63.")), ip
    # The host is named Imladris, its former name said once at its first mention.
    assert "Imladris (anciennement H0)" in text
