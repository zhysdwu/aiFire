<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { cloneVoiceAndSynthesize, generateDigitalHumanVideo } from "../api/client";

const API_KEY_STORAGE = "digital_human_alibaba_api_key";
const SUBTITLE_STORAGE = "digital_human_subtitle_lang";

const subtitleLanguage = ref(localStorage.getItem(SUBTITLE_STORAGE) || "zh_en");
const alibabaApiKey = ref(localStorage.getItem(API_KEY_STORAGE) || "");

const mode = ref("image_audio");
const imageFile = ref(null);
const audioFile = ref(null);
const usingDefaultImage = ref(true);
const usingDefaultAudio = ref(true);
const sampleFile = ref(null);
const cloneText = ref("");
const clonedAudioUrl = ref("");

const scriptText = ref("你好，我是你的数字人助手，很高兴为你服务。");
const DEFAULT_SUBTITLE_ZH = "你好，我是你的数字人助手，很高兴为你服务。";
const DEFAULT_SUBTITLE_EN = "Hello, I am your digital human assistant. Nice to serve you.";
const loading = ref(false);
const progress = ref("等待开始");
const error = ref("");
const result = ref(null);
const downloadHint = ref("");
const downloadPathHint = ref("");

watch(subtitleLanguage, (value) => localStorage.setItem(SUBTITLE_STORAGE, value));
watch(alibabaApiKey, (value) => localStorage.setItem(API_KEY_STORAGE, value));

const canGenerate = computed(() => {
  if (!alibabaApiKey.value.trim()) return false;
  if (!usingDefaultImage.value && !imageFile.value) return false;
  if (mode.value === "image_audio") return usingDefaultAudio.value || !!audioFile.value;
  return !!clonedAudioUrl.value;
});

