# ============================================================
# SECTION 4 — YAKE KEYPHRASE EXTRACTION (ported 1:1)
# ============================================================

import re
import yake

from app.core.stopwords import YAKE_STOPWORDS


def _is_high_signal(phrase: str) -> bool:
    tokens = phrase.lower().split()
    if not tokens:
        return False
    if len(tokens) == 1 and tokens[0] in YAKE_STOPWORDS:
        return False
    if all(t in YAKE_STOPWORDS for t in tokens):
        return False
    if re.fullmatch(r"[\d\s\W]+", phrase):
        return False
    return True


def _dedup_phrases(phrases: list, overlap_threshold: float = 0.65) -> list:
    selected = []
    for phrase in phrases:
        toks = frozenset(phrase.lower().split())
        redundant = any(
            bool(toks and kept) and
            len(toks & kept) / min(len(toks), len(kept)) >= overlap_threshold
            for _, kept in selected
        )
        if not redundant:
            selected.append((phrase, toks))
    return [p for p, _ in selected]


def extract_yake_keyphrases(text: str, max_out: int = 10) -> list:
    text = re.sub(r"\s+", " ", text.strip())
    words = text.split()
    if len(words) < 4:
        return [w for w in words if w.lower() not in YAKE_STOPWORDS][:max_out]

    kw_extractor = yake.KeywordExtractor(lan="en", n=3, dedupLim=0.75, top=25, features=None)
    raw = kw_extractor.extract_keywords(text)
    filtered = [
        phrase for phrase, _score in sorted(raw, key=lambda x: x[1])
        if _is_high_signal(phrase)
    ]
    deduped = _dedup_phrases(filtered)
    if len(deduped) < 3:
        extra = [
            w for w in re.findall(r"\b[a-zA-Z]{3,}\b", text)
            if w.lower() not in YAKE_STOPWORDS
        ]
        seen = {p.lower() for p in deduped}
        for w in extra:
            if w.lower() not in seen:
                seen.add(w.lower())
                deduped.append(w)
    return _dedup_phrases(deduped)[:max_out]
