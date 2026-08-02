# ============================================================
# SECTION 6 — OPENALEX CONCEPT PIPELINE (ported 1:1)
# SECTION 7 — RETRIEVAL ARMS A, B, C (ported 1:1; sync `requests`
#             calls converted to async `httpx` calls — same params,
#             same logic, same fallbacks, just non-blocking)
# SECTION 8 — ORCHESTRATOR: THREE-TIER RETRIEVAL LADDER
# SECTION 9 — ABSTRACT RECONSTRUCTION & UTILITIES
# ============================================================

import asyncio
import math
import re

import httpx

from app.core.config import (
    OPENALEX_CONCEPTS_URL, OPENALEX_WORKS_URL, USER_AGENT, SELECT_FIELDS,
    MAX_CONCURRENT_REQS, OPENALEX_FETCH, CONCEPT_TOP_N,
)
from app.core.cache import async_ttl_cache
from app.pipeline.keyphrases import extract_yake_keyphrases
from app.core.stopwords import YAKE_STOPWORDS


# ── Section 6 — concept fusion scoring ──────────────────────────────────────

def _fuse_concept_score(cited_by: int, level: int, query_rank: int) -> float:
    cite_score = math.log1p(max(cited_by, 0)) / math.log1p(1_000_000)
    level_weight = max(0.55, 1.0 - abs(level - 3) * 0.12)
    rank_bonus = 1.0 / math.sqrt(max(query_rank, 1))
    return cite_score * level_weight * rank_bonus


async def _query_concept_strict(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    phrase: str,
    phrase_rank: int,
    full_text_tokens: frozenset,
) -> list:
    async with semaphore:
        try:
            resp = await client.get(
                OPENALEX_CONCEPTS_URL,
                params={"search": phrase, "per_page": 3,
                        "select": "id,display_name,cited_by_count,level"},
                timeout=12.0,
            )
            if resp.status_code != 200:
                return []
            results = resp.json().get("results", [])
            enriched = []
            phrase_tokens = set(phrase.lower().split())
            combined_tokens = phrase_tokens | full_text_tokens
            for local_rank, item in enumerate(results, start=1):
                raw_id = item.get("id", "")
                short_id = raw_id.split("/")[-1] if "/" in raw_id else raw_id
                if not short_id:
                    continue
                cited = item.get("cited_by_count", 0)
                level = item.get("level", 3)
                if level < 2 or level > 4:
                    continue
                concept_name = item.get("display_name", "").lower()
                concept_tokens = set(concept_name.split())
                has_token_overlap = bool(combined_tokens & concept_tokens)
                has_substr_match = any(
                    pt in concept_name for pt in combined_tokens if len(pt) > 4
                )
                if not (has_token_overlap or has_substr_match):
                    continue
                combined_rank = phrase_rank * 3 + local_rank
                enriched.append({
                    "name": item.get("display_name", ""),
                    "id": short_id,
                    "cited_by": cited,
                    "level": level,
                    "_score": _fuse_concept_score(cited, level, combined_rank),
                })
            return enriched
        except (httpx.TimeoutException, httpx.RequestError):
            return []


async def _query_concept_relaxed(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    phrase: str,
    phrase_rank: int,
) -> list:
    async with semaphore:
        try:
            resp = await client.get(
                OPENALEX_CONCEPTS_URL,
                params={"search": phrase, "per_page": 3,
                        "select": "id,display_name,cited_by_count,level"},
                timeout=12.0,
            )
            if resp.status_code != 200:
                return []
            results = resp.json().get("results", [])
            enriched = []
            for local_rank, item in enumerate(results, start=1):
                raw_id = item.get("id", "")
                short_id = raw_id.split("/")[-1] if "/" in raw_id else raw_id
                if not short_id:
                    continue
                cited = item.get("cited_by_count", 0)
                level = item.get("level", 3)
                if level < 2 or level > 4:
                    continue
                combined_rank = phrase_rank * 3 + local_rank
                enriched.append({
                    "name": item.get("display_name", ""),
                    "id": short_id,
                    "cited_by": cited,
                    "level": level,
                    "_score": _fuse_concept_score(cited, level, combined_rank),
                })
            return enriched
        except (httpx.TimeoutException, httpx.RequestError):
            return []


def _fuse_and_rank_concepts(candidates: list, top_n: int) -> list:
    best: dict = {}
    for c in candidates:
        cid = c["id"]
        if cid not in best or c["_score"] > best[cid]["_score"]:
            best[cid] = c
    ranked = sorted(best.values(), key=lambda x: x["_score"], reverse=True)
    return [
        {"name": c["name"], "id": c["id"],
         "cited_by": c["cited_by"], "level": c["level"]}
        for c in ranked[:top_n]
    ]


async def _async_fetch_concepts(idea_text: str, top_n: int) -> list:
    if not idea_text or not idea_text.strip():
        return []
    keyphrases = extract_yake_keyphrases(idea_text)
    if not keyphrases:
        return []
    full_text_tokens = frozenset(
        w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", idea_text)
        if w.lower() not in YAKE_STOPWORDS
    )
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQS)
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(headers=headers, timeout=12.0) as client:
        tasks = [
            _query_concept_strict(client, semaphore, ph, rank, full_text_tokens)
            for rank, ph in enumerate(keyphrases, 1)
        ]
        nested = await asyncio.gather(*tasks)
    all_candidates = [item for sub in nested for item in sub]
    if not all_candidates:
        async with httpx.AsyncClient(headers=headers, timeout=12.0) as client:
            retry_tasks = [
                _query_concept_relaxed(client, semaphore, ph, rank)
                for rank, ph in enumerate(keyphrases[:3], 1)
            ]
            nested2 = await asyncio.gather(*retry_tasks)
        all_candidates = [item for sub in nested2 for item in sub]
    if not all_candidates:
        return []
    return _fuse_and_rank_concepts(all_candidates, top_n)


