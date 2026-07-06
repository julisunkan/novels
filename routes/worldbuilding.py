"""World building routes."""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from database import get_db

bp = Blueprint('worldbuilding', __name__)

CATEGORIES = [
    ('locations', 'Locations'),
    ('cities', 'Cities'),
    ('kingdoms', 'Kingdoms & Empires'),
    ('villages', 'Villages & Towns'),
    ('planets', 'Planets & Realms'),
    ('magic_system', 'Magic System'),
    ('technology', 'Technology'),
    ('history', 'History'),
    ('timeline', 'Timeline'),
    ('lore', 'Lore & Myths'),
    ('religion', 'Religion & Gods'),
    ('politics', 'Politics & Power'),
    ('economy', 'Economy & Trade'),
    ('culture', 'Culture & Customs'),
    ('languages', 'Languages'),
    ('rules', 'Rules & Laws'),
]


@bp.route('/project/<int:project_id>/worldbuilding')
def worldbuilding_page(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        return redirect(url_for('main.history'))
    entries = db.execute(
        'SELECT * FROM worldbuilding WHERE project_id = ? ORDER BY category, name', (project_id,)
    ).fetchall()
    # Group by category
    grouped = {}
    for cat_key, cat_label in CATEGORIES:
        grouped[cat_key] = {
            'label': cat_label,
            'entries': [e for e in entries if e['category'] == cat_key]
        }
    return render_template('worldbuilding.html', project=project, grouped=grouped,
                           categories=CATEGORIES)


@bp.route('/project/<int:project_id>/worldbuilding/add', methods=['POST'])
def add_entry(project_id):
    db = get_db()
    data = request.get_json() if request.is_json else request.form
    entry_id = db.execute(
        'INSERT INTO worldbuilding (project_id, category, name, description, details) VALUES (?,?,?,?,?)',
        (project_id, data.get('category', 'locations'), data.get('name', 'New Entry'),
         data.get('description', ''), data.get('details', ''))
    ).lastrowid
    db.commit()
    row = db.execute('SELECT * FROM worldbuilding WHERE id=?', (entry_id,)).fetchone()
    return jsonify({'success': True, 'entry': dict(row)})


@bp.route('/project/<int:project_id>/worldbuilding/<int:entry_id>', methods=['GET'])
def get_entry(project_id, entry_id):
    db = get_db()
    entry = db.execute('SELECT * FROM worldbuilding WHERE id=? AND project_id=?', (entry_id, project_id)).fetchone()
    if not entry:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(entry))


@bp.route('/project/<int:project_id>/worldbuilding/<int:entry_id>/edit', methods=['POST'])
def edit_entry(project_id, entry_id):
    db = get_db()
    data = request.get_json() if request.is_json else request.form
    db.execute(
        'UPDATE worldbuilding SET category=?, name=?, description=?, details=? WHERE id=? AND project_id=?',
        (data.get('category', ''), data.get('name', ''), data.get('description', ''),
         data.get('details', ''), entry_id, project_id)
    )
    db.commit()
    return jsonify({'success': True})


@bp.route('/project/<int:project_id>/worldbuilding/<int:entry_id>/delete', methods=['POST'])
def delete_entry(project_id, entry_id):
    db = get_db()
    db.execute('DELETE FROM worldbuilding WHERE id=? AND project_id=?', (entry_id, project_id))
    db.commit()
    return jsonify({'success': True})
