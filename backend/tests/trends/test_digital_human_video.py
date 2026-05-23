from django.conf import settings


def test_media_settings_are_configured():
    assert settings.MEDIA_URL == "/media/"
    assert settings.MEDIA_ROOT.name == "media"
