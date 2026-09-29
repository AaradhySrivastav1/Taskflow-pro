"""
AI-Augmented Dependency Suggestion.

Sends the target task's title/description plus a compact list of the
other tasks in the workspace to Gemini, and asks it to propose plausible
prerequisite relationships with a short rationale each.

Design choices that matter for the correctness story in the synopsis:
  * This module NEVER writes to the database. It only returns candidate
    suggestions; the caller (router) hands them to the frontend, and a
    suggestion is only persisted if the user accepts it — through the
    exact same app.dag.add_dependency() path as a manually created edge,
    so it still goes through cycle detection.
  * If no API key is configured, or the call fails for any reason, this
    degrades gracefully to an empty suggestion list rather than raising,
    so the rest of the app (manual dependency creation) is unaffected.
"""
import json
import os
from typing import List

from sqlalchemy.orm import Session

from app.models import Task, TaskDependency

MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = (
    "You are a project-planning assistant inside a Kanban tool called TaskFlow Pro. "
    "Given one target task and a list of other candidate tasks already in the workspace, "
    "identify which of the candidate tasks are LIKELY PREREQUISITES of the target task "
    "(i.e. the candidate task should logically be completed before the target task can "
    "start). Be conservative: only suggest a dependency when there is a clear, sensible "
    "ordering reason (e.g. 'Backend API' before 'Integration Tests'). Do not suggest a "
    "task as its own prerequisite. Respond ONLY with a JSON array (no prose, no markdown "
    "fences) of objects shaped like: "
    '[{"candidate_id": "<id>", "confidence": 0.0-1.0, "rationale": "<one short sentence>"}]. '
    "If nothing qualifies, respond with []."
)


def _client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def suggest_dependencies(db: Session, task: Task) -> List[dict]:
    client = _client()
    if client is None:
        return []

    others = db.query(Task).filter(Task.id != task.id).all()
    if not others:
        return []

    existing_prereq_ids = {e.prerequisite_id for e in task.incoming}
    candidates = [t for t in others if t.id not in existing_prereq_ids]
    if not candidates:
        return []

    candidate_lines = "\n".join(
        f'- id="{c.id}" title="{c.title}" description="{(c.description or "")[:200]}" '
        f'column="{c.column_status.value}"'
        for c in candidates
    )
    user_prompt = (
        f'Target task: title="{task.title}" description="{(task.description or "")[:400]}"\n\n'
        f"Candidate tasks:\n{candidate_lines}\n\n"
        "Which candidates are likely prerequisites of the target task?"
    )

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=f"{SYSTEM_PROMPT}\n\n{user_prompt}",
        )
        text = (response.text or "").strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        raw = json.loads(text) if text else []
    except Exception:
        return []

    by_id = {c.id: c for c in candidates}
    results = []
    for item in raw:
        cid = item.get("candidate_id")
        cand = by_id.get(cid)
        if not cand:
            continue
        results.append({
            "prerequisite_id": cand.id,
            "prerequisite_title": cand.title,
            "confidence": float(item.get("confidence", 0.5)),
            "rationale": str(item.get("rationale", ""))[:300],
        })
    results.sort(key=lambda r: r["confidence"], reverse=True)
    return results[:5]
