from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect


class ActiveDirectorySessionMiddleware:
    """Invalidate local-backend sessions and block unapproved AD identities."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.AUTH_MODE == "AD" and request.user.is_authenticated:
            backend = request.session.get("_auth_user_backend")
            approved = getattr(
                getattr(request.user, "profile", None),
                "ad_access_approved",
                False,
            )
            if backend != "recueil.auth_backends.ActiveDirectoryBackend" or not approved:
                logout(request)
                return redirect("login")
        return self.get_response(request)
