# Plan: Rework Summary Structure — Formell-rechtlich & Materiell-rechtlich

## Top-Level Overview

The file `Formalia.md` defines a fixed legal review outline used as a template.
When a lawyer's brief (Markdown file) is fed as input, a **summary** must be generated.
That summary must **not** invent chapters from the brief — instead, it must walk every single node of **both** `1. Formell-rechtlich` and `2. Materiell-rechtlich` in `Formalia.md` (at every depth level) and review the brief against each node.

The result: a structured output that mirrors the full outline exactly, with each node containing a review of what the brief says (or doesn't say) about that specific legal element.

---

## Design Intent

- The `Formalia.md` outline is the **fixed skeleton** — it is never modified.
- The input brief is the **source material** to be reviewed against the skeleton.
- The summary output preserves the **exact hierarchy** of **both sections**, including every level.
- `1. Formell-rechtlich` hierarchy (all leaf nodes):
  - `1.1 Ladung § 377 ZPO und Ladungsfrist § 217, 214 ZPO`
  - `1.2 Zustellung § 166 Abs. 1 ZPO`
  - `1.3 Frist § 222 Abs. 1 ZPO`
  - `1.4 Verjährung § 194-218 BGB`
- `2. Materiell-rechtlich` hierarchy (all leaf nodes), including every level, e.g.:
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

---

### Sub-Task 2: Add placeholders to `1. Formell-rechtlich` in `Formalia.md`

**Intent**
Apply the same review placeholder pattern to every node in `1. Formell-rechtlich`, so briefs are reviewed against procedural law points as well as substantive law points.

**Expected Outcomes**
- All 4 nodes in `1. Formell-rechtlich` have the two placeholder lines beneath them:
  `→ Aus dem Schriftsatz: [Zusammenfassung des Arguments / nicht behandelt]`
  `→ Beweise / Begründungen: [Belege aus dem Schriftsatz / fehlen]`
- All 4 nodes are leaf nodes — no intermediate node logic needed.
- `2. Materiell-rechtlich` and `3. Hauptverhandlung` are untouched.

**Todo List**
- [ ] Add the two placeholder lines under each of the 4 nodes in `1. Formell-rechtlich`:
  - `Ladung § 377 ZPO und Ladungsfrist § 217, 214 ZPO`
  - `Zustellung § 166 Abs. 1 ZPO`
  - `Frist § 222 Abs. 1 ZPO`
  - `Verjährung § 194-218 BGB`
- [ ] Do NOT modify `2. Materiell-rechtlich` or `3. Hauptverhandlung`.

**Relevant Context**
- File: [`Formalia.md`](Formalia.md) — lines 3–11 are the full `1. Formell-rechtlich` block.

**Status**: `[x] done`

---

## Open Questions / Decisions Already Confirmed

| Question | Answer |
|---|---|
| Should new chapters be invented from brief content? | **No** — the skeleton is fixed. |
| Should every depth level get a review slot? | **Only leaf nodes** — intermediate nodes with subchapters are named but hold no placeholders. |
| Should `1. Formell-rechtlich` be changed too? | **Yes** — added in Sub-Task 2. |
| What language for the placeholders? | **German** — consistent with the document. |
