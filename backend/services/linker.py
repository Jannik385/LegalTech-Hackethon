"""Cross-linking service — Verlinkung der Nachweise.

Combines classification results (Sub-Task 3) and summary results (Sub-Task 4)
into a unified LinkedReport.  Each LinkedSummary entry carries an
evidence_links list of ClassificationResults whose filenames are mentioned in
the summary text.

Design principle: the filename-reference pass is the default, pure-Python
approach.  An optional AI-assisted pass can be added later by replacing or
extending _find_evidence_links() without touching the rest of the module.
"""

from __future__ import annotations

from pydantic import BaseModel

from backend.services.classifier import ClassificationResult
from backend.services.summarizer import SummaryResult, Topic


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class LinkedSummary(BaseModel):
    """A single summary entry with its linked evidence items."""

    filename: str
    summary: str
    key_facts: list[str]
    template_output: str
    topics: list[Topic] = []
    evidence_links: list[ClassificationResult]


class LinkedReport(BaseModel):
    """The full cross-linked report produced by link_results()."""

    entries: list[LinkedSummary]


# ---------------------------------------------------------------------------
# Filename-reference pass
# ---------------------------------------------------------------------------


def _find_evidence_links(
    summary: SummaryResult,
    classifications: list[ClassificationResult],
) -> list[ClassificationResult]:
    """Return all ClassificationResults whose filename appears in the summary.

    The check is case-insensitive and scans the summary paragraph, key facts,
    and template_output so that any textual reference is caught.
    """
    # Build a single searchable blob from all text fields of the summary
    haystack = " ".join(
        [
            summary.summary,
            summary.template_output,
            *summary.key_facts,
        ]
    ).lower()
    # Also include all topic point text so filenames referenced there are found
    for topic in summary.topics:
        for side in topic.sides:
            haystack += " " + " ".join(side.points).lower()

    linked: list[ClassificationResult] = []
    for cls_result in classifications:
        if cls_result.filename.lower() in haystack:
            linked.append(cls_result)
    return linked


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def link_results(
    summaries: list[SummaryResult],
    classifications: list[ClassificationResult],
) -> LinkedReport:
    """Combine summaries and classifications into a LinkedReport.

    For each summary, runs a filename-reference pass against all classified
    files and attaches matching ones as evidence_links.
    """
    entries: list[LinkedSummary] = []
    for summary in summaries:
        evidence = _find_evidence_links(summary, classifications)
        entries.append(
            LinkedSummary(
                filename=summary.filename,
                summary=summary.summary,
                key_facts=summary.key_facts,
                template_output=summary.template_output,
                topics=summary.topics,
                evidence_links=evidence,
            )
        )
    return LinkedReport(entries=entries)
