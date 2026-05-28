from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(40), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # system: user | admin
    designation = db.Column(
        db.String(80), nullable=True
    )  # e.g. physician, nurse, researcher (from registration)
    is_blocked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    patients = db.relationship("Patient", backref="owner", lazy="dynamic")
    documents = db.relationship("EHRDocument", backref="uploader", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Patient(db.Model):
    __tablename__ = "patients"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    patient_id = db.Column(db.String(64), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    contact = db.Column(db.String(80), nullable=True)
    disease_hint = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    documents = db.relationship("EHRDocument", backref="patient", lazy="dynamic", cascade="all, delete-orphan")
    summaries = db.relationship("Summary", backref="patient", lazy="dynamic", cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint("user_id", "patient_id", name="uq_user_patient_ref"),)


class EHRDocument(db.Model):
    __tablename__ = "ehr_documents"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(512), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)  # txt | pdf
    extracted_text = db.Column(db.Text, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=utcnow)

    summaries = db.relationship("Summary", backref="document", lazy="dynamic", cascade="all, delete-orphan")


class Summary(db.Model):
    __tablename__ = "summaries"

    id = db.Column(db.Integer, primary_key=True)
    ehr_document_id = db.Column(db.Integer, db.ForeignKey("ehr_documents.id"), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", backref=db.backref("summaries", lazy="dynamic"))
    # JSON string of section -> text for generated
    generated_json = db.Column(db.Text, nullable=True)
    # Editable full text (markdown-like sections) or plain
    edited_content = db.Column(db.Text, nullable=True)
    is_saved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)


class MedicalCategory(db.Model):
    __tablename__ = "medical_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)


class MedicalTerm(db.Model):
    __tablename__ = "medical_terms"

    id = db.Column(db.Integer, primary_key=True)
    term = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("medical_categories.id"), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    category = db.relationship("MedicalCategory", backref="terms")


class Disease(db.Model):
    __tablename__ = "diseases"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)


class Medicine(db.Model):
    __tablename__ = "medicines"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    dosage_info = db.Column(db.String(300), nullable=True)
    usage_instructions = db.Column(db.Text, nullable=True)


class BrandInfo(db.Model):
    __tablename__ = "brand_info"

    id = db.Column(db.Integer, primary_key=True)
    project_name = db.Column(db.String(200), nullable=False)
    logo_path = db.Column(db.String(512), nullable=True)
    contact_email = db.Column(db.String(200), nullable=True)
    address = db.Column(db.Text, nullable=True)
    system_description = db.Column(db.Text, nullable=True)
