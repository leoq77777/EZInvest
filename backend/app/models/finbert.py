"""FinBERT sentiment analysis model wrapper."""

import logging

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from app.config import get_settings

logger = logging.getLogger(__name__)

LABEL_MAP = {0: "positive", 1: "negative", 2: "neutral"}


class FinBERTSentiment:
    """Wraps a fine-tuned FinBERT model for financial sentiment classification."""

    def __init__(self):
        settings = get_settings()
        model_path = settings.finbert_model_path
        logger.info("Loading FinBERT from: %s", model_path)

        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
        self.model.eval()

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

    def predict(self, text: str) -> dict:
        """Run sentiment prediction on a single text.

        Returns:
            dict with keys: label, score, scores
            Example: {"label": "positive", "score": 0.92, "scores": {"positive": 0.92, "negative": 0.03, "neutral": 0.05}}
        """
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)[0]

        scores = {LABEL_MAP[i]: round(float(probs[i]), 4) for i in range(len(LABEL_MAP))}
        top_idx = torch.argmax(probs).item()

        return {
            "label": LABEL_MAP[top_idx],
            "score": round(float(probs[top_idx]), 4),
            "scores": scores,
        }

    def predict_batch(self, texts: list[str]) -> list[dict]:
        """Run sentiment prediction on a batch of texts."""
        inputs = self.tokenizer(
            texts,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)

        results = []
        for prob in probs:
            scores = {LABEL_MAP[i]: round(float(prob[i]), 4) for i in range(len(LABEL_MAP))}
            top_idx = torch.argmax(prob).item()
            results.append({
                "label": LABEL_MAP[top_idx],
                "score": round(float(prob[top_idx]), 4),
                "scores": scores,
            })
        return results
