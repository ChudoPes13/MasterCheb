from __future__ import annotations

import asyncio

from app.tts_queue import TtsDeliveryQueue, split_tts_chunks


class FakeSocket:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.audio: list[bytes] = []

    async def send_json(self, data: dict) -> None:
        self.events.append(data)

    async def send_bytes(self, data: bytes) -> None:
        self.audio.append(data)


class FakeTts:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def synthesize_wav(self, text: str) -> bytes:
        self.calls.append(text)
        return text.encode("utf-8")


def test_split_tts_chunks_groups_two_sentences_without_breaking_codes_and_numbers():
    assert split_tts_chunks("1. Арт. UM.4.WMRV110 стоит 250.50 ₽. Первая готова! Вторая тоже? Третья.") == (
        "1. Арт. UM.4.WMRV110 стоит 250.50 ₽. Первая готова!",
        "Вторая тоже? Третья.",
    )


def test_tts_queue_keeps_each_session_and_chunk_order_isolated():
    async def run() -> tuple[FakeSocket, FakeSocket, FakeTts]:
        synth = FakeTts()
        queue = TtsDeliveryQueue(synth)
        first = FakeSocket()
        second = FakeSocket()
        await queue.enqueue("first", first, "Первая. Вторая! Третья.")
        await queue.enqueue("second", second, "Отдельная фраза.")
        await asyncio.gather(queue.wait_idle("first"), queue.wait_idle("second"))
        return first, second, synth

    first, second, synth = asyncio.run(run())

    assert first.audio == ["Первая. Вторая!".encode(), "Третья.".encode()]
    assert second.audio == ["Отдельная фраза.".encode()]
    assert [event["session_id"] for event in first.events] == ["first"] * 4
    assert [event["session_id"] for event in second.events] == ["second"] * 2
    assert synth.calls.index("Первая. Вторая!") < synth.calls.index("Третья.")


def test_tts_queue_drops_invalidated_speech_before_sending_it():
    async def run() -> FakeSocket:
        synth = FakeTts()
        queue = TtsDeliveryQueue(synth)
        socket = FakeSocket()
        await queue.enqueue("same-session", socket, "Старая фраза.")
        await queue.cancel_session("same-session")
        await queue.wait_idle("same-session")
        return socket

    socket = asyncio.run(run())

    assert socket.audio == []
    assert socket.events == []
