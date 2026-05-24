from django.urls import path

from apps.trends.api.digital_human_views import (
    DigitalHumanChatView,
    DigitalHumanVideoConfigListView,
    DigitalHumanVideoCreateView,
    DigitalHumanVideoDownloadView,
)
from apps.trends.api.views import (
    PhraseReviewActionView,
    PhraseReviewListView,
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
    WorkflowConfigView,
    WorkflowTriggerView,
)

urlpatterns = [
    path("digital-human/chat/", DigitalHumanChatView.as_view(), name="digital-human-chat"),
    path("digital-human/video-configs/", DigitalHumanVideoConfigListView.as_view(), name="digital-human-video-config-list"),
    path("digital-human/videos/", DigitalHumanVideoCreateView.as_view(), name="digital-human-video-create"),
    path("digital-human/videos/<str:job_id>/download/", DigitalHumanVideoDownloadView.as_view(), name="digital-human-video-download"),
    path("session-info/", SessionInfoView.as_view(), name="session-info"),
    path("review/phrases/", PhraseReviewListView.as_view(), name="review-phrase-list"),
    path("review/action/", PhraseReviewActionView.as_view(), name="review-phrase-action"),
    path("phrases/", PhraseListView.as_view(), name="phrase-list"),
    path("summary/", PlatformSummaryView.as_view(), name="platform-summary"),
    path("analytics/overview/", AnalyticsOverviewView.as_view(), name="analytics-overview"),
    path("workflow/status/", WorkflowStatusView.as_view(), name="workflow-status"),
    path("workflow/config/", WorkflowConfigView.as_view(), name="workflow-config"),
    path("workflow/trigger/", WorkflowTriggerView.as_view(), name="workflow-trigger"),
    path("assistant/chat/", AssistantChatView.as_view(), name="assistant-chat"),
    path("phrases/<int:pk>/", PhraseDetailView.as_view(), name="phrase-detail"),
    path("phrases/<int:pk>/soft-delete/", PhraseSoftDeleteView.as_view(), name="phrase-soft-delete"),
    path("phrase-delete-logs/", PhraseDeleteLogListView.as_view(), name="phrase-delete-log-list"),
    path("generated-titles/<int:pk>/feedback/", GeneratedTitleFeedbackView.as_view(), name="generated-title-feedback"),
]
