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
  Imladris (§1.2).
- **Trois axes, qui ne se remplacent pas** (§2.3) : la **zone** (`bench`, `twin`, `production` : ce qu'une
  expérience a le droit d'y faire, lue sur les tags), le **mode** (`human_only`, `non_disruptive` : ce que
  Glorfindel fait seul, la décision) et la **classe** (combien la VM compte : l'attention).
- **Trois niveaux proposés** (§3), des mots qui n'alarment pas : **`essential`** (une VM dont la perte
  arrête le métier ; le `critical: true` d'aujourd'hui), **`standard`** (le défaut, rien ne change), et
  **`quiet`** (une VM surveillée en silence : moins de bruit et de budget pour ses détections ordinaires,
  jamais pour ses graves). Aucun mot de la gravité des cartes (`critical`, `high`, `low`) : ils disent un
  événement, pas un objet.
- **Les effets** (§4, tableau au §4.8) : `essential` garde l'effet de PRT2 (la réserve, l'attente), passe
  d'abord dans la porte à gravité égale, a son dossier toujours composé, une enquête plus profonde à délai
  égal (0.7), un ping pour chaque carte qui attend un humain. `quiet` ne pingue plus l'ouverture d'un fil
  pour une détection basse, et ses détections ordinaires ont un quart du budget par VM. **Une grave reste
  grave à tous les niveaux.**
