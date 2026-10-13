"use strict";
// Grille politique 2027 : affichage de la grille embarquée dans index.html.
// Les heures sont déjà à l'heure de Paris dans les données (ISO 8601 avec décalage) :
// on les affiche telles quelles, quel que soit le fuseau du téléphone.

const DONNEES = JSON.parse(document.getElementById("donnees").textContent);
const CATEGORIES = ["débat", "interview", "meeting", "analyse"];
const PLATEFORMES = { tv: "TV", radio: "Radio", youtube: "YouTube", twitch: "Twitch", web: "Agenda" };
// Plateformes connues avant que les filtres mémorisés ne retiennent la liste (sans la radio).
const PLATEFORMES_ANCIENNES = ["tv", "youtube", "twitch", "web"];
const CLASSE_CATEGORIE = { "débat": "cat-debat", interview: "cat-interview", meeting: "cat-meeting", analyse: "cat-analyse" };
const JOURS = ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."];
const DIRECT_SANS_FIN_MAX = 4 * 3600 * 1000; // un direct sans heure de fin est supposé fini après 4 h

const etat = {
  jour: null,
  categories: new Set(CATEGORIES),
  plateformes: new Set(Object.keys(PLATEFORMES)),
  candidat: "",
  perimetre: "campagne", // « campagne » : Présidentielle 2027 ; « tout » : toute la politique
  chaine: "", // touché sur un logo : n'afficher que cette chaîne (non mémorisé)
};

function lireStockage() {
  try {
    const s = JSON.parse(localStorage.getItem("filtres") || "null");
    if (s) {
      etat.categories = new Set(s.categories);
      etat.plateformes = new Set(s.plateformes);
      // Une plateforme apparue depuis l'enregistrement des filtres est affichée d'office.
      const connues = s.connues || PLATEFORMES_ANCIENNES;
      Object.keys(PLATEFORMES).filter((p) => !connues.includes(p)).forEach((p) => etat.plateformes.add(p));
      etat.candidat = s.candidat || "";
      if (s.perimetre === "tout" || s.perimetre === "campagne") etat.perimetre = s.perimetre;
    }
  } catch (e) { /* stockage indisponible : filtres par défaut */ }
}

function ecrireStockage() {
  try {
    localStorage.setItem("filtres", JSON.stringify({
      categories: [...etat.categories], plateformes: [...etat.plateformes], candidat: etat.candidat,
      perimetre: etat.perimetre,
      connues: Object.keys(PLATEFORMES),
    }));
  } catch (e) { /* sans importance */ }
}

function aujourdhuiParis() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Paris" }).format(new Date());
}

function enDirect(e, maintenant) {
  const debut = Date.parse(e.debut);
  if (debut > maintenant || e.statut === "annulé") return false;
  if (e.fin) return maintenant < Date.parse(e.fin);
  return e.statut === "en direct" && maintenant - debut < DIRECT_SANS_FIN_MAX;
}

function termine(e, maintenant) {
  if (e.fin) return Date.parse(e.fin) <= maintenant;
  return e.statut === "terminé" || (!enDirect(e, maintenant) && Date.parse(e.debut) < maintenant - DIRECT_SANS_FIN_MAX);
}

// Diffuseurs d'une émission : plusieurs quand la même diffusion a été fusionnée.
function sources(e) {
  return e.sources || [{ chaine: e.chaine, plateforme: e.plateforme, lien: e.lien }];
}

// « Jean-Philippe Tanguy (RN) » : sigle du parti après le nom, s'il est connu.
function nommer(noms) {
  const sigles = DONNEES.sigles || {};
  return noms.map((n) => (sigles[n] ? `${n} (${sigles[n]})` : n)).join(", ");
}

function visible(e) {
  const s = sources(e);
  return (etat.perimetre === "tout" || !!e.campagne)
    && etat.categories.has(e.categorie) && s.some((x) => etat.plateformes.has(x.plateforme))
    && (!etat.candidat || e.invites.includes(etat.candidat) || (e.cites || []).includes(etat.candidat))
    && (!etat.chaine || s.some((x) => x.chaine === etat.chaine));
}

function initiales(nom) {
  const mots = nom.replace(/\(.*?\)/g, "").split(/[\s\/·-]+/).filter(Boolean);
  return (mots.length > 1 ? mots[0][0] + mots[1][0] : nom.slice(0, 2)).toUpperCase();
}

