"""Project CRUD routes."""
import json
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from database import get_db
from utils.helpers import get_setting, log_history, update_project_stats, safe_filename
from services.groq_service import generate_titles

bp = Blueprint('projects', __name__)

GENRES = ['Fantasy', 'Sci-Fi', 'Romance', 'Mystery', 'Adventure', 'Thriller',
          'Children', 'Comedy', 'Historical', 'Business', 'Educational', 'Horror', 'Other']
STORY_TYPES = ['Novel', 'Novella', 'Short Story Collection', 'Non-Fiction', 'Memoir', 'Biography']
POV_OPTIONS = ['First Person', 'Second Person', 'Third Person Limited', 'Third Person Omniscient']
TENSES = ['Past', 'Present', 'Future']
STYLES = ['Descriptive', 'Minimalist', 'Lyrical', 'Action-Oriented', 'Dialogue-Heavy', 'Stream of Consciousness']
TONES = ['Adventurous', 'Dark', 'Humorous', 'Romantic', 'Suspenseful', 'Inspirational', 'Melancholic', 'Whimsical']
AUDIENCES = ['Children (5-8)', 'Middle Grade (8-12)', 'Young Adult (12-18)', 'Adult', 'All Ages']
LANGUAGES = ['English', 'Spanish', 'French', 'German', 'Italian', 'Portuguese', 'Other']
IMAGE_STYLES = ['Realistic', 'Fantasy Art', 'Watercolor', 'Oil Painting', 'Anime', 'Comic Book', 'Pencil Sketch']
CREATIVITY = [('conservative', 'Conservative'), ('balanced', 'Balanced'), ('creative', 'Creative'), ('wild', 'Wild')]
GROQ_MODELS = [
    ('llama3-70b-8192', 'LLaMA 3 70B (Recommended)'),
    ('llama3-8b-8192', 'LLaMA 3 8B (Fast)'),
    ('llama-3.1-70b-versatile', 'LLaMA 3.1 70B Versatile'),
    ('llama-3.1-8b-instant', 'LLaMA 3.1 8B Instant'),
    ('mixtral-8x7b-32768', 'Mixtral 8x7B'),
    ('gemma-7b-it', 'Gemma 7B'),
]


@bp.route('/project/new')
def new_project():
    db = get_db()
    groq_configured = bool(get_setting(db, 'groq_api_key'))
    return render_template('project_new.html',
                           genres=GENRES, story_types=STORY_TYPES, pov_options=POV_OPTIONS,
                           tenses=TENSES, styles=STYLES, tones=TONES, audiences=AUDIENCES,
                           languages=LANGUAGES, image_styles=IMAGE_STYLES,
                           creativity=CREATIVITY, groq_configured=groq_configured)


