#!/bin/bash
# deploy.sh — on Glorfindel's VM (H0), in ~/eregion: deploy a named reference (M-3, #183).
#
#   make imladris-start REF=v0.3.1|<commit>      # verifies on the workstation, sends this script over ssh
#
#   deploy.sh REF COMMIT             fetch, check out COMMIT detached — the commit the workstation
#                                    verified for REF (SEC-C): REF resolving to another commit here
#                                    is refused —, build the image, start
#   deploy.sh --checkout-only REF [COMMIT]   fetch and check out, nothing built or started
#   deploy.sh --show                 the reference the running watch was built from
#   deploy.sh --build-only REF [TAG] build eregion-glorfindel:REF (or :TAG) from the current
#                                    directory, which must be checked out at REF (the CD's own
#                                    worktree, H1): the running image and the checkout of
#                                    ~/eregion are not touched
#   deploy.sh --activate REF         check out REF, make eregion-glorfindel:REF the running
#                                    image and restart the services — no build: the image must
#                                    be there (a candidate the CD built, or the one before:
#                                    the rollback, H1). No pruning: until the health is green,
#                                    the image to go back to must stay. A failed git fetch is
#                                    tolerated: the reference is resolved locally (the rollback
#                                    must not depend on the network)
#   deploy.sh --prune REF...         remove the old images, keeping REF... and the three newest
#                                    (the CD calls it once the health is green: the new and the
#                                    one before)
#
# REF is a tag or a commit, never a branch: a branch moves, and H0 ran whatever had just
# been merged into main. REF is required (SEC14, V-22): this path builds on H0 — the emergency
# path — so it builds only what the operator names, never « the latest tag » it found (a tag
# pushed by anyone with write access). And only what the workstation verified (SEC-C, audit of
# 06/11, V-29): `make imladris-start` reads REF's commit on origin/main there, proves the signature
# and the provenance of the image the CI published for that commit (scripts/published_image.py
# proven, the pinned cosign — as the CD does), then hands this script REF and that commit. Here,
# REF must resolve to that very commit, or nothing moves; the commit is checked out, never a name
# resolved here. The CD (H1) never builds here: it pulls the published image, signature and
# provenance verified. The image carries
# the reference (labels org.opencontainers.image.version / .revision) — `--show`, and so
# `make imladris-status`, read it back from the running container. Each image is also
# tagged by its reference, and the three newest are kept, with the one running and the one
# before it: going back is a retag, not a build.
#
# The script comes from the operator's checkout, not the VM's: deploying an old tag (one
# from before this script) works the same. The CD (H1) runs its own installed copy, and
# holds ~/.eregion-deploy.lock for its whole pass: a deployment by hand meanwhile is refused.
set -euo pipefail
shopt -s inherit_errexit   # a failure inside $(…) stops the script, not only the subshell

IMAGE="${EREGION_IMAGE:-eregion-glorfindel}"
LABEL_REF="org.opencontainers.image.version"
LABEL_REV="org.opencontainers.image.revision"
KEEP_IMAGES=3
# SEC-C (audit of 06/11, V-29): the repository's current name. The VM was cloned under the former one
# (variables.tf, eregion_repo: changed at the next rebuild only); origin is pointed here before every
# fetch, said when it changes. The CD passes its own (EREGION_REPO_URL); the tests, a local origin.
REPO_URL="${EREGION_REPO_URL:-https://github.com/grootcyber/eregion.git}"

die() { echo "✗ $*" >&2; exit 1; }

# Origin at the repository's current name, before any fetch — said once, when it changes.
point_origin() {
  local have
  have=$(git remote get-url origin 2>/dev/null || true)
  [ "$have" = "$REPO_URL" ] && return 0
  if [ -n "$have" ]; then
    git remote set-url origin "$REPO_URL" || die "git remote set-url a échoué : rien n'est déployé"
  else
    git remote add origin "$REPO_URL" || die "git remote add a échoué : rien n'est déployé"
  fi
  echo "  ↪ origin du dépôt d'Imladris : ${have:-aucun} → $REPO_URL (SEC-C)" >&2
}

# One deployment at a time: the CD (H1) takes the lock for its pass and tells this script
# so (EREGION_DEPLOY_LOCKED=1); by hand, the lock is taken here, or refused.
lock() {
  [ -n "${EREGION_DEPLOY_LOCKED:-}" ] && return 0
  exec 9>"$HOME/.eregion-deploy.lock"
  flock -n 9 || die "un déploiement est en cours (le CD d'Imladris, H1) : rien n'est fait. Réessayer après, ou make imladris-cd-status."
}

