"""AI Novel & Story Book Creator — main application entry point."""
import os
from flask import Flask, render_template, g, send_from_directory
from flask_wtf.csrf import CSRFProtect
from config import Config
from database import init_app, get_db
from database.models import init_db

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    csrf.init_app(app)

    # Ensure required directories exist
    os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)
    os.makedirs(app.config['EXPORTS_DIR'], exist_ok=True)
    os.makedirs(app.config['UPLOADS_DIR'], exist_ok=True)

    # Initialize database (schema + seed data)
    init_db(app.config['DATABASE'])

    # Register database teardown
    init_app(app)

    # Register blueprints
    from routes.main import bp as main_bp
    from routes.projects import bp as projects_bp
    from routes.outline import bp as outline_bp
    from routes.characters import bp as characters_bp
    from routes.worldbuilding import bp as worldbuilding_bp
    from routes.matter import bp as matter_bp
    from routes.editor import bp as editor_bp
    from routes.export_routes import bp as exports_bp
    from routes.chapters import bp as chapters_bp
    from routes.admin import bp as admin_bp
    from routes.reports import bp as reports_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(outline_bp)
    app.register_blueprint(characters_bp)
    app.register_blueprint(worldbuilding_bp)
    app.register_blueprint(matter_bp)
    app.register_blueprint(editor_bp)
    app.register_blueprint(exports_bp)
    app.register_blueprint(chapters_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(reports_bp)

    # Context processor: inject app-wide settings
    @app.context_processor
    def inject_globals():
        try:
            db = get_db()
            from utils.helpers import get_setting
            return {
                'app_name': get_setting(db, 'app_name', 'KDP Novel & Storybook Creator'),
                'app_footer': '',
                'default_theme': get_setting(db, 'default_theme', 'dark'),
                'maintenance_mode': get_setting(db, 'maintenance_mode', '0') == '1',
            }
        except Exception:
            return {
                'app_name': 'KDP Novel & Storybook Creator',
                'app_footer': '',
                'default_theme': 'dark',
                'maintenance_mode': False,
            }

    # Serve favicon.ico from static/icons to suppress browser 404s
    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, 'static', 'icons'),
            'icon-192.png',
            mimetype='image/png'
        )

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html', error=str(e)), 500

    return app


app = create_app()

if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug)
