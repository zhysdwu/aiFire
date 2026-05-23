# 数字人视频生成器设计

日期：2026-05-23
状态：已确认

## 1. 背景

项目已有热词列表、AI 趋势助手和悬浮数字人问答能力，但“数字人”目前主要是文本问答和 LiveTalking 播报触发，尚不能生成可下载的视频文件。

本设计新增一个独立“数字人视频”页面，不与热词列表混在同一页面。用户可输入口播内容，选择默认或上传音频，选择默认或上传视频，生成一个可下载的 mp4 文件。第一版采用 FFmpeg 素材合成链路，保证下载闭环稳定；后续再接入 LiveTalking/Wav2Lip 口型同步引擎。

## 2. 范围

### 包含

- 新增前端独立页面 `/digital-human-video`
- 新增全局顶部菜单，提供“热词洞察”和“数字人视频”跳转
- 页面支持输入口播脚本
- 页面支持音频来源：默认音频或上传音频
- 页面支持视频来源：默认视频或上传视频
- 后端生成真实 mp4 文件并提供下载
- 后端提供默认素材兜底
- 生成状态、错误提示、预览和下载按钮

### 不包含

- 第一版不做 LiveTalking/Wav2Lip 口型同步
- 第一版不做生成历史列表
- 第一版不做长任务队列和跨进程后台 worker
- 第一版不做素材库管理页面
- 第一版不做用户级权限隔离和配额管理

## 3. 方案选择

### 3.1 采用方案

采用“独立页面 + FFmpeg 素材合成”的第一阶段方案。

生成逻辑：
1. 用户提交脚本、音频来源、视频来源
2. 后端选择上传素材或默认素材
3. 后端将输入脚本写成字幕文件
4. 后端调用 FFmpeg 合成 mp4
5. API 返回任务状态、预览地址和下载地址

### 3.2 备选方案

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| 热词页内生成面板 | 入口近，适合热词上下文 | 页面拥挤，和用户要求冲突 | 不采用 |
| 独立页面 + FFmpeg 合成 | 最快交付，可下载真实 mp4 | 口型不同步 | 第一版采用 |
| LiveTalking/Wav2Lip 离线生成 | 数字人效果更真实 | 依赖模型/GPU/离线接口改造 | 后续阶段 |

## 4. 前端设计

### 4.1 全局菜单

`App.vue` 从单纯 `RouterView` 升级为应用骨架：

```
┌────────────────────────────────────────┐
│ AI Trend Studio     热词洞察 | 数字人视频 │
└────────────────────────────────────────┘
┌────────────────────────────────────────┐
│ 当前路由页面内容                         │
└────────────────────────────────────────┘
```

菜单项：
- `热词洞察` → `/`
- `数字人视频` → `/digital-human-video`
- 管理员入口仍保留热词页内部现有逻辑，不纳入第一版全局菜单

### 4.2 新页面布局

页面采用工作台布局，而不是营销页：

```
┌─ 数字人视频生成 ─────────────────────────┐
│ 脚本输入                                 │
│ ┌──────────────────────────────────────┐ │
│ │ 输入想让数字人播报的内容               │ │
│ └──────────────────────────────────────┘ │
│                                          │
│ 音频来源  (● 默认音频) (○ 上传音频)       │
│ 视频来源  (● 默认视频) (○ 上传视频)       │
│                                          │
│ [生成视频]                               │
└──────────────────────────────────────────┘

┌─ 生成结果 ───────────────────────────────┐
│ 状态：等待 / 生成中 / 已完成 / 失败        │
│ <video controls src="...">               │
│ [下载 mp4]                               │
└──────────────────────────────────────────┘
```

### 4.3 交互

- 默认脚本为空，少于 2 个字符时禁止生成并提示
- 音频默认选择“默认音频”
- 视频默认选择“默认视频”
- 选择上传音频后显示文件选择控件，限制常见音频格式：`mp3/wav/m4a/aac`
- 选择上传视频后显示文件选择控件，限制常见视频格式：`mp4/mov/webm`
- 点击“生成视频”后按钮进入 loading 状态
- 生成成功后显示视频预览和下载按钮
- 生成失败后展示后端返回的错误信息

## 5. 后端设计

### 5.1 媒体目录

新增 Django 媒体配置：

- `MEDIA_URL = "/media/"`
- `MEDIA_ROOT = BASE_DIR / "media"`

开发环境在 `config/urls.py` 中通过 `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` 暴露媒体文件。

目录结构：

```
backend/media/
  digital_human/
    defaults/
      default_audio.wav
      default_video.mp4
    uploads/
      <uuid>/
        input_audio.ext
        input_video.ext
    outputs/
      <uuid>.mp4
      <uuid>.srt
```

`backend/media/` 已在 `.gitignore` 中忽略。默认素材若不提交到仓库，则由服务在缺失时生成最小可用默认素材。

