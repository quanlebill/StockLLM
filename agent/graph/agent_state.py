from enum import Enum
from typing import Dict, TypedDict, Callable, Any, List
from pydantic import BaseModel
from langgraph.graph import StateGraph,END

class ResponseStatus(Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"

class Conversation(TypedDict):
    conversation_key: str

class AgentState(TypedDict):
    conversation_key: str
    state_name:str
    input: str
    enhance_query: str
    skill_subgraph: StateGraph
    response: str
    error: str

class SkillSubGraphState(TypedDict):
    conversation_key: str
    state_name: str
    skill_name: str
    skill_queries: str
    skill_response: str
    skill_subgraph_response: dict
    skill_subgraph_error: str
    skill_subgraph_error_status: ResponseStatus|None
