"use client";

import { Draggable } from "@hello-pangea/dnd";

function initials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return parts.slice(0, 2).map((p) => p[0].toUpperCase()).join("");
}

function formatDue(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function TaskCard({ task, index, onOpen }) {
  const blocked = task.readiness === "blocked";
  const prereqCount = task.prerequisite_ids.length;
  const due = formatDue(task.due_date);

  return (
    <Draggable draggableId={task.id} index={index}>
      {(provided, snapshot) => (
        <div
          ref={provided.innerRef}
          {...provided.draggableProps}
          {...provided.dragHandleProps}
          className={`card ${blocked ? "is-blocked" : "is-ready"} ${snapshot.isDragging ? "dragging" : ""}`}
          onClick={() => onOpen(task)}
        >
          <p className="card-title">{task.title}</p>
          <div className="card-meta">
            <span className={`badge ${blocked ? "badge-blocked" : "badge-ready"}`}>
              <span className="badge-dot" />
              {blocked ? "Blocked" : "Ready"}
            </span>
            {prereqCount > 0 && (
              <span className="dep-chip">⛓ {prereqCount} prereq{prereqCount > 1 ? "s" : ""}</span>
            )}
          </div>
          <div className="card-foot">
            <span>{due ? `Due ${due}` : "No due date"}</span>
            {task.assignee && <span className="avatar" title={task.assignee}>{initials(task.assignee)}</span>}
          </div>
        </div>
      )}
    </Draggable>
  );
}
