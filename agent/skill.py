from skills.skill_registry import SKILL_REGISTRY

def _invoke_skill(skill_name, **kwargs):
    return SKILL_REGISTRY[skill_name]['func'](**kwargs)