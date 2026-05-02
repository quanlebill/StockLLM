import json
import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

from dotenv import dotenv_values, set_key
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

ROOT = os.environ["STOCKLLM_ROOT"]

from cache_query import cache_store as _cache_store, cache_lookup as _cache_lookup
from skill_registry import invoke_skill, REGISTRY, SKILLS_BY_CATEGORY
import self_improvement as _kg_pipeline
import retrieval_pipeline as _retrieval_pipeline

from basestruct.base import (
    SkillRequest, SkillResult,
    InvokeResponse, LogAnswerRequest, LogCommentRequest, ConversationStartRequest, AppendWorkflowRequest, RateRequest, InvokeRequest, ConversationGroup,
    MCPStatus, LoadLastConversationResponse, RegistryDebug, ListSkillResponse, DefaultPayload
)

@asynccontextmanager
async def _lifespan(app: FastAPI):
    _kg_pipeline.startup()
    _retrieval_pipeline.prewarm_ollama()
    yield


app = FastAPI(title="StockLLM Control Plane", version="2.0.0", lifespan=_lifespan)

app.include_router(_kg_pipeline.router,        prefix="")
app.include_router(_retrieval_pipeline.router, prefix="")

## Cache
_cache_buffer: dict[str, dict] = {}

def _buffer_reset(key: str) -> None:
    _cache_buffer[key] = {
        "page_indexes": [],
        "topic":        "",
        "book_name":    "",
    }


def _buffer_collect(key: str, skill_name: str, arguments: dict, output: Any) -> None:
    """Extract caching data from successful skill outputs into the buffer."""
    pass


def _auto_cache(key: str, answer: str, canonical: str = "", query_hash: str = "") -> None:
    """
    Fire a best-effort cache_store to the cache service.
    Reads user_question from the conversation file's last block.
    Skips silently if canonical or query_hash are missing (preprocess_query not called).
    Never raises — cache failure must not block the main workflow.
    """
    buf = _cache_buffer.pop(key, {})
    if not answer or not canonical or not query_hash:
        return
    try:
        if _cache_lookup(canonical, query_hash).get("hit") == "answer":
            return
    except Exception:
        pass
    conv = _load_conversation(key)
    if not conv or not conv.get("conversation_block"):
        return
    user_question = conv["conversation_block"][-1].get("user", "")
    if not user_question:
        return
    try:
        _cache_store(
            user_question=user_question,
            canonical=canonical,
            query_hash=query_hash,
            answer=answer,
            topic=buf.get("topic", ""),
            book_name=buf.get("book_name", ""),
            page_indexes=buf.get("page_indexes", []),
        )
    except Exception:
        pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LOG_AWAITING_DIR = os.path.join(ROOT, "logs", "conversation", "awaiting")
LOG_SUCCESS_DIR = os.path.join(ROOT, "logs", "conversation", "success")
for _d in (LOG_AWAITING_DIR, LOG_SUCCESS_DIR):
    os.makedirs(_d, exist_ok=True)


## ENV UTILS
ENV_PATH = os.path.join(ROOT, ".env")

def _read_env_key() -> str:
    vals = dotenv_values(ENV_PATH)
    return vals.get("CONVERSATION_KEY", "") or ""


def _write_env_key(key: str) -> None:
    set_key(ENV_PATH, "CONVERSATION_KEY", key)


## CONVERSATION UTILS
def _conv_path(key: str, base_dir: str = None) -> str:
    d = base_dir or LOG_AWAITING_DIR
    return os.path.join(d, f"{key}.json")


