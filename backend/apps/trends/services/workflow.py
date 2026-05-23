from __future__ import annotations

from django.utils import timezone

from apps.trends.models import DailyWorkflowRun, Platform, WorkflowStatus
from apps.trends.services.analytics import SOCIAL_PLATFORMS


TERMINAL_STATUSES = {WorkflowStatus.SUCCESS, WorkflowStatus.FAILED, WorkflowStatus.SKIPPED}


def get_or_create_today_run(platform: str) -> DailyWorkflowRun:
    run, _ = DailyWorkflowRun.objects.get_or_create(platform=platform, run_date=timezone.localdate())
    return run


def mark_step(platform: str, step: str, status: str, message: str = "") -> DailyWorkflowRun:
    if step not in {"fetch", "extract", "recommend"}:
        raise ValueError(f"Unsupported workflow step: {step}")
    if status not in WorkflowStatus.values:
        raise ValueError(f"Unsupported workflow status: {status}")

    run = get_or_create_today_run(platform)
    setattr(run, f"{step}_status", status)
    if status == WorkflowStatus.RUNNING and not run.started_at:
        run.started_at = timezone.now()
    if status in TERMINAL_STATUSES:
        run.finished_at = timezone.now()
    run.last_message = (message or "")[:255]
    run.save()
    return run


def build_today_workflow_status() -> dict:
    runs = [get_or_create_today_run(platform) for platform in SOCIAL_PLATFORMS]
    return {
        "config": get_pipeline_config(),
        "date": timezone.localdate().isoformat(),
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

import json
from apps.trends.models import RuleConfig, Platform

PIPELINE_CONFIG_KEY = "pipeline_config"
PIPELINE_PLATFORMS = [Platform.TIKTOK, Platform.INSTAGRAM, Platform.FACEBOOK, Platform.YOUTUBE]

DEFAULT_PIPELINE_CONFIG = {
    platform: {"enabled": True, "steps": {"fetch": True, "extract": True, "recommend": True}}
    for platform in PIPELINE_PLATFORMS
}


def get_pipeline_config() -> dict:
    cfg, _ = RuleConfig.objects.get_or_create(
        key=PIPELINE_CONFIG_KEY,
        defaults={"value": DEFAULT_PIPELINE_CONFIG},
    )
    merged = dict(DEFAULT_PIPELINE_CONFIG)
    if isinstance(cfg.value, dict):
        for platform in PIPELINE_PLATFORMS:
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
    for platform in PIPELINE_PLATFORMS:
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
