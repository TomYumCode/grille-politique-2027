# Cahier des charges — Grille politique Présidentielle 2027

Version du 8 octobre 2026

## Objectif

Un programme qui collecte chaque heure les émissions politiques annoncées à la télévision et sur le Web, puis les présente dans une grille unique par jour et par heure, jusqu'au second tour de la présidentielle 2027.

- **Utilisateur** : usage personnel, un seul compte, pas d'inscription à gérer.
- **Horizon affiché** : aujourd'hui et les 7 jours suivants.
- **Fraîcheur** : une collecte par heure ; les directs annoncés à la dernière minute doivent apparaître dans l'heure.
- **Hors périmètre** : enregistrement ou rediffusion des émissions, analyse du contenu, décompte des temps de parole.

## Périmètre éditorial

Quatre catégories entrent dans la grille, chacune avec sa propre étiquette de filtre.

| Catégorie | Ce qui entre | Exemples |
| --- | --- | --- |
| Débat | Confrontation entre candidats ou leurs représentants | Débats de premier tour, débat d'entre-deux-tours, débats de primaires |
| Interview | Un invité politique face à un ou plusieurs journalistes | Matinales radio filmées, interviews de 20 h, grands entretiens Web |
| Meeting | Prise de parole d'un candidat diffusée en direct | Meetings, discours, conférences de presse, déclarations de candidature |
| Analyse | Émission de plateau ou de décryptage centrée sur la campagne | Émissions politiques hebdomadaires, soirées électorales, formats YouTube et Twitch |

Une émission est retenue si elle passe l'un de ces trois filtres, appliqués dans cet ordre :

1. **Liste blanche** : l'émission ou la chaîne figure dans la liste des programmes toujours politiques.
2. **Mots-clés** : le titre ou la description contient le nom d'un candidat, d'un parti, ou un terme de campagne (« présidentielle », « débat », « meeting »).
3. **Classement par modèle** : les cas ambigus sont soumis à un appel à l'API Claude, qui répond oui ou non et propose une catégorie.

Les listes de candidats, partis, émissions et mots-clés vivent dans un fichier de configuration modifiable sans toucher au code. La liste des candidats évolue jusqu'à la publication officielle par le Conseil constitutionnel ; elle doit couvrir tous les candidats déclarés, sans sélection.

## Sources

Quatre familles de sources, chacune avec son collecteur indépendant : si l'une tombe, les autres continuent.

| Source | Méthode de collecte | Ce qu'il faut prévoir |
| --- | --- | --- |
| Télévision (TNT et chaînes info) | Guide des programmes au format XMLTV, à 7 jours | Choisir un flux fiable et gratuit ; les titres changent souvent la veille |
| YouTube | API YouTube Data : vidéos des chaînes suivies, avec l'heure de début programmée des directs | Clé API Google ; quota quotidien limité, donc interroger chaîne par chaîne plutôt que par recherche |
| Twitch | API Twitch : planning publié par chaîne, plus l'état « en direct » | Identifiants d'application Twitch ; beaucoup de streamers ne remplissent pas leur planning |
| Web TV et sites des médias | Flux RSS quand il existe, sinon lecture de la page de programmation | Un petit adaptateur par site ; casse à chaque refonte de page |

Liste de départ, à compléter dans le fichier de configuration :

- **Télévision** : TF1, France 2, France 3, France 5, M6, Arte, BFMTV, CNews, LCI, franceinfo, LCP et Public Sénat.
- **Radios filmées** : France Inter, franceinfo, RTL, Europe 1, RMC, Sud Radio.
- **YouTube et Twitch** : chaînes officielles de chaque candidat et de chaque parti, chaînes des médias ci-dessus, et médias natifs du Web à choisir.

Chaînes Twitch et YouTube à suivre en priorité, fournies le 7 octobre 2026 :

