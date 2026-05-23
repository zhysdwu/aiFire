# Apify 三平台独立采集与推荐（Phase 1）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留现有 TikTok 功能基础上，新增 Instagram、Facebook 的 Apify 采集与独立推荐能力，并在前端单页通过下拉框切换三平台数据。

**Architecture:** 后端采用“统一 Apify 客户端 + 平台插件化采集器 + 平台维度 pipeline”实现三平台扩展；前端保持单页面架构，通过平台参数驱动 API 查询；调度层按平台维护每日成功抓取检查点，保证三平台各自每天最多一次成功抓取。

**Tech Stack:** Python, Django, Django REST Framework, MySQL, Vue3, Vite, Apify API

---

## File Structure（实施前边界）

- **采集与服务层**
  - Create: `backend/apps/trends/services/apify_client.py`
  - Create: `backend/apps/trends/services/apify_collectors.py`
  - Modify: `backend/apps/trends/services/source_collectors.py`
- **模型与迁移**
  - Modify: `backend/apps/trends/models.py`
  - Create: `backend/apps/trends/migrations/0008_platform_daily_checkpoint.py`（名称以实际生成为准）
- **调度与命令**
  - Modify: `backend/apps/trends/management/commands/run_daily_pipeline.py`
  - Modify: `backend/apps/trends/management/commands/ensure_daily_fetch.py`
  - Modify: `backend/apps/trends/management/commands/run_daily_scheduler.py`
- **API**
  - Modify: `backend/apps/trends/api/serializers.py`
  - Modify: `backend/apps/trends/api/views.py`
  - Modify: `backend/apps/trends/api/urls.py`
- **前端**
  - Modify: `frontend/src/api/client.js`
  - Modify: `frontend/src/pages/HotwordsList.vue`
  - Modify: `frontend/src/pages/HotwordDetail.vue`
- **测试**
  - Create: `backend/tests/trends/test_apify_collectors.py`
  - Modify: `backend/tests/trends/test_ensure_daily_fetch.py`
  - Modify: `backend/tests/trends/test_api_phrases.py`

---

### Task 1: 配置与数据模型扩展（平台+检查点）

**Files:**
- Modify: `backend/apps/trends/models.py`
- Create: `backend/apps/trends/migrations/0008_platform_daily_checkpoint.py`
- Test: `backend/tests/trends/test_ensure_daily_fetch.py`

- [ ] **Step 1: 写失败测试（平台检查点按平台生效）**

```python
@pytest.mark.django_db
def test_daily_checkpoint_is_platform_scoped():
    tiktok = DailyFetchCheckpoint.objects.create(key="tiktok")
    instagram = DailyFetchCheckpoint.objects.create(key="instagram")
    assert tiktok.key != instagram.key
```

- [ ] **Step 2: 运行测试确认失败**

Run: `..\.venv\Scripts\python.exe -m pytest tests/trends/test_ensure_daily_fetch.py::test_daily_checkpoint_is_platform_scoped -q`  
Expected: FAIL（模型字段或数据约束未满足）

- [ ] **Step 3: 最小实现模型变更**

```python
class Platform(models.TextChoices):
    TIKTOK = "tiktok", "TikTok"
    INSTAGRAM = "instagram", "Instagram"
    FACEBOOK = "facebook", "Facebook"

class DailyFetchCheckpoint(models.Model):
    key = models.CharField(max_length=32, unique=True)
    last_success_date = models.DateField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
```

- [ ] **Step 4: 生成并执行迁移**

Run:
- `..\.venv\Scripts\python.exe manage.py makemigrations trends`
- `..\.venv\Scripts\python.exe manage.py migrate`  
Expected: 新迁移应用成功

- [ ] **Step 5: 运行测试确认通过**

Run: `..\.venv\Scripts\python.exe -m pytest tests/trends/test_ensure_daily_fetch.py -q`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/apps/trends/models.py backend/apps/trends/migrations backend/tests/trends/test_ensure_daily_fetch.py
git commit -m "feat: add platform-scoped daily fetch checkpoint"
```

---

### Task 2: 引入 Apify 客户端与三平台采集器

**Files:**
- Create: `backend/apps/trends/services/apify_client.py`
- Create: `backend/apps/trends/services/apify_collectors.py`
- Test: `backend/tests/trends/test_apify_collectors.py`

- [ ] **Step 1: 写失败测试（collector 输出标准结构）**

```python
def test_instagram_collector_normalizes_schema(monkeypatch):
    payload = [{"id": "1", "caption": "street style", "url": "https://instagram.com/p/1"}]
    monkeypatch.setattr("apps.trends.services.apify_collectors._run_actor", lambda *a, **k: payload)
    items = collect_instagram_from_apify(limit=10, region="US")
    assert items[0]["platform"] == "instagram"
    assert "external_id" in items[0]
    assert "raw_metrics" in items[0]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `..\.venv\Scripts\python.exe -m pytest tests/trends/test_apify_collectors.py::test_instagram_collector_normalizes_schema -q`  
