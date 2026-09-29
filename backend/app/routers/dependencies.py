from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TaskDependency
from app import schemas, dag

router = APIRouter(prefix="/api/dependencies", tags=["dependencies"])


@router.get("", response_model=list[schemas.DependencyOut])
def list_dependencies(db: Session = Depends(get_db)):
    return db.query(TaskDependency).all()


@router.post("", response_model=schemas.DependencyOut, status_code=201)
def create_dependency(payload: schemas.DependencyCreate, db: Session = Depends(get_db)):
    try:
        edge = dag.add_dependency(db, payload.prerequisite_id, payload.dependent_id, source="manual")
        return edge
    except dag.CycleError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/{edge_id}", status_code=204)
def delete_dependency(edge_id: str, db: Session = Depends(get_db)):
    try:
        dag.remove_dependency(db, edge_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return None