function formatDateStamp() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}${m}${d}`;
}

function onImageFile(event) {
  const file = event.target.files?.[0] || null;
  imageFile.value = file;
  usingDefaultImage.value = !file;
}

function onAudioFile(event) {
  const file = event.target.files?.[0] || null;
  audioFile.value = file;
  usingDefaultAudio.value = !file;
}

function onSampleFile(event) {
  sampleFile.value = event.target.files?.[0] || null;
}

function useDefaultImage() {
  imageFile.value = null;
  usingDefaultImage.value = true;
}

function useDefaultAudio() {
  audioFile.value = null;
  usingDefaultAudio.value = true;
}

async function generateClonedAudio() {
  if (!alibabaApiKey.value.trim()) {
    error.value = "请先输入阿里云 API Key";
    return;
  }
  if (!sampleFile.value) {
    error.value = "请先上传声音样本";
    return;
  }
  if (cloneText.value.trim().length < 2) {
    error.value = "请输入要朗读的文本";
    return;
  }
  loading.value = true;
  error.value = "";
  progress.value = "步骤 1/2：声音复刻中";
  try {
    const data = await cloneVoiceAndSynthesize({
      alibabaApiKey: alibabaApiKey.value.trim(),
      text: cloneText.value.trim(),
      sampleFile: sampleFile.value,
    });
    progress.value = "步骤 2/2：语音合成完成";
    clonedAudioUrl.value = data.audio_url || "";
    scriptText.value = cloneText.value.trim();
  } catch (err) {
    error.value = err.message || "声音克隆失败";
  } finally {
    loading.value = false;
  }
}

async function submitVideo() {
  if (!canGenerate.value) return;
  loading.value = true;
  error.value = "";
  result.value = null;
  progress.value = "步骤 1/3：准备素材";
  try {
    const resolvedVideoMode = usingDefaultImage.value ? "default" : "upload";
    let resolvedAudioMode = "upload";
    let uploadAudioFile = null;

    if (mode.value === "image_audio") {
      resolvedAudioMode = usingDefaultAudio.value ? "default" : "upload";
      uploadAudioFile = resolvedAudioMode === "upload" ? audioFile.value : null;
      progress.value = "步骤 2/3：提交图片与音频到阿里云万象";
    } else {
      progress.value = "步骤 2/3：准备克隆语音音频";
      const response = await fetch(clonedAudioUrl.value);
      const blob = await response.blob();
      uploadAudioFile = new File([blob], "cloned-audio.mp3", { type: "audio/mpeg" });
      progress.value = "步骤 3/3：提交阿里云万象视频生成任务";
    }

    const resolvedScript =
      mode.value === "clone_text"
        ? scriptText.value.trim()
        : resolvedAudioMode === "default"
          ? `${DEFAULT_SUBTITLE_ZH}\n${DEFAULT_SUBTITLE_EN}`
          : "";

    result.value = await generateDigitalHumanVideo({
      script: resolvedScript,
      audioMode: resolvedAudioMode,
      videoMode: resolvedVideoMode,
      subtitleMode: subtitleLanguage.value,
      audioFile: uploadAudioFile,
      videoFile: resolvedVideoMode === "upload" ? imageFile.value : null,
      configId: "",
      alibabaApiKey: alibabaApiKey.value.trim(),
    });
    progress.value = "生成完成";
  } catch (err) {
    error.value = err.message || "生成视频失败";
  } finally {
    loading.value = false;
  }
}

async function downloadVideo() {
  if (!result.value?.video_url && !result.value?.download_url) return;
  downloadHint.value = "正在准备下载，请稍候...";
  downloadPathHint.value = "";
  try {
    const filename = `数字人视频_${formatDateStamp()}.mp4`;
    const saveByAnchor = (href, withDownloadName = false) => {
      const link = document.createElement("a");
      link.href = href;
      if (withDownloadName) link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
    };

    const directHref = result.value.download_url || result.value.video_url;

    if (result.value.download_url) {
      // 优先走后端下载接口（Content-Disposition），稳定性高于 fetch+blob。
      saveByAnchor(directHref, false);
      downloadHint.value = "下载完成";
      downloadPathHint.value = `已触发浏览器下载：${filename}（通常保存在系统“下载”目录）`;
      return;
    }

    const response = await fetch(result.value.video_url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    if (!blob || blob.size === 0) {
      saveByAnchor(directHref, false);
      downloadHint.value = "下载完成";
      downloadPathHint.value = `已触发浏览器下载：${filename}（通常保存在系统“下载”目录）`;
      return;
    }
    const blobUrl = URL.createObjectURL(blob);
    if ("showSaveFilePicker" in window) {
      try {
        const handle = await window.showSaveFilePicker({
          suggestedName: filename,
          types: [{ description: "MP4 Video", accept: { "video/mp4": [".mp4"] } }],
        });
        const writable = await handle.createWritable();
        await writable.write(blob);
        await writable.close();
        downloadPathHint.value = `已保存：${handle.name}`;
      } catch {
        saveByAnchor(blobUrl, true);
        downloadPathHint.value = `已触发浏览器下载：${filename}（通常保存在系统“下载”目录）`;
      }
    } else {
      saveByAnchor(blobUrl, true);
      downloadPathHint.value = `已触发浏览器下载：${filename}（通常保存在系统“下载”目录）`;
    }
    setTimeout(() => URL.revokeObjectURL(blobUrl), 10_000);
    downloadHint.value = "下载完成";
  } catch (err) {
    downloadHint.value = `下载失败：${err.message || "未知错误"}`;
    downloadPathHint.value = "";
  }
}

onMounted(() => {
  useDefaultImage();
  useDefaultAudio();
});
</script>

<template>
  <main class="digital-video-page">
    <section class="card">
      <h2>API 配置</h2>
      <label class="field">
        阿里云 API Key
        <input v-model="alibabaApiKey" type="password" autocomplete="off" placeholder="请输入阿里云万象 API Key" />
      </label>
      <div class="field">
        <span>字幕语言</span>
        <div class="radio-group">
          <label><input v-model="subtitleLanguage" type="radio" value="zh_en" /> 中英文双语</label>
        </div>
      </div>
      <p class="hint">字幕由音频自动识别并生成中英文双语，不需要手工输入。</p>
    </section>

    <section class="card">
      <h2>生成模式</h2>
      <div class="tabs">
        <button :class="{ active: mode === 'image_audio' }" type="button" @click="mode = 'image_audio'">模式一：照片+音频</button>
        <button :class="{ active: mode === 'clone_text' }" type="button" @click="mode = 'clone_text'">模式二：克隆音色+文本</button>
      </div>

      <div v-if="mode === 'image_audio'" class="mode-grid">
        <div class="field">
          <span>图片上传（jpg/png）</span>
          <input type="file" accept=".jpg,.jpeg,.png,image/*" @change="onImageFile" />
          <button type="button" @click="useDefaultImage">使用默认图片</button>
          <small>{{ usingDefaultImage ? "后端默认图片" : imageFile?.name || "未选择图片" }}</small>
        </div>
        <div class="field">
          <span>音频上传（mp3/wav）</span>
          <input type="file" accept=".mp3,.wav,.m4a,audio/*" @change="onAudioFile" />
          <button type="button" @click="useDefaultAudio">使用默认音频</button>
          <small>{{ usingDefaultAudio ? "后端默认音频" : audioFile?.name || "未选择音频" }}</small>
        </div>
      </div>

      <div v-else class="mode-grid">
        <div class="field">
          <span>声音样本（建议 10-20 秒）</span>
          <input type="file" accept=".mp3,.wav,.m4a,audio/*" @change="onSampleFile" />
          <small>{{ sampleFile?.name || "未选择样本" }}</small>
          <small class="hint">支持本地上传 wav/mp3/m4a，后端会自动转换并提交音色复刻。</small>
        </div>
        <div class="field">
          <span>克隆音色朗读文本</span>
          <textarea v-model="cloneText" rows="5" placeholder="请输入要朗读的文字"></textarea>
          <button type="button" :disabled="loading" @click="generateClonedAudio">克隆音色并生成语音</button>
          <audio v-if="clonedAudioUrl" :src="clonedAudioUrl" controls />
          <small class="hint">当前使用阿里云百炼 API Key 完成音色复刻与语音合成。</small>
        </div>
        <div class="field">
          <span>图片上传（jpg/png）</span>
          <input type="file" accept=".jpg,.jpeg,.png,image/*" @change="onImageFile" />
          <button type="button" @click="useDefaultImage">使用默认图片</button>
          <small>{{ usingDefaultImage ? "后端默认图片" : imageFile?.name || "未选择图片" }}</small>
        </div>
      </div>
    </section>

    <section class="card">
      <h2>生成视频</h2>
      <button class="primary" type="button" :disabled="loading || !canGenerate" @click="submitVideo">
        {{ loading ? "生成中..." : "生成数字人视频" }}
      </button>
      <p class="hint">{{ progress }}</p>
      <p v-if="error" class="error">{{ error }}</p>
      <video v-if="result?.video_url" :src="result.video_url" controls />
      <div v-if="result?.video_url" class="download-row">
        <button type="button" @click="downloadVideo">下载视频</button>
        <span class="hint">{{ downloadHint }}</span>
      </div>
      <p v-if="downloadPathHint" class="hint">{{ downloadPathHint }}</p>
    </section>
  </main>
</template>

<style scoped>
.digital-video-page {
  width: min(1120px, 94vw);
  margin: 28px auto 48px;
  display: grid;
  gap: 16px;
}

.card {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
  padding: 18px;
  display: grid;
  gap: 12px;
}

.card h2 {
  margin: 0;
}

.field {
  display: grid;
  gap: 8px;
}

.radio-group {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tabs button {
  border: 1px solid #ccd2da;
  border-radius: 6px;
  background: #f7f9fb;
  padding: 8px 12px;
  cursor: pointer;
}

.tabs button.active {
  border-color: #4d8cff;
  background: #eaf2ff;
}

.mode-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.primary {
  width: fit-content;
  border: 1px solid #4d8cff;
  background: #4d8cff;
  color: #fff;
  border-radius: 6px;
  padding: 10px 14px;
  cursor: pointer;
}

.primary:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.error {
  color: #d93025;
  margin: 0;
}

.hint {
  color: #5f6b7a;
  margin: 0;
}

video {
  width: 100%;
  border: 1px solid #d8dde4;
  border-radius: 6px;
  background: #111;
}

.download-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

@media (max-width: 860px) {
  .mode-grid {
    grid-template-columns: 1fr;
  }
}
</style>
