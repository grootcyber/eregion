# La configuration dans la console (CFG1, #1090) — conception

_Note de conception, sans code, 23/11. Décision de Jonathan du 23/11 : « Il faudra vraiment muscler la
partie config dans l'interface avec le fichier de conf et le discovery. On ne peut pas demander à un
utilisateur d'aller modifier un fichier yaml à la main. » La note maintenant, le code après. **Les
onze questions du §8 sont tranchées, le 23/11** (en interactif, CFG1b) : Jonathan a retenu chaque fois
l'option recommandée. Ce que ces réponses tranchent porte « décidé (Q…) » ; le reste porte encore le
mot « proposé »._

Les décisions de SEC2 du 23/11 (réseaux nommés, zone exposée, origines attendues) enrichissent la
configuration. Cette note dit comment la console l'écrira sans devenir une seconde source de vérité,
ni la cible qui désarme les gardes.

---

## 0. En bref

- **Aujourd'hui**, la console ne règle que le mode : celui d'une VM, et le défaut. Elle réécrit le
  fichier elle-même, par `yaml.safe_dump` : les commentaires sont perdus. La CLI fait de même
  (`glorfindel activate`). Tout le reste se fait à la main, par `sudoedit` sur Imladris (anciennement H0), ou sur le
  poste puis `make imladris-push`.
- **Proposé : la console part de ce qui est découvert.** On clique une VM, un VNet, une IP publique.
  Décidé (Q7) : elle n'écrit que des noms exacts ; (Q8) en v1, les sept gestes du §2, le reste en
  lecture seule.
- **Proposé : le fichier reste la référence.** Il reste lisible, relu, versionnable. La console est un
  éditeur au-dessus du fichier. Elle garde les commentaires et l'ordre des clés.
- **Décidé (Q1, Q5) : la console demande, la watch écrit.** La console dépose une demande signée dans la file
  d'actions (FS1). La watch la vérifie, relit le résultat avec la lecture stricte (A3), l'écrit, et
  garde l'historique. **Tout l'état de la configuration vit dans un répertoire que seule la watch
  écrit** (`runs/glorfindel/config/`) (proposé, §3.4, §4.3), en lecture seule chez la console et le
  bot.
- **Décidé (Q2, Q11) : resserrer s'applique, relâcher se confirme.** Un mode plus prudent part tout de
  suite. Une exclusion, une origine attendue, un mode plus hardi demandent une confirmation, et c'est
  dit fort (ces exemples suivent le classement du §5.2, qui reste proposé).
  La classe suit le sens de la configuration, pas ce que la découverte voit ce jour-là (proposé, §5.3) ;
  celle d'un ajout à `never_block` est décidée (Q10), l'annonce d'un passage en masse aussi (Q11).
- **Proposé : tout ce qui est relâché reste visible.** Une vue, calculée par la watch, le montre avec
  sa raison, sa date et son auteur. Une VM exclue ne disparaît jamais en silence.

Le parcours d'un changement, de bout en bout (proposé) :

```
 opérateur, dans le navigateur (jeton SEC1)
   │  clic sur la carte de vm-dev-01 : « Exclure des règles appliquées à toutes les VM »
   │  raison : « VM de dev, recréée chaque nuit »
   ▼
 console ── lit le fichier (en lecture seule), montre le diff, note son condensé « base »
   │  dépose une demande signée par sa clé (FS1)
   ▼
 runs/console/queue/<id>.json      kind: config_request · op: exclude · base: sha256:…
   │  (monté en lecture seule chez la watch ; vie de 120 s, comme toute demande de FS1)
   ▼
 watch ─ signature → fraîcheur → nonce → op d'une liste fermée
       ─ base = condensé du fichier actuel ?          non → refus « config_changed »
       ─ applique l'op au texte, commentaires gardés
       ─ lecture stricte (A3) du résultat              refusé → rien n'est écrit
       ─ classe : resserre / relâche / neutre          (sur le sens de la config, §5.3)
       ─ relâche ? → mise en attente, signée par la watch, annoncée (§4.4)
       ─ à l'échéance : base relue, classe recalculée, annonce postée ? → sinon refus, dit
       ─ écrit le fichier (verrou, remplacement atomique ou en place), recharge ce qu'elle tient
   ▼
 glorfindel-config.yaml              runs/glorfindel/config/   (la watch seule l'écrit)
 (la watch seule l'écrit)              history.jsonl · pending/ · notices.jsonl · applied.json · relaxed.json
   │                                    │
   ▼                                    ▼  (monté en lecture seule)
 reçu signé                          bot → Discord : « relâchement demandé : vm-dev-01 exclue… »
 runs/glorfindel/queue/console-<id>.json      puis le bot note qu'il l'a posté, dans runs/bot/
   ▲ suivi par la console (GET /api/queue/<id>), puis la carte grisée « EXCLUDED »
```

---

## 1. L'inventaire d'aujourd'hui

Lu dans le code le 23/11 : `glorfindel/config.py` (la lecture stricte A3, `_parse_config`),
`glorfindel-config.yaml.example`, `docs/operations.md` (« Configuration »), `eregion_console/api.py`,
`eregion_console/static/glorfindel.js`, `glorfindel/cli.py`, `glorfindel/detection_rules.py`,
`glorfindel/watch/rules.py`, `docker-compose.yml`, `Makefile` (`imladris-push`, `glorfindel-shell`) et
`infra/glorfindel-host/host_config.py`.

### 1.1 Les clés du fichier

« Relue » dit quand la watch relit la clé : un changement prend effet à ce moment-là.

| Clé | Ce qu'elle fait | Qui l'écrit | Ce que la console en montre | Relue |
|---|---|---|---|---|
| `monitoring_backends[]` : `name`, `type`, `workspace_id`, `endpoint`, `discovery.enabled`, `discovery.interval_s` | Les sources de détection et de découverte (Heartbeat). | La main ; le fragment de Celebrimbor (`make celebrimbor-output`) pour le banc. | `/api/config` : nom, type, découverte. La carte de l'infra (DETECT). | Au démarrage de la watch. |
| `action_backends[]` : `name`, `type`, `vault_name`, `resource_group`, `restore_staging_storage` | Le coffre du restore et son compte de transit. | La main. | Nom, type, coffre. | À chaque restore (`resolve_backup_vault`). |
| `exceptions[]` : `asset_pattern`, `exclude_all`, `exclude_rules` | Retire une VM (motif fnmatch, casse ignorée) de toutes les règles, ou de certaines. `posture` compte comme une règle. **Seules les règles appliquées à toutes les VM découvertes (`auto_apply`) en tiennent compte** : une règle écrite pour une VM la surveille encore (§10). | La main. | `exceptions_count` dans `/api/config`, que la page n'affiche pas. L'audit d'une VM compte ses règles « exclues », en vert, sans raison. | Au démarrage : le `RulePoller` garde la config qu'il a lue (`watch/rules.py:115`, `:189`). |
| `autonomy.default` | Le mode par défaut. | La main ; la console (`PATCH /api/config/autonomy/default` → `set_default_mode`). `imladris-push` le force à `human_only`. | Le menu de `/config`. | À chaque cycle (`decide`). |
| `autonomy.assets[]` : `match`, `mode` | Le mode d'une VM ou d'un motif. Une entrée exacte l'emporte sur tout motif (`AutonomyConfig.resolve`). | La main ; la console (`POST /api/autonomy/<vm>`, `/api/activate/<vm>` → `set_asset_mode`, un nom exact) ; la CLI (`glorfindel activate`, `cli.py:1458`). `imladris-push` garde ceux d'Imladris (BL1c). | Le badge et le menu de la carte : le mode effectif, avec la préparation (L6). | À chaque cycle. |
| `autonomy.allow_destructive` | Annoncé : les actions destructives permises seules. | La main ; `imladris-push` la vide. | `/api/state.capability` la range parmi les actions autonomes. | **Aucun code de Glorfindel ne la lit** (§10). |
| `isolation.quarantine_nsg`, `quarantine_rg` | Le mécanisme de la quarantaine. | La main. | Rien, sauf par la préparation. | À chaque isolation. |
| `isolation.forensic_sources`, `forensic_ports` | L'accès d'enquête à une VM isolée. | La main. | Rien. | À chaque isolation. |
| `never_block` | Les adresses jamais bloquées, en plus des livrées (SEC2). Le connecteur refuse leur blocage, même approuvé. | La main. | Rien. Une carte `protected_address` dit la raison d'un blocage retenu. | À chaque blocage. |
| `expected_sudo` : `admins[]` (`match`, `accounts`, `origins`), `sensitive_commands`, `origin_proof` | Les sudo attendus des administrateurs (ADM1, COR1, COR2). | La main, par `sudoedit` sur Imladris. | Le compte des sudo écartés, dans la règle. | Au démarrage : le `RulePoller` lit la politique dans la config qu'il garde (`detection_rules.py:1955`). |
| `memory.max_age_days` | L'âge au-delà duquel un cycle n'est plus un précédent (SEC17). | La main. | Rien. | À chaque recherche. |

