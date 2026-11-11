# Piloter le banc depuis le téléphone (MOB1, MOB2)

[← le banc](banc.md) · le rejeu du rançongiciel : [banc-t1486.md](../banc-t1486.md) · le modèle de menace : [frontière 9](../design/modele-de-menace.md#9-le-téléphone-et-son-chemin-vers-le-poste)

**Le principe.** C'est toujours l'opérateur qui tape la commande **sur son poste**. Seul le chemin
entre le téléphone et le poste change :

```
téléphone ──(Tailscale : téléphone → poste:22 seul)──► poste (WSL) : sshd, à clé seule
   │                                                      ├─ make bench-run / bench-restore, tapés dans le terminal
   └─ son propre tunnel SSH (-L 7007:127.0.0.1:7007) ───► └─ 127.0.0.1:7007 ── le tunnel du poste ──► Imladris : la console
                                                              (make mobile-tunnel-on : armé à la demande, 12 h au plus)
```

- Orodruin continue à n'écouter que le SSH du poste (DRL1). **Rien ne change sur Imladris** (H0) : la
  console y répond comme aujourd'hui, sous `localhost`, par le tunnel du poste — armé par un geste,
  pour 12 h au plus (MOB2, étape 5).
- **Deux barrières indépendantes**, pour le terminal comme pour la console : le réseau privé (le
  compte Tailscale avec MFA, une règle d'accès qui n'ouvre que téléphone → poste:22), puis le serveur
  SSH du poste, **à clé seule**, la clé gardée dans la puce sécurisée du téléphone et débloquée par
  biométrie. L'une tombée, l'autre tient. Pour la console, le jeton de la console vient ensuite.
- Le lot fournit les commandes et les modèles (`infra/poste/`) ; **Jonathan les applique**, aucune
  session ne le fait. Rien de ce guide n'a encore été joué sur le poste : chaque étape qui n'est ni
  lue dans le code ni testée sur des faux est marquée **non vérifié**.

## 0. Le Windows de l'hôte ne se met pas en veille

Un poste en veille ne répond plus, ni au téléphone ni à Orodruin, et une commande en cours (un
restore de 30 min) s'arrête avec lui. Sur Windows, branché sur secteur :

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
```

L'écran peut s'éteindre, pas la machine. WSL doit aussi rester démarré : garder un onglet WSL
ouvert dans Windows Terminal. **Non vérifié** : que les seuls services de systemd gardent la VM de
WSL en vie, sans terminal ouvert.

## 1. Tailscale dans WSL (systemd)

Dans WSL, systemd allumé (`/etc/wsl.conf`, puis `wsl --shutdown` depuis Windows) :

```ini
[boot]
systemd=true
```

Puis Tailscale, depuis son dépôt (sa documentation, « Install Tailscale on Linux »), et :

```zsh
sudo systemctl enable --now tailscaled
sudo tailscale up                     # le compte de l'opérateur, avec MFA
sudo tailscale set --ssh=false        # Tailscale SSH fermé : le serveur SSH du poste, à clé, est le seul
tailscale ip -4                       # l'adresse privée du poste : une adresse de 100.64.0.0/10
```

Sur le téléphone : l'application Tailscale, sous le même compte. Garder l'expiration des clés de
chaque appareil (le défaut) : un appareil se ré-authentifie, il ne reste pas ouvert pour toujours.

**La règle d'accès.** Sans règle, Tailscale laisse chaque appareil joindre chaque autre. Le modèle
`infra/poste/tailscale-acl.hujson` la remplace, dans la console d'administration de Tailscale
(*Access controls*), les deux adresses remplacées par celles des appareils : **téléphone →
poste:22, et rien d'autre**, aucune règle `ssh` de Tailscale. La console passe par ce même port 22,
dans le tunnel du téléphone (étape 5).

**Non vérifié** : la règle se lit dans la console de Tailscale, pas sur le poste ; `make
mobile-check` ne la voit pas.

## 2. Le serveur SSH du poste, durci

```zsh
sudo apt install openssh-server tmux
sudo install -m 644 infra/poste/sshd_config.d/00-eregion.conf /etc/ssh/sshd_config.d/00-eregion.conf
sudoedit /etc/ssh/sshd_config.d/00-eregion.conf      # ListenAddress <tailscale ip -4>, AllowUsers <toi>
sudo install -D -m 644 infra/poste/ssh.service.d/eregion.conf /etc/systemd/system/ssh.service.d/eregion.conf
sudo systemctl disable --now ssh.socket              # Ubuntu ≥ 22.10 : sshd écoute lui-même, pas le socket
sudo systemctl daemon-reload && sudo sshd -t && sudo systemctl enable --now ssh.service
```

- **Le fragment** (`infra/poste/sshd_config.d/00-eregion.conf`) :
  - l'adresse privée seule ;
  - aucun mot de passe, aucun clavier interactif, la clé seule (`AuthenticationMethods publickey`),
    lue dans le seul `~/.ssh/authorized_keys` (`AuthorizedKeysFile .ssh/authorized_keys`), sans
    commande qui fournisse des clés (`AuthorizedKeysCommand none`) ni autorité de certificats
    (`TrustedUserCAKeys none`) ; pas de root ;
  - **un seul tunnel** : `AllowTcpForwarding local` et `PermitOpen 127.0.0.1:7007` — le téléphone
    peut ouvrir une redirection locale vers la console, et vers rien d'autre ; aucune redirection
    distante, aucun port ouvert sur le poste (`GatewayPorts no`), ni socket, ni agent, ni X11.
    C'est une borne de **la seule connexion SSH** : avec un shell, le téléphone relaie comme
    l'opérateur (`ssh poste nc …`). Ce cas est celui d'un téléphone déverrouillé, qui est
    l'opérateur, ou perdu ou volé (« Ce qui reste ouvert », étape 7).

  Il s'appelle `00-` : `sshd` garde la **première** valeur qu'il lit, et un `50-cloud-init.conf` qui
  dirait `PasswordAuthentication yes` l'emporterait sur un `eregion.conf`.
- **L'ordre de systemd** (`infra/poste/ssh.service.d/eregion.conf`) : `sshd` attend que Tailscale ait
  son adresse avant d'écouter dessus, une minute au plus, et repart après un échec. **Non vérifié** sur
  le poste.
- **Le contrôle**, en lecture seule, chaque fois que la configuration change :

```zsh
sudo -v && make mobile-check
```

`make mobile-check` (`scripts/mobile.py`) dit une ligne ✓/⚠/✗ par point, sans afficher aucune
adresse, et sort en 1 sur un ✗ :
- le réseau privé : une adresse du tailnet, et Tailscale SSH fermé (illisible, c'est un ✗) ;
- le serveur SSH (`sshd -T`, ce qu'il applique vraiment) : `PasswordAuthentication no`,
  `KbdInteractiveAuthentication no`, `PermitEmptyPasswords no`, `HostbasedAuthentication no`,
  `GSSAPIAuthentication no`, `PubkeyAuthentication yes`, `AuthenticationMethods` à clé seule,
  `AuthorizedKeysFile .ssh/authorized_keys` seul, `AuthorizedKeysCommand none`, `TrustedUserCAKeys
  none` ; `AllowTcpForwarding local` (`yes`, `all` ou `remote` : ✗ ; `no` : ⚠, le tunnel du
  téléphone ne s'ouvre pas), `PermitOpen 127.0.0.1:7007` seul, `GatewayPorts no`,
  `AllowStreamLocalForwarding no`, `AllowAgentForwarding no`, `X11Forwarding no` ; `PermitRootLogin
  no` (un ⚠ sinon) ;
- les écoutes (`ss -Hltn`) : le port du serveur SSH sur l'adresse privée **seule** — toutes les
  interfaces (`0.0.0.0`, `[::]`, `*`), la boucle locale ou une autre adresse sont un ✗ ; le port de la
  console en `127.0.0.1` seul (et `::1`, l'autre boucle que `ssh` lie) — sur l'adresse privée, toutes
  les interfaces ou une autre adresse, c'est un ✗ ;
- les clés admises (`~/.ssh/authorized_keys`) : combien, de quels types — jamais une clé affichée.
  Leurs options (`from=`, `permitopen=`, étape 3) **ne sont pas lues** : c'est le guide qui les pose.

Il lit la configuration globale : un bloc `Match` peut la changer pour une connexion. Le fragment
n'en a pas ; n'en ajouter aucun.

## 3. La clé, dans la puce du téléphone

Dans **Blink Shell** (iOS) ou **Termius** (iOS, Android) : une clé créée **dans la puce sécurisée**
(Secure Enclave sur iOS, le Keystore matériel sur Android), non exportable, débloquée par biométrie.
Le type est ECDSA P-256 : c'est celui que la puce sait garder. **Non vérifié** : le nom exact du menu
dans chaque application.

Sa clé **publique** va sur le poste, une ligne par appareil, avec le nom de l'appareil en
commentaire et des options qui la bornent au tailnet et au seul tunnel de la console :

```
from="100.64.0.0/10",permitopen="127.0.0.1:7007",no-agent-forwarding,no-X11-forwarding ecdsa-sha2-nistp256 AAAA… telephone-de-l-operateur
```

`chmod 600 ~/.ssh/authorized_keys`. La clé privée ne quitte jamais le téléphone : elle n'est ni
copiée, ni sauvegardée, ni synchronisée.

## 4. `tmux` : le terminal qu'on retrouve, et son prix

Le téléphone perd la connexion (un tunnel, un écran qui se verrouille). Une commande lancée dans
`tmux` continue sur le poste, et on la retrouve :

```zsh
tmux new -A -s banc          # crée la session, ou la reprend
# Ctrl+b d : la quitter sans rien arrêter
```

Lancer `make bench-run` et `make bench-restore` dans `tmux`, pour qu'une coupure du téléphone ne les
arrête pas.

**Le prix, à dire franchement.** Une session `tmux` qui dure est un terminal que **tout processus du
même utilisateur peut piloter** (`tmux send-keys -t banc …`), une session d'agent comprise. Elle
tape alors dans un vrai terminal, hors de son worktree, sans `EREGION_AGENT_SESSION` : le garde de
session, le nom tapé et le contrôle du terminal ne voient que l'opérateur. Avec la paire de la
console chargée dans cette session, elle pourrait lancer un restore. D'où :
- **ne pas garder `.envrc` chargé dans une session qui dure** : le sourcer dans la seule commande,
  `zsh -c 'source .envrc && make bench-restore TARGET=… RUN=…'`, ou quitter la session (`exit`)
  après le geste ;
- fermer la session `tmux` à la fin du banc (`tmux kill-session -t banc`).

`HOST_SSH_FINGERPRINT` et `ORO_SSH_FINGERPRINT` doivent être posées pour la commande (dans
`.envrc`).

## 5. La console d'Imladris, sur le téléphone (MOB2)

Par le poste, **rien ne change sur Imladris** : téléphone → réseau privé → son propre tunnel SSH vers
le `127.0.0.1:7007` du poste → le tunnel du poste vers Imladris. Ce dernier tunnel, le poste le tient
par un service systemd de l'utilisateur, **armé à la demande et borné à 12 h** (décision de Jonathan,
11/11) : on n'a plus besoin d'un terminal du bureau ouvert sur `make glorfindel-host-tunnel`, et la
console n'est jamais joignable sur le poste sans un geste.

### 5a. Poser le tunnel, une fois

Sur le poste, `HOST_SSH_FINGERPRINT` posée (sans elle, rien n'est écrit : le tunnel n'accepte jamais
une clé au premier contact) :

```zsh
make mobile-tunnel-install DRY_RUN=1     # l'unité remplie, affichée ; rien n'est écrit
make mobile-tunnel-install               # HOST_SSH_KEY=~/.ssh/… si ton agent ne propose pas la clé d'Imladris
```

Elle écrit `~/.config/systemd/user/eregion-console-tunnel.service`, à partir du modèle
`infra/poste/eregion-console-tunnel.service`, puis `systemctl --user daemon-reload` — **sans
l'activer ni la lancer** :
- **jamais au boot** : l'unité n'a pas de section `[Install]`, `systemctl enable` n'a rien à faire ;
- `ssh -N -L 127.0.0.1:7007:127.0.0.1:7007` vers Imladris : le port lié à `127.0.0.1` **seul**,
  jamais `0.0.0.0` ni l'adresse Tailscale. C'est le téléphone qui ouvre son tunnel jusqu'à ce
  `127.0.0.1` ;
- **la clé d'hôte épinglée** : `infra/glorfindel-host/known_host.sh` la vérifie par son empreinte
  (`HOST_SSH_FINGERPRINT`, « required »), puis elle est copiée seule dans un known_hosts à elle
  (`~/.eregion/console-tunnel/known_hosts`) ; l'unité nomme ce fichier et l'empreinte
  (`X-Eregion-HostKey`), avec `StrictHostKeyChecking=yes`, `GlobalKnownHostsFile=/dev/null`,
  `UpdateHostKeys=no` — jamais `StrictHostKeyChecking=no` ;
- `-F none` (aucun `~/.ssh/config` lu), `BatchMode=yes` (rien n'est demandé : la clé doit s'ouvrir
  sans phrase de passe, ou par un agent que le service voit — **non vérifié** sur le poste),
  `ExitOnForwardFailure=yes` (le port pris, ssh sort), `ServerAliveInterval=30` et
  `ServerAliveCountMax=3` (une coupure vue en 90 s) ;
- `Restart=on-failure`, `RestartSec=15` : il repart après une coupure, jusqu'à la fin de sa fenêtre.

Elle refuse dans une session d'agent, comme toutes les cibles de cette étape sauf `make
mobile-check`. `make mobile-tunnel-remove` (`DRY_RUN=1` : ce qu'il retirerait) l'arrête et retire
l'unité, son known_hosts et sa date limite.

**L'adresse d'Imladris** est celle que donne Terraform (`terraform output public_ip`) au moment de
l'installation. Imladris redéployé sous une nouvelle adresse : ssh ne la joint plus, ou joint une
autre machine, dont la clé refuse ; le service échoue et repart toutes les 15 s sans rien lier,
jusqu'à la fin de sa fenêtre. `make mobile-check` le dit (✗), et `make mobile-tunnel-on` refuse
d'armer une unité dont l'adresse n'est plus celle de Terraform : `make mobile-tunnel-install` la
réécrit. Une VM reconstruite (une nouvelle clé d'hôte) : la nouvelle empreinte dans
`HOST_SSH_FINGERPRINT`, `~/.eregion/h0_known_hosts` retiré, puis `make mobile-tunnel-install`.

### 5b. L'armer, 12 h au plus

```zsh
make mobile-tunnel-on      # du poste, ou du téléphone dans tmux (étape 4)
make mobile-check          # « armé depuis …, expire à … (dans …) », 127.0.0.1:7007 seul
make mobile-tunnel-off     # avant la fin, dès qu'on n'en a plus besoin
```

**Comment les 12 h tiennent** — trois bornes, chacune suffisante pour qu'aucune fenêtre ne dure
sans fin :
1. `make mobile-tunnel-on` écrit la date limite (maintenant + 12 h) dans
   `~/.eregion/console-tunnel/deadline`, puis pose un minuteur de systemd,
   `eregion-console-tunnel-expiry.timer` (`systemd-run --user --on-active=43200s`), qui arrête
   l'unité à cette heure ; le minuteur ne se pose pas, rien n'est armé ;
2. l'unité lit la date limite à chaque départ (`ExecCondition`) : passée, ou absente, elle ne
   démarre pas, et `Restart=` ne la relance pas (une condition fausse n'est pas un échec) ; un
   `systemctl --user start` à la main, sans `make mobile-tunnel-on`, ne fait rien ;
3. `RuntimeMaxSec=12h` arrête toute exécution qui durerait plus, le minuteur perdu.

Sans session de l'utilisateur (sans *linger*), systemd de l'utilisateur s'arrête avec la dernière
session, et le tunnel avec lui : la fenêtre est alors plus courte, jamais plus longue. **Non
vérifié** sur le poste : `systemctl --user` depuis la session SSH du téléphone (il demande le bus de
l'utilisateur, que `pam_systemd` ouvre d'ordinaire), et `systemd-analyze --user verify` sur l'unité
remplie.

`make mobile-check` lit le tunnel en plus du reste :
- l'unité est celle du modèle : pas de `[Install]`, ni de lien dans un `*.wants/` (elle démarrerait
  au boot) ; `RuntimeMaxSec` entre 1 s et 12 h et la date limite lue (sinon : « sans limite de
  durée ») ; une redirection, `127.0.0.1:7007` seul ; la clé épinglée (le known_hosts ne tient que
  des clés de l'empreinte que l'unité nomme) ; `ExitOnForwardFailure`, `ServerAlive`, `Restart` ;
  l'adresse d'Imladris celle de Terraform (illisible ici : un ⚠). Chaque écart est un ✗ ;
- puis `systemctl --user show` : arrêté, **ℹ non armé** (pas un ✗) ; en échec ou qui redémarre, un ✗ ;
  armé : depuis quand, jusqu'à quand, le minuteur de fin vivant, et `ss -Hltnp` : son processus
  n'écoute qu'en `127.0.0.1:7007`. Armé au-delà de sa date limite, ou pour plus de 12 h, un ✗.

### 5c. Sur le téléphone : le tunnel, puis Safari

1. **Le tunnel du téléphone**, ouvert par l'application avec la clé de sa puce :
   - **Blink** (iPhone, iPad) : `ssh -L 7007:127.0.0.1:7007 <utilisateur>@<adresse privée du
     poste>`, puis laisser la session ouverte ;
   - **Termius** (iPhone, iPad) : un *Port Forwarding* de type *Local*, port local 7007,
     destination `127.0.0.1:7007`, par l'hôte du poste.

   **Non vérifié** : les noms des menus, et la syntaxe exacte de chaque application.
2. **L'URL** : dans le terminal du téléphone, sur le poste, `make console-url`. Le tunnel posé, elle
   donne celle de la console d'Imladris (`http://localhost:7007/?token=…`, le jeton lu dans
   `infra/glorfindel-host/host.env`), et dit si le tunnel n'est pas armé. Elle refuse dans une
   session d'agent : le jeton n'atteint jamais une session de code (`make glorfindel-host-url` et
   `make glorfindel-host-tunnel` refusent de même).
