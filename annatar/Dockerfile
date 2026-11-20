# SEC14 (P-02): the base image pinned by its digest (the multi-architecture index read on Docker
# Hub on 02/11), the tag beside it for the reader: a tag moves, a digest does not. Its security
# updates come by a bump — `docker buildx imagetools inspect python:3.12-slim`, the digest here
# and in the other Dockerfile, in one PR (docs/operations.md, « Les images publiées »). SEC-G (P-06):
# Dependabot proposes that bump every Monday, for both Dockerfiles at once (.github/dependabot.yml), and
# the release gate refuses a release whose packages carry a High or Critical CVE fixed upstream
# (scripts/image_cves.py) — no apt-get upgrade here: the image stays what its digest says, but for
# the one exception written and dated below (ZLIB1), one package at its exact version.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

# ZLIB1 (#962) — the exception, Jonathan's decision of 20/11. zlib1g carries CVE-2026-85091 (High) in the
# base's 1:1.3.dfsg+really1.3.1-1+b1; Debian fixed it in 1:1.3.dfsg+really1.3.1-1+deb13u1 (DSA-6613-1,
# 07/11, trixie-security), and no digest of python:3.12-slim carries the fix yet. This exact version,
# from the security source the base already reads: never an apt-get upgrade, never a free version.
# Remove this layer as soon as the base digest carries zlib1g +deb13u1 or newer: in the very PR of
# Dependabot's bump that brings it (docs/operations.md, « Les images publiées »). If Debian replaces
# this version in trixie-security, apt-get no longer finds it and the build breaks loudly — on purpose:
# the decision is taken again, never another version slipped in unseen. Both Dockerfiles, byte for byte
# (tests/unit/test_image_cves.py).
RUN apt-get update && \
    apt-get install -y --no-install-recommends zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# M-3 (#183), HY1: the dependencies come from the lock, every file checked against its hash
# (pip refuses any unpinned or unhashed requirement); the build backend too, so the project
# installs without fetching anything else. litellm is in it: the campaign planner
# (`annatar campaign plan --llm`) needs it. Before the code: a code change keeps this layer.
# Regenerate with `make lock` (docs/operations.md, « Verrou des dépendances »).
COPY requirements/annatar.txt requirements/annatar.txt
RUN pip install --no-cache-dir --require-hashes -r requirements/annatar.txt

COPY pyproject.toml .
COPY annatar/ annatar/
# Gothmog (G0) shares this image: it is the injectors' image on Orodruin (make orodruin-push).
COPY gothmog/ gothmog/
COPY eregion_core/ eregion_core/
COPY analysis/ analysis/
COPY scripts/ scripts/
COPY technique_catalog.yaml .
# Eregion's shipped drills (DG-d), where the drill of the week reads its own (DRL1,
# eregion_core/scheduled_drill.py: /app/drills/). Never expectations/: what the watch should see is
# not this image's to read (tests/unit/test_drill_expectations.py reads both Dockerfiles).
COPY drills/ drills/

# R2BS (#841): the pinned control-plane injector tool and its offline provisioning toolchain,
# carried read-only at /opt/stratus/ (the adapter reads them there). `make stratus-build` (the only
# step with network) builds + verifies them into annatar/stratus/staged/ — never committed. In
# CI nothing is staged (only .gitkeep), so the image builds but no control-plane technique runs.
COPY annatar/stratus/staged/ /opt/stratus/

# The campaign planner/synthesizer reads the shared technique catalog at repo root.

# The project alone: its dependencies are all above (--no-deps), nothing resolved here.
RUN pip install --no-cache-dir --no-deps --no-build-isolation -e .

# Run as the host operator's UID/GID (injected by `make build` via `id -u`/`id -g`) so
# state written to the bind-mounted ~/.annatar is owned by the operator, not root. HOME
# stays /root (chowned) so mount targets and shell init-files keep working unchanged.
# Building as root (UID=0) falls back to the historical root image.
ARG UID=1001
ARG GID=1001
RUN groupadd -o -g "$GID" app && \
    useradd -o -u "$UID" -g "$GID" -d /root -s /bin/bash app && \
    chown -R "$UID:$GID" /root /app
ENV HOME=/root
USER app

CMD ["annatar"]
