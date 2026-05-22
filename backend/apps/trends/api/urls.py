from django.urls import path

from apps.trends.api.views import (
    AnalyticsOverviewView,
    AssistantChatView,
    GeneratedTitleFeedbackView,
    PhraseDeleteLogListView,
    PhraseDetailView,
    PhraseListView,
    PhraseSoftDeleteView,
    PlatformSummaryView,
    SessionInfoView,
    WorkflowStatusView,
)

urlpatterns = [
    path("session-info/", SessionInfoView.as_view(), name="session-info"),
    path("phrases/", PhraseListView.as_view(), name="phrase-list"),
    path("summary/", PlatformSummaryView.as_view(), name="platform-summary"),
    path("analytics/overview/", AnalyticsOverviewView.as_view(), name="analytics-overview"),
    path("workflow/status/", WorkflowStatusView.as_view(), name="workflow-status"),
    path("assistant/chat/", AssistantChatView.as_view(), name="assistant-chat"),
    path("phrases/<int:pk>/", PhraseDetailView.as_view(), name="phrase-detail"),
    path("phrases/<int:pk>/soft-delete/", PhraseSoftDeleteView.as_view(), name="phrase-soft-delete"),
    path("phrase-delete-logs/", PhraseDeleteLogListView.as_view(), name="phrase-delete-log-list"),
    path("generated-titles/<int:pk>/feedback/", GeneratedTitleFeedbackView.as_view(), name="generated-title-feedback"),
]
