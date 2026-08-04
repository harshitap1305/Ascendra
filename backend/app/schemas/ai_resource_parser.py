"""
Pydantic schema for Agent 3 (Resource Parser) AI output.
This is the validated contract between the AI's JSON and the database write.
"""
from typing import Optional
from pydantic import BaseModel


class ParsedResource(BaseModel):
    type: str                              # video | book | practice | revision | other
    title: str
    source_name: Optional[str] = None     # "Gate Smashers", "Galvin"
    url: Optional[str] = None
    total_units: Optional[int] = None     # total videos / pages / questions


class ParsedResourcesResponse(BaseModel):
    resources: list[ParsedResource]
    estimated_total_hours: Optional[float] = None  # AI's own workload estimate
