# BCB — Ouverture de compte · Backlog des améliorations

> Document de suivi des points à traiter en priorité sur la nouvelle branche de développement.
> Mis à jour le 12/11/2026.

---

## 🔴 Bloquants / Bugs confirmés

### 1. Section consentements invisible sur le formulaire
- **Symptôme** : `document.querySelectorAll('.form-section').length` retourne `0` sur la page de modification d'un dossier existant.
- **Diagnostic** : La page retournée n'est pas le formulaire (`/modifier/`) — probablement une redirection silencieuse vers la page de détail ou la page de prévisualisation.
- **À vérifier** : La vue `dossier_edit` redirige si `dossier.signe_le` est renseigné. Vérifier aussi que l'utilisateur est bien `cree_par` du dossier.
- **Piste** : Ajouter un log ou un message flash pour indiquer la raison de la redirection si elle se produit.

### 2. Workflow "Prévisualiser → Corriger" sur dossier existant
- La session stocke les données POST sous la clé `preview_data_{pk}` (UUID).
- Après correction, si l'utilisateur revient au formulaire via "← Corriger", vérifier que le formulaire est bien pré-rempli avec les données modifiées (pas les données de la base).
- **À tester** : cycle complet modifier → prévisualiser → corriger → modifier → prévisualiser → valider.

---

## 🟠 Priorité haute

### 3. Formulaires commerciaux — conformité avec le PDF officiel
- Les formulaires commerciaux HTML (`_comm_kyc_pm.html`, `_comm_cover.html`, etc.) ont été construits à partir du scan PDF — les coordonnées de certains champs sont à recalibrer en imprimant un dossier de test et en comparant avec l'original papier.
- En particulier : `_comm_specimen.html` (carton de spécimen de signature) et `_comm_convention.html` (articles 1-12) nécessitent une relecture avec un exemplaire papier.
- **Action** : Imprimer un dossier commercial de test et annoter les écarts.

### 4. Nomenclature des dossiers
- Référence actuelle : `BCB-{ANNÉE}-{UUID8}` → ex. `BCB-2026-A3F7E12C`
- Proposition discutée : intégrer le numéro CNIB quand disponible → `BCB-2026-B1234567`
- **Problème** : Le CNIB n'est pas toujours saisi au moment de la création du brouillon.
- **Solution envisagée** : Générer la référence finale avec le CNIB au moment de la génération (pas de la création), et garder l'UUID pour les brouillons sans CNIB.
- **Décision à prendre** : Inclure nom/prénom dans la référence ? (non recommandé — confidentialité).

### 5. Formulaires particulier — alignement fin avec le PDF officiel
- **F2 (CREDITINFO)** : Le PDF officiel n'a pas de section "Formule(s) lue(s) et confirmée(s)" — à supprimer ou masquer à l'impression.
- **F4 (Localisation)** : La section III (2e personne à prévenir) a été ajoutée — vérifier l'alignement avec le PDF papier en termes d'espace disponible.
- **F3 (KYC) page 1** : Les cases "Fiche de Création / Mise à jour" et "Consultation CIP / AMPLITUDE" sont réservées à l'usage interne — les laisser vides est correct.

### 6. Champs manquants dans les formulaires imprimés
- Vérifier que **tous les champs saisis** apparaissent bien sur au moins un formulaire imprimable.
- Champs à vérifier spécifiquement : `telephone_bureau`, `boite_postale`, `rccm_particulier`, `ifu`, `nom_pere`, `conjoint_nom_mere`, `conjoint_piece_delivree_par`.
- **Action** : Créer un dossier de test avec tous les champs remplis, générer, et cocher chaque champ dans le tableau de correspondance.

---

## 🟡 Priorité moyenne

### 7. Fluidification de la saisie — suite
- **Professions** : La liste de suggestions (`datalist`) couvre les cas courants. Envisager une liste plus complète issue du répertoire des professions CEDEAO.
- **Secteurs de Ouagadougou** : Ajouter les secteurs de 1 à 55 en numérique dans la datalist du champ `secteur`.
- **Autofill téléphone** : Format BF (+226 XX XX XX XX) — ajouter un masque de saisie ou une validation de format.
- **Formulaire commercial** : Le champ `pm_capital_social` accepte 0 par défaut — envisager de le laisser vide plutôt que 0 pour éviter les confusions.
- **Date d'embauche** : Masquer si catégorie = Retraité, Étudiant, Ménagère, Sans emploi.

