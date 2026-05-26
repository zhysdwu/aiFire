from __future__ import annotations

import logging
import tempfile
from pathlib import Path
import subprocess

from django.conf import settings
from django.http import FileResponse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trends.models import Platform
from apps.trends.services.alibaba_tts_client import AlibabaTtsClient, settings_from_env as tts_settings_from_env
from apps.trends.services.alibaba_wanxiang_client import AlibabaWanxiangClient, settings_from_engine_config
from apps.trends.services.digital_human_engines import public_engine_config_payload
from apps.trends.services.digital_human_service import answer_with_digital_human
from apps.trends.services.digital_human_video_service import (
    DigitalHumanVideoError,
    find_ffmpeg_binary,
    generate_digital_human_video,
)

logger = logging.getLogger(__name__)


def _normalize_clone_sample_audio(input_path: str, original_name: str) -> tuple[str, str]:
    suffix = Path(original_name or "").suffix.lower()
    if suffix in {".wav", ".mp3"}:
        return input_path, (original_name or f"sample{suffix}" or "sample.wav")

    ffmpeg = find_ffmpeg_binary()
    if not ffmpeg:
        raise RuntimeError("未找到 ffmpeg，无法将上传音频转换为 wav/mp3")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as converted:
        converted_path = converted.name
    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", input_path, "-vn", "-acodec", "pcm_s16le", "-ar", "24000", "-ac", "1", converted_path],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception:
        Path(converted_path).unlink(missing_ok=True)
        raise
    safe_stem = Path(original_name or "sample").stem or "sample"
    return converted_path, f"{safe_stem}.wav"


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
        logger.info(
            "[视频生成] 收到请求 audio_mode=%s video_mode=%s subtitle_mode=%s config_id=%s has_audio=%s has_video=%s",
            request.data.get("audio_mode") or "default",
            request.data.get("video_mode") or "default",
            request.data.get("subtitle_mode") or "",
            request.data.get("config_id"),
            bool(request.FILES.get("audio_file")),
            bool(request.FILES.get("video_file")),
        )
        try:
            data = generate_digital_human_video(
                script=request.data.get("script") or "",
                audio_mode=request.data.get("audio_mode") or "default",
                video_mode=request.data.get("video_mode") or "default",
                subtitle_mode=request.data.get("subtitle_mode") or "",
                files=request.FILES,
                config_id=request.data.get("config_id"),
                api_key_override=request.data.get("alibaba_api_key"),
            )
        except DigitalHumanVideoError as exc:
            logger.error("[视频生成] 业务失败: %s", exc.message)
            return Response({"status": "failed", "message": exc.message}, status=exc.status_code)
        logger.info("[视频生成] 完成 status=%s", data.get("status"))
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


class DigitalHumanCloneTtsView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        api_key = (request.data.get("alibaba_api_key") or "").strip()
        text = (request.data.get("text") or "").strip()
        sample_file = request.FILES.get("sample_file")
        if not api_key:
            return Response({"message": "请输入阿里云 API Key"}, status=status.HTTP_400_BAD_REQUEST)
        if not sample_file:
            return Response({"message": "请上传声音样本"}, status=status.HTTP_400_BAD_REQUEST)
        if len(text) < 2:
            return Response({"message": "请输入要朗读的文本"}, status=status.HTTP_400_BAD_REQUEST)

        temp_path = ""
        normalized_path = ""
        normalized_name = ""
        suffix = Path(sample_file.name or "sample.wav").suffix or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            for chunk in sample_file.chunks():
                temp.write(chunk)
            temp_path = temp.name
        try:
            client = AlibabaTtsClient(tts_settings_from_env(api_key))
            normalized_path, normalized_name = _normalize_clone_sample_audio(temp_path, sample_file.name or "sample.wav")
            voice_id = client.clone_voice(normalized_path, normalized_name)
            if not voice_id:
                return Response({"message": "声音复刻失败，未返回音色 ID"}, status=status.HTTP_502_BAD_GATEWAY)
            audio_url = client.synthesize(voice_id, text)
            if not audio_url:
                return Response({"message": "语音合成失败，未返回音频 URL"}, status=status.HTTP_502_BAD_GATEWAY)
            return Response(
                {
                    "status": "success",
                    "voice_id": voice_id,
                    "audio_url": audio_url,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return Response({"message": f"声音克隆失败：{str(exc)[:280]}"}, status=status.HTTP_502_BAD_GATEWAY)
        finally:
            try:
                Path(temp_path).unlink(missing_ok=True)
                if normalized_path and normalized_path != temp_path:
                    Path(normalized_path).unlink(missing_ok=True)
            except Exception:
                pass


class DigitalHumanCapabilityCheckView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        api_key = (request.data.get("alibaba_api_key") or "").strip()
        if not api_key:
            return Response({"message": "请输入阿里云 API Key"}, status=status.HTTP_400_BAD_REQUEST)

        tts_client = AlibabaTtsClient(tts_settings_from_env(api_key))
        runtime_cfg = type(
            "RuntimeCfg",
            (),
            {"api_key": api_key, "api_base_url": "", "model_name": "", "voice_id": "", "extra_config": {}},
        )()
        wanxiang_client = AlibabaWanxiangClient(settings_from_engine_config(runtime_cfg))

        clone_ok, clone_msg = tts_client.probe_clone_capability()
        synth_ok, synth_msg = tts_client.probe_synthesis_capability()
        video_ok, video_msg = wanxiang_client.probe_video_capability()

        all_ok = clone_ok and synth_ok and video_ok
        return Response(
            {
                "status": "success" if all_ok else "failed",
                "checks": {
                    "voice_clone": {"ok": clone_ok, "message": clone_msg},
                    "tts_synthesis": {"ok": synth_ok, "message": synth_msg},
                    "wanxiang_video": {"ok": video_ok, "message": video_msg},
                },
            },
            status=status.HTTP_200_OK if all_ok else status.HTTP_400_BAD_REQUEST,
        )
