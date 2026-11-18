"""SEC-G (#848; audit of 13/11, V-07, V-35, V-38, V-39, V-40, P-06): the release Imladris's CD deploys —
a v<semver> tag a rule reserves, created by the maintainer, at the commit the repository's API names —,
a commit named by its 40 characters, the manual tunnel as the workstation's, one public IPv4 address as
the SSH source, Orodruin's channel journaled, a High or Critical CVE fixed upstream judged. M5761–M5778;
M5779–M5780 (the release gate's job) go with Jonathan's patch of release-gate.yml
(scripts/mutants/SEC-G-workflow.py).
"""
CD = "infra/glorfindel-host/cd/eregion_cd.py"
DEPLOY = "infra/glorfindel-host/deploy.sh"
MAKE = "Makefile"
CIDR = "scripts/operator_cidr.py"
CVES = "scripts/image_cves.py"
ORO = "infra/orodruin/main.tf"
_CD = "tests/unit/test_host_cd.py::"
_D = "tests/unit/test_host_deploy.py::"
_C = "tests/unit/test_host_console.py::"
_O = "tests/unit/test_operator_cidr.py::"
_I = "tests/unit/test_image_cves.py::"

MUTANTS = [
    # V-07: the tag, the author, the rule.
    ("M5761", "the CD takes a release tag without its « v »: « 0.6.2 », which no rule reserves, deployed (SEC-G)",
     CD, 'TAG_RE = r"v(0|[1-9][0-9]*)', 'TAG_RE = r"v?(0|[1-9][0-9]*)'),
    ("M5762", "a release tag not of the form v<semver> goes on to be fetched and judged by the rest (SEC-G)", CD,
     '    if not re.fullmatch(TAG_RE, tag):\n        return (f"son tag, « {shown(tag)} »',
     '    if False:\n        return (f"son tag, « {shown(tag)} »'),
    ("M5763", "the release's author is never read: one the sessions' App created is deployed (SEC-G)", CD,
     '    author = release.get("author")\n    if not isinstance(author, dict):\n',
     '    return ""\n    author = release.get("author")\n    if not isinstance(author, dict):\n'),
    ("M5764", "a person who is not the maintainer passes as the release's author (SEC-G)", CD,
     "    if aid != want or isinstance(aid, bool):\n", "    if aid is None:\n"),
    ("M5765", "a tag no active rule reserves is said again, never refused: the release deployed (SEC-G)", CD,
     '        if rule == "absent":\n            raise Refused(', '        if False:\n            raise Refused('),
    ("M5766", "a tag rule that does not read lets the release deploy (SEC-G)", CD,
     '            raise Quiet(f"{tag} : la règle des tags ne se lit pas, la release attend")\n', ""),
    # V-38: the commit, on the API; never a prefix.
    ("M5767", "the CD trusts the commit Imladris's origin gives the tag: the repository's API never read (SEC-G)",
     CD, "        named = tag_commit(tag)\n", "        named = commit\n"),
    ("M5768", "the way back asked on Imladris skips the tag's and the author's rule (SEC-G)", CD,
     "    why = release_refusal(tag, release)\n", '    why = "" if back_to else release_refusal(tag, release)\n'),
    ("M5769", "deploy.sh takes a commit prefix again: one off every branch deployed (SEC-G)", DEPLOY,
     '  if [[ "$ref" =~ ^[0-9a-f]{40}$ ]] \\\n      && commit=$(git rev-parse -q --verify "$ref^{commit}" 2>/dev/null) '
     '\\\n      && [ "$commit" = "$ref" ]; then\n',
     '  if [[ "$ref" =~ ^[0-9a-f]{7,40}$ ]] \\\n      && commit=$(git rev-parse -q --verify "$ref^{commit}" 2>/dev/null) '
     '\\\n      && [[ "$commit" == "$ref"* ]]; then\n'),
    ("M5770", "make imladris-start lets a commit prefix through to cosign and to Imladris (SEC-G)", MAKE,
     "*) [ $${#EREGION_DEPLOY_REF} -eq 40 ] ||", "*) true ||"),
    # V-35: the manual tunnel.
    ("M5771", "the manual tunnel to the console reads ~/.ssh/config: a LocalForward or a GatewayPorts slipped in (SEC-G)",
     MAKE, "\t@ssh -F none $(HOST_SSH_OPTS) -o GlobalKnownHostsFile=/dev/null",
     "\t@ssh $(HOST_SSH_OPTS) -o GlobalKnownHostsFile=/dev/null"),
    ("M5772", "the manual tunnel to the console listens without its address: GatewayPorts publishes 7007 (SEC-G)",
     MAKE, "-o ExitOnForwardFailure=yes -N -L 127.0.0.1:7007:127.0.0.1:7007 $(HOST_USER)@$(HOST_IP)\n",
     "-o ExitOnForwardFailure=yes -N -L 7007:127.0.0.1:7007 $(HOST_USER)@$(HOST_IP)\n"),
    # V-40: the operator's address.
    ("M5773", "OPERATOR_CIDR may be a range: 0.0.0.0/1 opens SSH to half the internet (SEC-G)", CIDR,
     '    if not slash or prefix != "32":\n', "    if not slash:\n"),
    ("M5774", "OPERATOR_CIDR may be a private, shared or reserved address (SEC-G)", CIDR,
     "    for net in RESERVED:\n", "    for net in ():\n"),
    ("M5775", "the third-party service's answer is suffixed /32 and handed to Terraform unchecked (SEC-G)", CIDR,
     '        return check_address(text) + "/32"\n', '        return text + "/32"\n'),
    # V-39: the channel's journal.
    ("M5776", "the channel's reads are no longer journaled: a stolen identity reads the windows without a trace "
     "(SEC-G)", ORO, '  enabled_log {\n    category = "StorageRead"\n  }\n', ""),
    # P-06: the judgement the release gate runs.
    ("M5777", "the CVE gate lets a High vulnerability fixed upstream through: only Critical refuses (SEC-G)", CVES,
     'REFUSED_SEVERITIES = frozenset({"High", "Critical"})', 'REFUSED_SEVERITIES = frozenset({"Critical"})'),
    ("M5778", "a report that saw no distribution passes the CVE gate: the system's packages never read (SEC-G)",
     CVES, "    if not name:\n        raise Unreadable(", "    if False:\n        raise Unreadable("),
]
TESTS = {
    "M5761": _CD + "test_a_release_whose_tag_is_not_v_semver_is_refused_before_anything_is_fetched " + _CD
    + "test_the_only_tag_deployed_is_v_semver",
    "M5762": _CD + "test_a_release_whose_tag_is_not_v_semver_is_refused_before_anything_is_fetched",
    "M5763": _CD + "test_a_release_the_maintainer_did_not_create_is_refused " + _CD
    + "test_a_way_back_follows_the_same_rule_its_release_by_the_app_refused",
    "M5764": _CD + "test_a_release_the_maintainer_did_not_create_is_refused " + _CD
    + "test_the_author_is_read_by_id_never_by_login",
    "M5765": _CD + "test_a_missing_tag_rule_refuses_the_release_said_with_the_mention_once " + _CD
    + "test_check_refuses_a_missing_tag_rule",
    "M5766": _CD + "test_a_tag_rule_that_cannot_be_read_holds_the_release_said_once_then_deploys",
    "M5767": _CD + "test_a_tag_whose_commit_the_api_names_otherwise_is_refused " + _CD
    + "test_a_tag_the_api_does_not_name_is_refused",
    "M5768": _CD + "test_a_way_back_follows_the_same_rule_its_release_by_the_app_refused",
    "M5769": _D + "test_a_commit_prefix_is_refused_even_of_a_commit_off_every_branch",
    "M5770": _D + "test_make_start_refuses_a_commit_prefix_before_anything",
    "M5771": _C + "test_the_tunnel_by_hand_reads_no_ssh_config_binds_the_loopback_and_pins_the_key",
    "M5772": _C + "test_the_tunnel_by_hand_reads_no_ssh_config_binds_the_loopback_and_pins_the_key " + _C
    + "test_host_tunnel_shows_the_console_url_under_either_name",
    "M5773": _O + "test_a_range_an_ipv6_a_private_or_reserved_address_is_refused " + _O
    + "test_a_wide_or_private_operator_cidr_stops_every_terraform_target",
    "M5774": _O + "test_a_range_an_ipv6_a_private_or_reserved_address_is_refused",
    "M5775": _O + "test_a_service_answer_that_is_not_one_public_address_is_refused_never_suffixed " + _O
    + "test_without_operator_cidr_the_service_answers_checked",
    "M5776": "tests/unit/test_orodruin.py::"
    "test_every_read_write_and_delete_of_the_channel_is_journaled_to_the_bench_workspace",
    "M5777": _I + "test_a_high_or_critical_cve_fixed_upstream_in_a_system_package_refuses",
    "M5778": _I + "test_a_report_that_proves_nothing_never_passes",
}
