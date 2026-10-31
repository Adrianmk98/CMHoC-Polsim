import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from forum.models import (
    Cabinet, CabinetPosition, Flair, ForumCategory,
    PoliticalParty, PositionHistory, Post, Province, Riding, Thread,
    UserProfile,
)
from voting.models import Ballot, Bill, BillDebatePost, Vote
from press.models import PressComment, PressRelease
from parties.models import JoinRequest, Party, PartyMembership, PartyRole
from elections.models import CandidateResult, Election, RidingElectionResult
from scores.models import ParliamentSession, PlayerLT, ScoreEntry
from npcs.models import NPCProfile

TEST_PASSWORD = "testpass123"

RIDINGS = [
    ("Toronto Centre", "ON"), ("Ottawa South", "ON"), ("Scarborough North", "ON"),
    ("Vancouver Granville", "BC"), ("Victoria", "BC"),
    ("Calgary Centre", "AB"), ("Edmonton Strathcona", "AB"),
    ("Westmount—Ville-Marie", "QC"), ("Papineau", "QC"), ("Quebec Centre", "QC"),
    ("Winnipeg South", "MB"), ("Halifax", "NS"), ("Saint John", "NB"),
    ("Regina—Wascana", "SK"), ("St. John's East", "NL"), ("Charlottetown", "PE"),
    ("Whitehorse", "YT"),
]

MP_NAMES = [
    ("Sarah", "Chen"), ("Marcus", "Dubois"), ("Priya", "Sharma"), ("Liam", "O'Brien"),
    ("Fatima", "Khan"), ("Jordan", "MacDonald"), ("Elena", "Petrov"), ("Noah", "Beaulieu"),
    ("Grace", "Tremblay"), ("Caleb", "Nguyen"),
]

PARTY_CODES = ["LIB", "CON", "NDP", "BQ", "GRN", "PPC", "IND"]


