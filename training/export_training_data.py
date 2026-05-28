"""
Export (input, target) JSONL pairs for fine-tuning from the app database.

Usage (from project root):
  python training/export_training_data.py --out training/data/ehr_train.jsonl

Each line: {"input": str, "target": str} where target is JSON with 8 EHR section keys.
Requires saved summaries with non-empty generated_json and linked EHR with extracted text.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Loading the app imports fpdf2; a legacy "fpdf" (PyFPDF) install prints a noisy warning.
warnings.filterwarnings("ignore", message="You have both PyFPDF", category=UserWarning)

from app import create_app, db
from app.models import Summary
from app.services.ehr_prompt import build_model_input
from app.services.summarizer import SECTION_KEYS, json_loads_sections

DEFAULT_MAX_NOTE = 8000


def main():
    p = argparse.ArgumentParser(description="Export EHR training JSONL")
    p.add_argument("--out", type=Path, default=ROOT / "training" / "data" / "ehr_train.jsonl")
    p.add_argument("--min-chars", type=int, default=200, help="Skip notes shorter than this")
    p.add_argument("--max-note", type=int, default=DEFAULT_MAX_NOTE, help="Truncate EHR for input")
    p.add_argument("--only-saved", action="store_true", help="Only rows where is_saved=True")
    args = p.parse_args()

    app = create_app()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    n_out = 0
    n_skip = 0
    lines: list[str] = []
    with app.app_context():
        q = db.session.query(Summary).order_by(Summary.id)
        if args.only_saved:
            q = q.filter(Summary.is_saved.is_(True))
        for s in q:
            if not s.generated_json:
                n_skip += 1
                continue
            doc = s.document
            if not doc or not doc.extracted_text or len(doc.extracted_text.strip()) < args.min_chars:
                n_skip += 1
                continue
            sec = json_loads_sections(s.generated_json)
            body = {k: (sec.get(k) or "").strip() for k in SECTION_KEYS}
            if not any(v and v != "—" for v in body.values()):
                n_skip += 1
                continue
            note = (doc.extracted_text or "")[: args.max_note]
            inp = build_model_input(note)
            tgt = json.dumps(body, ensure_ascii=False)
            lines.append(json.dumps({"input": inp, "target": tgt}, ensure_ascii=False))
            n_out += 1
    args.out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"Wrote {n_out} examples to {args.out} (skipped {n_skip}).")
    if n_out < 20:
        print(
            "Warning: fewer than 20 examples usually underfits. "
            "Add more saved summaries in the app, or use external MIMIC/Share notes with gold labels."
        )


if __name__ == "__main__":
    main()
