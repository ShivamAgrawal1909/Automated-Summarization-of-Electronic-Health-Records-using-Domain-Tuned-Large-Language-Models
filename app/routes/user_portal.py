from datetime import datetime, timezone
from pathlib import Path
import re

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from app import db
from app.decorators import user_required
from app.models import EHRDocument, MedicalTerm, Patient, Summary, User
from app.services.extraction import extract_text_from_file
from app.services.pdf_export import build_summary_pdf
from app.services.summarizer import (
    LABELS,
    SECTION_KEYS,
    json_dumps_sections,
    json_loads_sections,
    summarize_ehr_text,
    sections_to_display_text,
)

bp = Blueprint("user", __name__)


@bp.context_processor
def _workspace_context():
    if not current_user.is_authenticated or getattr(current_user, "role", None) == "admin":
        return {}
    uid = current_user.id
    n_pat = db.session.scalar(select(func.count(Patient.id)).where(Patient.user_id == uid)) or 0
    n_ehr = db.session.scalar(select(func.count(EHRDocument.id)).where(EHRDocument.user_id == uid)) or 0
    n_sum = db.session.scalar(select(func.count(Summary.id)).where(Summary.user_id == uid)) or 0
    n_saved = (
        db.session.scalar(
            select(func.count(Summary.id)).where(Summary.user_id == uid, Summary.is_saved.is_(True))
        )
        or 0
    )
    return {
        "ws_counts": {
            "patients": n_pat,
            "ehr": n_ehr,
            "summaries": n_sum,
            "saved": n_saved,
        },
    }


def _now():
    return datetime.now(timezone.utc)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


def _get_patient(pid, check_user: int) -> Patient:
    p = db.session.get(Patient, pid)
    if not p or p.user_id != check_user:
        abort(404)
    return p


@bp.route("/dashboard")
@login_required
@user_required
def dashboard():
    uid = current_user.id
    u = db.session.get(User, uid)
    total_ehr = (
        db.session.scalar(select(func.count(EHRDocument.id)).where(EHRDocument.user_id == uid)) or 0
    )
    total_patients = (
        db.session.scalar(select(func.count(Patient.id)).where(Patient.user_id == uid)) or 0
    )
    total_summaries = (
        db.session.scalar(select(func.count(Summary.id)).where(Summary.user_id == uid)) or 0
    )
    saved_summaries = (
        db.session.scalar(
            select(func.count(Summary.id)).where(Summary.user_id == uid, Summary.is_saved.is_(True))
        )
        or 0
    )
    recent = (
        db.session.execute(
            select(Summary)
            .where(Summary.user_id == uid)
            .options(joinedload(Summary.patient), joinedload(Summary.document))
            .order_by(Summary.created_at.desc())
            .limit(8)
        )
        .scalars()
        .all()
    )
    recent_docs = (
        db.session.execute(
            select(EHRDocument)
            .where(EHRDocument.user_id == uid)
            .options(joinedload(EHRDocument.patient))
            .order_by(EHRDocument.uploaded_at.desc())
            .limit(6)
        )
        .scalars()
        .all()
    )
    return render_template(
        "user/dashboard.html",
        account=u,
        total_ehr=total_ehr,
        total_patients=total_patients,
        total_summaries=total_summaries,
        saved_summaries=saved_summaries,
        recent_summaries=recent,
        recent_docs=recent_docs,
    )


@bp.route("/profile", methods=["GET", "POST"])
@login_required
@user_required
def profile():
    u = db.session.get(User, current_user.id)
    if request.method == "POST":
        u.name = (request.form.get("name") or u.name).strip()
        u.phone = (request.form.get("phone") or "").strip()
        new_email = (request.form.get("email") or "").strip().lower()
        if new_email and new_email != u.email:
            taken = db.session.scalar(select(User).where(User.email == new_email, User.id != u.id))
            if taken:
                flash("That email is already in use.", "error")
            else:
                u.email = new_email
        pw = request.form.get("password") or ""
        if len(pw) >= 6:
            u.set_password(pw)
        elif pw:
            flash("Password must be at least 6 characters.", "error")
            return render_template("user/profile.html", user=u)
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("user.profile"))
    return render_template("user/profile.html", user=u)


