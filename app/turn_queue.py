"""FIFO turn admission. A slot covers recognition, generation, delivery and playback."""
import asyncio
import secrets
from collections import deque
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field


class QueueFull(Exception):
    pass


@dataclass(eq=False)
class Turn:
    session_id: str
    notify: object
    token: str = field(default_factory=lambda: secrets.token_urlsafe(18))
    admitted: asyncio.Event = field(default_factory=asyncio.Event)
    playback_done: asyncio.Event = field(default_factory=asyncio.Event)


class TurnQueue:
    def __init__(self, capacity=3, max_waiting=24):
        self.capacity = capacity
        self.max_waiting = max_waiting
        self.active = set()
        self.waiting = deque()

    def _admit(self):
        while self.waiting and len(self.active) < self.capacity:
            turn = self.waiting.popleft()
            self.active.add(turn)
            turn.admitted.set()

    async def _positions(self):
        for position, turn in enumerate(tuple(self.waiting), 1):
            with suppress(Exception):
                await turn.notify({'event': 'turn_status', 'state': 'queued', 'position': position})

    @asynccontextmanager
    async def slot(self, session_id, notify, wait_timeout=90):
        if len(self.waiting) >= self.max_waiting:
            raise QueueFull()
        turn = Turn(session_id, notify)
        self.waiting.append(turn)
        try:
            self._admit()
            await self._positions()
            await asyncio.wait_for(turn.admitted.wait(), wait_timeout)
            await notify({'event': 'turn_status', 'state': 'processing', 'turn_id': turn.token})
            yield turn
        finally:
            self.active.discard(turn)
            with suppress(ValueError):
                self.waiting.remove(turn)
            self._admit()
            await self._positions()

    def acknowledge(self, session_id, token):
        for turn in self.active:
            if turn.session_id == session_id and turn.token == token:
                turn.playback_done.set()
