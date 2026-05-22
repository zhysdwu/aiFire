import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.trends.models import Phrase, PhraseMetricWindow, RiskLevel, Window


@pytest.mark.django_db
def test_phrase_list_marks_can_delete_for_staff_only():
    User = get_user_model()
    staff = User.objects.create_user(username="staff", password="pass12345", is_staff=True)
    normal = User.objects.create_user(username="normal", password="pass12345", is_staff=False)

    phrase = Phrase.objects.create(text="quiet luxury", risk_level=RiskLevel.LOW)
    PhraseMetricWindow.objects.create(phrase=phrase, window=Window.H24, heat_score=80)

    client = APIClient()

    client.force_authenticate(user=normal)
    normal_response = client.get(reverse("phrase-list"), {"window": Window.H24, "sort": "heat"})
    assert normal_response.status_code == 200
    assert normal_response.data["results"][0]["can_delete"] is False

    client.force_authenticate(user=staff)
    staff_response = client.get(reverse("phrase-list"), {"window": Window.H24, "sort": "heat"})
    assert staff_response.status_code == 200
    assert staff_response.data["results"][0]["can_delete"] is True