| Plateforme | Chaîne | Catégorie |
| --- | --- | --- |
| Twitch | [BackSeat (Jean Massiet)](https://www.twitch.tv/jeanmassiet) | Décryptage |
| Twitch | [Mediapart](https://www.twitch.tv/mediapart) | Média indépendant |
| Twitch | [LCP-Assemblée nationale](https://www.twitch.tv/lcpassembleenationale) | Débats parlementaires |
| Twitch | [La France insoumise](https://www.twitch.tv/la_france_insoumise) | Parti |
| Twitch | [Au Poste (David Dufresne)](https://www.twitch.tv/auposte_fr) | Média indépendant |
| Twitch | [Hugo au Perchoir](https://www.twitch.tv/hugoauperchoir) | Interviews politiques |
| YouTube | [Hugo au Perchoir](https://www.youtube.com/@HugoauPerchoir) | Interviews politiques (rediffusions) |
| YouTube | [HugoDécrypte - Actus du jour](https://www.youtube.com/channel/UCAcAnMF0OrCtUep3Y4M-ZPw) | Décryptage |
| YouTube | [Clément Viktorovitch](https://www.youtube.com/@Clemovitch) | Décryptage |
| YouTube | [Gaspard G](https://www.youtube.com/@GaspardG) | Décryptage |
| YouTube | [Blast](https://www.youtube.com/@blastinfo) | Média indépendant |
| YouTube | [Le Média](https://www.youtube.com/channel/UCT67YOMntJxfRnO_9bXDpvw) | Média indépendant |
| YouTube | [L'Humanité](https://www.youtube.com/@lhumanitefr) | Média indépendant |
| YouTube | [Thinkerview](https://www.youtube.com/@thinkerview) | Débats et interviews |
| YouTube | [C dans l'air](https://www.youtube.com/@Cdanslairofficiel) | Débats et interviews |
| YouTube | [Sciences Po](https://www.youtube.com/@sciencespo) | École |
| YouTube | [HEC Paris](https://www.youtube.com/user/hecparis) | École |
| YouTube | [HEC Débats](https://www.youtube.com/@hecdebats3040) | École |
| YouTube | [La France insoumise](https://www.youtube.com/channel/UCKHKSD-yanY2ZwwU_4Tgf0w) | Parti |
| YouTube | [Parti socialiste](https://www.youtube.com/channel/UCo7xGEOV-RfxOAxRfhlR3Ww) | Parti |
| YouTube | [Renaissance](https://www.youtube.com/@parti-renaissance) | Parti |
| YouTube | Horizons (lien à confirmer) | Parti |
| YouTube | [Rassemblement National](https://www.youtube.com/@RassemblementNationalOfficiel) | Parti |
| YouTube | [Les Républicains](https://www.youtube.com/channel/UC3Ma4tRFxx85oZI_XKVTPwg) | Parti |
| YouTube | [Raphaël Glucksmann](https://www.youtube.com/@RaphaelGlucksmann1) | Personnalité politique |
| YouTube | [Les Écologistes](https://www.youtube.com/@LesEcologistesFR) | Parti |

Un seul lien reste à confirmer : Horizons, couvert en attendant par la chaîne d'Édouard Philippe, qui figure dans les chaînes complémentaires. L'adresse trouvée pour le parti ne s'ouvre pas, et le site du parti renvoie vers la [chaîne d'Édouard Philippe](https://www.youtube.com/@EdouardPhilippe).

**Ajouter une chaîne en cours de route**

- Chaque chaîne est une ligne dans un fichier `chaines.yaml` : plateforme, nom, adresse, catégorie.
- Le fichier se modifie depuis le site GitHub, dans le navigateur ou sur téléphone, sans rien installer.
- La chaîne ajoutée est prise en compte à la collecte suivante, donc dans l'heure.
- Une adresse invalide ne bloque pas les autres sources : elle est signalée dans l'email du matin.

S'y ajoutent 105 chaînes complémentaires, validées le 7 octobre 2026 et à suivre elles aussi : voir l'annexe « Chaînes complémentaires retenues » en fin de document.

Les détails techniques ci-dessus (quotas, points d'accès exacts, flux XMLTV disponible) sont donnés de mémoire et doivent être confirmés dans la documentation officielle au début du lot 1.

## Architecture et hébergement

Démarrage sur GitHub, gratuit, pour tester ; si les retards de collecte gênent, migration vers une machine virtuelle sur ta Freebox Delta, gratuite, ou à défaut vers un petit serveur virtuel (VPS) toujours allumé, de l'ordre de 5 € par mois (prix approximatif), qui fait tout tourner à lui seul.

Schéma : les 4 familles de sources (télévision, YouTube, Twitch, web TV et sites) alimentent GitHub, où des tâches planifiées lancent chaque heure collecteurs → filtre politique et dédoublonnage → base SQLite (fichier dans le dépôt). La base produit 2 sorties : la page web installable et l'email du matin à 7 h.

Chaque heure, les collecteurs interrogent leurs sources, le filtre ne garde que le politique, et la base alimente la page web et l'email du matin.

| Option | Coût | Disponibilité | Limite |
| --- | --- | --- | --- |
| VPS (si la Freebox ne convient pas) | Environ 5 € par mois | 24 h sur 24 | Un peu d'administration, que Claude Code peut scripter |
| Tâches planifiées GitHub et page statique (choix de départ) | Gratuit | 24 h sur 24 | Déclenchements à l'heure approximative ; certains sites bloquent ces serveurs |
| Machine virtuelle sur ta Freebox Delta (repli prévu) | Gratuit | 24 h sur 24, tant que la box est allumée et connectée | Installation plus technique ; accès extérieur à ouvrir sur la box pour consulter la page hors de chez toi |
| Ton PC | Gratuit | Seulement PC allumé | Ni collecte ni email PC éteint ; page inaccessible depuis le téléphone hors de chez toi |

Choix techniques proposés à Claude Code :

- **Langage** : Python, pour ses bibliothèques de lecture XMLTV, d'appels d'API et de lecture de pages web.
- **Base** : SQLite, un fichier enregistré dans le dépôt après chaque collecte.
- **Planification** : des tâches planifiées GitHub, une par heure pour la collecte, une par jour pour l'email.
- **Page web** : page statique régénérée après chaque collecte et publiée sur GitHub Pages, donc rapide et sans risque de panne à l'affichage.
- **Email** : envoi par un service SMTP du commerce, gratuit à ce volume.
- **Secrets** : clés d'API et adresse email dans des variables d'environnement chiffrées de GitHub (secrets), jamais dans le code ni dans la documentation.

## Modèle de données

Une seule table `emissions` suffit : une ligne par diffusion, quelle que soit la source.

| Champ | Contenu | Exemple |
| --- | --- | --- |
| `id` | Identifiant stable, calculé à partir de la source et de l'identifiant d'origine | `youtube:abc123` |
| `titre` | Titre tel qu'annoncé | Le grand débat |
| `debut`, `fin` | Date et heure, fuseau Europe/Paris ; `fin` peut être vide | 2027-03-15 21:00 |
| `plateforme` | tv, youtube, twitch ou web | tv |
| `chaine` | Nom de la chaîne ou du compte | France 2 |
| `categorie` | débat, interview, meeting ou analyse | débat |
| `invites` | Personnalités repérées dans le titre ou la description | liste de noms |
| `lien` | Adresse pour regarder en direct | URL |
| `statut` | annoncé, en direct, terminé ou annulé | annoncé |
| `filtre` | Filtre qui a retenu l'émission : liste blanche, mots-clés ou modèle | mots-clés |
| `vu_le` | Dernière collecte où l'émission a été vue | horodatage |

Deux règles de traitement :

- **Dédoublonnage** : une même émission diffusée à la télévision et sur YouTube à la même heure est fusionnée en une ligne portant plusieurs liens.
- **Mise à jour** : une émission déjà connue dont l'heure ou le titre change est modifiée, pas recréée ; une émission qui disparaît de sa source passe en « annulé ».

## Restitution

Une seule page web couvre les trois besoins : elle se consulte dans le navigateur, s'installe sur l'écran d'accueil du téléphone comme une application, et sert de base à l'email quotidien.

**Page web**

- Vue par défaut : la journée en cours, heure par heure, avec les émissions en direct mises en avant en haut.
- Navigation par jour sur 7 jours, d'un geste ou d'un clic.
- Filtres par catégorie, par plateforme et par candidat.
- Chaque émission affiche l'heure, la chaîne, le titre, les invités et un lien direct pour regarder.
- Conçue d'abord pour le téléphone ; lisible sans connexion avec la dernière grille chargée.

**Application mobile**

La page est une application web installable (PWA) : icône sur l'écran d'accueil, plein écran, aucun passage par les magasins d'applications. Une application native n'apporterait rien de plus pour cet usage et coûterait plusieurs semaines.

**Email quotidien**

- Envoi chaque matin à 7 h, heure de Paris, à l'adresse enregistrée dans le secret GitHub `EMAIL_DESTINATAIRE` (jamais en clair dans le dépôt, qui est public).
- Contenu : la grille du jour triée par heure, puis les temps forts des 3 jours suivants.
- Chaque ligne renvoie vers le lien de visionnage.
- En option pour plus tard : une alerte 15 minutes avant un débat entre candidats.

## Étapes de réalisation

Six lots à donner à Claude Code un par un ; chacun produit quelque chose de vérifiable avant de passer au suivant.

1. **Socle** : dépôt, base de données, fichier de configuration (chaînes, candidats, mots-clés), et vérification des accès aux API.
   - Terminé quand : une commande crée la base vide et lit la configuration sans erreur.
2. **Collecteur télévision** : lecture du guide XMLTV, filtrage politique, écriture en base.
   - Terminé quand : la commande liste les émissions politiques des 7 prochains jours sur les chaînes configurées.
3. **Collecteurs YouTube et Twitch** : directs programmés et plannings des chaînes suivies.
   - Terminé quand : un direct programmé sur une chaîne suivie apparaît en base avec la bonne heure de Paris.
4. **Page web** : grille par jour et par heure, filtres, version installable sur téléphone.
   - Terminé quand : la grille du jour s'affiche correctement sur téléphone à partir de la base.
5. **Mise en ligne et planification** : déploiement sur GitHub, collecte horaire automatique, email du matin.
   - Terminé quand : l'email arrive à 7 h et la page se met à jour seule pendant 48 heures.
6. **Web TV et finitions** : adaptateurs pour les sites sans API, dédoublonnage entre plateformes, classement des cas ambigus par modèle.
   - Terminé quand : un débat diffusé sur deux plateformes n'apparaît qu'une fois, avec ses deux liens.

Les lots 1 à 5 donnent un outil utilisable. Le lot 6 peut s'étaler sur la campagne, au rythme des sources que tu veux ajouter.

Consigne à placer en tête du projet dans Claude Code : écrire un test par collecteur à partir d'une réponse enregistrée de la source, pour repérer tout de suite un changement de format.

## Risques et points à trancher

Le risque principal est la fragilité des sources sans API : une page de programmation qui change de structure casse son adaptateur sans prévenir.

| Risque | Conséquence | Parade |
| --- | --- | --- |
| Un site change sa page | Une source disparaît de la grille sans erreur visible | Alerte par email si une source ne renvoie rien pendant 24 heures |
| Quota YouTube dépassé | Plus de mise à jour YouTube jusqu'au lendemain | Interroger chaque chaîne directement, limiter la liste aux chaînes utiles |
| Faux positifs du filtre | Émissions sans rapport dans la grille | Champ `filtre` visible pour repérer la règle fautive et l'ajuster |
| Directs non annoncés | Meeting lancé sans programmation préalable | Vérification de l'état « en direct » des chaînes de candidats à chaque collecte |
| Conditions d'utilisation des sites | Lecture automatique de pages parfois interdite | Préférer API et RSS ; rythme lent ; usage strictement personnel, grille non publiée |

Décisions (mises à jour le 8 octobre 2026) :

- [x] Valider l'hébergement GitHub en créant le compte et le dépôt du projet : dépôt public créé le 8 octobre 2026. Public, il bénéficie des tâches planifiées GitHub sans limite de minutes.
- [x] Liste des chaînes YouTube et Twitch fournie ; sites de web TV à ajouter si besoin.
- [x] Choisir l'adresse qui reçoit l'email du matin : choisie, enregistrée dans le secret GitHub `EMAIL_DESTINATAIRE` pour ne pas l'exposer dans le dépôt public.
- [x] Accepter que la page soit publique sur GitHub, sans mot de passe : accepté. La page demandera aux moteurs de recherche de ne pas l'indexer, et son adresse ne sera diffusée à personne. En cas de gêne, repli vers la Freebox.
- [ ] Accepter ou non le classement des cas ambigus par l'API Claude, qui a un coût à l'usage : accord de principe, décision finale au lot 6, selon le nombre de cas que les deux premiers filtres laissent passer. Modèle envisagé : Claude Haiku 5.5, le moins cher (de l'ordre de quelques centimes par jour), avec un plafond de dépenses de 5 $ fixé dans la console. Prérequis : un compte sur console.anthropic.com avec du crédit prépayé (l'abonnement Claude ne couvre pas l'API) et une clé dans le secret `ANTHROPIC_API_KEY`.

Décidé au lot 5 :

- [x] Conserver la base sur une branche `donnees` qui ne garde que la dernière version, remplacée à chaque collecte : l'historique du dépôt ne grossit pas.
- [x] Email envoyé par le serveur SMTP d'iCloud, avec un mot de passe d'application révocable à tout moment.

Ajouté après le lot 5 :

- [ ] Radios : collecteur Radio France (API officielle : France Inter, franceinfo, France Culture), puis les autres stations susceptibles de diffuser des débats politiques. Radio Nova ajoutée le 10 octobre 2026 (émission « 2027 raisons de voter »), suivie par sa chaîne YouTube faute d'API de grille, comme RTL, Europe 1, RMC et Sud Radio.
- [ ] Lot 6 : lire les agendas publiés sur les sites des candidats et des partis, pour annoncer à l'avance les meetings diffusés en direct sans programmation YouTube (meeting de Gabriel Attal à Lyon, 10 octobre 2026, apparu seulement à son début).
- [ ] Lot 6 : lire les invités annoncés sur les sites des chaînes (france.tv et autres) quand le guide télévision ne les donne pas, comme pour Franc-jeu (France 2). Fait pour France Télévisions le 10 octobre 2026 : communiqués de presse de francetvpro.fr (france.tv ne montre que les émissions passées). Autres chaînes à étudier.

---

# Annexe — Chaînes complémentaires retenues

105 chaînes YouTube et Twitch repérées le 7 octobre 2026 pour compléter ta liste, sur tout l'éventail politique. Liste validée en bloc le 7 octobre 2026 : toutes ces chaînes sont à suivre, en plus de la liste de départ.

Les étiquettes d'orientation sont indicatives : elles reprennent l'auto-description de la chaîne quand elle existe, sinon l'usage courant de la presse. « À confirmer » signale une adresse ou une activité non vérifiée, que Claude Code contrôlera au lot 3 avant de l'activer. La fréquence réelle des directs n'a pas été contrôlée chaîne par chaîne.

## Grands médias : télévision, radio, presse

| Chaîne | Plateforme | Type ou orientation | État |
| --- | --- | --- | --- |
| [France Inter](https://www.youtube.com/@franceinter) | YouTube | Radio publique, matinale et interviews | Vérifié |
| [franceinfo](https://www.youtube.com/@franceinfo) | YouTube | Média public, info en continu | Vérifié |
| [France Culture](https://www.youtube.com/@franceculture) | YouTube | Radio publique, débats d'idées | Vérifié |
| [France Télévisions](https://www.youtube.com/@FranceTelevisions) | YouTube | Média public | Vérifié |
| [C à vous](https://www.youtube.com/@cavousofficiel) | YouTube | Média public, talk-show | Vérifié |
| [C ce soir](https://www.youtube.com/channel/UC1UUvhau_2V8ETvHfwkUQwg) | YouTube | Média public, débat | Vérifié |
| [28 minutes - ARTE](https://www.youtube.com/@28minutesARTE) | YouTube | Média public, débat quotidien | Vérifié |
| [ARTE Info](https://www.youtube.com/@ArteInfoFR) | YouTube | Média public, actualité européenne | Vérifié |
| [LCP - Assemblée nationale](https://www.youtube.com/@LCPAssembleenationale) | YouTube | Chaîne parlementaire | Vérifié |
| [Public Sénat](https://www.youtube.com/@publicsenat) | YouTube | Chaîne parlementaire | Vérifié |
| [France 24](https://www.youtube.com/@FRANCE24) | YouTube | Média public international | Vérifié |
| [BFMTV](https://www.youtube.com/@BFMTV) | YouTube | Info en continu, généraliste | Vérifié |
| [LCI](https://www.youtube.com/@LCI) | YouTube | Info en continu, généraliste | Vérifié |
| [TF1 Info](https://www.youtube.com/@TF1INFO) | YouTube | Généraliste | Vérifié |
| [CNews](https://www.youtube.com/@CNEWSofficiel) | YouTube | Info en continu, droite | Vérifié |
| [Europe 1](https://www.youtube.com/@Europe1) | YouTube | Radio privée, droite | Vérifié |
| [RTL](https://www.youtube.com/@rtl_france) | YouTube | Radio privée, généraliste | Vérifié |
| [RMC](https://www.youtube.com/@RMC) | YouTube | Radio privée, généraliste | Vérifié |
| [Sud Radio](https://www.youtube.com/@SudRadioOfficiel) | YouTube | Radio privée, généraliste | Vérifié |
| [Quotidien](https://www.youtube.com/@QuotidienTMC) | YouTube | Talk-show | Vérifié |
| [Le Figaro TV](https://www.youtube.com/@LeFigaroTV) | YouTube | Presse, droite | Vérifié |
| [Le Figaro](https://www.youtube.com/@LeFigaro) | YouTube | Presse, droite | Vérifié |
| [Le Monde](https://www.youtube.com/@lemondefr) | YouTube | Presse, généraliste | Vérifié |
| [Libération](https://www.youtube.com/@liberation) | YouTube | Presse, gauche | Vérifié |
| [L'Opinion](https://www.youtube.com/@Lopinionfr) | YouTube | Presse, libéral | Vérifié |
| [Le Point](https://www.youtube.com/@lepoint) | YouTube | Presse, centre droit, libéral | Vérifié |
| [L'Express](https://www.youtube.com/@LEXPRESS) | YouTube | Presse, libéral | Vérifié |
| [Marianne](https://www.youtube.com/@Mariannetv) | YouTube | Presse, souverainiste | Vérifié |
| [Le JDD](https://www.youtube.com/@le_jdd) | YouTube | Presse, droite | Vérifié |
| [Le Parisien](https://www.youtube.com/@leparisien) | YouTube | Presse, généraliste | Vérifié |
| [Ouest-France](https://www.youtube.com/@ouestfrance) | YouTube | Presse régionale, généraliste | Vérifié |
| [Konbini](https://www.youtube.com/@konbini) | YouTube | Média jeune, interviews ponctuelles | Vérifié |
| [Brut](https://www.youtube.com/c/brutofficiel) | YouTube | Média jeune, interviews ponctuelles | À confirmer |
| [Valeurs actuelles](https://www.youtube.com/user/valeursactuelles) | YouTube | Presse, droite | À confirmer |

## Médias du Web, émissions et cercles de réflexion

| Chaîne | Plateforme | Type ou orientation | État |
| --- | --- | --- | --- |
| [Le Crayon](https://www.youtube.com/@LeCrayonMedia) | YouTube | Débats contradictoires, pluraliste | Vérifié |
| [LEGEND](https://www.youtube.com/@LEGENDmedia) | YouTube | Longues interviews, non classé | Vérifié |
| [Mediapart](https://www.youtube.com/@mediapart) | YouTube | Gauche (déjà suivi sur Twitch) | Vérifié |
| [Arrêt sur images](https://www.youtube.com/channel/UCXHWT_QoQSsdGXbqF0hAMtg) | YouTube | Critique des médias, gauche | Vérifié |
| [QG TV](https://www.youtube.com/channel/UCCDPdHuBGfjMxlM3xZANgGQ) | YouTube | Gauche | Vérifié |
| [Élucid](https://www.youtube.com/@Elucid) | YouTube | Entretiens, souverainiste de gauche | Vérifié |
| [Off Investigation](https://www.youtube.com/@OffInvestigation) | YouTube | Enquête, gauche | Vérifié |
| [StreetPress](https://www.youtube.com/@StreetPress) | YouTube | Enquête, gauche | Vérifié |
| [Le Vent Se Lève](https://www.youtube.com/@LeVentSeLeve) | YouTube | Gauche | Vérifié |
| [Osons Causer](https://www.youtube.com/@OsonsCauser) | YouTube | Vulgarisation, gauche, peu de directs | Vérifié |
| [Tocsin](https://www.youtube.com/@Tocsin-media) | YouTube | Matinale quotidienne, souverainiste | Vérifié |
| [Front Populaire](https://www.youtube.com/@FrontPopulaireOff) | YouTube | Souverainiste | Vérifié |
| [Juste Milieu](https://www.youtube.com/@JusteMilieu) | YouTube | Directs d'actualité, non classé | Vérifié |
| [Les Incorrectibles](https://www.youtube.com/@LesIncorrectibles) | YouTube | Émission hebdomadaire, droite | Vérifié |
| [Frontières](https://www.youtube.com/@Frontieresmedia) | YouTube | Droite identitaire | Vérifié |
| [Omerta](https://www.youtube.com/@omertamediaoff) | YouTube | Droite souverainiste | Vérifié |
| [Ligne Droite](https://www.youtube.com/@LigneDroiteMatinale) | YouTube | Matinale, droite | Vérifié |
| [TVLibertés](https://www.youtube.com/@tvlibertes) | YouTube | Droite nationale | Vérifié |
| [Contrepoints](https://www.youtube.com/@Contrepoints) | YouTube | Libéral | Vérifié |
| [Tatiana Ventôse](https://www.youtube.com/@TatianaventoseTV) | YouTube | Créatrice, souverainiste | Vérifié |
| [Fondapol](https://www.youtube.com/@Fondapol) | YouTube | Cercle de réflexion, libéral | Vérifié |
| [Fondation Jean-Jaurès](https://www.youtube.com/c/fondationjeanjaures) | YouTube | Cercle de réflexion, social-démocrate | Vérifié |
| [Institut Montaigne](https://www.youtube.com/user/institutmontaigne) | YouTube | Cercle de réflexion, libéral | Vérifié |
| [Terra Nova](https://www.youtube.com/channel/UC_61p_l9h4q24BTs-CCotjg) | YouTube | Cercle de réflexion, centre gauche | Vérifié |
| [Mardis du Grand Continent](https://www.youtube.com/c/mardisgrandcontinent) | YouTube | Revue, pro-européen | À confirmer |

## Partis et mouvements

| Chaîne | Plateforme | Type ou orientation | État |
| --- | --- | --- | --- |
| [MoDem](https://www.youtube.com/@MouvementDemocrate) | YouTube | Parti, centre | Vérifié |
| [UDI](https://www.youtube.com/@UDI_off) | YouTube | Parti, centre droit | Vérifié |
| [La France Humaniste](https://www.youtube.com/@LaFranceHumaniste) | YouTube | Parti de Dominique de Villepin | Vérifié |
| [Place publique](https://www.youtube.com/@placepublique) | YouTube | Parti, centre gauche | Vérifié |
| [PCF](https://www.youtube.com/user/cnpcf) | YouTube | Parti, gauche communiste | Vérifié |
| [Debout!](https://www.youtube.com/@Debout_fr) | YouTube | Mouvement de François Ruffin, gauche | Vérifié |
| [NPA - L'Anticapitaliste](https://www.youtube.com/@NPALAnticapitaliste) | YouTube | Parti, extrême gauche | Vérifié |
| [Lutte ouvrière](https://www.youtube.com/@LutteOuvriere) | YouTube | Parti, extrême gauche | Vérifié |
| [Révolution Permanente](https://www.youtube.com/channel/UCwLLr_Fo9dpdJ9UHq4A7PjA) | YouTube | Organisation, extrême gauche | Vérifié |
| [Debout la France](https://www.youtube.com/c/DEBOUTLAFRANCE) | YouTube | Parti, souverainiste | Vérifié |
| [Les Patriotes](https://www.youtube.com/@LesPatriotes) | YouTube | Parti, souverainiste | Vérifié |
| [UPR](https://www.youtube.com/user/UPRdiffusion) | YouTube | Parti, souverainiste | Vérifié |

Aucune chaîne officielle trouvée pour Reconquête, l'UDR, Nouvelle Énergie, Génération.s ni Génération Écologie. Pour Reconquête et Nouvelle Énergie, les chaînes personnelles d'Éric Zemmour et de David Lisnard en tiennent lieu.

## Candidats déclarés ou pressentis

État à l'automne 2026 d'après [France-Vote](https://www.france-vote.fr/actualites/candidats-presidentielle-2027-qui-se-presente) (mise à jour du 21 septembre 2026), recoupé en partie avec [France 24](https://www.france24.com/fr/france/20260524-france-presidentielle-2027-qui-sont-les-candidats-officiellement-declares) et [Sud Radio](https://www.sudradio.fr/sud-radio/presidentielle-2027-qui-sont-les-candidats-declares). La liste des candidats bouge vite : à revérifier avant le lot 3.

| Chaîne | Plateforme | Statut indiqué par ces sources | État |
| --- | --- | --- | --- |
| [Jean-Luc Mélenchon](https://www.youtube.com/@JLMelenchon) | YouTube | Déclaré, LFI | Vérifié |
| [François Ruffin](https://www.youtube.com/@francois_ruffin) | YouTube | Déclaré, Debout! | Vérifié |
| [Juan Branco](https://www.youtube.com/@JuanBrancoFR) | YouTube | Déclaré, sans étiquette | Vérifié |
| [Nathalie Arthaud](https://www.youtube.com/c/NathalieArthaudLutteOuvriere) | YouTube | Déclarée, Lutte ouvrière | Vérifié |
| [Gabriel Attal](https://www.youtube.com/@gabriel_attal) | YouTube | Déclaré, Renaissance | Vérifié |
| [Édouard Philippe](https://www.youtube.com/@EdouardPhilippe) | YouTube | Déclaré, Horizons | Vérifié |
| [Bruno Retailleau](https://www.youtube.com/@Bruno_Retailleau) | YouTube | Désigné par Les Républicains | Vérifié |
| [David Lisnard](https://www.youtube.com/@david_lisnard) | YouTube | Déclaré, Nouvelle Énergie | Vérifié |
| [Marine Le Pen](https://www.youtube.com/@MarineLePenOfficiel) | YouTube | Déclarée, RN | Vérifié |
| [Jordan Bardella](https://www.youtube.com/@J_Bardella) | YouTube | Président du RN, non candidat | Vérifié |
| [Éric Zemmour](https://www.youtube.com/@EricZemmourOff) | YouTube | Déclaré, Reconquête | Vérifié |
| [Florian Philippot](https://www.youtube.com/@FLORIANPHILIPPOT1) | YouTube | Pressenti, Les Patriotes | Vérifié |
| [François Asselineau](https://www.youtube.com/@f_asselineau) | YouTube | Pressenti, UPR | Vérifié |
| [Jean Lassalle](https://www.youtube.com/@JeanLassalleOfficiel) | YouTube | Pressenti | Vérifié |

Aucune chaîne personnelle trouvée pour Marine Tondelier, Fabien Roussel, Xavier Bertrand, Olivier Faure, Jérôme Guedj, Ségolène Royal, Bruno Le Maire, Delphine Batho ni Anasse Kazib : leurs contenus passent par les chaînes de leur parti.

## Institutions

| Chaîne | Plateforme | Ce qu'on y trouve | État |
| --- | --- | --- | --- |
| [Assemblée nationale](https://www.youtube.com/@Assemblee-nationale) | YouTube | Séances et commissions en direct | Vérifié |
| [Sénat](https://www.youtube.com/@senat) | YouTube | Séances et auditions en direct | Vérifié |
| [Élysée](https://www.youtube.com/@elysee) | YouTube | Discours et déclarations | Vérifié |
| [Gouvernement](https://www.youtube.com/@gouvernementFR) | YouTube | Comptes rendus du Conseil des ministres | Vérifié |
| [Conseil constitutionnel](https://www.youtube.com/@Conseilconstitutionnel) | YouTube | Parrainages, audiences | Vérifié |
| [Vie-publique](https://www.youtube.com/@viepublique) | YouTube | Pédagogie | Vérifié |

## Twitch

| Chaîne | Plateforme | Type ou orientation | État |
| --- | --- | --- | --- |
| [Samuel Étienne](https://www.twitch.tv/samueletienne) | Twitch | Revue de presse quotidienne, généraliste | Vérifié |
| [Clemovitch (Clément Viktorovitch)](https://www.twitch.tv/clemovitch) | Twitch | Analyse du discours politique | Vérifié |
| [HugoDécrypte](https://www.twitch.tv/hugodecrypte) | Twitch | Talk-show d'actualité, généraliste | Vérifié |
| [Ostpolitik](https://www.twitch.tv/ostpolitik) | Twitch | Matinale d'actualité, non classé | Vérifié |
| [franceinfo](https://www.twitch.tv/franceinfo) | Twitch | Média public | Vérifié |
| [BFMTV](https://www.twitch.tv/bfmtv) | Twitch | Généraliste | Vérifié |
| [Sardoche](https://www.twitch.tv/sardoche) | Twitch | Streamer, jeux vidéo et politique, droite libérale | Vérifié |
| [Paroles d'Honneur](https://www.twitch.tv/parolesdhonneur) | Twitch | Gauche décoloniale | À confirmer |
| [Usul](https://www.twitch.tv/usul2000) | Twitch | Gauche | À confirmer |
| [Dany et Raz](https://www.twitch.tv/danyetraz) | Twitch | Gauche | À confirmer |
| [Le Média](https://www.twitch.tv/lemediatv) | Twitch | Gauche | À confirmer |
| [Public Sénat](https://www.twitch.tv/publicsenat) | Twitch | Chaîne parlementaire | À confirmer |
| [Le Monde](https://www.twitch.tv/lemondefr) | Twitch | Presse, généraliste | À confirmer |
| [ARTE](https://www.twitch.tv/arte) | Twitch | Média public | À confirmer |
