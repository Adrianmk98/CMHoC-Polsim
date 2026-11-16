"""Swing calculator: projects a riding result from a baseline + swing %, for mods to
review and adjust before saving real CandidateResult rows. Pure arithmetic, no persistence."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PartyProjection:
    party: object  # forum.models.PoliticalParty
    baseline_share: Decimal
    projected_share: Decimal
    projected_votes: int


class NoBaselineData(Exception):
    """Raised when a riding has neither prior results nor a static baseline to project from."""


def _get_baseline_shares(riding):
    """Return {party: share_percent} from the riding's most recent real result,
    falling back to its static baseline_party/baseline_vote_share fields."""
    last_result = riding.election_results.order_by('-election__election_date').first()
    if last_result:
        candidates = list(last_result.candidate_results.all())
        if candidates:
            return (
                {c.party: Decimal(c.vote_percentage) for c in candidates if c.party and c.vote_percentage is not None},
                last_result.total_votes_cast,
            )

    if riding.baseline_party and riding.baseline_vote_share is not None:
        return ({riding.baseline_party: Decimal(riding.baseline_vote_share)}, None)

    return (None, None)


def project_riding_result(riding, swing_by_party=None, total_votes_cast=None):
    """
    riding: a forum.models.Riding instance.
    swing_by_party: {party_id: Decimal percentage-point swing}, positive = gain.
    total_votes_cast: override for projected vote totals; else uses baseline's own total.

    Returns a list[PartyProjection] ordered winner-first, or None if the riding has no
    baseline data to project from (mod must enter results manually).
    """
    swing_by_party = swing_by_party or {}
    baseline_shares, baseline_total_votes = _get_baseline_shares(riding)
    if not baseline_shares:
        return None

    votes_total = total_votes_cast if total_votes_cast is not None else (baseline_total_votes or 0)

    # Apply swing and clamp at 0
    adjusted = {}
    for party, baseline_share in baseline_shares.items():
        swing = Decimal(str(swing_by_party.get(party.id, 0)))
        adjusted[party] = max(Decimal('0'), baseline_share + swing)

    # Renormalize to sum to 100
    total = sum(adjusted.values())
    if total == 0:
        return None

    projections = []
    for party, baseline_share in baseline_shares.items():
        projected_share = (adjusted[party] / total) * Decimal('100')
        projected_votes = int(round((projected_share / Decimal('100')) * votes_total))
        projections.append(PartyProjection(
            party=party,
            baseline_share=baseline_share,
            projected_share=projected_share,
            projected_votes=projected_votes,
        ))

    projections.sort(key=lambda p: p.projected_share, reverse=True)
    return projections
