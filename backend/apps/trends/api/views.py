from django.db.models import Avg, F, OuterRef, Subquery, F, OuterRef, Subquery
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import generics, permissions, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trends.api.serializers import (
    GeneratedTitleSerializer,
    PhraseDeleteLogSerializer,
    PhraseDetailSerializer,
    PhraseListSerializer,
)
from apps.trends.models import DeleteReasonType, GeneratedTitle, Phrase, PhraseDeleteLog, PhraseMetricWindow, Platform, RiskLevel, Window
from apps.trends.services.analytics import build_analytics_overview
from apps.trends.services.assistant import answer_assistant_question, normalize_platform
from apps.trends.services.deepseek_client import DeepSeekClient
from apps.trends.services.workflow import build_today_workflow_status


SOCIAL_PLATFORMS = {Platform.TIKTOK, Platform.INSTAGRAM, Platform.FACEBOOK, Platform.YOUTUBE}


def normalize_social_platform(value: str) -> str:
    platform = (value or Platform.TIKTOK).strip().lower()
    return platform if platform in SOCIAL_PLATFORMS else Platform.TIKTOK


class PhraseListView(generics.ListAPIView):
    serializer_class = PhraseListSerializer

    def get_queryset(self):
        request = self.request
        window = request.query_params.get("window", Window.H24)
        sort = request.query_params.get("sort", "heat")
        q = request.query_params.get("q", "").strip()
        risk = request.query_params.get("risk", "").strip()
        platform = normalize_social_platform(request.query_params.get("platform", Platform.TIKTOK))

        qs = Phrase.objects.filter(is_deleted=False, platform=platform)
        if q:
            qs = qs.filter(text__icontains=q)
        if risk in {RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH}:
            qs = qs.filter(risk_level=risk)

        qs = qs.exclude(risk_level__in=[RiskLevel.BLOCKED, RiskLevel.PENDING_REVIEW])

        if sort == "new":
            return qs.order_by("-created_at")

        if sort in {"heat", "growth", "ai"}:
            metric_sq = PhraseMetricWindow.objects.filter(
                phrase=OuterRef("pk"), window=window
            )
            qs = qs.annotate(
                _heat_score=Subquery(metric_sq.values("heat_score")[:1]),
                _growth=Subquery(metric_sq.values("growth_prev_window")[:1]),
            )
            if sort in {"heat", "ai"}:
                return qs.order_by(F("_heat_score").desc(nulls_last=True))
            return qs.order_by(F("_growth").desc(nulls_last=True))

        return qs.order_by("-created_at")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["window"] = self.request.query_params.get("window", Window.H24)
        return ctx


class PhraseDetailView(generics.RetrieveAPIView):
    queryset = Phrase.objects.exclude(risk_level__in=[RiskLevel.BLOCKED, RiskLevel.PENDING_REVIEW]).filter(is_deleted=False).prefetch_related(
        "metrics", "evidences", "generated_titles"
    )
    serializer_class = PhraseDetailSerializer


class PlatformSummaryView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        platform = normalize_social_platform(request.query_params.get("platform", Platform.TIKTOK))
        phrases = Phrase.objects.filter(is_deleted=False, platform=platform).exclude(risk_level__in=[RiskLevel.BLOCKED, RiskLevel.PENDING_REVIEW])
        metrics = phrases.filter(metrics__window=Window.H24).aggregate(avg_heat=Avg("metrics__heat_score"))
        top_keywords = list(phrases.order_by("-last_seen_at", "-created_at").values_list("text", flat=True)[:5])
        last_updated_at = phrases.order_by("-last_seen_at").values_list("last_seen_at", flat=True).first()
        return Response(
            {
                "platform": platform,
                "total_phrases": phrases.count(),
                "avg_heat_score": round(float(metrics.get("avg_heat") or 0), 2),
                "top_keywords": top_keywords,
                "last_updated_at": last_updated_at,
            }
        )


class AnalyticsOverviewView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(build_analytics_overview())


class WorkflowStatusView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(build_today_workflow_status())