@async_ttl_cache(ttl_seconds=3600)
async def fetch_openalex_concepts(idea_text: str, top_n: int = CONCEPT_TOP_N) -> list:
    return await _async_fetch_concepts(idea_text, top_n)


# ── Section 7 — retrieval arms A, B, C ──────────────────────────────────────

@async_ttl_cache(ttl_seconds=3600)
async def fetch_works_by_concepts(concept_ids: tuple, per_page: int = OPENALEX_FETCH) -> list:
    if not concept_ids:
        return []
    headers = {"User-Agent": USER_AGENT}
    params = {
        "filter": "concepts.id:" + "|".join(concept_ids),
        "per_page": per_page,
        "sort": "cited_by_count:desc",
        "select": SELECT_FIELDS,
    }
    try:
        async with httpx.AsyncClient(headers=headers, timeout=20.0) as client:
            resp = await client.get(OPENALEX_WORKS_URL, params=params)
            if resp.status_code == 200:
                works = resp.json().get("results", [])
                if len(works) >= 20:
                    return works
                all_works: list = list(works)
                seen_ids = {w.get("id") for w in works}
                for cid in concept_ids:
                    try:
                        r2 = await client.get(
                            OPENALEX_WORKS_URL,
                            params={"filter": f"concepts.id:{cid}",
                                    "per_page": max(20, per_page // len(concept_ids)),
                                    "sort": "cited_by_count:desc", "select": SELECT_FIELDS},
                            timeout=15.0,
                        )
                        if r2.status_code == 200:
                            for w in r2.json().get("results", []):
                                wid = w.get("id")
                                if wid and wid not in seen_ids:
                                    seen_ids.add(wid)
                                    all_works.append(w)
                    except Exception:
                        continue
                return all_works[:per_page]
    except Exception:
        pass
    return []


@async_ttl_cache(ttl_seconds=3600)
async def fetch_works_fulltext_yake(idea_summary: str, per_page: int = OPENALEX_FETCH) -> list:
    headers = {"User-Agent": USER_AGENT}
    params = {
        "search": idea_summary[:500],
        "per_page": per_page,
        "select": SELECT_FIELDS,
    }
    try:
        async with httpx.AsyncClient(headers=headers, timeout=20.0) as client:
            resp = await client.get(OPENALEX_WORKS_URL, params=params)
            if resp.status_code == 200:
                return resp.json().get("results", [])
    except Exception:
        pass
    return []


@async_ttl_cache(ttl_seconds=3600)
async def fetch_works_keyword_fallback(keywords: tuple, per_page: int = OPENALEX_FETCH) -> list:
    if not keywords:
        return []
    headers = {"User-Agent": USER_AGENT}
    search_str = " ".join(keywords)
    params = {
        "search": search_str,
        "per_page": per_page,
        "select": SELECT_FIELDS,
    }
    try:
        async with httpx.AsyncClient(headers=headers, timeout=20.0) as client:
            resp = await client.get(OPENALEX_WORKS_URL, params=params)
            if resp.status_code == 200:
                return resp.json().get("results", [])
    except Exception:
        pass
    return []


# ── Section 8 — orchestrator: three-tier retrieval ladder ───────────────────

async def orchestrate_retrieval(
    user_idea: str,
    concepts: list,
    classifier_info: dict,
    retrieval_mode: str,
    kw_fallback_terms: list,
) -> tuple:
    concept_works = []
    fulltext_works = []
    keyword_works = []

    if retrieval_mode in ["Concept + Full-Text (Recommended)", "Concept-Based Only"] and concepts:
        concept_ids = tuple(c["id"] for c in concepts)
        concept_works = await fetch_works_by_concepts(concept_ids, per_page=OPENALEX_FETCH)

    run_fulltext = (
        retrieval_mode in ["Concept + Full-Text (Recommended)", "Full-Text Only"]
        or not concepts
        or len(concept_works) < 60
    )
    if run_fulltext:
        fulltext_works = await fetch_works_fulltext_yake(user_idea, per_page=OPENALEX_FETCH)

    run_keyword_arm = retrieval_mode != "Concept-Based Only"
    if run_keyword_arm and kw_fallback_terms:
        keyword_works = await fetch_works_keyword_fallback(
            tuple(kw_fallback_terms), per_page=OPENALEX_FETCH
        )

    all_works = deduplicate_works(concept_works + fulltext_works + keyword_works)

    source_breakdown = {
        "concept": len(concept_works),
        "fulltext": len(fulltext_works),
        "keyword": len(keyword_works),
        "total": len(all_works),
        "arm_c_active": run_keyword_arm,
    }
    return all_works, source_breakdown


# ── Section 9 — abstract reconstruction & utilities ─────────────────────────

def reconstruct_abstract(inverted_index) -> str:
    if not inverted_index or not isinstance(inverted_index, dict):
        return ""
    try:
        positions = [(pos, word) for word, pos_list in inverted_index.items()
                     for pos in pos_list]
        positions.sort()
        return " ".join(word for _, word in positions)
    except Exception:
        return ""


def deduplicate_works(works: list) -> list:
    seen: set = set()
    unique = []
    for w in works:
        key = w.get("id") or w.get("doi") or w.get("title", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(w)
    return unique


def calculate_fused_score(bi_score: float, ce_score: float,
                           w_bi: float = 0.35, w_ce: float = 0.65) -> float:
    bi_safe = max(bi_score, 0.001)
    ce_safe = max(ce_score, 0.001)
    return 1.0 / ((w_bi / bi_safe) + (w_ce / ce_safe))
