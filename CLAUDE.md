# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
StockLLM is a Python project (configured via PyCharm/IntelliJ with a virtual environment named `StockLLM`)

## Constraints
- Do NOT access or read files outside of this repository directory (`D:\Personals\StockLLM`).

---

## Workflows

> **Workflow selection:**
> - Finance question requiring knowledge verification → **Workflow 1**
> - Stock buying recommendation → **Workflow 2**
> - User commenting on / correcting a previous answer → **Workflow 3**
> - Non-finance tasks (coding, storing documents, creating files) → skip all workflows, respond directly

---

### Workflow 1 — Finance Q&A (Knowledge Verification)

> **Applies when:**
> 1. The user is asking a **finance-related question** (stocks, macro, sectors, options, fundamentals, etc.), AND
> 2. The answer **requires verification against the base knowledge** (i.e. it is not a trivial factual question you already know with certainty).

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
- Call `cache_retrieve(queries=[...])` with the formatted query strings from Step 2
- Based on the cached answer, modify the queries to gain missing information
- If the cached answer already has all required information → move to Step 5, else continue
- Call `retrieve(queries=[...])` with the modified query
- The pipeline internally handles: lowercase → parse → entity canonicalization → cache lookup + LightRAG (concurrently)
- If the result contains `error == "format_error"` → reformat that query string per the `message` hint and retry
- Compose your answer from the `combined` field of each result

**Step 5 — Finalize**
- Call `finalize(answer, canonical, hash)` — logs the answer and triggers auto-cache
- Use the `canonical` and `hash` from any result in the `retrieve` response (or `preprocess_query` if you fell back to manual retrieval)
- ALWAYS call `finalize()` even when retrieval returned nothing — this saves the answer
- If the user later says an answer was wrong: call `preprocess_query()` to get canonical + hash, then `cache_invalidate(canonical, hash)`
- This completes the block: user → workflow → answer

**Rules**
- Free to answer, ALWAYS VERIFIED WITH BASE KNOWLEDGE
- If base knowledge returns nothing on a topic, you may fall back to your own knowledge or the internet
- Use `instruction/baseknowledge/RETRIEVE_GUIDE.md` for manual retrieval fallback details
- Reference `CONTROL_PLANE_MCP.md` for how to use skills

---

### Workflow 2 — Stock Buying Recommendation

> **Applies when the user asks:**
> - Which stock to buy / what is the best stock right now
> - Stock recommendation / what should I invest in
> - Any question implying "pick a stock for me" from the broad market
>
> For questions about a **specific ticker** already named by the user (e.g. "should I buy AAPL?"),
> skip to Step 3 and run `yfinance.stock_analysis` on that ticker directly instead of the full scan.

**Step 1 — Announce**
- Call `announce(user_question)` before any skill calls

**Step 2 — Market scan**
- Call `invoke_skill("yfinance.market_scan", {"top_n": 10, "period": "1y"})`
- This scans the top ~50 large-cap S&P 500 tickers in parallel, scores each on 8 metric groups (RSI, MACD, Bollinger, MA cross, Sharpe, drawdown, returns, volume), and returns the top 10 ranked by `health_score` (0–10)

**Step 3 — (Optional) Deep-dive on specific ticker**
- If the user named a ticker, or you want to go deeper on the #1 pick:
  - Call `invoke_skill("yfinance.stock_analysis", {"ticker": "<TICKER>", "period": "1y"})`
  - This returns full metric breakdown for that single stock

**Step 4 — Cross-check with base knowledge**
- Call `retrieve(queries=[...])` with macro context relevant to the recommendation
  - e.g. query GDP/inflation/Fed rate to confirm macro environment supports equities
  - Check for any policy signals that override the technical verdict

**Step 5 — Compose and finalize**
- Build your answer using:
  1. `top_picks` from the scan (rank, ticker, verdict, health_score, summary)
  2. Macro context from retrieve
  3. Any policy signals (e.g. "VIX > 40 → accumulate" or "GDP > 2% → attack mode")
- Call `finalize(answer, canonical, hash)` using the canonical/hash from the retrieve result

**Output format**
Present the recommendation as:
1. **Top pick** — ticker, verdict, score, key signals (RSI, MACD, Sharpe, golden cross)
2. **Runner-ups** — brief table of next 3–5 candidates
3. **Macro context** — whether macro supports the buy (GDP, inflation, Fed rate)
4. **Risk note** — max drawdown, volatility, any bearish signals to watch

**Rules**
- Never recommend a stock with `verdict == "SELL"` or `"STRONG SELL"` from the scan
- Always pair technical score with macro context before a final recommendation
- If macro is contractionary (GDP < 0, Fed hiking, VIX > 30), prefer defensive sectors even for high-scoring tickers

---

### Workflow 3 — User Comment on a Previous Answer

> **Applies when the user's message is commenting on, correcting, or giving feedback about a previous answer**
> (e.g. "that answer was wrong", "good answer", "you missed X", "add that the VIX also...").
> Treat it as a comment — NOT a new question.

**Step 1** — Do NOT call `announce` — this is not a new block.

**Step 2** — Call `log_comment(comment=<user's comment text>, block_index=<block they're referring to>)`.
- If it's unclear which block they mean, default to `-1` (last block).

**Step 3** — Acknowledge the comment briefly to the user.

**Signals that a message is a comment (not a question):**
- Short evaluative phrases: "good", "wrong", "correct", "nice", "that's right", "not quite"
- Explicit feedback: "you missed...", "add to your answer...", "the answer should also mention..."
- Corrections: "actually it's...", "that's not right because..."
- Approval/disapproval with no new question attached

> If the message contains BOTH feedback AND a new question, log the comment first, then proceed with the normal workflow for the question.

---

## References
1. Retrieving base knowledge: `instruction/baseknowledge/RETRIEVE_GUIDE.md`
2. Storing documents: `instruction/baseknowledge/STORING_GUIDE.md`
3. Creating: `CREATING.md`
4. Reviewing pipeline: `instruction/self_improvement`
