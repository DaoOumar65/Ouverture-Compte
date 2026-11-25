"""Read-only access to the central Amplitude customer/account database."""

import re
from datetime import date, datetime

from django.conf import settings


class AmplitudeNotConfigured(Exception):
    """Raised when the Amplitude connection settings are incomplete."""


class AmplitudeConnectionError(Exception):
    """Raised when Oracle cannot be reached or queried."""


class AmplitudeAmbiguousClient(Exception):
    """Raised when the account lookup points to more than one customer."""


_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,29}$")


def _connection_parameters():
    sid = settings.AMPLITUDE_SID
    service_name = settings.AMPLITUDE_NOM_SERVICE
    if (
        not settings.AMPLITUDE_HOTE
        or not settings.AMPLITUDE_UTILISATEUR
        or not settings.AMPLITUDE_MOT_DE_PASSE
        or bool(sid) == bool(service_name)
    ):
        raise AmplitudeNotConfigured
    schema = settings.AMPLITUDE_SCHEMA
    if not _IDENTIFIER_RE.fullmatch(schema):
        raise AmplitudeNotConfigured

    params = {
        "user": settings.AMPLITUDE_UTILISATEUR,
        "password": settings.AMPLITUDE_MOT_DE_PASSE,
        "host": settings.AMPLITUDE_HOTE,
        "port": settings.AMPLITUDE_PORT,
        "tcp_connect_timeout": settings.AMPLITUDE_TIMEOUT_S,
    }
    params["sid" if sid else "service_name"] = sid or service_name
    return schema.upper(), params


