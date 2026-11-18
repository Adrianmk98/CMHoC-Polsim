from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from elections.models import CandidateResult, Election, NationalPoll, RidingElectionResult
from forum.models import PoliticalParty, Riding


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
