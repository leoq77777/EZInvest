"""FinBERT-based financial sentiment analysis tool."""

import asyncio
import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_sentiment_model = None
_load_lock = asyncio.Lock()


@tool
async def sentiment_tool(text: str) -> str:
    """Analyze sentiment of financial text using a fine-tuned FinBERT model.

    Use this tool to assess market sentiment from earnings call excerpts,
    financial news headlines, or analyst commentary. Returns a sentiment
    label (positive/negative/neutral) with a confidence score.

    Args:
        text: The financial text to analyze. Can be a single sentence or
              a short paragraph (max ~512 tokens).
    """
    global _sentiment_model
    if _sentiment_model is None:
        async with _load_lock:
            if _sentiment_model is None:
                from app.models.finbert import FinBERTSentiment

                # HuggingFace / torch init blocks the event loop for minutes on first load;
                # offload so SSE and other requests can still make progress.
                _sentiment_model = await asyncio.to_thread(FinBERTSentiment)
    model = _sentiment_model
    try:
        result = await asyncio.to_thread(model.predict, text)
    except Exception as e:
        logger.error("Sentiment analysis failed: %s", e)
        return f"Sentiment analysis error: {e}"

    label = result["label"]
    score = result["score"]
    breakdown = result.get("scores", {})

    parts = [f"Sentiment: {label} (confidence: {score:.3f})"]
    if breakdown:
        detail = ", ".join(f"{k}: {v:.3f}" for k, v in breakdown.items())
        parts.append(f"Score breakdown: {detail}")

    return "\n".join(parts)
