"""
Node 1 — Query Parser (Real Estate vertical — locked)
======================================================
AgentReach only finds ONE thing: real estate agents & brokerages.
This node does NOT parse business_type from free text — the product
is intentionally locked to the real estate niche (that focus is what
makes it easy to sell vs. a generic "find any business" tool).

What it DOES still parse from natural language:
  - location                (city + state/country)
  - radius_km                (search radius)
  - max_results
  - specialization_filter   (optional — "luxury", "commercial", "new
    construction", etc. if the user mentions one — used later to bias
    scoring, never to hide results)
  - team_filter             (optional — "brokerage", "team", "solo agent" —
    same idea, a soft signal not a hard filter)

Set LLM_MODEL in your .env using "provider:model" format.
For Ollama models that contain colons in the name (e.g. qwen2.5:3b),
use LLM_PROVIDER + LLM_MODEL separately:

  # Simple providers (no colon in model name):
  LLM_MODEL=openai:gpt-4o-mini
  LLM_MODEL=groq:llama-3.1-8b-instant
  LLM_MODEL=anthropic:claude-haiku-3-5

  # Ollama (model names often contain colons like qwen2.5:3b):
  LLM_PROVIDER=ollama
  LLM_MODEL=qwen2.5:3b          ← just the model, no provider prefix
  LLM_MODEL=phi4-mini
  LLM_MODEL=gemma2:2b
"""

import os
import json
import re
import logging

from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import LeadState

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
_LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").strip().lower()
_LLM_MODEL_ENV = os.getenv("LLM_MODEL", "openai:gpt-4o-mini").strip()
_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_KNOWN_PROVIDERS = {
    "openai", "anthropic", "google_genai", "google_vertexai",
    "groq", "mistralai", "cohere", "fireworks", "together",
    "bedrock", "bedrock_converse", "azure_openai", "nvidia",
    "perplexity", "xai", "deepseek",
}


def _resolve_model_and_provider() -> tuple[str, str | None]:
    if _LLM_PROVIDER:
        return _LLM_MODEL_ENV, _LLM_PROVIDER
    parts = _LLM_MODEL_ENV.split(":", 1)
    if len(parts) == 2 and parts[0].lower() in _KNOWN_PROVIDERS:
        return parts[1], parts[0].lower()
    return _LLM_MODEL_ENV, None


_MODEL_NAME, _MODEL_PROVIDER = _resolve_model_and_provider()

logger.info(f"[parse_query] init_chat_model → model={_MODEL_NAME!r}  provider={_MODEL_PROVIDER!r}")

_extra_kwargs: dict = {}
if _MODEL_PROVIDER == "ollama":
    _extra_kwargs["base_url"] = _OLLAMA_BASE_URL

_llm = init_chat_model(
    _MODEL_NAME,
    model_provider=_MODEL_PROVIDER,
    configurable_fields=("model", "model_provider"),
    temperature=0,
    **_extra_kwargs,
)

# ── Prompt — locked to the real estate vertical ────────────────────────────────
SYSTEM_PROMPT = """You are the query parser for AgentReach, a tool that ONLY
finds real estate agents and brokerages (never any other business type).

Convert the user's query into a JSON object with EXACTLY these keys:

{
  "location":               "<city + state/country for Google Maps, e.g. 'Austin, TX'>",
  "radius_km":               <number, default 25, increase to 60-100 for 'area'/'metro'/'region' queries>,
  "max_results":             <integer 20-500, default 100>,
  "specialization_filter":   "<one of: luxury, commercial, new_construction, relocation,
                                first_time_buyer, waterfront, land, vacation_rental,
                                senior_55plus, none — pick 'none' if not mentioned>",
  "team_filter":             "<one of: solo, team, brokerage, none — pick 'none' if not mentioned>"
}

Rules:
- Ignore any business type in the query other than real estate agents/brokerages —
  this tool is single-purpose and always searches for real estate agents & brokerages.
- For tri-state / metro area queries: use the largest city + radius_km 80-100.
- Respond with ONLY valid JSON — no markdown fences, no explanation.
"""