### 8. Plan de repérage (F5)
- Actuellement : cadre vide à remplir à la main avec adresse pré-remplie en en-tête.
- **Amélioration envisagée** : Intégrer une carte statique (OpenStreetMap / API) centrée sur l'adresse du client si les coordonnées GPS sont disponibles.
- **Contrainte** : Nécessite une connexion internet au moment de l'impression + intégration d'une API cartographique.
- **Décision à prendre** : Laisser tel quel (dessin manuel) ou intégrer la carte ?

### 9. PDF côté serveur (WeasyPrint)
- WeasyPrint est installé mais pas encore utilisé.
- **Usage envisagé** : Bouton "Télécharger en PDF" sur la page d'impression pour générer un PDF côté serveur identique à ce qu'on voit à l'écran.
- Avantage : indépendant du navigateur (rendu identique sur tous les postes d'agence).
- **Action** : Créer une vue `dossier_pdf(request, pk)` qui utilise WeasyPrint sur le même template HTML.

### 10. Gestion du stock des dossiers commerciaux
- Les dossiers commerciaux ne génèrent plus de PDF figé (`pdf_fige`) — le champ `BinaryField` est présent en base mais jamais rempli.
- **Nettoyage à faire** : Supprimer `pdf_fige` du modèle (migration) ou le réutiliser pour le PDF WeasyPrint.

### 11. Recherche client améliorée
- Actuellement : recherche par numéro de pièce uniquement.
- **À ajouter** : Recherche par nom, prénom, raison sociale dans la vue `recherche_client`.
- Afficher un résumé plus complet (type de compte, agence, date dernière modification).

---

## 🟢 Améliorations à long terme

### 12. Tableau de bord Admin
- Vue synthétique : nombre de dossiers par statut, par agence, par gestionnaire.
- Statistiques : dossiers créés / générés / signés par période.

### 13. Export Excel / CSV
- Export de la liste des dossiers filtrés pour l'Admin.
- Utile pour les reportings réglementaires.

### 14. Notifications / alertes
- Alerte si un dossier généré n'est pas signé après N jours.
- Alerte si la pièce d'identité du client expire dans moins de 30 jours.

### 15. Multi-agence pour l'Admin
- Permettre à l'Admin de filtrer les dossiers par agence.
- Actuellement l'Admin voit tous les dossiers sans filtre d'agence.

### 16. Déploiement production
- Variables d'environnement à configurer : `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DB_PASSWORD`, `DJANGO_DEBUG=false`.
- Vérifier la configuration HTTPS (`SECURE_SSL_REDIRECT`, `HSTS`).
- Configurer `STATIC_ROOT` et lancer `collectstatic`.
- Envisager un reverse proxy (Nginx) devant Gunicorn.

---

## ✅ Déjà livré (cette session)

- Logo BCB harmonisé dans la topbar et les formulaires imprimables
- Topbar refaite aux couleurs BCB teal
- Champs conditionnels : conjoint (célibataire), enfants, autre nationalité, procuration, sociétés, parrainage, seconde pièce, nom de jeune fille, date embauche conjoint
- Suggestions datalist : pays, villes BF, professions, autorités de délivrance, tranche revenu, nature versement, régime matrimonial
- Préremplissages : Burkina Faso, Burkinabè, ONI, Ouagadougou
- Professions conjoint adaptées au sexe du client
- Workflow generate-first : Prévisualiser → Corriger ou Valider (sans sauvegarde intermédiaire)
- Résumé d'erreurs déplacé dans la colonne contenu (plus de chevauchement avec le rail)
- Formulaires commerciaux HTML complets (9 formulaires, ~20 pages)
- Section consentements CREDITINFO visible pour les deux types de compte
- Renommage "Recueil" → "Ouverture" dans toutes les interfaces
- Gestion des gestionnaires : création, modification, rattachement agence, activation/désactivation
- Synthèse lisibilité améliorée (tailles de police, contrastes, couleurs BCB)
- Plan de repérage enrichi avec adresse pré-remplie
