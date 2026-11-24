import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.forms.models import model_to_dict
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .forms import (
    DossierClientForm,
    DossierCommercialForm,
    DossierParticulierForm,
    GestionnairePasswordForm,
    GestionnaireUserForm,
    UserProfileForm,
    build_dossier_reference,
    new_dossier_reference,
)
from .models import ADAccessRequest, Agence, DossierAuditEvent, DossierClient, UserProfile
from .permissions import (
    ADMIN_GROUP,
    admin_required,
    has_role,
    manager_or_admin_required,
    manager_required,
)


FORM_SECTIONS = (
    ("compte", "Compte & profil", ("type_compte", "formule_produit")),
    ("identite", "Identité & pièce", (
        "nom", "prenoms", "nom_jeune_fille", "sexe", "date_naissance",
        "lieu_naissance", "pays_naissance", "nationalite", "nom_pere",
        "nom_mere", "type_piece", "type_piece_secondaire", "numero_piece", "piece_delivree_le",
        "piece_delivree_a", "piece_expire_le", "piece_delivree_par", "ifu",
        "rccm_particulier",
    )),
    ("coordonnees", "Résidence & contact", (
        "ville_residence", "pays_residence", "pays_residence_fiscale", "secteur", "quartier", "rue", "porte",
        "repere_proximite", "adresse", "resident_bf", "statut_logement",
        "justificatif_domicile", "a_autre_nationalite", "autre_nationalite",
        "contact_diaspora_pays", "contact_diaspora_nom", "contact_diaspora_adresse",
        "contact_diaspora_domicile", "contact_diaspora_telephone_fixe", "contact_diaspora_telephone_mobile",
        "telephone", "telephone_secondaire", "telephone_domicile",
        "telephone_bureau", "email", "boite_postale",
    )),
    ("activite", "Activité professionnelle", (
        "categorie_client", "categorie_client_autre", "activite_commerciale", "profession", "employeur",
        "secteur_activite", "adresse_employeur", "poste_occupe", "date_embauche", "revenu_mensuel",
    )),
    ("revenus", "Autres revenus & opérations", (
        "revenus_ailleurs", "revenus_immobiliers", "revenus_mobiliers", "recettes_commerciales",
        "indemnites", "autres_revenus", "montant_versement_initial",
        "nature_versement_initial", "operations_habituelles",
        "mandat_administrateur", "societes_administrees", "est_actionnaire",
        "societes_actionnaire",
    )),
    ("relation", "Historique bancaire & entrée en relation", (
        "numero_compte_bcb_existant", "autres_comptes_bancaires",
        "client_introduit_par", "entree_relation_directe", "parrainage_tiers",
        "mode_entree_relation", "procuration_donnee", "procuration_details",
    )),
    ("famille", "Famille & contacts à prévenir", (
        "situation_matrimoniale", "regime_matrimonial", "conjoint_nom",
        "conjoint_contact", "conjoint_date_naissance", "conjoint_ville_naissance",
        "conjoint_pays_naissance", "conjoint_nom_mere", "conjoint_type_piece",
        "conjoint_numero_piece", "conjoint_piece_delivree_a",
        "conjoint_piece_delivree_le", "conjoint_piece_delivree_par",
        "conjoint_piece_expire_le", "conjoint_profession",
        "conjoint_date_embauche", "conjoint_tranche_revenu",
        "nombre_enfants", "enfants_noms",
        "urgence_nom_1", "urgence_tel_1", "urgence_prof_1",
        "urgence_lieu_travail_1", "urgence_adresse_1",
        "urgence_tel_2_1", "urgence_secteur_1", "urgence_quartier_1",
        "urgence_detail_1",
        "urgence_nom_2", "urgence_tel_2", "urgence_prof_2",
        "urgence_lieu_travail_2", "urgence_adresse_2",
    )),
    ("entreprise", "Entreprise & mandataire", (
        "pm_raison_sociale", "pm_sigle", "pm_forme_juridique",
        "pm_activite_principale", "pm_numero_rccm", "pm_date_creation",
        "pm_date_enregistrement_rccm", "pm_date_nomination_mandataire",
        "pm_ifu", "pm_siege_social",
        "pm_secteur_rue", "pm_telephone_bureau", "pm_email", "pm_capital_social",
        "pm_chiffre_affaires", "pm_actionnaire_1", "pm_actionnaire_2",
        "pm_fonction_mandataire",
    )),
    ("conformite", "Déclarations du client", (
        "est_us_person", "est_ppe", "levee_secret_bancaire",
    )),
    ("consentements", "Consentement CREDITINFO (formulaire F2)", (
        "f2_transmission_credit", "f2_partage_credit", "f2_exclusion_depots",
        "f2_limite_anciennete", "f2_duree_conservation", "f2_droit_acces",
        "f2_droit_rapport", "creditinfo_confirme",
    )),
    ("controle-agent", "Contrôles KYC par le gestionnaire", (
        "f3_fiche_creation", "f3_consultation_cip", "f3_consultation_amplitude",
        "f3_risque_ppe", "f3_risque_revenus_multiples", "f3_risque_activite",
        "f3_risque_autre", "f3_risque_autre_detail", "f3_risque_pays",
        "f3_niveau_risque", "f3_niveau_risque_revision", "f3_niveau_profil",
        "f3_agent_nom", "f3_agent_date_signature", "f3_chef_agence_nom",
    )),
)