function logo(chaine, cliquable) {
  const url = DONNEES.logos[chaine];
  const n = el(cliquable ? "button" : "span", { classe: "logo", title: chaine });
  if (cliquable) {
    n.type = "button";
    n.setAttribute("aria-label", "Afficher seulement " + chaine);
    n.addEventListener("click", (ev) => {
      ev.stopPropagation();
      etat.chaine = etat.chaine === chaine ? "" : chaine;
      afficher();
      window.scrollTo({ top: 0 });
    });
  }
  if (url) {
    const img = el("img", { src: url, alt: "", loading: "lazy", referrerpolicy: "no-referrer" });
    img.addEventListener("error", () => { img.remove(); n.textContent = initiales(chaine); });
    n.append(img);
  } else {
    n.textContent = initiales(chaine);
  }
  return n;
}

function el(balise, attributs = {}, ...enfants) {
  const n = document.createElement(balise);
  for (const [cle, valeur] of Object.entries(attributs)) {
    if (cle === "classe") n.className = valeur;
    else if (cle === "texte") n.textContent = valeur;
    else n.setAttribute(cle, valeur);
  }
  for (const enfant of enfants) if (enfant) n.append(enfant);
  return n;
}

function libelleJour(iso, aujourdhui) {
  const [a, m, j] = iso.split("-").map(Number);
  const date = new Date(Date.UTC(a, m - 1, j, 12));
  if (iso === aujourdhui) return ["Auj.", String(j)];
  return [JOURS[date.getUTCDay()], String(j)];
}

function nomLien(url, e, fini) {
  if (url.includes("youtube.com")) return "YouTube";
  if (url.includes("twitch.tv")) return "Twitch";
  // Radio : direct de la station, ou page de l'émission (réécoute une fois diffusée).
  if (e.plateforme === "radio") {
    if ((DONNEES.directs || []).includes(url)) return "Écouter en direct";
    return fini ? "Réécouter" : "L'émission";
  }
  // Agenda d'un parti : page de l'événement, ou direct de la chaîne pour un passage média.
  if (e.plateforme === "web") return url.includes("direct") ? "Direct " + e.chaine : "Détails";
  if (url.includes("lcp")) return "Direct LCP / Public Sénat";
  return e.plateforme === "tv" ? "Direct " + e.chaine : "Regarder";
}

function libelleLien(url, source, plusieurs, fini) {
  const nom = nomLien(url, source, fini);
  // Plusieurs diffuseurs : préciser lequel (« YouTube · La France insoumise »).
  let libelle = plusieurs && !nom.includes(source.chaine) && !nom.includes("LCP") ? nom + " · " + source.chaine : nom;
  // Version particulière de la même diffusion (« Vélotypie et LSF »).
  if (source.precision) libelle += " · " + source.precision;
  return libelle;
}

function carte(e, maintenant) {
  const direct = enDirect(e, maintenant);
  const fini = !direct && termine(e, maintenant);
  const horaire = e.debut.slice(11, 16) + (e.fin && e.fin.slice(0, 10) === e.debut.slice(0, 10) ? "–" + e.fin.slice(11, 16) : "");
  const s = sources(e);
  const plateformes = [...new Set(s.map((x) => PLATEFORMES[x.plateforme] || x.plateforme))];
  const haut = el("div", { classe: "ligne-haut" },
    ...s.map((x) => logo(x.chaine, true)),
    el("span", { classe: "horaire", texte: horaire }),
    direct ? el("span", { classe: "badge-direct", texte: "En direct" }) : null,
    el("span", { classe: "chaine", texte: s.map((x) => x.chaine).join(" · ") }),
    el("span", { texte: plateformes.join(" · ") }));
  const bas = el("div", { classe: "ligne-bas" }, el("span", { classe: "categorie", texte: e.categorie }));
  const vus = new Set();
  for (const x of s) {
    for (const url of x.lien) {
      if (vus.has(url)) continue;
      vus.add(url);
      bas.append(el("a", { classe: "regarder", href: url, target: "_blank", rel: "noopener",
        texte: libelleLien(url, x, s.length > 1, fini) }));
    }
  }
  return el("article", {
    classe: ["carte", CLASSE_CATEGORIE[e.categorie] || "", direct ? "en-direct" : "", fini ? "termine" : ""].join(" "),
    title: "Retenue par : " + e.filtre,
  },
    haut,
    el("p", { classe: "titre-emission", texte: e.titre }),
    e.invites.length ? el("p", { classe: "invites", texte: "Avec " + nommer(e.invites) }) : null,
    // Personnes seulement citées (sujet d'un commentaire), sans être sur le plateau.
    (e.cites || []).length ? el("p", { classe: "cites", texte: "À propos de " + nommer(e.cites) }) : null,
    bas);
}

