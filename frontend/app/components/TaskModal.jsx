"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/api";

const COLUMN_OPTIONS = [
  { value: "backlog", label: "Backlog" },
  { value: "in_progress", label: "In Progress" },
  { value: "review", label: "Review" },
  { value: "done", label: "Done" },
];

export default function TaskModal({ mode, task, allTasks, onClose, onCreated, onChanged, onDeleted }) {
  const isEdit = mode === "edit";

  const [title, setTitle] = useState(task?.title || "");
  const [description, setDescription] = useState(task?.description || "");
  const [assignee, setAssignee] = useState(task?.assignee || "");
  const [dueDate, setDueDate] = useState(task?.due_date ? task.due_date.slice(0, 10) : "");
  const [columnStatus, setColumnStatus] = useState(task?.column_status || "backlog");

  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const [addPrereqId, setAddPrereqId] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [suggestLoading, setSuggestLoading] = useState(false);

  useEffect(() => {
    setSuggestions([]);
  }, [task?.id]);

  const prereqTasks = isEdit
    ? task.prerequisite_ids
        .map((id) => allTasks.find((t) => t.id === id))
        .filter(Boolean)
    : [];

  const eligiblePrereqOptions = isEdit
    ? allTasks.filter((t) => t.id !== task.id && !task.prerequisite_ids.includes(t.id))
    : [];

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    setSaving(true);
    try {
      if (isEdit) {
        await api.updateTask(task.id, {
          title: title.trim(),
          description,
          assignee,
          due_date: dueDate ? new Date(dueDate).toISOString() : null,
        });
        onChanged();
      } else {
        await api.createTask({
          title: title.trim(),
          description,
          assignee,
          due_date: dueDate ? new Date(dueDate).toISOString() : null,
          column_status: columnStatus,
        });
        onCreated();
      }
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!isEdit) return;
    if (!confirm(`Delete "${task.title}"? This also removes its dependency links.`)) return;
    setSaving(true);
    try {
      await api.deleteTask(task.id);
      onDeleted();
    } catch (err) {
      setError(err.message || "Could not delete task.");
      setSaving(false);
    }
  }

  async function handleAddPrereq() {
    if (!addPrereqId) return;
    setError("");
    try {
      await api.addDependency(addPrereqId, task.id);
      setAddPrereqId("");
      onChanged(true); // keep modal open, refresh data
    } catch (err) {
      setError(err.message || "Could not add dependency.");
    }
  }

  async function handleRemovePrereq(prereqId) {
    // find the edge id via dependencies list is not locally known; backend
    // exposes removal by edge id, so we look it up through a fresh fetch
    setError("");
    try {
      const edges = await api.listDependencies();
      const edge = edges.find(
        (e) => e.prerequisite_id === prereqId && e.dependent_id === task.id
      );
      if (edge) {
        await api.removeDependency(edge.id);
        onChanged(true);
      }
    } catch (err) {
      setError(err.message || "Could not remove dependency.");
    }
  }

  async function handleSuggest() {
    setSuggestLoading(true);
    setError("");
    try {
      const res = await api.suggestDependencies(task.id);
      setSuggestions(res.suggestions || []);
    } catch (err) {
      setError(err.message || "AI suggestion request failed.");
    } finally {
      setSuggestLoading(false);
    }
  }

  async function acceptSuggestion(s) {
    try {
      await api.addDependency(s.prerequisite_id, task.id);
      setSuggestions((prev) => prev.filter((x) => x.prerequisite_id !== s.prerequisite_id));
      onChanged(true);
    } catch (err) {
      setError(err.message || "Could not accept suggestion.");
    }
  }

  function rejectSuggestion(s) {
    setSuggestions((prev) => prev.filter((x) => x.prerequisite_id !== s.prerequisite_id));
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-head">
          <h2 className="modal-title">{isEdit ? "Edit task" : "New task"}</h2>
          <button className="btn btn-ghost" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Title</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Backend API" autoFocus />
          </div>
          <div className="field">
            <label>Description</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What does this task involve?" />
          </div>
          <div className="field-row">
            <div className="field">
              <label>Assignee</label>
              <input value={assignee} onChange={(e) => setAssignee(e.target.value)} placeholder="Name" />
            </div>
            <div className="field">
              <label>Due date</label>
              <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            </div>
          </div>
          {!isEdit && (
            <div className="field">
              <label>Starting column</label>
              <select value={columnStatus} onChange={(e) => setColumnStatus(e.target.value)}>
                {COLUMN_OPTIONS.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
          )}

          {isEdit && (
            <>
              <div className="section-label">Prerequisites ({prereqTasks.length})</div>
              <div className="dep-list">
                {prereqTasks.length === 0 && <p className="empty-hint">No prerequisites — this task is ready as soon as it's created.</p>}
                {prereqTasks.map((p) => (
                  <div className="dep-row" key={p.id}>
                    <span>{p.title}</span>
                    <span className="dep-chip" style={{ marginLeft: 4 }}>
                      {p.column_status === "done" ? "✓ done" : p.column_status.replace("_", " ")}
                    </span>
                    <button type="button" className="remove" onClick={() => handleRemovePrereq(p.id)}>Remove</button>
                  </div>
                ))}
              </div>

              {eligiblePrereqOptions.length > 0 && (
                <div className="field-row" style={{ marginBottom: 14 }}>
                  <div className="field" style={{ marginBottom: 0 }}>
                    <select value={addPrereqId} onChange={(e) => setAddPrereqId(e.target.value)}>
                      <option value="">Add a prerequisite…</option>
                      {eligiblePrereqOptions.map((t) => (
                        <option key={t.id} value={t.id}>{t.title}</option>
                      ))}
                    </select>
                  </div>
                  <button type="button" className="btn" onClick={handleAddPrereq} disabled={!addPrereqId}>Add</button>
                </div>
              )}

              <div className="section-label" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span>AI-suggested prerequisites</span>
                <button type="button" className="btn" onClick={handleSuggest} disabled={suggestLoading}>
                  {suggestLoading ? "Thinking…" : "✨ Suggest"}
                </button>
              </div>
              {suggestions.length === 0 && !suggestLoading && (
                <p className="empty-hint">Ask Gemini to scan the other tasks in this workspace for likely prerequisites.</p>
              )}
              {suggestions.map((s) => (
                <div className="suggest-row" key={s.prerequisite_id}>
                  <div className="txt">
                    <div className="title">{s.prerequisite_title}</div>
                    <div className="rationale">{s.rationale} · {Math.round(s.confidence * 100)}% confidence</div>
                  </div>
                  <div className="suggest-actions">
                    <button type="button" className="icon-btn accept" title="Accept" onClick={() => acceptSuggestion(s)}>✓</button>
                    <button type="button" className="icon-btn reject" title="Dismiss" onClick={() => rejectSuggestion(s)}>✕</button>
                  </div>
                </div>
              ))}
            </>
          )}

          <div className="modal-actions">
            {isEdit ? (
              <button type="button" className="btn btn-danger" onClick={handleDelete} disabled={saving}>Delete task</button>
            ) : <span />}
            <div style={{ display: "flex", gap: 10 }}>
              <button type="button" className="btn" onClick={onClose}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? "Saving…" : isEdit ? "Save changes" : "Create task"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
