"""The enquiry of a detection (ENQ2, #1064; `docs/design/enquete-raisonnee.md` §4, §13): what
Glorfindel reads before it decides, out of glorfindel/agent.py.

  catalog.py   the closed catalogue of reads: each one's id, its sentence for the model, its query, the
               parameters the code fills, its window anchored on the signal's hour, its declared
               latency, its author, and what it can say under each system; the seven states of a read
  fixed.py     today's enquiry (`investigate`): the reads chosen on the detected row's columns, run
               through the catalogue — the same queries, in the same order, and the same message to
               the model, to the byte

Nothing here changes what the model sees: the loop where the model picks its reads (`lire(id)`, ENQ4)
and the states said to it (ENQ5) come later, each with its own proof.
"""
