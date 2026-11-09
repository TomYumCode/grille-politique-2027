# Conditions d'utilisation des sources (relevé du 15 octobre 2026)

But : savoir ce que permettent les sources si la grille est ouverte au public (lien partagé,
application). Ce document n'est pas un avis juridique ; les textes cités ont été lus le
15 octobre 2026 (sonde GitHub Actions et recherches web) et peuvent changer.

Principe de l'outil : une seule collecte par heure, avec les clés du propriétaire, puis une page
statique servie à tous les visiteurs. Le nombre de visiteurs ne change rien aux quotas ; c'est
en revanche un **stockage suivi d'une rediffusion**, ce que certaines conditions encadrent.

## Bilan par source

| Source | Ce que disent les conditions | Situation de l'outil | Risque si ouvert au public |
| --- | --- | --- | --- |
| API Radio France | FAQ de l'Open API : « Ai-je le droit de stocker les données retournées par l'Open API ? Non. Chaque client de l'Open API doit utiliser les données immédiatement après la requête, vous ne pouvez pas avoir un serveur en coupure (proxy) qui stockerait les données de l'Open API. […] votre client (application mobile, site Web) doit aller chercher les données directement dans l'Open API en utilisant votre clé d'API. » Page officielle : pas d'agrégation de flux live ni de podcasts ; CGU à accepter ; usage annoncé non commercial (2018). Limite : 1 000 requêtes par jour. | Stockage en base et page publiée : contraire à la FAQ, mais **accord écrit de Radio France reçu le 9 novembre 2026** (voir plus bas). | **Faible** : usage autorisé tel que décrit dans la demande (application gratuite, semaine affichée, collecte toutes les 15 minutes, publicité discrète envisagée). Redemander si l'usage change. |
| API YouTube (Google) | Règles pour les développeurs : toute page qui affiche du contenu YouTube doit indiquer clairement que YouTube en est la source (éléments de marque, consignes de marque) ; données (titres, descriptions) à rafraîchir ou supprimer sous 30 jours ; politique de confidentialité exigée des clients de l'API. | Lien et libellé « YouTube » sur chaque carte ; base jamais purgée des vieilles vidéos ; pas de politique de confidentialité. | **Faible**, après mise en conformité : logo YouTube, purge à 30 jours, page « Confidentialité ». |
| API Twitch | Developer Services Agreement (12/04/2024) : « Do not store copies of Twitch Content or Program Materials, unless you […] (c) cache such information for only a twenty-four hour time period without further sharing it with third parties » ; attribution ; politique de confidentialité publique exigée ; données Twitch non revendues ni monétisées. | Plannings gardés en base au-delà de 24 h et affichés publiquement. | **Moyen** : réduire la conservation à 24 h, attribuer Twitch, et idéalement obtenir un accord écrit (formulaire développeur Twitch). |
| Guide TV xmltvfr.fr | Logiciel libre (Apache 2.0, racacax) ; aucune licence trouvée pour les données des programmes, qui viennent des chaînes ; demande de privilégier le fichier compressé (bande passante). | Fichier compressé lu une fois par heure ; seuls titres, horaires et liens sont affichés, pas les résumés. | **Faible à moyen** : horaires et titres sont des faits peu protégés ; demander l'accord du mainteneur (GitHub racacax/XML-TV-Fr) avant une diffusion large. |
| Sites lus directement : RTL, Europe 1, Sud Radio, RMC, Radio Classique, francetvpro.fr (communiqués), rassemblementnational.fr, upr.fr | Pas d'API ni d'accord. Droit des bases de données (Code de la propriété intellectuelle, art. L342-1) : le producteur peut interdire l'extraction d'une partie substantielle, ou l'extraction répétée et systématique de parties non substantielles excédant l'usage normal (jurisprudence Le Bon Coin 2022, La Centrale 2025, sur des annonces). | Lecture de pages entières chaque heure ; publication d'une petite partie (émissions politiques, horaires, titres, lien vers la chaîne) ; pas de résumés de télévision. | **Faible pour un usage personnel ou restreint**, **à surveiller** pour une application diffusée : lire les CGU et le fichier robots.txt de chaque site, espacer les lectures, citer et renvoyer vers la source. |
| Logos des chaînes | Marques ; ici images fournies par YouTube, Twitch ou le guide. | Affichés pour identifier la chaîne. | **Faible** (usage d'identification), à éviter dans une icône ou une publicité. |
| Visiteurs (RGPD) | Pas de compte, pas de mesure d'audience ; filtres gardés sur le téléphone (stockage local). Les notifications demanderaient d'enregistrer un identifiant d'abonnement par téléphone : donnée personnelle. | — | **Faible** aujourd'hui ; page « Confidentialité » nécessaire avant les notifications. |

## Ce qu'il faudrait faire avant d'ouvrir l'outil

1. **Radio France** : fait. Demande envoyée le 9 novembre 2026 (application gratuite pour
   iPhone et Android, grille gardée le temps de la semaine affichée, au plus 740 requêtes par
   jour, publicité discrète envisagée, jamais placée sur leurs contenus). Réponse du même jour :
   « Ces restrictions ne concernent pas votre cas d'application. Vous pouvez donc utiliser
   l'Open API de la manière exposée dans votre message. » Le courriel de réponse est gardé par
   le propriétaire ; toute évolution de l'usage (abonnement payant, autre usage des données)
   demande une nouvelle question.
2. **YouTube et Twitch** : mise en conformité dans l'outil. Fait le 16 octobre 2026 : données
   effacées si non relues depuis 30 jours (YouTube) ou 24 heures (Twitch, aussi pour les cas
   douteux) ; page « Sources et confidentialité » (`sources.html`, lien en bas de la grille)
   avec les services de l'API YouTube, les conditions de YouTube et de Google, celles de Twitch,
   et la politique de confidentialité. Reste : le logo YouTube à côté des contenus YouTube (le
   nom « YouTube » est affiché sur chaque carte), à vérifier avec les consignes de marque.
3. **Guide TV** : demander l'accord du mainteneur de xmltvfr.fr pour un usage public non
   commercial.
4. **Sites lus directement** : relire leurs CGU et robots.txt ; en cas de demande d'un site,
   le retirer aussitôt (une ligne dans `config/chaines.yaml`).
5. **Rester gratuit, sans publicité et sans revente de données** : c'est la condition qui
   rend les points 1 à 4 réalistes.

## Projet de courriel à Radio France (première version, octobre 2026 ; la demande envoyée le 9 novembre 2026 décrivait l'application grand public)

Objet : Open API — demande d'autorisation pour une grille des émissions politiques (usage non
commercial)

