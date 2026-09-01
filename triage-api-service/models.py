from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IncidentStatus(str, Enum):
    NEW = "new"
    TRIAGING = "triaging"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    description: str = Field(default="", max_length=8192)
    source: str = Field(default="rules-engine", max_length=128)
    labels: dict[str, str] = Field(default_factory=dict)


class TriageUpdate(BaseModel):
    severity: Optional[Severity] = None
    status: Optional[IncidentStatus] = None
    assignee: Optional[str] = Field(default=None, max_length=256)
    notes: Optional[str] = Field(default=None, max_length=8192)


class IncidentRead(BaseModel):
    id: str
    title: str
    description: str
    source: str
    labels: dict[str, str]
    severity: Severity
    status: IncidentStatus
    assignee: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime