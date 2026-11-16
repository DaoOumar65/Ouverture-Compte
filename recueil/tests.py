from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from .forms import DossierClientForm
from .models import DossierAuditEvent, DossierClient, UserProfile


class DossierFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="conseiller", password="test-pass-123"
        )

    def setUp(self):
        manager_group, _ = Group.objects.get_or_create(name="GESTIONNAIRE")
        self.user.groups.add(manager_group)
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nom_affiche = "Conseiller Test"
        profile.agence = "Ouagadougou"
        profile.save()
        self.client.force_login(self.user)

    def test_dossier_pages_require_authentication(self):
        self.client.logout()
        response = self.client.get(reverse("recueil:dossier-list"))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('recueil:dossier-list')}",
        )
        response = self.client.get(reverse("recueil:dossier-create"))
        self.assertEqual(response.status_code, 302)
        response = self.client.get(
            reverse(
                "recueil:dossier-print",
                args=["00000000-0000-0000-0000-000000000001"],
            )
        )
        self.assertEqual(response.status_code, 302)

    def test_can_save_an_incomplete_draft_and_retrieve_it(self):
        response = self.client.post(
            reverse("recueil:dossier-create"),
            {"type_compte": "PARTICULIER", "action": "draft"},
        )
        dossier = DossierClient.objects.get()
        self.assertRedirects(response, reverse("recueil:dossier-detail", args=[dossier.pk]))
        self.assertEqual(dossier.statut, DossierClient.Statut.BROUILLON)
        self.assertIsNone(dossier.date_naissance)
        self.assertIsNone(dossier.resident_bf)
        self.assertIsNone(dossier.a_autre_nationalite)

        list_response = self.client.get(
            reverse("recueil:dossier-list"), {"q": dossier.reference}
        )
        self.assertContains(list_response, dossier.reference)
        self.assertContains(self.client.get(response.url), "DOCUMENT INTERNE")

    def test_generated_individual_dossier_can_print_selected_information_sheets(self):
        dossier = DossierClient.objects.create(
            reference="BCB-2026-PRINT0001",
            statut=DossierClient.Statut.GENERE,
            cree_par=self.user,
            nom="Kaboré",
            prenoms="Aïcha",
            lieu_naissance="Bobo-Dioulasso",
            numero_piece="B1234567",
            telephone="70000000",
            profession="Commerçante",
            adresse="Ouagadougou, secteur 15",
            f2_transmission_credit=True,
            f2_partage_credit=False,
        )

        response = self.client.get(
            reverse("recueil:dossier-print", args=[dossier.pk]),
            {"f": ["f2"], "copies": "2"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FORMULAIRE TYPE D'OBTENTION DU CONSENTEMENT")
        self.assertContains(response, "Kaboré")
        self.assertEqual(response.content.count(b'class="page f2"'), 2)
        self.assertEqual(response.content.count(b'class="cb on"'), 2)
        self.assertNotContains(response, "RENSEIGNEMENTS COMPLEMENTAIRES")

    def test_print_page_renders_all_information_sheets_by_default(self):
        dossier = DossierClient.objects.create(
            reference="BCB-2026-PRINT0002",
            statut=DossierClient.Statut.GENERE,
            cree_par=self.user,
            agence_snapshot="Ouagadougou",
            charge_affaires_snapshot="Conseiller Test",
            nom="Kaboré",
            prenoms="Aïcha",
            formule_produit=DossierClient.FormuleProduit.EPARGNE,
            lieu_naissance="Bobo-Dioulasso",
            numero_piece="B1234567",
            piece_delivree_par="ONI Bobo",
            telephone="70000000",
            profession="Commerçante",
            adresse_employeur="Marché central",
            urgence_nom_2="Contact Deux",
            urgence_tel_2="76000002",
            urgence_prof_2="Enseignante",
            urgence_lieu_travail_2="École test",
            urgence_adresse_2="Secteur 8",
        )

        response = self.client.get(
            reverse("recueil:dossier-print", args=[dossier.pk])
        )

        self.assertEqual(response.status_code, 200)
        for form_code in ("f1", "f2", "f3", "f4", "f5"):
            self.assertContains(response, f'class="page {form_code}"')
        for value in (
            "Compte Épargne",
            "Bobo-Dioulasso",
            "ONI Bobo",
            "Marché central",
            "Contact Deux",
            "76000002",
            "École test",
            "Secteur 8",
        ):
            self.assertContains(response, value)

    def test_print_maps_additional_personal_information_and_explicit_answers(self):
        dossier = DossierClient.objects.create(
            reference="BCB-2026-PRINT0003",
            statut=DossierClient.Statut.GENERE,
            cree_par=self.user,
            nom="Kaboré",
            prenoms="Aïcha",
            lieu_naissance="Bobo-Dioulasso",
            numero_piece="B1234567",
            type_piece_secondaire="PASSEPORT",
            telephone="70000000",
            telephone_bureau="25334455",
            profession="Commerçante",
            categorie_client=DossierClient.CategorieClient.ACTIVITE_COMMERCIALE,
            activite_commerciale="Vente de céréales",
            resident_bf=True,
            statut_logement=DossierClient.StatutLogement.LOCATAIRE,
            justificatif_domicile=DossierClient.JustificatifDomicile.CONTRAT_BAIL,
            a_autre_nationalite=True,
            autre_nationalite="Ivoirienne",
            revenus_immobiliers=125000,
            montant_versement_initial=250000,
            nature_versement_initial="Épargne personnelle",
            operations_habituelles="Dépôts mensuels",
            mandat_administrateur=False,
            est_actionnaire=True,
            societes_actionnaire="Société Exemple",
            numero_compte_bcb_existant="001234567",
            autres_comptes_bancaires="Banque Exemple",
            entree_relation_directe=True,
            mode_entree_relation=DossierClient.ModeEntreeRelation.A_DISTANCE,
            procuration_donnee=False,
            conjoint_nom="Issa Kaboré",
            conjoint_date_naissance="1988-04-02",
            conjoint_profession="Enseignant",
            nombre_enfants=2,
            enfants_noms="Aminata\nMoussa",
        )

        response = self.client.get(
            reverse("recueil:dossier-print", args=[dossier.pk])
        )

        self.assertEqual(response.status_code, 200)
        for value in (
            "Aminata", "Moussa", "Enseignant", "25334455", "Contrat de bail",
            "Ivoirienne", "Vente de céréales", "125000 FCFA", "250000 FCFA",
            "Épargne personnelle", "Dépôts mensuels", "Société Exemple",
            "Banque Exemple",
        ):
            self.assertContains(response, value)
        self.assertNotContains(response, "001234567")
        self.assertContains(
            response,
            'Oui <i class="cb on"></i> &nbsp;&nbsp;&nbsp; Non <i class="cb"></i>',
        )
        self.assertContains(
            response,
            'Oui <i class="cb"></i> Non <i class="cb on"></i>',
        )

    def test_manager_cannot_open_another_managers_dossier_but_admin_can_read_it(self):
        other = get_user_model().objects.create_user(username="autre-conseiller")
        manager_group, _ = Group.objects.get_or_create(name="GESTIONNAIRE")
        other.groups.add(manager_group)
        dossier = DossierClient.objects.create(
            reference="BCB-2026-FOREIGN001",
            cree_par=other,
            statut=DossierClient.Statut.GENERE,
            nom="Client",
            prenoms="Confidentiel",
            numero_piece="FOREIGN-123",
            telephone="76000000",
        )

        for route in (
            "dossier-detail",
            "dossier-edit",
            "dossier-print",
            "dossier-reprendre",
        ):
            method = self.client.post if route == "dossier-reprendre" else self.client.get
            response = method(reverse(f"recueil:{route}", args=[dossier.pk]))
            self.assertEqual(response.status_code, 404, route)
        self.assertNotContains(
            self.client.get(reverse("recueil:dossier-list")),
            dossier.reference,
        )

        admin_user = get_user_model().objects.create_user(
            username="administrateur",
            is_staff=True,
        )
        admin_group, _ = Group.objects.get_or_create(name="ADMIN")
        admin_user.groups.add(admin_group)
        self.client.force_login(admin_user)
        self.assertContains(
            self.client.get(reverse("recueil:dossier-list")),
            dossier.reference,
        )
        self.assertEqual(
            self.client.get(
                reverse("recueil:dossier-detail", args=[dossier.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("recueil:dossier-create")).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("recueil:journal-audit")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get("/admin/").status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("admin:auth_user_changelist")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("admin:recueil_dossierclient_changelist")).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                reverse("admin:recueil_dossierclient_change", args=[dossier.pk]),
                {"nom": "Modification interdite"},
            ).status_code,
            403,
        )

    def test_global_identity_search_reuses_only_latest_summary_and_logs_copy(self):
        other = get_user_model().objects.create_user(username="collegue")
        manager_group, _ = Group.objects.get_or_create(name="GESTIONNAIRE")
        other.groups.add(manager_group)
        source = DossierClient.objects.create(
            reference="BCB-2026-REUSE0001",
            cree_par=other,
            nom="Traoré",
            prenoms="Aminata",
            numero_piece="CNIB-REUSE-99",
            telephone="77000000",
            profession="Information privée",
        )

        response = self.client.get(
            reverse("recueil:recherche-client"),
            {"numero_piece": "CNIB-REUSE-99"},
        )
        self.assertContains(response, source.reference)
        self.assertContains(response, "Aminata Traoré")
        self.assertNotContains(response, "77000000")
        self.assertNotContains(response, "Information privée")

        response = self.client.post(
            reverse("recueil:dossier-reprendre", args=[source.pk])
        )
        copied = DossierClient.objects.exclude(pk=source.pk).get()
        self.assertRedirects(
            response,
            reverse("recueil:dossier-edit", args=[copied.pk]),
        )
        self.assertEqual(copied.cree_par, self.user)
        self.assertEqual(copied.nom, source.nom)
        self.assertEqual(copied.numero_piece, source.numero_piece)
        self.assertTrue(
            DossierAuditEvent.objects.filter(
                dossier=source,
                action=DossierAuditEvent.Action.REUTILISATION,
                utilisateur=self.user,
            ).exists()
        )

    def test_edit_print_warning_signature_and_five_name_overflow(self):
        dossier = DossierClient.objects.create(
            reference="BCB-2026-LIFECYCLE1",
            cree_par=self.user,
            statut=DossierClient.Statut.GENERE,
            nom="Kaboré",
            prenoms="Aïcha",
            numero_piece="LIFE-123",
            telephone="70000000",
            profession="Commerçante",
            nombre_enfants=7,
            enfants_noms="Un\nDeux\nTrois\nQuatre\nCinq\nSix\nSept",
        )

        print_page = self.client.get(
            reverse("recueil:dossier-print", args=[dossier.pk]),
            {"f": ["f1", "f2", "f4"]},
        )
        self.assertContains(print_page, "SUITE : 2 autre(s) prénom(s) : Six, Sept")
        printed_date = timezone.localdate().strftime("%d/%m/%Y")
        self.assertContains(print_page, f"Date : {printed_date}")
        self.assertContains(print_page, f"Fait le {printed_date}")

        response = self.client.post(
            reverse("recueil:dossier-impression-marquer", args=[dossier.pk])
        )
        self.assertEqual(response.status_code, 200)
        dossier.refresh_from_db()
        self.assertIsNotNone(dossier.derniere_impression_le)
        self.assertEqual(dossier.derniere_impression_par, self.user)

        response = self.client.post(
            reverse("recueil:dossier-edit", args=[dossier.pk]),
            {
                "type_compte": "PARTICULIER",
                "formule_produit": "COURANT",
                "nom": "Kaboré-Modifié",
                "prenoms": "Aïcha",
                "sexe": "F",
                "lieu_naissance": "Ouagadougou",
                "type_piece": "CNIB",
                "numero_piece": "LIFE-123",
                "telephone": "70000000",
                "profession": "Commerçante",
                "action": "draft",
            },
        )
        self.assertEqual(response.status_code, 302)
        dossier.refresh_from_db()
        self.assertEqual(dossier.statut, DossierClient.Statut.GENERE)
        self.assertEqual(dossier.nom, "Kaboré-Modifié")
        stale_page = self.client.get(
            reverse("recueil:dossier-print", args=[dossier.pk])
        )
        self.assertContains(stale_page, "LA VERSION IMPRIMÉE N'EST PLUS À JOUR")
        modification = DossierAuditEvent.objects.get(
            dossier=dossier,
            action=DossierAuditEvent.Action.MODIFICATION,
        )
        self.assertEqual(modification.utilisateur, self.user)
        self.assertEqual(
            modification.details["nom"],
            {"ancienne": "Kaboré", "nouvelle": "Kaboré-Modifié"},
        )

        self.client.post(reverse("recueil:dossier-signer", args=[dossier.pk]))
        dossier.refresh_from_db()
        self.assertIsNotNone(dossier.signe_le)
        locked = self.client.get(reverse("recueil:dossier-edit", args=[dossier.pk]))
        self.assertRedirects(locked, reverse("recueil:dossier-detail", args=[dossier.pk]))
        self.assertTrue(
            DossierAuditEvent.objects.filter(
                dossier=dossier,
                action=DossierAuditEvent.Action.SIGNATURE,
            ).exists()
        )

    def test_generate_rejects_missing_required_identity_fields(self):
        response = self.client.post(
            reverse("recueil:dossier-create"),
            {"type_compte": "PARTICULIER", "formule_produit": "COURANT", "action": "preview"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DossierClient.objects.exists())
        self.assertContains(response, "Ce champ est requis pour générer les formulaires.")
        self.assertContains(response, 'class="error-summary"')
        self.assertContains(response, 'aria-invalid="true"')

    def test_individual_generation_requires_creditinfo_confirmation(self):
        form = DossierClientForm(
            data={
                "type_compte": "PARTICULIER",
                "formule_produit": "COURANT",
                "nom": "Kaboré",
                "prenoms": "Aïcha",
                "sexe": "F",
                "date_naissance": "1992-03-14",
                "lieu_naissance": "Bobo-Dioulasso",
                "pays_naissance": "Burkina Faso",
                "nationalite": "Burkinabè",
                "type_piece": "CNIB",
                "numero_piece": "B1234567",
                "situation_matrimoniale": "CELIBATAIRE",
                "ville_residence": "Ouagadougou",
                "telephone": "70000000",
                "profession": "Commerçante",
                "categorie_client": "ACTIVITE_COMMERCIALE",
                "activite_commerciale": "Vente de céréales",
                "resident_bf": "True",
                "statut_logement": "LOCATAIRE",
                "justificatif_domicile": "CONTRAT_BAIL",
                "a_autre_nationalite": "False",
                "mandat_administrateur": "False",
                "est_actionnaire": "False",
                "entree_relation_directe": "True",
                "mode_entree_relation": "EN_PERSONNE",
                "procuration_donnee": "False",
                "nombre_enfants": "0",
                "est_us_person": "False",
                "est_ppe": "False",
                "levee_secret_bancaire": "False",
                "f2_transmission_credit": "True",
                "f2_partage_credit": "True",
                "f2_exclusion_depots": "True",
                "f2_limite_anciennete": "True",
                "f2_duree_conservation": "True",
                "f2_droit_acces": "True",
                "f2_droit_rapport": "True",
            },
            generate=True,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("creditinfo_confirme", form.errors)

    def test_switching_to_individual_clears_company_data(self):
        dossier = DossierClient.objects.create(
            reference="BCB-2026-TEST0001",
            type_compte=DossierClient.TypeCompte.COMMERCIAL,
            cree_par=self.user,
            nom="Traoré",
            prenoms="Issa",
            pm_raison_sociale="Savane Distribution",
        )
        response = self.client.post(
            reverse("recueil:dossier-edit", args=[dossier.pk]),
            {
                "type_compte": "PARTICULIER",
                "formule_produit": "COURANT",
                "nom": "Traoré",
                "prenoms": "Issa",
                "telephone": "71000000",
                "profession": "Gérant",
            },
        )
        self.assertRedirects(response, reverse("recueil:dossier-detail", args=[dossier.pk]))
        dossier.refresh_from_db()
        self.assertEqual(dossier.type_compte, DossierClient.TypeCompte.PARTICULIER)
        self.assertEqual(dossier.pm_raison_sociale, "")

    def test_valid_individual_dossier_generates_the_new_print_layout(self):
        data = {
            "type_compte": "PARTICULIER",
            "formule_produit": "COURANT",
            "nom": "Kaboré",
            "prenoms": "Aïcha",
            "sexe": "F",
            "date_naissance": "1992-03-14",
            "lieu_naissance": "Bobo-Dioulasso",
            "pays_naissance": "Burkina Faso",
            "nationalite": "Burkinabè",
            "type_piece": "CNIB",
            "numero_piece": "B1234567",
            "situation_matrimoniale": "CELIBATAIRE",
            "ville_residence": "Ouagadougou",
            "telephone": "70000000",
            "profession": "Commerçante",
            "categorie_client": "ACTIVITE_COMMERCIALE",
            "activite_commerciale": "Vente de céréales",
            "resident_bf": "True",
            "statut_logement": "LOCATAIRE",
            "justificatif_domicile": "CONTRAT_BAIL",
            "a_autre_nationalite": "False",
            "mandat_administrateur": "False",
            "est_actionnaire": "False",
            "entree_relation_directe": "True",
            "mode_entree_relation": "EN_PERSONNE",
            "procuration_donnee": "False",
            "nombre_enfants": "0",
            "est_us_person": "False",
            "est_ppe": "False",
            "levee_secret_bancaire": "False",
            "f2_transmission_credit": "True",
            "f2_partage_credit": "True",
            "f2_exclusion_depots": "True",
            "f2_limite_anciennete": "True",
            "f2_duree_conservation": "True",
            "f2_droit_acces": "True",
            "f2_droit_rapport": "True",
            "creditinfo_confirme": "on",
            "action": "preview",
        }
        # Étape 1 : prévisualisation (rien n'est enregistré)
        preview = self.client.post(reverse("recueil:dossier-create"), data)
        self.assertEqual(preview.status_code, 200)
        self.assertFalse(DossierClient.objects.exists())
        # Étape 2 : confirmation → enregistrement
        response = self.client.post(reverse("recueil:dossier-create"), {"action": "confirm"})
        self.assertEqual(response.status_code, 302, response.content.decode())
        dossier = DossierClient.objects.get()
        self.assertEqual(dossier.statut, DossierClient.Statut.GENERE)
        self.assertIsNone(dossier.pdf_fige)
        self.assertEqual(
            dossier.categorie_client,
            DossierClient.CategorieClient.ACTIVITE_COMMERCIALE,
        )
        self.assertTrue(dossier.resident_bf)
        self.assertFalse(dossier.a_autre_nationalite)
        self.assertEqual(dossier.cree_par, self.user)
        self.assertEqual(dossier.agence_snapshot, "Ouagadougou")
        self.assertEqual(dossier.charge_affaires_snapshot, "Conseiller Test")
        self.assertRedirects(response, reverse("recueil:dossier-print", args=[dossier.pk]))
        documents = self.client.get(response.url)
        self.assertEqual(documents["Content-Type"], "text/html; charset=utf-8")
        for form_code in ("f1", "f2", "f3", "f4", "f5"):
            self.assertContains(documents, f'class="page {form_code}"')
        self.assertContains(documents, "Kaboré")
        self.assertContains(documents, "70000000")

    def test_commercial_generation_requires_company_information(self):
        response = self.client.post(
            reverse("recueil:dossier-create"),
            {
                "type_compte": "COMMERCIAL",
                "formule_produit": "COMMERCIAL",
                "nom": "Traoré",
                "prenoms": "Issa",
                "sexe": "M",
                "date_naissance": "1980-01-01",
                "lieu_naissance": "Ouagadougou",
                "pays_naissance": "Burkina Faso",
                "nationalite": "Burkinabè",
                "type_piece": "CNIB",
                "numero_piece": "C1234567",
                "situation_matrimoniale": "CELIBATAIRE",
                "ville_residence": "Ouagadougou",
                "telephone": "71000000",
                "profession": "Gérant",
                "action": "preview",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DossierClient.objects.exists())
        self.assertContains(response, "Raison sociale")

    def test_valid_commercial_dossier_generates_official_pdf_bundle(self):
        data = {
                "type_compte": "COMMERCIAL",
                "formule_produit": "COMMERCIAL",
                "nom": "Traoré",
                "prenoms": "Issa",
                "sexe": "M",
                "date_naissance": "1980-01-01",
                "lieu_naissance": "Ouagadougou",
                "pays_naissance": "Burkina Faso",
                "nationalite": "Burkinabè",
                "type_piece": "CNIB",
                "numero_piece": "C1234567",
                "situation_matrimoniale": "CELIBATAIRE",
                "ville_residence": "Ouagadougou",
                "telephone": "71000000",
                "profession": "Gérant",
                "pm_raison_sociale": "Savane Distribution",
                "pm_forme_juridique": "SARL",
                "pm_activite_principale": "Commerce général",
                "pm_numero_rccm": "BF-OUA-2020-B-1234",
                "pm_ifu": "00012345A",
                "pm_siege_social": "Ouagadougou, Burkina Faso",
                "est_us_person": "False",
                "est_ppe": "False",
                "levee_secret_bancaire": "False",
                "f2_transmission_credit": "True",
                "f2_partage_credit": "True",
                "f2_exclusion_depots": "True",
                "f2_limite_anciennete": "True",
                "f2_duree_conservation": "True",
                "f2_droit_acces": "True",
                "f2_droit_rapport": "True",
                "action": "preview",
            }
        # Étape 1 : prévisualisation
        preview = self.client.post(reverse("recueil:dossier-create"), data)
        self.assertEqual(preview.status_code, 200)
        self.assertFalse(DossierClient.objects.exists())
        # Étape 2 : confirmation
        response = self.client.post(reverse("recueil:dossier-create"), {"action": "confirm"})
        dossier = DossierClient.objects.get()
        self.assertRedirects(
            response, reverse("recueil:dossier-print", args=[dossier.pk])
        )
        self.assertEqual(dossier.pm_capital_social, 0)
        documents = self.client.get(response.url)
        self.assertEqual(documents.status_code, 200)
        self.assertEqual(documents["Content-Type"], "text/html; charset=utf-8")
        # Vérifie les formulaires commerciaux clés
        self.assertContains(documents, "Savane Distribution")
        self.assertContains(documents, "FICHE D'IDENTIFICATION DU CLIENT PERSONNE MORALE")
        self.assertContains(documents, "CONSENTEMENT")
        self.assertContains(documents, "SPÉCIMEN DE SIGNATURE")
