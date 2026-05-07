import json
import re
from agent.graph.agent_state import SubGraphPlannerState
from agent.graph.logger import graph_log, Logger
from agent.skills.skill_registry import get_skill_list
from langgraph.graph import StateGraph, END
from ollama_model import store_prompt, run_by_key, fetch_response


def _parse_step_json(response: str) -> dict | None:
    """Extract a {skill_name, description} JSON object from a raw LLM response."""
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        match = re.search(r'\{.*?\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


class SubGraphPlanner:

    @staticmethod
    @graph_log(Logger, "subgraph_planner", 1)
    def initiate_plan(state: SubGraphPlannerState) -> SubGraphPlannerState:
        prompt = f"""
            Task:
            - Based on the query and available tools, decide the FIRST step of a plan
            - Output ONLY a JSON object with exactly two keys: "skill_name" and "description"
            - "skill_name" must be one of the available tool names listed below
            - "description" is a short sentence describing what to do in this step

            Query:
            {state["query"]}

            Available Tools:
            {get_skill_list()}

            Example output:
            {{"skill_name": "retrieve", "description": "Retrieve macro data on GDP growth and inflation"}}
        """
        key = store_prompt(prompt)
        run_by_key(key)
        response = fetch_response(key)
        step = _parse_step_json(response)
        if step is None:
            step = {"skill_name": "retrieve", "description": response.strip()}
        state["plan"].append(step)
        return state

    @staticmethod
    @graph_log(Logger, "subgraph_planner", 1)
    def adding_plan(state: SubGraphPlannerState) -> SubGraphPlannerState:
        steps_text = "\n".join(
            f"Step {i + 1}: [{s['skill_name']}] {s['description']}"
            for i, s in enumerate(state["plan"])
        )
        prompt = f"""
            Task:
            - Given the past steps and query, decide if another step is needed
            - If more steps are needed: output ONLY a JSON object with "skill_name" and "description"
            - If the plan is complete: output only the word NO

            Query:
            {state["query"]}

            Past Steps:
            {steps_text}

            Available Tools:
            {get_skill_list()}

            Example output when another step is needed:
            {{"skill_name": "retrieve", "description": "Retrieve sector rotation signals"}}
        """
        key = store_prompt(prompt)
        run_by_key(key)
        response = fetch_response(key).strip()

        if "NO" in response.upper():
            state["stop"] = "true"
        else:
            step = _parse_step_json(response)
            if step:
                state["plan"].append(step)
            else:
                state["stop"] = "true"

        return state

    @staticmethod
    def plan_router(state: SubGraphPlannerState) -> str:
        return state["stop"]

    @staticmethod
    def get_plan_router_conditional_edges(entry_node: str, exit_node: str, loop_node: str) -> dict:
        return {
            "source": entry_node,
            "path": SubGraphPlanner.plan_router,
            "path_map": {
                "true": exit_node,
                "false": loop_node,
            },
        }

    @staticmethod
    def build_graph() -> StateGraph:
        graph = StateGraph(SubGraphPlannerState)
        graph.add_node("initiate_plan", SubGraphPlanner.initiate_plan)
        graph.add_node("adding_plan", SubGraphPlanner.adding_plan)
        graph.set_entry_point("initiate_plan")
        graph.add_edge("initiate_plan", "adding_plan")
        graph.add_conditional_edges(
            **SubGraphPlanner.get_plan_router_conditional_edges("adding_plan", END, "adding_plan")
        )
        return graph
