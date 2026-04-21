"""Evaluate FinBERT sentiment model on a test set.

Usage:
    python eval/run_sentiment.py \
        --model_path models/finetuned/finbert-sentiment \
        --test_data data/processed/sentiment_test.csv
"""

import argparse
import logging

import pandas as pd
from sklearn.metrics import classification_report, f1_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LABEL_MAP = {"positive": 0, "negative": 1, "neutral": 2}
ID_TO_LABEL = {v: k for k, v in LABEL_MAP.items()}


def main(args):
    logger.info("Loading model from: %s", args.model_path)
    from app.models.finbert import FinBERTSentiment

    # Override the model path temporarily
    import app.config as cfg
    settings = cfg.get_settings()
    settings.finbert_model_path = args.model_path

    model = FinBERTSentiment()

    logger.info("Loading test data: %s", args.test_data)
    df = pd.read_csv(args.test_data)
    df = df.dropna(subset=["text", "label"])

    texts = df["text"].tolist()
    true_labels = df["label"].tolist()

    logger.info("Running predictions on %d samples...", len(texts))
    predictions = model.predict_batch(texts)
    pred_labels = [p["label"] for p in predictions]

    print("\n" + "=" * 60)
    print("SENTIMENT MODEL EVALUATION")
    print("=" * 60)
    print(classification_report(true_labels, pred_labels))

    f1_w = f1_score(true_labels, pred_labels, average="weighted")
    f1_m = f1_score(true_labels, pred_labels, average="macro")
    print(f"F1 (weighted): {f1_w:.4f}")
    print(f"F1 (macro):    {f1_m:.4f}")
    print(f"Target:        ≥ 0.9000")
    print(f"{'PASS ✓' if f1_w >= 0.90 else 'FAIL ✗'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--test_data", required=True)
    main(parser.parse_args())
