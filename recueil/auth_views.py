from django.conf import settings
from django.contrib.auth.views import LoginView
from django.shortcuts import render
from .models import ADAccessRequest, DossierAuditEvent


class BCBLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True
    next_page = "recueil:dossier-list"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ad_mode"] = settings.AUTH_MODE == "AD"
        return context

    def form_valid(self, form):
        user = form.get_user()
        if settings.AUTH_MODE == "AD" and not user.profile.ad_access_approved:
            pending, demande_creee = ADAccessRequest.objects.get_or_create(
                user=user,
                status=ADAccessRequest.Status.PENDING,
            )
            if demande_creee:
                DossierAuditEvent.objects.create(
                    action=DossierAuditEvent.Action.ACCES_DEMANDE,
                    utilisateur=user,
                    details={"origine": "authentification_active_directory"},
                )

            return render(
                self.request,
                "registration/access_pending.html",
                {
                    "demande": pending,
                    "demande_creee": demande_creee,
                    "rejet_precedent": ADAccessRequest.objects.filter(
                        user=user,
                        status=ADAccessRequest.Status.REJECTED,
                    ).exists(),
                },
            )

        return super().form_valid(form)
