"""Manuscript editor routes."""
import re
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from database import get_db
from utils.helpers import count_words, update_project_stats

bp = Blueprint('editor', __name__)


@bp.route('/project/<int:project_id>/editor')
def editor_page(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        return redirect(url_for('main.history'))
    chapters = db.execute(
        'SELECT * FROM chapters WHERE project_id = ? ORDER BY chapter_number', (project_id,)
    ).fetchall()
    total_words = sum(c['word_count'] for c in chapters)
    target_words = project['num_chapters'] * project['words_per_chapter']
    return render_template('editor.html', project=project, chapters=chapters,
                           total_words=total_words, target_words=target_words)


@bp.route('/project/<int:project_id>/editor/chapter/<int:chapter_id>/save', methods=['POST'])
def save_chapter_content(project_id, chapter_id):
    db = get_db()
    data = request.get_json() or request.form
    content = data.get('content', '')
    wc = count_words(content)
    db.execute(
        'UPDATE chapters SET content=?, word_count=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND project_id=?',
        (content, wc, chapter_id, project_id)
    )
    db.commit()
    update_project_stats(db, project_id)
    return jsonify({'success': True, 'word_count': wc})


@bp.route('/project/<int:project_id>/search-replace', methods=['POST'])
def search_replace(project_id):
    db = get_db()
    data = request.get_json() or request.form
    find = data.get('find', '')
    replace = data.get('replace', '')
    match_case = data.get('match_case', False)
    whole_word = data.get('whole_word', False)
    replace_all = data.get('replace_all', False)

    if not find:
        return jsonify({'error': 'Search term required'}), 400

    chapters = db.execute(
        'SELECT * FROM chapters WHERE project_id = ? AND content IS NOT NULL', (project_id,)
    ).fetchall()

    flags = 0 if match_case else re.IGNORECASE
    if whole_word:
        pattern = r'\b' + re.escape(find) + r'\b'
    else:
        pattern = re.escape(find)

    total_replaced = 0
    for ch in chapters:
        content = ch['content'] or ''
        if replace_all:
            new_content, n = re.subn(pattern, replace, content, flags=flags)
        else:
            new_content, n = re.subn(pattern, replace, content, count=1, flags=flags)
        if n > 0:
            wc = count_words(new_content)
            db.execute(
                'UPDATE chapters SET content=?, word_count=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                (new_content, wc, ch['id'])
            )
            total_replaced += n
        if not replace_all and total_replaced > 0:
            break

    if total_replaced > 0:
        db.commit()
        update_project_stats(db, project_id)

    return jsonify({'success': True, 'replaced': total_replaced})
