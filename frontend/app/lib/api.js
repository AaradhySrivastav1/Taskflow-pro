const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (_) {}
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  listTasks: () => request("/api/tasks"),
  createTask: (payload) => request("/api/tasks", { method: "POST", body: JSON.stringify(payload) }),
  updateTask: (id, payload) => request(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteTask: (id) => request(`/api/tasks/${id}`, { method: "DELETE" }),
  moveTask: (id, column_status, force = false) =>
    request(`/api/tasks/${id}/move`, { method: "POST", body: JSON.stringify({ column_status, force }) }),

  listDependencies: () => request("/api/dependencies"),
  addDependency: (prerequisite_id, dependent_id) =>
    request("/api/dependencies", { method: "POST", body: JSON.stringify({ prerequisite_id, dependent_id }) }),
  removeDependency: (edgeId) => request(`/api/dependencies/${edgeId}`, { method: "DELETE" }),

  suggestDependencies: (taskId) => request(`/api/ai/suggest/${taskId}`),
};
