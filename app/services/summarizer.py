"""
Domain-style structured summarization from raw EHR text.
- Default: keyword/sentence heuristics (no GPU).
- Optional: fine-tuned seq2seq (Flan-T5) via EHR_SUMMARY_MODE=hf and EHR_HF_MODEL_DIR.
"""
import json
import logging
import os
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Section keys aligned with UI
SECTION_KEYS = [
    "patient_information",
    "symptoms",
    "diagnosis",
    "medicines",
    "lab_reports",
    "treatment_plan",
    "doctor_notes",
    "follow_up_instructions",
]

LABELS = {
    "patient_information": "Patient information",
    "symptoms": "Symptoms",
    "diagnosis": "Diagnosis",
    "medicines": "Medicines",
    "lab_reports": "Lab reports",
    "treatment_plan": "Treatment plan",
    "doctor_notes": "Doctor notes",
    "follow_up_instructions": "Follow-up instructions",
}


def _split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _pick_sentences(text: str, keywords: tuple, limit: int = 6) -> str:
    sents = _split_sentences(text)
    lower_kw = [k.lower() for k in keywords]
    scored = []
    for s in sents:
        sl = s.lower()
        score = sum(1 for k in lower_kw if k in sl)
        if score:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    picked = [s for _, s in scored[:limit]]
    if not picked and sents:
        picked = sents[: min(4, len(sents))]
    return " ".join(picked)


def _heuristic_summarize(raw_text: str, domain_terms: Optional[List[str]] = None) -> Dict[str, str]:
    """Return structured section dict using rules (no ML)."""
    raw = raw_text or ""
    terms = [t.lower() for t in (domain_terms or [])]
    _ = terms  # reserved for future weighting

    # Patient block: first ~400 chars or lines with name/age
    first_lines = "\n".join(raw.splitlines()[:12])
    patient_info = first_lines[:800].strip() or "Not explicitly stated in the record."

    symptoms = _pick_sentences(
        raw,
        (
            "symptom",
            "pain",
            "fever",
            "cough",
            "nausea",
            "fatigue",
            "shortness",
            "complaint",
            "presents with",
            "chief",
        ),
    )
    diagnosis = _pick_sentences(
        raw,
        (
            "diagnosis",
            "impression",
            "assessment",
            "icd",
            "condition",
            "found to have",
            "rule out",
            "differential",
        ),
    )
    medicines = _pick_sentences(
        raw,
        (
            "medication",
            "prescribed",
            "mg",
            "tablet",
            "capsule",
            "insulin",
            "antibiotic",
            "dose",
            "daily",
        ),
    )
    labs = _pick_sentences(
        raw,
        (
            "lab",
            "hemoglobin",
            "wbc",
            "glucose",
            "creatinine",
            "test",
            "result",
            "cbc",
            "cmp",
            "a1c",
            "lipid",
            "urinalysis",
        ),
    )
    treatment = _pick_sentences(
        raw,
        (
            "treatment",
            "plan",
            "procedure",
            "surgery",
            "therapy",
            "rehab",
            "intervention",
            "started on",
        ),
    )
    notes = _pick_sentences(
        raw,
        (
            "note",
            "physician",
            "provider",
            "attending",
            "resident",
            "history of present",
            "review of systems",
        ),
    )
    follow = _pick_sentences(
        raw,
        (
            "follow",
            "return",
            "next visit",
            "appointment",
            "discharge instructions",
            "when to seek",
        ),
    )

    out = {
        "patient_information": patient_info or "—",
        "symptoms": symptoms or "—",
        "diagnosis": diagnosis or "—",
        "medicines": medicines or "—",
        "lab_reports": labs or "—",
        "treatment_plan": treatment or "—",
        "doctor_notes": notes or "—",
        "follow_up_instructions": follow or "—",
    }
    return out


def summarize_ehr_text(raw_text: str, domain_terms: Optional[List[str]] = None) -> Dict[str, str]:
    """
    Main entry: heuristic, or Hugging Face model if EHR_SUMMARY_MODE=hf and model path is set.
    Falls back to heuristics if the model fails to load or raises.
    """
    mode = (os.environ.get("EHR_SUMMARY_MODE") or "heuristic").strip().lower()
    if mode == "hf":
        try:
            from app.services.hf_summarizer import summarize_ehr_text_hf

            return summarize_ehr_text_hf(raw_text, domain_terms)
        except Exception as e:
            logger.warning("HF summarizer failed (%s); using heuristics.", e)
    return _heuristic_summarize(raw_text, domain_terms)


def sections_to_display_text(sections: Dict[str, str]) -> str:
    lines = []
    for key in SECTION_KEYS:
        title = LABELS.get(key, key)
        body = sections.get(key, "—")
        lines.append(f"## {title}\n{body}\n")
    return "\n".join(lines)


def json_dumps_sections(sections: Dict[str, str]) -> str:
    return json.dumps(sections, ensure_ascii=False)


def json_loads_sections(s: Optional[str]) -> Dict[str, str]:
    if not s:
        return {k: "" for k in SECTION_KEYS}
    try:
        data = json.loads(s)
        return {k: data.get(k, "") for k in SECTION_KEYS}
    except json.JSONDecodeError:
        return {k: "" for k in SECTION_KEYS}