DETAIL_SECTIONS = (
    ("Identité & pièce", (
        ("Type de dossier", "get_type_compte_display"),
        ("Nom", "nom"), ("Prénom(s)", "prenoms"), ("Nom de jeune fille", "nom_jeune_fille"),
        ("Sexe", "get_sexe_display"), ("Date de naissance", "date_naissance"),
        ("Lieu de naissance", "lieu_naissance"), ("Pays de naissance", "pays_naissance"),
        ("Nationalité", "nationalite"), ("Nom du père", "nom_pere"), ("Nom de la mère", "nom_mere"),
        ("Pièce d'identité", "get_type_piece_display"),
        ("Seconde pièce d'identité", "get_type_piece_secondaire_display"),
        ("Numéro de pièce", "numero_piece"),
        ("Délivrée le", "piece_delivree_le"), ("Lieu de délivrance", "piece_delivree_a"),
        ("Expire le", "piece_expire_le"), ("Autorité", "piece_delivree_par"),
        ("IFU personnel", "ifu"), ("RCCM individuel", "rccm_particulier"),
    )),
    ("Résidence & contact", (
        ("Ville", "ville_residence"), ("Pays", "pays_residence"),
        ("Pays de résidence fiscale", "pays_residence_fiscale"),
        ("Secteur", "secteur"), ("Quartier", "quartier"),
        ("Rue / Avenue", "rue"), ("Porte / Lot", "porte"), ("Repère", "repere_proximite"),
        ("Adresse", "adresse"), ("Résident au Burkina Faso", "resident_bf"),
        ("Statut du logement", "get_statut_logement_display"),
        ("Justificatif de domicile", "get_justificatif_domicile_display"),
        ("Possède une autre nationalité", "a_autre_nationalite"),
        ("Autre nationalité", "autre_nationalite"), ("Téléphone principal", "telephone"),
        ("Téléphone secondaire", "telephone_secondaire"), ("Téléphone domicile", "telephone_domicile"),
        ("Téléphone bureau", "telephone_bureau"), ("Email", "email"),
        ("Boîte postale", "boite_postale"),
    )),
    ("Activité professionnelle", (
        ("Catégorie professionnelle", "get_categorie_client_display"),
        ("Autre catégorie", "categorie_client_autre"),
        ("Activité commerciale", "activite_commerciale"),
        ("Profession", "profession"), ("Employeur", "employeur"),
        ("Secteur d'activité", "secteur_activite"), ("Adresse de travail", "adresse_employeur"),
        ("Poste", "poste_occupe"),
        ("Date d'embauche", "date_embauche"), ("Revenu mensuel (FCFA)", "revenu_mensuel"),
    )),
    ("Revenus & opérations", (
        ("Revenus immobiliers (FCFA)", "revenus_immobiliers"),
        ("Revenus mobiliers (FCFA)", "revenus_mobiliers"),
        ("Recettes commerciales (FCFA)", "recettes_commerciales"),
        ("Indemnités (FCFA)", "indemnites"), ("Autres revenus (FCFA)", "autres_revenus"),
        ("Versement initial (FCFA)", "montant_versement_initial"),
        ("Nature du versement initial", "nature_versement_initial"),
        ("Opérations et volumes habituels", "operations_habituelles"),
        ("Mandat d'administrateur", "mandat_administrateur"),
        ("Sociétés administrées", "societes_administrees"),
        ("Actionnaire dans une société", "est_actionnaire"),
        ("Sociétés concernées", "societes_actionnaire"),
    )),
    ("Historique bancaire & entrée en relation", (
        ("Compte BCB déjà ouvert", "numero_compte_bcb_existant"),
        ("Autres comptes et banques", "autres_comptes_bancaires"),
        ("Client introduit par", "client_introduit_par"),
        ("Entrée en relation directe", "entree_relation_directe"),
        ("Parrainage", "parrainage_tiers"),
        ("Mode de contact", "get_mode_entree_relation_display"),
        ("Procuration donnée", "procuration_donnee"),
        ("Détails de la procuration", "procuration_details"),
    )),
    ("Famille & contacts à prévenir", (
        ("Situation matrimoniale", "get_situation_matrimoniale_display"),
        ("Régime matrimonial", "regime_matrimonial"), ("Conjoint", "conjoint_nom"),
        ("Contact du conjoint", "conjoint_contact"),
        ("Date de naissance du conjoint", "conjoint_date_naissance"),
        ("Ville de naissance du conjoint", "conjoint_ville_naissance"),
        ("Pays de naissance du conjoint", "conjoint_pays_naissance"),
        ("Nom de la mère du conjoint", "conjoint_nom_mere"),
        ("Pièce du conjoint", "get_conjoint_type_piece_display"),
        ("Numéro de pièce du conjoint", "conjoint_numero_piece"),
        ("Pièce délivrée à", "conjoint_piece_delivree_a"),
        ("Pièce délivrée le", "conjoint_piece_delivree_le"),
        ("Autorité de délivrance", "conjoint_piece_delivree_par"),
        ("Pièce expirant le", "conjoint_piece_expire_le"),
        ("Profession du conjoint", "conjoint_profession"),
        ("Date d'embauche du conjoint", "conjoint_date_embauche"),
        ("Tranche de revenu du conjoint", "conjoint_tranche_revenu"),
        ("Nombre d'enfants", "nombre_enfants"), ("Prénoms des enfants", "enfants_noms"),
        ("Personne à prévenir 1 — Nom", "urgence_nom_1"), ("Personne à prévenir 1 — Téléphone", "urgence_tel_1"),
        ("Personne à prévenir 1 — Profession", "urgence_prof_1"), ("Personne à prévenir 1 — Lieu de travail", "urgence_lieu_travail_1"),
        ("Personne à prévenir 1 — Adresse", "urgence_adresse_1"),
        ("Personne à prévenir 1 - Téléphone secondaire", "urgence_tel_2_1"),
        ("Personne à prévenir 1 - Secteur", "urgence_secteur_1"),
        ("Personne à prévenir 1 - Quartier", "urgence_quartier_1"),
        ("Personne à prévenir 1 - Détail explicatif", "urgence_detail_1"),
        ("Personne à prévenir 2 — Nom", "urgence_nom_2"), ("Personne à prévenir 2 — Téléphone", "urgence_tel_2"),
        ("Personne à prévenir 2 — Profession", "urgence_prof_2"), ("Personne à prévenir 2 — Lieu de travail", "urgence_lieu_travail_2"),
        ("Personne à prévenir 2 — Adresse", "urgence_adresse_2"),
    )),
    ("Entreprise & mandataire", (
        ("Raison sociale", "pm_raison_sociale"), ("Sigle", "pm_sigle"),
        ("Forme juridique", "get_pm_forme_juridique_display"), ("Activité principale", "pm_activite_principale"),
        ("RCCM entreprise", "pm_numero_rccm"),
        ("Date de création", "pm_date_creation"),
        ("Date d'enregistrement RCCM", "pm_date_enregistrement_rccm"),
        ("Date de nomination du mandataire", "pm_date_nomination_mandataire"),
        ("IFU entreprise", "pm_ifu"),
        ("Siège social", "pm_siege_social"), ("Adresse", "pm_secteur_rue"),
        ("Téléphone bureau", "pm_telephone_bureau"), ("Email société", "pm_email"),
        ("Capital social (FCFA)", "pm_capital_social"), ("Chiffre d'affaires annuel (FCFA)", "pm_chiffre_affaires"),
        ("Actionnaire 1", "pm_actionnaire_1"), ("Actionnaire 2", "pm_actionnaire_2"),
        ("Fonction du mandataire", "pm_fonction_mandataire"),
    )),
    ("Déclarations du client", (
        ("US Person (FATCA)", "est_us_person"),
        ("Personne politiquement exposée", "est_ppe"),
        ("Levée du secret bancaire", "levee_secret_bancaire"),
    )),
    ("Consentement CREDITINFO (formulaire F2)", (
        ("Autorise la transmission des informations de crédit", "f2_transmission_credit"),
        ("Autorise le partage aux établissements membres de l'UMOA", "f2_partage_credit"),
        ("Comprend l'exclusion des informations sur les dépôts", "f2_exclusion_depots"),
        ("Comprend la limite d'ancienneté de cinq ans", "f2_limite_anciennete"),
        ("Comprend la durée de conservation des informations", "f2_duree_conservation"),
        ("Comprend son droit d'accès et de contestation", "f2_droit_acces"),
        ("Comprend son droit à un rapport de crédit gratuit", "f2_droit_rapport"),
    )),
    ("Contrôles KYC du gestionnaire", (
        ("Fiche de création", "f3_fiche_creation"),
        ("Consultation CIP", "f3_consultation_cip"),
        ("Consultation AMPLITUDE", "f3_consultation_amplitude"),
        ("Risque PPE", "f3_risque_ppe"),
        ("Risque de revenus multiples", "f3_risque_revenus_multiples"),
        ("Activité à risque", "f3_risque_activite"),
        ("Autre raison de risque", "f3_risque_autre"),
        ("Précision du risque", "f3_risque_autre_detail"),
        ("Pays à risque", "f3_risque_pays"),
        ("Niveau de risque", "get_f3_niveau_risque_display"),
        ("Risque en cas de révision", "f3_niveau_risque_revision"),
        ("Niveau de profil", "get_f3_niveau_profil_display"),
        ("Gestionnaire de compte", "f3_agent_nom"),
        ("Date de signature du gestionnaire", "f3_agent_date_signature"),
        ("Chef d'agence", "f3_chef_agence_nom"),
    )),
)