def _date_value(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return ""


def _put(fields, name, value):
    if value is None:
        return
    if isinstance(value, (date, datetime)):
        value = _date_value(value)
    elif isinstance(value, str):
        value = value.strip()
    if value != "":
        fields[name] = str(value) if not isinstance(value, (int, float, bool)) else value


def _type_piece(type_code):
    """Map only explicit labels; opaque Amplitude codes must be confirmed."""
    value = (type_code or "").strip().upper()
    if "PASSEPORT" in value or "PASSPORT" in value:
        return "PASSEPORT"
    if "CNIB" in value:
        return "CNIB"
    if "CARTE SEJOUR" in value or "CARTE_SÉJOUR" in value or "CARTE_SEJOUR" in value:
        return "CARTE_SEJOUR"
    return ""


def rechercher_client_par_compte(numero_compte, agence):
    """Return Django form values for the customer attached to an account.

    The account lookup is intentionally read-only and uses bind parameters for
    all supplied values. Oracle identifiers come only from validated settings.
    """
    account = "".join((numero_compte or "").split())
    branch = (agence or "").strip().upper()
    if not account or len(account) > 11 or not branch or len(branch) > 5:
        raise ValueError("Saisissez un numéro de compte (11 caractères maximum) et un code agence valide.")

    # bkcom.ncp and bkcom.age are fixed-width CHAR columns (11 and 5 chars).
    # Pad the binds rather than wrapping indexed columns in TRIM(), preserving
    # the account/agency index lookup while matching Oracle's CHAR storage.
    account_bind = account.ljust(11)
    branch_bind = branch.ljust(5)

    schema, params = _connection_parameters()
    try:
        import oracledb

        with oracledb.connect(**params) as connection:
            connection.call_timeout = int(settings.AMPLITUDE_TIMEOUT_S * 1000)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""SELECT DISTINCT TRIM(cli)
                        FROM {schema}.bkcom
                        WHERE ncp = :numero_compte
                          AND age = :agence
                          AND TRIM(cli) IS NOT NULL""",
                    numero_compte=account_bind,
                    agence=branch_bind,
                )
                clients = [row[0] for row in cursor.fetchmany(2)]
                if not clients:
                    return None
                if len(clients) > 1:
                    raise AmplitudeAmbiguousClient
                client_bind = clients[0].ljust(15)

                cursor.execute(
                    f"""SELECT TRIM(nom), TRIM(pre), TRIM(midname), TRIM(sext),
                               dna, TRIM(viln), TRIM(njf), TRIM(nid), TRIM(tid), did,
                               TRIM(lid), TRIM(oid), vid, TRIM(nmer), tcli,
                               TRIM(conj), nbenf,
                               TRIM(rso), TRIM(sig), datc, TRIM(nrc), TRIM(nidf)
                        FROM {schema}.bkcli
                        WHERE cli = :code_client""",
                    code_client=client_bind,
                )
                row = cursor.fetchone()
                if not row:
                    return None

                (
                    nom, prenom, deuxieme_prenom, sexe, naissance, lieu_naissance,
                    nom_jeune_fille, numero_piece, type_piece_code, piece_delivree_le,
                    piece_delivree_a, piece_delivree_par, piece_expire_le,
                    nom_mere, type_client, code_conjoint, nombre_enfants,
                    raison_sociale, sigle, date_creation, rccm, ifu,
                ) = row

                fields = {"numero_compte_bcb_existant": account}
                type_client = str(type_client or "").strip()
                if type_client in {"2", "3"}:
                    _put(fields, "pm_raison_sociale", raison_sociale or nom)
                    _put(fields, "pm_sigle", sigle)
                    _put(fields, "pm_date_creation", date_creation)
                    _put(fields, "pm_numero_rccm", rccm)
                    _put(fields, "pm_ifu", ifu)
                if type_client in {"1", "3"}:
                    _put(fields, "nom", nom)
                    _put(fields, "prenoms", " ".join(part for part in (prenom, deuxieme_prenom) if part))
                    _put(fields, "sexe", sexe)
                    _put(fields, "date_naissance", naissance)
                    _put(fields, "lieu_naissance", lieu_naissance)
                    _put(fields, "nom_jeune_fille", nom_jeune_fille)
                    _put(fields, "numero_piece", numero_piece)
                    fields["type_piece"] = _type_piece(type_piece_code)
                    _put(fields, "piece_delivree_le", piece_delivree_le)
                    _put(fields, "piece_delivree_a", piece_delivree_a)
                    _put(fields, "piece_delivree_par", piece_delivree_par)
                    _put(fields, "piece_expire_le", piece_expire_le)
                    _put(fields, "nom_mere", nom_mere)
                    _put(fields, "nombre_enfants", nombre_enfants)

                    if code_conjoint:
                        cursor.execute(
                            f"""SELECT TRIM(nom), TRIM(pre), TRIM(midname), dna,
                                       TRIM(viln), TRIM(nid), TRIM(tid),
                                       did, TRIM(lid), TRIM(oid), vid, TRIM(nmer)
                                FROM {schema}.bkcli
                                WHERE cli = :code_client""",
                            code_client=code_conjoint.ljust(15),
                        )
                        conjoint = cursor.fetchone()
                        if conjoint:
                            (
                                conj_nom, conj_prenom, conj_deuxieme_prenom,
                                conj_naissance, conj_lieu_naissance,
                                conj_numero_piece,
                                conj_type_piece_code, conj_piece_delivree_le,
                                conj_piece_delivree_a, conj_piece_delivree_par,
                                conj_piece_expire_le, conj_nom_mere,
                            ) = conjoint
                            _put(fields, "conjoint_nom", " ".join(
                                part for part in (conj_prenom, conj_deuxieme_prenom, conj_nom)
                                if part
                            ))
                            _put(fields, "conjoint_date_naissance", conj_naissance)
                            _put(fields, "conjoint_ville_naissance", conj_lieu_naissance)
                            _put(fields, "conjoint_numero_piece", conj_numero_piece)
                            _put(fields, "conjoint_piece_delivree_le", conj_piece_delivree_le)
                            _put(fields, "conjoint_piece_delivree_a", conj_piece_delivree_a)
                            _put(fields, "conjoint_piece_delivree_par", conj_piece_delivree_par)
                            _put(fields, "conjoint_piece_expire_le", conj_piece_expire_le)
                            _put(fields, "conjoint_nom_mere", conj_nom_mere)
                            conj_type_piece = _type_piece(conj_type_piece_code)
                            if conj_type_piece:
                                fields["conjoint_type_piece"] = conj_type_piece

                cursor.execute(
                    f"""SELECT TRIM(adr1), TRIM(adr2), TRIM(adr3), TRIM(ville),
                               TRIM(email)
                        FROM {schema}.bkadcli
                        WHERE cli = :code_client
                          AND typ IN ('C', 'F')
                          AND (dprvf IS NULL OR dprvf >= SYSDATE)
                        ORDER BY CASE WHEN typ = 'C' THEN 0 ELSE 1 END,
                                 dprvd DESC NULLS FIRST""",
                    code_client=client_bind,
                )
                address = cursor.fetchone()
                if address:
                    adr1, adr2, adr3, ville, email = address
                    adresse = ", ".join(
                        part.strip() for part in (adr1, adr2, adr3)
                        if part and part.strip()
                    )
                    if type_client == "2":
                        _put(fields, "pm_siege_social", ", ".join(part for part in (adresse, ville) if part))
                        _put(fields, "pm_secteur_rue", adresse)
                        _put(fields, "pm_email", email)
                    else:
                        _put(fields, "adresse", adresse)
                        _put(fields, "ville_residence", ville)
                        _put(fields, "email", email)
                return {"fields": fields, "client_type": type_client}
    except (AmplitudeNotConfigured, AmplitudeAmbiguousClient):
        raise
    except ImportError as exc:
        raise AmplitudeNotConfigured from exc
    except Exception as exc:
        raise AmplitudeConnectionError from exc
