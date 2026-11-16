from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from forum.models import PoliticalParty, Riding, UserProfile
from .models import CandidateResult, Election, PartyModifier, RidingElectionResult
from .services import project_riding_result
from . import polling


def make_party(name='LIB'):
    return PoliticalParty.objects.create(name=name)


def make_candidate(username):
    user = User.objects.create_user(username=username, password='x')
    return UserProfile.objects.get(user=user)


class SwingCalculatorTests(TestCase):
    def setUp(self):
        self.lib = make_party('LIB')
        self.con = make_party('CON')

    def test_no_baseline_returns_none(self):
        riding = Riding.objects.create(name='Nowhere')
        self.assertIsNone(project_riding_result(riding, swing_by_party={}))

    def test_uses_static_baseline_when_no_prior_result(self):
        riding = Riding.objects.create(
            name='Static Riding', baseline_party=self.lib, baseline_vote_share=Decimal('60.0')
        )
        projections = project_riding_result(riding, swing_by_party={}, total_votes_cast=1000)
        self.assertIsNotNone(projections)
        self.assertEqual(len(projections), 1)
        self.assertEqual(projections[0].party, self.lib)
        self.assertEqual(projections[0].projected_share, Decimal('100'))
        self.assertEqual(projections[0].projected_votes, 1000)

    def test_prefers_real_history_over_static_baseline(self):
        riding = Riding.objects.create(
            name='History Riding', baseline_party=self.con, baseline_vote_share=Decimal('80.0')
        )
        election = Election.objects.create(name='2020', election_type='FEDERAL', election_date=date(2020, 1, 1))
        riding_result = RidingElectionResult.objects.create(
            election=election, riding=riding, total_votes_cast=1000
        )
        lib_candidate = make_candidate('lib_candidate')
        con_candidate = make_candidate('con_candidate')
        CandidateResult.objects.create(
            riding_result=riding_result, candidate=lib_candidate, party=self.lib, votes=600
        )
        CandidateResult.objects.create(
            riding_result=riding_result, candidate=con_candidate, party=self.con, votes=400
        )

        projections = project_riding_result(riding, swing_by_party={})
        by_party = {p.party: p for p in projections}
        # Real history (LIB 60/CON 40) should win out over the static baseline (CON 80).
        self.assertAlmostEqual(float(by_party[self.lib].projected_share), 60.0, places=1)
        self.assertAlmostEqual(float(by_party[self.con].projected_share), 40.0, places=1)

    def test_uniform_swing_shifts_shares(self):
        riding = Riding.objects.create(
            name='Swing Riding', baseline_party=self.lib, baseline_vote_share=Decimal('50.0')
        )
        election = Election.objects.create(name='2020', election_type='FEDERAL', election_date=date(2020, 1, 1))
        riding_result = RidingElectionResult.objects.create(
            election=election, riding=riding, total_votes_cast=1000
        )
        lib_candidate = make_candidate('lib2')
        con_candidate = make_candidate('con2')
        CandidateResult.objects.create(
            riding_result=riding_result, candidate=lib_candidate, party=self.lib, votes=500
        )
        CandidateResult.objects.create(
            riding_result=riding_result, candidate=con_candidate, party=self.con, votes=500
        )

        projections = project_riding_result(
            riding, swing_by_party={self.con.id: Decimal('10'), self.lib.id: Decimal('-10')}
        )
        by_party = {p.party: p for p in projections}
        self.assertGreater(by_party[self.con].projected_share, by_party[self.lib].projected_share)
        total_share = sum(p.projected_share for p in projections)
        self.assertAlmostEqual(float(total_share), 100.0, places=1)

    def test_negative_swing_clamped_and_renormalized(self):
        riding = Riding.objects.create(
            name='Clamp Riding', baseline_party=self.lib, baseline_vote_share=Decimal('10.0')
        )
        election = Election.objects.create(name='2020', election_type='FEDERAL', election_date=date(2020, 1, 1))
        riding_result = RidingElectionResult.objects.create(
            election=election, riding=riding, total_votes_cast=1000
        )
        lib_candidate = make_candidate('lib3')
        con_candidate = make_candidate('con3')
        CandidateResult.objects.create(
            riding_result=riding_result, candidate=lib_candidate, party=self.lib, votes=100
        )
        CandidateResult.objects.create(
            riding_result=riding_result, candidate=con_candidate, party=self.con, votes=900
        )

        # A swing far more negative than LIB's baseline share should clamp at 0, not go negative.
        projections = project_riding_result(riding, swing_by_party={self.lib.id: Decimal('-50')})
        by_party = {p.party: p for p in projections}
        self.assertEqual(by_party[self.lib].projected_share, Decimal('0'))
        self.assertEqual(by_party[self.con].projected_share, Decimal('100'))

    def test_votes_sum_to_total(self):
        riding = Riding.objects.create(
            name='Sum Riding', baseline_party=self.lib, baseline_vote_share=Decimal('50.0')
        )
        election = Election.objects.create(name='2020', election_type='FEDERAL', election_date=date(2020, 1, 1))
        riding_result = RidingElectionResult.objects.create(
            election=election, riding=riding, total_votes_cast=1000
        )
        lib_candidate = make_candidate('lib4')
        con_candidate = make_candidate('con4')
        CandidateResult.objects.create(
            riding_result=riding_result, candidate=lib_candidate, party=self.lib, votes=500
        )
        CandidateResult.objects.create(
            riding_result=riding_result, candidate=con_candidate, party=self.con, votes=500
        )

        projections = project_riding_result(riding, swing_by_party={}, total_votes_cast=1000)
        total_votes = sum(p.projected_votes for p in projections)
        # Rounding each share independently can be off by a vote or two; should stay close.
        self.assertAlmostEqual(total_votes, 1000, delta=2)


