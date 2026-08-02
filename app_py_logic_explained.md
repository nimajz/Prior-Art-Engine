# How `app.py` Finds the Closest Prior Art — Full Logic Walkthrough

This document explains, completely and in order, how the Streamlit program
`app.py` (v11 "LLM-Guided Hybrid" Prior Art Validation Engine) takes a free-text
description of a research idea and returns the most similar academic papers and
patents. It is written for an AI reader: every stage, data structure, and
scoring formula used in the pipeline is described explicitly, in the order the
code actually executes them.

---

## 1. What the program is

Given a block of user text describing an idea, the app tries to find the
**closest existing academic works (via OpenAlex)** and **closest existing US
patents (via PatentsView)**, rank them by semantic similarity to the user's
text, and — optionally — ask an LLM (Gemini 2.5 Flash) to (a) extract a
structured Problem/Method summary to drive an extra retrieval pass, and (b)
write a single qualitative "distinctiveness" narrative comparing the idea to
the best-matching documents found. It explicitly labels that narrative as
**not** a legal patentability opinion.

The retrieval side uses five parallel "arms" that all feed into one shared
candidate pool, which is then filtered by a two-stage semantic reranker
(bi-encoder → cross-encoder). Patents are scored with the same reranker but
kept in a separate pool/tab because they are a structurally different
document type.

---

## 2. Global constants that shape behavior

These are set once at the top of the file and control every downstream stage:

| Constant | Purpose |
|---|---|
| `BI_ENCODER_ID = "BAAI/bge-small-en-v1.5"` | Fast embedding model used to cheaply score *all* candidates first. |
| `BGE_QUERY_PREFIX` | BGE models require queries to be prefixed with an instruction string before encoding; this is that prefix. |
| `CE_MODEL_ID = "cross-encoder/ms-marco-MiniLM-L-6-v2"` | Slower, more accurate model used only on the shortlist that survives bi-encoder scoring. |
| `CE_HARD_FLOOR = 0.10` | Absolute minimum fused score a result must clear to ever be shown, regardless of the user-configurable threshold slider. |
| `OPENALEX_FETCH = 100` | Max works fetched per OpenAlex query. |
| `CONCEPT_TOP_N = 5` | Number of OpenAlex "concepts" (topic-graph nodes) kept after fusion-ranking. |
| `HIGHLIGHT_COSINE_THRESH = 0.78` | Default per-sentence highlight threshold (also user-adjustable in the sidebar). |
| `TOP_K_RERANK = 20` | How many bi-encoder-scored academic candidates are promoted to the expensive cross-encoder stage. |
| `MAX_CONCURRENT_REQS = 4` | Semaphore bound on concurrent async HTTP calls (OpenAlex, PatentsView, Gemini). |
| `CONCEPT_ARM_MIN_VIABLE = 10` | (documented threshold, referenced conceptually for concept-arm viability) |
| `PATENT_MAX_RESULTS = 25`, `PATENT_TOP_K_RERANK = 10` | Same idea as above but for the patent arm. |
| `ARM_D_CANDIDATE_QUOTA = 40`, `ARM_D_TIMEOUT_S = 20.0` | Cap on how many OpenAlex works ARM D (Gemini-guided) can inject into the pool, and its time budget. |
| `GLOBAL_REPORT_TOP_N = 5`, `GLOBAL_REPORT_TIMEOUT_S = 25.0` | How many top-ranked documents (across both academic + patent pools) are shown to Gemini for the final narrative report. |

The device (`cuda` or `cpu`) is auto-detected once via `torch.cuda.is_available()`.

---

## 3. End-to-end pipeline, in execution order

The moment the user types something into the `st.text_area`, this sequence runs:

