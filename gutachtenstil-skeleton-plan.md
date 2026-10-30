# Plan: Gutachtenstil-Structured Skeleton per Leaf Node

## Top-Level Overview

The current Formalia skeleton produces two flat string fields per leaf node
(`aus_dem_schriftsatz`, `beweise_begruendungen`). This will be replaced with a
proper **Gutachtenstil** structure:

For every leaf node in `2. Materiell-rechtlich`, the output walks through each
**Tatbestandsmerkmal** (element of the norm) in order. The Tatbestandsmerkmale
and their Definitionen are **hardcoded in the backend per norm** — they never
change. The LLM only fills in the **Subsumtion** and **Zwischenergebnis** for
each Tatbestandsmerkmal, and it does so **separately for each side** (side A
and side B).

No Obersatz. No final Ergebnis per leaf node. Just:

```
Leaf node: Wirksamer Mietvertrag, § 535 BGB
│
├── Tatbestandsmerkmal 1: Einigung über essentialia negotii
│   ├── Definition: "Ein Mietvertrag kommt zustande durch Einigung über..."
│   ├── Seite A:
│   │   ├── Subsumtion: "Der Kläger trägt vor, dass..."
│   │   └── Zwischenergebnis: "erfüllt / streitig / nicht behandelt"
│   └── Seite B:
│       ├── Subsumtion: "Der Beklagte bestreitet, dass..."
│       └── Zwischenergebnis: "streitig / nicht erfüllt"
│
└── Tatbestandsmerkmal 2: ...
```

---

## Scope

- **Backend:** `backend/services/summarizer.py` — new data structures, new
  hardcoded Tatbestandsmerkmale table, new LLM prompt, new parser, updated
  renderer.
- **Backend:** `backend/services/renderer.py` — updated HTML rendering for the
  dashboard skeleton section.
- **Frontend:** `frontend/index.html` — no changes needed (skeleton is
  backend-rendered only).
- **Formalia.md:** No structural changes needed.

---

## Sub-Tasks

---

### Sub-Task 1: Define hardcoded Tatbestandsmerkmale per leaf node

**Intent**
Create a new data structure in `summarizer.py` that defines, for each of the
16 leaf nodes, the fixed list of Tatbestandsmerkmale together with their
Definitionen. This replaces the need for the LLM to invent or discover the
elements of each norm — they are authoritative and immutable.

**Expected Outcomes**
- A new Python constant (e.g. `LEAF_NODE_MERKMALE`) maps each `node_id` to an
  ordered list of `(merkmal_label, definition_text)` tuples.
- Every one of the 16 leaf nodes has at least 2–4 Tatbestandsmerkmale with
  concise German definitions grounded in the relevant BGB paragraph.

**Todo List**
- [ ] For each leaf node in `FORMALIA_LEAF_NODES`, research and write the
  Tatbestandsmerkmale and their Definitionen (German, concise, legally correct).
  Nodes to cover:
  - `wirksamer_mietvertrag` — § 535 BGB
  - `mietmangel` — § 536 BGB (not 534 — confirm correct paragraph)
  - `massgeblicher_zeitpunkt` — § 536 Abs. 1 BGB
  - `kein_ausschluss_vertraglich` — § 536b BGB
  - `kenntnis` — § 536b BGB
  - `unterlassene_maenzelanzeige` — § 536c BGB
  - `herabsetzung` — Minderungsquote (case law + Mietminderungstabellen)
  - `rueckerstattung` — § 812 BGB
  - `vermieter_ordentlich` — § 542 Abs. 1 BGB, §§ 573, 573a BGB
  - `vermieter_fristlos_543` — §§ 543 Abs. 1, 2 Nr. 2 und 3 BGB
  - `vermieter_fristlos_569` — § 569 Abs. 2 BGB
  - `vermieter_befristet` — § 580 BGB
  - `mieter_ordentlich` — § 542 Abs. 1 BGB
  - `mieter_fristlos_543` — §§ 543 Abs. 1, 2 Nr. 2 BGB
  - `mieter_fristlos_569` — §§ 569 Abs. 1, 2 BGB
  - `mieter_befristet` — § 580 BGB