3. **Dans Safari** : cette URL. Le `Host` reste `localhost` : la console d'Imladris répond sans rien
   ajouter à `EREGION_CONSOLE_HOSTS`. Le jeton reste exigé : l'URL le porte une fois, la console le
   retire et pose un cookie de session (12 h).

**Ce que fait iOS en arrière-plan.** Une application mise en arrière-plan est suspendue au bout de
quelques secondes ou minutes, et sa redirection avec elle : Safari ne répond plus. Il faut revenir
dans Blink ou Termius, que le tunnel du téléphone se rouvre, puis recharger la page. Le tunnel du
poste, lui, ne dépend pas du téléphone : il reste armé jusqu'à `make mobile-tunnel-off` ou la fin de
ses 12 h. **Non vérifié** : la durée exacte avant suspension, propre à chaque application.

**Le retrait.** `make mobile-tunnel-off` à la fin du geste ; `make mobile-tunnel-remove` quand on
n'en veut plus du tout. Le tunnel du poste non armé, `make glorfindel-host-tunnel` tient encore le tunnel
à la main, dans un terminal (Ctrl+C le ferme) ; il refuse tant que le tunnel du poste est armé, qui
tient déjà le port.

Un restore depuis la console reste refusé sur Imladris (elle n'a pas le rôle Restore) ; il demandera
le nom tapé et le code à usage unique avec TOT1 (#685). En attendant, le restore passe par le
terminal du poste (étape 6).

## 6. Un run depuis le téléphone

Le déroulé reste celui de [banc-t1486.md](../banc-t1486.md) ; deux commandes y remplacent des
étapes.

```zsh
make bench-run TARGET=vm-celebrimbor-gondolin SCENARIO=T1486 DRY_RUN=1    # tout, sauf l'envoi
make bench-run TARGET=vm-celebrimbor-gondolin SCENARIO=T1486              # tape vm-celebrimbor-gondolin, puis o
```

`make bench-run` (`scripts/bench_run.py`) enchaîne, chaque étape arrêtant la suivante :
1. **un terminal** : sans terminal sur l'entrée (un tube, un script), rien n'est envoyé ni lancé
   (seules les adresses de H0 et d'Orodruin ont été lues, dans l'état Terraform local) ;
2. **le préflight** (`make bench-preflight`, BNC1) : un ✗, rien n'est demandé, rien n'est lancé ;
3. **la demande** : un fil `SCENARIO` → `TARGET`, l'id de la VM lu sur Azure sous ton `az login`
   (une seule VM de ce nom), lue par le seul lecteur des demandes, comme celles de Dagorlad ;
4. **le nom de la cible, tapé**, destructif ou non, puis « [o/N] » : un autre nom, ou rien, rien
   n'est envoyé ;
5. **le lancement** : la demande et le nom tapé portés sur Orodruin par son SSH épinglé, puis lancés
   par `eregion_core.exercise_runner`, qui la rejuge (contrat, watch, inscription, zone, le nom tapé
   comparé à celui qu'il lit, son plafond), comme `make orodruin-exercise` ; le nom tapé est retiré
   d'Orodruin à la fin, quelle qu'elle soit ;
6. **le rapport** : `make bench-report` pour chaque run de la sortie (« Run: … »), puis la commande
   du restore, avec le run nommé.

`make orodruin-exercise` exige lui aussi un terminal pour les noms qu'il fait taper.

Puis le restore, depuis le poste, sous la paire de la console :

```zsh
make bench-restore TARGET=vm-celebrimbor-gondolin RUN=<run_id> DRY_RUN=1   # la paire, le moment, la VM, le nom tapé, l'essai à blanc
make bench-restore TARGET=vm-celebrimbor-gondolin RUN=<run_id>             # tape vm-celebrimbor-gondolin, puis o
```

`make bench-restore` (`scripts/bench_restore.py`) :
- exige un terminal, puis la paire de la console (`EREGION_CONSOLE_AZURE_CLIENT_ID`, `…_SECRET`) :
  vide, le restore prendrait une autre identité sans le dire (RST1) ;
- prend pour `--before` le T0 du run, son `attack_started` (la règle de SEC4c), tel que `make
  bench-report` l'a écrit dans `runs/bench/<run_id>.json` : celui de `RUN=` (la commande que donne
  `make bench-run`). Sans `RUN=`, il prend le seul rapport de `TARGET`, et l'affiche avant de faire
  taper le nom ; **s'il y en a plusieurs, il refuse et les liste** : le plus récent n'est pas le sens
  sûr. `BEFORE=<instant>` l'emporte. Sans moment, rien n'est restauré ;
- passe **toujours** `--keep-isolated` : la levée est celle de H0 (REC1, REC1b ; LEV1 changera la
  règle) ;
- fait taper le nom de la VM, lance l'essai à blanc, puis demande « [o/N] » avant le vrai restore.
  Le restore lit ses droits avant de toucher la VM (RST1). La clé matérielle du SSH tient lieu de
  second facteur, en attendant FS1g et TOT1.

Ensuite, la levée par H0 (étape 7 de banc-t1486.md), puis `make bench-report RUN=<run_id>`.

**Les deux commandes refusent dans une session d'agent** (`EREGION_AGENT_SESSION`, le worktree d'un
lot) : le garde tourne seul, avant que make ne développe aucune commande de H0 ni d'Orodruin. Elles
refusent aussi `TARGET`, `SCENARIO`, `BEFORE`, `RUN` ou `POINT_MAX_H` venus de l'environnement : sur
la ligne de commande, toujours. Ce garde-là, comme le terminal, ne tient pas contre un processus qui
tape dans une session `tmux` ouverte (étape 4). Le T1486 reste lancé de la main de l'opérateur :
aucun créneau automatique ne joue de destructif (#684).

## 7. La perte du téléphone

Les deux barrières se ferment l'une sans l'autre ; fermer les deux, puis ce que le téléphone a vu :

1. **Le réseau** : dans la console de Tailscale, retirer l'appareil (*Remove*), ou le désactiver.
   Le téléphone ne joint plus le poste.
2. **La clé** : retirer sa ligne de `~/.ssh/authorized_keys` sur le poste (son commentaire la
   nomme). Même revenu sur le réseau, il n'entre plus, ni dans le terminal, ni dans la console.
3. **Le jeton de la console**, que le navigateur du téléphone a vu : un nouveau
   `EREGION_CONSOLE_TOKEN` dans `infra/glorfindel-host/host.env`, `make glorfindel-host-push`, puis
   sur H0 `cd eregion && docker compose up -d war-room` ; le cookie de session tombe avec lui (SEC10).
   **Non vérifié** comme enchaînement.
4. `make mobile-tunnel-off` sur le poste : le tunnel vers la console d'Imladris s'arrête avant la fin
   de ses 12 h.
5. `make mobile-check` : une clé de moins, « ℹ tunnel : non armé ».

## Ce qui reste ouvert

- La règle d'accès de Tailscale ne se lit pas sur le poste ; seule sa console la montre.
- Les options de la ligne de la clé (`from=`, `permitopen=`) sont posées par ce guide, pas lues par
  `make mobile-check`. Le fragment du serveur tient la même borne (`PermitOpen`), lui lu.
- Une session `tmux` ouverte se pilote par tout processus du même utilisateur (étape 4).
- Un téléphone déverrouillé, l'application ouverte et la session reprise, est l'opérateur : la
  biométrie débloque la clé, pas chaque commande. Les gestes qui comptent font taper un nom.
- Le jeton de la console s'affiche dans le terminal du téléphone (`make console-url`), comme dans
  celui du bureau.
- **Pendant que le tunnel est armé, tout processus local du poste joint la console d'Imladris** sur
  `127.0.0.1:7007` — une session d'agent comprise. Sans le jeton, il n'obtient qu'un refus. Le
  `127.0.0.1` de WSL est aussi partagé avec Windows : un processus de Windows y joint la console, jeton
  exigé, de même. La fenêtre est bornée par le geste (`make mobile-tunnel-on`) et par les 12 h ; le
  [modèle de menace](../design/modele-de-menace.md#9-le-téléphone-et-son-chemin-vers-le-poste) dit ce
  qui garde la console pendant ce temps.
- La clé du tunnel du poste vers Imladris doit s'ouvrir sans phrase de passe, ou par un agent que
  systemd de l'utilisateur voit (**non vérifié**) : une clé sans phrase, sur le disque du poste, ouvre
  Imladris à qui la lit.
- Le Windows de l'hôte n'est pas lu par `make mobile-check` : son pare-feu, et le réseau de WSL en
  mode *mirrored*, où une écoute de WSL sur toutes les interfaces le serait aussi sur celles de
  Windows. Le contrôle des écoutes de WSL le couvre en partie.
- Le détail : le [modèle de menace, frontière 9](../design/modele-de-menace.md#9-le-téléphone-et-son-chemin-vers-le-poste).
