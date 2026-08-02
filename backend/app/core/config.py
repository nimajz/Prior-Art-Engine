# ============================================================
# Prior Art Validation Engine — backend configuration
# All constants ported 1:1 from the original Streamlit app.py.
# No algorithmic values were changed during the migration.
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Architecture constants ───────────────────────────────────────────────
BI_ENCODER_ID            = "BAAI/bge-small-en-v1.5"
BGE_QUERY_PREFIX         = "Represent this sentence for searching relevant passages: "
CE_MODEL_ID               = "cross-encoder/ms-marco-MiniLM-L-6-v2"

CE_HARD_FLOOR             = 0.10
OPENALEX_FETCH            = 100
CONCEPT_TOP_N             = 5
HIGHLIGHT_COSINE_THRESH   = 0.78
TOP_K_RERANK              = 20
MAX_CONCURRENT_REQS       = 4
CONCEPT_ARM_MIN_VIABLE    = 10

# Patent search constants (ARM PV — PatentsView)
PATENT_MAX_RESULTS        = 25
PATENT_TOP_K_RERANK       = 10
PATENTSVIEW_URL           = "https://search.patentsview.org/api/v1/patent/"
PATENTSVIEW_FIELDS        = "patent_id,patent_title,patent_abstract,patent_date,cpc.cpc_subclass_id"

# ARM D — Gemini extraction
GEMINI_API_KEY            = os.environ.get(
    "GEMINI_API_KEY",
    "YOUR_GEMINI_API_KEY_HERE",  # ← set GEMINI_API_KEY in backend/.env
)
GEMINI_MODEL               = "gemini-2.5-flash"
GEMINI_BASE_URL            = "https://generativelanguage.googleapis.com/v1beta/models"
ARM_D_CANDIDATE_QUOTA      = 40
ARM_D_TIMEOUT_S            = 20.0

# Global Patentability & Novelty Report
GLOBAL_REPORT_TOP_N        = 5
GLOBAL_REPORT_TIMEOUT_S    = 25.0

# CORS — comma-separated list of allowed frontend origins in production.
# Defaults to "*" for local dev convenience; set explicitly when deployed.
CORS_ORIGINS               = [
    o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()
]

OPENALEX_CONCEPTS_URL      = "https://api.openalex.org/concepts"
OPENALEX_WORKS_URL         = "https://api.openalex.org/works"
USER_AGENT                 = "PriorArtEngineV11/full-stack (mailto:your@email.com)"
SELECT_FIELDS              = "id,title,abstract_inverted_index,publication_date,doi,concepts"
