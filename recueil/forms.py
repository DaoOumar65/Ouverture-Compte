import uuid

from django import forms
from django.conf import settings
from django.utils import timezone

from .models import DossierClient, DossierIdentiteVerrou, normaliser_numero_piece


# Widget RadioSelect qui propage data-field-name sur chaque <input> individuel
# pour permettre au JS de cibler les radios par [data-field-name].
class TaggedRadioSelect(forms.RadioSelect):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        option["attrs"]["data-field-name"] = name
        return option


IDENTITY_REQUIRED_FOR_GENERATION = (
    "type_compte",
    "formule_produit",
    "nom",
    "prenoms",
    "sexe",
    "date_naissance",
    "lieu_naissance",
    "pays_naissance",
    "nationalite",
    "type_piece",
    "numero_piece",
    "situation_matrimoniale",
    "ville_residence",
    "telephone",
    "profession",
)

COMMERCIAL_REQUIRED_FOR_GENERATION = (
    "pm_raison_sociale",
    "pm_forme_juridique",
    "pm_activite_principale",
    "pm_numero_rccm",
    "pm_date_creation",
    "pm_date_enregistrement_rccm",
    "pm_date_nomination_mandataire",
    "pm_ifu",
    "pm_siege_social",
)

# Déclarations du client : réponse explicite (Oui ou Non) obligatoire à la génération.
# Une valeur vide n'est jamais imprimée.
DECLARATIONS = ("est_us_person", "est_ppe", "levee_secret_bancaire")

CONSENTEMENTS_CREDITINFO = (
    "f2_transmission_credit",
    "f2_partage_credit",
    "f2_exclusion_depots",
    "f2_limite_anciennete",
    "f2_duree_conservation",
    "f2_droit_acces",
    "f2_droit_rapport",
)

REPONSES_KYC = (
    "resident_bf",
    "a_autre_nationalite",
    "mandat_administrateur",
    "est_actionnaire",
    "entree_relation_directe",
    "procuration_donnee",
)

CHAMPS_KYC_REQUIS_GENERATION = (
    "categorie_client",
    "statut_logement",
    "justificatif_domicile",
    "mode_entree_relation",
    "nombre_enfants",
    "pays_residence_fiscale",
)


