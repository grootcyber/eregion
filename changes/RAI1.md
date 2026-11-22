### Added
- **A reference document on reasoning and the model in Eregion** (RAI1, #1045; `docs/raisonnement.md`).
  One map, each fact cited by its file and line, with Mermaid diagrams: where a model takes part and
  where only code does (detection, correlation, today's enquiry, the control plane and identity
  decisions, actions, verification, guards, routing); for each use of a model (Glorfindel's decision,
  the writing of a rule, Annatar's optional campaign planner, the analysis AI's report and triage) what
  it reads, the tool it must return, what the code checks behind it, and what needs an end-to-end run;
  the memory as an embedding model, not an LLM; the default models, LiteLLM and the providers, the
  forced tool choice and the temperature, the decision noted on the cycle's line; the harness and the
  overconfident errors; what reaches the provider and the threat model; the 0.7 reasoned enquiry in a
  few lines. `docs/architecture.md` gains a diagram of the model's place in the loop, linked to it; the
  public manual gains its brick; `CLAUDE.md` indexes it. No code changes, nothing the model reads.
