from __future__ import annotations

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trends.models import Platform
from apps.trends.services.digital_human_service import answer_with_digital_human


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