class DossierClientForm(forms.ModelForm):
    creditinfo_confirme = forms.BooleanField(
        label="Le client a lu et confirmé les réponses CREDITINFO",
        required=False,
    )

    class Meta:
        model = DossierClient
        exclude = (
            "id", "reference", "statut", "cree_le", "maj_le", "pdf_fige",
            "cree_par", "agence_snapshot", "agence_numero_snapshot",
            "initiateur_snapshot", "termine_par", "charge_affaires_snapshot",
            "derniere_impression_le", "derniere_impression_par",
            "signe_le", "signe_par",
        )
        widgets = {
            "date_naissance": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "piece_delivree_le": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "piece_expire_le": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "date_embauche": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "pm_date_creation": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "pm_date_enregistrement_rccm": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "pm_date_nomination_mandataire": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "f3_agent_date_signature": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "f3_niveau_risque": forms.RadioSelect,
            "f3_niveau_profil": forms.RadioSelect,
            "conjoint_date_naissance": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "conjoint_piece_delivree_le": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "conjoint_piece_expire_le": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "conjoint_date_embauche": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "revenu_mensuel": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "revenus_immobiliers": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "revenus_mobiliers": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "recettes_commerciales": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "indemnites": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "autres_revenus": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "montant_versement_initial": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "pm_capital_social": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "pm_chiffre_affaires": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        self.generate = kwargs.pop("generate", False)
        fixed_type = kwargs.pop("fixed_type", None)
        super().__init__(*args, **kwargs)
        if fixed_type in DossierClient.TypeCompte.values:
            self.initial["type_compte"] = fixed_type
            self.fields["type_compte"].disabled = True
            self.fields["type_compte"].widget = forms.HiddenInput()
        if not self.instance._state.adding:
            self.fields["type_compte"].disabled = True
        for name, field in self.fields.items():
            field.required = False
            if isinstance(field, forms.ChoiceField) and not any(
                choice[0] == "" for choice in field.choices
            ):
                field.choices = [("", "—")] + list(field.choices)
            field.widget.attrs["class"] = (
                "checkbox-input"
                if getattr(field.widget, "input_type", None) == "checkbox"
                else "form-control"
            )
            field.widget.attrs["data-field-name"] = name

        # Déclarations : boutons radio Oui / Non, sans réponse par défaut.
        for name in (
            *DECLARATIONS,
            *CONSENTEMENTS_CREDITINFO,
            *REPONSES_KYC,
            "f3_consultation_cip",
            "f3_consultation_amplitude",
            "f3_risque_ppe",
            "f3_risque_revenus_multiples",
            "f3_risque_activite",
            "f3_risque_autre",
            "f3_risque_pays",
        ):
            label = self.fields[name].label
            self.fields[name] = forms.TypedChoiceField(
                label=label,
                required=False,
                choices=[("True", "Oui"), ("False", "Non")],
                coerce=lambda value: value == "True",
                empty_value=None,
                widget=TaggedRadioSelect(attrs={"data-field-name": name}),
            )
        self.fields["revenus_ailleurs"] = forms.TypedChoiceField(
            label=self.fields["revenus_ailleurs"].label,
            required=False,
            choices=[("True", "Oui"), ("False", "Non")],
            coerce=lambda value: value == "True",
            empty_value=None,
            widget=TaggedRadioSelect(attrs={"data-field-name": "revenus_ailleurs"}),
        )
        self.fields["f3_fiche_creation"] = forms.TypedChoiceField(
            label="Type de fiche KYC",
            required=False,
            choices=[("True", "Fiche de création"), ("False", "Fiche de mise à jour")],
            coerce=lambda value: value == "True",
            empty_value=None,
            widget=TaggedRadioSelect(attrs={"data-field-name": "f3_fiche_creation"}),
        )
        for name in ("f3_niveau_risque", "f3_niveau_profil"):
            field = self.fields[name]
            field.choices = [choice for choice in field.choices if choice[0] != ""]
            field.widget = TaggedRadioSelect(
                attrs={"data-field-name": name}, choices=field.choices,
            )

    def clean(self):
        cleaned = super().clean()
        numero_piece = (cleaned.get("numero_piece") or "").strip()
        if not numero_piece:
            self.add_error(
                "numero_piece",
                "Renseignez le numéro de CNIB ou de passeport pour enregistrer le brouillon.",
            )
        else:
            cleaned["numero_piece"] = numero_piece
            numero_normalise = normaliser_numero_piece(numero_piece)
            doublons = DossierClient.objects.filter(
                type_compte=cleaned.get("type_compte"),
                numero_piece_normalise=numero_normalise,
                statut__in=(DossierClient.Statut.CREE, DossierClient.Statut.GENERE),
            )
            if self.instance.pk:
                doublons = doublons.exclude(pk=self.instance.pk)
            verrous = DossierIdentiteVerrou.objects.filter(
                type_compte=cleaned.get("type_compte"),
                numero_piece_normalise=numero_normalise,
            )
            if self.instance.pk:
                verrous = verrous.exclude(dossier_id=self.instance.pk)
            if numero_normalise and (doublons.exists() or verrous.exists()):
                self.add_error(
                    "numero_piece",
                    "Un dossier de ce type existe déjà pour cette pièce dans le réseau BCB. Vérifiez le dossier existant avant toute nouvelle ouverture.",
                )

        if self.generate:
            required_fields = list(IDENTITY_REQUIRED_FOR_GENERATION)
            if cleaned.get("type_compte") == DossierClient.TypeCompte.COMMERCIAL:
                required_fields.extend(COMMERCIAL_REQUIRED_FOR_GENERATION)
                if cleaned.get("resident_bf") is False:
                    required_fields.extend((
                        "contact_diaspora_pays", "contact_diaspora_nom",
                        "contact_diaspora_adresse", "contact_diaspora_domicile",
                        "contact_diaspora_telephone_fixe",
                    ))
            for name in required_fields:
                if not cleaned.get(name):
                    self.add_error(name, "Ce champ est requis pour générer les formulaires.")
            if (
                cleaned.get("type_compte") == DossierClient.TypeCompte.PARTICULIER
                and cleaned.get("creditinfo_confirme") is not True
            ):
                self.add_error(
                    "creditinfo_confirme",
                    "Confirmez que le client a lu et validé les réponses CREDITINFO.",
                )
            if cleaned.get("type_compte") == DossierClient.TypeCompte.PARTICULIER:
                for name in (*CHAMPS_KYC_REQUIS_GENERATION, *REPONSES_KYC):
                    if cleaned.get(name) is None or cleaned.get(name) == "":
                        self.add_error(
                            name,
                            "Réponse requise pour générer les formulaires.",
                        )
                if (
                    cleaned.get("mode_entree_relation")
                    == DossierClient.ModeEntreeRelation.A_DISTANCE
                    and not cleaned.get("type_piece_secondaire")
                ):
                    self.add_error(
                        "type_piece_secondaire",
                        "Une seconde pièce est requise pour un contact à distance.",
                    )
                if cleaned.get("a_autre_nationalite") and not cleaned.get("autre_nationalite"):
                    self.add_error(
                        "autre_nationalite",
                        "Précisez l'autre nationalité déclarée.",
                    )
                if cleaned.get("mandat_administrateur") and not cleaned.get("societes_administrees"):
                    self.add_error(
                        "societes_administrees",
                        "Précisez la ou les sociétés administrées.",
                    )
                if cleaned.get("est_actionnaire") and not cleaned.get("societes_actionnaire"):
                    self.add_error(
                        "societes_actionnaire",
                        "Précisez la ou les sociétés concernées.",
                    )
                if cleaned.get("procuration_donnee") and not cleaned.get("procuration_details"):
                    self.add_error(
                        "procuration_details",
                        "Précisez la nature de la procuration et le compte concerné.",
                    )
                if (
                    not cleaned.get("entree_relation_directe")
                    and not cleaned.get("parrainage_tiers")
                ):
                    self.add_error(
                        "parrainage_tiers",
                        "Précisez le tiers parrain si l'entrée en relation n'est pas directe.",
                    )
                if (
                    cleaned.get("categorie_client")
                    == DossierClient.CategorieClient.ACTIVITE_COMMERCIALE
                    and not cleaned.get("activite_commerciale")
                ):
                    self.add_error(
                        "activite_commerciale",
                        "Précisez l'activité commerciale exercée.",
                    )
                if (
                    cleaned.get("categorie_client")
                    == DossierClient.CategorieClient.AUTRE
                    and not cleaned.get("categorie_client_autre")
                ):
                    self.add_error(
                        "categorie_client_autre",
                        "Précisez l'autre catégorie professionnelle.",
                    )
                if (cleaned.get("nombre_enfants") or 0) > 0 and not cleaned.get("enfants_noms"):
                    self.add_error(
                        "enfants_noms",
                        "Précisez les prénoms des enfants.",
                    )
            if cleaned.get("revenus_ailleurs") is None:
                self.add_error("revenus_ailleurs", "Réponse requise (Oui ou Non) pour générer les formulaires.")
            elif cleaned.get("revenus_ailleurs") is False:
                for name in ("revenus_immobiliers", "revenus_mobiliers", "recettes_commerciales", "indemnites", "autres_revenus"):
                    cleaned[name] = 0
            # False est une réponse valide : on teste uniquement l'absence de réponse.
            for name in (*DECLARATIONS, *CONSENTEMENTS_CREDITINFO):
                if cleaned.get(name) is None:
                    self.add_error(
                        name,
                        "Réponse obligatoire (Oui ou Non) pour générer les formulaires.",
                    )

        if cleaned.get("type_compte") != DossierClient.TypeCompte.COMMERCIAL:
            for name in (
                "pm_raison_sociale", "pm_sigle", "pm_forme_juridique",
                "pm_activite_principale", "pm_numero_rccm", "pm_ifu",
                "pm_siege_social", "pm_secteur_rue", "pm_telephone_bureau",
                "pm_email", "pm_actionnaire_1", "pm_actionnaire_2",
                "pm_fonction_mandataire",
            ):
                cleaned[name] = ""
            cleaned["pm_capital_social"] = 0
            cleaned["pm_chiffre_affaires"] = 0
        else:
            cleaned["pm_capital_social"] = cleaned.get("pm_capital_social") or 0
            cleaned["pm_chiffre_affaires"] = cleaned.get("pm_chiffre_affaires") or 0

        for name in self.errors:
            field = self.fields.get(name)
            if field:
                field.widget.attrs["aria-invalid"] = "true"
                error_id = f"{field.widget.attrs.get('id', f'id_{name}')}-errors"
                described_by = field.widget.attrs.get("aria-describedby", "")
                field.widget.attrs["aria-describedby"] = " ".join(
                    filter(None, (described_by, error_id))
                )
        return cleaned


class DossierParticulierForm(DossierClientForm):
    def __init__(self, *args, **kwargs):
        kwargs["fixed_type"] = DossierClient.TypeCompte.PARTICULIER
        super().__init__(*args, **kwargs)


class DossierCommercialForm(DossierClientForm):
    def __init__(self, *args, **kwargs):
        kwargs["fixed_type"] = DossierClient.TypeCompte.COMMERCIAL
        super().__init__(*args, **kwargs)
        mandataire_labels = {
            "nom": "Nom du mandataire",
            "prenoms": "Prénom(s) du mandataire",
            "sexe": "Sexe du mandataire",
            "date_naissance": "Date de naissance du mandataire",
            "lieu_naissance": "Lieu de naissance du mandataire",
            "pays_naissance": "Pays de naissance du mandataire",
            "nationalite": "Nationalité du mandataire",
            "type_piece": "Pièce d'identité du mandataire",
            "numero_piece": "Numéro de pièce du mandataire",
            "ville_residence": "Ville de résidence du mandataire",
            "pays_residence_fiscale": "Pays de résidence fiscale du mandataire",
            "telephone": "Téléphone mobile du mandataire",
            "email": "Adresse email du mandataire",
            "categorie_client": "Catégorie professionnelle du mandataire",
            "profession": "Situation professionnelle du mandataire (justificatifs)",
            "revenu_mensuel": "Salaire net mensuel du mandataire (FCFA)",
            "revenus_ailleurs": "Le mandataire a-t-il d'autres revenus ?",
        }
        for name, label in mandataire_labels.items():
            if name in self.fields:
                self.fields[name].label = label


def new_dossier_reference():
    return f"BCB-{timezone.localdate():%Y}-{uuid.uuid4().hex[:8].upper()}"


def build_dossier_reference(agence_numero, numero_piece, dossier_id=None):
    """Build the official reference; disabled records keep their sequence number."""
    from .models import DossierClient

    piece_clean = "".join(c for c in (numero_piece or "") if c.isalnum()).upper()[:20]
    if not piece_clean:
        piece_clean = uuid.uuid4().hex[:8].upper()
    dossiers = DossierClient.objects.all()
    if dossier_id:
        dossiers = dossiers.exclude(pk=dossier_id)
    ordre = dossiers.count() + 1
    agence_num = str(agence_numero or "0000")
    return f"BCB-{agence_num}-{piece_clean}-{ordre:04d}"


# ---------------------------------------------------------------------------
# Gestion des gestionnaires (création / modification par l'Admin)
# ---------------------------------------------------------------------------

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Agence, UserProfile


def _agences_choices():
    """Retourne les choix d'agences actives depuis la BD."""
    choices = [("", "— Choisir une agence —")]
    for agence in Agence.objects.filter(active=True).order_by("numero"):
        choices.append((str(agence.pk), f"{agence.nom} ({agence.numero})"))
    return choices


class GestionnaireUserForm(forms.ModelForm):
    """Champs de base du compte utilisateur (sans mot de passe)."""

    class Meta:
        model = get_user_model()
        fields = ("username", "first_name", "last_name", "email", "is_active")
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "checkbox-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].label = "Prénom(s)"
        self.fields["last_name"].required = True
        self.fields["last_name"].label = "Nom de famille"
        self.fields["first_name"].required = True
        self.fields["email"].required = False
        self.fields["is_active"].label = "Compte actif"
        if settings.AUTH_MODE == "AD" and self.instance.pk:
            for name in ("username", "first_name", "last_name", "email"):
                self.fields[name].disabled = True
                self.fields[name].help_text = "Valeur issue d'Active Directory."
        if not self.instance.pk:
            self.fields.pop("is_active", None)


class UserProfileForm(forms.ModelForm):
    """Champs du profil BCB : nom affiché + agence (FK)."""

    agence = forms.ModelChoiceField(
        queryset=Agence.objects.filter(active=True).order_by("numero"),
        required=True,
        label="Agence",
        empty_label="— Choisir une agence —",
        widget=forms.Select(attrs={"class": "form-control", "id": "id_agence"}),
    )

    class Meta:
        model = UserProfile
        fields = ("nom_affiche", "agence")
        widgets = {
            "nom_affiche": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_agence(self):
        agence = self.cleaned_data.get("agence")
        if not agence:
            raise forms.ValidationError("Rattachez ce gestionnaire à une agence.")
        return agence


class GestionnairePasswordForm(forms.Form):
    """Formulaire de mot de passe — 8 caractères minimum."""

    new_password1 = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
        required=False,
    )
    new_password2 = forms.CharField(
        label="Confirmer",
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
        required=False,
    )

    def __init__(self, *args, creation=False, **kwargs):
        self.creation = creation
        super().__init__(*args, **kwargs)
        if creation:
            self.fields["new_password1"].required = True
            self.fields["new_password2"].required = True

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("new_password1", "")
        p2 = cleaned.get("new_password2", "")
        if p1 or p2 or self.creation:
            if p1 != p2:
                self.add_error("new_password2", "Les deux mots de passe ne correspondent pas.")
            elif p1:
                if len(p1) < 8:
                    self.add_error("new_password1", "Le mot de passe doit comporter au moins 8 caractères.")
        return cleaned

    def has_new_password(self):
        return bool(self.cleaned_data.get("new_password1"))
