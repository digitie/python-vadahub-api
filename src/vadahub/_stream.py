"""native 객체를 소유한 producer를 한 worker에서 실행하는 bounded 전달기."""
import asyncio
from collections.abc import AsyncGenerator, Callable, Generator
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import closing
import threading
from typing import TypeVar

T = TypeVar('T')


async def iter_worker(producer: Callable[[threading.Event], Generator[T, None, None]], *, batch_size: int,
                      estimate: Callable[[T], int]) -> AsyncGenerator[T, None]:
    """최대2 batch·각4MiB 목표. 취소/조기종료 시 worker가 끝난 뒤 반환한다."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[list[T] | Exception | None] = asyncio.Queue(maxsize=2)
    stop = threading.Event()

    def send(value: list[T] | Exception | None) -> bool:
        if stop.is_set():
            return False
        future = asyncio.run_coroutine_threadsafe(queue.put(value), loop)
        while not stop.is_set():
            try:
                future.result(timeout=0.1)
                return True
            except FutureTimeout:
                continue
        future.cancel()
        return False

    def worker() -> None:
        try:
            batch: list[T] = []
            size = 0
            with closing(producer(stop)) as records:
                for item in records:
                    cost = estimate(item)
                    if batch and size + cost > 4 * 1024 * 1024:
                        if not send(batch): return
                        batch, size = [], 0
                    batch.append(item)
                    size += cost
                    if len(batch) >= batch_size or size >= 4 * 1024 * 1024:
                        if not send(batch): return
                        batch, size = [], 0
            if batch and not send(batch): return
        except Exception as exc:
            exc.__traceback__ = None
            exc.__cause__ = None
            exc.__context__ = None
            send(exc)
        finally:
            send(None)

    task = asyncio.create_task(asyncio.to_thread(worker))
    try:
        while True:
            value = await queue.get()
            if value is None: break
            if isinstance(value, Exception): raise value
            for item in value: yield item
    finally:
        stop.set()
        while not task.done():
            try: await asyncio.shield(task)
            except asyncio.CancelledError: continue
        task.result()
