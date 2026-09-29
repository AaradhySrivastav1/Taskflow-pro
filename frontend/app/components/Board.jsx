"use client";

import { useCallback, useEffect, useState } from "react";
import { DragDropContext } from "@hello-pangea/dnd";
import Column from "./Column";
import TaskModal from "./TaskModal";
import { api } from "../lib/api";

const COLUMNS = [
  { key: "backlog", label: "Backlog", color: "var(--col-backlog)" },
  { key: "in_progress", label: "In Progress", color: "var(--col-progress)" },
  { key: "review", label: "Review", color: "var(--col-review)" },
  { key: "done", label: "Done", color: "var(--col-done)" },
];

export default function Board() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState("");
  const [modal, setModal] = useState(null); // { mode: 'create' | 'edit', task? }

  const load = useCallback(async () => {
    try {
      const data = await api.listTasks();
      setTasks(data);
    } catch (err) {
      setToast(`Could not reach the API at ${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"} — is the backend running?`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 3200);
    return () => clearTimeout(t);
  }, [toast]);

  async function handleDragEnd(result) {
    const { source, destination, draggableId } = result;
    if (!destination) return;
    if (source.droppableId === destination.droppableId && source.index === destination.index) return;

    const newColumn = destination.droppableId;
    const previous = tasks;

    // optimistic update
    setTasks((prev) =>
      prev.map((t) => (t.id === draggableId ? { ...t, column_status: newColumn } : t))
    );

    try {
      const updated = await api.moveTask(draggableId, newColumn);
      // reconcile with server truth (readiness may have propagated elsewhere too)
      setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      // a move can change downstream readiness; pull the full board fresh
      load();
    } catch (err) {
      setTasks(previous); // rollback the optimistic UI change
      setToast(err.message || "That move isn't allowed.");
    }
  }

  function openCreate() {
    setModal({ mode: "create" });
  }
  function openEdit(task) {
    setModal({ mode: "edit", task });
  }
  function closeModal() {
    setModal(null);
  }

  async function handleCreated() {
    closeModal();
    await load();
    setToast("Task created.");
  }
  async function handleChanged(keepOpen = false) {
    await load();
    if (!keepOpen) {
      closeModal();
      setToast("Changes saved.");
    }
  }
  async function handleDeleted() {
    closeModal();
    await load();
    setToast("Task deleted.");
  }

  // keep the modal's task reference fresh as `tasks` updates (e.g. after adding a dependency)
  const liveModalTask =
    modal?.mode === "edit" ? tasks.find((t) => t.id === modal.task.id) || modal.task : null;

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <span className="brand-mark">TaskFlow Pro</span>
            <span className="brand-sub">DAG-driven workflow engine</span>
          </div>
          <button className="btn btn-primary" onClick={openCreate}>+ New task</button>
        </div>
      </header>

      {loading ? (
        <p className="spinner-line">Loading board…</p>
      ) : (
        <DragDropContext onDragEnd={handleDragEnd}>
          <div className="board">
            {COLUMNS.map((col) => (
              <Column
                key={col.key}
                column={col}
                tasks={tasks.filter((t) => t.column_status === col.key)}
                onOpenTask={openEdit}
              />
            ))}
          </div>
        </DragDropContext>
      )}

      {modal?.mode === "create" && (
        <TaskModal mode="create" allTasks={tasks} onClose={closeModal} onCreated={handleCreated} />
      )}
      {modal?.mode === "edit" && liveModalTask && (
        <TaskModal
          mode="edit"
          task={liveModalTask}
          allTasks={tasks}
          onClose={closeModal}
          onChanged={handleChanged}
          onDeleted={handleDeleted}
        />
      )}

      {toast && <div className="toast">{toast}</div>}
    </>
  );
}
