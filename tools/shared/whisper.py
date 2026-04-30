"""
tools/shared/whisper.py — Shared OpenAI Whisper transcription utilities.

Responsibilities:
  - Load a Whisper model and transcribe a WAV file with word-level timestamps.
  - Format the raw Whisper result into a human-readable transcript string.

Used by: tools.media.audio_to_srt
Absorbed from: ../transcribe/transcribe.py
"""

import re
import threading
import time

from rich.console import Console

console = Console()


def transcribe(wav_path: str, model_name: str) -> dict:
    """Load a Whisper model and transcribe wav_path with word-level timestamps.

    Args:
        wav_path:   Path to a 16 kHz mono WAV file.
        model_name: Whisper model size — one of tiny/base/small/medium/large/turbo.

    Returns:
        Whisper result dict with "segments" (each containing "words") and "text".
        Returns {} if no speech was detected.

    Side effects:
        Prints a live elapsed-time spinner to the terminal while transcribing.
    """
    # Deferred import — avoids paying the PyTorch/Whisper startup cost on every
    # CLI invocation. Only loaded when transcription is actually requested.
    import whisper

    console.print(f"[cyan]Loading Whisper model[/cyan] '{model_name}' …")
    model = whisper.load_model(model_name)

    with console.status(
        f"[cyan]Transcribing audio using whisper {model_name} …[/cyan]", spinner="dots"
    ) as status:
        _t0 = time.monotonic()

        def _tick() -> None:
            elapsed = time.monotonic() - _t0
            m, s = divmod(int(elapsed), 60)
            status.update(
                f"[cyan]Transcribing audio using whisper {model_name} …[/cyan]  [dim]{m:02d}:{s:02d}[/dim]"
            )

        _stop = threading.Event()

        def _timer() -> None:
            while not _stop.wait(1):
                _tick()

        _t = threading.Thread(target=_timer, daemon=True)
        _t.start()

        try:
            result = model.transcribe(
                wav_path,
                word_timestamps=True,
                temperature=0.1,
                condition_on_previous_text=False,
                fp16=False,
            )
        finally:
            _stop.set()
            _t.join()
            _elapsed = time.monotonic() - _t0

    _em, _es = divmod(int(_elapsed), 60)

    all_words = [
        word
        for seg in result.get("segments", [])
        for word in seg.get("words", [])
    ]

    if not all_words:
        console.print(f"[green]Transcription complete in {_em:02d}:{_es:02d}.[/green] No speech detected.")
        return {}

    PUNCT = set(".,;?!")
    count = sum(1 for w in all_words if w["word"].rstrip() and w["word"].rstrip()[-1] in PUNCT)
    if all_words and (not all_words[-1]["word"].rstrip() or all_words[-1]["word"].rstrip()[-1] not in PUNCT):
        count += 1

    console.print(f"[green]Transcription complete in {_em:02d}:{_es:02d}.[/green] {count} segment(s) found.")
    return result


def format_transcript(result: dict, plain: bool = False) -> str:
    """Format a Whisper result dict into one sentence per line with MM:SS timestamps.

    Args:
        result: Whisper result dict as returned by transcribe().
        plain:  If True, emit plain text timestamps; if False, use Rich markup.

    Returns:
        A string with one sentence per line, prefixed with a MM:SS timestamp.
    """
    if not result:
        return ""
    all_words = [
        word
        for seg in result.get("segments", [])
        for word in seg.get("words", [])
    ]
    if not all_words:
        return result.get("text", "").strip()

    SENT_END = set(".?!")
    lines = []
    sentence_words: list[str] = []
    sentence_start: float | None = None

    for w in all_words:
        text = w["word"]
        if sentence_start is None:
            sentence_start = w["start"]
        sentence_words.append(text.strip())
        if text.rstrip() and text.rstrip()[-1] in SENT_END:
            m, s = divmod(int(sentence_start), 60)
            ts = f"{m:02d}:{s:02d}"
            prefix = ts if plain else f"[dim]{ts}[/dim]"
            lines.append(f"{prefix}  {_fix_spacing(' '.join(sentence_words))}")
            sentence_words = []
            sentence_start = None

    if sentence_words:
        m, s = divmod(int(sentence_start), 60)  # type: ignore[arg-type]
        ts = f"{m:02d}:{s:02d}"
        prefix = ts if plain else f"[dim]{ts}[/dim]"
        lines.append(f"{prefix}  {_fix_spacing(' '.join(sentence_words))}")

    return "\n".join(lines)


def _fix_spacing(text: str) -> str:
    """Remove spurious spaces before apostrophes in contractions (e.g. 'c 'est' → 'c'est')."""
    return re.sub(r"(\w) (['''])(\w)", r"\1\2\3", text)
