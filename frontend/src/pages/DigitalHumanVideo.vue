<script setup>
import { computed, ref } from "vue";
import { generateDigitalHumanVideo } from "../api/client";

const scriptText = ref("");
const audioMode = ref("default");
const videoMode = ref("default");
const audioFile = ref(null);
const videoFile = ref(null);
const loading = ref(false);
const error = ref("");
const result = ref(null);

const canSubmit = computed(() => scriptText.value.trim().length >= 2 && !loading.value);

function onAudioFile(event) {
  audioFile.value = event.target.files?.[0] || null;
}

function onVideoFile(event) {
  videoFile.value = event.target.files?.[0] || null;
}

async function submitVideo() {
  if (scriptText.value.trim().length < 2) {
    error.value = "请输入至少 2 个字的口播脚本";
    return;
  }
  loading.value = true;
  error.value = "";
  result.value = null;
  try {
    result.value = await generateDigitalHumanVideo({
      script: scriptText.value.trim(),
      audioMode: audioMode.value,
      videoMode: videoMode.value,
      audioFile: audioMode.value === "upload" ? audioFile.value : null,
      videoFile: videoMode.value === "upload" ? videoFile.value : null,
    });
  } catch (err) {
    error.value = err.message || "数字人视频生成失败";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="digital-video-page">
    <section class="digital-video-hero">
      <p class="section-kicker">Digital Human Video</p>
      <h1>数字人视频生成</h1>
      <p>输入脚本，选择默认或上传素材，生成可下载 mp4。</p>
    </section>

    <section class="digital-video-layout">
      <form class="generator-panel" @submit.prevent="submitVideo">
        <label class="script-field">
          口播脚本
          <textarea v-model="scriptText" rows="7" placeholder="请输入想让数字人播报的内容"></textarea>
        </label>

        <div class="source-grid">
          <fieldset>
            <legend>音频来源</legend>
            <label><input v-model="audioMode" type="radio" value="default" /> 默认音频</label>
            <label><input v-model="audioMode" type="radio" value="upload" /> 上传音频</label>
            <input v-if="audioMode === 'upload'" type="file" accept=".mp3,.wav,.m4a,.aac,audio/*" @change="onAudioFile" />
          </fieldset>

          <fieldset>
            <legend>视频来源</legend>
            <label><input v-model="videoMode" type="radio" value="default" /> 默认视频</label>
            <label><input v-model="videoMode" type="radio" value="upload" /> 上传视频</label>
            <input v-if="videoMode === 'upload'" type="file" accept=".mp4,.mov,.webm,video/*" @change="onVideoFile" />
          </fieldset>
        </div>

        <p v-if="error" class="video-error">{{ error }}</p>
        <button class="generate-button" type="submit" :disabled="!canSubmit">
          {{ loading ? "生成中..." : "生成视频" }}
        </button>
      </form>

      <aside class="result-panel">
        <div class="result-head">
          <p class="section-kicker">Result</p>
          <h2>生成结果</h2>
        </div>
        <p v-if="loading" class="result-status">正在合成视频，请稍候。</p>
        <p v-else-if="!result" class="result-status">等待生成任务。</p>
        <template v-else>
          <p class="result-status">{{ result.message }}</p>
          <video v-if="result.video_url" :src="result.video_url" controls></video>
          <a v-if="result.download_url" class="download-button" :href="result.download_url">下载 mp4</a>
        </template>
      </aside>
    </section>
  </main>
</template>

<style scoped>
.digital-video-page {
  width: min(1120px, 94vw);
  margin: 28px auto 48px;
  display: grid;
  gap: 18px;
}

.digital-video-hero {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: linear-gradient(135deg, #fffdf8 0%, #e8fffb 100%);
  padding: 24px;
}

.digital-video-hero h1 {
  margin: 8px 0;
  font-size: clamp(28px, 4vw, 42px);
}

.digital-video-hero p {
  color: var(--ink-soft);
  margin: 0;
}

.digital-video-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
  gap: 16px;
  align-items: start;
}

.generator-panel,
.result-panel {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255, 253, 250, 0.92);
  box-shadow: var(--shadow-soft);
  padding: 18px;
}

.script-field {
  display: grid;
  gap: 8px;
  color: var(--ink-soft);
  font-size: 14px;
  font-weight: 800;
}

.script-field textarea {
  min-height: 170px;
}

.source-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

fieldset {
  border: 1px solid #d8c9b1;
  border-radius: 8px;
  display: grid;
  gap: 9px;
  margin: 0;
  padding: 13px;
}

legend {
  color: var(--brand-strong);
  font-weight: 900;
  padding: 0 5px;
}

fieldset label {
  align-items: center;
  display: flex;
  gap: 8px;
  color: var(--ink-strong);
}

input[type="radio"] {
  width: auto;
}

.generate-button,
.download-button {
  border: 1px solid #7bcfc4;
  border-radius: 8px;
  background: #e8fffb;
  color: var(--brand-strong);
  cursor: pointer;
  display: inline-flex;
  font-weight: 900;
  margin-top: 14px;
  padding: 10px 14px;
}

.generate-button:disabled {
  cursor: wait;
  opacity: 0.58;
}

.video-error {
  color: var(--danger);
  margin: 12px 0 0;
}

.result-head h2 {
  margin: 4px 0 12px;
}

.result-status {
  color: var(--ink-soft);
  margin: 0 0 12px;
}

.result-panel video {
  width: 100%;
  border-radius: 8px;
  border: 1px solid #d8c9b1;
  background: #111;
}

@media (max-width: 860px) {
  .digital-video-layout,
  .source-grid {
    grid-template-columns: 1fr;
  }
}
</style>
