"""Markdown summarization service.

Summarizes .md files into a structured legal summary by calling the
OpenRouter API.

Single-file path  → flat summary + key_facts (unchanged behaviour).
Combined overview → topic-based structure with per-side key points.
"""

from __future__ import annotations

import json
import re
from typing import Literal

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


class MissingDocument(BaseModel):
    """Documents referenced in the text but not present as uploaded files."""
    side: str           # which party is missing this document
    items: list[str]    # list of missing document names/descriptions


class Topic(BaseModel):
    """A single contested topic with opposing viewpoints."""
    title: str              # short topic title
    sides: list[TopicPoint] # always two entries: [side_a, side_b]
    # Legal category — assigned by the LLM based on Formalia.md taxonomy
    category: Literal["formellrechtlich", "materiellrechtlich", "hauptverhandlung"] = "materiellrechtlich"
    # Paragraph citations the model relied on (may be empty for Hauptverhandlung)
    relevant_law: list[str] = []
    # Missing documents relevant to this specific topic, per side
    missing_documents: list[MissingDocument] = []


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

# Legal taxonomy derived from Formalia.md — injected verbatim into the system prompt
# so the model has an authoritative, paragraph-anchored reference for every category.
LEGAL_TAXONOMY = """
## Rechtliche Klassifikation (Formalia)

Ordne jeden Streitpunkt genau einer der folgenden drei Kategorien zu:

### 1. formellrechtlich
Betrifft die verfahrensrechtliche Wirksamkeit von Schriftsätzen, Zustellungen und Fristen.
Leitparagraphen:
- Ladung: § 377 ZPO; Ladungsfrist: §§ 214, 217 ZPO
- Zustellung: § 166 Abs. 1 ZPO
- Frist: § 222 Abs. 1 ZPO
- Verjährung: §§ 194–218 BGB

### 2. materiellrechtlich
Betrifft den materiellen Anspruch — was Rechte und Pflichten inhaltlich sind.
Untergliedert in:

**Minderung**
- Eröffnung des Mängelgewährleistungsrechts:
  - Wirksamer Mietvertrag: § 535 BGB
  - Mietmangel: § 534 BGB
  - Maßgeblicher Zeitpunkt (bei/nach Gebrauchsüberlassung): § 536 Abs. 1 BGB
  - Kein Ausschluss: vertraglich (§ 536b BGB), gesetzlich (Kenntnis § 536b BGB, unterlassene Mängelanzeige § 536c BGB)
- Rechtsfolge:
  - Herabsetzung des Mietzahlungsanspruchs (Minderungsquote nach aktueller Rspr. und Mietminderungstabellen)
  - Rückerstattung der ungeminderten Miete: § 812 BGB

**Rücktritt / Kündigung**
- Grundsätzlich: §§ 542 ff. BGB
- Vermieter — ordentlich: § 542 Abs. 1 BGB (beachte §§ 573, 573a BGB)
- Vermieter — außerordentlich fristlos: §§ 543 Abs. 1, 2 Nr. 2 und 3 BGB; § 569 Abs. 2 BGB
- Vermieter — außerordentlich befristet: § 580 BGB
- Mieter — ordentlich: § 542 Abs. 1 BGB
- Mieter — außerordentlich fristlos: §§ 543 Abs. 1, 2 Nr. 2 BGB; §§ 569 Abs. 1, 2 BGB
- Mieter — außerordentlich befristet: § 580 BGB

### 3. hauptverhandlung
Betrifft tatsächliche Vorgänge und Beweismittel im Verfahren — keine feste Paragraphenbindung.
Unterpunkte:
- Mündliche Verhandlung
- Beweisführung
- Zeugenaussagen (ggf. § 373 ZPO)
- Sachverständigengutachten (ggf. § 402 ZPO)
"""


