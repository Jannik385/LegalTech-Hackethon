"""Markdown summarization service.

Summarizes .md files into a structured legal summary by calling the
OpenRouter API.

Single-file path  → flat summary + key_facts (unchanged behaviour).
Combined overview → topic-based structure with per-side key points.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel
from openrouter import OpenRouter

from backend.config import MODEL, OPENROUTER_API_KEY

# ---------------------------------------------------------------------------
# Output template (single-file path — unchanged)
# ---------------------------------------------------------------------------

SUMMARY_TEMPLATE = """\
=== Zusammenfassung: {filename} ===

{summary}

--- Key Facts ---
{key_facts}

=================
"""

# Separator inserted between individual files in the combined overview
_FILE_SEPARATOR = "\n\n---\n\n"

# ---------------------------------------------------------------------------
# Pydantic result models
# ---------------------------------------------------------------------------


class TopicPoint(BaseModel):
    """Key points for one side within a topic."""
    side: str           # name / label of the side (derived from filename)
    points: list[str]   # bullet points for this side on this topic


class Topic(BaseModel):
    """A single contested topic with opposing viewpoints."""
    title: str              # short topic title
    sides: list[TopicPoint] # always two entries: [side_a, side_b]


class SummaryResult(BaseModel):
    filename: str
    summary: str
    # Flat list kept for backward-compat with the single-file path and linker
    key_facts: list[str]
    template_output: str
    # Structured topics — only populated for the combined overview
    topics: list[Topic] = []


# ---------------------------------------------------------------------------
# Single-file prompts & parsing (unchanged)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "Du bist ein juristischer Dokumentenanalyst. "
    "Analysiere den übergebenen Markdown-Text und liefere zwei Dinge:\n"
    "1. Einen zusammenhängenden Zusammenfassungs-Paragraphen auf Deutsch "
    "(maximal 5 Sätze, Schlüssel: \"summary\").\n"
    "2. Eine Liste von bis zu 7 zentralen Fakten / Kernaussagen als Stichpunkte "
    "auf Deutsch (Schlüssel: \"key_facts\", Wert: Array von Strings, "
    "jeder String ohne führendes Aufzählungszeichen).\n"
    "Antworte ausschließlich mit einem JSON-Objekt mit den Feldern "
    "\"summary\" (String) und \"key_facts\" (Array von Strings). Kein weiterer Text."
)


def _user_prompt(filename: str, content: str) -> str:
    excerpt = content[:12_000]
    if len(content) > 12_000:
        excerpt += "\n\n[... Dokument gekürzt ...]"
    return (
        f'Dateiname: "{filename}"\n\n'
        f"Inhalt:\n{excerpt}"
    )


def _parse_response(raw: str) -> tuple[str, list[str]]:
    """Parse flat summary + key_facts JSON from a single-file response."""
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    try:
        data = json.loads(cleaned)
        summary = str(data.get("summary", "")).strip()
        raw_facts = data.get("key_facts", [])
        key_facts = [str(f).strip() for f in raw_facts if str(f).strip()]
        return summary, key_facts
    except (json.JSONDecodeError, AttributeError):
        return raw.strip(), []


# ---------------------------------------------------------------------------
# Combined-overview prompts & parsing (topic-based, two sides)
# ---------------------------------------------------------------------------

def _overview_system_prompt(side_a: str, side_b: str) -> str:
    return (
        "Du bist ein juristischer Dokumentenanalyst. "
        "Du erhältst zwei Dokumente, die gegensätzliche Standpunkte zu einem Thema darstellen: "
        f'Seite A heißt \"{side_a}\" und Seite B heißt \"{side_b}\".\n\n'
        "Deine Aufgabe:\n"
        "1. Identifiziere die 3–6 wichtigsten strittigen Themen / Streitpunkte.\n"
        "2. Formuliere für jedes Thema jeweils 2–4 konkrete Kernargumente für Seite A "
        "und 2–4 konkrete Kernargumente für Seite B — auf Deutsch, präzise, ohne "
        "Aufzählungszeichen.\n"
        "3. Schreibe außerdem einen kurzen übergreifenden Zusammenfassungs-Paragraph "
        "(maximal 4 Sätze, Schlüssel: \"summary\").\n\n"
        "Antworte ausschließlich mit einem JSON-Objekt in diesem exakten Format "
        "(kein weiterer Text, keine Markdown-Umrandung):\n"
        "{\n"
        "  \"summary\": \"<Zusammenfassungs-Paragraph>\",\n"
        "  \"topics\": [\n"
        "    {\n"
        "      \"title\": \"<Thementitel>\",\n"
        "      \"sides\": [\n"
        f'        {{ \"side\": \"{side_a}\", \"points\": [\"<Punkt 1>\", \"<Punkt 2>\"] }},\n'
        f'        {{ \"side\": \"{side_b}\", \"points\": [\"<Punkt 1>\", \"<Punkt 2>\"] }}\n'
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}"
    )


def _overview_user_prompt(side_a: str, content_a: str, side_b: str, content_b: str) -> str:
    def _excerpt(text: str) -> str:
        t = text[:10_000]
        if len(text) > 10_000:
            t += "\n\n[... Dokument gekürzt ...]"
        return t

    return (
        f"## Dokument Seite A: {side_a}\n\n{_excerpt(content_a)}\n\n"
        f"---\n\n"
        f"## Dokument Seite B: {side_b}\n\n{_excerpt(content_b)}"
    )


def _parse_overview_response(raw: str, side_a: str, side_b: str) -> tuple[str, list[Topic], list[str]]:
    """Parse topic-structured JSON from the combined-overview response.

    Returns (summary, topics, flat_key_facts).
    flat_key_facts is a fallback list derived from all points, used by the
    linker's text-search pass.
    """
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError):
        # Graceful fallback: treat raw text as a flat summary
        return raw.strip(), [], []

    summary = str(data.get("summary", "")).strip()
    topics: list[Topic] = []
    flat_facts: list[str] = []

    for t in data.get("topics", []):
        title = str(t.get("title", "")).strip()
        sides: list[TopicPoint] = []
        for s in t.get("sides", []):
            side_name = str(s.get("side", "")).strip()
            points = [str(p).strip() for p in s.get("points", []) if str(p).strip()]
            sides.append(TopicPoint(side=side_name, points=points))
            flat_facts.extend(points)
        if title and sides:
            topics.append(Topic(title=title, sides=sides))

    return summary, topics, flat_facts


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


def _render_template(filename: str, summary: str, key_facts: list[str]) -> str:
    facts_block = "\n".join(f"• {fact}" for fact in key_facts) if key_facts else "(keine Key Facts extrahiert)"
    return SUMMARY_TEMPLATE.format(
        filename=filename,
        summary=summary,
        key_facts=facts_block,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def summarize_all_md(files: dict[str, str]) -> SummaryResult:
    """Summarize all Markdown files as one topic-structured combined overview.

    Expects exactly two files (the two opposing sides).  If more than two are
    provided the first two are used as side A / B and the rest are appended to
    side B's content.  If only one file is provided it falls back to the
    single-file path.
    """
    if len(files) == 0:
        raise ValueError("Keine Dateien übergeben.")

    if len(files) == 1:
        fname, content = next(iter(files.items()))
        return summarize_md(fname, content)

    items = list(files.items())
    side_a_name, content_a = items[0]
    side_b_name = items[1][0]
    # Merge any additional files into side B
    content_b = _FILE_SEPARATOR.join(c for _, c in items[1:])

    messages = [
        {"role": "system", "content": _overview_system_prompt(side_a_name, side_b_name)},
        {"role": "user",   "content": _overview_user_prompt(side_a_name, content_a, side_b_name, content_b)},
    ]

    with OpenRouter(api_key=OPENROUTER_API_KEY) as client:
        res = client.chat.send(model=MODEL, messages=messages, stream=False)

    raw = res.choices[0].message.content or ""
    summary, topics, flat_facts = _parse_overview_response(raw, side_a_name, side_b_name)
    template_output = _render_template("Gesamtübersicht", summary, flat_facts)

    return SummaryResult(
        filename="Gesamtübersicht",
        summary=summary,
        key_facts=flat_facts,
        template_output=template_output,
        topics=topics,
    )


def summarize_md(filename: str, content: str) -> SummaryResult:
    """Summarize a single Markdown file and return a SummaryResult."""
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user",   "content": _user_prompt(filename, content)},
    ]

    with OpenRouter(api_key=OPENROUTER_API_KEY) as client:
        res = client.chat.send(model=MODEL, messages=messages, stream=False)

    raw = res.choices[0].message.content or ""
    summary, key_facts = _parse_response(raw)
    template_output = _render_template(filename, summary, key_facts)

    return SummaryResult(
        filename=filename,
        summary=summary,
        key_facts=key_facts,
        template_output=template_output,
    )
