from dataclasses import dataclass, field


@dataclass(frozen=True)
class FrameItem:
    seq: int
    captured_at: int
    mime: str
    data: str
    width: int | None = None
    height: int | None = None
    size_bytes: int | None = None


@dataclass
class FrameBuffer:
    max_frames: int = 12
    frames: list[FrameItem] = field(default_factory=list)

    def add(self, frame: FrameItem) -> None:
        self.frames.append(frame)
        if len(self.frames) > self.max_frames:
            self.frames = self.frames[-self.max_frames :]

    def recent(self) -> list[FrameItem]:
        return list(self.frames)

