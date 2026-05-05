import asyncio
import logging
from typing import List
from bs4 import BeautifulSoup

from langchain_core.tools import tool
import httpx
from app.agent.entity_resolution import SANDISK_FACT, mentions_sandisk

try:
    from duckduckgo_search import DDGS
except ImportError:  # pragma: no cover
    DDGS = None  # type: ignore[misc, assignment]

logger = logging.getLogger(__name__)


def _curated_web_hint(query: str) -> str:
    if not mentions_sandisk(query):
        return ""
    fact = SANDISK_FACT
    return (
        "Curated corporate-action fallback: "
        f"{fact['entity']} is treated as independently listed with ticker "
        f"{fact['ticker']} since {fact['valid_from']} after separation from "
        f"Western Digital ({fact['former_parent_ticker']}). Search/live-data "
        "providers should query SNDK, not WDC, for SanDisk stock price."
    )

async def fetch_and_parse(url: str) -> str:
    """Fetch a URL and extract text content."""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            # Basic headers to avoid immediate blocks
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Remove scripts and styles
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
                
            text = soup.get_text(separator="\n")
            
            # Clean up empty lines
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return ""

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Basic sliding window chunking."""
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += (chunk_size - overlap)
    return chunks

@tool
async def web_scraper_tool(query: str, max_urls: int = 2) -> str:
    """Search the web for real-time news or data, scrape the content, and index it into the database.
    
    Use this tool when the user asks about very recent events, live financial news, or specific
    company information that might not be in the local database. The tool automatically saves 
    the scraped information into the dynamic knowledge base for the retriever to find.
    
    Args:
        query: The search query to look for on the web.
        max_urls: Number of top URLs to scrape and index (default 2, max 3).
    """
    logger.info(f"Web scraper initiated for query: {query}")

    if DDGS is None:
        hint = _curated_web_hint(query)
        if hint:
            return hint + "\n\nWeb search is unavailable (duckduckgo_search not installed)."
        return (
            "Web search is unavailable (duckduckgo_search not installed). "
            "Install backend dependencies or use retriever/market_data only."
        )

    def _ddgs_sync_urls() -> list[str]:
        u: list[str] = []
        with DDGS() as ddgs:
            search_query = query
            if mentions_sandisk(query) and "SNDK" not in query.upper():
                search_query = (
                    query
                    + " SanDisk SNDK stock independent listing 2025 spinoff Western Digital"
                )
            results = ddgs.text(
                search_query,
                region="wt-wt",
                safesearch="off",
                max_results=max_urls,
            )
            if results:
                u = [r["href"] for r in results if "href" in r]
        return u

    urls: list[str] = []
    try:
        urls = await asyncio.to_thread(_ddgs_sync_urls)
    except Exception as e:
        logger.error(f"DDGS search failed for query '{query}': {e}")
        hint = _curated_web_hint(query)
        if hint:
            return f"{hint}\n\nWeb search encountered an issue: {e}"
        # If it's a 'return None' error, it might be a block; try a simpler query or just fail gracefully
        return f"Web search encountered an issue (it might be rate-limited). Error: {e}"

    if not urls:
        hint = _curated_web_hint(query)
        if hint:
            return hint + "\n\nNo web URLs were returned by the search provider."
        return "No results found on the web."

    logger.info(f"Scraping {len(urls)} URLs...")
    
    # Fetch concurrently
    tasks = [fetch_and_parse(url) for url in urls]
    contents = await asyncio.gather(*tasks)
    
    all_chunks = []
    all_metadatas = []
    
    for url, text in zip(urls, contents):
        if text:
            chunks = chunk_text(text)
            all_chunks.extend(chunks)
            all_metadatas.extend([{"source": url}] * len(chunks))
            
    if not all_chunks:
        hint = _curated_web_hint(query)
        if hint:
            return hint + f"\n\nSearched {urls}, but failed to extract readable content."
        return f"Searched {urls}, but failed to extract readable content."

    try:
        from app.rag.pgvector_store import get_dynamic_store
    except ImportError:
        return (
            f"Scraped {len(all_chunks)} chunks from web but pgvector store is not available "
            f"(langchain_postgres not installed). Sources:\n" + "\n".join(urls)
        )

    store = get_dynamic_store()
    await store.add_texts(texts=all_chunks, metadatas=all_metadatas)
    
    # Return a concise summary to the agent
    preview_sources = "\\n".join(urls)
    total_chunks = len(all_chunks)
    
    return (
        f"Successfully scraped and indexed {total_chunks} text chunks from the web.\\n"
        f"Sources:\\n{preview_sources}\\n\\n"
        f"The data is now in the dynamic vector database. Please use the `retriever` tool with relevant keywords to fetch the detailed information to answer the user's query."
    )
