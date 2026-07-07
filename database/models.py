"""Database schema creation and seeding."""
import sqlite3
import os
from werkzeug.security import generate_password_hash


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    subtitle TEXT DEFAULT '',
    genre TEXT DEFAULT 'Fantasy',
    audience TEXT DEFAULT 'Adult',
    description TEXT DEFAULT '',
    language TEXT DEFAULT 'English',
    story_type TEXT DEFAULT 'Novel',
    writing_style TEXT DEFAULT 'Descriptive',
    point_of_view TEXT DEFAULT 'Third Person Limited',
    tense TEXT DEFAULT 'Past',
    tone TEXT DEFAULT 'Adventurous',
    num_chapters INTEGER DEFAULT 10,
    words_per_chapter INTEGER DEFAULT 2000,
    creativity_level TEXT DEFAULT 'balanced',
    temperature REAL DEFAULT 0.7,
    top_p REAL DEFAULT 0.9,
    max_tokens INTEGER DEFAULT 4096,
    status TEXT DEFAULT 'draft',
    current_chapter INTEGER DEFAULT 0,
    total_words INTEGER DEFAULT 0,
    cover_prompt TEXT DEFAULT '',
    include_images INTEGER DEFAULT 0,
    images_per_chapter INTEGER DEFAULT 1,
    image_style TEXT DEFAULT 'Realistic',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS outline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    chapter_number INTEGER NOT NULL,
    chapter_title TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    target_word_count INTEGER DEFAULT 2000,
    order_index INTEGER DEFAULT 0,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    chapter_number INTEGER NOT NULL,
    chapter_title TEXT DEFAULT '',
    content TEXT DEFAULT '',
    word_count INTEGER DEFAULT 0,
    summary TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    important_events TEXT DEFAULT '',
    characters_introduced TEXT DEFAULT '',
    character_changes TEXT DEFAULT '',
    locations TEXT DEFAULT '',
    timeline_updates TEXT DEFAULT '',
    unresolved_plot_points TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    nickname TEXT DEFAULT '',
    age TEXT DEFAULT '',
    gender TEXT DEFAULT '',
    occupation TEXT DEFAULT '',
    personality TEXT DEFAULT '',
    appearance TEXT DEFAULT '',
    strengths TEXT DEFAULT '',
    weaknesses TEXT DEFAULT '',
    goals TEXT DEFAULT '',
    relationships TEXT DEFAULT '',
    backstory TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS worldbuilding (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    details TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS front_matter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    content TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS back_matter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    content TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prompt_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    genre TEXT NOT NULL,
    name TEXT NOT NULL,
    system_prompt TEXT DEFAULT '',
    writing_style TEXT DEFAULT '',
    tone TEXT DEFAULT '',
    genre_instructions TEXT DEFAULT '',
    is_default INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS generation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    chapter_id INTEGER,
    log_type TEXT DEFAULT 'chapter',
    prompt TEXT DEFAULT '',
    response TEXT DEFAULT '',
    tokens_used INTEGER DEFAULT 0,
    generation_time REAL DEFAULT 0,
    status TEXT DEFAULT 'success',
    error_message TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    action TEXT DEFAULT '',
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    chapter_id INTEGER,
    prompt TEXT DEFAULT '',
    style TEXT DEFAULT 'Realistic',
    filename TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    books_generated INTEGER DEFAULT 0,
    words_generated INTEGER DEFAULT 0,
    api_requests INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    avg_generation_time REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS content_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    chapter_id INTEGER,
    content_type TEXT DEFAULT 'chapter',
    report_reason TEXT NOT NULL,
    report_details TEXT DEFAULT '',
    reporter_info TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    admin_notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);
