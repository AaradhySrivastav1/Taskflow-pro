from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    assignee: Optional[str] = ""
    due_date: Optional[datetime] = None
    column_status: Optional[str] = "backlog"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee: Optional[str] = None
    due_date: Optional[datetime] = None


class TaskMove(BaseModel):
    column_status: str
    force: Optional[bool] = False


class TaskOut(BaseModel):
    id: str
    title: str
    description: str
    assignee: str
    due_date: Optional[str]
    column_status: str
    readiness: str
    created_at: Optional[str]
    updated_at: Optional[str]
    prerequisite_ids: List[str]
    dependent_ids: List[str]


class DependencyCreate(BaseModel):
    prerequisite_id: str
    dependent_id: str


class DependencyOut(BaseModel):
    id: str
    prerequisite_id: str
    dependent_id: str
    source: str


class AISuggestRequest(BaseModel):
    task_id: str


class AISuggestion(BaseModel):
    prerequisite_id: str
    prerequisite_title: str
    confidence: float
    rationale: str
