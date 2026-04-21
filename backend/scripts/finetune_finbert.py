"""Fine-tune FinBERT on financial sentiment data (Financial PhraseBank + custom).

Usage:
    python scripts/finetune_finbert.py \
        --dataset data/processed/sentiment_train.csv \
        --output_dir models/finetuned/finbert-sentiment \
        --epochs 5
"""

import argparse
import logging

import numpy as np
import pandas as pd
import torch
from datasets import Dataset
from sklearn.metrics import accuracy_score, f1_score, classification_report
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


LABEL_TO_ID = {"positive": 0, "negative": 1, "neutral": 2}


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro"),
        "f1_weighted": f1_score(labels, preds, average="weighted"),
    }


def main(args):
    logger.info("Loading dataset: %s", args.dataset)
    df = pd.read_csv(args.dataset)
    df["label"] = df["label"].map(LABEL_TO_ID)
    df = df.dropna(subset=["text", "label"])

    split = df.sample(frac=0.1, random_state=42)
    train_df = df.drop(split.index)
    val_df = split

    train_dataset = Dataset.from_pandas(train_df[["text", "label"]].reset_index(drop=True))
    val_dataset = Dataset.from_pandas(val_df[["text", "label"]].reset_index(drop=True))
    logger.info("Train: %d, Val: %d", len(train_dataset), len(val_dataset))

    model_name = "ProsusAI/finbert"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=3
    )

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=512, padding="max_length")

    train_dataset = train_dataset.map(tokenize, batched=True)
    val_dataset = val_dataset.map(tokenize, batched=True)
    train_dataset.set_format("torch", columns=["input_ids", "attention_mask", "label"])
    val_dataset.set_format("torch", columns=["input_ids", "attention_mask", "label"])

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=32,
        per_device_eval_batch_size=64,
        learning_rate=2e-5,
        warmup_ratio=0.1,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_weighted",
        logging_steps=50,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
    )

    logger.info("Starting FinBERT fine-tuning...")
    trainer.train()

    logger.info("Final evaluation:")
    metrics = trainer.evaluate()
    logger.info(metrics)

    logger.info("Saving model to %s", args.output_dir)
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    logger.info("FinBERT fine-tuning complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune FinBERT for financial sentiment")
    parser.add_argument("--dataset", type=str, required=True)
    parser.add_argument("--output_dir", type=str, default="models/finetuned/finbert-sentiment")
    parser.add_argument("--epochs", type=int, default=5)
    main(parser.parse_args())