class AssistantChatView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        question = (request.data.get("question") or "").strip()
        if len(question) < 2:
            return Response({"detail": "问题太短"}, status=status.HTTP_400_BAD_REQUEST)

        phrase_id = request.data.get("phrase_id")
        if phrase_id in {"", None}:
            phrase_id = None
        elif not str(phrase_id).isdigit():
            phrase_id = None
        return Response(
            answer_assistant_question(
                normalize_platform(request.data.get("platform") or Platform.TIKTOK),
                question,
                phrase_id,
                request.user,
            )
        )


@method_decorator(never_cache, name="dispatch")
class SessionInfoView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]

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


class PhraseDeleteLogListView(generics.ListAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]
    serializer_class = PhraseDeleteLogSerializer

    def get_queryset(self):
        return PhraseDeleteLog.objects.select_related("phrase", "operator").order_by("-created_at")


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
                    'Return JSON: {"title":"...","caption":"...","reply":"..."}.'
                ),
                user=(
                    f"ORIGINAL_TITLE: {item.title}\n"
                    f"ORIGINAL_CAPTION: {item.caption}\n"
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


class PhraseReviewListView(generics.ListAPIView):
    """管理员查看待审核关键词列表"""
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]
    serializer_class = PhraseListSerializer

    def get_queryset(self):
        return Phrase.objects.filter(
            is_deleted=False, risk_level=RiskLevel.PENDING_REVIEW
        ).order_by("-created_at")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["window"] = self.request.query_params.get("window", Window.H24)
        return ctx


class PhraseReviewActionView(APIView):
    """管理员审核操作：通过或屏蔽"""
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        phrase_ids = request.data.get("phrase_ids", [])
        action = (request.data.get("action") or "").strip().lower()
        if action not in ("approve", "block"):
            return Response(
                {"detail": "action must be approve or block"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(phrase_ids, list) or not phrase_ids:
            return Response(
                {"detail": "phrase_ids is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = Phrase.objects.filter(
            id__in=phrase_ids, risk_level=RiskLevel.PENDING_REVIEW, is_deleted=False
        )
        if action == "approve":
            updated = qs.update(risk_level=RiskLevel.LOW)
        else:
            updated = qs.update(risk_level=RiskLevel.BLOCKED)
        return Response({"updated": updated}, status=status.HTTP_200_OK)

class WorkflowConfigView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from apps.trends.services.workflow import get_pipeline_config
        return Response(get_pipeline_config())

    def patch(self, request):
        if not request.user or not request.user.is_authenticated or not request.user.is_staff:
            return Response({"detail": "需要管理员权限"}, status=status.HTTP_403_FORBIDDEN)
        from apps.trends.services.workflow import update_pipeline_config
        config = request.data
        if not isinstance(config, dict):
            return Response({"detail": "配置格式错误"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(update_pipeline_config(config))

class WorkflowTriggerView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        from apps.trends.models import WorkflowStatus
        from apps.trends.services.workflow import mark_step

        platform = (request.data.get("platform") or "").strip().lower()
        step = (request.data.get("step") or "").strip().lower()
        valid_steps = {"fetch", "extract", "recommend"}

        if platform not in SOCIAL_PLATFORMS:
            return Response({"detail": "不支持的平台"}, status=status.HTTP_400_BAD_REQUEST)
        if step not in valid_steps:
            return Response({"detail": "不支持的步骤"}, status=status.HTTP_400_BAD_REQUEST)

        mark_step(platform, step, WorkflowStatus.RUNNING, f"手动触发 {step}")

        try:
            from io import StringIO
            from django.core.management import call_command
            out = StringIO()
            source = (request.data.get("source") or "official").strip().lower()
            if source not in {"official", "all", "legacy"}:
                source = "official"

            call_command(
                "run_daily_pipeline",
                "--source",
                source,
                "--region",
                "US",
                "--limit",
                "60",
                stdout=out,
            )
            output = out.getvalue()
            mark_step(platform, step, WorkflowStatus.SUCCESS, output[:255])
            return Response({"status": "success", "platform": platform, "step": step, "message": output[:255]})
        except Exception as exc:
            mark_step(platform, step, WorkflowStatus.FAILED, str(exc)[:255])
            return Response({"status": "failed", "platform": platform, "step": step, "message": str(exc)[:255]},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
