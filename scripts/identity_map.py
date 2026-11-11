#!/usr/bin/env python3
"""identity_map — the identity map held to what the repository declares (IDM1, #687).

  python3 scripts/identity_map.py check    every declaration has its line in the map, every line
                                           marked « dépôt » its declaration; exit 1 otherwise
  python3 scripts/identity_map.py list     what the repository declares, one key per line

The map is docs/design/identites.md: its matrix (§3), one line per identity, and its register (§4),
« D'où vient chaque ligne », one row per declaration naming the lines it feeds. What is read here,
and only that — never a state, a tfvars, a host.env or an .envrc:

  the roles       infra/identities/*.json, by file; each role's Name said on one of its lines;
  Terraform       every `.tf` under infra/ (`.terraform/` aside): each resource that is an
                  identity or a right (a role assignment or definition, a user-assigned identity, a
                  federated credential, every azuread_* resource), and each resource that carries an
                  `identity {` or an `admin_ssh_key {` block — `<module>:<type>.<name>[#block]`;
  the environment the compose file and the example environments (host.env, orodruin.env, .envrc,
                  team.env): each variable whose name says an identity, a credential or a right
                  (IDENTITY_VAR) — `env:<NAME>`;
  the workflows   each secret a workflow reads, and each permission it grants in write, at the top
                  or per job (`id-token: write` among them) — `workflow:<file>:…`.

A line of the matrix says where it is declared: `dépôt` (it must be fed by a declaration), `code`
(drawn at run time by Eregion's code: a key, a token), `à la main` (made outside the repository: the
repository may carry only the variable that holds it), `dépôt, à la main` (both), `prévue` (planned:
nothing may declare it yet). The test is tests/unit/test_identity_map.py; nothing here calls Azure,
GitHub or Discord.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
DOC = "docs/design/identites.md"
ROLES_DIR = "infra/identities"
INFRA = "infra"
WORKFLOWS = ".github/workflows"
COMPOSE = "docker-compose.yml"
# The environments a container, a host or the workstation is given, as the repository shows them.
ENV_FILES = ("infra/glorfindel-host/host.env.example", "infra/orodruin/orodruin.env.example",
             ".envrc.example", "team.env.example")

# A variable that carries an identity, a credential, the name of a principal or the scope of a right.
IDENTITY_VAR = re.compile(r"CLIENT_ID|CLIENT_SECRET|TENANT_ID|OBJECT_ID|_TOKEN|API_KEY|_KEYS?$|WEBHOOK"
                          r"|ALLOWED_USERS|ALLOWED_ROLES|PRINCIPALS?$|IDENTIT|OWN_CALLERS|APPID|_PAIR$"
                          r"|DISCORD_BOT$|_SCOPE$")
# The Terraform resources that are an identity or a right; every azuread_* one too.
IDENTITY_TYPES = ("azurerm_role_assignment", "azurerm_role_definition", "azurerm_user_assigned_identity",
                  "azurerm_federated_identity_credential")
RESOURCE = re.compile(r'^resource "([a-z0-9_]+)" "([A-Za-z0-9_-]+)" \{')
NESTED = re.compile(r"^  (identity|admin_ssh_key) \{")

MATRIX = "## 3. La matrice"
REGISTER = "## 4. D'où vient chaque ligne"
SOURCES = ("dépôt", "dépôt, à la main", "code", "à la main", "prévue")
# Columns of a line: the identity, where it lives, its secret, who uses it, its rights, what it cannot
# do, its rotation and expiry, its boundary in the threat model, where it is declared.
COLUMNS = 9
FRONTIER = re.compile(r"§([1-9])\b")
# The identities the 0.6.0 must show although nothing declares them yet (the fiche of IDM1).
PLANNED = ("stratus", "executeur-restore", "totp", "graph-dediee")
LINE_ID = re.compile(r"^`([a-z0-9-]+)`")


def _rel(path: Path, repo: Path) -> str:
    return path.relative_to(repo).as_posix()


def tf_files(repo: Path = REPO) -> list[Path]:
    """Every Terraform file under infra/, the providers' cache aside."""
    return sorted(p for p in (repo / INFRA).rglob("*.tf") if ".terraform" not in p.parts)