```
user_idea (raw text)
   │
   ├─▶ Step 1: classify_input()              → word/acronym/domain stats
   ├─▶ Step 1: extract_keyword_fallback()     → ARM C keyword list
   ├─▶ Step 1: extract_yake_keyphrases()      → Layer 1 keyphrases (also reused by ARM PV)
   │
   ├─▶ Step 2: fetch_openalex_concepts()      → Layer 2/3 concept graph (ARM A input)
   │
   ├─▶ Step 2B: fetch_arm_d()                 → Gemini Problem/Method + 3 OpenAlex searches (ARM D)
   │
   ├─▶ Step 3: orchestrate_retrieval()        → runs ARM A, ARM B, ARM C, merges + dedups → all_works
   │        └─▶ ARM D candidates merged in afterward (deduped against all_works)
   │
   ├─▶ Step 4: bi_model.encode(user_idea)     → query_vector (shared by academic + patent scoring)
   │
   ├─▶ Step P: fetch_patents_patentsview()    → ARM PV raw patent records
   │        └─▶ rerank_patents_with_ce()      → bi-encoder + cross-encoder on patents
   │
   ├─▶ Step 5–7: academic bi-encoder scoring, auto-supplement, cross-encoder rerank, threshold filter
   │
   ├─▶ Section 12: render two tabs — Academic results / Patent results
   │
   └─▶ Section 13: fetch_global_report()      → single Gemini call over top-N combined docs
```

Each stage is expanded below.

---

## 4. Step 1 — Text analysis (classifier + two keyword extractors)

### 4.1 `classify_input(text)`
Purely rule-based, no ML. Computes:
- `word_count` — naive whitespace split.
- `acronym_density` — count of regex matches `\b[A-Z]{2,5}\b` divided by word count.
- `domain_hit_count` — how many terms from a hardcoded set of niche domain
  words (IoT/networking terms, gaming/social-media terms, waste-management
  terms) appear in the lowercased text.
- `force_keyword_arm` — `True` if the text is short (<8 words), OR acronym-dense
  (>15%), OR hits ≥2 domain terms. This flag doesn't gate anything directly in
  the current orchestrator (ARM C runs unless the user explicitly restricts to
  "Concept-Based Only"), but it is surfaced in the debug panel as a signal for
  why keyword fallback matters for this particular input.

### 4.2 `extract_yake_keyphrases(text)` — Layer 1
Uses the YAKE library (unsupervised statistical keyword extraction, n-grams
up to 3 words) to pull up to 25 candidate phrases, then:
1. Filters out phrases where every token is a stopword, or the phrase is only
   digits/punctuation (`_is_high_signal`).
2. Deduplicates near-identical phrases by token-set overlap ≥ 0.65
   (`_dedup_phrases`) — e.g. "energy harvesting system" and "energy harvesting"
   would collapse to one.
3. If fewer than 3 phrases survive, backfills with raw non-stopword words from
   the text.
4. Returns up to 10 final phrases.

These keyphrases are reused in **three** different places later: OpenAlex
concept lookup (Layer 2), the PatentsView query (ARM PV), and nowhere else —
ARM D uses its own Gemini-derived strings instead.

### 4.3 `extract_keyword_fallback(text)` — ARM C source
A simpler, stricter extractor (ported from an earlier version of the app):
lowercases, regex-extracts words of length ≥4, removes a *larger* stopword
set (`_KW_STOPWORDS`, which is `_YAKE_STOPWORDS` plus extra generic ML/paper
words like "learning", "framework", "algorithm"), dedupes while preserving
order, and returns up to 6 words. These are precision keywords meant to
directly hit OpenAlex's full-text search even when YAKE's phrase extraction
misses on short or jargon-heavy input.

---

## 5. Step 2 — OpenAlex concept graph (Layer 2/3, feeds ARM A)

`fetch_openalex_concepts(idea_text, top_n=5)` is cached (`st.cache_data`,
1 hour TTL) and runs an async pipeline under the hood via a background thread
with its own event loop (`fetch_openalex_concepts` → `_async_fetch_concepts`
executed inside `_run_in_thread`, since Streamlit's own loop can't be reused
for async work safely).

Logic of `_async_fetch_concepts`:
1. Re-derives YAKE keyphrases from the idea text.
2. Builds `full_text_tokens` — all non-stopword words ≥4 chars in the raw text,
   used later for overlap-checking.
3. For **each** keyphrase, fires a concurrent (semaphore-bounded, max 4)
   `GET /concepts?search=<phrase>` request to OpenAlex (`_query_concept_strict`).