# The ref to deploy → "<ref> <full commit>", or die. A tag (refs/tags/REF) or a full commit id (40
# hexadecimal digits — SEC-G, audit of 13/11, V-38: a prefix names whichever commit of the VM's
# repository starts with it, one off every branch included). Anything else — a prefix, main,
# origin/main, HEAD, HEAD~1, a name that is both — is refused. With a second argument (--activate
# only: the revision label of the image already on the VM), a prefix of 7 to 39 digits is taken when
# that revision has 40 and starts with it, and the VM has its commit: an image deployed by hand under a
# prefix before SEC-G stays a way back. Nothing is resolved by the prefix: the image names its commit.
resolve() {
  local ref="$1" image_rev="${2:-}" commit
  case "$ref" in
    "" | -* | .* | *[!A-Za-z0-9._-]*) die "référence invalide : « $ref » (un tag ou un commit)" ;;
  esac
  if commit=$(git rev-parse -q --verify "refs/tags/$ref^{commit}" 2>/dev/null); then
    echo "$ref $commit"
    return
  fi
  if [[ "$ref" =~ ^[0-9a-f]{40}$ ]] \
      && commit=$(git rev-parse -q --verify "$ref^{commit}" 2>/dev/null) \
      && [ "$commit" = "$ref" ]; then
    echo "$ref $commit"
    return
  fi
  if git show-ref -q --verify "refs/heads/$ref" || git show-ref -q --verify "refs/remotes/origin/$ref"; then
    die "« $ref » est une branche : elle bouge. Déployer un tag (v*) ou un commit."
  fi
  if [ -n "$image_rev" ] && [[ "$ref" =~ ^[0-9a-f]{7,39}$ ]] && [[ "$image_rev" =~ ^[0-9a-f]{40}$ ]] \
      && [[ "$image_rev" == "$ref"* ]] && git cat-file -e "$image_rev^{commit}" 2>/dev/null; then
    echo "$ref $image_rev"
    return
  fi
  if [[ "$ref" =~ ^[0-9a-f]{1,39}$ ]]; then
    die "« $ref » est un préfixe de commit : le commit entier (40 caractères) ou un tag — un préfixe peut nommer un autre commit (SEC-G)."
  fi
  die "« $ref » n'est ni un tag ni un commit connu (après git fetch)."
}

checkout() {
  local want="${1:-}" tolerant="${2:-}" expect="${3:-}" verified="${4:-}" pair dirty rules
  point_origin
  if ! git fetch -q --tags --force origin; then
    [ -n "$tolerant" ] || die "git fetch a échoué : rien n'est déployé"
    echo "⚠ git fetch a échoué : la référence est résolue sur la VM" >&2
  fi
  # V-22 (SEC14): named, or nothing moves — never « the latest tag ».
  [ -n "$want" ] || die "REF exigée : un tag ou un commit (make imladris-start REF=<tag ou commit>) ; rien n'est déployé"
  pair=$(resolve "$want" "$expect")
  # SEC-C: the commit the workstation verified, or nothing moves — never a name resolved here alone.
  if [ -n "$verified" ] && [ "${pair#* }" != "$verified" ]; then
    die "« $want » désigne ${pair#* } sur la VM, le poste a vérifié $verified : rien n'est déployé (un tag réécrit, ou un autre dépôt ?)"
  fi
  # The image was built from one commit (H1): a tag rewritten since names another — its compose,
  # its rules, its catalogue beside the old image. The image's own commit is checked out
  # instead, said; refused if the VM does not have it.
  if [ -n "$expect" ] && [ "${pair#* }" != "$expect" ]; then
    git cat-file -e "$expect^{commit}" 2>/dev/null || die "« $want » désigne maintenant ${pair#* }, son image a été construite depuis $expect, absent de la VM (tag réécrit) : rien n'a bougé"
    echo "⚠ « $want » désigne maintenant ${pair#* } (tag réécrit) : le commit de son image, $expect, est extrait" >&2
    pair="${pair% *} $expect"
  fi
  # A tracked file changed on the VM would ride along into the image: refused. The detection
  # rules too (P1): the containers no longer write them (mounted read-only) — approved rules
  # live in the client's layer, ~/.glorfindel/client_rules.yaml, which no checkout touches.
  # A rules file modified on the VM holds rules approved before P1: to migrate first, said
  # with what to do, before anything moves.
  dirty=$(git status --porcelain --untracked-files=no | awk '{print $NF}')
  rules=$(echo "$dirty" | grep '^glorfindel/rules/' || true)
  [ -z "$rules" ] || die "$(echo "$rules" | tr '\n' ' ')— modifié sur la VM (règles approuvées avant P1) : rien n'est déployé. Les migrer vers la couche du client (~/.glorfindel/client_rules.yaml) : infra/glorfindel-host/README.md, « Migrer les règles approuvées vers la couche du client ». Jamais git checkout -- glorfindel/rules : il les efface."
  [ -z "$dirty" ] || die "fichiers suivis modifiés sur la VM (rien n'est déployé) : $(echo "$dirty" | tr '\n' ' ')"
  git -c advice.detachedHead=false checkout -q --detach "${pair#* }"
  echo "$pair"
}