**Les clés que SEC2 ajoute** (décisions du 23/11 ; rien n'est encore dans le code) :

| Clé | Lot | Ce qu'elle fera |
|---|---|---|
| `networks` (nom → CIDR, ou `{subnet: "<vnet>/<sous-réseau>"}`, ou `{vnet: "<nom>"}`) | SEC2b | Des réseaux nommés, déclarés une fois, cités par leur nom. Un nom d'objet se résout par la découverte, en nom exact, jamais un motif. |
| `network_zones.exposed` | SEC2c | Une zone exposée (une DMZ, un partenaire) : le blocage seul y redevient possible, à deux conditions. |
| `network_zones.expected_origins` | SEC2d (#1147), en vigueur avec `GLORFINDEL_LATERAL` (0.7) | Une origine attendue : une détection qui en vient est écartée, dite et comptée ([`mouvement-lateral.md`](mouvement-lateral.md)). |

**Hors du fichier, et hors de cette note** :
- les variables d'environnement du déploiement (`GLORFINDEL_READ_ONLY`, `GLORFINDEL_CONFIDENCE_THRESHOLD`,
  `GLORFINDEL_ISOLATION_TTL_H`, `GLORFINDEL_LLM_MODEL`…). La page Config le dit déjà pour le modèle :
  « Not a setting of this page ». Proposé : elles le restent ;
- les règles du client (`~/.glorfindel/client_rules.yaml`, P1). La console les écrit déjà par
  `approve-rule`. FS1f prévoit de les faire passer par la file.

### 1.2 La découverte

- `glorfindel/discovery.py` lit les VM par le Heartbeat de chaque backend de surveillance. Chacune a un
  nom, un `resource_id`, son backend, `last_seen`, sa source, son type (`vm`, `vmss_instance`), son
  parent. Le registre vit dans `~/.glorfindel/discovered_assets.json`, **que la console monte en
  écriture**. Il ne décide pas de la classe (§5.3), mais il décide de la couverture des règles
  `auto_apply` au démarrage : il est lu au démarrage (`discovery.py:73`), et ces règles surveillent les
  VM qu'il nomme (`detection_rules.py:1890-1896`). FS1f le ferme.
- **Une VM exclue reste dans le registre.** L'exclusion s'applique plus tard, règle par règle
  (`RulePoller._targets`). La console voit donc encore la VM, et la montre sur la carte de l'infra.
- Avec SEC2b : les espaces d'adresses des VNet et de leurs sous-réseaux, et les IP publiques du client
  (cartes réseau, passerelles NAT, frontaux d'équilibreur), avec l'heure de lecture.

### 1.3 Ce que la console sait déjà

- **`/config`** : Azure (masqué), le modèle (lecture seule, avec la marche à suivre), le mode par défaut
  (un menu qui écrit), les sections.
- **La carte d'une VM** : son mode, et le menu qui le change. Passer en `non_disruptive` passe par la
  préparation (L6, `/api/activate`) : aucune VM ne quitte `human_only` sans que ses réserves aient été
  montrées. Le retour à `human_only` est direct, et efface les acquittements.
- **L'audit d'une VM** : la ligne « Detection rules » compte les règles exclues (« 3 exclues »). Elle
  reste en vert, sans raison : le fichier n'a pas de champ pour la raison.
- **Rien d'autre** : ni les exclusions, ni `never_block`, ni les administrateurs attendus, ni l'accès
  d'enquête.
- **L'écriture d'aujourd'hui** (`_update_config`, `glorfindel/config.py:226`) :
  - un verrou exclusif (`flock`), puis une relecture si le fichier a été remplacé pendant l'attente ;
  - un remplacement atomique, ou une écriture en place quand le fichier est monté seul dans un conteneur
    (`EBUSY`) ;
  - `yaml.safe_dump(sort_keys=False)` : l'ordre des clés reste, **les commentaires sont perdus** ;
  - seul le mode est validé. Le fichier écrit n'est pas relu par la lecture stricte avant l'écriture.

### 1.4 Qui écrit le fichier, et où

Il y a déjà quatre écrivains, et un cinquième possible :

```
 poste : glorfindel-config.yaml local ── make imladris-push ──┐  (host_config.py : défaut forcé à
                                                               │   human_only, allow_destructive
 Imladris : sudoedit ~/eregion/glorfindel-config.yaml ─────────┤   vidée, modes d'Imladris gardés,
                                                               │   relu juste avant l'envoi ;
 console : set_asset_mode, set_default_mode ───────────────────┼─► réécrit par safe_dump)
                                                               │
 CLI : glorfindel activate → set_asset_mode ───────────────────┤  (dans le conteneur de la watch sur
                                                               │   Imladris ; sur un poste, make
                                                               │   glorfindel-shell monte le fichier
                                                               │   en écriture, Makefile:112)
 (demain) l'IaC du client : Terraform qui produit le fichier ──┘
```

**Les montages** (`docker-compose.yml`) : la watch et le bot montent le fichier **en lecture seule**
(`:ro`) ; la console le monte **en écriture**. C'est l'inverse de ce que FS1 veut pour les actions :
aujourd'hui, la console écrit ce que la watch lit. La console monte aussi `~/.glorfindel` en écriture
(`docker-compose.yml:335`).

**Le push et la console** se connaissent déjà un peu. `host_config.py` garde le mode de chaque VM tel
qu'il est sur Imladris, jamais un plus hardi. Et le push relit la config d'Imladris juste avant
l'envoi : changée entre-temps (« un mode changé dans la console ? »), il n'envoie rien. **Mais tout le
reste est écrasé par la copie du poste**, réécrite par `yaml.safe_dump` (`host_config.py:165`) : les
commentaires sont perdus là aussi. Une exclusion posée depuis la console disparaîtrait au push suivant
(§3.3).

### 1.5 La remarque de Jonathan sur `exclude_all`

> `exceptions.exclude_all` rend une VM invisible : plus aucune détection. À vérifier : la console doit
> montrer qu'une VM est exclue, avec sa raison, au lieu de la passer sous silence.

Vérifié dans le code le 23/11 :
- **la VM reste sur la carte de l'infra** : le registre la garde ;
- **sa carte ne dit pas qu'elle est exclue** : aucun badge, aucune bande ;
- **seul l'audit le dit**, dans la ligne « Detection rules », en vert, sans raison ;
- **la raison n'existe pas** : `exceptions[]` n'a que `asset_pattern`, `exclude_all`, `exclude_rules` ;
- **un motif peut exclure une VM créée plus tard** (`vm-dev-*`), sans que rien ne le dise ;
- **« plus aucune détection » n'est pas tout à fait vrai**, et l'audit le dit mal : l'exclusion ne
  retire la VM que des règles `auto_apply` (`detection_rules.py:1883-1897`). Une règle écrite pour
  cette VM (`assets: [<resource_id>]`) la surveille encore, alors que l'audit la compte « exclue »
  (`audit.py:333-341`) ;
- **une exclusion ajoutée ne prend effet qu'au redémarrage de la watch** : le `RulePoller` garde la
  config lue au démarrage.

Il faut donc un petit lot : CFG2 (§9), qui peut partir avant tout le reste.

**Livré par CFG2 (#1128, 24/11)**, sans aucune écriture : la clé `exceptions[].reason` (facultative, une
ligne d'au plus 200 caractères, lue strictement ; une version d'avant CFG2 refuse le fichier qui la porte) ;
`/api/state.exclusions` et `/api/exclusions`, calculés par `glorfindel/exclusions.py` depuis le fichier et
les règles seuls : de quoi la VM est exclue, pourquoi, par quel motif, et les règles écrites pour elle qui
la surveillent encore ; sa carte grisée, avec la puce `EXCLUDED` ou `PARTLY EXCLUDED` et sa bande ; l'Overview
qui compte les VM exclues et les entrées qui n'en prennent aucune aujourd'hui ; la ligne d'audit en jaune,
qui ne compte plus « exclue » une règle écrite pour la VM. La date (« since ») attend l'historique (CFG5) ;
ce qui est écrit mais pas encore appliqué, `applied.json` (CFG5) : d'ici là, l'infobulle de la bande
(son `title`) dit que la watch lit l'exclusion à son démarrage.

---

## 2. Le principe : partir de ce qui est découvert

**Proposé : on clique un objet découvert au lieu de taper un nom, un motif ou un CIDR.** Décidé (Q7) :
la console écrit dans le fichier le **nom exact** de l'objet, jamais un motif qu'elle aurait inventé ;
un motif écrit à la main reste admis dans le fichier, et la console le montre, avec ce qu'il désigne
aujourd'hui. Proposé : un CIDR écrit à la main reste admis aussi, et la console le montre.

Un exemple par geste. **Ces sept gestes sont la portée de la console en v1, décidé (Q8)** ; le reste
(`isolation`, `memory`, les backends, `origin_proof`, `allow_destructive`) reste en lecture seule.

| Geste | Où on clique | Ce que la console demande d'écrire |
|---|---|---|
| **Le mode d'une VM** | la carte de `vm-web-01`, menu du mode | `autonomy.assets: [{match: "vm-web-01", mode: human_only}]` — comme aujourd'hui, par la file |
| **Une exclusion, avec sa raison** | la carte de `vm-dev-01`, « Exclude… » : toutes les règles, ou une liste cochée | `exceptions: [{asset_pattern: "vm-dev-01", exclude_all: true, reason: "VM de dev, recréée chaque nuit"}]` — `reason` est une clé nouvelle (proposé, CFG2). La VM reste sur la carte, grisée |
| **Un réseau nommé** | la liste des sous-réseaux découverts (SEC2b), `vnet-hub/snet-dmz` | `networks: {dmz: {subnet: "vnet-hub/snet-dmz"}}` — la découverte lit la plage, et le nom la suit |
| **Une zone exposée** | un réseau nommé, « Mark as exposed » | `network_zones: {exposed: [dmz]}` — refusée si trop large (jamais un /8), dite fort au démarrage (SEC2c) |
| **Une origine attendue** | un réseau nommé, « Expected origin » | `network_zones: {expected_origins: [bastion]}` (SEC2d, 0.7) |
| **`never_block`** | une IP publique découverte (la sortie d'une passerelle NAT), ou une adresse saisie | `never_block: ["198.51.100.10"]` — une adresse saisie passe la même validation que le fichier (`validate_never_block`) ; sa classe est décidée (Q10) : un hôte privé seul resserre, un préfixe plus large ou une adresse publique relâche |
| **Les administrateurs attendus (ADM1)** | une carte de sudo sur `vm-web-01`, « Expect admin1's sudo here » | `expected_sudo: {admins: [{match: "vm-web-01", accounts: [admin1], origins: [bastion]}]}` — le compte vient de la carte, l'origine d'un réseau nommé |

Trois règles en découlent. La première est décidée (Q7). La deuxième reste proposée. Dans la
troisième, le motif est décidé (Q7) et la clé hors liste aussi (Q8) ; le CIDR écrit à la main reste
proposé :
1. **Le nom exact, jamais un motif.** Un clic sur `vm-dev-01` écrit `vm-dev-01`, pas `vm-dev-*`. Une VM
   créée demain n'est jamais prise en silence. C'est déjà la règle de SEC2 pour les objets réseau
   (décision 9) et celle de `set_asset_mode`.
2. **Un objet introuvable reste dit.** Une VM supprimée, un sous-réseau renommé : l'entrée reste dans le
   fichier, et la console la montre « not found by the discovery » au lieu de la cacher. Pour un réseau
   nommé, c'est la liste illisible de SEC2 (décision 4).
3. **Ce que la console ne sait pas écrire, elle le montre.** Un motif, un CIDR écrit à la main, une clé
   hors de la liste du §5 : affichés en lecture seule, avec ce qu'ils désignent aujourd'hui (« vm-dev-*
   : 3 VM découvertes »).

---

## 3. Le fichier reste la référence

### 3.1 Pourquoi

- **Lisible et relu** : un humain le lit d'un coup. Une revue de code le lit aussi.
- **Versionnable** : chez un client, il vit dans un dépôt, ou il sort de son Terraform. C'est le principe
  du module d'isolation ([`module-isolation-iac.md`](module-isolation-iac.md)) : « Terraform possède la
  structure ; Glorfindel ne modifie que l'état ». Le banc le fait déjà : le fragment de Celebrimbor.
- **Une seule lecture** : la lecture stricte (A3) reste la seule porte. La console n'a pas de base à
  elle. **Elle n'est pas une seconde source de vérité.**

### 3.2 Une écriture aller-retour

**Proposé : la watch applique un changement au texte, pas à un dictionnaire.** Elle relit le fichier
dans une représentation qui garde les commentaires, l'ordre et les guillemets (une bibliothèque
aller-retour, `ruamel.yaml` par exemple : une dépendance nouvelle, donc `make lock` dans la même PR).
Elle change la seule entrée visée. Elle réécrit le reste à l'octet. Le même code sert à la CLI et,
plus tard, au push (CFG8).

Exemple. Le fichier contient :

```yaml
exceptions:
  # Les VM de dev : recréées chaque nuit (Jonathan, 12/11)
  - asset_pattern: "vm-dev-*"
    exclude_rules: [ssh-brute-force]
```

La console demande « exclure `vm-lab-02` de toutes les règles ». Le fichier devient :

```yaml
exceptions:
  # Les VM de dev : recréées chaque nuit (Jonathan, 12/11)
  - asset_pattern: "vm-dev-*"
    exclude_rules: [ssh-brute-force]
  - asset_pattern: "vm-lab-02"
    exclude_all: true
    reason: "Labo de formation, sans données"
```

Le commentaire est resté, l'entrée d'avant aussi. Un test le tient (proposé, CFG4) : sur chaque fichier
d'exemple, une opération puis son opération inverse rendent le fichier d'origine à l'octet.

**Livré par CFG4 (#1129, 24/11), sans bibliothèque ajoutée.** `glorfindel/config_edit.py` découpe le texte
là où la lecture de PyYAML met chaque nœud (`yaml.compose`, ses marques de début et de fin) : ce qui n'est
pas touché n'est jamais réécrit, ce qu'aucune bibliothèque aller-retour ne garantit (une indentation, une
largeur de ligne, un espacement normalisés). Trois gardes refusent avant toute écriture : le fichier doit
passer la lecture stricte (un fichier refusé se corrige à la main) ; le texte produit, relu par PyYAML, doit
être exactement le dictionnaire que l'opération demande (une ancre, une clé écrite deux fois, une mise en
page inconnue : refusé) ; le résultat passe la lecture stricte. Le condensé est le SHA-256 des octets
(`digest`, et `base` dans `edit_config`). La classe d'un changement est `glorfindel/config_class.py`, des deux
textes seuls (§5.3). `set_asset_mode`, `set_default_mode` et `glorfindel activate` y passent. **Les limites
connues** : l'octet près vaut pour un ajout ou un changement suivi de son inverse. Une section absente revient
de l'inverse vide (`exceptions: []`) ; une suppression (`unexclude`, `unset_mode`, `never_block_remove`) puis
son inverse rendent la même configuration, pas les mêmes octets : l'entrée revient en fin de liste, écrite
comme la console l'écrit, et un commentaire qui la précédait reste à sa place. Un scalaire en bloc (`|`,
`>`) garde ses commentaires : sa fin est son dernier caractère. Les opérations des réseaux, des zones et des
administrateurs attendus viennent avec leurs gestes (CFG7, CFG9).

### 3.3 La coexistence : la console, la CLI, la main, le push, l'IaC

**Proposé : un condensé du fichier sert de version.** C'est le SHA-256 de ses octets.

- **La console** lit le fichier, montre le diff, et met dans sa demande le condensé qu'elle a lu
  (`base`).
- **La watch** n'applique la demande que si le fichier a encore ce condensé. Sinon elle refuse,
  `config_changed`. La console relit et remontre le diff. C'est déjà la règle du push
  (`HOST_PUSH_RECHECK`) : changé entre deux lectures, rien n'est envoyé.
- **La CLI** (`glorfindel activate`, puis `glorfindel config`, proposé) garde son chemin direct : c'est
  l'issue de secours (FS1, Q4). Proposé : elle écrit par le même code (aller-retour, lecture stricte,
  même verrou), et **elle écrit sa ligne d'historique et son annonce** dans le répertoire de l'état
  (§4.3), avec `"by": {"via": "cli"}`. Dans le conteneur de la watch sur Imladris, c'est le même
  répertoire. Sur un poste (`make glorfindel-shell`), c'est celui du poste. Un relâchement par la CLI
  s'applique tout de suite (un geste sur l'hôte), mais il est annoncé fort.
