from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from elections.models import CandidateResult, Election, NationalPoll, RidingElectionResult
from forum.models import PoliticalParty, PositionHistory, Riding, UserProfile
from moderator.models import AuditLog, ModeratorProfile


class CreateElectionSeedsRidingResultsTests(TestCase):
    """create_election should pre-create a blank RidingElectionResult per riding so the
    candidate/polling wizard has something to attach to."""

    def setUp(self):
        self.mod = User.objects.create_user(username='mod', password='x', is_staff=True)
        self.client.force_login(self.mod)
        Riding.objects.create(name='Riding A')
        Riding.objects.create(name='Riding B')

    def test_federal_election_creates_a_result_row_per_riding(self):
        response = self.client.post(reverse('moderator:create_election'), {
            'name': 'Test Federal',
            'election_type': 'FEDERAL',
            'election_date': '2030-01-01',
        })
        election = Election.objects.get(name='Test Federal')
        self.assertRedirects(response, reverse('moderator:add_results', args=[election.id]))
        self.assertEqual(
            RidingElectionResult.objects.filter(election=election).count(),
            Riding.objects.count(),
        )

    def test_by_election_creates_only_its_own_riding_result(self):
        riding = Riding.objects.get(name='Riding A')
        self.client.post(reverse('moderator:create_election'), {
            'name': 'Test By-Election',
            'election_type': 'BY_ELECTION',
            'election_date': '2030-01-01',
            'riding': riding.id,
        })
        election = Election.objects.get(name='Test By-Election')
        self.assertEqual(RidingElectionResult.objects.filter(election=election).count(), 1)
        self.assertEqual(RidingElectionResult.objects.get(election=election).riding, riding)


class PollingWizardViewsTests(TestCase):
    """The new polling-stage views should call through to elections.polling and redirect
    back to the wizard page."""

    def setUp(self):
        self.mod = User.objects.create_user(username='mod2', password='x', is_staff=True)
        self.client.force_login(self.mod)
        self.lib = PoliticalParty.objects.create(name='LIB')
        self.election = Election.objects.create(
            name='Wizard Test', election_type='FEDERAL', election_date=date(2030, 1, 1)
        )
        self.riding = Riding.objects.create(name='Wizard Riding')
        RidingElectionResult.objects.create(election=self.election, riding=self.riding)

    def test_compute_modifiers_without_permission_redirects(self):
        anon = User.objects.create_user(username='nobody', password='x')
        self.client.force_login(anon)
        response = self.client.post(
            reverse('moderator:run_compute_modifiers', args=[self.election.id])
        )
        self.assertRedirects(
            response, reverse('moderator:dashboard'), fetch_redirect_response=False
        )

    def test_run_national_poll_requires_modifiers_first(self):
        response = self.client.post(
            reverse('moderator:run_national_poll', args=[self.election.id])
        )
        self.assertRedirects(response, reverse('moderator:add_results', args=[self.election.id]))
        self.assertFalse(NationalPoll.objects.filter(election=self.election).exists())

    def test_run_apply_to_ridings_reports_when_nothing_to_apply(self):
        # No candidates declared and no national poll yet — should error gracefully, not crash.
        response = self.client.post(
            reverse('moderator:run_apply_to_ridings', args=[self.election.id])
        )
        self.assertRedirects(response, reverse('moderator:add_results', args=[self.election.id]))

    def test_add_results_page_loads_with_seeded_result(self):
        response = self.client.get(reverse('moderator:add_results', args=[self.election.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Wizard Riding')


class ModeratorProfilePermissionTests(TestCase):
    """The granular ModeratorProfile permission system should actually gate access
    (previously it was dead code: the fields didn't exist on any model)."""

    def setUp(self):
        self.target = User.objects.create_user(username='target', password='x')
        self.profile, _ = UserProfile.objects.get_or_create(user=self.target)

    def test_non_staff_user_without_moderator_profile_is_denied(self):
        plain = User.objects.create_user(username='plain', password='x')
        self.client.force_login(plain)
        response = self.client.get(reverse('moderator:position_dashboard'))
        self.assertRedirects(response, reverse('moderator:dashboard'), fetch_redirect_response=False)

    def test_mod_with_can_manage_users_can_access_position_dashboard(self):
        mod_user = User.objects.create_user(username='position_mod', password='x')
        ModeratorProfile.objects.create(user=mod_user, is_moderator=True, can_manage_users=True)
        self.client.force_login(mod_user)
        response = self.client.get(reverse('moderator:position_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_mod_without_can_manage_users_is_denied_position_dashboard(self):
        mod_user = User.objects.create_user(username='cabinet_only_mod', password='x')
        ModeratorProfile.objects.create(user=mod_user, is_moderator=True, can_manage_cabinet=True)
        self.client.force_login(mod_user)
        response = self.client.get(reverse('moderator:position_dashboard'))
        self.assertRedirects(response, reverse('moderator:dashboard'))

    def test_adding_a_position_history_record_is_audit_logged(self):
        mod_user = User.objects.create_user(username='position_mod2', password='x')
        ModeratorProfile.objects.create(user=mod_user, is_moderator=True, can_manage_users=True)
        self.client.force_login(mod_user)

        response = self.client.post(reverse('moderator:mod_add_position_history'), {
            'user_profile': self.profile.id,
            'position_type': 'SPEAKER',
            'position_title': 'Speaker of the House',
            'start_date': '2026-01-01',
        })
        self.assertRedirects(response, reverse('moderator:position_dashboard'))
        self.assertTrue(
            PositionHistory.objects.filter(user_profile=self.profile, position_type='SPEAKER').exists()
        )

        entry = AuditLog.objects.filter(target_type='PositionHistory', action='create').latest('timestamp')
        self.assertEqual(entry.actor, mod_user)
        self.assertEqual(entry.view_name, 'mod_add_position_history')
