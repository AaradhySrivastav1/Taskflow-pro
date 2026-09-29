from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Task, ColumnStatus
from app import schemas, dag

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[schemas.TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(Task.created_at.asc()).all()
    return [t.to_dict() for t in tasks]


@router.post("", response_model=schemas.TaskOut, status_code=201)
def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db)):
    try:
        col = ColumnStatus(payload.column_status or "backlog")
    except ValueError:
        raise HTTPException(400, f"Invalid column_status: {payload.column_status}")

    task = Task(
        title=payload.title.strip(),
        description=payload.description or "",
        assignee=payload.assignee or "",
        due_date=payload.due_date,
        column_status=col,
    )
    if not task.title:
        raise HTTPException(400, "Title is required")

    db.add(task)
    db.commit()
    db.refresh(task)
    return task.to_dict()


@router.patch("/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: str, payload: schemas.TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    for field in ("title", "description", "assignee", "due_date"):
        val = getattr(payload, field)
        if val is not None:
            setattr(task, field, val)
    db.commit()
    db.refresh(task)
    return task.to_dict()


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    downstream_ids = [e.dependent_id for e in task.outgoing]
    db.delete(task)
    db.commit()
    # re-evaluate anything that depended on the deleted task
    for dep_id in downstream_ids:
        dep = db.query(Task).filter(Task.id == dep_id).first()
        if dep:
            dag._refresh_readiness(db, dep, reason="prerequisite_deleted")
            dag.propagate_from(db, dep_id, reason="prerequisite_deleted")
    db.commit()
    return None


@router.post("/{task_id}/move", response_model=schemas.TaskOut)
def move_task(task_id: str, payload: schemas.TaskMove, db: Session = Depends(get_db)):
    try:
        col = ColumnStatus(payload.column_status)
    except ValueError:
        raise HTTPException(400, f"Invalid column_status: {payload.column_status}")
    try:
        task = dag.move_task(db, task_id, col, force=payload.force)
        return task.to_dict()
    except dag.DependencyNotSatisfiedError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))
