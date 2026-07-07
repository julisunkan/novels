"""Groq API integration service."""
import re
import time
import json
from groq import Groq, RateLimitError


# ── Rate-limit helpers ──────────────────────────────────────────────────────

class GroqRateLimitError(Exception):
    """Raised when the Groq API returns 429 and the wait is too long to auto-retry."""
    def __init__(self, message, retry_after_seconds=None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def _parse_retry_seconds(error_str):
    """
    Extract the retry-after duration in seconds from a Groq 429 error message.
    Handles formats like '6m18.432s' or '45.123s'.
    Returns float seconds, or None if unparseable.
    """
    m = re.search(r'try again in (?:(\d+)m)?(\d+(?:\.\d+)?)s', str(error_str))
    if not m:
        return None
    minutes = int(m.group(1)) if m.group(1) else 0
    seconds = float(m.group(2))
    return minutes * 60 + seconds


def _format_wait(seconds):
    """Return a human-readable wait string, e.g. '6 min 18 s' or '45 s'."""
    if seconds is None:
        return 'a few minutes'
    m = int(seconds // 60)
    s = int(seconds % 60)
    if m:
        return f'{m} min {s} s'
    return f'{s} s'


def get_groq_client(api_key):
    """Create and return a Groq client."""
    return Groq(api_key=api_key)


# Auto-retry threshold: waits up to this many seconds are handled transparently.
_AUTO_RETRY_MAX_SECONDS = 65
_AUTO_RETRY_ATTEMPTS = 3


def call_groq(api_key, model, messages, temperature=0.7, top_p=0.9, max_tokens=4096):
    """
    Call the Groq API and return (content, tokens_used, elapsed_seconds).

    Rate-limit behaviour:
      - Wait ≤ 65 s  → sleep the exact amount and retry (up to 3 attempts).
      - Wait  > 65 s → raise GroqRateLimitError with the formatted wait time.
    Other API errors are re-raised as-is.
    """
    client = get_groq_client(api_key)

    for attempt in range(_AUTO_RETRY_ATTEMPTS):
        start = time.time()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=float(temperature),
                top_p=float(top_p),
                max_tokens=int(max_tokens),
            )
            elapsed = time.time() - start
            content = response.choices[0].message.content or ''
            tokens = response.usage.total_tokens if response.usage else 0
            return content, tokens, elapsed

        except RateLimitError as exc:
            retry_secs = _parse_retry_seconds(str(exc))

            if retry_secs is not None and retry_secs <= _AUTO_RETRY_MAX_SECONDS:
                # Short wait — sleep and retry transparently
                time.sleep(retry_secs + 2)   # +2 s buffer
                continue

            # Long wait — surface a friendly error to the caller
            wait_str = _format_wait(retry_secs)
            raise GroqRateLimitError(
                f'Groq daily token limit reached. Please try again in {wait_str}.',
                retry_after_seconds=retry_secs,
            ) from exc

    # Exhausted retries — raise a generic rate-limit error
    raise GroqRateLimitError(
        f'Groq rate limit persists after {_AUTO_RETRY_ATTEMPTS} retries. '
        'Wait a minute and resume generation.'
    )


def generate_titles(api_key, model, project_info, temperature=0.9, top_p=0.9, max_tokens=1024):
    """Generate 10 title and 10 subtitle suggestions."""
    system = (
        "You are a creative book title specialist. "
        "Generate compelling, marketable titles for the given book concept."
    )
    user = f"""Generate exactly 10 unique book titles AND 10 unique subtitles for this book.

Book Info:
Genre: {project_info.get('genre', '')}
Description: {project_info.get('description', '')}
Tone: {project_info.get('tone', '')}
Audience: {project_info.get('audience', '')}

Respond ONLY with valid JSON in this exact format:
{{
  "titles": ["Title 1", "Title 2", ..., "Title 10"],
  "subtitles": ["Subtitle 1", "Subtitle 2", ..., "Subtitle 10"]
}}"""
    messages = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': user}
    ]
    content, tokens, elapsed = call_groq(api_key, model, messages, temperature, top_p, max_tokens)
    # Extract JSON from response
    start = content.find('{')
    end = content.rfind('}') + 1
    if start >= 0 and end > start:
        data = json.loads(content[start:end])
    else:
        data = {'titles': [content.strip()], 'subtitles': []}
    return data, tokens, elapsed


