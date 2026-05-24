from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trends", "0014_digitalhumanengineconfig"),
    ]

    operations = [
        migrations.AlterField(
            model_name="digitalhumanengineconfig",
            name="engine_type",
            field=models.CharField(
                choices=[
                    ("local_ffmpeg", "Local FFmpeg"),
                    ("jimeng_visual", "Jimeng visual"),
                    ("talking_avatar", "Talking avatar"),
                    ("alibaba_wanxiang", "Alibaba Wanxiang"),
                ],
                default="local_ffmpeg",
                max_length=32,
            ),
        ),
    ]
