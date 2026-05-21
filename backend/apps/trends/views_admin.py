from __future__ import annotations

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone

from apps.trends.models import DataSourceStatus, PhraseDeleteLog


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
