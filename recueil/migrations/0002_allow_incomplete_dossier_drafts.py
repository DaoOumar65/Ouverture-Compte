from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recueil", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dossierclient",
            name="date_naissance",
            field=models.DateField(
                blank=True, null=True, verbose_name="Date de naissance"
            ),
        ),
    ]