# ── Rule-based fallback ───────────────────────────────────────────────────────
_US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC",
}

_SPECIALIZATION_KWS = {
    "luxury":            ["luxury", "high-end", "high end", "estate homes"],
    "commercial":        ["commercial"],
    "new_construction":  ["new construction", "new build", "new homes"],
    "relocation":        ["relocation", "relocating"],
    "first_time_buyer":  ["first-time buyer", "first time buyer"],
    "waterfront":        ["waterfront", "beachfront", "lakefront"],
    "land":              ["land", "acreage", "farm"],
    "vacation_rental":   ["vacation rental", "short-term rental", "str"],
    "senior_55plus":     ["55+", "senior living", "retirement community"],
}

_TEAM_KWS = {
    "solo":      ["solo agent", "independent agent", "individual agent"],
    "team":      ["team", "group of agents"],
    "brokerage": ["brokerage", "firm", "agency"],
}


def _detect_kw(query: str, table: dict[str, list[str]]) -> str:
    q = query.lower()
    for key, kws in table.items():
        if any(kw in q for kw in kws):
            return key
    return "none"


def _rule_based_parse(query: str) -> dict:
    """Offline fallback — no LLM required."""
    location = query

    m = re.search(r"\bin\s+([A-Za-z\s,]+?)(?:\s+with|\s+near|\s+that|$)", query, re.I)
    location_phrase = m.group(1).strip() if m else query

    # Scan the location phrase for a trailing state code, walking from the
    # END backward. State codes almost always terminate a location phrase
    # ("... in New York NY"), and scanning the isolated phrase (rather than
    # the full query) avoids the preposition "in" itself colliding with the
    # abbreviation for Indiana. Join ALL preceding words (not just one) so
    # multi-word cities like "New York" aren't truncated to "York".
    phrase_words = location_phrase.split()
    for i in range(len(phrase_words) - 1, 0, -1):
        word = phrase_words[i].strip(",.").upper()
        if word in _US_STATES:
            city = " ".join(w.strip(",.") for w in phrase_words[:i]).title()
            location = f"{city}, {word}"
            break
    else:
        location = location_phrase

    parsed = {
        "location":              location,
        "radius_km":             25,
        "max_results":           100,
        "specialization_filter": _detect_kw(query, _SPECIALIZATION_KWS),
        "team_filter":           _detect_kw(query, _TEAM_KWS),
    }
    logger.info(f"[parse_query] rule-based → {parsed}")
    return parsed


# ── Node ──────────────────────────────────────────────────────────────────────
def parse_query_node(state: LeadState) -> LeadState:
    query = state["raw_query"]
    logger.info(f"[parse_query] model={_MODEL_NAME!r} provider={_MODEL_PROVIDER!r} query='{query}'")

    parsed: dict | None = None

    try:
        response = _llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=query),
        ])

        content = response.content.strip()
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.MULTILINE)
        content = re.sub(r"\s*```\s*$",        "", content, flags=re.MULTILINE)

        parsed = json.loads(content)
        logger.info(f"[parse_query] LLM result → {parsed}")

    except Exception as e:
        logger.warning(f"[parse_query] LLM failed ({e}) — rule-based fallback")
        parsed = _rule_based_parse(query)

    return {
        **state,
        # business_type is intentionally fixed — AgentReach is single-purpose.
        "business_type":         "real estate agent & brokerage",
        "location":              str(parsed.get("location", query)),
        "radius_km":             float(parsed.get("radius_km", 25)),
        "enrichment_reqs":       ["email", "specialization", "team_size"],
        "max_results":           int(parsed.get("max_results", 100)),
        "specialization_filter": str(parsed.get("specialization_filter", "none") or "none").lower(),
        "team_filter":           str(parsed.get("team_filter", "none") or "none").lower(),
        "retry_count":           0,
        "max_retries":           state.get("max_retries", 3),
        "status":                "running",
    }