@bp.route("/patients")
@login_required
@user_required
def patients_list():
    uid = current_user.id
    items = (
        db.session.execute(select(Patient).where(Patient.user_id == uid).order_by(Patient.name))
        .scalars()
        .all()
    )
    doc_rows = (
        db.session.execute(
            select(EHRDocument.patient_id, func.count(EHRDocument.id))
            .where(EHRDocument.user_id == uid)
            .group_by(EHRDocument.patient_id)
        )
        .all()
    )
    doc_count_by_patient = {row[0]: row[1] for row in doc_rows}
    sum_rows = (
        db.session.execute(
            select(Summary.patient_id, func.count(Summary.id))
            .where(Summary.user_id == uid)
            .group_by(Summary.patient_id)
        )
        .all()
    )
    summary_count_by_patient = {row[0]: row[1] for row in sum_rows}
    return render_template(
        "user/patients_list.html",
        patients=items,
        doc_count_by_patient=doc_count_by_patient,
        summary_count_by_patient=summary_count_by_patient,
    )


@bp.route("/patients/new", methods=["GET", "POST"])
@login_required
@user_required
def patients_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        patient_id = (request.form.get("patient_id") or "").strip()
        age = request.form.get("age")
        gender = (request.form.get("gender") or "").strip()
        contact = (request.form.get("contact") or "").strip()
        disease_hint = (request.form.get("disease_hint") or "").strip()
        if not name or not patient_id:
            flash("Name and patient ID are required.", "error")
            return render_template("user/patient_form.html", patient=None)
        dup = db.session.scalar(
            select(Patient).where(
                Patient.user_id == current_user.id,
                Patient.patient_id == patient_id,
            )
        )
        if dup:
            flash("You already have a patient with this patient ID.", "error")
            return render_template("user/patient_form.html", patient=None)
        p = Patient(
            user_id=current_user.id,
            patient_id=patient_id,
            name=name,
            age=int(age) if age and str(age).isdigit() else None,
            gender=gender or None,
            contact=contact or None,
            disease_hint=disease_hint or None,
        )
        db.session.add(p)
        db.session.commit()
        flash("Patient record created.", "success")
        return redirect(url_for("user.patients_list"))
    return render_template("user/patient_form.html", patient=None)


@bp.route("/patients/<int:pid>/edit", methods=["GET", "POST"])
@login_required
@user_required
def patients_edit(pid):
    p = _get_patient(pid, current_user.id)
    if request.method == "POST":
        p.name = (request.form.get("name") or p.name).strip()
        new_ref = (request.form.get("patient_id") or "").strip()
        if new_ref and new_ref != p.patient_id:
            dup = db.session.scalar(
                select(Patient).where(
                    Patient.user_id == current_user.id,
                    Patient.patient_id == new_ref,
                    Patient.id != p.id,
                )
            )
            if dup:
                flash("Another patient already uses this patient ID.", "error")
                return render_template("user/patient_form.html", patient=p)
            p.patient_id = new_ref
        age = request.form.get("age")
        p.age = int(age) if age and str(age).isdigit() else None
        p.gender = (request.form.get("gender") or "").strip() or None
        p.contact = (request.form.get("contact") or "").strip() or None
        p.disease_hint = (request.form.get("disease_hint") or "").strip() or None
        db.session.commit()
        flash("Patient updated.", "success")
        return redirect(url_for("user.patients_list"))
    return render_template("user/patient_form.html", patient=p)


@bp.route("/patients/<int:pid>/delete", methods=["POST"])
@login_required
@user_required
def patients_delete(pid):
    p = _get_patient(pid, current_user.id)
    db.session.delete(p)
    db.session.commit()
    flash("Patient record deleted.", "info")
    return redirect(url_for("user.patients_list"))


