from django.conf import settings
from django.db import migrations, models
from django.db.models import F
import django.db.models.deletion


def backfill_initiator_snapshot(apps, schema_editor):
    DossierClient = apps.get_model("recueil", "DossierClient")
    db = schema_editor.connection.alias
    DossierClient.objects.using(db).update(
        initiateur_snapshot=F("charge_affaires_snapshot")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("recueil", "0020_draft_agency_sharing_and_piece_index"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="dossierclient",
            name="initiateur_snapshot",
            field=models.CharField(
                blank=True,
                default="",
                max_length=150,
                verbose_name="Gestionnaire ayant initié le brouillon",
            ),
        ),
        migrations.AddField(
            model_name="dossierclient",
            name="termine_par",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="dossiers_termines",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Gestionnaire ayant terminé le dossier",
            ),
        ),
        migrations.RunPython(backfill_initiator_snapshot, migrations.RunPython.noop),
    ]
