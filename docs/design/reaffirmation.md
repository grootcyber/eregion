# La réaffirmation, écrite une fois : ce qu'elle repose, dit et laisse (RSM1, #1018) — conception

_Conception — 21/11 (RSM1, #1018) — statut : **sémantique écrite, écarts ouverts** (§5, §7). Suite de la
dixième passe de revue (P10-2). Aucun code ne change, aucun mutant. Les lots qui suivraient (§6) attendent
les réponses de Jonathan._

_22/11 (RSM2a, #1033) : Jonathan a répondu à Q1, Q2, Q4 et Q7 (§7). L'oracle lit la tenue une fois, dans le
monde du test (E1, E2, E5, E7 faits, §5) ; L1Nc est re-mesurée (§1.1)._

_24/11 (RSM3, #1036, #1057) : E7 et E8 corrigés dans le code. Une paire de périmètre sur un NSG qui ne gouverne plus aucune carte de la VM est lue partie, dite sur une carte du blocage, jamais reposée ; une VM supprimée a sa carte à elle (Q6) ; l'excuse `_known_1057` est retirée de l'oracle (§3, §5)._

**Lié** : [`docs/glorfindel.md`](../glorfindel.md) (la réaffirmation, paragraphe par paragraphe, lot par
lot) ; [`docs/azure.md`](../azure.md) (la préséance, la quarantaine, les blocages, les contournements) ;
[`preuves.md`](preuves.md) (la machine à invariants, et les sections I3N, I3Q, I3W, L1N, I9A, I3X, L1V) ;
[`modele-de-menace.md`](modele-de-menace.md) (l'état local illisible) ; [`memoire.md`](memoire.md) (le
modèle de cette note).

**Règle de lecture.** Ce qui est lu dans le dépôt est une affirmation, avec son fichier et sa ligne, au
commit `7a74a120`. Un chemin sans dossier est dans `glorfindel/` (`reassert*.py`, `orphans.py`) ou
dans `glorfindel/providers/azure/` (`verify.py`, `verify_block.py`, `quarantine.py`, `perimeter.py`) ;
`inv:` renvoie à `tests/unit/test_invariants.py`. Cinq comportements ont été mesurés sur le faux Azure par une sonde
temporaire, hors du commit (§2.4) : le texte cité est celui que la passe a écrit. Le reste est une
hypothèse, et le texte le dit. Aucun appel à Azure ni au modèle.

---

## 0. En bref

- **Trois gestes.** La réaffirmation **repose** ce qui a disparu, une fois par tenue, hors `human_only`.
  Elle **dit** ce qui a changé : une carte par épisode et par sorte, sa marque posée après la carte. Elle
  **laisse** le reste : ce qu'une opération tient, ce qu'on ne sait pas lire, ce qu'un tiers a écrit.
- **Quatre objets, dix situations** : la table du §3. Le code est cohérent, mais sa sémantique n'est
  écrite nulle part en un seul endroit. Elle tient dans cinq paragraphes de `docs/glorfindel.md` (29 Ko,
  plus de trente lots nommés), six modules et les docstrings de la machine.
- **Les trois défauts d'oracle sûrs de la période ont la même forme.** L'oracle redéfinissait un mot que
  le code tranchait déjà autrement : « la levée est finie » (I9A), « le périmètre coupe » (I3X), « la
  tenue est contournée » (L1V). Un quatrième, L1Nc (« une règle a disparu depuis l'acquittement »), a été
  re-mesuré le 22/11 (§1.1) : son récit (« le produit dit le contournement ») était faux, sur la nuit comme
  sur sa séquence figée, et Q2 renverse sa règle (RSM2a). Les deux défauts du produit (L1N,
  L1Nd) relèvent de la règle de lecture d'A0 : une règle dite partie sans avoir été lue. Le §2.3 définit
  ces mots.
- **Les écarts restants** (§5) :
  - « disparue » a quatre définitions dans l'oracle, et aucune n'est celle du code ;
  - les exemptions de L1 lisent les marques du code (A0) ;
  - `_attacker_flows` lit encore les seules sondes (I3Xb) ;
  - la disparition d'une isolation n'est jugée que dans deux règles composées ;
  - une isolation dite ne se redit pas quand elle empire ;
  - un NSG ôté du sous-réseau est dit « autre subnet » (mesuré ; corrigé par RSM3, 24/11) ;
  - rien ne juge ce que la passe dit d'une VM supprimée (mesuré, avec un « de le blocage » ; sa carte à elle et « du blocage » depuis RSM3, 24/11) ;
  - sept situations n'ont aucun invariant.
- **La recommandation** (§6, §7) : cette table devient la référence. L'oracle passe ensuite par un seul
  classement de la tenue, lu dans le monde du test (RSM2), avant tout correctif de produit. Les deux
  changements de produit sont petits : les textes de ce qui n'est plus là (RSM3) et, si Jonathan le
  choisit, l'isolation redite quand elle empire (RSM4).

---

## 1. Le constat

### 1.1 Les contre-exemples des nuits, du 10 au 20/11

La revue en compte huit distincts. Ils tiennent dans sept issues, et #795 en porte trois causes, sur deux
nuits.

| Lot (issue) | Nuit | Propriété | La réaffirmation ? | Défaut | Ce qui a changé |
|---|---|---|---|---|---|
| AWS1b (#708) | 10/11, macOS | I3, une levée sur le faux AWS | non | oracle | une origine que plus rien ne tient n'est plus une fausse alarme ; l'excuse bornée au moment où les tags ont été perdus (#713) |
| I3N (#746) | 12/11, macOS | I3, la réponse de `block_perimeter` | non (la vérification d'un blocage, que la passe lit aussi) | produit | un blocage de périmètre interrompu par un 429 dit ses cartes non lues, jamais ouverte une carte qu'un autre périmètre coupe (#751) ; même famille : I3Q (#776), I3W (#781) |
| L1N (#795) | 13/11, ubuntu et macOS | L1 | oui | produit | un blocage dit disparu parce que son NSG ne gouverne plus la carte est relu là, pour `rules_seen` seulement : ses règles supprimées après l'acquittement sont dites de nouveau (#796 ; #809 en fige deux placements) |
| L1Nc (#795) | 15/11, ubuntu | L1 | oui | oracle, **sa règle renversée par Q2** (RSM2a) | `_ack_holds` jugeait l'acquittement sur les octets des règles ; L1Nc l'a fait tenir tant qu'aucune règle vue présente n'a disparu (#843). Re-mesurée le 22/11 (plus bas) : la deny de la nuit visait déjà une ancienne adresse, partie avant l'acquittement ; RSM2a lit la tenue par son contenu, et une deny retournée est partie |
| L1Nd (#795) | 15/11, macOS | L1 | oui | produit | derrière une quarantaine qu'on ne sait pas juger, les règles du blocage hors de la carte sont lues ; parties, le blocage est dit disparu, la carte laissée inconnue (#866) |
| I9A (#823) | 14/11, ubuntu | I9 | oui | oracle | le journal du test ne finissait une levée que sur une isolation qui avait écrit sur Azure ; il la finit aussi sur une isolation qui a écrit l'état de la VM (#825) |
| I3X (#824) | 14/11, macOS | I3, une carte de la réaffirmation | oui | oracle | `_perimeter_cuts` jugeait « coupée sur tous les ports » sur des sondes toutes TCP ; il lit chaque voie vers l'attaquant (`ATTACKER_WAYS`) (#826) |
| L1V (#864) | 16/11, ubuntu | L1, un contournement | oui | oracle | `_bypass_comes_back` comptait tout flux qu'ouvre l'allow ; il ne compte plus que ceux que les denies de la tenue ferment (#865) |
| SEC-Hb (#947) | 18 et 19/11 | I7 | non | produit (le message) et oracle | le refus de SEC-H donne une sortie qui existe ; l'oracle d'I7 la suit, et un second oracle (I3 d'un déblocage) est corrigé (#948) |

Compté par issue, comme la revue : la réaffirmation en touche quatre (L1N, I9A, I3X, L1V), dont trois
défauts d'oracle. Compté par cause : six, dont trois d'oracle sûrs (I9A, I3X, L1V), deux du produit (L1N,
L1Nd), et L1Nc, d'oracle aussi, re-mesurée le 22/11.

**L1Nc, à re-mesurer.** Son lot l'a classé défaut d'oracle : le produit aurait dit le retournement par sa
carte « contourné », et l'ancien oracle, qui comparait les octets, aurait réclamé à tort une seconde carte
« a disparu » (`preuves.md`, « L'oracle précisé, cette fois (L1Nc, #795) » ; `CHANGELOG.md`, [0.6.0]). La
relecture de cette note a rejoué sa séquence figée sur `7a74a120`, et la sonde de la note l'a refait, à
l'identique : `_l1nc_block_perimeter_gone_acknowledged`, puis la deny de `db-nic-1` retournée, puis une
passe en `human_only`. Le produit écrit alors **une nouvelle carte « a disparu »**, qui nomme la deny
retournée avec la paire de périmètre (« … a disparu d'Azure (glorfindel-block-…-db--01-1226…,
glorfindel-block-192-31-196-7, glorfindel-block-192-31-196-7-out) — l'IP n'est plus bloquée sur db-nic-0,
db-nic-1 »). La carte « contourné » de la même passe porte sur `allow-https` (priorité 100, `nsg-subnet`),
une règle d'un tiers, pas sur notre deny retournée. Sur cette séquence, aujourd'hui, le récit ne tient donc
pas, et l'ancien oracle passerait. Deux lectures restent ouvertes, et aucune n'est mesurée :
- la nuit du 15/11 tirait un autre chemin que la séquence figée, sur lequel le produit se taisait ; ou le
  produit a changé depuis (L1Nd, #866, fusionné le lendemain, touche la même vérification). La graine est
  à rejouer sur 7a049aca (L1Nc) et sur `main` ;
- le code et l'oracle ne lisent pas le même mot : pour le code, une deny retournée entre dans ce qui est
  parti, par son nom (§1.2) ; pour `_ack_holds` depuis L1Nc, elle n'a pas disparu (E1, Q2).

**L1Nc, re-mesurée (RSM2a, 22/11).** La nuit du 15/11 (run 43706627533, ubuntu,
`EREGION_HYPOTHESIS_SEED=733034525`, 10 000 exemples) a été rejouée pas à pas, telle qu'Hypothesis l'a
imprimée : 29 pas, chaque `@invariant` après chaque pas, par une sonde hors du commit, sur b5c10b29 (le code
de la nuit), sur 7a049aca (L1Nc) et sur `main` (199dc806). Entre les trois, seuls les noms des règles
changent (la marque de carte de SEC-H, 128 bits) : la sonde les retrouve par leur carte et leur sens.
- Sur b5c10b29, L1 échoue au pas 29, comme la nuit.
- Sur 7a049aca et sur `main`, le même chemin, les mêmes cartes, et L1 tient. La dernière passe n'écrit rien
  sur Db--01, et ce n'est pas un contournement qui la fait taire : la seule carte « contourné » en attente
  vise `allow-ssh` (priorité 100, `nsg-db-nic-1`), une règle d'un tiers, écrite au pas 18. La deny retournée
  au pas 29 visait déjà une ancienne adresse. Au pas 22, la seconde IP de db-nic-1 est passée de 10.0.0.8 à
  10.0.0.20, et 10.0.0.8 à une VM neuve (batch). La carte du pas 23 disait donc déjà db-nic-1 parti
  (« a disparu d'Azure une deuxième fois (…, …-db--01-…, …-out, …) — l'IP n'est plus bloquée sur db-nic-0,
  db-nic-1 »), et l'opérateur l'a acquittée au pas 27. Retourner cette deny n'ajoute rien à ce qui est
  parti : le produit se tait, à juste titre. L'oracle d'avant L1Nc comparait les octets, et lisait une
  règle « présente » à l'acquittement qui avait changé.
- La séquence figée de L1Nc, construite à la main, n'est pas ce chemin : la deny y est en vigueur à
  l'acquittement. Rejouée sur 7a049aca même, comme sur `main`, la passe écrit une nouvelle carte
  « a disparu » qui la nomme ; sa carte « contourné » vise `allow-https` (`nsg-subnet`), d'un tiers.

Les 29 pas sont figés, tels qu'imprimés, dans `test_the_night_of_15_11_turns_a_deny_already_gone`
(`tests/unit/test_invariant_regressions.py`) : L1 tient, la deny est lue partie à l'acquittement, et la
dernière passe ne dit rien de plus sur Db--01.

*Ce que cela tranche.* Les deux lectures ouvertes tenaient chacune en partie. La nuit tirait un autre
chemin que la séquence figée, et le produit n'a pas changé sur ce point entre 7a049aca et `main`. Le récit
de L1Nc (« le produit dit le contournement ») était faux sur les deux. Avec Q2, le nouvel oracle lit la
deny de la nuit partie dès l'acquittement (ancienne adresse) : la séquence de la nuit passe. Celle de L1Nc
change, l'acquittement rompu et la carte exigée
(`test_a_block_deny_turned_after_an_acknowledged_perimeter_loss_is_said_again`, 22/11).

### 1.2 Ce qu'ils ont en commun

**Les défauts d'oracle.** Chacun a redéfini, dans le test, un mot que le code tranchait déjà. La
dernière ligne est celle de L1Nc, qui se discute (§1.1) : même après son correctif, le code et l'oracle y
lisent le mot autrement.

| Mot | Ce que fait le code | Ce que lisait l'oracle | Contre-exemple |
|---|---|---|---|
| la levée est **finie** | une isolation entière réécrit l'état de la VM sans `releasing_at` ni `release_failed` : la levée est remplacée, la passe suivante tient l'isolation pour la courante (`_held_by_an_operation`, `reassert.py:227-228`, `:259`) | une levée finie seulement par une écriture sur Azure, ou une réponse `isolated` (`inv:1165-1177`, avant I9A) | I9A |
| le périmètre **coupe** | le modèle de la préséance : une allow sortante avant notre `-out` laisse joindre l'attaquant sur tout port et tout protocole | les sondes du faux Azure, toutes TCP, aucune vers l'attaquant sur 22 | I3X |
| la tenue est **contournée** | une allow d'un tiers évaluée avant une deny à nous qui refuse encore, pour les adresses de la carte (`_bypassing`, `reassert_cards.py:206-217`) ; une deny qui vise une ancienne adresse ne tient plus rien : la carte est non couverte, la tenue disparue (`verify.py:75`, `:78-85`) | tout flux qu'ouvre l'allow, quoi qui le fermait (`_bypass_comes_back`, avant L1V) | L1V |
| une règle a **disparu** depuis l'acquittement | `_worse` (`reassert_said.py:87-99`) a deux clauses. **Par le nom** : une règle nouvellement dans ce qui est parti (`set(now["gone"]) - set(said.get("gone") or [])`, `:96`) ; une deny retournée y entre, `altered` (`verify_block.py:178`). **Par la signature** : une règle lue à la carte puis absente (`rules_seen`, `:99`) | avant L1Nc, les octets des règles (`_block_rules_now(vm) != seen`) ; de L1Nc à RSM2a, la seule présence : une deny retournée n'avait pas disparu. Depuis RSM2a, le contenu : une règle lue intacte à l'acquittement, partie depuis (Q2) | L1Nc (re-mesurée, renversée) |

**Les défauts du produit.** L1N et L1Nd ont la même forme, et c'est la règle de lecture d'A0 : ce qui n'a
pas été lu n'est ni présent ni absent. L1N disait des règles « parties » sans lire le NSG où elles étaient.
L1Nd ne lisait rien derrière une quarantaine qu'on ne sait pas juger.

**Pourquoi la sémantique s'est éparpillée.** Chaque contre-exemple a eu son lot, et chaque lot a écrit sa
règle là où il la touchait : dans le code (une docstring), dans l'oracle (une autre docstring), dans
`docs/glorfindel.md` (un paragraphe de plus). Aucun lot n'avait pour objet de les tenir ensemble. Quand un
nouveau cas tombait entre deux règles, le code et l'oracle le tranchaient chacun de son côté.

---

## 2. La réaffirmation, lue dans le code

### 2.1 Où elle tourne

- **La cadence.** `Housekeeping._reassert` (`watch/housekeeping.py:97-108`) lance une passe toutes les
  `GLORFINDEL_REASSERT_INTERVAL_S` (60 s par défaut), dans son propre fil (`Solo`), jamais deux à la
  fois. Elle ne tourne jamais en dry-run, ni avec un intervalle à 0, ni avec un connecteur en lecture
  seule (`:101`).
- **Le mode.** `_watch_reassert_pass` (`watch/passes.py:43-77`) relit la configuration à chaque passe.
  Illisible, l'autonomie est `None` : alerte seule, jamais une écriture (`:59-66`, U4). Le mode d'une VM
  est son mode effectif : la préparation peut la retenir en `human_only` (`_mode`, `reassert.py:105-113`).
- **L'ordre d'une passe** (`reassert_active`, `reassert.py:126-172` ; `_whatever_the_state`, `:201-220`) :
  1. les isolations enregistrées, chacune sous le verrou de sa VM, son état relu ;
  2. les paires de périmètre à reposer, toutes (le premier temps, `reassert_perimeters.py:43-98`) ;
  3. les blocages, ceux qui tiennent un périmètre d'abord (le second temps, `reassert.py:155-170`) ;
  4. puis, quel que soit l'état local : les fichiers d'état illisibles, les cartes « non vérifiées » des
     tenues levées depuis, les NSG de quarantaine, les règles orphelines (A3), les coupures de sessions
     (DRN1).
- **Ce qui est dit** part en file vers le webhook, jamais attendu pendant la passe (JUG2c,
  `reassert.py:175-187`).

### 2.2 Les quatre objets

| Objet | Ce que l'état enregistre | Comment il est relu |
|---|---|---|
| **L'isolation par règles** d'une carte | une paire de deny sur le NSG de la carte ou de son sous-réseau, adressée aux IP de la carte (`placements`) | `verify_isolation` (`providers/azure/verify.py:18-138`), par contenu, pour les adresses actuelles ; la préséance de chaque allow avant |
| **La quarantaine** | la carte porte notre NSG de quarantaine (un par région et par groupe, partagé) | par contenu : nos règles exactement, et l'accès forensique de la configuration (`_quarantine_state`, `providers/azure/quarantine.py:406-429`) ; le NSG lui-même relu à chaque passe, que l'état le nomme ou non (`reassert_quarantine.py:46-184`) |
| **Le blocage d'une IP sur une VM** | une paire par carte, sur le NSG qui la gouverne, adressée à ses IP ; le port de la menace | `verify_block_ip` (`providers/azure/verify_block.py:26-363`), carte par carte, pour ses adresses actuelles (L26) |
| **Le blocage de périmètre** | une paire par IP et par sous-réseau, sur le NSG du sous-réseau de la carte primaire, sans adresse de destination ; seul, ou fusionné avec le blocage de la VM (`scoped: false`) | la paire relue (`verify_block.py:272-326`), puis les cartes de la VM hors de ce sous-réseau, chacune demandée à son périmètre (`_off_perimeter`, `providers/azure/perimeter.py:68-81`) |

### 2.3 Les mots

| Mot | Ce qu'il veut dire dans le code |
|---|---|
| **tenue** | ce que Glorfindel a posé et que l'état local enregistre : une isolation, un blocage |
| **intacte** | relue par son contenu, pour les adresses actuelles de la carte, sur un NSG qui la gouverne, rien avant elle qui laisse passer : `verified: True` |
| **disparue** | une règle de la tenue absente ; ou présente mais qui ne refuse plus ce qu'elle doit : retournée, rétrécie, visant une adresse que la carte n'a plus (`altered`, `verify_block.py:431-445`, « put back like missing », `:178`) ; ou posée sur un NSG qui ne gouverne plus la carte ; ou une carte sans rien de la tenue (`uncovered_nics`). Une deny à notre nom retournée en autorisation est une disparition **pour son placement** (mesuré, §2.4 M4, et sur la séquence de L1Nc, §1.1). Deux nuances, lues et non mesurées : `_shadowing_rules` tient une allow « nommée comme les nôtres » pour la règle d'un tiers (`providers/azure/nsg.py:119-120`), donc la deny retournée peut aussi contourner une autre de nos denies placée derrière elle ; et sur une carte où un autre placement tient, elle n'est pas dite partie du tout (le `break` de `verify_block.py:189-200`) |
| **contournée** | la tenue intacte, mais une règle **d'un tiers**, évaluée avant elle, laisse passer (`shadowed_by`) ; pour un blocage, seulement ce qui laisse passer la menace (le port de la menace, ou une sortie vers l'IP : `threat_port_open`), le reste est de l'exposition, non dite (`reassert_cards.py:206-217`) |
| **inconnue** | une lecture a échoué, ou la configuration ne permet pas de juger (`verified: None`) : jamais présente, jamais absente, nommée (A0) |
| **tenue par une opération** | une levée ou un déblocage qui a noté son intention (`releasing_at`, `unblocking_at`), qui a échoué (`release_failed`, `unblock_failed`), une écriture que le fournisseur a dite partielle (`partial`), ou le verrou de la VM pris par un autre écrivain |
| **épisode** | une disparition, de sa première carte jusqu'à ce que la tenue relue tienne de nouveau, ou qu'une écriture de Glorfindel la réécrive (L1O, L1Q, L1G, L1W) |

### 2.4 Ce qui a été mesuré

Une sonde temporaire, hors du commit, a joué la machine (`IsolationMachine`, le monde de `_net`,
`invariant_env`, donc hermétique) le 21/11, sur `7a74a120`. La sonde modifiait parfois le monde sans
passer par les règles de la machine : ses fins de séquence (la levée de tout) ne valent rien. Seules les
cartes et les écritures de la passe sont lues.

| | Cas | Écritures | Ce que la passe a dit |
|---|---|---|---|
| M1 | une isolation (par règles, ou en quarantaine), la VM supprimée, deux passes, les deux modes | aucune | `unverified` : « La vérification de l'isolation de web échoue ((ResourceNotFound) virtualMachines/web was not found.) : tant qu'elle échoue, la réaffirmation ne sait pas s'il tient encore — rien n'est reposé ni levé. » Par règles, en plus : une carte `orphan_rule` pour sa paire (« laissée par une carte qui n'existe plus … Gardée : ne coupe aucune carte vivante »). Cette carte ne vient que parce que la machine supprime la VM avec ses cartes réseau (`_delete_vm`) ; sur Azure, supprimer une VM laisse sa carte réseau par défaut, et la paire n'est alors pas orpheline |
| M2 | un blocage, la VM supprimée, ses règles en place | aucune | `unverified` : « La vérification de le blocage de 192.31.196.7 sur web échoue (blocage non vérifiable : cartes illisibles ((ResourceNotFound) …)) … » ; et la carte `orphan_rule`, à la même condition que M1 (la carte réseau supprimée avec la VM) |
| M3 | le même, ses règles parties | aucune | en `human_only` : « Le blocage de … sur web a disparu d'Azure (…) — on ne sait pas si l'IP est encore bloquée : cartes illisibles … » ; hors de lui : « … a disparu d'Azure ; le reposer a échoué : (ResourceNotFound) virtualMachines/web was not found. » |
| M4 | un blocage, sa deny d'entrée (à notre nom, visant l'adresse de la carte) retournée en autorisation | `human_only` : aucune ; hors : les deux règles réécrites | en `human_only` : « … a disparu d'Azure (glorfindel-block-…) — l'IP n'est plus bloquée sur web-nic. Glorfindel ne le repose pas … » ; hors : « … avait disparu d'Azure : reposé une fois. » Aucune carte de contournement |
| M5 | un blocage de périmètre, puis le NSG ôté du sous-réseau | aucune | les deux modes : « Le blocage de périmètre de … ne couvre pas web-nic de web : non couverte(s) depuis le blocage (autre subnet), l'IP les atteint. Bloquer aussi la VM (scope vm) : … » |

---

## 3. La sémantique, en tables

### 3.1 Les règles communes

| | Règle | Où |
|---|---|---|
| R1 | **Lire avant d'écrire**, sous le verrou de la VM, l'état relu : une levée en cours finit d'abord, et son état effacé dit qu'il n'y a rien à reposer. Le verrou pris plus de 30 s : la VM est sautée et relue à la passe suivante | `reassert.py:137-150`, `:223` |
| R2 | **N'écrire que ce qui manque, et que ce qui est à nous** : jamais la règle d'un tiers (I2), jamais pour une VM sans état (I5), jamais en `human_only` (le mode effectif), jamais ce qui est contourné ou inconnu | `reassert.py:281-304`, `:429-451` ; `reassert_cards.py:220-224` |
| R3 | **Une fois par tenue.** Une repose écrite pose `reasserted_at`, que la tenue revienne entière ou non. La disparition suivante est dite « une deuxième fois », sans écriture. Une nouvelle isolation ou un nouveau blocage écrits en entier effacent la marque (L1Q). Une repose qui a échoué ne compte pas : elle est retentée une fois après un redémarrage | `reassert.py:291`, `:310-311`, `:442`, `:493` |
| R4 | **Relire après écrire.** « Reposée une fois » ou « reposé une fois » seulement si la relecture tient entière et que le fournisseur n'a rien dit de partiel ; sinon la carte dit ce qui ne tient pas et ne promet rien (RW1–RW3) | `reassert.py:317-334`, `:494-520` |
| R5 | **Une carte par épisode et par sorte.** La marque est posée après la carte (L1F). Une nouvelle carte ferme l'ancienne dans la même écriture (L1A). La passe se tait sur une marque seulement si sa carte attend, ou si le dernier mot sur ce changement est celui de l'opérateur, et, pour une disparition, si ce processus a vu l'épisode ouvert (L2Q, L2C). Après un redémarrage, elle redit une fois. Un blocage dit est redit s'il empire ; une isolation, non (§5, E6) | `reassert_cards.py:103-125`, `:194-203` ; `reassert_said.py:87-99`, `:170-184` |
| R6 | **Un inconnu n'est ni présent ni absent** (A0) : ce qui n'a pas été lu n'est jamais dit parti, ni tenu, ni « plus bloqué ». Il est dit inconnu, et nommé | `verify_block.py:131-160`, `:258-268` ; `reassert_said.py:39-47` |
| R7 | **L'id d'une carte est en minuscules**, et toute recherche se fait sans casse (I3C) | `reassert.py:46-55` ; `reassert_cards.py:33-42` |
| R8 | **Une passe ne s'arrête pas** sur un état qu'elle ne peut pas écrire (« état local non écrit »), ni sur une carte qu'elle ne peut pas écrire : elle passe à la VM suivante | `reassert.py:151-154` ; `reassert_cards.py:167-176`, `:293-304` |

### 3.2 Ce qui est dit, et sur quelle carte

| Ce qui est dit | `escalation_type` | `action` | Id de la carte | Elle se ferme | Où |
|---|---|---|---|---|---|
| une disparition ; une levée ou un déblocage interrompus ; une carte que le périmètre ne couvre pas | `verification_failed` | `isolate_vm`, `block_suspicious_ip` | `reassert-<vm>-<hash>[-<ip>]` | remplacée par la suivante de la même tenue ; acquittée | `reassert.py:46-83` |
| un contournement | `bypassed` | `review_bypass` | `reassert-bypass-{iso,block}-…-<empreinte des allows>` | quand la deny tient de nouveau ; un autre contournement la remplace | `reassert_cards.py:220-284` |
| une vérification qui échoue ou ne conclut pas | `unverified` | `review_unverified` | `reassert-unverified-…` | quand elle repasse, ou quand la tenue n'est plus enregistrée | `reassert_cards.py:312-380` |
| les règles qu'un blocage a laissées, qui visent une autre adresse (I4A) | `rule_left` | `review_left_rule` | `reassert-left-…-<empreinte>` | un autre ensemble la remplace | `reassert_cards.py:388-431` |
| un état local illisible | `state_unreadable` | `repair_local_state` | `state-unreadable-<empreinte>` | quand tout se lit | `reassert_cards.py:459-516` |
| une VM sautée cinq passes de suite, son verrou tenu (SEC-H) | `verification_failed` | `reassert_skipped` | `reassert-busy-…` | à la première passe qui la relit | `reassert_skipped.py:33-74` |
| un NSG de quarantaine altéré qui porte des cartes | `quarantine_altered` | `restore_quarantine_nsg` | `reassert-quarantine-<hash>-<changement>` | entier, vide, ou disparu (relu par son id) | `reassert_quarantine.py:117-184` |
| une paire de périmètre sur un NSG qui ne gouverne plus aucune carte de la VM (RSM3) | `perimeter_off` | `block_suspicious_ip` | `reassert-off-<vm>-<hash>-<ip>` | quand ce NSG est relu sur le sous-réseau | `reassert_gone.py` (`say_perimeter_off`) |
| une VM supprimée dont une isolation ou un blocage est enregistré (Q6, RSM3) | `vm_gone` | `review_gone_vm` | `reassert-gone-{iso,block}-…` | à la levée ou au déblocage | `reassert_gone.py` (`say_vm_gone`, `gone_released`) |
| une règle orpheline (U1, A3) | `orphan_rule` | `remove_orphan_rule` | `orphan-…` | quand elle n'est plus orpheline | `orphans.py:1-17` |

Le rapport de la passe (ce que la watch affiche) porte un `outcome` par tenue : `reapplied`, `partial`,
`failed`, `escalated`, `bypassed`, `unverified`, `skipped`.

### 3.3 L'isolation par règles d'une carte

| Situation | Geste | Ce qui est dit | Pourquoi | Où |
|---|---|---|---|---|
| intacte | laisse | rien ; `verified_at` noté, la marque de dérive ôtée ; une carte de contournement ou « non vérifiée » en attente se ferme | elle tient | `reassert.py:266-280` ; `reassert_cards.py:255-260` |
| disparue, la première fois, hors `human_only` | **repose** (`isolate_vm`), puis relit | « L'isolation de X avait disparu d'Azure (modification hors Glorfindel) : reposée une fois. Si elle disparaît encore, Glorfindel alertera sans la reposer. » Relue sans tenir : « … reposée, elle ne tient pas en entier : … » (`partial`). En échec : « … la reposer a échoué : … » | R3, R4 | `reassert.py:305-346` |
| disparue, en `human_only` ou déjà reposée | dit | « L'isolation de X a disparu d'Azure (règles ou NSG de quarantaine retirés) [une deuxième fois (déjà reposée le …)] — la VM n'est plus isolée. … Glorfindel ne les repose pas », et qui a écrit la carte (journal d'activité) | R2, R3 | `reassert.py:290-304` |
| disparue, déjà dite dans cet épisode | laisse | rien, même si une carte de plus perd son isolation | R5 | `reassert.py:285-289` |
| contournée par une règle du client | laisse | `bypassed`, une fois par changement ; avec des règles parties à côté (L1B, L1C), les deux cartes, et la repose de ce qui manque | R2 : la règle d'un tiers n'est jamais retirée | `reassert.py:272` ; `verify.py:119-132` |
| une levée en cours, en échec, ou une écriture partielle | laisse | rien ; une levée commencée depuis plus de 30 min : une fois « La levée de l'isolation de X a été interrompue … » ; une isolation `partial` n'est plus relue avant une isolation entière ou une levée, et la carte de sa repose le dit | I9 ; l'opérateur tient la VM | `reassert.py:250-260`, `:610-615` |
| lecture impossible (429, 403, une lecture qui lève) | laisse | `unverified` : « La vérification de l'isolation de X échoue (…) : … rien n'est reposé ni levé », une carte tant que ça dure, son texte suivant la dernière erreur | R6 | `reassert.py:261-269` ; `reassert_cards.py:312-363` |
| NSG partagé (le sous-réseau, un NSG de tier) | comme une isolation seule | comme une isolation seule | la paire est adressée aux IP de la carte, réécrite à sa place (I5R), jamais plus bas qu'une allow (I4D) | `docs/azure.md`, I5R, I4D |
| NSG détaché ou supprimé | comme « disparue » | comme « disparue » | une deny sur un NSG qui ne gouverne plus la carte ne tient rien : la carte est non couverte | `verify.py:53-75` |
| VM supprimée | laisse | depuis RSM3 (Q6) : sa carte à elle, `vm_gone` (« web n'existe plus sur Azure (VM supprimée) : son isolation … ne peut plus être vérifiée ni remise — rien n'est écrit. La lever : `glorfindel release …` »), fermée à la levée ; la carte « non vérifiée » se ferme ; sa paire, par le balayage des orphelines (M1). Avant : `unverified` (« (ResourceNotFound) … ») | elle ne peut pas être relue ; lue partie sur le 404 de la VM seule (`vm_gone`), jamais sur un 429 (A0) | `reassert_gone.py` ; `gone.py` ; `orphans.py` |
| IP réattribuée | comme « disparue » : reposée pour l'adresse actuelle, ou dite | comme « disparue » ; ce que la réécriture laisse parce qu'il vise une autre VM est dit sur la carte (I4B) | la paire visait l'ancienne adresse | `reassert.py:312-313` |

### 3.4 La quarantaine

| Situation | Geste | Ce qui est dit | Pourquoi | Où |
|---|---|---|---|---|
| intacte | laisse | rien ; une carte `quarantine_altered` en attente se ferme (« entier de nouveau ») | elle tient | `verify.py:38-46` ; `reassert_quarantine.py:123-146` |
| altérée ou vidée, la VM a un état | **repose**, par l'isolation de la VM (§3.3), qui réécrit le NSG pour toutes ses cartes | comme une isolation disparue ; le passage par NSG, après les isolations, ne dit plus rien s'il relit le NSG entier. En `human_only`, rien n'est reposé : deux cartes, celle de l'isolation et celle du NSG | la carte en quarantaine altérée est non couverte | `verify.py:66-71` ; `reassert.py:218` |
| altérée, aucun état ne la nomme (état perdu) | laisse | `quarantine_altered` : « Le NSG de quarantaine N ne porte plus les règles de Glorfindel (…) … Glorfindel ne le repose pas seul pour des cartes dont il n'a pas l'état », une carte par NSG et par changement | I5 : sans état, ni la VM ni son mode | `reassert_quarantine.py:160-182` |
| contournée | sans objet | une allow ajoutée dans notre NSG de quarantaine est une **altération** (`_opens_quarantine`), pas un contournement | le NSG n'a que nos règles | `quarantine.py:427-428` |
| détachée de la carte, la VM a un état | comme « disparue » | comme une isolation disparue | la carte nue n'a rien de l'isolation | `verify.py:63-75` |
| détachée, aucun état ne la nomme | laisse | **rien** : le NSG ne la porte plus, aucun état ne la nomme | rien ne la lit (§5, E9) | `quarantine.py:431-458` |
| une levée en cours | comme §3.3 | comme §3.3 | | |
| qu'on ne sait pas juger (la configuration illisible, nos deny intacts : l'accès forensique inconnu) | laisse | l'isolation : `unverified` ; le passage par NSG : sa carte reste, aucune nouvelle | R6 ; le mode est aussi `human_only` | `quarantine.py:416-426` ; `reassert_quarantine.py:123-128` ; `watch/passes.py:59-66` |
| lecture impossible | laisse | le NSG illisible : `unverified`. La liste des NSG en échec : aucune carte de quarantaine ne se ferme. Absent de la liste n'est pas disparu : il est relu par son id ; un 404 ferme la carte, tout le reste la garde ; un NSG d'un autre abonnement garde sa carte, dit une fois au journal (I1S, ISU) | R6 | `reassert_quarantine.py:67-116` |
| partagée par plusieurs VM | repose pour celle qui a un état, ce qui vaut pour toutes ; dit une carte par NSG, toutes ses cartes nommées | | I5 l'admet pour une VM en `human_only` (`_shut_shared`) | `inv:1768-1795` |
| VM supprimée | comme §3.3 | comme §3.3 ; le NSG vide se ferme | | `reassert_quarantine.py:123-128` |
| IP réattribuée | sans objet | | la quarantaine n'est adressée à aucune IP | |

### 3.5 Le blocage d'une IP sur une VM

| Situation | Geste | Ce qui est dit | Pourquoi | Où |
|---|---|---|---|---|
| intact | laisse | rien ; `verified_at`, les marques de dérive et `uncovered_said` ôtées | il tient | `reassert.py:407-409` |
| disparu (absent, retourné, rétréci, visant une ancienne adresse), la première fois, hors `human_only` | **repose** (scope `vm`), puis relit | « Le blocage de IP sur X avait disparu d'Azure : reposé une fois. S'il disparaît encore, Glorfindel alertera sans le reposer. » (mesuré, M4). Sinon « … ses règles réécrites une fois (…), il ne tient pas en entier — … », ou « … le reposer a échoué : … » | R3, R4 | `reassert.py:452-539` |
| disparu, en `human_only` ou déjà reposé | dit | « Le blocage de IP sur X a disparu d'Azure [une deuxième fois] (règles) — » puis, carte par carte : « l'IP n'est plus bloquée sur … », « reste bloquée sur … par la règle de périmètre … », « on ne sait pas si l'IP est encore bloquée sur … » ; « Glorfindel ne le repose pas » | R2, R3, R6 | `reassert.py:442-451` ; `reassert_said.py:8-61` |
| disparu, déjà dit | laisse, sauf si c'est pire | rien tant que ce n'est pas pire que la référence (plus bloqué du tout, une règle de plus partie par ce qu'Azure tient, une carte de plus ouverte ou inconnue) et, carte acquittée, qu'aucune de ses règles n'a été réécrite depuis ; sinon une carte nouvelle | R5 | `reassert.py:389-397`, `:433-441` ; `reassert_said.py:87-184` |
| ses règles parties derrière la quarantaine (`held_missing`) | **repose**, ou dit | « … a disparu d'Azure en partie — l'IP reste bloquée … » | avant que la levée n'ouvre la carte (A0) | `verify_block.py:119-130` ; `reassert.py:36-43` |
| contourné par une règle du client | laisse | `bypassed`, pour la menace seulement ; avec des règles parties, les deux cartes | R2 | `verify_block.py:182-200`, `:249-257` |
| un déblocage en cours, en échec, ou partiel | laisse | rien ; commencé depuis plus de 30 min : une fois « Le déblocage de IP sur X a été interrompu … » ; un blocage réécrit en entier efface ces marques (L1B) | l'opérateur tient la VM | `reassert.py:370-382`, `:618-624` |
| la carte en quarantaine, une quarantaine qu'on ne sait pas juger | laisse, ou dit | ses règles hors de la carte sont lues ; parties ou altérées, « a disparu », la carte « on ne sait pas » (L1Nd) ; présentes : `unverified` | R6 | `verify_block.py:131-152` |
| lecture impossible | laisse | des règles illisibles, ou un NSG de sous-réseau illisible (I3N) : `unverified`. Une carte illisible parmi des règles qui manquent : le manque est dit, la carte « on ne sait pas » (I3P) | R6 | `verify_block.py:50-57`, `:153-160`, `:258-268` |
| NSG partagé | comme un blocage seul | comme un blocage seul | la paire est adressée aux IP de la carte (I4) | |
| NSG détaché | comme « disparu » : reposé sur le NSG qui gouverne maintenant | « … (… ne gouverne plus X) … » ; le NSG détaché est lu quand même, pour `rules_seen` seulement (L1N) | une règle d'un NSG qui ne gouverne plus la carte ne bloque rien | `verify_block.py:161-167` |
| VM supprimée | laisse | depuis RSM3 (Q6) : ses règles en place ou parties, sa carte `vm_gone`, avec `glorfindel unblock …`, fermée au déblocage ; aucune repose tentée. Avant : `unverified` (« La vérification de le blocage … »), ou « le reposer a échoué : (ResourceNotFound) … » (M2, M3). Limite : une entrée d'une ancienne version (une règle, sans placement) n'est pas lue partie | elle ne peut pas être relue | `reassert_gone.py` (`checked`) ; `verify_block.py:50-57` |
| IP réattribuée | comme « disparu », relu pour l'adresse actuelle ; une règle à son nom qui vise désormais une autre VM : laissée | `rule_left` : « Le blocage de IP sur X a laissé telles quelles des règles à son nom qui visent une adresse qui n'est plus celle de X … », une carte par ensemble, jamais une écriture (I4A) | la réécrire changerait les flux de l'autre VM | `reassert_cards.py:388-431` ; `reassert.py:369` |

### 3.6 Le blocage de périmètre

| Situation | Geste | Ce qui est dit | Pourquoi | Où |
|---|---|---|---|---|
| intact | laisse | rien ; une carte hors de ce sous-réseau, qu'un autre de nos périmètres coupe, est tenue (L1Qs) | | `verify_block.py:294-317` |
| la paire disparue | **repose** au premier temps, avant tout blocage de VM, décidé comme le second le déciderait ; marquée `reasserted_at` aussitôt. Le second temps lit l'entrée et la finit : les règles de la VM pour une entrée fusionnée, la relecture, la carte | comme §3.5 ; une paire écrite partielle par une passe coupée : « sa règle de périmètre réécrite à la passe précédente » (RW2) | une paire coupe toutes les VM du sous-réseau : lue avant, une VM était dite ouverte à tort (L1Qr, L1Qs) | `reassert_perimeters.py:24-98` ; `reassert.py:360-368`, `:455-539` |
| la paire réécrite pour une autre VM | finit l'épisode acquitté de l'entrée qui la nomme | ce qui reste parti est reposé, ou dit de nouveau | une paire par IP et par sous-réseau, nommée par toutes les entrées ; le journal de nos écritures de paire le montre quand aucune lecture ne le peut (L1W) | `reassert_said.py:111-167` |
| jamais couverte (une carte de la VM sur un autre sous-réseau) | laisse | une fois par ensemble de cartes : « Le blocage de périmètre de IP ne couvre pas … de X : non couverte(s) depuis le blocage (autre subnet), l'IP les atteint. Bloquer aussi la VM (scope vm) » ; sa propre marque | reposer la paire ne couvre rien de plus (RB1). Seulement pour des cartes vraiment sur un autre sous-réseau depuis RSM3 : la paire dont le NSG ne gouverne plus aucune carte de la VM est dite à part (ligne suivante) | `reassert.py:410-428` |
| contourné | laisse | `bypassed` | R2 | `verify_block.py:282-290` |
| la paire levée par le déblocage d'une voisine | comme « disparue », pour l'entrée qui la nomme encore | | L1Q | |
| lecture impossible | laisse | la paire illisible : `unverified`, jamais « denied for ALL VMs » (I3W) ; le sous-réseau d'une carte hors du périmètre illisible : « on ne sait pas » | R6 | `verify_block.py:278-281`, `:297-299`, `:312-314` |
| NSG partagé | voulu | | le périmètre coupe l'IP pour toute VM du sous-réseau : la décision de l'opérateur ; pour une voisine en `human_only`, seuls les flux de l'attaquant que la paire ferme (I5S) | `inv:1768-1795` |
| le NSG ôté du sous-réseau, ou remplacé (RSM3, #1057, la nuit n° 50) | laisse : jamais reposée, ni sur ce NSG, ni sur celui que le sous-réseau porte maintenant ; les règles de la VM d'une entrée fusionnée, parties aussi, sont reposées seules | une carte du blocage à elle (`perimeter_off`) : « La règle de périmètre du blocage de … a disparu du sous-réseau de … : son NSG rg/nom ne gouverne plus aucune carte de … — ôté du sous-réseau par le client, remplacé par un autre, ou la VM a changé de sous-réseau. Elle ne couvre plus … Ôté ou remplacé, ce NSG ne la fait plus tenir pour les autres VM du sous-réseau ; la VM déplacée, elle les couvre encore. Glorfindel ne la repose pas … » (relecture de RSM3, 25/11), une fois par NSG, fermée quand le NSG revient ; une carte de contournement d'avant se ferme. Avant : « ne couvre pas … (autre subnet) » (M5), « contourné » avec une allow (#1057), rien pour une entrée fusionnée | partie pour l'endroit où elle est (§2.3) ; le sous-réseau d'une carte illisible, aucune gouvernée : inconnue (A0) | `perimeter.py` (`_pair_at_home`, `_pair_off`) ; `reassert_gone.py` |
| VM supprimée | comme §3.5 | | | |
| IP réattribuée | sans objet pour la paire | | elle n'est adressée qu'à l'IP bloquée | |

---

## 4. Les invariants qui la tiennent

La machine juge la réaffirmation surtout dans la règle `reassert` (`inv:1631-1743`), après une passe sans
faute, et dans des règles composées qui fabriquent un cas rare. Sous une faute, seuls I5, I9 et I10 sont
jugés.

| Situation | Ce qui la tient | Où la machine le juge | Ce qui manque |
|---|---|---|---|
| intacte | I3 : une carte « reposée une fois », « reposé une fois » ou « reste bloquée » dit vrai ; une vérification `True` est vraie. I3 encore : aucune carte de dérive pour un blocage dont chaque règle est telle que Glorfindel l'a écrite (RB1). I5 : rien d'ouvert | `_isolation_cards_true` (`inv:1898-1916`), `_block_cards_true` (`:1964-2014`), `every_claim_is_true` (`:3847-3878`), `_no_drift_on_untouched` (`:1879-1896`), après chaque passe | `_attacker_flows` lit les sondes seules (§5, E4) |
| disparue, un blocage | L1 et L3 | après chaque passe sans faute : `_block_vanished` ; la carte acquittée : `_ack_holds` ; une carte hors du graphe : L3 | depuis RSM2a (22/11), par le **contenu** (`invariant_hold`) : une règle retournée ou visant une ancienne adresse compte partie (E1, fait). Reste : la L1 d'un blocage n'exige rien tant qu'une de ses règles tient |
| disparue, une isolation | L1 et L3 | depuis RSM2a, après chaque passe sans faute (`_isolations_said`, E5) ; et dans deux règles composées, `_gone_comes_back` et `graph_card_before_a_disappearance` | les exemptions lisent encore les marques du code (E3, RSM2b) |
| la quarantaine altérée | L2 : entière, ou dite ; dite, elle le reste hors de la liste (I1S) | après chaque passe sans faute (`inv:1692-1712`) ; `quarantine_altered_then_reasserted`, `quarantine_change_comes_back` (`:2559-2606`) | détachée, sans état : rien (§5, E9) |
| contournée | L1 et L2 (L2C) : un contournement est dit, et le reste tant qu'il tient | seulement dans `_bypass_comes_back` | `bypassed()` ne lit plus que les règles que le classement lit intactes (E2, fait) ; la règle reste jugée dans une seule règle composée |
| une levée en cours | I9 : une levée commencée n'est jamais défaite, du journal du test | après chaque passe, faute ou non (`inv:1727-1728`) | les exemptions de L1, L3 et du contournement lisent les marques du code (§5, E3) ; la carte d'une levée périmée : aucun oracle |
| quarantaine qu'on ne sait pas juger | I10 (aucune quarantaine écrite) ; L2 (une altération reste dite) ; L1 pour un blocage derrière (les cas figés de L1Nd) | `config_changes`, `quarantine_change_comes_back` | le mode « alerte seule » d'une configuration illisible n'est pas atteint : la machine remplace `_mode` (`inv:4375`) |
| lecture impossible | I3 : une lecture qui échoue donne un inconnu, jamais un oui | `verify` (`inv:1618-1629`), chaque API en 429 tour à tour | la carte `unverified` : aucun oracle ; une passe sous faute ne doit rien dire |
| NSG partagé | I4 (`scoped_on_a_shared_nsg`) ; I5 par VM (`_shut_shared`, I5S) | à chaque pas ; après chaque passe (`inv:1730-1742`) | |
| NSG détaché ou supprimé | L1 pour un blocage (les cas figés de L1N, L1Nb), et pour une isolation (E5) ; I1 l'excuse pour une carte nue | `customer_deletes_nsg`, `someone_detaches_the_quarantine`, `customer_changes_subnet_nsg` (le NSG d'un sous-réseau ôté, remplacé ou remis : E7, RSM2a) | le texte « autre subnet » : `tests/unit/test_reassert_gone.py` (RSM3), pas d'oracle ; la machine n'excuse plus rien de cette famille |
| VM supprimée | I3 de sa levée (I7S) ; U1 pour ses règles (`orphans_are_reported`, `inv:4276-4300`) | | ce que la passe dit d'elle : des tests unitaires (`test_reassert_gone.py`, RSM3), aucun oracle : `live` l'exclut (`inv:723-725`) (§5, E8) |
| IP réattribuée | I4 (I4A, I4B) ; U1 ; L1 pour un blocage, mais par les noms | `address_reused`, `address_reused_under_a_turned_rule`, `turned_then_address_reused` | la carte `rule_left` : aucun oracle |
| verrou tenu | L1 et L3 attendent la passe suivante (`_is_busy`) | `reassert_by_vm` | la carte des passes sautées (SEC-H) : aucun oracle |

---

## 5. Les écarts

Les quatre premiers répondent aux contre-exemples d'oracle de la période, les trois sûrs (I9A, I3X, L1V)
et L1Nc, qui se discute (§1.1) : chacun est un mot du §2.3 que l'oracle définit autrement que le code.
Pour chacun, la proposition dit où corriger : le code, l'oracle, ou la règle écrite.

**E1 — « Disparue » a quatre définitions dans l'oracle, et aucune n'est celle du code (L1Nc).**
- *Le code.* Par contenu, pour les adresses actuelles, sur un NSG qui gouverne la carte : absente ou
  `altered` (§2.3). Entre deux passes, `_worse` compte pire une règle de plus partie par son nom, ou lue
  là puis absente par sa signature (§1.2). Une deny à notre nom retournée en autorisation est dite
  disparue et réécrite, pour son placement (mesuré, M4 ; après un acquittement, sur la séquence de L1Nc,
  §1.1), avec les deux nuances du §2.3.
- *L'oracle.*
  - Pour un blocage, L1 se juge par les noms : toutes les règles nommées absentes (`_block_vanished`,
    `inv:1575-1596`). Une deny retournée, ou qui vise une ancienne adresse, y compte présente.
  - Pour une isolation, par les flux : ce qui s'ouvre depuis que le test a ôté nos règles (`_gone_said`,
    `_said_on_its_own`).
  - Pour un blocage dans `turned_perimeter_left_out`, par les flux de l'attaquant (`_open_said`,
    `inv:3425-3436`).
  - Pour l'acquittement, par la présence de ce qui était présent (`_ack_holds`, depuis L1Nc).
- *La conséquence.* L1 d'un blocage est plus faible que le produit. Un blocage dont toutes les denies
  ont été retournées n'est pas « disparu » pour L1 : si la réaffirmation cessait de le dire, aucun
  invariant ne le verrait (`_open_said` ne juge que les voisines d'un périmètre retourné, dans une règle
  composée ; `_bypass_said`, que les règles d'un tiers). Et quatre définitions voisines
  font que le prochain oracle en écrira une cinquième.
- *Proposition.* Écrire la règle (§2.3, ce document). Puis **corriger l'oracle** : un seul classement de
  la tenue, lu dans le monde du test et jamais dans la vérification du code (A0). Carte par carte, la
  tenue est intacte, partie (absente, retournée, visant ailleurs, sur un NSG qui ne gouverne plus),
  contournée ou inconnue (une faute jouée). L1, L3, `_ack_holds`, `_open_said` et `bypassed()` le lisent
  (RSM2a).
- *Fait (RSM2a, 22/11).* `tests/unit/invariant_hold.py` lit chaque règle d'une tenue dans le monde du faux
  Azure, par son contenu : une deny de tout protocole et de tout port ; l'attaquant (un blocage) ou
  n'importe qui (une isolation) de son côté ; chaque adresse actuelle de la carte de l'autre (n'importe qui,
  pour une paire de périmètre) ; sur un NSG qui gouverne la carte. Inconnue : un NSG illisible
  (`fake.unreadable`, I1S). Deux indulgences, chacune dans le sens sûr (l'oracle exige moins, jamais plus) :
  derrière notre quarantaine, les règles d'un blocage se lisent où qu'elles soient, comme le code les lit
  pour la levée à venir ; et l'isolation d'une carte est n'importe laquelle de nos denies d'isolation qui la
  coupe par son contenu. `_block_vanished`, `_ack_holds` (Q2 : la règle de L1Nc renversée, §1.1), `_open_said`
  (une carte inconnue n'y est pas jugée) et `bypassed()` le lisent. La L1 d'un blocage garde sa forme
  faible : toutes ses règles parties, ou sa paire de périmètre.
- *Ce que la proposition renverse.* Lire « retournée » comme « partie » (Q2, option 1) **renverse la
  règle que L1Nc a écrite dans `_ack_holds`** : « A named rule still present but turned into an allow has
  NOT vanished ». Le cas figé `test_a_block_deny_turned_after_an_acknowledged_perimeter_loss_is_no_worse`
  vérifie l'inverse (`m._ack_holds(DB) is True` juste après le retournement,
  `test_invariant_regressions.py:8325`). Avec RSM2a, ce test et la séquence figée de L1Nc changent : ils
  ne passent pas tels quels. C'est aussi pourquoi L1Nc est à re-mesurer avant (§1.1).

**E2 — « Contournée » n'a de définition que dans une docstring de l'oracle (L1V).**
- *Le code.* Une allow d'un tiers avant une deny à nous qui refuse encore, pour les adresses de la carte.
  Pour un blocage, seulement ce qui laisse passer la menace. Dans notre NSG de quarantaine, une allow est
  une altération.
- *L'oracle.* Depuis L1V, les flux que les denies de la tenue ferment, évaluées en premier
  (`inv:2776-2791`). C'est juste, mais écrit à un seul endroit, pour une seule règle composée.
- *Proposition.* Écrire la règle (§2.3, §3) et la mettre dans le classement d'E1. Le code ne change pas.
- *Fait (RSM2a, 22/11).* `bypassed()` ne remonte en tête que les règles de la tenue que le classement lit
  intactes : une deny rétrécie, retournée ou qui vise ailleurs relève de la disparition, jamais du
  contournement.

**E3 — « Tenue par une opération » se lit tantôt dans le journal du test, tantôt dans les marques du code
(I9A).**
- *Le code.* Une marque d'intention, d'échec ou de partiel retient la passe (`_held_by_an_operation`,
  `reassert.py:227-228`). Une isolation ou un blocage écrits en entier effacent ces marques.
- *L'oracle.* I9 lit le journal du test (`self.releasing`), fini depuis I9A aussi par une écriture
  d'état. L1B a fait de même pour le déblocage (`reblocked`). Mais les exemptions de L1, L3 et du
  contournement lisent encore les marques du code : `partial`, `release_failed`, `releasing_at`
  (`inv:2709-2711`, `:2840-2843`, `:3267-3270`) ; `_block_held` lit `partial`, et `unblock_failed` ou
  `unblocking_at` tant que le test n'a pas réécrit le blocage (`:2112-2119`).
  A0 l'interdit : un défaut qui pose une marque à tort ferait taire L1, L3 et le contournement pour cette
  tenue, et aucun oracle ne le verrait.
- *Proposition.* **Corriger l'oracle** : la machine note chaque opération qu'elle a vue coupée ou
  partielle (la faute qui a joué, la réponse `release_partial` ou `unblock_partial`, une isolation
  partielle), et les exemptions lisent ce journal (RSM2b). Écrire la règle : ce qui commence une levée en
  cours, ce qui la finit, et ce que veut dire `partial` (plus relue avant une tenue entière ou une levée,
  et dit une fois, sur la carte de l'écriture).

**E4 — « Coupée » se juge encore sur les sondes dans `_attacker_flows` (I3X, I3Xb).**
- *Le code.* Le modèle de la préséance : en entrée, le port de la menace (tous s'il est inconnu) ; en
  sortie, tout port et tout protocole.
- *L'oracle.* `_perimeter_only` lit `ATTACKER_WAYS` depuis I3X. `_attacker_flows` (`inv:1405-1409`) lit
  toujours les sondes, toutes TCP, la sortie vers l'attaquant sur 443 seulement. C'est le juge de
  « reposé une fois », « reste bloquée », `verify_block_ip` vrai et `_open_said`. Une allow sortante sur
  22 ou en UDP avant notre `-out` y échappe (`preuves.md`, « Resté ouvert (I3Xb) »). Ici l'oracle est plus
  faible que le produit : il laisserait passer une carte « reste bloquée » fausse.
- *Proposition.* **Corriger l'oracle** (I3Xb) : `_attacker_flows` sur `ATTACKER_WAYS`. Le coût en temps
  de la machine est à mesurer : douze voies au lieu de trois sondes.

**E5 — La disparition d'une isolation n'est jugée que dans deux règles composées.**
- *Le code.* Une isolation disparue est reposée une fois ou dite, après chaque passe, quelle qu'en soit la
  cause.
- *L'oracle.* La L1 d'un blocage est jugée après chaque passe sans faute ; celle d'une isolation, jamais.
  Une isolation défaite par un `terraform_apply`, un `customer_changes_ip`, un NSG détaché ou une
  quarantaine ôtée de la carte, tirés seuls, n'est jamais exigée dite. I1 excuse la carte laissée nue
  (`inv:3797-3804`), « jusqu'à ce que la levée ou la réaffirmation y remette quelque chose » : rien ne
  vérifie que la réaffirmation le fait.
- *Proposition.* **Corriger l'oracle** : L1 d'une isolation après chaque passe sans faute, par les flux
  du monde, comme `_gone_said`, à travers le classement d'E1 (RSM2a). C'est un durcissement : il peut
  faire rougir la machine sur des défauts anciens du produit. Il se mesure à 2 000 exemples et sur une
  nuit avant la fusion.
- *Fait (RSM2a, 22/11).* `_isolations_said`, après chaque passe sans faute : une VM dont l'isolation est
  enregistrée, qu'aucune opération ne tient (les exemptions de `_gone_said`, que RSM2b déplace), et dont une
  carte a perdu son isolation dans le monde du test, a une carte de la réaffirmation à elle (jamais celle du
  graphe). Une carte acquittée (`_gone_comes_back`) tient pour son épisode : jusqu'à ce que le test isole de
  nouveau la VM, ou qu'une passe sans faute commence avec l'isolation tenue (Q5 : une carte par épisode).
  À 500 et à 2 000 exemples, elle n'a trouvé aucun défaut du produit.

**E6 — Une isolation dite ne se redit pas quand elle empire ; un blocage, si.**
- *Le code.* Pour un blocage : `still_said` et `_worse` (`reassert_said.py:170-184`) redisent une
  disparition pire que la carte (RB1, quatrième relecture). Pour une isolation : `drift_said` seul
  (`reassert.py:285-289`), et sa carte ne nomme pas ses cartes réseau (`:292-299`).
- *L'oracle.* Aucun invariant ne juge le pire d'une isolation.
- *Proposition.* **Écrire la règle** telle qu'elle est (Q5) : la carte d'une isolation dit déjà le pire
  (« la VM n'est plus isolée »). L'aligner sur les blocages est l'autre option (RSM4).

**E7 — Le NSG ôté du sous-réseau d'un périmètre est dit « autre subnet » (mesuré, M5).**
- *Le code.* La paire est présente sur un NSG qui ne gouverne plus aucune carte de la VM. Toutes ses
  cartes sont donc « hors du périmètre » (`_off_perimeter`), et la branche « jamais couverte » les dit
  « non couverte(s) depuis le blocage (autre subnet) ». La moitié de la phrase est vraie (l'IP les
  atteint), l'autre fausse : elles étaient couvertes, et elles sont sur ce sous-réseau. Rien n'est écrit,
  et c'est juste (la paire est là, à nous, sur un NSG que le client a ôté). Mais la carte invite à
  « bloquer aussi la VM » au lieu de dire ce qui est lu.
- *L'oracle.* Le monde de la machine ne retirait jamais le NSG d'un sous-réseau.
- *Proposition.* **Corriger le code** : la branche dit ce qu'elle lit (le NSG de la paire ne gouverne
  plus le sous-réseau de la carte), et propose de le remettre ou de bloquer la VM (RSM3). **Corriger
  l'oracle** : le monde tire le NSG ôté ou remplacé sur un sous-réseau (RSM2a).
- *Fait, pour l'oracle (RSM2a, 22/11).* `customer_changes_subnet_nsg` ôte le NSG d'un sous-réseau, en met un
  autre du client à sa place (ses règles, jamais les nôtres), ou remet celui qu'il a ôté ; la conception
  suit le client (I1, I2). Ce qui reste sur le NSG ôté — une paire de périmètre, un placement sur le
  sous-réseau — ne gouverne plus rien : parti. La machine y a trouvé deux fois la même limite de l'oracle,
  pas du produit : nos règles sur le NSG du sous-réseau, ce NSG ôté, et rien qui les trace — l'état de la VM
  perdu par le test (une isolation, à 500 exemples), ou un blocage coupé par une faute avant d'écrire son
  entrée (à 2 000). La levée ou le déblocage sans trace ne peuvent plus lire ces règles, que rien ne lie plus
  à la VM, et I3 puis I7 les jugeaient laissées à tort (`_loose`, comme `_untied` pour le NSG propre d'une
  carte, I8F ; `test_a_rule_nothing_records_on_a_subnets_nsg_taken_off_is_out_of_reach`). Avec sa trace, la
  levée les lit où ses placements les ont posées, et les retire (mesuré). Resserrée après la relecture : seul
  un NSG qu'aucune trace actuelle ne nomme (l'état, les entrées de blocage), et seules des règles écrites
  avant que le test perde l'état (daté dans le journal du faux) ou par une opération du test où une faute a
  joué (`test_a_rule_its_entry_still_names_stays_in_reach`, M7078). Le texte « autre subnet » reste à
  RSM3.
- *La nuit du 24/11 (graine 439290643, tête de la PR).* Deux contre-exemples I3, de l'oracle encore : le test
  ne gardait qu'un NSG ôté par sous-réseau (celui que « back » remet), et un « remplacé » suivi d'un « ôté »
  oubliait le premier, que `_loose` ne connaissait plus. Le test garde désormais tous les NSG ôtés
  (`subnet_nsgs_off`), pour `_loose` comme pour l'excuse de #1057, qui reste celle d'un défaut connu et
  ouvert du produit (`test_a_release_is_not_failed_for_our_rules_on_a_subnet_nsg_replaced_then_taken_off`,
  M7463).
- *Un défaut du produit trouvé (RSM2a, 22/11, #1057).* À 2 000 exemples : une paire de périmètre sur le NSG
  ôté du sous-réseau, une règle d'autorisation ajoutée sur ce NSG détaché — la passe dit le blocage
  « contourné » par elle, n'écrit rien, et ne dit ni la disparition ni la carte non couverte, alors que la
  carte n'a plus aucun NSG. La table le dit parti ; « contournée » suppose la tenue intacte. Non corrigé ici
  (la famille de RSM3) : figé en `xfail` strict
  (`test_a_perimeter_on_an_nsg_taken_off_its_subnet_is_not_said_bypassed`, ses préconditions vérifiées hors
  du `xfail`), et excusé par la machine, lui seul (`_known_1057` : la seule paire de périmètre, partie pour
  sa seule place sur un NSG ôté d'un sous-réseau, et une carte « contourné » qui nomme ce NSG), jusqu'au
  correctif. M7048 et M7049 gardaient l'excuse contre un élargissement (`test_the_excuse_of_1057_is_1057_alone`).
  **Corrigé (RSM3, #1036, 24/11)** : la vérification d'un périmètre seul demande d'abord si le NSG de sa paire gouverne encore une carte de la VM (`_pair_at_home`, avant le contenu et la préséance) ; sinon, la paire est partie, dite sur une carte du blocage (`perimeter_off`), jamais reposée. Le `xfail` passe, il est devenu un test normal (les deux modes) ; `_known_1057` est retiré de l'oracle, M7048 et M7049 avec lui (`test_no_excuse_is_left_for_an_nsg_taken_off` : l'oracle n'excuse plus rien de cette famille).
- *Un autre défaut du produit, la même famille (la nuit n° 50, 24/11, graine 511946931, tête de la PR).* Une
  VM bloquée sur son sous-réseau et pour elle-même (une entrée fusionnée, sa carte sur son propre NSG), puis le
  NSG du sous-réseau ôté : la paire reste, intacte, sur un NSG qui ne gouverne plus rien, et les autres VM du
  sous-réseau sont de nouveau atteintes. La vérification lit la paire fusionnée par son contenu, sur le NSG
  qu'elle nomme, sans demander s'il gouverne encore le sous-réseau (`verify_block.py`, la paire de
  `_merged_perimeter`) ; la VM tient par sa propre règle, le contrôle dit `True`, la passe ne dit rien. De même
  sur `main` (le produit n'est pas touché par RSM2a ; sa machine n'ôte jamais le NSG d'un sous-réseau). Onze
  pas la nuit, quatre à la main : figé en `xfail` strict
  (`test_a_merged_perimeter_on_an_nsg_taken_off_its_subnet_is_said`, ses préconditions hors du `xfail`).
  Non corrigé ici, ni excusé par la machine : RSM3 (#1036) le corrige, avant RSM2b et I3Xb (décision de Jonathan
  du 24/11), et RSM2a fusionne après la nuit verte de RSM3.
  **Corrigé (RSM3, #1036, 24/11)** : la paire d'une entrée fusionnée est lue partie quand son NSG ne gouverne aucune des cartes que la vérification lit (`_pair_off`) ; la VM tenue par ses propres règles, la vérification reste `True` et porte `perimeter_off`, comme `perimeter_gone` (I3W) ; la passe le dit sur une carte du blocage, n'écrit rien, et ne repose que les règles de la VM si elles sont parties aussi. Le `xfail` passe, devenu un test normal (les deux modes).
- *La relecture de RSM3 (25/11).* Une écriture sans lecture restait : les cartes de la VM illisibles à la vérification (un 429), la paire était lue « chez elle » et, partie, reposée sur le NSG de remplacement que portait le sous-réseau à l'écriture. Corrigé : les cartes illisibles, une paire entière est non lue (`pair_unread`) ; aucune repose n'écrit la paire sur `perimeter_off`, `pair_unread` ou `nics_unread` (`_pair_not_home`) ; et une repose refuse un autre NSG que celui que l'entrée enregistre (`refused_elsewhere`, `perimeter_nsg_now`). La carte dit les trois causes possibles (ôté, remplacé, la VM changée de sous-réseau), et « les autres VM du sous-réseau ne sont plus couvertes » seulement sous les deux premières. Limite connue (25/11, relecture de RSM3) : un NSG partagé par deux sous-réseaux de la VM, ôté d'un seul, garde la paire lue chez elle tant qu'une carte de la VM reste derrière lui, sur l'autre sous-réseau ; les VM du sous-réseau d'où il a été ôté ne sont plus couvertes, et rien ne le dit. Le corriger demande d'enregistrer le sous-réseau de la paire (un changement de schéma de l'état), posé à Jonathan ; la suite le dira.

**E8 — Rien ne juge ce que la passe dit d'une VM supprimée (mesuré, M1–M3).**
- *Le code.* Une isolation : la carte « non vérifiée » (« (ResourceNotFound) … »), jusqu'à la levée.
  Un blocage : la même carte, ou « a disparu ; le reposer a échoué : (ResourceNotFound) … ». Rien n'est
  écrit. Et le texte de la carte d'un blocage dit « La vérification **de le** blocage »
  (`reassert_cards.py:320`, `:352`).
- *L'oracle.* `live` exclut une VM supprimée (`inv:723-725`) ; `_block_cards_true` et
  `_isolation_cards_true` sautent ses cartes ; I5 ne la regarde pas.
- *Proposition.* **Corriger le code** (Q6) : une carte à elle, « la VM n'existe plus », avec la commande
  de levée (qui sait lever une VM partie, I7S), fermée à la levée ; et « du blocage » (RSM3). **Corriger
  l'oracle** : une carte de la passe sur une VM supprimée ne dit jamais « reposé » ni « reste bloquée »,
  et aucune écriture ne vise ses règles hors du balayage des orphelines.
- *Fait, pour le code (RSM3, #1036, 24/11).* Sa carte à elle (`vm_gone`, action `review_gone_vm`), avec la commande de levée ou de déblocage, fermée à la levée ; la carte « non vérifiée » se ferme ; aucune repose tentée, rien n'est écrit. La VM n'est lue partie que sur son propre 404 (`vm_gone`), et seulement là où la vérification lève, ne conclut pas, ou dit des règles parties sans avoir lu les cartes. « du blocage » corrigé. L'oracle reste à écrire : la machine supprime une VM, mais aucune propriété ne juge encore la carte (tests unitaires seuls, `tests/unit/test_reassert_gone.py`).

**E9 — Sept situations n'ont aucun invariant.**
- la carte `unverified` (une vérification qui échoue est dite) ;
- la carte des passes sautées (SEC-H) ;
- la carte d'une levée ou d'un déblocage périmés (`time_passes` avance l'horloge, et seul I9 juge) ;
- l'alerte seule d'une configuration illisible, et le mode retenu par la préparation (la machine
  remplace `_mode`, `inv:4375`) ;
- la carte `rule_left` (I4A) ;
- une quarantaine détachée d'une carte dont l'état est perdu : ni le code ni l'oracle ne la lisent ;
- une passe sous faute ne doit rien dire : seuls I5, I9 et I10 y sont jugés.

Des tests unitaires tiennent les cinq premières (`tests/unit/test_reassert.py`,
`test_reassert_verified.py`, `test_reassert_status.py`, `test_watch_loop.py`, `test_glorfindel.py`). *Proposition* : écrire la
règle, c'est-à-dire cette table, et ne pas ajouter d'oracle pour elles. Pour la quarantaine détachée sans
état, c'est une limite à écrire, pas un oracle : sans état, rien ne dit que la carte était la nôtre (I5).
Elle se dit dans `docs/azure.md`, à côté de la limite connue d'I1S.

---

## 6. Les lots qui suivraient

Dans l'ordre, si Q1, Q2, Q3, Q4 et Q7 prennent l'option recommandée. Les mutants sont estimés ;
l'Orchestre donne les plages. RSM2a, RSM2b et I3Xb touchent tous `tests/unit/test_invariants.py` : ils se
suivent, sans se chevaucher. Les autres options changent le plan :
- **Q2 = 2** (retournée = contournée, la règle de L1Nc gardée) : RSM2a garde `_ack_holds` tel quel et ne
  lit plus la deny retournée comme partie ; son mutant « une deny retournée lue présente » tombe. C'est
  alors le produit qui change : la deny retournée dite sur la carte `bypassed`, plus réécrite ni redite
  « a disparu ». Ce lot de produit est à cadrer ;
- **Q3 = 2** (les marques gardées) : RSM2b ne se fait pas, et ses trois mutants tombent ; l'exception à A0
  s'écrit dans la docstring de la machine ;
- **Q4 = 2** (pas de L1 d'une isolation après chaque passe) : RSM2a perd cette partie, et son mutant
  « L1 d'une isolation coupée » tombe ;
- **Q5 = 1** : RSM4 ne se fait pas ;
- **Q1 = 2** : RSM5 ne se fait pas, et la table reste une photo du 21/11.

| Lot | Session | Contenu | Ce qu'il prouve | Taille | Mutants |
|---|---|---|---|---|---|
| **RSM2a** — la tenue lue une fois, dans le monde du test | Glorfindel (tests) | un classement par carte (intacte, partie, contournée, inconnue), du monde du faux Azure ; L1 d'un blocage par contenu ; L1 d'une isolation après chaque passe ; `_ack_holds`, `_open_said`, `bypassed()` sur lui ; le monde tire le NSG ôté d'un sous-réseau (E1, E2, E5, E7) | L1Nc re-mesurée d'abord (sa graine du 15/11 rejouée sur 7a049aca et sur `main`) ; les séquences figées de L1N, L1Nb, L1Nd, L1V, I3X et I9A passent ; celle de L1Nc et `test_a_block_deny_turned_after_an_acknowledged_perimeter_loss_is_no_worse` changent avec Q2 ; 2 000 exemples ; une nuit verte | M | **5** : une deny retournée lue présente ; une ancienne adresse lue tenue ; L1 d'une isolation coupée ; le classement lu dans la vérification du code ; le NSG du sous-réseau jamais tiré |
| **RSM2b** — les exemptions du journal du test | Glorfindel (tests) | la machine note les opérations qu'elle a vues coupées ou partielles ; `_block_held`, `_gone_said`, `_bypass_said`, `_said_on_its_own` le lisent, jamais les marques (E3) | M13 et M5321 restent attrapés ; 2 000 exemples | S–M | **3** : une marque `partial` du code qui exempte ; `releasing_at` lu dans l'état ; le journal jamais fini |
| **I3Xb** — les voies de l'attaquant dans `_attacker_flows` | Glorfindel (tests) | `ATTACKER_WAYS` pour « reposé une fois », « reste bloquée », `verify_block_ip` vrai, `_open_said` ; le coût mesuré (E4) | M5331 attrapé par la machine seule, pas seulement par ses cas figés | S | **2** : une sortie sur 22 lue fermée ; une sortie en UDP lue fermée |
| **RSM3** — ce que la passe dit de ce qui n'est plus là | Glorfindel | la VM supprimée (Q6) ; « du blocage » ; la branche « jamais couverte » qui dit le NSG de la paire hors du sous-réseau ; `docs/azure.md` (E7, E8) | les tests unitaires ; la machine, sur une VM supprimée puis sur un NSG ôté du sous-réseau | S | **3** : la carte « non vérifiée » d'une VM partie revenue ; « autre subnet » revenu ; une repose tentée pour une VM partie |
| **RSM4** — si Q5 = 2 : une isolation redite quand elle empire | Glorfindel | `_worse` pour une isolation, la carte nomme ses cartes réseau | les tests unitaires ; L1 d'une isolation (RSM2a) | S | **2** : le pire ignoré ; la carte qui ne nomme rien |
| **RSM5** — la section de `docs/glorfindel.md` autour de cette table | Glorfindel ou General | les cinq paragraphes (29 Ko) deviennent un résumé et un lien ; l'histoire, lot par lot, va dans `docs/historique.md` | `scripts/check_paragraphs.py` : rien de perdu | S | **0** |

Aucun de ces lots ne touche `_SYSTEM_PROMPT`, `_build_user_message()` ni `few_shot_examples.yaml`, et
aucun ne demande de run de bout en bout. Aucun ne touche le banc.

---

## 7. Les questions à Jonathan

Posées une à une par l'Orchestre. L'option recommandée vient en premier, avec sa raison. Rien n'est décidé
à sa place.

**Les réponses de Jonathan (21/11), écrites par RSM2a.** Q1 : 1 (la table est la référence). Q2 : 1 (une
deny retournée est disparue, comme le code le fait ; la règle de L1Nc renversée, après sa re-mesure). Q4 : 1
(la disparition d'une isolation jugée après chaque passe, par les flux du monde). Q7 : 1 (l'oracle d'abord :
RSM2a, RSM2b, I3Xb, RSM3, RSM5). Q3, Q5 et Q6 n'ont pas de réponse écrite ici ; RSM2a suit la règle telle
qu'elle est pour Q5 (une carte par épisode).

**Q1 — Cette table devient-elle la référence de la réaffirmation ?** (§3, §5)
1. **Oui (recommandée).** Un changement de la réaffirmation, du code ou de l'oracle, la met à jour dans la
   même PR, comme la doc aujourd'hui. Un écart entre le code et un oracle se tranche d'abord dans la
   table : la règle écrite, puis le code ou l'oracle. C'est ce qui a manqué aux trois défauts d'oracle, et
   ce qui laisse L1Nc en débat.
2. Non : la table reste une photo du 21/11, et la doc garde ses paragraphes par lot.

**Q2 — Une deny à notre nom retournée en autorisation, sur un blocage : disparue ou contournée ?** (§2.3,
E1)
1. **Disparue, comme le code le fait (recommandée).** C'est ce que le code fait, et c'est mesuré : M4, et
   après un acquittement, sur la séquence de L1Nc (§1.1). La règle est à notre nom : la réécrire ne touche
   rien du client (I2). La carte « contourné » reste aux règles d'un tiers, que Glorfindel ne retire
   jamais. L'oracle la compte disparue (RSM2a). **Cette option renverse la règle que L1Nc a écrite dans
   `_ack_holds`** (une deny retournée n'a pas disparu) : son cas figé change avec RSM2a, après la re-mesure
   de L1Nc.
2. Contournée, comme L1Nc l'a écrit dans l'oracle : le code la dirait sur la carte `bypassed`, ne la
   réécrirait plus et ne la redirait plus « a disparu ». C'est un changement de produit : celui qui
   retourne notre règle garderait la main sur elle.

**Q3 — Les exemptions de L1 (une opération qui tient la tenue) : du journal du test, ou des marques du
code ?** (E3)
1. **Du journal du test, comme I9 et L1B (recommandée).** A0 entier : un défaut qui pose une marque à
   tort ne fait plus taire L1, L3 et le contournement.
2. Garder les marques, et écrire l'exception à A0 : une marque fausse fait taire ces trois oracles pour
   sa tenue.

**Q4 — La disparition d'une isolation jugée après chaque passe ?** (E5)
1. **Oui, comme celle d'un blocage, par les flux du monde (recommandée).** Mesurée à 2 000 exemples et sur
   une nuit avant la fusion. L'Orchestre sait d'avance que la machine peut rougir sur des défauts anciens
   du produit, et que chacun aura son issue.
2. Non : les deux règles composées et les cas figés suffisent.

**Q5 — Une isolation dite, qui empire (une carte de plus sans isolation) ?** (E6)
1. **Écrire la règle telle qu'elle est : une carte par épisode (recommandée).** Sa carte dit déjà le pire
   (« la VM n'est plus isolée ») ; une carte de plus n'apprendrait rien à l'opérateur.
2. La redire, comme un blocage, et que la carte nomme ses cartes réseau (RSM4).

**Q6 — Ce que la passe dit d'une VM supprimée ?** (E8)
1. **Une carte à elle, « la VM n'existe plus », avec la commande de levée, fermée à la levée
   (recommandée).** Rien n'est écrit. La carte « non vérifiée » et « le reposer a échoué :
   (ResourceNotFound) » ne la disent plus à mots couverts. La levée d'une VM partie existe déjà (I7S).
2. Garder la carte « non vérifiée », qui dit l'erreur sans nommer la cause ; seul « du blocage » est
   corrigé.

**Q7 — Dans quel ordre ?** (§6)
1. **L'oracle d'abord (RSM2a, RSM2b, I3Xb), puis les textes (RSM3), puis la doc (RSM5) (recommandée).**
   Un oracle qui dit la table trouve les écarts du produit avant qu'on les corrige un par un.
2. Les textes d'abord : ils sont petits, et c'est ce que l'opérateur voit.
