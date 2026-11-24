from .models import ADAccessRequest


def access_approval_notifications(request):
    is_admin_role = bool(
        request.user.is_authenticated
        and (
            request.user.is_superuser
            or request.user.groups.filter(name="ADMIN").exists()
        )
    )
    pending_count = (
        ADAccessRequest.objects.filter(status=ADAccessRequest.Status.PENDING).count()
        if is_admin_role else 0
    )
    return {
        "is_admin_role": is_admin_role,
        "demandes_acces_ad_en_attente": pending_count,
    }
