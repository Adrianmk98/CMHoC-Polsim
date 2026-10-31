import logging
import random
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import NPCProfile

logger = logging.getLogger(__name__)

MAX_CONTEXT_POSTS = 6


def _global_cooldown_active():
    """A short, site-wide cooldown across *all* NPCs, independent of each NPC's own
    per-character cooldown_minutes. Caps worst-case LLM call frequency even if many
    NPCs happen to be off-cooldown and roll reply_chance favorably at once."""
    seconds = settings.NPCS_GLOBAL_COOLDOWN_SECONDS
    if seconds <= 0:
        return False
    last_posted_at = (
        NPCProfile.objects.exclude(last_posted_at__isnull=True)
        .order_by('-last_posted_at')
        .values_list('last_posted_at', flat=True)
        .first()
    )
    if last_posted_at is None:
        return False
    return timezone.now() < last_posted_at + timedelta(seconds=seconds)


def _generate_reply(system_prompt, user_prompt):
    """Dispatch to the configured NPC LLM backend ('ollama' for local dev, 'vertex' in production)."""
    if settings.NPC_LLM_BACKEND == 'vertex':
        from . import vertex_client
        return vertex_client.generate_reply(system_prompt, user_prompt)

    from . import ollama_client
    return ollama_client.generate_reply(system_prompt, user_prompt)


def _npc_persona_header(npc_profile):
    user = npc_profile.user_profile.user
    party = npc_profile.user_profile.party
    party_name = party.get_name_display() if party else 'Independent'
    role = npc_profile.user_profile.role or 'Member of Parliament'
    riding = npc_profile.user_profile.get_riding_display() or 'an unspecified riding'

    return (
        f"You are {user.first_name or user.username} {user.last_name}".strip() + ", "
        f"a {role} for {riding}, representing the {party_name}. "
        f"{npc_profile.persona}\n\n"
        "Write a single in-character forum/debate post (2-5 sentences, no preamble, "
        "no signature, no markdown headers). Stay on topic and consistent with your "
        "party's political stance."
    )


def select_candidate_npc(exclude_user_ids=None):
    """Pick one eligible, off-cooldown NPC, weighted by reply_chance. Returns None if nobody qualifies."""
    if _global_cooldown_active():
        return None

    exclude_user_ids = exclude_user_ids or set()

    candidates = [
        npc for npc in NPCProfile.objects.select_related('user_profile__user', 'user_profile__party').filter(is_active=True)
        if npc.user_profile.user_id not in exclude_user_ids and npc.can_post_now()
    ]
    if not candidates:
        return None

    weighted = [npc for npc in candidates if random.random() <= npc.reply_chance]
    if not weighted:
        return None
    return random.choice(weighted)


def _recent_posts_text(posts, label_fn):
    lines = []
    for post in posts[-MAX_CONTEXT_POSTS:]:
        lines.append(f"{label_fn(post)}: {post.content}")
    return "\n\n".join(lines) if lines else "(no prior posts)"


def maybe_reply_to_thread(post):
    """post: a forum.Post that was just created by a human. Maybe have an NPC reply in the same thread."""
    if not settings.NPCS_ENABLED:
        return

    thread = post.thread
    already_replied = set(thread.posts.values_list('author_id', flat=True))
    npc = select_candidate_npc(exclude_user_ids=already_replied)
    if npc is None:
        return

    recent = list(thread.posts.order_by('created_at'))
    context = _recent_posts_text(recent, lambda p: p.author.username)

    system_prompt = _npc_persona_header(npc)
    user_prompt = (
        f"Forum thread: \"{thread.title}\"\n\n"
        f"Recent posts:\n{context}\n\n"
        "Write your reply to this thread now."
    )

    content = _generate_reply(system_prompt, user_prompt)
    if not content:
        return

    from forum.models import Post
    Post.objects.create(thread=thread, author=npc.user_profile.user, content=content)
    npc.mark_posted()


def maybe_reply_to_debate(debate_post):
    """debate_post: a voting.BillDebatePost just created by a human. Maybe have an NPC add a debate post."""
    if not settings.NPCS_ENABLED:
        return

    bill = debate_post.bill
    stage = debate_post.reading_stage
    siblings = bill.debate_posts.filter(reading_stage=stage)
    already_replied = set(siblings.values_list('author_id', flat=True))
    npc = select_candidate_npc(exclude_user_ids=already_replied)
    if npc is None:
        return

    recent = list(siblings.order_by('created_at'))
    context = _recent_posts_text(recent, lambda p: p.author.username)

    system_prompt = _npc_persona_header(npc)
    user_prompt = (
        f"Bill {bill.bill_number}: \"{bill.title}\" ({bill.get_status_display()})\n"
        f"Summary: {bill.summary}\n\n"
        f"Debate so far at this stage:\n{context}\n\n"
        "Write your debate contribution now."
    )

    content = _generate_reply(system_prompt, user_prompt)
    if not content:
        return

    from voting.models import BillDebatePost
    BillDebatePost.objects.create(bill=bill, reading_stage=stage, author=npc.user_profile.user, content=content)
    npc.mark_posted()


def maybe_comment_on_press_release(press_release):
    """press_release: a press.PressRelease. Maybe have an NPC add a PressComment reacting to it."""
    if not settings.NPCS_ENABLED:
        return

    already_replied = set(press_release.comments.values_list('author_id', flat=True))
    already_replied.add(press_release.author_id)
    npc = select_candidate_npc(exclude_user_ids=already_replied)
    if npc is None:
        return

    recent_comments = list(press_release.comments.order_by('created_at'))
    context = _recent_posts_text(recent_comments, lambda c: c.author.username)

    system_prompt = _npc_persona_header(npc)
    user_prompt = (
        f"Press release: \"{press_release.title}\" (by {press_release.author.username})\n"
        f"Excerpt: {press_release.excerpt or press_release.content[:500]}\n\n"
        f"Existing comments:\n{context}\n\n"
        "Write your comment reacting to this press release now."
    )

    content = _generate_reply(system_prompt, user_prompt)
    if not content:
        return

    from press.models import PressComment
    PressComment.objects.create(press_release=press_release, author=npc.user_profile.user, content=content)
    npc.mark_posted()