- **Une édition à la main** (`sudoedit`) change le condensé. La watch le voit à sa lecture suivante :
  ce n'est pas une de ses écritures. Elle le dit (« glorfindel-config.yaml changed outside the
  console »), l'écrit dans l'historique avec le diff, l'auteur `outside`, et l'annonce sur Discord
  (décidé, Q9).
- **Un fichier refusé par A3** (une faute à la main) : la watch ne démarre pas, comme aujourd'hui. Une
  watch déjà en route tombe du côté prudent : `decide` met toutes les VM en `human_only` (G2), et une
  liste `never_block` illisible refuse tout blocage. La console montre les problèmes, chacun à son
  chemin. **Elle refuse toute modification tant que le fichier est refusé** : la correction se fait à
  la main, là où la faute a été faite.
- **`make imladris-push`** écrase aujourd'hui tout sauf les modes. Avec l'éditeur, il effacerait une
  exclusion posée sur Imladris. Il faut une règle. Décidé (Q3) : une fois l'édition ouverte, **le
  fichier d'Imladris devient la référence**. Le push refuse d'écraser une section changée sur Imladris
  depuis le dernier push, et dit laquelle. Une cible `make imladris-config-pull` rapatrie le fichier
  sur le poste. Le push passe aussi en aller-retour (CFG8).
- **Un fichier tenu par l'IaC du client** : une écriture de la console serait défaite au prochain
  `terraform apply`, sans bruit. Décidé (Q4) : le déploiement déclare le fichier « géré »
  (`EREGION_CONFIG_MANAGED=1`). La console prépare alors le diff, à coller dans le dépôt du client, et
  n'applique rien. Le diff garde la même classe et la même confirmation qu'une écriture.

### 3.4 L'historique et le retour arrière

**Proposé : `runs/glorfindel/config/history.jsonl`, écrit par la watch seule** (et par la CLI qui tourne
dans son conteneur). Une ligne par changement :

```json
{"at": "2026-11-24T09:22:03Z", "request": "<id>", "by": {"via": "console-token", "session": "3fa1c2d4"},
 "op": "exclude", "args": {"vm": "vm-dev-01", "rules": "all", "reason": "VM de dev, recréée chaque nuit"},
 "previous": null, "class": "relax", "before": "sha256:…", "after": "sha256:…",
 "diff": "@@ exceptions @@\n+  - asset_pattern: \"vm-dev-01\"…"}
```

- **L'opération et ses arguments font foi.** `previous` garde l'entrée visée telle qu'elle était avant
  (ici, aucune), lue par la lecture stricte. `diff` ne sert qu'à l'affichage : **il n'est jamais
  appliqué**.
- **Le retour arrière** est une demande comme une autre : « annuler la ligne `<id>` » (`op: revert`).
  La watch en dérive l'opération inverse, qui est dans la liste fermée : `exclude` ↔ `unexclude`,
  `never_block_add` ↔ `never_block_remove`, `set_mode` → `set_mode` avec le mode de `previous`, ou
  `unset_mode` s'il n'y avait pas d'entrée. Elle l'applique comme une opération neuve : même `base`,
  même lecture stricte, et elle la **reclasse**. Annuler un resserrement, c'est relâcher : la
  confirmation est demandée.
- **Une édition hors de la console** a sa ligne aussi, avec `"by": {"via": "outside"}`, le diff, et
  aucune opération. Elle ne s'annule pas depuis la console : elle se défait à la main.
- **Le journal est borné** (proposé : une taille maximale, les plus anciennes lignes archivées, comme
  les autres journaux de la watch).

---

## 4. La console demande, la watch écrit (FS1)

### 4.1 Le chemin

