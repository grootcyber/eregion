# La classification des VM : des niveaux et leurs effets (PRI1, #1216) — conception

_Note de conception, sans code, 26/11. Décision de Jonathan, le 26/11 : **« une vraie classification »** —
plusieurs niveaux, chacun avec son effet ; une note d'abord. CRT1 (#1215), qui l'affichera, reprend
après elle. Statut : **proposée** ; dix questions ouvertes (§9). Rien n'est codé, rien n'est appliqué._

**Lié** : [`configuration-console.md`](configuration-console.md) (CFG1 : la console demande, la watch
écrit ; resserrer s'applique, relâcher se confirme ; la vue « Relaxed ») ;
[`enquete-raisonnee.md`](enquete-raisonnee.md) (§5.1, le budget de l'enquête ; §15, la porte des appels
PRT1 à PRT3) ; [`dossier-isolation.md`](dossier-isolation.md) (« Un objet critique », en attendant la
criticité d'un objet) ; [`watch-multi-abonnement.md`](watch-multi-abonnement.md) (MSUB1 : rien n'est
hérité d'un abonnement à l'autre) ; [`docs/raisonnement.md`](../raisonnement.md) (§2.5, le budget du
modèle) ; [`docs/glorfindel.md`](../glorfindel.md) (« Modes d'autonomie par asset », la préparation L6) ;
[`docs/architecture.md`](../architecture.md) (le vocabulaire, les trois zones).

**Règle de lecture.** Ce qui est lu dans le dépôt est une affirmation, avec son fichier et sa ligne, au
commit `d772cb1b` (une fusion plus récente de `main` peut décaler les lignes). Ce que la note propose
est dit « proposé ». Les noms sont génériques : `vm-db-prod` (la base d'un ERP), `vm-web-01` (un frontal
redondant), `vm-dev-01` (une VM de développement, recréée chaque nuit).

---

## 0. En bref

**Le principe : la classe d'une VM est une déclaration de l'opérateur, et elle règle l'attention de
Glorfindel, jamais ses gardes.** Elle dit combien une VM compte pour le client ; le code en tire, de façon
déterministe, une part du budget du modèle, un rang dans la porte, une profondeur d'enquête, un bruit de
notification et un affichage. Elle ne relâche jamais seule une garde de sûreté : ni le seuil de confiance,
ni la porte destructive, ni la préparation (L6), ni le plafond de la règle (RDW1), ni `never_block`, ni la
gravité d'une technique, ni le mode. Monter d'un niveau resserre ; descendre relâche, et se confirme. La
question de fond, Q3, est posée à Jonathan.

- **Aujourd'hui, un seul oui/non** : `critical: true` sur une entrée d'`autonomy.assets` (PRT2, #1160).
  Il réserve aux graves de la VM une part du budget du modèle, et sa grave n'attend pas le refroidissement
  du fournisseur (§1.1). Rien d'autre ne le lit, hors de la classe d'un changement et du push vers
  Imladris (anciennement H0) (§1.2).
- **Trois axes, qui ne se remplacent pas** (§2.3) : la **zone** (`bench`, `twin`, `production` : ce qu'une
  expérience a le droit d'y faire, lue sur les tags), le **mode** (`human_only`, `non_disruptive` : ce que
  Glorfindel fait seul, la décision) et la **classe** (combien la VM compte : l'attention).
- **Trois niveaux proposés** (§3), des mots qui n'alarment pas : **`essential`** (une VM dont la perte
  arrête le métier ; le `critical: true` d'aujourd'hui), **`standard`** (le défaut, rien ne change), et
  **`quiet`** (une VM surveillée en silence : moins de bruit et de budget pour ses détections ordinaires,
  jamais pour ses graves). Aucun mot de la gravité des cartes (`critical`, `high`, `low`) : ils disent un
  événement, pas un objet.
- **Les effets** (§4, tableau au §4.8) : `essential` garde l'effet de PRT2 (la réserve, l'attente), a son
  dossier toujours composé, une enquête plus profonde à délai égal (0.7), un ping pour chaque carte qui
  attend un humain, et passe d'abord dans la porte à gravité égale — **un ordre entre les VM que la porte
  n'a pas aujourd'hui** (la première VM qui réessaie passe) et que PRI4 doit ajouter. `quiet` ne pingue
  plus l'ouverture d'un fil pour une détection basse, et ses détections basses ont un quart du budget par
  VM et passent les dernières. **Une grave reste grave à tous les niveaux** : sur une VM `quiet`, elle a
  le plancher, le rang de `standard`, et elle pingue même dans un fil ouvert en silence.
- **L'autonomie** (§4.5, Q4) : la classe ne décide pas ; le mode reste la décision. Proposé : passer une VM
  en `essential` ajoute une **réserve à sa préparation** (« ses actions seules, l'isolement compris,
  attendent qu'un humain l'ait voulu »), confirmée une fois, comme les autres réserves de L6. Jusque-là, la
  VM est en `human_only` : aucune action seule, ni isolement, ni blocage, ni instantané. Plus vite, oui,
  par le budget (et le rang, avec PRI4) ; jamais par une garde.
- **Le format** (§5), **tranché par Jonathan le 26/11** (sa proposition, Q5) : **une seule section
  `assets:`**, qui remplace `autonomy:` — `default_mode`, `allow_destructive`, et une `list` d'entrées
  (`match`, `mode` facultatif, `priority` facultative, `reason`). Le mode facultatif règle le constat 1
  (§1.4) : on classe une VM sans lui écrire de mode. Chaque champ se résout sur les entrées qui le portent :
  le mode par la règle d'aujourd'hui, la priorité par le plus haut niveau (proposé, Q6).
- **L'ancien format** (§5.4, Q7) : `autonomy:` entier et `critical: true` (lu comme `essential`), lus
  jusqu'à la 1.0 avec une note qui invite à migrer (`glorfindel config migrate`) ; les deux formats dans
  un même fichier sont une erreur de config ; la migration, à valeurs égales, est neutre.
- **Les deux lecteurs** (§5.5) : la watch (`glorfindel/config.py`) et le push vers Imladris
  (`infra/glorfindel-host/host_config.py`) lisent `assets:` de la même façon, changés dans le même lot et
  tenus égaux par un test. Le push ne baisse jamais un niveau : `essential` vient d'Imladris ou du poste,
  `quiet` seulement d'Imladris, où Jonathan le pose à la main jusqu'à CFG5. Une config d'Imladris que la
  watch refuserait est entière inconnue, comme aujourd'hui. Le push écrit le format que lit la release
  d'Imladris, et migre un Imladris encore en `autonomy:` ; la watch dit un `essential` perdu hors de la
  file.
- **Les classes de CFG1** (§6) : monter resserre (tout de suite, une ligne sur Discord) ; descendre relâche
  (le nom tapé, la raison, le délai) ; une entrée `quiet` se voit dans la vue « Relaxed ».
- **L'affichage** (§7, pour CRT1) : `ESSENTIAL` en marque neutre, jamais rouge ; rien pour `standard` ;
  `quiet` en gris ; une section « Priorities » dans la page Config ; une ligne au démarrage.
- **Ce qui ne change pas** : ce que voit le modèle (la classe n'entre jamais dans son message),
  `human_only` par défaut, la règle de production, les zones, les injecteurs.
- **Sept lots** (§10), environ 11,5 jours : PRI2 (le format `assets:` et la migration), CRT1 (l'affichage, repris),
  PRI3 (la réserve de préparation), PRI4 (l'ordre entre les VM, le budget de `quiet`, le dossier), PRI5
  (les notifications) en 0.6.x ; PRI6 (l'enquête) et le branchement de PRT3 en 0.7 ; PRI7 (retirer `critical`)
  à la 1.0.

---

## 1. L'état des lieux, lu dans le code

### 1.1 `critical: true` aujourd'hui (PRT2)

- **La clé** : `AutonomyRule.critical` (`glorfindel/config.py:359-371`), lue strictement : `true` ou
  `false`, sans guillemets ; une clé vide est refusée (`config.py:1123-1126`). « No Azure tag, no other
  source » (la docstring, `config.py:362-364`).
- **La VM critique** : `is_critical(name)` (`config.py:414-417`) — **toute** entrée qui la couvre, exacte
  ou par motif, suffit : « criticality only tightens ». C'est une autre règle que celle du mode, où
  l'entrée exacte l'emporte, puis le motif le plus long (`resolve`, `config.py:390-412`).
- **Le compte** : `critical_count()` (`config.py:419-422`) compte les **entrées** critiques, pas les VM :
  un motif `vm-erp-*` qui couvre cinq VM compte pour un.
- **La réserve des graves** : `min(réel, 2,50 $, 1 $ + 0,50 $ × entrées critiques)`
  (`glorfindel/model_budget.py:93-95`, `reserve()`, `:306-309`). La part au-dessus du plancher
  (`critical_part()`, `:311-316`) ne sert qu'aux graves des VM critiques : une grave sur une VM critique
  compte dans `real/critical`, borné par le seul réel ; les autres graves dans `real/noncritical`, qui
  s'arrête avant cette part (`_limit`, `:317-331` ; `_keys`, `:332-341`).
- **Où il joue** : seulement dans l'enveloppe du réel, et seulement pour une grave
  (`critical = envelope == REAL and grave and is_critical(vm)`, `model_budget.py:386`). Un exercice ne le
  lit jamais.
- **L'attente** : pendant le refroidissement du fournisseur, une grave sur une VM critique part tout de
  suite par le chemin du code, sans attendre (`_slowed`, `model_budget.py:409-416`). Elle attend encore sa
  place dans le plafond par minute de PRT1, comme toute grave (`docs/raisonnement.md`, §2.5).
- **La ligne de démarrage** du budget dit la réserve (`said()`, `model_budget.py:540-551`) ; celle de
  l'autonomie compte les entrées, sans dire lesquelles sont critiques (`glorfindel/watch/startup.py:113-117`).

### 1.2 Ce qui le lit

| Lecteur | Où | Ce qu'il en fait |
|---|---|---|
| La lecture stricte | `glorfindel/config.py:717` (`_AUTONOMY_ASSET_KEYS`), `:1123-1127` | accepte la clé, refuse tout sauf `true`/`false` |
| La VM et le compte | `config.py:414-422` | `is_critical`, `critical_count` |
| Le budget du modèle | `glorfindel/model_budget.py:246` (`_critical_count`), `:306-316`, `:386-391`, `:414` | la réserve, ses seaux, l'attente |
| La classe d'un changement | `glorfindel/config_class.py:17-19`, `:110-117` (`_critical`), `:165` | posé, resserre ; retiré, relâche |
| Le push vers Imladris | `infra/glorfindel-host/host_config.py:25-29`, `:48` (`ASSET_KEYS`), `:86-93`, `:97-101`, `:124-152` | sa propre lecture : jamais perdu par un push, retiré sur Imladris seulement |
| Le test des deux lecteurs | `tests/unit/test_glorfindel_host.py:190-198` | `ASSET_KEYS == _AUTONOMY_ASSET_KEYS` |
| Les seaux persistés | `~/.glorfindel/model_budget.json` (`docs/fichiers-cles.md:788-790`) | `real/critical`, `real/noncritical` : les renommer casserait le compte du jour |
| Les mutants de PRT2 | `scripts/mutants/PRT2.py` | M7413, M7414, M7427, M7428, M7431, M7473, M7481 |
| Les tests | `test_config.py:382`, `test_config_edit.py:278`, `test_model_budget.py:218-290`, `test_glorfindel_host.py:163` | la lecture, la classe, la réserve, le push |
| La doc | `configuration-console.md:545-546`, `operations.md:3590-3605`, `raisonnement.md:474-488`, `enquete-raisonnee.md:1597-1600`, `fichiers-cles.md:788` | la clé et la réserve |

- **Rien d'autre** : ni la préparation, ni les gardes de `decide`, ni la console, ni le bot, ni le
  dossier, ni l'enquête ne lisent `critical`. Pas de commande `glorfindel config check` : les notes de la
  config passent par le démarrage de la watch et par `/api/config`.
- **La console ne le montre pas** (CRT1, #1215). Mais elle le garde : le sélecteur de mode
  (`set_asset_mode`) réécrit une entrée sans perdre sa clé (`test_config_edit.py:278`).

### 1.3 Ce qui attend la criticité d'un objet

- **PRT3**, la porte qui trie (`enquete-raisonnee.md:1610-1612`, et sa ligne au plan) : « la criticité de
  l'objet dans la classe, le déjà traité, des exceptions proposées », en 0.7 ou après.
- **Le dossier d'une isolation** (`dossier-isolation.md:992-993`) : « Un objet critique, en attendant la
  criticité d'un objet (PRT3) : une détection de la classe critique ou d'une technique grave ». Le code :
  `_critical(signal)` (`glorfindel/dossier.py:232-239`) lit la gravité de la détection, pas l'objet. Un
  dossier `critique` passe avant les autres et n'est jamais dit « non composé »
  (`glorfindel/dossier_pass.py:19-22`, `:161-175`).
- **Le raisonnement** (`docs/raisonnement.md:488`) : « la criticité de l'objet dans le tri de la porte
  revient à PRT3 ».
- **La leçon du projet** : « la sûreté ne se délègue jamais à la confiance du modèle (réversibilité de
  l'action × criticité de l'asset × mode `human_only` par défaut × alerting) ». La criticité y est un
  facteur ; elle n'y est jamais une estimation du modèle.

### 1.4 Quatre constats

**Constat 1 — poser `critical` oblige à écrire un mode, et peut se classer « relâche ».** Une entrée
d'`autonomy.assets` exige `mode` (`config.py:1118-1120`). Pour rendre `vm-db-prod` critique, il faut
donc lui écrire une entrée exacte, avec un mode :
- sous un défaut `non_disruptive`, l'entrée `{match: vm-db-prod, mode: non_disruptive, critical: true}`
  est une entrée exacte plus hardie que `human_only` : CFG4 la classe **relâche, latente** (elle fait écran
  au défaut, `config_class.py:12-15`). Avec le `critical` qui resserre, le changement est mêlé, donc
  **relâche** : il passe par la confirmation, alors qu'il ne fait que resserrer ;
- avec `mode: human_only`, la VM change de mode en même temps : un effet de bord que personne n'a demandé.

La classe et le mode sont deux décisions ; la forme d'aujourd'hui les lie. Le format retenu (§5.1) le
règle : sur une entrée d'`assets.list`, le mode est facultatif.

**Constat 2 — le mot `critical` est déjà pris.** C'est une gravité de détection (`critical`, `high`,
`medium`, `low`, `signal_origin.form_refusal`) et une classe de la file (`CRITICAL`, `GRAVE`, `LOW`,
`glorfindel/decision_queue.py:117`), « le mot du RulePoller seul » (SEC-E). Sur une tuile, « CRITICAL » se
lit comme une alerte (Jonathan, 26/11). Une carte `critical` sur une VM `critical` mêle l'événement et
l'objet.

**Constat 3 — le push copie tel quel ce qui n'est pas l'autonomie.** `host_config()` part de la config
du poste (`out = dict(cfg)`, `host_config.py:116`) et ne réécrit que la section `autonomy`. Une section
nouvelle serait donc **écrasée** sur Imladris par celle du poste : un niveau posé sur Imladris, absent du
poste, serait perdu au push. La section `assets:` doit être lue par le push, pas copiée (§5.5).

**Constat 4 — une section que CFG4 ne classe pas est neutre.** `_others` ne parcourt que `_UNCLASSIFIED`
(`config_class.py:44-45`, `:145-150`) ; une section absente de la liste ne donne aucune raison, et
`classify` la rend **neutre** (`:153-173`). Le même piège que MSUB1 a relevé pour `subscriptions:`
(`watch-multi-abonnement.md`, §1.6) : une section `assets:` ajoutée à la lecture stricte sans être
classée ferait passer un `quiet`, et même un mode plus hardi, sans confirmation (§6).

---

## 2. Le principe et les trois axes

### 2.1 Une déclaration de l'opérateur

- **La classe est déclarée**, dans `glorfindel-config.yaml`, comme le mode. Elle n'est jamais estimée par
  le modèle, jamais tirée d'un historique, jamais devinée d'un nom (`*-prod`).
- **Elle est déterministe** : pour une VM et un fichier, un seul niveau, calculé par une seule fonction,
  la même pour la watch, la console et le push.
- **Proposé : le fichier seul** (Q8). Un tag Azure (`eregion-priority`) irait bien au Terraform du client
  (`module-isolation-iac.md`), mais il s'écrit hors de la file de CFG1, par qui écrit la ressource : un tag
  baissé relâcherait sans confirmation. Si un jour il vient, il ne pourra que monter.
- **Le modèle ne la voit pas.** Elle n'entre ni dans `_build_user_message()`, ni dans `_SYSTEM_PROMPT`, ni
  dans les exemples : aucun lot de la note n'appelle le run de bout en bout (`CLAUDE.md`, « Conventions »).
  Un modèle qui la lirait pourrait en faire un raccourci (« VM essentielle, donc j'isole »).

### 2.2 L'attention, jamais les gardes

La classe règle ce que Glorfindel **dépense et dit** pour une VM ; elle ne règle jamais ce qu'il **ose**.

| La classe règle (l'attention) | La classe ne touche jamais (les gardes) |
|---|---|
| la part du budget du modèle (PRT2) | le mode d'autonomie, la décision (`resolve`) |
| le rang dans la porte, à gravité égale (PRT1, PRT3) | la gravité d'une détection (`gravity`, `GRAVE_TTPS`) |
| l'attente pendant le refroidissement du fournisseur | le seuil de confiance, la porte destructive, `allow_destructive` |
| l'ordre et la tenue du dossier (DOS4) | les tirages qui s'accordent (D-1), les planchers (B3a, SEC4a) |
| la profondeur de l'enquête, à délai égal (ENQ) | le plafond de la règle (RDW1), la garde d'attribution (ATT1) |
| le ping de Discord | `never_block`, le réseau du client (SEC2) |
| l'affichage et l'ordre de la console | la préparation (L6) — sauf la réserve qu'elle peut ajouter (§4.5) |

**Une seule exception, dans le sens qui retient** : la réserve de préparation de `essential` (§4.5, Q4),
qui ne peut que tenir une VM en `human_only` jusqu'à une confirmation. Elle ne fait jamais agir.

**Plus vite, sans relâcher.** Une VM essentielle peut être contenue plus tôt : elle n'attend jamais
l'argent ni le refroidissement du fournisseur, et sa décision passera d'abord dans la porte, une fois
l'ordre entre les VM ajouté (PRI4). Elle ne l'est jamais par une garde plus basse : ni un seuil de
confiance réduit, ni des tirages en moins, ni un plafond de règle levé. Ce serait un relâchement que la
classe ne fait pas (Q3).

### 2.3 Trois axes qui se croisent : la zone, le mode, la classe

```
                 ┌───────────────────────────────────────────────────────────┐
  la zone        │ bench · twin · production      lue sur les tags (O0)      │  ce qu'une expérience
  (injecteurs)   │                                 de la VM et de son groupe │  a le droit d'y faire
                 └───────────────────────────────────────────────────────────┘
                 ┌───────────────────────────────────────────────────────────┐
  le mode        │ human_only · non_disruptive    assets (mode), le fichier  │  ce que Glorfindel
  (la décision)  │                                 + la préparation (L6)     │  fait seul
                 └───────────────────────────────────────────────────────────┘
                 ┌───────────────────────────────────────────────────────────┐
  la classe      │ essential · standard · quiet   assets.list (priority)     │  combien la VM compte :
  (l'attention)  │                                                           │  budget, rang, bruit
                 └───────────────────────────────────────────────────────────┘
```

- **Aucun axe ne se déduit d'un autre.** Une VM `production` n'est pas `essential` d'office (une VM de
  développement peut vivre dans le réseau de production) ; une VM `essential` n'est pas en `human_only`
  d'office (le mode reste à décider) ; une VM `quiet` peut être en `non_disruptive`.
- **La zone ne lit pas la classe.** Les injecteurs (Annatar, Gothmog) n'importent rien de la config de
  Glorfindel (D1) ; la règle de production reste la leur, cible par cible. Une VM `essential` en zone
  `production` reçoit ce que la zone permet (une technique non destructive), ni plus ni moins.
- **La classe ne lit pas la zone, sauf là où l'enveloppe la lit déjà** : le budget sépare le réel des
  exercices par la source et la zone (`model_budget.py:359-374`). Comme `critical` aujourd'hui, la part
  réservée de `essential` et le budget réduit de `quiet` ne jouent que dans le réel. Le rang dans la porte
  et l'affichage jouent partout, pour que le banc les mesure (§8.3).
- **Le mode d'une VM `essential`** : sa préparation porte une réserve de plus (§4.5). C'est le seul
  croisement entre la classe et le mode, et il ne retient que.

---

## 3. Les niveaux proposés

| Niveau | Pour quelles VM | Exemple | Ce qui change |
|---|---|---|---|
| **`essential`** | celles dont la perte arrête le métier, ou dont les données ne se reconstruisent pas | `vm-db-prod`, la base de l'ERP | plus d'attention : la réserve, le rang, le dossier, l'enquête, le ping ; une réserve de préparation |
| **`standard`** | toutes les autres, par défaut | `vm-web-01`, un frontal parmi trois | rien : le comportement d'aujourd'hui |
| **`quiet`** | celles qu'on veut surveiller sans bruit, plutôt que les exclure | `vm-dev-01`, recréée chaque nuit | moins de bruit et un rang plus bas pour ses détections basses, un quart du budget de ses ordinaires ; ses graves inchangées : budget, rang et ping de `standard` |

- **Trois niveaux, pas plus** (Q1). Chacun a un effet propre, et l'ordre se lit sans légende. Un quatrième
  (`important`, entre `essential` et `standard`) n'aurait que des demi-effets (une demi-réserve, un ping de
  plus) : à ajouter le jour où un besoin le demande, sans casser le format.
- **`quiet` est l'alternative douce à l'exclusion.** Aujourd'hui, une VM bruyante n'a qu'une issue :
  `exceptions`, qui la retire de la surveillance des règles (CFG2). `quiet` la garde surveillée, toutes ses
  règles comprises, et ne baisse que le bruit et la dépense de ses détections ordinaires. Une grave sur une
  VM `quiet` (un rançongiciel, une exfiltration) est traitée comme partout.
- **Les mots** (Q2) : `essential` et `quiet` disent un objet, pas un événement ; aucun n'est un mot de
  gravité (`critical`, `high`, `medium`, `low`), ni de la file (`grave`), ni de CFG4 (`relax`, `tighten`),
  ni de la vue « Relaxed ». Écartés : `critical` (§1.4, constat 2) ; `high`/`normal`/`low` (la gravité des
  cartes) ; `tier-1/2/3` (le « tier 0 » d'Active Directory, et un ordre qui se lit dans les deux sens) ;
  `disposable` (laisserait croire qu'une action destructive y est permise).
- **Le défaut est `standard`**, et il n'est pas réglable (§5.2) : un défaut `essential` diluerait la
  réserve sur tout le parc, un défaut `quiet` relâcherait tout d'un coup.

---

## 4. Les effets, axe par axe

### 4.1 (a) La réserve du modèle

- **`essential`** : l'effet de `critical: true` aujourd'hui, sans un chiffre changé. Chaque entrée ajoute
  0,50 $ à la réserve des graves, jusqu'à 2,50 $ ; la part au-dessus du plancher ne sert qu'à ses graves ;
  une grave n'attend jamais l'argent, seul le disjoncteur général l'envoie au chemin du code
  (`model_budget.py:20-29`). Le compte reste par entrée, pas par VM (§1.1).
- **`standard`** : le plancher de 1 $ que partagent toutes les graves ; ses ordinaires au plus 1 $ par VM
  et par jour (`VM_USD`, `model_budget.py:88`).
- **`quiet`**, proposé : ses graves gardent le plancher, comme toutes ; **ses ordinaires au plus un quart
  de `VM_USD`** (0,25 $ par jour, environ cinq décisions avec enquête à 0,051 $). Au-delà, une ordinaire est
  une carte, comme aujourd'hui pour une VM qui a épuisé son dollar. Le chiffre se tire de `VM_USD`, jamais
  recopié ; il se recale à la mesure (§8.3).
- **Ce que monter coûte aux autres.** La réserve se prend sur l'enveloppe du réel : chaque entrée
  `essential` retire jusqu'à 0,50 $ à ce que partagent les ordinaires de toutes les VM (`real/rest`, 4 $ sans
  entrée, 2,50 $ avec trois). Un motif `essential` très large (`*`) ne protège donc rien de plus et réduit
  les ordinaires de tout le parc : la note propose de le dire (§6).

### 4.2 (b) La porte des appels

- **Ce que fait le code aujourd'hui.** La file est celle de chaque VM, rangée par gravité puis par arrivée
  (`decision_queue.py:256-280`). **Entre les VM, aucun ordre** : une décision que le plafond par minute
  retient reçoit le délai avant la prochaine place (`room_in`, `decision_queue.py:419-426`) et réessaie
  (`:707-709`) ; la première VM qui réessaie passe. Le rang qui suit **n'existe donc pas** : c'est un ordre
  à ajouter entre les VM, que PRI4 porte (§10).
- **L'ordre proposé** : la gravité d'abord, toujours (`gravity` : la classe critique, puis grave, puis
  basse, `decision_queue.py:129-138`) ; à gravité égale, le niveau ; puis l'arrivée.
  - **pour les graves et les critiques** : `essential`, puis `standard` et `quiet` **ensemble**. Une grave
    sur une VM `quiet` se range comme sur une VM `standard` : `quiet` ne baisse jamais une grave ;
  - **pour les basses** : `essential`, puis `standard`, puis `quiet` ;
  - la classe ne fait jamais passer une détection basse d'une VM `essential` devant une grave d'une VM
    `standard` : un rançongiciel sur `vm-dev-01` passe avant une force brute sur `vm-db-prod`.
- **La forme, à fixer par PRI4** : un registre des décisions qui attendent une place, rangé par cet
  ordre ; quand une place revient, la première du registre la prend, et les autres réessaient après elle.
  Sans ce registre, le niveau ne change rien au rang, et la note ne le promet pas.
- **L'admission** : la place des graves (quatre appels par minute) ne change pas ; aucune place n'est
  réservée à `essential` (une place réservée serait prise aux autres graves).
- **L'attente** : pendant le refroidissement du fournisseur, une grave `essential` part tout de suite par
  le chemin du code (`_slowed`, l'existant) ; une grave `standard` ou `quiet` attend, jusqu'à la deuxième
  limite (`_strikes >= 2`), comme aujourd'hui.
- **Le dédoublonnage** (une décision par VM, règle, gravité et source en cinq minutes) ne change pas : le
  raccourcir pour `essential` multiplierait les appels sans preuve de plus.
- **`quiet`** : ses détections basses passent les dernières de leur classe, une fois l'ordre de PRI4 en
  place ; au-delà de la place des basses, une basse devient une carte, comme aujourd'hui pour toute VM.
  Ses graves et ses critiques ne sont jamais rangées après celles de `standard`.
- **PRT3**, en 0.7 : la classe y entre comme une donnée du tri. Les contraintes que la note pose :
  - une exception proposée par la porte ne couvre jamais une VM `essential` à son niveau le plus large ;
  - `quiet` ne rend aucune exception automatique : une exception reste proposée, datée, et cassée par un
    saut de volume ou une technique grave, à tous les niveaux ;
  - jamais le silence : une détection écartée par la porte reste dite, à tous les niveaux.

### 4.3 (c) La profondeur de l'enquête, et le dossier

- **L'enquête** (ENQ5, derrière `GLORFINDEL_ENQUIRY`, `fixed` par défaut) : au plus N = 4 lectures choisies
  par le modèle, en T = 30 s pour toute l'enquête (`glorfindel/enquiry/loop.py:63`,
  `enquete-raisonnee.md` §5.1). Proposé, **en 0.7, après la mesure d'ENQ5** :
  - `essential` : N = 6, **T inchangé**. L'enquête peut lire plus, jamais plus longtemps : le temps pour
    contenir ne s'allonge pas. Deux lectures de plus, ce sont deux appels de plus dans la part de la
    décision (`DecisionGate.share`) et dans la réserve de la porte : au-delà de la place des graves, ils se
    comptent après, comme aujourd'hui les tirages (`decision_queue.py:40-42`) ;
  - `standard` et `quiet` : N = 4. Voir moins sur une VM `quiet` n'économiserait presque rien (ses
    décisions sont rares) et relâcherait ce qu'elle voit ;
  - les lectures obligatoires des techniques graves, et l'aiguillage de l'enquête de base, partout et
    toujours, hors de N (`enquete-raisonnee.md` §5.2).
- **Le dossier** (DOS4, codé), **en 0.6.x** : une VM `essential` a un dossier `critique`, quelle que soit la
  gravité de la détection. Il passe avant les autres dans le budget d'ARM du dossier et n'est jamais dit
  « non composé » : il attend que le budget le laisse lire (`dossier_pass.py:161-175`). `_critical(signal)`
  (`dossier.py:232`) lit alors la gravité **ou** le niveau ; c'est ce que `dossier-isolation.md:992`
  attend.

### 4.4 (d) Les cartes, les notifications, Discord

- **La gravité d'une carte ne change jamais avec la classe.** Elle dit l'événement (la règle, la
  technique) ; la classe dit l'objet. Monter la gravité d'une carte sur une VM `essential` ferait entrer
  ses détections dans la classe critique de la file, prendrait la place des vraies compromissions (SEC-E)
  et viderait le mot de son sens (Q9).
- **La carte porte le niveau de sa VM**, à part (un champ `priority`), pour la console et le bot.
- **Ce que fait le bot aujourd'hui** : le rôle `DISCORD_PING_ROLE` n'est pingué qu'à la création d'un fil
  (« Incident opened », `glorfindel/bot.py:1589-1596`) et sur la carte d'une action prise seule
  (`bot.py:1673-1678`, JUG1). **Une carte postée dans un fil déjà ouvert ne pingue pas, même grave** : une
  force brute qui ouvre le fil de `vm-web-01` pingue, un rançongiciel qui suit dans le même fil, non. C'est
  un trou d'aujourd'hui, à tous les niveaux.
- **Discord**, tranché par la note (Q9 le soumet à Jonathan) :
  - **à tous les niveaux, la première carte grave ou critique d'un fil pingue**, même si le fil est déjà
    ouvert, une fois par fil (la clé du fil, comme `_posted`) : le trou d'aujourd'hui se ferme pour
    `standard` aussi, et `quiet` ne peut pas l'élargir. Raison : une grave est rare, et une seule mention de
    plus par incident ne fait pas de bruit ; sans elle, un fil ouvert par une basse tait la suite ;
  - **une action prise seule pingue toujours**, à tous les niveaux : « une action autonome alerte toujours
    quelque part » (JUG1) ne descend jamais ;
  - `essential` : en plus, un ping pour **chaque carte qui attend un humain** dans un fil déjà ouvert
    (`mode_hold`, `low_confidence`, `telemetry_gap`, `unstable_decision`, `readiness_hold`…), une fois par
    carte ;
  - `standard` : rien d'autre ne change ;
  - `quiet` : **pas de ping à l'ouverture d'un fil pour une détection basse** ; le fil s'ouvre, la carte y
    est, sans mention. Une grave qui suit dans ce fil ouvert en silence pingue (la première règle).
- **Le webhook** ne change pas. **TO JUDGE** non plus : l'ordre reste celui du temps, la carte montre le
  niveau.

### 4.5 (e) Ce que Glorfindel s'autorise seul

Le mode reste la décision (action ≠ décision) ; la classe peut au plus resserrer. Les deux sens, pesés :
- **isoler `vm-db-prod` coupe l'ERP** : une isolation sur un faux positif est la peur du client sans SOC
  (« l'action réversible mais disruptive décidée en autonome », `docs/glorfindel.md`, « Modes d'autonomie
  par asset »). Le banc l'a montré le 20/11 : une sauvegarde lourde a fait proposer `isolate_vm` à 80 %
  (RDW1) ;
- **un rançongiciel sur `vm-db-prod` est pire** : chaque minute chiffre plus. Une VM autonome y a
  l'instantané et l'isolement seuls, si son mode et sa préparation le permettent ; en `human_only`, elle
  n'a rien de seul : l'instantané lui-même est proposé sur la carte.

Trois réponses possibles (Q4) :
1. **Proposé : une réserve de préparation.** Passer une VM en `essential` ajoute à sa préparation (L6,
   `glorfindel/readiness.py`) une réserve `essential_service` : « VM declared essential: its actions
   alone, the isolation that cuts its service included, wait until a human has wanted them ». Comme toute
   réserve, elle se confirme une fois (`acknowledged`) ; d'ici là, la VM reste en `human_only` quoi que dise
   son mode (`readiness.py:15-26`), et une carte `readiness_hold` le dit (« ⚡ Review & turn on »). Une VM
   déjà autonome qui devient `essential` y retourne, comme pour toute réserve apparue après l'activation.
   Confirmée, son mode décide, isolement compris. **Une seule décision (le mode), prise en sachant, et
   datée.**
   **Le coût, dans cette fenêtre** : `human_only` retient **toute** action seule, pas seulement
   l'isolement — ni l'instantané, ni le blocage d'une adresse, ni le chemin du code ne partent seuls.
   Jusqu'à la confirmation, un rançongiciel sur `vm-db-prod` n'a **aucune action seule** : une carte, un
   ping, et l'attente d'un humain. Pour raccourcir la fenêtre, la console propose la confirmation dans le
   même geste que le passage en `essential` (CFG5) ; d'ici là, `glorfindel activate <vm>` ou l'écran de
   préparation. Une VM en `human_only` n'en perd rien : elle n'avait déjà rien de seul.
2. **Un plafond de l'objet**, sur le modèle du plafond de la règle (RDW1, `_apply_rule_ceiling`,
   `glorfindel/agent.py:1585`) : sur une VM `essential`, une isolation autonome est ramenée à l'instantané,
   et la carte propose l'isolement, approuvable en un clic ; le blocage d'une adresse et l'instantané
   restent au mode. Le plus prudent, mais deux endroits pour une décision : une tuile `non_disruptive` qui
   n'isole jamais seule, et un rançongiciel qui attend un humain.
3. **Rien** : la classe ne touche jamais l'autonomie. Le plus simple ; la leçon (« la criticité de
   l'asset ») tient alors par l'opérateur seul, qui pense à mettre `human_only`.

Écarté par le principe : **« contenir plus vite » par une garde** (un seuil plus bas, un tirage en moins
sur une VM `essential`). Ce serait un relâchement porté par la classe.

`quiet` ne touche pas l'autonomie : une VM `quiet` n'agit ni plus ni moins seule. Le passage en masse en
`human_only` (le geste d'urgence) ne lit pas la classe.

### 4.6 (f) La console

- **La carte de l'infra** : la marque du niveau sur la tuile (§7.1) ; dans un groupe (GRP1), les tuiles
  `essential` d'abord, puis par nom ; `quiet` à sa place, plus discrète.
- **La page Config** : une section « Priorities » (§7.2).
- **TO JUDGE** et le fil : l'ordre ne change pas ; la carte montre le niveau.
- **L'écran de préparation** (L6) : la réserve `essential_service` avec les autres, si Q4 retient l'option 1.
- **Dagorlad** : la marque sur une cible inscrite, pour information ; elle ne change rien au jugement d'un
  fil (la zone décide).
- **Rien ne s'écrit depuis la console avant CFG5** : la classe se pose à la main dans le fichier, puis par
  la file signée.

### 4.7 (g) Ce qui n'est pas touché

- **Les zones** (`bench`, `twin`, `production`) : un autre axe (§2.3). La règle de production
  (« jamais de panne ni d'action destructive sur une charge réelle ») ne lit pas la classe ; une VM
  `quiet` n'est pas une charge de banc.
- **Les injecteurs** : ils ne lisent pas la classe (D1). Annatar ne choisit pas ses cibles par elle.
- **Ce que voit le modèle** (§2.1).
- **Les gardes de `decide`** (§2.2), `allow_destructive`, `delete`/`wipe` jamais autonomes.
- **Les exclusions** (`exceptions`) : une VM exclue d'une règle l'est à tous les niveaux ; `quiet` n'exclut
  rien.
- **Plusieurs abonnements** (MSUB3) : une entrée d'`assets.list` sans clé `subscription` ne vaut que pour
  l'abonnement de la watch, comme une entrée d'autonomie (« rien n'est hérité »,
  `watch-multi-abonnement.md` §4.3) ; MSUB3 indexe la classe par (abonnement, motif), comme le mode.

### 4.8 Le tableau, niveau × axe

| Axe | `essential` | `standard` (défaut) | `quiet` | Quand |
|---|---|---|---|---|
| **(a) la réserve du modèle** | +0,50 $ par entrée, jusqu'à 2,50 $ ; la part au-dessus du plancher pour ses graves seules ; une grave n'attend jamais l'argent | le plancher de 1 $ ; ses ordinaires au plus 1 $ par jour | ses graves : le plancher ; ses ordinaires au plus 0,25 $ par jour | `essential` : l'existant ; `quiet` : 0.6.x |
| **(b) la porte : l'attente** | sa grave n'attend pas le refroidissement du fournisseur | l'existant | l'existant | `essential` : l'existant |
| **(b) la porte : le rang**, un ordre entre les VM que la porte n'a pas aujourd'hui (PRI4) | d'abord, à gravité égale | ses graves avec celles de `quiet` ; ses basses avant celles de `quiet` | ses graves avec celles de `standard` ; ses basses les dernières | 0.6.x, avec PRI4 ; PRT3 en 0.7 |
| **(c) l'enquête** | N = 6, T = 30 s inchangé | N = 4, T = 30 s | N = 4, T = 30 s | 0.7, après ENQ5 |
| **(c) le dossier** | toujours `critique` : d'abord, jamais « non composé » | selon la gravité (l'existant) | selon la gravité | 0.6.x |
| **(d) la carte** | gravité inchangée ; le niveau dit | inchangée | inchangée | 0.6.x |
| **(d) Discord** | la première grave d'un fil et les actions seules pinguent ; et chaque carte qui attend un humain | la première grave d'un fil pingue, même fil ouvert (nouveau) ; les actions seules pinguent | pas de ping à l'ouverture pour une basse ; la première grave d'un fil et les actions seules pinguent | 0.6.x |
| **(e) l'autonomie** | une réserve de préparation à confirmer (Q4) : jusque-là, aucune action seule ; ensuite, le mode décide | le mode décide | le mode décide | 0.6.x |
| **(f) la console** | `ESSENTIAL`, neutre ; en tête du groupe | rien | `quiet`, en gris | 0.6.x (CRT1) |
| **(g) la zone, les injecteurs, le modèle** | rien | rien | rien | — |
| **Les gardes de `decide`** | rien | rien | rien | — |

---

## 5. Le format dans la configuration

### 5.1 La question, et la décision de Jonathan

Trois formes ont été pesées (Q5, §9) :
- **A — une clé `priority:` sur les entrées d'`autonomy.assets`**, à la place de `critical`. Le chemin le
  plus court, mais le constat 1 reste (un mode imposé à chaque VM classée), avec une clé de plus dans
  `ASSET_KEYS` (§5.5).
- **B — une section à part, `priorities:`** (`match`, `level`, `reason`), la recommandation de la note :
  la classe sans mode, mais deux listes qui nomment les mêmes VM.
- **C — la proposition de Jonathan : une seule section `assets:`**, qui remplace `autonomy:` (et B). Une
  entrée par VM ou par motif porte son mode **et** sa priorité, chacun facultatif.

**Le format retenu par Jonathan, le 26/11, est C.** La suite du §5 le décrit ; la question reste au §9
telle qu'elle a été posée, et sa réponse ira avec les autres.
- **Ce qu'il règle** : le constat 1 (§1.4). Le mode devient facultatif sur une entrée : on classe une VM
  sans lui écrire de mode, donc sans « relâche » à confirmer. Une VM se lit à un seul endroit.
- **Ce qu'il garde** : deux axes, deux champs. Le mode reste la décision, la priorité l'attention ; une
  entrée peut porter l'un, l'autre, ou les deux, et chacun se résout par sa règle (§5.3).
- **Ce qui reste à part** : la découverte, sur sa source (`monitoring_backends[].discovery`) ; les
  exclusions (`exceptions`), pour l'instant (elles pourront rejoindre l'entrée plus tard).
- **Ce qu'il coûte** : une section de premier niveau qui en remplace une autre. Les deux lecteurs, les
  écrivains du fichier (la console, la CLI), CFG4, la vue « Relaxed » et la doc la lisent ; l'ancien
  format reste lu jusqu'à la 1.0 (§5.4). PRI2 grossit d'environ un jour (§10).

### 5.2 La section `assets:`, lue strictement (A3)

```yaml
assets:
  default_mode: human_only        # l'ancien autonomy.default ; human_only si absent
  allow_destructive: []           # l'ancien autonomy.allow_destructive
  list:                           # l'ancien autonomy.assets
    - match: vm-db-prod
      mode: non_disruptive        # facultatif : sans lui, la règle du mode (§5.3), puis default_mode
      priority: essential         # facultatif : sans lui, standard
      reason: the ERP database    # facultative, comme une exclusion (CFG2)
    - match: vm-dev-*
      priority: quiet             # classée sans mode
```

- **`default_mode`** : les valeurs de `autonomy.default` (`human_only`, `non_disruptive` ; `full_auto`
  différé, refusé). **Pas de défaut de priorité** : il est `standard`, fixe (§3).
- **`allow_destructive`** : l'axe à part d'aujourd'hui, qu'aucun mode ne lit ; inchangé.
- **`list`** : chaque entrée a un `match` (un texte non vide, nom ou motif, sans la casse) et **au moins
  un** de `mode` et `priority` ; `reason` est facultative. Une entrée qui ne dit ni l'un ni l'autre est
  refusée (« an entry that says nothing »), toute autre clé aussi. `subscription` viendra avec MSUB3
  (§4.7).
- **Le même `match` deux fois** (sans la casse) : refusé, et dit (« one entry per name or pattern »).
  Aujourd'hui, `autonomy.assets` l'accepte, et deux entrées à égalité donnent le mode le plus prudent
  (AUC) : l'ancien format garde cette règle ; la migration fusionne les doublons (§5.4).
- **`priority: standard`** est accepté : il ne fait rien à lui seul, mais documente une VM qu'on a
  regardée ; le démarrage le dit (« standard: no effect »).
- **Une valeur inconnue** (`priority: critical`, `mode: full_auto`, une faute) : refusée, comme tout écart
  d'A3 ; la watch démarre alors comme pour toute config illisible, toutes les VM en `human_only` jusqu'à
  correction (`glorfindel/watch/startup.py:103-111`). C'est le côté sûr, et il est bruyant.
- **En mémoire, un seul modèle.** Les deux formats se lisent dans la même structure (`AutonomyConfig`,
  dont les règles gagnent `priority` et `reason`, et dont le `mode` devient facultatif). Les six endroits
  qui résolvent le mode par le nom (`watch-multi-abonnement.md` §1.6) appellent `resolve` comme
  aujourd'hui ; `level_of(name)` s'y ajoute, pour la watch, la console, CFG4 et la vue « Relaxed ».
  `is_critical` devient `level_of(name) == essential`, et `critical_count` le compte des entrées
  `essential`.

### 5.3 Plusieurs entrées sur une VM, champ par champ

Chaque champ se résout sur les **seules entrées qui le portent** (Q6).

- **Le mode : la règle d'aujourd'hui**, telle que `AutonomyConfig.resolve` la code
  (`glorfindel/config.py:390-412`) :
  1. le nom de la VM en minuscules ; les entrées **exactes** (leur `match` en minuscules égal au nom) :
     s'il y en a, la plus prudente d'entre elles (`_most_prudent`, `config.py:353-354`) ;
  2. sinon, les entrées dont le motif couvre le nom (`fnmatchcase` sur les deux en minuscules, AUC) : le
     motif **le plus long** (en caractères) ; à égalité, la plus prudente ;
  3. sinon, `default_mode`.

  **Une entrée sans mode n'y prend jamais part** : une entrée exacte `vm-db-prod` qui ne porte que
  `priority: essential` ne fait pas écran à un motif `vm-*: non_disruptive`. Sans cette règle, classer
  une VM changerait son mode : le défaut que C vient fermer.
- **La priorité : proposé, le niveau le plus haut** parmi toutes les entrées qui portent une priorité,
  exactes ou par motif. C'est la règle de `is_critical` aujourd'hui (§1.1), et la seule où une erreur ne
  baisse jamais un niveau. L'autre option : la règle du mode (l'exacte, puis le plus long ; à égalité, le
  plus haut), qui permet l'exemption.
- **Un exemple**, où une entrée ne porte que la priorité et une autre que le mode :
  ```yaml
  assets:
    default_mode: human_only
    list:
      - match: vm-erp-*
        priority: essential
      - match: vm-erp-test
        mode: non_disruptive
      - match: vm-erp-qa
        priority: quiet
  ```
  - `vm-erp-test` : son mode est `non_disruptive` (l'entrée exacte, la seule qui porte un mode) ; sa
    priorité est `essential` (le motif, la seule qui en porte une), sous les deux règles ;
  - `vm-erp-prod-01` : `human_only` (aucune entrée ne lui donne de mode : `default_mode`) et `essential` ;
  - `vm-erp-qa` : `human_only` ; `essential` sous la règle proposée (le plus haut des deux), `quiet` sous
    la règle du mode (l'exacte l'emporte). Une entrée exacte `quiet` posée sous un motif `essential`
    baisserait en silence une VM que l'opérateur croit essentielle : CFG4 la classerait « relâche », la
    note préfère qu'elle ne puisse pas avoir d'effet.

### 5.4 L'ancien format : `autonomy:` et `critical: true`

Proposé (Q7), dans la release qui lit `assets:` (PRI2) :
- **`autonomy:` entier reste lu jusqu'à la 1.0**, dans le même modèle : `autonomy.default` comme
  `default_mode`, `autonomy.allow_destructive` comme `allow_destructive`, chaque entrée
  d'`autonomy.assets` comme une entrée de `list` qui porte son mode ; **`critical: true` comme
  `priority: essential`** ; `critical: false` ne dit rien (c'est le défaut du champ). Rien ne change pour
  une VM : son mode, sa réserve, son attente, sa classe.
- **Une note le dit**, au démarrage de la watch et dans `/api/config` (pas de `glorfindel config check`
  aujourd'hui) : « `autonomy:` is the former format of `assets:` — migrate it (`glorfindel config
  migrate`) » ; et pour chaque `critical: true`, « the former name of `priority: essential` ». Jamais une
  erreur.
- **Les deux formats dans un même fichier** (`autonomy:` et `assets:`) : **une erreur de config**, que
  leurs valeurs s'accordent ou se contredisent. Deux sections qui disent le mode d'une même VM font deux
  vérités ; la lecture refuse, et dit laquelle retirer.
- **La migration** : une commande, `glorfindel config migrate` (PRI2), écrit le nouveau format depuis
  l'ancien, à valeurs égales, et montre le changement avant de l'écrire. Les doublons d'`autonomy.assets`
  y sont fusionnés en une entrée : le mode que l'ancien format leur donnait (le plus prudent, AUC), la
  priorité la plus haute ; la commande le dit. CFG4 classe la migration **neutre** (§6).
- **Les écrivains gardent le format du fichier** : le sélecteur de mode de la console (`set_asset_mode`),
  le défaut, la CLI écrivent dans `autonomy.assets` un fichier à l'ancien format, dans `assets.list` un
  fichier au nouveau. Aucun ne migre en silence : la migration est un geste (la commande, la main, ou
  CFG5 plus tard).
- **Jusqu'à quand** : jusqu'à la 1.0, avec la note ; un lot de la 1.0 le retire (PRI7, §10).
- **Les noms internes** : `is_critical`, `critical_count`, `critical_part`, `CRITICAL_USD` se renomment
  (`is_essential`…) quand c'est raisonnable, et les mutants de PRT2 se ré-ancrent sans s'affaiblir. **Les
  seaux persistés** `real/critical` et `real/noncritical` (`~/.glorfindel/model_budget.json`) **gardent
  leur nom** : les renommer remettrait le compte du jour à zéro au redéploiement, ou demanderait une
  migration du fichier pour un mot.

### 5.5 Les deux lecteurs : la watch et le push

**La watch** (`glorfindel/config.py`) : `_SECTIONS` gagne `assets` ; `_check_assets` lit le §5.2, et
`_check_autonomy` reste pour l'ancien format ; les deux dans le même modèle ; les deux ensemble, refusés.

**Le push vers Imladris** (`infra/glorfindel-host/host_config.py`), qui n'importe rien de Glorfindel :
- **sa lecture** de `assets:` est celle de la watch. `ASSET_KEYS` devient `("match", "mode", "priority",
  "reason")`, le mode y devient facultatif, et `KNOWN_PRIORITIES` s'ajoute à `KNOWN_MODES` ; les clés de
  l'ancien format restent lues à part (`match`, `mode`, `critical`). **Le risque de CRT1** (une clé connue
  d'un seul lecteur : la config d'Imladris « forme inconnue », toutes les VM remises en `human_only`) se
  règle en changeant les deux lecteurs **dans le même lot** (PRI2), tenus par le test, et par la garde de
  version ci-dessous pour deux machines qui ne sont pas à la même release ;
- **une config d'Imladris que la watch refuserait** (une section `assets:` hors forme, les deux formats
  ensemble) est **entière inconnue**, tranché par la note : toutes les VM en `human_only` (le rapport du
  push le dit), et aucun niveau d'Imladris gardé ; le push envoie les seuls `essential` du poste. C'est le
  principe de `refusal()` aujourd'hui (`host_config.py:69-94`) : « a config the watch would not run is no
  config whose modes are kept — never one VM dropped and the others kept ». Écarté : ne refuser que la
  partie hors forme et garder le reste, la moitié d'un fichier que la watch d'Imladris ne fait pas
  tourner ;
- **une config du poste que la watch refuserait** : le push s'arrête, sans rien envoyer, et le dit ;
- **ce qu'il écrit** : `default_mode: human_only` et `allow_destructive: []`, comme aujourd'hui ; le mode
  de chaque nom exact gardé d'Imladris (BL1c), un motif jamais gardé ; **jamais un niveau plus bas** :
  - `essential` vient d'Imladris **ou** du poste : il n'est jamais perdu par un push, comme `critical`
    aujourd'hui (`host_config.py:124-152`) ;
  - `quiet` ne vient **que** d'Imladris : un `quiet` du poste n'est pas poussé (il relâcherait sans la
    confirmation que la console d'Imladris demandera), et le rapport le dit (« quiet on this machine
    only: not pushed ») ;
  - une entrée qui ne porte que la priorité est poussée **sans mode** : le push n'écrit jamais un mode
    qu'elle n'a pas ;
- **`quiet` sur Imladris avant CFG5** : le push ne le porte pas, et la console n'écrit rien dans le
  fichier avant la file signée. Il ne se pose donc qu'**à la main, sur l'hôte**, dans
  `eregion/glorfindel-config.yaml`, puis la watch relancée : un geste de Jonathan, comme tout geste sur
  Imladris (`CLAUDE.md`, « Jamais seule »). PRI2 l'écrit dans `docs/operations.md`. Q10 propose de garder
  les effets de `quiet` en 0.6.x malgré ce geste à la main ;
- **le constat 3** : `assets:` n'est jamais copiée du poste, elle est **calculée**, comme l'autonomie
  aujourd'hui ;
- **`HUMAN_ONLY=1`** remet chaque mode à `human_only` et ne touche pas les priorités : elles ne font
  qu'ajouter de l'attention, et le geste d'urgence reste celui des modes.

**La garde de version, et la migration d'Imladris.** `make imladris-push` tourne depuis le checkout du
poste (`Makefile:1250-1262`), pas depuis la release d'Imladris. Le push lit donc **la release
qu'Imladris fait tourner**, par la connexion qu'il ouvre déjà (la source exacte, la référence que tient
le CD ou la version du paquet dans le conteneur, est à choisir par PRI2), et **écrit le format qu'elle
lit** :
- **une release qui lit `assets:`** (PRI2 et après) : le push écrit `assets:`. **Si Imladris est encore
  en `autonomy:`**, il en lit les modes et les `critical: true` comme aujourd'hui, et les écrit au nouveau
  format : **la migration d'Imladris se fait au push**, à valeurs égales, et le rapport le dit
  (« Imladris: autonomy: migrated to assets: »). La watch d'Imladris la lit comme un changement neutre ;
- **une release d'avant PRI2, ou une release qui ne se lit pas** : le push écrit **l'ancien format**, que
  les deux lisent jusqu'à la 1.0, par la conversion du §5.6 ; les `quiet` n'y passent pas, et c'est dit.
  `HUMAN_ONLY=1` n'est jamais bloqué par cette lecture : il écrit l'ancien format si la release ne se lit
  pas ;
- **un poste d'avant PRI2, un Imladris de PRI2** : l'ancien `host_config.py` ne lit que `autonomy`
  (`refusal()`) et copie la config du poste (`out = dict(cfg)`, `host_config.py:116`). Il **efface sans
  rien dire** la section `assets:` d'Imladris : ses modes retombent à `human_only` (le côté sûr), ses
  `essential` sont perdus. Le code d'avant ne peut pas être changé ; la parade est du côté d'Imladris :
  **la watch garde les niveaux qu'elle a lus en dernier** (un fichier de son état), et un `essential` qui
  disparaît sans être passé par la file (CFG5) ou par la CLI est **dit** au démarrage et sur une carte
  (« essential lost outside the queue: vm-db-prod »). Un relâchement fait hors de la file ne passe jamais
  en silence ; la migration, qui garde les niveaux, ne déclenche rien.

**Le test qui les tient égaux** : celui d'aujourd'hui (`test_glorfindel_host.py:190-198`) compare
`ASSET_KEYS`, `KNOWN_MODES`, `KNOWN_PRIORITIES`, leur ordre et les clés de la section à ceux de la
watch, pour les deux formats. Un second test donne les mêmes configs aux deux lecteurs (une priorité
inconnue, un `match` vide, deux fois le même, une entrée sans mode ni priorité, une clé de plus, les deux
formats ensemble) et attend le même verdict : la watch refuse, le push rend la config entière inconnue.

### 5.6 Le retour arrière vers l'ancien format

Une release d'avant PRI2 refuse `assets:` (une section inconnue, `config.py:872`). Le préflight du CD
passe la config d'Imladris à la lecture stricte de l'image candidate (`watch-multi-abonnement.md` §1.8) :
un retour arrière sous PRI2 est donc refusé tant que la section est là, et le CD le dit. Le geste,
écrit dans la doc de PRI2 : **convertir vers l'ancien format, puis revenir en arrière**. La conversion
(`glorfindel config migrate --to autonomy`, et la même fonction dans `host_config.py`, qui sert aussi au
push vers une release d'avant) :
- `default_mode` en `autonomy.default`, `allow_destructive` tel quel, chaque entrée qui porte un mode en
  entrée d'`autonomy.assets` ;
- `essential` en `critical: true`. **L'ancien format exige un mode** sur chaque entrée (le constat 1) :
  une entrée `essential` sans mode reçoit le mode que la VM a déjà par la règle du §5.3, et `human_only`
  quand ce mode ne se lit pas sur un nom seul (un motif, plusieurs VM). Jamais un mode plus hardi que
  celui qu'elle a ; une entrée exacte `human_only` peut faire écran à un motif plus hardi : c'est plus
  prudent, et la conversion le dit ;
- `quiet` n'a pas d'équivalent : retiré, et dit ; `reason` aussi (l'ancien format n'en a pas).

MSUB6 prévoit le préflight par les deux images ; PRI2 s'y range s'il arrive après.

---

## 6. Les classes de CFG1 et CFG5

La classe d'un changement (CFG4, `glorfindel/config_class.py`) se calcule sur **le modèle lu** des deux
textes, jamais sur leur forme : les deux formats se lisent dans le même modèle (§5.2), et CFG4 compare le
mode et le niveau de chaque nom, sans la découverte (`configuration-console.md` §5.3).

| Geste | Classe | Ce qui le suit |
|---|---|---|
| ajouter ou retirer une entrée **sans mode** | pour le mode, **neutre** : elle ne prend jamais part à sa résolution (§5.3) ; sa priorité, selon les lignes ci-dessous | — |
| poser, changer ou retirer le `mode` d'une entrée | **la classe d'aujourd'hui** (`configuration-console.md` §5.2-5.3) : plus hardi relâche (latent sous un motif ou un défaut qui le donne déjà), plus prudent resserre, retiré la classe de ce que la VM retrouve | selon la classe |
| `default_mode` vers `human_only` / vers `non_disruptive` | comme `autonomy.default` : resserre, annoncé fort (Q11) / relâche | idem |
| `allow_destructive` changé | relâche (non classé, comme aujourd'hui) | la confirmation |
| poser `essential` (une entrée, ou `standard` → `essential`) | **resserre** | tout de suite, un reçu, une ligne sur Discord |
| `quiet` → `standard`, ou retirer la priorité `quiet` | **resserre** | idem |
| `essential` → `standard`, ou retirer la priorité `essential` | **relâche** | le nom tapé, la raison, le délai de 10 min (CFG1 Q2) |
| poser `quiet` (`standard` → `quiet`) | **relâche** | idem |
| `essential` → `quiet` | **relâche** | idem |
| changer `reason` seule | neutre | l'historique |
| élargir un motif `essential` (`vm-erp-prod-*` → `vm-erp-*`) | resserre | une ligne |
| élargir un motif `quiet` | **relâche** | la confirmation |
| **passer de l'ancien format au nouveau** (`autonomy:` → `assets:`, `critical: true` → `priority: essential`), à valeurs égales | **neutre** : le mode et le niveau de chaque nom sont les mêmes avant et après | l'historique |
| une migration qui fusionne des doublons | ce qu'elle change : rien, puisque le mode gardé est celui que l'ancien format donnait (AUC) | idem |

- **Monter resserre-t-il toujours ?** Pour la VM, oui : plus de réserve, un rang plus haut, plus de bruit,
  et, si Q4 retient l'option 1, une réserve de préparation qui ne peut que la retenir. Pour les autres, un
  `essential` de plus retire jusqu'à 0,50 $ aux ordinaires de tout le parc (§4.1). La note garde
  « resserre » (c'est déjà le choix de CFG4 pour `critical`), et propose d'annoncer fort un changement qui
  fait passer **5 VM ou plus** en `essential` d'un coup, comme un passage en masse en `human_only`
  (`configuration-console.md` §5.4, le même compte en VM).
- **Descendre relâche-t-il toujours ?** Oui : moins de budget, moins de bruit, un rang plus bas, et la
  réserve de préparation levée. Il se confirme.
- **La garde de CFG4** (constat 4) : un test échoue sur toute section de premier niveau acceptée par la
  lecture stricte qui n'est ni classée ni dans `_UNCLASSIFIED` ; `assets` est classée (son mode par
  `_autonomy`, sur le modèle ; sa priorité par une fonction à elle ; `allow_destructive` comme
  aujourd'hui), et son mutant le prouve.
- **La classe du niveau se calcule sur `level_of`** (§5.3), jamais entrée par entrée. **PRI2 remplace
  `_critical`** (`config_class.py:110-117`) : il compare les entrées qui disent `critical: true`, et
  classerait la migration « relâche » (l'entrée critique disparaît, `:116-117`), alors qu'aucune VM ne
  change de niveau. À sa place, une classe calculée par nom : pour chaque nom ou motif cité dans l'un des
  deux fichiers, le niveau que `level_of` lui rend avant et après. **La migration neutre a son test**, sur
  un fichier qui mêle modes, motifs, doublons et `critical: true`, et son mutant (l'ancienne `_critical`
  gardée à côté). Un motif `quiet` ajouté sous un motif `essential` qui le couvre ne baisse rien, il est
  neutre ; il relâche dès qu'il nomme ce que rien de plus haut ne tient.
- **La vue « Relaxed »** (CFG3, `glorfindel/relaxed.py`) : chaque entrée `quiet` présente y a sa ligne —
  l'objet, « quiet: fewer pings for its low detections, 0.25 $ a day for its ordinaries », sa raison, ce
  qu'elle désigne aujourd'hui. Un `essential` retiré ne laisse aucune entrée : il n'y est pas, comme
  `critical` aujourd'hui (`configuration-console.md:546`) ; l'historique de CFG5 le dira. Les lignes des
  modes hardis se lisent dans `assets.list` ou dans `autonomy.assets`, selon le fichier, et disent leur
  chemin.
- **Le push** et la main restent hors de la file, comme aujourd'hui (`configuration-console.md` §3.3) ; le
  push ne baisse jamais (§5.5).

---

## 7. L'affichage (pour CRT1)

Les textes de l'écran sont en anglais (ENG1a). Aucune couleur d'alarme : ni `--red`, ni `--orange`, ni
`--yellow` (la palette de la console, `CLAUDE_CONSOLE.md`).

### 7.1 La tuile

```
┌ rg-app · 3 VMs ───────────────────────────────────────────────────────────┐
│ vm-db-prod   [ESSENTIAL]   human_only   ⏸ CONFIRM            ● online     │
│   DETECT ✓   PROTECT ✓   RECOVER ✓                                        │
│ vm-web-01                  non_disruptive                    ● online     │
│   DETECT ✓   PROTECT ✓   RECOVER ✓                                        │
│ vm-dev-01    quiet         human_only                        ● online     │
│   DETECT ✓   PROTECT ✓   RECOVER –                                        │
└───────────────────────────────────────────────────────────────────────────┘
```
- **`ESSENTIAL`** : une marque à côté du mode, en capitales, entourée d'un trait fin (`--blue` ou
  `--cyan`), jamais pleine. Infobulle : « Essential (priority): its grave detections keep part of the
  model budget's reserve, and it is served first at equal gravity ».
- **`standard`** : rien. Le défaut ne fait pas de bruit.
- **`quiet`** : en minuscules, `--dim`. Infobulle : « Quiet (priority): watched by every rule; fewer
  pings and less model budget for its low detections; its grave ones are handled as anywhere ».
- **L'ordre** : dans un groupe, `essential` d'abord, puis par nom.
- **Une carte** (TO JUDGE, le fil) porte la même marque à côté du nom de la VM ; sa gravité reste la sienne.

### 7.2 La page Config

```
PRIORITIES                                                              ⚙ Config ▸ Priorities
essential · 2 entries · graves' reserve 2.00 $ (1.00 $ floor + 1.00 $ for these VMs)
  vm-db-prod      essential   « the ERP database »               1 VM today
  vm-erp-*        essential   (no reason)                        3 VMs today
quiet · 1 entry · their low detections: no ping, 0.25 $ a day per VM
  vm-dev-*        quiet       « recreated each night »           4 VMs today
standard · every other VM (the default)
notes · autonomy: is the former format of assets: — migrate it (glorfindel config migrate); autonomy.assets[0]
        says `critical: true`, the former name of priority: essential
Written in glorfindel-config.yaml for now; the console will write it through the signed queue (CFG5).
```
- **Les chiffres viennent d'une seule fonction** (`model_budget`), jamais recopiés (CRT1).
- « none » quand aucune entrée ne porte de priorité et qu'aucun `critical: true` ne reste.
- **La note de migration** (PRI2) : un fichier encore en `autonomy:` le dit en tête de la page, avec la
  commande ; un fichier aux deux formats n'arrive pas jusque-là (la watch le refuse au démarrage).
- Ce que désigne un motif, par la découverte : « N VMs today », ou « not found by the discovery today »
  (la forme de la vue « Relaxed »). La découverte ne décide jamais du niveau.

### 7.3 Le démarrage de la watch

```
Autonomy: default = human_only  (3 per-asset override(s))
Priorities: 2 essential (vm-db-prod, vm-erp-*) — their grave detections keep a 2.00 $ reserve;
            1 quiet (vm-dev-*); every other VM standard
  note: autonomy: is the former format of assets: — migrate it (glorfindel config migrate)
  note: autonomy.assets[0] says `critical: true`, the former name of priority: essential
```
- Les noms viennent de la config, échappés (`_outside`), vingt au plus, comme la ligne voisine.
- Une config illisible le dit déjà (`startup.py:103-111`) : la ligne des niveaux n'est pas écrite.

### 7.4 Le téléphone

Sous 760 px (MOB4), la marque passe sous le nom de la VM, sur la même ligne que le mode :
```
vm-db-prod
ESSENTIAL · human_only · ⏸ CONFIRM
```
La section « Priorities » de la page Config se lit en une colonne : le niveau, puis chaque entrée sur deux
lignes (le motif et sa raison ; ce qu'il désigne).

---

## 8. Les preuves

### 8.1 Les invariants à ajouter

- **PR1 — une classe plus haute ne relâche jamais une garde.** Pour une même détection et un même fichier,
  changer le seul niveau de la VM ne change ni l'action que les gardes de `decide` laissent partir seule,
  ni la carte qu'elles retiennent — sauf la réserve de préparation, qui ne peut que retenir. Deux preuves :
  une garde de structure (aucune garde de `decide`, `_apply_executable_guard` à `_uncontained_floor`, ne
  lit `level_of` : une lecture de l'arbre, comme `test_provider_boundary.py`), et une propriété
  (Hypothesis) sur les fonctions pures des gardes, le niveau tiré au hasard.
- **PR2 — monter ne retire rien à la VM.** Pour une VM, passer de `quiet` à `standard` à `essential` ne
  baisse jamais la part de budget de ses graves ni de ses ordinaires, ne retire jamais un ping, ne baisse
  jamais N ; une fois l'ordre de PRI4 en place, ne la fait jamais passer plus tard dans la porte à gravité
  égale. **De `quiet` à `standard`, seules ses basses changent** : ses graves et ses critiques ont le
  même budget, le même rang et le même ping aux deux niveaux.
- **PR3 — une grave reste grave.** `gravity()` ne lit pas le niveau ; une grave sur une VM `quiet` garde
  le plancher, le rang d'une grave de `standard`, et elle pingue, même dans un fil ouvert en silence.
- **PR4 — le push ne baisse jamais un niveau.** Pour toute paire (config d'Imladris, config du poste), le
  niveau poussé de chaque `match` est au moins celui d'Imladris ; `quiet` ne vient que d'Imladris ;
  `HUMAN_ONLY=1` laisse les niveaux.
- **PR5 — les deux lecteurs s'accordent** : mêmes clés, mêmes modes, mêmes niveaux, même verdict sur les
  mêmes configs, aux deux formats (§5.5).
- **PR6 — la classe d'un changement suit le niveau** : monter resserre, descendre relâche, par VM ; toute
  section acceptée est classée (la garde du constat 4).
- **PR7 — l'ancien format vaut le nouveau** : pour tout fichier à l'ancien format, sa migration donne à
  chaque nom le même mode et le même niveau (une propriété, Hypothesis, sur des fichiers tirés au hasard,
  doublons et motifs compris) ; les tests de PRT2 rejoués, paramétrés sur les deux formats, donnent les
  mêmes réserves, les mêmes seaux, la même attente ; la conversion vers l'ancien format ne rend jamais un
  mode plus hardi.
- **PR8 — une entrée sans mode ne change aucun mode** : ajouter ou retirer, sur n'importe quel fichier,
  une entrée qui ne porte que la priorité laisse `resolve` inchangé pour tout nom.
- **La machine à invariants** (`tests/unit/test_invariants.py`) : chaque VM du monde tire un niveau ; ses
  quinze propriétés doivent tenir quel que soit le niveau. Si Q4 retient l'option 1, une propriété de
  plus, l'oracle tiré du journal du faux Azure (A0) : **aucune écriture autonome sur le réseau d'une VM
  `essential` avant la confirmation de sa réserve**.

### 8.2 Les mutants

L'Orchestre donne les plages ; les lots en ont environ 40, plus ceux de CRT1 (§10). Exemples, par lot :
- **PRI2** : un niveau inconnu accepté ; `critical: true` ignoré (la réserve perdue) ; la contradiction
  les deux formats acceptés ensemble ; une entrée sans mode qui fait écran au mode d'un motif ; une entrée
  sans mode ni priorité acceptée ; le plus bas l'emporte ; un motif ignoré ; `assets` non classée
  (neutre) ; descendre classé « resserre » ; l'ancienne `_critical` gardée (le déplacement classé
  « relâche ») ; le push perd un `essential` d'Imladris ; le push pousse un `quiet` du poste ; une section
  d'Imladris refusée dont les modes sont gardés ; `assets:` envoyée à une release qui ne la lit pas ; la
  migration au push qui perd un mode ou un `essential` ; la conversion vers l'ancien format qui écrit un
  mode plus hardi ; un écrivain qui migre le fichier en silence ;
  un `essential` perdu hors de la file et tu ; les listes des deux lecteurs divergent.
- **CRT1** : la marque jamais posée ; un motif ignoré ; la réserve recopiée ou fausse ; la ligne de
  démarrage muette (sa fiche) ; `ESSENTIAL` en rouge.
- **PRI3** : la réserve `essential_service` jamais ajoutée ; ajoutée mais confirmée d'office ; une VM
  passée en `essential` reste autonome.
- **PRI4** : l'ordre entre les VM ignore le niveau (la première qui réessaie passe, comme avant) ; le
  niveau passe devant la gravité ; une grave de `quiet` rangée après une grave de `standard` ; les
  ordinaires de `quiet` à `VM_USD` ; une grave de `quiet` sans plancher ; le dossier d'une VM
  `essential` dit « non composé ».
- **PRI5** : une carte d'une VM `essential` qui attend un humain sans ping ; **un fil `quiet` ouvert en
  silence par une basse, puis une grave qui y arrive sans ping** ; la première grave d'un fil `standard`
  déjà ouvert sans ping ; une action seule sur `quiet` sans ping ; la gravité d'une carte montée par le
  niveau.
- **PRI6** : N non monté ; T monté avec N.

### 8.3 Ce qui se mesure au banc

La classe est du code déterministe : presque tout se prouve en tests. Le banc, une demi-séance avec PRI4 et
PRI5 (par Jonathan, sur une panne bénigne de Gothmog qui fait une détection grave, comme au 20/11) :
- **le push** lit les niveaux d'Imladris et les garde (`make imladris-push`, son rapport) ;
- **le démarrage** et la tuile disent les niveaux, sur Imladris et sur le téléphone ;
- **l'ordre**, une fois PRI4 fait : deux détections de même gravité retenues par le plafond dans la même
  minute, une sur une VM `essential`, une sur une VM `standard` : la première décidée d'abord. Aujourd'hui,
  l'ordre entre elles est celui de leur nouvel essai (§4.2) ;
- **Discord** : le ping d'une carte qui attend un humain sur la VM `essential` ; l'absence de ping à
  l'ouverture d'un fil bas sur la VM `quiet`, puis le ping de la grave qui y arrive ;
- **la préparation** (si Q4 = 1) : la réserve `essential_service` à l'écran d'activation, et le retour en
  `human_only` d'une VM autonome passée en `essential` ;
- **le chiffre de `quiet`** (0,25 $) se recale sur le coût mesuré d'une décision (`model_budget.json`) après
  une semaine de nuits.

---

## 9. Les questions à Jonathan

Chacune a ses options, la recommandée en premier, et sa raison. Les exemples : `vm-db-prod` (la base de
l'ERP), `vm-web-01` (un frontal parmi trois), `vm-dev-01` (recréée chaque nuit).

**Q1 — Combien de niveaux ?** (§3)
1. **Trois : `essential`, `standard` (le défaut), `quiet` (recommandée).** `vm-db-prod` essentielle,
   `vm-web-01` standard, `vm-dev-01` quiet. Chacun a un effet propre, et le bas donne une issue à une VM
   bruyante autre que l'exclure.
2. Deux : `essential` et `standard`. Le `critical` d'aujourd'hui renommé ; `vm-dev-01` reste standard, ou
   on l'exclut quand elle fait du bruit.
3. Quatre : `essential`, `important`, `standard`, `quiet`. `vm-web-01` important : une demi-réserve, un
   ping de plus. Plus fin, mais des effets à moitié.

*Raison* : trois niveaux donnent trois comportements nets ; un quatrième peut s'ajouter sans casser le
format.

**Q2 — Les mots à l'écran et dans le fichier ?** (§3)
1. **`essential` / `standard` / `quiet` (recommandée).** Sur la tuile : `ESSENTIAL`, rien, `quiet`. Aucun
   n'est un mot de gravité de carte.
2. `tier-1` / `tier-2` / `tier-3`. Familier en résilience, mais « tier 0 » dit autre chose en sécurité
   (Active Directory), et on ne sait pas si 1 est le haut ou le bas.
3. `high` / `normal` / `low`. Simple, mais une carte `high` sur une VM `high` mêle l'événement et l'objet.

*Raison* : les mots disent l'objet sans alarmer, et ne croisent aucun mot déjà pris (§1.4, constat 2).

**Q3 — Le principe : la classe peut-elle relâcher une garde de sûreté ?** (§2.2)
1. **Jamais : elle règle l'attention (budget, rang, bruit, affichage), jamais une garde (recommandée).**
   `vm-db-prod` essentielle est servie d'abord et n'attend pas l'argent, mais son seuil de confiance, ses
   tirages et son plafond de règle sont ceux de toutes les VM.
2. Le plus haut niveau peut contenir plus vite : un seuil de confiance plus bas, un tirage en moins sur
   `vm-db-prod`. Gagne quelques secondes sur un rançongiciel, au prix d'un isolement sur un faux positif
   plus probable, sur la VM où il coûte le plus.

*Raison* : la sûreté reste dans le code et dans le mode ; la leçon du projet (« jamais la confiance du
modèle ») vaut d'abord pour la VM qui compte le plus.

**Q4 — Une VM essentielle et l'autonomie : que fait la classe ?** (§4.5)
1. **Une réserve de préparation (recommandée).** Passer `vm-db-prod` en `essential` ajoute à sa
   préparation « ses actions seules, l'isolement qui coupe l'ERP compris, attendent qu'un humain l'ait
   voulu ». Tant qu'un humain ne l'a pas confirmé une fois, elle reste en `human_only` ; ensuite son mode
   décide, isolement compris. **Le coût** : dans cette fenêtre, `vm-db-prod` n'a **aucune** action seule,
   ni l'isolement, ni le blocage, ni l'instantané ; un rançongiciel qui tombe avant la confirmation attend
   un humain (une carte, un ping). La console propose la confirmation dans le même geste que le passage en
   `essential`, pour que la fenêtre dure le temps d'un clic.
2. Un plafond de l'objet, comme celui de la règle (RDW1) : sur `vm-db-prod`, une isolation autonome est
   ramenée à l'instantané et proposée sur la carte, quel que soit le mode ; le blocage d'une adresse et
   l'instantané restent au mode.
3. Rien : la classe ne touche pas l'autonomie ; l'opérateur pense lui-même à mettre `vm-db-prod` en
   `human_only`.

*Raison* : une seule décision, le mode, prise en sachant ce qu'elle coûte ; une fois la réserve
confirmée, le rançongiciel sur `vm-db-prod` garde un isolement seul si l'opérateur l'a voulu (l'option 2
le lui retire pour toujours), et personne ne découvre trop tard qu'une VM essentielle s'isolait seule
(l'option 3). La fenêtre sans action seule est le prix de cette confirmation ; elle ne touche qu'une VM
déjà autonome, et se ferme d'un clic.

**Q5 — Où s'écrit la classe dans le fichier ?** (§5.1)

La question telle qu'elle a été posée, avec la proposition de Jonathan en troisième option.
1. **Une section à part, `priorities:` (`match`, `level`, `reason`) (la recommandation de la note).** On
   rend `vm-db-prod` essentielle sans toucher son mode ; l'autonomie et ses clés ne changent pas.
2. Une clé `priority:` sur les entrées d'`autonomy.assets`, à la place de `critical`. Plus court, mais
   chaque VM classée doit recevoir un mode, et sous un défaut `non_disruptive` rendre `vm-db-prod`
   essentielle passerait par la confirmation d'un relâchement.
3. **La proposition de Jonathan : une seule section `assets:`**, qui remplace `autonomy:` —
   `default_mode`, `allow_destructive`, et une `list` d'entrées qui portent chacune un `mode` facultatif
   et une `priority` facultative. On écrit `vm-db-prod` une fois, son mode et sa priorité ensemble, et
   `vm-dev-*` avec sa seule priorité. Une VM se lit à un seul endroit ; l'ancien format est lu jusqu'à la
   1.0 et se migre.

*Raison de la recommandation d'alors* : la classe et le mode sont deux décisions, et la forme
d'aujourd'hui les lie (§1.4, constat 1). L'option 2 ramène exactement le risque que CRT1 avait : elle
ajoute une clé à `ASSET_KEYS`, la liste des clés d'une entrée d'autonomie que le push tient égale à celle
de la watch ; une clé que l'un connaît et pas l'autre rend la config d'Imladris « forme inconnue », et le
push remet alors toutes les VM en `human_only` (§5.5). L'option 3 délie aussi la classe et le mode (le
mode facultatif), au prix d'une section qui en remplace une autre ; elle change les clés des deux
lecteurs, ce qui se tient en les changeant dans le même lot, avec la garde de version du push (§5.5).

**Q6 — Deux entrées d'`assets.list` couvrent une VM : laquelle l'emporte, champ par champ ?** (§5.3)

Chaque champ se résout sur les seules entrées qui le portent. Exemple : `vm-erp-*` porte seulement
`priority: essential`, `vm-erp-test` seulement `mode: non_disruptive`, `vm-erp-qa` seulement
`priority: quiet`.
- **Le mode : la règle d'aujourd'hui, sans question** (`AutonomyConfig.resolve`, `config.py:390-412`) :
  le nom en minuscules ; s'il y a des entrées exactes, la plus prudente d'entre elles ; sinon le motif le
  plus long (en caractères) qui le couvre, et à égalité le plus prudent ; sinon `default_mode`. Une entrée
  sans mode n'y prend pas part. `vm-erp-test` est `non_disruptive`, `vm-erp-qa` et `vm-erp-prod-01`
  prennent `default_mode`.
- **La priorité :**
  1. **Le niveau le plus haut, toujours (recommandée).** `vm-erp-test` et `vm-erp-qa` sont essentielles
     (le motif) ; pour descendre `vm-erp-qa`, on resserre le motif (`vm-erp-prod-*`).
  2. La même règle que le mode : l'entrée exacte, puis le motif le plus long ; à égalité, le plus haut.
     `vm-erp-test` reste essentielle (son entrée exacte ne porte pas de priorité), `vm-erp-qa` devient
     quiet : une exemption.

*Raison* : une erreur d'écriture ne baisse jamais une VM qu'on croit essentielle ; c'est déjà la règle de
`critical`. Le mode garde sa règle : la changer toucherait l'autonomie de tout le parc.

**Q7 — Que devient l'ancien format, `autonomy:` et `critical: true` ?** (§5.4)
1. **Lus jusqu'à la 1.0, avec une note qui invite à migrer (`glorfindel config migrate`) ; la migration
   à valeurs égales est neutre ; les deux formats dans un même fichier, accordés ou en conflit, sont une
   erreur de config (recommandée).** Une config d'aujourd'hui démarre telle quelle, garde ses modes et
   sa réserve, et se migre quand l'opérateur le veut.
2. Refusés dès la release qui lit `assets:` : une config d'aujourd'hui ne démarre plus (toutes les VM en
   `human_only`) tant qu'on ne l'a pas réécrite.
3. Gardés pour toujours comme une seconde forme.

*Raison* : aucune rupture pour qui a écrit `autonomy:` ou posé `critical: true` depuis la 0.6.7, et une
seule forme à la 1.0.

**Q8 — D'où vient la classe ?** (§2.1)
1. **Du fichier seul (recommandée).** On la pose dans `glorfindel-config.yaml`, par la main aujourd'hui,
   par la console avec CFG5.
2. Du fichier, et d'un tag Azure (`eregion-priority=essential`) posé par le Terraform du client, qui ne
   peut que monter. Pratique pour un parc décrit en code, mais une lecture d'Azure de plus, et un tag
   écrit hors de la file.
3. Des tags seuls.

*Raison* : la classe se change par la file de CFG1, qui confirme ce qui relâche ; un tag s'écrit par qui
écrit la ressource. L'option 2 reste ouverte plus tard, dans le seul sens qui resserre.

**Q9 — Les cartes et Discord ?** (§4.4)
1. **La gravité d'une carte ne change jamais ; à tous les niveaux, la première grave d'un fil pingue,
   même dans un fil déjà ouvert (un changement pour `standard` aussi : aujourd'hui, une carte dans un fil
   ouvert ne pingue jamais), et une action seule pingue toujours ; `essential` pingue en plus chaque carte
   qui attend un humain ; `quiet` ne pingue plus l'ouverture d'un fil pour une détection basse
   (recommandée).** Une force brute sur `vm-dev-01` ouvre son fil sans mention ; un rançongiciel qui suit
   dans ce fil pingue ; un `mode_hold` sur `vm-db-prod` pingue même dans un fil ouvert.
2. La gravité d'une carte monte d'un cran sur une VM essentielle. Plus visible, mais une force brute sur
   `vm-db-prod` deviendrait « critique » et prendrait la place des vraies compromissions dans la file.
3. Rien ne change aux notifications : la classe ne se voit qu'à l'écran.

*Raison* : le niveau dit l'objet, la gravité l'événement ; le bruit suit l'objet, la file suit
l'événement. Sans la règle de la première grave, un fil `quiet` ouvert en silence tairait un rançongiciel
qui suit : pire qu'aujourd'hui.

**Q10 — Ce qui part avant la 0.7 ?** (§10)
1. **En 0.6.x : la lecture et la reprise (PRI2), l'affichage (CRT1), la réserve de préparation (PRI3),
   l'ordre entre les VM dans la porte, le budget de `quiet` et le dossier (PRI4), les notifications
   (PRI5) ; sur Imladris, `quiet` posé à la main par Jonathan jusqu'à CFG5. En 0.7 : l'enquête (PRI6),
   avec ENQ5 mesuré, et PRT3 (recommandée).** La classification vit tout de suite.
2. Tout en 0.7, avec PRT3 : un seul passage, mais `critical` reste invisible et seul d'ici là.
3. En 0.6.x, la lecture et l'affichage seulement ; les effets en 0.7.

*Raison* : chaque effet de la 0.6.x touche du code qui existe (le budget, le dossier, le bot), sauf
l'ordre entre les VM, que la porte n'a pas et que PRI4 ajoute (le plus gros des effets) ; l'enquête
attend sa propre mesure. Si l'ordre ne vaut pas son coût en 0.6.x, PRI4 peut le laisser à PRT3 sans
toucher le reste.

---

## 10. Les lots

En jours de travail effectif, à ±50 %, comme la feuille de route. Les mutants sont estimés ; l'Orchestre
donne les plages. Le découpage suit les recommandations ; une autre réponse à Q4, Q5 ou Q10 le change
(dit dans la colonne « Risques »).

| Lot | Session | Ce qu'il touche | Taille | Jalon | Risques | Mutants |
|---|---|---|---|---|---|---|
| **PRI2** — le format `assets:`, la migration et la reprise de l'ancien format | Glorfindel (et le push, côté Imladris) | la section `assets:` lue strictement (§5.2) : `default_mode`, `allow_destructive`, `list` (`match`, `mode` et `priority` facultatifs, `reason`), une entrée vide ou en double refusée ; un seul modèle en mémoire, `resolve` sur les seules entrées qui portent un mode, `level_of` (§5.3) ; l'ancien format (`autonomy:`, `critical: true`) lu avec sa note, les deux formats ensemble refusés (§5.4) ; `glorfindel config migrate`, dans les deux sens (§5.4, §5.6) ; les écrivains qui gardent le format du fichier (le sélecteur de mode de la console, le défaut, la CLI) ; `is_critical` et `critical_count` sur `level_of`, les seaux gardés ; CFG4 sur le modèle, `_critical` remplacée, la migration neutre et son test, la garde des sections (constat 4) ; la vue « Relaxed » aux deux formats ; la note de migration au démarrage et dans `/api/config` ; le push : `ASSET_KEYS` et `KNOWN_PRIORITIES` changés avec la watch, une config d'Imladris refusée entière inconnue, jamais plus bas, `quiet` d'Imladris seul, la garde de version (le format de la release d'Imladris), la migration d'Imladris au push, la conversion vers l'ancien format (§5.5, §5.6) ; la watch qui dit un `essential` perdu hors de la file ; le test des deux lecteurs et le test des mêmes verdicts ; les mutants de PRT2 ré-ancrés ; la doc : `configuration-console.md` (CFG1, CFG5 nomment partout `autonomy.assets`), `operations.md` (le format, la migration, `quiet` posé à la main sur Imladris, le retour arrière), `glorfindel.md` (« Modes d'autonomie par asset »), `raisonnement.md`, `fichiers-cles.md` | 4 j | 0.6.x | un lecteur qui diverge : toutes les VM en `human_only` au push ; une migration qui change un mode (la propriété PR7 la tient) ; un écrivain oublié qui écrit l'ancien format dans un fichier migré ; un retour arrière refusé tant que la section est là | ~17 |
| **CRT1** — l'affichage (repris) | Console, une ligne Glorfindel | la tuile, la page Config, le démarrage, le téléphone (§7) ; `/api/config` transmet le mode et la priorité de chaque entrée d'`assets.list` (ou de l'ancien format) et le niveau de chaque VM, les notes de PRI2, la réserve calculée par le budget | 1,5 j | 0.6.x, après PRI2 | une couleur d'alarme ; un chiffre recopié | M7771–M7780 (sa fiche, à refaire sur ce format) |
| **PRI3** — la réserve de préparation de `essential` (si Q4 = 1) | Glorfindel, une ligne Console | `essential_service` dans `readiness.py`, confirmée comme les autres ; le retour en `human_only` d'une VM autonome passée en `essential` ; la carte `readiness_hold` ; la propriété de la machine à invariants (§8.1) | 1 j | 0.6.x, après PRI2 | une VM essentielle retenue sans carte (personne ne sait pourquoi elle n'agit pas) | ~4 |
| **PRI4** — l'ordre entre les VM dans la porte, le budget de `quiet`, le dossier | Glorfindel | **un ordre entre les VM, que la porte n'a pas** (la première qui réessaie passe, `decision_queue.py:419-426`, `:707-709`) : un registre des décisions qui attendent une place, rangé par gravité, puis par niveau (les graves de `quiet` avec celles de `standard`), puis par arrivée (§4.2) ; les ordinaires de `quiet` au quart de `VM_USD` ; le dossier `critique` d'une VM `essential` (`dossier.py:232`) ; `docs/raisonnement.md` §2.5 et `dossier-isolation.md` mis à jour | 2,5 j | 0.6.x, après PRI2 | l'ordre touche le plafond de PRT1 (un critère de sa preuve : jamais plus de `MODEL_CALLS_PER_MIN`) ; une famine des `quiet` sous un flot d'`essential` ; si l'ordre ne vaut pas son coût, il part à PRT3 et PRI4 tombe à 1 j | ~8 |
| **PRI5** — les notifications | Glorfindel (le bot) | le niveau sur la carte (`priority`) ; **la première grave ou critique d'un fil pingue, même fil ouvert, à tous les niveaux** (aujourd'hui, seule la création du fil et l'action seule pinguent, `bot.py:1589-1596`, `:1673-1678`) ; le ping de chaque carte qui attend un humain sur `essential` ; pas de ping à l'ouverture d'un fil bas sur `quiet` ; les actions seules pinguent partout (§4.4) ; la ligne de Discord d'un changement de niveau (§6) | 1,5 j | 0.6.x, après PRI2 | trop de pings sur un parc tout `essential` ; un ping de plus par incident sur `standard` | ~5 |
| **PRI6** — l'enquête par niveau | Glorfindel | N = 6 pour `essential`, T inchangé, après la mesure d'ENQ5 (§4.3) ; la part de la décision dite à la porte | 0,5 j | 0.7 | deux appels de plus au-delà de la place des graves | ~2 |
| **PRT3** — la porte qui trie, branchée sur la classe | Glorfindel | la classe comme donnée du tri ; les contraintes du §4.2 (aucune exception large sur `essential`, rien d'automatique sur `quiet`, jamais le silence) | (sa fiche) | 0.7 | — | (sa fiche) |
| **PRI7** — retirer `critical` | Glorfindel | la clé refusée, la note devenue erreur, le push et sa doc | 0,5 j | 1.0 | une config jamais déplacée : dite depuis la 0.6.x | ~2 |

**Total** : environ 11,5 jours hors PRT3 (10 si l'ordre entre les VM part à PRT3), environ 40 mutants plus ceux de CRT1. PRI2 a grossi d'un jour avec le format de Jonathan (la section, la migration, les deux lecteurs, la note de migration).

**L'ordre.** PRI2 d'abord : tout lit `level_of` et le modèle unique. CRT1 ensuite, sur son format (sa
fiche, écrite pour `priority: true`, est à reprendre : les niveaux, `assets.list`, « Priorities », la
marque `ESSENTIAL` ; la note de migration est à PRI2). PRI3,
PRI4 et PRI5 en parallèle après PRI2. La demi-séance du banc (§8.3) après PRI4 et PRI5. PRI6 avec ENQ5
mesuré, PRT3 en 0.7. PRI7 à la 1.0.

**Si les réponses changent** : Q4 = 2 remplace PRI3 par un plafond de l'objet dans `decide` (1,5 j, et un
critère de la 1.0, « aucun constat haut ouvert sur le chemin d'isolation », à relire) ; Q4 = 3 supprime
PRI3 ; Q1 = 2 supprime ce que `quiet` touche
dans PRI2, PRI4 et PRI5 (environ 1 j de moins).

---

## 11. Les limites

- **La classe ne protège pas d'une config fausse.** Une VM essentielle oubliée dans `assets.list` est
  `standard` : rien ne le devine. La page Config montre ce qui est classé ; rien ne montre ce qui ne l'est
  pas, sauf la carte de l'infra, tuile par tuile.
- **Le compte de la réserve est par entrée, pas par VM** (§1.1) : un motif `essential` qui couvre dix VM
  apporte 0,50 $, comme une seule. La note le garde (la réserve reste bornée et lisible) ; un parc où
  beaucoup de VM sont essentielles verra le plafond de 2,50 $ tôt.
- **Une console compromise peut tout monter en `essential`.** C'est un resserrement, il s'applique ; il
  réduit les ordinaires du parc et multiplie les pings (une fatigue d'alerte). L'annonce forte au-delà de
  5 VM (§6) le rend visible ; elle ne l'empêche pas.
- **Le rang dans la porte n'existe pas aujourd'hui** (§4.2) : entre les VM, la première qui réessaie
  passe. Jusqu'à PRI4, `essential` n'est servie d'abord nulle part ; elle n'attend ni l'argent ni le
  refroidissement du fournisseur, c'est tout.
- **Les versions du poste et d'Imladris** (§5.5) : un push depuis un poste d'avant PRI2 efface les niveaux
  d'Imladris ; le code d'avant ne change pas, la watch d'Imladris le dit (un `essential` perdu hors de la
  file), elle ne l'empêche pas. Le geste qui l'évite : mettre le poste à jour avant de pousser.
- **`quiet` sur Imladris** ne se pose qu'à la main sur l'hôte, par Jonathan, jusqu'à CFG5 (§5.5).
- **Le retour arrière** sous PRI2 demande un geste (§5.5) tant que le préflight ne lit pas la config par
  les deux images (MSUB6).
- **Les abonnements ajoutés** (MSUB3) : jusqu'à ce que MSUB3 indexe par (abonnement, motif), une entrée de
  `assets.list` vaut par le nom, comme le mode aujourd'hui ; un homonyme d'un autre abonnement prendrait le
  niveau. Pour `essential`, c'est un resserrement ; pour `quiet`, un relâchement hérité — la même limite
  que MSUB1 a relevée pour le mode (`watch-multi-abonnement.md` §1.6), fermée par le même lot.
- **Deux formats jusqu'à la 1.0** (§5.4) : tout lecteur et tout écrivain du fichier les connaît tous
  les deux, ou se trompe en silence. PRI2 les recense (la watch, le push, la console, la CLI, CFG4, la vue
  « Relaxed ») ; un écrivain oublié écrirait l'ancien format dans un fichier migré, que la watch refuserait
  alors (les deux formats ensemble) : bruyant, jamais silencieux.
- **Le chiffre de `quiet`** (0,25 $ par jour) est une proposition, à recaler sur la mesure (§8.3).
