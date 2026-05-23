from django.test import TestCase
from rest_framework.test import APIClient
from apps.trends.models import RiskLevel, Phrase, Platform, RuleConfig
from apps.trends.services.risk import apply_ai_verdict, ai_batch_assess
from apps.trends.services.workflow import get_pipeline_config, update_pipeline_config, PIPELINE_CONFIG_KEY


class AIRiskAssessmentTests(TestCase):
    def test_apply_safe_verdict(self):
        result = apply_ai_verdict("test", {"verdict": "SAFE", "reason": ""}, RiskLevel.LOW)
        self.assertEqual(result, RiskLevel.LOW)

    def test_apply_review_verdict(self):
        result = apply_ai_verdict("test", {"verdict": "REVIEW", "reason": "borderline"}, RiskLevel.LOW)
        self.assertEqual(result, RiskLevel.PENDING_REVIEW)

    def test_apply_block_verdict(self):
        result = apply_ai_verdict("test", {"verdict": "BLOCK", "reason": "violates policy"}, RiskLevel.LOW)
        self.assertEqual(result, RiskLevel.BLOCKED)

    def test_respects_existing_high_risk(self):
        result = apply_ai_verdict("test", {"verdict": "SAFE", "reason": ""}, RiskLevel.HIGH)
        self.assertEqual(result, RiskLevel.HIGH)

    def test_unknown_verdict_defaults_safe(self):
        result = apply_ai_verdict("test", {"verdict": "UNKNOWN", "reason": ""}, RiskLevel.LOW)
        self.assertEqual(result, RiskLevel.LOW)

    def test_ai_batch_empty(self):
        result = ai_batch_assess([])
        self.assertEqual(result, {})


class PipelineConfigServiceTests(TestCase):
    def test_get_default_config(self):
        RuleConfig.objects.filter(key=PIPELINE_CONFIG_KEY).delete()
        cfg = get_pipeline_config()
        self.assertIn(Platform.TIKTOK, cfg)
        self.assertTrue(cfg[Platform.TIKTOK]["enabled"])
        self.assertTrue(cfg[Platform.TIKTOK]["steps"]["fetch"])

    def test_update_and_read_config(self):
        new_cfg = {Platform.TIKTOK: {"enabled": False, "steps": {"fetch": True, "extract": False, "recommend": True}}}
        result = update_pipeline_config(new_cfg)
        self.assertFalse(result[Platform.TIKTOK]["enabled"])
        cfg = get_pipeline_config()
        self.assertFalse(cfg[Platform.TIKTOK]["enabled"])

    def test_partial_update_preserves_other_platforms(self):
        update_pipeline_config({Platform.TIKTOK: {"enabled": False}})
        cfg = get_pipeline_config()
        self.assertFalse(cfg[Platform.TIKTOK]["enabled"])
        self.assertTrue(cfg[Platform.INSTAGRAM]["enabled"])


class PipelineConfigAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_get_config_returns_200(self):
        response = self.client.get("/api/workflow/config/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(Platform.TIKTOK, response.data)

    def test_trigger_invalid_step_returns_400(self):
        response = self.client.post("/api/workflow/trigger/", {
            "platform": Platform.TIKTOK, "step": "invalid_step"
        }, format="json")
        self.assertEqual(response.status_code, 400)


class PhraseAPIExclusionTests(TestCase):
    def setUp(self):
        self.safe = Phrase.objects.create(text="safe word", platform=Platform.TIKTOK, risk_level=RiskLevel.LOW)
        self.pending = Phrase.objects.create(text="pending word", platform=Platform.TIKTOK, risk_level=RiskLevel.PENDING_REVIEW)
        self.blocked = Phrase.objects.create(text="blocked word", platform=Platform.TIKTOK, risk_level=RiskLevel.BLOCKED)

    def test_excludes_pending_review_and_blocked(self):
        qs = Phrase.objects.exclude(risk_level__in=[RiskLevel.BLOCKED, RiskLevel.PENDING_REVIEW])
        ids = set(qs.values_list("id", flat=True))
        self.assertIn(self.safe.id, ids)
        self.assertNotIn(self.pending.id, ids)
        self.assertNotIn(self.blocked.id, ids)
