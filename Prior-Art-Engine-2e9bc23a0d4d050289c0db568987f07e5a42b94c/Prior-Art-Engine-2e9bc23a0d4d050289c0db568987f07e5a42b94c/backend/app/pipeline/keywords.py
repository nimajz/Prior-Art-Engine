# ============================================================
# SECTION 5 — KEYWORD EXTRACTOR (ported 1:1, originally from app2.py)
# ============================================================

import re

from app.core.stopwords import KW_STOPWORDS


def extract_keyword_fallback(text: str, max_out: int = 6) -> list:
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    cleaned = [w for w in words if w not in KW_STOPWORDS]
    seen: set = set()
    unique = [w for w in cleaned if not (w in seen or seen.add(w))]
    return unique[:max_out]
