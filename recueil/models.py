"""Modèles de données du Recueil d'informations BCB (Particulier & Commercial)."""
import uuid

from django.db import models
from django.conf import settings


class Agence(models.Model):
    """Agence BCB avec son numéro officiel."""
    nom = models.CharField("Nom de l'agence", max_length=150)
    numero = models.CharField("Numéro d'agence", max_length=20, unique=True)
    ville = models.CharField("Ville", max_length=80, default="Ouagadougou")
    active = models.BooleanField("Active", default=True)

    class Meta:
        ordering = ["numero"]
        verbose_name = "Agence"
        verbose_name_plural = "Agences"

    def __str__(self):
        return f"{self.numero} — {self.nom}"

    def label_complet(self):
        return f"{self.nom} ({self.numero})"


class DossierClient(models.Model):
    """Dossier d'ouverture unique représentant les informations recueillies auprès du client."""

    class TypeCompte(models.TextChoices):
        PARTICULIER = "PARTICULIER", "Particulier (Personne Physique)"
        COMMERCIAL = "COMMERCIAL", "Commercial (Entreprise / Personne Morale)"

    class FormuleProduit(models.TextChoices):
        COURANT = "COURANT", "Compte Courant"
        EPARGNE = "EPARGNE", "Compte Épargne"
        CHEQUE = "CHEQUE", "Compte Chèque"
        COMMERCIAL_ORD = "COMMERCIAL", "Compte Courant Commercial"
        AUTRE = "AUTRE", "Autre formule"

    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon (En cours)"
        CREE = "CREE", "Créé"
        GENERE = "GENERE", "Généré & Prêt pour impression"
        DESACTIVE = "DESACTIVE", "Désactivé"

    class CategorieClient(models.TextChoices):
        SALARIE_PRIVE = "SALARIE_PRIVE", "Salarié du privé"
        SALARIE_PUBLIC = "SALARIE_PUBLIC", "Salarié du public"
        ETUDIANT = "ETUDIANT", "Étudiant"
        PROFESSION_LIBERALE = "PROFESSION_LIBERALE", "Profession libérale"
        RETRAITE = "RETRAITE", "Retraité"
        ACTIVITE_COMMERCIALE = "ACTIVITE_COMMERCIALE", "Activité commerciale"
        AUTRE = "AUTRE", "Autre"

    class StatutLogement(models.TextChoices):
        LOCATAIRE = "LOCATAIRE", "Locataire"
        PROPRIETAIRE = "PROPRIETAIRE", "Propriétaire"
        AUTRE = "AUTRE", "Autre"

    class JustificatifDomicile(models.TextChoices):
        FACTURE_EAU_ELECTRICITE = "FACTURE_EAU_ELECTRICITE", "Facture d'eau ou d'électricité"
        CERTIFICAT_RESIDENCE = "CERTIFICAT_RESIDENCE", "Certificat de résidence"
        FACTURE_TELEPHONE = "FACTURE_TELEPHONE", "Facture de téléphone fixe"
        CONTRAT_BAIL = "CONTRAT_BAIL", "Contrat de bail"
        ATTESTATION_PRESENCE = "ATTESTATION_PRESENCE", "Attestation de présence au corps"
        AUTRE = "AUTRE", "Autre"

    class ModeEntreeRelation(models.TextChoices):
        EN_PERSONNE = "EN_PERSONNE", "Rencontré en personne"
        A_DISTANCE = "A_DISTANCE", "Contacté à distance"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField("Référence dossier", max_length=30, unique=True)
    type_compte = models.CharField(max_length=20, choices=TypeCompte.choices, default=TypeCompte.PARTICULIER)
    formule_produit = models.CharField(max_length=30, choices=FormuleProduit.choices, default=FormuleProduit.COURANT)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.BROUILLON)

    # PDF figé à la génération : ce que le client signe ne change plus ensuite.
    pdf_fige = models.BinaryField("PDF généré (figé)", null=True, blank=True, editable=False)

    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dossiers_crees",
        verbose_name="Gestionnaire créateur",
    )
    agence_snapshot = models.CharField("Agence à la création", max_length=120, blank=True)
    charge_affaires_snapshot = models.CharField(
        "Chargé d'affaires à la création", max_length=150, blank=True,
    )
    derniere_impression_le = models.DateTimeField(
        "Dernière impression", null=True, blank=True,
    )
    derniere_impression_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dossiers_imprimes",
        verbose_name="Dernière impression par",
    )
    signe_le = models.DateTimeField("Date de signature", null=True, blank=True)
    signe_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dossiers_signes",
        verbose_name="Signé par",
    )
    # Suppression logique : le brouillon reste en BD avec statut DESACTIVE
    supprime_le = models.DateTimeField("Supprimé le", null=True, blank=True)
    supprime_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dossiers_supprimes",
        verbose_name="Supprimé par",
    )

    # =========================================================================
    # 1. IDENTITÉ DU CLIENT / MANDATAIRE (PERSONNE PHYSIQUE)
    # =========================================================================
    nom = models.CharField("Nom de famille", max_length=100)
    prenoms = models.CharField("Prénom(s)", max_length=150)
    nom_jeune_fille = models.CharField("Nom de jeune fille", max_length=100, blank=True)
    # Pas de valeur par défaut : le sexe doit être choisi explicitement.
    sexe = models.CharField(
        "Sexe", max_length=1, blank=True, default="",
        choices=[("M", "Masculin"), ("F", "Féminin")],
    )
    # Un brouillon peut être ouvert avant d'avoir toutes les informations.
    # Les dossiers à générer sont validés par DossierClientForm.
    date_naissance = models.DateField("Date de naissance", null=True, blank=True)
    lieu_naissance = models.CharField("Lieu de naissance", max_length=100)
    pays_naissance = models.CharField("Pays de naissance", max_length=80, default="Burkina Faso")
    nationalite = models.CharField("Nationalité", max_length=60, default="Burkinabè")
    nom_pere = models.CharField("Nom et prénom(s) du père", max_length=150, blank=True)
    nom_mere = models.CharField("Nom complet de la mère", max_length=150, blank=True)

    # Pièce d'identité
    type_piece = models.CharField(
        "Nature pièce", max_length=30, default="CNIB",
        choices=[("CNIB", "CNIB"), ("PASSEPORT", "Passeport"), ("CARTE_SEJOUR", "Carte de séjour"), ("AUTRE", "Autre")],
    )
    type_piece_secondaire = models.CharField(
        "Seconde pièce d'identité", max_length=30, blank=True,
        choices=[("CNIB", "CNIB"), ("PASSEPORT", "Passeport"), ("CARTE_SEJOUR", "Carte de séjour"), ("AUTRE", "Autre")],
    )
    # Clé de recherche du client : indexée.
    numero_piece = models.CharField("Numéro de pièce", max_length=60, db_index=True)
    piece_delivree_le = models.DateField("Délivrée le", null=True, blank=True)
    piece_delivree_a = models.CharField("Lieu de délivrance", max_length=100, blank=True)
    piece_expire_le = models.DateField("Date d'expiration", null=True, blank=True)
    piece_delivree_par = models.CharField("Autorité de délivrance", max_length=80, default="ONI", blank=True)

    # Fiscalité
    ifu = models.CharField("Numéro IFU", max_length=50, blank=True)
    rccm_particulier = models.CharField("Numéro RCCM (si commerçant individuel)", max_length=60, blank=True)

    # =========================================================================
    # 2. LOCALISATION GÉOGRAPHIQUE & COORDONNÉES
    # =========================================================================
    ville_residence = models.CharField("Ville de résidence", max_length=80, default="Ouagadougou")
    pays_residence = models.CharField("Pays de résidence", max_length=80, default="Burkina Faso")
    secteur = models.CharField("Secteur", max_length=40, blank=True)
    quartier = models.CharField("Quartier", max_length=100, blank=True)
    rue = models.CharField("Rue / Avenue", max_length=100, blank=True)
    porte = models.CharField("Porte / Villa / Lot", max_length=60, blank=True)
    repere_proximite = models.CharField("Points de repère de proximité", max_length=200, blank=True)
    adresse = models.TextField("Adresse complète", blank=True)
    resident_bf = models.BooleanField("Résident au Burkina Faso", null=True, blank=True)
    statut_logement = models.CharField(
        "Statut du logement", max_length=20, blank=True,
        choices=StatutLogement.choices,
    )
    justificatif_domicile = models.CharField(
        "Justificatif de domicile fourni", max_length=30, blank=True,
        choices=JustificatifDomicile.choices,
    )
    a_autre_nationalite = models.BooleanField(
        "Possède une autre nationalité", null=True, blank=True,
    )
    autre_nationalite = models.CharField("Autre nationalité", max_length=80, blank=True)

    telephone = models.CharField("Téléphone mobile principal", max_length=30)
    telephone_secondaire = models.CharField("Téléphone secondaire", max_length=30, blank=True)
    telephone_domicile = models.CharField("Téléphone domicile fixe", max_length=30, blank=True)
    telephone_bureau = models.CharField("Téléphone bureau", max_length=30, blank=True)
    email = models.EmailField("Adresse email", blank=True)
    boite_postale = models.CharField("Boîte postale", max_length=60, blank=True)

    # =========================================================================
    # 3. SITUATION PROFESSIONNELLE & EMPLOYEUR
    # =========================================================================
    categorie_client = models.CharField(
        "Catégorie professionnelle", max_length=30, blank=True,
        choices=CategorieClient.choices,
    )
    categorie_client_autre = models.CharField(
        "Autre catégorie professionnelle", max_length=120, blank=True,
    )
    activite_commerciale = models.CharField(
        "Activité commerciale exercée", max_length=200, blank=True,
    )
    profession = models.CharField("Profession / Titre", max_length=120)
    employeur = models.CharField("Employeur / Établissement", max_length=150, blank=True)
    adresse_employeur = models.CharField("Adresse du lieu de travail", max_length=150, blank=True)
    poste_occupe = models.CharField("Poste occupé", max_length=100, blank=True)
    date_embauche = models.DateField("Date d'embauche", null=True, blank=True)
    revenu_mensuel = models.DecimalField("Salaire net mensuel (FCFA)", max_digits=14, decimal_places=2, null=True, blank=True)

    # =========================================================================
    # 4. REVENUS, OPÉRATIONS & RELATION BANCAIRE
    # =========================================================================
    revenus_immobiliers = models.DecimalField(
        "Revenus immobiliers (FCFA)", max_digits=14, decimal_places=2, null=True, blank=True,
    )
    revenus_mobiliers = models.DecimalField(
        "Revenus mobiliers (FCFA)", max_digits=14, decimal_places=2, null=True, blank=True,
    )
    recettes_commerciales = models.DecimalField(
        "Recettes d'activités commerciales (FCFA)", max_digits=14, decimal_places=2, null=True, blank=True,
    )
    indemnites = models.DecimalField(
        "Indemnités (FCFA)", max_digits=14, decimal_places=2, null=True, blank=True,
    )
    autres_revenus = models.DecimalField(
        "Autres revenus (FCFA)", max_digits=14, decimal_places=2, null=True, blank=True,
    )
    montant_versement_initial = models.DecimalField(
        "Montant du versement à l'ouverture (FCFA)", max_digits=14, decimal_places=2, null=True, blank=True,
    )
    nature_versement_initial = models.CharField(
        "Nature du versement à l'ouverture", max_length=200, blank=True,
    )
    operations_habituelles = models.TextField(
        "Types d'opérations et volumes habituels", blank=True,
    )
    mandat_administrateur = models.BooleanField(
        "Mandat d'administrateur dans une société", null=True, blank=True,
    )
    societes_administrees = models.TextField(
        "Sociétés administrées", blank=True,
    )
    est_actionnaire = models.BooleanField(
        "Actionnaire dans une société", null=True, blank=True,
    )
    societes_actionnaire = models.TextField(
        "Sociétés dans lesquelles le client est actionnaire", blank=True,
    )
    numero_compte_bcb_existant = models.CharField(
        "Numéro de compte BCB déjà ouvert", max_length=60, blank=True,
    )
    autres_comptes_bancaires = models.TextField(
        "Autres comptes bancaires et banques", blank=True,
    )
    client_introduit_par = models.CharField(
        "Client introduit par", max_length=200, blank=True,
    )
    entree_relation_directe = models.BooleanField(
        "Entrée en relation directe", null=True, blank=True,
    )
    parrainage_tiers = models.CharField(
        "Identité et qualité du tiers parrain", max_length=200, blank=True,
    )
    mode_entree_relation = models.CharField(
        "Mode de contact du client", max_length=20, blank=True,
        choices=ModeEntreeRelation.choices,
    )
    procuration_donnee = models.BooleanField(
        "Procuration donnée", null=True, blank=True,
    )
    procuration_details = models.CharField(
        "Détails de la procuration", max_length=200, blank=True,
    )

    # =========================================================================
    # 5. FAMILLE & PERSONNES À PRÉVENIR (URGENCE)
    # =========================================================================
    # Pas de valeur par défaut : à choisir explicitement.
    situation_matrimoniale = models.CharField(
        "Situation matrimoniale", max_length=30, blank=True, default="",
        choices=[
            ("CELIBATAIRE", "Célibataire"),
            ("MARIE_MONO", "Marié(e) - Monogamie"),
            ("MARIE_POLY", "Marié(e) - Polygamie"),
            ("DIVORCE", "Divorcé(e)"),
            ("VEUF", "Veuf / Veuve"),
        ],
    )
    regime_matrimonial = models.CharField("Régime matrimonial (Biens communs / séparés)", max_length=60, blank=True)
    conjoint_nom = models.CharField("Nom complet du conjoint", max_length=150, blank=True)
    conjoint_contact = models.CharField("Contact téléphonique du conjoint", max_length=30, blank=True)
    conjoint_date_naissance = models.DateField("Conjoint — date de naissance", null=True, blank=True)
    conjoint_ville_naissance = models.CharField("Conjoint — ville de naissance", max_length=100, blank=True)
    conjoint_pays_naissance = models.CharField("Conjoint — pays de naissance", max_length=80, blank=True)
    conjoint_nom_mere = models.CharField("Conjoint — nom de la mère", max_length=150, blank=True)
    conjoint_type_piece = models.CharField(
        "Conjoint — type de pièce d'identité", max_length=30, blank=True,
        choices=[("CNIB", "CNIB"), ("PASSEPORT", "Passeport"), ("CARTE_SEJOUR", "Carte de séjour"), ("AUTRE", "Autre")],
    )
    conjoint_numero_piece = models.CharField("Conjoint — numéro de pièce", max_length=60, blank=True)
    conjoint_piece_delivree_a = models.CharField("Conjoint — lieu de délivrance", max_length=100, blank=True)
    conjoint_piece_delivree_le = models.DateField("Conjoint — pièce délivrée le", null=True, blank=True)
    conjoint_piece_delivree_par = models.CharField("Conjoint — autorité de délivrance", max_length=80, blank=True)
    conjoint_piece_expire_le = models.DateField("Conjoint — pièce expirant le", null=True, blank=True)
    conjoint_profession = models.CharField("Conjoint — profession", max_length=120, blank=True)
    conjoint_date_embauche = models.DateField("Conjoint — date d'embauche", null=True, blank=True)
    conjoint_tranche_revenu = models.CharField("Conjoint — tranche de revenu", max_length=80, blank=True)
    nombre_enfants = models.PositiveSmallIntegerField("Nombre d'enfants", null=True, blank=True)
    enfants_noms = models.TextField(
        "Prénoms des enfants",
        blank=True,
        help_text="Un prénom par ligne (jusqu'à cinq prénoms sur le formulaire F1).",
    )

    # Contacts d'urgence (propagés dans Renseignements & Localisation)
    urgence_nom_1 = models.CharField("Urgence 1 - Nom et prénoms", max_length=150, blank=True)
    urgence_tel_1 = models.CharField("Urgence 1 - Téléphone", max_length=30, blank=True)
    urgence_prof_1 = models.CharField("Urgence 1 - Profession", max_length=120, blank=True)
    urgence_lieu_travail_1 = models.CharField("Urgence 1 - Lieu de travail", max_length=150, blank=True)
    urgence_adresse_1 = models.CharField("Urgence 1 - Secteur/Quartier", max_length=120, blank=True)

    urgence_nom_2 = models.CharField("Urgence 2 - Nom et prénoms", max_length=150, blank=True)
    urgence_tel_2 = models.CharField("Urgence 2 - Téléphone", max_length=30, blank=True)
    urgence_prof_2 = models.CharField("Urgence 2 - Profession", max_length=120, blank=True)
    urgence_lieu_travail_2 = models.CharField("Urgence 2 - Lieu de travail", max_length=150, blank=True)
    urgence_adresse_2 = models.CharField("Urgence 2 - Secteur/Quartier", max_length=120, blank=True)

    # =========================================================================
    # 6. ENTREPRISE / PERSONNE MORALE (SI COMPTE COMMERCIAL)
    # =========================================================================
    pm_raison_sociale = models.CharField("Raison sociale", max_length=150, blank=True)
    pm_sigle = models.CharField("Sigle ou nom commercial", max_length=60, blank=True)
    pm_forme_juridique = models.CharField(
        "Forme juridique", max_length=50, blank=True,
        choices=[
            ("SARL", "SARL"), ("SA", "SA"), ("SAS", "SAS"), ("ONG", "ONG"),
            ("EI", "Entreprise Individuelle"), ("AUTRE", "Autre"),
        ],
    )
    pm_activite_principale = models.CharField("Objet social ou activité principale", max_length=200, blank=True)
    pm_numero_rccm = models.CharField("N° RCCM Entreprise", max_length=80, blank=True)
    pm_ifu = models.CharField("N° IFU Entreprise", max_length=50, blank=True)
    pm_siege_social = models.CharField("Siège social (Ville/Pays)", max_length=120, blank=True)
    pm_secteur_rue = models.CharField("Secteur / Rue Entreprise", max_length=120, blank=True)
    pm_telephone_bureau = models.CharField("Téléphone bureau", max_length=30, blank=True)
    pm_email = models.EmailField("Email société", blank=True)
    pm_capital_social = models.DecimalField("Capital social (FCFA)", max_digits=16, decimal_places=2, default=0, blank=True)
    pm_chiffre_affaires = models.DecimalField("Chiffre d'affaires annuel estimé (FCFA)", max_digits=16, decimal_places=2, default=0, blank=True)

    # Actionnaires principaux
    pm_actionnaire_1 = models.CharField("Actionnaire 1 (Nom et %)", max_length=150, blank=True)
    pm_actionnaire_2 = models.CharField("Actionnaire 2 (Nom et %)", max_length=150, blank=True)

    # Fonction du mandataire
    pm_fonction_mandataire = models.CharField("Fonction du mandataire", max_length=100, default="Gérant / Directeur Général", blank=True)

    # =========================================================================
    # 7. CONFORMITÉ & DÉCLARATIONS DU CLIENT
    # =========================================================================
    # Trois états : None = non renseigné (rien n'est imprimé), True = Oui, False = Non.
    est_us_person = models.BooleanField("Est une US Person (FATCA)", null=True, blank=True)
    est_ppe = models.BooleanField("Personne Politiquement Exposée (PPE)", null=True, blank=True)
    levee_secret_bancaire = models.BooleanField("Autorise la levée du secret bancaire", null=True, blank=True)

    # Réponses explicites du client aux déclarations du formulaire F2.
    f2_transmission_credit = models.BooleanField(
        "F2 — Autorise la transmission des informations de crédit",
        null=True,
        blank=True,
    )
    f2_partage_credit = models.BooleanField(
        "F2 — Autorise la communication aux établissements membres de l'UMOA",
        null=True,
        blank=True,
    )
    f2_exclusion_depots = models.BooleanField(
        "F2 — Comprend l'exclusion des informations sur les dépôts",
        null=True,
        blank=True,
    )
    f2_limite_anciennete = models.BooleanField(
        "F2 — Comprend la limite d'ancienneté de cinq ans",
        null=True,
        blank=True,
    )
    f2_duree_conservation = models.BooleanField(
        "F2 — Comprend la durée de conservation des informations",
        null=True,
        blank=True,
    )
    f2_droit_acces = models.BooleanField(
        "F2 — Comprend son droit d'accès et de contestation",
        null=True,
        blank=True,
    )
    f2_droit_rapport = models.BooleanField(
        "F2 — Comprend son droit à un rapport de crédit gratuit",
        null=True,
        blank=True,
    )
    creditinfo_confirme = models.BooleanField(
        "Le client a lu et confirmé les réponses CREDITINFO",
        null=True,
        blank=True,
    )

    cree_le = models.DateTimeField(auto_now_add=True)
    maj_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-maj_le"]
        verbose_name = "Dossier Client"
        verbose_name_plural = "Dossiers Clients"

    def __str__(self):
        if self.type_compte == self.TypeCompte.COMMERCIAL and self.pm_raison_sociale:
            return f"{self.pm_raison_sociale} ({self.reference})"
        return f"{self.nom} {self.prenoms} ({self.reference})"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    nom_affiche = models.CharField("Nom affiché", max_length=150, blank=True)
    agence = models.ForeignKey(
        Agence,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gestionnaires",
        verbose_name="Agence",
    )

    def __str__(self):
        return self.nom_affiche or self.user.get_username()

    @property
    def agence_nom(self):
        return self.agence.nom if self.agence else ""

    @property
    def agence_numero(self):
        return self.agence.numero if self.agence else ""


class DossierAuditEvent(models.Model):
    class Action(models.TextChoices):
        CREATION = "CREATION", "Création"
        MODIFICATION = "MODIFICATION", "Modification"
        GENERATION = "GENERATION", "Génération"
        IMPRESSION = "IMPRESSION", "Impression"
        CONSULTATION = "CONSULTATION", "Consultation"
        SIGNATURE = "SIGNATURE", "Signature"
        REUTILISATION = "REUTILISATION", "Réutilisation"
        RECHERCHE_CLIENT = "RECHERCHE_CLIENT", "Recherche client"
        SUPPRESSION = "SUPPRESSION", "Suppression (brouillon)"

    dossier = models.ForeignKey(
        DossierClient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evenements_audit",
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evenements_dossier",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    date = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "Événement d'audit"
        verbose_name_plural = "Événements d'audit"