import requests
from typing import Dict, TypedDict, Callable, Any, List
from pydantic import BaseModel, ConfigDict
from ._internal import  _retrieve_question_, _retrieve_statement_
__all__ = ["FuncRetrieveArgs", "FuncRetrieveArgs_Hint", "FuncRetrieveArgs_Usage_Prompt", "retrieve"]

CONTROL_PLANE_URL = "http://localhost:8000"

FuncRetrieveArgs_Hint = """
{
    "Query #1": {
        "Type":"Question or Statement",
        "Question Word":"How|What|Where|Who|When",
        "Entities": List,
        "Relationship": List
    },
    "Query #2": {
        "Type": "Statement",
        "Entities": List,
        "Relationship": List
    }
}
"""

FuncRetrieveArgs_Usage_Prompt = f"""
    Rules:
    - Type: Question or Statement
    - If Type is Question, Question Word: How, What, Where, When, Who
    - Entities: list of entity in the provided text
    - Relationship: list of relationship between Entities
    
    Format:
    {FuncRetrieveArgs_Hint}
    
    Example: 
    [] If the user Query is 
    - How does GDP affect Inflation
    - GDP indicate Sector
    [] Then the extracted format is
    ``` output
    "Query #1": {{
        "Type": "Question",
        "Question Word": "How",
        "Entities": ["GDP", "Inflation"],
        "Relationship": ["affect"]
    }},
    "Query #2": {{
        "Type": "Statement",
        "Entities": ["GDP", "Sector"],
        "Relationship": ["indicate/right"]
    }}
    ```
"""

class FuncRetrieveArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: Dict[str,_retrieve_question_|_retrieve_statement_]


def retrieve(queries: dict) -> dict:
    resp = requests.post(
        f"{CONTROL_PLANE_URL}/retrieve",
        json={"queries": queries},
        timeout=180,
    )
    resp.raise_for_status()
    result = resp.json()
    return result