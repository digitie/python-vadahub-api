"""취소 뒤에도 파일을 사용하는 worker가 끝난 후 소유 파일을 정리한다."""
import asyncio
from collections.abc import Callable
from typing import TypeVar

T = TypeVar('T')


async def run_io(function: Callable[..., T], *args: object) -> T:
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            if task.cancelled():
                raise
            cancelled = True
        except Exception:
            if cancelled:
                raise asyncio.CancelledError from None
            raise
    if cancelled:
        raise asyncio.CancelledError
    return result
