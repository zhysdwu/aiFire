import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.trends.models import DeleteReasonType, Phrase, PhraseDeleteLog, Platform, RiskLevel


@pytest.mark.django_db
def test_phrase_delete_logs_are_admin_only():
    User = get_user_model()
    admin_user = User.objects.create_user(username="admin_user", password="pass12345", is_staff=True)
    normal_user = User.objects.create_user(username="normal_user", password="pass12345", is_staff=False)
    phrase = Phrase.objects.create(text="quiet luxury", platform=Platform.TIKTOK, risk_level=RiskLevel.LOW)
    PhraseDeleteLog.objects.create(
        phrase=phrase,
        operator=admin_user,
        reason_type=DeleteReasonType.INVALID,
    )

    client = APIClient()

    client.force_authenticate(user=normal_user)
    normal_response = client.get(reverse("phrase-delete-log-list"))
    assert normal_response.status_code == 403

    client.force_authenticate(user=admin_user)
    admin_response = client.get(reverse("phrase-delete-log-list"))
    assert admin_response.status_code == 200
    assert admin_response.data["results"][0]["phrase_text"] == "quiet luxury"
    assert admin_response.data["results"][0]["operator_username"] == "admin_user"
    assert admin_response.data["results"][0]["reason_type"] == DeleteReasonType.INVALID
