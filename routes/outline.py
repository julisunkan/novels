"""Outline generation and management routes."""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from database import get_db
from utils.helpers import get_setting, log_history
from services.groq_service import generate_outline
from services.memory_service import build_full_prompt_context

bp = Blueprint('outline', __name__)


@bp.route('/project/<int:project_id>/outline')
def outline_page(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        return redirect(url_for('main.history'))
    chapters = db.execute(
        'SELECT * FROM outline WHERE project_id = ? ORDER BY order_index, chapter_number',
        (project_id,)
    ).fetchall()
    groq_configured = bool(get_setting(db, 'groq_api_key'))
    return render_template('outline.html', project=project, chapters=chapters,
                           groq_configured=groq_configured)


@bp.route('/project/<int:project_id>/outline/generate', methods=['POST'])
def generate_outline_ajax(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    api_key = get_setting(db, 'groq_api_key')
    if not api_key:
        return jsonify({'error': 'Groq API key not configured. Visit /julisunkan to set it up.'}), 400
    model = get_setting(db, 'groq_model', 'llama-3.3-70b-versatile')

    # Get genre template
    template = db.execute(
        'SELECT * FROM prompt_templates WHERE genre = ? LIMIT 1',
        (project['genre'],)
    ).fetchone()
    if not template:
        template = db.execute('SELECT * FROM prompt_templates LIMIT 1').fetchone()
    template_dict = dict(template) if template else {}

    chars_ctx, world_ctx, _ = build_full_prompt_context(db, project_id)

    try:
        chapters_data, tokens, elapsed = generate_outline(
            api_key, model, dict(project), chars_ctx, world_ctx, template_dict,
            project['temperature'], project['top_p'], project['max_tokens']
        )
        # Clear existing outline
        db.execute('DELETE FROM outline WHERE project_id = ?', (project_id,))
        for i, ch in enumerate(chapters_data):
            db.execute(
                'INSERT INTO outline (project_id, chapter_number, chapter_title, summary, target_word_count, order_index) VALUES (?,?,?,?,?,?)',
                (project_id, ch.get('chapter_number', i+1), ch.get('chapter_title', f'Chapter {i+1}'),
                 ch.get('summary', ''), ch.get('target_word_count', project['words_per_chapter']), i)
            )
        db.commit()
        log_history(db, project_id, 'outline_generated', f'Generated {len(chapters_data)}-chapter outline')

        # Log
        db.execute(
            'INSERT INTO generation_logs (project_id, log_type, tokens_used, generation_time, status) VALUES (?,?,?,?,?)',
            (project_id, 'outline', tokens, elapsed, 'success')
        )
        db.commit()

        outline = db.execute(
            'SELECT * FROM outline WHERE project_id = ? ORDER BY order_index', (project_id,)
        ).fetchall()
        return jsonify({'success': True, 'count': len(chapters_data), 'chapters': [dict(c) for c in outline]})
    except Exception as e:
        db.execute(
            'INSERT INTO generation_logs (project_id, log_type, status, error_message) VALUES (?,?,?,?)',
            (project_id, 'outline', 'error', str(e))
        )
        db.commit()
        return jsonify({'error': str(e)}), 500


@bp.route('/project/<int:project_id>/outline/chapter/add', methods=['POST'])
def add_chapter(project_id):
    db = get_db()
    data = request.get_json() if request.is_json else request.form
    max_order = db.execute(
        'SELECT COALESCE(MAX(order_index),0) FROM outline WHERE project_id = ?', (project_id,)
    ).fetchone()[0]
    max_num = db.execute(
        'SELECT COALESCE(MAX(chapter_number),0) FROM outline WHERE project_id = ?', (project_id,)
    ).fetchone()[0]
    chapter_id = db.execute(
        'INSERT INTO outline (project_id, chapter_number, chapter_title, summary, target_word_count, order_index) VALUES (?,?,?,?,?,?)',
        (project_id, max_num + 1, data.get('chapter_title', f'Chapter {max_num+1}'),
         data.get('summary', ''), int(data.get('target_word_count', 2000)), max_order + 1)
    ).lastrowid
    db.commit()
    row = db.execute('SELECT * FROM outline WHERE id = ?', (chapter_id,)).fetchone()
    return jsonify({'success': True, 'chapter': dict(row)})


@bp.route('/project/<int:project_id>/outline/chapter/<int:chapter_id>/edit', methods=['POST'])
def edit_chapter(project_id, chapter_id):
    db = get_db()
    data = request.get_json() if request.is_json else request.form
    db.execute(
        'UPDATE outline SET chapter_title=?, summary=?, target_word_count=? WHERE id=? AND project_id=?',
        (data.get('chapter_title', ''), data.get('summary', ''),
         int(data.get('target_word_count', 2000)), chapter_id, project_id)
    )
    db.commit()
    return jsonify({'success': True})


@bp.route('/project/<int:project_id>/outline/chapter/<int:chapter_id>/delete', methods=['POST'])
def delete_chapter(project_id, chapter_id):
    db = get_db()
    db.execute('DELETE FROM outline WHERE id=? AND project_id=?', (chapter_id, project_id))
    db.commit()
    # Renumber
    chapters = db.execute(
        'SELECT id FROM outline WHERE project_id=? ORDER BY order_index, chapter_number', (project_id,)
    ).fetchall()
    for i, ch in enumerate(chapters):
        db.execute('UPDATE outline SET chapter_number=?, order_index=? WHERE id=?', (i+1, i, ch['id']))
    db.commit()
    return jsonify({'success': True})


@bp.route('/project/<int:project_id>/outline/chapter/<int:chapter_id>/duplicate', methods=['POST'])
def duplicate_chapter(project_id, chapter_id):
    db = get_db()
    ch = db.execute('SELECT * FROM outline WHERE id=? AND project_id=?', (chapter_id, project_id)).fetchone()
    if not ch:
        return jsonify({'error': 'Not found'}), 404
    new_id = db.execute(
        'INSERT INTO outline (project_id, chapter_number, chapter_title, summary, target_word_count, order_index) VALUES (?,?,?,?,?,?)',
        (project_id, ch['chapter_number'] + 100, f"{ch['chapter_title']} (Copy)",
         ch['summary'], ch['target_word_count'], ch['order_index'] + 1)
    ).lastrowid
    db.commit()
    # Renumber
    chapters = db.execute(
        'SELECT id FROM outline WHERE project_id=? ORDER BY order_index, chapter_number', (project_id,)
    ).fetchall()
    for i, c in enumerate(chapters):
        db.execute('UPDATE outline SET chapter_number=?, order_index=? WHERE id=?', (i+1, i, c['id']))
    db.commit()
    row = db.execute('SELECT * FROM outline WHERE id=?', (new_id,)).fetchone()
    return jsonify({'success': True, 'chapter': dict(row)})


@bp.route('/project/<int:project_id>/outline/reorder', methods=['POST'])
def reorder_chapters(project_id):
    db = get_db()
    data = request.get_json(silent=True)
    if not data or 'order' not in data:
        return jsonify({'error': 'Missing order list'}), 400
    order = data['order']
    for i, chapter_id in enumerate(order):
        db.execute(
            'UPDATE outline SET chapter_number=?, order_index=? WHERE id=? AND project_id=?',
            (i + 1, i, chapter_id, project_id)
        )
    db.commit()
    return jsonify({'success': True})
