"""In-process worker bus scaffolding for future agent runtime orchestration."""

from __future__ import annotations

import heapq
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from sighttalk_api.agent.frames import Frame


class FrameProcessor(Protocol):
    """Processes one frame and optionally emits follow-up frames."""

    async def process(self, frame: Frame) -> Sequence[Frame]:
        raise NotImplementedError


class ProcessorPipeline:
    """Ordered frame processor pipeline."""

    def __init__(self, processors: Iterable[FrameProcessor]) -> None:
        self._processors = tuple(processors)

    async def process(self, frame: Frame) -> list[Frame]:
        """Run processors sequentially and collect emitted frames."""
        emitted: list[Frame] = []
        current_frames = [frame]
        for processor in self._processors:
            next_frames: list[Frame] = []
            for current in current_frames:
                outputs = await processor.process(current)
                next_frames.extend(outputs)
            emitted.extend(next_frames)
            current_frames = next_frames or current_frames
        return emitted


class BaseWorker:
    """Base class for phase-1 workers with activation and subscriptions."""

    def __init__(self, *, worker_id: str, subscriptions: Iterable[str]) -> None:
        self.worker_id = worker_id
        self.subscriptions = frozenset(subscriptions)
        self.active = False

    async def start(self) -> None:
        """Activate the worker."""
        self.active = True

    async def stop(self) -> None:
        """Deactivate the worker."""
        self.active = False

    def accepts(self, frame: Frame) -> bool:
        """Return whether this worker should receive a frame."""
        return frame.type in self.subscriptions and self.active

    async def handle_frame(self, frame: Frame) -> Sequence[Frame]:
        """Handle a routed frame. Subclasses can return follow-up frames."""
        return ()


class PipelineWorker(BaseWorker):
    """Worker that delegates each frame to a processor pipeline."""

    def __init__(
        self,
        *,
        worker_id: str,
        subscriptions: Iterable[str],
        pipeline: ProcessorPipeline,
    ) -> None:
        super().__init__(worker_id=worker_id, subscriptions=subscriptions)
        self._pipeline = pipeline

    async def handle_frame(self, frame: Frame) -> Sequence[Frame]:
        """Process the frame through the configured pipeline."""
        return await self._pipeline.process(frame)


class WorkerRegistry:
    """Registry of worker ids, subscriptions, and activation state."""

    def __init__(self) -> None:
        self._workers: dict[str, BaseWorker] = {}

    def register(self, worker: BaseWorker) -> None:
        """Register or replace a worker by id."""
        self._workers[worker.worker_id] = worker

    def get(self, worker_id: str) -> BaseWorker | None:
        """Return a registered worker by id."""
        return self._workers.get(worker_id)

    def workers_for(self, frame: Frame) -> list[BaseWorker]:
        """Return active subscribers for a frame, respecting frame target."""
        if frame.target is not None:
            worker = self._workers.get(frame.target)
            if worker is None or not worker.accepts(frame):
                return []
            return [worker]
        return [worker for worker in self._workers.values() if worker.accepts(frame)]

    async def start_all(self) -> None:
        """Start all registered workers."""
        for worker in self._workers.values():
            await worker.start()

    async def stop_all(self) -> None:
        """Stop all registered workers."""
        for worker in self._workers.values():
            await worker.stop()


@dataclass(order=True)
class _QueuedFrame:
    priority: int
    sequence: int
    frame: Frame = field(compare=False)


@dataclass(frozen=True)
class DispatchResult:
    """Result of dispatching one frame."""

    frame: Frame
    delivered_to: tuple[str, ...]


class WorkerBus:
    """Priority queue and router for in-process agent frames."""

    def __init__(self, registry: WorkerRegistry) -> None:
        self._registry = registry
        self._queue: list[_QueuedFrame] = []
        self._sequence = 0

    @property
    def pending_count(self) -> int:
        """Number of queued frames."""
        return len(self._queue)

    def publish(self, frame: Frame) -> None:
        """Queue a frame for later dispatch."""
        self._sequence += 1
        heapq.heappush(
            self._queue,
            _QueuedFrame(priority=int(frame.priority), sequence=self._sequence, frame=frame),
        )

    def cancel_interruptible(self) -> int:
        """Drop interruptible queued frames while preserving system/cleanup frames."""
        kept: list[_QueuedFrame] = []
        cancelled = 0
        for item in self._queue:
            if item.frame.interruptible:
                cancelled += 1
            else:
                kept.append(item)
        heapq.heapify(kept)
        self._queue = kept
        return cancelled

    def peek_next(self) -> Frame | None:
        """Return the next queued frame without removing it."""
        if not self._queue:
            return None
        return self._queue[0].frame

    async def dispatch_next(self) -> DispatchResult | None:
        """Dispatch the next frame to active matching workers."""
        if not self._queue:
            return None
        item = heapq.heappop(self._queue)
        workers = self._registry.workers_for(item.frame)
        delivered_to: list[str] = []
        for worker in workers:
            outputs = await worker.handle_frame(item.frame)
            delivered_to.append(worker.worker_id)
            for output in outputs:
                self.publish(output)
        return DispatchResult(frame=item.frame, delivered_to=tuple(delivered_to))


class WorkerRunner:
    """Coordinates registered workers and bus dispatch in phase-1 tests."""

    def __init__(self, *, registry: WorkerRegistry, bus: WorkerBus) -> None:
        self.registry = registry
        self.bus = bus
        self._terminal_error_sent = False
        self._started = False

    async def start(self) -> None:
        """Start all workers."""
        try:
            await self.registry.start_all()
        except Exception as exc:
            self.publish_terminal_error(
                Frame.system(
                    "agent.terminal_error",
                    payload={
                        "code": "WORKER_STARTUP_ERROR",
                        "message": str(exc),
                    },
                )
            )
            await self.registry.stop_all()
            raise
        self._started = True

    async def stop(self) -> None:
        """Stop all workers idempotently."""
        await self.registry.stop_all()
        self._started = False

    def interrupt(self) -> int:
        """Cancel queued interruptible frames."""
        return self.bus.cancel_interruptible()

    def publish_terminal_error(self, frame: Frame) -> bool:
        """Publish one terminal error frame and suppress duplicates."""
        if self._terminal_error_sent:
            return False
        self._terminal_error_sent = True
        self.bus.publish(frame)
        return True

    async def run_until_idle(self) -> list[DispatchResult]:
        """Dispatch frames until the bus is empty."""
        results: list[DispatchResult] = []
        while self.bus.pending_count:
            result = await self.bus.dispatch_next()
            if result is not None:
                results.append(result)
        return results
