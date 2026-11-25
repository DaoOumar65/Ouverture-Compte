from django.db import migrations, models


def backfill_dossier_index(apps, schema_editor):
    DossierClient = apps.get_model("recueil", "DossierClient")
    DossierIdentiteVerrou = apps.get_model("recueil", "DossierIdentiteVerrou")
    UserProfile = apps.get_model("recueil", "UserProfile")
    db = schema_editor.connection.alias
    agence_par_utilisateur = dict(
        UserProfile.objects.using(db)
        .exclude(agence_id=None)
        .values_list("user_id", "agence__numero")
    )
    dossiers = DossierClient.objects.using(db).only(
        "pk", "cree_par_id", "numero_piece", "agence_numero_snapshot"
    )
    for dossier in dossiers.iterator():
        numero = "".join(
            character for character in (dossier.numero_piece or "") if character.isalnum()
        ).upper()
        agence_numero = agence_par_utilisateur.get(dossier.cree_par_id, "")
        DossierClient.objects.using(db).filter(pk=dossier.pk).update(
            numero_piece_normalise=numero,
            agence_numero_snapshot=dossier.agence_numero_snapshot or agence_numero,
        )

    identities = set()
    for dossier in DossierClient.objects.using(db).filter(
        statut__in=("CREE", "GENERE")
    ).order_by("cree_le", "pk").only(
        "pk", "type_compte", "numero_piece_normalise"
    ).iterator():
        identity = (dossier.type_compte, dossier.numero_piece_normalise)
        if not dossier.numero_piece_normalise or identity in identities:
            continue
        DossierIdentiteVerrou.objects.using(db).create(
            type_compte=dossier.type_compte,
            numero_piece_normalise=dossier.numero_piece_normalise,
            dossier_id=dossier.pk,
        )
        identities.add(identity)


class Migration(migrations.Migration):
    dependencies = [("recueil", "0019_sync_official_agences")]

    operations = [
        migrations.AddField(
            model_name="dossierclient",
            name="agence_numero_snapshot",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=20,
                verbose_name="Code agence à la création",
            ),
        ),
        migrations.AddField(
            model_name="dossierclient",
            name="numero_piece_normalise",
            field=models.CharField(
                blank=True, db_index=True, default="", editable=False, max_length=60,
                verbose_name="Numéro de pièce normalisé",
            ),
        ),
        migrations.CreateModel(
            name="DossierIdentiteVerrou",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("type_compte", models.CharField(choices=[("PARTICULIER", "Particulier (Personne Physique)"), ("COMMERCIAL", "Commercial (Entreprise / Personne Morale)")], max_length=20)),
                ("numero_piece_normalise", models.CharField(max_length=60)),
                ("dossier", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="verrou_identite", to="recueil.dossierclient")),
            ],
        ),
        migrations.AddConstraint(
            model_name="dossieridentiteverrou",
            constraint=models.UniqueConstraint(fields=("type_compte", "numero_piece_normalise"), name="uniq_created_type_piece_identity"),
        ),
        migrations.RunPython(backfill_dossier_index, migrations.RunPython.noop),
    ]
