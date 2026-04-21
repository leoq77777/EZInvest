"""Build FAISS + BM25 indexes from processed document chunks.

Usage:
    python scripts/build_index.py --data data/processed/chunks.jsonl

If no --data is provided, generates a sample dataset for testing.
"""

import argparse
import json
import logging
import pickle
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SAMPLE_DOCS = [
    {"text": "NVIDIA reported Q3 FY2025 revenue of $35.1 billion, up 94% year-over-year. Data center revenue reached $30.8 billion, driven by strong demand for Hopper GPUs and AI infrastructure.", "source": "NVDA 10-Q Q3 2025", "section": "financial_highlights"},
    {"text": "NVIDIA's gross margin expanded to 74.6% in Q3, reflecting favorable product mix shift toward high-margin data center GPUs. Operating expenses grew 44% to $4.3 billion.", "source": "NVDA 10-Q Q3 2025", "section": "profitability"},
    {"text": "NVIDIA gaming revenue was $3.3 billion in Q3, up 15% year-over-year. The GeForce RTX 50 series is expected to drive further growth in the next fiscal year.", "source": "NVDA 10-Q Q3 2025", "section": "gaming"},
    {"text": "Apple reported Q4 FY2025 revenue of $94.9 billion, with iPhone revenue of $46.2 billion. Services revenue hit a record $25.0 billion, growing 12% year-over-year.", "source": "AAPL 10-K FY2025", "section": "revenue"},
    {"text": "Apple's installed base of active devices exceeded 2.2 billion globally. The company returned $29 billion to shareholders through dividends and buybacks in Q4.", "source": "AAPL 10-K FY2025", "section": "shareholder_returns"},
    {"text": "Apple's Greater China revenue declined 2% to $15.0 billion, reflecting competitive pressure from Huawei and other domestic brands. Management expressed confidence in long-term growth.", "source": "AAPL 10-K FY2025", "section": "china"},
    {"text": "Microsoft reported Q1 FY2026 revenue of $65.6 billion, up 16% year-over-year. Azure and cloud services grew 34%, driven by AI workload adoption.", "source": "MSFT 10-Q Q1 2026", "section": "cloud"},
    {"text": "Microsoft's AI-related revenue run rate exceeded $10 billion annualized. Copilot adoption reached 1.3 million paid subscribers across enterprise and consumer segments.", "source": "MSFT 10-Q Q1 2026", "section": "ai_revenue"},
    {"text": "Tesla delivered 462,000 vehicles in Q3 2025, down 5% from Q2. Automotive gross margin fell to 17.1% amid ongoing price cuts to maintain market share.", "source": "TSLA 10-Q Q3 2025", "section": "deliveries"},
    {"text": "Tesla's energy generation and storage business grew 52% to $2.4 billion in Q3 revenue. Megapack deployments reached 6.9 GWh, a quarterly record.", "source": "TSLA 10-Q Q3 2025", "section": "energy"},
    {"text": "Tesla's FSD (Full Self-Driving) supervised miles exceeded 2 billion cumulative. Management expects robotaxi launch in Austin by Q2 2026.", "source": "TSLA 10-Q Q3 2025", "section": "autonomous"},
    {"text": "Amazon reported Q3 2025 net sales of $158.9 billion, up 11% year-over-year. AWS revenue was $27.5 billion, growing 19% with improving operating margins of 38.1%.", "source": "AMZN 10-Q Q3 2025", "section": "aws"},
    {"text": "Amazon's advertising revenue reached $14.3 billion in Q3, up 19%. The segment has become the company's fastest-growing high-margin business.", "source": "AMZN 10-Q Q3 2025", "section": "advertising"},
    {"text": "Google reported Q3 2025 revenue of $88.3 billion. Google Cloud revenue was $11.4 billion, up 35%, with operating profit of $1.9 billion.", "source": "GOOGL 10-Q Q3 2025", "section": "cloud"},
    {"text": "Alphabet's total headcount decreased by 5% year-over-year as the company continued efficiency measures. Capex rose to $13.1 billion for AI infrastructure.", "source": "GOOGL 10-Q Q3 2025", "section": "operations"},
    {"text": "In the Q3 2025 earnings call, NVIDIA CEO Jensen Huang stated: 'The next industrial revolution has begun. Companies and countries are investing in AI infrastructure at an unprecedented pace.'", "source": "NVDA Earnings Call Q3 2025", "section": "ceo_remarks"},
    {"text": "During the earnings call, NVIDIA CFO noted that Blackwell GPU production is ramping and expected to contribute significantly to Q4 revenue. Supply constraints are gradually easing.", "source": "NVDA Earnings Call Q3 2025", "section": "guidance"},
    {"text": "Tim Cook on Apple's Q4 call: 'We're incredibly excited about Apple Intelligence. Early customer feedback has been very positive, and we see this as a multi-year growth driver.'", "source": "AAPL Earnings Call Q4 2025", "section": "ai_strategy"},
    {"text": "Semiconductor industry capital expenditure is projected to exceed $190 billion in 2026, driven by AI chip demand. TSMC, Samsung, and Intel are all expanding advanced node capacity.", "source": "Industry Report: Semiconductor Capex 2026", "section": "industry"},
    {"text": "The Federal Reserve held interest rates steady at 4.25-4.50% in its January 2026 meeting, citing persistent inflation concerns. Markets now expect two rate cuts in H2 2026.", "source": "Fed Minutes Jan 2026", "section": "macro"},
]


def build_faiss_index(docs, output_path):
    from app.rag.embedder import embed_texts

    texts = [d["text"] for d in docs]
    metadata = [{"source": d["source"], "section": d.get("section", "")} for d in docs]

    logger.info("Generating embeddings for %d documents...", len(texts))
    vectors = embed_texts(texts)
    dim = vectors.shape[1]
    logger.info("Embedding dim: %d", dim)

    import faiss
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(path))

    meta_path = path.with_suffix(".meta.pkl")
    with open(meta_path, "wb") as f:
        pickle.dump({"texts": texts, "metadata": metadata}, f)

    logger.info("FAISS index saved: %d vectors → %s", index.ntotal, path)


def build_bm25_index(docs, output_path):
    from rank_bm25 import BM25Okapi

    corpus = []
    tokenized = []
    for d in docs:
        corpus.append({"text": d["text"], "source": d["source"]})
        tokenized.append(d["text"].lower().split())

    bm25 = BM25Okapi(tokenized)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump({"bm25": bm25, "corpus": corpus}, f)

    logger.info("BM25 index saved: %d documents → %s", len(corpus), path)


def main(args):
    if args.data and Path(args.data).exists():
        logger.info("Loading data from %s", args.data)
        docs = []
        with open(args.data) as f:
            for line in f:
                docs.append(json.loads(line))
    else:
        logger.info("Using built-in sample dataset (%d documents)", len(SAMPLE_DOCS))
        docs = SAMPLE_DOCS

    build_faiss_index(docs, args.faiss_output)
    build_bm25_index(docs, args.bm25_output)
    logger.info("All indexes built successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build FAISS + BM25 indexes")
    parser.add_argument("--data", type=str, default=None, help="Path to chunks.jsonl")
    parser.add_argument("--faiss_output", type=str, default="data/indexes/faiss_hnsw.index")
    parser.add_argument("--bm25_output", type=str, default="data/indexes/bm25.pkl")
    main(parser.parse_args())
