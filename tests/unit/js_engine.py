"""A JavaScript engine for the console's tests that run the page's own functions (IDT1, #1182).

The suite reads the page as text. A rule that a text does not fix — a sort, the choice of a table — is
run instead: the page's functions taken as they are (`take`), a harness of the test's around them, and
what the harness passes to `emit(text)` comes back. Node when the PATH has it (GitHub's runners do),
else a headless Chromium (EREGION_CHROMIUM, the PATH, Playwright's cache: scripts/console_shots.py's
search). Neither: the test is skipped — on the CI, it fails: never a measure that stops in silence.
No network, no Azure, no model: a script of the test's, run in a process of its own.
"""
from __future__ import annotations

import base64
import glob
import os
import re
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

import pytest

_NODE_EMIT = "const emit = s => process.stdout.write('EMIT:' + Buffer.from(String(s), 'utf8').toString('base64'));\n"
_PAGE_EMIT = "function emit(s) { document.body.textContent = 'EMIT:' + btoa(unescape(encodeURIComponent(String(s)))); }\n"


def take(source: str, *names: str) -> str:
    """The page's own text of each function or `const` named, in the order given: a function up to its
    closing `}` at the line's start, a const up to its `;` at a line's end."""
    out = []
    for name in names:
        m = re.search(r"^(?:async )?function " + re.escape(name) + r"\(", source, re.M)
        if m:
            first = source[m.start():].split("\n", 1)[0]
            one_line = first.rstrip().endswith("}") and first.count("{") == first.count("}")
            out.append(first + "\n" if one_line else source[m.start():].split("\n}\n", 1)[0] + "\n}\n")
            continue
        m = re.search(r"^const " + re.escape(name) + r"\b", source, re.M)
        assert m, f"{name}: neither a function nor a const of the page"
        end = re.compile(r";[ \t]*(?://[^\n]*)?$", re.M).search(source, m.start())
        out.append(source[m.start():end.end()] + "\n")
    return "".join(out)


def _chromium() -> str | None:
    given = os.environ.get("EREGION_CHROMIUM")
    if given:
        return given if Path(given).is_file() else None
    for name in ("chrome-headless-shell", "chromium", "chromium-browser", "google-chrome", "chrome"):
        if found := shutil.which(name):
            return found
    # The suite's HOME is a throwaway one (HY2, tests/unit/home_sandbox.py): Playwright's cache is the real one's.
    cache = Path(os.environ.get("EREGION_TEST_REAL_HOME") or Path.home()) / ".cache" / "ms-playwright"
    for pattern in ("chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell",
                    "chromium-*/chrome-linux*/chrome"):
        hits = sorted(glob.glob(str(cache / pattern)))
        if hits:
            return hits[-1]
    return None


def _emitted(text: str, err: str) -> str:
    m = re.search(r"EMIT:([A-Za-z0-9+/=]*)", text)
    assert m, f"the script emitted nothing: {err[-2000:]}"
    return base64.b64decode(m.group(1)).decode("utf-8")


def _run(argv: list[str], stdin: str | None, timeout: float) -> tuple[int, str, str]:
    """The engine in a process group of its own: past `timeout`, the whole group is killed — a Chromium's
    children with it, never its parent alone (the relecture of IDT1)."""
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = proc.communicate(stdin, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        pytest.fail(f"the JavaScript engine did not end within {timeout:g} s: {argv[0]}")
    return proc.returncode, out, err


def run(script: str, timeout: float = 60) -> str:
    """What `script` passed to `emit(text)`, run in Node or in a headless Chromium."""
    node = shutil.which("node")
    if node:
        code, out, err = _run([node, "-"], _NODE_EMIT + script, timeout)
        assert code == 0, err[-2000:]
        return _emitted(out, err)
    chromium = _chromium()
    if not chromium:
        if os.environ.get("GITHUB_ACTIONS") or os.environ.get("CI"):
            pytest.fail("no JavaScript engine (node, a Chromium) on the CI: the console's behaviour is not measured")
        pytest.skip("no JavaScript engine: node, or a Chromium (EREGION_CHROMIUM, Playwright's cache)")
    assert "</script" not in script.lower(), "the script would close its own tag"
    with tempfile.TemporaryDirectory(prefix="eregion-js-") as tmp:
        page = Path(tmp) / "run.html"
        page.write_text("<!doctype html><html><body><script>window.onerror = (m, s, l) => { document.body"
                        ".textContent = 'ERROR: ' + m + ' at line ' + l; };</script><script>\n"
                        + _PAGE_EMIT + script + "\n</script></body></html>", encoding="utf-8")
        # A local file only: no update, no background request — nothing leaves the machine.
        _, out, err = _run([chromium, "--headless", "--no-sandbox", "--disable-gpu", "--no-first-run",
                            "--disable-background-networking", "--disable-component-update",
                            f"--user-data-dir={Path(tmp) / 'profile'}", "--dump-dom", page.as_uri()], None, timeout)
        return _emitted(out, out + err)
