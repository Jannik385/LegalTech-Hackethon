"""Evidence classification service.

Classifies non-Markdown files into legal-evidence categories by calling the
OpenRouter API.  For image files a Base64-encoded vision prompt is tried first;
if the model rejects the image input the function falls back to a metadata-only
text prompt.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import re

from pydantic import BaseModel
from openrouter import OpenRouter

from backend.config import MODEL, OPENROUTER_API_KEY

# ---------------------------------------------------------------------------
# Supported categories
# ---------------------------------------------------------------------------

CATEGORIES = ["Foto", "Vertrag", "Rechnung", "Unterschrift", "Sonstiges"]
CATEGORIES_STR = ", ".join(CATEGORIES)

# MIME-type prefixes that indicate an image file
_IMAGE_MIMES = ("image/",)


def _is_image(mime_type: str) -> bool:
    return any(mime_type.startswith(prefix) for prefix in _IMAGE_MIMES)


# ---------------------------------------------------------------------------
# Pydantic result model
# ---------------------------------------------------------------------------


class ClassificationResult(BaseModel):
    filename: str
    category: str
    confidence_note: str


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "Du bist ein juristischer Dokumentenanalyst. "
    "Klassifiziere das übergebene Dokument/Bild in genau eine der folgenden Kategorien: "
    f"{CATEGORIES_STR}. "
    "Antworte ausschließlich mit einem JSON-Objekt mit den Feldern "
    '"category" (einer der obigen Werte) und "confidence_note" (ein kurzer Satz, '
    "der deine Einschätzung begründet). Kein weiterer Text."
)


def _text_prompt(filename: str, mime_type: str) -> str:
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "unbekannt"
    return (
        f'Dateiname: "{filename}"\n'
        f"Dateiendung: .{ext}\n"
        f"MIME-Typ: {mime_type}\n\n"
        "Klassifiziere diese Datei anhand der Metadaten."
    )


def _vision_messages(filename: str, file_bytes: bytes, mime_type: str) -> list[dict]:
    b64 = base64.b64encode(file_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{b64}"
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": data_url},
                },
                {
                    "type": "text",
                    "text": (
                        f'Klassifiziere dieses Bild ("{filename}") als juristische Beweisurkunde.'
                    ),
                },
            ],
        },
    ]


def _text_messages(filename: str, mime_type: str) -> list[dict]:
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _text_prompt(filename, mime_type)},
    ]


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------


def _parse_response(raw: str) -> tuple[str, str]:
    """Extract category and confidence_note from model output.

    The model should return clean JSON, but might wrap it in a fenced block.
    Falls back to 'Sonstiges' if parsing fails.
    """
    # Strip optional ```json ... ``` fences
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    try:
        data = json.loads(cleaned)
        category = data.get("category", "Sonstiges")
        if category not in CATEGORIES:
            category = "Sonstiges"
        note = data.get("confidence_note", "")
        return category, note
    except (json.JSONDecodeError, AttributeError):
        return "Sonstiges", f"Konnte Antwort nicht parsen: {raw[:120]}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_file(filename: str, file_bytes: bytes, mime_type: str) -> ClassificationResult:
    """Classify a single non-Markdown file and return a ClassificationResult.

    For image files the vision path (Base64 inline) is tried first.  If the
    model returns an error or the call raises an exception the function falls
    back to a metadata-only text prompt.
    """
    if not mime_type:
        guessed, _ = mimetypes.guess_type(filename)
        mime_type = guessed or "application/octet-stream"

    with OpenRouter(api_key=OPENROUTER_API_KEY) as client:
        # ── Vision path (images only) ───────────────────────────────────────
        if _is_image(mime_type):
            try:
                res = client.chat.send(
                    model=MODEL,
                    messages=_vision_messages(filename, file_bytes, mime_type),
                    stream=False,
                )
                raw = res.choices[0].message.content or ""
                category, note = _parse_response(raw)
                return ClassificationResult(
                    filename=filename,
                    category=category,
                    confidence_note=note,
                )
            except Exception:
                # Vision not supported by this model — fall through to text prompt
                pass

        # ── Text / metadata path ────────────────────────────────────────────
        res = client.chat.send(
            model=MODEL,
            messages=_text_messages(filename, mime_type),
            stream=False,
        )
        raw = res.choices[0].message.content or ""
        category, note = _parse_response(raw)
        return ClassificationResult(
            filename=filename,
            category=category,
            confidence_note=note,
        )
