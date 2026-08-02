# ============================================================
# SECTION 7D — ARM D: LLM-GUIDED PROBLEM/METHOD ALIGNMENT (Gemini 2.5 Flash)
# SECTION 7E — GLOBAL PATENTABILITY & NOVELTY REPORT (Gemini-assisted)
# Ported 1:1 from the original app.py. Streamlit thread/event-loop
# wrappers removed (FastAPI handlers are already async); all prompts,
# schemas, scoring rules, and guardrails are unchanged.
# ============================================================

import asyncio
import json
import re

import httpx

from app.core.config import (
    GEMINI_API_KEY, GEMINI_MODEL, GEMINI_BASE_URL,
    ARM_D_CANDIDATE_QUOTA, ARM_D_TIMEOUT_S,
    GLOBAL_REPORT_TIMEOUT_S,
    OPENALEX_WORKS_URL, USER_AGENT, SELECT_FIELDS, MAX_CONCURRENT_REQS,
)
from app.core.cache import async_ttl_cache


def _gemini_json_generation_config(schema: dict, max_output_tokens: int) -> dict:
    return {
        "temperature": 0.1,
        "maxOutputTokens": max_output_tokens,
        "responseMimeType": "application/json",
        "responseSchema": schema,
        "thinkingConfig": {"thinkingBudget": 0},
    }


_EXTRACTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "Problem": {"type": "STRING"},
        "Method": {"type": "STRING"},
    },
    "required": ["Problem", "Method"],
}


def _extract_gemini_text(data: dict) -> tuple:
    try:
        candidate = data["candidates"][0]
    except (KeyError, IndexError) as exc:
        raise ValueError(f"No candidates in Gemini response: {exc}") from exc

    finish_reason = candidate.get("finishReason")
    parts = candidate.get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts).strip()

    if not text:
        if finish_reason == "MAX_TOKENS":
            raise ValueError(
                "Gemini hit MAX_TOKENS before producing any visible output "
                "(likely consumed entirely by internal reasoning tokens — "
                "increase maxOutputTokens or check thinkingConfig)."
            )
        raise ValueError(f"Gemini returned no text. finishReason={finish_reason}")

    return text, finish_reason


async def _call_gemini_for_extraction(user_idea: str) -> dict:
    if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("YOUR_"):
        raise ValueError("GEMINI_API_KEY is not set — ARM D is disabled.")

    prompt = (
        "You are a precise technical analyst. Analyse the research description below "
        "and identify two things:\n"
        '  "Problem" : A dense, precise 1–3 sentence summary of the specific '
        "problem or knowledge gap the author addresses. Be domain-specific.\n"
        '  "Method"  : A concise description of the exact proposed solution, '
        "algorithm, system architecture, or methodology used to address it.\n\n"
        "Both fields must be non-empty.\n\n"
        f"Research description:\n{user_idea}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": _gemini_json_generation_config(_EXTRACTION_SCHEMA, max_output_tokens=1024),
    }
    url = f"{GEMINI_BASE_URL}/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    async with httpx.AsyncClient(timeout=ARM_D_TIMEOUT_S) as client:
        resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})

    if resp.status_code != 200:
        raise ValueError(f"Gemini HTTP {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    raw_text, finish_reason = _extract_gemini_text(data)

    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
    raw_text = re.sub(r"\s*```\s*$", "", raw_text).strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        hint = " (response was truncated at MAX_TOKENS)" if finish_reason == "MAX_TOKENS" else ""
        raise ValueError(f"Gemini JSON parse failed{hint}: {exc}") from exc

    problem = parsed.get("Problem", "").strip()
    method = parsed.get("Method", "").strip()
    if not problem or not method:
        raise ValueError(f"Gemini JSON missing non-empty 'Problem'/'Method'. Keys: {list(parsed.keys())}")
    return {"Problem": problem, "Method": method}


async def _arm_d_openalex_search(
    client: httpx.AsyncClient, semaphore: asyncio.Semaphore, search_str: str, per_page: int = 25,
) -> list:
    async with semaphore:
        try:
            resp = await client.get(
                OPENALEX_WORKS_URL,
                params={"search": search_str[:500], "per_page": per_page, "select": SELECT_FIELDS},
                timeout=15.0,
            )
            if resp.status_code == 200:
                return resp.json().get("results", [])
        except (httpx.TimeoutException, httpx.RequestError):
            pass
    return []


async def _async_run_arm_d(user_idea: str) -> tuple:
    try:
        extraction = await _call_gemini_for_extraction(user_idea)
    except Exception as exc:
        return [], None, str(exc)

    problem = extraction["Problem"]
    method = extraction["Method"]
    combined = f"{problem} {method}"

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQS)
    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(headers=headers, timeout=20.0) as client:
        batches = await asyncio.gather(
            _arm_d_openalex_search(client, semaphore, problem, per_page=25),
            _arm_d_openalex_search(client, semaphore, method, per_page=25),
            _arm_d_openalex_search(client, semaphore, combined, per_page=20),
            return_exceptions=False,
        )

    seen_ids: set = set()
    merged: list = []
    for batch in batches:
        for work in (batch or []):
            wid = work.get("id") or work.get("doi") or work.get("title", "")
            if wid and wid not in seen_ids:
                seen_ids.add(wid)
                merged.append(work)

    return merged[:ARM_D_CANDIDATE_QUOTA], extraction, None


