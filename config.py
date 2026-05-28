import os
from pathlib import Path


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-change-me-in-production-ehr-2026"
    BASE_DIR = Path(__file__).resolve().parent
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        "sqlite:///" + str(BASE_DIR / "ehr_summarizer.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {"txt", "pdf"}
    WTF_CSRF_ENABLED = True
    # EHR summarization: "heuristic" (built-in) or "hf" (fine-tuned Hugging Face model)
    EHR_SUMMARY_MODE = os.environ.get("EHR_SUMMARY_MODE", "heuristic")
    EHR_HF_MODEL_DIR = os.environ.get("EHR_HF_MODEL_DIR")  # path to fine-tuned checkpoint dir
    EHR_HF_MAX_INPUT_CHARS = int(os.environ.get("EHR_HF_MAX_INPUT_CHARS", "6000"))