def role_files(repo: Path = REPO) -> list[Path]:
    return sorted((repo / ROLES_DIR).glob("*.json"))


def workflow_files(repo: Path = REPO) -> list[Path]:
    return sorted((repo / WORKFLOWS).glob("*.yml"))


def read_files(repo: Path = REPO) -> list[Path]:
    """What this reader reads, and nothing else (the test copies exactly these)."""
    return [*role_files(repo), *tf_files(repo), repo / COMPOSE, *(repo / f for f in ENV_FILES),
            *workflow_files(repo), repo / DOC]


def role_declarations(repo: Path = REPO) -> dict[str, str]:
    """infra/identities/<file>.json → the role's Name."""
    out = {}
    for p in role_files(repo):
        out[_rel(p, repo)] = str(yaml.safe_load(p.read_text(encoding="utf-8")).get("Name", ""))
    return out


def terraform_declarations(repo: Path = REPO) -> dict[str, str]:
    """`<module>:<type>.<name>` for an identity or a right, `…#identity`, `…#admin_ssh_key` for a
    resource that carries one; the value is the file."""
    out = {}
    for p in tf_files(repo):
        module = _rel(p.parent, repo)
        current = None
        for line in p.read_text(encoding="utf-8").splitlines():
            m = RESOURCE.match(line)
            if m:
                kind, name = m.groups()
                current = f"{module}:{kind}.{name}"
                if kind in IDENTITY_TYPES or kind.startswith("azuread_"):
                    out[current] = _rel(p, repo)
                continue
            if line.startswith("}"):
                current = None
                continue
            n = NESTED.match(line)
            if n and current:
                out[f"{current}#{n.group(1)}"] = _rel(p, repo)
    return out