@bp.route('/project/create', methods=['POST'])
def create_project():
    db = get_db()
    data = request.form

    def float_or(key, default):
        try:
            return float(data.get(key, default))
        except (ValueError, TypeError):
            return float(default)

    def int_or(key, default):
        try:
            return int(data.get(key, default))
        except (ValueError, TypeError):
            return int(default)

    project_id = db.execute(
        '''INSERT INTO projects
           (title, subtitle, genre, audience, description, language, story_type,
            writing_style, point_of_view, tense, tone, num_chapters, words_per_chapter,
            creativity_level, temperature, top_p, max_tokens, include_images,
            images_per_chapter, image_style)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (
            data.get('title', 'Untitled').strip(),
            data.get('subtitle', '').strip(),
            data.get('genre', 'Fantasy'),
            data.get('audience', 'Adult'),
            data.get('description', '').strip(),
            data.get('language', 'English'),
            data.get('story_type', 'Novel'),
            data.get('writing_style', 'Descriptive'),
            data.get('point_of_view', 'Third Person Limited'),
            data.get('tense', 'Past'),
            data.get('tone', 'Adventurous'),
            int_or('num_chapters', 10),
            int_or('words_per_chapter', 2000),
            data.get('creativity_level', 'balanced'),
            float_or('temperature', 0.7),
            float_or('top_p', 0.9),
            int_or('max_tokens', 4096),
            1 if data.get('include_images') else 0,
            int_or('images_per_chapter', 1),
            data.get('image_style', 'Realistic'),
        )
    ).lastrowid
    db.commit()
    log_history(db, project_id, 'created', f'Project "{data.get("title")}" created')
    return redirect(url_for('projects.project_detail', project_id=project_id))


@bp.route('/project/<int:project_id>')
def project_detail(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        return redirect(url_for('main.history'))
    chapters = db.execute(
        'SELECT * FROM chapters WHERE project_id = ? ORDER BY chapter_number',
        (project_id,)
    ).fetchall()
    outline = db.execute(
        'SELECT * FROM outline WHERE project_id = ? ORDER BY order_index, chapter_number',
        (project_id,)
    ).fetchall()
    char_count = db.execute('SELECT COUNT(*) FROM characters WHERE project_id = ?', (project_id,)).fetchone()[0]
    world_count = db.execute('SELECT COUNT(*) FROM worldbuilding WHERE project_id = ?', (project_id,)).fetchone()[0]
    outline_count = len(outline)
    generated_count = sum(1 for c in chapters if c['status'] == 'generated')
    total_words = sum(c['word_count'] for c in chapters)
    target_words = (project['num_chapters'] or 10) * (project['words_per_chapter'] or 2000)
    progress = int((generated_count / project['num_chapters'] * 100)) if project['num_chapters'] else 0
    groq_configured = bool(get_setting(db, 'groq_api_key'))
    return render_template('project_detail.html',
                           project=project, chapters=chapters, outline=outline,
                           char_count=char_count, world_count=world_count,
                           outline_count=outline_count, generated_count=generated_count,
                           total_words=total_words, target_words=target_words,
                           progress=progress, groq_configured=groq_configured)


@bp.route('/project/<int:project_id>/edit', methods=['GET', 'POST'])
def edit_project(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        return redirect(url_for('main.history'))
    if request.method == 'POST':
        data = request.form
        db.execute(
            '''UPDATE projects SET title=?, subtitle=?, genre=?, audience=?, description=?,
               language=?, story_type=?, writing_style=?, point_of_view=?, tense=?, tone=?,
               num_chapters=?, words_per_chapter=?, creativity_level=?, temperature=?,
               top_p=?, max_tokens=?, include_images=?, images_per_chapter=?, image_style=?,
               updated_at=CURRENT_TIMESTAMP WHERE id=?''',
            (
                data.get('title', ''), data.get('subtitle', ''), data.get('genre', ''),
                data.get('audience', ''), data.get('description', ''), data.get('language', ''),
                data.get('story_type', ''), data.get('writing_style', ''),
                data.get('point_of_view', ''), data.get('tense', ''), data.get('tone', ''),
                int(data.get('num_chapters', 10)), int(data.get('words_per_chapter', 2000)),
                data.get('creativity_level', 'balanced'), float(data.get('temperature', 0.7)),
                float(data.get('top_p', 0.9)), int(data.get('max_tokens', 4096)),
                1 if data.get('include_images') else 0,
                int(data.get('images_per_chapter', 1)), data.get('image_style', 'Realistic'),
                project_id
            )
        )
        db.commit()
        log_history(db, project_id, 'edited', 'Project settings updated')
        return redirect(url_for('projects.project_detail', project_id=project_id))
    return render_template('project_edit.html', project=project,
                           genres=GENRES, story_types=STORY_TYPES, pov_options=POV_OPTIONS,
                           tenses=TENSES, styles=STYLES, tones=TONES, audiences=AUDIENCES,
                           languages=LANGUAGES, image_styles=IMAGE_STYLES, creativity=CREATIVITY)


@bp.route('/project/<int:project_id>/delete', methods=['POST'])
def delete_project(project_id):
    db = get_db()
    db.execute('DELETE FROM projects WHERE id = ?', (project_id,))
    db.commit()
    return redirect(url_for('main.history'))


@bp.route('/project/<int:project_id>/duplicate', methods=['POST'])
def duplicate_project(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        return jsonify({'error': 'Not found'}), 404
    new_id = db.execute(
        '''INSERT INTO projects
           (title, subtitle, genre, audience, description, language, story_type,
            writing_style, point_of_view, tense, tone, num_chapters, words_per_chapter,
            creativity_level, temperature, top_p, max_tokens, include_images,
            images_per_chapter, image_style, status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (
            f"{project['title']} (Copy)", project['subtitle'], project['genre'],
            project['audience'], project['description'], project['language'],
            project['story_type'], project['writing_style'], project['point_of_view'],
            project['tense'], project['tone'], project['num_chapters'],
            project['words_per_chapter'], project['creativity_level'],
            project['temperature'], project['top_p'], project['max_tokens'],
            project['include_images'], project['images_per_chapter'],
            project['image_style'], 'draft'
        )
    ).lastrowid
    db.commit()
    log_history(db, new_id, 'duplicated', f'Duplicated from project #{project_id}')
    return redirect(url_for('projects.project_detail', project_id=new_id))


@bp.route('/project/<int:project_id>/generate-titles', methods=['POST'])
def ajax_generate_titles(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    api_key = get_setting(db, 'groq_api_key')
    if not api_key:
        return jsonify({'error': 'Groq API key not configured. Visit Admin Settings.'}), 400
    model = get_setting(db, 'groq_model', 'llama3-70b-8192')
    try:
        data, tokens, elapsed = generate_titles(api_key, model, dict(project))
        return jsonify({'success': True, 'data': data, 'tokens': tokens})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/project/<int:project_id>/generate-cover-prompt', methods=['POST'])
def ajax_generate_cover_prompt(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    api_key = get_setting(db, 'groq_api_key')
    if not api_key:
        return jsonify({'error': 'Groq API key not configured.'}), 400
    model = get_setting(db, 'groq_model', 'llama3-70b-8192')
    from services.groq_service import generate_cover_prompt
    try:
        prompt, tokens, _ = generate_cover_prompt(api_key, model, dict(project))
        db.execute('UPDATE projects SET cover_prompt=? WHERE id=?', (prompt, project_id))
        db.commit()
        return jsonify({'success': True, 'prompt': prompt})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
