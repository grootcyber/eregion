"""SEC-C (#635; audit of 06/11, V-29, V-24, V-26): the deployment of Imladris and Orodruin. Origin of
Imladris's checkout at the repository's current name before every fetch, by hand and by the CD; the
deployment by hand verified on the workstation (the published image's signature and provenance) and
handed to the VM as a commit, never a name to resolve there; Orodruin's update never under its floor
(the image in service, this workstation's memory) unless ROLLBACK=1, and without REF the highest
release whose image is verified; Imladris's host key required. M5446–M5463; M5464–M5465 (the job
that signs the images, V-25) go with Jonathan's patch of publish.yml.
"""
DEPLOY = "infra/glorfindel-host/deploy.sh"
CD = "infra/glorfindel-host/cd/eregion_cd.py"
PIM = "scripts/published_image.py"
MAKE = "Makefile"
KH = "infra/glorfindel-host/known_host.sh"
_D = "tests/unit/test_host_deploy.py::"
_CD = "tests/unit/test_host_cd.py::"
_P = "tests/unit/test_published_image.py::"
_S = "tests/unit/test_host_ssh.py::"

MUTANTS = [
    # V-29: origin, and the deployment by hand.
    ("M5446", "deploy.sh fetches from the origin the VM was cloned with, never pointed at the current name (SEC-C)",
     DEPLOY, "  point_origin\n  if ! git fetch -q --tags --force origin; then\n",
     "  if ! git fetch -q --tags --force origin; then\n"),
    ("M5447", "the CD fetches from the origin Imladris was cloned with, never pointed at the current name (SEC-C)",
     CD, "    point_origin(state)\n    try:\n        git(\"fetch\"", "    try:\n        git(\"fetch\""),
    ("M5448", "the deployment by hand of Imladris hands the VM a name to resolve: the verified commit dropped (SEC-C)",
     DEPLOY, ('    [[ "${2:-}" =~ ^[0-9a-f]{40}$ ]] || die "le commit vérifié manque',
              '    pair=$(checkout "${1:-}" "" "" "$2")\n'),
     ('    true || die "le commit vérifié manque', '    pair=$(checkout "${1:-}")\n')),
    ("M5449", "a REF the VM resolves to another commit than the one verified is deployed (SEC-C)", DEPLOY,
     '  if [ -n "$verified" ] && [ "${pair#* }" != "$verified" ]; then\n', "  if false; then\n"),
    ("M5450", "make imladris-start sends REF alone: the tag resolved on the VM, not the commit verified (SEC-C)",
     MAKE, """bash -s -- '"$$EREGION_DEPLOY_REF $$commit" < infra/glorfindel-host/deploy.sh""",
     """bash -s -- '"$$EREGION_DEPLOY_REF" < infra/glorfindel-host/deploy.sh"""),
    ("M5451", "make imladris-start builds without verifying any signature: the commit read on the workstation (SEC-C)",
     MAKE, '\t@out=$$(python3 scripts/published_image.py proven glorfindel --ref "$$EREGION_DEPLOY_REF" --fetch) \\\n',
     '\t@out="commit=$$(git rev-parse HEAD)" \\\n'),
    ("M5452", "published_image.py proven: the commit of main taken, its image's signature never verified (SEC-C)",
     PIM, "    digest = resolve(image, commit)\n    verify(image, digest, commit, cosign, runner=runner)\n"
          "    return ref, commit, digest\n",
     "    digest = resolve(image, commit)\n    return ref, commit, digest\n"),
    ("M5453", "the CD's switch gets deploy.sh without the current name: it points origin back elsewhere (SEC-C)",
     CD, '             env={"EREGION_DEPLOY_LOCKED": "1", "EREGION_REPO_URL": REPO_URL})\n',
     '             env={"EREGION_DEPLOY_LOCKED": "1"})\n'),
    # V-24: the floor of Orodruin's update.
    ("M5454", "a release older than the highest pushed is sent to Orodruin without the way back asked (SEC-C)",
     PIM, "    if why and not rollback:\n        raise Unverified(", "    if False:\n        raise Unverified("),
    ("M5455", "the floor of this workstation never raised after a push: an Orodruin rebuilt takes any release (SEC-C)",
     MAKE, '\t   python3 scripts/published_image.py raise-floor annatar --ref "$$ref" --commit "$$commit" \\\n',
     "\t   true \\\n"),
    ("M5456", "without REF, the highest local tag taken without its image verified (SEC-C)", PIM,
     "            digest = resolve(image, commit)\n            verify(image, digest, commit, cosign, runner=runner)\n"
     "        except Unverified as e:\n",
     "            digest = resolve(image, commit)\n        except Unverified as e:\n"),
    ("M5457", "the push reads the image in service only: an Orodruin rebuilt forgets the floor (SEC-C)", PIM,
     "service_mark(marker, revision, runner) + memory_mark(), a.rollback, runner)",
     "service_mark(marker, revision, runner), a.rollback, runner)"),
    ("M5458", "the push reads this workstation's memory only: the image in service never marks the floor (SEC-C)",
     PIM, "service_mark(marker, revision, runner) + memory_mark(), a.rollback, runner)",
     "memory_mark(), a.rollback, runner)"),
    ("M5459", "a way back lowers the floor of this workstation (SEC-C)", PIM,
     '    if floor and semver(floor["tag"]) >= semver(tag):\n        return floor\n', ""),
    ("M5460", "a mark whose commit this checkout does not know taken for « not older » (SEC-C)", PIM,
     "            if known.returncode != 0:\n                raise Unverified(f\"l'ordre de",
     "            if False:\n                raise Unverified(f\"l'ordre de"),
    # V-26: Imladris's host key required.
    # Re-anchored (CDI2, #922): HOST_SSH_OPTS is printed by infra/glorfindel-host/ssh_opts.sh now.
    ("M5461", "ssh toward Imladris falls back to accept-new without HOST_SSH_FINGERPRINT (SEC-C)",
     "infra/glorfindel-host/ssh_opts.sh",
     "    printf '%s\\n' \"-o StrictHostKeyChecking=yes -o UserKnownHostsFile=$known -o HostKeyAlgorithms=ssh-ed25519 "
     "${key:+-i $key -o IdentitiesOnly=yes}\"\n",
     "    [ -n \"${HOST_SSH_FINGERPRINT:-}\" ] || { printf '%s\\n' \"-o StrictHostKeyChecking=accept-new "
     "${key:+-i $key -o IdentitiesOnly=yes}\"; exit 0; }\n"
     "    printf '%s\\n' \"-o StrictHostKeyChecking=yes -o UserKnownHostsFile=$known -o HostKeyAlgorithms=ssh-ed25519 "
     "${key:+-i $key -o IdentitiesOnly=yes}\"\n"),
    ("M5462", "known_host.sh lets a command toward Imladris go without its fingerprint (SEC-C)", KH,
     'if [ -z "$want" ]; then\n  case "$var" in\n',
     'if [ -z "$want" ]; then\n  [ "$var" = ORO_SSH_FINGERPRINT ] || exit 0\n  case "$var" in\n'),
    ("M5463", "host.env sent to Imladris over an ssh that accepts a new host key (SEC-C)", MAKE,
     "\t scp -q $(HOST_SSH_OPTS) infra/glorfindel-host/host.env",
     "\t scp -q -o StrictHostKeyChecking=accept-new infra/glorfindel-host/host.env"),
]
TESTS = {
    "M5446": _D + "test_origin_is_pointed_at_the_current_name_before_the_fetch_and_said",
    "M5447": _CD + "test_origin_is_pointed_at_the_current_name_before_the_fetch_said_once",
    "M5448": _D + "test_a_deployment_by_hand_without_the_verified_commit_builds_nothing",
    "M5449": _D + "test_a_reference_the_vm_resolves_to_another_commit_is_refused",
    "M5450": _D + "test_make_start_hands_the_vm_the_verified_commit_never_a_name_alone",
    "M5451": _D + "test_make_start_verifies_the_published_image_before_anything_reaches_imladris",
    "M5452": _P + "test_imladris_by_hand_is_proven_on_the_workstation_its_commit_said",
    "M5453": _CD + "test_the_current_name_is_the_agent_s_default_and_reaches_its_switch",
    "M5454": _P + "test_a_release_under_the_floor_is_refused_unless_the_way_back_is_asked " + _P
    + "test_a_push_older_than_the_image_in_service_is_refused_unless_the_way_back_is_asked",
    "M5455": _P + "test_the_floor_is_raised_by_a_push_and_holds_for_an_orodruin_rebuilt",
    "M5456": _P + "test_without_ref_the_release_is_the_highest_whose_published_image_is_verified",
    "M5457": _P + "test_the_floor_is_raised_by_a_push_and_holds_for_an_orodruin_rebuilt",
    "M5458": _P + "test_a_push_older_than_the_image_in_service_is_refused_unless_the_way_back_is_asked",
    "M5459": _P + "test_the_workstation_s_floor_is_raised_never_lowered " + _P
    + "test_a_push_older_than_the_image_in_service_is_refused_unless_the_way_back_is_asked",
    "M5460": _P + "test_a_release_under_the_floor_is_refused_unless_the_way_back_is_asked",
    "M5461": _S + "test_the_ssh_options_toward_imladris_never_accept_a_new_key_fingerprint_or_not",
    "M5462": _S + "test_without_a_fingerprint_nothing_reaches_imladris_never_accept_new",
    "M5463": _S + "test_host_env_reaches_imladris_only_through_the_pinned_key",
}
