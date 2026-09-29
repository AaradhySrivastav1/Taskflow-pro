"""
The DAG engine.

This module owns every correctness guarantee promised in the synopsis:

  * No Cycles          -> would_create_cycle() / add_dependency()
  * status derivation   -> compute_readiness()
  * propagation         -> propagate_from()
  * No Compounding      -> propagate_from() uses a single visited-set per
                            call, so one triggering change can touch each
                            downstream node at most once, however many
                            paths lead to it.
  * Rollback on Regression -> all public entry points wrap their writes in
                            a transaction; on any exception the session is
                            rolled back and the exception re-raised, so the
                            caller (the API layer) always sees either a
                            fully-applied change or no change at all.

Nothing in here trusts the client. The API layer is a thin translation
from HTTP to these functions.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Task, TaskDependency, StatusHistory, ColumnStatus, Readiness


class CycleError(Exception):
    """Raised when a proposed dependency edge would create a cycle."""
    pass


class DependencyNotSatisfiedError(Exception):
    """Raised when a user tries to move a task into Done/Review while Blocked."""
    pass


# --------------------------------------------------------------------------
# Cycle detection
# --------------------------------------------------------------------------

def would_create_cycle(db: Session, prerequisite_id: str, dependent_id: str) -> bool:
    """
    Would adding edge (prerequisite_id -> dependent_id) create a cycle?

    Equivalent to asking: is there already a path from `dependent_id` back
    to `prerequisite_id`? If so, adding this edge would close a loop.
    Implemented as an iterative DFS to avoid recursion-depth issues on
    large graphs.
    """
    if prerequisite_id == dependent_id:
        return True  # self-loop

    stack = [dependent_id]
    visited = set()
    while stack:
        node = stack.pop()
        if node == prerequisite_id:
            return True
        if node in visited:
            continue
        visited.add(node)
        # follow edges outward from `node` (things node is a prerequisite for)
        outgoing = db.query(TaskDependency).filter(
            TaskDependency.prerequisite_id == node
        ).all()
        for edge in outgoing:
            stack.append(edge.dependent_id)
    return False


# --------------------------------------------------------------------------
# Readiness derivation
# --------------------------------------------------------------------------

def compute_readiness(db: Session, task: Task) -> Readiness:
    """
    A task is Ready iff every direct prerequisite is in the Done column.
    This is a pure function of current data — never trust a stored value
    without recomputation when correctness matters.
    """
    incoming = db.query(TaskDependency).filter(
        TaskDependency.dependent_id == task.id
    ).all()
    if not incoming:
        return Readiness.ready

    for edge in incoming:
        prereq = db.query(Task).filter(Task.id == edge.prerequisite_id).first()
        if prereq is None or prereq.column_status != ColumnStatus.done:
            return Readiness.blocked
    return Readiness.ready


def _record(db: Session, task_id: str, field: str, old, new, reason: str):
    if old == new:
        return
    db.add(StatusHistory(
        task_id=task_id, field=field,
        old_value=str(old) if old is not None else None,
        new_value=str(new) if new is not None else None,
        reason=reason,
    ))


def _refresh_readiness(db: Session, task: Task, reason: str) -> bool:
    """Recompute and persist one task's readiness. Returns True if it changed."""
    new_readiness = compute_readiness(db, task)
    if new_readiness != task.readiness:
        _record(db, task.id, "readiness", task.readiness.value, new_readiness.value, reason)
        task.readiness = new_readiness
        task.updated_at = datetime.utcnow()
        return True
    return False


# --------------------------------------------------------------------------
# Propagation (No Compounding: one visited-set per triggering event)
# --------------------------------------------------------------------------

def propagate_from(db: Session, task_id: str, reason: str = "propagation") -> list[str]:
    """
    Walk downstream from `task_id` (tasks that depend on it, directly or
    transitively) and recompute readiness for each. A single visited-set
    scoped to this call guarantees each downstream node is (re)computed at
    most once per triggering event, regardless of how many paths reach it
    or how many of its own prerequisites also changed in this same batch —
    this is what "No Compounding" means in practice.

    Returns the list of task ids whose readiness actually changed.
    """
    visited: set[str] = set()
    changed: list[str] = []
    frontier = [task_id]

    while frontier:
        current_id = frontier.pop()
        edges = db.query(TaskDependency).filter(
            TaskDependency.prerequisite_id == current_id
        ).all()
        for edge in edges:
            dep_id = edge.dependent_id
            if dep_id in visited:
                continue
            visited.add(dep_id)
            dep_task = db.query(Task).filter(Task.id == dep_id).first()
            if dep_task is None:
                continue
            if _refresh_readiness(db, dep_task, reason):
                changed.append(dep_id)
            # continue walking downstream regardless of whether this node's
            # own readiness changed, since a grandchild might still need
            # re-evaluation (e.g. was already blocked for another reason)
            frontier.append(dep_id)

    return changed


