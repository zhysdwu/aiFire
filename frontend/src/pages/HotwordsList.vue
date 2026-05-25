<script setup>
import { computed, nextTick, ref, watchEffect } from "vue";
import { RouterLink } from "vue-router";
import {
  fetchAnalyticsOverview,
  fetchPhrases,
  fetchPlatformSummary,
  fetchPhraseDeleteLogs,
  fetchSessionInfo,
  fetchWorkflowStatus,
  fetchWorkflowConfig,
  updateWorkflowConfig,
  triggerWorkflowStep,
  sendAssistantQuestion,
  softDeletePhrase,
} from "../api/client";
import { useRouter } from "vue-router";
import FloatingDigitalHuman from "../components/FloatingDigitalHuman.vue";

const props = defineProps({
  mode: {
    type: String,
    default: "public",
  },
});
const router = useRouter();

const windowValue = ref("24h");
const sortValue = ref("heat");
const platformValue = ref("tiktok");
const query = ref("");
const page = ref(1);
const pageSize = 50;

const items = ref([]);
const total = ref(0);
const summary = ref(null);
const analytics = ref(null);
const workflow = ref(null);
const deleteLogs = ref([]);
const sessionInfo = ref({ is_authenticated: false, is_admin: false, username: "" });
const sessionReady = ref(false);
const loading = ref(false);
const error = ref("");
const deleteModalVisible = ref(false);
const deleteTarget = ref(null);
const deleteReason = ref("");
const deleteError = ref("");
const deleteLoading = ref(false);
const reviewPhrases = ref([]);
const reviewLoading = ref(false);
const reviewActionLoading = ref({});

const assistantPhraseId = ref(null);
const assistantContextLabel = ref("");
const assistantQuestion = ref("请对当前平台的热词趋势做简要分析，并给出适合内容创作者的标题方向。");
const assistantAnswer = ref("");
const assistantIntent = ref("");
const assistantSuggestions = ref(["对比三个平台表现", "生成更适合短视频的标题"]);
const assistantLoading = ref(false);
const assistantError = ref("");
const assistantPanel = ref(null);
const pipelineConfig = ref({});
const pipelineTriggerLoading = ref({});
const pipelineStatusPollTimer = ref(null);

const windowLabelMap = {
  "24h": "近24小时",
  "7d": "近7天",
  "30d": "近30天",
};

const sortLabelMap = {
  heat: "热度优先",
  growth: "增长优先",
  new: "最新出现",
  ai: "AI综合评分",
};

const platformLabelMap = {
  tiktok: "TikTok",
  instagram: "Instagram",
  facebook: "Facebook",
  youtube: "YouTube",
};

const stepLabelMap = {
  fetch: "📡 抓取",
  extract: "🔍 提取",
  recommend: "✅ 推荐",
};

const deleteReasonOptions = [
  { value: "invalid", label: "无效字段" },
  { value: "duplicate", label: "重复字段" },
  { value: "illegal", label: "非法字段" },
];

const statusLabelMap = {
  pending: "等待中",
  running: "执行中",
  success: "已成功",
  failed: "已失败",
  skipped: "已跳过",
};

const intentLabelMap = {
  trend_analysis: "趋势分析",
  platform_compare: "平台对比",
  title_refine: "标题优化",
  general: "综合建议",
};

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));
const canPrev = computed(() => page.value > 1);
const canNext = computed(() => page.value < totalPages.value);
const analyticsRows = computed(() => analytics.value?.platforms || []);
const workflowRows = computed(() => workflow.value?.runs || []);
const deleteLogRows = computed(() => deleteLogs.value.slice(0, 8));
const isAdminView = computed(() => props.mode === "admin");
const canShowDeleteButton = computed(() => sessionReady.value && Boolean(sessionInfo.value?.is_admin));
const showAdminEntry = import.meta.env.VITE_SHOW_ADMIN_ENTRY === "true";
const adminEntryVisible = computed(
  () => showAdminEntry && !isAdminView.value && sessionReady.value && Boolean(sessionInfo.value?.is_admin)
);
const comparisonSummary = computed(() => {
  const comparison = analytics.value?.comparison || {};
  const highest = comparison.highest_heat_platform ? platformLabelMap[comparison.highest_heat_platform] : "-";
  const most = comparison.most_keywords_platform ? platformLabelMap[comparison.most_keywords_platform] : "-";
  return `当前平均热度领先平台：${highest}；关键词覆盖最多平台：${most}`;
});

async function loadPipelineConfig() {
  try {
    pipelineConfig.value = await fetchWorkflowConfig();
  } catch {
    // silent fail for non-admin
  }
}

