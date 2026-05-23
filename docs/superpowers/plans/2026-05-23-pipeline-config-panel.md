# 管道配置面板 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为每日管道（fetch→extract→recommend）增加配置驱动能力和前端交互面板，支持平台开关、步骤跳过、手动触发。

**Architecture:** 后端在 RuleConfig 表存储 JSON 管道配置，通过 workflow.py 服务读写；run_daily_pipeline 执行前读取配置跳过禁用平台/步骤；前端在现有 workflow 卡片上升级为可交互面板，含开关、单步触发按钮和状态轮询。

**Tech Stack:** Django + DRF（后端），Vue 3（前端），无新增依赖。

---

### Task 1: 管道配置服务（workflow.py）

**Files:**
- Modify: `D:\aiFire\backend\apps\trends\services\workflow.py`

- [ ] **Step 1: 添加配置读写函数**

在 workflow.py 末尾添加：

```python
import json

from apps.trends.models import RuleConfig, Platform

PIPELINE_CONFIG_KEY = "pipeline_config"

PLATFORMS = [Platform.TIKTOK, Platform.INSTAGRAM, Platform.FACEBOOK, Platform.YOUTUBE]

DEFAULT_PIPELINE_CONFIG = {
    platform: {"enabled": True, "steps": {"fetch": True, "extract": True, "recommend": True}}
    for platform in PLATFORMS
}


def get_pipeline_config() -> dict:
    cfg, _ = RuleConfig.objects.get_or_create(
        key=PIPELINE_CONFIG_KEY,
        defaults={"value": DEFAULT_PIPELINE_CONFIG},
    )
    merged = dict(DEFAULT_PIPELINE_CONFIG)
    if isinstance(cfg.value, dict):
        for platform in PLATFORMS:
            if platform in cfg.value and isinstance(cfg.value[platform], dict):
                merged[platform] = {
                    "enabled": cfg.value[platform].get("enabled", True),
                    "steps": {
                        "fetch": cfg.value[platform].get("steps", {}).get("fetch", True),
                        "extract": cfg.value[platform].get("steps", {}).get("extract", True),
                        "recommend": cfg.value[platform].get("steps", {}).get("recommend", True),
                    },
                }
    return merged


def update_pipeline_config(config: dict) -> dict:
    merged = dict(DEFAULT_PIPELINE_CONFIG)
    for platform in PLATFORMS:
        if platform in config and isinstance(config[platform], dict):
            merged[platform] = {
                "enabled": bool(config[platform].get("enabled", True)),
                "steps": {
                    "fetch": bool(config[platform].get("steps", {}).get("fetch", True)),
                    "extract": bool(config[platform].get("steps", {}).get("extract", True)),
                    "recommend": bool(config[platform].get("steps", {}).get("recommend", True)),
                },
            }
    RuleConfig.objects.update_or_create(
        key=PIPELINE_CONFIG_KEY,
        defaults={"value": merged},
    )
    return merged
```

- [ ] **Step 2: 增强 `build_today_workflow_status` 携带配置信息**

修改 `build_today_workflow_status` 函数，在返回字典中增加 `config` 字段：

```python
def build_today_workflow_status() -> dict:
    runs = [get_or_create_today_run(platform) for platform in SOCIAL_PLATFORMS]
    config = get_pipeline_config()
    return {
        "date": timezone.localdate().isoformat(),
        "config": config,
        "runs": [
            {
                "platform": run.platform,
                "fetch_status": run.fetch_status,
                "extract_status": run.extract_status,
                "recommend_status": run.recommend_status,
                "last_message": run.last_message,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "updated_at": run.updated_at,
            }
            for run in runs
        ],
    }
```

- [ ] **Step 3: 运行测试确认**

```powershell
D:\aiFire\.venv\Scripts\python.exe -m pytest D:\aiFire\backend\tests\trends\ -v --tb=short 2>&1 | Select-Object -Last 20
```

Expected: 所有已有测试继续通过。

---

### Task 2: 管道配置 API

