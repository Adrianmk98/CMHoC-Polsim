import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        if settings.GEMINI_API_KEY:
            # Gemini Developer API (AI Studio key) - used as a fallback when the
            # GCE service account lacks generative-model access on Vertex AI.
            _client = genai.Client(api_key=settings.GEMINI_API_KEY)
        else:
            _client = genai.Client(
                enterprise=True,
                project=settings.VERTEX_PROJECT_ID,
                location=settings.VERTEX_LOCATION,
            )
    return _client


def generate_reply(system_prompt, user_prompt):
    """Call Vertex AI's Gemini API. Returns the generated text, or None on any failure."""
    try:
        response = _get_client().models.generate_content(
            model=settings.VERTEX_MODEL,
            contents=user_prompt,
            config={'system_instruction': system_prompt},
        )
        content = (response.text or '').strip()
        return content or None
    except Exception:
        logger.warning('Vertex AI request failed; skipping NPC reply', exc_info=True)
        return None
