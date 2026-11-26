# La classification des VM : des niveaux et leurs effets (PRI1, #1216) — conception

_Note de conception, sans code, 26/11. Décision de Jonathan, le 26/11 : **« une vraie classification »** —
plusieurs niveaux, chacun avec son effet ; une note d'abord. CRT1 (#1215), qui l'affichera, reprend
après elle. Statut : **conception tranchée** : Jonathan a répondu aux dix questions le 26/11 (§9), choisi
le format (`assets:`, §5) et **recadré la classe** : elle sert au coût et à l'ordre des files, jamais à la
détection ni à la remédiation (§0). Rien n'est codé, rien n'est appliqué._

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

**Le cadrage de Jonathan (26/11)** :
> « la classification sert juste à la gestion des coûts, c'est juste un ordre de priorité dans les
> files ; on ne doit en rien toucher au comportement associé pour la détection et la remédiation ».

**Le principe qui en suit : la classe d'une VM est une déclaration de l'opérateur, qui règle ce que
Glorfindel dépense pour elle et l'ordre où il la sert ; rien de ce qu'il détecte, lit ou dit.** Le code en
tire, de façon déterministe, une part du budget du modèle, un rang dans les files des appels au modèle, et
un affichage. Elle ne touche ni les règles, ni l'enquête, ni le dossier, ni les cartes, ni les
notifications, ni le mode, ni aucune garde (Q3). Monter d'un niveau resserre ; descendre relâche, et se
confirme (§6).

**Une exception, dite telle quelle : la réserve de `essential` quand le budget est serré.** La classe
change ce que Glorfindel **fait** par une seule voie, le verdict du budget, et seulement pour `essential`,
avec l'effet d'aujourd'hui (PRT2, `critical: true`) : à budget serré, une grave `essential` puise dans sa
part réservée et a le modèle, quand une grave `standard` part au chemin du code (un appel refusé faute de
budget ne passe pas par le modèle, `glorfindel/model_budget.py:419-425`). **`quiet` a le budget de
`standard`** (tranché le 26/11, §4.1) : il ne change jamais une remédiation.

- **Aujourd'hui, un seul oui/non** : `critical: true` sur une entrée d'`autonomy.assets` (PRT2, #1160).
  Il réserve aux graves de la VM une part du budget du modèle, et sa grave n'attend pas le refroidissement
  du fournisseur (§1.1). Rien d'autre ne le lit, hors de la classe d'un changement et du push vers
  Imladris (anciennement H0) (§1.2).
- **Trois axes, qui ne se remplacent pas** (§2.3) : la **zone** (`bench`, `twin`, `production` : ce qu'une
  expérience a le droit d'y faire, lue sur les tags), le **mode** (`human_only`, `non_disruptive` : ce que
  Glorfindel fait seul, la décision) et la **classe** (ce que la VM coûte et son rang dans les files).
- **Trois niveaux** (§3, Q1 et Q2 tranchées), des mots qui n'alarment pas : **`essential`** (une VM dont
  la perte arrête le métier ; le `critical: true` d'aujourd'hui), **`standard`** (le défaut, rien ne
  change) et **`quiet`** (une étiquette grise qui dit « cette VM compte peu » : l'affichage seul, le budget
  et le rang de `standard`). Aucun mot de la gravité des cartes (`critical`, `high`, `low`).
- **Ce qui reste** (§4, tableau au §4.8) : **(a)** la réserve et le budget du modèle — `essential` garde
  l'effet de PRT2, `standard` et `quiet` le même budget ; **(b)** l'ordre dans les files des appels au modèle — entre les graves qui attendent une
  place, `essential` d'abord ; **un ordre entre les VM que la porte n'a pas aujourd'hui** (la première VM
  qui réessaie passe), que PRI4 ajoute ; une grave n'est jamais affamée, les graves de `quiet` se rangent
  avec `standard`, et une basse n'attend jamais (au-delà de sa place, elle devient une carte) ; **(f)**
  l'affichage.
- **Ce qui sort, avec sa raison** (§4.3 à §4.5) : l'enquête plus profonde par niveau, le dossier
  « critique » par niveau, les notifications, et tout lien avec l'autonomie. Chacun toucherait ce que
  Glorfindel détecte, lit, dit ou fait. **La classe n'a aucun lien avec le mode** (Q4) : la combinaison est
  dite (`ESSENTIAL · NON_DISRUPTIVE` sur la tuile, une ligne sur la page Config).
- **Le format** (§5), **tranché par Jonathan le 26/11** (sa proposition, Q5) : **une seule section
  `assets:`**, qui remplace `autonomy:` — `default_mode`, `allow_destructive`, et une `list` d'entrées
  (`match`, `mode` facultatif, `priority` facultative, `reason`) ; la découverte reste sur sa source. Le
  mode facultatif règle le constat 1 (§1.4). **Chaque champ se résout par l'entrée exacte, puis par le
  motif le plus long** (Q6, la règle du mode, pas la recommandation de la note) : une exception précise
  est possible, et la descente qu'elle produit est retenue jusqu'à confirmation.
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
- **Un changement de config, retenu jusqu'à confirmation** (§6, décision de Jonathan du 26/11, pour tout le
  fichier) : quand la watch relit le fichier, une édition à la main comprise, ce qui resserre s'applique
  tout de suite et ce qui relâche est **retenu**, l'ancienne valeur gardée, jusqu'à ce qu'un humain le
  confirme. Le mécanisme vient avec CFG5 ; il remplace la décision CFG1 du 23/11 sur l'édition à la main
  (`configuration-console.md` §3.3).
- **L'affichage** (§7, pour CRT1) : `ESSENTIAL` en marque neutre, jamais rouge, à côté du mode ; rien pour
  `standard` ; `quiet` en gris ; une section « Priorities » dans la page Config ; une ligne au démarrage.
