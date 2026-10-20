"""Sandboxed code runner for the coding round.

Runs ONLY inside the locked-down `interview-runner` container (no network, no secrets, read-only
filesystem, dropped capabilities, pids/memory limits). The web app talks to it over a unix socket.
Per run we add rlimits (cpu, memory, file size, open files, processes), a wall-clock timeout that
kills the whole process group, a scrubbed environment and capped output.
"""
import asyncio
import json
import os
import resource
import shutil
import signal
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

MAX_OUT = 64 * 1024
# language -> (file name, argv template, address-space limit in MB (0 = none), max processes)
LANGS = {
    "python": ("main.py", ["python3", "-I", "-B", "{f}"], 384, 128),
    "javascript": ("main.js", ["node", "--max-old-space-size=96", "{f}"], 0, 128),
}


def execute(lang: str, code: str, stdin: str = "", timeout: float = 5.0) -> dict:
    spec = LANGS.get(lang)
    if spec is None:
        return {"ok": False, "error": "Unsupported language"}
    fname, argv, as_mb, nproc = spec
    if shutil.which(argv[0]) is None:
        return {"ok": False, "error": f"{lang} runtime is not installed"}
    cpu = int(timeout) + 1

    def limits():
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUT * 2, MAX_OUT * 2))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_NPROC, (nproc, nproc))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if as_mb:
            resource.setrlimit(resource.RLIMIT_AS, (as_mb << 20, as_mb << 20))

    with tempfile.TemporaryDirectory(prefix="run-") as d:
        path, out_p, err_p = (os.path.join(d, n) for n in (fname, "out", "err"))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(code)
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": d, "LANG": "C.UTF-8"}
        timed_out, t0 = False, time.time()
        with open(out_p, "wb") as fo, open(err_p, "wb") as fe:
            p = subprocess.Popen([a.replace("{f}", path) for a in argv], stdin=subprocess.PIPE, stdout=fo,
                                 stderr=fe, cwd=d, env=env, preexec_fn=limits, start_new_session=True)
            try:
                p.communicate(stdin.encode()[:MAX_OUT], timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
            try:  # kill anything left in the process group (also covers fork bombs)
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                pass
            p.wait()
        read = lambda f, n: open(f, "rb").read(n).decode("utf-8", "replace")  # noqa: E731
        return {"ok": True, "stdout": read(out_p, MAX_OUT), "stderr": read(err_p, 4000), "exit": p.returncode,
                "timed_out": timed_out, "ms": int((time.time() - t0) * 1000)}


async def serve(path: str) -> None:
    pool, loop = ThreadPoolExecutor(2), asyncio.get_running_loop()

    async def handle(r: asyncio.StreamReader, w: asyncio.StreamWriter):
        try:
            req = json.loads(await asyncio.wait_for(r.readline(), 5))
            res = await loop.run_in_executor(pool, lambda: execute(
                str(req["lang"]), str(req["code"]), str(req.get("stdin", "")), min(float(req.get("timeout", 5)), 10)))
        except Exception as exc:  # never let one bad request kill the runner
            res = {"ok": False, "error": f"bad request: {exc}"}
        w.write((json.dumps(res) + "\n").encode())
        await w.drain()
        w.close()

    if os.path.exists(path):
        os.unlink(path)
    server = await asyncio.start_unix_server(handle, path=path, limit=1 << 20)
    os.chmod(path, 0o666)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(serve(os.environ.get("RUNNER_SOCKET", "/run/runner/sock")))
