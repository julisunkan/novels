"""Chapter generation pipeline with pause/resume support."""
import threading
import time
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app
from database import get_db, get_raw_db
from utils.helpers import (get_setting, log_history, update_project_stats,
                            count_words, increment_statistic)
from services.groq_service import generate_chapter, generate_chapter_memory, generate_image_prompt
from services.memory_service import build_full_prompt_context, save_chapter_memory

bp = Blueprint('chapters', __name__)

# Per-project generation state: {project_id: {'thread': ..., 'stop': bool, 'pause': bool}}
_gen_state = {}
_gen_lock = threading.Lock()

# Per-chapter single-generation in-progress guard: set of (project_id, chapter_number)
_single_gen_active = set()
_single_gen_lock = threading.Lock()


def _get_template(db, genre):
    t = db.execute('SELECT * FROM prompt_templates WHERE genre=? LIMIT 1', (genre,)).fetchone()
    if not t:
        t = db.execute('SELECT * FROM prompt_templates LIMIT 1').fetchone()
    return dict(t) if t else {}


def _generation_worker(app, project_id):
    """Background thread: generates chapters one by one with memory."""
    with app.app_context():
        db_path = app.config['DATABASE']
        db = get_raw_db(db_path)

        def get_state():
            with _gen_lock:
                return _gen_state.get(project_id, {})

        try:
            project = dict(db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone())
            api_key = db.execute("SELECT value FROM settings WHERE key='groq_api_key'").fetchone()['value']
            model = db.execute("SELECT value FROM settings WHERE key='groq_model'").fetchone()['value']
            template = _get_template(db, project['genre'])

            # Get outline chapters
            outline_chapters = db.execute(
                'SELECT * FROM outline WHERE project_id=? ORDER BY order_index, chapter_number',
                (project_id,)
            ).fetchall()
            if not outline_chapters:
                db.execute("UPDATE projects SET status='draft' WHERE id=?", (project_id,))
                db.commit()
                return

            # Find where to start (resume support)
            last_done = db.execute(
                "SELECT COALESCE(MAX(chapter_number),0) FROM chapters WHERE project_id=? AND status='generated'",
                (project_id,)
            ).fetchone()[0]
            start_from = last_done  # 0-based index into outline

            db.execute("UPDATE projects SET status='generating' WHERE id=?", (project_id,))
            db.commit()

            for i, outline_ch in enumerate(outline_chapters):
                state = get_state()
                if state.get('stop'):
                    db.execute("UPDATE projects SET status='paused' WHERE id=?", (project_id,))
                    db.commit()
                    return
                # Wait while paused
                while state.get('pause') and not state.get('stop'):
                    time.sleep(1)
                    state = get_state()
                if state.get('stop'):
                    db.execute("UPDATE projects SET status='paused' WHERE id=?", (project_id,))
                    db.commit()
                    return

                ch_num = outline_ch['chapter_number']
                if ch_num <= last_done:
                    continue  # Already generated, skip

                # Update status: mark this chapter as generating
                existing = db.execute(
                    'SELECT id FROM chapters WHERE project_id=? AND chapter_number=?',
                    (project_id, ch_num)
                ).fetchone()
                if existing:
                    db.execute(
                        "UPDATE chapters SET status='generating', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (existing['id'],)
                    )
                else:
                    db.execute(
                        "INSERT INTO chapters (project_id, chapter_number, chapter_title, status) VALUES (?,?,?,?)",
                        (project_id, ch_num, outline_ch['chapter_title'], 'generating')
                    )
                db.commit()

                # Update project current chapter
                db.execute(
                    'UPDATE projects SET current_chapter=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                    (ch_num, project_id)
                )
                db.commit()

                # Build context
                chars_ctx, world_ctx, memory_ctx = build_full_prompt_context(
                    db, project_id, chapter_number=ch_num
                )

                # Generate chapter content
                start_time = time.time()
                try:
                    content, tokens, elapsed = generate_chapter(
                        api_key, model, project,
                        dict(outline_ch), chars_ctx, world_ctx, memory_ctx,
                        template, project['temperature'], project['top_p'], project['max_tokens']
                    )
                except Exception as e:
                    db.execute(
                        'INSERT INTO generation_logs (project_id, log_type, status, error_message) VALUES (?,?,?,?)',
                        (project_id, 'chapter', 'error', str(e))
                    )
                    db.commit()
                    # Mark chapter as failed, continue
                    db.execute(
                        "UPDATE chapters SET status='pending' WHERE project_id=? AND chapter_number=?",
                        (project_id, ch_num)
                    )
                    db.commit()
                    continue

                wc = count_words(content)

                # Save chapter
                ch_row = db.execute(
                    'SELECT id FROM chapters WHERE project_id=? AND chapter_number=?',
                    (project_id, ch_num)
                ).fetchone()
                if ch_row:
                    db.execute(
                        '''UPDATE chapters SET chapter_title=?, content=?, word_count=?,
                           status='generated', updated_at=CURRENT_TIMESTAMP WHERE id=?''',
                        (outline_ch['chapter_title'], content, wc, ch_row['id'])
                    )
                    chapter_id = ch_row['id']
                else:
                    chapter_id = db.execute(
                        '''INSERT INTO chapters (project_id, chapter_number, chapter_title,
                           content, word_count, status) VALUES (?,?,?,?,?,?)''',
                        (project_id, ch_num, outline_ch['chapter_title'], content, wc, 'generated')
                    ).lastrowid
                db.commit()

                # Log
                db.execute(
                    '''INSERT INTO generation_logs
                       (project_id, chapter_id, log_type, tokens_used, generation_time, status)
                       VALUES (?,?,?,?,?,?)''',
                    (project_id, chapter_id, 'chapter', tokens, elapsed, 'success')
                )
                db.commit()

                # Generate memory
                try:
                    memory_data, mem_tokens, _ = generate_chapter_memory(
                        api_key, model, outline_ch['chapter_title'], content, project['genre']
                    )
                    save_chapter_memory(db, chapter_id, memory_data)
                except Exception:
                    pass  # Memory generation is non-critical

                # Generate image prompt if needed
                if project.get('include_images'):
                    try:
                        ch_summary = db.execute(
                            'SELECT summary FROM chapters WHERE id=?', (chapter_id,)
                        ).fetchone()
                        img_prompt, _, _ = generate_image_prompt(
                            api_key, model, outline_ch['chapter_title'],
                            ch_summary['summary'] if ch_summary else '',
                            project.get('image_style', 'Realistic'), project['genre']
                        )
                        db.execute(
                            'INSERT INTO images (project_id, chapter_id, prompt, style) VALUES (?,?,?,?)',
                            (project_id, chapter_id, img_prompt, project.get('image_style', 'Realistic'))
                        )
                        db.commit()
                    except Exception:
                        pass

                # Update project stats
                total_words = db.execute(
                    "SELECT COALESCE(SUM(word_count),0) FROM chapters WHERE project_id=? AND status='generated'",
                    (project_id,)
                ).fetchone()[0]
                done_count = db.execute(
                    "SELECT COUNT(*) FROM chapters WHERE project_id=? AND status='generated'",
                    (project_id,)
                ).fetchone()[0]
                db.execute(
                    'UPDATE projects SET total_words=?, current_chapter=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                    (total_words, done_count, project_id)
                )
                db.commit()

                # Update daily stats
                today = time.strftime('%Y-%m-%d')
                db.execute(
                    'INSERT INTO statistics (date, words_generated, api_requests, tokens_used) VALUES (?,?,1,?) '
                    'ON CONFLICT(date) DO UPDATE SET words_generated=words_generated+?, '
                    'api_requests=api_requests+1, tokens_used=tokens_used+?',
                    (today, wc, tokens, wc, tokens)
                )
                db.commit()

            # All chapters done — only mark completed if none are still pending/failed
            pending_count = db.execute(
                "SELECT COUNT(*) FROM chapters WHERE project_id=? AND status != 'generated'",
                (project_id,)
            ).fetchone()[0]

            if pending_count == 0:
                # Only increment books_generated when transitioning to completed
                was_completed = db.execute(
                    "SELECT status FROM projects WHERE id=?", (project_id,)
                ).fetchone()['status'] == 'completed'

                db.execute(
                    "UPDATE projects SET status='completed', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (project_id,)
                )
                if not was_completed:
                    db.execute(
                        'INSERT INTO statistics (date, books_generated) VALUES (?,1) '
                        'ON CONFLICT(date) DO UPDATE SET books_generated=books_generated+1',
                        (time.strftime('%Y-%m-%d'),)
                    )
            else:
                # Some chapters failed — leave as paused so user can retry
                db.execute(
                    "UPDATE projects SET status='paused', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (project_id,)
                )
            db.commit()

        except Exception as e:
            try:
                db.execute("UPDATE projects SET status='paused' WHERE id=?", (project_id,))
                db.execute(
                    'INSERT INTO generation_logs (project_id, log_type, status, error_message) VALUES (?,?,?,?)',
                    (project_id, 'chapter', 'error', f'Worker crash: {e}')
                )
                db.commit()
            except Exception:
                pass
        finally:
            with _gen_lock:
                _gen_state.pop(project_id, None)
            try:
                db.close()
            except Exception:
                pass


