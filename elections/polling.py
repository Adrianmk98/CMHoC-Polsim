"""Election polling simulation pipeline.

Mirrors the old CMHoC polling-calculator spreadsheet: per-user scores roll up into a
party modifier, which becomes a national poll (with random "fuzz"), which splits
regionally, which is applied as a swing onto each riding's baseline (reusing
elections.services.project_riding_result), and optionally feeds a D'Hondt allocation of
proportional regional list seats.

Each stage is a plain function a mod runs in order (see elections/admin.py actions),
writing a snapshot of that stage's rows. Nothing here runs automatically.
"""
import random as random_module
from collections import defaultdict
from decimal import Decimal

from django.contrib.auth.models import User

from forum.models import Province

from .models import (
    CandidateResult, ElectionRegionSeats, NationalPoll, PartyModifier,
    RegionalListSeat, RegionalPoll,
)
from .services import project_riding_result

# Inferred from the source spreadsheet's sample rows (reproduces them exactly):
# max_variance = true_polling_pct * margin_of_error * DEFAULT_VOLATILITY_MULTIPLIER
DEFAULT_MARGIN_OF_ERROR = Decimal('0.12')
DEFAULT_VOLATILITY_MULTIPLIER = Decimal('5')


def compute_party_modifiers(election):
    """Sum each party's active members' personal modifier (scores app) into PartyModifier
    rows for this election. Other PartyModifier fields (platform/press/etc) are mod-entered
    separately and left untouched here."""
    from scores.models import ParliamentSession, get_player_totals
    from parties.models import Party as GameParty

    session = ParliamentSession.objects.filter(is_active=True).first()
    if session is None:
        raise ValueError("No active ParliamentSession to pull scores from.")

    updated = []
    for game_party in GameParty.objects.filter(political_party__isnull=False).select_related('political_party'):
        political_party = game_party.political_party
        member_users = User.objects.filter(
            party_memberships__party=game_party,
            party_memberships__is_active=True,
        ).distinct()

        total = Decimal('0')
        for user in member_users:
            total += get_player_totals(session, user)['active_modifier']

        modifier, _ = PartyModifier.objects.update_or_create(
            election=election, party=political_party,
            defaults={'personal_mods_total': total},
        )
        updated.append(modifier)
    return updated


def run_national_polling(election, margin_of_error=DEFAULT_MARGIN_OF_ERROR,
                          volatility_multiplier=DEFAULT_VOLATILITY_MULTIPLIER,
                          random_overrides=None):
    """Normalize PartyModifier totals into a polling %, apply random fuzz, renormalize.

    random_overrides: optional {party_id: Decimal 0..1} to force a specific "random roll"
    instead of drawing one — used for mod-entered rolls and for tests that check this
    reproduces the source spreadsheet's numbers exactly.
    """
    random_overrides = random_overrides or {}
    modifiers = list(election.party_modifiers.select_related('party'))
    if not modifiers:
        raise ValueError("No PartyModifier rows for this election — run compute_party_modifiers() first.")

    total_modifier_sum = sum((m.total_modifier for m in modifiers), Decimal('0'))
    if total_modifier_sum <= 0:
        raise ValueError("Total party modifier is zero; cannot compute polling percentages.")

    rows = []
    for modifier in modifiers:
        true_pct = modifier.total_modifier / total_modifier_sum

        override = random_overrides.get(modifier.party_id)
        random_number = Decimal(str(override)) if override is not None else Decimal(str(random_module.random()))

        max_variance = true_pct * margin_of_error * volatility_multiplier
        actual_variance = max_variance * (Decimal('1') - Decimal('2') * random_number)
        fuzzed_pct = true_pct + actual_variance

        rows.append({
            'party': modifier.party,
            'true_pct': true_pct,
            'random_number': random_number,
            'max_variance': max_variance,
            'actual_variance': actual_variance,
            'fuzzed_pct': fuzzed_pct,
        })

    fuzzed_sum = sum((row['fuzzed_pct'] for row in rows), Decimal('0'))
    if fuzzed_sum <= 0:
        raise ValueError("Fuzzed polling total is zero; cannot normalize.")

    polls = []
    for row in rows:
        corrected_pct = row['fuzzed_pct'] / fuzzed_sum
        poll, _ = NationalPoll.objects.update_or_create(
            election=election, party=row['party'],
            defaults={
                'true_polling_pct': row['true_pct'],
                'random_number': row['random_number'],
                'max_variance': row['max_variance'],
                'actual_variance': row['actual_variance'],
                'fuzzed_pct': row['fuzzed_pct'],
                'corrected_pct': corrected_pct,
            },
        )
        polls.append(poll)
    return polls


