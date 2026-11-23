# La configuration dans la console (CFG1, #1090) — conception

_Note de conception, sans code, 23/11. Décision de Jonathan du 23/11 : « Il faudra vraiment muscler la
partie config dans l'interface avec le fichier de conf et le discovery. On ne peut pas demander à un
utilisateur d'aller modifier un fichier yaml à la main. » La note maintenant, le code après. **Rien
n'est décidé ici au-delà de ce que Jonathan a déjà tranché** : chaque choix porte le mot « proposé »,
et les questions du §8 attendent sa réponse._

Les décisions de SEC2 du 23/11 (réseaux nommés, zone exposée, origines attendues) enrichissent la
configuration. Cette note dit comment la console l'écrira sans devenir une seconde source de vérité,
ni la cible qui désarme les gardes.

---

## 0. En bref

- **Aujourd'hui**, la console ne règle que le mode : celui d'une VM, et le défaut. Elle réécrit le
  fichier elle-même, par `yaml.safe_dump` : les commentaires sont perdus. Tout le reste se fait à la
  main, par `sudoedit` sur Imladris, ou sur le poste puis `make imladris-push`.
- **Proposé : la console part de ce qui est découvert.** On clique une VM, un VNet, une IP publique.
  On ne tape plus un CIDR ni un motif.
- **Proposé : le fichier reste la référence.** Il reste lisible, relu, versionnable. La console est un
  éditeur au-dessus du fichier. Elle garde les commentaires et l'ordre des clés.
- **Proposé : la console demande, la watch écrit.** La console dépose une demande signée dans la file
  d'actions (FS1). La watch la vérifie, relit le résultat avec la lecture stricte (A3), l'écrit, et
  garde l'historique.
- **Proposé : resserrer s'applique, relâcher se confirme.** Un mode plus prudent part tout de suite.
  Une exclusion, une origine attendue, un mode plus hardi demandent une confirmation, et c'est dit fort.
- **Proposé : tout ce qui est relâché reste visible.** Une vue le montre, avec sa raison, sa date et son
  auteur. Une VM exclue ne disparaît jamais en silence.

Le parcours d'un changement, de bout en bout (proposé) :

```
 opérateur, dans le navigateur (jeton SEC1)
   │  clic sur la carte de vm-dev-01 : « Exclure de toutes les règles »
   │  raison : « VM de dev, recréée chaque nuit »
   ▼
 console ── lit le fichier (en lecture seule), montre le diff, note son condensé « base »
   │  dépose une demande signée par sa clé (FS1)
   ▼
 runs/console/queue/<id>.json      kind: config_request · op: exclude · base: sha256:…
   │  (monté en lecture seule chez la watch)
   ▼
 watch ─ signature → fraîcheur → nonce → op d'une liste fermée
       ─ base = condensé du fichier actuel ?          non → refus « config_changed »
       ─ applique l'op au texte, commentaires gardés
       ─ lecture stricte (A3) du résultat              refusé → rien n'est écrit
       ─ classe l'effet : resserre / relâche / neutre  (calculé, jamais lu dans la demande)
       ─ relâche ? la confirmation y est ?             non → en attente, dit
       ─ écrit le fichier (verrou, remplacement atomique ou en place)
   ▼
 glorfindel-config.yaml              ~/.glorfindel/config_history.jsonl
 (la watch seule l'écrit)            qui, quand, le diff, les deux condensés, la classe
   │                                    │
   ▼                                    ▼
 reçu signé                          annonce de la watch → bot → Discord
 runs/glorfindel/queue/console-<id>.json      « relâché : vm-dev-01 exclue de toutes les règles »
   ▲ suivi par la console (GET /api/queue/<id>), puis la carte grisée « EXCLUDED »
```

---

## 1. L'inventaire d'aujourd'hui

Lu dans le code le 23/11 : `glorfindel/config.py` (la lecture stricte A3, `_parse_config`),
`glorfindel-config.yaml.example`, `docs/operations.md` (« Configuration »), `eregion_console/api.py`,
`eregion_console/static/glorfindel.js`, `docker-compose.yml`, `Makefile` (`imladris-push`) et
`infra/glorfindel-host/host_config.py`.

### 1.1 Les clés du fichier

« Relue » dit quand la watch relit la clé : un changement prend effet à ce moment-là.

