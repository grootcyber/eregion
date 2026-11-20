# Gothmog — pannes déclarées

Gothmog est le troisième agent de la boucle : Annatar attaque, Gothmog casse, Glorfindel détecte
et répond. Ses pannes éprouvent d'abord Glorfindel : **bruit bénin** (G1, il ne doit pas
isoler : écritures disque, CPU, redémarrage), **pannes de ses dépendances** (G2, il doit échouer fermé), **reprise** (G3, temps
mesuré).

## G0 — une panne déclarée, mesurée, réversible

Une panne est **déclarée en code** à deux endroits :

- l'expérience Chaos Studio, dans Celebrimbor ([`infra/terraform/chaos.tf`](../infra/terraform/chaos.tf),
  activable par `chaos.enabled` dans `config.yaml`) : la VM inscrite auprès du moteur (cible +
  capacité `Shutdown-1.0`), l'expérience d'arrêt **propre** de 5 minutes, son identité avec un
  rôle sur mesure attribué sur cette VM seule (la lire, l'éteindre, la démarrer : pas la
  supprimer) ;
- la panne vue par Gothmog, [`experiments/vm-shutdown.yaml`](experiments/vm-shutdown.yaml), au
  schéma d'expérience d'E1 (`kind: fault`, `engine: chaos-studio`) : ses cibles, son état normal,
  ses conditions d'abandon, son retour. Elle est aussi au catalogue (`technique_catalog.yaml`,
  `azure_vm.faults`).

Gothmog n'écrit jamais l'expérience : il la lit, la démarre, la suit, l'annule au besoin.
Modèle « Experiments (classic) » : les Workspaces, vers lesquels Microsoft migre, sont en
préversion publique et hors du provider azurerm (09/2026).

### Le déroulé d'un run ([`runner/engine.py`](runner/engine.py))

