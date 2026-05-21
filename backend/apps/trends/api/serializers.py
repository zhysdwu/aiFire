from rest_framework import serializers

from apps.trends.models import EvidenceLink, GeneratedTitle, Phrase, PhraseMetricWindow


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

    class Meta:
        model = Phrase
        fields = ("id", "text", "risk_level", "metric")

    def get_metric(self, obj: Phrase):
        window = self.context.get("window")
        if not window:
            return None
        metric = obj.metrics.filter(window=window).first()
        if not metric:
            return None
        return PhraseMetricWindowSerializer(metric).data


class PhraseDetailSerializer(serializers.ModelSerializer):
    metrics = PhraseMetricWindowSerializer(many=True)
    evidences = EvidenceLinkSerializer(many=True)
    generated_titles = serializers.SerializerMethodField()

    class Meta:
        model = Phrase
        fields = ("id", "text", "risk_level", "metrics", "evidences", "generated_titles")

    def get_generated_titles(self, obj: Phrase):
        qs = obj.generated_titles.filter(is_published=True).order_by("-created_at")[:3]
        return GeneratedTitleSerializer(qs, many=True).data