def _load_conversation(key: str) -> Optional[dict]:
    """Load conversation JSON from awaiting dir. Returns None if not found."""
    path = _conv_path(key)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_conversation(data: dict) -> None:
    key = data["conversation_key"]
    with open(_conv_path(key), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _create_conversation_block(user_question: str) -> dict:
    return {"user": user_question, "workflow": "", "answer": "", "comment": ""}


def _append_workflow(key: str, text: str) -> None:
    conv = _load_conversation(key)
    if conv is None:
        return
    conv["conversation_block"][-1]["workflow"] += text + "\n"
    _save_conversation(conv)

def _skill_start_block(skill_name: str, arguments: dict) -> str:
    arg_lines = "\n".join(f"- {k}: {v}" for k, v in arguments.items())
    return f"---SKILL START---\nSkill Name: {skill_name}\nArguments:\n{arg_lines}"


# Skill Utils
def _run_skill(skill_request: SkillRequest) -> tuple[Any, Optional[str]]:
    skill_name = skill_request.skill_name
    arguments  = skill_request.arguments
    start_block = _skill_start_block(skill_name, arguments)

    output: Any = None
    error: Optional[str] = None

    try:
        output = invoke_skill(skill_name, arguments)
        _append_workflow(skill_request.conversation_key, f"{start_block}\nOutput: SUCCESS\n---SKILL END---")
        _buffer_collect(skill_request.conversation_key, skill_name, arguments, output)

    except Exception as exc:
        error = str(exc)
        _append_workflow(skill_request.conversation_key, f"{start_block}\nOutput: FAILED\nError: {error}\n---SKILL END---")

    return output, error


"""
Fast API route
"""

@app.post("/conversation/start", response_model=MCPStatus)
def conversation_start(request: ConversationStartRequest) -> MCPStatus:
    key = request.conversation_key
    conv = _load_conversation(key)

    if conv is None:
        # Check success dir and move back to awaiting if found
        archive_path = _conv_path(key, LOG_SUCCESS_DIR)
        if os.path.exists(archive_path):
            shutil.move(archive_path, _conv_path(key))
            with open(_conv_path(key), "r", encoding="utf-8") as f:
                conv = json.load(f)

    if conv is None:
        conv = ConversationGroup(
            conversation_key = key,
            conversation_block = [_create_conversation_block(request.user_question)],
            conversation_date = datetime.now().isoformat()
        ).model_dump()
    else:
        conv["conversation_block"].append(_create_conversation_block(request.user_question))
    _save_conversation(conv)
    _write_env_key(key)
    _buffer_reset(key)
    return MCPStatus(
        status = "ok",
        payload = DefaultPayload(details = "conversation successfully started")
    )


@app.post("/conversation/log-answer", response_model=MCPStatus)
def log_answer(request: LogAnswerRequest) -> MCPStatus:
    """
    Set the answer field on the last block of the conversation and trigger auto-cache.
    """
    conv = _load_conversation(request.conversation_key)
    if conv is None:
        return MCPStatus(
            status = "failed",
            payload = DefaultPayload(details = "No conversation found"),
            error = HTTPException(status_code=404, detail=f"Conversation '{request.conversation_key}' not found.")
        )
    conv["conversation_block"][-1]["answer"] = request.answer
    _save_conversation(conv)
    _auto_cache(request.conversation_key, request.answer, request.canonical, request.query_hash)
    return MCPStatus(
        status = "ok",
        payload = DefaultPayload(details = "log answer successfully set")
    )


@app.post("/conversation/append-workflow", response_model=MCPStatus)
def append_workflow(request: AppendWorkflowRequest) -> MCPStatus:
    """
    Append a step entry to the workflow log of the current conversation block.
    """
    _append_workflow(request.conversation_key, request.workflow)

    return MCPStatus(
        status = "ok",
        payload = DefaultPayload(details = "append workflow successfully set")
    )


@app.post("/conversation/log-comment", response_model=MCPStatus)
def log_comment(request: LogCommentRequest) -> MCPStatus:
    key = request.conversation_key
    conv = _load_conversation(key)
    conv_dir = LOG_AWAITING_DIR

    if conv is None:
        path = _conv_path(key, LOG_SUCCESS_DIR)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                conv = json.load(f)
            conv_dir = LOG_SUCCESS_DIR

    if conv is None:
        return MCPStatus(
            status = "failed",
            payload = DefaultPayload(details = "No conversation found"),
            error = HTTPException(status_code=404, detail=f"Conversation '{request.conversation_key}' not found.")
        )

    blocks = conv["conversation_block"]
    idx = request.block_index if request.block_index >= 0 else len(blocks) - 1

    if idx >= len(blocks):
        return MCPStatus(
            status="failed",
            payload=DefaultPayload(details="Block index out of range"),
            error=HTTPException(status_code=400, detail=f"Block index {idx} out of range.")
        )
    blocks[idx]["comment"] = request.comment
    path = _conv_path(key, conv_dir)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(conv, f, ensure_ascii=False, indent=2)

    return MCPStatus(
        status = "ok",
        payload = DefaultPayload(details = "log comment successfully set")
    )


@app.get("/conversation/load-last", response_model=MCPStatus)
def load_last_conversation(maximum_conv = 4) -> MCPStatus:
    key = _read_env_key()
    if not key:
        return MCPStatus(
            status = "ok",
            payload =  LoadLastConversationResponse(result = None, conversation_key = None)
        )

    conv = _load_conversation(key)
    if conv is None:
        # Check success dir
        path = _conv_path(key, LOG_SUCCESS_DIR)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                conv = json.load(f)

    if conv is None:
        # Key exists in .env but no file found — create a fresh conversation
        conv = ConversationGroup(
            conversation_key = key,
            conversation_block = [],
            conversation_date = datetime.now().isoformat()
        ).model_dump()
        _save_conversation(conv)
        return MCPStatus(
            status = "ok",
            payload = LoadLastConversationResponse(result = None, conversation_key = key)
        )

    lines = []
    conv_start = len(conv["conversation_block"]) - maximum_conv
    if conv_start < 0:
        conv_start = 0

    for i, block in enumerate(conv["conversation_block"][conv_start:], 1):
        lines.append(f"{i}. user: {block.get('user', '')}")
        lines.append(f"{i}. answer: {block.get('answer', '')}")

    return MCPStatus(
        status = "ok",
        payload = LoadLastConversationResponse(result="\n".join(lines), conversation_key = key)
    )


@app.post("/invoke", response_model=MCPStatus)
def invoke(request: InvokeRequest) -> MCPStatus:
    results: list[SkillResult] = []

    for skill_req in request.skills:
        output, error = _run_skill(
            SkillRequest(
                skill_name=skill_req.skill_name,
                arguments=skill_req.arguments,
                conversation_key=request.conversation_key,
            )
        )
        results.append(SkillResult(skill_name=skill_req.skill_name, output=output, error=error))

    return MCPStatus(
        status = "neutral, may contain error",
        payload = InvokeResponse(conversation_key=request.conversation_key, skills=results)
    )


@app.get("/review/list", response_model=MCPStatus)
def review_list() -> MCPStatus:
    files = [
        f[:-5] for f in os.listdir(LOG_AWAITING_DIR)
        if f.endswith(".json")
    ]
    return MCPStatus(
        status = "ok",
        payload = {
            "awaiting":files,
        }
    )


@app.get("/review/content/{key}", response_model=MCPStatus)
def review_content(key: str) -> MCPStatus:
    path = _conv_path(key)
    if not os.path.exists(path):
        return MCPStatus(
            status = "failed",
            payload = DefaultPayload(details="Conversation not found"),
            error = HTTPException(status_code=404, detail=f"Conversation '{key}' not found in awaiting.")
        )
    with open(path, "r", encoding="utf-8") as f:
        return MCPStatus(
            status = "ok",
            payload=json.load(f)
        )


@app.post("/review/rate", response_model=MCPStatus)
def review_rate(request: RateRequest) -> MCPStatus:
    if request.rating != "success":
        return MCPStatus(
            status = "failed",
            payload = DefaultPayload(details = "wrong rating"),
            error = HTTPException(status_code=400, detail="rating must be 'success'")
        )
    src = _conv_path(request.conversation_key)
    if not os.path.exists(src):
        return MCPStatus(
            status = "failed",
            payload = DefaultPayload(details = "Conversation not found"),
            error = HTTPException(status_code=404, detail=f"Conversation '{request.key}' not found.")
        )
    shutil.move(src, _conv_path(request.conversation_key, LOG_SUCCESS_DIR))
    return MCPStatus(
        status = "ok",
        payload=DefaultPayload(details="Conversation successfully rated and moved to success"),
    )


@app.get("/debug-registry", response_model=MCPStatus)
def debug_registry() -> MCPStatus:
    return MCPStatus(
        status = "ok",
        payload = RegistryDebug(count = len(REGISTRY), keys = sorted(REGISTRY.keys()))
    )


@app.get("/skills", response_model=MCPStatus)
def list_skills(category: str = None) -> MCPStatus:
    if not category:
        return MCPStatus(
            status = "ok",
            payload = ListSkillResponse(skills=[], categories=None)
        )
    skills = sorted(s for s in SKILLS_BY_CATEGORY.get(category, []) if s in REGISTRY)
    return MCPStatus(
        status = "ok",
        payload = ListSkillResponse(skills=skills, categories=category)
    )



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("control_plane:app", host="0.0.0.0", port=8000)