def generate_outline(api_key, model, project, characters_ctx, world_ctx, template, temperature, top_p, max_tokens):
    """Generate a full book outline as a list of chapter dicts."""
    system = template.get('system_prompt', 'You are an expert novelist and story architect.')

    user = f"""Create a detailed outline for a {project['num_chapters']}-chapter book.

Book Details:
Title: {project['title']}
Subtitle: {project.get('subtitle', '')}
Genre: {project['genre']}
Story Type: {project['story_type']}
Audience: {project['audience']}
Description: {project['description']}
Writing Style: {project['writing_style']}
Point of View: {project['point_of_view']}
Tense: {project['tense']}
Tone: {project['tone']}
Target Words Per Chapter: {project['words_per_chapter']}

{characters_ctx}

{world_ctx}

Generate exactly {project['num_chapters']} chapters. Each chapter should have:
- A compelling chapter title
- A detailed 2-3 sentence summary of what happens
- Estimated word count (around {project['words_per_chapter']} words each)

Respond ONLY with valid JSON:
{{
  "chapters": [
    {{
      "chapter_number": 1,
      "chapter_title": "...",
      "summary": "...",
      "target_word_count": {project['words_per_chapter']}
    }},
    ...
  ]
}}"""
    messages = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': user}
    ]
    content, tokens, elapsed = call_groq(api_key, model, messages, temperature, top_p, max_tokens)
    start = content.find('{')
    end = content.rfind('}') + 1
    if start >= 0 and end > start:
        data = json.loads(content[start:end])
    else:
        data = {'chapters': []}
    return data.get('chapters', []), tokens, elapsed


def generate_chapter(api_key, model, project, outline_chapter, characters_ctx,
                     world_ctx, memory_ctx, template, temperature, top_p, max_tokens):
    """Generate the full text of a single chapter."""
    system = template.get('system_prompt', 'You are an expert novelist.')

    user = f"""Write Chapter {outline_chapter['chapter_number']}: "{outline_chapter['chapter_title']}"

Book Context:
Title: {project['title']}
Genre: {project['genre']}
Writing Style: {project['writing_style']}
Point of View: {project['point_of_view']}
Tense: {project['tense']}
Tone: {project['tone']}

Chapter Summary: {outline_chapter['summary']}
Target Length: approximately {outline_chapter.get('target_word_count', project['words_per_chapter'])} words

{characters_ctx}

{world_ctx}

{memory_ctx}

Instructions:
- Write ONLY the chapter content, starting with the chapter heading
- Target exactly {outline_chapter.get('target_word_count', project['words_per_chapter'])} words
- Maintain consistency with all previous chapters
- Use vivid, engaging prose appropriate for {project['genre']} fiction
- Do NOT include any author notes, metadata, or commentary
- Begin immediately with the chapter content"""

    messages = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': user}
    ]
    content, tokens, elapsed = call_groq(api_key, model, messages, temperature, top_p, max_tokens)
    return content, tokens, elapsed


def generate_chapter_memory(api_key, model, chapter_title, chapter_content, project_genre):
    """Generate memory/summary data for a chapter."""
    system = 'You are a story analyst. Extract key narrative information from the chapter.'
    user = f"""Analyze this chapter and extract key information.

Chapter: {chapter_title}
Genre: {project_genre}

Chapter Content:
{chapter_content[:6000]}

Respond ONLY with valid JSON:
{{
  "summary": "2-3 sentence summary of what happened",
  "important_events": "Key plot events (comma-separated)",
  "characters_introduced": "New characters introduced (comma-separated)",
  "character_changes": "Character development/changes (comma-separated)",
  "locations": "Locations visited (comma-separated)",
  "timeline_updates": "Timeline/time progression notes",
  "unresolved_plot_points": "Unresolved threads or cliffhangers (comma-separated)"
}}"""
    messages = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': user}
    ]
    content, tokens, elapsed = call_groq(api_key, model, messages, 0.3, 0.9, 1024)
    start = content.find('{')
    end = content.rfind('}') + 1
    if start >= 0 and end > start:
        data = json.loads(content[start:end])
    else:
        data = {'summary': chapter_content[:200]}
    return data, tokens, elapsed


