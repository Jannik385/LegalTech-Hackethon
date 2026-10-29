# Plan: Mietrecht RAG + Structured Legal Output

## Top-Level Overview

Extend the LegalTech backend to:

1. **Restructure the LLM output** by the legal taxonomy defined in `Formalia.md`:
   - **Formell-rechtlich** — procedural rules (ZPO, Ladung, Zustellung, Fristen, Verjährung)
   - **Materiell-rechtlich** — substantive law (Minderung, Rücktritt per BGB)
   - **Hauptverhandlung** — trial proceedings (Mündliche Verhandlung, Beweisführung, Zeugenaussagen, Sachverständigengutachten)
   - **Fehlende Unterlagen** — missing documents detected per side
2. **Add a RAG layer** using local embeddings (`sentence-transformers`) and ChromaDB, so relevant Mietrecht paragraphs are retrieved at query time and injected into the prompt.
3. **Update the frontend** to render the three legal categories as separate sections, plus a missing-documents alert panel.

No existing endpoints or data shapes are removed — all changes are additive or replacements of the prompt/model layer.

---

## Legal Taxonomy (from Formalia.md)

The three output categories and their authoritative anchors:

### Formell-rechtlich
Concerns procedural validity of documents and deadlines:
- Ladung § 377 ZPO, Ladungsfrist §§ 214, 217 ZPO
- Zustellung § 166 Abs. 1 ZPO
- Frist § 222 Abs. 1 ZPO
- Verjährung §§ 194–218 BGB

### Materiell-rechtlich
Concerns the substantive legal claim (Minderung and Rücktritt):
- **Minderung**: wirksamer Mietvertrag § 535 BGB, Mietmangel § 534 BGB,
  Maßgeblicher Zeitpunkt § 536 Abs. 1 BGB, Ausschlüsse §§ 536b/536c BGB,
  Rechtsfolge: Minderungsquote + Rückerstattung § 812 BGB
- **Rücktritt**: §§ 542 ff. BGB (ordentlich/außerordentlich, Vermieter/Mieter),
  §§ 543, 569, 573, 573a, 580 BGB

### Hauptverhandlung
Concerns what actually happened or is expected at trial — evidence and oral proceedings:
- Mündliche Verhandlung
- Beweisführung
- Zeugenaussagen
- Sachverständigengutachten
---

## Sub-Tasks

---

### Sub-Task 1 — Extend Pydantic models for the new output shape

**Intent**
The current `Topic` model has no legal category field. The new shape needs:
- `category`: one of `"formellrechtlich"`, `"materiellrechtlich"`, or `"hauptverhandlung"`
- `relevant_law`: list of cited paragraph strings (e.g. `"§ 536 BGB"`)
- A top-level `missing_documents` field on `SummaryResult` with per-side lists

**Expected Outcomes**
- `Topic` model has `category` (Literal with three values) and `relevant_law: list[str] = []`
- `MissingDocument` model: `side: str`, `items: list[str]`
- `SummaryResult` has `missing_documents: list[MissingDocument] = []`
- `LinkedSummary` in `linker.py` mirrors these new fields
- All existing fields kept for backward compatibility

**Todo List**
- [ ] Add `MissingDocument` Pydantic model to `summarizer.py`
- [ ] Add `category: Literal["formellrechtlich", "materiellrechtlich", "hauptverhandlung"]` and `relevant_law: list[str] = []` to `Topic`
- [ ] Add `missing_documents: list[MissingDocument] = []` to `SummaryResult`
- [ ] Mirror `missing_documents` in `LinkedSummary` in `linker.py`

**Relevant Context**
- `backend/services/summarizer.py` lines 43–62 (model definitions)
- `backend/services/linker.py` lines 26–34 (`LinkedSummary`)

**Status:** [ ] pending

---

### Sub-Task 2 — Rewrite the combined-overview system prompt

**Intent**
Replace `_overview_system_prompt()` with a prompt that:
1. Defines all three categories explicitly using the `Formalia.md` rules — with paragraph anchors for Formell and Materiell, and the five trial-proceedings sub-items for Hauptverhandlung
2. Instructs the model to detect missing documents per side
3. Specifies the exact JSON output shape including `category`, `relevant_law`, and `missing_documents`

The prompt is the single most important change — it is the mechanism by which the model learns the classification rules. Definitions must be concrete and exhaustive so the model never guesses category membership.

**Note on Hauptverhandlung**: this category has no fixed paragraph citations (it is factual/evidential, not normative). The model should still populate `relevant_law` where applicable (e.g. § 373 ZPO for witness examination, § 402 ZPO for expert witnesses), but `relevant_law` may be empty for Hauptverhandlung topics.

**Expected Outcomes**
- System prompt contains the full three-category Formalia taxonomy as a reference block
- Model assigns exactly one of the three categories to each topic
- Model lists BGB/ZPO paragraphs it relied on per topic (empty list allowed for Hauptverhandlung)
- Model lists missing documents per side under `missing_documents`
- The requested JSON schema in the prompt exactly matches the new Pydantic models from Sub-Task 1

**Todo List**
- [ ] Write `LEGAL_TAXONOMY` constant in `summarizer.py` derived from `Formalia.md` (all three categories)
- [ ] Rewrite `_overview_system_prompt()` to inject `LEGAL_TAXONOMY` and the new JSON schema
- [ ] Update `_parse_overview_response()` to parse `category`, `relevant_law`, and `missing_documents`
- [ ] Update `summarize_all_md()` to pass the new fields through to `SummaryResult`

**Relevant Context**
- `backend/services/summarizer.py` lines 104–200
- `Formalia.md` — full taxonomy source of truth
- New JSON shape defined in Sub-Task 1

