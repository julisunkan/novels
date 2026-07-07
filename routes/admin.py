"""Admin panel routes — protected by session auth at /julisunkan."""
import os
import shutil
import sqlite3
from datetime import datetime
from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, jsonify, flash, send_file, current_app)
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db
from utils.helpers import admin_required, get_setting, set_setting

bp = Blueprint('admin', __name__, url_prefix='/julisunkan')


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin.dashboard'))
    error = None
    if request.method == 'POST':
        db = get_db()
        stored_hash = get_setting(db, 'admin_password', '')
        entered = request.form.get('password', '')
        if stored_hash and check_password_hash(stored_hash, entered):
            session['admin_logged_in'] = True
            session.permanent = True
            return redirect(url_for('admin.dashboard'))
        error = 'Invalid password.'
    return render_template('admin/login.html', error=error)


@bp.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin.login'))


@bp.route('/dashboard')
@admin_required
def dashboard():
    db = get_db()
    stats = {
        'total_projects': db.execute('SELECT COUNT(*) FROM projects').fetchone()[0],
        'completed': db.execute("SELECT COUNT(*) FROM projects WHERE status='completed'").fetchone()[0],
        'total_words': db.execute('SELECT COALESCE(SUM(total_words),0) FROM projects').fetchone()[0],
        'total_chapters': db.execute("SELECT COUNT(*) FROM chapters WHERE status='generated'").fetchone()[0],
        'total_api_calls': db.execute('SELECT COALESCE(SUM(api_requests),0) FROM statistics').fetchone()[0],
        'total_tokens': db.execute('SELECT COALESCE(SUM(tokens_used),0) FROM statistics').fetchone()[0],
        'total_books': db.execute('SELECT COALESCE(SUM(books_generated),0) FROM statistics').fetchone()[0],
        'total_log_errors': db.execute("SELECT COUNT(*) FROM generation_logs WHERE status='error'").fetchone()[0],
    }
    recent_projects = db.execute(
        'SELECT * FROM projects ORDER BY updated_at DESC LIMIT 10'
    ).fetchall()
    recent_logs = db.execute(
        '''SELECT gl.*, p.title as project_title FROM generation_logs gl
           LEFT JOIN projects p ON gl.project_id = p.id
           ORDER BY gl.id DESC LIMIT 20'''
    ).fetchall()
    daily_stats = db.execute(
        'SELECT * FROM statistics ORDER BY date DESC LIMIT 30'
    ).fetchall()
    return render_template('admin/dashboard.html', stats=stats,
                           recent_projects=recent_projects,
                           recent_logs=recent_logs, daily_stats=daily_stats)


@bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action', 'save')
        if action == 'change_password':
            new_pw = request.form.get('new_password', '')
            if len(new_pw) >= 6:
                set_setting(db, 'admin_password', generate_password_hash(new_pw))
                flash('Password updated successfully.', 'success')
            else:
                flash('Password must be at least 6 characters.', 'error')
        else:
            fields = ['groq_api_key', 'groq_model', 'groq_temperature', 'groq_top_p',
                      'groq_max_tokens', 'app_name', 'app_footer', 'default_theme',
                      'default_font', 'maintenance_mode', 'export_include_toc',
                      'export_include_page_numbers', 'export_include_headers',
                      'export_include_footers']
            for field in fields:
                val = request.form.get(field, '')
                set_setting(db, field, val)
            flash('Settings saved successfully.', 'success')
        return redirect(url_for('admin.settings'))

    current_settings = {}
    rows = db.execute('SELECT key, value FROM settings').fetchall()
    for row in rows:
        current_settings[row['key']] = row['value']

    groq_models = [
        ('llama-3.3-70b-versatile', 'LLaMA 3.3 70B Versatile (Recommended)'),
        ('llama-3.1-70b-versatile', 'LLaMA 3.1 70B Versatile'),
        ('llama-3.1-8b-instant', 'LLaMA 3.1 8B Instant (Fast)'),
        ('llama3-groq-70b-8192-tool-use-preview', 'LLaMA 3 Groq 70B Tool Use'),
        ('gemma2-9b-it', 'Gemma 2 9B'),
    ]
    return render_template('admin/settings.html', s=current_settings, groq_models=groq_models)