def run_regional_polling(election, regional_swing=None):
    """Spread each party's national corrected_pct across regions, nudged by an optional
    mod-entered swing in percentage points: {(party_id, region): Decimal}. Regions with no
    swing entries just inherit the national split (renormalized per region)."""
    regional_swing = regional_swing or {}
    national_polls = list(election.national_polls.select_related('party'))
    if not national_polls:
        raise ValueError("No NationalPoll rows for this election — run run_national_polling() first.")

    results = []
    for region, _ in Province.REGION_CHOICES:
        adjusted = {}
        for poll in national_polls:
            swing = Decimal(str(regional_swing.get((poll.party_id, region), 0))) / Decimal('100')
            adjusted[poll.party] = max(Decimal('0'), poll.corrected_pct + swing)

        total = sum(adjusted.values())
        if total == 0:
            continue

        for party, value in adjusted.items():
            regional_pct = value / total
            obj, _ = RegionalPoll.objects.update_or_create(
                election=election, party=party, region=region,
                defaults={'regional_pct': regional_pct},
            )
            results.append(obj)
    return results


def apply_polling_to_ridings(election):
    """For each riding, turn (regional % − national %) into a swing and feed it through the
    existing swing-based projector, writing projected votes onto CandidateResult rows."""
    national_by_party = {poll.party_id: poll for poll in election.national_polls.all()}
    if not national_by_party:
        raise ValueError("No NationalPoll rows for this election — run run_national_polling() first.")

    updated, skipped = 0, 0
    riding_results = election.riding_results.select_related('riding').prefetch_related(
        'candidate_results__party', 'riding__provinces',
    )
    for riding_result in riding_results:
        riding = riding_result.riding
        province = riding.provinces.first()
        region = province.region if province else None

        regional_by_party = {}
        if region:
            regional_by_party = {
                poll.party_id: poll
                for poll in RegionalPoll.objects.filter(election=election, region=region)
            }

        swing_by_party = {}
        for party_id, national_poll in national_by_party.items():
            regional_poll = regional_by_party.get(party_id)
            target_pct = regional_poll.regional_pct if regional_poll else national_poll.corrected_pct
            swing_by_party[party_id] = (target_pct - national_poll.corrected_pct) * Decimal('100')

        projections = project_riding_result(riding, swing_by_party=swing_by_party)
        candidates = list(riding_result.candidate_results.all())
        if not projections or not candidates:
            skipped += 1
            continue

        projection_by_party = {proj.party.id: proj for proj in projections}
        updated_any = False
        for candidate in candidates:
            projection = projection_by_party.get(candidate.party_id)
            if projection is None:
                continue
            candidate.votes = projection.projected_votes
            candidate.save()
            updated_any = True

        if updated_any:
            updated += 1
        else:
            skipped += 1

    return {'updated': updated, 'skipped': skipped}


def _dhondt_allocate(votes_by_party, seats):
    """Standard D'Hondt highest-averages allocation: {party_id: votes} -> {party_id: seats}."""
    allocation = {party_id: 0 for party_id in votes_by_party}
    for _ in range(seats):
        best_party_id, best_quotient = None, Decimal('-1')
        for party_id, votes in votes_by_party.items():
            quotient = Decimal(votes) / Decimal(allocation[party_id] + 1)
            if quotient > best_quotient:
                best_quotient, best_party_id = quotient, party_id
        allocation[best_party_id] += 1
    return allocation


def allocate_list_seats(election):
    """D'Hondt-allocate each region's configured list seats from that region's riding vote
    totals. No-op if election.uses_list_seats is False."""
    if not election.uses_list_seats:
        return {'skipped': True, 'reason': 'uses_list_seats is False for this election'}

    region_configs = {
        config.region: config.list_seats
        for config in election.region_seat_configs.all()
    }
    if not region_configs:
        raise ValueError("No ElectionRegionSeats configured for this election.")

    results = []
    for region, seat_count in region_configs.items():
        if seat_count <= 0:
            continue

        votes_by_party = defaultdict(int)
        candidates = CandidateResult.objects.filter(
            riding_result__election=election,
            riding_result__riding__provinces__region=region,
        ).select_related('party')
        for candidate in candidates:
            if candidate.party_id:
                votes_by_party[candidate.party_id] += candidate.votes

        if not votes_by_party:
            continue

        allocation = _dhondt_allocate(votes_by_party, seat_count)
        for party_id, seats_won in allocation.items():
            obj, _ = RegionalListSeat.objects.update_or_create(
                election=election, party_id=party_id, region=region,
                defaults={'list_votes': votes_by_party[party_id], 'seats_won': seats_won},
            )
            results.append(obj)
    return results
