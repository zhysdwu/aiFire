# Digital Human Engine Admin Design

Date: 2026-05-24
Status: pending user review

## 1. Goal

Upgrade the digital human video generator from a single FFmpeg composite path into an admin-configurable engine system.

The admin must be able to create and edit multiple digital human configurations without changing frontend code. The user-facing generation page must let users choose which enabled configuration to use for each video. The first implementation will build the configuration model, Django Admin management UI, backend engine adapter boundary, public configuration list API, and frontend configuration picker. Real third-party providers such as Jimeng AI, HeyGen, D-ID, or Tavus will be plugged in later once API keys and exact provider documents are available.

This prevents the current placeholder-style output from being mistaken for a real speaking digital human and gives the project a clean path toward engines that can provide human portraits, natural motion, lip-sync speech, and bilingual subtitles.

## 2. Scope

Included in this phase:

- Add a `DigitalHumanEngineConfig` model managed in Django Admin.
- Allow admins to create multiple engine records, enable/disable them, and mark one as the default selection.
- Store provider type, API endpoint, model name, avatar id, voice id, subtitle mode, default prompt, and flexible JSON settings.
- Keep secrets out of the frontend. API keys are stored server-side only.
- Add a backend engine registry/adapter interface.
- Keep existing local FFmpeg generation as the fallback `local_ffmpeg` engine.
- Add placeholder adapters for third-party engine types that return clear configuration errors until credentials/provider docs are supplied.
- Add bilingual subtitle planning as a first-class option even before third-party generation is wired.
- Show enabled digital human configurations on the digital human video page and let the user pick one before generating.

Excluded in this phase:

- No real Jimeng/HeyGen/D-ID/Tavus API call until the exact service, API key, and provider docs are supplied.
- No background task queue.
- No paid provider billing/quota accounting.
- No user-facing admin editing outside Django Admin.
- No custom avatar training workflow.

## 3. Engine Types

The first engine types:

| Engine type | Purpose | First behavior |
| --- | --- | --- |
| `local_ffmpeg` | Current local composite fallback | Generate mp4 from audio/video/subtitles using FFmpeg |
| `jimeng_visual` | Portrait/action visual-video provider | Configurable but returns "provider not connected" until API docs/key are supplied |
| `talking_avatar` | Lip-sync digital human provider such as HeyGen, D-ID, Tavus | Configurable but returns "provider not connected" until API docs/key are supplied |

The design intentionally separates `jimeng_visual` and `talking_avatar` because visual motion generation and precise speech/lip-sync are different product categories. A provider may support both later, but the UI and adapter should not assume that.

## 4. Admin Model

New model: `DigitalHumanEngineConfig`

Fields:

- `name`: display name, for example `Jimeng AI visual video` or `HeyGen talking avatar`
- `engine_type`: choice field: `local_ffmpeg`, `jimeng_visual`, `talking_avatar`
- `is_enabled`: whether this configuration is visible and selectable on the user-facing page
- `is_default`: whether this configuration is selected by default on the user-facing page
- `api_base_url`: optional provider endpoint
- `api_key`: optional secret value stored server-side
- `model_name`: optional provider model name
- `avatar_id`: optional digital human avatar id
- `voice_id`: optional provider voice id
- `subtitle_mode`: choice field: `none`, `zh`, `zh_en`
- `default_prompt`: prompt template for visual providers
- `extra_config`: JSON field for provider-specific parameters
- `created_at`, `updated_at`

Admin behavior:

- List display: name, engine type, enabled flag, default flag, subtitle mode, model name, updated time.
- Search by name, engine type, model name, avatar id.
- Filter by engine type, enabled flag, default flag, subtitle mode.
- API key should not be shown in list display.
- Saving a config with `is_default=True` automatically sets all other engine configs to non-default.
- Disabled configs remain editable in admin but are not returned to the user-facing configuration list API.
- If no enabled config exists, backend falls back to an implicit local FFmpeg engine and the frontend can still generate.

## 5. Backend Adapter Boundary

Add a service layer around engine selection:

```text
generate_digital_human_video()
  -> resolve_engine_config(request.config_id)
  -> get_engine_adapter(config.engine_type)
  -> adapter.generate(request, config)
  -> optional bilingual subtitle post-processing
  -> return job result
```

Adapter interface:

```python
class DigitalHumanEngineAdapter:
    engine_type: str

    def generate(self, request: DigitalHumanVideoRequest, config: DigitalHumanEngineConfig) -> dict:
        ...
```

Request object:

