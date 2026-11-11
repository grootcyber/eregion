#!/usr/bin/env python3
"""identity_map — the identity map held to what the repository declares (IDM1, #687).

  python3 scripts/identity_map.py check    every declaration has its line in the map, every line
                                           marked « dépôt » its declaration; exit 1 otherwise
  python3 scripts/identity_map.py list     what the repository declares, one key per line

The map is docs/design/identites.md: its matrix (§3), one line per identity, and its register (§4),
« D'où vient chaque ligne », one row per declaration naming the lines it feeds. What is read here,
and only that — never a state, a tfvars, a host.env or an .envrc:

  the roles       infra/identities/*.json, by file; each role's Name said on one of its lines, and
                  each of its actions (Actions, NotActions, DataActions, NotDataActions) named in §3;
  Terraform       every `.tf` and `.tf.json` under infra/ (`.terraform/` aside): each resource that
                  is an identity or a right (a role assignment or definition, a user-assigned
                  identity, a federated credential, a key vault access policy, an azapi resource of
                  type Microsoft.Authorization/roleAssignments or roleDefinitions, every azuread_*
                  resource), and each resource that carries an `identity`, `admin_ssh_key` or
                  `access_policy` block, `dynamic` or not, at any depth — `<module>:<type>.<name>[#block]`.
                  An assignment's key carries its role and the expression of its scope,
                  `… [<role> @ <scope>]`: a role or a scope changed is a new key, said. The actions of
                  a Terraform role definition, the Graph permissions and the directory roles a `.tf`
                  names are each named in §3;
  the environment the compose file and the example environments (host.env, orodruin.env, .envrc,
                  team.env): each variable whose name says an identity, a credential or a right
                  (IDENTITY_VAR) — `env:<NAME>`;
  the workflows   `.yml` and `.yaml`: each secret a workflow reads (`secrets.X`, `secrets['X']`), each
                  job given `secrets: inherit`, and each permission it grants in write, at the top or
                  per job (`id-token: write` among them) — `workflow:<file>:…`.

A line of the matrix says where it is declared: `dépôt` (it must be fed by a declaration), `code`
(drawn at run time by Eregion's code: a key, a token), `à la main` (made outside the repository: the
repository may carry only the variable that holds it), `dépôt, à la main` (both), `prévue` (planned:
nothing may declare it yet). What stays out of reach is said in the map's §6. The test is
tests/unit/test_identity_map.py; nothing here calls Azure, GitHub or Discord.
"""
from __future__ import annotations

import json
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
IDENTITY_VAR = re.compile(r"CLIENT_ID|SECRET|PASSWORD|TENANT_ID|OBJECT_ID|_TOKEN|API_KEY|_KEYS?$|(^|_)SAS(_|$)"
                          r"|CONNECTION_STRING|FINGERPRINT|CERT|WEBHOOK|ALLOWED_USERS|ALLOWED_ROLES"
                          r"|PRINCIPALS?$|IDENTIT|OWN_CALLERS|APPID|_PAIR$|DISCORD_BOT$|_SCOPE$")
# The Terraform resources that are an identity or a right; every azuread_* one too.
IDENTITY_TYPES = ("azurerm_role_assignment", "azurerm_role_definition", "azurerm_user_assigned_identity",
                  "azurerm_federated_identity_credential", "azurerm_key_vault_access_policy")