@bp.route("/upload", methods=["GET", "POST"])
@login_required
@user_required
def upload_ehr():
    patients = (
        db.session.execute(select(Patient).where(Patient.user_id == current_user.id).order_by(Patient.name))
        .scalars()
        .all()
    )
    if request.method == "POST":
        pid = request.form.get("patient_id", type=int)
        if not pid:
            flash("Select a patient.", "error")
            return render_template("user/upload.html", patients=patients)
        patient = _get_patient(pid, current_user.id)
        f = request.files.get("file")
        if not f or not f.filename:
            flash("Choose a file (.txt or .pdf).", "error")
            return render_template("user/upload.html", patients=patients)
        if not allowed_file(f.filename):
            flash("Supported formats: PDF or plain text.", "error")
            return render_template("user/upload.html", patients=patients)
        ext = f.filename.rsplit(".", 1)[1].lower()
        safe = secure_filename(f.filename) or f"ehr.{ext}"
        up = current_app.config["UPLOAD_FOLDER"] / f"u{current_user.id}" / f"p{patient.id}"
        up.mkdir(parents=True, exist_ok=True)
        path = up / safe
        f.save(str(path))
        doc = EHRDocument(
            patient_id=patient.id,
            user_id=current_user.id,
            original_filename=f.filename,
            stored_path=str(path),
            file_type=ext,
        )
        try:
            doc.extracted_text = extract_text_from_file(path, ext)
        except Exception as e:
            db.session.rollback()
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            flash(f"Extraction failed: {e}", "error")
            return render_template("user/upload.html", patients=patients)
        db.session.add(doc)
        db.session.commit()
        flash("File uploaded and text extracted. Review below.", "success")
        return redirect(url_for("user.ehr_detail", eid=doc.id))
    return render_template("user/upload.html", patients=patients)


@bp.route("/ehr/<int:eid>")
@login_required
@user_required
def ehr_detail(eid):
    doc = db.session.get(EHRDocument, eid)
    if not doc or doc.user_id != current_user.id:
        abort(404)
    raw = doc.extracted_text or ""
    n_chars = len(raw)
    n_words = len(raw.split()) if raw else 0
    n_summaries_for_doc = (
        db.session.scalar(
            select(func.count(Summary.id)).where(Summary.ehr_document_id == doc.id)
        )
        or 0
    )
    return render_template(
        "user/ehr_detail.html",
        doc=doc,
        patient=doc.patient,
        n_chars=n_chars,
        n_words=n_words,
        n_chars_f=f"{n_chars:,}",
        n_words_f=f"{n_words:,}",
        n_summaries_for_doc=n_summaries_for_doc,
    )


@bp.route("/ehr/<int:eid>/reextract", methods=["POST"])
@login_required
@user_required
def ehr_reextract(eid):
    doc = db.session.get(EHRDocument, eid)
    if not doc or doc.user_id != current_user.id:
        abort(404)
    path = Path(doc.stored_path)
    try:
        doc.extracted_text = extract_text_from_file(path, doc.file_type)
        db.session.commit()
        flash("Text re-extracted.", "success")
    except Exception as e:
        flash(f"Extraction error: {e}", "error")
    return redirect(url_for("user.ehr_detail", eid=doc.id))


@bp.route("/ehr/<int:eid>/summarize", methods=["POST"])
@login_required
@user_required
def ehr_summarize(eid):
    doc = db.session.get(EHRDocument, eid)
    if not doc or doc.user_id != current_user.id:
        abort(404)
    text = doc.extracted_text or ""
    terms = [t.term for t in db.session.execute(select(MedicalTerm).limit(500)).scalars().all()]
    sec = summarize_ehr_text(text, terms)
    s = Summary(
        ehr_document_id=doc.id,
        patient_id=doc.patient_id,
        user_id=current_user.id,
        generated_json=json_dumps_sections(sec),
        edited_content=sections_to_display_text(sec),
        is_saved=False,
    )
    s.updated_at = _now()
    db.session.add(s)
    db.session.commit()
    flash("Summary generated. Review and edit as needed, then save.", "success")
    return redirect(url_for("user.summary_detail", sid=s.id))


