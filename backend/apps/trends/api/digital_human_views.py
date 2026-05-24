from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.http import FileResponse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trends.models import Platform
from apps.trends.services.digital_human_service import answer_with_digital_human
from apps.trends.services.digital_human_engines import public_engine_config_payload
from apps.trends.services.digital_human_video_service import DigitalHumanVideoError, generate_digital_human_video


class DigitalHumanChatView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        question = (request.data.get("question") or "").strip()
        if len(question) < 2:
            return Response({"detail": "问题太短"}, status=status.HTTP_400_BAD_REQUEST)

        data = answer_with_digital_human(
            platform=request.data.get("platform") or Platform.TIKTOK,
            question=question,
            phrase_id=request.data.get("phrase_id"),
            user=request.user,
        )
        return Response(data, status=status.HTTP_200_OK)


class DigitalHumanVideoCreateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            data = generate_digital_human_video(
                script=request.data.get("script") or "",
                audio_mode=request.data.get("audio_mode") or "default",
                video_mode=request.data.get("video_mode") or "default",
                files=request.FILES,
                config_id=request.data.get("config_id"),
            )
        except DigitalHumanVideoError as exc:
            return Response({"status": "failed", "message": exc.message}, status=exc.status_code)
        http_status = status.HTTP_200_OK if data.get("status") == "success" else status.HTTP_500_INTERNAL_SERVER_ERROR
        return Response(data, status=http_status)


class DigitalHumanVideoConfigListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(public_engine_config_payload(), status=status.HTTP_200_OK)


class DigitalHumanVideoDownloadView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, job_id: str):
        safe_job_id = Path(job_id).name
        output_path = Path(settings.MEDIA_ROOT) / "digital_human" / "outputs" / f"{safe_job_id}.mp4"
        if not output_path.exists():
            return Response({"detail": "视频不存在或已过期"}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(
            output_path.open("rb"),
            as_attachment=True,
            filename=f"digital-human-{safe_job_id}.mp4",
            content_type="video/mp4",
        )