# The ones whose key carries a role and a scope: (the role's attributes, the scope's), the first found.
ASSIGNMENTS = {
    "azurerm_role_assignment": (("role_definition_name", "role_definition_id"), ("scope",)),
    "azuread_directory_role_assignment": (("role_id",), ("directory_scope_id",)),
    "azuread_app_role_assignment": (("app_role_id",), ("resource_object_id",)),
}
AZAPI_RIGHTS = ("Microsoft.Authorization/roleAssignments", "Microsoft.Authorization/roleDefinitions")
AZAPI_TYPE = re.compile(r'^\s*type\s*=\s*"([^"@]+)')
RESOURCE = re.compile(r'^resource "([a-z0-9_]+)" "([A-Za-z0-9_-]+)" \{')
BLOCKS = ("identity", "admin_ssh_key", "access_policy")
NESTED = re.compile(r'^\s*(?:dynamic\s+"(identity|admin_ssh_key|access_policy)"|(identity|admin_ssh_key|access_policy))\s*\{')
ATTRIBUTE = re.compile(r"^\s*([a-z_]+)\s*=\s*(.+?)\s*$")
_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')
# The rights a .tf names that are no resource: an action of a role definition, a Graph permission, a
# directory role (its name beside its template id).
ARM_ACTION = re.compile(r'"(Microsoft\.[A-Za-z]+/[^"]+)"')
GRAPH_PERMISSION = re.compile(r'"((?:Application|AppRoleAssignment|AuditLog|DelegatedPermissionGrant|Directory|Group'
                              r'|GroupMember|Policy|RoleManagement|User)\.[A-Za-z]+(?:\.[A-Za-z]+)?)"')
DIRECTORY_ROLE = re.compile(r'^\s*"([A-Z][A-Za-z ]+)"\s*=\s*"[0-9a-f]{8}-[0-9a-f]{4}-')

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
    """Every Terraform file under infra/ (`.tf`, `.tf.json`), the providers' cache aside."""
    found = [*(repo / INFRA).rglob("*.tf"), *(repo / INFRA).rglob("*.tf.json")]
    return sorted(p for p in found if ".terraform" not in p.parts)


def role_files(repo: Path = REPO) -> list[Path]:
    return sorted((repo / ROLES_DIR).glob("*.json"))


def workflow_files(repo: Path = REPO) -> list[Path]:
    return sorted([*(repo / WORKFLOWS).glob("*.yml"), *(repo / WORKFLOWS).glob("*.yaml")])


def read_files(repo: Path = REPO) -> list[Path]:
    """What this reader reads, and nothing else (the test copies exactly these)."""
    return [*role_files(repo), *tf_files(repo), repo / COMPOSE, *(repo / f for f in ENV_FILES),
            *workflow_files(repo), repo / DOC]


