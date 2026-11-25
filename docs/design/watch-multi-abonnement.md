# Une watch par client : plusieurs abonnements d'un même tenant (MSUB1, #1196) — conception

_Note de conception, sans code, 25/11. Direction de produit de Jonathan, le 25/11, transmise par la session
Console pendant GRP1 : **une watch par client, pas une par abonnement**. Quand un workspace Log Analytics
voit une VM d'un autre abonnement, le mieux est de proposer à l'utilisateur d'ajouter les accès qui vont
bien. Go de Jonathan pour la note, le 25/11 (« Oui, la note maintenant »). Statut : **conception, huit
questions ouvertes** (§8). Rien n'est codé, aucun rôle n'est posé, rien n'est appliqué._

**Lié** : [`configuration-console.md`](configuration-console.md) (CFG1 : la console demande, la watch
écrit ; relâcher se confirme) ; [`file-actions-signee.md`](file-actions-signee.md) (FS1 : seule la watch
écrit) ; [`modele-de-menace.md`](modele-de-menace.md) (§5, les hôtes et l'identité de la réponse) ;
[`identites.md`](identites.md) (IDM1 : qui tient quoi) ; [`module-isolation-iac.md`](module-isolation-iac.md)
(les rôles et l'isolation déclarés en IaC) ; [`tenant-test-annuaire.md`](tenant-test-annuaire.md) (TEN1 :
Azure Lighthouse, le seul texte du dépôt sur un autre tenant) ; [`console.md`](console.md) (GRP1, la carte
groupée par abonnement) ; [`docs/operations.md`](../operations.md) (« Identités Azure », et « Les noms des
abonnements », SUBN1).

**Règle de lecture.** Ce qui est lu dans le dépôt est une affirmation, avec son fichier et sa ligne, au
commit `c7489018` (la base de la branche ; une fusion plus récente de `main` peut décaler les lignes).
GRP1 (#1189) et SUBN1 (#1190) sont en vol : leurs lignes sont lues sur leurs branches,
`lot/grp1-grouper` et `lot/subn1-noms-abonnements`. Ce qui est dit d'Azure vient de la documentation
publique, ou de ce que le code en dit : ce sont des **hypothèses**, numérotées HM1 à HM10 (§9), à mesurer
au banc avant le code qui en dépend. Les noms sont génériques : l'abonnement **A** est celui de la watch,
**B** un autre abonnement du même tenant, `rg-app` et `vm-web-01` des noms d'exemple.

---

## 0. En bref

- **Aujourd'hui, une watch tient un seul abonnement, par construction.** `AZURE_SUBSCRIPTION_ID` est
  obligatoire ; chaque client du SDK est construit pour lui seul ; 15 méthodes du connecteur, et le
  retrait d'une règle orpheline, refusent toute cible d'un autre abonnement (`WrongSubscriptionError`) ;
  27 listages d'Azure ne lisent que A. Mais **la découverte, l'enquête et le journal d'activité voient déjà
  plusieurs abonnements** : un workspace partagé remonte les VM de B. La console les montre « hors de
  portée » (GRP1).
- **Le périmètre** : plusieurs abonnements d'un même tenant Entra ID. Le multi-tenant (Lighthouse) reste
  hors champ ; la note dit ce qui le préparerait (§2.3).
- **L'identité, recommandée : une seule identité pour la watch**, avec, dans chaque abonnement ajouté, les
  rôles qu'elle tient déjà dans A, à la portée des groupes inscrits, déclarés en IaC. Une identité par
  abonnement ne borne rien de plus sur un même hôte : chaque conteneur d'Imladris lit déjà le jeton de
  l'identité de la VM, et lirait de même celui de chaque identité attachée (HM9). Un rôle au groupe
  d'administration est écarté : il élargit en silence à tout abonnement créé dessous.
- **Trois états pour un abonnement**, proposés : **vu** (un workspace en remonte des VM ; détection
  seule, comme aujourd'hui), **lu** (déclaré, la watch y lit avec Reader : réseau du client, topologie,
  préparation ; aucune écriture) et **en portée** (déclaré pour agir, et les droits lus ; la réponse y est
  possible, `human_only` par défaut). Les droits seuls ne mettent jamais un abonnement en portée.
- **Un abonnement ajouté n'hérite d'aucune autonomie** (proposé, Q3) : ses VM partent en `human_only`,
  quoi que disent le défaut global et les motifs. La règle de production ne change pas : la zone reste
  celle de chaque ressource (ses tags et ceux de son groupe) ; tout ce qui n'est pas inscrit est réel.
- **« Ajouter les accès »** : sur une tuile hors de portée, la console dit le rôle qui manque, sa portée,
  la commande `az` et le bloc Terraform à appliquer. **Glorfindel ne s'accorde jamais un droit** : son
  rôle n'en porte aucun (`infra/identities/glorfindel-response.json:5-16`). Le geste reste à l'opérateur
  ou à l'administrateur du client. La déclaration de l'abonnement passe par la file de CFG1 : ajouter
  pour agir relâche, et se confirme.
- **Ce qui ne change pas** : ce que voit le modèle, la règle « jamais de panne ni d'action destructive
  sur une charge réelle », `human_only` par défaut.
- **Huit lots** (§7), MSUB2 à MSUB7 avec VLT1 et MSUB3b, environ 22 jours ; SUBN1 et GRP1, en vol, en
  sont la première marche. **Huit questions** pour Jonathan (§8).

---

## 1. L'état des lieux, lu dans le code

### 1.1 L'abonnement de la watch : `AZURE_SUBSCRIPTION_ID`

- **Le connecteur** lit la variable au premier appel et refuse sans elle :
  `glorfindel/providers/azure/connector.py:134-136` (`RuntimeError("AZURE_SUBSCRIPTION_ID is not set")`).
  Il construit `ComputeManagementClient` et `NetworkManagementClient` pour cet abonnement seul, et le
  garde en `_subscription_id` (`connector.py:141-145`). Une instance, un abonnement : aucun client ne
  change d'abonnement en cours de route.
- **Les constructions** : `AzureConnector(` revient 32 fois hors des tests — 9 dans
  `eregion_console/api.py`, 11 dans `glorfindel/cli.py`, 6 dans `glorfindel/watch/rules.py`, une dans
  `glorfindel/agent.py:3321` (le graphe), `glorfindel/watch/housekeeping.py:41`,
  `glorfindel/watch/startup.py:203` (la file de FS1), `glorfindel/restore_executor.py:530`,
  `glorfindel/restore_plan.py:274` et `scripts/capture_enquete.py`. Chacune lit la même variable.
- **Ailleurs** : `eregion_console/api.py:964` (`/api/config`, l'identifiant masqué que la console compare,
  `_mask`, `api.py:955-957`) ; `api.py:3325` (les VM du banc, lues par `TagEnrollment`) ;
  `glorfindel/providers/azure/quarantine_origin.py:43` ; trois conseils de l'audit, qui écrivent
  `--scope /subscriptions/$AZURE_SUBSCRIPTION_ID/resourceGroups/…` (`glorfindel/audit.py:593`, `:661`,
  `:722`) ; `infra/glorfindel-host/host_env.py:118` (copiée dans le `host.env` d'Imladris) et `:145`
  (la seule variable exigée).
- **Le socle** : `eregion_core/inscription.py:120` et `:507` (le périmètre des injecteurs), `eregion_core/watch_gate.py:91`
  (le battement, §1.7), `eregion_core/drill.py:562`, `eregion_core/scheduled_drill.py:152` et `:231`,
  `eregion_core/orodruin.py:395` et `:619`. Côté injecteurs : `annatar/executors/azure_vm.py:189`,
  `annatar/runner/engine.py:731`, `gothmog/engines/chaos_studio.py:191`. Ceux-là ne changent pas (§4.4).

### 1.2 Le refus : `WrongSubscriptionError`

- **La classe** : `glorfindel/response/policy.py:441`, « The target lives in another subscription than
  the one Glorfindel acts in ».
- **Le décorateur** `_same_subscription` (`connector.py:148-174`) lit l'abonnement dans l'identifiant de
  la cible et le compare à celui des clients (`connector.py:166`), avant de construire quoi que ce soit ;
  différent, il lève (`connector.py:168`). Sa docstring dit pourquoi (troisième revue, T1) : les
  identifiants sont réduits à (groupe, nom), et une VM de B était isolée dans A, sur son homonyme s'il
  existe. Elle dit aussi la suite : « Until clients exist per subscription, the action is refused ».
- **Les méthodes gardées** (`connector.py:222-227`), 15 : `isolate_vm`, `release_isolation`,
  `verify_isolation`, `verify_release`, `block_suspicious_ip`, `unblock_ip`, `verify_block_ip`,
  `snapshot`, `restore_from_backup`, `drain_connections`, `sweep_vm_rules`, `check_permissions`,
  `observed_restore`, `observed_actors`, `observed_rights`. Plus `remove_orphan_rule`, par
  `_orphan_writer` (`connector.py:191-219`, le refus `:207`), et la lecture d'un NSG de quarantaine
  (`glorfindel/providers/azure/sweep.py:257-260`).
- **La préparation** le dit avant : `other_subscription`, `not_ready`, « Une instance de Glorfindel
  configurée pour cet abonnement » (`glorfindel/readiness.py:88-96`). Une VM de B ne passe donc jamais en
  `non_disruptive` effectif : le verrou de préparation (L6) la tient en `human_only`.
- Le refus devient une carte `action_failed` ; la CLI le dit sans les identifiants (MSK2,
  `glorfindel/cli.py:1435`).

### 1.3 Ce qui voit déjà plusieurs abonnements

- **La découverte** lit `Heartbeat` dans chaque workspace déclaré (`glorfindel/discovery.py:170-176`,
  `_discover_from_azure_monitor`, `:225`) : toute VM qui y écrit, de quelque abonnement qu'elle soit, avec
  son `_ResourceId` entier. Le registre la range par cet identifiant, jamais par son nom seul
  (`discovery.py:76-82`).
- **Les règles** du RulePoller lisent le workspace, sans filtre d'abonnement.
- **Le journal d'activité** (`AzureActivity`) n'arrive au workspace que par un paramètre de diagnostic
  posé sur l'abonnement (`glorfindel/providers/azure/activity.py:39-44` ; `infra/terraform/activity_log.tf:1-7`
  pour le banc). Si B envoie le sien au même workspace, les règles du plan de contrôle le lisent. Les
  cibles que Glorfindel a posées se comparent déjà avec leur abonnement (`sub/rg/nsg/rule`,
  `activity.py:133-141`).
- **L'enquête** prend l'abonnement dans l'identifiant de la VM, pas dans la variable : le journal
  d'activité d'une VM (`glorfindel/providers/azure/dossier_reads.py:174`) et l'identifiant de son coffre
  (`dossier_reads.py:127-131`). Seuls les droits de l'identité la bornent.
- **L'état local** est rangé par nom et par condensé de l'identifiant (`<nom>--<hash>.json`,
  `glorfindel/response/state_files.py:92-103`) : deux VM homonymes de A et de B ont deux fichiers.
- **Le tenant** est un : les journaux d'Entra ID arrivent au workspace par le paramètre de diagnostic du
  tenant, et l'exécuteur d'identité nomme le sien (`EREGION_TENANT_ID`,
  `glorfindel/providers/azure/identity_contract.py:83`). Dans le périmètre de cette note, il ne change pas.

### 1.4 Ce qui ne voit que A

Les 27 appels `list_all()` de `glorfindel/providers/azure/` (12 modules) listent l'abonnement des
clients, et lui seul. Ce qu'ils nourrissent :

| Lecture | Où | Ce que B y perd |
|---|---|---|
| Le réseau du client, gardé contre un blocage (SEC2b) : VNet, IP publiques, préfixes, frontaux, NIC | `glorfindel/providers/azure/client_network.py:1-2`, `:55-85` ; `glorfindel/client_network.py:3-4` | les adresses publiques de B (une passerelle NAT, un frontal) ne sont pas connues : **blocables** ; les plages privées restent protégées par la liste livrée |
| L'IP privée → la VM, pour attribuer une ligne de stockage (T1041) | `glorfindel/providers/azure/readers.py:160-191` | voir le constat du §1.10 |
| La topologie d'une carte du plan de contrôle (AL1c) : un NSG, ses VM ; un disque, sa VM | `readers.py:402`, `glorfindel/watch/rules.py:31-44` | une carte de B n'est rangée sur aucune VM (SLF1) : sûr, mais aveugle |
| Les droits d'une VM (API des permissions) | `readers.py:126` | gardé par `_same_subscription` : refusé |
| Le journal d'activité d'une ressource, pour expliquer une alerte | `readers.py:215` | lu dans A seulement |
| L'audit des NSG de quarantaine, des orphelines, des dormantes, des allow retournées | `glorfindel/providers/azure/quarantine.py:436-449`, `sweep.py`, `dormant.py`, `turned.py`, `away.py` | rien n'est relu dans B |
| La posture (coffre, NSG), la préparation | `glorfindel/watch/rules.py:145-165` | une instance du connecteur, pour A |

### 1.5 L'isolation, le blocage, le restore et les coffres

- **L'isolation** crée un NSG de quarantaine par région, dans `isolation.quarantine_rg` ou dans le groupe
  de la VM (`quarantine.py:307-319`). Sa docstring le dit : une NIC ne prend qu'un NSG **de sa région et
  de son abonnement** (HM1). Un `quarantine_rg` unique ne vaut donc que pour A.
- **Le blocage** écrit dans les NSG de la VM (sa NIC, son sous-réseau) : même abonnement qu'elle.
- **Le coffre** : `action_backends` peut en déclarer plusieurs, mais `backup_vault()` rend le premier de
  type `azure_backup_vault` (`glorfindel/config.py:624-628`), et `resolve_backup_vault`
  (`config.py:652-669`) n'en connaît qu'un. L'instantané et le restore appellent Recovery Services sous
  `self._subscription_id` (`glorfindel/providers/azure/backup.py:59-71`, `restore.py:58`, `:105`). Un
  coffre ne protège peut-être que les VM de son abonnement et de sa région (HM2). C'est VLT1.
- **Le compte de transit** du restore : « same region/subscription » (`config.py:314-317`).

### 1.6 La configuration et l'autonomie par asset

- `glorfindel-config.yaml` ne nomme aucun abonnement. `monitoring_backends` nomme des workspaces
  (`config.py:300-305`), `action_backends` un coffre et son groupe (`config.py:309-317`), `isolation` un
  groupe (`config.py:426-437`).
- **L'autonomie se résout par le nom de la VM**, jamais par son identifiant : `AutonomyConfig.resolve(asset_name)`
  (`config.py:390`), l'entrée exacte puis le motif le plus long, sans la casse (AUC) ; les exclusions de
  même (`ExceptionConfig`, `config.py:328`). Le défaut est `human_only` (`config.py:1109`). **Une entrée
  `vm-web-01: non_disruptive` vaudrait pour la `vm-web-01` de B le jour où B est en portée**, et un motif
  `vm-*` pour toutes ses VM. La préparation (L6) les retiendrait en `human_only` jusqu'au contrôle, mais
  l'intention, elle, aurait été héritée sans que personne la déclare.
- **Le verrou d'une VM** est pris par son nom (`glorfindel/response/locks.py:61-73`) : deux homonymes de A
  et de B se sérialisent. C'est plus prudent que nécessaire, et sûr.
- **La classe d'un changement** (CFG4) range toute section qu'elle ne classe pas en « relâche »
  (`glorfindel/config_class.py:44-45`, `_others`, `:145-150`).

### 1.7 L'inscription d'O0, la règle de production, le battement et Orodruin

- **Le périmètre des injecteurs** nomme un abonnement, ou refuse tout (SEC11, R-19) :
  `Scope.for_bench` le prend dans `AZURE_SUBSCRIPTION_ID` (`eregion_core/inscription.py:113-120`) ; une
  cible d'un autre est refusée (`inscription.py:141-152`). La zone (`bench`, `twin`, `production`) est
  lue sur les tags de la cible et de son groupe (`inscription.py:1-16`), pas sur l'abonnement.
- **Ce que la watch en lit** : une fenêtre d'exercice ne marque une VM que si la watch la lit inscrite
  (`glorfindel/watch/loop.py:101-110`) ; sans la lecture, tout est réel. La provenance d'une carte n'est
  `bench` que dans le périmètre de `Scope.check`, sur l'abonnement de la variable
  (`glorfindel/calibration.py:95-105`) ; sinon `unknown`. Le budget du modèle tient pour réel ce qui est
  en production, illisible ou inconnu (`glorfindel/model_budget.py:361`). `zone_of` ne prend jamais
  « illisible » pour `bench` (`glorfindel/gestures.py:217-227`).
- **Le battement pour les injecteurs** (SEC5, N-03) porte le condensé d'**un** abonnement
  (`eregion_core/watch_gate.py:88-93`, écrit par `glorfindel/watch/beat.py:95-98`) ; l'injecteur refuse
  une watch « of another subscription » (`watch_gate.py:199-210`). Une watch de A et de B ne dit que A.
- **Le contrat d'Orodruin** n'est pas touché : il lit les droits d'Orodruin, pas ceux de la watch.
  Deux contacts seulement : ce battement, que lisent Annatar et Gothmog (§7, MSUB3b) ; et
  `EREGION_PROTECTED_SUBSCRIPTIONS`, les abonnements où Stratus ne s'arme jamais, « the bench, the VM,
  Imladris, when they differ from Orodruin's » (`eregion_core/orodruin.py:554-558`). Un abonnement que la
  watch défend en production y a sa place : une ligne de doc, pas de code.

### 1.8 L'hôte, le CD et le Terraform des rôles

- **Imladris** a une identité managée système. Son Terraform lui donne `Reader` sur le groupe du banc et
  `Log Analytics Reader` sur le workspace (`infra/glorfindel-host/main.tf:203-213`), la coupure des
  sessions VM par VM (`main.tf:232-236`) ; le rôle de la réponse sur le groupe reste un geste à la main
  (`main.tf:7-8`). Le provider prend un abonnement (`main.tf:31-35`).
- **Les rôles personnalisés** (`infra/identities/*.json`) portent `AssignableScopes:
  ["/subscriptions/<SUBSCRIPTION_ID>"]` (`glorfindel-response.json:21`). Un second abonnement du même
  tenant est déjà prévu par la doc : le nom d'un rôle est unique dans le tenant, on ajoute l'abonnement à
  ses portées par `az role definition update` (`docs/operations.md:1026-1041`).
- **Le CD** d'Imladris ne lit aucun abonnement. Son préflight passe la config d'Imladris à la lecture
  stricte d'A3 dans l'image candidate (`infra/glorfindel-host/cd/eregion_cd.py:1258-1290`). Une section
  nouvelle (`subscriptions:`) est donc refusée par toute release d'avant : un retour arrière tomberait sur
  une config que l'ancienne image refuse, et la watch sortirait en 2 (§7, MSUB6).
- **Le push** garde le mode de chaque VM tel qu'il est sur Imladris, jamais un plus hardi
  (`infra/glorfindel-host/host_config.py`, BL1c) : la même règle devra tenir pour un abonnement.

### 1.9 La console, aujourd'hui et en vol

- **GRP1** (#1189, en vol) : la carte groupée par abonnement ou par groupe ; une tuile d'un autre
  abonnement que celui de la watch est **hors de portée** — pointillé, puce OUT OF REACH · DETECT ONLY,
  aucun fil de PROTECT, aucun bouton qui écrit dans Azure, ses cartes se jugent. La règle :
  `outOfReach`, l'abonnement de la tuile comparé masqué à celui de `/api/config`
  (`eregion_console/static/infra_groups.js:30-33`, branche `lot/grp1-grouper`).
- **SUBN1** (#1190, en vol) : la watch lit le `displayName` de chaque abonnement vu, par
  `GET /subscriptions/{id}`, Reader suffit (`glorfindel/providers/azure/subscriptions.py`, branche
  `lot/subn1-noms-abonnements`) ; servi masqué dans `/api/watch/status`, jamais au modèle. Donner Reader
  sur B pour son nom est « un choix de l'opérateur, jamais requis » (`docs/operations.md`, « Les noms
  des abonnements », sur la branche).
- Les gardes de FS1 exigent déjà une VM « dans le périmètre de la watch »
  (`file-actions-signee.md`, §2.9) : le mot reste, son sens s'élargit (§3.2).

### 1.10 En chiffres, et deux constats

| Ce qui suppose un seul abonnement | Combien | Où |
|---|---|---|
| Lectures de `AZURE_SUBSCRIPTION_ID` dans `glorfindel/` et `eregion_console/` | 9 (dont 3 conseils de l'audit) | §1.1 |
| Lectures dans `eregion_core/` | 8 | §1.1 |
| Constructions du connecteur hors tests | 32 | §1.1 |
| Méthodes refusées hors de A | 15, plus le retrait d'une orpheline et une lecture | §1.2 |
| Usages de `_subscription_id` dans l'adaptateur Azure | 23, dans 9 modules | `glorfindel/providers/azure/` |
| Listages `list_all()` sur A seul | 27, dans 12 modules | §1.4 |
| Coffres lus | 1 (le premier déclaré) | §1.5 |
| Abonnements dans le battement | 1 | §1.7 |
| Rôles personnalisés à étendre | 5 | `infra/identities/` |

**Constat 1 — l'IP privée d'un autre abonnement.** La carte IP → VM écarte une adresse tenue par deux VM
de A (`readers.py:165-167`, L21), mais elle ne connaît pas B. Si une VM de B réutilise `10.0.0.4`, qu'une
VM de A tient aussi (deux VNet non appairés le font sans conflit), une ligne de stockage qui cite
`10.0.0.4` serait attribuée à la VM de A. À vérifier par un test (MSUB2) : quelles lignes passent par
cette carte, et lesquelles portent déjà l'abonnement du compte de stockage. Le correctif est dans le sens
de L21 : la carte de tous les abonnements lus, une adresse tenue deux fois écartée, et une ligne d'un
abonnement **vu mais non lu** jamais attribuée par l'adresse.

**Constat 2 — les adresses publiques de B.** La garde du réseau du client ne connaît que A
(`client_network.py:1-2`). Une adresse publique de B (une passerelle NAT, un frontal) peut être bloquée
sur une VM de A, comme une adresse du dehors. Les plages privées, elles, restent protégées. C'est la limite écrite de SEC2b (« the read lists
what the watch can see, never more ») ; MSUB2 la lève pour chaque abonnement lu.

Ces deux constats concernent la watch d'aujourd'hui, dès qu'un workspace est partagé. L'Orchestre les
route (rapport du lot).

---

## 2. Le périmètre

### 2.1 Dedans

- **Plusieurs abonnements d'un même tenant Entra ID**, lus et défendus par **une** watch.
- L'abonnement de la watch (A, `AZURE_SUBSCRIPTION_ID`) reste obligatoire et reste sa **maison** : son
  hôte, son battement principal, le défaut de ce qui n'est pas déclaré. Les autres s'ajoutent.
- Les VM d'abord, comme aujourd'hui ; le plan de contrôle (AL1) et Entra ID (C2) suivent leurs lectures.

### 2.2 Dehors

- **Le multi-tenant** : un abonnement d'un autre tenant, Azure Lighthouse, une identité invitée.
- **Ce que voit le modèle** (§6).
- **Le code, les rôles, le Terraform et tout `apply`** : les lots du §7, sur le mot de Jonathan.
- **Plusieurs watch pour un client** (une par région, une haute disponibilité) : un autre sujet.

### 2.3 Ce qui préparerait le multi-tenant, sans le faire

- **Lire le tenant de chaque abonnement.** `GET /subscriptions/{id}`, que SUBN1 fait déjà, rend aussi
  son `tenantId` (HM3). La watch le garde avec le nom. Un abonnement déclaré d'un autre tenant que le sien
  est **refusé**, et dit : « another tenant: not supported ». Le refus est le crochet du lot futur.
- **Une seule identité, des rôles par portée** (§3) : c'est la forme d'une autorisation de Lighthouse
  (un principal, un rôle, une portée d'abonnement ou de groupe). La voie recommandée s'y transpose ; une
  identité par abonnement, non.
- **Ce que Lighthouse ne prendrait pas** : d'après la documentation, ses autorisations n'admettent pas de
  rôle personnalisé (HM4). Les cinq rôles d'Eregion, étroits, ne passeraient pas ; la réponse demanderait
  un rôle intégré plus large (`Network Contributor`). C'est la question de fond du multi-tenant, et la
  raison de ne pas le faire ici.
- **Les clés** : tout ce que MSUB2 range par abonnement (le nom, le réseau, l'état) prend l'identifiant
  entier de l'abonnement, jamais un index ; un tenant de plus n'y change rien.

---

## 3. L'identité et le rayon d'action

### 3.1 Le principe

- **Le moindre privilège** : chaque identité tient ce que son code appelle, sur les groupes inscrits, et
  rien d'autre ; jamais `Contributor` sur un abonnement (`modele-de-menace.md`, la ligne « Une identité de
  Glorfindel qui peut tout sur l'abonnement »).
- **Les rôles déclarés en IaC** (`module-isolation-iac.md`) : une attribution se lit dans un fichier
  versionné, se relit au plan, se retire par le même chemin. Aucune ne vient d'un clic oublié.
- **Glorfindel ne s'accorde jamais un droit** : aucun de ses rôles ne porte
  `Microsoft.Authorization/roleAssignments/write` (`infra/identities/glorfindel-response.json:5-16`). Ce
  n'est pas une garde de code : c'est l'absence du droit.

### 3.2 Les trois voies

**A — une seule identité pour la watch, un rôle dans chaque abonnement.** Celle d'aujourd'hui (sur
Imladris, l'identité managée de la VM ; sur un poste, le principal de la watch) reçoit dans B ce qu'elle
tient dans A : `Reader` et `Log Analytics Reader` pour lire ; `Eregion Glorfindel Response` sur chaque
groupe de B qui tient une VM défendue ; la coupure des sessions VM par VM. Les rôles personnalisés gagnent
B dans leurs portées (`docs/operations.md:1026-1041`). Une identité managée peut tenir des rôles dans tout
abonnement de son tenant (HM5).

**B — une identité par abonnement.** Une identité managée attribuée par l'utilisateur, ou un principal,
par abonnement ; la watch choisit la sienne pour chaque connecteur.

**C — un rôle au groupe d'administration.** Les rôles attribués au groupe d'administration qui contient
les abonnements du client ; ils s'héritent dans chacun.

| | A — une identité | B — une par abonnement | C — groupe d'administration |
|---|---|---|---|
| **Une watch compromise** (son conteneur, son hôte, son jeton) | écrit, avec le rôle de la réponse, dans les groupes inscrits des N abonnements en portée : l'union | **la même union** : sur un même hôte, chaque conteneur demande à IMDS le jeton de toute identité attachée, par son `client_id` (HM9) ; sur un poste, tous les secrets vivent dans le même environnement | écrit dans **tout groupe de tout abonnement** sous le groupe d'administration, présent et futur |
| **Ce qui borne** | le rôle (les écritures de la réponse seules), les groupes inscrits, les modes, la préparation | idem, plus une révocation par abonnement (qu'une attribution retirée donne aussi en A) | le rôle seul : aucune liste de groupes ni d'abonnements |
| **Un abonnement ajouté au client** | rien ne change tant que personne n'attribue de rôle | idem | **en portée sans que personne le déclare** : contraire à l'inscription explicite |
| **Notre identité surveillée** (SID1, AL1) | un appelant à reconnaître dans N journaux | N appelants à exclure des règles (`configured_identities`, `activity.py:286-291`) : autant d'angles morts | un appelant, mais des droits partout |
| **FS1** | la watch reste le seul écrivain ; la garde « dans le périmètre » devient « dans un abonnement en portée » | idem, et N identités à épingler côté file | la garde « dans le périmètre » ne borne plus rien que les droits ne bornent déjà |
| **Rotation, inventaire** (IDM1) | une identité, N attributions | N identités, N secrets ou N identités attachées, N lignes à `never_target` | une identité, une attribution très large |
| **Lighthouse plus tard** (§2.3) | se transpose | ne se transpose pas | ne se transpose pas |
| **Les limites d'Azure** | les portées d'un rôle personnalisé : une liste d'abonnements | idem | un rôle personnalisé n'admet qu'un groupe d'administration dans ses portées, et aucune `DataActions` à cette portée (HM6) |

**Au modèle de menace** (§5, « Ce qui le borne ») : la phrase « le groupe : `rg-celebrimbor` seul. Rien sur
l'abonnement » devient « les groupes inscrits de chaque abonnement en portée, déclarés » ; le rayon d'un
conteneur compromis devient l'union de ces groupes. Rien d'autre ne s'ouvre : ni un restore, ni une
suppression, ni une identité, ni un rôle. La voie C, elle, réécrirait la ligne en « tout groupe sous le
groupe d'administration ».

**À la file signée** (FS1) : la cible exécutée est celle de la proposition signée par la watch (SEC-B) ;
la watch ne propose que sur une VM d'un abonnement en portée ; une demande sur une VM de B quand B n'est
que vu ou lu est refusée par la garde, avant tout appel. Sans FS1 (`EREGION_ACTION_QUEUE` reste faux par
défaut), la console et le bot écrivent eux-mêmes, chacun sous son identité : chaque abonnement ajouté
demanderait aussi leurs rôles. C'est la question Q4.

### 3.3 La recommandation : A

**Une seule identité pour la watch, un rôle par abonnement en portée et par groupe inscrit, déclarés en
IaC.** Les raisons, dans l'ordre :
1. **B ne borne rien de plus** là où la watch tourne. Sur Imladris, le modèle de menace le dit déjà : le
   jeton de l'identité de la VM se lit de chacun des trois conteneurs ; il en irait de même de N identités
   attachées. Le rayon d'une watch compromise reste l'union des droits, quelle que soit la découpe.
2. **B coûte** : N identités à faire vivre, à épingler, à exclure du journal d'activité — et chaque
   exclusion est un angle mort pour SID1.
3. **C contredit le principe** : un abonnement créé demain sous le groupe d'administration serait en
   portée sans décision, et le rôle de la réponse vaudrait pour tous ses groupes.
4. **A se transpose** à Lighthouse le jour du multi-tenant.

Ce que la recommandation laisse ouvert : l'union est réelle. Elle se borne par **ce que l'on déclare**
(§4), pas par la découpe des identités. Une séparation qui borne vraiment, une watch par hôte et par
abonnement, est le contraire de la direction (« une watch par client ») ; elle reste possible plus tard
pour un client qui l'exige, avec deux watch.

---

## 4. L'inscription et l'autonomie par abonnement

### 4.1 Trois états : vu, lu, en portée

Proposé : un abonnement **vu** est distinct d'un abonnement **déclaré**, et un abonnement déclaré pour
lire est distinct d'un abonnement déclaré pour agir.

```
 inconnu
   │  un workspace en remonte une VM (aucun geste)
   ▼
 vu ─────────── détection seule ; ses cartes se jugent ; aucune écriture ;
   │            son nom si la watch a Reader (SUBN1)
   │  l'opérateur le déclare reach: read (la file de CFG1 ; resserre)
   ▼
 lu ─────────── + Reader lu : son réseau (gardé du blocage), la topologie,
   │            l'IP → VM, la posture, la préparation ; aucune écriture
   │  l'opérateur le déclare reach: act (la file de CFG1 ; relâche, confirmé)
   │  ET le rôle de la réponse lu sur le groupe de la VM
   ▼
 en portée ──── isoler, bloquer, lever, instantané, derrière les gardes ;
                human_only par défaut ; la préparation (L6) avant toute autonomie
```

- **vu** : ce qu'on a aujourd'hui pour B. Aucun geste, aucun fichier. La console dit OUT OF REACH ·
  DETECT ONLY (GRP1).
- **lu** : déclaré dans la configuration, `reach: read`. La watch y lit avec `Reader` : le réseau du
  client (ses adresses publiques gardées du blocage, constat 2), la topologie, l'IP → VM (constat 1), la
  posture, la préparation (qui dit `read_only_subscription` au lieu de `other_subscription`). Toujours
  aucune écriture : la console garde la puce DETECT ONLY.
- **en portée** : déclaré `reach: act`, **et** les droits lus sur Azure (§5.3). La réponse y devient
  possible, derrière les mêmes gardes que dans A, `human_only` par défaut.
- **Les droits seuls ne font rien.** Un administrateur qui donne par erreur le rôle de la réponse à la
  watch sur un abonnement non déclaré ne la fait pas agir : `_same_subscription` refuse hors de la liste
  déclarée, comme aujourd'hui hors de A.
- **La déclaration seule non plus.** `reach: act` sans les droits : la préparation dit ce qui manque
  (`permissions_unknown`, ou les droits absents, `readiness.py`), et la console le montre (§5.1).

« Inscrit », au sens d'O0, reste le mot des injecteurs (des tags sur la cible et son groupe). La watch ne
s'inscrit nulle part : elle **déclare** ce qu'elle lit et où elle agit.

### 4.2 La déclaration, proposée

Une section de `glorfindel-config.yaml`, lue strictement (A3) :

```yaml
subscriptions:
  - id: <id de l'abonnement B>          # un GUID ; jamais montré entier par la console (masqué, SEC1)
    reach: act                           # read | act ; absent : refusé (pas de défaut implicite)
    quarantine_rg: rg-glorfindel-quarantine   # optionnel ; sinon le groupe de la VM (comme aujourd'hui)
    autonomy:
      default: human_only               # le défaut de cet abonnement ; human_only si absent (Q3)
```

- A n'y figure pas : c'est la maison, `reach: act`, implicite.
- Un abonnement listé deux fois, un identifiant qui n'est pas un GUID, un `reach` inconnu : la config est
  refusée, comme tout écart d'A3.
- Un abonnement d'un autre tenant (lu au démarrage, §2.3) : refusé à la lecture d'Azure, dit, et tenu en
  « vu ».
- Le coffre par abonnement et par région est l'affaire de VLT1 (§7) ; il s'écrira dans `action_backends`.

### 4.3 L'autonomie d'un abonnement qu'on vient d'ajouter

Le principe d'Eregion : `human_only` par défaut ; la sûreté ne se délègue jamais à la confiance du modèle.

- **Proposé (Q3) : un abonnement ajouté n'hérite de rien.** Ses VM prennent le défaut de son entrée,
  `human_only` s'il n'en dit rien — jamais le défaut global, ni un motif, ni une entrée exacte écrite pour
  une VM de A. Aujourd'hui, la résolution se fait par le nom (`config.py:390`) : `vm-web-01` de B
  prendrait l'entrée de `vm-web-01` de A, et `vm-*` toutes les VM de B (§1.6).
- **Les entrées propres à B** : `autonomy.assets` gagne une clé `subscription` (l'identifiant de B), et
  une entrée sans elle ne vaut que pour A. Deux homonymes, un par abonnement, ont chacun la leur.
- **Ce qui reste** : le verrou de préparation (L6) ; une VM de B configurée `non_disruptive` n'agit seule
  qu'une fois `ready`, ou ses réserves confirmées ; le seuil de confiance, les tirages qui s'accordent, les
  gardes de `decide`, le plafond de la règle (RDW1).
- **Un passage de B en `human_only`** (son défaut, ou `reach: act` retiré) est le geste d'urgence pour B,
  annoncé fort comme le passage en masse de CFG1 (Q11).
- **`imladris-push`** garde le `reach` et l'autonomie de chaque abonnement tels qu'ils sont sur Imladris,
  jamais plus hardis, et le dit, comme pour les VM (BL1c). `HUMAN_ONLY=1` remet aussi chaque abonnement en
  `human_only`.

### 4.4 La règle de production, abonnement par abonnement

- **La règle ne change pas, et elle ne porte pas sur un abonnement.** Elle porte sur les injecteurs, cible
  par cible : la zone se lit sur les tags de la cible **et** de son groupe ; une zone absente, inconnue ou
  en désaccord est refusée (`inscription.py:1-16`). En `production`, une technique non destructive
  seulement ; jamais une panne.
- **Les injecteurs ne voient pas plus loin.** Leur périmètre nomme un abonnement (SEC11) ; la watch
  multi-abonnement n'élargit pas le leur. Un banc dans B serait un autre périmètre d'injecteur, un autre
  sujet.
- **Ce que la watch tient pour réel** ne change pas non plus : une VM de B non inscrite, ou dont les tags
  ne se lisent pas, est réelle pour la fenêtre d'exercice, la provenance et le budget du modèle (§1.7).
  **Proposé : aucune zone n'est donnée à un abonnement** ; un abonnement ajouté est présumé réel.
  Déclarer `zone: bench` sur un abonnement ferait d'une erreur de déclaration une charge réelle traitée
  en banc ; la zone reste là où O0 l'a mise, sur chaque ressource.
- **Stratus** : un abonnement que la watch défend s'ajoute à `EREGION_PROTECTED_SUBSCRIPTIONS`
  (`orodruin.py:554-558`) ; une ligne de `docs/operations.md`.

---

## 5. « Ajouter les accès », proposé par la console

### 5.1 Ce que la tuile hors de portée montre

Sur une tuile vue ou lue (GRP1), un panneau « What it takes to act here », en anglais comme la console :

- **L'état** : seen / read / in reach, et ce qui manque pour l'état suivant.
- **Le rôle qui manque, et sa portée**, lus par la watch, jamais devinés :
  - pour **lire** : `Reader` sur l'abonnement (le nom, le réseau, la topologie) ; `Log Analytics Reader` est
    déjà tenu, puisque le workspace voit la VM ;
  - pour **agir** : `Eregion Glorfindel Response` sur le groupe de la VM (et sur celui de sa quarantaine) ;
    `Eregion Glorfindel Session Drain` sur la VM ; les portées du rôle personnalisé étendues à B ;
  - **jamais** le restore à la watch : `Eregion Glorfindel Restore` va à la console et au bot, ou à
    l'exécuteur de FS1g (SEC7, `modele-de-menace.md`).
- **La commande `az`**, avec des variables, jamais un identifiant écrit en clair (MSK) ; l'abonnement se lit
  par son nom (SUBN1), le principal par la sortie de Terraform :

  ```bash
  SUB_B=$(az account show --subscription "<nom de l'abonnement B>" --query id -o tsv)
  WATCH=<object id du principal de la watch : terraform output, ou la carte des identités>
  az role assignment create --assignee-object-id "$WATCH" --assignee-principal-type ServicePrincipal \
    --role Reader --scope "/subscriptions/$SUB_B"
  az role assignment create --assignee-object-id "$WATCH" --assignee-principal-type ServicePrincipal \
    --role "Eregion Glorfindel Response" --scope "/subscriptions/$SUB_B/resourceGroups/rg-app"
  ```

  précédée de l'extension des portées du rôle personnalisé (le bloc de `docs/operations.md:1026-1041`).
- **Le bloc Terraform** du module d'Imladris (MSUB5), une entrée à ajouter ; la console y laisse le
  gabarit `<id de l'abonnement B>`, l'identifiant ne s'écrit jamais dans la page :

  ```hcl
  defended_subscriptions = {
    "b" = {
      subscription_id   = "<id de l'abonnement B>"
      reach             = "act"
      response_groups   = ["rg-app"]
      session_drain_vms = ["vm-web-01"]
    }
  }
  ```

- **La déclaration** dans la configuration (§4.2), par un bouton qui dépose une demande (§5.4).
- Le panneau se calcule dans la watch et se sert à la console ; la console ne lit aucun droit elle-même.

### 5.2 La console explique, l'opérateur agit

- **Glorfindel ne s'accorde jamais un droit** (§3.1) : aucune de ses identités ne peut écrire une
  attribution, et la console n'a aucun bouton qui l'essaie.
- **La console ne fait qu'expliquer.** Le geste reste à l'opérateur, ou à l'administrateur du client,
  avec son identité à lui : un `az`, ou un `terraform apply` relu au plan.
- La commande montrée ne porte aucun secret ; elle se copie, elle ne se lance pas depuis la page.

### 5.3 Comment la watch voit l'accès arriver

- **La lecture de l'abonnement** : à la tournée de SUBN1 (au démarrage, toutes les 6 h, à la passe
  d'entretien suivante pour un abonnement qui apparaît), un `GET /subscriptions/{id}` qui réussit dit que
  Reader est là (HM7 : un rôle au seul groupe suffit peut-être à rendre l'abonnement visible).
- **Les droits d'agir** : l'API des permissions, groupe par groupe, déjà lue par `check_permissions`
  (`readers.py:126`) et la préparation, rejouée pour une VM d'un abonnement déclaré `act` : à la
  découverte, à la cadence de la posture, et sur demande depuis le panneau (« Check again »). Rien ne se lit
  pour un abonnement seulement vu.
- **Ce qui passe de « detect only » à « en portée »**, et seulement quand les deux tiennent : la
  déclaration `reach: act` appliquée (§5.4) **et** les droits de la réponse lus sur le groupe de la VM.
  Alors la tuile perd son pointillé, ses boutons qui écrivent reviennent, les fils de PROTECT aussi ; son
  mode se montre et se règle. Elle reste en `human_only` (§4.3) : « en portée » veut dire qu'un humain peut
  approuver une action, pas que Glorfindel agit seul.
- **Le chemin inverse** : un droit retiré, ou une lecture des permissions en échec, ramène la VM en
  `not_ready` à la passe suivante ; la tuile repasse DETECT ONLY, et la raison est dite. Une isolation déjà
  posée dans B reste tenue : la réaffirmation et la levée en ont besoin (une ligne du lot MSUB3).
- **La console** reçoit l'état de chaque abonnement, masqué, dans `/api/watch/status` (comme les noms de
  SUBN1) ; `outOfReach` de GRP1 lit cet état au lieu de comparer à `/api/config`.

### 5.4 Ce qui s'écrit, et ce qui se confirme (CFG1)

La console demande, la watch écrit, relâcher se confirme (CFG1, Q1, Q2, Q5). Le classement proposé, dans
le sens des mots de CFG1 (relâcher : Glorfindel agit plus seul, ou voit moins, ou dit moins) :

| Geste | Classe | Pourquoi |
|---|---|---|
| ajouter un abonnement `reach: read` | resserre | Glorfindel voit plus, n'agit pas plus |
| passer un abonnement à `reach: act` | **relâche** : confirmation tapée, délai de 10 minutes, annonce sur la console et Discord | des actions deviennent possibles dans B |
| poser `autonomy.default` de B plus hardi que `human_only`, ou une entrée `non_disruptive` dans B | relâche (la préparation L6 en plus) | comme pour A |
| retirer `act` (revenir à `read`) | resserre, **annoncé fort** | le désarmement de B, comme le passage en masse (Q11) |
| retirer un abonnement lu | relâche | Glorfindel voit moins : ses adresses publiques redeviennent blocables |

- **CFG4** ajoute `subscriptions` à ce qu'il classe (aujourd'hui, toute section inconnue relâche,
  `config_class.py:44-45`).
- **La demande** est une demande de configuration de la file (CFG5), jamais une écriture de la console ;
  l'attente d'un relâchement suit CFG1 §4.4 (CFG6).
- **Ce qui ne s'écrit jamais par la console** : une attribution de rôle, une identité, le restore.
- **La CLI** garde son chemin direct, l'issue de secours (FS1, Q4), avec la même classe et la même annonce.

---

## 6. Ce qui ne change pas

- **Ce que voit le modèle.** Aucun abonnement, ni son identifiant, ni son nom, ni son `reach`, n'entre
  dans `_build_user_message()`, `_SYSTEM_PROMPT` ou les exemples ; le nom de SUBN1 ne va qu'à la console.
  Aucun lot de cette note ne touche les trois zones du prompt (`CLAUDE.md`, « Conventions ») : aucun
  n'appelle le run de bout en bout.
- **Jamais de panne ni d'action destructive sur une charge réelle.** Le destructif n'est dans aucun rôle de
  la watch ni dans aucun verbe de la file ; la règle de production reste celle des injecteurs (§4.4).
- **`human_only` par défaut**, pour A comme pour tout abonnement ajouté (§4.3) ; la sûreté reste dans le
  code — les gardes, la préparation, le seuil —, jamais dans la confiance du modèle.
- **Un tenant**, lu comme aujourd'hui (Entra ID, C2).
- **`WrongSubscriptionError` reste la garde** : elle compare à la liste déclarée `act` au lieu de A seul.
  Une cible d'un abonnement vu ou lu est refusée comme aujourd'hui, au même endroit.

---

## 7. Les lots

En jours de travail effectif, à ±50 %, comme la feuille de route. Les mutants sont estimés ; l'Orchestre
donne les plages. Session Glorfindel sauf mention.

| Lot | Session | Ce qu'il touche | Taille | Risques | Mutants |
|---|---|---|---|---|---|
| **SUBN1, GRP1** (en vol) | Glorfindel, Console | le nom de chaque abonnement vu ; la carte groupée, la tuile hors de portée | — | — | — |
| **MSUB2** — la lecture multi-abonnement | Glorfindel | la section `subscriptions:` lue strictement (`reach: read` seul accepté ; `act` refusé, dit, jusqu'à MSUB3) ; un connecteur par abonnement (`connector_for`) au lieu des 32 constructions ; les 27 listages par abonnement lu ; la carte IP → VM et le réseau du client faits de tous (constats 1 et 2), une adresse tenue deux fois écartée ; une lecture refusée dans B ne dégrade jamais celle de A (« list that can't be trusted » par abonnement) ; la topologie ; la posture et la préparation (`read_only_subscription`) ; la fraîcheur d'`AzureActivity` par `SubscriptionId` (LOGF1) ; le `tenantId` lu, un autre tenant refusé ; l'état servi masqué ; `fake_azure` à deux abonnements | 5 j | le temps d'une passe et le throttling d'ARM (N fois les listages) ; une fusion fautive des listes ; la machine à invariants à étendre | ~12 |
| **MSUB6** — le CD et le push | Glorfindel (Imladris) | `host_config.py` : le `reach` et l'autonomie par abonnement jamais plus hardis, `HUMAN_ONLY=1` aussi pour eux ; le préflight du CD : la config lue par l'image candidate **et** par celle qui tourne, ou la section `subscriptions:` refusée tant que la release d'avant ne la connaît pas (retour arrière sûr) | 1,5 j | un retour arrière sur une config que l'ancienne image refuse : la watch sort en 2 | ~4 |
| **MSUB5** — le Terraform des rôles | Infra (module d'Imladris) | `defended_subscriptions` dans `infra/glorfindel-host/` : `Reader` par abonnement, la réponse par groupe, la coupure VM par VM, chaque nom relu sur Azure au plan ; une précondition refuse un abonnement d'un autre tenant et A en double ; `tftest` contre le faux azurerm ; la doc des portées des rôles personnalisés ; l'`apply` reste à Jonathan | 2 j | une attribution dans un autre abonnement depuis un seul provider (HM8) ; la réponse reste un geste à la main aujourd'hui (BL1c) : la déclarer ici change cette posture, à trancher avec elle | ~3 |
| **VLT1** — plusieurs coffres | Glorfindel | `backup_vault()` choisi par l'abonnement et la région de la VM, jamais le premier ; `resolve_backup_vault` de même ; l'instantané et le restore refusés sans coffre de l'abonnement, et dits ; l'enquête lit le bon coffre | 2 j | un coffre d'un autre abonnement pris pour le bon (HM2) | ~5 |
| **MSUB3** — l'action multi-abonnement | Glorfindel | `_same_subscription`, `_orphan_writer` et `sweep.py:257` comparent à la liste `act` ; le NSG de quarantaine par abonnement et par région (`quarantine_rg` de l'entrée) ; l'audit de la quarantaine, les orphelines, les dormantes, les retournées, par abonnement ; l'autonomie par abonnement (Q3) ; la préparation ; la garde de FS1 « dans un abonnement en portée » ; les boutons de la console selon l'état ; le modèle de menace (§5) réécrit | 6 j | **le chemin d'isolation** : un critère de la 1.0 (« aucun constat haut ouvert sur le chemin d'isolation ») ; I1–I12 à tenir sur deux abonnements, plus une propriété : aucune écriture hors d'un abonnement `act` (l'oracle dans le journal du faux, A0) ; les homonymes entre abonnements | ~15 |
| **MSUB3b** — le battement pour les injecteurs | Glorfindel, avec Annatar et Gothmog (le socle) | `eregion_core/watch_gate.py` : le battement porte le condensé de chaque abonnement en portée (Q5), l'ancien champ gardé ; l'injecteur accepte une watch dont la liste contient son abonnement ; signé comme aujourd'hui (SEC19) ; `orodruin-contract.md` relu | 1,5 j | un injecteur d'avant qui lit le nouveau battement ; une liste qui s'allonge sans qu'on la voie | ~5 |
| **MSUB4** — la console, « ajouter les accès » | Console | le panneau du §5.1, calculé par la watch ; « Check again » ; la demande de configuration (`reach`, autonomie de B) par la file ; `outOfReach` sur l'état servi ; l'échappement de tout ce qui vient d'Azure | 3 j, après CFG5 et CFG6 | une commande montrée qui expose un identifiant ; un bouton qui écrirait sans la file | ~8 |
| **MSUB7** — la mesure au banc | Tests, gestes de Jonathan | un second abonnement du même tenant (Q8), une VM d'essai qui écrit dans le workspace du banc ; séance 1, après MSUB2, MSUB5 et MSUB6 : vu, puis Reader posé et lu, constats 1 et 2, HM3, HM7, HM8 ; séance 2, après MSUB3 : la réponse posée, isoler et lever sur approbation, un troisième abonnement non déclaré refusé ; coche « Garde d'abonnement mesurée sur un second abonnement réel » (ROADMAP, critères avant le mode autonome) | 1 j d'écriture, deux séances | le coût d'un abonnement de plus ; l'ordre des gestes | 0 |

**Total** : environ 22 jours, et une cinquantaine de mutants.

**L'ordre.** SUBN1 et GRP1 d'abord (en vol). Puis MSUB2, et MSUB6 avec lui : la section `subscriptions:` ne
doit pas atteindre Imladris avant que le retour arrière la supporte. MSUB5 en parallèle de MSUB2 (des
lectures seulement au départ). La première séance de MSUB7. Puis VLT1, MSUB3, MSUB3b. MSUB4 attend CFG5 et
CFG6 (la demande de configuration et l'attente d'un relâchement) ; d'ici là, la déclaration s'écrit à la
main ou par la CLI. La seconde séance de MSUB7 en dernier.

**Où VLT1 et SUBN1 se rangent.** SUBN1 est la première lecture multi-abonnement : la tournée qui dira
l'arrivée de Reader (§5.3), et celle qui lira le tenant (§2.3). VLT1 se place avant MSUB3 : sans lui,
l'instantané d'une VM de B partirait vers le coffre de A, ou vers aucun ; MSUB3 peut aussi partir sans
instantané ni restore dans B, et VLT1 après (Q6).

---

## 8. Les questions pour Jonathan

Posées une à une par l'Orchestre. L'option recommandée vient en premier, avec sa raison. Rien n'est
décidé à sa place.

**Q1 — Quelle identité pour une watch qui tient plusieurs abonnements ?** (§3)
1. **Une seule identité, celle de la watch, avec dans chaque abonnement ajouté les rôles qu'elle tient
   dans le sien, à la portée des groupes inscrits, déclarés en IaC (recommandée).** Une identité par
   abonnement ne borne rien de plus sur un même hôte (chaque conteneur lit le jeton de toute identité
   attachée), coûte N identités à faire vivre et autant d'angles morts dans la surveillance de notre propre
   identité ; cette voie se transpose à Lighthouse le jour du multi-tenant.
2. Une identité par abonnement (attribuée par l'utilisateur, ou un principal), la watch choisissant la
   sienne par connecteur. Une révocation par abonnement, la même union des droits sur l'hôte.
3. Les rôles au groupe d'administration du client. Une attribution pour tout, mais tout abonnement créé
   dessous entre en portée sans décision, et le rôle de la réponse vaut pour tous ses groupes.

**Q2 — Qu'est-ce qui fait d'un abonnement vu un abonnement où la watch lit, puis agit ?** (§4.1, §4.2)
1. **Une déclaration dans `glorfindel-config.yaml` (`subscriptions:`, `reach: read` ou `act`), passée par
   la file de CFG1 — `act` confirmé comme un relâchement —, et les droits lus sur Azure : les deux, jamais
   l'un sans l'autre (recommandée).** Un rôle donné par erreur ne fait pas agir la watch, et une
   déclaration sans droits dit ce qui manque ; le fichier reste la référence.
2. Les droits seuls : la watch agit là où son identité peut écrire. Rien à déclarer, mais le périmètre
   devient celui des attributions d'Azure, que personne ne relit dans Eregion.
3. Une variable d'environnement posée au déploiement (une liste d'abonnements dans `host.env`). Simple,
   mais hors de la console et de sa classe resserre/relâche, et sans niveau « lu ».

**Q3 — Les entrées d'autonomie d'aujourd'hui valent-elles pour un abonnement ajouté ?** (§4.3)
1. **Non : un abonnement ajouté n'hérite de rien ; ses VM prennent le défaut de son entrée, `human_only`
   s'il n'en dit rien ; une entrée de `autonomy.assets` sans clé `subscription` ne vaut que pour
   l'abonnement de la watch (recommandée).** Aujourd'hui, l'autonomie se résout par le nom : une entrée
   écrite pour une VM de A, ou un motif `vm-*`, rendrait autonomes, dans l'intention, les VM de même nom de
   B sans que personne l'ait déclaré.
2. Oui, comme aujourd'hui : les noms et les motifs valent partout, et le verrou de préparation (L6) tient
   les VM de B en `human_only` jusqu'à leur contrôle.
3. Les motifs non, les noms exacts oui.

**Q4 — Dans un abonnement ajouté, par où passe le geste d'un humain (approuver, isoler, lever) ?** (§3.2)
1. **Par la file signée seulement (FS1) : la watch exécute, la console et le bot n'y reçoivent aucun rôle
   d'écriture ; dans B, ces gestes attendent que la file soit allumée (recommandée).** Un abonnement
   nouveau part dans la posture visée par la 1.0 : une seule identité écrit dans B.
2. Comme dans l'abonnement de la watch : la console et le bot écrivent eux-mêmes, chacun avec ses rôles,
   dans chaque abonnement ajouté. Disponible tout de suite, mais trois identités de plus écrivent dans B
   hors d'Imladris.
3. Aucun geste dans B avant que FS1 soit allumée : `act` refusé jusque-là, B en lecture et en détection
   seulement. Le plus prudent, mais l'isolation dans B attend la bascule de la file.

**Q5 — Que dit le battement pour les injecteurs, quand la watch tient plusieurs abonnements ?** (§1.7, MSUB3b)
1. **Le condensé de chaque abonnement en portée, en liste, l'ancien champ gardé pour celui de la watch ;
   un injecteur accepte une watch dont la liste contient son abonnement (recommandée).** Un injecteur d'un
   autre abonnement du client trouve sa watch, et un injecteur d'avant lit toujours l'ancien champ.
2. L'abonnement de la watch seul, comme aujourd'hui : un injecteur ne joue que dans l'abonnement de la
   watch. Rien à changer côté Annatar et Gothmog, mais un banc dans B n'aura jamais de watch.
3. Les abonnements lus aussi (`read`), pas seulement ceux en portée : la watch y détecte, mais n'y
   contient rien.

**Q6 — Le coffre dans un autre abonnement : VLT1 avant ou après l'action multi-abonnement ?** (§7)
1. **VLT1 avant MSUB3 : un coffre par abonnement et par région, l'instantané et le restore refusés sans
   lui, et dits (recommandée).** L'instantané est une des actions autonomes ; il ne doit jamais partir
   vers le coffre d'un autre abonnement, ou vers aucun.
2. MSUB3 d'abord, sans instantané ni restore dans B (refusés, dits) ; VLT1 ensuite. L'isolation dans B
   arrive plus tôt.

**Q7 — Sur une tuile hors de portée, la console montre quoi pour « ajouter les accès » ?** (§5.1)
1. **Les deux : la commande `az`, avec des variables et sans identifiant en clair, et le bloc Terraform du
   module d'Imladris (recommandée).** L'opérateur d'un poste a `az` ; celui qui tient son infrastructure
   en IaC garde ses attributions dans son code (`module-isolation-iac.md`).
2. La commande `az` seule. Plus court, mais une attribution faite à la main n'est relue par aucun plan.
3. Le bloc Terraform seul. Tout en IaC, mais rien pour l'opérateur qui ne tient pas ce module.

**Q8 — Sur quoi mesure-t-on, avant le code de l'action ?** (§7, MSUB7)
1. **Un second abonnement du même tenant, dédié, vide hormis une VM d'essai qui écrit dans le workspace du
   banc ; d'abord en lecture, puis la réponse posée sur son seul groupe (recommandée).** C'est la règle
   des environnements de test (ROADMAP : lecture seule d'abord, écritures sur des VM dédiées) ; elle coche
   le critère « garde d'abonnement mesurée sur un second abonnement réel ».
2. Un abonnement proche de la production, en lecture seule : plus représentatif (des homonymes, des
   adresses réutilisées), mais aucune écriture mesurée, et rien de lui dans le dépôt.
3. Pas de mesure avant la 1.0 : les lots partent sur le faux Azure seul.

---

## 9. Les hypothèses, à mesurer avant le code qui en dépend

| | L'hypothèse | Sa source | Mesurée par |
|---|---|---|---|
| HM1 | Une NIC ne prend qu'un NSG de sa région et de son abonnement | `quarantine.py:311-312` (ce que le code en dit), documentation | MSUB7, séance 2 |
| HM2 | Un coffre Recovery Services ne protège que les VM de son abonnement et de sa région | documentation ; `config.py:314` pour le compte de transit | VLT1, au banc |
| HM3 | `GET /subscriptions/{id}` rend le `tenantId` de l'abonnement sous Reader | documentation de l'API d'ARM | MSUB7, séance 1 |
| HM4 | Une autorisation d'Azure Lighthouse n'admet pas de rôle personnalisé | documentation de Lighthouse | hors du périmètre (multi-tenant) |
| HM5 | Une identité managée peut tenir des rôles dans tout abonnement de son tenant | documentation d'Entra ID | MSUB7, séance 1 |
| HM6 | Un rôle personnalisé n'admet qu'un groupe d'administration dans ses portées, et aucune `DataActions` à cette portée | documentation du RBAC d'Azure | non mesurée : voie C écartée |
| HM7 | Un rôle limité à un groupe rend l'abonnement visible à `GET /subscriptions/{id}` | SUBN1 (`docs/operations.md`, sur la branche) | MSUB7, séance 1 |
| HM8 | `azurerm_role_assignment` attribue dans un autre abonnement du tenant depuis un seul provider (la portée est un identifiant entier) | documentation du provider | MSUB5, au plan |
| HM9 | Sur une VM, tout processus obtient d'IMDS le jeton de toute identité attribuée par l'utilisateur attachée à la VM, par son `client_id` | documentation d'IMDS ; `modele-de-menace.md` §5 pour l'identité système | non mesurée : la voie B n'est pas recommandée ; à mesurer, de la main de Jonathan, seulement si Q1 la retient |
| HM10 | Le journal d'activité de B n'arrive au workspace que par un paramètre de diagnostic posé sur B, et ses lignes portent `SubscriptionId` | `activity.py:39-44`, `activity_log.tf:1-7` | MSUB7, séance 1 |
