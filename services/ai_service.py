"""Unified AI service dispatcher — routes to Groq or Gemini based on active_provider setting."""
from utils.helpers import get_setting
import services.groq_service as groq
import services.gemini_service as gemini
from services.groq_service import GroqRateLimitError
from services.gemini_service import GeminiError

DEFAULT_GROQ_MODEL = 'llama-3.3-70b-versatile'
DEFAULT_GEMINI_MODEL = 'gemini-2.0-flash'

# Re-export so callers can catch either
AIError = (GroqRateLimitError, GeminiError)


def get_active_provider(db):
    """Return 'groq' or 'gemini' based on stored setting."""
    return get_setting(db, 'active_provider', 'groq')


def is_configured(db):
    """Return True if the active provider has an API key set."""
    provider = get_active_provider(db)
    if provider == 'gemini':
        return bool(get_setting(db, 'gemini_api_key'))
    return bool(get_setting(db, 'groq_api_key'))


def get_active_config(db):
    """Return a dict with provider, api_key, model, temperature, top_p, max_tokens."""
    provider = get_active_provider(db)
    temperature = float(get_setting(db, 'groq_temperature', '0.7'))
    top_p = float(get_setting(db, 'groq_top_p', '0.9'))
    max_tokens = int(get_setting(db, 'groq_max_tokens', '4096'))
    if provider == 'gemini':
        return {
            'provider': 'gemini',
            'api_key': get_setting(db, 'gemini_api_key', ''),
            'model': get_setting(db, 'gemini_model', DEFAULT_GEMINI_MODEL),
            'temperature': temperature,
            'top_p': top_p,
            'max_tokens': max_tokens,
        }
    return {
        'provider': 'groq',
        'api_key': get_setting(db, 'groq_api_key', ''),
        'model': get_setting(db, 'groq_model', DEFAULT_GROQ_MODEL),
        'temperature': temperature,
        'top_p': top_p,
        'max_tokens': max_tokens,
    }


def _svc(provider):
    return gemini if provider == 'gemini' else groq


def generate_titles(api_key, model, project_info, temperature=0.9, top_p=0.9, max_tokens=1024, provider='groq'):
    return _svc(provider).generate_titles(api_key, model, project_info, temperature, top_p, max_tokens)


def generate_outline(api_key, model, project, characters_ctx, world_ctx, template,
                     temperature, top_p, max_tokens, provider='groq'):
    return _svc(provider).generate_outline(
        api_key, model, project, characters_ctx, world_ctx, template, temperature, top_p, max_tokens)


def generate_chapter(api_key, model, project, outline_chapter, characters_ctx,
                     world_ctx, memory_ctx, template, temperature, top_p, max_tokens, provider='groq'):
    return _svc(provider).generate_chapter(
        api_key, model, project, outline_chapter, characters_ctx,
        world_ctx, memory_ctx, template, temperature, top_p, max_tokens)


def generate_chapter_memory(api_key, model, chapter_title, chapter_content, project_genre, provider='groq'):
    return _svc(provider).generate_chapter_memory(api_key, model, chapter_title, chapter_content, project_genre)


def generate_matter(api_key, model, matter_type, project, characters_ctx, world_ctx,
                    temperature=0.7, provider='groq'):
    return _svc(provider).generate_matter(api_key, model, matter_type, project, characters_ctx, world_ctx, temperature)


def generate_book_premise(api_key, model, project_info, temperature=0.85, provider='groq'):
    return _svc(provider).generate_book_premise(api_key, model, project_info, temperature)


def generate_cover_prompt(api_key, model, project, provider='groq'):
    return _svc(provider).generate_cover_prompt(api_key, model, project)


def generate_image_prompt(api_key, model, chapter_title, chapter_summary, style, genre, provider='groq'):
    return _svc(provider).generate_image_prompt(api_key, model, chapter_title, chapter_summary, style, genre)
