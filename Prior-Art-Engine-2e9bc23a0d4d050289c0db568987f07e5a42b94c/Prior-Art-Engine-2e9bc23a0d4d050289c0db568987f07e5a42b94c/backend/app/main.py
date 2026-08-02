# ============================================================
# Prior Art Validation Engine — FastAPI backend (v11 full-stack)
#
# This service exposes the exact same v11 LLM-Guided Hybrid pipeline
# that previously lived inside a single Streamlit script:
#   ARM A  concept graph (OpenAlex)
#   ARM B  full-text YAKE search (OpenAlex)
#   ARM C  precision keyword fallback (OpenAlex)
#   ARM PV PatentsView USPTO patent search
#   ARM D  Gemini 2.5 Flash Problem/Method extraction -> targeted search
#   Global Patentability & Novelty Report (Gemini-assisted, not legal advice)
#
# No retrieval, scoring, ranking, or LLM-prompt logic was changed
# during the migration — only the delivery mechanism (JSON over REST
# instead of server-rendered HTML).
# ============================================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import SearchRequest
from app.pipeline.search_service import run_search
from app.core.models import load_models
from app.core.config import CORS_ORIGINS

app = FastAPI(
    title="Prior Art Validation Engine API",
    description="Five-arm hybrid academic + patent prior-art retrieval engine.",
    version="11.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # set CORS_ORIGINS env var to your frontend's URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _warm_up_models():
    # Load the bi-encoder / cross-encoder once at startup instead of on
    # the first request, so the first real search isn't penalised. On
    # memory-constrained free-tier instances this can occasionally OOM;
    # if so, swallow it here and let the lazy-loading lock in
    # core/models.py retry on the first real request instead of crash-
    # looping the whole service before it can even serve /api/health.
    try:
        load_models()
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] Model warm-up failed, will retry lazily on first request: {exc}")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/search")
async def search(req: SearchRequest):
    idea = req.idea.strip()
    if not idea:
        raise HTTPException(status_code=400, detail="idea must not be empty.")
    try:
        result = await run_search(
            user_idea=idea,
            max_display=req.max_display,
            effective_threshold=req.effective_threshold,
            highlight_threshold_pct=req.highlight_threshold_pct,
            retrieval_mode=req.retrieval_mode,
            enable_patent_search=req.enable_patent_search,
            enable_arm_d=req.enable_arm_d,
            enable_global_report=req.enable_global_report,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search pipeline failed: {exc}") from exc
