"""Lightweight local voice activity detection for realtime microphone chunks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

VADEvent = Literal["speech_started", "speech_continued", "speech_stopped", "silence"]


@dataclass(frozen=True)
class LocalVADConfig:
    """Runtime thresholds for conservative local speech detection."""

    min_rms: float = 520.0
    min_peak: int = 1_400
    noise_multiplier: float = 3.2
    speech_start_chunks: int = 1
    speech_stop_chunks: int = 6
    noise_smoothing: float = 0.12


@dataclass(frozen=True)
class Pcm16Stats:
    """Basic signal statistics for a 16-bit PCM chunk."""

    rms: float
    peak: int
    sample_count: int


@dataclass(frozen=True)
class LocalVADResult:
    """Speech decision and diagnostics for one processed audio chunk."""

    event: VADEvent
    speech_detected: bool
    rms: float
    peak: int
    noise_rms: float
    threshold: float


class LocalVAD:
    """Adaptive local VAD without external model dependencies.

    The detector combines an RMS floor, peak floor, and slowly updated ambient
    noise estimate. It is intentionally conservative: a speech start can be fast
    enough for barge-in while sustained silence is required before a stop event.
    """

    def __init__(self, config: LocalVADConfig | None = None) -> None:
        self._config = config or LocalVADConfig()
        self._noise_rms = self._config.min_rms / self._config.noise_multiplier
        self._speaking = False
        self._speech_chunks = 0
        self._silence_chunks = 0

    def reset(self) -> None:
        """Return the detector to its initial non-speaking state."""
        self._speaking = False
        self._speech_chunks = 0
        self._silence_chunks = 0

    def process(self, data: bytes, *, enabled: bool = True) -> LocalVADResult:
        """Classify one PCM16 chunk as speech or non-speech."""
        stats = pcm16_stats(data)
        threshold = max(self._config.min_rms, self._noise_rms * self._config.noise_multiplier)
        candidate = enabled and stats.rms >= threshold and stats.peak >= self._config.min_peak

        if candidate:
            self._speech_chunks += 1
            self._silence_chunks = 0
        else:
            self._speech_chunks = 0
            self._silence_chunks += 1
            self._update_noise(stats.rms)

        if not self._speaking and self._speech_chunks >= self._config.speech_start_chunks:
            self._speaking = True
            return self._result("speech_started", True, stats, threshold)

        if self._speaking:
            if self._silence_chunks >= self._config.speech_stop_chunks:
                self._speaking = False
                return self._result("speech_stopped", False, stats, threshold)
            return self._result("speech_continued", candidate, stats, threshold)

        return self._result("silence", False, stats, threshold)

    def _update_noise(self, rms: float) -> None:
        smoothing = self._config.noise_smoothing
        self._noise_rms = (self._noise_rms * (1 - smoothing)) + (rms * smoothing)

    def _result(
        self,
        event: VADEvent,
        speech_detected: bool,
        stats: Pcm16Stats,
        threshold: float,
    ) -> LocalVADResult:
        return LocalVADResult(
            event=event,
            speech_detected=speech_detected,
            rms=stats.rms,
            peak=stats.peak,
            noise_rms=self._noise_rms,
            threshold=threshold,
        )


def pcm16_stats(data: bytes) -> Pcm16Stats:
    """Return RMS and peak values for little-endian signed PCM16 bytes."""
    sample_count = len(data) // 2
    if sample_count <= 0:
        return Pcm16Stats(rms=0.0, peak=0, sample_count=0)

    total_square = 0
    peak = 0
    for index in range(sample_count):
        offset = index * 2
        sample = int.from_bytes(data[offset : offset + 2], "little", signed=True)
        abs_sample = abs(sample)
        peak = max(peak, abs_sample)
        total_square += sample * sample
    return Pcm16Stats(
        rms=(total_square / sample_count) ** 0.5,
        peak=peak,
        sample_count=sample_count,
    )
