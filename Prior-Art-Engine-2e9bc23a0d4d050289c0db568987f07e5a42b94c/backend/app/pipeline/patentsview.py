# ============================================================
# SECTION 7P — ARM PV: PATENTSVIEW API PATENT SEARCH (USPTO)
# Ported 1:1 from the original app.py. The Streamlit-specific
# background-thread + own-event-loop wrapper is removed because
# FastAPI request handlers are already async — the query-building,
# field mapping, dedup, and reranking logic is unchanged.
# ============================================================

import asyncio
import json
import math
import re

import httpx
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine

from app.core.config import (
    PATENTSVIEW_URL, PATENTSVIEW_FIELDS, USER_AGENT,
    MAX_CONCURRENT_REQS, PATENT_MAX_RESULTS, PATENT_TOP_K_RERANK,
)
from app.core.cache import async_ttl_cache
from app.pipeline.openalex import calculate_fused_score


def _build_patentsview_query(keyphrases: list) -> str:
    safe_phrases = [
        re.sub(r'["\\\n\r\t]', " ", kp).strip()
        for kp in keyphrases
        if kp and kp.strip()
    ]
    if not safe_phrases:
        safe_phrases = ["invention method system"]
    combined = " ".join(safe_phrases[:8])
    return json.dumps({
        "_or": [
            {"_text_any": {"patent_title": combined}},
            {"_text_any": {"patent_abstract": combined}},
        ]
    })


async def _fetch_one_patentsview_page(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    query_str: str,
    per_page: int,
) -> tuple:
    params = {
        "q": query_str,
        "f": PATENTSVIEW_FIELDS,
        "o": json.dumps({"per_page": per_page, "matched_subentities_only": True}),
    }
    async with semaphore:
        try:
            resp = await client.get(PATENTSVIEW_URL, params=params, timeout=25.0)
            if resp.status_code != 200:
                try:
                    err_body = resp.text[:300]
                except Exception:
                    err_body = "(unreadable)"
                return [], resp.status_code, f"HTTP {resp.status_code}: {err_body}"
            data = resp.json()
            records = data.get("patents") or []
            return records, 200, None
        except httpx.TimeoutException:
            return [], 0, "Request timed out"
        except httpx.RequestError as exc:
            return [], 0, f"Network error: {exc}"
        except ValueError as exc:
            return [], 0, f"JSON decode error: {exc}"


def _parse_patentsview_record(raw: dict) -> dict:
    patent_number = (raw.get("patent_id") or raw.get("patent_number") or "").strip()
    cpc_raw = raw.get("cpc") or raw.get("cpcs") or []
    cpc_codes = list({
        c.get("cpc_subclass_id", "") for c in cpc_raw
        if c.get("cpc_subclass_id")
    })
    pub_date = (raw.get("patent_date") or "").strip()
    filing_date = ""

    return {
        "publication_number": patent_number,
        "title": (raw.get("patent_title") or "No title").strip(),
        "abstract": (raw.get("patent_abstract") or "").strip(),
        "publication_date": pub_date,
        "filing_date": filing_date,
        "assignee": "",
        "country_code": "US",
        "cpc_codes": cpc_codes,
    }


async def _async_fetch_patents(keyphrases: list, top_n: int = PATENT_MAX_RESULTS) -> tuple:
    if not keyphrases:
        return [], [{"phrase": "(none)", "status_code": 0, "error": "No keyphrases", "hit_count": 0}]

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQS)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    diagnostics: list = []

    async with httpx.AsyncClient(headers=headers, timeout=25.0) as client:
        tasks = []
        phrase_list = keyphrases[:8]
        for phrase in phrase_list:
            safe = re.sub(r'["\\\n\r\t]', " ", phrase).strip()
            query_str = json.dumps({
                "_or": [
                    {"_text_any": {"patent_title": safe}},
                    {"_text_any": {"patent_abstract": safe}},
                ]
            })
            tasks.append(
                _fetch_one_patentsview_page(client, semaphore, query_str, per_page=10)
            )
        results = await asyncio.gather(*tasks, return_exceptions=False)

    raw_hits: list = []
    for phrase, (records, status, err) in zip(phrase_list, results):
        diagnostics.append({
            "phrase": phrase, "status_code": status, "error": err, "hit_count": len(records),
        })
        raw_hits.extend(records or [])

    if len(raw_hits) < 5 and len(keyphrases) > 1:
        merged_str = _build_patentsview_query(keyphrases)
        async with httpx.AsyncClient(headers=headers, timeout=25.0) as client:
            extras, status_b, err_b = await _fetch_one_patentsview_page(
                client, semaphore, merged_str, per_page=top_n
            )
        diagnostics.append({
            "phrase": "(merged fallback)", "status_code": status_b,
            "error": err_b, "hit_count": len(extras or []),
        })
        raw_hits.extend(extras or [])

    seen_ids: set = set()
    unique_records: list = []
    for raw in raw_hits:
        pid = (raw.get("patent_id") or raw.get("patent_number") or "").strip()
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            unique_records.append(_parse_patentsview_record(raw))

    return unique_records[:top_n], diagnostics


@async_ttl_cache(ttl_seconds=3600)
async def fetch_patents_patentsview(keyphrases: tuple) -> tuple:
    """Returns (patent_records, source_label, error_msg, diagnostics)."""
    if not keyphrases:
        return [], "patentsview", "No keyphrases extracted — skipping patent search.", []
    try:
        records, diags = await asyncio.wait_for(
            _async_fetch_patents(list(keyphrases), top_n=PATENT_MAX_RESULTS), timeout=60.0
        )
        return records, "patentsview", None, diags
    except asyncio.TimeoutError:
        return [], "error", "PatentsView request timed out after 60 s.", []
    except Exception as exc:
        return [], "error", str(exc), []


def rerank_patents_with_ce(
    user_idea: str,
    patent_records: list,
    bi_model,
    ce_model,
    query_vector,
    top_k: int = PATENT_TOP_K_RERANK,
) -> list:
    if not patent_records:
        return []

    texts = [
        (r["title"] + ". " + r["abstract"]).strip()
        if r["abstract"] else r["title"]
        for r in patent_records
    ]

    doc_matrix = bi_model.encode(
        texts, convert_to_numpy=True,
        normalize_embeddings=True, batch_size=32, show_progress_bar=False,
    )
    bi_sims = sk_cosine(query_vector, doc_matrix)[0]

    pool = []
    for i, rec in enumerate(patent_records):
        pool.append({**rec, "text": texts[i], "bi_score": float(bi_sims[i])})

    pool.sort(key=lambda x: x["bi_score"], reverse=True)
    top = pool[:top_k]

    ce_pairs = [[user_idea, p["text"]] for p in top]
    try:
        ce_scores_raw = ce_model.predict(ce_pairs, show_progress_bar=False)
        ce_scores = [1.0 / (1.0 + math.exp(-float(s))) for s in ce_scores_raw]
    except Exception:
        ce_scores = [0.0] * len(top)

    for i, rec in enumerate(top):
        rec["ce_score"] = ce_scores[i]
        rec["fused"] = calculate_fused_score(rec["bi_score"], ce_scores[i])

    top.sort(key=lambda x: x["fused"], reverse=True)
    return top