FORMULAIRES_IMPRIMABLES = (
    ("f1", "F1 \u2013 Renseignements compl\u00e9mentaires"),
    ("f2", "F2 \u2013 Consentement CREDITINFO"),
    ("f3", "F3 \u2013 Fiche KYC personne physique"),
    ("f4", "F4 \u2013 Fiche de localisation client"),
    ("f5", "F5 \u2013 Plan de rep\u00e9rage"),
)

FORMULAIRES_IMPRIMABLES_COMM = (
    ("cover", "Demande d'ouverture de compte"),
    ("kyc_pm", "KYC Personne Morale (3 pages)"),
    ("f2", "F2 \u2013 Consentement CREDITINFO PM"),
    ("f4", "Fiche de localisation mandataire"),
    ("f5", "Plan de rep\u00e9rage"),
    ("f1", "F1 \u2013 Renseignements compl\u00e9mentaires du mandataire"),
    ("kyc_pp", "KYC du mandataire \u2013 Personne Physique"),
    ("specimen", "Sp\u00e9cimen de signature"),
    ("convention", "Convention de compte courant"),
)

# Champs qui ne sont jamais recopiés lors de « Nouveau dossier à partir de celui-ci » :
# identifiants, statut, PDF, et déclarations du client (à reposer à chaque dossier).
CHAMPS_NON_COPIES = {
    "id", "reference", "statut", "pdf_fige", "cree_le", "maj_le",
    "cree_par", "agence_snapshot", "charge_affaires_snapshot",
    "derniere_impression_le", "derniere_impression_par", "signe_le", "signe_par",
    "est_us_person", "est_ppe", "levee_secret_bancaire",
    "f2_transmission_credit", "f2_partage_credit", "f2_exclusion_depots",
    "f2_limite_anciennete", "f2_duree_conservation", "f2_droit_acces",
    "f2_droit_rapport", "resident_bf", "a_autre_nationalite",
    "mandat_administrateur", "est_actionnaire", "entree_relation_directe",
    "procuration_donnee", "creditinfo_confirme",
    "f3_fiche_creation", "f3_consultation_cip", "f3_consultation_amplitude",
    "f3_risque_ppe", "f3_risque_revenus_multiples", "f3_risque_activite",
    "f3_risque_autre", "f3_risque_autre_detail", "f3_risque_pays",
    "f3_niveau_risque", "f3_niveau_risque_revision", "f3_niveau_profil",
    "f3_agent_nom", "f3_agent_date_signature", "f3_chef_agence_nom",
}


def _dossier_form_class(type_compte):
    if type_compte == DossierClient.TypeCompte.COMMERCIAL:
        return DossierCommercialForm
    return DossierParticulierForm


def _form_context(form, dossier=None):
    type_compte = (
        dossier.type_compte if dossier else
        form.initial.get("type_compte") or form.data.get("type_compte")
    )
    sections = []
    commercial = type_compte == DossierClient.TypeCompte.COMMERCIAL
    commercial_order = ("compte", "entreprise", "identite", "coordonnees", "activite", "revenus", "relation", "famille", "conformite", "consentements", "controle-agent")
    section_definitions = list(FORM_SECTIONS)
    if commercial:
        section_definitions.sort(key=lambda item: commercial_order.index(item[0]))
    commercial_titles = {
        "compte": "Compte de l\u2019entreprise",
        "identite": "Identit\u00e9 du mandataire & pi\u00e8ce",
        "coordonnees": "R\u00e9sidence & contact du mandataire",
        "activite": "Activit\u00e9 professionnelle du mandataire",
        "revenus": "Revenus du mandataire & op\u00e9rations",
        "relation": "Historique bancaire & entr\u00e9e en relation du mandataire",
        "famille": "Famille du mandataire & contacts \u00e0 pr\u00e9venir",
    }
    for anchor, title, names in section_definitions:
        if commercial:
            title = commercial_titles.get(anchor, title)
        if anchor == "entreprise" and type_compte != DossierClient.TypeCompte.COMMERCIAL:
            continue
        section_fields = [form[name] for name in names if not (
            anchor == "coordonnees"
              and (
                  (type_compte == DossierClient.TypeCompte.COMMERCIAL and name == "pays_residence")
                  or (type_compte != DossierClient.TypeCompte.COMMERCIAL and name.startswith("contact_diaspora_"))
              )
        )]
        section = {
            "anchor": anchor,
            "title": title,
            "fields": section_fields,
            "business": anchor == "entreprise",
        }
        if anchor == "famille":
            contact_one_names = (
                "urgence_nom_1", "urgence_tel_1", "urgence_prof_1",
                "urgence_lieu_travail_1", "urgence_adresse_1", "urgence_tel_2_1",
                "urgence_secteur_1", "urgence_quartier_1", "urgence_detail_1",
            )
            contact_two_names = (
                "urgence_nom_2", "urgence_tel_2", "urgence_prof_2",
                "urgence_lieu_travail_2", "urgence_adresse_2",
            )
            contact_names = set(contact_one_names + contact_two_names)
            section["family_fields"] = [field for field in section_fields if field.name not in contact_names]
            section["contact_one"] = [form[name] for name in contact_one_names]
            section["contact_two"] = [form[name] for name in contact_two_names]
        sections.append(section)
    return {
        "form": form,
        "sections": sections,
        "dossier": dossier,
        "is_edit": dossier is not None,
        "type_compte": type_compte,
    }


