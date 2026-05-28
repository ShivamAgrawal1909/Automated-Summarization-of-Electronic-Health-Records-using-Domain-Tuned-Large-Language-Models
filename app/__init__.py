from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app(config_class=Config):
    load_dotenv(_PROJECT_ROOT / ".env")
    app = Flask(
        __name__,
        template_folder=str(_PROJECT_ROOT / "templates"),
        static_folder=str(_PROJECT_ROOT / "static"),
    )
    app.config.from_object(config_class)
    config_class.UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"
    csrf.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.routes.main import bp as main_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.user_portal import bp as user_bp
    from app.routes.admin_portal import bp as admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(user_bp, url_prefix="/app")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    with app.app_context():
        db.create_all()
        _ensure_brand_row()

    @app.context_processor
    def _brand():
        from app.models import BrandInfo

        return {"brand": db.session.query(BrandInfo).first()}

    return app


def _ensure_brand_row():
    from app.models import BrandInfo

    if db.session.query(BrandInfo).first() is None:
        db.session.add(
            BrandInfo(
                project_name="MedSynapse EHR",
                contact_email="support@medsynapse.example",
                address="100 Healthcare Plaza, Boston, MA 02115",
                system_description="Domain-tuned clinical summarization for electronic health records.",
            )
        )
        db.session.commit()