| Clé | Ce qu'elle fait | Qui l'écrit | Ce que la console en montre | Relue |
|---|---|---|---|---|
| `monitoring_backends[]` : `name`, `type`, `workspace_id`, `endpoint`, `discovery.enabled`, `discovery.interval_s` | Les sources de détection et de découverte (Heartbeat). | La main ; le fragment de Celebrimbor (`make celebrimbor-output`) pour le banc. | `/api/config` : nom, type, découverte. La carte de l'infra (DETECT). | Au démarrage de la watch. |
| `action_backends[]` : `name`, `type`, `vault_name`, `resource_group`, `restore_staging_storage` | Le coffre du restore et son compte de transit. | La main. | Nom, type, coffre. | À chaque restore (`resolve_backup_vault`). |
| `exceptions[]` : `asset_pattern`, `exclude_all`, `exclude_rules` | Retire une VM (motif fnmatch, casse ignorée) de toutes les règles, ou de certaines. `posture` compte comme une règle. | La main. | `exceptions_count` dans `/api/config`, que la page n'affiche pas. L'audit d'une VM compte ses règles « exclues », en vert, sans raison. | Au démarrage : le `RulePoller` garde la config qu'il a lue. |
| `autonomy.default` | Le mode par défaut. | La main ; la console (`PATCH /api/config/autonomy/default` → `set_default_mode`). `imladris-push` le force à `human_only`. | Le menu de `/config`. | À chaque cycle (`decide`). |
| `autonomy.assets[]` : `match`, `mode` | Le mode d'une VM ou d'un motif. | La main ; la console (`POST /api/autonomy/<vm>`, `/api/activate/<vm>` → `set_asset_mode`, un nom exact). `imladris-push` garde ceux d'Imladris (BL1c). | Le badge et le menu de la carte : le mode effectif, avec la préparation (L6). | À chaque cycle. |
| `autonomy.allow_destructive` | Annoncé : les actions destructives permises seules. | La main ; `imladris-push` la vide. | `/api/state.capability` la range parmi les actions autonomes. | **Aucun code de Glorfindel ne la lit** (§10). |
| `isolation.quarantine_nsg`, `quarantine_rg` | Le mécanisme de la quarantaine. | La main. | Rien, sauf par la préparation. | À chaque isolation. |
| `isolation.forensic_sources`, `forensic_ports` | L'accès d'enquête à une VM isolée. | La main. | Rien. | À chaque isolation. |
| `never_block` | Les adresses jamais bloquées, en plus des livrées (SEC2). | La main. | Rien. Une carte `protected_address` dit la raison d'un blocage retenu. | À chaque blocage. |
| `expected_sudo` : `admins[]` (`match`, `accounts`, `origins`), `sensitive_commands`, `origin_proof` | Les sudo attendus des administrateurs (ADM1, COR1, COR2). | La main, par `sudoedit` sur Imladris. | Le compte des sudo écartés, dans la règle. | À vérifier. |
| `memory.max_age_days` | L'âge au-delà duquel un cycle n'est plus un précédent (SEC17). | La main. | Rien. | À chaque recherche. |

**Les clés que SEC2 ajoute** (décisions du 23/11 ; rien n'est encore dans le code) :

| Clé | Lot | Ce qu'elle fera |
|---|---|---|
| `networks` (nom → CIDR, ou `{subnet: "<vnet>/<sous-réseau>"}`, ou `{vnet: "<nom>"}`) | SEC2b | Des réseaux nommés, déclarés une fois, cités par leur nom. Un nom d'objet se résout par la découverte, en nom exact, jamais un motif. |
| `network_zones.exposed` | SEC2c | Une zone exposée (une DMZ, un partenaire) : le blocage seul y redevient possible, à deux conditions. |
| `network_zones.expected_origins` | SEC2d, 0.7 | Une origine attendue : une détection qui en vient est écartée, dite et comptée. |

**Hors du fichier, et hors de cette note** :
- les variables d'environnement du déploiement (`GLORFINDEL_READ_ONLY`, `GLORFINDEL_CONFIDENCE_THRESHOLD`,
  `GLORFINDEL_ISOLATION_TTL_H`, `GLORFINDEL_LLM_MODEL`…). La page Config le dit déjà pour le modèle :
  « Not a setting of this page ». Proposé : elles le restent ;
- les règles du client (`~/.glorfindel/client_rules.yaml`, P1). La console les écrit déjà par
  `approve-rule`. FS1f prévoit de les faire passer par la file.

### 1.2 La découverte

- `glorfindel/discovery.py` lit les VM par le Heartbeat de chaque backend de surveillance. Chacune a un
  nom, un `resource_id`, son backend, `last_seen`, sa source, son type (`vm`, `vmss_instance`), son
  parent. Le registre vit dans `~/.glorfindel/discovered_assets.json`.
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

Il y a déjà trois écrivains, et un quatrième possible :

```
 poste : glorfindel-config.yaml local ── make imladris-push ──┐  (host_config.py : défaut forcé à
                                                               │   human_only, allow_destructive
 Imladris : sudoedit ~/eregion/glorfindel-config.yaml ─────────┼─► vidée, modes d'Imladris gardés,
                                                               │   relu juste avant l'envoi)
 console : set_asset_mode, set_default_mode ───────────────────┤
                                                               │
 (demain) l'IaC du client : Terraform qui produit le fichier ──┘
```

**Les montages** (`docker-compose.yml`) : la watch et le bot montent le fichier **en lecture seule**
(`:ro`) ; la console le monte **en écriture**. C'est l'inverse de ce que FS1 veut pour les actions :
aujourd'hui, la console écrit ce que la watch lit.

