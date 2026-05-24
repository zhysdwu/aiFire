from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


@dataclass
class DigitalHumanVideoError(Exception):
    message: str
    status_code: int = 400


@dataclass(frozen=True)
class GenerationPaths:
    job_id: str
    output_path: Path
    subtitle_path: Path
    upload_dir: Path


@dataclass(frozen=True)
class GenerationResult:
    job_id: str
    status: str
    engine: str
    video_url: str
    download_url: str
    message: str


def digital_human_media_root() -> Path:
    return Path(settings.MEDIA_ROOT) / "digital_human"


def validate_generation_request(*, script: str, audio_mode: str, video_mode: str, files) -> None:
    if len((script or "").strip()) < 2:
        raise DigitalHumanVideoError("请输入至少 2 个字的口播脚本", 400)
    if audio_mode not in {"default", "upload"}:
        raise DigitalHumanVideoError("音频来源必须是 default 或 upload", 400)
    if video_mode not in {"default", "upload"}:
        raise DigitalHumanVideoError("视频来源必须是 default 或 upload", 400)
    if audio_mode == "upload" and not files.get("audio_file"):
        raise DigitalHumanVideoError("请上传音频文件", 400)
    if video_mode == "upload" and not files.get("video_file"):
        raise DigitalHumanVideoError("请上传视频文件", 400)


def build_srt_content(script: str) -> str:
    clean_script = " ".join((script or "").split())
    return f"1\n00:00:00,000 --> 00:00:08,000\n{clean_script}\n"


def build_bilingual_srt_content(script_zh: str, script_en: str) -> str:
    clean_zh = " ".join((script_zh or "").split())
    clean_en = " ".join((script_en or "").split())
    return f"1\n00:00:00,000 --> 00:00:08,000\n{clean_zh}\n{clean_en}\n"


def local_ffmpeg_roots() -> list[Path]:
    project_root = Path(settings.BASE_DIR).parent
    return [
        project_root / "_tools" / "ffmpeg",
        project_root.parent / "_tools" / "ffmpeg",
        Path("D:/openaiskillnew/_tools/ffmpeg"),
    ]


def find_local_ffmpeg_binary() -> str | None:
    executable_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    for root in local_ffmpeg_roots():
        if not root.exists():
            continue
        direct = root / executable_name
        if direct.exists():
            return str(direct)
        matches = sorted(root.rglob(executable_name))
        if matches:
            return str(matches[0])
    return None


def find_ffmpeg_binary() -> str | None:
    configured = os.getenv("FFMPEG_BINARY", "").strip()
    if configured and Path(configured).exists():
        return configured
    return shutil.which("ffmpeg") or find_local_ffmpeg_binary()


def ensure_dirs(paths: GenerationPaths) -> None:
    paths.output_path.parent.mkdir(parents=True, exist_ok=True)
    paths.subtitle_path.parent.mkdir(parents=True, exist_ok=True)
    paths.upload_dir.mkdir(parents=True, exist_ok=True)


def build_paths(job_id: str) -> GenerationPaths:
    root = digital_human_media_root()
    return GenerationPaths(
        job_id=job_id,
        output_path=root / "outputs" / f"{job_id}.mp4",
        subtitle_path=root / "outputs" / f"{job_id}.srt",
        upload_dir=root / "uploads" / job_id,
    )


def validate_upload(file: UploadedFile, allowed_extensions: set[str], label: str) -> None:
    suffix = Path(file.name or "").suffix.lower()
    if suffix not in allowed_extensions:
        raise DigitalHumanVideoError(f"{label}文件类型不支持", 400)
    if file.size and file.size > MAX_UPLOAD_BYTES:
        raise DigitalHumanVideoError(f"{label}文件不能超过 100MB", 400)


def save_upload(file: UploadedFile, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as dest:
        for chunk in file.chunks():
            dest.write(chunk)
    return target


def default_audio_path() -> Path:
    return digital_human_media_root() / "defaults" / "default_audio.wav"


def default_video_path() -> Path:
    return digital_human_media_root() / "defaults" / "default_video.mp4"


def resolve_audio_path(audio_mode: str, files, paths: GenerationPaths) -> Path:
    if audio_mode == "default":
        return default_audio_path()
    audio_file = files["audio_file"]
    validate_upload(audio_file, AUDIO_EXTENSIONS, "音频")
    return save_upload(audio_file, paths.upload_dir / f"input_audio{Path(audio_file.name).suffix.lower()}")


def resolve_video_path(video_mode: str, files, paths: GenerationPaths) -> Path:
    if video_mode == "default":
        return default_video_path()
    video_file = files["video_file"]
    validate_upload(video_file, VIDEO_EXTENSIONS, "视频")
    return save_upload(video_file, paths.upload_dir / f"input_video{Path(video_file.name).suffix.lower()}")


def ensure_default_assets(ffmpeg: str) -> None:
    audio = default_audio_path()
    video = default_video_path()
    audio.parent.mkdir(parents=True, exist_ok=True)
    video.parent.mkdir(parents=True, exist_ok=True)
    if not audio.exists():
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "8", str(audio)],
            check=True,
            capture_output=True,
            text=True,
        )
    if not video.exists():
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=0x113a35:s=720x1280:r=25",
                "-t",
                "8",
                "-vf",
                "drawtext=text='AI Digital Human':fontcolor=white:fontsize=52:x=(w-text_w)/2:y=(h-text_h)/2",
                str(video),
            ],
            check=True,
            capture_output=True,
            text=True,
        )


