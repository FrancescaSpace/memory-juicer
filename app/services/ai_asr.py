"""语音转写封装（阿里云百炼 Paraformer 实时语音识别）。

浏览器录音得到的是 webm/opus，Paraformer 只吃 wav/pcm/mp3 等格式，
所以这里先用 imageio-ffmpeg 自带的静态 ffmpeg 做一次「转 16k 单声道 wav」，
用户无需在 Windows 上手工安装 ffmpeg。
"""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AsrResult:
    text: str
    provider: str
    ok: bool
    error: str = ""


def _ffmpeg_exe() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def to_wav16k(src: Path) -> Path:
    """把任意音频转成 16kHz 单声道 wav，返回新文件路径。"""
    dst = src.with_name(src.stem + "_16k.wav")
    proc = subprocess.run(
        [
            _ffmpeg_exe(),
            "-y",
            "-loglevel", "error",
            "-i", str(src),
            "-ac", "1",
            "-ar", "16000",
            "-f", "wav",
            str(dst),
        ],
        capture_output=True,
    )
    if proc.returncode != 0 or not dst.exists():
        raise RuntimeError(f"音频转码失败: {proc.stderr.decode('utf-8', 'ignore')[:300]}")
    return dst


def _extract_text(result: object) -> str:
    text = ""
    try:
        sentences = result.get_sentence()  # type: ignore[attr-defined]
        if isinstance(sentences, dict):
            sentences = [sentences]
        if sentences:
            text = "".join(
                s.get("text", "") for s in sentences if isinstance(s, dict)
            )
    except Exception:
        pass

    if not text:
        output = getattr(result, "output", None)
        if isinstance(output, dict):
            for key in ("text", "sentence", "sentences"):
                value = output.get(key)
                if isinstance(value, str):
                    text = value
                    break
                if isinstance(value, list):
                    text = "".join(
                        item.get("text", "") if isinstance(item, dict) else str(item)
                        for item in value
                    )
                    break
    return text.strip()


def transcribe(audio_path: Path) -> AsrResult:
    if not settings.ai_enabled:
        logger.info("ASR 跳过：未配置 DASHSCOPE_API_KEY（离线模式）")
        return AsrResult(
            text="",
            provider="offline",
            ok=False,
            error="未配置 DASHSCOPE_API_KEY，请直接把文字打出来",
        )

    try:
        import dashscope
        from dashscope.audio.asr import Recognition
    except ImportError:
        logger.warning("ASR 跳过：未安装 dashscope SDK")
        return AsrResult(text="", provider="offline", ok=False, error="未安装 dashscope SDK")

    wav_path: Path | None = None
    try:
        wav_path = to_wav16k(audio_path) if audio_path.suffix.lower() != ".wav" else audio_path

        dashscope.api_key = settings.dashscope_api_key
        logger.info("ASR 请求 model=%s file=%s", settings.asr_model, wav_path.name)
        recognition = Recognition(
            model=settings.asr_model,
            format="wav",
            sample_rate=16000,
        )
        result = recognition.call(str(wav_path))
        status = getattr(result, "status_code", 200)
        if status != 200:
            msg = getattr(result, "message", "")
            logger.warning("ASR 返回异常 status=%s message=%s", status, msg)
            if status in (401, 403):
                error = "API Key 无效或已过期，语音无法转写。请重新配置 DASHSCOPE_API_KEY，或直接打字回答。"
            else:
                error = f"语音识别失败（{status}）：{msg}"
            return AsrResult(text="", provider="offline", ok=False, error=error)

        text = _extract_text(result)
        if not text:
            logger.info("ASR 完成但没有识别出内容")
            return AsrResult(
                text="",
                provider=settings.asr_model,
                ok=False,
                error="没有识别出内容，可能是录音太短或环境太吵",
            )
        logger.info("ASR 成功 status=200 chars=%d", len(text))
        return AsrResult(text=text, provider=settings.asr_model, ok=True)
    except Exception as exc:
        logger.warning("ASR 调用异常: %s", exc)
        return AsrResult(text="", provider="offline", ok=False, error=f"语音识别失败: {exc}")
    finally:
        if wav_path and wav_path != audio_path and wav_path.exists():
            wav_path.unlink(missing_ok=True)