| Étape | Ce qui se passe | Refusé si |
|---|---|---|
| 0. Glorfindel | le battement de la watch, lu avant tout appel au cloud (V1, [`eregion_core/watch_gate.py`](../eregion_core/watch_gate.py)) : le canal retour s'il est configuré, sinon le fichier local (la copie des injecteurs, `~/.glorfindel/injectors/watch_heartbeat`) ; relu juste avant le démarrage de la panne (SEC5) | aucun battement de moins de 90 s, ou un battement d'un autre abonnement ou sans périmètre (SEC5) : refusé, et le message dit pourquoi ; `--without-glorfindel` passe (jamais en production), le rapport et le journal d'Orodruin le disent |
| 1. Contrat | `arm(run_id, "gothmog")` ([`eregion_core/orodruin.py`](../eregion_core/orodruin.py)) | contrat passif (rien lu, rien touché) ; plafond sous 3 appels (démarrer, annuler, redémarrer la VM) |
| 2. Cibles | relues **dans l'expérience Chaos Studio elle-même**, puis chacune passée par l'inscription (O0, `kind="fault"`) | cible non déclarée par la panne ou déclarée absente ; sélecteur dynamique ; cible hors banc, non inscrite, en `production` ; arrêt brutal pour une panne déclarée non destructive ; durée au-delà du plafond du run |
| 3. Avant | sondes d'état normal sur chaque cible | une sonde ne tient pas, ou ne se lit pas |
| 4. Injecter | fenêtre d'exercice ouverte (`kind: fault`, publiée vers la watch hébergée), démarrage **journalisé avant l'appel**, signal `fault_started` | — |
| 5. Pendant | l'exécution suivie toutes les 30 s ; la panne doit être constatée : son **effet** déclaré (G1), la VM arrêtée ou le bruit vu dans Perf ; les sondes marquées `during` tiennent (G1) | une sonde `during` qui ne tient plus : l'expérience est **annulée** (le bruit n'est plus bénin) ; au-delà de sa durée + 5 min, ou du plafond : annulée ; Ctrl-C : annulée aussi |
| 6. Après | les sondes à nouveau, Heartbeat **postérieur à la fin** de la panne, 10 min au plus ; un effet lu dans la télémétrie, pas encore vu, cherché encore entre son début et sa fin (l'ingestion a du retard) ; si le moteur n'a pas ramené la VM : le retour déclaré (`start_vm`, journalisé), puis les sondes encore ; enfin, la watch de Glorfindel relue (`checks.watch_after`, G1) | le retour n'est « vérifié » que par une sonde, jamais sur la parole du moteur ; un effet jamais vu fait échouer le run (`fault_effective`) ; une watch disparue aussi : la réaction de Glorfindel n'est pas connue |
| 7. Enregistrer | `runs/gothmog/<run_id>.json` comme Annatar, avec les valeurs des sondes avant et après (`metrics.before`, `metrics.after`, par VM) ; fenêtre fermée, puis, avec le canal, le rapport publié vers Imladris, anciennement H0 (#193) ; signaux dans `runs/gothmog/` | — |

**Les sondes d'état normal** ([`probes.py`](probes.py)) : la VM en marche (`PowerState/running`),
son agent `Ready` (le système répond), son Heartbeat dans Log Analytics de moins de 10 minutes.
Le Heartbeat compte à part : Chaos Studio ignore les erreurs d'extension au redémarrage, une
panne peut « réussir » avec l'agent de supervision arrêté — et Glorfindel aveugle sur cette VM.
Tout passe par l'API de contrôle d'Azure (ARM), la seule sortie qu'Orodruin laisse ouverte —
Log Analytics compris, par sa requête via ARM.

**Les signaux ne vont pas où la watch décide.** La watch de Glorfindel envoie à son graphe de
décision tout événement de `runs/annatar/*_signals.jsonl` sauf `attack_started` : un `fault_started` là
lancerait un cycle de décision sur la déclaration elle-même. Les signaux de Gothmog vont dans
`runs/gothmog/<run_id>_signals.jsonl` ; Glorfindel apprend la panne par sa fenêtre d'exercice et
par sa propre télémétrie, comme pour une vraie panne.

### Lancer

Depuis Orodruin (contrat armé), gondolin allumée :

```bash
make gothmog-preflight      # watch, contrat, cibles, état normal, puis droits, agent, séries (G1b) — rien d'écrit
make gothmog-run            # la panne et son retour vérifié (~15 min)
make gothmog-run WITHOUT_GLORFINDEL=1   # run de développement sans watch vivante, dit au rapport
```

Sur la VM : `gothmog run vm-shutdown [--yes] [--dry-run] [--without-glorfindel]`,
`gothmog preflight vm-shutdown [--without-glorfindel]`,
`gothmog report <run_id>`. Ailleurs (un poste d'opérateur), le contrat est passif : rien ne
part. `--dry-run` n'appelle pas Azure.

### Mesuré sur le banc (19/10)

Run `gothmog-20261019T200123Z`, depuis Orodruin armé : **PASS**.

| Instant (UTC) | Ce qui s'est passé | Source |
|---|---|---|
| 20:01:34.32 | `chaos_start` écrit au journal d'audit | Orodruin, `runs/orodruin/audit.jsonl` |
| 20:01:34.77 | début de l'exécution (0,45 s après le journal) | Chaos Studio |
| 20:02:06 | gondolin vue arrêtée par Gothmog (`stopping` dès 20:01:57) | Gothmog ; relevé indépendant |
| 20:07:30 | gondolin redémarrée par le moteur | relevé indépendant |
| 20:07:31 | exécution `Success` | Chaos Studio |
| 20:09:08 | premier Heartbeat après la panne | Log Analytics |
| 20:09:44 | retour vérifié (les trois sondes), 133 s après la fin, sans repli | Gothmog |

Glorfindel (la watch hébergée) n'a rien fait sur gondolin : aucun cycle, aucune escalade ; la
fenêtre `fault` était sur le canal, lisible par son identité. Avant le run, la sonde Heartbeat
avait **échoué fermé** : `last` est un mot de KQL (erreur de syntaxe) — l'état normal n'étant
pas vérifié, rien n'aurait été injecté ; la colonne s'appelle `LastSeen`.

### Mutants

M71 (panne lancée sans état normal vérifié avant), M72 (cible de l'expérience non inscrite
acceptée), M73 (retour déclaré sans être vérifié), M74 (signaux de panne là où la watch
décide) — mesurés par `tests/unit/test_gothmog.py`.

## G1 — le bruit bénin

Des pannes sur lesquelles Glorfindel ne doit **ni isoler ni bloquer** : du bruit qu'une charge
réelle fait tous les jours. Chacune est déclarée comme celle de G0, dans `experiments/` et au
catalogue (`azure_vm.faults`), avec son expérience dans Celebrimbor
([`infra/terraform/chaos.tf`](../infra/terraform/chaos.tf), `chaos.noise_vms`).

| Panne | Moteur | Ce qu'elle fait | Son effet, lu où Glorfindel lit |
|---|---|---|---|
| [`vm-disk-write`](experiments/vm-disk-write.yaml) | agent Chaos, LinuxDiskIOPressure-1.1 (stress-ng), 10 min | des écritures soutenues, une sauvegarde : **au-dessus du seuil** de `ransomware-disk-write`, décidé avec Jonathan le 31/10 — la règle se déclenche, et Glorfindel décide sur du bénin | Perf, `Disk Write Bytes/sec`, calculé comme la règle : au pas du banc (10 s), la moyenne de deux échantillons consécutifs au-dessus de 45 MB/s (au pas grossier, un échantillon au-dessus de 25 MB/s) |
| [`vm-cpu-pressure`](experiments/vm-cpu-pressure.yaml) | agent Chaos, CPUPressure-1.0, 95 %, 10 min | une compilation, un traitement par lots | Perf, `% Processor Time` au-dessus de 80 |
| [`vm-restart`](experiments/vm-restart.yaml) | Shutdown-1.0, arrêt propre d'une minute | un redémarrage de maintenance ; au démarrage, l'agent de supervision groupe ses échantillons (#105) | la VM vue arrêtée |

`vm-shutdown` (G0) déclare désormais son effet de la même façon (la VM vue arrêtée).

**L'effet, pas la parole du moteur.** Chaque panne déclare ce qui montre qu'elle a eu lieu
(`effect.probes`, schéma E1). Une requête en lit le pic (`Peak`) entre le début et la fin de la
panne (`{start}`, `{end}`), jamais au-delà. Une écriture d'avant, ou d'après, n'est pas son effet.
Celle de `vm-disk-write` reproduit le `Rate` de la règle, son mode lu dans le pas des données,
et exige son seuil. Un test garde les deux textes égaux : un échantillon à 30 MB/s au pas de
10 s n'est pas un effet, car la règle ne l'aurait pas vu.
Si le bruit n'atteint jamais la télémétrie de Glorfindel, le run échoue (`fault_effective` FAIL) et
ne compte pas dans le taux : un bruit que Glorfindel n'a pas vu ne prouve pas qu'il l'a ignoré.

**Le bruit est bénin : la VM sert pendant.** Les sondes marquées `during: true` (en marche, agent
prêt, Heartbeat frais) sont relues à chaque tour. Si l'une dit le contraire, l'expérience est
annulée tout de suite. Une sonde illisible (une API qui répond 429) passe deux tours ; au
troisième d'affilée, l'expérience est annulée aussi. Dans les deux cas, le run échoue
(`steady_state_during` FAIL, `metrics.steady_state_lost`), et le retour est vérifié comme
d'habitude.

**Le taux.** Une panne est prise pour une attaque quand Glorfindel a recommandé ou exécuté une
isolation ou un blocage de sa cible pendant la panne. Le taux compte par run, sur les pannes
mesurées, et toutes les pannes de Gothmog comptent, pas seulement celles d'une campagne.
Une panne n'est mesurée que si la watch de Glorfindel vivait avant la panne (V1) et après
(Gothmog la relit, `checks.watch_after`), et si ses décisions ont été lues sur l'hôte. Une
décision faite après le début de la panne suivante sur la même VM est à la suivante. Si elle
tombe aussi dans la fenêtre de la première, la première n'est pas mesurée. Définitions et calcul : [`docs/analysis.md`](../docs/analysis.md),
« Le taux des pannes prises pour une attaque ». Le taux se lit **sur l'hôte de la watch** (Imladris) :
`make imladris-fault-rate`. Sur Orodruin, chaque panne est « non mesurée » : les décisions
n'y sont pas.

**Mutants** : M2400–M2409 et M2424 (`tests/unit/test_gothmog_noise.py`), M2410–M2423 sauf
M2419 (`tests/unit/test_fault_rate.py`).

Le plan des deux cas, contre de faux providers :
- **le bruit éteint** (`chaos_noise_vms = []`) : le plan ne planifie rien de G1, ni l'identité d'une
  VM (chacune en identité système seule), ni G0, qui reste intact. Sur le banc, où G1 est appliqué,
  `[]` le détruirait ;
- **la config du dépôt** (`noise_vms: [gondolin]`, G1c) : le bruit ne touche que gondolin, et
  aucune ressource de G1 ne vise une autre VM.

Les deux cas sont dans `infra/terraform/tests/chaos_noise.tftest.hcl`. On les lance à la main,
comme le test d'ID1 (`terraform -chdir=infra/terraform test`), et la CI les lance à chaque PR
(job `terraform-test`, CI4).

**Un second moyen d'allumer le bruit, réservé aux tests.** Le cas « gondolin » passe par la
variable `chaos_noise_vms` (`variables.tf`), car un test ne peut pas remplacer une valeur lue dans
`config.yaml`. Elle est `null` par défaut, et c'est alors `chaos.noise_vms` du `config.yaml` qui
décide. Ne la pose ni dans `terraform.tfvars` ni par `TF_VAR_chaos_noise_vms` : le bruit s'allume
dans `config.yaml`, plan montré, par Jonathan seul.

### Le préflight dit si la panne peut tourner, et être vue (G1b)

Après l'état normal, `gothmog preflight <panne>` lit trois choses de plus, sans rien écrire. Chacune
a sa ligne, ✓ ou ✗, et un ✗ refuse : « not ready ».

| Lu | Où | Ce qu'un manque éviterait |
|---|---|---|
| Les droits d'Orodruin de démarrer **et** d'annuler cette expérience | `Microsoft.Authorization/permissions`, à la portée de l'expérience | un démarrage qui répond 403, ou une panne lancée qu'on ne peut plus annuler. Le contrat arme sur l'expérience de G0 seule : une expérience appliquée après le dernier `make orodruin-lock YES=1` n'a pas ses droits |
| L'agent Chaos installé, sur chaque VM que l'expérience atteint par lui | l'`instanceView` de la VM : l'extension `ChaosLinuxAgent` en `ProvisioningState/succeeded` | une panne d'agent qui ne démarre pas |
| Chaque série que lit l'effet, collectée sur chaque cible | la requête de l'effet elle-même, sur les 30 dernières minutes : un nombre, quelle que soit sa valeur | dix minutes de bruit jamais vues, parce qu'un compteur est collecté sous un autre nom (`fault_effective` FAIL) |

Une lecture qui échoue n'est jamais « prêt ». Le seuil de l'effet n'est pas demandé : au repos, le
bruit n'est pas encore là, et c'est le run qui le demande. Un arrêt (`vm-shutdown`, `vm-restart`)
cible la VM elle-même et lit son effet dans ARM : seuls ses droits sont demandés. L'agent est lu
sur les VM que l'expérience validée par le gate atteint par lui, sans relire l'expérience. Les
étapes du run ne changent pas ; son rapport nomme aussi ces VM (`metrics.experiment.agents`).

**Ce que le préflight ne lit pas.** Que stress-ng soit présent sur la VM, et que l'agent joigne
Chaos Studio : rien dans le plan de contrôle ne le montre. L'effet de la panne, lu pendant le run,
le dit : s'il manque, le run échoue fermé.

**Une hypothèse, à mesurer à la première séance.** La lecture des droits se fait à la portée d'une
expérience. On suppose qu'elle répond à l'identité d'Orodruin comme à la portée du groupe, où le
contrat la fait déjà. Si elle répond 403, le préflight dit « unreadable » et refuse : le signaler,
ne pas le contourner.

**Mutants** : M6586–M6605 et M6616 (`tests/unit/test_gothmog_readiness.py`). Pour l'apply ciblé du
bruit et son garde d'abonnement (G1c) : M6768–M6779, M6831–M6832, M6849–M6850
(`tests/unit/test_gothmog_noise.py`, `tests/unit/test_bench_perf_counters.py`).

### Mesuré sur le banc (20/11)

Depuis Orodruin armé, gondolin en `human_only`. L'image d'Orodruin est `bdd03240`, une image de
développement : son `gothmog/` est identique à la v0.6.2. Glorfindel est mesuré sur Imladris en
v0.6.3, avec des règles identiques entre les deux versions.

| Panne | Run | Résultat | Glorfindel |
|---|---|---|---|
| `vm-disk-write` | `gothmog-20261120T171114Z` | PASS : l'effet vu, la VM sert pendant | **prise pour une attaque** : `ransomware-disk-write` détecte à 17:14, sur environ 74 MB/s soutenus, et `isolate_vm` est recommandé à 80 %, retenu par `human_only`, jamais exécuté (deux cartes) |
| `vm-restart` | `gothmog-20261120T172413Z` | PASS | aucune carte à son nom |
| `vm-shutdown` | `gothmog-20261120T172851Z` | PASS : la preuve de G0, rafraîchie | aucune carte à son nom |
| `vm-cpu-pressure` | — | refusée au préflight : `cpu-load-seen`, `nothing in the last 30 min under these names` | non jouée : la DCR déclarait un compteur CPU que l'agent Linux ne collecte pas (DCR1, #985, pas encore appliquée) |

**Le constat.** Des écritures bénignes soutenues, celles d'une sauvegarde, suffisent à déclencher
`ransomware-disk-write`, et le modèle recommande d'isoler avec une confiance au-dessus de la porte.
Seul le mode `human_only` a retenu l'action. C'est la classe des isolations à tort de bree.
`vm-disk-write` la reproduit désormais à la demande.

**Le taux n'est pas encore publié.** `make imladris-fault-rate` comptait `vm-shutdown` prise
(1 sur 1), et laissait `vm-disk-write` et `vm-restart` non mesurées. Les runs étaient trop
rapprochés (17:11, 17:24, 17:28) : la seconde carte de `vm-disk-write` est tombée après le début du
shutdown, dans la fenêtre de `vm-disk-write`, qui court jusqu'à sa fin plus 15 minutes de grâce
(`GRACE_AFTER_S`, `eregion_core/exercise.py`). L'outil a fermé : rien n'a été compté comme
« Glorfindel n'a rien fait ». La lecture des cartes donne le résultat ci-dessus. Le taux, lui, doit
sortir de l'outil, sur des runs espacés d'au moins 16 minutes après le retour du précédent. Il
viendra de la séance courte, avec `vm-cpu-pressure` une fois sa DCR appliquée.

### Reste, sur le banc, avec Jonathan

`vm-disk-write` et `vm-restart` sont `implemented` depuis le 20/11 ; `vm-cpu-pressure` reste
`planned` (Dagorlad la montre sans poignée) jusqu'à son premier run. `chaos.noise_vms: [gondolin]`
est déclaré dans `config.yaml` (G1c). La séance, dans l'ordre. Chaque geste est celui de Jonathan.

0. **Le bon abonnement, d'abord.** Plusieurs abonnements vivent sur le poste (le banc, Stratus,
   Imladris), et `az account set` tient d'une séance à l'autre. Le 20/11, un apply lancé en
   terraform direct est parti sur l'abonnement de Stratus, et `celebrimbor-start` n'a trouvé
   aucune VM. Dans le shell de la séance :

   ```bash
   source .envrc
   export ARM_SUBSCRIPTION_ID=$AZURE_SUBSCRIPTION_ID
   az account set --subscription "$AZURE_SUBSCRIPTION_ID"
   [ "$(az account show --query id -o tsv | tr A-Z a-z)" = "$(printf '%s' "$AZURE_SUBSCRIPTION_ID" | tr A-Z a-z)" ] && echo BANC || echo STOP
   ```

   `BANC`, ou rien d'autre. Puis gondolin allumée (`make celebrimbor-start VM=gondolin`), et
   vérifiée : l'extension de l'agent ne s'installe pas sur une VM arrêtée (409).

   ```bash
   az vm get-instance-view -g rg-celebrimbor -n vm-celebrimbor-gondolin --query "instanceView.statuses[?starts_with(code,'PowerState/')].code" -o tsv
   ```

   `PowerState/running`. Puis Orodruin : `make orodruin-start`, `make orodruin-check` (`armed`).
   Tant que les garants de Stratus jugent tout armement (un lot à venir les limite à celui de
   Stratus), une ligne `EREGION_STRATUS_SUBSCRIPTION` dans l'`orodruin.env` d'Orodruin rend Gothmog
   passif : la mettre en commentaire le temps de la séance (`make orodruin-ssh`, puis
   `sed -i 's/^EREGION_STRATUS_SUBSCRIPTION=/#&/' orodruin.env`), et la remettre à la fin.
1. **Appliquer le bruit, à lui seul.** Jamais `make celebrimbor-up` complet : son plan retirerait
   les règles de Glorfindel du NSG partagé (le plan du 12/11). Jamais terraform à la main : les
   deux cibles vérifient l'abonnement avant de le lancer (`CELEBRIMBOR_SUB_GUARD`).

   ```bash
   make celebrimbor-noise-plan
   make celebrimbor-noise-up YES=1
   ```

   Le plan, lu avant l'apply : 11 à créer (l'identité de l'agent, la cible Microsoft-Agent — azapi,
   au verrou du module depuis CI4 —, l'extension, deux capacités, trois expériences et leurs trois
   rôles), 1 à changer (l'identité de gondolin, sur place), 0 à détruire. Toute autre ligne :
   s'arrêter. Puis les droits d'Orodruin, expérience par expérience, à son propre apply
   (`infra/orodruin/main.tf`, `experiment_injector`) : `make orodruin-plan`, lu (les droits sur les
   trois nouvelles expériences, rien d'autre), puis `make orodruin-lock YES=1`.
2. **Préflighter chaque panne**, gondolin en `human_only` (console) :

   ```bash
   make gothmog-preflight FAULT=vm-disk-write
   make gothmog-preflight FAULT=vm-cpu-pressure
   make gothmog-preflight FAULT=vm-restart
   make gothmog-preflight FAULT=vm-shutdown
   ```

   Un ✗, et ce qu'il demande :

   | La ligne dit | À faire |
   |---|---|
   | `start` ou `cancel` : `not held` | `make orodruin-lock YES=1`, puis le préflight à nouveau |
   | `chaos agent` : `absent`, ou un autre état que `ProvisioningState/succeeded` | l'extension : relire le plan et son état dans le portail. Ne pas lancer |
   | une série : `nothing in the last 30 min under these names`, ou `no row` | le compteur n'est pas collecté sous ce nom (pour le CPU : l'objet sous l'agent Azure Monitor). Relever le nom réel dans Log Analytics : `Perf \| where _ResourceId =~ '<id de gondolin>' \| distinct ObjectName, CounterName, InstanceName`. L'expérience se corrige par une PR, puis le préflight à nouveau |
   | `unreadable` | relancer une fois ; si ça tient, le signaler |

3. **Lancer, une panne à la fois**, chacune jusqu'à son rapport (`make gothmog-run FAULT=…`, environ
   15 minutes chacune) : `vm-disk-write`, `vm-cpu-pressure`, `vm-restart`, puis `vm-shutdown`.
   **Au moins 16 minutes après le retour du run précédent** : la fenêtre d'une panne court jusqu'à
   sa fin plus 15 minutes de grâce. Une carte qui tombe après le début de la suivante rend la
   première non mesurée (le 20/11). Avant `vm-shutdown`, rejouer son préflight : le Heartbeat doit
   être revenu après le redémarrage.
4. **Le taux.** `make imladris-fault-rate` (sur Imladris). Le taux mesuré va ici ; une panne jouée
   pour la première fois passe `implemented`, par une PR de la session Gothmog.

## G2 — les pannes des dépendances de Glorfindel

**Côté Glorfindel, fait le 21/10 (code)** : chacune des quatre dépendances — le modèle, l'API
du cloud, la télémétrie, la configuration — échoue fermé, prouvé par un cycle complet du graphe
et un mutant par panne (M151–M158 et M170–M178, `tests/unit/test_dependency_failures.py`). Détail :
[`docs/glorfindel.md`](../docs/glorfindel.md), « Pannes des dépendances ».

**Reste, sur le banc, avec Jonathan** : injecter ces pannes pour de vrai, depuis Orodruin, sur
un Glorfindel du banc, et constater les cartes attendues. Proposition, **non mesurée** (le moteur
ne sait aujourd'hui que l'arrêt de VM, `Shutdown-1.0`) :

| Panne | Injection envisagée | Attendu de Glorfindel |
|---|---|---|
| Modèle | règle de sortie refusée vers le fournisseur du modèle, sur le NSG de la VM de Glorfindel (faute Chaos Studio « NSG security rule ») | `cycle_failed` sur chaque détection, au plus 3 × 120 s après |
| API du cloud | règle de sortie refusée vers l'étiquette de service `AzureResourceManager` | VM jamais contrôlée tenue en `human_only` ; action tentée → `action_failed` |
| Télémétrie | règle de sortie refusée vers `AzureMonitor` | RulePoller en `last_error`, nœud DETECT rouge ; aucune action disruptive sur une enquête incomplète |
| Configuration | pas une faute de Chaos Studio (un fichier local) : reste un test | — |

À décider avant : la cible (Imladris n'est pas inscrite, et un Glorfindel d'exercice sur le banc
serait plus sûr qu'une coupure de celui qui observe bree) ; l'inscription des NSG auprès de
Chaos Studio et de l'inscription O0 (`kind="fault"`) ; si la faute NSG accepte bien une étiquette
de service comme destination (à mesurer, pas à supposer).

## Règles

Aucune panne en zone `production` (inscription, O0) ; exécution depuis Orodruin ; une panne est
déclarée, réversible, et son retour est vérifié ; chaque lot ajoute ses mutants au harnais.

Feuille de route : [`ROADMAP.md`](../ROADMAP.md), « Vers la 1.0 ». Session : [`CLAUDE_GOTHMOG.md`](../CLAUDE_GOTHMOG.md).