- **Ce qui ne change pas** : la détection, l'enquête, le dossier, les cartes, les notifications, le mode,
  les gardes ; ce que voit le modèle (la classe n'entre jamais dans son message) ; `human_only` par
  défaut ; la règle de production, les zones, les injecteurs.
- **Cinq lots** (§10), environ 8,5 jours : PRI2a (le format `assets:`, la lecture, la migration), PRI2b
  (le push, la garde de version), CRT1 (l'affichage, repris) et PRI4 (l'ordre entre les VM, pour les
  graves) en 0.6.x ; le branchement de PRT3 en 0.7 ; PRI7 (retirer l'ancien format) à la 1.0. PRI3, PRI5 et PRI6 sortent avec le cadrage.

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
  (`glorfindel/dossier_pass.py:19-22`, `:161-175`). **Avec le cadrage de Jonathan, le dossier ne lira
  pas la classe** (§4.3) : il garde la gravité de la détection, et la phrase de `dossier-isolation.md:992`
  « en attendant la criticité d'un objet » ne vaut plus pour lui.
- **Le raisonnement** (`docs/raisonnement.md:488`) : « la criticité de l'objet dans le tri de la porte
  revient à PRT3 ».
- **La leçon du projet** : « la sûreté ne se délègue jamais à la confiance du modèle (réversibilité de
  l'action × criticité de l'asset × mode `human_only` par défaut × alerting) ». La criticité y est un
  facteur ; elle n'y est jamais une estimation du modèle. Avec le cadrage, ce facteur reste dans les mains
  de l'opérateur, par le mode de chaque VM ; la classe ne le porte pas (§4.5).

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
- **Le fichier seul** (Q8, tranchée le 26/11). Un tag Azure (`eregion-priority`) irait bien au Terraform du client
  (`module-isolation-iac.md`), mais il s'écrit hors de la file de CFG1, par qui écrit la ressource : un tag
  baissé relâcherait sans confirmation. Si un jour il vient, il ne pourra que monter.
- **Le modèle ne la voit pas.** Elle n'entre ni dans `_build_user_message()`, ni dans `_SYSTEM_PROMPT`, ni
  dans les exemples : aucun lot de la note n'appelle le run de bout en bout (`CLAUDE.md`, « Conventions »).
  Un modèle qui la lirait pourrait en faire un raccourci (« VM essentielle, donc j'isole »).

### 2.2 Le coût et l'ordre, jamais la détection ni la remédiation

La classe règle ce que Glorfindel **dépense** pour une VM et **l'ordre** où il la sert ; elle ne règle
jamais ce qu'il **détecte, lit ou dit** (le cadrage de Jonathan, §0). **Ce qu'il fait** ne change que par
une voie, la réserve de `essential` à budget serré, avec l'effet d'aujourd'hui (§0, l'exception ; §4.1) ;
`standard` et `quiet` ont le même budget, donc le même verdict.

| La classe règle (le coût, l'ordre, l'affichage) | La classe ne touche jamais (la détection, la remédiation) |
|---|---|
| la part du budget du modèle (PRT2), et son attente pendant le refroidissement du fournisseur (l'existant) | les règles, la détection, la gravité d'une détection (`gravity`, `GRAVE_TTPS`) |
| le rang dans les files des appels au modèle, à gravité égale (PRT1, PRI4, PRT3) | l'enquête et son budget de lectures (ENQ), le dossier (DOS4) |
| l'affichage et l'ordre de la console | les cartes, leur gravité, les notifications, Discord, le webhook |
| | le mode d'autonomie, la décision (`resolve`), la préparation (L6) |
| | le seuil de confiance, la porte destructive, `allow_destructive`, les tirages (D-1), les planchers (B3a, SEC4a) |
| | le plafond de la règle (RDW1), la garde d'attribution (ATT1), `never_block`, le réseau du client (SEC2) |

**Plus vite, sans rien changer à la réponse.** Une grave d'une VM essentielle part plus tôt vers le modèle :
elle n'attend jamais l'argent ni le refroidissement du fournisseur (l'existant), et sa décision passera
d'abord dans la porte une fois l'ordre entre les VM ajouté (PRI4). Ce qui suit la décision est celui de
toute VM : les mêmes gardes, le même mode. Jamais un seuil de confiance réduit, des tirages en moins, un
plafond de règle levé (Q3).

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
  la classe      │ essential · standard · quiet   assets.list (priority)     │  ce que la VM coûte :
  (le coût)      │                                                           │  budget, rang des files
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
  réservée de `essential` ne joue que dans le réel. Le rang dans la porte
  et l'affichage jouent partout, pour que le banc les mesure (§8.3).
- **La classe et le mode ne se croisent pas** (Q4) : une VM `essential` en `non_disruptive` peut être
  isolée seule, comme toute VM de ce mode. La combinaison est dite à l'écran (§7), jamais corrigée par le
  code.

---

## 3. Les niveaux proposés

| Niveau | Pour quelles VM | Exemple | Ce qui change |
|---|---|---|---|
| **`essential`** | celles dont la perte arrête le métier, ou dont les données ne se reconstruisent pas | `vm-db-prod`, la base de l'ERP | la réserve du budget pour ses graves, le premier rang à gravité égale |
| **`standard`** | toutes les autres, par défaut | `vm-web-01`, un frontal parmi trois | rien : le comportement d'aujourd'hui |
| **`quiet`** | celles dont les détections basses ne valent pas beaucoup d'appels au modèle | `vm-dev-01`, recréée chaque nuit | l'affichage seul : une étiquette grise ; le budget et le rang de `standard` |

- **Trois niveaux, pas plus** (Q1, tranchée). `essential` a un effet propre (sa réserve) ; `quiet` n'a
  aujourd'hui que l'affichage (le budget de `quiet`, tranché le 26/11, §4.1). L'ordre se lit sans légende. Un
  quatrième (`important`) n'aurait que des demi-effets : à ajouter le jour où un besoin le demande, sans
  casser le format.
- **`quiet` ne retire rien de la surveillance.** Toutes ses règles tournent, ses cartes et ses
  notifications sont celles de toute VM ; seul l'affichage change : son budget et son rang sont ceux de
  `standard`. Une grave sur une VM `quiet` (un rançongiciel, une exfiltration) est traitée comme
  partout. Ce n'est pas une exclusion (`exceptions`), qui retire la VM des règles (CFG2).
- **Les mots** (Q2, tranchée) : `essential` et `quiet` disent un objet, pas un événement ; aucun n'est un mot de
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
- **`quiet` : le budget de `standard`, tranché par Jonathan le 26/11** (la question ouverte au second
  tour de relecture, « Le même budget que standard », la recommandation). La note proposait un quart de
  `VM_USD` pour ses ordinaires ; au-delà, une ordinaire serait devenue une carte `budget`, sans action seule
  (`model_budget.py:419-425`), et une basse d'une VM `quiet` en `non_disruptive` aurait perdu son action
  seule plus tôt que sur une VM `standard`. **Raison : le cadrage de Jonathan, tenu à la lettre** — la
  classe ne touche pas la remédiation. Le quart est retiré ; `quiet` ne change jamais une remédiation, et
  n'est plus qu'un niveau d'affichage.
- **À budget serré, `essential`** : une grave `essential` puise dans la part réservée et a le modèle ; une
  grave `standard` peut partir au chemin du code au même moment. C'est l'effet de PRT2 aujourd'hui, que la
  classe reprend sans le changer.
- **Ce que monter coûte aux autres.** La réserve se prend sur l'enveloppe du réel : chaque entrée
  `essential` retire jusqu'à 0,50 $ à ce que partagent les ordinaires de toutes les VM (`real/rest`, 4 $ sans
  entrée, 2,50 $ avec trois). Un motif `essential` très large (`*`) ne protège donc rien de plus et réduit
  les ordinaires de tout le parc : la note propose de le dire (§6).

### 4.2 (b) L'ordre dans les files des appels au modèle

- **Ce que fait le code aujourd'hui.** La file est celle de chaque VM, rangée par gravité puis par arrivée
  (`decision_queue.py:256-280`). **Entre les VM, aucun ordre** : une décision que le plafond par minute
  retient reçoit le délai avant la prochaine place (`room_in`, `decision_queue.py:419-426`) et réessaie
  (`:707-709`) ; la première VM qui réessaie passe. Le rang qui suit **n'existe donc pas** : c'est un ordre
  à ajouter entre les VM, que PRI4 porte (§10).
- **L'ordre proposé** : la gravité d'abord, toujours (`gravity` : la classe critique, puis grave, puis
  basse, `decision_queue.py:129-138`) ; à gravité égale, le niveau ; puis l'arrivée.
  - **pour les graves et les critiques** : `essential`, puis `standard` et `quiet` **ensemble**. Une grave
    sur une VM `quiet` se range comme sur une VM `standard` : `quiet` ne baisse jamais une grave ;
  - **les basses n'attendent jamais** : au-delà de la place des basses, une basse devient une carte, tout
    de suite, quel que soit son niveau (`decision_queue.py:27-31`). Il n'y a pas de file de basses entre
    les VM, donc pas de rang à leur donner ;
  - la classe ne fait jamais passer une détection basse d'une VM `essential` devant une grave d'une VM
    `standard` : un rançongiciel sur `vm-dev-01` passe avant une force brute sur `vm-db-prod`.
- **La forme, à fixer par PRI4** : un registre des **graves et des critiques** qui attendent une place,
  rangé par cet ordre ; quand une place revient, la première du registre la prend, et les autres
  réessaient après elle. Sans ce registre, le niveau ne change rien au rang, et la note ne le promet pas.
- **L'admission** : la place des graves (quatre appels par minute) ne change pas ; aucune place n'est
  réservée à `essential` (une place réservée serait prise aux autres graves).
- **L'attente** : pendant le refroidissement du fournisseur, une grave `essential` part tout de suite par
  le chemin du code (`_slowed`, l'existant) ; une grave `standard` ou `quiet` attend, jusqu'à la deuxième
  limite (`_strikes >= 2`), comme aujourd'hui.
- **Le dédoublonnage** (une décision par VM, règle, gravité et source en cinq minutes) ne change pas : le
  raccourcir pour `essential` multiplierait les appels sans preuve de plus.
- **`quiet`** : aucun rang à part. Ses basses, comme toutes, n'attendent pas ; ses graves et ses critiques
  se rangent avec celles de `standard`.
- **PRT3**, en 0.7 : la classe y entre **comme un ordre et un budget seulement**. Elle n'y est jamais une
  raison d'écarter ou de garder une détection : les exceptions de la porte (proposées, datées, cassées par
  un saut de volume ou une technique grave) ne lisent pas la classe, et une détection écartée reste dite, à
  tous les niveaux.

### 4.3 (c) Sort : l'enquête et le dossier par niveau

La note proposait une enquête plus profonde pour `essential` (N = 6 lectures au lieu de 4, en 0.7) et un
dossier toujours « critique » pour une VM `essential`. **Les deux sortent avec le cadrage** : ils
changeraient ce que Glorfindel lit avant de décider, donc la détection et la remédiation.
- **L'enquête** garde un seul budget pour toutes les VM (N = 4, T = 30 s, `glorfindel/enquiry/loop.py:63`)
  et ses lectures obligatoires pour les techniques graves (`enquete-raisonnee.md` §5.2). Il n'y a plus de
  PRI6.
- **Le dossier** garde la gravité de la détection (`_critical(signal)`, `glorfindel/dossier.py:232-239`) ;
  la phrase de `dossier-isolation.md:992` « en attendant la criticité d'un objet » ne vaut plus pour lui.

### 4.4 (d) Sort : les cartes et les notifications

- **La gravité d'une carte ne change jamais avec la classe** : elle dit l'événement, la classe l'objet.
- **Les notifications ne bougent pas** (Q9, tranchée) : ni Discord, ni le webhook, ni TO JUDGE ne lisent
  la classe. Il n'y a plus de PRI5. La note proposait un ping de plus pour `essential` et un de moins pour
  `quiet` : c'est ce que Glorfindel dit, donc hors du cadrage.
- **Un trou d'aujourd'hui, sans lien avec la classe** : le rôle `DISCORD_PING_ROLE` n'est mentionné qu'à
  la création d'un fil (`glorfindel/bot.py:1589-1596`) et sur la carte d'une action prise seule
  (`bot.py:1673-1678`, JUG1) ; une carte postée dans un fil déjà ouvert ne mentionne pas, même grave. Une
  force brute qui ouvre le fil de `vm-web-01` mentionne le rôle, un rançongiciel qui suit dans le même
  fil, non. La règle « la première grave d'un fil mentionne toujours » peut faire un lot à part (§11).

### 4.5 (e) Sort : l'autonomie

**Aucun lien entre la classe et le mode** (Q4, tranchée). Jonathan a demandé pourquoi la classe toucherait
l'autonomie ; la question, reformulée en séance, a changé de recommandation. Le mode reste la seule
décision ; la classe ne bloque ni n'ouvre rien. La note proposait une réserve de préparation
`essential_service`, qui aurait tenu une VM essentielle en `human_only` jusqu'à une confirmation : elle
sort, et PRI3 avec elle.
- **La combinaison est dite**, jamais corrigée : la tuile montre `ESSENTIAL · NON_DISRUPTIVE` (§7.1), et la
  page Config dit en une ligne quelles VM essentielles peuvent être isolées seules : « vm-db-prod may be
  isolated on its own (non_disruptive): its service stops while it is isolated » (§7.2).
- **Les deux sens restent ceux du mode** : isoler `vm-db-prod` coupe l'ERP, un rançongiciel dessus est
  pire ; c'est au mode de chaque VM de les peser, et à l'opérateur de le choisir en le voyant.
- `quiet` ne touche pas l'autonomie non plus. Le passage en masse en `human_only` (le geste d'urgence) ne
  lit pas la classe.

### 4.6 (f) La console

- **La carte de l'infra** : la marque du niveau sur la tuile (§7.1) ; dans un groupe (GRP1), les tuiles
  `essential` d'abord, puis par nom ; `quiet` à sa place, plus discrète.
- **La page Config** : une section « Priorities » (§7.2).
- **TO JUDGE** et le fil : l'ordre ne change pas ; la carte montre le niveau.
- **La combinaison avec le mode** : `ESSENTIAL · NON_DISRUPTIVE` sur la tuile, et la ligne des VM
  essentielles qui peuvent être isolées seules sur la page Config (§4.5).
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
- **La détection et la remédiation** (§2.2) : les règles, l'enquête, le dossier, les cartes, les
  notifications, le mode, les gardes de `decide`, `allow_destructive`, `delete`/`wipe` jamais autonomes.
- **Les exclusions** (`exceptions`) : une VM exclue d'une règle l'est à tous les niveaux ; `quiet` n'exclut
  rien.
- **Plusieurs abonnements** (MSUB3) : une entrée d'`assets.list` sans clé `subscription` ne vaut que pour
  l'abonnement de la watch, comme une entrée d'autonomie (« rien n'est hérité »,
  `watch-multi-abonnement.md` §4.3) ; MSUB3 indexe la classe par (abonnement, motif), comme le mode.

### 4.8 Le tableau, niveau × axe

| Axe | `essential` | `standard` (défaut) | `quiet` | Quand |
|---|---|---|---|---|
| **(a) la réserve et le budget du modèle** | +0,50 $ par entrée, jusqu'à 2,50 $ ; la part au-dessus du plancher pour ses graves seules ; une grave n'attend jamais l'argent ni le refroidissement du fournisseur | le plancher de 1 $ ; ses ordinaires au plus 1 $ par jour | celui de `standard` (tranché le 26/11) | `essential` : l'existant |
| **(b) l'ordre dans les files**, entre les graves qui attendent une place, que la porte n'a pas aujourd'hui | d'abord, à gravité égale | ses graves avec celles de `quiet` | ses graves avec celles de `standard` | 0.6.x (PRI4) ; PRT3 en 0.7 ; les basses n'attendent jamais |
| **(a) le verdict du budget épuisé** (la seule voie qui change ce que Glorfindel fait) | sa grave a le modèle tant que la part réservée tient | l'existant : une ordinaire en carte, une grave au chemin du code | celui de `standard` | `essential` : l'existant |
| **(f) l'affichage** | `ESSENTIAL`, neutre, à côté du mode ; en tête du groupe | rien | `quiet`, en gris | 0.6.x (CRT1) |
| **Sorti : (c) l'enquête, le dossier** | rien | rien | rien | — (ils changeraient ce que Glorfindel lit) |
| **Sorti : (d) les cartes, les notifications** | rien | rien | rien | — (ce que Glorfindel dit) |
| **Sorti : (e) l'autonomie** | rien : la combinaison dite | rien | rien | — (ce que Glorfindel fait, Q4) |
| **(g) la zone, les injecteurs, le modèle, les gardes** | rien | rien | rien | — |

Une grave n'est jamais affamée : la gravité passe toujours avant le niveau, et les graves de `quiet` se
rangent avec celles de `standard`.

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

**Le format retenu par Jonathan, le 26/11, est C** (Q5, §9). La suite du §5 le décrit.
- **Ce qu'il règle** : le constat 1 (§1.4). Le mode devient facultatif sur une entrée : on classe une VM
  sans lui écrire de mode, donc sans « relâche » à confirmer. Une VM se lit à un seul endroit.
- **Ce qu'il garde** : deux axes, deux champs. Le mode reste la décision, la priorité le coût et l'ordre ; une
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
- **`priority: standard`** est un niveau comme les autres. Sous la règle de Q6 (l'entrée exacte, puis le
  motif le plus long), une entrée exacte `vm-erp-qa: standard` sous `vm-erp-*: essential` fait
  **descendre** la VM : c'est un relâchement, retenu jusqu'à confirmation (§6).
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

**Tranché par Jonathan le 26/11 (Q6) : chaque champ se résout par l'entrée exacte, puis par le motif le
plus long**, sur les **seules entrées qui le portent**. Ce n'est pas la recommandation de la note, qui
voulait le niveau le plus haut pour la priorité. Sa raison : une exception précise doit être possible, et
la descente qu'elle produit est protégée par la confirmation (§6).

- **Le mode : la règle d'aujourd'hui**, telle que `AutonomyConfig.resolve` la code
  (`glorfindel/config.py:390-412`) :
  1. le nom de la VM en minuscules ; les entrées **exactes** (leur `match` en minuscules égal au nom) :
     s'il y en a, la plus prudente d'entre elles (`_most_prudent`, `config.py:354-355`) ;
  2. sinon, les entrées dont le motif couvre le nom (`fnmatchcase` sur les deux en minuscules, AUC) : le
     motif **le plus long** (en caractères) ; à égalité, la plus prudente ;
  3. sinon, `default_mode`.

  **Une entrée sans mode n'y prend jamais part** : une entrée exacte `vm-db-prod` qui ne porte que
  `priority: essential` ne fait pas écran à un motif `vm-*: non_disruptive`. Sans cette règle, classer
  une VM changerait son mode : le défaut que C vient fermer.
- **La priorité : la même règle**, sur les entrées qui portent une priorité : l'entrée exacte, puis le
  motif le plus long, puis `standard`. **À égalité** (deux entrées exactes que seule la casse distingue,
  ou deux motifs aussi longs), la note propose **le plus haut** : le côté qui ne baisse pas, comme le mode
  prend le plus prudent. Une entrée sans priorité n'y prend jamais part.
- **`level_of` remplace `is_critical`** (§1.1), qui prenait toute entrée critique, exacte ou par motif :
  sous la règle tranchée, une entrée exacte `quiet` sous un motif `essential` descend la VM. La migration
  d'un ancien fichier n'en crée aucune (l'ancien format n'a pas de `quiet`) : `critical: true` y garde le
  même effet (§5.4).
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
    priorité est `essential` (son entrée exacte n'en porte pas : le motif) ;
  - `vm-erp-prod-01` : `human_only` (aucune entrée ne lui donne de mode : `default_mode`) et `essential`
    (le motif) ;
  - `vm-erp-qa` : `human_only` et **`quiet`** : son entrée exacte l'emporte sur le motif, une exemption
    voulue. Écrite dans un fichier où `vm-erp-qa` était `essential`, cette entrée descend la VM : CFG4 la
    classe « relâche », et la watch la **retient jusqu'à confirmation** (§6).

### 5.4 L'ancien format : `autonomy:` et `critical: true`

Tranché (Q7, le 26/11), dans la release qui lit `assets:` (PRI2) :
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
  règle en changeant les deux lecteurs **dans la même release** (PRI2a et PRI2b), tenus par le test, et par la garde de
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
  - **toute priorité du poste qui baisserait le niveau qu'Imladris donne à un nom n'est pas poussée**, et
    le rapport le dit (« lowers vm-erp-qa on Imladris: not pushed »). Le push compare, pour chaque nom
    et chaque motif cité dans l'une des deux configs, le niveau que `level_of` lui rend sur Imladris et
    dans la config qu'il pousserait, motifs compris ; une entrée du poste qui en fait descendre un est
    retirée. Un `quiet` du poste, un `standard` exact sous un motif `essential` d'Imladris, un motif plus
    long qui cède : même règle. Une descente se fait sur Imladris, où la confirmation la retiendra
    (CFG5) ;
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
  que régler le coût et l'ordre, et le geste d'urgence reste celui des modes.

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

**Ce que PRI2b a choisi** (#1225 ; `infra/glorfindel-host/host_config.py`,
`tests/unit/test_host_config_assets.py`) :
- **la source de la release** : le label `org.opencontainers.image.version` de **chaque conteneur qui
  monte la config** (`docker-compose.yml` : la watch, la console, le bot, l'exécuteur de restore), lu par
  `docker inspect` sur la connexion du push — le label que lit le CD (`deployed()`), sur ce qui tourne.
  Écarté : l'état du CD (`~/.eregion-cd/state.json`), qui ne voit pas un déploiement à la main et dit ce
  qui a été déployé, pas ce qui tourne. `assets:` n'est écrit que si la watch est lue et que **tous** sont
  à `ASSETS_SINCE` (`v0.6.10`) ou après ; un conteneur en retard, un commit déployé à la main (sa
  référence n'est pas une version), aucun label : l'ancien format. Le seuil est tenu au CHANGELOG (la
  première release qui nomme PRI2a, avec PRI2b). La release est relue juste avant le `scp`, comme la
  config : changée entre les deux lectures, rien n'est envoyé ;
- **une config d'Imladris en `assets:` face à une release qui ne le lit pas, ou illisible** (un
  `compose down`, un `docker inspect` raté, un hoquet ssh) : si sa watch la lirait sur une release qui lit
  `assets:`, **ses niveaux sont gardés**, écrits `critical: true` par la conversion, **jamais ses modes**
  (`human_only`) : une release d'avant la refusait déjà (toutes les VM en `human_only`), et une release
  qui la lit garde ses `essential`. Ses `quiet` tombent (l'ancien format n'en a pas : un niveau relevé).
  La relecture de PRI2b l'a mesuré : avant, `vm-db: non_disruptive + essential` sur Imladris et une
  release illisible donnaient `autonomy: assets: []`, vm-db en `standard`, sans rien dire. Une config
  d'Imladris refusée pour une autre raison ne garde rien, et **le rapport dit chaque `essential` perdu**
  (ou gardé par un `essential` du poste) ;
- **un conteneur arrêté garde son label** : seul un conteneur retiré n'est pas lu. Un conteneur resté d'une
  vieille release (un `eregion-restore` jamais recréé) fait écrire l'ancien format jusqu'à son retrait, et
  le rapport le nomme ;
- **un `standard` du poste sur un nom qu'Imladris ne connaît pas est poussé** (il ne baisse rien). Il
  pourrait masquer un motif `essential` posé plus tard à la main sur Imladris : le push suivant refuserait
  alors ce même `standard` comme une baisse, et le dirait ; l'entrée déjà poussée, elle, reste sur Imladris
  jusqu'à ce qu'on la retire là-bas ;
- **le côté sûr de la note, appliqué** : un motif du poste en `standard` n'est jamais poussé. La
  comparaison nom par nom ne le voit pas toujours : `vm-??x: standard`, plus long que `vm-1*: essential`
  d'Imladris, prendrait `vm-1ax`, qu'aucune des deux configs ne nomme, et le motif lu comme un nom ne
  descend pas (le test le montre). Un `quiet` du poste non plus, même sous un motif `quiet` d'Imladris où
  il ne baisserait rien : il y garderait la VM quand Imladris relève le motif ;
- **les niveaux d'Imladris, tous gardés** : ses motifs et ses `quiet` compris (un push qui les retirerait
  relèverait le niveau, mais effacerait ce que Jonathan a posé à la main) ; deux entrées du même nom à
  l'ancien format : le mode le plus prudent, le niveau le plus haut, comme Imladris les lit ;
- **une config du poste que la watch refuserait, sous `HUMAN_ONLY=1`** : le geste n'est pas bloqué ;
  aucune entrée du poste n'est portée, et c'est dit. Un fichier du poste absent, vide, illisible ou qui
  n'est pas une table YAML arrête toujours le push, `HUMAN_ONLY=1` compris : une config vide poussée
  retirerait à Imladris ses backends, ses exceptions et son isolation ;
- **le retour arrière** (§5.6) : par le push, `make imladris-push IMLADRIS_CONFIG_FORMAT=autonomy` (sur la
  ligne de commande seulement : venu de l'environnement, refusé, comme `REF` et `ROLLBACK`), pendant
  qu'Imladris tourne encore une release qui lit `assets:` ; la conversion (`to_autonomy`) est tenue égale à
  `glorfindel config migrate --to autonomy` par une propriété ;
- **le rapport** se lit sur la config écrite, comme la watch d'Imladris la lira, jamais sur ce que le
  push voulait ; en anglais (ENG1).

Ce que la table du §10 range aussi sous PRI2b et que ce lot ne fait pas : la watch qui dit un
`essential` perdu hors de la file (le poste d'avant PRI2b, ci-dessus) ; il reste à prendre.

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

**Un changement de config, retenu jusqu'à confirmation** (décision de Jonathan du 26/11, pour **tout le
fichier**, pas seulement la classe ; écrite dans `configuration-console.md` §3.3, où elle remplace la
décision CFG1 du 23/11 sur l'édition à la main) :
- quand la watch relit le fichier, **y compris après une édition à la main**, elle le compare avec la
  configuration appliquée ;
- ce qui **resserre** s'applique tout de suite ;
- ce qui **relâche** (une priorité qui descend, un mode plus hardi, une exclusion, tout ce que
  `config_class.py` classe « relâche ») est **retenu** : l'ancienne valeur reste appliquée, et une demande
  à confirmer s'ouvre — dans la console, par la CLI, et sur Discord quand le bot agira par la file signée ;
- le mécanisme se construit avec **CFG5** (l'historique, les demandes en attente, `applied.json`). **D'ici
  là**, une priorité descendue à la main s'applique à la relecture, comme toute édition à la main
  aujourd'hui : le risque est faible, puisque la classe ne touche ni la détection ni la remédiation (§0).

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
| poser `quiet` (`standard` → `quiet`) | **relâche**, par prudence : sans effet sur la défense aujourd'hui (§4.1), `quiet` pourra en recevoir un sans changer le format | idem |
| `essential` → `quiet` | **relâche** | idem |
| changer `reason` seule | neutre | l'historique |
| changer le texte d'un motif (`vm-erp-prod-*` → `vm-erp-*`), quel que soit son niveau | **relâche, proposé** : sous la règle du motif le plus long, un motif `essential` élargi peut céder à un motif plus long d'un autre niveau (`vm-erp-prod-db`, tenu par `vm-erp-prod-*: essential`, passe à `vm-erp-*-db: quiet` quand le premier devient `vm-erp-*`). CFG4 calcule sans la découverte et ne voit pas cette VM : il classe donc tout changement du texte d'un motif « relâche », le côté sûr | la confirmation |
| élargir un motif `quiet` | **relâche** | la confirmation |
| **passer de l'ancien format au nouveau** (`autonomy:` → `assets:`, `critical: true` → `priority: essential`), à valeurs égales | **neutre** : le mode et le niveau de chaque nom sont les mêmes avant et après | l'historique |
| une migration qui fusionne des doublons | ce qu'elle change : rien, puisque le mode gardé est celui que l'ancien format donnait (AUC) | idem |

- **Monter resserre-t-il toujours ?** Pour la VM, oui : plus de réserve, un rang plus haut. Pour les autres, un
  `essential` de plus retire jusqu'à 0,50 $ aux ordinaires de tout le parc (§4.1). La note garde
  « resserre » (c'est déjà le choix de CFG4 pour `critical`), et propose d'annoncer fort un changement qui
  fait passer **5 VM ou plus** en `essential` d'un coup, comme un passage en masse en `human_only`
  (`configuration-console.md` §5.4, le même compte en VM).
- **Descendre relâche-t-il toujours ?** Depuis `essential` : moins de réserve, un rang plus bas pour ses graves.
  De `standard` à `quiet` : aucun effet aujourd'hui, classé « relâche » par prudence (la ligne du tableau
  ci-dessus), pour le jour où `quiet` recevrait un effet. Dans les deux cas, il se confirme, et il est
  retenu jusque-là (ci-dessus).
- **La garde de CFG4** (constat 4) : un test échoue sur toute section de premier niveau acceptée par la
  lecture stricte qui n'est ni classée ni dans `_UNCLASSIFIED` ; `assets` est classée (son mode par
  `_autonomy`, sur le modèle ; sa priorité par une fonction à elle ; `allow_destructive`, toujours
  « relâche » quand il change), et son mutant le prouve. **`allow_destructive` se lit sur le modèle** :
  aujourd'hui, `_others` le compare sur le texte brut, à son ancien chemin (`config_class.py:149-150`,
  `autonomy.allow_destructive`) ; PRI2 le compare sur le modèle lu, sinon la migration, qui le déplace
  sous `assets:`, serait classée « relâche ».
- **La limite de CFG4, sans la découverte** : la classe se calcule sur les noms et les motifs cités, pas
  sur les VM. Un changement de motif peut changer le niveau d'une VM qu'aucun texte ne nomme (la ligne
  du tableau) ; d'où la règle prudente sur le texte des motifs.
- **La classe du niveau se calcule sur `level_of`** (§5.3), jamais entrée par entrée. **PRI2 remplace
  `_critical`** (`config_class.py:110-117`) : il compare les entrées qui disent `critical: true`, et
  classerait la migration « relâche » (l'entrée critique disparaît, `:116-117`), alors qu'aucune VM ne
  change de niveau. À sa place, une classe calculée par nom : pour chaque nom ou motif cité dans l'un des
  deux fichiers, le niveau que `level_of` lui rend avant et après. **La migration neutre a son test**, sur
  un fichier qui mêle modes, motifs, doublons et `critical: true`, et son mutant (l'ancienne `_critical`
  gardée à côté). Sous la règle de Q6, un motif `quiet` plus long qu'un motif `essential` qui le couvre
  descend les VM qu'il nomme : il relâche ; un motif `quiet` plus court, sous un motif `essential` plus
  long, ne change rien pour celles qu'il tient : il est neutre pour elles.
- **La vue « Relaxed »** (CFG3, `glorfindel/relaxed.py`) : chaque entrée `quiet` présente y a sa ligne —
  l'objet, « quiet: shown grey, no effect on the defence today », sa raison, ce
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
│ vm-db-prod   [ESSENTIAL · NON_DISRUPTIVE]                    ● online     │
│   DETECT ✓   PROTECT ✓   RECOVER ✓                                        │
│ vm-web-01    non_disruptive                                  ● online     │
│   DETECT ✓   PROTECT ✓   RECOVER ✓                                        │
│ vm-dev-01    quiet · human_only                              ● online     │
│   DETECT ✓   PROTECT ✓   RECOVER –                                        │
└───────────────────────────────────────────────────────────────────────────┘
```
- **`ESSENTIAL`** : une marque collée au mode, en capitales, entourée d'un trait fin (`--blue` ou
  `--cyan`), jamais pleine : `ESSENTIAL · NON_DISRUPTIVE`, `ESSENTIAL · HUMAN_ONLY`. La combinaison se
  lit d'un coup d'œil (Q4) ; le code ne la corrige jamais. Infobulle : « Essential (priority): its grave
  detections keep part of the model budget's reserve, and its calls to the model are served first at
  equal gravity. It changes nothing to what Glorfindel detects; what it does changes only when the
  model budget is tight, through this reserve, as today ».
- **`standard`** : rien. Le défaut ne fait pas de bruit.
- **`quiet`** : en minuscules, `--dim`. Infobulle : « Quiet (priority): this VM matters little to you. A
  label only: Glorfindel watches, decides and spends on it as on any standard VM ».
- **L'ordre** : dans un groupe, `essential` d'abord, puis par nom.
- **Une carte** (TO JUDGE, le fil) porte la même marque à côté du nom de la VM ; sa gravité reste la sienne.

### 7.2 La page Config

```
PRIORITIES                                                              ⚙ Config ▸ Priorities
essential · 2 entries · graves' reserve 2.00 $ (1.00 $ floor + 1.00 $ for these VMs)
  vm-db-prod      essential   « the ERP database »               1 VM today
  vm-erp-*        essential   (no reason)                        3 VMs today
quiet · 1 entry · a label only: watched, decided and budgeted as standard
  vm-dev-*        quiet       « recreated each night »           4 VMs today
standard · every other VM (the default)
isolated on their own · vm-db-prod may be isolated on its own (non_disruptive): its service stops while it is isolated
notes · autonomy: is the former format of assets: — migrate it (glorfindel config migrate); autonomy.assets[0]
        says `critical: true`, the former name of priority: essential
Written in glorfindel-config.yaml for now; the console will write it through the signed queue (CFG5).
```
- **Les chiffres viennent d'une seule fonction** (`model_budget`), jamais recopiés (CRT1).
- **La ligne des VM essentielles qui peuvent être isolées seules** (Q4) : une par VM `essential` dont le
  mode effectif est `non_disruptive` ; « none » sinon. Elle dit, elle ne retient rien.
- **Une descente retenue** (CFG5, §6) : une priorité descendue en attente de confirmation se lit dans la
  section, avec la valeur appliquée et la valeur demandée.
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
ESSENTIAL · NON_DISRUPTIVE
```
La section « Priorities » de la page Config se lit en une colonne : le niveau, puis chaque entrée sur deux
lignes (le motif et sa raison ; ce qu'il désigne).

---

## 8. Les preuves

### 8.1 Les invariants à ajouter

- **PR1 — la classe ne touche ni la détection ni la remédiation, à verdict du budget égal.** Trois
  preuves :
  - **une garde de structure** : `level_of` (et l'ancien `is_critical`) n'est lu que par une liste fermée
    de modules — le budget du modèle, la porte des appels (l'ordre), la classe d'un changement, la vue
    « Relaxed », la console, le démarrage. (Le push n'y est pas : `host_config.py` n'importe rien de
    Glorfindel, il a sa propre lecture, tenue égale par PR5.) Un lecteur de plus (l'enquête, le dossier,
    le bot, `decide`, la préparation, le RulePoller) fait échouer le test, comme `test_provider_boundary.py`.
    **La garde interdit aussi à `decide` et au bot de lire un champ `priority` porté par les données** (le
    signal, la carte, l'état) : la classe ne peut pas y entrer par un autre chemin ;
  - **une propriété** (Hypothesis) : pour une même détection, un même fichier **et un même verdict du
    budget**, changer le seul niveau de la VM ne change ni ce que les gardes de `decide` laissent partir
    seul, ni la carte, ni sa gravité, ni ce que le bot poste ; seuls l'ordre des appels et le seau du
    budget changent ;
  - **une propriété à part, sur le verdict du budget** : pour un même état du compte, le niveau ne change
    que les seaux d'une décision (`_keys`) ; le verdict (`model`, `card`, `code`, `wait`) ne diffère d'un
    niveau à l'autre que pour `essential`, quand sa part réservée tient là où un autre seau est épuisé,
    et le verdict rendu est alors celui d'aujourd'hui (PRT2). **Pour `quiet` et `standard`, le verdict du
    budget est le même**, à tout état du compte.
- **PR2 — monter ne retire rien à la VM, dans le coût et l'ordre.** Passer de `quiet` à `standard` à
  `essential` ne baisse jamais la part de budget de ses graves ni de ses ordinaires ; une fois l'ordre de
  PRI4 en place, ne fait jamais passer ses graves plus tard dans les files. **De `quiet` à `standard`,
  rien ne change** hors de l'affichage : le même budget, le même rang, le même verdict.
- **PR3 — une grave n'est jamais affamée.** `gravity()` ne lit pas le niveau ; une grave passe avant toute
  basse, quel que soit le niveau des deux VM ; une grave sur une VM `quiet` garde le plancher et le rang
  d'une grave de `standard`.
- **PR4 — le push ne baisse jamais un niveau, nom par nom.** Pour toute paire (config d'Imladris, config
  du poste) tirée au hasard, et pour chaque nom et chaque motif cité dans l'une des deux, le niveau que
  `level_of` rend dans la config poussée est au moins celui qu'il rend sur Imladris, motifs compris ;
  `HUMAN_ONLY=1` laisse les niveaux.
- **PR5 — les deux lecteurs s'accordent** : mêmes clés, mêmes modes, mêmes niveaux, même verdict sur les
  mêmes configs, aux deux formats (§5.5).
- **PR6 — la classe d'un changement suit le niveau** : monter resserre, descendre relâche, par nom ; toute
  section acceptée est classée (la garde du constat 4). Avec CFG5 : ce qui relâche est retenu, l'ancienne
  valeur appliquée, jusqu'à la confirmation (§6).
- **PR7 — l'ancien format vaut le nouveau** : pour tout fichier à l'ancien format, sa migration donne à
  chaque nom le même mode et le même niveau (une propriété, Hypothesis, sur des fichiers tirés au hasard,
  doublons et motifs compris) ; les tests de PRT2 rejoués, paramétrés sur les deux formats, donnent les
  mêmes réserves, les mêmes seaux, la même attente ; la conversion vers l'ancien format ne rend jamais un
  mode plus hardi.
- **PR8 — une entrée sans mode ne change aucun mode** : ajouter ou retirer, sur n'importe quel fichier,
  une entrée qui ne porte que la priorité laisse `resolve` inchangé pour tout nom ; une entrée sans
  priorité laisse `level_of` inchangé.
- **La machine à invariants** (`tests/unit/test_invariants.py`) : chaque VM du monde tire un niveau ; ses
  quinze propriétés doivent tenir quel que soit le niveau. Aucune propriété nouvelle : la classe ne touche
  pas l'isolation.

### 8.2 Les mutants

L'Orchestre donne les plages ; les lots en ont environ 25, plus ceux de CRT1 (§10). Exemples, par lot :
- **PRI2** : un niveau inconnu accepté ; `critical: true` ignoré (la réserve perdue) ; les deux formats
  acceptés ensemble ; une entrée sans mode qui fait écran au mode d'un motif ; une entrée sans mode ni
  priorité acceptée ; la priorité résolue par le plus haut au lieu de l'entrée exacte ; à égalité, le plus
  bas ; un motif ignoré ; `assets` non classée (neutre) ; descendre classé « resserre » ; l'ancienne
  `_critical` gardée (la migration classée « relâche ») ; le push perd un `essential` d'Imladris ; le push
  pousse un `quiet` du poste ; un `standard` du poste qui fait descendre une VM `essential` d'Imladris ; une config d'Imladris refusée dont les modes sont gardés ; `assets:`
  envoyée à une release qui ne la lit pas ; la migration au push qui perd un mode ou un `essential` ; la
  conversion vers l'ancien format qui écrit un mode plus hardi ; un écrivain qui migre le fichier en
  silence ; un `essential` perdu hors de la file et tu ; un lecteur de `level_of` hors de la liste fermée
  (PR1) ; les listes des deux lecteurs divergent.
- **CRT1** : la marque jamais posée ; un motif ignoré ; la réserve recopiée ou fausse ; la ligne de
  démarrage muette (sa fiche) ; `ESSENTIAL` en rouge ; la combinaison avec le mode absente de la tuile ; la
  ligne « may be isolated on its own » absente ou fausse.
- **PRI4** : l'ordre entre les VM ignore le niveau (la première qui réessaie passe, comme avant) ; le
  niveau passe devant la gravité ; une grave de `quiet` rangée après une grave de `standard` ; un budget
  de `quiet` différent de celui de `standard` (PR1).

### 8.3 Ce qui se mesure au banc

La classe est du code déterministe : presque tout se prouve en tests. Le banc, une courte séance avec
PRI4 (par Jonathan, sur une panne bénigne de Gothmog qui fait une détection grave, comme au 20/11) :
- **le push** lit les niveaux d'Imladris et les garde (`make imladris-push`, son rapport), et migre un
  Imladris encore en `autonomy:` ;
- **le démarrage** et la tuile disent les niveaux et la combinaison avec le mode, sur Imladris et sur le
  téléphone ;
- **l'ordre**, une fois PRI4 fait : deux détections de même gravité retenues par le plafond dans la même
  minute, une sur une VM `essential`, une sur une VM `standard` : la première décidée d'abord. Aujourd'hui,
  l'ordre entre elles est celui de leur nouvel essai (§4.2) ;
- **rien d'autre ne bouge** : les mêmes cartes, les mêmes notifications, la même décision, pour une même
  détection sur une VM `essential` et sur une VM `standard` (PR1, vu au banc) ;
- **`quiet` ne change rien** : une même détection sur une VM `quiet` et sur une VM `standard`, le même
  verdict du budget, la même décision.

---

## 9. Les questions à Jonathan, tranchées le 26/11

Posées une à une par l'Orchestre le 26/11 ; Jonathan a répondu le jour même, et **a recadré la classe**
(§0) : elle sert au coût et à l'ordre des files, jamais à la détection ni à la remédiation. Chaque question
garde ses options telles qu'elles ont été posées, la recommandée d'alors en premier ; la réponse suit, avec
sa raison. **Deux réponses s'écartent de la recommandation de la note** : Q4 (la recommandation a changé en
séance, quand Jonathan a demandé pourquoi la classe toucherait l'autonomie) et Q6 (l'entrée exacte, pas le
plus haut). Q5 retient la proposition de Jonathan, et Q9 a été reformulée avec le cadrage. Les exemples :
`vm-db-prod` (la base de l'ERP), `vm-web-01` (un frontal parmi trois), `vm-dev-01` (recréée chaque nuit).

| | La réponse | Recommandée ? |
|---|---|---|
| Q1 | trois niveaux | oui |
| Q2 | `essential`, `standard`, `quiet` | oui |
| Q3 | jamais : l'attention seulement | oui |
| Q4 | aucun lien, la combinaison dite | **non** (la recommandation a changé en séance) |
| Q5 | `assets:`, la découverte reste sur sa source | sa propre proposition |
| Q6 | l'entrée exacte, puis le motif le plus long | **non** |
| Q7 | l'ancien format lu jusqu'à la 1.0, avec une note | oui |
| Q8 | le fichier seul | oui |
| Q9 | les notifications ne bougent pas | oui (la question reformulée) |
| Q10 | PRI2, CRT1 et PRI4 en 0.6.x ; PRT3 en 0.7 | oui, réduite par le cadrage |

**Q1 — Combien de niveaux ?** (§3)
1. **Trois : `essential`, `standard` (le défaut), `quiet` (recommandée).**
2. Deux : `essential` et `standard`, le `critical` d'aujourd'hui renommé.
3. Quatre : `essential`, `important`, `standard`, `quiet`.

**Tranchée le 26/11 : trois niveaux, la recommandée.** Raison : trois comportements nets ; un quatrième
peut s'ajouter sans casser le format. Depuis la réponse du 26/11 sur son budget (§4.1), **`quiet` n'a
plus que l'affichage**, et pourra recevoir un effet plus tard sans changer le format.

**Q2 — Les mots à l'écran et dans le fichier ?** (§3)
1. **`essential` / `standard` / `quiet` (recommandée).**
2. `tier-1` / `tier-2` / `tier-3` (« tier 0 » dit autre chose en sécurité, et l'ordre se lit dans les deux
   sens).
3. `high` / `normal` / `low` (une carte `high` sur une VM `high` mêle l'événement et l'objet).

**Tranchée le 26/11 : `essential`, `standard`, `quiet`, la recommandée.** Raison : les mots disent
l'objet sans alarmer, et ne croisent aucun mot déjà pris (§1.4, constat 2).

**Q3 — Le principe : la classe peut-elle relâcher une garde de sûreté ?** (§2.2)
1. **Jamais : l'attention seulement (recommandée).** `vm-db-prod` est servie d'abord et n'attend pas
   l'argent ; son seuil de confiance, ses tirages et son plafond de règle sont ceux de toutes les VM.
2. Le plus haut niveau contient plus vite : un seuil plus bas, un tirage en moins.

**Tranchée le 26/11 : jamais, la recommandée.** Raison : la sûreté reste dans le code et dans le mode.
Le cadrage du même jour va plus loin : la classe ne touche rien de la détection ni de la remédiation, pas
seulement les gardes (§0).

**Q4 — Une VM essentielle et l'autonomie : que fait la classe ?** (§4.5)

Posée d'abord avec trois options : 1. une réserve de préparation `essential_service`, à confirmer une
fois, la VM tenue en `human_only` d'ici là (la recommandée d'alors) ; 2. un plafond de l'objet, sur le
modèle de RDW1, qui ramène une isolation autonome à l'instantané ; 3. rien. Jonathan a demandé pourquoi
la classe toucherait l'autonomie ; reformulée en séance :
1. **Aucun lien, la combinaison dite (la recommandation nouvelle).** Le mode reste la seule décision. La
   tuile montre `ESSENTIAL · NON_DISRUPTIVE` ; la page Config dit en une ligne quelles VM essentielles
   peuvent être isolées seules : « vm-db-prod may be isolated on its own (non_disruptive): its service
   stops while it is isolated ».
2. La réserve de préparation d'abord proposée.

**Tranchée le 26/11 : aucun lien, la combinaison dite — pas la recommandation d'abord écrite.** Raison :
le mode est la décision, et une classe qui retient ou corrige le mode ferait deux endroits pour une même
décision ; l'opérateur choisit le mode d'une VM essentielle en voyant ce qu'il coûte. La réserve
`essential_service` sort, et PRI3 avec elle.

**Q5 — Où s'écrit la classe dans le fichier ?** (§5.1)
1. **Une section à part, `priorities:` (`match`, `level`, `reason`) (la recommandation de la note).**
2. Une clé `priority:` sur les entrées d'`autonomy.assets`, à la place de `critical` : un mode imposé à
   chaque VM classée, et une clé de plus dans `ASSET_KEYS`, le risque de CRT1.
3. **La proposition de Jonathan : une seule section `assets:`**, qui remplace `autonomy:` —
   `default_mode`, `allow_destructive`, une `list` d'entrées qui portent chacune un `mode` facultatif et
   une `priority` facultative.

**Tranchée le 26/11 : sa proposition, `assets:`, la découverte restant sur sa source.** Les exclusions
(`exceptions`) restent à part pour l'instant. Raison : une VM se lit à un seul endroit, et le mode
facultatif délie la classe du mode (le constat 1) ; les clés des deux lecteurs changent ensemble, dans
PRI2, avec la garde de version du push (§5.5).

**Q6 — Deux entrées d'`assets.list` couvrent une VM : laquelle l'emporte, champ par champ ?** (§5.3)

Le mode garde la règle d'aujourd'hui (l'entrée exacte, puis le motif le plus long), sans question. Pour la
priorité :
1. **Le niveau le plus haut, toujours (la recommandation de la note).** `vm-erp-*: essential` et
   `vm-erp-qa: quiet` : `vm-erp-qa` reste essentielle.
2. La même règle que le mode : l'entrée exacte, puis le motif le plus long. `vm-erp-qa` devient quiet,
   une exemption.

**Tranchée le 26/11 : l'entrée exacte, comme le mode — pas la recommandation de la note.** Raison de
Jonathan : une exception précise doit être possible ; la descente qu'elle produit est protégée par la
confirmation (§6). À égalité, la note propose le plus haut.

**Q7 — Que devient l'ancien format, `autonomy:` et `critical: true` ?** (§5.4)
1. **Lus jusqu'à la 1.0, avec une note qui invite à migrer ; la migration à valeurs égales est neutre ; les
   deux formats ensemble, ou en conflit, sont une erreur de config (recommandée).**
2. Refusés dès la release qui lit `assets:`.
3. Gardés pour toujours.

**Tranchée le 26/11 : lu jusqu'à la 1.0, avec une note, la recommandée.** `glorfindel config migrate`
migre à valeurs égales ; les deux formats ensemble sont refusés. Raison : aucune rupture pour une config
d'aujourd'hui, et une seule forme à la 1.0.

**Q8 — D'où vient la classe ?** (§2.1)
1. **Du fichier seul (recommandée).**
2. Du fichier, et d'un tag Azure qui ne peut que monter.
3. Des tags seuls.

**Tranchée le 26/11 : du fichier seul, la recommandée.** Raison : la classe se change par la file de
CFG1 ; un tag s'écrit par qui écrit la ressource. Un tag qui ne fait que monter reste possible plus tard.

**Q9 — La classe touche-t-elle les cartes et les notifications ?** (§4.4)

D'abord posée avec un ping de plus pour `essential` et un de moins pour `quiet` ; reformulée avec le
cadrage :
1. **Non : les notifications ne bougent pas (recommandée).** Ni Discord, ni le webhook, ni la gravité
   d'une carte ne lisent la classe.
2. Les pings d'abord proposés.

**Tranchée le 26/11 : non, les notifications ne bougent pas, la recommandée.** Raison : ce que Glorfindel
dit est hors du cadrage ; PRI5 sort. La règle « la première grave d'un fil mentionne toujours » peut
faire un lot à part, sans lien avec la classe (§11).

**Q10 — Ce qui part avant la 0.7 ?** (§10)
1. **En 0.6.x, PRI2 (le format), CRT1 (l'affichage) et PRI4 (l'ordre entre les
   VM) ; en 0.7, PRT3 (recommandée, réduite par le cadrage).**
2. Tout en 0.7, avec PRT3.
3. En 0.6.x, le format et l'affichage seulement.

**Tranchée le 26/11 : l'option 1.** D'ici CFG5, une priorité descendue à la main s'applique à la
relecture : le risque est faible, puisque la classe ne touche ni la détection ni la remédiation. Raison :
chaque effet qui reste touche du code qui existe (la réserve du budget, la porte), sauf l'ordre entre les VM, que
PRI4 ajoute.

---

## 10. Les lots

En jours de travail effectif, à ±50 %, comme la feuille de route. Les mutants sont estimés ; l'Orchestre
donne les plages. Le découpage suit les réponses du 26/11 (§9) et le cadrage : **PRI3** (la réserve de
préparation), **PRI5** (les notifications) et **PRI6** (l'enquête par niveau) sortent.

| Lot | Session | Ce qu'il touche | Taille | Jalon | Risques | Mutants |
|---|---|---|---|---|---|---|
| **PRI2a** — le format `assets:`, la lecture et la migration | Glorfindel | la section `assets:` lue strictement (§5.2) : `default_mode`, `allow_destructive`, `list` (`match`, `mode` et `priority` facultatifs, `reason`), une entrée vide ou en double refusée ; un seul modèle en mémoire ; `resolve` et `level_of` sur les seules entrées qui portent leur champ, l'entrée exacte puis le motif le plus long (§5.3, Q6) ; l'ancien format (`autonomy:`, `critical: true`) lu avec sa note, les deux formats ensemble refusés (§5.4) ; `glorfindel config migrate`, dans les deux sens (§5.4, §5.6) ; les écrivains qui gardent le format du fichier (le sélecteur de mode de la console, le défaut, la CLI) ; `is_critical` et `critical_count` sur `level_of`, les seaux gardés ; la garde de structure de PR1 et la propriété sur le verdict du budget ; CFG4 sur le modèle, `_critical` remplacée, `allow_destructive` lu sur le modèle, un motif changé classé « relâche », la migration neutre et son test, la garde des sections (constat 4) ; la vue « Relaxed » aux deux formats ; la note de migration au démarrage et dans `/api/config` ; les mutants de PRT2 ré-ancrés ; la doc : `configuration-console.md` (CFG1, CFG5 nomment partout `autonomy.assets`), `operations.md` (le format, la migration, `quiet` posé à la main sur Imladris, le retour arrière), `glorfindel.md` (« Modes d'autonomie par asset »), `raisonnement.md`, `fichiers-cles.md` | 3 j | 0.6.x | une migration qui change un mode (la propriété PR7 la tient) ; un écrivain oublié qui écrit l'ancien format dans un fichier migré | ~13 |
| **PRI2b** — le push et la garde de version | Glorfindel (le push, côté Imladris) | `host_config.py` : `ASSET_KEYS` et `KNOWN_PRIORITIES` changés avec la watch, une config d'Imladris refusée entière inconnue, jamais un niveau plus bas, nom par nom, motifs compris (PR4), la garde de version (le format de la release d'Imladris), la migration d'Imladris au push, la conversion vers l'ancien format (§5.5, §5.6) ; la watch qui dit un `essential` perdu hors de la file ; le test des deux lecteurs et le test des mêmes verdicts ; la doc du push (`infra/glorfindel-host/README.md`) | 1,5 j | 0.6.x, avec PRI2a ou juste après, avant toute release qui lit `assets:` | un lecteur qui diverge : toutes les VM en `human_only` au push ; un retour arrière refusé tant que la section est là ; la release d'Imladris illisible (l'ancien format écrit, dit) | ~7 |
| **CRT1** — l'affichage (repris) | Console, une ligne Glorfindel | la tuile (`ESSENTIAL · NON_DISRUPTIVE`), la page Config (la section « Priorities », la ligne des VM essentielles qui peuvent être isolées seules), le démarrage, le téléphone (§7) ; `/api/config` transmet le mode et la priorité de chaque entrée d'`assets.list` (ou de l'ancien format) et le niveau de chaque VM, les notes de PRI2, la réserve calculée par le budget | 1,5 j | 0.6.x, après PRI2 | une couleur d'alarme ; un chiffre recopié | M7771–M7780 (sa fiche, à refaire sur ce format) |
| **PRI4** — l'ordre entre les VM dans la porte, pour les graves | Glorfindel | **un ordre entre les VM, que la porte n'a pas** (la première qui réessaie passe, `decision_queue.py:419-426`, `:707-709`) : un registre des graves et des critiques qui attendent une place, rangé par gravité, puis par niveau (`essential` d'abord, `standard` et `quiet` ensemble), puis par arrivée (§4.2) ; `docs/raisonnement.md` §2.5 mis à jour | 2 j | 0.6.x, après PRI2a | l'ordre touche le plafond de PRT1 (un critère de sa preuve : jamais plus de `MODEL_CALLS_PER_MIN`) ; une famine des graves de `standard` sous un flot d'`essential` ; si l'ordre ne vaut pas son coût, il part à PRT3 et PRI4 disparaît | ~4 |
| **PRT3** — la porte qui trie, branchée sur la classe | Glorfindel | la classe comme ordre et comme budget seulement, jamais une raison d'écarter ou de garder une détection (§4.2) | (sa fiche) | 0.7 | — | (sa fiche) |
| **PRI7** — retirer l'ancien format | Glorfindel | `autonomy:` et `critical` refusés, la note devenue erreur, le push et sa doc | 0,5 j | 1.0 | une config jamais migrée : dite depuis la 0.6.x | ~2 |

**Total** : environ 8,5 jours hors PRT3 (6,5 si l'ordre entre les VM part à PRT3), environ 26 mutants plus
ceux de CRT1. PRI2 est découpé en PRI2a (3 j) et PRI2b (1,5 j) ; PRI4 ne porte plus que l'ordre entre les
VM pour les graves, `quiet` gardant le budget de `standard` (§4.1).

**La mise en attente d'un relâchement** (retenu jusqu'à confirmation, §6) **appartient à CFG5**, pour tout
le fichier : l'historique, les demandes en attente, `applied.json` (`configuration-console.md` §3.3, §9).
Aucun lot de cette note ne la construit.

**L'ordre.** PRI2a d'abord : tout lit `level_of` et le modèle unique ; PRI2b avec lui ou juste après,
toujours avant la première release qui lit `assets:` (sans lui, un push effacerait la section). CRT1 ensuite, sur son format (sa
fiche, écrite pour `priority: true`, est à reprendre : les niveaux, `assets.list`, « Priorities », la
marque `ESSENTIAL` collée au mode ; la note de migration est à PRI2a). PRI4 en parallèle de CRT1, après
PRI2a. La courte séance du banc (§8.3) après PRI4. PRT3 en 0.7. PRI7 à la 1.0.

---

## 11. Les limites

- **La classe ne protège pas d'une config fausse.** Une VM essentielle oubliée dans `assets.list` est
  `standard` : rien ne le devine. La page Config montre ce qui est classé ; rien ne montre ce qui ne l'est
  pas, sauf la carte de l'infra, tuile par tuile.
- **Le compte de la réserve est par entrée, pas par VM** (§1.1) : un motif `essential` qui couvre dix VM
  apporte 0,50 $, comme une seule. La note le garde (la réserve reste bornée et lisible) ; un parc où
  beaucoup de VM sont essentielles verra le plafond de 2,50 $ tôt.
- **Une console compromise peut tout monter en `essential`.** C'est un resserrement, il s'applique ; il
  réduit les ordinaires du parc et rend l'ordre des files sans effet. L'annonce forte au-delà de 5 VM (§6)
  le rend visible ; elle ne l'empêche pas.
- **Le rang dans la porte n'existe pas aujourd'hui** (§4.2) : entre les VM, la première qui réessaie
  passe. Jusqu'à PRI4, `essential` n'est servie d'abord nulle part ; elle n'attend ni l'argent ni le
  refroidissement du fournisseur, c'est tout.
- **D'ici CFG5, une descente s'applique** (§6) : une priorité descendue à la main, ou un `quiet` posé, prend
  effet à la relecture, sans confirmation. Le risque est faible : la classe ne touche ni la détection ni
  la remédiation (Q10).
- **Les versions du poste et d'Imladris** (§5.5) : un push depuis un poste d'avant PRI2 efface les niveaux
  d'Imladris ; le code d'avant ne change pas, la watch d'Imladris le dit (un `essential` perdu hors de la
  file), elle ne l'empêche pas. Le geste qui l'évite : mettre le poste à jour avant de pousser.
- **`quiet` sur Imladris** ne se pose qu'à la main sur l'hôte, par Jonathan, jusqu'à CFG5 (§5.5).
- **Le retour arrière** sous PRI2 demande un geste (§5.6) tant que le préflight ne lit pas la config par
  les deux images (MSUB6).
- **Les abonnements ajoutés** (MSUB3) : jusqu'à ce que MSUB3 indexe par (abonnement, motif), une entrée de
  `assets.list` vaut par le nom, comme le mode aujourd'hui ; un homonyme d'un autre abonnement prendrait le
  niveau. Pour `essential`, c'est un resserrement ; pour `quiet`, un relâchement hérité — la même limite
  que MSUB1 a relevée pour le mode (`watch-multi-abonnement.md` §1.6), fermée par le même lot.
- **Deux formats jusqu'à la 1.0** (§5.4) : tout lecteur et tout écrivain du fichier les connaît tous
  les deux, ou se trompe en silence. PRI2 les recense (la watch, le push, la console, la CLI, CFG4, la vue
  « Relaxed ») ; un écrivain oublié écrirait l'ancien format dans un fichier migré, que la watch refuserait
  alors (les deux formats ensemble) : bruyant, jamais silencieux.
- **Une suite, sans lien avec la classe** : aujourd'hui, une carte grave postée dans un fil Discord déjà
  ouvert ne mentionne pas le rôle (§4.4) ; une force brute qui ouvre le fil tait le rançongiciel qui
  suit. La règle « la première grave d'un fil mentionne toujours » peut faire un lot à part, du bot.
- **Le push compare les noms et les motifs cités** (§5.5) : une VM couverte par un seul motif d'Imladris,
  qu'un motif plus long du poste ferait descendre sans que son texte réponde à l'ancien (`vm-*-db` sur
  Imladris, `vm-erp-prod-?b: standard` sur le poste), peut lui échapper, comme à CFG4 sans la découverte.
  Le côté sûr, proposé pour PRI2b : refuser de pousser tout motif du poste qui porte `standard` ou
  `quiet`, et le dire.
