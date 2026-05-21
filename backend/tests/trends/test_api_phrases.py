import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.trends.models import Phrase, PhraseMetricWindow, RiskLevel, Window


@pytest.mark.django_db
def test_phrase_list_returns_metrics():
    phrase = Phrase.objects.create(text="quiet luxury", risk_level=RiskLevel.LOW)
    PhraseMetricWindow.objects.create(phrase=phrase, window=Window.H24, heat_score=80)

    client = APIClient()
    response = client.get(reverse("phrase-list"), {"window": Window.H24, "sort": "heat"})

    assert response.status_code == 200
    assert response.data["results"][0]["text"] == "quiet luxury"
    assert response.data["results"][0]["metric"]["heat_score"] == 80


@pytest.mark.django_db
def test_phrase_detail_returns_generated_titles_key():
    phrase = Phrase.objects.create(text="quiet luxury", risk_level=RiskLevel.LOW)

    client = APIClient()
    response = client.get(reverse("phrase-detail", args=[phrase.id]))

    assert response.status_code == 200
    assert "generated_titles" in response.data
