from __future__ import annotations

import asyncio
import logging
import re
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Protocol


log = logging.getLogger(__name__)


class TtsSynthesizer(Protocol):
    def synthesize_wav(self, text: str) -> bytes | None: ...


class TtsSocket(Protocol):
    async def send_json(self, data: dict) -> None: ...

    async def send_bytes(self, data: bytes) -> None: ...


_SENTENCE_END_RE = re.compile(r"[.!?]+(?=\s|$)")
_NON_TERMINAL_DOT_TOKENS = {
    "арт",
    "г",
    "д",
    "ед",
    "им",
    "компл",
    "мл",
    "пог",
    "пр",
    "руб",
    "стр",
    "т",
    "тел",
    "ул",
    "шт",
}


def split_tts_chunks(text: str, *, sentences_per_chunk: int = 2) -> tuple[str, ...]:
    """Split natural text into ordered chunks of no more than two sentences.

    A decimal number has no following whitespace after its dot, and list markers
    such as ``1.`` are explicitly kept with the following sentence. This keeps
    catalog prices, articles and numbered product choices intact.
    """
    if sentences_per_chunk < 1:
        raise ValueError("sentences_per_chunk must be positive")
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return ()

    sentences: list[str] = []
    start = 0
    for match in _SENTENCE_END_RE.finditer(normalized):
        end = match.end()
        punctuation = match.group()
        before = normalized[start : match.start()].rstrip()
        token_match = re.search(r"([\wа-яёА-ЯЁ]+)$", before)
        token = token_match.group(1).lower() if token_match else ""
        is_list_marker = punctuation == "." and token.isdigit()
        is_abbreviation = punctuation == "." and token in _NON_TERMINAL_DOT_TOKENS
        if is_list_marker or is_abbreviation:
            continue
        sentence = normalized[start:end].strip()
        if sentence:
            sentences.append(sentence)
        start = end

    tail = normalized[start:].strip()
    if tail:
        sentences.append(tail)
    if not sentences:
        sentences.append(normalized)

    return tuple(" ".join(sentences[index : index + sentences_per_chunk]) for index in range(0, len(sentences), sentences_per_chunk))


@dataclass(slots=True)
class _TtsChunk:
    session_id: str
    generation: int
    socket: TtsSocket
    text: str
    index: int
    total: int


@dataclass(slots=True)
class _SessionQueue:
    queue: asyncio.Queue[_TtsChunk | None] = field(default_factory=asyncio.Queue)
    generation: int = 0
    worker: asyncio.Task[None] | None = None


class TtsDeliveryQueue:
    """Per-session ordered TTS delivery with one shared Silero inference lane.

    The shared lane prevents concurrent access to a single Torch/Silero model.
    Each session owns its own FIFO queue and jobs retain both the session id and
    socket, so an audio buffer can only be sent back to the client that created
    it.  A generation counter invalidates all queued and in-flight older speech
    immediately after a barge-in or a new client message.
    """

    def __init__(self, synthesizer: TtsSynthesizer):
        self._synthesizer = synthesizer
        self._sessions: dict[str, _SessionQueue] = {}
        self._synthesis_lock = asyncio.Lock()

    async def enqueue(self, session_id: str, socket: TtsSocket, text: str) -> None:
        chunks = split_tts_chunks(text)
        if not chunks:
            return
        state = self._state_for(session_id)
        for index, chunk in enumerate(chunks, start=1):
            await state.queue.put(
                _TtsChunk(
                    session_id=session_id,
                    generation=state.generation,
                    socket=socket,
                    text=chunk,
                    index=index,
                    total=len(chunks),
                )
            )

    async def cancel_session(self, session_id: str) -> None:
        """Invalidate queued speech without cancelling an unsafe Torch thread."""
        state = self._sessions.get(session_id)
        if state is None:
            return
        await self._cancel_session_state(state)

    async def wait_idle(self, session_id: str) -> None:
        """Wait until the currently enqueued chunks for one session are delivered."""
        state = self._sessions.get(session_id)
        if state is not None:
            await state.queue.join()

    async def close_session(self, session_id: str) -> None:
        """Release a disconnected session after its active synthesis is safe to stop."""
        state = self._sessions.pop(session_id, None)
        if state is None:
            return
        await self._cancel_session_state(state)
        await state.queue.put(None)
        if state.worker is not None:
            with suppress(asyncio.CancelledError):
                await state.worker

    async def shutdown(self) -> None:
        await asyncio.gather(*(self.close_session(session_id) for session_id in tuple(self._sessions)), return_exceptions=True)

    def _state_for(self, session_id: str) -> _SessionQueue:
        state = self._sessions.get(session_id)
        if state is not None:
            return state
        state = _SessionQueue()
        state.worker = asyncio.create_task(self._run_session(session_id, state))
        self._sessions[session_id] = state
        return state

    async def _run_session(self, session_id: str, state: _SessionQueue) -> None:
        while True:
            item = await state.queue.get()
            try:
                if item is None:
                    return
                if item.generation != state.generation:
                    continue
                async with self._synthesis_lock:
                    if item.generation != state.generation:
                        continue
                    wav = await asyncio.to_thread(self._synthesizer.synthesize_wav, item.text)
                if item.generation != state.generation or not wav:
                    continue
                await item.socket.send_json(
                    {
                        "event": "assistant_tts_start",
                        "session_id": item.session_id,
                        "chunk_index": item.index,
                        "chunk_count": item.total,
                    }
                )
                await item.socket.send_bytes(wav)
                await item.socket.send_json(
                    {
                        "event": "assistant_tts_end",
                        "session_id": item.session_id,
                        "chunk_index": item.index,
                        "chunk_count": item.total,
                    }
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("TTS chunk failed (%s/%s): %s", item.index, item.total, type(exc).__name__)
                if item.generation == state.generation:
                    with suppress(Exception):
                        await item.socket.send_json({"event": "tts_error", "code": "synthesis"})
            finally:
                state.queue.task_done()

    async def _cancel_session_state(self, state: _SessionQueue) -> None:
        state.generation += 1
        while True:
            try:
                state.queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            else:
                state.queue.task_done()
