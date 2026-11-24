from getpass import getpass

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Provision the first trusted AD administrator after validating their AD credentials."

    def handle(self, *args, **options):
        if settings.AUTH_MODE != "AD":
            raise CommandError("Set AUTH_MODE=AD before bootstrapping an AD administrator.")

        username = input("Identifiant Active Directory : ").strip()
        password = getpass("Mot de passe Active Directory : ")
        user = authenticate(username=username, password=password)
        password = None
        if user is None:
            raise CommandError("Active Directory n'a pas validé ces identifiants.")

        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=user.pk)
            user.is_staff = True
            user.is_superuser = True
            user.set_unusable_password()
            user.save(update_fields=("is_staff", "is_superuser", "password"))

            admin_group, _ = Group.objects.get_or_create(name="ADMIN")
            user.groups.add(admin_group)

            profile = user.profile
            profile.ad_access_approved = True
            profile.nom_affiche = user.get_full_name() or user.get_username()
            profile.save(update_fields=("ad_access_approved", "nom_affiche"))

        self.stdout.write(self.style.SUCCESS(
            f"L'identité AD {user.get_username()} a été validée et configurée comme administrateur initial."
        ))
