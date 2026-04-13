from pydantic import BaseModel, ConfigDict
from typing import List

class _retrieve_question_(BaseModel):
    model_config = ConfigDict(extra="forbid")
    Type: str
    Question_Word: str
    Entities: List[str]
    Relationship: List[str]

class _retrieve_statement_(BaseModel):
    model_config = ConfigDict(extra="forbid")
    Type: str
    Entities: List[str]
    Relationship: List[str]