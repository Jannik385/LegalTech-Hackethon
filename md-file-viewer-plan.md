# Plan: Clickable Markdown File Viewer

## Top-Level Overview

When a `.md` filename appears in the summary cards (upload UI) or in the
`/dashboard` HTML page, it should be a clickable link. Clicking it opens a
modal overlay that fetches the raw file content from the server and displays it
in a scrollable `<pre>` block. No external JS libraries are added.

The change touches three files:
- `backend/main.py` — new `GET /file/{filename}` endpoint
- `frontend/index.html` — clickable filename + modal in the upload UI
- `backend/services/renderer.py` — clickable filename + modal in the dashboard

---

## Sub-Tasks

---

### Sub-Task 1: Add `GET /file/{filename}` endpoint

**Intent**
Expose the raw text of any uploaded `.md` file so the frontend can fetch and
display it on demand. The file bytes are already stored in
`session["md_files"]`.

**Expected Outcomes**
- `GET /file/{filename}` returns `{"filename": "...", "content": "..."}` when
  the file exists in the current session.
- Returns HTTP 404 if the filename is not in `session["md_files"]`.
- No changes to any other endpoints.

**Todo List**
- [ ] Add a `GET /file/{filename}` route to `backend/main.py` that looks up
  `session["md_files"][filename]`, decodes it to UTF-8, and returns a JSON
  dict `{"filename": filename, "content": decoded_text}`.
- [ ] Raise `HTTPException(404)` if the filename is absent.

**Relevant Context**
- [`backend/main.py`](backend/main.py) — `session["md_files"]` dict at line 30.
  Pattern to follow: the existing `/classify` route at line 62 for error handling style.

**Status**: `[ ] pending`

---

### Sub-Task 2: Clickable filenames + modal in `index.html`

**Intent**
In the upload UI, the summary cards (`renderSummaryCards`) and linked cards
(`renderLinkedCards`) display `.md` filenames as plain text. Wrap these in a
clickable element that fetches `/file/{filename}` and shows the content in an
inline modal overlay.

**Expected Outcomes**
- In `renderSummaryCards`, the `<summary>` filename text becomes a clickable
  `<button>` (or `<span>` styled as a link) next to the collapsible arrow.
- In `renderLinkedCards`, `entry.filename` in the `<summary>` is similarly
  clickable.
- Clicking opens a full-screen modal with:
  - The filename as a title
  - A scrollable `<pre>` showing the raw markdown text
  - A close button (×) in the top-right corner
- Clicking outside the modal content or pressing Escape closes it.
- The modal is defined once in the HTML and reused for all filenames.
- While loading, the pre shows a "Lade…" placeholder.

**Todo List**
- [ ] Add a modal HTML structure (hidden by default) to `index.html` — one
  `<div id="file-modal">` with an inner content box, a `<h3 id="modal-title">`,
  a `<pre id="modal-body">`, and a `<button id="modal-close">×</button>`.
- [ ] Add CSS for the modal: fixed full-screen overlay, centred content box,
  scrollable pre, close button styling.
- [ ] Add JS functions `openFileModal(filename)` and `closeFileModal()`.
  `openFileModal` sets the title, shows "Lade…", makes the modal visible, then
  `fetch('/file/' + encodeURIComponent(filename))` and puts `data.content`
  into `#modal-body`.
- [ ] Wire Escape key and backdrop click to `closeFileModal()`.
- [ ] In `renderSummaryCards`, change the `<summary>` template so the filename
  is wrapped in
  `<span class="md-link" onclick="openFileModal('...')">filename</span>`.
- [ ] In `renderLinkedCards`, do the same for `entry.filename` in the summary.

**Relevant Context**
- [`frontend/index.html`](frontend/index.html:701) — `renderSummaryCards` at line 701.
- [`frontend/index.html`](frontend/index.html:857) — `renderLinkedCards` at line 857.
- The existing `escHtml()` helper at line 898 must be used for all interpolated
  values to prevent XSS.

**Status**: `[ ] pending`

---

### Sub-Task 3: Clickable filenames + modal in the dashboard renderer

**Intent**
In the `/dashboard` HTML page, `_render_summary_section()` currently renders
the `.md` filename as a plain `<h2>` text. Make it a clickable element that
opens the same modal pattern — this time entirely self-contained inside the
dashboard's inline `<script>` and `<style>`.

**Expected Outcomes**
- Each summary card `<h2>` filename in the dashboard becomes a clickable
  `<button>` or `<a>` that triggers a modal.
- The modal is the same visual pattern as in `index.html` (fixed overlay, `<pre>` content, close button).
- The modal JS and CSS are inlined once in the dashboard's `<style>` and
  `<script>` blocks inside `render_dashboard()`.
- Fetches `/file/{filename}` — works only while the server is running (confirmed by user).

**Todo List**
- [ ] In `render_dashboard()` in `backend/services/renderer.py`, add modal CSS
  to the existing `<style>` block.
- [ ] Add a modal HTML div and inline JS (`openFileModal` / `closeFileModal`)
  to the `<body>` of the returned HTML template.
- [ ] In `_render_summary_section()`, change the `<h2>` that renders
  `entry.filename` so it wraps the name in a
  `<button onclick="openFileModal('...')">` element.

**Relevant Context**
- [`backend/services/renderer.py`](backend/services/renderer.py:246) —
  `_render_summary_section` at line 246; the `<h2>` at line 249.
- [`backend/services/renderer.py`](backend/services/renderer.py:332) —
  `render_dashboard` HTML template starts at line 332; `<style>` block at
  line 338.

**Status**: `[ ] pending`

---

## Open Decisions Confirmed

| Question | Answer |
|---|---|
| Display format for file content | `<pre>` block in a modal (no markdown renderer library) |
| Where to add clickable filenames | Both `index.html` and `/dashboard` |
| Dashboard offline support needed? | No — fetch from `/file/{filename}` while server runs is fine |