async function togglePlatform(platform) {
  const cfg = { ...pipelineConfig.value };
  if (!cfg[platform]) cfg[platform] = { enabled: true, steps: { fetch: true, extract: true, recommend: true } };
  cfg[platform].enabled = !cfg[platform].enabled;
  try {
    pipelineConfig.value = await updateWorkflowConfig(cfg);
  } catch (err) {
    alert("更新配置失败：" + (err.message || "未知错误"));
  }
}

async function triggerStep(platform, step) {
  const key = platform + "_" + step;
  pipelineTriggerLoading.value[key] = true;
  try {
    await triggerWorkflowStep(platform, step);
  } catch (err) {
    alert("触发 " + step + " 失败：" + (err.message || "未知错误"));
  } finally {
    pipelineTriggerLoading.value[key] = false;
    startPollingWorkflow();
  }
}

async function runAllPlatforms() {
  const cfg = pipelineConfig.value;
  const platforms = Object.keys(cfg).filter((p) => cfg[p] && cfg[p].enabled);
  for (const platform of platforms) {
    const steps = cfg[platform].steps || {};
    if (steps.fetch !== false) await triggerStep(platform, "fetch");
    if (steps.extract !== false) await triggerStep(platform, "extract");
    if (steps.recommend !== false) await triggerStep(platform, "recommend");
  }
}

function startPollingWorkflow() {
  stopPollingWorkflow();
  pipelineStatusPollTimer.value = setInterval(async () => {
    try {
      workflow.value = await fetchWorkflowStatus();
    } catch {}
  }, 3000);
  setTimeout(stopPollingWorkflow, 120000);
}

function stopPollingWorkflow() {
  if (pipelineStatusPollTimer.value) {
    clearInterval(pipelineStatusPollTimer.value);
    pipelineStatusPollTimer.value = null;
  }
}

watchEffect(async () => {
  loading.value = true;
  error.value = "";
  sessionReady.value = false;
  try {
    loadPipelineConfig();
    const [phrasePayload, summaryPayload, analyticsPayload, workflowPayload, sessionPayload] = await Promise.all([
      fetchPhrases({
        window: windowValue.value,
        sort: sortValue.value,
        q: query.value,
        page: page.value,
        platform: platformValue.value,
      }),
      fetchPlatformSummary(platformValue.value),
      fetchAnalyticsOverview(),
      fetchWorkflowStatus(),
      fetchSessionInfo(),
    ]);
    items.value = phrasePayload.results || [];
    total.value = phrasePayload.count || 0;
    summary.value = summaryPayload;
    analytics.value = analyticsPayload;
    workflow.value = workflowPayload;
    sessionInfo.value = sessionPayload || { is_authenticated: false, is_admin: false, username: "" };
    sessionReady.value = true;
    if (isAdminView.value && !sessionInfo.value?.is_admin) {
      await router.replace("/");
      return;
    }
    if (isAdminView.value) {
      const logPayload = await fetchPhraseDeleteLogs();
      deleteLogs.value = logPayload.results || [];
    } else {
      deleteLogs.value = [];
    }
    if (page.value > totalPages.value) {
      page.value = totalPages.value;
    }
  } catch (err) {
    error.value = err.message || "加载失败";
  } finally {
    loading.value = false;
  }
});



function resetToFirstPage() {
  page.value = 1;
}

function goPrev() {
  if (canPrev.value) page.value -= 1;
}

