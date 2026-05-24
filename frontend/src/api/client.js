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

export async function digitalHumanChat({ platform = "tiktok", phraseId = null, sessionId = "", question }) {
  const response = await fetch("/api/digital-human/chat/", {
    method: "POST",
    credentials: "same-origin",
    headers: csrfHeaders(),
    body: JSON.stringify({
      platform,
      phrase_id: phraseId,
      session_id: sessionId,
      question,
    }),
  });
  if (!response.ok) {
    let message = "数字人暂时不可用";
    try {
      const data = await response.json();
      message = data.detail || data.message || message;
    } catch {}
    throw new Error(message);
  }
  return response.json();
}

export async function fetchReviewPhrases() {
  const response = await fetch("/api/review/phrases/", { credentials: "same-origin" });
  if (!response.ok) {
    return { count: 0, results: [] };
  }
  return response.json();
}

export async function reviewPhraseAction(phraseIds, action) {
  const response = await fetch("/api/review/action/", {
    method: "POST",
    credentials: "same-origin",
    headers: csrfHeaders(),
    body: JSON.stringify({ phrase_ids: phraseIds, action }),
  });
  if (!response.ok) {
    let message = "操作失败";
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch {}
    throw new Error(message);
  }
  return response.json();
}

export function pickMetric(metrics, window = "24h") {
  if (!Array.isArray(metrics)) return null;
  return metrics.find((item) => item.window === window) || metrics[0] || null;
}

export async function fetchWorkflowConfig() {
  const response = await fetch("/api/workflow/config/", { credentials: "same-origin" });
  if (!response.ok) throw new Error("获取管道配置失败");
  return response.json();
}

export async function updateWorkflowConfig(config) {
  const response = await fetch("/api/workflow/config/", {
    method: "PATCH",
    credentials: "same-origin",
    headers: csrfHeaders(),
    body: JSON.stringify(config),
  });
  if (!response.ok) {
    let message = "更新管道配置失败";
    try {
      const data = await response.json();
      message = data.detail || data.message || message;
    } catch {}
    throw new Error(message);
  }
  return response.json();
}

export async function triggerWorkflowStep(platform, step) {
  const response = await fetch("/api/workflow/trigger/", {
    method: "POST",
    credentials: "same-origin",
    headers: csrfHeaders(),
    body: JSON.stringify({ platform, step }),
  });
  if (!response.ok) {
    let message = "触发步骤失败";
    try {
      const data = await response.json();
      message = data.detail || data.message || message;
    } catch {}
    throw new Error(message);
  }
  return response.json();
}

export async function fetchDigitalHumanVideoConfigs() {
  const response = await fetch("/api/digital-human/video-configs/", { credentials: "same-origin" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.message || payload.detail || "获取数字人视频配置失败");
  }
  return payload;
}

export async function generateDigitalHumanVideo({
  script,
  audioMode = "default",
  videoMode = "default",
  audioFile = null,
  videoFile = null,
  configId = null,
}) {
  const formData = new FormData();
  formData.set("script", script);
  formData.set("audio_mode", audioMode);
  formData.set("video_mode", videoMode);
  if (audioFile) formData.set("audio_file", audioFile);
  if (videoFile) formData.set("video_file", videoFile);
  if (configId !== null && configId !== undefined && configId !== "") {
    formData.set("config_id", String(configId));
  }

  const csrfToken = readCookie("csrftoken");
  const response = await fetch("/api/digital-human/videos/", {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-CSRFToken": csrfToken },
    body: formData,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.message || payload.detail || "数字人视频生成失败");
  }
  return payload;
}
