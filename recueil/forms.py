import uuid

from django import forms
from django.utils import timezone

from .models import DossierClient


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
            "cree_par", "agence_snapshot", "charge_affaires_snapshot",
            "derniere_impression_le", "derniere_impression_par",
            "signe_le", "signe_par",
        )
        widgets = {
            "date_naissance": forms.DateInput(attrs={"type": "date"}),
            "piece_delivree_le": forms.DateInput(attrs={"type": "date"}),
            "piece_expire_le": forms.DateInput(attrs={"type": "date"}),
            "date_embauche": forms.DateInput(attrs={"type": "date"}),
            "conjoint_date_naissance": forms.DateInput(attrs={"type": "date"}),
            "conjoint_piece_delivree_le": forms.DateInput(attrs={"type": "date"}),
            "conjoint_piece_expire_le": forms.DateInput(attrs={"type": "date"}),
            "conjoint_date_embauche": forms.DateInput(attrs={"type": "date"}),
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
        super().__init__(*args, **kwargs)
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

    def clean(self):
        cleaned = super().clean()
        if self.generate:
            required_fields = list(IDENTITY_REQUIRED_FOR_GENERATION)
            if cleaned.get("type_compte") == DossierClient.TypeCompte.COMMERCIAL:
                required_fields.extend(COMMERCIAL_REQUIRED_FOR_GENERATION)
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


def new_dossier_reference():
    return f"BCB-{timezone.localdate():%Y}-{uuid.uuid4().hex[:8].upper()}"


# ---------------------------------------------------------------------------
# Gestion des gestionnaires (création / modification par l'Admin)
# ---------------------------------------------------------------------------

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import UserProfile


# Agences connues de la BCB — liste extensible sans migration.
AGENCES_BCB = [
    ("", "— Choisir une agence —"),
    ("Siège — Ouagadougou", "Siège — Ouagadougou"),
    ("Agence Centrale — Ouagadougou", "Agence Centrale — Ouagadougou"),
    ("Agence Paspanga", "Agence Paspanga"),
    ("Agence Gounghin", "Agence Gounghin"),
    ("Agence Zone du Bois", "Agence Zone du Bois"),
    ("Agence Pissy", "Agence Pissy"),
    ("Agence Tampouy", "Agence Tampouy"),
    ("Agence Bobo-Dioulasso", "Agence Bobo-Dioulasso"),
    ("Agence Bobo Secteur 22", "Agence Bobo Secteur 22"),
    ("Agence Koudougou", "Agence Koudougou"),
    ("Agence Banfora", "Agence Banfora"),
    ("Agence Fada N'Gourma", "Agence Fada N'Gourma"),
    ("Agence Kaya", "Agence Kaya"),
    ("Agence Dédougou", "Agence Dédougou"),
    ("Agence Ouahigouya", "Agence Ouahigouya"),
    ("Agence Tenkodogo", "Agence Tenkodogo"),
    ("Agence Réo", "Agence Réo"),
    ("autre", "Autre (saisir ci-dessous)"),
]


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
        self.fields["last_name"].label = "Nom de famille"
        self.fields["email"].required = False
        self.fields["is_active"].label = "Compte actif"
        if not self.instance.pk:
            # À la création, is_active est True par défaut — pas besoin de l'afficher
            self.fields.pop("is_active", None)


class UserProfileForm(forms.ModelForm):
    """Champs du profil BCB : nom affiché + agence."""

    agence_liste = forms.ChoiceField(
        choices=AGENCES_BCB,
        required=False,
        label="Agence",
        widget=forms.Select(attrs={"class": "form-control", "id": "id_agence_liste"}),
    )
    agence_autre = forms.CharField(
        required=False,
        label="Préciser l'agence",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "id": "id_agence_autre",
            "placeholder": "Nom de l'agence…",
        }),
    )

    class Meta:
        model = UserProfile
        fields = ("nom_affiche",)
        widgets = {
            "nom_affiche": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Préremplir la liste si l'agence actuelle est connue, sinon "autre"
        if self.instance and self.instance.pk:
            agence_actuelle = self.instance.agence or ""
            valeurs_connues = [c[0] for c in AGENCES_BCB if c[0]]
            if agence_actuelle in valeurs_connues:
                self.fields["agence_liste"].initial = agence_actuelle
            elif agence_actuelle:
                self.fields["agence_liste"].initial = "autre"
                self.fields["agence_autre"].initial = agence_actuelle

    def clean(self):
        cleaned = super().clean()
        choix = cleaned.get("agence_liste", "")
        autre = cleaned.get("agence_autre", "").strip()
        if choix == "autre":
            if not autre:
                self.add_error("agence_autre", "Précisez le nom de l'agence.")
            else:
                cleaned["agence_resolue"] = autre
        elif choix:
            cleaned["agence_resolue"] = choix
        else:
            self.add_error("agence_liste", "Rattachez ce gestionnaire à une agence.")
        return cleaned

    @property
    def agence(self):
        return self.cleaned_data.get("agence_resolue", "")


class GestionnairePasswordForm(forms.Form):
    """Formulaire de mot de passe avec validation Django."""

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
                try:
                    validate_password(p1)
                except ValidationError as e:
                    self.add_error("new_password1", e)
        return cleaned

    def has_new_password(self):
        return bool(self.cleaned_data.get("new_password1"))
