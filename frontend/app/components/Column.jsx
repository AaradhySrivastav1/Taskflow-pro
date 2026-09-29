"use client";

import { Droppable } from "@hello-pangea/dnd";
import TaskCard from "./TaskCard";

export default function Column({ column, tasks, onOpenTask }) {
  return (
    <div className="column">
      <div className="column-head">
        <span className="column-dot" style={{ background: column.color }} />
        <span className="column-title">{column.label}</span>
        <span className="column-count">{tasks.length}</span>
      </div>

      <Droppable droppableId={column.key}>
        {(provided, snapshot) => (
          <div
            ref={provided.innerRef}
            {...provided.droppableProps}
            className={`column-body ${snapshot.isDraggingOver ? "drag-over" : ""}`}
          >
            {tasks.length === 0 && (
              <div className="column-empty">Nothing here yet</div>
            )}
            {tasks.map((task, index) => (
              <TaskCard key={task.id} task={task} index={index} onOpen={onOpenTask} />
            ))}
            {provided.placeholder}
          </div>
        )}
      </Droppable>
    </div>
  );
}