4. **Strict filter** on each returned concept:
   - Must have `level` between 2 and 4 (OpenAlex's concept hierarchy — avoids
     both overly broad top-level concepts and overly narrow leaf concepts).
   - Must have token overlap OR substring overlap between the concept's name
     and (the keyphrase tokens ∪ the full-text tokens). This prevents
     accepting an OpenAlex concept that only loosely string-matched the search
     query.
5. Each surviving concept gets a fused score via `_fuse_concept_score`:
   ```
   cite_score   = log1p(cited_by) / log1p(1_000_000)      # normalizes citation count
   level_weight = max(0.55, 1.0 - |level-3| * 0.12)        # prefers mid-level concepts (level 3)
   rank_bonus   = 1 / sqrt(combined_rank)                  # rewards concepts found by higher-ranked keyphrases/results
   score = cite_score * level_weight * rank_bonus
   ```
6. If **no** candidates survive the strict pass across all keyphrases, a
   **relaxed retry** (`_query_concept_relaxed`) is run on just the top 3
   keyphrases — same query, but skips the token/substring overlap filter
   entirely (keeps the level-2–4 filter only).
7. `_fuse_and_rank_concepts` deduplicates by concept ID (keeping the
   highest-scoring occurrence of each), sorts descending by fused score, and
   returns the top `top_n` (5) concepts as `{name, id, cited_by, level}` dicts.

This concept list is what powers **ARM A**.

---

## 6. Step 3 — The three OpenAlex retrieval arms + orchestration

`orchestrate_retrieval(user_idea, concepts, classifier_info, retrieval_mode, kw_fallback_terms)`
runs up to three independent OpenAlex queries depending on the sidebar's
"Retrieval Strategy" radio button (`Concept + Full-Text (Recommended)`,
`Full-Text Only`, or `Concept-Based Only`):

- **ARM A — `fetch_works_by_concepts`**: filters OpenAlex `/works` by
  `concepts.id:` (OR-joined concept IDs from Step 2), sorted by citation
  count descending. If the combined filter query returns fewer than 20 works,
  it falls back to querying each concept ID individually and merges/dedupes,
  up to `per_page` total. Runs when mode is "Concept + Full-Text" or
  "Concept-Based Only", and only if concepts exist.

