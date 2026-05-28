from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from app import db
from app.decorators import admin_required
from app.models import (
    BrandInfo,
    Disease,
    EHRDocument,
    MedicalCategory,
    MedicalTerm,
    Medicine,
    Patient,
    Summary,
    User,
)
bp = Blueprint("admin", __name__)


@bp.context_processor
def _admin_kpi():
    if not current_user.is_authenticated or current_user.role != "admin":
        return {}
    n_user_accts = db.session.scalar(select(func.count(User.id)).where(User.role == "user")) or 0
    n_admins = db.session.scalar(select(func.count(User.id)).where(User.role == "admin")) or 0
    n_patients = db.session.scalar(select(func.count(Patient.id))) or 0
    n_ehr = db.session.scalar(select(func.count(EHRDocument.id))) or 0
    n_sum = db.session.scalar(select(func.count(Summary.id))) or 0
    n_blocked = db.session.scalar(select(func.count(User.id)).where(User.is_blocked.is_(True))) or 0
    n_cats = db.session.scalar(select(func.count(MedicalCategory.id))) or 0
    n_terms = db.session.scalar(select(func.count(MedicalTerm.id))) or 0
    return {
        "adm": {
            "users": n_user_accts,
            "admins": n_admins,
            "blocked": n_blocked,
            "patients": n_patients,
            "ehr": n_ehr,
            "summaries": n_sum,
            "categories": n_cats,
            "terms": n_terms,
        }
    }


def _now():
    return datetime.now(timezone.utc)


@bp.route("/")
@login_required
@admin_required
def dashboard():
    n_users = db.session.scalar(select(func.count(User.id)).where(User.role == "user")) or 0
    n_patients = db.session.scalar(select(func.count(Patient.id))) or 0
    n_ehr = db.session.scalar(select(func.count(EHRDocument.id))) or 0
    n_sum = db.session.scalar(select(func.count(Summary.id))) or 0
    active_users = (
        db.session.scalar(
            select(func.count(User.id)).where(User.role == "user", User.is_blocked.is_(False))
        )
        or 0
    )
    brand = db.session.query(BrandInfo).first()
    return render_template(
        "admin/dashboard.html",
        n_users=n_users,
        n_patients=n_patients,
        n_ehr=n_ehr,
        n_sum=n_sum,
        active_users=active_users,
        brand=brand,
    )


# --- Users ---
@bp.route("/users")
@login_required
@admin_required
def users_list():
    rows = db.session.execute(select(User).order_by(User.created_at.desc())).scalars().all()
    return render_template("admin/users.html", users=rows)


@bp.route("/users/new", methods=["GET", "POST"])
@login_required
@admin_required
def users_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        role = (request.form.get("role") or "user").strip()
        if role not in ("user", "admin"):
            role = "user"
        designation = (request.form.get("designation") or "").strip()[:80]
        if not name or not email or len(password) < 6:
            flash("Name, email, and password (min 6 chars) are required.", "error")
            return render_template("admin/user_form.html", u=None)
        if db.session.scalar(select(User).where(User.email == email)):
            flash("Email already registered.", "error")
            return render_template("admin/user_form.html", u=None)
        u = User(name=name, email=email, phone=phone, role=role, designation=designation or None)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        flash("User created.", "success")
        return redirect(url_for("admin.users_list"))
    return render_template("admin/user_form.html", u=None)


