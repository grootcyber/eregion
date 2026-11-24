# Le mouvement latéral vu (SEC2d, #1147) — le temps 2 de SEC2, derrière un interrupteur

_Note de conception et de réalisation, 24/11. Le code est sur `main`, testé, **éteint** : il ne s'allume
que dans la 0.7, après deux étapes (§5)._

**Les décisions de Jonathan.** Le 23/11 (décisions 1, 2, 5 et 8 de SEC2) : la règle `ssh-brute-force`
voit toutes les sources ; le code, jamais le modèle, classe l'adresse selon son origine ; une source du
réseau du client n'est jamais bloquée, et l'isolement de la VM source reste une **proposition, jamais une
action seule**, quel que soit le mode ; une origine attendue est écartée, dite et comptée. Le temps 1
(SEC2b, #1089 ; SEC2c, #1107) ne changeait pas ce que voit le modèle ; le temps 2 le change. Le 24/11 :
SEC2d se prépare maintenant, **derrière un interrupteur éteint par défaut**.

---

## 1. L'interrupteur

- **`GLORFINDEL_LATERAL`**, une variable d'environnement de la watch seule (`docker-compose.yml`), lue à
  chaque usage (`glorfindel/lateral.py`, `switch`, `on`). Vide, absente ou `off` : éteint. `on`, espaces
  autour ôtés : allumé. Toute autre valeur (`ON`, `1`, `true`…) : éteint, et dit une fois sur stderr
  (« ⚠ GLORFINDEL_LATERAL=… inconnu ») — rien n'est deviné.
- **Pourquoi une variable, pas une clé de la configuration** : les raisons de MEM2
  ([`memoire.md`](memoire.md), §8.1). La configuration est lue strictement (A3) : une valeur inconnue y
  refuserait tout le fichier ; et la console la réécrit (le mode d'une VM, CFG) : l'interrupteur serait à
  sa portée. La variable est à l'opérateur, dans `host.env` sur Imladris.
- **Éteint, rien de ce que voit le modèle ne change à l'octet** : la règle livrée, le message, le prompt
  et l'outil. Un test le dit (`tests/unit/test_lateral.py`, `test_off_nothing_the_model_sees_changes_to_the_byte`) :
  la requête livrée et la règle entière par leur empreinte, le prompt et l'outil par celles d'IR1a
  (`test_identity_plan.py`), le message par celle de DOS2 (`test_cycle_line.py`) ; et, pour un même signal,
  le message envoyé est le même dans les deux positions.
- **Où il joue** : la watch (sa variante de la règle, son RulePoller, ses cartes, ses lignes au démarrage)
  et tout processus qui l'a dans son environnement (la CLI lancée dans le conteneur de la watch). La
  console et le bot ne l'ont pas : leurs gestes passent par la file signée, que la watch rejoue.

## 2. La règle : une variante, le fichier livré intact

- **Allumé**, la base livrée (`glorfindel/rules/azure/detection_rules.yaml`) charge `ssh-brute-force` dans
  sa variante (`lateral.variant`, appelée par `detection_rules.rule_layers`) : la requête livrée dont le
  filtre des plages privées — trois lignes, à l'octet, ses deux commentaires compris — est remplacé par
  un filtre du seul bouclage (`127.`). Toute autre clé reste celle de la règle livrée ; la description dit
  « any source but the loopback ». Une règle livrée qui n'aurait plus ce filtre à l'octet ne prend pas de
  variante : elle charge telle quelle, et c'est dit dans les notes du chargement.
- **Le fichier livré ne change jamais** : la variante est faite au chargement, pour la base livrée
  seulement (une autre base, celle d'un test, n'est jamais touchée). Ce qui lit le fichier lui-même
  (`shipped_query`, les empreintes de MID1 et d'ATT1, le CD d'Imladris) le lit tel qu'il est.
- **Les couches de règles (P1)** : la couche du client remplace la variante par son nom, comme elle
  remplace la base. Une copie de la règle livrée (WL1, `base_sha256`) est jugée contre la variante : son
  empreinte ne correspond plus, elle est écartée, la variante charge — plus de cartes, jamais moins.
- **Pourquoi une transformation plutôt qu'une seconde règle écrite** : une seule requête à tenir. Une
  correction de la règle livrée passe d'elle-même dans la variante ; un test vérifie que la variante voit
  une source privée que la règle livrée ne voit pas, et que tout le reste est identique.

## 3. Le code classe la source, jamais le modèle

L'ordre de la décision 8 (`policy.address_layers`), la déclaration la plus prudente gagne :

| Rang | Couche | Ce que la classe donne |
|---|---|---|
| 1 | la plateforme Azure et le bouclage | jamais bloquée (SEC2) |
| 2 | `never_block` | jamais bloquée ; jamais écartée comme une origine attendue |
| 3 | **une origine attendue** (`EXPECTED`, `network_zones.expected_origins`) | **la détection écartée par le RulePoller avant tout signal, dite et comptée** ; jamais bloquée |
| 4 | la zone exposée (SEC2c) | un seul hôte bloquable, le mode de la VM attaquée le permettant ; pas de carte de la source |
| 5 | le reste du réseau du client | **jamais bloquée** (la garde de `decide`, le connecteur) ; **une carte de la source** |
| 6 | Internet | le blocage, comme aujourd'hui |

- **`network_zones.expected_origins`** (`glorfindel/config_zones.py`) : lue comme `exposed` — une plage ou
  un réseau nommé (décision 5), étroite (au plus /16 en IPv4, /48 en IPv6 : jamais un /8), jamais la
  plateforme ni le bouclage ; un nom non déclaré refuse le fichier. Lue et vérifiée quel que soit
  l'interrupteur ; **éteint, la couche 3 est vide** : la clé est dite sans effet au démarrage.
- **Écartée, dite et comptée** (`lateral.origin_rows`) : avant le verrou du RulePoller, chaque ligne dont
  la `SourceIP` tombe dans la couche 3 — la première qui la tient : une adresse aussi dans `never_block`
  n'est pas écartée. Marquée envoyée comme toute ligne de la passe, elle n'est comptée qu'une fois par
  fenêtre (`expected_origins` dans le statut de la règle, que la console lit), et dite dans le journal de
  la watch.
- **La carte de la source** (`lateral.judge`, `lateral.record_card`, à la fin du cycle, dans
  `store_cycle`, à part de la carte de la décision et quel que soit le choix du modèle) :
  - **une VM surveillée** tient l'adresse — par son adresse exacte, dans la lecture des cartes réseau
    (`exposed_zone.holders`), une seule VM, aucune carte qui transfère les paquets, la liste fiable, la VM
    dans le registre de la découverte : une carte **`lateral_source`**, sur la VM source, qui propose
    `isolate_vm` ; approuvable en un clic par le chemin de toute carte retenue
    (`action_queue.APPROVABLE_TYPES`, la console, la file signée) ;
  - **sinon** — une appliance (la VM source est derrière elle), deux VM, une VM hors du registre, aucune
    carte, une liste non fiable, une ligne qui ne nomme aucune VM : une carte **`lateral_unknown_source`**,
    sur la cible, pour un humain, rien à approuver ; une carte par adresse.
  - **Jamais en dry-run**, jamais une exception qui arrête le cycle.
- **Jamais une isolation seule de la source**, quel que soit le mode, `full_auto` compris : le code n'écrit
  qu'une carte. L'adresse est lue dans une ligne de la cible, que son invité peut écrire (le modèle de
  menace, §2) ; une adresse forgée fait **proposer**, jamais isoler. La carte le dit. Ce que le modèle
  décide sur la cible (l'isoler, l'instantané) suit ses gardes, comme avant ; un blocage d'une adresse du
  client qu'il propose est retenu (`protected_address`, SEC2b).
- **Ce qui est échappé** (#254) : seule l'adresse jugée, canonique, entre dans le texte de la carte
  (`::ffff:a.b.c.d` y est écrite en IPv4) ; une `SourceIP` qui n'est pas une adresse ne fait aucune carte.
  Les noms des VM viennent d'Azure ; la console et Discord affichent la carte par leur chemin habituel.

## 4. Ce que dit la watch au démarrage

`lateral.start_lines`, ajoutées à celles du réseau du client (`client_network_watch.start_lines`) :
allumé, « ▲ Mouvement latéral vu (GLORFINDEL_LATERAL=on, SEC2d) », chaque origine attendue, une plage
d'objet trop large écartée ; un chevauchement avec la zone exposée est dit (« origine attendue
l'emporte »), jamais refusé ; la note de la décision 6 (« la règle livrée filtre encore les plages
privées ») n'est plus dite. Éteint : les origines déclarées, dites sans effet. Un interrupteur illisible,
en rouge.

## 5. Avant de l'allumer, et ce qui reste au banc

- **La mesure au banc d'une force brute interne** — la session rouge et les mains de Jonathan : une force
  brute SSH entre deux VM du banc, la variante allumée ; à mesurer : la ligne arrive (`SourceIP` privée),
  la carte `lateral_source` sur la VM source, aucun blocage, aucune isolation de la source, la latence.
- **Le run de bout en bout d'ENQ5** : ce que le modèle fait d'une source interne (§6).
- **Les points de banc venus de la relecture de SEC2c**, gardés au banc :
  - les cartes d'un VMSS uniforme sont-elles absentes de `networkInterfaces.listAll` ? (gardées dans tous
    les cas : une adresse qu'aucune carte lue ne tient ne propose aucune VM) ;
  - `enable_ip_forwarding` est-il rempli avec le seul rôle Reader ? (s'il ne l'est pas, une appliance
    passerait pour une VM : la carte proposerait son isolement) ;
  - `protection('<adresse>')` sur Imladris, pour une adresse de chaque couche.
- **L'allumer** : `GLORFINDEL_LATERAL=on` dans `host.env`, la watch redémarrée (`docs/operations.md`,
  « Le mouvement latéral vu : l'interrupteur »).

## 6. Ce que verra le modèle

Le message d'une détection ne change pas ; ce qui change, c'est quelles détections lui arrivent : les
forces brutes d'une source du réseau du client en plus, celles d'une origine attendue en moins. La
classe de la source n'est jamais dans le message. Le détail : [`../raisonnement.md`](../raisonnement.md),
§2.4.

## 7. Les reprises de SEC2c

- **La carte d'une levée en échec d'un épisode remplacé** (`exposed_blocks._close_replaced`) : un blocage
  réécrit sur une levée en échec porte une nouvelle marque, datée d'après la carte ; la carte est fermée
  (« remplacée : un nouveau blocage de l'adresse depuis »). Une carte dont le blocage garde sa marque
  d'avant reste ouverte.
- **Une demi-phrase dans `docs/operations.md`** : une config qui devient illisible entre les deux
  jugements d'un blocage de la zone refuse ce blocage, et la carte le dit.

## 8. Hors du lot

Allumer l'interrupteur (0.7) ; la mesure au banc ; le run d'ENQ5 ; l'automatisation de l'isolement de la
source par une corroboration venue d'elle (ses connexions sortantes, lues ailleurs que dans la cible) —
un lot à part.

## 9. Preuves

`tests/unit/test_lateral.py` ; mutants M7360–M7379 (`scripts/mutants/SEC2d.py`), tous attrapés.
