from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.database import Base, engine
from app.routers import tasks, dependencies, ai_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TaskFlow Pro API",
    description="DAG-driven task engine behind the TaskFlow Pro Kanban board.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local/demo project; tighten for real deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router)
app.include_router(dependencies.router)
app.include_router(ai_router.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
