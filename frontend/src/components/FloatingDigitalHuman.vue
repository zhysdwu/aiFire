<script setup>
import { computed, ref, watch } from "vue";
import { digitalHumanChat } from "../api/client";

const props = defineProps({
  platform: {
    type: String,
    default: "tiktok",
  },
});

const panelOpen = ref(false);
const loading = ref(false);
const error = ref("");
const question = ref("请总结当前平台最值得跟进的热词方向。");
const answer = ref("");
const highlights = ref([]);
const livetalking = ref(null);
const traceId = ref("");

const volume = ref(0.8);
const speaking = ref(false);
const ttsSupported = ref(typeof window !== "undefined" && "speechSynthesis" in window);

const sessionId = `web-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
const liveTalkingWebUrl = import.meta.env.VITE_LIVETALKING_WEB_URL || "http://127.0.0.1:8010/webrtcapi.html";

const livetalkingText = computed(() => {
  const status = livetalking.value?.status || "";
  if (!status) return "";
  const statusMap = {
    queued: "播报任务已入队",
    started: "数字人正在播报",
    failed: "数字人播报失败",
    skipped: "已跳过播报",
  };
  const message = livetalking.value?.message || "";
  return message ? `${statusMap[status] || status}：${message}` : statusMap[status] || status;
});

const volumeIcon = computed(() => {
  if (volume.value === 0) return "🔇";
  if (volume.value < 0.35) return "🔈";
  if (volume.value < 0.7) return "🔉";
  return "🔊";
});

function togglePanel() {
  panelOpen.value = !panelOpen.value;
}

function speakText(text) {
  if (!ttsSupported.value) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "zh-CN";
  utterance.rate = 1.1;
  utterance.volume = volume.value;
  utterance.onstart = () => { speaking.value = true; };
  utterance.onend = () => { speaking.value = false; };
  utterance.onerror = () => { speaking.value = false; };
  window.speechSynthesis.speak(utterance);
}

function stopSpeaking() {
  if (ttsSupported.value) {
    window.speechSynthesis.cancel();
    speaking.value = false;
  }
}

async function submitQuestion() {
  const text = question.value.trim();
  if (text.length < 2) {
    error.value = "请输入至少2个字的问题";
    return;
  }

  loading.value = true;
  error.value = "";
  try {
    const payload = await digitalHumanChat({
      platform: props.platform,
      sessionId,
      question: text,
    });
    answer.value = payload.answer || "";
    highlights.value = Array.isArray(payload.highlights) ? payload.highlights.slice(0, 3) : [];
    livetalking.value = payload.livetalking || null;
    traceId.value = payload.trace_id || "";

    if (payload.answer) {
      speakText(payload.answer);
    }
  } catch (err) {
    error.value = err.message || "数字人服务异常";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="floating-dh">
    <button class="float-trigger" type="button" @click="togglePanel">
      {{ panelOpen ? "收起数字人" : "打开数字人" }}
    </button>

    <section v-if="panelOpen" class="panel">
      <header class="panel-header">
        <h3>数字人助手</h3>
        <span>{{ platform }}</span>
      </header>

      <div class="avatar-box">
        <iframe
          :src="liveTalkingWebUrl"
          title="LiveTalking 数字人"
          allow="autoplay; microphone; camera"
        ></iframe>
      </div>
      <p class="avatar-tip">若视频未播放，请在视频区点击 Start。</p>

      <textarea v-model="question" rows="3" placeholder="请输入你想让数字人回答的问题"></textarea>
      <div class="actions">
        <button type="button" :disabled="loading" @click="submitQuestion">
          {{ loading ? "处理中..." : "发送问题" }}
        </button>
      </div>

      <p v-if="error" class="error">{{ error }}</p>
      <div v-if="answer" class="answer">
        <div class="answer-head">
          <h4>回答</h4>
          <div class="volume-row">
            <span class="volume-icon">{{ volumeIcon }}</span>
            <input
              type="range"
              v-model.number="volume"
              min="0"
              max="1"
              step="0.05"
              class="volume-slider"
              title="调整音量"
            />
            <button
              type="button"
              class="btn-speak"
              :disabled="speaking"
              @click="speakText(answer)"
              :title="speaking ? '正在朗读...' : '朗读回答'"
            >
              {{ speaking ? "🕤" : "🔊" }}
            </button>
            <button
              v-if="speaking"
              type="button"
              class="btn-stop"
              @click="stopSpeaking"
              title="停止朗读"
            >
              ⏹
            </button>
          </div>
        </div>
        <p>{{ answer }}</p>
      </div>
      <div v-if="highlights.length" class="highlights">
        <h4>要点</h4>
        <ul>
          <li v-for="(item, index) in highlights" :key="`${index}-${item}`">{{ item }}</li>
        </ul>
      </div>
      <p v-if="livetalkingText" class="lt-status">播报状态：{{ livetalkingText }}</p>
      <p v-if="traceId" class="trace">trace_id: {{ traceId }}</p>
    </section>
  </div>
</template>

<style scoped>
.floating-dh {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 40;
}

.float-trigger {
  border: 1px solid #7bcfc4;
  background: #e8fffb;
  color: #0d5d57;
  border-radius: 999px;
  padding: 10px 14px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.16);
}

.panel {
  margin-top: 10px;
  width: min(420px, calc(100vw - 32px));
  border: 1px solid #d8c9b1;
  border-radius: 14px;
  background: #fffdf8;
  padding: 12px;
  box-shadow: 0 14px 30px rgba(0, 0, 0, 0.2);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
}

.panel-header span {
  border: 1px solid #d2bf9f;
  border-radius: 999px;
  background: #f4ead8;
  color: #675438;
  font-size: 12px;
  padding: 3px 8px;
}

.avatar-box {
  width: 100%;
  height: 220px;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #ccbea8;
  background: #0f1418;
}

.avatar-box iframe {
  width: 100%;
  height: 100%;
  border: 0;
}

.avatar-tip {
  margin: 8px 0 10px;
  color: #5d523e;
  font-size: 12px;
}

textarea {
  width: 100%;
  border-radius: 10px;
  border: 1px solid #ccbea8;
  background: #fffef9;
  padding: 8px 10px;
  resize: vertical;
}

.actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

.actions button {
  border: 1px solid #7bcfc4;
  border-radius: 10px;
  background: #e8fffb;
  color: #0d5d57;
  padding: 8px 12px;
  font-weight: 700;
  cursor: pointer;
}

.actions button:disabled {
  opacity: 0.6;
  cursor: wait;
}

.error {
  margin: 10px 0 0;
  color: #a63b2f;
}

.answer {
  margin-top: 12px;
}
.answer-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.answer-head h4 { margin: 0; font-size: 14px; }
.volume-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.volume-icon {
  font-size: 16px;
}
.volume-slider {
  width: 72px;
  height: 4px;
  accent-color: #0d5d57;
  cursor: pointer;
}
.btn-speak, .btn-stop {
  border: 1px solid #ccbea8;
  border-radius: 6px;
  background: #fffef9;
  cursor: pointer;
  font-size: 14px;
  padding: 2px 6px;
  line-height: 1;
}
.btn-speak:hover { background: #e8fffb; border-color: #7bcfc4; }
.btn-stop:hover { background: #fff0f0; border-color: #c97; }
.btn-speak:disabled { opacity: 0.5; cursor: wait; }

.answer p {
  margin: 0;
  color: #2f2a22;
  line-height: 1.6;
}

.highlights h4 {
  margin: 10px 0 6px;
  font-size: 14px;
}

.highlights ul {
  margin: 0;
  padding-left: 18px;
}

.highlights li {
  color: #4c4130;
  margin-bottom: 4px;
}

.lt-status,
.trace {
  margin: 10px 0 0;
  color: #5d523e;
  font-size: 12px;
}

@media (max-width: 640px) {
  .floating-dh {
    right: 12px;
    bottom: 12px;
  }

  .panel {
    width: min(420px, calc(100vw - 24px));
  }
}
</style>