- [ ] Add the constant `LEAF_NODE_MERKMALE: dict[str, list[tuple[str, str]]]`
  to `backend/services/summarizer.py` directly below `FORMALIA_LEAF_NODES`.

**Relevant Context**
- [`backend/services/summarizer.py`](backend/services/summarizer.py:48) —
  `FORMALIA_LEAF_NODES` list starts at line 48.
- Definitionen should be short (1–2 sentences), suitable as a reference for
  the LLM during subsumtion.

**Status**: `[x] done`

---

### Sub-Task 2: Replace Pydantic models for the new per-Merkmal structure

**Intent**
Replace the two flat fields in `LeafNodeReview` with a list of
`TatbestandsmerkmalReview` objects — one per Tatbestandsmerkmal — each
containing a Subsumtion and Zwischenergebnis per side.

**Expected Outcomes**
- New model `SeitenReview` holds `subsumtion` and `zwischenergebnis` for one
  side.
- New model `TatbestandsmerkmalReview` holds `label`, `definition`, and a
  two-element `sides` list (`[SeitenReview, SeitenReview]`).
- Updated `LeafNodeReview` replaces `aus_dem_schriftsatz` and
  `beweise_begruendungen` with `merkmale: list[TatbestandsmerkmalReview]`.
- `FormaliaSkeleton` is unchanged (still `nodes: list[LeafNodeReview]`).

**Todo List**
- [ ] Add `SeitenReview(BaseModel)` with fields:
  - `side: str` — name of the party (derived from filename)
  - `subsumtion: str` — LLM-filled subsumtion text or "nicht behandelt"
  - `zwischenergebnis: str` — LLM-filled result or "offen"
- [ ] Add `TatbestandsmerkmalReview(BaseModel)` with fields:
  - `label: str` — hardcoded merkmal label
  - `definition: str` — hardcoded definition text
  - `sides: list[SeitenReview]` — always 2 entries: [side_a, side_b]
- [ ] Update `LeafNodeReview` — remove `aus_dem_schriftsatz` and
  `beweise_begruendungen`, add `merkmale: list[TatbestandsmerkmalReview]`.
- [ ] Keep `node_id`, `label`, and `path` fields unchanged.

**Relevant Context**
- [`backend/services/summarizer.py`](backend/services/summarizer.py:100) —
  current `LeafNodeReview` model at line 100.
- `FormaliaSkeleton` is at line 109 — no change needed there.

**Status**: `[x] done`

---

### Sub-Task 3: Rewrite the LLM prompt and parser for the new structure

**Intent**
Update `_skeleton_system_prompt()` to instruct the LLM to fill in only
Subsumtion and Zwischenergebnis per Tatbestandsmerkmal per side. Update
`_parse_skeleton_response()` to reconstruct the new model from the LLM's JSON.
Update `_call_skeleton()` to pass `side_a_name` and `side_b_name` through.

**Expected Outcomes**
- The LLM is given the hardcoded Tatbestandsmerkmale and Definitionen per node
  in the prompt — it does NOT invent them.
- The LLM produces a JSON with exactly the Subsumtion + Zwischenergebnis fields
  per side per Merkmal.
- The parser constructs the full `LeafNodeReview` with `TatbestandsmerkmalReview`
  objects, injecting the hardcoded `label` and `definition` from
  `LEAF_NODE_MERKMALE`.
- Falls back gracefully (empty/missing LLM fields → "nicht behandelt" /
  "offen").

**New LLM JSON shape (per node):**
```json
{
  "wirksamer_mietvertrag": {
    "merkmale": [
      {
        "merkmal": "Einigung über essentialia negotii",
        "seite_a": {
          "subsumtion": "...",
          "zwischenergebnis": "erfüllt"
        },
        "seite_b": {
          "subsumtion": "...",
          "zwischenergebnis": "streitig"
        }
      }
    ]
  }
}
```

