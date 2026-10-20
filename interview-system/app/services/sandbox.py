"""Client for the sandbox runner. `socket` mode (production) talks to the isolated runner container;
`local` mode (tests/dev only) executes in-process and must never be used in production."""
import asyncio
import json
import logging

from starlette.concurrency import run_in_threadpool

from ..config import get_settings
from ..runner import execute

log = logging.getLogger("sandbox")


class RunnerUnavailable(Exception):
    pass


async def run_code(lang: str, code: str, stdin: str = "", timeout: float = 5.0) -> dict:
    s = get_settings()
    if s.runner_mode == "local":
        return await run_in_threadpool(execute, lang, code, stdin, timeout)
    try:
        r, w = await asyncio.wait_for(asyncio.open_unix_connection(s.runner_socket, limit=1 << 20), 3)
        w.write(json.dumps({"lang": lang, "code": code, "stdin": stdin, "timeout": timeout}).encode() + b"\n")
        await w.drain()
        line = await asyncio.wait_for(r.readline(), timeout + 8)
        w.close()
        return json.loads(line)
    except (OSError, asyncio.TimeoutError, ValueError) as exc:
        log.error("Runner unavailable: %s", exc)
        raise RunnerUnavailable(str(exc))
