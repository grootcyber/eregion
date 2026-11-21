"""G1f (Partie de #76): vm-cpu-pressure's effect reads the CPU as the Linux agent names it in Perf,
measured on gondolin on 21/11 after DCR1 — Processor / % Processor Time, the instance « total ».
M6952–M6953, measured by tests/unit/test_gothmog_noise.py and tests/unit/test_gothmog_readiness.py."""
CPU = "gothmog/experiments/vm-cpu-pressure.yaml"
_N = "tests/unit/test_gothmog_noise.py::test_the_cpu_effect_reads_what_arrives_under_linux"
_R = ("tests/unit/test_gothmog_readiness.py::"
      "test_the_cpu_load_is_read_under_its_linux_instance_and_the_preflight_lets_it_run")

MUTANTS = [
    ("M6952", "the CPU's aggregate read under its Windows instance « _Total »: under Linux nothing "
     "arrives there, the preflight refuses and the noise is never seen (G1f)", CPU,
     "        | where InstanceName == 'total'\n",
     "        | where InstanceName == '_Total'\n"),
    ("M6953", "the CPU read under the Windows object « Processor Information »: never collected "
     "under Linux (G1f)", CPU,
     "        | where ObjectName == 'Processor' and CounterName == '% Processor Time'\n",
     "        | where ObjectName == 'Processor Information' and CounterName == '% Processor Time'\n"),
]

TESTS = {
    "M6952": f"{_N} {_R}",
    "M6953": _N,
}
