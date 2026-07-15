import asyncio
import contextlib
import os
import shlex
import threading
from collections.abc import AsyncIterator, Sequence

DEFAULT_CAMERA_COMMAND = (
    "rpicam-vid",
    "--codec",
    "mjpeg",
    "--timeout",
    "0",
    "--width",
    "640",
    "--height",
    "480",
    "--framerate",
    "15",
    "--nopreview",
    "--output",
    "-",
)
JPEG_END = b"\xff\xd9"
JPEG_START = b"\xff\xd8"
MAX_STDERR_BYTES = 4096
CAMERA_BUSY_MESSAGE = "Camera stream is already active"
_camera_process_lock = threading.Lock()


class CameraStreamError(Exception):
    """Raised when the Pi camera stream cannot be started or read."""


def camera_command() -> Sequence[str]:
    configured = os.getenv("R2D2_CAMERA_COMMAND")
    if configured:
        return shlex.split(configured)

    return DEFAULT_CAMERA_COMMAND


async def drain_stderr(stream: asyncio.StreamReader | None) -> bytes:
    if stream is None:
        return b""

    captured = bytearray()
    while True:
        chunk = await stream.read(1024)
        if not chunk:
            break
        captured.extend(chunk)
        if len(captured) > MAX_STDERR_BYTES:
            del captured[: len(captured) - MAX_STDERR_BYTES]
    return bytes(captured)


def extract_jpeg_frame(buffer: bytes) -> tuple[bytes | None, bytes]:
    start = buffer.find(JPEG_START)
    if start == -1:
        return None, b""

    end = buffer.find(JPEG_END, start + len(JPEG_START))
    if end == -1:
        return None, buffer[start:]

    frame_end = end + len(JPEG_END)
    return buffer[start:frame_end], buffer[frame_end:]


async def stream_camera_frames(
    command: Sequence[str] | None = None,
) -> AsyncIterator[bytes]:
    resolved_command = command or camera_command()
    if not resolved_command:
        raise CameraStreamError("Camera command is empty")

    if not _camera_process_lock.acquire(blocking=False):
        raise CameraStreamError(CAMERA_BUSY_MESSAGE)

    try:
        try:
            process = await asyncio.create_subprocess_exec(
                *resolved_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            message = f"Camera command not found: {resolved_command[0]}"
            raise CameraStreamError(message) from exc

        if process.stdout is None:
            raise CameraStreamError("Camera process did not expose stdout")

        buffer = b""
        stderr_task = asyncio.create_task(drain_stderr(process.stderr))
        stopped_by_server = False
        try:
            while True:
                chunk = await process.stdout.read(8192)
                if not chunk:
                    break

                buffer += chunk
                while True:
                    frame, buffer = extract_jpeg_frame(buffer)
                    if frame is None:
                        break
                    yield frame
        finally:
            if process.returncode is None:
                stopped_by_server = True
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except TimeoutError:
                    process.kill()
                    await process.wait()
            if not stderr_task.done():
                stderr_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await stderr_task

        if stopped_by_server:
            return

        stderr = await stderr_task
        message = stderr.decode(errors="replace").strip()
        if process.returncode not in (0, None):
            raise CameraStreamError(
                message or f"Camera exited with {process.returncode}"
            )
    finally:
        _camera_process_lock.release()
