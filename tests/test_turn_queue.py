import asyncio

from app.turn_queue import TurnQueue


def test_three_slots_hold_until_playback_then_fifo_and_cancel():
    async def run():
        q = TurnQueue(3)
        events = []
        admitted = []
        release = [asyncio.Event() for _ in range(5)]
        async def job(i):
            async def notify(e): events.append((i, e))
            async with q.slot(str(i), notify) as turn:
                admitted.append(i)
                await release[i].wait()
                q.acknowledge('wrong-session', turn.token)
                assert not turn.playback_done.is_set()
                q.acknowledge(str(i), turn.token)
                await turn.playback_done.wait()
        tasks = [asyncio.create_task(job(i)) for i in range(5)]
        for _ in range(10): await asyncio.sleep(0)
        assert admitted == [0, 1, 2]
        assert any(i == 4 and e.get('position') == 2 for i, e in events)
        tasks[3].cancel()
        await asyncio.gather(tasks[3], return_exceptions=True)
        release[0].set()
        for _ in range(10): await asyncio.sleep(0)
        assert admitted == [0, 1, 2, 4]
        for e in release: e.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        assert not q.active and not q.waiting
    asyncio.run(run())


def test_admission_timeout_does_not_leak_slot():
    async def run():
        q = TurnQueue(1)
        async def notify(e): pass
        async with q.slot('first', notify):
            try:
                async with q.slot('second', notify, wait_timeout=.01): pass
            except asyncio.TimeoutError: pass
            assert not q.waiting and len(q.active) == 1
        assert not q.active
    asyncio.run(run())