# --------------------------------------------------------------------------
# Public, transactional operations (Rollback on Regression)
# --------------------------------------------------------------------------

def add_dependency(db: Session, prerequisite_id: str, dependent_id: str, source: str = "manual") -> TaskDependency:
    """Create a dependency edge. Rejects cycles and self-loops. Transactional."""
    try:
        prereq = db.query(Task).filter(Task.id == prerequisite_id).first()
        dependent = db.query(Task).filter(Task.id == dependent_id).first()
        if prereq is None or dependent is None:
            raise ValueError("Both prerequisite and dependent task must exist")

        existing = db.query(TaskDependency).filter(
            TaskDependency.prerequisite_id == prerequisite_id,
            TaskDependency.dependent_id == dependent_id,
        ).first()
        if existing:
            return existing  # idempotent

        if would_create_cycle(db, prerequisite_id, dependent_id):
            raise CycleError(
                f"Adding '{prereq.title}' -> '{dependent.title}' would create a cycle."
            )

        edge = TaskDependency(prerequisite_id=prerequisite_id, dependent_id=dependent_id, source=source)
        db.add(edge)
        db.flush()

        # the newly-dependent task may now be blocked (or, if the
        # prerequisite is already done, might stay ready)
        _refresh_readiness(db, dependent, reason="dependency_added")
        propagate_from(db, dependent_id, reason="dependency_added")

        db.commit()
        db.refresh(edge)
        return edge
    except Exception:
        db.rollback()
        raise


def remove_dependency(db: Session, edge_id: str) -> None:
    try:
        edge = db.query(TaskDependency).filter(TaskDependency.id == edge_id).first()
        if edge is None:
            raise ValueError("Dependency edge not found")
        dependent_id = edge.dependent_id
        db.delete(edge)
        db.flush()

        dependent = db.query(Task).filter(Task.id == dependent_id).first()
        if dependent:
            _refresh_readiness(db, dependent, reason="dependency_removed")
            propagate_from(db, dependent_id, reason="dependency_removed")

        db.commit()
    except Exception:
        db.rollback()
        raise


def move_task(db: Session, task_id: str, new_column: ColumnStatus, force: bool = False) -> Task:
    """
    Move a task to a new Kanban column. Rejects moving a Blocked task into
    Review or Done unless `force=True` is explicitly passed (an escape
    hatch a UI could offer for exceptional cases, off by default).

    On success, this is exactly the kind of change that must propagate:
    moving a task INTO Done can unblock its dependents; moving a task OUT
    of Done (a regression) can re-block dependents that were already
    marked Ready/Done — this function handles both directions identically
    by simply recomputing readiness for every downstream node.
    """
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task is None:
            raise ValueError("Task not found")

        old_column = task.column_status
        current_readiness = compute_readiness(db, task)

        if (
            not force
            and current_readiness == Readiness.blocked
            and new_column in (ColumnStatus.review, ColumnStatus.done)
        ):
            raise DependencyNotSatisfiedError(
                f"'{task.title}' is Blocked by incomplete prerequisites and cannot move to "
                f"{new_column.value}."
            )

        _record(db, task.id, "column_status", old_column.value, new_column.value, "user_move")
        task.column_status = new_column
        task.updated_at = datetime.utcnow()
        db.flush()

        # this task's own readiness doesn't change from moving itself, but
        # every downstream dependent must be re-evaluated, since a move to
        # or from Done changes what they see as "prerequisite complete"
        propagate_from(db, task_id, reason="schedule_change")

        db.commit()
        db.refresh(task)
        return task
    except Exception:
        db.rollback()
        raise


def recompute_all(db: Session) -> None:
    """Full-graph recompute, used on startup/seed to guarantee consistency."""
    try:
        tasks = db.query(Task).all()
        # iterate a few passes so multi-level chains settle regardless of
        # row order (cheap for the sizes this project targets)
        for _ in range(max(1, len(tasks))):
            any_changed = False
            for task in tasks:
                if _refresh_readiness(db, task, reason="recompute"):
                    any_changed = True
            if not any_changed:
                break
        db.commit()
    except Exception:
        db.rollback()
        raise
