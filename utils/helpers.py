"""Shared helper utilities."""
import re
import os
import json
from datetime import datetime
from functools import wraps
from flask import session, redirect, url_for, flash, current_app


def admin_required(f):
    """Decorator: require admin session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated


def count_words(text):
    """Count words in a string."""
    if not text:
        return 0
    return len(re.findall(r'\b\w+\b', text))


def get_setting(db, key, default=''):
    """Fetch a single setting value from the DB."""
    row = db.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else default


def set_setting(db, key, value):
    """Upsert a setting value."""
    db.execute(
        'INSERT INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) '
        'ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP',
        (key, value)
    )
    db.commit()


def get_project_or_404(db, project_id):
    """Fetch a project by id or return None."""
    return db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()


def update_project_stats(db, project_id):
    """Recalculate and update project total_words and current_chapter."""
    result = db.execute(
        '''SELECT COALESCE(SUM(word_count), 0) as total,
                  COUNT(CASE WHEN status = "generated" THEN 1 END) as done
           FROM chapters WHERE project_id = ?''',
        (project_id,)
    ).fetchone()
    db.execute(
        'UPDATE projects SET total_words = ?, current_chapter = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (result['total'], result['done'], project_id)
    )
    db.commit()


def log_history(db, project_id, action, description=''):
    """Add a project history entry."""
    db.execute(
        'INSERT INTO project_history (project_id, action, description) VALUES (?, ?, ?)',
        (project_id, action, description)
    )
    db.commit()


def increment_statistic(db, field, amount=1):
    """Increment a daily statistic field."""
    today = datetime.utcnow().strftime('%Y-%m-%d')
    db.execute(
        f'INSERT INTO statistics (date, {field}) VALUES (?, ?) '
        f'ON CONFLICT(date) DO UPDATE SET {field} = {field} + ?',
        (today, amount, amount)
    )
    db.commit()


def build_character_context(db, project_id):
    """Build a character summary string for prompts."""
    chars = db.execute('SELECT * FROM characters WHERE project_id = ?', (project_id,)).fetchall()
    if not chars:
        return ''
    lines = ['CHARACTERS:']
    for c in chars:
        parts = [f"- {c['name']}"]
        if c['age']:
            parts.append(f"(Age: {c['age']})")
        if c['occupation']:
            parts.append(f"- {c['occupation']}")
        if c['personality']:
            parts.append(f"Personality: {c['personality']}")
        if c['goals']:
            parts.append(f"Goals: {c['goals']}")
        lines.append(' '.join(parts))
    return '\n'.join(lines)


def build_world_context(db, project_id):
    """Build a worldbuilding summary string for prompts."""
    entries = db.execute('SELECT * FROM worldbuilding WHERE project_id = ?', (project_id,)).fetchall()
    if not entries:
        return ''
    categories = {}
    for e in entries:
        cat = e['category'].replace('_', ' ').title()
        categories.setdefault(cat, []).append(f"  - {e['name']}: {e['description']}")
    lines = ['WORLD BUILDING:']
    for cat, items in categories.items():
        lines.append(f"{cat}:")
        lines.extend(items)
    return '\n'.join(lines)


def build_memory_context(db, project_id, up_to_chapter=None):
    """Build accumulated memory context from all generated chapters."""
    query = '''SELECT chapter_number, chapter_title, summary, important_events,
                      characters_introduced, character_changes, locations,
                      timeline_updates, unresolved_plot_points
               FROM chapters WHERE project_id = ? AND status = "generated"'''
    params = [project_id]
    if up_to_chapter:
        query += ' AND chapter_number < ?'
        params.append(up_to_chapter)
    query += ' ORDER BY chapter_number ASC'
    chapters = db.execute(query, params).fetchall()
    if not chapters:
        return ''
    lines = ['STORY MEMORY (Previous Chapters):']
    for ch in chapters:
        lines.append(f"\nChapter {ch['chapter_number']}: {ch['chapter_title']}")
        if ch['summary']:
            lines.append(f"  Summary: {ch['summary']}")
        if ch['important_events']:
            lines.append(f"  Events: {ch['important_events']}")
        if ch['locations']:
            lines.append(f"  Locations: {ch['locations']}")
        if ch['unresolved_plot_points']:
            lines.append(f"  Unresolved: {ch['unresolved_plot_points']}")
    return '\n'.join(lines)


def safe_filename(name):
    """Make a string safe for use as a filename."""
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[\s-]+', '_', name)
    return name[:100]
