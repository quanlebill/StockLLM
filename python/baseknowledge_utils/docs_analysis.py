import os
import PyPDF2
import ollama
from fastapi import FastAPI, HTTPException
from python.basestruct.base_model import OLLAMA_MODEL
from python.basestruct.agent_prompt import OllamaPrompt
from python.basestruct.base import SummaryEntry


def _summarize(text: str, page_index: int) -> str:
    if not text.strip():
        return "(empty page)"
    prompt = OllamaPrompt.get__docs_analysis__summraize_prompt(str(page_index), text)
    try:
        resp = ollama.generate(model=OLLAMA_MODEL, prompt=prompt)
        return resp["response"].strip()
    except Exception as e:
        return f"(summary failed: {e})"

ROOT      = os.environ["STOCKLLM_ROOT"]
DOCS_BASE = os.path.join(ROOT, "baseknowledge", "docs")


def _latest_doc_dir() -> str:
    """Return the most recently modified leaf folder under baseknowledge/docs/<topic>/<doc>."""
    candidates = []
    for topic in os.listdir(DOCS_BASE):
        topic_path = os.path.join(DOCS_BASE, topic)
        if not os.path.isdir(topic_path):
            continue
        for doc in os.listdir(topic_path):
            doc_path = os.path.join(topic_path, doc)
            if os.path.isdir(doc_path):
                candidates.append(doc_path)
    if not candidates:
        raise ValueError(f"No doc folders found under {DOCS_BASE} — run split_pdf first.")
    return max(candidates, key=os.path.getmtime)


DOC_PATH = _latest_doc_dir()

if not DOC_PATH.startswith(os.path.abspath(DOCS_BASE)):
    raise ValueError(f"--doc must be under baseknowledge/docs. Got: {DOC_PATH}")

CURRENT_PAGE_INDEX = 0
SUMMARY_FILE = os.path.join(DOC_PATH, "docs_summary_file.txt")

# Create summary file if not exists
open(SUMMARY_FILE, "a").close()

app = FastAPI()


def _total_pages() -> int:
    return len([f for f in os.listdir(DOC_PATH) if f.endswith(".pdf")])


@app.get("/page")
def get_current_page():
    """Summarize the current page via Ollama3, auto-save to summary file, and return summary."""
    global CURRENT_PAGE_INDEX
    page_file = os.path.join(DOC_PATH, f"{CURRENT_PAGE_INDEX}.pdf")
    if not os.path.exists(page_file):
        raise HTTPException(status_code=404, detail=f"Page {CURRENT_PAGE_INDEX} not found.")

    with open(page_file, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        text = reader.pages[0].extract_text() or ""

    summary = _summarize(text, CURRENT_PAGE_INDEX)

    with open(SUMMARY_FILE, "a", encoding="utf-8") as f:
        f.write(f"- page_index: {CURRENT_PAGE_INDEX}\n{summary}\n\n")

    total = _total_pages()
    result = {
        "page_index": CURRENT_PAGE_INDEX,
        "total_pages": total,
        "is_last": CURRENT_PAGE_INDEX >= total - 1,
        "summary": summary,
    }
    CURRENT_PAGE_INDEX += 1
    return result

@app.post("/summary")
def save_summary(entry: SummaryEntry):
    """Append a page summary to docs_summary_file.txt."""
    with open(SUMMARY_FILE, "a", encoding="utf-8") as f:
        f.write(f"- page_index: {entry.index}\n{entry.summary}\n\n")
    return {"status": "saved", "page_index": entry.index}


@app.get("/status")
def get_status():
    return {
        "current_page_index": CURRENT_PAGE_INDEX,
        "total_pages": _total_pages(),
        "summary_file": SUMMARY_FILE,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
