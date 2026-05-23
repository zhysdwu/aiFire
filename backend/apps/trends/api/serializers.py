from rest_framework import serializers

from apps.trends.models import EvidenceLink, GeneratedTitle, Phrase, PhraseDeleteLog, PhraseMetricWindow


class EvidenceLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvidenceLink
        fields = ("url", "title", "fetched_at")


class GeneratedTitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedTitle
        fields = (
            "id",
            "title",
            "caption",
            "template",
            "risk_level",
            "is_published",
            "feedback_text",
            "ai_reply",
            "refined_count",
            "created_at",
        )


class PhraseMetricWindowSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhraseMetricWindow
        fields = ("window", "heat_score", "growth_prev_window", "growth_vs_7d_avg", "score_explain", "computed_at")


class PhraseListSerializer(serializers.ModelSerializer):
    metric = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = Phrase
        fields = ("id", "text", "platform", "risk_level", "metric", "can_delete")

    def get_metric(self, obj: Phrase):
        window = self.context.get("window")
        if not window:
            return None
        metric = obj.metrics.filter(window=window).first()
        if metric:
            return PhraseMetricWindowSerializer(metric).data
        fallback = obj.metrics.order_by("-computed_at").first()
        if fallback:
            return PhraseMetricWindowSerializer(fallback).data
        return None

    def get_can_delete(self, obj: Phrase) -> bool:
        user = self.context.get("request").user if self.context.get("request") else None
        return bool(user and user.is_authenticated and user.is_staff)


class PhraseDetailSerializer(serializers.ModelSerializer):
    metrics = PhraseMetricWindowSerializer(many=True)
    evidences = EvidenceLinkSerializer(many=True)
    generated_titles = serializers.SerializerMethodField()

    class Meta:
        model = Phrase
        fields = ("id", "text", "platform", "risk_level", "metrics", "evidences", "generated_titles")

    def get_generated_titles(self, obj: Phrase):
        qs = obj.generated_titles.filter(is_published=True).order_by("-created_at")[:3]
        return GeneratedTitleSerializer(qs, many=True).data


class PhraseDeleteLogSerializer(serializers.ModelSerializer):
    phrase_text = serializers.CharField(source="phrase.text", read_only=True)
    operator_username = serializers.CharField(source="operator.username", read_only=True)
    reason_label = serializers.CharField(source="get_reason_type_display", read_only=True)

    class Meta:
        model = PhraseDeleteLog
        fields = ("id", "phrase_text", "operator_username", "reason_type", "reason_label", "reason_text", "created_at")