Expected: FAIL（函数不存在）

- [ ] **Step 3: 实现 ApifyClient（最小可用）**

```python
class ApifyClient:
    def __init__(self, token: str):
        self.token = token
    def run_actor(self, actor_id: str, actor_input: dict) -> list[dict]:
        ...
```

- [ ] **Step 4: 实现三平台 collector**

```python
def collect_tiktok_from_apify(limit: int, region: str) -> list[dict]: ...
def collect_instagram_from_apify(limit: int, region: str) -> list[dict]: ...
def collect_facebook_from_apify(limit: int, region: str) -> list[dict]: ...
```

- [ ] **Step 5: 运行采集器测试**

Run: `..\.venv\Scripts\python.exe -m pytest tests/trends/test_apify_collectors.py -q`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/apps/trends/services/apify_client.py backend/apps/trends/services/apify_collectors.py backend/tests/trends/test_apify_collectors.py
git commit -m "feat: add apify client and multi-platform collectors"
```

---

### Task 3: 将三平台采集接入日常 pipeline（独立运行）

**Files:**
- Modify: `backend/apps/trends/management/commands/run_daily_pipeline.py`
- Modify: `backend/apps/trends/services/source_collectors.py`
- Test: `backend/tests/trends/test_pipeline_compute_metrics.py`

- [ ] **Step 1: 写失败测试（三平台独立执行）**

```python
def test_pipeline_collects_per_platform_independently(monkeypatch):
    # 伪造 tiktok 成功、instagram 失败、facebook 成功
    ...
    assert tiktok_called and instagram_called and facebook_called
```

- [ ] **Step 2: 运行测试确认失败**

Run: `..\.venv\Scripts\python.exe -m pytest tests/trends/test_pipeline_compute_metrics.py::test_pipeline_collects_per_platform_independently -q`  
Expected: FAIL

- [ ] **Step 3: 修改 pipeline 为平台循环处理**

```python
for platform in [Platform.TIKTOK, Platform.INSTAGRAM, Platform.FACEBOOK]:
    collected = collect_by_platform(platform, limit, region)
    process_platform_snapshots(platform, collected)
```

- [ ] **Step 4: 保持原有 TikTok 兼容路径**

```python
if source_mode == "legacy":
    collected = legacy_tiktok_only(...)
```

- [ ] **Step 5: 运行相关测试**

Run: `..\.venv\Scripts\python.exe -m pytest tests/trends/test_pipeline_compute_metrics.py -q`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/apps/trends/management/commands/run_daily_pipeline.py backend/apps/trends/services/source_collectors.py backend/tests/trends/test_pipeline_compute_metrics.py
git commit -m "feat: run daily pipeline per platform independently"
```

---

### Task 4: 扩展每日检查与调度为平台维度

**Files:**
- Modify: `backend/apps/trends/management/commands/ensure_daily_fetch.py`
- Modify: `backend/apps/trends/management/commands/run_daily_scheduler.py`
- Test: `backend/tests/trends/test_ensure_daily_fetch.py`

- [ ] **Step 1: 写失败测试（当天仅跳过对应平台）**

```python
def test_ensure_daily_fetch_skips_only_platform_with_today_checkpoint(monkeypatch):
    ...
    assert "tiktok" skipped
    assert "instagram" executed
```

- [ ] **Step 2: 运行测试确认失败**

Run: `..\.venv\Scripts\python.exe -m pytest tests/trends/test_ensure_daily_fetch.py::test_ensure_daily_fetch_skips_only_platform_with_today_checkpoint -q`  
Expected: FAIL

- [ ] **Step 3: 实现 ensure_daily_fetch 平台循环**

```python
for platform in ["tiktok", "instagram", "facebook"]:
    ensure_one_platform(platform=platform, ...)
```

- [ ] **Step 4: 修改 scheduler 传递平台策略**

```python
call_command("ensure_daily_fetch", "--source", "official", ...)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `..\.venv\Scripts\python.exe -m pytest tests/trends/test_ensure_daily_fetch.py -q`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/apps/trends/management/commands/ensure_daily_fetch.py backend/apps/trends/management/commands/run_daily_scheduler.py backend/tests/trends/test_ensure_daily_fetch.py
git commit -m "feat: make daily fetch scheduler platform-aware"
```

---

### Task 5: API 增加平台参数与摘要分析接口

**Files:**
- Modify: `backend/apps/trends/api/views.py`
- Modify: `backend/apps/trends/api/serializers.py`
- Modify: `backend/apps/trends/api/urls.py`
- Test: `backend/tests/trends/test_api_phrases.py`

