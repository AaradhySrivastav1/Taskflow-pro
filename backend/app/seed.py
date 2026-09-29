"""
Seeds the database with 9 realistic tasks and a dependency graph that
mirrors a typical feature-delivery pipeline. Run with:

    python -m app.seed

Safe to re-run: it clears existing data first.

Dependency graph created:

    Design Mockups ────────────┐
                                ▼
    Database Schema ──► Backend API ──► Integration Tests ──► Deployment Pipeline
                                │                                     ▲
                                ▼                                     │
                          Frontend UI ─────────────────────────────────
                                │
                                ▼
                          Code Review ──► Documentation
                                
    Load Testing depends on Integration Tests as well.
"""
from app.database import SessionLocal, Base, engine
from app.models import Task, TaskDependency, ColumnStatus, StatusHistory
from app import dag

Base.metadata.create_all(bind=engine)


def run():
    db = SessionLocal()
    try:
        db.query(StatusHistory).delete()
        db.query(TaskDependency).delete()
        db.query(Task).delete()
        db.commit()

        def T(title, desc, assignee, col=ColumnStatus.backlog):
            t = Task(title=title, description=desc, assignee=assignee, column_status=col)
            db.add(t)
            db.flush()
            return t

        design = T("Design Mockups", "UI/UX mockups for the core screens.", "Priya", ColumnStatus.done)
        schema = T("Database Schema", "Define tables for tasks, edges, and history.", "Rahul", ColumnStatus.done)
        backend = T("Backend API", "FastAPI endpoints for tasks, dependencies, moves.", "Aaradhy", ColumnStatus.in_progress)
        frontend = T("Frontend UI", "React Kanban board with drag-and-drop.", "Sneha", ColumnStatus.in_progress)
        integ = T("Integration Tests", "End-to-end tests across API and UI.", "Rahul")
        load = T("Load Testing", "Stress-test the API under concurrent load.", "Aaradhy")
        deploy = T("Deployment Pipeline", "CI/CD to a staging environment.", "Priya")
        review = T("Code Review", "Peer review of backend and frontend PRs.", "Sneha", ColumnStatus.review)
        docs = T("Documentation", "README, API docs, setup instructions.", "Aaradhy")

        db.commit()

        edges = [
            (schema.id, backend.id),
            (design.id, frontend.id),
            (backend.id, frontend.id),
            (backend.id, integ.id),
            (frontend.id, integ.id),
            (integ.id, deploy.id),
            (integ.id, load.id),
            (backend.id, review.id),
            (frontend.id, review.id),
            (review.id, docs.id),
        ]
        for prereq_id, dep_id in edges:
            db.add(TaskDependency(prerequisite_id=prereq_id, dependent_id=dep_id, source="manual"))
        db.commit()

        dag.recompute_all(db)

        print(f"Seeded {db.query(Task).count()} tasks and {db.query(TaskDependency).count()} dependency edges.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
