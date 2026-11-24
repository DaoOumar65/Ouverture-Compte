from django.urls import path

from . import views

app_name = "recueil"

urlpatterns = [
    path("", views.dossier_list, name="dossier-list"),
    path("dossiers/nouveau/", views.dossier_create, name="dossier-create"),
    path("clients/rechercher/", views.recherche_client, name="recherche-client"),
    path("journal/", views.journal_audit, name="journal-audit"),
    # Gestion des gestionnaires (Admin uniquement)
    path("utilisateurs/", views.gestion_utilisateurs, name="gestion-utilisateurs"),
    path("utilisateurs/demandes-acces/", views.demandes_acces, name="demandes-acces"),
    path("utilisateurs/demandes-acces/<int:pk>/traiter/", views.traiter_demande_acces, name="traiter-demande-acces"),
    path("utilisateurs/nouveau/", views.gestionnaire_creer, name="gestionnaire-creer"),
    path("utilisateurs/<int:pk>/modifier/", views.gestionnaire_modifier, name="gestionnaire-modifier"),
    # Dossiers
    path("dossiers/<uuid:pk>/imprimer/", views.dossier_print, name="dossier-print"),
    path("dossiers/<uuid:pk>/enregistrer/", views.dossier_confirmer, name="dossier-confirmer"),
    path("dossiers/<uuid:pk>/impression/marquer/", views.dossier_impression_marquer, name="dossier-impression-marquer"),
    path("dossiers/<uuid:pk>/signer/", views.dossier_signer, name="dossier-signer"),
    path("dossiers/<uuid:pk>/reprendre/", views.dossier_reprendre, name="dossier-reprendre"),
    path("dossiers/<uuid:pk>/supprimer/", views.dossier_supprimer, name="dossier-supprimer"),
    path("dossiers/<uuid:pk>/", views.dossier_detail, name="dossier-detail"),
    path("dossiers/<uuid:pk>/modifier/", views.dossier_edit, name="dossier-edit"),
]