- **ARM B — `fetch_works_fulltext_yake`**: a plain OpenAlex `/works?search=`
  full-text query using the first 500 characters of the raw user idea text
  (not the keyphrases — the whole text). Runs when mode is "Concept + Full-Text"
  or "Full-Text Only", OR automatically whenever there are no concepts, OR
  automatically whenever ARM A returned fewer than 60 works (a safety net so
  a weak concept arm doesn't starve the pool).

- **ARM C — `fetch_works_keyword_fallback`**: OpenAlex `/works?search=` using
  the space-joined precision keywords from Step 1.3. This arm is **always
  active** unless the user explicitly selects "Concept-Based Only" mode.
  (Per the header comment: "ARM C always runs... Results are deduped
  downstream so there is no double-counting penalty.")

All three result lists are merged and deduplicated by `deduplicate_works`,
which keys on `work["id"]`, falling back to `doi`, falling back to `title`, and
keeps only first-seen entries. The function returns `(all_works, source_breakdown)`
where `source_breakdown` records how many works each arm contributed (used
only for the debug panel).

---

## 7. Step 2B — ARM D: Gemini-guided Problem/Method retrieval

This runs **before** Step 3 merges the pool, but architecturally it's a
fourth independent source that gets folded into `all_works` right after
`orchestrate_retrieval` returns. Entry point: `fetch_arm_d(user_idea)`, a
cached synchronous wrapper around `_async_run_arm_d`, executed (like the
concept fetch) inside its own thread + event loop.

### 7.1 Extraction call — `_call_gemini_for_extraction`
- Skips immediately (raises `ValueError`) if `GEMINI_API_KEY` is unset or
  still a placeholder (`"YOUR_..."`).
- Sends a prompt to `gemini-2.5-flash` instructing it to output **only**
  JSON matching `_EXTRACTION_SCHEMA`: `{"Problem": string, "Method": string}`.
  - `Problem` = a dense 1–3 sentence statement of the gap/problem being solved.
  - `Method` = a concise description of the proposed solution/technique.
- Uses Gemini's native structured-output mode
  (`responseMimeType: application/json`, `responseSchema`) rather than
  hoping the model free-forms valid JSON.
- **Important quirk handled explicitly**: `gemini-2.5-flash` is a "thinking"
  model — by default it spends part of its token budget on invisible internal
  reasoning before emitting the visible JSON, and `maxOutputTokens` caps that
  *combined* budget. If the internal reasoning eats the whole budget, the
  visible output gets truncated mid-string (observed bug:
  `"Unterminated string starting at: line 1 column 13"`). The fix, applied via
  `_gemini_json_generation_config`:
  1. `thinkingConfig.thinkingBudget = 0` — disables internal reasoning tokens
     entirely, so the full budget goes to visible output.
  2. `responseSchema` — constrains generation to valid, schema-complete JSON.
  3. Generous `maxOutputTokens` (1024 for extraction, 2048 for the global
     report) well above realistic JSON size.
- `_extract_gemini_text` pulls the text out of `candidates[0].content.parts`
  and, if it's empty, inspects `finishReason` to give a precise diagnostic
  (e.g. explicitly flags `MAX_TOKENS` truncation) instead of a bare parse
  error.
- After extraction, code strips any stray Markdown code fences, `json.loads`
  the result, and requires both `Problem` and `Method` to be non-empty
  strings — otherwise raises `ValueError`.

### 7.2 Targeted search — `_arm_d_openalex_search` × 3 (concurrent)
Once `{Problem, Method}` is extracted, three OpenAlex `/works?search=` queries
run concurrently (semaphore-bounded):
1. `Problem` alone (25 results)
2. `Method` alone (25 results)
3. `f"{Problem} {Method}"` combined (20 results) — meant to catch documents
   sitting at the *intersection* of both concepts.

### 7.3 Merge and cap
Results from all three searches are deduplicated (by `id` → `doi` → `title`
fallback, same pattern as everywhere else) and capped at
`ARM_D_CANDIDATE_QUOTA` (40) unique works.

### 7.4 Failure handling
Any exception anywhere in this chain (bad key, HTTP error, timeout, JSON
parse failure, missing fields) is caught and converted into
`(works=[], extraction=None, error=str)`. The rest of the app continues
normally — ARM D is best-effort and never blocks or crashes the pipeline. In
the UI, if `extraction` succeeded it's displayed in a dedicated purple
"ARM D" card; if it failed for a reason *other than* the placeholder-key case,
a soft warning is shown; if it failed *because* of the placeholder key, it's
silently skipped (no scary warning for a simply-unconfigured feature).

### 7.5 Merging into the global pool
Back in the main script body, after `orchestrate_retrieval()` returns
`all_works`, any `arm_d_works` are deduplicated against the existing pool
(same `id`/`doi`/`title` key logic) and appended. This final merged list is
what feeds the bi-encoder stage.

---

## 8. Step 4 — Query embedding

The raw user idea is prefixed with the BGE instruction string
(`"Represent this sentence for searching relevant passages: "`) and encoded
once with the bi-encoder into a single normalized vector, `query_vector`. This
same vector is reused for: academic bi-encoder scoring, patent bi-encoder
scoring, and all sentence-level highlight computations later. Embeddings are
L2-normalized (`normalize_embeddings=True`), which is what makes a plain dot
product equivalent to cosine similarity downstream.

---

## 9. Step P — ARM PV: PatentsView (USPTO) patent search

Runs independently of the OpenAlex arms, reusing the **same YAKE keyphrases**
computed in Step 1 (no re-extraction). Entry point:
`fetch_patents_patentsview(keyphrases_tuple)`, again a cached thread-wrapped
async call.

### 9.1 Strategy A — one query per keyphrase
For each of the first 8 keyphrases, builds a PatentsView v1 JSON query of the
form:
```json
{"_or": [
  {"_text_any": {"patent_title": "<phrase>"}},
  {"_text_any": {"patent_abstract": "<phrase>"}}
]}
```
and fires it as a `GET` to `https://search.patentsview.org/api/v1/patent/`
with `f=patent_id,patent_title,patent_abstract,patent_date,cpc.cpc_subclass_id`
and `o={"per_page":10,"matched_subentities_only":true}`. All 8 requests run
concurrently (semaphore-bounded to 4). Every request's outcome (status code,
error text, hit count) is logged into a `diagnostics` list regardless of
success/failure, which powers the "ARM PV Debug" panel in the UI.

### 9.2 Strategy B — merged fallback
If Strategy A's combined raw hit count is under 5 (and there was more than
one keyphrase), a second query is built by `_build_patentsview_query`, which
joins the first 8 keyphrases into one combined search string and OR-merges
title/abstract search on that combined string, cast as a single request. This
catches cases where individual short phrases are too narrow to hit anything
alone.