def _overview_system_prompt(side_a: str, side_b: str, rag_context: str = "") -> str:
    rag_block = f"\n\n## Relevante Rechtsgrundlagen (aus Wissensbasis)\n{rag_context}" if rag_context else ""
    return (
        "Du bist ein juristischer Dokumentenanalyst, spezialisiert auf deutsches Mietrecht.\n"
        f"Du erhältst zwei Schriftsätze zu einem Mietrechtsstreit: "
        f'Seite A heißt \"{side_a}\", Seite B heißt \"{side_b}\".\n\n'
        + LEGAL_TAXONOMY
        + rag_block
        + "\n\n"
        "## Deine Aufgaben\n\n"
        "1. Identifiziere 3–6 zentrale Streitpunkte aus den Dokumenten.\n"
        "2. Weise jedem Streitpunkt genau eine Kategorie zu "
        "(formellrechtlich | materiellrechtlich | hauptverhandlung) "
        "gemäß der obigen Klassifikation.\n"
        "3. Formuliere für jeden Streitpunkt 2–4 Kernargumente für Seite A "
        "und 2–4 Kernargumente für Seite B — auf Deutsch, präzise, ohne Aufzählungszeichen.\n"
        "4. Liste für jeden Streitpunkt die herangezogenen Paragraphen auf "
        "(leer lassen bei hauptverhandlung wenn keine einschlägigen Normen).\n"
        "5. Erkenne fehlende Unterlagen pro Streitpunkt: Wenn ein Schriftsatz für diesen "
        "Streitpunkt auf ein Dokument verweist (z. B. Mietvertrag, Fotos, Gutachten), "
        "das nicht hochgeladen wurde, liste es im Feld 'missing_documents' des jeweiligen "
        "Streitpunkts für die betreffende Seite.\n"
        "6. Schreibe einen übergreifenden Zusammenfassungs-Paragraphen (max. 4 Sätze).\n\n"
        "## Ausgabeformat\n\n"
        "Antworte ausschließlich mit einem JSON-Objekt (kein weiterer Text, keine Markdown-Umrandung):\n"
        "{\n"
        '  "summary": "<Zusammenfassungs-Paragraph>",\n'
        '  "topics": [\n'
        '    {\n'
        '      "title": "<Streitpunkt-Titel>",\n'
        '      "category": "materiellrechtlich",\n'
        '      "relevant_law": ["§ 536 BGB", "§ 812 BGB"],\n'
        '      "sides": [\n'
        f'        {{"side": "{side_a}", "points": ["<Argument 1>", "<Argument 2>"]}},\n'
        f'        {{"side": "{side_b}", "points": ["<Argument 1>", "<Argument 2>"]}}\n'
        '      ],\n'
        '      "missing_documents": [\n'
        f'        {{"side": "{side_a}", "items": ["<fehlendes Dokument>"]}},\n'
        f'        {{"side": "{side_b}", "items": []}}\n'
        '      ]\n'
        '    }\n'
        '  ]\n'
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


_VALID_CATEGORIES = {"formellrechtlich", "materiellrechtlich", "hauptverhandlung"}


def _parse_overview_response(
    raw: str, side_a: str, side_b: str
) -> tuple[str, list[Topic], list[str]]:
    """Parse topic-structured JSON from the combined-overview response.

    Returns (summary, topics, flat_key_facts).
    Missing documents are now embedded inside each Topic object.
    flat_key_facts is derived from all topic points and used by the linker's
    text-search pass.
    """
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, AttributeError):
        return raw.strip(), [], []

    summary = str(data.get("summary", "")).strip()
    topics: list[Topic] = []
    flat_facts: list[str] = []

    for t in data.get("topics", []):
        title = str(t.get("title", "")).strip()
        raw_cat = str(t.get("category", "materiellrechtlich")).strip().lower()
        category = raw_cat if raw_cat in _VALID_CATEGORIES else "materiellrechtlich"
        relevant_law = [str(p).strip() for p in t.get("relevant_law", []) if str(p).strip()]
        sides: list[TopicPoint] = []
        for s in t.get("sides", []):
            side_name = str(s.get("side", "")).strip()
            points = [str(p).strip() for p in s.get("points", []) if str(p).strip()]
            sides.append(TopicPoint(side=side_name, points=points))
            flat_facts.extend(points)
        # Parse missing_documents inside this topic
        topic_missing: list[MissingDocument] = []
        for m in t.get("missing_documents", []):
            side = str(m.get("side", "")).strip()
            items = [str(i).strip() for i in m.get("items", []) if str(i).strip()]
            if side and items:
                topic_missing.append(MissingDocument(side=side, items=items))
        if title and sides:
            topics.append(Topic(
                title=title,
                sides=sides,
                category=category,  # type: ignore[arg-type]
                relevant_law=relevant_law,
                missing_documents=topic_missing,
            ))

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

    # Build RAG context — retrieve relevant law chunks based on combined content
    rag_context = ""
    try:
        from backend.services.rag import retrieve
        rag_query = f"{side_a_name} {side_b_name} {content_a[:500]} {content_b[:500]}"
        chunks = retrieve(rag_query, top_k=6)
        if chunks:
            rag_context = "\n\n".join(chunks)
    except Exception:
        pass  # RAG is optional — proceed without it

    messages = [
        {"role": "system", "content": _overview_system_prompt(side_a_name, side_b_name, rag_context)},
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
