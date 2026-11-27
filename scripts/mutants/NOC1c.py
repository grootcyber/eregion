"""NOC1c (#1276): the night runs on the subscription, never on an API key (scripts/night/eregion-night.service,
UnsetEnvironment; docs/sessions.md, « La nuit »). Jonathan's decision of 27/11. M8207 takes the line out: a
key the user's systemd manager passes on reaches the pass, which is billed on it. M8208 lets the key itself
through again (ANTHROPIC_API_KEY out of the list), the others kept. Measured by tests/unit/test_night_unit.py.
"""
UNIT = "scripts/night/eregion-night.service"
_T = "tests/unit/test_night_unit.py"
_UNSET = ("UnsetEnvironment=ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_PROFILE ANTHROPIC_FEDERATION_RULE_ID "
          "ANTHROPIC_ORGANIZATION_ID CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX CLAUDE_CODE_USE_FOUNDRY "
          "CLAUDE_CODE_USE_MANTLE CLAUDE_CODE_USE_ANTHROPIC_AWS CLAUDE_CODE_USE_ANTHROPIC_GOOGLE_CLOUD\n")

MUTANTS = [
    ("M8207", "the unit unsets no key source: an API key the user's systemd manager passes on bills the night "
              "(NOC1c)", UNIT,
     _UNSET,
     ""),
    ("M8208", "ANTHROPIC_API_KEY let through again, the other sources unset: in -p the key passes before the "
              "subscription (NOC1c)", UNIT,
     _UNSET,
     _UNSET.replace("ANTHROPIC_API_KEY ", "")),
]

TESTS = {"M8207": _T, "M8208": _T}
