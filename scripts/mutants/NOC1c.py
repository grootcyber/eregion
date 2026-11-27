"""NOC1c (#1276): the night runs on the subscription, never on an API key (scripts/night/eregion-night.service,
UnsetEnvironment; docs/sessions.md, « La nuit »). Jonathan's decision of 27/11. M8207 takes the line out: a
key the user's systemd manager passes on reaches the pass, which is billed on it. M8208 lets the key itself
through again (ANTHROPIC_API_KEY out of the list), the others kept. Then, at the coordinator's word, in
scripts/night/install.sh: M8209 lets a claude inside an editor's extension through (check_claude_path never
refuses), M8210 a settings file that sets a key (check_settings_keys never refuses), M8211 writes the PATH
with its duplicates (dedupe_path keeps every directory). Measured by tests/unit/test_night_unit.py.
"""
UNIT = "scripts/night/eregion-night.service"
INSTALL = "scripts/night/install.sh"
_T = "tests/unit/test_night_unit.py"
_UNSET = ("UnsetEnvironment=ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_PROFILE ANTHROPIC_FEDERATION_RULE_ID "
          "ANTHROPIC_ORGANIZATION_ID CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX CLAUDE_CODE_USE_FOUNDRY "
          "CLAUDE_CODE_USE_MANTLE CLAUDE_CODE_USE_ANTHROPIC_AWS CLAUDE_CODE_USE_ANTHROPIC_GOOGLE_CLOUD "
          "ANTHROPIC_BASE_URL\n")

MUTANTS = [
    ("M8207", "the unit unsets no key source: an API key the user's systemd manager passes on bills the night "
              "(NOC1c)", UNIT,
     _UNSET,
     ""),
    ("M8208", "ANTHROPIC_API_KEY let through again, the other sources unset: in -p the key passes before the "
              "subscription (NOC1c)", UNIT,
     _UNSET,
     _UNSET.replace("ANTHROPIC_API_KEY ", "")),
    ("M8209", "a claude inside an editor's extension let through: the timer loses it at the extension's next "
              "update (NOC1c)", INSTALL,
     '        refuse "claude is ${p}, inside an editor\'s extension:',
     '        true "claude is ${p}, inside an editor\'s extension:'),
    ("M8210", "a settings file that sets a key or an apiKeyHelper let through: the night billed on that key "
              "(NOC1c)", INSTALL,
     '    [ -z "${names}" ] || refuse "${f} sets ${names% }:',
     '    [ -z "${names}" ] || true "${f} sets ${names% }:'),
    ("M8211", "the unit's PATH written with its duplicates: ~/.local/bin twice when claude lives there (NOC1c)",
     INSTALL,
     '      *":${d}:"*) ;;\n',
     '      *":${d}:"*) out="${out:+${out}:}${d}" ;;\n'),
]

TESTS = {mid: _T for mid in [f"M{n}" for n in range(8207, 8212)]}
