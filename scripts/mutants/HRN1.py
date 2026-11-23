"""HRN1 (#1065): the harness measures the latency, the tokens and the cost of each call to the model
(scripts/harness_meter.py, scripts/llm_smoke.py). M7100–M7102: a cost LiteLLM cannot compute made 0;
the draws' latency forgotten; the measure written into the attestation's verified block.
Measured by tests/unit/test_harness_meter.py."""
METER = "scripts/harness_meter.py"
SMOKE = "scripts/llm_smoke.py"
_T = "tests/unit/test_harness_meter.py"

MUTANTS = [
    ("M7100", "a cost LiteLLM cannot compute made 0: a run of an unpriced model looks free (HRN1)", METER,
     "    except Exception:\n        return None\n",
     "    except Exception:\n        return 0.0\n"),
    ("M7101", "the draws' latency forgotten: only the first call of a decision in the latency per call (HRN1)",
     METER,
     '    lat = [c["latency_s"] for c in ok]\n',
     '    lat = [c["latency_s"] for c in ok if c["role"] != DRAW]\n'),
    ("M7102", "the measure written into the attestation's verified block: a measured run changes the signed "
     "file (HRN1)", SMOKE,
     '                        "slots": r["slots"], "overconfident_errors": r["overconf"],\n',
     '                        "slots": r["slots"], "overconfident_errors": r["overconf"],\n'
     '                        "measure": r.get("measure"),\n'),
]
TESTS = {
    "M7100": f"{_T}::test_a_cost_litellm_cannot_compute_is_unknown_never_zero",
    "M7101": f"{_T}::test_the_draws_are_measured_with_their_decision "
             f"{_T}::test_the_json_and_the_leaderboard_carry_the_measure",
    "M7102": f"{_T}::test_the_attestation_is_the_same_to_the_byte_with_or_without_the_measure",
}
