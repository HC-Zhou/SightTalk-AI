class InMemoryAudioStore:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def save(self, session_id: str, turn_id: int, audio_bytes: bytes) -> str:
        filename = f"{session_id}-turn-{turn_id}.wav"
        self.files[filename] = audio_bytes
        return f"/api/v1/audio/{filename}"

    def get(self, filename: str) -> bytes | None:
        return self.files.get(filename)

