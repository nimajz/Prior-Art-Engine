from typing import Literal
from pydantic import BaseModel, Field


RetrievalMode = Literal[
    "Concept + Full-Text (Recommended)",
    "Full-Text Only",
    "Concept-Based Only",
]


class SearchRequest(BaseModel):
    idea: str = Field(..., min_length=1, description="Research idea / technical system description")
    max_display: int = Field(5, ge=3, le=10)
    effective_threshold: int = Field(25, ge=10, le=50)
    highlight_threshold_pct: int = Field(78, ge=60, le=95)
    retrieval_mode: RetrievalMode = "Concept + Full-Text (Recommended)"
    enable_patent_search: bool = True
    enable_arm_d: bool = True
    enable_global_report: bool = True
