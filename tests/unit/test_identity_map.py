"""IDM1 (#687): the identity map (docs/design/identites.md) holds every identity the repository
declares — a role of infra/identities/, a Terraform identity or right, an identity variable of the
compose and the example environments, a workflow's secret or write permission — and fails on one
added without its line (scripts/identity_map.py; mutants M4765–M4769).

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
                "infra/glorfindel-host:azurerm_role_assignment.restore_staging",
                "infra/orodruin:azurerm_role_definition.injector_vm",
                "infra/orodruin:azuread_app_role_assignment.graph_read",
                "infra/terraform:azuread_application.bench_reader",
                "infra/terraform:azurerm_linux_virtual_machine.baseline#admin_ssh_key",
                "env:EREGION_CONSOLE_AZURE_CLIENT_SECRET", "env:DISCORD_BOT_TOKEN", "env:EREGION_HARNESS_KEY",
                "workflow:canary-azurerm.yml:canary:id-token", "workflow:pip-audit.yml:*:issues",
                "workflow:notify.yml:secrets.EREGION_DISCORD_WEBHOOK_CI"):
        assert key in keys, key
    # What says no identity stays out: a subscription, a workspace, a channel's URL, a data source.
    for key in ("env:AZURE_SUBSCRIPTION_ID", "env:AZURE_WORKSPACE_ID", "env:EREGION_EXERCISE_CHANNEL",
                "env:DISCORD_CHANNEL_ID"):
        assert key not in keys, key
    assert not any(":data." in k or "azuread_service_principal.msgraph" in k for k in keys)


ADDED = {
    "a role file": ("infra/identities/glorfindel-probe.json",
                    '{"Name": "Eregion Glorfindel Probe", "Actions": []}\n', None,
                    "infra/identities/glorfindel-probe.json"),
    "a role assignment": ("infra/orodruin/main.tf",
                          '\nresource "azurerm_role_assignment" "probe" {\n  scope = "x"\n}\n', None,
                          "infra/orodruin:azurerm_role_assignment.probe"),
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
    "a workflow's secret": (".github/workflows/roadmap.yml", "\n# ${{ secrets.PROBE_WEBHOOK }}\n", None,
                            "workflow:roadmap.yml:secrets.PROBE_WEBHOOK"),
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
    rest = [p for p in idm.problems(copy) if "le rôle « Eregion Glorfindel Probe »" not in p]
    assert rest == []


def test_a_line_of_the_register_the_repository_no_longer_declares_fails(copy):
    _edit(copy / "infra/orodruin/main.tf", 'resource "azurerm_role_assignment" "channel_operator" {',
          'resource "azurerm_storage_blob" "channel_operator" {')
    found = idm.problems(copy)
    assert any(p.startswith("infra/orodruin:azurerm_role_assignment.channel_operator : au registre, mais le dépôt "
                            "ne la déclare plus") for p in found), found


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