@bp.route('/prompts', methods=['GET'])
@admin_required
def prompts():
    db = get_db()
    templates = db.execute('SELECT * FROM prompt_templates ORDER BY genre').fetchall()
    genres = ['Fantasy', 'Sci-Fi', 'Romance', 'Mystery', 'Adventure', 'Thriller',
              'Children', 'Comedy', 'Historical', 'Business', 'Educational', 'Horror']
    return render_template('admin/prompts.html', templates=templates, genres=genres)


@bp.route('/prompts/add', methods=['POST'])
@admin_required
def add_prompt():
    db = get_db()
    data = request.form
    db.execute(
        '''INSERT INTO prompt_templates
           (genre, name, system_prompt, writing_style, tone, genre_instructions)
           VALUES (?,?,?,?,?,?)''',
        (data.get('genre'), data.get('name'), data.get('system_prompt'),
         data.get('writing_style'), data.get('tone'), data.get('genre_instructions'))
    )
    db.commit()
    flash('Template added.', 'success')
    return redirect(url_for('admin.prompts'))


@bp.route('/prompts/<int:template_id>/edit', methods=['POST'])
@admin_required
def edit_prompt(template_id):
    db = get_db()
    data = request.form
    db.execute(
        '''UPDATE prompt_templates SET genre=?, name=?, system_prompt=?,
           writing_style=?, tone=?, genre_instructions=? WHERE id=?''',
        (data.get('genre'), data.get('name'), data.get('system_prompt'),
         data.get('writing_style'), data.get('tone'), data.get('genre_instructions'),
         template_id)
    )
    db.commit()
    return jsonify({'success': True})


@bp.route('/prompts/<int:template_id>/delete', methods=['POST'])
@admin_required
def delete_prompt(template_id):
    db = get_db()
    db.execute('DELETE FROM prompt_templates WHERE id=?', (template_id,))
    db.commit()
    return jsonify({'success': True})


@bp.route('/projects')
@admin_required
def projects():
    db = get_db()
    all_projects = db.execute('SELECT * FROM projects ORDER BY updated_at DESC').fetchall()
    return render_template('admin/projects.html', projects=all_projects)


@bp.route('/projects/<int:project_id>/delete', methods=['POST'])
@admin_required
def delete_project(project_id):
    db = get_db()
    db.execute('DELETE FROM projects WHERE id=?', (project_id,))
    db.commit()
    flash('Project deleted.', 'success')
    return redirect(url_for('admin.projects'))


@bp.route('/logs')
@admin_required
def logs():
    db = get_db()
    page = int(request.args.get('page', 1))
    per_page = 50
    offset = (page - 1) * per_page
    total = db.execute('SELECT COUNT(*) FROM generation_logs').fetchone()[0]
    log_entries = db.execute(
        '''SELECT gl.*, p.title as project_title FROM generation_logs gl
           LEFT JOIN projects p ON gl.project_id = p.id
           ORDER BY gl.id DESC LIMIT ? OFFSET ?''',
        (per_page, offset)
    ).fetchall()
    return render_template('admin/logs.html', logs=log_entries, page=page,
                           per_page=per_page, total=total)


@bp.route('/logs/clear', methods=['POST'])
@admin_required
def clear_logs():
    db = get_db()
    db.execute('DELETE FROM generation_logs')
    db.commit()
    flash('Logs cleared.', 'success')
    return redirect(url_for('admin.logs'))


@bp.route('/backup', methods=['POST'])
@admin_required
def backup():
    db_path = current_app.config['DATABASE']
    if not os.path.exists(db_path):
        flash('Database not found.', 'error')
        return redirect(url_for('admin.dashboard'))
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    backup_name = f'backup_{timestamp}.db'
    backup_path = os.path.join(current_app.config['EXPORTS_DIR'], backup_name)
    shutil.copy2(db_path, backup_path)
    return send_file(backup_path, as_attachment=True, download_name=backup_name)