def _valeur_audit(valeur):
    return json.loads(json.dumps(valeur, cls=DjangoJSONEncoder))


def _journaliser(action, utilisateur, dossier=None, details=None):
    return DossierAuditEvent.objects.create(
        action=action,
        utilisateur=utilisateur,
        dossier=dossier,
        details=details or {},
    )


def _instantane_gestionnaire(request, dossier):
    profil, _ = UserProfile.objects.get_or_create(user=request.user)
    dossier.cree_par = request.user
    dossier.agence_snapshot = profil.agence.nom if profil.agence else ""
    dossier.charge_affaires_snapshot = (
        profil.nom_affiche
        or request.user.get_full_name()
        or request.user.get_username()
    )


def _dossier_accessible(request, pk):
    # Les désactivés (supprimés logiquement) ne sont jamais accessibles
    dossiers = DossierClient.objects.exclude(statut=DossierClient.Statut.DESACTIVE)
    if not has_role(request.user, ADMIN_GROUP):
        dossiers = dossiers.filter(cree_par=request.user)
    return get_object_or_404(dossiers, pk=pk)


def _reference_officielle(request, dossier):
    profil = getattr(request.user, "profile", None)
    agence_numero = profil.agence.numero if (profil and profil.agence) else "0000"
    return build_dossier_reference(
        agence_numero, dossier.numero_piece, dossier_id=dossier.pk
    )


def _enregistrer(request, form, action, nouveau):
    """Enregistre le dossier.
    action='draft'   → statut BROUILLON
    action='generate' → statut CREE (workflow : générer PDF puis valider)
    """
    valeurs_initiales = dict(form.initial)
    dossier = form.save(commit=False)

    if nouveau:
        # Référence : brouillon d'abord avec UUID, puis on la met à jour à la validation
        dossier.reference = new_dossier_reference()
        _instantane_gestionnaire(request, dossier)

    if action == "generate":
        dossier.statut = DossierClient.Statut.CREE
    elif nouveau:
        dossier.statut = DossierClient.Statut.BROUILLON

    dossier.save()

    if nouveau:
        _journaliser(DossierAuditEvent.Action.CREATION, request.user, dossier)
    else:
        modifications = {}
        for field_name, valeur_nouvelle in form.cleaned_data.items():
            valeur_ancienne = valeurs_initiales.get(field_name)
            if valeur_ancienne != valeur_nouvelle:
                modifications[field_name] = {
                    "ancienne": _valeur_audit(valeur_ancienne),
                    "nouvelle": _valeur_audit(valeur_nouvelle),
                }
        if modifications:
            _journaliser(
                DossierAuditEvent.Action.MODIFICATION,
                request.user,
                dossier,
                modifications,
            )
    if action == "generate":
        _journaliser(DossierAuditEvent.Action.GENERATION, request.user, dossier)
    return dossier


@never_cache
@manager_or_admin_required
def dossier_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("statut", "").strip()
    # Exclure les désactivés (supprimés logiquement) de la liste
    dossiers = DossierClient.objects.exclude(statut=DossierClient.Statut.DESACTIVE)
    if not has_role(request.user, ADMIN_GROUP):
        dossiers = dossiers.filter(cree_par=request.user)
    if query:
        dossiers = dossiers.filter(
            Q(reference__icontains=query)
            | Q(numero_piece__icontains=query)
            | Q(nom__icontains=query)
            | Q(prenoms__icontains=query)
            | Q(pm_raison_sociale__icontains=query)
            | Q(pm_sigle__icontains=query)
        )
    # Filtrer sur les statuts visibles (pas DESACTIVE)
    statuts_visibles = [
        s for s in DossierClient.Statut.choices
        if s[0] != DossierClient.Statut.DESACTIVE
    ]
    if status in [s[0] for s in statuts_visibles]:
        dossiers = dossiers.filter(statut=status)
    page_obj = Paginator(dossiers, 20).get_page(request.GET.get("page"))
    return render(request, "recueil/dossier_list.html", {
        "page_obj": page_obj,
        "query": query,
        "status": status,
        "status_choices": statuts_visibles,
        "is_admin": has_role(request.user, ADMIN_GROUP),
    })


def _contexte_preview(dossier, request, pk=None):
    """Construit le contexte de prévisualisation à partir d'un dossier déjà sauvegardé."""
    contexte = _contexte_impression(dossier)
    contexte["pk"] = pk if pk is not None else str(dossier.pk)
    contexte["est_commercial"] = dossier.type_compte == DossierClient.TypeCompte.COMMERCIAL
    contexte["dossier_modifie_depuis_impression"] = False
    if contexte["est_commercial"]:
        codes = [code for code, _ in FORMULAIRES_IMPRIMABLES_COMM]
        contexte.update({
            "choisis": codes,
            "formulaires": FORMULAIRES_IMPRIMABLES_COMM,
            "copies": 3,
            "copies_range": range(3),
        })
    else:
        codes = [code for code, _ in FORMULAIRES_IMPRIMABLES]
        contexte.update({
            "choisis": codes,
            "formulaires": FORMULAIRES_IMPRIMABLES,
            "copies": 3,
            "copies_range": range(3),
        })
    return contexte



@never_cache
@manager_required
@transaction.atomic
def dossier_create(request):
    action = request.POST.get("action", "draft") if request.method == "POST" else "draft"

    # ---- Confirmation après prévisualisation ----
    # La preview sauvegarde maintenant en BROUILLON d'abord → plus de risque de perte session
    if action == "confirm":
        pk = request.session.pop("preview_pk", None)
        if not pk:
            messages.error(request, "Session expirée. Veuillez resaisir et générer à nouveau.")
            return redirect("recueil:dossier-create")
        try:
            dossier = DossierClient.objects.get(pk=pk, cree_par=request.user, statut=DossierClient.Statut.BROUILLON)
        except DossierClient.DoesNotExist:
            messages.error(request, "Dossier introuvable.")
            return redirect("recueil:dossier-create")
        # Revalider la version en base pour bloquer les confirmations directes.
        form = _dossier_form_class(dossier.type_compte)(
            data=model_to_dict(dossier), instance=dossier, generate=True
        )
        if not form.is_valid():
            messages.error(
                request,
                "Dossier incomplet : complétez les champs requis avant génération.",
            )
            return render(
                request, "recueil/dossier_form.html", _form_context(form, dossier)
            )
        dossier.reference = _reference_officielle(request, dossier)
        dossier.statut = DossierClient.Statut.CREE
        dossier.save(update_fields=["reference", "statut"])
        _journaliser(DossierAuditEvent.Action.GENERATION, request.user, dossier)
        messages.success(request, "Dossier créé et formulaires prêts pour impression.")
        return redirect("recueil:dossier-print", pk=dossier.pk)

    selected_type = (
        request.POST.get("type_compte", "").strip()
        if request.method == "POST"
        else request.GET.get("type_compte", "").strip()
    )
    if request.method == "GET" and selected_type not in DossierClient.TypeCompte.values:
        return render(request, "recueil/type_choix.html")
    form_class = _dossier_form_class(selected_type)
    form = form_class(
        request.POST or None,
        initial={"type_compte": selected_type} if request.method == "GET" else None,
        generate=action in {"generate", "preview"},
    )
    if request.method == "POST" and form.is_valid():
        if action in {"generate", "preview"}:
            # Sauvegarder en brouillon AVANT la prévisualisation → données jamais perdues
            dossier = _enregistrer(request, form, "draft", nouveau=True)
            request.session["preview_pk"] = str(dossier.pk)
            contexte = _contexte_preview(dossier, request)
            return render(request, "recueil/dossier_preview.html", contexte)
        # Brouillon simple
        dossier = _enregistrer(request, form, "draft", nouveau=True)
        messages.success(request, "Brouillon enregistré.")
        return redirect("recueil:dossier-detail", pk=dossier.pk)
    return render(request, "recueil/dossier_form.html", _form_context(form))


