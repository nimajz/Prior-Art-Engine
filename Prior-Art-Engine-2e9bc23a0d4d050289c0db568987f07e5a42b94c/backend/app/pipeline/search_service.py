# ============================================================
# SEARCH SERVICE — orchestrates the full v11 pipeline exactly as the
# original Streamlit app's main script body did (Steps 1-7, Section
# 12 tabbed results, Section 13 global report) but returns a single
# structured JSON payload instead of rendering st.markdown() blocks.
#
# No retrieval/ranking/scoring logic was altered — only the
# presentation layer (HTML strings -> JSON) changed.
# ============================================================

import math
import time

from sklearn.metrics.pairwise import cosine_similarity as sk_cosine

from app.core.config import (
    BGE_QUERY_PREFIX, OPENALEX_FETCH, CONCEPT_TOP_N, TOP_K_RERANK,
    CE_HARD_FLOOR, PATENT_TOP_K_RERANK, GLOBAL_REPORT_TOP_N,
)
from app.core.models import load_models
from app.pipeline.classifier import classify_input
from app.pipeline.keyphrases import extract_yake_keyphrases
from app.pipeline.keywords import extract_keyword_fallback
from app.pipeline.openalex import (
    fetch_openalex_concepts, orchestrate_retrieval, reconstruct_abstract,
    deduplicate_works, calculate_fused_score, fetch_works_keyword_fallback,
)
from app.pipeline.patentsview import fetch_patents_patentsview, rerank_patents_with_ce
from app.pipeline.gemini import fetch_arm_d, fetch_global_report
from app.pipeline.scoring import build_sentence_view