**Le push et la console** se connaissent déjà un peu. `host_config.py` garde le mode de chaque VM tel
qu'il est sur Imladris, jamais un plus hardi. Et le push relit la config d'Imladris juste avant
l'envoi : changée entre-temps (« un mode changé dans la console ? »), il n'envoie rien. **Mais tout le
reste est écrasé par la copie du poste.** Une exclusion posée depuis la console disparaîtrait au push
suivant (§3.3).

### 1.5 La remarque de Jonathan sur `exclude_all`

> `exceptions.exclude_all` rend une VM invisible : plus aucune détection. À vérifier : la console doit
> montrer qu'une VM est exclue, avec sa raison, au lieu de la passer sous silence.

Vérifié dans le code le 23/11 :
- **la VM reste sur la carte de l'infra** : le registre la garde ;
- **sa carte ne dit pas qu'elle est exclue** : aucun badge, aucune bande ;
- **seul l'audit le dit**, dans la ligne « Detection rules », en vert, sans raison ;
- **la raison n'existe pas** : `exceptions[]` n'a que `asset_pattern`, `exclude_all`, `exclude_rules` ;
- **un motif peut exclure une VM créée plus tard** (`vm-dev-*`), sans que rien ne le dise.

Il faut donc un petit lot : CFG2 (§9), qui peut partir avant tout le reste.

---

## 2. Le principe : partir de ce qui est découvert

**Proposé : on clique un objet découvert au lieu de taper un nom, un motif ou un CIDR.** La console
écrit dans le fichier le **nom exact** de l'objet, jamais un motif qu'elle aurait inventé. Un motif ou
un CIDR écrits à la main restent admis dans le fichier, et la console les montre (Q7).

Un exemple par geste :

| Geste | Où on clique | Ce que la console demande d'écrire |
|---|---|---|
| **Le mode d'une VM** | la carte de `vm-web-01`, menu du mode | `autonomy.assets: [{match: "vm-web-01", mode: human_only}]` — comme aujourd'hui, par la file |
| **Une exclusion, avec sa raison** | la carte de `vm-dev-01`, « Exclude… » : toutes les règles, ou une liste cochée | `exceptions: [{asset_pattern: "vm-dev-01", exclude_all: true, reason: "VM de dev, recréée chaque nuit"}]` — `reason` est une clé nouvelle (proposé, CFG2). La VM reste sur la carte, grisée |
| **Un réseau nommé** | la liste des sous-réseaux découverts (SEC2b), `vnet-hub/snet-dmz` | `networks: {dmz: {subnet: "vnet-hub/snet-dmz"}}` — la découverte lit la plage, et le nom la suit |
| **Une zone exposée** | un réseau nommé, « Mark as exposed » | `network_zones: {exposed: [dmz]}` — refusée si trop large (jamais un /8), dite fort au démarrage (SEC2c) |
| **Une origine attendue** | un réseau nommé, « Expected origin » | `network_zones: {expected_origins: [bastion]}` (SEC2d, 0.7) |
| **`never_block`** | une IP publique découverte (la sortie d'une passerelle NAT), ou une adresse saisie | `never_block: ["198.51.100.10"]` — une adresse saisie passe la même validation que le fichier (`validate_never_block`) |
| **Les administrateurs attendus (ADM1)** | une carte de sudo sur `vm-web-01`, « Expect admin1's sudo here » | `expected_sudo: {admins: [{match: "vm-web-01", accounts: [admin1], origins: [bastion]}]}` — le compte vient de la carte, l'origine d'un réseau nommé |

Trois règles en découlent (proposées) :
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
Elle change la seule entrée visée. Elle réécrit le reste à l'octet.

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
d'exemple, une opération puis son inverse rendent le fichier d'origine à l'octet.

### 3.3 La coexistence : la console, la main, le push, l'IaC

**Proposé : un condensé du fichier sert de version.** C'est le SHA-256 de ses octets.

- **La console** lit le fichier, montre le diff, et met dans sa demande le condensé qu'elle a lu
  (`base`).
- **La watch** n'applique la demande que si le fichier a encore ce condensé. Sinon elle refuse,
  `config_changed`. La console relit et remontre le diff. C'est déjà la règle du push
  (`HOST_PUSH_RECHECK`) : changé entre deux lectures, rien n'est envoyé.
- **Une édition à la main** (`sudoedit`) change le condensé. La watch le voit à sa lecture suivante :
  ce n'est pas une de ses écritures. Elle le dit (« glorfindel-config.yaml changed outside the
  console »), l'écrit dans l'historique avec le diff, l'auteur inconnu, et l'annonce sur Discord
  (proposé, Q9).
- **Un fichier refusé par A3** (une faute à la main) : la watch ne démarre pas, comme aujourd'hui. Une
  watch déjà en route tombe du côté prudent : `decide` met toutes les VM en `human_only` (G2), et une
  liste `never_block` illisible refuse tout blocage. La console montre les problèmes, chacun à son chemin. **Elle refuse toute modification tant que le
  fichier est refusé** : la correction se fait à la main, là où la faute a été faite.
