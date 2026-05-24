# Generated manually for digital human engine configuration.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trends", "0013_alter_generatedtitle_risk_level_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="DigitalHumanEngineConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128)),
                (
                    "engine_type",
                    models.CharField(
                        choices=[
                            ("local_ffmpeg", "Local FFmpeg"),
                            ("jimeng_visual", "Jimeng visual"),
                            ("talking_avatar", "Talking avatar"),
                        ],
                        default="local_ffmpeg",
                        max_length=32,
                    ),
                ),
                ("is_enabled", models.BooleanField(default=True)),
                ("is_default", models.BooleanField(default=False)),
                ("api_base_url", models.URLField(blank=True, default="")),
                ("api_key", models.CharField(blank=True, default="", max_length=255)),
                ("model_name", models.CharField(blank=True, default="", max_length=128)),
                ("avatar_id", models.CharField(blank=True, default="", max_length=128)),
                ("voice_id", models.CharField(blank=True, default="", max_length=128)),
                (
                    "subtitle_mode",
                    models.CharField(
                        choices=[
                            ("none", "No subtitles"),
                            ("zh", "Chinese subtitles"),
                            ("zh_en", "Chinese and English subtitles"),
                        ],
                        default="zh_en",
                        max_length=16,
                    ),
                ),
                ("default_prompt", models.TextField(blank=True, default="")),
                ("extra_config", models.JSONField(blank=True, default=dict)),
                (
                    "default_unique_key",
                    models.GeneratedField(
                        db_persist=True,
                        expression=models.Case(
                            models.When(is_default=True, then=models.Value(1)),
                            default=models.Value(None),
                            output_field=models.IntegerField(),
                        ),
                        null=True,
                        output_field=models.IntegerField(),
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-is_default", "name"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("default_unique_key",),
                        name="unique_default_digital_human_engine_config",
                    )
                ],
            },
        ),
    ]
