"""Local PCM16 noise suppression for realtime microphone audio."""

from __future__ import annotations

from dataclasses import dataclass

from sighttalk_api.agent.vad import Pcm16Stats, pcm16_stats


@dataclass(frozen=True)
class NoiseSuppressionConfig:
    """Conservative denoising parameters for low-latency speech input."""

    enabled: bool = True
    attenuation: float = 0.28
    min_noise_rms: float = 120.0
    noise_multiplier: float = 2.4
    noise_smoothing: float = 0.08
    speech_rms: float = 900.0
    speech_peak: int = 2_000


@dataclass(frozen=True)
class NoiseSuppressionResult:
    """Filtered audio plus diagnostics for one PCM chunk."""

    data: bytes
    applied: bool
    raw: Pcm16Stats
    cleaned: Pcm16Stats
    noise_rms: float
    threshold: float


class NoiseSuppressor:
    """Adaptive noise suppressor for 16-bit mono PCM chunks.

    This is intentionally lightweight: it estimates steady background energy and
    attenuates chunks that remain below the adaptive threshold, while leaving
    speech-like chunks untouched. It is not a replacement for RNNoise/Krisp, but
    gives the current direct provider path a safe, dependency-free denoising step.
    """

    def __init__(self, config: NoiseSuppressionConfig | None = None) -> None:
        self._config = config or NoiseSuppressionConfig()
        self._noise_rms = self._config.min_noise_rms

    @property
    def enabled(self) -> bool:
        """Return whether suppression is active."""
        return self._config.enabled

    def process(self, data: bytes) -> NoiseSuppressionResult:
        """Return a denoised PCM chunk, preserving byte length."""
        raw = pcm16_stats(data)
        threshold = max(self._config.min_noise_rms, self._noise_rms * self._config.noise_multiplier)
        if not self._config.enabled or raw.sample_count <= 0 or len(data) % 2 != 0:
            return NoiseSuppressionResult(
                data=data,
                applied=False,
                raw=raw,
                cleaned=raw,
                noise_rms=self._noise_rms,
                threshold=threshold,
            )

        speech_like = raw.rms >= self._config.speech_rms or raw.peak >= self._config.speech_peak
        if not speech_like:
            self._update_noise(raw.rms)
            threshold = max(
                self._config.min_noise_rms,
                self._noise_rms * self._config.noise_multiplier,
            )

        should_attenuate = not speech_like and raw.rms <= threshold
        if not should_attenuate:
            return NoiseSuppressionResult(
                data=data,
                applied=False,
                raw=raw,
                cleaned=raw,
                noise_rms=self._noise_rms,
                threshold=threshold,
            )

        cleaned_data = attenuate_pcm16(data, self._config.attenuation)
        return NoiseSuppressionResult(
            data=cleaned_data,
            applied=True,
            raw=raw,
            cleaned=pcm16_stats(cleaned_data),
            noise_rms=self._noise_rms,
            threshold=threshold,
        )

    def _update_noise(self, rms: float) -> None:
        smoothing = self._config.noise_smoothing
        self._noise_rms = (self._noise_rms * (1 - smoothing)) + (rms * smoothing)


def attenuate_pcm16(data: bytes, factor: float) -> bytes:
    """Scale PCM16 samples by factor, preserving little-endian signed encoding."""
    bounded_factor = min(max(factor, 0.0), 1.0)
    output = bytearray(len(data))
    for offset in range(0, len(data), 2):
        sample = int.from_bytes(data[offset : offset + 2], "little", signed=True)
        scaled = round(sample * bounded_factor)
        output[offset : offset + 2] = scaled.to_bytes(2, "little", signed=True)
    return bytes(output)