@bp.route("/summary/<int:sid>", methods=["GET", "POST"])
@login_required
@user_required
def summary_detail(sid):
    s = db.session.get(Summary, sid)
    if not s or s.user_id != current_user.id:
        abort(404)
    doc = s.document
    raw = doc.extracted_text or ""
    if request.method == "POST":
        s.edited_content = request.form.get("edited_content", "")
        if "save" in request.form:
            s.is_saved = True
        s.updated_at = _now()
        db.session.commit()
        flash("Summary saved." if s.is_saved else "Draft updated.", "success")
        return redirect(url_for("user.summary_detail", sid=s.id))
    sections = json_loads_sections(s.generated_json) if s.generated_json else None
    return render_template(
        "user/summary_detail.html",
        summary=s,
        document=doc,
        patient=s.patient,
        raw_ehr=raw,
        sections=sections,
        labels=LABELS,
        section_keys=SECTION_KEYS,
    )


@bp.route("/summary/<int:sid>/download")
@login_required
@user_required
def summary_download(sid):
    s = db.session.get(Summary, sid)
    if not s or s.user_id != current_user.id:
        abort(404)
    p = s.patient
    title = f"EHR Summary — {p.name}"
    patient_line = f"Patient: {p.name} | ID: {p.patient_id} | Age: {p.age or '—'} | Gender: {p.gender or '—'}"
    body = s.edited_content or sections_to_display_text(json_loads_sections(s.generated_json))
    sec = json_loads_sections(s.generated_json) if s.generated_json else None
    pdf_io = build_summary_pdf(title, patient_line, body, sec)
    fn = f"summary_{p.patient_id}_{sid}.pdf"
    return send_file(
        pdf_io,
        as_attachment=True,
        download_name=re.sub(r"[^\w\-.]+", "_", fn),
        mimetype="application/pdf",
    )


@bp.route("/summaries")
@login_required
@user_required
def summaries_history():
    items = (
        db.session.execute(
            select(Summary)
            .where(Summary.user_id == current_user.id)
            .options(joinedload(Summary.patient), joinedload(Summary.document))
            .order_by(Summary.created_at.desc())
        )
        .scalars()
        .all()
    )
    return render_template("user/summaries.html", summaries=items)


@bp.route("/summary/<int:sid>/delete", methods=["POST"])
@login_required
@user_required
def summary_delete(sid):
    s = db.session.get(Summary, sid)
    if not s or s.user_id != current_user.id:
        abort(404)
    db.session.delete(s)
    db.session.commit()
    flash("Summary deleted.", "info")
    return redirect(url_for("user.summaries_history"))


@bp.route("/search")
@login_required
@user_required
def search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return render_template("user/search.html", q="", results=[], sum_results=[])
    like = f"%{q.lower()}%"
    pats = (
        db.session.execute(
            select(Patient)
            .where(
                Patient.user_id == current_user.id,
                or_(
                    func.lower(Patient.name).like(like),
                    func.lower(Patient.patient_id).like(like),
                    func.lower(func.coalesce(Patient.disease_hint, "")).like(like),
                ),
            )
            .order_by(Patient.name)
        )
        .scalars()
        .all()
    )
    sums = (
        db.session.execute(
            select(Summary)
            .where(
                Summary.user_id == current_user.id,
                or_(
                    func.lower(func.coalesce(Summary.edited_content, "")).like(like),
                    func.lower(func.coalesce(Summary.generated_json, "")).like(like),
                ),
            )
            .options(joinedload(Summary.patient))
            .order_by(Summary.created_at.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )
    return render_template("user/search.html", q=q, results=pats, sum_results=sums)
