from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from unittest.mock import patch

from .forms import DossierClientForm, build_dossier_reference
from .models import Agence, DossierAuditEvent, DossierClient, UserProfile


class DossierFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="conseiller", password="test-pass-123"
        )

    def setUp(self):
        manager_group, _ = Group.objects.get_or_create(name="GESTIONNAIRE")
        self.user.groups.add(manager_group)
        agence, _ = Agence.objects.get_or_create(
            numero="1001",
            defaults={"nom": "Siège", "ville": "Ouagadougou", "active": True},
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nom_affiche = "Conseiller Test"
        profile.agence = agence
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

    def test_create_starts_with_separate_account_type_choices(self):
        response = self.client.get(reverse("recueil:dossier-create"))
        self.assertContains(response, "Compte particulier")
        self.assertContains(response, "Compte commercial")

        individual = self.client.get(
            reverse("recueil:dossier-create"), {"type_compte": "PARTICULIER"}
        )
        self.assertContains(individual, "Nouveau dossier particulier")
        self.assertNotContains(individual, "Entreprise &amp; mandataire")

        commercial = self.client.get(
            reverse("recueil:dossier-create"), {"type_compte": "COMMERCIAL"}
        )
        self.assertContains(commercial, "Nouveau dossier commercial")
        self.assertContains(commercial, "Entreprise &amp; mandataire")

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
            statut=DossierClient.Statut.CREE,
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
            statut=DossierClient.Statut.CREE,
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
        from django.conf import settings
        from weasyprint import HTML

        rendered = HTML(
            string=response.content.decode(), base_url=str(settings.BASE_DIR)
        ).render()
        self.assertEqual(len(rendered.pages), 9)
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

    def test_f5_remains_a_blank_plan_without_extra_client_fields(self):
        dossier = DossierClient.objects.create(
            reference="BCB-2026-PLAN0001",
            cree_par=self.user,
            statut=DossierClient.Statut.CREE,
            nom="Kaboré",
            prenoms="Aïcha",
            numero_piece="PLAN-1",
            telephone="70000000",
            secteur="15",
            repere_proximite="Marché central",
        )
        response = self.client.get(
            reverse("recueil:dossier-print", args=[dossier.pk]), {"f": ["f5"]}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="page f5"')
        self.assertNotContains(response, "Marché central")
        self.assertNotContains(response, "Kaboré")

    def test_print_maps_additional_personal_information_and_explicit_answers(self):
        dossier = DossierClient.objects.create(
            reference="BCB-2026-PRINT0003",
            statut=DossierClient.Statut.CREE,
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
            statut=DossierClient.Statut.CREE,
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

    def test_client_search_is_limited_to_owned_dossiers_and_logs_reuse(self):
        other = get_user_model().objects.create_user(username="collegue")
        manager_group, _ = Group.objects.get_or_create(name="GESTIONNAIRE")
        other.groups.add(manager_group)
        foreign = DossierClient.objects.create(
            reference="BCB-2026-FOREIGN001",
            cree_par=other,
            nom="Traore",
            prenoms="Aminata",
            numero_piece="CNIB-FOREIGN-99",
            telephone="77000000",
        )
        own = DossierClient.objects.create(
            reference="BCB-2026-OWN000001",
            cree_par=self.user,
            nom="Sawadogo",
            prenoms="Aminata",
            numero_piece="CNIB-OWN-99",
            telephone="76000000",
            profession="Information privee",
        )

        response = self.client.get(
            reverse("recueil:recherche-client"), {"q": "CNIB-FOREIGN-99"}
        )
        self.assertNotContains(response, foreign.reference)
        self.assertContains(response, "Aucun dossier")

        response = self.client.get(
            reverse("recueil:recherche-client"), {"q": "Aminata"}
        )
        self.assertContains(response, own.reference)
        self.assertNotContains(response, foreign.reference)
        self.assertNotContains(response, "76000000")
        self.assertNotContains(response, "Information privee")

        response = self.client.post(
            reverse("recueil:dossier-reprendre", args=[own.pk])
        )
        copied = DossierClient.objects.exclude(pk__in=[own.pk, foreign.pk]).get()
        self.assertRedirects(response, reverse("recueil:dossier-edit", args=[copied.pk]))
        self.assertEqual(copied.cree_par, self.user)
        self.assertEqual(copied.numero_piece, own.numero_piece)
        self.assertTrue(
            DossierAuditEvent.objects.filter(
                dossier=own,
                action=DossierAuditEvent.Action.REUTILISATION,
                utilisateur=self.user,
            ).exists()
        )

    def test_edit_print_warning_signature_and_five_name_overflow(self):
        dossier = DossierClient.objects.create(
            reference="BCB-2026-LIFECYCLE1",
            cree_par=self.user,
            statut=DossierClient.Statut.CREE,
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
        self.assertEqual(dossier.statut, DossierClient.Statut.CREE)
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

    def test_dossier_and_audit_are_rolled_back_together_on_log_failure(self):
        self.client.raise_request_exception = False
        with patch("recueil.views._journaliser", side_effect=RuntimeError("audit failure")):
            response = self.client.post(
                reverse("recueil:dossier-create"),
                {"type_compte": "PARTICULIER", "action": "draft"},
            )
        self.assertEqual(response.status_code, 500)
        self.assertFalse(DossierClient.objects.exists())
        self.client.raise_request_exception = True

    def test_printed_address_keeps_sector_separate_from_localization_detail(self):
        dossier = DossierClient.objects.create(
            reference="BCB-2026-ADDRESS01",
            cree_par=self.user,
            statut=DossierClient.Statut.CREE,
            nom="Kaboré",
            prenoms="Aïcha",
            numero_piece="ADDRESS-1",
            telephone="70000000",
            porte="Lot 15",
            rue="Rue A",
            secteur="15",
            quartier="Zogona",
            ville_residence="Ouagadougou",
            adresse="Près de la grande mosquée",
            repere_proximite="Marché central",
            urgence_nom_1="Contact Test",
            urgence_tel_1="70000001",
            urgence_tel_2_1="70000002",
            urgence_secteur_1="Secteur 4",
            urgence_quartier_1="Koulouba",
            urgence_detail_1="\u00c0 côté de la mairie",
        )
        response = self.client.get(
            reverse("recueil:dossier-print", args=[dossier.pk]), {"f": ["f4"]}
        )
        self.assertContains(response, "Lot 15, Rue A, Zogona, Ouagadougou")
        self.assertContains(response, 'Secteur :</span><span class="val">15')
        self.assertContains(response, "Détail explicatif précis")
        self.assertContains(response, "Près de la grande mosquée")
        self.assertContains(response, "70000002")
        self.assertContains(response, "Secteur 4")
        self.assertContains(response, "Koulouba")
        self.assertContains(response, "\u00c0 côté de la mairie")
        self.assertNotContains(response, "III-")

    def test_incomplete_draft_cannot_be_confirmed_directly(self):
        dossier = DossierClient.objects.create(
            reference="BCB-2026-CONFIRM001",
            cree_par=self.user,
            statut=DossierClient.Statut.BROUILLON,
            nom="Client",
            prenoms="Incomplet",
            numero_piece="CONFIRM-1",
            telephone="70000000",
        )

        response = self.client.post(
            reverse("recueil:dossier-edit", args=[dossier.pk]),
            {"action": "confirm"},
        )

        dossier.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(dossier.statut, DossierClient.Statut.BROUILLON)
        self.assertContains(response, "Dossier incomplet")
        self.assertFalse(
            DossierAuditEvent.objects.filter(
                dossier=dossier, action=DossierAuditEvent.Action.GENERATION
            ).exists()
        )

    def test_reference_uses_identity_and_never_reuses_disabled_order(self):
        DossierClient.objects.create(
            reference="BCB-1001-B1234567-0001",
            cree_par=self.user,
            statut=DossierClient.Statut.DESACTIVE,
            nom="Ancien",
            prenoms="Dossier",
            numero_piece="B1234567",
            telephone="70000000",
        )
        response = self.client.post(
            reverse("recueil:dossier-create"),
            {
                "type_compte": "PARTICULIER",
                "nom": "Nouveau",
                "prenoms": "Client",
                "numero_piece": "B1234567",
                "telephone": "70000000",
                "action": "draft",
            },
        )
        self.assertEqual(response.status_code, 302)
        draft = DossierClient.objects.exclude(statut=DossierClient.Statut.DESACTIVE).get()
        self.assertTrue(draft.reference.startswith("BCB-2026-"))
        self.assertEqual(
            build_dossier_reference("1001", "B1234567", dossier_id=draft.pk),
            "BCB-1001-B1234567-0002",
        )

    def test_client_search_accepts_names_and_hides_deactivated_dossiers(self):
        dossier = DossierClient.objects.create(
            reference="BCB-2026-NAME0001",
            cree_par=self.user,
            nom="Sawadogo",
            prenoms="Aminata",
            numero_piece="NAME-1",
            telephone="77000000",
        )
        response = self.client.get(
            reverse("recueil:recherche-client"), {"q": "Aminata"}
        )
        self.assertContains(response, dossier.reference)
        self.assertContains(response, "Particulier")
        self.assertNotContains(response, "77000000")

        dossier.statut = DossierClient.Statut.DESACTIVE
        dossier.save(update_fields=["statut"])
        response = self.client.get(
            reverse("recueil:recherche-client"), {"q": "Aminata"}
        )
        self.assertContains(response, "Aucun dossier")

    def test_account_type_is_locked_after_dossier_creation(self):
        dossier = DossierClient.objects.create(
            reference="BCB-2026-TYPE0001",
            type_compte=DossierClient.TypeCompte.COMMERCIAL,
            cree_par=self.user,
            nom="Traore",
            prenoms="Issa",
            numero_piece="TYPE-1",
            telephone="71000000",
            profession="Gerant",
            pm_raison_sociale="Savane Distribution",
        )
        form = DossierClientForm(instance=dossier)
        self.assertTrue(form.fields["type_compte"].disabled)

        response = self.client.post(
            reverse("recueil:dossier-edit", args=[dossier.pk]),
            {
                "type_compte": "PARTICULIER",
                "formule_produit": "COMMERCIAL",
                "nom": "Traore",
                "prenoms": "Issa",
                "telephone": "71000000",
                "profession": "Gerant",
                "pm_raison_sociale": "Savane Distribution",
            },
        )
        self.assertEqual(response.status_code, 302)
        dossier.refresh_from_db()
        self.assertEqual(dossier.type_compte, DossierClient.TypeCompte.COMMERCIAL)
        self.assertEqual(dossier.pm_raison_sociale, "Savane Distribution")

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

    def test_existing_dossier_type_cannot_be_changed(self):
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
                "pm_raison_sociale": "Savane Distribution",
            },
        )
        self.assertRedirects(response, reverse("recueil:dossier-detail", args=[dossier.pk]))
        dossier.refresh_from_db()
        self.assertEqual(dossier.type_compte, DossierClient.TypeCompte.COMMERCIAL)
        self.assertEqual(dossier.pm_raison_sociale, "Savane Distribution")

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
            "pays_residence_fiscale": "Burkina Faso",
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
        # Étape 1 : prévisualisation — sauvegarde en brouillon (fix bug session)
        preview = self.client.post(reverse("recueil:dossier-create"), data)
        self.assertEqual(preview.status_code, 200)
        from django.conf import settings
        from weasyprint import HTML

        preview_pages = HTML(
            string=preview.content.decode(), base_url=str(settings.BASE_DIR)
        ).render()
        self.assertEqual(len(preview_pages.pages), 9)
        dossier_brouillon = DossierClient.objects.get()
        self.assertEqual(dossier_brouillon.statut, DossierClient.Statut.BROUILLON)
        # Étape 2 : confirmation → passe en CREE
        response = self.client.post(
            reverse("recueil:dossier-edit", args=[dossier_brouillon.pk]),
            {"action": "confirm"},
        )
        self.assertEqual(response.status_code, 302, response.content.decode())
        dossier = DossierClient.objects.get()
        self.assertEqual(dossier.statut, DossierClient.Statut.CREE)
        self.assertEqual(dossier.reference, "BCB-1001-B1234567-0001")
        self.assertIsNone(dossier.pdf_fige)
        self.assertEqual(dossier.categorie_client, DossierClient.CategorieClient.ACTIVITE_COMMERCIALE)
        self.assertTrue(dossier.resident_bf)
        self.assertFalse(dossier.a_autre_nationalite)
        self.assertEqual(dossier.cree_par, self.user)
        self.assertEqual(dossier.agence_snapshot, "Siège")
        self.assertEqual(dossier.charge_affaires_snapshot, "Conseiller Test")
        self.assertRedirects(response, reverse("recueil:dossier-print", args=[dossier.pk]))
        documents = self.client.get(response.url)
        self.assertEqual(documents["Content-Type"], "text/html; charset=utf-8")
        for form_code in ("f1", "f2", "f3", "f4", "f5"):
            self.assertContains(documents, f'class="page {form_code}"')
        self.assertContains(documents, "Kaboré")
        self.assertContains(documents, "70000000")
        self.assertContains(documents, "Pays de résidence fiscale")
        self.assertContains(documents, "Burkina Faso")

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
                "pm_date_creation": "2020-01-15",
                "pm_date_enregistrement_rccm": "2020-02-01",
                "pm_date_nomination_mandataire": "2025-01-10",
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
        # Étape 1 : prévisualisation — sauvegarde maintenant en brouillon (fix bug session)
        preview = self.client.post(reverse("recueil:dossier-create"), data)
        self.assertEqual(preview.status_code, 200)
        # Le dossier est créé en BROUILLON après le preview
        dossier_brouillon = DossierClient.objects.get()
        self.assertEqual(dossier_brouillon.statut, DossierClient.Statut.BROUILLON)
        # Étape 2 : confirmation → passe en CREE
        response = self.client.post(
            reverse("recueil:dossier-edit", args=[dossier_brouillon.pk]),
            {"action": "confirm"},
        )
        dossier = DossierClient.objects.get()
        self.assertRedirects(
            response, reverse("recueil:dossier-print", args=[dossier.pk])
        )
        self.assertEqual(dossier.statut, DossierClient.Statut.CREE)
        self.assertEqual(dossier.pm_capital_social, 0)
        documents = self.client.get(response.url)
        self.assertEqual(documents.status_code, 200)
        self.assertEqual(documents["Content-Type"], "text/html; charset=utf-8")
        self.assertContains(documents, "Savane Distribution")
        self.assertContains(documents, "FICHE D'IDENTIFICATION DU CLIENT PERSONNE MORALE")
        self.assertContains(documents, "CONSENTEMENT")
        self.assertContains(documents, "SPÉCIMEN DE SIGNATURE")
        self.assertContains(documents, "15/01/2020")
        self.assertContains(documents, "01/02/2020")
        self.assertContains(documents, "10/01/2025")
        from django.conf import settings
        from weasyprint import HTML

        rendered = HTML(
            string=documents.content.decode(), base_url=str(settings.BASE_DIR)
        ).render()
        self.assertEqual(len(rendered.pages), 19)
