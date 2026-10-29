import mimetypes
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from typing import List

from backend.services.classifier import classify_file
from backend.services.summarizer import summarize_all_md
from backend.services.linker import link_results
from backend.services.renderer import render_dashboard
from backend.services.rag import ingest_law_texts


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Index law texts into ChromaDB on startup (no-op if already indexed or RAG unavailable)."""
    ingest_law_texts()
    yield


app = FastAPI(title="LegalTech Document Analyzer", lifespan=lifespan)

# ---------------------------------------------------------------------------
# In-memory session store — keyed by filename, value is raw bytes.
# Cleared and repopulated on every POST /upload call.
# ---------------------------------------------------------------------------
session: dict = {
    "md_files": {},        # filename -> bytes
    "other_files": {},     # filename -> bytes
    "classifications": {}, # filename -> ClassificationResult
    "summaries": {},       # filename -> SummaryResult
    "linked_report": None, # LinkedReport | None
}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)) -> dict:
    """Accept multiple files, split into md vs. other buckets, store in-memory."""
    session["md_files"].clear()
    session["other_files"].clear()

    for file in files:
        contents = await file.read()
        if file.filename.lower().endswith(".md"):
            session["md_files"][file.filename] = contents
        else:
            session["other_files"][file.filename] = contents

    return {
        "md_files": list(session["md_files"].keys()),
        "other_files": list(session["other_files"].keys()),
    }


@app.post("/classify")
def classify_files() -> dict:
    """Classify every file in the other_files bucket and store results in session."""
    other_files: dict = session["other_files"]
    if not other_files:
        raise HTTPException(status_code=400, detail="Keine anderen Dateien im Session-Store.")

    results = []
    session["classifications"].clear()

    for filename, file_bytes in other_files.items():
        mime_type, _ = mimetypes.guess_type(filename)
        mime_type = mime_type or "application/octet-stream"

        result = classify_file(filename, file_bytes, mime_type)
        session["classifications"][filename] = result
        results.append(result.model_dump())

    return {"classifications": results}


@app.post("/summarize")
def summarize_files() -> dict:
    """Combine all .md files into one overview and summarize them together."""
    md_files: dict = session["md_files"]
    if not md_files:
        raise HTTPException(status_code=400, detail="Keine Markdown-Dateien im Session-Store.")

    session["summaries"].clear()

    decoded = {fname: data.decode("utf-8", errors="replace") for fname, data in md_files.items()}
    result = summarize_all_md(decoded)
    session["summaries"][result.filename] = result

    return {"summaries": [result.model_dump()]}


@app.post("/link")
def link_files() -> dict:
    """Cross-link summaries with classifications and store result in session."""
    summaries = list(session["summaries"].values())
    classifications = list(session["classifications"].values())

    if not summaries:
        raise HTTPException(status_code=400, detail="Keine Zusammenfassungen im Session-Store.")

    linked_report = link_results(summaries, classifications)
    session["linked_report"] = linked_report
    return linked_report.model_dump()


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    """Render the LinkedReport as a self-contained HTML dashboard page."""
    linked_report = session["linked_report"]
    if linked_report is None:
        raise HTTPException(
            status_code=400,
            detail="Kein verlinkter Bericht im Session-Store. Bitte zuerst POST /link aufrufen.",
        )
    html = render_dashboard(linked_report)
    return HTMLResponse(content=html)


# Static frontend mount — must come after all API routes so it does not shadow them
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
