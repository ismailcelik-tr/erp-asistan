"""Local Turkish speech-to-text (Whisper on Apple MLX)."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import mlx_whisper

__all__ = ["is_ready", "transcribe", "warm_up"]

# Gemma 4's native audio input hung on this Ollama version; Whisper is the fallback.
_MODEL = "mlx-community/whisper-large-v3-turbo"
_LANGUAGE = "tr"

# MLX streams are thread-local: every call must run on the thread that loaded the model.
_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper")
_warm = None


def _run(audio: Path) -> str:
    return mlx_whisper.transcribe(str(audio), path_or_hf_repo=_MODEL, language=_LANGUAGE)["text"].strip()


def transcribe(audio: Path) -> str:
    return _worker.submit(_run, audio).result()


def warm_up(sample: Path) -> None:
    """First call loads weights (~5 s); queue it at startup, not during the demo."""
    global _warm
    _warm = _worker.submit(_run, sample)


def is_ready() -> bool:
    return _warm is not None and _warm.done() and _warm.exception() is None
