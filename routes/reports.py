"""User-facing content reporting routes."""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from database import get_db

bp = Blueprint('reports', __name__)

REPORT_REASONS = [
    ('harmful', 'Harmful or dangerous content'),
    ('explicit', 'Explicit or adult content (unexpected)'),
    ('offensive', 'Offensive or hateful content'),
    ('inaccurate', 'Factually inaccurate / misleading'),
    ('copyright', 'Possible copyright violation'),
    ('spam', 'Spam or irrelevant content'),
    ('other', 'Other'),
]


@bp.route('/project/<int:project_id>/chapter/<int:chapter_id>/report', methods=['POST'])
def report_chapter(project_id, chapter_id):
    """Submit a report for AI-generated chapter content."""
    db = get_db()
    chapter = db.execute(
        'SELECT id, project_id FROM chapters WHERE id=? AND project_id=?',
        (chapter_id, project_id)
    ).fetchone()
    if not chapter:
        return jsonify({'error': 'Chapter not found'}), 404

    data = request.get_json(silent=True) or {}
    reason = data.get('reason', '').strip()
    details = data.get('details', '').strip()[:1000]
    reporter_info = data.get('reporter_info', '').strip()[:200]

    valid_reasons = [r[0] for r in REPORT_REASONS]
    if reason not in valid_reasons:
        return jsonify({'error': 'Invalid report reason'}), 400

    db.execute(
        '''INSERT INTO content_reports
           (project_id, chapter_id, content_type, report_reason, report_details, reporter_info)
           VALUES (?,?,?,?,?,?)''',
        (project_id, chapter_id, 'chapter', reason, details, reporter_info)
    )
    db.commit()
    return jsonify({'success': True, 'message': 'Report submitted. Thank you for your feedback.'})


@bp.route('/api/report-reasons')
def get_report_reasons():
    return jsonify({'reasons': [{'value': v, 'label': l} for v, l in REPORT_REASONS]})
