from dataclasses import dataclass, field


@dataclass(frozen=True)
class AudioChunk:
    seq: int
    mime: str
    data: str


@dataclass
class AudioBuffer:
    max_chunks: int = 60
    chunks: list[AudioChunk] = field(default_factory=list)

    def add(self, chunk: AudioChunk) -> None:
        self.chunks.append(chunk)
        if len(self.chunks) > self.max_chunks:
            self.chunks = self.chunks[-self.max_chunks :]

    def collect_until(self, seq_end: int) -> list[AudioChunk]:
        selected = [chunk for chunk in self.chunks if chunk.seq <= seq_end]
        self.chunks = [chunk for chunk in self.chunks if chunk.seq > seq_end]
        return selected

