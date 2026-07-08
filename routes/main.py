"""Main routes: home, project history, search & replace."""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, send_from_directory, make_response, current_app
from database import get_db
from utils.helpers import get_setting, count_words

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    db = get_db()
    projects = db.execute(
        'SELECT * FROM projects ORDER BY updated_at DESC LIMIT 6'
    ).fetchall()
    stats = {
        'total_projects': db.execute('SELECT COUNT(*) FROM projects').fetchone()[0],
        'total_words': db.execute('SELECT COALESCE(SUM(total_words),0) FROM projects').fetchone()[0],
        'completed': db.execute("SELECT COUNT(*) FROM projects WHERE status='completed'").fetchone()[0],
        'in_progress': db.execute("SELECT COUNT(*) FROM projects WHERE status IN ('in_progress','paused')").fetchone()[0],
    }
    app_name = get_setting(db, 'app_name', 'KDP Novel & Storybook Creator')
    maintenance = get_setting(db, 'maintenance_mode', '0') == '1'
    return render_template('index.html',
                           projects=projects,
                           stats=stats,
                           app_name=app_name,
                           maintenance=maintenance)


@bp.route('/history')
def history():
    db = get_db()
    projects = db.execute('SELECT * FROM projects ORDER BY updated_at DESC').fetchall()
    return render_template('history.html', projects=projects)


@bp.route('/api/generate-titles-preview', methods=['POST'])
def generate_titles_preview():
    """Generate title suggestions without a saved project (for new project form)."""
    db = get_db()
    from services import ai_service
    cfg = ai_service.get_active_config(db)
    if not cfg['api_key']:
        return jsonify({'error': 'AI API key not configured. Visit /julisunkan to set it up.'}), 400
    data = request.get_json(silent=True) or {}  # optional body, no required fields
    try:
        result, tokens, elapsed = ai_service.generate_titles(cfg['api_key'], cfg['model'], data, temperature=0.9, provider=cfg['provider'])
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/sw.js')
def service_worker():
    """Serve the service worker from root scope so it controls all app pages."""
    resp = make_response(send_from_directory('static', 'sw.js'))
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Content-Type'] = 'application/javascript'
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp


@bp.route('/api/generate-premise-preview', methods=['POST'])
def generate_premise_preview():
    """Generate subtitle and description for a new/existing project (no saved project needed)."""
    db = get_db()
    from services import ai_service
    cfg = ai_service.get_active_config(db)
    if not cfg['api_key']:
        return jsonify({'error': 'AI API key not configured. Visit /julisunkan to set it up.'}), 400
    data = request.get_json(silent=True) or {}
    try:
        result, tokens, elapsed = ai_service.generate_book_premise(cfg['api_key'], cfg['model'], data, provider=cfg['provider'])
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/search', methods=['GET'])
def search_page():
    """Global search across all projects."""
    q = request.args.get('q', '').strip()
    results = []
    if q:
        db = get_db()
        results = db.execute(
            '''SELECT c.id, c.chapter_number, c.chapter_title, c.project_id,
                      p.title as project_title
               FROM chapters c JOIN projects p ON c.project_id = p.id
               WHERE c.content LIKE ?
               ORDER BY p.updated_at DESC LIMIT 50''',
            (f'%{q}%',)
        ).fetchall()
    return render_template('search.html', query=q, results=results)