- **`make imladris-push`** écrase aujourd'hui tout sauf les modes. Avec l'éditeur, il effacerait une
  exclusion posée sur Imladris. Il faut une règle (Q3). Proposé : une fois l'édition ouverte, **le
  fichier d'Imladris devient la référence**. Le push refuse d'écraser une section changée sur Imladris
  depuis le dernier push, et dit laquelle. Une cible `make imladris-config-pull` rapatrie le fichier
  sur le poste.
- **Un fichier tenu par l'IaC du client** : une écriture de la console serait défaite au prochain
  `terraform apply`, sans bruit. Proposé (Q4) : le déploiement déclare le fichier « géré »
  (`EREGION_CONFIG_MANAGED=1`). La console prépare alors le diff, à coller dans le dépôt du client, et
  n'applique rien. Le diff garde la même classe et la même confirmation qu'une écriture.

### 3.4 L'historique et le retour arrière

**Proposé : `~/.glorfindel/config_history.jsonl`, écrit par la watch seule.** Une ligne par
changement :

```json
{"at": "2026-11-24T09:12:03Z", "request": "<id>", "by": {"via": "console-token", "session": "3fa1c2d4"},
 "op": "exclude", "class": "relax", "reason": "VM de dev, recréée chaque nuit",
 "before": "sha256:…", "after": "sha256:…", "diff": "@@ exceptions @@\n+  - asset_pattern: \"vm-dev-01\"…"}
```

- **Une édition hors de la console** a sa ligne aussi : `"by": {"via": "outside"}`, et le diff que la
  watch a vu.
- **Le retour arrière** est une demande comme une autre : « annuler la ligne `<id>` ». La watch calcule
  l'inverse du diff, puis le **reclasse**. Annuler un resserrement, c'est relâcher : la confirmation
  est demandée.
- **Le journal est borné** (proposé : comme les autres journaux de la watch, une taille maximale, les
  plus anciennes lignes archivées).

---

## 4. La console demande, la watch écrit (FS1)

### 4.1 Le chemin

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

- **`op` vient d'une liste fermée**, fixée dans le code de la watch : `set_mode`, `set_default_mode`,
  `exclude`, `unexclude`, `never_block_add`, `never_block_remove`, `network_set`, `network_remove`,
  `zone_add`, `zone_remove`, `admin_add`, `admin_remove`, `revert`. Chacune a ses champs exacts dans
  `args`. **Jamais un morceau de YAML libre.**
- **La classe n'est pas dans la demande.** La watch la calcule sur l'effet (§5.3).
- **`confirm`** porte la preuve d'une confirmation pour un relâchement : le nom tapé, et le code d'un
  second facteur si Q2 le retient.

### 4.2 Ce que cela demande à FS1

FS1 est prêt, mais éteint par défaut (`EREGION_ACTION_QUEUE=1`). Proposé :

1. **Un nouveau genre de demande**, `config_request`, à côté de `request`. Ses champs sont exacts,
   comme ceux de `request` (un champ de plus refuse la demande), bornés à 4 Ko. Il a son propre domaine
   de signature (`eregion.config-request/1`) : une demande de configuration ne se lit jamais comme une
   action, ni l'inverse. Le nonce, la fraîcheur et le registre restent ceux de FS1.
