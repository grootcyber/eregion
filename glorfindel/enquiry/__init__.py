"""The enquiry of a detection (ENQ2, #1064; `docs/design/enquete-raisonnee.md` §4, §13): what
Glorfindel reads before it decides, out of glorfindel/agent.py.

  catalog.py   the closed catalogue of reads: each one's id, its sentence for the model, its query, the
               parameters the code fills (each with its check), how far back it reads (its `ago()`,
               counted from the read, not from the signal: ENQ5 anchors it there), its declared
               latency, its author, and what it can say under each system; the seven states of a read
  fixed.py     today's enquiry (`investigate`): the reads chosen on the detected row's columns, run
               through the catalogue — the same queries, in the same order, and the same message to
               the model, to the byte
  knowledge.py the base (ENQ3): a sheet per technique, its hypotheses; evolutions.py its store
  loop.py      the loop (ENQ4, #1085): the model picks its reads (`lire(id)`) and concludes, within a
               budget N and a real delay T the code holds — at the harness only
  message.py   what the loop's model sees: its prompt, its one tool, the message of a turn (ENQ4)
  reference.py the memory per object: the last enquiry on the same VM and rule, dated (ENQ4)
  lecteur.py   the loop's reader (ENQ5a, #1162): each read on its window anchored on the signal's hour,
               KQL on the workspace, ARM through the provider's adapter — at the harness and the capture
  predicats.py the predicates the code computes on the rows: T1486-H1 and H2 (ENQ5a)
  interrupteur.py the switch GLORFINDEL_ENQUIRY (ENQ5b, #1284): `fixed`, the default, or `loop`
  production.py the loop in the watch; decision.py `decide` with its enquiry; memoire.py the memory per
               object, written by the watch (ENQ5b) — imported only by the switch, once it says `loop`

In `fixed` (the default) nothing here changes what the model sees: the loop, its message, its reader, its
predicates and the memory per object are read by the harness and by the bridge of production alone,
which only the switch imports, inside its functions (tests/unit/test_enquiry_loop.py). `loop` is switched
on at Imladris after the maintainer's end-to-end run only (`docs/operations.md`).
"""