# Build from the current directory, tagged by its reference (or by NAME); `latest` also makes
# it the image compose runs (the deployment by hand), never for the CD's candidate.
build() {
  local ref="$1" commit="$2" latest="${3:-}" name="${4:-$1}"
  local tags=(-t "$IMAGE:$name")
  [ -n "$latest" ] && tags+=(-t "$IMAGE")
  # The labels for `--show`; the build-args so the console can say what it runs (its header).
  docker build --build-arg UID="$(id -u)" --build-arg GID="$(id -g)" \
    --build-arg "EREGION_REF=$ref" --build-arg "EREGION_REVISION=$commit" \
    --label "$LABEL_REF=$ref" --label "$LABEL_REV=$commit" \
    -f glorfindel/Dockerfile "${tags[@]}" .
}

start() {
  # Created as the operator before compose mounts them: left to docker, they would be root's,
  # and the console could not write its requests (DG-b), nor the watch its index (IA0).
  mkdir -p "$HOME/.eregion/analysis" "$HOME/.eregion/console/requests"
  # SEC-A1b: the injectors' heartbeat directory, which the console and the bot mount
  # read-only inside ~/.glorfindel — made here, as the operator (left to docker, it would be root's,
  # and the watch could no longer write its heartbeat there).
  mkdir -p "$HOME/.glorfindel/injectors"
  # SEC19 (N-03): the watch's key, drawn at its first start in a directory only the watch mounts —
  # made here, 0700, as the operator (left to docker, it would be root's: no key, beats unsigned).
  mkdir -p -m 700 "$HOME/.eregion/watch-key"
  # FS1b (#563): the bot's key of the action queue, and the watch's register of it — each in a
  # directory only its service mounts, made here, 0700, as the operator (left to docker, root's:
  # the bot could not draw its key, the watch could not keep its register). MEM2 (#1027): the
  # memory by keys too, the watch's alone (glorfindel/memory_keys.py).
  mkdir -p -m 700 "$HOME/.eregion/bot" "$HOME/.eregion/watch-queue" "$HOME/.eregion/watch-memory"
  # SEC18 (N-05): runs/ has one directory per writer, each service mounts its own (compose). The
  # former layout (files flat in runs/) is moved to its writers' directories here, on the host —
  # no service mounts the whole of runs/ — and those directories made as the operator. Nothing is
  # deleted; what is not told without ambiguity is left and said. A reference from before SEC18
  # has no runs_layout: its compose mounts runs/ whole, nothing to move.
  # A writer's directory that is a link (or a file) is never mounted: docker would resolve it on the
  # host. The services are stopped first when the former layout holds something to move.
  if [ -f eregion_core/runs_layout.py ]; then
    local d
    for d in runs/glorfindel runs/console runs/annatar runs/gothmog runs/orodruin runs/verdicts runs/bot runs/restore; do
      { [ ! -L "$d" ] && { [ ! -e "$d" ] || [ -d "$d" ]; }; } \
        || die "$d n'est pas un répertoire (un lien ?) : rien n'est démarré — le retirer à la main (SEC18)"
    done
    if python3 -m eregion_core.runs_layout pending runs; then
      docker compose --profile bot stop watch war-room bot || true
    fi
    python3 -m eregion_core.runs_layout migrate runs || die "runs/ : la migration de SEC18 a échoué — rien n'est démarré (docs/operations.md, « runs/ : un répertoire par écrivain — le redéploiement coordonné »)"
    # FS1b: the watch's receipts of the action queue, the one subdirectory the bot mounts.
    [ ! -L runs/glorfindel/queue ] || die "runs/glorfindel/queue est un lien : rien n'est démarré (FS1b)"
    # SEC2b: the client's network the watch reads, the bot's other read-only subdirectory.
    [ ! -L runs/glorfindel/network ] || die "runs/glorfindel/network est un lien : rien n'est démarré (SEC2b)"
    mkdir -p runs/glorfindel/queue runs/glorfindel/network
    # Made by docker for the bot's mount (a CD installed before SEC2b): root's — the watch could never
    # write the client's network there, and every block outside the Internet would stay refused.
    [ -w runs/glorfindel/network ] || die "runs/glorfindel/network n'est pas inscriptible (créé par docker, à root ?) : sudo chown -R \"\$(id -u):\$(id -g)\" runs/glorfindel/network, puis relancer (SEC2b)"
  fi
  docker compose --profile bot up -d watch war-room bot
}

