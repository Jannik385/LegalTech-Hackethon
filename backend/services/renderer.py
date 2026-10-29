"""Dashboard renderer — Sub-Task 6.

Converts a LinkedReport into a self-contained, single-file HTML dashboard.
No external CSS or JS is referenced; everything is inlined so the file can be
saved and opened offline.

The HTML structure:
  - Header with title and ISO-8601 creation timestamp
  - Summary sections (one per .md file) with key facts and anchor links to
    their referenced evidence items
  - Evidence gallery at the bottom where each item carries an id attribute
    matching the anchor used in the summary sections
  - "Download als HTML" link that is injected by the frontend (or can be
    triggered directly from the page via a small inline script)

Usage::

    from backend.services.renderer import render_dashboard
    html: str = render_dashboard(linked_report)
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from backend.services.linker import LinkedReport, LinkedSummary
from backend.services.classifier import ClassificationResult


# ---------------------------------------------------------------------------
# Anchor helpers
# ---------------------------------------------------------------------------


def _anchor_id(filename: str) -> str:
    """Return a CSS-safe anchor id for an evidence filename."""
    safe = filename.replace(" ", "-").replace("/", "-").replace("\\", "-")
    return f"beweis-{safe}"


# ---------------------------------------------------------------------------
# Category badge colours (inline style — no external CSS)
# ---------------------------------------------------------------------------

_BADGE_STYLES: dict[str, str] = {
    "Foto":         "background:#fef9c3;color:#92400e",
    "Vertrag":      "background:#d1fae5;color:#065f46",
    "Rechnung":     "background:#fee2e2;color:#991b1b",
    "Unterschrift": "background:#ede9fe;color:#4c1d95",
    "Sonstiges":    "background:#f3f4f6;color:#374151",
}

_DEFAULT_BADGE = "background:#f3f4f6;color:#374151"


def _badge(category: str) -> str:
    style = _BADGE_STYLES.get(category, _DEFAULT_BADGE)
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;'
        f'font-size:0.78rem;font-weight:600;{style}">{escape(category)}</span>'
    )


# ---------------------------------------------------------------------------
# HTML fragment builders
# ---------------------------------------------------------------------------


def _render_summary_section(entry: LinkedSummary) -> str:
    """Render one summary card with its evidence anchor links."""
    facts_html = ""
    if entry.key_facts:
        items = "".join(f"<li>{escape(f)}</li>" for f in entry.key_facts)
        facts_html = f'<ul style="margin:8px 0 0 0;padding-left:20px">{items}</ul>'
    else:
        facts_html = '<p style="color:#57606a;font-size:0.875rem;font-style:italic">Keine Key Facts extrahiert.</p>'

    if entry.evidence_links:
        link_items = []
        for ev in entry.evidence_links:
            anchor = _anchor_id(ev.filename)
            link_items.append(
                f'<li><a href="#{anchor}" style="color:#3b82d4;text-decoration:none;font-weight:500">'
                f'{escape(ev.filename)}</a> {_badge(ev.category)}</li>'
            )
        evidence_html = (
            '<div style="margin-top:14px">'
            '<strong style="font-size:0.85rem;text-transform:uppercase;letter-spacing:0.04em;color:#57606a">Verlinkte Nachweise</strong>'
            f'<ul style="margin:6px 0 0 0;padding-left:20px;list-style:disc">{"".join(link_items)}</ul>'
            "</div>"
        )
    else:
        evidence_html = (
            '<p style="margin-top:12px;color:#57606a;font-size:0.875rem;font-style:italic">'
            "Keine Nachweise im Text referenziert.</p>"
        )

    template_block = ""
    if entry.template_output:
        template_block = (
            '<details style="margin-top:14px">'
            '<summary style="cursor:pointer;font-size:0.85rem;color:#57606a;user-select:none">'
            "Template-Ausgabe anzeigen</summary>"
            f'<pre style="margin:8px 0 0 0;padding:12px;background:#f7f8fa;border:1px solid #e5e7eb;'
            f'border-radius:6px;white-space:pre-wrap;word-break:break-word;font-size:0.8rem;'
            f'color:#374151">{escape(entry.template_output)}</pre>'
            "</details>"
        )

    return (
        '<section style="margin-bottom:28px;padding:20px 24px;background:#fff;border:1px solid #e5e7eb;'
        'border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.04)">'
        f'<h2 style="margin:0 0 10px;font-size:1rem;font-weight:700;color:#1f2328">{escape(entry.filename)}</h2>'
        f'<p style="margin:0 0 8px;color:#374151;line-height:1.6">{escape(entry.summary)}</p>'
        f'<strong style="font-size:0.85rem;text-transform:uppercase;letter-spacing:0.04em;color:#57606a">Key Facts</strong>'
        f"{facts_html}"
        f"{evidence_html}"
        f"{template_block}"
        "</section>"
    )


def _render_evidence_item(ev: ClassificationResult) -> str:
    """Render one anchored evidence card in the gallery section."""
    anchor = _anchor_id(ev.filename)
    return (
        f'<div id="{anchor}" style="display:flex;align-items:flex-start;gap:12px;'
        f'padding:14px 16px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;'
        f'margin-bottom:12px;scroll-margin-top:80px">'
        f'<div style="flex:1;min-width:0">'
        f'<span style="font-weight:600;color:#1f2328;word-break:break-all">{escape(ev.filename)}</span>'
        f'<p style="margin:4px 0 0;font-size:0.8rem;color:#57606a;line-height:1.5">{escape(ev.confidence_note)}</p>'
        f"</div>"
        f'<div style="flex-shrink:0;padding-top:2px">{_badge(ev.category)}</div>'
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_dashboard(linked_report: LinkedReport) -> str:
    """Render a LinkedReport as a self-contained HTML string.

    The returned HTML is a complete document that can be served directly as
    an HTTPResponse or saved as a .html file.
    """
    timestamp = datetime.now(tz=timezone.utc).strftime("%d.%m.%Y %H:%M UTC")

    # ── Summary sections ──────────────────────────────────────────────────
    summary_sections = "".join(
        _render_summary_section(entry) for entry in linked_report.entries
    )
    if not summary_sections:
        summary_sections = (
            '<p style="color:#57606a;font-style:italic">Keine Zusammenfassungen vorhanden.</p>'
        )

    # ── Collect all unique evidence items across entries ──────────────────
    seen: set[str] = set()
    all_evidence: list[ClassificationResult] = []
    for entry in linked_report.entries:
        for ev in entry.evidence_links:
            if ev.filename not in seen:
                seen.add(ev.filename)
                all_evidence.append(ev)

    if all_evidence:
        gallery_items = "".join(_render_evidence_item(ev) for ev in all_evidence)
        gallery_section = (
            f'<section style="margin-top:40px">'
            f'<h2 style="font-size:1.05rem;font-weight:700;margin:0 0 16px;color:#1f2328;'
            f'padding-bottom:8px;border-bottom:2px solid #e5e7eb">Beweis-Galerie</h2>'
            f"{gallery_items}"
            f"</section>"
        )
    else:
        gallery_section = (
            '<section style="margin-top:40px">'
            '<h2 style="font-size:1.05rem;font-weight:700;margin:0 0 16px;color:#1f2328;'
            'padding-bottom:8px;border-bottom:2px solid #e5e7eb">Beweis-Galerie</h2>'
            '<p style="color:#57606a;font-style:italic">Keine klassifizierten Beweise vorhanden.</p>'
            "</section>"
        )

    # ── Full HTML document ────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>LegalTech Dashboard</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
      font-size: 15px;
      line-height: 1.6;
      color: #1f2328;
      background: #f7f8fa;
      margin: 0;
      padding: 0;
    }}
    a {{ color: #3b82d4; }}
    a:hover {{ text-decoration: underline; }}
    details > summary {{ list-style: none; }}
    details > summary::-webkit-details-marker {{ display: none; }}
  </style>
</head>
<body>
  <header style="background:#1f2328;color:#fff;padding:20px 0;margin-bottom:32px">
    <div style="max-width:820px;margin:0 auto;padding:0 24px;display:flex;align-items:center;justify-content:space-between;gap:16px">
      <div>
        <h1 style="margin:0;font-size:1.35rem;font-weight:700">LegalTech Document Analyzer</h1>
        <p style="margin:4px 0 0;font-size:0.85rem;color:#9ca3af">Dashboard &mdash; erstellt am {timestamp}</p>
      </div>
      <button
        id="download-btn"
        onclick="(function(){{
          var blob = new Blob([document.documentElement.outerHTML], {{type:'text/html'}});
          var a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = 'legaltech-dashboard.html';
          a.click();
          URL.revokeObjectURL(a.href);
        }})()"
        style="flex-shrink:0;padding:8px 18px;background:#3b82d4;color:#fff;border:none;
               border-radius:6px;font-size:0.875rem;font-weight:600;cursor:pointer;white-space:nowrap">
        ⬇ Download als HTML
      </button>
    </div>
  </header>

  <main style="max-width:820px;margin:0 auto;padding:0 24px 48px">

    <section style="margin-bottom:36px">
      <h2 style="font-size:1.05rem;font-weight:700;margin:0 0 16px;color:#1f2328;
                 padding-bottom:8px;border-bottom:2px solid #e5e7eb">Zusammenfassungen</h2>
      {summary_sections}
    </section>

    {gallery_section}

  </main>

</body>
</html>"""
