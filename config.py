"""Application configuration."""
import os


class Config:
    SECRET_KEY = os.environ.get('SESSION_SECRET', 'ai-novel-creator-secret-key-change-me')
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
