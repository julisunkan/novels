"""Application configuration."""
import os
import warnings

_FALLBACK_SECRET = 'ai-novel-creator-secret-key-change-me'


class Config:
    _raw_secret = os.environ.get('SESSION_SECRET', _FALLBACK_SECRET)
    if _raw_secret == _FALLBACK_SECRET:
        warnings.warn(
            "SESSION_SECRET is not set — using an insecure fallback key. "
            "Set the SESSION_SECRET environment variable before deploying.",
            stacklevel=2,
        )
    SECRET_KEY = _raw_secret
    DATABASE = os.path.join(os.path.dirname(__file__), 'database', 'novel_creator.db')
    EXPORTS_DIR = os.path.join(os.path.dirname(__file__), 'exports')
    UPLOADS_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload

    # Groq defaults (overridden by DB settings)
    GROQ_MODEL = 'llama-3.3-70b-versatile'
    GROQ_TEMPERATURE = 0.7
    GROQ_TOP_P = 0.9
    GROQ_MAX_TOKENS = 4096

    # Admin
    ADMIN_PASSWORD_DEFAULT = 'admin123'

    # App info
    APP_NAME = 'KDP Novel & Storybook Creator'
    APP_VERSION = '1.0.0'
