from functools import wraps
from pathlib import Path
import os
from datetime import datetime

from agent.graph.agent_state import AgentState, SubGraphSkillParserState

_SKILL_LOG_FOLDER = Path(os.path.dirname(__file__)).parent / "logs" / "skill"
_GRAPH_LOG_FOLDER = Path(os.path.dirname(__file__)).parent / "logs" / "graph"
_CONVERSATION_LOG_FOLDER = Path(os.path.dirname(__file__)).parent / "logs" / "conversation"

BASE_INDENT = "___"
SUB_INDENT = "_"


def _init_logs_folder():
    for folder in (_SKILL_LOG_FOLDER, _GRAPH_LOG_FOLDER, _CONVERSATION_LOG_FOLDER):
        os.makedirs(folder, exist_ok=True)

_init_logs_folder()


def _ind(level: int, extra: int = 0) -> str:
    return BASE_INDENT * level + SUB_INDENT * extra


def _to_readable(state: dict, level: int) -> str:
    prefix = _ind(level, 4)
    lines = []
    for key, value in state.items():
        text = str(value).replace("\n", " ")
        lines.append(f"{prefix}{key}: {text}")
    return "\n".join(lines)


class Logging:
    __slots__ = ["_conversation_key", "_skill_logger", "_graph_logger"]

    def __init__(self):
        self._conversation_key = ""
        self._skill_logger = None
        self._graph_logger = None

    def set_conversation_key(self, conversation_key: str):
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
    def __init__(self, conversation_key: str):
        self._conversation_key = conversation_key
        self._path = _SKILL_LOG_FOLDER / f"{self._conversation_key}.txt"
        with open(self._path, "w", encoding="utf-8") as f:
            f.write(f"<KEY>{conversation_key}</KEY>\n")
            f.write(f"<CREATED_DATETIME>{datetime.now()}</CREATED_DATETIME>\n")

    def pre_skill_log(self, func_name: str, **args):
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(f"<SKILL_LOG>\n")
            f.write(f"  <skill_name>{func_name}</skill_name>\n")
            f.write(f"  <skill_args>{args}</skill_args>\n")

    def post_skill_log(self, output):
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(f"  <skill_output>{output}</skill_output>\n")
            f.write(f"</SKILL_LOG>\n")


class GraphLog:
    def __init__(self, conversation_key: str):
        self._conversation_key = conversation_key
        self._path = _GRAPH_LOG_FOLDER / f"{self._conversation_key}.txt"
        with open(self._path, "w", encoding="utf-8") as f:
            f.write(f"<KEY>{conversation_key}</KEY>\n")
            f.write(f"<CREATED_DATETIME>{datetime.now()}</CREATED_DATETIME>\n")

    def pre_node_log(self, node_name: str, state: AgentState, graph_name: str, level: int):
        ind  = _ind(level)
        ind1 = _ind(level, 2)
        lines = [
            f"{ind}<GRAPH_[{graph_name}]_LOG>",
            f"{ind1}<node_name>{node_name}</node_name>",
            f"{ind1}<state_[{state['state_name']}]_before_node>",
            _to_readable(state, level + 1),
            f"{ind1}</state_[{state['state_name']}]_before_node>",
        ]
        with open(self._path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def post_node_log(self, state: AgentState, graph_name: str, level: int):
        ind  = _ind(level)
        ind1 = _ind(level, 2)
        lines = [
            f"{ind1}<state_[{state['state_name']}]_after_node>",
            _to_readable(state, level + 1),
            f"{ind1}</state_[{state['state_name']}]_after_node>",
            f"{ind}</GRAPH_[{graph_name}]_LOG>",
        ]
        with open(self._path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


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


def graph_log(log: Logging, graph_name: str = "main", level: int = 0):
    def node_wrapper(func):
        @wraps(func)
        def wrapper(state: AgentState | SubGraphSkillParserState):
            log.get_graph_logger().pre_node_log(func.__name__, state, graph_name, level)
            output = func(state)
            log.get_graph_logger().post_node_log(output, graph_name, level)
            return output
        return wrapper
    return node_wrapper
