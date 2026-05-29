# MedSynapse EHR — Automated EHR Summarization Platform

A full-stack **Flask** web application for **uploading electronic health records (EHR)**, **extracting text** from PDF or plain text, and **generating structured clinical summaries** with eight standard sections. It includes **role-based end-user and administrator consoles**, optional **Hugging Face (Flan-T5) fine-tuning** for better accuracy, and a **heuristic fallback** that works without a GPU.

> **Disclaimer:** This is a software demonstration. Do not use for real patient care or Protected Health Information (PHI) without proper legal review, security controls, and compliance (e.g. HIPAA).

---

## Table of contents

- [Features — end users](#features--end-users)
- [Features — administrators](#features--administrators)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation and how to run](#installation-and-how-to-run)
- [Default credentials (after seed)](#default-credentials-after-seed)
- [Configuration (`.env`)](#configuration-env)
- [How to train a summarization model](#how-to-train-a-summarization-model)
- [Summarization modes](#summarization-modes)
- [Troubleshooting](#troubleshooting)

---

## Features — end users

| Area | Capabilities |
|------|----------------|
| **Account** | Register with name, email, password, phone, and **role/function** (designation). Duplicate emails rejected. Passwords stored hashed. |
| **Sign in** | Email and password. Blocked users cannot sign in. Admins are redirected to the admin dashboard. |
| **Dashboard** | Totals, recent summaries, workflow guidance, quick actions. |
| **Patients** | Add, list, **edit**, **delete** patients (external ID, name, age, gender, contact, condition hint). |
| **Upload EHR** | Assign **.pdf** or **.txt** to a patient (size limit: 16 MB). |
| **Text extraction** | PDF via `pypdf`; text files read as UTF-8. View and **re-extract** on the EHR detail page. |
| **Generate summary** | Produces an **8-section** structured output: patient information, symptoms, diagnosis, medicines, lab reports, treatment plan, doctor notes, follow-up. |
| **View / compare** | Side-by-side **original extracted text** vs **generated sections** and an **editable** narrative. |
| **Edit & save** | Update draft or **save final** summary; **download PDF** of the report. |
| **History** | List summaries: open, edit, **PDF download**, **delete**. |
| **Search** | Search by patient name, ID, condition hint, or text in summary fields. |
| **Profile** | Update name, phone, email, and password. |
| **Logout** | Session end. |

**User app URLs** (after login) are under `/app/…` (e.g. dashboard at `/app/dashboard`).

---

## Features — administrators

| Area | Capabilities |
|------|----------------|
| **Dashboard** | System-wide metrics (users, patients, EHR files, summaries, etc.). |
| **Users (CRUD+)** | **Create** user accounts; **view** user detail with activity; **edit**; **block/unblock** end users; **delete** end users. Admins and self are protected from destructive rules where applicable. |
| **Patients (CRUD+)** | **List** all patients; **create** a patient and assign to an end-user owner; **view** detail (owner, EHR list, summaries); **edit**; **delete**. |
| **EHR documents** | **List**; **read** (full text + metadata); **delete** files and remove stored file when possible. |
| **Summaries (CRUD+)** | **List**; **read** (original + edited body); **edit** admin narrative and saved flag; **delete**. |
| **Medical categories** | **Create**, **read**, **update**, **delete**; term counts per category. |
| **Medical terms** | **CRUD** with optional link to a category. |
| **Diseases** | **CRUD** (unique names). |
| **Medicines** | **CRUD** (name, dosage, usage text). |
| **Brand / system** | **Update** product name, contact email, address, system description, **logo** upload. |
| **Reports** | Aggregate read-only stats (active/blocked users, patients, EHR, summaries, taxonomy). |
| **Change password** | Update the signed-in **admin** password. |
| **Logout** | End session. |

**Admin URLs** are under `/admin/…` (e.g. `/admin/`, `/admin/users`).

---

## Tech stack

- **Backend:** Python 3, **Flask 3**, **Flask-Login**, **Flask-WTF (CSRF)**, **Flask-SQLAlchemy**, **SQLite** (configurable `DATABASE_URL`).
- **EHR & PDF:** `pypdf` (extraction), `fpdf2` (summary PDF download).
- **HTML/CSS:** Jinja2 templates, custom professional UI; separate styling for user and admin areas.
- **Optional ML (training/inference):** `torch`, `transformers`, `datasets`, `accelerate` — see `requirements-ml.txt`.

---

## Project structure (high level)

```text
├── app/                    # Application package
│   ├── routes/            # main, auth, user (portal), admin (portal)
│   ├── services/        # PDF extraction, summarizer, hf_summarizer, ehr_prompt, PDF export
│   ├── models.py
│   └── ...
├── config.py
├── run.py                 # `python run.py` — dev server
├── requirements.txt
├── requirements-ml.txt  # optional ML / training
├── seed_data.py          # default demo data + credentials
├── training/              # export JSONL, fine-tune Flan-T5, training/README.md
├── templates/             # Jinja2 (landing, user, admin)
├── static/                # CSS, assets
└── uploads/                # user uploads, branding (created at runtime)
```

---

## Prerequisites

- **Python 3.10+** (3.12 tested).
- **pip** for dependencies.
- For **model training** or **HF inference:** enough disk for PyTorch and models; **GPU** strongly recommended for training.

---

## Installation and how to run

1. **Clone or copy** the project and open a terminal in the project root.

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   # Linux/macOS: source .venv/bin/activate
   ```

3. **Install the web app:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Optional — copy environment file** and edit as needed (see [Configuration](#configuration-env)):
   ```bash
   copy env.example .env
   # Linux/macOS: cp env.example .env
   ```

5. **Seed the database** (first-time demo data and default accounts). Safe to re-run: it **skips** if the admin email already exists.
   ```bash
   python seed_data.py
   ```

6. **Start the server:**
   ```bash
   python run.py
   ```
   Open a browser: **http://127.0.0.1:5000/**

- **Landing / public site:** `/`
- **User registration / login:** `/auth/register`, `/auth/login`
- **User workspace (after login as end user):** `/app/dashboard`
- **Admin (after login as admin):** `/admin/`

To **re-seed from scratch**, delete the SQLite file `ehr_summarizer.db` (and optionally the `uploads/` folder) in the project root, then run `python seed_data.py` again.

---

## Default credentials (after seed)

These are created only when `seed_data.py` runs and **no** user with `admin@medsynapse.local` exists yet.

| Role | Email | Password |
|------|--------|-------------|
| **Administrator** | `admin@medsynapse.local` | `Admin@123` |
| **End user (sample)** | `aisha.morgan@hospital.example` | `User@123` |
| **End user (sample)** | `jordan.lee@hospital.example` | `User@123` |

Change all passwords in production. Register additional end users from `/auth/register` (they cannot self-register as admin; admins are created via admin UI or database).

---

## Configuration (`.env`)

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Flask session secret. Set a long random value in production. |
| `DATABASE_URL` | Optional. Defaults to `sqlite:///ehr_summarizer.db` in the project root. |
| `EHR_SUMMARY_MODE` | `heuristic` (default) or `hf` (Hugging Face model from disk). |
| `EHR_HF_MODEL_DIR` | Path to the saved fine-tuned model directory. Required if `EHR_SUMMARY_MODE=hf`. |
| `EHR_HF_MAX_INPUT_CHARS` | Truncate long EHR for HF inference (default `6000`). |

See `env.example` for a template.

---

## How to train a summarization model

Training is **optional** and uses **separate** dependencies.

1. **Install ML requirements:**
   ```bash
   pip install -r requirements-ml.txt
   ```
   Install a **PyTorch** build suitable for your OS/GPU if needed: https://pytorch.org/

2. **Export (input, target) pairs** from the app database (uses saved `generated_json` and extracted EHR text):
   ```bash
   python training/export_training_data.py --out training/data/ehr_train.jsonl
   ```
   - Optional: `--only-saved` to restrict to summaries marked “saved” by users.  
   - You need a **sufficient number** of quality examples; dozens to hundreds+ pairs is typical for meaningful improvement.

3. **Fine-tune Flan-T5** (default base model: `google/flan-t5-base`):
   ```bash
   python training/finetune_flan_t5.py --train_file training/data/ehr_train.jsonl --output_dir training/model_ehr
   ```
   Quick CPU smoke test (small, short run):
   ```bash
   python training/finetune_flan_t5.py --train_file training/data/ehr_train.jsonl --output_dir training/model_ehr --base_model google/flan-t5-small --epochs 1 --batch_size 1
   ```

4. **Enable the model in the app** (`.env`):
   ```env
   EHR_SUMMARY_MODE=hf
   EHR_HF_MODEL_DIR=training/model_ehr
   EHR_HF_MAX_INPUT_CHARS=6000
   ```
   Restart the Flask app. If loading fails, the app **logs a warning** and uses **heuristic** summarization.

**More detail:** [training/README.md](training/README.md) (prompt format, JSON targets, context limits, optional improvements like LongT5 or LoRA).

---

## Summarization modes

1. **Heuristic (default):** No ML dependencies. Section sentences are chosen with keyword-style rules (fast, always available).
2. **HF (fine-tuned):** Same JSON section schema, produced by a **Flan-T5** checkpoint you trained. Requires `requirements-ml.txt` and a valid `EHR_HF_MODEL_DIR`.

---

## Troubleshooting

| Issue | Suggestion |
|--------|------------|
| `csrf_token` / form errors | Ensure cookies are enabled; do not open the app in mixed file:// and http without CSRF config changes. |
| `You have both PyFPDF & fpdf2` | The **export script** silences this. To remove it globally: `pip uninstall fpdf` (legacy PyFPDF). **Do not** uninstall `pypdf` — the app uses it to read PDFs. Keep `fpdf2` for PDF report generation. |
| Seed “Skipping” | Admin already present; delete `ehr_summarizer.db` to reseed, or use another DB URL. |
| HF model OOM or slow | Use `flan-t5-small`, reduce batch size in `finetune_flan_t5.py`, or train on a GPU. |
| Long EHR cut off | Lower/increase `EHR_HF_MAX_INPUT_CHARS` or use a long-context model strategy (see `training/README.md`). |

---

## License

This project is intended for educational and research purposes.
Licensed under the MIT License.
