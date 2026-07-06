# AI Novel & Story Book Creator

A Flask web application for writing AI-powered novels and story books using the Groq LLM API.

## Stack

- **Backend**: Python / Flask 3.0 with SQLite database
- **AI**: Groq API (LLaMA 3, Mixtral models)
- **Frontend**: Bootstrap 5, vanilla JS, Jinja2 templates
- **Export**: DOCX (python-docx), PDF (reportlab), TXT

## How to Run

```
python app.py
```

The app starts on port 5000.

## Key Notes

- Flask 3.0: all `request.get_json()` calls use `request.is_json` branching (`request.get_json() if request.is_json else request.form`) to avoid the Flask 3.0 415 breaking change where `get_json()` raises 415 when content-type is not JSON.
- The Groq API key is configured in the admin panel at `/julisunkan` (default password: `admin123`).
- SQLite DB lives at `database/novel_creator.db`.
- Exports are written to `exports/`, uploads to `uploads/`.

## Admin Panel

URL: `/julisunkan`  
Default password: `admin123`  
Set your Groq API key here before generating content.

## User Preferences

- Keep existing Flask/SQLite/Jinja2 stack — do not migrate.
