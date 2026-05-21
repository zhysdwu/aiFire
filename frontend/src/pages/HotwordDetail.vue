<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { fetchPhraseDetail, pickMetric, sendTitleFeedback } from "../api/client";

const route = useRoute();
const detail = ref(null);
const loading = ref(false);
const error = ref("");
const copied = ref(false);

const feedbackForms = reactive({});
const feedbackLoading = reactive({});
const feedbackError = reactive({});

const riskLabelMap = {
  low: "低",
  medium: "中",
  high: "高",
  blocked: "已屏蔽",
};

const riskClassMap = {
  low: "risk-low",
  medium: "risk-medium",
  high: "risk-high",
  blocked: "risk-blocked",
};

const currentMetric = computed(() => pickMetric(detail.value?.metrics || [], "24h"));

const riskLabel = computed(() => {
  const value = detail.value?.risk_level;
  return riskLabelMap[value] || value || "-";
});

const riskClass = computed(() => {
  const value = detail.value?.risk_level;
  return riskClassMap[value] || "";
});

async function copyTitle(item) {
  await navigator.clipboard.writeText(`${item.title}\n${item.caption}`);
  copied.value = true;
  setTimeout(() => {
    copied.value = false;
  }, 1400);
}

async function optimizeWithFeedback(item) {
  const id = item.id;
  const feedback = (feedbackForms[id] || "").trim();
  if (feedback.length < 2) {
    feedbackError[id] = "请先输入更具体的反馈。";
    return;
  }

  feedbackLoading[id] = true;
  feedbackError[id] = "";

  try {
    const updated = await sendTitleFeedback(id, feedback);
    const target = detail.value.generated_titles.find((x) => x.id === id);
    if (target) {
      Object.assign(target, updated);
    }
    feedbackForms[id] = "";
  } catch (err) {
    feedbackError[id] = err.message || "优化失败";
  } finally {
    feedbackLoading[id] = false;
  }
}

