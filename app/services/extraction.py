from pathlib import Path

from pypdf import PdfReader


def extract_text_from_file(path: Path, file_type: str) -> str:
    if file_type == "txt":
        return path.read_text(encoding="utf-8", errors="replace")
    if file_type == "pdf":
        reader = PdfReader(str(path))
        parts = []
        for page in reader.pages:
            t = page.extract_text() or ""
            parts.append(t)
        return "\n\n".join(parts).strip()
    raise ValueError("Unsupported file type")
