# LegalTech Document Analyzer — Plan

## Overview

A local web application that lets a user upload legal documents (`.md` files and supporting files like images) via a browser-based HTML frontend. The backend (Python FastAPI) routes those files through the OpenRouter AI API to perform two parallel tasks:

1. **Klassifikation der Beweise** — classify non-Markdown files (e.g. images) by their evidentiary type/category
2. **Zusammenfassung in Template** — summarize the content of `.md` files and insert the result into a (later-specified) output template

Both results are then merged in a **Verlinkung der Nachweise** step, which cross-links classifications back to the summaries. The final output is a **dashboard** — a single HTML page showing the structured summary with clickable links to each classified piece of evidence.

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Static HTML + vanilla JS (single file) |
| Backend | Python FastAPI (local server) |
| AI | OpenRouter Python SDK (`openrouter` package) |
| AI Model | `openai/gpt-5.4-mini` (swappable) |
| Config | `.env` file with `OPENROUTER_API_KEY` |

### Non-Goals

- No database or persistent storage — session-scoped only
- No user authentication
- The output template structure is not finalized yet (placeholder approach used)
- No deployment / cloud hosting

---

## Sub-Tasks

---

### Sub-Task 1 — Project Scaffold

**Status:** `[x] done`

**Intent:**
Set up the project directory structure, dependencies, and a runnable skeleton so every subsequent sub-task has a stable foundation to build on.

**Expected Outcomes:**
- `backend/main.py` starts with `uvicorn` and serves the static frontend
- `frontend/index.html` loads in a browser at `http://localhost:8000`
- `/health` endpoint returns `{"status": "ok"}`
- `.env` is read automatically; `OPENROUTER_API_KEY` is accessible in the backend
- `requirements.txt` contains all needed packages

**Todo List:**
1. Create directory layout: `backend/`, `frontend/`, `backend/services/`
2. Create `requirements.txt` with `fastapi`, `uvicorn[standard]`, `openrouter`, `python-dotenv`, `python-multipart`
3. Create `backend/main.py` with a FastAPI app, static file mount for `frontend/`, and a `/health` GET endpoint
4. Create `frontend/index.html` as a minimal HTML shell (title, placeholder body)
5. Copy `.env` pattern from `openrouter-example/` and document the required key

**Relevant Context:**
- [`openrouter-example/open_router.py`](openrouter-example/open_router.py) — shows SDK initialization pattern with `python-dotenv`
- [`openrouter-example/requirements.txt`](openrouter-example/requirements.txt) — base dependencies to extend

---

### Sub-Task 2 — File Upload Endpoint + Frontend Upload UI

**Status:** `[x] done`

**Intent:**
Allow the user to select and upload multiple files at once. The backend separates incoming files into two buckets: `.md` files and everything else (images, PDFs, etc.). This separation drives all downstream processing.

**Expected Outcomes:**
- Frontend shows a drag-and-drop / file picker area that accepts multiple files
- `POST /upload` endpoint receives a multipart form upload
- Backend returns a JSON response listing which files landed in which bucket: `{ "md_files": [...], "other_files": [...] }`
- Files are held in-memory (or a temp directory) for the duration of the session

**Todo List:**
1. Add `POST /upload` endpoint in `backend/main.py` accepting `List[UploadFile]`
2. Implement file-type separation logic: `.md` extension → md bucket, everything else → other bucket
3. Store uploaded file contents in a session-scoped dict (keyed by filename)
4. Add upload form + file list preview to `frontend/index.html` using `fetch()` + `FormData`
5. Display the two buckets (md files / other files) in the UI after upload

**Relevant Context:**
- FastAPI `UploadFile` + `python-multipart` for multipart handling
- Sub-Task 1 scaffold for the app entry point

---

### Sub-Task 3 — Evidence Classification Service (non-MD files)

**Status:** `[x] done`

**Intent:**
For every non-Markdown file, call the OpenRouter API and ask the model to classify the file as a piece of legal evidence (e.g. "Foto", "Vertrag", "Rechnung", "Unterschrift", "Sonstiges"). Each classification result is stored and later linked into the final dashboard.

**Expected Outcomes:**
- `backend/services/classifier.py` contains a function `classify_file(filename, file_bytes, mime_type) -> ClassificationResult`
- `ClassificationResult` is a dataclass/Pydantic model with fields: `filename`, `category`, `confidence_note`
- `POST /classify` endpoint triggers classification for all files in the "other" bucket and returns results as JSON
- Results are rendered in the frontend as a tagged list

**Todo List:**
1. Create `backend/services/classifier.py`
2. For image files: encode as base64 and pass to the model with a classification prompt (vision-capable model or describe-then-classify pattern)
3. For non-image binary files: pass filename + extension with a metadata-only prompt
4. Define the classification prompt (categories: Foto, Vertrag, Rechnung, Unterschrift, Sonstiges — extensible)
5. Return structured JSON per file; store results in session state
6. Add `POST /classify` endpoint in `main.py` that calls the service for each queued other-file
7. Render classification badges per file in the frontend

