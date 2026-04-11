# Retrieving Knowledge

## Overview

Use the `retrieve` MCP tool to query base knowledge. It handles everything internally —
entity canonicalization, cache lookup, KG query, document graph search, and page loading —
in a single call.

The retrieve pipeline is merged into `control_plane.py` and runs on **port 8000**.

---

## How to Call `retrieve`

Pass a dict of structured queries. Each entry describes one relationship to look up.

```json
{
  "Query #1": {
    "Type": "Question",
    "Question Word": "How",
    "Entities": ["GDP", "Fed Fund"],
    "Relationship": ["affect/right"]
  },
  "Query #2": {
    "Type": "Statement",
    "Entities": ["Inflation", "Interest Rate"],
    "Relationship": ["indicate/right"]
  }
}
```

**Field rules:**
| Field | Required | Values |
|---|---|---|
| `Type` | always | `"Question"` or `"Statement"` |
| `Question Word` | Question only | What, How, When, Where, Who |
| `Entities` | always | list of entity name strings |
| `Relationship` | always | list of `"relationship/direction"` strings |

`Relationship` is a list — multiple entries fan out into separate queries automatically.

---

## Reading the Response

Each result in `results` corresponds to one query. Use the `combined` field as your answer context.

```json
{
  "results": [
    {
      "query_index": 0,
      "cache": { "hit": "answer" | "document" | "miss" },
      "combined": "..."
    }
  ]
}
```

| `cache.hit` | What to do |
|---|---|
| `"answer"` | Respond immediately — cached answer is in `combined` |
| `"miss"` | Compose answer from `combined` (retrieval summary) |

**Policy entries in `combined`** follow this format:
```
[Policy] cause: [gdp < -1%], policy: [fed cuts rate ~0.5%] | Caused by: gdp | Affects: federal_funds_rate
```
- `Caused by` — entities whose state triggered the policy condition
- `Affects` — entities changed/impacted as a result

On format error:
```json
{ "error": "format_error", "message": "..." }
```
Fix the offending query per the `message` hint and retry.

---

## Fallback — Manual Retrieval