### 5.2 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `POST /api/digital-human/videos/` | POST multipart | 创建视频生成任务 |
| `GET /api/digital-human/videos/<job_id>/download/` | GET | 下载生成的 mp4 |

第一版同步执行生成，`POST` 返回时即包含结果：

```json
{
  "job_id": "uuid",
  "status": "success",
  "engine": "ffmpeg_composite",
  "video_url": "/media/digital_human/outputs/<uuid>.mp4",
  "download_url": "/api/digital-human/videos/<uuid>/download/",
  "message": "生成完成"
}
```

失败响应：

```json
{
  "status": "failed",
  "message": "生成失败：未找到 ffmpeg"
}
```

### 5.3 请求字段

`POST /api/digital-human/videos/`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `script` | string | 是 | 口播脚本，同时用于字幕 |
| `audio_mode` | string | 是 | `default` 或 `upload` |
| `video_mode` | string | 是 | `default` 或 `upload` |
| `audio_file` | file | 条件必填 | `audio_mode=upload` 时必填 |
| `video_file` | file | 条件必填 | `video_mode=upload` 时必填 |

### 5.4 服务分层

新增 `digital_human_video_service.py`：

- 校验脚本文本和上传文件
- 生成或定位默认素材
- 保存上传素材
- 生成 SRT 字幕
- 调用 FFmpeg 合成视频
- 返回产物路径和下载信息

新增 `DigitalHumanVideoCreateView` 和 `DigitalHumanVideoDownloadView`：

- View 层只负责请求解析、权限、响应格式
- 生成细节放在 service 中

### 5.5 FFmpeg 合成策略

第一版使用保守命令：

1. 以视频为画面源
2. 以音频为声音源
3. 将脚本写入字幕
4. 输出 H.264/AAC mp4
5. 若输入视频短于音频，循环视频画面
6. 若输入视频长于音频，以音频长度截断

服务查找 FFmpeg 的顺序：

1. 环境变量 `FFMPEG_BINARY`
2. 系统 PATH 中的 `ffmpeg`
3. 项目工具目录下可配置路径

如果找不到 FFmpeg，返回明确错误，不假装生成成功。

### 5.6 默认素材

默认素材策略：

- 默认视频：缺失时生成一段简洁的数字人默认形象画面视频
- 默认音频：缺失时生成一段静音音轨
- 用户上传音频或视频时，只替换对应素材，另一个仍可使用默认素材

该策略保证“默认音频 + 默认视频”也能生成可下载 mp4。

## 6. 错误处理

- 脚本过短：`400`，提示“请输入至少 2 个字”
- 上传模式缺少文件：`400`
- 文件类型不支持：`400`
- 文件过大：`400`，第一版限制单文件 100MB
- FFmpeg 不存在：`500`，提示安装或配置路径
- FFmpeg 执行失败：`500`，返回简短错误并记录服务端日志
- 下载不存在的任务：`404`

## 7. 改动清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend/config/settings.py` | 修改 | 增加 `MEDIA_URL` / `MEDIA_ROOT` |
| `backend/config/urls.py` | 修改 | 开发环境暴露 media |
| `backend/apps/trends/services/digital_human_video_service.py` | 新增 | 视频生成核心服务 |
| `backend/apps/trends/api/digital_human_views.py` | 修改 | 增加视频生成和下载视图 |
| `backend/apps/trends/api/urls.py` | 修改 | 增加视频生成路由 |
| `backend/tests/trends/test_digital_human_video.py` | 新增 | 后端 API 和服务测试 |
| `frontend/src/App.vue` | 修改 | 增加全局菜单骨架 |
| `frontend/src/router.js` | 修改 | 增加 `/digital-human-video` 路由 |
| `frontend/src/api/client.js` | 修改 | 增加视频生成 API |
| `frontend/src/pages/DigitalHumanVideo.vue` | 新增 | 独立数字人视频生成页面 |

## 8. 测试策略

### 8.1 后端测试

- `script` 过短返回 `400`
- 默认音频 + 默认视频可生成成功响应
- 上传模式缺失文件返回 `400`
- 不支持的文件类型返回 `400`
- 生成成功后下载接口返回 `video/mp4`
- FFmpeg 缺失时返回明确失败信息

测试中不依赖真实长视频，可 mock FFmpeg 执行或使用最小测试素材。

### 8.2 前端测试

- `npm run build` 通过
- 菜单可从热词页跳转到数字人视频页
- 默认模式下无需选择文件即可提交
- 上传模式下显示对应 file input
- 生成中按钮禁用并显示状态
- 成功后显示 `<video controls>` 和下载按钮
- 失败后显示错误提示

## 9. 后续阶段

- 增加生成历史列表
- 增加任务轮询和后台 worker
- 增加素材库管理
- 接入 LiveTalking/Wav2Lip 离线口型同步
- 接入 TTS，将输入脚本自动生成真实语音