- [ ] **Step 1: 写失败测试（按平台过滤）**

```python
def test_phrase_list_filters_by_platform(client):
    ...
    response = client.get("/api/phrases/?platform=instagram")
    assert all(item["platform"] == "instagram" for item in response.json()["results"])
```

- [ ] **Step 2: 写失败测试（summary 接口）**

```python
def test_summary_returns_platform_metrics(client):
    response = client.get("/api/summary/?platform=tiktok")
    assert response.status_code == 200
    assert "total_phrases" in response.json()
```

- [ ] **Step 3: 运行测试确认失败**

Run: `..\.venv\Scripts\python.exe -m pytest tests/trends/test_api_phrases.py -q`  
Expected: FAIL

- [ ] **Step 4: 最小实现平台过滤 + summary**

```python
platform = request.query_params.get("platform", "tiktok")
qs = qs.filter(metrics__source_platform=platform)
```

```python
class PlatformSummaryView(APIView):
    def get(self, request):
        ...
```

- [ ] **Step 5: 运行测试确认通过**

Run: `..\.venv\Scripts\python.exe -m pytest tests/trends/test_api_phrases.py -q`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/apps/trends/api/views.py backend/apps/trends/api/serializers.py backend/apps/trends/api/urls.py backend/tests/trends/test_api_phrases.py
git commit -m "feat: add platform-filtered phrase api and summary endpoint"
```

---

### Task 6: 前端单页平台下拉切换与独立展示

**Files:**
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/pages/HotwordsList.vue`
- Modify: `frontend/src/pages/HotwordDetail.vue`

- [ ] **Step 1: 写前端交互验收清单（手工）**

```text
1. 默认 TikTok
2. 切换 Instagram 后列表变化
3. 切换 Facebook 后列表变化
4. 详情页与推荐保持当前平台上下文
```

- [ ] **Step 2: 实现 API 客户端平台参数**

```javascript
export async function fetchPhrases(params) {
  const platform = params.platform || "tiktok";
  ...
}
```

- [ ] **Step 3: 实现列表页平台下拉**

```vue
<select v-model="platformValue" @change="resetToFirstPage">
  <option value="tiktok">TikTok</option>
  <option value="instagram">Instagram</option>
  <option value="facebook">Facebook</option>
</select>
```

- [ ] **Step 4: 请求携带平台参数并展示平台摘要**

```javascript
await fetchPhrases({ platform: platformValue.value, ... })
await fetchSummary({ platform: platformValue.value })
```

- [ ] **Step 5: 构建验证**

Run: `npm.cmd run build`（workdir: `D:\aiFire\frontend`）  
Expected: build 成功

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.js frontend/src/pages/HotwordsList.vue frontend/src/pages/HotwordDetail.vue
git commit -m "feat: add platform dropdown and independent data views"
```

---

### Task 7: 集成验证与回归

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-05-22-apify-multi-platform-design.md`（如需补充已实现差异）

- [ ] **Step 1: 运行后端测试集**

Run: `..\.venv\Scripts\python.exe -m pytest tests/trends -q`（workdir: `D:\aiFire\backend`）  
Expected: 全部 PASS

- [ ] **Step 2: 运行 Django 检查**

Run: `..\.venv\Scripts\python.exe manage.py check`（workdir: `D:\aiFire\backend`）  
Expected: `System check identified no issues`

- [ ] **Step 3: 手工联调**

Run:
- `powershell -ExecutionPolicy Bypass -File D:\aiFire\start-dev.ps1`
- 打开 `http://127.0.0.1:5173/`
- 验证三平台下拉切换、榜单独立、推荐独立

- [ ] **Step 4: 文档更新**

```markdown
## 新增能力
- 三平台独立采集与推荐
- 平台下拉切换展示
- 平台级每日抓取检查点
```

- [ ] **Step 5: Commit**

```bash
git add README.md docs/superpowers/specs/2026-05-22-apify-multi-platform-design.md
git commit -m "docs: update multi-platform usage and verification notes"
```

---

## Self-Review（计划自检）

1. **Spec 覆盖检查**
   - 三平台 Apify 采集：Task 2/3  
   - 平台独立推荐：Task 3/5/6  
   - 单页下拉切换：Task 6  
   - 平台级每日一次：Task 1/4  
   - 保留原功能：Task 3/7 回归验证

2. **占位符检查**
   - 无 `TBD`/`TODO`/“后续补充”占位符；
   - 每个任务均有命令与预期结果。

3. **一致性检查**
   - 平台常量统一为 `tiktok/instagram/facebook`；
   - 测试、API、前端参数名称统一使用 `platform`。

