"""
Shared prompt prefix for training and HF inference (must stay identical).
"""

EHR_JSON_INSTRUCTION_PREFIX = (
    "Convert the clinical note into a single JSON object only. "
    "Keys exactly: patient_information, symptoms, diagnosis, medicines, lab_reports, "
    "treatment_plan, doctor_notes, follow_up_instructions. "
    "Each value is a concise English string. No markdown, no code fence, only raw JSON.\n\n"
    "Clinical note:\n"
)


def build_model_input(extracted_note: str) -> str:
    return EHR_JSON_INSTRUCTION_PREFIX + (extracted_note or "")