> Bonjour,
>
> J'utilise l'Open API Radio France (application « Grille 2027 ») pour une grille gratuite des
> émissions consacrées à la campagne présidentielle 2027, toutes chaînes confondues : télévision,
> radio, YouTube, Twitch.
>
> Le fonctionnement : une interrogation de la grille de France Inter, franceinfo et France Culture
> par heure (environ 216 requêtes par jour), dont je ne garde que les émissions politiques
> (titre, horaire, invité) avec un lien vers votre site pour écouter. La grille est publiée sous
> forme d'une page web, sans publicité ni usage commercial, et ne diffuse aucun flux ni podcast.
>
> Votre FAQ indique que les données ne doivent pas être stockées par un serveur intermédiaire.
> Interroger l'API depuis chaque téléphone exposerait ma clé et dépasserait vite la limite de
> 1 000 requêtes par jour. Pourriez-vous m'autoriser à conserver ces quelques informations le
> temps de la semaine affichée, pour les publier sur cette page ? Je peux bien sûr ajouter toute
> mention de source que vous souhaiteriez.
>
> Bien cordialement,

## Sources

- FAQ de l'Open API Radio France, citée sur forum.ouvre-boite.org (fil « API Radio France ») ;
  radiofrance.com/lopen-api-radio-france ; api.gouv.fr/les-api/api-radio-france.
- developers.google.com/youtube/terms/developer-policies (version française lue le 15 octobre 2026).
- legal.twitch.com/en/legal/developer-agreement (version du 12/04/2024).
- xmltvfr.fr/docs.php ; github.com/racacax/XML-TV-Fr.
- Légifrance, Code de la propriété intellectuelle, art. L341-1 et suivants ; Cass. 1re civ.
  5 octobre 2022, n° 21-16.307 (Le Bon Coin) et 15 octobre 2025, n° 23-23.167 (La Centrale).
- Apple, App Store Review Guidelines, 4.2 (fonctionnalités minimales) ; notifications web sur
  iPhone depuis iOS 16.4 pour les pages ajoutées à l'écran d'accueil.
