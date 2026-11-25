"""OOR1 (#1202): what is out of reach, finished — the limits the relecture of GRP1 left. Each mutant takes a
piece back: a held card judged by its own id again, « pending approval » on a tile out of reach (M7717), its
Cmd window giving a command that acts (M7718), the tile not handed to an NSG tile's cards (M7719), the bar
« subscription unknown » said before /api/config answered (M7720), a failed read of /api/config never said
(M7721), a VM's readiness of another subscription a 500 again (M7722), the refusal's text — both
subscriptions whole — in the answer (M7723); the review of OOR1: the refusal not answered 409 (M7724), an error's
body of /api/config read as the config (M7725). M7717–M7725, measured by tests/unit/test_console_oor.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GF_JS = "eregion_console/static/glorfindel.js"
API = "eregion_console/api.py"
REACH = "eregion_console/reach.py"

_T = "tests/unit/test_console_oor.py::"

MUTANTS = [
    ("M7717", "a held card judged by its own id again: « pending approval » on a tile out of reach (OOR1)", GF_JS,
     "  if (oor) return 'out of reach: detect only';",
     "  if (_isOor({ resource_id: e.resource_id })) return 'out of reach: detect only';"),
    ("M7718", "the Cmd window of a card out of reach gives a command that acts (OOR1)", GF_JS,
     "  const cmd = oor ? _oorCommand(esc) : cliCommand(esc);", "  const cmd = cliCommand(esc);"),
    ("M7719", "an NSG tile's cards not handed their tile: judged as in reach (OOR1)", GF_JS,
     "${_groupEscs(myEscs).map(g => _renderEscGroup(g, resource)).join('')}</div>` : '';",
     "${_groupEscs(myEscs).map(g => _renderEscGroup(g)).join('')}</div>` : '';"),
    ("M7720", "the bar « subscription unknown » said before /api/config answered: it flashes at each load (OOR1)", GF_JS,
     "  const unknown = (_cfgData ? _watchSub() : !_cfgFailed) ? '' :", "  const unknown = _watchSub() ? '' :"),
    ("M7721", "a failed read of /api/config never said: the bar silent on an unknown subscription (OOR1)", GF_JS,
     "  } catch (e) { _cfgFailed = true; renderInfra(); }", "  } catch (e) {}"),
    ("M7722", "a VM's readiness of another subscription a 500 again (OOR1)", API,
     "    from eregion_console.reach import assess   # OOR1", "    from glorfindel.readiness import assess   # OOR1"),
    ("M7723", "the refusal's text, both subscriptions whole, in the console's answer (OOR1)", REACH,
     "    except WrongSubscriptionError:\n        raise OutOfReach(OUT_OF_REACH) from None",
     "    except WrongSubscriptionError as exc:\n        raise OutOfReach(f\"{OUT_OF_REACH}: {exc}\") from None"),
    ("M7724", "a VM of another subscription not answered 409: a 500 again (OOR1, its review)", API,
     "@app.exception_handler(AmbiguousVM)\n@app.exception_handler(OutOfReach)\n", "@app.exception_handler(AmbiguousVM)\n"),
    ("M7725", "an error's body of /api/config read as the config (OOR1, its review)", GF_JS,
     "    if (!r.ok) throw new Error(String(r.status));   // an error's body is never the config\n", ""),
]

TESTS = {
    "M7717": f"{_T}test_a_held_card_is_judged_by_the_tile_it_is_shown_on",
    "M7718": f"{_T}test_the_page_passes_the_tile_to_the_card_and_its_cmd",
    "M7719": f"{_T}test_the_page_passes_the_tile_to_the_card_and_its_cmd",
    "M7720": f"{_T}test_the_unknown_bar_waits_for_the_first_answer_of_config",
    "M7721": f"{_T}test_the_page_passes_the_tile_to_the_card_and_its_cmd",
    "M7722": f"{_T}test_readiness_and_activation_of_another_subscription_refused_409_never_a_500",
    "M7723": f"{_T}test_readiness_and_activation_of_another_subscription_refused_409_never_a_500",
    "M7724": f"{_T}test_readiness_and_activation_of_another_subscription_refused_409_never_a_500",
    "M7725": f"{_T}test_the_page_passes_the_tile_to_the_card_and_its_cmd",
}