def _env_names(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    if path.name.endswith(".yml"):
        names = set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", text))
        names |= set(re.findall(r"^\s+([A-Z][A-Z0-9_]*):", text, re.M))
        return names
    # An example environment: its lines, and those left commented for the reader to fill.
    return set(re.findall(r"^(?:#\s*)?(?:export\s+)?([A-Z][A-Z0-9_]*)=", text, re.M))


def env_declarations(repo: Path = REPO) -> dict[str, str]:
    """`env:<NAME>` for each identity variable; the value is the first file that names it."""
    out: dict[str, str] = {}
    for rel in (COMPOSE, *ENV_FILES):
        for name in sorted(_env_names(repo / rel)):
            if IDENTITY_VAR.search(name):
                out.setdefault(f"env:{name}", rel)
    return out


def workflow_declarations(repo: Path = REPO) -> dict[str, str]:
    """`workflow:<file>:secrets.<NAME>` and `workflow:<file>:<job|*>:<permission>` (write only)."""
    out = {}
    for p in workflow_files(repo):
        text = p.read_text(encoding="utf-8")
        rel = _rel(p, repo)
        for name in sorted(set(re.findall(r"secrets\.([A-Z][A-Z0-9_]*)", text))):
            out[f"workflow:{p.name}:secrets.{name}"] = rel
        doc = yaml.safe_load(text) or {}
        grants = [("*", doc.get("permissions"))]
        grants += [(job, (spec or {}).get("permissions")) for job, spec in (doc.get("jobs") or {}).items()]
        for job, perms in grants:
            if isinstance(perms, str) and perms == "write-all":
                out[f"workflow:{p.name}:{job}:write-all"] = rel
            elif isinstance(perms, dict):
                for perm, level in perms.items():
                    if level == "write":
                        out[f"workflow:{p.name}:{job}:{perm}"] = rel
    return out


def declarations(repo: Path = REPO) -> dict[str, str]:
    """Every declaration of the repository, by its key; the value is where it is."""
    out = {}
    for k in role_declarations(repo):
        out[k] = k
    out.update(terraform_declarations(repo))
    out.update(env_declarations(repo))
    out.update(workflow_declarations(repo))
    return out


def _section(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    try:
        start = lines.index(heading)
    except ValueError:
        return []
    out = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        out.append(line)
    return out


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split(" | ")]


def read_matrix(text: str) -> dict[str, list[str]]:
    """The matrix's lines, by their id: each table row of §3 whose first cell starts with `id`."""
    out = {}
    for line in _section(text, MATRIX):
        if not line.startswith("| `"):
            continue
        cells = _cells(line)
        m = LINE_ID.match(cells[0])
        if m:
            out[m.group(1)] = cells
    return out


def read_register(text: str) -> dict[str, list[str]]:
    """The register of §4: a declaration's key → the ids of the lines it feeds."""
    out = {}
    for line in _section(text, REGISTER):
        if not line.startswith("| `"):
            continue
        cells = _cells(line)
        if len(cells) < 2:
            continue
        key = cells[0].strip("`")
        out[key] = re.findall(r"`([a-z0-9-]+)`", cells[1])
    return out


def problems(repo: Path = REPO) -> list[str]:
    """What makes the map lie, each said once: empty when it holds."""
    out = []
    for rel in (COMPOSE, *ENV_FILES, DOC):
        if not (repo / rel).is_file():
            out.append(f"{rel} : introuvable — la carte ne se relit pas sans lui")
    if out:
        return out
    text = (repo / DOC).read_text(encoding="utf-8")
    matrix = read_matrix(text)
    register = read_register(text)
    declared = declarations(repo)
    if not matrix:
        out.append(f"{DOC} : aucune ligne dans « {MATRIX[3:]} »")
    for key in sorted(declared):
        if key not in register:
            out.append(f"{key} ({declared[key]}) : déclarée dans le dépôt, sans sa ligne au registre ({DOC}, §4)")
    for key in sorted(register):
        if key not in declared:
            out.append(f"{key} : au registre, mais le dépôt ne la déclare plus — retirer la ligne du registre")
        for ident in register[key]:
            if ident not in matrix:
                out.append(f"{key} : nomme la ligne `{ident}`, absente de la matrice")
        if key in declared and not register[key]:
            out.append(f"{key} : au registre, sans aucune ligne de la matrice")
    fed = {ident for key in register if key in declared for ident in register[key]}
    for ident, cells in sorted(matrix.items()):
        if len(cells) != COLUMNS:
            out.append(f"`{ident}` : {len(cells)} colonnes, {COLUMNS} attendues")
            continue
        source = cells[-1]
        if source not in SOURCES:
            out.append(f"`{ident}` : « {source} » — la dernière colonne dit {' ; '.join(SOURCES)}")
        if not FRONTIER.search(cells[-2]):
            out.append(f"`{ident}` : aucune frontière du modèle de menace (§1 à §9)")
        if "dépôt" in source and ident not in fed:
            out.append(f"`{ident}` : marquée « dépôt », mais aucune déclaration du dépôt ne la nourrit")
        if source == "prévue" and ident in fed:
            out.append(f"`{ident}` : marquée « prévue », mais le dépôt la déclare déjà")
    for ident in PLANNED:
        if ident not in matrix:
            out.append(f"`{ident}` : l'identité prévue manque à la matrice")
        elif matrix[ident][-1] != "prévue":
            out.append(f"`{ident}` : doit être marquée « prévue »")
    for key, name in sorted(role_declarations(repo).items()):
        rows = [matrix[i] for i in register.get(key, []) if i in matrix]
        if rows and not any(name and name in " ".join(cells) for cells in rows):
            out.append(f"{key} : le rôle « {name} » n'est nommé sur aucune de ses lignes")
    return out


def main(argv: list[str] | None = None, repo: Path = REPO) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["list"]:
        for key, where in sorted(declarations(repo).items()):
            print(f"{key}\t{where}")
        return 0
    if args == ["check"]:
        found = problems(repo)
        for p in found:
            print(f"✗ {p}")
        if not found:
            print(f"✓ la carte des identités ({DOC}) tient chaque déclaration du dépôt")
        return 1 if found else 0
    print(__doc__.strip().splitlines()[2], file=sys.stderr)
    print("usage : identity_map.py check | list", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
