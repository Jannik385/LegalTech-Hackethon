# Dashboard: .md Links & Law Badge Tooltips Plan

## Overview

The dashboard (rendered by `backend/services/renderer.py`) is missing two narrow features that
already work in the first view (`frontend/index.html`):

1. **Citation links in key facts** — `(M09)` / `(M09.md)` inline refs inside key-fact bullet
   text appear as plain escaped text. They must become clickable `openFileModal()` buttons,
   exactly as in the first view.

2. **Law badge chips with hover tooltips** — paragraph badges (e.g. "§ 535 BGB") with
   definition pop-ups on hover are never rendered in the dashboard. The CSS rules for
   `.law-badge` and `data-tooltip` are absent and no badge spans are emitted.

The `openFileModal()` JS function and the file-modal overlay **already exist** in the dashboard
(renderer.py lines 458–495). The filename link in the card header (line 250) already works.

**Scope:** All changes are confined to `backend/services/renderer.py`. No other files change.

**Not in scope:** The visual structure of the dashboard does not change — no new sections,
no new layout, no topic-block redesign. The badge chips appear in a thin row just below the
"Key Facts" heading inside the existing summary card.

---

## Data available

Each `LinkedSummary` (entry) carries:
- `entry.key_facts` — `list[str]`, the bullet texts (may contain `(M09)` refs)
- `entry.topics` — `list[Topic]`, each topic has:
  - `relevant_law: list[str]` — paragraph labels like "§ 535 BGB"
  - `law_definitions: dict[str, list[list[str]]]` — keyed by paragraph label; value is a list
    of `[term_label, definition_text]` pairs

---

## Sub-Task 1 — Add law-badge tooltip CSS to the dashboard `<style>` block

**Intent**
The dashboard is a self-contained HTML page. The `.law-badge` and `data-tooltip` CSS rules
must be inlined so badge spans render correctly without any external stylesheet.

**Expected Outcomes**
- The dashboard `<style>` block contains `.law-badge`, `.law-badge[data-tooltip]`,
  `.law-badge[data-tooltip]::after`, and `.law-badge[data-tooltip]:hover::after` rules
  identical to those in `frontend/index.html` (lines 323–366).
- No other styling in the dashboard changes.

**Todo List**
- [ ] Locate the closing `</style>` tag in the `render_dashboard()` f-string in
      `renderer.py` (currently around line 418).
- [ ] Append the four `.law-badge` CSS rule blocks immediately before `</style>`.
      Note: the template uses `{{ }}` for literal CSS braces.

**Relevant Context**
- Source CSS: `frontend/index.html` lines 323–366.
- Target: `backend/services/renderer.py`, `<style>` block inside `render_dashboard()`.

**Status** `[ ] pending`

---

## Sub-Task 2 — Add a `_law_badges_html()` helper and render chips in summary cards

**Intent**
Collect all unique paragraph refs and their definitions across all topics of an entry and
render a row of `.law-badge` chips just below the "Key Facts" heading. Badges that have
definitions get a `data-tooltip` attribute so the CSS from Sub-Task 1 activates the hover popup.

**Expected Outcomes**
- A new private function `_law_badges_html(topics: list) -> str` exists in `renderer.py`.
- It iterates `topics`, deduplicates `relevant_law` labels (preserving first-seen order),
  looks up `law_definitions` for each label, and returns a `<div>` containing one `.law-badge`
  span per label.
- Badges with at least one definition entry get `data-tooltip="..."` (same format as the first
  view: each entry is `label:\ndefinition`, joined by `\n\n` for multiple).
- Badges with no definitions get no `data-tooltip` attribute.
- `_render_summary_section()` calls `_law_badges_html(entry.topics)` and inserts the returned
  HTML immediately after the `<strong>Key Facts</strong>` line, before the `<ul>` of bullets.
- If `entry.topics` is empty or none of them have `relevant_law`, nothing is rendered (no
  empty `<div>`).

**Todo List**
- [ ] Write `_law_badges_html(topics)`.
- [ ] Insert its output into the summary card in `_render_summary_section()`, between the
      `<strong>Key Facts</strong>` label and `facts_html`.

**Relevant Context**
- `renderTopicBlock` in `frontend/index.html` lines 865–872 shows the exact tooltip format.
- `law_definitions` type: `dict[str, list[list[str]]]` — each value is a list of
  `[label, definition]` pairs.
- `_render_summary_section` is at `renderer.py` lines 205–260.

**Status** `[ ] pending`

---

## Sub-Task 3 — Add a `_link_citations()` helper and apply it to key-fact bullets

**Intent**
Each key-fact string may contain `(M09)` or `(M09.md)` inline refs. These must become
`<button onclick="openFileModal(...)">` elements, matching the first view's `linkCitations()`.

**Expected Outcomes**
- A new private function `_link_citations(text: str, md_filenames: set[str]) -> str` exists in
  `renderer.py`.
- It HTML-escapes the full text, then replaces `(REF)` / `(REF.md)` patterns (case-insensitive)
  with an `openFileModal()` button when the ref resolves to a known `.md` filename, or leaves
  the match as plain escaped text when no match is found.
- `_render_summary_section()` receives a `md_filenames: set[str]` argument and uses
  `_link_citations()` instead of bare `escape()` for each key-fact `<li>`.
- `render_dashboard()` builds `md_filenames` from `linked_report.entries` and passes it to
  each `_render_summary_section()` call.
- No change to the visual layout or any other part of the card.

**Todo List**
- [ ] Check if `import re` is already present in `renderer.py`; add it if not.
- [ ] Write `_link_citations(text, md_filenames)`:
  - Escape the full text with `escape()`.
  - Use `re.sub` with pattern `r'\(([A-Za-z]\d+(?:\.md)?)\)'` (case-insensitive) and a match
    callback.
  - Callback: strip `.md` suffix and uppercase the ref, find a match in `md_filenames`
    (case-insensitive), return a `<button>` on match or the original escaped token otherwise.
  - Button inline style matches `.citation-link` from `index.html` lines 569–581:
    `color:#7c5cd8`, `border-bottom:1px dotted`, no background, no border frame.
- [ ] Update `_render_summary_section(entry, md_filenames)` signature.
- [ ] Replace `escape(f)` in the key-facts `<li>` loop with `_link_citations(f, md_filenames)`.
- [ ] In `render_dashboard()`, derive `md_filenames` as a set of all `.filename` values from
      `linked_report.entries`, then pass it to each `_render_summary_section()` call.

**Relevant Context**
- Reference JS: `frontend/index.html` lines 914–925 (`linkCitations`).
- Citation-link style: `frontend/index.html` lines 569–581 (`.citation-link` CSS).
- Call-site: `renderer.py` lines 300–301.
- `escape` already imported in `renderer.py` (`from html import escape`).

**Status** `[ ] pending`
