from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trends.api.serializers import GeneratedTitleSerializer, PhraseDetailSerializer, PhraseListSerializer
from apps.trends.models import DeleteReasonType, GeneratedTitle, Phrase, PhraseDeleteLog, RiskLevel, Window
from apps.trends.services.deepseek_client import DeepSeekClient


class PhraseListView(generics.ListAPIView):
    serializer_class = PhraseListSerializer

    def get_queryset(self):
        request = self.request
        window = request.query_params.get("window", Window.H24)
        sort = request.query_params.get("sort", "heat")
        q = request.query_params.get("q", "").strip()
        risk = request.query_params.get("risk", "").strip()

        qs = Phrase.objects.filter(is_deleted=False)
        if q:
            qs = qs.filter(text__icontains=q)
        if risk in {RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH}:
            qs = qs.filter(risk_level=risk)

        qs = qs.exclude(risk_level=RiskLevel.BLOCKED)

        if sort == "new":
            return qs.order_by("-created_at")

        if sort in {"heat", "growth", "ai"}:
            qs = qs.filter(metrics__window=window)
            if sort in {"heat", "ai"}:
                return qs.order_by("-metrics__heat_score").distinct()
            return qs.order_by("-metrics__growth_prev_window").distinct()

        return qs.order_by("-created_at")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["window"] = self.request.query_params.get("window", Window.H24)
        return ctx


class PhraseDetailView(generics.RetrieveAPIView):
    queryset = Phrase.objects.exclude(risk_level=RiskLevel.BLOCKED).filter(is_deleted=False).prefetch_related(
        "metrics", "evidences", "generated_titles"
    )
    serializer_class = PhraseDetailSerializer


class SessionInfoView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        user = request.user
        return Response(
            {
                "is_authenticated": bool(user and user.is_authenticated),
                "is_admin": bool(user and user.is_authenticated and user.is_staff),
                "username": user.username if user and user.is_authenticated else "",
            }
        )


class PhraseSoftDeleteView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk: int):
        reason_type = (request.data.get("reason_type") or "").strip()
        custom_reason = (request.data.get("custom_reason") or "").strip()
        valid_types = {DeleteReasonType.INVALID, DeleteReasonType.ILLEGAL, DeleteReasonType.DUPLICATE}

        if reason_type not in valid_types:
            return Response({"detail": "必须选择删除理由"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            phrase = Phrase.objects.get(pk=pk, is_deleted=False)
        except Phrase.DoesNotExist:
            return Response({"detail": "关键词不存在或已删除"}, status=status.HTTP_404_NOT_FOUND)

        phrase.is_deleted = True
        phrase.deleted_at = timezone.now()
        phrase.deleted_reason_type = reason_type
        phrase.deleted_reason_text = custom_reason
        phrase.deleted_by = request.user
        phrase.save(update_fields=["is_deleted", "deleted_at", "deleted_reason_type", "deleted_reason_text", "deleted_by"])

        PhraseDeleteLog.objects.create(
            phrase=phrase,
            operator=request.user,
            reason_type=reason_type,
            reason_text=custom_reason,
        )

        return Response({"detail": "删除成功"}, status=status.HTTP_200_OK)


class GeneratedTitleFeedbackView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk: int):
        feedback = (request.data.get("feedback") or "").strip()
        if len(feedback) < 2:
            return Response({"detail": "反馈内容太短"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            item = GeneratedTitle.objects.get(pk=pk)
        except GeneratedTitle.DoesNotExist:
            return Response({"detail": "推荐不存在"}, status=status.HTTP_404_NOT_FOUND)

        fallback_title = f"{item.title} | {feedback[:20]}"
        fallback_caption = f"根据反馈优化：{feedback[:60]}"
        ai_reply = "已根据你的反馈优化推荐语气与切入角度。"

        try:
            client = DeepSeekClient.from_env()
            payload = client.chat_json(
                system=(
                    "You are a TikTok copywriting assistant. "
                    "Given original title/caption and user feedback, rewrite them. "
                    "Return JSON: {\"title\":\"...\",\"caption\":\"...\",\"reply\":\"...\"}."
                ),
                user=(
                    f"ORIGINAL_TITLE: {item.title}\\n"
                    f"ORIGINAL_CAPTION: {item.caption}\\n"
                    f"USER_FEEDBACK: {feedback}"
                ),
            )
            new_title = (payload.get("title") or fallback_title).strip()[:120]
            new_caption = (payload.get("caption") or fallback_caption).strip()[:180]
            ai_reply = (payload.get("reply") or ai_reply).strip()
        except Exception:
            new_title = fallback_title[:120]
            new_caption = fallback_caption[:180]

        item.title = new_title
        item.caption = new_caption
        item.feedback_text = feedback
        item.ai_reply = ai_reply
        item.refined_count = (item.refined_count or 0) + 1
        item.save(update_fields=["title", "caption", "feedback_text", "ai_reply", "refined_count"])

        return Response(GeneratedTitleSerializer(item).data, status=status.HTTP_200_OK)
