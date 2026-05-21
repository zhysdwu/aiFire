<script setup>
import { computed, ref, watchEffect } from "vue";
import { RouterLink } from "vue-router";
import { fetchPhrases, fetchSessionInfo, softDeletePhrase } from "../api/client";

const windowValue = ref("24h");
const sortValue = ref("heat");
const query = ref("");
const page = ref(1);
const pageSize = 50;

const items = ref([]);
const total = ref(0);
const loading = ref(false);
const error = ref("");
const isAdmin = ref(false);

const deleteModalVisible = ref(false);
const deleteTarget = ref(null);
const deleteReason = ref("");
const deleteError = ref("");
const deleteLoading = ref(false);

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

const deleteReasonOptions = [
  { value: "invalid", label: "无效字段" },
  { value: "duplicate", label: "重复字段" },
  { value: "illegal", label: "非法字段" },
];

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));
const canPrev = computed(() => page.value > 1);
const canNext = computed(() => page.value < totalPages.value);

const headerMeta = computed(() => ({
  windowText: windowLabelMap[windowValue.value],
  sortText: sortLabelMap[sortValue.value],
}));

fetchSessionInfo().then((info) => {
  isAdmin.value = !!info?.is_admin;
});

watchEffect(async () => {
  loading.value = true;
  error.value = "";
  try {
    const payload = await fetchPhrases({
      window: windowValue.value,
      sort: sortValue.value,
      q: query.value,
      page: page.value,
    });
    items.value = payload.results || [];
    total.value = payload.count || 0;
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

function openDeleteModal(item) {
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
  deleteLoading.value = true;
  deleteError.value = "";
  try {
    await softDeletePhrase(deleteTarget.value.id, deleteReason.value);
    items.value = items.value.filter((it) => it.id !== deleteTarget.value.id);
    total.value = Math.max(0, total.value - 1);
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
      <h1>关键词热榜洞察台</h1>
      <p class="hero-sub">
        聚焦 TikTok 美国热词，结合 AI 评分与趋势变化，帮你快速定位可执行的内容机会。
      </p>
      <div class="hero-meta">
        <span>{{ headerMeta.windowText }}</span>
        <span>{{ headerMeta.sortText }}</span>
        <span>共 {{ total }} 条</span>
      </div>
    </section>

    <section class="filter-panel">
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
              <RouterLink :to="`/hotwords/${item.id}`" class="detail-link" >查看详情</RouterLink>
              <div></div>
              <button
                v-if="isAdmin"
                type="button"
                class="delete-link"
                @click="openDeleteModal(item)"
              >
                删除
              </button>
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

    <section v-if="deleteModalVisible" class="modal-mask" @click.self="closeDeleteModal">
      <div class="modal-card">
        <h3>逻辑删除关键词</h3>
        <p class="modal-target">{{ deleteTarget?.text }}</p>
        <label class="modal-label">
          删除理由
          <select v-model="deleteReason">
            <option value="">请选择</option>
            <option v-for="item in deleteReasonOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </option>
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
</template>

<style scoped>
.page {
  width: min(1100px, 94vw);
  margin: 32px auto 48px;
  display: grid;
  gap: 20px;
}

.hero {
  background: linear-gradient(130deg, #fff8ec 0%, #f2e9d7 60%, #e8dfcd 100%);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 28px 28px 24px;
  box-shadow: var(--shadow-soft);
}

.hero-kicker {
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 12px;
  color: var(--brand);
  font-weight: 700;
}

.hero h1 {
  margin: 10px 0 8px;
  font-size: clamp(28px, 4vw, 42px);
  line-height: 1.15;
  font-weight: 800;
}

.hero-sub {
  margin: 0;
  color: var(--ink-soft);
  max-width: 720px;
}

.hero-meta {
  margin-top: 14px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.hero-meta span {
  border: 1px solid #cdbb9f;
  border-radius: 999px;
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.65);
  color: #5a4a35;
  font-size: 13px;
}

.filter-panel {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  background: var(--bg-panel);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 14px;
  box-shadow: var(--shadow-soft);
}

label {
  display: grid;
  gap: 6px;
  font-size: 13px;
  color: var(--ink-soft);
}

select,
input {
  width: 100%;
  border-radius: 12px;
  border: 1px solid #ccbea8;
  background: #fffef9;
  padding: 10px 12px;
  color: var(--ink-strong);
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

select:focus,
input:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.16);
}

.content-panel {
  background: var(--bg-panel);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 16px;
  box-shadow: var(--shadow-soft);
}

.status {
  margin: 0;
  padding: 20px 10px;
  color: var(--ink-soft);
  text-align: center;
}

.status-error {
  color: var(--danger);
}

.trend-grid {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 12px;
}

.trend-card {
  border: 1px solid #d8c9b1;
  border-radius: 16px;
  background: linear-gradient(135deg, #fffef9 0%, #f8f2e7 100%);
  padding: 14px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 12px;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.trend-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-strong);
}

.rank {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: #efe3cf;
  color: #7a5d38;
  font-weight: 700;
}

.card-main {
  min-width: 0;
}

.word-link {
  font-size: clamp(18px, 2vw, 24px);
  font-weight: 800;
  color: #2d2417;
  word-break: break-word;
}

.score-row {
  margin-top: 4px;
  display: inline-flex;
  gap: 8px;
  align-items: baseline;
}

.score-label {
  color: var(--ink-soft);
  font-size: 13px;
}

.score-row strong {
  color: var(--brand-strong);
  font-size: 18px;
}

.ai-line {
  margin: 8px 0 0;
  color: #5f543f;
  font-size: 13px;
}

.card-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-link {
  text-align: center;
  gap: 4px;
  border-radius: 10px;
  border: 1px solid #c5b295;
  padding: 8px 12px;
  color: #5e4a2d;
  white-space: nowrap;
  font-weight: 600;
  background: #fff7e8;
}

.detail-link:hover {
  border-color: var(--brand);
  color: var(--brand-strong);
}

.delete-link {
  border-radius: 10px;
  border: 1px solid #d4b4ad;
  background: #fff3f0;
  color: #8f2d21;
  padding: 8px 12px;
  cursor: pointer;
  font-weight: 600;
}

.delete-link:hover {
  border-color: #b94b3f;
}

.pager {
  margin-top: 14px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
}

.pager button {
  border-radius: 10px;
  border: 1px solid #c5b295;
  background: #fff7e8;
  color: #5e4a2d;
  padding: 7px 12px;
  cursor: pointer;
}

.pager button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: grid;
  place-items: center;
  z-index: 30;
}

.modal-card {
  width: min(420px, 92vw);
  background: #fffef9;
  border: 1px solid #d8c9b1;
  border-radius: 14px;
  padding: 16px;
}

.modal-card h3 {
  margin: 0 0 8px;
}

.modal-target {
  margin: 0 0 10px;
  color: #5f4d34;
  font-weight: 700;
}

.modal-label {
  display: grid;
  gap: 6px;
}

.modal-error {
  margin: 8px 0 0;
  color: #a63b2f;
}

.modal-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn-cancel,
.btn-confirm {
  border-radius: 10px;
  padding: 7px 12px;
  border: 1px solid #c5b295;
  cursor: pointer;
}

.btn-cancel {
  background: #fff7e8;
  color: #5e4a2d;
}

.btn-confirm {
  background: #8f2d21;
  border-color: #8f2d21;
  color: #fff;
}

@media (max-width: 860px) {
  .filter-panel {
    grid-template-columns: 1fr;
  }

  .trend-card {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .rank {
    width: 36px;
    height: 36px;
  }

  .detail-link {
    justify-self: start;
  }
}
</style>
