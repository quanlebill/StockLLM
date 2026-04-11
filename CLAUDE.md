# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
StockLLM is a Python project (configured via PyCharm/IntelliJ with a virtual environment named `StockLLM`)

## Constraints
- Do NOT access or read files outside of this repository directory (`D:\Personals\StockLLM`).

## Conversation About Finance — Workflow (Finance + Knowledge Verification Only)

> **This workflow applies ONLY when:**
> 1. The user is asking a **finance-related question** (stocks, macro, sectors, options, fundamentals, etc.), AND
> 2. The answer **requires verification against the base knowledge** (i.e. it is not a trivial factual question you already know with certainty).
>
> For non-finance questions (coding, general tasks, storing documents, creating files), skip this workflow entirely and respond directly.

### Steps — follow in order for every qualifying question: USE MCP SKILL
**Step 1 — Load context**
- Call `load_last_conversation` to retrieve prior Q&A from the current conversation key
- If the prior conversation exists and is related to the current question → keep the key (do nothing)
- If the prior conversation is unrelated or empty → call `change_conversation_key` to switch to a fresh key

**Step 2 — Format queries for the retrieval pipeline**
- From the user question, build a queries dict with one entry per relationship:
```json
{
  "Query #1": {
    "Type": "Question",
    "Question Word": "How",
    "Entities": ["GDP", "Fed Fund"],
    "Relationship": ["affect"]
  },
  "Query #2": {
    "Type": "Statement",
    "Entities": ["GDP", "Sector"],
    "Relationship": ["indicate"]
  }
}
```
- Rules:
  - `Type` must be `"Question"` or `"Statement"`
  - `Question Word` (Question only): one of `What` | `How` | `When` | `Where` | `Who`
  - `Relationship` is a list — multiple entries fan out into separate queries automatically
  - One complex question may produce multiple Query entries (one per relationship pair)
- Example with multiple relationships:
```json
{
  "Query #1": { "Type": "Question", "Question Word": "How",
                "Entities": ["Inflation", "Interest Rate"], "Relationship": ["affect"] },
  "Query #2": { "Type": "Question", "Question Word": "How",
                "Entities": ["Unemployment", "Interest Rate"], "Relationship": ["affect"] }
}
```

**Step 3 — Announce the conversation**
- Call `announce(user_question)` with the user's question
- This creates a new block in the conversation log and must be called BEFORE any retrieval
- Every subsequent tool call is automatically logged to the workflow from this point on

**Step 4 — Retrieve (single call)**
- Call `retrieve(queries=[...])` with the formatted query strings from Step 2
- The pipeline internally handles: lowercase → parse → entity canonicalization → cache lookup + LightRAG (concurrently)
- For each result in the response:
  - `cache.hit == "answer"` → a cached answer is ready in `combined`; use it immediately
  - `cache.hit == "miss"` → use `combined` (retrieval summary) to compose the answer
  - `error == "format_error"` → reformat that query string per the `message` hint and retry
- **If the retrieval pipeline is unavailable** → fall back to `invoke_skill` / `invoke_skills` as before
- Compose your answer from the `combined` field of each result

**Step 5 — Finalize**
- Call `finalize(answer, canonical, hash)` — logs the answer and triggers auto-cache
- Use the `canonical` and `hash` from any result in the `retrieve` response (or `preprocess_query` if you fell back to manual retrieval)
- ALWAYS call `finalize()` even when retrieval returned nothing — this saves the answer
- If the user later says an answer was wrong: call `preprocess_query()` to get canonical + hash, then `cache_invalidate(canonical, hash)`
- This completes the block: user → workflow → answer

### Rules
- Free to Answer, ALWAYS VERIFIED WITH BASE KNOWLEDGE
- If base knowledge returns nothing on a topic, you may fall back to your own knowledge or the internet
- Use `instruction/baseknowledge/RETRIEVE_GUIDE.md` for manual retrieval fallback details

### Ref
- Reference `CONTROL_PLANE_MCP.md` for how to use skills


## Detecting User Comments on Answers
If the user's message is **commenting on, correcting, or giving feedback about a previous answer**
(e.g. "that answer was wrong", "good answer", "you missed X", "add that the VIX also..."),
treat it as a comment — NOT a new question. Follow this flow instead of the normal Step 1–4 workflow:

1. Do NOT call `announce` — this is not a new block.
2. Call `log_comment(comment=<user's comment text>, block_index=<block they're referring to>)`.
   - If it's unclear which block they mean, default to `-1` (last block).
3. Acknowledge the comment briefly to the user.

Signals that a message is a comment (not a question):
- Short evaluative phrases: "good", "wrong", "correct", "nice", "that's right", "not quite"
- Explicit feedback: "you missed...", "add to your answer...", "the answer should also mention..."
- Corrections: "actually it's...", "that's not right because..."
- Approval/disapproval with no new question attached

If the message contains BOTH feedback AND a new question, log the comment first, then proceed with the normal workflow for the question.

## Description:
1. Retrieving base knowledge: refer to `instruction/baseknowledge/RETRIEVE_GUIDE.md`

2. Storing Documents: refer to `instruction/baseknowledge/STORING_GUIDE.md`

3. Creating: refer to `CREATING.md`

4. Reviewing pipeline: refer to `instruction/self_improvement`
