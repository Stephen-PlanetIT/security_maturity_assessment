#!/usr/bin/env python3
"""
Artefact schema for GenerationContract v1.1.
Provides a strict, explicit model for artefact metadata surface in the pipeline.
"""

from typing import Optional
from pydantic import BaseModel, Field

class ArtefactSchema(BaseModel):
    author: Optional[str] = Field(default="", description=" Artefact author")
    audience: Optional[str] = Field(default="", description="Target audience for the artefact")
    knowledge_level: Optional[str] = Field(default="", description="Knowledge level required by audience")
    type: Optional[str] = Field(default="", description="Artefact type/category (artefact_class)")
    reference: str = Field(..., description="Reference identifier for the artefact (e.g. 'slide23 log')")
    source: Optional[str] = Field(default="", description="Source/origin of artefact content")
    date: Optional[str] = Field(default="", description="Date or timestamp of artefact creation")
    purpose: Optional[str] = Field(default="", description="Purpose or intended use of the artefact")
    artefact_class: Optional[str] = Field(default=None, description="High-level taxonomy class for the artefact")

def validate_artefact(artefact: dict) -> bool:
    """
    Lightweight validator: returns True if artefact dictionary conforms to ArtefactSchema.
    """
    try:
        ArtefactSchema(**artefact)
        return True
    except Exception:
        return False

__all__ = ["ArtefactSchema", "validate_artefact"]