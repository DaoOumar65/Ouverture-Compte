from django.db import migrations


AGENCES_BCB = (
    ("01001", "AGENCE SIEGE"),
    ("01002", "AGENCE KWAME"),
    ("01003", "AGENCENATION"),
    ("01005", "AGENCE PATTE DOIE"),
    ("01006", "AGENCE WAYALGHIN"),
    ("01007", "AGENCE TAMPOUY"),
    ("02001", "AGENCE BOBO"),
    ("12001", "AGENCE TENKODOGO"),
    ("12002", "GUICHET BITOU"),
    ("22001", "AGENCE ORODARA"),
    ("37001", "GUICHET GARANGO"),
    ("01008", "AGENCE PISSY"),
    ("01009", "AGENCE BONHEUR-VILLE"),
    ("01010", "AGENCE WEMTENGA"),
    ("05002", "AGENCE KOUDOUGOU"),
    ("08001", "AGENCE ZINIARE"),
    ("01015", "AGENCE NAGRIN"),
    ("16001", "AGENCE GAOUA"),
    ("15001", "AGENCE DORI"),
    ("05001", "AGENCE KOUDOUGOU"),
    ("06001", "AGENCE OUAHIGOUYA"),
    ("07001", "AGENCE PO"),
    ("11001", "AGENCE KAYA"),
    ("02002", "AGENCE BOBO 2"),
    ("01014", "SAABA COTE OUEST DU MARCHE"),
    ("13001", "AGENCE BOROMO"),
    ("01011", "AGENCE BALKUY"),
    ("01012", "AGENCE KAMBOINSIN"),
)


def sync_agences(apps, schema_editor):
    Agence = apps.get_model("recueil", "Agence")
    db = schema_editor.connection.alias

    # Keep old rows to preserve user-profile foreign keys and dossier history.
    Agence.objects.using(db).all().update(active=False)

    for code, nom in AGENCES_BCB:
        agency = Agence.objects.using(db).filter(numero=code).first()
        if agency is None:
            # Older seed data omitted the leading zero from five-digit codes.
            legacy_code = str(int(code))
            agency = Agence.objects.using(db).filter(numero=legacy_code).first()
            if agency is not None:
                agency.numero = code
                agency.nom = nom
                agency.active = True
                agency.save(using=db, update_fields=("numero", "nom", "active"))
                continue

        if agency is None:
            Agence.objects.using(db).create(numero=code, nom=nom, active=True)
        else:
            agency.nom = nom
            agency.active = True
            agency.save(using=db, update_fields=("nom", "active"))


class Migration(migrations.Migration):
    dependencies = [("recueil", "0018_adaccessrequest_unique_pending_ad_access_per_user")]

    operations = [migrations.RunPython(sync_agences, migrations.RunPython.noop)]
