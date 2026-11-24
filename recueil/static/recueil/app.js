/**
 * BCB — Ouverture de compte — app.js
 *
 * 1. Formulaire dossier : champs conditionnels + suggestions (datalist)
 * 2. Navigation latérale active
 * 3. Focus résumé d'erreurs
 * 4. Formulaire gestionnaire : agence conditionnelle
 */

// ============================================================
// DONNÉES DE RÉFÉRENCE
// ============================================================

// Afficher/masquer les mots de passe au besoin, sans changer leur valeur.
document.querySelectorAll("[data-password-toggle]").forEach((button) => {
  button.addEventListener("click", () => {
    const input = button.parentElement?.querySelector('input[type="password"], input[type="text"]');
    if (!input) return;
    const visible = input.type === "password";
    input.type = visible ? "text" : "password";
    button.textContent = visible ? "Masquer" : "Afficher";
    button.setAttribute("aria-pressed", String(visible));
    button.setAttribute("aria-label", visible ? "Masquer le mot de passe" : "Afficher le mot de passe");
  });
});

const PAYS_AFRIQUE = [
  "Burkina Faso","Côte d'Ivoire","Mali","Niger","Sénégal","Ghana","Togo","Bénin",
  "Guinée","Sierra Leone","Liberia","Gambie","Mauritanie","Cap-Vert",
  "Cameroun","Nigeria","Tchad","Centrafrique","Congo","RD Congo","Gabon",
  "Maroc","Algérie","Tunisie","Égypte","Libye","Soudan","Éthiopie",
  "Kenya","Tanzanie","Ouganda","Rwanda","Mozambique","Afrique du Sud",
  "France","Belgique","Suisse","Canada","États-Unis","Allemagne","Royaume-Uni",
];

const VILLES_BF = [
  "Ouagadougou","Bobo-Dioulasso","Koudougou","Ouahigouya","Banfora",
  "Kaya","Tenkodogo","Fada N'Gourma","Dédougou","Réo","Gaoua",
  "Manga","Ziniaré","Léo","Diébougou","Nouna","Tougan","Kongoussi",
  "Bogandé","Sebba","Dori","Djibo","Titao","Yako","Zorgho","Pouytenga",
];

const VILLES_MONDE = [...VILLES_BF,
  "Abidjan","Dakar","Bamako","Niamey","Lomé","Cotonou","Accra","Conakry",
  "Lagos","Douala","Paris","Lyon","Bruxelles","Montréal","Washington",
];

const AUTORITES_DELIVRANCE = ["ONI","Préfecture","Commissariat de police","Mairie","Ambassade","Consulat"];

const PROFESSIONS_COURANTES = [
  "Commerçant(e)","Fonctionnaire","Enseignant(e)","Infirmier(ère)","Médecin",
  "Pharmacien(ne)","Ingénieur(e)","Agriculteur(rice)","Éleveur(euse)",
  "Chauffeur","Mécanicien(ne)","Maçon","Électricien(ne)","Plombier",
  "Couturier(ère)","Coiffeur(euse)","Artisan(e)","Agent de sécurité",
  "Militaire","Policier(ère)","Gendarme","Magistrat(e)","Avocat(e)",
  "Comptable","Économiste","Architecte","Journaliste","Étudiant(e)",
  "Retraité(e)","Ménagère","Sans emploi","Gérant(e)","Directeur(rice)",
];

const PROFESSIONS_CONJOINT_F = [
  "Ménagère","Fonctionnaire","Commerçante","Enseignante","Infirmière",
  "Comptable","Secrétaire","Agricultrice","Artisane","Retraitée","Sans emploi",
];
const PROFESSIONS_CONJOINT_M = [
  "Fonctionnaire","Commerçant","Enseignant","Ingénieur","Médecin",
  "Comptable","Agriculteur","Chauffeur","Artisan","Retraité","Sans emploi",
];

const TRANCHES_REVENU = [
  "Moins de 50 000 FCFA","50 000 – 100 000 FCFA","100 000 – 200 000 FCFA",
  "200 000 – 500 000 FCFA","500 000 – 1 000 000 FCFA","Plus de 1 000 000 FCFA",
];

const NATURES_VERSEMENT = ["Espèces","Virement bancaire","Chèque","Virement international","Autre"];

const REGIMES_MATRIMONIAUX = ["Biens communs","Biens séparés","Séparation de biens et de dettes"];

// ============================================================
// UTILITAIRES datalist
// ============================================================

function attachDatalist(fieldName, options) {
  const el = document.querySelector(`[data-field-name="${fieldName}"]`);
  if (!el || el.tagName !== "INPUT") return;
  const listId = `dl-${fieldName}`;
  if (!document.getElementById(listId)) {
    const dl = document.createElement("datalist");
    dl.id = listId;
    options.forEach((opt) => {
      const o = document.createElement("option");
      o.value = opt;
      dl.appendChild(o);
    });
    document.body.appendChild(dl);
  }
  el.setAttribute("list", listId);
  el.setAttribute("autocomplete", "off");
}

