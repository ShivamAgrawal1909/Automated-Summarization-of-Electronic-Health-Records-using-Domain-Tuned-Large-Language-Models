import os
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Optional

from fpdf import FPDF

from app.services.summarizer import LABELS, SECTION_KEYS


def _pdf_txt(s: str) -> str:
    t = (s or "").replace("\r", "")
    for a, b in ("\u2014", "-"), ("\u2013", "-"), ("\u2009", " "):
        t = t.replace(a, b)
    return t.encode("latin-1", "replace").decode("latin-1")


def build_summary_pdf(
    title: str,
    patient_line: str,
    content_text: str,
    sections_dict: Optional[dict] = None,
) -> BytesIO:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(14, 14, 14)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 11)
    pdf.multi_cell(0, 7, "EHR Summary Report", align="C")
    pdf.ln(3)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, _pdf_txt(title))
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, _pdf_txt(patient_line))
    pdf.ln(4)

    if sections_dict:
        for key in SECTION_KEYS:
            label = LABELS.get(key, key)
            body = _pdf_txt(sections_dict.get(key) or "")
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "B", 11)
            pdf.multi_cell(0, 7, _pdf_txt(label))
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5, body or "-")
            pdf.ln(2)
    else:
        pdf.set_font("Helvetica", "", 10)
        for line in content_text.split("\n"):
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 5, _pdf_txt(line))

    fd, tmp = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        pdf.output(tmp)
        data = Path(tmp).read_bytes()
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    return BytesIO(data)


def save_logo_bytes(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
