# Plan: Paragraph Hover Tooltip Feature

## Overview

When a user hovers over a `.law-badge` span (e.g. `§ 536 BGB`) in the topic cards of the
frontend, a tooltip appears showing the full Tatbestandsmerkmal definitions for that paragraph.

The definitions already exist in the backend as the hardcoded `LEAF_NODE_MERKMALE` dictionary.
The approach is:
1. Build a backend lookup table mapping paragraph strings (e.g. `"§ 536 BGB"`) to their
   definitions, derived from existing data.
2. Extend the `Topic` Pydantic model with a new optional field `law_definitions` that carries
   definitions for each relevant_law entry when available.
3. Populate `law_definitions` during topic construction in `summarizer.py`.
4. In `frontend/index.html`, render the badge with a CSS tooltip using the embedded definition
   text — no JS library required, pure CSS `title`-style or a lightweight CSS tooltip.

---

## Sub-Tasks

---

### Sub-Task 1 — Build a paragraph-to-definitions lookup table in `summarizer.py`

**Intent**
Create a static `PARAGRAPH_DEFINITIONS: dict[str, list[tuple[str, str]]]` mapping common
paragraph citation strings to their Tatbestandsmerkmal tuples. Derived from the existing
`LEAF_NODE_MERKMALE` + `FORMALIA_LEAF_NODES` data — no new data required.

The mapping is done by extracting the primary paragraph reference from each leaf-node label
in `FORMALIA_LEAF_NODES` (e.g. `"Mietmangel, § 536 BGB"` → `"§ 536 BGB"`) and pointing it
to the corresponding `LEAF_NODE_MERKMALE[node_id]` list. Some nodes have multiple paragraphs
in their label; the plan is to register one or more key strings per node where needed.

**Expected Outcomes**
- A new constant `PARAGRAPH_DEFINITIONS` in `summarizer.py` below `LEAF_NODE_MERKMALE`.
- It maps strings like `"§ 535 BGB"`, `"§ 536 BGB"`, `"§ 536b BGB"`, `"§ 812 BGB"` etc. to
  their definition tuples list.
- The mapping is hand-authored (not computed at runtime) for clarity and correctness.

**Todo List**
- [ ] After `LEAF_NODE_MERKMALE` in `summarizer.py`, add a new dict constant
      `PARAGRAPH_DEFINITIONS: dict[str, list[tuple[str, str]]]`.
- [ ] For each node that has a clear single paragraph in its label, add one entry mapping
      that paragraph string to `LEAF_NODE_MERKMALE[node_id]`.
- [ ] For multi-paragraph nodes or "Beachte:" references, add entries for the most prominent
      paragraph only (the one the LLM is most likely to emit).

**Relevant Context**
- `backend/services/summarizer.py` lines 48-389: `FORMALIA_LEAF_NODES` + `LEAF_NODE_MERKMALE`
- Node labels with clear single §: `wirksamer_mietvertrag` → `§ 535 BGB`,
  `mietmangel` → `§ 536 BGB`, `massgeblicher_zeitpunkt` → `§ 536 Abs. 1 BGB`,
  `kenntnis` → `§ 536b BGB`, `unterlassene_maenzelanzeige` → `§ 536c BGB`,
  `rueckerstattung` → `§ 812 BGB`

**Status** `[ ] pending`

---

### Sub-Task 2 — Extend `Topic` model and populate `law_definitions` in summarizer

**Intent**
Add a `law_definitions: dict[str, list[tuple[str, str]]] = {}` field to the `Topic` Pydantic
model. When a topic is built (in `_parse_overview_response`), look up each `relevant_law`
entry in `PARAGRAPH_DEFINITIONS` and populate the field.

**Expected Outcomes**
- `Topic.law_definitions` is a dict where keys are paragraph strings and values are lists of
  `[label, definition]` pairs.
- The `/summarize` API response (`result.model_dump()`) now includes `law_definitions` on each
  topic object.
- Paragraphs not found in the lookup simply have no entry (graceful fallback).

**Todo List**
- [ ] Add `law_definitions: dict[str, list[tuple[str, str]]] = {}` to the `Topic` class in
      `summarizer.py`.
- [ ] In `_parse_overview_response`, after building `relevant_law`, populate `law_definitions`
      by iterating over `relevant_law` and checking `PARAGRAPH_DEFINITIONS`.
- [ ] Pass `law_definitions` when constructing the `Topic(...)` instance.

**Relevant Context**
- `backend/services/summarizer.py` lines 451-460: `Topic` model
- `backend/services/summarizer.py` lines 650-675: `_parse_overview_response` topic loop
- Result is serialized via `result.model_dump()` at `backend/main.py` line 96

**Status** `[ ] pending`

---

### Sub-Task 3 — Render tooltip on `.law-badge` in `frontend/index.html`

**Intent**
Update `renderTopicBlock` in `frontend/index.html` to read `t.law_definitions` and attach
a CSS tooltip to each `.law-badge` span that has a matching definition. The tooltip renders
the definition labels and text on hover — no external library, pure CSS using a
`data-tooltip` attribute + `.law-badge[data-tooltip]:hover::after` rule.

**Expected Outcomes**
- Hovering over a badge like `§ 536 BGB` displays a small styled tooltip box with the
  Tatbestandsmerkmal labels and definitions.
- Badges with no definition (LLM-invented paragraphs not in the lookup) render as before
  with no tooltip effect.
- Tooltip is visually distinct: fixed max-width, scrollable if long, positioned above or
  below the badge, no layout shift.

**Todo List**
- [ ] Add CSS for `.law-badge[data-tooltip]` tooltip in the `<style>` block of `index.html`:
      position relative, `::after` pseudo-element with `content: attr(data-tooltip)`,
      absolute positioning, styled box, hidden by default, visible on hover.
- [ ] In `renderTopicBlock`, when building `lawBadges`, check `t.law_definitions[l]` and if
      present, format the definitions as a plain text string and set it as `data-tooltip`.
- [ ] Ensure `escHtml` is applied to the tooltip content to prevent XSS.

**Relevant Context**
- `frontend/index.html` lines 727-730: `renderTopicBlock` and `.law-badge` rendering
- `frontend/index.html` CSS `<style>` block (top of file): where tooltip CSS should be added
- Existing hover pattern at lines 737, 809, 832 uses native `title` attribute — the new
  tooltip replaces/supplements this with a styled version.

**Status** `[ ] pending`

---

## Notes

- `tuple[str, str]` is not directly JSON-serializable as a named dict. When serialized via
  `model_dump()`, Pydantic will output lists of 2-element arrays. The frontend should treat
  each entry as `[label, definition]`.
- The `law_definitions` field type in the Pydantic model should use `list[list[str]]` per
  paragraph key (not `tuple`) for clean JSON serialization: 
  `law_definitions: dict[str, list[list[str]]] = {}`.
- The lookup in Sub-Task 1 should convert tuples to lists of lists for consistency.