// ============================================================
// 1. FORMULAIRE DOSSIER CLIENT
// ============================================================
(() => {
  const form = document.querySelector(".intake-layout");
  if (!form) return;

  // ---- Utilitaires champs ----
  function getWrap(fieldName) {
    const el = form.querySelector(`[data-field-name="${fieldName}"]`);
    return el ? el.closest(".field-wrap") : null;
  }

  function setVisible(fieldName, visible) {
    const wrap = getWrap(fieldName);
    if (!wrap) return;
    wrap.hidden = !visible;
    wrap.querySelectorAll("input, select, textarea").forEach((f) => {
      f.disabled = !visible;
    });
  }

  function setGroupVisible(fieldNames, visible) {
    fieldNames.forEach((n) => setVisible(n, visible));
  }

  function getValue(fieldName) {
    const el = form.querySelector(`[data-field-name="${fieldName}"]`);
    if (!el) return "";
    if (el.type === "radio") {
      const checked = form.querySelector(`[data-field-name="${fieldName}"]:checked`);
      return checked ? checked.value : "";
    }
    return el.value || "";
  }

  function getBoolValue(fieldName) {
    const checked = form.querySelector(`[data-field-name="${fieldName}"]:checked`);
    if (!checked) return null;
    return checked.value === "True";
  }

  function watch(fieldNames, callback) {
    if (typeof fieldNames === "string") fieldNames = [fieldNames];
    fieldNames.forEach((name) => {
      form.querySelectorAll(`[data-field-name="${name}"]`).forEach((el) => {
        el.addEventListener("change", callback);
        el.addEventListener("input", callback);
      });
    });
  }

  function setInputValue(fieldName, value) {
    const el = form.querySelector(`[data-field-name="${fieldName}"]`);
    if (el && !el.value) el.value = value;
  }

  // ============================================================
  // TYPE DE COMPTE → section Entreprise
  // ============================================================
  const businessSection = form.querySelector("[data-business-section]");
  const businessLink = form.querySelector("[data-business-nav]");

  function syncTypeCompte() {
    const isComm = getValue("type_compte") === "COMMERCIAL";
    if (businessSection) businessSection.hidden = !isComm;
    if (businessLink) businessLink.hidden = !isComm;
    businessSection?.querySelectorAll("input, select, textarea, button").forEach((f) => {
      f.disabled = !isComm;
    });
    // Les consentements CREDITINFO s'appliquent aux deux types de compte
  }
  watch("type_compte", syncTypeCompte);
  syncTypeCompte();

  // KYC personne morale : coordonnées du contact à l'étranger uniquement pour la diaspora.
  const CHAMPS_CONTACT_DIASPORA = [
    "contact_diaspora_pays", "contact_diaspora_nom", "contact_diaspora_adresse",
    "contact_diaspora_domicile", "contact_diaspora_telephone_fixe",
    "contact_diaspora_telephone_mobile",
  ];
  function syncContactDiaspora() {
    setGroupVisible(CHAMPS_CONTACT_DIASPORA, getBoolValue("resident_bf") === false);
  }
  watch("resident_bf", syncContactDiaspora);
  syncContactDiaspora();

  const consentCheckAll = form.querySelector("[data-consent-check-all]");
  consentCheckAll?.addEventListener("click", () => {
    ["f2_transmission_credit", "f2_partage_credit", "f2_exclusion_depots",
      "f2_limite_anciennete", "f2_duree_conservation", "f2_droit_acces",
      "f2_droit_rapport"].forEach((name) => {
      const yes = form.querySelector(`[data-field-name="${name}"][value="True"]`);
      if (yes && !yes.checked) {
        yes.checked = true;
        yes.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
  });

  // ============================================================
  // SITUATION MATRIMONIALE → champs conjoint
  // ============================================================
  const CHAMPS_CONJOINT = [
    "regime_matrimonial",
    "conjoint_nom","conjoint_contact","conjoint_date_naissance",
    "conjoint_ville_naissance","conjoint_pays_naissance","conjoint_nom_mere",
    "conjoint_type_piece","conjoint_numero_piece","conjoint_piece_delivree_a",
    "conjoint_piece_delivree_le","conjoint_piece_delivree_par","conjoint_piece_expire_le",
    "conjoint_profession","conjoint_date_embauche","conjoint_tranche_revenu",
  ];

  function syncConjoint() {
    const sit = getValue("situation_matrimoniale");
    const estMarie = sit === "MARIE_MONO" || sit === "MARIE_POLY";
    setGroupVisible(CHAMPS_CONJOINT, estMarie);
    // Préremplir pays naissance conjoint avec BF par défaut
    if (estMarie) setInputValue("conjoint_pays_naissance", "Burkina Faso");
    // Suggestions profession conjoint selon le sexe du client
    updateConjointProfSuggestions();
  }
  watch("situation_matrimoniale", syncConjoint);
  syncConjoint();

  // ============================================================
  // DATE EMBAUCHE CONJOINT → visible seulement si conjoint salarié
  // ============================================================
  function syncConjointEmbauche() {
    const prof = (getValue("conjoint_profession") || "").toLowerCase();
    const estSalarie = prof.includes("fonctionnaire") || prof.includes("salarié") ||
                       prof.includes("agent") || prof.includes("enseignant") ||
                       prof.includes("infirmier") || prof.includes("médecin");
    setVisible("conjoint_date_embauche", estSalarie);
  }
  watch("conjoint_profession", syncConjointEmbauche);
  syncConjointEmbauche();

  // ============================================================
  // SUGGESTIONS PROFESSION CONJOINT selon sexe client
  // ============================================================
  function updateConjointProfSuggestions() {
    const sexe = getValue("sexe");
    // Si client masculin → conjoint est féminin → suggestions féminines
    const suggestions = sexe === "M" ? PROFESSIONS_CONJOINT_F :
                        sexe === "F" ? PROFESSIONS_CONJOINT_M : PROFESSIONS_COURANTES;
    attachDatalist("conjoint_profession", suggestions);
  }
  watch("sexe", () => { syncConjoint(); updateConjointProfSuggestions(); });
  updateConjointProfSuggestions();

  // ============================================================
  // NOMBRE D'ENFANTS → prénoms
  // ============================================================
  function syncEnfants() {
    const nb = parseInt(getValue("nombre_enfants") || "0", 10);
    setVisible("enfants_noms", nb > 0);
  }
  watch("nombre_enfants", syncEnfants);
  syncEnfants();

  // ============================================================
  // AUTRE NATIONALITÉ → champ texte
  // ============================================================
  function syncAutreNationalite() {
    setVisible("autre_nationalite", getBoolValue("a_autre_nationalite") === true);
  }
  watch("a_autre_nationalite", syncAutreNationalite);
  syncAutreNationalite();

  // ============================================================
  // CATÉGORIE CLIENT → champs spécifiques
  // ============================================================
  function syncCategorie() {
    const cat = getValue("categorie_client");
    setVisible("categorie_client_autre", cat === "AUTRE");
    setVisible("activite_commerciale", cat === "ACTIVITE_COMMERCIALE");
    const avecEmployeur = ["SALARIE_PRIVE","SALARIE_PUBLIC","PROFESSION_LIBERALE"].includes(cat);
    setVisible("employeur", avecEmployeur);
    setVisible("adresse_employeur", avecEmployeur || cat === "ACTIVITE_COMMERCIALE");
    setVisible("poste_occupe", avecEmployeur);
    setVisible("date_embauche", cat === "SALARIE_PRIVE" || cat === "SALARIE_PUBLIC");
    setVisible("revenu_mensuel", avecEmployeur || cat === "RETRAITE");
  }
  watch("categorie_client", syncCategorie);
  syncCategorie();

  // Autres revenus : n'afficher les montants que si le client en déclare.
  const AUTRES_REVENUS = [
    "revenus_immobiliers", "revenus_mobiliers", "recettes_commerciales",
    "indemnites", "autres_revenus",
  ];
  function syncAutresRevenus() {
    const hasOtherIncome = getBoolValue("revenus_ailleurs") === true;
    setGroupVisible(AUTRES_REVENUS, hasOtherIncome);
  }
  watch("revenus_ailleurs", syncAutresRevenus);
  syncAutresRevenus();

  // ============================================================
  // MANDAT D'ADMINISTRATEUR / ACTIONNAIRE / PROCURATION
  // ============================================================
  function syncAdministrateur() {
    setVisible("societes_administrees", getBoolValue("mandat_administrateur") === true);
  }
  watch("mandat_administrateur", syncAdministrateur);
  syncAdministrateur();

  function syncActionnaire() {
    setVisible("societes_actionnaire", getBoolValue("est_actionnaire") === true);
  }
  watch("est_actionnaire", syncActionnaire);
  syncActionnaire();

  function syncProcuration() {
    setVisible("procuration_details", getBoolValue("procuration_donnee") === true);
  }
  watch("procuration_donnee", syncProcuration);
  syncProcuration();

  // ============================================================
  // ENTRÉE EN RELATION → parrainage / seconde pièce
  // ============================================================
  function syncEntreeRelation() {
    setVisible("parrainage_tiers", getBoolValue("entree_relation_directe") === false);
  }
  watch("entree_relation_directe", syncEntreeRelation);
  syncEntreeRelation();

  function syncModeRelation() {
    const aDistance = getValue("mode_entree_relation") === "A_DISTANCE";
    setVisible("type_piece_secondaire", aDistance);
  }
  watch("mode_entree_relation", syncModeRelation);
  syncModeRelation();

  // ============================================================
  // NOM DE JEUNE FILLE → visible seulement si sexe = F
  // ============================================================
  function syncNomJeuneFille() {
    setVisible("nom_jeune_fille", getValue("sexe") === "F");
  }
  watch("sexe", syncNomJeuneFille);
  syncNomJeuneFille();

  // ============================================================
  // SUGGESTIONS DATALIST
  // ============================================================

  // Pays
  attachDatalist("pays_naissance", PAYS_AFRIQUE);
  attachDatalist("pays_residence", PAYS_AFRIQUE);
  attachDatalist("conjoint_pays_naissance", PAYS_AFRIQUE);
  attachDatalist("pm_siege_social", [...VILLES_BF, "Ouagadougou, Burkina Faso", "Bobo-Dioulasso, Burkina Faso"]);

  // Villes
  attachDatalist("ville_residence", VILLES_BF);
  attachDatalist("lieu_naissance", VILLES_MONDE);
  attachDatalist("conjoint_ville_naissance", VILLES_MONDE);
  attachDatalist("piece_delivree_a", VILLES_BF);
  attachDatalist("conjoint_piece_delivree_a", VILLES_BF);

  // Nationalité
  attachDatalist("nationalite", ["Burkinabè","Ivoirien(ne)","Malien(ne)","Nigérien(ne)","Sénégalais(e)","Ghanéen(ne)","Béninois(e)","Togolais(e)","Camerounais(e)","Français(e)","Autre"]);
  attachDatalist("autre_nationalite", ["Ivoirien(ne)","Malien(ne)","Nigérien(ne)","Sénégalais(e)","Ghanéen(ne)","Béninois(e)","Togolais(e)","Française","Camerounais(e)"]);

  // Autorité de délivrance
  attachDatalist("piece_delivree_par", AUTORITES_DELIVRANCE);
  attachDatalist("conjoint_piece_delivree_par", AUTORITES_DELIVRANCE);

  // Professions
  attachDatalist("profession", PROFESSIONS_COURANTES);

  // Tranche revenu conjoint
  attachDatalist("conjoint_tranche_revenu", TRANCHES_REVENU);

  // Nature versement
  attachDatalist("nature_versement_initial", NATURES_VERSEMENT);

  // Régime matrimonial
  attachDatalist("regime_matrimonial", REGIMES_MATRIMONIAUX);

  // Villes entreprise
  attachDatalist("pm_secteur_rue", ["Secteur 1","Secteur 2","Secteur 3","Secteur 4","Secteur 5","Secteur 6","Secteur 7","Secteur 8","Secteur 9","Secteur 10","Secteur 15","Secteur 20","Secteur 22","Secteur 25","Secteur 30","Zone industrielle","Zone commerciale"]);

  // Préremplissages par défaut
  setInputValue("pays_naissance", "Burkina Faso");
  setInputValue("pays_residence", "Burkina Faso");
  setInputValue("nationalite", "Burkinabè");
  setInputValue("piece_delivree_par", "ONI");
  setInputValue("ville_residence", "Ouagadougou");

  // ============================================================
  // Navigation latérale active (IntersectionObserver)
  // ============================================================
  const links = Array.from(form.querySelectorAll(".rail-link"));
  const sections = links
    .map((link) => document.getElementById(link.getAttribute("href").slice(1)))
    .filter(Boolean);

  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting || entry.target.hidden) return;
          links.forEach((link) => {
            link.classList.toggle(
              "active",
              link.getAttribute("href") === `#${entry.target.id}`
            );
          });
        });
      },
      { rootMargin: "-15% 0px -70% 0px" }
    );
    sections.forEach((section) => observer.observe(section));
  }

  // ============================================================
  // Focus résumé d'erreurs
  // ============================================================
  const errorSummary = form.querySelector(".error-summary");
  if (errorSummary) errorSummary.focus();
})();


// ============================================================
// 2. FORMULAIRE GESTIONNAIRE : champ "Autre agence"
// ============================================================
(() => {
  const agenceListe = document.getElementById("id_agence_liste");
  const wrapAutre = document.getElementById("id_agence_autre")?.closest(".field-wrap");
  if (!agenceListe || !wrapAutre) return;

  const syncAutre = () => {
    const show = agenceListe.value === "autre";
    wrapAutre.hidden = !show;
    const input = wrapAutre.querySelector("input");
    if (input) input.disabled = !show;
  };

  agenceListe.addEventListener("change", syncAutre);
  syncAutre();
})();
