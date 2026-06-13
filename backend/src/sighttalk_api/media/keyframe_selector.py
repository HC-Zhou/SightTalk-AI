from sighttalk_api.media.frame_buffer import FrameItem


def select_keyframes(frames: list[FrameItem], limit: int) -> list[FrameItem]:
    if limit <= 0:
        return []
    return frames[-limit:]