@never_cache
@manager_required
@transaction.atomic
def dossier_edit(request, pk):
    dossier = get_object_or_404(DossierClient, pk=pk, cree_par=request.user)
    if dossier.supprime_le:
        messages.error(request, "Ce dossier a été supprimé.")
        return redirect("recueil:dossier-list")
    if dossier.signe_le:
        messages.error(
            request,
            "Ce dossier est signé et figé. Utilisez « Nouveau dossier » pour le corriger.",
        )
        return redirect("recueil:dossier-detail", pk=dossier.pk)

    action = request.POST.get("action", "draft") if request.method == "POST" else "draft"

    # ---- Confirmation après prévisualisation ----
    if action == "confirm":
        # Revalider les donnees enregistrees, y compris les anciens brouillons.
        form = _dossier_form_class(dossier.type_compte)(
            data=model_to_dict(dossier), instance=dossier, generate=True
        )
        if not form.is_valid():
            messages.error(
                request,
                "Dossier incomplet : complétez les champs requis avant génération.",
            )
            return render(
                request, "recueil/dossier_form.html", _form_context(form, dossier)
            )
        if dossier.statut == DossierClient.Statut.BROUILLON:
            dossier.reference = _reference_officielle(request, dossier)
            dossier.statut = DossierClient.Statut.CREE
            dossier.save(update_fields=["reference", "statut"])
        _journaliser(DossierAuditEvent.Action.GENERATION, request.user, dossier)
        messages.success(request, "Dossier créé et formulaires prêts pour impression.")
        return redirect("recueil:dossier-print", pk=dossier.pk)

    form = _dossier_form_class(dossier.type_compte)(
        request.POST or None,
        instance=dossier,
        generate=action in {"generate", "preview"},
    )
    if request.method == "POST" and form.is_valid():
        if action in {"generate", "preview"}:
            # Sauvegarder les modifications en BD avant d'afficher la preview
            dossier = _enregistrer(request, form, "draft", nouveau=False)
            contexte = _contexte_preview(dossier, request, pk=pk)
            return render(request, "recueil/dossier_preview.html", contexte)
        dossier = _enregistrer(request, form, "draft", nouveau=False)
        messages.success(request, "Dossier mis à jour.")
        return redirect("recueil:dossier-detail", pk=dossier.pk)
    return render(request, "recueil/dossier_form.html", _form_context(form, dossier))


@never_cache
@manager_required
@transaction.atomic
@require_POST
def dossier_reprendre(request, pk):
    """Crée un nouveau brouillon à partir d'un dossier existant du même client.

    Les informations sont recopiées pour être confirmées ou corrigées.
    Les déclarations (FATCA, PPE, secret bancaire) ne sont pas recopiées.
    """
    source = get_object_or_404(DossierClient, pk=pk)
    est_proprietaire = source.cree_par_id == request.user.pk
    acces_recherche = str(source.pk) in request.session.get(
        "client_search_allowed_ids", []
    )
    if not est_proprietaire and not acces_recherche:
        return HttpResponse(status=404)

    nouveau = _copier_dossier(request, source)
    messages.success(
        request,
        "Nouveau brouillon créé à partir du dossier précédent. "
        "Vérifiez les informations (téléphone, adresse, emploi, validité de la pièce) "
        "et posez à nouveau les déclarations.",
    )
    return redirect("recueil:dossier-edit", pk=nouveau.pk)


def _copier_dossier(request, source):
    donnees = {
        field.name: getattr(source, field.name)
        for field in DossierClient._meta.fields
        if field.name not in CHAMPS_NON_COPIES
    }
    nouveau = DossierClient(
        **donnees,
        reference=new_dossier_reference(),
        statut=DossierClient.Statut.BROUILLON,
    )
    _instantane_gestionnaire(request, nouveau)
    nouveau.save()
    _journaliser(
        DossierAuditEvent.Action.CREATION,
        request.user,
        nouveau,
        {"copie_de": source.reference},
    )
    _journaliser(
        DossierAuditEvent.Action.REUTILISATION,
        request.user,
        source,
        {"nouveau_dossier": nouveau.reference},
    )
    return nouveau


@never_cache
@manager_or_admin_required
def dossier_detail(request, pk):
    dossier = _dossier_accessible(request, pk)
    _journaliser(
        DossierAuditEvent.Action.CONSULTATION,
        request.user,
        dossier,
    )
    sections = []
    for title, entries in DETAIL_SECTIONS:
        if title == "Entreprise & mandataire" and dossier.type_compte != DossierClient.TypeCompte.COMMERCIAL:
            continue
        values = []
        for label, attr in entries:
            value = getattr(dossier, attr)() if attr.startswith("get_") else getattr(dossier, attr)
            if isinstance(value, bool):
                value = "Oui" if value else "Non"
            values.append((label, value if value not in (None, "") else "—"))
        sections.append({"title": title, "values": values})
    return render(request, "recueil/dossier_detail.html", {
        "dossier": dossier,
        "sections": sections,
        "is_admin": has_role(request.user, ADMIN_GROUP),
        "is_owner": dossier.cree_par_id == request.user.pk,
    })


