import requests
from typing import Dict, TypedDict, Callable, Any, List
from pydantic import BaseModel, ConfigDict
from ._internal import  _retrieve_question_, _retrieve_statement_
__all__ = ["FuncRetrieveArgs", "FuncRetrieveArgs_Hint", "FuncRetrieveArgs_Usage_Prompt", "retrieve"]

CONTROL_PLANE_URL = "http://localhost:8000"

FuncRetrieveArgs_Hint = """
{
    "queries": {
        "Query #1": {
            "Type": "Question",
            "Question Word": "How",
            "Entities": ["Entity1", "Entity2"],
            "Relationship": ["relationship_word"]
        },
        "Query #2": {
            "Type": "Statement",
            "Entities": ["Entity1", "Entity2"],
            "Relationship": ["relationship_word"]
        }
    }
}
"""

FuncRetrieveArgs_Usage_Prompt = f"""
TASK: Extract entities and relationships from the Context and fill the JSON template below.

OUTPUT RULES — strictly follow every rule:
1. Output ONLY the JSON object. Start your response with {{ and end with }}.
2. Do NOT write any explanation, greeting, or prose before or after the JSON.
3. Do NOT use markdown or code fences.
4. Every field listed below is REQUIRED — never omit a field.

FIELD RULES:
- "Type"         : REQUIRED. Must be exactly "Question" or "Statement".
- "Question Word": REQUIRED when Type is "Question". Must be one of: How, What, Where, When, Who.
- "Entities"     : REQUIRED. Non-empty list of noun/concept strings found in the context.
- "Relationship" : REQUIRED. Non-empty list of verb/action strings found in the context.

JSON TEMPLATE (fill Entity1/Entity2/relationship_word with real values):
{FuncRetrieveArgs_Hint}

EXAMPLE — for input "How does GDP affect Inflation, GDP indicate Sector":
{{
    "queries": {{
        "Query #1": {{
            "Type": "Question",
            "Question Word": "How",
            "Entities": ["GDP", "Inflation"],
            "Relationship": ["affect"]
        }},
        "Query #2": {{
            "Type": "Statement",
            "Entities": ["GDP", "Sector"],
            "Relationship": ["indicate"]
        }}
    }}
}}

Now fill the template using the Context. Your response must begin with {{
"""

class FuncRetrieveArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: Dict[str,_retrieve_question_|_retrieve_statement_]


def retrieve(queries: dict) -> dict:
    resp = requests.post(
        f"{CONTROL_PLANE_URL}/retrieve",
        json={"queries": queries},
        timeout=300,
    )
    resp.raise_for_status()
    result = resp.json()
    return result