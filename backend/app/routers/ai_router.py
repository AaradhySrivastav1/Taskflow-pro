from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Task
from app import ai

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/suggest/{task_id}")
def suggest(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    suggestions = ai.suggest_dependencies(db, task)
    return {"task_id": task_id, "suggestions": suggestions}
