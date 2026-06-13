from __future__ import annotations

from sighttalk_api.agent.noise import NoiseSuppressionConfig, NoiseSuppressor
from sighttalk_api.agent.vad import pcm16_stats


def pcm16_chunk(sample: int, *, count: int = 1_600) -> bytes:
    return b"".join(sample.to_bytes(2, "little", signed=True) for _ in range(count))


def test_noise_suppressor_attenuates_quiet_background_pcm() -> None:
    suppressor = NoiseSuppressor(
        NoiseSuppressionConfig(
            attenuation=0.25,
            min_noise_rms=120,
            noise_multiplier=2.4,
        )
    )
    noise = pcm16_chunk(160)

    result = suppressor.process(noise)

    assert result.applied
    assert len(result.data) == len(noise)
    assert pcm16_stats(result.data).rms < pcm16_stats(noise).rms


def test_noise_suppressor_preserves_speech_like_pcm() -> None:
    suppressor = NoiseSuppressor()
    speech = pcm16_chunk(3_000)

    result = suppressor.process(speech)

    assert not result.applied
    assert result.data == speech


def test_noise_suppressor_can_be_disabled() -> None:
    suppressor = NoiseSuppressor(NoiseSuppressionConfig(enabled=False))
    noise = pcm16_chunk(160)

    result = suppressor.process(noise)

    assert not result.applied
    assert result.data == noise
