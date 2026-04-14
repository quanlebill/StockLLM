from functools import wraps
from pathlib import Path
import os
from datetime import datetime
from agent.graph.agent_state import AgentState, SkillSubGraphState
_SKILL_LOG_FOLDER = Path(os.path.dirname(__file__)).parent / "logs" / "skill"
_GRAPH_LOG_FOLDER = Path(os.path.dirname(__file__)).parent / "logs" / "graph"
_CONVERSATION_LOG_FOLDER = Path(os.path.dirname(__file__)).parent / "logs" / "conversation"
def _init_logs_folder():
    if not os.path.exists(_SKILL_LOG_FOLDER):
        os.mkdir(_SKILL_LOG_FOLDER)
    if not os.path.exists(_GRAPH_LOG_FOLDER):
        os.mkdir(_GRAPH_LOG_FOLDER)
    if not os.path.exists(_CONVERSATION_LOG_FOLDER):
        os.mkdir(_CONVERSATION_LOG_FOLDER)
_init_logs_folder()


class Logging:
    __slots__ = ["_conversation_key", "_skill_logger", "_graph_logger"]
    def __init__(self):
        self._conversation_key = ""
        self._skill_logger = None
        self._graph_logger = None

    def set_conversation_key(self, conversation_key:str):
        self._conversation_key = conversation_key
        self._skill_logger = SkillLog(conversation_key=conversation_key)
        self._graph_logger = GraphLog(conversation_key=conversation_key)

    def get_conversation_key(self):
        return self._conversation_key
    def get_skill_logger(self):
        return self._skill_logger

    def get_graph_logger(self):
        return self._graph_logger

Logger = Logging()

class SkillLog:
    def __init__(self, conversation_key:str):
        self._conversation_key = conversation_key
        init_format =f"""
            <KEY>{self._conversation_key}</KEY>
            <CREATED_DATETIME>{datetime.now()}</CREATED_DATETIME>
        """

        self._path = _SKILL_LOG_FOLDER / f"{self._conversation_key}.txt"

        with open(self._path, "w",encoding="utf-8") as f:
            f.write(init_format)
            f.close()

    def pre_skill_log(self, func_name:str, **args):
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(f"""
            <SKILL_LOG>
                <skill_name>{func_name}</skill_name>
                <skill_args>
                    {args}
                </skill_args>
            """)
            f.close()

        return "skill logged"

    def post_skill_log(self, output):
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(f"""
                <skill_output>
                    {output}
                </skill_output>
            </SKILL_LOG>
            """)

class GraphLog:
    def __init__(self, conversation_key:str):
        self._conversation_key = conversation_key
        init_format =f"""
            <KEY>{self._conversation_key}</KEY>
            <CREATED_DATETIME>{datetime.now()}</CREATED_DATETIME>
        """

        self._path = _GRAPH_LOG_FOLDER / f"{self._conversation_key}.txt"
        with open(self._path, "w") as f:
            f.write(init_format)
            f.close()

    def pre_node_log(self, node_name:str, state:AgentState, graph_name):
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(f"""
            <GRAPH_[{graph_name}]_LOG>
                <node_name>{node_name}</node_name>
                <state_[{state["state_name"]}]_before_node>
                    {str(state)}
                </state_[{state["state_name"]}]_before_node>
            """)
            f.close()

        return "skill logged"

    def post_node_log(self, state:AgentState, graph_name):
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(f"""
                <state_[{state["state_name"]}]_after_node>
                    {str(state)}
                </state_[{state["state_name"]}]_after_node>
            </GRAPH_[{graph_name}]_LOG>
            """)

def skill_log(log: Logging):
    def skill_wrapper(func):
        @wraps(func)
        def wrapper(**arguments):
            log.get_skill_logger().pre_skill_log(func.__name__, **arguments)
            output = func(**arguments)
            log.get_skill_logger().post_skill_log(output)
            return output
        return wrapper
    return skill_wrapper


def graph_log(log: Logging, graph_name:str = "main"):
    def node_wrapper(func):
        @wraps(func)
        def wrapper(state: AgentState|SkillSubGraphState):
            log.get_graph_logger().pre_node_log(func.__name__, state, graph_name)
            output = func(state)
            log.get_graph_logger().post_node_log(output, graph_name)
            return output
        return wrapper
    return node_wrapper