@bp.route('/project/<int:project_id>/generate')
def generation_page(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
    if not project:
        return redirect(url_for('main.history'))
    outline = db.execute(
        'SELECT * FROM outline WHERE project_id=? ORDER BY order_index', (project_id,)
    ).fetchall()
    chapters = db.execute(
        'SELECT * FROM chapters WHERE project_id=? ORDER BY chapter_number', (project_id,)
    ).fetchall()
    groq_configured = bool(get_setting(db, 'groq_api_key'))
    return render_template('generation.html', project=project, outline=outline,
                           chapters=chapters, groq_configured=groq_configured)


@bp.route('/project/<int:project_id>/generate/start', methods=['POST'])
def start_generation(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    api_key = get_setting(db, 'groq_api_key')
    if not api_key:
        return jsonify({'error': 'Groq API key not configured. Visit /julisunkan to set it up.'}), 400
    outline = db.execute('SELECT COUNT(*) FROM outline WHERE project_id=?', (project_id,)).fetchone()[0]
    if not outline:
        return jsonify({'error': 'Generate an outline first before starting chapter generation.'}), 400

    with _gen_lock:
        if project_id in _gen_state and _gen_state[project_id]['thread'].is_alive():
            return jsonify({'error': 'Generation already running'}), 400
        _gen_state[project_id] = {'stop': False, 'pause': False, 'thread': None}

    app = current_app._get_current_object()
    t = threading.Thread(target=_generation_worker, args=(app, project_id), daemon=True)
    with _gen_lock:
        _gen_state[project_id]['thread'] = t
    t.start()
    return jsonify({'success': True, 'status': 'generating'})


@bp.route('/project/<int:project_id>/generate/pause', methods=['POST'])
def pause_generation(project_id):
    with _gen_lock:
        state = _gen_state.get(project_id)
        if state:
            state['pause'] = True
    db = get_db()
    db.execute("UPDATE projects SET status='pausing' WHERE id=?", (project_id,))
    db.commit()
    return jsonify({'success': True, 'status': 'pausing'})


@bp.route('/project/<int:project_id>/generate/resume', methods=['POST'])
def resume_generation(project_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
    if not project:
        return jsonify({'error': 'Not found'}), 404

    with _gen_lock:
        state = _gen_state.get(project_id)
        if state and state['thread'].is_alive():
            # Thread is alive but paused — unpause
            state['pause'] = False
            db.execute("UPDATE projects SET status='generating' WHERE id=?", (project_id,))
            db.commit()
            return jsonify({'success': True, 'status': 'generating'})

    # Thread is not running — start fresh (will resume from last completed chapter)
    api_key = get_setting(db, 'groq_api_key')
    if not api_key:
        return jsonify({'error': 'Groq API key not configured.'}), 400

    with _gen_lock:
        _gen_state[project_id] = {'stop': False, 'pause': False, 'thread': None}

    app = current_app._get_current_object()
    t = threading.Thread(target=_generation_worker, args=(app, project_id), daemon=True)
    with _gen_lock:
        _gen_state[project_id]['thread'] = t
    t.start()
    return jsonify({'success': True, 'status': 'generating'})


@bp.route('/project/<int:project_id>/generate/stop', methods=['POST'])
def stop_generation(project_id):
    with _gen_lock:
        state = _gen_state.get(project_id)
        if state:
            state['stop'] = True
            state['pause'] = False
    db = get_db()
    db.execute("UPDATE projects SET status='paused' WHERE id=?", (project_id,))
    db.commit()
    return jsonify({'success': True, 'status': 'paused'})


@bp.route('/api/project/<int:project_id>/progress')
def generation_progress(project_id):
    """AJAX polling endpoint for live progress."""
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
    if not project:
        return jsonify({'error': 'Not found'}), 404

    chapters = db.execute(
        'SELECT chapter_number, chapter_title, status, word_count FROM chapters WHERE project_id=? ORDER BY chapter_number',
        (project_id,)
    ).fetchall()

    generated = [c for c in chapters if c['status'] == 'generated']
    generating = [c for c in chapters if c['status'] == 'generating']
    total_words = sum(c['word_count'] for c in generated)
    target_words = project['num_chapters'] * project['words_per_chapter']
    progress_pct = int(len(generated) / project['num_chapters'] * 100) if project['num_chapters'] else 0

    with _gen_lock:
        thread_alive = (project_id in _gen_state and
                        _gen_state[project_id].get('thread') and
                        _gen_state[project_id]['thread'].is_alive())

    current_chapter_num = None
    current_chapter_title = None
    if generating:
        current_chapter_num = generating[0]['chapter_number']
        current_chapter_title = generating[0]['chapter_title']

    # Get last log for token info
    last_log = db.execute(
        "SELECT tokens_used, generation_time FROM generation_logs WHERE project_id=? AND status='success' ORDER BY id DESC LIMIT 1",
        (project_id,)
    ).fetchone()

    return jsonify({
        'status': project['status'],
        'thread_alive': thread_alive,
        'generated_chapters': len(generated),
        'total_chapters': project['num_chapters'],
        'current_chapter': current_chapter_num,
        'current_chapter_title': current_chapter_title,
        'total_words': total_words,
        'target_words': target_words,
        'progress_pct': progress_pct,
        'last_tokens': last_log['tokens_used'] if last_log else 0,
        'last_gen_time': round(last_log['generation_time'], 1) if last_log else 0,
        'chapters': [dict(c) for c in chapters],
    })


@bp.route('/project/<int:project_id>/chapter/<int:chapter_id>')
def chapter_view(project_id, chapter_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
    chapter = db.execute('SELECT * FROM chapters WHERE id=? AND project_id=?', (chapter_id, project_id)).fetchone()
    if not project or not chapter:
        return redirect(url_for('main.history'))
    images = db.execute('SELECT * FROM images WHERE chapter_id=?', (chapter_id,)).fetchall()
    return render_template('chapter_view.html', project=project, chapter=chapter, images=images)


@bp.route('/project/<int:project_id>/generate/chapter/<int:chapter_number>', methods=['POST'])
def generate_single_chapter(project_id, chapter_number):
    """Generate (or regenerate) a single chapter by outline chapter number."""
    # Guard against concurrent double-clicks for the same chapter
    key = (project_id, chapter_number)
    with _single_gen_lock:
        if key in _single_gen_active:
            return jsonify({'error': 'This chapter is already being generated.'}), 409
        _single_gen_active.add(key)

    try:
        db = get_db()
        project = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        # Block if a bulk generation thread is already running for this project
        with _gen_lock:
            state = _gen_state.get(project_id, {})
        if state.get('thread') and state['thread'].is_alive():
            return jsonify({'error': 'Bulk generation is already running. Stop it first.'}), 409

        outline_ch = db.execute(
            'SELECT * FROM outline WHERE project_id=? AND chapter_number=?',
            (project_id, chapter_number)
        ).fetchone()
        if not outline_ch:
            return jsonify({'error': 'Chapter not found in outline'}), 404

        api_key = get_setting(db, 'groq_api_key')
        if not api_key:
            return jsonify({'error': 'Groq API key not configured.'}), 400

        model = get_setting(db, 'groq_model', 'llama-3.3-70b-versatile')
        template = _get_template(db, project['genre'])
        outline_ch = dict(outline_ch)

        # Upsert a chapters row so we can track status
        existing = db.execute(
            'SELECT id FROM chapters WHERE project_id=? AND chapter_number=?',
            (project_id, chapter_number)
        ).fetchone()
        if existing:
            chapter_id = existing['id']
            db.execute(
                "UPDATE chapters SET status='generating', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (chapter_id,)
            )
        else:
            chapter_id = db.execute(
                "INSERT INTO chapters (project_id, chapter_number, chapter_title, status) VALUES (?,?,?,?)",
                (project_id, chapter_number, outline_ch['chapter_title'], 'generating')
            ).lastrowid
        db.commit()

        chars_ctx, world_ctx, memory_ctx = build_full_prompt_context(
            db, project_id, chapter_number=chapter_number
        )

        # --- Content generation (critical) ---
        try:
            content, tokens, elapsed = generate_chapter(
                api_key, model, dict(project), outline_ch,
                chars_ctx, world_ctx, memory_ctx, template,
                project['temperature'], project['top_p'], project['max_tokens']
            )
        except Exception as e:
            db.execute(
                "UPDATE chapters SET status='pending', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (chapter_id,)
            )
            db.commit()
            current_app.logger.error('Single-chapter generation failed (ch %s): %s', chapter_number, e)
            return jsonify({'error': 'Generation failed. Please try again.'}), 500

        wc = count_words(content)
        db.execute(
            "UPDATE chapters SET chapter_title=?, content=?, word_count=?, status='generated', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (outline_ch['chapter_title'], content, wc, chapter_id)
        )
        db.commit()

        # --- Memory generation (non-critical: failure keeps chapter as generated) ---
        try:
            memory_data, _, _ = generate_chapter_memory(
                api_key, model, outline_ch['chapter_title'], content, project['genre']
            )
            save_chapter_memory(db, chapter_id, memory_data)
        except Exception as e:
            current_app.logger.warning('Chapter memory generation failed (ch %s): %s', chapter_number, e)

        update_project_stats(db, project_id)
        return jsonify({'success': True, 'word_count': wc, 'chapter_id': chapter_id})

    finally:
        with _single_gen_lock:
            _single_gen_active.discard(key)


@bp.route('/project/<int:project_id>/chapter/<int:chapter_id>/regenerate', methods=['POST'])
def regenerate_chapter(project_id, chapter_id):
    db = get_db()
    project = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
    chapter = db.execute('SELECT * FROM chapters WHERE id=? AND project_id=?', (chapter_id, project_id)).fetchone()
    if not project or not chapter:
        return jsonify({'error': 'Not found'}), 404
    api_key = get_setting(db, 'groq_api_key')
    if not api_key:
        return jsonify({'error': 'Groq API key not configured.'}), 400

    outline_ch = db.execute(
        'SELECT * FROM outline WHERE project_id=? AND chapter_number=?',
        (project_id, chapter['chapter_number'])
    ).fetchone()
    if not outline_ch:
        # Build a minimal outline entry from chapter
        outline_ch = {
            'chapter_number': chapter['chapter_number'],
            'chapter_title': chapter['chapter_title'],
            'summary': chapter['summary'] or '',
            'target_word_count': project['words_per_chapter']
        }
    else:
        outline_ch = dict(outline_ch)

    model = get_setting(db, 'groq_model', 'llama-3.3-70b-versatile')
    template = _get_template(db, project['genre'])
    chars_ctx, world_ctx, memory_ctx = build_full_prompt_context(
        db, project_id, chapter_number=chapter['chapter_number']
    )
    try:
        content, tokens, elapsed = generate_chapter(
            api_key, model, dict(project), outline_ch,
            chars_ctx, world_ctx, memory_ctx, template,
            project['temperature'], project['top_p'], project['max_tokens']
        )
        wc = count_words(content)
        db.execute(
            "UPDATE chapters SET content=?, word_count=?, status='generated', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (content, wc, chapter_id)
        )
        db.commit()
        # Regenerate memory (best-effort — don't fail the response if this errors)
        try:
            memory_data, _, _ = generate_chapter_memory(
                api_key, model, chapter['chapter_title'], content, project['genre']
            )
            save_chapter_memory(db, chapter_id, memory_data)
        except Exception:
            pass
        update_project_stats(db, project_id)
        return jsonify({'success': True, 'word_count': wc, 'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/project/<int:project_id>/chapter/<int:chapter_id>/delete', methods=['POST'])
def delete_chapter_content(project_id, chapter_id):
    db = get_db()
    db.execute('DELETE FROM chapters WHERE id=? AND project_id=?', (chapter_id, project_id))
    db.commit()
    update_project_stats(db, project_id)
    return jsonify({'success': True})


@bp.route('/project/<int:project_id>/chapter/<int:chapter_id>/duplicate', methods=['POST'])
def duplicate_chapter_content(project_id, chapter_id):
    db = get_db()
    ch = db.execute('SELECT * FROM chapters WHERE id=? AND project_id=?', (chapter_id, project_id)).fetchone()
    if not ch:
        return jsonify({'error': 'Not found'}), 404
    max_num = db.execute('SELECT MAX(chapter_number) FROM chapters WHERE project_id=?', (project_id,)).fetchone()[0] or 0
    new_id = db.execute(
        'INSERT INTO chapters (project_id, chapter_number, chapter_title, content, word_count, status) VALUES (?,?,?,?,?,?)',
        (project_id, max_num + 1, f"{ch['chapter_title']} (Copy)", ch['content'], ch['word_count'], ch['status'])
    ).lastrowid
    db.commit()
    update_project_stats(db, project_id)
    # If called via AJAX, return JSON; otherwise redirect back to chapter list
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
        return jsonify({'success': True, 'new_id': new_id})
    return redirect(url_for('projects.project_detail', project_id=project_id))
