"""SEC-K (#847; Jonathan's decision of 15/11): .github/CODEOWNERS names the files that a workflow
holding a credential runs, and nothing else.

A job holds a credential when it reads a secret (`secrets.…`, `github.token`), or its token may
write (`id-token: write`, `packages: write`, `issues: write`…, or no `permissions` at all: the
repository's default). What such a job runs, of the repository:
- a path named in one of its `run:` — a code file or a directory; a data file (`.md`, `.txt`,
  `.json`…) only when it is installed (`pip install -r <file>`): the packages it locks run there;
- a local action (`uses: ./…`);
- the code of its sparse checkout (the only files on its runner);
- then, from each file found: what a Python script imports from its directory or from the root of
  the repository, and the files next to a shell script that it names (`"$SRC/redact.py"`), but data.
A job that checks nothing out runs nothing of the repository, whatever its text names.
To that, Imladris's CD: the files it installs (`AGENT_FILES`, infra/glorfindel-host/cd/eregion_cd.py).

Each of them must be owned by a line of the CODEOWNERS; each line must own one of them, but the
directories owned whole by decision (`DECIDED`). The form is kept plain, so that this test reads it
as GitHub does: one owner, the maintainer; an anchored path, a file or a directory (trailing `/`),
no pattern. And no file next to a script that runs in a full checkout takes the name of a module of
the standard library: Python would import it first, from a path no line owns.

Once the maintainer has turned « Require review from Code Owners » on in main's rule, a pull request
that touches one of these files waits for his approval (docs/design/modele-de-menace.md, §7).

What it does not see:
- the inputs of an action (`with:`): the Dockerfiles that `docker/build-push-action` builds in the
  job that signs, and the code they copy into the image, are not read — the image's code is the one
  a session merges (the threat model's decision « Qui fusionne sur `main` publie une image… »);
- a module run by its name (`python -m pkg.mod` in a `run:`): only paths are read;
- the Makefile, left out by decision (18/11): its recipes run with the maintainer's rights.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"
OWNER = "@grootcyber"
CD = "infra/glorfindel-host/cd/eregion_cd.py"
# Owned whole by decision, not derived: the CI itself, the canary, the CD of Imladris (Q3, 15/11);
# the bench's Terraform (18/11), whose `local-exec` provisioners run with the rights of whoever
# applies, at `terraform apply`, without showing in the plan (infra/terraform/entra_bench_unit.tf,
# vm.tf).
DECIDED = ("/.github/", "/infra/canary/", "/infra/glorfindel-host/cd/", "/infra/terraform/")
# Read, never run — unless installed (`-r`).
DATA = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".csv", ".hujson"}
SECRET = re.compile(r"\bsecrets\s*[.\[]|\bgithub\s*\.\s*token\b|\bgithub\s*\[\s*'token'\s*\]")
TOKEN = re.compile(r"[\w./-]+")
REQUIREMENT = re.compile(r"(?:^|\s)(?:-r|--requirement)(?:\s+|=)([\w./-]+)")


def _workflows(root: Path) -> list[Path]:
    return sorted((root / ".github" / "workflows").glob("*.yml"))


def _writes(perms) -> bool:
    if perms is None or perms == "write-all":
        return True                   # no permissions: the repository's default, which may write
    if isinstance(perms, dict):
        return any(value == "write" for value in perms.values())
    return False


def credential(workflow: dict, job: dict) -> str:
    """Why this job holds a credential ("secret", "write"), or "" when it holds none."""
    text = yaml.safe_dump(job) + yaml.safe_dump(workflow.get("env") or {})
    if SECRET.search(text):
        return "secret"
    if _writes(job.get("permissions", workflow.get("permissions"))):
        return "write"
    return ""


def _named(root: Path, text: str) -> set[str]:
    """The paths of the repository a `run:` names that run: code files and directories, the
    requirements it installs."""
    out = set()
    installed = set(REQUIREMENT.findall(text))
    for token in TOKEN.findall(text):
        rel = token[2:] if token.startswith("./") else token
        if "/" not in rel or rel.startswith("/") or ".." in rel.split("/"):
            continue
        path = root / rel
        if path.is_dir() or (path.is_file() and (path.suffix not in DATA or rel in installed)):
            out.add(rel.rstrip("/"))
    if re.search(r"(?:^|[\s;&|(])make\s", text) and (root / "Makefile").is_file():
        out.add("Makefile")
    return out


def _sparse(job: dict) -> list[list[str]]:
    """Each sparse checkout of the job: its paths (a full checkout gives none)."""
    out = []
    for step in job.get("steps") or []:
        sparse = (step.get("with") or {}).get("sparse-checkout")
        if str(step.get("uses", "")).startswith("actions/checkout@") and sparse:
            out.append([line.strip() for line in str(sparse).splitlines() if line.strip()])
    return out


def _checks_out(job: dict) -> bool:
    return any(str(step.get("uses", "")).startswith("actions/checkout@") for step in job.get("steps") or [])


def job_files(root: Path, job: dict) -> set[str]:
    """The files of the repository this job runs, before what they import or call. A job that
    checks nothing out has none of them on its runner: a path in its text is only text."""
    files: set[str] = set()
    if not _checks_out(job):
        return files
    for step in job.get("steps") or []:
        if isinstance(step.get("run"), str):
            files |= _named(root, step["run"])
        uses = str(step.get("uses", ""))
        if uses.startswith("./"):
            files.add(uses[2:].rstrip("/"))
    for paths in _sparse(job):
        files |= {p.rstrip("/") for p in paths
                  if (root / p).exists() and ((root / p).is_dir() or Path(p).suffix not in DATA)}
    return files


def _imports(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module)
    return names


def _code_lines(path: Path) -> str:
    return "\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("#"))


def follows(root: Path, rel: str) -> set[str]:
    """What this file loads in turn: a Python script's imports found in its directory or at the
    root (as `<module>.py` or a package); a shell script's neighbours that it names."""
    path = root / rel
    out = set()
    if path.suffix == ".py":
        for name in _imports(path):
            parts = name.split(".")
            for base in (path.parent, root):
                for cand in (base.joinpath(*parts).with_suffix(".py"), base.joinpath(*parts, "__init__.py"),
                             base / f"{parts[0]}.py", base / parts[0] / "__init__.py"):
                    if cand.is_file():
                        out.add(cand.relative_to(root).as_posix())
    elif path.suffix == ".sh":
        code = _code_lines(path)
        for other in path.parent.iterdir():
            if (other.is_file() and other != path and other.suffix not in DATA
                    and re.search(rf"/{re.escape(other.name)}\b", code)):
                out.add(other.relative_to(root).as_posix())
    return out


