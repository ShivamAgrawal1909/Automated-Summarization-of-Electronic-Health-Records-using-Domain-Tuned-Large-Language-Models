# Training a domain EHR summary model (Flan-T5)

## What you are training

The app maps **full extracted EHR text** to a **single JSON object** with eight string fields (see `app/services/summarizer.py`). The fine-tuning script uses **supervised (input, target) pairs** where:

- **input** = the same instruction prefix the app uses at inference + the clinical note (`app/services/ehr_prompt.py`).
- **target** = JSON with keys `patient_information`, `symptoms`, `diagnosis`, `medicines`, `lab_reports`, `treatment_plan`, `doctor_notes`, `follow_up_instructions`.

## Data quality and quantity

- **More and higher-quality saved summaries in the app** lead to better labels. After experts edit summaries, re-export.
- A few hundred diverse notes beat thousands of near-duplicates. Aim for at least **50–200** good pairs before expecting solid gains; **hundreds+** is typical in papers.
- You can add **public de-identified notes** and **hand-written gold JSON** in the same JSONL format to supplement app exports.

## Steps

1. **Install ML stack** (ideally a GPU; CPU works for small models and short runs):
   ```bash
   pip install -r requirements-ml.txt
   ```

2. **Export training pairs** from your SQLite database (creates the JSONL file):
   ```bash
   python training/export_training_data.py --out training/data/ehr_train.jsonl
   ```
   Optional: `--only-saved` to use only summaries the user marked saved.

3. **Fine-tune** (default base: `google/flan-t5-base`):
   ```bash
   python training/finetune_flan_t5.py --train_file training/data/ehr_train.jsonl --output_dir training/model_ehr
   ```
   For a quick test on CPU: add `--base_model google/flan-t5-small --epochs 1 --batch_size 1`.

4. **Point the app at the checkpoint** (project root or absolute path to `training/model_ehr` after training):
   Create a `.env` file:
   ```env
   EHR_SUMMARY_MODE=hf
   EHR_HF_MODEL_DIR=training/model_ehr
   EHR_HF_MAX_INPUT_CHARS=6000
   ```

5. **Restart** the Flask app. If the model fails to load, the app **falls back to heuristics** and logs a warning.

## Limitations and next steps

- **Context length:** Flan-T5 is limited to ~512–1024 tokens per side in typical configs; long charts are truncated. For very long EHR, consider `LongT5`, chunking + merging, or an API model with 8k+ context.
- **Evaluation:** add ROUGE / BERTScore / clinician review on a held-out JSONL. The script does a small automatic train/validation split when enough rows exist.
- **LoRA / QLoRA:** for larger open models, use PEFT in a separate script to save VRAM; the inference loader would need a matching `PeftModel` path.

## Files

- `export_training_data.py` — DB → `ehr_train.jsonl`
- `finetune_flan_t5.py` — Flan-T5 `Seq2SeqTrainer`
- `app/services/hf_summarizer.py` — load checkpoint for production inference
- `app/services/ehr_prompt.py` — **keep training and inference prompts identical**