- `script`
- `audio_mode`
- `video_mode`
- `files`
- `subtitle_mode`
- `config_id`
- `job_id`
- `paths`

Adapters:

- `LocalFfmpegEngineAdapter`: wraps the current FFmpeg logic.
- `JimengVisualEngineAdapter`: validates `api_key` and `api_base_url`, then returns a clear not-connected response in this phase.
- `TalkingAvatarEngineAdapter`: validates `api_key` and avatar/voice settings, then returns a clear not-connected response in this phase.

The third-party adapters are placeholders by design. They establish the contract and admin configuration without pretending to generate real provider video before credentials and docs are available.

## 6. Subtitle Design

Subtitle modes:

- `none`: no burned-in subtitles.
- `zh`: Chinese subtitles only.
- `zh_en`: bilingual Chinese and English subtitles.

For this phase:

- The backend should generate a bilingual subtitle structure when `subtitle_mode=zh_en`.
- If no translation provider is configured, English subtitle text can be a clear placeholder derived from the source script only in test/mock paths. Production provider integration should later use a real translation service or LLM.
- Local FFmpeg can burn subtitles into the output mp4.
- Third-party videos, once available later, should be downloaded and passed through the same subtitle post-processing step.

The final video should be a local mp4 download regardless of engine.

## 7. Frontend Changes

Add a public read-only endpoint:

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/digital-human/video-configs/` | GET | Return enabled digital human configs safe for frontend display |

The response must not include `api_key` or other secret values.

Example response:

```json
{
  "configs": [
    {
      "id": 1,
      "name": "Local digital human fallback",
      "engine_type": "local_ffmpeg",
      "engine_label": "Local composite",
      "subtitle_mode": "zh_en",
      "is_default": true
    }
  ],
  "default_config_id": 1
}
```

The digital human video page should show:

- A selectable list/dropdown of enabled digital human configs.
- For each config: name, engine type label, subtitle mode label, and optional short description.
- Default selection based on the admin `is_default` flag.
- A clear message when the selected admin engine is configured but not yet connected.

The frontend should not allow public users to edit API keys or engine config. Creating and editing configurations happens in Django Admin only.

The video creation request adds `config_id`. If omitted, the backend uses the default enabled config. If the supplied config is disabled or missing, the backend returns a clear `400` validation error.

## 8. Error Handling

Errors must be explicit:

- No enabled/default engine: use implicit local FFmpeg fallback.
- Requested config does not exist or is disabled: return `400` with a clear invalid configuration message.
- Selected third-party config has no API key: return `500` with a clear "current digital human engine is missing API key" message.
- Selected third-party config has no provider adapter: return `500` with a clear "current digital human engine is not connected yet" message.
- Provider timeout: return `500` with provider timeout details.
- Provider returns no downloadable video: return `500` with a clear remote generation failure message.
- Subtitle post-processing fails: return `500` with a clear subtitle composition failure message.

The system must never silently fall back from a configured third-party engine to local FFmpeg without saying so. Silent fallback would hide provider configuration problems and make output quality confusing.

## 9. Tests

Backend tests:

- Creating a default engine marks other engines non-default.
- Disabled configs are not returned by the public config list API.
- Without enabled/default config, local FFmpeg fallback is selected.
- Selected local FFmpeg config routes to the existing local generation path.
- Selected `jimeng_visual` config without API key returns a clear configuration error.
- Selected `talking_avatar` config without API key returns a clear configuration error.
- Video generation API response includes selected config name/type.
- Bilingual subtitle mode creates subtitle content containing Chinese and English lines in the expected structure.

Frontend/build tests:

- `npm run build` succeeds.
- The digital human video page renders selectable configs returned by API.
- The selected config id is submitted with video generation requests.
- Provider configuration errors are displayed in the existing error area.

Manual verification:

- In Django Admin, create two configs and mark one default; confirm only one remains default.
- Confirm the user-facing page lists enabled configs and hides disabled configs.
- Generate using a selected local engine config and confirm mp4 download still works.
- Select a Jimeng placeholder config without credentials and confirm the page shows the admin configuration error.

## 10. Rollout

Recommended implementation order:

1. Add model, migration, and admin UI.
2. Add config resolution service and tests.
3. Wrap existing local FFmpeg path behind the adapter.
4. Add placeholder third-party adapters with clear errors.
5. Add public enabled-config list API.
6. Add selected config metadata to generation API response.
7. Show config picker on frontend and submit `config_id`.
8. Add bilingual subtitle structure and tests.

After this phase, the next provider-specific implementation can target one adapter file without changing the admin model or frontend workflow.
