# AI 热词合法性检测与审核队列设计

日期：2026-05-23
状态：已确认

## 1. 背景

现有风险检测仅靠 6 个正则模式匹配（nazi/kkk/cocaine/heroin/adult/nsfw/porn），覆盖范围极窄。需要引入 AI（DeepSeek）做语义级合法性判断，并将存疑词推给管理员审核。

## 2. 范围

### 包含
- RiskLevel 新增 `pending_review`
- AI 批量检测服务（DeepSeek）
- extract 步骤末尾嵌入 AI 检测
- Django Admin 审核 action
- 前端排除 pending_review 词

### 不包含
- 独立审核页面
- 审核历史日志（Admin 内置日志已覆盖）
- 实时检测
- 通知机制

## 3. 风险等级扩展

| 等级 | 值 | 前端展示 | 来源 |
|------|-----|---------|------|
| `low` | `pending_review` | 不展示 | AI 判定安全 |
| `pending_review` | 新增 | 不展示 | AI 不确定，推审核 |
| `blocked` | 已有 | 不展示 | AI 或规则命中违规 |

## 4. AI 检测服务

### 4.1 Prompt 设计

系统提示：内容安全审核员。判断英文关键词是否涉及政治敏感、仇恨言论、暴力极端、成人/色情、毒品/违禁品、侵权品牌。

输出格式：`{"keyword": {"verdict": "SAFE|REVIEW|BLOCK", "reason": "简短理由"}}`

### 4.2 批量策略

每批 30 个词，减少 API 调用。仅检测当日新入库的 `risk_level=low` 词（已 blocked 的跳过）。

### 4.3 映射

- `SAFE` → `risk_level = low`
- `REVIEW` → `risk_level = pending_review`
- `BLOCK` → `risk_level = blocked`

## 5. Admin 审核流程

Admin 列表按 `risk_level` 筛选 `pending_review`，提供两个 action：
- **审核通过** → 改 `risk_level = low`
- **屏蔽** → 改 `risk_level = blocked`

## 6. 改动清单

| 文件 | 改动 |
|------|------|
| `models.py` | RiskLevel 新增 PENDING_REVIEW |
| `services/risk.py` | 新增 ai_batch_assess() |
| `management/commands/run_daily_pipeline.py` | extract 末尾调用 AI |
| `admin.py` | 新增审核 action |
| `api/views.py` | queryset 排除 pending_review |

## 7. 测试策略

- AI 返回 SAFE 时正确设置 risk_level=low
- AI 返回 REVIEW 时正确设置 risk_level=pending_review
- AI 返回 BLOCK 时正确设置 risk_level=blocked
- API 无密钥时回退到规则检测
- Admin action 正确审核
- 前端不展示 pending_review 和 blocked 词