def closure(root: Path, files: set[str]) -> set[str]:
    seen: set[str] = set()
    todo = sorted(files)
    while todo:
        rel = todo.pop()
        if rel in seen:
            continue
        seen.add(rel)
        if (root / rel).is_file():
            todo.extend(sorted(follows(root, rel) - seen))
    return seen


def cd_files(root: Path) -> set[str]:
    """What Imladris's CD installs and runs (`AGENT_FILES`, read from its source)."""
    tree = ast.parse((root / CD).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "AGENT_FILES" for t in node.targets):
            return {ast.literal_eval(v) for v in node.value.values}
    raise AssertionError(f"{CD}: AGENT_FILES not found")


def credentialed(root: Path) -> dict[tuple[str, str], tuple[str, set[str], bool]]:
    """(workflow, job) → (why, the files it runs with their closure, a full checkout?)."""
    out = {}
    for wf_path in _workflows(root):
        workflow = yaml.safe_load(wf_path.read_text(encoding="utf-8")) or {}
        for name, job in (workflow.get("jobs") or {}).items():
            why = credential(workflow, job)
            if why:
                out[(wf_path.name, name)] = (why, closure(root, job_files(root, job)), not _sparse(job))
    return out


def sensitive(root: Path) -> set[str]:
    files = closure(root, cd_files(root)) if (root / CD).is_file() else set()
    for _, ran, _ in credentialed(root).values():
        files |= ran
    return files


def owned_lines(path: Path = CODEOWNERS) -> list[tuple[str, list[str]]]:
    return [(parts[0], parts[1:]) for parts in (line.split() for line in path.read_text(encoding="utf-8").splitlines())
            if parts and not parts[0].startswith("#")]


def covers(pattern: str, rel: str) -> bool:
    return pattern == f"/{rel}" or (pattern.endswith("/") and f"/{rel}/".startswith(pattern))