### 9.3 Normalization and dedup
Each raw hit is passed through `_parse_patentsview_record`, which maps the v1
API's field names (`patent_id`, `cpc[]` singular) onto a canonical internal
schema used everywhere else in the app: `publication_number, title, abstract,
publication_date, filing_date, assignee, country_code, cpc_codes`. Records are
deduplicated on `patent_id`/`patent_number`, then capped at
`PATENT_MAX_RESULTS` (25).

### 9.4 Reranking — `rerank_patents_with_ce`
Identical two-stage cascade to the academic pipeline, applied separately:
1. Concatenate `title + ". " + abstract` (or just title if no abstract) per
   patent → `texts`.
2. Bi-encode all patent texts in one batch, compute cosine similarity against
   `query_vector` → `bi_score` per patent.
3. Sort by `bi_score` descending, keep top `PATENT_TOP_K_RERANK` (10).
4. Cross-encode `[user_idea, patent_text]` pairs for that shortlist, convert
   raw logits to probabilities via sigmoid: `1 / (1 + e^-s)` → `ce_score`.
5. Compute `fused` score per patent via `calculate_fused_score` (see §11.3
   below — same formula used for academic results).
6. Re-sort by `fused` descending; return the list.

If the cross-encoder call itself throws, `ce_scores` degrades to all zeros
rather than crashing the app.

---

## 10. Step 5–7 — Academic bi-encoder → cross-encoder pipeline

This only runs if `all_works` (the merged ARM A+B+C+D pool) is non-empty.

### 10.1 Parsing
For each raw OpenAlex work: skip if no title. Reconstruct the abstract from
OpenAlex's *inverted index* format via `reconstruct_abstract` — OpenAlex
stores abstracts as `{word: [positions...]}` rather than plain text (to
comply with copyright/licensing constraints on abstract redistribution); the
function flattens `(position, word)` pairs, sorts by position, and joins them
back into a normal string. Builds `combined = f"{title}. {abstract}"` per
work.

### 10.2 Bi-encoder batch scoring
All `combined` texts are encoded in one batch (`batch_size=32`), cosine
similarity against `query_vector` computed via `sklearn.cosine_similarity`,
stored as `bi_score` per paper. A `st.progress` bar tracks this.

### 10.3 Top-K pruning
Sorts all parsed papers by `bi_score` descending, keeps only the top
`TOP_K_RERANK` (20) — this is the expensive-stage shortlist.

### 10.4 Auto-supplement safety net
If the **best** bi-encoder score in that shortlist is below 0.45, **and**
ARM C wasn't already active in this run, **and** keyword fallback terms
exist: the app treats this as a sign the primary arms found nothing
semantically close, and re-runs `fetch_works_keyword_fallback` as a rescue
query. New (non-duplicate) works are parsed, bi-encoded, and merged into the
candidate pool before re-selecting the top-20 shortlist. This is logged in
the debug panel as "Auto-supplement triggered."

### 10.5 Cross-encoder reranking
For the (possibly supplemented) top-20, builds `[user_idea, paper_text]`
pairs and runs them through the MS-MARCO cross-encoder — a model that jointly
attends over both texts (much more accurate than independently-embedded
cosine similarity, but too slow to run on the full candidate pool). Raw
logits are converted to `[0,1]` via sigmoid.

### 10.6 Fused scoring and filtering — `calculate_fused_score`
```python
def calculate_fused_score(bi_score, ce_score, w_bi=0.35, w_ce=0.65):
    bi_safe = max(bi_score, 0.001)
    ce_safe = max(ce_score, 0.001)
    return 1.0 / ((w_bi / bi_safe) + (w_ce / ce_safe))
```
This is a **weighted harmonic mean** of the bi-encoder and cross-encoder
scores, weighted 35%/65% in favor of the cross-encoder (since it's the more
reliable signal). A harmonic mean (vs. arithmetic) means a paper can't score
well overall by being strong on just one metric and weak on the other — both
signals have to be reasonably good. The `max(x, 0.001)` guards avoid
division-by-zero for a score of exactly 0.

