import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_session_info_allows_admin_and_rejects_normal_user():
    User = get_user_model()
    admin_user = User.objects.create_user(username="admin_user", password="pass12345", is_staff=True)
    normal_user = User.objects.create_user(username="normal_user", password="pass12345", is_staff=False)

    client = APIClient()

    client.force_authenticate(user=admin_user)
    admin_response = client.get(reverse("session-info"))
    assert admin_response.status_code == 200
    assert admin_response.data["is_admin"] is True
    assert admin_response.data["username"] == "admin_user"

    client.force_authenticate(user=normal_user)
    normal_response = client.get(reverse("session-info"))
    assert normal_response.status_code == 403