function goNext() {
  if (canNext.value) page.value += 1;
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusText(value) {
  return statusLabelMap[value] || value || "-";
}

function statusClass(value) {
  return `status-pill status-${value || "pending"}`;
}

async function focusAssistantFor(item) {
  assistantPhraseId.value = item.id;
  assistantContextLabel.value = item.text;
  assistantQuestion.value = `请分析「${item.text}」为什么可能成为爆款词，并给我 3 个适合 ${platformLabelMap[platformValue.value]} 的标题方向。`;
  assistantAnswer.value = "";
  assistantError.value = "";
  await nextTick();
  assistantPanel.value?.scrollIntoView({ behavior: "smooth", block: "center" });
  await askAssistant(assistantQuestion.value);
}

function clearAssistantContext() {
  assistantPhraseId.value = null;
  assistantContextLabel.value = "";
}

async function askAssistant(questionOverride = "") {
  const questionText = (questionOverride || assistantQuestion.value).trim();
  if (!questionText) {
    assistantError.value = "请输入你想让 AI 分析的问题";
    return;
  }

  assistantQuestion.value = questionText;
  assistantLoading.value = true;
  assistantError.value = "";
  try {
    const payload = await sendAssistantQuestion({
      platform: platformValue.value,
      phraseId: assistantPhraseId.value,
      question: questionText,
    });
    assistantAnswer.value = payload.answer || "";
    assistantIntent.value = payload.intent || "";
    assistantSuggestions.value = payload.suggestions?.length ? payload.suggestions : assistantSuggestions.value;
  } catch (err) {
    assistantError.value = err.message || "AI 助手暂时不可用";
  } finally {
    assistantLoading.value = false;
  }
}

function askSuggestion(suggestion) {
  askAssistant(suggestion);
}

function openDeleteModal(item) {
  if (!canShowDeleteButton.value) return;
  deleteTarget.value = item;
  deleteReason.value = "";
  deleteError.value = "";
  deleteModalVisible.value = true;
}

function closeDeleteModal() {
  if (deleteLoading.value) return;
  deleteModalVisible.value = false;
  deleteTarget.value = null;
  deleteReason.value = "";
  deleteError.value = "";
}

async function confirmDelete() {
  if (!deleteTarget.value) return;
  if (!deleteReason.value) {
    deleteError.value = "请至少选择一个删除理由";
    return;
  }
  try {
    const session = await fetchSessionInfo();
    if (!session?.is_admin) {
      deleteError.value = "只有管理员才能删除关键词";
      return;
    }
  } catch {
    deleteError.value = "无法确认管理员身份，请刷新后重试";
    return;
  }
  deleteLoading.value = true;
  deleteError.value = "";
  try {
    await softDeletePhrase(deleteTarget.value.id, deleteReason.value);
    items.value = items.value.filter((it) => it.id !== deleteTarget.value.id);
    total.value = Math.max(0, total.value - 1);
    if (isAdminView.value) {
      const logPayload = await fetchPhraseDeleteLogs();
      deleteLogs.value = logPayload.results || [];
    }
    closeDeleteModal();
  } catch (err) {
    deleteError.value = err.message || "删除失败";
  } finally {
    deleteLoading.value = false;
  }
}
</script>

<template>
  <main class="page">
    <section class="hero">
      <p class="hero-kicker">AI Trend Studio</p>
      <h1>多平台热词洞察台</h1>
      <p class="hero-sub">按平台独立查看热词与推荐结果，支持 TikTok / Instagram / Facebook / YouTube。</p>
      <div class="hero-meta">
        <span>平台：{{ platformLabelMap[platformValue] }}</span>
        <span>时间：{{ windowLabelMap[windowValue] }}</span>
        <span>排序：{{ sortLabelMap[sortValue] }}</span>
        <span>共 {{ summary?.total_phrases ?? total }} 条</span>
      </div>
    </section>

    <section v-if="isAdminView || adminEntryVisible" class="mode-banner" :class="{ 'mode-banner-admin': isAdminView }">
      <div>
        <p class="mode-banner-kicker">{{ isAdminView ? "管理员页面" : "管理员入口" }}</p>
        <h2>{{ isAdminView ? "管理与审核同步视图" : "你当前具备管理员权限" }}</h2>
        <p>{{ isAdminView ? "这里与普通用户页面共享同一份热词数据，但额外开放逻辑删除与记录查看能力。" : "点击右侧入口可切换到管理视图，普通用户不会看到这些操作。" }}</p>
      </div>
      <RouterLink v-if="adminEntryVisible" to="/manage" class="mode-banner-link">进入管理员视图</RouterLink>
      <RouterLink v-else to="/" class="mode-banner-link">返回普通视图</RouterLink>
    </section>

    <section v-if="isAdminView" class="audit-panel">
      <div class="audit-head">
        <div>
          <p class="section-kicker">审核记录</p>
          <h2>关键词删除记录</h2>
        </div>
        <span>{{ deleteLogs.length }} 条</span>
      </div>
      <div v-if="deleteLogRows.length" class="audit-list">
        <article v-for="item in deleteLogRows" :key="item.id" class="audit-item">
          <div>
            <strong>{{ item.phrase_text }}</strong>
            <p>{{ item.reason_label || item.reason_type }} <span v-if="item.reason_text">· {{ item.reason_text }}</span></p>
          </div>
          <div class="audit-meta">
            <span>{{ item.operator_username || "管理员" }}</span>
            <span>{{ formatDateTime(item.created_at) }}</span>
          </div>
        </article>
      </div>
      <p v-else class="audit-empty">暂无删除记录</p>
    </section>



    <section class="filter-panel">
      <label>
        平台
        <select v-model="platformValue" @change="resetToFirstPage">
          <option value="tiktok">TikTok</option>
          <option value="instagram">Instagram</option>
          <option value="facebook">Facebook</option>
          <option value="youtube">YouTube</option>
        </select>
      </label>

      <label>
        时间窗口
        <select v-model="windowValue" @change="resetToFirstPage">
          <option value="24h">近24小时</option>
          <option value="7d">近7天</option>
          <option value="30d">近30天</option>
        </select>
      </label>

      <label>
        排序方式
        <select v-model="sortValue" @change="resetToFirstPage">
          <option value="heat">热度优先</option>
          <option value="growth">增长优先</option>
          <option value="new">最新出现</option>
          <option value="ai">AI综合评分</option>
        </select>
      </label>

      <label class="search-box">
        关键词搜索
        <input v-model="query" placeholder="例如：quiet luxury" @input="resetToFirstPage" />
      </label>
    </section>

    <section class="summary-panel" v-if="summary">
      <div class="summary-card">
        <div>关键词总数</div>
        <strong>{{ summary.total_phrases }}</strong>
      </div>
      <div class="summary-card">
        <div>平均热度</div>
        <strong>{{ summary.avg_heat_score }}</strong>
      </div>
      <div class="summary-card">
        <div>最近更新</div>
        <strong>{{ summary.last_updated_at ? formatDateTime(summary.last_updated_at) : "-" }}</strong>
      </div>
    </section>

    <section class="intelligence-board">
      <article class="board-card board-card-wide">
        <div class="board-heading">
          <div>
            <p class="section-kicker">跨平台分析</p>
            <h2>社媒热词对比</h2>
          </div>
          <span class="board-note">{{ comparisonSummary }}</span>
        </div>

        <div class="platform-rows">
          <div v-for="row in analyticsRows" :key="row.platform" class="platform-row">
            <div class="platform-row-head">
              <strong>{{ platformLabelMap[row.platform] }}</strong>
              <span>{{ row.total_phrases }} 个关键词</span>
            </div>
            <div class="heat-track" aria-label="平均热度">
              <span :style="{ width: `${Math.min(row.avg_heat_score || 0, 100)}%` }"></span>
            </div>
            <div class="row-meta">
              <span>平均热度 {{ row.avg_heat_score }}</span>
              <span>更新 {{ formatDateTime(row.last_updated_at) }}</span>
            </div>
            <div class="keyword-chips">
              <span v-for="keyword in row.top_keywords" :key="keyword">{{ keyword }}</span>
              <span v-if="!row.top_keywords?.length">暂无高频词</span>
            </div>
          </div>
        </div>
      </article>

      <article class="board-card">
        <div class="board-heading compact">
          <div>
            <p class="section-kicker">每日工作流</p>
            <h2>采集与推荐状态</h2>
          </div>
          <span class="date-badge">{{ workflow?.date || "-" }}</span>
        </div>

        <div class="workflow-list">
          <div v-for="run in workflowRows" :key="run.platform" class="workflow-item">
            <div class="workflow-top">
              <strong>{{ platformLabelMap[run.platform] }}</strong>
              <small>{{ formatDateTime(run.updated_at) }}</small>
            </div>
            <div class="workflow-steps">
              <span :class="statusClass(run.fetch_status)">采集 {{ statusText(run.fetch_status) }}</span>
              <span :class="statusClass(run.extract_status)">提取 {{ statusText(run.extract_status) }}</span>
              <span :class="statusClass(run.recommend_status)">推荐 {{ statusText(run.recommend_status) }}</span>
            </div>
            <p v-if="run.last_message">{{ run.last_message }}</p>
          </div>
        </div>
      </article>

      <article ref="assistantPanel" class="board-card assistant-card">
        <div class="assistant-header">
          <div class="assistant-avatar">AI</div>
          <div>
            <p class="section-kicker">Skills 数字人</p>
            <h2>趋势分析助手</h2>
          </div>
        </div>
        <div class="assistant-context">
          <span>当前平台：{{ platformLabelMap[platformValue] }}</span>
          <button v-if="assistantContextLabel" type="button" @click="clearAssistantContext">
            正在分析：{{ assistantContextLabel }} ×
          </button>
        </div>
        <textarea
          v-model="assistantQuestion"
          rows="4"
          placeholder="例如：请比较三个平台今天更适合做内容标题的方向"
        ></textarea>
        <div class="assistant-actions">
          <button type="button" :disabled="assistantLoading" @click="askAssistant()">
            {{ assistantLoading ? "分析中..." : "发送给 AI" }}
          </button>
        </div>
        <p v-if="assistantError" class="assistant-error">{{ assistantError }}</p>
        <div v-if="assistantAnswer" class="assistant-answer">
          <span v-if="assistantIntent">{{ intentLabelMap[assistantIntent] || assistantIntent }}</span>
          <p>{{ assistantAnswer }}</p>
        </div>
        <div class="assistant-suggestions">
          <button v-for="suggestion in assistantSuggestions" :key="suggestion" type="button" @click="askSuggestion(suggestion)">
            {{ suggestion }}
          </button>
        </div>
      </article>
    </section>

    <section class="content-panel">
      <p v-if="loading" class="status">正在加载最新数据...</p>
      <p v-else-if="error" class="status status-error">{{ error }}</p>
      <p v-else-if="items.length === 0" class="status">暂无数据，请先执行抓取任务。</p>

      <template v-else>
        <ul class="trend-grid">
          <li v-for="(item, index) in items" :key="item.id" class="trend-card">
            <div class="rank">#{{ (page - 1) * pageSize + index + 1 }}</div>
            <div class="card-main">
              <RouterLink :to="`/hotwords/${item.id}`" class="word-link">{{ item.text }}</RouterLink>
              <div class="score-row">
                <span class="score-label">热度分</span>
                <strong>{{ item.metric?.heat_score ?? "-" }}</strong>
              </div>
              <p class="ai-line" v-if="item.metric?.score_explain">AI分析：{{ item.metric.score_explain }}</p>
            </div>
            <div class="card-actions">
              <button type="button" class="ask-link" @click="focusAssistantFor(item)">问AI</button>
              <RouterLink :to="`/hotwords/${item.id}`" class="detail-link">查看详情</RouterLink>
              <button v-if="canShowDeleteButton && item.can_delete" type="button" class="delete-link" @click="openDeleteModal(item)">删除</button>
            </div>
          </li>
        </ul>

        <div class="pager">
          <button :disabled="!canPrev" @click="goPrev">上一页</button>
          <span>第 {{ page }} / {{ totalPages }} 页</span>
          <button :disabled="!canNext" @click="goNext">下一页</button>
        </div>
      </template>
    </section>

    <section v-if="canShowDeleteButton && deleteModalVisible" class="modal-mask" @click.self="closeDeleteModal">
      <div class="modal-card">
        <h3>逻辑删除关键词</h3>
        <p class="modal-target">{{ deleteTarget?.text }}</p>
        <label class="modal-label">
          删除理由
          <select v-model="deleteReason">
            <option value="">请选择</option>
            <option v-for="item in deleteReasonOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
        </label>
        <p v-if="deleteError" class="modal-error">{{ deleteError }}</p>
        <div class="modal-actions">
          <button type="button" class="btn-cancel" :disabled="deleteLoading" @click="closeDeleteModal">取消</button>
          <button type="button" class="btn-confirm" :disabled="deleteLoading" @click="confirmDelete">
            {{ deleteLoading ? "删除中..." : "确认删除" }}
          </button>
        </div>
      </div>
    </section>
  </main>

    <FloatingDigitalHuman :platform="platformValue" />
</template>

<style scoped>
.page {
  width: min(1160px, 94vw);
  margin: 24px auto 40px;
  display: grid;
  gap: 16px;
}
.hero {
  background: linear-gradient(135deg, #0d3b39 0%, #15514d 56%, #1f6a64 100%);
  border: 1px solid rgba(17, 78, 73, 0.7);
  border-radius: 8px;
  padding: 24px;
  color: #f3fbfa;
  box-shadow: 0 12px 28px rgba(8, 47, 43, 0.18);
}
.hero-kicker { margin: 0; font-size: 12px; color: #9adbd3; font-weight: 700; }
.hero h1 { margin: 8px 0 6px; font-size: clamp(28px, 4vw, 38px); color: #ffffff; }
.hero-sub { margin: 0; color: rgba(243, 251, 250, 0.88); }
.hero-meta { margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap; }
.hero-meta span { border: 1px solid rgba(181, 228, 223, 0.5); border-radius: 999px; padding: 6px 10px; background: rgba(245, 254, 253, 0.1); color: #eaf9f7; }
.hero-link { border: 1px solid #9adbd3; border-radius: 999px; padding: 6px 12px; background: rgba(233, 251, 248, 0.14); color: #f3fbfa; font-weight: 700; }
.mode-banner { display: flex; justify-content: space-between; align-items: center; gap: 14px; border: 1px solid #d8dde7; border-radius: 8px; background: #ffffff; box-shadow: 0 8px 22px rgba(19, 33, 68, 0.08); padding: 16px 18px; }
.mode-banner-admin { background: linear-gradient(135deg, #123a34 0%, #1d544d 100%); color: #f8fdfc; border-color: #1b6158; }
.mode-banner-kicker { margin: 0 0 4px; font-size: 12px; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; color: #1f8f84; }
.mode-banner-admin .mode-banner-kicker { color: #a6ece4; }
.mode-banner h2 { margin: 0; font-size: 18px; }
.mode-banner p { margin: 6px 0 0; color: #5f6b7a; }
.mode-banner-admin p { color: rgba(240, 255, 252, 0.85); }
.mode-banner-link { flex: none; border-radius: 6px; border: 1px solid #80d4c9; background: #e9fbf8; color: #0f7067; padding: 9px 12px; font-weight: 700; white-space: nowrap; }
.audit-panel { border: 1px solid #d8dde7; border-radius: 8px; background: #ffffff; padding: 16px; box-shadow: 0 8px 22px rgba(19, 33, 68, 0.08); }
.audit-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }
.audit-head h2 { margin: 0; font-size: 20px; }
.audit-head span { border: 1px solid #cfe7e4; border-radius: 999px; background: #f2fbfa; color: #206f67; padding: 5px 10px; font-size: 12px; font-weight: 700; }
.audit-list { display: grid; gap: 8px; }
.audit-item { display: flex; justify-content: space-between; align-items: center; gap: 12px; border: 1px solid #e2e8f0; border-radius: 8px; background: #fbfdff; padding: 10px 12px; }
.audit-item strong { display: block; color: #111827; }
.audit-item p { margin: 4px 0 0; color: #5f6b7a; font-size: 13px; }
.audit-meta { display: grid; justify-items: end; gap: 4px; color: #6f7a87; font-size: 12px; white-space: nowrap; }
.audit-empty { margin: 0; color: #6f7a87; }
.filter-panel { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; background: #ffffff; border: 1px solid #d8dde7; border-radius: 8px; padding: 14px; box-shadow: 0 8px 20px rgba(24, 39, 75, 0.07); }
label { display: grid; gap: 6px; font-size: 13px; color: #5f6b7a; }
select, input, textarea { width: 100%; border-radius: 6px; border: 1px solid #cdd6e1; background: #ffffff; padding: 10px 12px; transition: border-color .2s ease, box-shadow .2s ease; }
select:focus, input:focus, textarea:focus { outline: none; border-color: #44bfb1; box-shadow: 0 0 0 3px rgba(68, 191, 177, 0.2); }
textarea { resize: vertical; color: #101826; }
.summary-panel { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.summary-card { border: 1px solid #d8dde7; border-radius: 8px; background: #ffffff; padding: 12px; box-shadow: 0 8px 20px rgba(24, 39, 75, 0.06); }
.summary-card div { color: #6a7585; }
.summary-card strong { display: block; margin-top: 6px; font-size: 20px; }
.intelligence-board { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(320px, .95fr); gap: 14px; align-items: stretch; }
.board-card { border: 1px solid #d8dde7; border-radius: 8px; background: #ffffff; box-shadow: 0 8px 22px rgba(24, 39, 75, 0.08); padding: 16px; }
.board-card-wide { grid-row: span 2; background: linear-gradient(140deg, #ffffff 0%, #f5fcfb 100%); }
.board-heading { display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; margin-bottom: 14px; }
.board-heading.compact { align-items: center; }
.section-kicker { margin: 0 0 4px; color: #259e92; font-size: 12px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
.board-card h2 { margin: 0; font-size: 20px; color: #0f172a; }
.board-note, .date-badge { border: 1px solid #d6e6e3; border-radius: 999px; color: #2e6e67; background: #f4fbfa; padding: 6px 10px; font-size: 12px; }
.platform-rows { display: grid; gap: 12px; }
.platform-row { border: 1px solid #e4eaf2; border-radius: 8px; background: #fbfdff; padding: 12px; }
.platform-row-head, .row-meta, .workflow-top { display: flex; justify-content: space-between; gap: 10px; align-items: center; }
.platform-row-head span, .row-meta, .workflow-top small { color: #6f7a87; font-size: 12px; }
.heat-track { height: 8px; overflow: hidden; border-radius: 999px; background: #e5edf5; margin: 10px 0 7px; }
.heat-track span { display: block; height: 100%; min-width: 8px; border-radius: inherit; background: linear-gradient(90deg, #30bfae, #2d98c6); }
.keyword-chips { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 10px; }
.keyword-chips span { border-radius: 999px; background: #f0f5fb; color: #36516d; padding: 5px 9px; font-size: 12px; border: 1px solid #deebf8; }
.workflow-list { display: grid; gap: 10px; }
.workflow-item { border: 1px solid #e3eaf2; border-radius: 8px; background: #fbfdff; padding: 11px; }
.workflow-item p { margin: 8px 0 0; color: #6f7a87; font-size: 12px; }
.workflow-steps { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.status-pill { border-radius: 999px; border: 1px solid #d8e2ec; padding: 4px 8px; font-size: 12px; background: #f6f9fc; color: #4e5b6b; }
.status-running { border-color: #7fb7af; background: #e2f4f1; color: #0b5e59; }
.status-success { border-color: #91be9b; background: #e8f5ea; color: #2e6d3a; }
.status-failed { border-color: #d8a29a; background: #fff0ed; color: #9a3228; }
.status-skipped { border-color: #c9c1b5; background: #f3f0eb; color: #776b5c; }
.assistant-card { background: linear-gradient(160deg, #123b38 0%, #0c2b29 100%); color: #f4fcfb; }
.assistant-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.assistant-avatar { width: 44px; height: 44px; border-radius: 8px; display: grid; place-items: center; background: linear-gradient(135deg, #f6b86d, #79d8cd); color: #14312e; font-weight: 900; box-shadow: 0 12px 28px rgba(0,0,0,.22); }
.assistant-card .section-kicker { color: #8ee0d6; }
.assistant-card h2 { color: #fff8e8; }
.assistant-context { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.assistant-context span, .assistant-context button { border: 1px solid rgba(255,255,255,.22); border-radius: 999px; background: rgba(255,255,255,.08); color: #f9f1df; padding: 6px 9px; font-size: 12px; }
.assistant-context button { cursor: pointer; }
.assistant-card textarea { border-color: rgba(255,255,255,.25); background: rgba(255,255,255,.92); }
.assistant-actions { display: flex; justify-content: flex-end; margin-top: 10px; }
.assistant-actions button, .assistant-suggestions button, .ask-link { border: 1px solid #7bcfc4; border-radius: 6px; background: #e8fffb; color: #0d5d57; padding: 8px 12px; font-weight: 700; cursor: pointer; }
.assistant-actions button:disabled { opacity: .62; cursor: wait; }
.assistant-error { margin: 10px 0 0; color: #ffd2ca; }
.assistant-answer { border: 1px solid rgba(255,255,255,.18); border-radius: 8px; background: rgba(255,255,255,.08); margin-top: 12px; padding: 12px; }
.assistant-answer span { display: inline-block; margin-bottom: 6px; color: #9be5dc; font-size: 12px; font-weight: 800; }
.assistant-answer p { margin: 0; }
.assistant-suggestions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.assistant-suggestions button { background: rgba(255,255,255,.1); color: #f9f1df; border-color: rgba(255,255,255,.22); padding: 6px 9px; font-size: 12px; }
.content-panel { background: #ffffff; border: 1px solid #d8dde7; border-radius: 8px; padding: 16px; box-shadow: 0 8px 22px rgba(24, 39, 75, 0.08); }
.status { margin: 0; padding: 20px 10px; color: #6f7a87; text-align: center; }
.status-error { color: var(--danger); }
.trend-grid { margin: 0; padding: 0; list-style: none; display: grid; gap: 12px; }
.trend-card { border: 1px solid #e0e7f0; border-radius: 8px; background: #ffffff; padding: 14px; display: grid; grid-template-columns: auto 1fr auto; gap: 12px; transition: box-shadow .2s ease, border-color .2s ease, transform .2s ease; }
.trend-card:hover { border-color: #b9d5ec; box-shadow: 0 10px 26px rgba(27, 50, 90, 0.1); transform: translateY(-1px); }
.rank { width: 42px; height: 42px; border-radius: 8px; display: grid; place-items: center; background: #f0f6fb; color: #2c5b80; font-weight: 700; border: 1px solid #dce9f4; }
.word-link { font-size: clamp(18px, 2vw, 23px); font-weight: 800; color: #152033; }
.score-row { margin-top: 4px; display: inline-flex; gap: 8px; align-items: baseline; }
.score-label { color: #6f7a87; font-size: 13px; }
.ai-line { margin: 8px 0 0; color: #4f6278; font-size: 13px; line-height: 1.45; }
.card-actions { display: flex; flex-direction: column; gap: 8px; }
.ask-link, .detail-link, .delete-link { border-radius: 6px; border: 1px solid #cad6e4; padding: 8px 12px; text-align: center; font-weight: 600; min-width: 112px; }
.detail-link { background: #f7f9fc; color: #2f445f; }
.ask-link { background: #e8fffb; border-color: #7bcfc4; color: #0d5d57; }
.delete-link { border-color: #d4b4ad; background: #fff3f0; color: #8f2d21; cursor: pointer; }
.pager { margin-top: 14px; display: flex; justify-content: center; align-items: center; gap: 12px; }
.pager button { border-radius: 6px; border: 1px solid #cad6e4; background: #f7f9fc; padding: 7px 12px; cursor: pointer; color: #2f445f; }
.pager button:disabled { opacity: 0.45; cursor: not-allowed; }
.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,.35); display: grid; place-items: center; z-index: 30; }
.modal-card { width: min(420px, 92vw); background: #ffffff; border: 1px solid #d8dde7; border-radius: 8px; padding: 16px; }
.modal-target { margin: 0 0 10px; color: #314963; font-weight: 700; }
.modal-error { margin: 8px 0 0; color: #a63b2f; }
.modal-actions { margin-top: 12px; display: flex; justify-content: flex-end; gap: 8px; }
.btn-cancel, .btn-confirm { border-radius: 6px; padding: 7px 12px; border: 1px solid #cad6e4; cursor: pointer; }
.btn-cancel { background: #f7f9fc; color: #2f445f; }
.btn-confirm { background: #8f2d21; border-color: #8f2d21; color: #fff; }
.workflow-panel { background: linear-gradient(160deg, #1a2e2b 0%, #142120 100%); color: #f9f1df; }
.workflow-panel .board-heading { margin-bottom: 10px; }
.workflow-panel .board-heading h2 { color: #fff8e8; }
.workflow-panel .board-heading .section-kicker { color: #8bc4bb; }
.workflow-panel .status { color: #b0a897; }
.btn-run-all { border: 1px solid #7bcfc4; border-radius: 10px; background: #e8fffb; color: #0d5d57; padding: 7px 12px; font-weight: 700; cursor: pointer; font-size: 13px; }
.btn-run-all:hover { background: #c8f7ef; }
.workflow-platforms { display: grid; gap: 10px; }
.workflow-platform-row { border: 1px solid rgba(255,255,255,.14); border-radius: 12px; padding: 10px; background: rgba(255,255,255,.05); }
.workflow-platform-row.platform-disabled { opacity: .45; }
.platform-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.platform-name { font-weight: 800; font-size: 14px; }
.platform-toggle { display: flex; align-items: center; gap: 5px; cursor: pointer; font-size: 12px; }
.platform-toggle input { width: auto; margin: 0; }
.toggle-label { color: #8bc4bb; user-select: none; }
.step-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.step-card { border: 1px solid rgba(255,255,255,.12); border-radius: 10px; padding: 8px 10px; display: flex; flex-direction: column; gap: 4px; background: rgba(255,255,255,.04); }
.step-card.step-success { border-color: rgba(129,199,132,.6); }
.step-card.step-running { border-color: rgba(100,181,246,.6); animation: pulse-border 1s infinite; }
.step-card.step-failed { border-color: rgba(229,115,115,.6); }
.step-icon { font-size: 16px; font-weight: 900; }
.step-success .step-icon { color: #81c784; }
.step-running .step-icon { color: #64b5f6; }
.step-failed .step-icon { color: #e57373; }
.step-skipped .step-icon { color: #9e9e9e; }
.step-body { display: flex; flex-direction: column; }
.step-label { font-size: 12px; color: #b0a897; }
.step-status { font-size: 11px; font-weight: 700; }
.step-success .step-status { color: #a5d6a7; }
.step-running .step-status { color: #90caf9; }
.step-failed .step-status { color: #ef9a9a; }
.step-skipped .step-status { color: #9e9e9e; }
.btn-step-trigger { margin-top: 4px; border: 1px solid rgba(255,255,255,.2); border-radius: 6px; background: rgba(255,255,255,.08); color: #c8e6c9; padding: 3px 6px; font-size: 11px; cursor: pointer; }
.btn-step-trigger:hover { background: rgba(255,255,255,.16); }
.btn-step-trigger:disabled { opacity: .5; cursor: wait; }
@keyframes pulse-border {
  0%, 100% { border-color: rgba(100,181,246,.6); }
  50% { border-color: rgba(100,181,246,.25); }
}


@media (max-width: 860px) {
  .filter-panel, .summary-panel, .intelligence-board { grid-template-columns: 1fr; }
  .board-card-wide { grid-row: auto; }
  .trend-card { grid-template-columns: 1fr; }
  .card-actions { flex-direction: row; flex-wrap: wrap; }
  .board-heading { flex-direction: column; }
}
</style>