def shadows(root: Path, rel: str) -> list[str]:
    """Files next to a Python script that Python would import in place of the standard library."""
    out = []
    for other in sorted((root / rel).parent.iterdir()):
        name = other.stem if other.suffix == ".py" else other.name
        regular = other.suffix == ".py" or (other.is_dir() and (other / "__init__.py").is_file())
        if regular and name in sys.stdlib_module_names:
            out.append(other.relative_to(root).as_posix())
    return out


# ── The repository ─────────────────────────────────────────────────────────────────────────────

def test_the_codeowners_is_plain_and_has_no_catch_all():
    lines = owned_lines()
    assert lines, "no line: nothing would wait for the maintainer"
    for pattern, owners in lines:
        assert owners == [OWNER], f"{pattern}: one owner, the maintainer — not {owners}"
        assert pattern.startswith("/") and pattern != "/", f"{pattern}: an anchored path, never all"
        assert not re.search(r"[*?\[\]!\\]", pattern), f"{pattern}: no pattern, a path"
        assert (ROOT / pattern.strip("/")).exists(), f"{pattern}: no such file or directory"
        assert pattern.endswith("/") == (ROOT / pattern.strip("/")).is_dir(), \
            f"{pattern}: a directory ends with /, a file does not"


def test_the_jobs_that_hold_a_credential_are_found():
    """Not a list to keep: what the derivation must at least see, each way it sees a file."""
    jobs = credentialed(ROOT)
    assert {("publish.yml", "publish"), ("notify.yml", "notify"), ("roadmap.yml", "roadmap"),
            ("canary-azurerm.yml", "canary"), ("pip-audit.yml", "audit")} <= set(jobs)
    assert ("images.yml", "image") not in jobs and ("ci.yml", "test") not in jobs
    files = sensitive(ROOT)
    assert {"scripts/published_image.py", "scripts/image_check.py", "scripts/retry.sh",    # run:
            "scripts/notify_discord.py", "scripts/roadmap_discord.py",
            "infra/canary/jit-terraform/run.sh", "scripts/pip_audit_issues.py",
            "requirements/audit.txt",                                                    # -r
            ".claude/skills/elrond/palantir.py", "glorfindel/chat_text.py",              # sparse
            "infra/canary/jit-terraform/redact.py",                                      # $SRC/
            "infra/glorfindel-host/deploy.sh", CD} <= files                              # the CD
    assert "ROADMAP.md" not in files and "requirements/dev.txt" not in files   # data, read


def test_every_file_a_credentialed_job_runs_is_owned():
    lines = [pattern for pattern, _ in owned_lines()]
    missing = sorted(rel for rel in sensitive(ROOT) if not any(covers(p, rel) for p in lines))
    assert missing == [], f"run with a credential, owned by no line of .github/CODEOWNERS: {missing}"


def test_every_line_owns_a_file_a_credentialed_job_runs():
    """The list never grows past the decision: a line that owns nothing run with a credential makes
    every pull request that touches it wait for the maintainer."""
    files = sensitive(ROOT)
    stale = [p for p, _ in owned_lines() if p not in DECIDED and not any(covers(p, rel) for rel in files)]
    assert stale == [], f"owned, but no credentialed job runs it: {stale}"
    assert {p for p, _ in owned_lines()} >= set(DECIDED)


def test_no_file_next_to_a_script_shadows_the_standard_library():
    found = {}
    for (wf, job), (_, ran, full) in credentialed(ROOT).items():
        for rel in sorted(ran):
            if full and rel.endswith(".py") and (bad := shadows(ROOT, rel)):
                found[f"{wf}:{job}:{rel}"] = bad
    assert found == {}


# ── The derivation, on a repository made here ──────────────────────────────────────────────────

def _repo(tmp_path: Path, workflow: str, files: dict[str, str]) -> Path:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "w.yml").write_text(workflow, encoding="utf-8")
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("job, why", [
    ("    permissions: {contents: read}\n    env: {T: '${{ secrets.T }}'}\n", "secret"),
    ("    permissions: {contents: read}\n    env: {T: '${{ github.token }}'}\n", "secret"),
    ("    permissions: {contents: read, id-token: write}\n", "write"),
    ("    permissions: {issues: write}\n", "write"),
    ("    permissions: write-all\n", "write"),
    ("    permissions: {contents: read}\n", ""),
])
def test_a_job_holds_a_credential_by_a_secret_or_a_write(tmp_path, job, why):
    root = _repo(tmp_path, "permissions: {contents: read}\njobs:\n  j:\n" + job
                 + "    steps:\n      - run: python3 s/a.py\n", {"s/a.py": ""})
    assert {k: v[0] for k, v in credentialed(root).items()} == ({("w.yml", "j"): why} if why else {})