# The three newest images by reference stay, and every one named (the running one, the one
# before): going back is a retag. Older ones go, then the dangling layers.
prune() {
  local n=0 tag k kept
  while read -r tag; do
    [ -z "$tag" ] || [ "$tag" = "latest" ] || [ "$tag" = "<none>" ] && continue
    n=$((n + 1))
    kept=""
    for k in "$@"; do [ "$tag" = "$k" ] && kept=1; done
    [ -n "$kept" ] && continue
    [ "$n" -le "$KEEP_IMAGES" ] && continue
    docker image rm "$IMAGE:$tag" >/dev/null 2>&1 || true
  done < <(docker image ls "$IMAGE" --format '{{.CreatedAt}}\t{{.Tag}}' | sort -r | cut -f2)
  docker image prune -f >/dev/null
}

running_ref() {
  docker inspect -f "{{index .Config.Labels \"$LABEL_REF\"}}" eregion-watch 2>/dev/null || true
}

show() {
  local ref rev head notes="" mark="✓"
  ref=$(docker inspect -f "{{index .Config.Labels \"$LABEL_REF\"}}" eregion-watch 2>/dev/null || true)
  rev=$(docker inspect -f "{{index .Config.Labels \"$LABEL_REV\"}}" eregion-watch 2>/dev/null || true)
  head=$(git rev-parse HEAD 2>/dev/null || true)
  if [ -z "$ref" ] || [ "$ref" = "<no value>" ]; then
    echo "  ⚠ référence déployée : inconnue (image sans référence) — checkout ${head:0:12}"
    return 0
  fi
  if [ "$rev" != "$head" ]; then
    mark="⚠"; notes=" — le checkout est ailleurs (${head:0:12}) : redéployer"
  fi
  if git symbolic-ref -q HEAD >/dev/null; then
    mark="⚠"; notes="$notes — checkout sur une branche"
  fi
  echo "  $mark référence déployée : $ref (${rev:0:12})$notes"
}

case "${1:-}" in
  --show)
    show ;;
  --checkout-only)
    lock
    [ -z "${3:-}" ] || [[ "${3:-}" =~ ^[0-9a-f]{40}$ ]] || die "commit vérifié invalide : « ${3:-} » (40 chiffres hexadécimaux)"
    checkout "${2:-}" "" "" "${3:-}" ;;
  --build-only)
    [ -n "${2:-}" ] || die "--build-only REF : la référence manque"
    name="${3:-$2}"
    case "$name" in -* | .* | *[!A-Za-z0-9._-]*) die "nom d'image invalide : « $name »" ;; esac
    pair=$(resolve "$2")
    [ "$(git rev-parse HEAD)" = "${pair#* }" ] || die "le répertoire n'est pas au commit de « $2 » : rien n'est construit"
    build "${pair% *}" "${pair#* }" "" "$name"
    echo "✓ construite : $IMAGE:$name (${pair#* }) — rien n'a basculé" ;;
  --activate)
    [ -n "${2:-}" ] || die "--activate REF : la référence manque"
    lock
    docker image inspect "$IMAGE:$2" >/dev/null 2>&1 || die "pas d'image $IMAGE:$2 sur la VM : rien n'a bougé"
    rev=$(docker image inspect -f "{{index .Config.Labels \"$LABEL_REV\"}}" "$IMAGE:$2" 2>/dev/null || true)
    [ "$rev" = "<no value>" ] && rev=""
    pair=$(checkout "$2" tolerant "$rev")
    docker tag "$IMAGE:${pair% *}" "$IMAGE"
    start
    echo "✓ activé : ${pair% *} (${pair#* })" ;;
  --prune)
    shift
    lock
    prune "$@"
    echo "✓ images gardées : les trois plus récentes et $*" ;;
  *)
    lock
    # SEC-C: REF and the commit the workstation verified (make imladris-start), never REF alone.
    [ -n "${1:-}" ] || die "REF exigée : un tag ou un commit (make imladris-start REF=<tag ou commit>) ; rien n'est déployé"
    [[ "${2:-}" =~ ^[0-9a-f]{40}$ ]] || die "le commit vérifié manque : ce chemin ne déploie que ce que le poste a vérifié (make imladris-start REF=${1:-}, la signature de son image publiée) ; rien n'est déployé"
    pair=$(checkout "${1:-}" "" "" "$2")
    before=$(running_ref)                  # the containers have not moved yet
    commit="${pair#* }"
    build "${pair% *}" "$commit" latest
    start
    prune "${pair% *}" "$before"
    echo "✓ déployé : ${pair% *} (${commit:0:12})" ;;
esac
