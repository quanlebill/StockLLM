import json
import re
from agent.graph.agent_state import SubGraphSkillParserState, ResponseStatus
from agent.graph.logger import graph_log, Logger
from agent.skills.skill_registry import SKILL_REGISTRY
from ollama_model import store_prompt, run_by_key, fetch_response

MAX_FIX_RETRIES = 3


def _extract_json(text: str) -> str:
    """Strip markdown code fences if present, otherwise return the text as-is."""
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        return match.group(1).strip()
    return text.strip()


class SubGraphSkillArgParser:
    @staticmethod
    @graph_log(Logger, "skill_usage_subgraph", 1)
    def skill_args_assign(state: SubGraphSkillParserState) -> SubGraphSkillParserState:
        skill = SKILL_REGISTRY.get_skill(state["skill_name"])
        prompt = f"""You are a JSON-only responder. Your entire response must be a single valid JSON object.

ABSOLUTE RULES — violation causes system failure:
1. Your response MUST start with the character {{ — no exceptions.
2. Your response MUST end with the character }} — no exceptions.
3. Do NOT write any word, sentence, or character before the opening {{.
4. Do NOT write any word, sentence, or character after the closing }}.
5. Do NOT use markdown, code fences, or backticks.
6. Every field listed in the format is REQUIRED — omitting any field is an error.
7. No list may be empty — every list must contain at least one item.

Context (extract information from this):
{state["skill_queries"]}

{skill.usage_prompt}

Remember: start immediately with {{ and end with }}. Nothing else."""
        key = store_prompt(prompt)
        run_by_key(key)
        state["skill_response"] = fetch_response(key)
        return state

    @staticmethod
    @graph_log(Logger, "skill_usage_subgraph", 1)
    def skill_args_parser(state: SubGraphSkillParserState) -> SubGraphSkillParserState:
        try:
            cleaned = _extract_json(state["skill_response"]).lower()
            state["skill_response"] = cleaned
            state["skill_subgraph_response"] = json.loads(cleaned)
            state["skill_subgraph_error_status"] = ResponseStatus.SUCCESS
        except json.decoder.JSONDecodeError as e:
            state["skill_subgraph_error"] = str(e)
            state["skill_subgraph_error_status"] = ResponseStatus.ERROR
        return state

    @staticmethod
    @graph_log(Logger, "skill_usage_subgraph", 1)
    def skill_args_fix(state: SubGraphSkillParserState) -> SubGraphSkillParserState:
        state["retry_count"] += 1
        skill = SKILL_REGISTRY.get_skill(state["skill_name"])
        prompt = f"""Your previous response failed JSON parsing. You must output a corrected valid JSON object.

THE ONLY VALID RESPONSE IS A JSON OBJECT:
- Start your response with {{ — this must be the very first character
- End your response with }} — this must be the very last character
- No text before {{, no text after }}, no markdown, no code fences

Parse error from your last attempt:
{state["skill_subgraph_error"]}

Required JSON format (copy this structure exactly, replace placeholder values):
{skill.arg_hint}

Context (extract real values from this):
{state["skill_queries"]}

Output the corrected JSON now. First character must be {{"""
        key = store_prompt(prompt)
        run_by_key(key)
        state["skill_response"] = fetch_response(key)
        return state

    @staticmethod
    def skill_router(state: SubGraphSkillParserState) -> ResponseStatus:
        if state["skill_subgraph_error_status"] == ResponseStatus.SUCCESS:
            return ResponseStatus.SUCCESS
        if state["retry_count"] >= MAX_FIX_RETRIES:
            return ResponseStatus.SUCCESS  # give up — pass empty result through
        return ResponseStatus.ERROR

    @staticmethod
    def get_skill_router_conditional_edge(entry_node: str, exit_node: str, fix_node: str) -> dict:
        return {
            "source": entry_node,
            "path": SubGraphSkillArgParser.skill_router,
            "path_map": {
                ResponseStatus.ERROR: fix_node,
                ResponseStatus.SUCCESS: exit_node,
            },
        }