**Todo List**
- [ ] Update `_skeleton_system_prompt(side_a, side_b, rag_context)` to accept
  `side_a` and `side_b` name parameters (previously not needed).
- [ ] In the prompt, list each node's Tatbestandsmerkmale with their
  Definitionen, and instruct the LLM to fill Subsumtion + Zwischenergebnis per
  side per Merkmal.
- [ ] Update `_call_skeleton(files, rag_context, side_a, side_b)` signature and
  pass `side_a_name` / `side_b_name` from `summarize_all_md()`.
- [ ] Rewrite `_parse_skeleton_response(raw, side_a, side_b)` to:
  - Decode the new JSON shape
  - For each node, iterate `LEAF_NODE_MERKMALE[node_id]` (hardcoded order)
  - Match LLM output by `merkmal` label; fall back on index if label mismatches
  - Build `TatbestandsmerkmalReview` objects with hardcoded `label`/`definition`
    and LLM-filled `sides`
- [ ] Update `render_formalia_skeleton()` (text renderer) to walk the new
  `merkmale` list instead of the two flat fields.

**Relevant Context**
- [`backend/services/summarizer.py`](backend/services/summarizer.py:378) —
  `_skeleton_system_prompt` at line 378.
- [`backend/services/summarizer.py`](backend/services/summarizer.py:426) —
  `_parse_skeleton_response` at line 426.
- [`backend/services/summarizer.py`](backend/services/summarizer.py:452) —
  `_call_skeleton` at line 452.
- [`backend/services/summarizer.py`](backend/services/summarizer.py:483) —
  `summarize_all_md` passes `side_a_name`/`side_b_name` at line 503.

**Status**: `[x] done`

---

### Sub-Task 4: Update the HTML dashboard renderer

**Intent**
Rewrite `_render_formalia_skeleton_section()` in `renderer.py` to render the
new per-Merkmal, per-side structure as an HTML table or card layout.

**Expected Outcomes**
- For each leaf node, the HTML shows the node label and path header.
- Under each leaf node, each Tatbestandsmerkmal is shown with:
  - The Definition (in a subdued colour, as a fixed reference)
  - A two-column layout: Seite A | Seite B
  - Each side shows Subsumtion text + a colour-coded Zwischenergebnis badge
    (green = erfüllt, yellow = streitig, red = nicht erfüllt / nicht behandelt)
- The overall table/card structure is consistent with the existing dashboard
  visual style (same fonts, colours, border radii).

**Todo List**
- [ ] Update `_render_formalia_skeleton_section()` to iterate
  `node.merkmale` instead of reading `aus_dem_schriftsatz` /
  `beweise_begruendungen`.
- [ ] Add a `_zwischenergebnis_badge(text)` helper that colour-codes the
  Zwischenergebnis string.
- [ ] Render each Tatbestandsmerkmal as a sub-row group:
  - Definition row (full-width, subdued)
  - Two-column row: Seite A subsumtion + badge | Seite B subsumtion + badge
- [ ] Keep the existing path-grouping header rows unchanged.

**Relevant Context**
- [`backend/services/renderer.py`](backend/services/renderer.py:89) —
  `_render_formalia_skeleton_section` at line 89.
- The `_status_badge()` helper at line 78 can be replaced or extended with the
  new `_zwischenergebnis_badge()`.

**Status**: `[x] done`

---

## Open Decisions Already Confirmed

| Question | Answer |
|---|---|
| Obersatz per leaf node? | **No** |
| Final Ergebnis per leaf node? | **No** |
| Tatbestandsmerkmale + Definitionen hardcoded or LLM-generated? | **Hardcoded in backend** |
| Subsumtion and Zwischenergebnis per side? | **Yes — one per side per Merkmal** |
| Frontend changes needed? | **No — skeleton is backend/dashboard-only** |
| Language? | **German throughout** |
