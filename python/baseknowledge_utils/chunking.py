import os
import tkinter as tk
from tkinter import filedialog
import PyPDF2
from fastapi import FastAPI, HTTPException
from python.basestruct.base import SplitRequest

ROOT = os.environ["STOCKLLM_ROOT"]
DOCS_BASE = os.path.join(ROOT, "baseknowledge", "docs")

app = FastAPI()


@app.get("/topics")
def get_topics():
    """Return list of existing topic folders under baseknowledge/docs/."""
    os.makedirs(DOCS_BASE, exist_ok=True)
    topics = [
        d for d in os.listdir(DOCS_BASE)
        if os.path.isdir(os.path.join(DOCS_BASE, d))
    ]
    return {"topics": topics}


@app.get("/select-file")
def select_file():
    """Open a tkinter file picker dialog and return the selected PDF filepath."""
    root = tk.Tk()
    root.attributes("-topmost", True)
    root.withdraw()
    filepath = filedialog.askopenfilename(
        title="Select PDF file",
        filetypes=[("PDF files", "*.pdf")]
    )
    root.destroy()

    if not filepath:
        raise HTTPException(status_code=400, detail="No file selected.")

    return {"filepath": filepath}


@app.post("/split")
def split_pdf(request: SplitRequest):
    if not os.path.exists(request.filepath):
        raise HTTPException(status_code=400, detail=f"File not found: {request.filepath}")
    if not request.filepath.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF.")

    doc_name = os.path.splitext(os.path.basename(request.filepath))[0]
    output_dir = os.path.join(DOCS_BASE, request.topic, doc_name)
    os.makedirs(output_dir, exist_ok=True)

    with open(request.filepath, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        total_pages = len(reader.pages)
        for i, page in enumerate(reader.pages):
            writer = PyPDF2.PdfWriter()
            writer.add_page(page)
            with open(os.path.join(output_dir, f"{i}.pdf"), "wb") as out:
                writer.write(out)

    return {
        "output_dir": output_dir,
        "topic": request.topic,
        "doc_name": doc_name,
        "total_pages": total_pages,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
