"""One OpenAI-compatible transport. No inferred model or cloud fallback."""
import os
from dataclasses import dataclass

from openai import OpenAI


class ProviderError(RuntimeError):
    """Safe, operator-facing provider configuration/transport failure."""


@dataclass
class Provider:
    client: OpenAI
    model: str


def provider_from_env() -> Provider:
    selected = os.getenv('STILLROOM_PROVIDER', 'disabled')
    if selected == 'disabled':
        raise ProviderError('Inference disabled: explicitly set STILLROOM_PROVIDER and STILLROOM_MODEL.')
    if selected not in {'openai', 'ollama-cloud', 'ollama-local'}:
        raise ProviderError('Unknown STILLROOM_PROVIDER; no fallback is permitted.')
    model = os.getenv('STILLROOM_MODEL', '').strip()
    if not model:
        raise ProviderError('Set STILLROOM_MODEL explicitly; no default model is selected.')
    if selected == 'ollama-local':
        # A loopback Ollama endpoint can still dispatch cloud inference. Local mode
        # cannot prove model locality, so it remains disabled rather than guessing.
        raise ProviderError('ollama-local disabled until model locality is verified; no network call made.')
    if selected == 'openai':
        key = os.getenv('OPENAI_API_KEY', '').strip()
        if not key:
            raise ProviderError('OPENAI_API_KEY is required for explicit OpenAI opt-in.')
        url = 'https://api.openai.com/v1'
    else:
        key = 'ollama'
        url = 'http://127.0.0.1:11434/v1'
    return Provider(OpenAI(api_key=key, base_url=url, timeout=30.0, max_retries=0), model)