def test_a_job_without_permissions_holds_the_repositorys_default(tmp_path):
    root = _repo(tmp_path, "jobs:\n  j:\n    steps:\n      - run: python3 s/a.py\n", {"s/a.py": ""})
    assert credentialed(root)[("w.yml", "j")][0] == "write"


def test_what_a_credentialed_job_runs_and_what_it_only_reads(tmp_path):
    workflow = (
        "permissions: {contents: read}\njobs:\n  j:\n    permissions: {id-token: write}\n    steps:\n"
        "      - uses: actions/checkout@0000000000000000000000000000000000000000\n"
        "      - run: |\n          bash s/retry.sh pip install -r req/lock.txt\n"
        "          python3 s/main.py --notes doc/notes.md req/other.txt\n"
        "      - run: exec infra/c/run.sh\n"
        "      - uses: ./act\n")
    root = _repo(tmp_path, workflow, {
        "s/retry.sh": "\"$@\"\n", "s/main.py": "import json\nimport helper\nfrom pkg.mod import x\n",
        "s/helper.py": "", "s/unused.py": "", "pkg/__init__.py": "", "pkg/mod.py": "",
        "req/lock.txt": "", "req/other.txt": "", "doc/notes.md": "",
        "infra/c/run.sh": "SRC=$(dirname \"$0\")\n# not ./old.py\npython3 \"$SRC/redact.py\"\ncp \"$SRC/main.tf\" .\n",
        "infra/c/redact.py": "", "infra/c/main.tf": "", "infra/c/old.py": "", "act/action.yml": ""})
    (_, ran, full), = credentialed(root).values()
    assert full
    assert ran == {"s/retry.sh", "s/main.py", "s/helper.py", "pkg/mod.py", "pkg/__init__.py",
                   "req/lock.txt", "infra/c/run.sh", "infra/c/redact.py", "infra/c/main.tf", "act"}


def test_a_job_that_checks_nothing_out_runs_nothing_of_the_repository(tmp_path):
    workflow = ("permissions: {contents: read}\njobs:\n  j:\n    permissions: {issues: write}\n    steps:\n"
                "      - run: echo \"replay python scripts/a.py\"\n")
    root = _repo(tmp_path, workflow, {"scripts/a.py": ""})
    assert credentialed(root) == {("w.yml", "j"): ("write", set(), True)}


def test_a_sparse_checkout_gives_its_code_never_its_data(tmp_path):
    workflow = (
        "permissions: {contents: read}\njobs:\n  j:\n    steps:\n"
        "      - uses: actions/checkout@0000000000000000000000000000000000000000\n"
        "        with:\n          sparse-checkout: |\n            ROADMAP.md\n            s/a.py\n            g/text.py\n"
        "      - env: {T: '${{ secrets.T }}'}\n        run: python3 s/a.py\n")
    root = _repo(tmp_path, workflow, {"ROADMAP.md": "", "s/a.py": "", "g/text.py": ""})
    (_, ran, full), = credentialed(root).values()
    assert (ran, full) == ({"s/a.py", "g/text.py"}, False)


def test_a_file_named_after_the_standard_library_next_to_a_script_is_found(tmp_path):
    root = _repo(tmp_path, "", {"s/a.py": "import json\n", "s/json.py": "", "s/fine.py": "",
                                "s/email/__init__.py": "", "s/notes/x.txt": ""})
    assert shadows(root, "s/a.py") == ["s/email", "s/json.py"]


@pytest.mark.parametrize("pattern, rel, held", [
    ("/scripts/a.py", "scripts/a.py", True), ("/scripts/", "scripts/a.py", True),
    ("/scripts/", "scripts", True), ("/scripts/a.py", "scripts/a.pyc", False),
    ("/script/", "scripts/a.py", False), ("/infra/canary/", "infra/canary/jit/run.sh", True),
])
def test_a_line_covers_its_file_or_what_its_directory_holds(pattern, rel, held):
    assert covers(pattern, rel) is held