def _etat_cases_impression(dossier):
    etat = {}

    def ajouter_oui_non(prefixe, valeur):
        etat[f"{prefixe}_oui"] = valeur is True
        etat[f"{prefixe}_non"] = valeur is False

    ajouter_oui_non("us", dossier.est_us_person)
    ajouter_oui_non("ppe", dossier.est_ppe)
    ajouter_oui_non("secret", dossier.levee_secret_bancaire)
    ajouter_oui_non("f2_transmission_credit", dossier.f2_transmission_credit)
    ajouter_oui_non("f2_partage_credit", dossier.f2_partage_credit)
    ajouter_oui_non("f2_exclusion_depots", dossier.f2_exclusion_depots)
    ajouter_oui_non("f2_limite_anciennete", dossier.f2_limite_anciennete)
    ajouter_oui_non("f2_duree_conservation", dossier.f2_duree_conservation)
    ajouter_oui_non("f2_droit_acces", dossier.f2_droit_acces)
    ajouter_oui_non("f2_droit_rapport", dossier.f2_droit_rapport)
    ajouter_oui_non("resident_bf", dossier.resident_bf)
    ajouter_oui_non("autre_nationalite", dossier.a_autre_nationalite)
    ajouter_oui_non("administrateur", dossier.mandat_administrateur)
    ajouter_oui_non("actionnaire", dossier.est_actionnaire)
    ajouter_oui_non("entree_directe", dossier.entree_relation_directe)
    ajouter_oui_non("procuration", dossier.procuration_donnee)
    ajouter_oui_non("f3_fiche_creation", dossier.f3_fiche_creation)
    ajouter_oui_non("f3_consultation_cip", dossier.f3_consultation_cip)
    ajouter_oui_non("f3_consultation_amplitude", dossier.f3_consultation_amplitude)
    ajouter_oui_non("f3_risque_ppe", dossier.f3_risque_ppe)
    ajouter_oui_non("f3_risque_revenus_multiples", dossier.f3_risque_revenus_multiples)
    ajouter_oui_non("f3_risque_activite", dossier.f3_risque_activite)
    ajouter_oui_non("f3_risque_autre", dossier.f3_risque_autre)
    ajouter_oui_non("f3_risque_pays", dossier.f3_risque_pays)

    situation = dossier.situation_matrimoniale
    marie = situation in ("MARIE_MONO", "MARIE_POLY")
    ajouter_oui_non("marie", marie if situation else None)
    ajouter_oui_non("mono", situation == "MARIE_MONO" if marie else None)
    ajouter_oui_non("poly", situation == "MARIE_POLY" if marie else None)
    ajouter_oui_non("celib", situation == "CELIBATAIRE" if situation else None)

    regime = (dossier.regime_matrimonial or "").lower()
    if marie and "commun" in regime:
        ajouter_oui_non("communs", True)
        ajouter_oui_non("separes", False)
    elif marie and ("sépar" in regime or "separ" in regime):
        ajouter_oui_non("communs", False)
        ajouter_oui_non("separes", True)
    else:
        ajouter_oui_non("communs", None)
        ajouter_oui_non("separes", None)

    categorie = dossier.categorie_client
    etat.update({
        "categorie_salarie_prive": categorie == DossierClient.CategorieClient.SALARIE_PRIVE,
        "categorie_salarie_public": categorie == DossierClient.CategorieClient.SALARIE_PUBLIC,
        "categorie_etudiant": categorie == DossierClient.CategorieClient.ETUDIANT,
        "categorie_liberale": categorie == DossierClient.CategorieClient.PROFESSION_LIBERALE,
        "categorie_retraite": categorie == DossierClient.CategorieClient.RETRAITE,
        "categorie_commerciale": categorie == DossierClient.CategorieClient.ACTIVITE_COMMERCIALE,
        "categorie_autre": categorie == DossierClient.CategorieClient.AUTRE,
        "logement_locataire": dossier.statut_logement == DossierClient.StatutLogement.LOCATAIRE,
        "logement_proprietaire": dossier.statut_logement == DossierClient.StatutLogement.PROPRIETAIRE,
        "logement_autre": dossier.statut_logement == DossierClient.StatutLogement.AUTRE,
        "relation_en_personne": dossier.mode_entree_relation == DossierClient.ModeEntreeRelation.EN_PERSONNE,
        "relation_distance": dossier.mode_entree_relation == DossierClient.ModeEntreeRelation.A_DISTANCE,
        # Forme juridique PM
        "forme_sarl": dossier.pm_forme_juridique == "SARL",
        "forme_sa": dossier.pm_forme_juridique == "SA",
        "forme_ong": dossier.pm_forme_juridique == "ONG",
        "forme_ei": dossier.pm_forme_juridique == "EI",
        "forme_autre": dossier.pm_forme_juridique in ("SAS", "AUTRE"),
    })
    return etat


def _contexte_impression(dossier):
    adresse = ", ".join(
        part
        for part in (
            dossier.porte,
            dossier.rue,
            dossier.quartier,
            dossier.ville_residence,
        )
        if part
    )
    details_delivrance = " - ".join(
        part
        for part in (
            dossier.piece_delivree_a,
            dossier.piece_delivree_le.strftime("%d/%m/%Y")
            if dossier.piece_delivree_le
            else "",
        )
        if part
    )
    tous_les_prenoms = [
        prenom.strip()
        for prenom in dossier.enfants_noms.splitlines()
        if prenom.strip()
    ]
    enfants_noms = tous_les_prenoms[:5]
    enfants_noms.extend([""] * (5 - len(enfants_noms)))
    return {
        "dossier": dossier,
        "nom_complet": " ".join(
            part for part in (dossier.nom, dossier.prenoms) if part
        ),
        "adresse_domicile": adresse,
        "details_delivrance": details_delivrance,
        "enfants_noms": enfants_noms,
        "suite_enfants": tous_les_prenoms[5:],
        "date_impression": timezone.localdate(),
        "diaspora": dossier.resident_bf is False,
        "montant_versement_initial_affiche": (
            f"{dossier.montant_versement_initial:,.0f}".replace(",", "\u202f")
            if dossier.montant_versement_initial is not None else ""
        ),
        "etat": _etat_cases_impression(dossier),
    }


@never_cache
@manager_required
@transaction.atomic
@require_POST
def dossier_supprimer(request, pk):
    """Suppression logique d'un brouillon — masqué dans l'interface, traçable en BD."""
    dossier = get_object_or_404(DossierClient, pk=pk, cree_par=request.user)
    if dossier.statut != DossierClient.Statut.BROUILLON:
        messages.error(request, "Seul un brouillon peut être supprimé.")
        return redirect("recueil:dossier-detail", pk=dossier.pk)
    dossier.statut = DossierClient.Statut.DESACTIVE
    dossier.supprime_le = timezone.now()
    dossier.supprime_par = request.user
    dossier.save(update_fields=["statut", "supprime_le", "supprime_par"])
    _journaliser(DossierAuditEvent.Action.SUPPRESSION, request.user, dossier)
    messages.success(request, f"Le brouillon {dossier.reference} a été supprimé.")
    return redirect("recueil:dossier-list")


