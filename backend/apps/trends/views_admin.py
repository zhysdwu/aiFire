from __future__ import annotations

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.trends.models import DataSourceStatus, Phrase, PhraseDeleteLog, RiskLevel


@staff_member_required
def source_status_view(request):
    failover_after_minutes = 30
    statuses = list(DataSourceStatus.objects.order_by("display_name"))
    context = {
        **admin.site.each_context(request),
        "title": "数据源状态",
        "statuses": statuses,
        "now": timezone.now(),
        "failover_after_minutes": failover_after_minutes,
    }
    return render(request, "admin/source_status.html", context)



@staff_member_required
def review_phrases_view(request):
    from apps.trends.models import Phrase, RiskLevel
    phrases = Phrase.objects.filter(
        is_deleted=False, risk_level=RiskLevel.PENDING_REVIEW
    ).order_by("-created_at")[:100]

    if request.method == "POST":
        phrase_ids = request.POST.getlist("phrase_ids")
        action = request.POST.get("action", "")
        if phrase_ids and action in ("approve", "block"):
            qs = Phrase.objects.filter(
                id__in=phrase_ids, risk_level=RiskLevel.PENDING_REVIEW, is_deleted=False
            )
            if action == "approve":
                updated = qs.update(risk_level=RiskLevel.LOW)
            else:
                updated = qs.update(risk_level=RiskLevel.BLOCKED)
            messages.success(request, f"已处理 {updated} 个关键词")
        return redirect("admin-review-phrases")

    context = {
        **admin.site.each_context(request),
        "title": "AI 审核待办",
        "phrases": phrases,
    }
    return render(request, "admin/review_phrases.html", context)


@staff_member_required
def delete_logs_view(request):
    logs = (
        PhraseDeleteLog.objects.select_related("phrase", "operator")
        .order_by("-created_at")[:300]
    )
    context = {
        **admin.site.each_context(request),
        "title": "删除记录",
        "logs": logs,
    }
    return render(request, "admin/delete_logs.html", context)
