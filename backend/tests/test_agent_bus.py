from __future__ import annotations

from collections.abc import Sequence

from sighttalk_api.agent.bus import (
    BaseWorker,
    ProcessorPipeline,
    WorkerBus,
    WorkerRegistry,
    WorkerRunner,
)
from sighttalk_api.agent.frames import Frame


async def test_worker_bus_dispatches_system_frames_first() -> None:
    registry = WorkerRegistry()
    worker = RecordingWorker(worker_id="worker", subscriptions={"event"})
    registry.register(worker)
    await registry.start_all()
    bus = WorkerBus(registry)

    bus.publish(Frame.data("event", payload={"order": "data"}))
    bus.publish(Frame.system("event", payload={"order": "system"}))

    result = await bus.dispatch_next()

    assert result is not None
    assert result.frame.payload["order"] == "system"
    assert worker.received[0].payload["order"] == "system"


async def test_worker_bus_cancels_interruptible_queued_frames_only() -> None:
    registry = WorkerRegistry()
    worker = RecordingWorker(worker_id="worker", subscriptions={"event"})
    registry.register(worker)
    await registry.start_all()
    bus = WorkerBus(registry)

    bus.publish(Frame.data("event", payload={"drop": True}))
    bus.publish(Frame.system("event", payload={"keep": True}))

    assert bus.cancel_interruptible() == 1

    result = await bus.dispatch_next()

    assert result is not None
    assert result.frame.payload == {"keep": True}
    assert bus.pending_count == 0


async def test_worker_bus_routes_targeted_frames_to_active_subscriber() -> None:
    registry = WorkerRegistry()
    first = RecordingWorker(worker_id="first", subscriptions={"memory.search"})
    second = RecordingWorker(worker_id="second", subscriptions={"memory.search"})
    registry.register(first)
    registry.register(second)
    await registry.start_all()
    bus = WorkerBus(registry)

    bus.publish(Frame.data("memory.search", target="second"))
    result = await bus.dispatch_next()

    assert result is not None
    assert result.delivered_to == ("second",)
    assert first.received == []
    assert len(second.received) == 1


async def test_inactive_worker_does_not_receive_frames() -> None:
    registry = WorkerRegistry()
    worker = RecordingWorker(worker_id="worker", subscriptions={"event"})
    registry.register(worker)
    bus = WorkerBus(registry)

    bus.publish(Frame.data("event"))
    result = await bus.dispatch_next()

    assert result is not None
    assert result.delivered_to == ()
    assert worker.received == []


async def test_pipeline_worker_output_is_requeued() -> None:
    registry = WorkerRegistry()
    processor = EchoProcessor()
    worker = RecordingWorker(
        worker_id="worker",
        subscriptions={"input", "output"},
        pipeline=ProcessorPipeline([processor]),
    )
    registry.register(worker)
    await registry.start_all()
    bus = WorkerBus(registry)

    bus.publish(Frame.data("input"))
    results = await WorkerRunner(registry=registry, bus=bus).run_until_idle()

    assert [result.frame.type for result in results] == ["input", "output"]


def test_worker_runner_suppresses_duplicate_terminal_errors() -> None:
    registry = WorkerRegistry()
    bus = WorkerBus(registry)
    runner = WorkerRunner(registry=registry, bus=bus)

    assert runner.publish_terminal_error(Frame.system("terminal.error"))
    assert not runner.publish_terminal_error(Frame.system("terminal.error"))
    assert bus.pending_count == 1


class RecordingWorker(BaseWorker):
    def __init__(
        self,
        *,
        worker_id: str,
        subscriptions: set[str],
        pipeline: ProcessorPipeline | None = None,
    ) -> None:
        super().__init__(worker_id=worker_id, subscriptions=subscriptions)
        self.received: list[Frame] = []
        self._pipeline = pipeline

    async def handle_frame(self, frame: Frame) -> Sequence[Frame]:
        self.received.append(frame)
        if self._pipeline is None:
            return ()
        return await self._pipeline.process(frame)


class EchoProcessor:
    async def process(self, frame: Frame) -> Sequence[Frame]:
        if frame.type == "input":
            return [Frame.data("output")]
        return ()
