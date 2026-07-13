# ============================================================
# SECTION 10 — SENTENCE HIGHLIGHTING (ported 1:1)
# The HTML-string builders (`build_highlighted_html`) are dropped:
# in the full-stack version the React frontend renders highlights
# from the same structured (sentence, is_highlighted) data instead
# of receiving pre-built HTML strings. The similarity math driving
# which sentences are highlighted is unchanged.
# ============================================================

import re

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine

from app.core.config import HIGHLIGHT_COSINE_THRESH


def split_into_sentences(text: str) -> list:
    if not text or not text.strip():
        return []
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if len(s.strip()) > 8]


def compute_sentence_highlights(sentences: list, query_vector, bi_model,
                                 threshold: float = HIGHLIGHT_COSINE_THRESH) -> list:
    if not sentences:
        return []
    vecs = bi_model.encode(
        sentences, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False,
    )
    return [float(sk_cosine(query_vector, v.reshape(1, -1))[0][0]) >= threshold for v in vecs]


def find_best_matching_sentence(sentences: list, query_vector, bi_model):
    if not sentences:
        return None, 0.0
    vecs = bi_model.encode(
        sentences, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False,
    )
    sims = [float(sk_cosine(query_vector, v.reshape(1, -1))[0][0]) for v in vecs]
    best_idx = int(np.argmax(sims))
    return sentences[best_idx], sims[best_idx]


def build_sentence_view(text: str, query_vector, bi_model, threshold: float) -> dict:
    """
    Structured replacement for build_highlighted_html(): returns
    sentences + per-sentence highlight flags + the single best-matching
    sentence, all driven by the exact same similarity computation as
    the original Streamlit app.
    """
    sentences = split_into_sentences(text)
    if not sentences:
        return {"sentences": [], "highlight_count": 0, "best_sentence": None, "best_similarity": 0.0}

    flags = compute_sentence_highlights(sentences, query_vector, bi_model, threshold=threshold)
    best_sentence, best_sim = find_best_matching_sentence(sentences, query_vector, bi_model)

    return {
        "sentences": [
            {"text": s, "highlighted": bool(f)} for s, f in zip(sentences, flags)
        ],
        "highlight_count": int(sum(flags)),
        "best_sentence": best_sentence,
        "best_similarity": float(best_sim),
    }