"""

DEFAULT_SETTINGS = [
    ('admin_password', generate_password_hash('admin123')),
    ('groq_api_key', ''),
    ('groq_model', 'llama-3.3-70b-versatile'),
    ('groq_temperature', '0.7'),
    ('groq_top_p', '0.9'),
    ('groq_max_tokens', '4096'),
    ('app_name', 'KDP Novel & Storybook Creator'),
    ('app_logo', ''),
    ('app_footer', '© 2024 KDP Novel & Storybook Creator. All rights reserved.'),
    ('default_theme', 'dark'),
    ('default_font', 'Georgia'),
    ('maintenance_mode', '0'),
    ('export_include_toc', '1'),
    ('export_include_page_numbers', '1'),
    ('export_include_headers', '1'),
    ('export_include_footers', '1'),
]

DEFAULT_PROMPT_TEMPLATES = [
    ('Fantasy', 'Epic Fantasy', 
     'You are a master fantasy novelist with decades of experience crafting immersive worlds.',
     'Descriptive, vivid, immersive',
     'Epic, adventurous, wonder-filled',
     'Include magic systems, mythical creatures, and epic quests. Focus on world-building and character growth.'),
    ('Sci-Fi', 'Science Fiction',
     'You are an acclaimed science fiction author known for hard sci-fi and speculative fiction.',
     'Technical, detailed, thought-provoking',
     'Intellectual, tense, futuristic',
     'Include technology, space exploration, AI, and societal implications. Ground speculation in plausible science.'),
    ('Romance', 'Contemporary Romance',
     'You are a bestselling romance novelist with a talent for emotional depth and chemistry.',
     'Emotional, sensual, character-driven',
     'Warm, passionate, hopeful',
     'Focus on emotional tension, character chemistry, and satisfying relationship arcs. Include dialogue-heavy scenes.'),
    ('Mystery', 'Detective Mystery',
     'You are a master of the mystery genre, known for intricate plots and clever reveals.',
     'Atmospheric, suspenseful, precise',
     'Tense, mysterious, intelligent',
     'Plant clues carefully, maintain red herrings, and build to a satisfying revelation. Every detail matters.'),
    ('Adventure', 'Action Adventure',
     'You are an exciting adventure novelist who writes pulse-pounding action sequences.',
     'Fast-paced, visceral, exciting',
     'Thrilling, energetic, bold',
     'Keep action moving, use short punchy sentences during action sequences, and create memorable set-pieces.'),
    ('Thriller', 'Psychological Thriller',
     'You are a psychological thriller author known for mind-bending plots and unreliable narrators.',
     'Tense, psychological, layered',
     'Dark, suspenseful, unnerving',
     'Build psychological tension, challenge reader assumptions, and create a sense of mounting dread.'),
    ('Children', "Children's Book",
     'You are a beloved children\'s book author who writes age-appropriate, educational stories.',
     'Simple, clear, engaging',
     'Playful, warm, encouraging',
     'Use simple vocabulary, clear moral lessons, and engaging characters. Keep sentences short and punchy.'),
    ('Comedy', 'Comedic Fiction',
     'You are a comedy writer known for wit, timing, and laugh-out-loud situations.',
     'Witty, punchy, observational',
     'Humorous, light, entertaining',
     'Use comic timing, absurdist scenarios, witty dialogue. Set up and payoff jokes throughout the narrative.'),
    ('Historical', 'Historical Fiction',
     'You are a meticulous historical novelist who brings the past to life with accuracy.',
     'Period-accurate, detailed, atmospheric',
     'Authentic, immersive, dramatic',
     'Research period details, use authentic dialogue, and weave historical events into personal narrative.'),
    ('Business', 'Business Non-Fiction',
     'You are a business author and thought leader known for actionable insights.',
     'Clear, authoritative, practical',
     'Professional, engaging, motivational',
     'Use real examples, practical advice, and clear frameworks. Balance storytelling with actionable takeaways.'),
    ('Educational', 'Educational Non-Fiction',
     'You are an educator and author who makes complex topics accessible and engaging.',
     'Clear, structured, informative',
     'Educational, engaging, accessible',
     'Break down complex concepts, use analogies, examples, and maintain an engaging teaching voice.'),
    ('Horror', 'Horror Fiction',
     'You are a master of horror fiction who crafts truly terrifying and psychologically disturbing stories.',
     'Atmospheric, dread-filled, visceral',
     'Dark, terrifying, unsettling',
     'Build atmosphere of dread, use psychological horror as well as visceral scares. Subvert expectations.'),
]


def init_db(db_path):
    """Initialize the database schema and seed default data."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    # Seed default settings: insert missing rows, and fill in any empty values
    for key, value in DEFAULT_SETTINGS:
        conn.execute(
            'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
            (key, value)
        )
        conn.execute(
            "UPDATE settings SET value=? WHERE key=? AND (value IS NULL OR value='')",
            (value, key)
        )

    # Seed default prompt templates
    existing = conn.execute('SELECT COUNT(*) FROM prompt_templates').fetchone()[0]
    if existing == 0:
        conn.executemany(
            '''INSERT INTO prompt_templates
               (genre, name, system_prompt, writing_style, tone, genre_instructions, is_default)
               VALUES (?, ?, ?, ?, ?, ?, 1)''',
            DEFAULT_PROMPT_TEMPLATES
        )

    conn.commit()
    conn.close()
