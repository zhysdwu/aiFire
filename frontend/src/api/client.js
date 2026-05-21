function readCookie(name) {
  const cookies = document.cookie ? document.cookie.split("; ") : [];
  for (const item of cookies) {
    const parts = item.split("=");
    const key = parts.shift();
    if (key === name) {
      return decodeURIComponent(parts.join("="));
    }
  }
  return "";
}

function csrfHeaders() {
  const csrfToken = readCookie("csrftoken");
  return {
    "Content-Type": "application/json",
    "X-CSRFToken": csrfToken,
  };
}

export async function fetchPhrases({ window = "24h", sort = "heat", q = "", page = 1 } = {}) {
  const params = new URLSearchParams({ window, sort, page: String(page) });
  if (q) params.set("q", q);
  const response = await fetch(`/api/phrases/?${params.toString()}`, { credentials: "same-origin" });
  if (!response.ok) throw new Error("获取关键词列表失败");
  return response.json();
}

export async function fetchPhraseDetail(id) {
  const response = await fetch(`/api/phrases/${id}/`, { credentials: "same-origin" });
  if (!response.ok) throw new Error("获取关键词详情失败");
  return response.json();
}

export async function fetchSessionInfo() {
  const response = await fetch(`/api/session-info/`, { credentials: "same-origin" });
  if (!response.ok) {
    return { is_authenticated: false, is_admin: false, username: "" };
  }
  return response.json();
}

export async function softDeletePhrase(id, reasonType) {
  const response = await fetch(`/api/phrases/${id}/soft-delete/`, {
    method: "POST",
    credentials: "same-origin",
    headers: csrfHeaders(),
    body: JSON.stringify({ reason_type: reasonType }),
  });
  if (!response.ok) {
    let message = "删除失败";
    try {
      const data = await response.json();
      message = data.detail || data.message || message;
    } catch {}
    throw new Error(message);
  }
  return response.json();
}

export async function sendTitleFeedback(id, feedback) {
  const response = await fetch(`/api/generated-titles/${id}/feedback/`, {
    method: "POST",
    credentials: "same-origin",
    headers: csrfHeaders(),
    body: JSON.stringify({ feedback }),
  });
  if (!response.ok) {
    let message = "提交反馈失败";
    try {
      const data = await response.json();
      message = data.detail || data.message || message;
    } catch {}
    throw new Error(message);
  }
  return response.json();
}

export function pickMetric(metrics, window = "24h") {
  if (!Array.isArray(metrics)) return null;
  return metrics.find((item) => item.window === window) || metrics[0] || null;
}
