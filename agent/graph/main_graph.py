import ollama

from agent.graph.agent_state import AgentState, SkillSubGraphState
from agent.graph.logger import graph_log, Logger

OLLAMA_MODEl = "llama3"

@graph_log(Logger, "main_agent_graph")
def user_query(state: AgentState) -> AgentState:
    user_input = input("User: ")
    state['input'] = user_input
    return state

@graph_log(Logger, "main_agent_graph")
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


@graph_log(Logger, "main_agent_graph")
def skill_arg_parser(state:AgentState) -> AgentState:
    skill_state = SkillSubGraphState(
        state_name="SkillSubGraphState",
        conversation_key=state["conversation_key"],
        skill_queries=state['enhance_query'],
        skill_name="retrieve",
        skill_response="",
        skill_subgraph_response={},
        skill_subgraph_error="",
        skill_subgraph_error_status=None,
    )
    skill_state = state["skill_subgraph"].invoke(skill_state)
    state["response"] = str(skill_state["skill_subgraph_response"])
    return state

@graph_log(Logger, "main_agent_graph")
def llm_response(state:AgentState) -> AgentState:
    print(state['response'])
    return state
