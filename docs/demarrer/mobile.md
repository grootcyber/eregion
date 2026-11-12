# Piloter le banc depuis le téléphone (MOB1, MOB2, MOB3)

[← le banc](banc.md) · le rejeu du rançongiciel : [banc-t1486.md](../banc-t1486.md) · le modèle de menace : [frontière 9](../design/modele-de-menace.md#9-le-téléphone-et-son-chemin-vers-le-poste)

**Le principe.** C'est toujours l'opérateur qui tape la commande **sur son poste**. Seul le chemin
entre le téléphone et le poste change :

```
téléphone ──(Tailscale : téléphone → poste:22 seul)──► poste (WSL) : sshd, à clé seule
   │                                                      ├─ make bench-run / bench-restore, tapés dans le terminal
   └─ son propre tunnel SSH (-L 7007:127.0.0.1:7007) ───► └─ 127.0.0.1:7007 ── le tunnel du poste ──► Imladris (anciennement H0) : la console
                                                              (make imladris-tunnel-on : armé à la demande, 12 h au plus)
```

- Orodruin continue à n'écouter que le SSH du poste (DRL1). **Rien ne change sur Imladris** : la
  console y répond comme aujourd'hui, sous `localhost`, par le tunnel du poste — armé par un geste,
  pour 12 h au plus (MOB2, étape 5).
- **Deux barrières indépendantes**, pour le terminal comme pour la console : le réseau privé (le
  compte Tailscale avec MFA, une règle d'accès qui n'ouvre que téléphone → poste:22), puis le serveur
  SSH du poste, **à clé seule**, la clé gardée dans la puce sécurisée du téléphone et débloquée par
  biométrie. L'une tombée, l'autre tient. Pour la console, le jeton de la console vient ensuite.
- Le lot fournit les commandes et les modèles (`infra/poste/`) ; **Jonathan les applique**, aucune
  session ne le fait. **Le banc du 11/11** (la session Tests avec Jonathan, de 12:20 à 13:50 UTC,
  sur un iPhone) a joué ce guide, puis **un redémarrage du poste, le 12/11** : ce qu'ils ont mesuré
  est marqué **mesuré le 11/11** ou **mesuré le 12/11** ; ce qu'ils n'ont pas mesuré, et chaque étape ni lue dans le code ni testée sur des faux, reste **non mesuré** ou
  **non vérifié**. Le bilan : [ce qui a été mesuré, ce qui reste à
  mesurer](#ce-qui-a-été-mesuré-ce-qui-reste-à-mesurer).

## 0. Le Windows de l'hôte ne se met pas en veille

Un poste en veille ne répond plus, ni au téléphone ni à Orodruin, et une commande en cours (un
restore de 30 min) s'arrête avec lui. Sur Windows, branché sur secteur :

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
```

L'écran peut s'éteindre, pas la machine. WSL doit aussi rester démarré : garder un onglet WSL
ouvert dans Windows Terminal. **Non mesuré** : que les seuls services de systemd gardent la VM de
WSL en vie, sans terminal ouvert — au redémarrage du 12/11, un terminal était ouvert.

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

**Un appareil, une ligne.** Le 11/11, seul l'iPhone y est (iPhone → poste:22) ; **l'iPad est
reporté**. Le modèle ne nomme qu'un téléphone : un second appareil, le jour où il vient, c'est son
adresse de plus dans `hosts` et dans le `src` de la même règle, sa propre clé à l'étape 3, et une
ligne de plus à fermer à l'étape 7. Rien ne l'ouvre d'avance.

**Non mesuré** : que la règle refuse tout le reste (un autre appareil du tailnet vers le poste,
l'iPhone vers un autre port). Elle se lit dans la console de Tailscale, pas sur le poste ; `make
imladris-tunnel-check` ne la voit pas.

## 2. Le serveur SSH du poste, durci

**L'ordre recommandé : le fragment et le drop-in d'abord, le paquet ensuite.** Le 11/11, ils ont été
posés avant `apt install openssh-server`, pour que le paquet n'ouvre jamais `ssh.socket` sur toutes
les interfaces avec le mot de passe. C'est une **hypothèse de lecture, non mesurée** : personne n'a
regardé ce qu'écoute un `openssh-server` installé seul, ni pendant combien de temps.

```zsh
sudo install -D -m 644 infra/poste/sshd_config.d/00-eregion.conf /etc/ssh/sshd_config.d/00-eregion.conf
sudoedit /etc/ssh/sshd_config.d/00-eregion.conf      # ListenAddress <tailscale ip -4>, AllowUsers <toi>
sudo install -D -m 644 infra/poste/ssh.service.d/eregion.conf /etc/systemd/system/ssh.service.d/eregion.conf
sudo apt install openssh-server tmux                 # après eux : l'ordre recommandé, une hypothèse (ci-dessus)
sudo systemctl disable --now ssh.socket              # Ubuntu ≥ 22.10 : sshd écoute lui-même, pas le socket
sudo install -d -m 755 /run/sshd                     # sans lui, sshd -t refuse avant le premier départ du service
sudo systemctl daemon-reload && sudo sshd -t && sudo systemctl enable --now ssh.service
```

- **`/run/sshd`** (mesuré le 11/11 sur Ubuntu 24.04) : `ssh.socket` coupé, `ssh.service` pas encore
  parti, `sudo sshd -t` refuse avec « Missing privilege separation directory: /run/sshd ». `/run` est
  un tmpfs, vidé à chaque démarrage, et ce répertoire, c'est le `RuntimeDirectory=sshd` du service
  qui le crée au départ du service — ni avant, ni pour `sshd -t` lancé à la main. `install -d` le crée
  vide (root, 755), comme le service le ferait. On garde le test **avant** le départ : une
  configuration refusée ne démarre rien. Au démarrage du poste, c'est le service qui recrée
  `/run/sshd`, sans aucun geste (mesuré le 12/11). Mais `RuntimeDirectory` le **retire aussi à
  l'arrêt** du service : un `sudo sshd -t` lancé le service arrêté (après un `systemctl stop ssh`,
  pour éprouver une configuration changée) en a de nouveau besoin — le même `install -d` d'abord.
  Le service en marche, le répertoire est là.

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
  son adresse avant d'écouter dessus, une minute au plus, et repart après un échec. **Mesuré le
  12/11**, après un redémarrage du poste (la session Tests, à 07:53:13 UTC) : WSL démarré à 07:39:38
  UTC (`uptime -s`), `tailscaled` actif à 07:39:58, `ssh.service` à 07:40:00, deux secondes plus
  tard, aucun redémarrage de l'un ni de l'autre. **On en déduit** que le drop-in qui attend
  l'adresse de Tailscale a tenu : `ssh` actif deux secondes après `tailscaled`, jamais relancé — son
  attente elle-même n'a pas été regardée ; `/run/sshd` recréé par le service lui-même, `ssh` actif sans aucun geste ; `make
  imladris-tunnel-check` tout ✓, avec « ℹ tunnel : non armé » : jamais au boot, comme voulu.
- **Le contrôle**, en lecture seule, chaque fois que la configuration change :

```zsh
sudo -v && make imladris-tunnel-check
```

`make imladris-tunnel-check` (`scripts/mobile.py`) dit une ligne ✓/⚠/✗ par point, sans afficher aucune
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

Dans **Termius** (iOS, Android) ou **Blink** (iOS) : une clé créée **dans la puce sécurisée**
(Secure Enclave sur iOS, le Keystore matériel sur Android), non exportable, débloquée par biométrie.
Le type est ECDSA P-256 : c'est celui que la puce sait garder.

**Termius sur iOS** (mesuré le 11/11, sur l'iPhone) :
- **la clé** : *Vaults* (la flèche `<`), puis *Keychain*, puis **+**, puis **New Face ID Key**.
  C'est une clé `ecdsa-sha2-nistp256` ; Face ID s'affiche à la connexion ;
- **sa clé publique** : *Export*, puis **Send by email** ou **Copy public key** ; puis la ligne
  ci-dessous, sur le poste ;
- **« Export to host » ne marche pas** : le poste refuse le mot de passe (étape 2). C'est voulu ;
- la redirection de la console : étape 5c.

**Blink** s'appelle **« Blink Shell, Build & Code »** sur l'App Store, et il est **payant**. Il n'a
pas été joué le 11/11 : ses menus restent **non vérifiés**, comme Termius sur Android.

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
11/11) : on n'a plus besoin d'un terminal du bureau ouvert sur `make imladris-tunnel`, et la
console n'est jamais joignable sur le poste sans un geste. Toutes les commandes de la console
d'Imladris s'appellent `make imladris-*` (IML1b) ; les anciens noms (`mobile-…`,
`glorfindel-host-…`) marchent encore, sans rien dire, jusqu'à IML2.

### 5a. Poser le tunnel, une fois

Sur le poste, `HOST_SSH_FINGERPRINT` posée (sans elle, rien n'est écrit : le tunnel n'accepte jamais
une clé au premier contact) :

```zsh
make imladris-tunnel-install DRY_RUN=1   # l'unité remplie, affichée ; rien n'est écrit
make imladris-tunnel-install             # HOST_SSH_KEY=~/.ssh/… si ton agent ne propose pas la clé d'Imladris
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
  sans phrase de passe, ou par un agent que le service voit — **mesuré le 11/11** : la clé vers
  Imladris s'ouvre sous `systemd --user`, en `BatchMode`),
  `ExitOnForwardFailure=yes` (le port pris, ssh sort), `ServerAliveInterval=30` et
  `ServerAliveCountMax=3` (une coupure vue en 90 s) ;
- `Restart=on-failure`, `RestartSec=15` : il repart après une coupure, jusqu'à la fin de sa fenêtre.

Elle refuse dans une session d'agent, comme toutes les cibles de cette étape sauf `make
imladris-tunnel-check`. `make imladris-tunnel-remove` (`DRY_RUN=1` : ce qu'il retirerait) l'arrête et retire
l'unité, son known_hosts et sa date limite.

**L'adresse d'Imladris** est celle que donne Terraform (`terraform output public_ip`) au moment de
l'installation. Imladris redéployé sous une nouvelle adresse : ssh ne la joint plus, ou joint une
autre machine, dont la clé refuse ; le service échoue et repart toutes les 15 s sans rien lier,
jusqu'à la fin de sa fenêtre. `make imladris-tunnel-check` le dit (✗), et `make imladris-tunnel-on` refuse
d'armer une unité dont l'adresse n'est plus celle de Terraform : `make imladris-tunnel-install` la
réécrit. Une VM reconstruite (une nouvelle clé d'hôte) : la nouvelle empreinte dans
`HOST_SSH_FINGERPRINT`, `~/.eregion/h0_known_hosts` retiré, puis `make imladris-tunnel-install`.

### 5b. L'armer, 12 h au plus

```zsh
make imladris-tunnel-on    # du poste, ou du téléphone dans tmux (étape 4)
make imladris-tunnel-check  # « armé depuis <jj/mm hh:mm> UTC, expire à <jj/mm hh:mm> UTC (dans …) », 127.0.0.1:7007 seul
make imladris-tunnel-off   # avant la fin, dès qu'on n'en a plus besoin
```

**Comment les 12 h tiennent.** `make imladris-tunnel-on` écrit la date limite (maintenant + 12 h)
dans `~/.eregion/console-tunnel/deadline`. **L'unité seule** s'y tient ensuite, sans le minuteur :
1. à chaque départ et à chaque relance, son `ExecCondition` lit la date limite : absente, passée, ou
   à plus de 12 h de maintenant, l'unité ne démarre pas, et `Restart=` ne la relance pas (une
   condition fausse n'est pas un échec). **Dans la fenêtre**, un `systemctl --user start` à la main la
   démarre bien, jusqu'à la date limite ; hors fenêtre, il ne fait rien ;
2. son `ExecStart` lance ssh sous `/usr/bin/timeout`, pour le temps qui reste jusqu'à la date limite
   (12 h au plus) : à l'heure, `timeout` arrête ssh (code 124), `Restart=` tente une relance, et
   l'`ExecCondition` la refuse ;
3. `RuntimeMaxSec=12h` arrête toute exécution qui durerait plus : la dernière borne.

En plus, `make imladris-tunnel-on` pose un minuteur de systemd, `eregion-console-tunnel-expiry.timer`
(`systemd-run --user --on-active=43200s`), qui arrête l'unité à l'heure : une quatrième borne, dont
les trois autres n'ont pas besoin ; le minuteur ne se pose pas, rien n'est armé.

Ce que ces bornes ne tiennent pas :
- **un processus du même utilisateur Unix** (une session d'agent comprise) peut réécrire la date
  limite et lancer le service : le garde des cibles `make` arrête l'erreur, pas une volonté ;
- **sous WSL, une veille de l'hôte met en pause les horloges monotones** (`timeout`, `RuntimeMaxSec`,
  le minuteur) : leurs 12 h comptent le temps où le poste est éveillé. L'`ExecCondition` lit
  l'horloge murale : au réveil, aucune relance ne passe la date limite.

Sans session de l'utilisateur (sans *linger*), systemd de l'utilisateur s'arrête avec la dernière
session, et le tunnel avec lui : la fenêtre est alors plus courte, jamais plus longue.

**Mesuré le 11/11** : armé, `make imladris-tunnel-check` est resté tout ✓ — armé pour 12 h, le minuteur de
fin vivant, aucun redémarrage, l'écoute en `127.0.0.1:7007` seule. **Non vérifié** sur le poste :
`systemctl --user` depuis la session SSH du téléphone (il demande le bus de l'utilisateur, que
`pam_systemd` ouvre d'ordinaire), et `systemd-analyze --user verify` sur l'unité remplie.

**Les heures sont en UTC** (MOB3) : « armé depuis …, expire à … », « armé au-delà de sa date
limite (…) » et le « armé jusqu'à … » de `make imladris-tunnel-on` disent `UTC`, quel que soit le
fuseau du poste. Le 11/11, c'était l'heure locale du poste, sans fuseau : lue sur le téléphone ou à
côté d'un journal, l'heure d'une autre zone.

`make imladris-tunnel-check` lit le tunnel en plus du reste :
- l'unité est celle du modèle : pas de `[Install]`, ni de lien dans un `*.wants/` (elle démarrerait
  au boot) ; aucune clé ni section dite deux fois ; `RuntimeMaxSec` entre 1 s et 12 h, la date limite
  lue, et ssh sous le `timeout` du modèle (sinon : « sans limite de durée », ou « pas borné ») ; une
  redirection, `127.0.0.1:7007` seul ; la clé épinglée (le known_hosts ne tient que
  des clés de l'empreinte que l'unité nomme) ; `ExitOnForwardFailure`, `ServerAlive`, `Restart` ;
  l'adresse d'Imladris celle de Terraform (illisible ici : un ⚠). Chaque écart est un ✗ ;
- puis `systemctl --user show`, ce que systemd a chargé : le fichier seul (`FragmentPath`), aucun
  drop-in (`DropInPaths`), le fichier non changé depuis sa lecture (`NeedDaemonReload=no`),
  `RuntimeMaxUSec` de 12 h au plus, aucune unité qui la tire (`WantedBy`, `RequiredBy`, `BoundBy`,
  `UpheldBy`, `TriggeredBy`, `OnFailureOf`, `OnSuccessOf`) — sinon un ✗, armé ou non ; arrêté, **ℹ non armé** (pas un ✗) ; en échec ou qui redémarre, un ✗ ;
  armé : depuis quand, jusqu'à quand, le minuteur de fin vivant, et `ss -Hltnp` : les processus de l'unité — ceux de son cgroup (`ControlGroup`), sinon `MainPID` et ses fils, car `MainPID` est celui de `timeout` et c'est son fils ssh qui écoute — n'écoutent qu'en `127.0.0.1:7007` ; le port tenu par un processus hors de l'unité est un ✗ ; ces processus ou `ss` illisibles, un ⚠ (l'écoute n'est pas vérifiée). Armé au-delà de sa date limite, ou pour plus de 12 h, un ✗.

### 5c. Sur le téléphone : le tunnel, puis Safari

1. **Le tunnel du téléphone**, ouvert par l'application avec la clé de sa puce :
   - **Termius** (mesuré le 11/11, sur l'iPhone) : *Port Forwarding*, puis **Local** — port local
     7007, destination `127.0.0.1:7007`, par l'hôte du poste et la clé Face ID de l'étape 3 ;
   - **Blink** : `ssh -L 7007:127.0.0.1:7007 <utilisateur>@<adresse privée du poste>`, puis laisser
     la session ouverte. **Non vérifié** : pas joué le 11/11.

   L'iPad est reporté (étape 1) : ces gestes sont ceux de l'iPhone.
2. **L'URL** : dans le terminal du téléphone, sur le poste, `make imladris-url`. Elle donne celle de
   la console d'Imladris (`http://localhost:7007/?token=…`, le jeton lu dans
   `infra/glorfindel-host/host.env`) ; le tunnel du poste pas armé, une ligne de plus le dit et
   renvoie à `make imladris-tunnel-on`. `make console-url` ne donne plus que la console locale du
   poste : le tunnel armé, elle renvoie à `make imladris-url` (IML1b). Elles refusent dans une
   session d'agent : le jeton n'atteint jamais une session de code (`make imladris-tunnel` refuse de
   même).
3. **Dans Safari** : cette URL. Le `Host` reste `localhost` : la console d'Imladris répond sans rien
   ajouter à `EREGION_CONSOLE_HOSTS`. Le jeton reste exigé : l'URL le porte une fois, la console le
   retire et pose un cookie de session (12 h). **Mesuré le 11/11** : la console d'Imladris s'affiche
   dans Safari, sur l'iPhone.

**Ce que fait iOS en arrière-plan.** Une application mise en arrière-plan est suspendue au bout de
quelques secondes ou minutes, et sa redirection avec elle : Safari ne répond plus. Il faut revenir
dans Blink ou Termius, que le tunnel du téléphone se rouvre, puis recharger la page. Le tunnel du
poste, lui, ne dépend pas du téléphone : il reste armé jusqu'à `make imladris-tunnel-off` ou la fin de
ses 12 h. **Mesuré le 11/11** (Termius) : la console revient après un passage en arrière-plan. **Non
vérifié** : la durée exacte avant suspension, propre à chaque application.

**Ce que `make imladris-*` affiche** (MOB3). Le 11/11, `make imladris-ssh` affichait
sa commande en clair, `ssh … glorfindel@<adresse d'Imladris>` et le chemin de la clé compris :
collée telle quelle depuis le terminal du téléphone, la sortie repartait comme commande. Chaque
recette `imladris-*` commence maintenant par `@` et n'affiche plus sa commande — `-ssh`,
`-tunnel`, `-start`, `-stop`, `-logs`, `-report`, `-cd-*`, et `-plan`, `-up`, `-down`, qui
affichaient l'adresse de l'opérateur (`operator_cidr`) ; ce qu'elles font ne change pas. Les lignes
de `known_host.sh` (« ⚠ HOST_SSH_FINGERPRINT absent : la clé d'hôte de <adresse> … », le ✓ de la
première écriture) nomment encore l'adresse ; ce ne sont pas des commandes.

**Le retrait.** `make imladris-tunnel-off` à la fin du geste ; `make imladris-tunnel-remove` quand on
n'en veut plus du tout. **Le secours** : le tunnel du poste non armé, `make imladris-tunnel` tient
le tunnel au premier plan, dans un terminal, jusqu'à Ctrl+C — un poste sans systemd de
l'utilisateur (macOS), ou un coup d'œil sans armer les 12 h ; il refuse tant que le tunnel du poste
est armé, qui tient déjà le port.

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
   (seules les adresses d'Imladris et d'Orodruin ont été lues, dans l'état Terraform local) ;
2. **le préflight** (`make bench-preflight`, BNC1) : un ✗, rien n'est demandé, rien n'est lancé ;
3. **la demande** : un fil `SCENARIO` → `TARGET`, l'id de la VM lu sur Azure sous ton `az login`
   (une seule VM de ce nom), lue par le seul lecteur des demandes, comme celles de Dagorlad ;
4. **le nom de la cible, tapé**, destructif ou non, puis « [o/N] » : un autre nom, ou rien, rien
   n'est envoyé ;
5. **le lancement** : la demande et le nom tapé portés sur Orodruin par son SSH épinglé, puis lancés
   par `eregion_core.exercise_runner`, qui la rejuge (contrat, watch, inscription, zone, le nom tapé
   comparé à celui qu'il lit, son plafond), comme `make orodruin-exercise` ; le nom tapé est retiré
   d'Orodruin à la fin, quelle qu'elle soit ;
6. **le rapport** : `make bench-report` pour chaque run de la sortie (« Run: … »), une fois le cycle
   du run écrit sur Imladris (relu toutes les 30 s, 10 min au plus, puis composé quand même, en disant ce
   qui n'est pas encore écrit ; Ctrl-C le compose tout de suite : BNC3a), puis la commande du restore,
   avec le run nommé.

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
- passe **toujours** `--keep-isolated` : la levée est celle d'Imladris (REC1, REC1b ; LEV1 changera la
  règle) ;
- fait taper le nom de la VM, lance l'essai à blanc, puis demande « [o/N] » avant le vrai restore.
  Le restore lit ses droits avant de toucher la VM (RST1). La clé matérielle du SSH tient lieu de
  second facteur, en attendant FS1g et TOT1 ;
- **le restore fini, suit la levée par Imladris**, en lecture : il relit Imladris toutes les 30 s, 30 min
  au plus, puis compose seul le rapport du run (`runs/bench/<run_id>.json`, BNC3a). Une levée retenue
  par la reprise de la watch l'arrête aussi, sauf `stopped`, que la watch relit. Seules comptent la levée
  et les cartes de ce restore-ci, après son début : celles d'un restore d'avant sur le même run restent
  dans les fichiers et n'arrêtent rien. Garder le terminal ouvert (`tmux`) jusqu'au rapport ;
  Ctrl-C le compose tout de suite (avant toute lecture d'Imladris, il n'y a rien à composer : il le dit). Avec `BEFORE=` sans `RUN=`, aucun run n'est nommé : pas de rapport.

**La sortie affiche l'id complet de la VM, l'abonnement compris, et le nom du coffre** (la ligne
`Resource :` de `glorfindel restore`, `glorfindel/cli.py:1609` ; relevé au banc le 12/11, à blanc comme
pour de vrai) : ne pas la coller telle quelle dans une issue ou un fil. La masquer demande du code.

La levée reste celle d'Imladris (étape 7 de banc-t1486.md) ; `make bench-report RUN=<run_id>` reste
possible à la main, à tout moment.

**Les deux commandes refusent dans une session d'agent** (`EREGION_AGENT_SESSION`, le worktree d'un
lot) : le garde tourne seul, avant que make ne développe aucune commande d'Imladris ni d'Orodruin. Elles
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
   `EREGION_CONSOLE_TOKEN` dans `infra/glorfindel-host/host.env`, `make imladris-push`, puis
   sur Imladris `cd eregion && docker compose up -d war-room` ; le cookie de session tombe avec lui (SEC10).
   **Non vérifié** comme enchaînement.
4. `make imladris-tunnel-off` sur le poste : le tunnel vers la console d'Imladris s'arrête avant la fin
   de ses 12 h.
5. `make imladris-tunnel-check` : une clé de moins, « ℹ tunnel : non armé ».

## Ce qui a été mesuré, ce qui reste à mesurer

Le banc du 11/11 : la session Tests avec Jonathan, de 12:20 à 13:50 UTC, un iPhone, Termius. Puis
le redémarrage du poste du 12/11 (la session Tests, à 07:53:13 UTC).

**Mesuré** :
- Termius sur iOS : la clé Face ID (`ecdsa-sha2-nistp256`, Face ID à la connexion), sa clé publique
  par *Export*, « Export to host » refusé par le poste (mot de passe fermé), la redirection par
  *Port Forwarding* → *Local* (étapes 3 et 5c) ;
- le poste installé dans l'ordre fragment, drop-in, puis paquet ; le geste `/run/sshd` avant
  `sshd -t` (étape 2, BNC1b) ;
- la clé du tunnel vers Imladris qui s'ouvre sous `systemd --user`, en `BatchMode` (étape 5a) ;
- `make imladris-tunnel-check` tout ✓, le tunnel armé : 12 h, le minuteur de fin vivant, aucun redémarrage,
  l'écoute en `127.0.0.1:7007` seule (étape 5b) ;
- la console d'Imladris dans Safari, et son retour après un passage en arrière-plan (étape 5c) ;
- la règle de Tailscale posée pour l'iPhone seul (étape 1) ;
- le 12/11, après un redémarrage du poste : `tailscaled` puis `sshd` revenus seuls, deux secondes
  l'un après l'autre, sans redémarrage ; `/run/sshd` recréé par le service ; `make imladris-tunnel-check` tout
  ✓, le tunnel non armé — jamais au boot (étapes 2 et 5b).

**Pas mesuré**, à jouer :
- WSL vivant sans terminal ouvert, par ses seuls services : au redémarrage du 12/11, un terminal
  était ouvert (étape 0) ;
- le refus, par la règle de Tailscale, de tout le reste (étape 1) ;
- la raison de l'ordre d'installation : qu'un `openssh-server` posé seul ouvre `ssh.socket` sur
  toutes les interfaces avec mot de passe reste une hypothèse de lecture (étape 2) ;
- `systemctl --user` depuis la session SSH du téléphone, `systemd-analyze --user verify` (étape 5b) ;
- Blink, Termius sur Android, l'iPad (reporté) ; la perte du téléphone, comme enchaînement (étape 7).

## Ce qui reste ouvert

- La règle d'accès de Tailscale ne se lit pas sur le poste ; seule sa console la montre.
- Les options de la ligne de la clé (`from=`, `permitopen=`) sont posées par ce guide, pas lues par
  `make imladris-tunnel-check`. Le fragment du serveur tient la même borne (`PermitOpen`), lui lu.
- Une session `tmux` ouverte se pilote par tout processus du même utilisateur (étape 4).
- Un téléphone déverrouillé, l'application ouverte et la session reprise, est l'opérateur : la
  biométrie débloque la clé, pas chaque commande. Les gestes qui comptent font taper un nom.
- Le jeton de la console s'affiche dans le terminal du téléphone (`make imladris-url`), comme dans
  celui du bureau.
- **Pendant que le tunnel est armé, tout processus local du poste joint la console d'Imladris** sur
  `127.0.0.1:7007` — une session d'agent comprise. Sans le jeton, il n'obtient qu'un refus. Le
  `127.0.0.1` de WSL est aussi partagé avec Windows : un processus de Windows y joint la console, jeton
  exigé, de même. La fenêtre est bornée par le geste (`make imladris-tunnel-on`) et par les 12 h ; le
  [modèle de menace](../design/modele-de-menace.md#9-le-téléphone-et-son-chemin-vers-le-poste) dit ce
  qui garde la console pendant ce temps.
- La clé du tunnel du poste vers Imladris doit s'ouvrir sans phrase de passe, ou par un agent que
  systemd de l'utilisateur voit (mesuré le 11/11 : elle s'ouvre en `BatchMode`) : une clé sans
  phrase, sur le disque du poste, ouvre Imladris à qui la lit.
- Le Windows de l'hôte n'est pas lu par `make imladris-tunnel-check` : son pare-feu, et le réseau de WSL en
  mode *mirrored*, où une écoute de WSL sur toutes les interfaces le serait aussi sur celles de
  Windows. Le contrôle des écoutes de WSL le couvre en partie.
- Le détail : le [modèle de menace, frontière 9](../design/modele-de-menace.md#9-le-téléphone-et-son-chemin-vers-le-poste).