class ElectionPhaseTests(TestCase):
    def make_election(self, **kwargs):
        defaults = {
            'name': 'Test Election',
            'election_type': 'FEDERAL',
            'election_date': date.today() + timedelta(days=30),
        }
        defaults.update(kwargs)
        return Election.objects.create(**defaults)

    def test_no_timeline_fields_defaults_to_pre_writ(self):
        election = self.make_election()
        self.assertEqual(election.phase, Election.PHASE_PRE_WRIT)

    def test_no_timeline_fields_never_raises_on_voting_day(self):
        election = self.make_election(election_date=date.today())
        self.assertEqual(election.phase, Election.PHASE_VOTING)

    def test_no_timeline_fields_closed_after_election_day(self):
        election = self.make_election(election_date=date.today() - timedelta(days=1))
        self.assertEqual(election.phase, Election.PHASE_CLOSED)

    def test_nominations_phase(self):
        election = self.make_election(
            election_date=date.today() + timedelta(days=30),
            writ_date=date.today() - timedelta(days=5),
        )
        self.assertEqual(election.phase, Election.PHASE_NOMINATIONS)
        self.assertTrue(election.is_nomination_open())

    def test_campaign_phase(self):
        election = self.make_election(
            election_date=date.today() + timedelta(days=30),
            writ_date=date.today() - timedelta(days=20),
            campaign_start_date=date.today() - timedelta(days=5),
        )
        self.assertEqual(election.phase, Election.PHASE_CAMPAIGN)
        self.assertTrue(election.is_campaign_active())

    def test_voting_day_phase(self):
        election = self.make_election(
            election_date=date.today(),
            writ_date=date.today() - timedelta(days=20),
            campaign_start_date=date.today() - timedelta(days=5),
        )
        self.assertEqual(election.phase, Election.PHASE_VOTING)

    def test_closed_when_marked_completed(self):
        election = self.make_election(
            election_date=date.today() + timedelta(days=30),
            is_completed=True,
        )
        self.assertEqual(election.phase, Election.PHASE_CLOSED)

    def test_closed_after_results_certified_date(self):
        election = self.make_election(
            election_date=date.today() - timedelta(days=10),
            results_certified_date=date.today() - timedelta(days=1),
        )
        self.assertEqual(election.phase, Election.PHASE_CLOSED)

    def test_get_phase_display_returns_label(self):
        election = self.make_election()
        self.assertEqual(election.get_phase_display(), 'Pre-Writ')


