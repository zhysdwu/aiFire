from django.urls import path

from apps.trends.api.views import (
    GeneratedTitleFeedbackView,
    PhraseDetailView,
    PhraseListView,
    PhraseSoftDeleteView,
    SessionInfoView,
)

urlpatterns = [
    path("session-info/", SessionInfoView.as_view(), name="session-info"),
    path("phrases/", PhraseListView.as_view(), name="phrase-list"),
    path("phrases/<int:pk>/", PhraseDetailView.as_view(), name="phrase-detail"),
    path("phrases/<int:pk>/soft-delete/", PhraseSoftDeleteView.as_view(), name="phrase-soft-delete"),
    path("generated-titles/<int:pk>/feedback/", GeneratedTitleFeedbackView.as_view(), name="generated-title-feedback"),
]