A result is kept only if `fused >= CE_HARD_FLOOR` (0.10, an absolute floor)
**and** `fused >= effective_threshold` (the user's sidebar slider, default
25%). Kept results are sorted by `fused` descending and truncated to
`max_display` (sidebar slider, default 5) for the UI.

---

## 11. Sentence-level highlighting (used for both academic and patent cards)

For each displayed result, the app doesn't just show an overall match score —
it highlights *which sentences* of the abstract are actually close to the
user's idea:

1. `split_into_sentences` — regex-splits on sentence-ending punctuation
   followed by whitespace, discards fragments ≤8 characters.
2. `_cached_sentence_embeddings` — bi-encodes all sentences of one document
   (cached by the tuple of sentences, so repeat renders are free).
3. `compute_sentence_highlights` — cosine-similarity each sentence vector
   against `query_vector`; returns a boolean list of "is this sentence above
   the highlight threshold" (sidebar-adjustable, default 78%).
4. `build_highlighted_html` — wraps highlighted sentences in a colored
   `<span>` (amber background) and non-highlighted ones in muted gray, joined
   into one HTML blob rendered via `st.markdown(..., unsafe_allow_html=True)`.
5. `find_best_matching_sentence` — separately finds the single
   highest-cosine-similarity sentence and its score, shown as a "Most Similar
   Sentence to Your Input" callout beneath the highlighted abstract.

The same four functions are reused verbatim for patent abstracts.

---

## 12. Section 13 — Global Patentability & Novelty Report

This is the **one** LLM step that runs *after* all retrieval/reranking is
finished (as opposed to ARM D, which runs *before* and *feeds* retrieval).

### 12.1 Building the input document set
Takes the `displayed` academic results (already filtered/sorted by `fused`)
and `ranked_patents` (patents that cleared `CE_HARD_FLOOR`), tags each with
its `source` ("academic paper" or "patent"), merges both lists, re-sorts by
`fused` descending across *both* types together, and keeps only the top
`GLOBAL_REPORT_TOP_N` (5) documents overall — regardless of which tab they
came from.

### 12.2 The Gemini call — `_call_gemini_global_report`
- Same placeholder-key guard as ARM D.
- Formats the top-N documents into a numbered block of
  `[i] (source) Title \n Abstract: ...` via `_format_docs_for_global_prompt`.
- Sends one prompt asking Gemini to score three axes, each an **integer 1–5**
  with a **multi-sentence narrative reason**, evaluated against the documents
  *collectively as a landscape* (not per-document):
  - `global_utility_score` — how practically distinct the idea is against the
    combined set (1 = redundant, 5 = clearly distinct).
  - `global_novelty_score` — how much of the idea's content is *not* already
    covered anywhere across the set (1 = landscape covers nearly all of it,
    5 = landscape covers very little).
  - `global_combination_score` — how "obvious" a combination of existing
    elements in the set would be to arrive at the idea (1 = straightforward
    combination, 5 = not straightforward).
- The prompt explicitly instructs the model **not** to write as if issuing a
  legal conclusion, and to stay strictly grounded in the provided text
  blocks.
- Same structured-output + `thinkingBudget: 0` + fenced-code-stripping +
  JSON-parsing pattern as ARM D. Additionally validates that each returned
  score is an integer in `[1, 5]`, raising `ValueError` otherwise (caller
  catches this and shows a graceful failure state).

### 12.3 Failure isolation
`fetch_global_report` is cached and thread-wrapped exactly like the other
Gemini calls. Any failure (missing key, timeout, malformed JSON, out-of-range
score) results in `{"report": None, "error": "..."}`, and the UI shows a
dedicated "unavailable" box — this is architected as a single, isolated
failure point that **cannot** affect the retrieval/ranking results already
computed and displayed above it.

