"""
Inference with a fine-tuned Flan-T5 (or compatible) seq2seq model.
Requires: pip install -r requirements-ml.txt
Environment:
  EHR_HF_MODEL_DIR   — path to saved model directory (from training/finetune_flan_t5.py)
  EHR_HF_MAX_INPUT_CHARS — truncate long notes (default 6000)
"""
from __future__ import annotations

import json
import logging
import os
import re
from threading import Lock
from typing import Dict, List, Optional

from app.services.ehr_prompt import build_model_input
from app.services.summarizer import SECTION_KEYS, _heuristic_summarize

logger = logging.getLogger(__name__)

_LOCK = Lock()
_MODEL = None
_TOKENIZER = None


def _get_model():
    global _MODEL, _TOKENIZER
    path = os.environ.get("EHR_HF_MODEL_DIR")
    if not path or not os.path.isdir(path):
        raise RuntimeError("EHR_HF_MODEL_DIR is not set or not a directory")
    with _LOCK:
        if _MODEL is not None:
            return _MODEL, _TOKENIZER
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        _TOKENIZER = AutoTokenizer.from_pretrained(path)
        _MODEL = AutoModelForSeq2SeqLM.from_pretrained(path)
        _MODEL.to(device)
        _MODEL.eval()
        logger.info("Loaded HF EHR model from %s on %s", path, device)
        return _MODEL, _TOKENIZER


def _parse_json_blob(text: str) -> Optional[dict]:
    text = (text or "").strip()
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text, flags=re.I)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def summarize_ehr_text_hf(raw_text: str, domain_terms: Optional[List[str]] = None) -> Dict[str, str]:
    """
    Run fine-tuned seq2seq. Falls back to heuristics if anything fails.
    """
    _ = domain_terms
    try:
        model, tok = _get_model()
    except Exception as e:
        logger.warning("Could not load HF model: %s", e)
        return _heuristic_summarize(raw_text, domain_terms)

    import torch

    max_chars = int(os.environ.get("EHR_HF_MAX_INPUT_CHARS", "6000"))
    note = (raw_text or "")[:max_chars]
    text_in = build_model_input(note)
    device = next(model.parameters()).device

    inputs = tok(
        text_in,
        return_tensors="pt",
        truncation=True,
        max_length=1024,
    ).to(device)

    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=1024,
            num_beams=2,
            do_sample=False,
            early_stopping=True,
        )

    decoded = tok.decode(out[0], skip_special_tokens=True)
    data = _parse_json_blob(decoded)
    if not data:
        logger.warning("HF model output was not valid JSON; using heuristics.")
        return _heuristic_summarize(raw_text, domain_terms)

    out_d: Dict[str, str] = {}
    for k in SECTION_KEYS:
        v = data.get(k)
        out_d[k] = (str(v).strip() if v is not None else "") or "—"
    return out_d
