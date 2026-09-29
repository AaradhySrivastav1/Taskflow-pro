"""
ORM models.

Tasks are graph nodes. TaskDependency rows are directed edges:
    prerequisite_id -> dependent_id
meaning `prerequisite_id` must be Done before `dependent_id` can be Ready.

`readiness` is intentionally NOT a plain editable column with free-text
values chosen by the client. It is written only by the DAG engine
(app/dag.py) after recomputation, so the stored value always reflects the
last engine computation. This keeps "the board can never lie" true even
though we persist the value (for fast reads) rather than recomputing it
on every single fetch.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, DateTime, Enum, ForeignKey, Text, UniqueConstraint, Integer
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class ColumnStatus(str, enum.Enum):
    backlog = "backlog"
    in_progress = "in_progress"
    review = "review"
    done = "done"


class Readiness(str, enum.Enum):
    ready = "ready"
    blocked = "blocked"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    assignee = Column(String, default="")
    due_date = Column(DateTime, nullable=True)

    column_status = Column(Enum(ColumnStatus), default=ColumnStatus.backlog, nullable=False)
    readiness = Column(Enum(Readiness), default=Readiness.ready, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Edges where this task is the prerequisite (i.e. things that depend on it)
    outgoing = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.prerequisite_id",
        back_populates="prerequisite",
        cascade="all, delete-orphan",
    )
    # Edges where this task is the dependent (i.e. its own prerequisites)
    incoming = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.dependent_id",
        back_populates="dependent",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description or "",
            "assignee": self.assignee or "",
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "column_status": self.column_status.value,
            "readiness": self.readiness.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "prerequisite_ids": [e.prerequisite_id for e in self.incoming],
            "dependent_ids": [e.dependent_id for e in self.outgoing],
        }


class TaskDependency(Base):
    """A directed edge: prerequisite_id -> dependent_id."""
    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint("prerequisite_id", "dependent_id", name="uq_edge_pair"),
    )

    id = Column(String, primary_key=True, default=gen_id)
    prerequisite_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    dependent_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String, default="manual")  # "manual" or "ai_suggested"

    prerequisite = relationship("Task", foreign_keys=[prerequisite_id], back_populates="outgoing")
    dependent = relationship("Task", foreign_keys=[dependent_id], back_populates="incoming")


class StatusHistory(Base):
    """
    Audit trail of every column/readiness change, including changes caused
    by propagation rather than a direct user action. Backs the
    Rollback-on-Regression guarantee and gives visibility into *why* a
    task's status changed.
    """
    __tablename__ = "status_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    field = Column(String, nullable=False)          # "column_status" | "readiness"
    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    reason = Column(String, default="")              # "user_move" | "propagation" | "rollback"
    created_at = Column(DateTime, default=datetime.utcnow)
