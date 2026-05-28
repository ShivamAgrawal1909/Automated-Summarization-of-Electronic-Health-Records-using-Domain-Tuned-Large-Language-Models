from pathlib import Path

from flask import Blueprint, abort, render_template, send_from_directory

from app import db
from app.models import BrandInfo

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    brand = db.session.query(BrandInfo).first()
    return render_template("landing.html", brand=brand)


@bp.route("/media/brand-logo")
def brand_logo():
    brand = db.session.query(BrandInfo).first()
    if not brand or not brand.logo_path:
        abort(404)
    p = Path(brand.logo_path)
    if not p.is_file():
        abort(404)
    return send_from_directory(str(p.parent), p.name)