def media_url_for_output(job_id: str) -> str:
    return f"{settings.MEDIA_URL.rstrip('/')}/digital_human/outputs/{job_id}.mp4"


def run_ffmpeg_composite(
    ffmpeg: str,
    video_path: Path,
    audio_path: Path,
    subtitle_path: Path | None,
    output_path: Path,
) -> None:
    cmd = [
        ffmpeg,
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
    ]
    if subtitle_path is not None:
        subtitle_arg = str(subtitle_path).replace("\\", "/").replace(":", "\\:")
        cmd.extend(["-vf", f"subtitles='{subtitle_arg}'"])
    cmd.extend(
        [
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ]
    )
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def extract_avatar_frame(ffmpeg: str, video_path: Path, image_path: Path) -> Path:
    image_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(image_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return image_path


def engine_config_to_result_dict(config) -> dict:
    return {
        "id": config.id,
        "name": config.name,
        "engine_type": config.engine_type,
        "subtitle_mode": config.subtitle_mode,
    }


def result_with_engine_config(result: dict, *, engine: str, engine_config) -> dict:
    if engine_config is None:
        return result
    return {
        **result,
        "engine": engine,
        "engine_config": engine_config_to_result_dict(engine_config),
    }


def _generate_local_ffmpeg_video_impl(
    *, script: str, audio_mode: str, video_mode: str, files, subtitle_mode: str = "zh"
) -> dict:
    job_id = str(uuid.uuid4())
    paths = build_paths(job_id)
    ensure_dirs(paths)

    ffmpeg = find_ffmpeg_binary()
    if not ffmpeg:
        return {"status": "failed", "message": "生成失败：未找到 ffmpeg，请安装或配置 FFMPEG_BINARY"}

    try:
        ensure_default_assets(ffmpeg)
        audio_path = resolve_audio_path(audio_mode, files, paths)
        video_path = resolve_video_path(video_mode, files, paths)
        subtitle_path = paths.subtitle_path
        if subtitle_mode == "none":
            subtitle_path = None
        elif subtitle_mode == "zh_en":
            subtitle_content = build_bilingual_srt_content(script, script)
            paths.subtitle_path.write_text(subtitle_content, encoding="utf-8")
        else:
            subtitle_content = build_srt_content(script)
            paths.subtitle_path.write_text(subtitle_content, encoding="utf-8")
        run_ffmpeg_composite(ffmpeg, video_path, audio_path, subtitle_path, paths.output_path)
    except DigitalHumanVideoError:
        raise
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip()
        return {"status": "failed", "message": f"生成失败：{message[:240]}"}

    return {
        "job_id": job_id,
        "status": "success",
        "engine": "ffmpeg_composite",
        "video_url": media_url_for_output(job_id),
        "download_url": f"/api/digital-human/videos/{job_id}/download/",
        "message": "生成完成",
    }


def generate_local_ffmpeg_video(*, script: str, audio_mode: str, video_mode: str, files, engine_config=None) -> dict:
    validate_generation_request(script=script, audio_mode=audio_mode, video_mode=video_mode, files=files)
    subtitle_mode = getattr(engine_config, "subtitle_mode", "zh")
    result = _generate_local_ffmpeg_video_impl(
        script=script,
        audio_mode=audio_mode,
        video_mode=video_mode,
        files=files,
        subtitle_mode=subtitle_mode,
    )
    return result_with_engine_config(result, engine="ffmpeg_composite", engine_config=engine_config)


def generate_digital_human_video(*, script: str, audio_mode: str, video_mode: str, files, config_id=None) -> dict:
    validate_generation_request(script=script, audio_mode=audio_mode, video_mode=video_mode, files=files)
    from apps.trends.services.digital_human_engines import get_engine_adapter, resolve_engine_config

    config = resolve_engine_config(config_id)
    adapter = get_engine_adapter(config.engine_type)
    return adapter.generate(
        script=script,
        audio_mode=audio_mode,
        video_mode=video_mode,
        files=files,
        config=config,
    )
