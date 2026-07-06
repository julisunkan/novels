"""Writing memory management service."""
from utils.helpers import build_character_context, build_world_context, build_memory_context


def build_full_prompt_context(db, project_id, chapter_number=None):
    """Build the complete context for a chapter generation prompt."""
    chars_ctx = build_character_context(db, project_id)
    world_ctx = build_world_context(db, project_id)
    memory_ctx = build_memory_context(db, project_id, up_to_chapter=chapter_number)
    return chars_ctx, world_ctx, memory_ctx


def save_chapter_memory(db, chapter_id, memory_data):
    """Save the extracted memory data to a chapter record."""
    db.execute(
        '''UPDATE chapters SET
               summary = ?,
               important_events = ?,
               characters_introduced = ?,
               character_changes = ?,
               locations = ?,
               timeline_updates = ?,
               unresolved_plot_points = ?,
               updated_at = CURRENT_TIMESTAMP
           WHERE id = ?''',
        (
            memory_data.get('summary', ''),
            memory_data.get('important_events', ''),
            memory_data.get('characters_introduced', ''),
            memory_data.get('character_changes', ''),
            memory_data.get('locations', ''),
            memory_data.get('timeline_updates', ''),
            memory_data.get('unresolved_plot_points', ''),
            chapter_id
        )
    )
    db.commit()
