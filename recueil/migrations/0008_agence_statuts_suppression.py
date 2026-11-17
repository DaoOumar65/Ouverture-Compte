# Généré manuellement — migration en 3 étapes pour convertir
# UserProfile.agence (CharField) → FK vers le nouveau modèle Agence,
# sans perdre les données existantes.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


AGENCES_INITIALES = [
    ("1001", "Siège", "Ouagadougou"),
    ("1002", "Agence Centrale", "Ouagadougou"),
    ("1003", "Agence Paspanga", "Ouagadougou"),
    ("1004", "Agence Gounghin", "Ouagadougou"),
    ("1005", "Agence Zone du Bois", "Ouagadougou"),
    ("1006", "Agence Pissy", "Ouagadougou"),
    ("1007", "Agence Tampouy", "Ouagadougou"),
    ("1008", "Agence Bobo-Dioulasso", "Bobo-Dioulasso"),
    ("1009", "Agence Bobo Secteur 22", "Bobo-Dioulasso"),
    ("1010", "Agence Koudougou", "Koudougou"),
    ("1011", "Agence Banfora", "Banfora"),
    ("1012", "Agence Fada N'Gourma", "Fada N'Gourma"),
    ("1013", "Agence Kaya", "Kaya"),
    ("1014", "Agence Dédougou", "Dédougou"),
    ("1015", "Agence Ouahigouya", "Ouahigouya"),
    ("1016", "Agence Tenkodogo", "Tenkodogo"),
    ("1017", "Agence Réo", "Réo"),
]


def creer_agences_et_migrer(apps, schema_editor):
    """Créer les agences par défaut et rattacher les profils existants."""
    Agence = apps.get_model("recueil", "Agence")
    UserProfile = apps.get_model("recueil", "UserProfile")

    # Créer les agences de référence
    agences_par_nom = {}
    for numero, nom, ville in AGENCES_INITIALES:
        a, _ = Agence.objects.get_or_create(
            numero=numero,
            defaults={"nom": nom, "ville": ville, "active": True},
        )
        agences_par_nom[nom.lower()] = a
        # Alias pour correspondance souple
        agences_par_nom[nom.replace("Agence ", "").lower()] = a

    # Migrer les profils existants : chercher l'agence par correspondance de nom
    for profil in UserProfile.objects.using(schema_editor.connection.alias).all():
        old_val = profil.agence_old or ""
        if not old_val:
            continue
        # Cherche une correspondance
        old_lower = old_val.lower()
        matched = None
        for key, agence in agences_par_nom.items():
            if key in old_lower or old_lower in key:
                matched = agence
                break
        if matched:
            profil.agence = matched
            profil.save(using=schema_editor.connection.alias, update_fields=["agence"])


def retour_arriere(apps, schema_editor):
    """Remettre le nom de l'agence dans le champ texte."""
    UserProfile = apps.get_model("recueil", "UserProfile")
    for profil in UserProfile.objects.using(schema_editor.connection.alias).select_related("agence").all():
        if profil.agence:
            profil.agence_old = profil.agence.nom
            profil.save(using=schema_editor.connection.alias, update_fields=["agence_old"])


class Migration(migrations.Migration):

    dependencies = [
        ('recueil', '0007_dossierclient_categorie_client_autre'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Créer le modèle Agence
        migrations.CreateModel(
            name='Agence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=150, verbose_name="Nom de l'agence")),
                ('numero', models.CharField(max_length=20, unique=True, verbose_name="Numéro d'agence")),
                ('ville', models.CharField(default='Ouagadougou', max_length=80, verbose_name='Ville')),
                ('active', models.BooleanField(default=True, verbose_name='Active')),
            ],
            options={
                'verbose_name': 'Agence',
                'verbose_name_plural': 'Agences',
                'ordering': ['numero'],
            },
        ),

        # 2. Renommer l'ancien champ agence (texte) pour garder les données
        migrations.RenameField(
            model_name='userprofile',
            old_name='agence',
            new_name='agence_old',
        ),

        # 3. Ajouter la nouvelle FK agence (nullable)
        migrations.AddField(
            model_name='userprofile',
            name='agence',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='gestionnaires',
                to='recueil.agence',
                verbose_name='Agence',
            ),
        ),

        # 4. Migrer les données : créer les agences de référence + rattacher les profils
        migrations.RunPython(creer_agences_et_migrer, retour_arriere),

        # 5. Supprimer l'ancien champ texte agence_old
        migrations.RemoveField(
            model_name='userprofile',
            name='agence_old',
        ),

        # 6. Champs de suppression logique sur DossierClient
        migrations.AddField(
            model_name='dossierclient',
            name='supprime_le',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Supprimé le'),
        ),
        migrations.AddField(
            model_name='dossierclient',
            name='supprime_par',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='dossiers_supprimes',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Supprimé par',
            ),
        ),

        # 7. Nouveaux statuts et action d'audit
        migrations.AlterField(
            model_name='dossierauditevent',
            name='action',
            field=models.CharField(
                choices=[
                    ('CREATION', 'Création'),
                    ('MODIFICATION', 'Modification'),
                    ('GENERATION', 'Génération'),
                    ('IMPRESSION', 'Impression'),
                    ('CONSULTATION', 'Consultation'),
                    ('SIGNATURE', 'Signature'),
                    ('REUTILISATION', 'Réutilisation'),
                    ('RECHERCHE_CLIENT', 'Recherche client'),
                    ('SUPPRESSION', 'Suppression (brouillon)'),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='dossierclient',
            name='statut',
            field=models.CharField(
                choices=[
                    ('BROUILLON', 'Brouillon (En cours)'),
                    ('CREE', 'Créé'),
                    ('GENERE', 'Généré & Prêt pour impression'),
                    ('DESACTIVE', 'Désactivé'),
                ],
                default='BROUILLON',
                max_length=20,
            ),
        ),
    ]