- **L'autonomie** (§4.5, Q4) : la classe ne décide pas ; le mode reste la décision. Proposé : passer une VM
  en `essential` ajoute une **réserve à sa préparation** (« l'isoler coupe un service déclaré essentiel »),
  qu'un humain confirme une fois, comme les autres réserves de L6. Une VM déjà autonome repasse en
  `human_only` jusqu'à cette confirmation. Plus vite, oui, par le rang et le budget ; jamais par une garde.
- **Le format** (§5, Q5) : une section à part, `priorities:` (`match`, `level`, `reason`), et non une clé de
  plus sur `autonomy.assets` : une entrée d'autonomie exige un mode, et poser `critical` sur une VM
  aujourd'hui oblige à lui en écrire un (§1.4, constat 1). Le plus haut niveau l'emporte (Q6).
- **La reprise de `critical: true`** (§5.4, Q7) : lu comme `essential`, avec une note qui invite à le
  déplacer ; une contradiction entre les deux est une erreur de config ; accepté jusqu'à la 1.0.
- **Les deux lecteurs** (§5.5) : la watch (`glorfindel/config.py`) et le push vers Imladris
  (`infra/glorfindel-host/host_config.py`), tenus égaux par un test. Le push ne baisse jamais un niveau :
  `essential` vient d'Imladris ou du poste, `quiet` seulement d'Imladris.
- **Les classes de CFG1** (§6) : monter resserre (tout de suite, une ligne sur Discord) ; descendre relâche
  (le nom tapé, la raison, le délai) ; une entrée `quiet` se voit dans la vue « Relaxed ».
- **L'affichage** (§7, pour CRT1) : `ESSENTIAL` en marque neutre, jamais rouge ; rien pour `standard` ;
  `quiet` en gris ; une section « Priorities » dans la page Config ; une ligne au démarrage.
- **Ce qui ne change pas** : ce que voit le modèle (la classe n'entre jamais dans son message),
  `human_only` par défaut, la règle de production, les zones, les injecteurs.
- **Sept lots** (§10), environ 8 jours : PRI2 (la lecture et la reprise), CRT1 (l'affichage, repris),
  PRI3 (la réserve de préparation), PRI4 (la porte, le budget de `quiet`, le dossier), PRI5 (les
  notifications) en 0.6.x ; PRI6 (l'enquête) et le branchement de PRT3 en 0.7 ; PRI7 (retirer `critical`)
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

La classe et le mode sont deux décisions ; la forme d'aujourd'hui les lie. C'est la raison du format
proposé (§5.1).

**Constat 2 — le mot `critical` est déjà pris.** C'est une gravité de détection (`critical`, `high`,
`medium`, `low`, `signal_origin.form_refusal`) et une classe de la file (`CRITICAL`, `GRAVE`, `LOW`,
`glorfindel/decision_queue.py:117`), « le mot du RulePoller seul » (SEC-E). Sur une tuile, « CRITICAL » se
lit comme une alerte (Jonathan, 26/11). Une carte `critical` sur une VM `critical` mêle l'événement et
l'objet.

**Constat 3 — le push copie tel quel ce qui n'est pas l'autonomie.** `host_config()` part de la config
du poste (`out = dict(cfg)`, `host_config.py:116`) et ne réécrit que la section `autonomy`. Une section
nouvelle serait donc **écrasée** sur Imladris par celle du poste : un niveau posé sur Imladris, absent du
poste, serait perdu au push. Toute section de classification doit être lue par le push, pas copiée (§5.5).

**Constat 4 — une section que CFG4 ne classe pas est neutre.** `_others` ne parcourt que `_UNCLASSIFIED`
(`config_class.py:44-45`, `:145-150`) ; une section absente de la liste ne donne aucune raison, et
`classify` la rend **neutre** (`:153-173`). Le même piège que MSUB1 a relevé pour `subscriptions:`
(`watch-multi-abonnement.md`, §1.6) : une section `priorities:` ajoutée à la lecture stricte sans être
classée ferait passer un `quiet` sans confirmation (§6).

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

**Plus vite, sans relâcher.** Une VM essentielle peut être contenue plus tôt : sa décision passe d'abord
dans la porte, elle n'attend jamais l'argent ni le refroidissement du fournisseur. Elle ne l'est jamais
par une garde plus basse : ni un seuil de confiance réduit, ni des tirages en moins, ni un plafond de règle
levé. Ce serait un relâchement que la classe ne fait pas (Q3).

### 2.3 Trois axes qui se croisent : la zone, le mode, la classe

```
                 ┌───────────────────────────────────────────────────────────┐
  la zone        │ bench · twin · production      lue sur les tags (O0)      │  ce qu'une expérience
  (injecteurs)   │                                 de la VM et de son groupe │  a le droit d'y faire
                 └───────────────────────────────────────────────────────────┘
                 ┌───────────────────────────────────────────────────────────┐
  le mode        │ human_only · non_disruptive    autonomy (le fichier)      │  ce que Glorfindel
  (la décision)  │                                 + la préparation (L6)     │  fait seul
                 └───────────────────────────────────────────────────────────┘
                 ┌───────────────────────────────────────────────────────────┐
  la classe      │ essential · standard · quiet   priorities (le fichier)    │  combien la VM compte :
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
| **`quiet`** | celles qu'on veut surveiller sans bruit, plutôt que les exclure | `vm-dev-01`, recréée chaque nuit | moins de bruit pour ses détections basses, un quart du budget de ses ordinaires ; ses graves inchangées |

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

- **L'ordre** : la gravité d'abord, toujours (`gravity` : la classe critique, puis grave, puis basse,
  `decision_queue.py:129-138`) ; **à gravité égale, le niveau** (`essential`, puis `standard`, puis
  `quiet`) ; puis l'arrivée. La classe ne fait jamais passer une détection basse d'une VM `essential`
  devant une grave d'une VM `standard` : un rançongiciel sur `vm-dev-01` passe avant une force brute sur
  `vm-db-prod`.
- **Où l'ordre joue** : la file est celle de chaque VM (`decision_queue.py:3-17`) ; entre les VM, l'ordre
  joue là où plusieurs décisions attendent la place de leur classe dans la minute (PRT1). Ce point est à
  lire dans le code de la porte (`room_in`) par PRI4, avant d'en fixer la forme ; si la porte ne sert pas
  dans un ordre aujourd'hui, PRI4 dit ce qu'il faut pour qu'elle le fasse.
- **L'admission** : la place des graves (quatre appels par minute) ne change pas ; aucune place n'est
  réservée à `essential` (une place réservée serait prise aux autres graves).
- **L'attente** : pendant le refroidissement du fournisseur, une grave `essential` part tout de suite par
  le chemin du code (`_slowed`, l'existant) ; une grave `standard` ou `quiet` attend, jusqu'à la deuxième
  limite (`_strikes >= 2`), comme aujourd'hui.
- **Le dédoublonnage** (une décision par VM, règle, gravité et source en cinq minutes) ne change pas : le
  raccourcir pour `essential` multiplierait les appels sans preuve de plus.
- **`quiet`** : ses détections basses passent les dernières de leur classe ; quand la place des basses est
  prise, elles deviennent des cartes les premières (l'existant pour toute basse au-delà du plafond).
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
- **Discord**, proposé (aujourd'hui : le rôle `DISCORD_PING_ROLE` est pingué à l'ouverture d'un fil, et à
  chaque action prise seule, `docs/glorfindel.md`, « alerting webhook + bot Discord ») :
  - `essential` : en plus, un ping pour **chaque carte qui attend un humain** dans un fil déjà ouvert
    (`mode_hold`, `low_confidence`, `telemetry_gap`, `unstable_decision`, `readiness_hold`…), une fois par
    carte ;
  - `standard` : rien ne change ;
  - `quiet` : **pas de ping à l'ouverture d'un fil pour une détection basse** ; le fil s'ouvre, la carte y
    est, sans mention ;
  - **à tous les niveaux**, une détection grave ou critique, et une action prise seule, pinguent : « une
    action autonome alerte toujours quelque part » (JUG1) ne descend jamais.
- **Le webhook** ne change pas. **TO JUDGE** non plus : l'ordre reste celui du temps, la carte montre le
  niveau.

### 4.5 (e) Ce que Glorfindel s'autorise seul

Le mode reste la décision (action ≠ décision) ; la classe peut au plus resserrer. Les deux sens, pesés :
- **isoler `vm-db-prod` coupe l'ERP** : une isolation sur un faux positif est la peur du client sans SOC
  (« l'action réversible mais disruptive décidée en autonome », `docs/glorfindel.md`, « Modes d'autonomie
  par asset »). Le banc l'a montré le 20/11 : une sauvegarde lourde a fait proposer `isolate_vm` à 80 %
  (RDW1) ;
- **un rançongiciel sur `vm-db-prod` est pire** : chaque minute chiffre plus. Le chemin du code y fait déjà
  l'instantané ; l'isolement seul, s'il est permis, le contient.

Trois réponses possibles (Q4) :
1. **Proposé : une réserve de préparation.** Passer une VM en `essential` ajoute à sa préparation (L6,
   `glorfindel/readiness.py`) une réserve `essential_service` : « l'isoler coupe un service déclaré
   essentiel ». Comme toute réserve, elle se confirme une fois (`acknowledged`) ; d'ici là, la VM reste en
   `human_only` quoi que dise son mode, et une carte `readiness_hold` le dit (« ⚡ Review & turn on »). Une VM
   déjà autonome qui devient `essential` y retourne, comme pour toute réserve apparue après l'activation.
   Confirmée, son mode décide, isolement compris. **Une seule décision (le mode), prise en sachant, et
   datée** ; le cas du rançongiciel garde son isolement seul si l'opérateur l'a voulu.
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
- **Plusieurs abonnements** (MSUB3) : une entrée de `priorities:` sans clé `subscription` ne vaut que pour
  l'abonnement de la watch, comme une entrée d'autonomie (« rien n'est hérité »,
  `watch-multi-abonnement.md` §4.3) ; MSUB3 indexe la classe par (abonnement, motif), comme le mode.

### 4.8 Le tableau, niveau × axe

| Axe | `essential` | `standard` (défaut) | `quiet` | Quand |
|---|---|---|---|---|
| **(a) la réserve du modèle** | +0,50 $ par entrée, jusqu'à 2,50 $ ; la part au-dessus du plancher pour ses graves seules ; une grave n'attend jamais l'argent | le plancher de 1 $ ; ses ordinaires au plus 1 $ par jour | ses graves : le plancher ; ses ordinaires au plus 0,25 $ par jour | `essential` : l'existant ; `quiet` : 0.6.x |
| **(b) la porte** | d'abord, à gravité égale ; sa grave n'attend pas le refroidissement du fournisseur | l'existant | la dernière de sa classe ; ses basses, cartes les premières | 0.6.x ; PRT3 en 0.7 |
| **(c) l'enquête** | N = 6, T = 30 s inchangé | N = 4, T = 30 s | N = 4, T = 30 s | 0.7, après ENQ5 |
| **(c) le dossier** | toujours `critique` : d'abord, jamais « non composé » | selon la gravité (l'existant) | selon la gravité | 0.6.x |
| **(d) la carte** | gravité inchangée ; le niveau dit | inchangée | inchangée | 0.6.x |
| **(d) Discord** | un ping par carte qui attend un humain | l'existant | pas de ping à l'ouverture pour une basse ; les graves et les actions seules pinguent | 0.6.x |
| **(e) l'autonomie** | une réserve de préparation à confirmer (Q4) ; le mode décide | le mode décide | le mode décide | 0.6.x |
| **(f) la console** | `ESSENTIAL`, neutre ; en tête du groupe | rien | `quiet`, en gris | 0.6.x (CRT1) |
| **(g) la zone, les injecteurs, le modèle** | rien | rien | rien | — |
| **Les gardes de `decide`** | rien | rien | rien | — |

---

## 5. Le format dans la configuration

### 5.1 Deux formes, une recommandée

**A — une clé sur les entrées d'`autonomy.assets`**, à la place de `critical` :
```yaml
autonomy:
  assets:
    - match: vm-db-prod
      mode: human_only          # obligatoire (config.py:1118-1120)
      priority: essential       # essential | standard | quiet
```
- Pour : le chemin le plus court ; `critical` y est déjà ; le push la lit déjà à côté du mode.
- Contre : le constat 1 (§1.4) — un mode imposé pour chaque VM classée, et un resserrement classé « relâche »
  sous un défaut `non_disruptive` ; la classe rangée dans l'autonomie, alors qu'elle n'en est pas une.

**B — une section à part, `priorities:`** (recommandée, Q5) :
```yaml
priorities:
  - match: vm-db-prod           # un nom ou un motif, sans la casse, comme autonomy et exceptions
    level: essential            # essential | standard | quiet ; obligatoire
    reason: "the ERP database"  # facultative, comme une exclusion (CFG2)
  - match: vm-dev-*
    level: quiet
    reason: "recreated each night"
```
- Pour : la classe ne demande aucun mode, et ne le change pas ; poser `essential` ne fait que resserrer ;
  une raison, comme une exclusion ; un axe à part, une section à part.
- Contre : une section de plus à classer (constat 4), à faire lire au push (constat 3), et que les
  releases d'avant refusent (§5.5).

### 5.2 La forme proposée (B), lue strictement (A3)

- **`priorities:`** est une liste ; absente ou vide, toutes les VM sont `standard`.
- **Chaque entrée** : `match` (un texte non vide), `level` (une valeur de la liste fermée), `reason`
  (facultative, un texte) ; toute autre clé est refusée, comme dans `autonomy.assets`. `subscription`
  viendra avec MSUB3 (§4.7).
- **`level: standard`** est accepté : il ne fait rien à lui seul (le plus haut l'emporte, §5.3), mais il
  documente une VM qu'on a regardée. La lecture le dit au démarrage (« standard: no effect »).
- **Le même `match` deux fois**, sans la casse : refusé, et dit (« one entry per name or pattern »). Deux
  motifs différents qui couvrent la même VM sont permis : le §5.3 les départage.
- **Pas de `default`** : le défaut est `standard`, fixe (§3).
- **Une valeur inconnue** (`critical`, `high`, une faute) : refusée, comme tout écart d'A3 ; la watch
  démarre alors comme pour toute config illisible, toutes les VM en `human_only` jusqu'à correction
  (`glorfindel/watch/startup.py:103-111`). C'est le côté sûr, et il est bruyant.
- **Une seule fonction** rend le niveau d'une VM (`level_of(name)`), pour la watch, la console, la classe
  d'un changement et la vue « Relaxed ». `is_critical` devient `level_of(name) == essential`, et
  `critical_count` le compte des entrées `essential`.

### 5.3 Plusieurs entrées sur une VM : le plus haut l'emporte

**Proposé (Q6) : parmi toutes les entrées qui couvrent une VM, exactes ou par motif, le niveau le plus
haut.** C'est la règle de `is_critical` aujourd'hui (§1.1), et la seule où une erreur ne baisse jamais un
niveau.
- `vm-erp-*: essential` et `vm-erp-test: quiet` : `vm-erp-test` est `essential`. Pour la descendre, on
  resserre le motif (`vm-erp-prod-*`), on ne l'exempte pas.
- La règle du mode (l'entrée exacte, puis le motif le plus long) permettrait l'exemption, mais une entrée
  exacte `quiet` posée sous un motif `essential` baisserait en silence une VM que l'opérateur croit
  essentielle. CFG4 la classerait « relâche » ; la note préfère qu'elle ne puisse pas exister.

### 5.4 La reprise de `critical: true`

Proposé (Q7), dans la release qui lit `priorities:` (PRI2) :
- **`critical: true`** sur une entrée d'`autonomy.assets` se lit comme une entrée
  `{match: <le même>, level: essential}`. Rien ne change pour la VM : sa réserve, son attente, sa classe.
- **Une note le dit**, au démarrage de la watch et dans `/api/config` (pas de `glorfindel config check`
  aujourd'hui) : « `critical` is the former name of `level: essential` — move it to `priorities:`
  (autonomy.assets[0]) ». Jamais une erreur.
- **`critical: false`** ne dit rien, comme aujourd'hui (c'est le défaut du champ) ; la note invite à le
  retirer. Il ne contredit aucune entrée.
- **Les deux pour un même `match`** (sans la casse) : `critical: true` et `level: essential` s'accordent,
  avec la note ; `critical: true` et `level: standard` ou `quiet` se contredisent : **une erreur de
  config**, dite, comme deux valeurs différentes d'une même clé (la décision de Jonathan pour CRT1, le
  26/11, reprise ici avec des niveaux).
- **Jusqu'à quand** : accepté jusqu'à la 1.0, avec la note ; un lot de la 1.0 le retire (PRI7, §10).
- **Les noms internes** : `is_critical`, `critical_count`, `critical_part`, `CRITICAL_USD` se renomment
  (`is_essential`…) quand c'est raisonnable, et les mutants de PRT2 se ré-ancrent sans s'affaiblir. **Les
  seaux persistés** `real/critical` et `real/noncritical` (`~/.glorfindel/model_budget.json`) **gardent
  leur nom** : les renommer remettrait le compte du jour à zéro au redéploiement, ou demanderait une
  migration du fichier pour un mot.
- **La console** garde la clé quand elle réécrit une entrée (`set_asset_mode`, l'existant) ; elle ne
  convertit rien elle-même : le déplacement est un geste de l'opérateur (ou de CFG5, plus tard).

### 5.5 Les deux lecteurs : la watch et le push

**La watch** (`glorfindel/config.py`) : `_SECTIONS` gagne `priorities` ; `_check_priorities` lit le §5.2 ;
`level_of` le §5.3 ; la reprise le §5.4.

**Le push vers Imladris** (`infra/glorfindel-host/host_config.py`), qui n'importe rien de Glorfindel :
- **sa lecture** de `priorities:` est la même que celle de la watch : les mêmes clés, les mêmes niveaux,
  le même refus d'un `match` deux fois. Une entrée que la watch refuserait rend la section d'Imladris
  « forme inconnue », dit ;
- **jamais un niveau plus bas** (l'esprit de BL1c, « jamais un mode plus hardi »), pour chaque `match` :
  - `essential` vient d'Imladris **ou** du poste : il n'est jamais perdu par un push, comme `critical`
    aujourd'hui (`host_config.py:124-152`) ;
  - `quiet` ne vient **que** d'Imladris : un `quiet` du poste n'est pas poussé (il relâcherait sans la
    confirmation que la console d'Imladris demande), et le rapport du push le dit (« quiet on this
    machine only: not pushed ») ;
  - une section d'Imladris illisible : ses `quiet` ne sont pas gardés (rien de plus bas), ses `essential`
    non plus (on ne sait pas les lire) ; le push envoie les `essential` du poste, et le dit ;
- **le constat 3** : la section n'est plus copiée du poste, elle est **calculée** comme l'autonomie ;
- **`HUMAN_ONLY=1`** ne touche pas les niveaux : ils ne font qu'ajouter de l'attention, et le geste
  d'urgence reste celui des modes ;
- **`critical: true`** reste lu par le push comme aujourd'hui, et compte comme `essential` dans la même
  règle ; le push ne convertit rien.

**Le test qui les tient égaux** : celui d'aujourd'hui (`test_glorfindel_host.py:190-198`) ajoute
`PRIORITY_KEYS`, `LEVELS` et leur ordre, comparés à ceux de la watch. Une valeur que l'un accepte et pas
l'autre rendrait la config « forme inconnue » au push, et **remettrait toutes les VM en `human_only`** :
c'est le point dur, et le test le tient. Un second test donne les mêmes configs aux deux lecteurs (un
niveau inconnu, un `match` vide, deux fois le même, une clé de plus) et attend le même verdict.

**Le retour arrière.** Une release d'avant PRI2 refuse la section `priorities:` (une section inconnue,
`config.py:872`). Le préflight du CD passe la config d'Imladris à la lecture stricte de l'image candidate
(`watch-multi-abonnement.md` §1.8) : un retour arrière sous PRI2 est donc refusé tant que la section est
là, et le CD le dit. Le geste est écrit dans la doc de PRI2 : réécrire les `essential` en `critical: true`,
retirer les `quiet`, puis revenir en arrière. MSUB6 prévoit le préflight par les deux images ; PRI2
s'y range s'il arrive après.

---

## 6. Les classes de CFG1 et CFG5

La classe d'un changement (CFG4, `glorfindel/config_class.py`) suit le sens du niveau, VM par VM, pour
tout `match`, découvert ou non (`configuration-console.md` §5.3) :

| Geste | Classe | Ce qui le suit |
|---|---|---|
| poser `essential` (une entrée, ou `standard` → `essential`) | **resserre** | tout de suite, un reçu, une ligne sur Discord |
| `quiet` → `standard`, ou retirer une entrée `quiet` | **resserre** | idem |
| `essential` → `standard`, ou retirer une entrée `essential` | **relâche** | le nom tapé, la raison, le délai de 10 min (CFG1 Q2) |
| poser `quiet` (`standard` → `quiet`) | **relâche** | idem |
| `essential` → `quiet` | **relâche** | idem |
| changer `reason` seule | neutre | l'historique |
| élargir un motif `essential` (`vm-erp-prod-*` → `vm-erp-*`) | resserre | une ligne |
| élargir un motif `quiet` | **relâche** | la confirmation |
| déplacer `critical: true` vers `priorities:` (même `match`, `essential`) | **neutre** | le niveau de chaque VM est le même avant et après |

- **Monter resserre-t-il toujours ?** Pour la VM, oui : plus de réserve, un rang plus haut, plus de bruit,
  et, si Q4 retient l'option 1, une réserve de préparation qui ne peut que la retenir. Pour les autres, un
  `essential` de plus retire jusqu'à 0,50 $ aux ordinaires de tout le parc (§4.1). La note garde
  « resserre » (c'est déjà le choix de CFG4 pour `critical`), et propose d'annoncer fort un changement qui
  fait passer **5 VM ou plus** en `essential` d'un coup, comme un passage en masse en `human_only`
  (`configuration-console.md` §5.4, le même compte en VM).
- **Descendre relâche-t-il toujours ?** Oui : moins de budget, moins de bruit, un rang plus bas, et la
  réserve de préparation levée. Il se confirme.
- **La garde de CFG4** (constat 4) : un test échoue sur toute section de premier niveau acceptée par la
  lecture stricte qui n'est ni classée ni dans `_UNCLASSIFIED` ; `priorities` est classée par une fonction
  à elle (`_priorities`, à côté de `_critical`), et son mutant le prouve.
- **La classe se calcule par VM, sur le niveau rendu par `level_of`** (§5.3), jamais entrée par entrée : un
  motif `quiet` ajouté sous un motif `essential` qui couvre les mêmes VM ne baisse rien, il est neutre ; il
  relâche dès qu'il couvre une VM que rien de plus haut ne tient.
- **La vue « Relaxed »** (CFG3, `glorfindel/relaxed.py`) : chaque entrée `quiet` présente y a sa ligne —
  l'objet, « quiet: fewer pings for its low detections, 0.25 $ a day for its ordinaries », sa raison, ce
  qu'elle désigne aujourd'hui. Un `essential` retiré ne laisse aucune entrée : il n'y est pas, comme
  `critical` aujourd'hui (`configuration-console.md:546`) ; l'historique de CFG5 le dira.
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
  `--cyan`), jamais pleine. Infobulle : « Essential (priorities): its grave detections keep part of the
  model budget's reserve, and it is served first at equal gravity ».
- **`standard`** : rien. Le défaut ne fait pas de bruit.
- **`quiet`** : en minuscules, `--dim`. Infobulle : « Quiet (priorities): watched by every rule; fewer
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
notes · autonomy.assets[0] says `critical: true`: the former name of level: essential — move it to priorities:
Written in glorfindel-config.yaml for now; the console will write it through the signed queue (CFG5).
```
- **Les chiffres viennent d'une seule fonction** (`model_budget`), jamais recopiés (CRT1).
- « none » quand `priorities:` est vide et qu'aucun `critical: true` ne reste.
- Ce que désigne un motif, par la découverte : « N VMs today », ou « not found by the discovery today »
  (la forme de la vue « Relaxed »). La découverte ne décide jamais du niveau.

### 7.3 Le démarrage de la watch

```
Autonomy: default = human_only  (3 per-asset override(s))
Priorities: 2 essential (vm-db-prod, vm-erp-*) — their grave detections keep a 2.00 $ reserve;
            1 quiet (vm-dev-*); every other VM standard
  note: autonomy.assets[0] says `critical: true`, the former name of level: essential — move it to priorities:
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
  baisse jamais la part de budget de ses graves ni de ses ordinaires, ne la fait jamais passer plus tard
  dans la porte à gravité égale, ne retire jamais un ping, ne baisse jamais N.
- **PR3 — une grave reste grave.** `gravity()` ne lit pas le niveau ; une grave sur une VM `quiet` garde
  le plancher, son rang et son ping.
- **PR4 — le push ne baisse jamais un niveau.** Pour toute paire (config d'Imladris, config du poste), le
  niveau poussé de chaque `match` est au moins celui d'Imladris ; `quiet` ne vient que d'Imladris ;
  `HUMAN_ONLY=1` laisse les niveaux.
- **PR5 — les deux lecteurs s'accordent** : mêmes clés, mêmes niveaux, même verdict sur les mêmes configs
  (§5.5).
- **PR6 — la classe d'un changement suit le niveau** : monter resserre, descendre relâche, par VM ; toute
  section acceptée est classée (la garde du constat 4).
- **PR7 — `critical: true` vaut `essential`** : les tests de PRT2 rejoués, paramétrés sur les deux formes,
  donnent les mêmes réserves, les mêmes seaux, la même attente.
- **La machine à invariants** (`tests/unit/test_invariants.py`) : chaque VM du monde tire un niveau ; ses
  quinze propriétés doivent tenir quel que soit le niveau. Si Q4 retient l'option 1, une propriété de
  plus, l'oracle tiré du journal du faux Azure (A0) : **aucune écriture autonome sur le réseau d'une VM
  `essential` avant la confirmation de sa réserve**.

### 8.2 Les mutants

L'Orchestre donne les plages ; les lots en ont une trentaine, plus ceux de CRT1 (§10). Exemples, par lot :
- **PRI2** : un niveau inconnu accepté ; `critical: true` ignoré (la réserve perdue) ; la contradiction
  `critical: true` + `quiet` acceptée ; le plus bas l'emporte ; un motif ignoré ; `priorities` non classée
  (neutre) ; descendre classé « resserre » ; le push perd un `essential` d'Imladris ; le push pousse un
  `quiet` du poste ; les listes des deux lecteurs divergent.
- **CRT1** : la marque jamais posée ; un motif ignoré ; la réserve recopiée ou fausse ; la ligne de
  démarrage muette (sa fiche) ; `ESSENTIAL` en rouge.
- **PRI3** : la réserve `essential_service` jamais ajoutée ; ajoutée mais confirmée d'office ; une VM
  passée en `essential` reste autonome.
- **PRI4** : l'ordre ignore le niveau ; le niveau passe devant la gravité ; les ordinaires de `quiet` à
  `VM_USD` ; une grave de `quiet` sans plancher ; le dossier d'une VM `essential` dit « non composé ».
- **PRI5** : une carte d'une VM `essential` qui attend un humain sans ping ; une grave sur `quiet` sans
  ping ; une action seule sur `quiet` sans ping ; la gravité d'une carte montée par le niveau.
- **PRI6** : N non monté ; T monté avec N.

### 8.3 Ce qui se mesure au banc

La classe est du code déterministe : presque tout se prouve en tests. Le banc, une demi-séance avec PRI4 et
PRI5 (par Jonathan, sur une panne bénigne de Gothmog qui fait une détection grave, comme au 20/11) :
- **le push** lit les niveaux d'Imladris et les garde (`make imladris-push`, son rapport) ;
- **le démarrage** et la tuile disent les niveaux, sur Imladris et sur le téléphone ;
- **l'ordre** : deux détections de même gravité dans la même minute, une sur une VM `essential`, une sur
  une VM `standard` : la première décidée d'abord ;
- **Discord** : le ping d'une carte qui attend un humain sur la VM `essential`, l'absence de ping à
  l'ouverture d'un fil bas sur la VM `quiet` ;
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
   préparation « l'isoler coupe un service déclaré essentiel ». Tant qu'un humain ne l'a pas confirmé une
   fois, elle reste en `human_only` ; ensuite son mode décide, isolement compris.
2. Un plafond de l'objet, comme celui de la règle (RDW1) : sur `vm-db-prod`, une isolation autonome est
   ramenée à l'instantané et proposée sur la carte, quel que soit le mode ; le blocage d'une adresse et
   l'instantané restent au mode.
3. Rien : la classe ne touche pas l'autonomie ; l'opérateur pense lui-même à mettre `vm-db-prod` en
   `human_only`.

*Raison* : une seule décision, le mode, prise en sachant ce qu'elle coûte ; le rançongiciel sur
`vm-db-prod` garde un isolement seul si l'opérateur l'a voulu (l'option 2 le lui retire), et personne ne
découvre trop tard qu'une VM essentielle s'isolait seule (l'option 3).

**Q5 — Où s'écrit la classe dans le fichier ?** (§5.1)
1. **Une section à part, `priorities:` (`match`, `level`, `reason`) (recommandée).** On rend `vm-db-prod`
   essentielle sans toucher son mode.
2. Une clé `priority:` sur les entrées d'`autonomy.assets`, à la place de `critical`. Plus court, mais
   chaque VM classée doit recevoir un mode, et sous un défaut `non_disruptive` rendre `vm-db-prod`
   essentielle passerait par la confirmation d'un relâchement.

*Raison* : la classe et le mode sont deux décisions ; la forme d'aujourd'hui les lie (§1.4, constat 1).

**Q6 — Deux entrées couvrent une VM : laquelle l'emporte ?** (§5.3)
1. **Le niveau le plus haut, toujours (recommandée).** `vm-erp-*: essential` et `vm-erp-test: quiet` :
   `vm-erp-test` reste essentielle ; pour la descendre, on resserre le motif.
2. Comme le mode : l'entrée exacte, puis le motif le plus long ; à égalité, le plus haut. `vm-erp-test`
   devient quiet, une exemption.

*Raison* : une erreur d'écriture ne baisse jamais une VM qu'on croit essentielle ; c'est déjà la règle de
`critical`.

**Q7 — Que devient `critical: true` ?** (§5.4)
1. **Lu comme `essential`, une note invite à le déplacer, une contradiction est une erreur ; accepté
   jusqu'à la 1.0 (recommandée).** Une config d'aujourd'hui démarre telle quelle et garde sa réserve.
2. Refusé dès la release qui lit `priorities:` : une config d'aujourd'hui ne démarre plus (toutes les VM
   en `human_only`) tant qu'on ne l'a pas réécrite.
3. Gardé pour toujours comme un second nom.

*Raison* : aucune rupture pour qui l'a posé depuis la 0.6.7, et une seule forme à la 1.0.

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
1. **La gravité d'une carte ne change jamais ; `essential` pingue chaque carte qui attend un humain ;
   `quiet` ne pingue plus l'ouverture d'un fil pour une détection basse ; une grave et une action seule
   pinguent partout (recommandée).** Une force brute sur `vm-dev-01` ouvre son fil sans mention ; un
   `mode_hold` sur `vm-db-prod` pingue même dans un fil ouvert.
2. La gravité d'une carte monte d'un cran sur une VM essentielle. Plus visible, mais une force brute sur
   `vm-db-prod` deviendrait « critique » et prendrait la place des vraies compromissions dans la file.
3. Rien ne change aux notifications : la classe ne se voit qu'à l'écran.

*Raison* : le niveau dit l'objet, la gravité l'événement ; le bruit suit l'objet, la file suit
l'événement.

**Q10 — Ce qui part avant la 0.7 ?** (§10)
1. **En 0.6.x : la lecture et la reprise (PRI2), l'affichage (CRT1), la réserve de préparation (PRI3), la
   porte, le budget de `quiet` et le dossier (PRI4), les notifications (PRI5). En 0.7 : l'enquête (PRI6),
   avec ENQ5 mesuré, et PRT3 (recommandée).** La classification vit tout de suite, sur ce qui est codé.
2. Tout en 0.7, avec PRT3 : un seul passage, mais `critical` reste invisible et seul d'ici là.
3. En 0.6.x, la lecture et l'affichage seulement ; les effets en 0.7.

*Raison* : chaque effet de la 0.6.x touche du code qui existe (le budget, la porte, le dossier, le bot) ;
l'enquête attend sa propre mesure.

---

## 10. Les lots

En jours de travail effectif, à ±50 %, comme la feuille de route. Les mutants sont estimés ; l'Orchestre
donne les plages. Le découpage suit les recommandations ; une autre réponse à Q4, Q5 ou Q10 le change
(dit dans la colonne « Risques »).

| Lot | Session | Ce qu'il touche | Taille | Jalon | Risques | Mutants |
|---|---|---|---|---|---|---|
| **PRI2** — la lecture du format et la reprise de `critical` | Glorfindel (et le push, côté Imladris) | `priorities:` lue strictement (§5.2), `level_of` (§5.3) ; `critical: true` lu comme `essential`, la note, la contradiction refusée (§5.4) ; `is_critical` et `critical_count` sur `level_of`, les seaux gardés ; la classe de CFG4 (`_priorities`) et la garde des sections (constat 4) ; la ligne `quiet` de la vue « Relaxed » ; le push : sa lecture, jamais plus bas, `quiet` d'Imladris seul (§5.5) ; le test des deux lecteurs et le test des mêmes verdicts ; les mutants de PRT2 ré-ancrés ; la doc de PRT2 (`operations.md`, `raisonnement.md`, `fichiers-cles.md`, `configuration-console.md` §5.2) et le geste du retour arrière | 2,5 j | 0.6.x | un lecteur qui diverge : toutes les VM en `human_only` au push ; un retour arrière refusé tant que la section est là | ~10 |
| **CRT1** — l'affichage (repris) | Console, une ligne Glorfindel | la tuile, la page Config, le démarrage, le téléphone (§7) ; `/api/config` transmet le niveau de chaque entrée et de chaque VM, les notes, la réserve calculée par le budget | 1,5 j | 0.6.x, après PRI2 | une couleur d'alarme ; un chiffre recopié | M7771–M7780 (sa fiche, à refaire sur ce format) |
| **PRI3** — la réserve de préparation de `essential` (si Q4 = 1) | Glorfindel, une ligne Console | `essential_service` dans `readiness.py`, confirmée comme les autres ; le retour en `human_only` d'une VM autonome passée en `essential` ; la carte `readiness_hold` ; la propriété de la machine à invariants (§8.1) | 1 j | 0.6.x, après PRI2 | une VM essentielle retenue sans carte (personne ne sait pourquoi elle n'agit pas) | ~4 |
| **PRI4** — la porte, le budget de `quiet`, le dossier | Glorfindel | le rang à gravité égale (lire `room_in` d'abord, §4.2) ; les ordinaires de `quiet` au quart de `VM_USD` ; le dossier `critique` d'une VM `essential` (`dossier.py:232`) ; `docs/raisonnement.md` §2.5 et `dossier-isolation.md` mis à jour | 1,5 j | 0.6.x, après PRI2 | une porte qui ne sert pas dans un ordre aujourd'hui (un lot plus gros) ; une famine des `quiet` sous un flot d'`essential` | ~6 |
| **PRI5** — les notifications | Glorfindel (le bot) | le niveau sur la carte (`priority`) ; le ping de chaque carte qui attend un humain sur `essential` ; pas de ping à l'ouverture d'un fil bas sur `quiet` ; les graves et les actions seules pinguent partout (§4.4) ; la ligne de Discord d'un changement de niveau (§6) | 1 j | 0.6.x, après PRI2 | trop de pings sur un parc tout `essential` | ~4 |
| **PRI6** — l'enquête par niveau | Glorfindel | N = 6 pour `essential`, T inchangé, après la mesure d'ENQ5 (§4.3) ; la part de la décision dite à la porte | 0,5 j | 0.7 | deux appels de plus au-delà de la place des graves | ~2 |
| **PRT3** — la porte qui trie, branchée sur la classe | Glorfindel | la classe comme donnée du tri ; les contraintes du §4.2 (aucune exception large sur `essential`, rien d'automatique sur `quiet`, jamais le silence) | (sa fiche) | 0.7 | — | (sa fiche) |
| **PRI7** — retirer `critical` | Glorfindel | la clé refusée, la note devenue erreur, le push et sa doc | 0,5 j | 1.0 | une config jamais déplacée : dite depuis la 0.6.x | ~2 |

**Total** : environ 8 jours hors PRT3, une trentaine de mutants plus ceux de CRT1.

**L'ordre.** PRI2 d'abord : tout lit `level_of`. CRT1 ensuite, sur son format (sa fiche, écrite pour
`priority: true`, est à reprendre : les niveaux, la section, « Priorities », la marque `ESSENTIAL`). PRI3,
PRI4 et PRI5 en parallèle après PRI2. La demi-séance du banc (§8.3) après PRI4 et PRI5. PRI6 avec ENQ5
mesuré, PRT3 en 0.7. PRI7 à la 1.0.

**Si les réponses changent** : Q4 = 2 remplace PRI3 par un plafond de l'objet dans `decide` (1,5 j, et un
critère de la 1.0, « aucun constat haut ouvert sur le chemin d'isolation », à relire) ; Q4 = 3 supprime
PRI3 ; Q5 = 2 rend PRI2 plus court (1,5 j) et garde le constat 1 ; Q1 = 2 supprime ce que `quiet` touche
dans PRI2, PRI4 et PRI5 (environ 1 j de moins).

---

## 11. Les limites

- **La classe ne protège pas d'une config fausse.** Une VM essentielle oubliée dans `priorities:` est
  `standard` : rien ne le devine. La page Config montre ce qui est classé ; rien ne montre ce qui ne l'est
  pas, sauf la carte de l'infra, tuile par tuile.
- **Le compte de la réserve est par entrée, pas par VM** (§1.1) : un motif `essential` qui couvre dix VM
  apporte 0,50 $, comme une seule. La note le garde (la réserve reste bornée et lisible) ; un parc où
  beaucoup de VM sont essentielles verra le plafond de 2,50 $ tôt.
- **Une console compromise peut tout monter en `essential`.** C'est un resserrement, il s'applique ; il
  réduit les ordinaires du parc et multiplie les pings (une fatigue d'alerte). L'annonce forte au-delà de
  5 VM (§6) le rend visible ; elle ne l'empêche pas.
- **Le rang dans la porte** dépend de ce que la porte sait faire aujourd'hui (§4.2) : PRI4 le lit avant de
  promettre un ordre.
- **Le retour arrière** sous PRI2 demande un geste (§5.5) tant que le préflight ne lit pas la config par
  les deux images (MSUB6).
- **Les abonnements ajoutés** (MSUB3) : jusqu'à ce que MSUB3 indexe par (abonnement, motif), une entrée de
  `priorities:` vaut par le nom, comme le mode aujourd'hui ; un homonyme d'un autre abonnement prendrait le
  niveau. Pour `essential`, c'est un resserrement ; pour `quiet`, un relâchement hérité — la même limite
  que MSUB1 a relevée pour le mode (`watch-multi-abonnement.md` §1.6), fermée par le même lot.
- **Le chiffre de `quiet`** (0,25 $ par jour) est une proposition, à recaler sur la mesure (§8.3).
