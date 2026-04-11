# Storing a Document via Control Plane

## Overview

When a user says they want to store a PDF as baseknowledge, use skills under the
`baseknowledge` category exclusively. Always call `list_skills(category="baseknowledge")`
first to confirm available skills before proceeding.

The storing workflow has 3 stages, each backed by a running FastAPI service:

| Service        | Port | Skills prefix              |
|----------------|------|----------------------------|
| chunking.py    | 8004 | `baseknowledge.get_topics`, `baseknowledge.select_file`, `baseknowledge.split_pdf` |
| docs_analysis  | 8001 | `baseknowledge.get_page`, `baseknowledge.save_summary`, `baseknowledge.analysis_status` |
| storing        | 8002 | `baseknowledge.add_entities`, `baseknowledge.add_relationship` |

---

## Step-by-Step Control Plane Requests

### Stage 1 — Chunking

**Step 1: Ask the user for a topic, then fetch existing topics**
```json
{
  "skill_name": "baseknowledge.get_topics",
  "arguments": {}
}
```
Returns: `{ "topics": ["finance", "macro", ...] }`

Compare the user's topic against the list. Reuse an existing topic name if it matches
or is similar. Confirm with the user if unsure.

---

**Step 2: Open a file picker so the user selects the PDF**
```json
{
  "skill_name": "baseknowledge.select_file",
  "arguments": {}
}
```
Returns: `{ "filepath": "C:/Users/.../document.pdf" }`

A native file dialog opens on the user's screen. The filepath comes back automatically.

---

**Step 3: Split the PDF into individual pages**
```json
{
  "skill_name": "baseknowledge.split_pdf",
  "arguments": {
    "filepath": "<filepath from previous step>",
    "topic":    "<confirmed topic name>"
  }
}
```
Returns:
```json
{
  "output_dir":   "baseknowledge/docs/finance/document_name",
  "topic":        "finance",
  "doc_name":     "document_name",
  "total_pages":  42
}
```
Save `output_dir`, `doc_name`, and `total_pages` — needed for Stage 2.

---

### Stage 2 — Page-by-Page Analysis

**Loop — repeat until `is_last: true`:**

**Step 4: Fetch the current page**
```json
{
  "skill_name": "baseknowledge.get_page",
  "arguments": {}
}
```
Returns:
```json
{
  "page_index":  3,
  "total_pages": 42,
  "is_last":     false,
  "content":     "Chapter 2: ..."
}
```
The page index auto-increments after each call.

---

**Step 5: Summarize the content, then save it**

Read the `content` field and produce a concise summary (2-4 sentences max).
Then call:
```json
{
  "skill_name": "baseknowledge.save_summary",
  "arguments": {
    "index":   3,
    "summary": "This page covers ..."
  }
}
```
Returns: `{ "status": "saved", "page_index": 3 }`

Repeat Steps 4–5 until `is_last: true`.

---

**Check progress at any time:**
```json
{
  "skill_name": "baseknowledge.analysis_status",
  "arguments": {}
}
```
Returns: `{ "current_page_index": 7, "total_pages": 42, "summary_file": "..." }`

---

### Stage 3 — Build & Store the Knowledge Graph

After the loop completes, read `docs_summary_file.txt` from `output_dir`.
From the summaries, identify the entity hierarchy:
- **Root**: the document/book name (always the first entity)
- **Level 1**: main chapters
- **Level 2**: sub-fields of each chapter
- **Level 3+**: smaller sub-fields if they exist

**Step 6: Store entities**
```json
{
  "skill_name": "baseknowledge.add_entities",
  "arguments": {
    "entities": {
      "BookName": {
        "page_index":        [[0, 41]],
        "summary":           "What this book is about...",
        "included_entities": ["Chapter1", "Chapter2"],
        "keywords":          ["keyword1", "keyword2", "...up to 15"]
      },
      "Chapter1": {
        "page_index":        [[1, 10]],
        "summary":           "What Chapter 1 covers...",
        "included_entities": ["SubField1", "SubField2"],
        "keywords":          ["..."]
      }
    }
  }
}
```
`related_to` edges are auto-created from each entity to its `included_entities`.

---

**Step 7: Add explicit relationships (optional)**
```json
{
  "skill_name": "baseknowledge.add_relationship",
  "arguments": {
    "relationship": "related_to",
    "from_entity":  "Chapter1",
    "to_entity":    "Chapter2"
  }
}
```

---

## Token-Saving Rules

- Never store raw page content — only summaries
- Keep summaries to 2-4 sentences per page
- Build entities from the summary file only — no re-reading raw pages
- Pass `output_dir`, `doc_name`, `total_pages` forward across steps — don't re-derive them
