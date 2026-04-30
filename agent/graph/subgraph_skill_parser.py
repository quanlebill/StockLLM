import json
import uuid
from datetime import datetime
from agent.graph.agent_state import SkillSubGraphState, ResponseStatus
from agent.graph.logger import graph_log, Logger
from agent.skills.skill_registry import SKILL_REGISTRY
from ollama_model import store_prompt, run_by_key, fetch_response


def _generate_conversation_key():
    key = f"{uuid.uuid4()}_{str(datetime.now().strftime("%Y%m%d_%H%M%S_%f"))}"
    key = key.replace("-", "_")
    return key


key = _generate_conversation_key()


class SubGraphSkillArgParser:
    @graph_log(Logger, "skill_usage_subgraph")
    def skill_select(state: SkillSubGraphState) -> SkillSubGraphState:
        prompt = f"""
            Given the Queries, choose a list of skill that 

        """

    @graph_log(Logger, "skill_usage_subgraph")
    def skill_args_assign(state: SkillSubGraphState) -> SkillSubGraphState:
        prompt = f"""
            Based on the provided Context, fill the format
            RESPONSE in the FORMAT only, nothing else

            Context:
            {state["skill_queries"]}

            {SKILL_REGISTRY.get_skill(state["skill_name"]).usage_prompt}
        """

        key = store_prompt(prompt)
        run_by_key(key)
        state["skill_response"] = fetch_response(key)
        return state

    @graph_log(Logger, "skill_usage_subgraph")
    def skill_args_parser(state: SkillSubGraphState) -> SkillSubGraphState:
        try:
            state["skill_subgraph_response"] = json.loads(state['skill_response'])
            state["skill_subgraph_error_status"] = ResponseStatus.SUCCESS
        except json.decoder.JSONDecodeError as e:
            state["skill_subgraph_error"] = str(e)
            state["skill_subgraph_error_status"] = ResponseStatus.ERROR

        return state

    @graph_log(Logger, "skill_usage_subgraph")
    def skill_args_fix(state: SkillSubGraphState) -> SkillSubGraphState:
        prompt = f"""
            Fix the format based on Right Format
            RESPONSE in the FORMAT only, nothing else

            Previous Output:
            {state["skill_response"]}

            Error:
            {state["skill_subgraph_error"]}

            Right Format:
            {SKILL_REGISTRY.get_skill(state["skill_name"]).arg_hint}
        """
        key = store_prompt(prompt)
        run_by_key(key)
        state["skill_response"] = fetch_response(key)
        return state

    def skill_router(state: SkillSubGraphState) -> ResponseStatus:
        return state["skill_subgraph_error_status"]

    def get_skill_router_conditional_edge(entry_node: str, exist_node: str, fix_node: str) -> dict:
        return {
            "source": entry_node,
            "path": SubGraphSkillArgParser.skill_router,
            "path_map": {
                ResponseStatus.ERROR: fix_node,
                ResponseStatus.SUCCESS: exist_node,
            }

        }




