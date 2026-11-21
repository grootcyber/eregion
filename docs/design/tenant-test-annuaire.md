# Le tenant de test dédié pour les techniques d'annuaire (#857)

_Conception — 2026-11-16 — statut : **conception, à relire avant tout code** (#857, jalon 0.6.1). Suite de RID2 (#844, la carte d'identité d'annuaire jouable, fusionnée le 15/11) et de `docs/design/stratus-cible.md` (R2b, le plan de contrôle). Débloque la preuve de détection de #844._

## La décision (Jonathan / Red Driver, 16/11)

**Les techniques d'annuaire de Stratus tournent dans un tenant workforce supplémentaire, permanent et dédié**, où rien de réel ne vit. Pas un jetable : il n'existe pas de « tenant éphémère par API », un tenant workforce supplémentaire est réservé aux clients payants (Jonathan l'est), créé sous le rôle **Tenant Creator**, et sa **suppression est bridée** (abonnements et licences à retirer d'abord) ; le bac à sable M365 Dev est gated (Visual Studio / partenaire) et expire à 90 jours — écarté.

**Pourquoi un tenant à part.** Une technique d'annuaire livrée par RID2 (créer une application + son principal de service, lui assigner un rôle d'annuaire, lui ajouter un secret) a besoin, au `warmup`, d'**écritures Graph privilégiées**. Le contrat d'Orodruin refuse à raison tout rôle Graph d'**écriture** sur l'identité d'Orodruin (§ 1). Un tel droit est **à l'échelle du tenant** : l'accorder sur l'annuaire réel mettrait tout l'annuaire dans le rayon de souffle. Un tenant dédié borne ce rayon à un annuaire **jetable, sans valeur** : une écriture d'annuaire y est sans conséquence sur le tenant réel.

