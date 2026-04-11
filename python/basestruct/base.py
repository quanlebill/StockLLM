from pydantic import BaseModel, ConfigDict
from typing import Any, Optional, List, Tuple, Dict

"""
Control Plane Struct: control_plane.py 
"""
# Abstraction
class StructConversation(BaseModel):
    conversation_key: str|None

class StructSkill(BaseModel):
    skill_name: str|None

# Skill Struct
class SkillRequest(StructSkill, StructConversation):
    arguments: Dict = {}
    conversation_key: str = ""

class SkillResult(StructSkill):
    output: Any = None
    error: Optional[str] = None

#Conversation Struct
class ConversationGroup(StructConversation):
    conversation_date:str
    conversation_block:List

class InvokeRequest(StructConversation):
    skills: List[SkillRequest]

class LogCommentRequest(StructConversation):
    comment: str
    block_index: int = -1

class ConversationStartRequest(StructConversation):
    user_question: str

class LogAnswerRequest(StructConversation):
    answer: str
    canonical: str = ""
    query_hash: str = ""

class AppendWorkflowRequest(StructConversation):
    workflow: str

class RateRequest(StructConversation):
    rating: str

#Status
class DefaultPayload(BaseModel):
    details: str

class MCPStatus(BaseModel):
    status: str = "ok"
    payload: Any = None
    error: Any = None

class InvokeResponse(StructConversation):
    skills: List[SkillResult]

class LoadLastConversationResponse(StructConversation):
    result: Any

class RegistryDebug(BaseModel):
    count:int
    keys: Any

class ListSkillResponse(BaseModel):
    skills: List
    categories: str|None



""" 
Retrieval Pipeline Struct: retrieval_pipeline.py 
"""
class LoadPagesRequest(BaseModel):
    topic: str
    book_name: str
    page_indexes: List[List[int]]

class LoadPagesByPathsRequest(BaseModel):
    page_paths: List[str]

class RetrieveRequest(BaseModel):
    queries: Dict


""" 
Storing Struct: storing.oy 
"""
class EntityProperties(BaseModel):
    page_index: List[Tuple[int, int]]
    summary: str
    included_entities: List[str]
    keywords: List[str]

class AddEntitiesRequest(BaseModel):
    entities: Dict[str, EntityProperties]

class AddRelationshipRequest(BaseModel):
    relationship: str
    from_entity: str
    to_entity: str

class BuildGraphRequest(BaseModel):
    summary_file: str
    book_name: str


"""
Self Improvement Struct: self_improvement.py
"""
class EntityInput(BaseModel):
    name: str
    aliases: list[str] = []
    category: str = ""
    description: str = ""

class PolicyInput(BaseModel):
    description: str
    cause_entities: list[str]
    affect_entities: list[str] = []
    expires_at: Optional[str] = None

class RelationshipInput(BaseModel):
    from_entity: str
    to_entity: str
    direction: str = ""
    strength: str = ""
    description: str = ""

class NoteInput(BaseModel):
    content: str
    entity: str

class ExtractRequest(BaseModel):
    block_id: str
    entities: list[EntityInput] = []
    policies: list[PolicyInput] = []
    relationships: list[RelationshipInput] = []
    notes: list[NoteInput] = []
    skipped: bool = False


"""
Chunking Struct: chunking.py 
"""
class SplitRequest(BaseModel):
    filepath: str
    topic: str


"""
Doc Analysis Struct: doc_analysis.py
"""
class SummaryEntry(BaseModel):
    index: int
    summary: str