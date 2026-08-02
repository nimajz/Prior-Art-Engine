# ============================================================
# SECTION 3 — QUERY ANALYSIS: INPUT CLASSIFIER (ported 1:1)
# ============================================================

import re


def classify_input(text: str) -> dict:
    words = text.lower().split()
    word_count = len(words)

    acronyms = re.findall(r'\b[A-Z]{2,5}\b', text)
    acronym_density = len(acronyms) / max(word_count, 1)

    domain_tokens = {
        "iot", "lorawan", "mqtt", "zigbee", "coap", "firmware", "telemetry",
        "apm", "fps", "latency", "bandwidth", "throughput", "embedded",
        "toxic", "toxicity", "gaming", "gameplay", "esport", "streamer",
        "twitch", "fomo", "tiktok", "instagram", "reddit", "twitter",
        "sentiment", "frustration", "player", "leaderboard", "mmr",
        "waste", "sanitation", "landfill", "bin", "municipal",
    }
    text_lower = text.lower()
    domain_hit_count = sum(1 for tok in domain_tokens if tok in text_lower)

    force_keyword_arm = (
        word_count < 8
        or acronym_density > 0.15
        or domain_hit_count >= 2
    )

    return {
        "word_count": word_count,
        "acronym_density": round(acronym_density, 3),
        "domain_hit_count": domain_hit_count,
        "force_keyword_arm": force_keyword_arm,
    }