@bp.route('/restore', methods=['POST'])
@admin_required
def restore():
    if 'backup_file' not in request.files:
        flash('No file provided.', 'error')
        return redirect(url_for('admin.dashboard'))
    f = request.files['backup_file']
    if not f.filename.endswith('.db'):
        flash('Invalid file type. Upload a .db file.', 'error')
        return redirect(url_for('admin.dashboard'))
    db_path = current_app.config['DATABASE']
    # Validate it's a SQLite file
    try:
        content = f.read()
        if not content.startswith(b'SQLite format 3'):
            flash('Invalid SQLite database file.', 'error')
            return redirect(url_for('admin.dashboard'))
        with open(db_path, 'wb') as out:
            out.write(content)
        flash('Database restored successfully. Please restart the application.', 'success')
    except Exception as e:
        flash(f'Restore failed: {e}', 'error')
    return redirect(url_for('admin.dashboard'))


@bp.route('/reports')
@admin_required
def reports():
    db = get_db()
    page = int(request.args.get('page', 1))
    status_filter = request.args.get('status', '')
    per_page = 25
    offset = (page - 1) * per_page

    where = "WHERE 1=1"
    params = []
    if status_filter:
        where += " AND cr.status = ?"
        params.append(status_filter)

    total = db.execute(
        f'SELECT COUNT(*) FROM content_reports cr {where}', params
    ).fetchone()[0]

    report_entries = db.execute(
        f'''SELECT cr.*, p.title as project_title, c.chapter_title, c.chapter_number
            FROM content_reports cr
            LEFT JOIN projects p ON cr.project_id = p.id
            LEFT JOIN chapters c ON cr.chapter_id = c.id
            {where}
            ORDER BY cr.id DESC LIMIT ? OFFSET ?''',
        params + [per_page, offset]
    ).fetchall()

    pending_count = db.execute(
        "SELECT COUNT(*) FROM content_reports WHERE status='pending'"
    ).fetchone()[0]

    return render_template('admin/reports.html',
                           reports=report_entries, page=page,
                           per_page=per_page, total=total,
                           status_filter=status_filter,
                           pending_count=pending_count)


@bp.route('/reports/<int:report_id>/update', methods=['POST'])
@admin_required
def update_report(report_id):
    db = get_db()
    data = request.get_json(silent=True) or request.form
    new_status = data.get('status', 'reviewed')
    if new_status not in ('pending', 'reviewed', 'actioned', 'dismissed'):
        new_status = 'reviewed'
    admin_notes = data.get('admin_notes', '')
    db.execute(
        '''UPDATE content_reports
           SET status=?, admin_notes=?, reviewed_at=CURRENT_TIMESTAMP
           WHERE id=?''',
        (new_status, admin_notes, report_id)
    )
    db.commit()
    if request.is_json:
        return jsonify({'success': True})
    flash('Report updated.', 'success')
    return redirect(url_for('admin.reports'))


@bp.route('/reports/<int:report_id>/delete', methods=['POST'])
@admin_required
def delete_report(report_id):
    db = get_db()
    db.execute('DELETE FROM content_reports WHERE id=?', (report_id,))
    db.commit()
    if request.is_json:
        return jsonify({'success': True})
    flash('Report deleted.', 'success')
    return redirect(url_for('admin.reports'))


@bp.route('/reports/clear-dismissed', methods=['POST'])
@admin_required
def clear_dismissed_reports():
    db = get_db()
    db.execute("DELETE FROM content_reports WHERE status IN ('dismissed', 'actioned')")
    db.commit()
    flash('Cleared resolved reports.', 'success')
    return redirect(url_for('admin.reports'))


@bp.route('/test-groq', methods=['POST'])
@admin_required
def test_groq():
    """Test the Groq API connection."""
    db = get_db()
    api_key = get_setting(db, 'groq_api_key')
    model = get_setting(db, 'groq_model', 'llama-3.3-70b-versatile')
    if not api_key:
        return jsonify({'error': 'No API key configured.'}), 400
    from services.groq_service import call_groq
    try:
        content, tokens, elapsed = call_groq(
            api_key, model,
            [{'role': 'user', 'content': 'Say "Connection successful!" in exactly 3 words.'}],
            0.1, 0.9, 50
        )
        return jsonify({'success': True, 'response': content.strip(), 'tokens': tokens, 'time': round(elapsed, 2)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
