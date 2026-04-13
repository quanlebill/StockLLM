from enum import Enum
from typing import Dict, TypedDict, Callable, Any, List
from langgraph.graph import StateGraph,END
import ollama
import json
import uuid
from datetime import datetime
from agent_state import AgentState, SkillSubGraphState, ResponseStatus
from logger import SkillLog, GraphLog, skill_log, graph_log

from skills.mcp_control_plane import FuncRetrieveArgs_Hint, FuncRetrieveArgs_Usage_Prompt, FuncRetrieveArgs


def _generate_conversation_key():
    key = f"{uuid.uuid4()}_{str(datetime.now().strftime("%Y%m%d_%H%M%S_%f"))}"
    key = key.replace("-", "_")
    return key

class Logging:
    _skill_log = None
    _graph_log = None

Loggers = Logging()
key = _generate_conversation_key()
Loggers._skill_log = SkillLog(conversation_key=key)
Loggers._graph_log = GraphLog(conversation_key=key)

class SkillUsageSubGraph:

    @graph_log(Loggers._graph_log, "skill_usage_subgraph")
    def skill_args_assign(state: SkillSubGraphState) -> SkillSubGraphState:
        prompt = f"""
            Based on the provided Context, fill the format
            RESPONSE in the FORMAT only, nothing else
            
            Context:
            {state["skill_queries"]}
            
            {FuncRetrieveArgs_Usage_Prompt}
        """

        response = ollama.generate(
            model = OLLAMA_MODEl,
            prompt = prompt
        )
        state["skill_response"] = response.response
        return state

    @graph_log(Loggers._graph_log, "skill_usage_subgraph")
    def skill_args_parser(state: SkillSubGraphState) -> SkillSubGraphState:
        try:
            state["skill_subgraph_response"] = json.loads(state['skill_response'])
            state["skill_subgraph_error_status"] = ResponseStatus.SUCCESS
        except json.decoder.JSONDecodeError as e:
            state["skill_subgraph_error"] = str(e)
            state["skill_subgraph_error_status"] = ResponseStatus.ERROR

        return state

    @graph_log(Loggers._graph_log, "skill_usage_subgraph")
    def skill_args_fix(state:SkillSubGraphState) -> SkillSubGraphState:
        prompt = f"""
            Fix the format based on Right Format
            RESPONSE in the FORMAT only, nothing else
            
            Previous Output:
            {state["skill_response"]}
            
            Error:
            {state["skill_subgraph_error"]}
            
            Right Format:
            {FuncRetrieveArgs_Hint}
        """
        response = ollama.generate(
            model=OLLAMA_MODEl,
            prompt=prompt,
        )
        state["skill_response"] = response.response
        return state


    def skill_router(state:SkillSubGraphState) -> ResponseStatus:
        return state["skill_subgraph_error_status"]

    def get_skill_router_conditional_edge(entry_node:str, exist_node:str, fix_node:str) -> dict:
        return {
            "source": entry_node,
            "path": SkillUsageSubGraph.skill_router,
            "path_map": {
                ResponseStatus.ERROR: fix_node,
                ResponseStatus.SUCCESS: exist_node,
            }

        }

OLLAMA_MODEl = "llama3"

@graph_log(Loggers._graph_log, "main_agent_graph")
def user_query(state: AgentState) -> AgentState:
    user_input = input("User: ")
    state['input'] = user_input
    return state

@graph_log(Loggers._graph_log, "main_agent_graph")
def enhance_query(state: AgentState) -> AgentState:
    prompt = f"""
    Based on provided User Query, 
    Provide 1-5 questions in proper format
    Using Only This Question Type: WHAT, WHO, WHERE, WHEN, HOW
    RESPONSE ONLY with your enhance questions
    
    User Query:
    {state["input"]}
    
    Example:
    ```example
    User Query: What affect GDP
    Enhance: 
    - What factor affect GDP
    - How does these factor affect GDP
    ```
    """
    response = ollama.generate(
        model=OLLAMA_MODEl,
        prompt=prompt,
    )
    state["enhance_query"] = response.response
    return state


@graph_log(Loggers._graph_log, "main_agent_graph")
def invoke_skill_graph(state:AgentState) -> AgentState:
    skill_state = SkillSubGraphState(
        state_name="SkillSubGraphState",
        conversation_key=state["conversation_key"],
        skill_queries=state['enhance_query'],
        skill_response="",
        skill_subgraph_response={},
        skill_subgraph_error="",
        skill_subgraph_error_status=None,
    )
    skill_state = state["skill_subgraph"].invoke(skill_state)
    state["response"] = str(skill_state["skill_subgraph_response"])
    return state

@graph_log(Loggers._graph_log, "main_agent_graph")
def llm_response(state:AgentState) -> AgentState:
    print(state['response'])
    return state

if __name__ == "__main__":

    # Skill Sub Graph
    skill_sub_graph = StateGraph(SkillSubGraphState)
    skill_sub_graph.add_node("skill_args_assign", SkillUsageSubGraph.skill_args_assign)
    skill_sub_graph.add_node("skill_args_parser", SkillUsageSubGraph.skill_args_parser)
    skill_sub_graph.add_node("skill_args_fix", SkillUsageSubGraph.skill_args_fix)
    skill_sub_graph.set_entry_point("skill_args_assign")
    skill_sub_graph.add_edge("skill_args_assign", "skill_args_parser")
    skill_sub_graph.add_edge("skill_args_fix", "skill_args_parser")
    skill_sub_graph.add_conditional_edges(**SkillUsageSubGraph.get_skill_router_conditional_edge("skill_args_parser", END, "skill_args_fix"))

    # Main Graph
    graph = StateGraph(AgentState)
    graph.add_node("user_query", user_query)
    graph.add_node("invoke_skill_graph", invoke_skill_graph)
    graph.add_node("llm_response", llm_response)
    graph.add_node("enhance_query", enhance_query)
    graph.set_entry_point("user_query")
    graph.add_edge("user_query", "enhance_query")
    graph.add_edge("enhance_query", "invoke_skill_graph")
    graph.add_edge("invoke_skill_graph", "llm_response")
    graph.add_edge("llm_response", END)

    agent_state = AgentState(
        state_name = "AgentState",
        input = "",
        skill_subgraph = skill_sub_graph.compile(),
        enhance_query="",
        response = "",
        error = "",
        conversation_key=key,
    )
    app = graph.compile()
    app.invoke(agent_state)