@never_cache
@manager_required
def dossier_print(request, pk):
    dossier = get_object_or_404(DossierClient, pk=pk, cree_par=request.user)
    en_generation = dossier.statut == DossierClient.Statut.BROUILLON
    if dossier.statut not in (
        DossierClient.Statut.BROUILLON,
        DossierClient.Statut.CREE,
        DossierClient.Statut.GENERE,
    ):
        return redirect("recueil:dossier-list")
    if en_generation:
        form = _dossier_form_class(dossier.type_compte)(
            data=model_to_dict(dossier), instance=dossier, generate=True
        )
        if not form.is_valid():
            messages.error(request, "Complétez les champs signalés avant de générer les formulaires.")
            return render(request, "recueil/dossier_form.html", _form_context(form, dossier))

    _journaliser(DossierAuditEvent.Action.CONSULTATION, request.user, dossier)

    contexte = _contexte_impression(dossier)
    contexte["en_generation"] = en_generation
    contexte["dossier_modifie_depuis_impression"] = (
        dossier.derniere_impression_le is not None
        and dossier.maj_le > dossier.derniere_impression_le
    )

    if dossier.type_compte == DossierClient.TypeCompte.COMMERCIAL:
        codes = [code for code, _ in FORMULAIRES_IMPRIMABLES_COMM]
        # Lors de la première génération, préparer systématiquement le dossier
        # commercial complet. La sélection reste disponible pour les réimpressions.
        choisis = codes if en_generation else (
            [c for c in request.GET.getlist("f") if c in codes] or codes
        )
        try:
            copies = max(1, min(5, int(request.GET.get("copies", 3))))
        except ValueError:
            copies = 3
        contexte.update({
            "choisis": choisis,
            "formulaires": FORMULAIRES_IMPRIMABLES_COMM,
            "copies": copies,
            "copies_range": range(copies),
        })
        response = render(request, "recueil/print/dossier_print_comm.html", contexte)
    else:
        codes = [code for code, _ in FORMULAIRES_IMPRIMABLES]
        choisis = [c for c in request.GET.getlist("f") if c in codes] or codes
        try:
            copies = max(1, min(5, int(request.GET.get("copies", 3))))
        except ValueError:
            copies = 3
        contexte.update({
            "choisis": choisis,
            "formulaires": FORMULAIRES_IMPRIMABLES,
            "copies": copies,
            "copies_range": range(copies),
        })
        response = render(request, "recueil/print/dossier_print.html", contexte)

    response["Cache-Control"] = "private, no-store"
    return response


@never_cache
@manager_required
@transaction.atomic
@require_POST
def dossier_confirmer(request, pk):
    dossier = get_object_or_404(
        DossierClient, pk=pk, cree_par=request.user, statut=DossierClient.Statut.BROUILLON
    )
    form = _dossier_form_class(dossier.type_compte)(
        data=model_to_dict(dossier), instance=dossier, generate=True
    )
    if not form.is_valid():
        messages.error(request, "Complétez les champs signalés avant d'enregistrer le dossier.")
        return redirect("recueil:dossier-edit", pk=dossier.pk)
    dossier.reference = _reference_officielle(request, dossier)
    dossier.statut = DossierClient.Statut.CREE
    dossier.save(update_fields=["reference", "statut"])
    _journaliser(DossierAuditEvent.Action.GENERATION, request.user, dossier)
    messages.success(request, "Dossier enregistré comme créé.")
    return redirect("recueil:dossier-print", pk=dossier.pk)


@never_cache
@manager_required
@transaction.atomic
@require_POST
def dossier_impression_marquer(request, pk):
    dossier = get_object_or_404(DossierClient, pk=pk, cree_par=request.user)
    if dossier.statut not in (
        DossierClient.Statut.BROUILLON,
        DossierClient.Statut.CREE,
        DossierClient.Statut.GENERE,
    ):
        return JsonResponse({"error": "Le dossier ne peut pas être imprimé dans son état actuel."}, status=400)

    dossier.derniere_impression_le = timezone.now()
    dossier.derniere_impression_par = request.user
    dossier.save(update_fields=["derniere_impression_le", "derniere_impression_par"])
    _journaliser(DossierAuditEvent.Action.IMPRESSION, request.user, dossier)
    return JsonResponse({"ok": True})


@never_cache
@manager_required
@transaction.atomic
@require_POST
def dossier_signer(request, pk):
    dossier = get_object_or_404(DossierClient, pk=pk, cree_par=request.user)
    if dossier.statut not in (DossierClient.Statut.CREE, DossierClient.Statut.GENERE):
        messages.error(request, "Seul un dossier créé peut être marqué comme signé.")
        return redirect("recueil:dossier-detail", pk=dossier.pk)
    if not dossier.signe_le:
        dossier.signe_le = timezone.now()
        dossier.signe_par = request.user
        dossier.save(update_fields=["signe_le", "signe_par"])
        _journaliser(DossierAuditEvent.Action.SIGNATURE, request.user, dossier)
        messages.success(request, "Le dossier est marqué comme signé et ne peut plus être modifié.")
    return redirect("recueil:dossier-detail", pk=dossier.pk)


@never_cache
@manager_required
def recherche_client(request):
    query = request.GET.get("q", "").strip()
    if not query:
        query = request.GET.get("numero_piece", "").strip()
    resultat = None
    if query:
        dossier = (
            DossierClient.objects.exclude(statut=DossierClient.Statut.DESACTIVE)
            .filter(cree_par=request.user)
            .filter(
                Q(numero_piece__iexact=query)
                | Q(nom__icontains=query)
                | Q(prenoms__icontains=query)
                | Q(pm_raison_sociale__icontains=query)
                | Q(pm_sigle__icontains=query)
            )
            .order_by("-maj_le")
            .first()
        )
        request.session["client_search_allowed_ids"] = (
            [str(dossier.pk)] if dossier else []
        )
        _journaliser(
            DossierAuditEvent.Action.RECHERCHE_CLIENT,
            request.user,
            dossier,
            {"correspondance": dossier is not None, "critere": query},
        )
        if dossier:
            resultat = {
                "pk": dossier.pk,
                "nom_complet": f"{dossier.prenoms} {dossier.nom}".strip(),
                "date_naissance": dossier.date_naissance,
                "reference": dossier.reference,
                "type_compte": dossier.get_type_compte_display(),
                "agence": dossier.agence_snapshot,
                "maj_le": dossier.maj_le,
            }
    return render(
        request,
        "recueil/recherche_client.html",
        {"query": query, "numero_piece": query, "resultat": resultat},
    )


