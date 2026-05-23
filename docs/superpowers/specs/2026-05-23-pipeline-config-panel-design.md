# 管道配置面板设计

日期：2026-05-23
状态：已确认

## 1. 背景

项目已有每日管道（fetch → extract → recommend）和 `DailyWorkflowRun` 追踪模型，前端 intelligence board 展示各平台步骤状态。但当前管道是硬编码的，无法：
- 按平台开关管道
- 跳过某个步骤
- 手动触发单个步骤

本设计在现有基础设施上增加配置驱动能力和交互面板，不改动管道核心逻辑。

## 2. 范围

### 包含
- 管道配置存储（RuleConfig JSON）
- 配置读写 API（GET/PATCH）
- 单步触发 API
- 前端 workflow 卡片升级为可交互面板
- 平台开关、步骤独立触发按钮

### 不包含
- 步骤顺序调整（只有 3 步，调整无实际意义）
- 自定义步骤/新步骤类型
- 拖拽交互
- 执行历史页面（现有信息足够）

## 3. 后端设计

### 3.1 配置模型

复用现有 `RuleConfig` 模型，`key = "pipeline_config"`，`value` 为 JSON：

```json
{
  "tiktok":    { "enabled": true,  "steps": { "fetch": true, "extract": true, "recommend": true } },
  "instagram": { "enabled": true,  "steps": { "fetch": true, "extract": true, "recommend": true } },
  "facebook":  { "enabled": false, "steps": { "fetch": true, "extract": true, "recommend": false } },
  "youtube":   { "enabled": true,  "steps": { "fetch": true, "extract": true, "recommend": true } }
}
```

默认值在首次读取时自动创建（lazy init）。

### 3.2 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `GET /api/workflow/config/` | GET | 读取管道配置 |
| `PATCH /api/workflow/config/` | PATCH | 更新管道配置（管理员 only） |
| `POST /api/workflow/trigger/` | POST | 手动触发某平台某步（`{platform, step}`） |
| `GET /api/workflow/status/` | GET | 已有，不变，增加 `steps_enabled` 字段 |

### 3.3 管道执行增强

`run_daily_pipeline` 命令执行前：
1. 读取 `pipeline_config`
2. `enabled = false` 的平台整体跳过，所有步骤标记 `skipped`
3. `steps.xxx = false` 的步骤跳过，标记 `skipped`
4. 其余步骤正常执行

### 3.4 单步触发

`trigger` 端点：
- 校验 `platform` 和 `step` 合法性
- 调用 `run_daily_pipeline` 中对应步骤的内部函数
- 不阻塞：异步返回，前端轮询 `/api/workflow/status/` 获取进展

## 4. 前端设计

### 4.1 布局

现有 `.board-card-wide` 卡片内，将静态状态展示改为交互式面板：

```
┌─ 每日管道状态 ──────────────────────────────────┐
│                                                  │
│  TikTok                          [启用 ●]        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ 📥 抓取   │→│ 🔍 提取   │→│ ✨ 推荐   │       │
│  │ ✓ 已成功  │ │ ✓ 已成功  │ │ ✓ 已成功  │       │
│  │ [重新执行]│ │ [重新执行]│ │ [重新执行]│       │
│  └──────────┘  └──────────┘  └──────────┘       │
│                                                  │
│  Instagram                      [启用 ●]        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ 📥 抓取   │→│ 🔍 提取   │→│ ⏳ 等待   │       │
│  │ ✓ 已成功  │ │ ⏳ 等待中  │ │ ⏳ 等待中  │       │
│  │ [重新执行]│ │ [立即执行]│ │ [立即执行]│       │
│  └──────────┘  └──────────┘  └──────────┘       │
│                                                  │
│  Facebook                       [停用 ○]        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ 📥 抓取   │→│ 🔍 提取   │→│ ✨ 推荐   │       │
│  │ ⊘ 已跳过  │ │ ⊘ 已跳过  │ │ ⊘ 已跳过  │       │
│  └──────────┘  └──────────┘  └──────────┘       │
│                                                  │
│  YouTube                        [启用 ●]        │
│  ...                                             │
│                                                  │
│  [一键执行全部启用平台]                            │
└──────────────────────────────────────────────────┘
```

### 4.2 交互

- **平台开关**：toggle 按钮，立即 PATCH 配置，关闭后所有步骤显示 `⊘ 已跳过`
- **单步按钮**：`pending`/`failed` 步骤显示「立即执行」，`success` 显示「重新执行」
- **一键执行**：底部按钮，触发所有启用平台 + 启用步骤
- **状态刷新**：步骤执行期间每 3 秒轮询 `/api/workflow/status/`

### 4.3 状态颜色

- `success`：绿色 ✓
- `running`：蓝色动画 ⟳
- `pending`：灰色 ⏳
- `failed`：红色 ✗
- `skipped`：灰色 ⊘

## 5. 改动清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend/apps/trends/services/workflow.py` | 修改 | 增加配置读写函数、skip 逻辑 |
| `backend/apps/trends/api/urls.py` | 修改 | 新增 config/trigger 路由 |
| `backend/apps/trends/api/views.py` | 修改 | 新增 config/trigger 视图 |
| `backend/apps/trends/management/commands/run_daily_pipeline.py` | 修改 | 执行前读取配置，按配置跳过 |
| `frontend/src/api/client.js` | 修改 | 新增 API 调用函数 |
| `frontend/src/pages/HotwordsList.vue` | 修改 | workflow 卡片交互升级 |

## 6. 测试策略

- 配置 API 返回默认配置（无数据时 lazy init）
- 配置 PATCH 正确更新并返回
- 关闭平台后管道跳过该平台所有步骤
- 关闭某步骤后该步骤标记 skipped
- 单步触发正确执行并更新状态
- 前端开关和按钮正确调用 API
- `npm run build` 通过