def role_declarations(repo: Path = REPO) -> dict[str, str]:
    """infra/identities/<file>.json → the role's Name."""
    out = {}
    for p in role_files(repo):
        out[_rel(p, repo)] = str((yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("Name", ""))
    return out


def _norm(value: str) -> str:
    """An attribute's expression as a key says it: its quotes off, a role definition by its address."""
    value = value.strip().rstrip(",")
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    return re.sub(r"\.(role_definition_resource_id|role_definition_id|id)$", "", value)


def _key(module: str, kind: str, name: str, attrs: dict[str, str]) -> str:
    """A resource's key; an assignment's carries its role and the expression of its scope."""
    addr = f"{module}:{kind}.{name}"
    if kind not in ASSIGNMENTS:
        return addr
    roles, scopes = ASSIGNMENTS[kind]
    role = next((_norm(attrs[a]) for a in roles if a in attrs), "?")
    scope = next((_norm(attrs[a]) for a in scopes if a in attrs), "?")
    return f"{addr} [{role} @ {scope}]"


def _is_right(kind: str, azapi_type: str) -> bool:
    return kind in IDENTITY_TYPES or kind.startswith("azuread_") or azapi_type.startswith(AZAPI_RIGHTS)


def _hcl_declarations(p: Path, module: str, rel: str) -> dict[str, str]:
    out = {}
    current = None
    depth = 0
    attrs: dict[str, str] = {}
    azapi_type = ""
    for line in p.read_text(encoding="utf-8").splitlines():
        if depth == 0:
            m = RESOURCE.match(line)
            if m:
                current, attrs, azapi_type, depth = m.groups(), {}, "", 1
            continue
        if depth == 1:
            a = ATTRIBUTE.match(line)
            if a:
                attrs.setdefault(a.group(1), a.group(2))
            t = AZAPI_TYPE.match(line)
            if t and current[0] == "azapi_resource":
                azapi_type = t.group(1)
        n = NESTED.match(line)
        if n:
            out[f"{module}:{current[0]}.{current[1]}#{n.group(1) or n.group(2)}"] = rel
        bare = _STRING.sub('""', line)
        depth += bare.count("{") - bare.count("}")
        if depth <= 0:
            if _is_right(current[0], azapi_type):
                out[_key(module, current[0], current[1], attrs)] = rel
            current, depth = None, 0
    return out


def _json_declarations(p: Path, module: str, rel: str) -> dict[str, str]:
    """A `.tf.json`: its `resource` blocks, read as their HCL twins are."""
    out = {}
    doc = json.loads(p.read_text(encoding="utf-8") or "{}")
    for kind, by_name in (doc.get("resource") or {}).items():
        for name, body in (by_name or {}).items():
            for b in body if isinstance(body, list) else [body]:
                b = b or {}
                attrs = {k: v if isinstance(v, str) else json.dumps(v) for k, v in b.items()}
                if _is_right(kind, str(b.get("type", "")).split("@")[0] if kind == "azapi_resource" else ""):
                    out[_key(module, kind, name, attrs)] = rel
                for block in BLOCKS:
                    if block in b or block in (b.get("dynamic") or {}):
                        out[f"{module}:{kind}.{name}#{block}"] = rel
    return out


def terraform_declarations(repo: Path = REPO) -> dict[str, str]:
    """`<module>:<type>.<name>` for an identity or a right — `… [<role> @ <scope>]` for an assignment —,
    `…#identity`, `…#admin_ssh_key`, `…#access_policy` for a resource that carries one; the value is
    the file."""
    out = {}
    for p in tf_files(repo):
        reader = _json_declarations if p.name.endswith(".tf.json") else _hcl_declarations
        out.update(reader(p, _rel(p.parent, repo), _rel(p, repo)))
    return out


def named_rights(repo: Path = REPO) -> dict[str, str]:
    """Each right the repository names that the matrix must name too (§3): every action of a role file
    and of a Terraform role definition, every Graph permission and directory role a `.tf` names."""
    out: dict[str, str] = {}
    for p in role_files(repo):
        role = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for field in ("Actions", "NotActions", "DataActions", "NotDataActions"):
            for action in role.get(field) or []:
                out.setdefault(str(action), _rel(p, repo))
    for p in tf_files(repo):
        if p.name.endswith(".tf.json"):
            continue
        rel = _rel(p, repo)
        definition = False
        depth = 0
        for line in p.read_text(encoding="utf-8").splitlines():
            if depth == 0:
                m = RESOURCE.match(line)
                if m:
                    definition, depth = m.group(1) == "azurerm_role_definition", 1
                    continue
            if definition:
                for action in ARM_ACTION.findall(line):
                    out.setdefault(action, rel)
            for perm in GRAPH_PERMISSION.findall(line):
                out.setdefault(perm, rel)
            d = DIRECTORY_ROLE.match(line)
            if d:
                out.setdefault(d.group(1), rel)
            if depth:
                bare = _STRING.sub('""', line)
                depth += bare.count("{") - bare.count("}")
                if depth <= 0:
                    definition, depth = False, 0
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
    """`workflow:<file>:secrets.<NAME>`, `workflow:<file>:<job>:secrets-inherit` and
    `workflow:<file>:<job|*>:<permission>` (write only)."""
    out = {}
    for p in workflow_files(repo):
        text = p.read_text(encoding="utf-8")
        rel = _rel(p, repo)
        names = set(re.findall(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)", text))
        names |= set(re.findall(r"secrets\[\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\]", text))
        for name in sorted(names):
            out[f"workflow:{p.name}:secrets.{name}"] = rel
        doc = yaml.safe_load(text) or {}
        jobs = doc.get("jobs") or {}
        for job, spec in jobs.items():
            if (spec or {}).get("secrets") == "inherit":
                out[f"workflow:{p.name}:{job}:secrets-inherit"] = rel
        grants = [("*", doc.get("permissions"))]
        grants += [(job, (spec or {}).get("permissions")) for job, spec in jobs.items()]
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
    named = "\n".join(_section(text, MATRIX))
    for right, where in sorted(named_rights(repo).items()):
        if f"`{right}`" not in named:
            out.append(f"{right} ({where}) : un droit que le dépôt déclare, nommé nulle part dans la matrice (§3)")
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