@never_cache
@admin_required
def journal_audit(request):
    events = DossierAuditEvent.objects.select_related(
        "dossier", "utilisateur"
    )
    page_obj = Paginator(events, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "recueil/journal_audit.html",
        {"page_obj": page_obj},
    )


# ---------------------------------------------------------------------------
# Gestion des gestionnaires (réservée aux Admins)
# ---------------------------------------------------------------------------


@never_cache
@admin_required
def demandes_acces(request):
    demandes = (
        ADAccessRequest.objects.filter(status=ADAccessRequest.Status.PENDING)
        .select_related("user", "user__profile")
        .order_by("requested_at")
    )
    return render(request, "recueil/demandes_acces.html", {
        "demandes": demandes,
        "agences": Agence.objects.filter(active=True).order_by("numero"),
    })


@never_cache
@admin_required
@transaction.atomic
@require_POST
def traiter_demande_acces(request, pk):
    demande = get_object_or_404(
        ADAccessRequest.objects.select_for_update(),
        pk=pk,
        status=ADAccessRequest.Status.PENDING,
    )
    decision = request.POST.get("decision")
    if decision == "approve":
        agence = get_object_or_404(
            Agence,
            pk=request.POST.get("agence"),
            active=True,
        )
        user = demande.user
        profile = user.profile
        profile.ad_access_approved = True
        profile.agence = agence
        profile.nom_affiche = user.get_full_name() or user.get_username()
        profile.save(update_fields=("ad_access_approved", "agence", "nom_affiche"))

        groupe, _ = Group.objects.get_or_create(name="GESTIONNAIRE")
        user.groups.add(groupe)
        user.set_unusable_password()
        user.save(update_fields=("password",))

        demande.status = ADAccessRequest.Status.APPROVED
        action = DossierAuditEvent.Action.ACCES_APPROUVE
        message = f"L'accès de {user.get_username()} a été approuvé."
    elif decision == "reject":
        demande.status = ADAccessRequest.Status.REJECTED
        action = DossierAuditEvent.Action.ACCES_REJETE
        message = f"La demande d'accès de {demande.user.get_username()} a été refusée."
    else:
        messages.error(request, "Choisissez une décision valide.")
        return redirect("recueil:demandes-acces")

    demande.reviewed_by = request.user
    demande.reviewed_at = timezone.now()
    demande.save(update_fields=("status", "reviewed_by", "reviewed_at"))
    _journaliser(action, request.user, details={
        "demande_acces_id": demande.pk,
        "utilisateur_concerne": demande.user.get_username(),
        "agence": str(demande.user.profile.agence) if decision == "approve" else "",
    })
    messages.success(request, message)
    return redirect("recueil:demandes-acces")


@never_cache
@admin_required
def gestion_utilisateurs(request):
    """Liste tous les gestionnaires (groupe GESTIONNAIRE)."""
    User = get_user_model()
    gestionnaires = (
        User.objects.filter(groups__name="GESTIONNAIRE")
        .select_related("profile")
        .order_by("profile__agence", "username")
    )
    return render(request, "recueil/gestion_utilisateurs.html", {
        "gestionnaires": gestionnaires,
        "ad_mode": settings.AUTH_MODE == "AD",
        "demandes_acces_en_attente": ADAccessRequest.objects.filter(
            status=ADAccessRequest.Status.PENDING
        ).count(),
    })


@never_cache
@admin_required
def gestionnaire_creer(request):
    """Création d'un nouveau gestionnaire avec rattachement agence."""
    if settings.AUTH_MODE == "AD":
        messages.info(request, "Les gestionnaires se connectent avec leur compte AD. Traitez leur demande d'accès après leur première connexion.")
        return redirect("recueil:demandes-acces")

    if request.method == "POST":
        form = GestionnaireUserForm(request.POST)
        profile_form = UserProfileForm(request.POST)
        password_form = GestionnairePasswordForm(request.POST, creation=True)

        if form.is_valid() and profile_form.is_valid() and password_form.is_valid():
            user = form.save(commit=False)
            user.set_password(password_form.cleaned_data["new_password1"])
            user.is_active = True
            user.save()

            groupe, _ = Group.objects.get_or_create(name="GESTIONNAIRE")
            user.groups.add(groupe)

            profile = user.profile
            profile.nom_affiche = profile_form.cleaned_data.get("nom_affiche", "")
            profile.agence = profile_form.cleaned_data.get("agence")
            profile.save()

            _journaliser(
                DossierAuditEvent.Action.CREATION,
                request.user,
                details={
                    "gestionnaire_cree": user.username,
                    "agence": str(profile.agence) if profile.agence else "",
                },
            )
            messages.success(
                request,
                f"Le gestionnaire « {user.get_full_name() or user.username} » a été créé.",
            )
            return redirect("recueil:gestion-utilisateurs")
    else:
        form = GestionnaireUserForm()
        profile_form = UserProfileForm()
        password_form = GestionnairePasswordForm(creation=True)

    return render(request, "recueil/gestionnaire_form.html", {
        "form": form,
        "profile_form": profile_form,
        "password_form": password_form,
        "is_edit": False,
    })


@never_cache
@admin_required
def gestionnaire_modifier(request, pk):
    """Modification d'un gestionnaire existant."""
    User = get_user_model()
    gestionnaire = get_object_or_404(
        User.objects.select_related("profile"),
        pk=pk,
        groups__name="GESTIONNAIRE",
    )
    profile = gestionnaire.profile
    ad_mode = settings.AUTH_MODE == "AD"

    if request.method == "POST":
        form = GestionnaireUserForm(request.POST, instance=gestionnaire)
        profile_form = UserProfileForm(request.POST, instance=profile)
        password_form = None if ad_mode else GestionnairePasswordForm(request.POST)

        if form.is_valid() and profile_form.is_valid() and (ad_mode or password_form.is_valid()):
            form.save()
            profile.nom_affiche = profile_form.cleaned_data.get("nom_affiche", "")
            profile.agence = profile_form.cleaned_data.get("agence")
            profile.save()
            if not ad_mode and password_form.has_new_password():
                gestionnaire.set_password(password_form.cleaned_data["new_password1"])
                gestionnaire.save(update_fields=["password"])
            messages.success(request, f"Le gestionnaire « {gestionnaire.get_full_name() or gestionnaire.username} » a été mis à jour.")
            return redirect("recueil:gestion-utilisateurs")
    else:
        form = GestionnaireUserForm(instance=gestionnaire)
        profile_form = UserProfileForm(instance=profile)
        password_form = None if ad_mode else GestionnairePasswordForm()

    return render(request, "recueil/gestionnaire_form.html", {
        "form": form,
        "profile_form": profile_form,
        "password_form": password_form,
        "gestionnaire": gestionnaire,
        "is_edit": True,
        "ad_mode": ad_mode,
    })