@bp.route("/users/<int:uid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def users_edit(uid):
    u = db.session.get(User, uid)
    if not u:
        abort(404)
    if request.method == "POST":
        u.name = (request.form.get("name") or u.name).strip()
        u.phone = (request.form.get("phone") or "").strip()
        ne = (request.form.get("email") or "").strip().lower()
        if ne and ne != u.email:
            if db.session.scalar(select(User).where(User.email == ne, User.id != u.id)):
                flash("Email in use.", "error")
                return render_template("admin/user_form.html", u=u)
            u.email = ne
        if u.id != current_user.id:
            role = (request.form.get("role") or u.role).strip()
            u.role = role if role in ("user", "admin") else u.role
        designation = (request.form.get("designation") or "").strip()
        u.designation = designation or None
        pw = request.form.get("password") or ""
        if len(pw) >= 6:
            u.set_password(pw)
        db.session.commit()
        flash("User updated.", "success")
        return redirect(url_for("admin.users_list"))
    return render_template("admin/user_form.html", u=u)


@bp.route("/users/<int:uid>/block", methods=["POST"])
@login_required
@admin_required
def users_block(uid):
    u = db.session.get(User, uid)
    if not u or u.id == current_user.id or u.role != "user":
        abort(404)
    u.is_blocked = True
    db.session.commit()
    flash("User blocked.", "info")
    return redirect(url_for("admin.users_list"))


@bp.route("/users/<int:uid>/unblock", methods=["POST"])
@login_required
@admin_required
def users_unblock(uid):
    u = db.session.get(User, uid)
    if not u or u.role != "user":
        abort(404)
    u.is_blocked = False
    db.session.commit()
    flash("User unblocked.", "success")
    return redirect(url_for("admin.users_list"))


@bp.route("/users/<int:uid>/delete", methods=["POST"])
@login_required
@admin_required
def users_delete(uid):
    u = db.session.get(User, uid)
    if not u or u.id == current_user.id or u.role != "user":
        abort(404)
    db.session.delete(u)
    db.session.commit()
    flash("User deleted.", "info")
    return redirect(url_for("admin.users_list"))


@bp.route("/users/<int:uid>/view", methods=["GET"])
@login_required
@admin_required
def users_view(uid):
    u = db.session.get(User, uid)
    if not u:
        abort(404)
    n_patients = (
        db.session.scalar(select(func.count(Patient.id)).where(Patient.user_id == u.id)) or 0
    )
    n_ehr = db.session.scalar(select(func.count(EHRDocument.id)).where(EHRDocument.user_id == u.id)) or 0
    n_sum = db.session.scalar(select(func.count(Summary.id)).where(Summary.user_id == u.id)) or 0
    patients = (
        db.session.execute(
            select(Patient).where(Patient.user_id == u.id).order_by(Patient.name).limit(50)
        )
        .scalars()
        .all()
    )
    recent_sums = (
        db.session.execute(
            select(Summary)
            .where(Summary.user_id == u.id)
            .options(joinedload(Summary.patient), joinedload(Summary.document))
            .order_by(Summary.created_at.desc())
            .limit(15)
        )
        .scalars()
        .all()
    )
    return render_template(
        "admin/user_detail.html",
        u=u,
        n_patients=n_patients,
        n_ehr=n_ehr,
        n_sum=n_sum,
        patients=patients,
        recent_sums=recent_sums,
    )


# --- Patients (all) ---
@bp.route("/patients")
@login_required
@admin_required
def patients_list():
    rows = (
        db.session.execute(
            select(Patient).options(joinedload(Patient.owner)).order_by(Patient.created_at.desc())
        )
        .scalars()
        .all()
    )
    pids = [p.id for p in rows]
    doc_counts = {}
    sum_counts = {}
    if pids:
        for pid, c in (
            db.session.execute(
                select(EHRDocument.patient_id, func.count(EHRDocument.id))
                .where(EHRDocument.patient_id.in_(pids))
                .group_by(EHRDocument.patient_id)
            )
            .all()
        ):
            doc_counts[pid] = c
        for pid, c in (
            db.session.execute(
                select(Summary.patient_id, func.count(Summary.id))
                .where(Summary.patient_id.in_(pids))
                .group_by(Summary.patient_id)
            )
            .all()
        ):
            sum_counts[pid] = c
    return render_template(
        "admin/patients.html",
        patients=rows,
        doc_counts=doc_counts,
        sum_counts=sum_counts,
    )


@bp.route("/patients/new", methods=["GET", "POST"])
@login_required
@admin_required
def patients_new():
    end_users = (
        db.session.execute(select(User).where(User.role == "user").order_by(User.name))
        .scalars()
        .all()
    )
    if request.method == "POST":
        uid = request.form.get("user_id", type=int)
        name = (request.form.get("name") or "").strip()
        patient_id = (request.form.get("patient_id") or "").strip()
        age = request.form.get("age")
        gender = (request.form.get("gender") or "").strip()
        contact = (request.form.get("contact") or "").strip()
        disease_hint = (request.form.get("disease_hint") or "").strip()
        owner = db.session.get(User, uid) if uid else None
        if not owner or owner.role != "user":
            flash("You must select an end-user account that will own this record.", "error")
            return render_template("admin/patient_form_new.html", users=end_users)
        if not name or not patient_id:
            flash("Name and patient ID are required.", "error")
            return render_template("admin/patient_form_new.html", users=end_users)
        if db.session.scalar(
            select(Patient).where(Patient.user_id == owner.id, Patient.patient_id == patient_id)
        ):
            flash("That user already has a patient with this patient ID.", "error")
            return render_template("admin/patient_form_new.html", users=end_users)
        p = Patient(
            user_id=owner.id,
            patient_id=patient_id,
            name=name,
            age=int(age) if age and str(age).isdigit() else None,
            gender=gender or None,
            contact=contact or None,
            disease_hint=disease_hint or None,
        )
        db.session.add(p)
        db.session.commit()
        flash("Patient record created for " + owner.email + ".", "success")
        return redirect(url_for("admin.patients_detail", pid=p.id))
    return render_template("admin/patient_form_new.html", users=end_users)


@bp.route("/patients/<int:pid>")
@login_required
@admin_required
def patients_detail(pid):
    p = db.session.get(Patient, pid)
    if not p:
        abort(404)
    owner = p.owner
    documents = (
        db.session.execute(
            select(EHRDocument)
            .where(EHRDocument.patient_id == pid)
            .options(joinedload(EHRDocument.uploader))
            .order_by(EHRDocument.uploaded_at.desc())
        )
        .scalars()
        .all()
    )
    summaries = (
        db.session.execute(
            select(Summary)
            .where(Summary.patient_id == pid)
            .order_by(Summary.created_at.desc())
        )
        .scalars()
        .all()
    )
    return render_template(
        "admin/patient_detail.html",
        patient=p,
        owner=owner,
        documents=documents,
        summaries=summaries,
    )


@bp.route("/patients/<int:pid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def patients_edit(pid):
    p = db.session.get(Patient, pid)
    if not p:
        abort(404)
    if request.method == "POST":
        p.name = (request.form.get("name") or p.name).strip()
        p.patient_id = (request.form.get("patient_id") or p.patient_id).strip()
        age = request.form.get("age")
        p.age = int(age) if age and str(age).isdigit() else None
        p.gender = (request.form.get("gender") or "").strip() or None
        p.contact = (request.form.get("contact") or "").strip() or None
        p.disease_hint = (request.form.get("disease_hint") or "").strip() or None
        db.session.commit()
        flash("Patient updated.", "success")
        return redirect(url_for("admin.patients_detail", pid=p.id))
    return render_template("admin/patient_form.html", patient=p)


@bp.route("/patients/<int:pid>/delete", methods=["POST"])
@login_required
@admin_required
def patients_delete(pid):
    p = db.session.get(Patient, pid)
    if not p:
        abort(404)
    db.session.delete(p)
    db.session.commit()
    flash("Patient record deleted.", "info")
    return redirect(url_for("admin.patients_list"))


# --- EHR documents ---
@bp.route("/ehr")
@login_required
@admin_required
def ehr_list():
    rows = (
        db.session.execute(
            select(EHRDocument)
            .options(joinedload(EHRDocument.patient), joinedload(EHRDocument.uploader))
            .order_by(EHRDocument.uploaded_at.desc())
        )
        .scalars()
        .all()
    )
    return render_template("admin/ehr_list.html", documents=rows)


@bp.route("/ehr/<int:eid>/delete", methods=["POST"])
@login_required
@admin_required
def ehr_delete(eid):
    doc = db.session.get(EHRDocument, eid)
    if not doc:
        abort(404)
    path = Path(doc.stored_path)
    db.session.delete(doc)
    db.session.commit()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    flash("EHR document removed.", "info")
    return redirect(url_for("admin.ehr_list"))


@bp.route("/ehr/<int:eid>")
@login_required
@admin_required
def ehr_view(eid):
    doc = db.session.execute(
        select(EHRDocument).where(EHRDocument.id == eid).options(
            joinedload(EHRDocument.patient), joinedload(EHRDocument.uploader)
        )
    ).scalar_one_or_none()
    if not doc:
        abort(404)
    raw = doc.extracted_text or ""
    n_chars = len(raw)
    n_words = len(raw.split()) if raw else 0
    n_sum = (
        db.session.scalar(
            select(func.count(Summary.id)).where(Summary.ehr_document_id == doc.id)
        )
        or 0
    )
    return render_template(
        "admin/ehr_view.html",
        doc=doc,
        n_chars=n_chars,
        n_words=n_words,
        n_chars_f=f"{n_chars:,}",
        n_words_f=f"{n_words:,}",
        n_summaries_for_doc=n_sum,
    )


# --- Summaries ---
@bp.route("/summaries")
@login_required
@admin_required
def summaries_list():
    rows = (
        db.session.execute(
            select(Summary)
            .options(joinedload(Summary.patient), joinedload(Summary.document), joinedload(Summary.user))
            .order_by(Summary.created_at.desc())
        )
        .scalars()
        .all()
    )
    return render_template("admin/summaries.html", summaries=rows)


@bp.route("/summaries/<int:sid>")
@login_required
@admin_required
def summary_view(sid):
    s = db.session.execute(
        select(Summary)
        .where(Summary.id == sid)
        .options(
            joinedload(Summary.document),
            joinedload(Summary.patient),
            joinedload(Summary.user),
        )
    ).scalar_one_or_none()
    if not s:
        abort(404)
    return render_template(
        "admin/summary_view.html",
        summary=s,
        document=s.document,
        patient=s.patient,
    )


@bp.route("/summaries/<int:sid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def summary_edit(sid):
    s = db.session.get(Summary, sid)
    if not s:
        abort(404)
    if request.method == "POST":
        s.edited_content = request.form.get("edited_content", "")
        s.is_saved = request.form.get("is_saved") == "1"
        s.updated_at = _now()
        db.session.commit()
        flash("Summary record updated.", "success")
        return redirect(url_for("admin.summary_view", sid=s.id))
    return render_template(
        "admin/summary_edit.html",
        summary=s,
        document=s.document,
        patient=s.patient,
    )


@bp.route("/summaries/<int:sid>/delete", methods=["POST"])
@login_required
@admin_required
def summary_delete(sid):
    s = db.session.get(Summary, sid)
    if not s:
        abort(404)
    db.session.delete(s)
    db.session.commit()
    flash("Summary deleted.", "info")
    return redirect(url_for("admin.summaries_list"))


# --- Medical categories ---
@bp.route("/categories", methods=["GET", "POST"])
@login_required
@admin_required
def categories():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        desc = (request.form.get("description") or "").strip()
        if name and not db.session.scalar(select(MedicalCategory).where(MedicalCategory.name == name)):
            db.session.add(MedicalCategory(name=name, description=desc or None))
            db.session.commit()
            flash("Category added.", "success")
        elif name:
            flash("Category already exists.", "error")
        return redirect(url_for("admin.categories"))
    rows = db.session.execute(select(MedicalCategory).order_by(MedicalCategory.name)).scalars().all()
    term_by_cat = {
        r[0]: r[1]
        for r in db.session.execute(
            select(MedicalTerm.category_id, func.count(MedicalTerm.id)).group_by(MedicalTerm.category_id)
        ).all()
    }
    return render_template("admin/categories.html", categories=rows, term_by_cat=term_by_cat)


@bp.route("/categories/<int:cid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def categories_edit(cid):
    c = db.session.get(MedicalCategory, cid)
    if not c:
        abort(404)
    if request.method == "POST":
        c.name = (request.form.get("name") or c.name).strip()
        c.description = (request.form.get("description") or "").strip() or None
        db.session.commit()
        flash("Category updated.", "success")
        return redirect(url_for("admin.categories"))
    return render_template("admin/category_edit.html", category=c)


@bp.route("/categories/<int:cid>/delete", methods=["POST"])
@login_required
@admin_required
def categories_delete(cid):
    c = db.session.get(MedicalCategory, cid)
    if not c:
        abort(404)
    db.session.delete(c)
    db.session.commit()
    flash("Category deleted.", "info")
    return redirect(url_for("admin.categories"))


# --- Terms ---
@bp.route("/terms", methods=["GET", "POST"])
@login_required
@admin_required
def terms():
    if request.method == "POST":
        term = (request.form.get("term") or "").strip()
        cat_id = request.form.get("category_id", type=int)
        notes = (request.form.get("notes") or "").strip()
        if term:
            t = MedicalTerm(term=term, category_id=cat_id or None, notes=notes or None)
            db.session.add(t)
            db.session.commit()
            flash("Term added.", "success")
        return redirect(url_for("admin.terms"))
    trows = (
        db.session.execute(
            select(MedicalTerm)
            .options(joinedload(MedicalTerm.category))
            .order_by(MedicalTerm.term)
            .limit(500)
        )
        .scalars()
        .all()
    )
    cats = db.session.execute(select(MedicalCategory).order_by(MedicalCategory.name)).scalars().all()
    return render_template("admin/terms.html", terms=trows, categories=cats)


@bp.route("/terms/<int:tid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def terms_edit(tid):
    t = db.session.get(MedicalTerm, tid)
    if not t:
        abort(404)
    cats = db.session.execute(select(MedicalCategory).order_by(MedicalCategory.name)).scalars().all()
    if request.method == "POST":
        t.term = (request.form.get("term") or t.term).strip()
        t.category_id = request.form.get("category_id", type=int) or None
        t.notes = (request.form.get("notes") or "").strip() or None
        db.session.commit()
        flash("Term updated.", "success")
        return redirect(url_for("admin.terms"))
    return render_template("admin/term_edit.html", term=t, categories=cats)


@bp.route("/terms/<int:tid>/delete", methods=["POST"])
@login_required
@admin_required
def terms_delete(tid):
    t = db.session.get(MedicalTerm, tid)
    if not t:
        abort(404)
    db.session.delete(t)
    db.session.commit()
    flash("Term deleted.", "info")
    return redirect(url_for("admin.terms"))


# --- Diseases ---
@bp.route("/diseases", methods=["GET", "POST"])
@login_required
@admin_required
def diseases():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        desc = (request.form.get("description") or "").strip()
        if name and not db.session.scalar(select(Disease).where(Disease.name == name)):
            db.session.add(Disease(name=name, description=desc or None))
            db.session.commit()
            flash("Disease added.", "success")
        elif name:
            flash("Disease name already exists.", "error")
        return redirect(url_for("admin.diseases"))
    rows = db.session.execute(select(Disease).order_by(Disease.name)).scalars().all()
    return render_template("admin/diseases.html", diseases=rows)


@bp.route("/diseases/<int:did>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def diseases_edit(did):
    d = db.session.get(Disease, did)
    if not d:
        abort(404)
    if request.method == "POST":
        d.name = (request.form.get("name") or d.name).strip()
        d.description = (request.form.get("description") or "").strip() or None
        db.session.commit()
        flash("Disease updated.", "success")
        return redirect(url_for("admin.diseases"))
    return render_template("admin/disease_edit.html", disease=d)


@bp.route("/diseases/<int:did>/delete", methods=["POST"])
@login_required
@admin_required
def diseases_delete(did):
    d = db.session.get(Disease, did)
    if not d:
        abort(404)
    db.session.delete(d)
    db.session.commit()
    flash("Disease removed.", "info")
    return redirect(url_for("admin.diseases"))


# --- Medicines ---
@bp.route("/medicines", methods=["GET", "POST"])
@login_required
@admin_required
def medicines():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        dose = (request.form.get("dosage_info") or "").strip()
        usage = (request.form.get("usage_instructions") or "").strip()
        if name:
            db.session.add(
                Medicine(name=name, dosage_info=dose or None, usage_instructions=usage or None)
            )
            db.session.commit()
            flash("Medicine added.", "success")
        return redirect(url_for("admin.medicines"))
    rows = db.session.execute(select(Medicine).order_by(Medicine.name)).scalars().all()
    return render_template("admin/medicines.html", medicines=rows)


@bp.route("/medicines/<int:mid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def medicines_edit(mid):
    m = db.session.get(Medicine, mid)
    if not m:
        abort(404)
    if request.method == "POST":
        m.name = (request.form.get("name") or m.name).strip()
        m.dosage_info = (request.form.get("dosage_info") or "").strip() or None
        m.usage_instructions = (request.form.get("usage_instructions") or "").strip() or None
        db.session.commit()
        flash("Medicine updated.", "success")
        return redirect(url_for("admin.medicines"))
    return render_template("admin/medicine_edit.html", medicine=m)


@bp.route("/medicines/<int:mid>/delete", methods=["POST"])
@login_required
@admin_required
def medicines_delete(mid):
    m = db.session.get(Medicine, mid)
    if not m:
        abort(404)
    db.session.delete(m)
    db.session.commit()
    flash("Medicine removed.", "info")
    return redirect(url_for("admin.medicines"))


# --- Brand / system info ---
@bp.route("/brand", methods=["GET", "POST"])
@login_required
@admin_required
def brand():
    b = db.session.query(BrandInfo).first()
    if not b:
        b = BrandInfo(project_name="EHR")
        db.session.add(b)
        db.session.commit()
    if request.method == "POST":
        b.project_name = (request.form.get("project_name") or b.project_name).strip()
        b.contact_email = (request.form.get("contact_email") or "").strip() or None
        b.address = (request.form.get("address") or "").strip() or None
        b.system_description = (request.form.get("system_description") or "").strip() or None
        f = request.files.get("logo")
        if f and f.filename:
            fn2 = secure_filename(f.filename) or "logo.png"
            dest = current_app.config["UPLOAD_FOLDER"] / "branding" / fn2
            dest.parent.mkdir(parents=True, exist_ok=True)
            f.save(str(dest))
            b.logo_path = str(dest)
        db.session.commit()
        flash("System information updated.", "success")
        return redirect(url_for("admin.brand"))
    return render_template("admin/brand.html", brand=b)


@bp.route("/reports")
@login_required
@admin_required
def reports():
    n_users = db.session.scalar(select(func.count(User.id)).where(User.role == "user")) or 0
    active = (
        db.session.scalar(
            select(func.count(User.id)).where(User.role == "user", User.is_blocked.is_(False))
        )
        or 0
    )
    blocked = db.session.scalar(select(func.count(User.id)).where(User.is_blocked.is_(True))) or 0
    n_patients = db.session.scalar(select(func.count(Patient.id))) or 0
    n_ehr = db.session.scalar(select(func.count(EHRDocument.id))) or 0
    n_sum = db.session.scalar(select(func.count(Summary.id))) or 0
    return render_template(
        "admin/reports.html",
        n_users=n_users,
        active_users=active,
        blocked_users=blocked,
        n_patients=n_patients,
        n_ehr=n_ehr,
        n_sum=n_sum,
    )


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
@admin_required
def change_password():
    if request.method == "POST":
        cur = request.form.get("current") or ""
        pw = request.form.get("password") or ""
        pw2 = request.form.get("password2") or ""
        u = db.session.get(User, current_user.id)
        if not u.check_password(cur):
            flash("Current password is incorrect.", "error")
            return render_template("admin/change_password.html")
        if len(pw) < 6 or pw != pw2:
            flash("New password must match and be at least 6 characters.", "error")
            return render_template("admin/change_password.html")
        u.set_password(pw)
        db.session.commit()
        flash("Password updated.", "success")
        return redirect(url_for("admin.dashboard"))
    return render_template("admin/change_password.html")
