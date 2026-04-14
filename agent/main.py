import uuid
from datetime import datetime
from agent.graph.agent_state import AgentState, SkillSubGraphState
from agent.graph.subgraph_skill_parser import SubGraphSkillArgParser
from langgraph.graph import StateGraph, END
from agent.graph.logger import Logger
from agent.graph.main_graph import (
    llm_response,
    user_query,
    enhance_query,
    skill_arg_parser
)



def _generate_conversation_key():
    key = f"{uuid.uuid4()}_{str(datetime.now().strftime("%Y%m%d_%H%M%S_%f"))}"
    key = key.replace("-", "_")
    return key

Logger.set_conversation_key(_generate_conversation_key())

if __name__ == "__main__":

    # Skill Sub Graph
    skill_sub_graph = StateGraph(SkillSubGraphState)
    skill_sub_graph.add_node("skill_args_assign", SubGraphSkillArgParser.skill_args_assign)
    skill_sub_graph.add_node("skill_args_parser", SubGraphSkillArgParser.skill_args_parser)
    skill_sub_graph.add_node("skill_args_fix", SubGraphSkillArgParser.skill_args_fix)
    skill_sub_graph.set_entry_point("skill_args_assign")
    skill_sub_graph.add_edge("skill_args_assign", "skill_args_parser")
    skill_sub_graph.add_edge("skill_args_fix", "skill_args_parser")
    skill_sub_graph.add_conditional_edges(**SubGraphSkillArgParser.get_skill_router_conditional_edge("skill_args_parser", END, "skill_args_fix"))

    # Main Graph
    graph = StateGraph(AgentState)
    graph.add_node("user_query", user_query)
    graph.add_node("skill_arg_parser", skill_arg_parser)
    graph.add_node("llm_response", llm_response)
    graph.add_node("enhance_query", enhance_query)
    graph.set_entry_point("user_query")
    graph.add_edge("user_query", "enhance_query")
    graph.add_edge("enhance_query", "skill_arg_parser")
    graph.add_edge("skill_arg_parser", "llm_response")
    graph.add_edge("llm_response", END)



    agent_state = AgentState(
        state_name = "AgentState",
        input = "",
        skill_subgraph = skill_sub_graph.compile(),
        enhance_query="",
        response = "",
        error = "",
        conversation_key=Logger.get_conversation_key(),
    )
    app = graph.compile()
    app.invoke(agent_state)