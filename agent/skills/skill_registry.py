from typing import List, Dict, Callable
from pydantic import BaseModel
from enum import Enum

from scripts.regsetup import description

#import skills
from .mcp_control_plane import FuncRetrieveArgs, FuncRetrieveArgs_Hint, FuncRetrieveArgs_Usage_Prompt, retrieve


class SkillAddFlag(Enum):
    ADDED = "added"
    FAILED = "failed, already existed"

class Skill(BaseModel):
    func: Callable
    usage_prompt: str
    arg_hint: str
    description: str

class SkillRegistry:
    __slots__ = ("skill_list")
    def __init__(self):
        self.skill_list = {}

    def add_skill(self, skill_name,skill: Skill) -> SkillAddFlag:
        if skill_name not in self.skill_list:
            self.skill_list[skill_name] = skill
            return SkillAddFlag.ADDED
        return SkillAddFlag.FAILED

    def get_skill(self, skill_name: str) -> Skill:
        return self.skill_list[skill_name]

SKILL_REGISTRY = SkillRegistry()
SKILL_REGISTRY.add_skill(
    skill_name="retrieve",
    skill = Skill(
        func=retrieve,
        usage_prompt=FuncRetrieveArgs_Usage_Prompt,
        arg_hint=FuncRetrieveArgs_Hint,
        description = """
             Retrieve information for more details answer
        """
    )
)