**Status:** [ ] pending

---

### Sub-Task 3 — Add the RAG service

**Intent**
Create `backend/services/rag.py` with two responsibilities:
1. **Ingest**: chunk Mietrecht law texts stored in `backend/law_texts/` and index them into a local ChromaDB collection
2. **Retrieve**: given a query string, return the top-k most relevant law chunks to inject into the prompt

Use `sentence-transformers` with `intfloat/multilingual-e5-large` for embeddings — it handles German legal text well and runs fully locally.

The ingestion step runs once (or on restart if the DB is empty). Retrieval runs on every `/summarize` call.

**Expected Outcomes**
- `backend/services/rag.py` exists with `ingest_law_texts()` and `retrieve(query, top_k) -> list[str]`
- `backend/law_texts/` directory contains three files, one per category:
  - `mietrecht_materiell.md` — BGB §§ 534–543, 569, 573, 812 with short descriptions
  - `mietrecht_formell.md` — ZPO §§ 166, 214, 217, 222, 377 + BGB §§ 194–218 with descriptions
  - `mietrecht_hauptverhandlung.md` — ZPO §§ 355–414 (Beweisaufnahme), §§ 373–401 (Zeugen), §§ 402–414 (Sachverständige), trial procedure notes
- Each chunk stored with metadata: `{ "category": "...", "paragraph": "§ ..." }`
- ChromaDB persists to `backend/.chromadb/` (gitignored)
- `requirements.txt` updated: `chromadb`, `sentence-transformers`

**Todo List**
- [ ] Create `backend/law_texts/mietrecht_materiell.md` with relevant BGB paragraphs
- [ ] Create `backend/law_texts/mietrecht_formell.md` with relevant ZPO/BGB paragraphs
- [ ] Create `backend/law_texts/mietrecht_hauptverhandlung.md` with ZPO Beweisaufnahme paragraphs
- [ ] Create `backend/services/rag.py` with `ingest_law_texts()` and `retrieve()`
- [ ] Add `chromadb` and `sentence-transformers` to `requirements.txt`
- [ ] Add `backend/.chromadb/` to `.gitignore`

**Relevant Context**
- `backend/config.py` — add `CHROMA_PATH` and `EMBEDDING_MODEL` constants here
- `Formalia.md` — determines which paragraphs belong in which law text file

**Status:** [ ] pending

---

### Sub-Task 4 — Wire RAG into the summarize pipeline

**Intent**
Before calling the LLM in `summarize_all_md()`, query the RAG service with a short description of the uploaded documents and inject the retrieved chunks into the system prompt as a `## Relevante Rechtsgrundlagen` block.

This keeps `_overview_system_prompt()` clean — the static taxonomy stays separate from the dynamically retrieved paragraphs, which are appended at call time.

**Expected Outcomes**
- `summarize_all_md()` calls `retrieve()` with a query derived from document filenames/content
- Retrieved chunks appended to the system prompt before the LLM call
- If RAG is unavailable (empty DB), the call proceeds without it — no hard failure

**Todo List**
- [ ] Call `ingest_law_texts()` once on startup in `backend/main.py` (background, non-blocking)
- [ ] In `summarize_all_md()`, call `retrieve(query)` and append results to the system prompt
- [ ] Make RAG import optional (try/except) so the app starts even if ChromaDB is not yet installed

**Relevant Context**
- `backend/main.py` — startup event hook
- `backend/services/summarizer.py` — `summarize_all_md()` and `_overview_system_prompt()`
- `backend/services/rag.py` — created in Sub-Task 3

**Status:** [ ] pending

---

### Sub-Task 5 — Update the frontend

**Intent**
Render the new structured output:
1. Three separate topic sections in order: **Formell-rechtlich**, **Materiell-rechtlich**, **Hauptverhandlung**
2. Each topic card shows `relevant_law` as small pill badges beneath the title
3. A **Fehlende Unterlagen** warning panel at the bottom of the summary card, two columns (one per side)

**Visual section colours** (accent bar on left edge of each section header):
- Formell-rechtlich → blue (`#3b82d4`)
- Materiell-rechtlich → purple (`#7c5cd8`)
- Hauptverhandlung → teal (`#0d9488`)

**Expected Outcomes**
- Summary card has four visual sections: Formell, Materiell, Hauptverhandlung, Fehlende Unterlagen
- Topics in each section keep the existing two-column side-A / side-B layout
- `relevant_law` strings render as small pill badges on each topic title bar (or absent if empty)
- Missing documents shown as a two-column list (one column per side), amber warning colour

**Todo List**
- [ ] Add CSS: `.section-formell`, `.section-materiell`, `.section-hauptverhandlung`, `.missing-docs-panel`, `.law-badge`
- [ ] Update `renderTopicsHtml()` to group topics by `category` into three labelled sections
- [ ] Add `renderMissingDocsHtml()` helper
- [ ] Render `relevant_law` as badge pills inside each `.topic-title`
- [ ] Update summary card template to include the missing docs panel

**Relevant Context**
- `frontend/index.html` lines 248–295 (topic CSS), lines 596–642 (render functions)

**Status:** [ ] pending

---

## Implementation Order

Sub-tasks must be done in order — each builds on the previous:

```
Sub-Task 1 (models) → Sub-Task 2 (prompt) → Sub-Task 3 (RAG service)
                                          → Sub-Task 4 (wire RAG)
                                          → Sub-Task 5 (frontend)
```

Sub-Tasks 3, 4, and 5 can be reviewed independently after Sub-Task 2 is confirmed working.
