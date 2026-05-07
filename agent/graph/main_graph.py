from agent.graph.agent_state import AgentState, SubGraphSkillParserState, SubGraphPlannerState
from agent.graph.logger import graph_log, Logger
from agent.skills.skill_registry import SKILL_REGISTRY
from ollama_model import store_prompt, run_by_key, fetch_response


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
    key = store_prompt(prompt)
    run_by_key(key)
    state["enhance_query"] = fetch_response(key)
    return state


@graph_log(Logger, "main_agent_graph")
def planner(state: AgentState) -> AgentState:
    planner_state = SubGraphPlannerState(
        state_name="SubGraphPlannerState",
        conversation_key=state["conversation_key"],
        query=state['enhance_query'],
        plan=[],
        stop="false",
    )
    result = state["subgraph_plan"].invoke(planner_state)
    state["plan"] = result["plan"]
    state["plan_index"] = 0
    state["action_results"] = []
    return state


@graph_log(Logger, "main_agent_graph")
def execute_step(state: AgentState) -> AgentState:
    step = state["plan"][state["plan_index"]]
    print(f"""
        Executing Step {state["plan_index"]}:
            - Skill Name: {step['skill_name']}
            - Description: {step["description"]}
    """)
    skill_state = SubGraphSkillParserState(
        state_name="SkillSubGraphState",
        conversation_key=state["conversation_key"],
        skill_name=step["skill_name"],
        skill_queries=f"{state['enhance_query']}\n\nCurrent step: {step['description']}",
        skill_response="",
        skill_subgraph_response={},
        skill_subgraph_error="",
        skill_subgraph_error_status=None,
        retry_count=0,
    )
    result_state = state["subgraph_skill"].invoke(skill_state)
    parsed_args = result_state["skill_subgraph_response"]

    results = list(state["action_results"])
    if not parsed_args:
        print(f"[execute_step] arg parsing failed after {result_state['retry_count']} retries, skipping skill call")
        results.append({
            "step_index": state["plan_index"],
            "skill_name": step["skill_name"],
            "description": step["description"],
            "args": {},
            "result": {"error": "arg parsing failed"},
        })
        state["action_results"] = results
        state["plan_index"] += 1
        return state

    skill = SKILL_REGISTRY.get_skill(step["skill_name"])
    skill_result = skill.func(**parsed_args)
    print(skill_result)
    results = list(state["action_results"])
    results.append({
        "step_index": state["plan_index"],
        "skill_name": step["skill_name"],
        "description": step["description"],
        "args": parsed_args,
        "result": skill_result,
    })
    state["action_results"] = results
    state["plan_index"] += 1
    return state


def execute_step_router(state: AgentState) -> str:
    if state["plan_index"] < len(state["plan"]):
        return "continue"
    return "done"


@graph_log(Logger, "main_agent_graph")
def llm_response(state: AgentState) -> AgentState:
    results_text = "\n".join(
        f"Step {e['step_index'] + 1} [{e['skill_name']}]: {e['description']}\nResult: {e['result']}"
        for e in state["action_results"]
    )
    prompt = f"""
    Based on the user's question and the collected information, provide a comprehensive answer.

    User Question:
    {state["input"]}

    Collected Information:
    {results_text}
    """
    key = store_prompt(prompt)
    run_by_key(key)
    state["response"] = fetch_response(key)
    print(f"\nAssistant: {state['response']}")
    return state
