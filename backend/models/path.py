from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AmbiguityCandidate(BaseModel):
    person_id: str = Field(..., description="Unique person identifier")
    name: str = Field(..., description="Full Name")
    aliases: List[str] = Field(default_factory=list, description="Known aliases")
    dob: Optional[str] = Field(default=None, description="Date of birth")
    case_ids: List[str] = Field(default_factory=list, description="Associated case IDs")
    element_id: Optional[str] = Field(default=None, description="Neo4j element ID")


class ShortestPathResponse(BaseModel):
    ambiguous: bool = Field(default=False)
    nodes: List[Dict[str, Any]] = Field(default_factory=list, description="Nodes in shortest path")
    relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Edges in shortest path")
    path_length: int = Field(default=0, description="Number of relationship hops")
    summary: Optional[str] = Field(default=None, description="Human readable path summary")


class AmbiguousPathResponse(BaseModel):
    ambiguous: bool = Field(default=True)
    message: str = Field(..., description="Explanation of ambiguity")
    candidates: List[AmbiguityCandidate] = Field(..., description="List of matching person candidates")

