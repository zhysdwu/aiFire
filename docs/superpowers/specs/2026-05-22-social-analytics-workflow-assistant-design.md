# Social Analytics, Workflow, and AI Assistant Design

## 1. Background

Phase 1 extends the project from a TikTok-only hotword tool into a three-platform system covering TikTok, Instagram, and Facebook. Phase 2 builds on that foundation by making the data easier to understand and act on.

The goal is to turn the product from a keyword list into an operational workspace for content creators and administrators:

1. Compare trends across TikTok, Instagram, and Facebook.
2. Show where each platform is in the daily processing workflow.
3. Add an AI assistant that can explain trends, compare platforms, and help refine titles.

Existing features must remain available: platform-specific rankings, keyword detail pages, AI title recommendation, feedback-based title refinement, admin review, logical deletion, and deletion logs.

## 2. Scope

### Included

- Cross-platform analytics summary.
- Simple chart-ready comparison data.
- Daily workflow status tracking.
- AI assistant endpoint for trend analysis and title/keyword advice.
- Frontend analytics section and assistant panel.

### Not Included

- Full BI dashboard with complex drill-down filters.
- Automated publishing to social platforms.
- A separate workflow engine such as Airflow or Celery.
- A separate digital human avatar renderer.

The "skills digital human" in this phase means an AI assistant experience embedded in the app, focused on trend interpretation, topic selection, and title optimization.

## 3. Recommended Approach

Use a practical workspace approach:

- Keep the existing page structure.
- Add compact analytics blocks above or beside the platform keyword list.
- Add workflow status as a clear platform-by-platform progress strip.
- Add an AI assistant panel that uses current platform context and selected keyword context.

This approach is intentionally smaller than a full BI rebuild, but gives the product a stronger AI and operations feel quickly.

## 4. Data Model

### 4.1 Workflow Status

Create `DailyWorkflowRun` to track each platform's daily process:

- `platform`: `tiktok`, `instagram`, or `facebook`
- `run_date`: local date
- `fetch_status`: `pending`, `running`, `success`, `failed`, `skipped`
- `extract_status`: same status set
- `recommend_status`: same status set
- `last_message`: short readable message
- `started_at`
- `finished_at`
- `updated_at`

Unique key:

- `(platform, run_date)`

This model is lightweight and fits the existing Django management-command style.

### 4.2 Assistant Conversation Log

Create `AssistantMessageLog` for admin/audit visibility:

- `platform`
- `phrase`: nullable foreign key to `Phrase`
- `question`
- `answer`
- `intent`: `trend_analysis`, `platform_compare`, `title_refine`, `general`
- `created_by`: nullable user
- `created_at`

This keeps assistant usage traceable without turning the app into a full chat system.

## 5. Backend Services

### 5.1 Analytics Service

Create an analytics service that reads existing phrase and metric data and returns:

- Per-platform keyword count.
- Per-platform average heat score.
- Per-platform top keywords.
- Per-platform latest update time.
- Cross-platform heat comparison.

The service should not create new business data. It only summarizes existing data.

### 5.2 Workflow Service

Create a workflow helper used by management commands:

- Mark platform step as `running`.
- Mark platform step as `success`.
- Mark platform step as `failed` with message.
- Mark platform step as `skipped` when daily checkpoint says the platform has already run.

This should be called from `ensure_daily_fetch` and `run_daily_pipeline`.

### 5.3 Assistant Service

Create an assistant service around DeepSeek:

- Builds a compact context from platform summary and optional phrase detail.
- Classifies request intent with simple rules first.
- Sends a structured prompt to DeepSeek.
- Falls back to a rule-based response if API key is missing or the model fails.

Supported user questions:

- "Compare TikTok and Instagram today."
- "Which platform is better for beauty content?"
- "Generate 5 titles for this keyword."
- "Explain why this keyword is popular."

## 6. API Design

### 6.1 Analytics API

`GET /api/analytics/overview/`

Response shape:

```json
{
  "platforms": [
    {
      "platform": "tiktok",
      "total_phrases": 50,
      "avg_heat_score": 72.4,
      "top_keywords": ["quiet luxury", "summer outfit"],
      "last_updated_at": "2026-05-22T10:00:00Z"
    }
  ],
  "comparison": {
    "highest_heat_platform": "tiktok",
    "most_keywords_platform": "instagram"
  }
}
```

### 6.2 Workflow API

`GET /api/workflow/status/`

Response shape:

```json
{
  "date": "2026-05-22",
  "runs": [
    {
      "platform": "tiktok",
      "fetch_status": "success",
      "extract_status": "success",
      "recommend_status": "success",
      "last_message": "Completed",
      "updated_at": "2026-05-22T10:00:00Z"
    }
  ]
}
```

### 6.3 Assistant API

`POST /api/assistant/chat/`

Request:

```json
{
  "platform": "instagram",
  "phrase_id": 12,
  "question": "Generate 5 punchier titles for this keyword"
}
```

Response:

```json
{
  "intent": "title_refine",
  "answer": "...",
  "suggestions": ["Compare platforms", "Generate title variants"]
}
```

## 7. Frontend Design

### 7.1 Homepage Analytics Area

Add a compact analytics section to the existing hotwords page:

- Platform comparison row.
- Average heat score by platform.
- Keyword count by platform.
- Top keyword chips per platform.

The page should remain a practical dashboard, not a marketing page.

### 7.2 Workflow Status Strip

Add a three-column workflow strip:

- TikTok
- Instagram
- Facebook

Each platform shows:

- Fetch
- AI Extract
- Recommend

Use simple status labels and compact colors.

### 7.3 AI Assistant Panel

Add a right-side or bottom panel depending on viewport:

- Input field for user question.
- Current platform context.
- Optional current keyword context.
- Answer area.
- Suggested follow-up actions.

The assistant should feel like a working helper, not a decorative chatbot.

## 8. Error Handling

- Analytics endpoint returns empty platform rows when no data exists.
- Workflow endpoint creates missing current-day rows lazily as `pending`.
- Assistant endpoint returns fallback guidance when DeepSeek is unavailable.
- Assistant question must be non-empty and at least 2 characters.
- Frontend shows local error state without blocking keyword browsing.

## 9. Testing Strategy

Backend tests:

- Analytics overview returns all three platforms.
- Workflow status creates or returns current-day records.
- Workflow helper updates step status correctly.
- Assistant endpoint returns fallback response without API key.
- Assistant logs messages.

Frontend validation:

- `npm run build` passes.
- Analytics section renders with empty data and with populated data.
- Workflow strip renders all statuses.
- Assistant panel submits and displays response.

## 10. Acceptance Criteria

1. Homepage displays cross-platform analytics for TikTok, Instagram, and Facebook.
2. Homepage displays daily workflow status per platform.
3. Assistant can answer platform or keyword questions.
4. Assistant gracefully falls back when DeepSeek is unavailable.
5. Existing platform dropdown, ranking list, detail page, deletion, and title feedback remain usable.
6. Backend tests and frontend build pass.

## 11. Future Work

- Add richer charts using a chart library.
- Add scheduled workflow history view.
- Add admin page for assistant logs.
- Add role-specific assistant modes for creator, analyst, and admin.
- Add image/video script generation after title recommendation.