class Command(BaseCommand):
    help = "Seed the database with realistic test data across every app (idempotent, safe to re-run)."

    def handle(self, *args, **options):
        with transaction.atomic():
            provinces = self.seed_provinces()
            ridings = self.seed_ridings(provinces)
            parties = self.seed_forum_parties()
            org_parties = self.seed_party_orgs(parties)
            users, user_party_codes = self.seed_users(ridings, org_parties)
            self.seed_party_leadership(org_parties, users)
            self.seed_cabinet(users, parties)
            categories, flairs = self.seed_forum_categories()
            self.seed_threads_and_posts(categories, flairs, users)
            bills = self.seed_bills(users)
            self.seed_votes_and_debates(bills, users)
            self.seed_press(parties, users)
            self.seed_leadership_and_confidence(org_parties, users)
            self.seed_elections(ridings, parties, users, user_party_codes)
            self.seed_scores(users)
            self.seed_npcs(ridings, org_parties)

        self.stdout.write(self.style.SUCCESS("Seed data complete."))

    # --- forum ---

    def seed_provinces(self):
        provinces = {}
        for code, _ in Province.PROVINCE_CHOICES:
            provinces[code], _ = Province.objects.get_or_create(code=code)
        self.stdout.write(f"Provinces: {len(provinces)}")
        return provinces

    def seed_ridings(self, provinces):
        ridings = []
        for name, prov_code in RIDINGS:
            riding, created = Riding.objects.get_or_create(
                name=name,
                defaults={"population": random.randint(60000, 120000), "is_active": True},
            )
            if created:
                riding.provinces.add(provinces[prov_code])
            ridings.append(riding)
        self.stdout.write(f"Ridings: {len(ridings)}")
        return ridings

    def seed_forum_parties(self):
        parties = {}
        for code, _ in PoliticalParty.PARTY_CHOICES:
            colors = {
                "LIB": "#D71920", "CON": "#1A4782", "NDP": "#F37021", "BQ": "#00A2E2",
                "GRN": "#3D9B35", "PPC": "#2B2B2B", "IND": "#808080",
            }
            parties[code], _ = PoliticalParty.objects.get_or_create(
                name=code, defaults={"color": colors[code]}
            )
        self.stdout.write(f"Forum parties: {len(parties)}")
        return parties

    def seed_users(self, ridings, org_parties):
        users = []
        user_party_codes = {}
        party_cycle = ["LIB", "LIB", "LIB", "CON", "CON", "NDP", "NDP", "BQ", "GRN", "PPC"]
        for i, ((first, last), riding, party_code) in enumerate(zip(MP_NAMES, ridings, party_cycle)):
            username = f"test_mp_{i+1:02d}"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": first, "last_name": last, "email": f"{username}@example.test"},
            )
            if created:
                user.set_password(TEST_PASSWORD)
                user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.riding = riding
            profile.role = "MP"
            profile.bio = f"{first} {last} is the Member of Parliament for {riding.name}."
            profile.save()

            # Joining the org triggers the signal that fills in profile.party/PartyHistory
            org = org_parties.get(party_code)
            if org:
                PartyMembership.objects.get_or_create(
                    user=user, party=org, defaults={"is_founding_member": True, "is_active": True},
                )

            PositionHistory.objects.get_or_create(
                user_profile=profile, position_type="MP", position_title="Member of Parliament",
                defaults={"riding_obj": riding, "start_date": timezone.now().date() - timedelta(days=365)},
            )
            users.append(user)
            user_party_codes[user.username] = party_code
        self.stdout.write(f"Test MPs: {len(users)}")
        return users, user_party_codes

    def seed_cabinet(self, users, parties):
        pm_user = users[0]  # LIB
        cabinet, created = Cabinet.objects.get_or_create(
            name="47th Canadian Ministry",
            defaults={
                "prime_minister": pm_user, "government_party": parties["LIB"],
                "start_date": timezone.now().date() - timedelta(days=200),
                "is_current": True, "description": "Test seed cabinet for the 47th Parliament.",
            },
        )
        portfolios = [
            ("PM", "Prime Minister", "Prime Minister", 1, pm_user),
            ("MINISTER", "Finance", "Minister of Finance", 2, users[1]),
            ("MINISTER", "Foreign Affairs", "Minister of Foreign Affairs", 3, users[2]),
            ("MINISTER", "Health", "Minister of Health", 4, users[3] if len(users) > 3 else pm_user),
        ]
        for position_type, portfolio, title, order, user in portfolios:
            profile = UserProfile.objects.get(user=user)
            CabinetPosition.objects.get_or_create(
                cabinet=cabinet, user_profile=profile, position_type=position_type, portfolio=portfolio,
                defaults={"title": title, "order": order, "start_date": cabinet.start_date},
            )
        self.stdout.write(f"Cabinet: {cabinet.name}")

    def seed_forum_categories(self):
        categories = {}
        for name, desc, order in [
            ("House of Commons", "Floor debate on government business.", 1),
            ("Committee Discussions", "Standing committee discussion threads.", 2),
            ("General Chat", "Off-topic and general political discussion.", 3),
        ]:
            categories[name], _ = ForumCategory.objects.get_or_create(
                name=name, defaults={"description": desc, "order": order}
            )
        flairs = {}
        for name, color in [("Debate", "#1A4782"), ("Announcement", "#D71920"), ("Question", "#F37021")]:
            flairs[name], _ = Flair.objects.get_or_create(name=name, defaults={"color": color})
        self.stdout.write(f"Forum categories: {len(categories)}")
        return categories, flairs

    def seed_threads_and_posts(self, categories, flairs, users):
        thread_specs = [
            ("House of Commons", "Debate: Budget Implementation Act", "Debate",
             "Let's discuss the government's latest budget implementation bill."),
            ("House of Commons", "Question Period Highlights", "Question",
             "What were the key exchanges in today's question period?"),
            ("Committee Discussions", "Finance Committee: Pre-Budget Consultations", "Debate",
             "Sharing notes from the pre-budget consultation hearings."),
            ("General Chat", "Welcome to the 47th Parliament", "Announcement",
             "Welcome all returning and new members!"),
        ]
        threads = []
        for cat_name, title, flair_name, first_post in thread_specs:
            thread, created = Thread.objects.get_or_create(
                title=title, category=categories[cat_name],
                defaults={"author": users[0], "flair": flairs[flair_name]},
            )
            if created:
                Post.objects.create(thread=thread, author=users[0], content=first_post)
                for user in random.sample(users[1:], k=min(3, len(users) - 1)):
                    Post.objects.create(
                        thread=thread, author=user,
                        content=f"As the member for {user.profile.get_riding_display()}, "
                                f"I think this deserves careful consideration.",
                    )
            threads.append(thread)
        self.stdout.write(f"Threads: {len(threads)}")
        return threads

    # --- voting ---

    def seed_bills(self, users):
        bill_specs = [
            ("C-10", "Budget Implementation Act, 2026", "DRAFT",
             "Implements measures from the 2026 federal budget."),
            ("C-15", "Affordable Housing Act", "SECOND_READING",
             "Establishes a national affordable housing strategy."),
            ("C-22", "Clean Energy Transition Act", "THIRD_READING",
             "Accelerates investment in renewable energy infrastructure."),
            ("C-30", "Veterans Support Enhancement Act", "ROYAL_ASSENT",
             "Expands support programs for veterans and their families."),
            ("C-41", "Digital Privacy Modernization Act", "FAILED",
             "Would have updated digital privacy protections; defeated at second reading."),
        ]
        bills = []
        for number, title, status, summary in bill_specs:
            bill, _ = Bill.objects.get_or_create(
                bill_number=number,
                defaults={
                    "title": title, "sponsor": random.choice(users), "status": status,
                    "summary": summary, "full_text": f"{summary}\n\n(Full legislative text omitted for test data.)",
                },
            )
            bills.append(bill)
        self.stdout.write(f"Bills: {len(bills)}")
        return bills

    def seed_votes_and_debates(self, bills, users):
        for bill in bills:
            for stage in ["FIRST_READING", "SECOND_READING"]:
                if bill.status in ("DRAFT",) and stage != "FIRST_READING":
                    continue
                for user in random.sample(users, k=min(3, len(users))):
                    BillDebatePost.objects.get_or_create(
                        bill=bill, reading_stage=stage, author=user,
                        defaults={"content": f"{user.first_name} {user.last_name} speaks on {bill.bill_number} "
                                              f"at the {stage.replace('_', ' ').lower()} stage."},
                    )
            if bill.status in ("THIRD_READING", "ROYAL_ASSENT", "FAILED"):
                vote, _ = Vote.objects.get_or_create(
                    bill=bill, vote_type="SECOND",
                    defaults={
                        "description": f"Second reading vote on {bill.bill_number}",
                        "closes_at": timezone.now() - timedelta(days=1),
                        "is_active": False, "created_by": users[0],
                    },
                )
                for user in users:
                    choice = "YEA" if bill.status != "FAILED" else random.choice(["YEA", "NAY"])
                    Ballot.objects.get_or_create(vote_session=vote, voter=user, defaults={"vote": choice})
        self.stdout.write("Debate posts and votes seeded.")

    # --- press ---

    def seed_press(self, parties, users):
        releases = [
            ("LIB", "Government Announces New Housing Investment", "ANNOUNCEMENT",
             "The government today announced a major new investment in affordable housing."),
            ("CON", "Opposition Responds to Budget Overspending", "RESPONSE",
             "The Official Opposition criticized the government's latest spending commitments."),
            ("NDP", "NDP Calls for Expanded Pharmacare Coverage", "POLICY",
             "The NDP is calling on the government to expand pharmacare to cover more conditions."),
        ]
        for party_code, title, category, content in releases:
            pr, created = PressRelease.objects.get_or_create(
                title=title,
                defaults={
                    "author": users[0], "party": parties[party_code], "content": content,
                    "category": category,
                },
            )
            if created:
                for user in random.sample(users, k=min(2, len(users))):
                    PressComment.objects.create(press_release=pr, author=user, content="Thanks for sharing this update.")
        self.stdout.write("Press releases seeded.")

    # --- parties (org app) ---

    def seed_party_orgs(self, parties):
        """Create the actual joinable party orgs - this is what UserProfile.party/PartyHistory
        point at. Leadership roles are assigned afterwards, once seed_users exists, by seed_leadership_roles."""
        org_specs = [
            ("Liberal Party of Canada", "LIB", "CENTER_LEFT"),
            ("Conservative Party of Canada", "CON", "RIGHT"),
            ("New Democratic Party", "NDP", "LEFT"),
            ("Bloc Québécois", "BQ", "CENTER_LEFT"),
            ("Green Party of Canada", "GRN", "LEFT"),
            ("People's Party of Canada", "PPC", "RIGHT"),
        ]
        org_parties = {}
        for name, code, ideology in org_specs:
            org, _ = Party.objects.get_or_create(
                name=name,
                defaults={
                    "abbreviation": code, "ideology": ideology,
                    "platform": f"The {name} platform for the 47th Parliament.",
                },
            )
            org_parties[code] = org
        self.stdout.write(f"Party orgs: {len(org_parties)}")
        return org_parties

    def seed_party_leadership(self, org_parties, users):
        leadership_specs = [
            ("LIB", users[0], users[1] if len(users) > 1 else users[0]),
            ("CON", users[4] if len(users) > 4 else users[0], users[0]),
            ("NDP", users[5] if len(users) > 5 else users[0], users[0]),
        ]
        for code, leader, press_sec in leadership_specs:
            org = org_parties.get(code)
            if not org:
                continue
            PartyRole.objects.get_or_create(
                party=org, user=leader, role="LEADER", defaults={"appointed_by": leader},
            )
            if press_sec != leader:
                PartyRole.objects.get_or_create(
                    party=org, user=press_sec, role="PRESS", defaults={"appointed_by": leader},
                )

    def seed_leadership_and_confidence(self, org_parties, users):
        ndp = org_parties.get("NDP")
        if not ndp:
            return
        election, created = LeadershipElectionCompat(ndp)
        self.stdout.write("Leadership/confidence votes seeded.")

    # --- elections ---

    def seed_elections(self, ridings, parties, users, user_party_codes):
        election, _ = Election.objects.get_or_create(
            name="46th General Election",
            defaults={
                "election_type": "FEDERAL", "election_date": timezone.now().date() - timedelta(days=400),
                "is_completed": True, "total_seats": len(ridings),
            },
        )
        for riding, user in zip(ridings, users):
            profile = UserProfile.objects.get(user=user)
            total_votes = random.randint(20000, 45000)
            result, created = RidingElectionResult.objects.get_or_create(
                election=election, riding=riding,
                defaults={
                    "winner": profile, "total_votes_cast": total_votes,
                    "total_registered_voters": total_votes + random.randint(5000, 15000),
                },
            )
            if created:
                winner_votes = int(total_votes * random.uniform(0.38, 0.55))
                party_code = user_party_codes.get(user.username)
                CandidateResult.objects.create(
                    riding_result=result, candidate=profile, party=parties.get(party_code),
                    votes=winner_votes, is_winner=True, is_incumbent=True,
                )
        self.stdout.write(f"Election results: {RidingElectionResult.objects.filter(election=election).count()}")

    # --- scores ---

    def seed_scores(self, users):
        session, _ = ParliamentSession.objects.get_or_create(
            name="47th Parliament", defaults={"start_date": timezone.now().date() - timedelta(days=200), "is_active": True},
        )
        for user in users:
            PlayerLT.objects.get_or_create(session=session, user=user, defaults={"lt_score": random.randint(10, 100)})
            ScoreEntry.objects.get_or_create(
                session=session, user=user, score_type="DEBATE", description="Seeded test debate contribution",
                defaults={"score": random.randint(1, 10), "created_by": user},
            )
        self.stdout.write("Scores seeded.")

    # --- npcs ---

    def seed_npcs(self, ridings, org_parties):
        import os
        from django.conf import settings as dj_settings

        personas_dir = os.path.join(dj_settings.BASE_DIR, "npcs", "personas")
        persona_files = [
            ("1_green_eco_socialist.txt", "GRN", "npc_green_mp"),
            ("2_ndp_labour_organizer.txt", "NDP", "npc_ndp_mp"),
            ("3_liberal_pragmatist.txt", "LIB", "npc_liberal_mp"),
            ("4_bq_quebec_nationalist.txt", "BQ", "npc_bq_mp"),
            ("5_independent_swing_voter.txt", "IND", "npc_independent_mp"),
            ("6_conservative_fiscal_hawk.txt", "CON", "npc_conservative_mp"),
            ("7_ppc_populist_libertarian.txt", "PPC", "npc_ppc_mp"),
        ]
        used_ridings = ridings[len(persona_files) * -1:]
        created_count = 0
        for (filename, party_code, username), riding in zip(persona_files, used_ridings):
            if NPCProfile.objects.filter(user_profile__user__username=username).exists():
                continue
            path = os.path.join(personas_dir, filename)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                persona_text = f.read().strip()

            user = User.objects.create(username=username)
            user.set_unusable_password()
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.riding = riding
            profile.role = "MP"
            profile.save()

            # IND has no joinable org - an independent NPC simply has no party membership
            org = org_parties.get(party_code)
            if org:
                PartyMembership.objects.get_or_create(
                    user=user, party=org, defaults={"is_active": True},
                )

            NPCProfile.objects.create(user_profile=profile, persona=persona_text)
            created_count += 1
        self.stdout.write(f"NPCs seeded: {created_count}")


def LeadershipElectionCompat(party):
    """Minimal leadership election + one confidence vote, created lazily so an import error here can't break the rest of seeding."""
    from parties.models import ConfidenceVote, LeadershipCandidate, LeadershipElection

    election, created = LeadershipElection.objects.get_or_create(
        party=party, title=f"{party.name} Leadership Review",
        defaults={"closes_at": timezone.now() + timedelta(days=14), "trigger": "SCHEDULED"},
    )
    if created and party.leader:
        LeadershipCandidate.objects.get_or_create(election=election, user=party.leader)

    if party.leader:
        ConfidenceVote.objects.get_or_create(
            party=party, target_leader=party.leader,
            defaults={
                "reason": "Routine test confidence vote seeded for QA purposes.",
                "initiated_by": party.leader, "closes_at": timezone.now() + timedelta(days=7),
            },
        )
    return election, created
