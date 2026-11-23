# SEC14 (P-02): the base image pinned by its digest (the multi-architecture index read on Docker
# Hub on 02/11), the tag beside it for the reader: a tag moves, a digest does not. Its security
# updates come by a bump — `docker buildx imagetools inspect python:3.12-slim`, the digest here
# and in the other Dockerfile, in one PR (docs/operations.md, « Les images publiées »). SEC-G (P-06):
# Dependabot proposes that bump every Monday, for both Dockerfiles at once (.github/dependabot.yml), and
# the release gate refuses a release whose packages carry a High or Critical CVE fixed upstream
# (scripts/image_cves.py) — no apt-get upgrade here: the image stays what its digest says, but for
# the exceptions written and dated below (ZLIB1, LIBC1), each package at its exact version.
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

# LIBC1 (#1098) — the second exception, Jonathan's decision of 23/11. libc6 and libc-bin carry CVE-2026-19499
# and CVE-2026-5435 (High) in the base's 2.41-12+deb13u4; Debian fixed them in 2.41-12+deb13u5 (glibc's
# stable update of 10/10, no DSA: it came with the point release 13.8 of 21/11, in trixie, a suite the base
# already reads), and no digest of python:3.12-slim carries the fix yet. This exact version, both packages
# named: never an apt-get upgrade, never a free version.
# Remove this layer as soon as the base digest carries libc6 and libc-bin +deb13u5 or newer: in the very PR
# of Dependabot's bump that brings it (docs/operations.md, « Les images publiées »). If Debian replaces
# this version in trixie (the next point release), apt-get no longer finds it and the build breaks loudly —
# on purpose: the decision is taken again, never another version slipped in unseen. Both Dockerfiles, byte
# for byte (tests/unit/test_image_cves.py).
RUN apt-get update && \
    apt-get install -y --no-install-recommends libc6=2.41-12+deb13u5 libc-bin=2.41-12+deb13u5 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# M-3 (#183): the dependencies come from the lock, every file checked against its hash
# (pip refuses any unpinned or unhashed requirement); the build backend too, so the project
# installs without fetching anything else. Before the code: a code change keeps this layer.
# Regenerate with `make lock` (docs/operations.md, « Verrou des dépendances »).
COPY requirements/glorfindel.txt requirements/glorfindel.txt
RUN pip install --no-cache-dir --require-hashes -r requirements/glorfindel.txt

COPY pyproject.toml .
COPY annatar/ annatar/
COPY eregion_core/ eregion_core/
COPY glorfindel/ glorfindel/
# The Eregion console (`eregion console`): its API and pages, served from this image.
COPY eregion_console/ eregion_console/
# The analysis AI (IA0): the watch on Imladris writes the report of the campaigns Orodruin
# publishes (#167, analysis/hosted_report.py) — chromadb and litellm come with [glorfindel].
COPY analysis/ analysis/
# Shared technique catalog (Annatar↔Glorfindel contract) — root-level, consumed by
# detection_authoring.load_catalog(). Baked in so the image is self-contained; the
# compose mount overrides it for live edits.
COPY technique_catalog.yaml .
# Eregion's reference drills (DG-d), listed and loaded by the console's Dagorlad; the client's own
# live in ~/.eregion/console/drills, mounted with the console's directory.
COPY drills/ drills/
# What the watch should see when the drill of the week plays (DRL1): read on Imladris (VP1), never
# by the injectors' image.
COPY expectations/ expectations/

# The project alone: its dependencies are all above (--no-deps), nothing resolved here.
RUN pip install --no-cache-dir --no-deps --no-build-isolation -e .

# `gf` alias for interactive shells — works for `docker exec -it <c> bash` and the
# compose container, independent of any host-mounted ~/.glorfindel/.bashrc.
RUN echo "alias gf='glorfindel'" >> /etc/bash.bashrc

# Run as the host operator's UID/GID (injected by `make build` via `id -u`/`id -g`) so
# state written to the bind-mounted ~/.glorfindel / ~/.cache/chroma / ./runs is owned by
# the operator, not root — otherwise the local `glorfindel` CLI can't mutate files the
# container wrote (PermissionError on reset/unblock). The user's HOME stays /root
# (chowned to it) so every mount target, shell init-file and HOME-writing lib keeps
# working unchanged. Building as root (UID=0) falls back to the historical root image.
ARG UID=1001
ARG GID=1001
RUN groupadd -o -g "$GID" app && \
    useradd -o -u "$UID" -g "$GID" -d /root -s /bin/bash app && \
    chown -R "$UID:$GID" /root /app
ENV HOME=/root
USER app

# The reference deploy.sh built this image from (M-3), shown in the console's header. Last, so
# a new reference rebuilds no earlier layer; empty for a local `make build`.
ARG EREGION_REF=
ARG EREGION_REVISION=
ENV EREGION_REF=$EREGION_REF EREGION_REVISION=$EREGION_REVISION

CMD ["glorfindel"]