**Relevant Context:**
- [`openrouter-example/open_router.py`](openrouter-example/open_router.py) — SDK call pattern to reuse
- Allowed models from README: `openai/gpt-5.4-mini` as default
- Sub-Task 2 for the session file store

---

### Sub-Task 4 — Markdown Summarization Service

**Status:** `[x] done`

**Intent:**
For every `.md` file, call the OpenRouter API to extract and summarize the legal content. The summary is inserted into a placeholder output template. Because the final template is not yet specified, a clearly marked placeholder structure is used — easy to swap out later.

**Expected Outcomes:**
- `backend/services/summarizer.py` contains `summarize_md(filename, content: str) -> SummaryResult`
- `SummaryResult` has fields: `filename`, `summary`, `key_facts` (list), `template_output` (rendered string)
- The template is a simple placeholder in a constant `SUMMARY_TEMPLATE` — a string with `{filename}`, `{summary}`, `{key_facts}` slots
- `POST /summarize` endpoint processes all queued `.md` files and returns results
- Frontend shows collapsible summary cards per file

**Todo List:**
1. Create `backend/services/summarizer.py`
2. Define `SUMMARY_TEMPLATE` constant as a clearly-commented placeholder (to be replaced later)
3. Write summarization prompt instructing the model to extract: summary paragraph, bullet-point key facts
4. Parse model response into `SummaryResult` fields
5. Render `template_output` by filling `SUMMARY_TEMPLATE` slots
6. Add `POST /summarize` endpoint in `main.py`
7. Render summary cards in the frontend (collapsible, one per file)

**Relevant Context:**
- Sub-Task 3 for the service pattern to mirror
- Sub-Task 2 for the session file store
- Template will be specified by the user later — keep `SUMMARY_TEMPLATE` isolated and easy to replace

---

### Sub-Task 5 — Verlinkung der Nachweise (Cross-Linking)

**Status:** `[x] done`

**Intent:**
Combine the classification results (Sub-Task 3) and summary results (Sub-Task 4) into a unified linked data structure. Each classified evidence item is associated with the summaries that reference it (by filename match or AI-assisted linking).

**Expected Outcomes:**
- `backend/services/linker.py` contains `link_results(summaries, classifications) -> LinkedReport`
- `LinkedReport` contains a list of summary entries, each with an `evidence_links` list pointing to classified files
- `POST /link` endpoint returns the full linked report as JSON
- The frontend receives this structure and prepares it for dashboard rendering

**Todo List:**
1. Create `backend/services/linker.py`
2. Implement a simple filename-reference pass: check if any classified file's name appears in the markdown summary text
3. Optionally: add an AI-assisted pass where the model identifies which evidence items support which summary claims
4. Produce `LinkedReport` as a Pydantic model
5. Add `POST /link` endpoint in `main.py`
6. Store the linked report in session state for the dashboard step

**Relevant Context:**
- Sub-Task 3 and Sub-Task 4 outputs are the inputs here
- Keep linking logic modular so the AI-assisted pass can be added/removed independently

---

### Sub-Task 6 — Dashboard Output

**Status:** `[x] done`

**Intent:**
Render the final `LinkedReport` as a self-contained HTML dashboard page — the last step in the flow. The dashboard shows the template-filled summary with clickable anchor links jumping to each classified evidence item below.

**Expected Outcomes:**
- `GET /dashboard` endpoint returns a fully rendered HTML page (or JSON consumed by the frontend)
- Each summary section has an "Nachweise" list with clickable links
- Each evidence item is anchored and shows its classification badge
- The dashboard can be downloaded as a single `.html` file
- The frontend has a "Zum Dashboard" button that navigates to `/dashboard`

**Todo List:**
1. Create `backend/services/renderer.py` with `render_dashboard(linked_report) -> str` returning HTML
2. Build the HTML template: header, summary sections with anchor links, evidence gallery at the bottom
3. Add `GET /dashboard` endpoint in `main.py` returning `HTMLResponse`
4. Add "Dashboard generieren" button to the frontend that triggers the full pipeline (upload → classify → summarize → link → dashboard) in sequence
5. Add "Download als HTML" button using a Blob URL in the frontend

**Relevant Context:**
- Sub-Task 5 `LinkedReport` is the sole input
- Keep dashboard HTML template separate from logic for easy styling later

---

## Processing Flow

```
User uploads files (frontend)
        |
        v
POST /upload  →  splits into [md_files] and [other_files]
        |
   _____|______
  |            |
  v            v
POST           POST
/summarize     /classify
  |            |
  |____________|
        |
        v
POST /link  →  LinkedReport
        |
        v
GET /dashboard  →  HTML Dashboard
```

---

## Key Design Decisions

- **Stateless session via in-memory dict**: simplest approach for a local hackathon tool; no DB needed
- **Template as a named constant**: `SUMMARY_TEMPLATE` in `summarizer.py` is the single place to update when the user specifies the real template
- **Modular services**: each step (`classifier`, `summarizer`, `linker`, `renderer`) is its own file — easy to test and replace independently
- **Model is a single constant**: `MODEL = "openai/gpt-5.4-mini"` defined once in a `backend/config.py`, swappable without touching service code
