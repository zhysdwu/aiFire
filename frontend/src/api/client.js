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

export async function fetchPhrases({ window = "24h", sort = "heat", q = "", page = 1, platform = "tiktok" } = {}) {
  const params = new URLSearchParams({ window, sort, page: String(page), platform });
  if (q) params.set("q", q);
  const response = await fetch(`/api/phrases/?${params.toString()}`, { credentials: "same-origin" });
  if (!response.ok) throw new Error("获取关键词列表失败");
  return response.json();
}

export async function fetchPlatformSummary(platform = "tiktok") {
  const response = await fetch(`/api/summary/?platform=${encodeURIComponent(platform)}`, { credentials: "same-origin" });
  if (!response.ok) throw new Error("获取平台统计失败");
  return response.json();
}

export async function fetchAnalyticsOverview() {
  const response = await fetch("/api/analytics/overview/", { credentials: "same-origin" });
  if (!response.ok) throw new Error("获取跨平台分析失败");
  return response.json();
}

export async function fetchWorkflowStatus() {
  const response = await fetch("/api/workflow/status/", { credentials: "same-origin" });
  if (!response.ok) throw new Error("获取工作流状态失败");
  return response.json();
}

export async function fetchPhraseDetail(id) {
  const response = await fetch(`/api/phrases/${id}/`, { credentials: "same-origin" });
  if (!response.ok) throw new Error("获取关键词详情失败");
  return response.json();
}

export async function fetchSessionInfo() {
  const response = await fetch(`/api/session-info/`, { credentials: "same-origin", cache: "no-store" });
  if (!response.ok) {
    return { is_authenticated: false, is_admin: false, username: "" };
  }
  return response.json();
}

export async function fetchPhraseDeleteLogs() {
  const response = await fetch("/api/phrase-delete-logs/", { credentials: "same-origin", cache: "no-store" });
  if (!response.ok) {
    return { count: 0, results: [] };
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

export async function sendAssistantQuestion({ platform = "tiktok", phraseId = null, question }) {
  const response = await fetch("/api/assistant/chat/", {
    method: "POST",
    credentials: "same-origin",
    headers: csrfHeaders(),
    body: JSON.stringify({ platform, phrase_id: phraseId, question }),
  });
  if (!response.ok) {
    let message = "AI 助手暂时不可用";
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