def generate_matter(api_key, model, matter_type, project, characters_ctx, world_ctx, temperature=0.7):
    """Generate front or back matter content."""
    system = 'You are a professional book editor and author.'
    user = f"""Generate the {matter_type.replace('_', ' ').title()} for this book.

Book: {project['title']}
Author: [Author Name]
Genre: {project['genre']}
Description: {project['description']}

{characters_ctx}
{world_ctx}

Write professional, polished {matter_type.replace('_', ' ')} content suitable for publication.
Be thorough and authentic. Output only the content itself, no extra commentary."""

    messages = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': user}
    ]
    content, tokens, elapsed = call_groq(api_key, model, messages, temperature, 0.9, 2048)
    return content, tokens, elapsed


def generate_book_premise(api_key, model, project_info, temperature=0.85):
    """Generate subtitle and book description/premise from basic book details."""
    system = (
        "You are a creative book editor and marketing specialist. "
        "Generate compelling subtitles and vivid book descriptions that hook readers."
    )
    user = f"""Generate a subtitle and a book description/premise for this book concept.

Book Details:
Title: {project_info.get('title', '')}
Genre: {project_info.get('genre', 'Fantasy')}
Story Type: {project_info.get('story_type', 'Novel')}
Tone: {project_info.get('tone', 'Adventurous')}
Audience: {project_info.get('audience', 'Adult')}
Writing Style: {project_info.get('writing_style', 'Descriptive')}
Existing Description (if any): {project_info.get('description', '')}

Respond ONLY with valid JSON:
{{
  "subtitle": "A compelling subtitle (max 10 words)",
  "description": "A gripping 3-4 sentence book premise that hooks the reader, reveals the central conflict, and teases the stakes. Written in present tense marketing style."
}}"""
    messages = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': user}
    ]
    content, tokens, elapsed = call_groq(api_key, model, messages, temperature, 0.9, 512)
    start = content.find('{')
    end = content.rfind('}') + 1
    if start >= 0 and end > start:
        data = json.loads(content[start:end])
    else:
        data = {'subtitle': '', 'description': content.strip()}
    return data, tokens, elapsed


def generate_cover_prompt(api_key, model, project):
    """Generate a detailed AI image prompt for the book cover."""
    system = 'You are an expert AI art prompt engineer specializing in book covers.'
    user = f"""Create a detailed, professional AI image generation prompt for this book cover.

Title: {project['title']}
Genre: {project['genre']}
Description: {project['description']}
Tone: {project['tone']}

Generate a single, detailed prompt (150-200 words) that would produce a stunning book cover.
Include: art style, mood, color palette, composition, key visual elements, lighting, and technical quality descriptors.
Output ONLY the prompt text."""

    messages = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': user}
    ]
    content, tokens, elapsed = call_groq(api_key, model, messages, 0.8, 0.9, 512)
    return content.strip(), tokens, elapsed


def generate_image_prompt(api_key, model, chapter_title, chapter_summary, style, genre):
    """Generate an image prompt for a chapter illustration."""
    system = 'You are an expert AI art prompt engineer.'
    user = f"""Create a detailed image generation prompt for a chapter illustration.

Chapter: {chapter_title}
Summary: {chapter_summary}
Style: {style}
Genre: {genre}

Generate a vivid, detailed prompt (80-120 words) in {style} art style.
Include: scene description, mood, lighting, colors, composition. Output ONLY the prompt."""

    messages = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': user}
    ]
    content, tokens, elapsed = call_groq(api_key, model, messages, 0.8, 0.9, 256)
    return content.strip(), tokens, elapsed
