"""
Document loader for user-provided sources.

Single public function
──────────────────────
    load_document(path_or_url) -> str

Handles three input types:
    • HTTP/HTTPS URL  — fetches the page and extracts visible text
    • PDF file path   — extracts text from all pages using pypdf
    • Plain text file — reads the file directly
"""

import logging
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT: int = 15       # seconds before giving up on a URL fetch
_MAX_CONTENT_CHARS: int = 12_000 # truncation limit to keep token usage bounded


def load_document(path_or_url: str) -> str:
    """Load and return text content from a file path or URL.

    Args:
        path_or_url: An HTTP/HTTPS URL, a PDF file path, or a plain-text
                     file path passed as a CLI argument.

    Returns:
        Extracted text as a single string, truncated to _MAX_CONTENT_CHARS.
        Returns an empty string on any error so the sub-agent can continue.
    """
    source = path_or_url.strip()

    try:
        if source.startswith("http://") or source.startswith("https://"):
            return _load_url(source)

        path = Path(source)
        if not path.exists():
            logger.warning("document_loader: file not found — %s", source)
            return ""

        if path.suffix.lower() == ".pdf":
            return _load_pdf(path)

        return _load_text_file(path)

    except Exception as exc:
        logger.error("document_loader: failed to load %r — %s", source, exc)
        return ""


# ── Private loaders ────────────────────────────────────────────────────────────

def _load_url(url: str) -> str:
    """Fetch a web page and return its visible text content."""
    logger.debug("document_loader: fetching URL %s", url)

    headers = {"User-Agent": "Mozilla/5.0 (research-agent/1.0)"}
    resp = requests.get(url, headers=headers, timeout=_REQUEST_TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove boilerplate tags
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    return _truncate(text, url)


def _load_pdf(path: Path) -> str:
    """Extract text from all pages of a PDF file."""
    logger.debug("document_loader: reading PDF %s", path)

    reader = PdfReader(str(path))
    pages = [
        page.extract_text() or ""
        for page in reader.pages
    ]
    text = "\n\n".join(pages)
    return _truncate(text, str(path))


def _load_text_file(path: Path) -> str:
    """Read a plain text file."""
    logger.debug("document_loader: reading text file %s", path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    return _truncate(text, str(path))


def _truncate(text: str, source: str) -> str:
    """Trim content to _MAX_CONTENT_CHARS and log if truncated."""
    cleaned = " ".join(text.split())  # collapse whitespace
    if len(cleaned) > _MAX_CONTENT_CHARS:
        logger.debug(
            "document_loader: truncated %s from %d to %d chars",
            source, len(cleaned), _MAX_CONTENT_CHARS,
        )
        return cleaned[:_MAX_CONTENT_CHARS]
    return cleaned
