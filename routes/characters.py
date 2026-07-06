"""Character management routes."""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from database import get_db

bp = Blueprint('characters', __name__)


@bp.route('/project/<int:project_id>/characters')
def characters_page(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        return redirect(url_for('main.history'))
    chars = db.execute(
        'SELECT * FROM characters WHERE project_id = ? ORDER BY name', (project_id,)
    ).fetchall()
    return render_template('characters.html', project=project, characters=chars)


@bp.route('/project/<int:project_id>/characters/add', methods=['POST'])
def add_character(project_id):
    db = get_db()
    data = request.get_json() or request.form
    char_id = db.execute(
        '''INSERT INTO characters
           (project_id, name, nickname, age, gender, occupation, personality,
            appearance, strengths, weaknesses, goals, relationships, backstory, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (project_id, data.get('name', 'New Character'), data.get('nickname', ''),
         data.get('age', ''), data.get('gender', ''), data.get('occupation', ''),
         data.get('personality', ''), data.get('appearance', ''),
         data.get('strengths', ''), data.get('weaknesses', ''),
         data.get('goals', ''), data.get('relationships', ''),
         data.get('backstory', ''), data.get('notes', ''))
    ).lastrowid
    db.commit()
    row = db.execute('SELECT * FROM characters WHERE id = ?', (char_id,)).fetchone()
    return jsonify({'success': True, 'character': dict(row)})


@bp.route('/project/<int:project_id>/characters/<int:char_id>', methods=['GET'])
def get_character(project_id, char_id):
    db = get_db()
    char = db.execute('SELECT * FROM characters WHERE id=? AND project_id=?', (char_id, project_id)).fetchone()
    if not char:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(char))


@bp.route('/project/<int:project_id>/characters/<int:char_id>/edit', methods=['POST'])
def edit_character(project_id, char_id):
    db = get_db()
    data = request.get_json() or request.form
    db.execute(
        '''UPDATE characters SET name=?, nickname=?, age=?, gender=?, occupation=?,
           personality=?, appearance=?, strengths=?, weaknesses=?, goals=?,
           relationships=?, backstory=?, notes=? WHERE id=? AND project_id=?''',
        (data.get('name', ''), data.get('nickname', ''), data.get('age', ''),
         data.get('gender', ''), data.get('occupation', ''), data.get('personality', ''),
         data.get('appearance', ''), data.get('strengths', ''), data.get('weaknesses', ''),
         data.get('goals', ''), data.get('relationships', ''), data.get('backstory', ''),
         data.get('notes', ''), char_id, project_id)
    )
    db.commit()
    return jsonify({'success': True})


@bp.route('/project/<int:project_id>/characters/<int:char_id>/delete', methods=['POST'])
def delete_character(project_id, char_id):
    db = get_db()
    db.execute('DELETE FROM characters WHERE id=? AND project_id=?', (char_id, project_id))
    db.commit()
    return jsonify({'success': True})
