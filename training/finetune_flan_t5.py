"""
Fine-tune a Flan-T5 model on JSONL from export_training_data.py.

Usage (from project root, with requirements-ml.txt installed):
  python training/finetune_flan_t5.py --train_file training/data/ehr_train.jsonl --output_dir training/model_ehr

GPU recommended. On CPU, use --base_model google/flan-t5-small --epochs 1 for smoke tests.
"""
from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--train_file", type=Path, default=ROOT / "training" / "data" / "ehr_train.jsonl")
    p.add_argument("--output_dir", type=Path, default=ROOT / "training" / "model_ehr")
    p.add_argument("--base_model", type=str, default="google/flan-t5-base")
    p.add_argument("--epochs", type=float, default=3.0)
    p.add_argument("--batch_size", type=int, default=1)
    p.add_argument("--grad_accum", type=int, default=4)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--max_input_length", type=int, default=1024)
    p.add_argument("--max_target_length", type=int, default=1024)
    p.add_argument("--test_split", type=float, default=0.05, help="Hold-out fraction (min 1 row eval)")
    args = p.parse_args()

    if not args.train_file.is_file():
        print(f"Not found: {args.train_file}. Run training/export_training_data.py first.", file=sys.stderr)
        sys.exit(1)

    import torch
    from datasets import load_dataset
    from transformers import (
        AutoModelForSeq2SeqLM,
        AutoTokenizer,
        DataCollatorForSeq2Seq,
        Seq2SeqTrainer,
        Seq2SeqTrainingArguments,
    )

    ds = load_dataset("json", data_files=str(args.train_file), split="all")
    if len(ds) < 1:
        print("No rows in training file.", file=sys.stderr)
        sys.exit(1)

    if len(ds) < 5 or args.test_split <= 0:
        train_d, eval_d = ds, None
    else:
        n_test = max(1, int(len(ds) * args.test_split))
        if n_test >= len(ds):
            n_test = max(1, len(ds) // 5)
        split = ds.train_test_split(test_size=n_test, seed=42)
        train_d, eval_d = split["train"], split["test"]

    tok = AutoTokenizer.from_pretrained(args.base_model)
    # Do not override tie_word_embeddings in config: it changes the expected param layout and
    # leaves encoder/decoder embed_tokens randomly initialized (MISSING in load report).
    model = AutoModelForSeq2SeqLM.from_pretrained(args.base_model)

    def tokenize(examples):
        m = tok(
            examples["input"],
            max_length=args.max_input_length,
            truncation=True,
        )
        t = tok(
            text_target=examples["target"],
            max_length=args.max_target_length,
            truncation=True,
        )
        m["labels"] = t["input_ids"]
        return m

    train_t = train_d.map(tokenize, batched=True, remove_columns=train_d.column_names)
    eval_t = (
        eval_d.map(tokenize, batched=True, remove_columns=eval_d.column_names) if eval_d is not None else None
    )

    collator = DataCollatorForSeq2Seq(tok, model=model)

    # transformers 5.x uses eval_strategy; 4.x used evaluation_strategy
    _s = inspect.signature(Seq2SeqTrainingArguments.__init__)
    _eval_key = "eval_strategy" if "eval_strategy" in _s.parameters else "evaluation_strategy"
    targs = Seq2SeqTrainingArguments(
        output_dir=str(args.output_dir),
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        num_train_epochs=args.epochs,
        weight_decay=0.01,
        predict_with_generate=bool(eval_t),
        save_strategy="epoch",
        load_best_model_at_end=bool(eval_t),
        save_total_limit=1,
        logging_steps=5,
        dataloader_pin_memory=torch.cuda.is_available(),
        **{_eval_key: "epoch" if eval_t is not None else "no"},
    )

    # transformers 5.x: tokenizer -> processing_class
    _ts = inspect.signature(Seq2SeqTrainer.__init__)
    _tok_key = "processing_class" if "processing_class" in _ts.parameters else "tokenizer"
    trainer = Seq2SeqTrainer(
        model=model,
        args=targs,
        train_dataset=train_t,
        eval_dataset=eval_t,
        data_collator=collator,
        **{_tok_key: tok},
    )
    trainer.train()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(args.output_dir))
    tok.save_pretrained(str(args.output_dir))
    print(f"Done. Set EHR_HF_MODEL_DIR={args.output_dir} and EHR_SUMMARY_MODE=hf")


if __name__ == "__main__":
    main()
