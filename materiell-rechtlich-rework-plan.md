# Plan: Rework Materiell-rechtlich Summary Structure

## Top-Level Overview

The file `Formalia.md` defines a fixed legal review outline used as a template.  
When a lawyer's brief (Markdown file) is fed as input, a **summary** must be generated.  
That summary must **not** invent chapters from the brief — instead, it must walk every single node of the `2. Materiell-rechtlich` hierarchy in `Formalia.md` (at every depth level) and review the brief against each node.

The result: a structured output that mirrors the `2. Materiell-rechtlich` outline exactly, with each node containing a review of what the brief says (or doesn't say) about that specific legal element.

---

## Design Intent

- The `Formalia.md` outline is the **fixed skeleton** — it is never modified.
- The input brief is the **source material** to be reviewed against the skeleton.
- The summary output preserves the **exact hierarchy** of `2. Materiell-rechtlich`, including every level, e.g.:
  - `2.1 Minderung`
    - `2.1.1 Eröffnung des Mängelgewährleistungsrechts`
      - `2.1.1.1 Wirksamer Mietvertrag, § 535 BGB`
      - `2.1.1.2 Mietmangel, § 534 BGB`
      - `2.1.1.3 Maßgeblicher Zeitpunkt ...`
      - `2.1.1.4 Kein Ausschluss`
        - `2.1.1.4.1 Vertraglich`
        - `2.1.1.4.2 Gesetzlich`
          - `2.1.1.4.2.1 Kenntnis, § 536b BGB`
          - `2.1.1.4.2.2 Unterlassene Mängelanzeige, § 536c BGB`
    - `2.1.2 Rechtsfolge`
      - `2.1.2.1 Herabsetzung des Anspruchs auf Mietzahlung ...`
      - `2.1.2.2 Rückerstattung der ungeminderten Miete, § 812 BGB`
  - `2.2 Rücktritt`
    - `2.2.1 Grundsätzlich § 542 ff. BGB`
      - `2.2.1.1 Vermieter`
        - Ordentlich / Außerordentlich / Fristlos / Befristet
      - `2.2.1.2 Mieter`
        - Ordentlich / Außerordentlich / Fristlos / Befristet
- **Only leaf nodes** (nodes with no direct subchapters) receive the two placeholder lines. Intermediate nodes (those that have subchapters) are named but carry no placeholders — their content is expressed entirely through their subchapters.
- At each leaf node, the review entry answers: **What does the brief argue for this element? Is it addressed, supported, or missing?**
- No extra sections are added from the brief content.

---

## Sub-Tasks

---

### Sub-Task 1: Rework the `2. Materiell-rechtlich` section in `Formalia.md`

**Intent**  
Expand every leaf node (and intermediate node) in the `2. Materiell-rechtlich` section so that each one has a clearly labelled review placeholder. This makes it explicit that when a brief is processed, the reviewer/LLM must fill in an assessment for each node — not derive a structure from the brief.

**Expected Outcomes**  
- Every node at every depth level inside `2. Materiell-rechtlich` has an inline review placeholder, e.g.:  
  `→ Aus dem Schriftsatz: [Zusammenfassung des Arguments / nicht behandelt]`  
  `→ Beweise / Begründungen: [Belege aus dem Schriftsatz / fehlen]`  
- The hierarchy is identical to the existing one — no nodes are added or removed.
- The style mirrors how `1. Formell-rechtlich` handles its sub-items (a clean list with space for evidence and reasoning under each point).

**Todo List**
- [x] Under each existing **leaf node** in `2. Materiell-rechtlich`, add two placeholder lines:
  - `→ Aus dem Schriftsatz:` (what the brief says about this element)
  - `→ Beweise / Begründungen:` (what evidence or legal reasoning is cited)
- [x] Intermediate nodes (nodes that have direct subchapters) are named only — no placeholders. Examples: `Minderung`, `Eröffnung des Mängelgewährleistungsrechts`, `Kein Ausschluss`, `Gesetzlich`, `Rechtsfolge`, `Rücktritt`, `Grundsätzlich`, `Vermieter`, `Mieter`, `Außerordentlich`, `Fristlos`.
- [x] Do NOT add any new chapters or restructure the hierarchy.
- [x] Do NOT modify `1. Formell-rechtlich` or `3. Hauptverhandlung`.

**Relevant Context**  
- File: [`Formalia.md`](Formalia.md) — lines 13–72 are the full `2. Materiell-rechtlich` block.  
- The two placeholder lines per node are the **only** addition — no heading levels change.

**Status**: `[x] done`

---

## Open Questions / Decisions Already Confirmed

| Question | Answer |
|---|---|
| Should new chapters be invented from brief content? | **No** — the skeleton is fixed. |
| Should every depth level get a review slot? | **Only leaf nodes** — intermediate nodes (with subchapters) are named but hold no placeholders. |
| Should `1. Formell-rechtlich` be changed too? | **No** — only `2. Materiell-rechtlich`. |
| What language for the placeholders? | **German** — consistent with the document. |
