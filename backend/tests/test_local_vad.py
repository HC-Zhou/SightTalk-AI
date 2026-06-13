from __future__ import annotations

from sighttalk_api.agent.vad import LocalVAD, LocalVADConfig, pcm16_stats


def pcm16_chunk(sample: int, *, count: int = 1_600) -> bytes:
    return b"".join(sample.to_bytes(2, "little", signed=True) for _ in range(count))


def test_pcm16_stats_reports_rms_and_peak() -> None:
    stats = pcm16_stats(pcm16_chunk(2_000, count=4))

    assert stats.sample_count == 4
    assert stats.rms == 2_000
    assert stats.peak == 2_000


def test_local_vad_detects_speech_start_and_stop() -> None:
    vad = LocalVAD(LocalVADConfig(speech_stop_chunks=2))

    assert vad.process(pcm16_chunk(0)).event == "silence"
    speech = vad.process(pcm16_chunk(3_000))

    assert speech.event == "speech_started"
    assert speech.speech_detected

    assert vad.process(pcm16_chunk(0)).event == "speech_continued"
    stopped = vad.process(pcm16_chunk(0))

    assert stopped.event == "speech_stopped"
    assert not stopped.speech_detected


def test_local_vad_can_be_disabled_by_media_policy() -> None:
    vad = LocalVAD()

    result = vad.process(pcm16_chunk(6_000), enabled=False)

    assert result.event == "silence"
    assert not result.speech_detected
