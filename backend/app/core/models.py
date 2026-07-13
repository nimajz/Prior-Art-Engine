# ============================================================
# SECTION 2 — MODEL LOADING (replaces st.cache_resource)
# Loaded once, on first request, then reused as a process-wide singleton.
# ============================================================

import threading
import torch
from sentence_transformers import SentenceTransformer, CrossEncoder

from app.core.config import BI_ENCODER_ID, CE_MODEL_ID

device = "cuda" if torch.cuda.is_available() else "cpu"

_lock = threading.Lock()
_bi_model = None
_ce_model = None


def load_models():
    """Lazily load and cache the bi-encoder / cross-encoder models."""
    global _bi_model, _ce_model
    if _bi_model is None or _ce_model is None:
        with _lock:
            if _bi_model is None:
                _bi_model = SentenceTransformer(BI_ENCODER_ID, device=device)
            if _ce_model is None:
                _ce_model = CrossEncoder(CE_MODEL_ID, device=device)
    return _bi_model, _ce_model