class NationalPollingTests(TestCase):
    """Regression check: with the source spreadsheet's exact modifier totals and random
    rolls plugged in, run_national_polling() must reproduce its corrected_pct column."""

    def setUp(self):
        self.election = Election.objects.create(
            name='Polling Test', election_type='FEDERAL', election_date=date(2024, 1, 1)
        )
        # (party abbrev, personal_mods_total, random_number, expected corrected_pct)
        self.sheet_rows = [
            ('LIB', Decimal('2665.184148'), Decimal('0.0'), Decimal('0.373')),
            ('CON', Decimal('5885.084921'), Decimal('0.7'), Decimal('0.391')),
            ('NDP', Decimal('863.4949914'), Decimal('0.2'), Decimal('0.103')),
            ('IND', Decimal('812.0465062'), Decimal('0.2'), Decimal('0.097')),  # Socialist -> unused real choice
            ('GRN', Decimal('937.198421'), Decimal('1.0'), Decimal('0.033')),
            ('PPC', Decimal('35'), Decimal('0.1169802775'), Decimal('0.004')),
        ]
        self.random_overrides = {}
        self.expected_by_party_id = {}
        for name, modifier_total, random_number, expected in self.sheet_rows:
            party = PoliticalParty.objects.create(name=name)
            PartyModifier.objects.create(
                election=self.election, party=party, personal_mods_total=modifier_total
            )
            self.random_overrides[party.id] = random_number
            self.expected_by_party_id[party.id] = expected

    def test_matches_spreadsheet_corrected_percentages(self):
        polls = polling.run_national_polling(self.election, random_overrides=self.random_overrides)
        self.assertEqual(len(polls), 6)
        for poll in polls:
            expected = self.expected_by_party_id[poll.party_id]
            self.assertAlmostEqual(float(poll.corrected_pct), float(expected), places=3)

    def test_corrected_percentages_sum_to_one(self):
        polls = polling.run_national_polling(self.election, random_overrides=self.random_overrides)
        total = sum(poll.corrected_pct for poll in polls)
        self.assertAlmostEqual(float(total), 1.0, places=6)

    def test_raises_without_party_modifiers(self):
        empty_election = Election.objects.create(
            name='Empty', election_type='FEDERAL', election_date=date(2024, 1, 1)
        )
        with self.assertRaises(ValueError):
            polling.run_national_polling(empty_election)


class DHondtTests(TestCase):
    def test_classic_four_party_example(self):
        # Standard textbook D'Hondt example: votes 340/280/160/60, 4 seats -> 2/1/1/0.
        votes_by_party = {'A': 340, 'B': 280, 'C': 160, 'D': 60}
        allocation = polling._dhondt_allocate(votes_by_party, 4)
        self.assertEqual(allocation, {'A': 2, 'B': 1, 'C': 1, 'D': 0})

    def test_allocates_exactly_the_requested_seats(self):
        votes_by_party = {'A': 100, 'B': 50, 'C': 25}
        allocation = polling._dhondt_allocate(votes_by_party, 7)
        self.assertEqual(sum(allocation.values()), 7)


class ListSeatsToggleTests(TestCase):
    def test_allocate_list_seats_skips_when_disabled(self):
        election = Election.objects.create(
            name='FPTP Only', election_type='FEDERAL', election_date=date(2024, 1, 1),
            uses_list_seats=False,
        )
        result = polling.allocate_list_seats(election)
        self.assertEqual(result, {'skipped': True, 'reason': 'uses_list_seats is False for this election'})

    def test_allocate_list_seats_requires_region_config_when_enabled(self):
        election = Election.objects.create(
            name='List Seats On', election_type='FEDERAL', election_date=date(2024, 1, 1),
            uses_list_seats=True,
        )
        with self.assertRaises(ValueError):
            polling.allocate_list_seats(election)
