"""
Seed the database with sample users, clinical vocabulary, patients, and EHR content.
Run from project root: python seed_data.py
"""
import warnings
from pathlib import Path

# Quiet legacy "fpdf" + fpdf2 namespace warning when the full app is imported
warnings.filterwarnings("ignore", message="You have both PyFPDF", category=UserWarning)

from app import create_app, db
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
from app.services.extraction import extract_text_from_file
from app.services.summarizer import json_dumps_sections, sections_to_display_text, summarize_ehr_text


def run():
    app = create_app()
    with app.app_context():
        if db.session.query(User).filter_by(email="admin@medsynapse.local").first():
            print("Database already contains seed admin (admin@medsynapse.local). Skipping.")
            return

        # Brand
        brand = db.session.query(BrandInfo).first()
        if brand:
            brand.project_name = "MedSynapse EHR Platform"
            brand.contact_email = "clinical-ops@medsynapse.example"
            brand.address = "500 Innovation Drive, Cambridge, MA 02139"
            brand.system_description = (
                "Enterprise-grade EHR summarization with domain-specific vocabulary management."
            )
        else:
            db.session.add(
                BrandInfo(
                    project_name="MedSynapse EHR Platform",
                    contact_email="clinical-ops@medsynapse.example",
                    address="500 Innovation Drive, Cambridge, MA 02139",
                    system_description="Enterprise-grade EHR summarization with domain-specific vocabulary management.",
                )
            )

        # Users
        admin = User(
            name="System Administrator",
            email="admin@medsynapse.local",
            phone="+1-617-555-0100",
            role="admin",
            designation="IT / compliance",
        )
        admin.set_password("Admin@123")
        u1 = User(
            name="Dr. Aisha Morgan",
            email="aisha.morgan@hospital.example",
            phone="+1-555-201-4000",
            role="user",
            designation="physician",
        )
        u1.set_password("User@123")
        u2 = User(
            name="Jordan Lee, RN",
            email="jordan.lee@hospital.example",
            role="user",
            designation="nurse",
        )
        u2.set_password("User@123")
        db.session.add_all([admin, u1, u2])
        db.session.flush()

        # 8 medical categories
        cat_rows = [
            ("Cardiology", "Heart and vascular system"),
            ("Neurology", "Brain, spine, and nervous system"),
            ("Endocrinology", "Hormones and metabolism"),
            ("Pulmonology", "Lung and breathing conditions"),
            ("Nephrology", "Kidney function and disease"),
            ("Gastroenterology", "Digestive system"),
            ("General medicine", "Primary / broad internal medicine"),
            ("Emergency medicine", "Acute triage and stabilization"),
        ]
        categories = [MedicalCategory(name=n, description=d) for n, d in cat_rows]
        db.session.add_all(categories)
        db.session.flush()
        c_by = {c.name: c for c in categories}

        # 8 medical terms
        terms = [
            ("myocardial infarction", "Cardiology", "Ischemic heart injury"),
            ("hemoglobin A1c", "Endocrinology", "3-month glucose control"),
            ("TIA", "Neurology", "Transient ischemic attack"),
            ("SpO2", "Pulmonology", "Oxygen saturation"),
            ("eGFR", "Nephrology", "Glomerular filtration rate"),
            ("CRP", "General medicine", "Inflammation marker"),
            ("troponin", "Cardiology", "Cardiac injury marker"),
            ("Hb", "General medicine", "Hemoglobin level"),
        ]
        for t, cname, note in terms:
            db.session.add(
                MedicalTerm(term=t, category_id=c_by[cname].id, notes=note)
            )

        # 8 diseases
        diseases = [
            ("Type 2 diabetes mellitus", "Chronic hyperglycemia with insulin resistance."),
            ("Hypertension", "Elevated blood pressure requiring long-term control."),
            ("Atrial fibrillation", "Irregular supraventricular arrhythmia."),
            ("COPD", "Chronic airflow limitation, often from smoking exposure."),
            ("Chronic kidney disease", "Progressive loss of kidney function."),
            ("Hypothyroidism", "Thyroid hormone deficiency, often Hashimoto-related."),
            ("GERD", "Gastroesophageal reflux disease with heartburn and erosion risk."),
            ("Migraine", "Episodic unilateral headaches with photophobia."),
        ]
        for n, d in diseases:
            db.session.add(Disease(name=n, description=d))

        # 8 medicines
        meds = [
            ("Metformin", "500-1000 mg BID with meals", "Oral; monitor renal function; hold before contrast if needed."),
            ("Lisinopril", "10-40 mg daily", "ACE inhibitor; check potassium and creatinine."),
            ("Atorvastatin", "20-40 mg QHS", "Statin; monitor LFTs and muscle symptoms."),
            ("Apixaban", "5 mg BID (adjust for renal/weight factors)", "Anticoagulant; assess bleeding risk."),
            ("Levothyroxine", "1.6 mcg/kg lean body mass daily Fasting", "Thyroid replacement; TSH-guided titration."),
            ("Albuterol", "2 puffs every 4-6 h PRN", "SABA; tremor and tachycardia possible."),
            ("Omeprazole", "20-40 mg daily before breakfast", "PPI; long-term B12 and bone risk awareness."),
            ("Sumatriptan", "50-100 mg at migraine onset, max 200 mg/24h", "Triptan; contraindicated in some vascular disease."),
        ]
        for n, d, u in meds:
            db.session.add(Medicine(name=n, dosage_info=d, usage_instructions=u))

        # Patients for u1
        p1 = Patient(
            user_id=u1.id,
            patient_id="MRN-10042",
            name="Elena Vargas",
            age=54,
            gender="F",
            contact="+1-555-900-1201",
            disease_hint="Type 2 diabetes",
        )
        p2 = Patient(
            user_id=u1.id,
            patient_id="MRN-10088",
            name="David Chen",
            age=68,
            gender="M",
            contact="+1-555-900-1202",
            disease_hint="Atrial fibrillation",
        )
        p3 = Patient(
            user_id=u2.id,
            patient_id="MRN-10102",
            name="Maria Santos",
            age=33,
            gender="F",
            contact="+1-555-900-1203",
            disease_hint="Migraine",
        )
        db.session.add_all([p1, p2, p3])
        db.session.flush()

        # Sample EHR text (txt files)
        ehr1_text = """
ELENA VARGAS, 54F — outpatient note — 2026-01-10
Chief complaint: increased thirst and fatigue x 6 weeks.
History: Type 2 diabetes diagnosed 4 years ago. Home glucose readings 180-220 fasting.
Meds: metformin 1000mg BID, lisinopril 20mg daily, atorvastatin 40mg QHS.
Labs: HbA1c 8.1%, eGFR 78, LDL 112, CRP 3.1 mg/L.
Impression: suboptimal glycemic control; hypertension and dyslipidemia.
Plan: continue metformin, reinforce diet/exercise, start structured glucose monitoring, repeat A1c in 3 months.
Follow-up: return in 6 weeks, sooner if hyperglycemia symptoms worsen.
        """.strip()

        ehr2_text = """
DAVID CHEN, 68M — cardiology — 2026-02-02
Presents with palpitations. History: hypertension, atrial fibrillation, prior TIA 2024.
Meds: apixaban 5mg BID, lisinopril, atorvastatin.
EKG: atrial fibrillation, rapid ventricular response, rate 118.
Impression: symptomatic atrial fibrillation.
Plan: rate control, continue anticoagulation, consider rhythm strategy per shared decision.
Discharge: monitor bleeding, return if syncope, chest pain, or stroke signs.
        """.strip()

        up = app.config["UPLOAD_FOLDER"] / f"u{u1.id}"
        up.mkdir(parents=True, exist_ok=True)
        path1 = up / f"p{p1.id}_ehr1.txt"
        path1.write_text(ehr1_text, encoding="utf-8")
        path2 = up / f"p{p2.id}_ehr1.txt"
        path2.write_text(ehr2_text, encoding="utf-8")

        d1 = EHRDocument(
            patient_id=p1.id,
            user_id=u1.id,
            original_filename="ehr_vargas_clinic.txt",
            stored_path=str(path1),
            file_type="txt",
            extracted_text=extract_text_from_file(path1, "txt"),
        )
        d2 = EHRDocument(
            patient_id=p2.id,
            user_id=u1.id,
            original_filename="ehr_chen_cardio.txt",
            stored_path=str(path2),
            file_type="txt",
            extracted_text=extract_text_from_file(path2, "txt"),
        )
        db.session.add_all([d1, d2])
        db.session.flush()

        tlist = [x.term for x in db.session.query(MedicalTerm).limit(200).all()]
        sec1 = summarize_ehr_text(d1.extracted_text, tlist)
        s1 = Summary(
            ehr_document_id=d1.id,
            patient_id=p1.id,
            user_id=u1.id,
            generated_json=json_dumps_sections(sec1),
            edited_content=sections_to_display_text(sec1),
            is_saved=True,
        )
        db.session.add(s1)

        db.session.commit()
        print("Seed complete.")
        print("  Admin: admin@medsynapse.local / Admin@123")
        print("  User:  aisha.morgan@hospital.example / User@123")
        print("  User:  jordan.lee@hospital.example / User@123")


if __name__ == "__main__":
    run()