**Ce que le tenant dédié règle, et ce qu'il ne règle pas.** Il règle le rayon de souffle d'une écriture d'annuaire. Il ne règle **pas**, à lui seul, trois choses, qui font le cœur de cette conception : (a) l'identité qui écrit doit être **native au tenant dédié** (une identité managée ne porte pas de rôle d'annuaire dans un autre tenant — § 2) ; (b) **Orodruin ne doit jamais pouvoir écrire l'annuaire réel** — son contrat reste inchangé, read-only côté tenant réel, et un contrôle refuse de viser le tenant réel (§ 4) ; (c) la **détection** (C2, la preuve de #844) exige de router les AuditLogs du tenant dédié vers une watch, ce qui est le point le plus lourd (§ 5).

---

## 1. Le bloquant, précisément

- `eregion_core/orodruin.py:121` : `GRAPH_READ_ONLY = {"Application.Read.All", "RoleManagement.Read.Directory"}`. `assess_graph` (l. 462-485) refuse tout rôle d'application hors de cette liste (`graph_unlisted_right`) et tout rôle d'annuaire (`wids` hors `APP_DEFAULT_WIDS` → `graph_directory_role`). Résultat : **Orodruin passif → l'injecteur refuse avant tout appel au cloud**.
- L'injecteur tourne **sous l'identité managée d'Orodruin** (`annatar/executors/stratus_host.py`, `DefaultAzureCredential`). Accorder `RoleManagement.ReadWrite.Directory` (ou une écriture d'applications) à cette identité **ne débloque pas** : ça bascule Orodruin en passif. Le poser « ≥ 24 h avant » (cache du jeton de la MI) n'y change rien.
- `--without-glorfindel` ne contourne que la watch (V1), pas le contrat.

La technique d'annuaire n'est donc **pas jouable** sous l'identité d'Orodruin. Il faut une autre identité, dans un autre tenant.

---

## 2. L'identité qui écrit l'annuaire — native au tenant dédié

Une **identité managée vit dans un seul tenant** (celui d'Orodruin) ; elle ne peut pas être un principal de première classe tenant un rôle d'annuaire dans un **autre** tenant. L'identité qui écrit l'annuaire du tenant dédié est donc une **application enregistrée DANS le tenant dédié**, avec ses rôles Graph d'écriture **scopés à l'annuaire de ce tenant seul** (p. ex. `Application.ReadWrite.OwnedBy` et `RoleManagement.ReadWrite.Directory` — le minimum exact est à mesurer, § À mesurer).

C'est une **troisième identité**, à ne confondre ni avec :

- l'**identité managée d'Orodruin** (tenant réel, GRAPH_READ_ONLY — le contrat), ni avec
- l'**identité Stratus du plan de contrôle** (R2b, `stratus-cible.md` § 1) : celle-ci vit dans le tenant d'Orodruin et porte un rôle **ARM** fermé sur l'abonnement de test dédié. R2b est l'**abonnement** ; #857 est le **tenant** — deux périmètres distincts.

---

## 3. Comment Stratus s'authentifie au tenant dédié (cross-tenant)

- Le binaire Stratus (Go) lit `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` (ou un certificat). Pour une technique `entra-id.*`, ces variables visent **le tenant dédié et son application native**, jamais l'identité managée d'Orodruin ni le tenant réel.
- Le **credential** de l'application native (un **certificat** de préférence, à **expiration courte**, en rotation) est délivré au sous-processus par le processus d'Orodruin **hors du bac à sable** (le sens voulu, comme R2b § 1). Jamais dans le dépôt.
- **Le tenant vient SEULEMENT de la config** — `EREGION_STRATUS_DIR_TENANT` (nom à figer) — jamais du tenant réel. Un contrôle **refuse s'il vaut `EREGION_TENANT_ID`** (le tenant du banc / réel), miroir du contrôle d'abonnement de R2b. Sans ce refus, une ligne de config ramènerait une écriture d'annuaire sur le tenant réel.
- **Pourquoi c'est borné même avec une écriture Graph** : un credential d'une application du **tenant B** ne peut pas émettre de jeton pour le Graph du **tenant A**. L'écriture ne peut atteindre que l'annuaire du tenant dédié. Le bornage ne repose pas sur la confiance au LLM ni sur une garde de surface : il est **structurel** (frontière de tenant).

---

## 4. Le contrat d'Orodruin reste read-only côté tenant réel

**Inchangé.** L'identité managée d'Orodruin garde `GRAPH_READ_ONLY` sur le tenant réel (`EREGION_TENANT_ID`), `assess_graph` inchangé, `orodruin-check` s'arme read-only là comme avant (IDI1). #857 **ne touche pas** `GRAPH_READ_ONLY` ni `assess_graph`.

Ce que #857 ajoute à la garde d'un **run d'annuaire** (une garde distincte de celle de R2b) :

- **`EREGION_STRATUS_DIR_TENANT` renseigné et ≠ `EREGION_TENANT_ID`**, sinon passif : jamais d'écriture d'annuaire sur le tenant réel.
- La technique d'annuaire utilise **l'application native du tenant dédié**, jamais l'identité managée d'Orodruin — vérifiable : le tenant / client id du credential passé au sous-processus diffère de ceux de la MI.
- **Prouver que l'application native ne tient que les rôles attendus — quelle voie ?** Deux options :
  - **(a) bornage structurel (reco).** Le tenant dédié **est** le confinement ; « l'application y tient des écritures Graph » est acceptable parce que le rayon de souffle est un annuaire jetable. Orodruin **ne reçoit aucun credential dans le tenant dédié** — lui en donner un serait un **pont** de plus entre les tenants. La garde se limite au refus de non-égalité (ci-dessus) et au contrat read-only inchangé côté réel.
  - (b) lecture cross-tenant : Orodruin lirait les rôles de l'application native via un second credential read-only dans le tenant dédié. **Écartée** : un pont de plus, pour prouver une borne déjà structurelle.
- Reco : **(a)**. Le contrat prouve, côté réel, que la MI n'a aucune écriture (inchangé) ; côté dédié, la borne est le tenant lui-même + le refus de non-égalité.

---

## 5. La détection (C2, #844) — router les AuditLogs du tenant dédié vers une watch

C'est la **preuve de #844** : le `warmup`/`detonate` (créer l'app + le SP, assigner le rôle, ajouter le secret) doit **apparaître dans les AuditLogs d'Entra** et être **détecté** par la règle d'annuaire de RID2. Point dur :

- **Un paramètre de diagnostic Entra ID ne route les AuditLogs que vers un Log Analytics workspace d'une souscription associée au MÊME tenant.** Le workspace du banc vit dans le tenant réel → **inutilisable** pour les logs du tenant dédié.
- Donc le tenant dédié a besoin de **sa propre souscription + son propre workspace** pour capter les AuditLogs, **et la watch doit lire CE workspace** — une **lecture cross-tenant**.

Conséquences, à cadrer :

- **Provisionnement** : une souscription liée au tenant dédié (payant — Jonathan est prêt), vide hormis le workspace ; un **paramètre de diagnostic Entra** (catégories `AuditLogs`, et `SignInLogs` si une règle les lit) → ce workspace.
- **La watch lit un workspace d'un autre tenant.** ⚠️ **le point le plus lourd.** Trois voies, et une **recommandation** :
  - **(reco) Azure Lighthouse** — une délégation de gestion déléguée (*delegated resource management*) qui donne à l'identité de la watch, **dans le tenant d'Orodruin**, le rôle **Log Analytics Reader** scopé au **seul workspace** du tenant dédié. La watch interroge alors ce workspace depuis son propre tenant (expression `workspace()`), **sans identité invitée ni secret** dans le tenant dédié — Lighthouse est une délégation, pas un principal de l'annuaire, donc il ne viole pas « aucun pont » (§ 7). C'est la voie que Microsoft indique pour lire, cross-tenant, des journaux d'Entra routés en Log Analytics, et elle lève le piège « une identité qui interroge un workspace doit vivre dans son tenant » (vrai **sauf** délégation). Lighthouse est gratuit ; l'ingestion du workspace reste facturée à l'abonnement qui le porte (celui du tenant dédié).
  - une **application multi-tenant** consentie en lecture dans le tenant dédié : porte un **secret/credential** (surface de plus), et un consentement administrateur dans le tenant dédié — moins propre que la délégation.
  - un **principal invité** (B2B) de la watch dans le tenant dédié : **écartée** — c'est exactement le pont inter-tenants que § 7 interdit.
  - **À mesurer au banc** (pas au design) : la **portée exacte** de la délégation Lighthouse (un seul workspace, Log Analytics Reader et rien d'autre), la **latence des AuditLogs** (quelques minutes à ~15–20 min d'après la doc), et que la watch ne tient, dans le tenant dédié, **que** cette lecture.
- **AL1 décide sans modèle** sur des données contrôlées par qui agit dans le tenant dédié — à garder ainsi. La règle qui tire : la règle d'annuaire de RID2 (ajout d'application / de principal de service / d'un membre à un rôle, lue dans AuditLogs).

Tant que §5 n'est pas tranché et mesuré, **#844 reste en détection non mesurée** : la technique est jouable (le run réussit), mais la preuve de détection attend ce pont de lecture.

---

## 6. Les identités de test à semer

Un annuaire vide ne donne pas de contexte réaliste ni des AuditLogs lisibles. Semer le minimum :

- quelques **utilisateurs de test synthétiques** (noms génériques, jamais de vrais — repo public, règle des identifiants) ;
- éventuellement un **groupe** et les **rôles** que la technique touche (`Directory Readers` existe par défaut) ;
- de quoi rendre le `warmup`/`detonate` lisibles dans AuditLogs.

Aucune **invitation B2B / invité** vers le tenant réel (§ 7).

---

## 7. L'isolement entre les deux tenants (aucun pont)

Invariants à tenir :

- **aucun utilisateur invité / B2B / synchronisation cross-tenant** entre le tenant dédié et le réel ;
- **aucune fédération** (workload identity) d'une application du tenant réel vers le dédié ni l'inverse, hors ce que #857 déclare ;
- la **souscription du tenant dédié** n'héberge aucune ressource réelle : elle ne sert qu'au workspace des AuditLogs (elle n'est **pas** l'abonnement de test de R2b, qui vit dans le tenant d'Orodruin — ne pas confondre) ;
- le **credential** de l'application native est à **expiration courte**, en rotation, jamais dans le dépôt.

Le refus de non-égalité (tenant dédié ≠ réel, § 4) est la première ligne ; le bornage structurel (un tenant jetable) est le fond.

---

## 8. Les gestes de Jonathan — `[J]`, en Terraform où c'est possible

Tous **manuels** (une session n'applique jamais, ne lance jamais une technique, ne fait jamais `az login`) ; plan montré avant tout `apply` ; valeurs réelles en variables, jamais dans le dépôt.

1. **`[J]` G-T1** — créer le **tenant workforce dédié** (Tenant Creator). Relever son tenant id (`EREGION_STRATUS_DIR_TENANT`, hors dépôt).
2. **`[J]` G-T2** — une **souscription** liée au tenant dédié (payant), vide hormis le workspace des AuditLogs.
3. **`[J]` G-T3** — l'**application native** + son **credential** (certificat court) + les **rôles Graph d'écriture scopés au tenant dédié**, avec le **consentement administrateur** dans le tenant dédié. Relever appid / oid. Le rôle minimal est mesuré (§ À mesurer).
4. **`[J]` G-T4** — le **paramètre de diagnostic Entra** (AuditLogs → workspace du tenant dédié), en Terraform via un alias `azuread`/`azurerm` sur le tenant dédié.
5. **`[J]` G-T5** — la **délégation Azure Lighthouse** (reco, § 5) : Log Analytics Reader à l'identité de la watch, scopé au **seul** workspace du tenant dédié, pour qu'elle le lise depuis le tenant d'Orodruin — sans identité invitée ni secret.
6. **`[J]` G-T6** — **semer** les identités de test (§ 6).

Ces gestes iront dans `docs/operations.md` au moment du code (avec la date), pas dans cette conception.

---

## Ce que #857 ne fait pas

- **Le run réel au banc** et la mesure de détection : au banc (#844), de la main de Jonathan.
- Les **autres techniques d'annuaire** que celle de RID2 : elles reviendront, une par une.
- **Toucher le contrat d'Orodruin côté tenant réel** : inchangé (`GRAPH_READ_ONLY`, `assess_graph`).
- **Toucher R2b** (plan de contrôle, abonnement dans le tenant d'Orodruin) : distinct.
- **Donner à Orodruin un credential dans le tenant dédié** : ce serait un pont (§ 4b, écartée).

## À mesurer avant le code

- Qu'un credential de l'application native du tenant dédié **ne peut pas** émettre de jeton Graph pour le tenant réel (le bornage structurel — témoin de l'invariant).
- Les **variables Graph** que lit Stratus (`AZURE_TENANT_ID`/`CLIENT_ID`/`CLIENT_SECRET`) pour viser le tenant dédié, et l'**échec attendu** si on vise le tenant réel.
- Les **rôles Graph minimaux** pour le `warmup` de la technique (`Application.ReadWrite.OwnedBy` suffit-il, ou `.All` ? `RoleManagement.ReadWrite.Directory` nécessaire pour assigner le rôle d'annuaire ?).
- Que les **AuditLogs** du tenant dédié arrivent dans son workspace, et leur **latence**.
- **La délégation Azure Lighthouse** par laquelle la watch (Imladris, anciennement H0) lit le workspace du tenant dédié (§ 5, reco) : sa **portée exacte** (un seul workspace, Log Analytics Reader et rien d'autre) et la **latence** des AuditLogs jusqu'à la watch — le point le plus lourd.
- La **procédure de suppression** du tenant (bridée : abonnements / licences à retirer d'abord), pour ne pas rester coincé.

## Les mutants (au code, plus tard) : M5670–M5699

Figés quand le code viendra : le contrôle **tenant dédié ≠ réel** (refus si égal, si vide) ; le **refus d'une écriture d'annuaire visant le tenant réel** ; la garde qui **exige** `EREGION_STRATUS_DIR_TENANT` ; le credential passé au sous-processus **≠** l'identité managée d'Orodruin ; le contrat read-only inchangé **toujours prouvé** côté réel.

---

## Décisions tranchées par Jonathan (21/11)

1. **§ 4 — bornage : structurel (a).** Orodruin **ne lit rien** dans le tenant dédié : le lanceur ne traverse pas les tenants, rien à lire côté tenant réel. (La lecture cross-tenant (b) est écartée.)
2. **§ 5 — voie de lecture cross-tenant de la watch : Azure Lighthouse.** Délégation Log Analytics Reader sur le **seul workspace** du tenant dédié, **sans identité invitée ni secret**, donc sans pont d'annuaire. La portée exacte et la latence **restent à mesurer au banc**.
3. **Ordre : les deux d'un bloc.** Le tenant + l'identité (jouer la technique, run réussi) **et** la détection (§ 5) sont livrés ensemble, une seule bascule — pas en incrémental.

La création du tenant (payant, sous Tenant Creator) et le run au banc restent de la main de Jonathan, plus tard.
