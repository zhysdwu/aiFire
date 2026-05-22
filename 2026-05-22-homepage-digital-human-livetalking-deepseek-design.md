# 首页数字人（LiveTalking + DeepSeek）设计文档

## 1. 背景与目标

当前项目首页已具备 AI 问答面板、跨平台分析与工作流状态能力，但“数字人”仍主要表现为文本助手，尚未完成与 `LiveTalking` 的真正联动。

本次目标是在首页数字人位置实现可用的“文本问答 + 数字人播报”体验，并满足以下已确认约束：

1. 交互形态：文本驱动型（用户文本提问，系统回答并播报）。
2. 回答风格：简洁结论型（1 条结论 + 3 条要点）。
3. 入口形式：悬浮入口（右下角按钮，点击展开面板）。
4. 方案选择：后端聚合层方案（方案 B）。

## 2. 范围定义

### 2.1 本阶段包含

- 首页新增悬浮数字人入口与对话面板组件。
- 新增后端聚合接口：`POST /api/digital-human/chat/`。
- 聚合层内部串联 DeepSeek 回答生成与 LiveTalking 播报触发。
- 会话日志与追踪字段（`trace_id`）落库与可观测性增强。
- 异常与降级策略落地（DeepSeek 失败降级、LiveTalking 失败不阻断主链路）。

### 2.2 本阶段不包含

- 语音输入（ASR）与全双工语音对话。
- 数字人复杂情绪控制、角色系统、口型精细化调参。
- 多轮会话记忆编排引擎（仅保留轻量会话标识与日志）。
- 独立数字人直播编排页面。

## 3. 总体架构

采用“前端单入口 + 后端聚合编排”的结构：

1. 前端仅调用 `POST /api/digital-human/chat/`。
2. 后端聚合层完成参数校验、意图识别、DeepSeek 调用、结果规范化、日志写入、LiveTalking 播报触发。
3. 接口以文本结果优先返回，LiveTalking 作为非阻塞播报能力。
4. 保留既有 `/api/assistant/chat/` 兼容路径，不直接作为首页数字人主入口。

该架构优先保证稳定交付与后续扩展边界清晰。

## 4. 组件与接口设计

### 4.1 前端组件

新增首页组件：`FloatingDigitalHuman.vue`

组件职责：

- 悬浮按钮：展开/收起数字人面板。
- 输入区：接收文本问题。
- 回答区：渲染“结论 + 3 要点”。
- 状态区：展示播报状态（进行中、失败、跳过等）。

交互原则：

- 默认收起，不遮挡首页核心信息。
- 发送问题后进入 loading；返回即刻显示文本回答。
- LiveTalking 异常仅提示，不清空已返回答案。

### 4.2 聚合接口

`POST /api/digital-human/chat/`

请求字段：

- `platform`：`tiktok|instagram|facebook|youtube`，默认 `tiktok`。
- `question`：用户问题，必填，最少 2 字符。
- `phrase_id`：可选，热词上下文。
- `session_id`：可选，前端会话标识。

响应字段：

- `answer`：最终回答文本（简洁结论型）。
- `highlights`：3 条要点数组。
- `intent`：识别意图（如 `trend_analysis`）。
- `provider`：`deepseek|fallback`。
- `livetalking`：`{ status, message }`。
- `trace_id`：链路追踪标识。

### 4.3 后端服务分层

- `digital_human_service.py`：聚合编排核心。
- `assistant_core.py`：提示词模板、响应解析、输出规范化。
- `livetalking_client.py`：LiveTalking 调用封装（HTTP/本地服务统一入口）。

## 5. 数据流设计

1. 前端提交 `platform/question/phrase_id/session_id`。
2. 接口层生成 `trace_id` 并校验参数。
3. 聚合层调用 DeepSeek，要求结构化输出“1 结论 + 3 要点”。
4. 写入会话日志（含 provider、intent、trace_id）。
5. 异步触发 LiveTalking 播报任务。
6. 立即返回文本答案与 `livetalking.status`。

关键原则：文本回答是主链路；播报能力不阻塞主链路。

## 6. 异常处理与降级策略

### 6.1 异常处理

- `question` 无效：返回 `400` 与明确提示。
- `phrase_id` 非法：忽略上下文继续处理。
- DeepSeek 调用失败：捕获异常并降级。
- LiveTalking 调用失败：记录错误并返回 `livetalking.status=failed`。
- 日志写入失败：不影响主响应，保留服务端错误日志。

### 6.2 降级策略

1. 一级降级：DeepSeek 失败，返回模板化简洁回答（`provider=fallback`）。
2. 二级降级：LiveTalking 不可用，仅保留文本回答（前端提示播报不可用）。
3. 三级降级：聚合接口超时，前端保留重试入口并展示 `trace_id`。

## 7. 测试与验收标准

### 7.1 后端测试

- 正常请求返回 `answer/highlights/provider/livetalking/trace_id`。
- 短问题返回 `400`。
- DeepSeek 异常返回 `provider=fallback`。
- LiveTalking 异常不影响 `200` 主响应。
- 非法 `phrase_id` 不中断主流程。
- 日志记录包含 `trace_id/platform/question/provider`。

### 7.2 前端测试

- 悬浮入口展开/收起正确。
- 提交问题后的 loading 与禁用状态正确。
- 回答区渲染结论与 3 条要点。
- 播报失败提示为非阻塞态。
- 移动端布局不遮挡核心操作。

### 7.3 验收标准

1. 首页存在悬浮数字人入口且可展开。
2. 文本提问后稳定返回简洁结论型回答。
3. DeepSeek 不可用时可自动降级并可读。
4. LiveTalking 不可用时不影响文本问答主链路。
5. 链路可追踪（`trace_id` + 会话日志）。
6. 现有热词与管理功能无回归。

## 8. 迭代建议（下一阶段）

- 增加语音输入（ASR）并升级为语音问答。
- 增加多轮上下文记忆与用户偏好。
- 增加数字人播报队列可视化与重试机制。
- 对接运营模式（定时播报与专题模板）。
