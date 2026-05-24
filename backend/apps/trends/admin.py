from django import forms
from django.contrib import admin, messages
from django.contrib.admin.sites import NotRegistered
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.shortcuts import render
from django.utils import timezone

from .models import (
    Category,
    DataSourceStatus,
    DeleteReasonType,
    DigitalHumanEngineConfig,
    EvidenceLink,
    GeneratedTitle,
    Phrase,
    PhraseDeleteLog,
    PhraseMetricWindow,
    RuleConfig,
    TikTokRawSnapshot,
)

admin.site.site_header = "AI爆款词管理后台"
admin.site.site_title = "AI爆款词后台"
admin.site.index_title = "管理首页"
admin.site.site_url = "http://127.0.0.1:5173/"


class PhraseSoftDeleteForm(forms.Form):
    reason_type = forms.ChoiceField(
        label="删除理由",
        choices=[
            (DeleteReasonType.INVALID, "无效字段"),
            (DeleteReasonType.ILLEGAL, "非法字段"),
            (DeleteReasonType.DUPLICATE, "重复字段"),
            (DeleteReasonType.CUSTOM, "自定义理由"),
        ],
    )
    custom_reason = forms.CharField(label="自定义理由", required=False, widget=forms.Textarea(attrs={"rows": 3}))


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name_en", "name_zh", "color_hex", "icon", "is_active", "created_at")
    search_fields = ("name_en", "name_zh")
    list_filter = ("is_active",)


@admin.register(Phrase)
class PhraseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "text",
        "language",
        "risk_level",
        "category",
        "is_deleted",
        "deleted_reason_type",
        "first_seen_at",
        "last_seen_at",
    )
    search_fields = ("text",)
    list_filter = ("risk_level", "language", "category", "is_deleted", "deleted_reason_type")
    actions = ["soft_delete_selected", "approve_review_selected", "block_review_selected"]

    @admin.action(description="逻辑删除所选关键词（需填写理由）")
    def soft_delete_selected(self, request, queryset):
        active_qs = queryset.filter(is_deleted=False)

    @admin.action(description="审核通过（→安全）")
    def approve_review_selected(self, request, queryset):
        count = queryset.filter(risk_level="pending_review").update(risk_level="low")
        self.message_user(request, f"已通过 {count} 个待审核词", level=messages.SUCCESS)

    @admin.action(description="屏蔽（→违规）")
    def block_review_selected(self, request, queryset):
        count = queryset.filter(risk_level="pending_review").update(risk_level="blocked")
        self.message_user(request, f"已屏蔽 {count} 个待审核词", level=messages.SUCCESS)
        if "apply" in request.POST:
            form = PhraseSoftDeleteForm(request.POST)
            if form.is_valid():
                reason_type = form.cleaned_data["reason_type"]
                custom_reason = (form.cleaned_data["custom_reason"] or "").strip()
                if reason_type == DeleteReasonType.CUSTOM and not custom_reason:
                    form.add_error("custom_reason", "选择“自定义理由”时必须填写内容。")
                else:
                    now = timezone.now()
                    reason_text = custom_reason if reason_type == DeleteReasonType.CUSTOM else ""
                    updated_count = 0
                    for phrase in active_qs:
                        phrase.is_deleted = True
                        phrase.deleted_at = now
                        phrase.deleted_reason_type = reason_type
                        phrase.deleted_reason_text = reason_text
                        phrase.deleted_by = request.user
                        phrase.save(
                            update_fields=[
                                "is_deleted",
                                "deleted_at",
                                "deleted_reason_type",
                                "deleted_reason_text",
                                "deleted_by",
                            ]
                        )
                        PhraseDeleteLog.objects.create(
                            phrase=phrase,
                            operator=request.user,
                            reason_type=reason_type,
                            reason_text=reason_text,
                        )
                        updated_count += 1
                    self.message_user(request, f"已逻辑删除 {updated_count} 个关键词。", level=messages.SUCCESS)
                    return None
        else:
            form = PhraseSoftDeleteForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "逻辑删除关键词",
            "phrases": active_qs,
            "form": form,
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
            "opts": self.model._meta,
            "queryset": active_qs,
        }
        return render(request, "admin/phrase_soft_delete.html", context)


@admin.register(GeneratedTitle)
class GeneratedTitleAdmin(admin.ModelAdmin):
    list_display = ("id", "phrase", "title", "template", "risk_level", "is_published", "created_at")
    search_fields = ("phrase__text", "title", "caption")
    list_filter = ("template", "risk_level", "is_published")
    actions = ["publish_selected", "unpublish_selected"]

    @admin.action(description="发布所选标题")
    def publish_selected(self, request, queryset):
        queryset.update(is_published=True)

    @admin.action(description="取消发布所选标题")
    def unpublish_selected(self, request, queryset):
        queryset.update(is_published=False)


@admin.register(DigitalHumanEngineConfig)
class DigitalHumanEngineConfigAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "engine_type",
        "is_enabled",
        "is_default",
        "subtitle_mode",
        "model_name",
        "updated_at",
    )
    search_fields = ("name", "engine_type", "model_name", "avatar_id", "voice_id")
    list_filter = ("engine_type", "is_enabled", "is_default", "subtitle_mode")
    fields = (
        "name",
        "engine_type",
        "is_enabled",
        "is_default",
        "api_base_url",
        "api_key",
        "model_name",
        "avatar_id",
        "voice_id",
        "subtitle_mode",
        "default_prompt",
        "extra_config",
    )


admin.site.register(TikTokRawSnapshot)
admin.site.register(EvidenceLink)
admin.site.register(PhraseMetricWindow)
admin.site.register(RuleConfig)


@admin.register(DataSourceStatus)
class DataSourceStatusAdmin(admin.ModelAdmin):
    list_display = (
        "source_key",
        "display_name",
        "platform",
        "last_success",
        "consecutive_failures",
        "last_count",
        "first_failure_at",
        "last_attempt_at",
        "last_success_at",
        "updated_at",
    )
    search_fields = ("source_key", "display_name", "error_message")
    list_filter = ("platform", "last_success")
    readonly_fields = (
        "source_key",
        "display_name",
        "platform",
        "last_attempt_at",
        "last_success_at",
        "last_success",
        "consecutive_failures",
        "last_count",
        "first_failure_at",
        "error_message",
        "updated_at",
    )


try:
    admin.site.unregister(PhraseDeleteLog)
except NotRegistered:
    pass