**Files:**
- Modify: `D:\aiFire\backend\apps\trends\api\views.py`
- Modify: `D:\aiFire\backend\apps\trends\api\urls.py`

- [ ] **Step 1: 添加 `WorkflowConfigView`**

在 views.py 末尾（`GeneratedTitleFeedbackView` 之后）添加：

```python
class WorkflowConfigView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        from apps.trends.services.workflow import get_pipeline_config
        return Response(get_pipeline_config())

    def patch(self, request):
        from apps.trends.services.workflow import update_pipeline_config
        config = request.data
        if not isinstance(config, dict):
            return Response({"detail": "配置格式错误"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(update_pipeline_config(config))
```

- [ ] **Step 2: 注册路由**

在 urls.py 的 import 和 urlpatterns 中添加：

```python
# import 中添加
WorkflowConfigView,

# urlpatterns 中添加（放在 workflow/status/ 后面）
path("workflow/config/", WorkflowConfigView.as_view(), name="workflow-config"),
```

完整的 urls.py import：

```python
from apps.trends.api.views import (
    AnalyticsOverviewView,
    AssistantChatView,
    GeneratedTitleFeedbackView,
    PhraseDeleteLogListView,
    PhraseDetailView,
    PhraseListView,
    PhraseSoftDeleteView,
    PlatformSummaryView,
    SessionInfoView,
    WorkflowConfigView,
    WorkflowStatusView,
)
```

---

### Task 3: 单步触发 API

**Files:**
- Modify: `D:\aiFire\backend\apps\trends\api\views.py`
- Modify: `D:\aiFire\backend\apps\trends\api\urls.py`

- [ ] **Step 1: 添加 `WorkflowTriggerView`**

在 views.py 的 `WorkflowConfigView` 之后添加：

```python
from apps.trends.models import WorkflowStatus
from apps.trends.services.workflow import mark_step

VALID_STEPS = {"fetch", "extract", "recommend"}


class WorkflowTriggerView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        platform = (request.data.get("platform") or "").strip().lower()
        step = (request.data.get("step") or "").strip().lower()

        if platform not in SOCIAL_PLATFORMS:
            return Response({"detail": "不支持的平台"}, status=status.HTTP_400_BAD_REQUEST)
        if step not in VALID_STEPS:
            return Response({"detail": "不支持的步骤"}, status=status.HTTP_400_BAD_REQUEST)

        # 标记开始运行
        mark_step(platform, step, WorkflowStatus.RUNNING, f"手动触发 {step}")

        try:
            from django.core.management import call_command
            from io import StringIO
            out = StringIO()
            call_command("run_daily_pipeline", platform=platform, step=step, stdout=out)
            output = out.getvalue()
            mark_step(platform, step, WorkflowStatus.SUCCESS, output[:255])
            return Response({
                "status": "success",
                "platform": platform,
                "step": step,
                "message": output[:255],
            })
        except Exception as exc:
            mark_step(platform, step, WorkflowStatus.FAILED, str(exc)[:255])
            return Response({
                "status": "failed",
                "platform": platform,
                "step": step,
                "message": str(exc)[:255],
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

- [ ] **Step 2: 注册路由**

在 urls.py 添加：

```python
# import 中添加
WorkflowTriggerView,

# urlpatterns 中添加
path("workflow/trigger/", WorkflowTriggerView.as_view(), name="workflow-trigger"),
```

---

### Task 4: 管道执行跳过逻辑

**Files:**
- Modify: `D:\aiFire\backend\apps\trends\management\commands\run_daily_pipeline.py`

- [ ] **Step 1: 在管道入口读取配置并跳过**

找到 `run_daily_pipeline` 的 `handle` 方法，在方法体最开始（`self.stdout.write` 之前）添加配置读取和跳过逻辑。

先找到 handle 方法的签名位置（约第 400+ 行，取决于文件版本），在方法体的 `add_arguments` 之后。

需要找到 handle 方法中处理 `platform` 参数的地方。在 `handle` 方法开头插入：

```python
from apps.trends.services.workflow import get_pipeline_config