2. **Rattachée au fichier, pas à une carte.** Une action de FS1 se rattache à une proposition que la
   watch a signée. Un changement de configuration se rattache au condensé `base`. Quand il part d'une
   carte (« Expect admin1's sudo here »), la carte est nommée en plus, pour l'historique.
3. **Les verbes par service.** La console peut tout demander. Le bot, rien en v1 (proposé). Un geste de
   configuration depuis Discord attend FS1g et TOT1.
4. **Les montages s'inversent** : la watch monte le fichier en écriture, la console et le bot en
   lecture seule. **FS1f ne le couvre pas aujourd'hui** : il prévoit de monter `~/.glorfindel` en
   lecture seule, mais le fichier de configuration est un montage à part (`EREGION_CONFIG`), en écriture
   chez la console (§10).
5. **Le reçu** dit `applied`, `held` (un relâchement qui attend son délai ou sa confirmation),
   `refused` (avec son code : `config_changed`, `config_refused`, `unknown_op`, `confirmation_missing`,
   `managed`), ou `cancelled`.
6. **L'annonce** : chaque changement appliqué, et chaque édition hors de la console, devient une
   annonce de la watch, que le bot poste sur Discord. Le chemin existe : `vm_notices` (DRN2).
7. **Sans la file** (le défaut d'aujourd'hui) : proposé (Q5), seule l'écriture du mode reste directe,
   comme aujourd'hui, jusqu'à FS1f. Toute autre édition exige la file. Aucun nouveau chemin d'écriture
   directe n'est ouvert.
8. **Sur Imladris**, la watch écrit `~/eregion/glorfindel-config.yaml` en place, sous le verrou : le
   fichier est monté seul, et `_write_atomic` sait déjà le faire (`EBUSY`).

### 4.3 Ce que la file ne change pas

- **La CLI de l'opérateur** garde son chemin direct (FS1, Q4) : c'est l'issue de secours. Proposé : une
  commande `glorfindel config` fait les mêmes opérations, sur le même code, dans le conteneur de la
  watch.
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

`never_block` est un cas à part. L'ajouter resserre : Glorfindel bloque moins, mais il voit et dit
autant (la carte `protected_address`). C'est le classement de la fiche. Une entrée très large
(un /16 public) reste dite fort au démarrage, comme aujourd'hui.

### 5.2 Le classement de chaque clé (proposé)

| Clé, geste | Classe | Dans la console ? |
|---|---|---|
| `autonomy.assets` : un mode plus prudent (`non_disruptive` → `human_only`) | resserre | oui |
| `autonomy.assets` : un mode plus hardi (`human_only` → `non_disruptive`) | relâche (la préparation L6 en plus) | oui |
| `autonomy.default` : vers `human_only` | resserre | oui |
| `autonomy.default` : vers `non_disruptive` | relâche | oui |
| `exceptions` : ajouter une exclusion (toutes les règles ou certaines) | relâche | oui |
| `exceptions` : retirer une exclusion | resserre | oui |
| `never_block` : ajouter une adresse | resserre | oui |
| `never_block` : retirer une adresse | relâche (elle redevient bloquable) | oui |
| `networks` : déclarer un nom que rien ne cite | neutre | oui (SEC2b) |
| `networks` : changer ce que désigne un nom cité | la classe la plus relâchante de ses usages (§5.3) | oui |
| `network_zones.exposed` : ajouter une zone | relâche (le blocage seul y redevient possible) | oui (SEC2c) |
| `network_zones.exposed` : retirer une zone | resserre | oui |
| `network_zones.expected_origins` : ajouter une origine | relâche (des détections écartées) | oui (SEC2d, 0.7) |
| `network_zones.expected_origins` : retirer une origine | resserre | oui |
| `expected_sudo.admins` : ajouter une entrée, un compte, une origine | relâche | oui |
| `expected_sudo.admins` : en retirer | resserre | oui |
| `expected_sudo.sensitive_commands` : ajouter un texte | resserre | oui |
| `expected_sudo.origin_proof` : `none` → `bastion` ou `flows` | resserre | proposé : non en v1 (Q8) |
| `expected_sudo.origin_proof` : vers `none` | relâche | proposé : non en v1 |
| `autonomy.allow_destructive` | relâche (si un jour lue) | **non** (§10) |
| `isolation.forensic_sources`, `forensic_ports` : ajouter | relâche (une VM isolée plus joignable) | non |
| `isolation.quarantine_nsg`, `quarantine_rg` | change le mécanisme | non |
| `memory.max_age_days` | neutre à la lecture, à mesurer | non |
| `monitoring_backends`, `action_backends`, `discovery` | retirer un backend ou couper la découverte relâche | non : le déploiement |

« Non » veut dire : montré en lecture seule, écrit à la main ou par l'IaC.

### 5.3 La classe se calcule sur l'effet

**Proposé : la watch compare la configuration avant et après**, lues toutes deux par la lecture stricte.
Elle ne croit pas le nom de l'opération.

- Pour chaque VM découverte : son mode avant et après, ses règles exclues avant et après.
- Pour chaque réseau nommé : ses usages. Un nom cité dans `never_block` et dans `exposed`, qu'on
  élargit, relâche : la zone exposée grandit.
- Pour les adresses : ce qui devient bloquable, ce qui ne l'est plus.

Exemple : un `set_mode` qui écrit `non_disruptive` sur une VM déjà tenue `non_disruptive` par un motif
ne change rien : neutre. Le même, sur une VM tenue `human_only` : relâche.

Un changement mêlé (un resserrement et un relâchement) est un relâchement.

### 5.4 Resserrer s'applique simplement

Un clic, un reçu, c'est fait. Aucune confirmation, aucun délai. L'historique le garde, et Discord le
dit sans bruit (une ligne).

C'est aussi **le geste d'urgence**. Une rafale de fausses alertes sur une VM ? On la passe en
`human_only` : tout de suite. On l'exclut ensuite, à froid, avec la confirmation.

### 5.5 Relâcher passe par une confirmation explicite (proposé)

1. **La console dit l'effet en une phrase**, calculée par le même code que la watch : « vm-dev-01 ne
   sera plus surveillée par aucune règle. Aucune détection, aucune carte. »
2. **La raison est obligatoire.** Elle va dans le fichier (`reason`) et dans l'historique.
3. **On tape le nom de l'objet** : `vm-dev-01`, ou `dmz`. C'est la forme de Dagorlad pour un fil
   destructif.
4. **C'est dit fort** :
   - une bannière sur la console, jusqu'à ce qu'un humain l'acquitte ;
   - une annonce sur Discord, postée par le bot depuis l'annonce de la watch, jamais par la console ;
   - la ligne de la vue « Relaxed » (§6).
5. **Un second facteur, ou un délai** (Q2). Proposé :
   - **en v1, un délai** : le relâchement prend effet 10 minutes après la demande, annoncé sur Discord
     dès la demande. On l'annule depuis la console ou la CLI. Une console compromise peut demander un
     relâchement, mais l'humain le voit venir ;
   - **avec TOT1**, le code à usage unique prévu pour le restore : un relâchement l'exige, et part tout
     de suite.

---

## 6. Tout ce qui est relâché reste visible

**Proposé : une vue « Relaxed », calculée depuis le fichier et l'historique, jamais tenue par la
console.**

```
RELAXED · 4                                                       ⚙ Config ▸ Relaxed
vm-dev-01      excluded from all rules    « VM de dev, recréée chaque nuit »   console · 3fa1c2d4 · 24/11 09:22
vm-dev-*       excluded from 1 rule       (no reason: hand-written)            outside · 12/11     · 3 VMs today
gondolin       non_disruptive             « banc, préparation ready »          console · 01/11
dmz            exposed zone (/27)         « DMZ du partenaire »                console · 25/11 · ends 25/12
```

- **Chaque ligne** : ce qui est relâché, l'objet, la raison, l'auteur (la session de la console, ou
  « outside »), la date, l'échéance si Q6 en pose une, et ce que désigne un motif aujourd'hui.
- **Une VM exclue ne disparaît jamais** :
  - sa carte reste sur la carte de l'infra, grisée, avec une bande « EXCLUDED from all rules —
    <raison> — since <date> » ;
  - une exclusion partielle : « EXCLUDED from ssh-brute-force » ;
  - l'Overview compte les VM exclues, à côté des autres chiffres ;
  - l'audit garde sa ligne, mais l'exclusion n'y est plus en vert : elle passe en jaune.
- **Une entrée sans raison** (écrite à la main, ou d'avant CFG2) est montrée « no reason ».
- **La watch le redit à son démarrage**, comme SEC2 le prévoit pour les réseaux nommés : chaque
  exclusion, chaque zone, chaque origine.

---

## 7. La frontière

### 7.1 Ce qui change

Écrire la configuration, c'est pouvoir désarmer les gardes : exclure une VM, rendre une autre
autonome, écarter des détections par une origine. **C'est la cible la plus précieuse de la console.**

La page « console » du modèle de menace ([`modele-de-menace.md`](modele-de-menace.md), §1) dit les
actions sur Azure et la demande d'exercice. **Elle ne dit pas que la console écrit le fichier de
configuration** (§10). Proposé, pour le lot qui ouvre l'édition :

| | Menace | Ce qui la tiendrait (proposé) |
|---|---|---|
| T | Une console compromise relâche : elle exclut une VM, rend une VM autonome, déclare une origine | La watch écrit seule ; la demande est signée ; un relâchement attend son délai ou un second facteur ; il est annoncé sur Discord par le bot, depuis la watch ; la vue « Relaxed » le montre |
| T | Une console compromise relâche puis cache | La vue est calculée par la watch depuis le fichier et l'historique, que la console ne monte qu'en lecture ; l'annonce part du bot, pas de la console |
| S | Une demande forgée, rejouée, périmée | Les contrôles de FS1 : signature, nonce, fraîcheur ; le domaine `eregion.config-request/1` |
| T | Une demande sur une version périmée du fichier écrase une édition à la main | Le condensé `base` : `config_changed` |
| T | Une édition à la main passe sans trace | Le condensé relu par la watch : « changed outside the console », dans l'historique et sur Discord |
| T | Une demande rend le fichier illisible, ce qui met toutes les VM en `human_only` ou arrête la watch au redémarrage | Le résultat passe la lecture stricte avant l'écriture ; refusé, rien n'est écrit |
| R | Un changement sans auteur | L'historique de la watch : la session, la date, le diff |
| E | Une opération écrit une clé hors de sa portée | Une liste fermée d'opérations, des champs exacts, jamais du YAML libre |
| D | Une rafale de demandes | La liste d'attente bornée de FS1 (`BACKLOG`) ; un relâchement en attente à la fois par objet (proposé) |
| I | La configuration nomme des comptes et des plages | Rien de nouveau : la console les montre déjà à l'opérateur ; rien ne quitte l'hôte, sauf l'annonce Discord, qui nomme l'objet et la classe, jamais un compte (proposé) |

### 7.2 Ce qui reste ouvert

- **Une console compromise signe comme la console** (FS1, §3.2). Sans second facteur, le délai et
  l'annonce sont ce qui la tient. Avec TOT1, il lui faut aussi le téléphone de l'opérateur.
- **Root sur Imladris** édite le fichier : c'est le même périmètre qu'aujourd'hui. La différence : la
  watch le voit et le dit.
- **Le choix assumé** (« un jeton, tous les droits de la console ») deviendrait : « un jeton, tous les
  resserrements ; relâcher demande en plus le délai, ou le second facteur ».

---

## 8. Les questions à Jonathan

Une à la fois, dans l'ordre. L'option recommandée vient en premier.

**Q1. Qui écrit le fichier ?**
1. **La watch, par la file signée** (recommandé). La console dépose, la watch vérifie et écrit. C'est la
   direction de FS1 : seule la watch écrit.
2. La console, directement, mais en aller-retour (les commentaires gardés), comme aujourd'hui pour les
   modes. Plus simple, mais une console compromise désarme les gardes sans passer par la watch.
3. Un petit service à part, seul à monter le fichier en écriture. Un conteneur de plus, pour peu de
   gain sur l'option 1.

**Q2. Quelle preuve pour relâcher ?**
1. **En v1, la confirmation (le nom tapé, la raison), l'annonce sur Discord et un délai de 10 minutes,
   annulable ; puis le code de TOT1 quand il existe, qui remplace le délai** (recommandé).
2. Le code de TOT1 dès le début : aucun relâchement depuis la console avant TOT1.
3. La confirmation et l'annonce seules, sans délai ni code.

**Q3. Que devient `make imladris-push` quand la console édite le fichier ?**
1. **Le fichier d'Imladris devient la référence.** Le push refuse d'écraser une section changée sur
   Imladris depuis le dernier push, et dit laquelle ; `make imladris-config-pull` rapatrie le fichier
   (recommandé).
2. Le push fusionne section par section, comme il le fait déjà pour les modes.
3. Le push écrase comme aujourd'hui (sauf les modes) : une édition de la console vit jusqu'au push
   suivant.

**Q4. Et un fichier tenu par l'IaC du client ?**
1. **Le déploiement le déclare géré (`EREGION_CONFIG_MANAGED=1`) : la console prépare le diff à coller
   dans le dépôt du client, et n'applique rien** (recommandé).
2. La console écrit quand même ; le prochain `terraform apply` la défait.
3. Pas en v1.

**Q5. Sans la file (le défaut d'aujourd'hui) ?**
1. **Seul le mode reste écrit directement, comme aujourd'hui, jusqu'à FS1f. Toute autre édition exige la
   file** (recommandé).
2. Toute édition directe, en aller-retour, jusqu'à FS1f.

**Q6. Un relâchement a-t-il une échéance ?**
1. **Une échéance facultative, posée par la console (« until »), et un rappel en carte après 90 jours
   pour ce qui n'en a pas** (recommandé). Les leçons de l'enquête qui relâchent sont datées ; une VM
   de dev exclue l'est souvent pour toujours.
2. Une échéance obligatoire (90 jours par défaut), renouvelable d'un clic.
3. Aucune échéance.

**Q7. Les motifs ?**
1. **La console n'écrit que des noms exacts. Un motif écrit à la main est montré, avec ce qu'il désigne
   aujourd'hui** (recommandé).
2. La console accepte un motif, avec l'aperçu des VM qu'il prend aujourd'hui.

**Q8. Jusqu'où va la console en v1 ?**
1. **Les sept gestes du §2 ; le reste en lecture seule** (`isolation`, `memory`, les backends,
   `origin_proof`, `allow_destructive`) (recommandé).
2. Toutes les clés du fichier.
3. Les gestes du temps 1 de SEC2 seulement (mode, exclusion, `never_block`, réseaux nommés, zone
   exposée) ; les administrateurs et les origines avec la 0.7.

**Q9. Une édition à la main, vue par la watch ?**
1. **Dite sur Discord et dans l'historique, avec son diff, l'auteur « outside »** (recommandé).
2. Dite dans la console seulement.

---

## 9. Les lots de code proposés

Dans l'ordre. Les estimations sont en jours de travail effectif, à ±50 %, comme la ROADMAP. Chaque lot
demande sa plage de mutants à l'Orchestre.

| Lot | Contenu | Ce qu'il prouve | Mutants | Sessions | Estimation |
|---|---|---|---|---|---|
| **CFG2** | **L'exclusion visible.** La clé `exceptions[].reason` (facultative, lue strictement ; une clé nouvelle refusée par une version antérieure, dit dans la doc). `/api/state` porte l'exclusion de chaque VM. La carte grisée et sa bande, l'Overview qui compte, la ligne d'audit en jaune. Aucune écriture. | Une VM exclue, par son nom ou par un motif, ne disparaît jamais en silence. | ~4 : la bande absente sous un motif, l'exclusion partielle lue comme totale, la raison non échappée, l'audit resté vert | Console, Glorfindel | 1–2 j |
| **CFG3** | **La vue « Relaxed », en lecture seule.** Calculée depuis le fichier : exclusions, modes hardis, `never_block` du client, administrateurs attendus, accès d'enquête ; puis, avec SEC2, zones et origines. Ce que désigne chaque motif. | Tout ce qui relâche est montré, à partir du fichier seul. | ~5 | Console, Glorfindel | 2 j |
| **CFG4** | **L'écriture aller-retour.** Une bibliothèque aller-retour (`make lock`) ; `apply_change(texte, op) → texte` pour la liste fermée ; la lecture stricte du résultat ; le condensé ; la classe calculée sur l'effet (fonction pure) ; `set_asset_mode` et `set_default_mode` y passent. | Les commentaires restent ; une opération puis son inverse rendent le fichier à l'octet ; un résultat refusé n'est jamais écrit ; la classe ne dépend que de l'effet. | ~8 : un commentaire perdu, une écriture sans relecture stricte, un motif écrit au lieu d'un nom, un relâchement classé resserrement, un changement mêlé classé resserrement | Glorfindel | 3 j |
| **CFG5** | **La demande par la file.** Le genre `config_request` dans `eregion_core/action_queue.py`, son domaine, ses champs exacts ; la watch l'applique (CFG4) ; `config_changed` ; `config_history.jsonl` ; le reçu ; les montages inversés derrière le drapeau ; l'édition hors de la console vue et dite. | Seule la watch écrit le fichier ; une demande sur une version périmée est refusée ; chaque changement a sa ligne d'historique. | ~10 | Glorfindel, Console | 3–4 j |
| **CFG6** | **L'asymétrie.** La confirmation (nom tapé, raison), l'annonce par le bot, la bannière, et le délai ou le code (Q2) ; l'annulation ; le retour arrière reclassé. | Un relâchement n'est jamais appliqué sans sa confirmation ni avant son délai ; un resserrement l'est tout de suite. | ~8 : le délai sauté, la confirmation non relue par la watch, le retour arrière d'un resserrement appliqué sans confirmation, l'annonce manquante | Glorfindel, Console, bot | 3 j |
| **CFG7** | **Les gestes de la console** : mode (migré), exclusion, `never_block` depuis une IP découverte, administrateurs attendus depuis une carte de sudo. | Chaque geste écrit le nom exact de l'objet cliqué, par `_post` et la file ; rien du dehors écrit brut (#254). | ~6 | Console | 3 j |
| **CFG8** | **La coexistence avec le push et l'IaC** (Q3, Q4) : `imladris-push` qui refuse d'écraser, `imladris-config-pull`, le mode « géré » et son diff. | Aucune édition d'Imladris perdue par un push ; un fichier géré n'est jamais écrit par la watch. | ~5 | Infra (Imladris), Glorfindel | 2 j |
| **CFG9** | **Les réseaux et les zones dans la console**, après SEC2b et SEC2c ; les origines attendues avec SEC2d (0.7). Choisir un VNet ou un sous-réseau découvert ; le changement de ce qu'un nom désigne, dit. | Une zone ne s'élargit jamais en silence ; un nom introuvable est dit. | ~6 | Console, Glorfindel | 2–3 j |

**Total** : de 19 à 22 jours, environ 52 mutants. CFG2 et CFG3 ne dépendent de rien et peuvent partir
tout de suite. CFG5 et la suite attendent la réponse à Q1 et Q5, et la file mesurée au banc (FS1c).

**Le modèle de menace** se met à jour dans le lot qui ouvre l'écriture (CFG5), avec les lignes du §7.1.

---

## 10. Ce que la note a trouvé dans le code et la doc

Relevé sans rien corriger (la note ne touche aucun code ni aucune autre doc) :

- **`autonomy.allow_destructive` n'est lue par aucun code de Glorfindel.** Seuls `config.py` la parse,
  `host_config.py` la vide et la console l'affiche. Or la console la range parmi les **actions
  autonomes** (`glorfindel.js`, `_capabilityHtml`), comme une liste de noms d'actions. Le commentaire
  d'A3 (`config.py`) la lit, lui, comme des motifs de VM (« `vm-*` »). Le sens de la clé n'est pas fixé,
  et la console promet ce que l'agent ne fait pas. À trancher par Glorfindel : la câbler, ou la retirer.
- **`docs/design/file-actions-signee.md`, §1.5** range « le mode d'une VM » parmi ce que la console
  écrit dans `~/.glorfindel`. Le mode est écrit dans `glorfindel-config.yaml`, un montage à part
  (`EREGION_CONFIG`), en écriture chez la console, en lecture seule chez la watch. **FS1f**, tel qu'il
  est écrit (« la console et le bot montent `~/.glorfindel` en lecture seule »), ne fermerait donc pas
  l'écriture de la configuration par la console.
- **La page « console » du modèle de menace** (§1) ne dit pas que la console écrit le fichier de
  configuration. Elle range « passer un actif en `non_disruptive` » parmi les actions qui touchent Azure,
  alors que ce geste écrit un fichier local que la watch relit à chaque cycle. Et son « Ouvert : rien de
  connu » tient sans cette écriture.
- **`glorfindel-config.yaml.example` n'a pas de section `isolation`**, alors que la lecture stricte
  connaît ses quatre clés (`quarantine_nsg`, `quarantine_rg`, `forensic_sources`, `forensic_ports`),
  et que `docs/operations.md` les liste.
- **`docs/operations.md`, « Clés connues »**, ne cite ni `memory` (SEC17) ni `origin_proof` (COR2) dans
  sa liste de tête, alors que les deux sont lues et documentées plus bas ou dans l'exemple.
- **L'écriture du mode** (`_update_config`) n'est pas relue par la lecture stricte avant d'être
  écrite. Elle ne peut pas créer une clé inconnue, mais elle réécrit sans le dire un fichier déjà
  refusé.
