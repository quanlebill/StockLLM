from enum import Enum
from typing import TypedDict, Any, List
from langgraph.graph import StateGraph, END


class ResponseStatus(Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class AgentState(TypedDict):
    conversation_key: str
    state_name: str
    input: str
    enhance_query: str

    subgraph_skill: Any   # compiled SubGraphSkillArgParser graph
    subgraph_plan: Any    # compiled SubGraphPlanner graph

    plan: List[dict]            # [{skill_name, description}, ...]
    plan_index: int             # current execution index
    action_results: List[dict]  # accumulated skill results

    response: str
    error: str


class SubGraphSkillParserState(TypedDict):
    conversation_key: str
    state_name: str
    skill_name: str
    skill_queries: str
    skill_response: str
    skill_subgraph_response: dict
    skill_subgraph_error: str
    skill_subgraph_error_status: ResponseStatus | None
    retry_count: int


class SubGraphPlannerState(TypedDict):
    conversation_key: str
    state_name: str
    query: str
    plan: List[dict]  # [{skill_name, description}, ...]
    stop: str