pipeline_config = get_pipeline_config()
platform_cfg = pipeline_config.get(platform, {})
if not platform_cfg.get("enabled", True):
    self.stdout.write(self.style.WARNING(f"平台 {platform} 已禁用，跳过"))
    return

step_filter = options.get("step")  # 部分执行模式
```

然后在各步骤执行前检查配置。找到 `fetch` 步骤相关代码，在外层添加：

```python
# fetch 步骤前
if not step_filter or step_filter == "fetch":
    if not platform_cfg.get("steps", {}).get("fetch", True):
        self.stdout.write(self.style.WARNING("fetch 步骤已禁用，跳过"))
        mark_step(platform, "fetch", WorkflowStatus.SKIPPED, "步骤已禁用")
    else:
        # 原有 fetch 逻辑...
```

对 `extract` 和 `recommend` 步骤做同样处理。

**注意**：由于 `handle` 方法非常大（约 600 行），这里给出的是逻辑框架。实际修改时：
1. 在 handle 方法开头读取 `pipeline_config`
2. 检查 `platform_cfg["enabled"]`，禁用则整个平台跳过
3. 在每个步骤的执行代码外层包裹 `if platform_cfg["steps"][step_name]` 检查
4. 禁用的步骤调用 `mark_step(platform, step, WorkflowStatus.SKIPPED, "步骤已禁用")`

- [ ] **Step 2: 运行测试确认**

```powershell
D:\aiFire\.venv\Scripts\python.exe -m pytest D:\aiFire\backend\tests\ -v --tb=short 2>&1 | Select-Object -Last 20
```

---

### Task 5: 前端 API Client

**Files:**
- Modify: `D:\aiFire\frontend\src\api\client.js`

- [ ] **Step 1: 添加三个新函数**

在 client.js 末尾添加：

```javascript
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
```

---

### Task 6: 前端 Workflow 卡片交互升级

**Files:**
- Modify: `D:\aiFire\frontend\src\pages\HotwordsList.vue`

- [ ] **Step 1: 导入新 API 函数**

在 `<script setup>` 顶部 import 中添加：

```javascript
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
```

- [ ] **Step 2: 添加管道配置和触发相关的响应式变量**

在 `<script setup>` 中其他 ref 声明附近添加：

```javascript
const pipelineConfig = ref({});
const pipelineTriggerLoading = ref({});
const pipelineStatusPollTimer = ref(null);
```

- [ ] **Step 3: 添加管道操作方法**

在 `<script setup>` 中 `askSuggestion` 函数之后添加：

```javascript
async function loadPipelineConfig() {
  try {
    pipelineConfig.value = await fetchWorkflowConfig();
  } catch {
    // 非管理员时静默失败，使用默认配置
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
  const key = `${platform}_${step}`;
  pipelineTriggerLoading.value[key] = true;
  try {
    await triggerWorkflowStep(platform, step);
  } catch (err) {
    alert(`触发 ${step} 失败：` + (err.message || "未知错误"));
  } finally {
    pipelineTriggerLoading.value[key] = false;
    startPollingWorkflow();
  }
}

async function runAllPlatforms() {
  const cfg = pipelineConfig.value;
  const platforms = Object.keys(cfg).filter((p) => cfg[p].enabled);
  for (const platform of platforms) {
    const steps = cfg[platform].steps;
    if (steps.fetch) await triggerStep(platform, "fetch");
    if (steps.extract) await triggerStep(platform, "extract");
    if (steps.recommend) await triggerStep(platform, "recommend");
  }
}

function startPollingWorkflow() {
  stopPollingWorkflow();
  pipelineStatusPollTimer.value = setInterval(async () => {
    try {
      workflow.value = await fetchWorkflowStatus();
    } catch {}
  }, 3000);
  setTimeout(stopPollingWorkflow, 120000); // 2分钟超时
}

function stopPollingWorkflow() {
  if (pipelineStatusPollTimer.value) {
    clearInterval(pipelineStatusPollTimer.value);
    pipelineStatusPollTimer.value = null;
  }
}
```

- [ ] **Step 4: 在 watchEffect 中加载配置**

在现有的 `watchEffect` 中，加载 pipeline config。找到 `try` 块内的 `Promise.all` 调用，在其中加入 `loadPipelineConfig()`。或者更简单，在 Promise.all 返回后调用：

在 `watchEffect` 的 `try` 块 `Promise.all` 之后，`sessionReady` 之前添加：

```javascript
loadPipelineConfig();
```

- [ ] **Step 5: 替换 workflow 卡片的静态模板**

找到现有的 workflow 卡片模板（`<article class="board-card board-card-wide">` 及其内容），替换为：

```html
      <article class="board-card board-card-wide workflow-panel">
        <div class="board-heading">
          <div>
            <p class="section-kicker">管道状态</p>
            <h2>每日管道状态</h2>
          </div>
          <button
            v-if="sessionInfo?.is_admin"
            type="button"
            class="btn-run-all"
            @click="runAllPlatforms"
          >
            一键执行全部
          </button>
        </div>
        <div v-if="!workflow?.runs?.length" class="status">暂无管道运行数据</div>
        <div v-else class="workflow-platforms">
          <section
            v-for="run in workflow.runs"
            :key="run.platform"
            class="workflow-platform-row"
            :class="{ 'platform-disabled': !pipelineConfig[run.platform]?.enabled }"
          >
            <div class="platform-header">
              <span class="platform-name">{{ platformLabelMap[run.platform] || run.platform }}</span>
              <label class="platform-toggle" v-if="sessionInfo?.is_admin">
                <input
                  type="checkbox"
                  :checked="pipelineConfig[run.platform]?.enabled !== false"
                  @change="togglePlatform(run.platform)"
                />
                <span class="toggle-label">{{ pipelineConfig[run.platform]?.enabled !== false ? '启用' : '停用' }}</span>
              </label>
            </div>
            <div class="step-row">
              <div
                v-for="step in ['fetch','extract','recommend']"
                :key="step"
                class="step-card"
                :class="'step-' + run[step + '_status']"
              >
                <div class="step-icon">
                  <template v-if="run[step + '_status'] === 'success'">✓</template>
                  <template v-else-if="run[step + '_status'] === 'running'">⟳</template>
                  <template v-else-if="run[step + '_status'] === 'failed'">✗</template>
                  <template v-else-if="run[step + '_status'] === 'skipped'">⊘</template>
                  <template v-else>⏳</template>
                </div>
                <div class="step-body">
                  <span class="step-label">{{ stepLabelMap[step] }}</span>
                  <span class="step-status">{{ statusLabelMap[run[step + '_status']] || '等待中' }}</span>
                </div>
                <button
                  v-if="sessionInfo?.is_admin"
                  type="button"
                  class="btn-step-trigger"
                  :disabled="pipelineTriggerLoading[run.platform + '_' + step]"
                  @click="triggerStep(run.platform, step)"
                >
                  {{ pipelineTriggerLoading[run.platform + '_' + step] ? '执行中...' : (run[step + '_status'] === 'success' ? '重新执行' : '立即执行') }}
                </button>
              </div>
            </div>
          </section>
        </div>
      </article>
```

- [ ] **Step 6: 添加 stepLabelMap**

在 `<script setup>` 的现有 label map（`windowLabelMap` 附近）添加：

```javascript
const stepLabelMap = {
  fetch: "📥 抓取",
  extract: "🔍 提取",
  recommend: "✨ 推荐",
};
```

- [ ] **Step 7: 添加 workflow 面板的 CSS**

在 `<style scoped>` 末尾（`@media` 规则之前）添加：

```css
.workflow-panel { background: linear-gradient(160deg, #1a2e2b 0%, #142120 100%); color: #f9f1df; }
.workflow-panel .board-heading { margin-bottom: 10px; }
.workflow-panel .board-heading h2 { color: #fff8e8; }
.workflow-panel .board-heading .section-kicker { color: #8bc4bb; }
.workflow-panel .status { color: #b0a897; }
.btn-run-all { border: 1px solid #7bcfc4; border-radius: 10px; background: #e8fffb; color: #0d5d57; padding: 7px 12px; font-weight: 700; cursor: pointer; font-size: 13px; }
.workflow-platforms { display: grid; gap: 10px; }
.workflow-platform-row { border: 1px solid rgba(255,255,255,.14); border-radius: 12px; padding: 10px; background: rgba(255,255,255,.05); }
.workflow-platform-row.platform-disabled { opacity: .45; }
.platform-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.platform-name { font-weight: 800; font-size: 14px; }
.platform-toggle { display: flex; align-items: center; gap: 5px; cursor: pointer; font-size: 12px; }
.platform-toggle input { width: auto; }
.toggle-label { color: #8bc4bb; }
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
```

- [ ] **Step 8: 构建验证**

```powershell
cd D:\aiFire\frontend; npm run build 2>&1 | Select-Object -Last 10
```

Expected: Build succeeds with no errors.

---

### Task 7: 编写后端测试

**Files:**
- Create: `D:\aiFire\backend\tests\trends\test_pipeline_config.py`

- [ ] **Step 1: 写测试文件**

```python
from django.test import TestCase
from rest_framework.test import APIClient

from apps.trends.models import RuleConfig, Platform
from apps.trends.services.workflow import get_pipeline_config, update_pipeline_config, PIPELINE_CONFIG_KEY


class PipelineConfigServiceTests(TestCase):
    def test_get_default_config(self):
        """首次读取应返回默认配置"""
        RuleConfig.objects.filter(key=PIPELINE_CONFIG_KEY).delete()
        cfg = get_pipeline_config()
        self.assertIn(Platform.TIKTOK, cfg)
        self.assertTrue(cfg[Platform.TIKTOK]["enabled"])
        self.assertTrue(cfg[Platform.TIKTOK]["steps"]["fetch"])

    def test_update_config(self):
        """更新配置后读取应反映变更"""
        new_cfg = {
            Platform.TIKTOK: {"enabled": False, "steps": {"fetch": True, "extract": False, "recommend": True}},
        }
        result = update_pipeline_config(new_cfg)
        self.assertFalse(result[Platform.TIKTOK]["enabled"])
        self.assertFalse(result[Platform.TIKTOK]["steps"]["extract"])

        # 再次读取确认持久化
        cfg = get_pipeline_config()
        self.assertFalse(cfg[Platform.TIKTOK]["enabled"])

    def test_partial_update_preserves_defaults(self):
        """部分更新应保留未指定平台的默认值"""
        update_pipeline_config({Platform.TIKTOK: {"enabled": False}})
        cfg = get_pipeline_config()
        self.assertFalse(cfg[Platform.TIKTOK]["enabled"])
        self.assertTrue(cfg[Platform.INSTAGRAM]["enabled"])


class PipelineConfigAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_get_config_anonymous(self):
        """匿名用户可读取配置（GET 不需要管理员）"""
        response = self.client.get("/api/workflow/config/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(Platform.TIKTOK, response.data)

    def test_trigger_invalid_step(self):
        """无效步骤应返回 400"""
        response = self.client.post("/api/workflow/trigger/", {
            "platform": Platform.TIKTOK,
            "step": "invalid_step",
        }, format="json")
        self.assertEqual(response.status_code, 400)
```

- [ ] **Step 2: 运行测试**

```powershell
D:\aiFire\.venv\Scripts\python.exe -m pytest D:\aiFire\backend\tests\trends\test_pipeline_config.py -v --tb=short
```

Expected: All tests pass.

---

### Task 8: 最终验证

- [ ] **Step 1: 运行全部后端测试**

```powershell
D:\aiFire\.venv\Scripts\python.exe -m pytest D:\aiFire\backend\tests\ -v --tb=short 2>&1 | Select-Object -Last 30
```

- [ ] **Step 2: 前端构建**

```powershell
cd D:\aiFire\frontend; npm run build 2>&1 | Select-Object -Last 10
```

Expected: Build succeeds.

