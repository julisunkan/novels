"""Front matter and back matter routes."""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from database import get_db
from utils.helpers import get_setting
from services.groq_service import generate_matter
from services.memory_service import build_full_prompt_context

bp = Blueprint('matter', __name__)

FRONT_MATTER_TYPES = [
    ('title_page', 'Title Page'),
    ('copyright', 'Copyright Page'),
    ('dedication', 'Dedication'),
    ('foreword', 'Foreword'),
    ('preface', 'Preface'),
    ('acknowledgements', 'Acknowledgements'),
    ('introduction', 'Introduction'),
    ('toc', 'Table of Contents'),
]

BACK_MATTER_TYPES = [
    ('conclusion', 'Conclusion'),
    ('epilogue', 'Epilogue'),
    ('afterword', 'Afterword'),
    ('about_author', 'About the Author'),
    ('glossary', 'Glossary'),
    ('appendix', 'Appendix'),
    ('references', 'References'),
]


@bp.route('/project/<int:project_id>/matter')
def matter_page(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        return redirect(url_for('main.history'))
    front = {}
    for row in db.execute('SELECT type, content FROM front_matter WHERE project_id=?', (project_id,)).fetchall():
        front[row['type']] = row['content']
    back = {}
    for row in db.execute('SELECT type, content FROM back_matter WHERE project_id=?', (project_id,)).fetchall():
        back[row['type']] = row['content']
    groq_configured = bool(get_setting(db, 'groq_api_key'))
    return render_template('matter.html', project=project,
                           front=front, back=back,
                           front_types=FRONT_MATTER_TYPES,
                           back_types=BACK_MATTER_TYPES,
                           groq_configured=groq_configured)


@bp.route('/project/<int:project_id>/matter/generate', methods=['POST'])
def generate_matter_ajax(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    api_key = get_setting(db, 'groq_api_key')
    if not api_key:
        return jsonify({'error': 'Groq API key not configured.'}), 400

    data = request.get_json() if request.is_json else request.form
    matter_type = data.get('type', '')
    table = 'front_matter' if matter_type in [t[0] for t in FRONT_MATTER_TYPES] else 'back_matter'

    model = get_setting(db, 'groq_model', 'llama3-70b-8192')
    chars_ctx, world_ctx, _ = build_full_prompt_context(db, project_id)
    try:
        content, tokens, elapsed = generate_matter(
            api_key, model, matter_type, dict(project), chars_ctx, world_ctx
        )
        existing = db.execute(
            f'SELECT id FROM {table} WHERE project_id=? AND type=?', (project_id, matter_type)
        ).fetchone()
        if existing:
            db.execute(f'UPDATE {table} SET content=? WHERE id=?', (content, existing['id']))
        else:
            db.execute(f'INSERT INTO {table} (project_id, type, content) VALUES (?,?,?)',
                       (project_id, matter_type, content))
        db.commit()
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/project/<int:project_id>/matter/save', methods=['POST'])
def save_matter(project_id):
    db = get_db()
    data = request.get_json() if request.is_json else request.form
    matter_type = data.get('type', '')
    content = data.get('content', '')
    table = 'front_matter' if matter_type in [t[0] for t in FRONT_MATTER_TYPES] else 'back_matter'
    existing = db.execute(
        f'SELECT id FROM {table} WHERE project_id=? AND type=?', (project_id, matter_type)
    ).fetchone()
    if existing:
        db.execute(f'UPDATE {table} SET content=? WHERE id=?', (content, existing['id']))
    else:
        db.execute(f'INSERT INTO {table} (project_id, type, content) VALUES (?,?,?)',
                   (project_id, matter_type, content))
    db.commit()
    return jsonify({'success': True})
