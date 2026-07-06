"""Export routes: DOCX, PDF, TXT."""
import os
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, send_file, abort
from database import get_db
from utils.helpers import safe_filename
from services.export_service import export_docx, export_pdf, export_txt
import io

bp = Blueprint('exports', __name__)


@bp.route('/project/<int:project_id>/export')
def export_page(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        return redirect(url_for('main.history'))
    chapters_done = db.execute(
        "SELECT COUNT(*) FROM chapters WHERE project_id=? AND status='generated'", (project_id,)
    ).fetchone()[0]
    return render_template('export.html', project=project, chapters_done=chapters_done)


@bp.route('/project/<int:project_id>/export/txt', methods=['POST'])
def do_export_txt(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        abort(404)
    options = {
        'include_toc': request.form.get('include_toc', '1') == '1',
        'include_front_matter': request.form.get('include_front_matter', '1') == '1',
        'include_back_matter': request.form.get('include_back_matter', '1') == '1',
    }
    content = export_txt(db, project_id, options)
    filename = safe_filename(project['title']) + '.txt'
    return send_file(
        io.BytesIO(content),
        mimetype='text/plain',
        as_attachment=True,
        download_name=filename
    )


@bp.route('/project/<int:project_id>/export/docx', methods=['POST'])
def do_export_docx(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        abort(404)
    options = {
        'include_toc': request.form.get('include_toc', '1') == '1',
        'include_front_matter': request.form.get('include_front_matter', '1') == '1',
        'include_back_matter': request.form.get('include_back_matter', '1') == '1',
        'include_headers': request.form.get('include_headers', '1') == '1',
        'include_footers': request.form.get('include_footers', '1') == '1',
        'include_page_numbers': request.form.get('include_page_numbers', '1') == '1',
    }
    try:
        content = export_docx(db, project_id, options)
        filename = safe_filename(project['title']) + '.docx'
        return send_file(
            io.BytesIO(content),
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/project/<int:project_id>/export/pdf', methods=['POST'])
def do_export_pdf(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        abort(404)
    options = {
        'include_toc': request.form.get('include_toc', '1') == '1',
        'include_front_matter': request.form.get('include_front_matter', '1') == '1',
        'include_back_matter': request.form.get('include_back_matter', '1') == '1',
        'include_page_numbers': request.form.get('include_page_numbers', '1') == '1',
    }
    try:
        content = export_pdf(db, project_id, options)
        filename = safe_filename(project['title']) + '.pdf'
        return send_file(
            io.BytesIO(content),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
