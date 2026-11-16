from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from .models import DossierAuditEvent, DossierClient, UserProfile


@receiver(post_save, sender=get_user_model())
def create_user_profile(sender, instance, **kwargs):
    UserProfile.objects.get_or_create(user=instance)


@receiver(post_migrate)
def create_roles_and_permissions(sender, **kwargs):
    if sender.name != "recueil":
        return

    manager_group, _ = Group.objects.get_or_create(name="GESTIONNAIRE")
    admin_group, _ = Group.objects.get_or_create(name="ADMIN")

    user_model = get_user_model()
    user_ct = ContentType.objects.get_for_model(user_model)
    group_ct = ContentType.objects.get_for_model(Group)
    profile_ct = ContentType.objects.get_for_model(UserProfile)
    dossier_ct = ContentType.objects.get_for_model(DossierClient)
    audit_ct = ContentType.objects.get_for_model(DossierAuditEvent)

    permission_specs = (
        (user_ct, ("view_user", "add_user", "change_user")),
        (group_ct, ("view_group", "add_group", "change_group")),
        (profile_ct, ("view_userprofile", "add_userprofile", "change_userprofile")),
        (dossier_ct, ("view_dossierclient",)),
        (audit_ct, ("view_dossierauditevent",)),
    )
    permission_ids = [
        permission.pk
        for content_type, codenames in permission_specs
        for permission in Permission.objects.filter(
            content_type=content_type,
            codename__in=codenames,
        )
    ]
    admin_group.permissions.set(permission_ids)
    manager_group.permissions.clear()