**Décidé (Q1) : la watch écrit le fichier, par la file signée, pour les clés autres que le mode** (le
mode : FS1, Q5, 04/11 ; jusqu'à CFG5, Q5 ci-dessous). La console
dépose, la watch vérifie, lit le résultat par la lecture stricte, et écrit. **Décidé (Q5) : jusqu'à
CFG5, la console continue d'écrire le mode directement, comme aujourd'hui.** Toute autre édition exige
la file, et aucun nouveau chemin d'écriture directe ne s'ouvre.

Le schéma du §0. La demande suit la file d'actions signée
([`file-actions-signee.md`](file-actions-signee.md)) : une clé Ed25519 par service, épinglée chez la
watch, un nonce, une vie de 120 s, un reçu signé par la watch.

**La demande proposée** :

```json
{
  "v": 1,
  "kind": "config_request",
  "id": "<128 bits aléatoires, hex>",
  "service": "console",
  "by": {"via": "console-token", "user": "", "name": "", "session": "<8 hex>"},
  "base": "sha256:<condensé du fichier que la console a lu>",
  "op": "exclude",
  "args": {"vm": "vm-dev-01", "rules": "all", "reason": "VM de dev, recréée chaque nuit"},
  "confirm": {"typed": "vm-dev-01", "code": ""},
  "issued_at": "2026-11-24T09:12:00.000+00:00",
  "expires_at": "2026-11-24T09:14:00.000+00:00",
  "key": "SHA256:<empreinte de la clé de la console>",
  "sig": "<Ed25519, base64>"
}
```

- **`op` vient d'une liste fermée**, fixée dans le code de la watch : `set_mode`, `unset_mode`,
  `set_default_mode`, `exclude`, `unexclude`, `never_block_add`, `never_block_remove`, `network_set`,
  `network_remove`, `zone_add`, `zone_remove`, `admin_add`, `admin_remove`, `revert`, `cancel`. Chacune a
  ses champs exacts dans `args`. **Jamais un morceau de YAML libre.**
- **La classe n'est pas dans la demande.** La watch la calcule (§5.3).
- **`confirm`** porte la preuve d'une confirmation pour un relâchement : le nom tapé, et, quand TOT1
  existe, son code, qui remplace le délai (décidé, Q2).

### 4.2 Ce que cela demande à FS1

FS1 est prêt, mais éteint par défaut (`EREGION_ACTION_QUEUE=1`). Proposé :

1. **Un nouveau genre de demande**, `config_request`, à côté de `request`. Ses champs sont exacts,
   comme ceux de `request` (un champ de plus refuse la demande), bornés à 4 Ko. Il a son propre domaine
   de signature (`eregion.config-request/1`) : une demande de configuration ne se lit jamais comme une
   action, ni l'inverse. Le nonce, la fraîcheur et le registre restent ceux de FS1.
2. **Rattachée au fichier, pas à une carte.** Une action de FS1 se rattache à une proposition que la
   watch a signée. Un changement de configuration se rattache au condensé `base`. Quand il part d'une
   carte (« Expect admin1's sudo here »), la carte est nommée en plus, pour l'historique.
3. **La dernière place dans la file.** Les demandes de configuration partagent la liste d'attente
   bornée (`BACKLOG = 32`, `queue_watch.py:66`). Proposé : elles passent après tout le reste, ce qui
   confine puis ce qui lève. Une rafale de changements ne retarde jamais une isolation.
4. **Les verbes par service.** La console peut tout demander. Le bot, rien en v1 (proposé). Un geste de
   configuration depuis Discord attend FS1g et TOT1.
5. **Le mode passe par la file : c'est déjà décidé.** Le Q5 de FS1 (Jonathan, 04/11) a mis le mode
   dans FS1f, prérequis avant toute VM hors du banc (`file-actions-signee.md`, §4.4 et « Les décisions
   de Jonathan »). Proposé (dans le sens de Q5, qui arrête l'écriture directe du mode à CFG5) :
   **CFG5 le porte**, avec ce genre de demande, et FS1f garde le reste de son
   périmètre (règles approuvées, acquittements, verdicts, `~/.glorfindel` en lecture seule).
6. **Les montages s'inversent, dans le même lot que le mode** (CFG5). La watch monte le fichier en
   écriture ; la console et le bot en lecture seule. Sinon, entre deux lots, la console monterait le
   fichier en `:ro` alors que le mode ne passerait pas encore par la file, et `set_asset_mode`
   échouerait. Proposé : le montage suit le drapeau de la file (une variable du compose), et le test des
   profils tient les deux formes. **FS1f, tel qu'il est écrit, ne le couvre pas** : il prévoit de monter
   `~/.glorfindel` en lecture seule, mais le fichier de configuration est un montage à part
   (`EREGION_CONFIG`) (§10).
7. **Le reçu** dit `applied`, `held` (un relâchement en attente, §4.4), `refused` (avec son code :
   `config_changed`, `config_refused`, `unknown_op`, `confirmation_missing`, `not_announced`,
   `expired`, `managed`), ou `cancelled`.
8. **Sur Imladris**, la watch écrit `~/eregion/glorfindel-config.yaml` en place, sous le verrou : le
   fichier est monté seul, et `_write_atomic` sait déjà le faire (`EBUSY`).
9. **Ce que la watch recharge.** Une exclusion et `expected_sudo` ne sont relues qu'au démarrage
   (§1.1). Proposé : après un changement appliqué, la watch recharge la config du `RulePoller`. Et elle
   publie ce qu'elle applique (`applied.json` : le condensé du fichier qu'elle tient pour chaque
   partie), que la console compare au fichier : « changed in the file, not applied yet » quand ils
   diffèrent (une édition à la main, par exemple).

### 4.3 L'état de la configuration : un répertoire que seule la watch écrit

**C'est le point le plus grave.** La console monte `~/.glorfindel` en écriture
(`docker-compose.yml:335`), jusqu'à FS1f. Si l'historique, l'attente d'un relâchement ou l'annonce y
vivaient, une console compromise pourrait :
- forger l'historique (un auteur, une raison, une date) ;
- écrire d'avance la clé de l'annonce, pour que le bot la croie déjà dite et se taise ;
- laisser courir le délai de 10 minutes sans qu'aucun humain l'ait vu.

**Proposé : tout cet état vit dans `runs/glorfindel/config/`**, le répertoire de la watch (SEC18 : un
répertoire par écrivain). La console le monte déjà en lecture seule (`runs/glorfindel`). Le bot reçoit
un montage en lecture seule de ce seul sous-répertoire, comme il monte déjà `runs/glorfindel/queue`.

| Fichier | Ce qu'il tient | Écrit par | Lu par |
|---|---|---|---|
| `history.jsonl` | chaque changement : l'opération, ses arguments, `previous`, la classe, les condensés, le diff montré | la watch (et la CLI dans son conteneur) | la console, la vue |
| `pending/<id>.json` | un relâchement en attente, signé par la watch sous un domaine à part, `eregion.config-pending/1`, distinct du battement SEC19 (L7) | la watch | la console (bannière, « Cancel »), le bot |
| `notices.jsonl` | les annonces de configuration : un genre à part, **sans VM** (pas `vm_notices`, qui suppose une VM et son fil) | la watch | le bot |
| `applied.json` | ce que la watch applique, par partie, et depuis quand | la watch | la console |
| `relaxed.json` | la vue « Relaxed », calculée par la watch (§6) | la watch | la console |

**L'annonce se prouve par le bot**, pas par la watch. Le bot poste l'annonce, puis note qu'il l'a postée
dans son propre répertoire (`runs/bot/config_said.jsonl`), que la watch monte déjà en lecture seule.
Une console compromise n'écrit ni l'un ni l'autre. **Un relâchement ne s'applique qu'une fois son
annonce notée par le bot** (§4.4). Trois règles (L1, CFG6) :
- le bot n'écrit `config_said` qu'après un envoi réussi à Discord ;
- il dédoublonne depuis `runs/bot/`, jamais depuis `~/.glorfindel`, qu'une console écrit encore ;
- il ne prend pas sa destination dans `bot_threads.json` (`~/.glorfindel`), qu'une console pourrait
  détourner vers un fil que personne ne lit.

Ce qui reste dans `~/.glorfindel`, donc à la portée d'une console compromise jusqu'à FS1f : le registre
de la découverte et l'état de la préparation (`readiness.json`). Le premier ne décide pas de la classe
(§5.3), mais il décide de la couverture des règles `auto_apply` au démarrage : une console compromise
peut y retirer une VM, que ces règles ne surveilleraient plus. FS1f le ferme. Le second reste la garde L6 d'aujourd'hui : un mode hardi passe
déjà par elle, et FS1f la ferme.

### 4.4 La vie d'un relâchement en attente

FS1 refuse une demande de plus de 120 s (`MAX_LIFETIME_S`, `eregion_core/action_queue.py:113`). Le
délai d'un relâchement (10 minutes, décidé Q2) est plus long. Proposé, pour le mécanisme :

1. **La demande vit 120 s, comme toute demande.** Dans ce temps, la watch la vérifie, la classe et,
   si elle relâche, la transforme en **attente** : `pending/<id>.json`, signé par la watch. Il garde
   l'opération, ses arguments, la `base`, la classe, l'auteur, l'échéance. Le reçu dit `held`, avec
   l'échéance.
2. **L'annonce part tout de suite** : la bannière de la console (lue dans `pending/`) et Discord (le
   bot, depuis `notices.jsonl`). L'humain voit venir le relâchement.
3. **L'annulation** : une demande `cancel` (console), ou `glorfindel config cancel <id>` (CLI). La watch
   retire l'attente, et le dit.
4. **À l'échéance**, sous le verrou du fichier :
   - la watch relit le fichier. Son condensé n'est plus la `base` ? Refus, `config_changed`, dit sur la
     console et sur Discord ; rien n'est écrit ;
   - elle recalcule la classe sur le fichier relu ;
   - elle vérifie que le bot a noté l'annonce (`runs/bot/config_said.jsonl`). Pas notée ? Refus,
     `not_announced`, et une carte : un relâchement ne passe jamais en silence, même si le bot est muet ;
   - elle applique, écrit l'historique, et annonce « applied ».
5. **L'attente survit à un redémarrage** : c'est un fichier, signé par la watch, relu au démarrage. Une
   attente dont l'échéance est passée depuis plus d'une heure (une watch longtemps arrêtée) est refusée,
   `expired`, et c'est dit : un relâchement n'est jamais appliqué des heures plus tard, quand plus
   personne ne le regarde.
6. **Une attente à la fois par objet** : une seconde demande sur le même objet est refusée tant que la
   première attend.

### 4.5 Ce que la file ne change pas

- **La CLI de l'opérateur** garde son chemin direct (FS1, Q4) : c'est l'issue de secours. Elle écrit
  par le même code, avec son historique et son annonce (§3.3).
- **La lecture stricte** reste la seule porte du fichier, quel que soit l'écrivain.

---

## 5. L'asymétrie entre resserrer et relâcher

### 5.1 Les mots

Le modèle est celui de l'enquête ([`enquete-raisonnee.md`](enquete-raisonnee.md), §3.4) : ce qui
resserre s'applique, ce qui relâche est une proposition qu'un humain confirme.

- **Resserre** : Glorfindel agit moins seul, ou voit et dit plus. Exemple : passer `vm-web-01` de
  `non_disruptive` à `human_only`.
- **Relâche** : Glorfindel agit plus seul, ou voit moins, ou dit moins. Exemple : exclure `vm-web-01`
  de `ssh-brute-force`.
- **Neutre** : sans effet sur la défense. Exemple : déclarer un réseau nommé que rien ne cite encore.

**Deux cas désarment pourtant la réponse en resserrant** ; Jonathan les a tranchés le 23/11 (Q10, Q11) :
- **`never_block`.** L'ajouter fait bloquer moins : la fiche le range dans « resserrer ». Mais le
  connecteur refuse ce blocage même après l'approbation d'un humain, et la validation accepte
  `0.0.0.0/1` plus `128.0.0.0/1` (elle ne refuse que `/0`) : deux entrées suffisent à couper tout
  blocage, sans confirmation. Décidé (Q10) : un ajout plus large qu'un hôte (/32, /128), ou d'une
  adresse publique, compte comme un relâchement ; un hôte privé seul resserre.
- **Un passage en masse en `human_only`** (le défaut, ou beaucoup de VM d'un coup). C'est le geste
  d'urgence ; mais une console compromise désarme ainsi toute la réponse. Il ne doit jamais passer sans
  bruit. Décidé (Q11) : il s'applique tout de suite, annoncé fort (§5.4).

### 5.2 Le classement de chaque clé (proposé, sauf ce que Q8, Q10 et Q11 ont décidé)

| Clé, geste | Classe | Dans la console ? |
|---|---|---|
| `autonomy.assets` : une entrée plus prudente que ce que la VM aurait sans elle | resserre | oui |
| `autonomy.assets` : une entrée plus hardie que le défaut, ou que ce que donnerait un motif (§5.3) | relâche (la préparation L6 en plus) | oui |
| `autonomy.assets` : retirer une entrée (`unset_mode`) | la classe de ce que la VM retrouve (le motif ou le défaut) | oui |
| `autonomy.default` : vers `human_only` | resserre, annoncé fort (décidé, Q11) | oui |
| `autonomy.default` : vers `non_disruptive` | relâche | oui |
| `exceptions` : ajouter une exclusion, pour tout nom visé (toutes les règles ou certaines) | relâche | oui |
| `exceptions` : retirer une exclusion | resserre | oui |
| `never_block` : ajouter une adresse | **décidé (Q10)** : un hôte privé seul (/32, /128) resserre ; un préfixe plus large ou une adresse publique relâche | oui |
| `never_block` : retirer une adresse | relâche (elle redevient bloquable) | oui |
| `networks` : déclarer un nom que rien ne cite | neutre | oui (SEC2b) |
| `networks` : changer ce que désigne un nom cité | la classe la plus relâchante de ses usages (§5.3) | oui |
| `network_zones.exposed` : ajouter une zone | relâche (le blocage seul y redevient possible) | oui (SEC2c) |
| `network_zones.exposed` : retirer une zone | resserre | oui |
| `network_zones.expected_origins` : ajouter une origine | relâche (des détections écartées) | oui (SEC2d, 0.7) |
| `network_zones.expected_origins` : retirer une origine | resserre | oui |
| `expected_sudo.admins` : ajouter une entrée, un compte, une origine | relâche | oui |
| `expected_sudo.admins` : en retirer | resserre | oui |
| `expected_sudo.sensitive_commands` : ajouter un texte | resserre | à préciser : hors des sept gestes (Q8) |
| `expected_sudo.origin_proof` : `none` → `bastion` ou `flows` | resserre | non en v1 (décidé, Q8) |
| `expected_sudo.origin_proof` : vers `none` | relâche | non en v1 (décidé, Q8) |
| `autonomy.allow_destructive` | relâche (si un jour lue) | **non** (§10) |
| `isolation.forensic_sources`, `forensic_ports` : ajouter | relâche (une VM isolée plus joignable) | non |
| `isolation.quarantine_nsg`, `quarantine_rg` | change le mécanisme | non |
| `memory.max_age_days` | neutre à la lecture, à mesurer | non |
| `monitoring_backends`, `action_backends`, `discovery` | retirer un backend ou couper la découverte relâche | non : le déploiement |

« Non » veut dire : montré en lecture seule, écrit à la main ou par l'IaC.

### 5.3 La classe suit le sens de la configuration

**Proposé : la watch classe selon la sémantique du fichier, pour tout nom visé, que la VM soit
découverte ou non.** Elle lit la configuration avant et après par la lecture stricte. **La découverte
ne sert qu'à la phrase d'effet**, jamais à la classe : le registre est à la portée d'une console
compromise (§4.3), et une VM absent du registre ce jour-là (pas encore découverte, retirée, éteinte)
rendrait son exclusion « neutre ».

Les règles :
- **Toute exclusion ajoutée relâche**, quel que soit le nom, découvert ou non.
- **Toute entrée exacte d'un mode plus hardi que `human_only` relâche, latente si elle ne change rien
  aujourd'hui.** Une entrée exacte l'emporte sur tout motif et sur le défaut (`AutonomyConfig.resolve`,
  `config.py:340-361`). Posée sous un motif, ou sous un défaut, qui donne déjà ce mode, elle ne change
  rien aujourd'hui, mais elle fait écran. Le jour où le motif repasse en `human_only`, ou le défaut par
  le geste d'urgence (Q11), la VM reste autonome. C'est un **relâchement latent**, classé comme tel.
- **Un réseau nommé prend la classe la plus relâchante de ses usages.** Cité dans `never_block` et dans
  `exposed`, on l'élargit : la zone exposée grandit, il relâche.
- **Un changement mêlé** (un resserrement et un relâchement) relâche.

Exemples :
- Défaut `human_only`, motif `vm-* : non_disruptive`. Une entrée `vm-web-01 : non_disruptive` :
  relâche (latent). Une entrée `vm-web-01 : human_only` : resserre.
- Défaut `non_disruptive`, aucun motif. Une entrée `vm-x : non_disruptive` : relâche (latent). Elle ne
  change rien aujourd'hui, mais un défaut repassé en `human_only` ne la tiendrait plus.
- `exclude` sur `vm-lab-07`, que la découverte ne connaît pas : relâche, et la phrase d'effet dit « not
  found by the discovery today ».

### 5.4 Resserrer s'applique simplement

Un clic, un reçu, c'est fait. Aucune confirmation, aucun délai. L'historique le garde, et Discord le
dit (une ligne) : **jamais sans bruit**.

C'est aussi **le geste d'urgence**. Une rafale de fausses alertes sur une VM ? On la passe en
`human_only` : tout de suite. On l'exclut ensuite, à froid, avec la confirmation.

Décidé (Q11) : un passage en masse en `human_only` (le défaut, ou un changement qui touche beaucoup de
VM) part tout de suite, mais il est **annoncé fort**, comme un relâchement : bannière et Discord,
« response disarmed on N VMs ».

**« En masse », compté en VM (CFG4b, #1136, décision de Jonathan du 24/11).** L'annonce forte vaut pour le
défaut passé en `human_only`, quel que soit le compte, ou quand **5 VM ou plus réellement touchées** passent
en `human_only` d'un coup : leur mode était plus hardi avant, il est `human_only` après. Un motif compte les
VM découvertes qu'il désigne ; un nom du fichier qu'aucune découverte ne connaît ne compte pas ; une VM déjà
en `human_only` n'est pas touchée. La classe reste une fonction pure des deux textes (`classify`, §5.3) :
seule l'annonce forte lit la découverte, dans une fonction à part, `loud(avant, après, vms)`
(`glorfindel/config_class.py`), qu'`edit_config` appelle avec les noms du registre de la découverte
(`discovered_assets.json`) et rend dans `loud` et `loud_said`. **Un registre vide ou illisible** (décision de
Jonathan du 24/11) : on retombe sur le compte en entrées, comme CFG4 (5 entrées ou plus, l'annonce est forte),
et l'annonce dit pourquoi — « the discovery's registry is absent », « could not be read », « the discovery
lists no VM », suivi de « counted by entry ». On ne perd jamais l'annonce. `AssetRegistry._load` avalant
toute erreur, `edit_config` lit d'abord le fichier lui-même : un registre absent, qui n'est pas du JSON, qui
n'est pas une liste, ou dont aucune entrée ne se charge, est illisible ; une liste lue sans VM est vide ; les
deux retombent sur les entrées. `loud(avant, après, None)` compte les entrées ; `loud(avant, après, [])`, une
liste lue sans VM, n'en compte aucune : c'est `edit_config` qui fait le repli. **Les deux comptes** : la clé
``loud`` de `classify` est comptée en entrées (CFG4), ce n'est pas l'annonce ; l'annonce est `loud()`, et
c'est elle que rend `edit_config`. **Pas encore** : la fenêtre de temps (5 VM en 10 minutes, sur plusieurs
demandes de la console) vient avec CFG5, et la bannière et le message Discord avec CFG6.

### 5.5 Relâcher passe par une confirmation explicite (décidé, Q2)

Q2 décide la confirmation (le nom tapé, la raison), l'annonce sur Discord prouvée par le bot, et le
délai de 10 minutes annulable, que le code de TOT1 remplacera. Le reste de ce paragraphe (la phrase
d'effet, la bannière, la vue) reste proposé.

1. **La console dit l'effet en une phrase**, calculée par le même code que la watch, et juste : « vm-dev-01
   ne sera plus surveillée par les 18 règles appliquées à toutes les VM. Les 2 règles écrites pour elle
   seule continuent. »
2. **La raison est obligatoire.** Elle va dans le fichier (`reason`) et dans l'historique.
3. **On tape le nom de l'objet** : `vm-dev-01`, ou `dmz`. C'est la forme de Dagorlad pour un fil
   destructif. La watch relit le nom tapé : la console ne le juge pas seule.
4. **C'est dit fort** :
   - une bannière sur la console, lue dans `pending/` puis dans l'historique, jusqu'à ce qu'un humain
     l'acquitte ;
   - une annonce sur Discord, postée par le bot depuis `notices.jsonl`, jamais par la console ;
   - la ligne de la vue « Relaxed » (§6).
5. **Un second facteur, ou un délai.** Décidé (Q2) :
   - **en v1, un délai** : le relâchement prend effet 10 minutes après la demande, annoncé dès la
     demande, annulable (§4.4). Une console compromise peut demander un relâchement, mais l'humain le
     voit venir, et rien ne passe si l'annonce n'a pas été postée ;
   - **avec TOT1**, le code à usage unique prévu pour le restore : un relâchement l'exige, et part tout
     de suite.

---

## 6. Tout ce qui est relâché reste visible

**Proposé : une vue « Relaxed », calculée par la watch** depuis le fichier et l'historique, écrite dans
`runs/glorfindel/config/relaxed.json`. La console la lit et l'affiche ; elle ne la calcule pas et ne
peut pas l'écrire.

```
RELAXED · 5                                                       ⚙ Config ▸ Relaxed
vm-dev-01      excluded from 18 auto rules    « VM de dev, recréée chaque nuit »   console · 3fa1c2d4 · 24/11 09:22
vm-dev-*       excluded from 1 rule           (no reason: hand-written)            outside · 12/11     · 3 VMs today
gondolin       non_disruptive                 « banc, préparation ready »          console · 01/11
dmz            exposed zone (/27)             « DMZ du partenaire »                console · 25/11 · ends 25/12
vm-ops-02      non_disruptive (pending)       « astreinte de nuit »                console · 24/11 · applies 09:32
```

- **Chaque ligne** : ce qui est relâché, l'objet, la raison, l'auteur (la session de la console, `cli`,
  ou `outside`), la date, l'échéance si elle en a une, et ce que désigne un motif aujourd'hui. Les
  attentes y sont aussi.
- **L'échéance, décidé (Q6)** : la console propose une échéance facultative (« until »). Ce qui n'en a
  pas revient en carte après 90 jours.
- **Une VM exclue ne disparaît jamais** :
  - sa carte reste sur la carte de l'infra, grisée, avec une bande « EXCLUDED from 18 auto rules —
    <raison> — since <date> ; 2 rules written for it still watch it » ;
  - une exclusion partielle : « EXCLUDED from ssh-brute-force » ;
  - l'Overview compte les VM exclues, à côté des autres chiffres ;
  - l'audit garde sa ligne, mais l'exclusion n'y est plus en vert : elle passe en jaune, et une règle
    écrite pour la VM n'y est plus comptée « exclue ».
- **Une entrée sans raison** (écrite à la main, ou d'avant CFG2) est montrée « no reason ».
- **Ce qui est dans le fichier mais pas encore appliqué** (une exclusion avant le rechargement) est dit
  à part, depuis `applied.json` (§4.2).
- **La watch le redit à son démarrage**, comme SEC2 le prévoit pour les réseaux nommés : chaque
  exclusion, chaque zone, chaque origine.

**Livré par CFG3 (#1139, 24/11)**, en lecture seule, sans aucune écriture du fichier.
`glorfindel/relaxed.py` calcule la vue depuis le fichier, par la lecture stricte, et la watch l'écrit dans
`runs/glorfindel/config/relaxed.json`, à son démarrage puis chaque minute. La console la lit
(`/api/config/relaxed`) et la montre sur `/config`, section « Relaxed ». Elle ne la calcule pas et ne
l'écrit pas : elle monte `runs/glorfindel` en lecture seule.

- **Ce qu'elle montre** : les exclusions ; le défaut et les modes hardis, latents compris ; le `never_block`
  du client ; les administrateurs attendus ; les accès d'enquête (`isolation.forensic_sources`, avec leurs
  ports) ; les zones exposées ; les réseaux nommés qu'une de ces lignes cite.
- **La classe est celle de CFG4.** Une entrée est dans la vue quand `classify` dit « relâche » du fichier sans
  elle vers le fichier avec elle. Une entrée qu'une autre donne déjà (une jumelle) ne change rien retirée
  seule : elle est alors classée seule dans sa liste, et montrée latente. Une entrée que `classify` ne
  sait pas classer est montrée, jamais cachée. Ce qui resserre n'y est pas : une entrée `human_only`, un
  hôte privé seul dans `never_block` (Q10), le défaut `human_only`, un réseau nommé que rien ne cite.
- **Chaque ligne** donne l'objet, ce qui est relâché, sa raison (`reason`, quand l'entrée en a une ; sinon
  « no reason »), l'auteur `unknown` et une date vide (l'historique de CFG5 les apportera), son chemin
  dans le fichier, et ce qu'elle désigne aujourd'hui. Pour un motif, ce sont les VM découvertes qu'il
  prend ; pour un mode, seulement celles dont il est le mode, jamais une VM qu'une autre entrée tient.
  Pour un nom exact, « found » ou « not found by the discovery today ». Pour un réseau nommé, ses plages.
- **Ce qui ne se lit pas est dit.** Un fichier refusé par la lecture stricte donne une vue sans entrées
  (`entries: null`) et la raison du refus. Un registre de la découverte illisible ou absent laisse les
  lignes, avec « not known » pour ce qu'elles désignent : la découverte ne décide jamais de la classe
  (§5.3). Une vue absente, illisible, ou vieille de plus de 5 minutes est dite. Un fichier changé depuis
  le calcul de la vue est dit aussi (son condensé diffère).
- **Pas encore** : les attentes (CFG6), l'échéance et le rappel à 90 jours (Q6), l'auteur et la date
  (CFG5), ce qui est écrit mais pas encore appliqué (`applied.json`, CFG5).
- **Hors de la vue, à confirmer (question à Jonathan)** : `sensitive_commands` et `origin_proof` (qui
  resserrent, §5.2), `allow_destructive` (qu'aucun code ne lit, §10), la découverte coupée
  (`discovery.enabled: false`) et le retrait d'un backend, qui relâchent pourtant (§5.2).
- **Le coût** : chaque entrée est classée sur le fichier entier, un coût qui croît comme le carré du
  nombre d'entrées (6,6 s pour 204 entrées, mesuré le 24/11). La watch calcule donc la vue dans un fil à
  elle, une passe à la fois, et ne la recalcule que si le condensé du fichier, le registre de la
  découverte ou la liste du réseau du client ont changé, ou toutes les 10 minutes. Entre deux calculs,
  elle réécrit la dernière vue avec son heure (`at`) : la vue reste « fresh ». Le premier calcul part
  dans ce fil au démarrage, sans le retenir.
- **Au démarrage**, une fois la vue écrite, la watch dit son compte puis ses lignes (vingt au plus,
  échappées), et l'avertissement de `--mode` si elle tourne avec : le mode par défaut de la session y est
  celui de `--mode`, quoi que dise le fichier. La vue le porte aussi (`override`), et la console le dit.

---

## 7. La frontière

### 7.1 Ce qui change

Écrire la configuration, c'est pouvoir désarmer les gardes : exclure une VM, rendre une autre
autonome, écarter des détections par une origine, couper les blocages par `never_block`. **C'est la
cible la plus précieuse de la console.**

La page « console » du modèle de menace ([`modele-de-menace.md`](modele-de-menace.md), §1) dit les
actions sur Azure et la demande d'exercice. **Elle ne dit pas que la console écrit le fichier de
configuration** (§10). Proposé, pour le lot qui ouvre l'écriture (CFG5) :

| | Menace | Ce qui la tiendrait (proposé) |
|---|---|---|
| T | Une console compromise relâche : elle exclut une VM, rend une VM autonome, déclare une origine | La watch écrit seule ; la demande est signée ; un relâchement attend son délai ou un second facteur ; il est annoncé sur Discord par le bot, et ne s'applique qu'une fois l'annonce notée par le bot ; la vue « Relaxed » le montre |
| T | Une console compromise relâche puis cache : elle forge l'historique, fait taire l'annonce, laisse courir le délai | L'historique, les attentes, les annonces et la vue vivent dans `runs/glorfindel/config/`, que la console ne monte qu'en lecture ; la preuve de l'annonce vit dans `runs/bot/`, que seul le bot écrit |
| T | Une console compromise désarme en resserrant : `never_block` large, tout en `human_only` | Décidé (Q10, Q11) : un ajout à `never_block` plus large qu'un hôte, ou public, relâche ; un passage en masse en `human_only` part tout de suite, annoncé fort (bannière et Discord) ; jamais sans bruit |
| T | Une console compromise fausse la classe par le registre de la découverte, qu'elle peut écrire | La classe suit la sémantique du fichier, jamais la découverte (§5.3) |
| T | Une console compromise vide le registre pour taire une mise en masse (CFG4b) | Le défaut en `human_only` est toujours fort, quel que soit le compte ; un registre vide ou illisible retombe sur le compte en entrées, et l'annonce le dit ; tout resserrement a sa ligne sur Discord (§5.4) ; après FS1f, la watch seule écrit la découverte |
| S | Une demande forgée, rejouée, périmée | Les contrôles de FS1 : signature, nonce, fraîcheur ; le domaine `eregion.config-request/1` ; une attente signée par la watch |
| T | Une demande sur une version périmée du fichier écrase une édition à la main | Le condensé `base`, relu à la demande et à l'échéance : `config_changed` |
| T | Une édition à la main passe sans trace | Le condensé relu par la watch : « changed outside the console », dans l'historique et sur Discord |
| T | Un retour arrière applique un diff choisi par la console | Le retour arrière est l'opération inverse, de la liste fermée ; le diff n'est jamais appliqué |
| T | Une demande rend le fichier illisible, ce qui met toutes les VM en `human_only` ou arrête la watch au redémarrage | Le résultat passe la lecture stricte avant l'écriture ; refusé, rien n'est écrit |
| R | Un changement sans auteur | L'historique de la watch : la session, la date, l'opération |
| E | Une opération écrit une clé hors de sa portée | Une liste fermée d'opérations, des champs exacts, jamais du YAML libre |
| D | Une rafale de demandes retarde une isolation | La dernière place dans `BACKLOG` ; une attente à la fois par objet |
| I | La configuration nomme des comptes et des plages | Rien de nouveau : la console les montre déjà à l'opérateur ; rien ne quitte l'hôte, sauf l'annonce Discord, qui nomme l'objet et la classe, jamais un compte (proposé) |

### 7.2 Ce qui reste ouvert

- **Une console compromise signe comme la console** (FS1, §3.2). Sans second facteur, le délai et
  l'annonce prouvée par le bot sont ce qui la tient. Avec TOT1, il lui faut aussi le téléphone de
  l'opérateur.
- **Jusqu'à FS1f**, la console écrit encore `~/.glorfindel` : la découverte (sans effet sur la classe,
  mais elle compte les VM de l'annonce forte, CFG4b, et elle décide de la couverture des règles
  `auto_apply` au démarrage) et la préparation (la garde L6 d'aujourd'hui).
- **Drapeau éteint, ce qui est le défaut** (L5), la console monte encore le fichier en écriture. Seule la
  détection d'une édition hors de la console (Q9) la voit : une écriture de la console sans la file
  apparaît « outside ».
- **Sans le bot** (L6), un profil facultatif, tout relâchement est refusé, `not_announced` : c'est fermé
  par défaut, et c'est assumé. Un resserrement passe toujours.
- **Root sur Imladris** édite le fichier : c'est le même périmètre qu'aujourd'hui. La différence : la
  watch le voit et le dit.
- **Le choix assumé** (« un jeton, tous les droits de la console ») deviendrait : « un jeton, tous les
  resserrements ; relâcher demande en plus le délai, ou le second facteur ».

---

## 8. Les questions à Jonathan

Une à la fois, dans l'ordre. L'option recommandée vient en premier. **Toutes tranchées le 23/11, en
interactif** : chaque fois l'option recommandée. Les options restent, pour l'historique de la décision.

**Q1. Qui écrit le fichier, pour les clés autres que le mode ?** Le mode est déjà tranché : il passe par
la file (FS1, Q5, 04/11) ; proposé, CFG5 le porte (voir Q5).
1. **La watch, par la file signée** (recommandé). La console dépose, la watch vérifie et écrit. C'est la
   direction de FS1 : seule la watch écrit.
2. La console, directement, mais en aller-retour (les commentaires gardés). Plus simple, mais une
   console compromise désarme les gardes sans passer par la watch.
3. Un petit service à part, seul à monter le fichier en écriture. Un conteneur de plus, pour peu de
   gain sur l'option 1.

**Décision de Jonathan (23/11) :** la watch, par la file signée (option 1). La console dépose, la watch
vérifie, lit le résultat par la lecture stricte, et écrit.

**Q2. Quelle preuve pour relâcher ?**
1. **En v1, la confirmation (le nom tapé, la raison), l'annonce sur Discord prouvée par le bot et un
   délai de 10 minutes, annulable ; puis le code de TOT1 quand il existe, qui remplace le délai**
   (recommandé).
2. Le code de TOT1 dès le début : aucun relâchement depuis la console avant TOT1.
3. La confirmation et l'annonce seules, sans délai ni code.

**Décision de Jonathan (23/11) :** option 1. En v1, la confirmation (le nom tapé, la raison), l'annonce
sur Discord prouvée par le bot, et un délai de 10 minutes annulable ; quand TOT1 existe, son code
remplace le délai.

**Q3. Que devient `make imladris-push` quand la console édite le fichier ?**
1. **Le fichier d'Imladris devient la référence.** Le push refuse d'écraser une section changée sur
   Imladris depuis le dernier push, et dit laquelle ; `make imladris-config-pull` rapatrie le fichier ;
   le push passe en aller-retour (recommandé).
2. Le push fusionne section par section, comme il le fait déjà pour les modes.
3. Le push écrase comme aujourd'hui (sauf les modes) : une édition de la console vit jusqu'au push
   suivant.

**Décision de Jonathan (23/11) :** option 1. Le fichier d'Imladris devient la référence ; le push refuse
d'écraser une section changée sur Imladris depuis le dernier push, et dit laquelle ;
`make imladris-config-pull` rapatrie le fichier, et le push passe en aller-retour.

**Q4. Et un fichier tenu par l'IaC du client ?**
1. **Le déploiement le déclare géré (`EREGION_CONFIG_MANAGED=1`) : la console prépare le diff à coller
   dans le dépôt du client, et n'applique rien** (recommandé).
2. La console écrit quand même ; le prochain `terraform apply` la défait.
3. Pas en v1.

**Décision de Jonathan (23/11) :** option 1. Le déploiement le déclare géré
(`EREGION_CONFIG_MANAGED=1`) ; la console prépare le diff à coller dans le dépôt du client, et n'applique rien.

**Q5. Sans la file (le défaut d'aujourd'hui) ?**
1. **Le mode reste écrit directement par la console, comme aujourd'hui, jusqu'à CFG5. Toute autre
   édition exige la file** (recommandé). Aucun nouveau chemin d'écriture directe.
2. Toute édition directe, en aller-retour, jusqu'à CFG5.

**Décision de Jonathan (23/11) :** option 1. Jusqu'à CFG5, la console continue d'écrire le mode
directement, comme aujourd'hui ; toute autre édition exige la file, et aucun nouveau chemin d'écriture
directe ne s'ouvre.

**Q6. Un relâchement a-t-il une échéance ?**
1. **Une échéance facultative, posée par la console (« until »), et un rappel en carte après 90 jours
   pour ce qui n'en a pas** (recommandé). Les leçons de l'enquête qui relâchent sont datées ; une VM
   de dev exclue l'est souvent pour toujours.
2. Une échéance obligatoire (90 jours par défaut), renouvelable d'un clic.
3. Aucune échéance.

**Décision de Jonathan (23/11) :** option 1. La console propose une échéance facultative (« until ») ;
ce qui n'en a pas revient en carte après 90 jours.

**Q7. Les motifs ?**
1. **La console n'écrit que des noms exacts. Un motif écrit à la main est montré, avec ce qu'il désigne
   aujourd'hui** (recommandé).
2. La console accepte un motif, avec l'aperçu des VM qu'il prend aujourd'hui.

**Décision de Jonathan (23/11) :** option 1. La console n'écrit que des noms exacts ; un motif écrit à
la main reste lu, et la console le montre avec ce qu'il désigne aujourd'hui.

**Q8. Jusqu'où va la console en v1 ?**
1. **Les sept gestes du §2 ; le reste en lecture seule** (`isolation`, `memory`, les backends,
   `origin_proof`, `allow_destructive`) (recommandé).
2. Toutes les clés du fichier.
3. Les gestes du temps 1 de SEC2 seulement (mode, exclusion, `never_block`, réseaux nommés, zone
   exposée) ; les administrateurs et les origines avec la 0.7.

**Décision de Jonathan (23/11) :** option 1. Les sept gestes du §2 ; le reste (`isolation`, `memory`,
les backends, `origin_proof`, `allow_destructive`) reste en lecture seule.

**Q9. Une édition à la main, vue par la watch ?**
1. **Dite sur Discord et dans l'historique, avec son diff, l'auteur « outside »** (recommandé).
2. Dite dans la console seulement.

**Décision de Jonathan (23/11) :** option 1. Elle est dite sur Discord et dans l'historique, avec son
diff, sous l'auteur « outside ».

**Q10. Un ajout à `never_block` resserre-t-il ?** Il fait bloquer moins, mais le connecteur refuse même
un blocage approuvé, et `0.0.0.0/1` plus `128.0.0.0/1` passent la validation.
1. **Un ajout plus large qu'un hôte (/32, /128), ou d'une adresse publique, compte comme un
   relâchement ; un hôte privé seul resserre** (recommandé). Comme les plages privées sont déjà
   livrées, presque tout ajout passe par la confirmation.
2. Tout ajout relâche.
3. Tout ajout resserre, comme dans la fiche, mais la lecture stricte refuse un préfixe plus large
   qu'un seuil (un /16, par exemple), quel que soit l'écrivain.

**Décision de Jonathan (23/11) :** option 1. Un ajout plus large qu'un hôte (/32, /128), ou d'une
adresse publique, compte comme un relâchement ; un hôte privé seul resserre.

**Q11. Un passage en masse en `human_only` ?**
1. **Il part tout de suite, mais il est annoncé fort : bannière et Discord, « response disarmed on N
   VMs »** (recommandé). C'est le geste d'urgence ; il ne passe jamais sans bruit.
2. Au-delà d'un seuil de VM (ou pour le défaut), il compte comme un relâchement : confirmation et délai.
3. Comme tout resserrement : une ligne sur Discord.

**Décision de Jonathan (23/11) :** option 1. Il s'applique tout de suite, mais il est annoncé fort : une
bannière et un message Discord, « response disarmed on N VMs ».

---

## 9. Les lots de code proposés

Dans l'ordre. Les estimations sont en jours de travail effectif, à ±50 %, comme la ROADMAP. Chaque lot
demande sa plage de mutants à l'Orchestre.

| Lot | Contenu | Ce qu'il prouve | Dépend de | Mutants | Sessions | Estimation |
|---|---|---|---|---|---|---|
| **CFG2** | **L'exclusion visible.** La clé `exceptions[].reason` (facultative, lue strictement ; une clé nouvelle refusée par une version antérieure, dit dans la doc). `/api/state` porte l'exclusion de chaque VM, et ce qu'elle ne couvre pas (les règles écrites pour la VM). La carte grisée et sa bande, l'Overview qui compte, la ligne d'audit en jaune et juste. Aucune écriture. | Une VM exclue, par son nom ou par un motif, ne disparaît jamais en silence ; la bande et l'audit disent les règles qui la surveillent encore. | rien | ~5 : la bande absente sous un motif ; l'exclusion partielle lue comme totale ; la bande qui dit « toutes les règles » alors qu'une règle écrite pour la VM la surveille ; l'audit qui compte « exclue » une règle hors `auto_apply` ; la raison non échappée | Console, Glorfindel | 1–2 j |
| **CFG4** | **L'écriture aller-retour.** Livré sans bibliothèque (§3.2) ; `apply_change(texte, op) → texte` pour la liste fermée, et l'inverse de chaque opération ; la lecture stricte du résultat ; le condensé ; la classe selon la sémantique (fonction pure, sans la découverte), livrée ici et reprise par CFG3 (L3) ; `set_asset_mode`, `set_default_mode` et `glorfindel activate` y passent. | Les commentaires restent ; une opération puis son inverse rendent le fichier à l'octet ; un résultat refusé n'est jamais écrit ; la classe ne dépend ni de la découverte ni du nom de l'opération. | rien | ~10 : un commentaire perdu ; une écriture sans relecture stricte ; un motif écrit au lieu d'un nom ; un relâchement classé resserrement ; un changement mêlé classé resserrement ; une exclusion d'une VM non découverte classée neutre ; une entrée exacte sous un motif de même mode classée neutre ; une entrée exacte de même mode que le défaut classée neutre ; un inverse faux | Glorfindel | 3 j |
| **CFG3** | **La vue « Relaxed », en lecture seule**, calculée par la watch dans `runs/glorfindel/config/relaxed.json`, lue par la console : exclusions, modes hardis (latents compris), `never_block` du client, administrateurs attendus, accès d'enquête ; puis, avec SEC2, zones et origines. Ce que désigne chaque motif. Sans historique encore : l'auteur « unknown ». La classe vient de la fonction pure de CFG4. | Tout ce qui relâche est montré, à partir du fichier seul, par un écrivain que la console n'est pas. | CFG4 (la classe, fonction pure) | ~5 : un relâchement latent absent de la vue ; la vue écrite par la console ; un motif sans ce qu'il désigne | Glorfindel, Console | 2 j |
| **CFG5** | **La demande par la file, et le mode avec elle.** Le genre `config_request` dans `eregion_core/action_queue.py`, son domaine, ses champs exacts, la dernière place dans `BACKLOG` ; la watch l'applique (CFG4) ; `config_changed` ; le répertoire `runs/glorfindel/config/` (`history.jsonl`, `applied.json`) et le montage du bot ; les routes de mode passent par la file (pris à FS1f) ; les montages du fichier inversés derrière le drapeau, dans ce lot ; la CLI qui écrit son historique ; la relecture des exclusions et d'`expected_sudo` après un changement ; l'édition hors de la console vue et dite ; le modèle de menace (§7.1). **Jusqu'à CFG6, la file refuse tout relâchement autre que le mode** (L2). **CFG5 hérite du statut de prérequis de FS1f avant toute VM hors du banc** (FS1, Q5, 04/11), puisqu'il en reprend le mode (L4). | Seule la watch écrit le fichier et son état ; une demande sur une version périmée est refusée ; chaque changement a sa ligne ; le mode marche avec et sans le drapeau ; un changement appliqué est tenu par la watch sans redémarrage. | CFG4, la file mesurée au banc (FS1c) ; Q1 et Q5 tranchées (23/11) | ~13 : l'historique écrit hors de `runs/glorfindel/` ; la `base` ignorée ; une demande de configuration avant une isolation ; le mode cassé sous `:ro` ; une exclusion non rechargée ; une édition à la main sans ligne ; la CLI sans historique ; un relâchement hors du mode accepté avant CFG6 | Glorfindel, Console | 4–5 j |
| **CFG6** | **L'asymétrie.** L'attente signée par la watch (`pending/`), qui survit au redémarrage ; à l'échéance, la `base` relue et la classe recalculée sous le verrou ; `notices.jsonl`, un genre d'annonce sans VM, et la preuve du bot (`runs/bot/config_said.jsonl`) ; l'attente signée sous `eregion.config-pending/1` (L7) ; le bot qui n'écrit `config_said` qu'après un envoi réussi, dédoublonne depuis `runs/bot/` et ne prend pas sa destination dans `bot_threads.json` (L1) ; la confirmation (nom tapé, raison) relue par la watch ; le délai ou le code (Q2) ; l'annulation ; le retour arrière par l'opération inverse, reclassé ; l'annonce forte du passage en masse (Q11) ; la classe de `never_block` (Q10). | Un relâchement n'est jamais appliqué sans sa confirmation, avant son délai, ni sans son annonce postée ; une attente périmée ou sur un fichier changé est refusée et dite ; un resserrement l'est tout de suite, jamais sans bruit. | CFG5 ; Q2, Q10, Q11 tranchées (23/11) | ~12 : le délai sauté ; la confirmation non relue par la watch ; l'annonce non exigée ; la `base` non relue à l'échéance ; une attente périmée appliquée au redémarrage ; un retour arrière par diff ; un resserrement en masse sans annonce ; `config_said` écrit sans envoi réussi ; une attente lue sous le domaine du battement | Glorfindel, Console, bot | 3–4 j |
| **CFG7** | **Les gestes de la console** : exclusion, `never_block` depuis une IP découverte, administrateurs attendus depuis une carte de sudo ; la phrase d'effet juste. | Chaque geste écrit le nom exact de l'objet cliqué, par `_post` et la file ; rien du dehors écrit brut (#254). | CFG6 ; Q7, Q8 tranchées (23/11) | ~6 | Console | 3 j |
| **CFG8** | **La coexistence avec le push et l'IaC** (Q3, Q4) : `host_config.py` en aller-retour, `imladris-push` qui refuse d'écraser, `imladris-config-pull`, le mode « géré » et son diff. | Aucune édition d'Imladris perdue par un push ; les commentaires restent au push ; un fichier géré n'est jamais écrit par la watch. | CFG4 ; Q3, Q4 tranchées (23/11) | ~5 | Infra (Imladris), Glorfindel | 2–3 j |
| **CFG9** | **Les réseaux et les zones dans la console** : choisir un VNet ou un sous-réseau découvert ; le changement de ce qu'un nom désigne, dit. Les plages résolues par `{subnet:}` et `{vnet:}` ne se lisent jamais dans un fichier que la console écrit : elles vivent dans l'état de la watch, ou sont relues dans Azure. Les origines attendues avec SEC2d (0.7). | Une zone ne s'élargit jamais en silence ; un nom introuvable est dit ; une plage forgée dans le registre de la découverte n'élargit rien. | SEC2b, SEC2c (SEC2d pour les origines), CFG7 | ~7 | Console, Glorfindel | 2–3 j |

**Total** : de 20 à 25 jours, environ 63 mutants. CFG2 et CFG4 ne dépendent de rien et peuvent partir
tout de suite ; CFG3 suit CFG4, dont il reprend la classe (L3). CFG5 et la suite attendaient les réponses à Q1 et Q5 : elles sont tranchées (23/11). Il leur reste la
file mesurée au banc (FS1c).

**FS1f se resserre** (proposé) : le mode passe à CFG5 ; FS1f garde les règles approuvées, les
acquittements, les verdicts et `~/.glorfindel` en lecture seule (la découverte, la préparation, les
fils du bot compris).

**Les limites connues**, chacune tenue par un lot ou assumée :
- **L1** (CFG6) : le bot n'écrit `config_said` qu'après un envoi réussi à Discord, dédoublonne depuis
  `runs/bot/`, jamais depuis `~/.glorfindel`, et ne prend pas sa destination dans `bot_threads.json`.
- **L2** (CFG5) : jusqu'à CFG6, la file refuse tout relâchement autre que le mode.
- **L3** : la classe, fonction pure, est livrée par CFG4, avant CFG3 qui la reprend.
- **L4** (CFG5) : CFG5 hérite du statut de prérequis de FS1f avant toute VM hors du banc (FS1, Q5,
  04/11), puisqu'il en reprend le mode.
- **L5** (§7.2) : drapeau éteint, ce qui est le défaut, la console monte encore le fichier en écriture ;
  seule la détection d'une édition hors de la console (Q9) la voit.
- **L6** (§7.2) : sans le bot, un profil facultatif, tout relâchement est refusé (`not_announced`) :
  fermé par défaut, assumé.
- **L7** (CFG6) : l'attente est signée sous un domaine à part, `eregion.config-pending/1`, distinct du
  battement SEC19.

---

## 10. Ce que la note a trouvé dans le code et la doc

Relevé sans rien corriger (la note ne touche aucun code ni aucune autre doc) :

1. **`autonomy.allow_destructive` n'est lue par aucun code de Glorfindel.** Seuls `config.py` la parse,
   `host_config.py` la vide et la console l'affiche. Or la console la range parmi les **actions
   autonomes** (`glorfindel.js`, `_capabilityHtml`), comme une liste de noms d'actions. Le commentaire
   d'A3 (`config.py`) la lit, lui, comme des motifs de VM (« `vm-*` »). Le sens de la clé n'est pas fixé,
   et la console promet ce que l'agent ne fait pas. À trancher par Glorfindel : la câbler, ou la retirer.
2. **`docs/design/file-actions-signee.md`, §1.5** range « le mode d'une VM » parmi ce que la console
   écrit dans `~/.glorfindel`. Le mode est écrit dans `glorfindel-config.yaml`, un montage à part
   (`EREGION_CONFIG`), en écriture chez la console, en lecture seule chez la watch. **FS1f**, tel qu'il
   est écrit (« la console et le bot montent `~/.glorfindel` en lecture seule »), ne fermerait donc pas
   l'écriture de la configuration par la console.
3. **La page « console » du modèle de menace** (§1) ne dit pas que la console écrit le fichier de
   configuration. Elle range « passer un actif en `non_disruptive` » parmi les actions qui touchent Azure,
   alors que ce geste écrit un fichier local que la watch relit à chaque cycle. Et son « Ouvert : rien de
   connu » tient sans cette écriture.
4. **`glorfindel-config.yaml.example` n'a pas de section `isolation`**, alors que la lecture stricte
   connaît ses quatre clés (`quarantine_nsg`, `quarantine_rg`, `forensic_sources`, `forensic_ports`),
   et que `docs/operations.md` les liste.
5. **`docs/operations.md`, « Clés connues »**, ne cite ni `memory` (SEC17) ni `origin_proof` (COR2) dans
   sa liste de tête, alors que les deux sont lues et documentées plus bas ou dans l'exemple.
6. **L'écriture du mode** (`_update_config`) n'est pas relue par la lecture stricte avant d'être
   écrite. Elle ne peut pas créer une clé inconnue, mais elle réécrit sans le dire un fichier déjà
   refusé.
7. **Les exclusions ne valent que pour les règles `auto_apply`** (`detection_rules.py:1883-1897`) : une
   règle écrite pour une VM (`assets: [<resource_id>]`) la surveille encore. Or l'audit la compte
   « exclue » (`audit.py:333-341`), et l'exemple de config dit « exclude all dev VMs from all rules ». CFG2 le corrige dans ce que la console montre.
8. **Une exclusion et `expected_sudo` ne prennent effet qu'au redémarrage de la watch** : le
   `RulePoller` garde la config lue au démarrage (`watch/rules.py:115`, `:189` ;
   `detection_rules.py:1955`). Aucune doc ne le dit ; l'exemple invite à éditer par `sudoedit`, sans
   relancer.
9. **`validate_never_block` ne refuse que `/0`** : `0.0.0.0/1` et `128.0.0.0/1` passent, et couvrent à
   eux deux toute l'IPv4. Q10, tranchée le 23/11 : un tel ajout compte comme un relâchement.