### 12.4 Rendering
If successful: shows a source breakdown caption (N academic / N patent docs
assessed), three `st.metric` score tiles, and three narrative reasoning blocks
— always preceded by a fixed, prominent disclaimer box stating this is not a
patentability or legal opinion and that a registered patent attorney should
be consulted before any filing/investment/disclosure decision.

---

## 13. UI structure (Section 11–13 of the code)

- **Sidebar**: sliders for `max_display`, `effective_threshold`,
  `highlight_threshold_pct`; a `show_debug` checkbox; a `retrieval_mode` radio;
  checkboxes to toggle `enable_patent_search`, `enable_arm_d`,
  `enable_global_report`.
- **Main body**: single `st.text_area` for the idea. Everything below only
  executes `if user_idea:` is truthy.
- **Two tabs** (`st.tabs`): "📚 Academic Prior Art" (renders `displayed`
  academic results with match badges, DOI links, concept pills, and the
  highlighted-abstract + best-sentence callout) and "🗂️ Patent Prior Art"
  (renders `patents_to_show` with a debug panel of per-keyphrase PatentsView
  diagnostics, patent number, CPC classification codes, a Google Patents
  link, and the same highlighted-abstract treatment).
- **Below both tabs**: the Global Report container (Section 13, described
  above), always visible as long as `user_idea` is set, independent of which
  tab is active.
- **Debug mode** (`show_debug`), when on, additionally renders: the raw
  classifier stats, the YAKE keyphrase pills, the ARM C keyword pills, the
  OpenAlex concept table, an arm-contribution summary line (`ARM A: n +
  ARM B: n + ARM C: n + ARM PV: enabled/disabled + ARM D: n new candidates`),
  the auto-supplement warning (if triggered), the pruned-candidate-count line,
  and per-result bi-encoder/cross-encoder raw score annotations.

---

## 14. Caching and concurrency model, summarized

Every external-API-calling function that doesn't need to run synchronously in
the Streamlit render loop is wrapped the same way:
1. The "real" logic is an `async def` function using `httpx.AsyncClient` and
   `asyncio.gather` for concurrent sub-requests, bounded by an
   `asyncio.Semaphore(MAX_CONCURRENT_REQS)`.
2. A synchronous wrapper spins up a **new OS thread**, creates a **fresh
   asyncio event loop** inside it, runs the async function to completion via
   `loop.run_until_complete(...)`, and joins the thread with a timeout. This
   avoids clashing with (or trying to reuse) any event loop Streamlit itself
   might be managing.
3. The synchronous wrapper is decorated with `@st.cache_data(ttl=3600, ...)`,
   so repeated calls with identical arguments within an hour return instantly
   from cache instead of re-hitting external APIs. (This is why arguments like
   `concept_ids`, `keyphrases`, and `docs` are passed as **tuples**, not lists
   — `st.cache_data` requires hashable arguments.)
4. Every wrapper degrades gracefully on total failure or thread timeout,
   returning an empty/`None` result plus an error string rather than raising
   an exception that would crash the whole Streamlit script.

This pattern is applied identically to: OpenAlex concept fetch (§6), ARM D
(§7), PatentsView fetch (§9), and the Global Report (§12).

---

## 15. One-paragraph summary

The app extracts keyphrases/keywords from the user's text with two different
rule-based extractors (YAKE for phrases, a stricter word-list extractor for
precision keywords), maps those to an OpenAlex concept-graph and to raw
full-text/keyword searches (three parallel "arms"), optionally asks Gemini to
distill the input into a formal Problem/Method pair and searches OpenAlex
again on that (a fourth arm), and separately queries the PatentsView USPTO API
using the same keyphrases (a fifth, patent-specific arm). All non-patent
candidates are merged into one deduplicated pool and scored in two stages —
first cheaply with a bi-encoder (cosine similarity) to prune to a shortlist,
then expensively with a cross-encoder (joint attention) for accurate
reranking — and the two scores are combined via a weighted harmonic mean into
a single "fused" percentage used for filtering and sorting. Patents go through
an identical bi-encoder/cross-encoder cascade but are kept in a separate pool
and UI tab. Finally, once both pools are ranked, a single Gemini call reads
the titles/abstracts of the very best academic + patent results combined and
writes a three-axis (utility/novelty/non-obviousness) narrative assessment,
explicitly and repeatedly labeled as not a legal patentability opinion.