// Séparateur d'une tranche d'une heure : « Entre 14 h et 15 h ». L'heure de diffusion
// exacte est sur chaque carte ; le séparateur ne fait que regrouper.
function libelleTranche(h) {
  const nom = (x) => (x === 0 || x === 24 ? "minuit" : x + " h");
  return "Entre " + nom(h) + " et " + nom(h + 1);
}

function afficherJours(aujourdhui) {
  const nav = document.getElementById("jours");
  nav.replaceChildren();
  for (const jour of DONNEES.jours) {
    const nombre = DONNEES.emissions.filter((e) => e.debut.startsWith(jour) && visible(e)).length;
    const [nom, numero] = libelleJour(jour, aujourdhui);
    const bouton = el("button", { classe: "jour", type: "button" },
      el("span", { texte: nom }), el("b", { texte: numero }),
      el("span", { classe: "nombre", texte: nombre ? nombre + " émis." : "—" }));
    if (jour === etat.jour) bouton.setAttribute("aria-current", "date");
    bouton.addEventListener("click", () => { etat.jour = jour; afficher(); });
    nav.append(bouton);
  }
  nav.querySelector('[aria-current="date"]')?.scrollIntoView({ inline: "center", block: "nearest" });
}

function afficherGrille(aujourdhui) {
  const main = document.getElementById("grille");
  main.replaceChildren();
  const maintenant = Date.now();
  const duJour = DONNEES.emissions.filter((e) => e.debut.startsWith(etat.jour) && visible(e));

  if (etat.jour === aujourdhui) {
    // Directs en tête : ceux du jour et ceux commencés la veille, toujours en cours.
    const directs = DONNEES.emissions.filter((e) => visible(e) && enDirect(e, maintenant));
    if (directs.length) {
      main.append(el("h2", { classe: "section-titre direct", texte: "En direct maintenant" }));
      directs.forEach((e) => main.append(carte(e, maintenant)));
      main.append(el("h2", { classe: "section-titre", texte: "Toute la journée" }));
    }
  }
  if (!duJour.length) {
    const filtre = etat.categories.size < CATEGORIES.length || etat.plateformes.size < Object.keys(PLATEFORMES).length || etat.candidat;
    const quoi = etat.perimetre === "campagne" ? "Aucune émission sur la présidentielle annoncée ce jour"
      : "Aucune émission politique annoncée ce jour";
    main.append(el("p", { classe: "vide", texte: quoi + (filtre ? " avec ces filtres." : ".")
      + (etat.perimetre === "campagne" ? " Voir « Toute la politique »." : "") }));
    return;
  }
  let heureCourante = null;
  for (const e of duJour) {
    const heure = e.debut.slice(11, 13);
    if (heure !== heureCourante) {
      heureCourante = heure;
      main.append(el("h3", { classe: "heure", texte: libelleTranche(Number(heure)) }));
    }
    main.append(carte(e, maintenant));
  }
}

function afficherFraicheur() {
  const p = document.getElementById("fraicheur");
  const genere = new Date(DONNEES.genere_le);
  const age = (Date.now() - genere.getTime()) / 3600000;
  const quand = new Intl.DateTimeFormat("fr-FR", {
    timeZone: "Europe/Paris", weekday: "long", hour: "2-digit", minute: "2-digit",
  }).format(genere);
  let texte = "Mise à jour " + quand;
  if (!navigator.onLine) texte = "Hors connexion — grille du " + quand;
  p.textContent = texte + (age > 3 ? " (il y a " + Math.round(age) + " h)" : "");
  p.classList.toggle("alerte", age > 3 || !navigator.onLine);
}

function afficherFiltreChaine() {
  const p = document.getElementById("filtre-chaine");
  p.replaceChildren();
  p.hidden = !etat.chaine;
  if (!etat.chaine) return;
  const bouton = el("button", { classe: "etiquette-chaine", type: "button", "aria-label": "Revenir à toutes les chaînes" },
    logo(etat.chaine, false), el("span", { texte: etat.chaine + "  ✕" }));
  bouton.addEventListener("click", () => { etat.chaine = ""; afficher(); });
  p.append(bouton);
}

function afficherFiltres() {
  const bouton = document.getElementById("bouton-filtres");
  const actif = etat.categories.size < CATEGORIES.length || etat.plateformes.size < Object.keys(PLATEFORMES).length || !!etat.candidat;
  bouton.classList.toggle("actif", actif);
  bouton.textContent = actif ? "Filtres ●" : "Filtres";
  for (const puce of document.querySelectorAll(".puce")) {
    const ensemble = puce.dataset.type === "categorie" ? etat.categories : etat.plateformes;
    puce.setAttribute("aria-pressed", String(ensemble.has(puce.dataset.valeur)));
  }
  document.getElementById("filtre-candidat").value = etat.candidat;
  for (const b of document.querySelectorAll("[data-perimetre]")) {
    b.setAttribute("aria-pressed", String(b.dataset.perimetre === etat.perimetre));
  }
}

