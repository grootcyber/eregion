@CLAUDE.md

# Session Glorfindel — Agent défensif

Tu es spécialisé sur l'agent défensif. Lis ce fichier en début de session.

**Docs de ton périmètre** (`CLAUDE.md` n'en garde que l'essentiel) : [`docs/glorfindel.md`](docs/glorfindel.md) (watch, graphe, gardes de `decide`, autonomie, vérification, escalades, alertes), [`docs/azure.md`](docs/azure.md) (ce que les actions font sur Azure), [`docs/fichiers-cles.md`](docs/fichiers-cles.md), [`docs/design/module-isolation-iac.md`](docs/design/module-isolation-iac.md), [`docs/design/preuves.md`](docs/design/preuves.md).

**La réaffirmation a une référence** : la table de [`docs/design/reaffirmation.md`](docs/design/reaffirmation.md), §3 (décision de Jonathan du 21/11, Q1). Un changement de la réaffirmation, de son code (`glorfindel/reassert*.py`, ses lectures dans `glorfindel/providers/`, `glorfindel/orphans.py`) ou de son oracle (`tests/unit/test_invariants.py`, `tests/unit/invariant_hold.py`), **met cette table à jour dans la même PR** : la case qui change, son texte et son `fichier:ligne`. Un écart entre le code et un oracle se tranche d'abord dans la table. `docs/glorfindel.md` n'en garde qu'un résumé ; l'histoire, lot par lot, est dans `docs/historique.md`.

## Périmètre

**Tu travailles sur :**
- `glorfindel/` — tout le code de l'agent défensif
- `tests/unit/` — tests unitaires (ton code, pas Annatar)
- `rules/azure/detection_rules.yaml` — queries KQL
- `glorfindel-config.yaml` — config infra locale

**Tu lis mais ne modifies pas :**
- `eregion_core/signals.py` — le contrat des signaux (D1 : sorti d'Annatar), pour comprendre le format signal entrant
- `annatar/scenarios/azure/` — pour comprendre ce que tu dois détecter

**Tu ne touches pas :**
- `annatar/runner/`, `annatar/scenarios/` (sauf lecture)

## Protocole collab

**En début de session :** lis `collab/inbox_glorfindel.md` — traite les messages en attente avant de commencer.

**Après chaque changement significatif :** mets à jour `collab/glorfindel_status.md` (ce qui a changé, impact éventuel sur Annatar ou les tests).

**Si tu changes une interface partagée** (format signal attendu, schema detection_rules.yaml, API du `watch`) : écris un message dans `collab/inbox_annatar.md` avec le détail du changement.

**En fin de session :** snapshot de l'état dans `collab/glorfindel_status.md`.

## Contexte technique rapide

- LangGraph 10 nœuds : `load_context → poll_detection → confirm_facts → investigate → decide → execute_action → verify_action → store_cycle` (+ `escalate_to_human`, `propose_detection_rule`)
- `investigate` : enrichit le signal avec des requêtes KQL contextuelles avant `decide`
- `decide` : LLM via LiteLLM + few-shot + RAG ChromaDB — pas de routing table TTP→action
- RulePoller : polling continu des règles `detection_rules.yaml`, émet un signal structuré avec `run_id` synthétique (`watch-{rule}-{ts}`)
- Tests : `pytest` — 0 appel Azure, 0 appel LLM, `dry_run=True` partout