async def run_search(
    user_idea: str,
    max_display: int = 5,
    effective_threshold: int = 25,
    highlight_threshold_pct: int = 78,
    retrieval_mode: str = "Concept + Full-Text (Recommended)",
    enable_patent_search: bool = True,
    enable_arm_d: bool = True,
    enable_global_report: bool = True,
) -> dict:
    t0 = time.time()
    bi_model, ce_model = load_models()

    # ── Step 1: classify input + cheap keyword layers ───────────────────────
    classifier_info = classify_input(user_idea)
    kw_fallback_terms = extract_keyword_fallback(user_idea)
    yake_keyphrases = extract_yake_keyphrases(user_idea)

    # ── Step 2: concept extraction ───────────────────────────────────────────
    concepts = await fetch_openalex_concepts(user_idea, top_n=CONCEPT_TOP_N)

    # ── Step 2B: ARM D — Gemini Problem/Method extraction ────────────────────
    arm_d_works, arm_d_extraction, arm_d_error = [], None, None
    if enable_arm_d:
        arm_d_works, arm_d_extraction, arm_d_error = await fetch_arm_d(user_idea)

    # ── Step 3: three-arm OpenAlex retrieval + ARM D merge ───────────────────
    all_works, src = await orchestrate_retrieval(
        user_idea, concepts, classifier_info, retrieval_mode, kw_fallback_terms
    )

    arm_d_new = []
    if arm_d_works:
        existing_ids = {w.get("id") or w.get("doi") or w.get("title", "") for w in all_works}
        arm_d_new = [
            w for w in arm_d_works
            if (w.get("id") or w.get("doi") or w.get("title", "")) not in existing_ids
        ]
        all_works = all_works + arm_d_new

    # ── Step 4: encode query ──────────────────────────────────────────────────
    formatted_query = BGE_QUERY_PREFIX + user_idea
    query_vector = bi_model.encode(
        [formatted_query], convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False,
    )

    # ── Step P: ARM PV — PatentsView patent search ────────────────────────────
    patent_records, patent_source, patent_error, patent_diags = [], "patentsview", None, []
    ranked_patents = []
    patent_kw_tuple = tuple(yake_keyphrases[:8])

    if enable_patent_search:
        patent_records, patent_source, patent_error, patent_diags = await fetch_patents_patentsview(
            patent_kw_tuple
        )
        if patent_records and not patent_error:
            ranked_patents = rerank_patents_with_ce(
                user_idea, patent_records, bi_model, ce_model, query_vector, top_k=PATENT_TOP_K_RERANK,
            )

    # ── Step 5-7: OpenAlex bi-encoder/cross-encoder pipeline ─────────────────
    displayed = []
    oa_pipeline_ran = False
    max_bi_in_pool = 0.0
    auto_supplement_triggered = False
    top_candidates_count = 0

    if all_works:
        oa_pipeline_ran = True

        parsed_papers, texts_to_encode = [], []
        for work in all_works:
            title = work.get("title")
            if not title:
                continue
            abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
            combined = f"{title}. {abstract}".strip()
            parsed_papers.append({
                "title": title, "abstract": abstract, "text": combined,
                "date": work.get("publication_date", "No date"),
                "doi": work.get("doi"),
                "concepts": [c.get("display_name", "") for c in work.get("concepts", [])[:3]],
            })
            texts_to_encode.append(combined)

        if parsed_papers:
            doc_matrix = bi_model.encode(
                texts_to_encode, convert_to_numpy=True,
                normalize_embeddings=True, batch_size=32, show_progress_bar=False,
            )
            bi_sims = sk_cosine(query_vector, doc_matrix)[0]
            for i, paper in enumerate(parsed_papers):
                paper["bi_score"] = float(bi_sims[i])

            top_candidates = sorted(parsed_papers, key=lambda p: p["bi_score"], reverse=True)[:TOP_K_RERANK]
            max_bi_in_pool = max((p["bi_score"] for p in top_candidates), default=0.0)

            # ── Auto-supplement (identical trigger condition to the original) ─
            if max_bi_in_pool < 0.45 and not src["arm_c_active"] and kw_fallback_terms:
                auto_supplement_triggered = True
                extra_works = await fetch_works_keyword_fallback(
                    tuple(kw_fallback_terms), per_page=OPENALEX_FETCH
                )
                extra_works = deduplicate_works(
                    [w for w in extra_works if w.get("id") not in {x.get("id") for x in all_works}]
                )
                if extra_works:
                    extra_parsed, extra_texts = [], []
                    for work in extra_works:
                        title = work.get("title")
                        if not title:
                            continue
                        abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
                        combined = f"{title}. {abstract}".strip()
                        extra_parsed.append({
                            "title": title, "abstract": abstract, "text": combined,
                            "date": work.get("publication_date", "No date"),
                            "doi": work.get("doi"),
                            "concepts": [c.get("display_name", "") for c in work.get("concepts", [])[:3]],
                        })
                        extra_texts.append(combined)
                    if extra_texts:
                        extra_matrix = bi_model.encode(
                            extra_texts, convert_to_numpy=True,
                            normalize_embeddings=True, batch_size=32, show_progress_bar=False,
                        )
                        extra_sims = sk_cosine(query_vector, extra_matrix)[0]
                        for i, ep in enumerate(extra_parsed):
                            ep["bi_score"] = float(extra_sims[i])
                        all_pool = parsed_papers + extra_parsed
                        top_candidates = sorted(all_pool, key=lambda p: p["bi_score"], reverse=True)[:TOP_K_RERANK]

            top_candidates_count = len(top_candidates)

            ce_pairs = [[user_idea, p["text"]] for p in top_candidates]
            ce_scores_raw = ce_model.predict(ce_pairs, show_progress_bar=False)
            ce_scores = [1.0 / (1.0 + math.exp(-float(s))) for s in ce_scores_raw]

            eff_thresh_float = effective_threshold / 100.0
            final_results = []
            for i, paper in enumerate(top_candidates):
                bi_s = paper["bi_score"]
                ce_s = ce_scores[i]
                fused_s = calculate_fused_score(bi_s, ce_s)
                if fused_s >= CE_HARD_FLOOR and fused_s >= eff_thresh_float:
                    final_results.append({
                        "title": paper["title"], "abstract": paper["abstract"],
                        "date": paper["date"], "doi": paper["doi"],
                        "fused": fused_s, "bi_pct": bi_s, "ce_pct": ce_s,
                        "concepts": paper["concepts"],
                    })
            final_results.sort(key=lambda x: x["fused"], reverse=True)
            displayed = final_results[:max_display]

    # ── Build academic results with sentence-level highlight views ──────────
    hl_threshold = highlight_threshold_pct / 100.0
    academic_results = []
    for rank, r in enumerate(displayed, 1):
        full_text = (r["title"] + ". " + r["abstract"]).strip() if r["abstract"] else r["title"]
        view = build_sentence_view(full_text, query_vector, bi_model, hl_threshold)
        academic_results.append({
            "rank": rank,
            "title": r["title"],
            "abstract": r["abstract"],
            "date": r["date"],
            "doi": r["doi"],
            "fused_pct": r["fused"] * 100,
            "bi_pct": r["bi_pct"] * 100,
            "ce_pct": r["ce_pct"] * 100,
            "concepts": r["concepts"],
            "sentence_view": view,
        })

    # ── Build patent results with sentence-level highlight views ────────────
    eff_thresh_float = effective_threshold / 100.0
    patents_to_show = [p for p in ranked_patents if p["fused"] >= CE_HARD_FLOOR][:max_display]
    patent_results = []
    for rank, pat in enumerate(patents_to_show, 1):
        view = build_sentence_view(pat["abstract"], query_vector, bi_model, hl_threshold) if pat["abstract"] else None
        pub_num = pat["publication_number"]
        patent_results.append({
            "rank": rank,
            "publication_number": pub_num,
            "title": pat["title"],
            "abstract": pat["abstract"],
            "publication_date": pat["publication_date"] or None,
            "cpc_codes": pat.get("cpc_codes") or [],
            "fused_pct": pat["fused"] * 100,
            "bi_pct": pat["bi_score"] * 100,
            "ce_pct": pat["ce_score"] * 100,
            "google_patents_url": f"https://patents.google.com/patent/US{pub_num}" if pub_num else None,
            "sentence_view": view,
        })

    # ── Global Patentability & Novelty Report ────────────────────────────────
    global_report_payload = None
    if enable_global_report:
        combined_docs = []
        for r in displayed:
            combined_docs.append({"title": r["title"], "abstract": r["abstract"],
                                   "source": "academic paper", "fused": r["fused"]})
        for p in (ranked_patents or []):
            combined_docs.append({"title": p["title"], "abstract": p["abstract"],
                                   "source": "patent", "fused": p["fused"]})
        combined_docs.sort(key=lambda d: d["fused"], reverse=True)
        top_docs = combined_docs[:GLOBAL_REPORT_TOP_N]

        if not top_docs:
            global_report_payload = {"available": False, "reason": "no_documents", "report": None, "error": None}
        else:
            report_doc_tuple = tuple((d["title"], d["abstract"], d["source"]) for d in top_docs)
            result = await fetch_global_report(user_idea, report_doc_tuple)
            global_report_payload = {
                "available": result.get("report") is not None,
                "reason": None,
                "report": result.get("report"),
                "error": result.get("error"),
                "n_academic": sum(1 for d in top_docs if d["source"] == "academic paper"),
                "n_patent": sum(1 for d in top_docs if d["source"] == "patent"),
                "n_total": len(top_docs),
            }

    elapsed_s = round(time.time() - t0, 2)

    return {
        "elapsed_s": elapsed_s,
        "classifier": classifier_info,
        "yake_keyphrases": yake_keyphrases,
        "keyword_fallback_terms": kw_fallback_terms,
        "concepts": concepts,
        "arm_d": {
            "enabled": enable_arm_d,
            "extraction": arm_d_extraction,
            "error": arm_d_error,
            "new_candidate_count": len(arm_d_new),
        },
        "retrieval": {
            "mode": retrieval_mode,
            "source_breakdown": src,
            "total_after_merge": len(all_works),
            "max_bi_score": max_bi_in_pool,
            "auto_supplement_triggered": auto_supplement_triggered,
            "top_candidates_for_rerank": top_candidates_count,
        },
        "academic": {
            "pipeline_ran": oa_pipeline_ran,
            "effective_threshold": effective_threshold,
            "results": academic_results,
        },
        "patent": {
            "enabled": enable_patent_search,
            "source": patent_source,
            "error": patent_error,
            "diagnostics": patent_diags,
            "raw_hit_count": sum(d.get("hit_count", 0) for d in patent_diags),
            "after_dedup_count": len(patent_records),
            "after_rerank_count": len(ranked_patents),
            "keyphrases_used": list(patent_kw_tuple),
            "results": patent_results,
        },
        "global_report": global_report_payload,
    }