function afficher() {
  const aujourdhui = aujourdhuiParis();
  if (!DONNEES.jours.includes(etat.jour)) etat.jour = DONNEES.jours.includes(aujourdhui) ? aujourdhui : DONNEES.jours[0];
  afficherFraicheur();
  afficherFiltres();
  afficherFiltreChaine();
  afficherJours(aujourdhui);
  afficherGrille(aujourdhui);
}

function preparerFiltres() {
  const groupes = [
    ["filtre-categories", "categorie", CATEGORIES, (c) => c, etat.categories],
    ["filtre-plateformes", "plateforme", Object.keys(PLATEFORMES), (p) => PLATEFORMES[p], etat.plateformes],
  ];
  for (const [id, type, valeurs, libelle, ensemble] of groupes) {
    const groupe = document.getElementById(id);
    for (const v of valeurs) {
      const puce = el("button", { classe: "puce", type: "button", texte: libelle(v) });
      puce.dataset.type = type;
      puce.dataset.valeur = v;
      puce.addEventListener("click", () => {
        ensemble.has(v) ? ensemble.delete(v) : ensemble.add(v);
        ecrireStockage();
        afficher();
      });
      groupe.append(puce);
    }
  }
  for (const b of document.querySelectorAll("[data-perimetre]")) {
    b.addEventListener("click", () => { etat.perimetre = b.dataset.perimetre; ecrireStockage(); afficher(); });
  }
  const choix = document.getElementById("filtre-candidat");
  // D'abord les candidats présents dans la grille (avec leur nombre d'émissions), puis les autres.
  const presents = DONNEES.candidats.filter((c) => c.emissions > 0);
  const absents = DONNEES.candidats.filter((c) => c.emissions === 0);
  if (presents.length) {
    choix.append(el("optgroup", { label: "Dans la grille" },
      ...presents.map((c) => el("option", { value: c.nom, texte: `${c.nom} (${c.emissions})` }))));
  }
  if (absents.length) {
    choix.append(el("optgroup", { label: "Aucune émission annoncée" },
      ...absents.map((c) => el("option", { value: c.nom, texte: c.nom }))));
  }
  choix.addEventListener("change", () => { etat.candidat = choix.value; ecrireStockage(); afficher(); });
  document.getElementById("tout-afficher").addEventListener("click", () => {
    CATEGORIES.forEach((c) => etat.categories.add(c));
    Object.keys(PLATEFORMES).forEach((p) => etat.plateformes.add(p));
    etat.candidat = "";
    etat.chaine = "";
    ecrireStockage();
    afficher();
  });
  const bouton = document.getElementById("bouton-filtres");
  bouton.addEventListener("click", () => {
    const panneau = document.getElementById("filtres");
    panneau.hidden = !panneau.hidden;
    bouton.setAttribute("aria-expanded", String(!panneau.hidden));
  });
}

function preparerBalayage() {
  // Glisser vers la gauche : jour suivant ; vers la droite : jour précédent.
  const zone = document.getElementById("grille");
  let x0 = null, y0 = null;
  zone.addEventListener("touchstart", (ev) => { x0 = ev.touches[0].clientX; y0 = ev.touches[0].clientY; }, { passive: true });
  zone.addEventListener("touchend", (ev) => {
    if (x0 === null) return;
    const dx = ev.changedTouches[0].clientX - x0, dy = ev.changedTouches[0].clientY - y0;
    x0 = null;
    if (Math.abs(dx) < 60 || Math.abs(dy) > Math.abs(dx) * 0.6) return;
    const i = DONNEES.jours.indexOf(etat.jour) + (dx < 0 ? 1 : -1);
    if (i >= 0 && i < DONNEES.jours.length) {
      etat.jour = DONNEES.jours[i];
      afficher();
      window.scrollTo({ top: 0 });
    }
  }, { passive: true });
}

lireStockage();
preparerFiltres();
preparerBalayage();
afficher();
window.addEventListener("online", afficher);
window.addEventListener("offline", afficher);
setInterval(afficher, 60000); // les directs et la fraîcheur évoluent avec l'heure

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => { /* hors HTTPS : pas de mode hors connexion */ });
}
