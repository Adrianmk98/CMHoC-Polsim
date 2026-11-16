"""AI-assisted score suggestions for moderator grading.

Reuses the same LLM backend configured for NPCs (Ollama locally, Vertex in
production) to suggest a 0-10 score + short rationale for a piece of content.
Moderators review and can freely edit the suggestion before approving it.
"""
import logging
import re

logger = logging.getLogger(__name__)

RUBRIC = (
    "Score from 0 to 10 using this rubric: "
    "effort and length (is it a substantive contribution, not a one-liner), "
    "relevance (does it actually engage with the topic at hand), "
    "quality and coherence of the writing, "
    "and in-character political voice. "
    "Respond in EXACTLY this format, nothing else:\n"
    "SCORE: <number 0-10, one decimal allowed>\n"
    "RATIONALE: <one sentence explaining the score>"
)

_SCORE_RE = re.compile(r'SCORE:\s*([0-9]+(?:\.[0-9]+)?)', re.IGNORECASE)
_RATIONALE_RE = re.compile(r'RATIONALE:\s*(.+)', re.IGNORECASE | re.DOTALL)


def _parse_response(text):
    if not text:
        return None
    score_match = _SCORE_RE.search(text)
    if not score_match:
        return None
    try:
        score = float(score_match.group(1))
    except ValueError:
        return None
    score = max(0.0, min(10.0, score))

    rationale_match = _RATIONALE_RE.search(text)
    rationale = rationale_match.group(1).strip().splitlines()[0] if rationale_match else ''
    return {'score': score, 'rationale': rationale}


def _ask(system_prompt, user_prompt):
    from npcs.services import generate_text

    try:
        raw = generate_text(system_prompt, user_prompt)
    except Exception:
        logger.warning('AI grading request failed', exc_info=True)
        return None
    return _parse_response(raw)


def suggest_debate_score(debate_post):
    bill = debate_post.bill
    system_prompt = (
        "You are grading a mock-parliament debate post for a moderator. " + RUBRIC
    )
    user_prompt = (
        f"Bill {bill.bill_number}: \"{bill.title}\" ({bill.get_status_display()}, {debate_post.get_reading_stage_display()})\n"
        f"Summary: {bill.summary}\n\n"
        f"Debate post by {debate_post.author.username}:\n{debate_post.content}"
    )
    return _ask(system_prompt, user_prompt)


def suggest_press_score(press_release):
    system_prompt = (
        "You are grading a mock-parliament press release for a moderator. " + RUBRIC
    )
    user_prompt = (
        f"Title: {press_release.title} ({press_release.get_category_display()})\n"
        f"By: {press_release.author.username}\n\n"
        f"Content:\n{press_release.content}"
    )
    return _ask(system_prompt, user_prompt)


def suggest_legislation_score(bill):
    system_prompt = (
        "You are grading a mock-parliament bill (legislation) for a moderator. " + RUBRIC
    )
    user_prompt = (
        f"Bill {bill.bill_number}: \"{bill.title}\" ({bill.get_status_display()})\n"
        f"Sponsor: {bill.sponsor.username if bill.sponsor else 'unknown'}\n\n"
        f"Summary: {bill.summary}\n\n"
        f"Full text:\n{bill.full_text[:4000]}"
    )
    return _ask(system_prompt, user_prompt)
