#!/usr/bin/env python3
"""ORU1 (#608): the session guard for ``make orodruin-run`` — play ONE scenario on an armed Orodruin
in one command. A session never launches an attack (``bench_shared.session_refusal``, SEC12/MOB1, the
same rule as ``make bench-run``): run from a code session (``EREGION_AGENT_SESSION``) or a lot's
worktree, it refuses before any ssh. The Makefile target calls this first; the run itself (``annatar
run <scenario>`` in the Orodruin image, over ssh) is the operator's gesture.

``--guard-only`` is the only mode (kept for symmetry with ``bench_run.py``); it reads nothing but the
environment and the working directory, writes nothing, reaches nothing."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_shared as bs  # noqa: E402  (scripts/ is not a package)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="the session guard of make orodruin-run")
    p.add_argument("--guard-only", action="store_true",
                   help="the guard alone: make runs it before anything else is expanded")
    p.parse_args(argv)

    refusal = bs.session_refusal()
    if refusal:
        print(f"✗ make orodruin-run refusé : {refusal}. Rien n'est lancé.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