onMounted(async () => {
  loading.value = true;
  error.value = "";
  try {
    detail.value = await fetchPhraseDetail(route.params.id);
    for (const item of detail.value.generated_titles || []) {
      feedbackForms[item.id] = "";
      feedbackLoading[item.id] = false;
      feedbackError[item.id] = "";
    }
  } catch (err) {
    error.value = err.message || "加载失败";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <main class="page">
    <section class="top-bar">
      <RouterLink to="/" class="back-link">← 返回榜单</RouterLink>
      <span class="copy-tip" :class="{ show: copied }">已复制到剪贴板</span>
    </section>

    <p v-if="loading" class="status">正在加载详情...</p>
    <p v-else-if="error" class="status status-error">{{ error }}</p>

    <section v-else-if="detail" class="detail-shell">
      <header class="headline">
        <h1>{{ detail.text }}</h1>
        <span class="risk-pill" :class="riskClass">风险等级：{{ riskLabel }}</span>
      </header>

      <article class="panel ai-panel" v-if="currentMetric">
        <h2>AI 分析摘要</h2>
        <p class="ai-explain">{{ currentMetric.score_explain || "暂无说明" }}</p>
        <div class="ai-metrics">
          <span>热度分：<strong>{{ currentMetric.heat_score }}</strong></span>
          <span>窗口增长：<strong>{{ currentMetric.growth_prev_window ?? "-" }}</strong></span>
          <span>对比7天：<strong>{{ currentMetric.growth_vs_7d_avg ?? "-" }}</strong></span>
        </div>
      </article>

      <div class="columns">
        <article class="panel">
          <h2>来源证据链接</h2>
          <ul class="evidence-list" v-if="detail.evidences?.length">
            <li v-for="evidence in detail.evidences" :key="evidence.url">
              <a :href="evidence.url" target="_blank" rel="noreferrer">
                {{ evidence.title || evidence.url }}
              </a>
            </li>
          </ul>
          <p v-else class="empty">暂无证据链接</p>
        </article>

        <article class="panel">
          <h2>推荐标题与文案</h2>
          <div v-if="detail.generated_titles?.length" class="title-list">
            <section v-for="(item, index) in detail.generated_titles" :key="`${item.id}-${index}`" class="title-card">
              <p class="title-text">{{ item.title }}</p>
              <p class="caption-text">{{ item.caption }}</p>
              <button type="button" class="copy-btn" @click="copyTitle(item)">复制标题和文案</button>

              <div class="feedback-box">
                <p class="feedback-title">AI 对话优化</p>
                <textarea
                  v-model="feedbackForms[item.id]"
                  placeholder="例如：语气更口语化，强调结果，控制在10个英文词以内"
                  rows="2"
                />
                <div class="feedback-actions">
                  <button type="button" class="optimize-btn" :disabled="feedbackLoading[item.id]" @click="optimizeWithFeedback(item)">
                    {{ feedbackLoading[item.id] ? "优化中..." : "根据反馈优化" }}
                  </button>
                  <span v-if="item.refined_count" class="refined-count">已优化 {{ item.refined_count }} 次</span>
                </div>
                <p v-if="item.ai_reply" class="ai-reply">AI：{{ item.ai_reply }}</p>
                <p v-if="feedbackError[item.id]" class="feedback-error">{{ feedbackError[item.id] }}</p>
              </div>
            </section>
          </div>
          <p v-else class="empty">暂无推荐标题</p>
        </article>
      </div>
    </section>
  </main>
</template>

<style scoped>
.page {
  width: min(1100px, 94vw);
  margin: 28px auto 48px;
  display: grid;
  gap: 16px;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #5f4d34;
  font-weight: 700;
}

.copy-tip {
  font-size: 13px;
  color: #195f48;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.copy-tip.show {
  opacity: 1;
}

.status {
  margin: 0;
  background: var(--bg-panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 22px;
  text-align: center;
  color: var(--ink-soft);
}

.status-error {
  color: var(--danger);
}

.detail-shell {
  display: grid;
  gap: 14px;
}

.headline {
  background: linear-gradient(135deg, #fff8ec 0%, #efe2ce 100%);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 20px;
  box-shadow: var(--shadow-soft);
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.headline h1 {
  margin: 0;
  font-size: clamp(28px, 4vw, 40px);
  font-weight: 800;
  color: #2d2213;
}

.risk-pill {
  padding: 7px 12px;
  border-radius: 999px;
  border: 1px solid #d4c2a7;
  background: #fffdf7;
  font-size: 13px;
  font-weight: 700;
}

.risk-low { color: #0c725d; }
.risk-medium { color: #8a5c09; }
.risk-high { color: #a63b2f; }
.risk-blocked { color: #7a2034; }

.panel {
  background: var(--bg-panel);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 16px;
  box-shadow: var(--shadow-soft);
}

.panel h2 {
  margin: 0 0 12px;
  font-size: 18px;
  font-weight: 800;
  color: #3e301c;
}

.ai-panel {
  border-color: #c7b08c;
  background: linear-gradient(135deg, #fffef9 0%, #f7efdf 100%);
}

.ai-explain {
  margin: 0;
  color: #5b4d39;
}

.ai-metrics {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: #4c3f2b;
  font-size: 14px;
}

.ai-metrics strong {
  color: #0b5e59;
}

.columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.evidence-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 10px;
}

.evidence-list a {
  color: #2e5d8e;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.title-list {
  display: grid;
  gap: 10px;
}

.title-card {
  border: 1px solid #d8c9b1;
  border-radius: 14px;
  background: linear-gradient(135deg, #fffef9 0%, #f7f0e4 100%);
  padding: 12px;
}

.title-text {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #2e2415;
}

.caption-text {
  margin: 7px 0 0;
  color: var(--ink-soft);
  font-size: 14px;
}

.copy-btn {
  margin-top: 10px;
  border: 1px solid #b89d7a;
  border-radius: 10px;
  background: #fff8eb;
  color: #5d4525;
  padding: 7px 10px;
  cursor: pointer;
  font-weight: 700;
}

.copy-btn:hover {
  border-color: var(--brand);
  color: var(--brand-strong);
}

.feedback-box {
  margin-top: 10px;
  border-top: 1px dashed #d8c9b1;
  padding-top: 10px;
}

.feedback-title {
  margin: 0 0 6px;
  font-weight: 700;
  color: #5a4630;
}

.feedback-box textarea {
  width: 100%;
  border-radius: 10px;
  border: 1px solid #cbbca4;
  background: #fffdf8;
  padding: 8px 10px;
  resize: vertical;
}

.feedback-actions {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.optimize-btn {
  border: 1px solid #0f6e66;
  border-radius: 10px;
  background: #0f766e;
  color: #fff;
  padding: 7px 10px;
  cursor: pointer;
}

.optimize-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}

.refined-count {
  color: #6a5a45;
  font-size: 13px;
}

.ai-reply {
  margin: 8px 0 0;
  color: #264f78;
  font-size: 13px;
}

.feedback-error {
  margin: 6px 0 0;
  color: #a63b2f;
  font-size: 13px;
}

.empty {
  margin: 0;
  color: var(--ink-soft);
}

@media (max-width: 900px) {
  .columns {
    grid-template-columns: 1fr;
  }
}
</style>
