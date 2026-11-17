from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group

from .models import Agence, DossierAuditEvent, DossierClient, UserProfile
from .permissions import ADMIN_GROUP, has_role


class RoleRestrictedAdminSite(AdminSite):
    site_header = "Administration BCB Recueil"
    site_title = "Administration BCB"
    index_title = "Gestion des utilisateurs et consultation"

    def has_permission(self, request):
        return (
            request.user.is_active
            and request.user.is_staff
            and has_role(request.user, ADMIN_GROUP)
        )


admin_site = RoleRestrictedAdminSite(name="admin")


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0


class UserAdmin(DjangoUserAdmin):
    inlines = (UserProfileInline,)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        user = form.instance
        is_admin_user = user.groups.filter(name=ADMIN_GROUP).exists()
        new_is_staff = user.is_superuser or is_admin_user
        if user.is_staff != new_is_staff:
            user.is_staff = new_is_staff
            user.save(update_fields=["is_staff"])


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DossierClient, site=admin_site)
class DossierClientAdmin(ReadOnlyAdmin):
    list_display = (
        "reference", "nom", "prenoms", "type_compte", "statut",
        "cree_par", "cree_le", "maj_le",
    )
    list_filter = ("type_compte", "statut")
    search_fields = ("reference", "nom", "prenoms", "numero_piece")
    readonly_fields = tuple(
        field.name
        for field in DossierClient._meta.fields
        if field.name != "pdf_fige"
    )

    def has_view_permission(self, request, obj=None):
        return has_role(request.user, ADMIN_GROUP)

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DossierAuditEvent, site=admin_site)
class DossierAuditEventAdmin(ReadOnlyAdmin):
    list_display = ("date", "action", "dossier", "utilisateur")
    list_filter = ("action", "date")
    search_fields = ("dossier__reference", "utilisateur__username")
    readonly_fields = tuple(
        field.name for field in DossierAuditEvent._meta.fields
    )

    def has_view_permission(self, request, obj=None):
        return has_role(request.user, ADMIN_GROUP)

    def has_change_permission(self, request, obj=None):
        return False


admin_site.register(get_user_model(), UserAdmin)
admin_site.register(UserProfile)
admin_site.register(Group)


@admin.register(Agence, site=admin_site)
class AgenceAdmin(admin.ModelAdmin):
    list_display = ("numero", "nom", "ville", "active", "nb_gestionnaires")
    list_filter = ("active", "ville")
    search_fields = ("nom", "numero", "ville")
    ordering = ("numero",)
    fields = ("numero", "nom", "ville", "active")

    def nb_gestionnaires(self, obj):
        return obj.gestionnaires.count()
    nb_gestionnaires.short_description = "Gestionnaires"

    def has_view_permission(self, request, obj=None):
        return has_role(request.user, ADMIN_GROUP)

    def has_add_permission(self, request):
        return has_role(request.user, ADMIN_GROUP)

    def has_change_permission(self, request, obj=None):
        return has_role(request.user, ADMIN_GROUP)

    def has_delete_permission(self, request, obj=None):
        return has_role(request.user, ADMIN_GROUP)
