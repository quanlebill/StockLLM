import os
import sys
os.environ.setdefault("STOCKLLM_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "python"))

import uuid
from datetime import datetime
from agent.graph.agent_state import AgentState, SubGraphSkillParserState
from agent.graph.subgraph_skill_parser import SubGraphSkillArgParser
from agent.graph.subgraph_planner import SubGraphPlanner
from langgraph.graph import StateGraph, END
from agent.graph.logger import Logger
from agent.graph.main_graph import (
    user_query,
    enhance_query,
    planner,
    execute_step,
    execute_step_router,
    llm_response,
)



def _generate_conversation_key():
    key = f"{uuid.uuid4()}_{str(datetime.now().strftime('%Y%m%d_%H%M%S_%f'))}"
    return key.replace("-", "_")


Logger.set_conversation_key(_generate_conversation_key())

if __name__ == "__main__":

    skill_sub_graph = StateGraph(SubGraphSkillParserState)
    skill_sub_graph.add_node("skill_args_assign", SubGraphSkillArgParser.skill_args_assign)
    skill_sub_graph.add_node("skill_args_parser", SubGraphSkillArgParser.skill_args_parser)
    skill_sub_graph.add_node("skill_args_fix", SubGraphSkillArgParser.skill_args_fix)
    skill_sub_graph.set_entry_point("skill_args_assign")
    skill_sub_graph.add_edge("skill_args_assign", "skill_args_parser")
    skill_sub_graph.add_edge("skill_args_fix", "skill_args_parser")
    skill_sub_graph.add_conditional_edges(
        **SubGraphSkillArgParser.get_skill_router_conditional_edge("skill_args_parser", END, "skill_args_fix")
    )

    plan_sub_graph = SubGraphPlanner.build_graph()

    graph = StateGraph(AgentState)
    graph.add_node("user_query", user_query)
    graph.add_node("enhance_query", enhance_query)
    graph.add_node("planner", planner)
    graph.add_node("execute_step", execute_step)
    graph.add_node("llm_response", llm_response)

    graph.set_entry_point("user_query")
    graph.add_edge("user_query", "enhance_query")
    graph.add_edge("enhance_query", "planner")
    graph.add_edge("planner", "execute_step")
    graph.add_conditional_edges(
        "execute_step",
        execute_step_router,
        {"continue": "execute_step", "done": "llm_response"},
    )
    graph.add_edge("llm_response", END)

    agent_state = AgentState(
        state_name="AgentState",
        conversation_key=Logger.get_conversation_key(),
        input="",
        enhance_query="",
        subgraph_skill=skill_sub_graph.compile(),
        subgraph_plan=plan_sub_graph.compile(),
        plan=[],
        plan_index=0,
        action_results=[],
        response="",
        error="",
    )
    app = graph.compile()
    while True:
        app.invoke(agent_state)
