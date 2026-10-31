import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def generate_reply(system_prompt, user_prompt):
    """Call the local Ollama chat API. Returns the generated text, or None on any failure."""
    try:
        response = requests.post(
            f'{settings.OLLAMA_BASE_URL}/api/chat',
            json={
                'model': settings.OLLAMA_MODEL,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                'stream': False,
            },
            timeout=30,
        )
        response.raise_for_status()
        content = response.json().get('message', {}).get('content', '').strip()
        return content or None
    except requests.RequestException:
        logger.warning('Ollama request failed; skipping NPC reply', exc_info=True)
        return None
    except (KeyError, ValueError):
        logger.warning('Unexpected Ollama response shape; skipping NPC reply', exc_info=True)
        return None
