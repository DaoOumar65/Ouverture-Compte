"""Overlay dossier data on the bank's blank account-opening PDFs."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pymupdf
from django.conf import settings

from .models import DossierClient


PERSONAL_TEMPLATE = "DOCUMENTS OUVERTURE DE COMPTE PARTICULIER.pdf"
COMMERCIAL_TEMPLATE = "OUVERTURE DE COMPTE COMMERCIAL.pdf"


class PdfValueTooLong(Exception):
    """Raised when a value cannot be printed safely inside its official field."""


def _full_name(dossier):
    return " ".join(part for part in (dossier.prenoms, dossier.nom) if part)


def _home_address(dossier):
    if dossier.adresse:
        return dossier.adresse
    return ", ".join(
        part
        for part in (
            dossier.porte,
            dossier.rue,
            dossier.secteur,
            dossier.quartier,
            dossier.ville_residence,
        )
        if part
    )


def _issue_details(dossier):
    parts = []
    if dossier.piece_delivree_a:
        parts.append(dossier.piece_delivree_a)
    if dossier.piece_delivree_le:
        parts.append(dossier.piece_delivree_le.strftime("%d/%m/%Y"))
    return " - ".join(parts)


def _expiry_date(dossier):
    return dossier.piece_expire_le.strftime("%d/%m/%Y") if dossier.piece_expire_le else ""


def _values(dossier):
    values = {
        field.name: getattr(dossier, field.name)
        for field in dossier._meta.fields
        if field.name != "pdf_fige"
    }
    values.update(
        full_name=_full_name(dossier),
        home_address=_home_address(dossier),
        issue_details=_issue_details(dossier),
        expiry_date=_expiry_date(dossier),
        marital_status=dossier.get_situation_matrimoniale_display(),
        type_piece_label=dossier.get_type_piece_display(),
        account_type_label=dossier.get_type_compte_display(),
        sexe_label=dossier.get_sexe_display(),
        company_address=", ".join(
            part for part in (dossier.pm_secteur_rue, dossier.pm_siege_social) if part
        ),
    )
    for name, value in tuple(values.items()):
        if value is None:
            values[name] = ""
        elif isinstance(value, date):
            values[name] = value.strftime("%d/%m/%Y")
        elif isinstance(value, Decimal):
            values[name] = f"{value:,.0f}".replace(",", " ")
    return values


# Coordinates are normalized to the page size. Signature blocks, staff-only
# sections, unknown account numbers, and client-consent boxes are intentionally
# not populated.
PERSONAL_PLACEMENTS = {
    0: (
        ("full_name", .264, .132, .69, .020),
        ("telephone", .264, .158, .69, .020),
        ("email", .264, .184, .69, .020),
        ("boite_postale", .264, .209, .69, .020),
        ("date_embauche", .264, .236, .69, .020),
        ("nom_mere", .264, .264, .69, .020),
        ("conjoint_nom", .266, .520, .68, .019),
        ("conjoint_contact", .286, .610, .65, .019),
        ("urgence_nom_1", .405, .808, .54, .018),
        ("urgence_tel_1", .405, .824, .54, .018),
        ("urgence_prof_1", .405, .841, .54, .018),
        ("urgence_nom_2", .405, .875, .54, .018),
        ("urgence_tel_2", .405, .891, .54, .018),
        ("urgence_prof_2", .405, .907, .54, .018),
    ),
    1: (
        ("nom", .180, .286, .72, .019),
        ("prenoms", .190, .313, .71, .019),
        ("home_address", .188, .340, .36, .019),
        ("telephone", .555, .340, .32, .019),
    ),
    2: (
        ("nom", .180, .286, .72, .019),
        ("prenoms", .190, .313, .71, .019),
        ("home_address", .188, .340, .36, .019),
        ("telephone", .555, .340, .32, .019),
    ),
    3: (
        ("nom", .180, .286, .72, .019),
        ("prenoms", .190, .313, .71, .019),
        ("home_address", .188, .340, .36, .019),
        ("telephone", .555, .340, .32, .019),
    ),
    4: (
        ("quartier", .145, .462, .33, .016),
        ("secteur", .145, .477, .33, .016),
        ("rue", .145, .493, .33, .016),
        ("porte", .145, .509, .22, .016),
        # Correction : le « Pays » du domicile reçoit le pays de résidence.
        ("pays_residence", .460, .509, .08, .016),
        ("repere_proximite", .145, .526, .33, .016),
        ("full_name", .245, .575, .22, .015),
        ("rccm_particulier", .290, .590, .18, .015),
        ("ifu", .220, .605, .25, .015),
        ("nom_jeune_fille", .205, .620, .26, .015),
        ("sexe_label", .120, .665, .34, .015),
        ("date_naissance", .250, .680, .21, .015),
        ("pays_naissance", .210, .700, .25, .015),
        ("nom_pere", .215, .715, .25, .015),
        ("nom_mere", .215, .740, .25, .015),
        ("type_piece_label", .205, .780, .25, .015),
        ("numero_piece", .145, .795, .31, .015),
        ("issue_details", .235, .810, .22, .015),
        ("expiry_date", .115, .825, .34, .015),
        ("marital_status", .220, .840, .24, .015),
        ("regime_matrimonial", .220, .855, .24, .015),
        ("conjoint_nom", .260, .870, .20, .015),
        ("telephone", .645, .590, .25, .015),
        ("telephone_domicile", .645, .605, .25, .015),
        ("pm_telephone_bureau", .645, .620, .25, .015),
        ("email", .555, .635, .34, .015),
        ("nationalite", .665, .770, .23, .015),
    ),
    5: (
        # Correction : « Si salarié, poste occupé » reçoit le poste, pas l'adresse.
        ("poste_occupe", .620, .055, .27, .018),
        ("employeur", .620, .093, .27, .018),
        ("adresse_employeur", .620, .132, .27, .018),
        ("revenu_mensuel", .650, .185, .24, .018),
    ),
    7: (
        ("nom", .170, .286, .70, .018),
        ("prenoms", .170, .309, .70, .018),
        ("adresse_employeur", .170, .333, .70, .018),
        ("telephone", .170, .360, .34, .018),
        ("telephone_secondaire", .570, .360, .30, .018),
        ("home_address", .170, .384, .70, .018),
        ("secteur", .170, .409, .28, .018),
        ("quartier", .510, .409, .36, .018),
        ("repere_proximite", .170, .432, .70, .018),
        ("adresse", .260, .465, .61, .018),
        ("urgence_nom_1", .240, .555, .63, .018),
        ("urgence_prof_1", .240, .579, .63, .018),
        # Correction : lieu de travail de la personne à prévenir (et non de l'employeur du client).
        ("urgence_lieu_travail_1", .240, .602, .63, .018),
        ("urgence_tel_1", .240, .650, .63, .018),
        ("urgence_adresse_1", .240, .673, .63, .018),
        ("full_name", .300, .805, .56, .018),
    ),
}

COMMERCIAL_PLACEMENTS = {
    0: (
        ("pm_raison_sociale", .30, .535, .56, .023),
        ("pm_siege_social", .32, .570, .54, .023),
        ("pm_secteur_rue", .26, .603, .57, .023),
    ),
    1: (
        ("pm_raison_sociale", .36, .287, .46, .022),
        ("pm_siege_social", .30, .310, .52, .022),
        ("pm_numero_rccm", .27, .385, .50, .018),
        ("pm_activite_principale", .24, .400, .52, .018),
        ("pm_siege_social", .22, .405, .55, .014),
    ),
    2: (
        ("pm_activite_principale", .34, .335, .55, .018),
        ("pm_numero_rccm", .32, .354, .56, .018),
        ("pm_siege_social", .30, .438, .58, .018),
        ("pm_email", .30, .458, .58, .018),
        ("company_address", .30, .480, .58, .018),
        ("pm_telephone_bureau", .32, .545, .28, .018),
        ("telephone", .28, .568, .58, .018),
        ("urgence_nom_1", .30, .638, .58, .018),
        ("urgence_adresse_1", .30, .659, .58, .018),
        ("urgence_tel_1", .30, .702, .58, .018),
    ),
    3: (
        ("pm_actionnaire_1", .09, .450, .29, .026),
        ("pm_actionnaire_2", .09, .485, .29, .026),
        ("full_name", .09, .660, .19, .026),
        ("date_naissance", .30, .660, .09, .026),
        ("pm_fonction_mandataire", .41, .660, .10, .026),
        ("nationalite", .52, .660, .10, .026),
        ("ville_residence", .63, .660, .09, .026),
        ("numero_piece", .73, .660, .11, .026),
    ),
    4: (
        ("pm_chiffre_affaires", .53, .132, .34, .07),
    ),
    5: (
        ("pm_raison_sociale", .25, .218, .60, .018),
        ("pm_siege_social", .25, .247, .60, .018),
        ("pm_siege_social", .22, .275, .27, .018),
        ("full_name", .30, .335, .55, .018),
        ("pm_fonction_mandataire", .26, .360, .58, .018),
    ),
    6: (
        ("pm_raison_sociale", .25, .218, .60, .018),
        ("pm_siege_social", .25, .247, .60, .018),
        ("pm_siege_social", .22, .275, .27, .018),
        ("full_name", .30, .335, .55, .018),
        ("pm_fonction_mandataire", .26, .360, .58, .018),
    ),
    7: (
        ("pm_raison_sociale", .25, .218, .60, .018),
        ("pm_siege_social", .25, .247, .60, .018),
        ("pm_siege_social", .22, .275, .27, .018),
        ("full_name", .30, .335, .55, .018),
        ("pm_fonction_mandataire", .26, .360, .58, .018),
    ),
    8: (
        ("full_name", .17, .286, .70, .018),
        ("adresse_employeur", .17, .333, .70, .018),
        ("pm_telephone_bureau", .17, .360, .34, .018),
        ("urgence_tel_1", .57, .360, .30, .018),
        ("company_address", .17, .384, .70, .018),
        ("urgence_nom_1", .24, .555, .63, .018),
        ("urgence_prof_1", .24, .579, .63, .018),
        ("urgence_tel_1", .24, .626, .63, .018),
        ("full_name", .30, .760, .56, .018),
    ),
    10: PERSONAL_PLACEMENTS[0],
    11: PERSONAL_PLACEMENTS[4],
    12: PERSONAL_PLACEMENTS[5],
    13: PERSONAL_PLACEMENTS[7],
    14: (
        ("pm_raison_sociale", .32, .090, .42, .020),
        ("ville_residence", .18, .145, .32, .020),
        ("nom", .14, .550, .34, .020),
        ("prenoms", .14, .585, .34, .020),
        ("date_naissance", .30, .615, .24, .020),
        ("lieu_naissance", .62, .615, .24, .020),
        ("numero_piece", .28, .675, .30, .020),
        ("piece_delivree_le", .16, .710, .30, .020),
        ("piece_delivree_a", .14, .745, .34, .020),
        ("nationalite", .20, .790, .34, .020),
        ("profession", .36, .830, .38, .020),
        ("home_address", .20, .870, .70, .020),
        ("telephone", .20, .900, .34, .020),
    ),
    15: (
        ("full_name", .56, .400, .36, .020),
        ("date_naissance", .22, .430, .32, .020),
        ("lieu_naissance", .84, .430, .12, .020),
        ("numero_piece", .50, .460, .20, .020),
        ("piece_delivree_a", .76, .460, .18, .020),
        ("piece_delivree_le", .08, .490, .34, .020),
        ("nationalite", .30, .550, .25, .020),
        ("pm_fonction_mandataire", .38, .600, .42, .020),
        ("pm_raison_sociale", .66, .660, .30, .020),
        ("pm_capital_social", .24, .690, .65, .020),
        ("pm_siege_social", .80, .720, .14, .020),
        ("pm_activite_principale", .34, .750, .59, .020),
        ("pm_numero_rccm", .48, .780, .45, .020),
    ),
}

# Cases à cocher (page index, x pour « Oui », x pour « Non », y).
# FATCA et PPE : positions reprises du code existant.
# Levée du secret bancaire : positions ESTIMÉES d'après le scan, à calibrer
# en imprimant un dossier de test (ajuster SECRET_BANCAIRE_* si la croix est décalée).
FATCA_BOX = (5, .310, .392, .552)
PPE_BOX = (6, .705, .835, .407)
SECRET_BANCAIRE_BOX = (5, .310, .392, .594)

# Formes juridiques → case du formulaire commercial. « SAS » n'a pas de case dédiée : « Autre ».
LEGAL_FORM_BOXES = {
    "SARL": (.45, .276),
    "SA": (.55, .276),
    "ONG": (.84, .276),
    "EI": (.55, .309),
    "AUTRE": (.67, .309),
}
LEGAL_FORM_ALIASES = {"SAS": "AUTRE"}


def _draw_text(page, value, x, y, width, height, field_name):
    text = str(value).strip()
    if not text:
        return
    rect = pymupdf.Rect(
        x * page.rect.width,
        y * page.rect.height,
        (x + width) * page.rect.width,
        (y + height) * page.rect.height,
    )
    for size in (8, 7, 6, 5):
        remaining = page.insert_textbox(
            rect,
            text,
            fontsize=size,
            fontname="helv",
            color=(0, 0, 0),
            align=pymupdf.TEXT_ALIGN_LEFT,
            overlay=True,
        )
        if remaining >= 0:
            return
    raise PdfValueTooLong(
        f"La valeur du champ « {field_name} » est trop longue pour le formulaire officiel."
    )


def _draw_cross(page, x, y):
    page.insert_text(
        (x * page.rect.width, y * page.rect.height),
        "X",
        fontsize=8,
        fontname="helv",
        color=(0, 0, 0),
        overlay=True,
    )


def _draw_yes_no(document, box, answer):
    """Coche Oui ou Non. Si la réponse est vide (None), ne coche rien."""
    if answer is None:
        return
    page_number, x_yes, x_no, y = box
    _draw_cross(document[page_number], x_yes if answer else x_no, y)


def generate_official_pdf(dossier):
    template_name = (
        COMMERCIAL_TEMPLATE
        if dossier.type_compte == DossierClient.TypeCompte.COMMERCIAL
        else PERSONAL_TEMPLATE
    )
    template_path = Path(settings.BASE_DIR) / template_name
    if not template_path.is_file():
        raise FileNotFoundError(f"Formulaire officiel introuvable : {template_name}")

    document = pymupdf.open(template_path)
    values = _values(dossier)

    if dossier.type_compte == DossierClient.TypeCompte.PARTICULIER:
        for page_number, placements in PERSONAL_PLACEMENTS.items():
            page = document[page_number]
            for name, x, y, width, height in placements:
                _draw_text(page, values.get(name, ""), x, y, width, height, name)
        # Déclarations du client : cochées uniquement si une réponse explicite existe.
        _draw_yes_no(document, FATCA_BOX, dossier.est_us_person)
        _draw_yes_no(document, PPE_BOX, dossier.est_ppe)
        _draw_yes_no(document, SECRET_BANCAIRE_BOX, dossier.levee_secret_bancaire)
    else:
        for page_number, placements in COMMERCIAL_PLACEMENTS.items():
            page = document[page_number]
            for name, x, y, width, height in placements:
                _draw_text(page, values.get(name, ""), x, y, width, height, name)

        form_key = LEGAL_FORM_ALIASES.get(dossier.pm_forme_juridique, dossier.pm_forme_juridique)
        position = LEGAL_FORM_BOXES.get(form_key)
        if position:
            _draw_cross(document[2], *position)

    output = document.tobytes(garbage=3, deflate=True)
    document.close()
    return output