@async_ttl_cache(ttl_seconds=3600)
async def fetch_arm_d(user_idea: str) -> tuple:
    """Returns (works, extraction, error)."""
    try:
        return await asyncio.wait_for(_async_run_arm_d(user_idea), timeout=ARM_D_TIMEOUT_S + 15)
    except asyncio.TimeoutError:
        return [], None, f"ARM D timed out after {ARM_D_TIMEOUT_S + 15:.0f} s."
    except Exception as exc:
        return [], None, str(exc)


# ── Section 7E — Global Patentability & Novelty Report ──────────────────────

_GLOBAL_REPORT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "global_utility_score": {"type": "INTEGER"},
        "global_utility_reason": {"type": "STRING"},
        "global_novelty_score": {"type": "INTEGER"},
        "global_novelty_reason": {"type": "STRING"},
        "global_combination_score": {"type": "INTEGER"},
        "global_combination_reason": {"type": "STRING"},
    },
    "required": [
        "global_utility_score", "global_utility_reason",
        "global_novelty_score", "global_novelty_reason",
        "global_combination_score", "global_combination_reason",
    ],
}

_GLOBAL_REPORT_FIELDS = (
    "global_utility_score", "global_novelty_score", "global_combination_score",
)


def _format_docs_for_global_prompt(docs: list) -> str:
    blocks = []
    for i, d in enumerate(docs, 1):
        abstract = (d.get("abstract") or "").strip() or "(no abstract available)"
        blocks.append(
            f"[{i}] ({d.get('source', 'document')}) {d.get('title', 'Untitled')}\n"
            f"    Abstract: {abstract}"
        )
    return "\n\n".join(blocks)


async def _call_gemini_global_report(user_idea: str, docs: list) -> dict:
    if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("YOUR_"):
        raise ValueError("GEMINI_API_KEY is not set.")
    if not docs:
        raise ValueError("No retrieved documents to assess against.")

    docs_block = _format_docs_for_global_prompt(docs)

    prompt = (
        "You are assisting with an early-stage, informal TEXTUAL COMPARISON between "
        "a user's idea and a COLLECTION of retrieved documents (the prior-art "
        "landscape this search engine discovered). This is NOT a legal "
        "patentability opinion — you cannot see patent claims, prosecution "
        "history, or the wider universe of prior art beyond what is listed below, "
        "so do not write as if rendering a legal conclusion. Base your answer "
        "strictly on the text blocks provided, and reason about the documents "
        "COLLECTIVELY as a landscape, not one at a time.\n\n"
        "Score the comparison on three axes, each 1–5 (integers only), with a "
        "multi-sentence narrative reason for each that references the landscape "
        "as a whole (which documents are closest, what they collectively cover, "
        "what they collectively miss):\n\n"
        '  "global_utility_score" — Considering all documents together, does the '
        "user idea describe a practically distinct application? 1 = appears "
        "redundant with this landscape, 5 = clearly distinct practical "
        "application relative to the entire set.\n\n"
        '  "global_novelty_score" — How much of the user idea\'s content is NOT '
        "already described anywhere across these documents, taken together? "
        "1 = the landscape collectively appears to already describe nearly all "
        "of it, 5 = the landscape collectively describes very little of it.\n\n"
        '  "global_combination_score" — Would assembling elements already '
        "present across this set of documents be a straightforward way to "
        "arrive at the user's idea? 1 = straightforward combination of what's "
        "already shown across these documents, 5 = not a straightforward "
        "combination based on this set.\n\n"
        "For each axis, give the integer score and a multi-sentence "
        "justification grounded in the documents listed.\n\n"
        f"USER IDEA:\n{user_idea}\n\n"
        f"TOP {len(docs)} RETRIEVED DOCUMENTS (the discovered prior-art landscape):\n"
        f"{docs_block}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": _gemini_json_generation_config(_GLOBAL_REPORT_SCHEMA, max_output_tokens=2048),
    }
    url = f"{GEMINI_BASE_URL}/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    async with httpx.AsyncClient(timeout=GLOBAL_REPORT_TIMEOUT_S) as client:
        resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})

    if resp.status_code != 200:
        raise ValueError(f"Gemini HTTP {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    raw_text, finish_reason = _extract_gemini_text(data)

    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
    raw_text = re.sub(r"\s*```\s*$", "", raw_text).strip()
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        hint = " (response was truncated at MAX_TOKENS)" if finish_reason == "MAX_TOKENS" else ""
        raise ValueError(f"Gemini JSON parse failed{hint}: {exc}") from exc

    out = {}
    for score_key in _GLOBAL_REPORT_FIELDS:
        reason_key = score_key.replace("_score", "_reason")
        score = int(parsed.get(score_key, 0))
        if not (1 <= score <= 5):
            raise ValueError(f"'{score_key}' value {score} out of 1-5 range.")
        reason = str(parsed.get(reason_key, "")).strip() or "No justification provided."
        out[score_key] = score
        out[reason_key] = reason
    return out


@async_ttl_cache(ttl_seconds=3600)
async def fetch_global_report(user_idea: str, docs: tuple) -> dict:
    """docs: tuple of (title, abstract, source) tuples. Returns {"report", "error"}."""
    if not docs:
        return {"report": None, "error": "No retrieved documents available to assess."}

    doc_dicts = [{"title": t, "abstract": a, "source": s} for (t, a, s) in docs]
    try:
        report = await asyncio.wait_for(
            _call_gemini_global_report(user_idea, doc_dicts), timeout=GLOBAL_REPORT_TIMEOUT_S + 15
        )
        return {"report": report, "error": None}
    except asyncio.TimeoutError:
        return {"report": None, "error": f"Global report timed out after {GLOBAL_REPORT_TIMEOUT_S + 15:.0f} s."}
    except Exception as exc:
        return {"report": None, "error": str(exc)}
